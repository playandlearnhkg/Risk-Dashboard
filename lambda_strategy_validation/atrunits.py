"""
atrunits.py — the core post-earnings continuation edge re-expressed in
ATR units, alongside the basis-point view.

WHY THE TWO VIEWS DIFFER
  A basis-point return treats a 1% move in a quiet $200 utility and a 1%
  move in a $30 name that routinely swings 6% as the same result. ATR
  units ask instead "how far did this go relative to what this stock
  normally does in a day", which is the scale a position-sizer actually
  works in. Averaging in ATR de-weights the high-volatility names that
  dominate a bps average.

  Win rate is identical under both, because dividing by a positive ATR
  cannot change a return's sign. Everything else can move, and the
  payoff ratio moves most, because it is a ratio of two means and each
  trade is rescaled by its own denominator.

THE COST CONVERSION IS NOT A CONSTANT
  6.6 bps is a fixed fraction of PRICE, so in ATR units it becomes

      cost_atr = (6.6 / 10000) x entry_price / ATR(14)_prior

  which is different for every trade: large for a low-volatility name
  whose ATR is a small share of its price, small for a volatile one.
  Net expectancy in ATR is therefore mean(return_atr - cost_atr), not
  mean(return_atr) minus a single number. The distribution of that
  per-trade cost is reported in section 3, because it is the part of
  this exercise most likely to be got wrong elsewhere.

NO LOOK-AHEAD
  ATR(14) is the prior session's, exactly as in every other report here.

The bps columns reproduce DIST_REPORT.md, including its convention of
dropping exactly-zero returns, so the two reports agree line for line.

Run: python3 lambda_strategy_validation/atrunits.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

import analysis as A  # noqa: E402
from volume_test import (  # noqa: E402
    COST_BPS, N_BOOT, SMALL, VOL_MULT, VOL_WINDOW, finalize, log,
    prep_earnings, volume_features,
)
from winrate_report import wilson  # noqa: E402

BASE = Path("/home/user/lambda_data")
OUT_DIR = BASE / "tables"
FEED = BASE / "atrunits_feed.json"
REPORT = Path(__file__).resolve().parent / "ATRUNITS_REPORT.md"

CONT = "Continuation (1st candle with gap)"
WINDOWS = {"5 min (09:40)": 9, "10 min (09:45)": 14,
           "15 min (09:50)": 19, "1 hour (10:35)": 64}


def block(r: pd.Series, cost: pd.Series, dates: pd.Series, unit: str,
          label: dict) -> dict:
    """Metrics for one return series, already in the target unit."""
    n = len(r)
    k = int((r > 0).sum())
    lo, hi = wilson(k, n)
    net = r - cost
    bn = A.clustered_bootstrap(net, dates, n_boot=N_BOOT)
    wins, losses = r[r > 0], r[r < 0]
    aw = wins.mean() if len(wins) else np.nan
    al = -losses.mean() if len(losses) else np.nan
    q = r.quantile([0.10, 0.25, 0.50, 0.75, 0.90])
    rec = dict(label)
    rec.update({
        "unit": unit, "n": n,
        "win_rate": k / n if n else np.nan, "wilson_lo": lo, "wilson_hi": hi,
        "mean": float(r.mean()), "median": float(q.loc[0.50]),
        "avg_win": aw, "avg_loss": al,
        "payoff_ratio": (aw / al) if al else np.nan,
        "net": bn["stat"], "net_p": bn["p"],
        "net_lo": bn["lo"], "net_hi": bn["hi"],
        "p10": float(q.loc[0.10]), "p25": float(q.loc[0.25]),
        "p75": float(q.loc[0.75]), "p90": float(q.loc[0.90]),
        "std": float(r.std()),
        "skew": float(stats.skew(r, bias=False)),
        "kurtosis": float(stats.kurtosis(r, fisher=True, bias=False)),
        "mean_cost": float(cost.mean()),
        "small": "YES" if n < SMALL else "",
    })
    return rec


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    vol = volume_features()
    log("volume features built")

    df, meta = finalize(prep_earnings(vol), "Post-Earnings (T+1)")
    df = df[(df["pattern"] == CONT) & df["high_vol"]].copy()
    df = df[df["atr14_prev"].notna() & (df["atr14_prev"] > 0)].copy()
    df = df.reset_index(drop=True)
    log(f"cohort: {len(df):,}")

    entry = df["entry_px"]
    atr = df["atr14_prev"]
    gs = pd.Series(np.where(df["gap_up"], 1.0, -1.0), index=df.index)
    # The same 6.6 bps, expressed per trade in each unit.
    cost_atr_all = (COST_BPS / 1e4) * entry / atr

    rows, tails = [], []
    for wname, wk in WINDOWS.items():
        px = df[f"m{wk}"]
        r = gs * (px / entry - 1.0)
        r = r.dropna()
        r = r[r != 0]                      # DIST_REPORT.md convention
        idx = r.index
        d = df.loc[idx, "date"]

        r_bps = r * 1e4
        cost_bps = pd.Series(COST_BPS, index=idx)
        rows.append(block(r_bps, cost_bps, d, "bps",
                          {"window": wname}))

        r_atr = (gs.loc[idx] * (px.loc[idx] - entry.loc[idx])) / atr.loc[idx]
        c_atr = cost_atr_all.loc[idx]
        rows.append(block(r_atr, c_atr, d, "ATR", {"window": wname}))

        tails.append({
            "window": wname, "n": len(r),
            "pct_loss_1atr": float((r_atr < -1.0).mean()),
            "pct_gain_1atr": float((r_atr > 1.0).mean()),
            "pct_loss_05atr": float((r_atr < -0.5).mean()),
            "pct_gain_05atr": float((r_atr > 0.5).mean()),
            "n_loss_1atr": int((r_atr < -1.0).sum()),
            "n_gain_1atr": int((r_atr > 1.0).sum()),
        })
    R = {"main": pd.DataFrame(rows), "tails": pd.DataFrame(tails)}

    # The cost conversion itself, which varies by name.
    ratio = atr / entry                     # ATR as a share of price
    qs = [0.10, 0.25, 0.50, 0.75, 0.90]
    R["cost"] = pd.DataFrame([{
        "metric": "ATR as % of entry price",
        **{f"p{int(q*100)}": float(ratio.quantile(q) * 100) for q in qs},
        "mean": float(ratio.mean() * 100),
    }, {
        "metric": f"{COST_BPS} bps expressed in ATR",
        **{f"p{int(q*100)}": float(cost_atr_all.quantile(q)) for q in qs},
        "mean": float(cost_atr_all.mean()),
    }])

    meta.update({"cost_bps": COST_BPS, "small": SMALL, "vol_mult": VOL_MULT,
                 "vol_window": VOL_WINDOW, "n_cohort": int(len(df)),
                 "median_atr_pct": float(ratio.median() * 100),
                 "median_cost_atr": float(cost_atr_all.median()),
                 "mean_cost_atr": float(cost_atr_all.mean())})

    for k, v in R.items():
        v.to_csv(OUT_DIR / f"atru_{k}.csv", index=False)
    FEED.write_text(json.dumps(
        {"meta": meta, **{k: json.loads(v.round(6).to_json(orient="records"))
                          for k, v in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables")

    from atrunits_text import build  # noqa: E402
    REPORT.write_text(build(R, meta))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
