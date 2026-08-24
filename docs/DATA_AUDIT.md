# Data Audit — HF Data Library vs Yahoo daily

**Question:** could Run 1's Verdict C be an artefact of missing events or bad
bars in HF, rather than a statement about this market sample?

**Discipline:** no IC, no score, no hypothesis test was computed. This document
compares the daily envelope implied by the Run 1 HF 5-minute bars against an
independent daily feed, and nothing else.

**Sources**

| Source | What was used | Status |
|---|---|---|
| HF Data Library | The prepared 5-min RTH bars from Run 1: SPY 4,066 sessions, IWM 4,064, 2006-01-03 → 2022-02-28 | Used |
| Yahoo Finance daily | SPY and IWM daily OHLC, same dates, via the chart API through `requests` | Used |
| Yahoo 5-minute | — | **Not used.** Yahoo does not serve intraday history this far back; anything it returned would not overlap the sample |
| TradingView | — | **Not used.** No TV 5-minute export overlapping 2021–2022 is available in this session. Comparing 2025–26 TV bars against a 2022-ending sample would not be a vendor check, and was not done |

Artifacts: `results/audit/SPY_daily_compare.csv`,
`IWM_daily_compare.csv`, `event_day_table.csv`, `audit_summary.json`.
Code: `stage1/audit_vendor.py`.

---

## 0. A correction to this audit's own first pass

The first run reported HF capturing only **83%** of Yahoo's daily range, which
looked alarming. It was wrong, and the cause matters.

**HF is dividend back-adjusted; Yahoo raw quote is not.** Median `hf_close /
y_close`:

| Year | 2006 | 2010 | 2015 | 2020 | 2021 | 2022 |
|---|---|---|---|---|---|---|
| ratio | 0.741 | 0.806 | 0.889 | 0.982 | 0.993 | **1.000** |

A ratio converging to 1.0 at the end of the sample is the signature of
multiplicative back-adjustment. Comparing raw price *ranges* across two
different scales understates HF's range by exactly that factor.

Corrected, scale-free metric used throughout below:

```
capture = (hf_high - hf_low) / hf_close      <-- HF range as a share of its own close
          ---------------------------------
          (y_high  - y_low ) / y_close       <-- Yahoo range as a share of its own close
```

| Metric | SPY | IWM |
|---|---|---|
| Raw (contaminated) range ratio | 0.834 | 0.886 |
| **Scale-free capture, median** | **0.988** | **0.990** |

**This settles `adjustment_convention: PENDING` in the pre-registration:
multiplicative back-adjustment.** Because every Stage 1 feature (`BD`, `CL`,
`SA`, `CONV`, `DQ`) is a ratio within a single bar, a constant per-day scale
factor cancels exactly. The adjustment does not affect Run 1's scores.

---

## 1. Daily completeness

| | SPY | IWM |
|---|---|---|
| Sessions in HF | 4,066 | 4,064 |
| Sessions in Yahoo | 4,067 | 4,067 |
| Sessions compared | 4,066 | 4,064 |
| **In Yahoo, missing from HF** | **1** — 2007-01-30 | **3** — 2007-01-23, 2007-01-26, 2007-01-30 |
| **In HF, missing from Yahoo** | 0 | 0 |
| Half-day-shaped sessions (≤46 bars) | 35 | 36 |

Whole-session coverage is essentially complete: 1 and 3 absent days out of
~4,066. Half-day counts (35–36 over 16 years) are consistent with the US
holiday calendar and are not anomalies.

**Within-session completeness is the weaker point.**

| | SPY | IWM |
|---|---|---|
| Median bars per session | **75** of 78 | **75** of 78 |
| Sessions with < 70 bars | 78 | 79 |
| Sessions with < 40 bars | 6 | 8 |
| Minimum bars in a session | 37 | **3** (2008-02-12) |
| **Sessions missing the 09:30 bar** | **389 (9.6%)** | **524 (12.9%)** |

A typical session is missing about three 5-minute bars. The opening bar is
absent on roughly one session in ten.

**The missing opening bar is not event-driven** — it is *less* common on big
days (SPY 2.4% of |return| > 3% sessions vs 9.8% of calm ones; IWM 6.6% vs
13.2%). It looks like ordinary sparse-print behaviour in the early years, not
suppression of volatile opens.

---

## 2. Event-day checklist

Full table with every named day and every |SPY Yahoo return| > 3% session:
`results/audit/event_day_table.csv` (371 rows across both symbols).
`high_bp` / `low_bp` below are scale-free: HF's extreme relative to its own
close, against Yahoo's relative to its own close, in basis points. Negative
`high_bp` means **HF's high is below Yahoo's**; positive `low_bp` means **HF's
low is above Yahoo's** — both mean HF did not print the extreme.

### SPY

| Date | bars | 09:30? | capture | Yahoo ret | high_bp | low_bp | note |
|---|---|---|---|---|---|---|---|
| 2008-09-15 | 76 | yes | 0.781 | −4.76% | −100 | 0 | high truncated |
| 2008-09-16 | 78 | yes | 0.986 | +1.67% | −5 | +1 | clean |
| 2008-09-17 | 75 | yes | **0.698** | −4.50% | −103 | +45 | both extremes short |
| 2008-09-18 | 78 | yes | 0.998 | +2.97% | −38 | −40 | clean |
| 2008-09-19 | 77 | yes | 0.989 | +3.37% | −87 | −86 | clean |
| 2008-09-22 | 74 | yes | 1.011 | −2.26% | +56 | +54 | clean |
| 2008-09-23 | 77 | yes | 0.990 | −2.28% | 0 | +3 | clean |
| 2008-09-24 | 75 | yes | 0.928 | +0.32% | −18 | −5 | mild |
| 2008-09-25 | 76 | yes | 0.906 | +1.56% | −11 | +17 | mild |
| 2008-09-26 | 75 | yes | 0.980 | +0.05% | −44 | −40 | clean |
| 2008-09-29 | 74 | yes | 0.986 | **−7.84%** | −129 | −128 | clean capture |
| 2008-09-30 | 78 | yes | **0.709** | +4.14% | −53 | +109 | low truncated |
| 2008-10-01 | 73 | yes | 0.970 | +0.06% | −4 | +3 | clean |
| 2008-10-02 | 78 | yes | 1.012 | −3.63% | +50 | +48 | clean |
| 2008-10-03 | 74 | yes | 0.996 | −1.35% | +28 | +32 | clean |
| 2008-10-06 | 75 | yes | 0.987 | −5.09% | −150 | −152 | clean capture |
| 2008-10-07 | 77 | yes | 1.002 | −4.48% | +26 | +26 | clean |
| 2008-10-08 | 74 | **no** | 0.961 | −2.52% | −150 | −136 | opening bar absent |
| 2008-10-09 | 76 | yes | 0.989 | −6.98% | −47 | −40 | clean |
| 2008-10-10 | 74 | yes | 0.805 | −2.43% | **−405** | −213 | **high missed by 4%** |
| **2010-05-06** | 75 | yes | **0.587** | −3.32% | −3 | **+468** | **flash-crash low missed by 4.7%** |
| 2015-08-24 | 75 | yes | 0.891 | −4.21% | −82 | +1 | high truncated |
| 2018-02-05 | 77 | yes | 0.944 | −4.18% | −10 | +17 | mild |
| 2020-03-09 | 74 | yes | 0.999 | −7.81% | −6 | −6 | clean |
| 2020-03-12 | 72 | yes | 0.910 | −9.57% | −63 | +1 | mild |
| 2020-03-16 | 74 | **no** | 1.001 | **−10.94%** | +18 | +19 | range clean, opening bar absent |

### IWM — the same days, worst cases

| Date | bars | 09:30? | capture | Yahoo ret | high_bp | low_bp |
|---|---|---|---|---|---|---|
| 2008-09-19 | 75 | **no** | **0.344** | +4.46% | **−956** | −40 |
| 2008-09-22 | 74 | yes | 0.716 | −4.07% | +4 | **+213** |
| 2008-09-29 | 75 | yes | 0.724 | −7.90% | −247 | −43 |
| 2008-10-10 | 71 | **no** | 0.765 | +4.92% | **−397** | −55 |
| **2010-05-06** | 74 | **no** | **0.658** | −3.75% | +2 | **+371** |
| 2015-08-24 | 78 | yes | 0.912 | −3.90% | −61 | −10 |
| 2020-03-16 | 72 | **no** | 1.003 | −13.27% | +33 | +33 |

### Aggregate over all |Yahoo return| > 3% sessions

| | SPY | IWM |
|---|---|---|
| Sessions | 123 | 229 |
| Median capture | 0.986 | 0.996 |
| Capture < 0.90 | **35.8%** | 15.7% |
| Capture < 0.75 | **14.6%** | 7.0% |
| Capture < 0.90 on *calm* days | 15.0% | 11.3% |
| corr(\|return\|, capture) | −0.126 | −0.037 |

**Big-move days are about 2.4× more likely to be badly truncated than calm
days on SPY.** The direction is unambiguous even though the median event day is
captured fine.

### But the worst days are not event days

SPY's six worst captures among event-or-big-move sessions are all *unnamed*
days: 2020-02-24 (0.374), 2011-11-30 (0.402), 2009-02-17 (0.416), 2016-06-24
(0.517), 2011-08-18 (0.533), 2011-12-20 (0.545). Across the whole sample the
single worst are ordinary sessions — 2017-04-24 (0.278, a +1.1% day) and
2019-12-16 (0.332, +0.7%). IWM's 2008-02-12 has **3 bars out of 78**.

So truncation is **broad and sporadic**, with an event-day tilt — not a
targeted failure on crisis days.

---

## 3. Integrity

**Timezone and bar label** — already established during Run 1 and unchanged
here. HF stamps are naive **America/New_York wall-clock**, and the 1-minute
bars are **open-labelled** (session runs 09:30 → 15:59). Run 1's first attempt
parsed the naive stamps as UTC and shifted every bar five hours into
pre-market; the bar-label detector refused to classify the result and raised,
which is the only reason it was caught. The corrected handling is what produced
the bars audited here, and this audit independently supports it: HF opens align
with Yahoo opens on the sessions where the 09:30 bar exists.

**Zero-range bars are rare and cluster on quiet days, not events.**

| | SPY | IWM |
|---|---|---|
| Zero-range bars in 16 years | **18** | **33** |
| Days with any | 13 | 26 |
| Median \|return\| on those days | 0.25% | 0.29% |
| Median \|return\| overall | 0.50% | 0.75% |

Zero-range bars occur on days about **half as volatile** as the median. They
are quiet-tape artefacts, not crisis artefacts. This is the reassuring result:
the degenerate bars that Run 1's NaN gate removed were not event bars.

**Empty-grid rows** (bars never built, left as NaN holes) numbered 11,158 for
SPY and 11,749 for IWM across ~316,000 grid slots — about 3.5%, consistent with
the median of 75 live bars per 78-bar session. Under the strict-spacing rule
those produce `NaN` forward returns and are excluded rather than mis-computed.

---

## 4. Verdict on the source

### Safe enough to keep Verdict C — with a narrower scope sentence

**The defects found are real but of the wrong kind to manufacture Run 1's
result.** The reasoning:

1. **Truncated extremes add noise to the denominator.** A missing high or low
   understates `R`, which inflates `CONV` and distorts `CL`/`SA` on that bar.
   That corrupts individual scores — but the corruption is **idiosyncratic**,
   driven by which prints happened to be missing, and carries no systematic
   relationship to the *next* bar's direction. Measurement error of that kind
   **attenuates** an information coefficient toward zero. It does not flip its
   sign, and it does not produce a −0.029 IC that holds in 58 of 61
   independent calendar blocks over 16 years.

2. **Missing bars are excluded, not mis-computed.** The strict forward-spacing
   rule makes `r_1` undefined across any grid hole, so the ~3.5% of unbuilt
   bars cost sample rather than injecting error.

3. **Whole-session coverage is essentially complete** — 1 of 4,066 sessions
   missing for SPY. There is no era, regime or crisis window absent from the
   sample.

4. **Zero-range bars do not cluster on event days**, so the degenerate-bar gate
   was not quietly deleting the crisis.

5. **The event-day tilt runs the wrong way to help.** Truncation is *more*
   common on big days, which makes the sample marginally *less* eventful than
   the market. That would weaken a real effect, not create a spurious one.

### But the scope sentence must change

Run 1's finding is a statement about **the market as recorded by a
last-trade, dividend-back-adjusted 5-minute tape that misses roughly 3 bars per
session, omits the opening bar on one session in ten, and understates the range
on about a third of big-move days.** That is a fair description of most retail
and prosumer intraday data — but it is not "the market", and specifically it is
**not a tape you should quote for intraday extremes**.

Two consequences worth carrying:

- Any future study that depends on **the opening bar** (the parked Study B)
  inherits a 9.6–12.9% missing rate on exactly the bar it studies. That is a
  spec-level problem for Study B, not a Run 1 problem.
- Any study that depends on **intraday extremes** — stop placement, MAE/MFE,
  range breakouts — cannot use this source without a better tape.

### An honest ambiguity this audit cannot resolve

On **2010-05-06** HF's low sits 4.7% above Yahoo's. Two explanations fit
equally well:

- HF is truncated and missed the flash-crash low; or
- HF correctly excludes **busted trades**. Exchanges cancelled prints more than
  60% away from pre-crash levels that day, and a "clean" dataset that removes
  them would legitimately show a higher low than a feed that keeps them.

Nothing in a daily-vs-daily comparison can distinguish these. The same
ambiguity applies in weaker form to the 2008 days.

### What would still be needed to say more

| To establish | Requires |
|---|---|
| Whether 2010-05-06 is truncation or correct bust-filtering | A paid consolidated tape with **bust/cancel flags** for that session — TAQ, Polygon full-tick, or equivalent |
| Whether the 2008 and 2015-08-24 high/low gaps are real | Same tape, tick level, for those specific sessions |
| Whether Run 1's negative tilt is information or bid-ask bounce | **Quote midpoint** bars rather than last-trade — the microstructure control already parked in `clarify.md`. This is the more valuable of the two, because it addresses the mechanism rather than the coverage |
| A genuine second-vendor check | A 5-minute source overlapping **2006–2022**, not a recent-history feed. Neither Yahoo intraday nor TradingView provides that here |

**Ranking:** the midpoint control is worth more than the tape. This audit
already shows coverage is good enough that Verdict C stands; what it cannot
show is *why* the tilt is negative, and that is a quote-data question, not a
completeness question.

---

## Bottom line

Verdict C is **not** an artefact of missing events. Session coverage is
essentially complete, degenerate bars cluster on quiet days rather than crises,
and the truncation that does exist is idiosyncratic measurement error that
attenuates rather than reverses. Run 1 stands as a statement about this market
sample.

The audit did, however, settle one open field — HF is multiplicatively
back-adjusted, which is harmless for ratio features — and it flags a real,
specific problem for the parked opening-bar study, which would be built on the
one bar this source most often fails to deliver.
