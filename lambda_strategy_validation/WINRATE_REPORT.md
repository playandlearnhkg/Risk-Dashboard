# Lambda Win-Rate Report — Continuation Probability Only

This report deliberately contains **no average returns, no net bps and no cost model**. Every cell is a count and a continuation win rate.

## Definitions used (exactly as specified)

| Term | Rule |
|---|---|
| Gap Up | `Open_T+1 > Prior Close` |
| Gap Down | `Open_T+1 < Prior Close` |
| Intraday Up | `Close_T+1 > Open_T+1` |
| Intraday Down | `Close_T+1 < Open_T+1` |
| Continuation | gap direction == intraday direction |

Sample: **17,583** T+1 earnings sessions (2015-2025). Exact ties are undefined under these rules and are excluded — 125 gap ties (Open == Prior Close) and 61 intraday ties (Close == Open) — leaving **17,397** events. Cells with n < 100 are flagged `YES` under `small n?`.

### How the two pattern systems are classified

**System 1 — original 4-pattern**, using all three 5-minute candles (09:30-09:35, 09:35-09:40, 09:40-09:45):

- **Strong Continuation+** — all three candles close in the gap direction AND highs progress upward (gap up) / lows progress downward (gap down).
- **Moderate Continuation+** — at least 2 of 3 close in the gap direction, and the third is not a strong counter-move (its body is < 50% of the mean body of the other two).
- **Early Reversal−** — the majority close against the gap, OR candle 1 shows a rejection wick against the gap direction longer than 60% of that candle's range.
- **Indecision0** — everything else.

**System 2 — simple online-style**, using ONLY the first 5-minute candle (09:30-09:35). Stated precisely so it is reproducible:

```
body  = c1_close - c1_open
range = c1_high  - c1_low

Doji         : range == 0  OR  |body| / range < 0.1
Continuation : otherwise, sign(body) == sign(gap)
Reversal     : otherwise, sign(body) != sign(gap)
```

The doji bucket uses body-to-range rather than an absolute price threshold, so it is scale-free across a $15 stock and a $900 one.

### Two intervals, shown side by side on purpose

`Wilson lo/hi` is the standard 95% interval for a proportion and assumes every event is independent. `p (binomial)` makes the same assumption. **That assumption is false here**: dozens of firms report the same evening and share the next day's market move, so events cluster by date. `p (clustered)` re-tests the win rate against a 50% null by resampling whole trading dates. Where the two disagree, the clustered one is correct and the Wilson interval is too narrow.

---

## Table 1 — Overall four quadrants

Raw cell counts:

| gap      |   Intraday Down |   Intraday Up |   Intraday Down % |   Intraday Up % |
|:---------|----------------:|--------------:|------------------:|----------------:|
| Gap Down |            4268 |          3972 |             24.53 |           22.83 |
| Gap Up   |            4613 |          4544 |             26.52 |           26.12 |

Continuation win rate:

| subgroup   | gap      |     n |   n cont |   n rev | Cont. win rate   | Wilson lo   | Wilson hi   |   p (clustered) |   p (binomial) | small n?   |
|:-----------|:---------|------:|---------:|--------:|:-----------------|:------------|:------------|----------------:|---------------:|:-----------|
| All events | Gap Up   |  9157 |     4544 |    4613 | 49.6%            | 48.6%       | 50.6%       |           0.603 |          0.477 |            |
| All events | Gap Down |  8240 |     4268 |    3972 | 51.8%            | 50.7%       | 52.9%       |           0.024 |          0.001 |            |
| All events | Both     | 17397 |     8812 |    8585 | 50.7%            | 49.9%       | 51.4%       |           0.158 |          0.087 |            |

## Table 2 — Quadrants split by the original 4-pattern system

> **Read this with care.** The pattern is built from 09:30-09:45, which sits *inside* the Open→Close window being scored. A pattern that moved with the gap has already contributed the first 15 minutes of the very move it is being credited for, so these separations are partly self-fulfilling. The clean, non-overlapping version is Table 2b.

| subgroup               | gap      |    n |   n cont |   n rev | Cont. win rate   | Wilson lo   | Wilson hi   |   p (clustered) |   p (binomial) | small n?   |
|:-----------------------|:---------|-----:|---------:|--------:|:-----------------|:------------|:------------|----------------:|---------------:|:-----------|
| Strong Continuation+   | Gap Up   |  789 |      671 |     118 | 85.0%            | 82.4%       | 87.4%       |               0 |              0 |            |
| Strong Continuation+   | Gap Down |  702 |      592 |     110 | 84.3%            | 81.5%       | 86.8%       |               0 |              0 |            |
| Strong Continuation+   | Both     | 1491 |     1263 |     228 | 84.7%            | 82.8%       | 86.4%       |               0 |              0 |            |
| Moderate Continuation+ | Gap Up   | 1351 |     1018 |     333 | 75.4%            | 73.0%       | 77.6%       |               0 |              0 |            |
| Moderate Continuation+ | Gap Down | 1300 |     1025 |     275 | 78.8%            | 76.5%       | 81.0%       |               0 |              0 |            |
| Moderate Continuation+ | Both     | 2651 |     2043 |     608 | 77.1%            | 75.4%       | 78.6%       |               0 |              0 |            |
| Indecision0            | Gap Up   | 1926 |     1092 |     834 | 56.7%            | 54.5%       | 58.9%       |               0 |              0 |            |
| Indecision0            | Gap Down | 1791 |     1006 |     785 | 56.2%            | 53.9%       | 58.5%       |               0 |              0 |            |
| Indecision0            | Both     | 3717 |     2098 |    1619 | 56.4%            | 54.8%       | 58.0%       |               0 |              0 |            |
| Early Reversal-        | Gap Up   | 4492 |     1584 |    2908 | 35.3%            | 33.9%       | 36.7%       |               0 |              0 |            |
| Early Reversal-        | Gap Down | 3941 |     1499 |    2442 | 38.0%            | 36.5%       | 39.6%       |               0 |              0 |            |
| Early Reversal-        | Both     | 8433 |     3083 |    5350 | 36.6%            | 35.5%       | 37.6%       |               0 |              0 |            |

### Table 2b — same split, scored only on 09:45 → Close (no overlap)

Here the pattern is complete *before* the measured window starts, so it cannot score itself. This is the honest version of Table 2.

| subgroup               | gap      |    n |   n cont |   n rev | Cont. win rate   | Wilson lo   | Wilson hi   |   p (clustered) |   p (binomial) | small n?   |
|:-----------------------|:---------|-----:|---------:|--------:|:-----------------|:------------|:------------|----------------:|---------------:|:-----------|
| Strong Continuation+   | Gap Up   |  787 |      406 |     381 | 51.6%            | 48.1%       | 55.1%       |           0.414 |          0.392 |            |
| Strong Continuation+   | Gap Down |  694 |      353 |     341 | 50.9%            | 47.2%       | 54.6%       |           0.71  |          0.676 |            |
| Strong Continuation+   | Both     | 1481 |      759 |     722 | 51.2%            | 48.7%       | 53.8%       |           0.358 |          0.35  |            |
| Moderate Continuation+ | Gap Up   | 1342 |      671 |     671 | 50.0%            | 47.3%       | 52.7%       |           1     |          1     |            |
| Moderate Continuation+ | Gap Down | 1295 |      658 |     637 | 50.8%            | 48.1%       | 53.5%       |           0.599 |          0.578 |            |
| Moderate Continuation+ | Both     | 2637 |     1329 |    1308 | 50.4%            | 48.5%       | 52.3%       |           0.691 |          0.697 |            |
| Indecision0            | Gap Up   | 1915 |      992 |     923 | 51.8%            | 49.6%       | 54.0%       |           0.191 |          0.12  |            |
| Indecision0            | Gap Down | 1787 |      901 |     886 | 50.4%            | 48.1%       | 52.7%       |           0.748 |          0.741 |            |
| Indecision0            | Both     | 3702 |     1893 |    1809 | 51.1%            | 49.5%       | 52.7%       |           0.185 |          0.173 |            |
| Early Reversal-        | Gap Up   | 4469 |     2203 |    2266 | 49.3%            | 47.8%       | 50.8%       |           0.486 |          0.354 |            |
| Early Reversal-        | Gap Down | 3930 |     1982 |    1948 | 50.4%            | 48.9%       | 52.0%       |           0.695 |          0.599 |            |
| Early Reversal-        | Both     | 8399 |     4185 |    4214 | 49.8%            | 48.8%       | 50.9%       |           0.799 |          0.76  |            |

## Table 3 — Quadrants split by the simple online-style pattern

> Same overlap caveat as Table 2: the first candle (09:30-09:35) is inside the Open→Close window. Table 3b is the clean version.

| subgroup                           | gap      |    n |   n cont |   n rev | Cont. win rate   | Wilson lo   | Wilson hi   |   p (clustered) |   p (binomial) | small n?   |
|:-----------------------------------|:---------|-----:|---------:|--------:|:-----------------|:------------|:------------|----------------:|---------------:|:-----------|
| Continuation (1st candle with gap) | Gap Up   | 3843 |     2691 |    1152 | 70.0%            | 68.6%       | 71.5%       |           0     |          0     |            |
| Continuation (1st candle with gap) | Gap Down | 3471 |     2496 |     975 | 71.9%            | 70.4%       | 73.4%       |           0     |          0     |            |
| Continuation (1st candle with gap) | Both     | 7314 |     5187 |    2127 | 70.9%            | 69.9%       | 71.9%       |           0     |          0     |            |
| Reversal (1st candle against gap)  | Gap Up   | 4109 |     1334 |    2775 | 32.5%            | 31.1%       | 33.9%       |           0     |          0     |            |
| Reversal (1st candle against gap)  | Gap Down | 3709 |     1293 |    2416 | 34.9%            | 33.3%       | 36.4%       |           0     |          0     |            |
| Reversal (1st candle against gap)  | Both     | 7818 |     2627 |    5191 | 33.6%            | 32.6%       | 34.7%       |           0     |          0     |            |
| Doji (1st candle)                  | Gap Up   |  770 |      399 |     371 | 51.8%            | 48.3%       | 55.3%       |           0.345 |          0.331 |            |
| Doji (1st candle)                  | Gap Down |  687 |      374 |     313 | 54.4%            | 50.7%       | 58.1%       |           0.031 |          0.022 |            |
| Doji (1st candle)                  | Both     | 1457 |      773 |     684 | 53.1%            | 50.5%       | 55.6%       |           0.032 |          0.021 |            |

### Table 3b — same split, scored only on 09:45 → Close (no overlap)

| subgroup                           | gap      |    n |   n cont |   n rev | Cont. win rate   | Wilson lo   | Wilson hi   |   p (clustered) |   p (binomial) | small n?   |
|:-----------------------------------|:---------|-----:|---------:|--------:|:-----------------|:------------|:------------|----------------:|---------------:|:-----------|
| Continuation (1st candle with gap) | Gap Up   | 3825 |     1976 |    1849 | 51.7%            | 50.1%       | 53.2%       |           0.097 |          0.042 |            |
| Continuation (1st candle with gap) | Gap Down | 3451 |     1759 |    1692 | 51.0%            | 49.3%       | 52.6%       |           0.369 |          0.261 |            |
| Continuation (1st candle with gap) | Both     | 7276 |     3735 |    3541 | 51.3%            | 50.2%       | 52.5%       |           0.036 |          0.024 |            |
| Reversal (1st candle against gap)  | Gap Up   | 4088 |     1977 |    2111 | 48.4%            | 46.8%       | 49.9%       |           0.098 |          0.037 |            |
| Reversal (1st candle against gap)  | Gap Down | 3699 |     1829 |    1870 | 49.4%            | 47.8%       | 51.1%       |           0.61  |          0.511 |            |
| Reversal (1st candle against gap)  | Both     | 7787 |     3806 |    3981 | 48.9%            | 47.8%       | 50.0%       |           0.091 |          0.049 |            |
| Doji (1st candle)                  | Gap Up   |  764 |      383 |     381 | 50.1%            | 46.6%       | 53.7%       |           0.944 |          0.971 |            |
| Doji (1st candle)                  | Gap Down |  687 |      357 |     330 | 52.0%            | 48.2%       | 55.7%       |           0.345 |          0.321 |            |
| Doji (1st candle)                  | Both     | 1451 |      740 |     711 | 51.0%            | 48.4%       | 53.6%       |           0.472 |          0.462 |            |

## Table 4 — Quadrants split by holding period

For a shorter window, 'intraday direction' is the sign of the move over that window, and continuation means it matches the gap direction. Windows are measured on 1-minute bars; sessions with an exactly flat window are excluded.

| subgroup                 | gap      |     n |   n cont |   n rev | Cont. win rate   | Wilson lo   | Wilson hi   |   p (clustered) |   p (binomial) | small n?   |
|:-------------------------|:---------|------:|---------:|--------:|:-----------------|:------------|:------------|----------------:|---------------:|:-----------|
| Full day (Open -> Close) | Gap Up   |  9156 |     4543 |    4613 | 49.6%            | 48.6%       | 50.6%       |           0.594 |          0.471 |            |
| Full day (Open -> Close) | Gap Down |  8240 |     4268 |    3972 | 51.8%            | 50.7%       | 52.9%       |           0.024 |          0.001 |            |
| Full day (Open -> Close) | Both     | 17396 |     8811 |    8585 | 50.6%            | 49.9%       | 51.4%       |           0.159 |          0.088 |            |
| 09:45 -> 10:00           | Gap Up   |  9058 |     4521 |    4537 | 49.9%            | 48.9%       | 50.9%       |           0.906 |          0.875 |            |
| 09:45 -> 10:00           | Gap Down |  8151 |     4216 |    3935 | 51.7%            | 50.6%       | 52.8%       |           0.019 |          0.002 |            |
| 09:45 -> 10:00           | Both     | 17209 |     8737 |    8472 | 50.8%            | 50.0%       | 51.5%       |           0.066 |          0.044 |            |
| 09:45 -> 10:15           | Gap Up   |  9079 |     4525 |    4554 | 49.8%            | 48.8%       | 50.9%       |           0.823 |          0.769 |            |
| 09:45 -> 10:15           | Gap Down |  8150 |     4182 |    3968 | 51.3%            | 50.2%       | 52.4%       |           0.079 |          0.018 |            |
| 09:45 -> 10:15           | Both     | 17229 |     8707 |    8522 | 50.5%            | 49.8%       | 51.3%       |           0.212 |          0.161 |            |
| 09:45 -> 11:00           | Gap Up   |  9116 |     4558 |    4558 | 50.0%            | 49.0%       | 51.0%       |           1     |          1     |            |
| 09:45 -> 11:00           | Gap Down |  8191 |     4240 |    3951 | 51.8%            | 50.7%       | 52.8%       |           0.03  |          0.001 |            |
| 09:45 -> 11:00           | Both     | 17307 |     8798 |    8509 | 50.8%            | 50.1%       | 51.6%       |           0.059 |          0.029 |            |

Quadrant counts per window:

| gap      |   Intraday Down |   Intraday Up |   Intraday Down % |   Intraday Up % | window                   |
|:---------|----------------:|--------------:|------------------:|----------------:|:-------------------------|
| Gap Down |            4268 |          3972 |             24.53 |           22.83 | Full day (Open -> Close) |
| Gap Up   |            4613 |          4543 |             26.52 |           26.12 | Full day (Open -> Close) |
| Gap Down |            4216 |          3935 |             24.5  |           22.87 | 09:45 -> 10:00           |
| Gap Up   |            4537 |          4521 |             26.36 |           26.27 | 09:45 -> 10:00           |
| Gap Down |            4182 |          3968 |             24.27 |           23.03 | 09:45 -> 10:15           |
| Gap Up   |            4554 |          4525 |             26.43 |           26.26 | 09:45 -> 10:15           |
| Gap Down |            4240 |          3951 |             24.5  |           22.83 | 09:45 -> 11:00           |
| Gap Up   |            4558 |          4558 |             26.34 |           26.34 | 09:45 -> 11:00           |

## Table 5 — Quadrants split by SPY direction on T+1

> Note: SPY's open-to-close direction is only known at 16:00, so this is a **diagnostic split, not a tradeable filter**. It describes the market conditions under which continuation happened; it cannot be used to select trades at the open.

| subgroup   | gap      |    n |   n cont |   n rev | Cont. win rate   | Wilson lo   | Wilson hi   |   p (clustered) |   p (binomial) | small n?   |
|:-----------|:---------|-----:|---------:|--------:|:-----------------|:------------|:------------|----------------:|---------------:|:-----------|
| SPY up     | Gap Up   | 4922 |     2870 |    2052 | 58.3%            | 56.9%       | 59.7%       |           0     |          0     |            |
| SPY up     | Gap Down | 4277 |     1855 |    2422 | 43.4%            | 41.9%       | 44.9%       |           0     |          0     |            |
| SPY up     | Both     | 9199 |     4725 |    4474 | 51.4%            | 50.3%       | 52.4%       |           0.028 |          0.009 |            |
| SPY down   | Gap Up   | 4235 |     1674 |    2561 | 39.5%            | 38.1%       | 41.0%       |           0     |          0     |            |
| SPY down   | Gap Down | 3963 |     2413 |    1550 | 60.9%            | 59.4%       | 62.4%       |           0     |          0     |            |
| SPY down   | Both     | 8198 |     4087 |    4111 | 49.9%            | 48.8%       | 50.9%       |           0.838 |          0.799 |            |

## Table 6 — Quadrants split by sector ETF direction on T+1

> Same caveat as Table 5 — the sector ETF's full-session direction is not known at entry.

| subgroup        | gap      |    n |   n cont |   n rev | Cont. win rate   | Wilson lo   | Wilson hi   |   p (clustered) |   p (binomial) | small n?   |
|:----------------|:---------|-----:|---------:|--------:|:-----------------|:------------|:------------|----------------:|---------------:|:-----------|
| Sector ETF up   | Gap Up   | 4825 |     3054 |    1771 | 63.3%            | 61.9%       | 64.6%       |            0    |          0     |            |
| Sector ETF up   | Gap Down | 4114 |     1489 |    2625 | 36.2%            | 34.7%       | 37.7%       |            0    |          0     |            |
| Sector ETF up   | Both     | 8939 |     4543 |    4396 | 50.8%            | 49.8%       | 51.9%       |            0.18 |          0.123 |            |
| Sector ETF down | Gap Up   | 4199 |     1432 |    2767 | 34.1%            | 32.7%       | 35.6%       |            0    |          0     |            |
| Sector ETF down | Gap Down | 4016 |     2720 |    1296 | 67.7%            | 66.3%       | 69.2%       |            0    |          0     |            |
| Sector ETF down | Both     | 8215 |     4152 |    4063 | 50.5%            | 49.5%       | 51.6%       |            0.41 |          0.332 |            |

## Table 7 — Quadrants split by Minervini Stage (Stage 2 vs Stage 3+4)

Stage is evaluated on the session *before* the event, so unlike Tables 5 and 6 this split is genuinely knowable in advance.

| subgroup   | gap      |    n |   n cont |   n rev | Cont. win rate   | Wilson lo   | Wilson hi   |   p (clustered) |   p (binomial) | small n?   |
|:-----------|:---------|-----:|---------:|--------:|:-----------------|:------------|:------------|----------------:|---------------:|:-----------|
| Stage 2    | Gap Up   | 4535 |     2167 |    2368 | 47.8%            | 46.3%       | 49.2%       |           0.021 |          0.003 |            |
| Stage 2    | Gap Down | 3879 |     2073 |    1806 | 53.4%            | 51.9%       | 55.0%       |           0.003 |          0     |            |
| Stage 2    | Both     | 8414 |     4240 |    4174 | 50.4%            | 49.3%       | 51.5%       |           0.523 |          0.479 |            |
| Stage 3+4  | Gap Up   | 4541 |     2335 |    2206 | 51.4%            | 50.0%       | 52.9%       |           0.16  |          0.057 |            |
| Stage 3+4  | Gap Down | 4289 |     2154 |    2135 | 50.2%            | 48.7%       | 51.7%       |           0.837 |          0.783 |            |
| Stage 3+4  | Both     | 8830 |     4489 |    4341 | 50.8%            | 49.8%       | 51.9%       |           0.191 |          0.118 |            |

## Table 8 — Gap Up versus Gap Down, side by side

Every table above already reports Gap Up and Gap Down rows separately; this section isolates them so asymmetry is easy to read.

### 8a — by 4-pattern system

| subgroup               | gap      |    n |   n cont |   n rev | Cont. win rate   | Wilson lo   | Wilson hi   |   p (clustered) |   p (binomial) | small n?   |
|:-----------------------|:---------|-----:|---------:|--------:|:-----------------|:------------|:------------|----------------:|---------------:|:-----------|
| Strong Continuation+   | Gap Up   |  789 |      671 |     118 | 85.0%            | 82.4%       | 87.4%       |               0 |              0 |            |
| Strong Continuation+   | Gap Down |  702 |      592 |     110 | 84.3%            | 81.5%       | 86.8%       |               0 |              0 |            |
| Moderate Continuation+ | Gap Up   | 1351 |     1018 |     333 | 75.4%            | 73.0%       | 77.6%       |               0 |              0 |            |
| Moderate Continuation+ | Gap Down | 1300 |     1025 |     275 | 78.8%            | 76.5%       | 81.0%       |               0 |              0 |            |
| Indecision0            | Gap Up   | 1926 |     1092 |     834 | 56.7%            | 54.5%       | 58.9%       |               0 |              0 |            |
| Indecision0            | Gap Down | 1791 |     1006 |     785 | 56.2%            | 53.9%       | 58.5%       |               0 |              0 |            |
| Early Reversal-        | Gap Up   | 4492 |     1584 |    2908 | 35.3%            | 33.9%       | 36.7%       |               0 |              0 |            |
| Early Reversal-        | Gap Down | 3941 |     1499 |    2442 | 38.0%            | 36.5%       | 39.6%       |               0 |              0 |            |

### 8b — by simple online-style pattern

| subgroup                           | gap      |    n |   n cont |   n rev | Cont. win rate   | Wilson lo   | Wilson hi   |   p (clustered) |   p (binomial) | small n?   |
|:-----------------------------------|:---------|-----:|---------:|--------:|:-----------------|:------------|:------------|----------------:|---------------:|:-----------|
| Continuation (1st candle with gap) | Gap Up   | 3843 |     2691 |    1152 | 70.0%            | 68.6%       | 71.5%       |           0     |          0     |            |
| Continuation (1st candle with gap) | Gap Down | 3471 |     2496 |     975 | 71.9%            | 70.4%       | 73.4%       |           0     |          0     |            |
| Reversal (1st candle against gap)  | Gap Up   | 4109 |     1334 |    2775 | 32.5%            | 31.1%       | 33.9%       |           0     |          0     |            |
| Reversal (1st candle against gap)  | Gap Down | 3709 |     1293 |    2416 | 34.9%            | 33.3%       | 36.4%       |           0     |          0     |            |
| Doji (1st candle)                  | Gap Up   |  770 |      399 |     371 | 51.8%            | 48.3%       | 55.3%       |           0.345 |          0.331 |            |
| Doji (1st candle)                  | Gap Down |  687 |      374 |     313 | 54.4%            | 50.7%       | 58.1%       |           0.031 |          0.022 |            |

### 8c — by Stage

| subgroup   | gap      |    n |   n cont |   n rev | Cont. win rate   | Wilson lo   | Wilson hi   |   p (clustered) |   p (binomial) | small n?   |
|:-----------|:---------|-----:|---------:|--------:|:-----------------|:------------|:------------|----------------:|---------------:|:-----------|
| Stage 2    | Gap Up   | 4535 |     2167 |    2368 | 47.8%            | 46.3%       | 49.2%       |           0.021 |          0.003 |            |
| Stage 2    | Gap Down | 3879 |     2073 |    1806 | 53.4%            | 51.9%       | 55.0%       |           0.003 |          0     |            |
| Stage 3+4  | Gap Up   | 4541 |     2335 |    2206 | 51.4%            | 50.0%       | 52.9%       |           0.16  |          0.057 |            |
| Stage 3+4  | Gap Down | 4289 |     2154 |    2135 | 50.2%            | 48.7%       | 51.7%       |           0.837 |          0.783 |            |

## Table 9 — Highest-win-rate combinations (pattern + Stage + SPY)

All combinations, sorted by win rate. Treat the top rows with suspicion: this is a search over many cells, and the SPY term is not knowable at entry (see Table 5).

| subgroup                            | gap   |    n |   n cont |   n rev | Cont. win rate   | Wilson lo   | Wilson hi   |   p (clustered) |   p (binomial) | small n?   |
|:------------------------------------|:------|-----:|---------:|--------:|:-----------------|:------------|:------------|----------------:|---------------:|:-----------|
| Continuation | Stage 2 | SPY up     | Both  | 1861 |     1332 |     529 | 71.6%            | 69.5%       | 73.6%       |           0     |          0     |            |
| Continuation | Stage 3+4 | SPY down | Both  | 1716 |     1222 |     494 | 71.2%            | 69.0%       | 73.3%       |           0     |          0     |            |
| Continuation | Stage 3+4 | SPY up   | Both  | 2017 |     1428 |     589 | 70.8%            | 68.8%       | 72.7%       |           0     |          0     |            |
| Continuation | Stage 2 | SPY down   | Both  | 1660 |     1157 |     503 | 69.7%            | 67.4%       | 71.9%       |           0     |          0     |            |
| Doji | Stage 2 | SPY up             | Both  |  352 |      199 |     153 | 56.5%            | 51.3%       | 61.6%       |           0.022 |          0.016 |            |
| Doji | Stage 3+4 | SPY up           | Both  |  424 |      229 |     195 | 54.0%            | 49.3%       | 58.7%       |           0.098 |          0.109 |            |
| Doji | Stage 2 | SPY down           | Both  |  342 |      176 |     166 | 51.5%            | 46.2%       | 56.7%       |           0.61  |          0.627 |            |
| Doji | Stage 3+4 | SPY down         | Both  |  327 |      164 |     163 | 50.2%            | 44.8%       | 55.5%       |           0.956 |          1     |            |
| Reversal | Stage 3+4 | SPY up       | Both  | 2091 |      720 |    1371 | 34.4%            | 32.4%       | 36.5%       |           0     |          0     |            |
| Reversal | Stage 2 | SPY down       | Both  | 1872 |      629 |    1243 | 33.6%            | 31.5%       | 35.8%       |           0     |          0     |            |
| Reversal | Stage 2 | SPY up         | Both  | 1946 |      648 |    1298 | 33.3%            | 31.2%       | 35.4%       |           0     |          0     |            |
| Reversal | Stage 3+4 | SPY down     | Both  | 1835 |      601 |    1234 | 32.8%            | 30.6%       | 34.9%       |           0     |          0     |            |

Lowest:

| subgroup                        | gap   |    n |   n cont |   n rev | Cont. win rate   | Wilson lo   | Wilson hi   |   p (clustered) |   p (binomial) | small n?   |
|:--------------------------------|:------|-----:|---------:|--------:|:-----------------|:------------|:------------|----------------:|---------------:|:-----------|
| Doji | Stage 2 | SPY down       | Both  |  342 |      176 |     166 | 51.5%            | 46.2%       | 56.7%       |           0.61  |          0.627 |            |
| Doji | Stage 3+4 | SPY down     | Both  |  327 |      164 |     163 | 50.2%            | 44.8%       | 55.5%       |           0.956 |          1     |            |
| Reversal | Stage 3+4 | SPY up   | Both  | 2091 |      720 |    1371 | 34.4%            | 32.4%       | 36.5%       |           0     |          0     |            |
| Reversal | Stage 2 | SPY down   | Both  | 1872 |      629 |    1243 | 33.6%            | 31.5%       | 35.8%       |           0     |          0     |            |
| Reversal | Stage 2 | SPY up     | Both  | 1946 |      648 |    1298 | 33.3%            | 31.2%       | 35.4%       |           0     |          0     |            |
| Reversal | Stage 3+4 | SPY down | Both  | 1835 |      601 |    1234 | 32.8%            | 30.6%       | 34.9%       |           0     |          0     |            |

---

## Summary

**Baseline.** Across all 17,397 usable events the continuation win rate is **50.7%** (Wilson 49.9-51.4%, clustered p = 0.158). That is the number every split below has to beat to mean anything.

### 1. Which pattern system separates better?

On the overlapping full-day basis the 4-pattern system separates far more widely — a **48.1 point** spread between Strong Continuation+ and Early Reversal−, against **37.3 points** for the simple first-candle split. But most of that is the overlap artefact, and it flatters the system that uses more of the scored window (three candles rather than one).

On the clean 09:45→Close basis, where neither system can score itself, the spreads collapse to **1.4 points** (4-pattern) and **2.5 points** (simple). The simple one-candle system separates at least as well as the more elaborate one. Either way the honest separation is a small fraction of the headline version.

### 2. Is Gap Up different from Gap Down?

Yes, and it is the most robust asymmetry in this report. Gap Down events continue **51.8%** of the time (n = 8,240, clustered p = 0.024), while Gap Up events continue only **49.6%** (n = 9,157, clustered p = 0.603). Gap downs tend to keep falling; gap ups are closer to a coin flip, if anything slightly mean-reverting. Any rule applied symmetrically to both sides is averaging two different behaviours.

### 3. Which combination gives the highest win rate?

The highest cell with n >= 100 is **Continuation | Stage 2 | SPY up** at **71.6%** (n = 1,861). Two warnings attach to it: the SPY term is only known at the close, so this combination cannot be traded as stated; and it is the best of 12 cells searched, which is exactly the setting where the top of a leaderboard is mostly selection.

The combinations that are genuinely knowable in advance — pattern plus Stage, with no SPY or sector term — are the only ones worth carrying forward, and those sit far closer to the baseline.

---

_Reproducible from `lambda_strategy_validation/winrate_report.py`; every table is also written to `lambda_data/tables/winrate_*.csv`._