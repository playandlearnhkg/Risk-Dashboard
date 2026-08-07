# Lambda — Limit-Order Entries on the Post-Earnings Continuation Setup

Post-earnings T+1, High Volume + Continuation (non-doji). Signal completes at 09:35; the limit order is placed there and the trade exits at 10:35. No stop is applied, so the baseline row is the familiar no-stop figure.

| Input | Definition |
|---|---|
| Universe | Post-earnings T+1, 2015-01-27 → 2025-12-19 |
| Signals | 4,906 |
| Group A | retracement from the candle's **extreme in the trade's direction**, by a fraction of the candle range — so 50% lands on the candle midpoint |
| Group B | the candle's close, the open/close midpoint, and the open |
| **Fill window** | order live from 09:35, **cancelled if unfilled at 09:50**; the 10:00 window is in section 3 |
| Fill trigger | a minute's low at/below a buy limit, or high at/above a sell limit |
| Fill price | the limit, or the bar's **open** if the bar opened through it (a better price) |
| Exit | 10:35, no stop |
| Costs | 6.6 bps round trip |

> **Read the fill rate before the expectancy.** A limit order only fills if price comes back to it, so every row below is a *self-selected* sample — and on a continuation setup the trades that never come back are the ones that ran. Expectancy per filled trade is therefore not the number that decides anything. Section 4 gives the two that do.

## 1. Results — 09:50 fill window

| Rule | n filled | Fill rate | Win rate | Avg Win | Avg Loss | Payoff | **NET** | Median | p10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A1. 25% of range | 4,101 | 83.6% | 58.1% | 149.8 | 122.2 | 1.23 | **+29.3** | +28.0 | -163 |
| A2. 50% of range (midpoint) | 2,867 | 58.4% | 58.8% | 142.4 | 117.3 | 1.21 | **+29.9** | +30.5 | -160 |
| A3. 75% of range | 1,609 | 32.8% | 58.5% | 137.2 | 114.5 | 1.20 | **+24.7** | +25.1 | -156 |
| B4. Candle close | 4,685 | 95.5% | 58.2% | 151.5 | 125.7 | 1.21 | **+29.9** | +28.1 | -169 |
| B5. Midpoint of open & close | 2,708 | 55.2% | 58.6% | 140.9 | 116.9 | 1.21 | **+27.1** | +28.0 | -161 |
| B6. Candle open | 1,526 | 31.1% | 59.3% | 135.8 | 120.6 | 1.13 | **+13.7** | +27.9 | -165 |
| 7. Market at 09:35 open | 4,906 | 100.0% | 58.2% | 153.6 | 126.9 | 1.21 | **+30.4** | +28.7 | -172 |

All figures in basis points, on filled trades only, as requested. NET is after 6.6 bps.

## 2. Against the market order

| Rule | Fill rate | NET | vs baseline | Median | vs baseline |
|---|---:|---:|---:|---:|---:|
| A1. 25% of range | 83.6% | +29.3 | **-1.1** | +28.0 | -0.7 |
| A2. 50% of range (midpoint) | 58.4% | +29.9 | **-0.5** | +30.5 | +1.8 |
| A3. 75% of range | 32.8% | +24.7 | **-5.7** | +25.1 | -3.6 |
| B4. Candle close | 95.5% | +29.9 | **-0.5** | +28.1 | -0.6 |
| B5. Midpoint of open & close | 55.2% | +27.1 | **-3.3** | +28.0 | -0.7 |
| B6. Candle open | 31.1% | +13.7 | **-16.7** | +27.9 | -0.8 |
| **7. Market at 09:35 open** | 100.0% | **+30.4** | — | +28.7 | — |

**No limit rule beats the market order even on filled trades**, which settles the question without needing the selection analysis: a better entry price did not compensate for the trades the patience cost.

There is a clean monotone pattern worth naming: the deeper the pullback demanded, the lower the fill rate and the better the entry price on the fills that do happen. The rules are ordered by how much they ask for.

**Two of the rules are barely limit orders at all.** A1. 25% of range (fill rate 83.6%, median entry improvement +0.0 bps), B4. Candle close (fill rate 95.5%, median entry improvement +0.0 bps). On a continuation candle the 09:35 open has usually already retraced past those levels, so the order fills immediately at the open — which is the market order. Their near-baseline results are not evidence that patience works; they are evidence that these two rules mostly do not ask for any.

## 3. Sensitivity to the fill window (09:50 vs 10:00)

| Rule | Fill rate @ 09:50 | Fill rate @ 10:00 | NET @ 09:50 | NET @ 10:00 |
|---|---:|---:|---:|---:|
| A1. 25% of range | 83.6% | 85.6% | +29.3 | +28.7 |
| A2. 50% of range (midpoint) | 58.4% | 62.5% | +29.9 | +24.8 |
| A3. 75% of range | 32.8% | 38.3% | +24.7 | +22.9 |
| B4. Candle close | 95.5% | 96.0% | +29.9 | +28.8 |
| B5. Midpoint of open & close | 55.2% | 59.5% | +27.1 | +26.3 |
| B6. Candle open | 31.1% | 36.0% | +13.7 | +23.5 |
| 7. Market at 09:35 open | 100.0% | 100.0% | +30.4 | +30.4 |

Extending the window to 10:00 raises fill rates but moves expectancy by -5.0 to +9.8 bps. The extra fills are trades that took longer to come back, and a continuation trade that is still retracing 25 minutes in is a different animal from one that dipped and turned.

## 4. The selection problem, quantified

Two questions decide whether a limit entry is actually better, and neither is answerable from the filled-trade table alone.

**(a) What does a signal earn, counting the ones you never got into?** An unfilled signal earns nothing, so the deployment number is expectancy per fill × fill rate.

| Rule | NET per filled trade | Fill rate | **NET per signal** | vs baseline |
|---|---:|---:|---:|---:|
| A1. 25% of range | +29.3 | 83.6% | **+24.5** | -5.9 |
| A2. 50% of range (midpoint) | +29.9 | 58.4% | **+17.4** | -12.9 |
| A3. 75% of range | +24.7 | 32.8% | **+8.1** | -22.3 |
| B4. Candle close | +29.9 | 95.5% | **+28.6** | -1.8 |
| B5. Midpoint of open & close | +27.1 | 55.2% | **+15.0** | -15.4 |
| B6. Candle open | +13.7 | 31.1% | **+4.3** | -26.1 |
| 7. Market at 09:35 open | +30.4 | 100.0% | **+30.4** | — |

**Every limit rule loses on this measure**, by 1.8 to 26.1 bps per signal. Waiting for a better price means not being in the trades that never offer one, and on a continuation setup that is a systematically expensive group to miss.

> This comparison assumes one unit of capital per *signal*. If capital is instead the binding constraint and unfilled signals free it up for something else, the per-filled-trade column is the relevant one — but then the alternative use has to earn its own keep, and nothing here measures that.

**(b) What did the missed trades do?** Every unfilled signal, priced at the baseline market entry:

| Rule | Filled | Missed | Missed trades' baseline NET | Filled trades' baseline NET | Median entry improvement |
|---|---:|---:|---:|---:|---:|
| A1. 25% of range | 4,101 | 805 | **+111.1** | +14.5 | +0.0 |
| A2. 50% of range (midpoint) | 2,867 | 2,039 | **+92.7** | -13.9 | +27.7 |
| A3. 75% of range | 1,609 | 3,297 | **+69.9** | -50.5 | +57.6 |
| B4. Candle close | 4,685 | 221 | **+130.5** | +25.7 | +0.0 |
| B5. Midpoint of open & close | 2,708 | 2,198 | **+94.9** | -22.0 | +35.9 |
| B6. Candle open | 1,526 | 3,380 | **+65.4** | -47.1 | +51.7 |

**The missed trades were the better trades, under every rule** — by 96.5 to 120.4 bps on the same baseline entry. This is the mechanism in one line: price comes back to your limit precisely when the move is not working, and runs away from it when the move is. The limit order systematically selects the weaker half of the signal.

The last column shows what the patience buys when it does work — a median entry improvement of 0 to 58 bps. That is a real saving, and it is not large enough to pay for the selection.

## 5. Reading notes

- **Fills are assumed at the limit price with no queue risk.** In reality a limit resting at a round retracement level fills last, and often only because the market is about to trade through it. Every limit row is therefore optimistic; the baseline market order is not.
- **Costs are the same flat 6.6 bps for every rule.** A limit entry genuinely should pay less than a market order — it earns the spread rather than crossing it — so this understates limit entries by roughly half the spread on one side. That is worth perhaps 1–2 bps here, which does not close the gaps in section 4.
- **Only the entry varies.** Signal, cohort, exit and holding period are identical across all seven rows, so the comparison is clean on everything except the selection effect it is designed to expose.
- **No stop is applied**, matching the baseline used in the stop reports. A limit entry combined with a stop would interact, and nothing here tests that.

---

_Reproducible from `lambda_strategy_validation/entrylimits.py`; tables in `lambda_data/tables/entlim_*.csv`._