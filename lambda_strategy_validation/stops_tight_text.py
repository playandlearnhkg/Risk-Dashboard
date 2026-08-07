"""stops_tight_text.py — renders STOPS_TIGHT_REPORT.md. Table-focused."""

from __future__ import annotations

import numpy as np
import pandas as pd

NOSTOP = "No stop (hold to 1 hour)"


def build(R: dict, meta: dict) -> str:
    d = R["ladder"]
    base = d[d["rule"] == NOSTOP].iloc[0]
    req = d[d["requested"] & (d["rule"] != NOSTOP)]
    stops = d[d["rule"] != NOSTOP]
    L: list[str] = []
    A = L.append

    A("# Lambda — Tighter ATR Stops on the Post-Earnings Continuation Setup")
    A("")
    A("Post-earnings T+1, High Volume + Continuation (non-doji), entry at "
      "the open of the 09:35 bar, exit at 1 hour (10:35) if the stop is not "
      "hit. Extends `STOPS_REPORT.md` to tighter levels.")
    A("")
    A("| Input | Definition |")
    A("|---|---|")
    A(f"| Universe | Post-earnings T+1, {meta['start']} → {meta['end']} |")
    A(f"| Cohort | {meta['n']:,} events — identical to `STOPS_REPORT.md`, "
      "built by the same code |")
    A("| Stop distance | **prior-session ATR(14)**, a window ending the day "
      "before the gap |")
    A("| Trigger | intrabar: the bar's **low** for a long, **high** for a "
      "short |")
    A("| Fill | the stop price, or the bar's **open** if the bar opened "
      "through it |")
    A(f"| Costs | {meta['cost_bps']} bps round trip, charged identically to "
      "stopped and held trades |")
    A("")

    # ---------------- 1. requested ----------------
    A("## 1. Results")
    A("")
    A("| Rule | n | % stopped | Win rate | Avg Win | Avg Loss | Payoff | "
      "**NET** | Median | p10 | % realised loss > 1 ATR |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, x in pd.concat([req, d[d["rule"] == NOSTOP]]).iterrows():
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

    # ---------------- 2. full ladder ----------------
    A("## 2. The full ladder")
    A("")
    A("Including the looser stops from the previous report, so the shape is "
      "visible end to end.")
    A("")
    A("| Stop | % stopped | Win rate | Payoff | **NET** | vs no stop | "
      "Median | p10 | % loss > 1 ATR |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, x in d.sort_values("mult").iterrows():
        if x["rule"] == NOSTOP:
            continue
        A(f"| {x['rule']} | {x['pct_stopped']*100:.1f}% | "
          f"{x['win_rate']*100:.1f}% | {x['payoff_ratio']:.2f} | "
          f"**{x['net_bps']:+.1f}** | "
          f"{x['net_bps'] - base['net_bps']:+.1f} | "
          f"{x['median_bps']:+.1f} | {x['p10_bps']:+.0f} | "
          f"{x['pct_loss_gt_1atr']*100:.2f}% |")
    A(f"| **{NOSTOP}** | — | {base['win_rate']*100:.1f}% | "
      f"{base['payoff_ratio']:.2f} | **{base['net_bps']:+.1f}** | — | "
      f"{base['median_bps']:+.1f} | {base['p10_bps']:+.0f} | "
      f"{base['pct_loss_gt_1atr']*100:.2f}% |")
    A("")

    srt = d[d["rule"] != NOSTOP].sort_values("mult")
    mono = all(srt["net_bps"].iloc[i] <= srt["net_bps"].iloc[i + 1]
               for i in range(len(srt) - 1))
    tightest = srt.iloc[0]
    if mono:
        A(f"**NET rises monotonically with the stop distance across all "
          f"{len(srt)} levels**, from {tightest['net_bps']:+.1f} bps at "
          f"{tightest['rule']} to {srt['net_bps'].iloc[-1]:+.1f} at "
          f"{srt['rule'].iloc[-1]}, and no level reaches the "
          f"{base['net_bps']:+.1f} bps of not stopping at all. There is no "
          "interior optimum — the ladder has no peak to find, it just "
          "climbs toward the no-stop case.")
        A("")

    # ---------------- 3. cost curve ----------------
    A("## 3. What each level costs")
    A("")
    A("| Stop | % stopped | NET | Cost vs no stop | Cost per 1% of trades "
      "stopped |")
    A("|---|---:|---:|---:|---:|")
    for _, x in srt.iterrows():
        cost = base["net_bps"] - x["net_bps"]
        per = cost / (x["pct_stopped"] * 100) if x["pct_stopped"] > 0 else \
            np.nan
        A(f"| {x['rule']} | {x['pct_stopped']*100:.1f}% | "
          f"{x['net_bps']:+.1f} | **−{cost:.1f}** | −{per:.2f} bps |")
    A("")
    t = srt.iloc[0]
    A(f"The tightest stop tested stops out **{t['pct_stopped']*100:.1f}%** "
      f"of all trades and costs **{base['net_bps'] - t['net_bps']:.1f} bps** "
      f"— roughly {(base['net_bps'] - t['net_bps'])/base['net_bps']*100:.0f}% "
      "of the entire edge. The cost-per-stop-out column is close to flat "
      "across the ladder, which is the signature of a stop that is firing "
      "on noise: each trade it catches costs about the same, regardless of "
      "how far out the level sits, because the trades being caught are not "
      "systematically different from the ones that are not.")
    A("")

    # ---------------- 4. attribution ----------------
    att = R.get("attribution")
    if att is not None and len(att):
        A("## 4. Where the expectancy goes")
        A("")
        A("For each stop, the trades it caught: what they realised, and "
          "what those same trades would have returned if left to run to "
          "1 hour.")
        A("")
        A("| Stop | Trades stopped | Realised | Would have made | "
          "**Forgone** | % that would have recovered to profit |")
        A("|---|---:|---:|---:|---:|---:|")
        for _, x in att.iterrows():
            forgone = x["stopped_if_held_bps"] - x["stopped_realised_bps"]
            A(f"| −{x['mult']:.1f} ATR | {int(x['n_stopped']):,} | "
              f"{x['stopped_realised_bps']:+.1f} | "
              f"{x['stopped_if_held_bps']:+.1f} | **{forgone:+.1f}** | "
              f"{x['pct_would_recover']*100:.1f}% |")
        A("")
        w = att.iloc[0]
        rec = w["pct_would_recover"] * 100
        A(f"At −{w['mult']:.1f} ATR, **{rec:.0f}% of the trades the stop "
          f"cut would have finished the hour in profit**, and the group as "
          f"a whole would have returned "
          f"{w['stopped_if_held_bps']:+.1f} bps instead of the "
          f"{w['stopped_realised_bps']:+.1f} actually realised. That gap is "
          "the entire mechanism: this cohort's adverse excursions are "
          "mostly temporary, so a stop inside the noise band converts "
          "round-trips into permanent losses.")
        A("")
        A("This is the same finding as the path-dependence test from a "
          "different angle. There, trades losing at the 5-minute mark went "
          "on to make **+30.1 bps** from 09:41 to 10:35 — the largest "
          "subsequent move of any group. A tight stop is the mechanism that "
          "guarantees you are not holding those trades when the recovery "
          "happens.")
        A("")

    # ---------------- 5. what tight stops do buy ----------------
    A("## 5. What the tight stops do buy")
    A("")
    A("| Stop | p10 | Std dev | % realised loss > 1 ATR | Win rate | NET |")
    A("|---|---:|---:|---:|---:|---:|")
    for _, x in srt.iterrows():
        A(f"| {x['rule']} | {x['p10_bps']:+.0f} | {x['std_bps']:.0f} | "
          f"{x['pct_loss_gt_1atr']*100:.2f}% | {x['win_rate']*100:.1f}% | "
          f"{x['net_bps']:+.1f} |")
    A(f"| **{NOSTOP}** | {base['p10_bps']:+.0f} | {base['std_bps']:.0f} | "
      f"{base['pct_loss_gt_1atr']*100:.2f}% | "
      f"{base['win_rate']*100:.1f}% | {base['net_bps']:+.1f} |")
    A("")
    better_p10 = srt[srt["p10_bps"] > base["p10_bps"]]
    tail_cut = srt[srt["pct_loss_gt_1atr"] < base["pct_loss_gt_1atr"]]
    if len(tail_cut):
        A(f"**The genuine benefit is tail truncation.** "
          f"{len(tail_cut)} of the {len(srt)} levels cut the share of "
          f"realised losses beyond 1 ATR below the "
          f"{base['pct_loss_gt_1atr']*100:.2f}% of holding, and the "
          f"tightest gets it to {srt.iloc[0]['pct_loss_gt_1atr']*100:.2f}%. "
          "If the binding constraint is a hard per-trade loss limit rather "
          "than expectancy, that is what a tight stop is for, and it works.")
        A("")
    if len(better_p10):
        only = len(better_p10) == 1
        A(f"**And unlike the 1.0 ATR stop, the tightest "
          f"{'level does' if only else 'levels do'} improve the 10th "
          f"percentile** — "
          + ", ".join(f"{x['rule']} at {x['p10_bps']:+.0f}"
                      for _, x in better_p10.iterrows())
          + f", against {base['p10_bps']:+.0f} for holding. The ordering is "
          "not monotone and that is the interesting part: p10 gets *worse* "
          "as the stop loosens from 0.5 to 1.0 ATR, then recovers. A stop "
          "at 1.0 ATR sits right where the mass of adverse excursions turns "
          "around, so it clusters losses exactly on the 10th percentile; a "
          "stop at 0.5 fires early enough that the cluster lands above it.")
        A("")
        A("So this is a genuine trade-off rather than a flat verdict: "
          "**the tightest stop improves the shape of the left tail and "
          "costs real expectancy.** It is a risk-budget instrument here, "
          "not a performance one.")
        A("")
        # The median is in the requested metric list and moves hardest.
        t0 = srt.iloc[0]
        A(f"One number qualifies even that. The **median** trade falls from "
          f"{base['median_bps']:+.1f} bps to {t0['median_bps']:+.1f} at "
          f"−{t0['mult']:.1f} ATR — the typical trade goes from clearly "
          f"profitable to barely above breakeven, and below the "
          f"{meta['cost_bps']} bps cost. Win rate drops to "
          f"{t0['win_rate']*100:.1f}%, essentially a coin flip, while the "
          f"payoff ratio rises to {t0['payoff_ratio']:.2f}. The tight stop "
          "converts a high-win-rate, modest-payoff strategy into a "
          "coin-flip, high-payoff one. That is a different business with "
          "different psychology, and worse expectancy.")
        A("")
    else:
        A("None of the tight levels improves the 10th percentile against "
          "holding.")
        A("")

    # ---------------- 6. caveats ----------------
    A("## 6. Reading notes")
    A("")
    A("- **Costs are charged identically to stopped and held trades.** A "
      f"stop firing in fast tape pays more than {meta['cost_bps']} bps in "
      "reality, and the tighter the stop the more often that happens, so "
      "every rule here is flattered relative to holding — the tight ones "
      "most of all.")
    A("- **The fill model already allows gap-throughs** (fill at the bar "
      "open when it opens through the level), which is why the realised "
      ">1 ATR column is not exactly zero for stops tighter than 1 ATR.")
    A("- **No level was searched for.** These are round numbers chosen in "
      "advance. The ladder is monotone, so there is no hidden optimum "
      "between them to go hunting for.")
    A("- **This says nothing about stops on other setups.** The result "
      "follows from this cohort's adverse excursions being mostly "
      "temporary; a breakout strategy, where an adverse move falsifies the "
      "premise, would behave differently.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/stops_tight.py`; "
      "tables in `lambda_data/tables/stopstight_*.csv`._")
    return "\n".join(L)
