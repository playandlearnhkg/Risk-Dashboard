"""
stage1.eligibility_study_b — DATA-ONLY evaluation of a proposed per-session
eligibility rule for Study B.

Scope, fixed before it was written:

    Computes NO DQ, NO IC, NO T1/T2/T3 value and NO hypothesis test. It counts
    how many sessions per instrument would survive a proposed eligibility rule,
    and where the survivors are lost. Nothing here is a result.

WHY A PER-SESSION RULE AT ALL
-----------------------------
Run 1 gated INSTRUMENTS: an instrument whose whole-instrument degenerate-bar
fraction exceeded 5% was refused entry, and every session of an admitted
instrument was then used. Study B reads one bar per session, so the natural
unit of admission is the SESSION, not the instrument. That is a genuine
specification change and is labelled as one — see docs/STUDY_B_ELIGIBILITY.md.

THE FAILURE MODE THIS RULE IS BUILT AROUND
------------------------------------------
`core.wilder_atr_prev` is a Wilder EWM. pandas' `ewm` does not propagate NaN —
it CARRIES THE LAST VALUE FORWARD across missing bars:

    pd.Series([1., 2., nan, nan, 4.]).ewm(alpha=.5, adjust=False).mean()
      -> [nan, 1.5, 1.5, 1.5, 3.6875]

So a prior session that barely traded still produces a finite, ordinary-looking
`atr_prev`, silently stale by hours or days. Every Study B target divides by
that number. A rule that only checked `atr_prev.notna()` would therefore pass
exactly the sessions it most needs to reject, which is why conditions E4 and E5
below are about FRESHNESS, not about the ATR value being present.

    python -m stage1.eligibility_study_b \
        --tickers SPY IWM GLD XLE TLT EEM \
        --out results/study_b_eligibility
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

import numpy as np
import pandas as pd

from stage1 import core
from stage1.coverage_study_b import (END, OPEN_MIN, START, T2_END_MIN,
                                     T3_END_MIN, T_ENTRY_MIN, TICK_SIZE,
                                     load_bars)

UNIVERSE = ["SPY", "IWM", "GLD", "XLE", "TLT", "EEM"]

ATR_N = core.ATR_N                 # 20 five-minute bars, from the frozen score

# --- The proposed rule's thresholds ---------------------------------------
# Named so the sweep can vary them; the PROPOSED row is the recommendation.
VARIANTS = {
    "loose":    {"atr_window_min": 12, "prior_density_min": 0.60, "max_gap_days": 7},
    "proposed": {"atr_window_min": 16, "prior_density_min": 0.80, "max_gap_days": 5},
    "strict":   {"atr_window_min": 20, "prior_density_min": 0.90, "max_gap_days": 4},
}

# Instrument-level admission floors proposed to REPLACE Run 1's 5% gate.
#
# Two floors, not one. The pooled floor catches an instrument that is thin
# throughout. The per-era floor catches something the pooled figure hides: an
# instrument whose ineligible sessions all sit in ONE era is contributing a
# sample selected on market regime, which is a bias, not just a smaller n.
MIN_ELIGIBLE_RATE = 0.70
MIN_ERA_ELIGIBLE_RATE = 0.70


def session_frame(ticker: str, bars: pd.DataFrame) -> pd.DataFrame:
    """
    One row per session, carrying every quantity the rule needs.

    No score is aggregated: `candle_features` is called for two columns only —
    the frozen `valid` flag and `atr_prev` — and `atr_prev` is required here
    precisely because the operator asked for a valid-ATR rule.
    """
    bars = bars[(bars.index >= pd.Timestamp(START, tz=bars.index.tz))
                & (bars.index <= pd.Timestamp(END, tz=bars.index.tz)
                   + pd.Timedelta(days=1))]

    feats = core.candle_features(bars, TICK_SIZE)
    valid = feats["valid"].to_numpy()
    atr_prev = feats["atr_prev"].to_numpy()
    del feats

    present = bars["close"].notna().to_numpy()
    mins = bars.index.hour * 60 + bars.index.minute
    day = bars.index.normalize()

    # Trailing count of priced bars over the ATR window, inclusive of each row.
    roll = pd.Series(present.astype(float)).rolling(
        ATR_N, min_periods=1).sum().to_numpy()

    # Per-session share of grid rows that carry a price.
    dens = pd.Series(present.astype(float)).groupby(day).mean()

    sessions = pd.DatetimeIndex(dens.index)
    pos_open = {}
    for i, (d, m) in enumerate(zip(day, mins)):
        if m == OPEN_MIN:
            pos_open[d] = i

    def present_at(minute: int) -> pd.Series:
        sel = mins == minute
        s = pd.Series(present[sel], index=day[sel])
        return s.groupby(level=0).any().reindex(sessions, fill_value=False)

    rows = []
    prev_day = None
    for d in sessions:
        i = pos_open.get(d)
        # Every session's grid starts at 09:30 by construction, so a missing
        # position would mean a malformed frame rather than a missing bar.
        if i is None:
            continue

        has_prior = prev_day is not None and i > 0
        rows.append({
            "session": d,
            "open_present": bool(present[i]),
            "open_valid": bool(valid[i]),
            "has_prior": bool(has_prior),
            "gap_days": (d - prev_day).days if has_prior else np.nan,
            # roll at i-1 = priced bars among the 20 bars ENDING at the prior
            # session's last bar, which is exactly the window atr_prev sits on.
            "atr_window_priced": float(roll[i - 1]) if has_prior else np.nan,
            "prior_density": float(dens.loc[prev_day]) if has_prior else np.nan,
            "atr_prev": float(atr_prev[i]),
        })
        prev_day = d

    out = pd.DataFrame(rows).set_index("session")
    out["entry_present"] = present_at(T_ENTRY_MIN).reindex(out.index)
    out["t2_present"] = present_at(T2_END_MIN).reindex(out.index)
    out["t3_present"] = present_at(T3_END_MIN).reindex(out.index)
    out["ticker"] = ticker
    return out


def apply_rule(sf: pd.DataFrame, atr_window_min: int, prior_density_min: float,
               max_gap_days: int) -> pd.DataFrame:
    """The six conditions, evaluated independently so attrition is attributable."""
    c = pd.DataFrame(index=sf.index)
    c["E1_open_present"] = sf["open_present"]
    c["E2_open_valid"] = sf["open_valid"]
    c["E3_prior_exists"] = sf["has_prior"] & (sf["gap_days"] <= max_gap_days)
    c["E4_atr_window_fresh"] = sf["atr_window_priced"] >= atr_window_min
    c["E5_prior_dense"] = sf["prior_density"] >= prior_density_min
    c["E6_atr_usable"] = sf["atr_prev"].notna() & (sf["atr_prev"] >= TICK_SIZE)
    c = c.fillna(False)
    c["eligible"] = c.all(axis=1)
    return c


def evaluate(ticker: str, sf: pd.DataFrame, name: str, params: dict) -> dict:
    c = apply_rule(sf, **params)
    n = len(sf)
    elig = c["eligible"]

    # Attrition in declaration order: what each condition removes from the
    # sessions still standing after the ones before it.
    order = ["E1_open_present", "E2_open_valid", "E3_prior_exists",
             "E4_atr_window_fresh", "E5_prior_dense", "E6_atr_usable"]
    standing = pd.Series(True, index=sf.index)
    attrition = {}
    for cond in order:
        lost = int((standing & ~c[cond]).sum())
        attrition[cond] = lost
        standing = standing & c[cond]

    usable_t2 = elig & sf["entry_present"] & sf["t2_present"]
    usable_t3 = elig & sf["entry_present"] & sf["t3_present"]

    # Era stability. Eligibility that is concentrated in one era means the
    # surviving sample is selected on liquidity regime, not drawn evenly.
    era = pd.cut(sf.index.year, [2005, 2009, 2013, 2017, 2022],
                 labels=["06-09", "10-13", "14-17", "18-22"])
    by_era = elig.groupby(era, observed=False).mean().round(4).to_dict()
    min_era = float(min(by_era.values())) if by_era else float("nan")
    worst_era = min(by_era, key=by_era.get) if by_era else None

    return {
        "ticker": ticker, "variant": name, **params,
        "sessions": n,
        "eligible": int(elig.sum()),
        "eligible_rate": round(float(elig.mean()), 4),
        "usable_T2": int(usable_t2.sum()),
        "usable_T3": int(usable_t3.sum()),
        "min_era_rate": round(min_era, 4),
        "worst_era": str(worst_era),
        "admitted_pooled": bool(elig.mean() >= MIN_ELIGIBLE_RATE),
        "admitted_era_stable": bool(min_era >= MIN_ERA_ELIGIBLE_RATE),
        "admitted": bool(elig.mean() >= MIN_ELIGIBLE_RATE
                         and min_era >= MIN_ERA_ELIGIBLE_RATE),
        "attrition": attrition,
        "eligible_rate_by_era": {str(k): v for k, v in by_era.items()},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Study B eligibility rule — DATA ONLY (no DQ, no IC)")
    ap.add_argument("--tickers", nargs="+", default=UNIVERSE)
    ap.add_argument("--clean", default="data/clean")
    ap.add_argument("--out", default="results/study_b_eligibility")
    args = ap.parse_args(argv)

    key = os.environ.get("ELKASSABGIDATA_KEY")
    clean_dir = pathlib.Path(args.clean)
    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print("STUDY B — PROPOSED ELIGIBILITY RULE (DATA ONLY)")
    print(f"  window   : {START} -> {END}")
    print("  computes : session counts under the rule")
    print("  does NOT : compute DQ, IC, T1/T2/T3 or any test")
    print("=" * 78)

    # Session frames are cached because they are expensive (a full HF pull and
    # resample) and completely determined by the source bars — the rule is then
    # swept over them for free. The cache holds no score and no target.
    cache_dir = out_dir / "session_frames"
    cache_dir.mkdir(parents=True, exist_ok=True)

    frames, results = {}, []
    for t in args.tickers:
        try:
            cached = cache_dir / f"{t}.parquet"
            if cached.exists():
                sf, src = pd.read_parquet(cached), "cached session frame"
            else:
                bars, src = load_bars(t, clean_dir, key)
                sf = session_frame(t, bars)
                sf.to_parquet(cached)
            frames[t] = sf
            print(f"  {t:<5} {len(sf):,} sessions   ({src})")
        except Exception as exc:                                # noqa: BLE001
            print(f"  {t:<5} FAILED — {type(exc).__name__}: {exc}")
            continue
        for name, params in VARIANTS.items():
            results.append(evaluate(t, sf, name, params))

    if not results:
        return 1

    res = pd.DataFrame(results)

    for name in VARIANTS:
        sub = res[res["variant"] == name]
        p = VARIANTS[name]
        print(f"\n--- {name.upper()}  "
              f"(ATR window >= {p['atr_window_min']}/{ATR_N} priced, "
              f"prior session >= {p['prior_density_min']:.0%} priced, "
              f"gap <= {p['max_gap_days']}d) ---")
        print(sub[["ticker", "sessions", "eligible", "eligible_rate",
                   "usable_T2", "usable_T3", "min_era_rate", "worst_era",
                   "admitted_pooled", "admitted_era_stable", "admitted"]]
              .to_string(index=False))

    print("\n--- ATTRITION under PROPOSED (sessions removed, in rule order) ---")
    att = pd.DataFrame(
        {r["ticker"]: r["attrition"]
         for r in results if r["variant"] == "proposed"}).T
    print(att.to_string())

    print("\n--- ELIGIBLE RATE BY ERA under PROPOSED ---")
    era = pd.DataFrame(
        {r["ticker"]: r["eligible_rate_by_era"]
         for r in results if r["variant"] == "proposed"}).T
    print(era.to_string())

    res.drop(columns=["attrition", "eligible_rate_by_era"]).to_csv(
        out_dir / "eligibility.csv", index=False)
    with open(out_dir / "eligibility.json", "w") as fh:
        json.dump({"window": [START, END], "atr_n": ATR_N,
                   "min_eligible_rate": MIN_ELIGIBLE_RATE,
                   "variants": VARIANTS, "rows": results}, fh, indent=2)
    print(f"\n  written -> {out_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
