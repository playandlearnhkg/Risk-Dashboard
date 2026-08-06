# Lambda Tradeable Win-Rate Report

**Continuation probability only, under strict no-look-ahead rules, including the ICT midday window.**

## How each rule is enforced

| Rule | Enforcement in code |
|---|---|
| 1. Pattern known at 09:45 | Both systems read only the three 5-minute candles covering 09:30-09:45. Nothing later touches the label. |
| 2. Measurement starts at 09:45 | Entry price is `m14`, the close of the 09:44 bar — the price at 09:45:00, and identical to `c3_close`, the close of the third candle. The 09:30-09:45 window is never inside a measured return. |
| 3. SPY / sector from Open to 09:45 only | Benchmark move = `benchmark 09:45 price / benchmark session open - 1`. The 16:00 close is never referenced. |
| 4. Stage from the prior session | `stage_prev`, evaluated on the session before the event. |

**This is the difference that matters.** In the earlier report the benchmark filter used SPY's full-day open-to-close return, which is only known at 16:00 — and since continuation was defined by the sign of the stock's own full-day return, that filter was partly reading its own answer. Everything below uses only information visible on the screen at 09:45.

### Definitions

- **Gap Up / Gap Down** — Open_T+1 versus Prior Close.
- **Continuation** — from 09:45 to the endpoint, the stock moves in the same direction as the original gap.
- **SPY Agree** — SPY's Open→09:45 move has the same sign as the stock's gap. **Disagree** — opposite sign.
- **Sector Agree / Disagree** — same rule against the stock's sector ETF.

Sample: **17,458** events with a non-zero gap and usable intraday data. SPY direction is available for 17,215 of them and sector direction for 16,861. Cells with n < 150 are flagged. Sessions whose move over a given window is exactly zero are excluded from that window:

| Window | Used | Flat, excluded |
|---|---:|---:|
| 09:45 -> 10:00 | 17,241 | 217 |
| 09:45 -> 10:30 | 17,316 | 142 |
| 09:45 -> 11:00 | 17,346 | 112 |
| 09:45 -> 12:00 | 17,363 | 95 |
| 09:45 -> 13:00 | 17,371 | 87 |
| 09:45 -> Close | 17,392 | 66 |

All p-values are two-sided against a 50% null from a **date-clustered bootstrap** (resampling whole trading dates), because events cluster on earnings evenings and an independence assumption would overstate significance.

---

## Window comparison first — the headline

Overall continuation from 09:45 to each endpoint, before any split:

| Window         | Gap      |     n |   n cont | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:---------------|:---------|------:|---------:|:-----------|:------------|:------------|----------------:|:---------|
| 09:45 -> 10:00 | Gap Up   |  9080 |     4571 | 50.3%      | 49.3%       | 51.4%       |           0.579 |          |
| 09:45 -> 10:00 | Gap Down |  8161 |     4221 | 51.7%      | 50.6%       | 52.8%       |           0.014 |          |
| 09:45 -> 10:00 | Both     | 17241 |     8792 | 51.0%      | 50.2%       | 51.7%       |           0.016 |          |
| 09:45 -> 10:30 | Gap Up   |  9115 |     4582 | 50.3%      | 49.2%       | 51.3%       |           0.7   |          |
| 09:45 -> 10:30 | Gap Down |  8201 |     4274 | 52.1%      | 51.0%       | 53.2%       |           0.007 |          |
| 09:45 -> 10:30 | Both     | 17316 |     8856 | 51.1%      | 50.4%       | 51.9%       |           0.007 |          |
| 09:45 -> 11:00 | Gap Up   |  9131 |     4550 | 49.8%      | 48.8%       | 50.9%       |           0.794 |          |
| 09:45 -> 11:00 | Gap Down |  8215 |     4252 | 51.8%      | 50.7%       | 52.8%       |           0.031 |          |
| 09:45 -> 11:00 | Both     | 17346 |     8802 | 50.7%      | 50.0%       | 51.5%       |           0.074 |          |
| 09:45 -> 12:00 | Gap Up   |  9141 |     4567 | 50.0%      | 48.9%       | 51.0%       |           0.956 |          |
| 09:45 -> 12:00 | Gap Down |  8222 |     4176 | 50.8%      | 49.7%       | 51.9%       |           0.295 |          |
| 09:45 -> 12:00 | Both     | 17363 |     8743 | 50.4%      | 49.6%       | 51.1%       |           0.427 |          |
| 09:45 -> 13:00 | Gap Up   |  9149 |     4614 | 50.4%      | 49.4%       | 51.5%       |           0.563 |          |
| 09:45 -> 13:00 | Gap Down |  8222 |     4154 | 50.5%      | 49.4%       | 51.6%       |           0.508 |          |
| 09:45 -> 13:00 | Both     | 17371 |     8768 | 50.5%      | 49.7%       | 51.2%       |           0.282 |          |
| 09:45 -> Close | Gap Up   |  9154 |     4543 | 49.6%      | 48.6%       | 50.7%       |           0.619 |          |
| 09:45 -> Close | Gap Down |  8238 |     4125 | 50.1%      | 49.0%       | 51.2%       |           0.91  |          |
| 09:45 -> Close | Both     | 17392 |     8668 | 49.8%      | 49.1%       | 50.6%       |           0.72  |          |

## Window 1: 09:45 -> 10:00

### Table 1 — Overall by gap direction

| Subgroup   | Gap      |     n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-----------|:---------|------:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| All events | Gap Up   |  9080 |     4571 |    4509 | 50.3%      | 49.3%       | 51.4%       |           0.579 |          |
| All events | Gap Down |  8161 |     4221 |    3940 | 51.7%      | 50.6%       | 52.8%       |           0.014 |          |
| All events | Both     | 17241 |     8792 |    8449 | 51.0%      | 50.2%       | 51.7%       |           0.016 |          |

### Table 2 — Split by the 4-pattern system

| Subgroup               | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-----------------------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| Strong Continuation+   | Gap Up   |  782 |      420 |     362 | 53.7%      | 50.2%       | 57.2%       |           0.046 |          |
| Strong Continuation+   | Gap Down |  688 |      364 |     324 | 52.9%      | 49.2%       | 56.6%       |           0.148 |          |
| Strong Continuation+   | Both     | 1470 |      784 |     686 | 53.3%      | 50.8%       | 55.9%       |           0.015 |          |
| Moderate Continuation+ | Gap Up   | 1338 |      721 |     617 | 53.9%      | 51.2%       | 56.5%       |           0.011 |          |
| Moderate Continuation+ | Gap Down | 1286 |      687 |     599 | 53.4%      | 50.7%       | 56.1%       |           0.008 |          |
| Moderate Continuation+ | Both     | 2624 |     1408 |    1216 | 53.7%      | 51.7%       | 55.6%       |           0.001 |          |
| Indecision0            | Gap Up   | 1911 |     1040 |     871 | 54.4%      | 52.2%       | 56.6%       |           0     |          |
| Indecision0            | Gap Down | 1780 |      978 |     802 | 54.9%      | 52.6%       | 57.2%       |           0     |          |
| Indecision0            | Both     | 3691 |     2018 |    1673 | 54.7%      | 53.1%       | 56.3%       |           0     |          |
| Early Reversal-        | Gap Up   | 4455 |     2227 |    2228 | 50.0%      | 48.5%       | 51.5%       |           0.992 |          |
| Early Reversal-        | Gap Down | 3905 |     2003 |    1902 | 51.3%      | 49.7%       | 52.9%       |           0.139 |          |
| Early Reversal-        | Both     | 8360 |     4230 |    4130 | 50.6%      | 49.5%       | 51.7%       |           0.294 |          |

### Table 3 — Split by the simple first-candle system

| Subgroup                           | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-----------------------------------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| Continuation (1st candle with gap) | Gap Up   | 3813 |     2072 |    1741 | 54.3%      | 52.8%       | 55.9%       |           0     |          |
| Continuation (1st candle with gap) | Gap Down | 3442 |     1887 |    1555 | 54.8%      | 53.2%       | 56.5%       |           0     |          |
| Continuation (1st candle with gap) | Both     | 7255 |     3959 |    3296 | 54.6%      | 53.4%       | 55.7%       |           0     |          |
| Reversal (1st candle against gap)  | Gap Up   | 4075 |     2004 |    2071 | 49.2%      | 47.6%       | 50.7%       |           0.35  |          |
| Reversal (1st candle against gap)  | Gap Down | 3667 |     1850 |    1817 | 50.4%      | 48.8%       | 52.1%       |           0.614 |          |
| Reversal (1st candle against gap)  | Both     | 7742 |     3854 |    3888 | 49.8%      | 48.7%       | 50.9%       |           0.704 |          |
| Doji (1st candle)                  | Gap Up   |  763 |      382 |     381 | 50.1%      | 46.5%       | 53.6%       |           0.966 |          |
| Doji (1st candle)                  | Gap Down |  682 |      348 |     334 | 51.0%      | 47.3%       | 54.8%       |           0.588 |          |
| Doji (1st candle)                  | Both     | 1445 |      730 |     715 | 50.5%      | 47.9%       | 53.1%       |           0.708 |          |

### Table 4 — Split by SPY Agree / Disagree (Open→09:45)

| Subgroup     | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-------------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| SPY Agree    | Gap Up   | 4219 |     2151 |    2068 | 51.0%      | 49.5%       | 52.5%       |           0.299 |          |
| SPY Agree    | Gap Down | 4115 |     2103 |    2012 | 51.1%      | 49.6%       | 52.6%       |           0.239 |          |
| SPY Agree    | Both     | 8334 |     4254 |    4080 | 51.0%      | 50.0%       | 52.1%       |           0.125 |          |
| SPY Disagree | Gap Up   | 4737 |     2361 |    2376 | 49.8%      | 48.4%       | 51.3%       |           0.852 |          |
| SPY Disagree | Gap Down | 3931 |     2058 |    1873 | 52.4%      | 50.8%       | 53.9%       |           0.016 |          |
| SPY Disagree | Both     | 8668 |     4419 |    4249 | 51.0%      | 49.9%       | 52.0%       |           0.177 |          |

### Table 5 — Split by Sector Agree / Disagree (Open→09:45)

| Subgroup        | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:----------------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| Sector Agree    | Gap Up   | 4502 |     2282 |    2220 | 50.7%      | 49.2%       | 52.1%       |           0.454 |          |
| Sector Agree    | Gap Down | 4047 |     2104 |    1943 | 52.0%      | 50.4%       | 53.5%       |           0.028 |          |
| Sector Agree    | Both     | 8549 |     4386 |    4163 | 51.3%      | 50.2%       | 52.4%       |           0.033 |          |
| Sector Disagree | Gap Up   | 4265 |     2132 |    2133 | 50.0%      | 48.5%       | 51.5%       |           0.992 |          |
| Sector Disagree | Gap Down | 3839 |     1971 |    1868 | 51.3%      | 49.8%       | 52.9%       |           0.167 |          |
| Sector Disagree | Both     | 8104 |     4103 |    4001 | 50.6%      | 49.5%       | 51.7%       |           0.317 |          |

### Table 6 — Split by Stage

| Subgroup   | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-----------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| Stage 2    | Gap Up   | 4500 |     2187 |    2313 | 48.6%      | 47.1%       | 50.1%       |           0.13  |          |
| Stage 2    | Gap Down | 3840 |     2036 |    1804 | 53.0%      | 51.4%       | 54.6%       |           0.001 |          |
| Stage 2    | Both     | 8340 |     4223 |    4117 | 50.6%      | 49.6%       | 51.7%       |           0.292 |          |
| Stage 3+4  | Gap Up   | 4500 |     2340 |    2160 | 52.0%      | 50.5%       | 53.5%       |           0.023 |          |
| Stage 3+4  | Gap Down | 4251 |     2148 |    2103 | 50.5%      | 49.0%       | 52.0%       |           0.604 |          |
| Stage 3+4  | Both     | 8751 |     4488 |    4263 | 51.3%      | 50.2%       | 52.3%       |           0.03  |          |

## Window 2: 09:45 -> 10:30

### Table 1 — Overall by gap direction

| Subgroup   | Gap      |     n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-----------|:---------|------:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| All events | Gap Up   |  9115 |     4582 |    4533 | 50.3%      | 49.2%       | 51.3%       |           0.7   |          |
| All events | Gap Down |  8201 |     4274 |    3927 | 52.1%      | 51.0%       | 53.2%       |           0.007 |          |
| All events | Both     | 17316 |     8856 |    8460 | 51.1%      | 50.4%       | 51.9%       |           0.007 |          |

### Table 2 — Split by the 4-pattern system

| Subgroup               | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-----------------------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| Strong Continuation+   | Gap Up   |  783 |      420 |     363 | 53.6%      | 50.1%       | 57.1%       |           0.055 |          |
| Strong Continuation+   | Gap Down |  701 |      376 |     325 | 53.6%      | 49.9%       | 57.3%       |           0.083 |          |
| Strong Continuation+   | Both     | 1484 |      796 |     688 | 53.6%      | 51.1%       | 56.2%       |           0.008 |          |
| Moderate Continuation+ | Gap Up   | 1340 |      707 |     633 | 52.8%      | 50.1%       | 55.4%       |           0.048 |          |
| Moderate Continuation+ | Gap Down | 1285 |      681 |     604 | 53.0%      | 50.3%       | 55.7%       |           0.047 |          |
| Moderate Continuation+ | Both     | 2625 |     1388 |    1237 | 52.9%      | 51.0%       | 54.8%       |           0.009 |          |
| Indecision0            | Gap Up   | 1918 |     1048 |     870 | 54.6%      | 52.4%       | 56.9%       |           0     |          |
| Indecision0            | Gap Down | 1784 |      989 |     795 | 55.4%      | 53.1%       | 57.7%       |           0     |          |
| Indecision0            | Both     | 3702 |     2037 |    1665 | 55.0%      | 53.4%       | 56.6%       |           0     |          |
| Early Reversal-        | Gap Up   | 4477 |     2198 |    2279 | 49.1%      | 47.6%       | 50.6%       |           0.329 |          |
| Early Reversal-        | Gap Down | 3926 |     2020 |    1906 | 51.5%      | 49.9%       | 53.0%       |           0.118 |          |
| Early Reversal-        | Both     | 8403 |     4218 |    4185 | 50.2%      | 49.1%       | 51.3%       |           0.723 |          |

### Table 3 — Split by the simple first-candle system

| Subgroup                           | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-----------------------------------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| Continuation (1st candle with gap) | Gap Up   | 3819 |     2036 |    1783 | 53.3%      | 51.7%       | 54.9%       |           0     |          |
| Continuation (1st candle with gap) | Gap Down | 3453 |     1892 |    1561 | 54.8%      | 53.1%       | 56.4%       |           0     |          |
| Continuation (1st candle with gap) | Both     | 7272 |     3928 |    3344 | 54.0%      | 52.9%       | 55.2%       |           0     |          |
| Reversal (1st candle against gap)  | Gap Up   | 4094 |     1983 |    2111 | 48.4%      | 46.9%       | 50.0%       |           0.087 |          |
| Reversal (1st candle against gap)  | Gap Down | 3687 |     1863 |    1824 | 50.5%      | 48.9%       | 52.1%       |           0.575 |          |
| Reversal (1st candle against gap)  | Both     | 7781 |     3846 |    3935 | 49.4%      | 48.3%       | 50.5%       |           0.335 |          |
| Doji (1st candle)                  | Gap Up   |  769 |      413 |     356 | 53.7%      | 50.2%       | 57.2%       |           0.041 |          |
| Doji (1st candle)                  | Gap Down |  688 |      363 |     325 | 52.8%      | 49.0%       | 56.5%       |           0.171 |          |
| Doji (1st candle)                  | Both     | 1457 |      776 |     681 | 53.3%      | 50.7%       | 55.8%       |           0.008 |          |

### Table 4 — Split by SPY Agree / Disagree (Open→09:45)

| Subgroup     | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-------------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| SPY Agree    | Gap Up   | 4235 |     2162 |    2073 | 51.1%      | 49.5%       | 52.6%       |           0.259 |          |
| SPY Agree    | Gap Down | 4138 |     2171 |    1967 | 52.5%      | 50.9%       | 54.0%       |           0.022 |          |
| SPY Agree    | Both     | 8373 |     4333 |    4040 | 51.7%      | 50.7%       | 52.8%       |           0.016 |          |
| SPY Disagree | Gap Up   | 4755 |     2365 |    2390 | 49.7%      | 48.3%       | 51.2%       |           0.773 |          |
| SPY Disagree | Gap Down | 3948 |     2061 |    1887 | 52.2%      | 50.6%       | 53.8%       |           0.045 |          |
| SPY Disagree | Both     | 8703 |     4426 |    4277 | 50.9%      | 49.8%       | 51.9%       |           0.234 |          |

### Table 5 — Split by Sector Agree / Disagree (Open→09:45)

| Subgroup        | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:----------------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| Sector Agree    | Gap Up   | 4511 |     2264 |    2247 | 50.2%      | 48.7%       | 51.6%       |           0.807 |          |
| Sector Agree    | Gap Down | 4064 |     2134 |    1930 | 52.5%      | 51.0%       | 54.0%       |           0.009 |          |
| Sector Agree    | Both     | 8575 |     4398 |    4177 | 51.3%      | 50.2%       | 52.3%       |           0.056 |          |
| Sector Disagree | Gap Up   | 4292 |     2156 |    2136 | 50.2%      | 48.7%       | 51.7%       |           0.814 |          |
| Sector Disagree | Gap Down | 3857 |     1997 |    1860 | 51.8%      | 50.2%       | 53.4%       |           0.066 |          |
| Sector Disagree | Both     | 8149 |     4153 |    3996 | 51.0%      | 49.9%       | 52.0%       |           0.145 |          |

### Table 6 — Split by Stage

| Subgroup   | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-----------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| Stage 2    | Gap Up   | 4521 |     2216 |    2305 | 49.0%      | 47.6%       | 50.5%       |           0.26  |          |
| Stage 2    | Gap Down | 3849 |     2047 |    1802 | 53.2%      | 51.6%       | 54.8%       |           0.001 |          |
| Stage 2    | Both     | 8370 |     4263 |    4107 | 50.9%      | 49.9%       | 52.0%       |           0.102 |          |
| Stage 3+4  | Gap Up   | 4515 |     2323 |    2192 | 51.5%      | 50.0%       | 52.9%       |           0.123 |          |
| Stage 3+4  | Gap Down | 4280 |     2194 |    2086 | 51.3%      | 49.8%       | 52.8%       |           0.247 |          |
| Stage 3+4  | Both     | 8795 |     4517 |    4278 | 51.4%      | 50.3%       | 52.4%       |           0.018 |          |

## Window 3: 09:45 -> 11:00

### Table 1 — Overall by gap direction

| Subgroup   | Gap      |     n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-----------|:---------|------:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| All events | Gap Up   |  9131 |     4550 |    4581 | 49.8%      | 48.8%       | 50.9%       |           0.794 |          |
| All events | Gap Down |  8215 |     4252 |    3963 | 51.8%      | 50.7%       | 52.8%       |           0.031 |          |
| All events | Both     | 17346 |     8802 |    8544 | 50.7%      | 50.0%       | 51.5%       |           0.074 |          |

### Table 2 — Split by the 4-pattern system

| Subgroup               | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-----------------------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| Strong Continuation+   | Gap Up   |  785 |      407 |     378 | 51.8%      | 48.4%       | 55.3%       |           0.34  |          |
| Strong Continuation+   | Gap Down |  702 |      378 |     324 | 53.8%      | 50.1%       | 57.5%       |           0.045 |          |
| Strong Continuation+   | Both     | 1487 |      785 |     702 | 52.8%      | 50.2%       | 55.3%       |           0.034 |          |
| Moderate Continuation+ | Gap Up   | 1345 |      684 |     661 | 50.9%      | 48.2%       | 53.5%       |           0.551 |          |
| Moderate Continuation+ | Gap Down | 1294 |      677 |     617 | 52.3%      | 49.6%       | 55.0%       |           0.128 |          |
| Moderate Continuation+ | Both     | 2639 |     1361 |    1278 | 51.6%      | 49.7%       | 53.5%       |           0.115 |          |
| Indecision0            | Gap Up   | 1919 |     1043 |     876 | 54.4%      | 52.1%       | 56.6%       |           0.001 |          |
| Indecision0            | Gap Down | 1788 |      979 |     809 | 54.8%      | 52.4%       | 57.0%       |           0     |          |
| Indecision0            | Both     | 3707 |     2022 |    1685 | 54.5%      | 52.9%       | 56.1%       |           0     |          |
| Early Reversal-        | Gap Up   | 4487 |     2186 |    2301 | 48.7%      | 47.3%       | 50.2%       |           0.134 |          |
| Early Reversal-        | Gap Down | 3926 |     2008 |    1918 | 51.1%      | 49.6%       | 52.7%       |           0.23  |          |
| Early Reversal-        | Both     | 8413 |     4194 |    4219 | 49.9%      | 48.8%       | 50.9%       |           0.814 |          |

### Table 3 — Split by the simple first-candle system

| Subgroup                           | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-----------------------------------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| Continuation (1st candle with gap) | Gap Up   | 3832 |     2023 |    1809 | 52.8%      | 51.2%       | 54.4%       |           0.001 |          |
| Continuation (1st candle with gap) | Gap Down | 3463 |     1875 |    1588 | 54.1%      | 52.5%       | 55.8%       |           0.001 |          |
| Continuation (1st candle with gap) | Both     | 7295 |     3898 |    3397 | 53.4%      | 52.3%       | 54.6%       |           0     |          |
| Reversal (1st candle against gap)  | Gap Up   | 4094 |     1949 |    2145 | 47.6%      | 46.1%       | 49.1%       |           0.009 |          |
| Reversal (1st candle against gap)  | Gap Down | 3693 |     1860 |    1833 | 50.4%      | 48.8%       | 52.0%       |           0.727 |          |
| Reversal (1st candle against gap)  | Both     | 7787 |     3809 |    3978 | 48.9%      | 47.8%       | 50.0%       |           0.05  |          |
| Doji (1st candle)                  | Gap Up   |  774 |      409 |     365 | 52.8%      | 49.3%       | 56.3%       |           0.108 |          |
| Doji (1st candle)                  | Gap Down |  687 |      362 |     325 | 52.7%      | 49.0%       | 56.4%       |           0.181 |          |
| Doji (1st candle)                  | Both     | 1461 |      771 |     690 | 52.8%      | 50.2%       | 55.3%       |           0.03  |          |

### Table 4 — Split by SPY Agree / Disagree (Open→09:45)

| Subgroup     | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-------------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| SPY Agree    | Gap Up   | 4249 |     2166 |    2083 | 51.0%      | 49.5%       | 52.5%       |           0.302 |          |
| SPY Agree    | Gap Down | 4141 |     2153 |    1988 | 52.0%      | 50.5%       | 53.5%       |           0.052 |          |
| SPY Agree    | Both     | 8390 |     4319 |    4071 | 51.5%      | 50.4%       | 52.5%       |           0.045 |          |
| SPY Disagree | Gap Up   | 4759 |     2330 |    2429 | 49.0%      | 47.5%       | 50.4%       |           0.254 |          |
| SPY Disagree | Gap Down | 3956 |     2056 |    1900 | 52.0%      | 50.4%       | 53.5%       |           0.09  |          |
| SPY Disagree | Both     | 8715 |     4386 |    4329 | 50.3%      | 49.3%       | 51.4%       |           0.632 |          |

### Table 5 — Split by Sector Agree / Disagree (Open→09:45)

| Subgroup        | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:----------------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| Sector Agree    | Gap Up   | 4524 |     2235 |    2289 | 49.4%      | 47.9%       | 50.9%       |           0.486 |          |
| Sector Agree    | Gap Down | 4075 |     2098 |    1977 | 51.5%      | 49.9%       | 53.0%       |           0.134 |          |
| Sector Agree    | Both     | 8599 |     4333 |    4266 | 50.4%      | 49.3%       | 51.4%       |           0.521 |          |
| Sector Disagree | Gap Up   | 4294 |     2151 |    2143 | 50.1%      | 48.6%       | 51.6%       |           0.924 |          |
| Sector Disagree | Gap Down | 3862 |     2003 |    1859 | 51.9%      | 50.3%       | 53.4%       |           0.089 |          |
| Sector Disagree | Both     | 8156 |     4154 |    4002 | 50.9%      | 49.8%       | 52.0%       |           0.165 |          |

### Table 6 — Split by Stage

| Subgroup   | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-----------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| Stage 2    | Gap Up   | 4525 |     2232 |    2293 | 49.3%      | 47.9%       | 50.8%       |           0.464 |          |
| Stage 2    | Gap Down | 3866 |     2031 |    1835 | 52.5%      | 51.0%       | 54.1%       |           0.009 |          |
| Stage 2    | Both     | 8391 |     4263 |    4128 | 50.8%      | 49.7%       | 51.9%       |           0.136 |          |
| Stage 3+4  | Gap Up   | 4526 |     2270 |    2256 | 50.2%      | 48.7%       | 51.6%       |           0.856 |          |
| Stage 3+4  | Gap Down | 4278 |     2187 |    2091 | 51.1%      | 49.6%       | 52.6%       |           0.259 |          |
| Stage 3+4  | Both     | 8804 |     4457 |    4347 | 50.6%      | 49.6%       | 51.7%       |           0.297 |          |

## Window 4: 09:45 -> 12:00

### Table 1 — Overall by gap direction

| Subgroup   | Gap      |     n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-----------|:---------|------:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| All events | Gap Up   |  9141 |     4567 |    4574 | 50.0%      | 48.9%       | 51.0%       |           0.956 |          |
| All events | Gap Down |  8222 |     4176 |    4046 | 50.8%      | 49.7%       | 51.9%       |           0.295 |          |
| All events | Both     | 17363 |     8743 |    8620 | 50.4%      | 49.6%       | 51.1%       |           0.427 |          |

### Table 2 — Split by the 4-pattern system

| Subgroup               | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-----------------------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| Strong Continuation+   | Gap Up   |  788 |      398 |     390 | 50.5%      | 47.0%       | 54.0%       |           0.811 |          |
| Strong Continuation+   | Gap Down |  703 |      373 |     330 | 53.1%      | 49.4%       | 56.7%       |           0.136 |          |
| Strong Continuation+   | Both     | 1491 |      771 |     720 | 51.7%      | 49.2%       | 54.2%       |           0.212 |          |
| Moderate Continuation+ | Gap Up   | 1345 |      713 |     632 | 53.0%      | 50.3%       | 55.7%       |           0.036 |          |
| Moderate Continuation+ | Gap Down | 1287 |      675 |     612 | 52.4%      | 49.7%       | 55.2%       |           0.098 |          |
| Moderate Continuation+ | Both     | 2632 |     1388 |    1244 | 52.7%      | 50.8%       | 54.6%       |           0.006 |          |
| Indecision0            | Gap Up   | 1923 |     1013 |     910 | 52.7%      | 50.4%       | 54.9%       |           0.04  |          |
| Indecision0            | Gap Down | 1791 |      933 |     858 | 52.1%      | 49.8%       | 54.4%       |           0.078 |          |
| Indecision0            | Both     | 3714 |     1946 |    1768 | 52.4%      | 50.8%       | 54.0%       |           0.004 |          |
| Early Reversal-        | Gap Up   | 4487 |     2212 |    2275 | 49.3%      | 47.8%       | 50.8%       |           0.41  |          |
| Early Reversal-        | Gap Down | 3936 |     1979 |    1957 | 50.3%      | 48.7%       | 51.8%       |           0.775 |          |
| Early Reversal-        | Both     | 8423 |     4191 |    4232 | 49.8%      | 48.7%       | 50.8%       |           0.682 |          |

### Table 3 — Split by the simple first-candle system

| Subgroup                           | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-----------------------------------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| Continuation (1st candle with gap) | Gap Up   | 3835 |     1988 |    1847 | 51.8%      | 50.3%       | 53.4%       |           0.06  |          |
| Continuation (1st candle with gap) | Gap Down | 3462 |     1843 |    1619 | 53.2%      | 51.6%       | 54.9%       |           0.001 |          |
| Continuation (1st candle with gap) | Both     | 7297 |     3831 |    3466 | 52.5%      | 51.4%       | 53.6%       |           0.001 |          |
| Reversal (1st candle against gap)  | Gap Up   | 4100 |     2026 |    2074 | 49.4%      | 47.9%       | 50.9%       |           0.55  |          |
| Reversal (1st candle against gap)  | Gap Down | 3697 |     1812 |    1885 | 49.0%      | 47.4%       | 50.6%       |           0.287 |          |
| Reversal (1st candle against gap)  | Both     | 7797 |     3838 |    3959 | 49.2%      | 48.1%       | 50.3%       |           0.191 |          |
| Doji (1st candle)                  | Gap Up   |  772 |      390 |     382 | 50.5%      | 47.0%       | 54.0%       |           0.796 |          |
| Doji (1st candle)                  | Gap Down |  690 |      359 |     331 | 52.0%      | 48.3%       | 55.7%       |           0.338 |          |
| Doji (1st candle)                  | Both     | 1462 |      749 |     713 | 51.2%      | 48.7%       | 53.8%       |           0.351 |          |

### Table 4 — Split by SPY Agree / Disagree (Open→09:45)

| Subgroup     | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-------------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| SPY Agree    | Gap Up   | 4250 |     2197 |    2053 | 51.7%      | 50.2%       | 53.2%       |           0.091 |          |
| SPY Agree    | Gap Down | 4142 |     2131 |    2011 | 51.4%      | 49.9%       | 53.0%       |           0.156 |          |
| SPY Agree    | Both     | 8392 |     4328 |    4064 | 51.6%      | 50.5%       | 52.6%       |           0.024 |          |
| SPY Disagree | Gap Up   | 4767 |     2319 |    2448 | 48.6%      | 47.2%       | 50.1%       |           0.16  |          |
| SPY Disagree | Gap Down | 3962 |     2002 |    1960 | 50.5%      | 49.0%       | 52.1%       |           0.63  |          |
| SPY Disagree | Both     | 8729 |     4321 |    4408 | 49.5%      | 48.5%       | 50.6%       |           0.513 |          |

### Table 5 — Split by Sector Agree / Disagree (Open→09:45)

| Subgroup        | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:----------------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| Sector Agree    | Gap Up   | 4524 |     2287 |    2237 | 50.6%      | 49.1%       | 52.0%       |           0.524 |          |
| Sector Agree    | Gap Down | 4077 |     2056 |    2021 | 50.4%      | 48.9%       | 52.0%       |           0.639 |          |
| Sector Agree    | Both     | 8601 |     4343 |    4258 | 50.5%      | 49.4%       | 51.6%       |           0.43  |          |
| Sector Disagree | Gap Up   | 4304 |     2129 |    2175 | 49.5%      | 48.0%       | 51.0%       |           0.576 |          |
| Sector Disagree | Gap Down | 3864 |     1975 |    1889 | 51.1%      | 49.5%       | 52.7%       |           0.274 |          |
| Sector Disagree | Both     | 8168 |     4104 |    4064 | 50.2%      | 49.2%       | 51.3%       |           0.733 |          |

### Table 6 — Split by Stage

| Subgroup   | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-----------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| Stage 2    | Gap Up   | 4533 |     2217 |    2316 | 48.9%      | 47.5%       | 50.4%       |           0.23  |          |
| Stage 2    | Gap Down | 3870 |     1986 |    1884 | 51.3%      | 49.7%       | 52.9%       |           0.167 |          |
| Stage 2    | Both     | 8403 |     4203 |    4200 | 50.0%      | 48.9%       | 51.1%       |           0.96  |          |
| Stage 3+4  | Gap Up   | 4527 |     2303 |    2224 | 50.9%      | 49.4%       | 52.3%       |           0.367 |          |
| Stage 3+4  | Gap Down | 4281 |     2155 |    2126 | 50.3%      | 48.8%       | 51.8%       |           0.734 |          |
| Stage 3+4  | Both     | 8808 |     4458 |    4350 | 50.6%      | 49.6%       | 51.7%       |           0.326 |          |

## Window 5: 09:45 -> 13:00 — **ICT midday window**

### Table 1 — Overall by gap direction

| Subgroup   | Gap      |     n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-----------|:---------|------:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| All events | Gap Up   |  9149 |     4614 |    4535 | 50.4%      | 49.4%       | 51.5%       |           0.563 |          |
| All events | Gap Down |  8222 |     4154 |    4068 | 50.5%      | 49.4%       | 51.6%       |           0.508 |          |
| All events | Both     | 17371 |     8768 |    8603 | 50.5%      | 49.7%       | 51.2%       |           0.282 |          |

### Table 2 — Split by the 4-pattern system

| Subgroup               | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-----------------------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| Strong Continuation+   | Gap Up   |  786 |      414 |     372 | 52.7%      | 49.2%       | 56.1%       |           0.141 |          |
| Strong Continuation+   | Gap Down |  697 |      360 |     337 | 51.6%      | 47.9%       | 55.3%       |           0.427 |          |
| Strong Continuation+   | Both     | 1483 |      774 |     709 | 52.2%      | 49.6%       | 54.7%       |           0.108 |          |
| Moderate Continuation+ | Gap Up   | 1347 |      712 |     635 | 52.9%      | 50.2%       | 55.5%       |           0.06  |          |
| Moderate Continuation+ | Gap Down | 1292 |      669 |     623 | 51.8%      | 49.1%       | 54.5%       |           0.217 |          |
| Moderate Continuation+ | Both     | 2639 |     1381 |    1258 | 52.3%      | 50.4%       | 54.2%       |           0.014 |          |
| Indecision0            | Gap Up   | 1924 |     1012 |     912 | 52.6%      | 50.4%       | 54.8%       |           0.032 |          |
| Indecision0            | Gap Down | 1785 |      932 |     853 | 52.2%      | 49.9%       | 54.5%       |           0.064 |          |
| Indecision0            | Both     | 3709 |     1944 |    1765 | 52.4%      | 50.8%       | 54.0%       |           0.005 |          |
| Early Reversal-        | Gap Up   | 4491 |     2232 |    2259 | 49.7%      | 48.2%       | 51.2%       |           0.73  |          |
| Early Reversal-        | Gap Down | 3941 |     1968 |    1973 | 49.9%      | 48.4%       | 51.5%       |           0.946 |          |
| Early Reversal-        | Both     | 8432 |     4200 |    4232 | 49.8%      | 48.7%       | 50.9%       |           0.743 |          |

### Table 3 — Split by the simple first-candle system

| Subgroup                           | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-----------------------------------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| Continuation (1st candle with gap) | Gap Up   | 3840 |     2031 |    1809 | 52.9%      | 51.3%       | 54.5%       |           0.004 |          |
| Continuation (1st candle with gap) | Gap Down | 3455 |     1802 |    1653 | 52.2%      | 50.5%       | 53.8%       |           0.035 |          |
| Continuation (1st candle with gap) | Both     | 7295 |     3833 |    3462 | 52.5%      | 51.4%       | 53.7%       |           0     |          |
| Reversal (1st candle against gap)  | Gap Up   | 4101 |     2009 |    2092 | 49.0%      | 47.5%       | 50.5%       |           0.285 |          |
| Reversal (1st candle against gap)  | Gap Down | 3704 |     1823 |    1881 | 49.2%      | 47.6%       | 50.8%       |           0.435 |          |
| Reversal (1st candle against gap)  | Both     | 7805 |     3832 |    3973 | 49.1%      | 48.0%       | 50.2%       |           0.151 |          |
| Doji (1st candle)                  | Gap Up   |  773 |      401 |     372 | 51.9%      | 48.4%       | 55.4%       |           0.324 |          |
| Doji (1st candle)                  | Gap Down |  689 |      359 |     330 | 52.1%      | 48.4%       | 55.8%       |           0.303 |          |
| Doji (1st candle)                  | Both     | 1462 |      760 |     702 | 52.0%      | 49.4%       | 54.5%       |           0.148 |          |

### Table 4 — Split by SPY Agree / Disagree (Open→09:45)

| Subgroup     | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-------------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| SPY Agree    | Gap Up   | 4256 |     2192 |    2064 | 51.5%      | 50.0%       | 53.0%       |           0.173 |          |
| SPY Agree    | Gap Down | 4143 |     2144 |    1999 | 51.7%      | 50.2%       | 53.3%       |           0.081 |          |
| SPY Agree    | Both     | 8399 |     4336 |    4063 | 51.6%      | 50.6%       | 52.7%       |           0.021 |          |
| SPY Disagree | Gap Up   | 4768 |     2365 |    2403 | 49.6%      | 48.2%       | 51.0%       |           0.692 |          |
| SPY Disagree | Gap Down | 3962 |     1972 |    1990 | 49.8%      | 48.2%       | 51.3%       |           0.837 |          |
| SPY Disagree | Both     | 8730 |     4337 |    4393 | 49.7%      | 48.6%       | 50.7%       |           0.648 |          |

### Table 5 — Split by Sector Agree / Disagree (Open→09:45)

| Subgroup        | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:----------------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| Sector Agree    | Gap Up   | 4525 |     2288 |    2237 | 50.6%      | 49.1%       | 52.0%       |           0.575 |          |
| Sector Agree    | Gap Down | 4072 |     2058 |    2014 | 50.5%      | 49.0%       | 52.1%       |           0.593 |          |
| Sector Agree    | Both     | 8597 |     4346 |    4251 | 50.6%      | 49.5%       | 51.6%       |           0.391 |          |
| Sector Disagree | Gap Up   | 4310 |     2175 |    2135 | 50.5%      | 49.0%       | 52.0%       |           0.632 |          |
| Sector Disagree | Gap Down | 3871 |     1954 |    1917 | 50.5%      | 48.9%       | 52.1%       |           0.592 |          |
| Sector Disagree | Both     | 8181 |     4129 |    4052 | 50.5%      | 49.4%       | 51.6%       |           0.502 |          |

### Table 6 — Split by Stage

| Subgroup   | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-----------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| Stage 2    | Gap Up   | 4539 |     2219 |    2320 | 48.9%      | 47.4%       | 50.3%       |           0.236 |          |
| Stage 2    | Gap Down | 3869 |     2009 |    1860 | 51.9%      | 50.4%       | 53.5%       |           0.04  |          |
| Stage 2    | Both     | 8408 |     4228 |    4180 | 50.3%      | 49.2%       | 51.4%       |           0.622 |          |
| Stage 3+4  | Gap Up   | 4530 |     2344 |    2186 | 51.7%      | 50.3%       | 53.2%       |           0.083 |          |
| Stage 3+4  | Gap Down | 4282 |     2107 |    2175 | 49.2%      | 47.7%       | 50.7%       |           0.443 |          |
| Stage 3+4  | Both     | 8812 |     4451 |    4361 | 50.5%      | 49.5%       | 51.6%       |           0.423 |          |

## Window 6: 09:45 -> Close

### Table 1 — Overall by gap direction

| Subgroup   | Gap      |     n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-----------|:---------|------:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| All events | Gap Up   |  9154 |     4543 |    4611 | 49.6%      | 48.6%       | 50.7%       |           0.619 |          |
| All events | Gap Down |  8238 |     4125 |    4113 | 50.1%      | 49.0%       | 51.2%       |           0.91  |          |
| All events | Both     | 17392 |     8668 |    8724 | 49.8%      | 49.1%       | 50.6%       |           0.72  |          |

### Table 2 — Split by the 4-pattern system

| Subgroup               | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-----------------------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| Strong Continuation+   | Gap Up   |  789 |      409 |     380 | 51.8%      | 48.4%       | 55.3%       |           0.322 |          |
| Strong Continuation+   | Gap Down |  705 |      364 |     341 | 51.6%      | 47.9%       | 55.3%       |           0.453 |          |
| Strong Continuation+   | Both     | 1494 |      773 |     721 | 51.7%      | 49.2%       | 54.3%       |           0.193 |          |
| Moderate Continuation+ | Gap Up   | 1344 |      679 |     665 | 50.5%      | 47.9%       | 53.2%       |           0.737 |          |
| Moderate Continuation+ | Gap Down | 1296 |      655 |     641 | 50.5%      | 47.8%       | 53.3%       |           0.727 |          |
| Moderate Continuation+ | Both     | 2640 |     1334 |    1306 | 50.5%      | 48.6%       | 52.4%       |           0.599 |          |
| Indecision0            | Gap Up   | 1923 |     1016 |     907 | 52.8%      | 50.6%       | 55.1%       |           0.031 |          |
| Indecision0            | Gap Down | 1786 |      902 |     884 | 50.5%      | 48.2%       | 52.8%       |           0.668 |          |
| Indecision0            | Both     | 3709 |     1918 |    1791 | 51.7%      | 50.1%       | 53.3%       |           0.056 |          |
| Early Reversal-        | Gap Up   | 4497 |     2202 |    2295 | 49.0%      | 47.5%       | 50.4%       |           0.312 |          |
| Early Reversal-        | Gap Down | 3946 |     1985 |    1961 | 50.3%      | 48.7%       | 51.9%       |           0.75  |          |
| Early Reversal-        | Both     | 8443 |     4187 |    4256 | 49.6%      | 48.5%       | 50.7%       |           0.531 |          |

### Table 3 — Split by the simple first-candle system

| Subgroup                           | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-----------------------------------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| Continuation (1st candle with gap) | Gap Up   | 3838 |     1997 |    1841 | 52.0%      | 50.5%       | 53.6%       |           0.045 |          |
| Continuation (1st candle with gap) | Gap Down | 3468 |     1776 |    1692 | 51.2%      | 49.5%       | 52.9%       |           0.249 |          |
| Continuation (1st candle with gap) | Both     | 7306 |     3773 |    3533 | 51.6%      | 50.5%       | 52.8%       |           0.006 |          |
| Reversal (1st candle against gap)  | Gap Up   | 4108 |     1987 |    2121 | 48.4%      | 46.8%       | 49.9%       |           0.088 |          |
| Reversal (1st candle against gap)  | Gap Down | 3706 |     1829 |    1877 | 49.4%      | 47.7%       | 51.0%       |           0.523 |          |
| Reversal (1st candle against gap)  | Both     | 7814 |     3816 |    3998 | 48.8%      | 47.7%       | 49.9%       |           0.069 |          |
| Doji (1st candle)                  | Gap Up   |  773 |      388 |     385 | 50.2%      | 46.7%       | 53.7%       |           0.901 |          |
| Doji (1st candle)                  | Gap Down |  690 |      351 |     339 | 50.9%      | 47.1%       | 54.6%       |           0.657 |          |
| Doji (1st candle)                  | Both     | 1463 |      739 |     724 | 50.5%      | 48.0%       | 53.1%       |           0.692 |          |

### Table 4 — Split by SPY Agree / Disagree (Open→09:45)

| Subgroup     | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-------------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| SPY Agree    | Gap Up   | 4257 |     2154 |    2103 | 50.6%      | 49.1%       | 52.1%       |           0.572 |          |
| SPY Agree    | Gap Down | 4153 |     2148 |    2005 | 51.7%      | 50.2%       | 53.2%       |           0.129 |          |
| SPY Agree    | Both     | 8410 |     4302 |    4108 | 51.2%      | 50.1%       | 52.2%       |           0.166 |          |
| SPY Disagree | Gap Up   | 4773 |     2342 |    2431 | 49.1%      | 47.7%       | 50.5%       |           0.385 |          |
| SPY Disagree | Gap Down | 3967 |     1943 |    2024 | 49.0%      | 47.4%       | 50.5%       |           0.383 |          |
| SPY Disagree | Both     | 8740 |     4285 |    4455 | 49.0%      | 48.0%       | 50.1%       |           0.217 |          |

### Table 5 — Split by Sector Agree / Disagree (Open→09:45)

| Subgroup        | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:----------------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| Sector Agree    | Gap Up   | 4530 |     2252 |    2278 | 49.7%      | 48.3%       | 51.2%       |           0.79  |          |
| Sector Agree    | Gap Down | 4086 |     2045 |    2041 | 50.0%      | 48.5%       | 51.6%       |           0.968 |          |
| Sector Agree    | Both     | 8616 |     4297 |    4319 | 49.9%      | 48.8%       | 50.9%       |           0.856 |          |
| Sector Disagree | Gap Up   | 4311 |     2151 |    2160 | 49.9%      | 48.4%       | 51.4%       |           0.916 |          |
| Sector Disagree | Gap Down | 3870 |     1934 |    1936 | 50.0%      | 48.4%       | 51.5%       |           0.979 |          |
| Sector Disagree | Both     | 8181 |     4085 |    4096 | 49.9%      | 48.8%       | 51.0%       |           0.927 |          |

### Table 6 — Split by Stage

| Subgroup   | Gap      |    n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:-----------|:---------|-----:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| Stage 2    | Gap Up   | 4541 |     2146 |    2395 | 47.3%      | 45.8%       | 48.7%       |           0.001 |          |
| Stage 2    | Gap Down | 3878 |     1985 |    1893 | 51.2%      | 49.6%       | 52.8%       |           0.246 |          |
| Stage 2    | Both     | 8419 |     4131 |    4288 | 49.1%      | 48.0%       | 50.1%       |           0.129 |          |
| Stage 3+4  | Gap Up   | 4532 |     2351 |    2181 | 51.9%      | 50.4%       | 53.3%       |           0.073 |          |
| Stage 3+4  | Gap Down | 4288 |     2099 |    2189 | 49.0%      | 47.5%       | 50.4%       |           0.33  |          |
| Stage 3+4  | Both     | 8820 |     4450 |    4370 | 50.5%      | 49.4%       | 51.5%       |           0.486 |          |

## Table 7 — Fully tradeable combinations (n >= 200)

Pattern + Stage + SPY Agree/Disagree, every window pooled into one ranking. Every term here is knowable at 09:45.

### 7a — using the simple first-candle pattern

| Window         | Subgroup                                |    n |   n cont | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:---------------|:----------------------------------------|-----:|---------:|:-----------|:------------|:------------|----------------:|:---------|
| 09:45 -> 10:00 | Continuation | Stage 3+4 | SPY Agree    | 1920 |     1080 | 56.2%      | 54.0%       | 58.5%       |           0     |          |
| 09:45 -> 12:00 | Continuation | Stage 3+4 | SPY Agree    | 1928 |     1078 | 55.9%      | 53.7%       | 58.1%       |           0     |          |
| 09:45 -> 10:30 | Doji | Stage 2 | SPY Disagree           |  358 |      198 | 55.3%      | 50.1%       | 60.4%       |           0.052 |          |
| 09:45 -> 10:30 | Continuation | Stage 3+4 | SPY Disagree | 1731 |      952 | 55.0%      | 52.6%       | 57.3%       |           0.001 |          |
| 09:45 -> 13:00 | Continuation | Stage 3+4 | SPY Agree    | 1934 |     1063 | 55.0%      | 52.7%       | 57.2%       |           0     |          |
| 09:45 -> 11:00 | Continuation | Stage 3+4 | SPY Agree    | 1940 |     1066 | 54.9%      | 52.7%       | 57.2%       |           0     |          |
| 09:45 -> 10:00 | Continuation | Stage 3+4 | SPY Disagree | 1728 |      949 | 54.9%      | 52.6%       | 57.3%       |           0     |          |
| 09:45 -> 10:30 | Continuation | Stage 3+4 | SPY Agree    | 1933 |     1056 | 54.6%      | 52.4%       | 56.8%       |           0     |          |
| 09:45 -> 10:30 | Doji | Stage 3+4 | SPY Disagree         |  356 |      194 | 54.5%      | 49.3%       | 59.6%       |           0.104 |          |
| 09:45 -> Close | Continuation | Stage 3+4 | SPY Agree    | 1932 |     1052 | 54.5%      | 52.2%       | 56.7%       |           0.001 |          |
| 09:45 -> 10:00 | Continuation | Stage 2 | SPY Disagree   | 1668 |      900 | 54.0%      | 51.6%       | 56.3%       |           0     |          |
| 09:45 -> 11:00 | Doji | Stage 3+4 | SPY Agree            |  382 |      206 | 53.9%      | 48.9%       | 58.9%       |           0.116 |          |
| 09:45 -> 13:00 | Doji | Stage 3+4 | SPY Agree            |  383 |      205 | 53.5%      | 48.5%       | 58.5%       |           0.196 |          |
| 09:45 -> 10:30 | Continuation | Stage 2 | SPY Agree      | 1794 |      960 | 53.5%      | 51.2%       | 55.8%       |           0.007 |          |
| 09:45 -> 10:30 | Continuation | Stage 2 | SPY Disagree   | 1669 |      892 | 53.4%      | 51.0%       | 55.8%       |           0.018 |          |
| 09:45 -> 11:00 | Continuation | Stage 2 | SPY Agree      | 1796 |      958 | 53.3%      | 51.0%       | 55.6%       |           0.009 |          |
| 09:45 -> 11:00 | Continuation | Stage 3+4 | SPY Disagree | 1732 |      920 | 53.1%      | 50.8%       | 55.5%       |           0.034 |          |
| 09:45 -> 13:00 | Continuation | Stage 2 | SPY Agree      | 1803 |      956 | 53.0%      | 50.7%       | 55.3%       |           0.016 |          |
| 09:45 -> 10:00 | Doji | Stage 2 | SPY Agree              |  325 |      172 | 52.9%      | 47.5%       | 58.3%       |           0.272 |          |
| 09:45 -> 10:30 | Doji | Stage 3+4 | SPY Agree            |  382 |      202 | 52.9%      | 47.9%       | 57.8%       |           0.275 |          |

Lowest-ranked:

| Window         | Subgroup                            |    n | Win rate   |   p (clustered) |
|:---------------|:------------------------------------|-----:|:-----------|----------------:|
| 09:45 -> 12:00 | Reversal | Stage 3+4 | SPY Disagree | 2027 | 48.7%      |           0.33  |
| 09:45 -> Close | Reversal | Stage 2 | SPY Agree      | 1726 | 48.6%      |           0.286 |
| 09:45 -> 10:00 | Reversal | Stage 2 | SPY Agree      | 1712 | 48.5%      |           0.234 |
| 09:45 -> 10:30 | Reversal | Stage 3+4 | SPY Disagree | 2027 | 48.5%      |           0.252 |
| 09:45 -> 11:00 | Reversal | Stage 2 | SPY Agree      | 1724 | 48.4%      |           0.176 |
| 09:45 -> Close | Reversal | Stage 3+4 | SPY Disagree | 2033 | 48.3%      |           0.247 |
| 09:45 -> 13:00 | Reversal | Stage 3+4 | SPY Disagree | 2030 | 47.8%      |           0.103 |
| 09:45 -> 11:00 | Reversal | Stage 3+4 | SPY Disagree | 2027 | 47.8%      |           0.076 |

### 7b — using the 4-pattern system

| Window         | Subgroup                                          |   n |   n cont | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:---------------|:--------------------------------------------------|----:|---------:|:-----------|:------------|:------------|----------------:|:---------|
| 09:45 -> 10:00 | Indecision0 | Stage 2 | SPY Disagree              | 914 |      523 | 57.2%      | 54.0%       | 60.4%       |           0     |          |
| 09:45 -> 12:00 | Moderate Continuation+ | Stage 3+4 | SPY Agree    | 726 |      414 | 57.0%      | 53.4%       | 60.6%       |           0.001 |          |
| 09:45 -> 10:00 | Strong Continuation+ | Stage 3+4 | SPY Agree      | 416 |      235 | 56.5%      | 51.7%       | 61.2%       |           0.006 |          |
| 09:45 -> 10:00 | Moderate Continuation+ | Stage 3+4 | SPY Disagree | 574 |      323 | 56.3%      | 52.2%       | 60.3%       |           0.001 |          |
| 09:45 -> 11:00 | Indecision0 | Stage 3+4 | SPY Agree               | 946 |      532 | 56.2%      | 53.1%       | 59.4%       |           0     |          |
| 09:45 -> 10:30 | Strong Continuation+ | Stage 3+4 | SPY Disagree   | 292 |      164 | 56.2%      | 50.4%       | 61.7%       |           0.044 |          |
| 09:45 -> 10:30 | Indecision0 | Stage 3+4 | SPY Agree               | 950 |      533 | 56.1%      | 52.9%       | 59.2%       |           0.001 |          |
| 09:45 -> 10:00 | Strong Continuation+ | Stage 2 | SPY Disagree     | 336 |      187 | 55.7%      | 50.3%       | 60.9%       |           0.06  |          |
| 09:45 -> 13:00 | Moderate Continuation+ | Stage 3+4 | SPY Agree    | 733 |      407 | 55.5%      | 51.9%       | 59.1%       |           0.003 |          |
| 09:45 -> 10:30 | Indecision0 | Stage 2 | SPY Agree                 | 869 |      481 | 55.4%      | 52.0%       | 58.6%       |           0     |          |
| 09:45 -> 10:30 | Strong Continuation+ | Stage 2 | SPY Disagree     | 342 |      189 | 55.3%      | 50.0%       | 60.4%       |           0.057 |          |
| 09:45 -> 10:00 | Indecision0 | Stage 3+4 | SPY Agree               | 943 |      520 | 55.1%      | 52.0%       | 58.3%       |           0.001 |          |
| 09:45 -> 10:30 | Indecision0 | Stage 3+4 | SPY Disagree            | 884 |      487 | 55.1%      | 51.8%       | 58.3%       |           0.007 |          |
| 09:45 -> 11:00 | Indecision0 | Stage 2 | SPY Disagree              | 920 |      506 | 55.0%      | 51.8%       | 58.2%       |           0.001 |          |
| 09:45 -> 12:00 | Indecision0 | Stage 3+4 | SPY Agree               | 953 |      524 | 55.0%      | 51.8%       | 58.1%       |           0.003 |          |

---

## Summary

### 1. Is there any combination clearly above 50% with a reasonable sample, under fair rules?

**Yes — one survives properly.** 16 of 72 cells with n >= 200 clear both a 50% win rate and a clustered p < 0.05. The strongest is **Continuation | Stage 3+4 | SPY Agree** on 09:45 -> 10:00 at **56.2%** (n = 1,920, p = 0.000).

On the multiple-testing arithmetic: those 72 cells are not 72 independent tests — they are 12 distinct combinations each measured over 6 heavily overlapping windows on the same events. Against ~12 effective tests, chance alone would produce about 1 hits at p < 0.05; 16 were observed, and the leading combination holds up across every window rather than appearing in one. That is more than a leaderboard artefact.

Two things still keep it short of a recommendation: the whole study sits on a survivorship-biased universe (see the main report), and a ~56% win rate says nothing about payoff size — this report deliberately measures no returns, and the earlier cost work showed the average move is close to the spread. It is a genuine candidate for out-of-sample testing, not a validated edge.

### 2. Does the ICT midday window behave differently?

The 09:45→13:00 window shows **50.5%** overall continuation (n = 17,371, p = 0.282). The other windows range from 49.8% to 51.1%. 
That places midday **0.1 points below** the average of the others — a difference too small to call a distinct regime. There is no sign of a special midday reversal: the continuation rate drifts smoothly with holding length rather than turning at any particular hour.

### 3. Does Gap Down still look better than Gap Up?

| Window | Gap Up | p | Gap Down | p |
|---|---:|---:|---:|---:|
| 09:45 -> 10:00 | 50.3% | 0.579 | 51.7% | 0.014 |
| 09:45 -> 10:30 | 50.3% | 0.700 | 52.1% | 0.007 |
| 09:45 -> 11:00 | 49.8% | 0.794 | 51.8% | 0.031 |
| 09:45 -> 12:00 | 50.0% | 0.956 | 50.8% | 0.295 |
| 09:45 -> 13:00 | 50.4% | 0.563 | 50.5% | 0.508 |
| 09:45 -> Close | 49.6% | 0.619 | 50.1% | 0.910 |

Gap Down beats Gap Up in **6 of 6** windows. The asymmetry survives the removal of look-ahead entirely.

It is also not weaker than the old contaminated version — it is concentrated differently. Gap Down peaks at **52.1%** on 09:45 -> 10:30 (p = 0.007), which is at least as strong as the full-day open-to-close figure reported earlier, even though the first fifteen minutes are now excluded by construction. What changes is the horizon: Gap Down is significant in 3 of 6 windows, all of them short, and decays to nothing by the close. Gap Up never reaches significance in any window.

### 4. Which pattern system works better with all look-ahead removed?

Spread between the most bullish and most bearish bucket of each system, in percentage points of win rate:

| Window | 4-pattern spread | Simple 1-candle spread |
|---|---:|---:|
| 09:45 -> 10:00 | 2.7 pts | 4.8 pts |
| 09:45 -> 10:30 | 3.4 pts | 4.6 pts |
| 09:45 -> 11:00 | 2.9 pts | 4.5 pts |
| 09:45 -> 12:00 | 2.0 pts | 3.3 pts |
| 09:45 -> 13:00 | 2.4 pts | 3.4 pts |
| 09:45 -> Close | 2.1 pts | 2.8 pts |

Average spread: **2.6 points** for the 4-pattern system versus **3.9 points** for the simple one-candle rule. The simple rule separates at least as well as the elaborate one, which is the practical answer: the extra structure in the 4-pattern definition was mostly consuming more of the scored window, not adding predictive content. Either way both spreads are a small fraction of what they looked like when the pattern window sat inside the measured return.

---

_Reproducible from `lambda_strategy_validation/tradeable_report.py`; tables also written to `lambda_data/tables/trade_*.csv`._