# Lambda — The Core Edge in ATR Units

Post-earnings T+1, High Volume + Continuation (non-doji), entry at the open of the 09:35 bar. The same results as `DIST_REPORT.md`, rescaled so a move is measured against what the stock normally does in a day rather than against its price.

| Input | Definition |
|---|---|
| Universe | Post-earnings T+1, 2015-01-27 → 2025-12-22 |
| Cohort | 4,938 events |
| ATR | **prior-session** ATR(14); no gap-day data |
| ATR return | signed price move ÷ prior ATR(14) |
| Cost | 6.6 bps round trip, converted **per trade** into ATR |
| Inference | date-clustered bootstrap; ⚠ marks n < 150 |

> **The cost conversion is not a constant, and that is the whole point.** 6.6 bps is a fixed fraction of *price*, so in ATR units it becomes `0.00066 × entry ÷ ATR` — large for a quiet name whose ATR is a small share of its price, small for a volatile one. Net expectancy in ATR is `mean(return − cost)` computed trade by trade, not the ATR mean minus one number. Section 3 shows the spread.

> **Win rate is identical in both views** — dividing by a positive ATR cannot flip a sign. Everything else can move, and the payoff ratio moves most, because it is a ratio of two means and each trade carries its own denominator.

## 1. ATR units

| Window | n | Win rate | Avg | Median | Avg Win | Avg Loss | Payoff | **NET** | p10 | p90 | % loss > 1 ATR | % gain > 1 ATR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 min (09:40) | 4,870 | 58.3% | +0.0607 | +0.0588 | 0.2832 | 0.2506 | 1.13 | **+0.0317** | -0.343 | +0.472 | 0.80% | 1.50% |
| 10 min (09:45) | 4,900 | 58.8% | +0.0896 | +0.0791 | 0.3654 | 0.3040 | 1.20 | **+0.0606** | -0.412 | +0.610 | 1.37% | 3.14% |
| 15 min (09:50) | 4,904 | 59.9% | +0.1215 | +0.1059 | 0.4272 | 0.3357 | 1.27 | **+0.0925** | -0.444 | +0.717 | 1.84% | 4.85% |
| 1 hour (10:35) | 4,908 | 58.4% | +0.1397 | +0.1256 | 0.5857 | 0.4852 | 1.21 | **+0.1107** | -0.673 | +0.970 | 4.63% | 9.25% |

All figures are fractions of one prior-session ATR(14). NET is mean expectancy per trade after the per-trade ATR cost.

## 2. Side by side with basis points

| Window | Metric | ATR | bps |
|---|---|---:|---:|
| 5 min (09:40) | n | 4,870 | 4,870 |
|  | Win rate | 58.3% | 58.3% |
|  | Average | +0.0607 | +14.4 |
|  | Median | +0.0588 | +13.8 |
|  | Average Win | 0.2832 | 72.0 |
|  | Average Loss | 0.2506 | 66.2 |
|  | Payoff | 1.13 | 1.09 |
|  | **NET** | **+0.0317** | **+7.8** |
|  | p10 | -0.343 | -91 |
|  | p90 | +0.472 | +123 |
| | | | |
| 10 min (09:45) | n | 4,900 | 4,900 |
|  | Win rate | 58.8% | 58.8% |
|  | Average | +0.0896 | +21.4 |
|  | Median | +0.0791 | +18.6 |
|  | Average Win | 0.3654 | 93.2 |
|  | Average Loss | 0.3040 | 81.0 |
|  | Payoff | 1.20 | 1.15 |
|  | **NET** | **+0.0606** | **+14.8** |
|  | p10 | -0.412 | -108 |
|  | p90 | +0.610 | +157 |
| | | | |
| 15 min (09:50) | n | 4,904 | 4,904 |
|  | Win rate | 59.9% | 59.9% |
|  | Average | +0.1215 | +30.3 |
|  | Median | +0.1059 | +25.0 |
|  | Average Win | 0.4272 | 110.3 |
|  | Average Loss | 0.3357 | 89.5 |
|  | Payoff | 1.27 | 1.23 |
|  | **NET** | **+0.0925** | **+23.7** |
|  | p10 | -0.444 | -116 |
|  | p90 | +0.717 | +190 |
| | | | |
| 1 hour (10:35) | n | 4,908 | 4,908 |
|  | Win rate | 58.4% | 58.4% |
|  | Average | +0.1397 | +36.7 |
|  | Median | +0.1256 | +29.1 |
|  | Average Win | 0.5857 | 153.6 |
|  | Average Loss | 0.4852 | 127.0 |
|  | Payoff | 1.21 | 1.21 |
|  | **NET** | **+0.1107** | **+30.1** |
|  | p10 | -0.673 | -173 |
|  | p90 | +0.970 | +254 |
| | | | |

The bps column reproduces `DIST_REPORT.md` exactly, including its convention of dropping exactly-zero returns, so the two reports agree line for line.

## 3. What 6.6 bps actually costs in ATR

| Metric | p10 | p25 | p50 | p75 | p90 | Mean |
|---|---:|---:|---:|---:|---:|---:|
| ATR as % of entry price | 1.47 | 1.81 | 2.40 | 3.27 | 4.43 | 2.74 |
| 6.6 bps expressed in ATR | 0.0149 | 0.0202 | 0.0275 | 0.0365 | 0.0450 | 0.0290 |

The median trade pays **0.0275 ATR** in costs, but the quietest decile pays 0.0450 — 1.6× as much in ATR terms for the identical 6.6 bps. A flat basis-point cost is a **volatility-dependent** cost once you think in ATR, and it penalises exactly the low-volatility names that a bps view makes look cheap to trade.

Set against the gross edge, that cost is not a rounding error:

| Window | Gross (ATR) | Cost (ATR) | **Cost as % of gross** | NET (ATR) |
|---|---:|---:|---:|---:|
| 5 min (09:40) | +0.0607 | 0.0290 | **48%** | +0.0317 |
| 10 min (09:45) | +0.0896 | 0.0290 | **32%** | +0.0606 |
| 15 min (09:50) | +0.1215 | 0.0290 | **24%** | +0.0925 |
| 1 hour (10:35) | +0.1397 | 0.0290 | **21%** | +0.1107 |

At 5 minutes the round trip consumes **48%** of the gross move; by 1 hour it is down to 21%. That gradient is the strongest argument in this report for the longer hold, and it is much starker in ATR units than the bps view makes it look, because the bps view hides how small the short-horizon moves are relative to each stock's own volatility.

## 4. What changes when you switch units

| Window | Payoff (ATR) | Payoff (bps) | Δ | Median/Mean (ATR) | Median/Mean (bps) |
|---|---:|---:|---:|---:|---:|
| 5 min (09:40) | 1.130 | 1.088 | +0.042 | 0.97 | 0.96 |
| 10 min (09:45) | 1.202 | 1.150 | +0.052 | 0.88 | 0.87 |
| 15 min (09:50) | 1.273 | 1.233 | +0.039 | 0.87 | 0.83 |
| 1 hour (10:35) | 1.207 | 1.209 | -0.002 | 0.90 | 0.79 |

**The payoff ratio is better in ATR units at 3 of 4 horizons** (+0.039 to +0.052), and unchanged at 1 hour (10:35). Losses shrink more than wins when each trade is divided by its own volatility, which says the large basis-point losses sit in high-ATR names where they are ordinary moves — not in quiet names where they would be genuine shocks. The bps view overstates how ugly the losses are, though only slightly.

The differences are small either way. Nothing in this table suggests the bps view was materially distorted — which is the answer the exercise was run to find, even though it is the less interesting one.

**Does the unit change which horizon looks best?**

| Rank by NET | ATR view | bps view |
|---|---|---|
| 1 | 1 hour (10:35) | 1 hour (10:35) |
| 2 | 15 min (09:50) | 15 min (09:50) |
| 3 | 10 min (09:45) | 10 min (09:45) |
| 4 | 5 min (09:40) | 5 min (09:40) |

**No — the ordering is identical.** The 1-hour hold is the best of the four under both measures, and the ranking of the rest is unchanged. That is the reassuring answer: the edge is not an artefact of letting volatile names dominate a basis-point average, which is exactly what this exercise was run to check.

| Window | NET (ATR) | 95% CI | p |
|---|---:|---:|---:|
| 5 min (09:40) | +0.0317 | [+0.0208, +0.0437] | 0.000 |
| 10 min (09:45) | +0.0606 | [+0.0469, +0.0755] | 0.000 |
| 15 min (09:50) | +0.0925 | [+0.0754, +0.1093] | 0.000 |
| 1 hour (10:35) | +0.1107 | [+0.0880, +0.1344] | 0.000 |

**Significant at 4 of 4 horizons in ATR units**, on a date-clustered bootstrap — the same count as the bps view. Rescaling does not create or destroy the result.

## 5. Symmetry of the ATR tails

| Window | % loss > 1 ATR | % gain > 1 ATR | Ratio | % loss > 0.5 ATR | % gain > 0.5 ATR |
|---|---:|---:|---:|---:|---:|
| 5 min (09:40) | 0.80% | 1.50% | 1.87 | 5.42% | 8.91% |
| 10 min (09:45) | 1.37% | 3.14% | 2.30 | 7.45% | 14.49% |
| 15 min (09:50) | 1.84% | 4.85% | 2.64 | 8.40% | 18.39% |
| 1 hour (10:35) | 4.63% | 9.25% | 2.00 | 15.16% | 26.20% |

At the 1-hour horizon 9.25% of trades gain more than a full ATR against 4.63% that lose more than one — a favourable ratio, and the clearest expression of the edge in risk-native units. Both tails are thin: the overwhelming majority of trades finish well inside a single ATR either way, which is what makes the 6.6 bps round trip a meaningful share of the outcome.

## 6. Reading notes

- **ATR is a daily measure applied to intraday holds.** A 5-minute move of 0.05 ATR is not 5% of a day's range in any strict sense — ATR includes overnight gaps and the full session. The unit is useful for cross-sectional comparability, not as a literal fraction of the day's expected travel.
- **The zero-return convention is inherited** from `DIST_REPORT.md`: exactly-zero returns are dropped as stale prints, which is why n varies slightly by horizon.
- **The per-trade cost conversion assumes the 6.6 bps is right in the first place.** It is a flat estimate that does not vary by name or by liquidity, so the ATR-denominated cost inherits that limitation and adds a volatility dimension to it.
- **Nothing here is a new test.** These are the published results in a different unit; no cohort, filter or convention has changed.

---

_Reproducible from `lambda_strategy_validation/atrunits.py`; tables in `lambda_data/tables/atru_*.csv`._