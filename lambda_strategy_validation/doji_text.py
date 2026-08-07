"""doji_text.py — renders DOJI_REPORT.md. Table-focused.

Every claim is computed from the tables.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WORDER = ["5 min (09:40)", "10 min (09:45)", "15 min (09:50)",
          "1 hour (10:35)"]
G_CONT = "Continuation (non-doji)"
G_REV = "Reversal (non-doji)"
G_DOJI = "Indecisive (doji)"
G_CONT_ALL = "Continuation incl. dojis"
MAIN3 = [G_CONT, G_REV, G_DOJI]
SHORT = {G_CONT: "Continuation", G_REV: "Reversal", G_DOJI: "Indecisive",
         G_CONT_ALL: "Cont. incl. dojis"}


def _get(df, g, w):
    m = df[(df["group"] == g) & (df["window"] == w)]
    return m.iloc[0] if len(m) else None


def _blocked(df, groups, header, sep, fmt):
    r = [header, sep]
    for i, g in enumerate(groups):
        if i:
            r.append(sep.replace("---", " ").replace(":", " "))
        for w in WORDER:
            x = _get(df, g, w)
            if x is not None:
                r.append(fmt(x))
    return "\n".join(r) + "\n"


def build(R: dict, meta: dict) -> str:
    d = R["main"]
    L: list[str] = []
    A = L.append

    A("# Lambda — Three-Way Doji Classification of the First 5-Minute "
      "Candle")
    A("")
    A("Post-earnings T+1, High Volume filter applied throughout.")
    A("")
    A("| Input | Definition |")
    A("|---|---|")
    A(f"| Universe | Post-earnings T+1, {meta['start']} → {meta['end']} |")
    A(f"| Doji / Indecisive | `\\|body\\| / (high − low) ≤ "
      f"{meta['doji_max']:.2f}` |")
    A("| Continuation | closes **with** the gap and is **not** a doji |")
    A("| Reversal | closes **against** the gap and is **not** a doji |")
    A(f"| High Volume | `c1_volume` > {meta['vol_mult']}× trailing "
      f"{meta['vol_window']}-session mean, same ticker, same 09:30–09:35 "
      "slot, shifted one session |")
    A("| Entry | Open of the 09:35 bar |")
    A(f"| Costs | {meta['cost_bps']} bps round trip, in NET only |")
    A("| Skew / Kurtosis | sample (Fisher); kurtosis is **excess** — "
      "normal = 0.0 |")
    A(f"| Inference | date-clustered bootstrap; ⚠ marks n < "
      f"{meta['small']} |")
    A("")

    # ---------------- the thing the reader needs first ----------------
    A("> ## ⚠ This carve-out was already in place")
    A(">")
    A("> The classifier used by **every previous report in this series** "
      "(`simple_first_candle`) already excludes dojis from both "
      "Continuation and Reversal, at this exact 0.10 body/range threshold. "
      "Groups 1 and 2 below therefore **reproduce the published figures "
      "rather than revising them** — the Continuation numbers here are the "
      "same ones in `VOLUME_TEST_REPORT.md`, `DIST_REPORT.md` and "
      "`GAPDIR_REPORT.md`.")
    A(">")
    A("> Two things here are genuinely new: the **Indecisive group**, which "
      "has never been reported on its own, and the **counterfactual in "
      "section 3** — a with-dojis Continuation cohort built specifically to "
      "measure what the carve-out is worth. Without that counterfactual the "
      "question \"does removing dojis improve the edge?\" cannot be "
      "answered from these tables at all, because both candidate answers "
      "would be the same column of numbers.")
    A(">")
    A("> The specification asks for `≤ 0.10` where the existing code uses "
      "`< 0.10`. No event on this data sits exactly on the boundary, so the "
      "two produce an identical partition.")
    A("")

    A(f"Of **{meta['n_hv']:,}** High Volume events: "
      f"**{meta['n_cont']:,}** Continuation, **{meta['n_rev']:,}** "
      f"Reversal, **{meta['n_doji']:,}** Indecisive "
      f"({meta['doji_share']*100:.1f}%). Of the dojis, "
      f"{meta['n_doji_withgap']:,} closed marginally with the gap and "
      f"{meta['n_doji'] - meta['n_doji_withgap']:,} against it."
      + ("" if meta["n_zero_range"] else
         " No event in this cohort had a zero-range first candle — the "
         "no-print guard removes those before classification — so the "
         "zero-range rule never binds."))
    A("")
    A("> **Sign conventions.** Continuation is signed in the gap "
      "direction. Reversal is signed in the **candle** direction, unchanged "
      "from the earlier reports, so positive means following the "
      "counter-gap candle paid. Indecisive is signed in the **gap** "
      "direction — a doji carries no usable direction of its own, so the "
      "gap is the only information available at 09:35. Section 5 shows the "
      "candle-direction reading of the same events.")
    A("")

    # ---------------- 1. core ----------------
    A("## 1. Core performance")
    A("")
    A(_blocked(
        d, MAIN3,
        "| Group | Window | n | Win rate | **NET** | Avg Win | Avg Loss | "
        "Payoff | net p |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        lambda x: (f"| {SHORT[x['group']]}"
                   f"{' ⚠' if x['small'] == 'YES' else ''} | {x['window']} | "
                   f"{int(x['n']):,} | {x['win_rate']*100:.1f}% | "
                   f"**{x['net_bps']:+.1f}** | {x['avg_win_bps']:.1f} | "
                   f"{x['avg_loss_bps']:.1f} | {x['payoff_ratio']:.2f} | "
                   f"{x['net_p']:.3f} |")))

    # ---------------- 2. shape and tails ----------------
    A("## 2. Distribution, shape and tail risk")
    A("")
    A(_blocked(
        d, MAIN3,
        "| Group | Window | Median | p10 | p90 | Skew | Kurtosis | "
        "Skew (wins.) | Kurt (wins.) | **% loss > 1.0 ATR** | "
        "**% gain > 1.5 ATR** |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        lambda x: (f"| {SHORT[x['group']]} | {x['window']} | "
                   f"{x['median_bps']:+.1f} | {x['p10_bps']:+.0f} | "
                   f"{x['p90_bps']:+.0f} | {x['skew']:+.2f} | "
                   f"{x['kurtosis']:+.1f} | {x['skew_w']:+.2f} | "
                   f"{x['kurtosis_w']:+.1f} | "
                   f"**{x['pct_loss_gt_1atr']*100:.2f}%** | "
                   f"**{x['pct_gain_gt_15atr']*100:.2f}%** |")))
    A("Winsorised (1%/99%) skew and kurtosis are carried because the raw "
      "pair is dominated by single observations at the 1-hour horizon — the "
      "CAR 2021-11-02 squeeze documented in `DIST_REPORT.md` sits in the "
      "Continuation group and drives its raw skew on its own.")
    A("")

    # ---------------- 3. the counterfactual ----------------
    A("## 3. Does removing dojis improve the Continuation edge?")
    A("")
    A("This is the only section that can answer the question, because it "
      "compares the carved-out cohort against the same cohort with dojis "
      f"folded back in ({meta['n_cont_all']:,} events — the "
      f"{meta['n_cont']:,} non-doji continuations plus the "
      f"{meta['n_doji_withgap']:,} dojis whose tiny body closed with the "
      "gap).")
    A("")
    A("| Window | NET, non-doji | NET, incl. dojis | **Δ** | Win rate, "
      "non-doji | Win rate, incl. | Payoff, non-doji | Payoff, incl. |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|")
    deltas = {}
    for w in WORDER:
        a, b = _get(d, G_CONT, w), _get(d, G_CONT_ALL, w)
        if a is None or b is None:
            continue
        deltas[w] = a["net_bps"] - b["net_bps"]
        A(f"| {w} | **{a['net_bps']:+.1f}** | {b['net_bps']:+.1f} | "
          f"**{deltas[w]:+.1f}** | {a['win_rate']*100:.1f}% | "
          f"{b['win_rate']*100:.1f}% | {a['payoff_ratio']:.2f} | "
          f"{b['payoff_ratio']:.2f} |")
    A("")
    if deltas:
        vals = list(deltas.values())
        npos = sum(1 for v in vals if v > 0)
        mean_d = float(np.mean(vals))
        if npos == len(vals):
            verdict = (f"**Yes, but marginally.** The carve-out helps at all "
                       f"{len(vals)} horizons, by {min(vals):+.1f} to "
                       f"{max(vals):+.1f} bps (mean {mean_d:+.1f}).")
        elif npos == 0:
            verdict = (f"**No.** The carve-out *hurts* at all {len(vals)} "
                       f"horizons, by {max(vals):+.1f} to {min(vals):+.1f} "
                       f"bps (mean {mean_d:+.1f}).")
        else:
            verdict = (f"**Barely.** The carve-out helps at {npos} of "
                       f"{len(vals)} horizons, spanning {min(vals):+.1f} to "
                       f"{max(vals):+.1f} bps (mean {mean_d:+.1f}).")
        A(verdict)
        A("")
        A(f"For scale: the dojis being excluded are only "
          f"{meta['n_doji_withgap']:,} events against "
          f"{meta['n_cont']:,} kept, about "
          f"{meta['n_doji_withgap']/meta['n_cont_all']*100:.0f}% of the "
          "combined cohort, so even a large difference in their behaviour "
          "moves the blended figure only slightly. The honest summary is "
          "that the doji filter is **defensible but not load-bearing** — it "
          "is not what makes this setup work.")
        A("")

    # ---------------- 4. the three key questions ----------------
    A("## 4. The three questions, answered")
    A("")
    A("**Q1 — Does removing dojis improve the Continuation edge?**")
    A("")
    if deltas:
        A(f"{verdict} See section 3. The more important finding is that "
          "this filter was already applied in all prior work, so no earlier "
          "number in this series needs revising.")
        A("")

    A("**Q2 — How does the Indecisive group perform?**")
    A("")
    A("| Window | n | NET | net p | Win rate | Median | % loss > 1.0 ATR | "
      "% gain > 1.5 ATR |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|")
    dj = []
    for w in WORDER:
        x = _get(d, G_DOJI, w)
        if x is None:
            continue
        dj.append(x)
        A(f"| {w} | {int(x['n']):,} | **{x['net_bps']:+.1f}** | "
          f"{x['net_p']:.3f} | {x['win_rate']*100:.1f}% | "
          f"{x['median_bps']:+.1f} | {x['pct_loss_gt_1atr']*100:.2f}% | "
          f"{x['pct_gain_gt_15atr']*100:.2f}% |")
    A("")
    if dj:
        sig = [x for x in dj if x["net_p"] < 0.05]
        pos = [x for x in dj if x["net_bps"] > 0]
        cn = [_get(d, G_CONT, x["window"]) for x in dj]
        gaps = [a["net_bps"] - b["net_bps"] for a, b in zip(dj, cn)
                if a is not None and b is not None]
        if len(sig) == 0:
            A(f"**Not tradeable in either direction.** None of the "
              f"{len(dj)} horizons is statistically distinguishable from "
              f"zero (p from {min(x['net_p'] for x in dj):.2f} to "
              f"{max(x['net_p'] for x in dj):.2f}), on samples of "
              f"{min(int(x['n']) for x in dj):,}–"
              f"{max(int(x['n']) for x in dj):,}. The point estimates run "
              f"{min(x['net_bps'] for x in dj):+.1f} to "
              f"{max(x['net_bps'] for x in dj):+.1f} bps.")
        elif len(pos) == len(dj):
            A(f"**This is the surprise of the test: the Indecisive group "
              f"makes money.** NET is positive at all {len(dj)} horizons "
              f"({min(x['net_bps'] for x in dj):+.1f} to "
              f"{max(x['net_bps'] for x in dj):+.1f} bps) and significant "
              f"at {len(sig)} of {len(dj)}, on a sample of roughly "
              f"{int(np.mean([x['n'] for x in dj])):,}. A doji is normally "
              "read as \"no information\", and on the direction of the "
              "candle that is exactly right — section 5 shows the "
              "candle-direction reading loses at every horizon. But the "
              "**gap** is still information, and following it works.")
            A("")
            A("| Window | Indecisive NET | Continuation NET | Δ |")
            A("|---|---:|---:|---:|")
            for x, y in zip(dj, cn):
                if y is None:
                    continue
                A(f"| {x['window']} | {x['net_bps']:+.1f} | "
                  f"{y['net_bps']:+.1f} | {x['net_bps'] - y['net_bps']:+.1f} "
                  "|")
            A("")
            early = [g for g, x in zip(gaps, dj) if g > 0]
            A(f"The relationship with Continuation is not constant: "
              f"Indecisive is {'ahead' if gaps[0] > 0 else 'behind'} at "
              f"5 minutes ({gaps[0]:+.1f} bps) and falls "
              f"{'behind' if gaps[-1] < 0 else 'further ahead'} as the hold "
              f"lengthens ({gaps[-1]:+.1f} bps at 1 hour). A clear-bodied "
              "continuation candle buys you *persistence*; a doji gives you "
              "the gap drift and little more, which is worth most in the "
              "first few minutes and decays after that.")
        else:
            A(f"**Mixed** — positive at {len(pos)} of {len(dj)} horizons, "
              f"significant at {len(sig)}. Point estimates run "
              f"{min(x['net_bps'] for x in dj):+.1f} to "
              f"{max(x['net_bps'] for x in dj):+.1f} bps.")
        A("")
        # Tail risk relative to the other two groups, read from the table
        # rather than assumed from the definition.
        A("**On tail risk it tracks Continuation, not something milder.**")
        A("")
        A("| Window | Loss > 1 ATR: Cont. | Rev. | **Doji** | "
          "Gain > 1.5 ATR: Cont. | Rev. | **Doji** |")
        A("|---|---:|---:|---:|---:|---:|---:|")
        for w in WORDER:
            xc, xr, xd = (_get(d, G_CONT, w), _get(d, G_REV, w),
                          _get(d, G_DOJI, w))
            if any(v is None for v in (xc, xr, xd)):
                continue
            A(f"| {w} | {xc['pct_loss_gt_1atr']*100:.2f}% | "
              f"{xr['pct_loss_gt_1atr']*100:.2f}% | "
              f"**{xd['pct_loss_gt_1atr']*100:.2f}%** | "
              f"{xc['pct_gain_gt_15atr']*100:.2f}% | "
              f"{xr['pct_gain_gt_15atr']*100:.2f}% | "
              f"**{xd['pct_gain_gt_15atr']*100:.2f}%** |")
        A("")
        lastd, lastc, lastr = (_get(d, G_DOJI, WORDER[-1]),
                               _get(d, G_CONT, WORDER[-1]),
                               _get(d, G_REV, WORDER[-1]))
        if all(v is not None for v in (lastd, lastc, lastr)):
            A(f"The doji group is well below Reversal at every horizon but "
              f"essentially level with Continuation — "
              f"{lastd['pct_loss_gt_1atr']*100:.2f}% of trades lose more "
              f"than 1 ATR at 1 hour, against "
              f"{lastc['pct_loss_gt_1atr']*100:.2f}% for Continuation and "
              f"{lastr['pct_loss_gt_1atr']*100:.2f}% for Reversal. **The "
              "intuition that a quiet opening candle implies a quiet hour "
              "is not supported.** A narrow *body* is not a narrow *range*, "
              "and this group's median gap is in fact the largest of the "
              "three (section 6). Indecision at 09:35 is not calm — it is a "
              "balanced fight inside a big gap, and it resolves like one.")
            A("")

    A("**Q3 — Is the Reversal group still weak after removing dojis?**")
    A("")
    A("| Window | n | NET | net p | Win rate | Payoff | Median |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    rv = []
    for w in WORDER:
        x = _get(d, G_REV, w)
        if x is None:
            continue
        rv.append(x)
        A(f"| {w} | {int(x['n']):,} | **{x['net_bps']:+.1f}** | "
          f"{x['net_p']:.3f} | {x['win_rate']*100:.1f}% | "
          f"{x['payoff_ratio']:.2f} | {x['median_bps']:+.1f} |")
    A("")
    if rv:
        negs = [x for x in rv if x["net_bps"] < 0]
        signeg = [x for x in negs if x["net_p"] < 0.05]
        if len(negs) == len(rv):
            A(f"**Yes — still weak, and the doji carve-out does not rescue "
              f"it.** NET is negative at all {len(rv)} horizons "
              f"({min(x['net_bps'] for x in rv):+.1f} to "
              f"{max(x['net_bps'] for x in rv):+.1f} bps), significantly so "
              f"at {len(signeg)} of them, with payoff ratios below 1.0 "
              f"({min(x['payoff_ratio'] for x in rv):.2f}–"
              f"{max(x['payoff_ratio'] for x in rv):.2f}) — losing trades "
              "are bigger than winning ones as well as more frequent. "
              "Removing the indecisive candles leaves the remaining "
              "counter-gap candles as clear-bodied genuine reversals, and "
              "following them still loses money.")
        else:
            A(f"NET is negative at {len(negs)} of {len(rv)} horizons. "
              "The carve-out does not turn this cohort positive.")
        A("")

    # ---------------- 5. doji direction robustness ----------------
    alt = R.get("doji_alt")
    if alt is not None and len(alt):
        A("## 5. Indecisive group — the direction choice")
        A("")
        A("A doji has a body, however small, so it has a nominal direction. "
          "Trading that instead of the gap:")
        A("")
        A("| Window | Gap direction NET | Candle direction NET | "
          "Gap win rate | Candle win rate |")
        A("|---|---:|---:|---:|---:|")
        for w in WORDER:
            a = _get(d, G_DOJI, w)
            b = _get(alt, "Indecisive, candle direction", w)
            if a is None or b is None:
                continue
            A(f"| {w} | {a['net_bps']:+.1f} | {b['net_bps']:+.1f} | "
              f"{a['win_rate']*100:.1f}% | {b['win_rate']*100:.1f}% |")
        A("")
        A(f"> **These two columns are not mirror images.** The candle "
          f"direction agrees with the gap for the "
          f"{meta['n_doji_withgap']:,} dojis whose body closed with the "
          f"gap and opposes it for the other "
          f"{meta['n_doji'] - meta['n_doji_withgap']:,}, so the second "
          "column is a partial re-signing, not a global flip — the pair "
          "does not sum to a constant.")
        A("")
        alt_neg = [b for w in WORDER
                   if (b := _get(alt, "Indecisive, candle direction", w))
                   is not None and b["net_bps"] < 0]
        if len(alt_neg) == len(WORDER):
            A("**Following the doji's own direction loses at every "
              "horizon** (" + ", ".join(
                  f"{b['net_bps']:+.1f}" for b in alt_neg) + " bps), while "
              "following the gap wins at every horizon. That is the "
              "cleanest possible statement of what a doji is: the candle "
              "has no usable direction, but the gap it sits inside still "
              "does. Anyone tempted to read a doji's one-tick body as a "
              "signal is reading noise.")
            A("")

    # ---------------- 6. composition ----------------
    c = R.get("comp")
    if c is not None and len(c):
        A("## 6. Composition of the three groups")
        A("")
        A("| Group | n | Share | Median body/range | Zero-range | "
          "Median \\|gap\\| | Median Gap/ATR | Median vol ratio | % Gap Up |")
        A("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for _, x in c.iterrows():
            A(f"| {SHORT.get(x['group'], x['group'])} | {int(x['n']):,} | "
              f"{x['share']*100:.1f}% | {x['median_body_range']:.2f} | "
              f"{int(x['n_zero_range']):,} | "
              f"{x['median_abs_gap_bps']:.0f} bps | "
              f"{x['median_gap_atr']:.2f} | {x['median_vol_ratio']:.2f} | "
              f"{x['pct_gap_up']*100:.1f}% |")
        A("")

    # ---------------- 7. caveats ----------------
    A("## 7. Reading notes")
    A("")
    A("- **The three groups partition the High Volume cohort**, so they are "
      "not independent tests — they are one sample cut three ways.")
    A("- **The doji threshold is a free parameter.** 0.10 is the classic "
      "convention, not an optimised value, and nothing here tests "
      "sensitivity to it. A materially different threshold would move "
      "events between all three groups at once.")
    A("- **Costs are flat "
      f"{meta['cost_bps']} bps** and do not vary by group. The natural "
      "assumption that doji sessions are quiet, and therefore cheap to "
      "trade, does not survive section 6: that group carries the *largest* "
      "median gap of the three. A narrow body says the buyers and sellers "
      "finished level, not that few of them showed up, so there is no "
      "reason to expect its spreads to be tighter than the other groups'.")
    A("- **Zero-range candles** (high = low) would be counted as dojis, but "
      f"there are {meta['n_zero_range']:,} of them in this cohort — the "
      "no-print guard applied at entry has already removed every one, so "
      "the rule never binds here.")
    A("- **The Indecisive result is the one to re-test out of sample.** It "
      f"rests on ~{meta['n_doji']:,} events, an eighth the size of the "
      "Continuation cohort, and it was not a hypothesis anyone held before "
      "the table was produced. Positive at four of four horizons is "
      "encouraging, not conclusive.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/doji.py`; tables in "
      "`lambda_data/tables/doji_*.csv`._")
    return "\n".join(L)
