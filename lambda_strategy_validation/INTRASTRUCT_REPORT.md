# Lambda — Intrabar Structural Stops Over the Full Holding Period

Post-earnings T+1, High Volume + Continuation (non-doji), entry at the open of the 09:35 bar, exit at 10:35 if no stop triggers. The same structural levels as `STRUCTSTOPS_REPORT.md`, now triggered on the first intrabar touch rather than on a 5-minute close.

| Input | Definition |
|---|---|
| Universe | Post-earnings T+1, 2015-01-27 → 2025-12-19 |
| Cohort | 4,906 events |
| Rule 1 | first touch beyond the 09:30–09:35 candle's **low** (long) / **high** (short) |
| Rule 2 | first touch beyond the **prior day's close** |
| Rule 3 | first touch of whichever level is nearer |
| Fill | the level, or the bar's **open** if it opened through |
| ATR | prior-session ATR(14) |
| Costs | 6.6 bps round trip |

## 1. Results — intrabar trigger

| Rule | % stopped | **NET** | Avg Win | Avg Loss | Payoff | % loss > 1 ATR | Avg loss > 1 ATR | Avg overshoot | Median overshoot | Worst overshoot |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1. Opening Range | 30.7% | **+23.9** | 160.9 | 108.2 | 1.49 | 2.77% | -291 bps | 1.4 bps | 0.0 bps | 84 bps |
| 2. Gap Level | 9.5% | **+29.1** | 155.6 | 121.4 | 1.28 | 4.38% | -339 bps | 2.1 bps | 0.0 bps | 140 bps |
| 3. Combined | 31.6% | **+23.4** | 161.4 | 106.7 | 1.51 | 2.75% | -292 bps | 1.4 bps | 0.0 bps | 140 bps |
| **4. No stop (baseline)** | — | **+30.4** | 153.6 | 126.9 | 1.21 | 4.61% | -348 bps | — | — | — |

Overshoot is the intended level minus the realised fill, in the adverse direction; it can only be non-zero when a bar opened through the level.

## 2. Intrabar versus close-confirmed, same levels

| Rule | Trigger | % stopped | NET | % loss > 1 ATR | Avg overshoot | Overshoot drag |
|---|---|---:|---:|---:|---:|---:|
| 1. Opening Range | intrabar | 30.7% | +23.9 | 2.77% | 1.4 bps | -0.4 bps |
| 1. Opening Range | 5-min close | 22.7% | +26.5 | 3.79% | 37.4 bps | -8.5 bps |
| 2. Gap Level | intrabar | 9.5% | +29.1 | 4.38% | 2.1 bps | -0.2 bps |
| 2. Gap Level | 5-min close | 7.0% | +30.1 | 4.48% | 29.1 bps | -2.0 bps |
| 3. Combined | intrabar | 31.6% | +23.4 | 2.75% | 1.4 bps | -0.5 bps |
| 3. Combined | 5-min close | 23.2% | +26.5 | 3.77% | 37.5 bps | -8.7 bps |

**Fill quality improves enormously, and it does not save the rules.** Moving to an intrabar trigger cuts average overshoot from 37→1.4 bps, 29→2.1 bps, 38→1.4 bps — a 20-to-30-fold improvement — because the stop now exits at its level instead of wherever the bar happened to close.

## 3. The prediction from the last report, tested

`STOPSUMMARY_REPORT.md` observed that adding each confirmed rule's overshoot back to its NET would put it ahead of holding, and suggested an intrabar version "would capture most of that gap". That was my inference, and it was wrong. Here it is against the data:

| Rule | Confirmed NET | Overshoot added back → predicted | **Actual intrabar NET** | Miss |
|---|---:|---:|---:|---:|
| 1. Opening Range | +26.5 | +34.9 | **+23.9** | -11.1 |
| 2. Gap Level | +30.1 | +32.2 | **+29.1** | -3.1 |
| 3. Combined | +26.5 | +35.2 | **+23.4** | -11.8 |

**The intrabar versions come in 3.1 to 11.8 bps below the counterfactual**, not close to it. The flaw in the inference was holding the stopped set fixed: the add-back asked what the *same* stops would have earned at better prices, but an intrabar trigger does not stop the same trades. It fires on every temporary poke through the level, so it stops far more of them:

| Rule | % stopped, confirmed | % stopped, intrabar | Increase |
|---|---:|---:|---:|
| 1. Opening Range | 22.7% | 30.7% | **+8.0 pp** |
| 2. Gap Level | 7.0% | 9.5% | **+2.6 pp** |
| 3. Combined | 23.2% | 31.6% | **+8.4 pp** |

Better fills on many more stops is a different trade from better fills on the same stops. The extra trades caught are exactly the ones that dipped through the level and recovered — the temporary excursions every report in this series keeps identifying — and cutting them costs more than the improved fills save.

## 4. Against holding

| Rule | Trigger | NET | vs no stop | % loss > 1 ATR | vs no stop |
|---|---|---:|---:|---:|---:|
| 1. Opening Range | intrabar | +23.9 | **-6.5** | 2.77% | -1.83 pp |
| 1. Opening Range | 5-min close | +26.5 | **-3.9** | 3.79% | -0.82 pp |
| 2. Gap Level | intrabar | +29.1 | **-1.3** | 4.38% | -0.22 pp |
| 2. Gap Level | 5-min close | +30.1 | **-0.3** | 4.48% | -0.12 pp |
| 3. Combined | intrabar | +23.4 | **-7.0** | 2.75% | -1.85 pp |
| 3. Combined | 5-min close | +26.5 | **-3.9** | 3.77% | -0.84 pp |
| **4. No stop (baseline)** | — | **+30.4** | — | 4.61% | — |

**No intrabar structural rule beats holding either.** The best of them (2. Gap Level) gives up 1.3 bps. Across every stop family tried in this series — ATR from entry, time-delayed ATR, structural on a confirmed close, structural intrabar, and anchored VWAP — holding to the hour still wins on expectancy.

On the efficiency measure used in `STOPSUMMARY_REPORT.md` — percentage points of >1 ATR tail removed per bp of expectancy surrendered:

| Rule | Trigger | Cost | Tail cut (pp) | **pp per bp** |
|---|---|---:|---:|---:|
| 2. Gap Level | 5-min close | −0.3 | 0.12 | **0.49** |
| 1. Opening Range | intrabar | −6.5 | 1.83 | **0.28** |
| 3. Combined | intrabar | −7.0 | 1.85 | **0.27** |
| 3. Combined | 5-min close | −3.9 | 0.84 | **0.22** |
| 1. Opening Range | 5-min close | −3.9 | 0.82 | **0.21** |
| 2. Gap Level | intrabar | −1.3 | 0.22 | **0.17** |

The best structural variant on this measure is **2. Gap Level (5-min close)** at 0.49 pp per bp — still short of the 0.88 that the intrabar ATR −1.0 stop achieves, which remains the most efficient tail-control instrument found anywhere in this series.

## 5. What the intrabar trigger did deliver

| Rule | Trigger | % loss > 1 ATR | Avg loss > 1 ATR | Worst loss | Drag from >1 ATR losses |
|---|---|---:|---:|---:|---:|
| 1. Opening Range | 5-min close | 3.79% | -312 bps | -791 bps | -11.8 bps |
| 1. Opening Range | intrabar | 2.77% | -291 bps | -730 bps | -8.1 bps |
| 2. Gap Level | 5-min close | 4.48% | -340 bps | -1,140 bps | -15.3 bps |
| 2. Gap Level | intrabar | 4.38% | -339 bps | -1,140 bps | -14.9 bps |
| 3. Combined | 5-min close | 3.77% | -311 bps | -791 bps | -11.7 bps |
| 3. Combined | intrabar | 2.75% | -292 bps | -730 bps | -8.0 bps |
| **4. No stop (baseline)** | — | 4.61% | -348 bps | -1,140 bps | -16.0 bps |

This is where the intrabar trigger does earn something. Every rule cuts both the frequency and the average severity of >1 ATR losses relative to its confirmed twin, and the drag falls with it.

**But it does not deliver a bounded loss, and that is worth being precise about.** 2. Gap Level still carries a worst case of 1,140 bps — identical to no stop at all. A structural level only caps a loss if price actually reaches it, and on a large gap the prior close can sit further away than the entire adverse move. The worst trade in this cohort never traded down to its gap level; it simply lost money without ever triggering the stop.

That is the difference between a structural stop and an ATR stop in one sentence: an ATR stop is defined by *distance*, so it always binds; a structural stop is defined by a *price*, so it binds only when the chart cooperates. Only 1. Opening Range, 3. Combined improved the worst case at all, and only from 791 to 730 bps.

## 6. Reading notes

- **The correction in section 3 is the main result.** An add-back counterfactual that holds the stopped set fixed is an upper bound on a different rule, not a forecast of the rule you would actually run. I drew that inference in the previous report and it did not survive the test.
- **Costs are flat 6.6 bps** and identical for stopped and held trades, so every stop rule here is flattered relative to holding — and the intrabar rules, which stop far more often, most of all.
- **No intrabar path within the minute.** If a bar's low breaches the level and its high also runs favourably, this test assumes the stop fired. Correct for a stop-only study, and conservative.
- **Nothing here was fitted.** Both levels are read directly off the chart with no free parameter.

---

_Reproducible from `lambda_strategy_validation/intrastruct.py`; tables in `lambda_data/tables/instr_*.csv`._