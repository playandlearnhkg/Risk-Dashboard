"""
cost_model.py — Realistic T+1 execution cost model.

A T+1 entry (trading the session after the Stage-2/pattern signal fires,
typically near the open or in the first few minutes) faces three cost
components, applied per side (entry AND exit):

  1. Half-spread   — half the quoted bid-ask spread, a direct cost of
                      crossing the spread with a marketable order.
  2. Market impact  — square-root model: impact_bps = K * sqrt(order_shares
                      / ADV_shares). Standard form for equity impact
                      estimation (Almgren et al.). K is a calibratable
                      constant; defaults below are deliberately conservative
                      (i.e. pessimistic) per the "prefer REJECT" mandate.
  3. Commission     — near-zero for US equities at retail/prop scale in the
                      current era; kept as an explicit, overridable knob
                      rather than assumed away.

Three named scenarios (LOW / BASE / HIGH) are provided for the cost
sensitivity test required in the standard battery — a strategy that only
survives under LOW costs is not fit for promotion.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CostScenario:
    name: str
    half_spread_bps: float
    impact_k: float          # sqrt-model coefficient, in bps
    commission_bps: float
    slippage_buffer_bps: float  # extra pad for T+1 open-auction/gap risk


SCENARIOS = {
    "low": CostScenario("low", half_spread_bps=2.0, impact_k=8.0,
                         commission_bps=0.2, slippage_buffer_bps=2.0),
    "base": CostScenario("base", half_spread_bps=5.0, impact_k=15.0,
                          commission_bps=0.5, slippage_buffer_bps=5.0),
    "high": CostScenario("high", half_spread_bps=10.0, impact_k=25.0,
                          commission_bps=1.0, slippage_buffer_bps=10.0),
}


def round_trip_cost_bps(
    order_shares: pd.Series | float,
    adv_shares: pd.Series | float,
    scenario: CostScenario = SCENARIOS["base"],
) -> pd.Series | float:
    """
    Total round-trip (entry + exit) cost in basis points of notional.
    Impact and spread are charged on both legs; commission and slippage
    buffer likewise apply per leg, doubled here for the round trip.
    """
    participation = np.asarray(order_shares) / np.asarray(adv_shares)
    impact_bps_per_leg = scenario.impact_k * np.sqrt(np.clip(participation, 0, None))
    per_leg = (
        scenario.half_spread_bps
        + impact_bps_per_leg
        + scenario.commission_bps
        + scenario.slippage_buffer_bps
    )
    total = 2 * per_leg
    if isinstance(order_shares, pd.Series):
        return pd.Series(total, index=order_shares.index)
    return float(total)


def apply_costs_to_returns(
    gross_return: pd.Series,
    order_shares: pd.Series,
    adv_shares: pd.Series,
    scenario: CostScenario = SCENARIOS["base"],
) -> pd.Series:
    """Net return = gross return - round-trip cost (in return space, not bps)."""
    cost_frac = round_trip_cost_bps(order_shares, adv_shares, scenario) / 10_000.0
    return gross_return - cost_frac


def cost_sensitivity_table(
    gross_returns: pd.Series,
    order_shares: pd.Series,
    adv_shares: pd.Series,
) -> pd.DataFrame:
    """One row per scenario: mean net return, win rate, and t-stat."""
    rows = []
    for scenario in SCENARIOS.values():
        net = apply_costs_to_returns(gross_returns, order_shares, adv_shares, scenario)
        n = net.dropna()
        t_stat = n.mean() / (n.std(ddof=1) / np.sqrt(len(n))) if len(n) > 1 else np.nan
        rows.append({
            "scenario": scenario.name,
            "mean_net_return": n.mean(),
            "win_rate": (n > 0).mean(),
            "t_stat": t_stat,
            "n": len(n),
        })
    return pd.DataFrame(rows)
