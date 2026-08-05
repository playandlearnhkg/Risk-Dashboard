# Review of Phase-0 code against Sigma's research design

Reviewed after receiving Sigma's full design document (5 Aug 2026). The
Phase-0 code was written *before* that document existed, against a generic
"Weinstein/Minervini stage analysis" assumption. Several parts do not match
the actual spec and are being rewritten. This file records what was wrong
so the corrections are auditable.

## A. Stage definitions — WRONG, rewritten

`stage_classifier.py` implemented a canonical Minervini/Weinstein synthesis.
Sigma's section 2E is materially different:

| Item | Phase-0 code | Sigma spec | Action |
|---|---|---|---|
| Stage 2 criteria | 7 hard rules, ALL required | 7 listed rules, **minimum 6 of 7** | Rewritten with a 6-of-7 tolerance |
| "≥25% above 52-week low" | Required | **Not in Sigma's list** | Removed |
| Stage 4 | Full mirror-image of Stage 2 (6 inequalities) | **`Close < 200-SMA`, nothing else** | Rewritten |
| Stage 3 | Inferred by a prior-stage state machine | `Close ≥ 200-SMA` **and** fails Stage 2 | Rewritten, state machine deleted |
| Stage 1 | Implemented (basing) | **Does not exist in the design** | Removed |

The Phase-0 Stage 4 rule was far stricter than Sigma's. On AAPL it labelled
only 3.3% of history Stage 4; Sigma's definition (`Close < 200-SMA`) is a
much broader bucket. Any Stage-stratified result from the old code would
have been describing a different partition than the one Sigma asked for.

**Consistency proof for the rewrite** (worth stating, since 6-of-7 looks
like it could create overlap between Stage 2 and Stage 4): criterion 2 is
`Close > 150-SMA` and criterion 5 is `150-SMA > 200-SMA`; together they
imply `Close > 200-SMA`, which is criterion 3. So failing criterion 3
forces failing criterion 2 or 5 as well — at least two failures, i.e. at
most 5 of 7. Therefore **any 6-of-7 Stage 2 stock necessarily has
`Close > 200-SMA`** and can never also satisfy Stage 4. Stages 2/3/4 form a
clean, exhaustive, mutually exclusive partition of all classifiable days.

## B. Performance — was unusable at universe scale

`classify_series` looped with `.iterrows()` and assigned via `.loc` per row.
At ~3 s per ticker that is ~40 minutes for the universe, repeated on every
parameter change. Rewritten fully vectorised.

The same defect appeared in `build_derived.py`'s first draft (per-session
`between_time` slicing, 13.4 s/ticker ≈ 3 h for the universe). Vectorised to
2.5 s/ticker (~5x), verified to produce identical values.

## C. `test_battery.beta_filter_impact` — WRONG CONCEPT

The Phase-0 function filtered on a numeric beta coefficient (`beta <= 1.5`).
Sigma's section 2C is **not** a beta-magnitude filter: it flags an
observation as low-quality when the stock's T+1 return has the **opposite
sign to both SPY and its sector ETF**. Different construct entirely —
rewritten as a sign-agreement filter.

## D. Bootstrap inference — understates uncertainty

`bootstrap_mean_ci` resamples trades i.i.d. In this design, observations are
**clustered by calendar date** (many stocks report the same day and share
that day's market move). An i.i.d. bootstrap treats those as independent and
will produce confidence intervals that are too narrow — exactly the failure
mode that manufactures false positives. Replaced with a **date-clustered
bootstrap** (resample whole dates, not individual observations).

## E. Cost model — arbitrary constants replaced with measured data

`cost_model.py` used assumed half-spread constants (2/5/10 bps). The HF
variables table ships **measured per-ticker per-day Roll and
Corwin-Schultz spread estimates**. Using the real measured spread per
observation is strictly better than a global guess, and directly serves
section 3's "Transaction Cost Reality Check". Scenario multipliers are kept
for sensitivity, now applied on top of measured spreads.

## F. `market_cap.py` — two latent bugs

1. `us-gaap/CommonStockSharesOutstanding` is not filed by every company;
   the code had no fallback and would fail outright on those tickers. Needs
   a `dei/EntityCommonStockSharesOutstanding` fallback (both confirmed
   available on SEC's API).
2. `drop_duplicates("filed", keep="last")` after sorting on `filed` alone is
   order-dependent when one filing date carries several period-end values.
   Should sort on `["filed", "end"]` before dropping.

The split-adjustment logic itself was validated against AAPL and is sound,
but the ratio-band heuristic (0.4-2.5) remains a known approximation — a
large single-filing share-count change from an acquisition could be
misread as a split. Flagged, spot-checks planned.

## G. What was correct and is kept

- `universe_filters.py` — ADV/ADTV/price logic is right; rolling windows and
  point-in-time application avoid look-ahead.
- `data_ingest.py` — correct, and the aggregation was verified against real
  AAPL sessions.
- The synthetic stage test harness concept (validate rules on a constructed
  path before trusting real data) — kept, rewritten for the new definitions.
- Keeping the API key in an env var and raw data out of the repo.

## H. Data-source problems found during Phase 0 (unchanged, still relevant)

- Nasdaq calendar API's `marketCap` field returns **today's** market cap on
  every historical row — never use it.
- HF split-adjusted price × SEC unadjusted share count understates historical
  market cap by the cumulative split ratio (caught a ~4.2x error on AAPL).
