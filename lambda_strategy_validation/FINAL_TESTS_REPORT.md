# Lambda Final Tests — Ultra-Short Windows and Move Size

Same strict no-look-ahead rules: pattern known at 09:45, all measurement starts at 09:45 (entry = close of the 09:44 bar, the price at 09:45:00), SPY direction from Open→09:45 only, Stage from the prior session.

Sample: **17,458** events. Cells with n < 150 are flagged.

## Test 1 — Ultra-short holding periods

| Window         | Subgroup             |     n |   n cont |   n rev | Win rate   | Wilson lo   | Wilson hi   |   p (clustered) | n<150?   |
|:---------------|:---------------------|------:|---------:|--------:|:-----------|:------------|:------------|----------------:|:---------|
| 09:45 -> 09:50 | All events           | 17084 |     8820 |    8264 | 51.6%      | 50.9%       | 52.4%       |           0     |          |
| 09:45 -> 09:50 | Gap Up               |  9006 |     4544 |    4462 | 50.5%      | 49.4%       | 51.5%       |           0.43  |          |
| 09:45 -> 09:50 | Gap Down             |  8078 |     4276 |    3802 | 52.9%      | 51.8%       | 54.0%       |           0     |          |
| 09:45 -> 09:50 | Simple: Continuation |  7181 |     3998 |    3183 | 55.7%      | 54.5%       | 56.8%       |           0     |          |
| 09:45 -> 09:50 | Simple: Reversal     |  7673 |     3859 |    3814 | 50.3%      | 49.2%       | 51.4%       |           0.633 |          |
| 09:45 -> 09:55 | All events           | 17230 |     8846 |    8384 | 51.3%      | 50.6%       | 52.1%       |           0.002 |          |
| 09:45 -> 09:55 | Gap Up               |  9071 |     4601 |    4470 | 50.7%      | 49.7%       | 51.8%       |           0.303 |          |
| 09:45 -> 09:55 | Gap Down             |  8159 |     4245 |    3914 | 52.0%      | 50.9%       | 53.1%       |           0.004 |          |
| 09:45 -> 09:55 | Simple: Continuation |  7251 |     4034 |    3217 | 55.6%      | 54.5%       | 56.8%       |           0     |          |
| 09:45 -> 09:55 | Simple: Reversal     |  7731 |     3822 |    3909 | 49.4%      | 48.3%       | 50.6%       |           0.323 |          |
| 09:45 -> 10:00 | All events           | 17241 |     8792 |    8449 | 51.0%      | 50.2%       | 51.7%       |           0.016 |          |
| 09:45 -> 10:00 | Gap Up               |  9080 |     4571 |    4509 | 50.3%      | 49.3%       | 51.4%       |           0.579 |          |
| 09:45 -> 10:00 | Gap Down             |  8161 |     4221 |    3940 | 51.7%      | 50.6%       | 52.8%       |           0.014 |          |
| 09:45 -> 10:00 | Simple: Continuation |  7255 |     3959 |    3296 | 54.6%      | 53.4%       | 55.7%       |           0     |          |
| 09:45 -> 10:00 | Simple: Reversal     |  7742 |     3854 |    3888 | 49.8%      | 48.7%       | 50.9%       |           0.704 |          |

## Test 2 — Average move size of winners vs losers (gross of costs)

`signed_return = sign(gap) x (P_end / P_entry - 1)`. Winners are the continuation cases, losers the reversals. `Avg loss` is reported as a positive number. **Expectancy** = win_rate x avg_win - (1-win_rate) x avg_loss, with a date-clustered CI — this is the number that decides whether a win rate is worth anything.

The cost column is a **reference only** and is not subtracted from any figure in these tables: it is the median round-trip cost using each event's own measured trailing Roll spread on both legs plus 2 bps impact per leg.

### Main windows

| Window         | Subgroup                                 |     n | Win rate   |   Avg win (bps) |   Avg loss (bps) |   Win − loss |   Payoff ratio |   Expectancy (bps) |   CI lo |   CI hi |     p |   Median cost (bps) | n<150?   |
|:---------------|:-----------------------------------------|------:|:-----------|----------------:|-----------------:|-------------:|---------------:|-------------------:|--------:|--------:|------:|--------------------:|:---------|
| 09:45 -> 10:00 | All events                               | 17241 | 51.0%      |            67.4 |             68.2 |         -0.8 |           0.99 |                1   |    -0.8 |     2.5 | 0.248 |                 6.6 |          |
| 09:45 -> 10:00 | Gap Up                                   |  9080 | 50.3%      |            66.9 |             67.7 |         -0.8 |           0.99 |                0.1 |    -2.9 |     2.8 | 0.964 |                 6.6 |          |
| 09:45 -> 10:00 | Gap Down                                 |  8161 | 51.7%      |            67.9 |             68.7 |         -0.8 |           0.99 |                1.9 |    -0.6 |     4.6 | 0.155 |                 6.6 |          |
| 09:45 -> 10:00 | Simple: Continuation                     |  7255 | 54.6%      |            70.3 |             66.7 |          3.7 |           1.05 |                8.1 |     5.7 |    10.6 | 0     |                 6.6 |          |
| 09:45 -> 10:00 | Simple: Reversal                         |  7742 | 49.8%      |            64.9 |             67.5 |         -2.6 |           0.96 |               -1.6 |    -3.8 |     0.6 | 0.148 |                 6.6 |          |
| 09:45 -> 10:00 | Stage 3+4 + SPY Agree                    |  4269 | 52.0%      |            72.5 |             71.6 |          0.9 |           1.01 |                3.3 |    -0.5 |     7.1 | 0.09  |                 6.7 |          |
| 09:45 -> 10:00 | Best combo: Cont + Stage 3+4 + SPY Agree |  1920 | 56.2%      |            75.3 |             69.8 |          5.4 |           1.08 |               11.8 |     6.6 |    16.4 | 0     |                 6.7 |          |
| 09:45 -> 10:30 | All events                               | 17316 | 51.1%      |            98.8 |             98.3 |          0.5 |           1    |                2.5 |    -0   |     5   | 0.055 |                 6.6 |          |
| 09:45 -> 10:30 | Gap Up                                   |  9115 | 50.3%      |            96.7 |             97.7 |         -1   |           0.99 |                0   |    -4.1 |     4.8 | 0.989 |                 6.6 |          |
| 09:45 -> 10:30 | Gap Down                                 |  8201 | 52.1%      |           100.9 |             98.9 |          2   |           1.02 |                5.2 |     0.5 |     9.9 | 0.033 |                 6.6 |          |
| 09:45 -> 10:30 | Simple: Continuation                     |  7272 | 54.0%      |           103.3 |             96.6 |          6.7 |           1.07 |               11.4 |     7.2 |    15.6 | 0     |                 6.6 |          |
| 09:45 -> 10:30 | Simple: Reversal                         |  7781 | 49.4%      |            96.2 |             96.2 |          0.1 |           1    |               -1.1 |    -4.4 |     2.1 | 0.525 |                 6.6 |          |
| 09:45 -> 10:30 | Stage 3+4 + SPY Agree                    |  4299 | 52.3%      |           104.9 |            101.5 |          3.3 |           1.03 |                6.5 |     1.2 |    12.6 | 0.025 |                 6.7 |          |
| 09:45 -> 10:30 | Best combo: Cont + Stage 3+4 + SPY Agree |  1933 | 54.6%      |           109.4 |             99   |         10.5 |           1.11 |               14.9 |     7.4 |    22.1 | 0     |                 6.7 |          |
| 09:45 -> Close | All events                               | 17392 | 49.8%      |           166   |            159.5 |          6.5 |           1.04 |                2.7 |    -1.6 |     6.7 | 0.2   |                 6.6 |          |
| 09:45 -> Close | Gap Up                                   |  9154 | 49.6%      |           162.9 |            157.5 |          5.3 |           1.03 |                1.5 |    -5.1 |     9.1 | 0.715 |                 6.6 |          |
| 09:45 -> Close | Gap Down                                 |  8238 | 50.1%      |           169.5 |            161.8 |          7.7 |           1.05 |                4.1 |    -3.8 |    12.2 | 0.336 |                 6.6 |          |
| 09:45 -> Close | Simple: Continuation                     |  7306 | 51.6%      |           173.5 |            157.5 |         16   |           1.1  |               13.4 |     7.4 |    19.8 | 0     |                 6.6 |          |
| 09:45 -> Close | Simple: Reversal                         |  7814 | 48.8%      |           159.4 |            158.9 |          0.4 |           1    |               -3.5 |    -9.4 |     2.1 | 0.212 |                 6.6 |          |
| 09:45 -> Close | Stage 3+4 + SPY Agree                    |  4311 | 52.1%      |           169.8 |            171.9 |         -2.1 |           0.99 |                6.1 |    -3.9 |    16.2 | 0.246 |                 6.7 |          |
| 09:45 -> Close | Best combo: Cont + Stage 3+4 + SPY Agree |  1932 | 54.5%      |           177.2 |            173.9 |          3.3 |           1.02 |               17.3 |     4   |    31.8 | 0.015 |                 6.7 |          |

### Ultra-short windows

| Window         | Subgroup                                 |     n | Win rate   |   Avg win (bps) |   Avg loss (bps) |   Win − loss |   Payoff ratio |   Expectancy (bps) |   CI lo |   CI hi |     p |   Median cost (bps) | n<150?   |
|:---------------|:-----------------------------------------|------:|:-----------|----------------:|-----------------:|-------------:|---------------:|-------------------:|--------:|--------:|------:|--------------------:|:---------|
| 09:45 -> 09:50 | All events                               | 17084 | 51.6%      |            44.6 |             43.8 |          0.8 |           1.02 |                1.8 |     0.8 |     2.9 | 0.002 |                 6.6 |          |
| 09:45 -> 09:50 | Gap Up                                   |  9006 | 50.5%      |            43.4 |             43.2 |          0.1 |           1    |                0.5 |    -1.1 |     2   | 0.554 |                 6.6 |          |
| 09:45 -> 09:50 | Gap Down                                 |  8078 | 52.9%      |            45.8 |             44.4 |          1.5 |           1.03 |                3.4 |     1.8 |     5.1 | 0     |                 6.6 |          |
| 09:45 -> 09:50 | Simple: Continuation                     |  7181 | 55.7%      |            46.5 |             42.7 |          3.8 |           1.09 |                7   |     5.3 |     8.5 | 0     |                 6.6 |          |
| 09:45 -> 09:50 | Simple: Reversal                         |  7673 | 50.3%      |            42.9 |             43.1 |         -0.2 |           1    |                0.1 |    -1.4 |     1.5 | 0.835 |                 6.6 |          |
| 09:45 -> 09:50 | Stage 3+4 + SPY Agree                    |  4229 | 53.3%      |            46.9 |             46.4 |          0.5 |           1.01 |                3.3 |     1   |     5.5 | 0.007 |                 6.7 |          |
| 09:45 -> 09:50 | Best combo: Cont + Stage 3+4 + SPY Agree |  1898 | 58.1%      |            49.3 |             46.2 |          3.1 |           1.07 |                9.2 |     5.9 |    12.1 | 0     |                 6.7 |          |
| 09:45 -> 09:55 | All events                               | 17230 | 51.3%      |            59   |             58.2 |          0.8 |           1.01 |                2   |     0.5 |     3.3 | 0.001 |                 6.6 |          |
| 09:45 -> 09:55 | Gap Up                                   |  9071 | 50.7%      |            58.1 |             57.7 |          0.4 |           1.01 |                1   |    -1.3 |     3.2 | 0.424 |                 6.6 |          |
| 09:45 -> 09:55 | Gap Down                                 |  8159 | 52.0%      |            60.1 |             58.8 |          1.2 |           1.02 |                3   |     0.8 |     5.3 | 0.008 |                 6.6 |          |
| 09:45 -> 09:55 | Simple: Continuation                     |  7251 | 55.6%      |            62.2 |             57.4 |          4.7 |           1.08 |                9.1 |     6.8 |    11.5 | 0     |                 6.6 |          |
| 09:45 -> 09:55 | Simple: Reversal                         |  7731 | 49.4%      |            56.9 |             56.6 |          0.3 |           1    |               -0.5 |    -2.3 |     1.2 | 0.575 |                 6.6 |          |
| 09:45 -> 09:55 | Stage 3+4 + SPY Agree                    |  4278 | 52.7%      |            61.9 |             61.3 |          0.6 |           1.01 |                3.6 |     0.7 |     7   | 0.029 |                 6.7 |          |
| 09:45 -> 09:55 | Best combo: Cont + Stage 3+4 + SPY Agree |  1925 | 57.1%      |            65.4 |             59.8 |          5.6 |           1.09 |               11.7 |     7.3 |    15.9 | 0     |                 6.7 |          |
| 09:45 -> 10:00 | All events                               | 17241 | 51.0%      |            67.4 |             68.2 |         -0.8 |           0.99 |                1   |    -0.8 |     2.5 | 0.248 |                 6.6 |          |
| 09:45 -> 10:00 | Gap Up                                   |  9080 | 50.3%      |            66.9 |             67.7 |         -0.8 |           0.99 |                0.1 |    -2.9 |     2.8 | 0.964 |                 6.6 |          |
| 09:45 -> 10:00 | Gap Down                                 |  8161 | 51.7%      |            67.9 |             68.7 |         -0.8 |           0.99 |                1.9 |    -0.6 |     4.6 | 0.155 |                 6.6 |          |
| 09:45 -> 10:00 | Simple: Continuation                     |  7255 | 54.6%      |            70.3 |             66.7 |          3.7 |           1.05 |                8.1 |     5.7 |    10.6 | 0     |                 6.6 |          |
| 09:45 -> 10:00 | Simple: Reversal                         |  7742 | 49.8%      |            64.9 |             67.5 |         -2.6 |           0.96 |               -1.6 |    -3.8 |     0.6 | 0.148 |                 6.6 |          |
| 09:45 -> 10:00 | Stage 3+4 + SPY Agree                    |  4269 | 52.0%      |            72.5 |             71.6 |          0.9 |           1.01 |                3.3 |    -0.5 |     7.1 | 0.09  |                 6.7 |          |
| 09:45 -> 10:00 | Best combo: Cont + Stage 3+4 + SPY Agree |  1920 | 56.2%      |            75.3 |             69.8 |          5.4 |           1.08 |               11.8 |     6.6 |    16.4 | 0     |                 6.7 |          |

## Test 3 — Statistical vs economic reality check

### 1. Which combinations are still statistically significant in the ultra-short windows?

9 of 15 cells clear both a 50% win rate and clustered p < 0.05:

| Window         | Subgroup             |     n | Win rate   |     p |
|:---------------|:---------------------|------:|:-----------|------:|
| 09:45 -> 09:50 | All events           | 17084 | 51.6%      | 0     |
| 09:45 -> 09:50 | Gap Down             |  8078 | 52.9%      | 0     |
| 09:45 -> 09:50 | Simple: Continuation |  7181 | 55.7%      | 0     |
| 09:45 -> 09:55 | All events           | 17230 | 51.3%      | 0.002 |
| 09:45 -> 09:55 | Gap Down             |  8159 | 52.0%      | 0.004 |
| 09:45 -> 09:55 | Simple: Continuation |  7251 | 55.6%      | 0     |
| 09:45 -> 10:00 | All events           | 17241 | 51.0%      | 0.016 |
| 09:45 -> 10:00 | Gap Down             |  8161 | 51.7%      | 0.014 |
| 09:45 -> 10:00 | Simple: Continuation |  7255 | 54.6%      | 0     |


### 2. Is the average win large enough to survive realistic T+1 costs?

The median round-trip cost on this sample is **6.6 bps** (inter-quartile range 5.9 to 7.6 bps), charging each event its own measured trailing Roll spread on both legs plus 2 bps impact per leg.

Eyeballing a gross expectancy against a median cost is not good enough to answer this, so the table below charges the cost **per event** and bootstraps the result, giving the net figure its own confidence interval:

| Window         | Cohort                                   |     n |   Gross (bps) |   Cost (bps) |   NET (bps) |   CI lo |   CI hi |     p |
|:---------------|:-----------------------------------------|------:|--------------:|-------------:|------------:|--------:|--------:|------:|
| 09:45 -> 09:50 | All events                               | 17458 |          1.8  |         6.61 |       -5.15 |   -6.21 |   -4.1  | 0     |
| 09:45 -> 09:50 | Simple: Continuation                     |  7336 |          6.82 |         6.6  |       -0.1  |   -1.54 |    1.38 | 0.879 |
| 09:45 -> 09:50 | Stage 3+4 + SPY Agree                    |  4326 |          3.21 |         6.7  |       -3.83 |   -5.94 |   -1.63 | 0.002 |
| 09:45 -> 09:50 | Best combo: Cont + Stage 3+4 + SPY Agree |  1942 |          9.04 |         6.7  |        2    |   -0.95 |    4.91 | 0.205 |
| 09:45 -> 09:55 | All events                               | 17458 |          1.94 |         6.61 |       -5.01 |   -6.41 |   -3.54 | 0     |
| 09:45 -> 09:55 | Simple: Continuation                     |  7336 |          9    |         6.6  |        2.08 |    0.02 |    4.21 | 0.051 |
| 09:45 -> 09:55 | Stage 3+4 + SPY Agree                    |  4326 |          3.6  |         6.7  |       -3.44 |   -6.39 |   -0.11 | 0.034 |
| 09:45 -> 09:55 | Best combo: Cont + Stage 3+4 + SPY Agree |  1942 |         11.64 |         6.7  |        4.6  |    0.25 |    8.87 | 0.041 |
| 09:45 -> 10:00 | All events                               | 17458 |          0.95 |         6.61 |       -6    |   -7.65 |   -4.41 | 0     |
| 09:45 -> 10:00 | Simple: Continuation                     |  7336 |          8    |         6.6  |        1.08 |   -1.21 |    3.39 | 0.375 |
| 09:45 -> 10:00 | Stage 3+4 + SPY Agree                    |  4326 |          3.24 |         6.7  |       -3.8  |   -7.52 |   -0.1  | 0.044 |
| 09:45 -> 10:00 | Best combo: Cont + Stage 3+4 + SPY Agree |  1942 |         11.65 |         6.7  |        4.61 |   -0.58 |    9.73 | 0.079 |
| 09:45 -> 10:30 | All events                               | 17458 |          2.47 |         6.61 |       -4.48 |   -7    |   -1.97 | 0.001 |
| 09:45 -> 10:30 | Simple: Continuation                     |  7336 |         11.25 |         6.6  |        4.33 |    0.54 |    8.88 | 0.041 |
| 09:45 -> 10:30 | Stage 3+4 + SPY Agree                    |  4326 |          6.46 |         6.7  |       -0.58 |   -6.05 |    5.17 | 0.839 |
| 09:45 -> 10:30 | Best combo: Cont + Stage 3+4 + SPY Agree |  1942 |         14.81 |         6.7  |        7.77 |    0.08 |   15.3  | 0.048 |
| 09:45 -> Close | All events                               | 17458 |          2.71 |         6.61 |       -4.25 |   -8.23 |   -0.06 | 0.045 |
| 09:45 -> Close | Simple: Continuation                     |  7336 |         13.36 |         6.6  |        6.44 |    0.36 |   12.56 | 0.038 |
| 09:45 -> Close | Stage 3+4 + SPY Agree                    |  4326 |          6.09 |         6.7  |       -0.96 |  -10.77 |    9.24 | 0.841 |
| 09:45 -> Close | Best combo: Cont + Stage 3+4 + SPY Agree |  1942 |         17.19 |         6.7  |       10.14 |   -3.39 |   23.72 | 0.161 |

**The answer depends entirely on which cohort you are in.**

- **All events: no.** Net is negative at every window (-4 to -6 bps, p < 0.05). The unconditional trade loses to costs.
- **Simple: Continuation pattern (n = 7,336): marginally yes**, but only once you hold past ten minutes — net +2.1 bps at 09:55 (p = 0.051), +4.3 bps at 10:30 (p = 0.041), +6.4 bps at the close (p = 0.038). Note the CI lower bounds: 0.02, 0.54, 0.36. They clear zero, barely.
- **Best combo (n = 1,942): yes on paper**, +4.6 bps at 09:55 (p = 0.041) rising to +7.8 bps at 10:30 (p = 0.048), though by the close the interval is so wide it stops being significant.
- **Stage 3+4 + SPY Agree without the pattern: no.** Net is negative or indistinguishable from zero everywhere. The pattern is doing all the work; the Stage and SPY terms add nothing on their own.

### 3. Updated view: do the ultra-short windows change the picture?

**Yes, but not in the direction the question hoped for — they make it worse, and in doing so they clarify the whole investigation.**

Test 1 shows the win rate is *highest* at the shortest horizon: 51.6% overall at five minutes against 51.0% at fifteen, and 55.7% for the Continuation pattern against 54.6%. If win rate were the objective, five minutes would be the answer.

But the economics run the other way. At five minutes the average win is ~45 bps and the average loss ~44 bps; by the close they are ~173 and ~158. The edge per trade scales with the size of the move, while the ~6.6 bps round trip is fixed. So the shortest window has the best hit rate and the worst net result — the best combo nets +2.0 bps at 09:50 (p = 0.21, not significant) versus +7.8 bps at 10:30.

The deeper reason is the **payoff ratio**, which sits at roughly 1.0 everywhere: 1.02 overall at five minutes, 0.99 at fifteen. Winners and losers are the same size. A 51-52% win rate with a symmetric payoff generates one to three basis points of expectancy — arithmetic, not opinion. Only the pattern-conditioned cohorts push the payoff ratio to 1.05-1.11, and that, not the win rate, is where their edge comes from.

**So I am revising the earlier verdict, in one direction only.** "Statistically real but economically dead" was too strong. The correct statement is:

- Unconditionally: **economically dead**, confirmed again here.
- Conditioned on the simple first-candle Continuation pattern, held 30+ minutes: **marginally alive** — a few basis points net, with p-values around 0.04 and confidence intervals whose lower bounds sit just above zero.

Three things keep that from being a green light. The p-values are borderline and many cells were examined. The universe is survivorship-biased, which pushes every result in this study upward. And a few basis points per trade is inside the range that a single unmodelled friction — borrow cost on the short side, a wider spread on an illiquid name, a missed fill — would erase. It is a real effect that is too thin to deploy on this evidence, which is a different and more useful conclusion than "there is nothing there".

---

_Reproducible from `lambda_strategy_validation/final_tests.py`; tables written to `lambda_data/tables/test1_ultrashort.csv`, `test2_earn.csv`, `test2_earn_ultrashort.csv`._