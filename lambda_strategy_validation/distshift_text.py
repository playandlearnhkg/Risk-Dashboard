"""distshift_text.py — renders DISTSHIFT_REPORT.md. Table-focused."""

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
    mix = R["mix"].set_index("period")
    L: list[str] = []
    A = L.append

    A("# Lambda — How the Return Distribution Shifts Across Periods, and "
      "What Stops and Sizing Do To It")
    A("")
    A("**Cohort.** Post-earnings T+1 with a non-zero gap; High Volume "
      "(`c1_volume` > 1.5× the trailing 20-session same-slot mean, shifted "
      "one session); **Continuation** = the 09:30–09:35 candle closes in "
      "the gap's direction and is **not** a doji, where doji means "
      "body/range ≤ 0.10. Entry at the open of the 09:35 bar, hold to "
      "10:35. Corrected universe screen applied. ATR is the prior "
      f"session's ATR(14). Costs {meta['cost_bps']} bps round trip.")
    A("")
    A(f"{meta['n_screened']:,} events, {meta['start']} → {meta['end']}.")
    A("")
    A("> **Everything is per unit of average notional deployed.** For a "
      "weight vector `w` the per-trade series is "
      "`w_i × (return_i − cost) / mean(w)`, so the mean is the return on "
      "capital actually committed and the percentiles describe the P&L a "
      "book of that shape would live through. Without that, a scheme that "
      "merely deploys less capital would look calmer and less profitable "
      "for no reason but leverage.")
    A("")
    A("> **Two versions of \"% losing more than 1 ATR\".** Sizing cannot "
      "change whether a *trade* moved 1 ATR against entry — that is the "
      "price path — so the **trade-count** version is identical for B, C "
      "and D by construction, and only the stop moves it. What sizing "
      "changes is how much capital stood in front of those moves, which "
      "is the **notional-weighted** version. Both are given; reading only "
      "the first would make sizing look inert when it is not.")
    A("")

    # ---------------- per period ----------------
    for p in PERIODS:
        if (p, CONFIGS[0]) not in g.index:
            continue
        m = mix.loc[p]
        A(f"## {p}")
        A("")
        A(f"n = {int(m['n']):,}; the ATR −1.0 stop fires on "
          f"{m['pct_stopped']*100:.1f}% of them. Tier mix: "
          f"{m['pct_high']*100:.1f}% High Risk, {m['pct_med']*100:.1f}% "
          f"Medium, {m['pct_low']*100:.1f}% Low Risk.")
        A("")
        A("| Config | Eff. n | Mean (NET) | Median | Std | p10 | p25 | "
          "p75 | p90 | Skew (w) | Kurt (w) |")
        A("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for c in CONFIGS:
            if (p, c) not in g.index:
                continue
            x = g.loc[(p, c)]
            A(f"| {c} | {x['eff_n']:,.0f} | **{x['mean_bps']:+.1f}** | "
              f"{x['median_bps']:+.1f} | {x['std_bps']:.0f} | "
              f"{x['p10']:+.0f} | {x['p25']:+.0f} | {x['p75']:+.0f} | "
              f"{x['p90']:+.0f} | {x['skew_w']:+.2f} | "
              f"{x['kurtosis_w']:+.1f} |")
        A("")
        A("| Config | % loss > 0.5 ATR | % loss > 1 ATR | % gain > 1 ATR | "
          "*Wtd* loss > 1 ATR | Avg large loss | NET / Std |")
        A("|---|---:|---:|---:|---:|---:|---:|")
        for c in CONFIGS:
            if (p, c) not in g.index:
                continue
            x = g.loc[(p, c)]
            ll = ("—" if pd.isna(x["avg_large_loss_bps"])
                  else f"{x['avg_large_loss_bps']:.0f}")
            A(f"| {c} | {x['pct_loss_05atr']*100:.2f}% | "
              f"{x['pct_loss_1atr']*100:.2f}% | "
              f"{x['pct_gain_1atr']*100:.2f}% | "
              f"{x['w_pct_loss_1atr']*100:.2f}% | {ll} | "
              f"{x['sharpe_like']:.4f} |")
        A("")

    # ---------------- A across periods ----------------
    A("## The baseline distribution, period by period")
    A("")
    A("| Period | Mean | Median | Std | p10 | p90 | Skew (w) | Kurt (w) | "
      "% loss > 0.5 ATR | % loss > 1 ATR | % gain > 1 ATR |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for p in PERIODS:
        if (p, CONFIGS[0]) not in g.index:
            continue
        x = g.loc[(p, CONFIGS[0])]
        A(f"| {p} | **{x['mean_bps']:+.1f}** | {x['median_bps']:+.1f} | "
          f"{x['std_bps']:.0f} | {x['p10']:+.0f} | {x['p90']:+.0f} | "
          f"{x['skew_w']:+.2f} | {x['kurtosis_w']:+.1f} | "
          f"{x['pct_loss_05atr']*100:.2f}% | "
          f"{x['pct_loss_1atr']*100:.2f}% | "
          f"{x['pct_gain_1atr']*100:.2f}% |")
    A("")
    e, r_ = g.loc[(PERIODS[0], CONFIGS[0])], g.loc[(PERIODS[-1], CONFIGS[0])]
    A(f"**The distribution has widened on both sides, and moved left on "
      f"net.** p10 goes from {e['p10']:+.0f} to {r_['p10']:+.0f} while p90 "
      f"goes from {e['p90']:+.0f} to {r_['p90']:+.0f}; the >1 ATR loss "
      f"rate rises {e['pct_loss_1atr']*100:.2f}% → "
      f"{r_['pct_loss_1atr']*100:.2f}% and the >1 ATR gain rate "
      f"{e['pct_gain_1atr']*100:.2f}% → {r_['pct_gain_1atr']*100:.2f}%. "
      "This is not a pure left-tail story — both tails are fatter — but "
      "the left one grew by more relative to where it started, and the "
      f"mean fell {e['mean_bps'] - r_['mean_bps']:.1f} bps.")
    A("")
    A("**Much of that is a change in what the setup is catching, not a "
      "change in how it performs.** The cohort's own composition shifted:")
    A("")
    A("| Period | n | % High Risk | % Low Risk | Median Gap/ATR | "
      "Median vol ratio | % stopped by ATR −1.0 |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    for p in PERIODS:
        if p not in mix.index:
            continue
        x = mix.loc[p]
        A(f"| {p} | {int(x['n']):,} | {x['pct_high']*100:.1f}% | "
          f"{x['pct_low']*100:.1f}% | {x['median_gap_atr']:.2f} | "
          f"{x['median_vol_ratio']:.2f} | {x['pct_stopped']*100:.1f}% |")
    A("")
    m0, m2 = mix.loc[PERIODS[0]], mix.loc[PERIODS[-1]]
    A(f"The High Risk share goes from {m0['pct_high']*100:.1f}% to "
      f"{m2['pct_high']*100:.1f}%, the median gap from "
      f"{m0['median_gap_atr']:.2f} to {m2['median_gap_atr']:.2f} ATR and "
      f"the median volume ratio from {m0['median_vol_ratio']:.2f}× to "
      f"{m2['median_vol_ratio']:.2f}×. The recent cohort is a "
      "structurally more violent set of events passing the same filter — "
      "which explains the fatter tails on **both** sides without needing "
      "the edge itself to have decayed as much as the headline mean "
      "suggests.")
    A("")

    # ---------------- left tail A -> D ----------------
    A("## How the left tail moves from A → B → C → D")
    A("")
    A("| Period | Metric | A | B | C | D | A → D |")
    A("|---|---|---:|---:|---:|---:|---:|")
    for p in PERIODS:
        if (p, CONFIGS[0]) not in g.index:
            continue
        for lab, key, fmt, pct in [
            ("p10", "p10", "+.0f", False),
            ("% loss > 1 ATR (trades)", "pct_loss_1atr", ".2f", True),
            ("% loss > 1 ATR (notional)", "w_pct_loss_1atr", ".2f", True),
            ("Avg large loss", "avg_large_loss_bps", ".0f", False),
            ("Std dev", "std_bps", ".0f", False),
        ]:
            vals = []
            for c in CONFIGS:
                v = g.loc[(p, c), key]
                vals.append(v * 100 if pct else v)
            suffix = "%" if pct else ""
            delta = vals[-1] - vals[0]
            A(f"| {p} | {lab} | "
              + " | ".join(f"{v:{fmt}}{suffix}" for v in vals)
              + f" | {delta:+{fmt.lstrip('+')}}{suffix} |")
        A("| | | | | | | |")
    A("")

    # narrative per period
    for p in PERIODS:
        if (p, CONFIGS[0]) not in g.index:
            continue
        a, b = g.loc[(p, CONFIGS[0])], g.loc[(p, CONFIGS[1])]
        c_, d = g.loc[(p, CONFIGS[2])], g.loc[(p, CONFIGS[3])]
        p10_dir = ("lifts" if b["p10"] > a["p10"] else "**worsens**")
        A(f"**{p}.** The stop alone (A→B) cuts the >1 ATR loss rate from "
          f"{a['pct_loss_1atr']*100:.2f}% to {b['pct_loss_1atr']*100:.2f}% "
          f"but {p10_dir} p10, from {a['p10']:+.0f} to {b['p10']:+.0f}, at "
          f"a cost of {a['mean_bps'] - b['mean_bps']:.1f} bps of mean. "
          f"Adding sizing (B→C) moves the notional-weighted large-loss "
          f"exposure from {b['w_pct_loss_1atr']*100:.2f}% to "
          f"{c_['w_pct_loss_1atr']*100:.2f}% and the standard deviation "
          f"from {b['std_bps']:.0f} to {c_['std_bps']:.0f}; "
          f"volatility targeting (D) takes them to "
          f"{d['w_pct_loss_1atr']*100:.2f}% and {d['std_bps']:.0f}. "
          f"Risk-adjusted, the four run "
          + " / ".join(f"{g.loc[(p, c), 'sharpe_like']:.4f}"
                       for c in CONFIGS) + ".")
        A("")

    # ---------------- is it worth more recently? ----------------
    A("## Are the stop and the sizing worth more in 2023–2025?")
    A("")
    A("| Period | A mean | B mean | Stop cost | A p10 | B p10 | p10 change "
      "| Tail cut (pp) | **pp per bp** |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    effs = {}
    for p in PERIODS:
        if (p, CONFIGS[0]) not in g.index:
            continue
        a, b = g.loc[(p, CONFIGS[0])], g.loc[(p, CONFIGS[1])]
        cost = a["mean_bps"] - b["mean_bps"]
        cut = (a["pct_loss_1atr"] - b["pct_loss_1atr"]) * 100
        eff = cut / cost if cost > 0 else np.nan
        effs[p] = eff
        A(f"| {p} | {a['mean_bps']:+.1f} | {b['mean_bps']:+.1f} | "
          f"{cost:+.1f} | {a['p10']:+.0f} | {b['p10']:+.0f} | "
          f"{b['p10'] - a['p10']:+.0f} | {cut:.2f} | **{eff:.2f}** |")
    A("")
    if len(effs) == 3 and effs[PERIODS[-1]] > effs[PERIODS[0]]:
        A(f"**Yes for the stop.** Its efficiency rises from "
          f"{effs[PERIODS[0]]:.2f} pp per bp in {PERIODS[0]} to "
          f"{effs[PERIODS[-1]]:.2f} in {PERIODS[-1]} — it removes more "
          "tail and charges less for it, because there is less expectancy "
          "left to give up and more tail to remove. That is the same "
          "conclusion `REGIME_REPORT.md` reached, now visible in the shape "
          "of the distribution rather than only in the summary "
          "statistics.")
        A("")
    A("| Period | Best NET/Std | Config | Equal-size (B) NET/Std | Gain |")
    A("|---|---:|---|---:|---:|")
    for p in PERIODS:
        if (p, CONFIGS[0]) not in g.index:
            continue
        sub = {c: g.loc[(p, c), "sharpe_like"] for c in CONFIGS}
        bc = max(sub, key=sub.get)
        A(f"| {p} | {sub[bc]:.4f} | {SHORT[bc]} | "
          f"{sub[CONFIGS[1]]:.4f} | "
          f"{sub[bc] - sub[CONFIGS[1]]:+.4f} |")
    A("")
    wins = [max({c: g.loc[(p, c), "sharpe_like"] for c in CONFIGS},
                key=lambda c: g.loc[(p, c), "sharpe_like"])
            for p in PERIODS if (p, CONFIGS[0]) in g.index]
    if all(w == wins[0] for w in wins):
        A(f"**{SHORT[wins[0]]} is the best risk-adjusted configuration in "
          "all three periods**, which is at least consistent across time "
          "even if the margins are narrow.")
        if wins[0] == CONFIGS[0]:
            A("")
            A("**These two results are not in conflict, and the "
              "distinction matters.** The stop's *tail efficiency* "
              "genuinely improves in the recent period — it removes more "
              "of the >1 ATR tail per basis point surrendered than it "
              "used to. But it still does not improve *return per unit of "
              "total volatility*, in any period, because the volatility "
              "it removes is concentrated in a tail that contributes "
              "little to the standard deviation, while the expectancy it "
              "removes comes straight off the mean.")
            A("")
            A("So the honest answer depends on which risk you are "
              "managing. If the constraint is a per-trade loss limit or a "
              "drawdown tolerance driven by extremes, the stop is worth "
              "more now than it has ever been in this data. If the "
              "objective is return per unit of variance, no stop and "
              "equal size still wins, in 2023–2025 as in 2015–2019.")
    else:
        A("**The best risk-adjusted configuration is not stable across "
          "periods** ("
          + ", ".join(f"{p}: {SHORT[w]}" for p, w in zip(PERIODS, wins))
          + "), which is a reason to distrust any of the margins as a "
          "guide to what to run.")
    A("")

    # ---------------- right tail / shape ----------------
    A("## Effect on the right tail and overall shape")
    A("")
    A("| Period | Config | p90 | % gain > 1 ATR | *Wtd* gain > 1 ATR | "
      "Skew (w) | Kurt (w) |")
    A("|---|---|---:|---:|---:|---:|---:|")
    for p in PERIODS:
        if (p, CONFIGS[0]) not in g.index:
            continue
        for c in CONFIGS:
            x = g.loc[(p, c)]
            A(f"| {p} | {SHORT[c]} | {x['p90']:+.0f} | "
              f"{x['pct_gain_1atr']*100:.2f}% | "
              f"{x['w_pct_gain_1atr']*100:.2f}% | {x['skew_w']:+.2f} | "
              f"{x['kurtosis_w']:+.1f} |")
        A("| | | | | | | |")
    A("")
    same = []
    for p in PERIODS:
        if (p, CONFIGS[0]) not in g.index:
            continue
        a, b = g.loc[(p, CONFIGS[0])], g.loc[(p, CONFIGS[1])]
        same.append(abs(a["pct_gain_1atr"] - b["pct_gain_1atr"]) * 100)
    A(f"**The stop barely touches the right tail** — the >1 ATR gain rate "
      f"moves by {min(same):.2f} to {max(same):.2f} pp between A and B, "
      "because a stop can only fire on an adverse excursion and the "
      "trades that ran never came near it. The p90 column says the same "
      "thing. This is the one respect in which the ATR stop is a clean "
      "instrument: it truncates one side of the distribution and leaves "
      "the other essentially intact.")
    A("")
    A("Sizing is different, and the notional-weighted gain column shows "
      "why. Scheme C deliberately holds less of the High Risk tier, and "
      "that tier owns a disproportionate share of the large winners as "
      "well as the large losers — so C's weighted upside exposure falls "
      "alongside its weighted downside. Volatility targeting (D) does the "
      "same thing more smoothly and more aggressively, which is why it "
      "compresses the standard deviation most and the mean with it.")
    A("")

    # ---------------- caveats ----------------
    A("## Reading notes")
    A("")
    A("- **Three periods is three observations.** The 2020–2022 block "
      "contains both the COVID crash and the 2021 meme episode; it is not "
      "a regime so much as two unrepeatable events sharing a bucket.")
    A("- **Winsorised skew and kurtosis at 1/99** are shown as the primary "
      "shape statistics. Raw values are carried in the CSVs and are "
      "dominated by single observations, which makes them useless for "
      "comparing periods.")
    A("- **The tier thresholds and the 1.25/1.0/0.5 weights were not "
      "fitted**, but they were chosen after seeing earlier segment "
      "tables, which is weaker than choosing them in advance.")
    A("- **Scheme D is uncapped.** Its weight is proportional to 1/ATR%, "
      "so the quietest names attract multiples of the average position. "
      "A real implementation caps that, and the cap would change its "
      "numbers here.")
    A("- **Costs scale with notional**, so a half-size trade pays half. "
      "That is right for a spread-driven cost and wrong for any fixed "
      "per-ticket component.")
    A("- **No compounding, no concurrency limit, no portfolio "
      "construction.** These are per-trade distributions, not equity "
      "curves.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/distshift.py`; "
      "tables in `lambda_data/tables/ds_*.csv`._")
    return "\n".join(L)
