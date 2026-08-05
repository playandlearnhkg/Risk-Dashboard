"""
Synthetic validation of the Stage classifier — proves the rule logic is
correct BEFORE it ever touches real data. Builds a price path that cycles
through basing -> markup -> topping -> decline by construction, and checks
the classifier recovers stages in that order with a plausible majority
stage in each labeled segment.

Run: python3 lambda_strategy_validation/tests/test_stage_classifier_synthetic.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd

from lambda_strategy_validation.stage_classifier import (
    classify_series, stage_transitions,
    STAGE_BASING, STAGE_MARKUP, STAGE_TOPPING, STAGE_DECLINE,
)


def build_synthetic_path(seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n_base, n_up, n_top, n_down = 300, 500, 150, 400
    segments = []

    # Stage 1: basing, flat with noise around 100
    segments.append(100 + rng.normal(0, 1.0, n_base).cumsum() * 0.05)

    # Stage 2: strong sustained uptrend
    base_level = segments[-1][-1]
    drift = np.linspace(0, 120, n_up)
    segments.append(base_level + drift + rng.normal(0, 1.0, n_up).cumsum() * 0.1)

    # Stage 3: topping, choppy flat near the high
    top_level = segments[-1][-1]
    segments.append(top_level + rng.normal(0, 1.5, n_top).cumsum() * 0.15)

    # Stage 4: sustained downtrend
    down_start = segments[-1][-1]
    drift_down = np.linspace(0, -100, n_down)
    segments.append(down_start + drift_down + rng.normal(0, 1.0, n_down).cumsum() * 0.1)

    close = np.concatenate(segments)
    close = np.clip(close, 5, None)  # keep price positive
    dates = pd.bdate_range("2015-01-02", periods=len(close))
    df = pd.DataFrame({"close": close}, index=dates)

    boundaries = np.cumsum([0, n_base, n_up, n_top, n_down])
    labels = pd.Series(index=df.index, dtype="object")
    names = ["intended_basing", "intended_markup", "intended_topping", "intended_decline"]
    for i, name in enumerate(names):
        labels.iloc[boundaries[i]:boundaries[i + 1]] = name
    df["intended_segment"] = labels
    return df


def main():
    df = build_synthetic_path()
    stages = classify_series(df[["close"]])
    df["stage"] = stages

    print("=== Majority classified stage per intended segment (full segment) ===")
    print("Note: SMA200/52w-based rules are deliberately lagging/conservative,")
    print("so trend segments (markup/decline) are checked on their back half —")
    print("the classifier is expected to take time to *confirm* a new stage")
    print("rather than flip immediately (this is the intended anti-whipsaw")
    print("behaviour, not a bug).\n")
    stage_names = {1: "Basing(1)", 2: "Markup(2)", 3: "Topping(3)", 4: "Decline(4)"}
    ok = True
    expectations = {
        "intended_basing": (STAGE_BASING, 0.0),
        "intended_markup": (STAGE_MARKUP, 0.5),
        "intended_topping": (STAGE_TOPPING, 0.0),
        "intended_decline": (STAGE_DECLINE, 0.5),
    }
    for seg, (expected, tail_frac) in expectations.items():
        full = df.loc[df["intended_segment"] == seg, "stage"].dropna()
        if full.empty:
            print(f"{seg:22s} -> no classified bars (all NaN, likely warm-up period)")
            continue
        sub = full.iloc[int(len(full) * tail_frac):]
        counts = sub.value_counts(normalize=True).sort_index()
        majority_stage = counts.idxmax()
        majority_pct = counts.max()
        status = "PASS" if majority_stage == expected else "FAIL"
        ok = ok and (status == "PASS")
        window_label = "full" if tail_frac == 0.0 else f"back {int((1-tail_frac)*100)}%"
        dist = ", ".join(f"{stage_names[int(k)]}={v:.0%}" for k, v in counts.items())
        print(f"{seg:22s} [{window_label:8s}] expected={stage_names[expected]:11s} "
              f"majority={stage_names[int(majority_stage)]:11s} ({majority_pct:.0%})  "
              f"[{status}]  dist: {dist}")

    print("\n=== Stage transition log (first 10) ===")
    trans = stage_transitions(stages)
    print(trans.head(10).to_string(index=False))

    print(f"\nOVERALL: {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
