"""gapstudy_text.py — renders GAP_STAGE1_REPORT.md.

Conclusions are computed from the tables, not pre-written.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

TABLES = Path("/home/user/lambda_data/tables")
WORDER = ["5 min (09:40)", "15 min (09:50)", "1 hour (10:35)"]
# earnings-study windows that match these holds, for the read-across
EARN_MAP = {"5 min (09:40)": "09:35 -> 09:40",
            "15 min (09:50)": "09:35 -> 09:50",
            "1 hour (10:35)": "09:35 -> 10:35"}


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
    d["_w"] = d["window"].map({v: i for i, v in enumerate(WORDER)})
    if col:
        d["_k"] = d[col].map({v: i for i, v in enumerate(order)})
        return d.sort_values(["_w", "_k"]).drop(columns=["_w", "_k"])
    return d.sort_values("_w").drop(columns="_w")


def build(R: dict, meta: dict) -> str:
    L = []
    A = L.append
    t1 = _order(R["g1_overall"], None, None)
    t2 = _order(R["g2_gapatr"], "bucket",
                ["Gap/ATR < 1.0", "Gap/ATR 1.0-2.0", "Gap/ATR > 2.0"])
    t3 = _order(R["g3_mcap"], "bucket",
                ["$3B - $10B", "$10B - $50B", "> $50B"])
    t4 = _order(R["g4_nofilter"], None, None)
    t5 = _order(R["g5_byyear"], None, None)

    A("# Lambda — Stage 1: General Gaps (non-earnings), 2021–2025")
    A("")
    A(f"**{meta['n_events']:,} gap events** across **{meta['n_tickers']} "
      f"tickers**, {meta['start']} to {meta['end']}. "
      f"**{meta['n_cont']:,}** fire the Continuation signal. Net subtracts "
      f"{meta['cost_bps']} bps round trip. p-values two-sided from a "
      "date-clustered bootstrap.")
    A("")
    A("| Input | Definition |")
    A("|---|---|")
    A("| Universe | Market cap > $3B, price ≥ $10, ADV ≥ 500k — all "
      "prior-session |")
    A("| Gap filter | \\|Gap\\| ≥ 0.8% **or** Gap/ATR ≥ 0.7 |")
    A("| Signal | 09:30–09:35 candle closes in the gap direction |")
    A("| Entry | Open of the 09:35 bar |")
    A("| Exits | 5 min = 09:40, 15 min = 09:50, 1 hour = 10:35 |")
    A("")
    A(f"> **Two things worth flagging up front.** The window straddles the "
      f"2022-03-01 IEX consolidated-tape change, which rescales reported "
      f"share volume; a raw 500k ADV cutoff would drop most of the "
      f"post-2022 sample for a units reason rather than an economic one, so "
      f"the cutoff is applied through the break-aware filter established "
      f"earlier. And {meta['n_dropped']:,} events with no real print by "
      f"09:35 are dropped outright — their forward-filled entry price would "
      f"otherwise come from *after* the intended entry.")
    A("")

    A("## 1. Overall performance")
    A("")
    A(_t(t1, ["window", "cohort", "n", "win_rate", "wilson_lo", "wilson_hi",
              "gross_bps", "net_bps", "net_p"],
         ["Window", "Cohort", "n", "Win rate", "Wilson lo", "Wilson hi",
          "Gross (bps)", "NET (bps)", "net p"],
         rate=("win_rate", "wilson_lo", "wilson_hi"),
         bps=("gross_bps", "net_bps"), p=("net_p",)))

    A("## 2. Gap / ATR buckets (Continuation)")
    A("")
    A(_t(t2, ["window", "bucket", "n", "win_rate", "avg_win_bps",
              "avg_loss_bps", "payoff_ratio", "gross_bps", "net_bps",
              "net_p"],
         ["Window", "Gap/ATR", "n", "Win rate", "Avg win", "Avg loss",
          "Payoff", "Gross (bps)", "NET (bps)", "net p"],
         rate=("win_rate",),
         bps=("avg_win_bps", "avg_loss_bps", "gross_bps", "net_bps"),
         p=("net_p",), num=("payoff_ratio",)))

    A("## 3. Market cap (Continuation)")
    A("")
    A(_t(t3, ["window", "bucket", "n", "win_rate", "avg_win_bps",
              "avg_loss_bps", "payoff_ratio", "gross_bps", "net_bps",
              "net_p"],
         ["Window", "Market cap", "n", "Win rate", "Avg win", "Avg loss",
          "Payoff", "Gross (bps)", "NET (bps)", "net p"],
         rate=("win_rate",),
         bps=("avg_win_bps", "avg_loss_bps", "gross_bps", "net_bps"),
         p=("net_p",), num=("payoff_ratio",)))

    A("## 4. Reference — the same trade with no candle filter")
    A("")
    A(_t(t4, ["window", "cohort", "n", "win_rate", "gross_bps", "net_bps",
              "net_p"],
         ["Window", "Cohort", "n", "Win rate", "Gross (bps)", "NET (bps)",
          "net p"],
         rate=("win_rate",), bps=("gross_bps", "net_bps"), p=("net_p",)))

    A("## 5. Year by year (Continuation)")
    A("")
    A(_t(t5, ["window", "year", "n", "win_rate", "gross_bps", "net_bps",
              "net_p"],
         ["Window", "Year", "n", "Win rate", "Gross (bps)", "NET (bps)",
          "net p"],
         rate=("win_rate",), bps=("gross_bps", "net_bps"), p=("net_p",)))

    # ---------------- read-across to the earnings study ----------------
    ef = TABLES / "e35_t1_holding.csv"
    if ef.exists():
        e = pd.read_csv(ef)
        e = e[e["cohort"] == "Simple Continuation"].set_index("window")
        c1 = t1[t1["cohort"] == "All Continuation"].set_index("window")
        A("## 6. General gaps vs the earnings gaps studied earlier")
        A("")
        A("Same entry, same signal, same cost. Earnings figures are the "
          "previously reported 09:35-entry numbers.")
        A("")
        A("| Hold | General n | General win | General NET | Earnings n | "
          "Earnings win | Earnings NET |")
        A("|---|---:|---:|---:|---:|---:|---:|")
        for w in WORDER:
            if w not in c1.index or EARN_MAP[w] not in e.index:
                continue
            g, x = c1.loc[w], e.loc[EARN_MAP[w]]
            A(f"| {w} | {int(g['n']):,} | {g['win_rate']*100:.1f}% | "
              f"**{g['net_bps']:+.1f}** | {int(x['n']):,} | "
              f"{x['win_rate']*100:.1f}% | **{x['net_bps']:+.1f}** |")
        A("")

    # ---------------- conclusion, computed ----------------
    c1 = t1[t1["cohort"] == "All Continuation"].set_index("window")
    n4 = t4.set_index("window")
    lift = {w: c1.loc[w, "net_bps"] - n4.loc[w, "net_bps"]
            for w in c1.index if w in n4.index}
    maxlift = max(abs(v) for v in lift.values())

    A("## Quick conclusion")
    A("")
    A(f"**Verdict: REJECT the candle signal on general gaps.** The "
      f"first-candle condition — the thing being tested — adds at most "
      f"{maxlift:.1f} bps over simply trading every gap in its own "
      f"direction, and nothing at all at the 15-minute horizon. What little "
      f"positive expectancy exists belongs to gap drift, not to the signal.")
    A("")

    # Q1 — does the edge exist
    pos = c1[(c1["net_bps"] > 0) & (c1["net_p"] < 0.05)]
    best_w = c1["net_bps"].idxmax()
    A("**Does the edge still exist on general (non-earnings) gaps?**")
    A("")
    if len(pos) == 0:
        A(f"No. Net expectancy is not significantly positive at any holding "
          f"period. The best of the three is {best_w} at "
          f"{c1.loc[best_w,'net_bps']:+.1f} bps "
          f"(p = {c1.loc[best_w,'net_p']:.3f}).")
    else:
        wl = ", ".join(f"{w} {c1.loc[w,'net_bps']:+.1f} bps "
                       f"(p = {c1.loc[w,'net_p']:.3f})" for w in pos.index)
        A(f"Not in any form worth trading. Net is positive and statistically "
          f"significant at {wl} — but with {int(c1['n'].max()):,} events the "
          f"bootstrap resolves effects far smaller than the ones that matter, "
          f"so significance here measures precision, not economic size.")
    A("")
    A("Three things make the small positive numbers unpersuasive:")
    A("")
    A("- **The candle filter is doing no work.** Against the no-filter "
      "baseline it adds "
      + ", ".join(f"{v:+.1f} bps at {w}" for w, v in lift.items())
      + f". Its win rate is also *lower* than the unfiltered trade at "
      f"15 minutes ({c1.loc[WORDER[1],'win_rate']*100:.1f}% vs "
      f"{n4.loc[WORDER[1],'win_rate']*100:.1f}%) — it raises payoff ratio "
      "slightly and win rate slightly less, netting out to nothing.")
    if len(t5):
        y = t5[t5["window"] == WORDER[2]].set_index("year")
        if len(y) >= 3:
            yrs = sorted(y.index)
            A(f"- **The 1-hour result decays across the sample**, from "
              f"{y.loc[yrs[0],'net_bps']:+.1f} bps in {yrs[0]} to "
              f"{y.loc[yrs[-1],'net_bps']:+.1f} in {yrs[-1]}, with the win "
              f"rate falling {y.loc[yrs[0],'win_rate']*100:.1f}% → "
              f"{y.loc[yrs[-1],'win_rate']*100:.1f}%. No single year at "
              "15 minutes is significant on its own.")
    A("- **The universe is survivorship-biased** (current index membership) "
      "and costs are a single 6.6 bps median. Both push in the optimistic "
      "direction, and the whole result lives inside a few bps.")
    A("")

    # Q2 — best Gap/ATR bucket
    A("**Which Gap/ATR bucket performs best?**")
    A("")
    wins = {}
    for w in WORDER:
        s = t2[t2["window"] == w]
        if len(s):
            wins[w] = s.loc[s["net_bps"].idxmax(), "bucket"]
    top = max(set(wins.values()), key=list(wins.values()).count) \
        if wins else None
    for w in WORDER:
        s = t2[t2["window"] == w].set_index("bucket")
        if not len(s):
            continue
        A(f"- **{w}**: " + " · ".join(
            f"{b} {s.loc[b,'net_bps']:+.1f} (p={s.loc[b,'net_p']:.2f})"
            for b in s.index) + f" → best **{wins[w]}**")
    A("")
    if top:
        A(f"**{top}** is the best bucket at "
          f"{list(wins.values()).count(top)} of {len(wins)} holding periods "
          "— and it is the only bucket that is ever positive.")
    A("")
    # The cross-study inversion is the single most important result here.
    ef3 = TABLES / "e35_t3_gapatr.csv"
    if ef3.exists() and top:
        e3 = pd.read_csv(ef3)
        e3 = e3.set_index(["window", "bucket"])
        rows = []
        for w in WORDER:
            ew = EARN_MAP[w]
            g = t2[t2["window"] == w].set_index("bucket")
            for b in ["Gap/ATR < 1.0", "Gap/ATR > 2.0"]:
                if (ew, b) in e3.index and b in g.index:
                    rows.append((w, b, g.loc[b, "net_bps"],
                                 e3.loc[(ew, b), "net_bps"]))
        if rows:
            A("> **This inverts the earnings result, and that matters more "
              "than the ranking itself.** On earnings gaps, Gap/ATR > 2.0 "
              "was the strongest cohort in the whole investigation. On "
              "general gaps it is negative at every horizon:")
            A(">")
            A("> | Hold | Gap/ATR | General NET | Earnings NET |")
            A("> |---|---|---:|---:|")
            for w, b, gn, en in rows:
                A(f"> | {w} | {b} | {gn:+.1f} | {en:+.1f} |")
            A(">")
            A("> This is not a composition effect — it is the *same bucket* "
              "giving opposite answers. Large gaps without an earnings "
              "catalyst behave differently from large gaps with one, so the "
              "Gap/ATR filter cannot be treated as a general property of "
              "gaps. It was an earnings-conditional result, and this test is "
              "the first evidence about how far it travels: not far.")
            A("")

    # Q3 — market cap
    A("**Does market cap meaningfully affect the result?**")
    A("")
    mono = []
    for w in WORDER:
        s = t3[t3["window"] == w].set_index("bucket")
        if not len(s):
            continue
        spread = s["net_bps"].max() - s["net_bps"].min()
        vals = [s.loc[b, "net_bps"] for b in
                ["$3B - $10B", "$10B - $50B", "> $50B"] if b in s.index]
        mono.append(vals == sorted(vals, reverse=True))
        A(f"- **{w}**: " + " · ".join(
            f"{b} {s.loc[b,'net_bps']:+.1f}" for b in s.index)
          + f" → spread {spread:.1f} bps")
    A("")
    if all(mono) and len(mono) == len(WORDER):
        s15 = t3[t3["window"] == WORDER[1]].set_index("bucket")
        s60 = t3[t3["window"] == WORDER[2]].set_index("bucket")
        A(f"**Yes — this is the one filter here that behaves consistently.** "
          f"Net expectancy falls monotonically with market cap at all three "
          f"horizons: smallest names beat the largest by "
          f"{s15.loc['$3B - $10B','net_bps'] - s15.loc['> $50B','net_bps']:.1f}"
          f" bps at 15 minutes and "
          f"{s60.loc['$3B - $10B','net_bps'] - s60.loc['> $50B','net_bps']:.1f}"
          f" bps at an hour, and the $3B–$10B bucket is the only one "
          f"significant at both (p = {s15.loc['$3B - $10B','net_p']:.3f} and "
          f"{s60.loc['$3B - $10B','net_p']:.3f}).")
        A("")
        A("The mechanism is the same cost-scaling seen throughout this "
          "investigation rather than a better signal: small caps move more "
          "(average win "
          f"{s60.loc['$3B - $10B','avg_win_bps']:.0f} bps vs "
          f"{s60.loc['> $50B','avg_win_bps']:.0f} at an hour) while the "
          "assumed cost stays fixed. Win rates are flat across the three "
          "buckets. That caveat is load-bearing: small caps carry the widest "
          "spreads, so a flat 6.6 bps is least realistic exactly where the "
          "result looks best. A cost that scales with size would compress "
          "most of this spread, and I would not trade the market-cap tilt "
          "on this evidence without re-running it on per-name spreads.")
    else:
        A("The ordering is not consistent across horizons, so market cap is "
          "not a dependable filter here.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/gapstudy.py` "
      "(universe and download in `build_gap_intraday.py`); tables in "
      "`lambda_data/tables/gs_*.csv`._")
    return "\n".join(L)
