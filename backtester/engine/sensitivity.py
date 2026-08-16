"""
sensitivity.py -- is the result a plateau, or a single lucky point?

Every strategy in this project has parameters somebody chose. The
question this module answers is not "which value is best" -- that is the
question that creates overfitting -- but "does the answer survive being
slightly wrong about the value we picked".

THE TWO SHAPES THIS LOOKS FOR

  PLATEAU   the neighbours of the chosen value earn roughly what the
            chosen value earns. The parameter is doing something real
            and the exact number is not load-bearing.

  SPIKE     the chosen value earns much more than its own neighbours.
            That is what a fitted parameter looks like from the outside,
            and it is the single most common way a backtest flatters
            itself. It is reported as a ratio and it is a red flag, not
            a failure of arithmetic.

WHY EVERY VARIANT REGENERATES SIGNALS

`volume_ratio_min` and the doji threshold are SIGNAL filters: change them
and a different set of trades exists. Re-costing or re-slicing the
baseline trade log cannot see that, so each variant rebuilds the
strategy from the varied config and re-runs the whole path. That is slow
and it is the only correct option. `hold_minutes` is included in the
same loop even though it only moves the exit, because the strategy sets
`planned_exit_ts` from the config and rebuilding is how that reaches it.

THE RATIO GUARD, AGAIN

`spike_ratio` divides the baseline by the median of its neighbours. When
that median is at or below zero the ratio is meaningless -- a deepening
loss in the denominator produces a large positive number that reads like
good news. The ratio is NaN in that case and the neighbourhood being
unprofitable is reported on its own, which is the finding that matters.

WHAT THIS MODULE MUST NEVER DO

Pick the best cell and report it. It measures the neighbourhood of ONE
declared configuration. The moment it starts returning a better
configuration it has become the search process it exists to detect.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from engine.config import BacktestConfig, ConfigError
from engine.metrics import evaluate
from engine.portfolio import Portfolio, SelectionRule

# Relative steps applied either side of the configured value. "Slightly"
# is the whole point: +/-10% and +/-20% is a neighbourhood, not a search.
DEFAULT_STEPS: tuple[float, ...] = (-0.20, -0.10, 0.10, 0.20)

# (dotted config path, cast to int). Paths that a given strategy's config
# does not use are skipped with a reason rather than silently dropped.
DEFAULT_PARAMS: tuple[tuple[str, bool], ...] = (
    ("signal.volume_ratio_min", False),
    ("signal.doji_max_body_ratio", False),
    ("exit.hold_minutes", True),
)

COLUMNS = ["parameter", "value", "pct_change", "n_trades", "expectancy_bps",
           "profit_factor", "win_rate", "cagr", "sharpe", "max_dd"]


class SensitivityError(RuntimeError):
    """The sweep could not be run at all -- reported, never swallowed."""


@dataclass(frozen=True)
class SensitivityResult:
    table: pd.DataFrame              # one row per variant, baseline first
    by_parameter: pd.DataFrame       # one row per parameter swept
    base_expectancy_bps: float
    n_variants: int
    n_binding: int                   # variants that actually changed anything
    share_profitable: float          # of the VARIANTS, baseline excluded
    median_neighbour_bps: float
    spike_ratio: float               # base / median(neighbours), or NaN
    skipped: dict[str, str] = field(default_factory=dict)

    def summary(self) -> str:
        L = ["PARAMETER SENSITIVITY", "-" * 21]
        if not self.n_variants:
            L.append("  no parameters were varied")
            for p, why in self.skipped.items():
                L.append(f"    skipped {p}: {why}")
            return "\n".join(L)
        L += [
            f"  baseline expectancy       {self.base_expectancy_bps:,.2f} bps",
            f"  variants run              {self.n_variants}",
            f"  variants that changed it  {self.n_binding} "
            f"(the rest returned the baseline result unchanged)",
            f"  variants still profitable {self.share_profitable:.0%}",
            f"  neighbourhood median      {self.median_neighbour_bps:,.2f} bps",
            f"  spike ratio               "
            + ("n/a (neighbourhood median <= 0)" if not np.isfinite(self.spike_ratio)
               else f"{self.spike_ratio:,.2f}x"),
        ]
        for p, why in self.skipped.items():
            L.append(f"  skipped {p}: {why}")
        return "\n".join(L)


# --------------------------------------------------------------- the sweep

def _get(cfg: BacktestConfig, path: str):
    obj = cfg
    for part in path.split("."):
        obj = getattr(obj, part)
    return obj


def _neighbour_values(base, steps, as_int: bool) -> list:
    """Values either side of `base`, deduplicated, baseline removed.

    A base of zero has no relative neighbourhood -- every step returns
    zero -- so the caller skips that parameter rather than running four
    identical variants and calling the result stable.
    """
    out = []
    for s in steps:
        v = base * (1.0 + s)
        v = int(round(v)) if as_int else round(float(v), 8)
        if v != base and v > 0:
            out.append(v)
    return sorted(set(out))


def _measure(cfg: BacktestConfig, frames, eligible, build, selection,
             label: str) -> dict:
    strat = build(cfg)
    signals = strat.run_many_signals(frames, eligible=eligible)
    log, curve = Portfolio(cfg, selection).run(signals, frames)
    m = evaluate(log, cfg.portfolio.starting_capital, label, equity=curve)
    o = m.overall
    return {k: o.get(k) for k in
            ("n_trades", "expectancy_bps", "profit_factor", "win_rate",
             "cagr", "sharpe", "max_dd")}


def parameter_sensitivity(
        cfg: BacktestConfig,
        frames: dict[str, pd.DataFrame],
        eligible,
        build,
        selection: SelectionRule = SelectionRule.VOLUME_RATIO,
        params: tuple[tuple[str, bool], ...] = DEFAULT_PARAMS,
        steps: tuple[float, ...] = DEFAULT_STEPS,
) -> SensitivityResult:
    """Sweep a small neighbourhood around each declared parameter.

    `build(config) -> StrategyBase` rebuilds the strategy from a varied
    config. Without it a signal-filter parameter cannot be varied at all,
    so the caller supplies it and a failure to build is raised rather
    than reported as stability.
    """
    try:
        base_row = _measure(cfg, frames, eligible, build, selection, "baseline")
    except Exception as exc:  # noqa: BLE001
        raise SensitivityError(f"the baseline run failed: {exc}") from exc

    base_exp = float(base_row.get("expectancy_bps", np.nan))
    rows = [{"parameter": "(baseline)", "value": "", "pct_change": 0.0,
             **base_row}]
    skipped: dict[str, str] = {}
    per_param: list[dict] = []

    for path, as_int in params:
        try:
            base_v = _get(cfg, path)
        except AttributeError:
            skipped[path] = "not a field of this config"
            continue
        if not isinstance(base_v, (int, float)) or isinstance(base_v, bool):
            skipped[path] = f"not numeric (value {base_v!r})"
            continue
        if base_v == 0:
            skipped[path] = ("configured value is 0, so a relative step is a "
                             "no-op; this parameter is switched off")
            continue

        values = _neighbour_values(base_v, steps, as_int)
        if not values:
            skipped[path] = "every step rounded back to the configured value"
            continue

        got: list[dict] = []
        for v in values:
            try:
                variant = cfg.replace(**{path: v})
            except ConfigError as exc:
                skipped[path] = f"{v} rejected by the config: {exc}"
                continue
            try:
                r = _measure(variant, frames, eligible, build, selection,
                             f"{path}={v}")
            except Exception as exc:  # noqa: BLE001
                skipped[path] = f"{v} could not be run: {exc}"
                continue
            row = {"parameter": path, "value": v,
                   "pct_change": float(v / base_v - 1.0), **r}
            got.append(row)
            rows.append(row)

        if got:
            e = pd.Series([g["expectancy_bps"] for g in got], dtype=float)
            med = float(e.median())
            per_param.append({
                "parameter": path, "base_value": base_v, "n_variants": len(got),
                "min_expectancy_bps": float(e.min()),
                "median_expectancy_bps": med,
                "max_expectancy_bps": float(e.max()),
                "share_profitable": float((e > 0).mean()),
                "spike_ratio": _spike(base_exp, med),
            })

    table = pd.DataFrame(rows, columns=COLUMNS)
    variants = table[table["parameter"] != "(baseline)"]
    e = variants["expectancy_bps"].astype(float)
    med_all = float(e.median()) if len(e) else float("nan")

    # A variant that produced the identical trade count AND the identical
    # expectancy did not bind: the parameter never touched a decision on
    # this data. Counting those as evidence of stability would let a
    # strategy pass by having filters loose enough to be inert, which is
    # the opposite of the property being tested.
    base_n = base_row.get("n_trades")
    binding = 0
    for _, r in variants.iterrows():
        same_n = (r["n_trades"] == base_n)
        same_e = (np.isfinite(float(r["expectancy_bps"] or np.nan))
                  and np.isfinite(base_exp)
                  and abs(float(r["expectancy_bps"]) - base_exp) < 1e-9)
        if not (same_n and same_e):
            binding += 1

    return SensitivityResult(
        table=table,
        by_parameter=pd.DataFrame(per_param),
        base_expectancy_bps=base_exp,
        n_variants=int(len(variants)),
        n_binding=int(binding),
        share_profitable=float((e > 0).mean()) if len(e) else float("nan"),
        median_neighbour_bps=med_all,
        spike_ratio=_spike(base_exp, med_all),
        skipped=skipped,
    )


def _spike(base: float, neighbour_median: float) -> float:
    """base / median(neighbours), or NaN when the ratio would lie.

    A non-positive denominator makes the ratio unbounded and
    sign-flipped: a neighbourhood that LOSES money would produce a large
    negative -- or, with a negative baseline, a large positive that reads
    as a healthy margin. The caller reports the non-positive
    neighbourhood directly instead.
    """
    if not np.isfinite(base) or not np.isfinite(neighbour_median):
        return float("nan")
    if neighbour_median <= 0:
        return float("nan")
    return float(base / neighbour_median)
