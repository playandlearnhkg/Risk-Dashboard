"""
candle_shapes.py — What do the four opening-candle patterns actually look
like?

For every event, the three 5-minute candles are expressed in basis points
relative to that session's open, then ORIENTED by the gap direction
(multiplied by sign(gap)) so a gap-down continuation and a gap-up
continuation have the same shape. After orientation, "up" always means
"moving with the gap". Averaging within each pattern label then gives the
archetypal candle for that label.

Also emits, per pattern, the forward return from 09:45 (when the pattern
completes) so the picture and the payoff sit together.

Output: /home/user/lambda_data/candle_shapes.json
Run: python3 lambda_strategy_validation/candle_shapes.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path("/home/user/lambda_data")
EVENTS = BASE / "events.parquet"
OUT = BASE / "candle_shapes.json"

PATTERNS = ["Strong Continuation+", "Moderate Continuation+",
            "Indecision0", "Early Reversal-"]
FIELDS = ["open", "high", "low", "close"]


def main() -> None:
    ev = pd.read_parquet(EVENTS)
    ev = ev[ev["pattern"].notna()].copy()
    orient = np.where(ev["gap_up"], 1.0, -1.0)
    base = ev["open"]

    for i in (1, 2, 3):
        for f in FIELDS:
            col = f"c{i}_{f}"
            ev[f"n_{col}"] = orient * (ev[col] / base - 1.0) * 1e4
        # Flipping a gap-down event reverses the price axis, so its high
        # becomes the lowest oriented value and its low the highest. Without
        # this swap the averaged candle can come out with its high below its
        # close, which is not a candle at all.
        hi, lo = ev[f"n_c{i}_high"].copy(), ev[f"n_c{i}_low"].copy()
        ev[f"n_c{i}_high"] = np.maximum(hi, lo)
        ev[f"n_c{i}_low"] = np.minimum(hi, lo)

    out = {"patterns": [], "n_total": int(len(ev))}
    for pat in PATTERNS:
        g = ev[ev["pattern"] == pat]
        if g.empty:
            continue
        candles = []
        for i in (1, 2, 3):
            candles.append({f: float(g[f"n_c{i}_{f}"].median()) for f in FIELDS})
        rec = {
            "pattern": pat,
            "n": int(len(g)),
            "share": float(len(g) / len(ev)),
            "candles": candles,
            "gap_up_share": float(g["gap_up"].mean()),
            "median_abs_gap_bps": float(g["gap"].abs().median() * 1e4),
            "continuation_rate_full_session": float(g["continuation"].mean()),
        }
        if "signed_post_pattern" in g.columns:
            rec["post_0945_gross_bps"] = float(g["signed_post_pattern"].mean() * 1e4)
        out["patterns"].append(rec)

    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps({p["pattern"]: {"n": p["n"], "share": round(p["share"], 3),
                                     "cont": round(p["continuation_rate_full_session"], 3)}
                      for p in out["patterns"]}, indent=2))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
