# Lambda — How the Return Distribution Shifts Across Periods, and What Stops and Sizing Do To It

**Cohort.** Post-earnings T+1 with a non-zero gap; High Volume (`c1_volume` > 1.5× the trailing 20-session same-slot mean, shifted one session); **Continuation** = the 09:30–09:35 candle closes in the gap's direction and is **not** a doji, where doji means body/range ≤ 0.10. Entry at the open of the 09:35 bar, hold to 10:35. Corrected universe screen applied. ATR is the prior session's ATR(14). Costs 6.6 bps round trip.

4,270 events, 2015-01-27 → 2025-12-19.

> **Everything is per unit of average notional deployed.** For a weight vector `w` the per-trade series is `w_i × (return_i − cost) / mean(w)`, so the mean is the return on capital actually committed and the percentiles describe the P&L a book of that shape would live through. Without that, a scheme that merely deploys less capital would look calmer and less profitable for no reason but leverage.

> **Two versions of "% losing more than 1 ATR".** Sizing cannot change whether a *trade* moved 1 ATR against entry — that is the price path — so the **trade-count** version is identical for B, C and D by construction, and only the stop moves it. What sizing changes is how much capital stood in front of those moves, which is the **notional-weighted** version. Both are given; reading only the first would make sizing look inert when it is not.

## 2015–2019

n = 1,840; the ATR −1.0 stop fires on 9.7% of them. Tier mix: 40.3% High Risk, 22.4% Medium, 37.3% Low Risk.

| Config | Eff. n | Mean (NET) | Median | Std | p10 | p25 | p75 | p90 | Skew (w) | Kurt (w) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A — No stop, equal size | 1,840 | **+34.9** | +23.0 | 171 | -141 | -56 | +117 | +230 | +0.40 | +1.3 |
| B — ATR −1.0 stop, equal size | 1,840 | **+31.1** | +21.3 | 170 | -163 | -64 | +116 | +227 | +0.47 | +1.0 |
| C — ATR −1.0 stop + three-tier sizing | 1,612 | **+28.4** | +20.4 | 153 | -138 | -60 | +102 | +207 | +0.44 | +0.9 |
| D — ATR −1.0 stop + fixed dollar risk | 1,596 | **+26.2** | +21.0 | 142 | -184 | -58 | +103 | +199 | +0.48 | +0.6 |

| Config | % loss > 0.5 ATR | % loss > 1 ATR | % gain > 1 ATR | *Wtd* loss > 1 ATR | Avg large loss | NET / Std |
|---|---:|---:|---:|---:|---:|---:|
| A — No stop, equal size | 13.42% | 3.48% | 10.60% | 3.48% | -324 | 0.2039 |
| B — ATR −1.0 stop, equal size | 16.09% | 0.49% | 10.33% | 0.49% | -263 | 0.1832 |
| C — ATR −1.0 stop + three-tier sizing | 16.09% | 0.49% | 10.33% | 0.44% | -243 | 0.1855 |
| D — ATR −1.0 stop + fixed dollar risk | 16.09% | 0.49% | 10.33% | 0.48% | -220 | 0.1842 |

## 2020–2022

n = 1,102; the ATR −1.0 stop fires on 9.0% of them. Tier mix: 37.5% High Risk, 26.5% Medium, 36.0% Low Risk.

| Config | Eff. n | Mean (NET) | Median | Std | p10 | p25 | p75 | p90 | Skew (w) | Kurt (w) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A — No stop, equal size | 1,102 | **+24.6** | +23.2 | 204 | -203 | -86 | +124 | +251 | +0.21 | +1.3 |
| B — ATR −1.0 stop, equal size | 1,102 | **+19.6** | +20.6 | 208 | -224 | -93 | +123 | +251 | +0.16 | +1.2 |
| C — ATR −1.0 stop + three-tier sizing | 974 | **+20.5** | +21.2 | 195 | -199 | -80 | +119 | +252 | +0.05 | +0.8 |
| D — ATR −1.0 stop + fixed dollar risk | 943 | **+18.6** | +20.7 | 169 | -232 | -81 | +119 | +226 | +0.09 | -0.1 |

| Config | % loss > 0.5 ATR | % loss > 1 ATR | % gain > 1 ATR | *Wtd* loss > 1 ATR | Avg large loss | NET / Std |
|---|---:|---:|---:|---:|---:|---:|
| A — No stop, equal size | 13.79% | 3.81% | 6.81% | 3.81% | -382 | 0.1204 |
| B — ATR −1.0 stop, equal size | 15.88% | 0.82% | 6.72% | 0.82% | -359 | 0.0942 |
| C — ATR −1.0 stop + three-tier sizing | 15.88% | 0.82% | 6.72% | 0.65% | -262 | 0.1053 |
| D — ATR −1.0 stop + fixed dollar risk | 15.88% | 0.82% | 6.72% | 0.89% | -310 | 0.1097 |

## 2023–2025

n = 1,328; the ATR −1.0 stop fires on 13.2% of them. Tier mix: 57.8% High Risk, 19.5% Medium, 22.7% Low Risk.

| Config | Eff. n | Mean (NET) | Median | Std | p10 | p25 | p75 | p90 | Skew (w) | Kurt (w) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A — No stop, equal size | 1,328 | **+24.9** | +17.7 | 196 | -200 | -85 | +130 | +261 | +0.17 | +0.6 |
| B — ATR −1.0 stop, equal size | 1,328 | **+22.0** | +12.5 | 191 | -209 | -100 | +128 | +259 | +0.41 | +0.3 |
| C — ATR −1.0 stop + three-tier sizing | 1,128 | **+20.8** | +11.5 | 181 | -180 | -95 | +117 | +237 | +0.41 | +0.8 |
| D — ATR −1.0 stop + fixed dollar risk | 1,169 | **+15.7** | +12.4 | 169 | -237 | -98 | +116 | +215 | +0.39 | +0.1 |

| Config | % loss > 0.5 ATR | % loss > 1 ATR | % gain > 1 ATR | *Wtd* loss > 1 ATR | Avg large loss | NET / Std |
|---|---:|---:|---:|---:|---:|---:|
| A — No stop, equal size | 17.85% | 6.33% | 9.49% | 6.33% | -348 | 0.1270 |
| B — ATR −1.0 stop, equal size | 20.86% | 1.88% | 9.26% | 1.88% | -225 | 0.1153 |
| C — ATR −1.0 stop + three-tier sizing | 20.86% | 1.88% | 9.26% | 1.47% | -182 | 0.1149 |
| D — ATR −1.0 stop + fixed dollar risk | 20.86% | 1.88% | 9.26% | 2.32% | -258 | 0.0928 |

## The baseline distribution, period by period

| Period | Mean | Median | Std | p10 | p90 | Skew (w) | Kurt (w) | % loss > 0.5 ATR | % loss > 1 ATR | % gain > 1 ATR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2015–2019 | **+34.9** | +23.0 | 171 | -141 | +230 | +0.40 | +1.3 | 13.42% | 3.48% | 10.60% |
| 2020–2022 | **+24.6** | +23.2 | 204 | -203 | +251 | +0.21 | +1.3 | 13.79% | 3.81% | 6.81% |
| 2023–2025 | **+24.9** | +17.7 | 196 | -200 | +261 | +0.17 | +0.6 | 17.85% | 6.33% | 9.49% |

**The distribution has widened on both sides, and moved left on net.** p10 goes from -141 to -200 while p90 goes from +230 to +261; the >1 ATR loss rate rises 3.48% → 6.33% and the >1 ATR gain rate 10.60% → 9.49%. This is not a pure left-tail story — both tails are fatter — but the left one grew by more relative to where it started, and the mean fell 10.0 bps.

**Much of that is a change in what the setup is catching, not a change in how it performs.** The cohort's own composition shifted:

| Period | n | % High Risk | % Low Risk | Median Gap/ATR | Median vol ratio | % stopped by ATR −1.0 |
|---|---:|---:|---:|---:|---:|---:|
| 2015–2019 | 1,840 | 40.3% | 37.3% | 0.56 | 3.62 | 9.7% |
| 2020–2022 | 1,102 | 37.5% | 36.0% | 0.63 | 3.47 | 9.0% |
| 2023–2025 | 1,328 | 57.8% | 22.7% | 0.83 | 5.32 | 13.2% |

The High Risk share goes from 40.3% to 57.8%, the median gap from 0.56 to 0.83 ATR and the median volume ratio from 3.62× to 5.32×. The recent cohort is a structurally more violent set of events passing the same filter — which explains the fatter tails on **both** sides without needing the edge itself to have decayed as much as the headline mean suggests.

## How the left tail moves from A → B → C → D

| Period | Metric | A | B | C | D | A → D |
|---|---|---:|---:|---:|---:|---:|
| 2015–2019 | p10 | -141 | -163 | -138 | -184 | -43 |
| 2015–2019 | % loss > 1 ATR (trades) | 3.48% | 0.49% | 0.49% | 0.49% | -2.99% |
| 2015–2019 | % loss > 1 ATR (notional) | 3.48% | 0.49% | 0.44% | 0.48% | -3.00% |
| 2015–2019 | Avg large loss | -324 | -263 | -243 | -220 | +105 |
| 2015–2019 | Std dev | 171 | 170 | 153 | 142 | -29 |
| | | | | | | |
| 2020–2022 | p10 | -203 | -224 | -199 | -232 | -29 |
| 2020–2022 | % loss > 1 ATR (trades) | 3.81% | 0.82% | 0.82% | 0.82% | -2.99% |
| 2020–2022 | % loss > 1 ATR (notional) | 3.81% | 0.82% | 0.65% | 0.89% | -2.92% |
| 2020–2022 | Avg large loss | -382 | -359 | -262 | -310 | +71 |
| 2020–2022 | Std dev | 204 | 208 | 195 | 169 | -35 |
| | | | | | | |
| 2023–2025 | p10 | -200 | -209 | -180 | -237 | -37 |
| 2023–2025 | % loss > 1 ATR (trades) | 6.33% | 1.88% | 1.88% | 1.88% | -4.44% |
| 2023–2025 | % loss > 1 ATR (notional) | 6.33% | 1.88% | 1.47% | 2.32% | -4.01% |
| 2023–2025 | Avg large loss | -348 | -225 | -182 | -258 | +90 |
| 2023–2025 | Std dev | 196 | 191 | 181 | 169 | -27 |
| | | | | | | |

**2015–2019.** The stop alone (A→B) cuts the >1 ATR loss rate from 3.48% to 0.49% but **worsens** p10, from -141 to -163, at a cost of 3.8 bps of mean. Adding sizing (B→C) moves the notional-weighted large-loss exposure from 0.49% to 0.44% and the standard deviation from 170 to 153; volatility targeting (D) takes them to 0.48% and 142. Risk-adjusted, the four run 0.2039 / 0.1832 / 0.1855 / 0.1842.

**2020–2022.** The stop alone (A→B) cuts the >1 ATR loss rate from 3.81% to 0.82% but **worsens** p10, from -203 to -224, at a cost of 5.0 bps of mean. Adding sizing (B→C) moves the notional-weighted large-loss exposure from 0.82% to 0.65% and the standard deviation from 208 to 195; volatility targeting (D) takes them to 0.89% and 169. Risk-adjusted, the four run 0.1204 / 0.0942 / 0.1053 / 0.1097.

**2023–2025.** The stop alone (A→B) cuts the >1 ATR loss rate from 6.33% to 1.88% but **worsens** p10, from -200 to -209, at a cost of 3.0 bps of mean. Adding sizing (B→C) moves the notional-weighted large-loss exposure from 1.88% to 1.47% and the standard deviation from 191 to 181; volatility targeting (D) takes them to 2.32% and 169. Risk-adjusted, the four run 0.1270 / 0.1153 / 0.1149 / 0.0928.

## Are the stop and the sizing worth more in 2023–2025?

| Period | A mean | B mean | Stop cost | A p10 | B p10 | p10 change | Tail cut (pp) | **pp per bp** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2015–2019 | +34.9 | +31.1 | +3.8 | -141 | -163 | -22 | 2.99 | **0.78** |
| 2020–2022 | +24.6 | +19.6 | +5.0 | -203 | -224 | -21 | 2.99 | **0.60** |
| 2023–2025 | +24.9 | +22.0 | +3.0 | -200 | -209 | -8 | 4.44 | **1.50** |

**Yes for the stop.** Its efficiency rises from 0.78 pp per bp in 2015–2019 to 1.50 in 2023–2025 — it removes more tail and charges less for it, because there is less expectancy left to give up and more tail to remove. That is the same conclusion `REGIME_REPORT.md` reached, now visible in the shape of the distribution rather than only in the summary statistics.

| Period | Best NET/Std | Config | Equal-size (B) NET/Std | Gain |
|---|---:|---|---:|---:|
| 2015–2019 | 0.2039 | A | 0.1832 | +0.0207 |
| 2020–2022 | 0.1204 | A | 0.0942 | +0.0261 |
| 2023–2025 | 0.1270 | A | 0.1153 | +0.0118 |

**A is the best risk-adjusted configuration in all three periods**, which is at least consistent across time even if the margins are narrow.

**These two results are not in conflict, and the distinction matters.** The stop's *tail efficiency* genuinely improves in the recent period — it removes more of the >1 ATR tail per basis point surrendered than it used to. But it still does not improve *return per unit of total volatility*, in any period, because the volatility it removes is concentrated in a tail that contributes little to the standard deviation, while the expectancy it removes comes straight off the mean.

So the honest answer depends on which risk you are managing. If the constraint is a per-trade loss limit or a drawdown tolerance driven by extremes, the stop is worth more now than it has ever been in this data. If the objective is return per unit of variance, no stop and equal size still wins, in 2023–2025 as in 2015–2019.

## Effect on the right tail and overall shape

| Period | Config | p90 | % gain > 1 ATR | *Wtd* gain > 1 ATR | Skew (w) | Kurt (w) |
|---|---|---:|---:|---:|---:|---:|
| 2015–2019 | A | +230 | 10.60% | 10.60% | +0.40 | +1.3 |
| 2015–2019 | B | +227 | 10.33% | 10.33% | +0.47 | +1.0 |
| 2015–2019 | C | +207 | 10.33% | 8.26% | +0.44 | +0.9 |
| 2015–2019 | D | +199 | 10.33% | 10.84% | +0.48 | +0.6 |
| | | | | | | |
| 2020–2022 | A | +251 | 6.81% | 6.81% | +0.21 | +1.3 |
| 2020–2022 | B | +251 | 6.72% | 6.72% | +0.16 | +1.2 |
| 2020–2022 | C | +252 | 6.72% | 5.63% | +0.05 | +0.8 |
| 2020–2022 | D | +226 | 6.72% | 7.12% | +0.09 | -0.1 |
| | | | | | | |
| 2023–2025 | A | +261 | 9.49% | 9.49% | +0.17 | +0.6 |
| 2023–2025 | B | +259 | 9.26% | 9.26% | +0.41 | +0.3 |
| 2023–2025 | C | +237 | 9.26% | 7.68% | +0.41 | +0.8 |
| 2023–2025 | D | +215 | 9.26% | 10.00% | +0.39 | +0.1 |
| | | | | | | |

**The stop barely touches the right tail** — the >1 ATR gain rate moves by 0.09 to 0.27 pp between A and B, because a stop can only fire on an adverse excursion and the trades that ran never came near it. The p90 column says the same thing. This is the one respect in which the ATR stop is a clean instrument: it truncates one side of the distribution and leaves the other essentially intact.

Sizing is different, and the notional-weighted gain column shows why. Scheme C deliberately holds less of the High Risk tier, and that tier owns a disproportionate share of the large winners as well as the large losers — so C's weighted upside exposure falls alongside its weighted downside. Volatility targeting (D) does the same thing more smoothly and more aggressively, which is why it compresses the standard deviation most and the mean with it.

## Reading notes

- **Three periods is three observations.** The 2020–2022 block contains both the COVID crash and the 2021 meme episode; it is not a regime so much as two unrepeatable events sharing a bucket.
- **Winsorised skew and kurtosis at 1/99** are shown as the primary shape statistics. Raw values are carried in the CSVs and are dominated by single observations, which makes them useless for comparing periods.
- **The tier thresholds and the 1.25/1.0/0.5 weights were not fitted**, but they were chosen after seeing earlier segment tables, which is weaker than choosing them in advance.
- **Scheme D is uncapped.** Its weight is proportional to 1/ATR%, so the quietest names attract multiples of the average position. A real implementation caps that, and the cap would change its numbers here.
- **Costs scale with notional**, so a half-size trade pays half. That is right for a spread-driven cost and wrong for any fixed per-ticket component.
- **No compounding, no concurrency limit, no portfolio construction.** These are per-trade distributions, not equity curves.

---

_Reproducible from `lambda_strategy_validation/distshift.py`; tables in `lambda_data/tables/ds_*.csv`._