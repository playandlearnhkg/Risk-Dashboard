"""
Validation of the Sigma-spec Stage 2/3/4 classifier.

Two independent checks:

1. HAND-COMPUTED CASES — a few constructed price paths whose Stage label
   can be worked out by hand, verifying the 6-of-7 rule, the Stage 4
   rule and the Stage 3 residual behave exactly as the spec says.

2. SYNTHETIC REGIME PATH — a price path built to cycle through a long
   advance, a topping phase and a decline; the classifier must recover
   Stage 2 in the advance and Stage 4 in the decline. Trend segments are
   scored on their back half because SMA200-based rules are intentionally
   lagging (confirmation, not prediction).

Also asserts the Stage2/Stage4 partition can never overlap.

Run: python3 lambda_strategy_validation/tests/test_stage_classifier_synthetic.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd

from lambda_strategy_validation.stage_classifier import (
    compute_stage_frame, assert_partition_valid,
    STAGE_MARKUP, STAGE_TOPPING, STAGE_DECLINE,
)

STAGE_NAMES = {2: "Markup(2)", 3: "Topping(3)", 4: "Decline(4)"}


def _frame(close: np.ndarray) -> pd.DataFrame:
    idx = pd.bdate_range("2010-01-04", periods=len(close))
    return pd.DataFrame({"close": close}, index=idx)


def hand_computed_cases() -> bool:
    """Each case: build a path, assert the final day's label."""
    ok = True
    n = 700

    # Case 1: relentless steady advance -> all 7 criteria -> Stage 2.
    steady_up = np.linspace(100, 300, n)
    # Case 2: price far below a falling long average -> Stage 4.
    steady_down = np.linspace(300, 100, n)
    # Case 3: long advance then a sharp drop that puts price under the
    # 200-SMA but leaves the 200-SMA still rising -> must be Stage 4
    # (Sigma's Stage 4 is purely Close < 200-SMA, regardless of slope).
    crash = np.concatenate([np.linspace(100, 300, n - 40),
                            np.linspace(300, 150, 40)])
    # Case 4: advance, then a long decline, then a partial rally. The
    # rally lifts price back above the 200-SMA (so NOT Stage 4) but is too
    # young to repair the 150>200 alignment or turn the 200-SMA up, so it
    # fails 2+ criteria and must land in the Stage 3 residual bucket.
    # This is the natural shape of a Stage 3: recovering, not yet advancing.
    top = np.concatenate([np.linspace(100, 300, 300),
                          np.linspace(300, 180, 300),
                          np.linspace(180, 235, 60)])

    cases = [
        ("steady advance", steady_up, STAGE_MARKUP),
        ("steady decline", steady_down, STAGE_DECLINE),
        ("advance then crash below 200SMA", crash, STAGE_DECLINE),
        ("advance then topping drift", top, STAGE_TOPPING),
    ]

    print("=== Hand-computed cases (label of final day) ===")
    for name, path, expected in cases:
        f = compute_stage_frame(_frame(path))
        assert_partition_valid(f)
        last = f.iloc[-1]
        got = last["stage"]
        status = "PASS" if got == expected else "FAIL"
        ok = ok and status == "PASS"
        crit = "".join("1" if last[f"c{i}"] else "0" for i in range(1, 8))
        print(f"  {name:34s} expected={STAGE_NAMES[expected]:11s} "
              f"got={STAGE_NAMES.get(got, got):11s} "
              f"criteria={crit} n={last['n_criteria']:.0f}  [{status}]")
    return ok


def build_synthetic_path(seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n_base, n_up, n_top, n_down = 300, 500, 150, 400
    seg = [100 + rng.normal(0, 1.0, n_base).cumsum() * 0.05]
    seg.append(seg[-1][-1] + np.linspace(0, 120, n_up)
               + rng.normal(0, 1.0, n_up).cumsum() * 0.1)
    seg.append(seg[-1][-1] + rng.normal(0, 1.5, n_top).cumsum() * 0.15)
    seg.append(seg[-1][-1] + np.linspace(0, -140, n_down)
               + rng.normal(0, 1.0, n_down).cumsum() * 0.1)
    close = np.clip(np.concatenate(seg), 5, None)
    df = _frame(close)
    bounds = np.cumsum([0, n_base, n_up, n_top, n_down])
    labels = pd.Series(index=df.index, dtype="object")
    for i, nm in enumerate(["basing", "advance", "topping", "decline"]):
        labels.iloc[bounds[i]:bounds[i + 1]] = nm
    df["segment"] = labels
    return df


def synthetic_regime_case() -> bool:
    df = build_synthetic_path()
    f = compute_stage_frame(df[["close"]])
    assert_partition_valid(f)
    f["segment"] = df["segment"]

    print("\n=== Synthetic regime path ===")
    print("(trend segments scored on their back half — SMA200 rules confirm,")
    print(" they do not predict, so early-segment lag is expected)\n")
    expectations = {"advance": (STAGE_MARKUP, 0.5), "decline": (STAGE_DECLINE, 0.5)}
    ok = True
    for seg, (expected, tail) in expectations.items():
        s = f.loc[f["segment"] == seg, "stage"].dropna()
        if s.empty:
            print(f"  {seg:10s} -> no classifiable bars (warm-up)")
            continue
        s = s.iloc[int(len(s) * tail):]
        counts = s.value_counts(normalize=True).sort_index()
        majority = counts.idxmax()
        status = "PASS" if majority == expected else "FAIL"
        ok = ok and status == "PASS"
        dist = ", ".join(f"{STAGE_NAMES[int(k)]}={v:.0%}" for k, v in counts.items())
        print(f"  {seg:10s} expected={STAGE_NAMES[expected]:11s} "
              f"majority={STAGE_NAMES[int(majority)]:11s} ({counts.max():.0%})  "
              f"[{status}]  {dist}")
    return ok


def main() -> None:
    ok = hand_computed_cases()
    ok = synthetic_regime_case() and ok
    print(f"\nOVERALL: {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
