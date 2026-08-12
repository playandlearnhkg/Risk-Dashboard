"""
make_fixtures.py -- deterministic sample data in the confirmed format.

The fixtures are deliberately awkward, because a loader that only ever
sees tidy data is untested. They contain:

  * a DST transition (2025-11-02), so the same 09:30 local open lands on
    two different UTC hours inside one file
  * pre- and post-market bars, so the regular-session filter has
    something to actually remove
  * an early close (2025-11-28, 13:00 ET), so half-day handling is
    exercised without a holiday table
  * a missing-bar gap, so nothing downstream may assume a dense grid
  * TWO OVERLAPPING FILES for one ticker with deliberately different
    prices in the overlap, so de-duplication is observable rather than
    assumed

Run: python3 tests/make_fixtures.py
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

NY = ZoneInfo("America/New_York")
OUT = Path(__file__).resolve().parents[1] / "data"

HOLIDAYS = {dt.date(2025, 9, 1), dt.date(2025, 11, 27),
            dt.date(2025, 12, 25)}
EARLY_CLOSE = {dt.date(2025, 11, 28): dt.time(13, 0)}


def sessions(start: dt.date, end: dt.date) -> list[dt.date]:
    days, d = [], start
    while d <= end:
        if d.weekday() < 5 and d not in HOLIDAYS:
            days.append(d)
        d += dt.timedelta(days=1)
    return days


def build(ticker: str, start: dt.date, end: dt.date, seed: int,
          px0: float, drop_bars: bool = False) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows, px = [], px0
    for day in sessions(start, end):
        close_t = EARLY_CLOSE.get(day, dt.time(17, 0))
        t = dt.datetime.combine(day, dt.time(8, 0), tzinfo=NY)
        stop = dt.datetime.combine(day, close_t, tzinfo=NY)
        # A gap up or down at the open, so continuation logic has input.
        px *= 1.0 + rng.normal(0, 0.012)
        # On a third of sessions the opening minutes trade heavy, so the
        # 1.5x volume filter has something to select. Without this the
        # synthetic volume is near-constant, the ratio sits at ~1.0, and
        # the strategy correctly produces no signals -- which would make
        # the end-to-end test vacuous rather than passing.
        surge = float(rng.uniform(2.0, 8.0)) if rng.random() < 0.34 else 1.0
        while t < stop:
            # Thin outside the regular session, as in real data.
            local = t.timetz()
            regular = dt.time(9, 30) <= local.replace(tzinfo=None) < dt.time(16, 0)
            step = rng.normal(0, 0.0008 if regular else 0.0003)
            o = px
            c = px * (1 + step)
            hi = max(o, c) * (1 + abs(rng.normal(0, 0.0004)))
            lo = min(o, c) * (1 - abs(rng.normal(0, 0.0004)))
            vol = float(rng.integers(2_000, 40_000) if regular
                        else rng.integers(0, 1_500))
            mins_in = (t.hour * 60 + t.minute) - (9 * 60 + 30)
            if regular and 0 <= mins_in < 5:
                vol *= surge
            rows.append((t.astimezone(dt.timezone.utc), o, hi, lo, c, vol))
            px = c
            t += dt.timedelta(minutes=1)

    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close",
                                     "volume"]).set_index("ts")
    df.index = pd.DatetimeIndex(df.index).tz_convert("UTC")
    df.index.name = "ts"

    if drop_bars:
        # Punch a hole: 20 consecutive minutes vanish mid-session.
        hole = df.index[(df.index >= "2025-11-12 15:00:00+00:00")
                        & (df.index < "2025-11-12 15:20:00+00:00")]
        df = df.drop(index=hole)

    return df.astype("float64")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    a = build("AAPL", dt.date(2025, 8, 1), dt.date(2025, 12, 15),
              seed=7, px0=220.0, drop_bars=True)
    a.to_parquet(OUT / "AAPL_20250801_20251215_1m.parquet")

    # Two overlapping extracts for MSFT. The later-issued one is shifted
    # by a visible amount inside the overlap so the tests can prove which
    # file survived de-duplication.
    b1 = build("MSFT", dt.date(2025, 10, 15), dt.date(2025, 11, 20),
               seed=11, px0=410.0)
    b2 = build("MSFT", dt.date(2025, 11, 10), dt.date(2025, 12, 15),
               seed=11, px0=410.0)
    b2 = b2 * 1.05
    b1.to_parquet(OUT / "MSFT_20251015_20251120_1m.parquet")
    b2.to_parquet(OUT / "MSFT_20251110_20251215_1m.parquet")

    # A file the catalog must ignore rather than choke on.
    (OUT / "README_not_a_bar_file.txt").write_text(
        "Deliberate non-parquet file; the catalog must skip it.\n")

    for p in sorted(OUT.glob("*.parquet")):
        n = len(pd.read_parquet(p, columns=[]))
        print(f"{p.name:44s} {n:>7,} bars")


if __name__ == "__main__":
    main()
