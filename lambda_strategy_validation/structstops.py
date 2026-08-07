"""
structstops.py — structural stop-loss rules on the post-earnings
continuation setup, as opposed to the volatility-scaled ATR stops in
stops.py / stops_tight.py.

    Rule 1  Opening Range   long: below the 09:30-09:35 candle's LOW
                            short: above that candle's HIGH
    Rule 2  Gap Level       long: below the prior day's close
                            short: above the prior day's close
    Rule 3  Combined        whichever of rule 1 or rule 2 triggers first
    Baseline                no stop, hold to 1 hour

CONFIRMATION ON THE 5-MINUTE CLOSE, NOT INTRABAR
  The specification asks for a 5-minute close to confirm the break, so
  the level is checked only at 09:40, 09:45, ... 10:35 -- twelve
  checkpoints -- and only against the CLOSE of each 5-minute bar. An
  intrabar poke through the level that closes back inside does not
  trigger. This is a materially different mechanism from the ATR stops,
  which fire on the first intrabar touch, and the two are not directly
  comparable on stop-out rate alone.

  The consequence is that a confirmed break can fill well beyond its
  level: price is under no obligation to sit on the line at the moment
  the bar closes. So unlike an ATR stop, a structural stop cannot cap
  the loss at its own distance, and the realised-loss tail is not
  truncated the way it is for a tight ATR stop.

EXIT PRICE
  Primary: the confirming 5-minute close. A robustness column re-prices
  every exit at the NEXT minute's open, since a close cannot actually be
  traded at the instant it is observed. The gap between the two is the
  cost of the confirmation convention.

LEVELS ARE NOT NORMALISED BY VOLATILITY
  That is the point of testing them, but it means the stop distance
  varies event by event. Section 2 reports the distance of each rule in
  ATR units so the results can be read against the ATR ladder.

Cohort, entry, ATR and cost are unchanged from stops.py, whose
prepare() builds the sample.

Run: python3 lambda_strategy_validation/structstops.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from stops import (  # noqa: E402
    COST_BPS, ENTRY_MIN, EXIT_MIN, MAX_MIN, OUT_DIR, SMALL, VOL_MULT,
    VOL_WINDOW, describe, log, prepare,
)

BASE = Path("/home/user/lambda_data")
FEED = BASE / "structstops_feed.json"
REPORT = Path(__file__).resolve().parent / "STRUCTSTOPS_REPORT.md"

# 5-minute bar closes from the first full bar after entry through 10:35.
CHECKS = list(range(ENTRY_MIN + 4, EXIT_MIN + 1, 5))   # 9, 14, ... 64

R1 = "Rule 1 — Opening Range"
R2 = "Rule 2 — Gap Level"
R3 = "Rule 3 — Combined"
NOSTOP = "Baseline — no stop"


def scan(sign, entry, closes, opens, level_signed):
    """Trigger on the first 5-minute CLOSE beyond `level_signed`.

    Returns (pnl_at_close, pnl_at_next_open, stopped, first_check_minute).
    """
    n = len(entry)
    sclose = sign[:, None] * (closes - entry[:, None])
    sopen = sign[:, None] * (opens - entry[:, None])

    stopped = np.zeros(n, dtype=bool)
    at_close = np.full(n, np.nan)
    at_open = np.full(n, np.nan)
    when = np.full(n, -1)

    for m in CHECKS:
        live = ~stopped
        if not live.any():
            break
        c = sclose[:, m]
        hit = live & ~np.isnan(c) & (c < level_signed)
        if not hit.any():
            continue
        stopped |= hit
        at_close[hit] = c[hit]
        when[hit] = m
        # A close cannot be traded at the instant it prints; the next
        # minute's open is the earliest realistic fill.
        nxt = m + 1
        if nxt < MAX_MIN:
            o = sopen[:, nxt]
            at_open[hit] = np.where(np.isnan(o[hit]), c[hit], o[hit])
        else:
            at_open[hit] = c[hit]
    return at_close, at_open, stopped, when


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df, P = prepare()
    sign, entry, atr = P["sign"], P["entry"], P["atr"]
    opens, close_exit = P["opens"], P["close_exit"]
    closes = df[[f"close{m}" for m in range(MAX_MIN)]].to_numpy(dtype=float)
    dates = df["date"]

    prev_close = (df["open"] / (1.0 + df["gap"])).to_numpy(dtype=float)
    or_level = np.where(sign > 0, df["c1_low"].to_numpy(dtype=float),
                        df["c1_high"].to_numpy(dtype=float))

    lvl_or = sign * (or_level - entry)
    lvl_gap = sign * (prev_close - entry)
    lvl_comb = np.maximum(lvl_or, lvl_gap)   # whichever is nearer = tighter

    rows, extra = [], []
    for name, lvl in ((R1, lvl_or), (R2, lvl_gap), (R3, lvl_comb)):
        ac, ao, stopped, when = scan(sign, entry, closes, opens, lvl)
        pnl = np.where(stopped, ac, close_exit)
        pnl_o = np.where(stopped, ao, close_exit)
        rows.append(describe(pd.Series(pnl / entry), pd.Series(pnl / atr),
                             dates, stopped, {"rule": name}))
        # Robustness: same rule, filled at the next minute's open.
        r_o = pd.Series(pnl_o / entry)
        rows[-1]["net_nextopen_bps"] = float(
            (r_o.mean() - COST_BPS / 1e4) * 1e4)
        rows[-1]["median_nextopen_bps"] = float(r_o.median() * 1e4)

        d_atr = -lvl / atr
        overshoot = np.where(stopped, (lvl - ac) / atr, np.nan)
        extra.append({
            "rule": name,
            "median_dist_atr": float(np.nanmedian(d_atr)),
            "p25_dist_atr": float(np.nanquantile(d_atr, 0.25)),
            "p75_dist_atr": float(np.nanquantile(d_atr, 0.75)),
            "median_dist_bps": float(np.nanmedian(-lvl / entry) * 1e4),
            "pct_level_above_entry": float((lvl >= 0).mean()),
            "n_stopped": int(stopped.sum()),
            "median_overshoot_atr": float(np.nanmedian(overshoot))
            if stopped.any() else np.nan,
            "mean_stop_minute": float(np.nanmean(np.where(stopped, when,
                                                          np.nan)))
            if stopped.any() else np.nan,
        })

    rows.append(describe(pd.Series(close_exit / entry),
                         pd.Series(close_exit / atr), dates,
                         np.zeros(len(df), dtype=bool), {"rule": NOSTOP}))
    rows[-1]["net_nextopen_bps"] = rows[-1]["net_bps"]
    rows[-1]["median_nextopen_bps"] = rows[-1]["median_bps"]

    R = {"main": pd.DataFrame(rows), "levels": pd.DataFrame(extra)}

    # What the stopped trades would have done if left alone.
    att = []
    for name, lvl in ((R1, lvl_or), (R2, lvl_gap), (R3, lvl_comb)):
        ac, _, stopped, _ = scan(sign, entry, closes, opens, lvl)
        if stopped.sum() < 30:
            continue
        held = close_exit / entry
        realised = np.where(stopped, ac, close_exit) / entry
        att.append({
            "rule": name, "n_stopped": int(stopped.sum()),
            "pct_stopped": float(stopped.mean()),
            "stopped_realised_bps": float(realised[stopped].mean() * 1e4),
            "stopped_if_held_bps": float(held[stopped].mean() * 1e4),
            "pct_would_recover": float((held[stopped] > 0).mean()),
            "untouched_bps": float(held[~stopped].mean() * 1e4),
        })
    R["attribution"] = pd.DataFrame(att)

    meta = {"cost_bps": COST_BPS, "small": SMALL, "vol_mult": VOL_MULT,
            "vol_window": VOL_WINDOW, "n": int(len(df)),
            "start": str(df["date"].min().date()),
            "end": str(df["date"].max().date()),
            "n_checks": len(CHECKS), "first_check": CHECKS[0],
            "last_check": CHECKS[-1]}
    for k, v in R.items():
        v.to_csv(OUT_DIR / f"struct_{k}.csv", index=False)
    FEED.write_text(json.dumps(
        {"meta": meta, **{k: json.loads(v.round(6).to_json(orient="records"))
                          for k, v in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables")

    from structstops_text import build  # noqa: E402
    REPORT.write_text(build(R, meta))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
