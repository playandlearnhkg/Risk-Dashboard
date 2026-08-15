"""
stage1.power — Step 2 of the execution order: effective sample size and power.

Answers one question: does this dataset have the statistical resolution to
detect the effect the pre-registration says is plausible (IC 0.01-0.03)?

    python -m stage1.power --data data/clean

A "no" here is Verdict B (INCONCLUSIVE / UNDERPOWERED) and the study stops.
That is a legitimate outcome and it is much cheaper to discover now than after
running every test in the plan.
"""

from __future__ import annotations

import argparse
import sys

from stage1 import core, stats
from stage1.dataset import load_clean, prepare

# Section 4.1 / 8.3 requirements under history Option A.
MIN_BLOCKS = 20
SESSIONS_PER_BLOCK = 63
WARMUP_SESSIONS = 250
HOLDOUT_SESSIONS = 252


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Stage 1 Step 2: power / n_eff")
    ap.add_argument("--data", default="data/clean")
    ap.add_argument("--target-ic", type=float, default=0.015,
                    help="smallest IC the study should be able to detect")
    args = ap.parse_args(argv)

    bars = load_clean(args.data)
    if not bars:
        print("no clean data found; run stage1.validate first")
        return 1

    scores, targets, sessions = {}, {}, {}
    for sym, df in bars.items():
        p = prepare(df, tick=1e-2)
        scores[sym] = p.dq
        targets[sym] = p.r1
        sessions[sym] = int(df.index.normalize().nunique())

    es = stats.effective_sample_size(scores, targets)

    print("=" * 74)
    print("STAGE 1 - STEP 2: EFFECTIVE SAMPLE SIZE AND POWER")
    print("=" * 74)
    print(f"\n  instruments            : {es.k_instruments}  ({', '.join(sorted(bars))})")
    print(f"  scored bar-observations: {es.n_raw:,}")
    print()
    print("  Serial dependence")
    print(f"    lag-1 autocorr, score : {es.lag1_score:+.4f}")
    print(f"    lag-1 autocorr, target: {es.lag1_target:+.4f}")
    print(f"    deflation factor      : {es.serial_factor:.4f}")
    print(f"    n_eff after serial    : {es.n_eff_serial:,}")
    print()
    print("  Cross-sectional dependence")
    print(f"    mean pairwise rho     : {es.rho_bar:+.4f}")
    print(f"    K_eff                 : {es.k_eff:.2f} of {es.k_instruments}")
    print()
    print(f"  n_eff TOTAL             : {es.n_eff_total:,}")

    print("\n  Detectable IC at t = 3.0")
    print("    target IC   n_eff required   available   verdict")
    print("    " + "-" * 56)
    for ic in (0.010, 0.015, 0.020, 0.030, 0.050):
        need = stats.required_n_for_ic(ic, 3.0)
        ok = es.n_eff_total >= need
        print(f"    {ic:9.3f}   {need:14,}   {es.n_eff_total:9,}   "
              f"{'reachable' if ok else 'UNDERPOWERED'}")

    min_sessions = min(sessions.values())
    usable = min_sessions - WARMUP_SESSIONS - HOLDOUT_SESSIONS
    blocks = max(0, usable // SESSIONS_PER_BLOCK)

    print("\n  Block budget (history Option A)")
    print(f"    shortest instrument   : {min_sessions:,} sessions")
    print(f"    minus warm-up ({WARMUP_SESSIONS}) and holdout ({HOLDOUT_SESSIONS}): {usable:,}")
    print(f"    evaluation blocks     : {blocks} of {MIN_BLOCKS} required")

    need = stats.required_n_for_ic(args.target_ic, 3.0)
    power_ok = es.n_eff_total >= need
    blocks_ok = blocks >= MIN_BLOCKS

    print("\n" + "=" * 74)
    if power_ok and blocks_ok:
        print("  PROCEED to Step 3.")
        return 0

    print("  VERDICT B - INCONCLUSIVE / UNDERPOWERED. Stop here.")
    if not power_ok:
        print(f"    n_eff {es.n_eff_total:,} < {need:,} needed for IC {args.target_ic:.3f} at t=3.0")
    if not blocks_ok:
        print(f"    {blocks} evaluation blocks < {MIN_BLOCKS} required by spec 4.1")
        print("    More instruments will NOT fix this: blocks are calendar periods,")
        print("    so breadth adds width per block, never more blocks. Only more")
        print("    history per instrument does.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
