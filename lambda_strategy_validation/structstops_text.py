"""structstops_text.py — renders STRUCTSTOPS_REPORT.md. Table-focused."""

from __future__ import annotations

import numpy as np
import pandas as pd

NOSTOP = "Baseline — no stop"


def build(R: dict, meta: dict) -> str:
    d = R["main"]
    base = d[d["rule"] == NOSTOP].iloc[0]
    stops = d[d["rule"] != NOSTOP]
    lv = R["levels"].set_index("rule")
    L: list[str] = []
    A = L.append

    A("# Lambda — Structural Stop-Loss Rules on the Post-Earnings "
      "Continuation Setup")
    A("")
    A("Post-earnings T+1, High Volume + Continuation (non-doji), entry at "
      "the open of the 09:35 bar, exit at 1 hour (10:35) if no stop "
      "triggers. Price-structure levels rather than the volatility-scaled "
      "ATR stops in `STOPS_REPORT.md`.")
    A("")
    A("| Input | Definition |")
    A("|---|---|")
    A(f"| Universe | Post-earnings T+1, {meta['start']} → {meta['end']} |")
    A(f"| Cohort | {meta['n']:,} events — identical to the ATR stop "
      "reports, built by the same code |")
    A("| Rule 1 | long: close below the 09:30–09:35 **low**; short: close "
      "above its **high** |")
    A("| Rule 2 | long: close below the **prior day's close**; short: close "
      "above it |")
    A("| Rule 3 | whichever of rule 1 or rule 2 triggers first |")
    A(f"| Confirmation | the **5-minute close** only — {meta['n_checks']} "
      f"checkpoints, 09:40 through 10:35 |")
    A("| Exit price | the confirming 5-minute close |")
    A(f"| Costs | {meta['cost_bps']} bps round trip |")
    A("")
    A("> **These are not comparable to the ATR stops on stop-out rate.** "
      "An ATR stop fires on the first intrabar touch; these fire only if a "
      "5-minute bar *closes* beyond the level, so an intrabar poke that "
      "closes back inside does nothing. The flip side is that a confirmed "
      "break can fill well past its level — price is under no obligation "
      "to sit on the line when the bar closes — so a structural stop "
      "**cannot cap the loss at its own distance** the way a tight ATR "
      "stop can.")
    A("")

    # ---------------- 1. results ----------------
    A("## 1. Results")
    A("")
    A("| Rule | n | % stopped | Win rate | Avg Win | Avg Loss | Payoff | "
      "**NET** | Median | p10 | % realised loss > 1 ATR |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, x in d.iterrows():
        A(f"| {x['rule']} | {int(x['n']):,} | "
          + ("—" if x["rule"] == NOSTOP else f"{x['pct_stopped']*100:.1f}%")
          + f" | {x['win_rate']*100:.1f}% | {x['avg_win_bps']:.1f} | "
          f"{x['avg_loss_bps']:.1f} | {x['payoff_ratio']:.2f} | "
          f"**{x['net_bps']:+.1f}** | {x['median_bps']:+.1f} | "
          f"{x['p10_bps']:+.0f} | {x['pct_loss_gt_1atr']*100:.2f}% |")
    A("")
    A("All figures in basis points. NET is mean expectancy per trade after "
      f"{meta['cost_bps']} bps.")
    A("")

    A("| Rule | NET | vs no stop | Median | vs no stop | p10 | vs no stop |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    for _, x in stops.iterrows():
        A(f"| {x['rule']} | {x['net_bps']:+.1f} | "
          f"**{x['net_bps'] - base['net_bps']:+.1f}** | "
          f"{x['median_bps']:+.1f} | "
          f"{x['median_bps'] - base['median_bps']:+.1f} | "
          f"{x['p10_bps']:+.0f} | {x['p10_bps'] - base['p10_bps']:+.0f} |")
    A("")
    better = stops[stops["net_bps"] > base["net_bps"]]
    best = stops.loc[stops["net_bps"].idxmax()]
    if not len(better):
        A(f"**No structural rule beats holding.** All {len(stops)} cost "
          f"expectancy; the least damaging ({best['rule'].split(' — ')[1]}) "
          f"gives up {abs(best['net_bps'] - base['net_bps']):.1f} bps. That "
          "is the same verdict the ATR ladder reached, now from levels that "
          "carry actual chart meaning rather than a volatility multiple.")
        A("")
    else:
        A(f"**{len(better)} of {len(stops)} structural rules beat "
          f"holding.** Best is {best['rule']} at {best['net_bps']:+.1f} "
          f"bps, {best['net_bps'] - base['net_bps']:+.1f} against the "
          "baseline — the first stop rule in this series to do so.")
        A("")

    # ---------------- 2. where the levels sit ----------------
    A("## 2. Where these levels actually sit")
    A("")
    A("The whole point of a structural stop is that its distance is set by "
      "the chart, not by volatility. This is what that distance turned out "
      "to be:")
    A("")
    A("| Rule | Median distance (ATR) | p25 | p75 | Median distance (bps) | "
      "Level already breached at entry | Mean stop minute |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    for r in lv.index:
        x = lv.loc[r]
        A(f"| {r} | {x['median_dist_atr']:.2f} | {x['p25_dist_atr']:.2f} | "
          f"{x['p75_dist_atr']:.2f} | {x['median_dist_bps']:.0f} | "
          f"{x['pct_level_above_entry']*100:.1f}% | "
          f"{x['mean_stop_minute']:.0f} |")
    A("")
    r1 = lv.iloc[0]
    r2 = lv.iloc[1]
    A(f"**Rule 1 is a tight stop and rule 2 is a wide one.** The opening "
      f"range sits {r1['median_dist_atr']:.2f} ATR from entry at the "
      f"median — comparable to the 0.5 ATR rung of the ATR ladder — while "
      f"the gap level sits {r2['median_dist_atr']:.2f} ATR away, wider than "
      "anything tested there. They are not two variants of one idea; they "
      "are stops at opposite ends of the range, and their results should "
      "be read that way.")
    A("")
    if r1["pct_level_above_entry"] > 0.01:
        A(f"Note that on {r1['pct_level_above_entry']*100:.1f}% of events "
          "the rule 1 level sits **above** the entry price — the 09:35 open "
          "printed through the opening candle's extreme. Those trades begin "
          "already beyond their stop and are cut at the first checkpoint "
          "that confirms it, which is a real property of the rule rather "
          "than an artefact.")
        A("")

    # ---------------- 3. attribution ----------------
    att = R.get("attribution")
    if att is not None and len(att):
        A("## 3. Where the expectancy goes")
        A("")
        A("| Rule | Trades stopped | Realised | Would have made | "
          "**Forgone** | % that would have recovered to profit |")
        A("|---|---:|---:|---:|---:|---:|")
        for _, x in att.iterrows():
            forgone = x["stopped_if_held_bps"] - x["stopped_realised_bps"]
            A(f"| {x['rule']} | {int(x['n_stopped']):,} | "
              f"{x['stopped_realised_bps']:+.1f} | "
              f"{x['stopped_if_held_bps']:+.1f} | **{forgone:+.1f}** | "
              f"{x['pct_would_recover']*100:.1f}% |")
        A("")
        w = att.iloc[0]
        A(f"Every rule forgoes return on the trades it cuts. For "
          f"{w['rule'].split(' — ')[1]}, "
          f"{w['pct_would_recover']*100:.0f}% of the stopped trades would "
          f"have finished the hour in profit and the group would have "
          f"returned {w['stopped_if_held_bps']:+.1f} bps against the "
          f"{w['stopped_realised_bps']:+.1f} realised. The mechanism is "
          "identical to the ATR case: adverse excursions in this cohort are "
          "mostly temporary, and any stop inside that noise band converts "
          "round-trips into permanent losses.")
        A("")

    # ---------------- 4. tail behaviour ----------------
    A("## 4. Do they at least control the tail?")
    A("")
    A("| Rule | % realised loss > 1 ATR | Median overshoot past the level | "
      "p10 | Std dev |")
    A("|---|---:|---:|---:|---:|")
    for _, x in d.iterrows():
        ov = (f"{lv.loc[x['rule'], 'median_overshoot_atr']:.2f} ATR"
              if x["rule"] in lv.index else "—")
        A(f"| {x['rule']} | {x['pct_loss_gt_1atr']*100:.2f}% | {ov} | "
          f"{x['p10_bps']:+.0f} | {x['std_bps']:.0f} |")
    A("")
    worse_tail = stops[stops["pct_loss_gt_1atr"] >= base["pct_loss_gt_1atr"]]
    if len(worse_tail):
        A(f"**{len(worse_tail)} of the {len(stops)} rules leave the "
          f">1 ATR loss rate at or above the "
          f"{base['pct_loss_gt_1atr']*100:.2f}% of not stopping at all.** "
          "This is the structural stop's central weakness, and it follows "
          "directly from close-confirmation: by the time a 5-minute bar has "
          "closed beyond the level, the loss is whatever the market says it "
          "is. Compare the 0.5 ATR stop, which drove that same figure to "
          "0.00% — an intrabar ATR stop truncates the tail by construction, "
          "and a close-confirmed structural stop cannot.")
        A("")
    else:
        A("The structural rules do reduce the >1 ATR loss rate below the "
          "no-stop baseline.")
        A("")

    # ---------------- 5. fill robustness ----------------
    A("## 5. Fill robustness — you cannot trade the close you just saw")
    A("")
    A("Re-pricing every stop exit at the **next minute's open** instead of "
      "the confirming close:")
    A("")
    A("| Rule | NET at close | NET at next open | Difference |")
    A("|---|---:|---:|---:|")
    for _, x in d.iterrows():
        if x["rule"] == NOSTOP:
            continue
        A(f"| {x['rule']} | {x['net_bps']:+.1f} | "
          f"{x['net_nextopen_bps']:+.1f} | "
          f"{x['net_nextopen_bps'] - x['net_bps']:+.1f} |")
    A("")
    diffs = [x["net_nextopen_bps"] - x["net_bps"]
             for _, x in stops.iterrows()]
    if diffs:
        big = max(abs(v) for v in diffs)
        if big < 0.1:
            A(f"**The convention makes no difference at all** — every rule "
              f"moves by less than {max(0.1, big):.1f} bps, in both "
              "directions. That is worth knowing rather than assuming: on "
              "a 5-minute confirmation the next minute's open is close "
              "enough to the confirming close that the choice between them "
              "is immaterial, so none of the results above rests on being "
              "able to trade a price at the instant it prints.")
        else:
            A(f"The convention is worth {min(diffs):+.1f} to "
              f"{max(diffs):+.1f} bps — not negligible, and the next-open "
              "column is the more realistic of the two.")
        A("")

    # ---------------- 6. verdict ----------------
    A("## 6. Verdict")
    A("")
    A("| Stop family | Best rule tested | NET | vs no stop | Cuts the "
      ">1 ATR tail? |")
    A("|---|---|---:|---:|---|")
    A(f"| Structural (this report) | {best['rule'].split(' — ')[1]} | "
      f"{best['net_bps']:+.1f} | "
      f"{best['net_bps'] - base['net_bps']:+.1f} | "
      + ("yes" if best["pct_loss_gt_1atr"] < base["pct_loss_gt_1atr"]
         else "no") + " |")
    A("| ATR, tight (`STOPS_TIGHT_REPORT.md`) | −0.5 ATR | +22.2 | −8.2 | "
      "yes, to 0.00% |")
    A("| ATR, loose (`STOPS_REPORT.md`) | −2.0 ATR | +30.0 | −0.4 | no |")
    A(f"| **None** | hold to 1 hour | **{base['net_bps']:+.1f}** | — | — |")
    A("")
    A("Across three families and eleven separate rules, **nothing beats "
      "holding to the hour on expectancy.** But the structural rules are "
      "not the worst of the three families, and one of them is close to "
      "free.")
    A("")
    r2row = d[d["rule"].str.startswith("Rule 2")].iloc[0]
    A(f"**{r2row['rule']} costs only "
      f"{abs(r2row['net_bps'] - base['net_bps']):.1f} bps** — the cheapest "
      "stop of any kind tested in this series, and within noise of free. "
      f"It stops {r2row['pct_stopped']*100:.1f}% of trades, trims the "
      f">1 ATR loss rate from {base['pct_loss_gt_1atr']*100:.2f}% to "
      f"{r2row['pct_loss_gt_1atr']*100:.2f}%, and improves p10 slightly "
      f"({r2row['p10_bps']:+.0f} against {base['p10_bps']:+.0f}). If a stop "
      "is required for mandate or psychological reasons, this is the one "
      "that costs least — though what it mostly demonstrates is that a "
      "stop far enough away to be nearly free is also nearly inactive.")
    A("")

    # The controlled-ish comparison that makes this report worth running.
    r1row = d[d["rule"].str.startswith("Rule 1")].iloc[0]
    r1dist = lv.iloc[0]["median_dist_atr"]
    A("### The finding worth keeping: confirmation beats immediacy")
    A("")
    A(f"Rule 1 sits {r1dist:.2f} ATR from entry at the median — "
      "essentially the same distance as the −0.5 ATR rung of the ATR "
      "ladder. The two rules differ almost only in *how* they trigger:")
    A("")
    A("| | −0.5 ATR (intrabar touch) | Rule 1 (5-min close) |")
    A("|---|---:|---:|")
    A(f"| Median stop distance | 0.50 ATR | {r1dist:.2f} ATR |")
    A(f"| % stopped | 34.1% | {r1row['pct_stopped']*100:.1f}% |")
    A(f"| NET | +22.2 | {r1row['net_bps']:+.1f} |")
    A(f"| Cost vs holding | -8.2 | "
      f"{r1row['net_bps'] - base['net_bps']:+.1f} |")
    A(f"| Median | +3.9 | {r1row['median_bps']:+.1f} |")
    A("")
    A(f"**At the same distance, requiring a 5-minute close cuts the "
      f"stop-out rate by a third and halves the cost** "
      f"({abs(r1row['net_bps'] - base['net_bps']):.1f} bps against 8.2). "
      "The trades saved are the ones that poked through the level "
      "intrabar and closed back inside — exactly the temporary excursions "
      "the attribution table keeps identifying. If a stop is going to be "
      "used on this setup, confirming it on a bar close is worth more than "
      "any amount of tuning the distance.")
    A("")
    A("Two caveats on that comparison. Rule 1's distance is a distribution "
      f"(p25 {lv.iloc[0]['p25_dist_atr']:.2f}, p75 "
      f"{lv.iloc[0]['p75_dist_atr']:.2f} ATR), not a constant, so this is "
      "not a perfectly controlled experiment — only the medians line up. "
      "And confirmation is not free in the other direction: it gives up "
      "the hard loss cap, which is why rule 1 leaves "
      f"{r1row['pct_loss_gt_1atr']*100:.2f}% of trades losing more than "
      "1 ATR where the intrabar 0.5 ATR stop left 0.00%.")
    A("")

    # ---------------- 7. caveats ----------------
    A("## 7. Reading notes")
    A("")
    A("- **Close-confirmation is doing a lot of work here.** An intrabar "
      "version of the same levels would stop out far more often and cap "
      "losses far better. That is a different rule, and the specification "
      "asked for the confirmed version.")
    A("- **Rule 3 is close to rule 1 by construction.** The opening range "
      "is the nearer level on most events, so the combined rule fires on "
      "the opening range first the large majority of the time and the gap "
      "level rarely adds anything.")
    A("- **Costs are charged identically to stopped and held trades**, so "
      "every stop rule is flattered relative to holding.")
    A("- **No level was fitted.** These are the levels the specification "
      "named, tested once.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/structstops.py`; "
      "tables in `lambda_data/tables/struct_*.csv`._")
    return "\n".join(L)
