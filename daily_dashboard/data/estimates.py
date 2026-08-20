"""
data/estimates.py — Analyst estimate daily snapshots.
=====================================================

Same rationale as short_interest, and more consequential: Layer 2's Estimate
Revisions factor is built from the 30/60/90-day CHANGE in consensus forward
EPS, and no free provider serves historical consensus. The only way to have
revision data in a month is to start snapshotting today.

Until roughly 30 days of snapshots exist, `revision_deltas` returns nothing
for the 30-day window and Layer 2 scores that factor as degenerate (every
stock 50). That is the correct behaviour — a factor with no data must not
masquerade as a factor with neutral data — and `history_depth` exists so the
run summary can tell you how many days remain before it activates.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Iterable, Optional

import pandas as pd

from core.logging_setup import get_logger

log = get_logger("data.estimates")

COLUMNS = ["ticker", "snapshot_date", "forward_eps", "forward_pe",
           "target_mean", "target_high", "target_low", "analyst_count"]


@dataclass
class EstimateStats:
    tickers_requested: int = 0
    tickers_stored: int = 0
    tickers_failed: int = 0
    failed: list[str] = field(default_factory=list)


def ingest(db, provider, tickers: Iterable[str]) -> EstimateStats:
    """Snapshot forward estimates and price targets for each ticker."""
    tickers = list(tickers)
    stats = EstimateStats(tickers_requested=len(tickers))
    today = dt.date.today().isoformat()

    rows: list[tuple] = []
    for i, ticker in enumerate(tickers, 1):
        if i % 100 == 0:
            log.info("  estimates %d/%d…", i, len(tickers))
        data = provider.get_estimates(ticker) or {}
        if data.get("forward_eps") is None and data.get("target_mean") is None:
            stats.tickers_failed += 1
            stats.failed.append(ticker)
            continue
        rows.append((
            ticker, today, data.get("forward_eps"), data.get("forward_pe"),
            data.get("target_mean"), data.get("target_high"),
            data.get("target_low"), data.get("analyst_count"),
        ))

    if rows:
        stats.tickers_stored = db.upsert_many("analyst_estimates", COLUMNS, rows)

    log.info("Estimates: %d stored, %d unavailable",
             stats.tickers_stored, stats.tickers_failed)
    return stats


def get_latest(db) -> pd.DataFrame:
    """Most recent estimate snapshot per ticker."""
    rows = db.query(
        "SELECT e.* FROM analyst_estimates e "
        "JOIN (SELECT ticker, MAX(snapshot_date) AS d FROM analyst_estimates "
        "      GROUP BY ticker) latest "
        "  ON e.ticker = latest.ticker AND e.snapshot_date = latest.d"
    )
    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()


def revision_deltas(db, windows: tuple[int, ...] = (30, 60, 90)) -> pd.DataFrame:
    """
    Percent change in consensus forward EPS over each window.

    Returns one column per available window (`eps_chg_30d`, …). A window with
    insufficient history is simply absent from the frame, which is how Layer 2
    knows to equal-weight only the deltas that exist.
    """
    latest_date = db.scalar("SELECT MAX(snapshot_date) FROM analyst_estimates")
    if not latest_date:
        return pd.DataFrame()

    current = db.query(
        "SELECT ticker, forward_eps FROM analyst_estimates WHERE snapshot_date = ?",
        (latest_date,),
    )
    if not current:
        return pd.DataFrame()
    df = pd.DataFrame([dict(r) for r in current]).rename(
        columns={"forward_eps": "eps_now"})

    latest = dt.date.fromisoformat(latest_date)
    for window in windows:
        target = (latest - dt.timedelta(days=window)).isoformat()
        prior_date = db.scalar(
            "SELECT MAX(snapshot_date) FROM analyst_estimates WHERE snapshot_date <= ?",
            (target,),
        )
        if not prior_date or prior_date == latest_date:
            continue        # not enough history yet for this window

        prior = db.query(
            "SELECT ticker, forward_eps FROM analyst_estimates WHERE snapshot_date = ?",
            (prior_date,),
        )
        if not prior:
            continue
        pdf = pd.DataFrame([dict(r) for r in prior]).rename(
            columns={"forward_eps": f"eps_{window}d_ago"})
        df = df.merge(pdf, on="ticker", how="left")

        col_prior = f"eps_{window}d_ago"
        df[f"eps_chg_{window}d"] = df.apply(
            lambda r, c=col_prior: ((r["eps_now"] / r[c] - 1) * 100)
            # Guard the sign flip: EPS going from -1.00 to +0.50 is not a
            # -150% revision. Only compute growth off a positive base.
            if pd.notna(r.get(c)) and r.get(c) and r[c] > 0 and pd.notna(r["eps_now"])
            else None, axis=1)
    return df


def history_depth(db) -> dict[str, object]:
    """Snapshot history, and which revision windows are usable yet."""
    first = db.scalar("SELECT MIN(snapshot_date) FROM analyst_estimates")
    last = db.scalar("SELECT MAX(snapshot_date) FROM analyst_estimates")
    days = 0
    if first and last:
        days = (dt.date.fromisoformat(last) - dt.date.fromisoformat(first)).days
    return {
        "first": first, "last": last, "days": days,
        "snapshots": db.scalar(
            "SELECT COUNT(DISTINCT snapshot_date) FROM analyst_estimates") or 0,
        "windows_ready": [w for w in (30, 60, 90) if days >= w],
    }
