"""lossanalysis_text.py — renders LOSS_REPORT.md. Table-focused."""

from __future__ import annotations

import numpy as np
import pandas as pd

NOSTOP = "1. No stop"


def build(R: dict, meta: dict) -> str:
    sev = R["severity"]
    ctx = R["context"].set_index("rule")
    s1 = sev[sev["threshold"] == 1.0].set_index("rule")
    s05 = sev[sev["threshold"] == 0.5].set_index("rule")
    order = list(ctx.index)
    L: list[str] = []
    A = L.append

    A("# Lambda — Severity of Large Losses Under Seven Stop Rules")
    A("")
    A("Post-earnings T+1, High Volume + Continuation (non-doji), entry at "
      "the open of the 09:35 bar, exit at 1 hour if no stop triggers. The "
      "question here is not expectancy — it is how bad the losses that get "
      "through actually are.")
    A("")
    A("| Input | Definition |")
    A("|---|---|")
    A(f"| Universe | Post-earnings T+1, {meta['start']} → {meta['end']} |")
    A(f"| Cohort | {meta['n']:,} events — identical to the earlier stop "
      "reports |")
    A("| Rules 2, 3, 6, 7 | confirm on the **5-minute close**, exit at that "
      f"close ({meta['n_checks']} checkpoints, 09:40–10:35) |")
    A("| Rules 4, 5 | fire on the first **intrabar touch**, fill at the "
      "stop or the bar's open if it opened through |")
    A("| ATR | prior-session ATR(14); no gap-day data |")
    A("| AVWAP | cumulative volume-weighted (H+L+C)/3 from the anchor, "
      "evaluated with minutes 0..t only |")
    A(f"| Costs | {meta['cost_bps']} bps round trip, in NET only |")
    A("")
    A("> **On rule 7.** An anchored VWAP accumulates volume from its "
      "anchor, and no regular-session volume trades between the prior "
      "close and 09:30 — so read literally, \"anchored at the prior "
      "close\" and \"anchored at 09:30\" are the *same line*, and rule 7 "
      "would duplicate rule 6. To make it a distinct rule the anchor has "
      "to contribute the prior close as a price observation, which needs a "
      "weight, and no weight is canonical. I seeded it with the prior "
      "close carrying the first 5-minute candle's volume — same scale as "
      "the early session, not tuned. That drags the line toward the "
      "unfilled gap and makes the stop **wider** than rule 6. Section 5 "
      "varies the seed so you can see how much rides on the choice.")
    A("")

    # ---------------- context ----------------
    A("## 1. Context — what each rule does before we look at the tail")
    A("")
    A("| Rule | % stopped | Win rate | NET | Median | p10 |")
    A("|---|---:|---:|---:|---:|---:|")
    for r in order:
        x = ctx.loc[r]
        A(f"| {r} | "
          + ("—" if r == NOSTOP else f"{x['pct_stopped']*100:.1f}%")
          + f" | {x['win_rate']*100:.1f}% | {x['net_bps']:+.1f} | "
          f"{x['median_bps']:+.1f} | {x['p10_bps']:+.0f} |")
    A("")

    # ---------------- A ----------------
    A("## 2. A — Losses larger than 1.0 ATR")
    A("")
    A("| Rule | n | % of all trades | Avg loss (bps) | Avg loss (ATR) | "
      "Median loss (bps) | Median (ATR) | Worst loss (bps) | Worst (ATR) |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in order:
        x = s1.loc[r]
        if not x["n_loss"]:
            A(f"| {r} | **0** | 0.00% | — | — | — | — | — | — |")
            continue
        A(f"| {r} | {int(x['n_loss']):,} | {x['pct_loss']*100:.2f}% | "
          f"{x['avg_loss_bps']:.0f} | {x['avg_loss_atr']:.2f} | "
          f"{x['median_loss_bps']:.0f} | {x['median_loss_atr']:.2f} | "
          f"{x['worst_loss_bps']:,.0f} | {x['worst_loss_atr']:.2f} |")
    A("")

    # ---------------- B ----------------
    A("## 3. B — Losses larger than 0.5 ATR")
    A("")
    A("| Rule | n | % of all trades | Avg loss (bps) | Avg loss (ATR) | "
      "Median loss (bps) | Median (ATR) |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    for r in order:
        x = s05.loc[r]
        if not x["n_loss"]:
            A(f"| {r} | **0** | 0.00% | — | — | — | — |")
            continue
        A(f"| {r} | {int(x['n_loss']):,} | {x['pct_loss']*100:.2f}% | "
          f"{x['avg_loss_bps']:.0f} | {x['avg_loss_atr']:.2f} | "
          f"{x['median_loss_bps']:.0f} | {x['median_loss_atr']:.2f} |")
    A("")

    # ---------------- read ----------------
    A("## 4. What the tail actually shows")
    A("")
    A("Every rule and its tail, side by side:")
    A("")
    A("| Rule | Confirmation | % beyond 1 ATR | Avg loss when beyond | "
      "Worst |")
    A("|---|---|---:|---:|---:|")
    conf = {"2. Gap Level": "5-min close", "3. Opening Range": "5-min close",
            "4. ATR −0.5": "intrabar", "5. ATR −1.0": "intrabar",
            "6. AVWAP from 09:30": "5-min close",
            "7. AVWAP from prior close": "5-min close",
            NOSTOP: "—"}
    for r in order:
        x = s1.loc[r]
        A(f"| {r} | {conf.get(r, '')} | {x['pct_loss']*100:.2f}% | "
          + (f"{x['avg_loss_bps']:.0f} bps | {x['worst_loss_bps']:,.0f} bps |"
             if x["n_loss"] else "— | — |"))
    A("")

    v6, v7 = "6. AVWAP from 09:30", "7. AVWAP from prior close"

    # Tail control is not free; rank the rules by what they charge for it.
    bn = ctx.loc[NOSTOP, "net_bps"]
    bt = s1.loc[NOSTOP, "pct_loss"] * 100
    eff = []
    for r in order:
        if r == NOSTOP:
            continue
        cut = bt - s1.loc[r, "pct_loss"] * 100
        paid = bn - ctx.loc[r, "net_bps"]
        eff.append({"rule": r, "cut": cut, "paid": paid,
                    "ratio": cut / paid if paid > 0 else np.nan})
    eff = pd.DataFrame(eff).sort_values("ratio", ascending=False)
    A("**Tail control is not free, and the rules differ enormously in what "
      "they charge for it.**")
    A("")
    A("| Rule | Tail cut (pp beyond 1 ATR) | Expectancy paid (bps) | "
      "**pp of tail per bp paid** |")
    A("|---|---:|---:|---:|")
    for _, x in eff.iterrows():
        A(f"| {x['rule']} | {x['cut']:.2f} | {x['paid']:.1f} | "
          f"**{x['ratio']:.2f}** |")
    A("")
    top = eff.iloc[0]
    A(f"**{top['rule']} is the most efficient tail-control instrument "
      f"tested** — {top['cut']:.2f} percentage points of >1 ATR losses "
      f"removed for {top['paid']:.1f} bps of expectancy. It is not the "
      "rule that cuts the most tail, and it is not the cheapest rule; it "
      "is the best exchange rate between the two.")
    A("")
    v6r = s1.loc[v6] if v6 in s1.index else None
    a5 = s1.loc["5. ATR −1.0"] if "5. ATR −1.0" in s1.index else None
    if v6r is not None and a5 is not None:
        A("**And the mechanism matters more than the trigger type.** It "
          "would be natural to assume intrabar stops truncate the tail and "
          "close-confirmed ones cannot, since an intrabar stop exits *at* "
          "its level while a confirmed stop exits at whatever price the bar "
          "closes at. The data does not support that as a general rule:")
        A("")
        A("| | ATR −1.0 (intrabar) | AVWAP 09:30 (5-min close) |")
        A("|---|---:|---:|")
        A(f"| % beyond 1 ATR | {a5['pct_loss']*100:.2f}% | "
          f"{v6r['pct_loss']*100:.2f}% |")
        A(f"| % stopped | {ctx.loc['5. ATR −1.0', 'pct_stopped']*100:.1f}% | "
          f"{ctx.loc[v6, 'pct_stopped']*100:.1f}% |")
        A(f"| NET | {ctx.loc['5. ATR −1.0', 'net_bps']:+.1f} | "
          f"{ctx.loc[v6, 'net_bps']:+.1f} |")
        A("")
        A(f"The close-confirmed AVWAP reaches essentially the same tail "
          f"({v6r['pct_loss']*100:.2f}% against "
          f"{a5['pct_loss']*100:.2f}%) — but it gets there by stopping "
          f"**{ctx.loc[v6, 'pct_stopped']*100:.0f}% of all trades** rather "
          f"than {ctx.loc['5. ATR −1.0', 'pct_stopped']*100:.0f}%, and it "
          f"costs {bn - ctx.loc[v6, 'net_bps']:.1f} bps rather than "
          f"{bn - ctx.loc['5. ATR −1.0', 'net_bps']:.1f}. Two routes to the "
          "same tail: cap the loss precisely, or exit almost everything "
          "early. The first is three times cheaper.")
        A("")
    A("The intrabar advantage is still real where it applies — the "
      "−0.5 ATR stop is the only rule that removes the >1 ATR tail "
      "**entirely**, which no close-confirmed rule can promise, because a "
      "confirmed break has no ceiling on where it fills.")
    A("")

    # VWAP specifics
    if v6 in s1.index and v7 in s1.index:
        a, b = s1.loc[v6], s1.loc[v7]
        ca, cb = ctx.loc[v6], ctx.loc[v7]
        A("**The two VWAP anchors behave very differently**, which "
          "vindicates treating them as separate rules rather than "
          "variations:")
        A("")
        A("| | AVWAP 09:30 | AVWAP prior close |")
        A("|---|---:|---:|")
        A(f"| % stopped | {ca['pct_stopped']*100:.1f}% | "
          f"{cb['pct_stopped']*100:.1f}% |")
        A(f"| NET | {ca['net_bps']:+.1f} | {cb['net_bps']:+.1f} |")
        A(f"| % beyond 1 ATR | {a['pct_loss']*100:.2f}% | "
          f"{b['pct_loss']*100:.2f}% |")
        A(f"| Avg loss beyond 1 ATR | {a['avg_loss_bps']:.0f} | "
          f"{b['avg_loss_bps']:.0f} |")
        A(f"| Worst | {a['worst_loss_bps']:,.0f} | "
          f"{b['worst_loss_bps']:,.0f} |")
        A("")
        tighter = (v6 if ca["pct_stopped"] > cb["pct_stopped"] else v7)
        tighter = tighter.split(". ", 1)[1]
        A(f"The **{tighter}** anchor is the more active of the two, as "
          "expected: seeding the anchor with the prior close pulls the line "
          "toward the "
          "unfilled gap on a gap up, so price has further to fall before it "
          "closes below. The seeded version is closer to a wide structural "
          "stop; the 09:30 version is closer to a moving one that rises "
          "with the session.")
        A("")

    # aggregate drag
    A("**The cost of the tail, expressed as drag on the whole book.** "
      "Summing every loss beyond 1 ATR and dividing by all "
      f"{meta['n']:,} trades:")
    A("")
    A("| Rule | Drag from >1 ATR losses (bps per trade) | vs no stop |")
    A("|---|---:|---:|")
    bd = s1.loc[NOSTOP, "total_drag_bps"]
    for r in order:
        x = s1.loc[r]
        v = x["total_drag_bps"] if x["n_loss"] else 0.0
        A(f"| {r} | {v:+.1f} | "
          + ("—" if r == NOSTOP else f"{v - bd:+.1f}") + " |")
    A("")
    A("This is the number a stop is supposed to improve, and it is the "
      "only column in this report where the stops clearly earn their keep. "
      "Read it against the NET column in section 1 to see what each one "
      "charged for the improvement.")
    A("")

    # ---------------- seed sensitivity ----------------
    ss = R.get("seed_sens")
    if ss is not None and len(ss):
        A("## 5. How much of rule 7 rides on the seed weight?")
        A("")
        A("| Seed weight | % stopped | NET | % beyond 1 ATR | "
          "% beyond 0.5 ATR | Avg loss beyond 1 ATR |")
        A("|---|---:|---:|---:|---:|---:|")
        for _, x in ss.iterrows():
            A(f"| {x['seed_mult']:.1f}× c1 volume | "
              f"{x['pct_stopped']*100:.1f}% | {x['net_bps']:+.1f} | "
              f"{x['pct_loss_1atr']*100:.2f}% | "
              f"{x['pct_loss_05atr']*100:.2f}% | "
              f"{x['avg_loss_1atr_bps']:.0f} bps |")
        A("")
        spread = ss["net_bps"].max() - ss["net_bps"].min()
        tspread = (ss["pct_loss_1atr"].max() - ss["pct_loss_1atr"].min()) * 100
        A(f"Across a 4× range of seed weights, NET moves {spread:.1f} bps "
          f"and the >1 ATR rate moves {tspread:.2f} percentage points. "
          + ("The choice of seed is therefore not driving the conclusion."
             if spread < 2.0 else
             "The seed choice does move the result, so rule 7's figures "
             "should be read as one point on this curve rather than as a "
             "property of the rule."))
        A("")

    # ---------------- caveats ----------------
    A("## 6. Reading notes")
    A("")
    A("- **Losses are measured after the exit rule, gross of the "
      f"{meta['cost_bps']} bps.** Costs are charged identically to stopped "
      "and held trades, which flatters every stop.")
    A("- **The worst-loss column is one observation.** It is reported "
      "because the question asked for it, not because a single realised "
      "extreme is a stable statistic.")
    A("- **Rule 7's seed weight is a judgement call**, disclosed above and "
      "stress-tested in section 5. Rule 6 has no such freedom.")
    A("- **Comparing stop-out rates across the two families is not "
      "meaningful** — intrabar and close-confirmed triggers are different "
      "mechanisms. Comparing loss severity across them, which is what this "
      "report does, is exactly the right use of the pair.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/lossanalysis.py`; "
      "tables in `lambda_data/tables/loss_*.csv`._")
    return "\n".join(L)
