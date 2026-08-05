# Lambda Validation Report

**Edge:** T+1 Post-Earnings Volatility + Gap Continuation + Relative Beta + Opening 5-Minute Pattern, conditional on Minervini Stage

**Verdict: REJECT**

- Events analysed: **6,215** earnings T+1 sessions
- Tickers: **344** | Distinct event dates: **1,066** | Span: 2015-01-15 to 2021-07-01
- Gross continuation expectancy: **5.65 bps**; after measured spread + 2 bps impact: **-1.53 bps** (95% CI -8.74 to 5.81, clustered p = 0.675)

## Decision reasoning

Thresholds were fixed before the results were computed:

- Headline net expectancy (Roll + 2bps impact): -1.53 bps/trade (threshold >= 5.0), clustered p = 0.675 (threshold <= 0.05), 95% CI lower bound = -8.74 bps.
- Years with positive net expectancy: 29% (2/7); threshold for PROMOTE >= 70%.
- Stages with positive net expectancy: 1/3 (threshold for PROMOTE = all 3).

## 1. Data and method

| Item | Value |
|---|---|
| Price/volume source | HF Data Library 1-minute bars, aggregated to daily and to 5-minute |
| Earnings dates | Nasdaq calendar API, confirmed-actual rows only |
| Market cap | SEC EDGAR point-in-time shares outstanding x split-adjusted close |
| Panel rows before filters | 1,190,027 |
| Panel rows passing universe filters | 519,960 |
| Tickers with direct market cap | 392 |
| Tickers using liquidity proxy for market cap | 195 |

**Market-cap proxy validation.** For tickers where SEC market cap *is* available, only **4.12%** of ticker-days that pass the $50M ADTV filter have market cap at or below $3B. The ADTV filter is therefore a tight substitute for the market-cap filter, which is why delisted and renamed tickers (whose SEC ticker mapping no longer resolves) are kept via the proxy rather than dropped — dropping them would compound the survivorship bias described below.

**Inference.** Earnings T+1 observations cluster by calendar date — dozens of firms report the same evening and share the next day's market move. All confidence intervals and p-values here come from a **date-clustered bootstrap** (resampling whole trading dates). Independence-assuming binomial p-values are shown alongside for contrast and are systematically too optimistic.

**Costs.** Each event is charged its ticker's **own measured trailing spread** on both legs, plus an explicit impact allowance. The Roll estimator is used as the primary input because it is realistically calibrated on this data (median ~1.9 bps for AAPL). Corwin-Schultz, although the more common high-low estimator, is inflated here by roughly an order of magnitude (median ~18 bps for AAPL, against a true quoted spread well under 2 bps) because it reads earnings-day range expansion as spread; it is therefore reported only as a pessimistic upper bound. The trailing median is also lagged one day, so the cost input is knowable before the trade.

## 2. Volatility elevation on T+1 (section 3.1)

Ratio of the T+1 value to the median non-earnings day for the same ticker in the same calendar quarter. A ratio of 1.0 means no elevation. `mean_excess` is the mean of (ratio - 1) with clustered CI.

| metric       |    n |   median_ratio |   mean_ratio |   mean_excess |   ci_lo |   ci_hi |   p |
|:-------------|-----:|---------------:|-------------:|--------------:|--------:|--------:|----:|
| true_range   | 6214 |         1.7381 |       2.2091 |        1.2091 |  1.1596 |  1.2599 |   0 |
| atr14        | 6214 |         1.0963 |       1.1371 |        0.1371 |  0.1252 |  0.1486 |   0 |
| tr_pct       | 6214 |         1.7441 |       2.2116 |        1.2116 |  1.1626 |  1.2629 |   0 |
| hl_over_open | 6214 |         1.6535 |       1.8642 |        0.8642 |  0.8318 |  0.8974 |   0 |
| rv_5min      | 6214 |         2.4364 |       3.3817 |        2.3817 |  2.2494 |  2.527  |   0 |
| parkinson    | 6214 |         2.7668 |       4.2045 |        3.2045 |  3.0379 |  3.3803 |   0 |

### By stage

| metric       |    n |   median_ratio |   mean_ratio |   mean_excess |   ci_lo |   ci_hi |   p | stage_name          |
|:-------------|-----:|---------------:|-------------:|--------------:|--------:|--------:|----:|:--------------------|
| true_range   | 3244 |         1.8    |       2.2528 |        1.2528 |  1.1924 |  1.3195 |   0 | Stage 2 (Advancing) |
| atr14        | 3244 |         1.0795 |       1.111  |        0.111  |  0.0998 |  0.1229 |   0 | Stage 2 (Advancing) |
| tr_pct       | 3244 |         1.7741 |       2.2353 |        1.2353 |  1.1752 |  1.3033 |   0 | Stage 2 (Advancing) |
| hl_over_open | 3244 |         1.6639 |       1.8735 |        0.8735 |  0.8335 |  0.9153 |   0 | Stage 2 (Advancing) |
| rv_5min      | 3244 |         2.4418 |       3.3815 |        2.3815 |  2.2513 |  2.5268 |   0 | Stage 2 (Advancing) |
| parkinson    | 3244 |         2.8204 |       4.2706 |        3.2706 |  3.0488 |  3.5271 |   0 | Stage 2 (Advancing) |
| true_range   |  830 |         1.6737 |       2.1354 |        1.1354 |  1.0233 |  1.2503 |   0 | Stage 3 (Topping)   |
| atr14        |  830 |         1.0953 |       1.1301 |        0.1301 |  0.1139 |  0.1479 |   0 | Stage 3 (Topping)   |
| tr_pct       |  830 |         1.6365 |       2.1208 |        1.1208 |  1.0111 |  1.2283 |   0 | Stage 3 (Topping)   |
| hl_over_open |  830 |         1.5817 |       1.7824 |        0.7824 |  0.7276 |  0.8402 |   0 | Stage 3 (Topping)   |
| rv_5min      |  830 |         2.3416 |       3.0918 |        2.0918 |  1.9189 |  2.2753 |   0 | Stage 3 (Topping)   |
| parkinson    |  830 |         2.5093 |       3.7973 |        2.7973 |  2.525  |  3.0873 |   0 | Stage 3 (Topping)   |
| true_range   | 2081 |         1.6902 |       2.1616 |        1.1616 |  1.08   |  1.2462 |   0 | Stage 4 (Declining) |
| atr14        | 2081 |         1.1309 |       1.181  |        0.181  |  0.1613 |  0.2015 |   0 | Stage 4 (Declining) |
| tr_pct       | 2081 |         1.7257 |       2.2008 |        1.2008 |  1.1216 |  1.2837 |   0 | Stage 4 (Declining) |
| hl_over_open | 2081 |         1.6735 |       1.8811 |        0.8811 |  0.8272 |  0.9354 |   0 | Stage 4 (Declining) |
| rv_5min      | 2081 |         2.4611 |       3.4972 |        2.4972 |  2.2289 |  2.8285 |   0 | Stage 4 (Declining) |
| parkinson    | 2081 |         2.7854 |       4.2555 |        3.2555 |  2.9858 |  3.5266 |   0 | Stage 4 (Declining) |

### By size (ADTV terciles)

| metric   |    n |   median_ratio |   mean_ratio |   mean_excess |   ci_lo |   ci_hi |   p | size_adtv   |
|:---------|-----:|---------------:|-------------:|--------------:|--------:|--------:|----:|:------------|
| tr_pct   | 2071 |         1.8256 |       2.3288 |        1.3288 |  1.2506 |  1.4134 |   0 | Small       |
| rv_5min  | 2071 |         2.7898 |       3.8556 |        2.8556 |  2.677  |  3.0391 |   0 | Small       |
| tr_pct   | 2071 |         1.718  |       2.1653 |        1.1653 |  1.0968 |  1.2363 |   0 | Mid         |
| rv_5min  | 2071 |         2.418  |       3.4138 |        2.4138 |  2.1992 |  2.6749 |   0 | Mid         |
| tr_pct   | 2072 |         1.6831 |       2.1408 |        1.1408 |  1.0644 |  1.2235 |   0 | Large       |
| rv_5min  | 2072 |         2.1952 |       2.8757 |        1.8757 |  1.72   |  2.0547 |   0 | Large       |

## 3. Four-quadrant gap x intraday (section 3.2)

Counts:

| gap     |   IntraDown |   IntraUp |
|:--------|------------:|----------:|
| GapDown |        1583 |      1456 |
| GapUp   |        1629 |      1547 |

Continuation = the T+1 open-to-close move has the same sign as the overnight gap. `mean_signed_o2c` is the gross return of trading in the gap direction from open to close.

|    n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |   chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|-----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|-------:|---------:|------------------:|---------------:|---------------:|-----------:|
| 6215 |      1066 |              0.5036 |  0.4893 |  0.5174 |        0.6005 |       0.5768 | 0.3653 |   0.5456 |            0.0006 |        -0.0002 |         0.0013 |     0.1365 |

### Stratified by stage

| stage_name          |    n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |   chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|:--------------------|-----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|-------:|---------:|------------------:|---------------:|---------------:|-----------:|
| Stage 2 (Advancing) | 3245 |       856 |              0.5063 |  0.4882 |  0.5253 |        0.4955 |       0.4826 | 0.6807 |   0.4093 |            0.0011 |         0.0002 |         0.002  |     0.011  |
| Stage 3 (Topping)   |  830 |       450 |              0.5    |  0.4642 |  0.536  |        1      |       1      | 0      |   1      |            0.0003 |        -0.0015 |         0.0021 |     0.7795 |
| Stage 4 (Declining) | 2081 |       691 |              0.4993 |  0.4784 |  0.5209 |        0.9585 |       0.965  | 0.0012 |   0.9723 |           -0.0004 |        -0.0017 |         0.0008 |     0.543  |

### By gap direction

| gap_up   |    n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial | chi2   | p_chi2   |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|:---------|-----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|:-------|:---------|------------------:|---------------:|---------------:|-----------:|
| False    | 3039 |       821 |              0.5209 |  0.4993 |  0.543  |         0.062 |       0.0223 |        |          |            0.001  |        -0.0002 |         0.0021 |     0.102  |
| True     | 3176 |       849 |              0.4871 |  0.4662 |  0.5083 |         0.25  |       0.1506 |        |          |            0.0002 |        -0.0009 |         0.0013 |     0.7755 |

## 4. Relative beta filter (section 3.3)

An event is flagged low-quality when the stock's T+1 open-to-close return has the opposite sign to **both** SPY and its sector ETF.

|    n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |   chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p | cohort                   |
|-----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|-------:|---------:|------------------:|---------------:|---------------:|-----------:|:-------------------------|
| 6084 |      1065 |              0.5048 |  0.4909 |  0.5188 |        0.511  |       0.4649 | 0.598  |   0.4393 |            0.0005 |        -0.0002 |         0.0013 |     0.1435 | all (benchmarked)        |
| 4454 |       960 |              0.5135 |  0.4954 |  0.5313 |        0.171  |       0.0746 | 3.0556 |   0.0805 |            0.0009 |        -0      |         0.0018 |     0.056  | beta filter applied      |
| 1630 |       658 |              0.481  |  0.4527 |  0.511  |        0.2045 |       0.1308 | 2.193  |   0.1386 |           -0.0005 |        -0.0018 |         0.0009 |     0.518  | excluded (opposite both) |

### Filtered cohort, by stage

| stage_name          |    n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |   chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|:--------------------|-----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|-------:|---------:|------------------:|---------------:|---------------:|-----------:|
| Stage 2 (Advancing) | 2334 |       746 |              0.5129 |  0.49   |  0.5342 |        0.2565 |       0.222  | 1.5554 |   0.2123 |            0.0013 |         0.0003 |         0.0025 |     0.0215 |
| Stage 3 (Topping)   |  583 |       358 |              0.518  |  0.4772 |  0.5584 |        0.414  |       0.4075 | 0.6778 |   0.4103 |            0.0005 |        -0.0015 |         0.0026 |     0.604  |
| Stage 4 (Declining) | 1493 |       590 |              0.5124 |  0.4837 |  0.5418 |        0.391  |       0.3515 | 0.6836 |   0.4083 |            0.0002 |        -0.0014 |         0.0018 |     0.818  |

## 5. First three 5-minute candles (section 3.4)

| pattern                |    n |   share |
|:-----------------------|-----:|--------:|
| Early Reversal-        | 2928 |  0.5009 |
| Indecision0            | 1470 |  0.2515 |
| Moderate Continuation+ |  914 |  0.1563 |
| Strong Continuation+   |  534 |  0.0913 |

### Continuation probability by pattern

| pattern                |    n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |     chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|:-----------------------|-----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|---------:|---------:|------------------:|---------------:|---------------:|-----------:|
| Early Reversal-        | 2928 |       858 |              0.3538 |  0.3354 |  0.3738 |             0 |            0 | 243.998  |        0 |           -0.0078 |        -0.0087 |        -0.0068 |          0 |
| Indecision0            | 1470 |       611 |              0.5592 |  0.5329 |  0.5857 |             0 |            0 |  20.0837 |        0 |            0.0036 |         0.0023 |         0.0049 |          0 |
| Moderate Continuation+ |  914 |       479 |              0.7626 |  0.7347 |  0.7885 |             0 |            0 | 250.041  |        0 |            0.015  |         0.0135 |         0.0165 |          0 |
| Strong Continuation+   |  534 |       335 |              0.8633 |  0.83   |  0.8929 |             0 |            0 | 279.023  |        0 |            0.0219 |         0.0195 |         0.0244 |          0 |

### Net expectancy by pattern (after measured spread + 2 bps)

| pattern                |    n |   n_dates |   win_rate |   mean_net_bps |   ci_lo_bps |   ci_hi_bps |      p |   profit_factor |
|:-----------------------|-----:|----------:|-----------:|---------------:|------------:|------------:|-------:|----------------:|
| Early Reversal-        | 2928 |       858 |     0.4737 |        -7.4104 |    -15.7697 |      1.045  | 0.0835 |          0.9024 |
| Indecision0            | 1470 |       611 |     0.4837 |        -1.027  |    -11.8114 |     10.1236 | 0.852  |          0.9861 |
| Moderate Continuation+ |  914 |       479 |     0.4726 |        -8.3343 |    -21.7428 |      4.6875 | 0.2185 |          0.8907 |
| Strong Continuation+   |  534 |       335 |     0.5056 |         6.0282 |    -13.6545 |     27.0009 | 0.584  |          1.0789 |

### `+` patterns vs everything else

| pattern_plus   |    n |   n_dates |   win_rate |   mean_net_bps |   ci_lo_bps |   ci_hi_bps |      p |   profit_factor |
|:---------------|-----:|----------:|-----------:|---------------:|------------:|------------:|-------:|----------------:|
| False          | 4398 |       967 |     0.477  |        -5.2768 |    -11.9534 |      1.3647 | 0.1295 |          0.9298 |
| True           | 1448 |       611 |     0.4848 |        -3.0376 |    -13.8632 |      8.4673 | 0.59   |          0.9602 |

### Sensitivity: same split with the rejection-wick clause removed

Sigma's wording ("strong rejection wicks against the gap direction") needs an interpreted threshold. If the pattern effect only exists under one reading of that clause, it is an artefact of the definition rather than a property of the market.

| pattern_plus_nowick   |    n |   n_dates |   win_rate |   mean_net_bps |   ci_lo_bps |   ci_hi_bps |      p |   profit_factor |
|:----------------------|-----:|----------:|-----------:|---------------:|------------:|------------:|-------:|----------------:|
| False                 | 4273 |       961 |     0.4769 |        -5.3975 |    -12.5792 |      1.2456 | 0.123  |          0.9283 |
| True                  | 1573 |       634 |     0.4844 |        -2.8876 |    -13.3937 |      7.6551 | 0.6125 |          0.962  |

## 6. Full interaction (section 3.5)

Stage 2 + `+` opening pattern + beta filter passed, split by gap direction.

| gap_up   |   n |   n_dates |   win_rate |   mean_net_bps |   ci_lo_bps |   ci_hi_bps |      p |   profit_factor |
|:---------|----:|----------:|-----------:|---------------:|------------:|------------:|-------:|----------------:|
| False    | 261 |       185 |     0.4483 |        -1.3674 |    -25.2604 |     21.4563 | 0.9125 |          0.9803 |
| True     | 315 |       226 |     0.5206 |         7.5477 |    -17.3676 |     30.6936 | 0.5275 |          1.1126 |

## 7. Robustness (section 3.6)

### Year by year

|   year |    n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |   chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|-------:|-----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|-------:|---------:|------------------:|---------------:|---------------:|-----------:|
|   2015 |  866 |       158 |              0.5312 |  0.4897 |  0.5714 |        0.1365 |       0.0716 | 3.0757 |   0.0795 |            0.0006 |        -0.001  |         0.0023 |     0.465  |
|   2016 |  885 |       154 |              0.4768 |  0.4381 |  0.5146 |        0.239  |       0.1787 | 1.3391 |   0.2472 |            0.0002 |        -0.0014 |         0.0017 |     0.8195 |
|   2017 |  943 |       154 |              0.4751 |  0.4422 |  0.5079 |        0.1425 |       0.1341 | 1.8164 |   0.1777 |            0.0004 |        -0.0011 |         0.002  |     0.6605 |
|   2018 | 1000 |       169 |              0.509  |  0.4804 |  0.5378 |        0.5375 |       0.5909 | 0.5561 |   0.4558 |            0.0007 |        -0.0011 |         0.0025 |     0.4495 |
|   2019 |  993 |       172 |              0.5086 |  0.4785 |  0.5394 |        0.5755 |       0.6117 | 0.2366 |   0.6267 |            0.001  |        -0.0008 |         0.0029 |     0.308  |
|   2020 | 1000 |       170 |              0.514  |  0.4725 |  0.5565 |        0.495  |       0.3932 | 0.7381 |   0.3903 |           -0.0003 |        -0.0026 |         0.0018 |     0.79   |
|   2021 |  528 |        89 |              0.5152 |  0.4621 |  0.5628 |        0.558  |       0.5139 | 0.5193 |   0.4712 |            0.0021 |        -0.0013 |         0.0056 |     0.2265 |

### Net expectancy by year (after costs)

|   year |    n |   n_dates |   win_rate |   mean_net_bps |   ci_lo_bps |   ci_hi_bps |      p |   profit_factor |
|-------:|-----:|----------:|-----------:|---------------:|------------:|------------:|-------:|----------------:|
|   2015 |  866 |       158 |     0.515  |        -1.2073 |    -17.2378 |     15.7197 | 0.8765 |          0.985  |
|   2016 |  885 |       154 |     0.4588 |        -5.3984 |    -20.6673 |      9.5975 | 0.48   |          0.9367 |
|   2017 |  943 |       154 |     0.4624 |        -3.4301 |    -18.1044 |     13.2814 | 0.679  |          0.9565 |
|   2018 | 1000 |       169 |     0.496  |        -0.0696 |    -18.7048 |     17.4267 | 0.991  |          0.9993 |
|   2019 |  993 |       172 |     0.4965 |         2.79   |    -15.294  |     21.8043 | 0.777  |          1.0312 |
|   2020 | 1000 |       170 |     0.506  |       -10.2647 |    -33.6414 |     11.2837 | 0.3715 |          0.9079 |
|   2021 |  528 |        89 |     0.5    |        13.4527 |    -20.7592 |     48.6439 | 0.453  |          1.1239 |

### Pre- vs post-2020

| era       |    n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |   chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|:----------|-----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|-------:|---------:|------------------:|---------------:|---------------:|-----------:|
| 2015-2019 | 4687 |       807 |              0.5001 |  0.4852 |  0.5152 |        0.9895 |       1      |  0     |   1      |            0.0006 |        -0.0002 |         0.0014 |     0.137  |
| 2020-2025 | 1528 |       259 |              0.5144 |  0.4813 |  0.5455 |        0.3655 |       0.2713 |  1.633 |   0.2013 |            0.0005 |        -0.0014 |         0.0024 |     0.5785 |

### Volatility regime

VIX itself is not available in the connected sources (no continuous daily series covering 2015-2025), so the regime split uses **SPY 21-day trailing realized volatility**, median-split. This is a documented substitution.

| vol_regime   |    n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |   chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|:-------------|-----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|-------:|---------:|------------------:|---------------:|---------------:|-----------:|
| High vol     | 3083 |       573 |              0.4995 |  0.4788 |  0.5205 |        0.9575 |       0.9713 | 0      |   1      |           -0.0003 |        -0.0014 |         0.0008 |      0.656 |
| Low vol      | 3132 |       493 |              0.5077 |  0.4883 |  0.5261 |        0.4275 |       0.401  | 0.7063 |   0.4007 |            0.0014 |         0.0005 |         0.0023 |      0.001 |

### Size subgroups

| size_adtv   |    n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |   chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|:------------|-----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|-------:|---------:|------------------:|---------------:|---------------:|-----------:|
| Small       | 2072 |       691 |              0.4995 |  0.4785 |  0.5216 |         0.965 |       0.9825 | 0.0013 |   0.9716 |            0.0007 |        -0.0004 |         0.0019 |     0.232  |
| Mid         | 2071 |       720 |              0.5123 |  0.4892 |  0.5342 |         0.258 |       0.2719 | 1.1634 |   0.2808 |            0.0001 |        -0.0012 |         0.0013 |     0.8255 |
| Large       | 2072 |       759 |              0.499  |  0.475  |  0.5223 |         0.935 |       0.9475 | 0      |   1      |            0.0009 |        -0.0002 |         0.002  |     0.1425 |

## 8. Transaction cost reality check (section 3.7)

| scenario                     |    n |   mean_net_bps |   ci_lo_bps |   ci_hi_bps |      p |   win_rate |   profit_factor |
|:-----------------------------|-----:|---------------:|------------:|------------:|-------:|-----------:|----------------:|
| gross (no costs)             | 6215 |         5.6536 |     -1.5387 |     12.9991 | 0.1365 |     0.5012 |          1.063  |
| trailing Roll spread         | 6215 |         2.4685 |     -4.7403 |      9.8148 | 0.5005 |     0.4981 |          1.027  |
| Roll + 2bps impact           | 6215 |        -1.5315 |     -8.7403 |      5.8148 | 0.675  |     0.4903 |          0.9836 |
| Roll + 5bps impact           | 6215 |        -7.5315 |    -14.7403 |     -0.1852 | 0.0425 |     0.4771 |          0.922  |
| 2x Roll + 5bps (stressed)    | 6215 |       -10.7167 |    -17.9373 |     -3.3703 | 0.003  |     0.4703 |          0.8909 |
| Corwin-Schultz (upper bound) | 6215 |       -23.0209 |    -30.2074 |    -15.5063 | 0      |     0.4508 |          0.7802 |

### Net expectancy by stage

| stage_name          |    n |   n_dates |   win_rate |   mean_net_bps |   ci_lo_bps |   ci_hi_bps |     p |   profit_factor |
|:--------------------|-----:|----------:|-----------:|---------------:|------------:|------------:|------:|----------------:|
| Stage 2 (Advancing) | 3245 |       856 |     0.4921 |         4.318  |     -4.6804 |     13.2592 | 0.351 |          1.0517 |
| Stage 3 (Topping)   |  830 |       450 |     0.4867 |        -4.6009 |    -22.0838 |     13.1894 | 0.617 |          0.9494 |
| Stage 4 (Declining) | 2081 |       691 |     0.4873 |       -11.2907 |    -24.0663 |      1.1427 | 0.081 |          0.8961 |

## 9. Limitations that constrain this verdict

1. **Survivorship and index-membership bias (severe).** The HF Data Library universe is built from *current* S&P 500 / Nasdaq 100 / Dow 30 membership. Names that were in those indices during 2015-2025 but have since been removed are under-represented, and the ones present were selected partly *because* they survived. The provider discloses survivorship bias pre-2022 directly. Any edge measured here is biased upward, so a weak positive result should be read as consistent with no edge.
2. **BMO vs AMC announcement timing (measured below, not just flagged).** Sigma defines T+1 as the first session after the announcement date. For companies reporting *before* the open, the true reaction day is the announcement date itself, so those events are measured one session late. The Nasdaq feed supplies an explicit time-of-day flag for only 0.0% of the events here. The table below compares volatility elevation on the announcement session against the T+1 session: if the announcement session is also elevated, a material share of the sample is mis-dated.

| session                    |    n |   median_tr_ratio |   mean_excess |   ci_lo |   ci_hi |
|:---------------------------|-----:|------------------:|--------------:|--------:|--------:|
| announcement session (T+0) | 6162 |            1.7963 |        1.2852 |  1.2321 |  1.3403 |
| first session after (T+1)  | 6215 |            1.7399 |        1.2017 |  1.1534 |  1.2521 |

3. **IEX source break (2022-03-01).** Volumes are not directly comparable across the provider's data-source transition, which affects ADV/ADTV filters and any volume-based inference spanning that date.
4. **1-minute bars are not tick data.** The opening-candle classification and the spread estimators are built on 1-minute sampling, not the order book. Corwin-Schultz and Roll are estimators, not quoted spreads.
5. **No borrow costs or short-availability modelling.** Gap-down continuation trades are short trades; their real-world cost is understated.

## 10. Recommended next experiments

1. **Rebuild the universe without survivorship bias.** This is the single highest-value next step: the current universe cannot distinguish a real edge from selection. A point-in-time index-membership source (or a delisted-inclusive vendor) would settle it.
2. **Resolve announcement timing.** Source a BMO/AMC flag (or infer it from which session carries the volume spike) and re-run with the reaction day correctly identified. If a real edge exists, mis-dating a large share of events would be diluting it.
3. **Condition on surprise magnitude.** The Nasdaq feed carries actual vs forecast EPS; the continuation hypothesis is much more plausible for large-surprise events than for the pooled sample tested here.
4. **Test a shorter holding window.** Open-to-close pools the informative first hour with an uninformative afternoon. Test open-to-11:00 and open-to-first-hour exits.
5. **Re-examine the opening-pattern definition.** The labels here are a faithful but necessarily interpreted reading of Sigma's prose; a sensitivity sweep over the wick/body thresholds would show whether any pattern effect is robust or an artefact of one cut.

---

_Generated by Lambda (Strategy Validator). Every table in this report is reproducible from `lambda_strategy_validation/` and the CSVs in `lambda_data/tables/`._