# Lambda — Effectiveness of the Risk-Management Configurations Across Periods

**Cohort.** Post-earnings T+1 with a non-zero gap; High Volume (`c1_volume` > 1.5× the trailing 20-session same-slot mean, shifted one session); **Continuation** = the 09:30–09:35 candle closes in the gap's direction and is not a doji (doji = body/range ≤ 0.10). Entry at the open of the 09:35 bar, hold to 10:35. Corrected universe screen. Prior-session ATR(14). Costs 6.6 bps round trip.

4,270 events, 2015-01-27 → 2025-12-19.

> **Three definitional choices worth stating, because each has a defensible alternative.**
>
> **Profit factor** is computed on the realised, *after-cost* series: profitable trades are those that cleared 6.6 bps. That is what reconciles to a blotter. The pre-cost version is in the CSV and runs materially higher.
>
> **MAE and MFE are measured over each trade's actual holding window**, so a stopped trade's excursions end at its stop minute rather than running to 10:35. Measuring to a fixed hour would credit the stop with excursions it never lived through. Since sizing does not change *when* a trade exits, trade-level MAE and MFE are identical for B, C and D — the notional-weighted versions are not, and both are given.
>
> **Everything is per unit of average notional deployed**, `w_i × (return_i − cost) / mean(w)`, so schemes are compared on capital committed rather than on leverage.

## 1. Core performance

| Period | Config | n | Eff. n | Win rate | Avg Win | Avg Loss | Payoff | **NET** | Median |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2015–2019 | A | 1,840 | 1,840 | 58.5% | 134.5 | 105.7 | 1.27 | **+34.9** | +23.0 |
| 2015–2019 | B | 1,840 | 1,840 | 57.6% | 134.8 | 109.7 | 1.23 | **+31.1** | +21.3 |
| 2015–2019 | C | 1,840 | 1,612 | 57.6% | 122.6 | 99.4 | 1.23 | **+28.4** | +20.4 |
| 2015–2019 | D | 1,840 | 1,596 | 57.6% | 117.7 | 97.8 | 1.20 | **+26.2** | +21.0 |
| | | | | | | | | | |
| 2020–2022 | A | 1,102 | 1,102 | 56.7% | 152.2 | 142.7 | 1.07 | **+24.6** | +23.2 |
| 2020–2022 | B | 1,102 | 1,102 | 56.0% | 153.1 | 150.2 | 1.02 | **+19.6** | +20.6 |
| 2020–2022 | C | 1,102 | 974 | 56.0% | 143.6 | 136.1 | 1.05 | **+20.5** | +21.2 |
| 2020–2022 | D | 1,102 | 943 | 56.0% | 134.2 | 128.5 | 1.04 | **+18.6** | +20.7 |
| | | | | | | | | | |
| 2023–2025 | A | 1,328 | 1,328 | 54.2% | 156.8 | 131.3 | 1.19 | **+24.9** | +17.7 |
| 2023–2025 | B | 1,328 | 1,328 | 53.0% | 157.5 | 130.9 | 1.20 | **+22.0** | +12.5 |
| 2023–2025 | C | 1,328 | 1,128 | 53.0% | 146.1 | 120.6 | 1.21 | **+20.8** | +11.5 |
| 2023–2025 | D | 1,328 | 1,169 | 53.0% | 139.0 | 123.4 | 1.13 | **+15.7** | +12.4 |
| | | | | | | | | | |

Win rate here is the share of trades finishing **above cost**, which is why it sits below the gross hit rates quoted in earlier reports. It is identical across B, C and D because sizing cannot change a trade's sign.

## 2. Risk and distribution

| Period | Config | Std | **NET / Std** | p10 | % loss > 0.5 ATR | % loss > 1 ATR | Avg large loss | % gain > 1 ATR |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2015–2019 | A | 171 | **0.2039** | -141 | 13.42% | 3.48% | -324 | 10.60% |
| 2015–2019 | B | 170 | **0.1832** | -163 | 16.09% | 0.49% | -263 | 10.33% |
| 2015–2019 | C | 153 | **0.1855** | -138 | 16.09% | 0.49% | -243 | 10.33% |
| 2015–2019 | D | 142 | **0.1842** | -184 | 16.09% | 0.49% | -220 | 10.33% |
| | | | | | | | | |
| 2020–2022 | A | 204 | **0.1204** | -203 | 13.79% | 3.81% | -382 | 6.81% |
| 2020–2022 | B | 208 | **0.0942** | -224 | 15.88% | 0.82% | -359 | 6.72% |
| 2020–2022 | C | 195 | **0.1053** | -199 | 15.88% | 0.82% | -262 | 6.72% |
| 2020–2022 | D | 169 | **0.1097** | -232 | 15.88% | 0.82% | -310 | 6.72% |
| | | | | | | | | |
| 2023–2025 | A | 196 | **0.1270** | -200 | 17.85% | 6.33% | -348 | 9.49% |
| 2023–2025 | B | 191 | **0.1153** | -209 | 20.86% | 1.88% | -225 | 9.26% |
| 2023–2025 | C | 181 | **0.1149** | -180 | 20.86% | 1.88% | -182 | 9.26% |
| 2023–2025 | D | 169 | **0.0928** | -237 | 20.86% | 1.88% | -258 | 9.26% |
| | | | | | | | | |

## 3. Additional effectiveness metrics

| Period | Config | Profit factor | Avg MAE (ATR) | Avg MFE (ATR) | *Wtd* MAE | *Wtd* MFE | % of NET from best decile |
|---|---|---:|---:|---:|---:|---:|---:|
| 2015–2019 | A | 1.796 | -0.436 | +0.683 | -0.436 | +0.683 | 105% |
| 2015–2019 | B | 1.668 | -0.407 | +0.673 | -0.407 | +0.673 | 118% |
| 2015–2019 | C | 1.673 | -0.407 | +0.673 | -0.376 | +0.618 | 116% |
| 2015–2019 | D | 1.632 | -0.407 | +0.673 | -0.422 | +0.699 | 116% |
| | | | | | | | |
| 2020–2022 | A | 1.398 | -0.430 | +0.583 | -0.430 | +0.583 | 168% |
| 2020–2022 | B | 1.297 | -0.400 | +0.578 | -0.400 | +0.578 | 210% |
| 2020–2022 | C | 1.342 | -0.400 | +0.578 | -0.370 | +0.554 | 184% |
| 2020–2022 | D | 1.329 | -0.400 | +0.578 | -0.410 | +0.612 | 178% |
| | | | | | | | |
| 2023–2025 | A | 1.415 | -0.497 | +0.641 | -0.497 | +0.641 | 158% |
| 2023–2025 | B | 1.357 | -0.444 | +0.634 | -0.444 | +0.634 | 179% |
| 2023–2025 | C | 1.367 | -0.444 | +0.634 | -0.409 | +0.588 | 178% |
| 2023–2025 | D | 1.271 | -0.444 | +0.634 | -0.465 | +0.660 | 218% |
| | | | | | | | |

The best-decile column is the share of total NET produced by the top 10% of trades. Values above 100% mean the remaining 90% are collectively negative — the strategy's entire result comes from its best decile and the rest, after costs, is a drag.

## 4. Best trade-off in each period

| Period | Best NET | Best NET/Std | Best profit factor | Best p10 | Lowest large-loss rate |
|---|---|---|---|---|---|
| 2015–2019 | A (+34.9) | A (0.2039) | A (1.796) | C (-138) | B (0.49%) |
| 2020–2022 | A (+24.6) | A (0.1204) | A (1.398) | C (-199) | B (0.82%) |
| 2023–2025 | A (+24.9) | A (0.1270) | A (1.415) | C (-180) | B (1.88%) |

**A wins on return per unit of volatility in every period.** No configuration that adds a stop or a sizing rule improves that measure, at any point in the sample.

But the columns disagree with each other, and that is the substance of this report. The configuration with the best expectancy, the best p10 and the smallest large-loss rate are generally three different configurations — so "best trade-off" has no answer independent of which risk is binding:

| If the binding constraint is… | Choose | Because |
|---|---|---|
| Expectancy, or return per unit of variance | **A** | highest NET and highest NET/Std in all three periods |
| A hard per-trade loss limit | **B** | cuts the >1 ATR rate by roughly two-thirds to three-quarters everywhere |
| Drawdown at the 10th percentile | **C** | the only configuration that improves p10 against no stop |
| Equalising risk across names | **D** | lowest standard deviation in every period, at the largest cost in NET |

## 5. Has the value of the stop and of sizing increased in 2023–2025?

**The stop (A → B):**

| Period | NET cost | >1 ATR: A → B | Tail cut (pp) | **pp per bp** | Profit factor A → B | NET/Std A → B |
|---|---:|---:|---:|---:|---:|---:|
| 2015–2019 | +3.8 | 3.48% → 0.49% | 2.99 | **0.78** | 1.796 → 1.668 | 0.2039 → 0.1832 |
| 2020–2022 | +5.0 | 3.81% → 0.82% | 2.99 | **0.60** | 1.398 → 1.297 | 0.1204 → 0.0942 |
| 2023–2025 | +3.0 | 6.33% → 1.88% | 4.44 | **1.50** | 1.415 → 1.357 | 0.1270 → 0.1153 |

**Yes on tail efficiency** — 0.78 pp per bp in 2015–2019 against 1.50 in 2023–2025, roughly double. **No on every other measure**: profit factor and NET/Std both still fall when the stop is added, in the recent period as in the early one. The stop buys more tail protection per basis point than it used to, and it still does not pay for itself in return terms.

**The sizing (B → C and B → D):**

| Period | B NET/Std | C NET/Std | D NET/Std | C gain | D gain | C p10 gain vs B | D p10 gain vs B |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2015–2019 | 0.1832 | 0.1855 | 0.1842 | +0.0023 | +0.0011 | +25 | -21 |
| 2020–2022 | 0.0942 | 0.1053 | 0.1097 | +0.0111 | +0.0154 | +25 | -8 |
| 2023–2025 | 0.1153 | 0.1149 | 0.0928 | -0.0004 | -0.0225 | +28 | -29 |

Three-tier sizing improves on the stop alone in 2 of 3 periods (by +0.0023 to +0.0111), and is flat to marginally worse in the other (-0.0004). Every one of those moves is small against a NET/Std of 0.20–0.13 for the baseline, and none recovers the ground the stop gave up against A.

**The one thing sizing does reliably is p10.** Three-tier improves it against the stop alone by +25 to +28 bps in all three periods, and against *no stop at all* in all three. If the 10th percentile is what governs the risk budget, C is the only configuration in this study that helps.

## 6. Three-tier sizing versus fixed dollar risk

| Period | Metric | C (three-tier) | D (fixed $ risk) | Difference |
|---|---|---:|---:|---:|
| 2015–2019 | NET | +28.4 | +26.2 | -2.2 |
| 2015–2019 | Std | 153 | 142 | -11 |
| 2015–2019 | NET/Std | 0.1855 | 0.1842 | -0.0012 |
| 2015–2019 | p10 | -138 | -184 | -46 |
| 2015–2019 | Profit factor | 1.673 | 1.632 | -0.041 |
| 2015–2019 | Wtd loss > 1 ATR | 0.44% | 0.48% | +0.04% |
| 2015–2019 | Best-decile share | 116% | 116% | +0% |
| | | | | |
| 2020–2022 | NET | +20.5 | +18.6 | -1.9 |
| 2020–2022 | Std | 195 | 169 | -25 |
| 2020–2022 | NET/Std | 0.1053 | 0.1097 | +0.0044 |
| 2020–2022 | p10 | -199 | -232 | -33 |
| 2020–2022 | Profit factor | 1.342 | 1.329 | -0.013 |
| 2020–2022 | Wtd loss > 1 ATR | 0.65% | 0.89% | +0.24% |
| 2020–2022 | Best-decile share | 184% | 178% | -7% |
| | | | | |
| 2023–2025 | NET | +20.8 | +15.7 | -5.1 |
| 2023–2025 | Std | 181 | 169 | -12 |
| 2023–2025 | NET/Std | 0.1149 | 0.0928 | -0.0221 |
| 2023–2025 | p10 | -180 | -237 | -57 |
| 2023–2025 | Profit factor | 1.367 | 1.271 | -0.096 |
| 2023–2025 | Wtd loss > 1 ATR | 1.47% | 2.32% | +0.85% |
| 2023–2025 | Best-decile share | 178% | 218% | +40% |
| | | | | |

**They are not two flavours of the same idea, and the difference is which variable they act on.**

Three-tier sizing conditions on the *signal's* risk — how big the gap is relative to ATR, how heavy the opening volume was. It cuts exposure to events that are unusual **for that stock**, and it leaves a quiet name in a quiet setup at full size.

Fixed dollar risk conditions on the *stock's* volatility alone and ignores the setup entirely. Its weight is proportional to 1/ATR%, so it systematically overweights low-volatility names — which is why it produces the lowest standard deviation in every period and, in this sample, the worst p10. Concentrating capital in quiet names is not the same as avoiding losses: when a quiet name gaps against you, the position is large.

That shows up directly: D's p10 is worse than C's in every period, by 33 to 57 bps, despite D having the lower standard deviation. **Standard deviation and tail risk point in opposite directions for D**, which is the single most important caveat on volatility targeting here.

## Reading notes

- **Three periods is three observations**, and 2020–2022 contains both the COVID crash and the 2021 meme episode.
- **Profit factors below 1.0 with a positive NET are impossible; above 1.0 with a negative NET likewise.** Where profit factor and NET rank configurations differently, it is because profit factor ignores the size of the average trade and NET does not.
- **D is uncapped.** Its maximum weight is several times the average; a real implementation would cap it, and the cap would change its numbers more than any other choice in this report.
- **Costs scale with notional**, so a half-size trade pays half — right for spread, wrong for any per-ticket component.
- **No compounding, concurrency limit or portfolio construction.** These are per-trade distributions, not equity curves, and the NET/Std column is not a Sharpe ratio.

---

_Reproducible from `lambda_strategy_validation/effectiveness.py`; table in `lambda_data/tables/eff_grid.csv`._