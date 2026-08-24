"""
stage1.audit_vendor — audit the Run 1 HF bars against an independent daily feed.

The question this answers is narrow and specific:

    Could Verdict C be an artefact of HF Data Library missing event structure -
    truncated sessions, absent extremes, dropped crisis days - rather than a
    statement about the market?

It computes NO score, NO IC and NO hypothesis test. It compares the daily
envelope implied by the HF 5-minute bars against Yahoo daily OHLC over the same
dates, and reports where they disagree.

    python -m stage1.audit_vendor --data data/clean --out results/audit

Yahoo is fetched through `requests` rather than yfinance: yfinance uses
curl_cffi, which does not honour this environment's proxy CA bundle.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import numpy as np
import pandas as pd
import requests

CHART = "https://query2.finance.yahoo.com/v8/finance/chart/{sym}"
UA = {"User-Agent": "Mozilla/5.0 (compatible; data-audit/1.0)"}

# Sessions the audit must look at by name, regardless of what the screens find.
EVENT_DAYS = [
    "2008-09-15", "2008-09-16", "2008-09-17", "2008-09-18", "2008-09-19",
    "2008-09-22", "2008-09-23", "2008-09-24", "2008-09-25", "2008-09-26",
    "2008-09-29", "2008-09-30", "2008-10-01", "2008-10-02", "2008-10-03",
    "2008-10-06", "2008-10-07", "2008-10-08", "2008-10-09", "2008-10-10",
    "2010-05-06",                      # flash crash
    "2015-08-24",                      # ETF open dislocation
    "2018-02-05",                      # volmageddon
    "2020-03-09", "2020-03-12", "2020-03-16",   # covid limit-down days
]

BIG_MOVE_THRESHOLD = 0.03              # |Yahoo daily return| above this
FULL_SESSION_BARS = 78
HALF_SESSION_BARS = 42


def fetch_yahoo_daily(symbol: str, start: str, end: str,
                      retries: int = 4) -> pd.DataFrame:
    """Daily OHLC from the Yahoo chart API, both raw and adjusted close."""
    p1 = int(pd.Timestamp(start, tz="America/New_York").timestamp())
    p2 = int(pd.Timestamp(end, tz="America/New_York").timestamp()) + 86400

    last = None
    for attempt in range(retries):
        try:
            r = requests.get(
                CHART.format(sym=symbol),
                params={"period1": p1, "period2": p2, "interval": "1d",
                        "events": "div,split", "includeAdjustedClose": "true"},
                headers=UA, timeout=60)
            if r.status_code == 200:
                break
            last = f"HTTP {r.status_code}"
        except Exception as exc:                                # noqa: BLE001
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(2 ** attempt)
    else:
        raise RuntimeError(f"{symbol}: Yahoo fetch failed - {last}")

    res = r.json()["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    out = pd.DataFrame({
        "y_open": q["open"], "y_high": q["high"], "y_low": q["low"],
        "y_close": q["close"], "y_volume": q["volume"],
    })
    adj = res["indicators"].get("adjclose")
    out["y_adjclose"] = adj[0]["adjclose"] if adj else np.nan

    ts = pd.to_datetime(res["timestamp"], unit="s", utc=True)
    out.index = pd.DatetimeIndex(ts).tz_convert("America/New_York").normalize().tz_localize(None)
    out.index.name = "date"
    return out.dropna(subset=["y_close"])


def hf_daily_envelope(bars: pd.DataFrame) -> pd.DataFrame:
    """
    Collapse HF 5-minute RTH bars to a daily envelope.

    Only rows carrying prices count toward n_bars; NaN placeholders on the
    session grid are bars that were never built and are counted separately.
    """
    present = bars["close"].notna()
    day = bars.index.normalize().tz_localize(None)
    g = bars.assign(_day=day, _present=present)

    def agg(chunk: pd.DataFrame) -> pd.Series:
        live = chunk[chunk["_present"]]
        if live.empty:
            return pd.Series({"hf_open": np.nan, "hf_high": np.nan,
                              "hf_low": np.nan, "hf_close": np.nan,
                              "n_bars": 0, "n_grid": len(chunk),
                              "first_stamp": "", "last_stamp": "",
                              "has_0930": False, "zero_range_bars": 0})
        rng = live["high"] - live["low"]
        return pd.Series({
            "hf_open": live["open"].iloc[0],
            "hf_high": live["high"].max(),
            "hf_low": live["low"].min(),
            "hf_close": live["close"].iloc[-1],
            "n_bars": int(len(live)),
            "n_grid": int(len(chunk)),
            "first_stamp": live.index[0].strftime("%H:%M"),
            "last_stamp": live.index[-1].strftime("%H:%M"),
            "has_0930": bool(((live.index.hour == 9) &
                              (live.index.minute == 30)).any()),
            "zero_range_bars": int((rng == 0).sum()),
        })

    out = g.groupby("_day").apply(agg, include_groups=False)
    out.index.name = "date"
    return out


def compare(hf: pd.DataFrame, ya: pd.DataFrame) -> pd.DataFrame:
    """Join the two daily views and compute the disagreement measures."""
    df = hf.join(ya, how="outer")
    df["in_hf"] = df["n_bars"].notna() & (df["n_bars"] > 0)
    df["in_yahoo"] = df["y_close"].notna()

    y_range = df["y_high"] - df["y_low"]
    hf_range = df["hf_high"] - df["hf_low"]
    df["y_range"] = y_range
    df["hf_range"] = hf_range

    # Range capture is the headline: what share of the day's high-low span do
    # the HF bars actually contain? Below 1 means HF never printed the extreme.
    df["range_capture"] = np.where(y_range > 0, hf_range / y_range, np.nan)

    df["high_diff_bp"] = (df["hf_high"] / df["y_high"] - 1.0) * 1e4
    df["low_diff_bp"] = (df["hf_low"] / df["y_low"] - 1.0) * 1e4
    df["close_diff_bp"] = (df["hf_close"] / df["y_close"] - 1.0) * 1e4
    df["open_diff_bp"] = (df["hf_open"] / df["y_open"] - 1.0) * 1e4

    df["y_ret"] = df["y_close"].pct_change()
    df["is_half_day"] = df["n_bars"].between(1, HALF_SESSION_BARS + 4)
    return df


def audit(symbol: str, bars: pd.DataFrame, start: str, end: str) -> dict:
    ya = fetch_yahoo_daily(symbol, start, end)
    ya = ya[(ya.index >= start) & (ya.index <= end)]
    hf = hf_daily_envelope(bars)
    df = compare(hf, ya)

    both = df[df["in_hf"] & df["in_yahoo"]]

    # Which adjustment convention does HF follow? Compare its closes against
    # Yahoo raw and Yahoo adjusted. The prereg still records this as PENDING.
    ratio_raw = (both["hf_close"] / both["y_close"]).median()
    ratio_adj = (both["hf_close"] / both["y_adjclose"]).median()

    summary = {
        "symbol": symbol,
        "sessions_hf": int(df["in_hf"].sum()),
        "sessions_yahoo": int(df["in_yahoo"].sum()),
        "sessions_both": int(len(both)),
        "in_yahoo_not_hf": sorted(
            d.strftime("%Y-%m-%d") for d in df.index[df["in_yahoo"] & ~df["in_hf"]]),
        "in_hf_not_yahoo": sorted(
            d.strftime("%Y-%m-%d") for d in df.index[df["in_hf"] & ~df["in_yahoo"]]),
        "median_range_capture": float(both["range_capture"].median()),
        "mean_range_capture": float(both["range_capture"].mean()),
        "sessions_capture_below_95pct": int((both["range_capture"] < 0.95).sum()),
        "sessions_capture_below_90pct": int((both["range_capture"] < 0.90).sum()),
        "sessions_capture_above_101pct": int((both["range_capture"] > 1.01).sum()),
        "median_close_diff_bp": float(both["close_diff_bp"].median()),
        "hf_close_over_yahoo_raw": float(ratio_raw),
        "hf_close_over_yahoo_adjclose": float(ratio_adj),
        "full_sessions": int((both["n_bars"] == FULL_SESSION_BARS).sum()),
        "short_sessions": int((both["n_bars"] < FULL_SESSION_BARS).sum()),
        "half_days": int(both["is_half_day"].sum()),
        "sessions_missing_0930": int((~both["has_0930"]).sum()),
    }
    return {"summary": summary, "frame": df, "both": both}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Audit HF bars against Yahoo daily")
    ap.add_argument("--data", default="data/clean")
    ap.add_argument("--out", default="results/audit")
    ap.add_argument("--start", default="2006-01-03")
    ap.add_argument("--end", default="2022-02-28")
    args = ap.parse_args(argv)

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    from stage1.dataset import load_clean
    bars = load_clean(args.data)

    results = {}
    for sym, df in sorted(bars.items()):
        print(f"\n=== {sym} ===")
        try:
            res = audit(sym, df, args.start, args.end)
        except Exception as exc:                                # noqa: BLE001
            print(f"  FAILED: {type(exc).__name__}: {exc}")
            continue
        results[sym] = res
        s = res["summary"]
        for k, v in s.items():
            if isinstance(v, list):
                print(f"  {k:<32}: {len(v)} {v[:6]}{' ...' if len(v) > 6 else ''}")
            elif isinstance(v, float):
                print(f"  {k:<32}: {v:.6f}")
            else:
                print(f"  {k:<32}: {v}")
        res["frame"].to_csv(out_dir / f"{sym}_daily_compare.csv")

    with open(out_dir / "audit_summary.json", "w") as fh:
        json.dump({k: v["summary"] for k, v in results.items()}, fh, indent=2)
    print(f"\nwritten -> {out_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
