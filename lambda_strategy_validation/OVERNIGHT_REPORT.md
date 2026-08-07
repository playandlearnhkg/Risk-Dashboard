# Lambda — Residual Edge in the Session After the Trade

Two universes: the post-earnings continuation cohort, and ordinary non-earnings sessions.

> **"Overnight" here means close → close.** Both designs specify the return from one close to the next, which is a full trading session *plus* the gap that precedes it — not the gap alone. The gap is broken out separately in section C so the two are never conflated. Returns are gross; no cost is applied, because holding an existing position overnight incurs no new round trip.

## Test 1 — Post-earnings (T+1 → T+2)

| Input | Definition |
|---|---|
| Cohort | High Volume + Continuation (non-doji), the setup used throughout this series |
| Entry | 09:35 open on T+1 |
| Classification | the T+1 **close** result, signed in the trade's direction |
| Measured | T+1 close → T+2 close, same sign |
| ATR | ATR(14) as of the T+1 close — known when the hold-overnight decision is made |

### A. Performance

| Group | n | Avg return | Win rate | Median | p10 | p90 | % losing > 1.0 ATR |
|---|---:|---:|---:|---:|---:|---:|---:|
| Winners at T+1 close | 2,786 | **+1.7** | 50.5% | +2.9 | -278 | +284 | 8.18% |
| Losers at T+1 close | 2,152 | **+6.2** | 50.9% | +4.8 | -274 | +278 | 9.01% |
| All trades | 4,938 | **+3.7** | 50.7% | +3.5 | -276 | +282 | 8.55% |

All figures in basis points. For reference, the T+1 day trade itself returned +214 bps (winners), -184 bps (losers), +40 bps (all trades).

### B. Distribution shape

| Group | Std dev | Skewness | Excess kurtosis |
|---|---:|---:|---:|
| Winners at T+1 close | 273 | -0.58 | +8.6 |
| Losers at T+1 close | 250 | -0.30 | +4.6 |
| All trades | 263 | -0.48 | +7.3 |

Excess kurtosis, so a normal distribution reads 0.0.

### C. Next-day gap behaviour (T+1 close → T+2 open)

| Group | Avg gap | Median gap | % gaps **with** the trade | % **against** | Avg favourable gap | Avg unfavourable gap |
|---|---:|---:|---:|---:|---:|---:|
| Winners at T+1 close | **-7.4** | -4.5 | 47.1% | 52.3% | +76.1 | -82.7 |
| Losers at T+1 close | **+3.6** | +2.2 | 51.1% | 47.4% | +77.0 | -75.4 |
| All trades | **-2.6** | -0.7 | 48.8% | 50.2% | +76.5 | -79.7 |

**The gap and the full period point opposite ways.** Across all trades the gap averages -2.6 bps while the whole close-to-close move averages +3.7 bps, so the T+2 session's intraday move contributes about +6.3 bps and more than offsets the opening drift. Neither component is large.

The more useful numbers in that table are the last three columns. Gaps go with the trade 48.8% of the time against 50.2% — a coin flip — and a favourable gap is worth +77 bps while an unfavourable one costs -80. **You are taking roughly symmetric 75–80 bps two-way risk at the open for an expected value of -2.6 bps.** That is the clearest statement of what carrying the position overnight actually buys.

### What test 1 shows

| Group | Pooled mean | 95% CI | p (clustered) | Date-weighted mean | t |
|---|---:|---:|---:|---:|---:|
| Winners at T+1 close | +1.7 | [-10.5, +17.3] | 0.614 | +1.5 | 0.21 |
| Losers at T+1 close | +6.2 | [-10.2, +22.6] | 0.462 | +7.4 | 1.11 |
| All trades | +3.7 | [-4.8, +11.5] | 0.379 | +4.3 | 0.78 |

**No group shows a residual edge distinguishable from zero.** The post-earnings continuation move is finished by the T+1 close: whatever the trade did during the day, the next session carries no reliable continuation and no reliable reversal.

Winners minus losers is **-4.6 bps**. That is small relative to the 263 bps standard deviation of the period, so the T+1 outcome is close to uninformative about the next session. 

## Test 2 — Ordinary non-earnings sessions

| Input | Definition |
|---|---|
| Universe | 551 tickers, 2015-01-02 → 2025-12-30 |
| Liquidity screen | price ≥ $10, ADV ≥ 500k shares, ADTV ≥ $50M, market cap ≥ $3B — all on the **prior** session, so point-in-time |
| Exclusions | post-earnings T+1 sessions, and the session before one (its close-to-close would land on a T+1) |
| Classification | day T **open → close**; a Winner closed above its open |
| Measured | T close → T+1 close, **long** |

Sample construction: 2,019,751 panel sessions → 663,715 passing the liquidity screen → 653,322 after removing earnings-adjacent days → **652,904** with a usable next close, after dropping 393 rows spanning a data seam.

> **A data problem found and fixed while running this.** The panel's price basis changes between 2022-03-04 and the following session: 28 liquid names show one-step close-to-close moves of 10× to 21× (AMZN 2,911 → 138, GOOGL 2,637 → 125, NVDA 229 → 21). Those are split adjustments applied from that date, not returns. Left in, they drove the excess kurtosis of this sample to over 23,000 and pulled the mean noticeably. Every close-to-close observation spanning that boundary is now dropped — for all tickers, not just the visibly broken ones, since the basis change affects the series rather than the name. It sits next to the 2022-03-01 IEX tape change already handled in the volume work.

Genuine extremes are deliberately **kept**. The largest surviving moves are real market history:

| Ticker | Date | Close | Next close | Return |
|---|---|---:|---:|---:|
| GME | 2021-01-26 | 145.97 | 345.00 | +13,635 bps |
| GME | 2021-02-23 | 44.94 | 91.70 | +10,405 bps |
| GME | 2021-01-25 | 76.77 | 145.97 | +9,014 bps |
| RKT | 2021-03-01 | 23.21 | 39.76 | +7,131 bps |
| TAL | 2021-07-22 | 20.52 | 6.00 | -7,076 bps |
| GME | 2021-01-28 | 197.44 | 328.24 | +6,625 bps |
| GME | 2021-02-01 | 227.00 | 90.47 | -6,015 bps |
| GME | 2021-01-12 | 19.94 | 31.44 | +5,767 bps |

> **Direction convention.** An ordinary session carries no signal direction, so the position is taken as long-the-stock and the following period is measured long. Winners are therefore stocks that rose during the session, and a negative average for that group means the rise partly gave back.

| Group | n | Avg return | Win rate | Median | p10 | % losing > 1.0 ATR | Skewness | Excess kurtosis |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Winners on day T | 331,202 | **+3.8** | 51.3% | +4.8 | -207 | 6.90% | +0.91 | +69.9 |
| Losers on day T | 321,702 | **+8.2** | 53.0% | +10.6 | -220 | 7.38% | +0.34 | +44.0 |
| All sessions | 652,904 | **+6.0** | 52.1% | +7.6 | -213 | 7.14% | +0.60 | +55.6 |

| Group | Std dev | 95% CI on the mean | p (clustered) |
|---|---:|---:|---:|
| Winners on day T | 222 | [+3.1, +6.8] | 0.000 |
| Losers on day T | 239 | [+6.8, +11.2] | 0.000 |
| All sessions | 230 | [+5.5, +7.4] | 0.000 |

### The weighting changes the answer

The means above are **pooled** — every observation counts equally, so a day contributing many names counts more than a quiet one. A daily-rebalanced equal-weight book earns the **date-weighted** mean instead: average within each date first, then across dates. On this sample the two disagree.

| Group | Pooled mean | Date-weighted mean | SE | t | n dates |
|---|---:|---:|---:|---:|---:|
| Winners on day T | +3.81 | **+7.59** | 2.84 | 2.67 | 2,681 |
| Losers on day T | +8.23 | **+8.19** | 3.10 | 2.64 | 2,682 |
| All sessions | +5.99 | **+9.02** | 2.80 | 3.23 | 2,764 |

**Winners minus losers is -4.42 bps pooled but -0.60 bps date-weighted.** The reversal effect is largely an artefact of weighting: once each day counts once, winners and losers earn almost the same thing over the following session. What survives both weightings is the level — the whole universe drifts up close-to-close, which is the equity risk premium showing up on a one-day horizon, not a signal.

### What test 2 shows

**On the pooled numbers day-T losers beat day-T winners by 4.4 bps** (+8.2 against +3.8) — the short-horizon reversal the literature would predict. **But it does not survive equal weighting by date**, where the gap shrinks to 0.6 bps. Report it as a weighting artefact, not an edge.

What does survive both weightings is the **level**: every group, including losers, earns a positive close-to-close return (+9.0 bps date-weighted, t = 3.2). That is the equity risk premium arriving on a one-day horizon, available to anyone already holding the stock and not a signal to act on.

On a sample of 652,904 sessions even small effects clear significance easily, so the p-values here say little about tradeability. The relevant comparison is the effect size against the 230 bps standard deviation of a single overnight-plus-session return, and against a round trip that would cost roughly 6.6 bps to put on and take off.

## The two tests side by side

| | Post-earnings T+1→T+2 | Ordinary T→T+1 |
|---|---:|---:|
| n | 4,938 | 652,904 |
| Winners' next return | +1.7 | +3.8 |
| Losers' next return | +6.2 | +8.2 |
| Winners − Losers | -4.6 | -4.4 |
| Std dev | 263 | 230 |
| Skewness (all) | -0.48 | +0.60 |
| Excess kurtosis (all) | +7.3 | +55.6 |

The post-earnings cohort is the more volatile of the two by a wide margin, which is expected — these are names that just gapped on news. What matters for the question asked is that the extra volatility does not come with extra edge.

## Reading notes

- **No costs are applied.** Holding a position you already own through the close incurs no new round trip, so a gross figure is the right one for the decision "carry it or flatten it". Anyone putting the position on *fresh* at the close would pay the usual 6.6 bps, which exceeds most of the effects above.
- **Overnight carries risks the intraday tests do not**: no opportunity to manage the position, gap risk on unrelated news, and — for the gap-down cohort, which is short — borrow that must be maintained. None of that is priced here.
- **Test 2's classification is long-only by construction.** Winners are sessions that rose. A short-side framing would mirror the table rather than add to it.
- **Both tests are date-clustered** in their inference, which matters most for test 2 where a single day contributes thousands of correlated observations.
- **Survivorship applies to test 2** in the usual direction: the panel contains names that existed through the sample.

---

_Reproducible from `lambda_strategy_validation/overnight.py`; tables in `lambda_data/tables/on_*.csv`._