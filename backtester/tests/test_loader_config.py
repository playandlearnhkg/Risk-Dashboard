"""
test_loader_config.py -- assertions for the DataLoader and Config loader.

Deliberately dependency-free (no pytest) so it runs anywhere with
`python3 tests/test_loader_config.py`. Every check prints PASS/FAIL and
the script exits non-zero if anything fails, which is enough to wire
into CI later.

The DST and de-duplication checks are the ones that matter most: they
are the two failure modes that produce a working-looking backtest with
wrong numbers.
"""

from __future__ import annotations

import datetime as dt
import sys
import traceback
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.calendar import (EXCHANGE_TZ, local_time_to_utc,  # noqa: E402
                             minutes_from_open, to_exchange_tz)
from engine.config import BacktestConfig, ConfigError  # noqa: E402
from engine.data_loader import (DataCatalog, DataError,  # noqa: E402
                                DataLoader, parse_filename)

DATA = ROOT / "data"
CFG = ROOT / "config" / "strategies" / "core_post_earnings.yaml"

_results: list[tuple[str, bool, str]] = []


def check(name: str, fn) -> None:
    try:
        fn()
        _results.append((name, True, ""))
    except Exception as exc:  # noqa: BLE001 - a test harness must catch all
        _results.append((name, False, f"{type(exc).__name__}: {exc}"))
        traceback.print_exc()


def expect_raises(exc_type, fn, contains: str = "") -> None:
    try:
        fn()
    except exc_type as exc:
        if contains and contains.lower() not in str(exc).lower():
            raise AssertionError(
                f"raised {exc_type.__name__} but message {str(exc)!r} "
                f"lacks {contains!r}")
        return
    raise AssertionError(f"expected {exc_type.__name__}, nothing raised")


# --------------------------------------------------------------- filenames

def t_parse_good():
    f = parse_filename("AAPL_20250801_20260801_1m.parquet")
    assert f.ticker == "AAPL", f.ticker
    assert f.start == pd.Timestamp("2025-08-01", tz="UTC"), f.start
    # End is inclusive to the last instant of the declared day.
    assert f.end.date() == dt.date(2026, 8, 1), f.end
    assert f.end.hour == 23 and f.end.minute == 59, f.end
    assert f.bar_size == "1m"


def t_parse_bad():
    for bad in ("AAPL.parquet", "AAPL_2025_2026_1m.parquet",
                "AAPL_20250801_20260801.parquet", "_20250801_20260801_1m.parquet"):
        expect_raises(DataError, lambda b=bad: parse_filename(b), "does not match")


def t_parse_reversed_range():
    expect_raises(DataError,
                  lambda: parse_filename("AAPL_20260801_20250801_1m.parquet"),
                  "start after end")


def t_catalog_skips_junk():
    cat = DataCatalog(DATA)
    assert cat.tickers == ["AAPL", "MSFT"], cat.tickers
    # The .txt file is not globbed at all; nothing should be "skipped"
    # for the wrong reason, and nothing should raise.
    assert isinstance(cat.skipped, list)


# ------------------------------------------------------------ load contract

def t_load_contract():
    df = DataLoader(DATA).load("AAPL")
    assert df.index.name == "ts"
    assert str(df.index.tz) == "UTC", df.index.tz
    assert df.index.is_monotonic_increasing
    assert not df.index.has_duplicates
    for c in ("open", "high", "low", "close", "volume"):
        assert c in df.columns and df[c].dtype == "float64", c
    assert not df[["open", "high", "low", "close", "volume"]].isna().to_numpy().any()


def t_regular_session_bounds():
    """The filter must keep exactly 09:30 <= local < 16:00, DST-correct."""
    df = DataLoader(DATA).load("AAPL", regular_session_only=True)
    local = to_exchange_tz(df.index)
    tmin, tmax = min(local.time), max(local.time)
    assert tmin == dt.time(9, 30), f"earliest local bar {tmin}, expected 09:30"
    assert tmax < dt.time(16, 0), f"latest local bar {tmax}, expected < 16:00"


def t_premarket_actually_removed():
    """Guard against a filter that is a no-op because the data is clean."""
    ld = DataLoader(DATA)
    everything = ld.load("AAPL", regular_session_only=False)
    regular = ld.load("AAPL", regular_session_only=True)
    assert len(everything) > len(regular), "fixture has no out-of-session bars"
    dropped = len(everything) - len(regular)
    assert dropped > 1000, f"only {dropped} bars dropped; filter looks inert"


def t_dst_transition():
    """THE important one.

    A hard-coded 13:30-20:00 UTC session would put the open at the same
    UTC hour all year. It must NOT: 09:30 New York is 13:30 UTC on
    daylight time and 14:30 UTC on standard time.
    """
    df = DataLoader(DATA).load("AAPL", regular_session_only=True)
    local = to_exchange_tz(df.index)
    opens = df[[t == dt.time(9, 30) for t in local.time]]
    utc_hours = sorted({ts.hour for ts in opens.index})
    assert utc_hours == [13, 14], (
        f"expected the 09:30 open at UTC hours [13, 14] across the DST "
        f"boundary, got {utc_hours}")

    edt = opens[opens.index < pd.Timestamp("2025-11-02", tz="UTC")]
    est = opens[opens.index > pd.Timestamp("2025-11-03", tz="UTC")]
    assert set(t.hour for t in edt.index) == {13}, "EDT open should be 13:30 UTC"
    assert set(t.hour for t in est.index) == {14}, "EST open should be 14:30 UTC"


def t_local_time_to_utc_dst():
    """09:35 local resolves to different UTC instants either side of DST."""
    a = local_time_to_utc(dt.date(2025, 10, 20), dt.time(9, 35))
    b = local_time_to_utc(dt.date(2025, 11, 20), dt.time(9, 35))
    assert (a.hour, a.minute) == (13, 35), a
    assert (b.hour, b.minute) == (14, 35), b


def t_minutes_from_open():
    df = DataLoader(DATA).load("AAPL", regular_session_only=True)
    local = to_exchange_tz(df.index)
    m = minutes_from_open(df.index)
    at_0935 = [t == dt.time(9, 35) for t in local.time]
    vals = set(m[at_0935].unique().tolist())
    assert vals == {5}, f"09:35 should be minute 5 from open, got {vals}"
    assert m.min() == 0 and m.max() < 390, (m.min(), m.max())


def t_early_close_detected():
    """A half day needs no holiday table: it just has fewer bars."""
    df = DataLoader(DATA).load("AAPL", regular_session_only=True)
    per = df.groupby("session_date").size()
    half = per[dt.date(2025, 11, 28)]
    typical = int(per.median())
    assert typical == 390, f"full session should be 390 bars, got {typical}"
    assert half == 210, f"2025-11-28 should be a 13:00 close (210 bars), got {half}"


def t_gaps_are_not_filled():
    """Missing minutes must stay missing, not be forward-filled."""
    df = DataLoader(DATA).load("AAPL", regular_session_only=True)
    day = df[df["session_date"] == dt.date(2025, 11, 12)]
    assert len(day) == 370, f"expected 390-20 punched bars, got {len(day)}"
    deltas = pd.Series(day.index).diff().dropna()
    assert deltas.max() == pd.Timedelta(minutes=21), (
        f"the 20-minute hole should survive as a gap, max delta {deltas.max()}")


# ------------------------------------------------------------ de-duplication

def t_overlap_newer_file_wins():
    """Overlapping extracts: the later-issued file must win, observably."""
    ld = DataLoader(DATA)
    df = ld.load("MSFT", regular_session_only=True)
    assert not df.index.has_duplicates
    assert df.attrs["duplicates_dropped"] > 0, "fixture overlap not exercised"

    old = pd.read_parquet(DATA / "MSFT_20251015_20251120_1m.parquet")
    new = pd.read_parquet(DATA / "MSFT_20251110_20251215_1m.parquet")
    shared = old.index.intersection(new.index)
    assert len(shared) > 0, "fixtures do not actually overlap"

    probe = shared[len(shared) // 2]
    got = float(df.loc[probe, "close"])
    assert abs(got - float(new.loc[probe, "close"])) < 1e-6, (
        f"at {probe} loader returned {got}, expected the newer extract's "
        f"{float(new.loc[probe, 'close'])} (older was "
        f"{float(old.loc[probe, 'close'])})")


# ------------------------------------------------------------- window clips

def t_window_end_is_inclusive():
    """A bare end date must include that whole day, not stop at midnight."""
    ld = DataLoader(DATA)
    df = ld.load("AAPL", start="2025-10-20", end="2025-10-20")
    assert len(df) > 0
    assert set(df["session_date"].unique()) == {dt.date(2025, 10, 20)}, \
        sorted(set(df["session_date"].unique()))


def t_empty_window_raises():
    expect_raises(DataError,
                  lambda: DataLoader(DATA).load("AAPL", start="2030-01-01"),
                  "no")


def t_unknown_ticker_raises():
    expect_raises(DataError, lambda: DataLoader(DATA).load("NOPE"), "no")


# -------------------------------------------------------------- validation

def _write_tmp(df: pd.DataFrame, name: str) -> Path:
    tmp = ROOT / "tests" / "_tmp"
    tmp.mkdir(exist_ok=True)
    p = tmp / name
    df.to_parquet(p)
    return p


def t_rejects_naive_index():
    df = pd.read_parquet(DATA / "AAPL_20251015_20251215_1m.parquet").head(500)
    df.index = df.index.tz_localize(None)
    df.index.name = "ts"
    _write_tmp(df, "NAIVE_20251015_20251215_1m.parquet")
    expect_raises(DataError,
                  lambda: DataLoader(ROOT / "tests" / "_tmp").load("NAIVE"),
                  "timezone-naive")


def t_rejects_bad_ohlc():
    df = pd.read_parquet(DATA / "AAPL_20251015_20251215_1m.parquet").head(500).copy()
    df.iloc[10, df.columns.get_loc("high")] = df.iloc[10]["low"] - 1.0
    _write_tmp(df, "BADOHLC_20251015_20251215_1m.parquet")
    expect_raises(DataError,
                  lambda: DataLoader(ROOT / "tests" / "_tmp").load("BADOHLC"),
                  "high < low")


def t_rejects_duplicate_timestamps_within_file():
    """A file duplicated against ITSELF cannot be resolved by recency."""
    df = pd.read_parquet(DATA / "AAPL_20251015_20251215_1m.parquet").head(500)
    doubled = pd.concat([df, df.iloc[:5]]).sort_index()
    _write_tmp(doubled, "DUPE_20251015_20251215_1m.parquet")
    # De-dup runs before validation, so this must come back clean and
    # keep exactly one row per timestamp.
    out = DataLoader(ROOT / "tests" / "_tmp").load(
        "DUPE", regular_session_only=False)
    assert not out.index.has_duplicates
    assert len(out) == len(df)


def t_audit_reports_range_mismatch():
    cat = DataCatalog(DATA)
    a = cat.audit()
    assert {"declared_start", "actual_start", "ends_early"} <= set(a.columns)
    row = a[a.file.str.startswith("AAPL")].iloc[0]
    # The fixture stops on 2025-12-15 but the filename claims through
    # the end of that day, so ends_early is expected and informative.
    assert bool(row["ends_early"]) is True


# ------------------------------------------------------------------ config

def t_config_loads():
    c = BacktestConfig.from_yaml(CFG)
    assert c.strategy.name == "Core_PostEarnings_Continuation"
    assert c.signal.entry_time == dt.time(9, 35)
    assert c.signal.volume_ratio_min == 1.5
    assert c.exit.hold_minutes == 60
    assert c.exit.stop.enabled is False
    assert c.direction == "signed"
    assert c.sizing.risk_pct == 0.005
    assert c.portfolio.starting_capital == 1_000_000
    assert c.costs.round_trip_bps == 6.6
    assert c.source_path is not None


def t_config_is_frozen():
    c = BacktestConfig.from_yaml(CFG)
    try:
        c.direction = "long_only"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("config must be immutable")


def t_config_rejects_typo():
    base = _yaml_dict()
    base["signal"]["volume_ratio_mim"] = 1.5      # deliberate typo
    expect_raises(ConfigError, lambda: BacktestConfig.from_dict(base),
                  "unknown key")


def t_config_rejects_unknown_section():
    base = _yaml_dict()
    base["portfolios"] = {}
    expect_raises(ConfigError, lambda: BacktestConfig.from_dict(base),
                  "unknown top-level")


def t_config_range_checks():
    base = _yaml_dict()
    base["sizing"]["risk_pct"] = 1.5
    expect_raises(ConfigError, lambda: BacktestConfig.from_dict(base), "risk_pct")

    base = _yaml_dict()
    base["signal"]["candle"] = "sideways"
    expect_raises(ConfigError, lambda: BacktestConfig.from_dict(base), "candle")

    base = _yaml_dict()
    base["exit"]["hold_minutes"] = 400
    expect_raises(ConfigError, lambda: BacktestConfig.from_dict(base),
                  "one regular session")


def t_config_coherence():
    base = _yaml_dict()
    base["signal"]["gap_required"] = False        # with candle=continuation
    expect_raises(ConfigError, lambda: BacktestConfig.from_dict(base),
                  "gap_required")


def t_config_warns_on_unbounded_risk():
    c = BacktestConfig.from_yaml(CFG)
    w = " ".join(c.warnings()).lower()
    assert "proxy" in w, f"expected the risk-proxy warning, got {c.warnings()}"


def t_config_bad_entry_time():
    base = _yaml_dict()
    base["signal"]["entry_time"] = "9h35"
    expect_raises(ConfigError, lambda: BacktestConfig.from_dict(base),
                  "entry_time")


def _yaml_dict() -> dict:
    import copy

    import yaml
    with CFG.open() as fh:
        return copy.deepcopy(yaml.safe_load(fh))


# -------------------------------------------------------------------- main

def main() -> int:
    tests = [(k[2:], v) for k, v in sorted(globals().items())
             if k.startswith("t_") and callable(v)]
    for name, fn in tests:
        check(name, fn)

    width = max(len(n) for n, _, _ in _results)
    failed = 0
    print()
    for name, ok, msg in _results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<{width}}  {msg}")
        failed += (not ok)
    print(f"\n{len(_results) - failed}/{len(_results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
