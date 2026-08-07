"""
entrylimits.py — limit-order entries on the post-earnings continuation
setup, against the market-on-open-of-09:35 baseline.

    Group A — retracement of the first 5-minute candle's RANGE
      1  25% of the range back from the candle's extreme
      2  50%  (the candle midpoint)
      3  75%  (a deep pullback, near the far end of the candle)
    Group B — anchored on the candle's OPEN and CLOSE
      4  the candle's close
      5  the midpoint of open and close
      6  the candle's open
    Baseline
      7  market order at the open of the 09:35 bar

  For a long (gap up) the retracement anchor is the candle HIGH and the
  limit sits pct x range below it, so 50% lands exactly on the candle
  midpoint -- which is the reading the specification's own "(midpoint)"
  annotation confirms. For a short the anchor is the candle LOW and the
  limit sits pct x range above it.

FILL WINDOW
  The order is live from 09:35 and is cancelled if unfilled at 09:50
  (minute 19), the same 15-minute mark used as a reference throughout
  this series. A 10:00 (minute 29) window is reported alongside so the
  choice is visible rather than assumed.

FILL MODEL
  A buy limit fills when a minute's LOW trades at or below it; a sell
  limit when a minute's HIGH trades at or above it. The fill price is
  the limit -- unless the bar OPENED already through it, in which case
  the fill is the bar's open, which is a better price. That includes the
  09:35 bar itself: if the session has already pulled back past the
  limit by the time the order goes in, it fills immediately at the open.

EXIT
  10:35 in every case. No stop is applied, so the baseline row is the
  same +30.4 bps no-stop figure as the stop reports.

THE SELECTION PROBLEM, WHICH IS THE WHOLE STORY
  A limit order only fills if price comes back to it. Trades that run
  away immediately never fill -- and on a continuation setup those are
  the best ones. Reporting "only the filled trades", as asked, therefore
  measures a self-selected sample and cannot on its own say whether the
  method is better. Section 4 adds the two figures that can: expectancy
  per SIGNAL (expectancy per fill x fill rate) and what the unfilled
  trades would have returned.

Run: python3 lambda_strategy_validation/entrylimits.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import analysis as A  # noqa: E402
from stops import (  # noqa: E402
    COST_BPS, ENTRY_MIN, EXIT_MIN, MAX_MIN, N_BOOT, OUT_DIR, SMALL,
    VOL_MULT, VOL_WINDOW, log, prepare,
)
from winrate_report import wilson  # noqa: E402

BASE = Path("/home/user/lambda_data")
FEED = BASE / "entrylimits_feed.json"
REPORT = Path(__file__).resolve().parent / "ENTRYLIMITS_REPORT.md"

WINDOWS = {"09:50": 19, "10:00": 29}
PRIMARY = "09:50"

RANGE_PCTS = [("A1. 25% of range", 0.25), ("A2. 50% of range (midpoint)", 0.50),
              ("A3. 75% of range", 0.75)]
BASELINE = "7. Market at 09:35 open"


def fill_scan(sign, limit, lows, highs, opens, last_min):
    """First minute in [ENTRY_MIN, last_min] at which the limit fills.

    Returns (fill_price, filled_bool).
    """
    n = len(limit)
    # Favourable-side extreme: a buy limit needs the low, a sell the high.
    touch = np.where(sign[:, None] > 0, lows, highs)
    # signed distance: negative once price has reached through the limit
    reach = sign[:, None] * (touch - limit[:, None])

    filled = np.zeros(n, dtype=bool)
    price = np.full(n, np.nan)
    for m in range(ENTRY_MIN, last_min + 1):
        live = ~filled
        if not live.any():
            break
        r = reach[:, m]
        hit = live & ~np.isnan(r) & (r <= 0)
        if not hit.any():
            continue
        filled |= hit
        o = opens[:, m]
        # Fill at the limit, or at the open if the bar opened through it.
        better = sign * (o - limit) <= 0
        price[hit] = np.where(better[hit] & ~np.isnan(o[hit]),
                              o[hit], limit[hit])
    return price, filled


def metrics(r: pd.Series, dates: pd.Series, n_signals: int,
            label: dict) -> dict:
    n = len(r)
    k = int((r > 0).sum())
    lo, hi = wilson(k, n)
    bn = A.clustered_bootstrap(r - COST_BPS / 1e4, dates, n_boot=N_BOOT)
    wins, losses = r[r > 0], r[r < 0]
    aw = wins.mean() * 1e4 if len(wins) else np.nan
    al = -losses.mean() * 1e4 if len(losses) else np.nan
    b = r * 1e4
    q = b.quantile([0.10, 0.25, 0.50, 0.75, 0.90])
    rec = dict(label)
    net = bn["stat"] * 1e4
    rec.update({
        "n": n, "n_signals": n_signals, "fill_rate": n / n_signals,
        "win_rate": k / n if n else np.nan, "wilson_lo": lo, "wilson_hi": hi,
        "avg_win_bps": aw, "avg_loss_bps": al,
        "payoff_ratio": (aw / al) if al else np.nan,
        "net_bps": net, "net_p": bn["p"],
        "net_ci_lo": bn["lo"] * 1e4, "net_ci_hi": bn["hi"] * 1e4,
        "median_bps": float(q.loc[0.50]), "p10_bps": float(q.loc[0.10]),
        "p25_bps": float(q.loc[0.25]), "p75_bps": float(q.loc[0.75]),
        "p90_bps": float(q.loc[0.90]), "std_bps": float(b.std()),
        # The deployment-relevant number: an unfilled signal earns nothing.
        "net_per_signal_bps": net * (n / n_signals),
        "small": "YES" if n < SMALL else "",
    })
    return rec


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df, P = prepare()
    sign, entry = P["sign"], P["entry"]
    opens, highs, lows = P["opens"], P["highs"], P["lows"]
    exit_px = df[f"close{EXIT_MIN}"].to_numpy(dtype=float)
    dates = df["date"]
    n_signals = len(df)

    c1o = df["c1_open"].to_numpy(dtype=float)
    c1c = df["c1_close"].to_numpy(dtype=float)
    c1h = df["c1_high"].to_numpy(dtype=float)
    c1l = df["c1_low"].to_numpy(dtype=float)
    rng = c1h - c1l

    # Anchor at the extreme in the trade's direction; retrace against it.
    anchor = np.where(sign > 0, c1h, c1l)
    limits = {}
    for name, pct in RANGE_PCTS:
        limits[name] = anchor - sign * pct * rng
    limits["B4. Candle close"] = c1c
    limits["B5. Midpoint of open & close"] = (c1o + c1c) / 2.0
    limits["B6. Candle open"] = c1o

    rows, extra = [], []
    for wname, wmin in WINDOWS.items():
        for name, lim in limits.items():
            px, filled = fill_scan(sign, lim, lows, highs, opens, wmin)
            r = pd.Series((sign * (exit_px / px - 1.0))[filled])
            if len(r) < 30:
                continue
            rows.append(metrics(r, dates[filled], n_signals,
                                {"rule": name, "window": wname}))
            if wname == PRIMARY:
                # What the signals this rule MISSED would have paid on the
                # baseline entry -- the opportunity cost of being patient.
                base_r = sign * (exit_px / entry - 1.0)
                extra.append({
                    "rule": name,
                    "n_filled": int(filled.sum()),
                    "n_missed": int((~filled).sum()),
                    "missed_baseline_bps": float(
                        base_r[~filled].mean() * 1e4 - COST_BPS)
                    if (~filled).any() else np.nan,
                    "filled_baseline_bps": float(
                        base_r[filled].mean() * 1e4 - COST_BPS),
                    "median_improve_bps": float(np.nanmedian(
                        (sign * (entry - px) / entry)[filled]) * 1e4),
                })
        # baseline, unchanged across windows
        r = pd.Series(sign * (exit_px / entry - 1.0))
        rows.append(metrics(r, dates, n_signals,
                            {"rule": BASELINE, "window": wname}))
    R = {"main": pd.DataFrame(rows), "opportunity": pd.DataFrame(extra)}

    meta = {"cost_bps": COST_BPS, "small": SMALL, "vol_mult": VOL_MULT,
            "vol_window": VOL_WINDOW, "n_signals": n_signals,
            "start": str(df["date"].min().date()),
            "end": str(df["date"].max().date()),
            "primary_window": PRIMARY, "exit_min": EXIT_MIN,
            "windows": {k: v for k, v in WINDOWS.items()}}
    for k, v in R.items():
        v.to_csv(OUT_DIR / f"entlim_{k}.csv", index=False)
    FEED.write_text(json.dumps(
        {"meta": meta, **{k: json.loads(v.round(6).to_json(orient="records"))
                          for k, v in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables")

    from entrylimits_text import build  # noqa: E402
    REPORT.write_text(build(R, meta))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
