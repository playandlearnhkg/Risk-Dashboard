"""
build_earnings.py — Pull confirmed historical earnings dates for
2015-01-01..2025-12-31 from Nasdaq's free calendar API, one business day
per request, cached to disk per month so the run is resumable.

Only rows carrying an actual reported EPS are kept (see
earnings_calendar.py for why upcoming-only rows are not trustworthy on
historical dates).

Run: python3 lambda_strategy_validation/build_earnings.py
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from earnings_calendar import fetch_confirmed_earnings  # noqa: E402

BASE = Path("/home/user/lambda_data")
EARN_DIR = BASE / "earnings"
LOG_PATH = BASE / "build_earnings.log"

START, END = "2015-01-01", "2025-12-31"
SLEEP_SECONDS = 0.5   # be polite to a free public endpoint
MAX_WORKERS = 4       # ~5 requests/second in aggregate


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a") as fh:
        fh.write(line + "\n")


def fetch_month(month: pd.Period) -> tuple[str, int]:
    out = EARN_DIR / f"{month}.parquet"
    if out.exists():
        return str(month), -1
    days = pd.bdate_range(month.start_time, min(month.end_time, pd.Timestamp(END)))
    frames = []
    for d in days:
        try:
            frames.append(fetch_confirmed_earnings(d.strftime("%Y-%m-%d")))
        except Exception as exc:  # noqa: BLE001 - log and continue
            log(f"  {d.date()}: {exc}")
        time.sleep(SLEEP_SECONDS)
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    df.to_parquet(out, index=False)
    return str(month), len(df)


def main() -> None:
    EARN_DIR.mkdir(parents=True, exist_ok=True)
    months = list(pd.period_range(START, END, freq="M"))
    log(f"START {len(months)} months, {MAX_WORKERS} workers")
    t0 = time.time()
    done = 0
    # Months are independent, so run a few concurrently. Kept modest
    # (4 workers x 0.5 s spacing ~= 5 req/s) — this is a free public
    # endpoint, not a bulk data feed.
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(fetch_month, m): m for m in months}
        for fut in as_completed(futures):
            month, n = fut.result()
            done += 1
            if n >= 0:
                rate = done / max(time.time() - t0, 1e-9)
                log(f"{month} rows={n} ({done}/{len(months)}, "
                    f"ETA {(len(months)-done)/max(rate,1e-9)/60:.0f}min)")
    log(f"DONE elapsed={(time.time()-t0)/60:.1f}min")


if __name__ == "__main__":
    main()
