"""
futu_daily_pull.py -- pull daily OHLCV from Futu OpenD for volume validation.

WHY DAILY AND NOT 5-MINUTE
  The question we are answering is not "does Futu volume equal HF volume".
  The High Volume filter is a RATIO -- c1_volume against the trailing
  20-session same-slot mean -- so any internally consistent volume
  definition gives the same answer. What breaks the filter is a
  DISCONTINUITY in the definition, and we already found one in the HF
  series: the 2022-03-01 IEX consolidated-tape change rescales volume by
  roughly 35x, which is what destroyed the ADV/ADTV liquidity screen.

  A step change of that size is visible in DAILY volume. Daily K-lines
  carry 20 years of history (intraday carries 8), cost the same one
  quota unit per stock, and cover the full 2015-2025 window. So the
  cheap test and the complete test are the same test.

  Only if this stage says the HF volume series is broken do we need to
  spend quota on 5-minute bars, and then only for the post-2018 events
  Futu can actually serve.

QUOTA
  Futu charges 1 history-K-line quota per stock per rolling 30 days,
  regardless of how many periods or date ranges you request for that
  stock. The allowance is asset-tiered (100 for an account-opened user,
  300 at HKD 10k, more above). This script checks the remaining quota
  before it starts and refuses to begin a run it cannot finish, rather
  than burning half the allowance and stopping.

ADJUSTMENT
  Default is AuType.NONE -- unadjusted. Forward adjustment rescales
  volume for splits, which would paper over exactly the kind of level
  shift we are looking for. Split handling belongs downstream, on a
  series we can see raw.

RUN THIS ON THE MACHINE WHERE OpenD IS LOGGED IN:

    python3 futu_daily_pull.py --tickers data/futu_priority_tickers.txt \
                               --start 2014-06-01 --out futu_daily.csv

    # trim to a smaller quota tier
    python3 futu_daily_pull.py --tickers ... --limit 100 --out futu_daily.csv

Only futu-api is required; this script does not import anything from the
repo so it can be copied out on its own.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

try:
    from futu import AuType, KLType, OpenQuoteContext, RET_OK
except ImportError:
    sys.exit("futu-api is not installed. Run: pip3 install futu-api")

# 60 requests per 30 seconds. Pace to ~1.8 req/s with headroom; each
# ticker costs one request per page and long histories page several times.
REQ_INTERVAL = 0.6
PAGE_SIZE = 1000


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def read_tickers(path: Path, limit: int | None) -> list[str]:
    codes = [ln.strip() for ln in path.read_text().splitlines() if ln.strip()]
    codes = [c if "." in c else f"US.{c}" for c in codes]
    return codes[:limit] if limit else codes


def check_quota(ctx, need: int) -> None:
    ret, data = ctx.get_history_kl_quota(get_detail=False)
    if ret != RET_OK:
        sys.exit(f"could not read history K-line quota: {data}")
    used, remain = data.get("used_quota"), data.get("remain_quota")
    log(f"history K-line quota: used {used}, remaining {remain}, need {need}")
    if remain is not None and remain < need:
        sys.exit(
            f"remaining quota {remain} < {need} tickers requested.\n"
            f"Re-run with --limit {remain} to stay inside the allowance; the "
            f"rest can be pulled after the 30-day window rolls."
        )


def pull_one(ctx, code: str, start: str, end: str) -> pd.DataFrame | None:
    frames, page_key = [], None
    while True:
        ret, data, page_key = ctx.request_history_kline(
            code, start=start, end=end, ktype=KLType.K_DAY,
            autype=AuType.NONE, max_count=PAGE_SIZE, page_req_key=page_key)
        if ret != RET_OK:
            log(f"  {code}: FAILED -- {data}")
            return None
        frames.append(data)
        time.sleep(REQ_INTERVAL)
        if page_key is None:
            break
    df = pd.concat(frames, ignore_index=True)
    return df if len(df) else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", required=True, type=Path)
    ap.add_argument("--start", default="2014-06-01")
    ap.add_argument("--end", default=None, help="default: today")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=11111)
    ap.add_argument("--out", default="futu_daily.csv")
    a = ap.parse_args()

    end = a.end or time.strftime("%Y-%m-%d")
    codes = read_tickers(a.tickers, a.limit)
    log(f"{len(codes)} tickers, {a.start} -> {end}")

    ctx = OpenQuoteContext(host=a.host, port=a.port)
    try:
        ret, state = ctx.get_global_state()
        if ret != RET_OK:
            sys.exit(f"OpenD not reachable at {a.host}:{a.port}: {state}")
        log(f"OpenD {state['server_ver']}, quote_logined={state['qot_logined']}, "
            f"market_us={state['market_us']}")
        if not state["qot_logined"]:
            sys.exit("OpenD is running but not logged in to quotes.")

        check_quota(ctx, len(codes))

        out, failed = [], []
        for i, code in enumerate(codes, 1):
            df = pull_one(ctx, code, a.start, end)
            if df is None:
                failed.append(code)
                continue
            out.append(df)
            if i % 10 == 0 or i == len(codes):
                log(f"  {i}/{len(codes)} done, {len(failed)} failed")
    finally:
        ctx.close()

    if not out:
        sys.exit("nothing pulled.")
    res = pd.concat(out, ignore_index=True)
    res.to_csv(a.out, index=False)
    log(f"wrote {a.out}: {len(res):,} rows, {res['code'].nunique()} tickers")
    if failed:
        log(f"failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
