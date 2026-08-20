"""
regime/composite.py — The Capital & Regime engine.
==================================================

Implements the governing model:

    Capital Availability = Money Available x Risk-on / Risk-off Behavior

Money and behaviour are scored independently (0-100 each) from their own
indicator blocks, then combined. The combination is MULTIPLICATIVE by design,
which is the substantive claim of the model and worth stating plainly:

    Money without appetite does not bid.  Appetite without money cannot bid.

A weighted average would let a strong reading on one side paper over a weak
reading on the other -- exactly the failure this model exists to prevent. The
default `geometric` method (sqrt of the product) keeps that multiplicative
behaviour while staying on a readable 0-100 scale and, importantly, penalising
imbalance: 90 money with 30 appetite scores 52, not 60.

Outputs
-------
  composite_score     0-100
  regime_label        Strong Risk-On .. Strong Risk-Off
  capital_status      High / Medium / Low  (from the MONEY half alone)
  factor_multipliers  regime-conditional weights for Layer 2
  coverage            share of indicator weight that actually had data
"""

from __future__ import annotations

import datetime as dt
import json
import math
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

from core.logging_setup import get_logger
from regime.indicators import (
    IndicatorReading,
    IndicatorSource,
    evaluate_block,
    weighted_score,
)

log = get_logger("regime.composite")

# Canonical ordering, risk-on to risk-off. Used for matrix lookups and for
# anywhere the label needs to become an index.
REGIME_KEYS = [
    "strong_risk_on",
    "mild_risk_on",
    "neutral",
    "mild_risk_off",
    "strong_risk_off",
]


@dataclass
class RegimeState:
    """The complete Layer 0 output for one run."""

    run_date: dt.date
    composite_score: float
    regime_key: str
    regime_label: str
    money_score: Optional[float]
    behavior_score: Optional[float]
    capital_status: str
    money_readings: list[IndicatorReading] = field(default_factory=list)
    behavior_readings: list[IndicatorReading] = field(default_factory=list)
    money_coverage: float = 0.0
    behavior_coverage: float = 0.0
    combination_method: str = "geometric"
    factor_multipliers: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    # -- derived -----------------------------------------------------------

    @property
    def coverage(self) -> float:
        """Overall share of indicator weight with live data."""
        return round((self.money_coverage + self.behavior_coverage) / 2, 3)

    @property
    def is_risk_on(self) -> bool:
        return self.regime_key in ("strong_risk_on", "mild_risk_on")

    @property
    def is_risk_off(self) -> bool:
        return self.regime_key in ("strong_risk_off", "mild_risk_off")

    def all_readings(self) -> list[IndicatorReading]:
        return list(self.money_readings) + list(self.behavior_readings)

    def unavailable(self) -> list[IndicatorReading]:
        return [r for r in self.all_readings() if not r.available]

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable form, for the DB and the frontend."""
        return {
            "run_date": self.run_date.isoformat(),
            "composite_score": self.composite_score,
            "regime_key": self.regime_key,
            "regime_label": self.regime_label,
            "money_score": self.money_score,
            "behavior_score": self.behavior_score,
            "capital_status": self.capital_status,
            "combination_method": self.combination_method,
            "coverage": self.coverage,
            "money_coverage": self.money_coverage,
            "behavior_coverage": self.behavior_coverage,
            "factor_multipliers": self.factor_multipliers,
            "warnings": self.warnings,
            "money_indicators": [
                {k: v for k, v in asdict(r).items() if k != "detail"} | {"detail": r.detail}
                for r in self.money_readings
            ],
            "behavior_indicators": [
                {k: v for k, v in asdict(r).items() if k != "detail"} | {"detail": r.detail}
                for r in self.behavior_readings
            ],
        }


# ---------------------------------------------------------------------------
# Combination
# ---------------------------------------------------------------------------

def combine(money: Optional[float], behavior: Optional[float],
            method: str, money_weight: float = 0.5,
            behavior_weight: float = 0.5) -> tuple[Optional[float], list[str]]:
    """
    Combine the two halves of the core model.

    Returns (composite, warnings). If exactly one half is available the other
    cannot be invented, so the available half is passed through with a loud
    warning -- the model's central claim is about the interaction, and a
    one-sided reading is a materially weaker statement.
    """
    warnings: list[str] = []

    if money is None and behavior is None:
        return None, ["Neither money nor behaviour could be scored."]

    if money is None or behavior is None:
        present = "behaviour" if money is None else "money"
        missing = "money" if money is None else "behaviour"
        warnings.append(
            f"Only the {present} half scored; {missing} had no usable data. "
            "The composite is NOT a true capital-availability reading."
        )
        return (behavior if money is None else money), warnings

    if method == "product":
        composite = (money / 100.0) * (behavior / 100.0) * 100.0
    elif method == "weighted":
        total = money_weight + behavior_weight
        composite = (money * money_weight + behavior * behavior_weight) / total
        warnings.append(
            "combination_method is 'weighted': the composite is additive, so a "
            "strong half can mask a weak one. This departs from the core model."
        )
    else:                                    # geometric, the default
        composite = math.sqrt(max(0.0, money) * max(0.0, behavior))

    return round(float(composite), 1), warnings


def label_for_score(score: float, labels_cfg: dict) -> tuple[str, str]:
    """Map a composite score to (regime_key, human label)."""
    for key in REGIME_KEYS:
        band = labels_cfg.get(key)
        if not band:
            continue
        if float(band["min"]) <= score < float(band["max"]):
            return key, band.get("name", key)
    # Defensive: bands should cover the range, but never crash on a gap.
    return "neutral", labels_cfg.get("neutral", {}).get("name", "Neutral")


def capital_status_for(money_score: Optional[float], cfg: dict) -> str:
    """
    Capital availability from the MONEY half only.

    Deliberately not from the composite: the system should be able to report
    "money is abundant but appetite is absent", which is the setup that
    precedes violent recoveries. Folding behaviour in here would erase that.
    """
    if money_score is None:
        return "Unknown"
    if money_score >= float(cfg.get("high_above", 62)):
        return "High"
    if money_score >= float(cfg.get("medium_above", 38)):
        return "Medium"
    return "Low"


def factor_multipliers_for(regime_key: str, cfg: dict) -> dict[str, float]:
    """Layer 2 factor-weight multipliers for the current regime."""
    table = (cfg or {}).get(regime_key)
    if not table:
        table = (cfg or {}).get("neutral", {})
    return {k: float(v) for k, v in table.items()}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def compute_regime(cfg, source: Optional[IndicatorSource] = None) -> RegimeState:
    """Run the full Layer 0 assessment."""
    src = source or IndicatorSource(cfg)
    regime_cfg = cfg.require("regime")

    log.info("Scoring money-availability indicators…")
    money_readings = evaluate_block(regime_cfg["money"], src)
    money_score, money_cov = weighted_score(money_readings)

    log.info("Scoring risk-on/risk-off indicators…")
    behavior_readings = evaluate_block(regime_cfg["behavior"], src)
    behavior_score, behavior_cov = weighted_score(behavior_readings)

    method = regime_cfg.get("combination_method", "geometric")
    composite, warnings = combine(
        money_score, behavior_score, method,
        float(regime_cfg.get("money_weight", 0.5)),
        float(regime_cfg.get("behavior_weight", 0.5)),
    )

    if composite is None:
        composite = 50.0
        warnings.append("No indicators scored; defaulting to Neutral 50.")

    regime_key, regime_label = label_for_score(composite, regime_cfg["labels"])
    capital_status = capital_status_for(money_score, regime_cfg.get("capital_status", {}))
    multipliers = factor_multipliers_for(regime_key, regime_cfg.get("factor_multipliers", {}))

    # Surface degraded coverage rather than quietly reporting a confident
    # number built on two working feeds.
    for name, cov in (("money", money_cov), ("behaviour", behavior_cov)):
        if 0 < cov < 0.6:
            warnings.append(
                f"Only {cov:.0%} of {name} indicator weight had data — "
                "treat this score as provisional."
            )

    state = RegimeState(
        run_date=dt.date.today(),
        composite_score=composite,
        regime_key=regime_key,
        regime_label=regime_label,
        money_score=money_score,
        behavior_score=behavior_score,
        capital_status=capital_status,
        money_readings=money_readings,
        behavior_readings=behavior_readings,
        money_coverage=money_cov,
        behavior_coverage=behavior_cov,
        combination_method=method,
        factor_multipliers=multipliers,
        warnings=warnings,
    )

    log.info("Regime: %s (%.1f) · capital %s · coverage %.0f%%",
             regime_label, composite, capital_status, state.coverage * 100)
    return state


def persist(state: RegimeState, db) -> None:
    """Append this run to regime_history (one row per day, replaced on rerun)."""
    db.upsert_many(
        "regime_history",
        ["run_date", "composite_score", "regime_label", "money_score",
         "behavior_score", "capital_status", "detail_json", "created_at"],
        [(
            state.run_date.isoformat(),
            state.composite_score,
            state.regime_label,
            state.money_score,
            state.behavior_score,
            state.capital_status,
            json.dumps(state.to_dict(), default=str),
            dt.datetime.now().isoformat(timespec="seconds"),
        )],
    )


def history(db, days: int = 180) -> list[dict[str, Any]]:
    """Recent regime history, newest last — for trend display in Layer 7."""
    cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    rows = db.query(
        "SELECT run_date, composite_score, regime_label, money_score, "
        "behavior_score, capital_status FROM regime_history "
        "WHERE run_date >= ? ORDER BY run_date", (cutoff,),
    )
    return [dict(r) for r in rows]
