"""
doji4.py — four-way classification of the first 5-minute candle.

Splits the doji group by which way its small body pointed, instead of
lumping all indecisive candles together:

    1. Small + Continuation   body/range <= 0.10, closes WITH the gap
    2. Small + Reversal       body/range <= 0.10, closes AGAINST the gap
    3. Continuation           body/range >  0.10, closes WITH the gap
    4. Reversal               body/range >  0.10, closes AGAINST the gap

THE QUESTION THIS ANSWERS
  For a small-bodied candle that closed against the gap, is the right
  trade to follow the candle (short the gap) or to ignore it and stay
  with the gap? Group 2 traded both ways settles it.

  For groups 1 and 3 the two readings coincide -- the candle points the
  same way as the gap -- so a single column is shown. For groups 2 and 4
  they are opposite, and both are shown. Note that the two directions of
  one cell do NOT sum to zero net: the cost is paid either way, so the
  pair sums to -2 x COST_BPS. Gross flips exactly; net does not.

A BODY-SIZE LADDER is also run across the counter-gap cohort, because
0.10 is an arbitrary line. If following a counter-gap candle only starts
paying above some body size, the ladder shows where -- and if it never
pays at any body size, that is a cleaner result than any single cut.

Universe, entry, guards, volume filter and cost are unchanged from
volume_test.py; metrics come from dist.describe, the same set used in
DIST_REPORT.md.

Run: python3 lambda_strategy_validation/doji4.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from dist import describe  # noqa: E402
from doji import DOJI_MAX, classify  # noqa: E402
from volume_test import (  # noqa: E402
    COST_BPS, SMALL, VOL_MULT, VOL_WINDOW, finalize, log, prep_earnings,
    volume_features,
)

BASE = Path("/home/user/lambda_data")
OUT_DIR = BASE / "tables"
FEED = BASE / "doji4_feed.json"
REPORT = Path(__file__).resolve().parent / "DOJI4_REPORT.md"

WINDOWS = {"5 min (09:40)": 9, "10 min (09:45)": 14,
           "15 min (09:50)": 19, "1 hour (10:35)": 64}

G1 = "1. Small + Continuation"
G2 = "2. Small + Reversal"
G3 = "3. Continuation"
G4 = "4. Reversal"

# Body/range ladder for the counter-gap cohort.
LADDER = [("≤ 0.10 (doji)", -np.inf, 0.10), ("0.10 – 0.25", 0.10, 0.25),
          ("0.25 – 0.50", 0.25, 0.50), ("0.50 – 0.75", 0.50, 0.75),
          ("> 0.75", 0.75, np.inf)]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    vol = volume_features()
    log("volume features built")

    df, meta = finalize(prep_earnings(vol), "Post-Earnings (T+1)")
    df = classify(df)
    hv = df[df["high_vol"]].copy()

    small, wg = hv["is_doji"], hv["with_gap"]
    groups = [(G1, hv[small & wg], "with"), (G2, hv[small & ~wg], "against"),
              (G3, hv[~small & wg], "with"), (G4, hv[~small & ~wg], "against")]
    log("; ".join(f"{g}={len(s):,}" for g, s, _ in groups))

    entry = df["entry_px"]
    gs = pd.Series(np.where(df["gap_up"], 1.0, -1.0), index=df.index)

    rows = []
    for wname, wk in WINDOWS.items():
        px = df[f"m{wk}"]
        for gname, sub, side in groups:
            # "gap" = trade the gap direction; "candle" = trade the body's
            # direction. They coincide for the with-gap groups.
            variants = [("Follow the gap", gs)]
            if side == "against":
                variants.append(("Follow the candle", -gs))
            for vname, sign in variants:
                simple = (sign * (px / entry - 1.0)).reindex(
                    sub.index).dropna()
                simple = simple[simple != 0]
                if len(simple) < 30:
                    continue
                logr = (sign * np.log(px / entry)).reindex(simple.index)
                atr = (sign * (px - entry) / df["atr14_prev"]).reindex(
                    simple.index)
                rows.append(describe(
                    simple, logr, atr, df.loc[simple.index, "date"],
                    {"window": wname, "group": gname, "direction": vname,
                     "side": side}))
    R = {"main": pd.DataFrame(rows)}

    # ---- body-size ladder across the counter-gap cohort ----
    counter = hv[~wg]
    rows = []
    for wname, wk in WINDOWS.items():
        px = df[f"m{wk}"]
        for bname, blo, bhi in LADDER:
            br = counter["body_range"].fillna(0.0)
            sub = counter[(br > blo) & (br <= bhi)]
            for vname, sign in (("Follow the candle", -gs),
                                ("Follow the gap", gs)):
                simple = (sign * (px / entry - 1.0)).reindex(
                    sub.index).dropna()
                simple = simple[simple != 0]
                if len(simple) < 30:
                    continue
                logr = (sign * np.log(px / entry)).reindex(simple.index)
                atr = (sign * (px - entry) / df["atr14_prev"]).reindex(
                    simple.index)
                rows.append(describe(
                    simple, logr, atr, df.loc[simple.index, "date"],
                    {"window": wname, "bucket": bname, "direction": vname}))
    R["ladder"] = pd.DataFrame(rows)

    comp = []
    for gname, sub, side in groups:
        comp.append({
            "group": gname, "n": len(sub), "share": len(sub) / len(hv),
            "median_body_range": float(sub["body_range"].median()),
            "median_abs_gap_bps": float(sub["gap"].abs().median() * 1e4),
            "median_gap_atr": float(sub["gap_atr"].median()),
            "median_vol_ratio": float(sub["vol_ratio"].median()),
            "pct_gap_up": float(sub["gap_up"].mean()),
        })
    R["comp"] = pd.DataFrame(comp)

    meta.update({"cost_bps": COST_BPS, "small": SMALL, "vol_mult": VOL_MULT,
                 "vol_window": VOL_WINDOW, "doji_max": DOJI_MAX,
                 "n_hv": int(len(hv)),
                 **{f"n_g{i}": int(len(s))
                    for i, (_, s, _) in enumerate(groups, 1)}})

    for k, v in R.items():
        v.to_csv(OUT_DIR / f"doji4_{k}.csv", index=False)
    FEED.write_text(json.dumps(
        {"meta": meta, **{k: json.loads(v.round(6).to_json(orient="records"))
                          for k, v in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables")

    from doji4_text import build  # noqa: E402
    REPORT.write_text(build(R, meta))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
