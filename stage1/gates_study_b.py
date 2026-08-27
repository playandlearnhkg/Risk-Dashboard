"""
stage1.gates_study_b — Study B Step 3: pipeline canaries on the session file.

These validate the CODE, not the hypothesis. A leaking pipeline makes every
other safeguard cosmetic, so no real result may be reported until all four
pass. K8 fires on any failure.

    python -m stage1.gates_study_b --file results/study_b/opening.parquet

Gate 1  synthetic null   : target shuffled across sessions -> IC ~ 0
Gate 2  future canary    : a score that IS the target -> IC ~ 1
Gate 3  noise canary     : an i.i.d. score -> IC ~ 0
Gate 4  shift invariance : lagging the score one SESSION must destroy a known
                           relationship

WHY GATE 4 IS PROBED WITH THE FUTURE CANARY, NOT WITH DQ
--------------------------------------------------------
Run 1's Gate 4 compared IC(DQ, r_1) against IC(DQ.shift(1), r_1). That form
computes the real score-target IC, which for Study B IS the Step 5 statistic —
and Step 5 has not been authorised. Running it here "just as a canary" would
be computing the official result and then claiming not to have looked.

So Gate 4 is probed with the future canary instead: a score that equals the
target must show IC ~ 1 unshifted and collapse toward 0 when lagged one
session. That tests exactly the machinery Gate 4 exists to test — that a
one-period shift actually moves the alignment — and it is a STRICTER probe
than the DQ version, because the unshifted relationship is known to be perfect
rather than merely hoped to be non-zero. No DQ-to-target correlation is
computed anywhere in this module.

The holdout is split off first and never read.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np
import pandas as pd

from stage1 import core
from stage1.power_study_b import split_holdout_sessions

FUTURE_IC_MIN = 0.95
SHIFT_COLLAPSE_MAX = 0.10      # lagged future canary must fall below this

# Run 1's fixed tolerance, kept only so both readings can be reported.
RUN1_NULL_IC_TOLERANCE = 0.02

# THE NULL CANARIES ARE SCALED BY SAMPLE SIZE. Run 1 hard-coded |IC| < 0.02 on
# ~300,000 bar-observations per instrument, where the sampling SE of a Spearman
# IC is ~1/sqrt(n) = 0.0018 - so 0.02 was an 11-SE excursion and a genuine
# alarm. Study B has ~3,000 session-observations, SE ~0.0183, and the SAME
# 0.02 is 1.1 SE: ordinary noise. Carried over unchanged it does not test the
# pipeline, it tests whether a coin landed heads.
#
# The threshold is therefore expressed in SE units. NULL_Z IS CHOSEN BY RULE,
# NOT BY WHAT PASSES: Bonferroni over the null-gate family (5 instruments x 2
# targets x 2 gates = 20 comparisons) at family-wise alpha = 0.01 gives a
# per-test two-sided alpha of 0.0005, hence z = 3.481.
#
# This is a change to canary CALIBRATION, not to any decision gate, kill
# condition or hypothesis. It is reported alongside the Run 1 reading so the
# difference is visible rather than absorbed.
NULL_GATE_FAMILY = 20
NULL_Z = 3.481


def _null_tolerance(n: int) -> float:
    """Sample-size-scaled tolerance for a null-hypothesis canary."""
    return NULL_Z / np.sqrt(max(1, n))


def run(df: pd.DataFrame, target: str, verbose: bool = True) -> dict:
    per: dict[str, dict] = {}
    all_pass = True

    for sym, g in df.groupby("ticker"):
        g = g.sort_index()
        mask = g["DQ_pct"].notna() & g[target].notna()
        score = g.loc[mask, "DQ_pct"]
        y = g.loc[mask, target]

        # Gate 1 — destroy the relationship, keep the marginals.
        rng = np.random.default_rng(11)
        shuffled = pd.Series(rng.permutation(y.to_numpy()), index=y.index)
        ic_null = core.information_coefficient(score, shuffled)

        # Gate 2 — the target as its own score.
        ic_future = core.information_coefficient(y, y)

        # Gate 3 — i.i.d. noise as a score.
        rng = np.random.default_rng(13)
        noise = pd.Series(rng.normal(size=len(y)), index=y.index)
        ic_noise = core.information_coefficient(noise, y)

        # Gate 4 — lag the future canary by one SESSION. A perfect relationship
        # must collapse; if it does not, the shift is not moving the alignment.
        ic_shift = core.information_coefficient(y.shift(1), y)

        n = int(len(y))
        tol = _null_tolerance(n)
        se = 1.0 / np.sqrt(max(1, n))

        passed = {
            "null": bool(abs(ic_null) < tol),
            "future": bool(ic_future > FUTURE_IC_MIN),
            "noise": bool(abs(ic_noise) < tol),
            "shift": bool(abs(ic_shift) < SHIFT_COLLAPSE_MAX),
        }
        all_pass &= all(passed.values())

        per[sym] = {"n": n, "null_tolerance": float(tol),
                    "ic_null": ic_null, "z_null": float(abs(ic_null) / se),
                    "ic_future": ic_future,
                    "ic_noise": ic_noise, "z_noise": float(abs(ic_noise) / se),
                    "ic_future_lagged": ic_shift,
                    "pass_null_at_run1_fixed_0.02":
                        bool(abs(ic_null) < RUN1_NULL_IC_TOLERANCE),
                    "pass_noise_at_run1_fixed_0.02":
                        bool(abs(ic_noise) < RUN1_NULL_IC_TOLERANCE),
                    **{f"pass_{k}": v for k, v in passed.items()}}

        if verbose:
            print(f"\n  {sym}  ({target})   n = {n:,}   SE = {se:.5f}   "
                  f"null tolerance = {tol:.5f}")
            print(f"    Gate 1  synthetic null   : IC = {ic_null:+.5f}  "
                  f"({abs(ic_null) / se:.2f} SE)   "
                  f"{'PASS' if passed['null'] else 'FAIL'}")
            print(f"    Gate 2  future canary    : IC = {ic_future:+.5f}   "
                  f"{'PASS' if passed['future'] else 'FAIL'}")
            print(f"    Gate 3  noise canary     : IC = {ic_noise:+.5f}  "
                  f"({abs(ic_noise) / se:.2f} SE)   "
                  f"{'PASS' if passed['noise'] else 'FAIL'}")
            print(f"    Gate 4  shift invariance : IC {ic_future:+.5f} -> "
                  f"{ic_shift:+.5f} lagged one session   "
                  f"{'PASS' if passed['shift'] else 'FAIL'}")

    return {"target": target, "per_instrument": per, "all_pass": all_pass}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Study B Step 3: pipeline canaries")
    ap.add_argument("--file", default="results/study_b/opening.parquet")
    ap.add_argument("--out", default="results/study_b/canaries.json")
    args = ap.parse_args(argv)

    df = pd.read_parquet(args.file)
    ev, _ = split_holdout_sessions(df)

    print("=" * 74)
    print("STUDY B - STEP 3: PIPELINE CANARIES")
    print("  Gate 4 is probed with the future canary; no DQ-to-target IC is")
    print("  computed in this module. The holdout is not read.")
    print("=" * 74)

    results = [run(ev, t) for t in ("T2", "T3")]
    all_pass = all(r["all_pass"] for r in results)

    # Both readings, so the recalibration is visible rather than absorbed.
    zs = [max(v["z_null"], v["z_noise"])
          for r in results for v in r["per_instrument"].values()]
    run1_fails = sum(
        (not v["pass_null_at_run1_fixed_0.02"])
        + (not v["pass_noise_at_run1_fixed_0.02"])
        for r in results for v in r["per_instrument"].values())

    print("\n" + "=" * 74)
    print(f"  max |IC| across all null/noise canaries : {max(zs):.2f} SE")
    print(f"  at Run 1's fixed 0.02 tolerance         : {run1_fails} of "
          f"{NULL_GATE_FAMILY} would fail")
    print(f"  at the sample-size-scaled tolerance     : "
          f"{sum(1 for r in results for v in r['per_instrument'].values() if not (v['pass_null'] and v['pass_noise']))}"
          f" of {NULL_GATE_FAMILY} fail")
    print("  The 0.02 figure is 11 SE at Run 1's n and 1.1 SE at Study B's n;")
    print("  see the NULL_Z note in this module for why the threshold scales.")
    print()
    for r in results:
        print(f"  {r['target']}: {'PASS' if r['all_pass'] else 'FAIL'}")
    print(f"  ALL CANARIES: {'PASS' if all_pass else 'FAIL'}")
    if not all_pass:
        print("  K8 fires. Stop; do not run Step 5.")

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump({"all_pass": all_pass, "results": results}, fh, indent=2)
    print(f"\n  written -> {out_path}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
