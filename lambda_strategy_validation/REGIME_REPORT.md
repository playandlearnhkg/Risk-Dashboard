# Lambda — Has the Post-Earnings T+1 Edge Decayed?

High Volume + Continuation (non-doji), entry at the 09:35 open, 1-hour hold, no stop unless stated. Skew and kurtosis are winsorised at 1/99 throughout, because the raw figures on this cohort are one observation (the CAR squeeze) and carry no information about a period.

Cohort 4,906 events, 2015-01-27 → 2025-12-19; 4,270 pass the corrected universe screen. ⚠ marks n < 150.

## 0. The universe screen had to be repaired first

The screen used in `VALIDATION_REPORT.md` is **broken from 2022 onward**, and a year-by-year study is exactly where that shows up. The 2022-03-01 IEX consolidated-tape change rescales reported volume, so a fixed 500k-share / $50M threshold stops measuring liquidity and starts measuring which side of the break a row sits on:

| Year | Events | Old screen pass rate | Corrected pass rate |
|---|---:|---:|---:|
| 2015 | 379 | 84.2% | 84.2% |
| 2016 | 344 | 89.5% | 89.5% |
| 2017 | 446 | 88.1% | 88.1% |
| 2018 | 482 | 87.1% | 84.4% |
| 2019 | 474 | 87.8% | 87.1% |
| 2020 | 482 | 87.8% | 86.1% |
| 2021 | 516 | 87.4% | 83.5% |
| 2022 | 324 | 26.2% | 79.0% |
| 2023 | 512 | 2.5% | 91.0% |
| 2024 | 452 | 3.3% | 90.5% |
| 2025 | 495 | 5.1% | 91.5% |

The old screen admits 87% of 2021 events and **2.5% of 2023**. Price and market-cap pass rates are unchanged across the break; only the two volume tests collapse. So a "screened" cohort built on it is not a liquidity cohort at all — it is very nearly a *2015–2021* cohort.

> **This corrects the previous report.** `VALIDATION_REPORT.md` compared screened against unscreened events and attributed the screened half's lower tail risk to liquidity. That comparison was confounded with time: the screened half was overwhelmingly pre-2022, and this report shows tail risk rose sharply after 2022. The like-for-like conclusion there does not survive, and the screened columns below use the corrected definition instead.

**The corrected screen** keeps the price and market-cap tests unchanged and replaces the two volume tests with a within-year cross-sectional rank on 63-day dollar volume, calibrated so the pass rate matches what the dollar threshold admitted before the break (72.5%). A relative screen is immune to a level shift in the units. It is not the same filter as the specification names — it cannot be, because that filter is not measurable consistently across this data — and that is a data-repair decision worth knowing about.

## By period — All (no screen)

| Bucket | n | Win rate | **NET (bps)** | NET (ATR) | Avg Win | Avg Loss | Payoff | Median | % loss > 0.5 ATR | % loss > 1 ATR | Avg large loss | p10 | Skew (w) | Kurt (w) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2015–2019 | 2,125 | 59.8% | **+35.4** | +0.1504 | 141 | 108 | 1.31 | +29.6 | 13.65% | 3.62% | -318 | -139 | +0.43 | +1.4 |
| 2020–2022 | 1,322 | 58.0% | **+32.5** | +0.0951 | 173 | 146 | 1.18 | +30.0 | 14.07% | 4.01% | -389 | -200 | +0.19 | +1.4 |
| 2023–2025 | 1,459 | 55.9% | **+21.1** | +0.0688 | 155 | 135 | 1.15 | +23.2 | 17.82% | 6.58% | -348 | -194 | +0.05 | +0.8 |

## By period — Screened

| Bucket | n | Win rate | **NET (bps)** | NET (ATR) | Avg Win | Avg Loss | Payoff | Median | % loss > 0.5 ATR | % loss > 1 ATR | Avg large loss | p10 | Skew (w) | Kurt (w) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2015–2019 | 1,840 | 60.0% | **+34.9** | +0.1493 | 138 | 105 | 1.31 | +29.6 | 13.42% | 3.48% | -318 | -135 | +0.40 | +1.3 |
| 2020–2022 | 1,102 | 58.1% | **+24.6** | +0.0803 | 155 | 141 | 1.10 | +29.8 | 13.79% | 3.81% | -375 | -197 | +0.21 | +1.3 |
| 2023–2025 | 1,328 | 56.2% | **+24.9** | +0.0815 | 158 | 132 | 1.19 | +24.3 | 17.85% | 6.33% | -341 | -194 | +0.17 | +0.6 |

## Is recent weakness a left-tail story?

**All (no screen)** — 2015–2019 → 2023–2025

| Component | Early | Recent | Change |
|---|---:|---:|---:|
| NET (bps) | +35.4 | +21.1 | -14.3 |
| Win rate | 59.8% | 55.9% | -3.8% |
| Average win (bps) | 141 | 155 | +14 |
| Average loss (bps) | 108 | 135 | +28 |
| Payoff ratio | 1.31 | 1.15 | -0.17 |
| % losing > 0.5 ATR | 13.65% | 17.82% | +4.17% |
| % losing > 1.0 ATR | 3.62% | 6.58% | +2.96% |
| Avg large loss (bps) | -318 | -348 | -30 |
| p10 (bps) | -139 | -194 | -55 |
| Std dev (bps) | 176 | 199 | +23 |

Reading the decomposition: hit rate -3.8 pp; average win +14 bps; average loss +28 bps; the >1 ATR loss rate moves +2.96 pp.

**The left tail is doing the damage.** Losses have grown both in average size and in frequency of large ones, which is the pattern the question anticipated.

**Screened** — 2015–2019 → 2023–2025

| Component | Early | Recent | Change |
|---|---:|---:|---:|
| NET (bps) | +34.9 | +24.9 | -10.0 |
| Win rate | 60.0% | 56.2% | -3.7% |
| Average win (bps) | 138 | 158 | +20 |
| Average loss (bps) | 105 | 132 | +27 |
| Payoff ratio | 1.31 | 1.19 | -0.11 |
| % losing > 0.5 ATR | 13.42% | 17.85% | +4.42% |
| % losing > 1.0 ATR | 3.48% | 6.33% | +2.85% |
| Avg large loss (bps) | -318 | -341 | -23 |
| p10 (bps) | -135 | -194 | -59 |
| Std dev (bps) | 171 | 196 | +25 |

Reading the decomposition: hit rate -3.7 pp; average win +20 bps; average loss +27 bps; the >1 ATR loss rate moves +2.85 pp.

**The left tail is doing the damage.** Losses have grown both in average size and in frequency of large ones, which is the pattern the question anticipated.

## By year — All (no screen)

| Bucket | n | Win rate | **NET (bps)** | NET (ATR) | Avg Win | Avg Loss | Payoff | Median | % loss > 0.5 ATR | % loss > 1 ATR | Avg large loss | p10 | Skew (w) | Kurt (w) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2015 | 379 | 64.1% | **+37.6** | +0.1728 | 119 | 92 | 1.30 | +41.9 | 10.03% | 2.64% | -313 | -112 | +0.06 | +0.8 |
| 2016 | 344 | 64.0% | **+49.9** | +0.2015 | 143 | 99 | 1.45 | +48.1 | 10.76% | 2.33% | -241 | -129 | +0.61 | +1.3 |
| 2017 | 446 | 57.0% | **+26.4** | +0.1190 | 124 | 89 | 1.39 | +17.7 | 14.80% | 4.26% | -266 | -119 | +0.76 | +2.0 |
| 2018 | 482 | 58.5% | **+29.2** | +0.1222 | 150 | 129 | 1.17 | +28.7 | 14.73% | 3.73% | -382 | -156 | +0.22 | +1.8 |
| 2019 | 474 | 57.2% | **+37.9** | +0.1537 | 167 | 120 | 1.39 | +26.2 | 16.46% | 4.64% | -341 | -161 | +0.41 | +1.0 |
| 2020 | 482 | 57.1% | **+17.3** | +0.0670 | 151 | 146 | 1.03 | +33.5 | 14.32% | 3.53% | -378 | -219 | +0.19 | +1.4 |
| 2021 | 516 | 57.2% | **+42.8** | +0.1231 | 196 | 147 | 1.33 | +25.9 | 15.50% | 4.26% | -410 | -197 | +0.06 | +1.6 |
| 2022 | 324 | 60.8% | **+38.8** | +0.0921 | 168 | 145 | 1.16 | +33.7 | 11.42% | 4.32% | -369 | -199 | +0.25 | +1.0 |
| 2023 | 512 | 54.7% | **+16.4** | +0.0489 | 148 | 129 | 1.15 | +15.7 | 17.77% | 6.25% | -362 | -183 | +0.24 | +1.1 |
| 2024 | 452 | 58.4% | **+30.9** | +0.1023 | 160 | 136 | 1.17 | +31.3 | 17.92% | 7.74% | -330 | -189 | -0.02 | +0.6 |
| 2025 | 495 | 54.9% | **+17.0** | +0.0587 | 158 | 141 | 1.12 | +21.9 | 17.78% | 5.86% | -356 | -207 | +0.03 | +0.6 |

## By year — Screened

| Bucket | n | Win rate | **NET (bps)** | NET (ATR) | Avg Win | Avg Loss | Payoff | Median | % loss > 0.5 ATR | % loss > 1 ATR | Avg large loss | p10 | Skew (w) | Kurt (w) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2015 | 319 | 64.9% | **+36.1** | +0.1673 | 116 | 94 | 1.22 | +43.3 | 10.03% | 2.51% | -342 | -111 | -0.03 | +1.0 |
| 2016 | 308 | 63.3% | **+51.3** | +0.2056 | 145 | 94 | 1.53 | +44.8 | 10.71% | 1.95% | -238 | -121 | +0.72 | +1.1 |
| 2017 | 393 | 56.7% | **+27.1** | +0.1188 | 127 | 91 | 1.40 | +16.6 | 15.78% | 4.58% | -275 | -127 | +0.97 | +2.8 |
| 2018 | 407 | 60.0% | **+34.1** | +0.1421 | 145 | 120 | 1.21 | +29.3 | 13.51% | 2.70% | -354 | -146 | +0.35 | +1.9 |
| 2019 | 413 | 56.9% | **+30.0** | +0.1296 | 154 | 119 | 1.29 | +25.3 | 15.74% | 5.08% | -349 | -163 | +0.09 | +0.5 |
| 2020 | 415 | 57.1% | **+15.3** | +0.0600 | 148 | 147 | 1.01 | +35.1 | 14.46% | 3.61% | -376 | -219 | +0.15 | +1.3 |
| 2021 | 431 | 58.0% | **+27.0** | +0.1009 | 156 | 136 | 1.14 | +28.8 | 14.39% | 3.94% | -387 | -192 | +0.08 | +1.0 |
| 2022 | 256 | 59.8% | **+35.7** | +0.0784 | 165 | 140 | 1.18 | +26.4 | 11.72% | 3.91% | -353 | -190 | +0.35 | +1.1 |
| 2023 | 466 | 54.9% | **+22.6** | +0.0669 | 152 | 122 | 1.25 | +18.1 | 17.60% | 5.58% | -347 | -178 | +0.45 | +1.0 |
| 2024 | 409 | 58.9% | **+35.6** | +0.1185 | 161 | 131 | 1.23 | +31.4 | 17.60% | 7.58% | -320 | -182 | +0.14 | +0.3 |
| 2025 | 453 | 55.2% | **+17.7** | +0.0632 | 159 | 143 | 1.11 | +21.9 | 18.32% | 5.96% | -358 | -208 | -0.02 | +0.5 |

## Does an ATR −1.0 stop earn more in the recent period?

| Universe | Period | n | % stopped | Baseline NET | Stopped NET | **Cost** | Tail before | Tail after | **Tail cut (pp)** | **pp per bp** |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| All (no screen) | 2015–2019 | 2,125 | 10.0% | +35.4 | +31.3 | **+4.1** | 3.62% | 0.42% | **3.20** | **0.77** |
| All (no screen) | 2020–2022 | 1,322 | 9.5% | +32.5 | +27.3 | **+5.2** | 4.01% | 1.06% | **2.95** | **0.57** |
| All (no screen) | 2023–2025 | 1,459 | 13.6% | +21.1 | +18.3 | **+2.8** | 6.58% | 1.99% | **4.59** | **1.61** |
| Screened | 2015–2019 | 1,840 | 9.7% | +34.9 | +31.1 | **+3.8** | 3.48% | 0.49% | **2.99** | **0.78** |
| Screened | 2020–2022 | 1,102 | 9.0% | +24.6 | +19.6 | **+5.0** | 3.81% | 0.82% | **2.99** | **0.60** |
| Screened | 2023–2025 | 1,328 | 13.2% | +24.9 | +22.0 | **+3.0** | 6.33% | 1.88% | **4.44** | **1.50** |

Cost is baseline NET minus stopped NET, so a positive number means the stop gave up expectancy. Efficiency is percentage points of >1 ATR tail removed per basis point surrendered — the same measure used in `STOPSUMMARY_REPORT.md`.

**All (no screen):** efficiency moves from 0.77 in 2015–2019 to 1.61 in 2023–2025 — the stop **is** worth more recently. Its cost changes from +4.1 to +2.8 bps while the tail it removes changes from 3.20 to 4.59 pp.

**Screened:** efficiency moves from 0.78 in 2015–2019 to 1.50 in 2023–2025 — the stop **is** worth more recently. Its cost changes from +3.8 to +3.0 bps while the tail it removes changes from 2.99 to 4.44 pp.

## Reading notes

- **Three periods is three observations.** Any story told across them is a story about three numbers, and the 2020–2022 block contains both the COVID crash and the 2021 meme episode, which are not a regime so much as two unrepeatable events.
- **Year buckets are small** — a few hundred trades each, so a single-year figure carries a wide interval that is not printed here. Use the periods for inference and the years for texture.
- **Winsorised skew and kurtosis** are shown because the raw values are dominated by one 2021 observation and would otherwise make that period look structurally different when it is not.
- **No multiple-comparison control.** Splitting one sample by time and then reading the worst period as a trend is exactly how decay gets diagnosed where none exists.

---

_Reproducible from `lambda_strategy_validation/regime_sizing.py`; tables in `lambda_data/tables/rs_*.csv`._