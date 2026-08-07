# Lambda — Path Dependence of High Volume + Continuation Trades

Post-earnings T+1. How the trade evolves conditional on whether it was up or down at the 5-minute mark (09:40).

| Input | Definition |
|---|---|
| Universe | Post-earnings T+1, 2015-01-27 → 2025-12-22 |
| Setup | High Volume + Continuation |
| Continuation | 09:30–09:35 candle closes **with** the gap |
| High Volume | `c1_volume` > 1.5× trailing 20-session mean, same ticker, same 09:30–09:35 slot, shifted one session |
| Entry | Open of the 09:35 bar |
| Costs | 6.6 bps round trip, in NET only |
| Inference | date-clustered bootstrap; ⚠ marks n < 150 |
| Conditioning point | Return from entry to the 09:40 close |

Of **4,870** classified trades, **2,840 (58.3%)** were profitable at 09:40 and **2,030** were losing. Mean 5-minute return: **+72.0 bps** for the winners, **-66.2 bps** for the losers.

> **Why there are two "subsequent return" columns.** Splitting on the sign of the 09:40 return and then measuring the move *from that same 09:40 print* shares one price between the classifier and the outcome. Noise in that print — a trade at the offer rather than the bid — enters the classification positively and the subsequent return negatively, manufacturing mean reversion out of nothing. **`sub (09:40)`** has that contamination; **`sub (09:41 open)`** measures from the next print, so classifier and outcome share no price. The gap between the two columns *is* the artefact. Only the second supports a claim about what actually happens next.

## 1. The two groups at later horizons

| Group | Horizon | n | % profitable | % profitable net | Win rate | Mean (from entry) | Median | sub (09:40) | **sub (09:41 open)** |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 10 min (09:45) | 2,821 | 82.5% | 79.8% | 82.5% | +78.2 | +61.5 | +5.8 | **+6.1** |
| A | 15 min (09:50) | 2,826 | 79.1% | 77.0% | 79.1% | +86.0 | +68.4 | +13.7 | **+14.8** |
| A | 1 hour (10:35) | 2,824 | 70.5% | 68.9% | 70.5% | +90.3 | +69.4 | +18.0 | **+19.2** |
| | | | | | | | | | |
| B | 10 min (09:45) | 2,015 | 25.8% | 22.7% | 25.8% | -57.2 | -39.5 | +9.1 | **+8.7** |
| B | 15 min (09:50) | 2,013 | 33.4% | 30.8% | 33.4% | -46.5 | -33.7 | +19.9 | **+19.6** |
| B | 1 hour (10:35) | 2,017 | 41.6% | 39.8% | 41.6% | -36.5 | -26.7 | +29.8 | **+30.1** |
| | | | | | | | | | |
| All | 10 min (09:45) | 4,836 | 58.9% | — | 58.9% | +21.8 | +19.3 | — | — |
| All | 15 min (09:50) | 4,839 | 60.1% | — | 60.1% | +30.9 | +25.7 | — | — |
| All | 1 hour (10:35) | 4,841 | 58.5% | — | 58.5% | +37.5 | +29.5 | — | — |

**% profitable** = cumulative return from entry above zero. **% profitable net** = above 6.6 bps, i.e. actually worth having exited into. **Win rate** is the same quantity as % profitable — the request listed them separately, so the net-of-cost version is given as the distinct third measure. **sub** columns are the mean return from the 5-minute mark onward.

## 2. Transition rates — the headline question

| From 09:40 status | To horizon | % profitable | % profitable net |
|---|---|---:|---:|
| **Losers** that became winners | 10 min (09:45) | 25.8% | 22.7% |
| **Losers** that became winners | 15 min (09:50) | 33.4% | 30.8% |
| **Losers** that became winners | 1 hour (10:35) | 41.6% | 39.8% |
| **Winners** that stayed winners | 10 min (09:45) | 82.5% | 79.8% |
| **Winners** that stayed winners | 15 min (09:50) | 79.1% | 77.0% |
| **Winners** that stayed winners | 1 hour (10:35) | 70.5% | 68.9% |

- **33.4%** of 5-minute losers are profitable at 15 minutes; **41.6%** at 1 hour.
- **79.1%** of 5-minute winners are still profitable at 15 minutes; **70.5%** at 1 hour.

## 3. Average subsequent move, winners vs losers at 09:40

| Horizon | Group | sub from 09:40 | sub from 09:41 open | Artefact | p (09:41) | 95% CI (09:41) |
|---|---|---:|---:|---:|---:|---:|
| 10 min (09:45) | A | +5.8 | **+6.1** | -0.3 | 0.000 | [+3.2, +9.2] |
| 10 min (09:45) | B | +9.1 | **+8.7** | +0.5 | 0.000 | [+4.7, +12.4] |
| 15 min (09:50) | A | +13.7 | **+14.8** | -1.1 | 0.000 | [+10.5, +18.7] |
| 15 min (09:50) | B | +19.9 | **+19.6** | +0.3 | 0.000 | [+15.0, +24.3] |
| 1 hour (10:35) | A | +18.0 | **+19.2** | -1.2 | 0.000 | [+10.6, +28.6] |
| 1 hour (10:35) | B | +29.8 | **+30.1** | -0.3 | 0.000 | [+21.6, +38.1] |

**The artefact is small.** It runs -1.2 to +0.5 bps — at most 1.2 bps against subsequent moves of 6 to 30 bps — and points in the direction bid-ask bounce predicts in 5 of 6 cells (contaminated column too low for winners, too high for losers). So the shared-print contamination is real but does not drive any conclusion here. Every statement below uses the 09:41 column regardless.

- **10 min (09:45)**: winners go on to make +6.1 bps (p=0.000), losers +8.7 bps (p=0.000) — a gap of **-2.6 bps** in favour of the losers.
- **15 min (09:50)**: winners go on to make +14.8 bps (p=0.000), losers +19.6 bps (p=0.000) — a gap of **-4.8 bps** in favour of the losers.
- **1 hour (10:35)**: winners go on to make +19.2 bps (p=0.000), losers +30.1 bps (p=0.000) — a gap of **-10.9 bps** in favour of the losers.

## 4. The size of the 5-minute move, not just its sign

Quartile cut at -32 and +63 bps.

| Horizon | 09:40 bucket | n | Mean at 09:40 | Mean from entry | % profitable | sub (09:41 open) | p |
|---|---|---:|---:|---:|---:|---:|---:|
| 10 min (09:45) | Losing, worse than p25 | 1,211 | -100.2 | -89.0 | 15.7% | +10.7 | 0.000 |
| 10 min (09:45) | Losing, mild | 804 | -15.2 | -9.3 | 41.0% | +5.6 | 0.017 |
| 10 min (09:45) | Winning, mild | 1,604 | +28.9 | +37.0 | 76.5% | +7.7 | 0.000 |
| 10 min (09:45) | Winning, better than p75 | 1,217 | +129.4 | +132.5 | 90.4% | +4.0 | 0.164 |
| 15 min (09:50) | Losing, worse than p25 | 1,213 | -100.2 | -76.5 | 24.4% | +23.7 | 0.000 |
| 15 min (09:50) | Losing, mild | 800 | -15.2 | -1.1 | 47.1% | +13.5 | 0.000 |
| 15 min (09:50) | Winning, mild | 1,611 | +28.9 | +40.8 | 72.4% | +12.4 | 0.000 |
| 15 min (09:50) | Winning, better than p75 | 1,215 | +129.4 | +145.9 | 88.0% | +18.0 | 0.000 |
| 1 hour (10:35) | Losing, worse than p25 | 1,212 | -100.2 | -63.9 | 36.3% | +37.0 | 0.000 |
| 1 hour (10:35) | Losing, mild | 805 | -15.2 | +4.7 | 49.7% | +19.6 | 0.001 |
| 1 hour (10:35) | Winning, mild | 1,609 | +28.9 | +39.3 | 64.4% | +11.4 | 0.001 |
| 1 hour (10:35) | Winning, better than p75 | 1,215 | +129.4 | +157.8 | 78.4% | +29.5 | 0.008 |

## 5. What this means for the trade

**The 5-minute mark tells you where the trade stands, not where it is going.** The two groups are already +138.3 bps apart at 09:40. An hour later they are +126.8 bps apart — the gap has *narrowed* by 11.4 bps, because the losers close ground faster than the winners extend. Measured cleanly from 09:41 onward the two groups differ by only **-10.9 bps**, against the +138.3 bps of separation that was already banked before the decision point.

In other words, roughly 91% of the gap between winners and losers at 1 hour was already determined in the first five minutes. Knowing a trade is up at 09:40 tells you a great deal about where it sits and comparatively little about what it does next.

- Group A (winning at 09:40) continues to make money from 09:41 to 10:35: +19.2 bps, p = 0.000, 95% CI [+10.6, +28.6].
- Group B (losing at 09:40) continues to make money from 09:41 to 10:35: +30.1 bps, p = 0.000, 95% CI [+21.6, +38.1].

### Losers recover faster than winners extend

**Both groups make money from 09:41 onward — but the losing group makes more** (+30.1 vs +19.2 bps to 1 hour, both p < 0.001). The continuation edge does not stop working for trades that start badly; if anything it works harder on them.

Section 4 sharpens this: the **worst** 5-minute losers — averaging -100 bps down at 09:40 — go on to make **+37.0 bps** from 09:41 to 10:35, the largest subsequent move of any bucket. They still end the hour at -64 bps cumulative, so this is a partial recovery, not a round trip to profit.

**The practical implication cuts against a stop-loss at the 5-minute mark.** Cutting the losers at 09:40 would realise an average -66.2 bps and forgo an expected +30.1 bps of recovery. That is not an argument for holding losers indefinitely — it is an argument that 5 minutes is too early to judge this particular setup, which is consistent with the whole edge being a slow repricing rather than an instant one.

**Caveats.**

- This is a *conditional description*, not a tradeable rule. Acting on it means a second decision at 09:40 — cutting losers or adding to winners — and that second trade pays its own spread, which is not modelled anywhere here.
- The groups are defined by an outcome, so both are selected samples. The unconditional row in section 1 is the only line that describes a decision you could make at entry.
- The 09:41-open reference removes the shared-print artefact but not all microstructure: a trade classified as winning at 09:40 is more likely to have been marked at the offer, and the next print inherits some of that. The artefact column is a floor on the bias, not a complete correction.

---

_Reproducible from `lambda_strategy_validation/longhold_path.py`; tables in `lambda_data/tables/lp_path.csv`, `lp_transition.csv`, `lp_by_magnitude.csv`._