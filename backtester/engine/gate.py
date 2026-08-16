"""
gate.py -- the validation gate every strategy must clear.

A gate is only useful if it can fail a strategy you want to pass. Two
design choices follow from that, and both are deliberate constraints on
the person running it:

  1 THRESHOLDS ARE DECLARED BEFORE THE RESULT IS SEEN. They live in
    `GateThresholds` with defaults, they are printed alongside every
    verdict, and the report names the number each check compared
    against. A threshold quietly loosened to make a run pass is then
    visible in the artefact rather than in somebody's memory.

  2 INTEGRITY OUTRANKS PERFORMANCE. A look-ahead failure is a hard FAIL
    no matter how good the Sharpe is. Performance checks cannot rescue
    it, and there is no override flag. A strategy that cheats is not a
    strategy with a caveat.

THREE VERDICTS, NOT TWO

  PASS          every check cleared
  NEEDS REVIEW  nothing is broken, but something is unproven -- too few
                trades, too short a history, one name carrying the P&L
  FAIL          an integrity check failed, or the edge is not there

The middle verdict exists because "we cannot tell yet" and "this does
not work" are different findings, and collapsing them into FAIL teaches
people to ignore the gate.

THE ORDER THE CHECKS RUN IN, AND WHY IT IS FIXED

  1 INTEGRITY     is this measuring what we think it is measuring
  2 ADEQUACY      is there enough of it to judge
  3 PERFORMANCE   is there an edge, and does it survive worse fills
  4 SENSITIVITY   is the edge a plateau or a single fitted point
  5 BENCHMARKS    is it better than the obvious alternative

Sensitivity and benchmarking run LAST because both are expensive -- each
re-runs the whole signal-to-portfolio path several times -- and both are
meaningless before the earlier stages clear. Measuring the parameter
neighbourhood of a strategy that reads the future prices the
neighbourhood of a leak. They do not change the precedence rule: any
FAIL is a FAIL, so an integrity failure still cannot be outvoted, no
matter how flat the sensitivity surface or how far ahead of the index
the equity curve finished.

WHAT THE GATE DOES NOT DO

It does not tune anything, rank anything, or pick a best variant. It
runs one configuration and judges it. The moment a gate starts searching
for a version that passes, it stops being a gate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path

import numpy as np
import pandas as pd

from engine.benchmarks import BenchmarkResult, compare
from engine.config import BacktestConfig
from engine.metrics import Metrics, evaluate
from engine.pit import LookAheadError, verify_no_lookahead
from engine.portfolio import Portfolio, SelectionRule
from engine.sensitivity import SensitivityResult, parameter_sensitivity
from engine.universe import AllSessions, UniverseProvider


class Verdict(str, Enum):
    PASS = "PASS"
    REVIEW = "NEEDS REVIEW"
    FAIL = "FAIL"


@dataclass(frozen=True)
class GateThresholds:
    """Every number the gate judges against. Printed with each verdict."""
    # -- sample adequacy: not broken, just unproven
    min_trades: int = 100
    min_tickers: int = 20
    min_years: float = 3.0
    max_single_ticker_pnl_share: float = 0.30
    max_single_trade_pnl_share: float = 0.25

    # -- performance
    min_expectancy_bps: float = 0.0          # <= this FAILS
    review_expectancy_bps: float = 5.0       # below this REVIEWS
    min_profit_factor: float = 1.0           # <= this FAILS
    review_profit_factor: float = 1.15
    min_positive_year_share: float = 0.60

    # -- cost headroom: the edge must survive worse fills
    fail_cost_multiple: float = 1.5          # dead at 1.5x cost -> FAIL
    review_cost_multiple: float = 2.5

    # -- data integrity
    max_time_stale_share: float = 0.05
    max_gross_capped_share: float = 0.25

    # -- parameter sensitivity: a plateau, or one fitted point?
    # Share of the varied neighbourhood that must still make money. A
    # strategy whose edge disappears when volume_ratio_min moves 10% was
    # never robust; it was located.
    review_sensitivity_profitable_share: float = 0.80
    fail_sensitivity_profitable_share: float = 0.50
    # Baseline expectancy divided by the median of its own neighbours.
    # 1.0 is a plateau. Well above 1.0 is a spike, which is what a fitted
    # parameter looks like from outside.
    review_sensitivity_spike: float = 1.50
    fail_sensitivity_spike: float = 3.00

    # -- benchmarks: better than the obvious alternative?
    # Sharpe margin the strategy must hold over buy-and-hold. Read this
    # alongside pct_days_active: an intraday book idle 93% of the time
    # has a structurally flattered Sharpe against a fully-invested index.
    review_sharpe_margin_vs_index: float = 0.25
    fail_sharpe_margin_vs_index: float = 0.00
    # How far a LONGER hold of the same names may beat the configured
    # hold before a human is asked why this hold length was chosen. A
    # small negative, not zero: an exact tie should not trigger a review,
    # and floating-point noise on two nearly identical curves lands
    # either side of zero at random.
    review_sharpe_margin_vs_longer_hold: float = -0.10


@dataclass(frozen=True)
class Check:
    name: str
    verdict: Verdict
    value: float | str | None
    threshold: float | str | None
    detail: str
    integrity: bool = False

    def row(self) -> dict:
        return {"check": self.name, "verdict": self.verdict.value,
                "value": self.value, "threshold": self.threshold,
                "integrity": self.integrity, "detail": self.detail}


@dataclass
class GateResult:
    strategy: str
    verdict: Verdict
    checks: list[Check]
    metrics: Metrics
    costs: pd.DataFrame
    samples: dict[str, pd.DataFrame]
    thresholds: GateThresholds
    sensitivity: SensitivityResult | None = None
    benchmarks: BenchmarkResult | None = None
    meta: dict = field(default_factory=dict)

    @property
    def table(self) -> pd.DataFrame:
        return pd.DataFrame([c.row() for c in self.checks])

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if c.verdict is Verdict.FAIL]

    @property
    def reviews(self) -> list[Check]:
        return [c for c in self.checks if c.verdict is Verdict.REVIEW]

    # -- output -------------------------------------------------------

    def report(self) -> str:
        o, d = self.metrics.overall, self.metrics.distribution
        bar = "=" * 78
        L = [bar, f"VALIDATION GATE  --  {self.strategy}", bar,
             f"VERDICT: {self.verdict.value}", ""]

        if self.failures:
            L += ["BLOCKING", "-" * 8]
            for c in self.failures:
                tag = "INTEGRITY" if c.integrity else "PERFORMANCE"
                L.append(f"  [{tag}] {c.name}: {c.detail}")
            L.append("")
        if self.reviews:
            L += ["NEEDS A HUMAN", "-" * 13]
            for c in self.reviews:
                L.append(f"  {c.name}: {c.detail}")
            L.append("")

        L += ["ALL CHECKS", "-" * 10, _fmt(self.table), ""]

        L += ["2. CORE PERFORMANCE", "-" * 19]
        for k, lab, pct in (("cagr", "CAGR", True),
                            ("max_dd", "max drawdown", True),
                            ("sharpe", "Sharpe (rf=0)", False),
                            ("calmar", "Calmar", False),
                            ("win_rate", "win rate", True),
                            ("expectancy_bps", "avg trade (bps)", False),
                            ("payoff_ratio", "payoff ratio", False),
                            ("profit_factor", "profit factor", False),
                            ("n_trades", "trades", False)):
            v = o.get(k)
            s = "n/a" if v is None or (isinstance(v, float) and pd.isna(v)) \
                else (f"{v * 100:,.2f}%" if pct else f"{v:,.2f}")
            L.append(f"  {lab:<18} {s}")

        L += ["", "3. DISTRIBUTION", "-" * 15]
        for k, lab in (("median_bps", "median (bps)"), ("p10", "p10"),
                       ("p25", "p25"), ("p75", "p75"), ("p90", "p90"),
                       ("skew_wins", "skew (winsorised)"),
                       ("exkurt_wins", "excess kurtosis (wins.)"),
                       ("pct_loss_gt_1atr", "% losing > 1 ATR"),
                       ("pct_loss_gt_0_5atr", "% losing > 0.5 ATR")):
            v = d.get(k)
            s = "n/a" if v is None or pd.isna(v) else (
                f"{v * 100:,.2f}%" if k.startswith("pct_") else f"{v:,.3f}")
            L.append(f"  {lab:<24} {s}")

        if len(self.metrics.by_year):
            L += ["", "4. YEAR BY YEAR", "-" * 15,
                  _fmt(self.metrics.by_year)]
        L += ["", "5. COST SENSITIVITY", "-" * 19, _fmt(self.costs)]

        L += ["", "6. PARAMETER SENSITIVITY", "-" * 24]
        if self.sensitivity is None:
            L.append("  not run")
        else:
            L.append(self.sensitivity.summary())
            if len(self.sensitivity.by_parameter):
                L += ["", _fmt(self.sensitivity.by_parameter)]
            if len(self.sensitivity.table):
                L += ["", _fmt(self.sensitivity.table)]

        L += ["", "7. BENCHMARKS", "-" * 13]
        L.append("  not run" if self.benchmarks is None
                 else self.benchmarks.summary())

        L += ["", "1. SAMPLE TRADES FOR MANUAL CHECK", "-" * 33]
        for name, s in self.samples.items():
            if len(s):
                L += [f"  {name}", _fmt(s), ""]

        L += ["", "THRESHOLDS APPLIED", "-" * 18]
        for k, v in asdict(self.thresholds).items():
            L.append(f"  {k:<38} {v}")
        return "\n".join(L)

    def write(self, out_dir: Path | str) -> list[Path]:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        paths = []
        for name, obj in (("gate_checks", self.table),
                          ("gate_costs", self.costs),
                          ("gate_year_by_year", self.metrics.by_year),
                          ("gate_trades", self.metrics.trades)):
            p = out / f"{name}.csv"
            obj.to_csv(p, index=False)
            paths.append(p)
        if self.sensitivity is not None:
            for name, obj in (("gate_sensitivity", self.sensitivity.table),
                              ("gate_sensitivity_by_parameter",
                               self.sensitivity.by_parameter)):
                p = out / f"{name}.csv"
                obj.to_csv(p, index=False)
                paths.append(p)
        if self.benchmarks is not None:
            p = out / "gate_benchmarks.csv"
            self.benchmarks.table.to_csv(p, index=False)
            paths.append(p)
        for name, s in self.samples.items():
            p = out / f"gate_sample_{name.replace(' ', '_')}.csv"
            s.to_csv(p, index=False)
            paths.append(p)
        p = out / "gate_report.txt"
        p.write_text(self.report())
        paths.append(p)
        return paths


# ------------------------------------------------------------------- runner

def run_gate(strategy, cfg: BacktestConfig, frames: dict[str, pd.DataFrame],
             provider: UniverseProvider | None = None,
             thresholds: GateThresholds | None = None,
             selection: SelectionRule = SelectionRule.VOLUME_RATIO,
             strategy_factory=None, n_sample: int = 8,
             config_factory=None, extended: bool = True,
             benchmark_bars: pd.DataFrame | None = None,
             benchmark_ticker: str = "SPY") -> GateResult:
    """Run one configuration and judge it.

    `strategy` is any StrategyBase instance. `strategy_factory`, if
    given, is `factory(bars) -> StrategyBase` and makes the look-ahead
    check strictly stronger -- it rebuilds the strategy from truncated
    data, which catches a strategy holding a frame it captured at
    construction. Without it the check still runs, but cannot see that
    case, and the report says so.

    `config_factory` is `factory(config) -> StrategyBase` and is what the
    sensitivity and longer-hold tests use to rebuild the strategy under a
    varied configuration. It defaults to `type(strategy)(config)`, which
    is correct for any strategy whose constructor takes only a config.
    A strategy needing more must pass one, or those two tests report
    NEEDS REVIEW rather than quietly measuring the unvaried baseline
    four times and calling it stable.

    `extended=False` skips both. It does not hide that it skipped: the
    two checks are still emitted, as NEEDS REVIEW, saying they were
    turned off. Speed is a legitimate reason to skip them and not a
    reason for the artefact to look like they passed.

    `benchmark_bars` is a bar frame for `benchmark_ticker` (SPY by
    default). Without it there is no buy-and-hold comparison, and that
    absence is itself a NEEDS REVIEW -- the same treatment `AllSessions`
    gets, and for the same reason: a missing comparison should be a
    visible choice rather than a silent one.
    """
    th = thresholds or GateThresholds()
    provider = provider or AllSessions()
    name = f"{cfg.strategy.name} v{cfg.strategy.version}"
    checks: list[Check] = []

    # ---- integrity: universe --------------------------------------
    eligible = provider.eligible(frames)
    diag = provider.diagnostics()
    if isinstance(provider, AllSessions):
        checks.append(Check(
            "universe_applied", Verdict.REVIEW, "AllSessions", "a real provider",
            "no universe filter: every session is evaluated. Correct only if "
            "the strategy genuinely trades every day.", integrity=True))
    else:
        checks.append(Check(
            "universe_applied", Verdict.PASS, diag.get("eligible_pairs"),
            diag.get("candidate_sessions"),
            f"{diag.get('eligible_pairs')} of {diag.get('candidate_sessions')} "
            f"candidate sessions eligible", integrity=True))

    signals = strategy.run_many_signals(frames, eligible=eligible)

    # ---- integrity: look-ahead ------------------------------------
    checks.append(_lookahead_check(strategy, strategy_factory, frames, cfg))

    # ---- run -------------------------------------------------------
    log, curve = Portfolio(cfg, selection).run(signals, frames)
    m = evaluate(log, cfg.portfolio.starting_capital, name, equity=curve)
    t = m.trades
    o, dist = m.overall, m.distribution

    if not len(t):
        checks.append(Check("trades_exist", Verdict.FAIL, 0, "> 0",
                            "no trades were produced; nothing can be judged",
                            integrity=True))
        return GateResult(name, Verdict.FAIL, checks, m, pd.DataFrame(),
                          {}, th, meta={"universe": diag})
    checks.append(Check("trades_exist", Verdict.PASS, len(t), "> 0",
                        f"{len(t):,} trades", integrity=True))

    # ---- integrity: execution quality -----------------------------
    stale = float((t.get("exit_reason", pd.Series(dtype=str)) == "time_stale").mean())
    checks.append(_band("stale_exits", stale, th.max_time_stale_share,
                        th.max_time_stale_share * 2, higher_is_worse=True,
                        detail=f"{stale:.1%} of exits fell back to a stale "
                               f"close because the exit bar never printed",
                        integrity=True))
    capped = float(t["scaled"].mean()) if "scaled" in t else 0.0
    checks.append(_band("gross_cap_binding", capped, th.max_gross_capped_share,
                        th.max_gross_capped_share * 2, higher_is_worse=True,
                        detail=f"{capped:.1%} of trades were scaled down by the "
                               f"gross-exposure cap"))

    # ---- sample adequacy ------------------------------------------
    yrs = o.get("n_days", 0) / 252.0
    checks.append(_min("sample_trades", len(t), th.min_trades,
                       f"{len(t):,} trades vs {th.min_trades} needed to judge"))
    checks.append(_min("sample_tickers", t["ticker"].nunique(), th.min_tickers,
                       f"{t['ticker'].nunique()} tickers vs {th.min_tickers} "
                       f"needed; a narrow book is a narrow test"))
    checks.append(_min("sample_years", yrs, th.min_years,
                       f"{yrs:.1f} years of sessions vs {th.min_years} needed"))

    # Concentration is measured against GROSS P&L (the sum of absolute
    # contributions), not net. A share of net is unbounded when winners
    # and losers nearly cancel -- it printed "273% of P&L" on the first
    # run here, which is arithmetically true and useless. Gross is
    # bounded to [0, 1] and means the same thing.
    gross = float(t["pnl"].abs().sum())
    if gross > 0:
        top_t = float(t.groupby("ticker")["pnl"].sum().abs().max() / gross)
        top_1 = float(t["pnl"].abs().max() / gross)
        checks.append(_band("concentration_ticker", top_t,
                            th.max_single_ticker_pnl_share, 0.5,
                            higher_is_worse=True,
                            detail=f"largest single name is {top_t:.0%} of "
                                   f"gross P&L"))
        checks.append(_band("concentration_trade", top_1,
                            th.max_single_trade_pnl_share, 0.5,
                            higher_is_worse=True,
                            detail=f"largest single trade is {top_1:.0%} of "
                                   f"gross P&L"))

    # ---- performance ----------------------------------------------
    exp = o.get("expectancy_bps", float("nan"))
    checks.append(_band("expectancy", exp, th.review_expectancy_bps,
                        th.min_expectancy_bps, higher_is_worse=False,
                        detail=f"average trade is {exp:,.2f} bps after costs"))
    pf = o.get("profit_factor", float("nan"))
    checks.append(_band("profit_factor", pf, th.review_profit_factor,
                        th.min_profit_factor, higher_is_worse=False,
                        detail=f"profit factor {pf:,.2f}"))

    if len(m.by_year):
        pos = float((m.by_year["total_return"] > 0).mean())
        checks.append(_min("positive_years", pos, th.min_positive_year_share,
                           f"{pos:.0%} of years positive "
                           f"({int((m.by_year['total_return'] > 0).sum())} of "
                           f"{len(m.by_year)})"))

    # ---- cost headroom --------------------------------------------
    costs, death = _cost_curve(cfg, signals, frames, selection)
    base = cfg.costs.round_trip_bps
    mult = (death / base) if (death and base) else float("inf")
    if not np.isfinite(mult):
        detail = (f"still profitable at the highest cost tested "
                  f"({costs['cost_bps'].max():g} bps, "
                  f"{costs['cost_bps'].max() / base:.1f}x)")
        checks.append(Check("cost_headroom", Verdict.PASS, ">= "
                            f"{costs['cost_bps'].max() / base:.1f}x",
                            f"{th.review_cost_multiple}x", detail))
    else:
        detail = (f"edge dies at {death:g} bps, {mult:.1f}x the assumed "
                  f"{base:g} bps")
        checks.append(_band("cost_headroom", mult, th.review_cost_multiple,
                            th.fail_cost_multiple, higher_is_worse=False,
                            detail=detail))

    # ---- 4. parameter sensitivity ---------------------------------
    # Runs after everything above, because it re-runs the entire path
    # once per varied value and there is no point pricing the parameter
    # neighbourhood of a strategy that already failed integrity.
    build = config_factory or _default_config_factory(strategy)
    sens: SensitivityResult | None = None
    if not extended:
        checks.append(_skipped("sensitivity_stability",
                               "extended tests were turned off (extended=False)"))
        checks.append(_skipped("sensitivity_spike",
                               "extended tests were turned off (extended=False)"))
    elif build is None:
        why = ("no config_factory was given and the strategy cannot be "
               "rebuilt from a config alone, so no parameter could be varied")
        checks.append(_skipped("sensitivity_stability", why))
        checks.append(_skipped("sensitivity_spike", why))
    else:
        try:
            sens = parameter_sensitivity(cfg, frames, eligible, build, selection)
            checks += _sensitivity_checks(sens, th)
        except Exception as exc:  # noqa: BLE001
            checks.append(_skipped("sensitivity_stability",
                                   f"the sweep could not run: {exc}"))
            checks.append(_skipped("sensitivity_spike",
                                   f"the sweep could not run: {exc}"))

    # ---- 5. benchmarks --------------------------------------------
    bench: BenchmarkResult | None = None
    if not extended:
        checks.append(_skipped("benchmark_vs_index",
                               "extended tests were turned off (extended=False)"))
        checks.append(_skipped("benchmark_vs_longer_hold",
                               "extended tests were turned off (extended=False)"))
    elif build is None:
        checks.append(_skipped("benchmark_vs_index",
                               "no config_factory, so no comparison was run"))
        checks.append(_skipped("benchmark_vs_longer_hold",
                               "no config_factory, so the same signals could "
                               "not be re-run with a longer hold"))
    else:
        try:
            bench = compare(cfg, m, frames, eligible, build,
                            benchmark_bars=benchmark_bars,
                            benchmark_ticker=benchmark_ticker,
                            selection=selection)
            checks += _benchmark_checks(bench, th)
        except Exception as exc:  # noqa: BLE001
            checks.append(_skipped("benchmark_vs_index",
                                   f"the comparison could not run: {exc}"))
            checks.append(_skipped("benchmark_vs_longer_hold",
                                   f"the comparison could not run: {exc}"))

    # ---- samples ----------------------------------------------------
    cols = [c for c in ("trade_id", "ticker", "date", "side", "entry_time",
                        "entry_price", "exit_price", "exit_reason", "pnl",
                        "pnl_bps", "mae_atr", "mfe_atr", "gap_atr",
                        "volume_ratio") if c in t.columns]
    k = min(n_sample, len(t))
    samples = {
        "random": t.sample(k, random_state=11).sort_values("date")[cols],
        "best": t.nlargest(k, "pnl_bps")[cols],
        "worst": t.nsmallest(k, "pnl_bps")[cols],
    }

    # Precedence, and the reason integrity cannot be overridden: ANY
    # failing check fails the run. There is no weighting, no scoring, and
    # nothing a later stage can add that outvotes an earlier one.
    verdict = (Verdict.FAIL if any(c.verdict is Verdict.FAIL for c in checks)
               else Verdict.REVIEW if any(c.verdict is Verdict.REVIEW for c in checks)
               else Verdict.PASS)
    meta = {"universe": diag, "n_signals": len(signals),
            "selection": selection.value, "extended": extended,
            "benchmark_ticker": benchmark_ticker}
    return GateResult(name, verdict, checks, m, costs, samples, th,
                      sensitivity=sens, benchmarks=bench, meta=meta)


# ------------------------------------------------- sensitivity + benchmarks

def _default_config_factory(strategy):
    """`cfg -> StrategyBase`, or None if the strategy needs more than that.

    Probing the constructor rather than assuming it. A strategy whose
    `__init__` takes extra arguments cannot be rebuilt from a config
    alone, and guessing would either crash inside the sweep or -- worse
    -- construct something subtly different and report its numbers as the
    strategy's own.
    """
    cls = type(strategy)
    try:
        import inspect
        params = list(inspect.signature(cls.__init__).parameters.values())[1:]
        required = [p for p in params
                    if p.default is inspect.Parameter.empty
                    and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        if len(required) != 1:
            return None
    except (TypeError, ValueError):
        return None
    return lambda cfg: cls(cfg)


def _skipped(name: str, why: str) -> Check:
    """A test that did not run is NEEDS REVIEW, never PASS.

    The alternative -- omitting the row -- makes a skipped test and a
    passed test look identical in the artefact, which is the failure mode
    this whole module exists to prevent.
    """
    return Check(name, Verdict.REVIEW, "not run", "must run", why)


def _sensitivity_checks(s: SensitivityResult, th: GateThresholds) -> list[Check]:
    """Two questions: does the neighbourhood work, and is this a spike."""
    if not s.n_variants:
        why = ("no parameter could be varied: "
               + "; ".join(f"{k} -- {v}" for k, v in s.skipped.items())
               if s.skipped else "no parameter could be varied")
        return [_skipped("sensitivity_stability", why),
                _skipped("sensitivity_spike", why)]

    if not s.n_binding:
        why = (f"all {s.n_variants} variants returned the baseline result "
               f"unchanged, so no parameter actually bound on this data. "
               f"Stability measured this way means nothing -- a filter loose "
               f"enough to be inert would pass it.")
        return [_skipped("sensitivity_stability", why),
                _skipped("sensitivity_spike", why)]

    out = [_band(
        "sensitivity_stability", s.share_profitable,
        th.review_sensitivity_profitable_share,
        th.fail_sensitivity_profitable_share, higher_is_worse=False,
        detail=(f"{s.share_profitable:.0%} of {s.n_variants} nearby parameter "
                f"settings are still profitable; neighbourhood median "
                f"{s.median_neighbour_bps:,.2f} bps against a baseline "
                f"{s.base_expectancy_bps:,.2f} bps"))]

    if not np.isfinite(s.spike_ratio):
        out.append(Check(
            "sensitivity_spike", Verdict.REVIEW, None,
            th.review_sensitivity_spike,
            f"the neighbourhood median is {s.median_neighbour_bps:,.2f} bps, "
            f"at or below zero, so the spike ratio is not computable. The "
            f"baseline earning {s.base_expectancy_bps:,.2f} bps while its own "
            f"neighbours do not is the finding."))
    else:
        out.append(_band(
            "sensitivity_spike", s.spike_ratio, th.review_sensitivity_spike,
            th.fail_sensitivity_spike, higher_is_worse=True,
            detail=(f"the configured values earn {s.spike_ratio:,.2f}x the "
                    f"median of their own neighbours "
                    f"(1.0x would be a flat plateau)")))
    return out


def _benchmark_checks(b: BenchmarkResult, th: GateThresholds) -> list[Check]:
    """Beating the index, and not being beaten by simply waiting longer."""
    out: list[Check] = []
    s_sharpe = float(b.strategy.get("sharpe", float("nan")))

    if not b.index_available:
        out.append(_skipped(
            "benchmark_vs_index",
            f"no {b.index_ticker} series was supplied, so the strategy was "
            f"never compared with buying and holding the index"))
    else:
        row = b.table[b.table["kind"] == "buy_and_hold"].iloc[0]
        margin = b.worst_sharpe_margin("buy_and_hold")
        idle = float(b.strategy.get("pct_days_active") or float("nan"))
        caveat = ("" if not np.isfinite(idle) or idle >= 0.5 else
                  f"; the strategy is idle on {1 - idle:.0%} of sessions, so "
                  f"this margin is flattered")
        out.append(_band(
            "benchmark_vs_index", margin, th.review_sharpe_margin_vs_index,
            th.fail_sharpe_margin_vs_index, higher_is_worse=False,
            detail=(f"Sharpe {s_sharpe:,.2f} vs {b.index_ticker} buy & hold "
                    f"{float(row['sharpe']):,.2f} (margin {margin:+,.2f}); "
                    f"max drawdown {float(b.strategy.get('max_dd') or 0):.1%} "
                    f"vs {float(row['max_dd']):.1%}; total return "
                    f"{float(b.strategy.get('total_return') or 0):.1%} vs "
                    f"{float(row['total_return']):.1%}{caveat}")))

    longer = b.table[b.table["kind"] == "longer_hold"]
    if not len(longer):
        out.append(_skipped("benchmark_vs_longer_hold",
                            "no longer hold could be tested (the configured "
                            "hold already reaches the session close)"))
    else:
        margin = b.worst_sharpe_margin("longer_hold")
        best = longer.loc[longer["sharpe"].astype(float).idxmax()]
        # REVIEW only, never FAIL. A longer hold winning does not make
        # the edge fake -- it makes the chosen exit questionable, and
        # that is a judgement for a human with the research in front of
        # them, not an automatic rejection.
        v = (Verdict.REVIEW
             if (np.isfinite(margin) and margin < th.review_sharpe_margin_vs_longer_hold)
             else Verdict.PASS if np.isfinite(margin) else Verdict.REVIEW)
        out.append(Check(
            "benchmark_vs_longer_hold", v, _r(margin),
            th.review_sharpe_margin_vs_longer_hold,
            (f"the configured hold has Sharpe {s_sharpe:,.2f}; the best longer "
             f"hold tested ({best['benchmark']}) has {float(best['sharpe']):,.2f} "
             f"(margin {margin:+,.2f}). "
             + ("Holding the same names longer did better, so the exit is "
                "doing work the entry filter is being credited with."
                if np.isfinite(margin) and margin < th.review_sharpe_margin_vs_longer_hold
                else "The configured hold is not beaten by simply waiting."))))
    return out


# ------------------------------------------------------------------ helpers

def _lookahead_check(strategy, factory, frames, cfg) -> Check:
    """Integrity, and the one no performance number can override."""
    tick = next(iter(frames), None)
    if tick is None:
        return Check("no_lookahead", Verdict.FAIL, None, "must pass",
                     "no data to verify against", integrity=True)
    target = factory if factory is not None else strategy
    try:
        out = verify_no_lookahead(target, frames[tick], tick)
    except LookAheadError as exc:
        return Check("no_lookahead", Verdict.FAIL, "LEAK", "must pass",
                     f"future data reached a decision: {exc}", integrity=True)
    except Exception as exc:  # noqa: BLE001
        return Check("no_lookahead", Verdict.REVIEW, "ERROR", "must pass",
                     f"the check could not run: {exc}", integrity=True)
    strength = ("factory form: strategy rebuilt from truncated data"
                if factory is not None else
                "instance form: cannot see a frame captured at construction "
                "-- pass strategy_factory for the stronger check")
    return Check("no_lookahead", Verdict.PASS, f"{len(out)} decisions",
                 "must pass", f"re-ran with the future deleted; {strength}",
                 integrity=True)


def _cost_curve(cfg, signals, frames, selection):
    """Expectancy against cost, and the level where it turns negative."""
    base = cfg.costs.round_trip_bps
    grid = sorted({round(base * m, 2) for m in (1.0, 1.5, 2.0, 2.5, 3.5, 5.0)})
    rows, death = [], None
    for c in grid:
        cc = cfg.replace(**{"costs.round_trip_bps": float(c)})
        log, curve = Portfolio(cc, selection).run(signals, frames)
        m = evaluate(log, cc.portfolio.starting_capital, "c", equity=curve)
        e = m.overall.get("expectancy_bps", float("nan"))
        rows.append({"cost_bps": c, "x_base": round(c / base, 2)
                     if base else np.nan,
                     "expectancy_bps": e, "cagr": m.overall.get("cagr"),
                     "profit_factor": m.overall.get("profit_factor"),
                     "win_rate": m.overall.get("win_rate")})
        if death is None and np.isfinite(e) and e <= 0:
            death = c
    return pd.DataFrame(rows), death


def _min(name, value, floor, detail) -> Check:
    v = Verdict.PASS if (np.isfinite(value) and value >= floor) else Verdict.REVIEW
    return Check(name, v, _r(value), floor, detail)


def _band(name, value, review_at, fail_at, higher_is_worse, detail,
          integrity: bool = False) -> Check:
    """Three-way: PASS, REVIEW past one line, FAIL past the other."""
    if not np.isfinite(value):
        return Check(name, Verdict.REVIEW, None, review_at,
                     detail + " (not computable)", integrity)
    if higher_is_worse:
        v = (Verdict.FAIL if value > fail_at else
             Verdict.REVIEW if value > review_at else Verdict.PASS)
    else:
        v = (Verdict.FAIL if value <= fail_at else
             Verdict.REVIEW if value < review_at else Verdict.PASS)
    return Check(name, v, _r(value), review_at, detail, integrity)


def _r(v):
    return round(float(v), 4) if isinstance(v, (int, float, np.floating)) else v


def _fmt(df: pd.DataFrame) -> str:
    x = df.copy()
    for c in x.columns:
        if pd.api.types.is_float_dtype(x[c]):
            x[c] = x[c].map(lambda v: "" if pd.isna(v) else f"{v:,.4f}")
    return x.to_string(index=False)
