# Lambda — Tighter ATR Stops on the Post-Earnings Continuation Setup

Post-earnings T+1, High Volume + Continuation (non-doji), entry at the open of the 09:35 bar, exit at 1 hour (10:35) if the stop is not hit. Extends `STOPS_REPORT.md` to tighter levels.

| Input | Definition |
|---|---|
| Universe | Post-earnings T+1, 2015-01-27 → 2025-12-19 |
| Cohort | 4,906 events — identical to `STOPS_REPORT.md`, built by the same code |
| Stop distance | **prior-session ATR(14)**, a window ending the day before the gap |
| Trigger | intrabar: the bar's **low** for a long, **high** for a short |
| Fill | the stop price, or the bar's **open** if the bar opened through it |
| Costs | 6.6 bps round trip, charged identically to stopped and held trades |

## 1. Results

| Rule | n | % stopped | Win rate | Avg Win | Avg Loss | Payoff | **NET** | Median | p10 | % realised loss > 1 ATR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Stop −0.5 ATR | 4,906 | 34.1% | 50.7% | 160.4 | 107.5 | 1.49 | **+22.2** | +3.9 | -150 | 0.00% |
| Stop −0.7 ATR | 4,906 | 21.6% | 55.0% | 155.8 | 123.1 | 1.27 | **+24.3** | +19.8 | -176 | 0.06% |
| Stop −0.8 ATR | 4,906 | 17.1% | 56.0% | 155.3 | 126.4 | 1.23 | **+25.4** | +23.0 | -182 | 0.10% |
| Stop −1.0 ATR | 4,906 | 10.9% | 57.1% | 154.4 | 130.4 | 1.18 | **+26.3** | +25.3 | -192 | 1.06% |
| No stop (hold to 1 hour) | 4,906 | — | 58.2% | 153.6 | 126.9 | 1.21 | **+30.4** | +28.7 | -172 | 4.61% |

All figures in basis points. NET is mean expectancy per trade after 6.6 bps.

## 2. The full ladder

Including the looser stops from the previous report, so the shape is visible end to end.

| Stop | % stopped | Win rate | Payoff | **NET** | vs no stop | Median | p10 | % loss > 1 ATR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Stop −0.5 ATR | 34.1% | 50.7% | 1.49 | **+22.2** | -8.2 | +3.9 | -150 | 0.00% |
| Stop −0.7 ATR | 21.6% | 55.0% | 1.27 | **+24.3** | -6.1 | +19.8 | -176 | 0.06% |
| Stop −0.8 ATR | 17.1% | 56.0% | 1.23 | **+25.4** | -4.9 | +23.0 | -182 | 0.10% |
| Stop −1.0 ATR | 10.9% | 57.1% | 1.18 | **+26.3** | -4.0 | +25.3 | -192 | 1.06% |
| Stop −1.5 ATR | 3.6% | 58.1% | 1.20 | **+29.6** | -0.8 | +28.2 | -182 | 5.46% |
| Stop −2.0 ATR | 1.2% | 58.1% | 1.20 | **+30.0** | -0.4 | +28.7 | -173 | 4.75% |
| **No stop (hold to 1 hour)** | — | 58.2% | 1.21 | **+30.4** | — | +28.7 | -172 | 4.61% |

**NET rises monotonically with the stop distance across all 6 levels**, from +22.2 bps at Stop −0.5 ATR to +30.0 at Stop −2.0 ATR, and no level reaches the +30.4 bps of not stopping at all. There is no interior optimum — the ladder has no peak to find, it just climbs toward the no-stop case.

## 3. What each level costs

| Stop | % stopped | NET | Cost vs no stop | Cost per 1% of trades stopped |
|---|---:|---:|---:|---:|
| Stop −0.5 ATR | 34.1% | +22.2 | **−8.2** | −0.24 bps |
| Stop −0.7 ATR | 21.6% | +24.3 | **−6.1** | −0.28 bps |
| Stop −0.8 ATR | 17.1% | +25.4 | **−4.9** | −0.29 bps |
| Stop −1.0 ATR | 10.9% | +26.3 | **−4.0** | −0.37 bps |
| Stop −1.5 ATR | 3.6% | +29.6 | **−0.8** | −0.23 bps |
| Stop −2.0 ATR | 1.2% | +30.0 | **−0.4** | −0.30 bps |

The tightest stop tested stops out **34.1%** of all trades and costs **8.2 bps** — roughly 27% of the entire edge. The cost-per-stop-out column is close to flat across the ladder, which is the signature of a stop that is firing on noise: each trade it catches costs about the same, regardless of how far out the level sits, because the trades being caught are not systematically different from the ones that are not.

## 4. Where the expectancy goes

For each stop, the trades it caught: what they realised, and what those same trades would have returned if left to run to 1 hour.

| Stop | Trades stopped | Realised | Would have made | **Forgone** | % that would have recovered to profit |
|---|---:|---:|---:|---:|---:|
| −0.5 ATR | 1,674 | -132.4 | -108.4 | **+24.0** | 21.9% |
| −0.7 ATR | 1,062 | -179.7 | -151.7 | **+28.0** | 14.6% |
| −0.8 ATR | 837 | -200.5 | -171.5 | **+29.0** | 12.7% |
| −1.0 ATR | 535 | -246.9 | -209.8 | **+37.1** | 9.7% |

At −0.5 ATR, **22% of the trades the stop cut would have finished the hour in profit**, and the group as a whole would have returned -108.4 bps instead of the -132.4 actually realised. That gap is the entire mechanism: this cohort's adverse excursions are mostly temporary, so a stop inside the noise band converts round-trips into permanent losses.

This is the same finding as the path-dependence test from a different angle. There, trades losing at the 5-minute mark went on to make **+30.1 bps** from 09:41 to 10:35 — the largest subsequent move of any group. A tight stop is the mechanism that guarantees you are not holding those trades when the recovery happens.

## 5. What the tight stops do buy

| Stop | p10 | Std dev | % realised loss > 1 ATR | Win rate | NET |
|---|---:|---:|---:|---:|---:|
| Stop −0.5 ATR | -150 | 226 | 0.00% | 50.7% | +22.2 |
| Stop −0.7 ATR | -176 | 233 | 0.06% | 55.0% | +24.3 |
| Stop −0.8 ATR | -182 | 236 | 0.10% | 56.0% | +25.4 |
| Stop −1.0 ATR | -192 | 239 | 1.06% | 57.1% | +26.3 |
| Stop −1.5 ATR | -182 | 240 | 5.46% | 58.1% | +29.6 |
| Stop −2.0 ATR | -173 | 240 | 4.75% | 58.1% | +30.0 |
| **No stop (hold to 1 hour)** | -172 | 240 | 4.61% | 58.2% | +30.4 |

**The genuine benefit is tail truncation.** 4 of the 6 levels cut the share of realised losses beyond 1 ATR below the 4.61% of holding, and the tightest gets it to 0.00%. If the binding constraint is a hard per-trade loss limit rather than expectancy, that is what a tight stop is for, and it works.

**And unlike the 1.0 ATR stop, the tightest level does improve the 10th percentile** — Stop −0.5 ATR at -150, against -172 for holding. The ordering is not monotone and that is the interesting part: p10 gets *worse* as the stop loosens from 0.5 to 1.0 ATR, then recovers. A stop at 1.0 ATR sits right where the mass of adverse excursions turns around, so it clusters losses exactly on the 10th percentile; a stop at 0.5 fires early enough that the cluster lands above it.

So this is a genuine trade-off rather than a flat verdict: **the tightest stop improves the shape of the left tail and costs real expectancy.** It is a risk-budget instrument here, not a performance one.

One number qualifies even that. The **median** trade falls from +28.7 bps to +3.9 at −0.5 ATR — the typical trade goes from clearly profitable to barely above breakeven, and below the 6.6 bps cost. Win rate drops to 50.7%, essentially a coin flip, while the payoff ratio rises to 1.49. The tight stop converts a high-win-rate, modest-payoff strategy into a coin-flip, high-payoff one. That is a different business with different psychology, and worse expectancy.

## 6. Reading notes

- **Costs are charged identically to stopped and held trades.** A stop firing in fast tape pays more than 6.6 bps in reality, and the tighter the stop the more often that happens, so every rule here is flattered relative to holding — the tight ones most of all.
- **The fill model already allows gap-throughs** (fill at the bar open when it opens through the level), which is why the realised >1 ATR column is not exactly zero for stops tighter than 1 ATR.
- **No level was searched for.** These are round numbers chosen in advance. The ladder is monotone, so there is no hidden optimum between them to go hunting for.
- **This says nothing about stops on other setups.** The result follows from this cohort's adverse excursions being mostly temporary; a breakout strategy, where an adverse move falsifies the premise, would behave differently.

---

_Reproducible from `lambda_strategy_validation/stops_tight.py`; tables in `lambda_data/tables/stopstight_*.csv`._