# Lambda Follow-Up Report

**Three questions: shorter holding periods, opening-candle patterns, and a tradeable market-agreement filter.**

Sample: all 17,582 earnings T+1 sessions, 615 US large caps, 2015-2025, with 1-minute bars from 09:30 to 11:00. All inference uses the date-clustered bootstrap; every trade is charged its own measured trailing Roll spread plus 2 bps impact, on both legs.

## 1. Does a shorter holding period help?

**Verdict: no — every entry x exit cell is negative net of costs.**

A shorter hold pays the same round-trip cost over a smaller slice of an already-small drift, so it is worse than holding to the close, not better. The specific horizon asked about, 09:45 -> 10:00, is -6.61 bps at p < 0.001.

| entry_time   | exit   |     n |   n_dates |   net_bps |   ci_lo_bps |   ci_hi_bps |    p |   hit_rate |
|:-------------|:-------|------:|----------:|----------:|------------:|------------:|-----:|-----------:|
| 09:35        | +15min | 17582 |      1941 |     -3.58 |       -5.57 |       -1.53 | 0    |       0.51 |
| 09:35        | +30min | 17582 |      1941 |     -3.36 |       -5.64 |       -0.89 | 0.01 |       0.51 |
| 09:35        | +60min | 17582 |      1941 |     -3.01 |       -5.99 |        0.26 | 0.06 |       0.51 |
| 09:35        | close  | 17582 |      1941 |     -2.63 |       -6.79 |        1.89 | 0.25 |       0.5  |
| 09:45        | +15min | 17582 |      1941 |     -6.61 |       -8.13 |       -5.02 | 0    |       0.5  |
| 09:45        | +30min | 17582 |      1941 |     -5.94 |       -8.12 |       -3.67 | 0    |       0.5  |
| 09:45        | +60min | 17582 |      1941 |     -5.19 |       -7.93 |       -2.24 | 0    |       0.5  |
| 09:45        | close  | 17582 |      1941 |     -5.37 |       -9.28 |       -1.32 | 0.01 |       0.5  |
| 10:00        | +15min | 17582 |      1941 |     -6.33 |       -7.68 |       -4.99 | 0    |       0.5  |
| 10:00        | +30min | 17582 |      1941 |     -6.04 |       -7.78 |       -4.29 | 0    |       0.5  |
| 10:00        | close  | 17582 |      1941 |     -5.79 |       -9.38 |       -2.25 | 0    |       0.5  |

## 2. What do the opening candle patterns look like?

**Verdict: real discriminating power, but the pattern is a dependable veto and an unreliable trigger.**

Each archetype below is the median of its three 5-minute candles, expressed in basis points from the session open and **oriented by gap direction** — a gap-down continuation and a gap-up continuation are flipped onto the same axis, so positive always means 'moving with the gap'.

Archetypal candle shapes (bps from session open, gap-oriented):

| pattern                | candle     |   open |   high |   low |   close |
|:-----------------------|:-----------|-------:|-------:|------:|--------:|
| Strong Continuation+   | c1 (09:30) |    0   |   93.9 | -22   |    67.7 |
| Strong Continuation+   | c2 (09:35) |   69   |  150.5 |  52.5 |   131   |
| Strong Continuation+   | c3 (09:40) |  132.3 |  200   | 116.5 |   181.2 |
| Moderate Continuation+ | c1 (09:30) |    0   |  109.4 | -23.1 |    72   |
| Moderate Continuation+ | c2 (09:35) |   71.3 |  136.8 |  45.2 |   105.9 |
| Moderate Continuation+ | c3 (09:40) |  105.8 |  154.3 |  80.1 |   126.8 |
| Indecision0            | c1 (09:30) |    0   |   46.3 | -53.2 |     8.1 |
| Indecision0            | c2 (09:35) |    8.7 |   43.7 | -31.6 |     3.7 |
| Indecision0            | c3 (09:40) |    4.9 |   48   | -14.7 |    21.3 |
| Early Reversal-        | c1 (09:30) |    0   |   22.6 | -67.3 |   -32.8 |
| Early Reversal-        | c2 (09:35) |  -31.2 |   -4.2 | -78.1 |   -47.5 |
| Early Reversal-        | c3 (09:40) |  -46.8 |  -22.6 | -87.2 |   -60.7 |

Frequency and context:

| pattern                |    n |   share |   median_abs_gap_bps |   full_session_continuation |
|:-----------------------|-----:|--------:|---------------------:|----------------------------:|
| Strong Continuation+   | 1496 |   0.091 |               85.54  |                       0.846 |
| Moderate Continuation+ | 2653 |   0.161 |               96.075 |                       0.77  |
| Indecision0            | 3856 |   0.234 |               92.04  |                       0.561 |
| Early Reversal-        | 8468 |   0.514 |               86.091 |                       0.366 |

Note: `full_session_continuation` is measured open-to-close and therefore *includes* the 09:30-09:45 window the pattern is built from. It is shown for context only. The tradeable numbers are the forward returns below, which start at 09:45 when the pattern completes.

Forward performance by pattern, entering at 09:45:

| exit   | pattern                |     n |   n_dates |   net_bps |   ci_lo_bps |   ci_hi_bps |    p |   hit_rate |
|:-------|:-----------------------|------:|----------:|----------:|------------:|------------:|-----:|-----------:|
| +15min | Strong Continuation+   |  1496 |       791 |     -3.18 |       -8.74 |        2.41 | 0.27 |       0.52 |
| +15min | Moderate Continuation+ |  2653 |      1067 |      0.48 |       -3.18 |        4.04 | 0.8  |       0.54 |
| +15min | Indecision0            |  3856 |      1266 |     -2.54 |       -5.39 |        0.29 | 0.08 |       0.52 |
| +15min | Early Reversal-        |  8468 |      1653 |     -6.66 |       -8.65 |       -4.49 | 0    |       0.5  |
| +15min | + patterns             |  4149 |      1287 |     -0.84 |       -3.78 |        2.24 | 0.6  |       0.53 |
| +15min | everything else        | 13433 |      1848 |     -8.39 |      -10.05 |       -6.58 | 0    |       0.49 |
| +30min | Strong Continuation+   |  1496 |       791 |      1.78 |       -8.57 |       15.59 | 0.8  |       0.51 |
| +30min | Moderate Continuation+ |  2653 |      1067 |      0.7  |       -4.41 |        5.25 | 0.78 |       0.53 |
| +30min | Indecision0            |  3856 |      1266 |     -0.62 |       -4.58 |        3.18 | 0.75 |       0.52 |
| +30min | Early Reversal-        |  8468 |      1653 |     -6.81 |       -9.34 |       -4.11 | 0    |       0.5  |
| +30min | + patterns             |  4149 |      1287 |      1.09 |       -3.6  |        7.07 | 0.7  |       0.52 |
| +30min | everything else        | 13433 |      1848 |     -8.12 |      -10.5  |       -5.75 | 0    |       0.49 |
| +60min | Strong Continuation+   |  1496 |       791 |      7.53 |       -6.1  |       25.38 | 0.36 |       0.52 |
| +60min | Moderate Continuation+ |  2653 |      1067 |     -0.61 |       -6.52 |        5.07 | 0.83 |       0.51 |
| +60min | Indecision0            |  3856 |      1266 |     -0.06 |       -5.13 |        5.02 | 0.98 |       0.53 |
| +60min | Early Reversal-        |  8468 |      1653 |     -6.25 |       -9.67 |       -2.73 | 0    |       0.5  |
| +60min | + patterns             |  4149 |      1287 |      2.33 |       -3.88 |       10.11 | 0.51 |       0.51 |
| +60min | everything else        | 13433 |      1848 |     -7.52 |      -10.62 |       -4.54 | 0    |       0.5  |
| close  | Strong Continuation+   |  1496 |       791 |     12.38 |       -3.71 |       31.05 | 0.15 |       0.51 |
| close  | Moderate Continuation+ |  2653 |      1067 |      0.66 |       -8.26 |       10.34 | 0.89 |       0.5  |
| close  | Indecision0            |  3856 |      1266 |     -1.78 |       -9.07 |        5.53 | 0.64 |       0.51 |
| close  | Early Reversal-        |  8468 |      1653 |     -6.36 |      -11.94 |       -0.72 | 0.02 |       0.5  |
| close  | + patterns             |  4149 |      1287 |      4.89 |       -3.14 |       13.45 | 0.25 |       0.5  |
| close  | everything else        | 13433 |      1848 |     -8.54 |      -13.07 |       -3.85 | 0    |       0.49 |

Only the negative side is significant. **Early Reversal-** is reliably bad at every horizon (-6.25 to -6.81 bps, p < 0.001 throughout). **Strong Continuation+** improves the longer it is held (-3.18 bps at 15 minutes rising to +12.38 bps at the close) but never reaches significance (best p = 0.15, n = 1,496).

## 3. Market agreement — and a correction

**Correction: Sigma's section-2C relative-beta filter is not tradeable, and the earlier result that it improved the edge (51.5% continuation, p = 0.008) is withdrawn.**

The filter compares the stock's T+1 *open-to-close* return with SPY's and the sector's. That return is only known at 16:00, and 'continuation' is itself defined by the sign of that same return — so the filter conditions on the outcome it is being scored against. Splitting by whether SPY happened to agree with the gap that day shows how mechanical it is:

| SPY agreed with gap? | Kept by filter | Excluded by filter |
|---|---|---|
| Yes | 80.7% continuation (n=6,421) | 0.6% continuation (n=2,321) |
| No | 22.0% continuation (n=6,372) | 98.0% continuation (n=2,226) |

A filter that sorts outcomes into 0.6% and 98.0% buckets is reading the answer, not detecting a signal. The mild overall 'improvement' is only what survives after those two opposing effects nearly cancel.

The tradeable rebuild uses only SPY's move from the open to the 09:45 entry — information actually on the screen at trade time — in both a raw and a beta-adjusted form:

| exit   | cohort                                       |     n |   n_dates |   net_bps |   ci_lo_bps |   ci_hi_bps |    p |   hit_rate |
|:-------|:---------------------------------------------|------:|----------:|----------:|------------:|------------:|-----:|-----------:|
| +15min | no filter                                    | 17582 |      1941 |     -6.61 |       -8.13 |       -5.02 | 0    |       0.5  |
| +15min | TRADEABLE: gap agrees with SPY move to 09:45 |  8619 |      1596 |     -6.66 |       -9.33 |       -4.08 | 0    |       0.49 |
| +15min | TRADEABLE: gap agrees with beta x SPY        |  8605 |      1599 |     -6.64 |       -9.34 |       -4.03 | 0    |       0.49 |
| +15min | TRADEABLE: gap disagrees with SPY (control)  |  8963 |      1632 |     -6.57 |       -9.34 |       -3.94 | 0    |       0.51 |
| +15min | SIGMA 2C (look-ahead, uses 16:00 return)     | 12792 |      1799 |     -5.77 |       -7.63 |       -4.05 | 0    |       0.51 |
| +30min | no filter                                    | 17582 |      1941 |     -5.94 |       -8.12 |       -3.67 | 0    |       0.5  |
| +30min | TRADEABLE: gap agrees with SPY move to 09:45 |  8619 |      1596 |     -5.4  |       -9.31 |       -1.59 | 0.01 |       0.5  |
| +30min | TRADEABLE: gap agrees with beta x SPY        |  8605 |      1599 |     -5.5  |       -9.36 |       -1.7  | 0.01 |       0.5  |
| +30min | TRADEABLE: gap disagrees with SPY (control)  |  8963 |      1632 |     -6.47 |      -10.04 |       -2.87 | 0    |       0.5  |
| +30min | SIGMA 2C (look-ahead, uses 16:00 return)     | 12792 |      1799 |     -4.72 |       -7.41 |       -1.97 | 0    |       0.51 |
| +60min | no filter                                    | 17582 |      1941 |     -5.19 |       -7.93 |       -2.24 | 0    |       0.5  |
| +60min | TRADEABLE: gap agrees with SPY move to 09:45 |  8619 |      1596 |     -4.34 |       -9.25 |        1.14 | 0.1  |       0.5  |
| +60min | TRADEABLE: gap agrees with beta x SPY        |  8605 |      1599 |     -4.54 |       -9.54 |        0.56 | 0.08 |       0.5  |
| +60min | TRADEABLE: gap disagrees with SPY (control)  |  8963 |      1632 |     -6.02 |      -10.62 |       -1.4  | 0.01 |       0.5  |
| +60min | SIGMA 2C (look-ahead, uses 16:00 return)     | 12792 |      1799 |     -3.49 |       -6.96 |       -0.1  | 0.05 |       0.51 |
| close  | no filter                                    | 17582 |      1941 |     -5.37 |       -9.28 |       -1.32 | 0.01 |       0.5  |
| close  | TRADEABLE: gap agrees with SPY move to 09:45 |  8619 |      1596 |     -2.48 |      -10.06 |        5.13 | 0.52 |       0.51 |
| close  | TRADEABLE: gap agrees with beta x SPY        |  8605 |      1599 |     -2.6  |       -9.91 |        4.88 | 0.51 |       0.51 |
| close  | TRADEABLE: gap disagrees with SPY (control)  |  8963 |      1632 |     -8.15 |      -15.53 |       -0.51 | 0.03 |       0.49 |
| close  | SIGMA 2C (look-ahead, uses 16:00 return)     | 12792 |      1799 |     -2.14 |       -7.4  |        2.75 | 0.4  |       0.5  |

**Answer: the instinct is directionally right but not economically useful.** At a 15-minute hold, agreeing with SPY (-6.66 bps) and fighting it (-6.57 bps) are indistinguishable. Held to the close a genuine gap appears — agreeing -2.48 bps versus fighting -8.15 bps — so 'don't fight the tape' is mildly real over a full session. But the agreeing cohort's confidence interval still spans zero (p = 0.52): it reduces the loss, it does not create a profit. Beta-adjusting SPY's move changes nothing (-2.60 vs -2.48).

## Bottom line

None of the three refinements rescues the edge. Shorter horizons are worse; the candle pattern is only trustworthy as an avoid signal; and the market filter that appeared to help was measuring the outcome. The REJECT verdict in the main report stands.

---

_Reproducible from `lambda_strategy_validation/horizons.py`, `candle_shapes.py` and the CSVs in `lambda_data/tables/`._