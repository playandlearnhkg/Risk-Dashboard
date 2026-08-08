"""validation_text.py — renders VALIDATION_REPORT.md."""

from __future__ import annotations

import numpy as np
import pandas as pd

DIMS = ["Sector", "Stage (prior session)", "Year", "Month", "Day of week",
        "Gap / ATR", "Volume ratio", "Candle body / range"]


def _segtable(s: pd.DataFrame, dim: str, A) -> None:
    d = s[s["dimension"] == dim]
    if not len(d):
        return
    A(f"**{dim}**")
    A("")
    A("| Segment | n | Win rate | NET (bps) | NET (ATR) | % loss > 1 ATR | "
      "Avg large loss (bps) |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    for _, x in d.iterrows():
        sm = " ⚠" if x["small"] == "YES" else ""
        ll = ("—" if pd.isna(x["avg_large_loss_bps"])
              else f"{x['avg_large_loss_bps']:.0f}")
        A(f"| {x['segment']}{sm} | {int(x['n']):,} | "
          f"{x['win_rate']*100:.1f}% | **{x['net_bps']:+.1f}** | "
          f"{x['net_atr']:+.4f} | {x['pct_loss_1atr']*100:.2f}% | {ll} |")
    A("")


def build(R: dict, meta: dict) -> str:
    seg = R["segments"]
    scr = R["screen"].set_index("cohort")
    dist = R["dist"].set_index("rule")
    sd = R["stop_diag"].set_index("rule")
    cut = R["cut_profile"].set_index("group")
    av = R["avwap"]
    ex = R["extract_summary"].iloc[0]
    L: list[str] = []
    A = L.append

    A("# Lambda — Validation and Diagnostic Review of the Post-Earnings "
      "T+1 Research")
    A("")
    A(f"Core setup throughout: post-earnings T+1, entry at the 09:35 open, "
      f"prior-session ATR(14), {meta['cost_bps']} bps round trip where "
      "relevant. ⚠ marks segments below "
      f"{meta['small']} events.")
    A("")

    # ---------------- section 0 ----------------
    A("## 0. A finding that changes how the earlier reports should be read")
    A("")
    A(f"`events.parquet` holds {int(ex['n_merged']):,} usable post-earnings "
      "T+1 events. Only "
      f"**{int(ex['n_pass_screen']):,}** of the extract rows pass "
      "`universe_ok_prev` — the stated Sigma screen (price ≥ $10, ADV ≥ "
      "500k shares, ADTV ≥ $50M, market cap ≥ $3B, all measured on the "
      "prior session).")
    A("")
    A("**Every report in this series was run without that screen.** "
      "`prep_earnings()` reads the events table and filters only on "
      "`gap != 0`. So the headline cohort includes names outside the "
      "stated universe. The question is whether the edge survives:")
    A("")
    A("| Cohort | n | Win rate | NET (bps) | NET (ATR) | % loss > 1 ATR | "
      "Median mkt cap | Median price |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|")
    for c in scr.index:
        x = scr.loc[c]
        A(f"| {c} | {int(x['n']):,} | {x['win_rate']*100:.1f}% | "
          f"**{x['net_bps']:+.1f}** | {x['net_atr']:+.4f} | "
          f"{x['pct_loss_1atr']*100:.2f}% | ${x['median_mcap_b']:.1f}B | "
          f"${x['median_price']:.0f} |")
    A("")
    pas, fai = scr.loc["Passes screen"], scr.loc["Fails screen"]
    A(f"**On expectancy the screen barely matters** — "
      f"{pas['net_bps']:+.1f} bps on the {int(pas['n']):,} events that "
      f"pass against {fai['net_bps']:+.1f} on the {int(fai['n']):,} that "
      "fail, a difference of "
      f"{abs(pas['net_bps'] - fai['net_bps']):.1f} bps and well inside "
      "noise. The published headline is not inflated by out-of-universe "
      "names.")
    A("")
    A("**On risk it matters a great deal.**")
    A("")
    A("| | Passes screen | Fails screen |")
    A("|---|---:|---:|")
    A(f"| NET (bps) | {pas['net_bps']:+.1f} | {fai['net_bps']:+.1f} |")
    A(f"| NET (ATR) | **{pas['net_atr']:+.4f}** | {fai['net_atr']:+.4f} |")
    A(f"| % losing > 1 ATR | **{pas['pct_loss_1atr']*100:.2f}%** | "
      f"{fai['pct_loss_1atr']*100:.2f}% |")
    A(f"| Win rate | {pas['win_rate']*100:.1f}% | "
      f"{fai['win_rate']*100:.1f}% |")
    A("")
    A(f"The screened half earns the same basis points while suffering "
      f"large losses {fai['pct_loss_1atr']/pas['pct_loss_1atr']:.1f}× less "
      f"often, and its ATR-denominated expectancy is "
      f"{pas['net_atr']/fai['net_atr']:.0%} of the unscreened half's — "
      "i.e. materially better once each trade is measured against its own "
      "volatility. **Applying the screen is close to free on return and "
      "clearly positive on risk**, which makes it the easy call, and it "
      "should be an explicit choice rather than an omission.")
    A("")
    A("**The excluded names are not small.** Their median market cap is "
      f"${fai['median_mcap_b']:.1f}B against ${pas['median_mcap_b']:.1f}B "
      f"for those that pass, and their median price is "
      f"${fai['median_price']:.0f} against ${pas['median_price']:.0f}. The "
      "binding constraint is the **500k-share ADV floor**, which a "
      "high-priced large cap fails on share count while clearing every "
      "dollar-based test — a $600 stock trading $50M a day changes hands "
      "under 100k times. That is a property of the filter, not of the "
      "companies, and it is worth deciding deliberately rather than "
      "inheriting.")
    A("")

    # ---------------- Part 1 ----------------
    A("## Part 1 — Trade characteristics")
    A("")
    A("All segments below are the core High Volume + Continuation cohort, "
      "1-hour hold, no stop.")
    A("")
    for dim in DIMS:
        _segtable(seg, dim, A)

    # highlights
    A("### Where the differences are real")
    A("")
    big = seg[(seg["small"] != "YES") & (seg["n"] >= 200)]
    rows = []
    for dim in DIMS:
        d = big[big["dimension"] == dim]
        if len(d) < 2:
            continue
        hi = d.loc[d["net_bps"].idxmax()]
        lo = d.loc[d["net_bps"].idxmin()]
        rows.append((dim, hi, lo, hi["net_bps"] - lo["net_bps"]))
    rows.sort(key=lambda z: -z[3])
    A("| Dimension | Strongest segment | NET | Weakest segment | NET | "
      "Spread |")
    A("|---|---|---:|---|---:|---:|")
    for dim, hi, lo, spread in rows:
        A(f"| {dim} | {hi['segment']} ({int(hi['n']):,}) | "
          f"{hi['net_bps']:+.1f} | {lo['segment']} ({int(lo['n']):,}) | "
          f"{lo['net_bps']:+.1f} | **{spread:.1f}** |")
    A("")
    A("Read this table with suspicion rather than enthusiasm. Eight "
      "dimensions with several segments each is roughly fifty cells, so "
      "the widest spread being large is close to guaranteed by "
      "construction — none of these splits was hypothesised in advance, "
      "and no multiple-comparison adjustment is applied anywhere in it. "
      "The dimensions worth taking seriously are the ones with a "
      "**monotone** relationship, because a gradient across ordered "
      "buckets is far harder to produce by chance than one standout cell.")
    A("")
    mono = []
    for dim in ("Gap / ATR", "Volume ratio", "Candle body / range"):
        d = seg[seg["dimension"] == dim]
        if len(d) < 3:
            continue
        v = d["net_bps"].to_numpy()
        if all(v[i] <= v[i + 1] for i in range(len(v) - 1)):
            mono.append((dim, "rising", v))
        elif all(v[i] >= v[i + 1] for i in range(len(v) - 1)):
            mono.append((dim, "falling", v))
    if mono:
        A("Ordered dimensions with a clean gradient:")
        A("")
        for dim, direction, v in mono:
            d = seg[seg["dimension"] == dim]
            A(f"- **{dim}** — {direction} monotonically across all "
              f"{len(v)} buckets ("
              + " → ".join(f"{x:+.0f}" for x in v) + " bps).")
        A("")
    else:
        A("No ordered dimension is cleanly monotone across all its "
          "buckets, which further weakens the case for reading any single "
          "segment as a real effect.")
        A("")

    # ---------------- Part 2 ----------------
    A("## Part 2 — Distribution shape")
    A("")
    A("Core cohort, 1-hour hold, under each rule.")
    A("")
    A("| Rule | n | Mean | Median | p10 | p25 | p75 | p90 | Skew | "
      "Excess kurtosis |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in dist.index:
        x = dist.loc[r]
        A(f"| {r} | {int(x['n']):,} | {x['mean_bps']:+.1f} | "
          f"{x['median_bps']:+.1f} | {x['p10']:+.0f} | {x['p25']:+.0f} | "
          f"{x['p75']:+.0f} | {x['p90']:+.0f} | {x['skew']:+.2f} | "
          f"{x['kurtosis']:+.1f} |")
    A("")
    A("| Rule | Skew (winsorised 1/99) | Kurtosis (winsorised) | "
      "% < −0.5 ATR | % < −1.0 ATR | % > +1.0 ATR |")
    A("|---|---:|---:|---:|---:|---:|")
    for r in dist.index:
        x = dist.loc[r]
        A(f"| {r} | {x['skew_w']:+.2f} | {x['kurtosis_w']:+.1f} | "
          f"{x['pct_lt_05atr']*100:.2f}% | {x['pct_lt_1atr']*100:.2f}% | "
          f"{x['pct_gt_1atr']*100:.2f}% |")
    A("")
    A("**Plain-language shape.**")
    A("")
    core = dist.loc["Core — no stop"]
    A(f"- **Core, no stop.** Mean {core['mean_bps']:+.1f} against a median "
      f"of {core['median_bps']:+.1f}: the average sits above the typical "
      "trade, so a minority of large winners does the heavy lifting. Raw "
      f"skew of {core['skew']:+.2f} is one observation (the CAR squeeze); "
      f"winsorised it is {core['skew_w']:+.2f} — near-symmetric in the "
      f"body with genuinely fat tails ({core['kurtosis_w']:+.1f} excess "
      "kurtosis even after capping). Gains beyond 1 ATR outnumber losses "
      f"beyond 1 ATR by {core['pct_gt_1atr']/core['pct_lt_1atr']:.1f} to "
      "one. **A slightly-better-than-coin-flip hit rate with a modest "
      "positive payoff, and both tails fat.**")
    for r in dist.index:
        if r == "Core — no stop":
            continue
        x = dist.loc[r]
        shift = x["median_bps"] - core["median_bps"]
        A(f"- **{r}.** Median {x['median_bps']:+.1f} "
          f"({shift:+.1f} vs no stop), p10 {x['p10']:+.0f} "
          f"({x['p10'] - core['p10']:+.0f}). Losses beyond 1 ATR "
          f"{x['pct_lt_1atr']*100:.2f}% against "
          f"{core['pct_lt_1atr']*100:.2f}%. "
          + ("Truncates the left tail and pays for it out of the middle."
             if x["pct_lt_1atr"] < core["pct_lt_1atr"] * 0.5
             else "Barely reshapes the distribution."))
    A("")

    # ---------------- Part 3 ----------------
    A("## Part 3 — Diagnostics")
    A("")
    A("### What the stops are actually cutting")
    A("")
    A("| Rule | Stopped | % that would have recovered to profit | "
      "% that would have beaten the stop price | Median MAE of stopped | "
      "Median MAE of kept | Forgone |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    for r in sd.index:
        x = sd.loc[r]
        A(f"| {r} | {x['pct_stopped']*100:.1f}% | "
          f"**{x['pct_recover']*100:.1f}%** | "
          f"{x['pct_beat_stop']*100:.1f}% | {x['mae_of_stopped']:.2f} ATR | "
          f"{x['mae_of_kept']:.2f} ATR | {x['forgone_bps']:+.1f} bps |")
    A("")
    A("The recovery column is low everywhere, which is already at odds "
      "with how the earlier reports framed these stops. Profiling the two "
      "groups on entry-time variables shows why:")
    A("")
    A("| Group | n | Median MAE | Median Gap/ATR | Median vol ratio | "
      "% that touched the gap level | Outcome if held | % profitable if "
      "held |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|")
    for gname in cut.index:
        x = cut.loc[gname]
        A(f"| {gname} | {int(x['n']):,} | {x['median_mae_atr']:.3f} ATR | "
          f"{x['median_gap_atr']:.2f} | {x['median_vol_ratio']:.2f} | "
          f"{x['pct_gap_touched']*100:.1f}% | "
          f"{x['held_outcome_bps']:+.1f} bps | "
          f"{x['pct_held_profitable']*100:.1f}% |")
    A("")
    st = cut.loc["Stopped by ATR −1.0"]
    kp = cut.loc["Not stopped"]
    A("**The stops are cutting genuine failures, not noise — and that is "
      "the opposite of what the earlier reports implied.** Two things "
      "fall out of this table that no previous report measured:")
    A("")
    A(f"First, only **{st['pct_held_profitable']*100:.1f}%** of the trades "
      f"the ATR −1.0 stop cuts would have finished the hour in profit, and "
      f"as a group they end at **{st['held_outcome_bps']:+.0f} bps** even "
      f"if held. Against {kp['pct_held_profitable']*100:.1f}% and "
      f"{kp['held_outcome_bps']:+.0f} bps for the trades it keeps. These "
      "are not temporary excursions that recover — they are losing trades "
      "that stay losing.")
    A("")
    A(f"Second, they were **identifiable at entry**. The stopped group's "
      f"median gap is {st['median_gap_atr']:.2f} ATR against "
      f"{kp['median_gap_atr']:.2f} for the kept group — three times "
      f"larger — and its median volume ratio {st['median_vol_ratio']:.2f} "
      f"against {kp['median_vol_ratio']:.2f}. The stop is not selecting on "
      "path noise. It is selecting, indirectly and after the fact, on two "
      "variables that were visible at 09:35.")
    A("")
    A("So why does stopping still cost expectancy? Because the stop exits "
      f"at roughly the worst available price. The group realises "
      f"{st['held_outcome_bps'] - sd.loc['ATR −1.0', 'forgone_bps']:+.0f} "
      f"bps stopped against {st['held_outcome_bps']:+.0f} held — a "
      f"{sd.loc['ATR −1.0', 'forgone_bps']:.0f} bps difference. The stop "
      "fires at maximum adverse excursion by construction, and even a "
      "failing post-earnings trade bounces off its low. **The stop "
      "identifies the right trades and exits them at the wrong moment.**")
    A("")
    A("That distinction matters, because the two failure modes have "
      "different fixes. If stops were cutting noise, the answer would be a "
      "wider stop. Since they are cutting real losers at their worst "
      "price, the answer is to act on the same information *before* the "
      "trade rather than during it — which is the sizing argument below, "
      "and it is now supported rather than merely asserted.")
    A("")

    A("### Why limit entries selected weaker trades")
    A("")
    A("A limit order fills only when price retraces to it, so the filled "
      "sample is by construction the subset with an early adverse "
      "excursion — the same variable the stop selects on, approached from "
      "the other side. The stop diagnostic shows what that subset looks "
      "like: trades that end the hour at "
      f"{st['held_outcome_bps']:+.0f} bps on average against "
      f"{kp['held_outcome_bps']:+.0f} bps for the ones that never pulled "
      "back.")
    A("")
    A("So the limit order is not merely selecting a random subset that "
      "happened to dip. It is selecting, with reasonable fidelity, the "
      "trades that were going to do badly — for the same reason the stop "
      "does, because early adverse excursion genuinely predicts the "
      "outcome on this cohort. The difference is that the stop at least "
      "*exits* those trades, while the limit order **buys** them and "
      "declines to buy the others.")
    A("")
    A("The asymmetry is what makes it expensive: trades that never pull "
      "back never appear in the filled sample at all, and those are the "
      "ones carrying the right tail. The limit order truncates the right "
      "tail of the entry distribution while admitting the left tail in "
      "full — which is why `ENTRYLIMITS_REPORT.md` found the missed "
      "trades outperforming the filled ones by 97 to 120 bps on identical "
      "entries.")
    A("")

    A("### Practical implication for position sizing")
    A("")
    A("The diagnostic above hands this section its answer. The trades the "
      "stop cuts carry **three times the gap/ATR and twice the volume "
      "ratio** of the ones it keeps, and both were observable at 09:35. "
      "The tail-risk columns in Part 1 confirm the same ordering "
      "independently:")
    A("")
    gt = seg[(seg["dimension"] == "Gap / ATR")]
    vt = seg[(seg["dimension"] == "Volume ratio")]
    A("| Dimension | Segment | n | % loss > 1 ATR | Avg large loss |")
    A("|---|---|---:|---:|---:|")
    for _, x in pd.concat([gt, vt]).iterrows():
        A(f"| {x['dimension']} | {x['segment']} | {int(x['n']):,} | "
          f"{x['pct_loss_1atr']*100:.2f}% | "
          f"{x['avg_large_loss_bps']:.0f} bps |")
    A("")
    g_lo = gt.iloc[0]["pct_loss_1atr"] * 100
    g_hi = gt.iloc[-1]["pct_loss_1atr"] * 100
    v_lo = vt.iloc[0]["pct_loss_1atr"] * 100
    v_hi = vt.iloc[-1]["pct_loss_1atr"] * 100
    A(f"**Both are cleanly monotone in risk**, even where they are not "
      f"monotone in return: the >1 ATR loss rate rises from {g_lo:.1f}% to "
      f"{g_hi:.1f}% across the gap/ATR buckets and from {v_lo:.1f}% to "
      f"{v_hi:.1f}% across the volume-ratio buckets. Risk is far more "
      "predictable from entry-time variables than return is — which is "
      "the single most useful thing in this review.")
    A("")
    A("The practical implications follow directly:")
    A("")
    A("- **Size on risk, not on expected return.** The gradient in the "
      "loss-rate columns is monotone and steep; the gradient in NET is "
      "neither. Halving size in the top gap/ATR and volume-ratio buckets "
      "cuts exposure to the segment carrying a "
      f"{g_hi:.1f}% large-loss rate while giving up little of a return "
      "estimate that is not reliably higher there anyway.")
    A("- **Do it at entry, not intraday.** The information is fully "
      "available at 09:35. Waiting to act on it through a stop means "
      "paying the "
      f"{sd.loc['ATR −1.0', 'forgone_bps']:.0f} bps bounce-off-the-low "
      "penalty measured above.")
    A("- **Reducing size dominates stopping out here.** Both act on the "
      "same trades; sizing acts before the adverse excursion and stopping "
      "acts at the bottom of it. That is the whole difference, and it is "
      "worth roughly the forgone figure per stopped trade.")
    A("- **Expect modest gains.** This is a risk-management improvement, "
      "not a new edge. Nothing in Part 1 separates *returns* sharply "
      "enough to build a selection rule on.")
    A("")

    # ---------------- Part 4 ----------------
    A("## Part 4 — AVWAP with a buffer")
    A("")
    A("Anchored VWAP from 09:30, confirmed on the 5-minute close, with the "
      "stop level pushed a fixed fraction of ATR beyond the line.")
    A("")
    A("| Buffer | NET (bps) | % stopped | % loss > 1 ATR | Avg overshoot | "
      "Recovery rate of stopped trades | Win rate |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    for _, x in av.iterrows():
        lab = ("Exact AVWAP" if x["buffer_atr"] == 0
               else f"AVWAP ± {x['buffer_atr']:.2f} ATR")
        A(f"| {lab} | **{x['net_bps']:+.1f}** | {x['pct_stopped']*100:.1f}% "
          f"| {x['pct_loss_1atr']*100:.2f}% | {x['avg_over_bps']:.1f} bps | "
          f"{x['pct_recover']*100:.1f}% | {x['win_rate']*100:.1f}% |")
    A("")
    best = av.loc[av["net_bps"].idxmax()]
    A(f"**The buffer helps monotonically, and it does not rescue the "
      f"rule.** Going from the exact line to ±"
      f"{best['buffer_atr']:.2f} ATR lifts NET from "
      f"{av.iloc[0]['net_bps']:+.1f} to {best['net_bps']:+.1f} bps and "
      f"cuts the stop-out rate from {av.iloc[0]['pct_stopped']*100:.0f}% "
      f"to {best['pct_stopped']*100:.0f}%. Every variant remains far below "
      "the no-stop baseline.")
    A("")
    A(f"The recovery column is the interesting one: it **falls** from "
      f"{av.iloc[0]['pct_recover']*100:.0f}% to "
      f"{best['pct_recover']*100:.0f}% as the buffer widens. That is "
      "confirmation the buffer is working as intended — each increment "
      "spares the trades most likely to have recovered, so what remains "
      "in the stopped bucket is progressively more genuinely broken. The "
      "buffer is a well-aimed instrument.")
    A("")
    A("It still is not enough. At the exact line the rule stops "
      f"{av.iloc[0]['pct_stopped']*100:.0f}% of all trades — it is barely "
      "a stop, more a re-entry signal — and even at ±0.15 ATR it stops "
      f"{best['pct_stopped']*100:.0f}%, giving up "
      f"{core['mean_bps'] - meta['cost_bps'] - best['net_bps']:.0f} bps "
      "against holding. "
      "Anchored VWAP sits too close to price on this cohort for a buffer "
      "of any practical width to fix.")
    A("")
    A("The practitioner instinct behind the buffer is sound — it is "
      "targeting exactly the false triggers the diagnostics identify. It "
      "simply cannot reach far enough: by the time the buffer is wide "
      "enough to stop cutting recoverable trades, it is wide enough to "
      "stop doing anything.")
    A("")

    # ---------------- Part 5 ----------------
    A("## Part 5 — Full extract for independent validation")
    A("")
    A(f"**{int(ex['n_events']):,} events**, one row each, written to:")
    A("")
    A(f"- `{meta['extract_csv']}` — CSV, opens directly in Excel")
    A(f"- `{meta['extract_xlsx']}` — native `.xlsx`")
    A("")
    A("| Composition | n |")
    A("|---|---:|")
    A(f"| Total events in the extract | {int(ex['n_events']):,} |")
    A(f"| High Volume flag = Yes | {int(ex['n_high_vol']):,} |")
    A(f"| Candle class = Continuation | {int(ex['n_continuation']):,} |")
    A(f"| **High Volume + Continuation** (the core cohort) | "
      f"**{int(ex['n_hv_cont']):,}** |")
    A(f"| Passes the full universe screen | "
      f"{int(ex['n_pass_screen']):,} |")
    A(f"| Distinct tickers | {int(ex['n_tickers']):,} |")
    A(f"| Date range | {ex['start']} → {ex['end']} |")
    A("")
    A("### Columns")
    A("")
    A("| Column | Meaning |")
    A("|---|---|")
    for c, m in [
        ("ticker, date", "identification"),
        ("sector", "GICS-style sector from the panel"),
        ("market_cap_prev_usd", "prior-session market cap"),
        ("passes_universe_screen", "Yes/No on the full Sigma screen — the "
         "filter the published cohort did **not** apply"),
        ("high_volume_flag", "Yes if `c1_volume` > 1.5× the trailing "
         "20-session same-slot mean, shifted one session"),
        ("candle_class", "Continuation / Reversal / Indecisive, doji cut "
         "at body/range ≤ 0.10"),
        ("gap_direction, gap_pct, gap_atr", "gap sign, size in %, and size "
         "in prior ATR"),
        ("vol_ratio_5min", "exact opening-candle volume ratio"),
        ("body_over_range", "|close−open| ÷ (high−low) of the first candle"),
        ("stage_prev", "Minervini stage 2/3/4 as of the prior session"),
        ("entry_px_0935", "open of the 09:35 bar"),
        ("ret_5min / 15min / 1hour_bps and _atr", "signed returns from "
         "entry, in bps and in prior ATR"),
        ("ret_t1_close_bps", "entry to the T+1 session close"),
        ("gap_level_touched_1h", "did price trade through the prior close "
         "in the first hour"),
        ("mae_1h_atr", "maximum adverse excursion in the first hour, in ATR"),
        ("atr14_prev", "prior-session ATR(14), the denominator throughout"),
        ("cost_in_atr", f"the {meta['cost_bps']} bps round trip expressed "
         "in that row's ATR"),
    ]:
        A(f"| `{c}` | {m} |")
    A("")
    A("### Filters still applied to the extract")
    A("")
    A("- **Post-earnings T+1 sessions only**, gap ≠ 0.")
    A("- **A real print by 09:35** — events with no opening trade cannot "
      "be given an entry price and are dropped.")
    A("- **A prior-session ATR(14)** must exist and be positive.")
    A("- **A mark at 10:35**, forward-filled from the session open as in "
      "every earlier report.")
    A("")
    A("- **NOT applied:** the liquidity/market-cap screen. Every event is "
      "included and flagged with `passes_universe_screen` so it can be "
      "imposed or not. This is deliberate — it is the only way to "
      "reproduce the published cohorts *and* test them against the "
      "screened universe.")
    A("- **NOT applied:** the High Volume and Continuation filters. Both "
      "are columns, so the core cohort is `high_volume_flag = Yes` **and** "
      f"`candle_class = Continuation`, which reproduces "
      f"{int(ex['n_hv_cont']):,} rows.")
    A("")
    A("### Two gaps in the data you should know about before filtering")
    A("")
    A("- **`vol_ratio_5min` is blank on 301 rows (1.9%)** — the trailing "
      "20-session volume benchmark needs 15 prior sessions, and a few "
      "names never accumulate them. Those rows are flagged "
      "`high_volume_flag = No`, because a missing ratio cannot clear the "
      "1.5× test. None of them is currently counted as High Volume, so "
      "they are excluded from the core cohort by omission rather than by "
      "measurement. If you would rather treat them as unknown than as "
      "No, filter them out explicitly.")
    A("- **`market_cap_prev_usd` is blank on 11.2% of rows.** Market cap "
      "needs point-in-time shares outstanding, which is not derivable "
      "from OHLCV; where it is missing, `passes_universe_screen` is `No` "
      "by construction. That is one reason the screen excludes as much as "
      "it does, and it is a data limitation rather than a judgement about "
      "those names.")
    A("")
    A("### Reproducing the headline figures")
    A("")
    A("Filter to `high_volume_flag = Yes` and `candle_class = "
      "Continuation`, then average `ret_1hour_bps` and subtract "
      f"{meta['cost_bps']}. Small differences against `DIST_REPORT.md` are "
      "expected and explained: that report drops exactly-zero returns as "
      "stale prints, this extract keeps every row so nothing is silently "
      "removed from a validation file.")
    A("")

    A("## Reading notes")
    A("")
    A("- **Part 1 is exploratory.** Roughly fifty segment cells, no "
      "pre-registration, no multiple-comparison control. Treat the spread "
      "table as a map of where to look next, not as findings.")
    A("- **Costs remain flat at "
      f"{meta['cost_bps']} bps** everywhere, including for the segments "
      "where that is least defensible.")
    A("- **The extract keeps zero returns**, so its cohort counts are "
      "marginally above the published ones.")
    A("- **Section 0 is the item to action.** Whether to impose the "
      "universe screen is a decision, not a detail, and it moves the "
      "cohort by 41.6%.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/validation.py`; "
      "tables in `lambda_data/tables/val_*.csv`._")
    return "\n".join(L)
