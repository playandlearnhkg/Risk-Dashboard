"""
benchmarks.py -- compared with what?

A strategy that earns 12% a year is impressive or embarrassing depending
entirely on what the obvious alternative earned over the same window. So
two alternatives are priced here, and both are deliberately unflattering
to the strategy:

  1 BUY AND HOLD THE INDEX over exactly the strategy's own window. Not a
    remembered long-run average -- the actual index over the actual
    sessions traded, so a strategy that ran through a bull market is
    measured against that bull market.

  2 THE SAME SIGNALS, HELD LONGER. This is the sharper test of the two.
    If holding the identical names for two or four times as long earns
    more, then the exit is the edge and the entry filter is decoration --
    or, worse, the hold length was chosen by looking at the answer.

THE COMPARISON THAT IS NOT FAIR, AND IS REPORTED ANYWAY

An intraday strategy holding positions 7% of the clock has almost no
volatility on the other 93% of days. Its Sharpe is therefore flattered
against an index that is exposed every single day, and the flattery is
large -- in this project's own research the headline Sharpe was 2.82
while volatility on days capital was actually working was 22.4%, not
6.7%. So `pct_days_active` and `deployed_vol` sit in the same table as
`sharpe`, and any read of the Sharpe column that ignores them is wrong.
Both are reported; neither is silently adjusted, because there is no
single defensible adjustment and inventing one would hide the problem
rather than show it.

WHY LONGER HOLDS STAY INSIDE THE SESSION

`planned_exit_ts` is wall-clock. A hold that runs past the close lands
in a gap with no bars, and the portfolio would correctly record a stale
exit for every trade -- a table full of `time_stale` that says nothing
about holding longer. Multiples are therefore capped at the session
close, and a multiple that would exceed it is reported at the cap rather
than dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from engine.calendar import SESSION_CLOSE, session_date
from engine.config import BacktestConfig, ConfigError
from engine.metrics import Metrics, equity_stats, evaluate
from engine.portfolio import Portfolio, SelectionRule

DEFAULT_MULTIPLES: tuple[float, ...] = (2.0, 4.0)
MAX_SESSION_MINUTES = 390

COLUMNS = ["benchmark", "kind", "detail", "total_return", "cagr", "ann_vol",
           "sharpe", "max_dd", "calmar", "n_trades", "expectancy_bps",
           "pct_days_active", "deployed_vol", "sharpe_diff", "max_dd_diff",
           "return_diff"]


@dataclass(frozen=True)
class BenchmarkResult:
    table: pd.DataFrame
    strategy: dict                    # the row every diff is measured against
    index_available: bool
    index_ticker: str
    notes: list[str] = field(default_factory=list)

    def worst_sharpe_margin(self, kind: str) -> float:
        """Strategy Sharpe minus the BEST competitor of that kind.

        The best competitor, not the average: a strategy is only clearly
        better than an alternative if it beats the strongest version of
        it that was tested.
        """
        rows = self.table[self.table["kind"] == kind]
        if not len(rows):
            return float("nan")
        best = rows["sharpe"].astype(float).max()
        if not np.isfinite(best):
            return float("nan")
        return float(self.strategy.get("sharpe", np.nan) - best)

    def summary(self) -> str:
        L = ["BENCHMARKS", "-" * 10]
        if not self.index_available:
            L.append(f"  {self.index_ticker}: NOT SUPPLIED -- no buy-and-hold "
                     f"comparison was made")
        show = self.table[["benchmark", "cagr", "ann_vol", "sharpe", "max_dd",
                           "sharpe_diff", "max_dd_diff", "return_diff"]]
        L.append(_fmt(show))
        for n in self.notes:
            L.append(f"  note: {n}")
        return "\n".join(L)


# ------------------------------------------------------------ buy and hold

def session_closes(bars: pd.DataFrame) -> pd.Series:
    """Last regular-session close per session date, indexed by date."""
    if bars.empty:
        return pd.Series(dtype=float)
    d = session_date(bars.index).to_numpy()
    s = bars["close"].groupby(d).last()
    s.index = pd.DatetimeIndex(s.index, name="date")
    return s.astype(float)


def buy_and_hold(bars: pd.DataFrame, capital: float,
                 index: pd.DatetimeIndex) -> pd.Series:
    """Equity from holding one name across the strategy's own sessions.

    The curve is normalised to `capital` on the FIRST session of the
    strategy's window, so both curves start at the same number on the
    same day and are annualised over the same count of observations. The
    benchmark's move on that first day is therefore excluded -- one day
    out of the sample, and the alternative (starting a day earlier) would
    give the benchmark an observation the strategy does not have.
    """
    px = session_closes(bars)
    if px.empty or index is None or not len(index):
        return pd.Series(dtype=float)
    idx = pd.DatetimeIndex(index)
    # Forward-fill across sessions the benchmark did not print, then
    # back-fill only the leading edge. A halted or late-listed benchmark
    # is flat rather than missing, and never interpolated backwards
    # through the middle of the sample.
    joined = px.reindex(px.index.union(idx)).ffill().reindex(idx)
    joined = joined.bfill()
    if joined.isna().all() or float(joined.iloc[0]) <= 0:
        return pd.Series(dtype=float)
    return (capital * joined / float(joined.iloc[0])).rename("equity")


# ------------------------------------------------------- the same, but longer

def max_hold_minutes(cfg: BacktestConfig) -> int:
    """Minutes from the entry time to the scheduled close."""
    e = cfg.signal.entry_time
    entry_min = e.hour * 60 + e.minute
    close_min = SESSION_CLOSE.hour * 60 + SESSION_CLOSE.minute
    return int(max(1, min(MAX_SESSION_MINUTES, close_min - entry_min)))


def hold_variants(cfg: BacktestConfig,
                  multiples: tuple[float, ...] = DEFAULT_MULTIPLES
                  ) -> list[tuple[str, int]]:
    """(label, hold_minutes) for each multiple, capped at the close."""
    base = cfg.exit.hold_minutes
    cap = max_hold_minutes(cfg)
    out: dict[int, str] = {}
    for m in multiples:
        v = int(round(base * m))
        capped = min(v, cap)
        if capped <= base:
            continue
        tag = " (capped at the close)" if capped < v else ""
        out.setdefault(capped, f"hold {m:g}x = {capped} min{tag}")
    return [(lab, mins) for mins, lab in sorted(out.items())]


# ------------------------------------------------------------------ compare

def compare(cfg: BacktestConfig, base: Metrics,
            frames: dict[str, pd.DataFrame], eligible, build,
            benchmark_bars: pd.DataFrame | None = None,
            benchmark_ticker: str = "SPY",
            selection: SelectionRule = SelectionRule.VOLUME_RATIO,
            multiples: tuple[float, ...] = DEFAULT_MULTIPLES,
            ) -> BenchmarkResult:
    """Price the strategy against buy-and-hold and against holding longer."""
    capital = cfg.portfolio.starting_capital
    o = base.overall
    strat_row = {"benchmark": base.label or "strategy", "kind": "strategy",
                 "detail": f"{cfg.exit.hold_minutes} min hold",
                 **{k: o.get(k) for k in
                    ("total_return", "cagr", "ann_vol", "sharpe", "max_dd",
                     "calmar", "n_trades", "expectancy_bps", "pct_days_active",
                     "deployed_vol")}}
    rows = [strat_row]
    notes: list[str] = []

    # -- 1. buy and hold the index ----------------------------------
    have_index = False
    if benchmark_bars is not None and len(base.equity) > 1:
        eq = buy_and_hold(benchmark_bars, capital,
                          pd.DatetimeIndex(base.equity.index))
        if len(eq) > 1:
            have_index = True
            s = equity_stats(eq, capital)
            rows.append({"benchmark": f"{benchmark_ticker} buy & hold",
                         "kind": "buy_and_hold",
                         "detail": f"{len(eq)} sessions, fully invested",
                         **{k: s.get(k) for k in
                            ("total_return", "cagr", "ann_vol", "sharpe",
                             "max_dd", "calmar")},
                         "n_trades": 1, "expectancy_bps": np.nan,
                         "pct_days_active": 1.0,
                         "deployed_vol": s.get("ann_vol")})
        else:
            notes.append(f"{benchmark_ticker} bars supplied but produced no "
                         f"overlapping sessions")
    if not have_index:
        notes.append(f"no {benchmark_ticker} series was supplied, so the "
                     f"risk-adjusted comparison against buy-and-hold was not "
                     f"made")

    # -- 2. the same signals, held longer ---------------------------
    for label, mins in hold_variants(cfg, multiples):
        try:
            variant = cfg.replace(**{"exit.hold_minutes": int(mins)})
        except ConfigError as exc:
            notes.append(f"{label}: rejected by the config ({exc})")
            continue
        try:
            strat = build(variant)
            signals = strat.run_many_signals(frames, eligible=eligible)
            log, curve = Portfolio(variant, selection).run(signals, frames)
            m = evaluate(log, capital, label, equity=curve)
        except Exception as exc:  # noqa: BLE001
            notes.append(f"{label}: could not be run ({exc})")
            continue
        mo = m.overall
        stale = float((m.trades.get("exit_reason",
                                    pd.Series(dtype=str)) == "time_stale").mean()) \
            if len(m.trades) else np.nan
        if np.isfinite(stale) and stale > 0.05:
            notes.append(f"{label}: {stale:.0%} of exits were stale, so this "
                         f"row understates what holding longer would have done")
        rows.append({"benchmark": label, "kind": "longer_hold",
                     "detail": f"same signals, exit at +{mins} min",
                     **{k: mo.get(k) for k in
                        ("total_return", "cagr", "ann_vol", "sharpe", "max_dd",
                         "calmar", "n_trades", "expectancy_bps",
                         "pct_days_active", "deployed_vol")}})

    table = pd.DataFrame(rows)
    for col, src in (("sharpe_diff", "sharpe"), ("max_dd_diff", "max_dd"),
                     ("return_diff", "total_return")):
        b = strat_row.get(src)
        table[col] = table[src].astype(float) - (
            float(b) if b is not None and np.isfinite(float(b)) else np.nan)
    table = table.reindex(columns=COLUMNS)

    active = float(strat_row.get("pct_days_active") or 0.0)
    if active < 0.5:
        dep, head = (strat_row.get("deployed_vol"), strat_row.get("ann_vol"))
        vols = ("deployed volatility is not computable on this sample"
                if not _ok(dep) or not _ok(head) else
                f"deployed volatility is {float(dep):.1%} against a headline "
                f"{float(head):.1%}")
        notes.append(
            f"the strategy holds positions on {active:.0%} of sessions, so its "
            f"Sharpe is computed over all sessions including idle ones and is "
            f"not comparable like-for-like with a fully-invested benchmark: "
            f"{vols}.")

    return BenchmarkResult(table=table, strategy=strat_row,
                           index_available=have_index,
                           index_ticker=benchmark_ticker, notes=notes)


def _ok(v) -> bool:
    return v is not None and isinstance(v, (int, float)) and np.isfinite(float(v))


def _fmt(df: pd.DataFrame) -> str:
    x = df.copy()
    for c in x.columns:
        if pd.api.types.is_float_dtype(x[c]):
            x[c] = x[c].map(lambda v: "" if pd.isna(v) else f"{v:,.4f}")
    return x.to_string(index=False)
