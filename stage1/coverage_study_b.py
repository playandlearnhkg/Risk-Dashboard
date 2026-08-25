"""
stage1.coverage_study_b — DATA-ONLY coverage screen for the Study B universe.

Scope, fixed before it was written and not to be widened here:

    This module answers "which of these names can Study B even ask its question
    of?" It computes NO DQ statistic, NO IC, NO hypothesis test and NO forward
    return. It reports coverage and validity only, so the operator can lock a
    ticker list before `preregistration-study-B.yaml` is written.

The one place it touches scoring code is `core.candle_features`, and it uses
exactly one column from it — `valid`, the frozen degenerate-bar flag from
`docs/preregistration.yaml`. The score columns are dropped on the next line and
never aggregated. Re-implementing the flag here to avoid touching the module
would have been worse: the gate would then exist in two places and could drift.

    export ELKASSABGIDATA_KEY=...
    python -m stage1.coverage_study_b \
        --tickers SPY IWM TLT GLD XLE UUP EEM IEF SLV FXE USO \
        --out results/study_b_coverage

What each reported column means
-------------------------------
sessions              distinct session dates on the 5-minute RTH grid
missing_0930_rate     share of those sessions with no 09:30 bar at all —
                      the quantity docs/DATA_AUDIT.md measured for SPY/IWM
usable_drop           sessions surviving spec-study-B.md §4 Drop AND carrying a
                      non-degenerate 09:30 bar with a warm prior-session ATR
usable_T2 / usable_T3 usable_drop further reduced to sessions that also carry
                      the closes T2 and T3 need (09:35 + 12:00, 09:35 + 15:55).
                      This is coverage arithmetic, not a target computation:
                      no return is formed, only presence is checked.
invalid_fraction      whole-instrument degenerate-bar fraction, computed the
                      way stage1.validate computes it (warm bars only), against
                      the frozen 5% abort. This is the gate that already
                      rejected TLT, GLD, SLV and FXE in Run 1.
open_invalid_rate     the same flag restricted to the 09:30 bar. Study B lives
                      on that bar alone, so an instrument can pass the
                      whole-instrument gate and still be unusable here — or
                      fail it on afternoon illiquidity while its open is clean.
empty_grid_fraction   NaN placeholder rows left by hf_prepare's incomplete-bin
                      rule, over all grid rows
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

import numpy as np
import pandas as pd

from stage1 import core, hf_prepare

DEFAULT_TICKERS = ["SPY", "IWM", "TLT", "GLD", "XLE", "UUP", "EEM",
                   "IEF", "SLV", "FXE", "USO"]

# The Study B universe as proposed by the operator, 2026-08-25.
PRIMARY = ["SPY", "IWM", "TLT", "GLD", "XLE", "UUP", "EEM"]
RESERVE = ["IEF", "SLV", "FXE", "USO"]

START = "2006-01-03"
END = "2022-02-28"                 # pre-IEX-break, same as Run 1
TICK_SIZE = 0.01

MAX_INVALID_FRACTION = 0.05        # frozen; see docs/preregistration.yaml

OPEN_MIN = 9 * 60 + 30
T_ENTRY_MIN = 9 * 60 + 35          # spec-study-B.md §2: T1 end / T2+T3 start
T2_END_MIN = 12 * 60               # frozen 2026-08-25
T3_END_MIN = 15 * 60 + 55          # frozen 2026-08-25, open-labelled


def _minutes(idx: pd.DatetimeIndex) -> np.ndarray:
    return idx.hour * 60 + idx.minute


def load_bars(ticker: str, clean_dir: pathlib.Path,
              key: str | None) -> tuple[pd.DataFrame, str]:
    """
    Prefer the already-validated Run 1 bars; pull and resample from HF otherwise.

    Both paths end at the same object because the HF path runs the frozen
    hf_prepare rules unchanged — RTH before resample, incomplete bins dropped,
    holes left as NaN, nothing forward-filled.
    """
    parquet = clean_dir / f"{ticker}_5min.parquet"
    if parquet.exists():
        df = pd.read_parquet(parquet)
        if not isinstance(df.index, pd.DatetimeIndex):
            df = df.set_index(pd.DatetimeIndex(df["timestamp"]))
        df = df.sort_index()
        return df, "data/clean (Run 1 validated)"

    if not key:
        raise RuntimeError("ELKASSABGIDATA_KEY not set and no local parquet")

    raw = hf_prepare._normalise_columns(hf_prepare.fetch_bars(ticker, key))
    idx = hf_prepare.to_new_york(raw["timestamp"])
    one_min = raw.drop(columns="timestamp").set_index(idx).sort_index()
    one_min = one_min[~one_min.index.duplicated(keep="first")]

    label = hf_prepare.detect_one_minute_label(one_min.index)
    if label == "close":
        one_min.index = one_min.index - pd.Timedelta(minutes=1)
    elif label == "indeterminate":
        raise ValueError(f"{ticker}: 1-minute bar label indeterminate")

    tz = one_min.index.tz
    one_min = one_min[(one_min.index >= pd.Timestamp(START, tz=tz))
                      & (one_min.index <= pd.Timestamp(END, tz=tz)
                         + pd.Timedelta(days=1))]
    bars, _ = hf_prepare.resample_to_5min(one_min)
    if bars.empty:
        raise ValueError(f"{ticker}: no RTH bars in {START}..{END}")
    return bars, f"HF live pull (1-min label '{label}')"


def coverage(ticker: str, bars: pd.DataFrame, source: str) -> dict:
    bars = bars[(bars.index >= pd.Timestamp(START, tz=bars.index.tz))
                & (bars.index <= pd.Timestamp(END, tz=bars.index.tz)
                   + pd.Timedelta(days=1))]

    feats = core.candle_features(bars, TICK_SIZE)
    # Only the frozen validity flag and the ATR warm-up mask leave this line.
    # DQ / DIR / CONV are dropped here and never aggregated — see module docstring.
    valid = feats["valid"]
    warm = feats["atr_prev"].notna()
    feats = None

    present = bars["close"].notna()
    mins = _minutes(bars.index)
    session = pd.Series(bars.index.normalize(), index=bars.index)

    sessions = session.nunique()

    def at(minute: int) -> pd.Series:
        """Per-session boolean: is a priced bar present at this minute?"""
        sel = mins == minute
        return present[sel].groupby(session[sel]).any().reindex(
            session.unique(), fill_value=False)

    open_present = at(OPEN_MIN)
    entry_present = at(T_ENTRY_MIN)
    t2_present = at(T2_END_MIN)
    t3_present = at(T3_END_MIN)

    sel_open = mins == OPEN_MIN
    open_ok = (valid & warm)[sel_open].groupby(session[sel_open]).any().reindex(
        session.unique(), fill_value=False)

    usable_drop = open_ok
    usable_t2 = usable_drop & entry_present & t2_present
    usable_t3 = usable_drop & entry_present & t3_present

    denom = int(warm.sum())
    invalid_fraction = float((~valid & warm).sum()) / denom if denom else np.nan

    open_warm = int((warm & sel_open).sum())
    open_invalid = int((~valid & warm & sel_open).sum())
    open_invalid_rate = open_invalid / open_warm if open_warm else np.nan

    # Split that rate into its two causes. An absent 09:30 bar and a flat 09:30
    # bar both fail `valid`, but they are different problems: the first is a
    # recording gap the Drop rule handles, the second says the instrument does
    # not trade enough at the open to have geometry at all.
    open_present_warm = int((warm & sel_open & present).sum())
    open_degenerate = int((~valid & warm & sel_open & present).sum())
    open_degenerate_given_present = (
        open_degenerate / open_present_warm if open_present_warm else np.nan)

    # Several candidates were thin ETFs in 2006-2010. If a whole-instrument
    # failure lives entirely in the early years, a later era_start is a
    # different remedy from relaxing the gate — so the two are separated here
    # rather than left for the operator to guess at. Still pure coverage: this
    # is the same validity flag, sliced by calendar year.
    year = pd.Series(bars.index.year, index=bars.index)
    earliest_pass = None
    for y in sorted(year.unique()):
        m = warm & (year >= y)
        d = int(m.sum())
        if d and float((~valid & m).sum()) / d <= MAX_INVALID_FRACTION:
            earliest_pass = int(y)
            break

    return {
        "ticker": ticker,
        "role": "primary" if ticker in PRIMARY else "reserve",
        "source": source,
        "first": str(bars.index[0].date()),
        "last": str(bars.index[-1].date()),
        "sessions": int(sessions),
        "sessions_with_0930": int(open_present.sum()),
        "missing_0930_rate": float(1.0 - open_present.mean()),
        "usable_drop": int(usable_drop.sum()),
        "usable_drop_rate": float(usable_drop.mean()),
        "usable_T2": int(usable_t2.sum()),
        "usable_T3": int(usable_t3.sum()),
        "invalid_fraction": invalid_fraction,
        "gate_5pct": "PASS" if invalid_fraction <= MAX_INVALID_FRACTION else "FAIL",
        "open_invalid_rate": float(open_invalid_rate),
        "open_degen_given_present": float(open_degenerate_given_present),
        "earliest_era_passing_5pct": earliest_pass,
        "empty_grid_fraction": float((~present).mean()),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Study B DATA-ONLY coverage screen (no DQ, no IC)")
    ap.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS)
    ap.add_argument("--clean", default="data/clean")
    ap.add_argument("--out", default="results/study_b_coverage")
    args = ap.parse_args(argv)

    key = os.environ.get("ELKASSABGIDATA_KEY")
    clean_dir = pathlib.Path(args.clean)
    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print("STUDY B — DATA-ONLY COVERAGE SCREEN")
    print(f"  window     : {START} -> {END} (pre-IEX-break)")
    print(f"  computes   : coverage + frozen 5% degenerate gate")
    print(f"  does NOT   : compute DQ, IC, forward returns or any test")
    print("=" * 78)

    rows, failed = [], []
    for t in args.tickers:
        try:
            bars, src = load_bars(t, clean_dir, key)
            rows.append(coverage(t, bars, src))
            print(f"  {t:<5} ok   ({src})")
        except Exception as exc:                                # noqa: BLE001
            print(f"  {t:<5} FAILED — {type(exc).__name__}: {exc}")
            failed.append({"ticker": t, "error": f"{type(exc).__name__}: {exc}"})

    if not rows:
        return 1

    table = pd.DataFrame(rows)
    order = {"primary": 0, "reserve": 1}
    table = table.sort_values(
        ["role", "invalid_fraction"], key=lambda s: s.map(order).fillna(s)
        if s.name == "role" else s)

    show = table[["ticker", "role", "sessions", "missing_0930_rate",
                  "usable_drop", "usable_T2", "usable_T3",
                  "invalid_fraction", "gate_5pct", "open_degen_given_present",
                  "earliest_era_passing_5pct", "empty_grid_fraction"]]
    print()
    print(show.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    table.to_csv(out_dir / "coverage.csv", index=False)
    with open(out_dir / "coverage.json", "w") as fh:
        json.dump({"window": [START, END], "rows": rows, "failed": failed},
                  fh, indent=2)
    print(f"\n  written -> {out_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
