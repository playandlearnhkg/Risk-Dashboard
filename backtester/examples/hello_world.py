"""
hello_world.py -- load one ticker, print what the engine sees.

The smallest useful program against this engine. It touches every layer
except the portfolio, so if this runs, your install and your data are
both fine.

    python3 examples/hello_world.py
    python3 examples/hello_world.py --ticker MSFT
    python3 examples/hello_world.py --data-dir "D:/bars" --ticker NVDA

Read the DST block in the output first. If the same 09:35 local time does
not map to two different UTC hours across a daylight-saving boundary,
something in the timezone chain is wrong and nothing downstream can be
trusted.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.calendar import local_time_to_utc, to_exchange_tz  # noqa: E402
from engine.data_loader import DataError, DataLoader  # noqa: E402
from engine.pit import PointInTimeEngine  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", default="AAPL")
    ap.add_argument("--data-dir", default=str(ROOT / "data"))
    ap.add_argument("--entry", default="09:35", help="local entry time")
    a = ap.parse_args()

    # ---- 1. load ----------------------------------------------------
    try:
        loader = DataLoader(a.data_dir)
    except DataError as exc:
        print(f"cannot open data dir: {exc}")
        return 2

    print(f"data dir : {a.data_dir}")
    print(f"tickers  : {', '.join(loader.tickers) or '(none)'}")
    if a.ticker.upper() not in loader.tickers:
        print(f"\n{a.ticker!r} not found. Run tests/make_fixtures.py for sample "
              f"data, or drop {{TICKER}}_{{YYYYMMDD}}_{{YYYYMMDD}}_1m.parquet "
              f"files into the data dir.")
        return 1

    bars = loader.load(a.ticker)          # regular session only, annotated

    # ---- 2. what came back ------------------------------------------
    print(f"\n{'=' * 62}\n{a.ticker.upper()}\n{'=' * 62}")
    print(f"bars             {len(bars):,}")
    print(f"sessions         {bars['session_date'].nunique():,}")
    print(f"first            {bars.index[0]}  "
          f"({to_exchange_tz(bars.index[:1])[0]:%Y-%m-%d %H:%M %Z})")
    print(f"last             {bars.index[-1]}  "
          f"({to_exchange_tz(bars.index[-1:])[0]:%Y-%m-%d %H:%M %Z})")
    print(f"source files     {', '.join(bars.attrs['source_files'])}")
    print(f"dup bars dropped {bars.attrs['duplicates_dropped']:,}")

    per = bars.groupby("session_date").size()
    print(f"bars/session     median {int(per.median())}, min {int(per.min())}, "
          f"max {int(per.max())}")
    short = per[per < 390]
    if len(short):
        print(f"short sessions   {len(short)} "
              f"(half days or missing bars: {', '.join(str(d) for d in short.index[:3])}"
              f"{' ...' if len(short) > 3 else ''})")

    print("\nfirst five bars")
    print(bars.head(5)[["open", "high", "low", "close", "volume",
                        "minutes_from_open"]].to_string())

    # ---- 3. the timezone sanity check -------------------------------
    # If this block does not show two different UTC hours, stop and fix
    # the environment before trusting anything else.
    hh, mm = (int(x) for x in a.entry.split(":"))
    import datetime as dt
    entry_local = dt.time(hh, mm)

    sessions = sorted(bars["session_date"].unique())
    probes = [sessions[0], sessions[len(sessions) // 2], sessions[-1]]
    rows = []
    for s in probes:
        want = local_time_to_utc(s, entry_local)
        present = bool(len(bars.index[bars.index == want]))
        rows.append({
            "session": s,
            "entry_utc": want,
            "local": to_exchange_tz(pd.DatetimeIndex([want]))[0]
                     .strftime("%H:%M %Z"),
            "bar_present": present,
            "open": float(bars.loc[want, "open"]) if present else float("nan"),
        })
    print(f"\nentry time {a.entry} America/New_York resolves to:")
    print(pd.DataFrame(rows).to_string(index=False))
    zones = {r["local"].split()[-1] for r in rows}
    print(f"timezones seen   {sorted(zones)}"
          f"{'   <- DST handled' if len(zones) > 1 else ''}")

    # ---- 4. what a strategy would actually see ----------------------
    eng = PointInTimeEngine(bars, a.ticker, atr_period=14, volume_window=20)
    eng.self_check()

    i = min(len(eng.sessions) - 1, 30)          # a session past warm-up
    s = eng.sessions[i]
    view = eng.view(s, eng.decision_ts(s, entry_local))

    print(f"\nSessionView for {s} at {a.entry} local")
    print(f"  prior sessions available   {len(view.prior)}")
    print(f"  today's bars in the view   {len(view.today)} "
          f"(minutes 0..{int(view.today['minutes_from_open'].max())})")
    print(f"  entry_open (decision bar)  {view.entry_open:.4f}")
    print(f"  prior close                {view.prior.last_close():.4f}")
    print(f"  gap                        {view.gap() * 100:+.3f}%")
    print(f"  ATR(14), prior sessions    {view.prior.atr(14):.4f}")
    print(f"  volume ratio, 5-min candle {view.volume_ratio(0, 4, 20):.2f}x")
    c = view.candle(0, 4)
    if c:
        rng = c["high"] - c["low"]
        body = c["close"] - c["open"]
        print(f"  opening candle o/h/l/c     {c['open']:.2f} / {c['high']:.2f} "
              f"/ {c['low']:.2f} / {c['close']:.2f}")
        print(f"  body / range               {abs(body) / rng:.3f}"
              f"{'  (doji)' if abs(body) / rng <= 0.10 else ''}")

    print("\nNote the view stops one minute BEFORE the decision instant: the "
          "\nentry bar's high, low and close do not exist yet, so only its "
          "\nopening print is exposed. That is the point-in-time guarantee.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
