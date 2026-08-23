"""
Unit tests for the Stage 1 modules.

Focus is on the properties that, if broken, would silently produce a fake
result rather than an obvious crash: causality of the percentile, the session
boundary mask, NaN handling for degenerate bars, and the direction of the
trend/shape tests.

    python -m pytest tests/test_stage1.py -q
    python tests/test_stage1.py            # no pytest required
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from stage1 import core, io, stats


# ---------------------------------------------------------------------------
# Causality — the tests that matter most
# ---------------------------------------------------------------------------

def test_trailing_percentile_is_strictly_prior():
    """
    Changing a FUTURE value must not change any earlier percentile.

    This is the single most important invariant in the whole pipeline. If it
    fails, every downstream number is contaminated and the study is void.
    """
    idx = pd.date_range("2020-01-06 09:30", periods=800, freq="5min")
    base = pd.Series(np.random.default_rng(0).normal(size=800), index=idx)

    a = core.trailing_percentile(base, window=100, min_obs=50, by_time_of_day=False)

    tampered = base.copy()
    tampered.iloc[600:] += 1000.0          # violently change the future
    b = core.trailing_percentile(tampered, window=100, min_obs=50,
                                 by_time_of_day=False)

    pd.testing.assert_series_equal(a.iloc[:600], b.iloc[:600])


def test_trailing_percentile_excludes_current_bar():
    """A strictly increasing series must score 1.0 — every prior value is lower."""
    idx = pd.date_range("2020-01-06 09:30", periods=200, freq="5min")
    rising = pd.Series(np.arange(200, dtype=float), index=idx)
    pct = core.trailing_percentile(rising, window=50, min_obs=20,
                                   by_time_of_day=False)
    assert np.allclose(pct.dropna(), 1.0)


def test_forward_return_masks_session_boundary():
    """The last bar of a session has no same-session successor."""
    idx = pd.DatetimeIndex(
        list(pd.date_range("2020-01-06 15:45", periods=3, freq="5min"))
        + list(pd.date_range("2020-01-07 09:30", periods=3, freq="5min"))
    )
    df = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0,
                       "close": np.arange(6, dtype=float) + 100}, index=idx)
    atr = pd.Series(1.0, index=idx)
    r = core.forward_return(df, atr, h=1)

    assert np.isnan(r.iloc[2]), "return crossed the overnight gap"
    assert np.isnan(r.iloc[-1]), "last bar of the series has no successor"
    assert r.iloc[0] == 1.0


def test_atr_excludes_current_bar():
    """ATR at t must not see bar t's own range."""
    idx = pd.date_range("2020-01-06 09:30", periods=60, freq="5min")
    df = pd.DataFrame({"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0},
                      index=idx)
    spike = df.copy()
    spike.iloc[40, spike.columns.get_loc("high")] = 200.0

    a = core.wilder_atr_prev(df, n=20)
    b = core.wilder_atr_prev(spike, n=20)
    assert a.iloc[40] == b.iloc[40], "ATR at t reacted to bar t's own range"
    assert a.iloc[41] != b.iloc[41], "ATR at t+1 should see the spike"


# ---------------------------------------------------------------------------
# Degenerate bars
# ---------------------------------------------------------------------------

def test_zero_range_gives_nan_not_zero():
    idx = pd.date_range("2020-01-06 09:30", periods=40, freq="5min")
    df = pd.DataFrame({"open": 100.0, "high": 100.4, "low": 99.6, "close": 100.2},
                      index=idx)
    df.iloc[30] = [100.0, 100.0, 100.0, 100.0]      # a perfect doji

    feats = core.candle_features(df, tick_size=0.01)
    for col in ("BD", "CL", "SA", "DQ"):
        assert np.isnan(feats[col].iloc[30]), f"{col} was not NaN on a zero-range bar"
    assert not feats["valid"].iloc[30]


def test_body_shadow_identity():
    """|B| + U + D == R must hold for every bar."""
    df = core.synthetic_bars(n_sessions=5, seed=3)
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    lhs = (c - o).abs() + (h - np.maximum(o, c)) + (np.minimum(o, c) - l)
    assert np.allclose(lhs, h - l)


# ---------------------------------------------------------------------------
# Baseline correctness
# ---------------------------------------------------------------------------

def test_pi0_removes_drift():
    """
    On drifting data with no information, the corrected baseline must be much
    closer to the observed concordance than the naive 0.5 is.
    """
    df = core.synthetic_bars(n_sessions=250, drift_per_bar=0.03, seed=5)
    feats, dq_pct, _, r1 = core._prepare(df, 0.01)
    table = core.bucket_table(feats["DQ"], dq_pct, r1)

    bull = table[table["frac_bullish"] > 0.9]
    naive = (bull["concordance"] - 0.5).abs().mean()
    corrected = bull["lift"].abs().mean()
    assert corrected < naive, "pi_0 did not reduce the drift artefact"


# ---------------------------------------------------------------------------
# Trend and shape tests
# ---------------------------------------------------------------------------

def test_jonckheere_detects_real_trend():
    rng = np.random.default_rng(1)
    groups = [rng.normal(loc=i * 0.4, scale=1.0, size=300) for i in range(5)]
    res = stats.jonckheere_terpstra(groups, permutations=300, seed=0)
    assert res.z > 3, f"failed to detect a strong monotone trend (z={res.z})"
    assert res.p_permutation < 0.05


def test_jonckheere_null_is_not_significant():
    rng = np.random.default_rng(2)
    groups = [rng.normal(size=300) for _ in range(5)]
    res = stats.jonckheere_terpstra(groups, permutations=300, seed=0)
    assert abs(res.z) < 3
    assert res.p_permutation > 0.05


def test_isotonic_is_monotone_and_exact_when_already_sorted():
    y = np.array([1.0, 2.0, 3.0, 4.0])
    assert np.allclose(stats.isotonic_fit(y), y)

    fit = stats.isotonic_fit(np.array([3.0, 1.0, 2.0, 5.0]))
    assert np.all(np.diff(fit) >= -1e-12)
    assert abs(fit.mean() - 2.75) < 1e-9      # PAVA preserves the mean


def test_shape_classification_labels_monotone_and_noise():
    mono = stats.shape_classification(np.arange(10, dtype=float))
    assert mono["shape"] == "monotone"

    rng = np.random.default_rng(4)
    noisy = stats.shape_classification(rng.normal(size=10))
    assert noisy["shape"] in ("noise", "non_monotone")


# ---------------------------------------------------------------------------
# Effective sample size
# ---------------------------------------------------------------------------

def test_k_eff_collapses_for_identical_instruments():
    """Three perfectly correlated instruments carry the weight of about one."""
    idx = pd.date_range("2020-01-06 09:30", periods=2000, freq="5min")
    r = pd.Series(np.random.default_rng(6).normal(size=2000), index=idx)
    s = pd.Series(np.random.default_rng(7).normal(size=2000), index=idx)

    es = stats.effective_sample_size(
        {"A": s, "B": s, "C": s}, {"A": r, "B": r, "C": r})
    assert es.k_eff < 1.2, f"K_eff was {es.k_eff}, expected ~1 for identical series"


def test_k_eff_is_full_for_independent_instruments():
    rng = np.random.default_rng(8)
    idx = pd.date_range("2020-01-06 09:30", periods=3000, freq="5min")
    scores = {k: pd.Series(rng.normal(size=3000), index=idx) for k in "ABC"}
    targets = {k: pd.Series(rng.normal(size=3000), index=idx) for k in "ABC"}

    es = stats.effective_sample_size(scores, targets)
    assert es.k_eff > 2.5, f"K_eff was {es.k_eff}, expected ~3 for independent series"


# ---------------------------------------------------------------------------
# Gate evaluator
# ---------------------------------------------------------------------------

def _detected_results():
    return {
        "mean_ic": 0.020, "ic_t": 4.0, "consistency_ratio": 0.75,
        "n_blocks": 24, "blocks_with_sign": 18, "jt_p": 0.01,
        "bucket_spearman": 0.85, "h2_spread": 0.02, "h2_ci_low": 0.005,
        "h2_ci_high": 0.035, "h1_ordering_respected": True,
        "permutation_p": 0.001, "survives_fdr": True,
        "composite_beats_components": True, "extreme_vs_middle_significant": True,
        "pipeline_gates_pass": True,
    }


def test_gate_evaluator_detects():
    _, verdict = stats.evaluate_gates(_detected_results())
    assert verdict == "DETECTED"


def test_gate_evaluator_kills_on_low_ic():
    r = _detected_results()
    r.update(mean_ic=0.001, ic_t=0.4)
    _, verdict = stats.evaluate_gates(r)
    assert verdict == "NO_USEFUL_PREDICTIVITY"


def test_gate_evaluator_kills_on_reversed_sign():
    """K7: a reversed sign is a rejection, however strong the effect."""
    r = _detected_results()
    r["h1_ordering_respected"] = False
    _, verdict = stats.evaluate_gates(r)
    assert verdict == "NO_USEFUL_PREDICTIVITY"


def test_missing_gates_do_not_count_as_passed():
    """A gate that has not been run has not been passed."""
    r = _detected_results()
    del r["composite_beats_components"]
    gates, verdict = stats.evaluate_gates(r)
    assert verdict == "INCONCLUSIVE"
    assert any(g.code == "G7" and g.passed is None for g in gates)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _spec(**kw):
    base = dict(symbol="X", path="", timezone="America/New_York", bar_label="open",
                session_start="09:30", session_end="16:00", tick_size=0.01,
                adjustment="multiplicative")
    base.update(kw)
    return io.InstrumentSpec(**base)


def test_bar_label_inference():
    open_idx = pd.date_range("2020-01-06 09:30", periods=78, freq="5min")
    assert io.infer_bar_label(open_idx, _spec(), 5) == "open"

    close_idx = pd.date_range("2020-01-06 09:35", periods=78, freq="5min")
    assert io.infer_bar_label(close_idx, _spec(), 5) == "close"


def test_normalise_bar_label_shifts_back():
    idx = pd.date_range("2020-01-06 09:35", periods=3, freq="5min")
    df = pd.DataFrame({"close": [1.0, 2.0, 3.0]}, index=idx)
    out = io.normalise_bar_label(df, "close", 5)
    assert out.index[0] == pd.Timestamp("2020-01-06 09:30")
    assert out["close"].iloc[0] == 1.0, "values must not move, only the labels"


def test_rth_filter_keeps_78_bars():
    idx = pd.date_range("2020-01-06 04:00", "2020-01-06 19:55", freq="5min")
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}, index=idx)
    assert len(io.filter_rth(df, _spec(), 5)) == 78



# ---------------------------------------------------------------------------
# HF 1-minute -> 5-minute resampling
# ---------------------------------------------------------------------------

def _one_min_session(day: str, n: int = 390, start_price: float = 100.0):
    idx = pd.date_range(f"{day} 09:30", periods=n, freq="1min", tz="America/New_York")
    rng = np.random.default_rng(abs(hash(day)) % 1000)
    close = start_price + np.cumsum(rng.normal(0, 0.02, n))
    return pd.DataFrame({
        "open": close - 0.01, "high": close + 0.03,
        "low": close - 0.03, "close": close,
        "volume": rng.integers(100, 5000, n),
    }, index=idx)


def test_resample_ohlc_is_correct():
    from stage1 import hf_prepare
    one = _one_min_session("2019-01-02")
    bars, stats = hf_prepare.resample_to_5min(one)

    assert len(bars) == 78, f"expected 78 five-minute bars, got {len(bars)}"
    assert bars.index[0].strftime("%H:%M") == "09:30"
    assert bars.index[-1].strftime("%H:%M") == "15:55"

    first5 = one.iloc[:5]
    b0 = bars.iloc[0]
    assert b0["open"] == first5["open"].iloc[0]
    assert b0["close"] == first5["close"].iloc[-1]
    assert b0["high"] == first5["high"].max()
    assert b0["low"] == first5["low"].min()
    assert b0["volume"] == first5["volume"].sum()


def test_resample_never_crosses_session_boundary():
    from stage1 import hf_prepare
    two = pd.concat([_one_min_session("2019-01-02"), _one_min_session("2019-01-03")])
    bars, _ = hf_prepare.resample_to_5min(two)

    per_session = bars.groupby(bars.index.normalize()).size()
    assert (per_session == 78).all(), "a bin spanned the overnight gap"


def test_resample_drops_incomplete_bins_and_leaves_a_hole():
    from stage1 import hf_prepare
    one = _one_min_session("2019-01-02")
    # Remove 4 of the 5 minutes in the 10:00 bin -> incomplete, must be dropped.
    drop = one.index[(one.index.hour == 10) & (one.index.minute < 4)]
    bars, stats = hf_prepare.resample_to_5min(one.drop(index=drop))

    assert stats["bins_dropped"] == 1
    ten = pd.Timestamp("2019-01-02 10:00", tz="America/New_York")
    assert ten in bars.index, "grid row missing entirely; should be a NaN hole"
    assert np.isnan(bars.loc[ten, "close"]), "hole was filled instead of left NaN"


def test_resample_excludes_extended_hours():
    from stage1 import hf_prepare
    pre = pd.date_range("2019-01-02 04:00", "2019-01-02 09:29", freq="1min",
                        tz="America/New_York")
    extended = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
                             "volume": 1}, index=pre)
    bars, _ = hf_prepare.resample_to_5min(pd.concat([extended, _one_min_session("2019-01-02")]))

    assert bars.index[0].strftime("%H:%M") == "09:30"
    assert bars["low"].min() > 1.0, "a pre-market bar leaked into the RTH series"


def test_one_minute_label_detection():
    from stage1 import hf_prepare
    open_idx = pd.date_range("2019-01-02 09:30", periods=390, freq="1min",
                             tz="America/New_York")
    assert hf_prepare.detect_one_minute_label(open_idx) == "open"

    close_idx = pd.date_range("2019-01-02 09:31", periods=390, freq="1min",
                              tz="America/New_York")
    assert hf_prepare.detect_one_minute_label(close_idx) == "close"


def test_forward_return_is_nan_across_a_hole():
    """
    The reason holes must stay in the index: without the strict spacing check,
    shift(-1) over a missing bar silently produces a 10-minute return labelled
    as r_1.
    """
    idx = pd.DatetimeIndex([
        pd.Timestamp("2019-01-02 09:30"), pd.Timestamp("2019-01-02 09:35"),
        pd.Timestamp("2019-01-02 09:45"),          # 09:40 is missing
        pd.Timestamp("2019-01-02 09:50"),
    ])
    df = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0,
                       "close": [100.0, 101.0, 103.0, 104.0]}, index=idx)
    atr = pd.Series(1.0, index=idx)

    loose = core.forward_return(df, atr, h=1)
    strict = core.forward_return(df, atr, h=1, bar_minutes=5)

    assert loose.iloc[1] == 2.0, "sanity: unguarded shift spans the hole"
    assert np.isnan(strict.iloc[1]), "strict spacing did not reject the 10-min jump"
    assert strict.iloc[0] == 1.0, "a correctly spaced bar was rejected"



# ---------------------------------------------------------------------------
# Local-file inspection
# ---------------------------------------------------------------------------

def _write_probe(tmp, name, tz_convert=None, label_shift=0, fill_frac=0.0,
                 epoch=None):
    import pathlib as _p
    df = core.synthetic_bars(n_sessions=40, seed=17)
    rng = np.random.default_rng(2)
    df["volume"] = rng.integers(1000, 90000, len(df))

    if fill_frac:
        hit = rng.choice(len(df), size=int(fill_frac * len(df)), replace=False)
        for i in sorted(hit):
            if i > 0:
                df.iloc[i] = [df.iloc[i - 1]["close"]] * 4 + [0]

    idx = df.index.tz_localize("America/New_York")
    if label_shift:
        idx = idx + pd.Timedelta(minutes=label_shift)
    out = df.copy()

    if epoch:
        out.index = idx
        emit = out.reset_index(names="timestamp")
        emit["timestamp"] = emit["timestamp"].map(lambda t: int(t.timestamp()))
    else:
        out.index = idx.tz_convert(tz_convert).tz_localize(None) if tz_convert else idx
        emit = out.reset_index(names="timestamp")
        emit["timestamp"] = emit["timestamp"].map(
            lambda t: t.isoformat() if hasattr(t, "isoformat") else str(t))

    path = _p.Path(tmp) / name
    emit.to_csv(path, index=False)
    return path


def test_inspect_reads_prices_not_nan(tmp_path=None):
    """
    Regression: passing a Series that still carries the file's RangeIndex
    against a DatetimeIndex makes pandas ALIGN them, silently turning every
    price into NaN. Every price-based diagnostic then reports a cheerful zero.
    """
    import tempfile
    from stage1 import inspect as insp

    with tempfile.TemporaryDirectory() as tmp:
        path = _write_probe(tmp, "AAA_5min.csv", epoch=True)
        d = insp.describe(path, bar_minutes=5)

    assert d["timestamp_form"] == "epoch_s"
    assert d["bar_label"] == "open"
    assert np.isfinite(d["inferred_tick"]), "prices came through as NaN"
    assert abs(d["inferred_tick"] - 0.01) < 1e-6


def test_inspect_detects_close_labelled_and_utc():
    import tempfile
    from stage1 import inspect as insp

    with tempfile.TemporaryDirectory() as tmp:
        path = _write_probe(tmp, "BBB_5min.csv", label_shift=5)
        d = insp.describe(path, bar_minutes=5)
    assert d["bar_label"] == "close"


def test_inspect_flags_forward_filled_bars():
    import tempfile
    from stage1 import inspect as insp

    with tempfile.TemporaryDirectory() as tmp:
        path = _write_probe(tmp, "CCC_5min.csv", fill_frac=0.03)
        d = insp.describe(path, bar_minutes=5)

    assert d["zero_range"] > 0.01 * d["rows_rth"], "filled bars not detected"
    flags = insp._flags(d)
    assert any("high == low" in f for f in flags), f"no zero-range flag: {flags}"
    assert any("synthetic fill" in f for f in flags), f"no fill flag: {flags}"



def test_to_new_york_localises_naive_exchange_stamps():
    """
    Regression: naive New York stamps parsed as UTC land five hours early, in
    pre-market. Nothing errors - the whole study is just computed on the wrong
    candles.
    """
    from stage1 import hf_prepare

    naive = pd.Series(pd.date_range("2019-01-02 09:30", periods=390, freq="1min"))
    idx = hf_prepare.to_new_york(naive)
    assert str(idx.tz) == "America/New_York"
    assert idx[0].strftime("%H:%M") == "09:30", f"shifted to {idx[0]}"

    utc = pd.Series(pd.date_range("2019-01-02 14:30", periods=390, freq="1min"))
    idx2 = hf_prepare.to_new_york(utc)
    assert idx2[0].strftime("%H:%M") == "09:30", f"UTC stamps not converted: {idx2[0]}"


def test_to_new_york_refuses_unrecognised_offset():
    from stage1 import hf_prepare
    weird = pd.Series(pd.date_range("2019-01-02 03:15", periods=100, freq="1min"))
    try:
        hf_prepare.to_new_york(weird)
    except ValueError as exc:
        assert "neither" in str(exc)
    else:
        raise AssertionError("accepted an unrecognisable timezone instead of raising")


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                passed += 1
                print(f"  PASS  {name}")
            except AssertionError as exc:
                failed += 1
                print(f"  FAIL  {name}: {exc}")
            except Exception as exc:                       # noqa: BLE001
                failed += 1
                print(f"  ERROR {name}: {type(exc).__name__}: {exc}")
    print(f"\n  {passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)
