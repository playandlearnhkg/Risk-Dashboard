# $1,000,000 in the strategy vs $1,000,000 in SPY

Identical terms: 2015-01-02 to 2025-12-31, 2,766 sessions, same
starting capital. Strategy configuration is the FULLVAL base --
frac0.5, max 5, 6.6 bps.

## The headline

| portfolio | final equity | CAGR | ann. vol | Sharpe (rf=0) | max DD | Calmar | worst day | worst month |
|---|---|---|---|---|---|---|---|---|
| SPY buy-and-hold | $3.74M | 12.77% | 17.87% | 0.71 | -33.85% | 0.38 | -11.63% | -12.47% |
| Strategy only, 1 hour, no stop | $6.62M | 18.79% | 6.66% | 2.82 | -6.46% | 2.91 | -2.54% | -3.52% |
| Strategy only, 1 hour, ATR -1.0 stop | $5.18M | 16.17% | 6.42% | 2.52 | -7.06% | 2.29 | -1.73% | -3.36% |
| Strategy, no stop, scaled to SPY vol (2.7x) | $142.88M | 57.16% | 17.87% | 3.20 | -16.51% | 3.46 | -6.81% | -9.46% |
| 90% SPY + 10% strategy (stop) | $3.93M | 13.29% | 16.11% | 0.83 | -31.00% | 0.43 | -10.47% | -11.04% |
| 80% SPY + 20% strategy (stop) | $4.12M | 13.77% | 14.37% | 0.96 | -28.27% | 0.49 | -9.31% | -9.64% |
| 70% SPY + 30% strategy (stop) | $4.30M | 14.21% | 12.69% | 1.12 | -25.48% | 0.56 | -8.14% | -8.30% |
| 50% SPY + 50% strategy (stop) | $4.63M | 14.97% | 9.54% | 1.57 | -19.94% | 0.75 | -5.82% | -5.78% |
| 100% SPY + 30% strategy overlay (stop) | $6.15M | 18.00% | 18.00% | 1.00 | -34.57% | 0.52 | -11.63% | -12.58% |

On raw numbers the strategy wins outright: **$6.62M against SPY's
$3.74M**, at roughly a third of the volatility (6.7% vs
17.9%) and a fifth of the drawdown (-6.5% vs -33.8%). Sharpe
2.82 against 0.71, Calmar 2.91 against 0.38.

That is a real result, but it is not the interesting one, and quoting it
alone would be misleading in both directions at once. The strategy is
not taking anything like SPY's risk, so on one reading it is being
under-credited; on another, its return is only available at a scale the
brief forbids. Both readings are below.

## The scaled comparison, and why it is not a recommendation

Matching SPY's volatility would need **2.7x** the position size, which
would take average gross exposure when active from about 52% to roughly
140%, and higher on busy days. At that scale the strategy returns
57.2% a year with a -16.5% drawdown -- better than SPY on both
axes simultaneously.

Treat that row as an illustration of the risk-adjusted gap, not a plan.
It breaches the 1x gross cap the validation was run under, and the
linear scaling assumes fills and borrow behave identically at 2.7x size,
which is exactly the assumption a capacity study exists to test and this
one has not.

## Year by year -- where the value actually comes from

| year | SPY | strategy (no stop) | strategy (stop) | difference | beat SPY |
|---|---|---|---|---|---|
| 2015 | 0.88% | 25.41% | 23.97% | 24.53% | True |
| 2016 | 11.98% | 31.63% | 25.94% | 19.65% | True |
| 2017 | 21.71% | 21.77% | 16.90% | 0.06% | True |
| 2018 | -4.51% | 26.16% | 25.31% | 30.67% | True |
| 2019 | 31.14% | 27.93% | 24.25% | -3.21% | False |
| 2020 | 18.31% | 10.84% | 9.53% | -7.47% | False |
| 2021 | 28.30% | 12.36% | 8.71% | -15.94% | False |
| 2022 | -22.80% | 7.36% | 6.50% | 30.16% | True |
| 2023 | 26.19% | 13.33% | 12.15% | -12.86% | False |
| 2024 | 24.87% | 19.99% | 15.85% | -4.88% | False |
| 2025 | 17.70% | 12.25% | 10.66% | -5.45% | False |

The strategy beats SPY in **5 of 11 years**, which on its own sounds
mediocre. The pattern is what matters, and it is almost mechanical: the
strategy returned between 7% and 32% every single year, so
**who wins is decided almost entirely by what SPY did**, not by what the
strategy did.

- In the 2 years SPY fell, the strategy beat it by an average of
  **30.4 percentage points** and was positive in both -- +31 pp in
  2018 and +30 pp in 2022.
- It also beat SPY in the 3 up-years where the index returned less
  than about 22%.
- It lost in every year SPY returned more than about 18%, by up to
  16 pp. Holding cash ~93% of the time cannot keep pace with a
  strong index, and no amount of edge inside one hour a day will change
  that.

Correlation to SPY is 0.016. This is not a better version of owning the
index; it is a flatter, steadier return stream whose relative value
appears exactly when the index disappoints.

## Rolling 12-month windows

| series | % of windows negative | worst 12m | best 12m | median 12m |
|---|---|---|---|---|
| SPY | 15.79% | -24.29% | 77.87% | 15.58% |
| Strategy (no stop) | 0.00% | 4.40% | 39.04% | 17.77% |
| Strategy (stop) | 0.00% | 3.34% | 36.53% | 14.61% |

SPY spends 15.8% of rolling one-year windows under water and its
worst is -24.3%. The strategy has **no negative rolling
12-month window in the sample** -- worst is
+4.4%. That is the single most useful fact in this report
for anyone deciding how to hold it, and also the one most likely to be
an artefact of a favourable sample: eleven years contains only about six
independent non-overlapping year-long windows, and the strategy has
never yet met a regime that broke it.

## Blends, which are the practical answer

| portfolio | CAGR | ann. vol | Sharpe (rf=0) | max DD | Calmar |
|---|---|---|---|---|---|
| 90% SPY + 10% strategy (stop) | 13.29% | 16.11% | 0.83 | -31.00% | 0.43 |
| 80% SPY + 20% strategy (stop) | 13.77% | 14.37% | 0.96 | -28.27% | 0.49 |
| 70% SPY + 30% strategy (stop) | 14.21% | 12.69% | 1.12 | -25.48% | 0.56 |
| 50% SPY + 50% strategy (stop) | 14.97% | 9.54% | 1.57 | -19.94% | 0.75 |
| 100% SPY + 30% strategy overlay (stop) | 18.00% | 18.00% | 1.00 | -34.57% | 0.52 |

Every step from SPY toward the strategy raises return and lowers both
volatility and drawdown at the same time. 70/30 gets 14.2% CAGR at
12.7% vol and -25.5% drawdown; 50/50 gets 15.0% at 9.5% and
-19.9%. On a Sharpe basis the optimum inside a 1x cap is simply as
much strategy as you are willing to hold.

The overlay (SPY plus a 30% sleeve funded by intraday buying power
rather than by selling SPY) reaches 18.0% but keeps SPY's full
drawdown at -34.6%, because it never reduces market exposure.

## Reconciling with BENCHMARK_REPORT

That earlier report showed a 70/30 blend at 20.6% CAGR; this one shows
14.2%. Nothing has changed about the edge -- the difference is
entirely the capital convention. BENCHMARK sized every signal day at
100% of the sleeve equal-weighted across that day's names, with no
position limit. This report uses 0.5% fixed-fractional risk and a
five-position cap, which runs the sleeve at about 52% gross when active
and skips 19% of signals.

The figures here are the conservative ones and should be preferred.

## What has not changed

The caveats from FULLVAL carry over unaltered and all cut the same way:
no borrow cost on a book that is half short and earns more on the short
side; a flat 6.6 bps that does not widen for mid-caps at 09:35; no
capacity constraint; and an edge that is roughly half as large in
2022-2025 as it was in 2015-2019. A comparison against SPY does not
repair any of them -- it only shows that SPY has its own problems.

Generated by `buyhold.py`.
