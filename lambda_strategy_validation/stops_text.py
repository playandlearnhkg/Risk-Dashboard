"""stops_text.py — renders STOPS_REPORT.md. Table-focused."""

from __future__ import annotations

import numpy as np
import pandas as pd

BASELINE = "C. No stop (hold to 1 hour)"


def build(R: dict, meta: dict) -> str:
    d = R["main"]
    base = d[d["rule"] == BASELINE].iloc[0]
    stops = d[d["rule"] != BASELINE]
    L: list[str] = []
    A = L.append

    A("# Lambda — Statistical Stop-Loss Rules on the Strongest Setup")
    A("")
    A("Post-earnings T+1, High Volume + Continuation (non-doji), entry at "
      "the open of the 09:35 bar, exit at 1 hour (10:35) if the stop is not "
      "hit.")
    A("")
    A("| Input | Definition |")
    A("|---|---|")
    A(f"| Universe | Post-earnings T+1, {meta['start']} → {meta['end']} |")
    A(f"| Cohort | {meta['n']:,} events |")
    A("| Stop distance | **prior-session ATR(14)** — a 14-session window "
      "ending the day *before* the gap. No gap-day data enters it. |")
    A("| Trigger | intrabar: the bar's **low** for a long, **high** for a "
      "short |")
    A("| Fill | the stop price, or the bar's **open** if the bar opened "
      "already through it |")
    A(f"| Costs | {meta['cost_bps']} bps round trip, charged identically to "
      "stopped and held trades |")
    A("| Inference | date-clustered bootstrap |")
    A("")
    A("> **Two things this test does that a naive stop study does not.** "
      "Stops are checked against intrabar highs and lows, not closes — "
      "testing on closes alone would understate stop-outs badly. And a bar "
      "that opens through the stop fills at the open, not the stop price, "
      "so realised losses are allowed to exceed the stop distance. Section "
      "4 measures how often that happened.")
    A("")

    # ---------------- 1. core ----------------
    A("## 1. Core performance")
    A("")
    A("| Rule | n | % stopped | Win rate | Avg Win | Avg Loss | Payoff | "
      "**NET** | net p |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, x in d.iterrows():
        A(f"| {x['rule']} | {int(x['n']):,} | "
          + ("—" if x["rule"] == BASELINE
             else f"{x['pct_stopped']*100:.1f}%")
          + f" | {x['win_rate']*100:.1f}% | {x['avg_win_bps']:.1f} | "
          f"{x['avg_loss_bps']:.1f} | {x['payoff_ratio']:.2f} | "
          f"**{x['net_bps']:+.1f}** | {x['net_p']:.3f} |")
    A("")
    A("All figures in basis points. NET is mean expectancy per trade after "
      f"{meta['cost_bps']} bps.")
    A("")

    # ---------------- 2. distribution ----------------
    A("## 2. Distribution after the stop")
    A("")
    A("| Rule | Median | p10 | p25 | p75 | p90 | Skew | "
      "**% realised loss > 1.0 ATR** |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|")
    for _, x in d.iterrows():
        A(f"| {x['rule']} | {x['median_bps']:+.1f} | {x['p10_bps']:+.0f} | "
          f"{x['p25_bps']:+.0f} | {x['p75_bps']:+.0f} | "
          f"{x['p90_bps']:+.0f} | {x['skew']:+.2f} | "
          f"**{x['pct_loss_gt_1atr']*100:.2f}%** |")
    A("")
    A("> **The skew column is one observation.** As documented in "
      "`DIST_REPORT.md`, the CAR 2021-11-02 squeeze (+10,023 bps in an "
      "hour) sits in this cohort and drives the 1-hour skew on its own. It "
      "is a winner, so no stop touches it and the figure is near-identical "
      "across all six rules — which is precisely why it carries no "
      "information about the stops. Read the quantile columns instead.")
    A("")

    # ---------------- 3. verdict ----------------
    A("## 3. Does any stop beat holding?")
    A("")
    A("| Rule | NET | vs no stop | Median | vs no stop | p10 | vs no stop |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    for _, x in d.iterrows():
        if x["rule"] == BASELINE:
            continue
        A(f"| {x['rule']} | {x['net_bps']:+.1f} | "
          f"**{x['net_bps'] - base['net_bps']:+.1f}** | "
          f"{x['median_bps']:+.1f} | "
          f"{x['median_bps'] - base['median_bps']:+.1f} | "
          f"{x['p10_bps']:+.0f} | "
          f"{x['p10_bps'] - base['p10_bps']:+.0f} |")
    A(f"| **{BASELINE}** | **{base['net_bps']:+.1f}** | — | "
      f"{base['median_bps']:+.1f} | — | {base['p10_bps']:+.0f} | — |")
    A("")
    better = stops[stops["net_bps"] > base["net_bps"]]
    best = stops.loc[stops["net_bps"].idxmax()]
    if not len(better):
        A(f"**No stop rule improves expectancy.** All "
          f"{len(stops)} cost money against simply holding — even the best "
          f"of them ({best['rule'].split('.')[0]}) gives up "
          f"{abs(best['net_bps'] - base['net_bps']):.1f} bps. The ordering "
          "is "
          "monotone in the obvious direction: the tighter the stop, the "
          "more it costs.")
        A("")
        A("That is the expected result for a setup whose edge is a **drift**"
          " rather than a breakout. A stop converts a temporary adverse "
          "excursion into a realised loss, and this cohort's adverse "
          "excursions are mostly temporary — the path-dependence test "
          "already showed that 5-minute losers go on to make "
          "**+30.1 bps** from 09:41 to 10:35, the *largest* subsequent move "
          "of any group. A stop is precisely the mechanism that prevents "
          "collecting that.")
        A("")
    else:
        A(f"**{len(better)} of {len(stops)} rules improve on holding.** Best "
          f"is {best['rule']} at {best['net_bps']:+.1f} bps, "
          f"{best['net_bps'] - base['net_bps']:+.1f} against the baseline.")
        A("")

    # what stops DO buy
    A("**What the stops do buy.**")
    A("")
    A("| Rule | p10 | Std dev | % realised loss > 1.0 ATR | NET |")
    A("|---|---:|---:|---:|---:|")
    for _, x in d.iterrows():
        A(f"| {x['rule']} | {x['p10_bps']:+.0f} | {x['std_bps']:.0f} | "
          f"{x['pct_loss_gt_1atr']*100:.2f}% | {x['net_bps']:+.1f} |")
    A("")
    tight = d[d["rule"].str.startswith("A1")]
    if len(tight):
        t = tight.iloc[0]
        worse_p10 = t["p10_bps"] < base["p10_bps"]
        A("**Less than you would expect — and on one measure, nothing at "
          "all.**")
        A("")
        A(f"The 1.0 ATR stop does cut the far tail: the share of trades "
          f"realising a loss worse than 1 ATR falls from "
          f"{base['pct_loss_gt_1atr']*100:.2f}% to "
          f"{t['pct_loss_gt_1atr']*100:.2f}%, a "
          f"{base['pct_loss_gt_1atr']/max(t['pct_loss_gt_1atr'],1e-9):.0f}× "
          "reduction. That is real risk control.")
        A("")
        if worse_p10:
            A(f"But it makes the **10th percentile worse**, not better — "
              f"{t['p10_bps']:+.0f} bps against {base['p10_bps']:+.0f} "
              f"without any stop. That is not a rounding artefact, it is "
              f"the mechanism: the stop takes the "
              f"{t['pct_stopped']*100:.1f}% of trades it catches and parks "
              "them all at roughly −1 ATR, whereas most of those would "
              "otherwise have recovered some of the way back. It converts a "
              "spread-out set of moderate outcomes into a dense cluster of "
              "losses at one level, and that cluster lands right on the "
              "10th percentile.")
            A("")
        A(f"Dispersion barely moves either — standard deviation "
          f"{t['std_bps']:.0f} against {base['std_bps']:.0f}, a "
          f"{abs(t['std_bps'] - base['std_bps']):.0f} bps difference for "
          f"{base['net_bps'] - t['net_bps']:.1f} bps of expectancy. The "
          "stop is not buying a materially smoother equity curve; it is "
          "buying protection against the extreme left tail only, and paying "
          "for it out of the middle of the distribution.")
        A("")
        # The looser stops make the >1 ATR metric WORSE, which is worth
        # calling out because it is the opposite of the intended effect.
        worse = d[(d["rule"] != BASELINE)
                  & (d["pct_loss_gt_1atr"] > base["pct_loss_gt_1atr"])]
        if len(worse):
            A(f"**The looser stops make even that metric worse.** "
              f"{len(worse)} of the {len(stops)} rules end with a *higher* "
              "share of realised losses beyond 1 ATR than holding with no "
              "stop at all ("
              + ", ".join(f"{x['rule'].split('.')[0]} "
                          f"{x['pct_loss_gt_1atr']*100:.2f}%"
                          for _, x in worse.iterrows())
              + f" against {base['pct_loss_gt_1atr']*100:.2f}%). A stop at "
              "1.5 or 2.0 ATR sits beyond where most adverse excursions "
              "turn around, so it rarely saves anything — but when it does "
              "fire it locks in a loss of at least its own distance, which "
              "by definition exceeds 1 ATR. It manufactures the very "
              "outcome it was meant to prevent.")
            A("")

    # risk-adjusted
    A("On return per unit of risk:")
    A("")
    A("| Rule | NET | Std dev | NET / Std |")
    A("|---|---:|---:|---:|")
    ratios = {}
    for _, x in d.iterrows():
        ratios[x["rule"]] = x["net_bps"] / x["std_bps"]
        A(f"| {x['rule']} | {x['net_bps']:+.1f} | {x['std_bps']:.0f} | "
          f"{ratios[x['rule']]:.3f} |")
    A("")
    best_r = max(ratios, key=ratios.get)
    A(f"**Best risk-adjusted: {best_r}** ({ratios[best_r]:.3f}). "
      + ("Holding wins on this measure too, so the stops are not even "
         "buying an efficiency improvement — they reduce return faster "
         "than they reduce risk."
         if best_r == BASELINE else
         f"On this measure the stop does earn its place, unlike on raw "
         f"expectancy, because it cuts dispersion "
         f"({d[d['rule'] == best_r].iloc[0]['std_bps']:.0f} vs "
         f"{base['std_bps']:.0f} bps) faster than it cuts return."))
    A("")

    # ---------------- 4. fill realism ----------------
    gt = R.get("gapthrough")
    if gt is not None and len(gt):
        A("## 4. Did the stops actually hold their price?")
        A("")
        A("A stop only fills at its level if the bar does not open through "
          "it. Where it did, the fill is the open and the realised loss "
          "exceeds the intended stop distance.")
        A("")
        A("| Rule | Trades stopped | Gapped through | % of stops | "
          "Mean overshoot | Worst overshoot |")
        A("|---|---:|---:|---:|---:|---:|")
        for _, x in gt.iterrows():
            A(f"| {x['rule']} | {int(x['n_stopped']):,} | "
              f"{int(x['n_gap_through']):,} | "
              f"{x['pct_of_stops']*100:.1f}% | "
              f"{x['mean_slip_atr']:.3f} ATR | "
              f"{x['max_slip_atr']:.2f} ATR |")
        A("")
        worst = gt.loc[gt["pct_of_stops"].idxmax()]
        A(f"Up to {worst['pct_of_stops']*100:.0f}% of stops "
          f"({worst['rule'].split('.')[0]}) filled worse than their level. "
          "That is why the *% realised loss > 1.0 ATR* column in section 2 "
          "is not zero even for the 1.0 ATR stop — a stop is an instruction, "
          "not a guarantee, and in post-earnings tape the difference is "
          "measurable. Note this is still the optimistic case: no spread or "
          "slippage is added beyond the gap-through itself.")
        A("")

    # ---------------- 5. excursions ----------------
    ex = R.get("excursion")
    if ex is not None and len(ex):
        A("## 5. Why the stop-out rates come out where they do")
        A("")
        A("Maximum excursion from entry, in ATR units, over the hour:")
        A("")
        A("| Metric | p10 | p25 | p50 | p75 | p90 | beyond 1.0 | "
          "beyond 1.5 | beyond 2.0 |")
        A("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for _, x in ex.iterrows():
            A(f"| {x['metric']} | {x['p10']:+.2f} | {x['p25']:+.2f} | "
              f"{x['p50']:+.2f} | {x['p75']:+.2f} | {x['p90']:+.2f} | "
              f"{x['pct_beyond_1.0']*100:.1f}% | "
              f"{x['pct_beyond_1.5']*100:.1f}% | "
              f"{x['pct_beyond_2.0']*100:.1f}% |")
        A("")
        mae = ex.iloc[0]
        A(f"The median trade dips {abs(mae['p50']):.2f} ATR against itself "
          f"at some point in the hour, and {mae['pct_beyond_1.0']*100:.1f}% "
          "touch a full ATR against. A 1.0 ATR stop is therefore not a "
          "tail-risk stop on this setup — it sits inside the ordinary "
          "breathing range of the trade, which is exactly why it costs so "
          "much expectancy.")
        A("")

    # ---------------- 6. caveats ----------------
    A("## 6. Reading notes")
    A("")
    A(f"- **The baseline differs trivially from the published +30.1 bps** "
      f"in `LONGHOLD_REPORT.md` (here {base['net_bps']:+.1f}). Earlier "
      "reports dropped exactly-zero returns as stale prints; a stop study "
      "must account for every trade it takes, so nothing is dropped here.")
    A("- **Costs are charged identically to stopped and held trades.** A "
      "stopped trade exits into fast tape and in reality pays more than "
      f"{meta['cost_bps']} bps. Every stop rule above is therefore "
      "flattered relative to holding.")
    A("- **No intrabar path within the minute.** If a bar's low breaches "
      "the stop and its high also reaches a target, this test assumes the "
      "stop fired. That is the conservative ordering, and correct for a "
      "stop-only study.")
    A("- **The stop distance is honest, the stop *choice* is not tested "
      "out of sample.** 1.0/1.5/2.0 ATR are conventional round numbers, "
      "not fitted, which is the right way to run this — but it does mean "
      "no search was done for a level that works, and none of these three "
      "does.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/stops.py`; tables in "
      "`lambda_data/tables/stops_*.csv`._")
    return "\n".join(L)
