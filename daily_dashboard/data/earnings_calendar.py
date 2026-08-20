"""
data/earnings_calendar.py — Upcoming earnings dates.
====================================================

Earnings dates matter to this system as a RISK GATE more than as a signal.
Layer 4 sizes down or defers entries into a print, and Layer 5 treats an
imminent report as a reason to cap position size: a stock can be a perfect
factor candidate and still be a coin flip three days before it reports.

`is_confirmed` distinguishes a company-announced date from a vendor estimate.
Estimated dates drift by a week or more, so anything unconfirmed should widen
the blackout window rather than be trusted precisely.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Iterable

import pandas as pd

from core.logging_setup import get_logger

log = get_logger("data.earnings")

COLUMNS = ["ticker", "earnings_date", "eps_estimate", "is_confirmed", "fetched_at"]


@dataclass
class EarningsStats:
    tickers_requested: int = 0
    events: int = 0
    tickers_with_events: int = 0
    failed: list[str] = field(default_factory=list)


def ingest(db, provider, tickers: Iterable[str], days_ahead: int = 30) -> EarningsStats:
    """Fetch upcoming earnings dates within `days_ahead`."""
    tickers = list(tickers)
    stats = EarningsStats(tickers_requested=len(tickers))
    fetched_at = dt.datetime.now().isoformat(timespec="seconds")

    rows: list[tuple] = []
    for i, ticker in enumerate(tickers, 1):
        if i % 100 == 0:
            log.info("  earnings calendar %d/%d…", i, len(tickers))
        try:
            df = provider.get_earnings_dates(ticker, days_ahead=days_ahead)
        except Exception as exc:                       # noqa: BLE001
            log.debug("earnings fetch failed for %s: %s", ticker, exc)
            stats.failed.append(ticker)
            continue
        if df is None or df.empty:
            continue
        for r in df.itertuples(index=False):
            rows.append((ticker, getattr(r, "earnings_date", None),
                         getattr(r, "eps_estimate", None), 0, fetched_at))
        stats.tickers_with_events += 1

    if rows:
        stats.events = db.upsert_many("earnings_calendar", COLUMNS, rows)

    log.info("Earnings calendar: %d events for %d tickers",
             stats.events, stats.tickers_with_events)
    return stats


def upcoming(db, days: int = 30) -> pd.DataFrame:
    """Earnings between today and `days` ahead, soonest first."""
    today = dt.date.today().isoformat()
    horizon = (dt.date.today() + dt.timedelta(days=days)).isoformat()
    rows = db.query(
        "SELECT ticker, earnings_date, eps_estimate, is_confirmed "
        "FROM earnings_calendar WHERE earnings_date BETWEEN ? AND ? "
        "ORDER BY earnings_date", (today, horizon),
    )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([dict(r) for r in rows])
    df["days_away"] = (pd.to_datetime(df["earnings_date"])
                       - pd.Timestamp.today().normalize()).dt.days
    return df


def reporting_within(db, days: int = 5) -> set[str]:
    """
    Tickers reporting within `days` — the blackout set for Layers 4 and 5.

    Returned as a set because the only question asked of it is membership.
    """
    df = upcoming(db, days=days)
    return set(df["ticker"]) if not df.empty else set()
