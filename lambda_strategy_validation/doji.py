"""
doji.py — three-way classification of the first 5-minute candle, with the
classic doji carve-out, on the post-earnings High Volume cohort.

    Doji / Indecisive : |body| / (high - low) <= 0.10
    Continuation      : closes WITH the gap and is not a doji
    Reversal          : closes AGAINST the gap and is not a doji

IMPORTANT CONTEXT FOR READING THIS REPORT.
  The classifier used by every previous report in this series
  (`simple_first_candle` in winrate_report.py) ALREADY applies this exact
  carve-out at this exact threshold. So groups 1 and 2 below are not new
  cohorts -- they reproduce the Continuation and Reversal figures already
  published. What is new is group 3, which has never been reported on its
  own, and the counterfactual in section 3, which is the only thing that
  actually answers "does removing dojis improve the Continuation edge".

  To answer that question a WITH-DOJI cohort is constructed explicitly:
  every event whose first candle closes with the gap, doji or not. The
  difference between that and group 1 is the value of the carve-out.

  The specification asks for <= 0.10 where the existing code uses < 0.10.
  On this data no event sits exactly on the boundary, so the two are the
  same partition; <= is used here to match the specification as written.

ZERO-RANGE CANDLES (high == low) have an undefined body/range ratio. They
are counted as indecisive, which matches both the existing classifier and
the economics -- a candle with no range is the limiting case of a doji.
Their count is reported separately.

SIGN CONVENTIONS
  Continuation : signed in the GAP direction.
  Reversal     : signed in the CANDLE direction (= against the gap),
                 unchanged from REVERSAL_PAYOFF_REPORT.md, so a positive
                 number means following the counter-gap candle paid.
  Indecisive   : signed in the GAP direction. A doji has no meaningful
                 direction of its own, so the gap is the only information
                 available at 09:35. The candle-direction reading is
                 carried alongside as a robustness check.

Run: python3 lambda_strategy_validation/doji.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from dist import describe  # noqa: E402  -- same metric set as DIST_REPORT
from volume_test import (  # noqa: E402
    COST_BPS, SMALL, VOL_MULT, VOL_WINDOW, finalize, log, prep_earnings,
    volume_features,
)

BASE = Path("/home/user/lambda_data")
OUT_DIR = BASE / "tables"
FEED = BASE / "doji_feed.json"
REPORT = Path(__file__).resolve().parent / "DOJI_REPORT.md"

DOJI_MAX = 0.10
WINDOWS = {"5 min (09:40)": 9, "10 min (09:45)": 14,
           "15 min (09:50)": 19, "1 hour (10:35)": 64}

G_CONT = "Continuation (non-doji)"
G_REV = "Reversal (non-doji)"
G_DOJI = "Indecisive (doji)"
G_CONT_ALL = "Continuation incl. dojis"


def classify(df: pd.DataFrame) -> pd.DataFrame:
    """Three-way label plus the body/range ratio it is built from."""
    body = df["c1_close"] - df["c1_open"]
    rng = df["c1_high"] - df["c1_low"]
    ratio = body.abs() / rng.where(rng > 0)
    df = df.copy()
    df["body_range"] = ratio
    df["zero_range"] = ~(rng > 0)
    # A zero-range candle has an undefined ratio and is indecisive by
    # construction, so it joins the doji group rather than being dropped.
    df["is_doji"] = df["zero_range"] | (ratio <= DOJI_MAX)
    df["with_gap"] = (body > 0) == (df["gap"] > 0)

    lab = np.where(df["is_doji"], G_DOJI,
                   np.where(df["with_gap"], G_CONT, G_REV))
    df["klass"] = lab
    return df


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    vol = volume_features()
    log("volume features built")

    df, meta = finalize(prep_earnings(vol), "Post-Earnings (T+1)")
    df = classify(df)
    hv = df[df["high_vol"]].copy()
    log(f"high volume n={len(hv):,}; "
        + ", ".join(f"{k}={v:,}" for k, v in
                    hv["klass"].value_counts().items()))

    entry = df["entry_px"]
    gs = pd.Series(np.where(df["gap_up"], 1.0, -1.0), index=df.index)

    cont = hv[hv["klass"] == G_CONT]
    rev = hv[hv["klass"] == G_REV]
    doji = hv[hv["klass"] == G_DOJI]
    # The counterfactual: what Continuation would have been WITHOUT the
    # carve-out. Dojis that happen to close with the gap are folded back in.
    cont_all = hv[(hv["klass"] == G_CONT)
                  | (hv["is_doji"] & hv["with_gap"])]

    specs = [(G_CONT, cont, gs), (G_REV, rev, -gs), (G_DOJI, doji, gs),
             (G_CONT_ALL, cont_all, gs)]

    rows = []
    for wname, wk in WINDOWS.items():
        px = df[f"m{wk}"]
        for gname, sub, sign in specs:
            simple = (sign * (px / entry - 1.0)).reindex(sub.index).dropna()
            simple = simple[simple != 0]
            if len(simple) < 30:
                continue
            logr = (sign * np.log(px / entry)).reindex(simple.index)
            atr = (sign * (px - entry) / df["atr14_prev"]).reindex(
                simple.index)
            rows.append(describe(simple, logr, atr,
                                 df.loc[simple.index, "date"],
                                 {"window": wname, "group": gname}))
    R = {"main": pd.DataFrame(rows)}

    # Doji read the other way, since "gap direction" is a choice.
    # Candle direction for a doji = sign(body), i.e. the gap sign flipped
    # whenever the (tiny) body closed against the gap.
    cs = gs.reindex(doji.index) * np.where(doji["with_gap"], 1.0, -1.0)
    rows = []
    for wname, wk in WINDOWS.items():
        px = df[f"m{wk}"].reindex(doji.index)
        e = entry.reindex(doji.index)
        simple = (cs * (px / e - 1.0)).dropna()
        simple = simple[simple != 0]
        if len(simple) < 30:
            continue
        logr = (cs * np.log(px / e)).reindex(simple.index)
        atr = (cs * (px - e) / df["atr14_prev"].reindex(doji.index)).reindex(
            simple.index)
        rows.append(describe(simple, logr, atr,
                             df.loc[simple.index, "date"],
                             {"window": wname,
                              "group": "Indecisive, candle direction"}))
    R["doji_alt"] = pd.DataFrame(rows)

    # Composition of the three groups.
    comp = []
    for gname, sub in ((G_CONT, cont), (G_REV, rev), (G_DOJI, doji)):
        comp.append({
            "group": gname, "n": len(sub),
            "share": len(sub) / len(hv),
            "median_body_range": float(sub["body_range"].median()),
            "n_zero_range": int(sub["zero_range"].sum()),
            "median_abs_gap_bps": float(sub["gap"].abs().median() * 1e4),
            "median_gap_atr": float(sub["gap_atr"].median()),
            "median_vol_ratio": float(sub["vol_ratio"].median()),
            "pct_gap_up": float(sub["gap_up"].mean()),
        })
    R["comp"] = pd.DataFrame(comp)

    n_doji_withgap = int((doji["with_gap"]).sum())
    meta.update({
        "cost_bps": COST_BPS, "small": SMALL, "vol_mult": VOL_MULT,
        "vol_window": VOL_WINDOW, "doji_max": DOJI_MAX,
        "n_hv": int(len(hv)), "n_cont": int(len(cont)), "n_rev": int(len(rev)),
        "n_doji": int(len(doji)), "n_cont_all": int(len(cont_all)),
        "n_doji_withgap": n_doji_withgap,
        "n_zero_range": int(doji["zero_range"].sum()),
        "doji_share": float(len(doji) / len(hv)),
    })

    for k, v in R.items():
        v.to_csv(OUT_DIR / f"doji_{k}.csv", index=False)
    FEED.write_text(json.dumps(
        {"meta": meta, **{k: json.loads(v.round(6).to_json(orient="records"))
                          for k, v in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables")

    from doji_text import build  # noqa: E402
    REPORT.write_text(build(R, meta))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
