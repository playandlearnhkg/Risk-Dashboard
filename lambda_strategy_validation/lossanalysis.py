"""
lossanalysis.py — severity of large losses under seven stop rules,
including two anchored-VWAP variants.

    1  No stop (hold to 1 hour)
    2  Gap Level structural stop      (5-min close beyond prior close)
    3  Opening Range structural stop  (5-min close beyond the 09:30-09:35
                                       candle's low/high)
    4  Statistical stop -0.5 x prior ATR(14)   (intrabar touch)
    5  Statistical stop -1.0 x prior ATR(14)   (intrabar touch)
    6  Anchored VWAP from the 09:30 open       (5-min close beyond it)
    7  Anchored VWAP from the prior close      (5-min close beyond it)

ANCHORED VWAP — AND AN AMBIGUITY THAT HAD TO BE RESOLVED
  Rule 6 is unambiguous: cumulative volume-weighted average of the
  typical price (H+L+C)/3 from minute 0, evaluated at each checkpoint.

  Rule 7 is not. An anchored VWAP accumulates volume from its anchor
  forward, but between the prior close and 09:30 no regular-session
  volume trades. Taken literally, "anchored at the prior close" and
  "anchored at 09:30" therefore produce the IDENTICAL line, and rule 7
  would just be a copy of rule 6.

  The reading that makes rule 7 a distinct rule is that the anchor
  contributes the prior close as a price observation. That needs a
  weight, and no weight is canonical. This implementation seeds the
  accumulation with `prev_close` carrying the first 5-minute candle's
  volume (`c1_volume`) -- a data-driven choice on the same scale as the
  early session, not a tuned one. The effect is to drag the line toward
  the unfilled gap, which makes the stop WIDER than rule 6 on a gap up.

  Because that seed is a judgement call, section 5 reports the rule at
  0.5x, 1x and 2x the seed weight so the reader can see how much rides
  on it.

NO LOOK-AHEAD
  Every VWAP value at checkpoint t uses only minutes 0..t. ATR is the
  prior-session ATR(14). Nothing from the gap day enters a stop
  DISTANCE; the VWAP and structural levels are of course observed as the
  session unfolds, which is what makes them tradeable rather than
  look-ahead.

CONFIRMATION
  Rules 2, 3, 6, 7 confirm on the 5-minute close and exit at that close.
  Rules 4 and 5 fire on the first intrabar touch and fill at the stop
  price, or the bar's open if it opened through. The two families are
  not comparable on stop-out RATE, but they are directly comparable on
  the question this report asks: how bad are the losses that get
  through?

Run: python3 lambda_strategy_validation/lossanalysis.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from stops import (  # noqa: E402
    COST_BPS, ENTRY_MIN, EXIT_MIN, MAX_MIN, OUT_DIR, VOL_MULT, VOL_WINDOW,
    apply_stop, log, mat, prepare,
)
from structstops import CHECKS  # noqa: E402

BASE = Path("/home/user/lambda_data")
FEED = BASE / "loss_feed.json"
REPORT = Path(__file__).resolve().parent / "LOSS_REPORT.md"

RULES = [
    "1. No stop",
    "2. Gap Level",
    "3. Opening Range",
    "4. ATR −0.5",
    "5. ATR −1.0",
    "6. AVWAP from 09:30",
    "7. AVWAP from prior close",
]
THRESHOLDS = (1.0, 0.5)
SEED_MULTS = (0.5, 1.0, 2.0)


def running_vwap(highs, lows, closes, vols, seed_px=None, seed_w=None):
    """Cumulative VWAP of the typical price, optionally seeded.

    Returns an (n, MAX_MIN) matrix; column t is the VWAP using minutes
    0..t only, so it is knowable at t.
    """
    tp = (highs + lows + closes) / 3.0
    v = np.nan_to_num(vols, nan=0.0)
    pv = np.nan_to_num(tp * v, nan=0.0)
    cum_pv = np.cumsum(pv, axis=1)
    cum_v = np.cumsum(v, axis=1)
    if seed_px is not None:
        cum_pv = cum_pv + (seed_px * seed_w)[:, None]
        cum_v = cum_v + seed_w[:, None]
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(cum_v > 0, cum_pv / cum_v, np.nan)


def scan_close(sign, entry, closes, level_mat):
    """First 5-minute CLOSE beyond a (possibly time-varying) level."""
    n = len(entry)
    stopped = np.zeros(n, dtype=bool)
    pnl = np.full(n, np.nan)
    for m in CHECKS:
        live = ~stopped
        if not live.any():
            break
        c, lv = closes[:, m], level_mat[:, m]
        hit = live & ~np.isnan(c) & ~np.isnan(lv) & (sign * (c - lv) < 0)
        if hit.any():
            stopped |= hit
            pnl[hit] = (sign * (c - entry))[hit]
    return pnl, stopped


def severity(r_bps: np.ndarray, r_atr: np.ndarray, rule: str) -> list[dict]:
    """Loss-severity rows at each ATR threshold."""
    n = len(r_bps)
    out = []
    for th in THRESHOLDS:
        m = r_atr < -th
        k = int(m.sum())
        rec = {"rule": rule, "threshold": th, "n_total": n, "n_loss": k,
               "pct_loss": k / n if n else np.nan}
        if k:
            rec.update({
                "avg_loss_bps": float(r_bps[m].mean()),
                "avg_loss_atr": float(r_atr[m].mean()),
                "median_loss_bps": float(np.median(r_bps[m])),
                "median_loss_atr": float(np.median(r_atr[m])),
                "worst_loss_bps": float(r_bps[m].min()),
                "worst_loss_atr": float(r_atr[m].min()),
                "total_drag_bps": float(r_bps[m].sum() / n),
            })
        else:
            for c in ("avg_loss_bps", "avg_loss_atr", "median_loss_bps",
                      "median_loss_atr", "worst_loss_bps", "worst_loss_atr",
                      "total_drag_bps"):
                rec[c] = np.nan
        out.append(rec)
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df, P = prepare()
    sign, entry, atr = P["sign"], P["entry"], P["atr"]
    opens, adverse, close_exit = P["opens"], P["adverse"], P["close_exit"]
    highs, lows = P["highs"], P["lows"]
    closes = df[[f"close{m}" for m in range(MAX_MIN)]].to_numpy(dtype=float)
    vols = mat(df, "volume")

    prev_close = (df["open"] / (1.0 + df["gap"])).to_numpy(dtype=float)
    or_level = np.where(sign > 0, df["c1_low"].to_numpy(dtype=float),
                        df["c1_high"].to_numpy(dtype=float))
    # Seed weight for rule 7: the first 5-minute candle's volume, taken
    # from the same minute matrix the VWAP is built from rather than from
    # the events table, so the two cannot disagree.
    c1v = np.nansum(vols[:, :ENTRY_MIN], axis=1)
    c1v = np.where(c1v > 0, c1v, np.nanmedian(c1v[c1v > 0]))

    vwap0 = running_vwap(highs, lows, closes, vols)
    vwapg = running_vwap(highs, lows, closes, vols, prev_close, c1v)

    # Constant levels broadcast to a matrix so one scanner handles all.
    def const(level_px):
        return np.repeat(level_px[:, None], MAX_MIN, axis=1)

    results = {}
    results[RULES[0]] = (close_exit.copy(), np.zeros(len(df), dtype=bool))
    for name, lvl in ((RULES[1], const(prev_close)),
                      (RULES[2], const(or_level)),
                      (RULES[5], vwap0), (RULES[6], vwapg)):
        pnl, stopped = scan_close(sign, entry, closes, lvl)
        results[name] = (np.where(stopped, pnl, close_exit), stopped)
    for name, k in ((RULES[3], 0.5), (RULES[4], 1.0)):
        pnl, stopped = apply_stop(sign, entry, atr, opens, adverse,
                                  close_exit, -k * atr, ENTRY_MIN)
        results[name] = (pnl, stopped)

    rows, ctx = [], []
    for name in RULES:
        pnl, stopped = results[name]
        r_bps = pnl / entry * 1e4
        r_atr = pnl / atr
        rows.extend(severity(r_bps, r_atr, name))
        ctx.append({"rule": name, "n": len(df),
                    "pct_stopped": float(stopped.mean()),
                    "net_bps": float(r_bps.mean() - COST_BPS),
                    "win_rate": float((r_bps > 0).mean()),
                    "median_bps": float(np.median(r_bps)),
                    "p10_bps": float(np.quantile(r_bps, 0.10)),
                    "mean_loss_all_bps": float(r_bps[r_bps < 0].mean())})
        log(f"{name}: {stopped.mean()*100:5.1f}% stopped, "
            f"net {ctx[-1]['net_bps']:+.1f}, "
            f">1ATR {rows[-2]['pct_loss']*100:.2f}%")
    R = {"severity": pd.DataFrame(rows), "context": pd.DataFrame(ctx)}

    # Sensitivity of rule 7 to the seed weight, which is a judgement call.
    sens = []
    for mlt in SEED_MULTS:
        vw = running_vwap(highs, lows, closes, vols, prev_close, c1v * mlt)
        pnl, stopped = scan_close(sign, entry, closes, vw)
        pnl = np.where(stopped, pnl, close_exit)
        r_bps, r_atr = pnl / entry * 1e4, pnl / atr
        sens.append({"seed_mult": mlt, "pct_stopped": float(stopped.mean()),
                     "net_bps": float(r_bps.mean() - COST_BPS),
                     "pct_loss_1atr": float((r_atr < -1.0).mean()),
                     "pct_loss_05atr": float((r_atr < -0.5).mean()),
                     "avg_loss_1atr_bps": float(r_bps[r_atr < -1.0].mean())
                     if (r_atr < -1.0).any() else np.nan})
    R["seed_sens"] = pd.DataFrame(sens)

    meta = {"cost_bps": COST_BPS, "vol_mult": VOL_MULT,
            "vol_window": VOL_WINDOW, "n": int(len(df)),
            "start": str(df["date"].min().date()),
            "end": str(df["date"].max().date()),
            "n_checks": len(CHECKS), "exit_min": EXIT_MIN,
            "thresholds": list(THRESHOLDS)}
    for k, v in R.items():
        v.to_csv(OUT_DIR / f"loss_{k}.csv", index=False)
    FEED.write_text(json.dumps(
        {"meta": meta, **{k: json.loads(v.round(6).to_json(orient="records"))
                          for k, v in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables")

    from lossanalysis_text import build  # noqa: E402
    REPORT.write_text(build(R, meta))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
