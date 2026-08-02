"""
scoring.py — The systematic risk score. Deliberately simple and auditable.
=========================================================================

THE WHOLE MODEL IN FIVE LINES
-----------------------------
1. Each raw signal becomes a 0-1 stress score via a linear ramp between two
   thresholds (config.THRESHOLDS): 0 at "calm", 1 at "stressed".
2. Signals are blended into eight components (config.SUB_WEIGHTS).
3. Components are blended into a 0-100 composite (config.WEIGHTS), with
   missing components dropped and the rest re-normalised.
4. Escalation rules (config.ESCALATIONS) can FLOOR the composite when a
   specific dangerous combination is present.
5. The composite maps to Low / Elevated / High (config.REGIME_BANDS).

Every intermediate value is kept on the result object so the UI can show its
work. Nothing here is a black box, and nothing is fitted to history — these
are judgement thresholds, chosen to be readable and editable, not optimised.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import config
from metrics import Metrics


# ---------------------------------------------------------------------------
# The ramp — the one piece of maths in the whole model
# ---------------------------------------------------------------------------

def ramp(value: Optional[float], calm: float, stress: float) -> Optional[float]:
    """
    Map `value` to a 0-1 stress score.

        score = 0.0 at or beyond `calm`
        score = 1.0 at or beyond `stress`
        linear in between

    Works in both directions: if stress < calm the signal is "lower is worse"
    (e.g. USDJPY 1-month change, where -7% is worse than -2%).
    """
    if value is None:
        return None
    span = stress - calm
    if span == 0:
        return 1.0 if value >= stress else 0.0
    return max(0.0, min(1.0, (value - calm) / span))


def level_from_score(score: Optional[float]) -> str:
    """Convert a 0-1 score to a traffic-light level."""
    if score is None:
        return "na"
    if score >= 0.62:
        return "high"
    if score >= 0.34:
        return "elevated"
    return "low"


def regime_from_composite(composite: float) -> str:
    if composite >= config.REGIME_BANDS["high_above"]:
        return "high"
    if composite >= config.REGIME_BANDS["elevated_above"]:
        return "elevated"
    return "low"


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class SignalResult:
    key: str
    label: str
    value: Optional[float]
    display: str
    score: Optional[float]
    weight: float
    thresholds: tuple[float, float]

    @property
    def level(self) -> str:
        return level_from_score(self.score)


@dataclass
class ComponentResult:
    key: str
    label: str
    weight: float
    score: Optional[float]
    signals: list[SignalResult] = field(default_factory=list)
    note: str = ""

    @property
    def level(self) -> str:
        return level_from_score(self.score)

    @property
    def available(self) -> bool:
        return self.score is not None


@dataclass
class RiskAssessment:
    composite: float
    base_composite: float          # before escalations
    regime: str
    components: list[ComponentResult]
    escalations: list[tuple[str, float, str]]
    missing: list[str]
    coverage_pct: float            # share of total weight that had data

    def component(self, key: str) -> Optional[ComponentResult]:
        for c in self.components:
            if c.key == key:
                return c
        return None

    @property
    def top_drivers(self) -> list[ComponentResult]:
        """Components ranked by their actual contribution to the composite."""
        avail = [c for c in self.components if c.available]
        return sorted(avail, key=lambda c: (c.score or 0) * c.weight, reverse=True)


# ---------------------------------------------------------------------------
# Signal construction
# ---------------------------------------------------------------------------

def _sig(key: str, label: str, value: Optional[float], display: str,
         weight: float) -> SignalResult:
    """Build a SignalResult, pulling thresholds from config by key."""
    calm, stress = config.THRESHOLDS[key]
    return SignalResult(
        key=key, label=label, value=value,
        display=display if value is not None else "n/a",
        score=ramp(value, calm, stress),
        weight=weight, thresholds=(calm, stress),
    )


def _blend(signals: list[SignalResult]) -> Optional[float]:
    """Weighted mean of available signal scores; None if none are available."""
    usable = [s for s in signals if s.score is not None and s.weight > 0]
    if not usable:
        return None
    total_w = sum(s.weight for s in usable)
    if total_w == 0:
        return None
    return sum(s.score * s.weight for s in usable) / total_w


def _fmt(value: Optional[float], suffix: str = "", decimals: int = 2,
         signed: bool = False) -> str:
    if value is None:
        return "n/a"
    fmt = f"{{:+.{decimals}f}}" if signed else f"{{:.{decimals}f}}"
    return fmt.format(value) + suffix


# ---------------------------------------------------------------------------
# Component builders — one per block of the dashboard
# ---------------------------------------------------------------------------

def _carry_fx(m: Metrics) -> ComponentResult:
    sw = config.SUB_WEIGHTS["carry_fx"]
    signals = [
        _sig("usdjpy_1m_pct", "USDJPY 1-month change", m.usdjpy_1m,
             _fmt(m.usdjpy_1m, "%", 2, signed=True), sw["usdjpy_1m_pct"]),
        _sig("usdjpy_1w_pct", "USDJPY 1-week change", m.usdjpy_1w,
             _fmt(m.usdjpy_1w, "%", 2, signed=True), sw["usdjpy_1w_pct"]),
        _sig("carry_cross_drawdown_pct", "Worst carry cross vs 60d high",
             m.carry_cross_drawdown,
             _fmt(m.carry_cross_drawdown, "%", 2, signed=True),
             sw["carry_cross_drawdown_pct"]),
    ]
    return ComponentResult(
        key="carry_fx", label="Yen carry / FX stress",
        weight=config.WEIGHTS["carry_fx"], score=_blend(signals), signals=signals,
        note="A strengthening yen is the transmission channel: it forces "
             "leveraged carry positions to be closed, and those positions are "
             "funded into risk assets worldwide.",
    )


def _rate_diff(m: Metrics) -> ComponentResult:
    sw = config.SUB_WEIGHTS["rate_diff"]
    signals = [
        _sig("diff_2y_change_3m", "US-JP 2y differential, 3m change",
             m.diff_2y_change_3m, _fmt(m.diff_2y_change_3m, "pp", 2, signed=True),
             sw["diff_2y_change_3m"]),
        _sig("diff_2y_level", "US-JP 2y differential level", m.diff_2y,
             _fmt(m.diff_2y, "pp", 2), sw["diff_2y_level"]),
    ]
    return ComponentResult(
        key="rate_diff", label="Rate differentials",
        weight=config.WEIGHTS["rate_diff"], score=_blend(signals), signals=signals,
        note="A WIDE differential is the incentive to carry; a NARROWING one "
             "removes the reason to hold the position. Compression is what "
             "turns a crowded trade into an exit.",
    )


def _rate_vol(m: Metrics) -> ComponentResult:
    signals = [
        _sig("rate_vol_pctile", "Treasury vol percentile (3y)", m.rate_vol_pctile,
             _fmt(m.rate_vol_pctile, "th pctile", 0), 1.0),
    ]
    return ComponentResult(
        key="rate_vol", label="Treasury volatility",
        weight=config.WEIGHTS["rate_vol"], score=_blend(signals), signals=signals,
        note=f"Source: {m.rate_vol_source}. Scored as a percentile so the "
             "proxy and the real MOVE index are interchangeable.",
    )


def _curve(m: Metrics) -> ComponentResult:
    signals = [
        _sig("curve_steepening_3m", "10y-2y slope, 3m change", m.curve_change_3m,
             _fmt(m.curve_change_3m, "pp", 2, signed=True), 1.0),
    ]
    return ComponentResult(
        key="curve", label="Yield curve",
        weight=config.WEIGHTS["curve"], score=_blend(signals), signals=signals,
        note="Rapid bull-steepening (the front end falling as the market "
             "prices cuts) has historically been a better recession tell than "
             "the inversion itself.",
    )


def _equity_vol(m: Metrics) -> ComponentResult:
    sw = config.SUB_WEIGHTS["equity_vol"]
    signals = [
        _sig("vix_level", "VIX level", m.vix, _fmt(m.vix, "", 2), sw["vix_level"]),
        _sig("vix_term_structure", "VIX / VIX3M", m.vix_ratio,
             _fmt(m.vix_ratio, "", 3), sw["vix_term_structure"]),
    ]
    return ComponentResult(
        key="equity_vol", label="Equity volatility",
        weight=config.WEIGHTS["equity_vol"], score=_blend(signals), signals=signals,
        note="The term structure matters more than the level: VIX above VIX3M "
             "(backwardation) means the market is pricing acute near-term "
             "stress, not just a nervous background.",
    )


def _credit(m: Metrics) -> ComponentResult:
    sw = config.SUB_WEIGHTS["credit"]
    if m.credit_kind == "oas":
        signals = [
            _sig("hy_oas_change_1m", "HY spread, 1m change", m.hy_oas_change_1m,
                 _fmt(m.hy_oas_change_1m, "pp", 2, signed=True),
                 sw["hy_oas_change_1m"]),
            _sig("hy_oas_level", "HY spread level", m.hy_oas,
                 _fmt(m.hy_oas, "pp", 2), sw["hy_oas_level"]),
        ]
    else:
        # Fallback: relative performance of high-yield vs investment-grade.
        signals = [
            _sig("hyg_lqd_drawdown_pct", "HYG/LQD vs 6m high", m.hyg_lqd_drawdown,
                 _fmt(m.hyg_lqd_drawdown, "%", 2, signed=True), 1.0),
        ]
    return ComponentResult(
        key="credit", label="Credit spreads",
        weight=config.WEIGHTS["credit"], score=_blend(signals), signals=signals,
        note=f"Source: {m.credit_source}. Credit usually reprices risk before "
             "equities do, which is what makes it worth watching daily.",
    )


def _leverage(m: Metrics) -> ComponentResult:
    sw = config.SUB_WEIGHTS["leverage"]
    ms = m.margin
    usable = ms is not None and ms.usable

    # Placeholder or missing data scores NOTHING. The component is dropped and
    # the remaining weights are re-normalised — never scored as if it were calm.
    yoy = ms.yoy_pct if usable else None
    peak = ms.pct_of_peak if usable else None

    signals = [
        _sig("margin_debt_yoy", "Margin debt YoY", yoy,
             _fmt(yoy, "%", 1, signed=True), sw["margin_debt_yoy"]),
        _sig("margin_debt_vs_peak", "Margin debt vs record high", peak,
             _fmt(peak, "% of peak", 1), sw["margin_debt_vs_peak"]),
    ]

    if ms is None or ms.latest_debit_musd is None:
        note = "No margin debt data loaded — component excluded from the score."
    elif ms.is_placeholder:
        note = ("Margin data is flagged as PLACEHOLDER, so this component is "
                "excluded from the score. Enter real FINRA figures to enable it.")
    else:
        note = ("Leverage does not cause a selloff, but it sets how violent one "
                "becomes. Record margin debt still rising is the condition "
                "under which an ordinary 5% drop becomes a forced-selling 15%.")

    return ComponentResult(
        key="leverage", label="Leverage / margin debt",
        weight=config.WEIGHTS["leverage"], score=_blend(signals),
        signals=signals, note=note,
    )


def _commodity(m: Metrics) -> ComponentResult:
    sw = config.SUB_WEIGHTS["commodity"]
    # A move in EITHER direction is informative: a spike is a supply/inflation
    # shock, a collapse is a demand/growth shock. So the signal is the
    # ABSOLUTE size of the move.
    abs_move = abs(m.wti_1m) if m.wti_1m is not None else None
    signals = [
        _sig("oil_abs_move_1m", "WTI 1-month move (absolute)", abs_move,
             _fmt(abs_move, "%", 1), sw["oil_abs_move_1m"]),
        _sig("oil_vol_pctile", "WTI realised vol percentile (3y)",
             m.wti_vol_pctile, _fmt(m.wti_vol_pctile, "th pctile", 0),
             sw["oil_vol_pctile"]),
    ]
    return ComponentResult(
        key="commodity", label="Commodity / inflation shock",
        weight=config.WEIGHTS["commodity"], score=_blend(signals), signals=signals,
        note="Oil is scored on the SIZE of the move, not its direction: a "
             "spike is a supply shock, a collapse is a demand shock, and both "
             "constrain what central banks can do.",
    )


COMPONENT_BUILDERS = [
    _carry_fx, _rate_diff, _rate_vol, _curve,
    _equity_vol, _credit, _leverage, _commodity,
]


# ---------------------------------------------------------------------------
# Escalation rules
# ---------------------------------------------------------------------------

def _check_escalations(m: Metrics) -> list[tuple[str, float, str]]:
    """
    Pattern overrides. Each returns (rule_id, floor_score, description).

    These exist because a weighted average is bad at combinations. A wide rate
    differential is not stress. A falling USDJPY is not necessarily stress.
    Both together, moving fast, is the single most reliable systematic-risk
    setup in this dashboard — and averaging would bury it.
    """
    p = config.ESCALATION_PARAMS
    fired: list[tuple[str, float, str]] = []

    # 1. The yen carry unwind.
    if (m.usdjpy_1w is not None and m.diff_2y is not None
            and m.usdjpy_1w < p["carry_unwind_usdjpy_1w"]
            and m.diff_2y > p["carry_unwind_min_diff"]):
        floor, desc = config.ESCALATIONS["carry_unwind"]
        fired.append(("carry_unwind", floor, desc))

    # 2. Volatility term structure inverted.
    if m.vix_ratio is not None and m.vix_ratio > p["vol_backwardation_ratio"]:
        floor, desc = config.ESCALATIONS["vol_backwardation"]
        fired.append(("vol_backwardation", floor, desc))

    # 3. Credit repricing faster than equities.
    if (m.hy_oas_change_1m is not None
            and m.hy_oas_change_1m > p["credit_crack_oas_1m"]):
        floor, desc = config.ESCALATIONS["credit_crack"]
        fired.append(("credit_crack", floor, desc))

    # 4. Peak leverage meeting rising volatility. Real data only.
    ms = m.margin
    if (ms is not None and ms.usable and ms.pct_of_peak is not None
            and m.vix is not None
            and ms.pct_of_peak >= p["leverage_peak_proximity"]
            and m.vix > p["leverage_vix_trigger"]):
        floor, desc = config.ESCALATIONS["leverage_at_peak_and_vol_rising"]
        fired.append(("leverage_at_peak_and_vol_rising", floor, desc))

    return fired


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def assess(m: Metrics, weight_overrides: Optional[dict[str, float]] = None) -> RiskAssessment:
    """
    Run the full model.

    `weight_overrides` lets the sidebar sliders change component weights
    without touching config.py.
    """
    components = [build(m) for build in COMPONENT_BUILDERS]

    if weight_overrides:
        for c in components:
            if c.key in weight_overrides:
                c.weight = float(weight_overrides[c.key])

    available = [c for c in components if c.available and c.weight > 0]
    missing = [c.label for c in components if not c.available]

    total_weight = sum(c.weight for c in components if c.weight > 0)
    available_weight = sum(c.weight for c in available)

    if available_weight == 0:
        return RiskAssessment(
            composite=0.0, base_composite=0.0, regime="na",
            components=components, escalations=[], missing=missing,
            coverage_pct=0.0,
        )

    # Weighted average over AVAILABLE components only — a dead feed must not
    # drag the score toward zero.
    base = sum((c.score or 0.0) * c.weight for c in available) / available_weight * 100.0

    escalations = _check_escalations(m)
    composite = base
    for _, floor, _ in escalations:
        composite = max(composite, floor)

    coverage = (available_weight / total_weight * 100.0) if total_weight else 0.0

    return RiskAssessment(
        composite=round(composite, 1),
        base_composite=round(base, 1),
        regime=regime_from_composite(composite),
        components=components,
        escalations=escalations,
        missing=missing,
        coverage_pct=round(coverage, 0),
    )


def explain(a: RiskAssessment, m: Metrics) -> str:
    """
    Plain-English reason for the current regime. This is the text a tired
    person reads at 7am, so it leads with the conclusion.
    """
    if a.regime == "na":
        return "No data available — check your connection and hit Refresh."

    headline = {
        "low": "Conditions are calm. No systematic action indicated.",
        "elevated": "Conditions are deteriorating. Tighten risk, avoid adding leverage.",
        "high": "Systematic stress is elevated. Consider reducing equity exposure.",
    }[a.regime]

    parts = [f"**{headline}** Composite score {a.composite:.0f}/100."]

    if a.escalations:
        names = ", ".join(f"`{rid}`" for rid, _, _ in a.escalations)
        parts.append(
            f"The score was **floored by {len(a.escalations)} escalation rule(s)** "
            f"({names}) — the weighted average alone was {a.base_composite:.0f}."
        )

    drivers = [c for c in a.top_drivers if (c.score or 0) >= 0.34][:3]
    if drivers:
        driver_text = "; ".join(
            f"{c.label} ({c.level}, {(c.score or 0) * 100:.0f}/100)" for c in drivers
        )
        parts.append(f"Main contributors: {driver_text}.")
    else:
        parts.append("No individual component is above its 'calm' band.")

    if a.missing:
        parts.append(
            f"_Excluded for lack of data ({100 - a.coverage_pct:.0f}% of total weight): "
            f"{', '.join(a.missing)}._"
        )

    return "\n\n".join(parts)
