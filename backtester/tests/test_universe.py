"""
test_universe.py -- assertions for the universe provider.

The BMO/AMC tests are the ones that matter. Mapping an announcement to
the wrong session shifts the entire cohort by one day and the backtest
still runs, still produces trades, and still prints a Sharpe ratio.

Run: python3 tests/test_universe.py
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
from engine.universe import (AllSessions, EarningsCalendar,  # noqa: E402
                             IntersectionUniverse, PostEarningsUniverse,
                             UniverseError, from_config)
from strategies.core_post_earnings import \
    CorePostEarningsContinuation  # noqa: E402

DATA = ROOT / "data"
CFG = ROOT / "config" / "strategies" / "core_post_earnings.yaml"
CAL = DATA / "earnings_calendar.csv"
CAPS = DATA / "market_caps.csv"

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


def synth_frame(dates: list[dt.date], close=100.0, volume=1e6) -> pd.DataFrame:
    """Minimal bars: one row per session, enough for the screens."""
    idx = pd.DatetimeIndex([pd.Timestamp(f"{d} 14:35", tz="UTC") for d in dates],
                           name="ts")
    return pd.DataFrame({
        "open": close, "high": close, "low": close, "close": close,
        "volume": volume, "session_date": dates,
        "minutes_from_open": 5,
    }, index=idx)


def cal(rows) -> EarningsCalendar:
    return EarningsCalendar(pd.DataFrame(
        rows, columns=["ticker", "announce_date", "announce_time"]))


# ------------------------------------------------------- the timing question

def t_bmo_reacts_same_session():
    days = [dt.date(2025, 3, 3), dt.date(2025, 3, 4), dt.date(2025, 3, 5)]
    p = PostEarningsUniverse(cal([("X", "2025-03-04", "bmo")]))
    e = p.eligible({"X": synth_frame(days)})
    assert e["X"] == {dt.date(2025, 3, 4)}, e


def t_amc_reacts_next_session():
    days = [dt.date(2025, 3, 3), dt.date(2025, 3, 4), dt.date(2025, 3, 5)]
    p = PostEarningsUniverse(cal([("X", "2025-03-04", "amc")]))
    e = p.eligible({"X": synth_frame(days)})
    assert e["X"] == {dt.date(2025, 3, 5)}, e


def t_amc_skips_the_weekend():
    """Friday AMC must land on Monday, not calendar Saturday."""
    days = [dt.date(2025, 3, 6), dt.date(2025, 3, 7),      # Thu, Fri
            dt.date(2025, 3, 10), dt.date(2025, 3, 11)]    # Mon, Tue
    p = PostEarningsUniverse(cal([("X", "2025-03-07", "amc")]))
    e = p.eligible({"X": synth_frame(days)})
    assert e["X"] == {dt.date(2025, 3, 10)}, e


def t_amc_skips_a_holiday_gap():
    """The next session comes from the DATA, so a halt cannot shift it."""
    days = [dt.date(2025, 3, 3), dt.date(2025, 3, 4), dt.date(2025, 3, 14)]
    p = PostEarningsUniverse(cal([("X", "2025-03-04", "amc")]))
    e = p.eligible({"X": synth_frame(days)})
    assert e["X"] == {dt.date(2025, 3, 14)}, "must use the next TRADED session"


def t_amc_on_the_last_session_is_dropped():
    days = [dt.date(2025, 3, 3), dt.date(2025, 3, 4)]
    p = PostEarningsUniverse(cal([("X", "2025-03-04", "amc")]))
    e = p.eligible({"X": synth_frame(days)})
    assert not e, "there is no session to trade the reaction on"
    assert p.diagnostics()["no_next_session"] == 1


def t_unknown_timing_is_skipped_by_default():
    days = [dt.date(2025, 3, 3), dt.date(2025, 3, 4), dt.date(2025, 3, 5)]
    p = PostEarningsUniverse(cal([("X", "2025-03-04", "")]))
    e = p.eligible({"X": synth_frame(days)})
    assert not e, "unknown timing must not be guessed"
    assert p.diagnostics()["unknown_timing_skipped"] == 1


def t_unknown_timing_policies_differ_by_a_session():
    """The whole point: the two assumptions trade different days."""
    days = [dt.date(2025, 3, 3), dt.date(2025, 3, 4), dt.date(2025, 3, 5)]
    f = {"X": synth_frame(days)}
    a = PostEarningsUniverse(cal([("X", "2025-03-04", "")]),
                             unknown_timing="assume_amc").eligible(f)
    b = PostEarningsUniverse(cal([("X", "2025-03-04", "")]),
                             unknown_timing="assume_bmo").eligible(f)
    assert a["X"] == {dt.date(2025, 3, 5)}
    assert b["X"] == {dt.date(2025, 3, 4)}
    assert a != b, "if these agreed, the timing field would not matter"


def t_assumed_timing_is_labelled_a_warning():
    p = PostEarningsUniverse(cal([("X", "2025-03-04", "")]),
                             unknown_timing="assume_amc")
    p.eligible({"X": synth_frame([dt.date(2025, 3, 4), dt.date(2025, 3, 5)])})
    d = p.diagnostics()
    assert "WARNING" in d and "assumption" in d["WARNING"].lower()


def t_bad_unknown_policy_raises():
    expect_raises(UniverseError,
                  lambda: PostEarningsUniverse(cal([]), unknown_timing="guess"),
                  "unknown_timing")


# ------------------------------------------------------------ point-in-time

def t_price_screen_reads_the_prior_session():
    """A name that was cheap YESTERDAY is excluded, even if it gapped up.

    Screening on the event session's own price would use the gap being
    traded to decide whether to trade it.
    """
    days = [dt.date(2025, 3, 3), dt.date(2025, 3, 4), dt.date(2025, 3, 5)]
    bars = synth_frame(days)
    bars.loc[bars["session_date"] == dt.date(2025, 3, 4), "close"] = 5.0
    bars.loc[bars["session_date"] == dt.date(2025, 3, 5), "close"] = 50.0
    p = PostEarningsUniverse(cal([("X", "2025-03-04", "amc")]), min_price=10.0)
    e = p.eligible({"X": bars})
    assert not e, "prior close was 5.0; the 50.0 event-day price must not rescue it"


def t_price_screen_passes_on_prior_close():
    days = [dt.date(2025, 3, 3), dt.date(2025, 3, 4), dt.date(2025, 3, 5)]
    bars = synth_frame(days)
    bars.loc[bars["session_date"] == dt.date(2025, 3, 4), "close"] = 50.0
    p = PostEarningsUniverse(cal([("X", "2025-03-04", "amc")]), min_price=10.0)
    assert p.eligible({"X": bars})["X"] == {dt.date(2025, 3, 5)}


def t_market_cap_is_asof_strictly_before():
    days = [dt.date(2025, 3, 3), dt.date(2025, 3, 4), dt.date(2025, 3, 5)]
    caps = pd.DataFrame([
        {"ticker": "X", "date": "2025-03-01", "market_cap": 1e9},
        # A revision stamped ON the event session must NOT be used.
        {"ticker": "X", "date": "2025-03-05", "market_cap": 9e9},
    ])
    p = PostEarningsUniverse(cal([("X", "2025-03-04", "amc")]),
                             min_market_cap=3e9, market_caps=caps)
    assert not p.eligible({"X": synth_frame(days)}), \
        "the 9e9 value dated on the event session must not be visible"


def t_market_cap_without_source_raises():
    expect_raises(UniverseError,
                  lambda: PostEarningsUniverse(cal([]), min_market_cap=3e9),
                  "market_caps")


def t_liquidity_needs_a_full_window():
    days = [dt.date(2025, 3, d) for d in (3, 4, 5)]
    p = PostEarningsUniverse(cal([("X", "2025-03-04", "amc")]),
                             min_adv_shares=1.0, adv_lookback=63)
    assert not p.eligible({"X": synth_frame(days)}), \
        "a partial baseline must not qualify"


def t_liquidity_excludes_the_event_session():
    days = [d.date() for d in pd.bdate_range("2025-01-02", periods=80)]
    bars = synth_frame(days, volume=1.0)
    # Only the event session is liquid. Averaging it in would qualify.
    bars.loc[bars["session_date"] == days[70], "volume"] = 1e12
    p = PostEarningsUniverse(cal([("X", str(days[69]), "amc")]),
                             min_adv_shares=1000.0, adv_lookback=63)
    assert not p.eligible({"X": bars}), \
        "the event session's own volume leaked into its baseline"


def t_no_prior_session_is_dropped():
    days = [dt.date(2025, 3, 4), dt.date(2025, 3, 5)]
    p = PostEarningsUniverse(cal([("X", "2025-03-03", "amc")]), min_price=1.0)
    e = p.eligible({"X": synth_frame(days)})
    assert not e and p.diagnostics()["no_prior_session"] == 1


# -------------------------------------------------------------- the calendar

def t_calendar_requires_columns():
    expect_raises(UniverseError,
                  lambda: EarningsCalendar(pd.DataFrame({"sym": ["X"]})),
                  "missing column")


def t_calendar_accepts_aliases():
    c = cal([("X", "2025-03-04", "After Market Close"),
             ("X", "2025-06-04", "pre")])
    assert set(c.table["announce_time"]) == {"amc", "bmo"}


def t_calendar_unrecognised_becomes_unknown():
    c = cal([("X", "2025-03-04", "time-not-supplied")])
    assert c.table["announce_time"].iloc[0] == "unknown"


def t_calendar_from_dict():
    c = EarningsCalendar.from_dict({"X": [("2025-03-04", "amc"), "2025-06-04"]})
    assert len(c.table) == 2
    assert set(c.table["announce_time"]) == {"amc", "unknown"}


def t_calendar_rejects_bad_dates():
    expect_raises(UniverseError,
                  lambda: cal([("X", "not-a-date", "amc")]), "announce_date")


def t_calendar_from_file_roundtrip():
    c = EarningsCalendar.from_file(CAL)
    assert "AAPL" in c.tickers
    mix = c.timing_mix()
    assert mix["amc"] > 0 and mix["bmo"] > 0 and mix["unknown"] > 0, \
        "the fixture should exercise all three timing paths"


# ------------------------------------------------------------- composition

def t_all_sessions_says_so():
    d = AllSessions().eligible({"X": synth_frame([dt.date(2025, 3, 3)])})
    assert d["X"] == {dt.date(2025, 3, 3)}
    assert "NO universe filtering" in AllSessions().diagnostics()["note"]


def t_intersection_narrows():
    days = [dt.date(2025, 3, 3), dt.date(2025, 3, 4), dt.date(2025, 3, 5)]
    f = {"X": synth_frame(days)}
    pe = PostEarningsUniverse(cal([("X", "2025-03-04", "amc")]))
    both = (AllSessions() & pe).eligible(f)
    assert both["X"] == {dt.date(2025, 3, 5)}, both


def t_from_config_demands_a_calendar():
    cfg = BacktestConfig.from_yaml(CFG)
    expect_raises(UniverseError, lambda: from_config(cfg, None),
                  "no earnings calendar")


def t_from_config_builds_the_provider():
    cfg = BacktestConfig.from_yaml(CFG)
    p = from_config(cfg, CAL, pd.read_csv(CAPS))
    assert isinstance(p, PostEarningsUniverse)
    assert p.min_price == cfg.universe.min_price


# ------------------------------------------------------------- end-to-end

def _frames():
    ld = DataLoader(DATA)
    return {t: ld.load(t) for t in ld.tickers}


def t_universe_actually_reduces_signals():
    """THE regression test for the blocking bug.

    Without a universe the strategy evaluates every session. With one it
    must evaluate strictly fewer, and every signal must fall on an
    eligible date.
    """
    cfg = BacktestConfig.from_yaml(CFG)
    frames = _frames()
    strat = CorePostEarningsContinuation(cfg)

    unfiltered = strat.run_many_signals(frames)
    prov = from_config(cfg, CAL, pd.read_csv(CAPS))
    elig = prov.eligible(frames)
    filtered = strat.run_many_signals(frames, eligible=elig)

    assert len(filtered) < len(unfiltered), (len(filtered), len(unfiltered))
    for s in filtered:
        assert s.session in elig[s.ticker], f"{s.ticker} {s.session} not eligible"


def t_every_signal_follows_an_announcement():
    """Each traded session must trace back to a real announcement."""
    cfg = BacktestConfig.from_yaml(CFG)
    frames = _frames()
    prov = from_config(cfg, CAL, pd.read_csv(CAPS))
    elig = prov.eligible(frames)
    sigs = CorePostEarningsContinuation(cfg).run_many_signals(
        frames, eligible=elig)
    assert sigs, "fixture should still produce signals"

    c = EarningsCalendar.from_file(CAL)
    for s in sigs:
        ann = c.for_ticker(s.ticker)
        ok = any(a <= s.session for a in ann["announce_date"])
        assert ok, f"{s.ticker} {s.session} precedes every announcement"


def t_diagnostics_report_a_funnel():
    cfg = BacktestConfig.from_yaml(CFG)
    prov = from_config(cfg, CAL, pd.read_csv(CAPS))
    prov.eligible(_frames())
    d = prov.diagnostics()
    assert d["candidate_sessions"] > d["eligible_pairs"], \
        "the filter must remove something on this fixture"
    assert d["after_price"] >= d["after_mcap"] >= d["after_liquidity"], \
        "the funnel must be monotone"
    assert d["eligible_pairs"] == d["after_liquidity"]


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
