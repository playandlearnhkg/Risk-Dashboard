"""
build_marketcap.py — Pull split-adjusted point-in-time shares-outstanding
history from SEC EDGAR for the whole stock universe, one parquet per
ticker. Market cap itself is computed later by multiplying against daily
close (see market_cap.point_in_time_market_cap).

SEC asks for <= 10 requests/second and a descriptive User-Agent; both are
respected here.

Run: python3 lambda_strategy_validation/build_marketcap.py
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from market_cap import fetch_shares_outstanding_history, split_adjust_shares  # noqa: E402

BASE = Path("/home/user/lambda_data")
SHARES_DIR = BASE / "shares"
META_PATH = BASE / "ticker_meta.json"
LOG_PATH = BASE / "build_marketcap.log"

MAX_WORKERS = 4
SLEEP_SECONDS = 0.4  # 4 workers x 0.4s ~= 10 req/s, SEC's stated ceiling


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a") as fh:
        fh.write(line + "\n")


def process(ticker: str) -> tuple[str, str]:
    out = SHARES_DIR / f"{ticker}.parquet"
    if out.exists():
        return ticker, "cached"
    try:
        hist = fetch_shares_outstanding_history(ticker)
        hist["shares_split_adj"] = split_adjust_shares(hist).to_numpy()
        hist["ticker"] = ticker
        hist.to_parquet(out, index=False)
        return ticker, "ok"
    except Exception as exc:  # noqa: BLE001 - record and continue
        return ticker, f"fail: {type(exc).__name__} {exc}"
    finally:
        time.sleep(SLEEP_SECONDS)


def main() -> None:
    SHARES_DIR.mkdir(parents=True, exist_ok=True)
    meta = json.loads(META_PATH.read_text())
    tickers = sorted([t for t, v in meta.items() if v.get("type") == "Stock"])
    log(f"START {len(tickers)} tickers")
    t0 = time.time()
    ok = fail = 0
    failures = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(process, t) for t in tickers]
        for i, fut in enumerate(as_completed(futures), 1):
            ticker, status = fut.result()
            if status.startswith("fail"):
                fail += 1
                failures.append((ticker, status))
            else:
                ok += 1
            if i % 100 == 0 or i == len(tickers):
                log(f"{i}/{len(tickers)} ok={ok} fail={fail}")
    if failures:
        pd.DataFrame(failures, columns=["ticker", "status"]).to_csv(
            BASE / "shares_failures.csv", index=False)
        log(f"failures written ({len(failures)}), e.g. {failures[:5]}")
    log(f"DONE ok={ok} fail={fail} elapsed={(time.time()-t0)/60:.1f}min")


if __name__ == "__main__":
    main()
