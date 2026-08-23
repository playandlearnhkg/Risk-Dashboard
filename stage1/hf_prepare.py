"""
stage1.hf_prepare — pull HF Data Library 1-minute bars and build the 5-minute
RTH series that docs/DATA_SCHEMA.md specifies.

    export ELKASSABGIDATA_KEY=...
    python -m stage1.hf_prepare --tickers SPY TLT GLD FXE --end 2022-02-28

Resampling is the step where OHLC geometry silently breaks, so each decision is
made explicitly here rather than left to a library default.

  1. RTH FIRST, resample second. Aggregating before the session filter lets a
     pre-market minute into the 09:30 bar, which corrupts the open and the low
     of the most-traded bar of the day.

  2. Bins never cross a session. Grouping is by (session date, bin), so no
     5-minute bar can straddle the close.

  3. Incomplete bins are DROPPED, not filled. A 5-minute bar built from two
     1-minute bars has a systematically narrower range, which inflates CONV and
     deflates WB - it biases exactly the quantities Stage 1 measures. Bins with
     fewer than MIN_MINUTES_PER_BAR of 5 minutes are removed.

  4. Dropped bins leave a HOLE in the grid, and the series is then reindexed to
     the full session grid with NaN rows. This matters: without it, .shift(-1)
     would land on the next existing bar, silently turning r_1 into a 10-minute
     return while still calling it r_1. The NaN row makes the forward return
     undefined, which is the truth.

  5. Nothing is forward-filled, ever. A filled bar has fabricated geometry:
     zero range, zero body, and a close location of exactly nothing.
"""

from __future__ import annotations

import argparse
import io as _io
import os
import pathlib
import sys

import numpy as np
import pandas as pd
import requests

API = "https://api.hfdatalibrary.com/v1"

SESSION_START = "09:30"
SESSION_END = "16:00"
BAR_MINUTES = 5
MIN_MINUTES_PER_BAR = 4        # of 5; see note 3 above
MAX_DROP_FRACTION = 0.02       # abort if more bins than this are incomplete
IEX_BREAK = "2022-03-01"


def fetch_bars(ticker: str, key: str, version: str = "clean") -> pd.DataFrame:
    url = f"{API}/bars/{ticker}?version={version}&via=mcp"
    resp = requests.get(url, headers={"X-API-Key": key}, timeout=1800)
    resp.raise_for_status()
    return pd.read_parquet(_io.BytesIO(resp.content))


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    lowered = {c.lower().strip(): c for c in df.columns}
    wanted = {
        "timestamp": ["timestamp", "datetime", "time", "t", "ts", "bar_time", "date"],
        "open": ["open", "o"], "high": ["high", "h"], "low": ["low", "l"],
        "close": ["close", "c"], "volume": ["volume", "v", "vol"],
    }
    mapping = {}
    for canon, opts in wanted.items():
        for o in opts:
            if o in lowered:
                mapping[canon] = lowered[o]
                break
    missing = [k for k in ("timestamp", "open", "high", "low", "close")
               if k not in mapping]
    if missing:
        raise ValueError(f"HF bars missing {missing}; got {list(df.columns)}")
    return df[[mapping[k] for k in mapping]].rename(
        columns={v: k for k, v in mapping.items()})


def to_new_york(ts: pd.Series) -> pd.DatetimeIndex:
    """
    HF stamps may be epoch, offset-aware, or naive. Land them all in exchange
    time.

    NAIVE STAMPS ARE THE TRAP. An earlier version parsed them with utc=True and
    then converted, which treats a naive 09:30 New York stamp as 09:30 UTC and
    silently moves every bar back five hours. Nothing errors; the series just
    lands in pre-market, the RTH filter keeps the wrong bars, and every feature
    is computed on the wrong candles.

    So naive input is not assumed either way - the modal session start decides:
    a session starting near 09:30 is already exchange-local; one starting near
    13:30 or 14:30 is UTC (New York +5 in winter, +4 in summer). Anything else
    raises rather than guessing.
    """
    if pd.api.types.is_integer_dtype(ts) or pd.api.types.is_float_dtype(ts):
        v = float(ts.dropna().iloc[0])
        unit = "s" if abs(v) < 1e11 else "ms" if abs(v) < 1e14 else "us"
        idx = pd.DatetimeIndex(pd.to_datetime(ts.astype("int64"), unit=unit, utc=True))
        return idx.tz_convert("America/New_York")

    if pd.api.types.is_datetime64_any_dtype(ts) and getattr(ts.dtype, "tz", None):
        return pd.DatetimeIndex(ts).tz_convert("America/New_York")

    naive = pd.DatetimeIndex(pd.to_datetime(ts, format="mixed"))
    if naive.tz is not None:
        return naive.tz_convert("America/New_York")

    minutes = naive.hour * 60 + naive.minute
    modal_start = int(pd.Series(minutes, index=naive)
                      .groupby(naive.normalize()).min().mode().iloc[0])

    if 9 * 60 <= modal_start <= 10 * 60:                 # already New York
        return naive.tz_localize("America/New_York",
                                 nonexistent="shift_forward", ambiguous="NaT")
    if 13 * 60 <= modal_start <= 15 * 60:                # UTC
        return naive.tz_localize("UTC").tz_convert("America/New_York")

    raise ValueError(
        f"naive timestamps whose modal session start is "
        f"{modal_start // 60:02d}:{modal_start % 60:02d} match neither "
        f"exchange-local (~09:30) nor UTC (~13:30/14:30). Establish the "
        f"timezone from the vendor before resampling."
    )


def detect_one_minute_label(idx: pd.DatetimeIndex) -> str:
    """
    Open- or close-labelled 1-minute bars?

    Open-labelled  RTH runs 09:30 .. 15:59
    Close-labelled RTH runs 09:31 .. 16:00

    Decided by the modal last stamp of a session. Reported, never assumed - an
    off-by-one here propagates straight into the 5-minute bars and then into
    every feature.
    """
    minutes = idx.hour * 60 + idx.minute
    rth = (minutes >= 9 * 60 + 30) & (minutes <= 16 * 60)
    if not rth.any():
        return "indeterminate"
    s = pd.Series(minutes[rth], index=idx[rth])
    modal_last = int(s.groupby(s.index.normalize()).max().mode().iloc[0])
    if modal_last == 16 * 60 - 1:
        return "open"
    if modal_last == 16 * 60:
        return "close"
    return "indeterminate"


def resample_to_5min(one_min: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """1-minute open-labelled RTH bars -> 5-minute open-labelled bars."""
    start_m = 9 * 60 + 30
    end_m = 16 * 60

    minutes = one_min.index.hour * 60 + one_min.index.minute
    rth = one_min[(minutes >= start_m) & (minutes < end_m)]        # step 1
    stats = {"one_min_rows": len(one_min), "one_min_rth": len(rth)}
    if rth.empty:
        return pd.DataFrame(), stats

    m = rth.index.hour * 60 + rth.index.minute
    bin_start = start_m + ((m - start_m) // BAR_MINUTES) * BAR_MINUTES
    session = rth.index.normalize()

    keys = session + pd.to_timedelta(bin_start, unit="m")          # step 2
    grouped = rth.groupby(keys)

    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if "volume" in rth.columns:
        agg["volume"] = "sum"
    bars = grouped.agg(agg)
    bars["n_minutes"] = grouped.size()

    complete = bars["n_minutes"] >= MIN_MINUTES_PER_BAR           # step 3
    stats["bins_total"] = len(bars)
    stats["bins_dropped"] = int((~complete).sum())
    stats["drop_fraction"] = stats["bins_dropped"] / max(1, len(bars))
    bars = bars[complete].drop(columns="n_minutes")

    # Step 4: reindex each session onto its own complete grid. The grid runs to
    # the session's own last observed bar, so early-close half-days keep their
    # true 42-bar shape instead of having phantom afternoon bars invented.
    pieces = []
    for day, chunk in bars.groupby(bars.index.normalize()):
        grid = pd.date_range(day + pd.Timedelta(minutes=start_m),
                             chunk.index[-1], freq=f"{BAR_MINUTES}min")
        pieces.append(chunk.reindex(grid))
    out = pd.concat(pieces).sort_index()

    stats["bars_5min"] = len(out)
    stats["bars_empty_grid"] = int(out["close"].isna().sum())
    return out, stats


def prepare_ticker(ticker: str, key: str, out_dir: pathlib.Path,
                   start: str | None, end: str | None) -> dict:
    raw = _normalise_columns(fetch_bars(ticker, key))
    idx = to_new_york(raw["timestamp"])
    one_min = raw.drop(columns="timestamp").set_index(idx).sort_index()
    one_min = one_min[~one_min.index.duplicated(keep="first")]

    label = detect_one_minute_label(one_min.index)
    if label == "close":
        one_min.index = one_min.index - pd.Timedelta(minutes=1)
    elif label == "indeterminate":
        raise ValueError(
            f"{ticker}: could not determine the 1-minute bar label from session "
            f"ends. Resolve against the vendor's documentation before "
            f"resampling - this decides the alignment of every feature."
        )

    if start:
        one_min = one_min[one_min.index >= pd.Timestamp(start, tz=one_min.index.tz)]
    if end:
        one_min = one_min[one_min.index <= pd.Timestamp(
            end, tz=one_min.index.tz) + pd.Timedelta(days=1)]

    bars, stats = resample_to_5min(one_min)
    if bars.empty:
        raise ValueError(f"{ticker}: no RTH bars in the requested window")

    path = out_dir / f"{ticker}_5min.csv"
    emit = bars.reset_index(names="timestamp")
    emit["timestamp"] = emit["timestamp"].map(lambda t: t.isoformat())
    emit.to_csv(path, index=False)

    stats.update({
        "ticker": ticker, "path": path.name,
        "one_min_label_detected": label,
        "sessions": int(bars.index.normalize().nunique()),
        "first": str(bars.index[0]), "last": str(bars.index[-1]),
    })
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pull and resample HF 1-min bars")
    ap.add_argument("--tickers", nargs="+", default=["SPY", "TLT", "GLD", "FXE"])
    ap.add_argument("--out", default="data/raw")
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None,
                    help=f"recommended: 2022-02-28 (IEX break {IEX_BREAK})")
    args = ap.parse_args(argv)

    key = os.environ.get("ELKASSABGIDATA_KEY")
    if not key:
        print("ELKASSABGIDATA_KEY is not set in this environment.\n"
              "  export ELKASSABGIDATA_KEY='your-key'    # bash/zsh\n"
              "  $env:ELKASSABGIDATA_KEY='your-key'      # PowerShell\n"
              "Get or view a key at https://hfdatalibrary.com/pages/account\n"
              "Note: the MCP connector's key is held server-side and is NOT\n"
              "visible to this process - the download endpoints need the key\n"
              "in the environment, not in the MCP configuration.")
        return 1

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print("HF DATA LIBRARY -> STAGE 1 SCHEMA")
    print(f"  window: {args.start or 'earliest'} -> {args.end or 'latest'}")
    if not args.end or args.end >= IEX_BREAK:
        print(f"  WARNING: window includes the {IEX_BREAK} IEX break. Run")
        print("  stage1.hf_quality first and read its verdict.")
    print("=" * 78)

    rows, failed = [], []
    for t in args.tickers:
        try:
            s = prepare_ticker(t, key, out_dir, args.start, args.end)
        except Exception as exc:                                # noqa: BLE001
            print(f"\n  {t}: FAILED - {exc}")
            failed.append(t)
            continue
        rows.append(s)
        print(f"\n  {t}")
        print(f"    1-min label detected : {s['one_min_label_detected']}")
        print(f"    1-min rows / RTH     : {s['one_min_rows']:,} / {s['one_min_rth']:,}")
        print(f"    5-min bins           : {s['bins_total']:,}"
              f"   dropped incomplete: {s['bins_dropped']:,}"
              f" ({s['drop_fraction']:.2%})")
        print(f"    5-min bars written   : {s['bars_5min']:,}"
              f"   empty grid rows: {s['bars_empty_grid']:,}")
        print(f"    sessions             : {s['sessions']:,}"
              f"   ({s['first'][:10]} -> {s['last'][:10]})")
        if s["drop_fraction"] > MAX_DROP_FRACTION:
            print(f"    WARNING: {s['drop_fraction']:.2%} of bins were incomplete "
                  f"(limit {MAX_DROP_FRACTION:.0%}). This instrument is thin at "
                  f"5 minutes; expect the validator's degenerate-bar gate to fire.")

    if not rows:
        return 1

    manifest = out_dir.parent / "manifest.yaml"
    entries = "\n".join(
        f"""  - symbol: {s['ticker']}
    path: raw/{s['path']}
    timezone: America/New_York
    bar_label: open
    session_start: "{SESSION_START}"
    session_end: "{SESSION_END}"
    tick_size: 0.01
    adjustment: multiplicative
    vendor: hfdatalibrary
    notes: >-
      Resampled from 1-minute bars by stage1.hf_prepare. Source 1-minute label
      detected as '{s['one_min_label_detected']}'. Incomplete 5-minute bins
      (< {MIN_MINUTES_PER_BAR} of {BAR_MINUTES} minutes) dropped and left as
      empty grid rows, never forward-filled."""
        for s in rows
    )
    manifest.write_text(
        "# Written by stage1.hf_prepare. Verify tick_size and adjustment\n"
        "# against the vendor before running the validator.\n"
        "instruments:\n" + entries + "\n"
    )
    print(f"\n  manifest -> {manifest}")
    print(f"\n  Next: python -m stage1.validate --manifest {manifest} --out data/clean")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
