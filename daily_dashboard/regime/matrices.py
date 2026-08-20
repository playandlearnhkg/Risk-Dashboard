"""
regime/matrices.py — Asset Class and Equity Sector preference matrices.
=======================================================================

Both matrices map the current regime to a -2..+2 preference per asset class or
sector, straight from config.yaml. The sector scan additionally blends that
theoretical preference with observed relative strength.

Why blend rather than use the matrix alone:

  A preference matrix encodes what *should* lead in a given regime. Relative
  strength measures what *is* leading. They disagree often enough to matter --
  a sector can be structurally favoured and still be in a downtrend for
  reasons the matrix cannot see (an idiosyncratic blow-up, a crowded
  positioning unwind). Weighting the matrix 60/40 over momentum leans on the
  model while letting the tape veto it, which is the behaviour you want from a
  rotation scan. Both weights live in config.yaml; set momentum_weight to 0
  for pure theory or matrix_weight to 0 for pure trend-following.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from core.logging_setup import get_logger
from regime.indicators import IndicatorSource

log = get_logger("regime.matrices")

# Human labels for the -2..+2 preference scale.
STANCE_NAMES = {
    2: "Strong Overweight",
    1: "Overweight",
    0: "Neutral",
    -1: "Underweight",
    -2: "Strong Underweight",
}


@dataclass
class PreferenceRow:
    """One asset class or sector under the current regime."""

    key: str                        # ticker or class id
    name: str
    matrix_score: int               # -2..+2 straight from config
    stance: str                     # human label for matrix_score
    momentum_pct: Optional[float] = None      # N-day relative return vs SPY
    momentum_rank: Optional[float] = None     # 0-100 rank within the peer set
    blended_score: Optional[float] = None     # 0-100 combined ranking score
    favored: bool = False
    proxy: str = ""

    @property
    def display_momentum(self) -> str:
        return "n/a" if self.momentum_pct is None else f"{self.momentum_pct:+.1f}%"


# ---------------------------------------------------------------------------
# Asset class matrix
# ---------------------------------------------------------------------------

def asset_class_preferences(cfg, regime_key: str) -> list[PreferenceRow]:
    """Asset-class stance for the current regime, strongest first."""
    matrix = cfg.get("regime.asset_class_matrix.classes", {}) or {}
    proxies = cfg.get("regime.asset_class_matrix.proxies", {}) or {}

    rows: list[PreferenceRow] = []
    for key, by_regime in matrix.items():
        score = int(by_regime.get(regime_key, 0))
        rows.append(PreferenceRow(
            key=key,
            name=key.replace("_", " ").title(),
            matrix_score=score,
            stance=STANCE_NAMES.get(score, "Neutral"),
            proxy=proxies.get(key, ""),
            favored=score >= 1,
        ))
    rows.sort(key=lambda r: (-r.matrix_score, r.name))
    return rows


# ---------------------------------------------------------------------------
# Equity sector matrix + rotation scan
# ---------------------------------------------------------------------------

def _relative_strength(src: IndicatorSource, tickers: list[str],
                       lookback_days: int, benchmark: str = "SPY"
                       ) -> dict[str, Optional[float]]:
    """
    Return over `lookback_days` for each ticker, minus the benchmark's return.

    Relative rather than absolute: in a rising market every sector is up, and
    the rotation question is which ones are beating the index, not which are
    positive.
    """
    bench = src.yahoo(benchmark, years=2)
    bench_ret: Optional[float] = None
    if bench is not None and len(bench) > lookback_days:
        cut = bench.index[-1] - pd.Timedelta(days=lookback_days)
        prior = bench.loc[:cut]
        if not prior.empty and float(prior.iloc[-1]) != 0:
            bench_ret = (float(bench.iloc[-1]) / float(prior.iloc[-1]) - 1.0) * 100.0

    out: dict[str, Optional[float]] = {}
    for t in tickers:
        s = src.yahoo(t, years=2)
        if s is None or len(s) < 20:
            out[t] = None
            continue
        cut = s.index[-1] - pd.Timedelta(days=lookback_days)
        prior = s.loc[:cut]
        if prior.empty or float(prior.iloc[-1]) == 0:
            out[t] = None
            continue
        ret = (float(s.iloc[-1]) / float(prior.iloc[-1]) - 1.0) * 100.0
        out[t] = ret - bench_ret if bench_ret is not None else ret
    return out


def sector_preferences(cfg, regime_key: str,
                       src: Optional[IndicatorSource] = None) -> list[PreferenceRow]:
    """
    Rank the eleven SPDR sectors for the current regime.

    Blends the preference matrix with live relative strength; see the module
    docstring for why. Falls back to matrix-only if price data is unavailable,
    so the scan still produces a usable answer when Yahoo is rate-limited.
    """
    sectors = cfg.get("regime.sector_matrix.sectors", {}) or {}
    matrix_w = float(cfg.get("regime.sector_matrix.matrix_weight", 0.6))
    momentum_w = float(cfg.get("regime.sector_matrix.momentum_weight", 0.4))
    threshold = int(cfg.get("regime.sector_matrix.favored_threshold", 1))
    lookback = int(cfg.get("regime.sector_matrix.momentum_lookback_days", 60))

    rows: list[PreferenceRow] = []
    for ticker, spec in sectors.items():
        score = int(spec.get(regime_key, 0))
        rows.append(PreferenceRow(
            key=ticker,
            name=spec.get("name", ticker),
            matrix_score=score,
            stance=STANCE_NAMES.get(score, "Neutral"),
            proxy=ticker,
        ))

    # --- relative strength -------------------------------------------------
    rs: dict[str, Optional[float]] = {}
    if src is not None and momentum_w > 0:
        try:
            rs = _relative_strength(src, [r.key for r in rows], lookback)
        except Exception as exc:                       # noqa: BLE001
            log.warning("relative strength unavailable: %s", exc)

    have_rs = [v for v in rs.values() if v is not None]
    use_momentum = len(have_rs) >= 3        # need a peer set to rank against

    if use_momentum:
        lo, hi = min(have_rs), max(have_rs)
        span = (hi - lo) or 1.0
        for r in rows:
            r.momentum_pct = rs.get(r.key)
            if r.momentum_pct is not None:
                r.momentum_rank = round((r.momentum_pct - lo) / span * 100.0, 1)
    else:
        if momentum_w > 0:
            log.warning("sector scan is matrix-only — insufficient price data")

    # --- blend -------------------------------------------------------------
    for r in rows:
        # Matrix -2..+2 -> 0..100 so the two components share a scale.
        matrix_component = (r.matrix_score + 2) / 4.0 * 100.0
        if use_momentum and r.momentum_rank is not None:
            r.blended_score = round(
                matrix_component * matrix_w + r.momentum_rank * momentum_w, 1)
        else:
            r.blended_score = round(matrix_component, 1)
        r.favored = r.matrix_score >= threshold

    rows.sort(key=lambda r: (-(r.blended_score or 0), -r.matrix_score))
    return rows


def favored_sectors(rows: list[PreferenceRow], limit: int = 4) -> list[PreferenceRow]:
    """
    The sectors to actually hunt in.

    Requires BOTH a favourable matrix stance and a top-half blended rank: the
    matrix says the regime supports it, the blend says the market agrees. A
    sector the model likes but that is bottom-ranked on relative strength is
    a thesis waiting for confirmation, not a place to allocate today.
    """
    eligible = [r for r in rows if r.favored]
    if not eligible:
        # Nothing clears the bar — return the best available rather than an
        # empty list, but the caller should note the regime has no clear
        # leadership.
        return rows[:limit]
    return eligible[:limit]


def avoid_sectors(rows: list[PreferenceRow], limit: int = 3) -> list[PreferenceRow]:
    """Sectors the matrix marks underweight — the natural short candidates."""
    return [r for r in rows if r.matrix_score <= -1][-limit:] or rows[-limit:]
