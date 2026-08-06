# Lambda — Market Cap and the Post-Earnings Edge

Post-earnings (T+1) continuation only, 2015-01-07 → 2025-12-22. **6,484** continuation events of 14,975 with a usable 09:35 price. Net subtracts 6.6 bps. p-values two-sided from a date-clustered bootstrap. Cells with n < 150 are flagged ⚠.

| Input | Definition |
|---|---|
| Signal | 09:30–09:35 candle closes in the gap direction |
| Entry | Open of the 09:35 bar |
| Market cap | Prior-session value |
| Holds | 5 min = 09:40 · 15 min = 09:50 · 1 hour = 10:35 |

## 1. Market cap groups

| Window | Market cap | n | Win rate | Gross | **NET** | net p |
|---|---|---:|---:|---:|---:|---:|
| 5 min (09:40) | All Continuation | 6,346 | 57.6% | +11.9 | **+5.3** | 0.000 |
| 5 min (09:40) | $3B - $10B | 927 | 60.1% | +20.2 | **+13.6** | 0.000 |
| 5 min (09:40) | $10B - $50B | 3,439 | 57.6% | +11.1 | **+4.5** | 0.001 |
| 5 min (09:40) | > $50B | 1,980 | 56.3% | +9.6 | **+3.0** | 0.062 |
| 15 min (09:50) | All Continuation | 6,428 | 58.6% | +24.8 | **+18.2** | 0.000 |
| 15 min (09:50) | $3B - $10B | 936 | 60.6% | +42.5 | **+35.9** | 0.000 |
| 15 min (09:50) | $10B - $50B | 3,493 | 58.1% | +23.4 | **+16.8** | 0.000 |
| 15 min (09:50) | > $50B | 1,999 | 58.5% | +18.9 | **+12.3** | 0.000 |
| 1 hour (10:35) | All Continuation | 6,448 | 57.0% | +28.1 | **+21.5** | 0.000 |
| 1 hour (10:35) | $3B - $10B | 937 | 60.5% | +57.1 | **+50.5** | 0.000 |
| 1 hour (10:35) | $10B - $50B | 3,506 | 57.2% | +27.5 | **+20.9** | 0.000 |
| 1 hour (10:35) | > $50B | 2,005 | 55.2% | +15.5 | **+8.9** | 0.007 |

## 2. Market cap × Gap/ATR

| Window | Market cap | Gap/ATR | n | Win rate | **NET** | net p |
|---|---|---|---:|---:|---:|---:|
| 5 min (09:40) | $3B - $10B | Gap/ATR < 1.0 | 662 | 61.2% | **+13.3** | 0.000 |
| 5 min (09:40) | $3B - $10B | Gap/ATR 1.0-2.0 ⚠ | 111 | 55.9% | **+2.6** | 0.852 |
| 5 min (09:40) | $3B - $10B | Gap/ATR > 2.0 | 154 | 58.4% | **+23.1** | 0.073 |
| 5 min (09:40) | $10B - $50B | Gap/ATR < 1.0 | 2,591 | 58.2% | **+3.9** | 0.017 |
| 5 min (09:40) | $10B - $50B | Gap/ATR 1.0-2.0 | 400 | 50.7% | **-2.4** | 0.639 |
| 5 min (09:40) | $10B - $50B | Gap/ATR > 2.0 | 448 | 60.3% | **+14.1** | 0.035 |
| 5 min (09:40) | > $50B | Gap/ATR < 1.0 | 1,399 | 56.5% | **+3.9** | 0.005 |
| 5 min (09:40) | > $50B | Gap/ATR 1.0-2.0 | 255 | 53.3% | **-3.8** | 0.484 |
| 5 min (09:40) | > $50B | Gap/ATR > 2.0 | 326 | 58.0% | **+4.5** | 0.398 |
| 15 min (09:50) | $3B - $10B | Gap/ATR < 1.0 | 670 | 61.0% | **+34.6** | 0.000 |
| 15 min (09:50) | $3B - $10B | Gap/ATR 1.0-2.0 ⚠ | 111 | 55.0% | **+13.4** | 0.446 |
| 15 min (09:50) | $3B - $10B | Gap/ATR > 2.0 | 155 | 62.6% | **+57.8** | 0.008 |
| 15 min (09:50) | $10B - $50B | Gap/ATR < 1.0 | 2,643 | 58.3% | **+15.0** | 0.000 |
| 15 min (09:50) | $10B - $50B | Gap/ATR 1.0-2.0 | 400 | 54.5% | **+12.3** | 0.074 |
| 15 min (09:50) | $10B - $50B | Gap/ATR > 2.0 | 450 | 60.0% | **+31.3** | 0.000 |
| 15 min (09:50) | > $50B | Gap/ATR < 1.0 | 1,415 | 59.2% | **+13.5** | 0.000 |
| 15 min (09:50) | > $50B | Gap/ATR 1.0-2.0 | 257 | 54.5% | **-0.2** | 0.986 |
| 15 min (09:50) | > $50B | Gap/ATR > 2.0 | 327 | 58.7% | **+16.9** | 0.025 |
| 1 hour (10:35) | $3B - $10B | Gap/ATR < 1.0 | 672 | 60.1% | **+39.2** | 0.000 |
| 1 hour (10:35) | $3B - $10B | Gap/ATR 1.0-2.0 ⚠ | 111 | 62.2% | **+56.8** | 0.034 |
| 1 hour (10:35) | $3B - $10B | Gap/ATR > 2.0 | 154 | 61.0% | **+95.1** | 0.000 |
| 1 hour (10:35) | $10B - $50B | Gap/ATR < 1.0 | 2,656 | 56.6% | **+16.4** | 0.000 |
| 1 hour (10:35) | $10B - $50B | Gap/ATR 1.0-2.0 | 400 | 55.5% | **+16.7** | 0.109 |
| 1 hour (10:35) | $10B - $50B | Gap/ATR > 2.0 | 450 | 62.0% | **+51.1** | 0.000 |
| 1 hour (10:35) | > $50B | Gap/ATR < 1.0 | 1,421 | 55.1% | **+9.6** | 0.005 |
| 1 hour (10:35) | > $50B | Gap/ATR 1.0-2.0 | 256 | 50.0% | **-10.5** | 0.290 |
| 1 hour (10:35) | > $50B | Gap/ATR > 2.0 | 328 | 59.8% | **+21.1** | 0.039 |

## 3. What sits inside each market-cap bucket

| Market cap | n | Median Gap/ATR | Median \|Gap\| | < 1.0 | 1.0–2.0 | > 2.0 |
|---|---:|---:|---:|---:|---:|---:|
| $3B - $10B | 945 | 0.39 | 1.41% | 679 | 111 | 155 |
| $10B - $50B | 3,526 | 0.37 | 0.90% | 2,672 | 403 | 451 |
| > $50B | 2,013 | 0.42 | 0.95% | 1,428 | 257 | 328 |

## Key question — does smaller market cap improve the edge?

- **5 min (09:40)**: $3B - $10B +13.6 (60.1%) · $10B - $50B +4.5 (57.6%) · > $50B +3.0 (56.3%) → small minus large **+10.6 bps**
- **15 min (09:50)**: $3B - $10B +35.9 (60.6%) · $10B - $50B +16.8 (58.1%) · > $50B +12.3 (58.5%) → small minus large **+23.6 bps**
- **1 hour (10:35)**: $3B - $10B +50.5 (60.5%) · $10B - $50B +20.9 (57.2%) · > $50B +8.9 (55.2%) → small minus large **+41.6 bps**

**Yes, and monotonically.** Net expectancy falls with size at all three horizons, worth **+10.6 to +41.6 bps** going from > $50B down to $3B–$10B (mean +25.3).

**And it is not only trade size.** The win rate also rises as market cap falls — 5 min (09:40) +3.8 pp, 15 min (09:50) +2.0 pp, 1 hour (10:35) +5.3 pp. That distinguishes this from the general-gap market-cap result, where win rates were flat across buckets and the entire ranking came from bigger moves against a fixed cost. Here small caps both move more *and* go the right way more often, so two independent channels point the same way.

**Is it size, or just what small caps happen to gap like?** Composition does not explain it — the buckets gap very similarly in ATR terms:

$3B - $10B median Gap/ATR 0.39, $10B - $50B median Gap/ATR 0.37, > $50B median Gap/ATR 0.42.

Share of each bucket falling in Gap/ATR > 2.0: $3B - $10B 16.4%, $10B - $50B 12.8%, > $50B 16.3% — the smallest and largest buckets are near-identical on that measure. What does differ is the gap in percentage terms (median $3B - $10B 1.41%, $10B - $50B 0.90%, > $50B 0.95%), which is simply small caps being more volatile — the same quantity ATR already normalises away.

Section 2 is the direct control. Within matched Gap/ATR cells where all three market-cap groups clear the n ≥ 30 floor, small-minus-large is positive in **9 of 9** cells, mean **+31.2 bps**. Size survives holding gap size fixed.

## Does a flat cost assumption manufacture this?

Costs are a single 6.6 bps median across every bucket, and small caps trade wider — so the assumption is least defensible exactly where the result is strongest. That objection can be sized rather than left hanging, using the Roll spread estimates already in the panel:

| Market cap | Median Roll spread | Extra round-trip vs > $50B |
|---|---:|---:|
| $3B - $10B | 3.75 bps | +3.2 bps |
| $10B - $50B | 2.62 bps | +1.0 bps |
| > $50B | 2.13 bps | +0.0 bps |

A round trip crosses the spread twice, so the smallest bucket should carry roughly **3.2 bps** more cost than the largest. Charging that against the small-minus-large deltas:

| Window | Raw delta | Spread-adjusted |
|---|---:|---:|
| 5 min (09:40) | +10.6 | **+7.4** |
| 15 min (09:50) | +23.6 | **+20.4** |
| 1 hour (10:35) | +41.6 | **+38.4** |

**The ranking survives.** The spread differential is real but small next to the effect — it removes roughly 3.2 bps from a gap that runs 11–42 bps, and every horizon stays positive. This is not a cost-assumption artefact.

Two caveats do remain. The Roll estimator is a lower bound on real trading cost — it captures the quoted spread, not impact, and impact scales worse in small caps, so the adjustment above is optimistic. And the universe is survivorship-biased throughout (current index membership), which plausibly hits the smallest bucket hardest, since a $3B name that failed is far more likely to have left the index than a mega cap.

## Comparison with the general-gap universe

Small-minus-large net expectancy, same buckets and holds:

| Window | Post-Earnings | General Gaps |
|---|---:|---:|
| 5 min (09:40) | +10.6 | +1.7 |
| 15 min (09:50) | +23.6 | +5.2 |
| 1 hour (10:35) | +41.6 | +7.0 |

---

_Reproducible from `lambda_strategy_validation/mcap_earnings.py`; tables in `lambda_data/tables/me_*.csv`._