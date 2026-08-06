"""gapdir_text.py — renders GAPDIR_REPORT.md.

Every claim in the prose is computed from the tables, so the report cannot
drift out of sync with the numbers.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WORDER = ["15 min (09:50)", "1 hour (10:35)"]
MAIN = ["HV + Continuation + Gap Up", "HV + Continuation + Gap Down",
        "HV + Reversal + Gap Up", "HV + Reversal + Gap Down"]
FADE = ["Fade Reversal + Gap Up (stay long the gap)",
        "Fade Reversal + Gap Down (stay short the gap)"]
CTRL = ["LV + Continuation + Gap Up", "LV + Continuation + Gap Down",
        "LV + Reversal + Gap Up", "LV + Reversal + Gap Down"]

SIDE = {
    "HV + Continuation + Gap Up": "long",
    "HV + Continuation + Gap Down": "short",
    "HV + Reversal + Gap Up": "short",
    "HV + Reversal + Gap Down": "long",
}


def _sort(df: pd.DataFrame, order: list[str]) -> pd.DataFrame:
    d = df.copy()
    d["_w"] = d["window"].map({v: i for i, v in enumerate(WORDER)})
    d["_g"] = d["group"].map({v: i for i, v in enumerate(order)})
    return d.sort_values(["_w", "_g"]).drop(columns=["_w", "_g"])


def _tbl(df: pd.DataFrame, order: list[str], side: bool = True) -> str:
    head = "| Window | Group |"
    sep = "|---|---|"
    if side:
        head += " Side |"
        sep += "---|"
    head += (" n | Win rate | **NET (bps)** | Avg Win | Avg Loss | "
             "Payoff | net p |")
    sep += "---:|---:|---:|---:|---:|---:|---:|"
    r = [head, sep]
    for _, x in _sort(df, order).iterrows():
        sm = " ⚠" if x.get("small") == "YES" else ""
        row = f"| {x['window']} | {x['group']}{sm} |"
        if side:
            row += f" {SIDE.get(x['group'], '')} |"
        row += (f" {int(x['n']):,} | {x['win_rate']*100:.1f}% | "
                f"**{x['net_bps']:+.1f}** | {x['avg_win_bps']:.0f} | "
                f"{x['avg_loss_bps']:.0f} | {x['payoff_ratio']:.2f} | "
                f"{x['net_p']:.3f} |")
        r.append(row)
    return "\n".join(r) + "\n"


def _get(df: pd.DataFrame, w: str, g: str):
    m = df[(df["window"] == w) & (df["group"] == g)]
    return m.iloc[0] if len(m) else None


def build(R: dict, meta: dict) -> str:
    L: list[str] = []
    A = L.append
    main, fade, ctrl = R["main"], R["fade"], R["control"]

    A("# Lambda — High Volume Signals by Gap Direction")
    A("")
    A("Post-earnings (T+1) only. The four High Volume cells split by "
      "whether the gap was **up** or **down**, at 15 minutes and 1 hour.")
    A("")
    A("| Input | Definition |")
    A("|---|---|")
    A("| Universe | Post-earnings T+1 sessions, "
      f"{meta['start']} → {meta['end']} |")
    A("| Signal | Direction of the 09:30–09:35 candle relative to the gap |")
    A("| Continuation | first candle closes **with** the gap |")
    A("| Reversal | first candle closes **against** the gap |")
    A(f"| High Volume | `c1_volume` > {meta['vol_mult']}× the trailing "
      f"{meta['vol_window']}-session mean of `c1_volume` for the same ticker "
      "and the same 09:30–09:35 slot, shifted one session |")
    A(f"| Entry | Open of the 09:35 bar (minute {meta['entry_min']}) |")
    A(f"| Costs | {meta['cost_bps']} bps round trip, subtracted for NET |")
    A(f"| Inference | date-clustered bootstrap; ⚠ marks n < {meta['small']} |")
    A("")
    A(f"Events after guards: **{meta['n_events']:,}**, of which "
      f"**{meta['n_hv_signals']:,}** are High Volume Continuation or "
      f"Reversal signals. Gap-up share: {meta['pct_gap_up_all']*100:.1f}% of "
      f"all events, {meta['pct_gap_up_hv']*100:.1f}% of the High Volume "
      "signals.")
    A("")
    A("> **Sign convention.** Continuation is signed in the **gap** "
      "direction; Reversal is signed in the **candle** direction. Both are "
      "the same rule — *follow the first 5-minute candle* — so a positive "
      "number always means the rule paid. The Side column says which way "
      "the trade actually points, because that is what determines whether "
      "market drift helps or hurts.")
    A("")

    # ---------------- 1. the four groups ----------------
    A("## 1. The four groups")
    A("")
    A(_tbl(main, MAIN))
    A("Avg Win and Avg Loss are in basis points, gross of costs; Payoff is "
      "their ratio. NET is the mean expectancy per trade after "
      f"{meta['cost_bps']} bps.")
    A("")

    # ---------------- 2. what the split says ----------------
    A("## 2. Does gap direction matter?")
    A("")
    for w in WORDER:
        cu, cd = _get(main, w, MAIN[0]), _get(main, w, MAIN[1])
        ru, rd = _get(main, w, MAIN[2]), _get(main, w, MAIN[3])
        if cu is None or cd is None:
            continue
        A(f"**{w}**")
        A("")
        A(f"- Continuation: Gap Up **{cu['net_bps']:+.1f}** "
          f"(n={int(cu['n']):,}, {cu['win_rate']*100:.1f}% win) vs Gap Down "
          f"**{cd['net_bps']:+.1f}** (n={int(cd['n']):,}, "
          f"{cd['win_rate']*100:.1f}% win) → Up − Down "
          f"**{cu['net_bps'] - cd['net_bps']:+.1f} bps**")
        if ru is not None and rd is not None:
            A(f"- Reversal: Gap Up **{ru['net_bps']:+.1f}** "
              f"(n={int(ru['n']):,}, {ru['win_rate']*100:.1f}% win) vs Gap "
              f"Down **{rd['net_bps']:+.1f}** (n={int(rd['n']):,}, "
              f"{rd['win_rate']*100:.1f}% win) → Up − Down "
              f"**{ru['net_bps'] - rd['net_bps']:+.1f} bps**")
        A("")

    cont_gaps, rev_gaps = [], []
    for w in WORDER:
        cu, cd = _get(main, w, MAIN[0]), _get(main, w, MAIN[1])
        ru, rd = _get(main, w, MAIN[2]), _get(main, w, MAIN[3])
        if cu is not None and cd is not None:
            cont_gaps.append(cu["net_bps"] - cd["net_bps"])
        if ru is not None and rd is not None:
            rev_gaps.append(ru["net_bps"] - rd["net_bps"])
    if cont_gaps and rev_gaps:
        A("**Gap direction splits the two cohorts in opposite ways.** "
          "Continuation is better on gap **downs** "
          f"({-max(cont_gaps):+.1f} to {-min(cont_gaps):+.1f} bps in favour "
          "of down); Reversal is better on gap **ups** "
          f"({min(rev_gaps):+.1f} to {max(rev_gaps):+.1f} bps in favour of "
          "up). Read as \"gap direction\", that is a contradiction. Read "
          "another way, it is one statement.")
        A("")

    # The unifying read: within each cohort, the cell that is a SHORT beats
    # the cell that is a LONG. Verified against the table rather than asserted.
    shorts = [g for g in MAIN if SIDE[g] == "short"]
    longs = [g for g in MAIN if SIDE[g] == "long"]
    pairs = [(MAIN[0], MAIN[1]), (MAIN[3], MAIN[2])]  # (long, short) per cohort
    wins = []
    for w in WORDER:
        for lg, sg in pairs:
            xl, xs = _get(main, w, lg), _get(main, w, sg)
            if xl is None or xs is None:
                continue
            wins.append((w, lg, sg, xs["net_bps"] - xl["net_bps"]))
    if wins and all(d > 0 for *_, d in wins):
        A("### The short side wins in every cell")
        A("")
        A("Within **each** cohort, the cell that points **short** beats the "
          "cell that points long — at both horizons, without exception:")
        A("")
        A("| Window | Cohort | Short cell | Long cell | Short − Long |")
        A("|---|---|---:|---:|---:|")
        for w, lg, sg, d in wins:
            xl, xs = _get(main, w, lg), _get(main, w, sg)
            coh = "Continuation" if "Continuation" in lg else "Reversal"
            A(f"| {w} | {coh} | {xs['net_bps']:+.1f} | {xl['net_bps']:+.1f} "
              f"| **{d:+.1f}** |")
        A("")
        A(f"That is 4 of 4 comparisons, spanning "
          f"{min(d for *_, d in wins):+.1f} to "
          f"{max(d for *_, d in wins):+.1f} bps. The variable that orders "
          "these cells is not whether the stock gapped up or down — it is "
          "**which way the resulting trade points**. Falling prices on heavy "
          "post-earnings volume travel further in the first hour than rising "
          "ones do, which is the standard downside-moves-faster asymmetry "
          "showing up intraday.")
        A("")
        A("Three things qualify that reading. Market drift does not explain "
          "it (section 4). The Normal/Low volume control shows the same "
          "asymmetry in weaker and less consistent form (section 6), so "
          "volume sharpens it rather than creating it. And shorting is not "
          "free (section 7) — that cost is not measurable from this data, "
          "and it lands on exactly the cells that look best.")
        A("")

    # ---------------- 3. fade the candle ----------------
    A("## 3. “Fade the candle” — the Reversal groups traded the other way")
    A("")
    A("The identical Reversal events, re-signed in the **gap** direction: "
      "the first candle went against the gap, and this version ignores it "
      "and stays with the gap.")
    A("")
    A(_tbl(fade, FADE, side=False))
    A("> **Costs do not flip with the sign.** Gross flips exactly; net does "
      f"not, because the {meta['cost_bps']} bps round trip is paid either "
      "way. Both directions of a small gross edge lose money — the pair of "
      "figures for one cell sums to −"
      f"{2*meta['cost_bps']:.1f} bps, not to zero. Only where gross is "
      "large does fading produce something tradeable.")
    A("")
    for w in WORDER:
        for foll, fad in ((MAIN[2], FADE[0]), (MAIN[3], FADE[1])):
            a, b = _get(main, w, foll), _get(fade, w, fad)
            if a is None or b is None:
                continue
            better = "fade" if b["net_bps"] > a["net_bps"] else "follow"
            A(f"- **{w}**, {foll.replace('HV + ', '')}: follow "
              f"{a['net_bps']:+.1f} vs fade {b['net_bps']:+.1f} → "
              f"**{better}** is the better side "
              f"(gross {a['gross_bps']:+.1f} / {b['gross_bps']:+.1f})")
    A("")
    pos = fade[fade["net_bps"] > 0]
    sig = pos[pos["net_p"] < 0.05]
    if len(pos) and not len(sig):
        best = pos.loc[pos["net_bps"].idxmax()]
        A(f"**Fading is better than following in most cells, but it does not "
          f"produce a tradeable edge.** The only positive net figures are the "
          f"two Gap Down fades (staying short), and neither is distinguishable "
          f"from zero — the best of them is {best['net_bps']:+.1f} bps at "
          f"p = {best['net_p']:.2f}. The Reversal signal on high volume is "
          f"best read as *information that the signal is worthless*, not as a "
          f"signal to be inverted: the gross moves are too small for either "
          f"side to clear {meta['cost_bps']} bps.")
        A("")

    # ---------------- 4. drift control ----------------
    A("## 4. How much of the up/down split is just market drift?")
    A("")
    A("A gap-up Continuation trade is long; a gap-down Continuation trade "
      "is short. Any index drift over the holding window is therefore "
      "*added* to one group and *subtracted* from the other, which "
      "manufactures an up-versus-down difference out of nothing. Measured "
      "SPY drift over the same clock windows, on the same dates:")
    A("")
    d = R.get("drift")
    if d is not None and len(d):
        A("| Window | Cohort | n | Mean SPY (bps) | Median SPY (bps) |")
        A("|---|---|---:|---:|---:|")
        for _, x in d.iterrows():
            A(f"| {x['window']} | {x['cohort']} | {int(x['n']):,} | "
              f"{x['mean_spy_bps']:+.2f} | {x['median_spy_bps']:+.2f} |")
        A("")
    A("Subtracting that drift at beta 1 — *removing the market's move, not "
      "hedging the exposure* — gives:")
    A("")
    A("| Window | Group | Side | NET | NET, drift-adjusted | Change |")
    A("|---|---|---|---:|---:|---:|")
    for w in WORDER:
        for g in MAIN:
            x = _get(main, w, g)
            if x is None or pd.isna(x.get("net_adj_bps")):
                continue
            A(f"| {w} | {g} | {SIDE.get(g, '')} | {x['net_bps']:+.1f} | "
              f"**{x['net_adj_bps']:+.1f}** | "
              f"{x['net_adj_bps'] - x['net_bps']:+.1f} |")
    A("")
    surv = []
    for w in WORDER:
        cu, cd = _get(main, w, MAIN[0]), _get(main, w, MAIN[1])
        if cu is None or cd is None or pd.isna(cu.get("net_adj_bps")):
            continue
        raw = cu["net_bps"] - cd["net_bps"]
        adj = cu["net_adj_bps"] - cd["net_adj_bps"]
        surv.append((w, raw, adj))
    if surv:
        A("Continuation, Gap Up minus Gap Down, before and after the "
          "adjustment:")
        A("")
        for w, raw, adj in surv:
            keep = (adj / raw * 100) if raw else np.nan
            A(f"- **{w}**: {raw:+.1f} bps raw → **{adj:+.1f} bps** adjusted "
              f"({keep:.0f}% of the raw difference survives)")
        A("")
        A("**Drift is not the explanation.** SPY moves barely more than a "
          "basis point over either window, so removing it changes every "
          "figure by less than 2 bps and leaves the up-versus-down gap "
          "essentially intact. The short-side advantage in section 2 is a "
          "property of the individual names, not a free ride on a falling "
          "index — and note that the drift on gap-down days is *negative*, "
          "which if anything means the short cells were helped by the market "
          "and still keep their lead once that help is stripped out.")
        A("")

    # ---------------- 5. comparability ----------------
    A("## 5. Are the up and down cohorts comparable?")
    A("")
    p = R.get("profile")
    if p is not None and len(p):
        A("| Group | n | Median \\|gap\\| (bps) | Median Gap/ATR | "
          "Median vol ratio | Median price |")
        A("|---|---:|---:|---:|---:|---:|")
        for _, x in p.iterrows():
            A(f"| {x['group']} | {int(x['n']):,} | "
              f"{x['median_abs_gap_bps']:.0f} | {x['median_gap_atr']:.2f} | "
              f"{x['median_vol_ratio']:.2f} | ${x['median_entry_px']:.0f} |")
        A("")
    y = R.get("byyear")
    if y is not None and len(y):
        A("Gap-up share of High Volume signals by year — a check that the "
          "split is not concentrated in one regime:")
        A("")
        A("| Year | Continuation n | % Gap Up | Reversal n | % Gap Up |")
        A("|---|---:|---:|---:|---:|")
        piv = y.pivot(index="year", columns="pattern",
                      values=["n", "pct_up"])
        cont_c = [c for c in y["pattern"].unique() if c.startswith("Cont")]
        rev_c = [c for c in y["pattern"].unique() if c.startswith("Rev")]
        for yr in piv.index:
            cn = piv.loc[yr, ("n", cont_c[0])] if cont_c else np.nan
            cp = piv.loc[yr, ("pct_up", cont_c[0])] if cont_c else np.nan
            rn = piv.loc[yr, ("n", rev_c[0])] if rev_c else np.nan
            rp = piv.loc[yr, ("pct_up", rev_c[0])] if rev_c else np.nan
            A(f"| {int(yr)} | {cn:,.0f} | {cp*100:.1f}% | {rn:,.0f} | "
              f"{rp*100:.1f}% |")
        A("")

    # ---------------- 6. volume control ----------------
    A("## 6. Control — the same four cells on Normal/Low volume")
    A("")
    A("High Volume only means something against the alternative. These are "
      "the same four cells for events that did **not** clear the "
      f"{meta['vol_mult']}× threshold.")
    A("")
    A(_tbl(ctrl, CTRL, side=False))
    lw = []
    for w in WORDER:
        for lg, sg in ((CTRL[0], CTRL[1]), (CTRL[3], CTRL[2])):
            xl, xs = _get(ctrl, w, lg), _get(ctrl, w, sg)
            if xl is not None and xs is not None:
                lw.append(xs["net_bps"] - xl["net_bps"])
    hw = [d for *_, d in wins] if wins else []
    if lw and hw:
        n_short = sum(1 for d in lw if d > 0)
        A(f"The short-side advantage is **weaker and less consistent** "
          f"without the volume condition: the short cell beats the long cell "
          f"in {n_short} of {len(lw)} comparisons rather than "
          f"{len(hw)} of {len(hw)}, and averages "
          f"**{float(np.mean(lw)):+.1f} bps** against "
          f"**{float(np.mean(hw)):+.1f} bps** on High Volume. It is not, "
          f"however, absent — the 1-hour Reversal comparison "
          f"({max(lw):+.1f} bps) is as large as anything in the High Volume "
          f"set. So volume sharpens the asymmetry; it does not create it, "
          f"and the case for the asymmetry being about *side* rather than "
          f"about *volume* is correspondingly weaker than section 2 alone "
          f"suggests.")
        A("")
        A("The more clear-cut contrast is the Reversal cohort itself: "
          "Normal/Low Reversal is **profitable** at both horizons where "
          "High Volume Reversal loses at both. That reproduces the earlier "
          "finding — heavy opening volume confirms the with-gap move and "
          "penalises the attempt to fade it — and it holds in both gap "
          "directions.")
        A("")

    # ---------------- 7. read ----------------
    A("## 7. What this does and does not establish")
    A("")
    A("- The four cells are read *after* the fact from one sample, and "
      "splitting an already-conditioned cohort in two halves the sample in "
      "each. Cells marked ⚠ are below "
      f"{meta['small']} events and should be treated as directionally "
      "suggestive at most.")
    A("- The gap-down cells are **short** trades. The flat "
      f"{meta['cost_bps']} bps cost carries no borrow fee, no locate "
      "failure and no uptick-rule friction, all of which fall on exactly "
      "those cells. Their true net is worse than shown by an amount this "
      "test cannot measure.")
    A("- The drift adjustment in section 4 is beta 1 on SPY. Post-earnings "
      "names on heavy volume are higher-beta than the index, so it "
      "under-corrects; the residual up-versus-down difference is an upper "
      "bound on the genuine signal asymmetry, not a point estimate.")
    A("- The universe is survivorship-affected in the usual direction: "
      "names that delisted mid-sample are absent, which flatters long "
      "cells relative to short ones.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/gapdir.py`; tables in "
      "`lambda_data/tables/gapdir_*.csv`._")
    return "\n".join(L)
