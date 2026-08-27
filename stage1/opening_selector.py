"""
stage1.opening_selector — Study B Step 4: bars -> one row per session.

The thin additive module docs/spec-study-B.md 10 allows, and nothing more. It
does NOT score, does NOT test, and computes NO information coefficient. It
emits a session-indexed file that Run 1's existing Step 5 machinery can consume
exactly as it consumes bar-level r_1 today.

    python -m stage1.opening_selector --data data/study_b/clean \
        --out results/study_b/opening.parquet

What it does, in order:

  1. Applies eligibility E1-E6 per session, at the FROZEN thresholds
     (eligibility_study_b.FROZEN_RULE, = docs/preregistration-study-B.yaml
     data.eligibility_rule). The rule is imported, never re-implemented.
  2. Reads DQ / DIR / CONV that core.candle_features already computed, on the
     09:30 row only. The score is untouched: the opening bar is scored by the
     identical function that scored every bar in Run 1.
  3. Builds T1 / T2 / T3 from closes in the same validated frame, all divided
     by ATR_20 at the last bar of the PRIOR session (causal by construction).
  4. Applies the trailing percentile in SESSION units - window 500, min_obs
     250, tod_bucketed false - which is the one genuinely new design decision
     here and is frozen in the yaml, not chosen in this file.
  5. Assigns CALENDAR block ids from the shared session calendar of all five
     instruments, so block n means the same dates for every name.

HALF-DAY HANDLING FOR T3. The yaml fixes T3's endpoint as the official RTH
close: the 15:55 open-labelled bar, or on an early-close half-day the session's
own last bar. Those two cases are distinguished structurally, not by guessing:
if the session's grid does not extend to 15:55 the session is short and its
last bar is the endpoint; if the grid reaches 15:55 but that bar carries no
price, the endpoint is genuinely missing and T3 is NaN. Note this makes the
T3 count here slightly HIGHER than usable_T3 in docs/STUDY_B_ELIGIBILITY.md,
which counted strict 15:55 presence and so charged half-days as missing.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

import numpy as np
import pandas as pd

from stage1 import core
from stage1.coverage_study_b import (OPEN_MIN, T2_END_MIN, T3_END_MIN,
                                     T_ENTRY_MIN, TICK_SIZE)
from stage1.dataset import global_block_map, load_clean, load_tick_sizes
from stage1.eligibility_study_b import (FROZEN_RULE, apply_rule, session_frame)

# Frozen in docs/preregistration-study-B.yaml (normalisation:). Session units,
# not bars: Study B has one observation per session, so a 500-BAR window would
# silently mean 500 sessions' worth of a single slot in Run 1's scheme and
# something else entirely here.
PCT_WINDOW_SESSIONS = 500
PCT_MIN_OBS_SESSIONS = 250
SESSIONS_PER_BLOCK = 63


def _close_at(bars: pd.DataFrame, minute: int) -> pd.Series:
    """Close of the bar at a given minute-of-day, indexed by session date."""
    mins = bars.index.hour * 60 + bars.index.minute
    sel = mins == minute
    s = pd.Series(bars["close"].to_numpy()[sel],
                  index=bars.index.normalize()[sel])
    return s[~s.index.duplicated(keep="first")]


def _session_last_close(bars: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Last PRICED close of each session, and the session's last grid minute."""
    day = bars.index.normalize()
    mins = pd.Series(bars.index.hour * 60 + bars.index.minute, index=bars.index)
    priced = bars["close"].notna()
    live = bars[priced]
    last_close = live.groupby(live.index.normalize())["close"].last()
    last_grid_minute = mins.groupby(day).max()
    return last_close, last_grid_minute


def build_one(ticker: str, bars: pd.DataFrame, tick: float) -> pd.DataFrame:
    feats = core.candle_features(bars, tick)

    # --- Eligibility, imported at the frozen thresholds --------------------
    sf = session_frame(ticker, bars)
    cond = apply_rule(sf, **FROZEN_RULE)

    idx = sf.index                                   # session dates

    # --- Score on the 09:30 row only ---------------------------------------
    mins = bars.index.hour * 60 + bars.index.minute
    sel = mins == OPEN_MIN
    open_day = bars.index.normalize()[sel]

    def at_open(col: str) -> pd.Series:
        s = pd.Series(feats[col].to_numpy()[sel], index=open_day)
        return s[~s.index.duplicated(keep="first")].reindex(idx)

    out = pd.DataFrame(index=idx)
    out.index.name = "session"
    out["ticker"] = ticker
    out["eligible"] = cond["eligible"].reindex(idx).fillna(False)
    for c in ("DQ", "DIR", "CONV"):
        out[c] = at_open(c)
    out["atr_prev"] = at_open("atr_prev")

    # --- Targets ------------------------------------------------------------
    c_open = _close_at(bars, OPEN_MIN).reindex(idx)
    c_entry = _close_at(bars, T_ENTRY_MIN).reindex(idx)
    c_t2 = _close_at(bars, T2_END_MIN).reindex(idx)

    c_1555 = _close_at(bars, T3_END_MIN).reindex(idx)
    last_close, last_minute = _session_last_close(bars)
    last_close = last_close.reindex(idx)
    last_minute = last_minute.reindex(idx)
    # Half-day: the grid never reaches 15:55, so the session's last bar IS the
    # close. Full day with an unpriced 15:55: the endpoint is missing, NaN.
    is_half_day = last_minute < T3_END_MIN
    c_t3 = c_1555.where(~is_half_day, last_close)

    atr = out["atr_prev"]
    out["T1"] = (c_entry - c_open) / atr
    out["T2"] = (c_t2 - c_entry) / atr
    out["T3"] = (c_t3 - c_entry) / atr
    out["half_day"] = is_half_day.fillna(False)

    # Ineligible sessions produce NO observation. Masking here rather than
    # filtering keeps the session index intact for the block map and makes the
    # attrition visible downstream instead of silently absent.
    mask = out["eligible"]
    for c in ("DQ", "DIR", "CONV", "T1", "T2", "T3"):
        out[c] = out[c].where(mask)

    # --- Session-unit trailing percentile -----------------------------------
    for c in ("DQ", "DIR", "CONV"):
        out[f"{c}_pct"] = core.trailing_percentile(
            out[c], window=PCT_WINDOW_SESSIONS,
            min_obs=PCT_MIN_OBS_SESSIONS, by_time_of_day=False)

    return out


def build(data_dir: str, verbose: bool = True) -> pd.DataFrame:
    bars = load_clean(data_dir)
    ticks = load_tick_sizes(data_dir)
    if not bars:
        raise RuntimeError(f"no validated bars in {data_dir}; run stage1.validate")

    blocks = global_block_map(bars, SESSIONS_PER_BLOCK)

    frames = []
    for sym in sorted(bars):
        one = build_one(sym, bars[sym], ticks.get(sym, TICK_SIZE))
        one["block"] = blocks.reindex(one.index).to_numpy()
        frames.append(one)
        if verbose:
            e = int(one["eligible"].sum())
            print(f"  {sym:<5} sessions {len(one):>5,}   eligible {e:>5,}"
                  f"   scored {int(one['DQ_pct'].notna().sum()):>5,}"
                  f"   T2 {int((one['DQ_pct'].notna() & one['T2'].notna()).sum()):>5,}"
                  f"   T3 {int((one['DQ_pct'].notna() & one['T3'].notna()).sum()):>5,}")

    out = pd.concat(frames).sort_index()
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Study B Step 4: opening-bar selector (no score test)")
    ap.add_argument("--data", default="data/study_b/clean")
    ap.add_argument("--out", default="results/study_b/opening.parquet")
    args = ap.parse_args(argv)

    print("=" * 74)
    print("STUDY B - STEP 4: OPENING-BAR SELECTOR")
    print("  emits one row per (instrument, session). No IC, no test.")
    print("=" * 74)

    df = build(args.data)

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path)

    print(f"\n  rows: {len(df):,}   sessions: {df.index.nunique():,}"
          f"   blocks: {int(df['block'].nunique())}")
    print(f"  written -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
