"""
core/logging_setup.py — Console + file logging, and small console helpers.
==========================================================================

Ingest runs are long and mostly unattended, so the console output is built to
be skimmed: aligned stage banners, a one-line status per step, and a summary
table at the end. The file log keeps the full detail for when something needs
diagnosing after the fact.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_CONFIGURED = False

# ANSI colours, suppressed when stdout is not a terminal so piping to a file
# or a CI log does not fill it with escape sequences.
_TTY = sys.stdout.isatty()


def _c(code: str) -> str:
    return code if _TTY else ""


DIM = _c("\033[2m")
BOLD = _c("\033[1m")
RED = _c("\033[31m")
GREEN = _c("\033[32m")
YELLOW = _c("\033[33m")
BLUE = _c("\033[34m")
RESET = _c("\033[0m")


def setup_logging(level: str = "INFO", log_file: Path | None = None) -> logging.Logger:
    """Configure root logging once; repeat calls are no-ops."""
    global _CONFIGURED
    logger = logging.getLogger("meridian")
    if _CONFIGURED:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(getattr(logging, level.upper(), logging.INFO))
    console.setFormatter(logging.Formatter(f"{DIM}%(asctime)s{RESET} %(message)s",
                                           datefmt="%H:%M:%S"))
    logger.addHandler(console)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)     # file always keeps full detail
        fh.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-8s %(name)s | %(message)s"))
        logger.addHandler(fh)

    # yfinance and urllib3 are extremely chatty at INFO.
    for noisy in ("yfinance", "urllib3", "peewee", "requests"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True
    return logger


def get_logger(name: str = "meridian") -> logging.Logger:
    return logging.getLogger(name if name.startswith("meridian") else f"meridian.{name}")


# --------------------------------------------------------------------------
# Console formatting helpers
# --------------------------------------------------------------------------

def banner(text: str, width: int = 78) -> str:
    return f"\n{BOLD}{'=' * width}\n{text}\n{'=' * width}{RESET}"


def stage(text: str, width: int = 78) -> str:
    return f"\n{BOLD}{BLUE}── {text} {'─' * max(0, width - len(text) - 4)}{RESET}"


def ok(text: str) -> str:
    return f"  {GREEN}✓{RESET} {text}"


def warn(text: str) -> str:
    return f"  {YELLOW}!{RESET} {text}"


def fail(text: str) -> str:
    return f"  {RED}✗{RESET} {text}"


def info(text: str) -> str:
    return f"  {DIM}·{RESET} {text}"


def kv(label: str, value: str, width: int = 26) -> str:
    return f"  {label:<{width}} {BOLD}{value}{RESET}"


def color_for_level(level: str) -> str:
    """Traffic-light colour for a risk level, used by the regime report."""
    return {"low": GREEN, "elevated": YELLOW, "high": RED,
            "risk_on": GREEN, "risk_off": RED, "neutral": YELLOW}.get(level, "")
