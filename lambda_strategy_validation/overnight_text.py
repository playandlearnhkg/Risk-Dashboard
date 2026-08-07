"""overnight_text.py — renders OVERNIGHT_REPORT.md. Table-focused."""

from __future__ import annotations

import numpy as np
import pandas as pd

EORDER = ["Winners at T+1 close", "Losers at T+1 close", "All trades"]
OORDER = ["Winners on day T", "Losers on day T", "All sessions"]


def build(R: dict, meta: dict) -> str:
    ep = R["e_perf"].set_index("group")
    eg = R["e_gap"].set_index("group")
    op = R["o_perf"].set_index("group")
    om = R["o_meta"].iloc[0]
    L: list[str] = []
    A = L.append

    A("# Lambda — Residual Edge in the Session After the Trade")
    A("")
    A("Two universes: the post-earnings continuation cohort, and ordinary "
      "non-earnings sessions.")
    A("")
    A("> **\"Overnight\" here means close → close.** Both designs specify "
      "the return from one close to the next, which is a full trading "
      "session *plus* the gap that precedes it — not the gap alone. The "
      "gap is broken out separately in section C so the two are never "
      "conflated. Returns are gross; no cost is applied, because holding "
      "an existing position overnight incurs no new round trip.")
    A("")

    # =============== TEST 1 ===============
    A("## Test 1 — Post-earnings (T+1 → T+2)")
    A("")
    A("| Input | Definition |")
    A("|---|---|")
    A("| Cohort | High Volume + Continuation (non-doji), the setup used "
      "throughout this series |")
    A("| Entry | 09:35 open on T+1 |")
    A("| Classification | the T+1 **close** result, signed in the trade's "
      "direction |")
    A("| Measured | T+1 close → T+2 close, same sign |")
    A("| ATR | ATR(14) as of the T+1 close — known when the "
      "hold-overnight decision is made |")
    A("")

    A("### A. Performance")
    A("")
    A("| Group | n | Avg return | Win rate | Median | p10 | p90 | "
      "% losing > 1.0 ATR |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|")
    for gname in EORDER:
        x = ep.loc[gname]
        A(f"| {gname} | {int(x['n']):,} | **{x['mean_bps']:+.1f}** | "
          f"{x['win_rate']*100:.1f}% | {x['median_bps']:+.1f} | "
          f"{x['p10_bps']:+.0f} | {x['p90_bps']:+.0f} | "
          f"{x['pct_loss_1atr']*100:.2f}% |")
    A("")
    A("All figures in basis points. For reference, the T+1 day trade "
      "itself returned "
      + ", ".join(f"{ep.loc[g, 'mean_day_bps']:+.0f} bps "
                  f"({g.split(' at ')[0].lower()})" for g in EORDER)
      + ".")
    A("")

    A("### B. Distribution shape")
    A("")
    A("| Group | Std dev | Skewness | Excess kurtosis |")
    A("|---|---:|---:|---:|")
    for gname in EORDER:
        x = ep.loc[gname]
        A(f"| {gname} | {x['std_bps']:.0f} | {x['skew']:+.2f} | "
          f"{x['kurtosis']:+.1f} |")
    A("")
    A("Excess kurtosis, so a normal distribution reads 0.0.")
    A("")

    A("### C. Next-day gap behaviour (T+1 close → T+2 open)")
    A("")
    A("| Group | Avg gap | Median gap | % gaps **with** the trade | "
      "% **against** | Avg favourable gap | Avg unfavourable gap |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    for gname in EORDER:
        x = eg.loc[gname]
        A(f"| {gname} | **{x['mean_gap_bps']:+.1f}** | "
          f"{x['median_gap_bps']:+.1f} | {x['pct_same_dir']*100:.1f}% | "
          f"{x['pct_against']*100:.1f}% | {x['avg_fav_gap_bps']:+.1f} | "
          f"{x['avg_unfav_gap_bps']:+.1f} |")
    A("")
    allrow = ep.loc["All trades"]
    allgap = eg.loc["All trades"]
    g_, tot = allgap["mean_gap_bps"], allrow["mean_bps"]
    if tot != 0:
        same_sign = (g_ > 0) == (tot > 0)
        if not same_sign:
            A(f"**The gap and the full period point opposite ways.** Across "
              f"all trades the gap averages {g_:+.1f} bps while the whole "
              f"close-to-close move averages {tot:+.1f} bps, so the T+2 "
              f"session's intraday move contributes about {tot - g_:+.1f} "
              "bps and more than offsets the opening drift. Neither "
              "component is large.")
        elif abs(g_) > abs(tot) * 0.5:
            A(f"The gap accounts for {g_:+.1f} bps of the {tot:+.1f} bps "
              "close-to-close move — most of it, so what residual exists "
              "arrives at the open rather than through the next session.")
        else:
            A(f"The gap accounts for {g_:+.1f} bps of the {tot:+.1f} bps "
              "close-to-close move — a minority, so the next session's "
              "intraday move carries the rest.")
        A("")
        A("The more useful numbers in that table are the last three "
          "columns. Gaps go with the trade "
          f"{allgap['pct_same_dir']*100:.1f}% of the time against "
          f"{allgap['pct_against']*100:.1f}% — a coin flip — and a "
          f"favourable gap is worth {allgap['avg_fav_gap_bps']:+.0f} bps "
          f"while an unfavourable one costs "
          f"{allgap['avg_unfav_gap_bps']:+.0f}. **You are taking roughly "
          "symmetric 75–80 bps two-way risk at the open for an expected "
          f"value of {g_:+.1f} bps.** That is the clearest statement of "
          "what carrying the position overnight actually buys.")
        A("")

    # verdict on test 1
    w, l = ep.loc[EORDER[0]], ep.loc[EORDER[1]]
    A("### What test 1 shows")
    A("")
    sig = [g for g in EORDER if ep.loc[g, "boot_p"] < 0.05]
    A("| Group | Pooled mean | 95% CI | p (clustered) | Date-weighted mean "
      "| t |")
    A("|---|---:|---:|---:|---:|---:|")
    for gname in EORDER:
        x = ep.loc[gname]
        A(f"| {gname} | {x['mean_bps']:+.1f} | [{x['ci_lo']:+.1f}, "
          f"{x['ci_hi']:+.1f}] | {x['boot_p']:.3f} | "
          f"{x['dw_mean_bps']:+.1f} | {x['dw_t']:.2f} |")
    A("")
    if not sig:
        A("**No group shows a residual edge distinguishable from zero.** "
          "The post-earnings continuation move is finished by the T+1 "
          "close: whatever the trade did during the day, the next session "
          "carries no reliable continuation and no reliable reversal.")
        A("")
    else:
        A(f"**{len(sig)} of {len(EORDER)} groups differ from zero** at the "
          "5% level on a date-clustered bootstrap: "
          + ", ".join(f"{g} ({ep.loc[g, 'mean_bps']:+.1f} bps, "
                      f"p={ep.loc[g, 'boot_p']:.3f})" for g in sig) + ".")
        A("")
    d = w["mean_bps"] - l["mean_bps"]
    A(f"Winners minus losers is **{d:+.1f} bps**. "
      + ("A positive figure would mean the day's result carries forward; a "
         "negative one would mean it reverses. "
         if abs(d) > 20 else
         "That is small relative to the "
         f"{ep.loc['All trades', 'std_bps']:.0f} bps standard deviation of "
         "the period, so the T+1 outcome is close to uninformative about "
         "the next session. "))
    A("")

    # =============== TEST 2 ===============
    A("## Test 2 — Ordinary non-earnings sessions")
    A("")
    A("| Input | Definition |")
    A("|---|---|")
    A(f"| Universe | {int(om['n_tickers'])} tickers, "
      f"{om['start']} → {om['end']} |")
    A("| Liquidity screen | price ≥ $10, ADV ≥ 500k shares, ADTV ≥ $50M, "
      "market cap ≥ $3B — all on the **prior** session, so point-in-time |")
    A("| Exclusions | post-earnings T+1 sessions, and the session before "
      "one (its close-to-close would land on a T+1) |")
    A("| Classification | day T **open → close**; a Winner closed above "
      "its open |")
    A("| Measured | T close → T+1 close, **long** |")
    A("")
    A(f"Sample construction: {int(om['n_raw']):,} panel sessions → "
      f"{int(om['n_liquid']):,} passing the liquidity screen → "
      f"{int(om['n_nonearn']):,} after removing earnings-adjacent days → "
      f"**{int(om['n_sessions']):,}** with a usable next close, after "
      f"dropping {int(om['n_seam'])} rows spanning a data seam.")
    A("")
    A("> **A data problem found and fixed while running this.** The "
      "panel's price basis changes between 2022-03-04 and the following "
      "session: 28 liquid names show one-step close-to-close moves of 10× "
      "to 21× (AMZN 2,911 → 138, GOOGL 2,637 → 125, NVDA 229 → 21). Those "
      "are split adjustments applied from that date, not returns. Left in, "
      "they drove the excess kurtosis of this sample to over 23,000 and "
      "pulled the mean noticeably. Every close-to-close observation "
      "spanning that boundary is now dropped — for all tickers, not just "
      "the visibly broken ones, since the basis change affects the series "
      "rather than the name. It sits next to the 2022-03-01 IEX tape "
      "change already handled in the volume work.")
    A("")
    ext = R.get("o_extremes")
    if ext is not None and len(ext):
        A("Genuine extremes are deliberately **kept**. The largest "
          "surviving moves are real market history:")
        A("")
        A("| Ticker | Date | Close | Next close | Return |")
        A("|---|---|---:|---:|---:|")
        for _, x in ext.iterrows():
            A(f"| {x['ticker']} | {x['date']} | {x['close']:,.2f} | "
              f"{x['next_close']:,.2f} | {x['ret_bps']:+,.0f} bps |")
        A("")
    A("> **Direction convention.** An ordinary session carries no signal "
      "direction, so the position is taken as long-the-stock and the "
      "following period is measured long. Winners are therefore stocks "
      "that rose during the session, and a negative average for that group "
      "means the rise partly gave back.")
    A("")

    A("| Group | n | Avg return | Win rate | Median | p10 | "
      "% losing > 1.0 ATR | Skewness | Excess kurtosis |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for gname in OORDER:
        x = op.loc[gname]
        A(f"| {gname} | {int(x['n']):,} | **{x['mean_bps']:+.1f}** | "
          f"{x['win_rate']*100:.1f}% | {x['median_bps']:+.1f} | "
          f"{x['p10_bps']:+.0f} | {x['pct_loss_1atr']*100:.2f}% | "
          f"{x['skew']:+.2f} | {x['kurtosis']:+.1f} |")
    A("")
    A("| Group | Std dev | 95% CI on the mean | p (clustered) |")
    A("|---|---:|---:|---:|")
    for gname in OORDER:
        x = op.loc[gname]
        A(f"| {gname} | {x['std_bps']:.0f} | [{x['ci_lo']:+.1f}, "
          f"{x['ci_hi']:+.1f}] | {x['boot_p']:.3f} |")
    A("")
    A("### The weighting changes the answer")
    A("")
    A("The means above are **pooled** — every observation counts equally, "
      "so a day contributing many names counts more than a quiet one. A "
      "daily-rebalanced equal-weight book earns the **date-weighted** mean "
      "instead: average within each date first, then across dates. On this "
      "sample the two disagree.")
    A("")
    A("| Group | Pooled mean | Date-weighted mean | SE | t | n dates |")
    A("|---|---:|---:|---:|---:|---:|")
    for gname in OORDER:
        x = op.loc[gname]
        A(f"| {gname} | {x['mean_bps']:+.2f} | **{x['dw_mean_bps']:+.2f}** "
          f"| {x['dw_se_bps']:.2f} | {x['dw_t']:.2f} | "
          f"{int(x['n_dates']):,} |")
    A("")
    pooled_gap = op.loc[OORDER[0], "mean_bps"] - op.loc[OORDER[1], "mean_bps"]
    dw_gap = op.loc[OORDER[0], "dw_mean_bps"] - op.loc[OORDER[1], "dw_mean_bps"]
    A(f"**Winners minus losers is {pooled_gap:+.2f} bps pooled but "
      f"{dw_gap:+.2f} bps date-weighted.** "
      + ("The reversal effect is largely an artefact of weighting: once "
         "each day counts once, winners and losers earn almost the same "
         "thing over the following session. What survives both weightings "
         "is the level — the whole universe drifts up close-to-close, "
         "which is the equity risk premium showing up on a one-day "
         "horizon, not a signal."
         if abs(dw_gap) < abs(pooled_gap) / 2 else
         "The effect survives both weightings, so it is not a weighting "
         "artefact."))
    A("")

    ow, ol = op.loc[OORDER[0]], op.loc[OORDER[1]]
    od = ow["mean_bps"] - ol["mean_bps"]
    A("### What test 2 shows")
    A("")
    dwg = ow["dw_mean_bps"] - ol["dw_mean_bps"]
    if od < 0 and abs(dwg) < abs(od) / 2:
        A(f"**On the pooled numbers day-T losers beat day-T winners by "
          f"{abs(od):.1f} bps** ({ol['mean_bps']:+.1f} against "
          f"{ow['mean_bps']:+.1f}) — the short-horizon reversal the "
          "literature would predict. **But it does not survive equal "
          "weighting by date**, where the gap shrinks to "
          f"{abs(dwg):.1f} bps. Report it as a weighting artefact, not an "
          "edge.")
        A("")
        A("What does survive both weightings is the **level**: every group, "
          "including losers, earns a positive close-to-close return "
          f"({op.loc['All sessions', 'dw_mean_bps']:+.1f} bps "
          f"date-weighted, t = {op.loc['All sessions', 'dw_t']:.1f}). That "
          "is the equity risk premium arriving on a one-day horizon, "
          "available to anyone already holding the stock and not a signal "
          "to act on.")
    elif od < 0:
        A(f"**Day-T losers outperform day-T winners over the next "
          f"session, by {abs(od):.1f} bps pooled and {abs(dwg):.1f} bps "
          f"date-weighted** ({ol['mean_bps']:+.1f} against "
          f"{ow['mean_bps']:+.1f}). That is short-horizon reversal, the "
          "most heavily documented effect in the equity microstructure "
          "literature, and finding it here is a sanity check on the data "
          "rather than a discovery.")
    else:
        A(f"**Day-T winners outperform day-T losers over the next "
          f"session, by {od:.1f} bps** "
          f"({ow['mean_bps']:+.1f} against {ol['mean_bps']:+.1f}) — "
          "short-horizon momentum rather than the reversal usually "
          "documented at this frequency.")
    A("")
    A(f"On a sample of {int(op.loc['All sessions', 'n']):,} sessions even "
      "small effects clear significance easily, so the p-values here say "
      "little about tradeability. The relevant comparison is the effect "
      f"size against the {op.loc['All sessions', 'std_bps']:.0f} bps "
      "standard deviation of a single overnight-plus-session return, and "
      "against a round trip that would cost roughly "
      f"{meta['cost_bps']} bps to put on and take off.")
    A("")

    # cross-test
    A("## The two tests side by side")
    A("")
    A("| | Post-earnings T+1→T+2 | Ordinary T→T+1 |")
    A("|---|---:|---:|")
    A(f"| n | {int(ep.loc['All trades', 'n']):,} | "
      f"{int(op.loc['All sessions', 'n']):,} |")
    A(f"| Winners' next return | {w['mean_bps']:+.1f} | "
      f"{ow['mean_bps']:+.1f} |")
    A(f"| Losers' next return | {l['mean_bps']:+.1f} | "
      f"{ol['mean_bps']:+.1f} |")
    A(f"| Winners − Losers | {d:+.1f} | {od:+.1f} |")
    A(f"| Std dev | {ep.loc['All trades', 'std_bps']:.0f} | "
      f"{op.loc['All sessions', 'std_bps']:.0f} |")
    A(f"| Skewness (all) | {ep.loc['All trades', 'skew']:+.2f} | "
      f"{op.loc['All sessions', 'skew']:+.2f} |")
    A(f"| Excess kurtosis (all) | {ep.loc['All trades', 'kurtosis']:+.1f} | "
      f"{op.loc['All sessions', 'kurtosis']:+.1f} |")
    A("")
    A("The post-earnings cohort is the more volatile of the two by a wide "
      "margin, which is expected — these are names that just gapped on "
      "news. What matters for the question asked is that the extra "
      "volatility does not come with extra edge.")
    A("")

    # ---------------- caveats ----------------
    A("## Reading notes")
    A("")
    A("- **No costs are applied.** Holding a position you already own "
      "through the close incurs no new round trip, so a gross figure is "
      "the right one for the decision \"carry it or flatten it\". Anyone "
      "putting the position on *fresh* at the close would pay the usual "
      f"{meta['cost_bps']} bps, which exceeds most of the effects above.")
    A("- **Overnight carries risks the intraday tests do not**: no "
      "opportunity to manage the position, gap risk on unrelated news, "
      "and — for the gap-down cohort, which is short — borrow that must "
      "be maintained. None of that is priced here.")
    A("- **Test 2's classification is long-only by construction.** "
      "Winners are sessions that rose. A short-side framing would mirror "
      "the table rather than add to it.")
    A("- **Both tests are date-clustered** in their inference, which "
      "matters most for test 2 where a single day contributes thousands of "
      "correlated observations.")
    A("- **Survivorship applies to test 2** in the usual direction: the "
      "panel contains names that existed through the sample.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/overnight.py`; "
      "tables in `lambda_data/tables/on_*.csv`._")
    return "\n".join(L)
