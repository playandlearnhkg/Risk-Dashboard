"""
deep_tests.py — Distribution, stop-loss simulation, VIX and ATR filters,
focused on the 5- and 10-minute windows.

STRICT NO-LOOK-AHEAD, unchanged:
  - Pattern from the three candles 09:30-09:45 only.
  - Entry = m14, the close of the 09:44 bar (price at 09:45:00 == c3_close).
  - SPY direction from Open -> 09:45 only.
  - Stage from the prior session.
  - VIX = PRIOR trading day's CBOE close, known before the open.
  - ATR(14) = prior session's value, so it excludes the event day entirely.

STOP-LOSS MECHANICS. Stops are checked against the actual 1-minute path,
not the endpoint: for a long (gap up) the stop triggers if any minute LOW
from 09:46 onward breaches entry x (1 - stop); for a short (gap down) if
any minute HIGH breaches entry x (1 + stop). A stopped trade is booked at
exactly -stop bps.

That fill assumption is OPTIMISTIC and the report says so: a real stop on a
volatile post-earnings name can slip through its level, and 1-minute bars
cannot see intra-minute sequencing. So the stop results are an upper bound
on how much a stop can help.

Run: python3 lambda_strategy_validation/deep_tests.py
"""

from __future__ import annotations

import io
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

import analysis as A  # noqa: E402
from tradeable_report import ENTRY_MIN, load_bench_0945  # noqa: E402
from winrate_report import simple_first_candle, wilson  # noqa: E402

BASE = Path("/home/user/lambda_data")
INTRADAY_DIR = BASE / "intraday210"
OUT_DIR = BASE / "tables"
VIX_PATH = BASE / "vix_history.csv"
FEED = BASE / "deep_feed.json"
REPORT = Path(__file__).resolve().parent / "DEEP_TESTS_REPORT.md"

VIX_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

WINDOWS = {"09:45 -> 09:50": 19, "09:45 -> 09:55": 24, "09:45 -> 10:00": 29}
STOPS_BPS = [40, 50, 60, 80, 100]
MIN_CELL = 150
N_BOOT = 1000

VIX_BUCKETS = [("Low VIX (<15)", -np.inf, 15), ("Medium VIX (15-20)", 15, 20),
               ("High VIX (20-25)", 20, 25), ("Very High VIX (>25)", 25, np.inf)]
ATR_BUCKETS = [("Gap/ATR < 1.0", -np.inf, 1.0), ("Gap/ATR 1.0-2.0", 1.0, 2.0),
               ("Gap/ATR > 2.0", 2.0, np.inf)]


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def load_vix() -> pd.Series:
    """Prior-day CBOE VIX close, indexed by the date it applies TO."""
    if not VIX_PATH.exists():
        r = requests.get(VIX_URL, headers={"User-Agent": UA}, timeout=40)
        r.raise_for_status()
        VIX_PATH.write_bytes(r.content)
    v = pd.read_csv(VIX_PATH)
    v["DATE"] = pd.to_datetime(v["DATE"], format="%m/%d/%Y")
    v = v.sort_values("DATE").set_index("DATE")["CLOSE"]
    # shift(1): the value carried into date d is the PREVIOUS session's close
    return v.shift(1).rename("vix_prev")


def load_intraday_paths(ev: pd.DataFrame, max_min: int) -> pd.DataFrame:
    """Per-event close at each minute plus running low/high after entry."""
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
        d = d[d["minute"] <= max_min]
        d = d[[(t, dt) in want for t, dt in zip(d["ticker"], d["date"])]]
        if not d.empty:
            frames.append(d)
        if i % 250 == 0:
            log(f"  {i}/{len(files)} files")
    return pd.concat(frames, ignore_index=True)


def build_paths(raw: pd.DataFrame, max_min: int) -> pd.DataFrame:
    """Wide: close at every minute, and cumulative low/high from 09:46 on."""
    close = raw.pivot_table(index=["ticker", "date"], columns="minute",
                            values="close", aggfunc="last").reindex(
                                columns=range(max_min + 1))
    close = close.ffill(axis=1)
    close.columns = [f"m{c}" for c in close.columns]

    post = raw[raw["minute"] > ENTRY_MIN]
    lows = post.pivot_table(index=["ticker", "date"], columns="minute",
                            values="low", aggfunc="min").reindex(
                                columns=range(ENTRY_MIN + 1, max_min + 1))
    highs = post.pivot_table(index=["ticker", "date"], columns="minute",
                             values="high", aggfunc="max").reindex(
                                 columns=range(ENTRY_MIN + 1, max_min + 1))
    # cumulative extremes: worst level reached by each minute
    cl = lows.cummin(axis=1)
    ch = highs.cummax(axis=1)
    cl.columns = [f"lo{c}" for c in cl.columns]
    ch.columns = [f"hi{c}" for c in ch.columns]
    return close.join(cl).join(ch).reset_index()


def dist_stats(s: pd.Series, label: dict) -> dict:
    b = s * 1e4
    rec = dict(label)
    rec.update({
        "n": len(b), "mean_bps": b.mean(), "median_bps": b.median(),
        "p10": b.quantile(0.10), "p25": b.quantile(0.25),
        "p75": b.quantile(0.75), "p90": b.quantile(0.90),
        "pct_gt_100": (b > 100).mean() * 100, "pct_lt_m100": (b < -100).mean() * 100,
        "pct_gt_200": (b > 200).mean() * 100, "pct_lt_m200": (b < -200).mean() * 100,
        "skew": b.skew(),
    })
    return rec


def rate_and_exp(s: pd.Series, dates: pd.Series, cost: pd.Series,
                 label: dict) -> dict:
    n = len(s)
    k = int((s > 0).sum())
    lo, hi = wilson(k, n)
    b = A.clustered_bootstrap(s, dates, n_boot=N_BOOT)
    net = (s - cost).dropna()
    bn = A.clustered_bootstrap(net, dates.loc[net.index], n_boot=N_BOOT)
    rec = dict(label)
    rec.update({"n": n, "win_rate": k / n if n else np.nan,
                "wilson_lo": lo, "wilson_hi": hi,
                "exp_bps": b["stat"] * 1e4, "exp_p": b["p"],
                "net_bps": bn["stat"] * 1e4, "net_p": bn["p"],
                "small": "YES" if n < MIN_CELL else ""})
    return rec


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ev = pd.read_parquet(BASE / "events.parquet")
    ev["date"] = pd.to_datetime(ev["date"])
    ev = ev[ev["gap"] != 0].copy()
    ev["gap_up"] = ev["gap"] > 0
    ev["pattern_simple"] = ev.apply(simple_first_candle, axis=1)
    ev["stage_group"] = np.where(ev["stage_prev"] == 2.0, "Stage 2",
                                 np.where(ev["stage_prev"].isin([3.0, 4.0]),
                                          "Stage 3+4", None))

    # --- prior-day ATR(14), from the daily panel, shifted one session ---
    panel = pd.read_parquet(BASE / "panel.parquet",
                            columns=["ticker", "date", "atr14", "close"])
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel.sort_values(["ticker", "date"])
    panel["atr14_prev"] = panel.groupby("ticker")["atr14"].shift(1)
    ev = ev.merge(panel[["ticker", "date", "atr14_prev"]], on=["ticker", "date"],
                  how="left")

    # --- prior-day VIX close ---
    vix = load_vix()
    ev["vix_prev"] = vix.reindex(ev["date"]).to_numpy()
    log(f"VIX matched on {ev['vix_prev'].notna().mean():.1%} of events")

    max_min = max(WINDOWS.values())
    raw = load_intraday_paths(ev, max_min)
    paths = build_paths(raw, max_min)
    df = ev.merge(paths, on=["ticker", "date"], how="inner", suffixes=("", "_p"))
    log(f"joined: {len(df):,}")

    bench = load_bench_0945()
    spy = bench[bench["bench"] == "SPY"][["date", "ret_0945"]].rename(
        columns={"ret_0945": "spy_0945"})
    df = df.merge(spy, on="date", how="left")
    df["spy_agree"] = np.where(
        df["spy_0945"].isna() | (df["spy_0945"] == 0), None,
        np.where(np.sign(df["spy_0945"]) == np.sign(df["gap"]),
                 "SPY Agree", "SPY Disagree"))

    entry = df[f"m{ENTRY_MIN}"]
    sign = np.where(df["gap_up"], 1.0, -1.0)
    df = df[entry.notna()].copy()
    entry = df[f"m{ENTRY_MIN}"]
    sign = np.where(df["gap_up"], 1.0, -1.0)

    # gap measured in ATR units, both terms known before the open
    prev_close = df["open"] / (1.0 + df["gap"])
    df["gap_atr"] = (df["open"] - prev_close).abs() / df["atr14_prev"]

    spread = A.spread_series(df)
    df["cost"] = 2.0 * (spread / 2.0 + 2.0) / 1e4

    CONT = "Continuation (1st candle with gap)"
    cohorts = [
        ("All events", df),
        ("Simple Continuation", df[df["pattern_simple"] == CONT]),
        ("Cont + SPY Agree",
         df[(df["pattern_simple"] == CONT) & (df["spy_agree"] == "SPY Agree")]),
        ("Cont + SPY Agree + Stage 3+4",
         df[(df["pattern_simple"] == CONT) & (df["spy_agree"] == "SPY Agree")
            & (df["stage_group"] == "Stage 3+4")]),
    ]

    R: dict[str, pd.DataFrame] = {}

    # ---------------- PART 1: distribution ----------------
    rows, rows_wl = [], []
    for wname, wmin in WINDOWS.items():
        ret_all = pd.Series(sign, index=df.index) * (df[f"m{wmin}"] / entry - 1.0)
        for cname, sub in cohorts:
            r = ret_all.loc[sub.index].dropna()
            if len(r) < 30:
                continue
            rows.append(dist_stats(r, {"window": wname, "cohort": cname}))
            rows_wl.append(dist_stats(r[r > 0], {"window": wname, "cohort": cname,
                                                 "side": "Winners"}))
            rows_wl.append(dist_stats(r[r < 0], {"window": wname, "cohort": cname,
                                                 "side": "Losers"}))
    R["p1_distribution"] = pd.DataFrame(rows)
    R["p1_winners_losers"] = pd.DataFrame(rows_wl)

    # ---------------- PART 2: stop-loss ----------------
    rows = []
    for wname, wmin in WINDOWS.items():
        lo_col, hi_col = f"lo{wmin}", f"hi{wmin}"
        if lo_col not in df.columns:
            continue
        gross = pd.Series(sign, index=df.index) * (df[f"m{wmin}"] / entry - 1.0)
        for stop in STOPS_BPS:
            frac = stop / 1e4
            adverse = np.where(df["gap_up"],
                               df[lo_col] <= entry * (1 - frac),
                               df[hi_col] >= entry * (1 + frac))
            hit = pd.Series(adverse, index=df.index).fillna(False)
            stopped_ret = pd.Series(np.where(hit, -frac, gross), index=df.index)
            for cname, sub in cohorts:
                idx = sub.index
                g, s_ret, h = gross.loc[idx], stopped_ret.loc[idx], hit.loc[idx]
                valid = g.notna()
                g, s_ret, h = g[valid], s_ret[valid], h[valid]
                if len(g) < 30:
                    continue
                d = df.loc[g.index, "date"]
                b = A.clustered_bootstrap(s_ret, d, n_boot=N_BOOT)
                bn = A.clustered_bootstrap(s_ret - df.loc[g.index, "cost"], d,
                                           n_boot=N_BOOT)
                rows.append({
                    "window": wname, "cohort": cname, "stop_bps": stop,
                    "n": len(g), "pct_stopped": h.mean() * 100,
                    "avg_ret_stopped_nostop_bps": g[h].mean() * 1e4 if h.any() else np.nan,
                    "avg_ret_not_stopped_bps": g[~h].mean() * 1e4 if (~h).any() else np.nan,
                    "win_rate_after_stop": (s_ret > 0).mean(),
                    "exp_after_stop_bps": b["stat"] * 1e4, "exp_p": b["p"],
                    "net_after_stop_bps": bn["stat"] * 1e4, "net_p": bn["p"],
                    "exp_no_stop_bps": g.mean() * 1e4,
                    "small": "YES" if len(g) < MIN_CELL else "",
                })
    R["p2_stops"] = pd.DataFrame(rows)

    # ---------------- PART 3 & 4: VIX and ATR regimes ----------------
    def bucket_table(col, buckets, cohort_names):
        out = []
        for wname, wmin in WINDOWS.items():
            gross = pd.Series(sign, index=df.index) * (df[f"m{wmin}"] / entry - 1.0)
            for cname, sub in cohorts:
                if cname not in cohort_names:
                    continue
                for bname, lo_v, hi_v in buckets:
                    m = sub[(sub[col] >= lo_v) & (sub[col] < hi_v)]
                    r = gross.loc[m.index].dropna()
                    if len(r) < 30:
                        continue
                    out.append(rate_and_exp(
                        r, df.loc[r.index, "date"], df.loc[r.index, "cost"],
                        {"window": wname, "cohort": cname, "bucket": bname}))
        return pd.DataFrame(out)

    R["p3_vix"] = bucket_table("vix_prev", VIX_BUCKETS,
                               {"Simple Continuation", "Cont + SPY Agree"})
    R["p4_atr"] = bucket_table("gap_atr", ATR_BUCKETS, {"Simple Continuation"})

    # ---------------- PART 5: combined ----------------
    rows = []
    base = df[(df["pattern_simple"] == CONT) & (df["spy_agree"] == "SPY Agree")]
    for wname, wmin in WINDOWS.items():
        gross = pd.Series(sign, index=df.index) * (df[f"m{wmin}"] / entry - 1.0)
        for vname, vlo, vhi in VIX_BUCKETS:
            for aname, alo, ahi in ATR_BUCKETS:
                m = base[(base["vix_prev"] >= vlo) & (base["vix_prev"] < vhi)
                         & (base["gap_atr"] >= alo) & (base["gap_atr"] < ahi)]
                r = gross.loc[m.index].dropna()
                if len(r) < MIN_CELL:
                    continue
                rows.append(rate_and_exp(
                    r, df.loc[r.index, "date"], df.loc[r.index, "cost"],
                    {"window": wname, "cohort": "Cont + SPY Agree",
                     "bucket": f"{vname} | {aname}"}))
    R["p5_combined"] = (pd.DataFrame(rows).sort_values("net_bps", ascending=False)
                        .reset_index(drop=True) if rows else pd.DataFrame())

    meta = {"n_events": int(len(df)),
            "vix_coverage": float(df["vix_prev"].notna().mean()),
            "atr_coverage": float(df["gap_atr"].notna().mean()),
            "median_cost_bps": float(df["cost"].median() * 1e4),
            "min_cell": MIN_CELL, "stops": STOPS_BPS}

    for k, v in R.items():
        v.to_csv(OUT_DIR / f"{k}.csv", index=False)
    (BASE / "deep_meta.json").write_text(json.dumps(meta, indent=1))
    FEED.write_text(json.dumps(
        {"meta": meta, **{k: json.loads(v.round(6).to_json(orient="records"))
                          for k, v in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables")

    from deep_text import build  # noqa: E402
    REPORT.write_text(build(R, meta))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
