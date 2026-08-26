# Product & Technical Specification
## Meridian Capital Partners + risk-dashboard

| | |
|---|---|
| **Document version** | 1.0 |
| **Date** | 2026-08-26 |
| **Repository** | `playandlearnhkg/risk-dashboard` |
| **Branch** | `claude/meridian-layer0-layer1` |
| **Status of code described** | As at commit `a82a459` |
| **Audience** | Engineering manager; incoming developer |
| **Related document** | `daily_dashboard/SPEC.md` — the *build* specification for all 7 layers. This document describes what **is**; SPEC.md describes what is **intended**. |

---

## 1. Executive Summary

### What the system does

Two related but currently **separate** applications live in one repository:

1. **risk-dashboard** — a working Streamlit web application that scores global systematic risk daily from free data (Yahoo Finance, FRED, FINRA). It produces a 0–100 stress score labelled Low / Elevated / High, across eight components, with a heavy focus on the yen carry trade.

2. **Meridian Capital Partners** (`daily_dashboard/`) — a planned seven-layer long/short equity system. **Layers 0 and 1 are built and running. Layers 2 through 7 do not exist.** Layer 0 is the regime engine implementing *Capital Availability = Money Available × Risk-on/Risk-off Behaviour*. Layer 1 is the data infrastructure: a ~530-ticker universe with prices, fundamentals, SEC filings, insider transactions and 13-F holdings in SQLite.

### Current status vs intended direction

| | Current | Intended |
|---|---|---|
| Dashboard framework | Streamlit | **Marimo** |
| Data processing | pandas | **Polars** |
| Meridian layers built | 0 and 1 of 7 | All 7 |
| Frontend integration | One JSON status file | Full regime page with historical trends |

The Marimo and Polars direction is **documented preference only — no migration code has been written.** This document is the first artefact of that direction.

### Key risks a manager should know

| # | Risk | Severity | Detail |
|---|---|---|---|
| 1 | **Two scoring systems run on inverted scales** | **High** | risk-dashboard's composite: 100 = maximum *stress*. Meridian's composite: 100 = maximum *risk-on*. Both are displayed as "0–100". A reader who confuses them reads the market exactly backwards. Not yet reconciled in code or UI. |
| 2 | Meridian is 2/7 complete | High | The layers that generate trade candidates, size positions and manage risk (2, 4, 5) do not exist. The system today informs judgement; it does not produce trades. |
| 3 | Yahoo Finance rate limiting | Medium | Yahoo returns HTTP 429 persistently from shared and cloud IPs. Full-universe price refresh **must** run on a local machine. Mitigations are implemented but this constrains deployment. |
| 4 | Layer 1 verified on one machine only | Medium | Stages 2–7 (prices, fundamentals, short interest, estimates, earnings) have never completed in the development sandbox because of item 3. They are proven only by the owner's Windows run. |
| 5 | Historical regime data is collected but never displayed | Medium | `regime_history` accumulates one row per day. No user interface reads it. The trend view — explicitly a high-priority requirement — is not built. |
| 6 | Migration cost is real | Medium | 216 pandas call sites across 17 files; 234 Streamlit call sites. A Marimo + Polars migration is a rewrite of the presentation and data layers, not a swap. |
| 7 | Single maintainer, no tests | Medium | There is no automated test suite. Correctness has been established by targeted manual verification, documented per fix in commit messages. |

---

## 2. Purpose of the Dashboard

### Why it exists

The owner manages personal capital and needs a **single daily read on whether the macro environment is supportive or hostile**, without paying for a terminal and without reading twenty sources each morning.

### The problem it solves

Systematic risk is not visible in any one number. It builds across funding markets, credit, volatility, leverage and currency carry simultaneously — and each of those has its own vendor, its own units and its own release schedule. By the time it is obvious in equity prices, the information advantage is gone.

Three specific failures the system is designed to prevent:

1. **Averaging away a dangerous combination.** A wide US–Japan rate differential is not stress. A falling USDJPY is not necessarily stress. Both at once, moving fast, is a forced carry unwind. A weighted average buries this; escalation rules do not.
2. **Silently scoring a dead feed as neutral.** "No data" and "perfectly average" are different statements. Every model here drops unavailable inputs and re-normalises, then reports coverage.
3. **Confusing money with appetite.** Abundant liquidity in a risk-off posture is not available capital. This is why Meridian's core model multiplies rather than adds.

### Who it is for

**Primary and currently only user: the repository owner**, as a personal daily monitoring and decision-support tool. Not a product, not multi-tenant, no authentication, no user accounts.

Secondary audiences created by this document: an engineering manager assessing state and cost, and a developer taking over the work.

### What decisions it supports

| Decision | Supported by |
|---|---|
| Do I reduce or add equity exposure today? | risk-dashboard composite + regime band |
| Is it safe to add leverage? | Leverage component; `leverage_at_peak_and_vol_rising` escalation |
| Is the yen carry trade unwinding? | Carry & FX tab; `carry_unwind` escalation |
| Which asset classes should I favour? | Meridian asset-class preference matrix |
| Which equity sectors should I hunt in? | Meridian sector rotation scan |
| Is there money available to be deployed at all? | Meridian Capital Availability status |
| Am I looking at complete data? | Data-sources panel; coverage percentage |

**Explicit non-goals.** The system does not place orders, does not size positions, does not tell you what to buy, and does not claim predictive accuracy. Thresholds are judgement calls, chosen to be readable and editable — **nothing in either model is fitted to historical data or backtested.**

---

## 3. Information the Dashboard is Designed to Provide

Legend: **✅ Built** · **⚠️ Partial** · **📋 Planned**

### 3.1 Capital Availability status — ✅ Built (Meridian, console only)

**What it means.** High / Medium / Low, derived from the *money* half of the model alone — money-market fund assets, reverse repo balances, margin debt growth, net liquidity and financial conditions.

**Why it is useful.** Deliberately separated from risk appetite so the system can say *"money is abundant but nobody wants risk"* — historically the setup that precedes violent recoveries. Folding appetite into this number would erase that distinction.

**Status.** Computed and printed by `run_regime.py`; written to `output/regime_latest.json`. **No web UI displays it.**

### 3.2 Risk-on / Risk-off regime — ✅ Built (Meridian, console only)

**What it means.** A 0–100 composite mapped to five bands: Strong Risk-On, Mild Risk-On, Neutral, Mild Risk-Off, Strong Risk-Off. 100 = maximum risk-on.

**Why it is useful.** It is the conditioning variable for everything downstream — sector preferences, asset-class stance, and (when Layer 2 exists) factor weights.

**Status.** Fully computed. Console output only.

### 3.3 Systematic risk score — ✅ Built (risk-dashboard, in the web UI)

**What it means.** A separate 0–100 composite where **100 = maximum stress**, mapped to Low / Elevated / High. Built from eight components.

**Why it is useful.** This is the number the owner actually reads each morning. It is the live product.

> **⚠️ Scale conflict.** This runs in the opposite direction to §3.2. A "high" reading here means danger; a "high" reading there means safety. Reconciling or clearly labelling these is a required task before the two systems share a screen.

### 3.4 Key macro and market indicators — ✅ Built (both systems)

VIX level and term structure, high-yield credit spreads, US Treasury yields and curve, Treasury volatility, USDJPY and the carry-cross complex, WTI oil, copper/gold, dollar index, margin debt, net liquidity, money-market fund assets, reverse repo, financial conditions.

**Why useful.** These are the inputs; showing them lets the owner disagree with the model rather than obey it.

**Status.** risk-dashboard displays all its own indicators with charts and thresholds. Meridian prints its eleven indicators to console with score, raw value, source and as-of date.

### 3.5 Sector preference / rotation signals — ✅ Built (Meridian, console only)

**What it means.** All eleven SPDR sector ETFs ranked for the current regime, blending a preference matrix (60%) with live relative strength versus SPY (40%).

**Why useful.** The matrix says what *should* lead; relative strength says what *is* leading. They disagree often enough to matter — the blend leans on the model while letting the tape veto it.

**Status.** Computed and printed. **No web UI.**

### 3.6 Asset class preference — ✅ Built (Meridian, console only)

**What it means.** Ten asset classes scored −2 (Strong Underweight) to +2 (Strong Overweight) for the current regime, each with a tradeable ETF proxy.

**Status.** Computed and printed. **No web UI.**

### 3.7 Data provider status — ✅ Built (risk-dashboard sidebar)

**What it means.** Which provider is serving each data type, whether any silently fell back to a different one, and whether the data on screen is complete or was truncated by rate limiting.

**Why useful.** The single most valuable thing the panel says is *"what you are looking at is incomplete."* A quietly degraded feed is worse than an obviously broken one.

**Status.** Live in the Streamlit sidebar (`data_sources_panel.py`). Reads `daily_dashboard/output/system_status.json` **as a file**, so the dashboard works whether or not Meridian is installed or has ever run.

### 3.8 Historical regime trends — ⚠️ Data collected, nothing displayed

**What it means.** Composite score, money score, behaviour score and capital status over time.

**Why useful.** A regime score of 55 means something different climbing from 40 than falling from 70. Level without trajectory is half the information.

**Status.** The `regime_history` table stores one row per day, and `composite.history(db, days)` reads it back. **No consumer exists.** This is the highest-priority missing view.

### 3.9 Escalation / action flags — ✅ Built (risk-dashboard)

Four named pattern rules that can floor the composite: `carry_unwind`, `vol_backwardation`, `credit_crack`, `leverage_at_peak_and_vol_rising`. When one fires, the UI names it and shows what the un-floored average would have been.

### 3.10 Policy calendar — ✅ Built (risk-dashboard)

Countdown to FOMC and BOJ meetings. Dates are **hardcoded and approximate** — flagged in the UI as requiring verification against official sources.

### 3.11 Methodology / audit trail — ✅ Built (risk-dashboard)

A full write-up of every threshold, weight and rule, with current values, so the model can be argued with rather than trusted.

### 3.12 Views that are planned but not built — 📋

| View | Layer | Notes |
|---|---|---|
| Regime & Capital Flow page | 7 | Explicitly requested, high priority. Blocked on nothing but effort. |
| Historical regime trend charts | 7 | Data ready; see §3.8. |
| Stock scoring / candidate list | 2 | Requires the entire scoring engine. |
| Portfolio positions and P&L | 4 | Not started. |
| Risk exposures, factor attribution | 5 | Not started. |
| AI narrative analysis of filings | 3 | Filing sections are already extracted and stored; nothing consumes them. |
| Order blotter / execution | 6 | Not started. |

---

## 4. Project Overview

### Project names

| Name | Location | Meaning |
|---|---|---|
| **risk-dashboard** | repository root | The live Streamlit application. Also the repository name. |
| **Meridian Capital Partners** | `daily_dashboard/` | The seven-layer system. Folder named `daily_dashboard` at the owner's request. |

> **Naming hazard for a newcomer.** The repository is `risk-dashboard`; the Meridian folder inside it is `daily_dashboard`. On the owner's machine the checkout sits at `…\Investment\daily_dashboard\risk-dashboard\daily_dashboard`, which reads as circular. The innermost `daily_dashboard` is the Meridian package.

### High-level purpose

Move from *"a dashboard that tells me the macro weather"* to *"a system that conditions security selection, position sizing and risk limits on that weather."* The regime engine is the hinge: everything in Layers 2–5 is designed to be a function of Layer 0's output.

### Current status vs target

```
Layer 0  Capital & Regime Engine      ✅ BUILT, running on live data
Layer 1  Data Infrastructure          ✅ BUILT, 9 sources, verified on Windows
Layer 2  Scoring Engine               ❌ NOT STARTED  (factors/ is empty)
Layer 3  AI Analysis                  ❌ NOT STARTED  (analysis/ is empty)
Layer 4  Portfolio Construction       ❌ NOT STARTED  (portfolio/ is empty)
Layer 5  Risk Management              ❌ NOT STARTED  (risk/ is empty)
Layer 6  Execution                    ❌ NOT STARTED  (execution/ is empty)
Layer 7  Dashboard & Reporting        ⚠️ PARTIAL — risk-dashboard exists and is
                                         useful, but is not the Layer 7 described
                                         in SPEC.md and does not read Meridian's
                                         regime output
```

Six of eight Meridian package directories contain only an empty `__init__.py`. That is an honest measure of remaining work.

---

## 5. System Architecture

### 5.1 Current architecture

```
┌─────────────────────────── EXTERNAL DATA (all free) ───────────────────────────┐
│  Yahoo Finance      FRED            SEC EDGAR         FINRA                     │
│  (yfinance)         (datareader)    (HTTP + bs4)      (manual .xlsx download)   │
└────────┬────────────────┬────────────────┬────────────────┬────────────────────┘
         │                │                │                │
    ┌────▼────────────────▼────┐      ┌────▼────────────────▼────┐
    │  risk-dashboard          │      │  Meridian (daily_dashboard)│
    │  data_sources.py         │      │  data/providers.py         │
    │       ↓                  │      │       ↓                    │
    │  metrics.py   (pandas)   │      │  Layer 1 ingest (9 stages) │
    │       ↓                  │      │       ↓                    │
    │  scoring.py              │      │  SQLite  cache/meridian.db │
    │       ↓                  │      │       ↓                    │
    │  ui.py  (plotly)         │      │  Layer 0 regime engine     │
    │       ↓                  │      │       ↓                    │
    │  app.py  (Streamlit)     │      │  console + JSON output     │
    └──────────┬───────────────┘      └───────────┬────────────────┘
               │                                  │
               │   data_sources_panel.py reads    │
               └──────  system_status.json  ◄─────┘
                        (the ONLY link today)
```

**The only coupling between the two systems is one JSON file read from disk.** This was deliberate: the dashboard must work whether or not Meridian is installed, configured, or has ever run. It also means the two are, in every other respect, separate programs.

### 5.2 Target architecture (Marimo + Polars)

```
┌─────────────────────── EXTERNAL DATA (unchanged) ───────────────────────┐
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  Provider layer (unchanged   │
                    │  abstraction, Polars frames) │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  Layer 1 ingest → SQLite     │
                    │  (Polars read_database /     │
                    │   write_database)            │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  Layers 0, 2–5 pure Polars   │
                    │  DataFrame / LazyFrame       │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  Marimo notebook-app         │
                    │  reactive DAG, one app       │
                    │  serving all views           │
                    └─────────────────────────────┘
```

**Why Marimo** (the case, as understood):
- Cells form a reactive dependency graph, so a changed input updates exactly what depends on it — closer to how this model actually works than Streamlit's full-script rerun.
- Notebooks are plain `.py`, so they diff and review properly in git. Current Streamlit code is already plain Python, so this is a continuity, not a change.
- The same file serves as an interactive exploration surface and a deployed app, which suits a single-maintainer research tool.

**Why Polars**:
- Expression API is explicit about column operations, which removes a class of silent-alignment bugs pandas allows.
- Missing data is `null`, distinct from NaN — directly relevant to a system whose central rule is that *missing must never be scored as neutral*.
- Lazy evaluation and query optimisation matter once Layer 2 computes ~40 sub-factors across ~530 tickers.
- Strict schemas would have caught at least two bugs already fixed here by hand (the 13-F share/principal conflation, the market-cap ordering bug).

**Honest counter-considerations:**
- `pandas-datareader` (FRED) and `yfinance` both return pandas objects. A conversion boundary at the provider layer is unavoidable, so pandas remains a dependency.
- Time-series resampling, `asof` joins and forward-fill across mixed daily/weekly/quarterly series — used heavily in `net_liquidity` and every percentile score — are more ergonomic in pandas today. This is the highest-friction part of the migration.
- Marimo's ecosystem is younger than Streamlit's. `st.tabs`, `st.expander`, `st.sidebar` and the caching decorators all need direct equivalents identified before committing.

### 5.3 How the Meridian backend relates to the frontend

**Today: barely.** Meridian writes two files that a frontend could consume:

| File | Written by | Read by |
|---|---|---|
| `output/system_status.json` | `run_data.py`, `run_regime.py` | `data_sources_panel.py` ✅ |
| `output/regime_latest.json` | `run_regime.py` | **nothing** ❌ |
| `regime_history` table | `run_regime.py` | **nothing** ❌ |

The contract is deliberately file-based and one-directional. Meridian never imports the dashboard; the dashboard never imports Meridian. Keep this property through any migration — it is what lets either side be rewritten independently.

### 5.4 Data flow

**risk-dashboard, per page load:**

```
Streamlit cache (TTL 1800s) ─miss─► data_sources.py
                                      ├─ Yahoo batch (30s budget, 45s retry budget)
                                      └─ FRED series (60s budget)
                                           ↓
                                     metrics.py  — derive ~25 metrics
                                           ↓
                                     scoring.py  — 8 components → composite
                                           ↓                    → escalations
                                     ui.py / app.py — render 8 tabs
```

Hard time budgets exist so a hung vendor degrades the page instead of hanging it.

**Meridian, per ingest run:**

```
run_data.py
  1 universe        Wikipedia scrape → universe table  (sanity gate: ≥450 names)
  2 prices          incremental, 5-day overlap for restatements
  3 fundamentals    quarterly + annual, up to 20 quarters
  4 ratios          24 derived ratios per period
  5 short_interest  snapshot, accumulates history
  6 estimates       snapshot, accumulates history
  7 earnings        forward calendar, 30 days
  8 filings         10-K/10-Q/8-K/Form 4; risk-factor + MD&A extraction
  9 institutional   13-F for 9 tracked funds
       ↓
  SQLite (WAL mode, so the dashboard can read while an ingest writes)
       ↓
run_regime.py → 11 indicators → money/behaviour → composite → matrices
             → console report + regime_latest.json + regime_history row
```

---

## 6. Current Dashboard Features (What Actually Exists Today)

### 6.1 risk-dashboard — eight tabs, all live

| Tab | Contents |
|---|---|
| **Overview** | Regime banner (score, band, coverage %), plain-English explanation, component breakdown with per-component scores and levels, top drivers, fired escalations |
| **Carry & FX** | USDJPY with 1-week and 1-month change, four carry crosses (AUD/NZD/MXN/EUR-JPY), drawdown from 60-day highs, DXY |
| **Rates** | US 2y/10y/30y, 10y–2y curve, US–Japan 2y differential, Treasury volatility (MOVE or a realised-vol proxy), FOMC/BOJ countdowns, editable Japanese yield inputs |
| **Commodities** | WTI with 1-month absolute move and realised-vol percentile, gold, copper, copper/gold ratio |
| **Leverage** | FINRA margin debt: level, YoY change, percentile, distance from record high, historical context, CSV upload |
| **Stress** | VIX level and VIX/VIX3M term structure, HY and IG spreads, HYG/LQD, cross-asset correlation regime |
| **Watchlist** | The morning shortlist — the handful of metrics to check first |
| **Methodology** | Every threshold, weight, escalation rule and data source, with current values |

### 6.2 Key UI elements

- **Regime banner** — score, band, coverage %; colour always paired with a word so colour is never the only channel.
- **Data-sources panel** (sidebar) — per-source status, provider fallback warnings, and an explicit "data incomplete — rate limited" banner when Yahoo returns nothing.
- **Sidebar controls** — refresh (clears cache), chart window, component weight overrides, manual Japanese yield inputs seeded live from FRED with source and date shown.
- **Mode-invariant palette** — Streamlit gives Python no reliable way to know which theme the browser painted (`st.context.theme` reports the *client's* preference, which a config-pinned theme overrides). Rather than guess, surfaces are neutral greys at low alpha and text inherits colour. Correct in both themes automatically. **Preserve this constraint in any Marimo port.**
- **CSV upload** for FINRA margin data, with a `(name, size)` signature check to prevent a rerun loop.

### 6.3 Meridian — console reports

`run_regime.py` prints: indicator tables with score/value/source/as-of, money and behaviour subtotals with coverage, the composite and regime label, capital availability status, the asset-class preference table, the sector rotation ranking, Layer 2 factor multipliers, and the four-step weekly process checklist.

Flags: `--brief`, `--json`, `--no-persist`, `--complete-step STEP_ID`, `--notes`.

---

## 7. Core Model (Layer 0) — Including Formulas

> Everything in this section is **implemented and running** unless explicitly marked otherwise. All thresholds and weights below are the live values in `daily_dashboard/config.yaml`.

### 7.1 The governing model

```
Capital Availability = Money Available × Risk-on/Risk-off Behaviour
```

The claim is multiplicative, and that is the substantive content:

> **Money without appetite does not bid. Appetite without money cannot bid.**

A weighted average lets a strong reading on one side paper over a weak reading on the other — precisely the failure the model exists to prevent.

### 7.2 Scoring primitives

Every indicator is normalised to 0–100 where **100 always means "more capital available / more risk-on"**, regardless of which way the raw series moves. That normalisation is what makes the two blocks combinable at all.

#### 7.2.1 Ramp — `score_ramp(value, at_100, at_0)`

For indicators whose absolute level has meaning in itself (VIX at 30 is stress whatever the last three years looked like).

```
score = clip( (at_0 − value) / (at_0 − at_100), 0, 1 ) × 100
```

Either bound may be the larger number, which is how one function handles both "higher is better" and "lower is better" without a direction flag.

*Worked example — VIX, `risk_on_at = 13.0`, `risk_off_at = 30.0`:*
```
VIX = 13 → 100.0      VIX = 18 → 70.6      VIX = 30 → 0.0
score = clip((30 − 18) / (30 − 13), 0, 1) × 100 = 70.6
```

#### 7.2.2 Percentile — `score_percentile(series, direction, lookback_days)`

For series with no natural absolute scale, or whose scale drifts structurally (Fed balance sheet, money-fund AUM).

```
window  = series[ last_date − lookback_days : ]
score   = mean( window ≤ latest ) × 100
if direction == "down":  score = 100 − score
```

Requires ≥10 observations in the window, else falls back to the full series; below 10 observations overall, returns unavailable.

#### 7.2.3 Trend percentile — `score_trend_percentile(series, direction, trend_days, lookback_days)`

Where direction carries the signal and level does not (copper/gold, AUDJPY).

```
roc    = series.pct_change(trend_days) × 100
score  = score_percentile(roc, direction, lookback_days)
```

Requires at least `trend_days + 10` observations.

#### 7.2.4 YoY ramp — used only by margin debt

```
prior  = last observation at or before (latest_date − 12 months)
yoy    = (latest / prior − 1) × 100
score  = clip( (yoy − calm) / (stress − calm), 0, 1 ) × 100
```

With `calm = −5.0` and `stress = +35.0`: −5% YoY → 0, +15% YoY → 50, +35% YoY → 100.

> **Implementation note.** The code calls `score_ramp` and then inverts (`100 − score`), because `score_ramp` returns 100 at its first argument. The result is algebraically identical to the formula above. The inversion is intentional and commented; do not "simplify" it without re-checking the direction.

#### 7.2.5 Missing data — the rule that matters most

Nothing raises on a bad feed. A missing indicator returns `available = False` and is **dropped**, with remaining weights re-normalised. A dead series is never silently scored as neutral, because *"no data"* and *"perfectly average"* are very different statements. Coverage is reported alongside every score.

### 7.3 Money Availability score

Five indicators, `lookback_years: 5`:

| Indicator | Weight | Source | Series | Method | Direction |
|---|---:|---|---|---|---|
| `mmf_aum` | 0.25 | FRED | `MMMFFAQ027S` (fallback `RMFSL`) | percentile | up |
| `net_liquidity` | 0.25 | FRED composite | see below | trend percentile, 90d | up |
| `reverse_repo` | 0.20 | FRED | `RRPONTSYD` | percentile | **down** |
| `margin_debt` | 0.20 | FINRA CSV | `data/margin_debt.csv` | YoY ramp (−5 / +35) | up |
| `financial_conditions` | 0.10 | FRED | `NFCI` | percentile | **down** |

**Net liquidity composite:**

```
net_liquidity = WALCL − WTREGEN − (RRPONTSYD × 1000)
```

The `× 1000` is load-bearing: WALCL and WTREGEN are published in **$ millions**, RRPONTSYD in **$ billions**. Subtracting raw would understate the RRP drain by a factor of 1000 — and the resulting series would still look plausible. Weekly and daily series are forward-filled onto one index before subtraction.

**Aggregation:**

```
money_score    = Σ(scoreᵢ × weightᵢ) / Σ(weightᵢ)     over AVAILABLE indicators
money_coverage = Σ(available weights) / Σ(all weights)
```

> **A deliberate tension — do not "fix" it.** Rising margin debt *raises* the money-availability score here, while the same series *raises* fragility in the risk-dashboard's leverage component. This is correct. Leverage genuinely does add buying power on the way up and genuinely does amplify the way down. The system holds both facts at once rather than averaging them into nothing.

### 7.4 Risk-on / Risk-off Behaviour score

Six indicators, `lookback_years: 3`:

| Indicator | Weight | Source | Method | Thresholds |
|---|---:|---|---|---|
| `hy_credit_spread` | 0.25 | FRED `BAMLH0A0HYM2` | ramp, down | 3.0 → 6.5 |
| `vix_level` | 0.22 | Yahoo `^VIX` (fallback FRED `VIXCLS`) | ramp, down | 13.0 → 30.0 |
| `copper_gold_ratio` | 0.15 | Yahoo `HG=F / GC=F` | trend percentile, 60d, up | — |
| `audjpy` | 0.15 | Yahoo `AUDJPY=X` | trend percentile, 60d, up | — |
| `vix_term_structure` | 0.13 | Yahoo `^VIX / ^VIX3M` | ramp, down | 0.85 → 1.05 |
| `high_beta_vs_defensive` | 0.10 | Yahoo `SPHB / SPLV` (fallback `XLY / XLP`) | trend percentile, 60d, up | — |

Credit carries the highest weight deliberately: it reprices risk before equities do, and unlike VIX it cannot be suppressed by systematic option selling.

```
behavior_score    = Σ(scoreᵢ × weightᵢ) / Σ(weightᵢ)   over AVAILABLE indicators
behavior_coverage = Σ(available weights) / Σ(all weights)
```

### 7.5 Composite Regime Score

Three combination methods; `geometric` is the configured default.

```
geometric  (default):  composite = √(money × behaviour)
product:               composite = (money/100) × (behaviour/100) × 100
weighted:              composite = (money×w_m + behaviour×w_b) / (w_m + w_b)
```

**Why geometric.** It keeps the multiplicative behaviour — either term near zero drags the result down — while staying on a readable 0–100 scale, and it penalises imbalance:

| Money | Behaviour | Geometric | Product | Weighted |
|---:|---:|---:|---:|---:|
| 90 | 30 | **52.0** | 27.0 | 60.0 |
| 50 | 50 | **50.0** | 25.0 | 50.0 |
| 60 | 60 | **60.0** | 36.0 | 60.0 |

`product` is the purest reading of the formula but compresses everything downward — two neutral 50s produce 25, which reads as risk-off when it is not. `weighted` is an additive escape hatch and **emits a warning when selected**, because it departs from the core model.

**Degraded cases, both handled explicitly:**
- One half unavailable → the available half passes through, with a loud warning that the composite is *not* a true capital-availability reading.
- Neither available → composite defaults to 50.0 (Neutral) with a warning.
- Either half below 60% coverage → a "treat as provisional" warning is attached.

**Bands** (asymmetric on purpose — risk-off arrives faster than risk-on, so the system should change posture quickly on deterioration and slowly on improvement):

| Band | Range |
|---|---|
| Strong Risk-On | 70 – 101 |
| Mild Risk-On | 57 – 70 |
| Neutral | 43 – 57 |
| Mild Risk-Off | 30 – 43 |
| Strong Risk-Off | −1 – 30 |

### 7.6 Capital Availability status

**Driven by the money half alone, never the composite.**

```
money_score ≥ 62  →  High
money_score ≥ 38  →  Medium
money_score <  38  →  Low
money_score is None → Unknown
```

Folding behaviour in here would erase the system's ability to report *"plenty of money, but nobody wants risk"* — the classic setup for a violent rally once behaviour turns.

### 7.7 Sector preference / rotation

```
matrix_component = (matrix_score + 2) / 4 × 100          # −2..+2 → 0..100

rs_i             = return_i(60d) − return_SPY(60d)        # relative strength, %
momentum_rank_i  = (rs_i − min(rs)) / (max(rs) − min(rs)) × 100

blended_score    = matrix_component × 0.60 + momentum_rank × 0.40

favored          = matrix_score ≥ 1
```

Requires **≥3 sectors** with usable price data to rank against; below that the scan falls back to matrix-only and logs a warning, so it still produces a usable answer when Yahoo is rate-limited.

Relative rather than absolute return is the right choice here: in a rising market every sector is up, and the rotation question is which are beating the index.

**Sector matrix** (−2 to +2 per regime), abbreviated:

| ETF | Sector | Strong On | Mild On | Neutral | Mild Off | Strong Off |
|---|---|---:|---:|---:|---:|---:|
| XLK | Technology | 2 | 2 | 1 | −1 | −2 |
| XLY | Cons. Discretionary | 2 | 1 | 0 | −1 | −2 |
| XLC | Communication Svcs | 2 | 1 | 1 | −1 | −1 |
| XLF | Financials | 1 | 2 | 1 | −1 | −2 |
| XLI | Industrials | 1 | 1 | 1 | −1 | −2 |
| XLB | Materials | 1 | 1 | 0 | −1 | −2 |
| XLE | Energy | 1 | 1 | 0 | 0 | −1 |
| XLRE | Real Estate | 0 | 1 | 0 | 0 | −1 |
| XLV | Health Care | −1 | 0 | 1 | 2 | 2 |
| XLP | Consumer Staples | −2 | −1 | 0 | 2 | 2 |
| XLU | Utilities | −2 | −1 | 0 | 2 | 2 |

Energy is deliberately flat-to-positive across the middle because it trades on the commodity cycle more than the risk cycle.

> **⚠️ Documentation/code discrepancy.** The docstring of `favored_sectors()` states it requires *"BOTH a favourable matrix stance and a top-half blended rank."* The code filters on matrix stance only, then takes the top *n* of a list already sorted by blended score. The behaviour is reasonable; the docstring overstates the guarantee. Fix the docstring or add the rank check — do not leave both.

### 7.8 Asset class preference

Straight matrix lookup by regime, −2 to +2, with an ETF proxy per class:

| Class | Proxy | Strong On | Mild On | Neutral | Mild Off | Strong Off |
|---|---|---:|---:|---:|---:|---:|
| US equity | SPY | 2 | 1 | 0 | −1 | −2 |
| Intl developed equity | EFA | 2 | 1 | 0 | −1 | −2 |
| EM equity | EEM | 2 | 1 | 0 | −2 | −2 |
| HY credit | HYG | 2 | 1 | 0 | −1 | −2 |
| IG credit | LQD | 0 | 1 | 1 | 1 | 0 |
| Long Treasuries | TLT | −1 | −1 | 0 | 1 | 2 |
| Short Treasuries | SHY | −1 | 0 | 0 | 1 | 2 |
| Gold | GLD | −1 | 0 | 0 | 1 | 2 |
| Broad commodity | DBC | 1 | 1 | 0 | 0 | −1 |
| Cash | BIL | −2 | −1 | 0 | 1 | 2 |

### 7.9 Regime-conditional factor multipliers — ✅ computed, ❌ nothing consumes them

Multipliers on Layer 2's base factor weights, to be renormalised after application. Momentum works when liquidity is abundant and trends persist; quality and value work when money is scarce and balance sheets matter.

| Factor | Strong On | Mild On | Neutral | Mild Off | Strong Off |
|---|---:|---:|---:|---:|---:|
| momentum | 1.40 | 1.20 | 1.00 | 0.80 | 0.55 |
| growth | 1.30 | 1.15 | 1.00 | 0.85 | 0.70 |
| value | 0.70 | 0.85 | 1.00 | 1.15 | 1.30 |
| quality | 0.75 | 0.90 | 1.00 | 1.25 | 1.50 |
| revisions | 1.15 | 1.10 | 1.00 | 0.95 | 0.85 |
| insider | 1.00 | 1.00 | 1.00 | 1.10 | 1.20 |
| short_interest | 0.90 | 0.95 | 1.00 | 1.05 | 1.15 |
| institutional | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

**Status: computed and printed every run. Layer 2 does not exist, so nothing applies them.**

### 7.10 The risk-dashboard model (separate, and inverted)

For completeness, since it is the model actually in production:

```
1. signal_score = clip( (value − calm) / (stress − calm), 0, 1 )   # 0–1, 1 = STRESS
2. component    = Σ(signal × sub_weight) / Σ(sub_weight)           # available only
3. composite    = Σ(component × weight) / Σ(available weights) × 100
4. escalations  = max(composite, floor) for each fired rule
5. band         = High ≥ 62, Elevated ≥ 34, else Low
```

**Component weights:** carry_fx 20, equity_vol 15, credit 15, leverage 15, rate_diff 10, rate_vol 10, commodity 10, curve 5.

**Escalation rules** (floor the composite when a dangerous *combination* is present that an average would bury):

| Rule | Condition | Floor |
|---|---|---:|
| `carry_unwind` | USDJPY 1w < −2.0% **and** US–JP 2y differential > 2.0pp | 70 |
| `vol_backwardation` | VIX / VIX3M > 1.00 | 66 |
| `credit_crack` | HY OAS widened > 1.00pp in a month | 66 |
| `leverage_at_peak_and_vol_rising` | margin debt ≥ 97% of record **and** VIX > 22 | 60 |

> **⚠️ Restating the scale conflict.** `composite = 100` here means maximum stress. `composite = 100` in §7.5 means maximum risk-on. These two numbers must never appear on one screen without explicit, unmistakable labelling.

---

## 8. Data Sources & Providers

### 8.1 Active providers

| Data type | Provider | Cost | Auth | Notes |
|---|---|---|---|---|
| Market / FX / VIX / commodities | Yahoo Finance (`yfinance`) | Free | None | Rate limited; see §8.3 |
| Macro, rates, credit spreads | FRED (`pandas-datareader`) | Free | None | Reliable; ~1 business day lag |
| SEC filings, Form 4, 13-F | SEC EDGAR | Free | `SEC_USER_AGENT` required | Capped at 8 req/s (SEC's limit is 10) |
| Margin debt | FINRA | Free | None | **Manual monthly `.xlsx` download**, converted by `import_finra.py` |
| Fundamentals | Yahoo Finance | Free | None | Quality varies by ticker |
| Transcripts | FMP | Paid | `FMP_API_KEY` | Configured; not exercised |

### 8.2 Provider abstraction — ✅ Built and hardened

`data/providers.py` defines a `Provider` ABC with:

- `preflight()` — can this provider actually run here?
- `implemented` — `False` marks a documented stub; selecting it in config triggers a visible fallback rather than a crash
- `requires_secret` — the `.env` key without which it cannot work
- `requires_local_gateway` — a local process that must be running

Only `market_data`, `fundamentals` and `transcripts` are provider-backed (`PROVIDER_BACKED_ROLES`). `macro`, `filings` and `margin_debt` are `FIXED_SOURCES` — they have exactly one implementation and are not swappable. Distinguishing these fixed a false alarm where the report claimed FRED and SEC had "fallen back to yfinance."

| Provider | Status |
|---|---|
| `YFinanceProvider` | ✅ Implemented, default for market data and fundamentals |
| `FMPProvider` | ✅ Implemented, requires `FMP_API_KEY` |
| `PolygonProvider` | ✅ Implemented, requires `POLYGON_API_KEY` |
| `TradingViewProvider` | ⚠️ **Documented stub.** `implemented = False`. Requires a CDP browser-automation surface. |
| `FutuProvider` | ⚠️ **Documented stub.** `implemented = False`. Requires FutuOpenD running and logged in on `127.0.0.1:11111`. |

The stubs carry the owner's real integration constraints in their docstrings so a future implementer starts from the actual requirements rather than guesses. Every fallback is reported in the console, in the log, and in the dashboard's data-sources panel.

**This abstraction is the main asset to preserve in a Polars migration.** Keep it as the pandas↔Polars conversion boundary.

### 8.3 Known limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| **Yahoo HTTP 429** | Persistent from shared/cloud IPs. Full-universe refresh fails. | Batch size 25, 3s baseline pause, ≤4 threads, 90s cooldown, 1.6× backoff growth, abort after 6 hits, full-jitter retries. **Full runs must be local.** |
| **FINRA is manual** | Margin debt is monthly and requires a human to download a spreadsheet. | `import_finra.py` converts it. Placeholder rows are detected and **excluded from scoring**, never scored as calm. |
| **No JGB daily feed** | The US–Japan 2y differential depends on a manual input. | Seeded from FRED's monthly Japanese series with source and date shown; overridable in the sidebar. |
| **FRED release lag** | ~1 business day on daily series; quarterly series lag far more. | Every indicator carries an as-of date. |
| **Yahoo fundamentals quality** | Varies by ticker; occasional wrong values. | Not yet cross-validated. Open item. |
| **Central bank calendar hardcoded** | Dates will drift. | Flagged in the UI as approximate. |

---

## 9. Current Tech Stack vs Target Tech Stack

| Area | Current | Target (Preferred) | Migration difficulty |
|---|---|---|---|
| Dashboard framework | Streamlit ≥ 1.50 | **Marimo** | **High** — 234 call sites, 8 tabs, custom theme handling |
| Data library | pandas ≥ 2.0 | **Polars** | **High** — 216 call sites across 17 files |
| Charting | Plotly ≥ 5.20 | Plotly (unchanged) | Low — Plotly is framework-agnostic |
| Backend language | Python 3.11+ | Python 3.11+ | None |
| Database | SQLite (WAL) | SQLite (WAL) | None — Polars reads/writes it natively |
| Config | `config.py` (dashboard) + `config.yaml` (Meridian) | Consolidate on YAML | Medium |
| Market data | yfinance | yfinance, provider swap kept open | None |
| Macro data | pandas-datareader (FRED) | Unchanged — **returns pandas** | Conversion boundary needed |
| Filing parsing | BeautifulSoup + lxml | Unchanged | None |
| Spreadsheets | openpyxl | Unchanged | None |
| Testing | **None** | pytest | **New work** |
| Deployment | Local + Streamlit Cloud (partial) | Local-first | — |

### Migration surface, measured

| Metric | Count |
|---|---:|
| Files importing pandas | 17 |
| `pd.*` call sites | 216 |
| `st.*` call sites | 234 |
| Files importing Plotly | 1 (`ui.py`) |
| Total Python lines | ~9,950 |

### Recommended sequencing

**Do not migrate both at once.** They are independent and failing at both simultaneously is the likely outcome.

1. **Polars first, bottom-up.** Start at `daily_dashboard/data/` where frames are simple and tabular and schemas are explicit. Convert pandas→Polars at the provider boundary. Layer 1 has no UI, so a break is loud and local.
2. **Layer 0 second.** `regime/indicators.py` is the hardest part — percentile windows, `pct_change` over irregular indices, and mixed-frequency forward-fill in `net_liquidity`. Budget disproportionate time here, and verify each converted indicator against the pandas output on the same data before deleting anything.
3. **Marimo third, on a new page.** Build the *Regime & Capital Flow* page — which does not exist yet — as a Marimo app first. That gives a real evaluation with zero regression risk to the working dashboard.
4. **Port the eight existing tabs last,** only if step 3 proves the framework out.

**Keep Streamlit running throughout.** There is no point at which the owner should be without a working morning dashboard.

---

## 10. Known Gaps & Incomplete Areas

### 10.1 Missing layers

| Layer | Directory | State |
|---|---|---|
| 2 — Scoring Engine | `factors/` | Empty `__init__.py`. Spec'd in detail: 8 factors, ~40 sub-factors, regime-conditional weights, crowding detection. **Nothing built.** |
| 3 — AI Analysis | `analysis/` | Empty. Filing sections *are* extracted and stored; no consumer. |
| 4 — Portfolio Construction | `portfolio/` | Empty. MVO optimiser, conviction tilt, transaction costs, rebalance schedule all spec'd only. |
| 5 — Risk Management | `risk/` | Empty. Factor risk model, 8-check pre-trade veto, circuit breakers spec'd only. |
| 6 — Execution | `execution/` | Empty. |
| 7 — Dashboard | `reporting/` | Empty. risk-dashboard exists but is a different application. |

### 10.2 Untested / unverified

| Item | Why it matters |
|---|---|
| **No automated test suite** | Correctness rests on targeted manual verification. Every fix so far has been verified by hand and documented in its commit message, but nothing prevents regression. |
| **Layer 1 stages 2–7 never run in the dev sandbox** | Yahoo 429 blocks them. Verified only on the owner's Windows machine. |
| **Full 503-ticker run not yet completed** on the current code | Pending. This is the immediate next action. |
| **`fcf_yield` fix verified by code path, not live run** | The ordering bug is fixed and unit-verified; a live run must confirm the column populates. |
| **Yahoo fundamentals never cross-validated** | No second source has been checked against. |
| **Marimo and Polars: zero code** | The direction is documented; nothing has been attempted. Estimates in §9 are informed but unproven. |

### 10.3 Known bugs and open issues

| # | Issue | Severity | State |
|---|---|---|---|
| 1 | Inverted composite scales between the two systems | **High** | Open. Not a code bug — a design collision that will become one when they share a screen. |
| 2 | `favored_sectors()` docstring overstates the code | Low | Open. See §7.7. |
| 3 | Pre-migration insider rows remain under-counted | Low | Structural. The PK fix stops *future* loss; rows already collapsed are only restored by re-fetching those Form 4s. |
| 4 | Central bank calendar hardcoded | Low | Open; flagged in UI. |
| 5 | Nested `daily_dashboard/risk-dashboard/daily_dashboard` path on the owner's machine | Low | Environmental, confusing for a newcomer. |

### 10.4 Recently fixed (for context on stability)

Six data-corruption bugs have been found and fixed, all with explicit verification. Listed because they indicate where the fragile areas are:

| Bug | Impact when live |
|---|---|
| 13-F primary key collision | Silently lost 62% of rows (4,766 → 1,799) |
| 13-F option positions merged into common stock | Read Citadel's NVDA conviction as $23.7bn; actual common was $2.4bn |
| 13-F convertible debt counted as shares | Implied a $922 share price for DXCM |
| Form 4 fetched the XSL rendering, not the raw XML | Zero insider transactions parsed |
| `fcf_yield` computed before its input existed | NULL across the entire universe, while the run reported success |
| Insider transaction PK collision | 153 parsed, 152 stored |

**Pattern worth noting:** every one of these failed *silently* and reported success. That is the strongest argument in this document for Polars' strict schemas and for a test suite.

---

## 11. Technical Decisions Already Made

### 11.1 Keep Streamlit for now — and explicitly do not start a Next.js frontend

**Decision (owner, explicit): no new Next.js frontend at this stage.**

Reasoning:
- The Streamlit dashboard works, is used daily, and has had substantial design investment — mode-invariant theming, mobile layout, chart-title handling, accessibility (colour never load-bearing).
- The bottleneck is **backend completeness** (Layers 2–5), not presentation.
- A JavaScript frontend adds a second language, a build pipeline and an API contract, for a single-user tool.
- Marimo, unlike Next.js, keeps everything in Python — so the migration path stays open without paying for a second stack.

### 11.2 Document Marimo + Polars before migrating

Writing this specification first is deliberate:
- The formulas in §7 are currently expressed *only* as pandas code. Extracting them into notation makes them portable and re-implementable — and is the artefact a second developer actually needs.
- The measured migration surface (§9) turns a preference into a costed decision.
- Migrating without a specification means re-deriving intent from code under time pressure, which is how the semantics of "missing data is dropped, not neutral" gets quietly lost.

### 11.3 Other decisions already settled

| Decision | Rationale |
|---|---|
| **Geometric mean** for the composite | Preserves multiplicative behaviour on a readable scale; penalises imbalance. `product` compresses too hard; `weighted` breaks the model and warns when used. |
| **Missing data drops, never scores neutral** | "No data" ≠ "average". Non-negotiable; carry into every rewrite. |
| **Capital status from the money half only** | Preserves the ability to say "money is abundant, appetite is absent". |
| **File-based coupling** between the systems | The dashboard works whether or not Meridian is installed. Keep this. |
| **Provider abstraction with documented stubs** | TradingView and Futu can be added without touching other layers; the stubs carry the real constraints. |
| **Full-universe runs are local-only** | Yahoo 429 from shared IPs. Not solvable by better code. |
| **Only Form 4 codes P and S are signal** | Grants (A), option exercises (M) and tax withholding (F) are compensation mechanics. Counting them as "insider buying" is the most common way this data gets misread. |
| **Mode-invariant palette** | Streamlit cannot reliably tell Python which theme was painted. Avoid needing to know. |
| **60/40 matrix/momentum blend** | Leans on the model while letting the tape veto it. |
| **Step 4 of the weekly process stays manual** | Confirming a stated edge is the one step that cannot be automated. |
| **SQLite in WAL mode** | Lets the dashboard read while an ingest writes. |

---

## 12. Open Questions & Assumptions

### 12.1 Open questions — for the owner

| # | Question | Why it blocks work |
|---|---|---|
| 1 | **How should the two inverted composite scales be reconciled?** Invert one? Rename both? Show them side by side with explicit labels? | Blocks the Regime page design. Highest-priority decision in this document. |
| 2 | Is Marimo + Polars a firm commitment or a direction under evaluation? | Determines whether §9 step 3 is a spike or a project. |
| 3 | Should Layer 2 be built before or after the Marimo/Polars migration? | Building Layer 2 in pandas adds to the migration surface; migrating first delays the feature the system exists for. |
| 4 | Is a paid data provider acceptable for fundamentals? | Yahoo fundamentals quality is the main input risk to Layer 2. |
| 5 | Should Meridian and risk-dashboard eventually merge into one application, or stay separate? | Determines whether the file-based coupling is permanent architecture or a temporary bridge. |
| 6 | What is the intended deployment target? | Yahoo 429 rules out cloud for full runs, but the regime engine alone might be cloud-viable. |

### 12.2 Assumptions made in this document

| # | Assumption | If wrong |
|---|---|---|
| 1 | Single user, single machine; no multi-tenancy, auth or concurrency requirements | Architecture changes materially |
| 2 | Free data sources remain the constraint | A paid feed removes the 429 problem and most of §8.3 |
| 3 | `daily_dashboard/SPEC.md` remains the authority on Layers 2–7 | Layer sequencing would need revisiting |
| 4 | The Marimo migration targets the *existing* dashboard, not a new product | Scope changes |
| 5 | Windows is the primary run environment | Affects setup instructions and path handling |
| 6 | Thresholds stay judgement calls, not fitted parameters | Introducing backtesting is a significant new workstream with its own methodology risks |
| 7 | Layer 0's output is the intended conditioning variable for Layers 2–5 | The factor-multiplier design would need rework |

---

## 13. Recommended Next Steps

### Priority 1 — Immediate (this week)

1. **Complete the full 503-ticker Layer 1 run on the local machine.** Everything downstream depends on a complete dataset. Verify specifically that `fcf_yield` populates and that insider rows parsed equals insider rows stored.
2. **Decide the scale-reconciliation question (§12.1 #1).** One decision; blocks the next item.
3. **Build the Regime & Capital Flow page with historical trend charts.** Explicitly high-priority. All the data exists; nothing displays it. *Recommend building this in Marimo* (see §9 step 3) — it is the natural, zero-risk evaluation.

### Priority 2 — Near term (2–4 weeks)

4. **Add a test suite.** Start with the scoring primitives (`score_ramp`, `score_percentile`, `weighted_score`, `combine`) — pure functions, high value, no I/O. Then the database migration path. Six silent-corruption bugs is the argument.
5. **Polars spike on `daily_dashboard/data/`.** Timeboxed. Convert one ingest module, measure the real friction, then decide.
6. **Fix the low-severity items** in §10.3 — the `favored_sectors` docstring, the calendar note.

### Priority 3 — Medium term (1–3 months)

7. **Layer 2 scoring engine.** The largest single piece of remaining value: it is what turns a macro read into a candidate list. Note that the regime-conditional multipliers it needs already exist and are computed daily.
8. **Complete the Polars migration** through Layer 0, if the spike succeeds.
9. **Cross-validate Yahoo fundamentals** against a second source before Layer 2 depends on them.

### Priority 4 — Longer term

10. Marimo migration of the remaining eight tabs.
11. Layers 3–6, in spec order.
12. Revisit TradingView / Futu providers if Yahoo's data quality or rate limiting becomes binding.

---

## 14. How to Run the Current System

### 14.1 Prerequisites

- Python 3.11 or later
- Git
- ~500 MB free disk (SQLite database plus caches)

### 14.2 Setup — Windows / PowerShell

```powershell
git clone https://github.com/playandlearnhkg/risk-dashboard.git
cd risk-dashboard
git checkout claude/meridian-layer0-layer1

python -m venv .venv
.\.venv\Scripts\Activate.ps1
# If blocked by execution policy:
#   Set-ExecutionPolicy -Scope Process RemoteSigned

pip install -r requirements.txt
pip install -r daily_dashboard\requirements.txt
```

> **Note.** `source .venv/bin/activate` is bash syntax and will fail in PowerShell. Use `.\.venv\Scripts\Activate.ps1`.

### 14.3 Setup — macOS / Linux

```bash
git clone https://github.com/playandlearnhkg/risk-dashboard.git
cd risk-dashboard
git checkout claude/meridian-layer0-layer1

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
pip install -r daily_dashboard/requirements.txt
```

### 14.4 Run the Streamlit dashboard

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`. **No configuration, database or prior ingest is required** — it fetches everything live and caches for 30 minutes.

### 14.5 Run the Meridian regime engine (Layer 0)

```bash
cd daily_dashboard
python run_regime.py
```

Takes 1–3 minutes (FRED and Yahoo fetches). No database needed — Layer 0 runs standalone by design, because the regime read is what you want working first thing in the morning.

Useful flags:

```bash
python run_regime.py --brief                        # headline only
python run_regime.py --json                         # JSON to stdout
python run_regime.py --no-persist                   # do not write to the database
python run_regime.py --complete-step opportunity_filter --notes "reviewed 6 names"
```

### 14.6 Run the Meridian data ingest (Layer 1)

**Run this on a local machine, not a cloud host or shared IP** — Yahoo will return 429 otherwise.

```powershell
cd daily_dashboard
$env:SEC_USER_AGENT = "Your Name your.email@example.com"   # SEC requires this
python run_data.py
```

Bash equivalent: `export SEC_USER_AGENT="Your Name your.email@example.com"`

> **Correction to earlier instructions.** There is **no `--full` flag**. Running `run_data.py` with no arguments performs the complete run over the full universe. Passing `--full` will fail with "unrecognized arguments".

Actual flags:

| Flag | Effect |
|---|---|
| *(none)* | Full run: all 9 stages, full universe |
| `--quick` | Universe and prices only |
| `--stage NAME` | One stage. Valid: `universe`, `prices`, `fundamentals`, `ratios`, `short_interest`, `estimates`, `earnings`, `filings`, `institutional` |
| `--limit N` | Cap ticker count (testing) |
| `--tickers AAPL,MSFT` | Explicit subset (testing) |
| `--no-filings` | Skip SEC EDGAR |
| `--no-13f` | Skip institutional holdings |
| `--full-refresh` | Refetch all price history, ignoring what is stored |
| `--force-universe` | Re-scrape the universe even if cached |

**Recommended first run** (proves the pipeline in ~2 minutes before committing to the full one):

```powershell
python run_data.py --limit 20 --no-13f
```

**Then the full run,** capturing output:

```powershell
python run_data.py 2>&1 | Tee-Object -FilePath ..\layer1_full.log
```

Expect it to take a while — the 429 hardening deliberately paces batches.

### 14.7 Updating margin debt (monthly)

1. Download the margin statistics `.xlsx` from FINRA.
2. `python import_finra.py --xlsx path\to\downloaded.xlsx`
   (`--xlsx` and `--csv` both have defaults, so a bare `python import_finra.py` works if the file is in the expected place. `--months N` limits how many months are imported.)
3. It writes `data/margin_debt.csv` and prints the derived figures for sanity-checking.

Both applications read this same CSV — one copy in the repository, not two that drift.

### 14.8 Output locations

| Path | Contents |
|---|---|
| `daily_dashboard/cache/meridian.db` | SQLite database, all Layer 1 data |
| `daily_dashboard/output/regime_latest.json` | Most recent Layer 0 result |
| `daily_dashboard/output/system_status.json` | Provider status, rate-limit state, coverage |
| `daily_dashboard/output/meridian.log` | Full run log (UTF-8) |
| `data/margin_debt.csv` | FINRA margin debt, shared by both apps |

---

## 15. Handover Notes

### The five-minute version

- **Two applications, one repository.** `app.py` at the root is a working Streamlit risk dashboard. `daily_dashboard/` is Meridian, of which 2 of 7 layers exist.
- **Meridian's Layers 0 and 1 work and produce good output — into a terminal.** The main gap is not computation; it is that almost none of it reaches a screen.
- **The two systems' composite scores run in opposite directions.** Resolve this before they share a page. It is the first thing that will bite you.
- **Marimo and Polars are a documented direction with zero code.** This document is the plan, not a report on progress.

### Where to start reading

| Order | File | Why |
|---:|---|---|
| 1 | `daily_dashboard/config.yaml` | Every tunable, heavily commented. The system's intent is here. |
| 2 | `daily_dashboard/regime/composite.py` | The core model in ~300 lines. |
| 3 | `daily_dashboard/regime/indicators.py` | The three scoring methods and all data access. |
| 4 | `scoring.py` (root) | The live dashboard's model — simpler, and separate. |
| 5 | `config.py` (root) | The dashboard's thresholds and weights. |
| 6 | `daily_dashboard/SPEC.md` | The full 7-layer build specification. |
| 7 | `daily_dashboard/data/providers.py` | The provider abstraction; the asset to preserve. |

### Conventions to preserve

1. **Missing data is dropped and weights re-normalised — never scored as neutral.** The single most important invariant. Coverage is reported everywhere.
2. **Colour is never the only channel.** Every status has a word beside it.
3. **Config, not code.** Thresholds and weights live in `config.yaml` / `config.py`. If you find yourself hardcoding a number, it belongs in config.
4. **Comments explain *why*, not *what*.** The codebase is dense with reasoning about why a formula is shaped the way it is — the unit rescale in `net_liquidity`, the inverted ramp in `yoy_ramp`, the mode-invariant palette. **Read those before changing anything nearby.** Several encode bugs that were expensive to find.
5. **Verify data fixes with real data.** Every corruption bug in §10.4 failed silently and reported success. A green run proves nothing on its own.

### Things that will surprise you

| Surprise | Explanation |
|---|---|
| Rising margin debt *helps* Meridian's score and *hurts* the dashboard's | Intentional. Leverage adds buying power on the way up and amplifies the way down. §7.3. |
| `yoy_ramp` computes a ramp then inverts it | `score_ramp` returns 100 at its first argument. Algebraically correct; commented in place. §7.2.4. |
| The palette looks washed out in code | Deliberate. Streamlit cannot tell Python which theme was painted, so surfaces are translucent greys that read correctly on both. §6.2. |
| Chart titles are rendered as HTML above the figure, not inside Plotly | Plotly titles collide with legends and render "undefined" when `None`. |
| Six of eight Meridian package directories are empty | Accurate. Layers 2–7 are not started. |
| SEC Form 4 fetching strips an `xsl*/` path prefix | EDGAR's "primary document" is the human-readable HTML rendering; the machine-readable XML is at the same path with that directory removed. |
| `run_data.py` has no `--full` flag | Bare invocation *is* the full run. §14.6. |

### Contact and provenance

Sole maintainer to date: the repository owner (`playandlearn.hkg@gmail.com`). All design decisions in §11 are theirs and are recorded with rationale in code comments and commit messages. Where this document and the code disagree, **the code is correct and this document is stale** — please fix it.

---

*End of specification.*
