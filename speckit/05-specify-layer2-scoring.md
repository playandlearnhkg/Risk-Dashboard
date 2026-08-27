# Paste into `/speckit.specify` — Feature 002

> ⛔ **Do not start this until Feature 001 has shipped and the full 503-ticker Layer 1
> run has completed successfully.** Both are hard prerequisites; the reasons are below.
>
> This is a **starting point, not a finished spec**. Layer 2's per-factor detail lives in
> `daily_dashboard/SPEC.md` under "LAYER 2 — Scoring Engine". This prompt points there
> rather than restating ~40 sub-factors that would immediately drift out of sync.

---

## Prerequisites — verify before running this

| Prerequisite | Why | How to check |
|---|---|---|
| Feature 001 shipped | You need one completed Spec Kit cycle before attempting the largest remaining piece | The Regime page renders and its ACs pass |
| Full 503-ticker Layer 1 run completed | Layer 2 scores every name in the universe. Scoring against a partial dataset produces plausible, wrong rankings | `python run_data.py` completes; check row counts |
| `fcf_yield` populated | The ordering bug is fixed in code but **never verified against a live run** (§24.1) | `SELECT COUNT(*) FROM fundamental_ratios WHERE fcf_yield IS NOT NULL` |
| Insider parsed = stored | The PK fix is verified only against a synthetic database (§24.1) | Compare `stats.insider_rows` to `SELECT COUNT(*) FROM insider_transactions` |
| Yahoo fundamentals sanity-checked | Never cross-validated against a second source. **The main input risk to this entire feature** (§10.2) | Spot-check 10 names against another source |

**If any of these fail, fix it first.** Layer 2 amplifies data quality problems — it
computes ~40 sub-factors across ~530 tickers, and a systematic error in one input
produces a ranked list that looks authoritative and is wrong.

---

Build **Layer 2 — the Scoring Engine**: rank the equity universe on eight factors,
weighted according to the current regime.

## Problem

Meridian can currently describe the macro environment (Layer 0) and holds a complete
dataset about ~530 companies (Layer 1). It cannot answer *"given this environment, which
names are interesting?"* — the question the system exists for.

Layer 0 already computes **regime-conditional factor multipliers** every run — momentum
1.40 in Strong Risk-On, quality 1.50 in Strong Risk-Off, and so on (`PRODUCT_SPEC.md`
§7.9). **Nothing consumes them.** They are computed, printed, written to JSON, and
discarded. Layer 2 is their consumer.

## Outcomes

1. Every ticker in the universe carries a composite score and a per-factor breakdown.
2. Factor weights shift with the regime, using Layer 0's existing multipliers.
3. Every score is explainable — which factors drove it, and on what data.
4. Coverage is reported per ticker. A name scored on three of eight factors is not
   comparable to one scored on all eight, and the output must say so.

## Scope

**In scope**

- Eight factors, each with its sub-factors as specified in `daily_dashboard/SPEC.md`
  "LAYER 2": momentum, value, quality, growth, estimate revisions, short interest,
  insider activity, institutional flow.
- Cross-sectional normalisation so factors are comparable.
- Composite scoring applying Layer 0's `factor_multipliers`, **renormalised after
  application**.
- Per-ticker coverage reporting.
- Crowding detection (see `SPEC.md`).
- Persistence to SQLite, following existing table conventions.

**Out of scope**

- Portfolio construction, position sizing, risk limits — Layers 4 and 5.
- Any UI. Console output plus a database table. A Layer 2 view is a separate feature.
- Changes to Layer 0 or Layer 1.
- Any change to how the regime is computed.

## Non-negotiable behaviours

These follow from the constitution and from bugs already fixed in this repository:

- **Missing data drops out and weights renormalise** (Principle 1). A ticker missing
  short-interest data is scored on the remaining seven factors with weights
  re-normalised, and its coverage reported. It is never scored as neutral on the missing
  factor. This is the single most important requirement in the feature.
- **Form 4 signal discipline.** Only codes **P** and **S** carry signal. Codes A, M, F,
  G, C, D are compensation mechanics — stored, but excluded. Counting a vesting event as
  insider buying is the most common way this data is misread.
- **13-F common stock only.** `shares` and `value_usd` hold common stock. Options
  (`put_value_usd`, `call_value_usd`) and convertible debt (`other_value_usd`) are
  separate columns and must not be summed into conviction. Three separate bugs here have
  already produced wildly wrong readings — a $23.7bn position that was actually $2.4bn,
  and an implied $922 share price.
- **The margin-debt tension is preserved** (§7.3). Rising leverage raises money
  availability *and* raises fragility. Layer 2 must not "resolve" this.
- **No fitted parameters** (Principle 3). Factor definitions and weights are judgement
  calls in config. Introducing optimisation or backtesting is a separate decision.

## Constraints

- Reads from SQLite; does not fetch. Layer 1 owns ingestion.
- Config-driven: every factor weight, sub-factor weight and threshold lives in
  `config.yaml`.
- Must complete over the full universe in a time that suits a daily run.
- Additive: no changes to Layers 0 or 1.

## Open questions for `/speckit.clarify`

1. **Neutralisation.** Are factor scores z-scored within sector, within the whole
   universe, or both? Sector-neutral momentum and absolute momentum answer different
   questions.
2. **Minimum coverage.** Below what coverage is a ticker excluded from the ranking
   rather than reported with a caveat?
3. **Outliers.** Winsorise before normalising, and at what percentile?
4. **History.** Is the score table a daily snapshot (accumulating history, like
   `short_interest`) or current-state-only? Snapshots enable score-change signals later
   but grow quickly.
5. **Point-in-time correctness.** Fundamentals arrive with a lag. Does scoring use the
   latest *available* data, or the data that *was* available on the scoring date? The
   second is harder and matters if backtesting is ever added.
6. **Sector classification.** GICS sector from `universe`, or something finer?

**Question 5 deserves a real decision now**, not later. Retrofitting point-in-time
correctness is substantially harder than building it in, and getting it wrong makes every
future backtest optimistic in a way that is difficult to detect.

## Reference

- `daily_dashboard/SPEC.md` — "LAYER 2 — Scoring Engine": all eight factors and their
  sub-factors, the composite method, regime-conditional weighting, Regime Fit score, and
  crowding detection.
- `PRODUCT_SPEC.md` §7.9 — the multipliers this feature consumes.
- `PRODUCT_SPEC.md` §17.5 — table conventions, especially why snapshot tables key on
  `(ticker, snapshot_date)`.
- `PRODUCT_SPEC.md` §10.4 — the six silent-corruption bugs. Read these before trusting
  any input.
