# Lambda — Reversal Analysis and Continuation Payoff Ratio

Both parts use entry at the **open of the 09:35 bar**, the same rules and the same look-ahead guards as the previous 09:35 report.

## Rules and sign convention

| Input | Definition |
|---|---|
| Continuation signal | 09:30–09:35 candle closes **in** the gap direction |
| Reversal signal | 09:30–09:35 candle closes **against** the gap direction |
| Entry | Open of the 09:35 bar |
| ATR / Gap-ATR | Prior-session ATR(14); overnight gap in price terms ÷ that ATR |
| Costs | 6.6 bps round trip, subtracted for NET |

Sample: **16,855** events with a usable 09:35 price — **7,336** Continuation, **7,843** Reversal (the balance are Doji first candles, excluded from both). Cells with n < 150 are flagged. p-values are two-sided from a date-clustered bootstrap.

> **Sign convention — the one judgement call here.** For Reversal events the first candle closed *against* the gap, so the tradeable rule is *follow the candle*, i.e. trade against the gap. All Reversal figures below are signed in the **candle's** direction:
>
> `reversal_return = −sign(gap) × (P_end / P_entry − 1)`
>
> Under that convention both cohorts express one single rule — follow the first 5-minute candle — and are directly comparable. If you prefer to read the Reversal rows as *fade the candle / stay with the gap*, flip the sign of every Reversal number: win rate becomes 1 − p, and average win and average loss swap.

## Part 1A — Reversal by holding period

| Window         | Cohort            |    n | Win rate   | Wilson lo   | Wilson hi   |   Avg win |   Avg loss |   Payoff |   Gross (bps) |     p |   NET (bps) |   net p | n<150?   |
|:---------------|:------------------|-----:|:-----------|:------------|:------------|----------:|-----------:|---------:|--------------:|------:|------------:|--------:|:---------|
| 09:35 -> 09:40 | All Reversal      | 7601 | 52.1%      | 50.9%       | 53.2%       |      57.4 |       58.1 |     0.99 |           2   | 0.033 |        -4.6 |   0     |          |
| 09:35 -> 09:40 | Gap Up Reversal   | 3988 | 53.4%      | 51.8%       | 54.9%       |      56   |       56.4 |     0.99 |           3.6 | 0.011 |        -3   |   0.03  |          |
| 09:35 -> 09:40 | Gap Down Reversal | 3613 | 50.6%      | 49.0%       | 52.3%       |      58.9 |       59.8 |     0.99 |           0.3 | 0.838 |        -6.3 |   0     |          |
| 09:35 -> 09:45 | All Reversal      | 7747 | 51.6%      | 50.5%       | 52.7%       |      74.4 |       73.2 |     1.02 |           3   | 0.021 |        -3.6 |   0.007 |          |
| 09:35 -> 09:45 | Gap Up Reversal   | 4078 | 53.0%      | 51.4%       | 54.5%       |      72   |       71.2 |     1.01 |           4.7 | 0.007 |        -1.9 |   0.278 |          |
| 09:35 -> 09:45 | Gap Down Reversal | 3669 | 50.1%      | 48.5%       | 51.8%       |      77.1 |       75.2 |     1.03 |           1.2 | 0.58  |        -5.4 |   0.01  |          |
| 09:35 -> 09:50 | All Reversal      | 7790 | 52.3%      | 51.2%       | 53.5%       |      85.3 |       87.7 |     0.97 |           2.9 | 0.046 |        -3.7 |   0.012 |          |
| 09:35 -> 09:50 | Gap Up Reversal   | 4098 | 54.2%      | 52.7%       | 55.7%       |      82.6 |       86.2 |     0.96 |           5.3 | 0.01  |        -1.3 |   0.531 |          |
| 09:35 -> 09:50 | Gap Down Reversal | 3692 | 50.3%      | 48.7%       | 51.9%       |      88.5 |       89.3 |     0.99 |           0.1 | 0.959 |        -6.5 |   0.004 |          |
| 09:35 -> 10:35 | All Reversal      | 7793 | 51.6%      | 50.5%       | 52.8%       |     126   |      125.8 |     1    |           4.2 | 0.049 |        -2.4 |   0.268 |          |
| 09:35 -> 10:35 | Gap Up Reversal   | 4092 | 53.5%      | 52.0%       | 55.1%       |     124.2 |      122.4 |     1.01 |           9.6 | 0.001 |         3   |   0.319 |          |
| 09:35 -> 10:35 | Gap Down Reversal | 3701 | 49.6%      | 47.9%       | 51.2%       |     128.1 |      129.3 |     0.99 |          -1.7 | 0.613 |        -8.3 |   0.024 |          |
| 09:35 -> Close | All Reversal      | 7807 | 52.1%      | 51.0%       | 53.2%       |     175.4 |      177.5 |     0.99 |           6.5 | 0.047 |        -0.1 |   0.968 |          |
| 09:35 -> Close | Gap Up Reversal   | 4108 | 53.4%      | 51.9%       | 54.9%       |     173.3 |      174.7 |     0.99 |          11.2 | 0.017 |         4.6 |   0.362 |          |
| 09:35 -> Close | Gap Down Reversal | 3699 | 50.7%      | 49.1%       | 52.3%       |     177.9 |      180.4 |     0.99 |           1.3 | 0.794 |        -5.3 |   0.313 |          |

## Part 1B — Reversal by Gap/ATR

| Window         | Gap/ATR         |    n | Win rate   | Wilson lo   | Wilson hi   |   Avg win |   Avg loss |   Payoff |   Gross (bps) |     p |   NET (bps) |   net p | n<150?   |
|:---------------|:----------------|-----:|:-----------|:------------|:------------|----------:|-----------:|---------:|--------------:|------:|------------:|--------:|:---------|
| 09:35 -> 09:40 | Gap/ATR < 1.0   | 5860 | 53.7%      | 52.4%       | 55.0%       |      51   |       46.2 |     1.1  |           6   | 0     |        -0.6 |   0.539 |          |
| 09:35 -> 09:40 | Gap/ATR 1.0-2.0 |  760 | 45.7%      | 42.1%       | 49.2%       |      73.3 |       83.9 |     0.87 |         -12.1 | 0     |       -18.7 |   0     |          |
| 09:35 -> 09:40 | Gap/ATR > 2.0   |  981 | 47.2%      | 44.1%       | 50.3%       |      88.7 |       99.7 |     0.89 |         -10.8 | 0.007 |       -17.4 |   0     |          |
| 09:35 -> 09:45 | Gap/ATR < 1.0   | 6003 | 53.4%      | 52.2%       | 54.7%       |      68.1 |       59.3 |     1.15 |           8.8 | 0     |         2.2 |   0.102 |          |
| 09:35 -> 09:45 | Gap/ATR 1.0-2.0 |  760 | 46.2%      | 42.7%       | 49.7%       |      89.1 |      111.2 |     0.8  |         -18.7 | 0     |       -25.3 |   0     |          |
| 09:35 -> 09:45 | Gap/ATR > 2.0   |  984 | 44.8%      | 41.7%       | 47.9%       |     108.1 |      115.8 |     0.93 |         -15.5 | 0.002 |       -22.1 |   0     |          |
| 09:35 -> 09:50 | Gap/ATR < 1.0   | 6039 | 54.6%      | 53.3%       | 55.8%       |      79.1 |       71.8 |     1.1  |          10.6 | 0     |         4   |   0.01  |          |
| 09:35 -> 09:50 | Gap/ATR 1.0-2.0 |  766 | 45.0%      | 41.5%       | 48.6%       |      98.3 |      123.4 |     0.8  |         -23.5 | 0     |       -30.1 |   0     |          |
| 09:35 -> 09:50 | Gap/ATR > 2.0   |  985 | 44.3%      | 41.2%       | 47.4%       |     122.2 |      139.8 |     0.87 |         -23.8 | 0     |       -30.4 |   0     |          |
| 09:35 -> 10:35 | Gap/ATR < 1.0   | 6041 | 53.2%      | 52.0%       | 54.5%       |     117.1 |      108.4 |     1.08 |          11.6 | 0     |         5   |   0.022 |          |
| 09:35 -> 10:35 | Gap/ATR 1.0-2.0 |  768 | 45.6%      | 42.1%       | 49.1%       |     157.6 |      162.1 |     0.97 |         -16.4 | 0.03  |       -23   |   0.005 |          |
| 09:35 -> 10:35 | Gap/ATR > 2.0   |  984 | 46.7%      | 43.6%       | 49.9%       |     164.1 |      190.3 |     0.86 |         -24.6 | 0.002 |       -31.2 |   0     |          |
| 09:35 -> Close | Gap/ATR < 1.0   | 6054 | 52.7%      | 51.4%       | 53.9%       |     163.5 |      153.6 |     1.06 |          13.5 | 0     |         6.9 |   0.027 |          |
| 09:35 -> Close | Gap/ATR 1.0-2.0 |  770 | 50.0%      | 46.5%       | 53.5%       |     219.1 |      257.6 |     0.85 |         -19.2 | 0.126 |       -25.8 |   0.03  |          |
| 09:35 -> Close | Gap/ATR > 2.0   |  983 | 50.5%      | 47.3%       | 53.6%       |     218.1 |      254.7 |     0.86 |         -16.1 | 0.112 |       -22.7 |   0.029 |          |

## Part 2 — Continuation: average win vs average loss by Gap/ATR

Average win = mean of positive outcomes. Average loss = mean of negative outcomes, shown as a positive magnitude. Payoff ratio = avg win ÷ avg loss. Expectancy is the gross mean; NET subtracts costs.

| Window         | Gap/ATR         |    n | Win rate   |   Avg win |   Avg loss |   Payoff |   Gross (bps) |     p |   NET (bps) |   CI lo |   CI hi |   net p | n<150?   |
|:---------------|:----------------|-----:|:-----------|----------:|-----------:|---------:|--------------:|------:|------------:|--------:|--------:|--------:|:---------|
| 09:35 -> 09:40 | Gap/ATR < 1.0   | 5275 | 58.3%      |      53   |       44.9 |     1.18 |          12.1 | 0     |         5.5 |     3.6 |     7.5 |   0     |          |
| 09:35 -> 09:40 | Gap/ATR 1.0-2.0 |  880 | 52.0%      |      81.5 |       77.1 |     1.06 |           5.4 | 0.165 |        -1.2 |    -9.1 |     6.2 |   0.757 |          |
| 09:35 -> 09:40 | Gap/ATR > 2.0   | 1023 | 58.2%      |     100.1 |      101.5 |     0.99 |          15.8 | 0     |         9.2 |     0.6 |    17.8 |   0.037 |          |
| 09:35 -> 09:45 | Gap/ATR < 1.0   | 5340 | 58.8%      |      70.2 |       54.5 |     1.29 |          18.9 | 0     |        12.3 |     9.9 |    14.7 |   0     |          |
| 09:35 -> 09:45 | Gap/ATR 1.0-2.0 |  881 | 51.5%      |      98.3 |       93.6 |     1.05 |           5.3 | 0.25  |        -1.3 |   -10.6 |     7.6 |   0.748 |          |
| 09:35 -> 09:45 | Gap/ATR > 2.0   | 1026 | 58.3%      |     133.9 |      122.9 |     1.09 |          26.8 | 0     |        20.2 |    10   |    30.1 |   0     |          |
| 09:35 -> 09:50 | Gap/ATR < 1.0   | 5363 | 59.4%      |      82.5 |       61.1 |     1.35 |          24.2 | 0     |        17.6 |    14.6 |    20.5 |   0     |          |
| 09:35 -> 09:50 | Gap/ATR 1.0-2.0 |  883 | 53.9%      |     117.2 |      104.9 |     1.12 |          14.9 | 0.003 |         8.3 |    -1.2 |    18.5 |   0.121 |          |
| 09:35 -> 09:50 | Gap/ATR > 2.0   | 1026 | 60.1%      |     155.5 |      137.3 |     1.13 |          38.8 | 0     |        32.2 |    20.3 |    45.1 |   0     |          |

## Final comparison — Continuation vs Reversal in each Gap/ATR zone

**09:35 -> 09:40**

| Gap/ATR | Side | n | Win rate | Avg win | Avg loss | Payoff | Gross | NET | net p |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Gap/ATR < 1.0 | Continuation | 5,275 | 58.3% | +53.0 | +44.9 | 1.18 | +12.1 | **+5.5** | 0.000 |
| Gap/ATR < 1.0 | Reversal | 5,860 | 53.7% | +51.0 | +46.2 | 1.10 | +6.0 | **-0.6** | 0.539 |
| Gap/ATR 1.0-2.0 | Continuation | 880 | 52.0% | +81.5 | +77.1 | 1.06 | +5.4 | **-1.2** | 0.757 |
| Gap/ATR 1.0-2.0 | Reversal | 760 | 45.7% | +73.3 | +83.9 | 0.87 | -12.1 | **-18.7** | 0.000 |
| Gap/ATR > 2.0 | Continuation | 1,023 | 58.2% | +100.1 | +101.5 | 0.99 | +15.8 | **+9.2** | 0.037 |
| Gap/ATR > 2.0 | Reversal | 981 | 47.2% | +88.7 | +99.7 | 0.89 | -10.8 | **-17.4** | 0.000 |

**09:35 -> 09:45**

| Gap/ATR | Side | n | Win rate | Avg win | Avg loss | Payoff | Gross | NET | net p |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Gap/ATR < 1.0 | Continuation | 5,340 | 58.8% | +70.2 | +54.5 | 1.29 | +18.9 | **+12.3** | 0.000 |
| Gap/ATR < 1.0 | Reversal | 6,003 | 53.4% | +68.1 | +59.3 | 1.15 | +8.8 | **+2.2** | 0.102 |
| Gap/ATR 1.0-2.0 | Continuation | 881 | 51.5% | +98.3 | +93.6 | 1.05 | +5.3 | **-1.3** | 0.748 |
| Gap/ATR 1.0-2.0 | Reversal | 760 | 46.2% | +89.1 | +111.2 | 0.80 | -18.7 | **-25.3** | 0.000 |
| Gap/ATR > 2.0 | Continuation | 1,026 | 58.3% | +133.9 | +122.9 | 1.09 | +26.8 | **+20.2** | 0.000 |
| Gap/ATR > 2.0 | Reversal | 984 | 44.8% | +108.1 | +115.8 | 0.93 | -15.5 | **-22.1** | 0.000 |

**09:35 -> 09:50**

| Gap/ATR | Side | n | Win rate | Avg win | Avg loss | Payoff | Gross | NET | net p |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Gap/ATR < 1.0 | Continuation | 5,363 | 59.4% | +82.5 | +61.1 | 1.35 | +24.2 | **+17.6** | 0.000 |
| Gap/ATR < 1.0 | Reversal | 6,039 | 54.6% | +79.1 | +71.8 | 1.10 | +10.6 | **+4.0** | 0.010 |
| Gap/ATR 1.0-2.0 | Continuation | 883 | 53.9% | +117.2 | +104.9 | 1.12 | +14.9 | **+8.3** | 0.121 |
| Gap/ATR 1.0-2.0 | Reversal | 766 | 45.0% | +98.3 | +123.4 | 0.80 | -23.5 | **-30.1** | 0.000 |
| Gap/ATR > 2.0 | Continuation | 1,026 | 60.1% | +155.5 | +137.3 | 1.13 | +38.8 | **+32.2** | 0.000 |
| Gap/ATR > 2.0 | Reversal | 985 | 44.3% | +122.2 | +139.8 | 0.87 | -23.8 | **-30.4** | 0.000 |

## Supplementary — what the candle filter is actually worth

Same trade, gap direction, **no candle filter at all** (every event in the bucket, Continuation, Reversal and Doji together). Compare against the Continuation rows above to see how much the first-candle condition adds.

| Window         | Gap/ATR         |     n | Win rate   |   Avg win |   Avg loss |   Payoff |   Gross (bps) |     p |   NET (bps) |   net p |
|:---------------|:----------------|------:|:-----------|----------:|-----------:|---------:|--------------:|------:|------------:|--------:|
| 09:35 -> 09:40 | Gap/ATR < 1.0   | 12181 | 52.0%      |      49.8 |       48.2 |     1.03 |           2.8 | 0     |        -3.8 |   0     |
| 09:35 -> 09:40 | Gap/ATR 1.0-2.0 |  1817 | 53.1%      |      81.8 |       75   |     1.09 |           8.3 | 0.001 |         1.7 |   0.492 |
| 09:35 -> 09:40 | Gap/ATR > 2.0   |  2208 | 55.8%      |      99.6 |       95.2 |     1.05 |          13.5 | 0     |         6.9 |   0.015 |
| 09:35 -> 09:45 | Gap/ATR < 1.0   | 12412 | 52.7%      |      64.5 |       62.6 |     1.03 |           4.3 | 0     |        -2.3 |   0.012 |
| 09:35 -> 09:45 | Gap/ATR 1.0-2.0 |  1818 | 52.9%      |     103.8 |       91.9 |     1.13 |          11.6 | 0.001 |         5   |   0.12  |
| 09:35 -> 09:45 | Gap/ATR > 2.0   |  2215 | 56.7%      |     125.8 |      116.6 |     1.08 |          20.7 | 0     |        14.1 |   0     |
| 09:35 -> 09:50 | Gap/ATR < 1.0   | 12473 | 52.1%      |      76.8 |       71.8 |     1.07 |           5.7 | 0     |        -0.9 |   0.368 |
| 09:35 -> 09:50 | Gap/ATR 1.0-2.0 |  1825 | 54.5%      |     118.4 |      101.3 |     1.17 |          18.3 | 0     |        11.7 |   0.001 |
| 09:35 -> 09:50 | Gap/ATR > 2.0   |  2213 | 58.4%      |     147.5 |      130.7 |     1.13 |          31.7 | 0     |        25.1 |   0     |

## What the numbers say

**1. In aggregate the Reversal signal is not tradeable.** Following the counter-gap candle across all 7,747 events at ten minutes wins 51.6% of the time with a payoff ratio of 1.02 — essentially a coin flip with symmetric stakes. Gross expectancy is +3.0 bps (p = 0.021); after the 6.6 bps round trip that becomes -3.6 bps. It is negative net at every window out to an hour.

**2. But the aggregate hides a sign flip across Gap/ATR.** The Reversal cohort is not one population:

- **Gap/ATR < 1.0** (n = 6,003): win rate 53.4%, payoff 1.15, net **+2.2 bps** (p = 0.102)
- **Gap/ATR 1.0-2.0** (n = 760): win rate 46.2%, payoff 0.80, net **-25.3 bps** (p = 0.000)
- **Gap/ATR > 2.0** (n = 984): win rate 44.8%, payoff 0.93, net **-22.1 bps** (p = 0.000)

On small gaps, following the counter-gap candle is mildly constructive (+2.2 bps, p = 0.102). On gaps above one ATR it is a reliable way to lose money — -22.1 bps at p = 0.000 in the largest bucket, with the win rate falling below 50% and the payoff ratio below 1.0 at the same time. Both halves of the expectancy move against you together, which is what a genuine adverse signal looks like rather than a noise artefact.

**The practical reading is the inverse trade.** Because these figures are signed in the candle's direction, flipping them says: on a gap larger than one ATR, an adverse first 5-minute candle is something to *fade*, not to follow. Staying with the gap despite it earned +15.5 bps gross / +8.9 bps net at ten minutes. The gap reasserts itself.

**3. Payoff ratio does not improve with gap size — win rate and trade size do.** This is the opposite of the intuition that big gaps give you better reward-to-risk:

| Gap/ATR | Win rate | Avg win | Avg loss | Payoff | NET |
|---|---:|---:|---:|---:|---:|
| Gap/ATR < 1.0 | 58.8% | +70.2 | +54.5 | **1.29** | +12.3 |
| Gap/ATR 1.0-2.0 | 51.5% | +98.3 | +93.6 | **1.05** | -1.3 |
| Gap/ATR > 2.0 | 58.3% | +133.9 | +122.9 | **1.09** | +20.2 |

The best payoff ratio in the Continuation book belongs to the **smallest** gaps (1.29), not the largest (1.09). What large gaps deliver is a comparable win rate on a much bigger trade — average win 134 bps versus 70 — so the fixed 6.6 bps cost consumes a far smaller share of it. That is the whole reason the large-gap bucket nets more (+20.2 vs +12.3 bps), and it is a cost-scaling story, not an edge-quality story.

Payoff ratio also rises with holding time in every bucket (small gaps: 1.29 at ten minutes → 1.35 at fifteen), because average wins grow faster than average losses. Nothing here cuts losers short — that is simply the shape of the unmanaged distribution.

**4. In the middle bucket the candle signal inverts.** Gap/ATR 1.0–2.0 is the worst *Continuation* bucket (-1.3 bps net, p = 0.748), yet it is the bucket where the counter-gap candle predicts gap continuation most strongly: read in gap terms the Reversal cohort there returns +18.7 bps gross, better than the +5.3 bps from the with-gap candle. So this is not a dead zone — it is a zone where the first candle points the wrong way.

That inversion does **not** carry to the largest bucket, and it would be wrong to generalise it. At Gap/ATR > 2.0 the with-gap candle still beats the counter-gap one in gap terms (+26.8 vs +15.5 bps gross), so there the candle is confirmatory. What the two buckets above one ATR share is narrower and more robust than an inversion: **the gap direction pays regardless of what the first candle does**, and in neither bucket does an adverse candle justify trading against the gap. Whether the candle adds anything on top of the gap varies by bucket, and its sign is not stable.

Note also that the Gap/ATR effect is **U-shaped at this entry**, not monotone: Continuation nets more in the smallest bucket than in the middle one. The monotone result reported earlier was measured at the 09:45 entry and is not overturned by this — but Gap/ATR should not be treated as a smooth dial at 09:35.

**5. How much is the candle filter actually worth?** Comparing Continuation against the same trade with no candle condition at all, at ten minutes:

| Gap/ATR | No filter (NET) | Continuation (NET) | Filter adds |
|---|---:|---:|---:|
| Gap/ATR < 1.0 | -2.3 | +12.3 | **+14.5** |
| Gap/ATR 1.0-2.0 | +5.0 | -1.3 | **-6.3** |
| Gap/ATR > 2.0 | +14.1 | +20.2 | **+6.0** |

On small gaps the candle filter is doing nearly all the work — without it the trade is -2.3 bps net, with it +12.3. On large gaps the gap itself already pays +14.1 bps net with no filter, and the candle adds +6.0. So the two ideas are not the same trade: on small gaps you are trading the candle, on large gaps you are trading the gap and using the candle as a modest enhancer. In the middle bucket the filter is actively harmful (-6.3), which is the same inversion described in point 4.

### Caveats that still apply

- The universe is survivorship-biased (current index membership), which flatters every cohort here equally.
- Costs are a single 6.6 bps median. Large-gap events are the widest-spread events, so their true cost is above the median and their net figures are the most optimistic in the table.
- The 1.0–2.0 and > 2.0 buckets hold roughly 1,000 events each across eleven years; they are not small, but they are concentrated in high-volatility dates, which the date-clustered bootstrap accounts for in the p-values and the CI widths.
- T+0 versus T+1 event dating remains ambiguous for part of the sample, as noted in earlier reports.

---

_Reproducible from `lambda_strategy_validation/reversal_payoff.py`; tables in `lambda_data/tables/rp_*.csv`._