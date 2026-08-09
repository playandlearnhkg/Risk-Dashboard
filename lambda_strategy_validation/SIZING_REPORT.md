# Lambda — Conviction and Risk-Based Position Sizing

Post-earnings T+1, High Volume + Continuation (non-doji), entry at the 09:35 open, 1-hour hold, **full universe screen applied** (4,270 of 4,906 events). Risk factors are entry-time only: gap/ATR and the opening 5-minute volume ratio.

| Tier | Definition | Share of trades |
|---|---|---:|
| High Risk | gap/ATR > 1.5 **or** volume ratio > 5× | 45.0% |
| Low Risk | gap/ATR < 0.8 **and** volume ratio < 3× | 32.4% |
| Medium | everything else | 22.6% |

> **How the schemes are made comparable.** Each is a vector of notional weights, and every figure is reported **per unit of average notional deployed**. Without that, a scheme that simply deploys less capital would look safer and less profitable for no reason but leverage. Mean and max raw weight are shown so the de-leveraging stays visible.
>
> **Scheme D expressed as a weight.** Risking a fixed dollar amount per ATR implies `shares = R / ATR_$`, so `notional = R / ATR%`. Its weight is therefore proportional to the inverse of ATR as a share of price — which is what makes it comparable to A, B and C rather than only expressible in risk units.
>
> **Win rate is identical across all schemes**, because a positive weight cannot change a trade's sign. So is *% of trades losing more than 1 ATR*, which is a property of the trade, not the position. What sizing changes is those trades' **contribution**, which is what the average-large-loss and standard-deviation columns capture.

## 1. The schemes

| Scheme | Mean weight | Max weight | Win rate | **NET (bps)** | NET (ATR) | Avg Win | Avg Loss | Payoff | Avg large loss | Std dev | **NET / Std** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C — Equal size (baseline) | 1.00 | 1.0 | 58.3% | **+29.1** | +0.1104 | 148 | 123 | 1.20 | -341 | 188 | **0.1549** |
| A — Two tier (0.5× high risk) | 0.77 | 1.0 | 58.3% | **+27.0** | +0.1034 | 139 | 115 | 1.20 | -270 | 175 | **0.1543** |
| B — Three tier (1.25 / 1.0 / 0.5) | 0.86 | 1.2 | 58.3% | **+26.7** | +0.1022 | 137 | 113 | 1.21 | -258 | 174 | **0.1539** |
| B2 — Three tier (1.5 / 1.0 / 0.5) | 0.94 | 1.5 | 58.3% | **+26.5** | +0.1012 | 135 | 111 | 1.22 | -248 | 175 | **0.1520** |
| D — Fixed dollar risk (∝ 1/ATR%) | 1.00 | 4.7 | 58.3% | **+24.9** | +0.1095 | 130 | 108 | 1.20 | -330 | 160 | **0.1559** |

All returns are basis points per unit of average notional. NET is after 6.6 bps.

| | Best scheme | Value |
|---|---|---:|
| Highest expectancy | C — Equal size (baseline) | +29.1 bps |
| Best risk-adjusted | D — Fixed dollar risk (∝ 1/ATR%) | 0.1559 |

**D — Fixed dollar risk (∝ 1/ATR%) is the best risk-adjusted variant** (0.1559 against 0.1549 for equal sizing) — but the margin is +0.7%, and the entire spread across all five schemes is 0.0039, or 2.5% of the baseline. **No scheme meaningfully separates from equal sizing.**

Note the direction of the trade-off: every risk-tiered scheme lowers NET **and** lowers standard deviation, in nearly the same proportion. Section 3 explains why that had to happen.

## 2. What the tiers actually do, under equal size

| Group | n | Share of trades | Win rate | **NET (bps)** | NET (ATR) | Payoff | Std dev | % loss > 1 ATR | Avg large loss | **Share of total P&L** | **Share of large losses** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| High Risk | 1,922 | 45.0% | 58.3% | **+36.6** | +0.1345 | 1.20 | 225 | 7.49% | -346 | **56.5%** | **75.8%** |
| Medium | 963 | 22.6% | 57.1% | **+20.9** | +0.0913 | 1.18 | 163 | 1.87% | -332 | **16.1%** | **9.5%** |
| Low Risk | 1,385 | 32.4% | 59.3% | **+24.5** | +0.0903 | 1.24 | 143 | 2.02% | -317 | **27.3%** | **14.7%** |
| Low + Medium | 2,348 | 55.0% | 58.4% | **+23.0** | +0.0907 | 1.21 | 152 | 1.96% | -323 | **43.5%** | **24.2%** |

**The High Risk tier is 45.0% of trades, 56.5% of total P&L and 75.8% of all >1 ATR losses.** It contributes more P&L than its share of trades, which is the problem with cutting it: the risk and the return live in the same place.

For contrast, Low + Medium is 55.0% of trades, 43.5% of P&L and 24.2% of the large losses, at +23.0 bps with a 152 bps standard deviation against 225 for High Risk.

## 3. Verdict

| High Risk tier | Multiple of its trade share |
|---|---:|
| Share of P&L | 1.26× |
| Share of large losses | 1.68× |

Large losses are more concentrated in the High Risk tier (1.68×) than P&L is (1.26×), which looks like the classic case for cutting size there. **It is not, and the reason is the single most useful number in this report:**

| Group under equal size | NET | Std dev | **NET / Std** |
|---|---:|---:|---:|
| High Risk | +36.6 | 225 | **0.1629** |
| Low + Medium | +23.0 | 152 | **0.1519** |

**The High Risk tier is not risk-inefficient — it is simply bigger.** Its return per unit of volatility (0.1629) is at least as good as the Low + Medium tier's (0.1519). It earns more *and* swings more, in proportion. Cutting its size therefore removes return and risk together, which is why Schemes A, B and B2 all land within 0.5% of equal sizing on NET/Std and slightly below it: they are de-levering a part of the book that did not deserve to be de-levered.

This is the opposite of what the tier concentration table implies at first glance, and it is why the concentration of *large losses* is the wrong statistic to size on. A group can own most of the tail simply by being more volatile throughout, without being any worse per unit of that volatility.

Scheme D deserves separate comment. Volatility targeting is the most theoretically appealing of the four — it is the only one that equalises risk rather than approximating it — and it delivers the best risk-adjusted result here. But its weight distribution is the practical objection: a mean weight of 1.00 with a maximum of 4.7× means the quietest name in the sample gets a position many times the average. Any real implementation caps that, and the cap — not the theory — determines what the scheme actually earns.

## Reading notes

- **The tier thresholds were not fitted**, but they were chosen after seeing the segment tables in `VALIDATION_REPORT.md`, which is not the same as choosing them in advance.
- **Differences between schemes are small** relative to the standard deviation of a single trade. None of this is a new edge; it is a reallocation of an existing one.
- **Costs are flat 6.6 bps per unit of notional**, so a half-size trade pays half the cost. That is right for a spread-driven cost and wrong for any fixed per-ticket component, which would penalise the smaller positions.
- **No compounding, no portfolio constraint, no cap on concurrent positions.** These are per-trade averages, not an equity curve.

---

_Reproducible from `lambda_strategy_validation/regime_sizing.py`; tables in `lambda_data/tables/rs_*.csv`._