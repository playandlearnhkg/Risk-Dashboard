"""
regime/weekly_process.py — The four-step weekly process checklist.
==================================================================

    1. Macro & Volatility / Regime Check
    2. Capital Availability Assessment
    3. Sector Rotation Scan
    4. Opportunity Filter & Edge Review

Steps 1-3 are marked complete automatically when the regime engine runs, since
running it *is* performing them. Step 4 is deliberately manual: reviewing
candidates and articulating why an edge exists is the part that cannot be
automated, and auto-completing it would turn the checklist into theatre.

Completions are recorded in `weekly_process_log` and expire after
`staleness_days`, so the checklist answers "what is due now", not "what has
ever been done".
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Optional

from core.logging_setup import get_logger

log = get_logger("regime.weekly")


@dataclass
class ProcessStep:
    """One checklist step and its current freshness."""

    step_id: str
    order: int
    name: str
    description: str
    staleness_days: int
    auto: bool
    last_completed: Optional[dt.date] = None
    notes: str = ""

    @property
    def days_since(self) -> Optional[int]:
        if self.last_completed is None:
            return None
        return (dt.date.today() - self.last_completed).days

    @property
    def is_current(self) -> bool:
        d = self.days_since
        return d is not None and d <= self.staleness_days

    @property
    def status(self) -> str:
        if self.last_completed is None:
            return "never"
        return "current" if self.is_current else "due"

    @property
    def status_symbol(self) -> str:
        return {"current": "✓", "due": "!", "never": "○"}[self.status]

    @property
    def display_age(self) -> str:
        d = self.days_since
        if d is None:
            return "never run"
        if d == 0:
            return "today"
        if d == 1:
            return "yesterday"
        return f"{d} days ago"


class WeeklyProcess:
    """Loads step definitions from config and tracks completion in the DB."""

    def __init__(self, cfg, db):
        self.cfg = cfg
        self.db = db
        self.steps = self._load_steps()

    def _load_steps(self) -> list[ProcessStep]:
        specs = self.cfg.get("regime.weekly_process.steps", []) or []
        steps = [
            ProcessStep(
                step_id=s["id"],
                order=int(s.get("order", 99)),
                name=s.get("name", s["id"]),
                description=" ".join((s.get("description") or "").split()),
                staleness_days=int(s.get("staleness_days", 7)),
                auto=bool(s.get("auto", False)),
            )
            for s in specs
        ]
        steps.sort(key=lambda s: s.order)
        self._hydrate(steps)
        return steps

    def _hydrate(self, steps: list[ProcessStep]) -> None:
        """Fill in each step's most recent completion from the log."""
        try:
            rows = self.db.query(
                "SELECT step_id, MAX(completed_at) AS completed_at, notes "
                "FROM weekly_process_log GROUP BY step_id"
            )
        except Exception as exc:                       # noqa: BLE001
            log.debug("could not read weekly_process_log: %s", exc)
            return

        latest = {r["step_id"]: r for r in rows}
        for step in steps:
            row = latest.get(step.step_id)
            if not row or not row["completed_at"]:
                continue
            try:
                step.last_completed = dt.date.fromisoformat(row["completed_at"][:10])
                step.notes = row["notes"] or ""
            except ValueError:
                continue

    # -- recording ---------------------------------------------------------

    def mark_complete(self, step_id: str, notes: str = "") -> None:
        """Record a completion for `step_id` as of now."""
        now = dt.datetime.now()
        self.db.upsert_many(
            "weekly_process_log",
            ["step_id", "completed_at", "notes"],
            [(step_id, now.isoformat(timespec="seconds"), notes)],
        )
        for step in self.steps:
            if step.step_id == step_id:
                step.last_completed = now.date()
                step.notes = notes
        log.debug("weekly process step '%s' marked complete", step_id)

    def mark_auto_steps(self, regime_state) -> None:
        """
        Mark the automatable steps complete after a regime run.

        Each note records the actual finding, so the log doubles as a history
        of what the process said each week rather than just that it ran.
        """
        notes = {
            "macro_vol_check": (
                f"{regime_state.regime_label} · composite "
                f"{regime_state.composite_score:.0f}/100 · behaviour "
                f"{regime_state.behavior_score if regime_state.behavior_score is not None else 'n/a'}"
            ),
            "capital_assessment": (
                f"Capital {regime_state.capital_status} · money score "
                f"{regime_state.money_score if regime_state.money_score is not None else 'n/a'}"
            ),
            "sector_rotation": "Sector scan run with the regime engine",
        }
        for step in self.steps:
            if step.auto:
                self.mark_complete(step.step_id, notes.get(step.step_id, "auto"))

    # -- reporting ---------------------------------------------------------

    @property
    def all_current(self) -> bool:
        return all(s.is_current for s in self.steps)

    @property
    def outstanding(self) -> list[ProcessStep]:
        return [s for s in self.steps if not s.is_current]

    def summary(self) -> str:
        done = sum(1 for s in self.steps if s.is_current)
        return f"{done}/{len(self.steps)} steps current"

    def to_dict(self) -> dict:
        return {
            "summary": self.summary(),
            "all_current": self.all_current,
            "steps": [
                {
                    "id": s.step_id,
                    "order": s.order,
                    "name": s.name,
                    "description": s.description,
                    "auto": s.auto,
                    "status": s.status,
                    "last_completed": s.last_completed.isoformat() if s.last_completed else None,
                    "days_since": s.days_since,
                    "display_age": s.display_age,
                    "notes": s.notes,
                }
                for s in self.steps
            ],
        }
