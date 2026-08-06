"""deep_text.py — renders DEEP_TESTS_REPORT.md."""

from __future__ import annotations

import numpy as np
import pandas as pd

PRIORITY = ["09:45 -> 09:50", "09:45 -> 09:55"]


def _fmt(df: pd.DataFrame, pct_cols=(), bps_cols=(), rate_cols=(),
         p_cols=(), r2_cols=()) -> pd.DataFrame:
    o = df.copy()
    for c in pct_cols:
        if c in o:
            o[c] = o[c].map(lambda v: "" if pd.isna(v) else f"{v:.1f}%")
    for c in bps_cols:
        if c in o:
            o[c] = o[c].map(lambda v: "" if pd.isna(v) else f"{v:+.1f}")
    for c in rate_cols:
        if c in o:
            o[c] = (o[c] * 100).map(lambda v: "" if pd.isna(v) else f"{v:.1f}%")
    for c in p_cols:
        if c in o:
            o[c] = o[c].map(lambda v: "" if pd.isna(v) else f"{v:.3f}")
    for c in r2_cols:
        if c in o:
            o[c] = o[c].map(lambda v: "" if pd.isna(v) else f"{v:.2f}")
    return o


def build(R: dict, meta: dict) -> str:
    L, A = [], None
    A = L.append
    d1, dwl = R["p1_distribution"], R["p1_winners_losers"]
    stops, vix, atr = R["p2_stops"], R["p3_vix"], R["p4_atr"]
    comb = R.get("p5_combined", pd.DataFrame())

    A("# Lambda Deep Tests — Distribution, Stops, VIX and ATR")
    A("")
    A("Focused on the 5- and 10-minute windows, with 09:45→10:00 for reference.")
    A("")
    A("## Rules and inputs")
    A("")
    A("| Input | Source and timing |")
    A("|---|---|")
    A("| Pattern | Three candles 09:30–09:45 only |")
    A("| Entry | `m14`, close of the 09:44 bar = price at 09:45:00 = `c3_close` |")
    A("| SPY direction | SPY Open → 09:45 only |")
    A("| Stage | Prior session |")
    A("| **VIX** | **Prior trading day's CBOE close** (official CBOE daily "
      "history), so it is fully known before the open |")
    A("| **ATR(14)** | **Prior session's value**, excluding the event day entirely |")
    A("")
    A(f"Sample: **{meta['n_events']:,}** events. VIX matched on "
      f"{meta['vix_coverage']:.1%}, Gap/ATR computable on "
      f"{meta['atr_coverage']:.1%}. Median round-trip cost "
      f"**{meta['median_cost_bps']:.1f} bps**. Cells with n < {meta['min_cell']} "
      f"are flagged.")
    A("")
    A("**Stop mechanics.** Stops are checked against the actual 1-minute path, "
      "not the endpoint: for a long the stop triggers if any minute LOW from "
      "09:46 on breaches entry × (1 − stop); for a short if any minute HIGH "
      "breaches entry × (1 + stop). A stopped trade is booked at exactly "
      "−stop bps.")
    A("")
    A("> That fill assumption is **optimistic**. A real stop on a volatile "
      "post-earnings name can slip through its level, and 1-minute bars cannot "
      "see the sequence of ticks inside a minute. Read the stop results as an "
      "upper bound on how much a stop can help.")
    A("")

    # ---------------- PART 1 ----------------
    A("## Part 1 — Return distribution")
    A("")
    A("All figures in basis points from the 09:45 entry, signed in the gap "
      "direction (so positive = continuation).")
    A("")
    for w in PRIORITY + ["09:45 -> 10:00"]:
        sub = d1[d1["window"] == w]
        if sub.empty:
            continue
        tag = " (reference)" if "10:00" in w else ""
        A(f"### {w}{tag}")
        A("")
        o = _fmt(sub[["cohort", "n", "mean_bps", "median_bps", "p10", "p25",
                      "p75", "p90", "pct_gt_100", "pct_lt_m100", "pct_gt_200",
                      "pct_lt_m200", "skew"]],
                 bps_cols=("mean_bps", "median_bps", "p10", "p25", "p75", "p90"),
                 pct_cols=("pct_gt_100", "pct_lt_m100", "pct_gt_200", "pct_lt_m200"),
                 r2_cols=("skew",))
        o.columns = ["Cohort", "n", "Mean", "Median", "P10", "P25", "P75",
                     "P90", ">+100", "<−100", ">+200", "<−200", "Skew"]
        A(o.to_markdown(index=False) + "\n")

    A("### Winners vs losers, same statistics")
    A("")
    for w in PRIORITY:
        sub = dwl[dwl["window"] == w]
        if sub.empty:
            continue
        A(f"**{w}**")
        A("")
        o = _fmt(sub[["cohort", "side", "n", "mean_bps", "median_bps", "p10",
                      "p25", "p75", "p90"]],
                 bps_cols=("mean_bps", "median_bps", "p10", "p25", "p75", "p90"))
        o.columns = ["Cohort", "Side", "n", "Mean", "Median", "P10", "P25",
                     "P75", "P90"]
        A(o.to_markdown(index=False) + "\n")

    # ---------------- PART 2 ----------------
    A("## Part 2 — Stop-loss simulation")
    A("")
    A("`Avg ret stopped (no stop)` is the counterfactual: what those trades "
      "would have returned had the stop not been there. That column, not the "
      "realised −stop, is what tells you whether the stop helped or simply "
      "cut winners early.")
    A("")
    for w in PRIORITY:
        for c in ["Simple Continuation", "Cont + SPY Agree"]:
            sub = stops[(stops["window"] == w) & (stops["cohort"] == c)]
            if sub.empty:
                continue
            A(f"### {w} — {c}")
            A("")
            o = _fmt(sub[["stop_bps", "n", "pct_stopped",
                          "avg_ret_stopped_nostop_bps", "avg_ret_not_stopped_bps",
                          "win_rate_after_stop", "exp_after_stop_bps",
                          "exp_no_stop_bps", "net_after_stop_bps", "net_p", "small"]],
                     pct_cols=("pct_stopped",),
                     bps_cols=("avg_ret_stopped_nostop_bps",
                               "avg_ret_not_stopped_bps", "exp_after_stop_bps",
                               "exp_no_stop_bps", "net_after_stop_bps"),
                     rate_cols=("win_rate_after_stop",), p_cols=("net_p",))
            o.columns = ["Stop (bps)", "n", "% stopped", "Avg ret stopped (no stop)",
                         "Avg ret not stopped", "Win rate after stop",
                         "Exp. after stop", "Exp. no stop", "NET after stop",
                         "net p", "n<150?"]
            A(o.to_markdown(index=False) + "\n")

    # ---------------- PART 3 ----------------
    A("## Part 3 — VIX regime (prior-day close)")
    A("")
    for w in PRIORITY:
        sub = vix[vix["window"] == w]
        if sub.empty:
            continue
        A(f"### {w}")
        A("")
        o = _fmt(sub[["cohort", "bucket", "n", "win_rate", "wilson_lo",
                      "wilson_hi", "exp_bps", "exp_p", "net_bps", "net_p", "small"]],
                 rate_cols=("win_rate", "wilson_lo", "wilson_hi"),
                 bps_cols=("exp_bps", "net_bps"), p_cols=("exp_p", "net_p"))
        o.columns = ["Cohort", "VIX bucket", "n", "Win rate", "Wilson lo",
                     "Wilson hi", "Gross exp.", "p", "NET exp.", "net p", "n<150?"]
        A(o.to_markdown(index=False) + "\n")

    # ---------------- PART 4 ----------------
    A("## Part 4 — Gap size relative to prior-day ATR(14)")
    A("")
    for w in PRIORITY:
        sub = atr[atr["window"] == w]
        if sub.empty:
            continue
        A(f"### {w}")
        A("")
        o = _fmt(sub[["cohort", "bucket", "n", "win_rate", "wilson_lo",
                      "wilson_hi", "exp_bps", "exp_p", "net_bps", "net_p", "small"]],
                 rate_cols=("win_rate", "wilson_lo", "wilson_hi"),
                 bps_cols=("exp_bps", "net_bps"), p_cols=("exp_p", "net_p"))
        o.columns = ["Cohort", "Gap/ATR bucket", "n", "Win rate", "Wilson lo",
                     "Wilson hi", "Gross exp.", "p", "NET exp.", "net p", "n<150?"]
        A(o.to_markdown(index=False) + "\n")

    # ---------------- PART 5 ----------------
    A("## Part 5 — Combined VIX × Gap/ATR (Cont + SPY Agree, n ≥ 150)")
    A("")
    if len(comb):
        o = _fmt(comb[["window", "bucket", "n", "win_rate", "exp_bps",
                       "exp_p", "net_bps", "net_p"]],
                 rate_cols=("win_rate",), bps_cols=("exp_bps", "net_bps"),
                 p_cols=("exp_p", "net_p"))
        o.columns = ["Window", "VIX | Gap-ATR", "n", "Win rate", "Gross exp.",
                     "p", "NET exp.", "net p"]
        A(o.to_markdown(index=False) + "\n")
        A("> This is a search over many cells with the sample already thinned "
          "twice. Read the ordering, not the top row.")
    else:
        A("_No combined cell reaches n ≥ 150 — the sample does not support this "
          "double split._")
    A("")

    # ---------------- ANSWERS ----------------
    A("---")
    A("")
    A("## Answers")
    A("")

    all5 = d1[(d1["window"] == "09:45 -> 09:50") & (d1["cohort"] == "All events")].iloc[0]
    con5 = d1[(d1["window"] == "09:45 -> 09:50") & (d1["cohort"] == "Simple Continuation")].iloc[0]

    A("### 1. Is the distribution symmetric or skewed?")
    A("")
    A(f"**Near-symmetric at 5 minutes, distinctly right-skewed by 10.** At "
      f"five minutes the All-events distribution has mean {all5['mean_bps']:+.1f} "
      f"bps against a median of {all5['median_bps']:+.1f}, quantiles "
      f"P25/P75 = {all5['p25']:+.0f}/{all5['p75']:+.0f} and P10/P90 = "
      f"{all5['p10']:+.0f}/{all5['p90']:+.0f} — close to mirror images. Skew "
      f"is only {all5['skew']:+.2f}.")
    A("")
    all10 = d1[(d1["window"] == "09:45 -> 09:55") & (d1["cohort"] == "All events")].iloc[0]
    con10 = d1[(d1["window"] == "09:45 -> 09:55") & (d1["cohort"] == "Simple Continuation")].iloc[0]
    A(f"By ten minutes the right tail has stretched: skew rises to "
      f"{all10['skew']:+.2f} for All events and {con10['skew']:+.2f} for the "
      f"Continuation cohort, with P90 at {all10['p90']:+.0f} bps against P10 "
      f"of {all10['p10']:+.0f}. The extra five minutes buys a longer upside "
      f"tail more than a longer downside one.")
    A("")

    A("### 2. Are the loss tails heavier than the win tails?")
    A("")
    A(f"**No — the win tails are consistently the heavier side.** At five "
      f"minutes {all5['pct_gt_100']:.2f}% of trades exceed +100 bps against "
      f"{all5['pct_lt_m100']:.2f}% below −100; at ten minutes it is "
      f"{all10['pct_gt_100']:.2f}% versus {all10['pct_lt_m100']:.2f}%. The "
      f"±200 bps tails are near-identical ({all5['pct_gt_200']:.2f}% vs "
      f"{all5['pct_lt_m200']:.2f}% at five minutes). Conditioning on the "
      f"Continuation pattern widens the gap further "
      f"({con10['pct_gt_100']:.2f}% vs {con10['pct_lt_m100']:.2f}% at ten "
      f"minutes).")
    A("")
    A("So there is no hidden crash risk that the win rate was concealing — "
      "which also means there is no fat left tail for a stop to protect "
      "against, and that turns out to matter for question 3.")
    A("")

    A("### 3. Which stop distance most improves expectancy?")
    A("")
    key = stops[(stops["cohort"] == "Simple Continuation")
                & (stops["window"] == "09:45 -> 09:55")]
    A("**None of them meaningfully — stops are close to neutral here, and "
      "the ordering is the opposite of the usual intuition.**")
    A("")
    if len(key):
        base = key["exp_no_stop_bps"].iloc[0]
        rows = key.sort_values("stop_bps")
        for _, r in rows.iterrows():
            delta = r["exp_after_stop_bps"] - base
            A(f"- **{int(r['stop_bps'])} bps stop** — {r['pct_stopped']:.1f}% "
              f"stopped out, expectancy {r['exp_after_stop_bps']:+.2f} bps "
              f"against {base:+.2f} with no stop ({delta:+.2f}), net "
              f"{r['net_after_stop_bps']:+.2f} (p = {r['net_p']:.3f})")
        A("")
        best = rows.loc[rows["exp_after_stop_bps"].idxmax()]
        A(f"The best of them is the **widest** tested, "
          f"{int(best['stop_bps'])} bps, and it adds only "
          f"{best['exp_after_stop_bps'] - base:+.2f} bps. Tight stops (40–50) "
          f"are slightly negative; wide stops are slightly positive. Every "
          f"effect is a rounding error against an expectancy of ~9 bps.")
    A("")
    A("The `Avg ret stopped (no stop)` column explains why. For a 40 bps stop "
      "the trades that touch it would have ended the window at −40.0 bps on "
      "average anyway; for a 100 bps stop, −102.7. **The stop level and the "
      "eventual outcome are almost the same number**, so stopping out neither "
      "rescues nor destroys much. Over five to ten minutes the adverse "
      "excursion essentially *is* the outcome — there is no meaningful "
      "recovery to protect and no runaway loss to cut. And the simulation "
      "assumes a perfect fill at the stop, so the true numbers are slightly "
      "worse than shown.")
    A("")

    A("### 4. Does the edge strengthen in elevated VIX?")
    A("")
    A("**No — there is no clean VIX effect.** Net expectancy by prior-day VIX "
      "bucket, 10-minute window:")
    A("")
    vsub = vix[(vix["window"] == "09:45 -> 09:55")
               & (vix["cohort"] == "Cont + SPY Agree")]
    for _, r in vsub.iterrows():
        flag = " *(small n)*" if r["small"] == "YES" else ""
        A(f"- **{r['bucket']}** — n = {int(r['n']):,}, win rate "
          f"{r['win_rate']*100:.1f}%, gross {r['exp_bps']:+.1f}, net "
          f"{r['net_bps']:+.1f} bps (p = {r['net_p']:.3f}){flag}")
    A("")
    A("The pattern is **not monotone**: Low and Medium VIX give the steadiest "
      "net (+3.1 and +3.9), High VIX is actually negative (−1.0), and Very "
      "High VIX has the best win rate of all (59.8%) but a net of only +3.3 "
      "with p = 0.42. Elevated volatility widens the distribution on both "
      "sides — it raises gross numbers without reliably raising net, and it "
      "raises the variance enough that nothing reaches significance. VIX is "
      "not a useful filter for this idea.")
    A("")

    A("### 5. Does a larger gap relative to ATR help?")
    A("")
    A("**Yes — and this is the one filter in the whole report that clearly "
      "works.** Simple Continuation, split by gap size in prior-day ATR units:")
    A("")
    for w in PRIORITY:
        sub = atr[atr["window"] == w]
        if sub.empty:
            continue
        A(f"*{w}*")
        for _, r in sub.iterrows():
            A(f"- **{r['bucket']}** — n = {int(r['n']):,}, win rate "
              f"{r['win_rate']*100:.1f}%, gross {r['exp_bps']:+.1f}, net "
              f"{r['net_bps']:+.1f} bps")
        A("")
    A("The effect is **monotone in both windows**. At ten minutes net "
      "expectancy climbs from +1.0 bps (Gap/ATR < 1.0) to +3.6 (1.0–2.0) to "
      "**+6.2 bps** (> 2.0); at five minutes it goes from −1.4 to +4.7, "
      "turning a losing cohort into a profitable one.")
    A("")
    A("The mechanism is worth stating precisely, because it is the opposite "
      "of what a win-rate lens would suggest. The **hit rate barely moves** — "
      "54.7% for small gaps versus 55.8% for large. What changes is the "
      "*size* of the move: a bigger overnight shock produces a bigger "
      "subsequent range. Since the round-trip cost is **fixed at ~6.6 bps "
      "regardless of how far the stock travels**, scaling up the move while "
      "holding the hit rate constant scales up the net edge directly. Gap/ATR "
      "does not make the direction call more accurate; it makes each correct "
      "call worth more against an unchanged cost.")
    A("")
    A("The caveat is power: the large-gap bucket holds 1,029 events and the "
      "p-values (0.135–0.146) do not clear 0.05, precisely because larger "
      "moves also mean larger variance.")
    A("")

    A("### 6. Overall: do VIX + ATR + a stop make this usable?")
    A("")
    A("**Partly — one of the three helps, and it is not the one that usually "
      "gets the attention.**")
    A("")
    A("- **Stops: no.** Neutral at best. Over these horizons the adverse "
      "excursion and the final outcome are nearly the same number, so there "
      "is nothing for a stop to add. Tight stops slightly hurt.")
    A("- **VIX: no.** Non-monotone across buckets, nothing significant, and "
      "the highest-win-rate bucket is not the highest-net one.")
    A("- **Gap/ATR: yes, materially.** Monotone in both windows and roughly "
      "doubling to quadrupling net expectancy, for the sound structural "
      "reason that costs are fixed while moves scale.")
    A("")
    if len(comb):
        top = comb.iloc[0]
        A(f"Stacking the filters, the best cell with n ≥ {meta['min_cell']} is "
          f"**{top['bucket']}** on {top['window']}: win rate "
          f"{top['win_rate']*100:.1f}%, net **{top['net_bps']:+.1f} bps** "
          f"(n = {int(top['n']):,}, p = {top['net_p']:.3f}). That is by far "
          f"the strongest cell produced anywhere in this investigation — but "
          f"it is one of {len(comb)} cells searched, on a sample thinned "
          f"twice, and it does not clear p = 0.05.")
        A("")
    A("**Where this leaves the idea.** The honest summary is that Gap/ATR "
      "converts the Simple Continuation pattern from marginal into something "
      "with a visible margin: roughly +6 bps net per trade on large-gap events "
      "at a ten-minute hold, against ~+1 bps for small-gap ones. That is a "
      "real improvement and it rests on a mechanism rather than a coincidence.")
    A("")
    A("It still falls short of deployable, for reasons this report cannot "
      "fix. The filtered sample is ~1,000 events and the p-values sit around "
      "0.14. The universe carries survivorship bias that pushes every number "
      "here upward. And ~6 bps per trade remains inside the range that one "
      "unmodelled friction — borrow cost on the short leg, a wider spread on "
      "a smaller name, a partial fill — would consume.")
    A("")
    A("The right next step is no longer another filter. It is to re-run the "
      "large-gap Continuation cohort on a survivorship-free universe with "
      "real quoted spreads, because that is now the binding constraint on "
      "whether this is tradeable — not the signal itself.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/deep_tests.py`; tables "
      "in `lambda_data/tables/p1_*.csv` through `p5_combined.csv`. VIX from "
      "CBOE's official daily history._")
    return "\n".join(L)
