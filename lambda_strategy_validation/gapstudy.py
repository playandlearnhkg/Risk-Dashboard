"""
gapstudy.py — Stage 1 test of the first-candle continuation signal on
GENERAL gaps, 2021-2025. Not conditioned on earnings.

Universe (all from prior-session information):
  Market cap > $3B, price >= $10, ADV >= 500k, |Gap| >= 0.8% OR
  Gap/ATR >= 0.7.

  The ADV cutoff is applied through break_aware_liquidity() because the
  study window straddles the 2022-03-01 IEX consolidated-tape change; a
  raw 500k share cutoff drops most of the post-2022 sample for a units
  reason rather than an economic one.

Signal : the 09:30-09:35 candle closes in the gap direction.
Entry  : the OPEN of the 09:35 bar (minute 5).
Exits  : 5 min = 09:40 (m9), 15 min = 09:50 (m19), 1 hour = 10:35 (m64).

Look-ahead guards, identical to entry0935.py:
  - the forward-filled series is seeded from session_open, so any event
    with no real print by 09:35 would enter at a price from after the
    intended entry. Those events are dropped.
  - market cap, ATR and liquidity are all prior-session values.

Run: python3 lambda_strategy_validation/gapstudy.py
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
INTRADAY_DIR = BASE / "gapintraday"
OUT_DIR = BASE / "tables"
FEED = BASE / "gapstudy_feed.json"
REPORT = Path(__file__).resolve().parent / "GAP_STAGE1_REPORT.md"

ENTRY_MIN = 5
MAX_MIN = 70
N_BOOT = 1000
SMALL = 150
COST_BPS = 6.6
CONT = "Continuation (1st candle with gap)"

WINDOWS = {"5 min (09:40)": 9, "15 min (09:50)": 19, "1 hour (10:35)": 64}
ATR_BUCKETS = [("Gap/ATR < 1.0", -np.inf, 1.0), ("Gap/ATR 1.0-2.0", 1.0, 2.0),
               ("Gap/ATR > 2.0", 2.0, np.inf)]
MCAP_BUCKETS = [("$3B - $10B", 3e9, 10e9), ("$10B - $50B", 10e9, 50e9),
                ("> $50B", 50e9, np.inf)]


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
        if i % 150 == 0:
            log(f"  {i}/{len(files)} files")
    raw = pd.concat(frames, ignore_index=True)
    wide = raw.pivot_table(index=["ticker", "date"], columns="minute",
                           values="close", aggfunc="last").reindex(
                               columns=range(MAX_MIN))
    sess = raw.groupby(["ticker", "date"])[
        ["session_open", "session_close"]].first()
    wide.insert(0, "seed", sess["session_open"])
    wide = wide.ffill(axis=1).drop(columns="seed")
    wide.columns = [f"m{int(c)}" for c in wide.columns]

    opens = raw.pivot_table(index=["ticker", "date"], columns="minute",
                            values="open", aggfunc="first").reindex(
                                columns=range(MAX_MIN))
    opens.columns = [f"o{int(c)}" for c in opens.columns]
    return wide.join(opens).join(sess).reset_index()


def stat_row(s: pd.Series, dates: pd.Series, label: dict) -> dict:
    n = len(s)
    k = int((s > 0).sum())
    lo, hi = wilson(k, n)
    b = A.clustered_bootstrap(s, dates, n_boot=N_BOOT)
    bn = A.clustered_bootstrap(s - COST_BPS / 1e4, dates, n_boot=N_BOOT)
    wins, losses = s[s > 0], s[s < 0]
    aw = wins.mean() * 1e4 if len(wins) else np.nan
    al = -losses.mean() * 1e4 if len(losses) else np.nan
    rec = dict(label)
    rec.update({"n": n, "win_rate": k / n if n else np.nan,
                "wilson_lo": lo, "wilson_hi": hi,
                "avg_win_bps": aw, "avg_loss_bps": al,
                "payoff_ratio": (aw / al) if al else np.nan,
                "gross_bps": b["stat"] * 1e4, "gross_p": b["p"],
                "net_bps": bn["stat"] * 1e4, "net_p": bn["p"],
                "net_ci_lo": bn["lo"] * 1e4, "net_ci_hi": bn["hi"] * 1e4,
                "small": "YES" if n < SMALL else ""})
    return rec


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tgt = pd.read_parquet(BASE / "gap_targets.parquet")
    tgt["date"] = pd.to_datetime(tgt["date"])
    log(f"targets: {len(tgt):,}")

    # first-candle shape comes from the daily panel (available every session)
    p = pd.read_parquet(BASE / "panel.parquet",
                        columns=["ticker", "date", "c1_open", "c1_high",
                                 "c1_low", "c1_close"])
    p["date"] = pd.to_datetime(p["date"])
    ev = tgt.merge(p, on=["ticker", "date"], how="left")
    ev["gap_up"] = ev["gap"] > 0
    ev["pattern"] = ev.apply(simple_first_candle, axis=1)

    wide = load_wide(ev)
    df = ev.merge(wide, on=["ticker", "date"], how="inner")
    df = df[df["session_open"].notna()]
    n_pre = len(df)

    early = [f"o{i}" for i in range(0, ENTRY_MIN + 1) if f"o{i}" in df.columns]
    df = df[df[early].notna().any(axis=1)].copy()
    n_drop = n_pre - len(df)
    df["entry_px"] = df[f"o{ENTRY_MIN}"].fillna(df[f"m{ENTRY_MIN - 1}"])
    df = df[df["entry_px"].notna()].copy()
    log(f"events after guard: {len(df):,} (dropped {n_drop:,} with no "
        f"real print by 09:35)")

    entry = df["entry_px"]
    gap_sign = pd.Series(np.where(df["gap_up"], 1.0, -1.0), index=df.index)
    cont = df[df["pattern"] == CONT]
    log(f"Continuation n={len(cont):,} of {len(df):,}")

    R: dict[str, pd.DataFrame] = {}

    # ---------- 1. overall ----------
    rows = []
    for wname, wmin in WINDOWS.items():
        r = gap_sign * (df[f"m{wmin}"] / entry - 1.0)
        for cname, sub in (("All Continuation", cont),
                           ("Gap Up", cont[cont["gap_up"]]),
                           ("Gap Down", cont[~cont["gap_up"]])):
            s = r.reindex(sub.index).dropna()
            s = s[s != 0]
            if len(s) < 30:
                continue
            rows.append(stat_row(s, df.loc[s.index, "date"],
                                 {"window": wname, "cohort": cname}))
    R["g1_overall"] = pd.DataFrame(rows)

    # ---------- 2. Gap/ATR ----------
    rows = []
    for wname, wmin in WINDOWS.items():
        r = gap_sign * (df[f"m{wmin}"] / entry - 1.0)
        for bname, lo_v, hi_v in ATR_BUCKETS:
            sub = cont[(cont["gap_atr"] >= lo_v) & (cont["gap_atr"] < hi_v)]
            s = r.reindex(sub.index).dropna()
            s = s[s != 0]
            if len(s) < 30:
                continue
            rows.append(stat_row(s, df.loc[s.index, "date"],
                                 {"window": wname, "bucket": bname}))
    R["g2_gapatr"] = pd.DataFrame(rows)

    # ---------- 3. market cap ----------
    rows = []
    for wname, wmin in WINDOWS.items():
        r = gap_sign * (df[f"m{wmin}"] / entry - 1.0)
        for bname, lo_v, hi_v in MCAP_BUCKETS:
            sub = cont[(cont["market_cap_prev"] >= lo_v)
                       & (cont["market_cap_prev"] < hi_v)]
            s = r.reindex(sub.index).dropna()
            s = s[s != 0]
            if len(s) < 30:
                continue
            rows.append(stat_row(s, df.loc[s.index, "date"],
                                 {"window": wname, "bucket": bname}))
    R["g3_mcap"] = pd.DataFrame(rows)

    # ---------- reference: no candle filter, and by year ----------
    rows = []
    for wname, wmin in WINDOWS.items():
        r = gap_sign * (df[f"m{wmin}"] / entry - 1.0)
        s = r[df["pattern"].notna()].dropna()
        s = s[s != 0]
        rows.append(stat_row(s, df.loc[s.index, "date"],
                             {"window": wname,
                              "cohort": "All gaps, no candle filter"}))
    R["g4_nofilter"] = pd.DataFrame(rows)

    rows = []
    for wname, wmin in WINDOWS.items():
        r = gap_sign * (df[f"m{wmin}"] / entry - 1.0)
        for yr, sub in cont.groupby(cont["date"].dt.year):
            s = r.reindex(sub.index).dropna()
            s = s[s != 0]
            if len(s) < 30:
                continue
            rows.append(stat_row(s, df.loc[s.index, "date"],
                                 {"window": wname, "year": int(yr)}))
    R["g5_byyear"] = pd.DataFrame(rows)

    meta = {"n_targets": int(len(tgt)), "n_events": int(len(df)),
            "n_cont": int(len(cont)), "n_dropped": int(n_drop),
            "cost_bps": COST_BPS, "small": SMALL,
            "n_tickers": int(df["ticker"].nunique()),
            "start": str(df["date"].min().date()),
            "end": str(df["date"].max().date())}
    for k, v in R.items():
        v.to_csv(OUT_DIR / f"gs_{k}.csv", index=False)
    FEED.write_text(json.dumps(
        {"meta": meta, **{k: json.loads(v.round(6).to_json(orient="records"))
                          for k, v in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables")

    from gapstudy_text import build  # noqa: E402
    REPORT.write_text(build(R, meta))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
