# Lambda — Entry at 09:35

Re-test with entry immediately after the first 5-minute candle closes, under the same strict no-look-ahead discipline.

## Rules

| Input | Definition |
|---|---|
| Signal | The 09:30–09:35 candle closes in the gap direction |
| Entry | **Open of the 09:35 bar** (minute 5) — the first print *after* the signal candle completes |
| SPY / Sector | Open → 09:35 only |
| Stage | Prior session |
| ATR / Gap-ATR | Prior-session ATR(14); gap in price terms ÷ that ATR |

Sample: **16,855** events with a usable 09:35 price, of which **7,336** fire the Continuation signal and **1,029** also have Gap/ATR > 2.0. Net figures subtract the **6.6 bps** median round-trip cost established earlier. Cells with n < 150 are flagged. All p-values are two-sided from a date-clustered bootstrap.

> **Why the open of the next bar, not `c1_close`.** The signal is derived from `c1_close`, so filling at that same print would mean transacting on the exact tick that generated the signal — if that print sat on the offer, the rule would be selecting an upward-biased entry price and the measured forward return would inherit the reversal. Taking the open of the 09:35 bar separates signal and fill entirely. 15,595 of 16,855 entries come from a real 09:35 print; the remainder had no trade in that exact minute and use the prevailing price from an earlier real print.

> **Look-ahead guard.** The forward-filled price series is seeded from `session_open`, the first Open of the session. For a name that does not trade until well after the bell, that seed is a price from *after* the intended entry — so any event with no real print by 09:35 would enter at a future price. **603 such events are dropped outright.** They were never in the pattern cohorts (which require real 09:30–09:35 candle data) but they were contaminating the All-events rows, where they averaged roughly −95 bps.

## 1. Holding period performance from 09:35

| Window         | Cohort                        |     n | Win rate   | Wilson lo   | Wilson hi   |   Gross (bps) |     p |   NET (bps) |   net p | n<150?   |
|:---------------|:------------------------------|------:|:-----------|:------------|:------------|--------------:|------:|------------:|--------:|:---------|
| 09:35 -> 09:40 | All events                    | 16412 | 52.1%      | 51.3%       | 52.9%       |           3.7 | 0     |        -2.9 |   0     |          |
| 09:35 -> 09:40 | Gap Up                        |  8614 | 51.2%      | 50.2%       | 52.3%       |           2.7 | 0.018 |        -3.9 |   0.001 |          |
| 09:35 -> 09:40 | Gap Down                      |  7798 | 53.1%      | 52.0%       | 54.2%       |           4.8 | 0     |        -1.8 |   0.127 |          |
| 09:35 -> 09:40 | Simple Continuation           |  7178 | 57.5%      | 56.3%       | 58.6%       |          11.8 | 0     |         5.2 |   0     |          |
| 09:35 -> 09:40 | Simple Continuation, Gap Up   |  3769 | 57.3%      | 55.7%       | 58.8%       |          11.1 | 0     |         4.5 |   0.004 |          |
| 09:35 -> 09:40 | Simple Continuation, Gap Down |  3409 | 57.7%      | 56.1%       | 59.4%       |          12.6 | 0     |         6   |   0     |          |
| 09:35 -> 09:45 | All events                    | 16653 | 52.7%      | 51.9%       | 53.4%       |           5.9 | 0     |        -0.7 |   0.468 |          |
| 09:35 -> 09:45 | Gap Up                        |  8759 | 51.5%      | 50.5%       | 52.5%       |           4.6 | 0.001 |        -2   |   0.157 |          |
| 09:35 -> 09:45 | Gap Down                      |  7894 | 53.9%      | 52.8%       | 55.0%       |           7.4 | 0     |         0.8 |   0.641 |          |
| 09:35 -> 09:45 | Simple Continuation           |  7247 | 57.9%      | 56.7%       | 59.0%       |          18.3 | 0     |        11.7 |   0     |          |
| 09:35 -> 09:45 | Simple Continuation, Gap Up   |  3806 | 56.8%      | 55.2%       | 58.3%       |          17.1 | 0     |        10.5 |   0     |          |
| 09:35 -> 09:45 | Simple Continuation, Gap Down |  3441 | 59.1%      | 57.4%       | 60.7%       |          19.8 | 0     |        13.2 |   0     |          |
| 09:35 -> 09:50 | All events                    | 16719 | 52.6%      | 51.9%       | 53.4%       |           8.9 | 0     |         2.3 |   0.044 |          |
| 09:35 -> 09:50 | Gap Up                        |  8792 | 51.1%      | 50.0%       | 52.1%       |           6.4 | 0     |        -0.2 |   0.866 |          |
| 09:35 -> 09:50 | Gap Down                      |  7927 | 54.4%      | 53.3%       | 55.5%       |          11.7 | 0     |         5.1 |   0.007 |          |
| 09:35 -> 09:50 | Simple Continuation           |  7272 | 58.9%      | 57.7%       | 60.0%       |          25.2 | 0     |        18.6 |   0     |          |
| 09:35 -> 09:50 | Simple Continuation, Gap Up   |  3820 | 57.5%      | 55.9%       | 59.0%       |          22.5 | 0     |        15.9 |   0     |          |
| 09:35 -> 09:50 | Simple Continuation, Gap Down |  3452 | 60.4%      | 58.7%       | 62.0%       |          28.1 | 0     |        21.5 |   0     |          |
| 09:35 -> 10:35 | All events                    | 16751 | 52.4%      | 51.6%       | 53.1%       |          10.3 | 0     |         3.7 |   0.02  |          |
| 09:35 -> 10:35 | Gap Up                        |  8808 | 51.0%      | 49.9%       | 52.0%       |           6.6 | 0.01  |         0   |   0.988 |          |
| 09:35 -> 10:35 | Gap Down                      |  7943 | 53.9%      | 52.8%       | 55.0%       |          14.4 | 0     |         7.8 |   0.006 |          |
| 09:35 -> 10:35 | Simple Continuation           |  7295 | 57.1%      | 56.0%       | 58.2%       |          29.5 | 0     |        22.9 |   0     |          |
| 09:35 -> 10:35 | Simple Continuation, Gap Up   |  3836 | 56.0%      | 54.5%       | 57.6%       |          26.9 | 0     |        20.3 |   0     |          |
| 09:35 -> 10:35 | Simple Continuation, Gap Down |  3459 | 58.3%      | 56.6%       | 59.9%       |          32.4 | 0     |        25.8 |   0     |          |
| 09:35 -> Close | All events                    | 16782 | 51.4%      | 50.6%       | 52.2%       |          10.5 | 0     |         3.9 |   0.107 |          |
| 09:35 -> Close | Gap Up                        |  8826 | 50.7%      | 49.7%       | 51.8%       |           8.1 | 0.049 |         1.5 |   0.697 |          |
| 09:35 -> Close | Gap Down                      |  7956 | 52.2%      | 51.1%       | 53.3%       |          13.2 | 0.001 |         6.6 |   0.132 |          |
| 09:35 -> Close | Simple Continuation           |  7311 | 55.7%      | 54.5%       | 56.8%       |          31.7 | 0     |        25.1 |   0     |          |
| 09:35 -> Close | Simple Continuation, Gap Up   |  3840 | 55.7%      | 54.1%       | 57.2%       |          31.7 | 0     |        25.1 |   0     |          |
| 09:35 -> Close | Simple Continuation, Gap Down |  3471 | 55.7%      | 54.0%       | 57.3%       |          31.6 | 0     |        25   |   0     |          |

## 2. Context filters (each tested alone, no combinations)

Simple Continuation cohort only.

| Window         | Filter       | Bucket          |    n | Win rate   |   Gross (bps) |   p |   NET (bps) |   net p | n<150?   |
|:---------------|:-------------|:----------------|-----:|:-----------|--------------:|----:|------------:|--------:|:---------|
| 09:35 -> 09:40 | spy_agree    | SPY Agree       | 3680 | 56.5%      |          11.1 |   0 |         4.5 |   0.006 |          |
| 09:35 -> 09:40 | spy_agree    | SPY Disagree    | 3211 | 58.7%      |          13.1 |   0 |         6.5 |   0     |          |
| 09:35 -> 09:40 | sector_agree | Sector Agree    | 4175 | 57.7%      |          12.2 |   0 |         5.6 |   0     |          |
| 09:35 -> 09:40 | sector_agree | Sector Disagree | 2493 | 57.4%      |          10.7 |   0 |         4.1 |   0.027 |          |
| 09:35 -> 09:40 | stage_group  | Stage 2         | 3461 | 58.4%      |          13.5 |   0 |         6.9 |   0     |          |
| 09:35 -> 09:40 | stage_group  | Stage 3+4       | 3657 | 56.7%      |          10.3 |   0 |         3.7 |   0.028 |          |
| 09:35 -> 09:45 | spy_agree    | SPY Agree       | 3708 | 57.7%      |          18.3 |   0 |        11.7 |   0     |          |
| 09:35 -> 09:45 | spy_agree    | SPY Disagree    | 3250 | 58.3%      |          18.5 |   0 |        11.9 |   0     |          |
| 09:35 -> 09:45 | sector_agree | Sector Agree    | 4210 | 58.8%      |          20.1 |   0 |        13.5 |   0     |          |
| 09:35 -> 09:45 | sector_agree | Sector Disagree | 2521 | 57.0%      |          15.9 |   0 |         9.3 |   0     |          |
| 09:35 -> 09:45 | stage_group  | Stage 2         | 3495 | 58.8%      |          19.4 |   0 |        12.8 |   0     |          |
| 09:35 -> 09:45 | stage_group  | Stage 3+4       | 3692 | 56.9%      |          17.2 |   0 |        10.6 |   0     |          |
| 09:35 -> 09:50 | spy_agree    | SPY Agree       | 3721 | 59.0%      |          25.9 |   0 |        19.3 |   0     |          |
| 09:35 -> 09:50 | spy_agree    | SPY Disagree    | 3259 | 58.9%      |          25   |   0 |        18.4 |   0     |          |
| 09:35 -> 09:50 | sector_agree | Sector Agree    | 4227 | 59.6%      |          26.5 |   0 |        19.9 |   0     |          |
| 09:35 -> 09:50 | sector_agree | Sector Disagree | 2525 | 58.6%      |          24.4 |   0 |        17.8 |   0     |          |
| 09:35 -> 09:50 | stage_group  | Stage 2         | 3501 | 59.3%      |          25.7 |   0 |        19.1 |   0     |          |
| 09:35 -> 09:50 | stage_group  | Stage 3+4       | 3711 | 58.4%      |          24.4 |   0 |        17.8 |   0     |          |
| 09:35 -> 10:35 | spy_agree    | SPY Agree       | 3735 | 56.9%      |          29.6 |   0 |        23   |   0     |          |
| 09:35 -> 10:35 | spy_agree    | SPY Disagree    | 3268 | 57.3%      |          29.2 |   0 |        22.6 |   0     |          |
| 09:35 -> 10:35 | sector_agree | Sector Agree    | 4237 | 57.4%      |          28.2 |   0 |        21.6 |   0     |          |
| 09:35 -> 10:35 | sector_agree | Sector Disagree | 2536 | 57.2%      |          27.9 |   0 |        21.3 |   0     |          |
| 09:35 -> 10:35 | stage_group  | Stage 2         | 3512 | 56.8%      |          29.6 |   0 |        23   |   0     |          |
| 09:35 -> 10:35 | stage_group  | Stage 3+4       | 3723 | 57.5%      |          29.4 |   0 |        22.8 |   0     |          |
| 09:35 -> Close | spy_agree    | SPY Agree       | 3747 | 55.8%      |          34.1 |   0 |        27.5 |   0     |          |
| 09:35 -> Close | spy_agree    | SPY Disagree    | 3270 | 55.1%      |          28   |   0 |        21.4 |   0     |          |
| 09:35 -> Close | sector_agree | Sector Agree    | 4255 | 56.0%      |          30.8 |   0 |        24.2 |   0     |          |
| 09:35 -> Close | sector_agree | Sector Disagree | 2534 | 56.0%      |          29.8 |   0 |        23.2 |   0     |          |
| 09:35 -> Close | stage_group  | Stage 2         | 3522 | 55.2%      |          29.4 |   0 |        22.8 |   0     |          |
| 09:35 -> Close | stage_group  | Stage 3+4       | 3729 | 55.9%      |          31.4 |   0 |        24.8 |   0     |          |

## 3. Gap / ATR buckets (Simple Continuation)

| Window         | Gap/ATR         |    n | Win rate   | Wilson lo   | Wilson hi   |   Gross (bps) |     p |   NET (bps) |   net p | n<150?   |
|:---------------|:----------------|-----:|:-----------|:------------|:------------|--------------:|------:|------------:|--------:|:---------|
| 09:35 -> 09:40 | Gap/ATR < 1.0   | 5275 | 58.3%      | 56.9%       | 59.6%       |          12.1 | 0     |         5.5 |   0     |          |
| 09:35 -> 09:40 | Gap/ATR 1.0-2.0 |  880 | 52.0%      | 48.7%       | 55.3%       |           5.4 | 0.165 |        -1.2 |   0.757 |          |
| 09:35 -> 09:40 | Gap/ATR > 2.0   | 1023 | 58.2%      | 55.1%       | 61.1%       |          15.8 | 0     |         9.2 |   0.037 |          |
| 09:35 -> 09:45 | Gap/ATR < 1.0   | 5340 | 58.8%      | 57.5%       | 60.2%       |          18.9 | 0     |        12.3 |   0     |          |
| 09:35 -> 09:45 | Gap/ATR 1.0-2.0 |  881 | 51.5%      | 48.2%       | 54.8%       |           5.3 | 0.25  |        -1.3 |   0.748 |          |
| 09:35 -> 09:45 | Gap/ATR > 2.0   | 1026 | 58.3%      | 55.2%       | 61.3%       |          26.8 | 0     |        20.2 |   0     |          |
| 09:35 -> 09:50 | Gap/ATR < 1.0   | 5363 | 59.4%      | 58.1%       | 60.7%       |          24.2 | 0     |        17.6 |   0     |          |
| 09:35 -> 09:50 | Gap/ATR 1.0-2.0 |  883 | 53.9%      | 50.6%       | 57.2%       |          14.9 | 0.003 |         8.3 |   0.121 |          |
| 09:35 -> 09:50 | Gap/ATR > 2.0   | 1026 | 60.1%      | 57.1%       | 63.1%       |          38.8 | 0     |        32.2 |   0     |          |
| 09:35 -> 10:35 | Gap/ATR < 1.0   | 5387 | 57.0%      | 55.7%       | 58.3%       |          26.9 | 0     |        20.3 |   0     |          |
| 09:35 -> 10:35 | Gap/ATR 1.0-2.0 |  881 | 53.9%      | 50.6%       | 57.2%       |          18.8 | 0.009 |        12.2 |   0.102 |          |
| 09:35 -> 10:35 | Gap/ATR > 2.0   | 1027 | 60.4%      | 57.3%       | 63.3%       |          52.6 | 0     |        46   |   0     |          |
| 09:35 -> Close | Gap/ATR < 1.0   | 5397 | 55.4%      | 54.1%       | 56.8%       |          26.4 | 0     |        19.8 |   0     |          |
| 09:35 -> Close | Gap/ATR 1.0-2.0 |  885 | 53.4%      | 50.2%       | 56.7%       |          25.9 | 0.011 |        19.3 |   0.069 |          |
| 09:35 -> Close | Gap/ATR > 2.0   | 1029 | 58.8%      | 55.8%       | 61.8%       |          64.6 | 0     |        58   |   0     |          |

## 4. Distribution — 5, 10 and 15 minute windows

| Window         | Cohort                             |    n |   Mean |   Median |    P10 |   P25 |   P75 |   P90 |   >+100 bps |   <−100 bps |
|:---------------|:-----------------------------------|-----:|-------:|---------:|-------:|------:|------:|------:|------------:|------------:|
| 09:35 -> 09:40 | Simple Continuation                | 7178 |   11.8 |     10.4 |  -77.1 | -28.7 |  52.3 | 105.1 |     10.9919 |     6.9518  |
| 09:35 -> 09:40 | Simple Continuation, Gap/ATR > 2.0 | 1023 |   15.8 |     19.4 | -139.9 | -57.9 |  93.2 | 169.8 |     22.2874 |    15.738   |
| 09:35 -> 09:45 | Simple Continuation                | 7247 |   18.3 |     15   |  -90.2 | -33.9 |  68.5 | 138.9 |     16.5862 |     8.76225 |
| 09:35 -> 09:45 | Simple Continuation, Gap/ATR > 2.0 | 1026 |   26.8 |     29.8 | -179.2 | -63.5 | 122.9 | 224.3 |     30.5068 |    17.2515  |
| 09:35 -> 09:50 | Simple Continuation                | 7272 |   25.2 |     18.1 | -102.7 | -35.5 |  81.7 | 164.9 |     20.2008 |    10.4923  |
| 09:35 -> 09:50 | Simple Continuation, Gap/ATR > 2.0 | 1026 |   38.8 |     35.8 | -192.3 | -67.7 | 149.1 | 273.2 |     34.308  |    19.883   |

Winners vs losers within the same cohorts:

| Window         | Cohort                             |   Winners mean |   Winners median |   Losers mean |   Losers median |
|:---------------|:-----------------------------------|---------------:|-----------------:|--------------:|----------------:|
| 09:35 -> 09:40 | Simple Continuation                |           62.9 |             44   |         -57.3 |           -36.3 |
| 09:35 -> 09:40 | Simple Continuation, Gap/ATR > 2.0 |          100.1 |             79.8 |        -101.5 |           -74.3 |
| 09:35 -> 09:45 | Simple Continuation                |           82.3 |             57.9 |         -69.5 |           -43.7 |
| 09:35 -> 09:45 | Simple Continuation, Gap/ATR > 2.0 |          133.9 |            107   |        -122.9 |           -80.8 |
| 09:35 -> 09:50 | Simple Continuation                |           96.9 |             69.4 |         -77.4 |           -48.1 |
| 09:35 -> 09:50 | Simple Continuation, Gap/ATR > 2.0 |          155.5 |            123   |        -137.3 |           -99.2 |

## 5. Expectancy before and after costs

| Window         | Cohort                             |    n | Win rate   |   Gross (bps) |   gross p |   NET (bps) |   CI lo |   CI hi |   net p |
|:---------------|:-----------------------------------|-----:|:-----------|--------------:|----------:|------------:|--------:|--------:|--------:|
| 09:35 -> 09:40 | Simple Continuation                | 7178 | 57.5%      |          11.8 |         0 |         5.2 |     3   |     7.3 |   0     |
| 09:35 -> 09:40 | Simple Continuation, Gap/ATR > 2.0 | 1023 | 58.2%      |          15.8 |         0 |         9.2 |     0.6 |    17.8 |   0.037 |
| 09:35 -> 09:45 | Simple Continuation                | 7247 | 57.9%      |          18.3 |         0 |        11.7 |     9   |    14.3 |   0     |
| 09:35 -> 09:45 | Simple Continuation, Gap/ATR > 2.0 | 1026 | 58.3%      |          26.8 |         0 |        20.2 |    10   |    30.1 |   0     |
| 09:35 -> 09:50 | Simple Continuation                | 7272 | 58.9%      |          25.2 |         0 |        18.6 |    15.4 |    21.7 |   0     |
| 09:35 -> 09:50 | Simple Continuation, Gap/ATR > 2.0 | 1026 | 60.1%      |          38.8 |         0 |        32.2 |    20.3 |    45.1 |   0     |
| 09:35 -> 10:35 | Simple Continuation                | 7295 | 57.1%      |          29.5 |         0 |        22.9 |    18.4 |    28.4 |   0     |
| 09:35 -> 10:35 | Simple Continuation, Gap/ATR > 2.0 | 1027 | 60.4%      |          52.6 |         0 |        46   |    30.2 |    62.7 |   0     |
| 09:35 -> Close | Simple Continuation                | 7311 | 55.7%      |          31.7 |         0 |        25.1 |    18.2 |    31.7 |   0     |
| 09:35 -> Close | Simple Continuation, Gap/ATR > 2.0 | 1029 | 58.8%      |          64.6 |         0 |        58   |    35.3 |    82.7 |   0     |

---

## 09:35 entry versus the 09:45 entry

Matched on holding length rather than clock time, Simple Continuation cohort:

| Hold | 09:35 entry | | | 09:45 entry | | |
|---|---:|---:|---:|---:|---:|---:|
| | Win rate | Gross | NET | Win rate | Gross | NET |
| 5 min | 57.5% | +11.8 | **+5.2** | 55.7% | +6.8 | **-0.1** |
| 10 min | 57.9% | +18.3 | **+11.7** | 55.6% | +9.0 | **+2.1** |
| 15 min | 58.9% | +25.2 | **+18.6** | 54.6% | +8.0 | **+1.1** |
| ~1 hour | 57.1% | +29.5 | **+22.9** | 54.0% | +11.2 | **+4.3** |
| To close | 55.7% | +31.7 | **+25.1** | 51.6% | +13.4 | **+6.4** |

And for the large-gap subgroup, which was the best cohort found at 09:45:

| Hold | 09:35 entry | | 09:45 entry | |
|---|---:|---:|---:|---:|
| | Win rate | NET | Win rate | NET |
| 5 min | 58.2% | **+9.2** | 55.7% | **+4.7** |
| 10 min | 58.3% | **+20.2** | 55.8% | **+6.2** |
| 15 min | 60.1% | **+32.2** | — | — |

_Comparison written from the tables above; the 09:45 figures are the previously reported ones for the same cohorts._

---

_Reproducible from `lambda_strategy_validation/entry0935.py`; tables in `lambda_data/tables/e35_*.csv`._