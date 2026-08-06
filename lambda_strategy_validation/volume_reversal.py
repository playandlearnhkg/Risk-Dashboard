"""
volume_reversal.py — the volume-confirmation test applied to the REVERSAL
signal (first 5-minute candle closes AGAINST the gap), on both universes.

Everything except the cohort is identical to volume_test.py: same High
Volume definition, same entry, same guards, same universes. The loading
and preparation functions are imported from there rather than copied.

SIGN CONVENTION — unchanged from REVERSAL_PAYOFF_REPORT.md.
  Reversal returns are signed in the CANDLE's direction:

      reversal_return = -sign(gap) * (P_end / P_entry - 1)

  So "the Reversal signal working" means following the counter-gap candle
  pays. The gap-direction view of the same events is the negative of every
  Reversal figure. Continuation is signed in the gap direction as always,
  so both express one rule: follow the first 5-minute candle.

Run: python3 lambda_strategy_validation/volume_reversal.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from volume_test import (  # noqa: E402
    COST_BPS, SMALL, VOL_MULT, VOL_WINDOW, WINDOWS, finalize, log,
    prep_earnings, prep_general, stat_row, volume_features,
)

BASE = Path("/home/user/lambda_data")
OUT_DIR = BASE / "tables"
FEED = BASE / "volrev_feed.json"
REPORT = Path(__file__).resolve().parent / "VOLUME_REVERSAL_REPORT.md"

REV = "Reversal (1st candle against gap)"
CONT = "Continuation (1st candle with gap)"


def run_reversal(df: pd.DataFrame, name: str) -> dict[str, pd.DataFrame]:
    entry = df["entry_px"]
    gs = pd.Series(np.where(df["gap_up"], 1.0, -1.0), index=df.index)
    rev = df[df["pattern"] == REV]
    cont = df[df["pattern"] == CONT]
    log(f"{name}: Reversal n={len(rev):,} "
        f"({rev['high_vol'].mean()*100:.1f}% high vol), "
        f"Continuation n={len(cont):,}")
    R = {}

    rows = []
    for wname, wmin in WINDOWS.items():
        # candle direction = against the gap
        r = -gs * (df[f"m{wmin}"] / entry - 1.0)
        for gname, sub in (("All Reversal", rev),
                           ("Rev + High Volume", rev[rev["high_vol"]]),
                           ("Rev + Normal/Low Vol", rev[~rev["high_vol"]])):
            s = r.reindex(sub.index).dropna()
            s = s[s != 0]
            if len(s) < 30:
                continue
            rows.append(stat_row(s, df.loc[s.index, "date"],
                                 {"universe": name, "window": wname,
                                  "group": gname}))
    R["main"] = pd.DataFrame(rows)

    # Same events read in the GAP direction, so the "fade the candle"
    # alternative is visible without the reader flipping signs by hand.
    rows = []
    for wname, wmin in WINDOWS.items():
        r = gs * (df[f"m{wmin}"] / entry - 1.0)
        for gname, sub in (("Rev events, gap dir — High Vol",
                            rev[rev["high_vol"]]),
                           ("Rev events, gap dir — Normal/Low",
                            rev[~rev["high_vol"]])):
            s = r.reindex(sub.index).dropna()
            s = s[s != 0]
            if len(s) < 30:
                continue
            rows.append(stat_row(s, df.loc[s.index, "date"],
                                 {"universe": name, "window": wname,
                                  "group": gname}))
    R["gapdir"] = pd.DataFrame(rows)

    # Volume composition of each cohort — is volume even informative here?
    comp = []
    for cname, sub in (("Continuation", cont), ("Reversal", rev)):
        comp.append({"universe": name, "cohort": cname, "n": len(sub),
                     "n_high": int(sub["high_vol"].sum()),
                     "pct_high": float(sub["high_vol"].mean()),
                     "median_ratio": float(sub["vol_ratio"].median())})
    R["comp"] = pd.DataFrame(comp)
    return R


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    vol = volume_features()
    log("volume features built")

    out: dict[str, pd.DataFrame] = {}
    metas = {}
    for key, prep, label in (("A", prep_earnings, "Post-Earnings (T+1)"),
                             ("B", prep_general, "General Gaps")):
        df, meta = finalize(prep(vol), label)
        rev = df[df["pattern"] == REV]
        meta["n_rev"] = int(len(rev))
        meta["pct_high_rev"] = float(rev["high_vol"].mean())
        metas[key] = meta
        for tname, tbl in run_reversal(df, label).items():
            out[f"{key}_{tname}"] = tbl

    meta = {"cost_bps": COST_BPS, "small": SMALL, "vol_mult": VOL_MULT,
            "vol_window": VOL_WINDOW, "A": metas["A"], "B": metas["B"]}
    for k, v in out.items():
        v.to_csv(OUT_DIR / f"volrev_{k}.csv", index=False)
    FEED.write_text(json.dumps(
        {"meta": meta, **{k: json.loads(v.round(6).to_json(orient="records"))
                          for k, v in out.items()}}, separators=(",", ":")))
    log(f"wrote {len(out)} tables")

    from volume_reversal_text import build  # noqa: E402
    REPORT.write_text(build(out, meta))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
