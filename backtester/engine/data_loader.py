"""
data_loader.py -- read {TICKER}_{YYYYMMDD}_{YYYYMMDD}_1m.parquet files.

CONTRACT
  On disk : DatetimeIndex named "ts", tz-aware UTC, 1-minute bars,
            columns open/high/low/close/volume as float64.
  In memory: the same, sorted, de-duplicated, validated, and optionally
            annotated with session_date / minutes_from_open / regular
            session flags.

FOUR DESIGN DECISIONS WORTH KNOWING

1 VALIDATION IS ON BY DEFAULT AND LOUD. A backtest that silently
  consumes a file with duplicated timestamps, a naive index, or bars
  where high < low will produce plausible-looking nonsense. Every check
  here raises rather than warns, because a warning in a research loop is
  a check that nobody reads. `validate=False` exists for speed once a
  dataset is known good, and it is the caller's problem after that.

2 OVERLAPPING FILES ARE EXPECTED, NOT AN ERROR. Vendors re-issue ranges;
  a ticker may have 2015-2020 and 2019-2025 files sitting side by side.
  The loader reads every file that intersects the requested window and
  resolves duplicate timestamps by keeping the row from the file with
  the LATER end date -- the more recently issued extract -- and reports
  how many rows that affected. Silently keeping "first" would make the
  result depend on directory iteration order.

3 GAPS ARE LEFT AS GAPS. Missing minutes are not reindexed onto a
  complete grid and not forward-filled. A forward-filled bar has a real
  price and zero true volume, and any volume ratio computed over it is
  wrong in a direction that flatters the strategy (a quiet stretch
  becomes a low baseline, so the next real bar looks like a surge).
  Callers that need a dense grid must ask for it explicitly and say what
  volume should be.

4 NO FILTERING ON PRICE OR MARKET CAP HAPPENS HERE. Those are
  point-in-time universe questions that need a separate, as-of data
  source; doing them from the price file alone invites survivorship and
  restatement bias. The loader's job ends at "correct bars for this
  ticker".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from engine.calendar import (is_regular_session, minutes_from_open,
                             session_date)

FILENAME_RE = re.compile(
    r"^(?P<ticker>[A-Za-z0-9.\-]+)_"
    r"(?P<start>\d{8})_(?P<end>\d{8})_"
    r"(?P<bar>\d+[a-z]+)\.parquet$"
)

OHLCV = ("open", "high", "low", "close", "volume")
INDEX_NAME = "ts"


class DataError(Exception):
    """Raised when data on disk violates the loader's contract."""


@dataclass(frozen=True)
class DataFile:
    """One parquet file on disk, with its declared coverage."""
    path: Path
    ticker: str
    start: pd.Timestamp          # inclusive, UTC midnight of declared start
    end: pd.Timestamp            # inclusive, UTC end-of-day of declared end
    bar_size: str

    def covers(self, start: pd.Timestamp | None, end: pd.Timestamp | None) -> bool:
        """Does this file's declared range intersect [start, end]?"""
        if start is not None and self.end < start:
            return False
        if end is not None and self.start > end:
            return False
        return True


def parse_filename(path: Path | str) -> DataFile:
    """Parse {TICKER}_{YYYYMMDD}_{YYYYMMDD}_1m.parquet.

    The declared range is taken from the FILENAME, and treated as a hint
    for file selection only. What is actually loaded is whatever the file
    contains, clipped to the caller's requested window. A filename that
    lies about its contents is a data-quality problem, not something to
    silently trust -- `DataCatalog.audit()` reports the mismatch.
    """
    path = Path(path)
    m = FILENAME_RE.match(path.name)
    if not m:
        raise DataError(
            f"{path.name!r} does not match "
            f"{{TICKER}}_{{YYYYMMDD}}_{{YYYYMMDD}}_{{bar}}.parquet"
        )
    try:
        start = pd.Timestamp(m["start"], tz="UTC")
        # Inclusive end: the last instant of the declared end date.
        end = (pd.Timestamp(m["end"], tz="UTC")
               + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1))
    except ValueError as exc:
        raise DataError(f"{path.name!r} has an unparseable date: {exc}") from exc
    if start > end:
        raise DataError(f"{path.name!r} has start after end")
    return DataFile(path=path, ticker=m["ticker"].upper(), start=start,
                    end=end, bar_size=m["bar"])


def _validate_frame(df: pd.DataFrame, source: str) -> None:
    """Structural and internal-consistency checks. Every failure raises."""
    if df.index.name != INDEX_NAME:
        raise DataError(f"{source}: index must be named {INDEX_NAME!r}, "
                        f"got {df.index.name!r}")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise DataError(f"{source}: index must be a DatetimeIndex")
    if df.index.tz is None:
        raise DataError(f"{source}: index must be tz-aware UTC; a naive index "
                        f"cannot be converted to exchange time unambiguously")
    if str(df.index.tz) not in ("UTC", "utc"):
        raise DataError(f"{source}: index timezone must be UTC, got {df.index.tz}")

    missing = [c for c in OHLCV if c not in df.columns]
    if missing:
        raise DataError(f"{source}: missing columns {missing}")

    if not df.index.is_monotonic_increasing:
        raise DataError(f"{source}: index is not sorted")
    dupes = int(df.index.duplicated().sum())
    if dupes:
        raise DataError(f"{source}: {dupes} duplicate timestamps remain")

    sub = df[list(OHLCV)]
    n_nan = int(sub.isna().to_numpy().sum())
    if n_nan:
        raise DataError(f"{source}: {n_nan} NaN values in OHLCV")

    o, h, l, c, v = (df[k].to_numpy() for k in OHLCV)
    if (h < l).any():
        raise DataError(f"{source}: {(h < l).sum()} bars with high < low")
    # Tolerance absorbs float round-trip noise, not real inconsistency.
    tol = 1e-9
    if (h + tol < o).any() or (h + tol < c).any():
        raise DataError(f"{source}: bars where high is below open or close")
    if (l - tol > o).any() or (l - tol > c).any():
        raise DataError(f"{source}: bars where low is above open or close")
    if (v < 0).any():
        raise DataError(f"{source}: {(v < 0).sum()} bars with negative volume")
    if (df[["open", "high", "low", "close"]] <= 0).to_numpy().any():
        raise DataError(f"{source}: non-positive prices present")


class DataCatalog:
    """Index of the parquet files in a directory, grouped by ticker."""

    def __init__(self, data_dir: Path | str, bar_size: str = "1m") -> None:
        self.data_dir = Path(data_dir)
        if not self.data_dir.is_dir():
            raise DataError(f"data dir not found: {self.data_dir}")
        self.bar_size = bar_size
        self._files: dict[str, list[DataFile]] = {}
        self._skipped: list[tuple[str, str]] = []
        self._scan()

    def _scan(self) -> None:
        for p in sorted(self.data_dir.glob("*.parquet")):
            try:
                f = parse_filename(p)
            except DataError as exc:
                self._skipped.append((p.name, str(exc)))
                continue
            if f.bar_size != self.bar_size:
                continue
            self._files.setdefault(f.ticker, []).append(f)
        # Later-issued extract wins on overlap, so sort by end date.
        for fs in self._files.values():
            fs.sort(key=lambda f: (f.end, f.start))

    @property
    def tickers(self) -> list[str]:
        return sorted(self._files)

    @property
    def skipped(self) -> list[tuple[str, str]]:
        """Files in the directory that did not match the naming contract."""
        return list(self._skipped)

    def files_for(self, ticker: str, start=None, end=None) -> list[DataFile]:
        fs = self._files.get(ticker.upper(), [])
        return [f for f in fs if f.covers(start, end)]

    def audit(self) -> pd.DataFrame:
        """Compare each file's declared range against its actual contents.

        Cheap to run and worth running once on any new dataset: a
        filename whose dates do not match its bars is the kind of thing
        that quietly truncates a backtest at one end.
        """
        rows = []
        for ticker, fs in self._files.items():
            for f in fs:
                idx = pd.read_parquet(f.path, columns=[]).index
                actual_lo = pd.Timestamp(idx.min()) if len(idx) else pd.NaT
                actual_hi = pd.Timestamp(idx.max()) if len(idx) else pd.NaT
                rows.append({
                    "ticker": ticker, "file": f.path.name, "rows": len(idx),
                    "declared_start": f.start, "declared_end": f.end,
                    "actual_start": actual_lo, "actual_end": actual_hi,
                    "starts_late": bool(actual_lo > f.start) if len(idx) else True,
                    "ends_early": bool(actual_hi < f.end) if len(idx) else True,
                })
        return pd.DataFrame(rows).sort_values(["ticker", "file"])


class DataLoader:
    """Loads validated 1-minute bars for one ticker at a time."""

    def __init__(self, data_dir: Path | str, bar_size: str = "1m",
                 validate: bool = True) -> None:
        self.catalog = DataCatalog(data_dir, bar_size=bar_size)
        self.validate = validate

    @property
    def tickers(self) -> list[str]:
        return self.catalog.tickers

    def load(self, ticker: str,
             start: str | pd.Timestamp | None = None,
             end: str | pd.Timestamp | None = None,
             regular_session_only: bool = True,
             annotate: bool = True) -> pd.DataFrame:
        """Return bars for `ticker` within [start, end], UTC-indexed.

        start/end are interpreted as UTC instants. Passing a bare date
        string means UTC midnight, so `end="2025-12-31"` would exclude
        almost the whole final day -- it is therefore snapped to the end
        of that day when no time component is supplied.
        """
        start_ts = _as_utc(start, end_of_day=False)
        end_ts = _as_utc(end, end_of_day=True)

        files = self.catalog.files_for(ticker, start_ts, end_ts)
        if not files:
            raise DataError(f"no {self.catalog.bar_size} files for {ticker!r} "
                            f"covering the requested window")

        parts, provenance = [], []
        for f in files:
            df = pd.read_parquet(f.path)
            df = _normalise(df, f.path.name)
            parts.append(df)
            provenance.append(pd.Series(f.path.name, index=df.index))

        raw = pd.concat(parts)
        src = pd.concat(provenance)
        order = raw.index.argsort(kind="stable")
        raw, src = raw.iloc[order], src.iloc[order]

        # Files are ordered oldest-issued first, so on a duplicate
        # timestamp the LAST occurrence comes from the newest extract.
        dup = raw.index.duplicated(keep="last")
        n_dup = int(dup.sum())
        raw, src = raw[~dup], src[~dup]

        if start_ts is not None:
            raw, src = raw[raw.index >= start_ts], src[src.index >= start_ts]
        if end_ts is not None:
            raw, src = raw[raw.index <= end_ts], src[src.index <= end_ts]

        if raw.empty:
            raise DataError(f"{ticker}: no bars in the requested window")

        if self.validate:
            _validate_frame(raw, f"{ticker} ({len(files)} file(s))")

        if regular_session_only:
            raw = raw[is_regular_session(raw.index).to_numpy()]
            if raw.empty:
                raise DataError(f"{ticker}: no regular-session bars in window")

        if annotate:
            raw = raw.assign(
                session_date=session_date(raw.index).to_numpy(),
                minutes_from_open=minutes_from_open(raw.index).to_numpy(),
            )

        raw.attrs["ticker"] = ticker.upper()
        raw.attrs["source_files"] = [f.path.name for f in files]
        raw.attrs["duplicates_dropped"] = n_dup
        return raw

    def load_many(self, tickers, **kwargs) -> dict[str, pd.DataFrame]:
        """Load several tickers, skipping ones with no usable data.

        Returns a dict rather than a concatenated panel: a single wide
        frame across hundreds of tickers with unaligned session grids
        costs far more memory than it saves, and every downstream step
        here is per-ticker anyway.
        """
        out: dict[str, pd.DataFrame] = {}
        for t in tickers:
            try:
                out[t.upper()] = self.load(t, **kwargs)
            except DataError:
                continue
        return out


def _normalise(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Coerce a freshly-read frame to the in-memory contract."""
    if INDEX_NAME in df.columns:            # index round-tripped as a column
        df = df.set_index(INDEX_NAME)
    df.index.name = INDEX_NAME

    if not isinstance(df.index, pd.DatetimeIndex):
        try:
            df.index = pd.DatetimeIndex(df.index)
        except (TypeError, ValueError) as exc:
            raise DataError(f"{source}: index is not datetime-like") from exc

    if df.index.tz is None:
        # Localising a naive index would be a guess. The contract says
        # UTC on disk; a naive index means the writer dropped it, and
        # assuming UTC here is the least-bad option ONLY if declared.
        raise DataError(
            f"{source}: index is timezone-naive. The file contract requires "
            f"tz-aware UTC. Re-write the file with tz_localize('UTC') rather "
            f"than having the loader guess."
        )
    df.index = df.index.tz_convert("UTC")

    keep = [c for c in OHLCV if c in df.columns]
    df = df[keep].astype("float64")
    return df.sort_index(kind="stable")


def _as_utc(value, end_of_day: bool) -> pd.Timestamp | None:
    """Interpret a user-supplied bound as a UTC instant."""
    if value is None:
        return None
    ts = pd.Timestamp(value)
    bare_date = (ts.hour == 0 and ts.minute == 0
                 and ts.second == 0 and ts.nanosecond == 0)
    ts = ts.tz_localize("UTC") if ts.tz is None else ts.tz_convert("UTC")
    if end_of_day and bare_date:
        ts = ts + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
    return ts
