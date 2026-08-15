"""
stage1.io — canonical bar schema and loader.
============================================

Defines exactly what a Stage 1 input file must contain and loads it into the
canonical in-memory form. Everything that could silently corrupt the study
(timestamp convention, timezone, session filtering) is handled HERE, once,
rather than being re-derived by each analysis module.

Canonical in-memory form:
    pd.DataFrame indexed by a tz-aware DatetimeIndex in the exchange's local
    timezone, sorted ascending, unique, with float columns
    open / high / low / close and optional volume.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field

import re

import numpy as np
import pandas as pd

# Trailing UTC offset such as +00:00, -0500, +05:30.
OFFSET_RE = re.compile(r"[+-]\d{2}:?\d{2}$")

REQUIRED_COLUMNS = ["timestamp", "open", "high", "low", "close"]
OPTIONAL_COLUMNS = ["volume"]

# Column name aliases accepted on load. Anything not listed is rejected rather
# than guessed — a silently mismapped column is worse than a failed load.
ALIASES = {
    "timestamp": ["timestamp", "time", "datetime", "date", "t", "ts", "bar_time"],
    "open": ["open", "o"],
    "high": ["high", "h"],
    "low": ["low", "l"],
    "close": ["close", "c"],
    "volume": ["volume", "v", "vol"],
}


@dataclass
class InstrumentSpec:
    """One instrument's declared metadata, from data/manifest.yaml."""

    symbol: str
    path: str
    timezone: str                      # e.g. "America/New_York"
    bar_label: str                     # "open" | "close" — DECLARED, then verified
    session_start: str                 # "09:30"
    session_end: str                   # "16:00"  (exclusive of the closing print)
    tick_size: float
    adjustment: str                    # "multiplicative" | "additive" | "none"
    vendor: str = "unknown"
    timestamp_unit: str | None = None  # "ms"/"s" if timestamps are epoch ints
    notes: str = ""


@dataclass
class LoadReport:
    """What the loader did, so the validator can assert on it."""

    symbol: str
    rows_raw: int = 0
    rows_after_rth: int = 0
    duplicates_dropped: int = 0
    unsorted_fixed: bool = False
    sessions: int = 0
    first: pd.Timestamp | None = None
    last: pd.Timestamp | None = None
    inferred_bar_label: str | None = None
    problems: list[str] = field(default_factory=list)


def _resolve_columns(df: pd.DataFrame) -> dict[str, str]:
    """Map the file's actual column names onto canonical ones, or fail loudly."""
    lowered = {c.lower().strip(): c for c in df.columns}
    mapping: dict[str, str] = {}
    for canonical, options in ALIASES.items():
        for opt in options:
            if opt in lowered:
                mapping[canonical] = lowered[opt]
                break
    missing = [c for c in REQUIRED_COLUMNS if c not in mapping]
    if missing:
        raise ValueError(
            f"missing required column(s) {missing}; "
            f"file has {list(df.columns)}. Rename them rather than letting the "
            f"loader guess."
        )
    return mapping


def _parse_timestamps(raw: pd.Series, spec: InstrumentSpec) -> pd.DatetimeIndex:
    """
    Produce a tz-aware index in the instrument's local exchange timezone.

    Three accepted input forms, in order of preference:
      1. ISO 8601 with an explicit UTC offset  -> converted to spec.timezone
      2. epoch integers + spec.timestamp_unit  -> read as UTC, converted
      3. naive local wall-clock                -> localised to spec.timezone

    Form 3 is accepted but is the one that hides DST bugs, so the validator
    reports which form was used.
    """
    if spec.timestamp_unit:
        idx = pd.to_datetime(raw.astype("int64"), unit=spec.timestamp_unit, utc=True)
        return pd.DatetimeIndex(idx).tz_convert(spec.timezone)

    # Already-typed datetime columns (parquet) carry their own tz.
    if pd.api.types.is_datetime64_any_dtype(raw):
        idx = pd.DatetimeIndex(raw)
        return (idx.tz_convert(spec.timezone) if idx.tz is not None
                else idx.tz_localize(spec.timezone, nonexistent="raise",
                                     ambiguous="raise"))

    # Strings. Offset-aware input MUST be parsed with utc=True: any series
    # spanning a DST change contains two different offsets (e.g. -05:00 and
    # -04:00), and pandas refuses to build a single naive index from those.
    # Parsing to UTC first preserves the absolute instants, then one
    # tz_convert puts them in exchange-local time with DST handled correctly.
    sample = raw.dropna().astype(str)
    aware = bool(len(sample)) and bool(
        sample.iloc[0].strip().endswith("Z")
        or OFFSET_RE.search(sample.iloc[0].strip())
    )

    if aware:
        idx = pd.DatetimeIndex(pd.to_datetime(raw, format="mixed", utc=True))
        return idx.tz_convert(spec.timezone)

    # Genuinely naive: treat as local wall clock. nonexistent/ambiguous are DST
    # edges and must raise rather than be silently shifted — a shifted bar is a
    # misaligned bar.
    idx = pd.DatetimeIndex(pd.to_datetime(raw, format="mixed"))
    if idx.tz is not None:
        return idx.tz_convert(spec.timezone)
    return idx.tz_localize(spec.timezone, nonexistent="raise", ambiguous="raise")


def infer_bar_label(index: pd.DatetimeIndex, spec: InstrumentSpec,
                    bar_minutes: int) -> str | None:
    """
    Infer whether bars are stamped at their OPEN or their CLOSE, by looking at
    where the last bar of a full session sits relative to the session end.

    Open-labelled : last stamp == session_end - bar_minutes  (e.g. 15:55)
    Close-labelled: last stamp == session_end                 (e.g. 16:00)

    This is cross-checked against the declared value in the manifest. An
    off-by-one here manufactures a spectacular fake edge and is the single most
    likely source of a large false positive in this study, so it is never
    taken on trust from either side — the declaration and the data must agree.
    """
    end = pd.Timestamp(spec.session_end).time()
    end_minutes = end.hour * 60 + end.minute

    local_minutes = index.hour * 60 + index.minute
    by_session = pd.Series(local_minutes, index=index).groupby(index.normalize()).max()
    if by_session.empty:
        return None

    modal_last = int(by_session.mode().iloc[0])
    if modal_last == end_minutes - bar_minutes:
        return "open"
    if modal_last == end_minutes:
        return "close"
    return None


def load_bars(
    spec: InstrumentSpec,
    bar_minutes: int = 5,
    rth_only: bool = True,
) -> tuple[pd.DataFrame, LoadReport]:
    """
    Load one instrument into canonical form.

    Deliberately does NOT repair anything silently. Duplicates are dropped and
    counted; unsorted input is sorted and flagged; everything else that looks
    wrong is recorded in the report for the validator to act on.
    """
    path = pathlib.Path(spec.path)
    if not path.exists():
        raise FileNotFoundError(f"{spec.symbol}: no such file {path}")

    if path.suffix.lower() in (".parquet", ".pq"):
        raw = pd.read_parquet(path)
    else:
        raw = pd.read_csv(path)

    rep = LoadReport(symbol=spec.symbol, rows_raw=len(raw))
    if rep.rows_raw == 0:
        rep.problems.append("file is empty")
        return pd.DataFrame(), rep

    mapping = _resolve_columns(raw)
    idx = _parse_timestamps(raw[mapping["timestamp"]], spec)

    cols = {c: pd.to_numeric(raw[mapping[c]], errors="coerce")
            for c in ["open", "high", "low", "close"] }
    if "volume" in mapping:
        cols["volume"] = pd.to_numeric(raw[mapping["volume"]], errors="coerce")

    df = pd.DataFrame(cols)
    df.index = idx

    if not df.index.is_monotonic_increasing:
        df = df.sort_index(kind="mergesort")
        rep.unsorted_fixed = True

    dup = df.index.duplicated(keep="first")
    if dup.any():
        rep.duplicates_dropped = int(dup.sum())
        df = df[~dup]

    rep.inferred_bar_label = infer_bar_label(df.index, spec, bar_minutes)

    if rth_only:
        df = filter_rth(df, spec, bar_minutes)
    rep.rows_after_rth = len(df)

    if len(df):
        rep.first, rep.last = df.index[0], df.index[-1]
        rep.sessions = int(df.index.normalize().nunique())

    return df, rep


def filter_rth(df: pd.DataFrame, spec: InstrumentSpec,
               bar_minutes: int) -> pd.DataFrame:
    """
    Keep only regular trading hours.

    The window is [session_start, session_end) in OPEN-label terms: for a
    09:30-16:00 session on 5-minute bars the last kept bar is the one stamped
    15:55, which covers 15:55-16:00. Close-labelled data is shifted onto
    open-label terms first (see normalise_bar_label), so this function always
    sees open-labelled stamps.

    Extended-hours bars are excluded by pre-registration. They have a different
    spread, volume and volatility regime, and mixing them in makes the
    time-of-day buckets incoherent.
    """
    start = pd.Timestamp(spec.session_start).time()
    end = pd.Timestamp(spec.session_end).time()
    start_m = start.hour * 60 + start.minute
    end_m = end.hour * 60 + end.minute

    minutes = df.index.hour * 60 + df.index.minute
    keep = (minutes >= start_m) & (minutes <= end_m - bar_minutes)
    return df[keep]


def normalise_bar_label(df: pd.DataFrame, from_label: str,
                        bar_minutes: int) -> pd.DataFrame:
    """
    Convert close-labelled bars to open-labelled, which is what the rest of the
    pipeline assumes.

    A close-labelled bar stamped 09:35 covers 09:30-09:35, so its open label is
    09:30. Getting this backwards shifts every feature one bar relative to its
    target, which is indistinguishable from a genuine edge in the results and
    is why infer_bar_label cross-checks the declaration.
    """
    if from_label == "open":
        return df
    if from_label != "close":
        raise ValueError(f"bar_label must be 'open' or 'close', got {from_label!r}")
    out = df.copy()
    out.index = out.index - pd.Timedelta(minutes=bar_minutes)
    return out


def infer_tick_size(df: pd.DataFrame, sample: int = 20000) -> float:
    """
    Estimate the price increment from the data, to cross-check the declared
    tick size that feeds the section 1.4 noise floor.

    Uses the smallest positive gap between distinct observed prices, which is
    robust enough for a sanity check. A declared tick far from this is usually
    a sign of the wrong instrument spec or of averaged/synthetic prices.
    """
    prices = pd.unique(df[["open", "high", "low", "close"]].to_numpy().ravel())
    prices = np.sort(prices[np.isfinite(prices)])
    if len(prices) < 2:
        return float("nan")
    if len(prices) > sample:
        prices = prices[:: max(1, len(prices) // sample)]
    diffs = np.diff(prices)
    diffs = diffs[diffs > 1e-12]
    return float(np.min(diffs)) if len(diffs) else float("nan")


def load_manifest(path: str | pathlib.Path) -> list[InstrumentSpec]:
    """Read data/manifest.yaml into InstrumentSpec objects."""
    import yaml

    path = pathlib.Path(path)
    with open(path) as fh:
        doc = yaml.safe_load(fh)

    base = path.parent
    specs = []
    for entry in doc["instruments"]:
        entry = dict(entry)
        p = pathlib.Path(entry["path"])
        entry["path"] = str(p if p.is_absolute() else base / p)
        specs.append(InstrumentSpec(**entry))
    return specs
