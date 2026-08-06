# Lambda Deep Tests — Distribution, Stops, VIX and ATR

Focused on the 5- and 10-minute windows, with 09:45→10:00 for reference.

## Rules and inputs

| Input | Source and timing |
|---|---|
| Pattern | Three candles 09:30–09:45 only |
| Entry | `m14`, close of the 09:44 bar = price at 09:45:00 = `c3_close` |
| SPY direction | SPY Open → 09:45 only |
| Stage | Prior session |
| **VIX** | **Prior trading day's CBOE close** (official CBOE daily history), so it is fully known before the open |
| **ATR(14)** | **Prior session's value**, excluding the event day entirely |

Sample: **17,433** events. VIX matched on 100.0%, Gap/ATR computable on 100.0%. Median round-trip cost **6.6 bps**. Cells with n < 150 are flagged.

**Stop mechanics.** Stops are checked against the actual 1-minute path, not the endpoint: for a long the stop triggers if any minute LOW from 09:46 on breaches entry × (1 − stop); for a short if any minute HIGH breaches entry × (1 + stop). A stopped trade is booked at exactly −stop bps.

> That fill assumption is **optimistic**. A real stop on a volatile post-earnings name can slip through its level, and 1-minute bars cannot see the sequence of ticks inside a minute. Read the stop results as an upper bound on how much a stop can help.

## Part 1 — Return distribution

All figures in basis points from the 09:45 entry, signed in the gap direction (so positive = continuation).

### 09:45 -> 09:50

| Cohort                       |     n |   Mean |   Median |   P10 |   P25 |   P75 |   P90 | >+100   | <−100   | >+200   | <−200   |   Skew |
|:-----------------------------|------:|-------:|---------:|------:|------:|------:|------:|:--------|:--------|:--------|:--------|-------:|
| All events                   | 17433 |    1.9 |      1.2 | -63.9 | -27.9 |  30.7 |  68.9 | 5.1%    | 4.3%    | 0.8%    | 0.8%    |   0.16 |
| Simple Continuation          |  7336 |    6.8 |      5.5 | -59   | -23.2 |  35.2 |  74.8 | 6.0%    | 3.9%    | 0.9%    | 0.6%    |   0.38 |
| Cont + SPY Agree             |  3786 |    7.9 |      6   | -58.6 | -22.3 |  36.1 |  76.3 | 6.1%    | 3.8%    | 0.8%    | 0.5%    |   0.33 |
| Cont + SPY Agree + Stage 3+4 |  1942 |    9   |      8.5 | -61.6 | -22.4 |  41.2 |  83.2 | 7.0%    | 4.1%    | 0.9%    | 0.8%    |  -0.18 |

### 09:45 -> 09:55

| Cohort                       |     n |   Mean |   Median |   P10 |   P25 |   P75 |   P90 | >+100   | <−100   | >+200   | <−200   |   Skew |
|:-----------------------------|------:|-------:|---------:|------:|------:|------:|------:|:--------|:--------|:--------|:--------|-------:|
| All events                   | 17433 |    2.1 |      1.7 | -85.5 | -37.8 |  41.7 |  91.5 | 8.6%    | 7.9%    | 1.8%    | 1.7%    |   1    |
| Simple Continuation          |  7336 |    9   |      7.8 | -80.2 | -32.2 |  48.4 |  99.1 | 9.9%    | 7.2%    | 2.1%    | 1.6%    |   2.29 |
| Cont + SPY Agree             |  3786 |    9.7 |      8.2 | -80.4 | -32.4 |  49.6 | 101.5 | 10.2%   | 7.2%    | 2.2%    | 1.5%    |   3.58 |
| Cont + SPY Agree + Stage 3+4 |  1942 |   11.6 |     11   | -82.9 | -32.3 |  56.7 | 108.2 | 11.3%   | 7.3%    | 2.4%    | 1.5%    |  -0.07 |

### 09:45 -> 10:00 (reference)

| Cohort                       |     n |   Mean |   Median |    P10 |   P25 |   P75 |   P90 | >+100   | <−100   | >+200   | <−200   |   Skew |
|:-----------------------------|------:|-------:|---------:|-------:|------:|------:|------:|:--------|:--------|:--------|:--------|-------:|
| All events                   | 17433 |    1.1 |      1.4 | -100.8 | -45.2 |  47.4 | 103.6 | 10.6%   | 10.1%   | 2.6%    | 2.5%    |   0.47 |
| Simple Continuation          |  7336 |    8   |      6.6 |  -94.6 | -40.7 |  54.4 | 112.7 | 12.3%   | 9.2%    | 3.0%    | 2.2%    |   1.29 |
| Cont + SPY Agree             |  3786 |    7.9 |      6.3 |  -93.8 | -40.5 |  55.6 | 113.8 | 12.4%   | 9.2%    | 3.3%    | 2.1%    |   2    |
| Cont + SPY Agree + Stage 3+4 |  1942 |   11.6 |      9.1 |  -93.5 | -38.9 |  63.3 | 128.3 | 14.7%   | 9.2%    | 3.8%    | 2.4%    |  -0.33 |

### Winners vs losers, same statistics

**09:45 -> 09:50**

| Cohort                       | Side    |    n |   Mean |   Median |    P10 |   P25 |   P75 |   P90 |
|:-----------------------------|:--------|-----:|-------:|---------:|-------:|------:|------:|------:|
| All events                   | Winners | 8820 |   44.6 |     30.2 |    5.7 |  13.8 |  58.5 | 100.2 |
| All events                   | Losers  | 8241 |  -43.7 |    -30   |  -96.2 | -57.6 | -13.6 |  -5.6 |
| Simple Continuation          | Winners | 3998 |   46.5 |     31.7 |    6.3 |  15.1 |  61   | 104.2 |
| Simple Continuation          | Losers  | 3183 |  -42.7 |    -29.1 |  -96   | -56   | -13.1 |  -5.4 |
| Cont + SPY Agree             | Winners | 2073 |   47.3 |     32.5 |    6.7 |  15.8 |  62.7 | 105.7 |
| Cont + SPY Agree             | Losers  | 1625 |  -41.9 |    -27.7 |  -95.7 | -55.6 | -13.1 |  -5.4 |
| Cont + SPY Agree + Stage 3+4 | Winners | 1102 |   49.3 |     35.7 |    7.2 |  17.4 |  65.4 | 109.7 |
| Cont + SPY Agree + Stage 3+4 | Losers  |  796 |  -46.2 |    -30.2 | -100.1 | -60.7 | -15.3 |  -6.3 |

**09:45 -> 09:55**

| Cohort                       | Side    |    n |   Mean |   Median |    P10 |   P25 |   P75 |   P90 |
|:-----------------------------|:--------|-----:|-------:|---------:|-------:|------:|------:|------:|
| All events                   | Winners | 8845 |   59   |     41.1 |    7.9 |  18.3 |  77.6 | 132.6 |
| All events                   | Losers  | 8361 |  -58.1 |    -40   | -128.6 | -76   | -17.9 |  -7.4 |
| Simple Continuation          | Winners | 4034 |   62.2 |     43.7 |    8.6 |  20.5 |  81.7 | 139   |
| Simple Continuation          | Losers  | 3217 |  -57.4 |    -39.6 | -127.6 | -74.9 | -17.4 |  -6.9 |
| Cont + SPY Agree             | Winners | 2092 |   62.8 |     44.2 |    8.7 |  20.7 |  82.3 | 140.6 |
| Cont + SPY Agree             | Losers  | 1653 |  -57.2 |    -40   | -127.6 | -76   | -18   |  -7   |
| Cont + SPY Agree + Stage 3+4 | Winners | 1100 |   65.4 |     48.4 |    9.2 |  23.2 |  85.8 | 141.2 |
| Cont + SPY Agree + Stage 3+4 | Losers  |  825 |  -59.8 |    -41.4 | -133   | -80.2 | -18.2 |  -7.2 |

## Part 2 — Stop-loss simulation

`Avg ret stopped (no stop)` is the counterfactual: what those trades would have returned had the stop not been there. That column, not the realised −stop, is what tells you whether the stop helped or simply cut winners early.

### 09:45 -> 09:50 — Simple Continuation

|   Stop (bps) |    n | % stopped   |   Avg ret stopped (no stop) |   Avg ret not stopped | Win rate after stop   |   Exp. after stop |   Exp. no stop |   NET after stop |   net p | n<150?   |
|-------------:|-----:|:------------|----------------------------:|----------------------:|:----------------------|------------------:|---------------:|-----------------:|--------:|:---------|
|           40 | 7336 | 31.6%       |                       -40.1 |                  28.5 | 48.5%                 |               6.8 |            6.8 |             -0.1 |   0.883 |          |
|           50 | 7336 | 25.0%       |                       -49.3 |                  25.5 | 50.6%                 |               6.7 |            6.8 |             -0.3 |   0.674 |          |
|           60 | 7336 | 19.5%       |                       -59.4 |                  22.8 | 51.9%                 |               6.7 |            6.8 |             -0.2 |   0.712 |          |
|           80 | 7336 | 11.7%       |                       -80.5 |                  18.4 | 53.3%                 |               6.9 |            6.8 |             -0   |   0.95  |          |
|          100 | 7336 | 7.4%        |                      -101.2 |                  15.5 | 54.0%                 |               6.9 |            6.8 |             -0   |   0.981 |          |

### 09:45 -> 09:50 — Cont + SPY Agree

|   Stop (bps) |    n | % stopped   |   Avg ret stopped (no stop) |   Avg ret not stopped | Win rate after stop   |   Exp. after stop |   Exp. no stop |   NET after stop |   net p | n<150?   |
|-------------:|-----:|:------------|----------------------------:|----------------------:|:----------------------|------------------:|---------------:|-----------------:|--------:|:---------|
|           40 | 3786 | 30.4%       |                       -40.7 |                  29.2 | 49.0%                 |               8.1 |            7.9 |              1.2 |   0.187 |          |
|           50 | 3786 | 23.9%       |                       -50.7 |                  26.4 | 51.1%                 |               8.1 |            7.9 |              1.1 |   0.21  |          |
|           60 | 3786 | 18.8%       |                       -61   |                  23.9 | 52.5%                 |               8.1 |            7.9 |              1.2 |   0.229 |          |
|           80 | 3786 | 11.6%       |                       -80.4 |                  19.6 | 53.8%                 |               8   |            7.9 |              1   |   0.339 |          |
|          100 | 3786 | 7.4%        |                       -99.8 |                  16.5 | 54.4%                 |               7.9 |            7.9 |              1   |   0.374 |          |

### 09:45 -> 09:55 — Simple Continuation

|   Stop (bps) |    n | % stopped   |   Avg ret stopped (no stop) |   Avg ret not stopped | Win rate after stop   |   Exp. after stop |   Exp. no stop |   NET after stop |   net p | n<150?   |
|-------------:|-----:|:------------|----------------------------:|----------------------:|:----------------------|------------------:|---------------:|-----------------:|--------:|:---------|
|           40 | 7336 | 41.6%       |                       -40   |                  44   | 45.0%                 |               9   |              9 |              2.1 |   0.013 |          |
|           50 | 7336 | 34.5%       |                       -49.8 |                  40   | 48.0%                 |               8.9 |              9 |              2   |   0.023 |          |
|           60 | 7336 | 28.4%       |                       -60.3 |                  36.5 | 50.0%                 |               9.1 |              9 |              2.2 |   0.015 |          |
|           80 | 7336 | 19.3%       |                       -81.6 |                  30.7 | 52.4%                 |               9.3 |              9 |              2.4 |   0.013 |          |
|          100 | 7336 | 13.3%       |                      -102.7 |                  26.2 | 53.7%                 |               9.4 |              9 |              2.4 |   0.013 |          |

### 09:45 -> 09:55 — Cont + SPY Agree

|   Stop (bps) |    n | % stopped   |   Avg ret stopped (no stop) |   Avg ret not stopped | Win rate after stop   |   Exp. after stop |   Exp. no stop |   NET after stop |   net p | n<150?   |
|-------------:|-----:|:------------|----------------------------:|----------------------:|:----------------------|------------------:|---------------:|-----------------:|--------:|:---------|
|           40 | 3786 | 40.4%       |                       -41.7 |                  44.6 | 46.1%                 |              10.4 |            9.7 |              3.4 |   0.012 |          |
|           50 | 3786 | 33.2%       |                       -52.3 |                  40.5 | 48.9%                 |              10.5 |            9.7 |              3.5 |   0.014 |          |
|           60 | 3786 | 27.5%       |                       -62.8 |                  37.2 | 50.8%                 |              10.5 |            9.7 |              3.5 |   0.013 |          |
|           80 | 3786 | 19.1%       |                       -82   |                  31.4 | 52.9%                 |              10.1 |            9.7 |              3.1 |   0.033 |          |
|          100 | 3786 | 13.4%       |                      -102.7 |                  27.1 | 54.1%                 |              10.1 |            9.7 |              3.1 |   0.041 |          |

## Part 3 — VIX regime (prior-day close)

### 09:45 -> 09:50

| Cohort              | VIX bucket          |    n | Win rate   | Wilson lo   | Wilson hi   |   Gross exp. |     p |   NET exp. |   net p | n<150?   |
|:--------------------|:--------------------|-----:|:-----------|:------------|:------------|-------------:|------:|-----------:|--------:|:---------|
| Simple Continuation | Low VIX (<15)       | 2556 | 55.0%      | 53.1%       | 56.9%       |          7.8 | 0     |        0.8 |   0.482 |          |
| Simple Continuation | Medium VIX (15-20)  | 2751 | 54.6%      | 52.7%       | 56.5%       |          7.1 | 0     |        0.3 |   0.841 |          |
| Simple Continuation | High VIX (20-25)    | 1166 | 53.1%      | 50.2%       | 55.9%       |          5.4 | 0.012 |       -1.6 |   0.446 |          |
| Simple Continuation | Very High VIX (>25) |  863 | 54.6%      | 51.2%       | 57.9%       |          5.2 | 0.047 |       -2   |   0.427 |          |
| Cont + SPY Agree    | Low VIX (<15)       | 1261 | 57.1%      | 54.3%       | 59.8%       |          9.2 | 0     |        2.2 |   0.185 |          |
| Cont + SPY Agree    | Medium VIX (15-20)  | 1423 | 53.0%      | 50.4%       | 55.6%       |          7.2 | 0     |        0.4 |   0.816 |          |
| Cont + SPY Agree    | High VIX (20-25)    |  620 | 53.2%      | 49.3%       | 57.1%       |          8   | 0.007 |        1   |   0.737 |          |
| Cont + SPY Agree    | Very High VIX (>25) |  482 | 55.8%      | 51.3%       | 60.2%       |          6.6 | 0.065 |       -0.7 |   0.855 |          |

### 09:45 -> 09:55

| Cohort              | VIX bucket          |    n | Win rate   | Wilson lo   | Wilson hi   |   Gross exp. |     p |   NET exp. |   net p | n<150?   |
|:--------------------|:--------------------|-----:|:-----------|:------------|:------------|-------------:|------:|-----------:|--------:|:---------|
| Simple Continuation | Low VIX (<15)       | 2556 | 55.6%      | 53.7%       | 57.6%       |          9.5 | 0     |        2.5 |   0.1   |          |
| Simple Continuation | Medium VIX (15-20)  | 2751 | 54.4%      | 52.6%       | 56.3%       |          9.5 | 0     |        2.7 |   0.144 |          |
| Simple Continuation | High VIX (20-25)    | 1166 | 53.3%      | 50.4%       | 56.1%       |          6.7 | 0.041 |       -0.3 |   0.911 |          |
| Simple Continuation | Very High VIX (>25) |  863 | 57.2%      | 53.9%       | 60.5%       |          9.1 | 0.01  |        1.9 |   0.62  |          |
| Cont + SPY Agree    | Low VIX (<15)       | 1261 | 56.1%      | 53.4%       | 58.9%       |         10.1 | 0     |        3.1 |   0.158 |          |
| Cont + SPY Agree    | Medium VIX (15-20)  | 1423 | 53.8%      | 51.2%       | 56.3%       |         10.7 | 0     |        3.9 |   0.183 |          |
| Cont + SPY Agree    | High VIX (20-25)    |  620 | 53.4%      | 49.5%       | 57.3%       |          6   | 0.178 |       -1   |   0.807 |          |
| Cont + SPY Agree    | Very High VIX (>25) |  482 | 59.8%      | 55.3%       | 64.0%       |         10.6 | 0.012 |        3.3 |   0.422 |          |

## Part 4 — Gap size relative to prior-day ATR(14)

### 09:45 -> 09:50

| Cohort              | Gap/ATR bucket   |    n | Win rate   | Wilson lo   | Wilson hi   |   Gross exp. |   p |   NET exp. |   net p | n<150?   |
|:--------------------|:-----------------|-----:|:-----------|:------------|:------------|-------------:|----:|-----------:|--------:|:---------|
| Simple Continuation | Gap/ATR < 1.0    | 5421 | 54.1%      | 52.8%       | 55.5%       |          5.4 |   0 |       -1.4 |   0.059 |          |
| Simple Continuation | Gap/ATR 1.0-2.0  |  886 | 55.3%      | 52.0%       | 58.5%       |          9.6 |   0 |        2.4 |   0.344 |          |
| Simple Continuation | Gap/ATR > 2.0    | 1029 | 55.7%      | 52.6%       | 58.7%       |         11.8 |   0 |        4.7 |   0.146 |          |

### 09:45 -> 09:55

| Cohort              | Gap/ATR bucket   |    n | Win rate   | Wilson lo   | Wilson hi   |   Gross exp. |     p |   NET exp. |   net p | n<150?   |
|:--------------------|:-----------------|-----:|:-----------|:------------|:------------|-------------:|------:|-----------:|--------:|:---------|
| Simple Continuation | Gap/ATR < 1.0    | 5421 | 54.7%      | 53.4%       | 56.0%       |          7.9 | 0     |        1   |   0.354 |          |
| Simple Continuation | Gap/ATR 1.0-2.0  |  886 | 55.8%      | 52.5%       | 59.0%       |         10.7 | 0.002 |        3.6 |   0.315 |          |
| Simple Continuation | Gap/ATR > 2.0    | 1029 | 55.8%      | 52.7%       | 58.8%       |         13.4 | 0     |        6.2 |   0.135 |          |

## Part 5 — Combined VIX × Gap/ATR (Cont + SPY Agree, n ≥ 150)

| Window         | VIX | Gap-ATR                        |    n | Win rate   |   Gross exp. |     p |   NET exp. |   net p |
|:---------------|:-------------------------------------|-----:|:-----------|-------------:|------:|-----------:|--------:|
| 09:45 -> 09:50 | Low VIX (<15) | Gap/ATR > 2.0        |  186 | 60.2%      |         20.1 | 0.003 |       12.8 |   0.055 |
| 09:45 -> 09:55 | Low VIX (<15) | Gap/ATR > 2.0        |  186 | 58.6%      |         20.1 | 0.014 |       12.8 |   0.132 |
| 09:45 -> 10:00 | Medium VIX (15-20) | Gap/ATR > 2.0   |  211 | 53.6%      |         14.2 | 0.133 |        7.1 |   0.474 |
| 09:45 -> 09:50 | Medium VIX (15-20) | Gap/ATR > 2.0   |  211 | 55.5%      |         13.7 | 0.028 |        6.6 |   0.315 |
| 09:45 -> 09:55 | Medium VIX (15-20) | Gap/ATR > 2.0   |  211 | 53.1%      |         13.6 | 0.123 |        6.5 |   0.455 |
| 09:45 -> 09:55 | Medium VIX (15-20) | Gap/ATR 1.0-2.0 |  193 | 54.9%      |         12.9 | 0.123 |        6   |   0.448 |
| 09:45 -> 10:00 | Very High VIX (>25) | Gap/ATR < 1.0  |  392 | 56.6%      |         11.5 | 0.034 |        4.3 |   0.416 |
| 09:45 -> 09:50 | Medium VIX (15-20) | Gap/ATR 1.0-2.0 |  193 | 55.4%      |         11   | 0.069 |        4.1 |   0.479 |
| 09:45 -> 10:00 | Medium VIX (15-20) | Gap/ATR 1.0-2.0 |  193 | 54.9%      |         10.6 | 0.276 |        3.7 |   0.7   |
| 09:45 -> 10:00 | Low VIX (<15) | Gap/ATR < 1.0        |  946 | 55.0%      |         10.6 | 0     |        3.7 |   0.129 |
| 09:45 -> 09:55 | Very High VIX (>25) | Gap/ATR < 1.0  |  392 | 59.7%      |         10.5 | 0.005 |        3.4 |   0.367 |
| 09:45 -> 09:55 | Medium VIX (15-20) | Gap/ATR < 1.0   | 1019 | 53.7%      |          9.7 | 0.005 |        3   |   0.365 |
| 09:45 -> 09:55 | Low VIX (<15) | Gap/ATR < 1.0        |  946 | 56.2%      |          9.5 | 0     |        2.6 |   0.214 |
| 09:45 -> 10:00 | Medium VIX (15-20) | Gap/ATR < 1.0   | 1019 | 54.1%      |          8.1 | 0.013 |        1.4 |   0.64  |
| 09:45 -> 09:50 | Low VIX (<15) | Gap/ATR < 1.0        |  946 | 56.9%      |          8   | 0     |        1.1 |   0.513 |
| 09:45 -> 10:00 | Low VIX (<15) | Gap/ATR > 2.0        |  186 | 51.1%      |          8.2 | 0.35  |        0.9 |   0.939 |
| 09:45 -> 09:50 | Very High VIX (>25) | Gap/ATR < 1.0  |  392 | 55.1%      |          6.6 | 0.043 |       -0.5 |   0.892 |
| 09:45 -> 09:50 | Medium VIX (15-20) | Gap/ATR < 1.0   | 1019 | 52.0%      |          5.1 | 0.006 |       -1.6 |   0.391 |
| 09:45 -> 09:50 | High VIX (20-25) | Gap/ATR < 1.0     |  490 | 52.2%      |          4.5 | 0.119 |       -2.4 |   0.408 |
| 09:45 -> 09:55 | High VIX (20-25) | Gap/ATR < 1.0     |  490 | 53.5%      |          4.2 | 0.356 |       -2.7 |   0.55  |
| 09:45 -> 10:00 | High VIX (20-25) | Gap/ATR < 1.0     |  490 | 52.9%      |          0.9 | 0.909 |       -6.1 |   0.305 |

> This is a search over many cells with the sample already thinned twice. Read the ordering, not the top row.

---

## Answers

### 1. Is the distribution symmetric or skewed?

**Near-symmetric at 5 minutes, distinctly right-skewed by 10.** At five minutes the All-events distribution has mean +1.9 bps against a median of +1.2, quantiles P25/P75 = -28/+31 and P10/P90 = -64/+69 — close to mirror images. Skew is only +0.16.

By ten minutes the right tail has stretched: skew rises to +1.00 for All events and +2.29 for the Continuation cohort, with P90 at +91 bps against P10 of -86. The extra five minutes buys a longer upside tail more than a longer downside one.

### 2. Are the loss tails heavier than the win tails?

**No — the win tails are consistently the heavier side.** At five minutes 5.09% of trades exceed +100 bps against 4.34% below −100; at ten minutes it is 8.64% versus 7.88%. The ±200 bps tails are near-identical (0.76% vs 0.75% at five minutes). Conditioning on the Continuation pattern widens the gap further (9.88% vs 7.22% at ten minutes).

So there is no hidden crash risk that the win rate was concealing — which also means there is no fat left tail for a stop to protect against, and that turns out to matter for question 3.

### 3. Which stop distance most improves expectancy?

**None of them meaningfully — stops are close to neutral here, and the ordering is the opposite of the usual intuition.**

- **40 bps stop** — 41.6% stopped out, expectancy +8.99 bps against +9.00 with no stop (-0.01), net +2.07 (p = 0.013)
- **50 bps stop** — 34.5% stopped out, expectancy +8.93 bps against +9.00 with no stop (-0.07), net +2.01 (p = 0.023)
- **60 bps stop** — 28.4% stopped out, expectancy +9.09 bps against +9.00 with no stop (+0.08), net +2.16 (p = 0.015)
- **80 bps stop** — 19.3% stopped out, expectancy +9.31 bps against +9.00 with no stop (+0.31), net +2.39 (p = 0.013)
- **100 bps stop** — 13.3% stopped out, expectancy +9.37 bps against +9.00 with no stop (+0.36), net +2.44 (p = 0.013)

The best of them is the **widest** tested, 100 bps, and it adds only +0.36 bps. Tight stops (40–50) are slightly negative; wide stops are slightly positive. Every effect is a rounding error against an expectancy of ~9 bps.

The `Avg ret stopped (no stop)` column explains why. For a 40 bps stop the trades that touch it would have ended the window at −40.0 bps on average anyway; for a 100 bps stop, −102.7. **The stop level and the eventual outcome are almost the same number**, so stopping out neither rescues nor destroys much. Over five to ten minutes the adverse excursion essentially *is* the outcome — there is no meaningful recovery to protect and no runaway loss to cut. And the simulation assumes a perfect fill at the stop, so the true numbers are slightly worse than shown.

### 4. Does the edge strengthen in elevated VIX?

**No — there is no clean VIX effect.** Net expectancy by prior-day VIX bucket, 10-minute window:

- **Low VIX (<15)** — n = 1,261, win rate 56.1%, gross +10.1, net +3.1 bps (p = 0.158)
- **Medium VIX (15-20)** — n = 1,423, win rate 53.8%, gross +10.7, net +3.9 bps (p = 0.183)
- **High VIX (20-25)** — n = 620, win rate 53.4%, gross +6.0, net -1.0 bps (p = 0.807)
- **Very High VIX (>25)** — n = 482, win rate 59.8%, gross +10.6, net +3.3 bps (p = 0.422)

The pattern is **not monotone**: Low and Medium VIX give the steadiest net (+3.1 and +3.9), High VIX is actually negative (−1.0), and Very High VIX has the best win rate of all (59.8%) but a net of only +3.3 with p = 0.42. Elevated volatility widens the distribution on both sides — it raises gross numbers without reliably raising net, and it raises the variance enough that nothing reaches significance. VIX is not a useful filter for this idea.

### 5. Does a larger gap relative to ATR help?

**Yes — and this is the one filter in the whole report that clearly works.** Simple Continuation, split by gap size in prior-day ATR units:

*09:45 -> 09:50*
- **Gap/ATR < 1.0** — n = 5,421, win rate 54.1%, gross +5.4, net -1.4 bps
- **Gap/ATR 1.0-2.0** — n = 886, win rate 55.3%, gross +9.6, net +2.4 bps
- **Gap/ATR > 2.0** — n = 1,029, win rate 55.7%, gross +11.8, net +4.7 bps

*09:45 -> 09:55*
- **Gap/ATR < 1.0** — n = 5,421, win rate 54.7%, gross +7.9, net +1.0 bps
- **Gap/ATR 1.0-2.0** — n = 886, win rate 55.8%, gross +10.7, net +3.6 bps
- **Gap/ATR > 2.0** — n = 1,029, win rate 55.8%, gross +13.4, net +6.2 bps

The effect is **monotone in both windows**. At ten minutes net expectancy climbs from +1.0 bps (Gap/ATR < 1.0) to +3.6 (1.0–2.0) to **+6.2 bps** (> 2.0); at five minutes it goes from −1.4 to +4.7, turning a losing cohort into a profitable one.

The mechanism is worth stating precisely, because it is the opposite of what a win-rate lens would suggest. The **hit rate barely moves** — 54.7% for small gaps versus 55.8% for large. What changes is the *size* of the move: a bigger overnight shock produces a bigger subsequent range. Since the round-trip cost is **fixed at ~6.6 bps regardless of how far the stock travels**, scaling up the move while holding the hit rate constant scales up the net edge directly. Gap/ATR does not make the direction call more accurate; it makes each correct call worth more against an unchanged cost.

The caveat is power: the large-gap bucket holds 1,029 events and the p-values (0.135–0.146) do not clear 0.05, precisely because larger moves also mean larger variance.

### 6. Overall: do VIX + ATR + a stop make this usable?

**Partly — one of the three helps, and it is not the one that usually gets the attention.**

- **Stops: no.** Neutral at best. Over these horizons the adverse excursion and the final outcome are nearly the same number, so there is nothing for a stop to add. Tight stops slightly hurt.
- **VIX: no.** Non-monotone across buckets, nothing significant, and the highest-win-rate bucket is not the highest-net one.
- **Gap/ATR: yes, materially.** Monotone in both windows and roughly doubling to quadrupling net expectancy, for the sound structural reason that costs are fixed while moves scale.

Stacking the filters, the best cell with n ≥ 150 is **Low VIX (<15) | Gap/ATR > 2.0** on 09:45 -> 09:50: win rate 60.2%, net **+12.8 bps** (n = 186, p = 0.055). That is by far the strongest cell produced anywhere in this investigation — but it is one of 21 cells searched, on a sample thinned twice, and it does not clear p = 0.05.

**Where this leaves the idea.** The honest summary is that Gap/ATR converts the Simple Continuation pattern from marginal into something with a visible margin: roughly +6 bps net per trade on large-gap events at a ten-minute hold, against ~+1 bps for small-gap ones. That is a real improvement and it rests on a mechanism rather than a coincidence.

It still falls short of deployable, for reasons this report cannot fix. The filtered sample is ~1,000 events and the p-values sit around 0.14. The universe carries survivorship bias that pushes every number here upward. And ~6 bps per trade remains inside the range that one unmodelled friction — borrow cost on the short leg, a wider spread on a smaller name, a partial fill — would consume.

The right next step is no longer another filter. It is to re-run the large-gap Continuation cohort on a survivorship-free universe with real quoted spreads, because that is now the binding constraint on whether this is tradeable — not the signal itself.

---

_Reproducible from `lambda_strategy_validation/deep_tests.py`; tables in `lambda_data/tables/p1_*.csv` through `p5_combined.csv`. VIX from CBOE's official daily history._