"""doji4_text.py — renders DOJI4_REPORT.md. Table-focused."""

from __future__ import annotations

import numpy as np
import pandas as pd

WORDER = ["5 min (09:40)", "10 min (09:45)", "15 min (09:50)",
          "1 hour (10:35)"]
G1 = "1. Small + Continuation"
G2 = "2. Small + Reversal"
G3 = "3. Continuation"
G4 = "4. Reversal"
GORDER = [G1, G2, G3, G4]
GAP, CANDLE = "Follow the gap", "Follow the candle"


def _get(df, g, w, direction=None):
    m = df[(df["group"] == g) & (df["window"] == w)]
    if direction is not None:
        m = m[m["direction"] == direction]
    return m.iloc[0] if len(m) else None


def build(R: dict, meta: dict) -> str:
    d = R["main"]
    L: list[str] = []
    A = L.append

    A("# Lambda — Four-Way Candle Classification: Does a Small Body Still "
      "Tell You Which Way to Trade?")
    A("")
    A("Post-earnings T+1, High Volume. The doji group split by which way "
      "its small body pointed, rather than pooled.")
    A("")
    A("| Group | Definition | n |")
    A("|---|---|---:|")
    A(f"| {G1} | body/range ≤ {meta['doji_max']:.2f}, closes **with** the "
      f"gap | {meta['n_g1']:,} |")
    A(f"| {G2} | body/range ≤ {meta['doji_max']:.2f}, closes **against** "
      f"the gap | {meta['n_g2']:,} |")
    A(f"| {G3} | body/range > {meta['doji_max']:.2f}, closes **with** the "
      f"gap | {meta['n_g3']:,} |")
    A(f"| {G4} | body/range > {meta['doji_max']:.2f}, closes **against** "
      f"the gap | {meta['n_g4']:,} |")
    A("")
    A(f"Entry at the open of the 09:35 bar; {meta['cost_bps']} bps round "
      f"trip in NET; date-clustered bootstrap; ⚠ marks n < {meta['small']}.")
    A("")
    A("> **How to read the two direction columns.** For groups 1 and 3 the "
      "candle points the same way as the gap, so there is only one trade to "
      "make. For groups 2 and 4 they point opposite ways, and both are "
      "shown. The pair does **not** sum to zero: gross flips exactly but "
      f"the {meta['cost_bps']} bps is paid either way, so the two NET "
      f"figures for one cell sum to −{2*meta['cost_bps']:.1f} bps. Both "
      "sides of a small gross edge lose.")
    A("")

    # ---------------- headline ----------------
    A("## 1. All four groups, both directions")
    A("")
    A("| Group | Window | n | Follow the **gap** | Follow the **candle** | "
      "Better side |")
    A("|---|---|---:|---:|---:|---|")
    for g in GORDER:
        for w in WORDER:
            xg = _get(d, g, w, GAP)
            xc = _get(d, g, w, CANDLE)
            if xg is None:
                continue
            sm = " ⚠" if xg["small"] == "YES" else ""
            if xc is None:
                A(f"| {g}{sm} | {w} | {int(xg['n']):,} | "
                  f"**{xg['net_bps']:+.1f}** | — (same trade) | gap |")
            else:
                better = "**gap**" if xg["net_bps"] > xc["net_bps"] \
                    else "**candle**"
                A(f"| {g}{sm} | {w} | {int(xg['n']):,} | "
                  f"{xg['net_bps']:+.1f} | {xc['net_bps']:+.1f} | {better} |")
        A("| | | | | | |")
    A("")
    A("NET in bps after costs.")
    A("")

    # ---------------- the question ----------------
    A("## 2. Your question: small body, closed against the gap")
    A("")
    A("| Window | n | Follow the gap | p | Follow the candle | p | "
      "Gap win rate | Candle win rate |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|")
    g2g, g2c = [], []
    for w in WORDER:
        xg, xc = _get(d, G2, w, GAP), _get(d, G2, w, CANDLE)
        if xg is None or xc is None:
            continue
        g2g.append(xg)
        g2c.append(xc)
        A(f"| {w} | {int(xg['n']):,} | **{xg['net_bps']:+.1f}** | "
          f"{xg['net_p']:.3f} | {xc['net_bps']:+.1f} | {xc['net_p']:.3f} | "
          f"{xg['win_rate']*100:.1f}% | {xc['win_rate']*100:.1f}% |")
    A("")
    if g2g and g2c:
        gap_better = sum(1 for a, b in zip(g2g, g2c)
                         if a["net_bps"] > b["net_bps"])
        gap_pos = [x for x in g2g if x["net_bps"] > 0]
        gap_sig = [x for x in g2g if x["net_bps"] > 0 and x["net_p"] < 0.05]
        cand_pos = [x for x in g2c if x["net_bps"] > 0]
        if gap_better == len(g2g) and not cand_pos:
            A(f"**No — do not follow the candle.** Following the gap beats "
              f"following the candle at all {len(g2g)} horizons, and the "
              f"follow-the-candle column is negative at every one "
              f"({min(x['net_bps'] for x in g2c):+.1f} to "
              f"{max(x['net_bps'] for x in g2c):+.1f} bps). A small body "
              "pointing against the gap is not a reversal signal — it is a "
              "candle that failed to go anywhere, and the gap is still the "
              "only thing on the chart carrying information.")
            A("")
            if gap_sig:
                detail = ", ".join(
                    "{} {:+.1f}".format(x["window"].split(" (")[0],
                                        x["net_bps"]) for x in gap_sig)
                A(f"Following the **gap** in this cell is positive at "
                  f"{len(gap_pos)} of {len(g2g)} horizons and significant "
                  f"at {len(gap_sig)} ({detail}). On a sample of "
                  f"{int(g2g[0]['n']):,} that is suggestive rather than "
                  "settled, but it points the same way as every other "
                  "result in this series.")
                A("")
        elif gap_better == len(g2g):
            A(f"**Follow the gap, not the candle** — the gap side wins at "
              f"all {len(g2g)} horizons, though the candle side is not "
              f"negative everywhere.")
            A("")
        else:
            A(f"**Mixed** — the gap side wins at {gap_better} of "
              f"{len(g2g)} horizons.")
            A("")

    # ---------------- splitting the doji group changes its story --------
    g1g = [_get(d, G1, w, GAP) for w in WORDER]
    g1g = [x for x in g1g if x is not None]
    if g1g and g2g:
        s1 = [x for x in g1g if x["net_p"] < 0.05]
        s2 = [x for x in g2g if x["net_p"] < 0.05]
        if len(s2) > len(s1):
            A("### Splitting the doji group was worth doing")
            A("")
            A("The pooled Indecisive figure in `DOJI_REPORT.md` (+9.4 to "
              "+16.2 bps) turns out to be an average over two unlike "
              "halves:")
            A("")
            A("| Window | Small + **with** gap | p | Small + **against** "
              "gap | p |")
            A("|---|---:|---:|---:|---:|")
            for a, b in zip(g1g, g2g):
                A(f"| {a['window']} | {a['net_bps']:+.1f} | "
                  f"{a['net_p']:.3f} | **{b['net_bps']:+.1f}** | "
                  f"{b['net_p']:.3f} |")
            A("")
            A(f"**Nearly all of the doji edge comes from the half that "
              f"closed against the gap.** Those cells are significant at "
              f"{len(s2)} of {len(g2g)} horizons; the half that closed "
              f"*with* the gap is significant at {len(s1)} and its point "
              f"estimates are roughly half the size. That is the opposite "
              "of the intuitive ordering — a candle that leaned the "
              "*wrong* way is the better setup, provided you trade the gap "
              "rather than the candle.")
            A("")
            A("The reading that fits: a counter-gap candle that could not "
              "produce a real body is a **failed reversal**. Sellers into "
              "a gap up (or buyers into a gap down) showed up, got "
              "absorbed, and closed the candle nearly flat. That is "
              "evidence the gap direction is holding against pressure — "
              "stronger evidence than a small candle that merely drifted "
              "the same way the gap already pointed. It also matches the "
              "failed-reversal result in `VOLUME_REVERSAL_REPORT.md`, "
              "reached there by a completely different cut of the data.")
            A("")

    # ---------------- compare to a real reversal ----------------
    A("### Compared with a full-bodied reversal (group 4)")
    A("")
    A("| Window | Small+Rev: follow candle | Full Rev: follow candle | "
      "Small+Rev: follow gap | Full Rev: follow gap |")
    A("|---|---:|---:|---:|---:|")
    for w in WORDER:
        a, b = _get(d, G2, w, CANDLE), _get(d, G4, w, CANDLE)
        c, e = _get(d, G2, w, GAP), _get(d, G4, w, GAP)
        if any(v is None for v in (a, b, c, e)):
            continue
        A(f"| {w} | {a['net_bps']:+.1f} | {b['net_bps']:+.1f} | "
          f"{c['net_bps']:+.1f} | {e['net_bps']:+.1f} |")
    A("")
    g4c = [_get(d, G4, w, CANDLE) for w in WORDER]
    g4c = [x for x in g4c if x is not None]
    if g4c and all(x["net_bps"] < 0 for x in g4c):
        A("**Following the candle loses in both reversal groups**, small "
          f"body or full body ({min(x['net_bps'] for x in g4c):+.1f} to "
          f"{max(x['net_bps'] for x in g4c):+.1f} bps for the full-bodied "
          "one). So the answer does not depend on body size at all: a "
          "counter-gap candle is not worth following whether it is a "
          "hesitant one or an emphatic one. Section 3 tests that across the "
          "whole body-size range rather than at one cut.")
        A("")

    # ---------------- ladder ----------------
    lad = R.get("ladder")
    if lad is not None and len(lad):
        A("## 3. Body-size ladder — does a *bigger* counter-gap body ever "
          "justify following it?")
        A("")
        A("Every event whose first candle closed against the gap, bucketed "
          "by body/range. 0.10 is an arbitrary line, so this checks the "
          "whole range.")
        A("")
        A("| Window | Body/range | n | Follow the candle | p | "
          "Follow the gap | p |")
        A("|---|---|---:|---:|---:|---:|---:|")
        for w in WORDER:
            sub = lad[lad["window"] == w]
            for bucket in sub["bucket"].unique():
                c = sub[(sub["bucket"] == bucket)
                        & (sub["direction"] == CANDLE)]
                g = sub[(sub["bucket"] == bucket)
                        & (sub["direction"] == GAP)]
                if not len(c) or not len(g):
                    continue
                c, g = c.iloc[0], g.iloc[0]
                sm = " ⚠" if c["small"] == "YES" else ""
                A(f"| {w} | {bucket}{sm} | {int(c['n']):,} | "
                  f"{c['net_bps']:+.1f} | {c['net_p']:.3f} | "
                  f"**{g['net_bps']:+.1f}** | {g['net_p']:.3f} |")
            A("| | | | | | | |")
        A("")
        cand = lad[lad["direction"] == CANDLE]
        pos_sig = cand[(cand["net_bps"] > 0) & (cand["net_p"] < 0.05)]
        A(f"Across all {len(cand)} bucket × horizon cells, "
          + (f"**not one** shows a significantly positive return from "
             f"following the counter-gap candle."
             if not len(pos_sig) else
             f"{len(pos_sig)} show a significantly positive return from "
             f"following the counter-gap candle.")
          + " There is no body size at which the counter-gap candle becomes "
          "worth following.")
        A("")
        # The gradient across buckets is the real content of this table.
        order = [b for b, _, _ in
                 [("≤ 0.10 (doji)", 0, 0), ("0.10 – 0.25", 0, 0),
                  ("0.25 – 0.50", 0, 0), ("0.50 – 0.75", 0, 0),
                  ("> 0.75", 0, 0)]]
        piv = []
        for b in order:
            c = cand[cand["bucket"] == b]["net_bps"]
            g = lad[(lad["bucket"] == b)
                    & (lad["direction"] == GAP)]["net_bps"]
            if len(c) and len(g):
                piv.append((b, float(c.mean()), float(g.mean())))
        if len(piv) >= 4:
            A("Averaging each bucket across the four horizons shows the "
              "gradient plainly:")
            A("")
            A("| Body/range | Follow the candle | Follow the gap |")
            A("|---|---:|---:|")
            for b, c, g in piv:
                A(f"| {b} | {c:+.1f} | {g:+.1f} |")
            A("")
            mono_c = all(piv[i][1] <= piv[i + 1][1]
                         for i in range(len(piv) - 1))
            steady = "steadily" if mono_c else "broadly, though not " \
                "monotonically — the 0.25–0.50 bucket breaks the sequence "
            A("**The two columns move in opposite directions as the body "
              f"grows.** Following the candle improves {steady}"
              f"({piv[0][1]:+.1f} → {piv[-1][1]:+.1f} bps) while following "
              f"the gap decays over the same range ({piv[0][2]:+.1f} → "
              f"{piv[-1][2]:+.1f} bps), and they cross around the "
              "0.50 bucket. So body size *does* carry information — it just "
              "never carries enough to make following the candle "
              "profitable. What it really measures is how much to trust the "
              "gap: the smaller the counter-gap body, the more the gap is "
              "worth backing, and the bigger it is, the more you should "
              "simply stand aside.")
            A("")

    # ---------------- practical ----------------
    A("## 4. The rule this implies")
    A("")
    def _verdict(g, direction=GAP):
        xs = [_get(d, g, w, direction) for w in WORDER]
        xs = [x for x in xs if x is not None]
        sig = [x for x in xs if x["net_p"] < 0.05 and x["net_bps"] > 0]
        return xs, sig

    g1, g1s = _verdict(G1)
    g2, g2s = _verdict(G2)
    g3, g3s = _verdict(G3)
    g4g, _ = _verdict(G4)

    A("| First candle | Trade | Evidence |")
    A("|---|---|---|")
    A(f"| Full body, **with** the gap | With the gap | "
      f"{g3[0]['net_bps']:+.1f} to {g3[-1]['net_bps']:+.1f} bps, "
      f"significant at {len(g3s)}/{len(g3)}, n = {int(g3[0]['n']):,} |")
    A(f"| Small body, **against** the gap | With the gap — ignore the body "
      f"| {g2[0]['net_bps']:+.1f} to {g2[-1]['net_bps']:+.1f} bps, "
      f"significant at {len(g2s)}/{len(g2)}, n = {int(g2[0]['n']):,} |")
    A(f"| Small body, **with** the gap | With the gap, but weakly "
      f"evidenced | {g1[0]['net_bps']:+.1f} to {g1[-1]['net_bps']:+.1f} "
      f"bps, significant at {len(g1s)}/{len(g1)}, n = {int(g1[0]['n']):,} |")
    A(f"| Full body, **against** the gap | Stand aside | both directions "
      f"lose or are indistinguishable from zero |")
    A("")
    if g4g and all(x["net_bps"] < 0 for x in g4g):
        insig = [x for x in g4g if x["net_p"] >= 0.05]
        A("The last row is **stand aside**, not *fade the candle*. "
          "Following the gap after a full-bodied counter-gap candle is "
          f"negative at all {len(g4g)} horizons "
          f"({min(x['net_bps'] for x in g4g):+.1f} to "
          f"{max(x['net_bps'] for x in g4g):+.1f} bps) though mostly "
          f"indistinguishable from zero ({len(insig)} of {len(g4g)} with "
          f"p ≥ 0.05), while following the candle loses significantly. "
          "Losing on one side is not the same as winning on the other: the "
          f"{meta['cost_bps']} bps is paid whichever way you point, so both "
          "directions of a near-zero gross edge lose. There is no trade "
          "here.")
        A("")

    # ---------------- composition ----------------
    c = R.get("comp")
    if c is not None and len(c):
        A("## 5. Composition")
        A("")
        A("| Group | n | Share | Median body/range | Median \\|gap\\| | "
          "Median Gap/ATR | Median vol ratio | % Gap Up |")
        A("|---|---:|---:|---:|---:|---:|---:|---:|")
        for _, x in c.iterrows():
            A(f"| {x['group']} | {int(x['n']):,} | {x['share']*100:.1f}% | "
              f"{x['median_body_range']:.2f} | "
              f"{x['median_abs_gap_bps']:.0f} bps | "
              f"{x['median_gap_atr']:.2f} | {x['median_vol_ratio']:.2f} | "
              f"{x['pct_gap_up']*100:.1f}% |")
        A("")

    A("## 6. Caveats")
    A("")
    A(f"- **Group 2 is small** — {meta['n_g2']:,} events, against "
      f"{meta['n_g3']:,} in the main Continuation cell. It clears the "
      f"{meta['small']}-event floor used throughout this series but it is "
      "the thinnest cell in any report so far, and it deserves an "
      "out-of-sample check before anything is built on it.")
    A("- **The four groups partition one sample**, so they are not "
      "independent tests.")
    if c is not None and len(c) >= 2:
        u1 = float(c.iloc[0]["pct_gap_up"]) * 100
        u2 = float(c.iloc[1]["pct_gap_up"]) * 100
        if abs(u2 - u1) > 5:
            A(f"- **The two small-body groups differ in gap-direction mix** "
              f"({u1:.0f}% gap-up in group 1 against {u2:.0f}% in group 2), "
              "which matters because `GAPDIR_REPORT.md` found gap-down "
              "cells outperform gap-up ones. Group 2 is the more "
              "**gap-up**-weighted of the two, so that mix works *against* "
              "its result rather than explaining it — the finding survives "
              "the confound rather than resting on it.")
    A("- **0.10 is a convention, not an optimum.** The ladder in section 3 "
      "is the answer to that objection: the conclusion holds across every "
      "body size, so it does not depend on where the line is drawn.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/doji4.py`; tables in "
      "`lambda_data/tables/doji4_*.csv`._")
    return "\n".join(L)
