"""
data/universe.py — The tradeable universe and its metadata.
===========================================================

Three populations, all in the `universe` table, distinguished by `kind`:

    equity      S&P 500 constituents, scraped from Wikipedia
    benchmark   SPY / QQQ / IWM / DIA
    sector_etf  the eleven SPDR sector ETFs
    regime      the Layer 0 macro tickers (VIX, copper, gold, AUDJPY, …)

Wikipedia is the source for constituents because it is free, current, and
carries GICS sector plus sub-industry — which Layer 2 needs, since every score
is a percentile rank WITHIN a sector. A ticker with no sector cannot be
ranked, so sector coverage is checked explicitly rather than assumed.

Two safety properties matter here:

  * The scrape is gated. If Wikipedia returns fewer than
    `min_expected_constituents` rows, the result is rejected and the existing
    cached universe is kept. A silently truncated universe would quietly
    shrink every downstream layer, and that failure is hard to notice.

  * Departed constituents are marked `is_constituent = 0` rather than deleted,
    so historical prices and scores stay joinable and backtests do not
    develop survivorship bias.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from core.logging_setup import get_logger

log = get_logger("data.universe")


@dataclass
class UniverseStats:
    """Outcome of a refresh, for the run summary."""
    constituents: int = 0
    added: int = 0
    removed: int = 0
    benchmarks: int = 0
    refreshed: bool = False
    source: str = ""
    error: str = ""


def _today() -> str:
    return dt.date.today().isoformat()


def needs_refresh(db, refresh_days: int) -> bool:
    """True if the cached universe is missing or older than refresh_days."""
    last_seen = db.scalar(
        "SELECT MAX(last_seen) FROM universe WHERE kind = 'equity'"
    )
    if not last_seen:
        return True
    try:
        age = (dt.date.today() - dt.date.fromisoformat(last_seen[:10])).days
    except ValueError:
        return True
    return age >= refresh_days


def scrape_sp500(url: str, timeout: int = 20) -> Optional[pd.DataFrame]:
    """
    Scrape the current S&P 500 list.

    Returns a frame with ticker / company_name / gics_sector / sub_industry,
    or None if the page could not be parsed into something usable.
    """
    import io

    import requests

    try:
        # Wikipedia blocks the default urllib/pandas user agent.
        resp = requests.get(
            url, timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (compatible; MeridianResearch/1.0)"},
        )
        resp.raise_for_status()
        # StringIO, not the raw string: pandas 2.1 deprecated and pandas 3.0
        # removed literal-string input to read_html, and the failure mode is
        # confusing — the string gets treated as a path and the whole document
        # is echoed back in the error.
        tables = pd.read_html(io.StringIO(resp.text))
    except Exception as exc:                       # noqa: BLE001
        log.warning("Wikipedia scrape failed: %s", exc)
        return None

    # Find the constituents table by its columns rather than by position —
    # Wikipedia reorders tables on the page from time to time.
    for table in tables:
        cols = {str(c).strip().lower() for c in table.columns}
        if "symbol" in cols and any("gics" in c for c in cols):
            df = table.copy()
            df.columns = [str(c).strip().lower() for c in df.columns]

            sector_col = next((c for c in df.columns if "gics" in c and "sub" not in c), None)
            sub_col = next((c for c in df.columns if "gics" in c and "sub" in c), None)
            name_col = next((c for c in df.columns if "security" in c or "name" in c), None)

            out = pd.DataFrame({
                # Wikipedia writes BRK.B; Yahoo wants BRK-B.
                "ticker": df["symbol"].astype(str).str.strip().str.replace(".", "-", regex=False),
                "company_name": df[name_col].astype(str).str.strip() if name_col else None,
                "gics_sector": df[sector_col].astype(str).str.strip() if sector_col else None,
                "sub_industry": df[sub_col].astype(str).str.strip() if sub_col else None,
            })
            out = out[out["ticker"].str.len().between(1, 10)]
            return out.drop_duplicates(subset=["ticker"]).reset_index(drop=True)

    log.warning("No constituents table found on the Wikipedia page")
    return None


def _store_static(db, tickers: list[str], kind: str) -> int:
    """Insert benchmark / sector-ETF / regime tickers, preserving first_seen."""
    if not tickers:
        return 0
    today = _today()
    existing = {
        r["ticker"]: r["first_seen"]
        for r in db.query("SELECT ticker, first_seen FROM universe WHERE kind = ?", (kind,))
    }
    rows = [
        (t, None, None, None, 1, kind, existing.get(t, today), today)
        for t in tickers
    ]
    return db.upsert_many(
        "universe",
        ["ticker", "company_name", "gics_sector", "sub_industry",
         "is_constituent", "kind", "first_seen", "last_seen"],
        rows,
    )


def refresh(db, cfg, force: bool = False) -> UniverseStats:
    """Refresh the universe if stale. Always (re)stores the static tickers."""
    stats = UniverseStats()
    ucfg = cfg.get("data.universe", {}) or {}

    # --- static tickers: cheap, always kept current ------------------------
    static = 0
    static += _store_static(db, ucfg.get("benchmarks", []), "benchmark")
    static += _store_static(db, ucfg.get("sector_etfs", []), "sector_etf")
    static += _store_static(db, ucfg.get("regime_tickers", []), "regime")
    stats.benchmarks = static

    # --- constituents ------------------------------------------------------
    refresh_days = int(ucfg.get("refresh_days", 7))
    if not force and not needs_refresh(db, refresh_days):
        stats.constituents = db.scalar(
            "SELECT COUNT(*) FROM universe WHERE kind='equity' AND is_constituent=1"
        ) or 0
        stats.source = "cache"
        log.info("Universe is current (%d constituents); skipping scrape",
                 stats.constituents)
        return stats

    url = ucfg.get("wikipedia_url")
    log.info("Scraping S&P 500 constituents…")
    scraped = scrape_sp500(url, timeout=int(cfg.get("data.timeouts.http_seconds", 20)))

    min_expected = int(ucfg.get("min_expected_constituents", 450))
    if scraped is None or len(scraped) < min_expected:
        got = 0 if scraped is None else len(scraped)
        stats.error = (f"scrape returned {got} rows (< {min_expected}); "
                       "keeping the cached universe")
        stats.constituents = db.scalar(
            "SELECT COUNT(*) FROM universe WHERE kind='equity' AND is_constituent=1"
        ) or 0
        stats.source = "cache (scrape rejected)"
        log.warning(stats.error)
        return stats

    today = _today()
    previous = {
        r["ticker"] for r in
        db.query("SELECT ticker FROM universe WHERE kind='equity' AND is_constituent=1")
    }
    first_seen = {
        r["ticker"]: r["first_seen"]
        for r in db.query("SELECT ticker, first_seen FROM universe WHERE kind='equity'")
    }
    current = set(scraped["ticker"])

    rows = [
        (r.ticker, r.company_name, r.gics_sector, r.sub_industry, 1, "equity",
         first_seen.get(r.ticker, today), today)
        for r in scraped.itertuples(index=False)
    ]
    db.upsert_many(
        "universe",
        ["ticker", "company_name", "gics_sector", "sub_industry",
         "is_constituent", "kind", "first_seen", "last_seen"],
        rows,
    )

    # Mark departures rather than deleting them — see the module docstring.
    departed = previous - current
    for ticker in departed:
        db.execute("UPDATE universe SET is_constituent = 0 WHERE ticker = ?", (ticker,))

    stats.constituents = len(current)
    stats.added = len(current - previous)
    stats.removed = len(departed)
    stats.refreshed = True
    stats.source = "wikipedia"

    missing_sector = int(db.scalar(
        "SELECT COUNT(*) FROM universe WHERE kind='equity' AND is_constituent=1 "
        "AND (gics_sector IS NULL OR gics_sector = '' OR gics_sector = 'nan')"
    ) or 0)
    if missing_sector:
        # Layer 2 ranks within sector, so this is a real defect, not cosmetic.
        log.warning("%d constituents have no GICS sector — they cannot be "
                    "sector-ranked by Layer 2", missing_sector)

    log.info("Universe refreshed: %d constituents (+%d / -%d)",
             stats.constituents, stats.added, stats.removed)
    return stats


# ---------------------------------------------------------------------------
# Read helpers used by the rest of the system
# ---------------------------------------------------------------------------

def get_constituents(db, include_inactive: bool = False) -> list[str]:
    sql = "SELECT ticker FROM universe WHERE kind = 'equity'"
    if not include_inactive:
        sql += " AND is_constituent = 1"
    return [r["ticker"] for r in db.query(sql + " ORDER BY ticker")]


def get_all_tickers(db) -> list[str]:
    """Everything that needs a price history — equities plus every ETF/index."""
    return [r["ticker"] for r in db.query(
        "SELECT ticker FROM universe WHERE is_constituent = 1 ORDER BY ticker")]


def get_sector_map(db) -> dict[str, str]:
    """ticker -> GICS sector, for Layer 2's within-sector percentile ranking."""
    return {
        r["ticker"]: r["gics_sector"]
        for r in db.query(
            "SELECT ticker, gics_sector FROM universe "
            "WHERE kind='equity' AND is_constituent=1 AND gics_sector IS NOT NULL")
    }


def sector_counts(db) -> dict[str, int]:
    """Constituents per sector — small sectors make percentile ranks noisy."""
    return {
        r["gics_sector"]: r["n"]
        for r in db.query(
            "SELECT gics_sector, COUNT(*) AS n FROM universe "
            "WHERE kind='equity' AND is_constituent=1 AND gics_sector IS NOT NULL "
            "GROUP BY gics_sector ORDER BY n DESC")
    }
