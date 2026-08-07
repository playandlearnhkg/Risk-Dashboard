# Lambda — Structural Stop-Loss Rules on the Post-Earnings Continuation Setup

Post-earnings T+1, High Volume + Continuation (non-doji), entry at the open of the 09:35 bar, exit at 1 hour (10:35) if no stop triggers. Price-structure levels rather than the volatility-scaled ATR stops in `STOPS_REPORT.md`.

| Input | Definition |
|---|---|
| Universe | Post-earnings T+1, 2015-01-27 → 2025-12-19 |
| Cohort | 4,906 events — identical to the ATR stop reports, built by the same code |
| Rule 1 | long: close below the 09:30–09:35 **low**; short: close above its **high** |
| Rule 2 | long: close below the **prior day's close**; short: close above it |
| Rule 3 | whichever of rule 1 or rule 2 triggers first |
| Confirmation | the **5-minute close** only — 12 checkpoints, 09:40 through 10:35 |
| Exit price | the confirming 5-minute close |
| Costs | 6.6 bps round trip |

> **These are not comparable to the ATR stops on stop-out rate.** An ATR stop fires on the first intrabar touch; these fire only if a 5-minute bar *closes* beyond the level, so an intrabar poke that closes back inside does nothing. The flip side is that a confirmed break can fill well past its level — price is under no obligation to sit on the line when the bar closes — so a structural stop **cannot cap the loss at its own distance** the way a tight ATR stop can.

## 1. Results

| Rule | n | % stopped | Win rate | Avg Win | Avg Loss | Payoff | **NET** | Median | p10 | % realised loss > 1 ATR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Rule 1 — Opening Range | 4,906 | 22.7% | 55.2% | 157.6 | 121.6 | 1.30 | **+26.5** | +21.2 | -172 | 3.79% |
| Rule 2 — Gap Level | 4,906 | 7.0% | 57.4% | 154.8 | 124.1 | 1.25 | **+30.1** | +27.1 | -169 | 4.48% |
| Rule 3 — Combined | 4,906 | 23.2% | 55.0% | 157.8 | 120.7 | 1.31 | **+26.5** | +21.0 | -171 | 3.77% |
| Baseline — no stop | 4,906 | — | 58.2% | 153.6 | 126.9 | 1.21 | **+30.4** | +28.7 | -172 | 4.61% |

All figures in basis points. NET is mean expectancy per trade after 6.6 bps.

| Rule | NET | vs no stop | Median | vs no stop | p10 | vs no stop |
|---|---:|---:|---:|---:|---:|---:|
| Rule 1 — Opening Range | +26.5 | **-3.9** | +21.2 | -7.5 | -172 | -0 |
| Rule 2 — Gap Level | +30.1 | **-0.3** | +27.1 | -1.6 | -169 | +3 |
| Rule 3 — Combined | +26.5 | **-3.9** | +21.0 | -7.7 | -171 | +1 |

**No structural rule beats holding.** All 3 cost expectancy; the least damaging (Gap Level) gives up 0.3 bps. That is the same verdict the ATR ladder reached, now from levels that carry actual chart meaning rather than a volatility multiple.

## 2. Where these levels actually sit

The whole point of a structural stop is that its distance is set by the chart, not by volatility. This is what that distance turned out to be:

| Rule | Median distance (ATR) | p25 | p75 | Median distance (bps) | Level already breached at entry | Mean stop minute |
|---|---:|---:|---:|---:|---:|---:|
| Rule 1 — Opening Range | 0.54 | 0.33 | 0.86 | 137 | 0.2% | 28 |
| Rule 2 — Gap Level | 1.16 | 0.61 | 2.34 | 295 | 0.0% | 34 |
| Rule 3 — Combined | 0.52 | 0.32 | 0.85 | 134 | 0.2% | 28 |

**Rule 1 is a tight stop and rule 2 is a wide one.** The opening range sits 0.54 ATR from entry at the median — comparable to the 0.5 ATR rung of the ATR ladder — while the gap level sits 1.16 ATR away, wider than anything tested there. They are not two variants of one idea; they are stops at opposite ends of the range, and their results should be read that way.

## 3. Where the expectancy goes

| Rule | Trades stopped | Realised | Would have made | **Forgone** | % that would have recovered to profit |
|---|---:|---:|---:|---:|---:|
| Rule 1 — Opening Range | 1,113 | -162.9 | -145.7 | **+17.3** | 13.1% |
| Rule 2 — Gap Level | 342 | -153.9 | -150.3 | **+3.6** | 10.8% |
| Rule 3 — Combined | 1,137 | -159.8 | -143.0 | **+16.7** | 13.6% |

Every rule forgoes return on the trades it cuts. For Opening Range, 13% of the stopped trades would have finished the hour in profit and the group would have returned -145.7 bps against the -162.9 realised. The mechanism is identical to the ATR case: adverse excursions in this cohort are mostly temporary, and any stop inside that noise band converts round-trips into permanent losses.

## 4. Do they at least control the tail?

| Rule | % realised loss > 1 ATR | Median overshoot past the level | p10 | Std dev |
|---|---:|---:|---:|---:|
| Rule 1 — Opening Range | 3.79% | 0.09 ATR | -172 | 236 |
| Rule 2 — Gap Level | 4.48% | 0.07 ATR | -169 | 239 |
| Rule 3 — Combined | 3.77% | 0.09 ATR | -171 | 236 |
| Baseline — no stop | 4.61% | — | -172 | 240 |

The structural rules do reduce the >1 ATR loss rate below the no-stop baseline.

## 5. Fill robustness — you cannot trade the close you just saw

Re-pricing every stop exit at the **next minute's open** instead of the confirming close:

| Rule | NET at close | NET at next open | Difference |
|---|---:|---:|---:|
| Rule 1 — Opening Range | +26.5 | +26.4 | -0.0 |
| Rule 2 — Gap Level | +30.1 | +30.2 | +0.0 |
| Rule 3 — Combined | +26.5 | +26.5 | -0.0 |

**The convention makes no difference at all** — every rule moves by less than 0.1 bps, in both directions. That is worth knowing rather than assuming: on a 5-minute confirmation the next minute's open is close enough to the confirming close that the choice between them is immaterial, so none of the results above rests on being able to trade a price at the instant it prints.

## 6. Verdict

| Stop family | Best rule tested | NET | vs no stop | Cuts the >1 ATR tail? |
|---|---|---:|---:|---|
| Structural (this report) | Gap Level | +30.1 | -0.3 | yes |
| ATR, tight (`STOPS_TIGHT_REPORT.md`) | −0.5 ATR | +22.2 | −8.2 | yes, to 0.00% |
| ATR, loose (`STOPS_REPORT.md`) | −2.0 ATR | +30.0 | −0.4 | no |
| **None** | hold to 1 hour | **+30.4** | — | — |

Across three families and eleven separate rules, **nothing beats holding to the hour on expectancy.** But the structural rules are not the worst of the three families, and one of them is close to free.

**Rule 2 — Gap Level costs only 0.3 bps** — the cheapest stop of any kind tested in this series, and within noise of free. It stops 7.0% of trades, trims the >1 ATR loss rate from 4.61% to 4.48%, and improves p10 slightly (-169 against -172). If a stop is required for mandate or psychological reasons, this is the one that costs least — though what it mostly demonstrates is that a stop far enough away to be nearly free is also nearly inactive.

### The finding worth keeping: confirmation beats immediacy

Rule 1 sits 0.54 ATR from entry at the median — essentially the same distance as the −0.5 ATR rung of the ATR ladder. The two rules differ almost only in *how* they trigger:

| | −0.5 ATR (intrabar touch) | Rule 1 (5-min close) |
|---|---:|---:|
| Median stop distance | 0.50 ATR | 0.54 ATR |
| % stopped | 34.1% | 22.7% |
| NET | +22.2 | +26.5 |
| Cost vs holding | -8.2 | -3.9 |
| Median | +3.9 | +21.2 |

**At the same distance, requiring a 5-minute close cuts the stop-out rate by a third and halves the cost** (3.9 bps against 8.2). The trades saved are the ones that poked through the level intrabar and closed back inside — exactly the temporary excursions the attribution table keeps identifying. If a stop is going to be used on this setup, confirming it on a bar close is worth more than any amount of tuning the distance.

Two caveats on that comparison. Rule 1's distance is a distribution (p25 0.33, p75 0.86 ATR), not a constant, so this is not a perfectly controlled experiment — only the medians line up. And confirmation is not free in the other direction: it gives up the hard loss cap, which is why rule 1 leaves 3.79% of trades losing more than 1 ATR where the intrabar 0.5 ATR stop left 0.00%.

## 7. Reading notes

- **Close-confirmation is doing a lot of work here.** An intrabar version of the same levels would stop out far more often and cap losses far better. That is a different rule, and the specification asked for the confirmed version.
- **Rule 3 is close to rule 1 by construction.** The opening range is the nearer level on most events, so the combined rule fires on the opening range first the large majority of the time and the gap level rarely adds anything.
- **Costs are charged identically to stopped and held trades**, so every stop rule is flattered relative to holding.
- **No level was fitted.** These are the levels the specification named, tested once.

---

_Reproducible from `lambda_strategy_validation/structstops.py`; tables in `lambda_data/tables/struct_*.csv`._