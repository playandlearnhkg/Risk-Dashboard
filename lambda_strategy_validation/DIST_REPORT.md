# Lambda — Return Distribution of the Strongest Post-Earnings Setups

Post-earnings T+1, High Volume Continuation. Four groups × four holding periods. Same events as `VOLUME_TEST_REPORT.md` and `GAPDIR_REPORT.md` — described here rather than only averaged.

| Input | Definition |
|---|---|
| Universe | Post-earnings T+1, 2015-01-27 → 2025-12-22 |
| Continuation | 09:30–09:35 candle closes **with** the gap |
| High Volume | `c1_volume` > 1.5× trailing 20-session mean, same ticker, same 09:30–09:35 slot, shifted one session |
| Entry | Open of the 09:35 bar |
| Costs | 6.6 bps round trip, in NET only |
| Simple return | `sign × (P_end/P_entry − 1)`, in bps |
| Log return | `sign × ln(P_end/P_entry)` — shape only |
| ATR move | signed price move ÷ prior-session ATR(14) |
| Skew / Kurtosis | sample (Fisher); kurtosis is **excess** — normal = 0.0 |
| Inference | date-clustered bootstrap; ⚠ marks n < 150 |

High Volume Continuation events: **4,938**. ATR(14) available for 100.0% of them.

## 1. Core metrics — simple returns (bps)

| Group | Window | n | Win rate | Avg Win | Avg Loss | Payoff | **NET** | net p |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| All | 5 min (09:40) | 4,870 | 58.3% | 72.0 | 66.2 | 1.09 | **+7.8** | 0.000 |
| All | 10 min (09:45) | 4,900 | 58.8% | 93.2 | 81.0 | 1.15 | **+14.8** | 0.000 |
| All | 15 min (09:50) | 4,904 | 59.9% | 110.3 | 89.5 | 1.23 | **+23.7** | 0.000 |
| All | 1 hour (10:35) | 4,908 | 58.4% | 153.6 | 127.0 | 1.21 | **+30.1** | 0.000 |
| | |  |  |  |  |  |  |  |
| Gap Up | 5 min (09:40) | 2,544 | 58.5% | 68.4 | 64.5 | 1.06 | **+6.6** | 0.002 |
| Gap Up | 10 min (09:45) | 2,557 | 58.0% | 91.9 | 80.7 | 1.14 | **+12.9** | 0.000 |
| Gap Up | 15 min (09:50) | 2,561 | 58.8% | 108.0 | 90.2 | 1.20 | **+19.8** | 0.000 |
| Gap Up | 1 hour (10:35) | 2,567 | 57.1% | 152.5 | 128.3 | 1.19 | **+25.6** | 0.001 |
| | |  |  |  |  |  |  |  |
| Gap Down | 5 min (09:40) | 2,326 | 58.2% | 76.1 | 68.0 | 1.12 | **+9.2** | 0.000 |
| Gap Down | 10 min (09:45) | 2,343 | 59.6% | 94.5 | 81.4 | 1.16 | **+16.8** | 0.000 |
| Gap Down | 15 min (09:50) | 2,343 | 61.1% | 112.8 | 88.6 | 1.27 | **+27.8** | 0.000 |
| Gap Down | 1 hour (10:35) | 2,341 | 59.7% | 154.7 | 125.5 | 1.23 | **+35.1** | 0.000 |
| | |  |  |  |  |  |  |  |
| $3B–$10B | 5 min (09:40) | 685 | 61.5% | 94.2 | 84.7 | 1.11 | **+18.6** | 0.000 |
| $3B–$10B | 10 min (09:45) | 685 | 59.9% | 128.5 | 100.5 | 1.28 | **+30.0** | 0.000 |
| $3B–$10B | 15 min (09:50) | 692 | 61.3% | 155.6 | 119.5 | 1.30 | **+42.5** | 0.000 |
| $3B–$10B | 1 hour (10:35) | 690 | 61.9% | 215.0 | 165.1 | 1.30 | **+63.5** | 0.000 |

## 2. Distribution — simple returns (bps)

| Group | Window | Mean | **Median** | p10 | p25 | p75 | p90 | Std | Skew | Kurtosis |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| All | 5 min (09:40) | +14.4 | **+13.8** | -91 | -32 | +63 | +123 | 98 | -0.25 | +4.5 |
| All | 10 min (09:45) | +21.4 | **+18.6** | -108 | -39 | +81 | +157 | 123 | -0.06 | +3.7 |
| All | 15 min (09:50) | +30.3 | **+25.0** | -116 | -40 | +96 | +190 | 142 | +0.23 | +4.9 |
| All | 1 hour (10:35) | +36.7 | **+29.1** | -173 | -67 | +130 | +254 | 240 | +14.69 | +607.5 |
| | |  |  |  |  |  |  |  |  |  |
| Gap Up | 5 min (09:40) | +13.2 | **+12.5** | -90 | -31 | +60 | +121 | 94 | -0.26 | +3.7 |
| Gap Up | 10 min (09:45) | +19.5 | **+16.7** | -111 | -38 | +76 | +158 | 123 | -0.20 | +3.5 |
| Gap Up | 15 min (09:50) | +26.4 | **+21.3** | -121 | -42 | +91 | +188 | 143 | +0.27 | +5.7 |
| Gap Up | 1 hour (10:35) | +32.2 | **+24.2** | -177 | -70 | +123 | +247 | 275 | +18.65 | +674.8 |
| | |  |  |  |  |  |  |  |  |  |
| Gap Down | 5 min (09:40) | +15.8 | **+15.4** | -92 | -33 | +65 | +126 | 103 | -0.24 | +5.0 |
| Gap Down | 10 min (09:45) | +23.4 | **+20.7** | -105 | -40 | +85 | +155 | 124 | +0.09 | +3.9 |
| Gap Down | 15 min (09:50) | +34.4 | **+29.2** | -109 | -38 | +103 | +192 | 141 | +0.19 | +4.0 |
| Gap Down | 1 hour (10:35) | +41.7 | **+34.2** | -168 | -60 | +138 | +267 | 195 | +0.17 | +3.3 |
| | |  |  |  |  |  |  |  |  |  |
| $3B–$10B | 5 min (09:40) | +25.2 | **+21.5** | -113 | -37 | +89 | +169 | 120 | -0.16 | +1.8 |
| $3B–$10B | 10 min (09:45) | +36.6 | **+28.6** | -145 | -45 | +121 | +234 | 156 | -0.03 | +1.4 |
| $3B–$10B | 15 min (09:50) | +49.1 | **+37.0** | -152 | -51 | +142 | +288 | 187 | +0.03 | +1.6 |
| $3B–$10B | 1 hour (10:35) | +70.1 | **+48.7** | -201 | -83 | +208 | +378 | 256 | +0.19 | +1.3 |

## 3. Distribution — log returns

| Group | Window | Skew (log) | Kurtosis (log) | Skew (simple) | Kurtosis (simple) | Δ Skew |
|---|---|---:|---:|---:|---:|---:|
| All | 5 min (09:40) | -0.22 | +4.5 | -0.25 | +4.5 | +0.02 |
| All | 10 min (09:45) | -0.05 | +3.8 | -0.06 | +3.7 | +0.00 |
| All | 15 min (09:50) | +0.21 | +4.7 | +0.23 | +4.9 | -0.02 |
| All | 1 hour (10:35) | +6.63 | +208.2 | +14.69 | +607.5 | -8.06 |
| | |  |  |  |  |  |
| Gap Up | 5 min (09:40) | -0.34 | +3.9 | -0.26 | +3.7 | -0.08 |
| Gap Up | 10 min (09:45) | -0.30 | +3.6 | -0.20 | +3.5 | -0.10 |
| Gap Up | 15 min (09:50) | +0.11 | +5.3 | +0.27 | +5.7 | -0.16 |
| Gap Up | 1 hour (10:35) | +9.89 | +291.1 | +18.65 | +674.8 | -8.76 |
| | |  |  |  |  |  |
| Gap Down | 5 min (09:40) | -0.14 | +4.8 | -0.24 | +5.0 | +0.11 |
| Gap Down | 10 min (09:45) | +0.20 | +4.0 | +0.09 | +3.9 | +0.11 |
| Gap Down | 15 min (09:50) | +0.32 | +4.1 | +0.19 | +4.0 | +0.13 |
| Gap Down | 1 hour (10:35) | +0.33 | +3.4 | +0.17 | +3.3 | +0.16 |
| | |  |  |  |  |  |
| $3B–$10B | 5 min (09:40) | -0.16 | +1.7 | -0.16 | +1.8 | +0.00 |
| $3B–$10B | 10 min (09:45) | -0.02 | +1.4 | -0.03 | +1.4 | +0.00 |
| $3B–$10B | 15 min (09:50) | -0.00 | +1.7 | +0.03 | +1.6 | -0.03 |
| $3B–$10B | 1 hour (10:35) | +0.16 | +1.3 | +0.19 | +1.3 | -0.03 |

### 3b. The same shape, winsorised at 1% / 99%

The raw skew and kurtosis above are **dominated by single observations** — see section 6. Capping the extreme 1% at each end leaves the body of the distribution intact and shows what the typical trade population looks like. Both readings are legitimate; they answer different questions.

| Group | Window | Skew (w) | Kurtosis (w) | Skew (log, w) | Kurtosis (log, w) | Mean (w) | Mean (raw) |
|---|---|---:|---:|---:|---:|---:|---:|
| All | 5 min (09:40) | -0.01 | +1.2 | -0.01 | +1.3 | +14.8 | +14.4 |
| All | 10 min (09:45) | +0.07 | +1.4 | +0.08 | +1.4 | +21.7 | +21.4 |
| All | 15 min (09:50) | +0.19 | +1.3 | +0.18 | +1.4 | +30.4 | +30.3 |
| All | 1 hour (10:35) | +0.16 | +1.2 | +0.18 | +1.2 | +34.7 | +36.7 |
| | |  |  |  |  |  |  |
| Gap Up | 5 min (09:40) | -0.06 | +1.1 | -0.10 | +1.1 | +13.5 | +13.2 |
| Gap Up | 10 min (09:45) | -0.01 | +1.3 | -0.07 | +1.4 | +19.9 | +19.5 |
| Gap Up | 15 min (09:50) | +0.10 | +1.4 | +0.03 | +1.4 | +26.2 | +26.4 |
| Gap Up | 1 hour (10:35) | +0.12 | +1.3 | +0.03 | +1.3 | +28.4 | +32.2 |
| | |  |  |  |  |  |  |
| Gap Down | 5 min (09:40) | +0.03 | +1.3 | +0.08 | +1.3 | +16.3 | +15.8 |
| Gap Down | 10 min (09:45) | +0.20 | +1.5 | +0.26 | +1.5 | +23.9 | +23.4 |
| Gap Down | 15 min (09:50) | +0.22 | +1.3 | +0.29 | +1.3 | +34.7 | +34.4 |
| Gap Down | 1 hour (10:35) | +0.31 | +1.1 | +0.39 | +1.2 | +42.4 | +41.7 |
| | |  |  |  |  |  |  |
| $3B–$10B | 5 min (09:40) | +0.04 | +0.6 | +0.05 | +0.6 | +25.9 | +25.2 |
| $3B–$10B | 10 min (09:45) | +0.09 | +0.6 | +0.08 | +0.7 | +37.1 | +36.6 |
| $3B–$10B | 15 min (09:50) | +0.18 | +0.7 | +0.15 | +0.7 | +49.8 | +49.1 |
| $3B–$10B | 1 hour (10:35) | +0.15 | +0.7 | +0.15 | +0.8 | +69.6 | +70.1 |

## 4. Tail risk — ATR-normalised

Share of trades whose signed move exceeds **-1.0 ATR against** the position, and **+1.5 ATR in favour**. ATR is the prior session's ATR(14), so it is known before entry.

| Group | Window | n (ATR) | **% loss > 1.0 ATR** | **% gain > 1.5 ATR** | Median ATR move | p10 ATR | p90 ATR |
|---|---|---:|---:|---:|---:|---:|---:|
| All | 5 min (09:40) | 4,870 | **0.80%** | **0.14%** | +0.059 | -0.34 | +0.47 |
| All | 10 min (09:45) | 4,900 | **1.37%** | **0.80%** | +0.079 | -0.41 | +0.61 |
| All | 15 min (09:50) | 4,904 | **1.84%** | **1.49%** | +0.106 | -0.44 | +0.72 |
| All | 1 hour (10:35) | 4,908 | **4.63%** | **3.52%** | +0.126 | -0.67 | +0.97 |
| | |  |  |  |  |  |  |
| Gap Up | 5 min (09:40) | 2,544 | **1.06%** | **0.16%** | +0.055 | -0.36 | +0.47 |
| Gap Up | 10 min (09:45) | 2,557 | **2.03%** | **0.98%** | +0.074 | -0.44 | +0.63 |
| Gap Up | 15 min (09:50) | 2,561 | **2.58%** | **1.80%** | +0.094 | -0.49 | +0.75 |
| Gap Up | 1 hour (10:35) | 2,567 | **5.61%** | **3.66%** | +0.113 | -0.73 | +0.99 |
| | |  |  |  |  |  |  |
| Gap Down | 5 min (09:40) | 2,326 | **0.52%** | **0.13%** | +0.065 | -0.32 | +0.47 |
| Gap Down | 10 min (09:45) | 2,343 | **0.64%** | **0.60%** | +0.085 | -0.39 | +0.58 |
| Gap Down | 15 min (09:50) | 2,343 | **1.02%** | **1.15%** | +0.119 | -0.40 | +0.69 |
| Gap Down | 1 hour (10:35) | 2,341 | **3.55%** | **3.37%** | +0.134 | -0.61 | +0.95 |
| | |  |  |  |  |  |  |
| $3B–$10B | 5 min (09:40) | 685 | **0.58%** | **0.00%** | +0.081 | -0.33 | +0.50 |
| $3B–$10B | 10 min (09:45) | 685 | **1.17%** | **1.31%** | +0.096 | -0.39 | +0.71 |
| $3B–$10B | 15 min (09:50) | 692 | **2.46%** | **2.46%** | +0.131 | -0.47 | +0.85 |
| $3B–$10B | 1 hour (10:35) | 690 | **4.64%** | **6.09%** | +0.171 | -0.63 | +1.16 |

## 5. Full decile ladder — HV + Continuation (All)

| Decile | 5 min (09:40) | 10 min (09:45) | 15 min (09:50) | 1 hour (10:35) |
|---|---:|---:|---:|---:|
| 10th | -91 | -108 | -116 | -173 |
| 20th | -45 | -54 | -58 | -95 |
| 30th | -21 | -26 | -27 | -43 |
| 40th | -4 | -4 | -0 | -6 |
| 50th | +14 | +19 | +25 | +29 |
| 60th | +30 | +40 | +51 | +63 |
| 70th | +51 | +66 | +79 | +105 |
| 80th | +76 | +100 | +119 | +160 |
| 90th | +123 | +157 | +190 | +254 |

## 6. What the shape says

| Window | Mean | Median | Mean − Median | Median after costs |
|---|---:|---:|---:|---:|
| 5 min (09:40) | +14.4 | +13.8 | +0.6 | **+7.2** |
| 10 min (09:45) | +21.4 | +18.6 | +2.8 | **+12.0** |
| 15 min (09:50) | +30.3 | +25.0 | +5.2 | **+18.4** |
| 1 hour (10:35) | +36.7 | +29.1 | +7.6 | **+22.5** |

**The median trade is profitable after costs at all 4 horizons** (+7.2 to +22.5 bps). That is a stronger result than a positive mean on its own: the edge does not depend on the right tail to reach breakeven, so an implementation that caps upside with a profit target still keeps a positive core. The mean sits +0.6 to +7.6 bps above the median, and that gap widens with the horizon — the longer the hold, the more of the average comes from the tail rather than the typical trade.

**Skew changes sign with the horizon, and that is the interesting part.**

| Window | Skew (raw) | Skew (winsorised) | Reading |
|---|---:|---:|---|
| 5 min (09:40) | -0.25 | -0.01 | roughly symmetric body |
| 10 min (09:45) | -0.06 | +0.07 | roughly symmetric body |
| 15 min (09:50) | +0.23 | +0.19 | right-skewed body — gains larger than losses |
| 1 hour (10:35) | +14.69 | +0.16 | right-skewed body — gains larger than losses |

At the short horizons (5 min (09:40), 10 min (09:45)) raw skew is **negative** — the biggest fast moves go *against* the position, even though the mean is positive. The distribution only turns right-skewed from 15 min (09:50) onward.

The winsorised column shows this is a **tail** effect, not a property of the typical trade: with the extreme 1% capped, the 5 min (09:40) and 10 min (09:45) body is essentially symmetric (-0.01, +0.07). So the risk at short horizons is not that the average losing trade is bigger — it is that the *worst* trades are, and they arrive before there has been time to react.

**Excess kurtosis stays high even after winsorising** (+1.2 to +1.4, against 0.0 for a normal), so the fat tails are a property of the population and not only of the few extreme events. Two consequences: the sample mean converges slowly, so the bootstrap intervals in the core table are the honest read rather than the point estimates; and position sizing on standard deviation will understate how often large adverse moves occur.

**On the body of the distribution, logs change almost nothing** (-0.01 to +0.01 change in winsorised skew). Over 5–60 minute windows the moves are small enough that log and simple returns are nearly identical, so the asymmetry measured here is a property of the moves rather than an artefact of percentage arithmetic. On the **raw** figures the 1 hour (10:35) window is the exception — logs move its skew by -8.06, because the log transform compresses one +100% observation far more than it compresses the rest of the sample.

### One observation drives the 1-hour shape statistics

| Window | Skew (all) | Skew (drop largest) | Kurtosis (all) | Kurtosis (drop largest) | Mean (all) | Mean (drop largest) |
|---|---:|---:|---:|---:|---:|---:|
| 5 min (09:40) | -0.25 | -0.15 | +4.5 | +3.9 | +14.4 | +14.6 |
| 10 min (09:45) | -0.06 | -0.01 | +3.7 | +3.5 | +21.4 | +21.6 |
| 15 min (09:50) | +0.23 | +0.09 | +4.9 | +3.7 | +30.3 | +30.0 |
| 1 hour (10:35) | +14.69 | +0.16 | +607.5 | +3.1 | +36.7 | +34.7 |

The five largest absolute moves in the headline group, per horizon:

| Window | # | Ticker | Date | Return (bps) | Entry | Gap |
|---|---:|---|---|---:|---:|---|
| 5 min (09:40) | 1 | QRVO | 2024-10-30 | -763 | $71.36 | Down |
| 5 min (09:40) | 2 | ZS | 2022-02-25 | +623 | $220.53 | Down |
| 5 min (09:40) | 3 | WDC | 2019-01-25 | -592 | $44.09 | Up |
| 5 min (09:40) | 4 | SNAP | 2024-08-02 | -537 | $9.68 | Down |
| 5 min (09:40) | 5 | Z | 2022-08-05 | -521 | $34.09 | Down |
| 10 min (09:45) | 1 | AVGO | 2020-03-13 | -762 | $210.48 | Up |
| 10 min (09:45) | 2 | STNE | 2021-11-17 | +741 | $25.23 | Down |
| 10 min (09:45) | 3 | TWLO | 2022-11-04 | +725 | $46.16 | Down |
| 10 min (09:45) | 4 | CAR | 2021-11-02 | +634 | $180.10 | Up |
| 10 min (09:45) | 5 | PAYC | 2024-05-02 | +614 | $171.54 | Down |
| 15 min (09:50) | 1 | CAR | 2021-11-02 | +1,311 | $180.10 | Up |
| 15 min (09:50) | 2 | STNE | 2021-11-17 | +904 | $25.23 | Down |
| 15 min (09:50) | 3 | CAR | 2021-08-04 | +883 | $85.37 | Down |
| 15 min (09:50) | 4 | PAYC | 2024-05-02 | +816 | $171.54 | Down |
| 15 min (09:50) | 5 | ENPH | 2025-04-23 | -796 | $46.14 | Down |
| 1 hour (10:35) | 1 | CAR | 2021-11-02 | +10,023 | $180.10 | Up |
| 1 hour (10:35) | 2 | STNE | 2021-11-17 | +1,217 | $25.23 | Down |
| 1 hour (10:35) | 3 | RMBS | 2023-08-01 | -1,140 | $49.38 | Down |
| 1 hour (10:35) | 4 | U | 2024-02-27 | -1,110 | $28.25 | Down |
| 1 hour (10:35) | 5 | ROKU | 2019-05-09 | +1,033 | $72.39 | Up |

**CAR on 2021-11-02 returned +10,023 bps in one hour** — a +100% move. This is not a bad print: it is the Avis Budget short squeeze, a real and widely documented session, and the position was genuinely available to a rule that bought the 09:35 open. It is kept in every table.

**The shape statistics depend on it; the edge does not.** One row out of 4,908 moves the 1-hour skew from +0.16 to +14.69 and the kurtosis from +3.1 to +608 — those two numbers describe that single session, not the strategy. But its contribution to the 1-hour mean is only +2.0 bps of +36.7 (6%): drop it entirely and the mean is still +34.7 bps. That is the reassuring result — the expectancy is carried by the broad population, not by one squeeze.

Practical reading: **quote the winsorised skew and kurtosis** (section 3b) when describing what a typical trade looks like, and the raw mean when describing what the strategy actually returned. Quoting raw skew of 14.7 as a property of the setup would be wrong in both directions — it overstates the upside asymmetry available going forward, and it implies a tail dependence the expectancy does not have.

**Gap Up versus Gap Down, on shape rather than expectancy.**

| Window | Metric | Gap Up | Gap Down |
|---|---|---:|---:|
| 5 min (09:40) | Median (bps) | +12.5 | +15.4 |
| 5 min (09:40) | Skew | -0.26 | -0.24 |
| 5 min (09:40) | % gain > 1.5 ATR | 0.16% | 0.13% |
| 5 min (09:40) | % loss > 1.0 ATR | 1.06% | 0.52% |
| 10 min (09:45) | Median (bps) | +16.7 | +20.7 |
| 10 min (09:45) | Skew | -0.20 | +0.09 |
| 10 min (09:45) | % gain > 1.5 ATR | 0.98% | 0.60% |
| 10 min (09:45) | % loss > 1.0 ATR | 2.03% | 0.64% |
| 15 min (09:50) | Median (bps) | +21.3 | +29.2 |
| 15 min (09:50) | Skew | +0.27 | +0.19 |
| 15 min (09:50) | % gain > 1.5 ATR | 1.80% | 1.15% |
| 15 min (09:50) | % loss > 1.0 ATR | 2.58% | 1.02% |
| 1 hour (10:35) | Median (bps) | +24.2 | +34.2 |
| 1 hour (10:35) | Skew | +18.65 | +0.17 |
| 1 hour (10:35) | % gain > 1.5 ATR | 3.66% | 3.37% |
| 1 hour (10:35) | % loss > 1.0 ATR | 5.61% | 3.55% |

## 7. The $3B–$10B group

Sample **does** allow it: 696 of the 4,938 High Volume Continuation events fall in $3B–$10B (4,401 have a market cap at all). Median cap in the bucket $7.4B, median price $42.

> **Cost caveat, quantified.** Median Roll spread in this bucket is **3.8 bps** against **2.7 bps** for the full High Volume Continuation cohort. The flat 6.6 bps charged in NET is therefore least defensible for exactly this group, and Roll excludes market impact entirely.

Against the full cohort:

| Window | NET, $3B–$10B | NET, All | Δ | Skew, $3B–$10B | Skew, All | % gain > 1.5 ATR |
|---|---:|---:|---:|---:|---:|---:|
| 5 min (09:40) | **+18.6** | +7.8 | +10.8 | -0.16 | -0.25 | 0.00% vs 0.14% |
| 10 min (09:45) | **+30.0** | +14.8 | +15.2 | -0.03 | -0.06 | 1.31% vs 0.80% |
| 15 min (09:50) | **+42.5** | +23.7 | +18.8 | +0.03 | +0.23 | 2.46% vs 1.49% |
| 1 hour (10:35) | **+63.5** | +30.1 | +33.4 | +0.19 | +14.69 | 6.09% vs 3.52% |

## 8. Dropped zero-return observations

A print-to-print move of exactly zero is a stale quote rather than a flat trade, and every previous report in this series drops them. The share is material at the shortest horizon, so it is reported rather than buried:

| Window | n before | n zero | % dropped |
|---|---:|---:|---:|
| 5 min (09:40) | 4,938 | 68 | 1.38% |
| 10 min (09:45) | 4,938 | 38 | 0.77% |
| 15 min (09:50) | 4,938 | 34 | 0.69% |
| 1 hour (10:35) | 4,938 | 30 | 0.61% |

At 5 min (09:40) this removes 1.4% of the sample. Those observations are neither wins nor losses; including them would lower the win rate and pull the median toward zero without changing the mean much.

## 9. Reading notes

- **The expectancy gain with horizon comes from move size, not from hit rate.** Win rate is essentially flat across the four windows (58.3%–59.9%) while the average win grows from 72 to 154 bps and the payoff ratio from 1.09 to 1.21. Holding longer does not make the rule more often right; it makes the right calls bigger.
- **Kurtosis is excess** — a normal reads 0.0. Raw values here run +3.7 to +608; winsorised, +1.2 to +1.4. Even the winsorised figures are meaningfully fat-tailed, which is why every significance test in this series is a date-clustered bootstrap rather than a t-test.
- **The ATR tail columns use prior-session ATR(14)**, known before entry, so they are implementable as stop/target distances. They are *realised* frequencies with no stop in place — a live stop at −1.0 ATR would convert some of the >1.5 ATR gains into losses, because part of that tail traded through the stop first. This is an upper bound on what a stop-and-target implementation would capture.
- **Costs are flat 6.6 bps** and do not vary by group, horizon or market cap. Section 7 quantifies where that assumption is weakest.
- **The groups overlap.** Gap Up and Gap Down partition the headline group; $3B–$10B is a subset of it. These are four views of one sample, not four independent tests.

---

_Reproducible from `lambda_strategy_validation/dist.py`; tables in `lambda_data/tables/dist_*.csv`._