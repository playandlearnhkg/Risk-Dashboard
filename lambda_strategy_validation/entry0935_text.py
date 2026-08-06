"""entry0935_text.py — renders ENTRY_0935_REPORT.md."""

from __future__ import annotations

import pandas as pd

# 09:45-entry results from the previous round, for the head-to-head.
PRIOR_0945 = {
    "Simple Continuation": {
        "09:45 -> 09:50": (0.557, 6.82, -0.10, 0.879),
        "09:45 -> 09:55": (0.556, 9.00, 2.08, 0.051),
        "09:45 -> 10:00": (0.546, 8.00, 1.08, 0.375),
        "09:45 -> 10:30": (0.540, 11.25, 4.33, 0.041),
        "09:45 -> Close": (0.516, 13.36, 6.44, 0.038),
    },
    "Gap/ATR > 2.0": {
        "09:45 -> 09:50": (0.557, 11.85, 4.71, 0.146),
        "09:45 -> 09:55": (0.558, 13.38, 6.24, 0.135),
    },
}


def _t(df, cols, names, rate=(), bps=(), p=()):
    o = df[cols].copy()
    for c in rate:
        o[c] = (o[c] * 100).map(lambda v: "" if pd.isna(v) else f"{v:.1f}%")
    for c in bps:
        o[c] = o[c].map(lambda v: "" if pd.isna(v) else f"{v:+.1f}")
    for c in p:
        o[c] = o[c].map(lambda v: "" if pd.isna(v) else f"{v:.3f}")
    o.columns = names
    return o.to_markdown(index=False) + "\n"


def build(R: dict, meta: dict, windows: list) -> str:
    L, A = [], None
    A = L.append
    t1, t2, t3, t4, t5 = (R["t1_holding"], R["t2_filters"], R["t3_gapatr"],
                          R["t4_distribution"], R["t5_net"])

    A("# Lambda — Entry at 09:35")
    A("")
    A("Re-test with entry immediately after the first 5-minute candle closes, "
      "under the same strict no-look-ahead discipline.")
    A("")
    A("## Rules")
    A("")
    A("| Input | Definition |")
    A("|---|---|")
    A("| Signal | The 09:30–09:35 candle closes in the gap direction |")
    A(f"| Entry | **Open of the 09:35 bar** (minute {meta['entry_minute']}) — "
      "the first print *after* the signal candle completes |")
    A("| SPY / Sector | Open → 09:35 only |")
    A("| Stage | Prior session |")
    A("| ATR / Gap-ATR | Prior-session ATR(14); gap in price terms ÷ that ATR |")
    A("")
    A(f"Sample: **{meta['n_events']:,}** events with a usable 09:35 price, of "
      f"which **{meta['n_cont']:,}** fire the Continuation signal and "
      f"**{meta['n_big']:,}** also have Gap/ATR > 2.0. Net figures subtract the "
      f"**{meta['cost_bps']} bps** median round-trip cost established earlier. "
      f"Cells with n < {meta['small']} are flagged. All p-values are two-sided "
      f"from a date-clustered bootstrap.")
    A("")
    A("> **Why the open of the next bar, not `c1_close`.** The signal is "
      "derived from `c1_close`, so filling at that same print would mean "
      "transacting on the exact tick that generated the signal — if that print "
      "sat on the offer, the rule would be selecting an upward-biased entry "
      "price and the measured forward return would inherit the reversal. "
      "Taking the open of the 09:35 bar separates signal and fill entirely. "
      f"{meta['n_real_open']:,} of {meta['n_events']:,} entries come from a "
      "real 09:35 print; the remainder had no trade in that exact minute and "
      "use the prevailing price from an earlier real print.")
    A("")
    A(f"> **Look-ahead guard.** The forward-filled price series is seeded from "
      f"`session_open`, the first Open of the session. For a name that does not "
      f"trade until well after the bell, that seed is a price from *after* the "
      f"intended entry — so any event with no real print by 09:35 would enter "
      f"at a future price. **{meta['n_dropped_no_print']:,} such events are "
      f"dropped outright.** They were never in the pattern cohorts (which "
      f"require real 09:30–09:35 candle data) but they were contaminating the "
      f"All-events rows, where they averaged roughly −95 bps.")
    A("")

    A("## 1. Holding period performance from 09:35")
    A("")
    A(_t(t1, ["window", "cohort", "n", "win_rate", "wilson_lo", "wilson_hi",
              "gross_bps", "gross_p", "net_bps", "net_p", "small"],
         ["Window", "Cohort", "n", "Win rate", "Wilson lo", "Wilson hi",
          "Gross (bps)", "p", "NET (bps)", "net p", "n<150?"],
         rate=("win_rate", "wilson_lo", "wilson_hi"),
         bps=("gross_bps", "net_bps"), p=("gross_p", "net_p")))

    A("## 2. Context filters (each tested alone, no combinations)")
    A("")
    A("Simple Continuation cohort only.")
    A("")
    A(_t(t2, ["window", "filter", "bucket", "n", "win_rate", "gross_bps",
              "gross_p", "net_bps", "net_p", "small"],
         ["Window", "Filter", "Bucket", "n", "Win rate", "Gross (bps)", "p",
          "NET (bps)", "net p", "n<150?"],
         rate=("win_rate",), bps=("gross_bps", "net_bps"),
         p=("gross_p", "net_p")))

    A("## 3. Gap / ATR buckets (Simple Continuation)")
    A("")
    A(_t(t3, ["window", "bucket", "n", "win_rate", "wilson_lo", "wilson_hi",
              "gross_bps", "gross_p", "net_bps", "net_p", "small"],
         ["Window", "Gap/ATR", "n", "Win rate", "Wilson lo", "Wilson hi",
          "Gross (bps)", "p", "NET (bps)", "net p", "n<150?"],
         rate=("win_rate", "wilson_lo", "wilson_hi"),
         bps=("gross_bps", "net_bps"), p=("gross_p", "net_p")))

    A("## 4. Distribution — 5, 10 and 15 minute windows")
    A("")
    A(_t(t4, ["window", "cohort", "n", "mean_bps", "median_bps", "p10", "p25",
              "p75", "p90", "pct_gt_100", "pct_lt_m100"],
         ["Window", "Cohort", "n", "Mean", "Median", "P10", "P25", "P75",
          "P90", ">+100 bps", "<−100 bps"],
         bps=("mean_bps", "median_bps", "p10", "p25", "p75", "p90"),
         p=()))
    A("Winners vs losers within the same cohorts:")
    A("")
    A(_t(t4, ["window", "cohort", "win_mean", "win_median", "loss_mean",
              "loss_median"],
         ["Window", "Cohort", "Winners mean", "Winners median", "Losers mean",
          "Losers median"],
         bps=("win_mean", "win_median", "loss_mean", "loss_median")))

    A("## 5. Expectancy before and after costs")
    A("")
    A(_t(t5, ["window", "cohort", "n", "win_rate", "gross_bps", "gross_p",
              "net_bps", "net_ci_lo", "net_ci_hi", "net_p"],
         ["Window", "Cohort", "n", "Win rate", "Gross (bps)", "gross p",
          "NET (bps)", "CI lo", "CI hi", "net p"],
         rate=("win_rate",), bps=("gross_bps", "net_bps", "net_ci_lo",
                                  "net_ci_hi"),
         p=("gross_p", "net_p")))

    # ------------------- comparison -------------------
    A("---")
    A("")
    A("## 09:35 entry versus the 09:45 entry")
    A("")
    c35 = t1[t1["cohort"] == "Simple Continuation"].set_index("window")
    A("Matched on holding length rather than clock time, Simple Continuation "
      "cohort:")
    A("")
    A("| Hold | 09:35 entry | | | 09:45 entry | | |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    A("| | Win rate | Gross | NET | Win rate | Gross | NET |")
    pairs = [("5 min", "09:35 -> 09:40", "09:45 -> 09:50"),
             ("10 min", "09:35 -> 09:45", "09:45 -> 09:55"),
             ("15 min", "09:35 -> 09:50", "09:45 -> 10:00"),
             ("~1 hour", "09:35 -> 10:35", "09:45 -> 10:30"),
             ("To close", "09:35 -> Close", "09:45 -> Close")]
    for label, w35, w45 in pairs:
        if w35 not in c35.index:
            continue
        r = c35.loc[w35]
        p = PRIOR_0945["Simple Continuation"].get(w45)
        if p is None:
            continue
        A(f"| {label} | {r['win_rate']*100:.1f}% | {r['gross_bps']:+.1f} | "
          f"**{r['net_bps']:+.1f}** | {p[0]*100:.1f}% | {p[1]:+.1f} | "
          f"**{p[2]:+.1f}** |")
    A("")

    big35 = t3[t3["bucket"] == "Gap/ATR > 2.0"].set_index("window")
    A("And for the large-gap subgroup, which was the best cohort found at "
      "09:45:")
    A("")
    A("| Hold | 09:35 entry | | 09:45 entry | |")
    A("|---|---:|---:|---:|---:|")
    A("| | Win rate | NET | Win rate | NET |")
    for label, w35, w45 in pairs[:3]:
        if w35 not in big35.index:
            continue
        r = big35.loc[w35]
        p = PRIOR_0945["Gap/ATR > 2.0"].get(w45)
        if p is None:
            A(f"| {label} | {r['win_rate']*100:.1f}% | "
              f"**{r['net_bps']:+.1f}** | — | — |")
        else:
            A(f"| {label} | {r['win_rate']*100:.1f}% | "
              f"**{r['net_bps']:+.1f}** | {p[0]*100:.1f}% | **{p[2]:+.1f}** |")
    A("")
    A("_Comparison written from the tables above; the 09:45 figures are the "
      "previously reported ones for the same cohorts._")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/entry0935.py`; tables in "
      "`lambda_data/tables/e35_*.csv`._")
    return "\n".join(L)
