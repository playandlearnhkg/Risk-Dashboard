# Lambda — Stop Rules: Consolidated Cost/Benefit and Fill Quality

Post-earnings T+1, High Volume + Continuation (non-doji), entry at the open of the 09:35 bar, target exit 10:35. Every rule tested in this series on one cohort, with fill quality measured for the first time.

| Input | Definition |
|---|---|
| Universe | Post-earnings T+1, 2015-01-27 → 2025-12-19 |
| Cohort | 4,906 events |
| Intrabar rules (4, 5) | trigger on the first touch; fill at the level, or the bar's open if it opened through |
| Close-confirmed rules (2, 3, 6, 7) | trigger only if a 5-minute bar CLOSES beyond the level (12 checkpoints); fill at that close |
| ATR | prior-session ATR(14); no gap-day data |
| Costs | 6.6 bps round trip, charged identically to stopped and held trades |

## A. Core performance

| Rule | Trigger | % stopped | Win rate | **NET** | Avg Win | Avg Loss | Payoff | Median |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1. No stop | — | — | 58.2% | **+30.4** | 153.6 | 126.9 | 1.21 | +28.7 |
| 2. Gap Level | 5-min close | 7.0% | 57.4% | **+30.1** | 154.8 | 124.1 | 1.25 | +27.1 |
| 3. Opening Range | 5-min close | 22.7% | 55.2% | **+26.5** | 157.6 | 121.6 | 1.30 | +21.2 |
| 4. ATR −0.5 | intrabar | 34.1% | 50.7% | **+22.2** | 160.4 | 107.5 | 1.49 | +3.9 |
| 5. ATR −1.0 | intrabar | 10.9% | 57.1% | **+26.3** | 154.4 | 130.4 | 1.18 | +25.3 |
| 6. AVWAP 09:30 | 5-min close | 77.1% | 44.2% | **+18.0** | 146.4 | 72.4 | 2.02 | -9.8 |
| 7. AVWAP prior close | 5-min close | 41.1% | 52.9% | **+27.0** | 159.6 | 108.7 | 1.47 | +13.4 |

## B. Tail risk — losses beyond 1.0 ATR

| Rule | n | % of trades | Avg loss (bps) | Avg loss (ATR) | Median (bps) | Worst (bps) | **Drag (bps/trade)** |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1. No stop | 226 | 4.61% | -348 | -1.48 | -312 | -1,140 | **-16.0** |
| 2. Gap Level | 220 | 4.48% | -340 | -1.46 | -302 | -1,140 | **-15.3** |
| 3. Opening Range | 186 | 3.79% | -312 | -1.37 | -272 | -791 | **-11.8** |
| 4. ATR −0.5 | **0** | 0.00% | — | — | — | — | **+0.0** |
| 5. ATR −1.0 | 52 | 1.06% | -261 | -1.07 | -233 | -774 | **-2.8** |
| 6. AVWAP 09:30 | 54 | 1.10% | -308 | -1.35 | -301 | -763 | **-3.4** |
| 7. AVWAP prior close | 177 | 3.61% | -331 | -1.40 | -291 | -1,109 | **-11.9** |

Drag is the sum of every >1 ATR loss divided by all 4,906 trades — the part of expectancy the large losses eat.

## C. Fill quality — how far past the intended level the stop actually filled

> **The "% filled worse" column means two different things, and the difference is structural, not empirical.** An intrabar stop exits *at* its level, so it can only fill worse when a bar opens through — that percentage is a genuine measure of slippage risk. A close-confirmed stop exits at whatever the bar closed at, which is *by definition* already beyond the level, so its percentage is 100% by construction and carries no information. For rules 2, 3, 6 and 7 only the **size** of the overshoot is an empirical question.

| Rule | Trigger | Stopped | % filled worse | Avg overshoot (bps) | Avg (ATR) | Median (bps) | Worst (bps) | Worst (ATR) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2. Gap Level | 5-min close | 342 | 100.0% | **29.1** | 0.104 | 16.2 | 428 | 1.07 |
| 3. Opening Range | 5-min close | 1,113 | 100.0% | **37.4** | 0.133 | 22.0 | 469 | 1.16 |
| 4. ATR −0.5 | intrabar | 1,674 | 10.1% | **1.3** | 0.006 | 0.0 | 134 | 0.32 |
| 5. ATR −1.0 | intrabar | 535 | 9.7% | **1.7** | 0.007 | 0.0 | 85 | 0.32 |
| 6. AVWAP 09:30 | 5-min close | 3,782 | 100.0% | **37.3** | 0.141 | 22.7 | 506 | 1.49 |
| 7. AVWAP prior close | 5-min close | 2,014 | 100.0% | **26.9** | 0.102 | 17.3 | 421 | 1.12 |

**Intended stop level versus what was actually realised**, averaged over the trades each rule stopped:

| Rule | Mean intended level (bps) | Mean realised (bps) | Shortfall | **Overshoot drag (bps/trade, whole book)** |
|---|---:|---:|---:|---:|
| 2. Gap Level | -125 | -154 | -29 | **-2.0** |
| 3. Opening Range | -126 | -163 | -37 | **-8.5** |
| 4. ATR −0.5 | -131 | -132 | -1 | **-0.5** |
| 5. ATR −1.0 | -245 | -247 | -2 | **-0.2** |
| 6. AVWAP 09:30 | +1 | -36 | -37 | **-28.7** |
| 7. AVWAP prior close | -68 | -94 | -27 | **-11.1** |

The last column is the expectancy lost purely to imperfect fills, spread across the whole book — separable from the expectancy lost to the stop firing at all.

**Close-confirmed stops overshoot by roughly 21× as much as intrabar stops** — an average of 33 bps past the intended level against 2 bps. That gap is the price of waiting for confirmation, and it is the single largest hidden cost in the structural and VWAP rules. None of the earlier reports could see it, because they measured only what the stops returned, never what they promised.

3. Opening Range is the worst offender at 37 bps average overshoot (0.13 ATR), with a worst case of 469 bps.

### Fill quality is the entire story for the confirmed rules

Adding each rule's overshoot drag back to its NET gives what it would have earned had every stop filled exactly at its intended level:

| Rule | NET as traded | Overshoot drag | NET if filled at the level | vs no stop |
|---|---:|---:|---:|---:|
| 2. Gap Level | +30.1 | -2.0 | **+32.2** | +1.8 |
| 3. Opening Range | +26.5 | -8.5 | **+34.9** | +4.6 |
| 4. ATR −0.5 | +22.2 | -0.5 | **+22.6** | -7.7 |
| 5. ATR −1.0 | +26.3 | -0.2 | **+26.5** | -3.9 |
| 6. AVWAP 09:30 | +18.0 | -28.7 | **+46.8** | +16.4 |
| 7. AVWAP prior close | +27.0 | -11.1 | **+38.1** | +7.7 |

**Every close-confirmed rule would beat holding if it filled at its level.** All four are pushed below the baseline purely by fill quality — the overshoot costs more than the stop's entire net disadvantage. That reframes the earlier reports: the structural and VWAP levels are not choosing bad moments to exit, they are choosing bad *prices*, and the price is bad because the confirmation is what makes it late.

This is a diagnostic, not a strategy. A confirmed break cannot fill at its level by construction — you only learn the level broke once the bar has closed past it. But it does point somewhere concrete: an **intrabar** version of these same levels would capture most of that gap, and none of the reports so far has tested one.

## D. Efficiency ranking

Ranked by percentage points of >1 ATR tail removed per basis point of expectancy surrendered.

| Rank | Rule | Cost vs no stop | Tail cut (pp) | **pp per bp** | Remaining severity | Overshoot drag | Overshoot as % of cost |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | 5. ATR −1.0 | −4.0 | 3.55 | **0.88** | -261 bps | -0.2 | 5% |
| 2 | 4. ATR −0.5 | −8.2 | 4.61 | **0.56** | none left | -0.5 | 6% |
| 3 | 2. Gap Level | −0.3 | 0.12 | **0.49** | -340 bps | -2.0 | 809% |
| 4 | 7. AVWAP prior close | −3.4 | 1.00 | **0.30** | -331 bps | -11.1 | 330% |
| 5 | 6. AVWAP 09:30 | −12.3 | 3.51 | **0.28** | -308 bps | -28.7 | 233% |
| 6 | 3. Opening Range | −3.9 | 0.82 | **0.21** | -312 bps | -8.5 | 216% |

A value above 100% in the last column means the overshoot drag exceeds the rule's whole net cost — the stop's timing is adding value and its fills are giving back more than all of it. Those are the four close-confirmed rules, and the counterfactual table above is the same fact stated the other way round.

**5. ATR −1.0 is the most efficient tail-control instrument tested** — 3.55 percentage points of >1 ATR losses removed for 4.0 bps of expectancy, with only 0.2 bps lost to fill quality.

### Overall assessment

| Rule | Verdict |
|---|---|
| 1. No stop | **Highest expectancy (+30.4 bps).** Carries the full tail: 4.61% of trades lose more than 1 ATR, dragging 16.0 bps/trade. The right default unless a loss cap is mandated. |
| 2. Gap Level | **Poor value.** Costs 0.3 bps to remove 0.12 pp of the >1 ATR tail, leaving the rest averaging -340 bps. Overshoots 29 bps (0.10 ATR) per stop, a drag of 2.0 bps/trade — more than its whole net cost, so it would beat holding on perfect fills. |
| 3. Opening Range | **Worst value.** Costs 3.9 bps to remove 0.82 pp of the >1 ATR tail, leaving the rest averaging -312 bps. Overshoots 37 bps (0.13 ATR) per stop, a drag of 8.5 bps/trade — more than its whole net cost, so it would beat holding on perfect fills. |
| 4. ATR −0.5 | **Reasonable value.** Costs 8.2 bps to remove 4.61 pp of the >1 ATR tail, eliminating it entirely. Overshoots 1 bps (0.01 ATR) per stop, only 6% of its cost. |
| 5. ATR −1.0 | **Best value.** Costs 4.0 bps to remove 3.55 pp of the >1 ATR tail, leaving the rest averaging -261 bps. Overshoots 2 bps (0.01 ATR) per stop, only 5% of its cost. |
| 6. AVWAP 09:30 | **Worst value.** Costs 12.3 bps to remove 3.51 pp of the >1 ATR tail, leaving the rest averaging -308 bps. Overshoots 37 bps (0.14 ATR) per stop, a drag of 28.7 bps/trade — more than its whole net cost, so it would beat holding on perfect fills. |
| 7. AVWAP prior close | **Worst value.** Costs 3.4 bps to remove 1.00 pp of the >1 ATR tail, leaving the rest averaging -331 bps. Overshoots 27 bps (0.10 ATR) per stop, a drag of 11.1 bps/trade — more than its whole net cost, so it would beat holding on perfect fills. |

## The decision

**Nothing beats holding on expectancy.** The baseline is +30.4 bps and every stop costs 0.3 to 12.3 bps. The choice is therefore not "which stop makes money" but "what am I buying, and is it worth the price".

| If your constraint is… | Use | Why |
|---|---|---|
| Maximum expectancy | **1. No stop** | +30.4 bps, the highest of any rule |
| Best risk reduction per bp spent | **5. ATR −1.0** | 0.88 pp of tail per bp, and the smallest overshoot of any rule |
| A hard cap on per-trade loss | **4. ATR −0.5** | the only rule that eliminates >1 ATR losses entirely, for 8.2 bps |
| A stop that barely interferes | **2. Gap Level** | 0.3 bps, but it removes only 0.12 pp of tail — near-free because near-inactive |

**What this analysis adds to the earlier ones.** Two things, and they point in opposite directions.

The first is a mark *against* the confirmed rules: they cannot promise a loss cap at all. Their fill is wherever the bar closed, so the >1 ATR tail survives — Gap Level still carries the full 1,140 bps worst case, identical to no stop. If a stop exists to bound per-trade loss, only the intrabar ATR rules deliver that, and only ATR −0.5 delivers it absolutely.

The second is a mark *for* them, and it was invisible until fill quality was measured: the levels themselves are good. Every confirmed rule would beat holding on perfect fills. Their weakness is not where they exit but how late — which makes an intrabar version of the same levels the obvious next test, and the one thing this series has not yet run.

## Reading notes

- **Costs are flat 6.6 bps for every rule and every trade.** A stop firing into fast tape pays more, so every stop rule is flattered relative to holding, and the tighter/more active the stop the more it is flattered.
- **Overshoot here is measured against the rule's own intended level**, not against a theoretical best fill. It excludes spread and queue effects entirely, so it is a floor on real-world slippage, not an estimate of it.
- **The AVWAP prior-close anchor carries a judgement call** (the seed weight), documented and stress-tested in `LOSS_REPORT.md`. Its figures should be read as one point on that curve.
- **All seven rules run on one sample**, so this is a comparison under identical conditions, not seven independent tests.
- **No rule here was fitted.** Every level is a convention chosen in advance.

---

_Reproducible from `lambda_strategy_validation/stopsummary.py`; tables in `lambda_data/tables/sum_*.csv`._