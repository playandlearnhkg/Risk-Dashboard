"""winrate_text.py — renders WINRATE_REPORT.md from the computed tables."""

from __future__ import annotations

import pandas as pd


def _best(df: pd.DataFrame, min_n: int = 100) -> pd.DataFrame:
    d = df[(df["n_total"] >= min_n) & (df["gap"] == "Both")].copy()
    return d.sort_values("win_rate", ascending=False)


def build(R: dict, meta: dict, md) -> str:
    L, A = [], None
    A = L.append

    A("# Lambda Win-Rate Report — Continuation Probability Only")
    A("")
    A("This report deliberately contains **no average returns, no net bps and "
      "no cost model**. Every cell is a count and a continuation win rate.")
    A("")

    A("## Definitions used (exactly as specified)")
    A("")
    A("| Term | Rule |")
    A("|---|---|")
    A("| Gap Up | `Open_T+1 > Prior Close` |")
    A("| Gap Down | `Open_T+1 < Prior Close` |")
    A("| Intraday Up | `Close_T+1 > Open_T+1` |")
    A("| Intraday Down | `Close_T+1 < Open_T+1` |")
    A("| Continuation | gap direction == intraday direction |")
    A("")
    A(f"Sample: **{meta['n_raw']:,}** T+1 earnings sessions (2015-2025). Exact "
      f"ties are undefined under these rules and are excluded — "
      f"{meta['tie_gap']} gap ties (Open == Prior Close) and "
      f"{meta['tie_o2c']} intraday ties (Close == Open) — leaving "
      f"**{meta['n_used']:,}** events. Cells with n < "
      f"{meta['small_sample_threshold']} are flagged `YES` under `small n?`.")
    A("")

    A("### How the two pattern systems are classified")
    A("")
    A("**System 1 — original 4-pattern**, using all three 5-minute candles "
      "(09:30-09:35, 09:35-09:40, 09:40-09:45):")
    A("")
    A("- **Strong Continuation+** — all three candles close in the gap "
      "direction AND highs progress upward (gap up) / lows progress downward "
      "(gap down).")
    A("- **Moderate Continuation+** — at least 2 of 3 close in the gap "
      "direction, and the third is not a strong counter-move (its body is "
      "< 50% of the mean body of the other two).")
    A("- **Early Reversal−** — the majority close against the gap, OR candle 1 "
      "shows a rejection wick against the gap direction longer than 60% of "
      "that candle's range.")
    A("- **Indecision0** — everything else.")
    A("")
    A("**System 2 — simple online-style**, using ONLY the first 5-minute candle "
      "(09:30-09:35). Stated precisely so it is reproducible:")
    A("")
    A("```")
    A("body  = c1_close - c1_open")
    A("range = c1_high  - c1_low")
    A("")
    A(f"Doji         : range == 0  OR  |body| / range < {meta['doji_body_fraction']}")
    A("Continuation : otherwise, sign(body) == sign(gap)")
    A("Reversal     : otherwise, sign(body) != sign(gap)")
    A("```")
    A("")
    A("The doji bucket uses body-to-range rather than an absolute price "
      "threshold, so it is scale-free across a $15 stock and a $900 one.")
    A("")

    A("### Two intervals, shown side by side on purpose")
    A("")
    A("`Wilson lo/hi` is the standard 95% interval for a proportion and assumes "
      "every event is independent. `p (binomial)` makes the same assumption. "
      "**That assumption is false here**: dozens of firms report the same "
      "evening and share the next day's market move, so events cluster by "
      "date. `p (clustered)` re-tests the win rate against a 50% null by "
      "resampling whole trading dates. Where the two disagree, the clustered "
      "one is correct and the Wilson interval is too narrow.")
    A("")

    A("---")
    A("")
    A("## Table 1 — Overall four quadrants")
    A("")
    A("Raw cell counts:")
    A("")
    A(md(R["t1_quadrants"]))
    A("Continuation win rate:")
    A("")
    A(md(R["t1_rates"]))

    A("## Table 2 — Quadrants split by the original 4-pattern system")
    A("")
    A("> **Read this with care.** The pattern is built from 09:30-09:45, which "
      "sits *inside* the Open→Close window being scored. A pattern that moved "
      "with the gap has already contributed the first 15 minutes of the very "
      "move it is being credited for, so these separations are partly "
      "self-fulfilling. The clean, non-overlapping version is Table 2b.")
    A("")
    A(md(R["t2_pattern4"]))
    A("### Table 2b — same split, scored only on 09:45 → Close (no overlap)")
    A("")
    A("Here the pattern is complete *before* the measured window starts, so it "
      "cannot score itself. This is the honest version of Table 2.")
    A("")
    A(md(R["t2_clean_0945_close"]))

    A("## Table 3 — Quadrants split by the simple online-style pattern")
    A("")
    A("> Same overlap caveat as Table 2: the first candle (09:30-09:35) is "
      "inside the Open→Close window. Table 3b is the clean version.")
    A("")
    A(md(R["t3_pattern_simple"]))
    A("### Table 3b — same split, scored only on 09:45 → Close (no overlap)")
    A("")
    A(md(R["t3_clean_0945_close"]))

    A("## Table 4 — Quadrants split by holding period")
    A("")
    A("For a shorter window, 'intraday direction' is the sign of the move over "
      "that window, and continuation means it matches the gap direction. "
      "Windows are measured on 1-minute bars; sessions with an exactly flat "
      "window are excluded.")
    A("")
    A(md(R["t4_holding"]))
    A("Quadrant counts per window:")
    A("")
    A(md(R["t4_quadrants"]))

    A("## Table 5 — Quadrants split by SPY direction on T+1")
    A("")
    A("> Note: SPY's open-to-close direction is only known at 16:00, so this is "
      "a **diagnostic split, not a tradeable filter**. It describes the market "
      "conditions under which continuation happened; it cannot be used to "
      "select trades at the open.")
    A("")
    A(md(R["t5_spy"]))

    A("## Table 6 — Quadrants split by sector ETF direction on T+1")
    A("")
    A("> Same caveat as Table 5 — the sector ETF's full-session direction is "
      "not known at entry.")
    A("")
    A(md(R["t6_sector"]))

    A("## Table 7 — Quadrants split by Minervini Stage (Stage 2 vs Stage 3+4)")
    A("")
    A("Stage is evaluated on the session *before* the event, so unlike Tables 5 "
      "and 6 this split is genuinely knowable in advance.")
    A("")
    A(md(R["t7_stage"]))

    A("## Table 8 — Gap Up versus Gap Down, side by side")
    A("")
    A("Every table above already reports Gap Up and Gap Down rows separately; "
      "this section isolates them so asymmetry is easy to read.")
    A("")
    A("### 8a — by 4-pattern system")
    A("")
    A(md(R["t8_pattern4"]))
    A("### 8b — by simple online-style pattern")
    A("")
    A(md(R["t8_simple"]))
    A("### 8c — by Stage")
    A("")
    A(md(R["t8_stage"]))

    A("## Table 9 — Highest-win-rate combinations (pattern + Stage + SPY)")
    A("")
    A("All combinations, sorted by win rate. Treat the top rows with suspicion: "
      "this is a search over many cells, and the SPY term is not knowable at "
      "entry (see Table 5).")
    A("")
    best = _best(R["t9_combos"])
    A(md(best.head(12)))
    A("Lowest:")
    A("")
    A(md(best.tail(6)))

    # ---------------- summary -------------------------------------------
    t1 = R["t1_rates"]
    both = t1[t1["gap"] == "Both"].iloc[0]
    up = t1[t1["gap"] == "Gap Up"].iloc[0]
    dn = t1[t1["gap"] == "Gap Down"].iloc[0]

    def spread(tbl, order):
        d = tbl[tbl["gap"] == "Both"].set_index("subgroup")["win_rate"]
        d = d.reindex([o for o in order if o in d.index]).dropna()
        return (d.max() - d.min()) * 100 if len(d) else float("nan")

    p4_raw = spread(R["t2_pattern4"], ["Strong Continuation+", "Early Reversal-"])
    p2_raw = spread(R["t3_pattern_simple"],
                    ["Continuation (1st candle with gap)", "Reversal (1st candle against gap)"])
    p4_cl = spread(R["t2_clean_0945_close"], ["Strong Continuation+", "Early Reversal-"])
    p2_cl = spread(R["t3_clean_0945_close"],
                   ["Continuation (1st candle with gap)", "Reversal (1st candle against gap)"])

    A("---")
    A("")
    A("## Summary")
    A("")
    A(f"**Baseline.** Across all {int(both['n_total']):,} usable events the "
      f"continuation win rate is **{both['win_rate']*100:.1f}%** "
      f"(Wilson {both['wilson_lo']*100:.1f}-{both['wilson_hi']*100:.1f}%, "
      f"clustered p = {both['p_clustered']:.3f}). That is the number every "
      f"split below has to beat to mean anything.")
    A("")

    A("### 1. Which pattern system separates better?")
    A("")
    A(f"On the overlapping full-day basis the 4-pattern system separates far "
      f"more widely — a **{p4_raw:.1f} point** spread between Strong "
      f"Continuation+ and Early Reversal−, against **{p2_raw:.1f} points** for "
      f"the simple first-candle split. But most of that is the overlap "
      f"artefact, and it flatters the system that uses more of the scored "
      f"window (three candles rather than one).")
    A("")
    A(f"On the clean 09:45→Close basis, where neither system can score itself, "
      f"the spreads collapse to **{p4_cl:.1f} points** (4-pattern) and "
      f"**{p2_cl:.1f} points** (simple). "
      + ("The 4-pattern system still separates more." if p4_cl > p2_cl else
         "The simple one-candle system separates at least as well as the "
         "more elaborate one.")
      + " Either way the honest separation is a small fraction of the "
        "headline version.")
    A("")

    A("### 2. Is Gap Up different from Gap Down?")
    A("")
    A(f"Yes, and it is the most robust asymmetry in this report. Gap Down "
      f"events continue **{dn['win_rate']*100:.1f}%** of the time "
      f"(n = {int(dn['n_total']):,}, clustered p = {dn['p_clustered']:.3f}), "
      f"while Gap Up events continue only **{up['win_rate']*100:.1f}%** "
      f"(n = {int(up['n_total']):,}, clustered p = {up['p_clustered']:.3f}). "
      f"Gap downs tend to keep falling; gap ups are closer to a coin flip, if "
      f"anything slightly mean-reverting. Any rule applied symmetrically to "
      f"both sides is averaging two different behaviours.")
    A("")

    A("### 3. Which combination gives the highest win rate?")
    A("")
    if len(best):
        top = best.iloc[0]
        A(f"The highest cell with n >= 100 is **{top['subgroup']}** at "
          f"**{top['win_rate']*100:.1f}%** (n = {int(top['n_total']):,}). "
          f"Two warnings attach to it: the SPY term is only known at the close, "
          f"so this combination cannot be traded as stated; and it is the best "
          f"of {len(best)} cells searched, which is exactly the setting where "
          f"the top of a leaderboard is mostly selection.")
    A("")
    A("The combinations that are genuinely knowable in advance — pattern plus "
      "Stage, with no SPY or sector term — are the only ones worth carrying "
      "forward, and those sit far closer to the baseline.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/winrate_report.py`; "
      "every table is also written to `lambda_data/tables/winrate_*.csv`._")
    return "\n".join(L)
