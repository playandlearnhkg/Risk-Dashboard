"""
stopsummary.py — consolidated cost/benefit analysis of every major stop
rule tested in this series, with fill-quality (overshoot) measurement.

    1  No stop (baseline)
    2  Gap Level structural       (5-min close beyond the prior close)
    3  Opening Range structural   (5-min close beyond the 09:30-09:35
                                   candle's low/high)
    4  ATR -0.5                   (intrabar touch)
    5  ATR -1.0                   (intrabar touch)
    6  Anchored VWAP from 09:30   (5-min close beyond it)
    7  Anchored VWAP from prior close (5-min close beyond it)

WHAT IS NEW HERE
  Every earlier report measured what a stop RETURNED. This one also
  measures what each stop PROMISED and how far the fill missed it.

  For every stopped trade the scanner records the intended level at the
  moment of the trigger -- for the ATR rules a constant distance, for the
  structural rules a fixed price, for the AVWAP rules the VWAP value at
  the confirming checkpoint. Overshoot is intended minus realised, in the
  adverse direction, expressed in bps and in ATR.

  The asymmetry that falls out of this is structural, not empirical:

    * An INTRABAR stop exits AT its level. It can only fill worse if the
      bar opened through the level, so overshoot is occasional.
    * A CLOSE-CONFIRMED stop exits at whatever the bar closed at, which
      is by definition already beyond the level. Overshoot is therefore
      universal -- 100% of stopped trades by construction -- and only its
      SIZE is an empirical question.

  Reporting "% of stopped trades that filled worse than intended" is
  consequently near-meaningless for rules 2, 3, 6 and 7 and highly
  informative for rules 4 and 5. Both are shown, with that caveat
  attached rather than left for the reader to discover.

OVERSHOOT DRAG
  The decision-relevant summary is total overshoot spread across the
  whole book: sum of overshoot over ALL trades, in bps per trade. That
  is expectancy lost purely to imperfect fills, separable from the
  expectancy lost to the stop firing at all.

Cohort, entry, ATR and cost come from stops.prepare(), so every figure
here is comparable to the earlier reports and reproduces them.

Run: python3 lambda_strategy_validation/stopsummary.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import analysis as A  # noqa: E402
from lossanalysis import running_vwap  # noqa: E402
from stops import (  # noqa: E402
    COST_BPS, ENTRY_MIN, EXIT_MIN, MAX_MIN, N_BOOT, OUT_DIR, VOL_MULT,
    VOL_WINDOW, log, mat, prepare,
)
from structstops import CHECKS  # noqa: E402
from winrate_report import wilson  # noqa: E402

BASE = Path("/home/user/lambda_data")
FEED = BASE / "stopsummary_feed.json"
REPORT = Path(__file__).resolve().parent / "STOPSUMMARY_REPORT.md"

NOSTOP = "1. No stop"
RULES = [NOSTOP, "2. Gap Level", "3. Opening Range", "4. ATR −0.5",
         "5. ATR −1.0", "6. AVWAP 09:30", "7. AVWAP prior close"]
TRIGGER = {NOSTOP: "—", "2. Gap Level": "5-min close",
           "3. Opening Range": "5-min close", "4. ATR −0.5": "intrabar",
           "5. ATR −1.0": "intrabar", "6. AVWAP 09:30": "5-min close",
           "7. AVWAP prior close": "5-min close"}


def scan_intrabar(sign, entry, opens, adverse, close_exit, level):
    """Intrabar touch. Fill at the level, or the bar open if it gapped."""
    n = len(entry)
    sadv = sign[:, None] * (adverse - entry[:, None])
    sopen = sign[:, None] * (opens - entry[:, None])
    hit = np.zeros_like(sadv, dtype=bool)
    hit[:, ENTRY_MIN:] = sadv[:, ENTRY_MIN:] <= level[:, None]
    hit &= ~np.isnan(sadv)
    stopped = hit.any(axis=1)
    first = np.where(stopped, hit.argmax(axis=1), -1)

    pnl = np.where(stopped, np.nan, close_exit)
    lvl = np.full(n, np.nan)
    idx = np.arange(n)
    if stopped.any():
        bo = sopen[idx[stopped], first[stopped]]
        lv = level[stopped]
        pnl[stopped] = np.where(np.isnan(bo), lv, np.minimum(bo, lv))
        lvl[stopped] = lv
    return pnl, stopped, lvl


def scan_close(sign, entry, closes, close_exit, level_mat):
    """First 5-minute CLOSE beyond a possibly time-varying level."""
    n = len(entry)
    stopped = np.zeros(n, dtype=bool)
    pnl = np.full(n, np.nan)
    lvl = np.full(n, np.nan)
    for m in CHECKS:
        live = ~stopped
        if not live.any():
            break
        c, lv = closes[:, m], level_mat[:, m]
        hit = live & ~np.isnan(c) & ~np.isnan(lv) & (sign * (c - lv) < 0)
        if hit.any():
            stopped |= hit
            pnl[hit] = (sign * (c - entry))[hit]
            lvl[hit] = (sign * (lv - entry))[hit]
    pnl = np.where(stopped, pnl, close_exit)
    return pnl, stopped, lvl


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df, P = prepare()
    sign, entry, atr = P["sign"], P["entry"], P["atr"]
    opens, adverse, close_exit = P["opens"], P["adverse"], P["close_exit"]
    highs, lows = P["highs"], P["lows"]
    closes = df[[f"close{m}" for m in range(MAX_MIN)]].to_numpy(dtype=float)
    vols = mat(df, "volume")
    dates = df["date"]
    n = len(df)

    prev_close = (df["open"] / (1.0 + df["gap"])).to_numpy(dtype=float)
    or_level = np.where(sign > 0, df["c1_low"].to_numpy(dtype=float),
                        df["c1_high"].to_numpy(dtype=float))
    c1v = np.nansum(vols[:, :ENTRY_MIN], axis=1)
    c1v = np.where(c1v > 0, c1v, np.nanmedian(c1v[c1v > 0]))

    vwap0 = running_vwap(highs, lows, closes, vols)
    vwapg = running_vwap(highs, lows, closes, vols, prev_close, c1v)

    def const(px):
        return np.repeat(px[:, None], MAX_MIN, axis=1)

    res = {NOSTOP: (close_exit.copy(), np.zeros(n, dtype=bool),
                    np.full(n, np.nan))}
    res["2. Gap Level"] = scan_close(sign, entry, closes, close_exit,
                                     const(prev_close))
    res["3. Opening Range"] = scan_close(sign, entry, closes, close_exit,
                                         const(or_level))
    res["4. ATR −0.5"] = scan_intrabar(sign, entry, opens, adverse,
                                       close_exit, -0.5 * atr)
    res["5. ATR −1.0"] = scan_intrabar(sign, entry, opens, adverse,
                                       close_exit, -1.0 * atr)
    res["6. AVWAP 09:30"] = scan_close(sign, entry, closes, close_exit, vwap0)
    res["7. AVWAP prior close"] = scan_close(sign, entry, closes, close_exit,
                                             vwapg)

    core, tail, fill = [], [], []
    for name in RULES:
        pnl, stopped, lvl = res[name]
        r = pd.Series(pnl / entry)
        r_bps = (pnl / entry) * 1e4
        r_atr = pnl / atr

        # ---- A. core ----
        k = int((r > 0).sum())
        lo, hi = wilson(k, n)
        bn = A.clustered_bootstrap(r - COST_BPS / 1e4, dates, n_boot=N_BOOT)
        wins, losses = r_bps[r_bps > 0], r_bps[r_bps < 0]
        aw = wins.mean() if len(wins) else np.nan
        al = -losses.mean() if len(losses) else np.nan
        core.append({
            "rule": name, "trigger": TRIGGER[name], "n": n,
            "pct_stopped": float(stopped.mean()), "win_rate": k / n,
            "wilson_lo": lo, "wilson_hi": hi,
            "net_bps": bn["stat"] * 1e4, "net_p": bn["p"],
            "avg_win_bps": aw, "avg_loss_bps": al,
            "payoff_ratio": (aw / al) if al else np.nan,
            "median_bps": float(np.median(r_bps)),
            "p10_bps": float(np.quantile(r_bps, 0.10)),
            "std_bps": float(r_bps.std()),
        })

        # ---- B. tail ----
        m1 = r_atr < -1.0
        rec = {"rule": name, "n_loss": int(m1.sum()),
               "pct_loss": float(m1.mean())}
        if m1.any():
            rec.update({
                "avg_loss_bps": float(r_bps[m1].mean()),
                "avg_loss_atr": float(r_atr[m1].mean()),
                "median_loss_bps": float(np.median(r_bps[m1])),
                "median_loss_atr": float(np.median(r_atr[m1])),
                "worst_loss_bps": float(r_bps[m1].min()),
                "worst_loss_atr": float(r_atr[m1].min()),
                "drag_bps": float(r_bps[m1].sum() / n)})
        else:
            for c in ("avg_loss_bps", "avg_loss_atr", "median_loss_bps",
                      "median_loss_atr", "worst_loss_bps", "worst_loss_atr"):
                rec[c] = np.nan
            rec["drag_bps"] = 0.0
        tail.append(rec)

        # ---- C. fill quality ----
        if not stopped.any():
            fill.append({"rule": name, "trigger": TRIGGER[name],
                         "n_stopped": 0, "pct_worse": np.nan,
                         "avg_over_bps": np.nan, "avg_over_atr": np.nan,
                         "median_over_bps": np.nan, "worst_over_bps": np.nan,
                         "worst_over_atr": np.nan, "drag_bps": 0.0,
                         "mean_intended_bps": np.nan,
                         "mean_realised_bps": np.nan})
            continue
        s = stopped
        over_px = lvl[s] - pnl[s]            # >0 means filled worse
        over_bps = over_px / entry[s] * 1e4
        over_atr = over_px / atr[s]
        worse = over_px > 1e-9
        fill.append({
            "rule": name, "trigger": TRIGGER[name],
            "n_stopped": int(s.sum()),
            "pct_worse": float(worse.mean()),
            "avg_over_bps": float(over_bps.mean()),
            "avg_over_atr": float(over_atr.mean()),
            "median_over_bps": float(np.median(over_bps)),
            "median_over_atr": float(np.median(over_atr)),
            "worst_over_bps": float(over_bps.max()),
            "worst_over_atr": float(over_atr.max()),
            # expectancy lost to imperfect fills, spread over the book
            "drag_bps": float(over_bps.sum() * -1 / n),
            "mean_intended_bps": float((lvl[s] / entry[s]).mean() * 1e4),
            "mean_realised_bps": float((pnl[s] / entry[s]).mean() * 1e4),
        })
        log(f"{name}: {s.mean()*100:5.1f}% stopped, "
            f"overshoot {over_bps.mean():.1f} bps on "
            f"{worse.mean()*100:.0f}% of stops")

    R = {"core": pd.DataFrame(core), "tail": pd.DataFrame(tail),
         "fill": pd.DataFrame(fill)}

    # ---- D. efficiency ----
    c = R["core"].set_index("rule")
    t = R["tail"].set_index("rule")
    f = R["fill"].set_index("rule")
    bn_, bt = c.loc[NOSTOP, "net_bps"], t.loc[NOSTOP, "pct_loss"] * 100
    eff = []
    for name in RULES:
        if name == NOSTOP:
            continue
        paid = bn_ - c.loc[name, "net_bps"]
        cut = bt - t.loc[name, "pct_loss"] * 100
        eff.append({
            "rule": name, "trigger": TRIGGER[name],
            "cost_bps": paid, "tail_cut_pp": cut,
            "ratio": cut / paid if paid > 0 else np.nan,
            "remaining_severity_bps": t.loc[name, "avg_loss_bps"],
            "overshoot_drag_bps": f.loc[name, "drag_bps"],
            "overshoot_share": (abs(f.loc[name, "drag_bps"]) / paid
                                if paid > 0 else np.nan),
            "drag_improve_bps": t.loc[NOSTOP, "drag_bps"]
            - t.loc[name, "drag_bps"],
        })
    R["efficiency"] = pd.DataFrame(eff).sort_values("ratio", ascending=False)

    meta = {"cost_bps": COST_BPS, "vol_mult": VOL_MULT,
            "vol_window": VOL_WINDOW, "n": n,
            "start": str(df["date"].min().date()),
            "end": str(df["date"].max().date()),
            "exit_min": EXIT_MIN, "n_checks": len(CHECKS)}
    for k_, v in R.items():
        v.to_csv(OUT_DIR / f"sum_{k_}.csv", index=False)
    FEED.write_text(json.dumps(
        {"meta": meta, **{k_: json.loads(v.round(6).to_json(orient="records"))
                          for k_, v in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables")

    from stopsummary_text import build  # noqa: E402
    REPORT.write_text(build(R, meta))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
