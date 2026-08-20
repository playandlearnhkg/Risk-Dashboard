#!/usr/bin/env python3
"""
run_regime.py — Layer 0 entry point. Run this first, every day.
===============================================================

    python3 run_regime.py                  # full report
    python3 run_regime.py --brief          # just the headline
    python3 run_regime.py --json           # machine-readable, for Layer 7
    python3 run_regime.py --complete-step opportunity_filter --notes "..."
    python3 run_regime.py --no-persist     # do not write to the database

Everything downstream is conditional on this layer's output, which is why it
runs first and why its result is persisted: Layer 2 reads the factor
multipliers, Layer 4 reads the sector preferences, Layer 5 reads the regime
label. Running the scoring engine without a current regime read means scoring
against yesterday's world.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.config import load_config                                # noqa: E402
from core.db import Database                                       # noqa: E402
from core.logging_setup import (                                   # noqa: E402
    BOLD, DIM, GREEN, RED, RESET, YELLOW,
    banner, fail, info, kv, ok, setup_logging, stage, warn,
)
from regime.composite import compute_regime, persist                # noqa: E402
from regime.indicators import IndicatorSource                       # noqa: E402
from regime.matrices import (                                       # noqa: E402
    asset_class_preferences, avoid_sectors, favored_sectors, sector_preferences,
)
from regime.weekly_process import WeeklyProcess                     # noqa: E402


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

REGIME_COLOR = {
    "strong_risk_on": GREEN,
    "mild_risk_on": GREEN,
    "neutral": YELLOW,
    "mild_risk_off": YELLOW,
    "strong_risk_off": RED,
}

CAPITAL_COLOR = {"High": GREEN, "Medium": YELLOW, "Low": RED, "Unknown": DIM}


def score_bar(score: float | None, width: int = 24) -> str:
    """Compact 0-100 bar. Colour reinforces the number; it never replaces it."""
    if score is None:
        return f"{DIM}{'·' * width}{RESET}  n/a"
    filled = int(round(score / 100 * width))
    color = GREEN if score >= 60 else (RED if score <= 40 else YELLOW)
    return f"{color}{'█' * filled}{RESET}{DIM}{'░' * (width - filled)}{RESET} {score:5.1f}"


def print_indicators(title: str, readings, coverage: float) -> None:
    print(f"\n  {BOLD}{title}{RESET} {DIM}(coverage {coverage:.0%}){RESET}")
    for r in readings:
        if r.available:
            print(f"    {r.label:<26} {score_bar(r.score, 16)}  "
                  f"{DIM}{r.display:>14}{RESET}  {DIM}{r.note}{RESET}")
        else:
            print(f"    {r.label:<26} {DIM}{'·' * 16}    n/a{RESET}  "
                  f"{YELLOW}{r.error}{RESET}")


def print_report(state, sectors, assets, process, brief: bool = False) -> None:
    color = REGIME_COLOR.get(state.regime_key, "")

    print(banner(f"  MERIDIAN CAPITAL PARTNERS · Capital & Regime · {state.run_date}"))
    print()
    print(f"  {BOLD}{color}{state.regime_label.upper()}{RESET}   "
          f"composite {BOLD}{state.composite_score:.0f}{RESET}/100")
    print(f"  Capital availability: "
          f"{CAPITAL_COLOR.get(state.capital_status, '')}{BOLD}{state.capital_status}{RESET}"
          f"   {DIM}(data coverage {state.coverage:.0%}){RESET}")
    print()
    print(f"  {'Money available':<20} {score_bar(state.money_score)}")
    print(f"  {'Risk-on behaviour':<20} {score_bar(state.behavior_score)}")
    print(f"  {DIM}{'':<20} combined via {state.combination_method} "
          f"→ {state.composite_score:.1f}{RESET}")

    for w in state.warnings:
        print(warn(w))

    if brief:
        return

    # ---- indicator detail --------------------------------------------------
    print(stage("Indicators"))
    print_indicators("Money availability", state.money_readings, state.money_coverage)
    print_indicators("Risk-on / risk-off behaviour", state.behavior_readings,
                     state.behavior_coverage)

    # ---- sectors -----------------------------------------------------------
    print(stage("Sector rotation scan"))
    print(f"  {DIM}{'Sector':<24}{'Matrix':>10}{'Rel str':>10}{'Blended':>10}{RESET}")
    for r in sectors:
        mark = f"{GREEN}★{RESET}" if r.favored else " "
        stance_col = GREEN if r.matrix_score > 0 else (RED if r.matrix_score < 0 else DIM)
        print(f"  {mark} {r.name:<22}{stance_col}{r.matrix_score:>+8}{RESET}"
              f"{r.display_momentum:>10}{r.blended_score or 0:>10.0f}")

    fav = favored_sectors(sectors)
    avoid = avoid_sectors(sectors)
    print()
    print(kv("Favored (hunt longs here)", ", ".join(f"{r.key} {r.name}" for r in fav)))
    print(kv("Underweight (short bias)", ", ".join(f"{r.key} {r.name}" for r in avoid)))

    # ---- asset classes -----------------------------------------------------
    print(stage("Asset class preference"))
    for r in assets:
        stance_col = GREEN if r.matrix_score > 0 else (RED if r.matrix_score < 0 else DIM)
        print(f"  {r.name:<24}{stance_col}{r.matrix_score:>+4}{RESET}  "
              f"{DIM}{r.stance:<20} {r.proxy}{RESET}")

    # ---- factor multipliers ------------------------------------------------
    print(stage("Layer 2 factor weight multipliers"))
    for factor, mult in sorted(state.factor_multipliers.items(),
                               key=lambda kv_: -kv_[1]):
        arrow = "↑" if mult > 1.02 else ("↓" if mult < 0.98 else "·")
        col = GREEN if mult > 1.02 else (RED if mult < 0.98 else DIM)
        print(f"  {factor:<18} {col}{arrow} ×{mult:.2f}{RESET}")

    # ---- weekly process ----------------------------------------------------
    print(stage(f"Weekly process — {process.summary()}"))
    for step in process.steps:
        col = {"current": GREEN, "due": YELLOW, "never": RED}[step.status]
        auto = f"{DIM}auto{RESET}" if step.auto else f"{YELLOW}manual{RESET}"
        print(f"  {col}{step.status_symbol}{RESET} {step.order}. {step.name:<38} "
              f"{DIM}{step.display_age:<14}{RESET}{auto}")
        if step.status != "current" and not step.auto:
            print(f"      {DIM}{step.description}{RESET}")

    if process.outstanding:
        print()
        for step in process.outstanding:
            print(warn(f"Step {step.order} ({step.name}) is due."))

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--brief", action="store_true", help="headline only")
    ap.add_argument("--json", action="store_true", help="emit JSON to stdout")
    ap.add_argument("--no-persist", action="store_true",
                    help="do not write to the database")
    ap.add_argument("--complete-step", metavar="STEP_ID",
                    help="mark a weekly-process step complete (e.g. opportunity_filter)")
    ap.add_argument("--notes", default="", help="notes to store with --complete-step")
    args = ap.parse_args()

    cfg = load_config()
    cfg.ensure_dirs()
    setup_logging(
        level="WARNING" if args.json else cfg.get("logging.level", "INFO"),
        log_file=cfg.path("logging.file") if cfg.get("logging.file") else None,
    )

    db = Database(cfg.path("paths.database"))
    process = WeeklyProcess(cfg, db)

    # A step completion is a bookkeeping action, not an analysis run.
    if args.complete_step:
        valid = {s.step_id for s in process.steps}
        if args.complete_step not in valid:
            print(fail(f"Unknown step '{args.complete_step}'. Valid: {', '.join(sorted(valid))}"))
            return 1
        process.mark_complete(args.complete_step, args.notes)
        print(ok(f"Marked '{args.complete_step}' complete."))
        return 0

    src = IndicatorSource(cfg)
    state = compute_regime(cfg, src)
    sectors = sector_preferences(cfg, state.regime_key, src)
    assets = asset_class_preferences(cfg, state.regime_key)

    if not args.no_persist:
        persist(state, db)
        process.mark_auto_steps(state)

    if args.json:
        payload = state.to_dict()
        payload["sectors"] = [
            {"ticker": r.key, "name": r.name, "matrix_score": r.matrix_score,
             "stance": r.stance, "momentum_pct": r.momentum_pct,
             "blended_score": r.blended_score, "favored": r.favored}
            for r in sectors
        ]
        payload["asset_classes"] = [
            {"key": r.key, "name": r.name, "matrix_score": r.matrix_score,
             "stance": r.stance, "proxy": r.proxy}
            for r in assets
        ]
        payload["weekly_process"] = process.to_dict()
        print(json.dumps(payload, indent=2, default=str))
        return 0

    print_report(state, sectors, assets, process, brief=args.brief)

    # Write the same payload to output/ so Layer 7 and the reporting layer
    # have a stable file to read without re-running the engine.
    if not args.no_persist:
        out = cfg.path("paths.output_dir") / "regime_latest.json"
        payload = state.to_dict()
        payload["sectors"] = [
            {"ticker": r.key, "name": r.name, "matrix_score": r.matrix_score,
             "momentum_pct": r.momentum_pct, "blended_score": r.blended_score,
             "favored": r.favored} for r in sectors
        ]
        payload["asset_classes"] = [
            {"key": r.key, "matrix_score": r.matrix_score, "proxy": r.proxy}
            for r in assets
        ]
        payload["weekly_process"] = process.to_dict()
        out.write_text(json.dumps(payload, indent=2, default=str))
        print(info(f"Wrote {out.relative_to(cfg.root)}"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
