# Lambda Strategy Validation — Phase 0 (Infrastructure)

Status: **all four data gaps identified in the original brief are now
solved and validated against real, known historical values. No universe-
wide observational analysis has been run yet** — that's Phase 1, waiting
on scope (see bottom).

## What this is

Scaffolding for validating a Weinstein Stage-2/3/4 trend-based strategy
against Sigma's research design (full design doc not yet shared with
Lambda — placeholder in the original brief). Nothing here should be read
as a strategy result. It is the harness the result will run through.

## Files

- `stage_classifier.py` — Stage 1-4 classification via 50/150/200-day SMA
  (Minervini Trend Template rules, Weinstein-consistent state machine for
  Stage 1 vs 3 disambiguation). **Assumption pending Sigma's exact spec.**
  Validated on a synthetic price path cycling through all four stages
  (`tests/test_stage_classifier_synthetic.py`, PASS) and on real AAPL
  history (2002-2026): 49.0% Markup / 38.4% Topping / 9.3% Basing / 3.3%
  Decline — sane for a stock in a two-decade uptrend.
- `universe_filters.py` — ADV / ADTV / Price filters (pure functions of
  OHLCV, fully implemented) plus a `market_cap_ok` slot that now plugs
  into `market_cap.py`.
- `market_cap.py` — point-in-time historical market cap: SEC EDGAR shares
  outstanding (free, no key) x HF Data Library close price. **Two bugs
  caught and fixed during validation** — see "Data-quality catches"
  below. Verified against AAPL's real historical market cap at three
  dates.
- `earnings_calendar.py` — historical earnings dates via Nasdaq's free
  calendar API, filtered to confirmed-actual rows only (never the
  upcoming-only or `marketCap` fields — see docstring and catches below).
- `data_ingest.py` — downloads 1-min bars from HF Data Library and
  aggregates to daily OHLCV. Key read from `ELKASSABGIDATA_KEY` env var
  only; never commit the key or raw downloaded data to this repo.
- `cost_model.py` — T+1 round-trip execution cost model (half-spread +
  square-root market impact + commission + slippage buffer), with LOW /
  BASE / HIGH scenarios for the mandatory cost-sensitivity test.
- `test_battery.py` — IS/OOS split, walk-forward, bootstrap CI, stage-
  stratified returns, year-by-year returns, beta-filter impact comparison.
  `first_three_5min_pattern()` raises `NotImplementedError` until we
  actually pull 5-min/1-min T+1 bars at scale (mechanism now proven via
  `data_ingest.py`, just not run for this purpose yet).

Run the synthetic classifier check any time with:
```
python3 lambda_strategy_validation/tests/test_stage_classifier_synthetic.py
```

## Data sources now connected

| Need | Source | Status |
|---|---|---|
| Daily OHLCV, 2002-2026 | HF Data Library (`elkassabgidata` MCP, `data_ingest.py`) | Working, verified on AAPL |
| 5-min/1-min T+1 bars | Same source, native 1-min resolution | Working, not yet run at universe scale |
| Market cap history | SEC EDGAR + HF close price (`market_cap.py`) | Working, verified on AAPL |
| Earnings dates | Nasdaq calendar API (`earnings_calendar.py`) | Working, verified on AAPL |

`macromicro.me`'s earnings calendar (suggested as a source) is **not**
usable — it's behind a Cloudflare bot-challenge page ("Just a moment...")
like stooq.com was, not parseable without a real browser solving the
challenge, which isn't something to route around. Nasdaq's API served the
same purpose and is free/unauthenticated.

## Data-quality catches (read before trusting any number downstream)

Two silent bugs would have corrupted the market-cap filter if not caught
by validating against AAPL's real historical values:

1. **Nasdaq calendar API's `marketCap` field is not historical.** Querying
   `date=2019-01-29` for AAPL returned `marketCap: $4.5T` — that's *today's*
   market cap, stamped onto every row regardless of the requested date
   (real AAPL market cap on 2019-01-29 was ~$700B). `market_cap.py`
   doesn't use this field at all; `eps`/`surprise`/`fiscal_quarter_ending`
   on already-reported rows ARE genuinely historical (AAPL's 2019-01-29
   entry: EPS $4.18 vs forecast $4.17, matching Apple's real reported
   results) and those are what `earnings_calendar.py` uses.
2. **Split-adjustment mismatch between price and shares outstanding.**
   HF Data Library's close price is split-adjusted; SEC's raw shares-
   outstanding count is not (a 10-Q filed before a split reports the real
   share count from before that split). Naively multiplying them
   understated AAPL's 2019 market cap by ~4.2x — almost exactly its
   Aug-2020 4:1 split ratio. Fixed in `market_cap.py` by detecting
   split-sized jumps in the raw shares series and scaling historical
   shares forward by the cumulative ratio of later splits. Verified:
   AAPL market cap now computes to ~$659B (2015-03-16), ~$706B
   (2019-01-29), ~$3.0T (2023-07-27) — all consistent with real history.

Also carrying forward from the HF Data Library tool's own disclosed
caveats: **survivorship bias** in its ticker universe pre-2022, and an
**IEX source break on 2022-03-01** (volumes not comparable across it,
visible via the `source` column in raw bars: `pitrading` vs `iex`).

## Still open

- **Sigma's full research design** — section 3's exact test list, and
  confirmation the Stage 2/3/4 definitions here match Sigma's intent.
- **Phase 1 scope** — which tickers/universe size, date range within
  2015-2025, and whether to start observational (no defined entry rule
  yet, per your answer) or wait for a specific rule. You said scope would
  be shared later.
- `first_three_5min_pattern()` and the beta-filter test both need real
  data run through them at scale — mechanically ready, not yet executed.
