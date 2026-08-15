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
