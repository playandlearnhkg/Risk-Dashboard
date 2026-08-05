# Lambda Validation Report

**Edge:** T+1 Post-Earnings Volatility + Gap Continuation + Relative Beta + Opening 5-Minute Pattern, conditional on Minervini Stage

**Verdict: REJECT**

- Events analysed: **1,436** earnings T+1 sessions
- Tickers: **149** | Distinct event dates: **358** | Span: 2015-01-16 to 2017-11-01
- Gross continuation expectancy: **3.76 bps**; after measured spread + 2 bps impact: **-39.23 bps** (95% CI -50.45 to -27.14, clustered p = 0.000)

## Decision reasoning

Thresholds were fixed before the results were computed:

- Headline net expectancy (measured + 2bps impact): -39.23 bps/trade (threshold >= 5.0), clustered p = 0.000 (threshold <= 0.05), 95% CI lower bound = -50.45 bps.
- Years with positive net expectancy: 0% (0/3); threshold for PROMOTE >= 70%.
- Stages with positive net expectancy: 0/3 (threshold for PROMOTE = all 3).

## 1. Data and method

| Item | Value |
|---|---|
| Price/volume source | HF Data Library 1-minute bars, aggregated to daily and to 5-minute |
| Earnings dates | Nasdaq calendar API, confirmed-actual rows only |
| Market cap | SEC EDGAR point-in-time shares outstanding x split-adjusted close |
| Panel rows before filters | 664,026 |
| Panel rows passing universe filters | 294,329 |
| Tickers with direct market cap | 224 |
| Tickers using liquidity proxy for market cap | 111 |

**Market-cap proxy validation.** For tickers where SEC market cap *is* available, only **4.63%** of ticker-days that pass the $50M ADTV filter have market cap at or below $3B. The ADTV filter is therefore a tight substitute for the market-cap filter, which is why delisted and renamed tickers (whose SEC ticker mapping no longer resolves) are kept via the proxy rather than dropped — dropping them would compound the survivorship bias described below.

**Inference.** Earnings T+1 observations cluster by calendar date — dozens of firms report the same evening and share the next day's market move. All confidence intervals and p-values here come from a **date-clustered bootstrap** (resampling whole trading dates). Independence-assuming binomial p-values are shown alongside for contrast and are systematically too optimistic.

**Costs.** Each event is charged its **own measured spread** (Corwin-Schultz, falling back to Roll) rather than a global constant, on both legs, plus an explicit impact allowance.

## 2. Volatility elevation on T+1 (section 3.1)

Ratio of the T+1 value to the median non-earnings day for the same ticker in the same calendar quarter. A ratio of 1.0 means no elevation. `mean_excess` is the mean of (ratio - 1) with clustered CI.

| metric       |    n |   median_ratio |   mean_ratio |   mean_excess |   ci_lo |   ci_hi |   p |
|:-------------|-----:|---------------:|-------------:|--------------:|--------:|--------:|----:|
| true_range   | 1436 |         1.735  |       2.2859 |        1.2859 |  1.1927 |  1.386  |   0 |
| atr14        | 1436 |         1.1021 |       1.1387 |        0.1387 |  0.1206 |  0.1582 |   0 |
| tr_pct       | 1436 |         1.7246 |       2.2887 |        1.2887 |  1.1935 |  1.3891 |   0 |
| hl_over_open | 1436 |         1.6711 |       1.8719 |        0.8719 |  0.8184 |  0.9254 |   0 |
| rv_5min      | 1436 |         2.3998 |       3.2544 |        2.2544 |  2.0809 |  2.439  |   0 |
| parkinson    | 1436 |         2.8065 |       4.2062 |        3.2062 |  2.9414 |  3.4678 |   0 |

### By stage

| metric       |   n |   median_ratio |   mean_ratio |   mean_excess |   ci_lo |   ci_hi |   p | stage_name          |
|:-------------|----:|---------------:|-------------:|--------------:|--------:|--------:|----:|:--------------------|
| true_range   | 787 |         1.8    |       2.3725 |        1.3725 |  1.2506 |  1.5031 |   0 | Stage 2 (Advancing) |
| atr14        | 787 |         1.0829 |       1.1141 |        0.1141 |  0.0959 |  0.1341 |   0 | Stage 2 (Advancing) |
| tr_pct       | 787 |         1.7896 |       2.3654 |        1.3654 |  1.2445 |  1.4971 |   0 | Stage 2 (Advancing) |
| hl_over_open | 787 |         1.6788 |       1.879  |        0.879  |  0.8129 |  0.9475 |   0 | Stage 2 (Advancing) |
| rv_5min      | 787 |         2.3981 |       3.3327 |        2.3327 |  2.1234 |  2.5308 |   0 | Stage 2 (Advancing) |
| parkinson    | 787 |         2.8423 |       4.2579 |        3.2579 |  2.9491 |  3.5835 |   0 | Stage 2 (Advancing) |
| true_range   | 185 |         1.68   |       2.1677 |        1.1677 |  0.9549 |  1.4359 |   0 | Stage 3 (Topping)   |
| atr14        | 185 |         1.0873 |       1.11   |        0.11   |  0.0815 |  0.1431 |   0 | Stage 3 (Topping)   |
| tr_pct       | 185 |         1.6184 |       2.1202 |        1.1202 |  0.9184 |  1.3631 |   0 | Stage 3 (Topping)   |
| hl_over_open | 185 |         1.6134 |       1.8064 |        0.8064 |  0.7017 |  0.9223 |   0 | Stage 3 (Topping)   |
| rv_5min      | 185 |         2.3314 |       2.9615 |        1.9615 |  1.6549 |  2.3181 |   0 | Stage 3 (Topping)   |
| parkinson    | 185 |         2.5966 |       3.7551 |        2.7551 |  2.321  |  3.253  |   0 | Stage 3 (Topping)   |
| true_range   | 458 |         1.6767 |       2.1949 |        1.1949 |  1.0293 |  1.3602 |   0 | Stage 4 (Declining) |
| atr14        | 458 |         1.1603 |       1.1919 |        0.1919 |  0.1607 |  0.2225 |   0 | Stage 4 (Declining) |
| tr_pct       | 458 |         1.6936 |       2.2345 |        1.2345 |  1.0703 |  1.4032 |   0 | Stage 4 (Declining) |
| hl_over_open | 458 |         1.6838 |       1.891  |        0.891  |  0.8023 |  0.9777 |   0 | Stage 4 (Declining) |
| rv_5min      | 458 |         2.4438 |       3.2534 |        2.2534 |  1.9283 |  2.688  |   0 | Stage 4 (Declining) |
| parkinson    | 458 |         2.8427 |       4.326  |        3.326  |  2.8594 |  3.8409 |   0 | Stage 4 (Declining) |

### By size (ADTV terciles)

| metric   |   n |   median_ratio |   mean_ratio |   mean_excess |   ci_lo |   ci_hi |   p | size_adtv   |
|:---------|----:|---------------:|-------------:|--------------:|--------:|--------:|----:|:------------|
| tr_pct   | 479 |         1.7375 |       2.3023 |        1.3023 |  1.1565 |  1.4543 |   0 | Small       |
| rv_5min  | 479 |         2.4697 |       3.7031 |        2.7031 |  2.3487 |  3.131  |   0 | Small       |
| tr_pct   | 478 |         1.5698 |       2.085  |        1.085  |  0.9487 |  1.2278 |   0 | Mid         |
| rv_5min  | 478 |         2.288  |       3.0846 |        2.0846 |  1.8396 |  2.3663 |   0 | Mid         |
| tr_pct   | 479 |         1.9632 |       2.4785 |        1.4785 |  1.3021 |  1.6587 |   0 | Large       |
| rv_5min  | 479 |         2.4341 |       2.9753 |        1.9753 |  1.7679 |  2.1713 |   0 | Large       |

## 3. Four-quadrant gap x intraday (section 3.2)

Counts:

| gap     |   IntraDown |   IntraUp |
|:--------|------------:|----------:|
| GapDown |         345 |       368 |
| GapUp   |         349 |       374 |

Continuation = the T+1 open-to-close move has the same sign as the overnight gap. `mean_signed_o2c` is the gross return of trading in the gap direction from open to close.

|    n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |   chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|-----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|-------:|---------:|------------------:|---------------:|---------------:|-----------:|
| 1436 |       358 |              0.5007 |  0.4743 |  0.5285 |         0.959 |       0.9789 |      0 |        1 |            0.0004 |        -0.0007 |         0.0015 |       0.53 |

### Stratified by stage

| stage_name          |   n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |   chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|:--------------------|----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|-------:|---------:|------------------:|---------------:|---------------:|-----------:|
| Stage 2 (Advancing) | 787 |       278 |              0.493  |  0.4577 |  0.5269 |        0.6815 |       0.7215 | 0.0788 |   0.779  |            0.0007 |        -0.0007 |         0.0021 |     0.338  |
| Stage 3 (Topping)   | 185 |       118 |              0.5405 |  0.462  |  0.6186 |        0.315  |       0.3033 | 1.2049 |   0.2723 |            0.0023 |        -0.0008 |         0.0054 |     0.1635 |
| Stage 4 (Declining) | 458 |       213 |              0.4956 |  0.4478 |  0.5402 |        0.8555 |       0.8885 | 0.0049 |   0.9439 |           -0.001  |        -0.0033 |         0.0012 |     0.388  |

### By gap direction

| gap_up   |   n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial | chi2   | p_chi2   |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|:---------|----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|:-------|:---------|------------------:|---------------:|---------------:|-----------:|
| False    | 713 |       260 |              0.4839 |  0.444  |  0.5231 |         0.426 |       0.41   |        |          |           -0.0007 |        -0.0024 |         0.0011 |     0.45   |
| True     | 723 |       281 |              0.5173 |  0.4735 |  0.5599 |         0.438 |       0.3721 |        |          |            0.0014 |        -0.0006 |         0.0034 |     0.1645 |

## 4. Relative beta filter (section 3.3)

An event is flagged low-quality when the stock's T+1 open-to-close return has the opposite sign to **both** SPY and its sector ETF.

|    n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |   chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p | cohort                   |
|-----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|-------:|---------:|------------------:|---------------:|---------------:|-----------:|:-------------------------|
| 1388 |       358 |              0.5036 |  0.4762 |  0.5315 |        0.7955 |       0.8091 | 0.0398 |   0.8418 |            0.0004 |        -0.0007 |         0.0016 |     0.4915 | all (benchmarked)        |
| 1029 |       314 |              0.5073 |  0.4724 |  0.5416 |        0.658  |       0.6625 | 0.1216 |   0.7273 |            0.0002 |        -0.0013 |         0.0016 |     0.7655 | beta filter applied      |
|  359 |       196 |              0.493  |  0.4354 |  0.5496 |        0.805  |       0.8328 | 0.0365 |   0.8484 |            0.001  |        -0.0014 |         0.0034 |     0.411  | excluded (opposite both) |

### Filtered cohort, by stage

| stage_name          |   n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |   chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|:--------------------|----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|-------:|---------:|------------------:|---------------:|---------------:|-----------:|
| Stage 2 (Advancing) | 560 |       236 |              0.4964 |  0.4529 |  0.5374 |        0.8595 |       0.8991 | 0.0053 |   0.9421 |            0.0007 |        -0.001  |         0.0024 |     0.4265 |
| Stage 3 (Topping)   | 125 |        91 |              0.536  |  0.4412 |  0.6325 |        0.4575 |       0.4744 | 0.7664 |   0.3813 |            0.0023 |        -0.0011 |         0.0058 |     0.191  |
| Stage 4 (Declining) | 339 |       179 |              0.5103 |  0.4548 |  0.565  |        0.6995 |       0.7446 | 0.0364 |   0.8488 |           -0.0014 |        -0.0044 |         0.0012 |     0.3125 |

## 5. First three 5-minute candles (section 3.4)

| pattern                |   n |   share |
|:-----------------------|----:|--------:|
| Early Reversal-        | 687 |  0.5108 |
| Indecision0            | 325 |  0.2416 |
| Moderate Continuation+ | 218 |  0.1621 |
| Strong Continuation+   | 115 |  0.0855 |

### Continuation probability by pattern

| pattern                |   n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |    chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|:-----------------------|----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|--------:|---------:|------------------:|---------------:|---------------:|-----------:|
| Early Reversal-        | 687 |       273 |              0.3406 |  0.306  |  0.3754 |         0     |       0      | 68.9301 |   0      |           -0.0069 |        -0.0084 |        -0.0055 |      0     |
| Indecision0            | 325 |       170 |              0.56   |  0.5031 |  0.6132 |         0.033 |       0.0349 |  4.2733 |   0.0387 |            0.0016 |        -0.0004 |         0.0036 |      0.128 |
| Moderate Continuation+ | 218 |       138 |              0.7982 |  0.7414 |  0.8509 |         0     |       0      | 74.8694 |   0      |            0.0146 |         0.0119 |         0.0173 |      0     |
| Strong Continuation+   | 115 |        89 |              0.8348 |  0.7395 |  0.9115 |         0     |       0      | 49.0662 |   0      |            0.0176 |         0.0132 |         0.0219 |      0     |

### Net expectancy by pattern (after measured spread + 2 bps)

| pattern                |   n |   n_dates |   win_rate |   mean_net_bps |   ci_lo_bps |   ci_hi_bps |      p |   profit_factor |
|:-----------------------|----:|----------:|-----------:|---------------:|------------:|------------:|-------:|----------------:|
| Early Reversal-        | 687 |       273 |     0.2358 |      -112.199  |   -126.755  |    -97.9032 | 0      |          0.2135 |
| Indecision0            | 325 |       170 |     0.4    |       -30.9874 |    -51.3444 |    -10.762  | 0.0045 |          0.6517 |
| Moderate Continuation+ | 218 |       138 |     0.711  |       103.864  |     77.355  |    130.459  | 0      |          4.5425 |
| Strong Continuation+   | 115 |        89 |     0.7391 |       136.646  |     90.8895 |    182.728  | 0      |          5.5709 |

### `+` patterns vs everything else

| pattern_plus   |    n |   n_dates |   win_rate |   mean_net_bps |   ci_lo_bps |   ci_hi_bps |   p |   profit_factor |
|:---------------|-----:|----------:|-----------:|---------------:|------------:|------------:|----:|----------------:|
| False          | 1012 |       315 |     0.2885 |       -86.1182 |    -98.905  |    -74.2062 |   0 |          0.3134 |
| True           |  333 |       178 |     0.7207 |       115.185  |     91.4691 |    136.86   |   0 |          4.9022 |

## 6. Full interaction (section 3.5)

Stage 2 + `+` opening pattern + beta filter passed, split by gap direction.

| gap_up   |   n |   n_dates |   win_rate |   mean_net_bps |   ci_lo_bps |   ci_hi_bps |      p |   profit_factor |
|:---------|----:|----------:|-----------:|---------------:|------------:|------------:|-------:|----------------:|
| False    |  55 |        44 |     0.6    |        65.4681 |      8.2405 |     131.695 | 0.0425 |          2.6582 |
| True     |  78 |        62 |     0.7179 |       127.084  |     79.0781 |     174.127 | 0      |          5.8181 |

## 7. Robustness (section 3.6)

### Year by year

|   year |   n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |   chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|-------:|----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|-------:|---------:|------------------:|---------------:|---------------:|-----------:|
|   2015 | 469 |       122 |              0.5522 |  0.5022 |  0.6005 |         0.036 |       0.0266 | 4.6238 |   0.0315 |            0.0015 |        -0.0009 |         0.0037 |     0.197  |
|   2016 | 499 |       126 |              0.4689 |  0.4236 |  0.5181 |         0.211 |       0.1792 | 1.3329 |   0.2483 |           -0.0005 |        -0.0023 |         0.0015 |     0.5745 |
|   2017 | 468 |       110 |              0.4829 |  0.4439 |  0.5204 |         0.388 |       0.4881 | 0.4367 |   0.5087 |            0.0003 |        -0.0017 |         0.0023 |     0.793  |

### Net expectancy by year (after costs)

|   year |   n |   n_dates |   win_rate |   mean_net_bps |   ci_lo_bps |   ci_hi_bps |      p |   profit_factor |
|-------:|----:|----------:|-----------:|---------------:|------------:|------------:|-------:|----------------:|
|   2015 | 469 |       122 |     0.4115 |       -30.439  |    -53.8064 |     -8.3924 | 0.011  |          0.6935 |
|   2016 | 499 |       126 |     0.3587 |       -53.6663 |    -71.8513 |    -33.6337 | 0      |          0.5275 |
|   2017 | 468 |       110 |     0.3932 |       -32.6618 |    -51.2552 |    -13.5328 | 0.0005 |          0.6598 |

### Pre- vs post-2020

| era       |    n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |   chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|:----------|-----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|-------:|---------:|------------------:|---------------:|---------------:|-----------:|
| 2015-2019 | 1436 |       358 |              0.5007 |  0.4743 |  0.5285 |         0.959 |       0.9789 |      0 |        1 |            0.0004 |        -0.0007 |         0.0015 |       0.53 |

### Volatility regime

VIX itself is not available in the connected sources (no continuous daily series covering 2015-2025), so the regime split uses **SPY 21-day trailing realized volatility**, median-split. This is a documented substitution.

| vol_regime   |   n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |   chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|:-------------|----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|-------:|---------:|------------------:|---------------:|---------------:|-----------:|
| High vol     | 717 |       188 |              0.516  |  0.4699 |  0.5578 |        0.49   |       0.4113 | 0.677  |   0.4106 |            0.0004 |        -0.0013 |         0.0022 |     0.6225 |
| Low vol      | 719 |       170 |              0.4854 |  0.4523 |  0.5178 |        0.3855 |       0.4558 | 0.4687 |   0.4936 |            0.0003 |        -0.0012 |         0.002  |     0.709  |

### Size subgroups

| size_adtv   |   n |   n_dates |   continuation_rate |   ci_lo |   ci_hi |   p_clustered |   p_binomial |   chi2 |   p_chi2 |   mean_signed_o2c |   signed_ci_lo |   signed_ci_hi |   signed_p |
|:------------|----:|----------:|--------------------:|--------:|--------:|--------------:|-------------:|-------:|---------:|------------------:|---------------:|---------------:|-----------:|
| Small       | 479 |       221 |              0.5115 |  0.4667 |  0.5595 |        0.6245 |       0.6478 | 0.1585 |   0.6905 |            0.0011 |        -0.0009 |         0.0031 |     0.2755 |
| Mid         | 478 |       215 |              0.5042 |  0.4592 |  0.5489 |        0.842  |       0.8909 | 0.0131 |   0.9088 |            0.0002 |        -0.0017 |         0.0021 |     0.835  |
| Large       | 479 |       248 |              0.4864 |  0.4398 |  0.5312 |        0.578  |       0.5835 | 0.2457 |   0.6201 |           -0.0002 |        -0.0022 |         0.0018 |     0.869  |

## 8. Transaction cost reality check (section 3.7)

| scenario               |    n |   mean_net_bps |   ci_lo_bps |   ci_hi_bps |    p |   win_rate |   profit_factor |
|:-----------------------|-----:|---------------:|------------:|------------:|-----:|-----------:|----------------:|
| gross (no costs)       | 1436 |         3.7646 |     -7.308  |     15.334  | 0.53 |     0.4986 |          1.0489 |
| measured spread        | 1436 |       -35.2348 |    -46.4529 |    -23.1352 | 0    |     0.3955 |          0.6503 |
| measured + 2bps impact | 1436 |       -39.2348 |    -50.4529 |    -27.1352 | 0    |     0.3872 |          0.6198 |
| measured + 5bps impact | 1436 |       -45.2348 |    -56.4529 |    -33.1352 | 0    |     0.374  |          0.5769 |
| 1.5x spread + 5bps     | 1436 |       -64.7344 |    -76.7695 |    -52.4775 | 0    |     0.3447 |          0.4684 |

### Net expectancy by stage

| stage_name          |   n |   n_dates |   win_rate |   mean_net_bps |   ci_lo_bps |   ci_hi_bps |     p |   profit_factor |
|:--------------------|----:|----------:|-----------:|---------------:|------------:|------------:|------:|----------------:|
| Stage 2 (Advancing) | 787 |       278 |     0.3837 |       -31.0445 |    -44.5566 |    -17.7211 | 0     |          0.654  |
| Stage 3 (Topping)   | 185 |       118 |     0.4    |       -27.4348 |    -59.5311 |      3.9805 | 0.096 |          0.6979 |
| Stage 4 (Declining) | 458 |       213 |     0.3886 |       -58.6871 |    -82.1727 |    -37.543  | 0     |          0.5549 |

## 9. Limitations that constrain this verdict

1. **Survivorship and index-membership bias (severe).** The HF Data Library universe is built from *current* S&P 500 / Nasdaq 100 / Dow 30 membership. Names that were in those indices during 2015-2025 but have since been removed are under-represented, and the ones present were selected partly *because* they survived. The provider discloses survivorship bias pre-2022 directly. Any edge measured here is biased upward, so a weak positive result should be read as consistent with no edge.
2. **BMO vs AMC announcement timing.** Sigma defines T+1 as the first session after the announcement date. For companies reporting *before* the open, the true reaction day is the announcement date itself, so those events are measured one session late. The Nasdaq feed supplies an explicit time-of-day flag for only a minority of historical rows (0.0% of events here), so the contamination cannot be fully removed.
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