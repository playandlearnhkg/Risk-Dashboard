"""
intrastruct.py — INTRABAR versions of the structural stops, over the full
holding period.

    1  Opening Range : first touch beyond the 09:30-09:35 candle's
                       low (long) / high (short)
    2  Gap Level     : first touch beyond the prior day's close
    3  Combined      : first touch of whichever level is nearer
    4  Baseline      : no stop, hold to 10:35

WHY THIS TEST EXISTS
  STOPSUMMARY_REPORT.md found that the close-confirmed structural rules
  overshoot their level by 27-37 bps on every stop, and that adding that
  overshoot back would put all of them ahead of holding. It suggested an
  intrabar version of the same levels would "capture most of that gap".

  That suggestion contained a flaw, and this script is the test of it.
  The add-back counterfactual held the STOPPED SET fixed and only
  improved the fill. An intrabar trigger does not do that: it fires on
  every temporary poke through the level, so it stops a much larger and
  differently-composed set of trades. Better fills on more stops is not
  the same trade as better fills on the same stops.

  Both close-confirmed variants are recomputed here on the same cohort
  so the comparison is exact rather than quoted.

FILL MODEL
  Fill at the level, unless the bar opened already through it, in which
  case the fill is the bar's open. Overshoot is intended level minus
  realised fill, in the adverse direction.

Run: python3 lambda_strategy_validation/intrastruct.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import analysis as A  # noqa: E402
from stops import (  # noqa: E402
    COST_BPS, EXIT_MIN, MAX_MIN, N_BOOT, OUT_DIR, VOL_MULT, VOL_WINDOW,
    log, prepare,
)
from stopsummary import scan_close, scan_intrabar  # noqa: E402
from winrate_report import wilson  # noqa: E402

BASE = Path("/home/user/lambda_data")
FEED = BASE / "intrastruct_feed.json"
REPORT = Path(__file__).resolve().parent / "INTRASTRUCT_REPORT.md"

NOSTOP = "4. No stop (baseline)"
R1 = "1. Opening Range"
R2 = "2. Gap Level"
R3 = "3. Combined"
RULES = [R1, R2, R3, NOSTOP]


def measure(pnl, stopped, lvl, entry, atr, dates, n, label) -> dict:
    r = pd.Series(pnl / entry)
    r_bps = (pnl / entry) * 1e4
    r_atr = pnl / atr
    k = int((r > 0).sum())
    lo, hi = wilson(k, n)
    bn = A.clustered_bootstrap(r - COST_BPS / 1e4, dates, n_boot=N_BOOT)
    wins, losses = r_bps[r_bps > 0], r_bps[r_bps < 0]
    aw = wins.mean() if len(wins) else np.nan
    al = -losses.mean() if len(losses) else np.nan
    m1 = r_atr < -1.0

    rec = dict(label)
    rec.update({
        "n": n, "pct_stopped": float(stopped.mean()),
        "win_rate": k / n, "wilson_lo": lo, "wilson_hi": hi,
        "net_bps": bn["stat"] * 1e4, "net_p": bn["p"],
        "net_ci_lo": bn["lo"] * 1e4, "net_ci_hi": bn["hi"] * 1e4,
        "avg_win_bps": aw, "avg_loss_bps": al,
        "payoff_ratio": (aw / al) if al else np.nan,
        "median_bps": float(np.median(r_bps)),
        "p10_bps": float(np.quantile(r_bps, 0.10)),
        "std_bps": float(r_bps.std()),
        "pct_loss_1atr": float(m1.mean()),
        "n_loss_1atr": int(m1.sum()),
        "avg_loss_1atr_bps": float(r_bps[m1].mean()) if m1.any() else np.nan,
        "avg_loss_1atr_atr": float(r_atr[m1].mean()) if m1.any() else np.nan,
        "worst_loss_bps": float(r_bps[m1].min()) if m1.any() else np.nan,
        "drag_1atr_bps": float(r_bps[m1].sum() / n) if m1.any() else 0.0,
    })
    if stopped.any():
        s = stopped
        over_px = lvl[s] - pnl[s]
        over_bps = over_px / entry[s] * 1e4
        over_atr = over_px / atr[s]
        rec.update({
            "n_stopped": int(s.sum()),
            "pct_worse": float((over_px > 1e-9).mean()),
            "avg_over_bps": float(over_bps.mean()),
            "avg_over_atr": float(over_atr.mean()),
            "median_over_bps": float(np.median(over_bps)),
            "worst_over_bps": float(over_bps.max()),
            "worst_over_atr": float(over_atr.max()),
            "over_drag_bps": float(-over_bps.sum() / n),
        })
    else:
        for c in ("pct_worse", "avg_over_bps", "avg_over_atr",
                  "median_over_bps", "worst_over_bps", "worst_over_atr"):
            rec[c] = np.nan
        rec["n_stopped"] = 0
        rec["over_drag_bps"] = 0.0
    return rec


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df, P = prepare()
    sign, entry, atr = P["sign"], P["entry"], P["atr"]
    opens, adverse, close_exit = P["opens"], P["adverse"], P["close_exit"]
    closes = df[[f"close{m}" for m in range(MAX_MIN)]].to_numpy(dtype=float)
    dates = df["date"]
    n = len(df)

    prev_close = (df["open"] / (1.0 + df["gap"])).to_numpy(dtype=float)
    or_px = np.where(sign > 0, df["c1_low"].to_numpy(dtype=float),
                     df["c1_high"].to_numpy(dtype=float))

    lvl_or = sign * (or_px - entry)
    lvl_gap = sign * (prev_close - entry)
    lvl_comb = np.maximum(lvl_or, lvl_gap)   # nearer level binds first

    def const(x):
        return np.repeat(x[:, None], MAX_MIN, axis=1)

    rows = []
    specs = [(R1, lvl_or, or_px), (R2, lvl_gap, prev_close),
             (R3, lvl_comb, None)]
    for name, lvl, _ in specs:
        pnl, stopped, at_lvl = scan_intrabar(sign, entry, opens, adverse,
                                             close_exit, lvl)
        rows.append(measure(pnl, stopped, at_lvl, entry, atr, dates, n,
                            {"rule": name, "trigger": "intrabar"}))
        log(f"{name} intrabar: {stopped.mean()*100:5.1f}% stopped, "
            f"net {rows[-1]['net_bps']:+.1f}, "
            f"overshoot {rows[-1]['avg_over_bps']:.2f} bps")

    # Close-confirmed counterparts, recomputed on this cohort so the
    # comparison is exact rather than quoted from the earlier report.
    for name, lvl_px in ((R1, or_px), (R2, prev_close)):
        pnl, stopped, at_lvl = scan_close(sign, entry, closes, close_exit,
                                          const(lvl_px))
        rows.append(measure(pnl, stopped, at_lvl, entry, atr, dates, n,
                            {"rule": name, "trigger": "5-min close"}))
    # Combined, close-confirmed: nearer level, evaluated per checkpoint.
    comb_px = np.where(lvl_or >= lvl_gap, or_px, prev_close)
    pnl, stopped, at_lvl = scan_close(sign, entry, closes, close_exit,
                                      const(comb_px))
    rows.append(measure(pnl, stopped, at_lvl, entry, atr, dates, n,
                        {"rule": R3, "trigger": "5-min close"}))

    rows.append(measure(close_exit.copy(), np.zeros(n, dtype=bool),
                        np.full(n, np.nan), entry, atr, dates, n,
                        {"rule": NOSTOP, "trigger": "—"}))
    R = {"main": pd.DataFrame(rows)}

    # Did the "intrabar would capture the overshoot gap" prediction hold?
    m = R["main"].set_index(["rule", "trigger"])
    base_net = m.loc[(NOSTOP, "—"), "net_bps"]
    chk = []
    for name in (R1, R2, R3):
        cc = m.loc[(name, "5-min close")]
        ib = m.loc[(name, "intrabar")]
        chk.append({
            "rule": name,
            "cc_net": cc["net_bps"], "cc_stopped": cc["pct_stopped"],
            "cc_over_drag": cc["over_drag_bps"],
            "predicted_net": cc["net_bps"] - cc["over_drag_bps"],
            "ib_net": ib["net_bps"], "ib_stopped": ib["pct_stopped"],
            "ib_over_drag": ib["over_drag_bps"],
            "baseline_net": base_net,
            "prediction_met": bool(
                ib["net_bps"] >= cc["net_bps"] - cc["over_drag_bps"] - 1.0),
        })
    R["prediction"] = pd.DataFrame(chk)

    meta = {"cost_bps": COST_BPS, "vol_mult": VOL_MULT,
            "vol_window": VOL_WINDOW, "n": n, "exit_min": EXIT_MIN,
            "start": str(df["date"].min().date()),
            "end": str(df["date"].max().date())}
    for k_, v in R.items():
        v.to_csv(OUT_DIR / f"instr_{k_}.csv", index=False)
    FEED.write_text(json.dumps(
        {"meta": meta, **{k_: json.loads(v.round(6).to_json(orient="records"))
                          for k_, v in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables")

    from intrastruct_text import build  # noqa: E402
    REPORT.write_text(build(R, meta))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
