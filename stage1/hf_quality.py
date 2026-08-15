"""
stage1.hf_quality — measure the HF Data Library IEX break before trusting it.

The vendor discloses a source break on 2022-03-01 (consolidated tape before,
IEX-only after) and says "volumes not comparable across it". Stage 1 uses no
volume, so the tempting conclusion is that the break does not matter.

That conclusion is wrong until measured. IEX carries a small share of
consolidated volume. If the BARS are built from IEX prints only, then the
high and low of each bar come from a sparse subset of the tape, and every
geometry ratio this study measures - body/range, shadow/range, close location -
is computed on an attenuated range. That is not a volume caveat; it is a change
in the measurement instrument, landing in the middle of the sample.

This script settles it with the vendor's own data-quality variables (18-21 of
the dictionary: gap rate, observed bars, longest gap) computed per trading day,
and compares the pre-break and post-break eras.

    export ELKASSABGIDATA_KEY=...
    python -m stage1.hf_quality --tickers SPY TLT GLD FXE

Decision rule, fixed before looking:
    post-break gap rate materially above pre-break  -> the bars themselves are
    sparse; exclude the post-break era from Stage 1 rather than pooling across
    a change in how the data was made.
"""

from __future__ import annotations

import argparse
import io as _io
import os
import sys

import pandas as pd
import requests

API = "https://api.hfdatalibrary.com/v1"
BREAK_DATE = pd.Timestamp("2022-03-01")

# Pre-registered: more than this much extra gap rate after the break means the
# eras are not the same measurement and must not be pooled.
GAP_RATE_TOLERANCE = 0.02


def fetch(dataset: str, ticker: str, key: str, version: str = "clean") -> pd.DataFrame:
    url = f"{API}/{dataset}/{ticker}?version={version}&via=mcp"
    resp = requests.get(url, headers={"X-API-Key": key}, timeout=300)
    resp.raise_for_status()
    return pd.read_parquet(_io.BytesIO(resp.content))


def _col(df: pd.DataFrame, *candidates: str) -> str | None:
    lowered = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand in lowered:
            return lowered[cand]
    return None


def assess(ticker: str, key: str) -> dict:
    q = fetch("quality", ticker, key)

    date_col = _col(q, "trade_date", "date")
    q[date_col] = pd.to_datetime(q[date_col])
    q = q.sort_values(date_col)

    gap_col = _col(q, "gap_rate", "gaprate")
    obs_col = _col(q, "observed_bars", "traded_bars", "observedbars")
    long_col = _col(q, "longest_gap", "longestgap")

    pre = q[q[date_col] < BREAK_DATE]
    post = q[q[date_col] >= BREAK_DATE]

    def stat(frame, col):
        if col is None or frame.empty:
            return float("nan")
        return float(frame[col].mean())

    out = {
        "ticker": ticker,
        "first": str(q[date_col].min().date()),
        "last": str(q[date_col].max().date()),
        "sessions_total": len(q),
        "sessions_pre": len(pre),
        "sessions_post": len(post),
        "gap_pre": stat(pre, gap_col),
        "gap_post": stat(post, gap_col),
        "obs_pre": stat(pre, obs_col),
        "obs_post": stat(post, obs_col),
        "longest_gap_pre": stat(pre, long_col),
        "longest_gap_post": stat(post, long_col),
    }
    out["gap_delta"] = out["gap_post"] - out["gap_pre"]
    out["break_material"] = (
        pd.notna(out["gap_delta"]) and out["gap_delta"] > GAP_RATE_TOLERANCE
    )
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Measure the HF IEX source break")
    ap.add_argument("--tickers", nargs="+", default=["SPY", "TLT", "GLD", "FXE"])
    args = ap.parse_args(argv)

    key = os.environ.get("ELKASSABGIDATA_KEY")
    if not key:
        print("set ELKASSABGIDATA_KEY in your environment first")
        return 1

    print("=" * 78)
    print("HF DATA LIBRARY - IEX SOURCE BREAK ASSESSMENT")
    print(f"break date: {BREAK_DATE.date()}   gap-rate tolerance: {GAP_RATE_TOLERANCE:.0%}")
    print("=" * 78)

    rows = []
    for t in args.tickers:
        try:
            rows.append(assess(t, key))
        except Exception as exc:                                # noqa: BLE001
            print(f"  {t}: FAILED - {exc}")
    if not rows:
        return 1

    table = pd.DataFrame(rows)
    print()
    print(table[["ticker", "first", "last", "sessions_pre", "sessions_post",
                 "gap_pre", "gap_post", "gap_delta",
                 "obs_pre", "obs_post"]].round(4).to_string(index=False))

    material = table[table["break_material"]]
    print("\n" + "=" * 78)
    if len(material):
        print("  BREAK IS MATERIAL for: " + ", ".join(material["ticker"]))
        print("  The bars themselves are sparser after the break, not just the")
        print("  volumes. Every geometry ratio in Stage 1 is computed on an")
        print("  attenuated range in the post-break era.")
        print("\n  ACTION: restrict Stage 1 to the pre-break consolidated-tape era")
        print("  (--end 2022-02-28 in stage1.hf_prepare). Roughly 16 years of")
        print("  common history remains, against the 1,762 sessions Option A")
        print("  needs, so this costs nothing.")
    else:
        print("  Break not material on these tickers at the pre-registered")
        print("  tolerance. Pooling across it is defensible, but record this")
        print("  table in the pre-registration as the evidence.")
    print("\n  Note: the vendor also discloses a SURVIVOR-BIASED universe")
    print("  pre-2022. Stage 1 names four specific surviving ETFs rather than")
    print("  screening a universe, so no selection is performed on the data -")
    print("  but the result generalises to major liquid ETFs only, never to")
    print("  'US stocks'. Disclose it in the results memo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
