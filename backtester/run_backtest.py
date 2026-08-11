"""
run_backtest.py -- entry point.

Steps 1-2 are complete, so today this command validates a configuration,
audits the data directory against it, and prints exactly what a run
would consume. That is deliberately useful on its own: most wasted
backtests are wasted because the data or the config was not what the
author assumed, and this surfaces both before any modelling happens.

Signal generation, portfolio simulation and metrics arrive in steps 3-6
and will hang off the same entry point.

    python3 run_backtest.py --config config/strategies/core_post_earnings.yaml
    python3 run_backtest.py --config ... --audit
    python3 run_backtest.py --config ... --peek AAPL
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from engine.calendar import local_time_to_utc, to_exchange_tz  # noqa: E402
from engine.config import BacktestConfig, ConfigError  # noqa: E402
from engine.data_loader import DataError, DataLoader  # noqa: E402


def rule(title: str) -> None:
    print(f"\n{title}\n{'-' * len(title)}")


def peek(loader: DataLoader, cfg: BacktestConfig, ticker: str) -> None:
    """Show what the configured entry time resolves to on real sessions.

    This is the check that catches a timezone mistake immediately: if
    the entry bar's local time is not the configured one on BOTH sides
    of a DST change, something is wrong before any signal is computed.
    """
    df = loader.load(ticker, start=cfg.data.start, end=cfg.data.end)
    rule(f"{ticker}: {len(df):,} regular-session bars")
    print(f"first bar      {df.index[0]}  "
          f"({to_exchange_tz(df.index[:1])[0]:%Y-%m-%d %H:%M %Z})")
    print(f"last bar       {df.index[-1]}  "
          f"({to_exchange_tz(df.index[-1:])[0]:%Y-%m-%d %H:%M %Z})")
    print(f"sessions       {df['session_date'].nunique():,}")
    print(f"source files   {', '.join(df.attrs['source_files'])}")
    print(f"dup bars dropped {df.attrs['duplicates_dropped']:,}")

    per = df.groupby("session_date").size()
    short = per[per < per.max()]
    print(f"bars/session   median {int(per.median())}, "
          f"min {int(per.min())}, max {int(per.max())}")
    if len(short):
        print(f"short sessions {len(short)} "
              f"(e.g. {short.index[0]} with {int(short.iloc[0])} bars)")

    rule(f"entry bar resolution for entry_time={cfg.signal.entry_time:%H:%M} "
         f"America/New_York")
    sessions = sorted(df["session_date"].unique())
    probes = [sessions[0], sessions[len(sessions) // 2], sessions[-1]]
    rows = []
    for s in probes:
        want = local_time_to_utc(s, cfg.signal.entry_time)
        hit = df.index[df.index == want]
        rows.append({
            "session": s,
            "entry_utc": want,
            "entry_local": to_exchange_tz(pd.DatetimeIndex([want]))[0]
                           .strftime("%H:%M %Z"),
            "bar_present": bool(len(hit)),
            "price": float(df.loc[want, cfg.signal.entry_price])
                     if len(hit) else float("nan"),
        })
    print(pd.DataFrame(rows).to_string(index=False))


def main() -> int:
    ap = argparse.ArgumentParser(description="Run or inspect a backtest.")
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--data-dir", type=Path, default=None,
                    help="override config.data.dir")
    ap.add_argument("--audit", action="store_true",
                    help="compare filename ranges against file contents")
    ap.add_argument("--peek", metavar="TICKER",
                    help="resolve the configured entry time on real sessions")
    a = ap.parse_args()

    try:
        cfg = BacktestConfig.from_yaml(a.config)
    except ConfigError as exc:
        print(f"CONFIG ERROR  {exc}", file=sys.stderr)
        return 2

    rule(f"{cfg.strategy.name} v{cfg.strategy.version}")
    print(cfg.describe())

    for w in cfg.warnings():
        print(f"\nNOTE  {w}")

    data_dir = a.data_dir or (ROOT / cfg.data.dir)
    try:
        loader = DataLoader(data_dir, bar_size=cfg.data.bar_size,
                            validate=cfg.data.validate)
    except DataError as exc:
        print(f"\nDATA ERROR  {exc}", file=sys.stderr)
        return 2

    rule(f"data: {data_dir}")
    print(f"tickers  {len(loader.tickers)}: "
          f"{', '.join(loader.tickers[:12])}"
          f"{' ...' if len(loader.tickers) > 12 else ''}")
    if loader.catalog.skipped:
        print(f"skipped  {len(loader.catalog.skipped)} unparseable filename(s)")
        for name, why in loader.catalog.skipped[:5]:
            print(f"         {name}: {why}")

    if a.audit:
        rule("file audit (declared range vs actual contents)")
        print(loader.catalog.audit().to_string(index=False))

    if a.peek:
        try:
            peek(loader, cfg, a.peek)
        except DataError as exc:
            print(f"\nDATA ERROR  {exc}", file=sys.stderr)
            return 2

    rule("status")
    print("Steps 1-2 complete: DataLoader and Config are implemented and "
          "tested.\nSteps 3-6 (StrategyBase, Portfolio, Metrics, full run) "
          "are stubs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
