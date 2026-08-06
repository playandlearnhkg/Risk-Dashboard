"""
bench_intraday.py — 1-minute SPY and sector-ETF prices for the opening
window on every event date.

Needed because Sigma's section 2C relative-beta filter, as written, is NOT
tradeable: it compares the stock's T+1 open-to-close return against SPY's
and the sector's, but the stock's open-to-close return is only known at
16:00. Worse, "continuation" is itself defined by the sign of that same
return, so filtering on it conditions on the outcome.

A tradeable version has to use only what is on the screen at the entry
time — e.g. how far SPY has moved from the open by 09:45. That requires
benchmark prices minute by minute, which is what this builds.

Run: ELKASSABGIDATA_KEY=... python3 lambda_strategy_validation/bench_intraday.py
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from build_derived import BARS_URL, fetch_with_retry, log  # noqa: E402

BASE = Path("/home/user/lambda_data")
OUT = BASE / "bench_intraday.parquet"
N_MINUTES = 90
BENCH = ["SPY", "XLK", "XLY", "XLF", "XLI", "XLV", "XLC", "XLP", "XLE",
         "XLB", "XLU", "IYR"]


def main() -> None:
    ev = pd.read_parquet(BASE / "events.parquet", columns=["date"])
    dates = set(pd.to_datetime(ev["date"]).dt.normalize())
    log(f"benchmark intraday for {len(dates):,} event dates")

    frames = []
    for t in BENCH:
        blob = fetch_with_retry(BARS_URL.format(t=t))
        if blob is None:
            log(f"{t}: unavailable")
            continue
        b = pd.read_parquet(io.BytesIO(blob))
        del blob
        b["datetime"] = pd.to_datetime(b["datetime"])
        b = b.set_index("datetime").sort_index()
        b["date"] = b.index.normalize()
        b = b[b["date"].isin(dates)]
        if b.empty:
            log(f"{t}: no matching dates")
            continue
        w = b.between_time("09:30", "11:00", inclusive="left").copy()
        w["minute"] = ((w.index.hour * 60 + w.index.minute) - (9 * 60 + 30)).astype("int16")
        w = w[(w["minute"] >= 0) & (w["minute"] < N_MINUTES)]
        g = w.groupby(["date", "minute"]).agg(close=("Close", "last")).reset_index()
        sess = b.groupby("date").agg(bench_open=("Open", "first"),
                                     bench_close=("Close", "last"))
        g = g.merge(sess, on="date", how="left")
        g["bench"] = t
        frames.append(g)
        log(f"{t}: {len(g):,} rows")

    pd.concat(frames, ignore_index=True).to_parquet(OUT, index=False)
    log(f"wrote {OUT}")


if __name__ == "__main__":
    main()
