"""
Generate synthetic Stage 1 fixture data in the canonical CSV schema.

Produces bars with NO predictability, so the whole chain should end in
"no useful predictivity" — which is exactly what a smoke test of this pipeline
should demonstrate. Used to verify the CLIs end to end without real data.

    python tests/make_fixture.py --out data/raw --sessions 600
"""

from __future__ import annotations

import argparse
import pathlib

import numpy as np
import pandas as pd

from stage1 import core

# Distinct seeds and drifts so the instruments are not identical, and a
# correlation term so K_eff has something real to measure.
INSTRUMENTS = {
    "SPY": dict(seed=101, drift_per_bar=0.004, tick=0.01),
    "TLT": dict(seed=202, drift_per_bar=-0.001, tick=0.01),
    "GLD": dict(seed=303, drift_per_bar=0.002, tick=0.01),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/raw")
    ap.add_argument("--sessions", type=int, default=600)
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    entries = []
    for sym, cfg in INSTRUMENTS.items():
        df = core.synthetic_bars(
            n_sessions=args.sessions,
            bars_per_session=78,
            tick=cfg["tick"],
            seed=cfg["seed"],
            drift_per_bar=cfg["drift_per_bar"],
        )
        rng = np.random.default_rng(cfg["seed"] + 1)
        df["volume"] = rng.integers(1_000, 500_000, size=len(df))

        # Emit ISO 8601 with an explicit offset - the preferred input form.
        stamped = df.copy()
        stamped.index = stamped.index.tz_localize("America/New_York")
        stamped = stamped.reset_index(names="timestamp")
        stamped["timestamp"] = stamped["timestamp"].map(lambda t: t.isoformat())

        path = out / f"{sym}_5min.csv"
        stamped.to_csv(path, index=False)
        print(f"  wrote {path}  ({len(stamped):,} rows)")

        entries.append(f"""  - symbol: {sym}
    path: raw/{sym}_5min.csv
    timezone: America/New_York
    bar_label: open
    session_start: "09:30"
    session_end: "16:00"
    tick_size: {cfg['tick']}
    adjustment: multiplicative
    vendor: synthetic_fixture""")

    manifest = out.parent / "manifest.yaml"
    manifest.write_text(
        "# Stage 1 data manifest - synthetic fixture.\n"
        "# Replace with your real instruments; every field is verified by\n"
        "# stage1.validate, which aborts on any mismatch.\n"
        "instruments:\n" + "\n".join(entries) + "\n"
    )
    print(f"  wrote {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
