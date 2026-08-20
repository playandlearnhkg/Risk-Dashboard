"""
core/status.py — System status written for the dashboard to read.
=================================================================

Meridian and the Streamlit risk-dashboard are separate applications. Rather
than have the dashboard import Meridian's modules (which would couple them and
require the package to be importable from the dashboard's working directory),
Meridian writes a small JSON file and the dashboard reads it.

That keeps the seam a FILE, not an import: the dashboard works whether or not
Meridian has ever run, and Meridian does not care whether a dashboard exists.

Written to `output/system_status.json` by run_data.py and run_regime.py.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Optional

from core.logging_setup import get_logger

log = get_logger("core.status")

STATUS_FILENAME = "system_status.json"


def write_status(cfg, *, providers: Optional[list[tuple[str, str, str, str]]] = None,
                 rate_limit: Optional[dict[str, Any]] = None,
                 price_coverage: Optional[dict[str, Any]] = None,
                 stage_results: Optional[dict[str, str]] = None,
                 run_id: str = "", elapsed_sec: float = 0.0) -> Optional[Path]:
    """
    Merge the given fields into output/system_status.json.

    MERGES rather than overwrites, because run_regime.py and run_data.py both
    write to it and neither knows about the other's fields. A regime run must
    not erase the price-coverage block written by the last ingest.
    """
    try:
        path = cfg.path("paths.output_dir") / STATUS_FILENAME
        existing: dict[str, Any] = {}
        if path.exists():
            try:
                existing = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                existing = {}

        now = dt.datetime.now().isoformat(timespec="seconds")

        if providers is not None:
            existing["providers"] = [
                {"role": role, "requested": requested, "effective": effective,
                 "fell_back": requested != effective, "note": note}
                for role, requested, effective, note in providers
            ]
            # Roles that are constants rather than configurable providers, so
            # the dashboard can show a complete picture of where data is from.
            existing["fixed_sources"] = [
                {"role": "macro", "effective": "FRED"},
                {"role": "sec_filings", "effective": "SEC EDGAR"},
                {"role": "margin_debt", "effective": "FINRA (manual CSV)"},
            ]

        if rate_limit is not None:
            existing["rate_limit"] = rate_limit
            existing["rate_limit"]["checked_at"] = now

        if price_coverage is not None:
            existing["price_coverage"] = price_coverage

        if stage_results is not None:
            existing["last_ingest"] = {
                "run_id": run_id,
                "finished_at": now,
                "elapsed_sec": round(elapsed_sec, 1),
                "stages": stage_results,
            }

        existing["updated_at"] = now
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(existing, indent=2, default=str))
        return path
    except Exception as exc:                       # noqa: BLE001
        # Status reporting must never break an ingest run.
        log.debug("could not write system status: %s", exc)
        return None


def read_status(path: Path) -> dict[str, Any]:
    """Read a status file. Returns {} if absent or unreadable."""
    try:
        if path.exists():
            return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        pass
    return {}
