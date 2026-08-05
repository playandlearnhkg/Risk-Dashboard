"""
stage_classifier.py — Weinstein Stage 1-4 classification via the Minervini
Trend Template (50/150/200-day SMA).

STATUS: standard-definition implementation, pending reconciliation against
Sigma's exact Stage 2/3/4 spec (not yet shared — placeholder in the brief).
If Sigma's definitions differ (different SMA windows, different slope lookback,
different 52-week thresholds), only the constants and the two boolean rule
functions below need to change; everything downstream (universe filters,
cost model, test battery) is stage-definition-agnostic.

Rules implemented (industry-standard Weinstein/Minervini synthesis):

Stage 2 (Markup) — ALL of:
  1. Close > SMA150 and Close > SMA200
  2. SMA150 > SMA200
  3. SMA200 has been rising for >= SLOPE_LOOKBACK trading days (~1 month)
  4. SMA50 > SMA150 > SMA200          (correct stacking order)
  5. Close > SMA50
  6. Close >= (1 + MIN_ABOVE_52W_LOW) * rolling 52-week low
  7. Close >= (1 - MAX_BELOW_52W_HIGH) * rolling 52-week high

Stage 4 (Decline) — mirror image of Stage 2 (all six inequalities flipped).

Stage 1 (Basing) / Stage 3 (Topping) are NOT independently defined by a
snapshot of moving averages — by construction, anything failing both the
Stage 2 and Stage 4 checks is a transition/consolidation regime, and
Weinstein's own framework distinguishes "basing after a decline" (Stage 1)
from "topping after an advance" (Stage 3) using the prior confirmed stage.
We track that with a small state machine (see `classify_series`):
  - coming from {Stage 4, Stage 1} and failing both checks -> Stage 1
  - coming from {Stage 2, Stage 3} and failing both checks -> Stage 3
  - first classifiable bar with no history -> Stage 1 (conservative default)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SMA_FAST = 50
SMA_MID = 150
SMA_SLOW = 200
SLOPE_LOOKBACK = 21          # ~1 trading month, for "SMA200 rising/falling"
LOOKBACK_52W = 252           # trading days
MIN_ABOVE_52W_LOW = 0.25     # Stage 2 requires price >= 25% above 52w low
MAX_BELOW_52W_HIGH = 0.25    # Stage 2 requires price within 25% of 52w high

STAGE_BASING = 1
STAGE_MARKUP = 2
STAGE_TOPPING = 3
STAGE_DECLINE = 4


def compute_indicators(daily: pd.DataFrame) -> pd.DataFrame:
    """
    daily: DataFrame indexed by date, ascending, with a 'close' column
    (case-insensitive). Returns a copy with sma50/150/200, sma200_slope_up/
    down flags, and rolling 52-week high/low columns appended.
    """
    df = daily.copy()
    df.columns = [c.lower() for c in df.columns]
    if "close" not in df.columns:
        raise ValueError("daily frame must have a 'close' column")

    close = df["close"]
    df["sma50"] = close.rolling(SMA_FAST).mean()
    df["sma150"] = close.rolling(SMA_MID).mean()
    df["sma200"] = close.rolling(SMA_SLOW).mean()

    sma200_lag = df["sma200"].shift(SLOPE_LOOKBACK)
    df["sma200_rising"] = df["sma200"] > sma200_lag
    df["sma200_falling"] = df["sma200"] < sma200_lag

    df["low_52w"] = close.rolling(LOOKBACK_52W, min_periods=LOOKBACK_52W).min()
    df["high_52w"] = close.rolling(LOOKBACK_52W, min_periods=LOOKBACK_52W).max()
    return df


def _is_stage2(row: pd.Series) -> bool:
    c, s50, s150, s200 = row["close"], row["sma50"], row["sma150"], row["sma200"]
    if any(pd.isna(x) for x in (s50, s150, s200, row["low_52w"], row["high_52w"])):
        return False
    return (
        c > s150 and c > s200
        and s150 > s200
        and bool(row["sma200_rising"])
        and s50 > s150 > s200
        and c > s50
        and c >= (1 + MIN_ABOVE_52W_LOW) * row["low_52w"]
        and c >= (1 - MAX_BELOW_52W_HIGH) * row["high_52w"]
    )


def _is_stage4(row: pd.Series) -> bool:
    c, s50, s150, s200 = row["close"], row["sma50"], row["sma150"], row["sma200"]
    if any(pd.isna(x) for x in (s50, s150, s200, row["low_52w"], row["high_52w"])):
        return False
    return (
        c < s150 and c < s200
        and s150 < s200
        and bool(row["sma200_falling"])
        and s50 < s150 < s200
        and c < s50
        and c <= (1 - MIN_ABOVE_52W_LOW) * row["high_52w"]
        and c <= (1 + MAX_BELOW_52W_HIGH) * row["low_52w"]
    )


def classify_series(daily: pd.DataFrame) -> pd.Series:
    """
    Returns an integer Series (1-4) aligned to `daily`'s index. Bars before
    enough history exists for all indicators are NaN.
    """
    df = compute_indicators(daily)
    stages = pd.Series(index=df.index, dtype="float64")
    prev_stage = None

    for ts, row in df.iterrows():
        if pd.isna(row["sma200"]) or pd.isna(row["low_52w"]):
            stages.loc[ts] = np.nan
            continue
        if _is_stage2(row):
            stage = STAGE_MARKUP
        elif _is_stage4(row):
            stage = STAGE_DECLINE
        else:
            if prev_stage in (STAGE_MARKUP, STAGE_TOPPING):
                stage = STAGE_TOPPING
            else:
                stage = STAGE_BASING
        stages.loc[ts] = stage
        prev_stage = stage

    return stages


def stage_transitions(stages: pd.Series) -> pd.DataFrame:
    """
    Returns one row per stage change: date, from_stage, to_stage.
    Useful for finding Stage-2 entry dates (from != 2, to == 2).
    """
    s = stages.dropna()
    changed = s != s.shift(1)
    changed.iloc[0] = False
    out = pd.DataFrame({
        "date": s.index[changed],
        "from_stage": s.shift(1)[changed].values,
        "to_stage": s[changed].values,
    })
    return out.reset_index(drop=True)
