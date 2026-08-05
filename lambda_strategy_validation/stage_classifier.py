"""
stage_classifier.py — Minervini Stage 2 / 3 / 4 exactly as specified in
Sigma's research design, section 2E, using Simple Moving Averages.

Stage 2 (Advancing) — Trend Template, minimum 6 of these 7 criteria:
  1. Close > 50-SMA
  2. Close > 150-SMA
  3. Close > 200-SMA
  4. 50-SMA > 150-SMA
  5. 150-SMA > 200-SMA
  6. 200-SMA sloping upward (200-SMA_t > 200-SMA_{t-21})
  7. Close within 25% of the 52-week high

Stage 4 (Declining):  Close < 200-SMA
Stage 3 (Topping):    Close >= 200-SMA and not Stage 2

WHY THESE THREE ARE A CLEAN PARTITION (not obvious under a 6-of-7 rule):
criterion 2 (Close > 150-SMA) and criterion 5 (150-SMA > 200-SMA) together
imply criterion 3 (Close > 200-SMA) by transitivity. So a day that fails
criterion 3 must also fail criterion 2 or 5 — at least two failures, i.e.
at most 5 of 7 satisfied. Therefore any day meeting the 6-of-7 bar
necessarily has Close > 200-SMA and can never simultaneously be Stage 4.
Stages 2/3/4 are mutually exclusive and exhaustive over all days with
enough history. `assert_partition_valid` checks this empirically too.

Deliberate deviations from the *canonical* Minervini template, to follow
Sigma's document rather than the textbook:
  - Canonical Minervini also requires price >= 25-30% above the 52-week
    low. Sigma's list omits it, so it is NOT applied here.
  - Canonical stage analysis has a Stage 1 (basing). Sigma's design has no
    Stage 1, so days are only ever labelled 2, 3 or 4.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SMA_FAST = 50
SMA_MID = 150
SMA_SLOW = 200
SLOPE_LOOKBACK = 21           # "200-SMA_t > 200-SMA_{t-21}"
LOOKBACK_52W = 252
WITHIN_52W_HIGH = 0.25        # Close >= 75% of the 52-week high
MIN_STAGE2_CRITERIA = 6       # "preferably all criteria, minimum 6 of 7"

STAGE_MARKUP = 2
STAGE_TOPPING = 3
STAGE_DECLINE = 4

CRITERIA_COLUMNS = [f"c{i}" for i in range(1, 8)]


def compute_stage_frame(daily: pd.DataFrame) -> pd.DataFrame:
    """
    daily: DataFrame indexed by trading date (ascending) with a 'close'
    column (case-insensitive). Returns a frame with the SMAs, each of the
    seven criteria as a boolean column c1..c7, `n_criteria`, and `stage`.

    `stage` is NaN until there is enough history for the 200-SMA, the
    21-day slope reference and the 52-week high (i.e. the first
    200+21 / 252 bars, whichever binds later).
    """
    df = daily.copy()
    df.columns = [c.lower() for c in df.columns]
    if "close" not in df.columns:
        raise ValueError("daily frame must have a 'close' column")

    close = df["close"]
    sma50 = close.rolling(SMA_FAST).mean()
    sma150 = close.rolling(SMA_MID).mean()
    sma200 = close.rolling(SMA_SLOW).mean()
    high_52w = close.rolling(LOOKBACK_52W, min_periods=LOOKBACK_52W).max()

    df["sma50"], df["sma150"], df["sma200"] = sma50, sma150, sma200
    df["high_52w"] = high_52w

    df["c1"] = close > sma50
    df["c2"] = close > sma150
    df["c3"] = close > sma200
    df["c4"] = sma50 > sma150
    df["c5"] = sma150 > sma200
    df["c6"] = sma200 > sma200.shift(SLOPE_LOOKBACK)
    df["c7"] = close >= (1 - WITHIN_52W_HIGH) * high_52w

    # A day is only classifiable once every input exists; otherwise the
    # booleans above silently read False and would fake a Stage 4.
    ready = (
        sma50.notna() & sma150.notna() & sma200.notna()
        & sma200.shift(SLOPE_LOOKBACK).notna() & high_52w.notna()
    )

    df["n_criteria"] = df[CRITERIA_COLUMNS].sum(axis=1).where(ready)

    is_stage2 = ready & (df["n_criteria"] >= MIN_STAGE2_CRITERIA)
    is_stage4 = ready & (close < sma200)

    stage = pd.Series(np.nan, index=df.index, dtype="float64")
    stage[ready] = STAGE_TOPPING          # default for classifiable days
    stage[is_stage4] = STAGE_DECLINE
    stage[is_stage2] = STAGE_MARKUP       # takes precedence; proven disjoint
    df["stage"] = stage
    return df


def classify_series(daily: pd.DataFrame) -> pd.Series:
    """Convenience wrapper returning just the stage Series."""
    return compute_stage_frame(daily)["stage"]


def assert_partition_valid(frame: pd.DataFrame) -> None:
    """
    Empirically verify the Stage 2 / Stage 4 disjointness argued in the
    module docstring. Raises if a single day ever satisfies both.
    """
    ready = frame["stage"].notna()
    both = ready & (frame["n_criteria"] >= MIN_STAGE2_CRITERIA) & (
        frame["close"] < frame["sma200"]
    )
    if bool(both.any()):
        raise AssertionError(
            f"{int(both.sum())} day(s) satisfy Stage 2 and Stage 4 at once — "
            "the 6-of-7 disjointness argument is violated."
        )


def stage_transitions(stages: pd.Series) -> pd.DataFrame:
    """One row per stage change: date, from_stage, to_stage."""
    s = stages.dropna()
    if s.empty:
        return pd.DataFrame(columns=["date", "from_stage", "to_stage"])
    changed = s != s.shift(1)
    changed.iloc[0] = False
    return pd.DataFrame({
        "date": s.index[changed],
        "from_stage": s.shift(1)[changed].to_numpy(),
        "to_stage": s[changed].to_numpy(),
    }).reset_index(drop=True)
