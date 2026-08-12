"""
test_pit_strategy.py -- assertions for the point-in-time guards.

The tests that matter most here are the adversarial ones: a deliberately
cheating strategy must be REJECTED, by each of the three layers in turn.
A guard that has never been shown to fail is not a guard.

Run: python3 tests/test_pit_strategy.py
"""

from __future__ import annotations

import datetime as dt
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.config import BacktestConfig  # noqa: E402
from engine.data_loader import DataLoader  # noqa: E402
from engine.pit import (LookAheadError, PointInTimeEngine,  # noqa: E402
                        audit_source, shifted_rolling_mean,
                        verify_no_lookahead)
from engine.strategy_base import Signal, StrategyBase  # noqa: E402
from strategies.core_post_earnings import \
    CorePostEarningsContinuation  # noqa: E402

DATA = ROOT / "data"
CFG = ROOT / "config" / "strategies" / "core_post_earnings.yaml"

_results: list[tuple[str, bool, str]] = []


def check(name, fn):
    try:
        fn()
        _results.append((name, True, ""))
    except Exception as exc:  # noqa: BLE001
        _results.append((name, False, f"{type(exc).__name__}: {exc}"))
        traceback.print_exc()


def expect_raises(exc_type, fn, contains=""):
    try:
        fn()
    except exc_type as exc:
        if contains and contains.lower() not in str(exc).lower():
            raise AssertionError(f"message {str(exc)!r} lacks {contains!r}")
        return
    raise AssertionError(f"expected {exc_type.__name__}, nothing raised")


def _cfg(**over):
    c = BacktestConfig.from_yaml(CFG)
    if not over:
        return c
    import copy
    d = copy.deepcopy(c.__dict__)
    d.update(over)
    return BacktestConfig(**d)


def _bars(ticker="AAPL"):
    return DataLoader(DATA).load(ticker)


def _engine(ticker="AAPL"):
    c = _cfg()
    return PointInTimeEngine(_bars(ticker), ticker,
                             atr_period=c.signal.atr_period,
                             volume_window=c.signal.volume_lookback_sessions)


# ------------------------------------------------- layer 1: structural

def t_prior_excludes_current_session():
    eng = _engine()
    s = eng.sessions[30]
    v = eng.view(s, eng.decision_ts(s, dt.time(9, 35)))
    assert s not in set(v.prior.daily.index), "today leaked into prior sessions"
    assert v.prior.daily.index.max() < s
    assert v.prior.slot_volume.index.max() < s


def t_today_stops_before_decision():
    """The decision bar's OHLC must be absent; only its open is exposed."""
    eng = _engine()
    s = eng.sessions[30]
    ts = eng.decision_ts(s, dt.time(9, 35))
    v = eng.view(s, ts)
    assert v.today.index.max() < ts, "view contains the decision bar itself"
    assert v.bar_at(5) is None, "minute 5 is the decision bar and must be hidden"
    assert v.today["minutes_from_open"].max() == 4, \
        v.today["minutes_from_open"].max()
    assert np.isfinite(v.entry_open), "entry open should still be available"


def t_entry_open_matches_raw_bar():
    eng = _engine()
    bars = _bars()
    s = eng.sessions[30]
    ts = eng.decision_ts(s, dt.time(9, 35))
    v = eng.view(s, ts)
    assert abs(v.entry_open - float(bars.loc[ts, "open"])) < 1e-12


def t_atr_uses_prior_sessions_only():
    """Recompute the ATR by hand from completed sessions and compare."""
    eng = _engine()
    p = eng.atr_period
    i = p + 5
    s = eng.sessions[i]
    v = eng.view(s, eng.decision_ts(s, dt.time(9, 35)))

    d = eng.daily.iloc[:i]                      # strictly before session i
    pc = d["close"].shift(1)
    tr = pd.concat([d["high"] - d["low"],
                    (d["high"] - pc).abs(),
                    (d["low"] - pc).abs()], axis=1).max(axis=1)
    want = float(tr.iloc[-p:].mean())
    assert abs(v.prior.atr(p) - want) < 1e-9, (v.prior.atr(p), want)


def t_atr_is_nan_before_full_window():
    eng = _engine()
    s = eng.sessions[3]
    v = eng.view(s, eng.decision_ts(s, dt.time(9, 35)))
    assert np.isnan(v.prior.atr(eng.atr_period)), \
        "a partial ATR window must be NaN, not a partial estimate"


def t_volume_baseline_excludes_today():
    eng = _engine()
    w = 20
    i = w + 5
    s = eng.sessions[i]
    v = eng.view(s, eng.decision_ts(s, dt.time(9, 35)))
    got = v.prior.same_slot_mean_volume(range(0, 5), w)

    grid = eng.slot_volume.iloc[:i][[0, 1, 2, 3, 4]].sum(axis=1)
    want = float(grid.iloc[-w:].mean())
    assert abs(got - want) < 1e-6, (got, want)

    # And it must not equal a version that includes today.
    with_today = float(eng.slot_volume.iloc[:i + 1][[0, 1, 2, 3, 4]]
                       .sum(axis=1).iloc[-w:].mean())
    assert abs(got - with_today) > 1e-9, "baseline appears to include today"


def t_volume_baseline_nan_before_window():
    eng = _engine()
    s = eng.sessions[5]
    v = eng.view(s, eng.decision_ts(s, dt.time(9, 35)))
    assert np.isnan(v.prior.same_slot_mean_volume(range(0, 5), 20))


def t_view_refuses_rolling():
    eng = _engine()
    s = eng.sessions[30]
    v = eng.view(s, eng.decision_ts(s, dt.time(9, 35)))
    expect_raises(LookAheadError, lambda: v.rolling, "shifted by construction")
    expect_raises(LookAheadError, lambda: v.ewm, "shifted by construction")


def t_partial_candle_returns_none():
    """A candle missing bars must not be silently aggregated."""
    bars = _bars()
    s = list(bars["session_date"].unique())[30]
    day = bars[bars["session_date"] == s]
    hole = day[day["minutes_from_open"] == 2].index
    punched = bars.drop(index=hole)
    eng = PointInTimeEngine(punched, "AAPL")
    v = eng.view(s, eng.decision_ts(s, dt.time(9, 35)))
    assert v.candle(0, 4) is None, "4 bars were aggregated as a 5-minute candle"


def t_shifted_rolling_mean_is_shifted():
    s = pd.Series(np.arange(1, 21, dtype=float))
    out = shifted_rolling_mean(s, 5)
    assert np.isnan(out.iloc[4]), "row 4 needs 5 prior observations, has 4"
    assert abs(out.iloc[5] - s.iloc[0:5].mean()) < 1e-12
    probe = s.copy()
    probe.iloc[10] = 999.0
    assert abs(shifted_rolling_mean(probe, 5).iloc[10] - out.iloc[10]) < 1e-12


def t_engine_self_check_passes():
    _engine().self_check()


# ----------------------------------------------------- layer 2: source audit

class _CheatsWithRolling(StrategyBase):
    def evaluate(self, view):
        v = view.today["volume"].rolling(20).mean()      # banned
        return None


class _CheatsWithNegativeShift(StrategyBase):
    def evaluate(self, view):
        v = view.today["close"].shift(-1)                # banned
        return None


class _Clean(StrategyBase):
    def evaluate(self, view):
        return None


def t_audit_rejects_rolling():
    expect_raises(LookAheadError, lambda: _CheatsWithRolling(_cfg()), "rolling")


def t_audit_rejects_negative_shift():
    expect_raises(LookAheadError,
                  lambda: _CheatsWithNegativeShift(_cfg()), "negative")


def t_audit_passes_clean_strategy():
    _Clean(_cfg())
    assert audit_source(CorePostEarningsContinuation) == []


def t_audit_opt_out_is_explicit():
    class _OptedOut(StrategyBase):
        ALLOW_RAW_WINDOWING = True

        def evaluate(self, view):
            return view.today["volume"].rolling(5).mean() and None
    _OptedOut(_cfg())          # must not raise


# --------------------------------------------- layer 3: behavioural proof

def t_no_lookahead_behavioural():
    strat = CorePostEarningsContinuation(_cfg())
    out = verify_no_lookahead(strat, _bars(), "AAPL")
    assert len(out) > 0, "no sessions probed"
    assert bool(out["identical"].all())


class _TimeTraveller(StrategyBase):
    """Reaches around the view to a frame captured at construction."""
    ALLOW_RAW_WINDOWING = True

    def __init__(self, config, future: pd.DataFrame):
        super().__init__(config)
        self.future = future

    def evaluate(self, view):
        later = self.future[(self.future["session_date"] == view.session)
                            & (self.future.index > view.decision_ts)]
        if later.empty or not np.isfinite(view.entry_open):
            return None
        atr = view.prior.atr(self.config.signal.atr_period)
        if not np.isfinite(atr) or atr <= 0:
            return None
        # Peek: trade the direction that will actually have worked.
        end = float(later["close"].iloc[min(59, len(later) - 1)])
        direction = 1 if end > view.entry_open else -1
        return Signal(ticker=view.ticker, session=view.session,
                      decision_ts=view.decision_ts, direction=direction,
                      entry_ts=view.decision_ts, entry_price=view.entry_open,
                      risk_unit=atr,
                      planned_exit_ts=view.decision_ts + pd.Timedelta(minutes=60))


def t_behavioural_catches_a_cheat():
    """The proof that the proof works.

    The factory form is the one with teeth: the cheat captures a frame
    at construction, so the checker must REBUILD it from truncated data
    to see the leak.
    """
    bars = _bars()
    cfg = _cfg()
    expect_raises(LookAheadError,
                  lambda: verify_no_lookahead(
                      lambda b: _TimeTraveller(cfg, b), bars, "AAPL"),
                  "changed when future bars were removed")


def t_instance_form_misses_captured_state():
    """Documents the known blind spot rather than pretending it is closed.

    Passed an INSTANCE, the checker cannot truncate a frame the strategy
    captured beforehand, so the same cheat slips through. This asserts
    that limitation so it stays visible, and so anyone who later closes
    it will see this test fail and update the docs.
    """
    bars = _bars()
    strat = _TimeTraveller(_cfg(), bars)
    out = verify_no_lookahead(strat, bars, "AAPL")
    assert bool(out["identical"].all()), (
        "instance form unexpectedly caught the cheat -- if the checker was "
        "strengthened, update verify_no_lookahead's docstring and drop this "
        "test")


# ------------------------------------------------------------- signal object

def t_signal_rejects_bad_risk_unit():
    ts = pd.Timestamp("2025-11-03 14:35", tz="UTC")
    expect_raises(ValueError, lambda: Signal(
        ticker="X", session=dt.date(2025, 11, 3), decision_ts=ts, direction=1,
        entry_ts=ts, entry_price=100.0, risk_unit=0.0,
        planned_exit_ts=ts + pd.Timedelta(minutes=60)), "risk_unit")


def t_signal_rejects_entry_before_decision():
    ts = pd.Timestamp("2025-11-03 14:35", tz="UTC")
    expect_raises(ValueError, lambda: Signal(
        ticker="X", session=dt.date(2025, 11, 3), decision_ts=ts, direction=1,
        entry_ts=ts - pd.Timedelta(minutes=1), entry_price=100.0,
        risk_unit=1.0, planned_exit_ts=ts + pd.Timedelta(minutes=60)),
        "precedes decision")


def t_signal_rejects_zero_direction():
    ts = pd.Timestamp("2025-11-03 14:35", tz="UTC")
    expect_raises(ValueError, lambda: Signal(
        ticker="X", session=dt.date(2025, 11, 3), decision_ts=ts, direction=0,
        entry_ts=ts, entry_price=100.0, risk_unit=1.0,
        planned_exit_ts=ts + pd.Timedelta(minutes=60)), "direction")


# ------------------------------------------------------------ end-to-end run

def t_strategy_runs_and_respects_dst():
    strat = CorePostEarningsContinuation(_cfg())
    frames = {t: DataLoader(DATA).load(t) for t in ("AAPL", "MSFT")}
    df = strat.run_many(frames)
    assert len(df) > 0, "no signals produced on the fixtures"

    from engine.calendar import to_exchange_tz
    local = to_exchange_tz(pd.DatetimeIndex(df["entry_ts"]))
    assert set(t.strftime("%H:%M") for t in local.time) == {"09:35"}, \
        "entry did not land on 09:35 local in every session"
    utc_hours = sorted({ts.hour for ts in pd.DatetimeIndex(df["entry_ts"])})
    assert utc_hours == [13, 14], f"expected both DST regimes, got {utc_hours}"

    assert set(df["direction"].unique()) <= {-1, 1}
    assert (df["entry_price"] > 0).all()
    assert (df["risk_unit"] > 0).all()
    assert (df["volume_ratio"] > _cfg().signal.volume_ratio_min).all()
    assert (df["body_over_range"] > _cfg().signal.doji_max_body_ratio).all()
    # Continuation: sign of the gap must equal the traded direction.
    assert ((df["gap_pct"] > 0) == (df["direction"] > 0)).all()


def t_hold_minutes_respected():
    strat = CorePostEarningsContinuation(_cfg())
    df = strat.run_many({"AAPL": _bars()})
    delta = (pd.DatetimeIndex(df["planned_exit_ts"])
             - pd.DatetimeIndex(df["entry_ts"]))
    assert set(delta.unique()) == {pd.Timedelta(minutes=60)}


def t_long_only_filters_shorts():
    import copy
    base = BacktestConfig.from_yaml(CFG)
    d = copy.deepcopy(base.__dict__)
    d["direction"] = "long_only"
    strat = CorePostEarningsContinuation(BacktestConfig(**d))
    df = strat.run_many({"AAPL": _bars()})
    if len(df):
        assert set(df["direction"].unique()) == {1}


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
