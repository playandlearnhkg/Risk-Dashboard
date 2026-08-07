# Lambda — Severity of Large Losses Under Seven Stop Rules

Post-earnings T+1, High Volume + Continuation (non-doji), entry at the open of the 09:35 bar, exit at 1 hour if no stop triggers. The question here is not expectancy — it is how bad the losses that get through actually are.

| Input | Definition |
|---|---|
| Universe | Post-earnings T+1, 2015-01-27 → 2025-12-19 |
| Cohort | 4,906 events — identical to the earlier stop reports |
| Rules 2, 3, 6, 7 | confirm on the **5-minute close**, exit at that close (12 checkpoints, 09:40–10:35) |
| Rules 4, 5 | fire on the first **intrabar touch**, fill at the stop or the bar's open if it opened through |
| ATR | prior-session ATR(14); no gap-day data |
| AVWAP | cumulative volume-weighted (H+L+C)/3 from the anchor, evaluated with minutes 0..t only |
| Costs | 6.6 bps round trip, in NET only |

> **On rule 7.** An anchored VWAP accumulates volume from its anchor, and no regular-session volume trades between the prior close and 09:30 — so read literally, "anchored at the prior close" and "anchored at 09:30" are the *same line*, and rule 7 would duplicate rule 6. To make it a distinct rule the anchor has to contribute the prior close as a price observation, which needs a weight, and no weight is canonical. I seeded it with the prior close carrying the first 5-minute candle's volume — same scale as the early session, not tuned. That drags the line toward the unfilled gap and makes the stop **wider** than rule 6. Section 5 varies the seed so you can see how much rides on the choice.

## 1. Context — what each rule does before we look at the tail

| Rule | % stopped | Win rate | NET | Median | p10 |
|---|---:|---:|---:|---:|---:|
| 1. No stop | — | 58.2% | +30.4 | +28.7 | -172 |
| 2. Gap Level | 7.0% | 57.4% | +30.1 | +27.1 | -169 |
| 3. Opening Range | 22.7% | 55.2% | +26.5 | +21.2 | -172 |
| 4. ATR −0.5 | 34.1% | 50.7% | +22.2 | +3.9 | -150 |
| 5. ATR −1.0 | 10.9% | 57.1% | +26.3 | +25.3 | -192 |
| 6. AVWAP from 09:30 | 77.1% | 44.2% | +18.0 | -9.8 | -116 |
| 7. AVWAP from prior close | 41.1% | 52.9% | +27.0 | +13.4 | -158 |

## 2. A — Losses larger than 1.0 ATR

| Rule | n | % of all trades | Avg loss (bps) | Avg loss (ATR) | Median loss (bps) | Median (ATR) | Worst loss (bps) | Worst (ATR) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1. No stop | 226 | 4.61% | -348 | -1.48 | -312 | -1.33 | -1,140 | -3.16 |
| 2. Gap Level | 220 | 4.48% | -340 | -1.46 | -302 | -1.31 | -1,140 | -3.16 |
| 3. Opening Range | 186 | 3.79% | -312 | -1.37 | -272 | -1.20 | -791 | -3.08 |
| 4. ATR −0.5 | **0** | 0.00% | — | — | — | — | — | — |
| 5. ATR −1.0 | 52 | 1.06% | -261 | -1.07 | -233 | -1.05 | -774 | -1.32 |
| 6. AVWAP from 09:30 | 54 | 1.10% | -308 | -1.35 | -301 | -1.25 | -763 | -2.80 |
| 7. AVWAP from prior close | 177 | 3.61% | -331 | -1.40 | -291 | -1.26 | -1,109 | -2.86 |

## 3. B — Losses larger than 0.5 ATR

| Rule | n | % of all trades | Avg loss (bps) | Avg loss (ATR) | Median loss (bps) | Median (ATR) |
|---|---:|---:|---:|---:|---:|---:|
| 1. No stop | 736 | 15.00% | -236 | -0.94 | -194 | -0.79 |
| 2. Gap Level | 724 | 14.76% | -231 | -0.92 | -192 | -0.78 |
| 3. Opening Range | 770 | 15.70% | -215 | -0.85 | -179 | -0.74 |
| 4. ATR −0.5 | 169 | 3.44% | -130 | -0.56 | -116 | -0.53 |
| 5. ATR −1.0 | 876 | 17.86% | -222 | -0.87 | -194 | -1.00 |
| 6. AVWAP from 09:30 | 405 | 8.26% | -179 | -0.75 | -149 | -0.67 |
| 7. AVWAP from prior close | 662 | 13.49% | -220 | -0.88 | -182 | -0.74 |

## 4. What the tail actually shows

Every rule and its tail, side by side:

| Rule | Confirmation | % beyond 1 ATR | Avg loss when beyond | Worst |
|---|---|---:|---:|---:|
| 1. No stop | — | 4.61% | -348 bps | -1,140 bps |
| 2. Gap Level | 5-min close | 4.48% | -340 bps | -1,140 bps |
| 3. Opening Range | 5-min close | 3.79% | -312 bps | -791 bps |
| 4. ATR −0.5 | intrabar | 0.00% | — | — |
| 5. ATR −1.0 | intrabar | 1.06% | -261 bps | -774 bps |
| 6. AVWAP from 09:30 | 5-min close | 1.10% | -308 bps | -763 bps |
| 7. AVWAP from prior close | 5-min close | 3.61% | -331 bps | -1,109 bps |

**Tail control is not free, and the rules differ enormously in what they charge for it.**

| Rule | Tail cut (pp beyond 1 ATR) | Expectancy paid (bps) | **pp of tail per bp paid** |
|---|---:|---:|---:|
| 5. ATR −1.0 | 3.55 | 4.0 | **0.88** |
| 4. ATR −0.5 | 4.61 | 8.2 | **0.56** |
| 2. Gap Level | 0.12 | 0.3 | **0.49** |
| 7. AVWAP from prior close | 1.00 | 3.4 | **0.30** |
| 6. AVWAP from 09:30 | 3.51 | 12.3 | **0.28** |
| 3. Opening Range | 0.82 | 3.9 | **0.21** |

**5. ATR −1.0 is the most efficient tail-control instrument tested** — 3.55 percentage points of >1 ATR losses removed for 4.0 bps of expectancy. It is not the rule that cuts the most tail, and it is not the cheapest rule; it is the best exchange rate between the two.

**And the mechanism matters more than the trigger type.** It would be natural to assume intrabar stops truncate the tail and close-confirmed ones cannot, since an intrabar stop exits *at* its level while a confirmed stop exits at whatever price the bar closes at. The data does not support that as a general rule:

| | ATR −1.0 (intrabar) | AVWAP 09:30 (5-min close) |
|---|---:|---:|
| % beyond 1 ATR | 1.06% | 1.10% |
| % stopped | 10.9% | 77.1% |
| NET | +26.3 | +18.0 |

The close-confirmed AVWAP reaches essentially the same tail (1.10% against 1.06%) — but it gets there by stopping **77% of all trades** rather than 11%, and it costs 12.3 bps rather than 4.0. Two routes to the same tail: cap the loss precisely, or exit almost everything early. The first is three times cheaper.

The intrabar advantage is still real where it applies — the −0.5 ATR stop is the only rule that removes the >1 ATR tail **entirely**, which no close-confirmed rule can promise, because a confirmed break has no ceiling on where it fills.

**The two VWAP anchors behave very differently**, which vindicates treating them as separate rules rather than variations:

| | AVWAP 09:30 | AVWAP prior close |
|---|---:|---:|
| % stopped | 77.1% | 41.1% |
| NET | +18.0 | +27.0 |
| % beyond 1 ATR | 1.10% | 3.61% |
| Avg loss beyond 1 ATR | -308 | -331 |
| Worst | -763 | -1,109 |

The **AVWAP from 09:30** anchor is the more active of the two, as expected: seeding the anchor with the prior close pulls the line toward the unfilled gap on a gap up, so price has further to fall before it closes below. The seeded version is closer to a wide structural stop; the 09:30 version is closer to a moving one that rises with the session.

**The cost of the tail, expressed as drag on the whole book.** Summing every loss beyond 1 ATR and dividing by all 4,906 trades:

| Rule | Drag from >1 ATR losses (bps per trade) | vs no stop |
|---|---:|---:|
| 1. No stop | -16.0 | — |
| 2. Gap Level | -15.3 | +0.8 |
| 3. Opening Range | -11.8 | +4.2 |
| 4. ATR −0.5 | +0.0 | +16.0 |
| 5. ATR −1.0 | -2.8 | +13.3 |
| 6. AVWAP from 09:30 | -3.4 | +12.6 |
| 7. AVWAP from prior close | -11.9 | +4.1 |

This is the number a stop is supposed to improve, and it is the only column in this report where the stops clearly earn their keep. Read it against the NET column in section 1 to see what each one charged for the improvement.

## 5. How much of rule 7 rides on the seed weight?

| Seed weight | % stopped | NET | % beyond 1 ATR | % beyond 0.5 ATR | Avg loss beyond 1 ATR |
|---|---:|---:|---:|---:|---:|
| 0.5× c1 volume | 52.9% | +25.1 | 2.73% | 12.70% | -315 bps |
| 1.0× c1 volume | 41.1% | +27.0 | 3.61% | 13.49% | -331 bps |
| 2.0× c1 volume | 28.4% | +28.4 | 4.08% | 13.94% | -341 bps |

Across a 4× range of seed weights, NET moves 3.3 bps and the >1 ATR rate moves 1.35 percentage points. The seed choice does move the result, so rule 7's figures should be read as one point on this curve rather than as a property of the rule.

## 6. Reading notes

- **Losses are measured after the exit rule, gross of the 6.6 bps.** Costs are charged identically to stopped and held trades, which flatters every stop.
- **The worst-loss column is one observation.** It is reported because the question asked for it, not because a single realised extreme is a stable statistic.
- **Rule 7's seed weight is a judgement call**, disclosed above and stress-tested in section 5. Rule 6 has no such freedom.
- **Comparing stop-out rates across the two families is not meaningful** — intrabar and close-confirmed triggers are different mechanisms. Comparing loss severity across them, which is what this report does, is exactly the right use of the pair.

---

_Reproducible from `lambda_strategy_validation/lossanalysis.py`; tables in `lambda_data/tables/loss_*.csv`._