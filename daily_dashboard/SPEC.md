# Meridian Capital Partners — Master Build Specification

**The single source of truth for this system.** It merges the original 7-layer
specification with the regime-conditioning overlay, reconciles the conflicts
between them, and records what is already built.

Where the two source documents disagreed, the resolution is stated inline and
marked **⚖️ RECONCILED**. Where a source contained an internal contradiction or
a stale API fact, it is marked **⚠️ CORRECTED**. Read those markers — they are
the parts where following either source alone would produce a broken system.

| | |
|---|---|
| **Project folder** | `daily_dashboard/` |
| **Repo** | `playandlearnhkg/risk-dashboard` |
| **Language** | Python (Layers 0–6), dashboard per Layer 7 |
| **Build status** | Layers 0–1 complete · Layer 2 next · 3–7 specified |

---

## 0. The governing model

Everything in this system is conditional on one equation:

> **Capital Availability = Money Available × Risk-on / Risk-off Behavior**

Layer 0 computes it and every layer above consumes it. Factor weights, sector
selection, position sizing, gross exposure and circuit breakers are all
functions of the current regime state — not fixed constants.

The combination is **multiplicative, not additive**. Money without appetite
does not bid; appetite without money cannot bid. A weighted average would let
a strong reading on one side mask a weak reading on the other, which is the
exact failure the model exists to prevent.

### Build order

Layer 0 first, then 1, then upward. Each layer consumes only the layers below
it and never reaches sideways. Layers 0 and 1 are built; the rest follow this
document.

---

## 1. Project structure

```
daily_dashboard/
├── config.yaml            ★ every tunable parameter — no thresholds in code
├── .env                   API keys (gitignored)
├── SPEC.md                this document
├── core/                  config loader, SQLite, logging
├── regime/                LAYER 0 — capital & regime engine        ✅ BUILT
├── data/                  LAYER 1 — all ingestion, no scoring      ✅ BUILT
├── factors/               LAYER 2 — 8 factors / 27 sub-factors     ← NEXT
├── analysis/              LAYER 3 — Claude AI analysis
├── portfolio/             LAYER 4 — MVO + conviction tilt
├── risk/                  LAYER 5 — veto, breakers, factor model
├── execution/             LAYER 6 — Alpaca paper
├── frontend/              LAYER 7 — dashboard
├── reporting/             LAYER 7 — P&L attribution, LP letters
├── cache/                 SQLite database + cached files
└── output/                CSVs, logs, reports
```

**Entry points** — one per layer, each runnable standalone:

```
run_regime.py    run_data.py      run_scoring.py    run_analysis.py
run_portfolio.py run_risk_check.py run_execution.py  run_dashboard.py
```

---

## 2. Cross-cutting requirements

These apply to every layer and are not repeated in each section.

1. **All parameters in `config.yaml`.** No threshold, weight, limit or date is
   hardcoded in a `.py` file. If a number can be argued about, it lives in
   config.
2. **Missing data is dropped and remaining weights re-normalised — never
   scored as neutral.** "No data" and "perfectly average" are different
   statements, and conflating them silently corrupts every score built on top.
   Every layer reports its own coverage percentage.
3. **Nothing raises on a data miss.** Only genuine programming errors
   propagate. A dead feed returns `None` and the run continues.
4. **Full logging** to console (skimmable) and `output/meridian.log` (complete).
5. **Fast-run flags** on every entry point so a daily run can skip the slow
   stages (`--no-filings`, `--no-13f`, `--quick`).
6. **Idempotent re-runs.** Every table's primary key is chosen so re-ingesting
   or re-scoring replaces rather than duplicates.
7. **Dark institutional aesthetic** for all UI, with colour never carrying
   meaning alone — always paired with a word or number.

---

## LAYER 0 — Capital & Regime Engine ✅ BUILT

Runs first, every day. Needs no database and no API key.

### Money availability indicators

| Indicator | Source | Weight | Method |
|---|---|---:|---|
| MMF AUM | FRED `MMMFFAQ027S` (fallback `RMFSL`) | 0.25 | percentile |
| Reverse repo | FRED `RRPONTSYD` | 0.20 | percentile, inverted |
| Margin debt YoY | FINRA CSV | 0.20 | ramp |
| Net liquidity | FRED `WALCL − WTREGEN − RRP` | 0.25 | trend percentile |
| Financial conditions | FRED `NFCI` | 0.10 | percentile, inverted |

### Risk-on / risk-off indicators

| Indicator | Source | Weight | Method |
|---|---|---:|---|
| VIX level | `^VIX` → FRED `VIXCLS` | 0.22 | ramp |
| VIX term structure | `^VIX / ^VIX3M` | 0.13 | ramp |
| HY credit spread | FRED `BAMLH0A0HYM2` | 0.25 | ramp |
| Copper / gold | `HG=F / GC=F` | 0.15 | trend percentile |
| AUD/JPY | `AUDJPY=X` | 0.15 | trend percentile |
| High-beta vs defensive | `SPHB / SPLV` → `XLY / XLP` | 0.10 | trend percentile |

### Three scoring methods

- **ramp** — between two absolute thresholds. For series whose levels mean
  something in themselves (VIX at 30 is stress regardless of history).
- **percentile** — rank in trailing distribution. For series with no natural
  scale or a drifting one (Fed balance sheet, MMF AUM both grow structurally).
- **trend_percentile** — percentile of the N-day rate of change. For series
  where direction carries the signal and level does not (copper/gold, AUDJPY).

### Outputs

- Composite regime score 0–100
- Regime label: Strong Risk-On / Mild Risk-On / Neutral / Mild Risk-Off /
  Strong Risk-Off
- **Capital availability: High / Medium / Low — from the money half alone.**
  Deliberately not from the composite, so the system can report *"money is
  abundant but nobody wants risk"*, which is the setup that precedes violent
  recoveries.
- Regime-conditional factor multipliers (consumed by Layer 2)
- Asset-class and equity-sector preference matrices
- Weekly process checklist status

### Preference matrices

Both score −2 (strong underweight) to +2 (strong overweight) per regime, in
`config.yaml`. The sector scan **blends matrix stance with live relative
strength, 60/40**: the matrix encodes what *should* lead, relative strength
measures what *is* leading. Set `momentum_weight: 0` for pure theory or
`matrix_weight: 0` for pure trend-following.

### Weekly process

1. Macro & Volatility / Regime Check — *auto*
2. Capital Availability Assessment — *auto*
3. Sector Rotation Scan — *auto*
4. **Opportunity Filter & Edge Review — manual, by design.** Articulating why
   an edge exists cannot be automated; auto-completing it would make the
   checklist theatre.

### A deliberate tension — do not "fix" this

Rising margin debt **raises** money availability in Layer 0 while **raising
fragility** in Layer 5. That is intentional. Leverage genuinely does add
buying power on the way up and genuinely does amplify the way down. The system
holds both facts rather than averaging them into something that means neither.

At the time of writing, margin debt sits at a record and is growing ~49% YoY,
so Layer 0 reads Strong Risk-On *because of* a condition Layer 5 will treat as
maximum leverage stress. Both are correct. The combination is the signature of
a late-cycle, leverage-fuelled advance.

---

## LAYER 1 — Data Infrastructure ✅ BUILT

Pure ingestion into SQLite. No scoring, no analysis.

```bash
python3 run_data.py [--no-filings] [--no-13f] [--quick] [--stage X] [--tickers A,B]
```

### Sources

1. **Universe** (`data/universe.py`) — S&P 500 from Wikipedia with ticker,
   company name, GICS sector, sub-industry. Cached, refreshed weekly. Plus
   benchmarks (SPY, QQQ, IWM, DIA), the 11 sector ETFs, and the Layer 0 macro
   tickers (`^VIX`, `^VIX3M`, TLT, HYG, LQD, `HG=F`, `GC=F`, `CL=F`,
   `AUDJPY=X`, `USDJPY=X`, DXY, SPHB, SPLV, GLD, DBC, EFA, EEM, SHY, BIL).
2. **Market data** (`data/market_data.py`) — daily OHLCV, incremental, into
   `daily_prices`.
3. **Fundamentals** (`data/fundamentals.py`) — quarterly + annual income
   statement, balance sheet, cash flow, plus **24 derived ratios**: ROE, ROA,
   gross/operating/net margin, revenue growth YoY/QoQ, earnings growth
   YoY/QoQ, debt/equity, FCF yield, current ratio, AR/revenue, CFO/NI,
   accruals ratio, retained earnings, working capital, total liabilities,
   EBIT, R&D expense, shares outstanding, dividends paid, buybacks, asset
   turnover.
4. **SEC filings** (`data/sec_data.py`) — EDGAR, User-Agent with email, 8
   req/sec. Latest 10-K (Risk Factors extracted), latest 10-Q (MD&A), recent
   8-K, Form 4 over 180 days.
5. **Institutional** (`data/institutional.py`) — 13-F for Citadel, Point72,
   Bridgewater, Tiger Global, Third Point, Berkshire, Appaloosa, Baupost,
   Pershing Square. Funds-holding count, net change, multi-fund opening flag.
6. **Short interest** (`data/short_interest.py`) — daily snapshots.
7. **Analyst estimates** (`data/estimates.py`) — daily snapshots.
8. **Earnings calendar** (`data/earnings_calendar.py`) — next 30 days.
9. **Transcripts** (`data/transcripts.py`) — FMP, candidates only.

### Three decisions worth knowing

**Incremental fetch with 5-day overlap.** Prices resume from each ticker's
last stored date *minus 5 days*. Vendors restate recent bars (late splits,
dividend adjustments) and a strict resume freezes the first version forever.

**Daily snapshots of fortnightly data.** Short interest and estimates are
snapshotted every run because no free provider serves *history*. Until ~30
days accumulate, Layer 2's revisions factor is degenerate — the run summary
reports how many days remain.

**Form 4 signal vs noise.** Only codes **P** (open-market purchase) and **S**
(sale) are marked `is_signal = 1`. Grants (A), option exercises (M), tax
withholding (F) and gifts (G) are stored but excluded. On a two-ticker test
this was 60 signal rows out of 124 — **half the data is compensation
mechanics**, and counting a vesting event as insider buying is the most common
way this data gets misread.

### Provider abstraction

`data/providers.py` routes by role. `TradingViewProvider` and `FutuProvider`
exist as explicit stubs marking the seam — implementing them means satisfying
the documented contract and changing one config line.

```yaml
data:
  providers:
    market_data: yfinance   # → tradingview | futu | polygon | fmp
```

Active provider is logged on every run.

---

## LAYER 2 — Scoring Engine ← BUILD NEXT

8 factors, 27 sub-factors. **All scores are 0–100 percentile ranks within GICS
sector.** Sub-factors are equal-weighted within each parent factor, then the
parent is sector-percentile-ranked.

### 1. Momentum (`factors/momentum.py`) — 6 sub-factors

12-1 month return (skip most recent month to avoid short-term reversal);
6-month return; 3-month return; acceleration (recent 3m minus older 3m);
52-week-high proximity (price ÷ 52w high); relative strength vs sector ETF
(6m stock return minus sector ETF return).

*The sector-relative sub-factor isolates stock-specific momentum from sector
beta — without it this factor mostly measures which sector a name is in.*

### 2. Value (`factors/value.py`) — 6 sub-factors

Forward earnings yield (1 ÷ forward P/E); book-to-price; FCF yield; EV/EBITDA
(inverted); shareholder yield (TTM buybacks + dividends ÷ market cap);
sales-to-EV (revenue ÷ EV — works where P/E breaks on negative or volatile
earnings).

### 3. Quality (`factors/quality.py`) — 8 sub-factors

ROE stability (std dev of trailing ROEs, inverted); gross margin level; gross
margin trend (latest minus 4Q ago); debt/equity (inverted); CFO/NI (higher =
real cash earnings); accruals ratio ((NI−CFO)/TA, inverted — high accruals
predict underperformance).

**Piotroski F-Score (0–9)** — nine binary tests: positive ROA, positive CFO,
rising ROA, CFO > NI, falling D/E, rising current ratio, no dilution, rising
gross margin, rising asset turnover.

**Altman Z-Score** = 1.2(WC/TA) + 1.4(RE/TA) + 3.3(EBIT/TA) + 0.6(MktCap/TL)
+ 1.0(Sales/TA). Bands: >2.99 safe, 1.81–2.99 grey zone, <1.81 distress.

> ⚠️ **CORRECTED — Piotroski colour thresholds.** The source spec says
> "green ≥3, amber <3" for a 0–9 score. On the standard interpretation 8–9 is
> strong and ≤3 is *weak*, so that mapping paints almost every stock green and
> the signal disappears. Use **green ≥7, amber 4–6, red ≤3**, and put the
> boundaries in `config.yaml` so they can be retuned. Altman's bands are
> standard and unchanged, except that <1.81 should be **red**, not amber —
> otherwise nothing in the quality factor can ever show red.

### 4. Growth (`factors/growth.py`) — 5 sub-factors

Revenue growth YoY; earnings growth YoY; revenue growth acceleration (latest
YoY minus 4Q-ago YoY); R&D intensity (R&D ÷ revenue); free cash flow growth
YoY (harder to manipulate than earnings growth).

*Growth off a negative or zero base is not meaningful — a loss shrinking from
−100 to −50 is not "+50% growth". Those cases return None, not a number that
would rank confidently and wrongly.*

### 5. Estimate Revisions (`factors/revisions.py`) — 3 sub-factors

30-day, 60-day and 90-day change in consensus next-quarter EPS. Equal-weight
the deltas that are available.

**Degenerate until ~30 days of snapshots exist** — every score is 50, and the
run must say so explicitly rather than letting a flat factor pass as a real
one.

### 6. Short Interest (`factors/short_interest.py`) — 3 sub-factors

Short percent of float; days to cover; change vs prior period.

**Direction is book-dependent:** for LONGS, declining short interest scores
higher; for SHORTS, increasing scores higher. This is the one factor whose
sign flips between books.

### 7. Insider Activity (`factors/insider.py`) — 3 sub-factors

Net dollar flow over 90 days; CEO/CFO open-market purchases weighted **3×**
other insiders; cluster-buy bonus (3+ distinct insiders within 30 days).

Only codes P and S count. No data → sector median (50), not zero.

### 8. Institutional Flow (`factors/institutional.py`) — 3 sub-factors

Number of tracked funds holding; net change in aggregate holdings vs prior
quarter; multi-fund simultaneous opening flag (3+ funds opening new positions
in the same name).

### Composite (`factors/composite.py`)

Base weights:

| Factor | Weight |
|---|---:|
| Momentum | 0.20 |
| Value | 0.20 |
| Quality | 0.20 |
| Estimate Revisions | 0.15 |
| Insider Activity | 0.10 |
| Growth | 0.10 |
| Short Interest | 0.05 |
| Institutional Flow | 0.05 |

After blending, **re-rank within sector** for the final 0–100 composite.
Top quintile → LONG candidates. Bottom quintile → SHORT candidates.

### ⚖️ RECONCILED — regime-conditional weights

The two sources define the regime differently:

| Source | Regime definition |
|---|---|
| Original spec | `factors/regime_weights.py` — VIX-only buckets: Low Vol <15 (momentum 0.28, value 0.10), Normal 15–25 (default), High Vol >25 (quality 0.28, momentum 0.10) |
| Regime overlay | Multipliers from Layer 0's 5-level regime |

**Resolution: Layer 0 is authoritative.** The multipliers already exist in
`config.yaml` under `regime.factor_multipliers` — Layer 2 **reads** them, it
does not define its own. The VIX-only buckets are retained in
`factors/regime_weights.py` strictly as a **fallback** for when Layer 0 has
not run today (stale `regime_history`, or `--no-regime`). The fallback logs a
warning; it must never be the silent default.

Applying multipliers: multiply each base weight, then **renormalise to sum to
1.0**. Without renormalisation, Strong Risk-On (which raises more weights than
it cuts) inflates total weight and the composite drifts off the 0–100 scale.

### ⚖️ RECONCILED — Regime Fit score

The overlay adds a Regime Fit score "measuring alignment with currently
favored sectors from Layer 0". It must be a **separate column, not folded into
the composite.**

Reason: folding it in makes a high-conviction name in an out-of-favour sector
numerically indistinguishable from a mediocre name in a favoured one, and
those are different situations calling for different actions. Kept separate,
Layer 4 can tilt on it and Layer 7 can show it as a second axis.

Definition, 0–100:

```
regime_fit = 100 * (sector_matrix_score + 2) / 4     # −2..+2 → 0..100
           blended with the sector's live relative-strength rank,
           using the same matrix_weight / momentum_weight from config
```

For SHORT candidates the scale inverts — a name in a −2 sector is a *good*
short fit.

### Crowding Detection (`factors/crowding.py`)

Synthesise daily factor returns, compute pairwise correlations, flag when
deviation from the historical norm exceeds 0.4. Crowding means the factors are
no longer providing independent information, so a diversified-looking book is
really one bet.

### Output

`output/scored_universe_latest.csv` — every sub-factor score, each parent
factor score, the composite, LONG/SHORT flag, and Regime Fit.

```bash
python3 run_scoring.py                 # full universe
python3 run_scoring.py --ticker AAPL   # single-stock detail
```

Print: top 5 longs, top 5 shorts, crowding warnings, **degenerate factor
warnings** (which factors are flat and why).

---

## LAYER 3 — Claude AI Analysis

The qualitative analyst: reads filings, financials and insider data.

### ⚠️ CORRECTED — model, cost and API surface

The source spec was written against an older API. These are the current facts
and following the original would produce runtime errors:

| Item | Source spec | Correct |
|---|---|---|
| Model | `claude-sonnet-4-5` | **`claude-opus-5`** (default; configurable) |
| Thinking | — | Adaptive, **on by default** on Opus 5. `budget_tokens` is **removed** — sending it returns HTTP 400. Control depth with `output_config: {effort: ...}` |
| JSON output | "handle raw JSON, ```json fences" | Use **structured outputs** (`output_config: {format: {...}}`) — guaranteed schema conformance, no fence-stripping. Assistant **prefill is removed** and returns 400 |
| Refusals | — | Check `stop_reason == "refusal"` before reading content; `stop_details` is populated only then |
| Cost estimate | "$2–5 per full run using Sonnet" | Recompute — see below |

**Pricing per 1M tokens:** Opus 5 $5 in / $25 out · Sonnet 5 $3 / $15 ·
Haiku 4.5 $1 / $5. Cache writes ≈1.25×, cache reads ≈0.1×.

**Use the Message Batches API.** A 40-candidate run is not latency-sensitive
and batching costs **50% less**. Submit with `custom_id` per candidate, poll
`processing_status` until `ended`, then key results by `custom_id` — results
arrive in **any order**, never rely on position.

Default `analysis.cost_ceiling_usd: 25` in config, aborting mid-run if
exceeded. Set the model in config so cost/quality is your decision, not the
code's.

### Components

1. **API client** (`analysis/api_client.py`) — official `anthropic` Python
   SDK. Prompt caching (`cache_control: {type: "ephemeral"}`) on every system
   prompt; minimum cacheable prefix is ~1024 tokens and there are at most 4
   breakpoints per request. Keep stable content first and volatile content
   (ticker, timestamps) after the last breakpoint, or the cache silently never
   hits. **Verify with `usage.cache_read_input_tokens` — if it is zero across
   repeated runs, something in the prefix is varying.** Retry 429/5xx with
   exponential backoff; catch typed exceptions most-specific-first, not one
   broad class.
2. **Cost tracker** (`analysis/cost_tracker.py`) — read `usage` after every
   call: input, output, cache-write, cache-read. Hard ceiling aborts the run.
3. **Analysis cache** (`analysis/cache.py`) — SQLite `analysis_results` keyed
   by (analyzer, ticker, artifact_id), 30-day TTL. Re-running the same
   artifact is free.
4. **Earnings call analyzer** — transcript in (truncate 120K chars). Scores
   1–10 on Management Confidence, Revenue Guidance, Margin Trajectory,
   Competitive Position, Risk Factors, Capital Allocation. JSON out with
   per-category reasoning, bull_case, bear_case, key_quotes, one_line_summary.
   Returns None with no transcript.
5. **Filing analyzer** — 8 quarters of metrics, forensic accounting review:
   earnings quality (CFO vs NI), revenue quality (AR vs revenue), balance
   sheet, accruals. JSON: earnings_quality_score, balance_sheet_score,
   red/green flags, risk_level.
6. **Risk analyzer** — 10-K Risk Factors (HTML stripped, 80K cap). Separate
   material risks from boilerplate; flag new risks vs prior filing. JSON:
   new_risks, material_risks, boilerplate_percentage, risk_severity.
7. **Insider analyzer** — Form 4 last 90 days. Routine selling vs meaningful
   buying. JSON: signal_strength (STRONG BUY → STRONG SELL), confidence,
   key_transactions, reasoning.
8. **Sector analysis** — per sector, rank by fundamental quality and
   positioning. Output rankings, top_long_idea, top_short_idea,
   sector_outlook.
9. **Regime Context Analyzer** *(new)* — takes the Layer 0 state and the
   candidate, and answers: does this thesis depend on the current regime
   persisting? What would break it if capital availability turned Low? Output
   JSON: regime_dependency (HIGH/MEDIUM/LOW), thesis_fragility, what_breaks_it.
10. **Combined score** (`analysis/combined_score.py`) — **60% quantitative
    composite + 40% Claude**. If no Claude analysis is available, use 100%
    quantitative with **no penalty** — absence of qualitative data is not
    negative evidence. Re-rank within sector.
11. **Report generator** — per candidate, markdown to
    `output/reports/[timestamp]/[TICKER].md`.

```bash
python3 run_analysis.py --estimate-cost      # dry-run token/cost estimate
python3 run_analysis.py --ticker AAPL
python3 run_analysis.py --sector Technology
```

---

## LAYER 4 — Portfolio Construction

Two optimisers, selectable per run.

### 1. MVO optimiser (`portfolio/mvo_optimizer.py`)

Markowitz via `scipy.optimize.minimize` (SLSQP).

- **Expected returns:** composite mapped linearly — score 100 → +15%/yr,
  score 0 → −15%/yr.
- **Covariance:** 120-day historical, later replaced by the factor covariance
  matrix from Layer 5.
- **Risk aversion λ:** default 1.0.
- **Transaction costs** subtracted from gross expected return so the optimiser
  sees net-of-cost returns.
- **Objective:** maximise `μᵀw − λ·wᵀΣw`.
- **Constraints:** long weights sum to target long gross; short weights to
  target short gross; per-position `[min_pct, max_pct]`; `|w_beta| ≤ 0.15`;
  `|sector_net| ≤ 5%`; single-side sector ≤ 25%.
- **On non-convergence:** log a warning and fall back to conviction-tilt.
  Never fail the run.

### 2. Conviction-tilt optimiser (`portfolio/optimizer.py`)

Equal weight base within each book. Top 5% of scores get 1.5×, top 10% get
1.25×. Liquidity cap: no position > 5% of 20-day ADV. Earnings: halve size if
reporting within 5 days. Beta adjustment so beta-adjusted exposure matches
1.0. Sector neutral.

### 3. Transaction cost model (`portfolio/transaction_costs.py`)

Three components in bps: commission ($0 on Alpaca); spread cost (5% of average
daily high-low range); market impact (`coef · sqrt(trade_size/ADV) ·
daily_vol_bps`, coef 0.10).

### 4. Rebalance schedule (`portfolio/rebalance_schedule.py`)

Advisory warnings only — never blocks trading. Checks: positions with earnings
within 2 days; FOMC within 5 days; monthly opex within 3 days (third Friday).

> **Note:** FOMC and BOJ dates already live in `config.yaml` under
> `regime.weekly_process` / the Layer 0 calendar. Read them from there rather
> than hardcoding a second copy that will drift.

### 5–8. Supporting modules

- **Portfolio state** (`state.py`) — tables `portfolio_positions`,
  `portfolio_history`, `position_approvals`. Tracks ticker, shares, entry
  price/date, current price, unrealised P&L, sector, factor scores at entry.
  Handles corporate actions.
- **Beta calculator** (`beta.py`) — rolling 60-day beta vs SPY; long-book,
  short-book and net portfolio beta.
- **Factor exposure** (`factor_exposure.py`) — weighted average factor score
  across each book; flag spreads beyond 1 SD of history.
- **Rebalance generator** (`rebalance.py`) — diff current vs target, apply a
  30% turnover budget, prioritise largest score changes, estimate costs.
  `--whatif` shows proposed changes without committing.

### ⚖️ RECONCILED — regime-conditional portfolio rules

Gross exposure, sector limits and beta targets adapt to Layer 0. Add to
`config.yaml`:

| Regime | Gross target | Net range | Max sector | Notes |
|---|---:|---|---:|---|
| Strong Risk-On | 150% | 0 to +15% | 25% | Full risk budget |
| Mild Risk-On | 140% | 0 to +10% | 25% | |
| Neutral | 120% | −5 to +5% | 20% | |
| Mild Risk-Off | 90% | −10 to +5% | 20% | Trim gross first |
| Strong Risk-Off | 60% | −15 to 0% | 15% | Defensive |

Additionally, when **Capital Availability = Low**, cap gross at the Neutral
level regardless of the behaviour half — cheap money is what finances a
leveraged book, and its absence binds harder than sentiment.

Base config: `num_longs=20, num_shorts=20, max_position=5%, max_sector=25%,
gross=150%, net=[0,+10]%, max_beta=0.15, turnover_budget=30%,
mvo_risk_aversion=1.0`.

```bash
python3 run_portfolio.py --rebalance | --whatif | --current
python3 run_portfolio.py --optimize-method mvo | conviction
```

---

## LAYER 5 — Risk Management

**Absolute veto power.** Risk overrides every other layer including a human
override flag; the only way past a veto is to change the position, not the
check.

### Factor risk model (`risk/factor_risk_model.py`)

Barra-style cross-sectional regression. For each day *t* in a 120-day
lookback: `r_i,t = α_t + Σ_k β_k,t · F_k,t + ε_i,t`, where `F_k,t` is stock
*i*'s standardised factor exposure (z-scored 0–100 sector ranks).

Produces daily factor returns, an annualised factor covariance matrix, and
per-stock specific variance. Portfolio: `factor_var = wᵀ(FΣFᵀ)w`,
`specific_var = Σ wᵢ²·specᵢ`, `total_var = factor_var + specific_var`.

`MCTR_i = w_i · cov(r_i, r_p) / σ_p`. **Flag where MCTR > 1.5× weight** — that
is a position contributing far more risk than capital, which is the definition
of a hidden concentration.

Feed the predicted covariance matrix back to Layer 4's MVO optimiser.

### Pre-trade veto (`risk/pre_trade.py`) — 8 checks, any failure = REJECT

1. Halt lock exists?
2. Earnings blackout (within 5 days → 50% size cut)
3. Liquidity < 5% ADV
4. Sector < 25%
5. Gross ≤ 165%, net ∈ [−10%, +15%]
6. |net beta| ≤ 0.20
7. Pairwise correlation ≤ 0.80 with existing positions
8. Regime gate — see below

**Closing and covering trades are always approved.** Risk management that can
block a de-risking trade is broken.

Log every rejection with timestamp and reason.

> **Note on the apparent contradictions with Layer 4.** Layer 4 targets gross
> 150% and |beta| 0.15; Layer 5 vetoes above 165% and 0.20. This is
> intentional — Layer 4 holds the *target*, Layer 5 the *hard limit*, and the
> gap absorbs intraday drift without tripping a veto on every market move.

### Circuit breakers (`risk/circuit_breakers.py`)

| Trigger | Action |
|---|---|
| Daily loss > 1.5% | SIZE DOWN 30% |
| Weekly loss > 4% | SIZE DOWN 30% |
| Drawdown > 8% | **KILL SWITCH** — lock file, cleared only by `--clear-halt` |
| Single-position loss > 3% of NAV | Force-close that position |

> ⚠️ **CORRECTED — a real contradiction in the source spec.** The original
> reads *"Single position > 3% NAV → force-close immediately"* while Layer 4
> sets `max_position = 5%`. Taken literally, every position between 3% and 5%
> would be force-closed the moment it was opened, so the portfolio could never
> hold a full-size position. The coherent reading is **single-position
> LOSS > 3% of NAV**, which is what a circuit breaker is for. Adopted above.
> If you intended a size trigger instead, it must be set above
> `max_position` — put it in config either way.

### Monitors

- **Factor monitor** — z-score each factor spread (long minus short) vs the
  universe cross-sectional std; alert when |z| > 1.5σ.
- **Correlation monitor** — 60-day rolling pairwise correlation within each
  book; alert if average within-book > 0.60.
- **Tail risk monitor** — VIX ≥ 25 → REDUCE GROSS 20%; VIX ≥ 35 → REDUCE
  GROSS 50%; credit spread z ≥ 1σ widening → REDUCE GROSS 20%.
- **Stress testing** — 6 scenarios, including at minimum: 2008 credit crisis,
  2020 COVID crash, 2022 rate shock, a yen carry unwind, a sector rotation
  shock, and a factor-crowding unwind.

### ⚖️ RECONCILED — regime circuit breakers, and how they stack

The overlay adds regime-based breakers. Add:

| Trigger | Action |
|---|---|
| Regime score falls > 20 points in 5 days | REDUCE GROSS 25% |
| Capital Availability turns Low | REDUCE GROSS 25%, no new longs |
| Regime = Strong Risk-Off | REDUCE GROSS 40% |

**Reductions do not compound — apply the single largest.** VIX ≥ 35 (−50%)
plus Strong Risk-Off (−40%) plus Capital Low (−25%) would otherwise stack to
−115% and command a negative book. Take the maximum single reduction and log
every trigger that fired, so the reasoning stays visible.

```bash
python3 run_risk_check.py [--stress] [--tail-only] [--clear-halt]
```

---

## LAYER 6 — Execution

Alpaca paper trading. **Defaults to paper; live requires an explicit config
change plus a CLI flag.**

1. **Broker** (`execution/broker.py`) — Alpaca via `ALPACA_API_KEY` /
   `ALPACA_SECRET_KEY`. Paper URL is the default.
2. **Order executor** (`execution/executor.py`) — per trade: (a) pre-trade
   veto, (b) short availability, (c) limit price `close × (1 ± 0.001)`,
   (d) chunk orders > 2% ADV, (e) 120s time-in-force, (f) poll every 5s,
   (g) cancel and retry on timeout, max 3×, (h) record `signal_price` for
   slippage.
3. **Slippage tracker** (`execution/costs.py`) — `(fill − signal) / signal ×
   10,000` bps. 30-day rolling avg, median, p95. Surface the worst 5 fills.
4. **Short availability** (`execution/short_check.py`) — Alpaca `shortable` +
   `easy_to_borrow`, cached 7 days.
5. **Order manager** (`execution/order_manager.py`) — track
   pending/partial/filled/cancelled. **SIGINT → cancel pending orders, keep
   positions.** Never liquidate on interrupt.

```bash
python3 run_execution.py --dry-run    # log what would happen
python3 run_execution.py --execute
```

---

## LAYER 7 — Dashboard & Reporting

### ⚖️ RECONCILED — Streamlit vs Next.js *(confirm before building)*

| Source | Says |
|---|---|
| Original spec | Streamlit at `localhost:8502`, JARVIS persona |
| Regime overlay | Streamlit, institutional dark |
| Earlier standalone note | "Next.js + Tailwind + shadcn/ui recommended" |

**Recommendation: Streamlit.** Two of three sources say so, the existing
risk-dashboard app in this repo is already Streamlit, and — the substantive
reason — Layers 0–6 are Python, so Streamlit reads the same SQLite connection
and pandas objects directly. Next.js requires building and maintaining a REST
layer over everything below, which is real work that buys a nicer mobile
experience and little else here.

Choose Next.js only if phone usability is the priority. **Confirm before Layer
7 is built** — this is the one decision that is expensive to reverse.

### Persistent status bar (always visible)

Regime label + composite score · Capital Availability · VIX · HY spread ·
gross/net exposure · any active circuit breaker. This bar is on every page —
the regime is the context for everything else and should never require a click
to see.

### Navigation — 5 pages

> ⚖️ **RECONCILED.** The original had four pages (I Portfolio, II Research,
> III Risk, IV Performance). The overlay adds Regime & Capital Flow as the
> highest-priority page. Result: five pages, with Regime first, since it is
> the layer everything else is conditional on.

**I · Regime & Capital Flow** *(new, highest priority)* — full Layer 0
visualisation: money vs behaviour gauges, every indicator as a card with
sparkline and trend, the composite over time, sector preference matrix, asset
class preference matrix, weekly process checklist with the manual step
actionable from the page.

**II · Portfolio** — JARVIS cover treatment (92px title, "LONG/SHORT HEDGE
FUND ANALYST" 11px small caps), 10 headline metrics, long and short books,
status strip with VIX regime badge.

**III · Research & Candidates** — KPIs, crowding warnings, rebalance advisory,
factor heatmap, candidate cards showing factor scores + Claude summaries +
Regime Fit, with an Execute button.

**IV · Risk** — circuit breaker bars, risk decomposition donut, factor risk
contributions, MCTR table (highlighting MCTR > 1.5× weight), stress tests.

**V · Performance** — P&L attribution, win/loss, sector-relative, turnover.

### Reporting engine

- Daily P&L attribution (`reporting/pnl_attribution.py`)
- Position attribution — mark-to-market, FIFO round-trips
- Win/loss analysis
- Sector-relative performance
- Turnover analytics
- **Claude weekly commentary** — JARVIS-authored
- **Daily LP letter** — 3–4 paragraphs, letterhead, signature block, and
  **explicitly referencing the current Capital & Regime state** and what would
  change the posture

### Placeholder data

The dashboard must render immediately with realistic placeholder data before
the full pipeline has run — but **every placeholder must be visibly labelled
as such**, exactly as Layer 1 flags placeholder margin data. Unlabelled
plausible fake numbers on a trading dashboard are worse than blank panels.

---

## 3. Summary of reconciliations and corrections

| # | Issue | Resolution |
|---|---|---|
| 1 | Project folder: `ls_equity_fund` vs `meridian_capital` vs `daily_dashboard` | **`daily_dashboard/`** — as built |
| 2 | Regime: VIX-only buckets vs Layer 0's 5-level state | **Layer 0 authoritative**; VIX buckets are a logged fallback only |
| 3 | Regime Fit placement | **Separate column**, not folded into composite |
| 4 | Factor multipliers | Read from `config.yaml`; **renormalise to 1.0** after applying |
| 5 | Piotroski colour bands ("green ≥3" on a 0–9 scale) | **Green ≥7, amber 4–6, red ≤3** |
| 6 | Altman distress band shown as amber | **Red** |
| 7 | Claude model `claude-sonnet-4-5` | **`claude-opus-5`**, configurable |
| 8 | `budget_tokens`, prefill, JSON-fence parsing | Removed/400 on current models — use **adaptive thinking + `effort`** and **structured outputs** |
| 9 | Cost estimate "$2–5 per run" | Recompute at current pricing; **use Batches API for 50% off** |
| 10 | Layer 4 gross 150% vs Layer 5 veto 165% | Intentional target-vs-limit gap; documented |
| 11 | "Single position > 3% NAV → force-close" vs `max_position = 5%` | Read as **single-position LOSS > 3% of NAV** |
| 12 | Multiple gross-reduction triggers | **Apply the largest, do not compound** |
| 13 | Dashboard: Streamlit vs Next.js | **Streamlit recommended** — confirm before Layer 7 |
| 14 | Nav: 4 pages vs 5 | **5 pages, Regime first** |
| 15 | FOMC dates hardcoded in two layers | Single copy in `config.yaml` |

---

## 4. Open decisions

1. **Layer 7 stack** — Streamlit (recommended) or Next.js. Blocks Layer 7 only.
2. **Claude model** — `claude-opus-5` default. Haiku 4.5 would cut Layer 3
   cost ~80% at some quality cost; your call, not the code's.
3. **Live trading** — Layer 6 defaults to paper indefinitely. Going live
   should be a deliberate, separate decision after a paper track record.
