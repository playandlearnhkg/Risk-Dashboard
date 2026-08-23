"""
stage1.run_all — execute Stage 1 steps 1 to 5 in order, stopping at the first gate.

    python -m stage1.run_all --manifest data/manifest.yaml --out results/run1

The order is not a convenience. Each step can end the study, and each one is
cheaper than the step after it:

    Step 1  validate   data usable?              -> abort on any red flag
    Step 2  power      enough resolution?        -> Verdict B, stop
    Step 3  gates      pipeline trustworthy?     -> K8 fires, everything void
    Step 5  step5      does the score inform?    -> Verdict C, stop

Running them out of order, or continuing past a failure "just to look", is how
a study talks itself into a result. This driver refuses to do either.

It also refuses to run unless the pre-registration reads FROZEN_ANALYSIS, and
it stamps the environment into the run report so the result is reproducible.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

import yaml

from stage1 import gates, power, provenance, step5, validate

STEPS = {
    1: ("validate", "data usable?", "red flag in the data"),
    2: ("power", "enough statistical resolution?", "VERDICT B - underpowered"),
    3: ("gates", "pipeline trustworthy?", "K8 - pipeline gate failed"),
    5: ("step5", "does the score inform r_1?", "VERDICT C - no useful predictivity"),
}


def check_prereg(path: pathlib.Path) -> tuple[bool, str]:
    if not path.exists():
        return False, f"no pre-registration at {path}"
    doc = yaml.safe_load(path.read_text())
    status = str(doc.get("status", ""))
    if status not in ("FROZEN_ANALYSIS", "FROZEN"):
        return False, (
            f"pre-registration status is '{status}', not FROZEN_ANALYSIS. "
            f"Freeze the analysis half before touching real data - deciding "
            f"what counts as a result after seeing one is the failure this "
            f"whole design exists to prevent."
        )

    src = doc.get("data", {}).get("source", "")
    return True, f"frozen, source declared as '{src}'"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run Stage 1 steps 1-5 in order")
    ap.add_argument("--manifest", default="data/manifest.yaml")
    ap.add_argument("--clean", default="data/clean")
    ap.add_argument("--out", default="results/run1")
    ap.add_argument("--prereg", default="docs/preregistration.yaml")
    ap.add_argument("--target-ic", type=float, default=0.015)
    ap.add_argument("--skip-prereg-check", action="store_true",
                    help="for dry runs on fixture data only; never for a real result")
    args = ap.parse_args(argv)

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    started = dt.datetime.now(dt.timezone.utc)

    stamp = provenance.environment_stamp()
    print("=" * 78)
    print("STAGE 1 - FULL RUN")
    print("=" * 78)
    print(provenance.format_stamp(stamp))

    ok, msg = check_prereg(pathlib.Path(args.prereg))
    print(f"\n  pre-registration : {msg}")
    if not ok and not args.skip_prereg_check:
        print("\n  ABORT. " + msg)
        return 1
    if args.skip_prereg_check:
        print("  WARNING: pre-registration check skipped. This run is a dry run "
              "and its numbers may not be cited as a result.")

    record: dict = {
        "started_utc": started.isoformat(),
        "environment": stamp,
        "prereg": {"path": args.prereg, "ok": ok, "message": msg},
        "steps": [],
    }

    runners = {
        1: lambda: validate.main(["--manifest", args.manifest, "--out", args.clean]),
        2: lambda: power.main(["--data", args.clean,
                               "--target-ic", str(args.target_ic)]),
        3: lambda: gates.main(["--data", args.clean]),
        5: lambda: step5.main(["--data", args.clean,
                               "--out", str(out_dir / "step5")]),
    }

    final = "COMPLETED_THROUGH_STEP_5"
    for n, (name, question, failure) in STEPS.items():
        print("\n" + "=" * 78)
        print(f"STEP {n}: {name} - {question}")
        print("=" * 78)
        try:
            code = runners[n]()
        except Exception as exc:                             # noqa: BLE001
            code = 99
            print(f"\n  EXCEPTION in step {n}: {type(exc).__name__}: {exc}")

        record["steps"].append({"step": n, "name": name, "exit_code": code})

        if code != 0:
            final = f"STOPPED_AT_STEP_{n}"
            print("\n" + "=" * 78)
            print(f"  STOPPED AT STEP {n} ({name}), exit code {code}")
            print(f"  Reason: {failure}")
            if n == 5 and code == 2:
                print("\n  This is a complete, pre-registered result, not a")
                print("  malfunction. Record it and stop; the negative conclusion")
                print("  text is in the pre-registration.")
            elif n == 2 and code == 2:
                print("\n  More instruments will NOT fix a block shortfall. Blocks")
                print("  are calendar periods; breadth widens each block, it does")
                print("  not create more of them. Only more history per")
                print("  instrument does.")
            break

    record["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    record["outcome"] = final
    report = out_dir / "run_report.json"
    report.write_text(json.dumps(record, indent=2))

    print("\n" + "=" * 78)
    print(f"  OUTCOME  : {final}")
    print(f"  report   -> {report}")
    print(f"  elapsed  : {dt.datetime.now(dt.timezone.utc) - started}")
    return 0 if final.startswith("COMPLETED") else 2


if __name__ == "__main__":
    sys.exit(main())
