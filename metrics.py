"""
metrics.py — Turns raw feeds into the numbers the dashboard actually displays.
=============================================================================

Everything derived from market data is computed ONCE here and passed to both
the scoring engine and the UI. That guarantees the number in the risk score is
the same number shown on the card — a dashboard that scores off one value and
displays another is worse than no dashboard.

All yields and spreads are in PERCENT (so 4.25 means 4.25%), all changes in
percentage points unless the field name ends in `_pct`, which means a percent
change of a price.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

import config
import data_sources as ds
from data_sources import MarketData
from margin_debt import MarginStats


@dataclass
class Metrics:
    """Every derived value the dashboard needs. `None` always means 'no data'."""

    # --- FX / carry --------------------------------------------------------
    usdjpy: Optional[float] = None
    usdjpy_1d: Optional[float] = None
    usdjpy_1w: Optional[float] = None
    usdjpy_1m: Optional[float] = None
    usdjpy_series: Optional[pd.Series] = None

    crosses: dict[str, dict] = field(default_factory=dict)  # AUDJPY, NZDJPY, ...
    carry_cross_drawdown: Optional[float] = None            # worst of the crosses

    # --- Rates -------------------------------------------------------------
    us2y: Optional[float] = None
    us10y: Optional[float] = None
    us30y: Optional[float] = None
    us2y_1w: Optional[float] = None
    us10y_1w: Optional[float] = None
    us30y_1w: Optional[float] = None
    us2y_series: Optional[pd.Series] = None
    us10y_series: Optional[pd.Series] = None
    us30y_series: Optional[pd.Series] = None

    jp2y: Optional[float] = None
    jp10y: Optional[float] = None
    jp2y_source: str = "unavailable"
    jp10y_source: str = "unavailable"

    diff_2y: Optional[float] = None            # US 2y minus JP 2y
    diff_10y: Optional[float] = None           # US 10y minus JP 10y
    diff_2y_series: Optional[pd.Series] = None
    diff_10y_series: Optional[pd.Series] = None
    diff_2y_change_3m: Optional[float] = None

    curve_10_2: Optional[float] = None
    curve_10_2_series: Optional[pd.Series] = None
    curve_change_3m: Optional[float] = None

    fed_funds: Optional[float] = None
    boj_rate: Optional[float] = None
    policy_gap: Optional[float] = None

    rate_vol_series: Optional[pd.Series] = None
    rate_vol_level: Optional[float] = None
    rate_vol_pctile: Optional[float] = None
    rate_vol_source: str = "unavailable"

    # --- Volatility & credit ----------------------------------------------
    vix: Optional[float] = None
    vix3m: Optional[float] = None
    vix_ratio: Optional[float] = None
    vix_series: Optional[pd.Series] = None

    credit_series: Optional[pd.Series] = None
    credit_kind: str = "none"
    credit_source: str = "unavailable"
    hy_oas: Optional[float] = None
    hy_oas_change_1m: Optional[float] = None
    hyg_lqd_drawdown: Optional[float] = None

    # --- Commodities -------------------------------------------------------
    wti: Optional[float] = None
    wti_1w: Optional[float] = None
    wti_1m: Optional[float] = None
    wti_series: Optional[pd.Series] = None
    wti_vol: Optional[float] = None
    wti_vol_pctile: Optional[float] = None

    gold: Optional[float] = None
    gold_1w: Optional[float] = None
    gold_series: Optional[pd.Series] = None

    copper: Optional[float] = None
    copper_1w: Optional[float] = None
    copper_series: Optional[pd.Series] = None

    # --- Equities & correlation -------------------------------------------
    spx: Optional[float] = None
    spx_1w: Optional[float] = None
    spx_series: Optional[pd.Series] = None
    spx_drawdown: Optional[float] = None
    stock_bond_corr: Optional[float] = None    # 60d corr of SPX and TLT returns

    # --- Leverage ----------------------------------------------------------
    margin: Optional[MarginStats] = None


def compute(md: MarketData, manual: dict, margin_stats: MarginStats) -> Metrics:
    """Build the full Metrics bundle. Never raises; missing feeds stay None."""
    m = Metrics()
    m.margin = margin_stats

    # ---------------------------------------------------------------- FX ---
    usdjpy = md.yf("USDJPY")
    m.usdjpy_series = usdjpy
    m.usdjpy = md.latest(usdjpy)
    m.usdjpy_1d = ds.pct_change_over(usdjpy, 1)
    m.usdjpy_1w = ds.pct_change_over(usdjpy, 7)
    m.usdjpy_1m = ds.pct_change_over(usdjpy, 30)

    # High-carry crosses. AUDJPY is the primary high-beta proxy; the others
    # are shown for confirmation. The scorer uses the WORST drawdown of the
    # set, because a carry unwind rarely hits every cross at once.
    for name in ("AUDJPY", "NZDJPY", "MXNJPY", "EURJPY"):
        s = md.yf(name)
        if s is None:
            continue
        m.crosses[name] = {
            "series": s,
            "level": md.latest(s),
            "d1": ds.pct_change_over(s, 1),
            "w1": ds.pct_change_over(s, 7),
            "m1": ds.pct_change_over(s, 30),
            "dd60": ds.drawdown_from_high(s, 60),
        }
    drawdowns = [c["dd60"] for c in m.crosses.values() if c["dd60"] is not None]
    m.carry_cross_drawdown = min(drawdowns) if drawdowns else None

    # ------------------------------------------------------------- Rates ---
    m.us2y_series = ds.us_yield(md, "2Y")
    m.us10y_series = ds.us_yield(md, "10Y")
    m.us30y_series = ds.us_yield(md, "30Y")
    m.us2y = md.latest(m.us2y_series)
    m.us10y = md.latest(m.us10y_series)
    m.us30y = md.latest(m.us30y_series)
    m.us2y_1w = ds.change_over(m.us2y_series, 7)
    m.us10y_1w = ds.change_over(m.us10y_series, 7)
    m.us30y_1w = ds.change_over(m.us30y_series, 7)

    m.jp2y, m.jp2y_source = ds.jp_yield(md, "2Y", manual)
    m.jp10y, m.jp10y_source = ds.jp_yield(md, "10Y", manual)

    if m.us2y is not None and m.jp2y is not None:
        m.diff_2y = m.us2y - m.jp2y
    if m.us10y is not None and m.jp10y is not None:
        m.diff_10y = m.us10y - m.jp10y

    # Historical differential series. The JGB side is a single manual number,
    # so the HISTORY of the differential is really the history of the US leg
    # shifted by today's JGB yield. That is an approximation and the chart
    # says so — but the SHAPE (which is what matters for spotting compression)
    # is dominated by the US leg anyway, which is far more volatile.
    if m.us2y_series is not None and m.jp2y is not None:
        m.diff_2y_series = (m.us2y_series - m.jp2y).dropna()
        m.diff_2y_change_3m = ds.change_over(m.diff_2y_series, 90)
    if m.us10y_series is not None and m.jp10y is not None:
        m.diff_10y_series = (m.us10y_series - m.jp10y).dropna()

    # Yield curve — FRED's own T10Y2Y is preferred over subtracting two
    # series, since it handles the odd day where one leg is missing.
    curve = md.fr("CURVE_10_2")
    if curve is None and m.us10y_series is not None and m.us2y_series is not None:
        curve = (m.us10y_series - m.us2y_series).dropna()
    m.curve_10_2_series = curve
    m.curve_10_2 = md.latest(curve)
    m.curve_change_3m = ds.change_over(curve, 90)

    ff = md.fr("FED_FUNDS")
    m.fed_funds = md.latest(ff) if ff is not None else manual.get("FED_FUNDS")
    m.boj_rate = manual.get("BOJ_RATE")
    if m.fed_funds is not None and m.boj_rate is not None:
        m.policy_gap = m.fed_funds - m.boj_rate

    rv, rv_src = ds.move_index_or_proxy(md)
    m.rate_vol_series = rv
    m.rate_vol_level = md.latest(rv)
    m.rate_vol_pctile = ds.percentile_of_latest(rv)
    m.rate_vol_source = rv_src

    # -------------------------------------------------- Vol and credit -----
    m.vix, m.vix3m, m.vix_ratio = ds.vix_term_structure(md)
    vix_series = md.yf("VIX")
    if vix_series is None:
        vix_series = md.fr("VIX_FRED")
    m.vix_series = vix_series

    credit, credit_src, credit_kind = ds.credit_spread(md)
    m.credit_series = credit
    m.credit_source = credit_src
    m.credit_kind = credit_kind
    if credit_kind == "oas":
        m.hy_oas = md.latest(credit)
        m.hy_oas_change_1m = ds.change_over(credit, 30)
    elif credit_kind == "ratio":
        m.hyg_lqd_drawdown = ds.drawdown_from_high(credit, 180)

    # ------------------------------------------------------ Commodities ----
    wti = md.yf("WTI")
    if wti is None:
        wti = md.fr("WTI_FRED")
    m.wti_series = wti
    m.wti = md.latest(wti)
    m.wti_1w = ds.pct_change_over(wti, 7)
    m.wti_1m = ds.pct_change_over(wti, 30)
    wti_vol = ds.realised_vol(wti, window=20)
    m.wti_vol = md.latest(wti_vol)
    m.wti_vol_pctile = ds.percentile_of_latest(wti_vol)

    gold = md.yf("GOLD")
    m.gold_series, m.gold = gold, md.latest(gold)
    m.gold_1w = ds.pct_change_over(gold, 7)

    copper = md.yf("COPPER")
    m.copper_series, m.copper = copper, md.latest(copper)
    m.copper_1w = ds.pct_change_over(copper, 7)

    # --------------------------------------------------------- Equities ----
    spx = md.yf("SPX")
    m.spx_series, m.spx = spx, md.latest(spx)
    m.spx_1w = ds.pct_change_over(spx, 7)
    m.spx_drawdown = ds.drawdown_from_high(spx, 365)

    # Stock/bond correlation regime. When it turns POSITIVE, bonds stop
    # hedging equities and every 60/40-style portfolio is more fragile than
    # its historical volatility suggests.
    tlt = md.yf("TLT")
    if spx is not None and tlt is not None:
        joined = pd.concat(
            [spx.pct_change().rename("spx"), tlt.pct_change().rename("tlt")],
            axis=1,
        ).dropna()
        if len(joined) >= 60:
            m.stock_bond_corr = float(joined["spx"].tail(60).corr(joined["tlt"].tail(60)))

    return m
