"""
stops.py — statistical stop-loss rules on the strongest post-earnings
setup (High Volume + Continuation, non-doji, entry at the 09:35 open).

NO LOOK-AHEAD IN THE STOP DISTANCE
  The stop distance is `atr14_prev` = ATR(14) as of the PRIOR session.
  In assemble.py, `atr14` at date d is a 14-session rolling mean of true
  range ending at d; shifting one session gives a window ending at d-1.
  Nothing from the gap day itself enters the stop distance. The stop
  LEVEL for rule B uses the 15-minute price, which is of course known at
  15 minutes -- that is a time-delayed rule, not a look-ahead.

STOPS ARE TESTED AGAINST INTRABAR EXTREMES, NOT CLOSES
  Minute bars carry high and low, so a stop is triggered when the bar's
  adverse extreme (low for a long, high for a short) breaches the level.
  Testing on closes only would badly understate stop-out rates.

FILL MODEL, AND WHY IT MATTERS
  When a bar breaches the stop, the fill is the stop price -- UNLESS the
  bar opened already through it, in which case the fill is the bar's
  open. That second clause is what stops a stop-loss study from quietly
  assuming every stop fills perfectly. Without it, realised losses could
  never exceed the stop distance and the tail metrics would be fiction.
  The "% losing more than -1.0 ATR realised" column on rule A1 is the
  direct read of how often the stop failed to hold its price.

  Still optimistic in one respect: no slippage or spread is added at the
  stop beyond the gap-through, and the flat 6.6 bps round trip is charged
  identically to a stopped trade and a held one. Real stop fills in fast
  post-earnings tape are worse than this.

ZERO-RETURN CONVENTION
  Earlier reports dropped exactly-zero returns as stale prints. A stop
  study must account for every trade it takes, so nothing is dropped
  here. The rule C baseline therefore differs trivially from the +30.1
  bps published in LONGHOLD_REPORT.md; the difference is reported.

Run: python3 lambda_strategy_validation/stops.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

import analysis as A  # noqa: E402
from doji import G_CONT, classify  # noqa: E402
from volume_test import (  # noqa: E402
    COST_BPS, ENTRY_MIN, N_BOOT, SIGNAL_MIN, SMALL, VOL_MULT, VOL_WINDOW,
    log, volume_features,
)
from winrate_report import wilson  # noqa: E402

BASE = Path("/home/user/lambda_data")
OUT_DIR = BASE / "tables"
FEED = BASE / "stops_feed.json"
REPORT = Path(__file__).resolve().parent / "STOPS_REPORT.md"

CONT = G_CONT   # "Continuation (non-doji)" from the doji classifier
MAX_MIN = 65          # minutes 0..64; 64 is the 10:35 exit
EXIT_MIN = 64
DELAY_MIN = 19        # the 15-minute reference price (09:50)

FIELDS = ("open", "high", "low", "close")


def load_paths(ev: pd.DataFrame) -> pd.DataFrame:
    """Per-minute open/high/low/close for minutes 0..64, one row per event."""
    want = set(zip(ev["ticker"], ev["date"]))
    frames = []
    files = sorted((BASE / "intraday210").glob("*.parquet"))
    for i, f in enumerate(files, 1):
        try:
            d = pd.read_parquet(f)
        except Exception:  # noqa: BLE001
            continue
        if d.empty:
            continue
        d["date"] = pd.to_datetime(d["date"])
        d = d[d["minute"] < MAX_MIN]
        d = d[[(t, dt) in want for t, dt in zip(d["ticker"], d["date"])]]
        if not d.empty:
            frames.append(d)
        if i % 250 == 0:
            log(f"  {i}/{len(files)} files")
    raw = pd.concat(frames, ignore_index=True)

    out = None
    for fld in FIELDS:
        w = raw.pivot_table(index=["ticker", "date"], columns="minute",
                            values=fld, aggfunc="last").reindex(
                                columns=range(MAX_MIN))
        w.columns = [f"{fld}{c}" for c in w.columns]
        out = w if out is None else out.join(w)
    sess = raw.groupby(["ticker", "date"])[
        ["session_open", "session_close"]].first()
    return out.join(sess).reset_index()


def mat(df: pd.DataFrame, fld: str) -> np.ndarray:
    return df[[f"{fld}{m}" for m in range(MAX_MIN)]].to_numpy(dtype=float)


def apply_stop(sign, entry, atr, opens, adverse, close_exit,
               level_signed, start_min):
    """Vectorised stop scan.

    level_signed : signed P&L level (in price units) at which the stop
                   triggers, per event. Negative.
    start_min    : first minute the stop is armed.
    Returns (signed_pnl_price, stopped_bool).
    """
    n = len(entry)
    # Signed adverse excursion in price units, per minute.
    sadv = sign[:, None] * (adverse - entry[:, None])
    sopen = sign[:, None] * (opens - entry[:, None])

    hit = np.zeros_like(sadv, dtype=bool)
    hit[:, start_min:] = sadv[:, start_min:] <= level_signed[:, None]
    hit &= ~np.isnan(sadv)

    any_hit = hit.any(axis=1)
    first = np.where(any_hit, hit.argmax(axis=1), -1)

    pnl = np.where(any_hit, np.nan, close_exit)
    idx = np.arange(n)
    h = any_hit
    if h.any():
        bo = sopen[idx[h], first[h]]
        lv = level_signed[h]
        # Fill at the stop, unless the bar opened already through it.
        fill = np.where(np.isnan(bo), lv, np.minimum(bo, lv))
        pnl[h] = fill
    return pnl, any_hit


def describe(r: pd.Series, atr_r: pd.Series, dates: pd.Series,
             stopped: np.ndarray, label: dict) -> dict:
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
    rec.update({
        "n": n, "n_dates": int(pd.Series(dates).nunique()),
        "pct_stopped": float(stopped.mean()),
        "win_rate": k / n if n else np.nan, "wilson_lo": lo, "wilson_hi": hi,
        "avg_win_bps": aw, "avg_loss_bps": al,
        "payoff_ratio": (aw / al) if al else np.nan,
        "mean_bps": float(b.mean()),
        "net_bps": bn["stat"] * 1e4, "net_p": bn["p"],
        "net_ci_lo": bn["lo"] * 1e4, "net_ci_hi": bn["hi"] * 1e4,
        "median_bps": float(q.loc[0.50]), "p10_bps": float(q.loc[0.10]),
        "p25_bps": float(q.loc[0.25]), "p75_bps": float(q.loc[0.75]),
        "p90_bps": float(q.loc[0.90]), "std_bps": float(b.std()),
        "skew": float(stats.skew(b, bias=False)),
        "kurtosis": float(stats.kurtosis(b, fisher=True, bias=False)),
        "pct_loss_gt_1atr": float((atr_r < -1.0).mean()),
        "pct_gain_gt_15atr": float((atr_r > 1.5).mean()),
        "small": "YES" if n < SMALL else "",
    })
    return rec


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    vol = volume_features()
    log("volume features built")

    ev = pd.read_parquet(BASE / "events.parquet")
    ev["date"] = pd.to_datetime(ev["date"])
    ev = ev[ev["gap"] != 0].copy()
    ev["gap_up"] = ev["gap"] > 0

    panel = pd.read_parquet(BASE / "panel.parquet",
                            columns=["ticker", "date", "atr14"])
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel.sort_values(["ticker", "date"])
    panel["atr14_prev"] = panel.groupby("ticker")["atr14"].shift(1)
    ev = ev.merge(panel[["ticker", "date", "atr14_prev"]],
                  on=["ticker", "date"], how="left")
    ev = ev.merge(vol, on=["ticker", "date"], how="left")
    ev = classify(ev)

    paths = load_paths(ev)
    df = ev.merge(paths, on=["ticker", "date"], how="inner", suffixes=("", "_p"))
    log(f"merged paths: {len(df):,}")

    n0 = len(df)
    early = [f"open{i}" for i in range(0, ENTRY_MIN + 1)]
    df = df[df[early].notna().any(axis=1)].copy()
    df["entry_px"] = df[f"open{ENTRY_MIN}"].fillna(df[f"close{SIGNAL_MIN}"])
    df = df[df["entry_px"].notna()].copy()
    df = df[~df["vol_straddle"].fillna(False)]
    df = df[df["vol_ratio"].notna()]
    df["high_vol"] = df["vol_ratio"] > VOL_MULT
    df = df[df["high_vol"] & (df["klass"] == CONT)].copy()
    df = df[df["atr14_prev"].notna() & (df["atr14_prev"] > 0)].copy()
    df = df.reset_index(drop=True)

    # Exit prices are forward-filled from the session open, exactly as
    # load_wide does in every earlier report, so a minute with no print
    # still yields a mark and the cohort stays comparable to the published
    # +30.1 bps baseline. Highs and lows are deliberately NOT filled: a
    # minute that did not trade cannot trigger a stop.
    ccols = [f"close{m}" for m in range(MAX_MIN)]
    cm = df[ccols].copy()
    cm.insert(0, "seed", df["session_open"])
    cm = cm.ffill(axis=1).drop(columns="seed")
    df[ccols] = cm
    n_filled = int(df[f"close{EXIT_MIN}"].notna().sum())
    df = df[df[f"close{EXIT_MIN}"].notna()].copy().reset_index(drop=True)
    log(f"cohort: {len(df):,} (from {n0:,} merged, {n_filled:,} with a mark)")

    sign = np.where(df["gap_up"], 1.0, -1.0)
    entry = df["entry_px"].to_numpy(dtype=float)
    atr = df["atr14_prev"].to_numpy(dtype=float)
    opens = mat(df, "open")
    highs = mat(df, "high")
    lows = mat(df, "low")
    adverse = np.where(sign[:, None] > 0, lows, highs)
    close_exit = sign * (df[f"close{EXIT_MIN}"].to_numpy(dtype=float) - entry)
    ref15 = sign * (df[f"close{DELAY_MIN}"].to_numpy(dtype=float) - entry)

    rules = []
    for k in (1.0, 1.5, 2.0):
        rules.append((f"A{len(rules)+1}. Stop −{k:.1f} ATR from entry",
                      -k * atr, ENTRY_MIN, k))
    for i, k in enumerate((1.0, 1.5), start=4):
        rules.append((f"B{i-3}. No stop 15 min, then −{k:.1f} ATR from "
                      "15-min price", ref15 - k * atr, DELAY_MIN + 1, k))

    rows = []
    dates = df["date"]
    for name, level, start, k in rules:
        pnl, stopped = apply_stop(sign, entry, atr, opens, adverse,
                                  close_exit, level, start)
        r = pd.Series(pnl / entry)
        atr_r = pd.Series(pnl / atr)
        rows.append(describe(r, atr_r, dates, stopped,
                             {"rule": name, "mult": k}))
        log(f"{name}: {stopped.mean()*100:.1f}% stopped, "
            f"net {rows[-1]['net_bps']:+.1f}")

    r = pd.Series(close_exit / entry)
    rows.append(describe(r, pd.Series(close_exit / atr), dates,
                         np.zeros(len(df), dtype=bool),
                         {"rule": "C. No stop (hold to 1 hour)",
                          "mult": np.nan}))
    R = {"main": pd.DataFrame(rows)}

    # Maximum adverse excursion, which is what sets the stop-out rates.
    sadv = sign[:, None] * (adverse - entry[:, None])
    mae = np.nanmin(sadv[:, ENTRY_MIN:EXIT_MIN + 1], axis=1) / atr
    mfe_src = np.where(sign[:, None] > 0, highs, lows)
    mfe = np.nanmax((sign[:, None] * (mfe_src - entry[:, None]))
                    [:, ENTRY_MIN:EXIT_MIN + 1], axis=1) / atr
    qs = [0.10, 0.25, 0.50, 0.75, 0.90]
    R["excursion"] = pd.DataFrame([
        {"metric": "Max adverse excursion (ATR)",
         **{f"p{int(q*100)}": float(np.nanquantile(mae, q)) for q in qs},
         "pct_beyond_1.0": float((mae <= -1.0).mean()),
         "pct_beyond_1.5": float((mae <= -1.5).mean()),
         "pct_beyond_2.0": float((mae <= -2.0).mean())},
        {"metric": "Max favourable excursion (ATR)",
         **{f"p{int(q*100)}": float(np.nanquantile(mfe, q)) for q in qs},
         "pct_beyond_1.0": float((mfe >= 1.0).mean()),
         "pct_beyond_1.5": float((mfe >= 1.5).mean()),
         "pct_beyond_2.0": float((mfe >= 2.0).mean())},
    ])

    # How often did the stop fail to hold its price (gap-through)?
    gt = []
    for name, level, start, k in rules:
        pnl, stopped = apply_stop(sign, entry, atr, opens, adverse,
                                  close_exit, level, start)
        through = stopped & (pnl < level - 1e-9)
        slip = np.where(through, (level - pnl) / atr, np.nan)
        gt.append({"rule": name, "n_stopped": int(stopped.sum()),
                   "n_gap_through": int(through.sum()),
                   "pct_of_stops": float(through.sum() / max(stopped.sum(), 1)),
                   "mean_slip_atr": float(np.nanmean(slip))
                   if through.any() else 0.0,
                   "max_slip_atr": float(np.nanmax(slip))
                   if through.any() else 0.0})
    R["gapthrough"] = pd.DataFrame(gt)

    meta = {"cost_bps": COST_BPS, "small": SMALL, "vol_mult": VOL_MULT,
            "vol_window": VOL_WINDOW, "n": int(len(df)),
            "start": str(df["date"].min().date()),
            "end": str(df["date"].max().date()),
            "exit_min": EXIT_MIN, "delay_min": DELAY_MIN}
    for k_, v in R.items():
        v.to_csv(OUT_DIR / f"stops_{k_}.csv", index=False)
    FEED.write_text(json.dumps(
        {"meta": meta, **{k_: json.loads(v.round(6).to_json(orient="records"))
                          for k_, v in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables")

    from stops_text import build  # noqa: E402
    REPORT.write_text(build(R, meta))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
