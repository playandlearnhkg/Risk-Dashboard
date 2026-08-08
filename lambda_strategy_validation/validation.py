"""
validation.py — focused validation and diagnostic review of the
post-earnings T+1 research, plus a full extract for independent checking.

Parts
  1  trade characteristics: sector, stage, time, gap/ATR, volume ratio,
     candle body strength
  2  distribution shape for the core rule and the main stops
  3  new diagnostics: what the stops actually cut, why limit entries
     selected weak trades, what that implies for sizing
  4  AVWAP stop with a practitioner's buffer
  5  full post-earnings extract, one row per event, before the High
     Volume + Continuation filter

A FINDING THAT BELONGS AT THE TOP
  `events.parquet` holds 17,583 post-earnings T+1 events, of which only
  10,122 pass `universe_ok_prev` -- the Sigma screen (price >= $10,
  ADV >= 500k shares, ADTV >= $50M, market cap >= $3B, all prior
  session). The cohort used by every report in this series never applied
  that screen: prep_earnings() reads events.parquet and filters only on
  gap != 0. So 41.6% of the headline cohort sits outside the stated
  universe. Section 0 measures whether the edge survives the screen.

  The binding constraints are ADV and ADTV, not market cap, and the
  names being excluded are NOT small: their median market cap is higher
  than the ones that pass. A 500k-SHARE ADV floor screens out
  high-priced large caps, because a $600 stock clearing $50M a day
  trades under 100k shares. That is a property of the filter, not of the
  companies.

Run: python3 lambda_strategy_validation/validation.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

import analysis as A  # noqa: E402
from doji import G_CONT, G_DOJI, G_REV, classify  # noqa: E402
from lossanalysis import running_vwap  # noqa: E402
from stops import (  # noqa: E402
    COST_BPS, ENTRY_MIN, EXIT_MIN, MAX_MIN, N_BOOT, OUT_DIR, SIGNAL_MIN,
    VOL_MULT, load_paths, log, mat,
)
from stopsummary import scan_close, scan_intrabar  # noqa: E402
from volume_test import volume_features  # noqa: E402
from winrate_report import wilson  # noqa: E402

BASE = Path("/home/user/lambda_data")
FEED = BASE / "validation_feed.json"
REPORT = Path(__file__).resolve().parent / "VALIDATION_REPORT.md"
EXTRACT_CSV = BASE / "postearnings_extract.csv"
EXTRACT_XLSX = BASE / "postearnings_extract.xlsx"

W5, W15, W60 = 9, 19, 64
SMALL = 150


def stat_pack(r_bps: np.ndarray, r_atr: np.ndarray, cost_atr: np.ndarray,
              dates: pd.Series, label: dict) -> dict:
    n = len(r_bps)
    k = int((r_bps > 0).sum())
    lo, hi = wilson(k, n) if n else (np.nan, np.nan)
    # Both series must share an index: clustered_bootstrap aligns them in a
    # DataFrame and then dropna()s, so a values-vs-dates index mismatch
    # silently empties the frame and returns NaN.
    vals = pd.Series(r_bps / 1e4 - COST_BPS / 1e4).reset_index(drop=True)
    clus = pd.Series(np.asarray(dates)).reset_index(drop=True)
    net_b = A.clustered_bootstrap(vals, clus, n_boot=N_BOOT)
    m1 = r_atr < -1.0
    rec = dict(label)
    rec.update({
        "n": n, "win_rate": k / n if n else np.nan,
        "wilson_lo": lo, "wilson_hi": hi,
        "net_bps": net_b["stat"] * 1e4, "net_p": net_b["p"],
        "net_atr": float((r_atr - cost_atr).mean()) if n else np.nan,
        "mean_bps": float(r_bps.mean()) if n else np.nan,
        "median_bps": float(np.median(r_bps)) if n else np.nan,
        "pct_loss_1atr": float(m1.mean()) if n else np.nan,
        "avg_large_loss_bps": float(r_bps[m1].mean()) if m1.any() else np.nan,
        "avg_large_loss_atr": float(r_atr[m1].mean()) if m1.any() else np.nan,
        "small": "YES" if n < SMALL else "",
    })
    return rec


def dist_pack(r_bps: np.ndarray, r_atr: np.ndarray, label: dict) -> dict:
    q = np.quantile(r_bps, [0.10, 0.25, 0.50, 0.75, 0.90])
    rec = dict(label)
    rec.update({
        "n": len(r_bps),
        "mean_bps": float(r_bps.mean()), "median_bps": float(q[2]),
        "p10": float(q[0]), "p25": float(q[1]), "p75": float(q[3]),
        "p90": float(q[4]),
        "skew": float(stats.skew(r_bps, bias=False)),
        "kurtosis": float(stats.kurtosis(r_bps, fisher=True, bias=False)),
        "skew_w": float(stats.skew(np.clip(r_bps, *np.quantile(
            r_bps, [0.01, 0.99])), bias=False)),
        "kurtosis_w": float(stats.kurtosis(np.clip(r_bps, *np.quantile(
            r_bps, [0.01, 0.99])), fisher=True, bias=False)),
        "pct_lt_05atr": float((r_atr < -0.5).mean()),
        "pct_lt_1atr": float((r_atr < -1.0).mean()),
        "pct_gt_1atr": float((r_atr > 1.0).mean()),
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

    panel = pd.read_parquet(
        BASE / "panel.parquet",
        columns=["ticker", "date", "atr14", "sector", "stage_prev",
                 "close", "market_cap_prev", "universe_ok_prev"])
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel.sort_values(["ticker", "date"]).reset_index(drop=True)
    panel["atr14_prev"] = panel.groupby("ticker")["atr14"].shift(1)
    keep = ["ticker", "date", "atr14_prev", "sector", "stage_prev", "close",
            "market_cap_prev", "universe_ok_prev"]
    ev = ev.drop(columns=[c for c in keep
                          if c in ev.columns and c not in ("ticker", "date")],
                 errors="ignore")
    ev = ev.merge(panel[keep], on=["ticker", "date"], how="left")
    ev = ev.merge(vol, on=["ticker", "date"], how="left", suffixes=("", "_v"))
    ev = classify(ev)

    paths = load_paths(ev)
    df = ev.merge(paths, on=["ticker", "date"], how="inner",
                  suffixes=("", "_p"))
    n_merge = len(df)

    early = [f"open{i}" for i in range(0, ENTRY_MIN + 1)]
    df = df[df[early].notna().any(axis=1)].copy()
    df["entry_px"] = df[f"open{ENTRY_MIN}"].fillna(df[f"close{SIGNAL_MIN}"])
    df = df[df["entry_px"].notna() & df["atr14_prev"].notna()
            & (df["atr14_prev"] > 0)].copy()
    df = df.reset_index(drop=True)

    ccols = [f"close{m}" for m in range(MAX_MIN)]
    cm = df[ccols].copy()
    cm.insert(0, "seed", df["session_open"])
    df[ccols] = cm.ffill(axis=1).drop(columns="seed")
    df = df[df[f"close{EXIT_MIN}"].notna()].reset_index(drop=True)
    log(f"full extract universe: {len(df):,} (from {n_merge:,} merged)")

    sign = np.where(df["gap_up"], 1.0, -1.0)
    entry = df["entry_px"].to_numpy(float)
    atr = df["atr14_prev"].to_numpy(float)
    closes = df[ccols].to_numpy(float)
    opens, highs, lows = mat(df, "open"), mat(df, "high"), mat(df, "low")
    vols = mat(df, "volume")
    adverse = np.where(sign[:, None] > 0, lows, highs)
    cost_atr = (COST_BPS / 1e4) * entry / atr

    def ret(k):
        p = closes[:, k]
        return sign * (p / entry - 1.0) * 1e4, sign * (p - entry) / atr

    r5b, r5a = ret(W5)
    r15b, r15a = ret(W15)
    r60b, r60a = ret(W60)
    day_b = sign * (df["close"].to_numpy(float) / entry - 1.0) * 1e4

    sadv = sign[:, None] * (adverse - entry[:, None])
    mae_atr = np.nanmin(sadv[:, ENTRY_MIN:EXIT_MIN + 1], axis=1) / atr
    prev_close = (df["open"] / (1.0 + df["gap"])).to_numpy(float)
    gap_lvl = sign * (prev_close - entry)
    gap_touched = np.nanmin(sadv[:, ENTRY_MIN:EXIT_MIN + 1],
                            axis=1) <= gap_lvl

    df["_hv"] = (df["vol_ratio"] > VOL_MULT) & ~df["vol_straddle"].fillna(
        False)
    body = (df["c1_close"] - df["c1_open"]).abs() / (
        df["c1_high"] - df["c1_low"]).replace(0, np.nan)

    # ---------- Part 5: the extract ----------
    ex = pd.DataFrame({
        "ticker": df["ticker"], "date": df["date"].dt.date,
        "sector": df["sector"], "market_cap_prev_usd": df["market_cap_prev"],
        "passes_universe_screen": np.where(
            df["universe_ok_prev"].fillna(False), "Yes", "No"),
        "high_volume_flag": np.where(df["_hv"], "Yes", "No"),
        "candle_class": df["klass"].map({G_CONT: "Continuation",
                                         G_REV: "Reversal",
                                         G_DOJI: "Indecisive"}),
        "gap_direction": np.where(df["gap_up"], "Up", "Down"),
        "gap_pct": df["gap"] * 100,
        "gap_atr": (df["open"].to_numpy(float) - prev_close) / atr,
        "vol_ratio_5min": df["vol_ratio"],
        "body_over_range": body,
        "stage_prev": df["stage_prev"],
        "entry_px_0935": entry,
        "ret_5min_bps": r5b, "ret_5min_atr": r5a,
        "ret_15min_bps": r15b, "ret_15min_atr": r15a,
        "ret_1hour_bps": r60b, "ret_1hour_atr": r60a,
        "ret_t1_close_bps": day_b,
        "gap_level_touched_1h": np.where(gap_touched, "Yes", "No"),
        "mae_1h_atr": mae_atr,
        "atr14_prev": atr,
        "cost_in_atr": cost_atr,
    })
    ex = ex.sort_values(["date", "ticker"]).reset_index(drop=True)
    ex.to_csv(EXTRACT_CSV, index=False)
    with pd.ExcelWriter(EXTRACT_XLSX, engine="openpyxl") as xw:
        ex.to_excel(xw, sheet_name="events", index=False)
    log(f"extract written: {len(ex):,} rows")

    R: dict[str, pd.DataFrame] = {}
    R["extract_summary"] = pd.DataFrame([{
        "n_events": len(ex),
        "n_merged": n_merge,
        "n_high_vol": int((ex["high_volume_flag"] == "Yes").sum()),
        "n_continuation": int((ex["candle_class"] == "Continuation").sum()),
        "n_hv_cont": int(((ex["high_volume_flag"] == "Yes")
                          & (ex["candle_class"] == "Continuation")).sum()),
        "n_pass_screen": int((ex["passes_universe_screen"] == "Yes").sum()),
        "start": str(ex["date"].min()), "end": str(ex["date"].max()),
        "n_tickers": int(ex["ticker"].nunique()),
    }])

    # ---------- core cohort ----------
    core = df["_hv"].to_numpy() & (df["klass"] == G_CONT).to_numpy()
    ci = np.where(core)[0]
    dates = df["date"]
    log(f"core HV+Continuation cohort: {core.sum():,}")

    # ---------- Section 0: does the screen matter? ----------
    scr = df["universe_ok_prev"].fillna(False).to_numpy()
    rows = []
    for nm, m in (("All (as published)", core),
                  ("Passes screen", core & scr),
                  ("Fails screen", core & ~scr)):
        i = np.where(m)[0]
        rows.append(stat_pack(r60b[i], r60a[i], cost_atr[i],
                              dates.iloc[i], {"cohort": nm}))
        rows[-1]["median_mcap_b"] = float(
            df.loc[i, "market_cap_prev"].median() / 1e9)
        rows[-1]["median_price"] = float(np.median(entry[i]))
    R["screen"] = pd.DataFrame(rows)

    # ---------- Part 1: segments ----------
    seg_rows = []

    def add_seg(dim, labels, masks):
        for lab, m in zip(labels, masks):
            i = np.where(m & core)[0]
            if len(i) < 30:
                continue
            seg_rows.append(stat_pack(r60b[i], r60a[i], cost_atr[i],
                                      dates.iloc[i],
                                      {"dimension": dim, "segment": lab}))

    sec = df["sector"].fillna("Unknown").to_numpy()
    add_seg("Sector", sorted(set(sec)), [sec == s for s in sorted(set(sec))])

    st = df["stage_prev"].to_numpy()
    add_seg("Stage (prior session)",
            ["Stage 2 — advancing", "Stage 3 — topping", "Stage 4 — declining"],
            [st == 2, st == 3, st == 4])

    yr = df["date"].dt.year.to_numpy()
    add_seg("Year", [str(y) for y in sorted(set(yr))],
            [yr == y for y in sorted(set(yr))])

    mo = df["date"].dt.month.to_numpy()
    mnames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
              "Oct", "Nov", "Dec"]
    add_seg("Month", mnames, [mo == i for i in range(1, 13)])

    dow = df["date"].dt.dayofweek.to_numpy()
    add_seg("Day of week", ["Mon", "Tue", "Wed", "Thu", "Fri"],
            [dow == i for i in range(5)])

    ga = ((df["open"].to_numpy(float) - prev_close) / atr)
    add_seg("Gap / ATR",
            ["< 0.5", "0.5 – 1.0", "1.0 – 2.0", "> 2.0"],
            [np.abs(ga) < 0.5, (np.abs(ga) >= 0.5) & (np.abs(ga) < 1.0),
             (np.abs(ga) >= 1.0) & (np.abs(ga) < 2.0), np.abs(ga) >= 2.0])

    vr = df["vol_ratio"].to_numpy(float)
    add_seg("Volume ratio",
            ["1.5 – 2.5×", "2.5 – 4×", "4 – 7×", "> 7×"],
            [(vr >= 1.5) & (vr < 2.5), (vr >= 2.5) & (vr < 4),
             (vr >= 4) & (vr < 7), vr >= 7])

    bd = body.to_numpy(float)
    add_seg("Candle body / range",
            ["0.10 – 0.30 (weak)", "0.30 – 0.55", "0.55 – 0.80",
             "> 0.80 (strong)"],
            [(bd > 0.10) & (bd <= 0.30), (bd > 0.30) & (bd <= 0.55),
             (bd > 0.55) & (bd <= 0.80), bd > 0.80])
    R["segments"] = pd.DataFrame(seg_rows)

    # ---------- Part 2: distributions ----------
    close_exit = sign * (closes[:, EXIT_MIN] - entry)
    rules = {"Core — no stop": (close_exit, np.zeros(len(df), bool),
                                np.full(len(df), np.nan))}
    rules["ATR −1.0"] = scan_intrabar(sign, entry, opens, adverse,
                                      close_exit, -1.0 * atr)
    or_px = np.where(sign > 0, df["c1_low"].to_numpy(float),
                     df["c1_high"].to_numpy(float))
    rules["Opening Range"] = scan_close(
        sign, entry, closes, close_exit,
        np.repeat(or_px[:, None], MAX_MIN, axis=1))
    rules["Gap Level"] = scan_close(
        sign, entry, closes, close_exit,
        np.repeat(prev_close[:, None], MAX_MIN, axis=1))

    drows, stop_diag = [], []
    for nm, (pnl, stopped, lvl) in rules.items():
        i = ci
        rb = (pnl[i] / entry[i]) * 1e4
        ra = pnl[i] / atr[i]
        drows.append(dist_pack(rb, ra, {"rule": nm}))
        if stopped[i].any():
            s = stopped[i]
            held = close_exit[i] / entry[i]
            realised = pnl[i] / entry[i]
            stop_diag.append({
                "rule": nm, "n_stopped": int(s.sum()),
                "pct_stopped": float(s.mean()),
                "pct_recover": float((held[s] > 0).mean()),
                "pct_beat_stop": float((held[s] > realised[s]).mean()),
                "mae_of_stopped": float(np.nanmedian(mae_atr[i][s])),
                "mae_of_kept": float(np.nanmedian(mae_atr[i][~s])),
                "forgone_bps": float((held[s] - realised[s]).mean() * 1e4),
            })
    R["dist"] = pd.DataFrame(drows)
    R["stop_diag"] = pd.DataFrame(stop_diag)

    # ---------- Part 3: what the stops cut, by MAE depth ----------
    _, st10, _ = rules["ATR −1.0"]
    rows = []
    buckets = [("recovered to profit", None)]
    held60 = close_exit[ci] / entry[ci] * 1e4
    s10 = st10[ci]
    for lab, m in (("Stopped by ATR −1.0", s10),
                   ("Not stopped", ~s10)):
        rows.append({
            "group": lab, "n": int(m.sum()),
            "median_mae_atr": float(np.nanmedian(mae_atr[ci][m])),
            "median_gap_atr": float(np.nanmedian(np.abs(ga[ci][m]))),
            "median_vol_ratio": float(np.nanmedian(vr[ci][m])),
            "pct_gap_touched": float(gap_touched[ci][m].mean()),
            "held_outcome_bps": float(held60[m].mean()),
            "pct_held_profitable": float((held60[m] > 0).mean()),
        })
    R["cut_profile"] = pd.DataFrame(rows)

    # ---------- Part 4: AVWAP buffers ----------
    vwap0 = running_vwap(highs, lows, closes, vols)
    rows = []
    for buf in (0.0, 0.05, 0.10, 0.15):
        lvl_mat = vwap0 - sign[:, None] * (buf * atr)[:, None]
        pnl, stopped, at_lvl = scan_close(sign, entry, closes, close_exit,
                                          lvl_mat)
        i = ci
        rb = pnl[i] / entry[i] * 1e4
        ra = pnl[i] / atr[i]
        s = stopped[i]
        held = close_exit[i] / entry[i]
        over = (at_lvl[i][s] - pnl[i][s]) / entry[i][s] * 1e4
        rows.append({
            "buffer_atr": buf,
            "net_bps": float(rb.mean() - COST_BPS),
            "pct_stopped": float(s.mean()),
            "pct_loss_1atr": float((ra < -1.0).mean()),
            "avg_over_bps": float(over.mean()) if s.any() else np.nan,
            "pct_recover": float((held[s] > 0).mean()) if s.any() else np.nan,
            "win_rate": float((rb > 0).mean()),
        })
        log(f"AVWAP buffer {buf:.2f}: {s.mean()*100:.1f}% stopped, "
            f"net {rows[-1]['net_bps']:+.1f}")
    R["avwap"] = pd.DataFrame(rows)

    meta = {"cost_bps": COST_BPS, "vol_mult": VOL_MULT, "small": SMALL,
            "n_extract": int(len(ex)), "n_core": int(core.sum()),
            "extract_csv": str(EXTRACT_CSV.name),
            "extract_xlsx": str(EXTRACT_XLSX.name)}
    for k, v in R.items():
        v.to_csv(OUT_DIR / f"val_{k}.csv", index=False)
    FEED.write_text(json.dumps(
        {"meta": meta, **{k: json.loads(v.round(6).to_json(orient="records"))
                          for k, v in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables")

    from validation_text import build  # noqa: E402
    REPORT.write_text(build(R, meta))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
