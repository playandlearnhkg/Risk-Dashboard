"""
data_sources.py — All external data fetching, with caching and graceful decay.
=============================================================================

Design rules followed here:

  * NOTHING raises. Every fetch is wrapped; a failed feed returns None and the
    UI renders "n/a" instead of the dashboard dying. A macro dashboard that
    crashes because one Yahoo symbol was delisted is useless at 7am.

  * Everything is cached via Streamlit's @st.cache_data with a TTL from
    config.CACHE_TTL_SECONDS. The "Refresh data" button calls
    st.cache_data.clear().

  * Returned frames are always indexed by date, ascending, timezone-naive.
"""

from __future__ import annotations

import datetime as dt
import time
import warnings
from typing import Optional

import pandas as pd
import streamlit as st

import config

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Network time budgets. The dashboard must render in a predictable amount of
# time even when a provider is slow or rate-limiting; missing series are
# handled gracefully everywhere downstream, a five-minute hang is not.
BATCH_TIMEOUT_SECONDS = 30    # the one bulk Yahoo request
SINGLE_TIMEOUT_SECONDS = 8    # each per-symbol retry
RETRY_BUDGET_SECONDS = 45     # total spent retrying missing symbols
FRED_BUDGET_SECONDS = 60      # total spent on all FRED series


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise_index(df: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Force a tz-naive, ascending DatetimeIndex so frames can be joined."""
    if df is None or len(df) == 0:
        return df
    idx = pd.to_datetime(df.index)
    try:
        if getattr(idx, "tz", None) is not None:
            idx = idx.tz_localize(None)
    except (TypeError, AttributeError):
        pass
    out = df.copy()
    out.index = idx.normalize()
    return out.sort_index()


def _start_date() -> dt.date:
    return dt.date.today() - dt.timedelta(days=365 * config.HISTORY_YEARS + 30)


# ---------------------------------------------------------------------------
# Yahoo Finance
# ---------------------------------------------------------------------------

@st.cache_data(ttl=config.CACHE_TTL_SECONDS, show_spinner=False)
def fetch_yahoo(tickers: tuple[str, ...]) -> pd.DataFrame:
    """
    Download daily closes for a tuple of Yahoo symbols.

    Returns a DataFrame of closes with one column per symbol. Symbols that
    fail to download are simply absent from the result — callers must check.
    `tickers` is a tuple (not a list) because Streamlit's cache needs a
    hashable argument.
    """
    import yfinance as yf

    symbols = list(tickers)
    if not symbols:
        return pd.DataFrame()

    try:
        raw = yf.download(
            symbols,
            start=_start_date(),
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=True,
            timeout=BATCH_TIMEOUT_SECONDS,
        )
    except Exception:
        raw = None

    close = _extract_close(raw, symbols)

    # Retry any symbol that came back empty, one at a time. Batch downloads
    # occasionally drop a symbol that works fine on its own.
    #
    # This retry loop runs under a HARD TIME BUDGET. When Yahoo rate-limits you
    # (HTTP 429 — it happens, especially on shared or cloud IPs), every single
    # retry burns yfinance's internal backoff, and twenty of them in a row will
    # hang the dashboard for minutes. Better to render in a known time with
    # some series missing: the risk model already re-weights around gaps, and
    # the next refresh usually recovers them.
    missing = [s for s in symbols if s not in close.columns or close[s].dropna().empty]
    deadline = time.monotonic() + RETRY_BUDGET_SECONDS
    recovered: dict[str, pd.Series] = {}
    for sym in missing:
        if time.monotonic() > deadline:
            break
        try:
            single = yf.Ticker(sym).history(
                start=_start_date(), interval="1d", timeout=SINGLE_TIMEOUT_SECONDS,
            )
            if single is not None and not single.empty and "Close" in single:
                recovered[sym] = _normalise_index(single["Close"])
        except Exception:
            continue

    if recovered:
        # Concat rather than assigning column by column: assignment would
        # reindex each recovered series onto whatever index the batch happened
        # to produce, silently truncating history when the batch was partial.
        close = close.drop(columns=[c for c in recovered if c in close.columns])
        close = pd.concat([close, pd.DataFrame(recovered)], axis=1)

    if close.empty:
        return close
    close = close.dropna(axis=1, how="all")
    return _normalise_index(close)


def _extract_close(raw, symbols: list[str]) -> pd.DataFrame:
    """Pull the Close block out of whatever shape yfinance returned."""
    if raw is None or len(raw) == 0:
        return pd.DataFrame()
    try:
        if isinstance(raw.columns, pd.MultiIndex):
            level0 = set(raw.columns.get_level_values(0))
            if "Close" in level0:                       # (field, ticker)
                close = raw["Close"].copy()
            else:                                       # (ticker, field)
                close = raw.xs("Close", axis=1, level=1).copy()
        else:
            # Flat columns only happen on a single-symbol download. If we asked
            # for several and got flat columns back, we cannot tell which
            # symbol they belong to — return nothing and let the per-symbol
            # retry loop rebuild the frame with correct labels.
            if len(symbols) != 1:
                return pd.DataFrame()
            col = "Close" if "Close" in raw.columns else raw.columns[0]
            close = raw[[col]].copy()
            close.columns = [symbols[0]]
        return _normalise_index(close)
    except Exception:
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# FRED
# ---------------------------------------------------------------------------

@st.cache_data(ttl=config.CACHE_TTL_SECONDS, show_spinner=False)
def fetch_fred(series_ids: tuple[str, ...]) -> pd.DataFrame:
    """
    Download FRED series via pandas-datareader.

    Fetched one series at a time: a single bad/renamed id would otherwise
    fail the whole batch, and FRED is fast enough that it does not matter.
    """
    from pandas_datareader import data as pdr

    frames: dict[str, pd.Series] = {}
    start = _start_date()
    deadline = time.monotonic() + FRED_BUDGET_SECONDS
    for sid in series_ids:
        if time.monotonic() > deadline:
            break
        try:
            got = pdr.DataReader(sid, "fred", start)
            if got is not None and not got.empty:
                frames[sid] = got.iloc[:, 0]
        except Exception:
            continue

    if not frames:
        return pd.DataFrame()
    return _normalise_index(pd.DataFrame(frames))


# ---------------------------------------------------------------------------
# Market data bundle
# ---------------------------------------------------------------------------

class MarketData:
    """
    A thin container holding everything the dashboard needs, plus small
    accessors that keep the "series might be missing" checks in one place.
    """

    def __init__(self, yahoo: pd.DataFrame, fred: pd.DataFrame):
        self.yahoo = yahoo if yahoo is not None else pd.DataFrame()
        self.fred = fred if fred is not None else pd.DataFrame()
        self.fetched_at = dt.datetime.now()

    # -- series lookup ------------------------------------------------------

    def yf(self, name: str) -> Optional[pd.Series]:
        """Get a Yahoo series by its config.YF_TICKERS key (e.g. 'USDJPY')."""
        sym = config.YF_TICKERS.get(name)
        if sym is None or sym not in self.yahoo.columns:
            return None
        s = self.yahoo[sym].dropna()
        return s if not s.empty else None

    def fr(self, name: str) -> Optional[pd.Series]:
        """Get a FRED series by its config.FRED_SERIES key (e.g. 'US2Y')."""
        sid = config.FRED_SERIES.get(name)
        if sid is None or sid not in self.fred.columns:
            return None
        s = self.fred[sid].dropna()
        return s if not s.empty else None

    # -- convenience --------------------------------------------------------

    def latest(self, series: Optional[pd.Series]) -> Optional[float]:
        if series is None or series.empty:
            return None
        return float(series.iloc[-1])

    def as_of(self, series: Optional[pd.Series]) -> Optional[dt.date]:
        if series is None or series.empty:
            return None
        return series.index[-1].date()


@st.cache_data(ttl=config.CACHE_TTL_SECONDS, show_spinner=False)
def _load_raw() -> tuple[pd.DataFrame, pd.DataFrame]:
    yahoo = fetch_yahoo(tuple(config.YF_TICKERS.values()))
    fred = fetch_fred(tuple(config.FRED_SERIES.values()))
    return yahoo, fred


def load_market_data() -> MarketData:
    """Entry point used by app.py. Cached; cleared by the refresh button."""
    yahoo, fred = _load_raw()
    return MarketData(yahoo, fred)


# ---------------------------------------------------------------------------
# US Treasury yields — FRED primary, Yahoo fallback
# ---------------------------------------------------------------------------

def us_yield(md: MarketData, tenor: str) -> Optional[pd.Series]:
    """
    Return a US Treasury yield series in PERCENT for tenor in {2Y, 10Y, 30Y}.

    FRED (DGS2/DGS10/DGS30) is authoritative. Yahoo's ^TNX/^TYX are the
    fallback; note that Yahoo has historically quoted these at 10x the yield,
    so the value is normalised if it looks like basis-point-ish scaling.
    """
    primary = md.fr(f"US{tenor}")
    if primary is not None and len(primary) > 5:
        return primary

    fallback_key = {"10Y": "US10Y_YF", "30Y": "US30Y_YF"}.get(tenor)
    if fallback_key is None:
        return None
    s = md.yf(fallback_key)
    if s is None:
        return None
    # ^TNX has been quoted both as 4.25 and as 42.5 over the years.
    if float(s.iloc[-1]) > 20:
        s = s / 10.0
    return s


def jp_rate_seeds(md: MarketData) -> dict[str, dict]:
    """
    Best-available starting values for the manual Japanese inputs.

    There is no free daily JGB feed, so the sidebar asks the user to type
    these. Rather than opening with a hardcoded number that goes stale the
    moment it is written, each input is SEEDED from FRED's monthly Japanese
    series, and the UI shows where the seed came from and how old it is.

    Returns {key: {"value": float, "source": str, "is_live": bool}} for
    JP2Y, JP10Y and BOJ_RATE.
    """
    def seed(fred_key: str, fallback: float, label: str) -> dict:
        s = md.fr(fred_key)
        if s is not None and not s.empty:
            return {
                "value": round(float(s.iloc[-1]), 3),
                "source": f"{label}, {s.index[-1]:%b %Y}",
                "is_live": True,
            }
        return {
            "value": float(fallback),
            "source": f"config.py fallback ({config.MANUAL_INPUTS_AS_OF})",
            "is_live": False,
        }

    return {
        # No 2-year Japanese series exists on FRED. The 3-month interbank rate
        # is the closest free anchor — it is NOT the 2-year yield, and the UI
        # says so, but it beats a hardcoded guess by a wide margin.
        "JP2Y": seed("JP3M_MONTHLY", config.MANUAL_JP_YIELDS["JP2Y"],
                     "seeded from FRED 3-month interbank"),
        "JP10Y": seed("JP10Y_MONTHLY", config.MANUAL_JP_YIELDS["JP10Y"],
                      "FRED monthly 10-year"),
        "BOJ_RATE": seed("JP_OVERNIGHT", config.MANUAL_POLICY_RATES["BOJ_RATE"],
                         "FRED call money rate"),
    }


def jp_yield(md: MarketData, tenor: str, manual: dict[str, float]) -> tuple[Optional[float], str]:
    """
    Japanese government bond yield for tenor in {'2Y','10Y'}.

    Returns (value_in_percent, source_label). The sidebar value wins, because
    a number the user typed today beats a monthly series lagged by six weeks.
    """
    val = manual.get(f"JP{tenor}")
    if val is not None:
        return float(val), manual.get(f"JP{tenor}_source", "manual entry")

    if tenor == "10Y":
        s = md.fr("JP10Y_MONTHLY")
        if s is not None and not s.empty:
            return float(s.iloc[-1]), f"FRED monthly, {s.index[-1].date()}"
    return None, "unavailable"


# ---------------------------------------------------------------------------
# Derived series
# ---------------------------------------------------------------------------

def move_index_or_proxy(md: MarketData) -> tuple[Optional[pd.Series], str]:
    """
    Treasury volatility. Prefers the real MOVE index; falls back to a
    realised-volatility proxy built from daily 10-year yield changes.

    The proxy is annualised standard deviation of daily yield changes,
    expressed in basis points per year — not the same units as MOVE, which is
    why the risk score uses a PERCENTILE of this series rather than its level.
    """
    move = md.yf("MOVE")
    if move is not None and len(move) > 60:
        return move, "MOVE index (Yahoo)"

    ten = us_yield(md, "10Y")
    if ten is None or len(ten) < 60:
        return None, "unavailable"

    daily_change_bp = ten.diff() * 100.0            # yield in %, so ×100 = bp
    proxy = daily_change_bp.rolling(20).std() * (252 ** 0.5)
    proxy = proxy.dropna()
    if proxy.empty:
        return None, "unavailable"
    return proxy, "proxy: 20d realised vol of 10y yield (annualised bp)"


def credit_spread(md: MarketData) -> tuple[Optional[pd.Series], str, str]:
    """
    High-yield credit stress.

    Returns (series, source_label, kind) where kind is either:
      'oas'   -> the series is a spread in percentage points (higher = worse)
      'ratio' -> the series is the HYG/LQD price ratio (lower = worse)
    """
    oas = md.fr("HY_OAS")
    if oas is not None and len(oas) > 30:
        return oas, "ICE BofA US High Yield OAS (FRED)", "oas"

    hyg, lqd = md.yf("HYG"), md.yf("LQD")
    if hyg is not None and lqd is not None:
        ratio = (hyg / lqd).dropna()
        if not ratio.empty:
            return ratio, "HYG / LQD price ratio (Yahoo)", "ratio"
    return None, "unavailable", "none"


def vix_term_structure(md: MarketData) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """Return (vix, vix3m, ratio). Ratio > 1.0 means backwardation."""
    vix = md.yf("VIX")
    if vix is None:
        vix = md.fr("VIX_FRED")
    v3 = md.yf("VIX3M")

    v_now = float(vix.iloc[-1]) if vix is not None and not vix.empty else None
    v3_now = float(v3.iloc[-1]) if v3 is not None and not v3.empty else None
    ratio = (v_now / v3_now) if (v_now and v3_now) else None
    return v_now, v3_now, ratio


def pct_change_over(series: Optional[pd.Series], days: int) -> Optional[float]:
    """
    Percent change over the last `days` CALENDAR days.

    Calendar rather than trading days so "1 week" means what a human means by
    one week regardless of holidays. Returns None if there is no observation
    old enough to compare against.
    """
    if series is None or series.empty:
        return None
    s = series.dropna()
    if len(s) < 2:
        return None
    target = s.index[-1] - pd.Timedelta(days=days)
    prior = s.loc[:target]
    if prior.empty:
        return None
    base = float(prior.iloc[-1])
    if base == 0:
        return None
    return (float(s.iloc[-1]) / base - 1.0) * 100.0


def change_over(series: Optional[pd.Series], days: int) -> Optional[float]:
    """Absolute (not percent) change over the last `days` calendar days."""
    if series is None or series.empty:
        return None
    s = series.dropna()
    if len(s) < 2:
        return None
    target = s.index[-1] - pd.Timedelta(days=days)
    prior = s.loc[:target]
    if prior.empty:
        return None
    return float(s.iloc[-1]) - float(prior.iloc[-1])


def drawdown_from_high(series: Optional[pd.Series], window_days: int) -> Optional[float]:
    """Percent below the highest close of the trailing `window_days`."""
    if series is None or series.empty:
        return None
    s = series.dropna()
    cutoff = s.index[-1] - pd.Timedelta(days=window_days)
    window = s.loc[cutoff:]
    if window.empty:
        return None
    peak = float(window.max())
    if peak == 0:
        return None
    return (float(s.iloc[-1]) / peak - 1.0) * 100.0


def percentile_of_latest(series: Optional[pd.Series], window_days: int = 365 * 3) -> Optional[float]:
    """Where the latest value sits in its own trailing distribution, 0-100."""
    if series is None or series.empty:
        return None
    s = series.dropna()
    cutoff = s.index[-1] - pd.Timedelta(days=window_days)
    window = s.loc[cutoff:]
    if len(window) < 30:
        return None
    return float((window <= window.iloc[-1]).mean() * 100.0)


def realised_vol(series: Optional[pd.Series], window: int = 20) -> Optional[pd.Series]:
    """Annualised rolling realised volatility of daily returns, in percent."""
    if series is None or len(series) < window + 5:
        return None
    rets = series.pct_change()
    vol = rets.rolling(window).std() * (252 ** 0.5) * 100.0
    vol = vol.dropna()
    return vol if not vol.empty else None
