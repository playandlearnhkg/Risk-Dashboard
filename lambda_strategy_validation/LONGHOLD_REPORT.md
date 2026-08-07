# Lambda — Longer Holding Periods on the Strongest Setup

Post-earnings T+1, High Volume + Continuation, entry at the open of the 09:35 bar. The 1-hour row is the figure from the earlier reports, carried here unchanged for reference.

| Input | Definition |
|---|---|
| Universe | Post-earnings T+1, 2015-01-27 → 2025-12-22 |
| Setup | High Volume + Continuation |
| Continuation | 09:30–09:35 candle closes **with** the gap |
| High Volume | `c1_volume` > 1.5× trailing 20-session mean, same ticker, same 09:30–09:35 slot, shifted one session |
| Entry | Open of the 09:35 bar |
| Costs | 6.6 bps round trip, in NET only |
| Inference | date-clustered bootstrap; ⚠ marks n < 150 |

High Volume Continuation events: **4,938**. The **Until close** row exits at the session's official closing price, not an intraday bar.

## Results

| Holding period | n | Win rate | Avg Win | Avg Loss | Payoff | **NET** | Median | p10 | p90 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 hour (10:35) | 4,908 | 58.4% | 153.6 | 127.0 | 1.21 | **+30.1** | +29.1 | -173 | +254 |
| 2 hours (11:35) | 4,918 | 57.7% | 176.2 | 146.3 | 1.20 | **+33.0** | +29.7 | -206 | +294 |
| Until 12:00 | 4,918 | 57.1% | 182.0 | 151.1 | 1.20 | **+32.4** | +31.7 | -210 | +298 |
| Until close (16:00) | 4,918 | 56.6% | 214.0 | 185.9 | 1.15 | **+34.0** | +31.3 | -261 | +361 |

All figures in basis points. NET is mean expectancy per trade after 6.6 bps; net p-values: 1 hour (10:35) 0.000, 2 hours (11:35) 0.000, Until 12:00 0.000, Until close (16:00) 0.000.

## What each additional leg of holding time earns

The table above is cumulative, so a rising NET can hide a leg that contributes nothing. This decomposes it — gross return between consecutive exit points, no costs (you pay the round trip once, whichever exit you choose).

| Leg | n | Gross | 95% CI | p | Win rate | Median |
|---|---:|---:|---:|---:|---:|---:|
| Entry (09:35) → 1 hour (10:35) | 4,938 | +36.5 | [+30.4, +44.0] | 0.000 | 58.0% | +28.0 |
| 1 hour (10:35) → 2 hours (11:35) | 4,938 | +3.0 | [-0.5, +6.6] | 0.105 | 50.8% | +2.5 |
| 2 hours (11:35) → Until 12:00 | 4,938 | -0.4 | [-2.4, +1.5] | 0.678 | 49.7% | +0.0 |
| Until 12:00 → Until close (16:00) | 4,938 | +1.4 | [-3.1, +6.3] | 0.552 | 49.3% | -0.7 |

**All 3 legs after the first hour are indistinguishable from zero** (2 hours (11:35) +3.0 bps, p=0.10; Until 12:00 -0.4 bps, p=0.68; Until close (16:00) +1.4 bps, p=0.55). 

Nothing is earned after 10:35. The cumulative NET keeps drifting up because the point estimates are positive, but none of the incremental legs is statistically separable from zero, and each one adds hours of exposure and overnight-adjacent risk for it.

## Read

| Holding period | NET | vs 1 hour | Win rate | vs 1 hour |
|---|---:|---:|---:|---:|
| 1 hour (10:35) | +30.1 | +0.0 | 58.4% | +0.0 pp |
| 2 hours (11:35) | +33.0 | +2.9 | 57.7% | -0.7 pp |
| Until 12:00 | +32.4 | +2.3 | 57.1% | -1.3 pp |
| Until close (16:00) | +34.0 | +3.9 | 56.6% | -1.7 pp |

**Highest NET is Until close (16:00) at +34.0 bps.** But NET alone is the wrong way to choose a holding period, because it ignores how much risk is carried to get it. The dispersion widens far faster than the mean:

| Holding period | NET | Std dev | NET / Std | p10 | p90 | p90 − p10 |
|---|---:|---:|---:|---:|---:|---:|
| 1 hour (10:35) | +30.1 | 240 | 0.125 | -173 | +254 | 427 |
| 2 hours (11:35) | +33.0 | 261 | 0.127 | -206 | +294 | 500 |
| Until 12:00 | +32.4 | 254 | 0.128 | -210 | +298 | 508 |
| Until close (16:00) | +34.0 | 312 | 0.109 | -261 | +361 | 622 |

**On return per unit of risk, the first three holding periods are indistinguishable** — 1 hour (10:35) 0.125, 2 hours (11:35) 0.127, Until 12:00 0.128, Until close (16:00) 0.109. The nominal best is Until 12:00, ahead of 2 hours (11:35) by 0.001 — a difference far too small to act on at this sample size. What the column does show cleanly is that **Until close (16:00) is the worst of the four**: it carries the widest dispersion (312 bps std, p90 − p10 of 622 bps) for a NET only +3.9 bps above the 1-hour figure.

The p90 − p10 column is the plainest statement of the cost: the range of outcomes a trader actually lives through grows from 427 bps at 1 hour to 622 bps at the close, for essentially the same expectancy.

Three caveats specific to the long holds:

- **The flat cost model gets more wrong, not less.** 6.6 bps is a round trip; it does not change with holding time, so the long holds look cheap by construction. What it misses — the risk of needing to exit into a thinner book late in the session — grows with the horizon.
- **Capital efficiency is not in any of these numbers.** A 6.4-hour hold uses the slot for the whole session; four 1-hour holds could use it four times. On a per-unit-of-capital-per-hour basis the short holds win by a wide margin, and this table cannot show that.
- **The close is a different execution problem.** Marking out at 16:00 means trading the closing auction or accepting late-session spreads. Neither is priced here.

---

_Reproducible from `lambda_strategy_validation/longhold_path.py`; tables in `lambda_data/tables/lp_long.csv`, `lp_legs.csv`._