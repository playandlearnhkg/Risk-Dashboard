"""
data/market_data.py — Daily OHLCV ingestion into `daily_prices`.
================================================================

Incremental by design: on each run, every ticker is fetched only from its own
last stored date, not from the configured start date. On a 530-ticker universe
that is the difference between a multi-minute full refetch and a few seconds.

Two details that matter more than they look:

  * OVERLAP. Fetching resumes `overlap_days` BEFORE the last stored date
    rather than exactly at it. Vendors restate recent bars — late splits,
    dividend adjustments, corrected volume — and a strict resume would freeze
    the first version of each bar forever. The primary key makes the re-fetch
    idempotent, so the overlap costs nothing but correctness improves.

  * ADJUSTED vs RAW. Both `close` and `adj_close` are stored. Layer 2's
    momentum factors need adjusted prices (a split is not a -50% return),
    while execution and any price-level logic need the raw close. Storing only
    one forces a wrong choice later.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from core.logging_setup import get_logger

log = get_logger("data.market")

COLUMNS = ["ticker", "date", "open", "high", "low", "close", "adj_close", "volume"]


@dataclass
class PriceStats:
    """Outcome of a price ingest."""
    tickers_requested: int = 0
    tickers_updated: int = 0
    tickers_failed: int = 0
    rows_written: int = 0
    up_to_date: int = 0
    failed_tickers: list[str] = field(default_factory=list)
    earliest: Optional[str] = None
    latest: Optional[str] = None


def _resume_dates(db, tickers: list[str], default_start: dt.date,
                  overlap_days: int) -> dict[str, dt.date]:
    """
    Per-ticker fetch start: last stored date minus the overlap.

    One query for all tickers rather than one per ticker; on 500+ names the
    round-trip cost of the naive version is noticeable.
    """
    rows = db.query(
        "SELECT ticker, MAX(date) AS last_date FROM daily_prices GROUP BY ticker"
    )
    stored = {r["ticker"]: r["last_date"] for r in rows}

    out: dict[str, dt.date] = {}
    for t in tickers:
        last = stored.get(t)
        if not last:
            out[t] = default_start
            continue
        try:
            out[t] = dt.date.fromisoformat(last) - dt.timedelta(days=overlap_days)
        except (ValueError, TypeError):
            out[t] = default_start
    return out


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce a provider frame into the daily_prices schema."""
    if df is None or df.empty:
        return pd.DataFrame(columns=COLUMNS)

    out = df.copy()
    for col in COLUMNS:
        if col not in out.columns:
            out[col] = None

    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date", "ticker"])
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")

    for col in ("open", "high", "low", "close", "adj_close", "volume"):
        out[col] = pd.to_numeric(out[col], errors="coerce")

    # A bar with no close is not a bar. Keep rows missing only adj_close —
    # some providers omit it and the momentum code falls back to close.
    out = out.dropna(subset=["close"])
    out = out[out["close"] > 0]
    out = out.drop_duplicates(subset=["ticker", "date"], keep="last")
    return out[COLUMNS]


def ingest(db, provider, tickers: list[str], cfg,
           full_refresh: bool = False) -> PriceStats:
    """Fetch and store daily prices for `tickers`."""
    stats = PriceStats(tickers_requested=len(tickers))
    if not tickers:
        return stats

    mcfg = cfg.get("data.market_data", {}) or {}
    default_start = dt.date.fromisoformat(mcfg.get("start_date", "2015-01-01"))
    overlap = int(mcfg.get("overlap_days", 5))
    incremental = bool(mcfg.get("incremental", True)) and not full_refresh

    today = dt.date.today()

    if incremental:
        resume = _resume_dates(db, tickers, default_start, overlap)
        # Anything already current through the last trading day is skipped
        # entirely — no request, no rate-limit budget spent.
        pending = {t: d for t, d in resume.items() if d < today}
        stats.up_to_date = len(tickers) - len(pending)
    else:
        pending = {t: default_start for t in tickers}

    if not pending:
        log.info("All %d tickers already current", len(tickers))
        return stats

    # Group tickers by resume date so each batch is a single provider call.
    # Most tickers share a resume date, so this collapses to very few groups.
    groups: dict[dt.date, list[str]] = {}
    for ticker, start in pending.items():
        groups.setdefault(start, []).append(ticker)

    log.info("Fetching prices for %d tickers in %d date-group(s)…",
             len(pending), len(groups))

    for start, group in sorted(groups.items()):
        log.debug("  %d tickers from %s", len(group), start)
        try:
            raw = provider.get_prices(group, start=start, end=None)
        except Exception as exc:                       # noqa: BLE001
            log.warning("price fetch failed for %d tickers: %s", len(group), exc)
            stats.tickers_failed += len(group)
            stats.failed_tickers.extend(group)
            continue

        clean = _clean(raw)
        if clean.empty:
            stats.tickers_failed += len(group)
            stats.failed_tickers.extend(group)
            continue

        written = db.upsert_many(
            "daily_prices", COLUMNS,
            list(clean.itertuples(index=False, name=None)),
        )
        stats.rows_written += written

        returned = set(clean["ticker"])
        stats.tickers_updated += len(returned)
        missing = [t for t in group if t not in returned]
        stats.tickers_failed += len(missing)
        stats.failed_tickers.extend(missing)

    row = db.query("SELECT MIN(date) AS lo, MAX(date) AS hi FROM daily_prices")
    if row:
        stats.earliest, stats.latest = row[0]["lo"], row[0]["hi"]

    log.info("Prices: %d rows for %d tickers (%d already current, %d failed)",
             stats.rows_written, stats.tickers_updated,
             stats.up_to_date, stats.tickers_failed)
    if stats.failed_tickers:
        log.debug("failed: %s", ", ".join(sorted(stats.failed_tickers)[:25]))
    return stats


# ---------------------------------------------------------------------------
# Read helpers for Layers 2+
# ---------------------------------------------------------------------------

def get_price_history(db, ticker: str, days: int = 400,
                      adjusted: bool = True) -> Optional[pd.Series]:
    """
    Close-price series for one ticker, oldest first.

    `adjusted=True` returns adj_close where available (correct for returns and
    momentum); falls back to close when the provider omitted it.
    """
    cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    rows = db.query(
        "SELECT date, close, adj_close FROM daily_prices "
        "WHERE ticker = ? AND date >= ? ORDER BY date", (ticker, cutoff),
    )
    if not rows:
        return None
    idx, vals = [], []
    for r in rows:
        price = (r["adj_close"] if adjusted and r["adj_close"] else r["close"])
        if price:
            idx.append(pd.Timestamp(r["date"]))
            vals.append(float(price))
    if not vals:
        return None
    return pd.Series(vals, index=pd.DatetimeIndex(idx)).sort_index()


def get_price_matrix(db, tickers: list[str], days: int = 400,
                     adjusted: bool = True) -> pd.DataFrame:
    """
    Wide price matrix (dates x tickers) for cross-sectional work.

    Layer 2's crowding detection needs pairwise factor correlations across the
    whole universe, which is a matrix operation — pulling 500 series
    individually and concatenating is far slower than one query.
    """
    if not tickers:
        return pd.DataFrame()
    cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    placeholders = ",".join("?" * len(tickers))
    rows = db.query(
        f"SELECT ticker, date, close, adj_close FROM daily_prices "
        f"WHERE ticker IN ({placeholders}) AND date >= ? ORDER BY date",
        (*tickers, cutoff),
    )
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(
        [(r["ticker"], r["date"],
          (r["adj_close"] if adjusted and r["adj_close"] else r["close"]))
         for r in rows],
        columns=["ticker", "date", "price"],
    )
    df["date"] = pd.to_datetime(df["date"])
    return df.pivot(index="date", columns="ticker", values="price").sort_index()


def coverage_report(db) -> dict[str, object]:
    """Freshness summary, printed by run_data and shown in Layer 7."""
    latest = db.scalar("SELECT MAX(date) FROM daily_prices")
    total = db.scalar("SELECT COUNT(DISTINCT ticker) FROM daily_prices") or 0
    stale = 0
    if latest:
        stale = db.scalar(
            "SELECT COUNT(*) FROM (SELECT ticker, MAX(date) AS d FROM daily_prices "
            "GROUP BY ticker HAVING d < ?)", (latest,)
        ) or 0
    return {"latest_date": latest, "tickers": total, "stale_tickers": stale}
