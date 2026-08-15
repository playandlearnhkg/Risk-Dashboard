"""
run_backtest.py -- entry point.

This is the single entry point for every stage. Today it validates a
configuration, audits the data directory against it, generates signals,
and proves the signals carry no look-ahead. Portfolio simulation and
metrics (steps 4-6) will hang off the same command.

Config and data inspection are deliberately useful on their own: most
wasted backtests are wasted because the data or the config was not what
the author assumed, and both surface here before any modelling happens.

    python3 run_backtest.py --config config/strategies/core_post_earnings.yaml
    python3 run_backtest.py --config ... --audit
    python3 run_backtest.py --config ... --peek AAPL
    python3 run_backtest.py --config ... --signals --verify
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
from engine.pit import LookAheadError, verify_no_lookahead  # noqa: E402
from engine.portfolio import Portfolio, SelectionRule  # noqa: E402
from engine import capacity as CAP  # noqa: E402
from engine import metrics as MET  # noqa: E402
from engine import robustness as ROB  # noqa: E402
from engine import validation as VAL  # noqa: E402
from engine.gate import GateThresholds, Verdict, run_gate  # noqa: E402
from engine.universe import (AllSessions, UniverseError,  # noqa: E402
                             from_config as universe_from_config)
from strategies.core_post_earnings import \
    CorePostEarningsContinuation  # noqa: E402


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
    ap.add_argument("--signals", action="store_true",
                    help="generate signals (step 3) and write them to results/")
    ap.add_argument("--verify", action="store_true",
                    help="prove no look-ahead by deleting the future and "
                         "re-running each probed decision")
    ap.add_argument("--run", action="store_true",
                    help="simulate the portfolio (step 4) and write the trade "
                         "log and equity curve to results/")
    ap.add_argument("--validate", action="store_true",
                    help="full validation report (step 5): performance, "
                         "distribution, year-by-year, long/short, trade log")
    ap.add_argument("--robustness", action="store_true",
                    help="robustness suite (step 6): cost, period, side, "
                         "position limit and stop sensitivity")
    ap.add_argument("--capacity", action="store_true",
                    help="risk and capacity suite (step 7): borrow, slippage, "
                         "participation, concentration, execution delay")
    ap.add_argument("--full-validation", action="store_true",
                    help="the standardised report: both stop variants, "
                         "year-by-year, distribution, cost sweep, 2022-2025 "
                         "stress period, trade logs and plots")
    ap.add_argument("--gate", action="store_true",
                    help="run the validation gate and exit non-zero unless it "
                         "PASSES; this is the check every strategy must clear "
                         "before robustness or live consideration")
    ap.add_argument("--all", action="store_true",
                    help="--run --validate --robustness --capacity")
    ap.add_argument("--earnings", type=Path, default=None,
                    help="earnings calendar (CSV/Parquet: ticker, "
                         "announce_date, announce_time). Required when "
                         "universe.post_earnings_only is true.")
    ap.add_argument("--market-caps", type=Path, default=None,
                    help="point-in-time market caps (ticker, date, market_cap)")
    ap.add_argument("--unknown-timing", default="skip",
                    choices=["skip", "assume_amc", "assume_bmo"],
                    help="what to do with announcements of unknown timing; "
                         "skip is the only one that assumes nothing")
    ap.add_argument("--no-universe", action="store_true",
                    help="evaluate every session, ignoring universe filters "
                         "(diagnostic only -- this is NOT the strategy)")
    ap.add_argument("--start", default=None, help="restrict to YYYY-MM-DD")
    ap.add_argument("--end", default=None, help="restrict to YYYY-MM-DD")
    ap.add_argument("--cost-bps", type=float, default=None,
                    help="override costs.round_trip_bps for this run")
    ap.add_argument("--selection", default=SelectionRule.VOLUME_RATIO.value,
                    choices=[r.value for r in SelectionRule],
                    help="ex-ante rule for choosing which signals to take "
                         "when a session exceeds max_concurrent_positions")
    a = ap.parse_args()
    if a.all:
        a.run = a.validate = a.robustness = a.capacity = True
        a.full_validation = True

    try:
        cfg = BacktestConfig.from_yaml(a.config)
    except ConfigError as exc:
        print(f"CONFIG ERROR  {exc}", file=sys.stderr)
        return 2

    rule(f"{cfg.strategy.name} v{cfg.strategy.version}")
    print(cfg.describe())

    if a.cost_bps is not None:
        cfg = cfg.replace(**{"costs.round_trip_bps": float(a.cost_bps)})
        print(f"\noverride: costs.round_trip_bps = {a.cost_bps}")

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

    need_engine = (a.signals or a.verify or a.run or a.validate
                   or a.robustness or a.capacity
                   or a.full_validation or a.gate)
    if need_engine:
        strat = CorePostEarningsContinuation(cfg)
        frames = loader.load_many(loader.tickers, start=cfg.data.start,
                                  end=cfg.data.end)

        # ---- universe: which (ticker, session) pairs may be evaluated
        caps = None
        if a.market_caps is not None:
            caps = pd.read_csv(a.market_caps) if a.market_caps.suffix == ".csv" \
                else pd.read_parquet(a.market_caps)
        try:
            provider = (AllSessions() if a.no_universe
                        else universe_from_config(cfg, a.earnings, caps,
                                                  a.unknown_timing))
            eligible = provider.eligible(frames, start=a.start, end=a.end)
        except UniverseError as exc:
            print(f"\nUNIVERSE ERROR  {exc}", file=sys.stderr)
            return 2

        rule("universe")
        for k, v in provider.diagnostics().items():
            print(f"  {k:<28} {v}")
        if a.no_universe:
            print("\n  WARNING: --no-universe evaluates every session. Any "
                  "\n  performance number from this run describes a different "
                  "\n  strategy from the configured one.")


        if a.verify:
            rule("look-ahead verification (future deleted, decisions re-run)")
            for t, bars in frames.items():
                try:
                    out = verify_no_lookahead(
                        lambda b, _c=cfg: CorePostEarningsContinuation(_c),
                        bars, t)
                except LookAheadError as exc:
                    print(f"FAILED  {t}: {exc}", file=sys.stderr)
                    return 3
                print(f"  {t}: {len(out)} decisions re-run, all identical")

        if a.signals:
            sigs = strat.run_many(frames, eligible=eligible)
            rule(f"signals: {len(sigs)}")
            if len(sigs):
                show = sigs.copy()
                show["entry_local"] = to_exchange_tz(
                    pd.DatetimeIndex(show["entry_ts"])).strftime("%H:%M %Z")
                cols = ["ticker", "session", "direction", "entry_local",
                        "entry_price", "risk_unit", "gap_pct", "volume_ratio",
                        "body_over_range"]
                print(show[cols].round(4).to_string(index=False))
                out_path = ROOT / "results" / "signals.csv"
                sigs.to_csv(out_path, index=False)
                print(f"\nwrote {out_path}")
            else:
                print("none -- every session was filtered out")

        sigs_obj = strat.run_many_signals(frames, eligible=eligible)

        if a.run:
            sigs = sigs_obj
            pf = Portfolio(cfg, SelectionRule(a.selection))
            log, curve = pf.run(sigs, frames)
            rule(f"portfolio: {len(log)} trades, selection={a.selection}")
            if len(log):
                cols = ["trade_id", "ticker", "session", "direction",
                        "entry_price", "exit_price", "exit_reason", "notional",
                        "weight", "net_pnl", "ret_bps", "mae_atr", "mfe_atr"]
                print(log[cols].round(4).to_string(index=False))
                print(f"\nstarting capital  {cfg.portfolio.starting_capital:>14,.2f}")
                print(f"final equity      {curve.iloc[-1]:>14,.2f}")
                print(f"net P&L           {log['net_pnl'].sum():>14,.2f}")
                print(f"costs paid        {log['cost'].sum():>14,.2f}")
                print(f"stopped           {int((log.exit_reason == 'stop').sum())} "
                      f"of {len(log)}")
                print(f"gross-capped days {int(log['scaled'].sum())} trades")
                log.to_csv(ROOT / "results" / "trades.csv", index=False)
                curve.to_csv(ROOT / "results" / "equity.csv")
                print(f"\nwrote {ROOT / 'results' / 'trades.csv'}"
                      f"\nwrote {ROOT / 'results' / 'equity.csv'}")

        results = ROOT / "results"

        if a.validate:
            log, curve = Portfolio(cfg, SelectionRule(a.selection)).run(
                sigs_obj, frames)
            m = MET.evaluate(log, cfg.portfolio.starting_capital,
                             f"{cfg.strategy.name} v{cfg.strategy.version}",
                             equity=curve, start=a.start, end=a.end)
            print()
            print(m.summary())
            written = m.write(results, prefix="validation_")
            print(f"\nwrote {len(written)} files to {results}")

        if a.gate:
            res = run_gate(strat, cfg, frames, provider=provider,
                           selection=SelectionRule(a.selection),
                           strategy_factory=lambda b, _c=cfg:
                               CorePostEarningsContinuation(_c))
            print("\n" + res.report())
            written = res.write(results)
            print(f"\nwrote {len(written)} files to {results}")
            if res.verdict is not Verdict.PASS:
                print(f"\nGATE {res.verdict.value}: do not proceed to "
                      f"robustness, capacity or live sizing until the "
                      f"blocking items are resolved.", file=sys.stderr)
                return 4 if res.verdict is Verdict.FAIL else 5

        if a.full_validation:
            rep = VAL.run(cfg, sigs_obj, frames, out_dir=results)
            print("\n" + rep.summary())
            written = rep.write(results)
            print(f"\nwrote {len(written)} files to {results}")

        if a.robustness:
            tables = ROB.run_suite(cfg, sigs_obj, frames)
            text = ROB.dashboard(tables, cfg)
            print("\n" + text)
            ROB.write(tables, results, text)
            print(f"\nwrote robustness_*.csv and robustness_dashboard.txt "
                  f"to {results}")

        if a.capacity:
            tables = CAP.run_suite(cfg, sigs_obj, frames)
            hc = CAP.haircut(tables, cfg)
            text = CAP.dashboard(tables, cfg, hc)
            print("\n" + text)
            CAP.write(tables, results, text, hc)
            print(f"\nwrote capacity_*.csv and capacity_dashboard.txt "
                  f"to {results}")

    rule("status")
    print("Steps 1-7 complete: DataLoader, Config, point-in-time guards, "
          "StrategyBase, Portfolio, Metrics, Robustness and Capacity.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
