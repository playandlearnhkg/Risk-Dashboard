# Lambda — Three-Way Doji Classification of the First 5-Minute Candle

Post-earnings T+1, High Volume filter applied throughout.

| Input | Definition |
|---|---|
| Universe | Post-earnings T+1, 2015-01-27 → 2025-12-22 |
| Doji / Indecisive | `\|body\| / (high − low) ≤ 0.10` |
| Continuation | closes **with** the gap and is **not** a doji |
| Reversal | closes **against** the gap and is **not** a doji |
| High Volume | `c1_volume` > 1.5× trailing 20-session mean, same ticker, same 09:30–09:35 slot, shifted one session |
| Entry | Open of the 09:35 bar |
| Costs | 6.6 bps round trip, in NET only |
| Skew / Kurtosis | sample (Fisher); kurtosis is **excess** — normal = 0.0 |
| Inference | date-clustered bootstrap; ⚠ marks n < 150 |

> ## ⚠ This carve-out was already in place
>
> The classifier used by **every previous report in this series** (`simple_first_candle`) already excludes dojis from both Continuation and Reversal, at this exact 0.10 body/range threshold. Groups 1 and 2 below therefore **reproduce the published figures rather than revising them** — the Continuation numbers here are the same ones in `VOLUME_TEST_REPORT.md`, `DIST_REPORT.md` and `GAPDIR_REPORT.md`.
>
> Two things here are genuinely new: the **Indecisive group**, which has never been reported on its own, and the **counterfactual in section 3** — a with-dojis Continuation cohort built specifically to measure what the carve-out is worth. Without that counterfactual the question "does removing dojis improve the edge?" cannot be answered from these tables at all, because both candidate answers would be the same column of numbers.
>
> The specification asks for `≤ 0.10` where the existing code uses `< 0.10`. No event on this data sits exactly on the boundary, so the two produce an identical partition.

Of **9,720** High Volume events: **4,938** Continuation, **3,980** Reversal, **802** Indecisive (8.3%). Of the dojis, 424 closed marginally with the gap and 378 against it. No event in this cohort had a zero-range first candle — the no-print guard removes those before classification — so the zero-range rule never binds.

> **Sign conventions.** Continuation is signed in the gap direction. Reversal is signed in the **candle** direction, unchanged from the earlier reports, so positive means following the counter-gap candle paid. Indecisive is signed in the **gap** direction — a doji carries no usable direction of its own, so the gap is the only information available at 09:35. Section 5 shows the candle-direction reading of the same events.

## 1. Core performance

| Group | Window | n | Win rate | **NET** | Avg Win | Avg Loss | Payoff | net p |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 5 min (09:40) | 4,870 | 58.3% | **+7.8** | 72.0 | 66.2 | 1.09 | 0.000 |
| Continuation | 10 min (09:45) | 4,900 | 58.8% | **+14.8** | 93.2 | 81.0 | 1.15 | 0.000 |
| Continuation | 15 min (09:50) | 4,904 | 59.9% | **+23.7** | 110.3 | 89.5 | 1.23 | 0.000 |
| Continuation | 1 hour (10:35) | 4,908 | 58.4% | **+30.1** | 153.6 | 127.0 | 1.21 | 0.000 |
| | |  |  |  |  |  |  |  |
| Reversal | 5 min (09:40) | 3,913 | 50.3% | **-7.6** | 71.0 | 73.8 | 0.96 | 0.000 |
| Reversal | 10 min (09:45) | 3,942 | 48.3% | **-10.1** | 90.7 | 91.5 | 0.99 | 0.000 |
| Reversal | 15 min (09:50) | 3,954 | 48.3% | **-13.1** | 102.6 | 108.4 | 0.95 | 0.000 |
| Reversal | 1 hour (10:35) | 3,959 | 49.2% | **-10.9** | 148.7 | 152.4 | 0.98 | 0.005 |
| | |  |  |  |  |  |  |  |
| Indecisive | 5 min (09:40) | 786 | 58.5% | **+9.4** | 74.4 | 66.5 | 1.12 | 0.009 |
| Indecisive | 10 min (09:45) | 797 | 58.3% | **+11.1** | 93.5 | 88.4 | 1.06 | 0.020 |
| Indecisive | 15 min (09:50) | 792 | 59.2% | **+15.1** | 103.6 | 97.2 | 1.07 | 0.001 |
| Indecisive | 1 hour (10:35) | 796 | 54.9% | **+16.2** | 152.8 | 135.4 | 1.13 | 0.018 |

## 2. Distribution, shape and tail risk

| Group | Window | Median | p10 | p90 | Skew | Kurtosis | Skew (wins.) | Kurt (wins.) | **% loss > 1.0 ATR** | **% gain > 1.5 ATR** |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 5 min (09:40) | +13.8 | -91 | +123 | -0.25 | +4.5 | -0.01 | +1.2 | **0.80%** | **0.14%** |
| Continuation | 10 min (09:45) | +18.6 | -108 | +157 | -0.06 | +3.7 | +0.07 | +1.4 | **1.37%** | **0.80%** |
| Continuation | 15 min (09:50) | +25.0 | -116 | +190 | +0.23 | +4.9 | +0.19 | +1.3 | **1.84%** | **1.49%** |
| Continuation | 1 hour (10:35) | +29.1 | -173 | +254 | +14.69 | +607.5 | +0.16 | +1.2 | **4.63%** | **3.52%** |
| | |  |  |  |  |  |  |  |  |  |
| Reversal | 5 min (09:40) | +0.9 | -116 | +110 | +0.19 | +4.1 | +0.01 | +1.2 | **1.35%** | **0.18%** |
| Reversal | 10 min (09:45) | -3.9 | -150 | +135 | +0.14 | +3.7 | +0.02 | +1.3 | **2.92%** | **0.51%** |
| Reversal | 15 min (09:50) | -5.6 | -179 | +154 | +0.06 | +2.8 | -0.11 | +1.2 | **4.17%** | **0.89%** |
| Reversal | 1 hour (10:35) | -2.9 | -237 | +229 | -0.08 | +3.2 | -0.15 | +1.3 | **8.23%** | **2.50%** |
| | |  |  |  |  |  |  |  |  |  |
| Indecisive | 5 min (09:40) | +12.2 | -94 | +135 | +0.07 | +4.1 | +0.27 | +1.1 | **0.64%** | **0.00%** |
| Indecisive | 10 min (09:45) | +15.6 | -115 | +161 | -0.19 | +3.7 | -0.19 | +2.1 | **1.63%** | **0.88%** |
| Indecisive | 15 min (09:50) | +21.2 | -126 | +184 | -0.48 | +4.0 | -0.12 | +1.4 | **1.89%** | **0.88%** |
| Indecisive | 1 hour (10:35) | +18.5 | -204 | +246 | +0.20 | +2.5 | +0.23 | +0.8 | **5.03%** | **3.14%** |

Winsorised (1%/99%) skew and kurtosis are carried because the raw pair is dominated by single observations at the 1-hour horizon — the CAR 2021-11-02 squeeze documented in `DIST_REPORT.md` sits in the Continuation group and drives its raw skew on its own.

## 3. Does removing dojis improve the Continuation edge?

This is the only section that can answer the question, because it compares the carved-out cohort against the same cohort with dojis folded back in (5,362 events — the 4,938 non-doji continuations plus the 424 dojis whose tiny body closed with the gap).

| Window | NET, non-doji | NET, incl. dojis | **Δ** | Win rate, non-doji | Win rate, incl. | Payoff, non-doji | Payoff, incl. |
|---|---:|---:|---:|---:|---:|---:|---:|
| 5 min (09:40) | **+7.8** | +7.7 | **+0.1** | 58.3% | 58.4% | 1.09 | 1.08 |
| 10 min (09:45) | **+14.8** | +14.0 | **+0.8** | 58.8% | 58.6% | 1.15 | 1.14 |
| 15 min (09:50) | **+23.7** | +22.5 | **+1.2** | 59.9% | 59.9% | 1.23 | 1.21 |
| 1 hour (10:35) | **+30.1** | +28.5 | **+1.6** | 58.4% | 58.1% | 1.21 | 1.19 |

**Yes, but marginally.** The carve-out helps at all 4 horizons, by +0.1 to +1.6 bps (mean +0.9).

For scale: the dojis being excluded are only 424 events against 4,938 kept, about 8% of the combined cohort, so even a large difference in their behaviour moves the blended figure only slightly. The honest summary is that the doji filter is **defensible but not load-bearing** — it is not what makes this setup work.

## 4. The three questions, answered

**Q1 — Does removing dojis improve the Continuation edge?**

**Yes, but marginally.** The carve-out helps at all 4 horizons, by +0.1 to +1.6 bps (mean +0.9). See section 3. The more important finding is that this filter was already applied in all prior work, so no earlier number in this series needs revising.

**Q2 — How does the Indecisive group perform?**

| Window | n | NET | net p | Win rate | Median | % loss > 1.0 ATR | % gain > 1.5 ATR |
|---|---:|---:|---:|---:|---:|---:|---:|
| 5 min (09:40) | 786 | **+9.4** | 0.009 | 58.5% | +12.2 | 0.64% | 0.00% |
| 10 min (09:45) | 797 | **+11.1** | 0.020 | 58.3% | +15.6 | 1.63% | 0.88% |
| 15 min (09:50) | 792 | **+15.1** | 0.001 | 59.2% | +21.2 | 1.89% | 0.88% |
| 1 hour (10:35) | 796 | **+16.2** | 0.018 | 54.9% | +18.5 | 5.03% | 3.14% |

**This is the surprise of the test: the Indecisive group makes money.** NET is positive at all 4 horizons (+9.4 to +16.2 bps) and significant at 4 of 4, on a sample of roughly 792. A doji is normally read as "no information", and on the direction of the candle that is exactly right — section 5 shows the candle-direction reading loses at every horizon. But the **gap** is still information, and following it works.

| Window | Indecisive NET | Continuation NET | Δ |
|---|---:|---:|---:|
| 5 min (09:40) | +9.4 | +7.8 | +1.5 |
| 10 min (09:45) | +11.1 | +14.8 | -3.7 |
| 15 min (09:50) | +15.1 | +23.7 | -8.6 |
| 1 hour (10:35) | +16.2 | +30.1 | -13.9 |

The relationship with Continuation is not constant: Indecisive is ahead at 5 minutes (+1.5 bps) and falls behind as the hold lengthens (-13.9 bps at 1 hour). A clear-bodied continuation candle buys you *persistence*; a doji gives you the gap drift and little more, which is worth most in the first few minutes and decays after that.

**On tail risk it tracks Continuation, not something milder.**

| Window | Loss > 1 ATR: Cont. | Rev. | **Doji** | Gain > 1.5 ATR: Cont. | Rev. | **Doji** |
|---|---:|---:|---:|---:|---:|---:|
| 5 min (09:40) | 0.80% | 1.35% | **0.64%** | 0.14% | 0.18% | **0.00%** |
| 10 min (09:45) | 1.37% | 2.92% | **1.63%** | 0.80% | 0.51% | **0.88%** |
| 15 min (09:50) | 1.84% | 4.17% | **1.89%** | 1.49% | 0.89% | **0.88%** |
| 1 hour (10:35) | 4.63% | 8.23% | **5.03%** | 3.52% | 2.50% | **3.14%** |

The doji group is well below Reversal at every horizon but essentially level with Continuation — 5.03% of trades lose more than 1 ATR at 1 hour, against 4.63% for Continuation and 8.23% for Reversal. **The intuition that a quiet opening candle implies a quiet hour is not supported.** A narrow *body* is not a narrow *range*, and this group's median gap is in fact the largest of the three (section 6). Indecision at 09:35 is not calm — it is a balanced fight inside a big gap, and it resolves like one.

**Q3 — Is the Reversal group still weak after removing dojis?**

| Window | n | NET | net p | Win rate | Payoff | Median |
|---|---:|---:|---:|---:|---:|---:|
| 5 min (09:40) | 3,913 | **-7.6** | 0.000 | 50.3% | 0.96 | +0.9 |
| 10 min (09:45) | 3,942 | **-10.1** | 0.000 | 48.3% | 0.99 | -3.9 |
| 15 min (09:50) | 3,954 | **-13.1** | 0.000 | 48.3% | 0.95 | -5.6 |
| 1 hour (10:35) | 3,959 | **-10.9** | 0.005 | 49.2% | 0.98 | -2.9 |

**Yes — still weak, and the doji carve-out does not rescue it.** NET is negative at all 4 horizons (-13.1 to -7.6 bps), significantly so at 4 of them, with payoff ratios below 1.0 (0.95–0.99) — losing trades are bigger than winning ones as well as more frequent. Removing the indecisive candles leaves the remaining counter-gap candles as clear-bodied genuine reversals, and following them still loses money.

## 5. Indecisive group — the direction choice

A doji has a body, however small, so it has a nominal direction. Trading that instead of the gap:

| Window | Gap direction NET | Candle direction NET | Gap win rate | Candle win rate |
|---|---:|---:|---:|---:|
| 5 min (09:40) | +9.4 | -8.7 | 58.5% | 50.9% |
| 10 min (09:45) | +11.1 | -12.3 | 58.3% | 48.6% |
| 15 min (09:50) | +15.1 | -12.1 | 59.2% | 50.4% |
| 1 hour (10:35) | +16.2 | -12.4 | 54.9% | 50.8% |

> **These two columns are not mirror images.** The candle direction agrees with the gap for the 424 dojis whose body closed with the gap and opposes it for the other 378, so the second column is a partial re-signing, not a global flip — the pair does not sum to a constant.

**Following the doji's own direction loses at every horizon** (-8.7, -12.3, -12.1, -12.4 bps), while following the gap wins at every horizon. That is the cleanest possible statement of what a doji is: the candle has no usable direction, but the gap it sits inside still does. Anyone tempted to read a doji's one-tick body as a signal is reading noise.

## 6. Composition of the three groups

| Group | n | Share | Median body/range | Zero-range | Median \|gap\| | Median Gap/ATR | Median vol ratio | % Gap Up |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 4,938 | 50.8% | 0.56 | 0 | 164 bps | 0.65 | 3.86 | 52.2% |
| Reversal | 3,980 | 40.9% | 0.56 | 0 | 164 bps | 0.63 | 3.49 | 51.5% |
| Indecisive | 802 | 8.3% | 0.05 | 0 | 211 bps | 0.76 | 3.73 | 51.5% |

## 7. Reading notes

- **The three groups partition the High Volume cohort**, so they are not independent tests — they are one sample cut three ways.
- **The doji threshold is a free parameter.** 0.10 is the classic convention, not an optimised value, and nothing here tests sensitivity to it. A materially different threshold would move events between all three groups at once.
- **Costs are flat 6.6 bps** and do not vary by group. The natural assumption that doji sessions are quiet, and therefore cheap to trade, does not survive section 6: that group carries the *largest* median gap of the three. A narrow body says the buyers and sellers finished level, not that few of them showed up, so there is no reason to expect its spreads to be tighter than the other groups'.
- **Zero-range candles** (high = low) would be counted as dojis, but there are 0 of them in this cohort — the no-print guard applied at entry has already removed every one, so the rule never binds here.
- **The Indecisive result is the one to re-test out of sample.** It rests on ~802 events, an eighth the size of the Continuation cohort, and it was not a hypothesis anyone held before the table was produced. Positive at four of four horizons is encouraging, not conclusive.

---

_Reproducible from `lambda_strategy_validation/doji.py`; tables in `lambda_data/tables/doji_*.csv`._