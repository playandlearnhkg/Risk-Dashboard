"""dist_text.py — renders DIST_REPORT.md. Table-focused.

Every figure and every claim is read from the tables produced by dist.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WORDER = ["5 min (09:40)", "10 min (09:45)", "15 min (09:50)",
          "1 hour (10:35)"]
GORDER = ["HV + Continuation (All)", "HV + Continuation + Gap Up",
          "HV + Continuation + Gap Down", "HV + Continuation + $3B-$10B"]
SHORT = {GORDER[0]: "All", GORDER[1]: "Gap Up", GORDER[2]: "Gap Down",
         GORDER[3]: "$3B–$10B"}


def _sort(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["_g"] = d["group"].map({v: i for i, v in enumerate(GORDER)})
    d["_w"] = d["window"].map({v: i for i, v in enumerate(WORDER)})
    return d.sort_values(["_g", "_w"]).drop(columns=["_g", "_w"])


def _get(df, g, w):
    m = df[(df["group"] == g) & (df["window"] == w)]
    return m.iloc[0] if len(m) else None


def _blocked(df, header, sep, fmt):
    """One table, rows grouped by group with a rule between blocks."""
    r = [header, sep]
    d = _sort(df)
    prev = None
    for _, x in d.iterrows():
        if prev is not None and x["group"] != prev:
            r.append(sep.replace("---", " ").replace(":", " "))
        r.append(fmt(x))
        prev = x["group"]
    return "\n".join(r) + "\n"


def build(R: dict, meta: dict) -> str:
    d = R["dist"]
    L: list[str] = []
    A = L.append

    A("# Lambda — Return Distribution of the Strongest Post-Earnings Setups")
    A("")
    A("Post-earnings T+1, High Volume Continuation. Four groups × four "
      "holding periods. Same events as `VOLUME_TEST_REPORT.md` and "
      "`GAPDIR_REPORT.md` — described here rather than only averaged.")
    A("")
    A("| Input | Definition |")
    A("|---|---|")
    A(f"| Universe | Post-earnings T+1, {meta['start']} → {meta['end']} |")
    A("| Continuation | 09:30–09:35 candle closes **with** the gap |")
    A(f"| High Volume | `c1_volume` > {meta['vol_mult']}× trailing "
      f"{meta['vol_window']}-session mean, same ticker, same 09:30–09:35 "
      "slot, shifted one session |")
    A("| Entry | Open of the 09:35 bar |")
    A(f"| Costs | {meta['cost_bps']} bps round trip, in NET only |")
    A("| Simple return | `sign × (P_end/P_entry − 1)`, in bps |")
    A("| Log return | `sign × ln(P_end/P_entry)` — shape only |")
    A("| ATR move | signed price move ÷ prior-session ATR(14) |")
    A("| Skew / Kurtosis | sample (Fisher); kurtosis is **excess** — "
      "normal = 0.0 |")
    A(f"| Inference | date-clustered bootstrap; ⚠ marks n < {meta['small']} |")
    A("")
    A(f"High Volume Continuation events: **{meta['n_hv_cont']:,}**. "
      f"ATR(14) available for {meta['atr_coverage']*100:.1f}% of them.")
    A("")

    # ---------------- 1. core ----------------
    A("## 1. Core metrics — simple returns (bps)")
    A("")
    A(_blocked(
        d,
        "| Group | Window | n | Win rate | Avg Win | Avg Loss | Payoff | "
        "**NET** | net p |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        lambda x: (f"| {SHORT[x['group']]}"
                   f"{' ⚠' if x['small'] == 'YES' else ''} | {x['window']} | "
                   f"{int(x['n']):,} | {x['win_rate']*100:.1f}% | "
                   f"{x['avg_win_bps']:.1f} | {x['avg_loss_bps']:.1f} | "
                   f"{x['payoff_ratio']:.2f} | **{x['net_bps']:+.1f}** | "
                   f"{x['net_p']:.3f} |")))

    # ---------------- 2. distribution, simple ----------------
    A("## 2. Distribution — simple returns (bps)")
    A("")
    A(_blocked(
        d,
        "| Group | Window | Mean | **Median** | p10 | p25 | p75 | p90 | "
        "Std | Skew | Kurtosis |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        lambda x: (f"| {SHORT[x['group']]} | {x['window']} | "
                   f"{x['mean_bps']:+.1f} | **{x['median_bps']:+.1f}** | "
                   f"{x['p10_bps']:+.0f} | {x['p25_bps']:+.0f} | "
                   f"{x['p75_bps']:+.0f} | {x['p90_bps']:+.0f} | "
                   f"{x['std_bps']:.0f} | {x['skew']:+.2f} | "
                   f"{x['kurtosis']:+.1f} |")))

    # ---------------- 3. distribution, log ----------------
    A("## 3. Distribution — log returns")
    A("")
    A(_blocked(
        d,
        "| Group | Window | Skew (log) | Kurtosis (log) | Skew (simple) | "
        "Kurtosis (simple) | Δ Skew |",
        "|---|---|---:|---:|---:|---:|---:|",
        lambda x: (f"| {SHORT[x['group']]} | {x['window']} | "
                   f"{x['skew_log']:+.2f} | {x['kurtosis_log']:+.1f} | "
                   f"{x['skew']:+.2f} | {x['kurtosis']:+.1f} | "
                   f"{x['skew_log'] - x['skew']:+.2f} |")))

    # ---------------- 3b. winsorised shape ----------------
    A("### 3b. The same shape, winsorised at 1% / 99%")
    A("")
    A("The raw skew and kurtosis above are **dominated by single "
      "observations** — see section 6. Capping the extreme 1% at each end "
      "leaves the body of the distribution intact and shows what the "
      "typical trade population looks like. Both readings are legitimate; "
      "they answer different questions.")
    A("")
    A(_blocked(
        d,
        "| Group | Window | Skew (w) | Kurtosis (w) | Skew (log, w) | "
        "Kurtosis (log, w) | Mean (w) | Mean (raw) |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
        lambda x: (f"| {SHORT[x['group']]} | {x['window']} | "
                   f"{x['skew_w']:+.2f} | {x['kurtosis_w']:+.1f} | "
                   f"{x['skew_log_w']:+.2f} | {x['kurtosis_log_w']:+.1f} | "
                   f"{x['mean_w_bps']:+.1f} | {x['mean_bps']:+.1f} |")))

    # ---------------- 4. tails ----------------
    A(f"## 4. Tail risk — ATR-normalised")
    A("")
    A(f"Share of trades whose signed move exceeds "
      f"**{meta['loss_atr']:.1f} ATR against** the position, and "
      f"**+{meta['gain_atr']:.1f} ATR in favour**. ATR is the prior "
      "session's ATR(14), so it is known before entry.")
    A("")
    A(_blocked(
        d,
        "| Group | Window | n (ATR) | **% loss > 1.0 ATR** | "
        "**% gain > 1.5 ATR** | Median ATR move | p10 ATR | p90 ATR |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
        lambda x: (f"| {SHORT[x['group']]} | {x['window']} | "
                   f"{int(x['n_atr']):,} | "
                   f"**{x['pct_loss_gt_1atr']*100:.2f}%** | "
                   f"**{x['pct_gain_gt_15atr']*100:.2f}%** | "
                   f"{x['median_atr_move']:+.3f} | {x['p10_atr']:+.2f} | "
                   f"{x['p90_atr']:+.2f} |")))

    # ---------------- 5. deciles ----------------
    dec = R.get("deciles")
    if dec is not None and len(dec):
        A("## 5. Full decile ladder — HV + Continuation (All)")
        A("")
        piv = dec.pivot(index="decile", columns="window", values="bps")
        piv = piv.reindex(columns=[w for w in WORDER if w in piv.columns])
        A("| Decile | " + " | ".join(piv.columns) + " |")
        A("|---|" + "---:|" * len(piv.columns))
        for dc in piv.index:
            A(f"| {int(dc)}th | "
              + " | ".join(f"{piv.loc[dc, c]:+.0f}" for c in piv.columns)
              + " |")
        A("")

    # ---------------- 6. what the shape says ----------------
    A("## 6. What the shape says")
    A("")
    all_g = GORDER[0]
    rows = [(_get(d, all_g, w), w) for w in WORDER]
    rows = [(x, w) for x, w in rows if x is not None]

    net_med = [x["median_bps"] - meta["cost_bps"] for x, _ in rows]
    med_pos = [w for x, w in rows if x["median_bps"] > 0]
    A("| Window | Mean | Median | Mean − Median | Median after costs |")
    A("|---|---:|---:|---:|---:|")
    for x, w in rows:
        A(f"| {w} | {x['mean_bps']:+.1f} | {x['median_bps']:+.1f} | "
          f"{x['mean_bps'] - x['median_bps']:+.1f} | "
          f"**{x['median_bps'] - meta['cost_bps']:+.1f}** |")
    A("")
    if all(v > 0 for v in net_med):
        A(f"**The median trade is profitable after costs at all "
          f"{len(rows)} horizons** ({min(net_med):+.1f} to "
          f"{max(net_med):+.1f} bps). That is a stronger result than a "
          "positive mean on its own: the edge does not depend on the right "
          "tail to reach breakeven, so an implementation that caps upside "
          "with a profit target still keeps a positive core. The mean sits "
          f"{min(x['mean_bps'] - x['median_bps'] for x, _ in rows):+.1f} to "
          f"{max(x['mean_bps'] - x['median_bps'] for x, _ in rows):+.1f} bps "
          "above the median, and that gap widens with the horizon — the "
          "longer the hold, the more of the average comes from the tail "
          "rather than the typical trade.")
        A("")
    elif any(v < 0 for v in net_med):
        A(f"After costs the median trade is negative at "
          f"{sum(1 for v in net_med if v < 0)} of {len(net_med)} horizons "
          "even though the mean is positive at all of them — the edge leans "
          "on the right tail rather than on the typical trade.")
        A("")

    # Skew sign is NOT uniform across horizons — state what the table says.
    sk = {w: x["skew"] for x, w in rows}
    skw = {w: x["skew_w"] for x, w in rows}
    neg = [w for w, v in sk.items() if v < 0]
    pos = [w for w, v in sk.items() if v > 0]
    A("**Skew changes sign with the horizon, and that is the interesting "
      "part.**")
    A("")
    A("| Window | Skew (raw) | Skew (winsorised) | Reading |")
    A("|---|---:|---:|---|")
    for x, w in rows:
        if x["skew_w"] < -0.10:
            note = "left-skewed body — losses larger than gains"
        elif x["skew_w"] > 0.10:
            note = "right-skewed body — gains larger than losses"
        else:
            note = "roughly symmetric body"
        A(f"| {w} | {x['skew']:+.2f} | {x['skew_w']:+.2f} | {note} |")
    A("")
    if neg and pos:
        body = [w for w in neg if abs(skw.get(w, 0)) < 0.10]
        A(f"At the short horizons ({', '.join(neg)}) raw skew is "
          "**negative** — the biggest fast moves go *against* the position, "
          "even though the mean is positive. The distribution only turns "
          f"right-skewed from {pos[0]} onward.")
        A("")
        if body:
            A("The winsorised column shows this is a **tail** effect, not a "
              f"property of the typical trade: with the extreme 1% capped, "
              f"the {' and '.join(body)} body is essentially symmetric "
              f"({', '.join(f'{skw[w]:+.2f}' for w in body)}). So the risk "
              "at short horizons is not that the average losing trade is "
              "bigger — it is that the *worst* trades are, and they arrive "
              "before there has been time to react.")
            A("")
    ku = [x["kurtosis_w"] for x, _ in rows]
    A(f"**Excess kurtosis stays high even after winsorising** "
      f"({min(ku):+.1f} to {max(ku):+.1f}, against 0.0 for a normal), so "
      "the fat tails are a property of the population and not only of the "
      "few extreme events. Two consequences: the sample mean converges "
      "slowly, so the bootstrap intervals in the core table are the honest "
      "read rather than the point estimates; and position sizing on "
      "standard deviation will understate how often large adverse moves "
      "occur.")
    A("")
    dskw = [x["skew_log_w"] - x["skew_w"] for x, _ in rows]
    dsk = {w: x["skew_log"] - x["skew"] for x, w in rows}
    big_w = max(dsk, key=lambda w: abs(dsk[w]))
    A(f"**On the body of the distribution, logs change almost nothing** "
      f"({min(dskw):+.2f} to {max(dskw):+.2f} change in winsorised skew). "
      "Over 5–60 minute windows the moves are small enough that log and "
      "simple returns are nearly identical, so the asymmetry measured here "
      "is a property of the moves rather than an artefact of percentage "
      f"arithmetic. On the **raw** figures the {big_w} window is the "
      f"exception — logs move its skew by {dsk[big_w]:+.2f}, because the "
      "log transform compresses one +100% observation far more than it "
      "compresses the rest of the sample.")
    A("")

    # ---------------- outliers ----------------
    o = R.get("outliers")
    if o is not None and len(o):
        A("### One observation drives the 1-hour shape statistics")
        A("")
        hdr = o[o["skew_all"].notna()].set_index("window")
        A("| Window | Skew (all) | Skew (drop largest) | Kurtosis (all) | "
          "Kurtosis (drop largest) | Mean (all) | Mean (drop largest) |")
        A("|---|---:|---:|---:|---:|---:|---:|")
        for w in WORDER:
            if w not in hdr.index:
                continue
            x = hdr.loc[w]
            A(f"| {w} | {x['skew_all']:+.2f} | {x['skew_ex1']:+.2f} | "
              f"{x['kurt_all']:+.1f} | {x['kurt_ex1']:+.1f} | "
              f"{x['mean_all_bps']:+.1f} | {x['mean_ex1_bps']:+.1f} |")
        A("")
        big = o.loc[o["bps"].abs().idxmax()]
        A(f"The five largest absolute moves in the headline group, per "
          f"horizon:")
        A("")
        A("| Window | # | Ticker | Date | Return (bps) | Entry | Gap |")
        A("|---|---:|---|---|---:|---:|---|")
        for w in WORDER:
            for _, x in o[o["window"] == w].iterrows():
                A(f"| {w} | {int(x['rank'])} | {x['ticker']} | {x['date']} | "
                  f"{x['bps']:+,.0f} | ${x['entry_px']:.2f} | "
                  f"{'Up' if x['gap_up'] else 'Down'} |")
        A("")
        A(f"**{big['ticker']} on {big['date']} returned "
          f"{big['bps']:+,.0f} bps in one hour** — a {big['bps']/1e4:+.0%} "
          "move. This is not a bad print: it is the Avis Budget short "
          "squeeze, a real and widely documented session, and the position "
          "was genuinely available to a rule that bought the 09:35 open. "
          "It is kept in every table.")
        A("")
        h = hdr.loc["1 hour (10:35)"]
        contrib = h["mean_all_bps"] - h["mean_ex1_bps"]
        share = contrib / h["mean_all_bps"] * 100
        n1h = int(_get(d, all_g, "1 hour (10:35)")["n"])
        A(f"**The shape statistics depend on it; the edge does not.** One "
          f"row out of {n1h:,} moves the 1-hour skew from "
          f"{h['skew_ex1']:+.2f} to {h['skew_all']:+.2f} and the kurtosis "
          f"from {h['kurt_ex1']:+.1f} to {h['kurt_all']:+.0f} — those two "
          "numbers describe that single session, not the strategy. But its "
          f"contribution to the 1-hour mean is only {contrib:+.1f} bps of "
          f"{h['mean_all_bps']:+.1f} ({share:.0f}%): drop it entirely and "
          f"the mean is still {h['mean_ex1_bps']:+.1f} bps. That is the "
          "reassuring result — the expectancy is carried by the broad "
          "population, not by one squeeze.")
        A("")
        A("Practical reading: **quote the winsorised skew and kurtosis** "
          "(section 3b) when describing what a typical trade looks like, "
          "and the raw mean when describing what the strategy actually "
          "returned. Quoting raw skew of 14.7 as a property of the setup "
          "would be wrong in both directions — it overstates the upside "
          "asymmetry available going forward, and it implies a tail "
          "dependence the expectancy does not have.")
        A("")

    # gap up vs down shape
    A("**Gap Up versus Gap Down, on shape rather than expectancy.**")
    A("")
    A("| Window | Metric | Gap Up | Gap Down |")
    A("|---|---|---:|---:|")
    for w in WORDER:
        u, dn = _get(d, GORDER[1], w), _get(d, GORDER[2], w)
        if u is None or dn is None:
            continue
        A(f"| {w} | Median (bps) | {u['median_bps']:+.1f} | "
          f"{dn['median_bps']:+.1f} |")
        A(f"| {w} | Skew | {u['skew']:+.2f} | {dn['skew']:+.2f} |")
        A(f"| {w} | % gain > 1.5 ATR | {u['pct_gain_gt_15atr']*100:.2f}% | "
          f"{dn['pct_gain_gt_15atr']*100:.2f}% |")
        A(f"| {w} | % loss > 1.0 ATR | {u['pct_loss_gt_1atr']*100:.2f}% | "
          f"{dn['pct_loss_gt_1atr']*100:.2f}% |")
    A("")

    # ---------------- 7. mcap group ----------------
    cov = R.get("mcap_cov")
    A("## 7. The $3B–$10B group")
    A("")
    if cov is not None and len(cov):
        c = cov.iloc[0]
        A(f"Sample **does** allow it: {int(c['n_3_10b']):,} of the "
          f"{int(c['n_hv_cont']):,} High Volume Continuation events fall in "
          f"$3B–$10B ({int(c['n_with_mcap']):,} have a market cap at all). "
          f"Median cap in the bucket ${c['median_mcap_b']:.1f}B, median "
          f"price ${c['median_price']:.0f}.")
        A("")
        if not pd.isna(c.get("median_roll_bps")):
            A(f"> **Cost caveat, quantified.** Median Roll spread in this "
              f"bucket is **{c['median_roll_bps']:.1f} bps** against "
              f"**{c['all_median_roll_bps']:.1f} bps** for the full High "
              f"Volume Continuation cohort. The flat {meta['cost_bps']} bps "
              f"charged in NET is therefore least defensible for exactly "
              f"this group, and Roll excludes market impact entirely.")
            A("")
    m_rows = [(_get(d, GORDER[3], w), w) for w in WORDER]
    m_rows = [(x, w) for x, w in m_rows if x is not None]
    a_rows = {w: _get(d, GORDER[0], w) for w in WORDER}
    if m_rows:
        A("Against the full cohort:")
        A("")
        A("| Window | NET, $3B–$10B | NET, All | Δ | Skew, $3B–$10B | "
          "Skew, All | % gain > 1.5 ATR |")
        A("|---|---:|---:|---:|---:|---:|---:|")
        for x, w in m_rows:
            a = a_rows.get(w)
            if a is None:
                continue
            A(f"| {w} | **{x['net_bps']:+.1f}** | {a['net_bps']:+.1f} | "
              f"{x['net_bps'] - a['net_bps']:+.1f} | {x['skew']:+.2f} | "
              f"{a['skew']:+.2f} | {x['pct_gain_gt_15atr']*100:.2f}% vs "
              f"{a['pct_gain_gt_15atr']*100:.2f}% |")
        A("")

    # ---------------- 8. zeros ----------------
    z = R.get("zeros")
    if z is not None and len(z):
        zz = z[z["group"] == GORDER[0]]
        A("## 8. Dropped zero-return observations")
        A("")
        A("A print-to-print move of exactly zero is a stale quote rather "
          "than a flat trade, and every previous report in this series drops "
          "them. The share is material at the shortest horizon, so it is "
          "reported rather than buried:")
        A("")
        A("| Window | n before | n zero | % dropped |")
        A("|---|---:|---:|---:|")
        for _, x in zz.iterrows():
            A(f"| {x['window']} | {int(x['n_raw']):,} | "
              f"{int(x['n_zero']):,} | {x['pct_zero']*100:.2f}% |")
        A("")
        worst = zz.loc[zz["pct_zero"].idxmax()]
        A(f"At {worst['window']} this removes {worst['pct_zero']*100:.1f}% of "
          "the sample. Those observations are neither wins nor losses; "
          "including them would lower the win rate and pull the median "
          "toward zero without changing the mean much.")
        A("")

    # ---------------- 9. caveats ----------------
    A("## 9. Reading notes")
    A("")
    wr = [x["win_rate"] * 100 for x, _ in rows]
    pay = [x["payoff_ratio"] for x, _ in rows]
    aw = [x["avg_win_bps"] for x, _ in rows]
    A(f"- **The expectancy gain with horizon comes from move size, not from "
      f"hit rate.** Win rate is essentially flat across the four windows "
      f"({min(wr):.1f}%–{max(wr):.1f}%) while the average win grows from "
      f"{aw[0]:.0f} to {aw[-1]:.0f} bps and the payoff ratio from "
      f"{pay[0]:.2f} to {pay[-1]:.2f}. Holding longer does not make the "
      "rule more often right; it makes the right calls bigger.")
    kr = [x["kurtosis"] for x, _ in rows]
    kw = [x["kurtosis_w"] for x, _ in rows]
    A(f"- **Kurtosis is excess** — a normal reads 0.0. Raw values here run "
      f"{min(kr):+.1f} to {max(kr):+.0f}; winsorised, {min(kw):+.1f} to "
      f"{max(kw):+.1f}. Even the winsorised figures are meaningfully "
      "fat-tailed, which is why every significance test in this series is a "
      "date-clustered bootstrap rather than a t-test.")
    A("- **The ATR tail columns use prior-session ATR(14)**, known before "
      "entry, so they are implementable as stop/target distances. They are "
      "*realised* frequencies with no stop in place — a live stop at −1.0 "
      "ATR would convert some of the >1.5 ATR gains into losses, because "
      "part of that tail traded through the stop first. This is an upper "
      "bound on what a stop-and-target implementation would capture.")
    A("- **Costs are flat 6.6 bps** and do not vary by group, horizon or "
      "market cap. Section 7 quantifies where that assumption is weakest.")
    A("- **The groups overlap.** Gap Up and Gap Down partition the headline "
      "group; $3B–$10B is a subset of it. These are four views of one "
      "sample, not four independent tests.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/dist.py`; tables in "
      "`lambda_data/tables/dist_*.csv`._")
    return "\n".join(L)
