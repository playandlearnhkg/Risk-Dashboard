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

### Document map

| § | Section | Read it for |
|---:|---|---|
| 1–4 | Summary, Purpose, Information, Overview | What the system is and why |
| 5–6 | Architecture, Current Features | How it is put together, what exists today |
| **7** | **Core Model (Layer 0) with formulas** | The Meridian regime engine, exactly |
| 8–9 | Data Sources, Tech Stack | Providers; Streamlit→Marimo, pandas→Polars |
| 10–13 | Gaps, Decisions, Open Questions, Next Steps | Planning and hand-over judgement |
| 14–15 | How to Run, Handover Notes | Getting it working on a new machine |
| **16** | **Glossary** | **Start here if the two 0–100 scores confuse you** |
| **17** | **Output contracts** | JSON field lists, DB schemas, real examples |
| **18** | **Target UI spec — Regime & Capital Flow** | What to build next, in detail |
| **19** | **risk-dashboard model reference** | All 8 components: sub-metrics and thresholds |
| **20** | **Daily operating workflow** | Morning checklist; local vs view-only |
| **21** | **Acceptance criteria** | Testable Definition of Done |
| **22** | **Known environment issues** | Windows, paths, first-run |
| **23** | **Data freshness** | Per-indicator lag and update frequency |
| **24** | **What could not be confirmed from code** | Honest limits of this document |

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

## 16. Glossary

### 16.1 The two 0–100 scores — read this first

The system contains **two different composite scores, both on a 0–100 scale, running in opposite directions.** This is the single most likely source of a serious misreading.

| | **Stress Score** | **Regime Score** |
|---|---|---|
| **Produced by** | risk-dashboard (`scoring.py`) | Meridian Layer 0 (`regime/composite.py`) |
| **Field name** | `RiskAssessment.composite` | `composite_score` |
| **0 means** | Total calm | Maximum risk-**off** |
| **100 means** | Maximum **danger** | Maximum risk-**on** |
| **Direction** | **Higher is worse** | **Higher is better** |
| **Bands** | Low < 34 ≤ Elevated < 62 ≤ High | Strong Risk-Off < 30 ≤ Mild Risk-Off < 43 ≤ Neutral < 57 ≤ Mild Risk-On < 70 ≤ Strong Risk-On |
| **Answers** | "How stressed is the system right now?" | "Is capital available and willing?" |
| **Where seen** | Streamlit UI, every tab | Console, `regime_latest.json` |
| **Status** | ✅ In production | ✅ Computed; no UI |

> **A worked confusion.** A Stress Score of 85 means *get out of the way*. A Regime Score of 85 means *conditions are supportive*. Identical numbers, opposite instructions. Neither is wrong; they measure different things in different directions.

**Naming convention adopted by this document, and recommended for the code and UI:** never write "the score" unqualified. Write **Stress Score** or **Regime Score**, always. §18.7 specifies how they must be labelled if displayed together.

### 16.2 Capital Availability vs Regime vs Coverage

These three are routinely confused because all three are outputs of the same Layer 0 run.

| Term | What it is | Range / values | Derived from | Answers |
|---|---|---|---|---|
| **Capital Availability** | A three-state label | High / Medium / Low / Unknown | The **Money Score alone** (≥62 High, ≥38 Medium) | *Does money exist to be deployed?* |
| **Regime** | A five-state label plus its score | Strong Risk-Off … Strong Risk-On, 0–100 | Money **×** Behaviour, geometric | *Is capital available **and** willing?* |
| **Coverage** | A data-quality percentage | 0–100% | Share of indicator **weight** that returned data | *How much of the model actually ran?* |

**Why Capital Availability excludes behaviour.** So the system can report *"money is abundant but nobody wants risk"* — Capital High with Regime Strong Risk-Off. Historically the setup preceding violent recoveries. Folding behaviour in would collapse that into a single mid reading and destroy the information.

**Why Coverage is not a confidence score.** It measures *how much of the model ran*, not *how right it is*. 100% coverage on a badly specified model is still a bad answer. But **below ~60% coverage the composite should not be treated as a regime call at all** — see the live example in §23.3, where a Regime Score of 90.2 "Strong Risk-On" was produced from 47% behaviour coverage.

### 16.3 Other terms

| Term | Meaning |
|---|---|
| **Ramp** | Linear map from a raw value to a score between two named thresholds. Handles both directions without a flag. §7.2.1 |
| **Percentile score** | Rank of the latest observation in its own trailing window. For series with no natural absolute scale. §7.2.2 |
| **Trend percentile** | Percentile of the *rate of change* rather than the level. Where direction carries the signal. §7.2.3 |
| **Escalation** | A named rule that *floors* the Stress Score when a dangerous combination is present that a weighted average would bury. §7.10 |
| **Money Score** | 0–100, the money-availability half of the core model. 100 = most money available. |
| **Behaviour Score** | 0–100, the risk-appetite half. 100 = most risk-on. |
| **Matrix score** | An integer −2…+2 preference for a sector or asset class in the current regime. Pure theory, from config. |
| **Momentum rank** | 0–100 rank of a sector's 60-day return *relative to SPY* within the peer set. Pure observation. |
| **Blended score** | 0.60 × matrix + 0.40 × momentum rank, both on 0–100. The ranking key for the rotation scan. |
| **Favored** | A sector with `matrix_score ≥ 1`. Note: matrix stance only — momentum does not make a sector favored, only ranks it. |
| **Signal (Form 4)** | An insider transaction with code **P** (open-market purchase) or **S** (open-market sale). Codes A/M/F/G/C/D are compensation mechanics and are stored but excluded. |
| **Cluster buy** | 3+ distinct insiders buying the same name within 30 days. |
| **Provider fallback** | The configured provider could not run (missing key, unimplemented stub), so a working one was substituted. Always reported, never silent. |
| **Fixed source** | A data role with exactly one implementation and no provider abstraction: `macro` (FRED), `filings` (SEC EDGAR), `margin_debt` (FINRA). |
| **Placeholder (margin data)** | A row flagged `is_placeholder`. **Excluded from scoring entirely** — never scored as calm. |
| **Layer** | One of Meridian's seven tiers. Layers 0–1 built; 2–7 not started. |
| **Stale ticker** | A ticker whose newest stored price is older than the universe's newest stored price. |

---

## 17. Output Contracts

> Every example below is **real output** from the run of 2026-08-21, not illustrative. Values are abridged where marked `…`.

### 17.1 `daily_dashboard/output/regime_latest.json` — ✅ Written

**Producer:** `run_regime.py`, unless `--no-persist`. **Consumers today: none.** This is the file the Regime & Capital Flow page (§18) must read.

#### Top-level fields

| Field | Type | Notes |
|---|---|---|
| `run_date` | string, ISO date | The engine's run date, not the data's as-of date |
| `composite_score` | float 0–100 | **Regime Score.** 100 = risk-on. Never null — defaults to 50.0 with a warning |
| `regime_key` | string | One of `strong_risk_on`, `mild_risk_on`, `neutral`, `mild_risk_off`, `strong_risk_off` |
| `regime_label` | string | Human label, e.g. `"Strong Risk-On"` |
| `money_score` | float 0–100 \| **null** | Null if no money indicator scored |
| `behavior_score` | float 0–100 \| **null** | Null if no behaviour indicator scored |
| `capital_status` | string | `High` \| `Medium` \| `Low` \| `Unknown` |
| `combination_method` | string | `geometric` \| `product` \| `weighted` |
| `coverage` | float 0–1 | Mean of the two coverages. **Note: 0–1, not 0–100** |
| `money_coverage` | float 0–1 | |
| `behavior_coverage` | float 0–1 | |
| `factor_multipliers` | object | 8 float values, keyed by factor name |
| `warnings` | array of string | **Must be surfaced in any UI.** Empty array when clean |
| `money_indicators` | array[5] of Indicator | See below |
| `behavior_indicators` | array[6] of Indicator | See below |
| `sectors` | array[11] of Sector | |
| `asset_classes` | array[10] of AssetClass | |
| `weekly_process` | object | |

#### Indicator object (13 fields, identical in both blocks)

| Field | Type | Notes |
|---|---|---|
| `key` | string | e.g. `vix_level` |
| `label` | string | Title-cased from `key`. **Cosmetically poor** — `mmf_aum` → `"Mmf Aum"`. A UI should map its own labels |
| `score` | float 0–100 \| **null** | **Null means unavailable.** Never treat as 0 |
| `raw_value` | float \| null | The underlying number |
| `display` | string | Pre-formatted with units, or `"n/a"` |
| `weight` | float | As configured, before renormalisation |
| `method` | string | `ramp` \| `percentile` \| `trend_percentile` \| `yoy_ramp` |
| `direction` | string | `up` \| `down` |
| `source` | string | **Reports the effective source**, e.g. `"fred:VIXCLS"` after a fallback |
| `as_of` | string ISO date \| null | **The data's date, not the run's.** See §23 |
| `note` | string | Explanatory text from config |
| `error` | string | Populated only when `score` is null, e.g. `"no data returned"` |
| `detail` | object | Method-dependent: `{risk_on_at, risk_off_at}` for ramp, `{lookback_days}` for percentile, `{trend_days, trend_pct}` for trend, `{calm, stress, level_musd}` for yoy_ramp |

#### Sector, AssetClass, weekly_process objects

```
Sector      { ticker, name, matrix_score, momentum_pct, blended_score, favored }
AssetClass  { key, matrix_score, proxy }
weekly_process {
  summary: "3/4 steps current", all_current: bool,
  steps: [ { id, order, name, description, auto, status, last_completed,
             days_since, display_age, notes } ]
}
```

> **⚠️ Contract inconsistency — two payload shapes.** `run_regime.py --json` (stdout) and `regime_latest.json` (file) are **not identical**, despite both being "the Layer 0 payload":
>
> | | stdout (`--json`) | file |
> |---|---|---|
> | Sector `stance` | ✅ present | ❌ absent |
> | AssetClass `name` | ✅ present | ❌ absent |
> | AssetClass `stance` | ✅ present | ❌ absent |
>
> A consumer written against one breaks on the other. **Recommend unifying on the richer stdout shape** before anything depends on the file. Until then, a UI must derive `stance` from `matrix_score` via the −2…+2 → label map itself.

#### Real example (abridged)

```json
{
  "run_date": "2026-08-21",
  "composite_score": 90.2,
  "regime_key": "strong_risk_on",
  "regime_label": "Strong Risk-On",
  "money_score": 85.9,
  "behavior_score": 94.8,
  "capital_status": "High",
  "combination_method": "geometric",
  "coverage": 0.735,
  "money_coverage": 1.0,
  "behavior_coverage": 0.47,
  "factor_multipliers": {
    "momentum": 1.4, "growth": 1.3, "value": 0.7, "quality": 0.75,
    "revisions": 1.15, "insider": 1.0, "short_interest": 0.9,
    "institutional": 1.0
  },
  "warnings": [
    "Only 47% of behaviour indicator weight had data — treat this score as provisional."
  ],
  "money_indicators": [
    {
      "key": "mmf_aum", "label": "Mmf Aum", "score": 100.0,
      "raw_value": 8289569.0, "display": "8289569.00", "weight": 0.25,
      "method": "percentile", "direction": "up", "source": "fred",
      "as_of": "2026-01-01", "note": "Dry powder parked in money funds",
      "error": "", "detail": { "lookback_days": 1825 }
    }
  ],
  "behavior_indicators": [
    {
      "key": "vix_level", "label": "Vix Level", "score": 88.9,
      "raw_value": 14.89, "display": "14.89", "weight": 0.22,
      "method": "ramp", "direction": "down", "source": "fred:VIXCLS",
      "as_of": "2026-08-19", "note": "Implied equity volatility",
      "error": "", "detail": { "risk_on_at": 13.0, "risk_off_at": 30.0 }
    },
    {
      "key": "vix_term_structure", "label": "Vix Term Structure",
      "score": null, "raw_value": null, "display": "n/a", "weight": 0.13,
      "method": "ramp", "direction": "down", "source": "yahoo_ratio",
      "as_of": null, "note": "VIX / VIX3M -- above 1.0 is backwardation",
      "error": "no data returned", "detail": {}
    }
  ],
  "sectors": [
    { "ticker": "XLK", "name": "Technology", "matrix_score": 2,
      "momentum_pct": null, "blended_score": 100.0, "favored": true }
  ],
  "asset_classes": [
    { "key": "em_equity", "matrix_score": 2, "proxy": "EEM" }
  ],
  "weekly_process": {
    "summary": "3/4 steps current",
    "all_current": false,
    "steps": [
      { "id": "macro_vol_check", "order": 1,
        "name": "Macro & Volatility / Regime Check",
        "description": "Read VIX level and term structure, HY spreads...",
        "auto": true, "status": "current", "last_completed": "2026-08-21",
        "days_since": 0, "display_age": "today",
        "notes": "Strong Risk-On · composite 90/100 · behaviour 94.8" }
    ]
  }
}
```

### 17.2 `daily_dashboard/output/system_status.json` — ✅ Written and consumed

**Producer:** `run_data.py` only. **Consumer:** `data_sources_panel.py` (Streamlit sidebar) ✅.

Written by **merge**, not overwrite, so the two entry points cannot erase each other's blocks. Any consumer must therefore treat **every top-level block as optional.**

| Field | Type | Notes |
|---|---|---|
| `providers` | array | One per provider-backed role: `market_data`, `fundamentals`, `transcripts` |
| `providers[].role` | string | |
| `providers[].requested` | string | What `config.yaml` asked for |
| `providers[].effective` | string | What actually ran |
| `providers[].fell_back` | bool | `requested != effective` |
| `providers[].note` | string | Reason for the fallback; empty when none |
| `fixed_sources` | array | Constant, 3 entries: FRED, SEC EDGAR, FINRA |
| `rate_limit.rate_limited` | bool | |
| `rate_limit.hits` | int | Count of HTTP 429s |
| `rate_limit.cooldowns` | int | Count of cooldown pauses taken |
| `rate_limit.aborted` | bool | **True = the fetch stopped early; prices are partial** |
| `rate_limit.first_hit_at` | string \| null | |
| `rate_limit.checked_at` | string ISO datetime | |
| `price_coverage.latest_date` | string \| null | Newest stored price date |
| `price_coverage.tickers` | int | |
| `price_coverage.stale_tickers` | int | |
| `last_ingest.run_id` | string | 12 hex chars |
| `last_ingest.finished_at` | string ISO datetime | |
| `last_ingest.elapsed_sec` | float | |
| `last_ingest.stages` | object | Stage name → human-readable result |
| `updated_at` | string ISO datetime | Always written |

#### Real example

```json
{
  "providers": [
    { "role": "market_data",  "requested": "yfinance", "effective": "yfinance",
      "fell_back": false, "note": "" },
    { "role": "fundamentals", "requested": "yfinance", "effective": "yfinance",
      "fell_back": false, "note": "" },
    { "role": "transcripts",  "requested": "fmp",      "effective": "yfinance",
      "fell_back": true,  "note": "'fmp' needs FMP_API_KEY in .env" }
  ],
  "fixed_sources": [
    { "role": "macro",        "effective": "FRED" },
    { "role": "sec_filings",  "effective": "SEC EDGAR" },
    { "role": "margin_debt",  "effective": "FINRA (manual CSV)" }
  ],
  "rate_limit": {
    "rate_limited": false, "hits": 0, "cooldowns": 0, "aborted": false,
    "first_hit_at": null, "checked_at": "2026-08-20T17:42:34"
  },
  "price_coverage": { "latest_date": null, "tickers": 0, "stale_tickers": 0 },
  "last_ingest": {
    "run_id": "2e9f15124cf7",
    "finished_at": "2026-08-20T17:42:34",
    "elapsed_sec": 13.9,
    "stages": { "universe": "503 constituents (+0/-0), 34 benchmark/ETF tickers, source=cache" }
  },
  "updated_at": "2026-08-20T17:42:34"
}
```

> **⚠️ Docstring/code discrepancy.** `core/status.py`'s module docstring states the file is *"Written to `output/system_status.json` by run_data.py **and run_regime.py**."* **`run_regime.py` does not import or call `write_status`.** Only `run_data.py` does. Consequence: after a regime-only run the status file still reflects the last *ingest*, so `updated_at` can be days older than `regime_latest.json`. A UI must not use `system_status.updated_at` as the regime's freshness. Either fix the docstring or add the call — do not leave both.

### 17.3 `regime_history` table — ✅ Written, ❌ never read

**Producer:** `regime/composite.persist()`, one row per day, `INSERT OR REPLACE` so a rerun overwrites the same day.

```sql
CREATE TABLE IF NOT EXISTS regime_history (
    run_date        TEXT PRIMARY KEY,   -- ISO date; one row per day
    composite_score REAL,               -- Regime Score, 100 = risk-on
    regime_label    TEXT,               -- "Strong Risk-On" etc.
    money_score     REAL,               -- nullable
    behavior_score  REAL,               -- nullable
    capital_status  TEXT,               -- High | Medium | Low | Unknown
    detail_json     TEXT,               -- full to_dict() payload, JSON
    created_at      TEXT
);
```

Read back by `composite.history(db, days=180)`, which returns the six scalar columns (**not** `detail_json`) ordered oldest-first. **This is the data source for §18.5's trend charts.** `detail_json` holds the complete indicator-level payload for any date, so a historical drill-down needs no schema change.

> **Caveat for charting:** `run_date` is the *engine run* date, not a market date. Rows exist only for days the engine was actually run — there will be gaps across weekends and any day it was skipped. **Do not assume a continuous daily series.** Plot against the actual dates; do not forward-fill silently.

### 17.4 `weekly_process_log` table — ✅ Written and read

```sql
CREATE TABLE IF NOT EXISTS weekly_process_log (
    step_id      TEXT NOT NULL,
    completed_at TEXT NOT NULL,      -- ISO datetime
    notes        TEXT,
    PRIMARY KEY (step_id, completed_at)
);
```

Append-only — the key includes the timestamp, so every completion is kept. `WeeklyProcess._hydrate()` reads `MAX(completed_at)` per step. See §20.4.

### 17.5 SQLite tables — and which the dashboard uses

**Verified by search: the Streamlit dashboard imports no SQLite driver and opens no database.** None of `app.py`, `config.py`, `data_sources.py`, `data_sources_panel.py`, `metrics.py`, `scoring.py`, `ui.py`, `margin_debt.py`, `import_finra.py` contains a `sqlite` reference.

The dashboard's inputs are exactly three:

| Input | Type | Path |
|---|---|---|
| Live market/macro data | HTTP | Yahoo Finance, FRED |
| Margin debt | CSV | `data/margin_debt.csv` |
| Meridian status | JSON file | `daily_dashboard/output/system_status.json` |

This is deliberate (§5.3) and **is why the dashboard runs with no setup at all**. Preserve it: a database dependency would make the dashboard unusable on a machine where Meridian has never run.

**All 14 tables in `cache/meridian.db`** (Meridian-only today):

| Table | Primary key | Written by | Read by dashboard? |
|---|---|---|---|
| `universe` | `ticker` | stage 1 | ❌ |
| `daily_prices` | `(ticker, date)` | stage 2 | ❌ |
| `fundamentals` | `(ticker, period, period_end, statement, item)` | stage 3 | ❌ |
| `fundamental_ratios` | `(ticker, period, period_end)` | stage 4 | ❌ |
| `short_interest` | `(ticker, snapshot_date)` | stage 5 | ❌ |
| `analyst_estimates` | `(ticker, snapshot_date)` | stage 6 | ❌ |
| `earnings_calendar` | `(ticker, earnings_date)` | stage 7 | ❌ |
| `filings` | `accession` | stage 8 | ❌ |
| `filing_sections` | `(accession, section)` | stage 8 | ❌ |
| `insider_transactions` | `(accession, line_no)` | stage 8 | ❌ |
| `institutional_holdings` | `(fund_cik, ticker, report_date)` | stage 9 | ❌ |
| `transcripts` | `(ticker, period)` | optional | ❌ |
| **`regime_history`** | `run_date` | `run_regime.py` | ❌ **— §18 must change this** |
| `weekly_process_log` | `(step_id, completed_at)` | `run_regime.py` | ❌ |
| `ingest_log` | `(run_id, stage)` | `run_data.py` | ❌ |

Snapshot tables (`short_interest`, `analyst_estimates`) key on `(ticker, snapshot_date)` **because accumulating history the vendor does not provide is their entire purpose.** A row must never be overwritten with a later value under the same date — Layer 2's revisions factor is built from exactly these snapshots.

**Recommended access pattern for §18:** open the database **read-only** (`file:…?mode=ro` URI). WAL mode means a reader never blocks an ingest, but a read-only handle also makes it impossible for a UI bug to corrupt ingest data.

---

## 18. Target UI Specification — "Regime & Capital Flow"

> **Status: 📋 PLANNED. None of this exists.** This section is the build spec for the next increment. Acceptance criteria are in §21.
>
> **Framework recommendation: build this page in Marimo** (§9, sequencing step 3). It is a new page, so there is no regression risk to the working Streamlit dashboard, and it is the cheapest honest evaluation of the target framework. If Marimo proves unsuitable, the same spec builds in Streamlit unchanged — nothing below depends on the framework.

### 18.1 Purpose and data sources

One page answering, in order: **What regime are we in? Is capital available? Which way is it moving? Do I trust today's reading?**

| Source | Path | Required? |
|---|---|---|
| `regime_latest.json` | `daily_dashboard/output/` | **Yes** — page is empty without it |
| `regime_history` | `cache/meridian.db`, read-only | No — trends degrade gracefully |
| `system_status.json` | `daily_dashboard/output/` | No — provider strip degrades |

**Read files and the DB directly. Do not import Meridian modules.** The file seam (§5.3) is load-bearing.

### 18.2 Layout — desktop (≥1024px)

```
┌───────────────────────────────────────────────────────────────────────────┐
│ A · STATUS BAR                                                            │
│   REGIME SCORE 90 · Strong Risk-On    Capital: HIGH    Coverage 74%       │
│   ⚠ Only 47% of behaviour indicator weight had data — provisional         │
├──────────────────────────────────────┬────────────────────────────────────┤
│ B · THE CORE MODEL                   │ C · TREND (90d)                    │
│   Money      ████████████░░  85.9    │   ┌──────────────────────────────┐ │
│   Behaviour  ██████████████  94.8    │   │  Regime / Money / Behaviour  │ │
│   ── geometric ──►  90.2             │   │  3 lines + regime bands      │ │
│   √(85.9 × 94.8) = 90.2              │   └──────────────────────────────┘ │
├──────────────────────────────────────┴────────────────────────────────────┤
│ D · INDICATOR DETAIL      [ Money (5) | Behaviour (6) ]                    │
│   Indicator      Score  Value    As of      Source     Weight   State      │
│   MMF AUM        100.0  8.29tn   2026-01-01 FRED       0.25     ● 232d old │
│   VIX Term Str.    n/a  —        —          yahoo      0.13     ✕ no data  │
├──────────────────────────────────┬────────────────────────────────────────┤
│ E · SECTOR ROTATION              │ F · ASSET CLASS PREFERENCE             │
│   ★ XLK Technology  +2  100      │   US Equity          +2  Strong OW  SPY│
├──────────────────────────────────┴────────────────────────────────────────┤
│ G · WEEKLY PROCESS      ✓1 ✓2 ✓3 ○4 — Step 4 due    [ Mark complete… ]    │
├───────────────────────────────────────────────────────────────────────────┤
│ H · DATA SOURCES & FRESHNESS (collapsed by default)                       │
└───────────────────────────────────────────────────────────────────────────┘
```

### 18.3 Required widgets

| ID | Widget | Requirements |
|---|---|---|
| **A** | Status bar | Regime Score + label + Capital Availability + Coverage %. **Every `warnings[]` entry rendered verbatim** — never truncated, never collapsed behind a click. Colour always paired with the label text. Sticky on scroll. |
| **B** | Core model panel | Money and Behaviour as labelled bars, the combination method named, and **the arithmetic shown** (`√(85.9 × 94.8) = 90.2`). Showing the working is the point — §7.1's claim is only legible if the multiplication is visible. |
| **C** | Trend chart | See §18.5. |
| **D** | Indicator table | Two tabs (Money 5 / Behaviour 6). Columns: label, score, `display`, `as_of`, `source`, `weight`, state. **Unavailable indicators must be listed, not hidden**, showing `error`. Row tooltip = `note`. Age badge per §23.4. |
| **E** | Sector rotation | 11 rows sorted by `blended_score`. Columns: ticker, name, matrix score (signed, with stance word), `momentum_pct`, blended. Star the `favored`. **When `momentum_pct` is null for all rows, show "matrix-only — no price data" prominently** — the blend silently became pure theory. |
| **F** | Asset class | 10 rows sorted by `matrix_score`, with proxy ETF. Derive the stance word locally (see §17.1 contract inconsistency). |
| **G** | Weekly process | 4 steps with status symbol, name, `display_age`, auto/manual badge. Step 4 needs a completion control — see §20.4. |
| **H** | Data sources | Provider table from `system_status.json` with fallback warnings; freshness summary. Collapsed by default; **auto-expanded when any `fell_back` is true or `rate_limit.rate_limited` is true.** |

### 18.4 Mobile behaviour (<768px)

1. **Single column**, sections stacked A → H. B/C and E/F unstack.
2. **Status bar (A) stays sticky** and compresses to: score, label, capital status, coverage. Warnings collapse to a tappable `⚠ 1` chip that expands in place. **The chip must be visible without scrolling** — a provisional score that looks confident on a phone is the worst failure mode this page has.
3. **Tables scroll horizontally inside their own container.** The page body must never scroll horizontally. Priority columns pinned left: indicator label + score; sector ticker + blended.
4. **Trend chart:** default window drops 90d → 30d; legend moves below the plot; touch-drag pans rather than selects.
5. **Minimum touch target 44×44px** for the tab switcher, the process control, and the section H toggle.
6. **No hover-only information anywhere.** Notes and tooltips must be reachable by tap.
7. Charts must render legibly at 320px.

### 18.5 Historical trends — how they must be shown

**Data:** `composite.history(db, days)` — `run_date`, `composite_score`, `money_score`, `behavior_score`, `capital_status`.

**Chart 1 — Regime trajectory (primary).**
- Three lines: Regime Score (emphasis), Money, Behaviour (both lighter).
- Y-axis fixed **0–100** — never auto-scaled. An auto-scaled axis makes a 4-point wobble look like a regime change.
- Five horizontal **regime bands** as background shading at 30 / 43 / 57 / 70, labelled at the right edge.
- Window selector: **30d / 90d / 180d / All**, default 90d.
- Hover: date, all three scores, regime label, capital status.
- **Gaps must render as gaps.** Rows exist only for days the engine ran (§17.3). Plot against real dates; never forward-fill silently. If a gap exceeds 3 days, mark it.

**Chart 2 — Capital Availability history (secondary).**
- A horizontal band chart of High / Medium / Low over time, aligned to Chart 1's x-axis.
- Because it is a three-state label, **the block boundaries are the information** — do not draw it as a line.

**Required annotation — the interpretation the whole chart exists for:**

> A Regime Score of 55 means something different climbing from 40 than falling from 70. Show the level **and** the trajectory: alongside the current score, display the change over 5 and 20 engine-runs with an explicit direction word (`improving` / `deteriorating` / `flat`), not just an arrow.

**Empty-history behaviour:** with fewer than 2 rows, replace both charts with *"Trend needs at least two runs. Run `run_regime.py` daily to build history."* — **not** a blank panel or a single floating point.

### 18.6 Empty, partial and rate-limited states

Every state must be **explicit and worded**, never a blank region. Colour is never the sole channel.

| # | Condition | Detection | Behaviour |
|---|---|---|---|
| 1 | **No Meridian output at all** | `regime_latest.json` absent | Full-page empty state: what the page will show, the exact command (`cd daily_dashboard && python run_regime.py`), expected runtime. **Not an error.** |
| 2 | **Stale regime** | `run_date` older than today | Amber banner: *"Regime last computed {n} days ago ({date}). Re-run for a current reading."* Render everything normally beneath. |
| 3 | **Partial coverage** | `coverage < 0.60`, or either half `< 0.60` | **Score displayed with a visible provisional treatment** (hatched bar fill or explicit `~` prefix) plus the `warnings[]` text. **The score must not be presented as a clean regime call.** See §23.3 for why this matters. |
| 4 | **One half missing** | `money_score` or `behavior_score` is null | Show the surviving half; render the missing one as an explicit "no data" slot, not zero. Banner: *"This is not a capital-availability reading — only the {money/behaviour} half scored."* Suppress the ×/√ arithmetic in panel B. |
| 5 | **Nothing scored** | `warnings` contains the defaulting message | The 50.0 default must **never** display as "Neutral" without the caveat *"defaulted — no indicators scored"*. |
| 6 | **Rate-limited ingest** | `system_status.rate_limit.rate_limited` | Red-bordered notice in section H, auto-expanded. If `aborted` is true add: *"fetch stopped early — prices are partial."* Direct to a local re-run. |
| 7 | **Provider fallback** | any `providers[].fell_back` | Amber notice naming requested → effective and the `note`. Section H auto-expands. |
| 8 | **Sector scan matrix-only** | all `momentum_pct` null | Inline caption on section E: *"Matrix-only — no price data. Relative strength is not contributing."* |
| 9 | **No status file** | `system_status.json` absent | Section H shows *"Layer 1 has not run"*. **Never block the rest of the page.** |
| 10 | **Individual indicator down** | `score` null | Row present, greyed, `error` shown, weight struck through to signal exclusion. |

### 18.7 Displaying both scores together — required labelling

If the Regime Score and the Stress Score ever appear on one screen, **all six rules are mandatory.** This is the highest-risk UI decision in the system (§16.1).

1. **Never label either as "score" alone.** Always the full name: **Regime Score** / **Stress Score**.
2. **Always attach the direction inline**, not in a legend or tooltip:
   - `Regime Score 90 / 100 — higher = more risk-on`
   - `Stress Score 41 / 100 — higher = more danger`
3. **Never place them adjacent on the same axis or in the same row of tiles.** Separate cards, visually distinct, with a divider.
4. **Do not colour them on a shared scale.** Green-at-100 for Regime and green-at-0 for Stress in the same viewport is precisely the confusion to avoid. Use the traffic-light meaning (green = good) computed per score, and **write the state word beside each** — `Supportive`, `Elevated stress`.
5. **State the relationship explicitly** where both appear: *"These measure different things in opposite directions. A high Regime Score is supportive; a high Stress Score is dangerous."*
6. **Never compute a difference, ratio, average or combined gauge from the two.** They share a range by coincidence, not by construction. Any arithmetic across them is meaningless.

> **Preferred alternative, and the recommendation:** keep them on separate pages. The Regime page shows the Regime Score; the existing dashboard shows the Stress Score. Cross-link with a labelled link (*"Systematic stress: 41/100 — higher is worse →"*) rather than embedding. Cheapest way to eliminate the risk entirely.

---

## 19. risk-dashboard Model Reference — All 8 Components

> ✅ **All of this is implemented and in production.** Thresholds are `(calm, stress)` from `config.THRESHOLDS`; sub-weights from `config.SUB_WEIGHTS`; derivations from `metrics.py`. Component score = weighted mean of available sub-metrics; composite = weighted mean of available components × 100. Missing sub-metrics are dropped and remaining weights renormalised.

### 19.1 Carry / FX stress — weight 20.0 (largest)

| Sub-metric | Sub-wt | Derivation | Calm | Stress |
|---|---:|---|---:|---:|
| `usdjpy_1w_pct` | 0.40 | USDJPY % change over 7 days | −1.0% | −4.0% |
| `usdjpy_1m_pct` | 0.35 | USDJPY % change over 30 days | −2.0% | −7.0% |
| `carry_cross_drawdown_pct` | 0.25 | **Worst** 60-day drawdown across AUDJPY, NZDJPY, MXNJPY, EURJPY | −2.0% | −8.0% |

The 1-week move outweighs the 1-month: acceleration matters more than trend for an unwind. The cross drawdown takes the **minimum** across four pairs because a carry unwind rarely hits every cross at once.

*Rationale:* a strengthening yen is the transmission channel — it forces leveraged carry positions closed, and those positions are funded into risk assets worldwide.

### 19.2 Rate differentials — weight 10.0

| Sub-metric | Sub-wt | Derivation | Calm | Stress |
|---|---:|---|---:|---:|
| `diff_2y_change_3m` | 0.70 | 90-day change in (US 2y − JP 2y), pp | −0.15pp | −0.75pp |
| `diff_2y_level` | 0.30 | US 2y − JP 2y, pp | 1.0pp | 4.0pp |

*Rationale:* a wide differential is the **incentive** to carry; a narrowing one removes the reason to hold. Compression turns a crowded trade into an exit. Level alone is fuel, not fire — which is why it is weighted 0.30 and why the escalation rule (§7.10) requires level **and** yen strength together.

> **Known approximation, disclosed in the UI.** The JGB leg is a single manual number, so the *history* of the differential is the US leg shifted by today's JGB yield. The shape — which is what compression detection needs — is dominated by the far more volatile US leg.

### 19.3 Treasury volatility — weight 10.0

| Sub-metric | Sub-wt | Derivation | Calm | Stress |
|---|---:|---|---:|---:|
| `rate_vol_pctile` | 1.00 | Percentile of MOVE (or realised-vol proxy from DGS10) over trailing 3y | 60th | 92nd |

Scored as a **percentile** specifically so the real MOVE index and the fallback proxy are interchangeable. `m.rate_vol_source` reports which is live and is shown in the UI.

### 19.4 Yield curve — weight 5.0 (smallest)

| Sub-metric | Sub-wt | Derivation | Calm | Stress |
|---|---:|---|---:|---:|
| `curve_steepening_3m` | 1.00 | 90-day change in the 10y−2y slope, pp | +0.25pp | +1.00pp |

Prefers FRED's own `T10Y2Y` over subtracting two series, which handles days where one leg is missing.

*Rationale:* rapid bull-steepening (front end falling as the market prices cuts) has historically been a better recession tell than the inversion itself.

### 19.5 Equity volatility — weight 15.0

| Sub-metric | Sub-wt | Derivation | Calm | Stress |
|---|---:|---|---:|---:|
| `vix_level` | 0.60 | `^VIX`, FRED `VIXCLS` fallback | 15.0 | 32.0 |
| `vix_term_structure` | 0.40 | `^VIX / ^VIX3M` | 0.92 | 1.05 |

*Rationale:* term structure matters more than level. VIX 20 in contango is normal uncertainty; VIX 20 in backwardation is the market pricing something breaking this month.

> Note the deliberate threshold difference from Meridian, which uses 13.0 → 30.0 for the same VIX (§7.4). Meridian scores *risk appetite*; the dashboard scores *stress*. Same input, different question, different calibration.

### 19.6 Credit spreads — weight 15.0

**Primary path** (`credit_kind == "oas"`, FRED `BAMLH0A0HYM2`):

| Sub-metric | Sub-wt | Derivation | Calm | Stress |
|---|---:|---|---:|---:|
| `hy_oas_change_1m` | 0.60 | 30-day change in HY OAS, pp | +0.10pp | +0.90pp |
| `hy_oas_level` | 0.40 | HY OAS level, pp | 3.0pp | 6.0pp |

**Fallback path** (`credit_kind == "ratio"`, when FRED OAS is unavailable):

| Sub-metric | Sub-wt | Derivation | Calm | Stress |
|---|---:|---|---:|---:|
| `hyg_lqd_drawdown_pct` | 1.00 | HYG/LQD ratio drawdown from its 180-day high | −1.0% | −5.0% |

Rate of change outweighs level: credit usually reprices risk before equities do, which is what makes it worth watching daily. `m.credit_source` names the live path in the UI.

### 19.7 Leverage / margin debt — weight 15.0

| Sub-metric | Sub-wt | Derivation | Calm | Stress |
|---|---:|---|---:|---:|
| `margin_debt_yoy` | 0.55 | FINRA debit balances, YoY % | +10.0% | +30.0% |
| `margin_debt_vs_peak` | 0.45 | % of all-time-high debit balance | 90% | 100% |

Also computed and displayed but **not scored**: `mom_pct`, `net_credit_musd` (free credit minus debit; negative = investors net borrowers), `pct_of_spx_mktcap`, `peak_month`.

> **Placeholder handling — the important part.** If `MarginStats.is_placeholder` is true or `latest_debit_musd` is null, **both sub-metrics are passed as `None`, the whole component drops out, and the remaining seven components are renormalised.** Placeholder data is never scored as calm. The UI states which of the three cases applies.

*Rationale:* leverage does not cause a selloff; it sets how violent one becomes. Record margin debt still rising is the condition under which an ordinary 5% drop becomes a forced-selling 15%.

### 19.8 Commodity / inflation shock — weight 10.0

| Sub-metric | Sub-wt | Derivation | Calm | Stress |
|---|---:|---|---:|---:|
| `oil_abs_move_1m` | 0.60 | **`abs()`** of WTI 30-day % change | 8.0% | 25.0% |
| `oil_vol_pctile` | 0.40 | Percentile of WTI 20-day realised vol over trailing 3y | 60th | 90th |

The absolute value is deliberate: a spike is a supply/inflation shock, a collapse is a demand/growth shock, and **both constrain what central banks can do.** Direction is discarded; size is the signal.

### 19.9 Weight summary and the escalation layer

| Component | Weight | Share |
|---|---:|---:|
| Carry / FX | 20.0 | 20% |
| Equity volatility | 15.0 | 15% |
| Credit spreads | 15.0 | 15% |
| Leverage | 15.0 | 15% |
| Rate differentials | 10.0 | 10% |
| Treasury volatility | 10.0 | 10% |
| Commodity | 10.0 | 10% |
| Yield curve | 5.0 | 5% |
| **Total** | **100.0** | |

All eight are overridable live from the sidebar without editing `config.py`.

Escalation rules (§7.10) floor the composite *after* the weighted average. They fire on **combinations** and are the reason the model is not just an average — see `_check_escalations()` for the exact predicates.

### 19.10 Displayed but not scored

Shown in the UI for context, contributing nothing to the composite: DXY, S&P 500 level / 1w / drawdown from 365-day high, NDX, gold and copper levels and 1w changes, IG OAS, 60-day stock–bond correlation, US 30y, Fed funds, BOJ rate, policy gap, FOMC/BOJ countdowns.

The stock–bond correlation is worth watching without scoring: when it turns **positive**, bonds stop hedging equities and every 60/40-style portfolio is more fragile than its historical volatility suggests.

---

## 20. Daily Operating Workflow

### 20.1 Morning checklist (~5 minutes)

| # | Action | Where | Time | Look for |
|---:|---|---|---|---|
| 1 | Open the dashboard | `streamlit run app.py` | 30s | **Stress Score** and band |
| 2 | Check coverage | Overview banner | 5s | **< 100% means components were excluded** |
| 3 | Check escalations | Overview | 10s | Any fired rule — read its description |
| 4 | Read the explanation | Overview | 30s | Top 3 contributing components |
| 5 | Scan the Watchlist tab | Watchlist | 60s | The morning shortlist |
| 6 | Check the data-sources panel | Sidebar | 10s | Rate-limit or fallback warnings |
| 7 | Run the regime engine | `python run_regime.py` | 1–3 min | **Regime Score**, Capital Availability, favored sectors |
| 8 | Compare the two | — | 30s | **Disagreement is information** — see below |

**Step 8 is the one worth doing slowly.** The two models answer different questions on different calibrations. When they disagree, that is a signal, not a bug:

| Stress Score | Regime Score | Reading |
|---|---|---|
| Low | Risk-On | Aligned. Conditions supportive. |
| High | Risk-Off | Aligned. Reduce risk. |
| **Low** | **Risk-Off** | Nothing is breaking, but money or appetite is absent. Grinding, low-conviction tape. |
| **High** | **Risk-On** | Liquidity abundant *and* something is cracking. Historically the most dangerous quadrant — leverage is present and stress is rising. Treat with the most caution. |

### 20.2 What must run locally vs what is view-only

| Task | Where | Why |
|---|---|---|
| **Streamlit dashboard** | Anywhere | Live fetch, no DB. Yahoo 429 possible on shared IPs → panel says so |
| **`run_regime.py`** | Anywhere; **local preferred** | ~10 Yahoo calls. Degrades to FRED fallbacks under 429 (§23.3 shows this happening) |
| **`run_data.py` full universe** | 🔴 **LOCAL ONLY** | ~530 tickers. Cloud/shared IPs get 429 regardless of pacing |
| **`run_data.py --stage filings`** | Anywhere | SEC EDGAR, no Yahoo. Needs `SEC_USER_AGENT` |
| **`run_data.py --stage institutional`** | Anywhere | SEC EDGAR only |
| **`import_finra.py`** | Anywhere | Local file conversion |
| **Reading `regime_latest.json` / DB** | Anywhere | View-only, no network |

**Rule of thumb:** anything touching Yahoo **in bulk** is local-only. Everything else travels.

### 20.3 Cadence

| Frequency | Task | Command |
|---|---|---|
| **Daily** | Dashboard check | `streamlit run app.py` |
| **Daily** | Regime engine (builds trend history) | `python run_regime.py` |
| **Weekly** | Full data ingest, local | `python run_data.py` |
| **Weekly** | Step 4 review (see §20.4) | `--complete-step opportunity_filter` |
| **Monthly** | FINRA margin debt | `python import_finra.py --xlsx …` |
| **Quarterly** | 13-F refresh (filed ~45d after quarter end) | `python run_data.py --stage institutional` |

> **Running `run_regime.py` daily is not optional if you want §18.5's trend charts.** `regime_history` has one row per *engine run*. Skipped days are permanent gaps — there is no backfill.

### 20.4 How Step 4 is captured — ✅ implemented

Steps 1–3 are marked complete automatically by `mark_auto_steps()` when the regime engine runs, because running it *is* performing them. Each auto-completion stores the actual finding as its note, so the log doubles as a history of what the process said each week:

```
macro_vol_check     → "Strong Risk-On · composite 90/100 · behaviour 94.8"
capital_assessment  → "Capital High · money score 85.9"
sector_rotation     → "Sector scan run with the regime engine"
```

**Step 4 — Opportunity Filter & Edge Review — is `auto: false` and is never auto-completed.** Reviewing candidates and articulating why an edge exists is the part that cannot be automated; auto-completing it would turn the checklist into theatre.

**Capture mechanism (the only one today — CLI):**

```bash
python run_regime.py --complete-step opportunity_filter \
    --notes "Reviewed 6 names in XLK/XLF. Long NVDA on datacentre capex; edge is
             the Street modelling FY27 gross margin 300bp below guidance."
```

This writes one row to `weekly_process_log` (`step_id`, `completed_at`, `notes`). The step reports `current` for `staleness_days: 7`, then flips to `due`. Invalid step IDs are rejected with the valid list.

**Where the notes go.** `weekly_process_log` is append-only — the primary key includes the timestamp — so every completion is kept permanently. `_hydrate()` reads `MAX(completed_at)` per step for the current status, but the full history remains queryable:

```sql
SELECT completed_at, notes FROM weekly_process_log
WHERE step_id = 'opportunity_filter' ORDER BY completed_at DESC;
```

**This is the system's trade-rationale journal.** It is the only place a "why did I take this position" record exists.

> **📋 Gap.** There is **no UI for step 4** — CLI only, and nothing reads the note history back. §18.3 widget G should provide a text-area completion control and a reverse-chronological view of past notes. Without that, the journal is write-only in practice.

---

## 21. Acceptance Criteria — Definition of Done

> Scope: the **Regime & Capital Flow page** (§18), the next increment. Every criterion is objectively verifiable. `AC-n` numbering is for use in review.

### 21.1 Data loading

| ID | Criterion | How to verify |
|---|---|---|
| AC-1 | Page renders `regime_latest.json` without importing any Meridian module | `grep` the page source for `from regime` / `import regime` → no matches |
| AC-2 | Reads `regime_history` **read-only** | Connection uses `mode=ro`; page cannot write |
| AC-3 | Reads `system_status.json` if present, renders fully if absent | Rename the file; page still renders |
| AC-4 | No network calls | Disconnect network; page renders from disk |
| AC-5 | Page load < 2s with 180 days of history | Time it |

### 21.2 Correctness — the numbers must match the engine

| ID | Criterion | How to verify |
|---|---|---|
| AC-6 | Regime Score, label, Money, Behaviour, Capital Status, coverage all match `regime_latest.json` exactly | Field-by-field against the JSON |
| AC-7 | All 11 indicators listed, including unavailable ones | Count rows = 5 + 6 |
| AC-8 | Unavailable indicators show `error`, never 0 or blank | Force a null; confirm text |
| AC-9 | Panel B's stated arithmetic evaluates correctly | `√(85.9 × 94.8) = 90.2` ✓ |
| AC-10 | All 11 sectors and 10 asset classes shown, correctly sorted | Compare with console output |
| AC-11 | Asset-class stance words derived locally (file lacks `stance`) | Confirm `+2` → "Strong Overweight" |

### 21.3 States — §18.6, all ten

| ID | Criterion | How to verify |
|---|---|---|
| AC-12 | State 1: missing `regime_latest.json` → empty state with the exact command, **not** an error/stack trace | Rename the file |
| AC-13 | State 2: `run_date` < today → stale banner with day count | Edit `run_date` |
| AC-14 | State 3: coverage < 0.60 → provisional treatment **and** warning text | Use the real 2026-08-21 file (coverage 0.735, behaviour 0.47) |
| AC-15 | State 4: null half → surviving half shown, arithmetic suppressed, banner shown | Null `behavior_score` |
| AC-16 | State 5: defaulted 50.0 never reads as plain "Neutral" | Inject the defaulting warning |
| AC-17 | State 6: `rate_limited` → red notice, section H auto-expanded; `aborted` adds the partial-prices line | Set the flags |
| AC-18 | State 7: any `fell_back` → amber notice naming requested → effective | Use the real file (`transcripts` fell back) |
| AC-19 | State 8: all `momentum_pct` null → "matrix-only" caption on section E | Use the real file |
| AC-20 | State 9: missing status file → section H degrades, page unaffected | Rename it |
| AC-21 | State 10: null indicator → greyed row, weight struck through | Use the real file (4 null indicators) |
| AC-22 | **Every `warnings[]` entry rendered verbatim, none truncated** | Compare strings exactly |

### 21.4 Trends — §18.5

| ID | Criterion | How to verify |
|---|---|---|
| AC-23 | Y-axis fixed 0–100, never auto-scaled | Feed a 5-point range; axis stays 0–100 |
| AC-24 | Regime bands shaded at 30 / 43 / 57 / 70 and labelled | Visual |
| AC-25 | Window selector 30/90/180/All, default 90 | Click each |
| AC-26 | **Gaps render as gaps; no silent forward-fill** | Delete a mid-series row; confirm a visible break |
| AC-27 | < 2 rows → the specified message, not a blank panel or lone point | Empty the table |
| AC-28 | Capital history drawn as blocks, not a line | Visual |
| AC-29 | Direction stated as a **word** (`improving`/`deteriorating`/`flat`) over 5 and 20 runs | Confirm text present |

### 21.5 Mobile — §18.4

| ID | Criterion | How to verify |
|---|---|---|
| AC-30 | No horizontal body scroll at 320/375/390/768px | Resize |
| AC-31 | Tables scroll inside their own container | Wide table at 320px |
| AC-32 | **Warning chip visible without scrolling at 390px** | Load state 3 on a phone viewport |
| AC-33 | Touch targets ≥ 44×44px | Inspect |
| AC-34 | No hover-only information | Keyboard/touch traversal |
| AC-35 | Charts legible at 320px; legend below plot | Visual |

### 21.6 Dual-score safety — §18.7

| ID | Criterion | How to verify |
|---|---|---|
| AC-36 | The word "score" never appears unqualified | Search rendered text |
| AC-37 | If both scores appear, each carries its direction inline | Visual |
| AC-38 | The two are never adjacent on a shared axis or tile row | Visual |
| AC-39 | **No arithmetic combines the two** | Code review |
| AC-40 | If separate pages: cross-link states direction (*"higher is worse"*) | Visual |

### 21.7 Non-regression and process

| ID | Criterion | How to verify |
|---|---|---|
| AC-41 | **No file outside the new page's own files is modified** | `git diff --stat` |
| AC-42 | Existing Streamlit dashboard runs unchanged | `streamlit run app.py`, all 8 tabs |
| AC-43 | `run_regime.py` and `run_data.py` unchanged | `git diff` |
| AC-44 | Page works when Meridian has never run | Fresh clone, no `output/` |
| AC-45 | Unit tests for any new pure logic (age formatting, direction words, band lookup) | `pytest` green |
| AC-46 | This spec updated to mark §18 built, with any deviations recorded | Diff review |

**Definition of Done:** AC-1 … AC-46 all pass, verified on the real 2026-08-21 `regime_latest.json` (which conveniently exercises states 3, 7, 8 and 10 simultaneously), plus one fabricated file per remaining state.

---

## 22. Known Environment Issues

### 22.1 Windows logging encoding — ✅ Fixed

**Symptom:** `UnicodeEncodeError` mid-run on Windows 11 / Python 3.14, from inside a logging handler — a stack trace for what is purely a display concern. Triggered by the arrow in `"Provider for market_data → yfinance"`.

**Cause:** Python opened both the log file and the console stream with the system locale encoding, a legacy code page (cp1252) on a Windows console. `print()` was unaffected because CPython writes to a Windows console through the **wide-character API**, which is why the banners and box-drawing characters rendered fine while logging failed on the same stream — a genuinely confusing signature.

**Fix** (`core/logging_setup.py`): `sys.stdout` and `sys.stderr` are reconfigured to UTF-8 with `errors="replace"`, and the `FileHandler` is opened with `encoding="utf-8"`. Verified: `Provider for market_data → yfinance ✓ ✗ ▲` writes and reads back intact.

**If it recurs** (older Python, an embedded console): set `PYTHONUTF8=1` or `PYTHONIOENCODING=utf-8`. Do not strip the non-ASCII characters — they are load-bearing in the console report.

### 22.2 Nested folder path — ⚠️ Environmental, unresolved

The owner's checkout sits at:

```
…\Investment\daily_dashboard\risk-dashboard\daily_dashboard\
```

`daily_dashboard` appears **twice**, and the outer one is an unrelated parent folder. **The innermost is the Meridian package.**

**Consequences.** Ambiguous instructions ("cd to daily_dashboard"), `cd ..` landing somewhere plausible but wrong, and `paths.margin_debt_csv: ../data/margin_debt.csv` resolving relative to the Meridian package — correct only from the innermost directory.

**Rule:** run `run_data.py` and `run_regime.py` **from `<repo>/daily_dashboard/`**, and `app.py` from `<repo>/`. Verify with:

```powershell
Test-Path .\config.yaml -and (Test-Path .\run_regime.py)   # in daily_dashboard
Test-Path .\app.py                                          # in the repo root
```

**Recommendation:** re-clone to an unambiguous path, e.g. `C:\dev\risk-dashboard`. Cosmetic, but it has already caused confusion once.

### 22.3 First-run ratio and market-cap issues — ✅ Fixed

**Symptom:** `fcf_yield` NULL for the entire universe **while the run reported success.** The log showed `market caps for 0 tickers`.

**Cause — an ordering bug, and the most instructive failure so far.** `compute_all_ratios` sourced shares outstanding from `fundamental_ratios.shares_outstanding`, but `fundamental_ratios` is written **by that same stage**. On a first run it is empty, so every lookup missed. On a *second* run it would partially work — meaning the bug was invisible to anyone testing on an existing database.

**Fix:** added `fundamentals.market_caps(db, period)`, reading shares outstanding from the **raw `fundamentals` table**, and `run_data.py` stage 4 now calls it. Verified by code path; **a live full run must confirm the column populates** (§10.2).

**Other first-run behaviours that are correct but look wrong:**

| Observation on a fresh database | Explanation |
|---|---|
| Stage 2 downloads from 2015-01-01, very slow | First fetch only. Later runs are incremental with a 5-day overlap for vendor restatements. |
| `price_coverage` all zeros in `system_status.json` | Stage 2 has not completed. See the real example in §17.2. |
| Universe reports `source=cache` immediately | Cached for `refresh_days: 7`. Force with `--force-universe`. |
| Snapshot tables have exactly one row per ticker | By design — they accumulate one snapshot per run. |
| Trend charts unavailable | `regime_history` needs ≥2 runs (§18.5). |
| Sector scan is matrix-only | Yahoo 429 or a first run with no price data (§18.6 state 8). |

**Recommended first-run sequence** — proves the pipeline in ~2 minutes before committing to a multi-hour run:

```powershell
python run_data.py --limit 20 --no-13f     # smoke test
python run_regime.py                       # Layer 0 needs no database
python run_data.py                         # the full run
```

### 22.4 Other environment notes

| Issue | Impact | Handling |
|---|---|---|
| `source .venv/bin/activate` fails in PowerShell | Bash syntax; leads to global installs | Use `.\.venv\Scripts\Activate.ps1` |
| PowerShell execution policy blocks activation | Cannot enter the venv | `Set-ExecutionPolicy -Scope Process RemoteSigned` |
| `SEC_USER_AGENT` unset | Filing stages refuse to start | Set it; SEC requires a real contact address |
| Yahoo 429 in the dev sandbox | Stages 2–7 cannot be verified there | Structural. Verify locally |
| No `.env` file | FMP/Polygon fall back with a warning | Expected; visible in `providers[].note` |

---

## 23. Data Freshness

> **As-of dates below are observed** from the real run of **2026-08-21**, not estimated. "Age" is days between the data's `as_of` and that run date.

### 23.1 Meridian Layer 0 indicators

| Indicator | Wt | Source | Series | Frequency | Publication lag | Observed as-of | Age |
|---|---:|---|---|---|---|---|---:|
| `mmf_aum` | 0.25 | FRED | `MMMFFAQ027S` | **Quarterly** | ~10 weeks after quarter end | 2026-01-01 | **232d** |
| `net_liquidity` | 0.25 | FRED | `WALCL`, `WTREGEN`, `RRPONTSYD` | Weekly (Wed) + daily | ~1–2 business days | 2026-08-19 | 2d |
| `reverse_repo` | 0.20 | FRED | `RRPONTSYD` | **Daily** | ~1 business day | 2026-08-20 | 1d |
| `margin_debt` | 0.20 | FINRA CSV | manual | **Monthly** | ~4 weeks + manual download | 2026-06-01 | **81d** |
| `financial_conditions` | 0.10 | FRED | `NFCI` | **Weekly** | ~1 week | 2026-08-14 | 7d |
| `hy_credit_spread` | 0.25 | FRED | `BAMLH0A0HYM2` | Daily | ~1 business day | 2026-08-19 | 2d |
| `vix_level` | 0.22 | Yahoo → **FRED fallback** | `^VIX` → `VIXCLS` | Daily | Real-time → 1 business day | 2026-08-19 | 2d |
| `copper_gold_ratio` | 0.15 | Yahoo | `HG=F / GC=F` | Daily | Real-time (~15m delay) | **null (429)** | — |
| `audjpy` | 0.15 | Yahoo | `AUDJPY=X` | Daily | Real-time | **null (429)** | — |
| `vix_term_structure` | 0.13 | Yahoo | `^VIX / ^VIX3M` | Daily | Real-time | **null (429)** | — |
| `high_beta_vs_defensive` | 0.10 | Yahoo | `SPHB/SPLV` → `XLY/XLP` | Daily | Real-time | **null (429)** | — |

**Two observations that matter more than the table.**

**The highest-weighted money indicator is the stalest.** `mmf_aum` carries 0.25 — a quarter of the Money Score — on data **232 days old**. That is not a bug: `MMMFFAQ027S` comes from the quarterly Financial Accounts release, so this is as current as the series gets. But it means **the Money Score cannot respond to a liquidity shift inside a quarter through this channel.** Combined with `margin_debt` (0.20, 81 days old), **45% of the Money Score's weight sits on data more than two months old.** A UI must show these ages (§18.3, §23.4). Whether that weighting is right is a modelling question for the owner, not a defect.

**The Behaviour Score is the fragile half.** Four of its six indicators are Yahoo-only with no FRED fallback — 0.53 of 1.00 weight. When Yahoo 429s, behaviour coverage collapses to 0.47. Both survivors happen to have FRED paths, which is the only reason the score existed at all on 2026-08-21.

### 23.2 risk-dashboard feeds

| Feed | Source | Frequency | Lag | Cache |
|---|---|---|---|---|
| FX (USDJPY, crosses, DXY) | Yahoo | Continuous | ~15 min | 30 min |
| Equity indices, VIX, VIX3M | Yahoo | Continuous | ~15 min | 30 min |
| Commodities (WTI, gold, copper) | Yahoo | Continuous | ~15 min | 30 min |
| US yields `DGS2/10/30`, `T10Y2Y` | FRED | Daily | ~1 business day | 30 min |
| Fed funds `DFF` | FRED | Daily | ~1 business day | 30 min |
| HY/IG OAS | FRED | Daily | ~1 business day | 30 min |
| `VIXCLS`, `DCOILWTICO` (fallbacks) | FRED | Daily | 1 business day – 1 week | 30 min |
| **JP 10y** `IRLTLT01JPM156N` | FRED | **Monthly** | **up to ~6 weeks** | 30 min |
| **JP overnight** `IRSTCI01JPM156N` | FRED | **Monthly** | ~6 weeks | 30 min |
| **JP 3-month** `IR3TIB01JPM156N` | FRED | **Monthly** | ~6 weeks | 30 min |
| **Margin debt** | FINRA CSV | **Monthly** | **~4 weeks + manual** | 60s |
| FOMC / BOJ calendar | Hardcoded | Static | — | — |

> **The JGB inputs are the weakest link in the Stress Score.** They feed `diff_2y` (§19.2) and both escalation predicates for `carry_unwind`. FRED has **no** 2-year Japanese series at all, so `JP2Y` is seeded from the **3-month interbank rate** — an anchor, not the real thing — and is monthly with a ~6-week lag. The sidebar seeds from FRED, shows the source and date, and allows a manual override; **the override is the intended daily workflow when the carry trade is the live question.**

### 23.3 Freshness in practice — the 2026-08-21 run

Reproduced because it is the clearest illustration of why §18.6 state 3 exists:

```
Regime Score  90.2   Strong Risk-On
Money         85.9   coverage 100%
Behaviour     94.8   coverage  47%     ← 4 of 6 indicators null (Yahoo 429)
Overall coverage     73.5%
warnings: ["Only 47% of behaviour indicator weight had data — treat this
           score as provisional."]
```

A confident-looking **90.2 / Strong Risk-On** built from **two** behaviour indicators, both of which happened to score near 100. The model behaved exactly as designed — dropped the dead feeds, renormalised, warned loudly. **The risk is entirely in presentation:** a UI that renders `90.2 Strong Risk-On` without the coverage caveat converts a correctly-hedged output into a false signal. That is what AC-14, AC-22 and AC-32 exist to prevent.

### 23.4 Recommended staleness badges

| Age vs expected frequency | Badge | Treatment |
|---|---|---|
| ≤ 1 expected period | **Current** | Normal |
| 1–2 periods | **Aging** | Muted date shown |
| > 2 periods | **Stale** | Amber, date always visible |
| Null | **No data** | Greyed, `error` shown, weight struck through |

Compare against **expected frequency, not wall-clock days** — a quarterly series 60 days old is current; a daily series 60 days old is broken.

---

## 24. What I Could Not Confirm From Code

> Everything above is drawn from the source unless listed here. This section is the honest boundary of the document.

### 24.1 Could not verify — no live run available in this environment

| # | Item | Why | How to close it |
|---:|---|---|---|
| 1 | **The `fcf_yield` fix populates the column** | Yahoo 429 blocks stages 2–7 in the sandbox. Verified by code path and unit test only. | Full local run; check `SELECT COUNT(*) FROM fundamental_ratios WHERE fcf_yield IS NOT NULL` |
| 2 | **`price_coverage` values when populated** | Every observed run has `{null, 0, 0}` — stage 2 has never completed here. Field names and the queries behind them **are** confirmed (`market_data.coverage_report`: `MAX(date)`, `COUNT(DISTINCT ticker)`, and a count of tickers whose max date trails the global max). Only the populated values are unseen. | Full local run, then re-read `system_status.json` |
| 3 | **`last_ingest.stages` values for stages 2–9** | Only `universe` has ever been observed. | Full local run |
| 4 | **Insider parsed-vs-stored now agree** | Migration verified against a synthetic legacy database; not against real Form 4 volume. | Full local run; compare `stats.insider_rows` to `SELECT COUNT(*)` |
| 5 | **Real-world Layer 1 runtime** | Never completed end-to-end here. | Time the local run |

### 24.2 Could not verify — external and time-dependent

| # | Item | Note |
|---:|---|---|
| 7 | **FRED publication lags in §23** | Series IDs, frequencies and observed as-of dates are confirmed from real output. The *lag* column is from general knowledge of each release schedule, **not** from code or a vendor calendar. Treat as indicative. |
| 8 | **FOMC / BOJ dates in `config.py`** | Hardcoded and self-described as approximate. Not checked against federalreserve.gov or boj.or.jp. |
| 9 | **`SP500_DIVISOR_BN = 8.40`** | Drifts with issuance and index changes. Not validated. Affects only the "margin debt as % of market cap" display, which is not scored. |
| 10 | **Yahoo fundamentals accuracy** | Never cross-validated against a second source. The main input risk to Layer 2. |
| 11 | **Whether Yahoo 429 behaviour differs on the owner's IP** | Sandbox-specific. The owner's Windows run succeeded where this environment cannot. |

### 24.3 Design intent I inferred rather than read

| # | Inference | Basis | Risk if wrong |
|---:|---|---|---|
| 12 | **Marimo/Polars rationale (§5.2)** | The preference was stated; the *reasons* are my reconstruction from the codebase's needs. | The real motivation may differ; the migration sequencing in §9 would need revisiting |
| 13 | **Migration effort ratings** | Extrapolated from call-site counts (216 pandas / 234 Streamlit). No migration has been attempted. | Could be materially wrong in either direction. §13 recommends a timeboxed spike before committing |
| 14 | **The morning-checklist quadrant table (§20.1)** | My synthesis of what the two models measure. **Not derived from code and not backtested.** | It is an interpretive aid, not a validated signal. Owner should confirm it matches their intent |
| 15 | **Staleness badge thresholds (§23.4)** | Proposed by me. No such logic exists. | A design proposal, not a description |
| 16 | **The entire §18 UI spec** | Synthesised from the data contracts, the stated requirement for trends, and the constraints in §16.1. **The owner has not reviewed it.** | Layout and widget choices are proposals. §18.6 states and §18.7 labelling rules are the parts I would argue for hardest |

### 24.4 Discrepancies found — flagged, not fixed

Per the instruction not to change code:

| # | Location | Discrepancy |
|---:|---|---|
| 17 | `core/status.py` docstring | Claims `run_regime.py` writes `system_status.json`. **It does not** — no import, no call. §17.2 |
| 18 | `regime/matrices.py` → `favored_sectors()` | Docstring promises a "top-half blended rank" check the code does not perform. §7.7 |
| 19 | `run_regime.py` | `--json` stdout and `regime_latest.json` emit **different shapes** for the same payload. §17.1 |
| 20 | `regime/indicators.py` | `IndicatorReading.label` is auto-titled from the key, producing `"Mmf Aum"`, `"Vix Level"`, `"Audjpy"`. Cosmetic; a UI should carry its own label map. §17.1 |

None affects the correctness of any score. Items 17–19 will bite a developer building against these contracts, which is why they are recorded here rather than left to be discovered.

---

*End of specification.*
