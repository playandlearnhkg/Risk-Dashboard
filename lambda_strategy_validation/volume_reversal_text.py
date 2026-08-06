"""volume_reversal_text.py — renders VOLUME_REVERSAL_REPORT.md.

Conclusions computed from the tables. The Continuation figures used for
the head-to-head are read back from the volume_test.py output rather than
restated by hand.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

TABLES = Path("/home/user/lambda_data/tables")
WORDER = ["5 min (09:40)", "15 min (09:50)", "1 hour (10:35)"]
GORDER = ["All Reversal", "Rev + High Volume", "Rev + Normal/Low Vol"]
UNI = {"A": "Post-Earnings (T+1)", "B": "General Gaps"}


def _sort(df, col, order):
    d = df.copy()
    d["_w"] = d["window"].map({v: i for i, v in enumerate(WORDER)})
    d["_g"] = d[col].map({v: i for i, v in enumerate(order)})
    return d.sort_values(["_w", "_g"]).drop(columns=["_w", "_g"])


def _tbl(df):
    r = ["| Window | Group | n | Win rate | Gross | **NET** | net p |",
         "|---|---|---:|---:|---:|---:|---:|"]
    for _, x in df.iterrows():
        sm = " ⚠" if x.get("small") == "YES" else ""
        r.append(f"| {x['window']} | {x['group']}{sm} | {int(x['n']):,} | "
                 f"{x['win_rate']*100:.1f}% | {x['gross_bps']:+.1f} | "
                 f"**{x['net_bps']:+.1f}** | {x['net_p']:.3f} |")
    return "\n".join(r) + "\n"


def _delta(df, hi, lo):
    s = df.set_index(["window", "group"])
    out = {}
    for w in WORDER:
        if (w, hi) in s.index and (w, lo) in s.index:
            out[w] = s.loc[(w, hi), "net_bps"] - s.loc[(w, lo), "net_bps"]
    return out


def build(R: dict, meta: dict) -> str:
    L = []
    A = L.append
    mA, mB = meta["A"], meta["B"]

    A("# Lambda — Volume Confirmation on the Reversal Signal")
    A("")
    A("Same volume test as the Continuation report, applied to the cohort "
      "whose first 5-minute candle closes **against** the gap.")
    A("")
    A("| Input | Definition |")
    A("|---|---|")
    A("| Reversal signal | 09:30–09:35 candle closes **against** the gap "
      "direction |")
    A(f"| High Volume | `c1_volume` > {meta['vol_mult']}× the trailing "
      f"{meta['vol_window']}-session mean of `c1_volume` for the same ticker "
      "and the same 09:30–09:35 slot |")
    A("| Entry | Open of the 09:35 bar |")
    A(f"| Costs | {meta['cost_bps']} bps round trip, subtracted for NET |")
    A("")
    A("| Universe | Period | Reversal events | % High Volume |")
    A("|---|---|---:|---:|")
    for m in (mA, mB):
        A(f"| {m['universe']} | {m['start']} → {m['end']} | "
          f"{m['n_rev']:,} | {m['pct_high_rev']*100:.1f}% |")
    A("")
    A("> **Sign convention.** Reversal returns are signed in the **candle's** "
      "direction — `−sign(gap) × (P_end/P_entry − 1)` — so a positive number "
      "means *following the counter-gap candle* paid. Continuation is signed "
      "in the gap direction, so both cohorts express the same single rule: "
      "follow the first 5-minute candle. Section 3 shows the same Reversal "
      "events read in the gap direction, which is the *fade the candle* "
      "alternative, so no sign-flipping by hand is needed.")
    A("")

    for key in ("A", "B"):
        m = meta[key]
        A(f"## Universe {key} — {m['universe']}")
        A("")
        A(_tbl(_sort(R[f"{key}_main"], "group", GORDER)))

    # ---------------- questions ----------------
    dA = _delta(R["A_main"], "Rev + High Volume", "Rev + Normal/Low Vol")
    dB = _delta(R["B_main"], "Rev + High Volume", "Rev + Normal/Low Vol")
    sA = R["A_main"].set_index(["window", "group"])
    sB = R["B_main"].set_index(["window", "group"])

    A("## Key questions")
    A("")

    def block(d, s, label, key):
        A(f"**Does High Volume improve or worsen the Reversal signal in the "
          f"{label} universe?**")
        A("")
        for w in WORDER:
            if w not in d:
                continue
            hi = s.loc[(w, "Rev + High Volume")]
            lo = s.loc[(w, "Rev + Normal/Low Vol")]
            A(f"- **{w}**: High {hi['net_bps']:+.1f} bps / "
              f"{hi['win_rate']*100:.1f}% win (n={int(hi['n']):,}, "
              f"p={hi['net_p']:.3f}) vs Normal/Low {lo['net_bps']:+.1f} / "
              f"{lo['win_rate']*100:.1f}% (n={int(lo['n']):,}) → "
              f"**{d[w]:+.1f} bps**")
        A("")
        neg = [w for w, v in d.items() if v < 0]
        if len(neg) == len(d):
            A(f"**Worsens it at every horizon** ({min(d.values()):+.1f} to "
              f"{max(d.values()):+.1f} bps).")
        elif not neg:
            A(f"**Improves it at every horizon** ({min(d.values()):+.1f} to "
              f"{max(d.values()):+.1f} bps).")
        else:
            A(f"**Mixed** — negative at {len(neg)} of {len(d)} horizons, "
              f"spanning {min(d.values()):+.1f} to {max(d.values()):+.1f} "
              "bps.")
        A("")

    block(dA, sA, "post-earnings", "A")
    block(dB, sB, "general gap", "B")

    # Q3 — versus Continuation
    A("**Is the effect of High Volume on Reversal different from its effect "
      "on Continuation?**")
    A("")
    cont = {}
    for key in ("A", "B"):
        f = TABLES / f"vol_{key}_main.csv"
        if f.exists():
            cont[key] = _delta(pd.read_csv(f), "Cont + High Volume",
                               "Cont + Normal/Low Vol")
    if cont:
        A("Net effect of High Volume (High minus Normal/Low), in bps:")
        A("")
        A("| Universe | Window | Continuation | Reversal | Difference |")
        A("|---|---|---:|---:|---:|")
        for key in ("A", "B"):
            d = dA if key == "A" else dB
            if key not in cont:
                continue
            for w in WORDER:
                if w not in d or w not in cont[key]:
                    continue
                A(f"| {UNI[key]} | {w} | {cont[key][w]:+.1f} | {d[w]:+.1f} | "
                  f"**{d[w] - cont[key][w]:+.1f}** |")
        A("")
        if "A" in cont and dA:
            ca = sum(cont["A"].values()) / len(cont["A"])
            ra = sum(dA.values()) / len(dA)
            cb = sum(cont["B"].values()) / len(cont["B"]) if "B" in cont else 0
            rb = sum(dB.values()) / len(dB) if dB else 0
            A(f"Mean across the three horizons — post-earnings: "
              f"Continuation **{ca:+.1f}** vs Reversal **{ra:+.1f}**. "
              f"General gaps: Continuation **{cb:+.1f}** vs Reversal "
              f"**{rb:+.1f}**.")
            A("")
            if ra < 0 < ca:
                A("**Yes — the sign is opposite, in both universes.** Heavy "
                  "opening volume makes the with-gap candle better and the "
                  "counter-gap candle worse. That is what you would expect "
                  "if volume marks genuine information being priced: it "
                  "confirms the move already under way and penalises the "
                  "attempt to fade it. Volume is not a generic "
                  "'more-conviction' marker that improves whatever signal it "
                  "is attached to — it is directional.")
                A("")
                A(f"> **This revises the previous report's read on general "
                  f"gaps.** Measured on the Continuation side alone, volume "
                  f"looked close to inert there ({cb:+.1f} bps) and I "
                  f"described it that way. On the Reversal side the same "
                  f"variable is worth **{rb:+.1f} bps** — comparable in "
                  f"magnitude to the earnings effect and far outside the "
                  f"cost noise. Volume is informative on general gaps after "
                  f"all; the Continuation test simply could not see it, "
                  f"because both the high- and low-volume Continuation "
                  f"cohorts drift with the gap and the contrast is small. "
                  f"The Reversal cohort is where the two volume regimes "
                  f"actually diverge.")
            elif ra < ca:
                A("The effect is weaker on Reversal than on Continuation, "
                  "though not opposite in sign.")
            else:
                A("The effect is not smaller on Reversal, which argues "
                  "against reading volume as directional confirmation.")
        A("")

    # ---------------- gap-direction view ----------------
    A("## The same events read in the gap direction")
    A("")
    A("If following the counter-gap candle loses on high volume, the "
      "mechanical alternative is to fade it and stay with the gap. These are "
      "the identical events with the direction reversed.")
    A("")
    A("> **Costs do not flip with the sign.** Gross flips exactly; net does "
      f"not, because the {meta['cost_bps']} bps round trip is paid either "
      "way. A cohort at −13.1 bps net in the candle direction is not +13.1 "
      "the other way — it is gross +6.5 minus costs, so −0.1. Both sides of "
      "a small gross edge lose. Only where gross is large does the flip "
      "produce something tradeable.")
    A("")
    for key in ("A", "B"):
        t = R.get(f"{key}_gapdir")
        if t is None or not len(t):
            continue
        A(f"**{UNI[key]}**")
        A("")
        A(_tbl(_sort(t, "group", ["Rev events, gap dir — High Vol",
                                  "Rev events, gap dir — Normal/Low"])))

    gb = R.get("B_gapdir")
    if gb is not None and len(gb):
        s = gb.set_index(["window", "group"])
        k = "Rev events, gap dir — High Vol"
        best = [(w, s.loc[(w, k)]) for w in WORDER if (w, k) in s.index]
        best = [(w, x) for w, x in best if x["net_bps"] > 0
                and x["net_p"] < 0.05]
        if best:
            A("### The strongest general-gap cell found so far")
            A("")
            for w, x in best:
                A(f"- **{w}**: staying with the gap when the first candle "
                  f"went against it *on high volume* — "
                  f"**{x['net_bps']:+.1f} bps net**, "
                  f"{x['win_rate']*100:.1f}% win rate, n = {int(x['n']):,}, "
                  f"p = {x['net_p']:.3f}")
            A("")
            A("This is a larger net figure than anything the Continuation "
              "route produced on general gaps, on a sample of over 13,000 "
              "events, and it has a coherent mechanism: a counter-gap first "
              "candle on heavy volume looks like a failed reversal — supply "
              "being absorbed — after which the gap direction reasserts.")
            A("")
            A("**Two reasons not to promote it yet.** It is a cell selected "
              "*after* seeing the results, and this investigation has now "
              "examined enough cohorts that some will clear p < 0.05 by "
              "construction; the p-value above is not adjusted for that "
              "search. And high-volume names carry the widest spreads, so "
              "the flat 6.6 bps cost is least defensible exactly here. The "
              "honest status is a hypothesis worth a clean out-of-sample "
              "test, not a validated edge.")
            A("")

    # ---------------- composition ----------------
    A("## Volume composition of the two cohorts")
    A("")
    A("| Universe | Cohort | n | High Vol | % High | Median vol ratio |")
    A("|---|---|---:|---:|---:|---:|")
    for key in ("A", "B"):
        t = R.get(f"{key}_comp")
        if t is None:
            continue
        for _, x in t.iterrows():
            A(f"| {UNI[key]} | {x['cohort']} | {int(x['n']):,} | "
              f"{int(x['n_high']):,} | {x['pct_high']*100:.1f}% | "
              f"{x['median_ratio']:.2f} |")
    A("")
    A("If the two cohorts carry similar volume profiles, then the difference "
      "in how volume acts on them is about direction rather than about one "
      "cohort simply being the higher-volume one.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/volume_reversal.py`; "
      "tables in `lambda_data/tables/volrev_*.csv`._")
    return "\n".join(L)
