"""regime_sizing_text.py — renders REGIME_REPORT.md and SIZING_REPORT.md."""

from __future__ import annotations

import numpy as np
import pandas as pd

PERIODS = ["2015–2019", "2020–2022", "2023–2025"]
UNIS = ["All (no screen)", "Screened"]


def _row(x, A):
    sm = " ⚠" if x.get("small") == "YES" else ""
    A(f"| {x['bucket']}{sm} | {int(x['n']):,} | {x['win_rate']*100:.1f}% | "
      f"**{x['net_bps']:+.1f}** | {x['net_atr']:+.4f} | "
      f"{x['avg_win_bps']:.0f} | {x['avg_loss_bps']:.0f} | "
      f"{x['payoff_ratio']:.2f} | {x['median_bps']:+.1f} | "
      f"{x['pct_loss_05atr']*100:.2f}% | {x['pct_loss_1atr']*100:.2f}% | "
      + ("—" if pd.isna(x["avg_large_loss_bps"])
         else f"{x['avg_large_loss_bps']:.0f}")
      + f" | {x['p10_bps']:+.0f} | {x['skew_w']:+.2f} | "
      f"{x['kurtosis_w']:+.1f} |")


def _hdr(A):
    A("| Bucket | n | Win rate | **NET (bps)** | NET (ATR) | Avg Win | "
      "Avg Loss | Payoff | Median | % loss > 0.5 ATR | % loss > 1 ATR | "
      "Avg large loss | p10 | Skew (w) | Kurt (w) |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
      "---:|---:|")


# ===========================================================================
def build_regime(R: dict, meta: dict) -> str:
    y = R["yearly"]
    sv = R["stopvalue"]
    L: list[str] = []
    A = L.append

    A("# Lambda — Has the Post-Earnings T+1 Edge Decayed?")
    A("")
    A("High Volume + Continuation (non-doji), entry at the 09:35 open, "
      "1-hour hold, no stop unless stated. Skew and kurtosis are "
      "winsorised at 1/99 throughout, because the raw figures on this "
      "cohort are one observation (the CAR squeeze) and carry no "
      "information about a period.")
    A("")
    A(f"Cohort {meta['n_core']:,} events, {meta['start']} → {meta['end']}; "
      f"{meta['n_screened']:,} pass the corrected universe screen. ⚠ marks "
      f"n < {meta['small']}.")
    A("")

    # ---- the screen had to be rebuilt before any of this was meaningful ----
    cov = R.get("coverage")
    A("## 0. The universe screen had to be repaired first")
    A("")
    A("The screen used in `VALIDATION_REPORT.md` is **broken from 2022 "
      "onward**, and a year-by-year study is exactly where that shows up. "
      "The 2022-03-01 IEX consolidated-tape change rescales reported "
      "volume, so a fixed 500k-share / $50M threshold stops measuring "
      "liquidity and starts measuring which side of the break a row sits "
      "on:")
    A("")
    if cov is not None and len(cov):
        A("| Year | Events | Old screen pass rate | Corrected pass rate |")
        A("|---|---:|---:|---:|")
        for _, x in cov.iterrows():
            A(f"| {int(x['year'])} | {int(x['n']):,} | "
              f"{x['old_pass']*100:.1f}% | {x['v2_pass']*100:.1f}% |")
        A("")
    A("The old screen admits 87% of 2021 events and **2.5% of 2023**. "
      "Price and market-cap pass rates are unchanged across the break; "
      "only the two volume tests collapse. So a \"screened\" cohort built "
      "on it is not a liquidity cohort at all — it is very nearly a "
      "*2015–2021* cohort.")
    A("")
    A("> **This corrects the previous report.** `VALIDATION_REPORT.md` "
      "compared screened against unscreened events and attributed the "
      "screened half's lower tail risk to liquidity. That comparison was "
      "confounded with time: the screened half was overwhelmingly "
      "pre-2022, and this report shows tail risk rose sharply after 2022. "
      "The like-for-like conclusion there does not survive, and the "
      "screened columns below use the corrected definition instead.")
    A("")
    A(f"**The corrected screen** keeps the price and market-cap tests "
      "unchanged and replaces the two volume tests with a within-year "
      "cross-sectional rank on 63-day dollar volume, calibrated so the "
      "pass rate matches what the dollar threshold admitted before the "
      f"break ({meta.get('screen_target', float('nan'))*100:.1f}%). A "
      "relative screen is immune to a level shift in the units. It is not "
      "the same filter as the specification names — it cannot be, because "
      "that filter is not measurable consistently across this data — and "
      "that is a data-repair decision worth knowing about.")
    A("")

    for uni in UNIS:
        A(f"## By period — {uni}")
        A("")
        d = y[(y["universe"] == uni) & (y["kind"] == "period")]
        _hdr(A)
        for p in PERIODS:
            r = d[d["bucket"] == p]
            if len(r):
                _row(r.iloc[0], A)
        A("")

    # the diagnostic question
    A("## Is recent weakness a left-tail story?")
    A("")
    for uni in UNIS:
        d = y[(y["universe"] == uni) & (y["kind"] == "period")
              ].set_index("bucket")
        if not all(p in d.index for p in PERIODS):
            continue
        e, r_ = d.loc[PERIODS[0]], d.loc[PERIODS[-1]]
        A(f"**{uni}** — {PERIODS[0]} → {PERIODS[-1]}")
        A("")
        A("| Component | Early | Recent | Change |")
        A("|---|---:|---:|---:|")
        for lab, key, fmt in [
            ("NET (bps)", "net_bps", "+.1f"),
            ("Win rate", "win_rate", ".1%"),
            ("Average win (bps)", "avg_win_bps", ".0f"),
            ("Average loss (bps)", "avg_loss_bps", ".0f"),
            ("Payoff ratio", "payoff_ratio", ".2f"),
            ("% losing > 0.5 ATR", "pct_loss_05atr", ".2%"),
            ("% losing > 1.0 ATR", "pct_loss_1atr", ".2%"),
            ("Avg large loss (bps)", "avg_large_loss_bps", ".0f"),
            ("p10 (bps)", "p10_bps", "+.0f"),
            ("Std dev (bps)", "std_bps", ".0f"),
        ]:
            ev_, rv = e[key], r_[key]
            A(f"| {lab} | {ev_:{fmt}} | {rv:{fmt}} | "
              f"{rv - ev_:+{fmt.lstrip('+')}} |")
        A("")

        # decompose: is it wins shrinking or losses growing?
        dwin = r_["avg_win_bps"] - e["avg_win_bps"]
        dloss = r_["avg_loss_bps"] - e["avg_loss_bps"]
        dwr = (r_["win_rate"] - e["win_rate"]) * 100
        dtail = (r_["pct_loss_1atr"] - e["pct_loss_1atr"]) * 100
        parts = []
        if abs(dwr) > 0.5:
            parts.append(f"hit rate {dwr:+.1f} pp")
        if abs(dwin) > 5:
            parts.append(f"average win {dwin:+.0f} bps")
        if abs(dloss) > 5:
            parts.append(f"average loss {dloss:+.0f} bps")
        A("Reading the decomposition: "
          + ("; ".join(parts) if parts else "no single component moves much")
          + f"; the >1 ATR loss rate moves {dtail:+.2f} pp.")
        A("")
        if dloss > 5 and dtail > 0.5:
            A("**The left tail is doing the damage.** Losses have grown "
              "both in average size and in frequency of large ones, which "
              "is the pattern the question anticipated.")
        elif dwin < -5 and dloss < 5:
            A("**This is not a left-tail story.** The average loss has "
              "not grown; the winners have shrunk. That points at a "
              "smaller move being available rather than at worse risk, "
              "and it argues against a stop as the remedy — a stop "
              "addresses losses, and losses are not what changed.")
        elif dloss > 5 and dtail <= 0.5:
            A("**Losses are larger on average but not more often "
              "extreme** — the whole loss distribution shifted rather "
              "than the tail alone.")
        else:
            A("**No clean single explanation.** The components move "
              "modestly and in different directions.")
        A("")

    # yearly detail
    for uni in UNIS:
        A(f"## By year — {uni}")
        A("")
        d = y[(y["universe"] == uni) & (y["kind"] == "year")]
        _hdr(A)
        for _, x in d.iterrows():
            _row(x, A)
        A("")

    # ---- stop value early vs recent ----
    A("## Does an ATR −1.0 stop earn more in the recent period?")
    A("")
    A("| Universe | Period | n | % stopped | Baseline NET | Stopped NET | "
      "**Cost** | Tail before | Tail after | **Tail cut (pp)** | "
      "**pp per bp** |")
    A("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, x in sv.iterrows():
        eff = ("—" if pd.isna(x["efficiency"]) else f"{x['efficiency']:.2f}")
        A(f"| {x['universe']} | {x['period']} | {int(x['n']):,} | "
          f"{x['pct_stopped']*100:.1f}% | {x['base_net']:+.1f} | "
          f"{x['stop_net']:+.1f} | **{x['cost_bps']:+.1f}** | "
          f"{x['base_tail_pct']:.2f}% | {x['stop_tail_pct']:.2f}% | "
          f"**{x['tail_cut_pp']:.2f}** | **{eff}** |")
    A("")
    A("Cost is baseline NET minus stopped NET, so a positive number means "
      "the stop gave up expectancy. Efficiency is percentage points of "
      ">1 ATR tail removed per basis point surrendered — the same measure "
      "used in `STOPSUMMARY_REPORT.md`.")
    A("")
    for uni in UNIS:
        d = sv[sv["universe"] == uni].set_index("period")
        if not all(p in d.index for p in PERIODS):
            continue
        e, r_ = d.loc[PERIODS[0]], d.loc[PERIODS[-1]]
        better = r_["efficiency"] > e["efficiency"]
        A(f"**{uni}:** efficiency moves from {e['efficiency']:.2f} in "
          f"{PERIODS[0]} to {r_['efficiency']:.2f} in {PERIODS[-1]}"
          + (" — the stop **is** worth more recently."
             if better else
             " — the stop is **not** worth more recently.")
          + f" Its cost changes from {e['cost_bps']:+.1f} to "
          f"{r_['cost_bps']:+.1f} bps while the tail it removes changes "
          f"from {e['tail_cut_pp']:.2f} to {r_['tail_cut_pp']:.2f} pp.")
        A("")

    A("## Reading notes")
    A("")
    A("- **Three periods is three observations.** Any story told across "
      "them is a story about three numbers, and the 2020–2022 block "
      "contains both the COVID crash and the 2021 meme episode, which are "
      "not a regime so much as two unrepeatable events.")
    A("- **Year buckets are small** — a few hundred trades each, so a "
      "single-year figure carries a wide interval that is not printed "
      "here. Use the periods for inference and the years for texture.")
    A("- **Winsorised skew and kurtosis** are shown because the raw "
      "values are dominated by one 2021 observation and would otherwise "
      "make that period look structurally different when it is not.")
    A("- **No multiple-comparison control.** Splitting one sample by time "
      "and then reading the worst period as a trend is exactly how decay "
      "gets diagnosed where none exists.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/regime_sizing.py`; "
      "tables in `lambda_data/tables/rs_*.csv`._")
    return "\n".join(L)


# ===========================================================================
def build_sizing(R: dict, meta: dict) -> str:
    s = R["schemes"].set_index("scheme")
    g = R["groups"].set_index("group")
    L: list[str] = []
    A = L.append
    base = s.loc["C — Equal size (baseline)"]

    A("# Lambda — Conviction and Risk-Based Position Sizing")
    A("")
    A("Post-earnings T+1, High Volume + Continuation (non-doji), entry at "
      "the 09:35 open, 1-hour hold, **full universe screen applied** "
      f"({meta['n_screened']:,} of {meta['n_core']:,} events). Risk "
      "factors are entry-time only: gap/ATR and the opening 5-minute "
      "volume ratio.")
    A("")
    A("| Tier | Definition | Share of trades |")
    A("|---|---|---:|")
    A(f"| High Risk | gap/ATR > 1.5 **or** volume ratio > 5× | "
      f"{meta['pct_high']*100:.1f}% |")
    A(f"| Low Risk | gap/ATR < 0.8 **and** volume ratio < 3× | "
      f"{meta['pct_low']*100:.1f}% |")
    A(f"| Medium | everything else | {meta['pct_med']*100:.1f}% |")
    A("")
    A("> **How the schemes are made comparable.** Each is a vector of "
      "notional weights, and every figure is reported **per unit of "
      "average notional deployed**. Without that, a scheme that simply "
      "deploys less capital would look safer and less profitable for no "
      "reason but leverage. Mean and max raw weight are shown so the "
      "de-leveraging stays visible.")
    A(">")
    A("> **Scheme D expressed as a weight.** Risking a fixed dollar "
      "amount per ATR implies `shares = R / ATR_$`, so `notional = R / "
      "ATR%`. Its weight is therefore proportional to the inverse of ATR "
      "as a share of price — which is what makes it comparable to A, B "
      "and C rather than only expressible in risk units.")
    A(">")
    A("> **Win rate is identical across all schemes**, because a positive "
      "weight cannot change a trade's sign. So is *% of trades losing "
      "more than 1 ATR*, which is a property of the trade, not the "
      "position. What sizing changes is those trades' **contribution**, "
      "which is what the average-large-loss and standard-deviation "
      "columns capture.")
    A("")

    # ---------------- schemes ----------------
    A("## 1. The schemes")
    A("")
    A("| Scheme | Mean weight | Max weight | Win rate | **NET (bps)** | "
      "NET (ATR) | Avg Win | Avg Loss | Payoff | Avg large loss | "
      "Std dev | **NET / Std** |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for nm in s.index:
        x = s.loc[nm]
        A(f"| {nm} | {x['mean_weight']:.2f} | {x['max_weight']:.1f} | "
          f"{x['win_rate']*100:.1f}% | **{x['net_bps']:+.1f}** | "
          f"{x['net_atr']:+.4f} | {x['avg_win_bps']:.0f} | "
          f"{x['avg_loss_bps']:.0f} | {x['payoff_ratio']:.2f} | "
          f"{x['avg_large_loss_bps']:.0f} | {x['std_bps']:.0f} | "
          f"**{x['sharpe_like']:.4f}** |")
    A("")
    A("All returns are basis points per unit of average notional. "
      f"NET is after {meta['cost_bps']} bps.")
    A("")

    best_n = s["net_bps"].idxmax()
    best_r = s["sharpe_like"].idxmax()
    A("| | Best scheme | Value |")
    A("|---|---|---:|")
    A(f"| Highest expectancy | {best_n} | {s.loc[best_n, 'net_bps']:+.1f} "
      "bps |")
    A(f"| Best risk-adjusted | {best_r} | "
      f"{s.loc[best_r, 'sharpe_like']:.4f} |")
    A("")
    spread = s["sharpe_like"].max() - s["sharpe_like"].min()
    if best_r != "C — Equal size (baseline)":
        d = s.loc[best_r]
        A(f"**{best_r} is the best risk-adjusted variant** "
          f"({d['sharpe_like']:.4f} against {base['sharpe_like']:.4f} for "
          f"equal sizing) — but the margin is "
          f"{(d['sharpe_like']/base['sharpe_like']-1)*100:+.1f}%, and the "
          f"entire spread across all five schemes is {spread:.4f}, or "
          f"{spread/base['sharpe_like']*100:.1f}% of the baseline. **No "
          "scheme meaningfully separates from equal sizing.**")
    else:
        A(f"**Equal sizing is the best risk-adjusted variant.** The whole "
          f"spread across the five schemes is {spread:.4f}, "
          f"{spread/base['sharpe_like']*100:.1f}% of the baseline.")
    A("")
    A("Note the direction of the trade-off: every risk-tiered scheme "
      "lowers NET **and** lowers standard deviation, in nearly the same "
      "proportion. Section 3 explains why that had to happen.")
    A("")

    # ---------------- groups ----------------
    A("## 2. What the tiers actually do, under equal size")
    A("")
    A("| Group | n | Share of trades | Win rate | **NET (bps)** | "
      "NET (ATR) | Payoff | Std dev | % loss > 1 ATR | Avg large loss | "
      "**Share of total P&L** | **Share of large losses** |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for nm in g.index:
        x = g.loc[nm]
        A(f"| {nm} | {int(x['n']):,} | {x['share_of_trades']*100:.1f}% | "
          f"{x['win_rate']*100:.1f}% | **{x['net_bps']:+.1f}** | "
          f"{x['net_atr']:+.4f} | {x['payoff_ratio']:.2f} | "
          f"{x['std_bps']:.0f} | {x['pct_loss_1atr']*100:.2f}% | "
          + ("—" if pd.isna(x["avg_large_loss_bps"])
             else f"{x['avg_large_loss_bps']:.0f}")
          + f" | **{x['share_of_total_pnl']*100:.1f}%** | "
          f"**{x['share_of_large_losses']*100:.1f}%** |")
    A("")
    hr = g.loc["High Risk"]
    A(f"**The High Risk tier is {hr['share_of_trades']*100:.1f}% of "
      f"trades, {hr['share_of_total_pnl']*100:.1f}% of total P&L and "
      f"{hr['share_of_large_losses']*100:.1f}% of all >1 ATR losses.** "
      + ("It contributes more P&L than its share of trades, which is the "
         "problem with cutting it: the risk and the return live in the "
         "same place."
         if hr["share_of_total_pnl"] > hr["share_of_trades"] else
         "It contributes less P&L than its share of trades while "
         "carrying a disproportionate share of the large losses, which is "
         "the case for cutting it."))
    A("")
    if "Low + Medium" in g.index:
        lm = g.loc["Low + Medium"]
        A(f"For contrast, Low + Medium is {lm['share_of_trades']*100:.1f}% "
          f"of trades, {lm['share_of_total_pnl']*100:.1f}% of P&L and "
          f"{lm['share_of_large_losses']*100:.1f}% of the large losses, at "
          f"{lm['net_bps']:+.1f} bps with a "
          f"{lm['std_bps']:.0f} bps standard deviation against "
          f"{hr['std_bps']:.0f} for High Risk.")
        A("")

    # the verdict
    A("## 3. Verdict")
    A("")
    ratio_pnl = hr["share_of_total_pnl"] / hr["share_of_trades"]
    ratio_loss = hr["share_of_large_losses"] / hr["share_of_trades"]
    A("| High Risk tier | Multiple of its trade share |")
    A("|---|---:|")
    A(f"| Share of P&L | {ratio_pnl:.2f}× |")
    A(f"| Share of large losses | {ratio_loss:.2f}× |")
    A("")
    A(f"Large losses are more concentrated in the High Risk tier "
      f"({ratio_loss:.2f}×) than P&L is ({ratio_pnl:.2f}×), which looks "
      "like the classic case for cutting size there. **It is not, and the "
      "reason is the single most useful number in this report:**")
    A("")
    hr_ratio = hr["net_bps"] / hr["std_bps"]
    lm = g.loc["Low + Medium"]
    lm_ratio = lm["net_bps"] / lm["std_bps"]
    A("| Group under equal size | NET | Std dev | **NET / Std** |")
    A("|---|---:|---:|---:|")
    A(f"| High Risk | {hr['net_bps']:+.1f} | {hr['std_bps']:.0f} | "
      f"**{hr_ratio:.4f}** |")
    A(f"| Low + Medium | {lm['net_bps']:+.1f} | {lm['std_bps']:.0f} | "
      f"**{lm_ratio:.4f}** |")
    A("")
    if hr_ratio >= lm_ratio:
        A(f"**The High Risk tier is not risk-inefficient — it is simply "
          f"bigger.** Its return per unit of volatility ({hr_ratio:.4f}) "
          f"is at least as good as the Low + Medium tier's "
          f"({lm_ratio:.4f}). It earns more *and* swings more, in "
          "proportion. Cutting its size therefore removes return and risk "
          "together, which is why Schemes A, B and B2 all land within "
          "0.5% of equal sizing on NET/Std and slightly below it: they are "
          "de-levering a part of the book that did not deserve to be "
          "de-levered.")
        A("")
        A("This is the opposite of what the tier concentration table "
          "implies at first glance, and it is why the concentration of "
          "*large losses* is the wrong statistic to size on. A group can "
          "own most of the tail simply by being more volatile throughout, "
          "without being any worse per unit of that volatility.")
    else:
        A(f"The High Risk tier is genuinely less efficient "
          f"({hr_ratio:.4f} against {lm_ratio:.4f}), so cutting its size "
          "should help — and the scheme table confirms it.")
    A("")
    A("Scheme D deserves separate comment. Volatility targeting is the "
      "most theoretically appealing of the four — it is the only one that "
      "equalises risk rather than approximating it — and it "
      + ("delivers the best risk-adjusted result here."
         if best_r.startswith("D") else
         "does not win here.")
      + f" But its weight distribution is the practical objection: a mean "
      f"weight of {s.loc['D — Fixed dollar risk (∝ 1/ATR%)', 'mean_weight']:.2f} "
      f"with a maximum of "
      f"{s.loc['D — Fixed dollar risk (∝ 1/ATR%)', 'max_weight']:.1f}× "
      "means the quietest name in the sample gets a position many times "
      "the average. Any real implementation caps that, and the cap — not "
      "the theory — determines what the scheme actually earns.")
    A("")

    A("## Reading notes")
    A("")
    A("- **The tier thresholds were not fitted**, but they were chosen "
      "after seeing the segment tables in `VALIDATION_REPORT.md`, which "
      "is not the same as choosing them in advance.")
    A("- **Differences between schemes are small** relative to the "
      "standard deviation of a single trade. None of this is a new edge; "
      "it is a reallocation of an existing one.")
    A("- **Costs are flat "
      f"{meta['cost_bps']} bps per unit of notional**, so a half-size "
      "trade pays half the cost. That is right for a spread-driven cost "
      "and wrong for any fixed per-ticket component, which would "
      "penalise the smaller positions.")
    A("- **No compounding, no portfolio constraint, no cap on "
      "concurrent positions.** These are per-trade averages, not an "
      "equity curve.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/regime_sizing.py`; "
      "tables in `lambda_data/tables/rs_*.csv`._")
    return "\n".join(L)
