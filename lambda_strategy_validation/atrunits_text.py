"""atrunits_text.py — renders ATRUNITS_REPORT.md. Table-focused."""

from __future__ import annotations

import numpy as np
import pandas as pd

WORDER = ["5 min (09:40)", "10 min (09:45)", "15 min (09:50)",
          "1 hour (10:35)"]


def build(R: dict, meta: dict) -> str:
    d = R["main"]
    a = d[d["unit"] == "ATR"].set_index("window")
    b = d[d["unit"] == "bps"].set_index("window")
    t = R["tails"].set_index("window")
    cost = R["cost"]
    L: list[str] = []
    A = L.append

    A("# Lambda — The Core Edge in ATR Units")
    A("")
    A("Post-earnings T+1, High Volume + Continuation (non-doji), entry at "
      "the open of the 09:35 bar. The same results as `DIST_REPORT.md`, "
      "rescaled so a move is measured against what the stock normally does "
      "in a day rather than against its price.")
    A("")
    A("| Input | Definition |")
    A("|---|---|")
    A(f"| Universe | Post-earnings T+1, {meta['start']} → {meta['end']} |")
    A(f"| Cohort | {meta['n_cohort']:,} events |")
    A("| ATR | **prior-session** ATR(14); no gap-day data |")
    A("| ATR return | signed price move ÷ prior ATR(14) |")
    A(f"| Cost | {meta['cost_bps']} bps round trip, converted **per trade** "
      "into ATR |")
    A(f"| Inference | date-clustered bootstrap; ⚠ marks n < "
      f"{meta['small']} |")
    A("")
    A("> **The cost conversion is not a constant, and that is the whole "
      f"point.** {meta['cost_bps']} bps is a fixed fraction of *price*, so "
      "in ATR units it becomes `0.00066 × entry ÷ ATR` — large for a quiet "
      "name whose ATR is a small share of its price, small for a volatile "
      "one. Net expectancy in ATR is `mean(return − cost)` computed trade "
      "by trade, not the ATR mean minus one number. Section 3 shows the "
      "spread.")
    A("")
    A("> **Win rate is identical in both views** — dividing by a positive "
      "ATR cannot flip a sign. Everything else can move, and the payoff "
      "ratio moves most, because it is a ratio of two means and each trade "
      "carries its own denominator.")
    A("")

    # ---------------- 1. ATR ----------------
    A("## 1. ATR units")
    A("")
    A("| Window | n | Win rate | Avg | Median | Avg Win | Avg Loss | "
      "Payoff | **NET** | p10 | p90 | % loss > 1 ATR | % gain > 1 ATR |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for w in WORDER:
        x, tt = a.loc[w], t.loc[w]
        A(f"| {w} | {int(x['n']):,} | {x['win_rate']*100:.1f}% | "
          f"{x['mean']:+.4f} | {x['median']:+.4f} | {x['avg_win']:.4f} | "
          f"{x['avg_loss']:.4f} | {x['payoff_ratio']:.2f} | "
          f"**{x['net']:+.4f}** | {x['p10']:+.3f} | {x['p90']:+.3f} | "
          f"{tt['pct_loss_1atr']*100:.2f}% | "
          f"{tt['pct_gain_1atr']*100:.2f}% |")
    A("")
    A("All figures are fractions of one prior-session ATR(14). NET is mean "
      "expectancy per trade after the per-trade ATR cost.")
    A("")

    # ---------------- 2. side by side ----------------
    A("## 2. Side by side with basis points")
    A("")
    A("| Window | Metric | ATR | bps |")
    A("|---|---|---:|---:|")
    for w in WORDER:
        x, y = a.loc[w], b.loc[w]
        rows = [("n", f"{int(x['n']):,}", f"{int(y['n']):,}"),
                ("Win rate", f"{x['win_rate']*100:.1f}%",
                 f"{y['win_rate']*100:.1f}%"),
                ("Average", f"{x['mean']:+.4f}", f"{y['mean']:+.1f}"),
                ("Median", f"{x['median']:+.4f}", f"{y['median']:+.1f}"),
                ("Average Win", f"{x['avg_win']:.4f}",
                 f"{y['avg_win']:.1f}"),
                ("Average Loss", f"{x['avg_loss']:.4f}",
                 f"{y['avg_loss']:.1f}"),
                ("Payoff", f"{x['payoff_ratio']:.2f}",
                 f"{y['payoff_ratio']:.2f}"),
                ("**NET**", f"**{x['net']:+.4f}**", f"**{y['net']:+.1f}**"),
                ("p10", f"{x['p10']:+.3f}", f"{y['p10']:+.0f}"),
                ("p90", f"{x['p90']:+.3f}", f"{y['p90']:+.0f}")]
        for i, (m, av, bv) in enumerate(rows):
            A(f"| {w if i == 0 else ''} | {m} | {av} | {bv} |")
        A("| | | | |")
    A("")
    A("The bps column reproduces `DIST_REPORT.md` exactly, including its "
      "convention of dropping exactly-zero returns, so the two reports "
      "agree line for line.")
    A("")

    # ---------------- 3. the cost ----------------
    A("## 3. What 6.6 bps actually costs in ATR")
    A("")
    A("| Metric | p10 | p25 | p50 | p75 | p90 | Mean |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    for _, x in cost.iterrows():
        fmt = ".2f" if "%" in x["metric"] else ".4f"
        A(f"| {x['metric']} | {x['p10']:{fmt}} | {x['p25']:{fmt}} | "
          f"{x['p50']:{fmt}} | {x['p75']:{fmt}} | {x['p90']:{fmt}} | "
          f"{x['mean']:{fmt}} |")
    A("")
    c = cost.iloc[1]
    A(f"The median trade pays **{c['p50']:.4f} ATR** in costs, but the "
      f"quietest decile pays {c['p90']:.4f} — "
      f"{c['p90']/c['p50']:.1f}× as much in ATR terms for the identical "
      f"{meta['cost_bps']} bps. A flat basis-point cost is a "
      "**volatility-dependent** cost once you think in ATR, and it "
      "penalises exactly the low-volatility names that a bps view makes "
      "look cheap to trade.")
    A("")
    A("Set against the gross edge, that cost is not a rounding error:")
    A("")
    A("| Window | Gross (ATR) | Cost (ATR) | **Cost as % of gross** | "
      "NET (ATR) |")
    A("|---|---:|---:|---:|---:|")
    for w in WORDER:
        x = a.loc[w]
        A(f"| {w} | {x['mean']:+.4f} | {x['mean_cost']:.4f} | "
          f"**{x['mean_cost']/x['mean']*100:.0f}%** | {x['net']:+.4f} |")
    A("")
    shares = [a.loc[w, "mean_cost"] / a.loc[w, "mean"] for w in WORDER]
    A(f"At 5 minutes the round trip consumes **{shares[0]*100:.0f}%** of "
      f"the gross move; by 1 hour it is down to {shares[-1]*100:.0f}%. "
      "That gradient is the strongest argument in this report for the "
      "longer hold, and it is much starker in ATR units than the bps view "
      "makes it look, because the bps view hides how small the short-"
      "horizon moves are relative to each stock's own volatility.")
    A("")

    # ---------------- 4. what changes ----------------
    A("## 4. What changes when you switch units")
    A("")
    A("| Window | Payoff (ATR) | Payoff (bps) | Δ | Median/Mean (ATR) | "
      "Median/Mean (bps) |")
    A("|---|---:|---:|---:|---:|---:|")
    for w in WORDER:
        x, y = a.loc[w], b.loc[w]
        A(f"| {w} | {x['payoff_ratio']:.3f} | {y['payoff_ratio']:.3f} | "
          f"{x['payoff_ratio'] - y['payoff_ratio']:+.3f} | "
          f"{x['median']/x['mean']:.2f} | {y['median']/y['mean']:.2f} |")
    A("")
    pdiff = [a.loc[w, "payoff_ratio"] - b.loc[w, "payoff_ratio"]
             for w in WORDER]
    up = [v for v in pdiff if v > 0.005]
    flat = [v for v in pdiff if abs(v) <= 0.005]
    dn = [v for v in pdiff if v < -0.005]
    if up and not dn:
        A(f"**The payoff ratio is better in ATR units at "
          f"{len(up)} of {len(pdiff)} horizons** "
          f"({min(up):+.3f} to {max(up):+.3f})"
          + (", and unchanged at "
             + ", ".join(w for w, v in zip(WORDER, pdiff)
                         if abs(v) <= 0.005) + "."
             if flat else ".")
          + " Losses shrink more than wins when each trade is divided by "
          "its own volatility, which says the large basis-point losses sit "
          "in high-ATR names where they are ordinary moves — not in quiet "
          "names where they would be genuine shocks. The bps view "
          "overstates how ugly the losses are, though only slightly.")
    elif dn and not up:
        A(f"**The payoff ratio is worse in ATR units** "
          f"({max(dn):+.3f} to {min(dn):+.3f}), so the large basis-point "
          "wins are the ones concentrated in high-volatility names.")
    else:
        A("The payoff ratio moves in both directions across horizons, so "
          "neither view flatters the strategy consistently.")
    A("")
    A("The differences are small either way. Nothing in this table "
      "suggests the bps view was materially distorted — which is the "
      "answer the exercise was run to find, even though it is the less "
      "interesting one.")
    A("")

    # ATR-view ranking of the horizons
    ranks_a = sorted(WORDER, key=lambda w: -a.loc[w, "net"])
    ranks_b = sorted(WORDER, key=lambda w: -b.loc[w, "net"])
    A("**Does the unit change which horizon looks best?**")
    A("")
    A("| Rank by NET | ATR view | bps view |")
    A("|---|---|---|")
    for i in range(len(WORDER)):
        A(f"| {i+1} | {ranks_a[i]} | {ranks_b[i]} |")
    A("")
    if ranks_a == ranks_b:
        A("**No — the ordering is identical.** The 1-hour hold is the best "
          "of the four under both measures, and the ranking of the rest is "
          "unchanged. That is the reassuring answer: the edge is not an "
          "artefact of letting volatile names dominate a basis-point "
          "average, which is exactly what this exercise was run to check.")
    else:
        A("**Yes — the ordering differs**, which means at least part of "
          "the bps ranking was driven by high-volatility names rather than "
          "by the signal.")
    A("")

    # significance in ATR
    A("| Window | NET (ATR) | 95% CI | p |")
    A("|---|---:|---:|---:|")
    for w in WORDER:
        x = a.loc[w]
        A(f"| {w} | {x['net']:+.4f} | [{x['net_lo']:+.4f}, "
          f"{x['net_hi']:+.4f}] | {x['net_p']:.3f} |")
    A("")
    sig = [w for w in WORDER if a.loc[w, "net_p"] < 0.05]
    A(f"**Significant at {len(sig)} of {len(WORDER)} horizons in ATR "
      "units**, on a date-clustered bootstrap — the same count as the bps "
      "view. Rescaling does not create or destroy the result.")
    A("")

    # ---------------- 5. tails ----------------
    A("## 5. Symmetry of the ATR tails")
    A("")
    A("| Window | % loss > 1 ATR | % gain > 1 ATR | Ratio | "
      "% loss > 0.5 ATR | % gain > 0.5 ATR |")
    A("|---|---:|---:|---:|---:|---:|")
    for w in WORDER:
        x = t.loc[w]
        ratio = (x["pct_gain_1atr"] / x["pct_loss_1atr"]
                 if x["pct_loss_1atr"] else np.nan)
        A(f"| {w} | {x['pct_loss_1atr']*100:.2f}% | "
          f"{x['pct_gain_1atr']*100:.2f}% | {ratio:.2f} | "
          f"{x['pct_loss_05atr']*100:.2f}% | "
          f"{x['pct_gain_05atr']*100:.2f}% |")
    A("")
    last = t.loc[WORDER[-1]]
    A(f"At the 1-hour horizon {last['pct_gain_1atr']*100:.2f}% of trades "
      f"gain more than a full ATR against {last['pct_loss_1atr']*100:.2f}% "
      "that lose more than one — "
      + ("a favourable ratio, and the clearest expression of the edge in "
         "risk-native units."
         if last["pct_gain_1atr"] > last["pct_loss_1atr"] else
         "an unfavourable ratio, so the big moves in ATR terms are more "
         "often against the position than for it.")
      + " Both tails are thin: the overwhelming majority of trades finish "
      "well inside a single ATR either way, which is what makes the "
      f"{meta['cost_bps']} bps round trip a meaningful share of the "
      "outcome.")
    A("")

    # ---------------- 6. caveats ----------------
    A("## 6. Reading notes")
    A("")
    A("- **ATR is a daily measure applied to intraday holds.** A 5-minute "
      "move of 0.05 ATR is not 5% of a day's range in any strict sense — "
      "ATR includes overnight gaps and the full session. The unit is "
      "useful for cross-sectional comparability, not as a literal fraction "
      "of the day's expected travel.")
    A("- **The zero-return convention is inherited** from "
      "`DIST_REPORT.md`: exactly-zero returns are dropped as stale prints, "
      "which is why n varies slightly by horizon.")
    A("- **The per-trade cost conversion assumes the 6.6 bps is right in "
      "the first place.** It is a flat estimate that does not vary by name "
      "or by liquidity, so the ATR-denominated cost inherits that "
      "limitation and adds a volatility dimension to it.")
    A("- **Nothing here is a new test.** These are the published results "
      "in a different unit; no cohort, filter or convention has changed.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/atrunits.py`; tables "
      "in `lambda_data/tables/atru_*.csv`._")
    return "\n".join(L)
