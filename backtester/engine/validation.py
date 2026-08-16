"""
validation.py -- one standardised report for any strategy config.

This module ORCHESTRATES; it computes almost nothing itself. Every
number comes from `metrics.evaluate`, and the cost sweep re-runs the
Portfolio through the same path the robustness suite uses. That is
deliberate: a validation report that recomputed its own Sharpe would
eventually disagree with the robustness suite's Sharpe, and nobody would
know which was right.

WHAT IT ASSEMBLES, AND WHY EACH PIECE IS THERE

  BOTH STOP VARIANTS SIDE BY SIDE. The stop is not a detail. In the
  research it lowered CAGR and made max drawdown slightly WORSE, and
  more than half the trades it fired on would have ended better without
  it. A report showing only one variant invites the reader to assume the
  other is similar.

  THE 2022-2025 SLICE AS A FIRST-CLASS SECTION, not an optional flag.
  The full-sample number is the one people quote and the recent number
  is the one they will actually trade. Both are printed, and the slice
  is annualised over its OWN window -- see metrics.filter_period.

  A COST SWEEP, because the edge dying at a plausible spread is the
  single most likely way this stops being a business.

  PLOTS, because a drawdown table hides the shape of the drawdown. They
  are matplotlib PNGs written to disk, not shown, so the module stays
  usable headless.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from engine.config import BacktestConfig
from engine.metrics import Metrics, evaluate
from engine.portfolio import Portfolio, SelectionRule

DEFAULT_COSTS = [6.6, 10.0, 15.0, 25.0]
STRESS_PERIOD = ("2022-2025", "2022-01-01", "2025-12-31")

VARIANTS = [("no_stop", "No stop", False, 1.0),
            ("atr_1_0", "ATR -1.0 stop", True, 1.0)]


@dataclass
class ValidationReport:
    config: BacktestConfig
    variants: dict[str, Metrics]
    stress: dict[str, Metrics]
    costs: pd.DataFrame
    plots: list[Path] = field(default_factory=list)

    # -- assembly -----------------------------------------------------

    def summary(self) -> str:
        c = self.config
        L = ["=" * 78,
             f"FULL VALIDATION  --  {c.strategy.name} v{c.strategy.version}",
             "=" * 78,
             f"capital {c.portfolio.starting_capital:,.0f}   "
             f"cost {c.costs.round_trip_bps} bps   "
             f"max {c.portfolio.max_concurrent_positions} concurrent   "
             f"risk {c.sizing.risk_pct:.2%}", ""]

        for key, m in self.variants.items():
            L += [m.summary(), ""]

        L += ["", "=" * 78, "STRESS PERIOD  " + STRESS_PERIOD[0],
              "=" * 78,
              "annualised over its OWN window, not the full sample", ""]
        if any(len(m.trades) for m in self.stress.values()):
            L += [_fmt(self.side_by_side(self.stress)), ""]
        else:
            L += ["  no trades in this window", ""]

        L += ["", "=" * 78, "COST SENSITIVITY", "=" * 78,
              "full re-run at each level, not a re-priced trade log", "",
              _fmt(self.costs), ""]

        L += ["", "=" * 78, "FULL SAMPLE, SIDE BY SIDE", "=" * 78, "",
              _fmt(self.side_by_side(self.variants)), ""]

        if self.plots:
            L += ["", "PLOTS", "-" * 5]
            L += [f"  {p}" for p in self.plots]
        return "\n".join(L)

    def side_by_side(self, group: dict[str, Metrics]) -> pd.DataFrame:
        keys = ["total_return", "cagr", "ann_vol", "sharpe", "max_dd",
                "calmar", "n_trades", "win_rate", "expectancy_bps",
                "expectancy_atr", "payoff_ratio", "profit_factor"]
        dkeys = ["median_bps", "p10", "p90", "skew_wins", "exkurt_wins",
                 "pct_loss_gt_1atr", "pct_gain_gt_1atr", "mean_mae_atr",
                 "mean_mfe_atr"]
        rows = []
        for label, m in group.items():
            rows.append({"variant": label,
                         **{k: m.overall.get(k) for k in keys},
                         **{k: m.distribution.get(k) for k in dkeys}})
        return pd.DataFrame(rows)

    def write(self, out_dir: Path | str) -> list[Path]:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        paths = []
        for key, m in self.variants.items():
            paths += m.write(out, prefix=f"validation_{key}_")
        for key, m in self.stress.items():
            if len(m.trades):
                paths += m.write(out, prefix=f"validation_stress_{key}_")
        p = out / "validation_costs.csv"
        self.costs.to_csv(p, index=False)
        paths.append(p)
        p = out / "validation_side_by_side.csv"
        self.side_by_side(self.variants).to_csv(p, index=False)
        paths.append(p)
        p = out / "validation_summary.txt"
        p.write_text(self.summary())
        paths.append(p)
        return paths + self.plots


# ------------------------------------------------------------------- runner

def _run_variant(cfg: BacktestConfig, signals, frames, stop: bool,
                 mult: float, label: str, selection, start=None, end=None):
    c = cfg.replace(**{"exit.stop.enabled": stop, "exit.stop.multiple": mult})
    log, curve = Portfolio(c, selection).run(signals, frames)
    return evaluate(log, c.portfolio.starting_capital, label,
                    equity=curve, start=start, end=end)


def run(cfg: BacktestConfig, signals, frames,
        costs=None, selection=SelectionRule.VOLUME_RATIO,
        out_dir: Path | str | None = None,
        make_plots: bool = True) -> ValidationReport:
    variants, stress = {}, {}
    for key, label, stop, mult in VARIANTS:
        variants[label] = _run_variant(cfg, signals, frames, stop, mult,
                                       label, selection)
        stress[label] = _run_variant(cfg, signals, frames, stop, mult,
                                     f"{label} ({STRESS_PERIOD[0]})", selection,
                                     start=STRESS_PERIOD[1], end=STRESS_PERIOD[2])

    rows = []
    for bps in (costs or DEFAULT_COSTS):
        cc = cfg.replace(**{"costs.round_trip_bps": float(bps)})
        for key, label, stop, mult in VARIANTS:
            m = _run_variant(cc, signals, frames, stop, mult, label, selection)
            o = m.overall
            rows.append({"cost_bps": bps, "variant": label,
                         "cagr": o.get("cagr"), "sharpe": o.get("sharpe"),
                         "max_dd": o.get("max_dd"), "calmar": o.get("calmar"),
                         "win_rate": o.get("win_rate"),
                         "expectancy_bps": o.get("expectancy_bps"),
                         "profit_factor": o.get("profit_factor")})
    rep = ValidationReport(cfg, variants, stress, pd.DataFrame(rows))

    if make_plots and out_dir is not None:
        rep.plots = _plot(rep, Path(out_dir))
    return rep


def _plot(rep: ValidationReport, out_dir: Path) -> list[Path]:
    """Equity on a log axis with drawdown beneath, both variants together."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []                     # plotting is optional, not required

    live = {k: m for k, m in rep.variants.items() if len(m.equity) > 1}
    if not live:
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(2, 1, figsize=(11, 7), sharex=True,
                           gridspec_kw={"height_ratios": [2, 1]})
    colours = ["#1f4e79", "#c0504d", "#2e7d32"]
    for (label, m), col in zip(live.items(), colours):
        o = m.overall
        ax[0].plot(m.equity.index, m.equity, lw=1.3, color=col,
                   label=f"{label} -- {m.equity.iloc[-1]:,.0f}, "
                         f"CAGR {o.get('cagr', float('nan')) * 100:.1f}%, "
                         f"DD {o.get('max_dd', float('nan')) * 100:.1f}%")
        ax[1].fill_between(m.drawdown.index, m.drawdown * 100, 0,
                           alpha=0.35, color=col, lw=0)
    ax[0].axhline(rep.config.portfolio.starting_capital, color="grey",
                  lw=0.8, ls="--")
    if (min(m.equity.min() for m in live.values()) > 0):
        ax[0].set_yscale("log")
    ax[0].set_ylabel("Equity")
    ax[0].set_title(f"{rep.config.strategy.name} -- "
                    f"{rep.config.costs.round_trip_bps} bps")
    ax[0].legend(loc="upper left", fontsize=9, frameon=False)
    ax[0].grid(alpha=0.25)
    ax[1].set_ylabel("Drawdown (%)")
    ax[1].grid(alpha=0.25)
    fig.tight_layout()
    p1 = out_dir / "validation_equity.png"
    fig.savefig(p1, dpi=130)
    plt.close(fig)

    # Trade-return histogram, winsorised so one outlier cannot flatten it.
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for (label, m), col in zip(live.items(), colours):
        b = m.trades["pnl_bps"]
        if len(b) < 2:
            continue
        lo, hi = b.quantile([0.01, 0.99])
        ax.hist(b.clip(lo, hi), bins=40, alpha=0.5, label=label, color=col)
    ax.axvline(0, color="grey", lw=0.8)
    ax.set_xlabel("trade return (bps, winsorised 1/99)")
    ax.set_ylabel("trades")
    ax.legend(frameon=False)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    p2 = out_dir / "validation_distribution.png"
    fig.savefig(p2, dpi=130)
    plt.close(fig)
    return [p1, p2]


def _fmt(df: pd.DataFrame) -> str:
    x = df.copy()
    for c in x.columns:
        if pd.api.types.is_float_dtype(x[c]):
            x[c] = x[c].map(lambda v: "" if pd.isna(v) else f"{v:,.4f}")
    return x.to_string(index=False)
