"""Run every test suite. Exit code is non-zero if any assertion failed."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUITES = ["test_loader_config.py", "test_pit_strategy.py"]


def main() -> int:
    failed = 0
    for s in SUITES:
        print(f"\n{'=' * 60}\n{s}\n{'=' * 60}")
        rc = subprocess.run([sys.executable, str(HERE / s)],
                            cwd=HERE.parent).returncode
        failed += bool(rc)
    print(f"\n{'ALL SUITES PASSED' if not failed else f'{failed} SUITE(S) FAILED'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
