# Lambda Strategy Validation — Phase 0 (Infrastructure)

Status: **infrastructure built and unit-validated on synthetic data. No real
market data has been run through this yet** — see "Data blocker" below.

## What this is

Scaffolding for validating a Weinstein Stage-2/3/4 trend-based strategy
against Sigma's research design (full design doc not yet shared with
Lambda — placeholder in the original brief). Nothing here should be read
as a strategy result. It is the harness the result will run through.

## Files

- `stage_classifier.py` — Stage 1-4 classification via 50/150/200-day SMA
  (Minervini Trend Template rules, Weinstein-consistent state machine for
  Stage 1 vs 3 disambiguation). **Assumption pending Sigma's exact spec** —
  see docstring for the full rule list; only the constants/two rule
  functions need to change if Sigma's definition differs.
- `universe_filters.py` — ADV / ADTV / Price filters (fully implemented,
  pure functions of OHLCV). Market cap filter is stubbed — needs a
  point-in-time shares-outstanding source, not derivable from price data.
- `cost_model.py` — T+1 round-trip execution cost model (half-spread +
  square-root market impact + commission + slippage buffer), with LOW /
  BASE / HIGH scenarios for the mandatory cost-sensitivity test.
- `test_battery.py` — IS/OOS split, walk-forward, bootstrap CI, stage-
  stratified returns, year-by-year returns, beta-filter impact comparison.
  `first_three_5min_pattern()` raises `NotImplementedError` — it needs
  5-min/1-min T+1 bars that aren't connected yet.
- `tests/test_stage_classifier_synthetic.py` — builds a synthetic price
  path that cycles basing -> markup -> topping -> decline by construction
  and checks the classifier recovers the correct stage. **PASS** as of the
  last run (see below). This proves the rule logic is internally correct;
  it says nothing about whether the resulting strategy has edge on real
  data.

Run the synthetic check any time with:
```
python3 lambda_strategy_validation/tests/test_stage_classifier_synthetic.py
```

## Data blocker (read before running anything on real tickers)

Both free daily-OHLCV sources tried from this sandboxed session are
unreachable:
- `stooq.com` — serves a JavaScript proof-of-work anti-bot challenge
  instead of data (not a policy block — no denials in the egress proxy
  log; stooq is fingerprinting the sandbox as bot traffic).
- Yahoo Finance / `yfinance` — connection reset on every request.

No market-cap/fundamentals source and no 5-min/1-min intraday source has
been connected at all.

## What Lambda needs from you to move to Phase 1 (real data)

Pick whichever is easiest on your end:
1. **Upload files to Google Drive** (already connected in this session) —
   CSV/Parquet daily OHLCV + earnings dates + (ideally) shares
   outstanding/market cap history, and later the 5-min T+1 bars from HF
   Data Library. Lambda can read them directly via the Drive connector.
2. **Point Lambda at a GitHub repo** if the HF Data Library ships as a
   client/SDK repo — Lambda can attach it mid-session.
3. **An API endpoint + key** — if HF Data Library is a hosted API, give
   Lambda the base URL and how the key should be supplied (env var vs
   header) and Lambda will write the client.

Also still needed, independent of the data-access mechanism:
- Sigma's full research design (the brief called it "[to share later]")
  — specifically section 3's exact test list, and the exact Stage 2/3/4
  definitions if they differ from the Minervini/Weinstein synthesis coded
  here.
- The actual entry/exit rule to test (per your answer, this will emerge
  from observing the Stage classification on real data first — Phase 1
  should therefore start as descriptive/observational, not a live
  strategy backtest).
