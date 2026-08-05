"""
intraday_timing.py — When is the earnings gap actually priced?

Motivating question: the opening-pattern test enters at 09:45, and by then
the tradeable edge is gone. Is that because no edge exists, or because 15
minutes is already long enough for the information to be absorbed? This
answers it directly by sweeping the entry time minute by minute.

For every event session, using 1-minute bars 09:30-10:00:

  1. ENTRY SWEEP — enter at the close of minute k (k = 1..29), exit at the
     session close, signed in the gap direction, net of the same measured
     spread used everywhere else. If information is absorbed progressively,
     expectancy should decay smoothly with k; if it is absorbed instantly,
     every k looks the same and equally dead.

  2. DRIFT PATH — the average signed cumulative return from the open,
     minute by minute. This shows *where* in the session the move happens
     rather than only whether it nets out.

  3. SHORT-HORIZON EXITS — enter at the open, exit at minute k, to test
     whether a fast scalp captures something a full-session hold gives back.

All inference is the same date-clustered bootstrap used in analysis.py.

Run: python3 lambda_strategy_validation/intraday_timing.py
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd

import analysis as A  # noqa: E402

BASE = Path("/home/user/lambda_data")
INTRADAY_DIR = BASE / "intraday"
EVENTS = BASE / "events.parquet"
OUT_DIR = BASE / "tables"

MAX_MIN = 30


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def load_intraday_for_events(ev: pd.DataFrame) -> pd.DataFrame:
    """Wide frame: one row per event session, m1..m29 closes + session close."""
    want = set(zip(ev["ticker"], ev["date"]))
    frames = []
    files = sorted(INTRADAY_DIR.glob("*.parquet"))
    for i, f in enumerate(files, 1):
        try:
            d = pd.read_parquet(f)
        except Exception:  # noqa: BLE001 - empty/partial file
            continue
        if d.empty:
            continue
        d["date"] = pd.to_datetime(d["date"])
        d = d[[(t, dt) in want for t, dt in zip(d["ticker"], d["date"])]]
        if not d.empty:
            frames.append(d)
        if i % 150 == 0:
            log(f"  loaded {i}/{len(files)} files, kept {sum(len(x) for x in frames):,} rows")
    if not frames:
        raise RuntimeError("no intraday rows matched the event set")
    raw = pd.concat(frames, ignore_index=True)
    wide = raw.pivot_table(index=["ticker", "date"], columns="minute",
                           values="close", aggfunc="last")
    wide.columns = [f"m{int(c)}" for c in wide.columns]
    sess = raw.groupby(["ticker", "date"])[["session_open", "session_close"]].first()
    return wide.join(sess).reset_index()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ev = pd.read_parquet(EVENTS)
    ev["date"] = pd.to_datetime(ev["date"])
    log(f"events: {len(ev):,}")

    wide = load_intraday_for_events(ev)
    log(f"intraday sessions matched: {len(wide):,}")

    df = ev.merge(wide, on=["ticker", "date"], how="inner", suffixes=("", "_id"))
    log(f"joined: {len(df):,}")
    sign = np.where(df["gap_up"], 1.0, -1.0)
    spread_bps = A.spread_series(df)          # full spread, bps
    open_px = df["session_open"].where(df["session_open"].notna(), df["open"])
    close_px = df["session_close"].where(df["session_close"].notna(), df["close"])

    # ---- 1. entry sweep: enter at minute k close, exit at session close ----
    rows = []
    for k in range(1, MAX_MIN):
        col = f"m{k}"
        if col not in df.columns:
            continue
        entry = df[col]
        gross = sign * (close_px / entry - 1.0)
        # One round trip regardless of entry time.
        net = gross - 2.0 * (spread_bps / 2.0 + 2.0) / 1e4
        b = A.clustered_bootstrap(pd.Series(net, index=df.index), df["date"])
        c = A.clustered_bootstrap(pd.Series(np.where(gross > 0, 1.0, 0.0),
                                            index=df.index) - 0.5, df["date"])
        rows.append({"entry_minute": k, "entry_time": f"09:{30+k:02d}",
                     "n": b["n"], "net_bps": b["stat"] * 1e4,
                     "ci_lo_bps": b["lo"] * 1e4, "ci_hi_bps": b["hi"] * 1e4,
                     "p": b["p"], "hit_rate": c["stat"] + 0.5})
    entry_sweep = pd.DataFrame(rows)
    entry_sweep.to_csv(OUT_DIR / "intraday_entry_sweep.csv", index=False)

    # ---- 2. drift path from the open --------------------------------------
    rows = []
    for k in range(1, MAX_MIN):
        col = f"m{k}"
        if col not in df.columns:
            continue
        gross = sign * (df[col] / open_px - 1.0)
        b = A.clustered_bootstrap(pd.Series(gross, index=df.index), df["date"])
        rows.append({"minute": k, "time": f"09:{30+k:02d}",
                     "cum_signed_bps": b["stat"] * 1e4,
                     "ci_lo_bps": b["lo"] * 1e4, "ci_hi_bps": b["hi"] * 1e4,
                     "p": b["p"], "n": b["n"]})
    # and the full session for context
    b = A.clustered_bootstrap(pd.Series(sign * (close_px / open_px - 1.0),
                                        index=df.index), df["date"])
    rows.append({"minute": 390, "time": "16:00 (close)",
                 "cum_signed_bps": b["stat"] * 1e4, "ci_lo_bps": b["lo"] * 1e4,
                 "ci_hi_bps": b["hi"] * 1e4, "p": b["p"], "n": b["n"]})
    drift = pd.DataFrame(rows)
    drift.to_csv(OUT_DIR / "intraday_drift_path.csv", index=False)

    # ---- 3. short-horizon exits: open -> minute k --------------------------
    rows = []
    for k in list(range(1, 11)) + [15, 20, 29]:
        col = f"m{k}"
        if col not in df.columns:
            continue
        gross = sign * (df[col] / open_px - 1.0)
        net = gross - 2.0 * (spread_bps / 2.0 + 2.0) / 1e4
        b = A.clustered_bootstrap(pd.Series(net, index=df.index), df["date"])
        rows.append({"hold_minutes": k, "exit_time": f"09:{30+k:02d}",
                     "n": b["n"], "net_bps": b["stat"] * 1e4,
                     "ci_lo_bps": b["lo"] * 1e4, "ci_hi_bps": b["hi"] * 1e4,
                     "p": b["p"]})
    scalp = pd.DataFrame(rows)
    scalp.to_csv(OUT_DIR / "intraday_scalp_exits.csv", index=False)

    pd.set_option("display.width", 200)
    log("ENTRY SWEEP (enter at minute k, hold to close)")
    print(entry_sweep.round(3).to_string(index=False))
    log("DRIFT PATH (signed cumulative move from the open)")
    print(drift.round(3).to_string(index=False))
    log("SHORT-HORIZON EXITS (enter at open, exit at minute k)")
    print(scalp.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
