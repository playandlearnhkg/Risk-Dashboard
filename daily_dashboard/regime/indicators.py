"""
regime/indicators.py — Fetching and scoring the Layer 0 indicators.
===================================================================

Every indicator in the Capital & Regime engine ends up as a single number on
the same 0-100 scale, where **100 always means "more capital available / more
risk-on"**, regardless of which direction the raw series moves. That
normalisation is what lets money-availability and risk-appetite indicators be
combined at all.

Three scoring methods, chosen per indicator in config.yaml:

  ramp              Map between two absolute thresholds. Use when the levels
                    have meaning in themselves -- VIX at 30 is stress whatever
                    the last three years looked like.

  percentile        Rank the latest value in its own trailing distribution.
                    Use when the series has no natural absolute scale, or when
                    its scale drifts (Fed balance sheet, MMF AUM -- both grow
                    structurally, so "high vs its own history" is the only
                    meaningful reading).

  trend_percentile  Percentile of the N-day RATE OF CHANGE rather than the
                    level. Use where direction carries the signal and level
                    does not: copper/gold and AUDJPY matter for which way they
                    are going, not for where they happen to sit.

Nothing here raises on a bad feed. A missing indicator returns
`available=False`, and the composite re-weights over what remains -- a dead
series must never be silently scored as neutral, because "no data" and
"perfectly average" are very different statements.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd

from core.logging_setup import get_logger

log = get_logger("regime.indicators")


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class IndicatorReading:
    """One indicator, fetched and scored."""

    key: str
    label: str
    score: Optional[float]            # 0-100, 100 = more capital / more risk-on
    raw_value: Optional[float]        # the underlying number, for display
    display: str                      # formatted raw value with units
    weight: float
    method: str
    direction: str
    source: str
    as_of: Optional[dt.date]
    note: str = ""
    error: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def available(self) -> bool:
        return self.score is not None

    @property
    def stance(self) -> str:
        """Coarse label for console/UI colouring."""
        if self.score is None:
            return "na"
        if self.score >= 60:
            return "risk_on"
        if self.score <= 40:
            return "risk_off"
        return "neutral"


# ---------------------------------------------------------------------------
# Scoring primitives
# ---------------------------------------------------------------------------

def score_ramp(value: Optional[float], at_100: float, at_0: float) -> Optional[float]:
    """
    Linear map from raw value to 0-100.

    `at_100` is the value scoring 100, `at_0` the value scoring 0. Either may
    be the larger number, which is how a single function handles both
    "higher is better" and "lower is better" without a direction flag.
    """
    if value is None:
        return None
    span = at_0 - at_100
    if span == 0:
        return 100.0 if value == at_100 else 0.0
    pct = (value - at_100) / span
    return float(max(0.0, min(100.0, (1.0 - pct) * 100.0)))


def score_percentile(series: Optional[pd.Series], direction: str = "up",
                     lookback_days: int = 365 * 5) -> tuple[Optional[float], Optional[float]]:
    """
    Percentile rank of the latest observation within its trailing window.

    Returns (score_0_100, latest_raw_value). With direction='down' the
    percentile is inverted, so a low reading scores high.
    """
    if series is None or series.dropna().empty:
        return None, None
    s = series.dropna()
    if len(s) < 10:
        return None, float(s.iloc[-1])

    cutoff = s.index[-1] - pd.Timedelta(days=lookback_days)
    window = s.loc[cutoff:]
    if len(window) < 10:
        window = s

    latest = float(window.iloc[-1])
    pct = float((window <= latest).mean() * 100.0)
    if direction == "down":
        pct = 100.0 - pct
    return pct, latest


def score_trend_percentile(series: Optional[pd.Series], direction: str = "up",
                           trend_days: int = 60,
                           lookback_days: int = 365 * 3
                           ) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Percentile of the trailing rate of change, not the level.

    Returns (score, latest_level, trend_pct_change).
    """
    if series is None or series.dropna().empty:
        return None, None, None
    s = series.dropna()
    if len(s) < trend_days + 10:
        return None, float(s.iloc[-1]), None

    roc = s.pct_change(periods=trend_days) * 100.0
    roc = roc.dropna()
    if roc.empty:
        return None, float(s.iloc[-1]), None

    score, latest_roc = score_percentile(roc, direction=direction,
                                         lookback_days=lookback_days)
    return score, float(s.iloc[-1]), latest_roc


# ---------------------------------------------------------------------------
# Data access
# ---------------------------------------------------------------------------

class IndicatorSource:
    """
    Fetches the raw series an indicator needs.

    Wraps the Layer 1 providers but stays usable standalone, so Layer 0 can
    run on a machine where the full ingest has never been executed -- the
    regime read is the thing you want working first thing in the morning,
    and it should not depend on a database being populated.
    """

    def __init__(self, cfg, provider=None):
        self.cfg = cfg
        self._provider = provider
        self._fred_cache: dict[str, pd.Series] = {}
        self._yahoo_cache: dict[str, pd.Series] = {}

    # -- FRED ---------------------------------------------------------------

    def fred(self, series_id: str, years: int = 5) -> Optional[pd.Series]:
        if series_id in self._fred_cache:
            return self._fred_cache[series_id]
        try:
            from pandas_datareader import data as pdr
            start = dt.date.today() - dt.timedelta(days=365 * years + 30)
            frame = pdr.DataReader(series_id, "fred", start)
            s = frame.iloc[:, 0].dropna()
            s.index = pd.to_datetime(s.index)
            self._fred_cache[series_id] = s
            return s
        except Exception as exc:
            log.debug("FRED %s failed: %s", series_id, exc)
            return None

    # -- Yahoo --------------------------------------------------------------

    def yahoo(self, ticker: str, years: int = 5) -> Optional[pd.Series]:
        if ticker in self._yahoo_cache:
            return self._yahoo_cache[ticker]
        try:
            import yfinance as yf
            start = dt.date.today() - dt.timedelta(days=365 * years + 30)
            raw = yf.download(ticker, start=start, interval="1d",
                              auto_adjust=True, progress=False, timeout=20)
            if raw is None or raw.empty:
                return None
            close = raw["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            s = close.dropna()
            s.index = pd.to_datetime(s.index).tz_localize(None)
            self._yahoo_cache[ticker] = s
            return s
        except Exception as exc:
            log.debug("Yahoo %s failed: %s", ticker, exc)
            return None

    def ratio(self, numerator: str, denominator: str,
              years: int = 5) -> Optional[pd.Series]:
        """Aligned ratio of two Yahoo series."""
        a, b = self.yahoo(numerator, years), self.yahoo(denominator, years)
        if a is None or b is None:
            return None
        joined = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
        if joined.empty:
            return None
        return (joined["a"] / joined["b"]).dropna()

    # -- FINRA margin debt --------------------------------------------------

    def margin_debt(self) -> Optional[pd.Series]:
        """
        Monthly FINRA margin debt, read from the CSV the parent
        risk-dashboard app already maintains. One copy of the series in the
        repo rather than two that drift apart.
        """
        try:
            path = self.cfg.path("paths.margin_debt_csv")
            if not path.exists():
                log.debug("margin debt CSV not found at %s", path)
                return None
            df = pd.read_csv(path, comment="#")
            df.columns = [c.strip().lower() for c in df.columns]
            if "month" not in df.columns or "debit_balances_musd" not in df.columns:
                return None
            # Placeholder rows must never reach the score.
            if "is_placeholder" in df.columns:
                flags = df["is_placeholder"].astype(str).str.lower()
                if flags.isin(["true", "1", "yes"]).any():
                    log.warning("margin debt CSV contains placeholder rows — skipping")
                    return None
            df["month"] = pd.to_datetime(df["month"], errors="coerce")
            df = df.dropna(subset=["month"]).sort_values("month")
            s = pd.Series(df["debit_balances_musd"].values, index=df["month"])
            return s.dropna()
        except Exception as exc:
            log.debug("margin debt load failed: %s", exc)
            return None

    # -- composite ----------------------------------------------------------

    def net_liquidity(self, components: dict[str, str]) -> Optional[pd.Series]:
        """
        Net liquidity = Fed balance sheet - Treasury General Account - RRP.

        Unit care matters here: WALCL and WTREGEN are published in $ millions
        while RRPONTSYD is in $ billions. Subtracting them raw understates the
        RRP drain by a factor of 1000, which would make the whole series
        wrong in a way that still looks plausible.
        """
        bs = self.fred(components.get("balance_sheet", "WALCL"))
        tga = self.fred(components.get("tga", "WTREGEN"))
        rrp = self.fred(components.get("rrp", "RRPONTSYD"))
        if bs is None:
            return None

        frame = pd.DataFrame({"bs": bs})
        if tga is not None:
            frame["tga"] = tga
        if rrp is not None:
            frame["rrp"] = rrp * 1000.0        # $bn -> $mn

        # Weekly and daily series on one index: forward-fill the slower ones
        # so a daily RRP print does not blank the weekly balance sheet.
        frame = frame.sort_index().ffill().dropna(subset=["bs"])
        net = frame["bs"]
        if "tga" in frame:
            net = net - frame["tga"].fillna(0)
        if "rrp" in frame:
            net = net - frame["rrp"].fillna(0)
        return net.dropna()


# ---------------------------------------------------------------------------
# Indicator evaluation
# ---------------------------------------------------------------------------

def _fmt(value: Optional[float], suffix: str = "", decimals: int = 2,
         thousands: bool = False) -> str:
    if value is None:
        return "n/a"
    spec = f",.{decimals}f" if thousands else f".{decimals}f"
    return f"{value:{spec}}{suffix}"


def evaluate_indicator(key: str, spec: dict, src: IndicatorSource,
                       lookback_years: int) -> IndicatorReading:
    """
    Fetch and score one configured indicator.

    `spec` is the config.yaml block for this indicator. Every failure path
    returns a reading with score=None and a populated `error`, so the caller
    can report exactly which feed is down rather than a silent gap.
    """
    label = key.replace("_", " ").title()
    weight = float(spec.get("weight", 0.0))
    method = spec.get("method", "percentile")
    direction = spec.get("direction", "up")
    source = spec.get("source", "fred")
    note = spec.get("note", "")
    lookback_days = 365 * lookback_years

    def bail(msg: str) -> IndicatorReading:
        return IndicatorReading(
            key=key, label=label, score=None, raw_value=None, display="n/a",
            weight=weight, method=method, direction=direction, source=source,
            as_of=None, note=note, error=msg,
        )

    series: Optional[pd.Series] = None
    unit_suffix = ""
    decimals = 2
    thousands = False

    # ---- resolve the raw series ------------------------------------------
    try:
        if source == "fred":
            series = src.fred(spec["series"], years=lookback_years)
            if (series is None or series.empty) and spec.get("fallback_series"):
                series = src.fred(spec["fallback_series"], years=lookback_years)
                source = f"fred:{spec['fallback_series']}"
            if spec.get("units_billions"):
                unit_suffix = "bn"

        elif source == "yahoo":
            series = src.yahoo(spec["ticker"], years=lookback_years)
            if series is None and spec.get("fallback_source") == "fred":
                series = src.fred(spec["fallback_series"], years=lookback_years)
                source = f"fred:{spec['fallback_series']}"

        elif source == "yahoo_ratio":
            series = src.ratio(spec["numerator"], spec["denominator"],
                               years=lookback_years)
            if series is None and spec.get("fallback_numerator"):
                series = src.ratio(spec["fallback_numerator"],
                                   spec["fallback_denominator"],
                                   years=lookback_years)
                source = (f"yahoo_ratio:{spec['fallback_numerator']}/"
                          f"{spec['fallback_denominator']}")
            decimals = 3

        elif source == "finra_csv":
            series = src.margin_debt()
            thousands = True
            decimals = 0

        elif source == "fred_composite":
            series = src.net_liquidity(spec.get("components", {}))
            thousands = True
            decimals = 0

        else:
            return bail(f"unknown source '{source}'")

    except KeyError as exc:
        return bail(f"config missing key {exc}")
    except Exception as exc:                       # noqa: BLE001
        return bail(f"fetch error: {exc}")

    if series is None or series.dropna().empty:
        return bail("no data returned")

    as_of = series.index[-1].date()

    # ---- score it ---------------------------------------------------------
    detail: dict[str, Any] = {}
    if method == "ramp":
        raw = float(series.iloc[-1])
        score = score_ramp(raw, float(spec["risk_on_at"]), float(spec["risk_off_at"]))
        detail = {"risk_on_at": spec["risk_on_at"], "risk_off_at": spec["risk_off_at"]}

    elif method == "yoy_ramp":
        # Year-over-year percent change, then a ramp. Used for margin debt,
        # where the growth rate carries the signal and the level does not.
        if len(series) < 13:
            return bail("insufficient history for YoY")
        target = series.index[-1] - pd.DateOffset(months=12)
        prior = series.loc[:target]
        if prior.empty or float(prior.iloc[-1]) == 0:
            return bail("no comparable observation 12 months back")
        raw = (float(series.iloc[-1]) / float(prior.iloc[-1]) - 1.0) * 100.0
        score = score_ramp(raw, float(spec["calm"]), float(spec["stress"]))
        # For margin debt the ramp is written calm->stress, i.e. LOW growth
        # scores 0 and HIGH growth scores 100 on the money-availability
        # reading. score_ramp returns 100 at `at_100`, so invert.
        score = 100.0 - score if score is not None else None
        unit_suffix, decimals, thousands = "% YoY", 1, False
        detail = {"calm": spec["calm"], "stress": spec["stress"],
                  "level_musd": float(series.iloc[-1])}

    elif method == "percentile":
        score, raw = score_percentile(series, direction=direction,
                                      lookback_days=lookback_days)
        detail = {"lookback_days": lookback_days}

    elif method == "trend_percentile":
        trend_days = int(spec.get("trend_days", 60))
        score, raw, roc = score_trend_percentile(
            series, direction=direction, trend_days=trend_days,
            lookback_days=lookback_days)
        detail = {"trend_days": trend_days, "trend_pct": roc}
        if roc is not None:
            note = f"{note} ({roc:+.1f}% over {trend_days}d)" if note else ""

    else:
        return bail(f"unknown method '{method}'")

    if score is None:
        return bail("insufficient history to score")

    return IndicatorReading(
        key=key, label=label, score=round(float(score), 1), raw_value=raw,
        display=_fmt(raw, unit_suffix, decimals, thousands),
        weight=weight, method=method, direction=direction, source=source,
        as_of=as_of, note=note, detail=detail,
    )


def evaluate_block(block_cfg: dict, src: IndicatorSource) -> list[IndicatorReading]:
    """Evaluate every enabled indicator in a config block (money or behavior)."""
    lookback_years = int(block_cfg.get("lookback_years", 5))
    readings: list[IndicatorReading] = []
    for key, spec in (block_cfg.get("indicators") or {}).items():
        if not spec.get("enabled", True):
            continue
        reading = evaluate_indicator(key, spec, src, lookback_years)
        readings.append(reading)
        if reading.available:
            log.debug("%s = %.1f (%s)", key, reading.score, reading.display)
        else:
            log.warning("%s unavailable: %s", key, reading.error)
    return readings


def weighted_score(readings: list[IndicatorReading]) -> tuple[Optional[float], float]:
    """
    Weighted mean over AVAILABLE readings, plus the coverage fraction.

    Renormalising over what is available is the whole point: a broken feed
    reduces confidence in the score, it does not drag the score toward zero.
    """
    usable = [r for r in readings if r.available and r.weight > 0]
    if not usable:
        return None, 0.0
    total_w = sum(r.weight for r in usable)
    all_w = sum(r.weight for r in readings if r.weight > 0)
    if total_w == 0:
        return None, 0.0
    score = sum((r.score or 0) * r.weight for r in usable) / total_w
    coverage = total_w / all_w if all_w else 0.0
    return round(score, 1), round(coverage, 3)
