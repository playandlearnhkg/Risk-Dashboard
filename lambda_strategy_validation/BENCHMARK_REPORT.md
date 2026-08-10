# Post-earnings T+1 continuation vs buy-and-hold

4,270 trades, 515 tickers, 2015-01-27 to 2025-12-19,
across 2,765 trading sessions.

**One definitional fix.** The brief says "non-doji, body/range <= 0.10",
which is the doji condition rather than its complement. The cohort here
uses body/range **> 0.10**, i.e. genuinely non-doji, matching every
earlier report in this programme.

## Assumptions that drive the numbers

| Choice | What was assumed | Why it matters |
|---|---|---|
| Direction | Short on gap-down continuations | "Buy the same stock" and "hold the position longer" are different questions; both are reported |
| Capital | Sleeve equal-weights that day's signals, cash otherwise | Charges the strategy for idle days rather than annualising deployed hours only |
| Cash yield | Zero on idle cash, rf = 0 in Sharpe | Conservative: a real cash rate adds ~1.9 pp/yr at 2%, ~3.7 pp/yr at 4%, and subtracts nothing |
| Costs | Flat 6.6 bps round trip | The most exposed assumption here; sensitivity is in section D4 |
| Deployment | Signal on 48.0% of sessions, ~7.4% of market hours | The strategy is in cash the overwhelming majority of the time |

## A. Per-trade comparison

Entry is identical in every row: the open of the 09:35 bar. Only the
exit differs. LONG-ONLY buys regardless of gap direction; SIGNED holds
the strategy's own direction for longer.

| exit rule | n | mean net | median | win rate | std dev | SPY, same window | excess vs SPY | return / risk |
|---|---|---|---|---|---|---|---|---|
| STRATEGY 1 hour, no stop | 4270 | 0.29% | 0.22% | 56.72% | 1.88% |  |  | 0.15 |
| STRATEGY 1 hour, ATR -1.0 stop | 4270 | 0.25% | 0.19% | 55.74% | 1.87% |  |  | 0.14 |
| hold to close, 1 day -- LONG-ONLY | 4270 | -0.11% | -0.11% | 47.75% | 2.73% | 0.09% | -0.20% | -0.04 |
| hold to close, 1 day -- SIGNED (strategy direction) | 4270 | 0.30% | 0.20% | 54.52% | 2.71% | 0.16% | 0.15% | 0.11 |
| hold to close, 5 days -- LONG-ONLY | 4270 | 0.04% | 0.01% | 50.05% | 5.12% | 0.36% | -0.32% | 0.01 |
| hold to close, 5 days -- SIGNED (strategy direction) | 4270 | 0.36% | 0.36% | 53.40% | 5.10% | 0.14% | 0.22% | 0.07 |
| hold to close, 20 days -- LONG-ONLY | 4270 | 0.73% | 0.76% | 54.24% | 10.05% | 1.15% | -0.42% | 0.07 |
| hold to close, 20 days -- SIGNED (strategy direction) | 4270 | 0.51% | 0.64% | 53.16% | 10.06% | 0.18% | 0.34% | 0.05 |
| hold to close, 60 days (~1 quarter) -- LONG-ONLY | 4270 | 2.78% | 2.37% | 57.24% | 26.55% | 3.27% | -0.49% | 0.10 |
| hold to close, 60 days (~1 quarter) -- SIGNED (strategy direction) | 4270 | 0.75% | 1.06% | 53.11% | 26.69% | 0.25% | 0.50% | 0.03 |

Three things read straight off this table.

**Buying these names and holding is a losing trade at short horizons.**
One day long-only returns -11 bps at a 47.8% win rate. Half the
signals are gap-down names and holding those long is simply the wrong
side.

**At long horizons you are buying beta, and slightly less of it than
SPY.** Sixty sessions long-only returns 2.78% against 3.27% for SPY
over the identical windows -- an excess of -49 bps. You would have
done better owning the index.

**Holding the direction longer earns more per trade and much less per
unit of risk.** Sixty sessions signed returns 75 bps against the
1-hour 29 bps, but its standard deviation is 14x larger, so
return-per-unit-risk falls from 0.155 to 0.028. The extra return
costs far more risk than it is worth, and ties capital up for a quarter
instead of an hour.

## B and C. Portfolio level, with risk-adjusted metrics

| portfolio | total return | CAGR | ann. vol | Sharpe (rf=0) | max drawdown | Calmar | best day | worst day | % days deployed |
|---|---|---|---|---|---|---|---|---|---|
| Strategy only, no stop | 4,839.29% | 42.68% | 15.72% | 2.72 | -18.39% | 2.32 | 7.60% | -7.65% | 47.96% |
| Strategy only, ATR -1.0 stop | 3,449.58% | 38.45% | 15.37% | 2.50 | -19.60% | 1.96 | 7.60% | -6.18% | 47.96% |
| SPY buy-and-hold | 274.17% | 12.78% | 17.88% | 0.71 | -33.85% | 0.38 | 9.47% | -11.63% |  |
| Signal basket, long, 1 day hold | -81.07% | -14.07% | 22.62% | -0.62 | -82.09% | -0.17 | 10.77% | -14.32% |  |
| Signal basket, long, 5 days hold | -24.51% | -2.53% | 23.53% | -0.11 | -68.24% | -0.04 | 12.83% | -12.68% |  |
| 80% SPY + 20% strategy (stop) | 516.01% | 18.02% | 14.65% | 1.23 | -28.81% | 0.63 | 7.58% | -9.31% |  |
| 70% SPY + 30% strategy (stop) | 683.20% | 20.63% | 13.37% | 1.54 | -26.32% | 0.78 | 6.63% | -8.14% |  |
| 100% SPY + 25% strategy overlay (stop) | 834.97% | 22.60% | 18.31% | 1.23 | -35.03% | 0.64 | 9.47% | -11.63% |  |

## Is it market exposure in disguise?

| strategy | beta to SPY | alpha, annualised | corr to SPY | mean on SPY up days | mean on SPY down days |
|---|---|---|---|---|---|
| no stop | 0.0075 | 36.69% | 0.0086 | 0.14% | 0.16% |
| ATR -1.0 stop | 0.0065 | 33.64% | 0.0076 | 0.13% | 0.14% |

Beta to SPY is 0.008, correlation 0.009. Essentially all of the
return is alpha, and the strategy earns as much on SPY down days
(16 bps) as on up days (14 bps). Whatever this is, it is
not disguised long exposure -- which is what makes it useful as an
overlay rather than a substitute.

## D. The four questions

**1. Does it add value on top of holding SPY?** Yes, and the blend is
the practical form. 70/30 lifts CAGR from 12.8% to 20.6% while
*lowering* volatility from 17.9% to 13.4% and cutting max drawdown
from -33.8% to -26.3%. Sharpe roughly doubles, 0.71 to 1.54.
Improving all three axes at once is only possible because the
correlation is near zero.

The overlay version (100% SPY plus a 25% notional sleeve funded by
intraday buying power rather than by selling SPY) reaches a higher CAGR
still at 22.6%, but inherits SPY's drawdown (-35.0%) because it never
reduces market exposure. Capital-split blend for risk reduction, overlay
for return.

**2. Is the 1-hour edge worth the activity versus longer holds?** On
risk-adjusted terms, clearly. The 1-hour hold has the best
return-per-unit-risk in section A (0.155) and achieves it while using
capital ~7.4% of market hours. Every longer hold is worse per unit
of risk and locks capital up for days or months. The
buy-and-hold-the-signal-names baskets confirm it from the portfolio
side: the 1-day long basket compounds at -14.1% a year with a -82.1%
drawdown.

The caveat is that "worth it" here ignores the operational load: about
389 trades a year, all at a fixed minute of the session.

**3. How does the ATR -1.0 stop compare in a portfolio context?** It
costs more than it saves. CAGR falls from 42.7% to 38.4% and max
drawdown gets *worse*, -18.4% to -19.6%. Sharpe drops 2.72 to
2.50, Calmar 2.32 to 1.96.

What it does buy is a shallower worst day, -7.7% to -6.2%,
firing on 10.6% of trades. So it trims the single worst session
but not the drawdown that matters, because drawdowns here accumulate
from ordinary losing days rather than one catastrophic one. That is
consistent with what the stop work already found at trade level: it
truncates the tail and pays for it in expectancy.

**4. Where does this break?** Cost, before anything else.

| round-trip cost (bps) | mean net (bps) | win rate | strategy CAGR |
|---|---|---|---|
| 6.60 | 29.14 | 56.72% | 42.68% |
| 10.00 | 25.74 | 55.76% | 36.95% |
| 15.00 | 20.74 | 54.17% | 28.94% |
| 25.00 | 10.74 | 50.98% | 14.28% |
| 35.00 | 0.74 | 48.08% | 1.28% |

Gross edge is 35.7 bps, so the strategy dies at roughly **36 bps round
trip**, about 5.4x the assumed cost. At 25 bps it still compounds
at 14.3%, roughly SPY's rate, with none of SPY's drawdown. That is a
wide margin -- but 09:35 in a post-earnings name is exactly where
spreads are widest, and a flat 6.6 bps does not distinguish a
mega-cap from a mid-cap on the morning after a surprise.

## What these numbers do not include

- **Borrow.** Roughly half the trades are shorts. No borrow cost or
  locate constraint is modelled, and post-earnings names are exactly
  when borrow gets expensive and hard to source.
- **Concentration.** The sleeve holds 3.2 names on an average deployed
  day, median 2, and is in a **single name on 38% of deployed
  days** (p90 7 names, max 20). The portfolio statistics are real,
  but they are not a diversified book's.
- **The Sharpe is flattered by idle days.** Volatility measured only on
  days capital is at work is 22.4%, not the 15.7% headline. Both are
  honest answers to different questions; anyone sizing the sleeve should
  use the deployed figure.
- **Capacity.** Nothing here constrains position size against a name's
  actual liquidity in that hour.

Generated by `benchmark.py`.
