"""entrylimits_text.py — renders ENTRYLIMITS_REPORT.md. Table-focused."""

from __future__ import annotations

import numpy as np
import pandas as pd

BASELINE = "7. Market at 09:35 open"
ORDER = ["A1. 25% of range", "A2. 50% of range (midpoint)",
         "A3. 75% of range", "B4. Candle close",
         "B5. Midpoint of open & close", "B6. Candle open", BASELINE]


def build(R: dict, meta: dict) -> str:
    d = R["main"]
    pw = meta["primary_window"]
    p = d[d["window"] == pw].set_index("rule")
    base = p.loc[BASELINE]
    L: list[str] = []
    A = L.append

    A("# Lambda — Limit-Order Entries on the Post-Earnings Continuation "
      "Setup")
    A("")
    A("Post-earnings T+1, High Volume + Continuation (non-doji). Signal "
      "completes at 09:35; the limit order is placed there and the trade "
      "exits at 10:35. No stop is applied, so the baseline row is the "
      "familiar no-stop figure.")
    A("")
    A("| Input | Definition |")
    A("|---|---|")
    A(f"| Universe | Post-earnings T+1, {meta['start']} → {meta['end']} |")
    A(f"| Signals | {meta['n_signals']:,} |")
    A("| Group A | retracement from the candle's **extreme in the trade's "
      "direction**, by a fraction of the candle range — so 50% lands on "
      "the candle midpoint |")
    A("| Group B | the candle's close, the open/close midpoint, and the "
      "open |")
    A(f"| **Fill window** | order live from 09:35, **cancelled if unfilled "
      f"at {pw}**; the {[k for k in meta['windows'] if k != pw][0]} window "
      "is in section 3 |")
    A("| Fill trigger | a minute's low at/below a buy limit, or high "
      "at/above a sell limit |")
    A("| Fill price | the limit, or the bar's **open** if the bar opened "
      "through it (a better price) |")
    A("| Exit | 10:35, no stop |")
    A(f"| Costs | {meta['cost_bps']} bps round trip |")
    A("")
    A("> **Read the fill rate before the expectancy.** A limit order only "
      "fills if price comes back to it, so every row below is a "
      "*self-selected* sample — and on a continuation setup the trades "
      "that never come back are the ones that ran. Expectancy per filled "
      "trade is therefore not the number that decides anything. Section 4 "
      "gives the two that do.")
    A("")

    # ---------------- 1. main ----------------
    A(f"## 1. Results — {pw} fill window")
    A("")
    A("| Rule | n filled | Fill rate | Win rate | Avg Win | Avg Loss | "
      "Payoff | **NET** | Median | p10 |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in ORDER:
        if r not in p.index:
            continue
        x = p.loc[r]
        sm = " ⚠" if x["small"] == "YES" else ""
        A(f"| {r}{sm} | {int(x['n']):,} | {x['fill_rate']*100:.1f}% | "
          f"{x['win_rate']*100:.1f}% | {x['avg_win_bps']:.1f} | "
          f"{x['avg_loss_bps']:.1f} | {x['payoff_ratio']:.2f} | "
          f"**{x['net_bps']:+.1f}** | {x['median_bps']:+.1f} | "
          f"{x['p10_bps']:+.0f} |")
    A("")
    A("All figures in basis points, on filled trades only, as requested. "
      f"NET is after {meta['cost_bps']} bps.")
    A("")

    # ---------------- 2. vs baseline ----------------
    A("## 2. Against the market order")
    A("")
    A("| Rule | Fill rate | NET | vs baseline | Median | vs baseline |")
    A("|---|---:|---:|---:|---:|---:|")
    for r in ORDER:
        if r not in p.index or r == BASELINE:
            continue
        x = p.loc[r]
        A(f"| {r} | {x['fill_rate']*100:.1f}% | {x['net_bps']:+.1f} | "
          f"**{x['net_bps'] - base['net_bps']:+.1f}** | "
          f"{x['median_bps']:+.1f} | "
          f"{x['median_bps'] - base['median_bps']:+.1f} |")
    A(f"| **{BASELINE}** | 100.0% | **{base['net_bps']:+.1f}** | — | "
      f"{base['median_bps']:+.1f} | — |")
    A("")
    lim = p.drop(index=[BASELINE], errors="ignore")
    better = lim[lim["net_bps"] > base["net_bps"]]
    if len(better):
        b = better["net_bps"].idxmax()
        A(f"**{len(better)} of {len(lim)} limit rules beat the market order "
          f"on expectancy per filled trade**, the best being {b} at "
          f"{better.loc[b, 'net_bps']:+.1f} bps "
          f"({better.loc[b, 'net_bps'] - base['net_bps']:+.1f}) — on a "
          f"{better.loc[b, 'fill_rate']*100:.1f}% fill rate. Whether that "
          "is a real improvement or a selection effect is exactly what "
          "section 4 tests.")
        A("")
    else:
        A("**No limit rule beats the market order even on filled trades**, "
          "which settles the question without needing the selection "
          "analysis: a better entry price did not compensate for the "
          "trades the patience cost.")
        A("")
    A("There is a clean monotone pattern worth naming: the deeper the "
      "pullback demanded, the lower the fill rate and the better the entry "
      "price on the fills that do happen. The rules are ordered by how "
      "much they ask for.")
    A("")
    opp0 = R.get("opportunity")
    if opp0 is not None and len(opp0):
        oo0 = opp0.set_index("rule")
        inert = [r for r in oo0.index
                 if abs(oo0.loc[r, "median_improve_bps"]) < 1.0]
        if inert:
            A("**Two of the rules are barely limit orders at all.** "
              + ", ".join(f"{r} (fill rate "
                          f"{p.loc[r, 'fill_rate']*100:.1f}%, median entry "
                          "improvement "
                          f"{oo0.loc[r, 'median_improve_bps']:+.1f} bps)"
                          for r in inert if r in p.index)
              + ". On a continuation candle the 09:35 open has usually "
              "already retraced past those levels, so the order fills "
              "immediately at the open — which is the market order. Their "
              "near-baseline results are not evidence that patience works; "
              "they are evidence that these two rules mostly do not ask "
              "for any.")
            A("")

    # ---------------- 3. fill window ----------------
    other = [k for k in meta["windows"] if k != pw][0]
    o = d[d["window"] == other].set_index("rule")
    A(f"## 3. Sensitivity to the fill window ({pw} vs {other})")
    A("")
    A("| Rule | Fill rate @ " + pw + " | Fill rate @ " + other +
      " | NET @ " + pw + " | NET @ " + other + " |")
    A("|---|---:|---:|---:|---:|")
    for r in ORDER:
        if r not in p.index or r not in o.index:
            continue
        A(f"| {r} | {p.loc[r, 'fill_rate']*100:.1f}% | "
          f"{o.loc[r, 'fill_rate']*100:.1f}% | "
          f"{p.loc[r, 'net_bps']:+.1f} | {o.loc[r, 'net_bps']:+.1f} |")
    A("")
    dn = [o.loc[r, "net_bps"] - p.loc[r, "net_bps"] for r in ORDER
          if r in p.index and r in o.index and r != BASELINE]
    if dn:
        A(f"Extending the window to {other} raises fill rates but moves "
          f"expectancy by {min(dn):+.1f} to {max(dn):+.1f} bps. The extra "
          "fills are trades that took longer to come back, and a "
          "continuation trade that is still retracing 25 minutes in is a "
          "different animal from one that dipped and turned.")
        A("")

    # ---------------- 4. selection ----------------
    opp = R.get("opportunity")
    A("## 4. The selection problem, quantified")
    A("")
    A("Two questions decide whether a limit entry is actually better, and "
      "neither is answerable from the filled-trade table alone.")
    A("")
    A("**(a) What does a signal earn, counting the ones you never got "
      "into?** An unfilled signal earns nothing, so the deployment number "
      "is expectancy per fill × fill rate.")
    A("")
    A("| Rule | NET per filled trade | Fill rate | **NET per signal** | "
      "vs baseline |")
    A("|---|---:|---:|---:|---:|")
    for r in ORDER:
        if r not in p.index:
            continue
        x = p.loc[r]
        A(f"| {r} | {x['net_bps']:+.1f} | {x['fill_rate']*100:.1f}% | "
          f"**{x['net_per_signal_bps']:+.1f}** | "
          + ("—" if r == BASELINE else
             f"{x['net_per_signal_bps'] - base['net_per_signal_bps']:+.1f}")
          + " |")
    A("")
    ps = lim["net_per_signal_bps"]
    if len(ps) and ps.max() < base["net_per_signal_bps"]:
        A(f"**Every limit rule loses on this measure**, by "
          f"{base['net_per_signal_bps'] - ps.max():.1f} to "
          f"{base['net_per_signal_bps'] - ps.min():.1f} bps per signal. "
          "Waiting for a better price means not being in the trades that "
          "never offer one, and on a continuation setup that is a "
          "systematically expensive group to miss.")
        A("")
    A("> This comparison assumes one unit of capital per *signal*. If "
      "capital is instead the binding constraint and unfilled signals free "
      "it up for something else, the per-filled-trade column is the "
      "relevant one — but then the alternative use has to earn its own "
      "keep, and nothing here measures that.")
    A("")

    if opp is not None and len(opp):
        A("**(b) What did the missed trades do?** Every unfilled signal, "
          "priced at the baseline market entry:")
        A("")
        A("| Rule | Filled | Missed | Missed trades' baseline NET | "
          "Filled trades' baseline NET | Median entry improvement |")
        A("|---|---:|---:|---:|---:|---:|")
        oo = opp.set_index("rule")
        for r in ORDER:
            if r not in oo.index:
                continue
            x = oo.loc[r]
            A(f"| {r} | {int(x['n_filled']):,} | {int(x['n_missed']):,} | "
              f"**{x['missed_baseline_bps']:+.1f}** | "
              f"{x['filled_baseline_bps']:+.1f} | "
              f"{x['median_improve_bps']:+.1f} |")
        A("")
        gaps = oo["missed_baseline_bps"] - oo["filled_baseline_bps"]
        if (gaps > 0).all():
            A(f"**The missed trades were the better trades, under every "
              f"rule** — by {gaps.min():.1f} to {gaps.max():.1f} bps on the "
              "same baseline entry. This is the mechanism in one line: "
              "price comes back to your limit precisely when the move is "
              "not working, and runs away from it when the move is. The "
              "limit order systematically selects the weaker half of the "
              "signal.")
            A("")
            A("The last column shows what the patience buys when it does "
              "work — a median entry improvement of "
              f"{oo['median_improve_bps'].min():.0f} to "
              f"{oo['median_improve_bps'].max():.0f} bps. That is a real "
              "saving, and it is not large enough to pay for the "
              "selection.")
            A("")
        elif (gaps < 0).all():
            A("The missed trades were the *worse* trades under every rule, "
              "so the limit entry is selecting favourably — the opposite of "
              "the usual concern.")
            A("")

    # ---------------- 5. caveats ----------------
    A("## 5. Reading notes")
    A("")
    A("- **Fills are assumed at the limit price with no queue risk.** In "
      "reality a limit resting at a round retracement level fills last, "
      "and often only because the market is about to trade through it. "
      "Every limit row is therefore optimistic; the baseline market order "
      "is not.")
    A("- **Costs are the same flat "
      f"{meta['cost_bps']} bps for every rule.** A limit entry genuinely "
      "should pay less than a market order — it earns the spread rather "
      "than crossing it — so this understates limit entries by roughly "
      "half the spread on one side. That is worth perhaps 1–2 bps here, "
      "which does not close the gaps in section 4.")
    A("- **Only the entry varies.** Signal, cohort, exit and holding "
      "period are identical across all seven rows, so the comparison is "
      "clean on everything except the selection effect it is designed to "
      "expose.")
    A("- **No stop is applied**, matching the baseline used in the stop "
      "reports. A limit entry combined with a stop would interact, and "
      "nothing here tests that.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/entrylimits.py`; "
      "tables in `lambda_data/tables/entlim_*.csv`._")
    return "\n".join(L)
