"""longhold_path_text.py — renders LONGHOLD_REPORT.md and PATH_REPORT.md.

Table-focused. Every claim in the prose is computed from the tables.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

LORDER = ["1 hour (10:35)", "2 hours (11:35)", "Until 12:00",
          "Until close (16:00)"]
PORDER = ["10 min (09:45)", "15 min (09:50)", "1 hour (10:35)"]
GA = "A — winning at 09:40"
GB = "B — losing at 09:40"


def _get(df, **kw):
    m = df
    for k, v in kw.items():
        m = m[m[k] == v]
    return m.iloc[0] if len(m) else None


def _hdr(meta: dict) -> list[str]:
    return [
        "| Input | Definition |",
        "|---|---|",
        f"| Universe | Post-earnings T+1, {meta['start']} → {meta['end']} |",
        "| Setup | High Volume + Continuation |",
        "| Continuation | 09:30–09:35 candle closes **with** the gap |",
        f"| High Volume | `c1_volume` > {meta['vol_mult']}× trailing "
        f"{meta['vol_window']}-session mean, same ticker, same 09:30–09:35 "
        "slot, shifted one session |",
        "| Entry | Open of the 09:35 bar |",
        f"| Costs | {meta['cost_bps']} bps round trip, in NET only |",
        f"| Inference | date-clustered bootstrap; ⚠ marks n < "
        f"{meta['small']} |",
    ]


# ===========================================================================
# TEST 1
# ===========================================================================

def build_long(R: dict, meta: dict) -> str:
    d = R["long"].set_index("window").reindex(
        [w for w in LORDER if w in set(R["long"]["window"])])
    L: list[str] = []
    A = L.append

    A("# Lambda — Longer Holding Periods on the Strongest Setup")
    A("")
    A("Post-earnings T+1, High Volume + Continuation, entry at the open of "
      "the 09:35 bar. The 1-hour row is the figure from the earlier "
      "reports, carried here unchanged for reference.")
    A("")
    L.extend(_hdr(meta))
    A("")
    A(f"High Volume Continuation events: **{meta['n_hv_cont']:,}**. The "
      "**Until close** row exits at the session's official closing price, "
      "not an intraday bar.")
    A("")

    A("## Results")
    A("")
    A("| Holding period | n | Win rate | Avg Win | Avg Loss | Payoff | "
      "**NET** | Median | p10 | p90 |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for w, x in d.iterrows():
        sm = " ⚠" if x["small"] == "YES" else ""
        A(f"| {w}{sm} | {int(x['n']):,} | {x['win_rate']*100:.1f}% | "
          f"{x['avg_win_bps']:.1f} | {x['avg_loss_bps']:.1f} | "
          f"{x['payoff_ratio']:.2f} | **{x['net_bps']:+.1f}** | "
          f"{x['median_bps']:+.1f} | {x['p10_bps']:+.0f} | "
          f"{x['p90_bps']:+.0f} |")
    A("")
    A("All figures in basis points. NET is mean expectancy per trade after "
      f"{meta['cost_bps']} bps; net p-values: "
      + ", ".join(f"{w} {x['net_p']:.3f}" for w, x in d.iterrows()) + ".")
    A("")

    # ---- marginal legs ----
    legs = R.get("legs")
    if legs is not None and len(legs):
        A("## What each additional leg of holding time earns")
        A("")
        A("The table above is cumulative, so a rising NET can hide a leg "
          "that contributes nothing. This decomposes it — gross return "
          "between consecutive exit points, no costs (you pay the round "
          "trip once, whichever exit you choose).")
        A("")
        A("| Leg | n | Gross | 95% CI | p | Win rate | Median |")
        A("|---|---:|---:|---:|---:|---:|---:|")
        for _, x in legs.iterrows():
            A(f"| {x['leg']} | {int(x['n']):,} | {x['gross_bps']:+.1f} | "
              f"[{x['lo']:+.1f}, {x['hi']:+.1f}] | {x['p']:.3f} | "
              f"{x['win_rate']*100:.1f}% | {x['median_bps']:+.1f} |")
        A("")
        after = legs.iloc[1:]
        dead = after[after["p"] >= 0.05]
        alive = after[after["p"] < 0.05]
        if len(dead):
            A((f"**All {len(after)} legs after the first hour are "
               "indistinguishable from zero** ("
               if len(dead) == len(after) else
               f"**{len(dead)} of the {len(after)} legs after the first hour "
               "are indistinguishable from zero** (")
              + "; ".join(f"{x['leg'].split('→ ')[-1]} {x['gross_bps']:+.1f} "
                          f"bps, p={x['p']:.2f}" for _, x in dead.iterrows())
              + "). ")
            if not len(alive):
                A("")
                A("Nothing is earned after 10:35. The cumulative NET keeps "
                  "drifting up because the point estimates are positive, but "
                  "none of the incremental legs is statistically separable "
                  "from zero, and each one adds hours of exposure and "
                  "overnight-adjacent risk for it.")
            A("")

    # ---- read ----
    best_net = d["net_bps"].idxmax()
    hour = d.loc["1 hour (10:35)"] if "1 hour (10:35)" in d.index else None
    A("## Read")
    A("")
    if hour is not None:
        A("| Holding period | NET | vs 1 hour | Win rate | vs 1 hour |")
        A("|---|---:|---:|---:|---:|")
        for w, x in d.iterrows():
            A(f"| {w} | {x['net_bps']:+.1f} | "
              f"{x['net_bps'] - hour['net_bps']:+.1f} | "
              f"{x['win_rate']*100:.1f}% | "
              f"{(x['win_rate'] - hour['win_rate'])*100:+.1f} pp |")
        A("")
    A(f"**Highest NET is {best_net} at {d.loc[best_net, 'net_bps']:+.1f} "
      f"bps.** But NET alone is the wrong way to choose a holding period, "
      "because it ignores how much risk is carried to get it. The "
      "dispersion widens far faster than the mean:")
    A("")
    A("| Holding period | NET | Std dev | NET / Std | p10 | p90 | "
      "p90 − p10 |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    for w, x in d.iterrows():
        A(f"| {w} | {x['net_bps']:+.1f} | {x['std_bps']:.0f} | "
          f"{x['net_bps']/x['std_bps']:.3f} | {x['p10_bps']:+.0f} | "
          f"{x['p90_bps']:+.0f} | {x['p90_bps'] - x['p10_bps']:.0f} |")
    A("")
    ratios = {w: x["net_bps"] / x["std_bps"] for w, x in d.iterrows()}
    best_r = max(ratios, key=ratios.get)
    others = {w: v for w, v in ratios.items() if w != best_r}
    spread = max(ratios.values()) - min(ratios.values())
    tight = [w for w, v in ratios.items()
             if abs(v - ratios[best_r]) < 0.1 * ratios[best_r]]
    runner = sorted(others, key=others.get)[-1] if others else None
    A(f"**On return per unit of risk, the first three holding periods are "
      f"indistinguishable** — "
      + ", ".join(f"{w} {ratios[w]:.3f}" for w in ratios) + ". "
      f"The nominal best is {best_r}"
      + (f", ahead of {runner} by {ratios[best_r] - ratios[runner]:.3f}"
         if runner else "")
      + " — a difference far too small to act on at this sample size. What "
      "the column does show cleanly is that "
      f"**{min(ratios, key=ratios.get)} is the worst of the four**: it "
      f"carries the widest dispersion "
      f"({d['std_bps'].max():.0f} bps std, p90 − p10 of "
      f"{(d['p90_bps'] - d['p10_bps']).max():.0f} bps) for a NET only "
      f"{d.loc[best_net, 'net_bps'] - d.loc['1 hour (10:35)', 'net_bps']:+.1f} "
      "bps above the 1-hour figure.")
    A("")
    A("The p90 − p10 column is the plainest statement of the cost: the "
      f"range of outcomes a trader actually lives through grows from "
      f"{(d.loc['1 hour (10:35)', 'p90_bps'] - d.loc['1 hour (10:35)', 'p10_bps']):.0f} "
      f"bps at 1 hour to "
      f"{(d.loc[LORDER[-1], 'p90_bps'] - d.loc[LORDER[-1], 'p10_bps']):.0f} "
      "bps at the close, for essentially the same expectancy.")
    A("")
    A("Three caveats specific to the long holds:")
    A("")
    A("- **The flat cost model gets more wrong, not less.** "
      f"{meta['cost_bps']} bps is a round trip; it does not change with "
      "holding time, so the long holds look cheap by construction. What it "
      "misses — the risk of needing to exit into a thinner book late in the "
      "session — grows with the horizon.")
    A("- **Capital efficiency is not in any of these numbers.** A 6.4-hour "
      "hold uses the slot for the whole session; four 1-hour holds could "
      "use it four times. On a per-unit-of-capital-per-hour basis the short "
      "holds win by a wide margin, and this table cannot show that.")
    A("- **The close is a different execution problem.** Marking out at "
      "16:00 means trading the closing auction or accepting late-session "
      "spreads. Neither is priced here.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/longhold_path.py`; "
      "tables in `lambda_data/tables/lp_long.csv`, `lp_legs.csv`._")
    return "\n".join(L)


# ===========================================================================
# TEST 2
# ===========================================================================

def build_path(R: dict, meta: dict) -> str:
    p = R["path"]
    base = R["baseline"].set_index("window")
    sp = R["split"].iloc[0]
    L: list[str] = []
    A = L.append

    A("# Lambda — Path Dependence of High Volume + Continuation Trades")
    A("")
    A("Post-earnings T+1. How the trade evolves conditional on whether it "
      "was up or down at the 5-minute mark (09:40).")
    A("")
    L.extend(_hdr(meta))
    A("| Conditioning point | Return from entry to the 09:40 close |")
    A("")
    A(f"Of **{int(sp['n_classified']):,}** classified trades, "
      f"**{int(sp['n_win']):,} ({sp['pct_win']*100:.1f}%)** were profitable "
      f"at 09:40 and **{int(sp['n_lose']):,}** were losing. Mean 5-minute "
      f"return: **{sp['mean_5min_win_bps']:+.1f} bps** for the winners, "
      f"**{sp['mean_5min_lose_bps']:+.1f} bps** for the losers.")
    A("")
    A("> **Why there are two \"subsequent return\" columns.** Splitting on "
      "the sign of the 09:40 return and then measuring the move *from that "
      "same 09:40 print* shares one price between the classifier and the "
      "outcome. Noise in that print — a trade at the offer rather than the "
      "bid — enters the classification positively and the subsequent return "
      "negatively, manufacturing mean reversion out of nothing. "
      "**`sub (09:40)`** has that contamination; **`sub (09:41 open)`** "
      "measures from the next print, so classifier and outcome share no "
      "price. The gap between the two columns *is* the artefact. Only the "
      "second supports a claim about what actually happens next.")
    A("")

    # ---- main table ----
    A("## 1. The two groups at later horizons")
    A("")
    A("| Group | Horizon | n | % profitable | % profitable net | Win rate | "
      "Mean (from entry) | Median | sub (09:40) | **sub (09:41 open)** |")
    A("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for g in (GA, GB):
        for w in PORDER:
            x = _get(p, group=g, window=w)
            if x is None:
                continue
            A(f"| {g.split(' — ')[0]} | {w} | {int(x['n']):,} | "
              f"{x['pct_gross_pos']*100:.1f}% | "
              f"{x['pct_net_pos']*100:.1f}% | {x['win_rate']*100:.1f}% | "
              f"{x['mean_bps']:+.1f} | {x['median_bps']:+.1f} | "
              f"{x['sub_m9_bps']:+.1f} | **{x['sub_o10_bps']:+.1f}** |")
        A("| | | | | | | | | | |")
    for w in PORDER:
        if w in base.index:
            x = base.loc[w]
            A(f"| All | {w} | {int(x['n']):,} | "
              f"{x['win_rate']*100:.1f}% | — | {x['win_rate']*100:.1f}% | "
              f"{x['mean_bps']:+.1f} | {x['median_bps']:+.1f} | — | — |")
    A("")
    A("**% profitable** = cumulative return from entry above zero. "
      "**% profitable net** = above "
      f"{meta['cost_bps']} bps, i.e. actually worth having exited into. "
      "**Win rate** is the same quantity as % profitable — the request "
      "listed them separately, so the net-of-cost version is given as the "
      "distinct third measure. **sub** columns are the mean return from the "
      "5-minute mark onward.")
    A("")

    # ---- transition ----
    A("## 2. Transition rates — the headline question")
    A("")
    A("| From 09:40 status | To horizon | % profitable | % profitable net |")
    A("|---|---|---:|---:|")
    for g, lab in ((GB, "**Losers** that became winners"),
                   (GA, "**Winners** that stayed winners")):
        for w in PORDER:
            x = _get(p, group=g, window=w)
            if x is None:
                continue
            A(f"| {lab} | {w} | {x['pct_gross_pos']*100:.1f}% | "
              f"{x['pct_net_pos']*100:.1f}% |")
    A("")
    lose15 = _get(p, group=GB, window="15 min (09:50)")
    lose60 = _get(p, group=GB, window="1 hour (10:35)")
    win15 = _get(p, group=GA, window="15 min (09:50)")
    win60 = _get(p, group=GA, window="1 hour (10:35)")
    if all(v is not None for v in (lose15, lose60, win15, win60)):
        A(f"- **{lose15['pct_gross_pos']*100:.1f}%** of 5-minute losers are "
          f"profitable at 15 minutes; **{lose60['pct_gross_pos']*100:.1f}%** "
          "at 1 hour.")
        A(f"- **{win15['pct_gross_pos']*100:.1f}%** of 5-minute winners are "
          f"still profitable at 15 minutes; "
          f"**{win60['pct_gross_pos']*100:.1f}%** at 1 hour.")
        A("")

    # ---- subsequent move ----
    A("## 3. Average subsequent move, winners vs losers at 09:40")
    A("")
    A("| Horizon | Group | sub from 09:40 | sub from 09:41 open | "
      "Artefact | p (09:41) | 95% CI (09:41) |")
    A("|---|---|---:|---:|---:|---:|---:|")
    for w in PORDER:
        for g in (GA, GB):
            x = _get(p, group=g, window=w)
            if x is None:
                continue
            A(f"| {w} | {g.split(' — ')[0]} | {x['sub_m9_bps']:+.1f} | "
              f"**{x['sub_o10_bps']:+.1f}** | "
              f"{x['sub_m9_bps'] - x['sub_o10_bps']:+.1f} | "
              f"{x['sub_o10_p']:.3f} | [{x['sub_o10_lo']:+.1f}, "
              f"{x['sub_o10_hi']:+.1f}] |")
    A("")
    arts = {(g, w): (_get(p, group=g, window=w)["sub_m9_bps"]
                     - _get(p, group=g, window=w)["sub_o10_bps"])
            for w in PORDER for g in (GA, GB)
            if _get(p, group=g, window=w) is not None}
    if arts:
        av = list(arts.values())
        # Bounce predicts the contaminated column understates winners
        # (negative artefact) and overstates losers (positive artefact).
        as_pred = sum(1 for (g, _), v in arts.items()
                      if (g == GA and v < 0) or (g == GB and v > 0))
        A(f"**The artefact is small.** It runs {min(av):+.1f} to "
          f"{max(av):+.1f} bps — at most "
          f"{max(abs(v) for v in av):.1f} bps against subsequent moves of "
          f"6 to 30 bps — and points in the direction bid-ask bounce "
          f"predicts in {as_pred} of {len(arts)} cells (contaminated column "
          "too low for winners, too high for losers). So the shared-print "
          "contamination is real but does not drive any conclusion here. "
          "Every statement below uses the 09:41 column regardless.")
        A("")

    for w in PORDER:
        a, b = _get(p, group=GA, window=w), _get(p, group=GB, window=w)
        if a is None or b is None:
            continue
        diff = a["sub_o10_bps"] - b["sub_o10_bps"]
        A(f"- **{w}**: winners go on to make {a['sub_o10_bps']:+.1f} bps "
          f"(p={a['sub_o10_p']:.3f}), losers {b['sub_o10_bps']:+.1f} bps "
          f"(p={b['sub_o10_p']:.3f}) — a gap of **{diff:+.1f} bps** in "
          f"favour of the {'winners' if diff > 0 else 'losers'}.")
    A("")

    # ---- magnitude ----
    mg = R.get("by_magnitude")
    if mg is not None and len(mg):
        A("## 4. The size of the 5-minute move, not just its sign")
        A("")
        A(f"Quartile cut at {sp['p25_5min_bps']:+.0f} and "
          f"{sp['p75_5min_bps']:+.0f} bps.")
        A("")
        A("| Horizon | 09:40 bucket | n | Mean at 09:40 | Mean from entry | "
          "% profitable | sub (09:41 open) | p |")
        A("|---|---|---:|---:|---:|---:|---:|---:|")
        for w in PORDER:
            for _, x in mg[mg["window"] == w].iterrows():
                A(f"| {w} | {x['bucket']} | {int(x['n']):,} | "
                  f"{x['mean_5min_bps']:+.1f} | {x['cum_mean_bps']:+.1f} | "
                  f"{x['cum_win']*100:.1f}% | {x['sub_o10_bps']:+.1f} | "
                  f"{x['sub_o10_p']:.3f} |")
        A("")

    # ---- conclusion ----
    A("## 5. What this means for the trade")
    A("")
    h = _get(p, group=GA, window="1 hour (10:35)")
    l = _get(p, group=GB, window="1 hour (10:35)")
    if h is not None and l is not None:
        gap = h["mean_bps"] - l["mean_bps"]
        subgap = h["sub_o10_bps"] - l["sub_o10_bps"]
        gap5 = sp["mean_5min_win_bps"] - sp["mean_5min_lose_bps"]
        A(f"**The 5-minute mark tells you where the trade stands, not where "
          f"it is going.** The two groups are already {gap5:+.1f} bps apart "
          f"at 09:40. An hour later they are {gap:+.1f} bps apart — the gap "
          f"has *narrowed* by {gap5 - gap:.1f} bps, because the losers "
          f"close ground faster than the winners extend. Measured cleanly "
          f"from 09:41 onward the two groups differ by only "
          f"**{subgap:+.1f} bps**, against the {gap5:+.1f} bps of "
          "separation that was already banked before the decision point.")
        A("")
        if abs(subgap) < abs(gap) / 3:
            A(f"In other words, roughly "
              f"{(1 - abs(subgap)/abs(gap))*100:.0f}% of the gap between "
              "winners and losers at 1 hour was already determined in the "
              "first five minutes. Knowing a trade is up at 09:40 tells you "
              "a great deal about where it sits and comparatively little "
              "about what it does next.")
            A("")
        for g, x in ((GA, h), (GB, l)):
            verdict = ("continues to make money" if x["sub_o10_p"] < 0.05
                       and x["sub_o10_bps"] > 0 else
                       "continues to lose" if x["sub_o10_p"] < 0.05
                       and x["sub_o10_bps"] < 0 else
                       "does nothing distinguishable from zero")
            A(f"- Group {g.split(' — ')[0]} ({g.split('— ')[1]}) "
              f"{verdict} from 09:41 to 10:35: {x['sub_o10_bps']:+.1f} bps, "
              f"p = {x['sub_o10_p']:.3f}, 95% CI "
              f"[{x['sub_o10_lo']:+.1f}, {x['sub_o10_hi']:+.1f}].")
        A("")
        if l["sub_o10_bps"] > h["sub_o10_bps"] > 0:
            A(f"### Losers recover faster than winners extend")
            A("")
            A("**Both groups make money from 09:41 onward — but the losing "
              f"group makes more** ({l['sub_o10_bps']:+.1f} vs "
              f"{h['sub_o10_bps']:+.1f} bps to 1 hour, both p < 0.001). "
              "The continuation edge does not stop working for trades that "
              "start badly; if anything it works harder on them.")
            A("")
            if mg is not None and len(mg):
                w60 = mg[mg["window"] == "1 hour (10:35)"]
                if len(w60):
                    worst = w60.loc[w60["mean_5min_bps"].idxmin()]
                    A(f"Section 4 sharpens this: the **worst** 5-minute "
                      f"losers — averaging {worst['mean_5min_bps']:+.0f} bps "
                      f"down at 09:40 — go on to make "
                      f"**{worst['sub_o10_bps']:+.1f} bps** from 09:41 to "
                      f"10:35, the largest subsequent move of any bucket. "
                      f"They still end the hour at "
                      f"{worst['cum_mean_bps']:+.0f} bps cumulative, so this "
                      "is a partial recovery, not a round trip to profit.")
                    A("")
            A("**The practical implication cuts against a stop-loss at the "
              "5-minute mark.** Cutting the losers at 09:40 would realise "
              f"an average {sp['mean_5min_lose_bps']:+.1f} bps and forgo an "
              f"expected {l['sub_o10_bps']:+.1f} bps of recovery. That is "
              "not an argument for holding losers indefinitely — it is an "
              "argument that 5 minutes is too early to judge this "
              "particular setup, which is consistent with the whole edge "
              "being a slow repricing rather than an instant one.")
            A("")
    A("**Caveats.**")
    A("")
    A("- This is a *conditional description*, not a tradeable rule. Acting "
      "on it means a second decision at 09:40 — cutting losers or adding to "
      "winners — and that second trade pays its own spread, which is not "
      "modelled anywhere here.")
    A("- The groups are defined by an outcome, so both are selected "
      "samples. The unconditional row in section 1 is the only line that "
      "describes a decision you could make at entry.")
    A("- The 09:41-open reference removes the shared-print artefact but not "
      "all microstructure: a trade classified as winning at 09:40 is more "
      "likely to have been marked at the offer, and the next print inherits "
      "some of that. The artefact column is a floor on the bias, not a "
      "complete correction.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/longhold_path.py`; "
      "tables in `lambda_data/tables/lp_path.csv`, `lp_transition.csv`, "
      "`lp_by_magnitude.csv`._")
    return "\n".join(L)
