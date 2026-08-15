"""
stage1.validate — Step 1 of the execution order: load and validate.

Runs every data-integrity check the spec calls for, prints an audit, and
ABORTS on any red flag. On success it writes the cleaned bars plus a data
manifest recording exactly what was loaded (including a content hash), which
is the descriptive half of the pre-registration.

    python -m stage1.validate --manifest data/manifest.yaml --out data/clean

Nothing downstream may run until this exits 0.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from stage1 import core, io

# Abort thresholds, from the pre-registration.
MAX_INVALID_FRACTION = 0.05
MAX_TICK_RATIO = 10.0          # declared vs inferred tick size
MIN_SESSIONS_OPTION_A = 1762   # 250 warm-up + 1260 evaluation + 252 holdout


@dataclass
class InstrumentAudit:
    symbol: str
    rows_raw: int = 0
    rows_rth: int = 0
    sessions: int = 0
    first: str = ""
    last: str = ""
    bars_per_session_mode: int = 0
    short_sessions: int = 0
    calendar_gaps: int = 0
    duplicates_dropped: int = 0
    unsorted_fixed: bool = False
    declared_bar_label: str = ""
    inferred_bar_label: str = ""
    declared_tick: float = 0.0
    inferred_tick: float = 0.0
    invalid_bars: int = 0
    invalid_fraction: float = 0.0
    zero_range_bars: int = 0
    repeated_ohlc_runs: int = 0
    zero_volume_bars: int = 0
    suspect_split_gaps: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _file_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def audit_instrument(spec: io.InstrumentSpec, bar_minutes: int) -> tuple[pd.DataFrame, InstrumentAudit]:
    """Load one instrument and run every integrity check against it."""
    a = InstrumentAudit(symbol=spec.symbol)

    try:
        df, rep = io.load_bars(spec, bar_minutes=bar_minutes, rth_only=False)
    except Exception as exc:                                  # noqa: BLE001
        a.errors.append(f"load failed: {exc}")
        return pd.DataFrame(), a

    a.rows_raw = rep.rows_raw
    a.duplicates_dropped = rep.duplicates_dropped
    a.unsorted_fixed = rep.unsorted_fixed
    a.declared_bar_label = spec.bar_label
    a.inferred_bar_label = rep.inferred_bar_label or "indeterminate"

    if df.empty:
        a.errors.append("no rows after load")
        return df, a

    # --- Timestamp convention: declared must match inferred -----------------
    if rep.inferred_bar_label is None:
        a.warnings.append(
            "could not infer bar label from session ends; verify manually "
            "against the vendor's documentation before proceeding"
        )
    elif rep.inferred_bar_label != spec.bar_label:
        a.errors.append(
            f"bar_label mismatch: manifest declares '{spec.bar_label}' but the "
            f"data looks '{rep.inferred_bar_label}'. An off-by-one here "
            f"manufactures a fake edge. Resolve before continuing."
        )

    # Normalise to open-labelled, then apply the RTH window.
    df = io.normalise_bar_label(df, spec.bar_label, bar_minutes)
    df = io.filter_rth(df, spec, bar_minutes)
    a.rows_rth = len(df)
    if df.empty:
        a.errors.append("no rows inside the declared RTH window")
        return df, a

    a.first, a.last = str(df.index[0]), str(df.index[-1])
    sessions = df.index.normalize()
    a.sessions = int(sessions.nunique())

    # --- Session shape ------------------------------------------------------
    per_session = df.groupby(sessions).size()
    a.bars_per_session_mode = int(per_session.mode().iloc[0])
    a.short_sessions = int((per_session < a.bars_per_session_mode).sum())

    expected = _expected_bars(spec, bar_minutes)
    if a.bars_per_session_mode != expected:
        a.errors.append(
            f"modal bars/session is {a.bars_per_session_mode}, expected {expected} "
            f"for {spec.session_start}-{spec.session_end} on {bar_minutes}min bars. "
            f"Session window or bar size is misdeclared."
        )

    # Calendar gaps: business days inside the range with no bars at all.
    all_bdays = pd.bdate_range(df.index[0].normalize(), df.index[-1].normalize(),
                               tz=df.index.tz)
    a.calendar_gaps = int(len(set(all_bdays) - set(sessions.unique())))

    if (sessions.dayofweek >= 5).any():
        a.errors.append("weekend timestamps present in an RTH equity session")

    # --- Price sanity -------------------------------------------------------
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    bad_ohlc = ~((l <= np.minimum(o, c)) & (h >= np.maximum(o, c)))
    if bad_ohlc.any():
        a.errors.append(f"{int(bad_ohlc.sum())} bars violate low <= min(O,C) <= max(O,C) <= high")
    if (df[["open", "high", "low", "close"]] <= 0).to_numpy().any():
        a.errors.append("non-positive prices present")

    # --- Tick size ----------------------------------------------------------
    a.declared_tick = spec.tick_size
    a.inferred_tick = io.infer_tick_size(df)
    if np.isfinite(a.inferred_tick) and a.inferred_tick > 0:
        ratio = max(a.declared_tick / a.inferred_tick, a.inferred_tick / a.declared_tick)
        if ratio > MAX_TICK_RATIO:
            a.errors.append(
                f"declared tick {a.declared_tick} is {ratio:.0f}x from the inferred "
                f"{a.inferred_tick:.6g}; the section 1.4 noise floor would be wrong"
            )

    # --- Degenerate bars ----------------------------------------------------
    feats = core.candle_features(df, spec.tick_size)
    warm = feats["atr_prev"].notna()
    a.invalid_bars = int((~feats["valid"] & warm).sum())
    denom = int(warm.sum())
    a.invalid_fraction = a.invalid_bars / denom if denom else 0.0
    a.zero_range_bars = int(((df["high"] - df["low"]) == 0).sum())

    if a.invalid_fraction > MAX_INVALID_FRACTION:
        a.errors.append(
            f"{a.invalid_fraction:.1%} of bars are degenerate (limit "
            f"{MAX_INVALID_FRACTION:.0%}); this instrument/timeframe is too "
            f"illiquid for the study"
        )

    # --- Vendor fill artefacts ---------------------------------------------
    same = (df[["open", "high", "low", "close"]]
            .eq(df[["open", "high", "low", "close"]].shift()).all(axis=1))
    a.repeated_ohlc_runs = int((same & same.shift(fill_value=False)).sum())
    if a.repeated_ohlc_runs > 0.01 * len(df):
        a.warnings.append(
            f"{a.repeated_ohlc_runs} bars repeat the previous OHLC exactly; "
            f"the vendor may be forward-filling empty bars, which fabricates geometry"
        )

    if "volume" in df:
        a.zero_volume_bars = int((df["volume"] == 0).sum())
        if a.zero_volume_bars > 0.02 * len(df):
            a.warnings.append(
                f"{a.zero_volume_bars} zero-volume bars; check whether these are "
                f"synthetic fills"
            )

    # --- Adjustment sanity --------------------------------------------------
    # Overnight gaps beyond ~20% usually mean an unadjusted split.
    session_first = df.groupby(sessions)["open"].first()
    session_last = df.groupby(sessions)["close"].last()
    overnight = (session_first / session_last.shift() - 1.0).abs()
    a.suspect_split_gaps = int((overnight > 0.20).sum())
    if a.suspect_split_gaps:
        a.warnings.append(
            f"{a.suspect_split_gaps} overnight moves exceed 20%; verify the series "
            f"is split-adjusted"
        )

    if spec.adjustment == "additive":
        a.errors.append(
            "additive adjustment corrupts intrabar ratios; only multiplicative "
            "(or unadjusted) series are usable"
        )

    # --- History budget (Option A) -----------------------------------------
    if a.sessions < MIN_SESSIONS_OPTION_A:
        a.warnings.append(
            f"{a.sessions} sessions is short of the {MIN_SESSIONS_OPTION_A} that "
            f"history Option A needs (250 warm-up + 1260 evaluation + 252 holdout). "
            f"Step 2 will decide whether this is fatal."
        )

    return df, a


def _expected_bars(spec: io.InstrumentSpec, bar_minutes: int) -> int:
    start = pd.Timestamp(spec.session_start)
    end = pd.Timestamp(spec.session_end)
    return int((end - start).total_seconds() // 60 // bar_minutes)


def _print_audit(a: InstrumentAudit) -> None:
    print(f"\n  {a.symbol}")
    print(f"    rows raw / RTH        : {a.rows_raw:,} / {a.rows_rth:,}")
    print(f"    sessions              : {a.sessions:,}   ({a.first[:10]} -> {a.last[:10]})")
    print(f"    bars per session mode : {a.bars_per_session_mode}"
          f"   short sessions: {a.short_sessions}   calendar gaps: {a.calendar_gaps}")
    print(f"    bar label decl/infer  : {a.declared_bar_label} / {a.inferred_bar_label}")
    print(f"    tick decl/infer       : {a.declared_tick:g} / {a.inferred_tick:.6g}")
    print(f"    degenerate bars       : {a.invalid_bars:,} ({a.invalid_fraction:.2%})"
          f"   zero-range: {a.zero_range_bars:,}")
    print(f"    duplicates dropped    : {a.duplicates_dropped:,}"
          f"   repeated OHLC: {a.repeated_ohlc_runs:,}")
    for w in a.warnings:
        print(f"    WARN  {w}")
    for e in a.errors:
        print(f"    ERROR {e}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Stage 1 Step 1: load and validate")
    ap.add_argument("--manifest", default="data/manifest.yaml")
    ap.add_argument("--out", default="data/clean")
    ap.add_argument("--bar-minutes", type=int, default=5)
    args = ap.parse_args(argv)

    specs = io.load_manifest(args.manifest)
    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 74)
    print("STAGE 1 - STEP 1: DATA VALIDATION")
    print("=" * 74)
    print(f"  manifest: {args.manifest}   instruments: {len(specs)}")

    audits, frames, manifest_out = [], {}, []
    for spec in specs:
        df, a = audit_instrument(spec, args.bar_minutes)
        audits.append(a)
        _print_audit(a)
        if a.ok and not df.empty:
            frames[spec.symbol] = df
            path = out_dir / f"{spec.symbol}_{args.bar_minutes}min.parquet"
            df.to_parquet(path)
            manifest_out.append({
                "symbol": spec.symbol,
                "clean_path": str(path),
                "source_path": spec.path,
                "source_sha256": _file_hash(spec.path),
                "rows": len(df),
                "sessions": a.sessions,
                "first": a.first,
                "last": a.last,
                "bar_label_verified": a.inferred_bar_label,
                "tick_size": spec.tick_size,
                "timezone": spec.timezone,
                "adjustment": spec.adjustment,
                "vendor": spec.vendor,
            })

    failed = [a.symbol for a in audits if not a.ok]
    print("\n" + "=" * 74)
    if failed:
        print(f"  VALIDATION FAILED for: {', '.join(failed)}")
        print("  Fix the errors above. Nothing downstream may run.")
        return 1

    stamp = out_dir / "data_manifest.json"
    with open(stamp, "w") as fh:
        json.dump({"instruments": manifest_out,
                   "audits": [asdict(a) for a in audits]}, fh, indent=2)

    print(f"  VALIDATION PASSED for {len(frames)} instrument(s)")
    print(f"  clean bars  -> {out_dir}/")
    print(f"  manifest    -> {stamp}")
    print("\n  Copy the verified values into docs/preregistration.yaml (data section),")
    print("  then set status: FROZEN before running Step 3.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
