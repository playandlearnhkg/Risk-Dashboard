"""
tradeable_report.py — Continuation win rates under STRICT no-look-ahead
rules, including the ICT midday window.

THE FOUR RULES, and exactly how each is enforced in code:

  1. The pattern is fully known at 09:45.
     Both pattern systems read only the three 5-minute candles covering
     09:30-09:45. Nothing after 09:45 touches the classification.

  2. Every continuation measurement starts at 09:45, never at the open.
     Entry price = m14, the close of the 09:44 bar, which is the price at
     09:45:00 and is identical to c3_close (the close of the third
     5-minute candle). So the entry is the close of the very bar that
     completes the signal — the standard backtest convention — and the
     09:30-09:45 window is never inside a measured return.

  3. SPY and sector direction use Open -> 09:45 only.
     Computed as benchmark m14 close / benchmark session open - 1. The
     16:00 close, which contaminated the earlier version of this filter,
     is never referenced.

  4. Stage comes from the prior session (`stage_prev`), unchanged.

DEFINITIONS
  Gap Up / Gap Down : Open_T+1 vs Prior Close
  Continuation      : from 09:45 to the endpoint, the stock moves in the
                      same direction as the original gap
  SPY Agree         : SPY's Open->09:45 move has the same sign as the
                      stock's gap;  Disagree = opposite sign
  Sector Agree      : same rule against the stock's sector ETF

WINDOWS (all start at 09:45)
  10:00 = m29, 10:30 = m59, 11:00 = m89, 12:00 = m149, 13:00 = m209,
  Close = session close. Sessions whose window move is exactly zero are
  excluded from that window and counted.

Run: python3 lambda_strategy_validation/tradeable_report.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import analysis as A  # noqa: E402
from winrate_report import simple_first_candle, wilson  # noqa: E402

BASE = Path("/home/user/lambda_data")
INTRADAY_DIR = BASE / "intraday210"
BENCH_PATH = BASE / "bench_intraday.parquet"
EVENTS = BASE / "events.parquet"
OUT_DIR = BASE / "tables"
FEED = BASE / "tradeable_feed.json"
REPORT = Path(__file__).resolve().parent / "TRADEABLE_REPORT.md"

MAX_MIN = 210
ENTRY_MIN = 14              # close of the 09:44 bar == price at 09:45:00
SMALL_SAMPLE = 150          # per the brief
MIN_COMBO_N = 200           # per the brief
N_BOOT = 1000

WINDOWS = {
    "09:45 -> 10:00": 29,
    "09:45 -> 10:30": 59,
    "09:45 -> 11:00": 89,
    "09:45 -> 12:00": 149,
    "09:45 -> 13:00": 209,     # ICT midday
    "09:45 -> Close": None,
}

PAT4_ORDER = ["Strong Continuation+", "Moderate Continuation+",
              "Indecision0", "Early Reversal-"]
PAT2_ORDER = ["Continuation (1st candle with gap)",
              "Reversal (1st candle against gap)", "Doji (1st candle)"]


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def load_wide(ev: pd.DataFrame) -> pd.DataFrame:
    want = set(zip(ev["ticker"], ev["date"]))
    frames = []
    files = sorted(INTRADAY_DIR.glob("*.parquet"))
    for i, f in enumerate(files, 1):
        try:
            d = pd.read_parquet(f)
        except Exception:  # noqa: BLE001
            continue
        if d.empty:
            continue
        d["date"] = pd.to_datetime(d["date"])
        d = d[[(t, dt) in want for t, dt in zip(d["ticker"], d["date"])]]
        if not d.empty:
            frames.append(d)
        if i % 250 == 0:
            log(f"  {i}/{len(files)} files")
    raw = pd.concat(frames, ignore_index=True)
    wide = raw.pivot_table(index=["ticker", "date"], columns="minute",
                           values="close", aggfunc="last")
    wide = wide.reindex(columns=range(MAX_MIN))
    sess = raw.groupby(["ticker", "date"])[["session_open", "session_close"]].first()
    # A minute with no print means no trade, so the prevailing price is the
    # last one printed. Forward-filling keeps the sample identical across
    # every window instead of letting it change with the endpoint.
    wide.insert(0, "seed", sess["session_open"])
    wide = wide.ffill(axis=1).drop(columns="seed")
    wide.columns = [f"m{int(c)}" for c in wide.columns]
    return wide.join(sess).reset_index()


def load_bench_0945() -> pd.DataFrame:
    """Benchmark Open -> 09:45 return per (date, bench). No later data used."""
    b = pd.read_parquet(BENCH_PATH)
    b["date"] = pd.to_datetime(b["date"])
    at = b[b["minute"] <= ENTRY_MIN].sort_values("minute")
    at = at.groupby(["bench", "date"]).agg(px=("close", "last"),
                                           open_=("bench_open", "first")).reset_index()
    at["ret_0945"] = at["px"] / at["open_"] - 1.0
    return at[["bench", "date", "ret_0945"]]


def rate_row(g: pd.DataFrame, labels: dict, col: str) -> dict:
    n = len(g)
    k = int(g[col].sum())
    lo, hi = wilson(k, n)
    rec = dict(labels)
    rec.update({"n_total": n, "n_continuation": k, "n_reversal": n - k,
                "win_rate": (k / n) if n else np.nan,
                "wilson_lo": lo, "wilson_hi": hi,
                "small_sample": "YES" if n < SMALL_SAMPLE else ""})
    if n >= 30:
        r = A.clustered_rate_vs_half(g[col].astype(bool), g["date"], n_boot=N_BOOT)
        rec["p_clustered"] = r["p"]
    else:
        rec["p_clustered"] = np.nan
    return rec


def split(df: pd.DataFrame, by: str | None, order: list | None,
          gap_rows: bool = True) -> pd.DataFrame:
    rows = []
    groups = ([("All events", df)] if by is None
              else [(v, df[df[by] == v]) for v in
                    (order or sorted(df[by].dropna().unique()))])
    for name, g in groups:
        splits = ([("Gap Up", g[g["gap_up"]]), ("Gap Down", g[~g["gap_up"]]),
                   ("Both", g)] if gap_rows else [("Both", g)])
        for gl, sub in splits:
            if len(sub) == 0:
                continue
            rows.append(rate_row(sub, {"subgroup": name, "gap": gl}, "cont"))
    cols = ["subgroup", "gap", "n_total", "n_continuation", "n_reversal",
            "win_rate", "wilson_lo", "wilson_hi", "p_clustered", "small_sample"]
    return pd.DataFrame(rows)[cols]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ev = pd.read_parquet(EVENTS)
    ev["date"] = pd.to_datetime(ev["date"])
    ev = ev[ev["gap"] != 0].copy()
    ev["gap_up"] = ev["gap"] > 0
    ev["pattern_simple"] = ev.apply(simple_first_candle, axis=1)
    ev["stage_group"] = np.where(ev["stage_prev"] == 2.0, "Stage 2",
                                 np.where(ev["stage_prev"].isin([3.0, 4.0]),
                                          "Stage 3+4", None))
    log(f"events with a non-zero gap: {len(ev):,}")

    wide = load_wide(ev)
    df = ev.merge(wide, on=["ticker", "date"], how="inner", suffixes=("", "_i"))
    df = df[df["session_open"].notna() & df["session_close"].notna()].copy()
    log(f"joined with intraday: {len(df):,}")

    # --- rule 3: benchmark direction from Open -> 09:45 only -------------
    bench = load_bench_0945()
    spy = bench[bench["bench"] == "SPY"][["date", "ret_0945"]].rename(
        columns={"ret_0945": "spy_0945"})
    df = df.merge(spy, on="date", how="left")
    sec = bench.rename(columns={"bench": "sector_etf", "ret_0945": "sector_0945"})
    df = df.merge(sec, on=["sector_etf", "date"], how="left")

    df["spy_agree"] = np.where(
        df["spy_0945"].isna() | (df["spy_0945"] == 0), None,
        np.where(np.sign(df["spy_0945"]) == np.sign(df["gap"]),
                 "SPY Agree", "SPY Disagree"))
    df["sector_agree"] = np.where(
        df["sector_0945"].isna() | (df["sector_0945"] == 0), None,
        np.where(np.sign(df["sector_0945"]) == np.sign(df["gap"]),
                 "Sector Agree", "Sector Disagree"))

    entry = df[f"m{ENTRY_MIN}"]
    R: dict[str, pd.DataFrame] = {}
    excluded = {}
    per_window = []

    for wname, wmin in WINDOWS.items():
        end = df["session_close"] if wmin is None else df.get(f"m{wmin}")
        if end is None:
            log(f"  {wname}: column missing, skipped")
            continue
        d = df.copy()
        d["move"] = end - entry
        n_flat = int((d["move"] == 0).sum())
        d = d[d["move"] != 0]
        d["up"] = d["move"] > 0
        d["cont"] = d["gap_up"] == d["up"]
        d["window"] = wname
        excluded[wname] = {"n_flat_excluded": n_flat, "n_used": int(len(d))}
        per_window.append(d)

        R[f"t1_{wname}"] = split(d, None, None)
        R[f"t2_{wname}"] = split(d[d["pattern"].notna()], "pattern", PAT4_ORDER)
        R[f"t3_{wname}"] = split(d[d["pattern_simple"].notna()],
                                 "pattern_simple", PAT2_ORDER)
        R[f"t4_{wname}"] = split(d[d["spy_agree"].notna()], "spy_agree",
                                 ["SPY Agree", "SPY Disagree"])
        R[f"t5_{wname}"] = split(d[d["sector_agree"].notna()], "sector_agree",
                                 ["Sector Agree", "Sector Disagree"])
        R[f"t6_{wname}"] = split(d[d["stage_group"].notna()], "stage_group",
                                 ["Stage 2", "Stage 3+4"])

    allw = pd.concat(per_window, ignore_index=True)

    # --- Table 7: fully tradeable combinations --------------------------
    combo_rows = []
    c = allw[allw["pattern_simple"].notna() & allw["stage_group"].notna()
             & allw["spy_agree"].notna()].copy()
    c["combo"] = (c["pattern_simple"].str.split(" (", regex=False).str[0] + " | "
                  + c["stage_group"] + " | " + c["spy_agree"])
    for wname in WINDOWS:
        sub = c[c["window"] == wname]
        if sub.empty:
            continue
        t = split(sub, "combo", None, gap_rows=False)
        t["window"] = wname
        combo_rows.append(t)
    combos = pd.concat(combo_rows, ignore_index=True)
    R["t7_combos"] = combos[combos["n_total"] >= MIN_COMBO_N].sort_values(
        "win_rate", ascending=False).reset_index(drop=True)

    # 4-pattern variant of the same combination table
    c4 = allw[allw["pattern"].notna() & allw["stage_group"].notna()
              & allw["spy_agree"].notna()].copy()
    c4["combo"] = (c4["pattern"] + " | " + c4["stage_group"] + " | "
                   + c4["spy_agree"])
    rows4 = []
    for wname in WINDOWS:
        sub = c4[c4["window"] == wname]
        if sub.empty:
            continue
        t = split(sub, "combo", None, gap_rows=False)
        t["window"] = wname
        rows4.append(t)
    cb4 = pd.concat(rows4, ignore_index=True)
    R["t7_combos_pattern4"] = cb4[cb4["n_total"] >= MIN_COMBO_N].sort_values(
        "win_rate", ascending=False).reset_index(drop=True)

    # --- window comparison, for the ICT question ------------------------
    R["window_summary"] = pd.concat(
        [R[f"t1_{w}"].assign(window=w) for w in WINDOWS if f"t1_{w}" in R],
        ignore_index=True)

    meta = {"n_events": int(len(df)), "entry_minute": ENTRY_MIN,
            "small_sample_threshold": SMALL_SAMPLE,
            "min_combo_n": MIN_COMBO_N, "excluded_flat": excluded,
            "n_spy_known": int(df["spy_agree"].notna().sum()),
            "n_sector_known": int(df["sector_agree"].notna().sum())}

    for k, v in R.items():
        v.to_csv(OUT_DIR / f"trade_{k.replace(' ', '').replace('->','to').replace(':','')}.csv",
                 index=False)
    (BASE / "tradeable_meta.json").write_text(json.dumps(meta, indent=1))
    FEED.write_text(json.dumps(
        {"meta": meta, "windows": list(WINDOWS),
         **{k: json.loads(v.round(6).to_json(orient="records"))
            for k, v in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables")

    from tradeable_text import build  # noqa: E402
    REPORT.write_text(build(R, meta, list(WINDOWS)))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
