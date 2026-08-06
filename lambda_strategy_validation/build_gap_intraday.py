"""
build_gap_intraday.py — 1-minute opening bars for GENERAL gap sessions
(not earnings-conditioned), 2021-2025.

The daily panel already carries the 09:30-09:35 candle (c1_*) and the open
of the 09:35 bar (c2_open) for every session, so the signal and the 5-minute
exit need no new data. The 15-minute (09:50 = minute 19) and 1-hour
(10:35 = minute 64) exits do.

Downloading every session of every ticker would be far more than needed, so
the target set is restricted up front to sessions that actually pass the
universe and gap filters. That is ~128k ticker-days rather than ~470k.

Output: /home/user/lambda_data/gapintraday/{ticker}.parquet
  ticker, date, minute (0 = 09:30-09:31 ... 69), open, high, low, close,
  volume, session_open, session_close

Run: ELKASSABGIDATA_KEY=... python3 \
        lambda_strategy_validation/build_gap_intraday.py
"""

from __future__ import annotations

import io
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from build_derived import BARS_URL, fetch_with_retry, log  # noqa: E402

BASE = Path("/home/user/lambda_data")
OUT_DIR = BASE / "gapintraday"
TARGETS = BASE / "gap_targets.parquet"

N_MINUTES = 70             # covers minute 64 (10:35) with margin
START, END = "2021-01-01", "2025-12-31"
MIN_ABS_GAP = 0.008        # |Gap| >= 0.8%
MIN_GAP_ATR = 0.7          # or Gap/ATR >= 0.7
MIN_MCAP = 3e9
MIN_PRICE = 10.0
WORKERS = 4


def build_targets() -> pd.DataFrame:
    """Universe + gap filters, entirely from prior-session information."""
    from run_study import break_aware_liquidity

    cols = ["ticker", "date", "open", "gap", "atr14", "close_prev",
            "market_cap_prev", "adv_63_prev", "adtv_63_prev",
            "price_ok_prev", "adv_ok_prev", "adtv_ok_prev", "mcap_ok_prev"]
    p = pd.read_parquet(BASE / "panel.parquet", columns=cols)
    p["date"] = pd.to_datetime(p["date"])

    # Calibrate the IEX-break-aware liquidity filter on the FULL history,
    # then subset. The study window straddles the 2022-03-01 tape change, so
    # an absolute ADV cutoff alone would silently drop most of 2022 onward.
    liq, diag = break_aware_liquidity(p)
    p["liq_ok"] = liq

    w = p[(p["date"] >= START) & (p["date"] <= END)].copy()
    keep = (w["market_cap_prev"] > MIN_MCAP).fillna(False) \
        & (w["close_prev"] >= MIN_PRICE).fillna(False) \
        & w["liq_ok"].fillna(False)
    w = w[keep].copy()

    prev_close = w["open"] / (1.0 + w["gap"])
    w["gap_atr"] = (w["open"] - prev_close).abs() / w["atr14"]
    w = w[(w["gap"].abs() >= MIN_ABS_GAP) | (w["gap_atr"] >= MIN_GAP_ATR)]
    w = w[w["gap"] != 0]
    log(f"targets: {len(w):,} ticker-days, {w['ticker'].nunique()} tickers, "
        f"{w['date'].dt.year.min()}-{w['date'].dt.year.max()}")
    return w[["ticker", "date", "gap", "gap_atr", "atr14", "open",
              "market_cap_prev", "close_prev"]].reset_index(drop=True)


def process(ticker: str, dates: set) -> bool:
    out_path = OUT_DIR / f"{ticker}.parquet"
    if out_path.exists():
        return True
    blob = fetch_with_retry(BARS_URL.format(t=ticker))
    if blob is None:
        return False

    bars = pd.read_parquet(io.BytesIO(blob))
    del blob
    bars["datetime"] = pd.to_datetime(bars["datetime"])
    bars = bars.set_index("datetime").sort_index()
    bars["date"] = bars.index.normalize()

    sel = bars[bars["date"].isin(dates)]
    del bars
    if sel.empty:
        pd.DataFrame().to_parquet(out_path, index=False)
        return True

    window = sel.between_time("09:30", "11:00", inclusive="left")
    if window.empty:
        pd.DataFrame().to_parquet(out_path, index=False)
        return True

    w = window.copy()
    w["minute"] = ((w.index.hour * 60 + w.index.minute)
                   - (9 * 60 + 30)).astype("int16")
    w = w[(w["minute"] >= 0) & (w["minute"] < N_MINUTES)]
    agg = w.groupby(["date", "minute"]).agg(
        open=("Open", "first"), high=("High", "max"), low=("Low", "min"),
        close=("Close", "last"), volume=("Volume", "sum"),
    ).reset_index()

    daily = sel.groupby("date").agg(session_open=("Open", "first"),
                                    session_close=("Close", "last"))
    agg = agg.merge(daily, on="date", how="left")
    agg["ticker"] = ticker
    for c in ("open", "high", "low", "close", "session_open",
              "session_close"):
        agg[c] = agg[c].astype("float32")
    agg.to_parquet(out_path, index=False, compression="zstd")
    return True


def main() -> None:
    if "ELKASSABGIDATA_KEY" not in os.environ:
        sys.exit("ELKASSABGIDATA_KEY not set")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    tgt = build_targets()
    tgt.to_parquet(TARGETS, index=False)
    by_ticker = {t: set(g["date"]) for t, g in tgt.groupby("ticker")}
    tickers = sorted(by_ticker)
    log(f"GAP INTRADAY START {len(tickers)} tickers")

    t0 = time.time()
    done = ok = fail = 0

    def run(t: str) -> bool:
        r = process(t, by_ticker[t])
        time.sleep(0.2)
        return r

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for t, res in zip(tickers, ex.map(run, tickers)):
            done += 1
            ok += bool(res)
            fail += (not res)
            if done % 25 == 0:
                el = time.time() - t0
                eta = el / done * (len(tickers) - done) / 60
                log(f"gap intraday {done}/{len(tickers)} ok={ok} "
                    f"fail={fail} ETA {eta:.0f}min")
    log(f"GAP INTRADAY DONE ok={ok} fail={fail} "
        f"elapsed={(time.time()-t0)/60:.1f}min")


if __name__ == "__main__":
    main()
