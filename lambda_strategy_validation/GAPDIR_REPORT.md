# Lambda — High Volume Signals by Gap Direction

Post-earnings (T+1) only. The four High Volume cells split by whether the gap was **up** or **down**, at 15 minutes and 1 hour.

| Input | Definition |
|---|---|
| Universe | Post-earnings T+1 sessions, 2015-01-27 → 2025-12-22 |
| Signal | Direction of the 09:30–09:35 candle relative to the gap |
| Continuation | first candle closes **with** the gap |
| Reversal | first candle closes **against** the gap |
| High Volume | `c1_volume` > 1.5× the trailing 20-session mean of `c1_volume` for the same ticker and the same 09:30–09:35 slot, shifted one session |
| Entry | Open of the 09:35 bar (minute 5) |
| Costs | 6.6 bps round trip, subtracted for NET |
| Inference | date-clustered bootstrap; ⚠ marks n < 150 |

Events after guards: **16,548**, of which **8,918** are High Volume Continuation or Reversal signals. Gap-up share: 52.6% of all events, 51.9% of the High Volume signals.

> **Sign convention.** Continuation is signed in the **gap** direction; Reversal is signed in the **candle** direction. Both are the same rule — *follow the first 5-minute candle* — so a positive number always means the rule paid. The Side column says which way the trade actually points, because that is what determines whether market drift helps or hurts.

## 1. The four groups

| Window | Group | Side | n | Win rate | **NET (bps)** | Avg Win | Avg Loss | Payoff | net p |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| 15 min (09:50) | HV + Continuation + Gap Up | long | 2,561 | 58.8% | **+19.8** | 108 | 90 | 1.20 | 0.000 |
| 15 min (09:50) | HV + Continuation + Gap Down | short | 2,343 | 61.1% | **+27.8** | 113 | 89 | 1.27 | 0.000 |
| 15 min (09:50) | HV + Reversal + Gap Up | short | 2,037 | 50.0% | **-9.7** | 100 | 106 | 0.94 | 0.002 |
| 15 min (09:50) | HV + Reversal + Gap Down | long | 1,917 | 46.5% | **-16.7** | 106 | 111 | 0.95 | 0.000 |
| 1 hour (10:35) | HV + Continuation + Gap Up | long | 2,567 | 57.1% | **+25.6** | 152 | 128 | 1.19 | 0.001 |
| 1 hour (10:35) | HV + Continuation + Gap Down | short | 2,341 | 59.7% | **+35.1** | 155 | 125 | 1.23 | 0.000 |
| 1 hour (10:35) | HV + Reversal + Gap Up | short | 2,036 | 51.2% | **-5.2** | 145 | 149 | 0.97 | 0.280 |
| 1 hour (10:35) | HV + Reversal + Gap Down | long | 1,923 | 47.1% | **-16.9** | 153 | 155 | 0.98 | 0.000 |

Avg Win and Avg Loss are in basis points, gross of costs; Payoff is their ratio. NET is the mean expectancy per trade after 6.6 bps.

## 2. Does gap direction matter?

**15 min (09:50)**

- Continuation: Gap Up **+19.8** (n=2,561, 58.8% win) vs Gap Down **+27.8** (n=2,343, 61.1% win) → Up − Down **-8.0 bps**
- Reversal: Gap Up **-9.7** (n=2,037, 50.0% win) vs Gap Down **-16.7** (n=1,917, 46.5% win) → Up − Down **+7.0 bps**

**1 hour (10:35)**

- Continuation: Gap Up **+25.6** (n=2,567, 57.1% win) vs Gap Down **+35.1** (n=2,341, 59.7% win) → Up − Down **-9.5 bps**
- Reversal: Gap Up **-5.2** (n=2,036, 51.2% win) vs Gap Down **-16.9** (n=1,923, 47.1% win) → Up − Down **+11.7 bps**

**Gap direction splits the two cohorts in opposite ways.** Continuation is better on gap **downs** (+8.0 to +9.5 bps in favour of down); Reversal is better on gap **ups** (+7.0 to +11.7 bps in favour of up). Read as "gap direction", that is a contradiction. Read another way, it is one statement.

### The short side wins in every cell

Within **each** cohort, the cell that points **short** beats the cell that points long — at both horizons, without exception:

| Window | Cohort | Short cell | Long cell | Short − Long |
|---|---|---:|---:|---:|
| 15 min (09:50) | Continuation | +27.8 | +19.8 | **+8.0** |
| 15 min (09:50) | Reversal | -9.7 | -16.7 | **+7.0** |
| 1 hour (10:35) | Continuation | +35.1 | +25.6 | **+9.5** |
| 1 hour (10:35) | Reversal | -5.2 | -16.9 | **+11.7** |

That is 4 of 4 comparisons, spanning +7.0 to +11.7 bps. The variable that orders these cells is not whether the stock gapped up or down — it is **which way the resulting trade points**. Falling prices on heavy post-earnings volume travel further in the first hour than rising ones do, which is the standard downside-moves-faster asymmetry showing up intraday.

Three things qualify that reading. Market drift does not explain it (section 4). The Normal/Low volume control shows the same asymmetry in weaker and less consistent form (section 6), so volume sharpens it rather than creating it. And shorting is not free (section 7) — that cost is not measurable from this data, and it lands on exactly the cells that look best.

## 3. “Fade the candle” — the Reversal groups traded the other way

The identical Reversal events, re-signed in the **gap** direction: the first candle went against the gap, and this version ignores it and stays with the gap.

| Window | Group | n | Win rate | **NET (bps)** | Avg Win | Avg Loss | Payoff | net p |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 15 min (09:50) | Fade Reversal + Gap Up (stay long the gap) | 2,037 | 50.0% | **-3.5** | 106 | 100 | 1.06 | 0.285 |
| 15 min (09:50) | Fade Reversal + Gap Down (stay short the gap) | 1,917 | 53.5% | **+3.5** | 111 | 106 | 1.05 | 0.314 |
| 1 hour (10:35) | Fade Reversal + Gap Up (stay long the gap) | 2,036 | 48.8% | **-8.0** | 149 | 145 | 1.03 | 0.086 |
| 1 hour (10:35) | Fade Reversal + Gap Down (stay short the gap) | 1,923 | 52.9% | **+3.7** | 155 | 153 | 1.02 | 0.480 |

> **Costs do not flip with the sign.** Gross flips exactly; net does not, because the 6.6 bps round trip is paid either way. Both directions of a small gross edge lose money — the pair of figures for one cell sums to −13.2 bps, not to zero. Only where gross is large does fading produce something tradeable.

- **15 min (09:50)**, Reversal + Gap Up: follow -9.7 vs fade -3.5 → **fade** is the better side (gross -3.1 / +3.1)
- **15 min (09:50)**, Reversal + Gap Down: follow -16.7 vs fade +3.5 → **fade** is the better side (gross -10.1 / +10.1)
- **1 hour (10:35)**, Reversal + Gap Up: follow -5.2 vs fade -8.0 → **follow** is the better side (gross +1.4 / -1.4)
- **1 hour (10:35)**, Reversal + Gap Down: follow -16.9 vs fade +3.7 → **fade** is the better side (gross -10.3 / +10.3)

**Fading is better than following in most cells, but it does not produce a tradeable edge.** The only positive net figures are the two Gap Down fades (staying short), and neither is distinguishable from zero — the best of them is +3.7 bps at p = 0.48. The Reversal signal on high volume is best read as *information that the signal is worthless*, not as a signal to be inverted: the gross moves are too small for either side to clear 6.6 bps.

## 4. How much of the up/down split is just market drift?

A gap-up Continuation trade is long; a gap-down Continuation trade is short. Any index drift over the holding window is therefore *added* to one group and *subtracted* from the other, which manufactures an up-versus-down difference out of nothing. Measured SPY drift over the same clock windows, on the same dates:

| Window | Cohort | n | Mean SPY (bps) | Median SPY (bps) |
|---|---|---:|---:|---:|
| 15 min (09:50) | Gap Up days | 8,128 | +0.17 | +0.22 |
| 15 min (09:50) | Gap Down days | 7,257 | -1.16 | -0.46 |
| 1 hour (10:35) | Gap Up days | 7,916 | +1.36 | +1.84 |
| 1 hour (10:35) | Gap Down days | 7,086 | -1.30 | +0.44 |

Subtracting that drift at beta 1 — *removing the market's move, not hedging the exposure* — gives:

| Window | Group | Side | NET | NET, drift-adjusted | Change |
|---|---|---|---:|---:|---:|
| 15 min (09:50) | HV + Continuation + Gap Up | long | +19.8 | **+19.7** | -0.1 |
| 15 min (09:50) | HV + Continuation + Gap Down | short | +27.8 | **+28.1** | +0.3 |
| 15 min (09:50) | HV + Reversal + Gap Up | short | -9.7 | **-10.2** | -0.5 |
| 15 min (09:50) | HV + Reversal + Gap Down | long | -16.7 | **-16.3** | +0.4 |
| 1 hour (10:35) | HV + Continuation + Gap Up | long | +25.6 | **+24.3** | -1.3 |
| 1 hour (10:35) | HV + Continuation + Gap Down | short | +35.1 | **+33.0** | -2.1 |
| 1 hour (10:35) | HV + Reversal + Gap Up | short | -5.2 | **-6.5** | -1.3 |
| 1 hour (10:35) | HV + Reversal + Gap Down | long | -16.9 | **-15.7** | +1.2 |

Continuation, Gap Up minus Gap Down, before and after the adjustment:

- **15 min (09:50)**: -8.0 bps raw → **-8.4 bps** adjusted (105% of the raw difference survives)
- **1 hour (10:35)**: -9.5 bps raw → **-8.7 bps** adjusted (91% of the raw difference survives)

**Drift is not the explanation.** SPY moves barely more than a basis point over either window, so removing it changes every figure by less than 2 bps and leaves the up-versus-down gap essentially intact. The short-side advantage in section 2 is a property of the individual names, not a free ride on a falling index — and note that the drift on gap-down days is *negative*, which if anything means the short cells were helped by the market and still keep their lead once that help is stripped out.

## 5. Are the up and down cohorts comparable?

| Group | n | Median \|gap\| (bps) | Median Gap/ATR | Median vol ratio | Median price |
|---|---:|---:|---:|---:|---:|
| HV + Continuation + Gap Up | 2,580 | 156 | 0.63 | 3.73 | $75 |
| HV + Continuation + Gap Down | 2,358 | 171 | 0.67 | 4.02 | $73 |
| HV + Reversal + Gap Up | 2,049 | 165 | 0.63 | 3.41 | $78 |
| HV + Reversal + Gap Down | 1,931 | 163 | 0.64 | 3.54 | $74 |

Gap-up share of High Volume signals by year — a check that the split is not concentrated in one regime:

| Year | Continuation n | % Gap Up | Reversal n | % Gap Up |
|---|---:|---:|---:|---:|
| 2015 | 380 | 57.4% | 259 | 50.6% |
| 2016 | 345 | 51.9% | 320 | 43.1% |
| 2017 | 448 | 58.7% | 383 | 48.8% |
| 2018 | 486 | 53.7% | 411 | 51.3% |
| 2019 | 475 | 49.9% | 383 | 51.7% |
| 2020 | 484 | 49.0% | 308 | 55.2% |
| 2021 | 519 | 50.7% | 316 | 55.4% |
| 2022 | 326 | 52.8% | 306 | 51.6% |
| 2023 | 519 | 51.8% | 431 | 48.3% |
| 2024 | 457 | 51.9% | 459 | 55.3% |
| 2025 | 499 | 48.9% | 404 | 54.2% |

## 6. Control — the same four cells on Normal/Low volume

High Volume only means something against the alternative. These are the same four cells for events that did **not** clear the 1.5× threshold.

| Window | Group | n | Win rate | **NET (bps)** | Avg Win | Avg Loss | Payoff | net p |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 15 min (09:50) | LV + Continuation + Gap Up | 1,237 | 54.5% | **+7.6** | 68 | 50 | 1.35 | 0.002 |
| 15 min (09:50) | LV + Continuation + Gap Down | 1,091 | 58.8% | **+7.9** | 67 | 60 | 1.12 | 0.005 |
| 15 min (09:50) | LV + Reversal + Gap Up | 2,038 | 58.3% | **+7.0** | 68 | 62 | 1.09 | 0.002 |
| 15 min (09:50) | LV + Reversal + Gap Down | 1,749 | 54.4% | **+4.6** | 73 | 62 | 1.17 | 0.097 |
| 1 hour (10:35) | LV + Continuation + Gap Up | 1,246 | 53.5% | **+8.9** | 106 | 88 | 1.20 | 0.030 |
| 1 hour (10:35) | LV + Continuation + Gap Down | 1,100 | 55.8% | **+7.0** | 98 | 93 | 1.05 | 0.125 |
| 1 hour (10:35) | LV + Reversal + Gap Up | 2,033 | 55.8% | **+11.1** | 105 | 93 | 1.13 | 0.000 |
| 1 hour (10:35) | LV + Reversal + Gap Down | 1,752 | 52.2% | **+1.0** | 104 | 98 | 1.06 | 0.802 |

The short-side advantage is **weaker and less consistent** without the volume condition: the short cell beats the long cell in 3 of 4 comparisons rather than 4 of 4, and averages **+2.7 bps** against **+9.1 bps** on High Volume. It is not, however, absent — the 1-hour Reversal comparison (+10.0 bps) is as large as anything in the High Volume set. So volume sharpens the asymmetry; it does not create it, and the case for the asymmetry being about *side* rather than about *volume* is correspondingly weaker than section 2 alone suggests.

The more clear-cut contrast is the Reversal cohort itself: Normal/Low Reversal is **profitable** at both horizons where High Volume Reversal loses at both. That reproduces the earlier finding — heavy opening volume confirms the with-gap move and penalises the attempt to fade it — and it holds in both gap directions.

## 7. What this does and does not establish

- The four cells are read *after* the fact from one sample, and splitting an already-conditioned cohort in two halves the sample in each. Cells marked ⚠ are below 150 events and should be treated as directionally suggestive at most.
- The gap-down cells are **short** trades. The flat 6.6 bps cost carries no borrow fee, no locate failure and no uptick-rule friction, all of which fall on exactly those cells. Their true net is worse than shown by an amount this test cannot measure.
- The drift adjustment in section 4 is beta 1 on SPY. Post-earnings names on heavy volume are higher-beta than the index, so it under-corrects; the residual up-versus-down difference is an upper bound on the genuine signal asymmetry, not a point estimate.
- The universe is survivorship-affected in the usual direction: names that delisted mid-sample are absent, which flatters long cells relative to short ones.

---

_Reproducible from `lambda_strategy_validation/gapdir.py`; tables in `lambda_data/tables/gapdir_*.csv`._