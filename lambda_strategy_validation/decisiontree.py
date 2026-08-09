"""
decisiontree.py — every decision node in the programme, computed on ONE
cohort so the tree reconciles.

WHY THIS EXISTS
  The reports each answer one question and several use slightly different
  conventions (dropping exactly-zero returns, applying or not applying
  the universe screen). Quoting their headline numbers side by side in a
  tree would produce children that do not sum to their parent. Every node
  below is recomputed from a single frame with a single convention:

      universe : post-earnings T+1, non-zero gap, a real print by 09:35,
                 a positive prior-session ATR(14), a mark at 10:35
      entry    : open of the 09:35 bar
      exit     : 10:35 unless the node says otherwise
      sign     : the gap direction unless the node says otherwise
      zeros    : KEPT, so counts add up
      cost     : 6.6 bps round trip on every node

  Consequence: a few figures differ in the first decimal from the report
  that introduced them. That is the price of a tree that adds up, and the
  differences are disclosed rather than smoothed.

Emits decision_tree.json for the research artifact.

Run: python3 lambda_strategy_validation/decisiontree.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import analysis as A  # noqa: E402
from doji import G_CONT, G_DOJI, G_REV, classify  # noqa: E402
from lossanalysis import running_vwap  # noqa: E402
from stops import (  # noqa: E402
    COST_BPS, ENTRY_MIN, EXIT_MIN, MAX_MIN, N_BOOT, OUT_DIR, SIGNAL_MIN,
    VOL_MULT, load_paths, log, mat,
)
from stopsummary import scan_close, scan_intrabar  # noqa: E402
from volume_test import volume_features  # noqa: E402

BASE = Path("/home/user/lambda_data")
OUT_JSON = BASE / "decision_tree.json"

W5, W15, W60 = 9, 19, 64


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    vol = volume_features()
    ev = pd.read_parquet(BASE / "events.parquet")
    ev["date"] = pd.to_datetime(ev["date"])
    ev = ev[ev["gap"] != 0].copy()
    ev["gap_up"] = ev["gap"] > 0

    panel = pd.read_parquet(
        BASE / "panel.parquet",
        columns=["ticker", "date", "atr14", "close", "market_cap_prev",
                 "price_ok_prev", "mcap_ok_prev", "adtv_63_prev"])
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel.sort_values(["ticker", "date"]).reset_index(drop=True)
    panel["atr14_prev"] = panel.groupby("ticker")["atr14"].shift(1)
    panel["yr"] = panel["date"].dt.year
    pre = panel[panel["yr"] <= 2021]
    target = float((pre["adtv_63_prev"] >= 50e6).mean())
    thr = panel.groupby("yr")["adtv_63_prev"].transform(
        lambda s: s.quantile(max(0.0, 1.0 - target)))
    panel["screen_v2"] = (panel["price_ok_prev"].fillna(False)
                          & panel["mcap_ok_prev"].fillna(False)
                          & (panel["adtv_63_prev"] >= thr).fillna(False))

    keep = ["ticker", "date", "atr14_prev", "close", "market_cap_prev",
            "screen_v2"]
    ev = ev.drop(columns=[c for c in keep if c in ev.columns
                          and c not in ("ticker", "date")], errors="ignore")
    ev = ev.merge(panel[keep], on=["ticker", "date"], how="left")
    ev = ev.merge(vol, on=["ticker", "date"], how="left", suffixes=("", "_v"))
    ev = classify(ev)

    paths = load_paths(ev)
    df = ev.merge(paths, on=["ticker", "date"], how="inner",
                  suffixes=("", "_p"))
    early = [f"open{i}" for i in range(0, ENTRY_MIN + 1)]
    df = df[df[early].notna().any(axis=1)].copy()
    df["entry_px"] = df[f"open{ENTRY_MIN}"].fillna(df[f"close{SIGNAL_MIN}"])
    df = df[df["entry_px"].notna()
            & df["atr14_prev"].notna() & (df["atr14_prev"] > 0)].copy()
    df = df.reset_index(drop=True)
    ccols = [f"close{m}" for m in range(MAX_MIN)]
    cm = df[ccols].copy()
    cm.insert(0, "seed", df["session_open"])
    df[ccols] = cm.ffill(axis=1).drop(columns="seed")
    df = df[df[f"close{EXIT_MIN}"].notna()].reset_index(drop=True)
    log(f"tree universe: {len(df):,}")

    sign = np.where(df["gap_up"], 1.0, -1.0)
    entry = df["entry_px"].to_numpy(float)
    atr = df["atr14_prev"].to_numpy(float)
    closes = df[ccols].to_numpy(float)
    opens, highs, lows = mat(df, "open"), mat(df, "high"), mat(df, "low")
    vols = mat(df, "volume")
    adverse = np.where(sign[:, None] > 0, lows, highs)
    close_exit = sign * (closes[:, EXIT_MIN] - entry)
    dates = df["date"]
    cost_atr = (COST_BPS / 1e4) * entry / atr

    hv = (df["vol_ratio"] > VOL_MULT) & ~df["vol_straddle"].fillna(False)
    hv = hv.to_numpy()
    klass = df["klass"].to_numpy()
    prev_close = (df["open"] / (1.0 + df["gap"])).to_numpy(float)
    gap_atr = np.abs(df["open"].to_numpy(float) - prev_close) / atr
    vr = df["vol_ratio"].to_numpy(float)
    scr = df["screen_v2"].fillna(False).to_numpy()
    mcap = df["market_cap_prev"].to_numpy(float)
    body = ((df["c1_close"] - df["c1_open"]).abs()
            / (df["c1_high"] - df["c1_low"]).replace(0, np.nan)).to_numpy()
    with_gap = df["with_gap"].to_numpy()

    nodes: list[dict] = []

    def add(key, label, mask, pnl_price, note="", w=None, parent=None):
        m = np.asarray(mask, bool)
        if m.sum() < 30:
            return
        p = np.asarray(pnl_price, float)[m]
        e, a_ = entry[m], atr[m]
        r_bps = p / e * 1e4
        r_atr = p / a_
        ww = np.ones(m.sum()) if w is None else np.asarray(w, float)[m]
        wm = ww.mean()
        net_series = ww * (r_bps - COST_BPS) / wm
        b = A.clustered_bootstrap(
            pd.Series(net_series / 1e4).reset_index(drop=True),
            pd.Series(np.asarray(dates[m])).reset_index(drop=True),
            n_boot=N_BOOT)
        nodes.append({
            "key": key, "parent": parent, "label": label, "note": note,
            "n": int(m.sum()),
            "share": float(m.sum() / len(df)),
            "net_bps": float(net_series.mean()),
            "net_p": float(b["p"]),
            "net_atr": float((ww * (r_atr - cost_atr[m]) / wm).mean()),
            "win_rate": float((r_bps > 0).mean()),
            "median_bps": float(np.median(r_bps)),
            "pct_loss_1atr": float((r_atr < -1.0).mean()),
        })

    def ret(k, s=None):
        s = sign if s is None else s
        return s * (closes[:, k] - entry)

    ALL = np.ones(len(df), bool)
    cont, rev, doji = klass == G_CONT, klass == G_REV, klass == G_DOJI

    # ---- level 0/1: what the candle says ----
    add("root", "All post-earnings T+1 gaps", ALL, ret(W60),
        "traded blindly in the gap direction")
    add("cont", "Continuation", cont, ret(W60),
        "candle closes with the gap", parent="root")
    add("rev_gap", "Reversal — trade the gap anyway", rev, ret(W60),
        "ignore the counter-gap candle", parent="root")
    add("rev_candle", "Reversal — follow the candle", rev, ret(W60, -sign),
        "trade against the gap", parent="root")
    add("doji_gap", "Indecisive (doji) — trade the gap", doji, ret(W60),
        "body/range ≤ 0.10", parent="root")

    # ---- level 2: volume ----
    add("cont_hv", "+ High Volume", cont & hv, ret(W60),
        "c1 volume > 1.5× trailing mean", parent="cont")
    add("cont_lv", "+ Normal / Low Volume", cont & ~hv, ret(W60),
        "", parent="cont")
    add("rev_hv", "Reversal + High Volume (follow candle)", rev & hv,
        ret(W60, -sign), "", parent="rev_candle")
    cs = sign * np.where(with_gap, 1.0, -1.0)
    # Volume splits every class, not just Continuation — the doji result
    # in DOJI_REPORT.md is a High Volume result, and pooling all volumes
    # here would contradict it.
    add("doji_hv", "+ High Volume", doji & hv, ret(W60), "trade the gap",
        parent="doji_gap")
    add("doji_lv", "+ Normal / Low Volume", doji & ~hv, ret(W60),
        "trade the gap", parent="doji_gap")
    add("doji_against", "Body closed against the gap", doji & hv & ~with_gap,
        ret(W60), "still trade the gap", parent="doji_hv")
    add("doji_with", "Body closed with the gap", doji & hv & with_gap,
        ret(W60), "trade the gap", parent="doji_hv")

    CORE = cont & hv

    # ---- level 3a: holding period ----
    for key, k, lab in (("h5", W5, "Exit 09:40 (5 min)"),
                        ("h15", W15, "Exit 09:50 (15 min)"),
                        ("h60", W60, "Exit 10:35 (1 hour)")):
        add(f"core_{key}", lab, CORE, ret(k), "", parent="cont_hv")
    # The path matrix stops at minute 64, so the 2-hour node cannot be
    # computed on this frame; LONGHOLD_REPORT.md covers it on its own
    # cohort and importing that figure here would break the reconciliation.
    add("core_close", "Exit at the close",
        CORE, sign * (df["close"].to_numpy(float) - entry), "",
        parent="cont_hv")

    # ---- level 3b: stops (all exit 10:35 if not stopped) ----
    p10, _, _ = scan_intrabar(sign, entry, opens, adverse, close_exit,
                              -1.0 * atr)
    p05, _, _ = scan_intrabar(sign, entry, opens, adverse, close_exit,
                              -0.5 * atr)
    or_px = np.where(sign > 0, df["c1_low"].to_numpy(float),
                     df["c1_high"].to_numpy(float))
    pOR, _, _ = scan_close(sign, entry, closes, close_exit,
                           np.repeat(or_px[:, None], MAX_MIN, axis=1))
    pGAP, _, _ = scan_close(sign, entry, closes, close_exit,
                            np.repeat(prev_close[:, None], MAX_MIN, axis=1))
    vwap0 = running_vwap(highs, lows, closes, vols)
    pVW, _, _ = scan_close(sign, entry, closes, close_exit, vwap0)

    add("stop_none", "No stop", CORE, close_exit, "", parent="core_h60")
    add("stop_atr10", "ATR −1.0 stop", CORE, p10, "intrabar",
        parent="core_h60")
    add("stop_atr05", "ATR −0.5 stop", CORE, p05, "intrabar",
        parent="core_h60")
    add("stop_or", "Opening-range stop", CORE, pOR, "5-min close",
        parent="core_h60")
    add("stop_gap", "Gap-level stop", CORE, pGAP, "5-min close",
        parent="core_h60")
    add("stop_vwap", "Anchored VWAP stop", CORE, pVW, "5-min close",
        parent="core_h60")

    # ---- level 3c: sizing ----
    high_r = (gap_atr > 1.5) | (vr > 5.0)
    low_r = (gap_atr < 0.8) & (vr < 3.0)
    w_tier = np.where(high_r, 0.5, np.where(low_r, 1.25, 1.0))
    w_vol = 1.0 / (atr / entry)
    add("size_equal", "Equal size", CORE, close_exit, "", parent="core_h60")
    add("size_tier", "Three-tier sizing", CORE, close_exit,
        "1.25 / 1.0 / 0.5", w=w_tier, parent="core_h60")
    add("size_vol", "Fixed dollar risk", CORE, close_exit,
        "weight ∝ 1/ATR%", w=w_vol, parent="core_h60")

    # ---- level 3d: conditioners ----
    add("cond_screen", "Passes the liquidity screen", CORE & scr,
        close_exit, "", parent="core_h60")
    add("cond_noscreen", "Fails the liquidity screen", CORE & ~scr,
        close_exit, "", parent="core_h60")
    add("cond_up", "Gap up (long)", CORE & df["gap_up"].to_numpy(),
        close_exit, "", parent="core_h60")
    add("cond_down", "Gap down (short)", CORE & ~df["gap_up"].to_numpy(),
        close_exit, "", parent="core_h60")
    add("cond_mcap_s", "Market cap $3–10B", CORE & (mcap >= 3e9)
        & (mcap < 10e9), close_exit, "", parent="core_h60")
    add("cond_mcap_l", "Market cap > $50B", CORE & (mcap >= 50e9),
        close_exit, "", parent="core_h60")
    add("cond_gap_lo", "Gap/ATR < 0.5", CORE & (gap_atr < 0.5), close_exit,
        "", parent="core_h60")
    add("cond_gap_hi", "Gap/ATR > 2.0", CORE & (gap_atr >= 2.0), close_exit,
        "", parent="core_h60")
    add("cond_body_hi", "Strong body (> 0.80)", CORE & (body > 0.80),
        close_exit, "", parent="core_h60")
    add("cond_body_lo", "Weak body (0.10–0.30)",
        CORE & (body > 0.10) & (body <= 0.30), close_exit, "",
        parent="core_h60")

    out = pd.DataFrame(nodes)
    out.to_csv(OUT_DIR / "decision_tree.csv", index=False)
    OUT_JSON.write_text(json.dumps(
        {"meta": {"n_universe": int(len(df)), "cost_bps": COST_BPS,
                  "start": str(df["date"].min().date()),
                  "end": str(df["date"].max().date())},
         "nodes": nodes}, separators=(",", ":")))
    log(f"wrote {len(nodes)} nodes")
    for r in nodes:
        log(f"  {r['key']:<16} n={r['n']:>6,}  net={r['net_bps']:+7.1f}  "
            f"p={r['net_p']:.3f}  {r['label']}")


if __name__ == "__main__":
    main()
