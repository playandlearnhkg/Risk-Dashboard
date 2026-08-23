"""
stage1.provenance — record exactly what produced a result.

Spec 5.6 requires that two independent runs produce byte-identical output.
That is only checkable if the environment is recorded alongside the numbers:
vendors silently revise historical bars, and library upgrades silently change
rank-tie handling and rolling-window edge cases. Without this stamp, an
irreproducible result cannot be told apart from a leaking one.
"""

from __future__ import annotations

import platform
import subprocess
import sys


def git_commit() -> str:
    """Commit of the code that produced the result, with a dirty-tree flag."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
            timeout=10, check=True).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True,
            timeout=10, check=True).stdout.strip()
        return f"{sha}{'-dirty' if dirty else ''}"
    except Exception:                                        # noqa: BLE001
        return "unknown"


def environment_stamp() -> dict:
    """Versions of everything that can change a number without changing code."""
    stamp = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "git_commit": git_commit(),
    }
    for mod in ("numpy", "pandas", "pyarrow", "yaml"):
        try:
            stamp[mod] = __import__(mod).__version__
        except Exception:                                    # noqa: BLE001
            stamp[mod] = "absent"
    return stamp


def format_stamp(stamp: dict) -> str:
    width = max(len(k) for k in stamp)
    return "\n".join(f"    {k:<{width}} : {v}" for k, v in stamp.items())
