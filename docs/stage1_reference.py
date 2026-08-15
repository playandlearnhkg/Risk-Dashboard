"""
stage1_reference.py — self-test entry point for the Stage 1 numerical core.
===========================================================================

The implementation now lives in `stage1/core.py`, which is the single source of
truth. This file is a thin shim that runs the section 5.6 pipeline gates
against it, so the validated implementation and the implementation actually
used by the CLIs cannot drift apart.

Run:  python docs/stage1_reference.py
      (or, equivalently, python -m stage1.gates --synthetic)

Do not trust output from any faster reimplementation that has not reproduced
the three gates this prints.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from stage1.gates import run_synthetic_gates  # noqa: E402

if __name__ == "__main__":
    result = run_synthetic_gates(verbose=True)
    sys.exit(0 if result["all_gates_pass"] else 1)
