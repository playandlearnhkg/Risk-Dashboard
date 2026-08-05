"""
assemble.py — Build the master event panel for Sigma's study.

Output: /home/user/lambda_data/panel.parquet, one row per ticker-session
for 2015-2025, carrying everything the tests in section 3 need:

  identity   : ticker, date, sector, year, quarter
  prices     : open, high, low, close, volume
  returns    : gap (Open/PrevClose-1), o2c (Close/Open-1), daily_ret
  volatility : true_range, atr14, hl_over_open, rv_5min, parkinson
  liquidity  : adv_63, adtv_63, roll_spread_bps, corwin_schultz_bps
  stage      : stage (2/3/4), n_criteria
  universe   : price_ok, adv_ok, adtv_ok, mcap_ok, universe_ok
  event      : is_t1 (first session strictly after an earnings date),
               ann_date, ann_time
  benchmarks : spy_o2c, sector_o2c, sector_etf
  opening    : c1_*/c2_*/c3_* OHLCV for the first three 5-minute candles

Key point-in-time discipline:
  - Stage and the universe filters are evaluated on the session BEFORE
    T+1 (Sigma section 1: "applied on the day before earnings or on the
    T+1 open"), so they are carried as *_prev columns and never peek at
    the T+1 outcome.
  - SMAs use the full price history (from 2002) but the panel is then
    truncated to 2015-2025, so no SMA is computed on a truncated window.

Run: python3 lambda_strategy_validation/assemble.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from stage_classifier import compute_stage_frame  # noqa: E402

BASE = Path("/home/user/lambda_data")
DERIVED_DIR = BASE / "derived"
VARS_DIR = BASE / "vars"
SHARES_DIR = BASE / "shares"
EARN_DIR = BASE / "earnings"
META_PATH = BASE / "ticker_meta.json"
PANEL_PATH = BASE / "panel.parquet"
LOG_PATH = BASE / "assemble.log"

START, END = "2015-01-01", "2025-12-31"
LIQ_WINDOW = 63          # ~3 months, for ADV / ADTV
ATR_WINDOW = 14

# Sigma section 2C needs a sector benchmark. XLRE is absent from the HF
# universe, so Real Estate uses IYR (iShares US Real Estate) instead.
# XLC only launched mid-2018; Communication Services observations before
# that get no sector benchmark and are flagged, not silently dropped.
SECTOR_ETF = {
    "Technology": "XLK",
    "Consumer Discretionary": "XLY",
    "Financials": "XLF",
    "Industrials": "XLI",
    "Healthcare": "XLV",
    "Communication Services": "XLC",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Materials": "XLB",
    "Real Estate": "IYR",
    "Utilities": "XLU",
}


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a") as fh:
        fh.write(line + "\n")


def load_ticker(ticker: str) -> pd.DataFrame | None:
    """Daily OHLCV + opening candles + the pre-computed variables."""
    dpath = DERIVED_DIR / f"{ticker}.parquet"
    if not dpath.exists():
        return None
    df = pd.read_parquet(dpath)
    df["date"] = pd.to_datetime(df["date"])
    vpath = VARS_DIR / f"{ticker}.parquet"
    if vpath.exists():
        v = pd.read_parquet(vpath)
        v["date"] = pd.to_datetime(v["trade_date"])
        keep = ["date", "rv_5min", "parkinson", "roll_spread_bps",
                "corwin_schultz_bps", "dollar_volume", "share_volume",
                "overnight_return", "open_to_close_return", "amihud_illiquidity"]
        v = v[[c for c in keep if c in v.columns]]
        df = df.merge(v, on="date", how="left")
    return df.sort_values("date").reset_index(drop=True)


def benchmark_o2c(ticker: str) -> pd.Series | None:
    """Open-to-close simple return for a benchmark ETF, indexed by date."""
    df = load_ticker(ticker)
    if df is None:
        return None
    s = (df["close"] / df["open"] - 1.0)
    s.index = df["date"]
    return s.rename(ticker)


def load_earnings() -> pd.DataFrame:
    files = sorted(EARN_DIR.glob("*.parquet"))
    if not files:
        raise FileNotFoundError("no earnings parquets — run build_earnings.py")
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df["ann_date"] = pd.to_datetime(df["date"])
    df = df[["ann_date", "symbol", "time"]].rename(
        columns={"symbol": "ticker", "time": "ann_time"})
    return df.drop_duplicates(["ann_date", "ticker"])


def load_shares(ticker: str) -> pd.Series | None:
    p = SHARES_DIR / f"{ticker}.parquet"
    if not p.exists():
        return None
    s = pd.read_parquet(p)
    if "shares_split_adj" not in s.columns:
        return None
    out = s.set_index(pd.to_datetime(s["filed"]))["shares_split_adj"]
    return out[~out.index.duplicated(keep="last")].sort_index()


def build_ticker_panel(
    ticker: str, sector: str, earnings: pd.DataFrame,
    spy: pd.Series, sector_series: dict[str, pd.Series],
) -> pd.DataFrame | None:
    df = load_ticker(ticker)
    if df is None or len(df) < 300:
        return None

    # --- Stage, on full history so SMAs are never computed on a stub ---
    stage_input = df.set_index("date")[["close"]]
    sf = compute_stage_frame(stage_input)
    df["stage"] = sf["stage"].to_numpy()
    df["n_criteria"] = sf["n_criteria"].to_numpy()

    # --- Returns (simple, exactly as Sigma writes them) ---
    prev_close = df["close"].shift(1)
    df["gap"] = df["open"] / prev_close - 1.0
    df["o2c"] = df["close"] / df["open"] - 1.0
    df["daily_ret"] = df["close"] / prev_close - 1.0

    # --- Volatility ---
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    df["true_range"] = tr
    df["atr14"] = tr.rolling(ATR_WINDOW).mean()
    df["tr_pct"] = tr / prev_close
    df["hl_over_open"] = (df["high"] - df["low"]) / df["open"]

    # --- Liquidity (trailing, so knowable before the event) ---
    if "share_volume" not in df.columns:
        df["share_volume"] = df["volume"]
    if "dollar_volume" not in df.columns:
        df["dollar_volume"] = df["close"] * df["volume"]
    df["adv_63"] = df["share_volume"].rolling(LIQ_WINDOW, min_periods=LIQ_WINDOW).mean()
    df["adtv_63"] = df["dollar_volume"].rolling(LIQ_WINDOW, min_periods=LIQ_WINDOW).mean()

    # --- Market cap ---
    shares = load_shares(ticker)
    if shares is not None:
        df["shares_adj"] = shares.reindex(df["date"], method="ffill").to_numpy()
        df["market_cap"] = df["close"] * df["shares_adj"]
    else:
        df["market_cap"] = np.nan

    # --- Universe filters, evaluated on the PREVIOUS session ---
    df["price_ok"] = df["close"] >= 10.0
    df["adv_ok"] = df["adv_63"] >= 500_000
    df["adtv_ok"] = df["adtv_63"] >= 50_000_000
    df["mcap_ok"] = df["market_cap"] > 3_000_000_000
    for col in ("price_ok", "adv_ok", "adtv_ok", "mcap_ok", "stage",
                "n_criteria", "market_cap", "adv_63", "adtv_63", "close"):
        df[f"{col}_prev"] = df[col].shift(1)
    df["universe_ok_prev"] = (
        df["price_ok_prev"].astype("boolean")
        & df["adv_ok_prev"].astype("boolean")
        & df["adtv_ok_prev"].astype("boolean")
        & df["mcap_ok_prev"].astype("boolean")
    )

    # --- Event flag: T+1 = first session strictly after an announcement ---
    ann = earnings[earnings["ticker"] == ticker]
    df["is_t1"] = False
    df["ann_date"] = pd.NaT
    df["ann_time"] = pd.NA
    if not ann.empty:
        dates = df["date"].to_numpy()
        pos = np.searchsorted(dates, ann["ann_date"].to_numpy(), side="right")
        valid = pos < len(dates)
        idx = pos[valid]
        df.loc[df.index[idx], "is_t1"] = True
        df.loc[df.index[idx], "ann_date"] = ann["ann_date"].to_numpy()[valid]
        df.loc[df.index[idx], "ann_time"] = ann["ann_time"].to_numpy()[valid]

    # --- Benchmarks ---
    df["spy_o2c"] = spy.reindex(df["date"]).to_numpy()
    etf = SECTOR_ETF.get(sector)
    df["sector_etf"] = etf
    ser = sector_series.get(etf) if etf else None
    df["sector_o2c"] = ser.reindex(df["date"]).to_numpy() if ser is not None else np.nan

    df["ticker"] = ticker
    df["sector"] = sector
    return df[(df["date"] >= START) & (df["date"] <= END)]


def main() -> None:
    meta = json.loads(META_PATH.read_text())
    stocks = {t: v for t, v in meta.items() if v.get("type") == "Stock"}
    earnings = load_earnings()
    log(f"earnings rows={len(earnings)} tickers={earnings['ticker'].nunique()}")

    spy = benchmark_o2c("SPY")
    if spy is None:
        raise RuntimeError("SPY derived file missing")
    sector_series = {}
    for etf in sorted(set(SECTOR_ETF.values())):
        s = benchmark_o2c(etf)
        if s is None:
            log(f"WARNING: benchmark {etf} unavailable")
        else:
            sector_series[etf] = s

    frames = []
    t0 = time.time()
    tickers = sorted(stocks)
    for i, t in enumerate(tickers, 1):
        try:
            p = build_ticker_panel(t, stocks[t].get("sector"), earnings, spy, sector_series)
            if p is not None and not p.empty:
                frames.append(p)
        except Exception as exc:  # noqa: BLE001
            log(f"{t}: ERROR {exc}")
        if i % 100 == 0 or i == len(tickers):
            log(f"{i}/{len(tickers)} frames={len(frames)} "
                f"elapsed={(time.time()-t0)/60:.1f}min")

    panel = pd.concat(frames, ignore_index=True)
    panel.to_parquet(PANEL_PATH, index=False)
    log(f"WROTE {PANEL_PATH} rows={len(panel):,} tickers={panel['ticker'].nunique()} "
        f"t1_events={int(panel['is_t1'].sum()):,}")


if __name__ == "__main__":
    main()
