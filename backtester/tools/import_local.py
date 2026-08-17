"""
import_local.py -- turn YOUR data files into the engine's parquet format.

The engine loads `{TICKER}_{YYYYMMDD}_{YYYYMMDD}_1m.parquet`, indexed by a
tz-aware UTC `ts`, with float64 open/high/low/close/volume. Almost no
vendor ships exactly that, so this module does the translation once, in
one place, and REPORTS WHAT IT DID rather than guessing silently.

THE ONE RULE: INSPECT BEFORE YOU IMPORT

`--inspect` reads a file and prints what it found -- which column it
believes is the timestamp, what timezone it decided on, and the first
bars rendered in New York time -- and writes NOTHING. A 1-minute bar
file whose timezone is guessed wrong is the single most destructive
error possible here: every "09:35 entry" silently becomes some other
minute, the backtest still runs, and every number it produces is wrong
in a way no summary statistic will reveal. So the timezone is decided by
evidence and shown to you, never assumed.

HOW THE TIMEZONE IS DECIDED

  1 If the timestamps are tz-aware, that is authoritative. Done.
  2 If they are integers, they are epochs; the unit is inferred from
    magnitude (s / ms / us / ns) and re-checked by decoded year.
  3 If they are naive datetimes, they are AMBIGUOUS, and this is where
    data gets silently corrupted. So the file is tested BOTH ways -- as
    UTC and as US/Eastern -- and whichever reading puts the modal
    first-bar-of-day at 09:30 New York wins. That is a real measurement,
    not a preference. If neither reading lands on 09:30, the tool says
    so and refuses to guess: pass --assume-tz explicitly.

WIDE OR LONG

A file holding one ticker needs `--ticker`. A file holding many needs a
ticker column, which is auto-detected, and every ticker is written as its
own parquet. Both are common; neither is assumed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Column aliases seen across common vendors, lowercased for matching.
ALIASES = {
    "ts": ["ts", "timestamp", "datetime", "date_time", "time", "t",
           "window_start", "bar_time", "date"],
    "open": ["open", "o", "openprice", "open_price", "px_open"],
    "high": ["high", "h", "highprice", "high_price", "px_high"],
    "low": ["low", "l", "lowprice", "low_price", "px_low"],
    "close": ["close", "c", "closeprice", "close_price", "px_last", "px_close"],
    "volume": ["volume", "v", "vol", "size", "qty", "quantity"],
    "ticker": ["ticker", "symbol", "sym", "instrument", "asset", "name"],
}
OHLCV = ["open", "high", "low", "close", "volume"]
NY = "America/New_York"


class ImportError_(RuntimeError):
    """Raised instead of writing a file this tool is not sure about."""


# ------------------------------------------------------------------ reading

def read_any(path: Path) -> pd.DataFrame:
    """CSV, TSV or parquet in, DataFrame out. Format from the suffix."""
    s = path.suffix.lower()
    if s in (".parquet", ".pq"):
        return pd.read_parquet(path)
    if s in (".csv", ".txt"):
        return pd.read_csv(path)
    if s in (".tsv",):
        return pd.read_csv(path, sep="\t")
    if s in (".gz",):                       # e.g. .csv.gz
        return pd.read_csv(path, compression="gzip")
    raise ImportError_(f"unsupported file type {s!r}: use csv, tsv or parquet")


def find_column(df: pd.DataFrame, role: str) -> str | None:
    """Match a role to a real column name, case- and space-insensitively."""
    norm = {c.lower().replace(" ", "").replace("_", ""): c for c in df.columns}
    for alias in ALIASES[role]:
        key = alias.replace("_", "")
        if key in norm:
            return norm[key]
    return None


# --------------------------------------------------------------- timestamps

def _epoch_unit(v: pd.Series) -> str:
    mag = int(abs(pd.to_numeric(v.dropna()).iloc[0]))
    return ("ns" if mag >= 10**17 else "us" if mag >= 10**14
            else "ms" if mag >= 10**11 else "s")


def _first_bar_hhmm(idx: pd.DatetimeIndex, tz: str) -> pd.Series:
    """Most common first-bar-of-day clock time in the given timezone."""
    local = idx.tz_convert(tz)
    first = pd.Series(local, index=local).groupby(local.date).min()
    return first.dt.strftime("%H:%M").value_counts()


def to_utc_index(raw: pd.Series, assume_tz: str | None = None
                 ) -> tuple[pd.DatetimeIndex, str]:
    """Return (UTC index, human explanation of how it was decided)."""
    # -- integers: an epoch, unit inferred and year-checked ------------
    if pd.api.types.is_integer_dtype(raw) or pd.api.types.is_float_dtype(raw):
        unit = _epoch_unit(raw)
        idx = pd.DatetimeIndex(pd.to_datetime(raw.astype("int64"), unit=unit,
                                              utc=True), name="ts")
        yr = idx.year
        if yr.min() < 1990 or yr.max() > 2100:
            raise ImportError_(
                f"numeric timestamps read as {unit!r} decode to years "
                f"{yr.min()}..{yr.max()}, which cannot be right. The epoch "
                f"unit is wrong -- inspect the raw values.")
        return idx, f"numeric epoch in {unit}, treated as UTC"

    parsed = pd.to_datetime(raw, errors="coerce")
    if parsed.isna().any():
        bad = int(parsed.isna().sum())
        raise ImportError_(f"{bad} timestamp values could not be parsed")

    # -- already tz-aware: authoritative -------------------------------
    if parsed.dt.tz is not None:
        return (pd.DatetimeIndex(parsed.dt.tz_convert("UTC"), name="ts"),
                f"already tz-aware ({parsed.dt.tz}), converted to UTC")

    # -- naive: the dangerous case. Decide by evidence. ----------------
    if assume_tz:
        idx = pd.DatetimeIndex(parsed.dt.tz_localize(
            assume_tz, ambiguous="NaT", nonexistent="shift_forward"),
            name="ts").tz_convert("UTC")
        return idx, f"naive, localised as {assume_tz} because --assume-tz said so"

    as_utc = pd.DatetimeIndex(parsed.dt.tz_localize("UTC"), name="ts")
    try:
        as_et = pd.DatetimeIndex(parsed.dt.tz_localize(
            NY, ambiguous="NaT", nonexistent="shift_forward"),
            name="ts").tz_convert("UTC")
    except Exception:                        # noqa: BLE001
        as_et = None

    utc_share = _first_bar_hhmm(as_utc, NY)
    utc_hit = float(utc_share.get("09:30", 0)) / max(1, utc_share.sum())
    et_hit = 0.0
    if as_et is not None:
        et_share = _first_bar_hhmm(as_et, NY)
        et_hit = float(et_share.get("09:30", 0)) / max(1, et_share.sum())

    if max(utc_hit, et_hit) < 0.5:
        raise ImportError_(
            f"naive timestamps: neither reading puts the session open at "
            f"09:30 New York (as-UTC {utc_hit:.0%}, as-Eastern {et_hit:.0%}). "
            f"This usually means the file includes pre-market bars, which is "
            f"fine -- rerun with --assume-tz UTC or --assume-tz "
            f"'America/New_York' once you know which it is. Refusing to "
            f"guess, because a wrong timezone silently shifts every entry.")
    if et_hit > utc_hit:
        return as_et, (f"naive, read as US/Eastern -- {et_hit:.0%} of sessions "
                       f"then open at 09:30 NY (vs {utc_hit:.0%} as UTC)")
    return as_utc, (f"naive, read as UTC -- {utc_hit:.0%} of sessions then "
                    f"open at 09:30 NY (vs {et_hit:.0%} as Eastern)")


# ------------------------------------------------------------------ convert

def normalise(df: pd.DataFrame, ticker: str | None,
              assume_tz: str | None) -> tuple[dict[str, pd.DataFrame], str]:
    """Vendor frame -> {ticker: engine frame}, plus an explanation."""
    tcol = find_column(df, "ts")
    if tcol is None:
        raise ImportError_(
            f"no timestamp column found. Looked for {ALIASES['ts']}; "
            f"the file has {list(df.columns)}")
    missing = [r for r in OHLCV if find_column(df, r) is None]
    if missing:
        raise ImportError_(
            f"missing price columns {missing}. The file has "
            f"{list(df.columns)}")

    idx, why = to_utc_index(df[tcol], assume_tz)
    cols = {r: pd.to_numeric(df[find_column(df, r)], errors="coerce")
            for r in OHLCV}
    out = pd.DataFrame(cols).set_axis(idx)

    tick_col = find_column(df, "ticker")
    frames: dict[str, pd.DataFrame] = {}
    if tick_col is not None and df[tick_col].nunique() > 1:
        keys = df[tick_col].astype(str).str.upper().to_numpy()
        for tk in pd.unique(keys):
            frames[tk] = out[keys == tk]
    else:
        name = (ticker or (str(df[tick_col].iloc[0]).upper()
                           if tick_col is not None else None))
        if not name:
            raise ImportError_(
                "this file holds one ticker but has no ticker column; "
                "pass --ticker AAPL")
        frames[name.upper()] = out

    cleaned = {}
    for tk, f in frames.items():
        f = f[~f.index.duplicated(keep="last")].sort_index()
        f = f.dropna(subset=["open", "high", "low", "close"])
        cleaned[tk] = f.astype("float64")
    return cleaned, why


def write_frames(frames: dict[str, pd.DataFrame], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for tk, f in frames.items():
        if f.empty:
            print(f"  {tk}: no usable rows, skipped")
            continue
        a = f.index.min().strftime("%Y%m%d")
        b = f.index.max().strftime("%Y%m%d")
        p = out_dir / f"{tk}_{a}_{b}_1m.parquet"
        f.to_parquet(p)
        written.append(p)
        print(f"  wrote {p.name}  ({len(f):,} bars)")
    return written


# -------------------------------------------------------------------- report

def describe(frames: dict[str, pd.DataFrame], why: str) -> None:
    print(f"\nTIMESTAMP DECISION: {why}\n")
    for tk, f in list(frames.items())[:5]:
        if f.empty:
            print(f"{tk}: no usable rows")
            continue
        ny = f.index.tz_convert(NY)
        hh = _first_bar_hhmm(f.index, NY).head(3)
        print(f"{tk}: {len(f):,} bars   "
              f"{ny.min():%Y-%m-%d %H:%M} .. {ny.max():%Y-%m-%d %H:%M} (NY)")
        print(f"    most common first bar of day (NY): "
              f"{', '.join(f'{k} x{v}' for k, v in hh.items())}")
        print(f"    first 3 rows (NY time):")
        head = f.head(3).copy()
        head.index = head.index.tz_convert(NY)
        for ts, r in head.iterrows():
            print(f"      {ts:%Y-%m-%d %H:%M}  O={r.open:.4f} H={r.high:.4f} "
                  f"L={r.low:.4f} C={r.close:.4f} V={r.volume:,.0f}")
    if len(frames) > 5:
        print(f"... and {len(frames) - 5} more tickers")
    print("\nCHECK THIS: the session open should read 09:30 in NY time.")
    print("If it reads 04:00 or similar, the file includes pre-market bars,")
    print("which is fine -- the loader filters to the regular session.")
    print("If it reads 14:30 or 05:30, the TIMEZONE IS WRONG. Stop and fix it")
    print("with --assume-tz before importing, or every entry will be shifted.")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Convert local bar files into the engine's parquet format.")
    ap.add_argument("files", nargs="+", type=Path,
                    help="input csv/tsv/parquet files (globs allowed)")
    ap.add_argument("--out", type=Path, default=Path("data"),
                    help="output directory (default: data)")
    ap.add_argument("--ticker", help="ticker name, if the file has no "
                                     "ticker column")
    ap.add_argument("--assume-tz", metavar="TZ",
                    help="force naive timestamps to this timezone, e.g. UTC "
                         "or 'America/New_York'. Only needed when the "
                         "automatic check cannot decide")
    ap.add_argument("--inspect", action="store_true",
                    help="report what would be imported and write NOTHING")
    a = ap.parse_args()

    paths: list[Path] = []
    for f in a.files:
        paths.extend(sorted(Path().glob(str(f))) if any(c in str(f)
                     for c in "*?[") else [f])
    if not paths:
        print("no input files matched", file=sys.stderr)
        return 2

    total = 0
    for p in paths:
        if not p.exists():
            print(f"SKIP {p}: not found", file=sys.stderr)
            continue
        print(f"\n=== {p} ===")
        try:
            df = read_any(p)
            frames, why = normalise(df, a.ticker, a.assume_tz)
        except ImportError_ as exc:
            print(f"IMPORT ERROR  {exc}", file=sys.stderr)
            return 2
        describe(frames, why)
        if a.inspect:
            print("\n--inspect: nothing written.")
        else:
            print()
            total += len(write_frames(frames, a.out))

    if not a.inspect:
        print(f"\n{total} parquet file(s) written to {a.out}")
        print("Next: python3 run_backtest.py --config "
              "config/strategies/core_post_earnings.yaml --audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
