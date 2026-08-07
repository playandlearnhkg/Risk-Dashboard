"""intrastruct_text.py — renders INTRASTRUCT_REPORT.md. Table-focused."""

from __future__ import annotations

import numpy as np
import pandas as pd

NOSTOP = "4. No stop (baseline)"
R1, R2, R3 = "1. Opening Range", "2. Gap Level", "3. Combined"
RULES = [R1, R2, R3]


def build(R: dict, meta: dict) -> str:
    d = R["main"]
    m = d.set_index(["rule", "trigger"])
    ib = d[d["trigger"] == "intrabar"].set_index("rule")
    cc = d[d["trigger"] == "5-min close"].set_index("rule")
    base = m.loc[(NOSTOP, "—")]
    pred = R["prediction"].set_index("rule")
    L: list[str] = []
    A = L.append

    A("# Lambda — Intrabar Structural Stops Over the Full Holding Period")
    A("")
    A("Post-earnings T+1, High Volume + Continuation (non-doji), entry at "
      "the open of the 09:35 bar, exit at 10:35 if no stop triggers. The "
      "same structural levels as `STRUCTSTOPS_REPORT.md`, now triggered on "
      "the first intrabar touch rather than on a 5-minute close.")
    A("")
    A("| Input | Definition |")
    A("|---|---|")
    A(f"| Universe | Post-earnings T+1, {meta['start']} → {meta['end']} |")
    A(f"| Cohort | {meta['n']:,} events |")
    A("| Rule 1 | first touch beyond the 09:30–09:35 candle's **low** "
      "(long) / **high** (short) |")
    A("| Rule 2 | first touch beyond the **prior day's close** |")
    A("| Rule 3 | first touch of whichever level is nearer |")
    A("| Fill | the level, or the bar's **open** if it opened through |")
    A("| ATR | prior-session ATR(14) |")
    A(f"| Costs | {meta['cost_bps']} bps round trip |")
    A("")

    # ---------------- 1. results ----------------
    A("## 1. Results — intrabar trigger")
    A("")
    A("| Rule | % stopped | **NET** | Avg Win | Avg Loss | Payoff | "
      "% loss > 1 ATR | Avg loss > 1 ATR | Avg overshoot | Median "
      "overshoot | Worst overshoot |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in RULES:
        x = ib.loc[r]
        sev = (f"{x['avg_loss_1atr_bps']:.0f} bps"
               if not pd.isna(x["avg_loss_1atr_bps"]) else "—")
        A(f"| {r} | {x['pct_stopped']*100:.1f}% | **{x['net_bps']:+.1f}** | "
          f"{x['avg_win_bps']:.1f} | {x['avg_loss_bps']:.1f} | "
          f"{x['payoff_ratio']:.2f} | {x['pct_loss_1atr']*100:.2f}% | "
          f"{sev} | {x['avg_over_bps']:.1f} bps | "
          f"{x['median_over_bps']:.1f} bps | "
          f"{x['worst_over_bps']:,.0f} bps |")
    A(f"| **{NOSTOP}** | — | **{base['net_bps']:+.1f}** | "
      f"{base['avg_win_bps']:.1f} | {base['avg_loss_bps']:.1f} | "
      f"{base['payoff_ratio']:.2f} | {base['pct_loss_1atr']*100:.2f}% | "
      f"{base['avg_loss_1atr_bps']:.0f} bps | — | — | — |")
    A("")
    A("Overshoot is the intended level minus the realised fill, in the "
      "adverse direction; it can only be non-zero when a bar opened "
      "through the level.")
    A("")

    # ---------------- 2. intrabar vs confirmed ----------------
    A("## 2. Intrabar versus close-confirmed, same levels")
    A("")
    A("| Rule | Trigger | % stopped | NET | % loss > 1 ATR | "
      "Avg overshoot | Overshoot drag |")
    A("|---|---|---:|---:|---:|---:|---:|")
    for r in RULES:
        for trig, tbl in (("intrabar", ib), ("5-min close", cc)):
            if r not in tbl.index:
                continue
            x = tbl.loc[r]
            A(f"| {r} | {trig} | {x['pct_stopped']*100:.1f}% | "
              f"{x['net_bps']:+.1f} | {x['pct_loss_1atr']*100:.2f}% | "
              f"{x['avg_over_bps']:.1f} bps | "
              f"{x['over_drag_bps']:+.1f} bps |")
    A("")
    A("**Fill quality improves enormously, and it does not save the "
      "rules.** Moving to an intrabar trigger cuts average overshoot from "
      + ", ".join(f"{cc.loc[r, 'avg_over_bps']:.0f}→"
                  f"{ib.loc[r, 'avg_over_bps']:.1f} bps"
                  for r in RULES if r in cc.index and r in ib.index)
      + " — a 20-to-30-fold improvement — because the stop now exits at "
      "its level instead of wherever the bar happened to close.")
    A("")

    # ---------------- 3. the prediction ----------------
    A("## 3. The prediction from the last report, tested")
    A("")
    A("`STOPSUMMARY_REPORT.md` observed that adding each confirmed rule's "
      "overshoot back to its NET would put it ahead of holding, and "
      "suggested an intrabar version \"would capture most of that gap\". "
      "That was my inference, and it was wrong. Here it is against the "
      "data:")
    A("")
    A("| Rule | Confirmed NET | Overshoot added back → predicted | "
      "**Actual intrabar NET** | Miss |")
    A("|---|---:|---:|---:|---:|")
    for r in RULES:
        x = pred.loc[r]
        A(f"| {r} | {x['cc_net']:+.1f} | {x['predicted_net']:+.1f} | "
          f"**{x['ib_net']:+.1f}** | "
          f"{x['ib_net'] - x['predicted_net']:+.1f} |")
    A("")
    misses = pred["ib_net"] - pred["predicted_net"]
    A(f"**The intrabar versions come in {abs(misses.max()):.1f} to "
      f"{abs(misses.min()):.1f} bps below the counterfactual**, not close "
      "to it. The flaw in the inference was holding the stopped set fixed: "
      "the add-back asked what the *same* stops would have earned at "
      "better prices, but an intrabar trigger does not stop the same "
      "trades. It fires on every temporary poke through the level, so it "
      "stops far more of them:")
    A("")
    A("| Rule | % stopped, confirmed | % stopped, intrabar | Increase |")
    A("|---|---:|---:|---:|")
    for r in RULES:
        a, b = cc.loc[r, "pct_stopped"], ib.loc[r, "pct_stopped"]
        A(f"| {r} | {a*100:.1f}% | {b*100:.1f}% | "
          f"**{(b - a)*100:+.1f} pp** |")
    A("")
    A("Better fills on many more stops is a different trade from better "
      "fills on the same stops. The extra trades caught are exactly the "
      "ones that dipped through the level and recovered — the temporary "
      "excursions every report in this series keeps identifying — and "
      "cutting them costs more than the improved fills save.")
    A("")

    # ---------------- 4. against baseline ----------------
    A("## 4. Against holding")
    A("")
    A("| Rule | Trigger | NET | vs no stop | % loss > 1 ATR | vs no stop |")
    A("|---|---|---:|---:|---:|---:|")
    for r in RULES:
        for trig, tbl in (("intrabar", ib), ("5-min close", cc)):
            if r not in tbl.index:
                continue
            x = tbl.loc[r]
            A(f"| {r} | {trig} | {x['net_bps']:+.1f} | "
              f"**{x['net_bps'] - base['net_bps']:+.1f}** | "
              f"{x['pct_loss_1atr']*100:.2f}% | "
              f"{(x['pct_loss_1atr'] - base['pct_loss_1atr'])*100:+.2f} pp |")
    A(f"| **{NOSTOP}** | — | **{base['net_bps']:+.1f}** | — | "
      f"{base['pct_loss_1atr']*100:.2f}% | — |")
    A("")
    best_ib = ib["net_bps"].idxmax()
    if ib["net_bps"].max() < base["net_bps"]:
        A(f"**No intrabar structural rule beats holding either.** The best "
          f"of them ({best_ib}) gives up "
          f"{base['net_bps'] - ib.loc[best_ib, 'net_bps']:.1f} bps. Across "
          "every stop family tried in this series — ATR from entry, "
          "time-delayed ATR, structural on a confirmed close, structural "
          "intrabar, and anchored VWAP — holding to the hour still wins on "
          "expectancy.")
        A("")
    else:
        A(f"**{best_ib} beats holding on the intrabar trigger** at "
          f"{ib.loc[best_ib, 'net_bps']:+.1f} bps against "
          f"{base['net_bps']:+.1f} — the first stop rule in this series to "
          "do so.")
        A("")

    # efficiency
    A("On the efficiency measure used in `STOPSUMMARY_REPORT.md` — "
      "percentage points of >1 ATR tail removed per bp of expectancy "
      "surrendered:")
    A("")
    A("| Rule | Trigger | Cost | Tail cut (pp) | **pp per bp** |")
    A("|---|---|---:|---:|---:|")
    effrows = []
    for r in RULES:
        for trig, tbl in (("intrabar", ib), ("5-min close", cc)):
            if r not in tbl.index:
                continue
            x = tbl.loc[r]
            paid = base["net_bps"] - x["net_bps"]
            cut = (base["pct_loss_1atr"] - x["pct_loss_1atr"]) * 100
            effrows.append((r, trig, paid, cut,
                            cut / paid if paid > 0 else np.nan))
    for r, trig, paid, cut, ratio in sorted(
            effrows, key=lambda z: (-z[4] if not np.isnan(z[4]) else 1e9)):
        A(f"| {r} | {trig} | −{paid:.1f} | {cut:.2f} | **{ratio:.2f}** |")
    A("")
    best = max((z for z in effrows if not np.isnan(z[4])), key=lambda z: z[4])
    A(f"The best structural variant on this measure is **{best[0]} "
      f"({best[1]})** at {best[4]:.2f} pp per bp — still short of the "
      "0.88 that the intrabar ATR −1.0 stop achieves, which remains the "
      "most efficient tail-control instrument found anywhere in this "
      "series.")
    A("")

    # ---------------- 5. what did improve ----------------
    A("## 5. What the intrabar trigger did deliver")
    A("")
    A("| Rule | Trigger | % loss > 1 ATR | Avg loss > 1 ATR | "
      "Worst loss | Drag from >1 ATR losses |")
    A("|---|---|---:|---:|---:|---:|")
    for r in RULES:
        for trig, tbl in (("5-min close", cc), ("intrabar", ib)):
            if r not in tbl.index:
                continue
            x = tbl.loc[r]
            sev = (f"{x['avg_loss_1atr_bps']:.0f} bps"
                   if not pd.isna(x["avg_loss_1atr_bps"]) else "none left")
            wl = (f"{x['worst_loss_bps']:,.0f} bps"
                  if not pd.isna(x["worst_loss_bps"]) else "—")
            A(f"| {r} | {trig} | {x['pct_loss_1atr']*100:.2f}% | {sev} | "
              f"{wl} | {x['drag_1atr_bps']:+.1f} bps |")
    A(f"| **{NOSTOP}** | — | {base['pct_loss_1atr']*100:.2f}% | "
      f"{base['avg_loss_1atr_bps']:.0f} bps | "
      f"{base['worst_loss_bps']:,.0f} bps | {base['drag_1atr_bps']:+.1f} "
      "bps |")
    A("")
    improved = [r for r in RULES
                if ib.loc[r, "worst_loss_bps"] > cc.loc[r, "worst_loss_bps"]]
    unchanged = [r for r in RULES
                 if abs(ib.loc[r, "worst_loss_bps"]
                        - base["worst_loss_bps"]) < 1.0]
    A("This is where the intrabar trigger does earn something. Every rule "
      "cuts both the frequency and the average severity of >1 ATR losses "
      "relative to its confirmed twin, and the drag falls with it.")
    A("")
    if unchanged:
        A("**But it does not deliver a bounded loss, and that is worth "
          "being precise about.** "
          + ", ".join(unchanged) + " still carries a worst case of "
          f"{abs(base['worst_loss_bps']):,.0f} bps — identical to no stop "
          "at all. A structural level only caps a loss if price actually "
          "reaches it, and on a large gap the prior close can sit further "
          "away than the entire adverse move. The worst trade in this "
          "cohort never traded down to its gap level; it simply lost "
          "money without ever triggering the stop.")
        A("")
        A("That is the difference between a structural stop and an ATR "
          "stop in one sentence: an ATR stop is defined by *distance*, so "
          "it always binds; a structural stop is defined by a *price*, so "
          "it binds only when the chart cooperates. Only "
          + (", ".join(improved) if improved else "none of these rules")
          + " improved the worst case at all"
          + (f", and only from {abs(cc.loc[improved[0], 'worst_loss_bps']):,.0f} "
             f"to {abs(ib.loc[improved[0], 'worst_loss_bps']):,.0f} bps."
             if improved else "."))
        A("")

    # ---------------- 6. caveats ----------------
    A("## 6. Reading notes")
    A("")
    A("- **The correction in section 3 is the main result.** An add-back "
      "counterfactual that holds the stopped set fixed is an upper bound "
      "on a different rule, not a forecast of the rule you would actually "
      "run. I drew that inference in the previous report and it did not "
      "survive the test.")
    A("- **Costs are flat "
      f"{meta['cost_bps']} bps** and identical for stopped and held "
      "trades, so every stop rule here is flattered relative to holding — "
      "and the intrabar rules, which stop far more often, most of all.")
    A("- **No intrabar path within the minute.** If a bar's low breaches "
      "the level and its high also runs favourably, this test assumes the "
      "stop fired. Correct for a stop-only study, and conservative.")
    A("- **Nothing here was fitted.** Both levels are read directly off "
      "the chart with no free parameter.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/intrastruct.py`; "
      "tables in `lambda_data/tables/instr_*.csv`._")
    return "\n".join(L)
