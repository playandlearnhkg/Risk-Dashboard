# Lambda — Statistical Stop-Loss Rules on the Strongest Setup

Post-earnings T+1, High Volume + Continuation (non-doji), entry at the open of the 09:35 bar, exit at 1 hour (10:35) if the stop is not hit.

| Input | Definition |
|---|---|
| Universe | Post-earnings T+1, 2015-01-27 → 2025-12-19 |
| Cohort | 4,906 events |
| Stop distance | **prior-session ATR(14)** — a 14-session window ending the day *before* the gap. No gap-day data enters it. |
| Trigger | intrabar: the bar's **low** for a long, **high** for a short |
| Fill | the stop price, or the bar's **open** if the bar opened already through it |
| Costs | 6.6 bps round trip, charged identically to stopped and held trades |
| Inference | date-clustered bootstrap |

> **Two things this test does that a naive stop study does not.** Stops are checked against intrabar highs and lows, not closes — testing on closes alone would understate stop-outs badly. And a bar that opens through the stop fills at the open, not the stop price, so realised losses are allowed to exceed the stop distance. Section 4 measures how often that happened.

## 1. Core performance

| Rule | n | % stopped | Win rate | Avg Win | Avg Loss | Payoff | **NET** | net p |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A1. Stop −1.0 ATR from entry | 4,906 | 10.9% | 57.1% | 154.4 | 130.4 | 1.18 | **+26.3** | 0.000 |
| A2. Stop −1.5 ATR from entry | 4,906 | 3.6% | 58.1% | 153.8 | 128.4 | 1.20 | **+29.6** | 0.000 |
| A3. Stop −2.0 ATR from entry | 4,906 | 1.2% | 58.1% | 153.7 | 127.7 | 1.20 | **+30.0** | 0.000 |
| B1. No stop 15 min, then −1.0 ATR from 15-min price | 4,906 | 6.6% | 58.1% | 152.5 | 128.2 | 1.19 | **+29.0** | 0.000 |
| B2. No stop 15 min, then −1.5 ATR from 15-min price | 4,906 | 1.8% | 58.1% | 153.4 | 127.7 | 1.20 | **+29.9** | 0.000 |
| C. No stop (hold to 1 hour) | 4,906 | — | 58.2% | 153.6 | 126.9 | 1.21 | **+30.4** | 0.000 |

All figures in basis points. NET is mean expectancy per trade after 6.6 bps.

## 2. Distribution after the stop

| Rule | Median | p10 | p25 | p75 | p90 | Skew | **% realised loss > 1.0 ATR** |
|---|---:|---:|---:|---:|---:|---:|---:|
| A1. Stop −1.0 ATR from entry | +25.3 | -192 | -78 | +128 | +254 | +15.11 | **1.06%** |
| A2. Stop −1.5 ATR from entry | +28.2 | -182 | -67 | +130 | +254 | +14.88 | **5.46%** |
| A3. Stop −2.0 ATR from entry | +28.7 | -173 | -66 | +130 | +254 | +14.70 | **4.75%** |
| B1. No stop 15 min, then −1.0 ATR from 15-min price | +28.0 | -176 | -67 | +129 | +253 | +14.76 | **4.83%** |
| B2. No stop 15 min, then −1.5 ATR from 15-min price | +28.5 | -172 | -66 | +130 | +254 | +14.71 | **4.69%** |
| C. No stop (hold to 1 hour) | +28.7 | -172 | -66 | +130 | +254 | +14.75 | **4.61%** |

> **The skew column is one observation.** As documented in `DIST_REPORT.md`, the CAR 2021-11-02 squeeze (+10,023 bps in an hour) sits in this cohort and drives the 1-hour skew on its own. It is a winner, so no stop touches it and the figure is near-identical across all six rules — which is precisely why it carries no information about the stops. Read the quantile columns instead.

## 3. Does any stop beat holding?

| Rule | NET | vs no stop | Median | vs no stop | p10 | vs no stop |
|---|---:|---:|---:|---:|---:|---:|
| A1. Stop −1.0 ATR from entry | +26.3 | **-4.0** | +25.3 | -3.4 | -192 | -20 |
| A2. Stop −1.5 ATR from entry | +29.6 | **-0.8** | +28.2 | -0.5 | -182 | -10 |
| A3. Stop −2.0 ATR from entry | +30.0 | **-0.4** | +28.7 | -0.0 | -173 | -1 |
| B1. No stop 15 min, then −1.0 ATR from 15-min price | +29.0 | **-1.4** | +28.0 | -0.6 | -176 | -4 |
| B2. No stop 15 min, then −1.5 ATR from 15-min price | +29.9 | **-0.5** | +28.5 | -0.2 | -172 | -0 |
| **C. No stop (hold to 1 hour)** | **+30.4** | — | +28.7 | — | -172 | — |

**No stop rule improves expectancy.** All 5 cost money against simply holding — even the best of them (A3) gives up 0.4 bps. The ordering is monotone in the obvious direction: the tighter the stop, the more it costs.

That is the expected result for a setup whose edge is a **drift** rather than a breakout. A stop converts a temporary adverse excursion into a realised loss, and this cohort's adverse excursions are mostly temporary — the path-dependence test already showed that 5-minute losers go on to make **+30.1 bps** from 09:41 to 10:35, the *largest* subsequent move of any group. A stop is precisely the mechanism that prevents collecting that.

**What the stops do buy.**

| Rule | p10 | Std dev | % realised loss > 1.0 ATR | NET |
|---|---:|---:|---:|---:|
| A1. Stop −1.0 ATR from entry | -192 | 239 | 1.06% | +26.3 |
| A2. Stop −1.5 ATR from entry | -182 | 240 | 5.46% | +29.6 |
| A3. Stop −2.0 ATR from entry | -173 | 240 | 4.75% | +30.0 |
| B1. No stop 15 min, then −1.0 ATR from 15-min price | -176 | 240 | 4.83% | +29.0 |
| B2. No stop 15 min, then −1.5 ATR from 15-min price | -172 | 240 | 4.69% | +29.9 |
| C. No stop (hold to 1 hour) | -172 | 240 | 4.61% | +30.4 |

**Less than you would expect — and on one measure, nothing at all.**

The 1.0 ATR stop does cut the far tail: the share of trades realising a loss worse than 1 ATR falls from 4.61% to 1.06%, a 4× reduction. That is real risk control.

But it makes the **10th percentile worse**, not better — -192 bps against -172 without any stop. That is not a rounding artefact, it is the mechanism: the stop takes the 10.9% of trades it catches and parks them all at roughly −1 ATR, whereas most of those would otherwise have recovered some of the way back. It converts a spread-out set of moderate outcomes into a dense cluster of losses at one level, and that cluster lands right on the 10th percentile.

Dispersion barely moves either — standard deviation 239 against 240, a 1 bps difference for 4.0 bps of expectancy. The stop is not buying a materially smoother equity curve; it is buying protection against the extreme left tail only, and paying for it out of the middle of the distribution.

**The looser stops make even that metric worse.** 4 of the 5 rules end with a *higher* share of realised losses beyond 1 ATR than holding with no stop at all (A2 5.46%, A3 4.75%, B1 4.83%, B2 4.69% against 4.61%). A stop at 1.5 or 2.0 ATR sits beyond where most adverse excursions turn around, so it rarely saves anything — but when it does fire it locks in a loss of at least its own distance, which by definition exceeds 1 ATR. It manufactures the very outcome it was meant to prevent.

On return per unit of risk:

| Rule | NET | Std dev | NET / Std |
|---|---:|---:|---:|
| A1. Stop −1.0 ATR from entry | +26.3 | 239 | 0.110 |
| A2. Stop −1.5 ATR from entry | +29.6 | 240 | 0.123 |
| A3. Stop −2.0 ATR from entry | +30.0 | 240 | 0.125 |
| B1. No stop 15 min, then −1.0 ATR from 15-min price | +29.0 | 240 | 0.121 |
| B2. No stop 15 min, then −1.5 ATR from 15-min price | +29.9 | 240 | 0.124 |
| C. No stop (hold to 1 hour) | +30.4 | 240 | 0.127 |

**Best risk-adjusted: C. No stop (hold to 1 hour)** (0.127). Holding wins on this measure too, so the stops are not even buying an efficiency improvement — they reduce return faster than they reduce risk.

## 4. Did the stops actually hold their price?

A stop only fills at its level if the bar does not open through it. Where it did, the fill is the open and the realised loss exceeds the intended stop distance.

| Rule | Trades stopped | Gapped through | % of stops | Mean overshoot | Worst overshoot |
|---|---:|---:|---:|---:|---:|
| A1. Stop −1.0 ATR from entry | 535 | 52 | 9.7% | 0.071 ATR | 0.32 ATR |
| A2. Stop −1.5 ATR from entry | 176 | 10 | 5.7% | 0.084 ATR | 0.46 ATR |
| A3. Stop −2.0 ATR from entry | 59 | 10 | 16.9% | 0.088 ATR | 0.23 ATR |
| B1. No stop 15 min, then −1.0 ATR from 15-min price | 326 | 36 | 11.0% | 0.063 ATR | 0.30 ATR |
| B2. No stop 15 min, then −1.5 ATR from 15-min price | 86 | 12 | 14.0% | 0.064 ATR | 0.26 ATR |

Up to 17% of stops (A3) filled worse than their level. That is why the *% realised loss > 1.0 ATR* column in section 2 is not zero even for the 1.0 ATR stop — a stop is an instruction, not a guarantee, and in post-earnings tape the difference is measurable. Note this is still the optimistic case: no spread or slippage is added beyond the gap-through itself.

## 5. Why the stop-out rates come out where they do

Maximum excursion from entry, in ATR units, over the hour:

| Metric | p10 | p25 | p50 | p75 | p90 | beyond 1.0 | beyond 1.5 | beyond 2.0 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Max adverse excursion (ATR) | -1.04 | -0.64 | -0.33 | -0.13 | -0.03 | 10.9% | 3.6% | 1.2% |
| Max favourable excursion (ATR) | +0.09 | +0.25 | +0.52 | +0.86 | +1.33 | 19.2% | 7.4% | 3.0% |

The median trade dips 0.33 ATR against itself at some point in the hour, and 10.9% touch a full ATR against. A 1.0 ATR stop is therefore not a tail-risk stop on this setup — it sits inside the ordinary breathing range of the trade, which is exactly why it costs so much expectancy.

## 6. Reading notes

- **The baseline differs trivially from the published +30.1 bps** in `LONGHOLD_REPORT.md` (here +30.4). Earlier reports dropped exactly-zero returns as stale prints; a stop study must account for every trade it takes, so nothing is dropped here.
- **Costs are charged identically to stopped and held trades.** A stopped trade exits into fast tape and in reality pays more than 6.6 bps. Every stop rule above is therefore flattered relative to holding.
- **No intrabar path within the minute.** If a bar's low breaches the stop and its high also reaches a target, this test assumes the stop fired. That is the conservative ordering, and correct for a stop-only study.
- **The stop distance is honest, the stop *choice* is not tested out of sample.** 1.0/1.5/2.0 ATR are conventional round numbers, not fitted, which is the right way to run this — but it does mean no search was done for a level that works, and none of these three does.

---

_Reproducible from `lambda_strategy_validation/stops.py`; tables in `lambda_data/tables/stops_*.csv`._