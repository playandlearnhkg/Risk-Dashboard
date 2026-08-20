"""
data/short_interest.py — Short interest daily snapshots.
========================================================

Exchanges publish short interest twice monthly with a settlement lag, so the
underlying figure only changes every couple of weeks. This module snapshots it
DAILY anyway, keyed on (ticker, snapshot_date).

That is deliberate. Layer 2's short-interest factor needs the CHANGE versus a
prior period, and no free provider serves historical short interest — you can
only get "as of now". Snapshotting daily is the only way to accumulate that
history. Repeated identical values cost a few KB and are exactly what makes
the third sub-factor computable a month from now.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Iterable, Optional

import pandas as pd

from core.logging_setup import get_logger

log = get_logger("data.short_interest")

COLUMNS = ["ticker", "snapshot_date", "shares_short", "short_ratio",
           "short_percent_of_float"]


@dataclass
class ShortInterestStats:
    tickers_requested: int = 0
    tickers_stored: int = 0
    tickers_failed: int = 0
    failed: list[str] = field(default_factory=list)


def ingest(db, provider, tickers: Iterable[str]) -> ShortInterestStats:
    """Snapshot short interest for each ticker as of today."""
    tickers = list(tickers)
    stats = ShortInterestStats(tickers_requested=len(tickers))
    today = dt.date.today().isoformat()

    rows: list[tuple] = []
    for i, ticker in enumerate(tickers, 1):
        if i % 100 == 0:
            log.info("  short interest %d/%d…", i, len(tickers))
        data = provider.get_short_interest(ticker) or {}
        if not any(v is not None for v in data.values()):
            stats.tickers_failed += 1
            stats.failed.append(ticker)
            continue
        rows.append((ticker, today, data.get("shares_short"),
                     data.get("short_ratio"), data.get("short_percent_of_float")))

    if rows:
        stats.tickers_stored = db.upsert_many("short_interest", COLUMNS, rows)

    log.info("Short interest: %d stored, %d unavailable",
             stats.tickers_stored, stats.tickers_failed)
    return stats


def get_latest(db) -> pd.DataFrame:
    """Most recent snapshot per ticker."""
    rows = db.query(
        "SELECT s.* FROM short_interest s "
        "JOIN (SELECT ticker, MAX(snapshot_date) AS d FROM short_interest "
        "      GROUP BY ticker) latest "
        "  ON s.ticker = latest.ticker AND s.snapshot_date = latest.d"
    )
    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()


def get_change(db, days: int = 30) -> pd.DataFrame:
    """
    Change in short interest versus the snapshot closest to `days` ago.

    Returns an empty frame until enough history has accumulated — Layer 2
    treats that as a degenerate sub-factor and scores it neutral rather than
    inventing a change from a single observation.
    """
    latest_date = db.scalar("SELECT MAX(snapshot_date) FROM short_interest")
    if not latest_date:
        return pd.DataFrame()

    target = (dt.date.fromisoformat(latest_date) - dt.timedelta(days=days)).isoformat()
    prior_date = db.scalar(
        "SELECT MAX(snapshot_date) FROM short_interest WHERE snapshot_date <= ?",
        (target,),
    )
    if not prior_date or prior_date == latest_date:
        return pd.DataFrame()

    rows = db.query(
        "SELECT c.ticker, c.short_percent_of_float AS pct_now, "
        "       p.short_percent_of_float AS pct_prior, "
        "       c.shares_short AS shares_now, p.shares_short AS shares_prior "
        "FROM short_interest c JOIN short_interest p ON c.ticker = p.ticker "
        "WHERE c.snapshot_date = ? AND p.snapshot_date = ?",
        (latest_date, prior_date),
    )
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame([dict(r) for r in rows])
    df["pct_change"] = df["pct_now"] - df["pct_prior"]
    df["shares_pct_change"] = df.apply(
        lambda r: ((r["shares_now"] / r["shares_prior"] - 1) * 100)
        if r["shares_prior"] else None, axis=1)
    df["days_between"] = (dt.date.fromisoformat(latest_date)
                          - dt.date.fromisoformat(prior_date)).days
    return df


def history_depth(db) -> dict[str, object]:
    """How much snapshot history exists — used to warn about degenerate factors."""
    first = db.scalar("SELECT MIN(snapshot_date) FROM short_interest")
    last = db.scalar("SELECT MAX(snapshot_date) FROM short_interest")
    days = 0
    if first and last:
        days = (dt.date.fromisoformat(last) - dt.date.fromisoformat(first)).days
    return {"first": first, "last": last, "days": days,
            "snapshots": db.scalar(
                "SELECT COUNT(DISTINCT snapshot_date) FROM short_interest") or 0}
