# Lambda — Validation and Diagnostic Review of the Post-Earnings T+1 Research

Core setup throughout: post-earnings T+1, entry at the 09:35 open, prior-session ATR(14), 6.6 bps round trip where relevant. ⚠ marks segments below 150 events.

## 0. A finding that changes how the earlier reports should be read

`events.parquet` holds 17,457 usable post-earnings T+1 events. Only **9,345** of the extract rows pass `universe_ok_prev` — the stated Sigma screen (price ≥ $10, ADV ≥ 500k shares, ADTV ≥ $50M, market cap ≥ $3B, all measured on the prior session).

**Every report in this series was run without that screen.** `prep_earnings()` reads the events table and filters only on `gap != 0`. So the headline cohort includes names outside the stated universe. The question is whether the edge survives:

| Cohort | n | Win rate | NET (bps) | NET (ATR) | % loss > 1 ATR | Median mkt cap | Median price |
|---|---:|---:|---:|---:|---:|---:|---:|
| All (as published) | 4,906 | 58.2% | **+30.4** | +0.1112 | 4.61% | $27.7B | $74 |
| Passes screen | 2,868 | 59.1% | **+30.8** | +0.1257 | 3.52% | $24.4B | $68 |
| Fails screen | 2,038 | 56.9% | **+29.8** | +0.0908 | 6.13% | $33.2B | $84 |

**On expectancy the screen barely matters** — +30.8 bps on the 2,868 events that pass against +29.8 on the 2,038 that fail, a difference of 0.9 bps and well inside noise. The published headline is not inflated by out-of-universe names.

**On risk it matters a great deal.**

| | Passes screen | Fails screen |
|---|---:|---:|
| NET (bps) | +30.8 | +29.8 |
| NET (ATR) | **+0.1257** | +0.0908 |
| % losing > 1 ATR | **3.52%** | 6.13% |
| Win rate | 59.1% | 56.9% |

The screened half earns the same basis points while suffering large losses 1.7× less often, and its ATR-denominated expectancy is 139% of the unscreened half's — i.e. materially better once each trade is measured against its own volatility. **Applying the screen is close to free on return and clearly positive on risk**, which makes it the easy call, and it should be an explicit choice rather than an omission.

**The excluded names are not small.** Their median market cap is $33.2B against $24.4B for those that pass, and their median price is $84 against $68. The binding constraint is the **500k-share ADV floor**, which a high-priced large cap fails on share count while clearing every dollar-based test — a $600 stock trading $50M a day changes hands under 100k times. That is a property of the filter, not of the companies, and it is worth deciding deliberately rather than inheriting.

## Part 1 — Trade characteristics

All segments below are the core High Volume + Continuation cohort, 1-hour hold, no stop.

**Sector**

| Segment | n | Win rate | NET (bps) | NET (ATR) | % loss > 1 ATR | Avg large loss (bps) |
|---|---:|---:|---:|---:|---:|---:|
| Communication Services | 325 | 62.8% | **+52.1** | +0.1772 | 5.23% | -364 |
| Consumer Discretionary | 855 | 58.5% | **+46.7** | +0.1497 | 3.51% | -413 |
| Consumer Staples | 306 | 57.5% | **+13.9** | +0.0536 | 3.59% | -239 |
| Energy | 254 | 57.9% | **+27.0** | +0.1084 | 3.15% | -372 |
| Financials | 504 | 55.4% | **+8.3** | +0.0597 | 4.17% | -285 |
| Healthcare | 509 | 58.9% | **+25.0** | +0.1038 | 4.52% | -319 |
| Industrials | 451 | 61.2% | **+31.6** | +0.1292 | 2.88% | -304 |
| Materials | 216 | 61.6% | **+50.7** | +0.1828 | 4.63% | -315 |
| Real Estate | 181 | 55.8% | **+8.7** | +0.0415 | 6.08% | -299 |
| Technology | 1,124 | 56.6% | **+29.9** | +0.1015 | 6.76% | -386 |
| Utilities | 181 | 55.8% | **+21.1** | +0.0759 | 3.31% | -222 |

**Stage (prior session)**

| Segment | n | Win rate | NET (bps) | NET (ATR) | % loss > 1 ATR | Avg large loss (bps) |
|---|---:|---:|---:|---:|---:|---:|
| Stage 2 — advancing | 2,396 | 58.1% | **+33.0** | +0.1254 | 4.55% | -333 |
| Stage 3 — topping | 707 | 58.8% | **+29.5** | +0.1096 | 4.67% | -321 |
| Stage 4 — declining | 1,751 | 58.2% | **+27.7** | +0.0941 | 4.63% | -377 |

**Year**

| Segment | n | Win rate | NET (bps) | NET (ATR) | % loss > 1 ATR | Avg large loss (bps) |
|---|---:|---:|---:|---:|---:|---:|
| 2015 | 379 | 64.1% | **+37.6** | +0.1728 | 2.64% | -313 |
| 2016 | 344 | 64.0% | **+49.9** | +0.2015 | 2.33% | -241 |
| 2017 | 446 | 57.0% | **+26.4** | +0.1190 | 4.26% | -266 |
| 2018 | 482 | 58.5% | **+29.2** | +0.1222 | 3.73% | -382 |
| 2019 | 474 | 57.2% | **+37.9** | +0.1537 | 4.64% | -341 |
| 2020 | 482 | 57.1% | **+17.3** | +0.0670 | 3.53% | -378 |
| 2021 | 516 | 57.2% | **+42.8** | +0.1231 | 4.26% | -410 |
| 2022 | 324 | 60.8% | **+38.8** | +0.0921 | 4.32% | -369 |
| 2023 | 512 | 54.7% | **+16.4** | +0.0489 | 6.25% | -362 |
| 2024 | 452 | 58.4% | **+30.9** | +0.1023 | 7.74% | -330 |
| 2025 | 495 | 54.9% | **+17.0** | +0.0587 | 5.86% | -356 |

**Month**

| Segment | n | Win rate | NET (bps) | NET (ATR) | % loss > 1 ATR | Avg large loss (bps) |
|---|---:|---:|---:|---:|---:|---:|
| Jan | 359 | 52.9% | **+10.8** | +0.0345 | 4.18% | -335 |
| Feb | 735 | 54.7% | **+15.3** | +0.0543 | 6.12% | -372 |
| Mar ⚠ | 126 | 59.5% | **+37.6** | +0.1666 | 1.59% | -210 |
| Apr | 482 | 57.3% | **+16.2** | +0.0804 | 2.90% | -291 |
| May | 527 | 60.5% | **+44.0** | +0.1709 | 4.55% | -320 |
| Jun ⚠ | 76 | 53.9% | **+12.5** | +0.0560 | 6.58% | -378 |
| Jul | 604 | 62.3% | **+29.4** | +0.1292 | 3.31% | -329 |
| Aug | 609 | 55.7% | **+24.1** | +0.0784 | 5.75% | -357 |
| Sep ⚠ | 104 | 56.7% | **+39.2** | +0.1190 | 3.85% | -250 |
| Oct | 612 | 62.6% | **+37.5** | +0.1369 | 4.74% | -323 |
| Nov | 552 | 59.6% | **+69.6** | +0.2133 | 4.89% | -374 |
| Dec ⚠ | 120 | 53.3% | **-5.7** | -0.0031 | 5.00% | -537 |

**Day of week**

| Segment | n | Win rate | NET (bps) | NET (ATR) | % loss > 1 ATR | Avg large loss (bps) |
|---|---:|---:|---:|---:|---:|---:|
| Mon | 231 | 63.2% | **+22.0** | +0.0945 | 0.43% | -653 |
| Tue | 452 | 61.1% | **+53.0** | +0.1733 | 6.42% | -381 |
| Wed | 1,224 | 57.5% | **+28.4** | +0.1034 | 3.92% | -290 |
| Thu | 1,394 | 58.2% | **+31.0** | +0.1097 | 4.88% | -350 |
| Fri | 1,605 | 57.0% | **+26.2** | +0.1035 | 4.98% | -365 |

**Gap / ATR**

| Segment | n | Win rate | NET (bps) | NET (ATR) | % loss > 1 ATR | Avg large loss (bps) |
|---|---:|---:|---:|---:|---:|---:|
| < 0.5 | 2,085 | 60.9% | **+35.2** | +0.1305 | 1.73% | -333 |
| 0.5 – 1.0 | 956 | 54.1% | **+20.0** | +0.0457 | 3.77% | -286 |
| 1.0 – 2.0 | 852 | 54.0% | **+13.9** | +0.0538 | 6.81% | -347 |
| > 2.0 | 1,013 | 59.9% | **+44.0** | +0.1817 | 9.48% | -377 |

**Volume ratio**

| Segment | n | Win rate | NET (bps) | NET (ATR) | % loss > 1 ATR | Avg large loss (bps) |
|---|---:|---:|---:|---:|---:|---:|
| 1.5 – 2.5× | 1,488 | 57.9% | **+21.4** | +0.0747 | 2.08% | -281 |
| 2.5 – 4× | 1,032 | 59.2% | **+26.0** | +0.1067 | 2.62% | -349 |
| 4 – 7× | 962 | 55.3% | **+26.4** | +0.0854 | 4.89% | -320 |
| > 7× | 1,424 | 59.6% | **+45.7** | +0.1701 | 8.50% | -375 |

**Candle body / range**

| Segment | n | Win rate | NET (bps) | NET (ATR) | % loss > 1 ATR | Avg large loss (bps) |
|---|---:|---:|---:|---:|---:|---:|
| 0.10 – 0.30 (weak) | 964 | 57.4% | **+26.9** | +0.1152 | 4.15% | -370 |
| 0.30 – 0.55 | 1,440 | 61.3% | **+48.1** | +0.1678 | 3.26% | -334 |
| 0.55 – 0.80 | 1,494 | 57.1% | **+23.9** | +0.0966 | 4.82% | -373 |
| > 0.80 (strong) | 1,008 | 56.0% | **+18.1** | +0.0483 | 6.65% | -317 |

### Where the differences are real

| Dimension | Strongest segment | NET | Weakest segment | NET | Spread |
|---|---|---:|---|---:|---:|
| Month | Nov (552) | +69.6 | Jan (359) | +10.8 | **58.7** |
| Sector | Communication Services (325) | +52.1 | Financials (504) | +8.3 | **43.9** |
| Year | 2016 (344) | +49.9 | 2023 (512) | +16.4 | **33.5** |
| Day of week | Tue (452) | +53.0 | Mon (231) | +22.0 | **30.9** |
| Gap / ATR | > 2.0 (1,013) | +44.0 | 1.0 – 2.0 (852) | +13.9 | **30.1** |
| Candle body / range | 0.30 – 0.55 (1,440) | +48.1 | > 0.80 (strong) (1,008) | +18.1 | **30.0** |
| Volume ratio | > 7× (1,424) | +45.7 | 1.5 – 2.5× (1,488) | +21.4 | **24.3** |
| Stage (prior session) | Stage 2 — advancing (2,396) | +33.0 | Stage 4 — declining (1,751) | +27.7 | **5.3** |

Read this table with suspicion rather than enthusiasm. Eight dimensions with several segments each is roughly fifty cells, so the widest spread being large is close to guaranteed by construction — none of these splits was hypothesised in advance, and no multiple-comparison adjustment is applied anywhere in it. The dimensions worth taking seriously are the ones with a **monotone** relationship, because a gradient across ordered buckets is far harder to produce by chance than one standout cell.

Ordered dimensions with a clean gradient:

- **Volume ratio** — rising monotonically across all 4 buckets (+21 → +26 → +26 → +46 bps).

## Part 2 — Distribution shape

Core cohort, 1-hour hold, under each rule.

| Rule | n | Mean | Median | p10 | p25 | p75 | p90 | Skew | Excess kurtosis |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Core — no stop | 4,906 | +37.0 | +28.7 | -172 | -66 | +130 | +254 | +14.75 | +610.9 |
| ATR −1.0 | 4,906 | +32.9 | +25.3 | -192 | -78 | +128 | +254 | +15.11 | +623.6 |
| Opening Range | 4,906 | +33.1 | +21.2 | -172 | -80 | +127 | +253 | +15.63 | +650.6 |
| Gap Level | 4,906 | +36.7 | +27.1 | -169 | -68 | +129 | +254 | +15.04 | +624.7 |

| Rule | Skew (winsorised 1/99) | Kurtosis (winsorised) | % < −0.5 ATR | % < −1.0 ATR | % > +1.0 ATR |
|---|---:|---:|---:|---:|---:|
| Core — no stop | +0.17 | +1.2 | 15.00% | 4.61% | 9.21% |
| ATR −1.0 | +0.36 | +0.8 | 17.86% | 1.06% | 9.01% |
| Opening Range | +0.40 | +1.0 | 15.70% | 3.79% | 9.07% |
| Gap Level | +0.26 | +1.1 | 14.76% | 4.48% | 9.17% |

**Plain-language shape.**

- **Core, no stop.** Mean +37.0 against a median of +28.7: the average sits above the typical trade, so a minority of large winners does the heavy lifting. Raw skew of +14.75 is one observation (the CAR squeeze); winsorised it is +0.17 — near-symmetric in the body with genuinely fat tails (+1.2 excess kurtosis even after capping). Gains beyond 1 ATR outnumber losses beyond 1 ATR by 2.0 to one. **A slightly-better-than-coin-flip hit rate with a modest positive payoff, and both tails fat.**
- **ATR −1.0.** Median +25.3 (-3.4 vs no stop), p10 -192 (-20). Losses beyond 1 ATR 1.06% against 4.61%. Truncates the left tail and pays for it out of the middle.
- **Opening Range.** Median +21.2 (-7.5 vs no stop), p10 -172 (-0). Losses beyond 1 ATR 3.79% against 4.61%. Barely reshapes the distribution.
- **Gap Level.** Median +27.1 (-1.6 vs no stop), p10 -169 (+3). Losses beyond 1 ATR 4.48% against 4.61%. Barely reshapes the distribution.

## Part 3 — Diagnostics

### What the stops are actually cutting

| Rule | Stopped | % that would have recovered to profit | % that would have beaten the stop price | Median MAE of stopped | Median MAE of kept | Forgone |
|---|---:|---:|---:|---:|---:|---:|
| ATR −1.0 | 10.9% | **9.7%** | 58.3% | -1.29 ATR | -0.28 ATR | +37.1 bps |
| Opening Range | 22.7% | **13.1%** | 52.0% | -0.75 ATR | -0.23 ATR | +17.3 bps |
| Gap Level | 7.0% | **10.8%** | 50.6% | -0.69 ATR | -0.30 ATR | +3.6 bps |

The recovery column is low everywhere, which is already at odds with how the earlier reports framed these stops. Profiling the two groups on entry-time variables shows why:

| Group | n | Median MAE | Median Gap/ATR | Median vol ratio | % that touched the gap level | Outcome if held | % profitable if held |
|---|---:|---:|---:|---:|---:|---:|---:|
| Stopped by ATR −1.0 | 535 | -1.293 ATR | 1.73 | 7.47 | 22.1% | -209.8 bps | 9.7% |
| Not stopped | 4,371 | -0.276 ATR | 0.58 | 3.64 | 8.0% | +67.2 bps | 64.1% |

**The stops are cutting genuine failures, not noise — and that is the opposite of what the earlier reports implied.** Two things fall out of this table that no previous report measured:

First, only **9.7%** of the trades the ATR −1.0 stop cuts would have finished the hour in profit, and as a group they end at **-210 bps** even if held. Against 64.1% and +67 bps for the trades it keeps. These are not temporary excursions that recover — they are losing trades that stay losing.

Second, they were **identifiable at entry**. The stopped group's median gap is 1.73 ATR against 0.58 for the kept group — three times larger — and its median volume ratio 7.47 against 3.64. The stop is not selecting on path noise. It is selecting, indirectly and after the fact, on two variables that were visible at 09:35.

So why does stopping still cost expectancy? Because the stop exits at roughly the worst available price. The group realises -247 bps stopped against -210 held — a 37 bps difference. The stop fires at maximum adverse excursion by construction, and even a failing post-earnings trade bounces off its low. **The stop identifies the right trades and exits them at the wrong moment.**

That distinction matters, because the two failure modes have different fixes. If stops were cutting noise, the answer would be a wider stop. Since they are cutting real losers at their worst price, the answer is to act on the same information *before* the trade rather than during it — which is the sizing argument below, and it is now supported rather than merely asserted.

### Why limit entries selected weaker trades

A limit order fills only when price retraces to it, so the filled sample is by construction the subset with an early adverse excursion — the same variable the stop selects on, approached from the other side. The stop diagnostic shows what that subset looks like: trades that end the hour at -210 bps on average against +67 bps for the ones that never pulled back.

So the limit order is not merely selecting a random subset that happened to dip. It is selecting, with reasonable fidelity, the trades that were going to do badly — for the same reason the stop does, because early adverse excursion genuinely predicts the outcome on this cohort. The difference is that the stop at least *exits* those trades, while the limit order **buys** them and declines to buy the others.

The asymmetry is what makes it expensive: trades that never pull back never appear in the filled sample at all, and those are the ones carrying the right tail. The limit order truncates the right tail of the entry distribution while admitting the left tail in full — which is why `ENTRYLIMITS_REPORT.md` found the missed trades outperforming the filled ones by 97 to 120 bps on identical entries.

### Practical implication for position sizing

The diagnostic above hands this section its answer. The trades the stop cuts carry **three times the gap/ATR and twice the volume ratio** of the ones it keeps, and both were observable at 09:35. The tail-risk columns in Part 1 confirm the same ordering independently:

| Dimension | Segment | n | % loss > 1 ATR | Avg large loss |
|---|---|---:|---:|---:|
| Gap / ATR | < 0.5 | 2,085 | 1.73% | -333 bps |
| Gap / ATR | 0.5 – 1.0 | 956 | 3.77% | -286 bps |
| Gap / ATR | 1.0 – 2.0 | 852 | 6.81% | -347 bps |
| Gap / ATR | > 2.0 | 1,013 | 9.48% | -377 bps |
| Volume ratio | 1.5 – 2.5× | 1,488 | 2.08% | -281 bps |
| Volume ratio | 2.5 – 4× | 1,032 | 2.62% | -349 bps |
| Volume ratio | 4 – 7× | 962 | 4.89% | -320 bps |
| Volume ratio | > 7× | 1,424 | 8.50% | -375 bps |

**Both are cleanly monotone in risk**, even where they are not monotone in return: the >1 ATR loss rate rises from 1.7% to 9.5% across the gap/ATR buckets and from 2.1% to 8.5% across the volume-ratio buckets. Risk is far more predictable from entry-time variables than return is — which is the single most useful thing in this review.

The practical implications follow directly:

- **Size on risk, not on expected return.** The gradient in the loss-rate columns is monotone and steep; the gradient in NET is neither. Halving size in the top gap/ATR and volume-ratio buckets cuts exposure to the segment carrying a 9.5% large-loss rate while giving up little of a return estimate that is not reliably higher there anyway.
- **Do it at entry, not intraday.** The information is fully available at 09:35. Waiting to act on it through a stop means paying the 37 bps bounce-off-the-low penalty measured above.
- **Reducing size dominates stopping out here.** Both act on the same trades; sizing acts before the adverse excursion and stopping acts at the bottom of it. That is the whole difference, and it is worth roughly the forgone figure per stopped trade.
- **Expect modest gains.** This is a risk-management improvement, not a new edge. Nothing in Part 1 separates *returns* sharply enough to build a selection rule on.

## Part 4 — AVWAP with a buffer

Anchored VWAP from 09:30, confirmed on the 5-minute close, with the stop level pushed a fixed fraction of ATR beyond the line.

| Buffer | NET (bps) | % stopped | % loss > 1 ATR | Avg overshoot | Recovery rate of stopped trades | Win rate |
|---|---:|---:|---:|---:|---:|---:|
| Exact AVWAP | **+18.0** | 77.1% | 1.10% | 37.3 bps | 46.0% | 44.2% |
| AVWAP ± 0.05 ATR | **+19.0** | 70.0% | 1.20% | 35.2 bps | 41.6% | 44.2% |
| AVWAP ± 0.10 ATR | **+20.4** | 61.9% | 1.37% | 34.8 bps | 36.4% | 45.7% |
| AVWAP ± 0.15 ATR | **+21.8** | 53.9% | 1.49% | 34.3 bps | 31.1% | 48.3% |

**The buffer helps monotonically, and it does not rescue the rule.** Going from the exact line to ±0.15 ATR lifts NET from +18.0 to +21.8 bps and cuts the stop-out rate from 77% to 54%. Every variant remains far below the no-stop baseline.

The recovery column is the interesting one: it **falls** from 46% to 31% as the buffer widens. That is confirmation the buffer is working as intended — each increment spares the trades most likely to have recovered, so what remains in the stopped bucket is progressively more genuinely broken. The buffer is a well-aimed instrument.

It still is not enough. At the exact line the rule stops 77% of all trades — it is barely a stop, more a re-entry signal — and even at ±0.15 ATR it stops 54%, giving up 9 bps against holding. Anchored VWAP sits too close to price on this cohort for a buffer of any practical width to fix.

The practitioner instinct behind the buffer is sound — it is targeting exactly the false triggers the diagnostics identify. It simply cannot reach far enough: by the time the buffer is wide enough to stop cutting recoverable trades, it is wide enough to stop doing anything.

## Part 5 — Full extract for independent validation

**16,188 events**, one row each, written to:

- `postearnings_extract.csv` — CSV, opens directly in Excel
- `postearnings_extract.xlsx` — native `.xlsx`

| Composition | n |
|---|---:|
| Total events in the extract | 16,188 |
| High Volume flag = Yes | 9,580 |
| Candle class = Continuation | 7,172 |
| **High Volume + Continuation** (the core cohort) | **4,906** |
| Passes the full universe screen | 9,345 |
| Distinct tickers | 610 |
| Date range | 2015-01-07 → 2025-12-22 |

### Columns

| Column | Meaning |
|---|---|
| `ticker, date` | identification |
| `sector` | GICS-style sector from the panel |
| `market_cap_prev_usd` | prior-session market cap |
| `passes_universe_screen` | Yes/No on the full Sigma screen — the filter the published cohort did **not** apply |
| `high_volume_flag` | Yes if `c1_volume` > 1.5× the trailing 20-session same-slot mean, shifted one session |
| `candle_class` | Continuation / Reversal / Indecisive, doji cut at body/range ≤ 0.10 |
| `gap_direction, gap_pct, gap_atr` | gap sign, size in %, and size in prior ATR |
| `vol_ratio_5min` | exact opening-candle volume ratio |
| `body_over_range` | |close−open| ÷ (high−low) of the first candle |
| `stage_prev` | Minervini stage 2/3/4 as of the prior session |
| `entry_px_0935` | open of the 09:35 bar |
| `ret_5min / 15min / 1hour_bps and _atr` | signed returns from entry, in bps and in prior ATR |
| `ret_t1_close_bps` | entry to the T+1 session close |
| `gap_level_touched_1h` | did price trade through the prior close in the first hour |
| `mae_1h_atr` | maximum adverse excursion in the first hour, in ATR |
| `atr14_prev` | prior-session ATR(14), the denominator throughout |
| `cost_in_atr` | the 6.6 bps round trip expressed in that row's ATR |

### Filters still applied to the extract

- **Post-earnings T+1 sessions only**, gap ≠ 0.
- **A real print by 09:35** — events with no opening trade cannot be given an entry price and are dropped.
- **A prior-session ATR(14)** must exist and be positive.
- **A mark at 10:35**, forward-filled from the session open as in every earlier report.

- **NOT applied:** the liquidity/market-cap screen. Every event is included and flagged with `passes_universe_screen` so it can be imposed or not. This is deliberate — it is the only way to reproduce the published cohorts *and* test them against the screened universe.
- **NOT applied:** the High Volume and Continuation filters. Both are columns, so the core cohort is `high_volume_flag = Yes` **and** `candle_class = Continuation`, which reproduces 4,906 rows.

### Two gaps in the data you should know about before filtering

- **`vol_ratio_5min` is blank on 301 rows (1.9%)** — the trailing 20-session volume benchmark needs 15 prior sessions, and a few names never accumulate them. Those rows are flagged `high_volume_flag = No`, because a missing ratio cannot clear the 1.5× test. None of them is currently counted as High Volume, so they are excluded from the core cohort by omission rather than by measurement. If you would rather treat them as unknown than as No, filter them out explicitly.
- **`market_cap_prev_usd` is blank on 11.2% of rows.** Market cap needs point-in-time shares outstanding, which is not derivable from OHLCV; where it is missing, `passes_universe_screen` is `No` by construction. That is one reason the screen excludes as much as it does, and it is a data limitation rather than a judgement about those names.

### Reproducing the headline figures

Filter to `high_volume_flag = Yes` and `candle_class = Continuation`, then average `ret_1hour_bps` and subtract 6.6. Small differences against `DIST_REPORT.md` are expected and explained: that report drops exactly-zero returns as stale prints, this extract keeps every row so nothing is silently removed from a validation file.

## Reading notes

- **Part 1 is exploratory.** Roughly fifty segment cells, no pre-registration, no multiple-comparison control. Treat the spread table as a map of where to look next, not as findings.
- **Costs remain flat at 6.6 bps** everywhere, including for the segments where that is least defensible.
- **The extract keeps zero returns**, so its cohort counts are marginally above the published ones.
- **Section 0 is the item to action.** Whether to impose the universe screen is a decision, not a detail, and it moves the cohort by 41.6%.

---

_Reproducible from `lambda_strategy_validation/validation.py`; tables in `lambda_data/tables/val_*.csv`._