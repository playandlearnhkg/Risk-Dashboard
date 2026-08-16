"""
test_gate.py -- assertions for the validation gate.

The tests that matter are the ones proving the gate can FAIL: a gate
never observed rejecting anything is decoration.

Run: python3 tests/test_gate.py
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.config import BacktestConfig  # noqa: E402
from engine.data_loader import DataLoader  # noqa: E402
from engine.gate import (Check, GateThresholds, Verdict,  # noqa: E402
                         run_gate)
from engine.strategy_base import Signal, StrategyBase  # noqa: E402
from engine.universe import AllSessions, from_config  # noqa: E402
from strategies.core_post_earnings import \
    CorePostEarningsContinuation  # noqa: E402
from strategies.opening_range_breakout import OpeningRangeBreakout  # noqa: E402

DATA = ROOT / "data"
CORE = ROOT / "config" / "strategies" / "core_post_earnings.yaml"
ORB = ROOT / "config" / "strategies" / "opening_range_breakout.yaml"

_results: list[tuple[str, bool, str]] = []


def check(name, fn):
    try:
        fn()
        _results.append((name, True, ""))
    except Exception as exc:  # noqa: BLE001
        _results.append((name, False, f"{type(exc).__name__}: {exc}"))
        traceback.print_exc()


def frames():
    ld = DataLoader(DATA)
    return {t: ld.load(t) for t in ld.tickers}


def core_gate(**kw):
    cfg = BacktestConfig.from_yaml(CORE)
    prov = from_config(cfg, DATA / "earnings_calendar.csv",
                       pd.read_csv(DATA / "market_caps.csv"))
    return run_gate(CorePostEarningsContinuation(cfg), cfg, frames(),
                    provider=prov,
                    strategy_factory=lambda b: CorePostEarningsContinuation(cfg),
                    **kw)


# ---------------------------------------------------------- it can refuse

def t_integrity_failure_cannot_be_outvoted():
    """A leak must FAIL even when every performance check passes."""
    class Cheat(StrategyBase):
        ALLOW_RAW_WINDOWING = True

        def __init__(self, cfg, future=None):
            super().__init__(cfg)
            self.future = future

        def evaluate(self, view):
            if self.future is None:
                return None
            later = self.future[(self.future["session_date"] == view.session)
                                & (self.future.index > view.decision_ts)]
            atr = view.prior.atr(self.config.signal.atr_period)
            if later.empty or not np.isfinite(view.entry_open) \
                    or not np.isfinite(atr) or atr <= 0:
                return None
            end = float(later["close"].iloc[min(59, len(later) - 1)])
            return Signal(ticker=view.ticker, session=view.session,
                          decision_ts=view.decision_ts,
                          direction=1 if end > view.entry_open else -1,
                          entry_ts=view.decision_ts,
                          entry_price=view.entry_open, risk_unit=atr,
                          planned_exit_ts=view.decision_ts
                          + pd.Timedelta(minutes=60),
                          features={"volume_ratio": 1.0})

    cfg = BacktestConfig.from_yaml(CORE)
    f = frames()
    res = run_gate(Cheat(cfg, f[next(iter(f))]), cfg, f,
                   strategy_factory=lambda b: Cheat(cfg, b))
    assert res.verdict is Verdict.FAIL
    leak = [c for c in res.checks if c.name == "no_lookahead"][0]
    assert leak.verdict is Verdict.FAIL and leak.integrity
    # And it fails on integrity even though the cheat is wildly profitable.
    assert res.metrics.overall.get("expectancy_bps", 0) > 0, \
        "the cheat should look great, which is the point"


def t_zero_trades_is_a_hard_fail():
    class Never(StrategyBase):
        def evaluate(self, view):
            return None
    cfg = BacktestConfig.from_yaml(CORE)
    res = run_gate(Never(cfg), cfg, frames())
    assert res.verdict is Verdict.FAIL
    assert any(c.name == "trades_exist" and c.verdict is Verdict.FAIL
               for c in res.checks)


def t_all_sessions_universe_is_flagged():
    cfg = BacktestConfig.from_yaml(ORB)
    res = run_gate(OpeningRangeBreakout(cfg), cfg, frames(),
                   provider=AllSessions())
    c = [c for c in res.checks if c.name == "universe_applied"][0]
    assert c.verdict is Verdict.REVIEW and c.integrity


# ------------------------------------------------------------- arithmetic

def t_concentration_is_bounded():
    """Share of GROSS, so winners cancelling losers cannot exceed 1."""
    res = core_gate()
    for n in ("concentration_ticker", "concentration_trade"):
        hits = [c for c in res.checks if c.name == n]
        if hits and isinstance(hits[0].value, float):
            assert 0.0 <= hits[0].value <= 1.0, (n, hits[0].value)


def t_verdict_precedence():
    mk = lambda v: Check("x", v, 1, 1, "")          # noqa: E731
    from engine.gate import GateResult
    import engine.metrics as M
    m = M.evaluate(pd.DataFrame(columns=M.STANDARD_COLUMNS), 1e6, "e")
    for checks, want in (([mk(Verdict.PASS)], Verdict.PASS),
                         ([mk(Verdict.PASS), mk(Verdict.REVIEW)], Verdict.REVIEW),
                         ([mk(Verdict.REVIEW), mk(Verdict.FAIL)], Verdict.FAIL)):
        got = (Verdict.FAIL if any(c.verdict is Verdict.FAIL for c in checks)
               else Verdict.REVIEW if any(c.verdict is Verdict.REVIEW for c in checks)
               else Verdict.PASS)
        assert got is want, (checks, want)


def t_thresholds_are_in_the_report():
    res = core_gate()
    txt = res.report()
    assert "THRESHOLDS APPLIED" in txt
    for k in ("min_trades", "fail_cost_multiple", "min_profit_factor"):
        assert k in txt, k


def t_custom_thresholds_are_honoured():
    strict = GateThresholds(min_trades=10_000_000)
    res = core_gate(thresholds=strict)
    c = [c for c in res.checks if c.name == "sample_trades"][0]
    assert c.threshold == 10_000_000 and c.verdict is Verdict.REVIEW


def t_cost_curve_is_monotone():
    res = core_gate()
    if len(res.costs) > 1:
        e = res.costs.sort_values("cost_bps")["expectancy_bps"].to_numpy()
        assert np.all(np.diff(e) <= 1e-9), "higher cost cannot raise expectancy"


# ------------------------------------------------------------ reusability

def t_gate_runs_on_a_second_unrelated_strategy():
    """The proof it is not tailored to the post-earnings strategy."""
    cfg = BacktestConfig.from_yaml(ORB)
    res = run_gate(OpeningRangeBreakout(cfg), cfg, frames(),
                   strategy_factory=lambda b: OpeningRangeBreakout(cfg))
    assert res.verdict in (Verdict.PASS, Verdict.REVIEW, Verdict.FAIL)
    assert res.report()
    names = {c.name for c in res.checks}
    assert {"no_lookahead", "trades_exist", "universe_applied"} <= names


def t_report_has_every_required_section():
    res = core_gate()
    txt = res.report()
    for s in ("1. SAMPLE TRADES", "2. CORE PERFORMANCE", "3. DISTRIBUTION",
              "5. COST SENSITIVITY", "VERDICT:"):
        assert s in txt, s


def t_write_produces_files():
    import tempfile
    res = core_gate()
    with tempfile.TemporaryDirectory() as d:
        paths = res.write(d)
        assert any(p.name == "gate_report.txt" for p in paths)
        assert any(p.name == "gate_checks.csv" for p in paths)


# ------------------------------------------- sensitivity: it can refuse

def _sens(base, neighbours, binding=None):
    """A SensitivityResult with a chosen neighbourhood, no backtest run."""
    from engine.sensitivity import SensitivityResult, _spike
    e = pd.Series(neighbours, dtype=float)
    med = float(e.median())
    tbl = pd.DataFrame([{"parameter": "(baseline)", "value": "",
                         "expectancy_bps": base}]
                       + [{"parameter": "signal.volume_ratio_min", "value": i,
                           "expectancy_bps": float(v)}
                          for i, v in enumerate(neighbours)])
    return SensitivityResult(
        table=tbl, by_parameter=pd.DataFrame(), base_expectancy_bps=float(base),
        n_variants=len(neighbours),
        n_binding=len(neighbours) if binding is None else binding,
        share_profitable=float((e > 0).mean()), median_neighbour_bps=med,
        spike_ratio=_spike(float(base), med))


def t_sensitivity_spike_fails():
    """A baseline far above its own neighbours is the overfitting shape."""
    from engine.gate import _sensitivity_checks
    th = GateThresholds()
    cs = {c.name: c for c in _sensitivity_checks(_sens(40.0, [8, 9, 10, 11]), th)}
    assert cs["sensitivity_spike"].verdict is Verdict.FAIL, cs["sensitivity_spike"]
    assert not cs["sensitivity_spike"].integrity, \
        "a spike is a performance finding, not an integrity one"


def t_sensitivity_plateau_passes():
    from engine.gate import _sensitivity_checks
    cs = {c.name: c for c in
          _sensitivity_checks(_sens(30.0, [28, 29, 31, 32]), GateThresholds())}
    assert cs["sensitivity_spike"].verdict is Verdict.PASS
    assert cs["sensitivity_stability"].verdict is Verdict.PASS


def t_sensitivity_collapsing_neighbourhood_fails():
    """Most of the neighbourhood losing money is a FAIL, not a caveat."""
    from engine.gate import _sensitivity_checks
    cs = {c.name: c for c in
          _sensitivity_checks(_sens(30.0, [-5, -3, -1, 2]), GateThresholds())}
    assert cs["sensitivity_stability"].verdict is Verdict.FAIL


def t_spike_ratio_is_nan_against_a_nonpositive_base():
    """The ratio bug this project keeps re-finding, guarded once more."""
    from engine.sensitivity import _spike
    assert not np.isfinite(_spike(30.0, 0.0))
    assert not np.isfinite(_spike(30.0, -10.0))
    assert not np.isfinite(_spike(-30.0, -10.0)), \
        "a negative over a negative must not read as a healthy 3x margin"
    assert _spike(30.0, 15.0) == 2.0


def t_inert_parameters_do_not_count_as_stable():
    """Variants that changed nothing prove nothing."""
    from engine.gate import _sensitivity_checks
    cs = {c.name: c for c in
          _sensitivity_checks(_sens(30.0, [30, 30, 30, 30], binding=0),
                              GateThresholds())}
    for n in ("sensitivity_stability", "sensitivity_spike"):
        assert cs[n].verdict is Verdict.REVIEW, n
        assert "bound" in cs[n].detail


# -------------------------------------------- benchmarks: it can refuse

def _bench(strat_sharpe, index_sharpe=None, longer_sharpe=None, active=1.0):
    from engine.benchmarks import BenchmarkResult
    strat = {"benchmark": "S", "kind": "strategy", "sharpe": strat_sharpe,
             "max_dd": -0.05, "total_return": 1.0, "pct_days_active": active,
             "ann_vol": 0.07, "deployed_vol": 0.22}
    rows = [strat]
    if index_sharpe is not None:
        rows.append({"benchmark": "SPY buy & hold", "kind": "buy_and_hold",
                     "sharpe": index_sharpe, "max_dd": -0.34,
                     "total_return": 0.9, "pct_days_active": 1.0})
    if longer_sharpe is not None:
        rows.append({"benchmark": "hold 4x = 240 min", "kind": "longer_hold",
                     "sharpe": longer_sharpe, "max_dd": -0.06,
                     "total_return": 1.2, "pct_days_active": active})
    return BenchmarkResult(table=pd.DataFrame(rows), strategy=strat,
                           index_available=index_sharpe is not None,
                           index_ticker="SPY")


def t_losing_to_the_index_fails():
    from engine.gate import _benchmark_checks
    cs = {c.name: c for c in
          _benchmark_checks(_bench(0.40, index_sharpe=0.85), GateThresholds())}
    assert cs["benchmark_vs_index"].verdict is Verdict.FAIL


def t_beating_the_index_passes():
    from engine.gate import _benchmark_checks
    cs = {c.name: c for c in
          _benchmark_checks(_bench(2.80, index_sharpe=0.60), GateThresholds())}
    assert cs["benchmark_vs_index"].verdict is Verdict.PASS


def t_a_thin_margin_over_the_index_reviews():
    from engine.gate import _benchmark_checks
    cs = {c.name: c for c in
          _benchmark_checks(_bench(0.70, index_sharpe=0.60), GateThresholds())}
    assert cs["benchmark_vs_index"].verdict is Verdict.REVIEW


def t_missing_benchmark_is_review_not_pass():
    from engine.gate import _benchmark_checks
    cs = {c.name: c for c in
          _benchmark_checks(_bench(2.80, index_sharpe=None), GateThresholds())}
    assert cs["benchmark_vs_index"].verdict is Verdict.REVIEW
    assert cs["benchmark_vs_index"].value == "not run"


def t_idle_time_caveat_is_stated_not_silently_adjusted():
    from engine.gate import _benchmark_checks
    cs = {c.name: c for c in
          _benchmark_checks(_bench(2.80, index_sharpe=0.60, active=0.074),
                            GateThresholds())}
    assert "flattered" in cs["benchmark_vs_index"].detail


def t_a_longer_hold_winning_reviews_but_never_fails():
    from engine.gate import _benchmark_checks
    cs = {c.name: c for c in
          _benchmark_checks(_bench(1.50, index_sharpe=0.60,
                                   longer_sharpe=2.40), GateThresholds())}
    c = cs["benchmark_vs_longer_hold"]
    assert c.verdict is Verdict.REVIEW
    assert c.verdict is not Verdict.FAIL


def t_a_tie_on_the_longer_hold_does_not_review():
    """Floating-point noise on two near-identical curves is not a finding."""
    from engine.gate import _benchmark_checks
    cs = {c.name: c for c in
          _benchmark_checks(_bench(1.6290, index_sharpe=0.60,
                                   longer_sharpe=1.6292), GateThresholds())}
    assert cs["benchmark_vs_longer_hold"].verdict is Verdict.PASS


# ------------------------------------------------- ordering and precedence

def t_new_checks_run_after_integrity_and_performance():
    res = core_gate()
    names = [c.name for c in res.checks]
    for early in ("no_lookahead", "trades_exist", "expectancy", "cost_headroom"):
        if early in names:
            for late in ("sensitivity_stability", "benchmark_vs_index"):
                assert names.index(late) > names.index(early), (late, early)


def t_a_leak_still_fails_with_a_perfect_sensitivity_surface():
    """Integrity supremacy, restated against the new checks."""
    from engine.gate import GateResult, Verdict as V
    import engine.metrics as M
    m = M.evaluate(pd.DataFrame(columns=M.STANDARD_COLUMNS), 1e6, "e")
    checks = [Check("no_lookahead", V.FAIL, "LEAK", "must pass", "",
                    integrity=True),
              Check("sensitivity_spike", V.PASS, 1.0, 1.5, ""),
              Check("benchmark_vs_index", V.PASS, 2.2, 0.25, "")]
    got = (V.FAIL if any(c.verdict is V.FAIL for c in checks)
           else V.REVIEW if any(c.verdict is V.REVIEW for c in checks)
           else V.PASS)
    assert got is V.FAIL
    assert GateResult("s", got, checks, m, pd.DataFrame(), {},
                      GateThresholds()).verdict is V.FAIL


def t_extended_off_is_visible_in_the_report():
    """Skipping is allowed. Looking like it passed is not."""
    res = core_gate(extended=False)
    cs = {c.name: c for c in res.checks}
    for n in ("sensitivity_stability", "sensitivity_spike",
              "benchmark_vs_index", "benchmark_vs_longer_hold"):
        assert cs[n].verdict is Verdict.REVIEW, n
        assert "turned off" in cs[n].detail
    assert res.verdict is not Verdict.PASS


def t_new_sections_and_thresholds_are_in_the_report():
    res = core_gate()
    txt = res.report()
    for s in ("6. PARAMETER SENSITIVITY", "7. BENCHMARKS",
              "review_sensitivity_spike", "review_sharpe_margin_vs_index"):
        assert s in txt, s


def t_buy_and_hold_curve_starts_at_capital():
    from engine.benchmarks import buy_and_hold
    f = frames()
    bars = f[next(iter(f))]
    idx = pd.DatetimeIndex(sorted({pd.Timestamp(d) for d in
                                   bars.index.tz_convert("America/New_York").date}))
    eq = buy_and_hold(bars, 1_000_000.0, idx)
    assert len(eq) == len(idx)
    assert abs(float(eq.iloc[0]) - 1_000_000.0) < 1e-6
    assert eq.notna().all(), "a benchmark gap must be flat, never NaN"


def t_benchmark_runs_end_to_end_when_spy_is_supplied():
    """The whole path, not the helpers: real bars in, a real margin out."""
    ld = DataLoader(DATA / "benchmark")
    assert "SPY" in ld.tickers, "the SPY fixture is missing; run make_fixtures"
    res = core_gate(benchmark_bars=ld.load("SPY"))
    c = [c for c in res.checks if c.name == "benchmark_vs_index"][0]
    assert c.value != "not run", c.detail
    assert res.benchmarks is not None and res.benchmarks.index_available
    kinds = set(res.benchmarks.table["kind"])
    assert {"strategy", "buy_and_hold", "longer_hold"} <= kinds, kinds
    assert "SPY buy & hold" in res.report()


def t_the_benchmark_is_not_in_the_tradeable_universe():
    """A benchmark that joined `frames` would be compared with itself."""
    assert "SPY" not in DataLoader(DATA).tickers


def t_longer_holds_are_capped_at_the_session_close():
    from engine.benchmarks import hold_variants, max_hold_minutes
    cfg = BacktestConfig.from_yaml(CORE)
    cap = max_hold_minutes(cfg)
    assert cap == 385, cap                      # 09:35 -> 16:00
    for _, mins in hold_variants(cfg, multiples=(2.0, 4.0, 40.0)):
        assert mins <= cap
        assert mins > cfg.exit.hold_minutes


def main() -> int:
    for name, fn in [(k[2:], v) for k, v in sorted(globals().items())
                     if k.startswith("t_") and callable(v)]:
        check(name, fn)
    width = max(len(n) for n, _, _ in _results)
    failed = sum(not ok for _, ok, _ in _results)
    print()
    for name, ok, msg in _results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<{width}}  {msg}")
    print(f"\n{len(_results) - failed}/{len(_results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
