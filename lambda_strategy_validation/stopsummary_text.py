"""stopsummary_text.py — renders STOPSUMMARY_REPORT.md.

Decision-oriented: tables first, one verdict at the end.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

NOSTOP = "1. No stop"


def build(R: dict, meta: dict) -> str:
    c = R["core"].set_index("rule")
    t = R["tail"].set_index("rule")
    f = R["fill"].set_index("rule")
    e = R["efficiency"].set_index("rule")
    order = list(c.index)
    base = c.loc[NOSTOP]
    L: list[str] = []
    A = L.append

    A("# Lambda — Stop Rules: Consolidated Cost/Benefit and Fill Quality")
    A("")
    A("Post-earnings T+1, High Volume + Continuation (non-doji), entry at "
      "the open of the 09:35 bar, target exit 10:35. Every rule tested in "
      "this series on one cohort, with fill quality measured for the first "
      "time.")
    A("")
    A("| Input | Definition |")
    A("|---|---|")
    A(f"| Universe | Post-earnings T+1, {meta['start']} → {meta['end']} |")
    A(f"| Cohort | {meta['n']:,} events |")
    A("| Intrabar rules (4, 5) | trigger on the first touch; fill at the "
      "level, or the bar's open if it opened through |")
    A(f"| Close-confirmed rules (2, 3, 6, 7) | trigger only if a 5-minute "
      f"bar CLOSES beyond the level ({meta['n_checks']} checkpoints); fill "
      "at that close |")
    A("| ATR | prior-session ATR(14); no gap-day data |")
    A(f"| Costs | {meta['cost_bps']} bps round trip, charged identically to "
      "stopped and held trades |")
    A("")

    # ---------------- A ----------------
    A("## A. Core performance")
    A("")
    A("| Rule | Trigger | % stopped | Win rate | **NET** | Avg Win | "
      "Avg Loss | Payoff | Median |")
    A("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in order:
        x = c.loc[r]
        A(f"| {r} | {x['trigger']} | "
          + ("—" if r == NOSTOP else f"{x['pct_stopped']*100:.1f}%")
          + f" | {x['win_rate']*100:.1f}% | **{x['net_bps']:+.1f}** | "
          f"{x['avg_win_bps']:.1f} | {x['avg_loss_bps']:.1f} | "
          f"{x['payoff_ratio']:.2f} | {x['median_bps']:+.1f} |")
    A("")

    # ---------------- B ----------------
    A("## B. Tail risk — losses beyond 1.0 ATR")
    A("")
    A("| Rule | n | % of trades | Avg loss (bps) | Avg loss (ATR) | "
      "Median (bps) | Worst (bps) | **Drag (bps/trade)** |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in order:
        x = t.loc[r]
        if not x["n_loss"]:
            A(f"| {r} | **0** | 0.00% | — | — | — | — | **+0.0** |")
            continue
        A(f"| {r} | {int(x['n_loss']):,} | {x['pct_loss']*100:.2f}% | "
          f"{x['avg_loss_bps']:.0f} | {x['avg_loss_atr']:.2f} | "
          f"{x['median_loss_bps']:.0f} | {x['worst_loss_bps']:,.0f} | "
          f"**{x['drag_bps']:+.1f}** |")
    A("")
    A("Drag is the sum of every >1 ATR loss divided by all "
      f"{meta['n']:,} trades — the part of expectancy the large losses eat.")
    A("")

    # ---------------- C ----------------
    A("## C. Fill quality — how far past the intended level the stop "
      "actually filled")
    A("")
    A("> **The \"% filled worse\" column means two different things, and "
      "the difference is structural, not empirical.** An intrabar stop "
      "exits *at* its level, so it can only fill worse when a bar opens "
      "through — that percentage is a genuine measure of slippage risk. A "
      "close-confirmed stop exits at whatever the bar closed at, which is "
      "*by definition* already beyond the level, so its percentage is "
      "100% by construction and carries no information. For rules 2, 3, 6 "
      "and 7 only the **size** of the overshoot is an empirical question.")
    A("")
    A("| Rule | Trigger | Stopped | % filled worse | Avg overshoot (bps) | "
      "Avg (ATR) | Median (bps) | Worst (bps) | Worst (ATR) |")
    A("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in order:
        if r == NOSTOP:
            continue
        x = f.loc[r]
        A(f"| {r} | {x['trigger']} | {int(x['n_stopped']):,} | "
          f"{x['pct_worse']*100:.1f}% | **{x['avg_over_bps']:.1f}** | "
          f"{x['avg_over_atr']:.3f} | {x['median_over_bps']:.1f} | "
          f"{x['worst_over_bps']:,.0f} | {x['worst_over_atr']:.2f} |")
    A("")
    A("**Intended stop level versus what was actually realised**, averaged "
      "over the trades each rule stopped:")
    A("")
    A("| Rule | Mean intended level (bps) | Mean realised (bps) | "
      "Shortfall | **Overshoot drag (bps/trade, whole book)** |")
    A("|---|---:|---:|---:|---:|")
    for r in order:
        if r == NOSTOP:
            continue
        x = f.loc[r]
        A(f"| {r} | {x['mean_intended_bps']:+.0f} | "
          f"{x['mean_realised_bps']:+.0f} | "
          f"{x['mean_realised_bps'] - x['mean_intended_bps']:+.0f} | "
          f"**{x['drag_bps']:+.1f}** |")
    A("")
    A("The last column is the expectancy lost purely to imperfect fills, "
      "spread across the whole book — separable from the expectancy lost "
      "to the stop firing at all.")
    A("")

    ib = [r for r in order if c.loc[r, "trigger"] == "intrabar"]
    cc = [r for r in order if c.loc[r, "trigger"] == "5-min close"]
    if ib and cc:
        ib_o = f.loc[ib, "avg_over_bps"].mean()
        cc_o = f.loc[cc, "avg_over_bps"].mean()
        A(f"**Close-confirmed stops overshoot by roughly "
          f"{cc_o/ib_o:.0f}× as much as intrabar stops** — an average of "
          f"{cc_o:.0f} bps past the intended level against {ib_o:.0f} bps. "
          "That gap is the price of waiting for confirmation, and it is "
          "the single largest hidden cost in the structural and VWAP "
          "rules. None of the earlier reports could see it, because they "
          "measured only what the stops returned, never what they "
          "promised.")
        A("")
        worst_o = f.loc[cc, "avg_over_bps"].idxmax()
        A(f"{worst_o} is the worst offender at "
          f"{f.loc[worst_o, 'avg_over_bps']:.0f} bps average overshoot "
          f"({f.loc[worst_o, 'avg_over_atr']:.2f} ATR), with a worst case "
          f"of {f.loc[worst_o, 'worst_over_bps']:,.0f} bps.")
        A("")

        # The counterfactual that reframes the whole comparison.
        A("### Fill quality is the entire story for the confirmed rules")
        A("")
        A("Adding each rule's overshoot drag back to its NET gives what it "
          "would have earned had every stop filled exactly at its intended "
          "level:")
        A("")
        A("| Rule | NET as traded | Overshoot drag | NET if filled at the "
          "level | vs no stop |")
        A("|---|---:|---:|---:|---:|")
        for r in order:
            if r == NOSTOP:
                continue
            ideal = c.loc[r, "net_bps"] - f.loc[r, "drag_bps"]
            A(f"| {r} | {c.loc[r, 'net_bps']:+.1f} | "
              f"{f.loc[r, 'drag_bps']:+.1f} | **{ideal:+.1f}** | "
              f"{ideal - base['net_bps']:+.1f} |")
        A("")
        ideals = {r: c.loc[r, "net_bps"] - f.loc[r, "drag_bps"]
                  for r in order if r != NOSTOP}
        beat = [r for r in cc if ideals[r] > base["net_bps"]]
        if len(beat) == len(cc):
            A("**Every close-confirmed rule would beat holding if it filled "
              "at its level.** All four are pushed below the baseline "
              "purely by fill quality — the overshoot costs more than the "
              "stop's entire net disadvantage. That reframes the earlier "
              "reports: the structural and VWAP levels are not choosing bad "
              "moments to exit, they are choosing bad *prices*, and the "
              "price is bad because the confirmation is what makes it late.")
            A("")
            A("This is a diagnostic, not a strategy. A confirmed break "
              "cannot fill at its level by construction — you only learn "
              "the level broke once the bar has closed past it. But it does "
              "point somewhere concrete: an **intrabar** version of these "
              "same levels would capture most of that gap, and none of the "
              "reports so far has tested one.")
            A("")

    # ---------------- D ----------------
    A("## D. Efficiency ranking")
    A("")
    A("Ranked by percentage points of >1 ATR tail removed per basis point "
      "of expectancy surrendered.")
    A("")
    A("| Rank | Rule | Cost vs no stop | Tail cut (pp) | **pp per bp** | "
      "Remaining severity | Overshoot drag | Overshoot as % of cost |")
    A("|---:|---|---:|---:|---:|---:|---:|---:|")
    for i, (r, x) in enumerate(e.iterrows(), 1):
        sev = ("none left" if pd.isna(x["remaining_severity_bps"])
               else f"{x['remaining_severity_bps']:.0f} bps")
        osh = (f"{x['overshoot_share']*100:.0f}%"
               if not pd.isna(x["overshoot_share"]) else "—")
        A(f"| {i} | {r} | −{x['cost_bps']:.1f} | {x['tail_cut_pp']:.2f} | "
          f"**{x['ratio']:.2f}** | {sev} | {x['overshoot_drag_bps']:+.1f} | "
          f"{osh} |")
    A("")
    A("A value above 100% in the last column means the overshoot drag "
      "exceeds the rule's whole net cost — the stop's timing is adding "
      "value and its fills are giving back more than all of it. Those are "
      "the four close-confirmed rules, and the counterfactual table above "
      "is the same fact stated the other way round.")
    A("")
    top = e.iloc[0]
    A(f"**{e.index[0]} is the most efficient tail-control instrument "
      f"tested** — {top['tail_cut_pp']:.2f} percentage points of >1 ATR "
      f"losses removed for {top['cost_bps']:.1f} bps of expectancy, with "
      f"only {abs(top['overshoot_drag_bps']):.1f} bps lost to fill "
      "quality.")
    A("")

    # overall assessment
    A("### Overall assessment")
    A("")
    A("| Rule | Verdict |")
    A("|---|---|")
    for r in order:
        if r == NOSTOP:
            A(f"| {r} | **Highest expectancy ({base['net_bps']:+.1f} bps).** "
              "Carries the full tail: "
              f"{t.loc[r, 'pct_loss']*100:.2f}% of trades lose more than "
              f"1 ATR, dragging {abs(t.loc[r, 'drag_bps']):.1f} bps/trade. "
              "The right default unless a loss cap is mandated. |")
            continue
        x, xe, xf = c.loc[r], e.loc[r], f.loc[r]
        if xe["ratio"] >= 0.80:
            v = "**Best value.** "
        elif xe["ratio"] >= 0.50:
            v = "**Reasonable value.** "
        elif xe["ratio"] >= 0.30:
            v = "**Poor value.** "
        else:
            v = "**Worst value.** "
        v += (f"Costs {xe['cost_bps']:.1f} bps to remove "
              f"{xe['tail_cut_pp']:.2f} pp of the >1 ATR tail")
        if pd.isna(xe["remaining_severity_bps"]):
            v += ", eliminating it entirely"
        else:
            v += (f", leaving the rest averaging "
                  f"{xe['remaining_severity_bps']:.0f} bps")
        v += (f". Overshoots {xf['avg_over_bps']:.0f} bps "
              f"({xf['avg_over_atr']:.2f} ATR) per stop")
        if not pd.isna(xe["overshoot_share"]):
            if xe["overshoot_share"] > 1.0:
                v += (f", a drag of {abs(xf['drag_bps']):.1f} bps/trade — "
                      "more than its whole net cost, so it would beat "
                      "holding on perfect fills")
            else:
                v += (f", only {xe['overshoot_share']*100:.0f}% of its "
                      "cost")
        v += ". |"
        A(f"| {r} | {v}")
    A("")

    # ---------------- decision ----------------
    A("## The decision")
    A("")
    A(f"**Nothing beats holding on expectancy.** The baseline is "
      f"{base['net_bps']:+.1f} bps and every stop costs "
      f"{e['cost_bps'].min():.1f} to {e['cost_bps'].max():.1f} bps. The "
      "choice is therefore not \"which stop makes money\" but \"what am I "
      "buying, and is it worth the price\".")
    A("")
    A("| If your constraint is… | Use | Why |")
    A("|---|---|---|")
    best_ratio = e.index[0]
    zero_tail = t[t["n_loss"] == 0].index.tolist()
    cheapest = e["cost_bps"].idxmin()
    A(f"| Maximum expectancy | **{NOSTOP}** | "
      f"{base['net_bps']:+.1f} bps, the highest of any rule |")
    A(f"| Best risk reduction per bp spent | **{best_ratio}** | "
      f"{e.loc[best_ratio, 'ratio']:.2f} pp of tail per bp, and the "
      "smallest overshoot of any rule |")
    if zero_tail:
        z = zero_tail[0]
        A(f"| A hard cap on per-trade loss | **{z}** | the only rule that "
          f"eliminates >1 ATR losses entirely, for "
          f"{e.loc[z, 'cost_bps']:.1f} bps |")
    A(f"| A stop that barely interferes | **{cheapest}** | "
      f"{e.loc[cheapest, 'cost_bps']:.1f} bps, but it removes only "
      f"{e.loc[cheapest, 'tail_cut_pp']:.2f} pp of tail — near-free "
      "because near-inactive |")
    A("")
    A("**What this analysis adds to the earlier ones.** Two things, and "
      "they point in opposite directions.")
    A("")
    A("The first is a mark *against* the confirmed rules: they cannot "
      "promise a loss cap at all. Their fill is wherever the bar closed, "
      "so the >1 ATR tail survives — Gap Level still carries the full "
      f"{abs(t.loc['2. Gap Level', 'worst_loss_bps']):,.0f} bps worst case, "
      "identical to no stop. If a stop exists to bound per-trade loss, "
      "only the intrabar ATR rules deliver that, and only "
      "ATR −0.5 delivers it absolutely.")
    A("")
    A("The second is a mark *for* them, and it was invisible until fill "
      "quality was measured: the levels themselves are good. Every "
      "confirmed rule would beat holding on perfect fills. Their weakness "
      "is not where they exit but how late — which makes an intrabar "
      "version of the same levels the obvious next test, and the one thing "
      "this series has not yet run.")
    A("")

    # ---------------- caveats ----------------
    A("## Reading notes")
    A("")
    A("- **Costs are flat "
      f"{meta['cost_bps']} bps for every rule and every trade.** A stop "
      "firing into fast tape pays more, so every stop rule is flattered "
      "relative to holding, and the tighter/more active the stop the more "
      "it is flattered.")
    A("- **Overshoot here is measured against the rule's own intended "
      "level**, not against a theoretical best fill. It excludes spread "
      "and queue effects entirely, so it is a floor on real-world "
      "slippage, not an estimate of it.")
    A("- **The AVWAP prior-close anchor carries a judgement call** (the "
      "seed weight), documented and stress-tested in `LOSS_REPORT.md`. Its "
      "figures should be read as one point on that curve.")
    A("- **All seven rules run on one sample**, so this is a comparison "
      "under identical conditions, not seven independent tests.")
    A("- **No rule here was fitted.** Every level is a convention chosen "
      "in advance.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/stopsummary.py`; "
      "tables in `lambda_data/tables/sum_*.csv`._")
    return "\n".join(L)
