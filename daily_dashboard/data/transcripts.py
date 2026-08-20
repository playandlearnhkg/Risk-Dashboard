"""
data/transcripts.py — Earnings call transcripts (FMP, optional).
================================================================

Transcripts are fetched ONLY for candidates, never for the whole universe.
Two reasons: FMP charges per call and rate-limits, and a full-universe pull
would be several hundred requests for text that Layer 3 will only read for the
handful of names that actually reach the shortlist.

Without FMP_API_KEY this module is inert — it logs once and returns empty
stats. Nothing else in the system depends on transcripts being present.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Iterable, Optional

from core.logging_setup import get_logger

log = get_logger("data.transcripts")


@dataclass
class TranscriptStats:
    tickers_requested: int = 0
    stored: int = 0
    skipped_no_key: bool = False
    failed: list[str] = field(default_factory=list)


def _recent_quarters(n: int = 2) -> list[tuple[int, int]]:
    """The last `n` completed calendar quarters as (year, quarter) pairs."""
    today = dt.date.today()
    quarter = (today.month - 1) // 3 + 1
    year = today.year
    out: list[tuple[int, int]] = []
    for _ in range(n):
        quarter -= 1
        if quarter == 0:
            quarter, year = 4, year - 1
        out.append((year, quarter))
    return out


def ingest(db, cfg, tickers: Iterable[str], quarters: int = 2) -> TranscriptStats:
    """Fetch recent transcripts for the given (candidate) tickers."""
    tickers = list(tickers)
    stats = TranscriptStats(tickers_requested=len(tickers))

    if not cfg.has_secret("FMP_API_KEY"):
        stats.skipped_no_key = True
        log.info("Transcripts skipped — FMP_API_KEY not set")
        return stats

    from data.providers import FMPProvider
    provider = FMPProvider(cfg)

    rows: list[tuple] = []
    for ticker in tickers:
        for year, quarter in _recent_quarters(quarters):
            period = f"{year}Q{quarter}"
            already = db.scalar(
                "SELECT COUNT(*) FROM transcripts WHERE ticker = ? AND period = ?",
                (ticker, period),
            )
            if already:
                continue        # transcripts are immutable once published
            content = provider.get_transcript(ticker, year, quarter)
            if not content:
                continue
            rows.append((ticker, period, None, content))

    if rows:
        stats.stored = db.upsert_many(
            "transcripts", ["ticker", "period", "call_date", "content"], rows)

    log.info("Transcripts: %d stored for %d tickers", stats.stored, len(tickers))
    return stats


def get_transcript(db, ticker: str, period: Optional[str] = None) -> Optional[str]:
    """Most recent transcript for a ticker, or a specific period."""
    if period:
        return db.scalar(
            "SELECT content FROM transcripts WHERE ticker = ? AND period = ?",
            (ticker, period),
        )
    return db.scalar(
        "SELECT content FROM transcripts WHERE ticker = ? "
        "ORDER BY period DESC LIMIT 1", (ticker,),
    )
