# Lambda — Stage 1: General Gaps (non-earnings), 2021–2025

**123,809 gap events** across **556 tickers**, 2021-01-04 to 2025-12-31. **55,995** fire the Continuation signal. Net subtracts 6.6 bps round trip. p-values two-sided from a date-clustered bootstrap.

| Input | Definition |
|---|---|
| Universe | Market cap > $3B, price ≥ $10, ADV ≥ 500k — all prior-session |
| Gap filter | \|Gap\| ≥ 0.8% **or** Gap/ATR ≥ 0.7 |
| Signal | 09:30–09:35 candle closes in the gap direction |
| Entry | Open of the 09:35 bar |
| Exits | 5 min = 09:40, 15 min = 09:50, 1 hour = 10:35 |

> **Two things worth flagging up front.** The window straddles the 2022-03-01 IEX consolidated-tape change, which rescales reported share volume; a raw 500k ADV cutoff would drop most of the post-2022 sample for a units reason rather than an economic one, so the cutoff is applied through the break-aware filter established earlier. And 4,285 events with no real print by 09:35 are dropped outright — their forward-filled entry price would otherwise come from *after* the intended entry.

## 1. Overall performance

| Window         | Cohort           |     n | Win rate   | Wilson lo   | Wilson hi   |   Gross (bps) |   NET (bps) |   net p |
|:---------------|:-----------------|------:|:-----------|:------------|:------------|--------------:|------------:|--------:|
| 5 min (09:40)  | All Continuation | 55111 | 52.3%      | 51.8%       | 52.7%       |           3.5 |        -3.1 |   0.002 |
| 5 min (09:40)  | Gap Up           | 29217 | 51.8%      | 51.2%       | 52.4%       |           3.2 |        -3.4 |   0     |
| 5 min (09:40)  | Gap Down         | 25894 | 52.7%      | 52.1%       | 53.3%       |           3.9 |        -2.7 |   0.059 |
| 15 min (09:50) | All Continuation | 55655 | 53.4%      | 53.0%       | 53.8%       |           9.5 |         2.9 |   0.049 |
| 15 min (09:50) | Gap Up           | 29505 | 52.5%      | 51.9%       | 53.0%       |           8.2 |         1.6 |   0.343 |
| 15 min (09:50) | Gap Down         | 26150 | 54.5%      | 53.9%       | 55.1%       |          11.1 |         4.5 |   0.063 |
| 1 hour (10:35) | All Continuation | 55774 | 53.3%      | 52.9%       | 53.7%       |          12.6 |         6   |   0.016 |
| 1 hour (10:35) | Gap Up           | 29564 | 53.8%      | 53.2%       | 54.3%       |          13.4 |         6.8 |   0.013 |
| 1 hour (10:35) | Gap Down         | 26210 | 52.7%      | 52.1%       | 53.3%       |          11.7 |         5.1 |   0.282 |

## 2. Gap / ATR buckets (Continuation)

| Window         | Gap/ATR         |     n | Win rate   |   Avg win |   Avg loss |   Payoff |   Gross (bps) |   NET (bps) |   net p |
|:---------------|:----------------|------:|:-----------|----------:|-----------:|---------:|--------------:|------------:|--------:|
| 5 min (09:40)  | Gap/ATR < 1.0   | 50240 | 52.5%      |      43.3 |       39.4 |     1.1  |           4   |        -2.6 |   0.001 |
| 5 min (09:40)  | Gap/ATR 1.0-2.0 |  3918 | 49.7%      |      59.5 |       61   |     0.97 |          -1.1 |        -7.7 |   0.001 |
| 5 min (09:40)  | Gap/ATR > 2.0   |   953 | 50.6%      |      94.3 |       98.8 |     0.95 |          -1.2 |        -7.8 |   0.096 |
| 15 min (09:50) | Gap/ATR < 1.0   | 50771 | 53.7%      |      68   |       56.8 |     1.2  |          10.3 |         3.7 |   0.007 |
| 15 min (09:50) | Gap/ATR 1.0-2.0 |  3928 | 49.9%      |      87.7 |       82.5 |     1.06 |           2.4 |        -4.2 |   0.356 |
| 15 min (09:50) | Gap/ATR > 2.0   |   956 | 51.4%      |     134.6 |      140.7 |     0.96 |           0.7 |        -5.9 |   0.351 |
| 1 hour (10:35) | Gap/ATR < 1.0   | 50872 | 53.7%      |     103.3 |       90.9 |     1.14 |          13.4 |         6.8 |   0.005 |
| 1 hour (10:35) | Gap/ATR 1.0-2.0 |  3944 | 48.5%      |     137.8 |      120.1 |     1.15 |           5.1 |        -1.5 |   0.869 |
| 1 hour (10:35) | Gap/ATR > 2.0   |   958 | 49.7%      |     189.2 |      185.8 |     1.02 |           0.5 |        -6.1 |   0.514 |

## 3. Market cap (Continuation)

| Window         | Market cap   |     n | Win rate   |   Avg win |   Avg loss |   Payoff |   Gross (bps) |   NET (bps) |   net p |
|:---------------|:-------------|------:|:-----------|----------:|-----------:|---------:|--------------:|------------:|--------:|
| 5 min (09:40)  | $3B - $10B   |  8390 | 52.2%      |      58.9 |       54   |     1.09 |           5   |        -1.6 |   0.206 |
| 5 min (09:40)  | $10B - $50B  | 28588 | 52.3%      |      44.8 |       42.1 |     1.06 |           3.3 |        -3.3 |   0     |
| 5 min (09:40)  | > $50B       | 18133 | 52.2%      |      39.7 |       36.6 |     1.08 |           3.2 |        -3.4 |   0     |
| 15 min (09:50) | $3B - $10B   |  8534 | 53.8%      |      91.5 |       78.2 |     1.17 |          13.2 |         6.6 |   0.003 |
| 15 min (09:50) | $10B - $50B  | 28890 | 53.1%      |      70.7 |       59.9 |     1.18 |           9.4 |         2.8 |   0.063 |
| 15 min (09:50) | > $50B       | 18231 | 53.7%      |      60.2 |       52.4 |     1.15 |           8   |         1.4 |   0.29  |
| 1 hour (10:35) | $3B - $10B   |  8540 | 53.3%      |     142.6 |      124   |     1.15 |          18   |        11.4 |   0.002 |
| 1 hour (10:35) | $10B - $50B  | 28979 | 53.2%      |     105.8 |       94.3 |     1.12 |          12.1 |         5.5 |   0.039 |
| 1 hour (10:35) | > $50B       | 18255 | 53.5%      |      92   |       82.2 |     1.12 |          11   |         4.4 |   0.079 |

## 4. Reference — the same trade with no candle filter

| Window         | Cohort                     |      n | Win rate   |   Gross (bps) |   NET (bps) |   net p |
|:---------------|:---------------------------|-------:|:-----------|--------------:|------------:|--------:|
| 5 min (09:40)  | All gaps, no candle filter | 119651 | 52.5%      |           3.2 |        -3.4 |   0     |
| 15 min (09:50) | All gaps, no candle filter | 121487 | 54.3%      |           9.5 |         2.9 |   0.016 |
| 1 hour (10:35) | All gaps, no candle filter | 121768 | 53.8%      |          11.3 |         4.7 |   0.025 |

## 5. Year by year (Continuation)

| Window         |   Year |     n | Win rate   |   Gross (bps) |   NET (bps) |   net p |
|:---------------|-------:|------:|:-----------|--------------:|------------:|--------:|
| 5 min (09:40)  |   2021 | 10870 | 53.6%      |           5.3 |        -1.3 |   0.516 |
| 5 min (09:40)  |   2022 | 11357 | 52.0%      |           2.4 |        -4.2 |   0.027 |
| 5 min (09:40)  |   2023 | 11366 | 50.7%      |           1.9 |        -4.7 |   0.001 |
| 5 min (09:40)  |   2024 | 10036 | 51.2%      |           1.6 |        -5   |   0.005 |
| 5 min (09:40)  |   2025 | 11482 | 53.6%      |           6.4 |        -0.2 |   0.9   |
| 15 min (09:50) |   2021 | 10956 | 54.5%      |          12.5 |         5.9 |   0.07  |
| 15 min (09:50) |   2022 | 11484 | 52.4%      |           7.5 |         0.9 |   0.819 |
| 15 min (09:50) |   2023 | 11473 | 53.7%      |           9.2 |         2.6 |   0.265 |
| 15 min (09:50) |   2024 | 10147 | 52.9%      |           8.1 |         1.5 |   0.525 |
| 15 min (09:50) |   2025 | 11595 | 53.6%      |          10.4 |         3.8 |   0.258 |
| 1 hour (10:35) |   2021 | 10986 | 55.8%      |          16.2 |         9.6 |   0.029 |
| 1 hour (10:35) |   2022 | 11494 | 54.6%      |          15.2 |         8.6 |   0.148 |
| 1 hour (10:35) |   2023 | 11501 | 53.9%      |          13.9 |         7.3 |   0.036 |
| 1 hour (10:35) |   2024 | 10180 | 52.1%      |           8.6 |         2   |   0.62  |
| 1 hour (10:35) |   2025 | 11613 | 50.0%      |           8.8 |         2.2 |   0.798 |

## 6. General gaps vs the earnings gaps studied earlier

Same entry, same signal, same cost. Earnings figures are the previously reported 09:35-entry numbers.

| Hold | General n | General win | General NET | Earnings n | Earnings win | Earnings NET |
|---|---:|---:|---:|---:|---:|---:|
| 5 min (09:40) | 55,111 | 52.3% | **-3.1** | 7,178 | 57.5% | **+5.2** |
| 15 min (09:50) | 55,655 | 53.4% | **+2.9** | 7,272 | 58.9% | **+18.6** |
| 1 hour (10:35) | 55,774 | 53.3% | **+6.0** | 7,295 | 57.1% | **+22.9** |

## Quick conclusion

**Verdict: REJECT the candle signal on general gaps.** The first-candle condition — the thing being tested — adds at most 1.3 bps over simply trading every gap in its own direction, and nothing at all at the 15-minute horizon. What little positive expectancy exists belongs to gap drift, not to the signal.

**Does the edge still exist on general (non-earnings) gaps?**

Not in any form worth trading. Net is positive and statistically significant at 15 min (09:50) +2.9 bps (p = 0.049), 1 hour (10:35) +6.0 bps (p = 0.016) — but with 55,774 events the bootstrap resolves effects far smaller than the ones that matter, so significance here measures precision, not economic size.

Three things make the small positive numbers unpersuasive:

- **The candle filter is doing no work.** Against the no-filter baseline it adds +0.3 bps at 5 min (09:40), +0.0 bps at 15 min (09:50), +1.3 bps at 1 hour (10:35). Its win rate is also *lower* than the unfiltered trade at 15 minutes (53.4% vs 54.3%) — it raises payoff ratio slightly and win rate slightly less, netting out to nothing.
- **The 1-hour result decays across the sample**, from +9.6 bps in 2021 to +2.2 in 2025, with the win rate falling 55.8% → 50.0%. No single year at 15 minutes is significant on its own.
- **The universe is survivorship-biased** (current index membership) and costs are a single 6.6 bps median. Both push in the optimistic direction, and the whole result lives inside a few bps.

**Which Gap/ATR bucket performs best?**

- **5 min (09:40)**: Gap/ATR < 1.0 -2.6 (p=0.00) · Gap/ATR 1.0-2.0 -7.7 (p=0.00) · Gap/ATR > 2.0 -7.8 (p=0.10) → best **Gap/ATR < 1.0**
- **15 min (09:50)**: Gap/ATR < 1.0 +3.7 (p=0.01) · Gap/ATR 1.0-2.0 -4.2 (p=0.36) · Gap/ATR > 2.0 -5.9 (p=0.35) → best **Gap/ATR < 1.0**
- **1 hour (10:35)**: Gap/ATR < 1.0 +6.8 (p=0.01) · Gap/ATR 1.0-2.0 -1.5 (p=0.87) · Gap/ATR > 2.0 -6.1 (p=0.51) → best **Gap/ATR < 1.0**

**Gap/ATR < 1.0** is the best bucket at 3 of 3 holding periods — and it is the only bucket that is ever positive.

> **This inverts the earnings result, and that matters more than the ranking itself.** On earnings gaps, Gap/ATR > 2.0 was the strongest cohort in the whole investigation. On general gaps it is negative at every horizon:
>
> | Hold | Gap/ATR | General NET | Earnings NET |
> |---|---|---:|---:|
> | 5 min (09:40) | Gap/ATR < 1.0 | -2.6 | +5.5 |
> | 5 min (09:40) | Gap/ATR > 2.0 | -7.8 | +9.2 |
> | 15 min (09:50) | Gap/ATR < 1.0 | +3.7 | +17.6 |
> | 15 min (09:50) | Gap/ATR > 2.0 | -5.9 | +32.2 |
> | 1 hour (10:35) | Gap/ATR < 1.0 | +6.8 | +20.3 |
> | 1 hour (10:35) | Gap/ATR > 2.0 | -6.1 | +46.0 |
>
> This is not a composition effect — it is the *same bucket* giving opposite answers. Large gaps without an earnings catalyst behave differently from large gaps with one, so the Gap/ATR filter cannot be treated as a general property of gaps. It was an earnings-conditional result, and this test is the first evidence about how far it travels: not far.

**Does market cap meaningfully affect the result?**

- **5 min (09:40)**: $3B - $10B -1.6 · $10B - $50B -3.3 · > $50B -3.4 → spread 1.7 bps
- **15 min (09:50)**: $3B - $10B +6.6 · $10B - $50B +2.8 · > $50B +1.4 → spread 5.2 bps
- **1 hour (10:35)**: $3B - $10B +11.4 · $10B - $50B +5.5 · > $50B +4.4 → spread 7.0 bps

**Yes — this is the one filter here that behaves consistently.** Net expectancy falls monotonically with market cap at all three horizons: smallest names beat the largest by 5.2 bps at 15 minutes and 7.0 bps at an hour, and the $3B–$10B bucket is the only one significant at both (p = 0.003 and 0.002).

The mechanism is the same cost-scaling seen throughout this investigation rather than a better signal: small caps move more (average win 143 bps vs 92 at an hour) while the assumed cost stays fixed. Win rates are flat across the three buckets. That caveat is load-bearing: small caps carry the widest spreads, so a flat 6.6 bps is least realistic exactly where the result looks best. A cost that scales with size would compress most of this spread, and I would not trade the market-cap tilt on this evidence without re-running it on per-name spreads.

---

_Reproducible from `lambda_strategy_validation/gapstudy.py` (universe and download in `build_gap_intraday.py`); tables in `lambda_data/tables/gs_*.csv`._