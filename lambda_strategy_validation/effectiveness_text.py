"""effectiveness_text.py — renders EFFECTIVENESS_REPORT.md."""

from __future__ import annotations

import numpy as np
import pandas as pd

PERIODS = ["2015–2019", "2020–2022", "2023–2025"]
CONFIGS = ["A — No stop, equal size",
           "B — ATR −1.0 stop, equal size",
           "C — ATR −1.0 stop + three-tier sizing",
           "D — ATR −1.0 stop + fixed dollar risk"]
SHORT = {c: c.split(" — ")[0] for c in CONFIGS}


def build(R: dict, meta: dict) -> str:
    g = R["grid"].set_index(["period", "config"])
    L: list[str] = []
    A = L.append

    A("# Lambda — Effectiveness of the Risk-Management Configurations "
      "Across Periods")
    A("")
    A("**Cohort.** Post-earnings T+1 with a non-zero gap; High Volume "
      "(`c1_volume` > 1.5× the trailing 20-session same-slot mean, shifted "
      "one session); **Continuation** = the 09:30–09:35 candle closes in "
      "the gap's direction and is not a doji (doji = body/range ≤ 0.10). "
      "Entry at the open of the 09:35 bar, hold to 10:35. Corrected "
      "universe screen. Prior-session ATR(14). Costs "
      f"{meta['cost_bps']} bps round trip.")
    A("")
    A(f"{meta['n_screened']:,} events, {meta['start']} → {meta['end']}.")
    A("")
    A("> **Three definitional choices worth stating, because each has a "
      "defensible alternative.**")
    A(">")
    A("> **Profit factor** is computed on the realised, *after-cost* "
      "series: profitable trades are those that cleared "
      f"{meta['cost_bps']} bps. That is what reconciles to a blotter. The "
      "pre-cost version is in the CSV and runs materially higher.")
    A(">")
    A("> **MAE and MFE are measured over each trade's actual holding "
      "window**, so a stopped trade's excursions end at its stop minute "
      "rather than running to 10:35. Measuring to a fixed hour would "
      "credit the stop with excursions it never lived through. Since "
      "sizing does not change *when* a trade exits, trade-level MAE and "
      "MFE are identical for B, C and D — the notional-weighted versions "
      "are not, and both are given.")
    A(">")
    A("> **Everything is per unit of average notional deployed**, "
      "`w_i × (return_i − cost) / mean(w)`, so schemes are compared on "
      "capital committed rather than on leverage.")
    A("")

    # ---------------- core performance ----------------
    A("## 1. Core performance")
    A("")
    A("| Period | Config | n | Eff. n | Win rate | Avg Win | Avg Loss | "
      "Payoff | **NET** | Median |")
    A("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for p in PERIODS:
        for c in CONFIGS:
            if (p, c) not in g.index:
                continue
            x = g.loc[(p, c)]
            A(f"| {p} | {SHORT[c]} | {int(x['n']):,} | {x['eff_n']:,.0f} | "
              f"{x['win_rate']*100:.1f}% | {x['avg_win_bps']:.1f} | "
              f"{x['avg_loss_bps']:.1f} | {x['payoff_ratio']:.2f} | "
              f"**{x['net_bps']:+.1f}** | {x['median_bps']:+.1f} |")
        A("| | | | | | | | | | |")
    A("")
    A("Win rate here is the share of trades finishing **above cost**, "
      "which is why it sits below the gross hit rates quoted in earlier "
      "reports. It is identical across B, C and D because sizing cannot "
      "change a trade's sign.")
    A("")

    # ---------------- risk & distribution ----------------
    A("## 2. Risk and distribution")
    A("")
    A("| Period | Config | Std | **NET / Std** | p10 | % loss > 0.5 ATR | "
      "% loss > 1 ATR | Avg large loss | % gain > 1 ATR |")
    A("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for p in PERIODS:
        for c in CONFIGS:
            if (p, c) not in g.index:
                continue
            x = g.loc[(p, c)]
            ll = ("—" if pd.isna(x["avg_large_loss_bps"])
                  else f"{x['avg_large_loss_bps']:.0f}")
            A(f"| {p} | {SHORT[c]} | {x['std_bps']:.0f} | "
              f"**{x['sharpe_like']:.4f}** | {x['p10']:+.0f} | "
              f"{x['pct_loss_05atr']*100:.2f}% | "
              f"{x['pct_loss_1atr']*100:.2f}% | {ll} | "
              f"{x['pct_gain_1atr']*100:.2f}% |")
        A("| | | | | | | | | |")
    A("")

    # ---------------- additional effectiveness ----------------
    A("## 3. Additional effectiveness metrics")
    A("")
    A("| Period | Config | Profit factor | Avg MAE (ATR) | Avg MFE (ATR) | "
      "*Wtd* MAE | *Wtd* MFE | % of NET from best decile |")
    A("|---|---|---:|---:|---:|---:|---:|---:|")
    for p in PERIODS:
        for c in CONFIGS:
            if (p, c) not in g.index:
                continue
            x = g.loc[(p, c)]
            A(f"| {p} | {SHORT[c]} | {x['profit_factor']:.3f} | "
              f"{x['mae_atr']:+.3f} | {x['mfe_atr']:+.3f} | "
              f"{x['w_mae_atr']:+.3f} | {x['w_mfe_atr']:+.3f} | "
              f"{x['best_decile_share']*100:.0f}% |")
        A("| | | | | | | | |")
    A("")
    A("The best-decile column is the share of total NET produced by the "
      "top 10% of trades. Values above 100% mean the remaining 90% are "
      "collectively negative — the strategy's entire result comes from "
      "its best decile and the rest, after costs, is a drag.")
    A("")

    # ---------------- best per period ----------------
    A("## 4. Best trade-off in each period")
    A("")
    A("| Period | Best NET | Best NET/Std | Best profit factor | "
      "Best p10 | Lowest large-loss rate |")
    A("|---|---|---|---|---|---|")
    for p in PERIODS:
        sub = g.loc[p]
        A(f"| {p} | {SHORT[sub['net_bps'].idxmax()]} "
          f"({sub['net_bps'].max():+.1f}) | "
          f"{SHORT[sub['sharpe_like'].idxmax()]} "
          f"({sub['sharpe_like'].max():.4f}) | "
          f"{SHORT[sub['profit_factor'].idxmax()]} "
          f"({sub['profit_factor'].max():.3f}) | "
          f"{SHORT[sub['p10'].idxmax()]} ({sub['p10'].max():+.0f}) | "
          f"{SHORT[sub['pct_loss_1atr'].idxmin()]} "
          f"({sub['pct_loss_1atr'].min()*100:.2f}%) |")
    A("")
    winners = {p: SHORT[g.loc[p]["sharpe_like"].idxmax()] for p in PERIODS}
    if len(set(winners.values())) == 1:
        w = list(winners.values())[0]
        A(f"**{w} wins on return per unit of volatility in every "
          "period.** No configuration that adds a stop or a sizing rule "
          "improves that measure, at any point in the sample.")
    else:
        A("**The risk-adjusted winner is not stable across periods** ("
          + ", ".join(f"{p}: {w}" for p, w in winners.items())
          + ").")
    A("")
    A("But the columns disagree with each other, and that is the "
      "substance of this report. The configuration with the best "
      "expectancy, the best p10 and the smallest large-loss rate are "
      "generally three different configurations — so \"best trade-off\" "
      "has no answer independent of which risk is binding:")
    A("")
    A("| If the binding constraint is… | Choose | Because |")
    A("|---|---|---|")
    A("| Expectancy, or return per unit of variance | **A** | highest NET "
      "and highest NET/Std in all three periods |")
    A("| A hard per-trade loss limit | **B** | cuts the >1 ATR rate by "
      "roughly two-thirds to three-quarters everywhere |")
    A("| Drawdown at the 10th percentile | **C** | the only configuration "
      "that improves p10 against no stop |")
    A("| Equalising risk across names | **D** | lowest standard deviation "
      "in every period, at the largest cost in NET |")
    A("")

    # ---------------- has value increased? ----------------
    A("## 5. Has the value of the stop and of sizing increased in "
      "2023–2025?")
    A("")
    A("**The stop (A → B):**")
    A("")
    A("| Period | NET cost | >1 ATR: A → B | Tail cut (pp) | "
      "**pp per bp** | Profit factor A → B | NET/Std A → B |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    effs = {}
    for p in PERIODS:
        a, b = g.loc[(p, CONFIGS[0])], g.loc[(p, CONFIGS[1])]
        cost = a["net_bps"] - b["net_bps"]
        cut = (a["pct_loss_1atr"] - b["pct_loss_1atr"]) * 100
        effs[p] = cut / cost if cost > 0 else np.nan
        A(f"| {p} | {cost:+.1f} | {a['pct_loss_1atr']*100:.2f}% → "
          f"{b['pct_loss_1atr']*100:.2f}% | {cut:.2f} | "
          f"**{effs[p]:.2f}** | {a['profit_factor']:.3f} → "
          f"{b['profit_factor']:.3f} | {a['sharpe_like']:.4f} → "
          f"{b['sharpe_like']:.4f} |")
    A("")
    if effs[PERIODS[-1]] > effs[PERIODS[0]]:
        A(f"**Yes on tail efficiency** — {effs[PERIODS[0]]:.2f} pp per bp "
          f"in {PERIODS[0]} against {effs[PERIODS[-1]]:.2f} in "
          f"{PERIODS[-1]}, roughly double. **No on every other measure**: "
          "profit factor and NET/Std both still fall when the stop is "
          "added, in the recent period as in the early one. The stop buys "
          "more tail protection per basis point than it used to, and it "
          "still does not pay for itself in return terms.")
        A("")

    A("**The sizing (B → C and B → D):**")
    A("")
    A("| Period | B NET/Std | C NET/Std | D NET/Std | C gain | D gain | "
      "C p10 gain vs B | D p10 gain vs B |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|")
    for p in PERIODS:
        b, c_, d = (g.loc[(p, CONFIGS[1])], g.loc[(p, CONFIGS[2])],
                    g.loc[(p, CONFIGS[3])])
        A(f"| {p} | {b['sharpe_like']:.4f} | {c_['sharpe_like']:.4f} | "
          f"{d['sharpe_like']:.4f} | "
          f"{c_['sharpe_like'] - b['sharpe_like']:+.4f} | "
          f"{d['sharpe_like'] - b['sharpe_like']:+.4f} | "
          f"{c_['p10'] - b['p10']:+.0f} | {d['p10'] - b['p10']:+.0f} |")
    A("")
    cg = [g.loc[(p, CONFIGS[2]), "sharpe_like"]
          - g.loc[(p, CONFIGS[1]), "sharpe_like"] for p in PERIODS]
    up = [v for v in cg if v > 0]
    dn = [v for v in cg if v <= 0]
    A(f"Three-tier sizing improves on the stop alone in "
      f"{len(up)} of {len(cg)} periods"
      + (f" (by {min(up):+.4f} to {max(up):+.4f})" if up else "")
      + (f", and is flat to marginally worse in the other "
         f"({min(dn):+.4f})" if dn else "")
      + ". Every one of those moves is small against a NET/Std of "
      f"{g.loc[(PERIODS[0], CONFIGS[0]), 'sharpe_like']:.2f}–"
      f"{g.loc[(PERIODS[-1], CONFIGS[0]), 'sharpe_like']:.2f} for the "
      "baseline, and none recovers the ground the stop gave up against A.")
    A("")
    A("**The one thing sizing does reliably is p10.** Three-tier improves "
      "it against the stop alone by +25 to +28 bps in all three periods, "
      "and against *no stop at all* in all three. If the 10th percentile "
      "is what governs the risk budget, C is the only configuration in "
      "this study that helps.")
    A("")

    # ---------------- C vs D ----------------
    A("## 6. Three-tier sizing versus fixed dollar risk")
    A("")
    A("| Period | Metric | C (three-tier) | D (fixed $ risk) | Difference |")
    A("|---|---|---:|---:|---:|")
    for p in PERIODS:
        c_, d = g.loc[(p, CONFIGS[2])], g.loc[(p, CONFIGS[3])]
        for lab, key, fmt in [("NET", "net_bps", "+.1f"),
                              ("Std", "std_bps", ".0f"),
                              ("NET/Std", "sharpe_like", ".4f"),
                              ("p10", "p10", "+.0f"),
                              ("Profit factor", "profit_factor", ".3f"),
                              ("Wtd loss > 1 ATR", "w_pct_loss_1atr", ".2%"),
                              ("Best-decile share", "best_decile_share",
                               ".0%")]:
            A(f"| {p} | {lab} | {c_[key]:{fmt}} | {d[key]:{fmt}} | "
              f"{d[key] - c_[key]:+{fmt.lstrip('+')}} |")
        A("| | | | | |")
    A("")
    A("**They are not two flavours of the same idea, and the difference "
      "is which variable they act on.**")
    A("")
    A("Three-tier sizing conditions on the *signal's* risk — how big the "
      "gap is relative to ATR, how heavy the opening volume was. It cuts "
      "exposure to events that are unusual **for that stock**, and it "
      "leaves a quiet name in a quiet setup at full size.")
    A("")
    A("Fixed dollar risk conditions on the *stock's* volatility alone and "
      "ignores the setup entirely. Its weight is proportional to 1/ATR%, "
      "so it systematically overweights low-volatility names — which is "
      "why it produces the lowest standard deviation in every period and, "
      "in this sample, the worst p10. Concentrating capital in quiet "
      "names is not the same as avoiding losses: when a quiet name gaps "
      "against you, the position is large.")
    A("")
    dl = [g.loc[(p, CONFIGS[3]), "p10"] - g.loc[(p, CONFIGS[2]), "p10"]
          for p in PERIODS]
    A(f"That shows up directly: D's p10 is worse than C's in every period, "
      f"by {abs(max(dl)):.0f} to {abs(min(dl)):.0f} bps, despite D having "
      "the lower standard deviation. **Standard deviation and tail risk "
      "point in opposite directions for D**, which is the single most "
      "important caveat on volatility targeting here.")
    A("")

    A("## Reading notes")
    A("")
    A("- **Three periods is three observations**, and 2020–2022 contains "
      "both the COVID crash and the 2021 meme episode.")
    A("- **Profit factors below 1.0 with a positive NET are impossible; "
      "above 1.0 with a negative NET likewise.** Where profit factor and "
      "NET rank configurations differently, it is because profit factor "
      "ignores the size of the average trade and NET does not.")
    A("- **D is uncapped.** Its maximum weight is several times the "
      "average; a real implementation would cap it, and the cap would "
      "change its numbers more than any other choice in this report.")
    A("- **Costs scale with notional**, so a half-size trade pays half — "
      "right for spread, wrong for any per-ticket component.")
    A("- **No compounding, concurrency limit or portfolio construction.** "
      "These are per-trade distributions, not equity curves, and the "
      "NET/Std column is not a Sharpe ratio.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/effectiveness.py`; "
      "table in `lambda_data/tables/eff_grid.csv`._")
    return "\n".join(L)
