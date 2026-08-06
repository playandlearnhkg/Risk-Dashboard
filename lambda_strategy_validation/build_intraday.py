"""
build_intraday.py — Second pass over the 1-minute bars, extracting the full
opening window at 1-minute resolution for EVENT sessions only.

Why a second pass: build_derived.py keeps only three 5-minute candles per
session, which fixes the entry at 09:45. Testing whether the information is
already priced by then needs finer granularity — but storing 30 one-minute
bars for every session of every ticker would be ~3 GB. Restricting to
earnings sessions (T+0 and T+1) makes it ~1M rows.

Output: /home/user/lambda_data/intraday/{ticker}.parquet, long format
  ticker, date, minute (0 = 09:30-09:31, ... 29 = 09:59-10:00),
  open, high, low, close, volume
plus session_open and session_close on every row for convenience.

Run: ELKASSABGIDATA_KEY=... python3 lambda_strategy_validation/build_intraday.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

from build_derived import BARS_URL, fetch_with_retry, log  # noqa: E402

BASE = Path("/home/user/lambda_data")
INTRADAY_DIR = BASE / "intraday90"
EARN_DIR = BASE / "earnings"
META_PATH = BASE / "ticker_meta.json"

N_MINUTES = 90          # 09:30 -> 11:00, so exits out to 10:45 are testable
START, END = "2015-01-01", "2025-12-31"


def event_dates_by_ticker() -> dict[str, set]:
    """Announcement dates per ticker; the T+1 session is picked up by taking
    the announcement date and the two sessions around it."""
    files = sorted(EARN_DIR.glob("*.parquet"))
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df["d"] = pd.to_datetime(df["date"])
    df = df[(df["d"] >= START) & (df["d"] <= END)]
    out: dict[str, set] = {}
    for tkr, g in df.groupby("symbol"):
        out[tkr] = set(g["d"].dt.normalize())
    return out


def process(ticker: str, ann_dates: set) -> bool:
    out_path = INTRADAY_DIR / f"{ticker}.parquet"
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

    sessions = pd.Index(sorted(bars["date"].unique()))
    # Keep the announcement session and the next two sessions, so both the
    # T+0 and T+1 conventions are covered whichever turns out to be right.
    keep = set()
    for d in ann_dates:
        pos = sessions.searchsorted(d)
        for off in (0, 1, 2):
            if pos + off < len(sessions):
                keep.add(sessions[pos + off])
    if not keep:
        pd.DataFrame().to_parquet(out_path, index=False)
        return True

    sel = bars[bars["date"].isin(keep)]
    window = sel.between_time("09:30", "11:00", inclusive="left")
    if window.empty:
        pd.DataFrame().to_parquet(out_path, index=False)
        return True

    w = window.copy()
    w["minute"] = ((w.index.hour * 60 + w.index.minute) - (9 * 60 + 30)).astype("int16")
    w = w[(w["minute"] >= 0) & (w["minute"] < N_MINUTES)]
    agg = w.groupby(["date", "minute"]).agg(
        open=("Open", "first"), high=("High", "max"), low=("Low", "min"),
        close=("Close", "last"), volume=("Volume", "sum"),
    ).reset_index()

    daily = sel.groupby("date").agg(session_open=("Open", "first"),
                                    session_close=("Close", "last"))
    agg = agg.merge(daily, on="date", how="left")
    agg["ticker"] = ticker
    agg.to_parquet(out_path, index=False)
    return True


def main() -> None:
    if "ELKASSABGIDATA_KEY" not in os.environ:
        sys.exit("ELKASSABGIDATA_KEY not set")
    INTRADAY_DIR.mkdir(parents=True, exist_ok=True)
    meta = json.loads(META_PATH.read_text())
    ann = event_dates_by_ticker()
    tickers = sorted([t for t, v in meta.items()
                      if v.get("type") == "Stock" and t in ann])
    log(f"INTRADAY START {len(tickers)} tickers with events")
    t0 = time.time()
    ok = fail = 0
    for i, t in enumerate(tickers, 1):
        try:
            good = process(t, ann[t])
        except Exception as exc:  # noqa: BLE001
            log(f"{t}: ERROR {exc}")
            good = False
        ok += good
        fail += (not good)
        if i % 25 == 0 or i == len(tickers):
            rate = i / max(time.time() - t0, 1e-9)
            log(f"intraday {i}/{len(tickers)} ok={ok} fail={fail} "
                f"ETA {(len(tickers)-i)/max(rate,1e-9)/60:.0f}min")
    log(f"INTRADAY DONE ok={ok} fail={fail} elapsed={(time.time()-t0)/60:.1f}min")


if __name__ == "__main__":
    main()
