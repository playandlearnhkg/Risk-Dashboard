"""
stage1.gates — Step 3 of the execution order: pipeline validation (spec 5.6).

These tests validate the CODE, not the hypothesis. A leaking pipeline makes
every other safeguard cosmetic, so no real result may be reported until all of
them pass on the actual data.

    python -m stage1.gates --synthetic          # the reference self-test
    python -m stage1.gates --data data/clean    # the same gates on real bars

Gate 1  synthetic null   : shuffled / random-walk data must show no edge
Gate 2  future canary    : a score that IS the target must show IC ~ 1
Gate 3  noise canary     : an i.i.d. score must show IC ~ 0
Gate 4  shift invariance : an extra lag must degrade the result gracefully
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from stage1 import core
from stage1.dataset import load_clean, load_tick_sizes, prepare, split_holdout

NULL_IC_TOLERANCE = 0.02
FUTURE_IC_MIN = 0.95
# Below this the shift-invariance comparison is noise-vs-noise (spec G1 floor).
SHIFT_TEST_FLOOR = 0.005


def _shuffle_within_session(s: pd.Series, seed: int = 0) -> pd.Series:
    """Destroy any real relationship while preserving the session structure."""
    rng = np.random.default_rng(seed)
    out = s.copy()
    sess = pd.Series(s.index.normalize(), index=s.index)
    for _, idx in out.groupby(sess).groups.items():
        vals = np.array(out.loc[idx], dtype=float, copy=True)
        finite = np.isfinite(vals)
        vals[finite] = rng.permutation(vals[finite])
        out.loc[idx] = vals
    return out


def run_synthetic_gates(verbose: bool = True) -> dict:
    """The reference self-test, on random-walk bars with a deliberate drift."""
    tick = 0.01
    df = core.synthetic_bars(drift_per_bar=0.03)
    feats, dq_pct, conv_pct, r1 = core._prepare(df, tick)

    res = {}
    res["synthetic_null_ic"] = core.information_coefficient(feats["DQ"], r1)
    res["synthetic_null_pass"] = abs(res["synthetic_null_ic"]) < NULL_IC_TOLERANCE

    res["future_canary_ic"] = core.information_coefficient(
        r1.where(feats["valid"]), r1)
    res["future_canary_pass"] = res["future_canary_ic"] > FUTURE_IC_MIN

    rng = np.random.default_rng(7)
    noise = pd.Series(rng.normal(size=len(df)), index=df.index).where(feats["valid"])
    res["noise_canary_ic"] = core.information_coefficient(noise, r1)
    res["noise_canary_pass"] = abs(res["noise_canary_ic"]) < NULL_IC_TOLERANCE

    table = core.bucket_table(feats["DQ"], dq_pct, r1)
    bull = table[table["frac_bullish"] > 0.9]
    res["p_up"] = core.p_up_baseline(feats["DQ"], dq_pct, r1)
    res["naive_lift_bull"] = float((bull["concordance"] - 0.5).mean())
    res["corrected_lift_bull"] = float(bull["lift"].mean())
    res["quadrant_spread_H2"] = core.quadrant_spread(feats, conv_pct, r1)

    if verbose:
        print("=" * 74)
        print("PIPELINE GATES - SYNTHETIC (random-walk bars, upward drift)")
        print("=" * 74)
        print(f"  valid bars              : {int(feats['valid'].sum()):,} / {len(df):,}")
        print(f"  scored bars (DQ_pct)    : {int(dq_pct.notna().sum()):,}\n")
        for label, key in (("Gate 1  synthetic null ", "synthetic_null"),
                           ("Gate 2  future canary  ", "future_canary"),
                           ("Gate 3  noise canary   ", "noise_canary")):
            print(f"  {label} : IC = {res[key + '_ic']:+.5f}   "
                  f"{'PASS' if res[key + '_pass'] else 'FAIL'}")
        print("\n  Drift trap (this data contains NO information, only drift):")
        print(f"    P(r > 0) on the sample      : {res['p_up']:.4f}"
              "   <- not 0.50, so 0.50 is the wrong baseline")
        print(f"    bullish buckets, conc - 0.50: {res['naive_lift_bull']:+.4f}"
              "   <- the naive baseline's fake 'edge'")
        print(f"    bullish buckets, conc - pi_0: {res['corrected_lift_bull']:+.4f}"
              "   <- corrected, collapses toward 0")
        print(f"    quadrant spread H2          : {res['quadrant_spread_H2']:+.4f}"
              "   <- drift cancels in a difference")
        print("\n  Decile ladder on data with no predictivity:")
        print(table.round(4).to_string(index=False))

    res["all_gates_pass"] = all(v for k, v in res.items() if k.endswith("_pass"))
    if verbose:
        print(f"\n  ALL GATES: {'PASS' if res['all_gates_pass'] else 'FAIL'}")
        if not res["all_gates_pass"]:
            print("  Pipeline is not trustworthy. Fix before running on real data.")
    return res


def run_real_gates(data_dir: str, verbose: bool = True) -> dict:
    """The same four gates, on the validated bars."""
    bars = load_clean(data_dir)
    ticks = load_tick_sizes(data_dir)
    res: dict = {"per_instrument": {}}

    if verbose:
        print("=" * 74)
        print("PIPELINE GATES - REAL DATA")
        print("=" * 74)

    all_pass = True
    for sym, raw in sorted(bars.items()):
        df, _ = split_holdout(raw)          # holdout stays sealed
        tick = ticks.get(sym, 0.01)
        p = prepare(df, tick)

        # Gate 1: shuffle the target within session -> no relationship left.
        shuffled = _shuffle_within_session(p.r1, seed=11)
        ic_null = core.information_coefficient(p.dq, shuffled)

        # Gate 2: the target as its own score.
        ic_future = core.information_coefficient(
            p.r1.where(p.feats["valid"]), p.r1)

        # Gate 3: i.i.d. noise as a score.
        rng = np.random.default_rng(13)
        noise = pd.Series(rng.normal(size=len(df)),
                          index=df.index).where(p.feats["valid"])
        ic_noise = core.information_coefficient(noise, p.r1)

        # Gate 4: one extra lag on the score.
        ic_real = core.information_coefficient(p.dq, p.r1)
        ic_lagged = core.information_coefficient(p.dq.shift(1), p.r1)

        passed = {
            "null": abs(ic_null) < NULL_IC_TOLERANCE,
            "future": ic_future > FUTURE_IC_MIN,
            "noise": abs(ic_noise) < NULL_IC_TOLERANCE,
        }
        all_pass &= all(passed.values())

        res["per_instrument"][sym] = {
            "ic_null_shuffled": ic_null, "ic_future": ic_future,
            "ic_noise": ic_noise, "ic_observed": ic_real, "ic_lagged": ic_lagged,
            **{f"pass_{k}": v for k, v in passed.items()},
        }

        if verbose:
            print(f"\n  {sym}   scored bars: {int(p.dq_pct.notna().sum()):,}")
            print(f"    Gate 1  shuffled-target null : IC = {ic_null:+.5f}   "
                  f"{'PASS' if passed['null'] else 'FAIL'}")
            print(f"    Gate 2  future canary        : IC = {ic_future:+.5f}   "
                  f"{'PASS' if passed['future'] else 'FAIL'}")
            print(f"    Gate 3  noise canary         : IC = {ic_noise:+.5f}   "
                  f"{'PASS' if passed['noise'] else 'FAIL'}")
            print(f"    Gate 4  shift invariance     : IC {ic_real:+.5f} -> "
                  f"{ic_lagged:+.5f} when lagged one bar")
            # Only meaningful when there is something to degrade. Below the
            # detection floor, "lagged is larger" is two noise draws being
            # compared, not evidence about alignment.
            if abs(ic_real) >= SHIFT_TEST_FLOOR and abs(ic_lagged) > abs(ic_real):
                print("            NOTE: lagging did not degrade the result. Either the")
                print("            score is slow-moving (recompute n_eff) or the")
                print("            alignment is wrong. Investigate before Step 5.")
            elif abs(ic_real) < SHIFT_TEST_FLOOR:
                print(f"            (base IC below the {SHIFT_TEST_FLOOR} floor -- "
                      f"shift test not informative here)")

    res["all_gates_pass"] = all_pass
    if verbose:
        print("\n" + "=" * 74)
        print(f"  ALL GATES: {'PASS' if all_pass else 'FAIL'}")
        if not all_pass:
            print("  Pipeline is not trustworthy on this data. K8 fires; stop.")
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Stage 1 Step 3: pipeline gates")
    ap.add_argument("--data", default=None)
    ap.add_argument("--synthetic", action="store_true")
    args = ap.parse_args(argv)

    if args.data:
        ok = run_real_gates(args.data)["all_gates_pass"]
    else:
        ok = run_synthetic_gates()["all_gates_pass"]
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
