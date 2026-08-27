"""
stage1.power_study_b — Study B Step 2: effective sample size and power.

Answers one question, separately for T2 and T3: does this dataset have the
resolution to detect the effect docs/preregistration-study-B.yaml calls
plausible (IC 0.01-0.03)?

    python -m stage1.power_study_b --file results/study_b/opening.parquet

NO INFORMATION COEFFICIENT IS COMPUTED HERE. `stats.effective_sample_size`
takes the score and the target, but uses only their lag-1 autocorrelations and
the cross-sectional correlation OF THE TARGETS. It never correlates score with
target, so nothing in this module is the Step 5 statistic.

rho_bar IS MEASURED ON THE OPENING-BAR SERIES. The yaml records every planning
rho_bar as an assumption and requires this measurement before Step 5
(`rho_bar_measured_at_step_2: true`). Run 1's 0.79 was all-day 5-minute bars
on a different universe and is NOT reused.

The holdout is split off first and never read.
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys

import pandas as pd

from stage1 import stats

# All frozen in docs/preregistration-study-B.yaml.
SESSIONS_PER_BLOCK = 63
MIN_BLOCKS = 20
WARMUP_SESSIONS = 250
HOLDOUT_SESSIONS = 252
T_CRIT_SINGLE = 3.0
T_CRIT_TWO_TRIAL = 3.21        # Bonferroni over the {T2, T3} family
PLAUSIBLE_BAND = (0.01, 0.03)
FROZEN_DETECTABLE = (0.040, 0.046)
SUSPICION_IC = 0.05


def split_holdout_sessions(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Seal the last HOLDOUT_SESSIONS calendar sessions. Never read the second."""
    sessions = pd.DatetimeIndex(sorted(df.index.unique()))
    if len(sessions) <= HOLDOUT_SESSIONS:
        return df.iloc[:0], df
    cutoff = sessions[-HOLDOUT_SESSIONS]
    return df[df.index < cutoff], df[df.index >= cutoff]


def analyse(ev: pd.DataFrame, target: str) -> dict:
    scores, targets = {}, {}
    for sym, g in ev.groupby("ticker"):
        mask = g["DQ_pct"].notna() & g[target].notna()
        scores[sym] = g.loc[mask, "DQ_pct"]
        targets[sym] = g.loc[mask, target]

    es = stats.effective_sample_size(scores, targets)

    per_instrument = {s: int(len(targets[s])) for s in sorted(targets)}
    blocks = int(ev.loc[ev[target].notna() & ev["DQ_pct"].notna(), "block"].nunique())

    out = {
        "target": target,
        "instruments": es.k_instruments,
        "usable_sessions_per_instrument": per_instrument,
        "mean_usable_sessions": round(
            sum(per_instrument.values()) / max(1, len(per_instrument)), 1),
        "n_raw": es.n_raw,
        "lag1_score": round(es.lag1_score, 5),
        "lag1_target": round(es.lag1_target, 5),
        "serial_factor": round(es.serial_factor, 5),
        "n_eff_serial": es.n_eff_serial,
        "rho_bar_measured": round(es.rho_bar, 5),
        "k_eff": round(es.k_eff, 4),
        "n_eff_total": es.n_eff_total,
        "calendar_blocks": blocks,
        "blocks_ok": blocks >= MIN_BLOCKS,
    }
    for t, label in ((T_CRIT_SINGLE, "single"), (T_CRIT_TWO_TRIAL, "two_trial")):
        out[f"detectable_ic_{label}"] = round(t / math.sqrt(max(1, es.n_eff_total)), 5)
    out["detects_plausible_band_top"] = (
        out["detectable_ic_two_trial"] <= PLAUSIBLE_BAND[1])
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Study B Step 2: power / n_eff")
    ap.add_argument("--file", default="results/study_b/opening.parquet")
    ap.add_argument("--out", default="results/study_b/power.json")
    args = ap.parse_args(argv)

    df = pd.read_parquet(args.file)
    ev, holdout = split_holdout_sessions(df)

    print("=" * 74)
    print("STUDY B - STEP 2: EFFECTIVE SAMPLE SIZE AND POWER")
    print("  No IC is computed here. The holdout is split off and not read.")
    print("=" * 74)
    print(f"\n  evaluation sessions : {ev.index.nunique():,}"
          f"   holdout sealed: {holdout.index.nunique():,}")
    print(f"  warm-up already applied by the selector: {WARMUP_SESSIONS} sessions"
          f" (percentile min_obs)")

    results = [analyse(ev, t) for t in ("T2", "T3")]

    for r in results:
        print(f"\n--- {r['target']}"
              f"{'  (PRIMARY, gates the verdict)' if r['target'] == 'T2' else '  (second pre-declared target, reported)'} ---")
        print(f"  usable sessions/instrument : "
              + "  ".join(f"{k} {v:,}" for k, v in r["usable_sessions_per_instrument"].items()))
        print(f"  mean usable sessions       : {r['mean_usable_sessions']:,.1f}")
        print(f"  raw observations           : {r['n_raw']:,}")
        print(f"  lag-1 autocorr score/target: {r['lag1_score']:+.4f} / {r['lag1_target']:+.4f}")
        print(f"  serial deflation factor    : {r['serial_factor']:.4f}"
              f"  -> n_eff_serial {r['n_eff_serial']:,}")
        print(f"  rho_bar MEASURED (open bar): {r['rho_bar_measured']:+.4f}")
        print(f"  K_eff                      : {r['k_eff']:.3f} of {r['instruments']}")
        print(f"  n_eff TOTAL                : {r['n_eff_total']:,}")
        print(f"  calendar blocks            : {r['calendar_blocks']} of {MIN_BLOCKS} required"
              f"   {'OK' if r['blocks_ok'] else 'SHORT'}")
        print(f"  detectable IC  t=3.00      : {r['detectable_ic_single']:.4f}")
        print(f"  detectable IC  t=3.21      : {r['detectable_ic_two_trial']:.4f}"
              f"   (two-trial, the frozen critical value)")

    print("\n" + "=" * 74)
    print("  VERDICT B CHECK against the frozen expectation")
    print(f"  frozen expected detectable IC : {FROZEN_DETECTABLE[0]:.3f}-{FROZEN_DETECTABLE[1]:.3f}")
    print(f"  plausible effect band         : {PLAUSIBLE_BAND[0]:.2f}-{PLAUSIBLE_BAND[1]:.2f}")
    for r in results:
        d = r["detectable_ic_two_trial"]
        inside = FROZEN_DETECTABLE[0] <= d <= FROZEN_DETECTABLE[1]
        print(f"  {r['target']}: measured {d:.4f}  "
              f"{'within' if inside else 'OUTSIDE'} the frozen range;  "
              f"{'CANNOT' if d > PLAUSIBLE_BAND[1] else 'can'} detect the top of the band"
              f"{'   (>= suspicion threshold 0.05)' if d >= SUSPICION_IC else ''}")

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump({"evaluation_sessions": int(ev.index.nunique()),
                   "holdout_sessions": int(holdout.index.nunique()),
                   "results": results}, fh, indent=2)
    print(f"\n  written -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
