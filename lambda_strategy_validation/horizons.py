"""
horizons.py — Short holding periods, candle-pattern conditioning, and a
TRADEABLE market-agreement filter.

Three questions:

1. HOLDING PERIOD. Enter at 09:35 / 09:45 / 10:00, exit 15 min, 30 min,
   60 min later or at the close. The full-session test pools an informative
   first hour with an uninformative afternoon; a short hold may not.

2. CANDLE PATTERN. Condition each of those cells on the first three
   5-minute candles. Entering at 09:45 uses only 09:30-09:45 information,
   so the pattern is genuinely known at entry — no look-ahead.

3. MARKET AGREEMENT — the tradeable rebuild of Sigma's section 2C.
   Sigma's filter compares the stock's T+1 OPEN-TO-CLOSE return with SPY's
   and the sector's. That return is not known until 16:00, and
   "continuation" is defined by the sign of that very return, so filtering
   on it conditions on the outcome. It is a diagnostic, not a trading rule.
   The tradeable analogue uses only what is on the screen at entry: how far
   SPY (and the sector ETF) has moved from the open by the entry minute.
   Both are reported side by side so the gap between them is visible.

Run: python3 lambda_strategy_validation/horizons.py
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd

import analysis as A  # noqa: E402

BASE = Path("/home/user/lambda_data")
INTRADAY_DIR = BASE / "intraday90"
BENCH_PATH = BASE / "bench_intraday.parquet"
EVENTS = BASE / "events.parquet"
OUT_DIR = BASE / "tables"

MAX_MIN = 90
ENTRIES = {"09:35": 5, "09:45": 15, "10:00": 30}
EXITS = {"+15min": 15, "+30min": 30, "+60min": 60, "close": None}
IMPACT_BPS = 2.0


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
        if i % 200 == 0:
            log(f"  {i}/{len(files)} files")
    raw = pd.concat(frames, ignore_index=True)
    wide = raw.pivot_table(index=["ticker", "date"], columns="minute",
                           values="close", aggfunc="last")
    wide = wide.reindex(columns=range(MAX_MIN))
    sess = raw.groupby(["ticker", "date"])[["session_open", "session_close"]].first()
    # Forward-fill: a minute with no print means no trade, so the prevailing
    # price is the last one printed. Keeps the sample identical across all
    # entry/exit pairs (see intraday_timing.py for why this matters).
    wide.insert(0, "seed", sess["session_open"])
    wide = wide.ffill(axis=1).drop(columns="seed")
    wide.columns = [f"m{int(c)}" for c in wide.columns]
    return wide.join(sess).reset_index()


def load_bench() -> tuple[pd.DataFrame, pd.DataFrame]:
    b = pd.read_parquet(BENCH_PATH)
    b["date"] = pd.to_datetime(b["date"])
    spy = b[b["bench"] == "SPY"]
    spy_wide = spy.pivot_table(index="date", columns="minute", values="close",
                               aggfunc="last").reindex(columns=range(MAX_MIN))
    spy_open = spy.groupby("date")["bench_open"].first()
    spy_wide.insert(0, "seed", spy_open)
    spy_wide = spy_wide.ffill(axis=1).drop(columns="seed")
    spy_wide.columns = [f"s{int(c)}" for c in spy_wide.columns]
    spy_wide["spy_open"] = spy_open
    return spy_wide.reset_index(), b


def stat_row(net: pd.Series, dates: pd.Series, gross: pd.Series, **extra) -> dict:
    b = A.clustered_bootstrap(net, dates)
    hit = float((gross > 0).mean()) if len(gross) else np.nan
    out = {"n": b["n"], "n_dates": b["n_clusters"], "net_bps": b["stat"] * 1e4,
           "ci_lo_bps": b["lo"] * 1e4, "ci_hi_bps": b["hi"] * 1e4, "p": b["p"],
           "hit_rate": hit}
    out.update(extra)
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ev = pd.read_parquet(EVENTS)
    ev["date"] = pd.to_datetime(ev["date"])
    log(f"events {len(ev):,}")

    wide = load_wide(ev)
    spy_wide, _ = load_bench()
    df = ev.merge(wide, on=["ticker", "date"], how="inner", suffixes=("", "_i"))
    df = df.merge(spy_wide, on="date", how="left")
    df = df[df["session_open"].notna() & df["session_close"].notna()].reset_index(drop=True)
    log(f"joined {len(df):,}")

    sign = np.where(df["gap_up"], 1.0, -1.0)
    spread = A.spread_series(df)
    cost = 2.0 * (spread / 2.0 + IMPACT_BPS) / 1e4
    close_px = df["session_close"]

    def px(minute):
        return close_px if minute is None else df[f"m{minute}"]

    # ---------- 1. entry x exit grid ----------
    rows = []
    for ename, emin in ENTRIES.items():
        entry = df[f"m{emin}"]
        for xname, off in EXITS.items():
            xmin = None if off is None else emin + off
            if xmin is not None and xmin >= MAX_MIN:
                continue
            gross = pd.Series(sign * (px(xmin) / entry - 1.0), index=df.index)
            rows.append(stat_row(gross - cost, df["date"], gross,
                                 entry_time=ename, exit=xname))
    grid = pd.DataFrame(rows)[["entry_time", "exit", "n", "n_dates", "net_bps",
                               "ci_lo_bps", "ci_hi_bps", "p", "hit_rate"]]
    grid.to_csv(OUT_DIR / "horizon_grid.csv", index=False)

    # ---------- 2. conditioned on the opening candle pattern ----------
    # Entry fixed at 09:45, the first moment the three candles are complete.
    emin = ENTRIES["09:45"]
    entry = df[f"m{emin}"]
    rows = []
    for xname, off in EXITS.items():
        xmin = None if off is None else emin + off
        if xmin is not None and xmin >= MAX_MIN:
            continue
        gross_all = pd.Series(sign * (px(xmin) / entry - 1.0), index=df.index)
        for pat in ["Strong Continuation+", "Moderate Continuation+",
                    "Indecision0", "Early Reversal-"]:
            m = df["pattern"] == pat
            if m.sum() < 30:
                continue
            rows.append(stat_row((gross_all - cost)[m], df.loc[m, "date"],
                                 gross_all[m], exit=xname, pattern=pat))
        for label, m in (("+ patterns", df["pattern_plus"] == True),          # noqa: E712
                         ("everything else", df["pattern_plus"] == False)):   # noqa: E712
            rows.append(stat_row((gross_all - cost)[m], df.loc[m, "date"],
                                 gross_all[m], exit=xname, pattern=label))
    bypat = pd.DataFrame(rows)[["exit", "pattern", "n", "n_dates", "net_bps",
                                "ci_lo_bps", "ci_hi_bps", "p", "hit_rate"]]
    bypat.to_csv(OUT_DIR / "horizon_by_pattern.csv", index=False)

    # ---------- 3. market-agreement filter: tradeable vs Sigma's ----------
    spy_move = df[f"s{emin}"] / df["spy_open"] - 1.0      # SPY, open -> 09:45
    beta = df["beta"].fillna(1.0)
    expected = beta * spy_move                            # beta-adjusted drift
    agree_raw = np.sign(df["gap"]) == np.sign(spy_move)
    agree_beta = np.sign(df["gap"]) == np.sign(expected)
    rows = []
    for xname, off in EXITS.items():
        xmin = None if off is None else emin + off
        if xmin is not None and xmin >= MAX_MIN:
            continue
        gross_all = pd.Series(sign * (px(xmin) / entry - 1.0), index=df.index)
        cohorts = {
            "no filter": pd.Series(True, index=df.index),
            "TRADEABLE: gap agrees with SPY move to 09:45": pd.Series(agree_raw, index=df.index),
            "TRADEABLE: gap agrees with beta x SPY": pd.Series(agree_beta, index=df.index),
            "TRADEABLE: gap disagrees with SPY (control)": ~pd.Series(agree_raw, index=df.index),
            "SIGMA 2C (look-ahead, uses 16:00 return)": df["beta_ok"].fillna(False).astype(bool),
        }
        for label, m in cohorts.items():
            m = m.fillna(False) if hasattr(m, "fillna") else m
            if m.sum() < 30:
                continue
            rows.append(stat_row((gross_all - cost)[m], df.loc[m, "date"],
                                 gross_all[m], exit=xname, cohort=label))
    mkt = pd.DataFrame(rows)[["exit", "cohort", "n", "n_dates", "net_bps",
                              "ci_lo_bps", "ci_hi_bps", "p", "hit_rate"]]
    mkt.to_csv(OUT_DIR / "horizon_market_filter.csv", index=False)

    pd.set_option("display.width", 210)
    log("ENTRY x EXIT GRID")
    print(grid.round(2).to_string(index=False))
    log("BY OPENING CANDLE PATTERN (entry 09:45)")
    print(bypat.round(2).to_string(index=False))
    log("MARKET-AGREEMENT FILTER (entry 09:45)")
    print(mkt.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
