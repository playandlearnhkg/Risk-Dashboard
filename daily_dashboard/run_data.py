#!/usr/bin/env python3
"""
run_data.py — Layer 1 entry point. All data ingestion, no scoring.
==================================================================

    python3 run_data.py                    # everything
    python3 run_data.py --no-filings       # skip SEC EDGAR (10-K/Q/8-K/Form 4)
    python3 run_data.py --no-13f           # skip institutional holdings
    python3 run_data.py --quick            # prices + universe only
    python3 run_data.py --tickers AAPL,MSFT
    python3 run_data.py --full-refresh     # refetch all price history
    python3 run_data.py --stage prices     # run one stage

Stages run in dependency order: the universe defines which tickers everything
else fetches, and fundamentals must be ingested before ratios can be derived
from them. Each stage is independently fault-tolerant — a failed stage is
logged and the run continues, because a Yahoo outage should not prevent the
SEC pull from completing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.config import load_config                                # noqa: E402
from core.db import Database                                       # noqa: E402
from core.logging_setup import (                                   # noqa: E402
    BOLD, DIM, GREEN, RESET, YELLOW, banner, fail, info, kv, ok,
    setup_logging, stage, warn,
)
from data import (                                                 # noqa: E402
    earnings_calendar, estimates, fundamentals, institutional,
    market_data, sec_data, short_interest, transcripts, universe,
)
from data.providers import get_provider                            # noqa: E402

ALL_STAGES = ["universe", "prices", "fundamentals", "ratios", "short_interest",
              "estimates", "earnings", "filings", "institutional"]


def _record(db, run_id: str, stage_name: str, status: str, rows: int,
            message: str, started: float) -> None:
    db.upsert_many(
        "ingest_log",
        ["run_id", "stage", "status", "rows", "message", "started_at", "finished_at"],
        [(run_id, stage_name, status, rows, message[:500],
          dt.datetime.fromtimestamp(started).isoformat(timespec="seconds"),
          dt.datetime.now().isoformat(timespec="seconds"))],
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-filings", action="store_true",
                    help="skip SEC EDGAR filings and Form 4")
    ap.add_argument("--no-13f", action="store_true",
                    help="skip institutional 13-F holdings")
    ap.add_argument("--quick", action="store_true",
                    help="universe + prices only")
    ap.add_argument("--full-refresh", action="store_true",
                    help="refetch all price history, ignoring what is stored")
    ap.add_argument("--force-universe", action="store_true",
                    help="re-scrape the universe even if cached")
    ap.add_argument("--tickers", help="comma-separated subset, for testing")
    ap.add_argument("--stage", choices=ALL_STAGES, help="run a single stage")
    ap.add_argument("--limit", type=int, help="cap ticker count (testing)")
    args = ap.parse_args()

    cfg = load_config()
    cfg.ensure_dirs()
    log = setup_logging(cfg.get("logging.level", "INFO"),
                        cfg.path("logging.file") if cfg.get("logging.file") else None)

    run_id = uuid.uuid4().hex[:12]
    run_started = time.time()
    db = Database(cfg.path("paths.database"))

    print(banner(f"  MERIDIAN · LAYER 1 DATA INGESTION · run {run_id}"))

    # --- provider health --------------------------------------------------
    provider = get_provider(cfg, "market_data")
    healthy, detail = provider.healthcheck()
    print(kv("Market data provider", f"{provider.name} — {detail}"))
    if not healthy:
        print(warn("Provider healthcheck failed; price stages may return nothing."))

    def selected(name: str) -> bool:
        if args.stage:
            return name == args.stage
        if args.quick:
            return name in ("universe", "prices")
        if name == "filings" and args.no_filings:
            return False
        if name == "institutional" and args.no_13f:
            return False
        return True

    results: dict[str, str] = {}

    # --- 1. universe ------------------------------------------------------
    if selected("universe"):
        print(stage("1 · Universe"))
        t0 = time.time()
        try:
            u = universe.refresh(db, cfg, force=args.force_universe)
            msg = (f"{u.constituents} constituents (+{u.added}/-{u.removed}), "
                   f"{u.benchmarks} benchmark/ETF tickers, source={u.source}")
            print(ok(msg) if not u.error else warn(u.error))
            results["universe"] = msg
            _record(db, run_id, "universe", "ok", u.constituents, msg, t0)
        except Exception as exc:                       # noqa: BLE001
            print(fail(f"universe failed: {exc}"))
            results["universe"] = f"FAILED: {exc}"
            _record(db, run_id, "universe", "error", 0, str(exc), t0)

    # --- ticker selection -------------------------------------------------
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        equities = tickers
    else:
        tickers = universe.get_all_tickers(db)
        equities = universe.get_constituents(db)
    if args.limit:
        tickers, equities = tickers[:args.limit], equities[:args.limit]

    if not tickers:
        print(fail("No tickers in the universe — cannot continue."))
        return 1
    print(info(f"{len(tickers)} tickers to process ({len(equities)} equities)"))

    # --- 2. prices --------------------------------------------------------
    if selected("prices"):
        print(stage("2 · Daily prices"))
        t0 = time.time()
        try:
            p = market_data.ingest(db, provider, tickers, cfg,
                                   full_refresh=args.full_refresh)
            msg = (f"{p.rows_written:,} rows · {p.tickers_updated} updated · "
                   f"{p.up_to_date} already current · {p.tickers_failed} failed")
            print(ok(msg))
            if p.latest:
                print(info(f"history spans {p.earliest} → {p.latest}"))
            if p.failed_tickers:
                print(warn(f"no data: {', '.join(sorted(p.failed_tickers)[:12])}"
                           f"{' …' if len(p.failed_tickers) > 12 else ''}"))
            results["prices"] = msg
            _record(db, run_id, "prices", "ok", p.rows_written, msg, t0)
        except Exception as exc:                       # noqa: BLE001
            print(fail(f"prices failed: {exc}"))
            results["prices"] = f"FAILED: {exc}"
            _record(db, run_id, "prices", "error", 0, str(exc), t0)

    # --- 3. fundamentals --------------------------------------------------
    if selected("fundamentals"):
        print(stage("3 · Fundamentals"))
        t0 = time.time()
        try:
            f = fundamentals.ingest(db, provider, equities, cfg)
            msg = (f"{f.line_items:,} line items · {f.tickers_ingested} tickers · "
                   f"{f.tickers_failed} failed")
            print(ok(msg))
            results["fundamentals"] = msg
            _record(db, run_id, "fundamentals", "ok", f.line_items, msg, t0)
        except Exception as exc:                       # noqa: BLE001
            print(fail(f"fundamentals failed: {exc}"))
            results["fundamentals"] = f"FAILED: {exc}"
            _record(db, run_id, "fundamentals", "error", 0, str(exc), t0)

    # --- 4. derived ratios ------------------------------------------------
    if selected("ratios"):
        print(stage("4 · Derived ratios (24 per period)"))
        t0 = time.time()
        try:
            # Market caps come from the latest close x shares outstanding, so
            # fcf_yield can be computed without another provider round-trip.
            caps: dict[str, float] = {}
            for row in db.query(
                "SELECT r.ticker, r.shares_outstanding, p.close FROM fundamental_ratios r "
                "JOIN (SELECT ticker, MAX(date) AS d FROM daily_prices GROUP BY ticker) l "
                "  ON r.ticker = l.ticker "
                "JOIN daily_prices p ON p.ticker = l.ticker AND p.date = l.d "
                "WHERE r.shares_outstanding IS NOT NULL"
            ):
                if row["shares_outstanding"] and row["close"]:
                    caps[row["ticker"]] = row["shares_outstanding"] * row["close"]

            n = fundamentals.compute_all_ratios(db, equities, cfg, caps)
            msg = f"{n:,} ratio rows · market caps for {len(caps)} tickers"
            print(ok(msg))
            results["ratios"] = msg
            _record(db, run_id, "ratios", "ok", n, msg, t0)
        except Exception as exc:                       # noqa: BLE001
            print(fail(f"ratios failed: {exc}"))
            results["ratios"] = f"FAILED: {exc}"
            _record(db, run_id, "ratios", "error", 0, str(exc), t0)

    # --- 5. short interest ------------------------------------------------
    if selected("short_interest"):
        print(stage("5 · Short interest snapshot"))
        t0 = time.time()
        try:
            s = short_interest.ingest(db, provider, equities)
            depth = short_interest.history_depth(db)
            msg = f"{s.tickers_stored} stored · {s.tickers_failed} unavailable"
            print(ok(msg))
            print(info(f"snapshot history: {depth['snapshots']} snapshots "
                       f"over {depth['days']} days"))
            results["short_interest"] = msg
            _record(db, run_id, "short_interest", "ok", s.tickers_stored, msg, t0)
        except Exception as exc:                       # noqa: BLE001
            print(fail(f"short interest failed: {exc}"))
            results["short_interest"] = f"FAILED: {exc}"
            _record(db, run_id, "short_interest", "error", 0, str(exc), t0)

    # --- 6. estimates -----------------------------------------------------
    if selected("estimates"):
        print(stage("6 · Analyst estimates snapshot"))
        t0 = time.time()
        try:
            e = estimates.ingest(db, provider, equities)
            depth = estimates.history_depth(db)
            msg = f"{e.tickers_stored} stored · {e.tickers_failed} unavailable"
            print(ok(msg))
            ready = depth["windows_ready"]
            if ready:
                print(info(f"revision windows ready: {ready} days"))
            else:
                # This is the single most common source of confusion in the
                # first month of running the system, so say it explicitly.
                print(warn(f"no revision windows ready yet — {depth['days']} days of "
                           "history; Layer 2's revisions factor stays degenerate "
                           "(all scores 50) until ~30 days accumulate"))
            results["estimates"] = msg
            _record(db, run_id, "estimates", "ok", e.tickers_stored, msg, t0)
        except Exception as exc:                       # noqa: BLE001
            print(fail(f"estimates failed: {exc}"))
            results["estimates"] = f"FAILED: {exc}"
            _record(db, run_id, "estimates", "error", 0, str(exc), t0)

    # --- 7. earnings calendar ---------------------------------------------
    if selected("earnings"):
        print(stage("7 · Earnings calendar"))
        t0 = time.time()
        try:
            days = int(cfg.get("data.earnings.calendar_days_ahead", 30))
            c = earnings_calendar.ingest(db, provider, equities, days_ahead=days)
            soon = earnings_calendar.reporting_within(db, days=5)
            msg = f"{c.events} events for {c.tickers_with_events} tickers"
            print(ok(msg))
            if soon:
                print(info(f"reporting within 5 days: {len(soon)} tickers"))
            results["earnings"] = msg
            _record(db, run_id, "earnings", "ok", c.events, msg, t0)
        except Exception as exc:                       # noqa: BLE001
            print(fail(f"earnings calendar failed: {exc}"))
            results["earnings"] = f"FAILED: {exc}"
            _record(db, run_id, "earnings", "error", 0, str(exc), t0)

    # --- 8. SEC filings ---------------------------------------------------
    if selected("filings"):
        print(stage("8 · SEC filings & Form 4"))
        t0 = time.time()
        try:
            sec = sec_data.ingest(db, cfg, equities)
            if sec.error:
                print(warn(sec.error))
                results["filings"] = f"SKIPPED: {sec.error[:80]}"
                _record(db, run_id, "filings", "skipped", 0, sec.error, t0)
            else:
                msg = (f"{sec.filings} filings · {sec.sections} sections · "
                       f"{sec.insider_rows} insider rows ({sec.signal_rows} signal)")
                print(ok(msg))
                if sec.cluster_flags:
                    print(info(f"cluster-buy flags: {sec.cluster_flags} tickers"))
                results["filings"] = msg
                _record(db, run_id, "filings", "ok", sec.filings, msg, t0)
        except Exception as exc:                       # noqa: BLE001
            print(fail(f"SEC ingest failed: {exc}"))
            results["filings"] = f"FAILED: {exc}"
            _record(db, run_id, "filings", "error", 0, str(exc), t0)
    elif args.no_filings:
        print(stage("8 · SEC filings & Form 4"))
        print(info("skipped (--no-filings)"))

    # --- 9. institutional 13-F --------------------------------------------
    if selected("institutional"):
        print(stage("9 · Institutional 13-F"))
        t0 = time.time()
        try:
            inst = institutional.ingest(db, cfg)
            if inst.error:
                print(warn(inst.error))
                results["institutional"] = f"SKIPPED: {inst.error[:80]}"
                _record(db, run_id, "institutional", "skipped", 0, inst.error, t0)
            else:
                msg = (f"{inst.holdings} holdings from "
                       f"{inst.funds_processed}/{inst.funds_requested} funds")
                print(ok(msg))
                if inst.multi_fund_opens:
                    print(info(f"multi-fund new positions: {inst.multi_fund_opens}"))
                if inst.failed_funds:
                    print(warn(f"no data: {', '.join(inst.failed_funds)}"))
                results["institutional"] = msg
                _record(db, run_id, "institutional", "ok", inst.holdings, msg, t0)
        except Exception as exc:                       # noqa: BLE001
            print(fail(f"13-F ingest failed: {exc}"))
            results["institutional"] = f"FAILED: {exc}"
            _record(db, run_id, "institutional", "error", 0, str(exc), t0)
    elif args.no_13f:
        print(stage("9 · Institutional 13-F"))
        print(info("skipped (--no-13f)"))

    # --- summary ----------------------------------------------------------
    elapsed = time.time() - run_started
    print(banner(f"  SUMMARY · {elapsed:.0f}s elapsed"))
    for name in ALL_STAGES:
        if name in results:
            outcome = results[name]
            marker = (f"{GREEN}✓{RESET}" if not outcome.startswith(("FAILED", "SKIPPED"))
                      else f"{YELLOW}!{RESET}")
            print(f"  {marker} {name:<16} {DIM}{outcome}{RESET}")

    print(f"\n  {BOLD}Database{RESET} {cfg.path('paths.database')}")
    counts = db.counts()
    width = max(len(k) for k in counts)
    for table, n in counts.items():
        print(f"    {table:<{width}}  {n:>10,}")

    cov = market_data.coverage_report(db)
    print(f"\n  {BOLD}Price coverage{RESET}  latest {cov['latest_date']} · "
          f"{cov['tickers']} tickers · {cov['stale_tickers']} stale")

    sectors = universe.sector_counts(db)
    if sectors:
        print(f"\n  {BOLD}Sector distribution{RESET}")
        for sector, n in sectors.items():
            bar = "█" * max(1, round(n / max(sectors.values()) * 28))
            print(f"    {sector[:26]:<26} {n:>4}  {DIM}{bar}{RESET}")
        thin = [s for s, n in sectors.items() if n < 10]
        if thin:
            # Percentile ranks over fewer than ~10 names are extremely coarse.
            print(warn(f"thin sectors (<10 names) will produce noisy percentile "
                       f"ranks in Layer 2: {', '.join(thin)}"))

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
