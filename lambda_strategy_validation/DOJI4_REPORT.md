# Lambda — Four-Way Candle Classification: Does a Small Body Still Tell You Which Way to Trade?

Post-earnings T+1, High Volume. The doji group split by which way its small body pointed, rather than pooled.

| Group | Definition | n |
|---|---|---:|
| 1. Small + Continuation | body/range ≤ 0.10, closes **with** the gap | 424 |
| 2. Small + Reversal | body/range ≤ 0.10, closes **against** the gap | 378 |
| 3. Continuation | body/range > 0.10, closes **with** the gap | 4,938 |
| 4. Reversal | body/range > 0.10, closes **against** the gap | 3,980 |

Entry at the open of the 09:35 bar; 6.6 bps round trip in NET; date-clustered bootstrap; ⚠ marks n < 150.

> **How to read the two direction columns.** For groups 1 and 3 the candle points the same way as the gap, so there is only one trade to make. For groups 2 and 4 they point opposite ways, and both are shown. The pair does **not** sum to zero: gross flips exactly but the 6.6 bps is paid either way, so the two NET figures for one cell sum to −13.2 bps. Both sides of a small gross edge lose.

## 1. All four groups, both directions

| Group | Window | n | Follow the **gap** | Follow the **candle** | Better side |
|---|---|---:|---:|---:|---|
| 1. Small + Continuation | 5 min (09:40) | 414 | **+6.6** | — (same trade) | gap |
| 1. Small + Continuation | 10 min (09:45) | 423 | **+4.7** | — (same trade) | gap |
| 1. Small + Continuation | 15 min (09:50) | 418 | **+8.7** | — (same trade) | gap |
| 1. Small + Continuation | 1 hour (10:35) | 419 | **+9.6** | — (same trade) | gap |
| | | | | | |
| 2. Small + Reversal | 5 min (09:40) | 372 | +12.5 | -25.7 | **gap** |
| 2. Small + Reversal | 10 min (09:45) | 374 | +18.3 | -31.5 | **gap** |
| 2. Small + Reversal | 15 min (09:50) | 374 | +22.2 | -35.4 | **gap** |
| 2. Small + Reversal | 1 hour (10:35) | 377 | +23.6 | -36.8 | **gap** |
| | | | | | |
| 3. Continuation | 5 min (09:40) | 4,870 | **+7.8** | — (same trade) | gap |
| 3. Continuation | 10 min (09:45) | 4,900 | **+14.8** | — (same trade) | gap |
| 3. Continuation | 15 min (09:50) | 4,904 | **+23.7** | — (same trade) | gap |
| 3. Continuation | 1 hour (10:35) | 4,908 | **+30.1** | — (same trade) | gap |
| | | | | | |
| 4. Reversal | 5 min (09:40) | 3,913 | -5.6 | -7.6 | **gap** |
| 4. Reversal | 10 min (09:45) | 3,942 | -3.1 | -10.1 | **gap** |
| 4. Reversal | 15 min (09:50) | 3,954 | -0.1 | -13.1 | **gap** |
| 4. Reversal | 1 hour (10:35) | 3,959 | -2.3 | -10.9 | **gap** |
| | | | | | |

NET in bps after costs.

## 2. Your question: small body, closed against the gap

| Window | n | Follow the gap | p | Follow the candle | p | Gap win rate | Candle win rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| 5 min (09:40) | 372 | **+12.5** | 0.021 | -25.7 | 0.000 | 58.1% | 41.9% |
| 10 min (09:45) | 374 | **+18.3** | 0.004 | -31.5 | 0.000 | 60.4% | 39.6% |
| 15 min (09:50) | 374 | **+22.2** | 0.002 | -35.4 | 0.000 | 59.4% | 40.6% |
| 1 hour (10:35) | 377 | **+23.6** | 0.027 | -36.8 | 0.002 | 54.4% | 45.6% |

**No — do not follow the candle.** Following the gap beats following the candle at all 4 horizons, and the follow-the-candle column is negative at every one (-36.8 to -25.7 bps). A small body pointing against the gap is not a reversal signal — it is a candle that failed to go anywhere, and the gap is still the only thing on the chart carrying information.

Following the **gap** in this cell is positive at 4 of 4 horizons and significant at 4 (5 min +12.5, 10 min +18.3, 15 min +22.2, 1 hour +23.6). On a sample of 372 that is suggestive rather than settled, but it points the same way as every other result in this series.

### Splitting the doji group was worth doing

The pooled Indecisive figure in `DOJI_REPORT.md` (+9.4 to +16.2 bps) turns out to be an average over two unlike halves:

| Window | Small + **with** gap | p | Small + **against** gap | p |
|---|---:|---:|---:|---:|
| 5 min (09:40) | +6.6 | 0.168 | **+12.5** | 0.021 |
| 10 min (09:45) | +4.7 | 0.451 | **+18.3** | 0.004 |
| 15 min (09:50) | +8.7 | 0.211 | **+22.2** | 0.002 |
| 1 hour (10:35) | +9.6 | 0.343 | **+23.6** | 0.027 |

**Nearly all of the doji edge comes from the half that closed against the gap.** Those cells are significant at 4 of 4 horizons; the half that closed *with* the gap is significant at 0 and its point estimates are roughly half the size. That is the opposite of the intuitive ordering — a candle that leaned the *wrong* way is the better setup, provided you trade the gap rather than the candle.

The reading that fits: a counter-gap candle that could not produce a real body is a **failed reversal**. Sellers into a gap up (or buyers into a gap down) showed up, got absorbed, and closed the candle nearly flat. That is evidence the gap direction is holding against pressure — stronger evidence than a small candle that merely drifted the same way the gap already pointed. It also matches the failed-reversal result in `VOLUME_REVERSAL_REPORT.md`, reached there by a completely different cut of the data.

### Compared with a full-bodied reversal (group 4)

| Window | Small+Rev: follow candle | Full Rev: follow candle | Small+Rev: follow gap | Full Rev: follow gap |
|---|---:|---:|---:|---:|
| 5 min (09:40) | -25.7 | -7.6 | +12.5 | -5.6 |
| 10 min (09:45) | -31.5 | -10.1 | +18.3 | -3.1 |
| 15 min (09:50) | -35.4 | -13.1 | +22.2 | -0.1 |
| 1 hour (10:35) | -36.8 | -10.9 | +23.6 | -2.3 |

**Following the candle loses in both reversal groups**, small body or full body (-13.1 to -7.6 bps for the full-bodied one). So the answer does not depend on body size at all: a counter-gap candle is not worth following whether it is a hesitant one or an emphatic one. Section 3 tests that across the whole body-size range rather than at one cut.

## 3. Body-size ladder — does a *bigger* counter-gap body ever justify following it?

Every event whose first candle closed against the gap, bucketed by body/range. 0.10 is an arbitrary line, so this checks the whole range.

| Window | Body/range | n | Follow the candle | p | Follow the gap | p |
|---|---|---:|---:|---:|---:|---:|
| 5 min (09:40) | ≤ 0.10 (doji) | 372 | -25.7 | 0.000 | **+12.5** | 0.021 |
| 5 min (09:40) | 0.10 – 0.25 | 604 | -15.5 | 0.001 | **+2.3** | 0.552 |
| 5 min (09:40) | 0.25 – 0.50 | 1,064 | -15.6 | 0.000 | **+2.4** | 0.421 |
| 5 min (09:40) | 0.50 – 0.75 | 1,201 | -4.5 | 0.170 | **-8.7** | 0.008 |
| 5 min (09:40) | > 0.75 | 1,044 | +1.4 | 0.634 | **-14.6** | 0.000 |
| | | | | | | |
| 10 min (09:45) | ≤ 0.10 (doji) | 374 | -31.5 | 0.000 | **+18.3** | 0.004 |
| 10 min (09:45) | 0.10 – 0.25 | 612 | -15.6 | 0.003 | **+2.4** | 0.611 |
| 10 min (09:45) | 0.25 – 0.50 | 1,067 | -21.8 | 0.000 | **+8.6** | 0.029 |
| 10 min (09:45) | 0.50 – 0.75 | 1,208 | -5.3 | 0.169 | **-7.9** | 0.048 |
| 10 min (09:45) | > 0.75 | 1,055 | -0.8 | 0.830 | **-12.4** | 0.002 |
| | | | | | | |
| 15 min (09:50) | ≤ 0.10 (doji) | 374 | -35.4 | 0.000 | **+22.2** | 0.002 |
| 15 min (09:50) | 0.10 – 0.25 | 615 | -22.7 | 0.000 | **+9.5** | 0.085 |
| 15 min (09:50) | 0.25 – 0.50 | 1,066 | -26.2 | 0.000 | **+13.0** | 0.004 |
| 15 min (09:50) | 0.50 – 0.75 | 1,213 | -8.2 | 0.077 | **-5.0** | 0.262 |
| 15 min (09:50) | > 0.75 | 1,060 | -0.1 | 0.991 | **-13.1** | 0.005 |
| | | | | | | |
| 1 hour (10:35) | ≤ 0.10 (doji) | 377 | -36.8 | 0.002 | **+23.6** | 0.027 |
| 1 hour (10:35) | 0.10 – 0.25 | 613 | -20.1 | 0.014 | **+6.9** | 0.377 |
| 1 hour (10:35) | 0.25 – 0.50 | 1,071 | -29.9 | 0.000 | **+16.7** | 0.009 |
| 1 hour (10:35) | 0.50 – 0.75 | 1,213 | -6.7 | 0.312 | **-6.5** | 0.321 |
| 1 hour (10:35) | > 0.75 | 1,062 | +8.7 | 0.174 | **-21.9** | 0.002 |
| | | | | | | |

Across all 20 bucket × horizon cells, **not one** shows a significantly positive return from following the counter-gap candle. There is no body size at which the counter-gap candle becomes worth following.

Averaging each bucket across the four horizons shows the gradient plainly:

| Body/range | Follow the candle | Follow the gap |
|---|---:|---:|
| ≤ 0.10 (doji) | -32.3 | +19.1 |
| 0.10 – 0.25 | -18.5 | +5.3 |
| 0.25 – 0.50 | -23.4 | +10.2 |
| 0.50 – 0.75 | -6.1 | -7.1 |
| > 0.75 | +2.3 | -15.5 |

**The two columns move in opposite directions as the body grows.** Following the candle improves broadly, though not monotonically — the 0.25–0.50 bucket breaks the sequence (-32.3 → +2.3 bps) while following the gap decays over the same range (+19.1 → -15.5 bps), and they cross around the 0.50 bucket. So body size *does* carry information — it just never carries enough to make following the candle profitable. What it really measures is how much to trust the gap: the smaller the counter-gap body, the more the gap is worth backing, and the bigger it is, the more you should simply stand aside.

## 4. The rule this implies

| First candle | Trade | Evidence |
|---|---|---|
| Full body, **with** the gap | With the gap | +7.8 to +30.1 bps, significant at 4/4, n = 4,870 |
| Small body, **against** the gap | With the gap — ignore the body | +12.5 to +23.6 bps, significant at 4/4, n = 372 |
| Small body, **with** the gap | With the gap, but weakly evidenced | +6.6 to +9.6 bps, significant at 0/4, n = 414 |
| Full body, **against** the gap | Stand aside | both directions lose or are indistinguishable from zero |

The last row is **stand aside**, not *fade the candle*. Following the gap after a full-bodied counter-gap candle is negative at all 4 horizons (-5.6 to -0.1 bps) though mostly indistinguishable from zero (3 of 4 with p ≥ 0.05), while following the candle loses significantly. Losing on one side is not the same as winning on the other: the 6.6 bps is paid whichever way you point, so both directions of a near-zero gross edge lose. There is no trade here.

## 5. Composition

| Group | n | Share | Median body/range | Median \|gap\| | Median Gap/ATR | Median vol ratio | % Gap Up |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1. Small + Continuation | 424 | 4.4% | 0.05 | 205 bps | 0.76 | 3.63 | 45.8% |
| 2. Small + Reversal | 378 | 3.9% | 0.05 | 218 bps | 0.76 | 3.74 | 57.9% |
| 3. Continuation | 4,938 | 50.8% | 0.56 | 164 bps | 0.65 | 3.86 | 52.2% |
| 4. Reversal | 3,980 | 40.9% | 0.56 | 164 bps | 0.63 | 3.49 | 51.5% |

## 6. Caveats

- **Group 2 is small** — 378 events, against 4,938 in the main Continuation cell. It clears the 150-event floor used throughout this series but it is the thinnest cell in any report so far, and it deserves an out-of-sample check before anything is built on it.
- **The four groups partition one sample**, so they are not independent tests.
- **The two small-body groups differ in gap-direction mix** (46% gap-up in group 1 against 58% in group 2), which matters because `GAPDIR_REPORT.md` found gap-down cells outperform gap-up ones. Group 2 is the more **gap-up**-weighted of the two, so that mix works *against* its result rather than explaining it — the finding survives the confound rather than resting on it.
- **0.10 is a convention, not an optimum.** The ladder in section 3 is the answer to that objection: the conclusion holds across every body size, so it does not depend on where the line is drawn.

---

_Reproducible from `lambda_strategy_validation/doji4.py`; tables in `lambda_data/tables/doji4_*.csv`._