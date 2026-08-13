"""
universe_example.py -- supplying an earnings calendar, three ways.

Shows the cohort shrinking at each stage and demonstrates that the
BMO/AMC field is load-bearing: flipping one announcement's timing moves
the traded session by a day.

    python3 examples/universe_example.py
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.config import BacktestConfig  # noqa: E402
from engine.data_loader import DataLoader  # noqa: E402
from engine.universe import (AllSessions, EarningsCalendar,  # noqa: E402
                             PostEarningsUniverse, from_config)
from strategies.core_post_earnings import \
    CorePostEarningsContinuation  # noqa: E402

DATA = ROOT / "data"
CFG = ROOT / "config" / "strategies" / "core_post_earnings.yaml"


def rule(t):
    print(f"\n{t}\n{'-' * len(t)}")


def main() -> int:
    cfg = BacktestConfig.from_yaml(CFG)
    ld = DataLoader(DATA)
    frames = {t: ld.load(t) for t in ld.tickers}
    strat = CorePostEarningsContinuation(cfg)

    # --- 1. three ways to supply a calendar ---------------------------
    rule("1. supplying an earnings calendar")

    from_csv = EarningsCalendar.from_file(DATA / "earnings_calendar.csv")
    print(f"from CSV     {len(from_csv.table)} announcements, "
          f"timing mix {from_csv.timing_mix()}")

    from_dict = EarningsCalendar.from_dict({
        "AAPL": [("2025-10-05", "amc"), ("2025-11-11", "amc")],
        "MSFT": [("2025-11-25", "amc"), "2025-10-30"],   # bare date = unknown
    })
    print(f"from dict    {len(from_dict.table)} announcements, "
          f"timing mix {from_dict.timing_mix()}")

    inline = EarningsCalendar(pd.DataFrame([
        {"ticker": "AAPL", "announce_date": "2025-12-04",
         "announce_time": "After Market Close"},          # alias accepted
    ]))
    print(f"from frame   {len(inline.table)} announcement, "
          f"parsed as {inline.table['announce_time'].iloc[0]!r}")

    # --- 2. the cohort shrinking --------------------------------------
    rule("2. what each stage removes")
    caps = pd.read_csv(DATA / "market_caps.csv")
    prov = from_config(cfg, DATA / "earnings_calendar.csv", caps)
    elig = prov.eligible(frames)

    d = prov.diagnostics()
    for k in ("candidate_sessions", "after_earnings", "after_price",
              "after_mcap", "after_liquidity", "eligible_pairs"):
        print(f"  {k:<24} {d[k]:>6,}")
    print(f"  {'unknown timing skipped':<24} {d['unknown_timing_skipped']:>6,}")

    # --- 3. the difference it makes -----------------------------------
    rule("3. signals with and without the universe")
    no_filter = strat.run_many_signals(frames)
    filtered = strat.run_many_signals(frames, eligible=elig)
    print(f"  every session (WRONG cohort)  {len(no_filter):>3} signals")
    print(f"  post-earnings T+1 only        {len(filtered):>3} signals")
    dropped = {(s.ticker, s.session) for s in no_filter} - \
              {(s.ticker, s.session) for s in filtered}
    for t, s in sorted(dropped, key=lambda x: x[1]):
        print(f"    dropped {t} {s}  (no announcement before this session)")

    # --- 4. BMO vs AMC is not cosmetic --------------------------------
    rule("4. the same announcement, two timings")
    days = sorted(set(frames["AAPL"]["session_date"]))
    probe = days[60]
    for when in ("bmo", "amc"):
        c = EarningsCalendar(pd.DataFrame([
            {"ticker": "AAPL", "announce_date": str(probe),
             "announce_time": when}]))
        e = PostEarningsUniverse(c).eligible({"AAPL": frames["AAPL"]})
        got = sorted(e.get("AAPL", set()))
        print(f"  announced {probe} {when.upper():<4} -> trades {got}")
    print("\n  One field, one session apart. Getting it wrong puts every "
          "\n  trade on a day with no news, and the backtest still runs.")

    rule("5. opting out, visibly")
    a = AllSessions()
    a.eligible(frames)
    print(f"  {a.diagnostics()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
