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

from stage1 import core, io, provenance

# Abort thresholds, from the pre-registration.
MAX_INVALID_FRACTION = 0.05
MAX_TICK_RATIO = 10.0          # declared vs inferred tick size
MIN_SESSIONS_OPTION_A = 1762   # 250 warm-up + 1260 evaluation + 252 holdout

# Scope of the degenerate-bar gate. PRE-REGISTERED, never passed on a whim.
#
#   WHOLE_INSTRUMENT  Run 1 (docs/preregistration.yaml). An instrument whose
#                     whole-instrument degenerate fraction exceeds 5% is
#                     refused entry outright. This is the DEFAULT and Run 1's
#                     behaviour is unchanged by anything below.
#
#   STUDY_B_SESSION   Study B (docs/preregistration-study-B.yaml,
#                     data.eligibility_rule). Study B reads ONE bar per
#                     session, so admission moves to the session: the E1-E6
#                     rule decides each session individually, and instruments
#                     are admitted by pooled AND per-era eligible rate.
#
# Under STUDY_B_SESSION the whole-instrument fraction is still MEASURED and
# reported - it is simply no longer the admission test, because it is a
# statement about bars this study never reads. The 5% figure itself does not
# move under either scope; only what it is applied to does.
WHOLE_INSTRUMENT = "whole_instrument"
STUDY_B_SESSION = "study_b_session"
GATE_SCOPES = (WHOLE_INSTRUMENT, STUDY_B_SESSION)


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
    missing_bars: int = 0
    invalid_fraction: float = 0.0
    zero_range_bars: int = 0
    repeated_ohlc_runs: int = 0
    zero_volume_bars: int = 0
    suspect_split_gaps: int = 0
    session_open_equals_prior_close: int = 0
    grid_holes: int = 0
    grid_hole_fraction: float = 0.0
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


def audit_instrument(spec: io.InstrumentSpec, bar_minutes: int,
                     gate_scope: str = WHOLE_INSTRUMENT,
                     ) -> tuple[pd.DataFrame, InstrumentAudit]:
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
    # Rows may be NaN placeholders on a reindexed session grid (a bar with no
    # trades). Those are legitimate; only rows carrying prices are checked.
    present = o.notna() & h.notna() & l.notna() & c.notna()
    a.missing_bars = int((~present).sum())
    bad_ohlc = present & ~((l <= np.minimum(o, c)) & (h >= np.maximum(o, c)))
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
        if gate_scope == WHOLE_INSTRUMENT:
            a.errors.append(
                f"{a.invalid_fraction:.1%} of bars are degenerate (limit "
                f"{MAX_INVALID_FRACTION:.0%}); this instrument/timeframe is too "
                f"illiquid for the study"
            )
        else:
            a.warnings.append(
                f"{a.invalid_fraction:.1%} of bars are degenerate, above the "
                f"{MAX_INVALID_FRACTION:.0%} whole-instrument limit. NOT an abort "
                f"under gate_scope='{STUDY_B_SESSION}': admission is per-session "
                f"(E1-E6) plus the pooled and per-era instrument floors in "
                f"docs/preregistration-study-B.yaml. Recorded, not waived - most "
                f"of these bars are midday and afternoon bars Study B never reads."
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

    # --- Provenance of a PRE-AGGREGATED series ------------------------------
    # When the 5-minute bars were built by someone else, the five resampling
    # decisions in DATA_SCHEMA.md 7a were made out of our sight. Two of them
    # leave detectable fingerprints in the bars themselves.

    session_first = df.groupby(sessions)["open"].first()
    session_last = df.groupby(sessions)["close"].last()

    # (a) Did an aggregation bin straddle the overnight gap? If it did, the
    # first bar of a session begins where the previous one ended, so its open
    # equals the prior close far more often than chance allows. A genuine
    # overnight gap almost always moves the price at least one tick.
    # Thresholds are deliberately loose. Genuine boundary-crossing aggregation
    # shows up at near 100%, because EVERY session would carry over. Low-priced
    # instruments collide by rounding alone at up to ~10%, so a tight threshold
    # would fire on clean data and train the reader to ignore it.
    exact_carry = (session_first == session_last.shift())
    a.session_open_equals_prior_close = int(exact_carry.sum())
    carry_frac = a.session_open_equals_prior_close / max(1, len(session_first) - 1)
    if carry_frac > 0.40:
        a.errors.append(
            f"{carry_frac:.0%} of sessions open exactly at the prior close. "
            f"The upstream aggregation is spanning the overnight gap, so the "
            f"first bar of each session is not a 5-minute bar."
        )
    elif carry_frac > 0.15:
        a.warnings.append(
            f"{carry_frac:.0%} of sessions open exactly at the prior close. "
            f"Rounding collisions explain up to ~10% on low-priced names; above "
            f"that, check how the 5-minute bars were built."
        )

    # (b) How much of each session's grid is actually present? Missing bars are
    # not a bias - forward returns across a hole are already NaN by the strict
    # spacing rule - but they cost sample, and heavy holing means the
    # instrument is thin at this timeframe.
    span = df.groupby(sessions).apply(
        lambda g: int((g.index[-1] - g.index[0]).total_seconds() // 60 // bar_minutes) + 1,
        include_groups=False,
    )
    present = df.groupby(sessions).size()
    a.grid_holes = int((span - present).clip(lower=0).sum())
    a.grid_hole_fraction = a.grid_holes / max(1, int(span.sum()))
    if a.grid_hole_fraction > 0.02:
        a.warnings.append(
            f"{a.grid_hole_fraction:.2%} of the session grid is missing "
            f"({a.grid_holes:,} absent bars). Forward returns across a hole are "
            f"correctly dropped, so this costs sample rather than biasing it - "
            f"but Step 2 will show the cost in n_eff."
        )

    # --- Adjustment sanity --------------------------------------------------
    # Overnight gaps beyond ~20% usually mean an unadjusted split.
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
          f"   zero-range: {a.zero_range_bars:,}   empty-grid: {a.missing_bars:,}")
    print(f"    duplicates dropped    : {a.duplicates_dropped:,}"
          f"   repeated OHLC: {a.repeated_ohlc_runs:,}")
    print(f"    grid holes            : {a.grid_holes:,} ({a.grid_hole_fraction:.2%})"
          f"   session open == prior close: {a.session_open_equals_prior_close:,}")
    for w in a.warnings:
        print(f"    WARN  {w}")
    for e in a.errors:
        print(f"    ERROR {e}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Stage 1 Step 1: load and validate")
    ap.add_argument("--manifest", default="data/manifest.yaml")
    ap.add_argument("--out", default="data/clean")
    ap.add_argument("--bar-minutes", type=int, default=5)
    ap.add_argument("--gate-scope", choices=GATE_SCOPES, default=WHOLE_INSTRUMENT,
                    help="scope of the degenerate-bar gate. PRE-REGISTERED: "
                         "'whole_instrument' is Run 1; 'study_b_session' is "
                         "declared in docs/preregistration-study-B.yaml")
    args = ap.parse_args(argv)

    specs = io.load_manifest(args.manifest)
    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 74)
    print("STAGE 1 - STEP 1: DATA VALIDATION")
    print("=" * 74)
    print(f"  manifest: {args.manifest}   instruments: {len(specs)}")
    print(f"  gate scope: {args.gate_scope}")
    if args.gate_scope != WHOLE_INSTRUMENT:
        print("  NOTE: the degenerate-bar gate is scoped per the Study B "
              "pre-registration.\n"
              "  The 5% threshold is unchanged; admission moves to the session.")

    audits, frames, manifest_out = [], {}, []
    for spec in specs:
        df, a = audit_instrument(spec, args.bar_minutes, args.gate_scope)
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
        json.dump({"environment": provenance.environment_stamp(),
                   "instruments": manifest_out,
                   "audits": [asdict(a) for a in audits]}, fh, indent=2)

    print(f"  VALIDATION PASSED for {len(frames)} instrument(s)")
    print(f"  clean bars  -> {out_dir}/")
    print(f"  manifest    -> {stamp}")
    print("\n  Copy the verified values into docs/preregistration.yaml (data section),")
    print("  then set status: FROZEN before running Step 3.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
