"""
stops_tight.py — extends the stop-loss test to tighter ATR stops.

Requested ladder: 0.5, 0.7, 0.8 ATR, with 1.0 ATR and no-stop carried
forward from STOPS_REPORT.md for comparison. 1.5 and 2.0 are also run so
the full continuum is visible in one place; they add nothing to the cost
of the test since the cohort is already loaded.

Setup, entry, ATR definition, intrabar trigger, gap-through fill model
and cost are all unchanged from stops.py, whose `prepare()` builds the
cohort so the two reports cannot drift apart.

Run: python3 lambda_strategy_validation/stops_tight.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from stops import (  # noqa: E402
    COST_BPS, ENTRY_MIN, EXIT_MIN, OUT_DIR, SMALL, VOL_MULT, VOL_WINDOW,
    apply_stop, describe, log, prepare,
)

BASE = Path("/home/user/lambda_data")
FEED = BASE / "stops_tight_feed.json"
REPORT = Path(__file__).resolve().parent / "STOPS_TIGHT_REPORT.md"

# The three new levels, then the two already reported, then the loose end
# of the ladder for continuity.
REQUESTED = (0.5, 0.7, 0.8, 1.0)
EXTRA = (1.5, 2.0)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df, P = prepare()
    sign, entry, atr = P["sign"], P["entry"], P["atr"]
    opens, adverse, close_exit = P["opens"], P["adverse"], P["close_exit"]
    dates = df["date"]

    rows = []
    for k in REQUESTED + EXTRA:
        pnl, stopped = apply_stop(sign, entry, atr, opens, adverse,
                                  close_exit, -k * atr, ENTRY_MIN)
        rows.append(describe(pd.Series(pnl / entry), pd.Series(pnl / atr),
                             dates, stopped,
                             {"rule": f"Stop −{k:.1f} ATR", "mult": k,
                              "requested": k in REQUESTED}))
        log(f"−{k:.1f} ATR: {stopped.mean()*100:5.1f}% stopped, "
            f"net {rows[-1]['net_bps']:+.1f}")

    rows.append(describe(pd.Series(close_exit / entry),
                         pd.Series(close_exit / atr), dates,
                         np.zeros(len(df), dtype=bool),
                         {"rule": "No stop (hold to 1 hour)",
                          "mult": np.nan, "requested": True}))
    R = {"ladder": pd.DataFrame(rows)}

    # Where does the expectancy actually go? Split the cohort into the
    # trades a given stop catches and the ones it does not, and measure
    # what the caught ones would have done if left alone.
    rows = []
    for k in REQUESTED:
        pnl, stopped = apply_stop(sign, entry, atr, opens, adverse,
                                  close_exit, -k * atr, ENTRY_MIN)
        held = close_exit / entry              # what they'd have made
        realised = pnl / entry
        if stopped.sum() >= 30:
            rows.append({
                "mult": k, "n_stopped": int(stopped.sum()),
                "pct_stopped": float(stopped.mean()),
                "stopped_realised_bps": float(realised[stopped].mean() * 1e4),
                "stopped_if_held_bps": float(held[stopped].mean() * 1e4),
                "pct_would_recover": float((held[stopped] > 0).mean()),
                "pct_would_beat_stop": float(
                    (held[stopped] > realised[stopped]).mean()),
                "untouched_bps": float(held[~stopped].mean() * 1e4),
            })
    R["attribution"] = pd.DataFrame(rows)

    meta = {"cost_bps": COST_BPS, "small": SMALL, "vol_mult": VOL_MULT,
            "vol_window": VOL_WINDOW, "n": int(len(df)),
            "start": str(df["date"].min().date()),
            "end": str(df["date"].max().date()),
            "exit_min": EXIT_MIN,
            "requested": list(REQUESTED), "extra": list(EXTRA)}
    for k_, v in R.items():
        v.to_csv(OUT_DIR / f"stopstight_{k_}.csv", index=False)
    FEED.write_text(json.dumps(
        {"meta": meta, **{k_: json.loads(v.round(6).to_json(orient="records"))
                          for k_, v in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables")

    from stops_tight_text import build  # noqa: E402
    REPORT.write_text(build(R, meta))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
