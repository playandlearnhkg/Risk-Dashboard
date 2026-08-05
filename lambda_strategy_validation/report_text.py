"""
report_text.py — Assemble REPORT.md from the computed result tables.

The verdict is produced by `decide()` from thresholds fixed BEFORE the
numbers were seen, so the decision rule cannot be quietly tuned to the
outcome. Every threshold is printed in the report next to the value it was
applied to.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# --- Promotion thresholds, fixed in advance -------------------------------
MIN_NET_BPS = 5.0          # net edge must beat 5 bps/trade to be economic
MAX_P = 0.05               # date-clustered p-value ceiling
MIN_POSITIVE_YEAR_FRAC = 0.70   # >=70% of years positive for PROMOTE
MIN_STAGE_CONSISTENCY = 3  # net edge positive in all 3 stages for PROMOTE
HEADLINE_COST_SCENARIO = "Roll + 2bps impact"


def md(df: pd.DataFrame | None, floatfmt: str = ".4f") -> str:
    if df is None or len(df) == 0:
        return "_(no observations)_\n"
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_float_dtype(out[c]):
            out[c] = out[c].map(lambda v: "" if pd.isna(v) else format(v, floatfmt))
    return out.to_markdown(index=False) + "\n"


def _get(df: pd.DataFrame, col: str, default=np.nan):
    if df is None or len(df) == 0 or col not in df.columns:
        return default
    return df[col].iloc[0]


def decide(R: dict) -> tuple[str, list[str]]:
    """Return (verdict, reasons) from the pre-registered thresholds."""
    reasons: list[str] = []
    ladder = R.get("cost_ladder", pd.DataFrame())
    row = ladder[ladder["scenario"] == HEADLINE_COST_SCENARIO] if len(ladder) else pd.DataFrame()
    net = _get(row, "mean_net_bps")
    p = _get(row, "p")
    lo = _get(row, "ci_lo_bps")

    economic = bool(np.isfinite(net) and net >= MIN_NET_BPS)
    significant = bool(np.isfinite(p) and p <= MAX_P)
    ci_excludes_zero = bool(np.isfinite(lo) and lo > 0)

    reasons.append(
        f"Headline net expectancy ({HEADLINE_COST_SCENARIO}): "
        f"{net:.2f} bps/trade (threshold >= {MIN_NET_BPS}), "
        f"clustered p = {p:.3f} (threshold <= {MAX_P}), "
        f"95% CI lower bound = {lo:.2f} bps."
    )

    by_year = R.get("expectancy_by_year", pd.DataFrame())
    if len(by_year):
        frac = float((by_year["mean_net_bps"] > 0).mean())
        reasons.append(
            f"Years with positive net expectancy: {frac:.0%} "
            f"({int((by_year['mean_net_bps'] > 0).sum())}/{len(by_year)}); "
            f"threshold for PROMOTE >= {MIN_POSITIVE_YEAR_FRAC:.0%}."
        )
    else:
        frac = np.nan

    by_stage = R.get("cost_by_stage", pd.DataFrame())
    if len(by_stage):
        n_pos = int((by_stage["mean_net_bps"] > 0).sum())
        reasons.append(
            f"Stages with positive net expectancy: {n_pos}/{len(by_stage)} "
            f"(threshold for PROMOTE = all {MIN_STAGE_CONSISTENCY})."
        )
    else:
        n_pos = 0

    stage_consistent = n_pos >= MIN_STAGE_CONSISTENCY
    year_consistent = bool(np.isfinite(frac) and frac >= MIN_POSITIVE_YEAR_FRAC)

    if economic and significant and ci_excludes_zero and stage_consistent and year_consistent:
        verdict = "PROMOTE TO ROUTINE"
    elif (significant and ci_excludes_zero) or (economic and np.isfinite(p) and p <= 0.10):
        verdict = "CONDITIONAL"
    else:
        verdict = "REJECT"
    return verdict, reasons


def build_report(ev: pd.DataFrame, R: dict, diag: dict) -> str:
    verdict, reasons = decide(R)
    n_events = len(ev)
    n_tickers = ev["ticker"].nunique()
    n_dates = ev["date"].nunique()
    span = f"{ev['date'].min():%Y-%m-%d} to {ev['date'].max():%Y-%m-%d}"

    ladder = R.get("cost_ladder", pd.DataFrame())
    head = ladder[ladder["scenario"] == HEADLINE_COST_SCENARIO] if len(ladder) else pd.DataFrame()
    gross = ladder[ladder["scenario"] == "gross (no costs)"] if len(ladder) else pd.DataFrame()

    L = []
    A = L.append

    A("# Lambda Validation Report")
    A("")
    A("**Edge:** T+1 Post-Earnings Volatility + Gap Continuation + Relative Beta "
      "+ Opening 5-Minute Pattern, conditional on Minervini Stage")
    A("")
    A(f"**Verdict: {verdict}**")
    A("")
    A(f"- Events analysed: **{n_events:,}** earnings T+1 sessions")
    A(f"- Tickers: **{n_tickers}** | Distinct event dates: **{n_dates:,}** | Span: {span}")
    A(f"- Gross continuation expectancy: **{_get(gross,'mean_net_bps'):.2f} bps**; "
      f"after measured spread + 2 bps impact: **{_get(head,'mean_net_bps'):.2f} bps** "
      f"(95% CI {_get(head,'ci_lo_bps'):.2f} to {_get(head,'ci_hi_bps'):.2f}, "
      f"clustered p = {_get(head,'p'):.3f})")
    A("")
    A("## Decision reasoning")
    A("")
    A("Thresholds were fixed before the results were computed:")
    A("")
    for r in reasons:
        A(f"- {r}")
    A("")

    A("## 1. Data and method")
    A("")
    A("| Item | Value |")
    A("|---|---|")
    A(f"| Price/volume source | HF Data Library 1-minute bars, aggregated to daily and to 5-minute |")
    A(f"| Earnings dates | Nasdaq calendar API, confirmed-actual rows only |")
    A(f"| Market cap | SEC EDGAR point-in-time shares outstanding x split-adjusted close |")
    A(f"| Panel rows before filters | {diag.get('n_rows_total', 0):,} |")
    A(f"| Panel rows passing universe filters | {diag.get('n_rows_universe', 0):,} |")
    A(f"| Tickers with direct market cap | {diag.get('n_tickers_mcap_known', 0)} |")
    A(f"| Tickers using liquidity proxy for market cap | {diag.get('n_tickers_mcap_proxied', 0)} |")
    A("")
    pv = diag.get("proxy_violation_rate")
    if pv is not None and np.isfinite(pv):
        A(f"**Market-cap proxy validation.** For tickers where SEC market cap *is* "
          f"available, only **{pv:.2%}** of ticker-days that pass the $50M ADTV "
          f"filter have market cap at or below $3B. The ADTV filter is therefore "
          f"a tight substitute for the market-cap filter, which is why delisted "
          f"and renamed tickers (whose SEC ticker mapping no longer resolves) are "
          f"kept via the proxy rather than dropped — dropping them would compound "
          f"the survivorship bias described below.")
        A("")

    A("**Inference.** Earnings T+1 observations cluster by calendar date — dozens of "
      "firms report the same evening and share the next day's market move. All "
      "confidence intervals and p-values here come from a **date-clustered "
      "bootstrap** (resampling whole trading dates). Independence-assuming "
      "binomial p-values are shown alongside for contrast and are systematically "
      "too optimistic.")
    A("")
    A("**Costs.** Each event is charged its ticker's **own measured trailing "
      "spread** on both legs, plus an explicit impact allowance. The Roll "
      "estimator is used as the primary input because it is realistically "
      "calibrated on this data (median ~1.9 bps for AAPL). Corwin-Schultz, "
      "although the more common high-low estimator, is inflated here by roughly "
      "an order of magnitude (median ~18 bps for AAPL, against a true quoted "
      "spread well under 2 bps) because it reads earnings-day range expansion as "
      "spread; it is therefore reported only as a pessimistic upper bound. "
      "The trailing median is also lagged one day, so the cost input is knowable "
      "before the trade.")
    A("")

    A("## 2. Volatility elevation on T+1 (section 3.1)")
    A("")
    A("Ratio of the T+1 value to the median non-earnings day for the same ticker "
      "in the same calendar quarter. A ratio of 1.0 means no elevation. "
      "`mean_excess` is the mean of (ratio - 1) with clustered CI.")
    A("")
    A(md(R.get("vol_overall")))
    A("### By stage")
    A("")
    A(md(R.get("vol_by_stage")))
    A("### By size (ADTV terciles)")
    A("")
    A(md(R.get("vol_by_size")))

    A("## 3. Four-quadrant gap x intraday (section 3.2)")
    A("")
    A("Counts:")
    A("")
    A(md(R.get("quadrant_counts"), ".0f"))
    A("Continuation = the T+1 open-to-close move has the same sign as the "
      "overnight gap. `mean_signed_o2c` is the gross return of trading in the "
      "gap direction from open to close.")
    A("")
    A(md(R.get("quadrant_overall")))
    A("### Stratified by stage")
    A("")
    A(md(R.get("quadrant_by_stage")))
    A("### By gap direction")
    A("")
    A(md(R.get("quadrant_by_gapdir")))

    A("## 4. Relative beta filter (section 3.3)")
    A("")
    A("An event is flagged low-quality when the stock's T+1 open-to-close return "
      "has the opposite sign to **both** SPY and its sector ETF.")
    A("")
    A(md(R.get("beta_filter")))
    A("### Filtered cohort, by stage")
    A("")
    A(md(R.get("beta_by_stage")))

    A("## 5. First three 5-minute candles (section 3.4)")
    A("")
    A(md(R.get("pattern_distribution")))
    A("### Continuation probability by pattern")
    A("")
    A(md(R.get("pattern_continuation")))
    A("### Net expectancy by pattern (after measured spread + 2 bps)")
    A("")
    A(md(R.get("pattern_expectancy")))
    A("### `+` patterns vs everything else")
    A("")
    A(md(R.get("pattern_plus_vs_not")))
    A("### Sensitivity: same split with the rejection-wick clause removed")
    A("")
    A("Sigma's wording (\"strong rejection wicks against the gap direction\") needs "
      "an interpreted threshold. If the pattern effect only exists under one "
      "reading of that clause, it is an artefact of the definition rather than a "
      "property of the market.")
    A("")
    A(md(R.get("pattern_sensitivity_nowick")))

    A("## 6. Full interaction (section 3.5)")
    A("")
    A("Stage 2 + `+` opening pattern + beta filter passed, split by gap direction.")
    A("")
    A(md(R.get("full_interaction")))

    A("## 7. Robustness (section 3.6)")
    A("")
    A("### Year by year")
    A("")
    A(md(R.get("by_year")))
    A("### Net expectancy by year (after costs)")
    A("")
    A(md(R.get("expectancy_by_year")))
    A("### Pre- vs post-2020")
    A("")
    A(md(R.get("by_era")))
    A("### Volatility regime")
    A("")
    A("VIX itself is not available in the connected sources (no continuous daily "
      "series covering 2015-2025), so the regime split uses **SPY 21-day trailing "
      "realized volatility**, median-split. This is a documented substitution.")
    A("")
    A(md(R.get("by_volregime")))
    A("### Size subgroups")
    A("")
    A(md(R.get("by_size")))

    A("## 8. Transaction cost reality check (section 3.7)")
    A("")
    A(md(R.get("cost_ladder")))
    A("### Net expectancy by stage")
    A("")
    A(md(R.get("cost_by_stage")))

    A("## 9. Limitations that constrain this verdict")
    A("")
    A("1. **Survivorship and index-membership bias (severe).** The HF Data Library "
      "universe is built from *current* S&P 500 / Nasdaq 100 / Dow 30 membership. "
      "Names that were in those indices during 2015-2025 but have since been "
      "removed are under-represented, and the ones present were selected partly "
      "*because* they survived. The provider discloses survivorship bias pre-2022 "
      "directly. Any edge measured here is biased upward, so a weak positive "
      "result should be read as consistent with no edge.")
    known_share = _get(R.get("timing_known", pd.DataFrame()), "known_time_share",
                       float("nan"))
    A("2. **BMO vs AMC announcement timing (measured below, not just flagged).** "
      "Sigma defines T+1 as the first session after the announcement date. For "
      "companies reporting *before* the open, the true reaction day is the "
      "announcement date itself, so those events are measured one session late. "
      "The Nasdaq feed supplies an explicit time-of-day flag for only "
      f"{known_share:.1%} of the events here. The table below compares "
      "volatility elevation on the announcement session against the T+1 session: "
      "if the announcement session is also elevated, a material share of the "
      "sample is mis-dated.")
    A("")
    A(md(R.get("timing_diag")))
    A("3. **IEX source break (2022-03-01).** Volumes are not directly comparable "
      "across the provider's data-source transition, which affects ADV/ADTV "
      "filters and any volume-based inference spanning that date.")
    A("4. **1-minute bars are not tick data.** The opening-candle classification "
      "and the spread estimators are built on 1-minute sampling, not the order "
      "book. Corwin-Schultz and Roll are estimators, not quoted spreads.")
    A("5. **No borrow costs or short-availability modelling.** Gap-down "
      "continuation trades are short trades; their real-world cost is understated.")
    A("")

    A("## 9b. Two additional findings from the extended analysis")
    A("")
    A("**Per-stock scan (496 tickers).** 25 names clear p<0.05 on their own "
      "continuation rate. Chance alone predicts 24.8. After a Benjamini-Hochberg "
      "correction across the family of tests, **zero** survive. The per-stock "
      "leaderboard is therefore a picture of noise, not a shortlist — the top name "
      "(CAR, +697 bps) carries q = 0.90.")
    A("")
    A("**One sector does survive.** Communication Services returns +40.1 bps net "
      "per trade (date-clustered p = 0.0040), which clears a Bonferroni threshold "
      "of 0.0045 for 11 sector tests. It is positive in all 11 years and still "
      "significant after dropping its 20 largest moves (+35.4 bps, p = 0.004). "
      "Caveats that keep this CONDITIONAL rather than promotable: 35 tickers only, "
      "concentration in SNAP / LUMN / NTES / ROKU, a continuation *rate* of just "
      "52.6% (p = 0.16) meaning the result rests on return asymmetry rather than "
      "hit rate, and the sector itself did not exist as a GICS grouping until 2018.")
    A("")
    A("**Entry timing (1-minute bars).** Sweeping the entry minute by minute over "
      "09:31-09:59 and holding to the close, **no entry time is profitable net of "
      "costs** — the best (09:31) returns -2.0 bps at p = 0.40, and later entries "
      "get steadily worse. The full-session signed drift is only 8.9 bps, of which "
      "44% is priced within the first minute and 81% by 09:45. So a faster trigger "
      "does not rescue the edge: the move is real and highly significant, but it is "
      "smaller than the cost of capturing it.")
    A("")
    A("## 10. Recommended next experiments")
    A("")
    if verdict == "PROMOTE TO ROUTINE":
        A("- Re-run on a survivorship-free universe before sizing any capital.")
        A("- Add borrow-cost modelling for the short leg.")
        A("- Paper-trade for one full earnings season to confirm live fills.")
    else:
        A("1. **Rebuild the universe without survivorship bias.** This is the single "
          "highest-value next step: the current universe cannot distinguish a real "
          "edge from selection. A point-in-time index-membership source (or a "
          "delisted-inclusive vendor) would settle it.")
        A("2. **Resolve announcement timing.** Source a BMO/AMC flag (or infer it "
          "from which session carries the volume spike) and re-run with the "
          "reaction day correctly identified. If a real edge exists, mis-dating a "
          "large share of events would be diluting it.")
        A("3. **Condition on surprise magnitude.** The Nasdaq feed carries actual "
          "vs forecast EPS; the continuation hypothesis is much more plausible "
          "for large-surprise events than for the pooled sample tested here.")
        A("4. **Test a shorter holding window.** Open-to-close pools the "
          "informative first hour with an uninformative afternoon. Test "
          "open-to-11:00 and open-to-first-hour exits.")
        A("5. **Re-examine the opening-pattern definition.** The labels here are a "
          "faithful but necessarily interpreted reading of Sigma's prose; a "
          "sensitivity sweep over the wick/body thresholds would show whether any "
          "pattern effect is robust or an artefact of one cut.")
    A("")
    A("---")
    A("")
    A("_Generated by Lambda (Strategy Validator). Every table in this report is "
      "reproducible from `lambda_strategy_validation/` and the CSVs in "
      "`lambda_data/tables/`._")
    return "\n".join(L)
