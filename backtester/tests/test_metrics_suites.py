"""
test_metrics_suites.py -- assertions for metrics, robustness and capacity.

Most tests use a HAND-BUILT trade log with known arithmetic, because a
metric is only verified if the answer was known before the code ran.
The end-to-end tests then confirm the same functions survive real
Portfolio output.

Run: python3 tests/test_metrics_suites.py
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

from engine import capacity as CAP  # noqa: E402
from engine import metrics as M  # noqa: E402
from engine import robustness as R  # noqa: E402
from engine import validation as VAL  # noqa: E402
from engine.config import BacktestConfig, ConfigError  # noqa: E402
from engine.data_loader import DataLoader  # noqa: E402
from engine.portfolio import Portfolio  # noqa: E402
from strategies.core_post_earnings import \
    CorePostEarningsContinuation  # noqa: E402

DATA = ROOT / "data"
CFG = ROOT / "config" / "strategies" / "core_post_earnings.yaml"
CAPITAL = 1_000_000.0

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


def toy(pnls, dates=None, sides=None, notional=100_000.0) -> pd.DataFrame:
    """A standard-shaped trade log with P&L chosen by hand."""
    n = len(pnls)
    # date_range, not date(2024, 1, 2 + i): the latter overflows the month
    # as soon as a test wants more than 29 trades.
    dates = dates or [d.date() for d in
                      pd.date_range("2024-01-02", periods=n, freq="D")]
    sides = sides or ["LONG"] * n
    return pd.DataFrame({
        "trade_id": [f"T{i:05d}" for i in range(1, n + 1)],
        "ticker": [f"TK{i % 3}" for i in range(n)],
        "date": dates,
        "side": sides,
        "entry_time": [pd.Timestamp(f"{d} 14:35", tz="UTC") for d in dates],
        "exit_time": [pd.Timestamp(f"{d} 15:35", tz="UTC") for d in dates],
        "entry_price": 100.0, "exit_price": 101.0,
        "pnl": [float(x) for x in pnls],
        "pnl_bps": [float(x) / notional * 1e4 for x in pnls],
        "mae_atr": -0.2, "mfe_atr": 0.3,
        "gap_atr": 1.0, "volume_ratio": 3.0,
        "notional": notional, "gross_pnl": [float(x) + 66.0 for x in pnls],
        "ret_atr": [float(x) / notional * 10 for x in pnls],
        "exit_reason": "time",
    })


# ------------------------------------------------------------------ metrics

def t_equity_stats_arithmetic():
    """1,000,000 -> 1,210,000 over exactly one year is +21% and CAGR 21%."""
    eq = pd.Series(np.linspace(1_000_000, 1_210_000, M.TRADING_DAYS),
                   index=pd.date_range("2024-01-01", periods=M.TRADING_DAYS))
    s = M.equity_stats(eq, CAPITAL)
    assert abs(s["total_return"] - 0.21) < 1e-9, s["total_return"]
    assert abs(s["cagr"] - 0.21) < 1e-6, s["cagr"]
    assert s["max_dd"] == 0.0, "a monotone curve has no drawdown"


def t_drawdown_arithmetic():
    eq = pd.Series([100.0, 120.0, 90.0, 150.0])
    dd = M.drawdown(eq)
    assert abs(dd.iloc[2] - (-0.25)) < 1e-12, dd.iloc[2]   # 90/120 - 1
    assert dd.iloc[3] == 0.0


def t_trade_stats_arithmetic():
    """Wins 100, 200, 300; losses -50, -150. Known answers throughout."""
    t = toy([100, 200, 300, -50, -150])
    s = M.trade_stats(t)
    assert s["n_trades"] == 5
    assert abs(s["win_rate"] - 0.6) < 1e-12
    assert abs(s["avg_win"] - 200.0) < 1e-12
    assert abs(s["avg_loss"] - 100.0) < 1e-12
    assert abs(s["payoff_ratio"] - 2.0) < 1e-12
    assert abs(s["profit_factor"] - 3.0) < 1e-12       # 600 / 200
    assert abs(s["expectancy"] - 80.0) < 1e-12         # 400 / 5


def t_profit_factor_no_losses():
    s = M.trade_stats(toy([10, 20]))
    assert np.isnan(s["profit_factor"]), "no losses means no finite ratio"


def t_distribution_percentiles_and_winsor():
    """One extreme value must move raw kurtosis and not the winsorised one."""
    base = list(np.linspace(-100, 100, 200))
    clean = M.distribution_stats(toy(base))
    spiked = M.distribution_stats(toy(base + [1_000_000.0]))
    assert spiked["exkurt_raw"] > clean["exkurt_raw"] + 10, \
        "raw kurtosis should react violently to the outlier"
    assert abs(spiked["exkurt_wins"] - clean["exkurt_wins"]) < 5, \
        "winsorised kurtosis should barely move"


def t_tail_counts_use_atr():
    t = toy([0, 0, 0, 0])
    t["ret_atr"] = [-0.6, -1.2, 0.5, -0.4]
    d = M.distribution_stats(t)
    assert abs(d["pct_loss_gt_0_5atr"] - 0.5) < 1e-12    # -0.6 and -1.2
    assert abs(d["pct_loss_gt_1atr"] - 0.25) < 1e-12     # -1.2 only


def t_rebuild_equity_compounds_by_day():
    t = toy([100, 200, -50])
    eq = M.rebuild_equity(t, CAPITAL)
    assert abs(eq.iloc[-1] - (CAPITAL + 250)) < 1e-9
    assert len(eq) == 3


def t_same_day_trades_collapse_to_one_step():
    d = dt.date(2024, 3, 1)
    eq = M.rebuild_equity(toy([100, 200], dates=[d, d]), CAPITAL)
    assert len(eq) == 1, "two trades on one session are one equity step"
    assert abs(eq.iloc[0] - (CAPITAL + 300)) < 1e-9


def t_period_filter_rebases_cagr():
    """THE important one.

    A subset must be annualised over its own window. Charging it for the
    years before its first trade was worth 7 percentage points in the
    research.
    """
    early = [dt.date(2020, 1, 2 + i) for i in range(3)]
    late = [dt.date(2024, 1, 2 + i) for i in range(3)]
    t = toy([100] * 6, dates=early + late)
    full = M.evaluate(t, CAPITAL, "full")
    sub = M.evaluate(t, CAPITAL, "sub", start="2024-01-01")
    assert sub.overall["n_trades"] == 3
    assert abs(sub.equity.iloc[-1] - (CAPITAL + 300)) < 1e-9, \
        "subset equity must start from capital, not carry the earlier P&L"
    assert sub.overall["cagr"] > full.overall["cagr"], \
        "the subset traded the same P&L in fewer days; its CAGR must be higher"


def t_reprice_is_exact_per_trade():
    t = toy([100, -200])                  # gross = pnl + 66 by construction
    r = M.reprice(t, 0.0)
    assert abs(r["pnl"].iloc[0] - 166.0) < 1e-9, "zero cost returns gross"
    r15 = M.reprice(t, 15.0)
    expected = t["gross_pnl"].iloc[0] - 100_000.0 * 15 / 1e4
    assert abs(r15["pnl"].iloc[0] - expected) < 1e-9


def t_reprice_needs_gross():
    t = toy([100]).drop(columns=["gross_pnl"])
    expect_raises(KeyError, lambda: M.reprice(t, 10.0), "gross_pnl")


def t_by_side_shares_sum_to_one():
    t = toy([300, -100], sides=["LONG", "SHORT"])
    m = M.evaluate(t, CAPITAL, "x")
    assert abs(m.by_side["pct_of_total_pnl"].sum() - 1.0) < 1e-9


def t_empty_trade_log_is_safe():
    m = M.evaluate(toy([]).iloc[:0], CAPITAL, "empty")
    assert m.overall["n_trades"] == 0 or np.isnan(m.overall["n_trades"])
    assert m.summary()          # must not raise


def t_standard_columns_present():
    ld = DataLoader(DATA)
    frames = {t: ld.load(t) for t in ld.tickers}
    cfg = BacktestConfig.from_yaml(CFG)
    sigs = CorePostEarningsContinuation(cfg).run_many_signals(frames)
    log, _ = Portfolio(cfg).run(sigs, frames)
    std = M.standard_trade_log(log)
    for c in M.STANDARD_COLUMNS:
        assert c in std.columns, c
    assert set(std["side"].unique()) <= {"LONG", "SHORT"}


def t_metrics_reconciles_with_portfolio():
    ld = DataLoader(DATA)
    frames = {t: ld.load(t) for t in ld.tickers}
    cfg = BacktestConfig.from_yaml(CFG)
    sigs = CorePostEarningsContinuation(cfg).run_many_signals(frames)
    log, curve = Portfolio(cfg).run(sigs, frames)
    m = M.evaluate(log, CAPITAL, "core", equity=curve)
    assert abs(curve.iloc[-1] - (CAPITAL + m.trades["pnl"].sum())) < 1e-6
    assert m.overall["n_trades"] == len(log)


# --------------------------------------------------------------- robustness

def t_config_replace_is_deep_and_pure():
    c = BacktestConfig.from_yaml(CFG)
    d = c.replace(**{"exit.stop.multiple": 2.0, "costs.round_trip_bps": 15.0})
    assert d.exit.stop.multiple == 2.0 and d.costs.round_trip_bps == 15.0
    assert c.exit.stop.multiple == 1.0 and c.costs.round_trip_bps == 6.6, \
        "replace must not mutate the original"


def t_config_replace_rejects_bad_paths():
    c = BacktestConfig.from_yaml(CFG)
    expect_raises(ConfigError, lambda: c.replace(**{"exit.nope": 1}), "not a field")
    expect_raises(ConfigError, lambda: c.replace(**{"nope.x": 1}), "no section")


def t_config_replace_revalidates():
    """A variant must not reach a state the YAML loader would refuse."""
    c = BacktestConfig.from_yaml(CFG)
    expect_raises(ConfigError,
                  lambda: c.replace(**{"exit.hold_minutes": 400}),
                  "one regular session")


def _suite_inputs():
    ld = DataLoader(DATA)
    frames = {t: ld.load(t) for t in ld.tickers}
    cfg = BacktestConfig.from_yaml(CFG)
    sigs = CorePostEarningsContinuation(cfg).run_many_signals(frames)
    return cfg, sigs, frames


def t_cost_stress_is_monotone():
    cfg, sigs, frames = _suite_inputs()
    t = R.cost_stress(cfg, sigs, frames, [6.6, 15.0, 25.0])
    assert len(t) == 3
    e = t["expectancy_bps"].to_numpy()
    assert np.all(np.diff(e) < 0), "higher cost must lower expectancy"
    # 15 - 6.6 = 8.4 bps of extra cost, straight off expectancy.
    assert abs((e[0] - e[1]) - 8.4) < 0.2, (e[0], e[1])


def t_period_stability_covers_all_periods():
    cfg, sigs, frames = _suite_inputs()
    t = R.period_stability(cfg, sigs, frames)
    assert list(t["case"]) == [p[0] for p in R.DEFAULT_PERIODS]


def t_position_limits_are_monotone_in_trades():
    cfg, sigs, frames = _suite_inputs()
    t = R.position_limits(cfg, sigs, frames, [1, 3, 8])
    n = t["n_trades"].to_numpy()
    assert np.all(np.diff(n) >= 0), "a larger cap cannot take fewer trades"
    assert (t["pct_signals_taken"] <= 1.0 + 1e-9).all()


def t_stop_comparison_keeps_trade_count():
    """A stop changes exits, never which signals fire."""
    cfg, sigs, frames = _suite_inputs()
    t = R.stop_comparison(cfg, sigs, frames, (1.0, 2.0))
    assert t["n_trades"].nunique() == 1, t["n_trades"].tolist()


def t_long_short_books_reconcile_in_count():
    cfg, sigs, frames = _suite_inputs()
    t = R.long_short(cfg, sigs, frames)
    combined = t[t["book"] == "combined"].iloc[0]["n_trades"]
    within = t[t["book"] == "within"]["n_trades"].sum()
    assert combined == within, (combined, within)


def t_dashboard_renders():
    cfg, sigs, frames = _suite_inputs()
    txt = R.dashboard(R.run_suite(cfg, sigs, frames), cfg)
    assert "ROBUSTNESS SUITE" in txt and "FLAGS" in txt


# ----------------------------------------------------------------- capacity

def t_kept_ratio_guards_negative_base():
    """A friction can only subtract; a ratio > 1 means a bad denominator."""
    assert np.isnan(CAP._kept(-1081.0, -881.0)), \
        "dividing by a loss inverts the meaning and must be refused"
    assert np.isnan(CAP._kept(50.0, 0.0))
    assert abs(CAP._kept(80.0, 100.0) - 0.8) < 1e-12


def t_borrow_charges_shorts_only():
    cfg, sigs, frames = _suite_inputs()
    t = CAP.borrow_stress(cfg, sigs, frames, [0.0, 10.0])
    assert abs(t.iloc[0]["borrow_cost_paid"]) < 1e-12
    assert t.iloc[1]["borrow_cost_paid"] > 0
    assert t.iloc[1]["pnl_change"] < 0, "borrow can only reduce P&L"


def t_borrow_arithmetic():
    """10 bps on short notional is exactly notional * 10/1e4."""
    cfg, sigs, frames = _suite_inputs()
    m = CAP._base(cfg, sigs, frames)
    shorts = m.trades[m.trades["side"] == "SHORT"]
    want = float(shorts["notional"].sum() * 10.0 / 1e4)
    t = CAP.borrow_stress(cfg, sigs, frames, [10.0])
    assert abs(t.iloc[0]["borrow_cost_paid"] - want) < 1e-6


def t_slippage_moves_entry_adversely():
    cfg, sigs, frames = _suite_inputs()
    slipped = CAP._slip_signals(sigs, 0.1)
    for a, b in zip(sigs, slipped):
        moved = (b.entry_price - a.entry_price) * a.direction
        assert moved > 0, "entry must move against the position"
        assert abs(moved - 0.1 * a.risk_unit) < 1e-9


def t_slippage_only_hurts():
    cfg, sigs, frames = _suite_inputs()
    t = CAP.slippage_stress(cfg, sigs, frames, [0.0, 0.1, 0.2])
    e = t["expectancy_bps"].to_numpy()
    assert np.all(np.diff(e) < 0), "more slippage must lower expectancy"


def t_delay_whole_minutes_are_exact():
    cfg, sigs, frames = _suite_inputs()
    out, interp = CAP._delayed_signals(sigs, 60, frames)
    assert interp == 0, "a 60-second delay needs no interpolation"
    for a, b in zip(sigs, out):
        assert b.entry_ts == a.entry_ts + pd.Timedelta(minutes=1)
        assert b.entry_price == float(frames[a.ticker].loc[b.entry_ts, "open"])
        assert b.planned_exit_ts == a.planned_exit_ts, \
            "a late entry must not earn a longer hold"


def t_delay_sub_minute_is_flagged():
    cfg, sigs, frames = _suite_inputs()
    _out, interp = CAP._delayed_signals(sigs, 30, frames)
    assert interp > 0
    t = CAP.delay_stress(cfg, sigs, frames, [0, 30, 60])
    assert set(t["exact"]) == {"yes", "INTERPOLATED"}
    assert t[t.delay_sec == 30].iloc[0]["exact"] == "INTERPOLATED"


def t_delay_interpolation_sits_between_bars():
    cfg, sigs, frames = _suite_inputs()
    out, _ = CAP._delayed_signals(sigs, 30, frames)
    for b in out:
        bars = frames[b.ticker]
        p0 = float(bars.loc[b.entry_ts, "open"])
        p1 = float(bars.loc[b.entry_ts + pd.Timedelta(minutes=1), "open"])
        assert min(p0, p1) - 1e-9 <= b.entry_price <= max(p0, p1) + 1e-9


def t_participation_is_a_share_of_volume():
    cfg, sigs, frames = _suite_inputs()
    det, summ = CAP.participation(cfg, sigs, frames)
    assert (det["participation_5m"] > 0).all()
    assert (det["participation_15m"] <= det["participation_5m"] + 1e-12).all(), \
        "a longer window has more volume, so participation cannot rise"
    assert (summ["pct_over_limit"] <= 1.0).all()


def t_concentration_counts_days():
    cfg, sigs, frames = _suite_inputs()
    dist, stats = CAP.concentration(cfg, sigs, frames)
    assert abs(dist["pct_of_active_days"].sum() - 1.0) < 1e-9
    assert stats["mean_concurrent"] >= 1.0
    assert 0.0 <= stats["pct_days_1_or_2_names"] <= 1.0


def t_haircut_refuses_to_total_a_loss():
    cfg, sigs, frames = _suite_inputs()
    tab = CAP.run_suite(cfg, sigs, frames)
    hc = CAP.haircut(tab, cfg)
    # Fixtures are random walks and lose money, so every ratio is NaN
    # and the combined row must SAY so rather than invent a number.
    last = hc.iloc[-1]["friction"]
    assert "NOT COMPUTABLE" in last or "COMBINED" in last
    if "NOT COMPUTABLE" in last:
        assert pd.isna(hc.iloc[-1]["pct_of_pnl_kept"])


def t_capacity_dashboard_renders():
    cfg, sigs, frames = _suite_inputs()
    tab = CAP.run_suite(cfg, sigs, frames)
    txt = CAP.dashboard(tab, cfg, CAP.haircut(tab, cfg))
    assert "RISK & CAPACITY" in txt and "RECOMMENDED LIVE LIMITS" in txt


# ---------------------------------------------------------------- validation

def t_validation_reports_both_stop_variants():
    cfg, sigs, frames = _suite_inputs()
    rep = VAL.run(cfg, sigs, frames, out_dir=None, make_plots=False)
    assert set(rep.variants) == {"No stop", "ATR -1.0 stop"}
    assert set(rep.stress) == set(rep.variants)


def t_validation_stop_is_wired_not_just_unreached():
    """Guard against a report whose two variants are identical by BUG.

    On the fixtures a 1 ATR stop is never reached, so both variants agree
    -- which is indistinguishable from the stop never being applied. A
    deliberately tight stop must move the numbers.
    """
    cfg, sigs, frames = _suite_inputs()
    saved = VAL.VARIANTS
    try:
        VAL.VARIANTS = [("no_stop", "No stop", False, 1.0),
                        ("tight", "tight", True, 0.1)]
        rep = VAL.run(cfg, sigs, frames, out_dir=None, make_plots=False)
    finally:
        VAL.VARIANTS = saved
    a = rep.variants["No stop"].overall["expectancy_bps"]
    b = rep.variants["tight"].overall["expectancy_bps"]
    assert abs(a - b) > 1e-9, "a 0.1 ATR stop changed nothing; stop not wired"
    assert (rep.variants["tight"].trades["exit_reason"] == "stop").any()


def t_validation_cost_sweep_covers_the_grid():
    cfg, sigs, frames = _suite_inputs()
    rep = VAL.run(cfg, sigs, frames, costs=[6.6, 15.0], out_dir=None,
                  make_plots=False)
    assert set(rep.costs["cost_bps"]) == {6.6, 15.0}
    assert len(rep.costs) == 2 * len(VAL.VARIANTS)
    for v, g in rep.costs.groupby("variant"):
        e = g.sort_values("cost_bps")["expectancy_bps"].to_numpy()
        assert e[0] > e[1], f"{v}: higher cost must lower expectancy"


def t_validation_stress_is_annualised_on_its_own_window():
    cfg, sigs, frames = _suite_inputs()
    rep = VAL.run(cfg, sigs, frames, out_dir=None, make_plots=False)
    for label, m in rep.stress.items():
        if len(m.trades):
            d = pd.to_datetime(pd.Series(list(m.trades["date"]))).dt.date
            assert d.min() >= dt.date(2022, 1, 1), (label, d.min())


def t_validation_summary_and_write():
    import tempfile
    cfg, sigs, frames = _suite_inputs()
    rep = VAL.run(cfg, sigs, frames, costs=[6.6], out_dir=None,
                  make_plots=False)
    txt = rep.summary()
    for section in ("FULL VALIDATION", "STRESS PERIOD", "COST SENSITIVITY",
                    "SIDE BY SIDE"):
        assert section in txt, section
    with tempfile.TemporaryDirectory() as d:
        written = rep.write(d)
        assert any(p.name == "validation_summary.txt" for p in written)
        assert any("side_by_side" in p.name for p in written)


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
