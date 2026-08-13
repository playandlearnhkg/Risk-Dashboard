"""
robustness.py -- does the result survive changing the assumptions?

Every test here answers the same question in a different direction: how
much of the headline number is the strategy, and how much is a choice
somebody made while measuring it.

THE ONE DESIGN DECISION THAT MATTERS

Each variant RE-RUNS THE PORTFOLIO rather than re-costing the existing
trade log. That is slower and it is the only correct option, because
capital compounds: a different cost, position limit or stop changes
equity, and fixed-fractional sizing reads equity to size the next trade.
Re-pricing a fixed trade log would hold sizing at the baseline path and
quietly understate how much the variants differ. `metrics.reprice` exists
for fast sweeps and says the same thing about itself.

Signals are generated ONCE and reused. That is safe and deliberate:
none of these knobs touches signal generation, so regenerating would
burn time to produce identical Signal objects. The stop test is the
exception worth stating -- it changes the exit, not the entry, so the
same signals are correct there too, and a test asserts the two variants
see the same trade count.

WHAT WOULD MAKE THESE NUMBERS LIES

Nothing here re-optimises anything. No parameter is chosen by looking at
the output. If a future version starts picking the best cell of a grid
and reporting it, these tables stop being robustness checks and become
an overfitting engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from engine.config import BacktestConfig
from engine.metrics import Metrics, evaluate
from engine.portfolio import Portfolio, SelectionRule
from engine.strategy_base import Signal

DEFAULT_COSTS = [6.6, 10.0, 15.0, 25.0, 35.0]
DEFAULT_LIMITS = [3, 5, 8]
DEFAULT_PERIODS = [
    ("Full sample", None, None),
    ("2015-2019", "2015-01-01", "2019-12-31"),
    ("2020-2021", "2020-01-01", "2021-12-31"),
    ("2022-2025", "2022-01-01", "2025-12-31"),
]

HEADLINE = ["cagr", "ann_vol", "sharpe", "max_dd", "calmar", "n_trades",
            "win_rate", "expectancy_bps", "profit_factor"]


@dataclass(frozen=True)
class Case:
    """One variant: a label, the config that produced it, its metrics."""
    label: str
    config: BacktestConfig
    metrics: Metrics

    def row(self, **extra) -> dict:
        o = self.metrics.overall
        return {"case": self.label, **{k: o.get(k) for k in HEADLINE}, **extra}


def _run(cfg: BacktestConfig, signals: list[Signal],
         frames: dict[str, pd.DataFrame], label: str,
         selection: SelectionRule = SelectionRule.VOLUME_RATIO,
         start=None, end=None) -> Case:
    log, curve = Portfolio(cfg, selection).run(signals, frames)
    m = evaluate(log, cfg.portfolio.starting_capital, label,
                 equity=curve, start=start, end=end)
    return Case(label=label, config=cfg, metrics=m)


# --------------------------------------------------------------- the tests

def cost_stress(cfg, signals, frames, costs=None) -> pd.DataFrame:
    """Re-run at each cost level. Full re-run, not a re-price."""
    rows = []
    for c in (costs or DEFAULT_COSTS):
        case = _run(cfg.replace(**{"costs.round_trip_bps": float(c)}),
                    signals, frames, f"{c:g} bps")
        rows.append(case.row(cost_bps=c))
    return pd.DataFrame(rows)


def period_stability(cfg, signals, frames, periods=None) -> pd.DataFrame:
    """Same run, sliced by period, each annualised over its OWN window.

    The slice happens in `metrics.evaluate`, which rebuilds equity from
    the filtered trades. Annualising a 2022-2025 subset over the full
    eleven years would charge it for years it did not trade.
    """
    rows = []
    for label, a, b in (periods or DEFAULT_PERIODS):
        case = _run(cfg, signals, frames, label, start=a, end=b)
        rows.append(case.row(start=a or "", end=b or ""))
    return pd.DataFrame(rows)


def long_short(cfg, signals, frames) -> pd.DataFrame:
    """Long-only and short-only as SEPARATE BOOKS, plus the combined split.

    Two different questions, both reported. Filtering the signal list
    gives a real long-only portfolio -- fewer trades, different
    compounding, its own drawdown. Splitting the combined trade log by
    side instead shows each side's contribution WITHIN the joint book,
    where they shared capital and slots. The two do not reconcile, and
    should not.
    """
    combined = _run(cfg, signals, frames, "Combined")
    rows = [combined.row(book="combined", pct_of_total_pnl=1.0)]

    for side, keep in (("LONG", 1), ("SHORT", -1)):
        subset = [s for s in signals if s.direction == keep]
        if not subset:
            continue
        case = _run(cfg, subset, frames, f"{side} only")
        rows.append(case.row(book="standalone", pct_of_total_pnl=np.nan))

    out = pd.DataFrame(rows)
    within = combined.metrics.by_side
    if len(within):
        for _, r in within.iterrows():
            out.loc[len(out)] = {
                "case": f"{r['side']} within combined", "book": "within",
                "n_trades": r["n_trades"], "win_rate": r["win_rate"],
                "expectancy_bps": r["expectancy_bps"],
                "profit_factor": r["profit_factor"],
                "pct_of_total_pnl": r["pct_of_total_pnl"],
            }
    return out


def position_limits(cfg, signals, frames, limits=None) -> pd.DataFrame:
    """How much does the concurrency cap cost, and what does it change?"""
    rows = []
    n_signals = len(signals)
    for k in (limits or DEFAULT_LIMITS):
        c = cfg.replace(**{"portfolio.max_concurrent_positions": int(k)})
        case = _run(c, signals, frames, f"max {k}")
        t = case.metrics.trades
        rows.append(case.row(
            max_positions=k,
            pct_signals_taken=len(t) / n_signals if n_signals else np.nan,
            avg_gross=float(t["weight"].groupby(t["date"]).sum().mean())
            if len(t) else np.nan,
            pct_days_capped=float(t.groupby("date").size().ge(k).mean())
            if len(t) else np.nan))
    return pd.DataFrame(rows)


def stop_comparison(cfg, signals, frames, multiples=(1.0,)) -> pd.DataFrame:
    """No stop against ATR stops, under identical capital rules.

    Also reports the whipsaw split, which is the number that explains
    the headline: of the trades a stop fires on, how many would have
    ended BETTER without it.
    """
    rows = []
    base = _run(cfg.replace(**{"exit.stop.enabled": False}), signals, frames,
                "No stop")
    rows.append(base.row(stop="none", stop_rate=0.0, pct_stops_harmful=np.nan))
    ref = base.metrics.trades.set_index("trade_id")["pnl_bps"]

    for mult in multiples:
        c = cfg.replace(**{"exit.stop.enabled": True,
                           "exit.stop.multiple": float(mult)})
        case = _run(c, signals, frames, f"ATR -{mult:g} stop")
        t = case.metrics.trades
        stopped = t[t["exit_reason"] == "stop"] if "exit_reason" in t else t.iloc[:0]
        harmful = np.nan
        if len(stopped):
            same = ref.reindex(stopped["trade_id"]).to_numpy()
            harmful = float(np.nanmean(stopped["pnl_bps"].to_numpy() < same))
        rows.append(case.row(
            stop=f"{mult:g} ATR",
            stop_rate=float(len(stopped) / len(t)) if len(t) else np.nan,
            pct_stops_harmful=harmful))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------- suite

def run_suite(cfg: BacktestConfig, signals: list[Signal],
              frames: dict[str, pd.DataFrame],
              costs=None, limits=None, periods=None,
              stop_multiples=(1.0,)) -> dict[str, pd.DataFrame]:
    return {
        "cost_stress": cost_stress(cfg, signals, frames, costs),
        "period_stability": period_stability(cfg, signals, frames, periods),
        "long_short": long_short(cfg, signals, frames),
        "position_limits": position_limits(cfg, signals, frames, limits),
        "stop_comparison": stop_comparison(cfg, signals, frames, stop_multiples),
    }


def dashboard(tables: dict[str, pd.DataFrame], cfg: BacktestConfig) -> str:
    """One page. Tables, then the flags that would concern a reviewer."""
    L = ["=" * 78,
         f"ROBUSTNESS SUITE  --  {cfg.strategy.name} v{cfg.strategy.version}",
         "=" * 78, ""]
    titles = {
        "cost_stress": "1. COST STRESS  (full re-run at each level)",
        "period_stability": "2. PERIOD STABILITY  (each annualised over its own window)",
        "long_short": "3. LONG vs SHORT",
        "position_limits": "4. POSITION LIMIT SENSITIVITY",
        "stop_comparison": "5. STOP vs NO STOP",
    }
    for key, title in titles.items():
        t = tables.get(key)
        if t is None or t.empty:
            continue
        L += [title, "-" * len(title), _fmt(t), ""]
    L += ["", "FLAGS", "-" * 5, *_flags(tables)]
    return "\n".join(L)


def _fmt(df: pd.DataFrame) -> str:
    x = df.copy()
    for c in x.columns:
        if pd.api.types.is_float_dtype(x[c]):
            x[c] = x[c].map(lambda v: "" if pd.isna(v) else f"{v:,.4f}")
    return x.to_string(index=False)


def _flags(tables: dict[str, pd.DataFrame]) -> list[str]:
    """Mechanical checks. Each states the threshold it applied."""
    out: list[str] = []

    cs = tables.get("cost_stress")
    if cs is not None and len(cs):
        alive = cs[cs["cagr"] > 0]
        dead = cs[cs["cagr"] <= 0]
        if len(dead):
            out.append(f"  COST      dies at {dead.iloc[0]['cost_bps']:g} bps "
                       f"round trip. Headroom over the 6.6 bps assumption is "
                       f"{dead.iloc[0]['cost_bps'] / 6.6:.1f}x.")
        elif len(alive):
            out.append(f"  COST      still positive at the highest level "
                       f"tested ({cs['cost_bps'].max():g} bps).")

    ps = tables.get("period_stability")
    if ps is not None and len(ps) > 1:
        sub = ps[ps["case"] != "Full sample"]
        if len(sub):
            best, worst = sub["cagr"].max(), sub["cagr"].min()
            out.append(f"  PERIODS   CAGR ranges {worst * 100:,.1f}% to "
                       f"{best * 100:,.1f}% across sub-periods.")
            if worst <= 0:
                out.append("            CONCERN: at least one sub-period is "
                           "negative. A single strong regime may carry the "
                           "full-sample result.")
            elif best > 0 and worst < best / 3:
                out.append("            CONCERN: the weakest sub-period is "
                           "under a third of the strongest. Size off the "
                           "weak one, not the average.")

    ls = tables.get("long_short")
    if ls is not None and "book" in ls:
        st = ls[ls["book"] == "standalone"]
        if len(st) == 2 and (st["expectancy_bps"] <= 0).any():
            bad = st[st["expectancy_bps"] <= 0].iloc[0]["case"]
            out.append(f"  SIDES     CONCERN: {bad} has non-positive "
                       f"expectancy standalone. The combined result depends "
                       f"on one leg.")

    pl = tables.get("position_limits")
    if pl is not None and len(pl) > 1:
        spread = pl["cagr"].max() - pl["cagr"].min()
        out.append(f"  LIMITS    CAGR spread across limits "
                   f"{spread * 100:,.1f} pp.")
        if (pl["pct_signals_taken"] < 0.7).any():
            k = pl[pl["pct_signals_taken"] < 0.7].iloc[0]
            out.append(f"            at max {k['max_positions']:g} only "
                       f"{k['pct_signals_taken'] * 100:.0f}% of signals are "
                       f"taken; the cap is binding, not decorative.")

    sc = tables.get("stop_comparison")
    if sc is not None and len(sc) > 1:
        nostop = sc[sc["stop"] == "none"].iloc[0]
        for _, r in sc[sc["stop"] != "none"].iterrows():
            better = r["cagr"] > nostop["cagr"]
            out.append(f"  STOP      {r['stop']}: CAGR "
                       f"{r['cagr'] * 100:,.1f}% vs {nostop['cagr'] * 100:,.1f}% "
                       f"unstopped, max DD {r['max_dd'] * 100:,.1f}% vs "
                       f"{nostop['max_dd'] * 100:,.1f}% "
                       f"({'stop helps' if better else 'stop costs return'}).")
            if pd.notna(r.get("pct_stops_harmful")) and r["pct_stops_harmful"] > 0.5:
                out.append(f"            CONCERN: {r['pct_stops_harmful'] * 100:.0f}% "
                           f"of stopped trades would have ended better "
                           f"unstopped. That is whipsaw, not protection.")

    return out or ["  (no flags raised)"]


def write(tables: dict[str, pd.DataFrame], out_dir: Path | str,
          text: str | None = None) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, t in tables.items():
        p = out_dir / f"robustness_{name}.csv"
        t.to_csv(p, index=False)
        paths.append(p)
    if text is not None:
        p = out_dir / "robustness_dashboard.txt"
        p.write_text(text)
        paths.append(p)
    return paths
