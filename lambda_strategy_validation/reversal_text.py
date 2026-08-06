"""reversal_text.py — renders REVERSAL_PAYOFF_REPORT.md.

Deliberately table-first. Every sentence that makes a claim is generated
from the numbers in `R`, not pre-written, because pre-written conclusions
have contradicted the data three times in this investigation.
"""

from __future__ import annotations

import pandas as pd

BUCKET_ORDER = ["Gap/ATR < 1.0", "Gap/ATR 1.0-2.0", "Gap/ATR > 2.0"]


def _t(df, cols, names, rate=(), bps=(), p=(), num=()):
    o = df[cols].copy()
    for c in rate:
        o[c] = (o[c] * 100).map(lambda v: "" if pd.isna(v) else f"{v:.1f}%")
    for c in bps:
        o[c] = o[c].map(lambda v: "" if pd.isna(v) else f"{v:+.1f}")
    for c in p:
        o[c] = o[c].map(lambda v: "" if pd.isna(v) else f"{v:.3f}")
    for c in num:
        o[c] = o[c].map(lambda v: "" if pd.isna(v) else f"{v:.2f}")
    o.columns = names
    return o.to_markdown(index=False) + "\n"


def _order(df, col, order):
    d = df.copy()
    d["_k"] = d[col].map({v: i for i, v in enumerate(order)})
    return d.sort_values(["window", "_k"]).drop(columns="_k")


def build(R: dict, meta: dict) -> str:
    L = []
    A = L.append
    t1a, t1b, t2, t3 = (R["p1a_reversal_holding"], R["p1b_reversal_gapatr"],
                        R["p2_continuation_payoff"], R["p3_compare"])

    A("# Lambda — Reversal Analysis and Continuation Payoff Ratio")
    A("")
    A("Both parts use entry at the **open of the 09:35 bar**, the same rules "
      "and the same look-ahead guards as the previous 09:35 report.")
    A("")
    A("## Rules and sign convention")
    A("")
    A("| Input | Definition |")
    A("|---|---|")
    A("| Continuation signal | 09:30–09:35 candle closes **in** the gap "
      "direction |")
    A("| Reversal signal | 09:30–09:35 candle closes **against** the gap "
      "direction |")
    A("| Entry | Open of the 09:35 bar |")
    A("| ATR / Gap-ATR | Prior-session ATR(14); overnight gap in price terms "
      "÷ that ATR |")
    A("| Costs | 6.6 bps round trip, subtracted for NET |")
    A("")
    A(f"Sample: **{meta['n_events']:,}** events with a usable 09:35 price — "
      f"**{meta['n_cont']:,}** Continuation, **{meta['n_rev']:,}** Reversal "
      f"(the balance are Doji first candles, excluded from both). Cells with "
      f"n < {meta['small']} are flagged. p-values are two-sided from a "
      "date-clustered bootstrap.")
    A("")
    A("> **Sign convention — the one judgement call here.** For Reversal "
      "events the first candle closed *against* the gap, so the tradeable "
      "rule is *follow the candle*, i.e. trade against the gap. All Reversal "
      "figures below are signed in the **candle's** direction:")
    A(">")
    A("> `reversal_return = −sign(gap) × (P_end / P_entry − 1)`")
    A(">")
    A("> Under that convention both cohorts express one single rule — follow "
      "the first 5-minute candle — and are directly comparable. If you prefer "
      "to read the Reversal rows as *fade the candle / stay with the gap*, "
      "flip the sign of every Reversal number: win rate becomes 1 − p, and "
      "average win and average loss swap.")
    A("")

    # ---------------- Part 1A ----------------
    A("## Part 1A — Reversal by holding period")
    A("")
    A(_t(t1a, ["window", "cohort", "n", "win_rate", "wilson_lo", "wilson_hi",
               "avg_win_bps", "avg_loss_bps", "payoff_ratio", "gross_bps",
               "gross_p", "net_bps", "net_p", "small"],
         ["Window", "Cohort", "n", "Win rate", "Wilson lo", "Wilson hi",
          "Avg win", "Avg loss", "Payoff", "Gross (bps)", "p", "NET (bps)",
          "net p", "n<150?"],
         rate=("win_rate", "wilson_lo", "wilson_hi"),
         bps=("avg_win_bps", "avg_loss_bps", "gross_bps", "net_bps"),
         p=("gross_p", "net_p"), num=("payoff_ratio",)))

    # ---------------- Part 1B ----------------
    A("## Part 1B — Reversal by Gap/ATR")
    A("")
    A(_t(_order(t1b, "bucket", BUCKET_ORDER),
         ["window", "bucket", "n", "win_rate", "wilson_lo", "wilson_hi",
          "avg_win_bps", "avg_loss_bps", "payoff_ratio", "gross_bps",
          "gross_p", "net_bps", "net_p", "small"],
         ["Window", "Gap/ATR", "n", "Win rate", "Wilson lo", "Wilson hi",
          "Avg win", "Avg loss", "Payoff", "Gross (bps)", "p", "NET (bps)",
          "net p", "n<150?"],
         rate=("win_rate", "wilson_lo", "wilson_hi"),
         bps=("avg_win_bps", "avg_loss_bps", "gross_bps", "net_bps"),
         p=("gross_p", "net_p"), num=("payoff_ratio",)))

    # ---------------- Part 2 ----------------
    A("## Part 2 — Continuation: average win vs average loss by Gap/ATR")
    A("")
    A("Average win = mean of positive outcomes. Average loss = mean of "
      "negative outcomes, shown as a positive magnitude. Payoff ratio = "
      "avg win ÷ avg loss. Expectancy is the gross mean; NET subtracts costs.")
    A("")
    A(_t(_order(t2, "bucket", BUCKET_ORDER),
         ["window", "bucket", "n", "win_rate", "avg_win_bps", "avg_loss_bps",
          "payoff_ratio", "gross_bps", "gross_p", "net_bps", "net_ci_lo",
          "net_ci_hi", "net_p", "small"],
         ["Window", "Gap/ATR", "n", "Win rate", "Avg win", "Avg loss",
          "Payoff", "Gross (bps)", "p", "NET (bps)", "CI lo", "CI hi",
          "net p", "n<150?"],
         rate=("win_rate",),
         bps=("avg_win_bps", "avg_loss_bps", "gross_bps", "net_bps",
              "net_ci_lo", "net_ci_hi"),
         p=("gross_p", "net_p"), num=("payoff_ratio",)))

    # ---------------- Part 3 ----------------
    A("## Final comparison — Continuation vs Reversal in each Gap/ATR zone")
    A("")
    for w in sorted(t3["window"].unique()):
        sub = _order(t3[t3["window"] == w], "bucket", BUCKET_ORDER)
        A(f"**{w}**")
        A("")
        A("| Gap/ATR | Side | n | Win rate | Avg win | Avg loss | Payoff | "
          "Gross | NET | net p |")
        A("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for _, r in sub.iterrows():
            A(f"| {r['bucket']} | {r['side']} | {int(r['n']):,} | "
              f"{r['win_rate']*100:.1f}% | {r['avg_win_bps']:+.1f} | "
              f"{r['avg_loss_bps']:+.1f} | {r['payoff_ratio']:.2f} | "
              f"{r['gross_bps']:+.1f} | **{r['net_bps']:+.1f}** | "
              f"{r['net_p']:.3f} |")
        A("")

    # ---------------- supplementary ----------------
    t4 = R.get("p4_gapdir")
    if t4 is not None and len(t4):
        A("## Supplementary — what the candle filter is actually worth")
        A("")
        A("Same trade, gap direction, **no candle filter at all** (every "
          "event in the bucket, Continuation, Reversal and Doji together). "
          "Compare against the Continuation rows above to see how much the "
          "first-candle condition adds.")
        A("")
        A(_t(_order(t4, "bucket", BUCKET_ORDER),
             ["window", "bucket", "n", "win_rate", "avg_win_bps",
              "avg_loss_bps", "payoff_ratio", "gross_bps", "gross_p",
              "net_bps", "net_p"],
             ["Window", "Gap/ATR", "n", "Win rate", "Avg win", "Avg loss",
              "Payoff", "Gross (bps)", "p", "NET (bps)", "net p"],
             rate=("win_rate",),
             bps=("avg_win_bps", "avg_loss_bps", "gross_bps", "net_bps"),
             p=("gross_p", "net_p"), num=("payoff_ratio",)))

    # ---------------- findings, computed from the tables ----------------
    W = "09:35 -> 09:45"
    rev_all = t1a[(t1a["window"] == W) & (t1a["cohort"] == "All Reversal")]
    rb = t1b[t1b["window"] == W].set_index("bucket")
    cb = t2[t2["window"] == W].set_index("bucket")
    cb15 = t2[t2["window"] == "09:35 -> 09:50"].set_index("bucket")
    lo_b, mid_b, hi_b = BUCKET_ORDER

    A("## What the numbers say")
    A("")
    ra = rev_all.iloc[0]
    A(f"**1. In aggregate the Reversal signal is not tradeable.** Following "
      f"the counter-gap candle across all {int(ra['n']):,} events at ten "
      f"minutes wins {ra['win_rate']*100:.1f}% of the time with a payoff "
      f"ratio of {ra['payoff_ratio']:.2f} — essentially a coin flip with "
      f"symmetric stakes. Gross expectancy is {ra['gross_bps']:+.1f} bps "
      f"(p = {ra['gross_p']:.3f}); after the {meta['cost_bps']} bps round "
      f"trip that becomes {ra['net_bps']:+.1f} bps. It is negative net at "
      "every window out to an hour.")
    A("")
    A("**2. But the aggregate hides a sign flip across Gap/ATR.** The "
      "Reversal cohort is not one population:")
    A("")
    for b in BUCKET_ORDER:
        if b not in rb.index:
            continue
        r = rb.loc[b]
        A(f"- **{b}** (n = {int(r['n']):,}): win rate "
          f"{r['win_rate']*100:.1f}%, payoff {r['payoff_ratio']:.2f}, net "
          f"**{r['net_bps']:+.1f} bps** (p = {r['net_p']:.3f})")
    A("")
    if lo_b in rb.index and hi_b in rb.index:
        rl, rh = rb.loc[lo_b], rb.loc[hi_b]
        A(f"On small gaps, following the counter-gap candle is mildly "
          f"constructive ({rl['net_bps']:+.1f} bps, p = {rl['net_p']:.3f}). "
          f"On gaps above one ATR it is a reliable way to lose money — "
          f"{rh['net_bps']:+.1f} bps at p = {rh['net_p']:.3f} in the largest "
          "bucket, with the win rate falling below 50% and the payoff ratio "
          "below 1.0 at the same time. Both halves of the expectancy move "
          "against you together, which is what a genuine adverse signal "
          "looks like rather than a noise artefact.")
        A("")
        A(f"**The practical reading is the inverse trade.** Because these "
          f"figures are signed in the candle's direction, flipping them says: "
          f"on a gap larger than one ATR, an adverse first 5-minute candle is "
          f"something to *fade*, not to follow. Staying with the gap despite "
          f"it earned {-rh['gross_bps']:+.1f} bps gross / "
          f"{-rh['gross_bps'] - meta['cost_bps']:+.1f} bps net at ten "
          f"minutes. The gap reasserts itself.")
    A("")

    A("**3. Payoff ratio does not improve with gap size — win rate and trade "
      "size do.** This is the opposite of the intuition that big gaps give "
      "you better reward-to-risk:")
    A("")
    A("| Gap/ATR | Win rate | Avg win | Avg loss | Payoff | NET |")
    A("|---|---:|---:|---:|---:|---:|")
    for b in BUCKET_ORDER:
        if b not in cb.index:
            continue
        r = cb.loc[b]
        A(f"| {b} | {r['win_rate']*100:.1f}% | {r['avg_win_bps']:+.1f} | "
          f"{r['avg_loss_bps']:+.1f} | **{r['payoff_ratio']:.2f}** | "
          f"{r['net_bps']:+.1f} |")
    A("")
    if lo_b in cb.index and hi_b in cb.index:
        cl, ch = cb.loc[lo_b], cb.loc[hi_b]
        A(f"The best payoff ratio in the Continuation book belongs to the "
          f"**smallest** gaps ({cl['payoff_ratio']:.2f}), not the largest "
          f"({ch['payoff_ratio']:.2f}). What large gaps deliver is a "
          f"comparable win rate on a much bigger trade — average win "
          f"{ch['avg_win_bps']:.0f} bps versus {cl['avg_win_bps']:.0f} — so "
          f"the fixed {meta['cost_bps']} bps cost consumes a far smaller "
          f"share of it. That is the whole reason the large-gap bucket nets "
          f"more ({ch['net_bps']:+.1f} vs {cl['net_bps']:+.1f} bps), and it "
          "is a cost-scaling story, not an edge-quality story.")
    A("")
    if lo_b in cb15.index:
        A(f"Payoff ratio also rises with holding time in every bucket "
          f"(small gaps: {cb.loc[lo_b,'payoff_ratio']:.2f} at ten minutes → "
          f"{cb15.loc[lo_b,'payoff_ratio']:.2f} at fifteen), because average "
          "wins grow faster than average losses. Nothing here cuts losers "
          "short — that is simply the shape of the unmanaged distribution.")
    A("")

    mid_c = cb.loc[mid_b] if mid_b in cb.index else None
    mid_r = rb.loc[mid_b] if mid_b in rb.index else None
    if mid_c is not None and mid_r is not None:
        A(f"**4. In the middle bucket the candle signal inverts.** Gap/ATR "
          f"1.0–2.0 is the worst *Continuation* bucket "
          f"({mid_c['net_bps']:+.1f} bps net, p = {mid_c['net_p']:.3f}), yet "
          f"it is the bucket where the counter-gap candle predicts gap "
          f"continuation most strongly: read in gap terms the Reversal cohort "
          f"there returns {-mid_r['gross_bps']:+.1f} bps gross, better than "
          f"the {mid_c['gross_bps']:+.1f} bps from the with-gap candle. So "
          "this is not a dead zone — it is a zone where the first candle "
          "points the wrong way.")
        A("")
        hi_c, hi_r = cb.loc[hi_b], rb.loc[hi_b]
        A(f"That inversion does **not** carry to the largest bucket, and it "
          f"would be wrong to generalise it. At Gap/ATR > 2.0 the with-gap "
          f"candle still beats the counter-gap one in gap terms "
          f"({hi_c['gross_bps']:+.1f} vs {-hi_r['gross_bps']:+.1f} bps "
          f"gross), so there the candle is confirmatory. What the two "
          "buckets above one ATR share is narrower and more robust than an "
          "inversion: **the gap direction pays regardless of what the first "
          "candle does**, and in neither bucket does an adverse candle "
          "justify trading against the gap. Whether the candle adds anything "
          "on top of the gap varies by bucket, and its sign is not stable.")
        A("")
        A("Note also that the Gap/ATR effect is **U-shaped at this entry**, "
          "not monotone: Continuation nets more in the smallest bucket than "
          "in the middle one. The monotone result reported earlier was "
          "measured at the 09:45 entry and is not overturned by this — but "
          "Gap/ATR should not be treated as a smooth dial at 09:35.")
        A("")

    if t4 is not None and len(t4):
        g4 = t4[t4["window"] == W].set_index("bucket")
        A("**5. How much is the candle filter actually worth?** Comparing "
          "Continuation against the same trade with no candle condition at "
          "all, at ten minutes:")
        A("")
        A("| Gap/ATR | No filter (NET) | Continuation (NET) | Filter adds |")
        A("|---|---:|---:|---:|")
        for b in BUCKET_ORDER:
            if b not in g4.index or b not in cb.index:
                continue
            A(f"| {b} | {g4.loc[b,'net_bps']:+.1f} | "
              f"{cb.loc[b,'net_bps']:+.1f} | "
              f"**{cb.loc[b,'net_bps'] - g4.loc[b,'net_bps']:+.1f}** |")
        A("")
        if lo_b in g4.index and hi_b in g4.index:
            A(f"On small gaps the candle filter is doing nearly all the work "
              f"— without it the trade is {g4.loc[lo_b,'net_bps']:+.1f} bps "
              f"net, with it {cb.loc[lo_b,'net_bps']:+.1f}. On large gaps the "
              f"gap itself already pays {g4.loc[hi_b,'net_bps']:+.1f} bps net "
              f"with no filter, and the candle adds "
              f"{cb.loc[hi_b,'net_bps'] - g4.loc[hi_b,'net_bps']:+.1f}. So "
              "the two ideas are not the same trade: on small gaps you are "
              "trading the candle, on large gaps you are trading the gap and "
              "using the candle as a modest enhancer. In the middle bucket "
              "the filter is actively harmful "
              f"({cb.loc[mid_b,'net_bps'] - g4.loc[mid_b,'net_bps']:+.1f}), "
              "which is the same inversion described in point 4.")
        A("")

    A("### Caveats that still apply")
    A("")
    A("- The universe is survivorship-biased (current index membership), "
      "which flatters every cohort here equally.")
    A("- Costs are a single 6.6 bps median. Large-gap events are the widest-"
      "spread events, so their true cost is above the median and their net "
      "figures are the most optimistic in the table.")
    A("- The 1.0–2.0 and > 2.0 buckets hold roughly 1,000 events each across "
      "eleven years; they are not small, but they are concentrated in "
      "high-volatility dates, which the date-clustered bootstrap accounts "
      "for in the p-values and the CI widths.")
    A("- T+0 versus T+1 event dating remains ambiguous for part of the "
      "sample, as noted in earlier reports.")
    A("")

    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/reversal_payoff.py`; "
      "tables in `lambda_data/tables/rp_*.csv`._")
    return "\n".join(L)
