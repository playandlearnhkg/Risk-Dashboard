# Meridian Capital Partners

A long/short equity system organised into seven layers, governed by one model:

> **Capital Availability = Money Available × Risk-on / Risk-off Behavior**

Everything else — factor weights, sector selection, portfolio construction,
risk limits — is conditional on what Layer 0 says about that equation today.

**Status:** Layers 0 and 1 are built and running. Layers 2–7 are scaffolded.

---

## Quick start

```bash
cd daily_dashboard
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then set SEC_USER_AGENT to a real email

python3 run_regime.py       # Layer 0 — run this first, every day
python3 run_data.py         # Layer 1 — full ingest (slow on first run)
```

`run_regime.py` needs no database and no API key. It is the thing you actually
look at in the morning, so it was built to work standalone.

---

## The layers

| Layer | Directory | Status | What it does |
|---|---|---|---|
| **0** | `regime/` | ✅ Built | Capital & regime engine, preference matrices, weekly process |
| **1** | `data/` | ✅ Built | All ingestion into SQLite. No scoring, no analysis. |
| 2 | `factors/` | Scaffolded | 8 factors / 27 sub-factors, sector-percentile ranked |
| 3 | `analysis/` | Scaffolded | AI analysis + regime context |
| 4 | `portfolio/` | Scaffolded | MVO + conviction tilt |
| 5 | `risk/` | Scaffolded | Vetoes, circuit breakers, MCTR |
| 6 | `execution/` | Scaffolded | Alpaca paper |
| 7 | `frontend/` | Scaffolded | Responsive dashboard |

---

## Layer 0 — Capital & Regime Engine

Runs first, every day. Everything downstream reads its output.

### The core model, implemented

Money availability and risk appetite are scored **separately**, 0–100 each,
then combined **multiplicatively** — because the model is a product, not a sum:

> Money without appetite does not bid. Appetite without money cannot bid.

The default combination is the **geometric mean** (`sqrt(money × behavior)`),
which keeps the multiplicative property — either term near zero drags the
result toward zero — while staying on a readable 0–100 scale and penalising
imbalance. 90 money with 30 appetite scores 52, not 60.

`combination_method: product` in `config.yaml` gives the literal product;
`weighted` gives an additive blend and warns you that it departs from the model.

### Indicators

| Money available | Source | Weight |
|---|---|---|
| MMF AUM | FRED `MMMFFAQ027S` | 0.25 |
| Reverse repo | FRED `RRPONTSYD` | 0.20 |
| Margin debt (YoY) | FINRA CSV (shared with the parent app) | 0.20 |
| Net liquidity | FRED `WALCL − WTREGEN − RRP` | 0.25 |
| Financial conditions | FRED `NFCI` | 0.10 |

| Risk-on / risk-off | Source | Weight |
|---|---|---|
| VIX level | Yahoo `^VIX` → FRED `VIXCLS` | 0.22 |
| VIX term structure | `^VIX / ^VIX3M` | 0.13 |
| HY credit spread | FRED `BAMLH0A0HYM2` | 0.25 |
| Copper / gold | `HG=F / GC=F` | 0.15 |
| AUD/JPY | `AUDJPY=X` | 0.15 |
| High-beta vs defensive | `SPHB / SPLV` → `XLY / XLP` | 0.10 |

A dead feed is **dropped and the rest re-weighted**, never scored as neutral —
"no data" and "perfectly average" are different statements. The report shows
coverage as a percentage and warns below 60%.

### Outputs

- Composite regime score 0–100
- Regime label: Strong Risk-On → Strong Risk-Off
- Capital availability: High / Medium / Low — from the **money half alone**,
  so the system can say *"money is abundant but nobody wants risk"*, which is
  the setup that precedes violent recoveries
- Regime-conditional factor multipliers for Layer 2
- Favored sectors and asset classes
- Weekly process checklist status

### A deliberate tension worth knowing about

Rising margin debt **raises** the money-availability score here while **raising
fragility** in the risk layer. That is intentional, not a bug. Leverage
genuinely does add buying power on the way up and genuinely does amplify the
way down. The system holds both facts rather than averaging them into
something that means neither.

At the time of writing, margin debt is at a record and growing ~49% YoY — so
Layer 0 reads Strong Risk-On *because of* a condition the risk layer flags as
maximum leverage stress. Both readings are correct, and the combination is the
signature of a late-cycle, leverage-fuelled advance.

### Preference matrices

Both the asset-class and equity-sector matrices score −2 (strong underweight)
to +2 (strong overweight) per regime, in `config.yaml`.

The sector scan **blends the matrix with live relative strength**, 60/40 by
default. A matrix encodes what *should* lead; relative strength measures what
*is* leading. Weighting the matrix while letting the tape veto it is the
behaviour you want from a rotation scan. Set `momentum_weight: 0` for pure
theory, or `matrix_weight: 0` for pure trend-following.

### Weekly process

Steps 1–3 auto-complete when the engine runs, because running it *is*
performing them. Step 4 (Opportunity Filter & Edge Review) is deliberately
manual — articulating why an edge exists cannot be automated, and
auto-completing it would make the checklist theatre.

```bash
python3 run_regime.py --complete-step opportunity_filter --notes "reviewed XLK names"
```

---

## Layer 1 — Data Infrastructure

Pure ingestion into SQLite. No scoring, no interpretation.

```bash
python3 run_data.py                  # everything
python3 run_data.py --no-filings     # skip SEC EDGAR
python3 run_data.py --no-13f         # skip institutional holdings
python3 run_data.py --quick          # universe + prices only
python3 run_data.py --stage prices   # one stage
python3 run_data.py --tickers AAPL,MSFT --limit 10   # testing
```

Stages run in dependency order and are independently fault-tolerant — a Yahoo
outage does not prevent the SEC pull from completing.

### What it ingests

1. **Universe** — S&P 500 from Wikipedia with GICS sector and sub-industry,
   plus benchmarks, the 11 sector ETFs, and the Layer 0 macro tickers.
   Refreshed weekly.
2. **Prices** — daily OHLCV, incremental, into `daily_prices`.
3. **Fundamentals** — quarterly and annual statements, plus **24 derived
   ratios** (ROE, ROA, margins, growth, D/E, FCF yield, current ratio,
   AR/revenue, CFO/NI, accruals, retained earnings, working capital, EBIT,
   R&D, shares, dividends, buybacks, asset turnover).
4. **SEC EDGAR** — 10-K (Risk Factors), 10-Q (MD&A), 8-K, Form 4.
5. **13-F** — 9 tracked funds, with multi-fund opening detection.
6. **Short interest**, **analyst estimates**, **earnings calendar**,
   **transcripts** (FMP, candidates only).

### Three design decisions that matter

**Incremental with overlap.** Prices resume from each ticker's last stored date
*minus 5 days*, not exactly at it. Vendors restate recent bars — late splits,
dividend adjustments — and a strict resume would freeze the first version of
each bar forever. The primary key makes the refetch idempotent.

**Daily snapshots of slow-moving data.** Short interest and analyst estimates
are snapshotted every run even though they change fortnightly. No free provider
serves *historical* consensus or short interest, so snapshotting is the only
way to have revision data in a month. Until ~30 days accumulate, Layer 2's
revisions factor is degenerate (all scores 50) — the run summary tells you how
many days remain.

**Form 4 signal vs noise.** Only transaction codes **P** (open-market purchase)
and **S** (sale) are marked `is_signal = 1`. Grants (A), option exercises (M),
tax withholding (F) and gifts (G) are stored but excluded. On a two-ticker test
this was 60 signal rows out of 124 — **half the rows are compensation
mechanics**, and counting a vesting event as "insider buying" is the most
common way this data gets misread.

### Provider abstraction

Everything goes through `data/providers.py`. `TradingViewProvider` and
`FutuProvider` exist as explicit stubs marking the seam — implementing them
means satisfying the documented contract and changing one line in
`config.yaml`, not rewriting six ingest modules.

```yaml
data:
  providers:
    market_data: yfinance    # → tradingview | futu | polygon | fmp
```

---

## Configuration

**Everything tunable is in `config.yaml`.** No thresholds are hardcoded.

| Change | Edit |
|---|---|
| How money × behaviour combine | `regime.combination_method` |
| Indicator weights or thresholds | `regime.money` / `regime.behavior` |
| Regime band boundaries | `regime.labels` |
| Factor multipliers per regime | `regime.factor_multipliers` |
| Sector / asset preferences | `regime.sector_matrix` / `asset_class_matrix` |
| Matrix vs momentum blend | `regime.sector_matrix.matrix_weight` |
| Data providers | `data.providers` |
| SEC rate limit, insider window | `data.sec` |

Secrets live in `.env` (gitignored). Only `SEC_USER_AGENT` is required, and
only for EDGAR access — run with `--no-filings --no-13f` to skip it entirely.

---

## Known limitations

- **Yahoo rate-limits hard (HTTP 429)**, especially from cloud and shared IPs.
  The provider healthcheck reports this up front and price stages return
  nothing rather than hanging. It usually clears within the hour.
- **13-F is quarterly and up to 45 days stale**, long-only, US-listed only.
  Treat absence as no information, never as a negative signal.
- **CUSIP→ticker mapping is name-based** and therefore partial. Unmatched
  holdings are dropped rather than guessed at — a wrong mapping would silently
  attribute one fund's position to the wrong company.
- **Estimate revisions need ~30 days of snapshots** before they mean anything.
- **Thin sectors** (<10 constituents) produce coarse percentile ranks; the run
  summary names them.

---

## Next: Layer 2

The scoring engine spec is defined — 8 factors, 27 sub-factors, all ranked as
0–100 percentiles **within GICS sector**, with regime-conditional weights from
Layer 0 and crowding detection. Layer 1 already exposes everything it needs:
`get_price_matrix`, `get_latest_ratios`, `get_ratio_history`,
`net_insider_flow`, `cluster_buys`, `fund_counts`, `multi_fund_openings`,
`revision_deltas`, and `get_change`.
