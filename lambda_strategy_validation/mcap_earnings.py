"""
mcap_earnings.py — market-cap effect on the POST-EARNINGS (T+1)
continuation edge. The mirror of the market-cap section of the general-gap
Stage 1 study, so the two are directly comparable.

Universe, signal, entry and guards are identical to entry0935.py: signal
from the 09:30-09:35 candle, entry at the OPEN of the 09:35 bar,
prior-session ATR(14) and market cap, events with no real print by 09:35
dropped. No volume join, so the sample is the full earnings continuation
cohort rather than the volume-filtered subset used in volume_test.py.

Holds: 5 min = 09:40 (m9), 15 min = 09:50 (m19), 1 hour = 10:35 (m64).

Run: python3 lambda_strategy_validation/mcap_earnings.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from volume_test import (  # noqa: E402
    COST_BPS, ENTRY_MIN, SIGNAL_MIN, SMALL, WINDOWS, load_wide, log, stat_row,
)
from winrate_report import simple_first_candle  # noqa: E402

BASE = Path("/home/user/lambda_data")
OUT_DIR = BASE / "tables"
FEED = BASE / "mcapearn_feed.json"
REPORT = Path(__file__).resolve().parent / "MCAP_EARNINGS_REPORT.md"

CONT = "Continuation (1st candle with gap)"
MCAP_BUCKETS = [("$3B - $10B", 3e9, 10e9), ("$10B - $50B", 10e9, 50e9),
                ("> $50B", 50e9, np.inf)]
ATR_BUCKETS = [("Gap/ATR < 1.0", -np.inf, 1.0), ("Gap/ATR 1.0-2.0", 1.0, 2.0),
               ("Gap/ATR > 2.0", 2.0, np.inf)]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ev = pd.read_parquet(BASE / "events.parquet")
    ev["date"] = pd.to_datetime(ev["date"])
    ev = ev[ev["gap"] != 0].copy()
    ev["gap_up"] = ev["gap"] > 0
    ev["pattern"] = ev.apply(simple_first_candle, axis=1)

    panel = pd.read_parquet(BASE / "panel.parquet",
                            columns=["ticker", "date", "atr14"])
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel.sort_values(["ticker", "date"])
    panel["atr14_prev"] = panel.groupby("ticker")["atr14"].shift(1)
    ev = ev.merge(panel[["ticker", "date", "atr14_prev"]],
                  on=["ticker", "date"], how="left")

    wide = load_wide(ev, BASE / "intraday210", 210)
    df = ev.merge(wide, on=["ticker", "date"], how="inner", suffixes=("", "_p"))
    df = df[df["session_open"].notna()]

    n0 = len(df)
    early = [f"o{i}" for i in range(0, ENTRY_MIN + 1) if f"o{i}" in df.columns]
    df = df[df[early].notna().any(axis=1)].copy()
    df["entry_px"] = df[f"o{ENTRY_MIN}"].fillna(df[f"m{SIGNAL_MIN}"])
    df = df[df["entry_px"].notna()].copy()
    n_noprint = n0 - len(df)

    n1 = len(df)
    df = df[df["market_cap_prev"].notna()].copy()
    n_nomcap = n1 - len(df)

    prev_close = df["open"] / (1.0 + df["gap"])
    df["gap_atr"] = (df["open"] - prev_close).abs() / df["atr14_prev"]

    entry = df["entry_px"]
    gs = pd.Series(np.where(df["gap_up"], 1.0, -1.0), index=df.index)
    cont = df[df["pattern"] == CONT]
    log(f"events {len(df):,} (dropped {n_noprint:,} no-print, "
        f"{n_nomcap:,} no market cap), continuation {len(cont):,}")

    R: dict[str, pd.DataFrame] = {}

    # ---------- baseline + market cap ----------
    rows = []
    for wname, wmin in WINDOWS.items():
        r = gs * (df[f"m{wmin}"] / entry - 1.0)
        s = r.reindex(cont.index).dropna()
        s = s[s != 0]
        rows.append(stat_row(s, df.loc[s.index, "date"],
                             {"window": wname, "bucket": "All Continuation"}))
        for bname, lo_v, hi_v in MCAP_BUCKETS:
            sub = cont[(cont["market_cap_prev"] >= lo_v)
                       & (cont["market_cap_prev"] < hi_v)]
            s = r.reindex(sub.index).dropna()
            s = s[s != 0]
            if len(s) < 30:
                continue
            rows.append(stat_row(s, df.loc[s.index, "date"],
                                 {"window": wname, "bucket": bname}))
    R["m1_mcap"] = pd.DataFrame(rows)

    # ---------- market cap x Gap/ATR ----------
    rows = []
    for wname, wmin in WINDOWS.items():
        r = gs * (df[f"m{wmin}"] / entry - 1.0)
        for mname, mlo, mhi in MCAP_BUCKETS:
            for aname, alo, ahi in ATR_BUCKETS:
                sub = cont[(cont["market_cap_prev"] >= mlo)
                           & (cont["market_cap_prev"] < mhi)
                           & (cont["gap_atr"] >= alo)
                           & (cont["gap_atr"] < ahi)]
                s = r.reindex(sub.index).dropna()
                s = s[s != 0]
                if len(s) < 30:
                    continue
                rows.append(stat_row(s, df.loc[s.index, "date"],
                                     {"window": wname, "mcap": mname,
                                      "bucket": aname}))
    R["m2_mcap_atr"] = pd.DataFrame(rows)

    # ---------- composition, to read the interaction honestly ----------
    # Also carry the per-bucket Roll spread, so the "flat 6.6 bps flatters
    # small caps" caveat can be quantified rather than asserted.
    comp = []
    for mname, mlo, mhi in MCAP_BUCKETS:
        sub = cont[(cont["market_cap_prev"] >= mlo)
                   & (cont["market_cap_prev"] < mhi)]
        spread = sub["roll_spread_bps_med63"].median() \
            if "roll_spread_bps_med63" in sub.columns else np.nan
        row = {"mcap": mname, "n": len(sub),
               "median_gap_atr": float(sub["gap_atr"].median()),
               "median_abs_gap_pct": float(sub["gap"].abs().median() * 100),
               "median_roll_bps": float(spread)}
        for aname, alo, ahi in ATR_BUCKETS:
            row[aname] = int(((sub["gap_atr"] >= alo)
                              & (sub["gap_atr"] < ahi)).sum())
        comp.append(row)
    R["m3_comp"] = pd.DataFrame(comp)

    meta = {"n_events": int(len(df)), "n_cont": int(len(cont)),
            "n_dropped_noprint": int(n_noprint),
            "n_dropped_nomcap": int(n_nomcap),
            "cost_bps": COST_BPS, "small": SMALL,
            "start": str(df["date"].min().date()),
            "end": str(df["date"].max().date())}
    for k, v in R.items():
        v.to_csv(OUT_DIR / f"me_{k}.csv", index=False)
    FEED.write_text(json.dumps(
        {"meta": meta, **{k: json.loads(v.round(6).to_json(orient="records"))
                          for k, v in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables")

    from mcap_earnings_text import build  # noqa: E402
    REPORT.write_text(build(R, meta))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
