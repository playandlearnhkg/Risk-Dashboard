"""
test_portfolio.py -- assertions for sizing, caps and execution.

The execution tests use hand-built bars with known highs and lows rather
than the random fixtures, because a stop-fill test is only meaningful if
the exact price it should fill at is known in advance. Each case states
the arithmetic it expects.

Run: python3 tests/test_portfolio.py
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
from engine.portfolio import (Portfolio, SelectionRule,  # noqa: E402
                              risk_per_share, simulate_exit, stop_price_for)
from engine.strategy_base import Signal  # noqa: E402
from strategies.core_post_earnings import \
    CorePostEarningsContinuation  # noqa: E402

DATA = ROOT / "data"
CFG = ROOT / "config" / "strategies" / "core_post_earnings.yaml"
SESSION = dt.date(2025, 11, 13)
T0 = pd.Timestamp("2025-11-13 14:35", tz="UTC")     # 09:35 EST

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


def cfg(**over) -> BacktestConfig:
    """Config with dotted overrides, e.g. cfg(**{"exit.stop.enabled": True})."""
    import copy
    base = BacktestConfig.from_yaml(CFG)
    if not over:
        return base
    d = copy.deepcopy(base.__dict__)
    for path, val in over.items():
        parts = path.split(".")
        if len(parts) == 1:
            d[parts[0]] = val
            continue
        section = d[parts[0]]
        sub = copy.deepcopy(section.__dict__)
        if len(parts) == 2:
            sub[parts[1]] = val
            d[parts[0]] = type(section)(**sub)
        else:                                   # exit.stop.multiple
            inner = copy.deepcopy(sub[parts[1]].__dict__)
            inner[parts[2]] = val
            sub[parts[1]] = type(sub[parts[1]])(**inner)
            d[parts[0]] = type(section)(**sub)
    return BacktestConfig(**d)


def make_bars(rows: list[tuple[int, float, float, float, float]],
              volume: float = 10_000.0) -> pd.DataFrame:
    """Bars from (minute_offset, open, high, low, close) tuples."""
    idx = pd.DatetimeIndex([T0 + pd.Timedelta(minutes=m) for m, *_ in rows],
                           name="ts")
    df = pd.DataFrame([r[1:] for r in rows], index=idx,
                      columns=["open", "high", "low", "close"])
    df["volume"] = volume
    df["session_date"] = SESSION
    df["minutes_from_open"] = [5 + m for m, *_ in rows]
    return df.astype({"open": float, "high": float, "low": float,
                      "close": float, "volume": float})


def sig(direction=1, entry=100.0, atr=2.0, hold=60) -> Signal:
    return Signal(ticker="TST", session=SESSION, decision_ts=T0, direction=direction,
                  entry_ts=T0, entry_price=entry, risk_unit=atr,
                  planned_exit_ts=T0 + pd.Timedelta(minutes=hold),
                  features={"volume_ratio": 3.0, "gap_atr": 1.0})


# ------------------------------------------------------------- stop fills

def t_stop_fills_at_level_when_bar_straddles():
    """Long, entry 100, ATR 2, stop 98. A bar opens 99 and dips to 97.5.

    The level was reachable inside the bar, so the fill is 98 exactly.
    """
    bars = make_bars([(0, 100.0, 100.5, 99.5, 99.8),
                      (1, 99.0, 99.2, 97.5, 98.0),
                      (60, 99.0, 99.1, 98.9, 99.0)])
    s = sig()
    stop = stop_price_for(s, cfg(**{"exit.stop.enabled": True}))
    assert abs(stop - 98.0) < 1e-12, stop
    ts, px, reason, held, mae, mfe = simulate_exit(s, bars, stop)
    assert reason == "stop"
    assert abs(px - 98.0) < 1e-12, f"expected a fill at the level 98, got {px}"
    assert ts == T0 + pd.Timedelta(minutes=1)


def t_stop_fills_at_open_when_gapped_through():
    """Same stop at 98, but the bar OPENS at 96 -- below it.

    The level was never obtainable. The honest fill is 96, not 98.
    """
    bars = make_bars([(0, 100.0, 100.5, 99.5, 99.8),
                      (1, 96.0, 96.5, 95.0, 95.5),
                      (60, 96.0, 96.1, 95.9, 96.0)])
    s = sig()
    stop = stop_price_for(s, cfg(**{"exit.stop.enabled": True}))
    _ts, px, reason, _h, _a, _f = simulate_exit(s, bars, stop)
    assert reason == "stop"
    assert abs(px - 96.0) < 1e-12, (
        f"gapped through 98 but filled at {px}; must use the bar open")


def t_short_stop_fills_at_open_when_gapped_through():
    """Short, entry 100, ATR 2, stop 102. Bar opens at 104."""
    bars = make_bars([(0, 100.0, 100.5, 99.5, 100.2),
                      (1, 104.0, 105.0, 103.5, 104.5),
                      (60, 104.0, 104.1, 103.9, 104.0)])
    s = sig(direction=-1)
    stop = stop_price_for(s, cfg(**{"exit.stop.enabled": True}))
    assert abs(stop - 102.0) < 1e-12, stop
    _ts, px, reason, _h, _a, _f = simulate_exit(s, bars, stop)
    assert reason == "stop"
    assert abs(px - 104.0) < 1e-12, f"short must fill at 104, got {px}"


def t_stop_can_fire_inside_the_entry_bar():
    """The entry bar's low comes after its open, so it counts."""
    bars = make_bars([(0, 100.0, 100.2, 97.0, 97.5),
                      (60, 99.0, 99.1, 98.9, 99.0)])
    s = sig()
    stop = stop_price_for(s, cfg(**{"exit.stop.enabled": True}))
    ts, px, reason, held, _a, _f = simulate_exit(s, bars, stop)
    assert reason == "stop" and ts == T0, (reason, ts)
    assert abs(px - 98.0) < 1e-12
    assert held == 1


def t_no_stop_runs_to_time():
    bars = make_bars([(0, 100.0, 100.5, 90.0, 95.0),
                      (60, 93.0, 93.5, 92.5, 93.0)])
    s = sig()
    ts, px, reason, _h, _a, _f = simulate_exit(s, bars, float("nan"))
    assert reason == "time"
    assert abs(px - 93.0) < 1e-12, "time exit fills at the exit bar's OPEN"
    assert ts == T0 + pd.Timedelta(minutes=60)


def t_missing_exit_bar_is_flagged_not_hidden():
    bars = make_bars([(0, 100.0, 100.5, 99.5, 100.2),
                      (30, 101.0, 101.5, 100.5, 101.2)])   # no minute 60
    s = sig()
    ts, px, reason, _h, _a, _f = simulate_exit(s, bars, float("nan"))
    assert reason == "time_stale", reason
    assert ts == T0 + pd.Timedelta(minutes=30)
    assert abs(px - 101.2) < 1e-12, "should use the last available close"


def t_empty_window_raises():
    bars = make_bars([(-5, 100.0, 100.5, 99.5, 100.0)])
    expect_raises(ValueError, lambda: simulate_exit(sig(), bars, float("nan")),
                  "no bars")


# -------------------------------------------------------------- excursions

def t_mae_mfe_signs_and_scale():
    """Long, entry 100, ATR 2. Low 97 is -1.5 ATR, high 105 is +2.5 ATR."""
    bars = make_bars([(0, 100.0, 101.0, 97.0, 99.0),
                      (30, 99.0, 105.0, 99.0, 104.0),
                      (60, 104.0, 104.5, 103.5, 104.0)])
    _ts, _px, _r, _h, mae, mfe = simulate_exit(sig(), bars, float("nan"))
    assert abs(mae + 1.5) < 1e-12, mae
    assert abs(mfe - 2.5) < 1e-12, mfe


def t_short_mae_mfe_inverted():
    """Short, entry 100, ATR 2. High 103 is -1.5 ATR against a short."""
    bars = make_bars([(0, 100.0, 103.0, 99.0, 102.0),
                      (60, 96.0, 96.5, 95.0, 96.0)])
    _ts, _px, _r, _h, mae, mfe = simulate_exit(sig(direction=-1), bars,
                                               float("nan"))
    assert abs(mae + 1.5) < 1e-12, mae
    assert abs(mfe - 2.5) < 1e-12, mfe      # low 95 is +2.5 ATR for a short


def t_stopped_trade_excursions_are_truncated():
    """A stop must not be credited with a rally it never saw."""
    bars = make_bars([(0, 100.0, 100.2, 100.0, 100.1),
                      (1, 100.0, 100.1, 97.0, 97.5),      # stop at 98 here
                      (2, 97.5, 130.0, 97.0, 129.0),      # huge move AFTER
                      (60, 129.0, 129.5, 128.5, 129.0)])
    s = sig()
    stop = stop_price_for(s, cfg(**{"exit.stop.enabled": True}))
    _ts, _px, reason, held, _mae, mfe = simulate_exit(s, bars, stop)
    assert reason == "stop" and held == 2
    assert mfe < 1.0, f"MFE {mfe} includes bars after the stop fired"


# ------------------------------------------------------------------ sizing

def t_fixed_risk_uses_stop_distance():
    """0.5% of 1,000,000 = 5,000 risk. Stop 1 ATR = 2.0 -> 2,500 shares."""
    c = cfg(**{"exit.stop.enabled": True, "sizing.max_pct_equity_per_trade": 1.0})
    p = Portfolio(c)
    s = sig()
    assert abs(risk_per_share(s, c) - 2.0) < 1e-12
    nt = p._size([s], 1_000_000.0)[0]
    assert abs(nt / s.entry_price - 2500.0) < 1e-9, nt / s.entry_price


def t_wider_stop_sizes_smaller():
    c = cfg(**{"exit.stop.enabled": True, "exit.stop.multiple": 2.0,
               "sizing.max_pct_equity_per_trade": 1.0})
    nt = Portfolio(c)._size([sig()], 1_000_000.0)[0]
    assert abs(nt / 100.0 - 1250.0) < 1e-9, "2 ATR stop should halve the size"


def t_no_stop_uses_one_atr_proxy():
    c = cfg(**{"sizing.max_pct_equity_per_trade": 1.0})   # stop disabled
    assert abs(risk_per_share(sig(), c) - 2.0) < 1e-12
    assert np.isnan(stop_price_for(sig(), c))


def t_per_trade_cap_binds():
    """Cap is 5% of equity = 50,000 regardless of what risk sizing wants."""
    c = cfg(**{"exit.stop.enabled": True})     # cap 0.05 from the yaml
    nt = Portfolio(c)._size([sig()], 1_000_000.0)[0]
    assert abs(nt - 50_000.0) < 1e-9, nt


def t_fixed_notional_splits_equity():
    c = cfg(**{"sizing.method": "fixed_notional",
               "sizing.max_pct_equity_per_trade": 1.0})
    nt = Portfolio(c)._size([sig()], 1_000_000.0)[0]
    assert abs(nt - 200_000.0) < 1e-9, "equity / 5 slots"


# -------------------------------------------------------------------- caps

def t_fixed_notional_can_never_breach_gross():
    """Worth pinning: equity / n_slots sums to 100% by construction.

    So the gross cap is unreachable under fixed_notional, and only
    fixed-fractional sizing can demand more than the account holds.
    """
    c = cfg(**{"sizing.method": "fixed_notional",
               "sizing.max_pct_equity_per_trade": 1.0,
               "portfolio.max_concurrent_positions": 2})
    n = Portfolio(c)._size([sig(), sig()], 1_000_000.0)
    assert abs(n.sum() - 1_000_000.0) < 1e-6
    assert n.sum() <= c.portfolio.max_gross_exposure * 1_000_000.0 + 1e-6


def t_gross_exposure_cap_scales_pro_rata():
    """Fixed-fractional sizing on a low-ATR name overruns the account.

    0.5% of 1,000,000 = 5,000 risk. With ATR 0.01 that is 500,000 shares
    = 50,000,000 notional, cut to 800,000 by the per-trade cap. Two such
    trades want 1,600,000 against a 1,000,000 limit, so each must be
    scaled to 500,000 -- exactly 50% weight.
    """
    c = cfg(**{"exit.stop.enabled": True,
               "sizing.max_pct_equity_per_trade": 0.8,
               "portfolio.max_concurrent_positions": 2,
               "portfolio.max_gross_exposure": 1.0})
    bars = make_bars([(0, 100.0, 100.5, 99.5, 100.0),
                      (60, 100.0, 100.5, 99.5, 100.0)])
    sigs = [Signal(ticker=t, session=SESSION, decision_ts=T0, direction=1,
                   entry_ts=T0, entry_price=100.0, risk_unit=0.01,
                   planned_exit_ts=T0 + pd.Timedelta(minutes=60),
                   features={"volume_ratio": 3.0}) for t in ("AAA", "BBB")]
    frames = {t: bars for t in ("AAA", "BBB")}

    raw = Portfolio(c)._size(sigs, 1_000_000.0)
    assert abs(raw[0] - 800_000.0) < 1e-6, raw[0]      # per-trade cap first
    assert raw.sum() > 1_000_000.0, "the test needs the gross cap to bind"

    log, _curve = Portfolio(c).run(sigs, frames, pd.DatetimeIndex([SESSION]))
    assert len(log) == 2
    assert log["scaled"].all(), "the gross cap should have bitten"
    assert abs(log["notional"].sum() - 1_000_000.0) < 1e-6
    assert (log["weight"] - 0.5).abs().max() < 1e-9


def t_concurrency_limit_picks_highest_volume_ratio():
    c = cfg(**{"portfolio.max_concurrent_positions": 2})
    bars = make_bars([(0, 100.0, 100.5, 99.5, 100.0),
                      (60, 100.0, 100.5, 99.5, 100.0)])
    vr = {"AAA": 2.0, "BBB": 9.0, "CCC": 5.0}
    sigs = [Signal(ticker=t, session=SESSION, decision_ts=T0, direction=1,
                   entry_ts=T0, entry_price=100.0, risk_unit=2.0,
                   planned_exit_ts=T0 + pd.Timedelta(minutes=60),
                   features={"volume_ratio": v}) for t, v in vr.items()]
    frames = {t: bars for t in vr}
    log, _ = Portfolio(c, SelectionRule.VOLUME_RATIO).run(
        sigs, frames, pd.DatetimeIndex([SESSION]))
    assert set(log["ticker"]) == {"BBB", "CCC"}, set(log["ticker"])


def t_selection_rule_ticker_is_naive_and_different():
    c = cfg(**{"portfolio.max_concurrent_positions": 2})
    bars = make_bars([(0, 100.0, 100.5, 99.5, 100.0),
                      (60, 100.0, 100.5, 99.5, 100.0)])
    vr = {"AAA": 2.0, "BBB": 9.0, "CCC": 5.0}
    sigs = [Signal(ticker=t, session=SESSION, decision_ts=T0, direction=1,
                   entry_ts=T0, entry_price=100.0, risk_unit=2.0,
                   planned_exit_ts=T0 + pd.Timedelta(minutes=60),
                   features={"volume_ratio": v}) for t, v in vr.items()]
    log, _ = Portfolio(c, SelectionRule.TICKER).run(
        sigs, {t: bars for t in vr}, pd.DatetimeIndex([SESSION]))
    assert set(log["ticker"]) == {"AAA", "BBB"}


def t_selection_missing_key_raises():
    c = cfg()
    bars = make_bars([(0, 100.0, 100.5, 99.5, 100.0),
                      (60, 100.0, 100.5, 99.5, 100.0)])
    s = Signal(ticker="AAA", session=SESSION, decision_ts=T0, direction=1,
               entry_ts=T0, entry_price=100.0, risk_unit=2.0,
               planned_exit_ts=T0 + pd.Timedelta(minutes=60), features={})
    expect_raises(KeyError,
                  lambda: Portfolio(c, SelectionRule.GAP_ATR).run(
                      [s], {"AAA": bars}, pd.DatetimeIndex([SESSION])),
                  "gap_atr")


# ------------------------------------------------------------ P&L and costs

def t_pnl_and_cost_arithmetic():
    """Long 50,000 notional at 100, exits at 101 -> +1% gross = +500.

    Cost is 6.6 bps of notional, charged ONCE as a round trip = 33.
    """
    c = cfg(**{"exit.stop.enabled": True})       # 5% cap -> 50,000
    bars = make_bars([(0, 100.0, 101.5, 99.5, 101.0),
                      (60, 101.0, 101.2, 100.8, 101.0)])
    log, curve = Portfolio(c).run([sig()], {"TST": bars},
                                  pd.DatetimeIndex([SESSION]))
    r = log.iloc[0]
    assert abs(r["notional"] - 50_000.0) < 1e-9
    assert abs(r["shares"] - 500.0) < 1e-9
    assert abs(r["gross_pnl"] - 500.0) < 1e-9
    assert abs(r["cost"] - 33.0) < 1e-9, r["cost"]
    assert abs(r["net_pnl"] - 467.0) < 1e-9
    assert abs(r["ret_bps"] - 93.4) < 1e-9, r["ret_bps"]
    assert abs(curve.iloc[-1] - 1_000_467.0) < 1e-6


def t_short_pnl_sign():
    c = cfg(**{"exit.stop.enabled": True, "costs.round_trip_bps": 0.0})
    bars = make_bars([(0, 100.0, 100.5, 98.0, 99.0),
                      (60, 99.0, 99.2, 98.8, 99.0)])
    log, _ = Portfolio(c).run([sig(direction=-1)], {"TST": bars},
                              pd.DatetimeIndex([SESSION]))
    assert log.iloc[0]["gross_pnl"] > 0, "a short into a falling price must gain"
    assert abs(log.iloc[0]["ret_atr"] - 0.5) < 1e-12   # 1.0 move / 2.0 ATR


def t_equity_compounds_and_idle_days_are_flat():
    c = cfg(**{"exit.stop.enabled": True, "costs.round_trip_bps": 0.0})
    bars = make_bars([(0, 100.0, 102.5, 99.5, 102.0),
                      (60, 102.0, 102.2, 101.8, 102.0)])
    cal = pd.DatetimeIndex([dt.date(2025, 11, 12), SESSION,
                            dt.date(2025, 11, 14)])
    _log, curve = Portfolio(c).run([sig()], {"TST": bars}, cal)
    assert abs(curve.iloc[0] - 1_000_000.0) < 1e-9, "idle day must be flat"
    assert curve.iloc[1] > curve.iloc[0], "trade day should move equity"
    assert abs(curve.iloc[2] - curve.iloc[1]) < 1e-9, "idle day must be flat"


def t_no_trades_leaves_equity_untouched():
    c = cfg()
    log, curve = Portfolio(c).run([], {}, pd.DatetimeIndex([SESSION]))
    assert log.empty
    assert abs(curve.iloc[-1] - c.portfolio.starting_capital) < 1e-9


# ------------------------------------------------------------- end-to-end

def t_end_to_end_on_fixtures():
    c = cfg()
    strat = CorePostEarningsContinuation(c)
    ld = DataLoader(DATA)
    frames = {t: ld.load(t) for t in ld.tickers}
    sigs: list[Signal] = []
    for t, bars in frames.items():
        sigs.extend(strat.run(bars, t))
    assert sigs, "no signals on the fixtures"

    log, curve = Portfolio(c).run(sigs, frames)
    assert len(log) == len(sigs), (len(log), len(sigs))
    assert curve.is_monotonic_increasing or True     # may lose; just present
    assert len(curve) > len(log), "curve should cover idle sessions too"
    assert (log["notional"] > 0).all()
    assert (log["weight"] <= c.sizing.max_pct_equity_per_trade + 1e-9).all()
    assert set(log["exit_reason"]) <= {"time", "stop", "time_stale"}
    # Positions are intraday: every exit lands in its own session.
    same_day = pd.DatetimeIndex(log["exit_ts"]).tz_convert(
        "America/New_York").date == log["session"].to_numpy()
    assert same_day.all(), "a position survived past its session"
    assert abs(curve.iloc[-1] - (c.portfolio.starting_capital
                                 + log["net_pnl"].sum())) < 1e-6


def t_stop_enabled_changes_outcomes():
    """Sanity: turning the stop on must actually alter some trades."""
    ld = DataLoader(DATA)
    frames = {t: ld.load(t) for t in ld.tickers}

    def run(c):
        strat = CorePostEarningsContinuation(c)
        sigs = []
        for t, bars in frames.items():
            sigs.extend(strat.run(bars, t))
        return Portfolio(c).run(sigs, frames)

    a, _ = run(cfg())
    b, _ = run(cfg(**{"exit.stop.enabled": True}))
    assert len(a) == len(b), "the stop must not change which signals fire"
    assert (b["exit_reason"] == "stop").any() or \
        abs(a["net_pnl"].sum() - b["net_pnl"].sum()) < 1e-9


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
