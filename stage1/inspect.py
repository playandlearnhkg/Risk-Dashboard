"""
stage1.inspect — read local bar files and report what they actually are.

Use this when the 5-minute bars already exist on disk and their provenance is
not fully known. It reads each file, works out the things the manifest has to
declare, and writes a draft data/manifest.yaml so none of it has to be guessed.

    python -m stage1.inspect data/raw/*.csv --emit-manifest data/manifest.yaml

It reports, per file:
  - which columns map to the canonical schema
  - the timestamp form (epoch / offset-aware ISO / naive) and a timezone read
  - whether bars are open- or close-labelled
  - the session window actually present, and bars per session
  - inferred tick size
  - fingerprints of upstream resampling: forward-filled bars, zero-range bars,
    grid holes, and bins that appear to span the overnight gap

Nothing here decides anything. It describes. The validator still has to pass.
"""

from __future__ import annotations

import argparse
import glob
import pathlib
import sys

import numpy as np
import pandas as pd

from stage1 import io as s1io

# Modal session-start minute -> what timezone the naive stamps are really in.
# 09:30 New York is 13:30 UTC in summer, 14:30 UTC in winter.
# Both open- and close-labelled variants, since a close-labelled file's first
# stamp sits one bar later than the session open.
NAIVE_TZ_HINTS = {
    9 * 60 + 30: "America/New_York",
    9 * 60 + 35: "America/New_York",
    13 * 60 + 30: "UTC",
    13 * 60 + 35: "UTC",
    14 * 60 + 30: "UTC",
    14 * 60 + 35: "UTC",
}


def _epoch_unit(v: float) -> str:
    """
    Classify an epoch integer by magnitude: seconds, milliseconds,
    microseconds or nanoseconds.

    For any date between 2000 and 2030 the four scales are separated by three
    orders of magnitude each, so magnitude identifies the unit unambiguously.
    Assuming "big number means milliseconds" misreads a microsecond stamp as
    milliseconds and lands the whole series in the year 51969 - which is
    obvious once plotted and invisible in a summary statistic.
    """
    av = abs(v)
    if av < 1e11:
        return "epoch_s"
    if av < 1e14:
        return "epoch_ms"
    if av < 1e17:
        return "epoch_us"
    return "epoch_ns"


def read_any(path: pathlib.Path) -> pd.DataFrame:
    if path.suffix.lower() in (".parquet", ".pq"):
        return pd.read_parquet(path)
    return pd.read_csv(path)


def timestamp_form(raw: pd.Series) -> str:
    if pd.api.types.is_datetime64_any_dtype(raw):
        return "datetime64_tz_aware" if getattr(raw.dtype, "tz", None) else "datetime64_naive"
    if pd.api.types.is_integer_dtype(raw) or pd.api.types.is_float_dtype(raw):
        return _epoch_unit(float(pd.Series(raw).dropna().iloc[0]))
    sample = str(pd.Series(raw).dropna().astype(str).iloc[0]).strip()
    if sample.endswith("Z") or s1io.OFFSET_RE.search(sample):
        return "iso_offset_aware"
    return "iso_naive"


def parse_index(raw: pd.Series, form: str) -> pd.DatetimeIndex:
    """Parse without assuming a timezone — that is what we are trying to learn."""
    if form.startswith("epoch"):
        unit = form.split("_")[1]
        return pd.DatetimeIndex(
            pd.to_datetime(raw.astype("int64"), unit=unit, utc=True))
    if form in ("iso_offset_aware", "datetime64_tz_aware"):
        return pd.DatetimeIndex(pd.to_datetime(raw, format="mixed", utc=True))
    return pd.DatetimeIndex(pd.to_datetime(raw, format="mixed"))


def describe(path: pathlib.Path, bar_minutes: int) -> dict:
    df = read_any(path)
    out: dict = {"file": path.name, "rows": len(df),
                 "symbol": path.stem.split("_")[0].upper()}

    try:
        mapping = s1io._resolve_columns(df)
    except ValueError as exc:
        out["error"] = str(exc)
        return out
    out["column_map"] = {k: v for k, v in mapping.items()}

    form = timestamp_form(df[mapping["timestamp"]])
    out["timestamp_form"] = form
    idx = parse_index(df[mapping["timestamp"]], form)

    # For anything anchored to UTC, read the session in New York time; naive
    # stamps are examined as-is and the modal session start tells us the zone.
    if idx.tz is not None:
        local = idx.tz_convert("America/New_York")
        out["timezone_read"] = "America/New_York (converted from UTC anchor)"
    else:
        local = idx
        minutes = local.hour * 60 + local.minute
        modal_start = int(pd.Series(minutes, index=local)
                          .groupby(local.normalize()).min().mode().iloc[0])
        hint = NAIVE_TZ_HINTS.get(modal_start)
        out["timezone_read"] = (
            f"naive stamps, modal session start {modal_start // 60:02d}:"
            f"{modal_start % 60:02d} -> looks like {hint or 'UNRECOGNISED'}"
        )
        out["timezone_guess"] = hint

    # .to_numpy() is load-bearing. Handing pandas a Series that still carries
    # the file's RangeIndex, against a DatetimeIndex, makes it ALIGN the two -
    # nothing matches, every price becomes NaN, and every price-based
    # diagnostic below then reports a cheerful zero. Raw arrays have no index
    # to align, so the values land positionally as intended.
    cols = {c: pd.to_numeric(df[mapping[c]], errors="coerce").to_numpy()
            for c in ("open", "high", "low", "close")}
    if "volume" in mapping:
        cols["volume"] = pd.to_numeric(df[mapping["volume"]],
                                       errors="coerce").to_numpy()
    # Sort only after every column is attached, so rows stay together.
    frame = pd.DataFrame(cols, index=local).sort_index()

    out["duplicate_stamps"] = int(frame.index.duplicated().sum())
    frame = frame[~frame.index.duplicated(keep="first")]

    minutes = frame.index.hour * 60 + frame.index.minute
    sessions = frame.index.normalize()
    by_session = pd.Series(minutes, index=frame.index).groupby(sessions)

    out["first"], out["last"] = str(frame.index[0]), str(frame.index[-1])
    out["sessions"] = int(sessions.nunique())

    modal_start = int(by_session.min().mode().iloc[0])
    modal_end = int(by_session.max().mode().iloc[0])
    out["session_window_observed"] = (
        f"{modal_start // 60:02d}:{modal_start % 60:02d}"
        f" -> {modal_end // 60:02d}:{modal_end % 60:02d}"
    )
    out["has_extended_hours"] = bool(modal_start < 9 * 60 + 30 or modal_end >= 16 * 60)

    # Bar label: 15:55 last => open-labelled; 16:00 last => close-labelled.
    if modal_end == 16 * 60 - bar_minutes:
        out["bar_label"] = "open"
    elif modal_end == 16 * 60:
        out["bar_label"] = "close"
    else:
        out["bar_label"] = "indeterminate"

    rth = frame[(minutes >= 9 * 60 + 30) & (minutes < 16 * 60)]
    out["rows_rth"] = len(rth)
    if rth.empty:
        out["error"] = "no rows inside 09:30-16:00; check the timezone read above"
        return out

    per_session = rth.groupby(rth.index.normalize()).size()
    out["bars_per_session_mode"] = int(per_session.mode().iloc[0])
    out["sessions_below_mode"] = int((per_session < out["bars_per_session_mode"]).sum())

    out["inferred_tick"] = s1io.infer_tick_size(rth)

    # --- upstream resampling fingerprints ----------------------------------
    ohlc = rth[["open", "high", "low", "close"]]
    same = ohlc.eq(ohlc.shift()).all(axis=1)
    out["repeated_ohlc"] = int((same & same.shift(fill_value=False)).sum())
    out["zero_range"] = int(((rth["high"] - rth["low"]) == 0).sum())
    if "volume" in rth:
        out["zero_volume"] = int((rth["volume"] == 0).sum())

    rsess = rth.index.normalize()
    span = rth.groupby(rsess).apply(
        lambda g: int((g.index[-1] - g.index[0]).total_seconds() // 60 // bar_minutes) + 1,
        include_groups=False)
    out["grid_holes"] = int((span - rth.groupby(rsess).size()).clip(lower=0).sum())
    out["grid_hole_fraction"] = out["grid_holes"] / max(1, int(span.sum()))

    s_first = rth.groupby(rsess)["open"].first()
    s_last = rth.groupby(rsess)["close"].last()
    carry = int((s_first == s_last.shift()).sum())
    out["session_open_equals_prior_close"] = carry
    out["carry_fraction"] = carry / max(1, len(s_first) - 1)

    return out


def _print(d: dict) -> None:
    print(f"\n  {d['file']}   ({d.get('rows', 0):,} rows)")
    if "error" in d:
        print(f"    ERROR {d['error']}")
        return
    print(f"    columns          : {d['column_map']}")
    print(f"    timestamp form   : {d['timestamp_form']}")
    print(f"    timezone         : {d['timezone_read']}")
    print(f"    range            : {d['first'][:16]} -> {d['last'][:16]}"
          f"   sessions: {d['sessions']:,}")
    print(f"    session window   : {d['session_window_observed']}"
          f"   extended hours present: {d['has_extended_hours']}")
    print(f"    BAR LABEL        : {d['bar_label']}")
    print(f"    bars/session mode: {d.get('bars_per_session_mode')}"
          f"   below mode: {d.get('sessions_below_mode')}")
    print(f"    inferred tick    : {d.get('inferred_tick', float('nan')):.6g}")
    print(f"    duplicates       : {d['duplicate_stamps']:,}")
    print(f"    grid holes       : {d.get('grid_holes', 0):,}"
          f" ({d.get('grid_hole_fraction', 0):.2%})")
    print(f"    repeated OHLC    : {d.get('repeated_ohlc', 0):,}"
          f"   zero-range: {d.get('zero_range', 0):,}"
          + (f"   zero-volume: {d['zero_volume']:,}" if "zero_volume" in d else ""))
    print(f"    open==prior close: {d.get('session_open_equals_prior_close', 0):,}"
          f" ({d.get('carry_fraction', 0):.1%})")

    for msg in _flags(d):
        print(f"    {msg}")


def _flags(d: dict) -> list[str]:
    msgs = []
    if d.get("bar_label") == "indeterminate":
        msgs.append("FLAG  bar label could not be determined from session ends. "
                    "Resolve this before anything else - it sets the alignment "
                    "of every feature.")
    if d.get("timezone_guess") is None and "naive" in d.get("timestamp_form", ""):
        msgs.append("FLAG  naive timestamps whose session start matches no known "
                    "zone. Establish the timezone from the vendor.")
    if d.get("has_extended_hours"):
        msgs.append("note  extended-hours bars present; they are filtered out, "
                    "no action needed.")
    if d.get("grid_hole_fraction", 0) > 0.02:
        msgs.append(f"FLAG  {d['grid_hole_fraction']:.1%} of the grid is missing. "
                    "Costs sample, not bias - forward returns across a hole are "
                    "dropped by the strict spacing rule.")
    rth = max(1, d.get("rows_rth", 1))
    if d.get("repeated_ohlc", 0) > 0.01 * rth:
        msgs.append("FLAG  many bars repeat the previous OHLC exactly. If the "
                    "source forward-filled empty bars, that geometry is "
                    "fabricated - far worse than a missing bar.")
    if d.get("zero_range", 0) > 0.01 * rth:
        frac = d["zero_range"] / rth
        msgs.append(
            f"FLAG  {frac:.1%} of bars have high == low. Above ~1% on a liquid "
            "name this usually means empty bars were filled with the previous "
            "close rather than left out. Those bars carry no geometry at all, "
            "and the study's 5% degenerate-bar limit applies to them.")
    if d.get("zero_volume", 0) > 0.01 * rth and d.get("zero_range", 0) > 0.01 * rth:
        msgs.append("FLAG  zero-range and zero-volume bars coincide, which is "
                    "the signature of synthetic fill. Prefer a source that "
                    "omits untraded bars over one that invents them.")
    if d.get("carry_fraction", 0) > 0.40:
        msgs.append("FLAG  most sessions open exactly at the prior close. The "
                    "upstream aggregation is probably spanning the overnight gap.")
    return msgs


def emit_manifest(rows: list[dict], path: pathlib.Path, raw_dir: pathlib.Path) -> None:
    entries = []
    for d in rows:
        if "error" in d:
            continue
        tz = d.get("timezone_guess") or "America/New_York"
        tick = d.get("inferred_tick", 0.01)
        tick = 0.01 if not np.isfinite(tick) else round(float(tick), 6)
        entries.append(f"""  - symbol: {d['symbol']}
    path: {raw_dir.name}/{d['file']}
    timezone: {tz}
    bar_label: {d['bar_label']}
    session_start: "09:30"
    session_end: "16:00"
    tick_size: {tick}
    adjustment: multiplicative     # VERIFY with the vendor - not detectable from bars
    vendor: CHANGE_ME
    notes: >-
      Drafted by stage1.inspect from {d['file']}. Bar label detected as
      '{d['bar_label']}'; timestamp form {d['timestamp_form']}.""")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Drafted by stage1.inspect. CHECK EVERY FIELD before running the\n"
        "# validator. tick_size is inferred from observed prices and adjustment\n"
        "# is a placeholder - neither can be read off the bars with certainty.\n"
        "instruments:\n" + "\n".join(entries) + "\n"
    )
    print(f"\n  draft manifest -> {path}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Describe local bar files")
    ap.add_argument("paths", nargs="+", help="files or globs")
    ap.add_argument("--bar-minutes", type=int, default=5)
    ap.add_argument("--emit-manifest", default=None)
    args = ap.parse_args(argv)

    files: list[pathlib.Path] = []
    for p in args.paths:
        matched = sorted(glob.glob(p))
        if matched:
            files += [pathlib.Path(m) for m in matched]
        elif pathlib.Path(p).is_dir():
            files += sorted(pathlib.Path(p).glob("*.csv")) + \
                     sorted(pathlib.Path(p).glob("*.parquet"))
        else:
            files.append(pathlib.Path(p))

    if not files:
        print("no files matched")
        return 1

    print("=" * 78)
    print("STAGE 1 - LOCAL DATA INSPECTION")
    print("=" * 78)

    rows = []
    for f in files:
        try:
            d = describe(f, args.bar_minutes)
        except Exception as exc:                                # noqa: BLE001
            d = {"file": f.name, "error": f"{type(exc).__name__}: {exc}"}
        rows.append(d)
        _print(d)

    if args.emit_manifest:
        emit_manifest(rows, pathlib.Path(args.emit_manifest), files[0].parent)
        print("\n  Next: check the manifest, then")
        print(f"  python -m stage1.validate --manifest {args.emit_manifest} --out data/clean")

    return 1 if any("error" in d for d in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
