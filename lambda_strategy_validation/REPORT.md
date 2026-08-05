# Lambda Validation Report

**Edge:** T+1 Post-Earnings Volatility + Gap Continuation + Relative Beta + Opening 5-Minute Pattern, conditional on Minervini Stage

**Verdict: REJECT**

- Events analysed: **17,583** earnings T+1 sessions
- Tickers: **615** | Distinct event dates: **1,941** | Span: 2015-01-07 to 2025-12-22
- Gross continuation expectancy: **8.92 bps**; after measured spread + 2 bps impact: **1.96 bps** (95% CI -3.16 to 7.11, clustered p = 0.452)

## Decision reasoning

Thresholds were fixed before the results were computed:

- Headline net expectancy (Roll + 2bps impact): 1.96 bps/trade (threshold >= 5.0), clustered p = 0.452 (threshold <= 0.05), 95% CI lower bound = -3.16 bps.
- Years with positive net expectancy: 64% (7/11); threshold for PROMOTE >= 70%.
- Stages with positive net expectancy: 2/3 (threshold for PROMOTE = all 3).

## 1. Data and method

| Item | Value |
|---|---|
| Price/volume source | HF Data Library 1-minute bars, aggregated to daily and to 5-minute |
| Earnings dates | Nasdaq calendar API, confirmed-actual rows only |
| Market cap | SEC EDGAR point-in-time shares outstanding x split-adjusted close |
| Panel rows before filters | 2,019,751 |
| Panel rows passing universe filters | 1,230,471 |
| Tickers with direct market cap | 664 |
| Tickers using liquidity proxy for market cap | 362 |

**Market-cap proxy validation.** For tickers where SEC market cap *is* available, only **4.85%** of ticker-days that pass the $50M ADTV filter have market cap at or below $3B. The ADTV filter is therefore a tight substitute for the market-cap filter, which is why delisted and renamed tickers (whose SEC ticker mapping no longer resolves) are kept via the proxy rather than dropped — dropping them would compound the survivorship bias described below.

**Inference.** Earnings T+1 observations cluster by calendar date — dozens of firms report the same evening and share the next day's market move. All confidence intervals and p-values here come from a **date-clustered bootstrap** (resampling whole trading dates). Independence-assuming binomial p-values are shown alongside for contrast and are systematically too optimistic.

**Costs.** Each event is charged its ticker's **own measured trailing spread** on both legs, plus an explicit impact allowance. The Roll estimator is used as the primary input because it is realistically calibrated on this data (median ~1.9 bps for AAPL). Corwin-Schultz, although the more common high-low estimator, is inflated here by roughly an order of magnitude (median ~18 bps for AAPL, against a true quoted spread well under 2 bps) because it reads earnings-day range expansion as spread; it is therefore reported only as a pessimistic upper bound. The trailing median is also lagged one day, so the cost input is knowable before the trade.

## 2. Volatility elevation on T+1 (section 3.1)

Ratio of the T+1 value to the median non-earnings day for the same ticker in the same calendar quarter. A ratio of 1.0 means no elevation. `mean_excess` is the mean of (ratio - 1) with clustered CI.

| metric       |     n |   median_ratio |   mean_ratio |   mean_excess |   ci_lo |   ci_hi |   p |
|:-------------|------:|---------------:|-------------:|--------------:|--------:|--------:|----:|
| true_range   | 17574 |         1.7874 |       2.2896 |        1.2896 |  1.2539 |  1.3245 |   0 |
| atr14        | 17574 |         1.1098 |       1.1485 |        0.1485 |  0.1398 |  0.1572 |   0 |
| tr_pct       | 17574 |         1.7939 |       2.2922 |        1.2922 |  1.2565 |  1.3283 |   0 |
| hl_over_open | 17574 |         1.6993 |       1.8982 |        0.8982 |  0.8756 |  0.9219 |   0 |
| rv_5min      | 17574 |         2.5421 |       3.4512 |        2.4512 |  2.3656 |  2.5408 |   0 |
| parkinson    | 17574 |         2.8941 |       4.3645 |        3.3645 |  3.25   |  3.491  |   0 |

### By stage

| metric       |    n |   median_ratio |   mean_ratio |   mean_excess |   ci_lo |   ci_hi |   p | stage_name          |
|:-------------|-----:|---------------:|-------------:|--------------:|--------:|--------:|----:|:--------------------|
| true_range   | 8511 |         1.8077 |       2.3153 |        1.3153 |  1.2686 |  1.3633 |   0 | Stage 2 (Advancing) |
| atr14        | 8511 |         1.0929 |       1.1246 |        0.1246 |  0.1158 |  0.1332 |   0 | Stage 2 (Advancing) |
| tr_pct       | 8511 |         1.7896 |       2.2935 |        1.2935 |  1.2466 |  1.3398 |   0 | Stage 2 (Advancing) |
| hl_over_open | 8511 |         1.6899 |       1.8973 |        0.8973 |  0.8671 |  0.9274 |   0 | Stage 2 (Advancing) |
| rv_5min      | 8511 |         2.5369 |       3.4629 |        2.4629 |  2.3673 |  2.5643 |   0 | Stage 2 (Advancing) |
| parkinson    | 8511 |         2.872  |       4.4016 |        3.4016 |  3.2401 |  3.5707 |   0 | Stage 2 (Advancing) |
| true_range   | 2447 |         1.7618 |       2.2814 |        1.2814 |  1.2057 |  1.3574 |   0 | Stage 3 (Topping)   |
| atr14        | 2447 |         1.1227 |       1.1525 |        0.1525 |  0.1411 |  0.1635 |   0 | Stage 3 (Topping)   |
| tr_pct       | 2447 |         1.7637 |       2.2763 |        1.2763 |  1.2003 |  1.3514 |   0 | Stage 3 (Topping)   |
| hl_over_open | 2447 |         1.6665 |       1.877  |        0.877  |  0.834  |  0.9184 |   0 | Stage 3 (Topping)   |
| rv_5min      | 2447 |         2.5154 |       3.3439 |        2.3439 |  2.2159 |  2.4726 |   0 | Stage 3 (Topping)   |
| parkinson    | 2447 |         2.7944 |       4.2665 |        3.2665 |  3.0494 |  3.496  |   0 | Stage 3 (Topping)   |
| true_range   | 6463 |         1.7607 |       2.246  |        1.246  |  1.1952 |  1.2965 |   0 | Stage 4 (Declining) |
| atr14        | 6463 |         1.1289 |       1.1788 |        0.1788 |  0.1653 |  0.1929 |   0 | Stage 4 (Declining) |
| tr_pct       | 6463 |         1.7956 |       2.2833 |        1.2833 |  1.2319 |  1.3357 |   0 | Stage 4 (Declining) |
| hl_over_open | 6463 |         1.7158 |       1.904  |        0.904  |  0.871  |  0.9355 |   0 | Stage 4 (Declining) |
| rv_5min      | 6463 |         2.5546 |       3.4763 |        2.4763 |  2.3384 |  2.6213 |   0 | Stage 4 (Declining) |
| parkinson    | 6463 |         2.957  |       4.3429 |        3.3429 |  3.1835 |  3.5015 |   0 | Stage 4 (Declining) |

### By size (ADTV terciles)

| metric   |    n |   median_ratio |   mean_ratio |   mean_excess |   ci_lo |   ci_hi |   p | size_adtv   |
|:---------|-----:|---------------:|-------------:|--------------:|--------:|--------:|----:|:------------|
| tr_pct   | 5856 |         1.8875 |       2.4447 |        1.4447 |  1.3814 |  1.5089 |   0 | Small       |
| rv_5min  | 5856 |         2.8251 |       3.7883 |        2.7883 |  2.6522 |  2.9286 |   0 | Small       |
| tr_pct   | 5857 |         1.7861 |       2.2774 |        1.2774 |  1.224  |  1.3311 |   0 | Mid         |
| rv_5min  | 5857 |         2.578  |       3.5957 |        2.5957 |  2.4758 |  2.7257 |   0 | Mid         |
| tr_pct   | 5861 |         1.6886 |       2.1548 |        1.1548 |  1.11   |  1.2013 |   0 | Large       |
| rv_5min  | 5861 |         2.2577 |       2.97   |        1.97   |  1.8625 |  2.1022 |   0 | Large       |

## 3. Four-quadrant gap x intraday (section 3.2)

Counts:

| gap     |   IntraDown |   IntraUp |
|:--------|------------:|----------:|
| GapDown |        4354 |      4036 |
| GapUp   |        4649 |      4544 |

Continuation = the T+1 open-to-close move has the same sign as the overnight gap. `mean_signed_o2c` is the gross return of trading in the gap direction from open to close.

|     n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |   chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|------:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|-------:|---------:|------------------:|---------------:|---------------:|-----------:|
| 17583 |      1941 |              0.5061 |  0.4977 |  0.5148 |        0.1715 |       0.1099 |  3.025 |    0.082 |            0.0009 |         0.0004 |         0.0014 |      0.001 |

### Stratified by stage

| stage_name          |    n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |   chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|:--------------------|-----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|-------:|---------:|------------------:|---------------:|---------------:|-----------:|
| Stage 2 (Advancing) | 8514 |      1588 |              0.5029 |  0.4909 |  0.515  |        0.6325 |       0.5954 | 0.8253 |   0.3636 |            0.0013 |         0.0006 |         0.002  |     0      |
| Stage 3 (Topping)   | 2448 |      1004 |              0.5229 |  0.5018 |  0.5434 |        0.0265 |       0.0248 | 4.958  |   0.026  |            0.0019 |         0.0008 |         0.0031 |     0.0015 |
| Stage 4 (Declining) | 6467 |      1442 |              0.5029 |  0.49   |  0.5155 |        0.6755 |       0.6544 | 0.1762 |   0.6747 |           -0.0001 |        -0.001  |         0.0007 |     0.7785 |

### By gap direction

| gap_up   |    n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial | chi2   | p_chi2   |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|:---------|-----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|:-------|:---------|------------------:|---------------:|---------------:|-----------:|
| False    | 8390 |      1601 |              0.519  |  0.5037 |  0.5336 |        0.0165 |       0.0005 |        |          |            0.0011 |         0.0001 |         0.002  |     0.0255 |
| True     | 9193 |      1636 |              0.4943 |  0.4787 |  0.5089 |        0.47   |       0.2781 |        |          |            0.0007 |        -0.0002 |         0.0016 |     0.1015 |

## 4. Relative beta filter (section 3.3)

An event is flagged low-quality when the stock's T+1 open-to-close return has the opposite sign to **both** SPY and its sector ETF.

|     n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |    chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p | cohort                   |
|------:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|--------:|---------:|------------------:|---------------:|---------------:|-----------:|:-------------------------|
| 17340 |      1941 |              0.5064 |  0.4981 |  0.5156 |        0.155  |       0.0933 |  3.2723 |   0.0705 |            0.0009 |         0.0004 |         0.0014 |     0.0005 | all (benchmarked)        |
| 12793 |      1799 |              0.5148 |  0.5034 |  0.5266 |        0.0105 |       0.0008 | 10.4254 |   0.0012 |            0.0013 |         0.0006 |         0.0019 |     0      | beta filter applied      |
|  4547 |      1346 |              0.4827 |  0.4647 |  0.5004 |        0.059  |       0.0207 |  3.7099 |   0.0541 |           -0.0003 |        -0.0011 |         0.0006 |     0.55   | excluded (opposite both) |

### Filtered cohort, by stage

| stage_name          |    n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |   chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|:--------------------|-----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|-------:|---------:|------------------:|---------------:|---------------:|-----------:|
| Stage 2 (Advancing) | 6163 |      1416 |              0.5071 |  0.492  |  0.5226 |        0.362  |       0.2733 | 1.4739 |   0.2247 |            0.0015 |         0.0007 |         0.0024 |     0      |
| Stage 3 (Topping)   | 1761 |       840 |              0.5378 |  0.5138 |  0.562  |        0.003  |       0.0017 | 9.4527 |   0.0021 |            0.0026 |         0.0012 |         0.0039 |     0      |
| Stage 4 (Declining) | 4761 |      1280 |              0.5154 |  0.4978 |  0.5326 |        0.0835 |       0.0343 | 3.9768 |   0.0461 |            0.0004 |        -0.0007 |         0.0015 |     0.4265 |

## 5. First three 5-minute candles (section 3.4)

| pattern                |    n |   share |
|:-----------------------|-----:|--------:|
| Early Reversal-        | 8468 |  0.5141 |
| Indecision0            | 3856 |  0.2341 |
| Moderate Continuation+ | 2653 |  0.1611 |
| Strong Continuation+   | 1496 |  0.0908 |

### Continuation probability by pattern

| pattern                |    n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |     chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|:-----------------------|-----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|---------:|---------:|------------------:|---------------:|---------------:|-----------:|
| Early Reversal-        | 8468 |      1653 |              0.3656 |  0.3539 |  0.377  |             0 |            0 | 600.041  |        0 |           -0.008  |        -0.0086 |        -0.0073 |          0 |
| Indecision0            | 3856 |      1266 |              0.5615 |  0.5449 |  0.5784 |             0 |            0 |  57.7593 |        0 |            0.0036 |         0.0027 |         0.0044 |          0 |
| Moderate Continuation+ | 2653 |      1067 |              0.7704 |  0.7536 |  0.7861 |             0 |            0 | 776.199  |        0 |            0.0174 |         0.0163 |         0.0185 |          0 |
| Strong Continuation+   | 1496 |       791 |              0.8463 |  0.8255 |  0.8664 |             0 |            0 | 713.182  |        0 |            0.0247 |         0.0227 |         0.027  |          0 |

### Net expectancy by pattern (after measured spread + 2 bps)

| pattern                |    n |   n_dates |   win_rate |   mean_net_bps |   ci_lo_bps |   ci_hi_bps |      p |   profit_factor |
|:-----------------------|-----:|----------:|-----------:|---------------:|------------:|------------:|-------:|----------------:|
| Early Reversal-        | 8468 |      1653 |     0.4792 |        -5.4127 |    -10.9988 |      0.1084 | 0.0555 |          0.9345 |
| Indecision0            | 3855 |      1266 |     0.4986 |         0.8158 |     -6.6791 |      8.3293 | 0.8295 |          1.0102 |
| Moderate Continuation+ | 2653 |      1067 |     0.4877 |         2.8843 |     -6.1757 |     12.1217 | 0.5345 |          1.0371 |
| Strong Continuation+   | 1496 |       791 |     0.5067 |        14.0747 |     -2.519  |     33.0504 | 0.1145 |          1.1717 |

### `+` patterns vs everything else

| pattern_plus   |     n |   n_dates |   win_rate |   mean_net_bps |   ci_lo_bps |   ci_hi_bps |      p |   profit_factor |
|:---------------|------:|----------:|-----------:|---------------:|------------:|------------:|-------:|----------------:|
| False          | 12323 |      1815 |     0.4853 |        -3.4642 |     -8.015  |      1.5184 | 0.1415 |          0.9576 |
| True           |  4149 |      1287 |     0.4946 |         6.9192 |     -1.0041 |     15.6295 | 0.1005 |          1.0873 |

### Sensitivity: same split with the rejection-wick clause removed

Sigma's wording ("strong rejection wicks against the gap direction") needs an interpreted threshold. If the pattern effect only exists under one reading of that clause, it is an artefact of the definition rather than a property of the market.

| pattern_plus_nowick   |     n |   n_dates |   win_rate |   mean_net_bps |   ci_lo_bps |   ci_hi_bps |     p |   profit_factor |
|:----------------------|------:|----------:|-----------:|---------------:|------------:|------------:|------:|----------------:|
| False                 | 11946 |      1804 |     0.4854 |        -3.2216 |     -7.7861 |      1.7441 | 0.187 |          0.9605 |
| True                  |  4526 |      1331 |     0.4936 |         5.414  |     -2.3777 |     13.7535 | 0.19  |          1.0675 |

## 6. Full interaction (section 3.5)

Stage 2 + `+` opening pattern + beta filter passed, split by gap direction.

| gap_up   |   n |   n_dates |   win_rate |   mean_net_bps |   ci_lo_bps |   ci_hi_bps |      p |   profit_factor |
|:---------|----:|----------:|-----------:|---------------:|------------:|------------:|-------:|----------------:|
| False    | 655 |       420 |     0.4947 |        20.6172 |      1.869  |     39.6653 | 0.0325 |          1.2909 |
| True     | 812 |       499 |     0.5234 |        24.8434 |      2.9657 |     53.0664 | 0.0515 |          1.3595 |

## 7. Robustness (section 3.6)

### Year by year

|   year |    n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |   chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|-------:|-----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|-------:|---------:|------------------:|---------------:|---------------:|-----------:|
|   2015 | 1402 |       172 |              0.5364 |  0.5042 |  0.5658 |        0.0245 |       0.007  | 6.8246 |   0.009  |            0.0013 |        -0.0001 |         0.0027 |     0.061  |
|   2016 | 1428 |       168 |              0.4958 |  0.4628 |  0.5296 |        0.7965 |       0.771  | 0.0106 |   0.9178 |            0.0008 |        -0.0007 |         0.0021 |     0.2775 |
|   2017 | 1558 |       172 |              0.4891 |  0.462  |  0.519  |        0.438  |       0.4031 | 0.3035 |   0.5817 |            0.0011 |        -0.0002 |         0.0024 |     0.0965 |
|   2018 | 1678 |       183 |              0.5072 |  0.4839 |  0.5309 |        0.5535 |       0.5745 | 0.5247 |   0.4688 |            0.001  |        -0.0007 |         0.0026 |     0.226  |
|   2019 | 1656 |       190 |              0.5006 |  0.4766 |  0.5246 |        0.959  |       0.9804 | 0      |   1      |            0.0009 |        -0.0006 |         0.0024 |     0.2485 |
|   2020 | 1649 |       189 |              0.5227 |  0.4901 |  0.5563 |        0.194  |       0.0684 | 3.815  |   0.0508 |            0.0004 |        -0.0017 |         0.0023 |     0.6755 |
|   2021 | 1686 |       190 |              0.5065 |  0.4798 |  0.5328 |        0.6095 |       0.6091 | 0.5153 |   0.4729 |            0.0017 |        -0.0004 |         0.0039 |     0.146  |
|   2022 | 1272 |       122 |              0.4914 |  0.4496 |  0.5277 |        0.6385 |       0.556  | 0.3441 |   0.5575 |           -0.0009 |        -0.0041 |         0.0017 |     0.5365 |
|   2023 | 1795 |       189 |              0.512  |  0.4872 |  0.5375 |        0.349  |       0.3215 | 1.049  |   0.3057 |            0.0006 |        -0.0008 |         0.0018 |     0.4055 |
|   2024 | 1729 |       181 |              0.513  |  0.4842 |  0.5392 |        0.3675 |       0.29   | 1.6666 |   0.1967 |            0.0021 |         0.0007 |         0.0034 |     0.0035 |
|   2025 | 1730 |       185 |              0.4908 |  0.4658 |  0.5176 |        0.468  |       0.4561 | 0.3418 |   0.5588 |            0.0005 |        -0.001  |         0.0022 |     0.4855 |

### Net expectancy by year (after costs)

|   year |    n |   n_dates |   win_rate |   mean_net_bps |   ci_lo_bps |   ci_hi_bps |      p |   profit_factor |
|-------:|-----:|----------:|-----------:|---------------:|------------:|------------:|-------:|----------------:|
|   2015 | 1402 |       172 |     0.52   |         5.9493 |     -8.203  |     19.4325 | 0.3965 |          1.0737 |
|   2016 | 1428 |       168 |     0.4797 |         0.4024 |    -13.9908 |     14.0992 | 0.956  |          1.0047 |
|   2017 | 1558 |       172 |     0.4763 |         3.9151 |     -8.6791 |     17.1352 | 0.537  |          1.0518 |
|   2018 | 1678 |       183 |     0.4958 |         2.3852 |    -14.5197 |     18.5585 | 0.7755 |          1.0224 |
|   2019 | 1656 |       190 |     0.4867 |         1.642  |    -13.3432 |     16.7712 | 0.8325 |          1.0174 |
|   2020 | 1649 |       189 |     0.5149 |        -2.9408 |    -23.8957 |     16.1803 | 0.782  |          0.9748 |
|   2021 | 1686 |       190 |     0.4947 |         9.4167 |    -11.208  |     32.1427 | 0.425  |          1.0861 |
|   2022 | 1272 |       122 |     0.4803 |       -15.9785 |    -48.4775 |     10.3467 | 0.2725 |          0.8859 |
|   2023 | 1795 |       189 |     0.5008 |        -0.7361 |    -14.0117 |     11.5062 | 0.91   |          0.993  |
|   2024 | 1729 |       181 |     0.5043 |        14.8305 |      0.6521 |     27.998  | 0.0335 |          1.1581 |
|   2025 | 1730 |       185 |     0.4798 |        -1.2871 |    -16.3475 |     14.984  | 0.867  |          0.9885 |

### Pre- vs post-2020

| era       |    n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |   chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|:----------|-----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|-------:|---------:|------------------:|---------------:|---------------:|-----------:|
| 2015-2019 | 7722 |       885 |              0.5053 |  0.4928 |  0.5182 |        0.409  |       0.3567 | 0.8199 |   0.3652 |            0.001  |         0.0003 |         0.0016 |      0.004 |
| 2020-2025 | 9861 |      1056 |              0.5066 |  0.495  |  0.5188 |        0.2735 |       0.1905 | 2.385  |   0.1225 |            0.0008 |         0      |         0.0015 |      0.043 |

### Volatility regime

VIX itself is not available in the connected sources (no continuous daily series covering 2015-2025), so the regime split uses **SPY 21-day trailing realized volatility**, median-split. This is a documented substitution.

| vol_regime   |    n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |   chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|:-------------|-----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|-------:|---------:|------------------:|---------------:|---------------:|-----------:|
| High vol     | 8784 |       960 |              0.5023 |  0.4892 |  0.5146 |        0.715  |       0.6773 | 0.2126 |   0.6447 |            0.0003 |        -0.0005 |         0.0011 |     0.4355 |
| Low vol      | 8799 |       981 |              0.5098 |  0.4984 |  0.5212 |        0.1015 |       0.0667 | 3.9666 |   0.0464 |            0.0015 |         0.0008 |         0.0021 |     0      |

### Size subgroups

| size_adtv   |    n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |   chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|:------------|-----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|-------:|---------:|------------------:|---------------:|---------------:|-----------:|
| Small       | 5861 |       636 |              0.5066 |  0.4912 |  0.5209 |        0.392  |       0.3208 | 1.0881 |   0.2969 |            0.001  |         0.0002 |         0.0019 |     0.0155 |
| Mid         | 5861 |      1211 |              0.5086 |  0.4951 |  0.5221 |        0.2335 |       0.1915 | 1.6794 |   0.195  |            0.0009 |         0.0001 |         0.0016 |     0.033  |
| Large       | 5861 |      1198 |              0.503  |  0.4888 |  0.5172 |        0.682  |       0.657  | 0.3199 |   0.5717 |            0.0008 |        -0.0001 |         0.0017 |     0.085  |

## 8. Transaction cost reality check (section 3.7)

| scenario                     |     n |   mean_net_bps |   ci_lo_bps |   ci_hi_bps |      p |   win_rate |   profit_factor |
|:-----------------------------|------:|---------------:|------------:|------------:|-------:|-----------:|----------------:|
| gross (no costs)             | 17583 |         8.9169 |      3.7768 |     14.0656 | 0.001  |     0.5046 |          1.0909 |
| trailing Roll spread         | 17583 |         5.964  |      0.8413 |     11.1085 | 0.0225 |     0.5016 |          1.0599 |
| Roll + 2bps impact           | 17583 |         1.964  |     -3.1587 |      7.1085 | 0.452  |     0.4942 |          1.0193 |
| Roll + 5bps impact           | 17583 |        -4.036  |     -9.1587 |      1.1085 | 0.13   |     0.4833 |          0.9614 |
| 2x Roll + 5bps (stressed)    | 17583 |        -6.9889 |    -12.1097 |     -1.8487 | 0.008  |     0.4781 |          0.9342 |
| Corwin-Schultz (upper bound) | 17583 |       -19.8346 |    -24.9383 |    -14.6084 | 0      |     0.4578 |          0.8245 |

### Net expectancy by stage

| stage_name          |    n |   n_dates |   win_rate |   mean_net_bps |   ci_lo_bps |   ci_hi_bps |      p |   profit_factor |
|:--------------------|-----:|----------:|-----------:|---------------:|------------:|------------:|-------:|----------------:|
| Stage 2 (Advancing) | 8514 |      1588 |     0.4904 |         6.4585 |     -0.5136 |     13.2802 | 0.0645 |          1.0717 |
| Stage 3 (Topping)   | 2448 |      1004 |     0.5098 |        12.0858 |      0.7371 |     23.6189 | 0.0385 |          1.1274 |
| Stage 4 (Declining) | 6467 |      1442 |     0.4922 |        -8.277  |    -16.5774 |     -0.4104 | 0.047  |          0.9293 |

## 9. Limitations that constrain this verdict

1. **Survivorship and index-membership bias (severe).** The HF Data Library universe is built from *current* S&P 500 / Nasdaq 100 / Dow 30 membership. Names that were in those indices during 2015-2025 but have since been removed are under-represented, and the ones present were selected partly *because* they survived. The provider discloses survivorship bias pre-2022 directly. Any edge measured here is biased upward, so a weak positive result should be read as consistent with no edge.
2. **BMO vs AMC announcement timing (measured below, not just flagged).** Sigma defines T+1 as the first session after the announcement date. For companies reporting *before* the open, the true reaction day is the announcement date itself, so those events are measured one session late. The Nasdaq feed supplies an explicit time-of-day flag for only 0.0% of the events here. The table below compares volatility elevation on the announcement session against the T+1 session: if the announcement session is also elevated, a material share of the sample is mis-dated.

| session                    |     n |   median_tr_ratio |   mean_excess |   ci_lo |   ci_hi |
|:---------------------------|------:|------------------:|--------------:|--------:|--------:|
| announcement session (T+0) | 17460 |            1.8082 |        1.3234 |  1.2873 |  1.3624 |
| first session after (T+1)  | 17578 |            1.7872 |        1.2813 |  1.246  |  1.3166 |

3. **IEX source break (2022-03-01).** Volumes are not directly comparable across the provider's data-source transition, which affects ADV/ADTV filters and any volume-based inference spanning that date.
4. **1-minute bars are not tick data.** The opening-candle classification and the spread estimators are built on 1-minute sampling, not the order book. Corwin-Schultz and Roll are estimators, not quoted spreads.
5. **No borrow costs or short-availability modelling.** Gap-down continuation trades are short trades; their real-world cost is understated.

## 9b. Two additional findings from the extended analysis

**Per-stock scan (496 tickers).** 25 names clear p<0.05 on their own continuation rate. Chance alone predicts 24.8. After a Benjamini-Hochberg correction across the family of tests, **zero** survive. The per-stock leaderboard is therefore a picture of noise, not a shortlist — the top name (CAR, +697 bps) carries q = 0.90.

**One sector does survive.** Communication Services returns +40.1 bps net per trade (date-clustered p = 0.0040), which clears a Bonferroni threshold of 0.0045 for 11 sector tests. It is positive in all 11 years and still significant after dropping its 20 largest moves (+35.4 bps, p = 0.004). Caveats that keep this CONDITIONAL rather than promotable: 35 tickers only, concentration in SNAP / LUMN / NTES / ROKU, a continuation *rate* of just 52.6% (p = 0.16) meaning the result rests on return asymmetry rather than hit rate, and the sector itself did not exist as a GICS grouping until 2018.

**Entry timing (1-minute bars).** Sweeping the entry minute by minute over 09:31-09:59 and holding to the close, **no entry time is profitable net of costs** — the best (09:31) returns -2.0 bps at p = 0.40, and later entries get steadily worse. The full-session signed drift is only 8.9 bps, of which 44% is priced within the first minute and 81% by 09:45. So a faster trigger does not rescue the edge: the move is real and highly significant, but it is smaller than the cost of capturing it.

## 10. Recommended next experiments

1. **Rebuild the universe without survivorship bias.** This is the single highest-value next step: the current universe cannot distinguish a real edge from selection. A point-in-time index-membership source (or a delisted-inclusive vendor) would settle it.
2. **Resolve announcement timing.** Source a BMO/AMC flag (or infer it from which session carries the volume spike) and re-run with the reaction day correctly identified. If a real edge exists, mis-dating a large share of events would be diluting it.
3. **Condition on surprise magnitude.** The Nasdaq feed carries actual vs forecast EPS; the continuation hypothesis is much more plausible for large-surprise events than for the pooled sample tested here.
4. **Test a shorter holding window.** Open-to-close pools the informative first hour with an uninformative afternoon. Test open-to-11:00 and open-to-first-hour exits.
5. **Re-examine the opening-pattern definition.** The labels here are a faithful but necessarily interpreted reading of Sigma's prose; a sensitivity sweep over the wick/body thresholds would show whether any pattern effect is robust or an artefact of one cut.

---

_Generated by Lambda (Strategy Validator). Every table in this report is reproducible from `lambda_strategy_validation/` and the CSVs in `lambda_data/tables/`._