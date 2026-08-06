# Lambda — Volume Confirmation Test

Does opening-candle volume confirm the first-candle continuation signal? Run on two universes with identical machinery.

| Input | Definition |
|---|---|
| High Volume | `c1_volume` > 1.5× the trailing 20-session **mean** of `c1_volume` for the same ticker and the same 09:30–09:35 slot |
| Benchmark timing | Trailing window shifted one session — the current day never enters its own benchmark |
| Entry | Open of the 09:35 bar |
| Signal | 09:30–09:35 candle closes in the gap direction |
| Costs | 6.6 bps round trip, subtracted for NET |

| Universe | Period | Events | Continuation | % High Volume |
|---|---|---:|---:|---:|
| Post-Earnings (T+1) | 2015-01-27 → 2025-12-22 | 16,548 | 7,295 | 67.7% |
| General Gaps | 2021-01-04 → 2025-12-31 | 121,764 | 55,751 | 36.7% |

> **On the threshold.** `c1_volume` is strongly right-skewed, so the trailing *mean* sits well above the typical session: the median ratio is 2.29 (earnings) and 1.11 (general). A 1.5× cut on a mean denominator is therefore closer to a top-63th-percentile selection than to "half again above typical". That is the definition as specified; a median-denominator variant is carried below as a robustness check.

> **Tape break.** The 2022-03-01 IEX consolidated-tape change rescales reported volume roughly 35×. A within-ticker ratio is nearly immune (14.9% of sessions clear 1.5× before the break, 16.0% after), but a trailing window that *straddles* the break mixes units. A guard for those sessions removed **0** events from either universe — not because the guard failed, but because the liquidity filter used to build both event sets already excludes the 120 days following the break. The exclusion is real; it just happened upstream.

## Universe A — Post-Earnings (T+1)

| Window | Group | n | Win rate | Gross | **NET** | net p |
|---|---|---:|---:|---:|---:|---:|
| 5 min (09:40) | All Continuation | 7,138 | 57.5% | +11.9 | **+5.3** | 0.000 |
| 5 min (09:40) | Cont + High Volume | 4,870 | 58.3% | +14.4 | **+7.8** | 0.000 |
| 5 min (09:40) | Cont + Normal/Low Vol | 2,268 | 55.7% | +6.5 | **-0.1** | 0.910 |
| 15 min (09:50) | All Continuation | 7,232 | 58.8% | +25.1 | **+18.5** | 0.000 |
| 15 min (09:50) | Cont + High Volume | 4,904 | 59.9% | +30.3 | **+23.7** | 0.000 |
| 15 min (09:50) | Cont + Normal/Low Vol | 2,328 | 56.5% | +14.3 | **+7.7** | 0.000 |
| 1 hour (10:35) | All Continuation | 7,254 | 57.1% | +29.6 | **+23.0** | 0.000 |
| 1 hour (10:35) | Cont + High Volume | 4,908 | 58.4% | +36.7 | **+30.1** | 0.000 |
| 1 hour (10:35) | Cont + Normal/Low Vol | 2,346 | 54.6% | +14.6 | **+8.0** | 0.002 |

## Universe B — General Gaps

| Window | Group | n | Win rate | Gross | **NET** | net p |
|---|---|---:|---:|---:|---:|---:|
| 5 min (09:40) | All Continuation | 54,881 | 52.3% | +3.5 | **-3.1** | 0.002 |
| 5 min (09:40) | Cont + High Volume | 20,255 | 52.4% | +4.4 | **-2.2** | 0.053 |
| 5 min (09:40) | Cont + Normal/Low Vol | 34,626 | 52.2% | +3.1 | **-3.5** | 0.000 |
| 15 min (09:50) | All Continuation | 55,413 | 53.4% | +9.5 | **+2.9** | 0.051 |
| 15 min (09:50) | Cont + High Volume | 20,362 | 53.3% | +10.7 | **+4.1** | 0.020 |
| 15 min (09:50) | Cont + Normal/Low Vol | 35,051 | 53.5% | +8.9 | **+2.3** | 0.121 |
| 1 hour (10:35) | All Continuation | 55,530 | 53.3% | +12.6 | **+6.0** | 0.016 |
| 1 hour (10:35) | Cont + High Volume | 20,400 | 52.8% | +13.3 | **+6.7** | 0.059 |
| 1 hour (10:35) | Cont + Normal/Low Vol | 35,130 | 53.5% | +12.2 | **+5.6** | 0.013 |

## Key questions

**Does High Volume improve the edge in the post-earnings universe?**

- **5 min (09:40)**: High +7.8 bps / 58.3% win (n=4,870, p=0.000) vs Normal/Low -0.1 / 55.7% (n=2,268) → **+7.9 bps**
- **15 min (09:50)**: High +23.7 bps / 59.9% win (n=4,904, p=0.000) vs Normal/Low +7.7 / 56.5% (n=2,328) → **+15.9 bps**
- **1 hour (10:35)**: High +30.1 bps / 58.4% win (n=4,908, p=0.000) vs Normal/Low +8.0 / 54.6% (n=2,346) → **+22.1 bps**

**Yes, materially.** High Volume beats Normal/Low at 3 of 3 horizons, by +7.9 to +22.1 bps, and the win rate improves at every one (+2.6 to +3.8 pp). Direction and size both move the right way, which is what a real conditioning variable looks like. Note also that the Normal/Low cohort at 5 minutes is flat (-0.1 bps, p=0.91) — essentially the entire short-horizon earnings edge lives in the high-volume subset.

**Does High Volume improve the edge in the general gap universe?**

- **5 min (09:40)**: High -2.2 bps / 52.4% win (n=20,255, p=0.053) vs Normal/Low -3.5 / 52.2% (n=34,626) → **+1.3 bps**
- **15 min (09:50)**: High +4.1 bps / 53.3% win (n=20,362, p=0.020) vs Normal/Low +2.3 / 53.5% (n=35,051) → **+1.9 bps**
- **1 hour (10:35)**: High +6.7 bps / 52.8% win (n=20,400, p=0.059) vs Normal/Low +5.6 / 53.5% (n=35,130) → **+1.2 bps**

**Barely, and not in a way worth acting on.** The sign is positive at 3 of 3 horizons, but the size is +1.2 to +1.9 bps — inside the noise of the cost assumption itself. More telling, the win rate is *lower* for high volume at 2 of 3 horizons (15 min (09:50) -0.2 pp, 1 hour (10:35) -0.8 pp). The small net gain comes from larger average trade size, not from picking direction better — high-volume names simply move more, and a fixed cost eats proportionally less of the move. That is the same cost-scaling artefact seen with market cap, not a signal.

**Is the improvement larger in one universe than the other?**

| Window | Post-Earnings Δ | General Gaps Δ | Larger in |
|---|---:|---:|---|
| 5 min (09:40) | +7.9 | +1.3 | Post-Earnings |
| 15 min (09:50) | +15.9 | +1.9 | Post-Earnings |
| 1 hour (10:35) | +22.1 | +1.2 | Post-Earnings |

**Much larger post-earnings — by roughly 11×.** Mean effect across the three horizons is **+15.3 bps** post-earnings versus **+1.4 bps** on general gaps, and the gap widens with holding period. This is the clearest separation between the two universes found so far: volume confirmation is a real conditioning variable on earnings days and close to inert without the catalyst.

**Does High Volume help more in Gap/ATR < 1.0 or > 2.0?**

This one cannot be answered at Gap/ATR > 2.0, and the reason is worth stating plainly: **large gaps are almost always high-volume already**, so there is no low-volume comparison group to measure against.

| Universe | Gap/ATR | n | High Vol | Normal/Low | % High |
|---|---|---:|---:|---:|---:|
| Post-Earnings (T+1) | Gap/ATR < 1.0 | 5,385 | 3,072 | 2,313 | 57.0% |
| Post-Earnings (T+1) | Gap/ATR 1.0-2.0 | 884 | 852 | 32 | 96.4% |
| Post-Earnings (T+1) | Gap/ATR > 2.0 | 1,026 | 1,014 | 12 | 98.8% |
| General Gaps | Gap/ATR < 1.0 | 50,869 | 16,382 | 34,487 | 32.2% |
| General Gaps | Gap/ATR 1.0-2.0 | 3,928 | 3,165 | 763 | 80.6% |
| General Gaps | Gap/ATR > 2.0 | 954 | 924 | 30 | 96.9% |

The Normal/Low cell at Gap/ATR > 2.0 holds a handful of events in each universe — far too few to support any comparison, and the rows that do survive the n ≥ 30 floor swing wildly. **Volume confirmation and large gap size are close to the same filter at the top of the range.**

The comparison *is* well populated in Gap/ATR < 1.0, and that is the informative test — it asks whether volume adds anything once gap size is held small:

| Universe | Window | High Vol NET | Normal/Low NET | Δ |
|---|---|---:|---:|---:|
| Post-Earnings (T+1) | 5 min (09:40) | +9.4 | +0.6 | **+8.8** |
| Post-Earnings (T+1) | 15 min (09:50) | +24.9 | +8.1 | **+16.8** |
| Post-Earnings (T+1) | 1 hour (10:35) | +29.9 | +7.9 | **+21.9** |
| General Gaps | 5 min (09:40) | -1.0 | -3.4 | **+2.3** |
| General Gaps | 15 min (09:50) | +6.1 | +2.5 | **+3.6** |
| General Gaps | 1 hour (10:35) | +8.8 | +5.9 | **+2.9** |

Within small gaps only, volume is worth **+15.8 bps** on average post-earnings versus **+2.9 bps** on general gaps. That matters for interpretation: in the earnings universe volume is **not** merely a proxy for gap size — it still separates outcomes strongly among gaps below one ATR, where the earlier Gap/ATR filter does nothing.

## Robustness — median denominator

Same test with the trailing **median** of `c1_volume` as the benchmark instead of the mean, which is less sensitive to a single prior volume spike.

**Post-Earnings (T+1)** — 81.3% classified high volume under this denominator

| Window | Group | n | Win rate | Gross | **NET** | net p |
|---|---|---:|---:|---:|---:|---:|
| 5 min (09:40) | High Vol (median denom) | 5,842 | 58.2% | +13.6 | **+7.0** | 0.000 |
| 5 min (09:40) | Normal/Low (median denom) | 1,296 | 54.2% | +4.1 | **-2.5** | 0.110 |
| 15 min (09:50) | High Vol (median denom) | 5,885 | 60.2% | +29.1 | **+22.5** | 0.000 |
| 15 min (09:50) | Normal/Low (median denom) | 1,347 | 52.9% | +7.9 | **+1.3** | 0.593 |
| 1 hour (10:35) | High Vol (median denom) | 5,897 | 58.0% | +34.3 | **+27.7** | 0.000 |
| 1 hour (10:35) | Normal/Low (median denom) | 1,357 | 53.2% | +9.2 | **+2.6** | 0.493 |

**General Gaps** — 52.9% classified high volume under this denominator

| Window | Group | n | Win rate | Gross | **NET** | net p |
|---|---|---:|---:|---:|---:|---:|
| 5 min (09:40) | High Vol (median denom) | 29,125 | 52.1% | +4.0 | **-2.6** | 0.015 |
| 5 min (09:40) | Normal/Low (median denom) | 25,756 | 52.4% | +3.0 | **-3.6** | 0.000 |
| 15 min (09:50) | High Vol (median denom) | 29,297 | 53.4% | +10.6 | **+4.0** | 0.014 |
| 15 min (09:50) | Normal/Low (median denom) | 26,116 | 53.4% | +8.3 | **+1.7** | 0.240 |
| 1 hour (10:35) | High Vol (median denom) | 29,361 | 53.0% | +13.3 | **+6.7** | 0.032 |
| 1 hour (10:35) | Normal/Low (median denom) | 26,169 | 53.6% | +11.7 | **+5.1** | 0.024 |

---

_Reproducible from `lambda_strategy_validation/volume_test.py`; tables in `lambda_data/tables/vol_*.csv`._