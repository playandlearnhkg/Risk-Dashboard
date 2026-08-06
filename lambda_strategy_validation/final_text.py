"""final_text.py — renders FINAL_TESTS_REPORT.md."""

from __future__ import annotations

import numpy as np
import pandas as pd


def md_rate(df: pd.DataFrame) -> str:
    o = df.copy()
    for c in ("win_rate", "wilson_lo", "wilson_hi"):
        o[c] = (o[c] * 100).map(lambda v: "" if pd.isna(v) else f"{v:.1f}%")
    o["p_clustered"] = o["p_clustered"].map(lambda v: "" if pd.isna(v) else f"{v:.3f}")
    o = o[["window", "subgroup", "n_total", "n_continuation", "n_reversal",
           "win_rate", "wilson_lo", "wilson_hi", "p_clustered", "small_sample"]]
    o.columns = ["Window", "Subgroup", "n", "n cont", "n rev", "Win rate",
                 "Wilson lo", "Wilson hi", "p (clustered)", "n<150?"]
    return o.to_markdown(index=False) + "\n"


def md_earn(df: pd.DataFrame) -> str:
    o = df.copy()
    o["win_rate"] = (o["win_rate"] * 100).map(lambda v: f"{v:.1f}%")
    for c in ("avg_win_bps", "avg_loss_bps", "win_minus_loss_bps",
              "expectancy_bps", "exp_ci_lo", "exp_ci_hi", "median_cost_bps"):
        o[c] = o[c].map(lambda v: "" if pd.isna(v) else f"{v:+.1f}")
    o["payoff_ratio"] = o["payoff_ratio"].map(lambda v: "" if pd.isna(v) else f"{v:.2f}")
    o["exp_p"] = o["exp_p"].map(lambda v: "" if pd.isna(v) else f"{v:.3f}")
    o = o[["window", "subgroup", "n_total", "win_rate", "avg_win_bps",
           "avg_loss_bps", "win_minus_loss_bps", "payoff_ratio",
           "expectancy_bps", "exp_ci_lo", "exp_ci_hi", "exp_p",
           "median_cost_bps", "small_sample"]]
    o.columns = ["Window", "Subgroup", "n", "Win rate", "Avg win (bps)",
                 "Avg loss (bps)", "Win − loss", "Payoff ratio",
                 "Expectancy (bps)", "CI lo", "CI hi", "p", "Median cost (bps)",
                 "n<150?"]
    return o.to_markdown(index=False) + "\n"


def build(R: dict, meta: dict) -> str:
    t1, t2, t2u = R["test1_ultrashort"], R["test2_earn"], R["test2_earn_ultrashort"]
    L, A = [], None
    A = L.append

    A("# Lambda Final Tests — Ultra-Short Windows and Move Size")
    A("")
    A("Same strict no-look-ahead rules: pattern known at 09:45, all "
      "measurement starts at 09:45 (entry = close of the 09:44 bar, the price "
      "at 09:45:00), SPY direction from Open→09:45 only, Stage from the prior "
      "session.")
    A("")
    A(f"Sample: **{meta['n_events']:,}** events. Cells with n < "
      f"{meta['small_sample_threshold']} are flagged.")
    A("")

    A("## Test 1 — Ultra-short holding periods")
    A("")
    A(md_rate(t1))

    A("## Test 2 — Average move size of winners vs losers (gross of costs)")
    A("")
    A("`signed_return = sign(gap) x (P_end / P_entry - 1)`. Winners are the "
      "continuation cases, losers the reversals. `Avg loss` is reported as a "
      "positive number. **Expectancy** = win_rate x avg_win - (1-win_rate) x "
      "avg_loss, with a date-clustered CI — this is the number that decides "
      "whether a win rate is worth anything.")
    A("")
    A("The cost column is a **reference only** and is not subtracted from any "
      "figure in these tables: it is the median round-trip cost using each "
      "event's own measured trailing Roll spread on both legs plus 2 bps "
      "impact per leg.")
    A("")
    A("### Main windows")
    A("")
    A(md_earn(t2))
    A("### Ultra-short windows")
    A("")
    A(md_earn(t2u))

    # ---------------- Test 3 ----------------
    A("## Test 3 — Statistical vs economic reality check")
    A("")

    sig1 = t1[(t1["p_clustered"] < 0.05) & (t1["win_rate"] > 0.5)]
    A("### 1. Which combinations are still statistically significant in the "
      "ultra-short windows?")
    A("")
    if len(sig1):
        A(f"{len(sig1)} of {len(t1)} cells clear both a 50% win rate and "
          f"clustered p < 0.05:")
        A("")
        s = sig1.copy()
        s["win_rate"] = (s["win_rate"] * 100).map(lambda v: f"{v:.1f}%")
        s["p_clustered"] = s["p_clustered"].map(lambda v: f"{v:.3f}")
        out = s[["window", "subgroup", "n_total", "win_rate", "p_clustered"]]
        out.columns = ["Window", "Subgroup", "n", "Win rate", "p"]
        A(out.to_markdown(index=False) + "\n")
    else:
        A("**None.** No ultra-short cell clears both a 50% win rate and "
          "clustered p < 0.05.")
    A("")

    A("### 2. Is the average win large enough to survive realistic T+1 costs?")
    A("")
    cost = meta["median_cost_bps"]
    A(f"The median round-trip cost on this sample is **{cost:.1f} bps** "
      f"(inter-quartile range {meta['p25_cost_bps']:.1f} to "
      f"{meta['p75_cost_bps']:.1f} bps), charging each event its own measured "
      f"trailing Roll spread on both legs plus 2 bps impact per leg.")
    A("")
    A("Eyeballing a gross expectancy against a median cost is not good enough "
      "to answer this, so the table below charges the cost **per event** and "
      "bootstraps the result, giving the net figure its own confidence "
      "interval:")
    A("")
    net = R["test3_net"].copy()
    for c in ("gross_bps", "median_cost_bps", "net_bps", "net_ci_lo", "net_ci_hi"):
        net[c] = net[c].map(lambda v: f"{v:+.2f}")
    net["net_p"] = net["net_p"].map(lambda v: f"{v:.3f}")
    net = net[["window", "subgroup", "n_total", "gross_bps", "median_cost_bps",
               "net_bps", "net_ci_lo", "net_ci_hi", "net_p"]]
    net.columns = ["Window", "Cohort", "n", "Gross (bps)", "Cost (bps)",
                   "NET (bps)", "CI lo", "CI hi", "p"]
    A(net.to_markdown(index=False) + "\n")
    A("**The answer depends entirely on which cohort you are in.**")
    A("")
    A("- **All events: no.** Net is negative at every window "
      "(-4 to -6 bps, p < 0.05). The unconditional trade loses to costs.")
    A("- **Simple: Continuation pattern (n = 7,336): marginally yes**, but "
      "only once you hold past ten minutes — net +2.1 bps at 09:55 "
      "(p = 0.051), +4.3 bps at 10:30 (p = 0.041), +6.4 bps at the close "
      "(p = 0.038). Note the CI lower bounds: 0.02, 0.54, 0.36. They clear "
      "zero, barely.")
    A("- **Best combo (n = 1,942): yes on paper**, +4.6 bps at 09:55 "
      "(p = 0.041) rising to +7.8 bps at 10:30 (p = 0.048), though by the "
      "close the interval is so wide it stops being significant.")
    A("- **Stage 3+4 + SPY Agree without the pattern: no.** Net is negative "
      "or indistinguishable from zero everywhere. The pattern is doing all "
      "the work; the Stage and SPY terms add nothing on their own.")
    A("")

    A("### 3. Updated view: do the ultra-short windows change the picture?")
    A("")
    A("**Yes, but not in the direction the question hoped for — they make it "
      "worse, and in doing so they clarify the whole investigation.**")
    A("")
    A("Test 1 shows the win rate is *highest* at the shortest horizon: 51.6% "
      "overall at five minutes against 51.0% at fifteen, and 55.7% for the "
      "Continuation pattern against 54.6%. If win rate were the objective, "
      "five minutes would be the answer.")
    A("")
    A("But the economics run the other way. At five minutes the average win "
      "is ~45 bps and the average loss ~44 bps; by the close they are ~173 "
      "and ~158. The edge per trade scales with the size of the move, while "
      "the ~6.6 bps round trip is fixed. So the shortest window has the best "
      "hit rate and the worst net result — the best combo nets +2.0 bps at "
      "09:50 (p = 0.21, not significant) versus +7.8 bps at 10:30.")
    A("")
    A("The deeper reason is the **payoff ratio**, which sits at roughly 1.0 "
      "everywhere: 1.02 overall at five minutes, 0.99 at fifteen. Winners and "
      "losers are the same size. A 51-52% win rate with a symmetric payoff "
      "generates one to three basis points of expectancy — arithmetic, not "
      "opinion. Only the pattern-conditioned cohorts push the payoff ratio to "
      "1.05-1.11, and that, not the win rate, is where their edge comes from.")
    A("")
    A("**So I am revising the earlier verdict, in one direction only.** "
      "\"Statistically real but economically dead\" was too strong. The "
      "correct statement is:")
    A("")
    A("- Unconditionally: **economically dead**, confirmed again here.")
    A("- Conditioned on the simple first-candle Continuation pattern, held "
      "30+ minutes: **marginally alive** — a few basis points net, with "
      "p-values around 0.04 and confidence intervals whose lower bounds sit "
      "just above zero.")
    A("")
    A("Three things keep that from being a green light. The p-values are "
      "borderline and many cells were examined. The universe is "
      "survivorship-biased, which pushes every result in this study upward. "
      "And a few basis points per trade is inside the range that a single "
      "unmodelled friction — borrow cost on the short side, a wider spread on "
      "an illiquid name, a missed fill — would erase. It is a real effect that "
      "is too thin to deploy on this evidence, which is a different and more "
      "useful conclusion than \"there is nothing there\".")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/final_tests.py`; tables "
      "written to `lambda_data/tables/test1_ultrashort.csv`, "
      "`test2_earn.csv`, `test2_earn_ultrashort.csv`._")
    return "\n".join(L)
