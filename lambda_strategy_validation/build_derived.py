"""
build_derived.py — One pass over HF Data Library 1-minute bars per ticker,
producing the two derived tables the study needs, then deleting the raw
parquet (raw bars for the whole universe would be ~20-35 GB).

Per ticker it writes ONE parquet to DERIVED_DIR/{ticker}.parquet with one
row per trading session:
  daily OHLCV      : open, high, low, close, volume, n_bars
  opening 3 candles: c1_*, c2_*, c3_* for 09:30-09:35, 09:35-09:40,
                     09:40-09:45 ET (open/high/low/close/volume each)
  bookkeeping      : n_bars_first15 (how many 1-min bars actually traded
                     in the first 15 minutes — lets the analysis drop
                     sessions where the opening pattern is not measurable)

The opening-candle features are computed for EVERY session, not just
earnings T+1 sessions, so this pass does not depend on having the earnings
calendar yet. The analysis step joins on earnings dates afterwards.

Also fetches the per-ticker `variables` table (~1 MB, 25 pre-computed
academic variables incl. overnight_return, open_to_close_return, realized
volatility and measured Roll / Corwin-Schultz spreads) into
VARS_DIR/{ticker}.parquet.

Resumable: a ticker whose output already exists is skipped.
Run:  ELKASSABGIDATA_KEY=... python3 lambda_strategy_validation/build_derived.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests

BASE = Path("/home/user/lambda_data")
DERIVED_DIR = BASE / "derived"
VARS_DIR = BASE / "vars"
META_PATH = BASE / "ticker_meta.json"
LOG_PATH = BASE / "build_derived.log"

BARS_URL = "https://api.hfdatalibrary.com/v1/download/{t}?version=clean&format=parquet&via=mcp"
VARS_URL = "https://api.hfdatalibrary.com/v1/variables/{t}"

# Opening 5-minute candle windows (ET), per Sigma section 2D.
CANDLE_WINDOWS = [
    ("c1", "09:30", "09:35"),
    ("c2", "09:35", "09:40"),
    ("c3", "09:40", "09:45"),
]


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a") as fh:
        fh.write(line + "\n")


# The API rejects Python's default user agent with 403, so send a browser UA.
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")


def fetch_with_retry(url: str, attempts: int = 4, timeout: int = 180) -> bytes | None:
    headers = {"X-API-Key": os.environ["ELKASSABGIDATA_KEY"], "User-Agent": _UA}
    delay = 2.0
    for i in range(attempts):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.content
        except Exception as exc:  # noqa: BLE001 - network layer, log and retry
            if i == attempts - 1:
                log(f"  FAILED after {attempts} attempts: {exc}")
                return None
            time.sleep(delay)
            delay *= 2
    return None


def opening_candles_frame(first15: pd.DataFrame) -> pd.DataFrame:
    """
    first15: 1-minute bars restricted to 09:30-09:45 ET across all sessions,
    indexed by datetime with a 'date' column. Returns one row per session
    with c1_/c2_/c3_ OHLCV columns.

    Vectorised: bucket each minute into candle 0/1/2 and do a single
    groupby, rather than slicing per session (the per-session loop cost
    ~13 s/ticker, which is ~3 h across the universe).
    """
    if first15.empty:
        return pd.DataFrame()
    df = first15.copy()
    minutes_from_open = (df.index.hour * 60 + df.index.minute) - (9 * 60 + 30)
    df["bucket"] = (minutes_from_open // 5).astype("int8")
    grouped = df.groupby(["date", "bucket"]).agg(
        open=("Open", "first"), high=("High", "max"), low=("Low", "min"),
        close=("Close", "last"), volume=("Volume", "sum"),
    )
    wide = grouped.unstack("bucket")
    wide.columns = [f"c{int(b) + 1}_{field}" for field, b in wide.columns]
    wide["n_bars_first15"] = first15.groupby("date").size()
    keep = [f"c{i}_{f}" for i in (1, 2, 3)
            for f in ("open", "high", "low", "close", "volume")]
    for col in keep:
        if col not in wide.columns:
            wide[col] = float("nan")
    return wide[keep + ["n_bars_first15"]]


def process_ticker(ticker: str) -> bool:
    out_path = DERIVED_DIR / f"{ticker}.parquet"
    vars_path = VARS_DIR / f"{ticker}.parquet"
    if out_path.exists() and vars_path.exists():
        return True

    if not vars_path.exists():
        blob = fetch_with_retry(VARS_URL.format(t=ticker))
        if blob is None:
            log(f"{ticker}: no variables file")
        else:
            vars_path.write_bytes(blob)

    if out_path.exists():
        return True

    blob = fetch_with_retry(BARS_URL.format(t=ticker))
    if blob is None:
        log(f"{ticker}: no bars, skipping")
        return False

    bars = pd.read_parquet(io.BytesIO(blob))
    del blob
    bars["datetime"] = pd.to_datetime(bars["datetime"])
    bars = bars.set_index("datetime").sort_index()
    bars["date"] = bars.index.normalize()

    daily = bars.groupby("date").agg(
        open=("Open", "first"), high=("High", "max"), low=("Low", "min"),
        close=("Close", "last"), volume=("Volume", "sum"), n_bars=("Close", "count"),
    )

    # Opening-candle features: restrict to the first 15 minutes once, then
    # group — far cheaper than slicing the full session per day.
    first15 = bars.between_time("09:30", "09:45", inclusive="left")
    opening = opening_candles_frame(first15)

    result = daily.join(opening, how="left")
    result["ticker"] = ticker
    result = result.reset_index()
    result.to_parquet(out_path, index=False)
    return True


def main() -> None:
    if "ELKASSABGIDATA_KEY" not in os.environ:
        sys.exit("ELKASSABGIDATA_KEY not set")
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    VARS_DIR.mkdir(parents=True, exist_ok=True)

    meta = json.loads(META_PATH.read_text())
    # Sigma section 1: "All US-listed common stocks" -> stocks only.
    # SPY and the sector ETFs are added because section 2C needs them as
    # benchmarks for the relative-beta filter.
    benchmarks = ["SPY", "XLK", "XLY", "XLF", "XLI", "XLV", "XLC", "XLP",
                  "XLE", "XLB", "XLU", "IYR"]
    tickers = sorted([t for t, v in meta.items() if v.get("type") == "Stock"])
    tickers = benchmarks + [t for t in tickers if t not in benchmarks]

    log(f"START {len(tickers)} tickers")
    done = fail = 0
    t0 = time.time()
    for i, t in enumerate(tickers, 1):
        try:
            ok = process_ticker(t)
        except Exception as exc:  # noqa: BLE001 - never let one ticker kill the run
            log(f"{t}: ERROR {exc}")
            ok = False
        done += ok
        fail += (not ok)
        if i % 25 == 0 or i == len(tickers):
            rate = i / max(time.time() - t0, 1e-9)
            eta = (len(tickers) - i) / max(rate, 1e-9) / 60
            log(f"{i}/{len(tickers)} ok={done} fail={fail} {rate*60:.0f}/min ETA {eta:.0f}min")
    log(f"DONE ok={done} fail={fail} elapsed={(time.time()-t0)/60:.1f}min")


if __name__ == "__main__":
    main()
