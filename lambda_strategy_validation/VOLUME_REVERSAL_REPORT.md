# Lambda — Volume Confirmation on the Reversal Signal

Same volume test as the Continuation report, applied to the cohort whose first 5-minute candle closes **against** the gap.

| Input | Definition |
|---|---|
| Reversal signal | 09:30–09:35 candle closes **against** the gap direction |
| High Volume | `c1_volume` > 1.5× the trailing 20-session mean of `c1_volume` for the same ticker and the same 09:30–09:35 slot |
| Entry | Open of the 09:35 bar |
| Costs | 6.6 bps round trip, subtracted for NET |

| Universe | Period | Reversal events | % High Volume |
|---|---|---:|---:|
| Post-Earnings (T+1) | 2015-01-27 → 2025-12-22 | 7,794 | 51.1% |
| General Gaps | 2021-01-04 → 2025-12-31 | 55,508 | 23.6% |

> **Sign convention.** Reversal returns are signed in the **candle's** direction — `−sign(gap) × (P_end/P_entry − 1)` — so a positive number means *following the counter-gap candle* paid. Continuation is signed in the gap direction, so both cohorts express the same single rule: follow the first 5-minute candle. Section 3 shows the same Reversal events read in the gap direction, which is the *fade the candle* alternative, so no sign-flipping by hand is needed.

## Universe A — Post-Earnings (T+1)

| Window | Group | n | Win rate | Gross | **NET** | net p |
|---|---|---:|---:|---:|---:|---:|
| 5 min (09:40) | All Reversal | 7,556 | 52.0% | +1.9 | **-4.7** | 0.000 |
| 5 min (09:40) | Rev + High Volume | 3,913 | 50.3% | -1.0 | **-7.6** | 0.000 |
| 5 min (09:40) | Rev + Normal/Low Vol | 3,643 | 53.9% | +5.1 | **-1.5** | 0.140 |
| 15 min (09:50) | All Reversal | 7,741 | 52.3% | +2.8 | **-3.8** | 0.011 |
| 15 min (09:50) | Rev + High Volume | 3,954 | 48.3% | -6.5 | **-13.1** | 0.000 |
| 15 min (09:50) | Rev + Normal/Low Vol | 3,787 | 56.5% | +12.5 | **+5.9** | 0.001 |
| 1 hour (10:35) | All Reversal | 7,744 | 51.6% | +4.2 | **-2.4** | 0.256 |
| 1 hour (10:35) | Rev + High Volume | 3,959 | 49.2% | -4.3 | **-10.9** | 0.005 |
| 1 hour (10:35) | Rev + Normal/Low Vol | 3,785 | 54.2% | +13.0 | **+6.4** | 0.009 |

## Universe B — General Gaps

| Window | Group | n | Win rate | Gross | **NET** | net p |
|---|---|---:|---:|---:|---:|---:|
| 5 min (09:40) | All Reversal | 54,086 | 47.4% | -2.5 | **-9.1** | 0.000 |
| 5 min (09:40) | Rev + High Volume | 12,902 | 44.3% | -7.6 | **-14.2** | 0.000 |
| 5 min (09:40) | Rev + Normal/Low Vol | 41,184 | 48.3% | -0.9 | **-7.5** | 0.000 |
| 15 min (09:50) | All Reversal | 55,143 | 45.0% | -8.9 | **-15.5** | 0.000 |
| 15 min (09:50) | Rev + High Volume | 13,041 | 41.2% | -18.4 | **-25.0** | 0.000 |
| 15 min (09:50) | Rev + Normal/Low Vol | 42,102 | 46.1% | -5.9 | **-12.5** | 0.000 |
| 1 hour (10:35) | All Reversal | 55,269 | 45.8% | -9.7 | **-16.3** | 0.000 |
| 1 hour (10:35) | Rev + High Volume | 13,055 | 44.3% | -17.9 | **-24.5** | 0.000 |
| 1 hour (10:35) | Rev + Normal/Low Vol | 42,214 | 46.2% | -7.2 | **-13.8** | 0.000 |

## Key questions

**Does High Volume improve or worsen the Reversal signal in the post-earnings universe?**

- **5 min (09:40)**: High -7.6 bps / 50.3% win (n=3,913, p=0.000) vs Normal/Low -1.5 / 53.9% (n=3,643) → **-6.1 bps**
- **15 min (09:50)**: High -13.1 bps / 48.3% win (n=3,954, p=0.000) vs Normal/Low +5.9 / 56.5% (n=3,787) → **-19.0 bps**
- **1 hour (10:35)**: High -10.9 bps / 49.2% win (n=3,959, p=0.005) vs Normal/Low +6.4 / 54.2% (n=3,785) → **-17.3 bps**

**Worsens it at every horizon** (-19.0 to -6.1 bps).

**Does High Volume improve or worsen the Reversal signal in the general gap universe?**

- **5 min (09:40)**: High -14.2 bps / 44.3% win (n=12,902, p=0.000) vs Normal/Low -7.5 / 48.3% (n=41,184) → **-6.7 bps**
- **15 min (09:50)**: High -25.0 bps / 41.2% win (n=13,041, p=0.000) vs Normal/Low -12.5 / 46.1% (n=42,102) → **-12.4 bps**
- **1 hour (10:35)**: High -24.5 bps / 44.3% win (n=13,055, p=0.000) vs Normal/Low -13.8 / 46.2% (n=42,214) → **-10.7 bps**

**Worsens it at every horizon** (-12.4 to -6.7 bps).

**Is the effect of High Volume on Reversal different from its effect on Continuation?**

Net effect of High Volume (High minus Normal/Low), in bps:

| Universe | Window | Continuation | Reversal | Difference |
|---|---|---:|---:|---:|
| Post-Earnings (T+1) | 5 min (09:40) | +7.9 | -6.1 | **-14.0** |
| Post-Earnings (T+1) | 15 min (09:50) | +15.9 | -19.0 | **-34.9** |
| Post-Earnings (T+1) | 1 hour (10:35) | +22.1 | -17.3 | **-39.5** |
| General Gaps | 5 min (09:40) | +1.3 | -6.7 | **-8.0** |
| General Gaps | 15 min (09:50) | +1.9 | -12.4 | **-14.3** |
| General Gaps | 1 hour (10:35) | +1.2 | -10.7 | **-11.8** |

Mean across the three horizons — post-earnings: Continuation **+15.3** vs Reversal **-14.1**. General gaps: Continuation **+1.4** vs Reversal **-10.0**.

**Yes — the sign is opposite, in both universes.** Heavy opening volume makes the with-gap candle better and the counter-gap candle worse. That is what you would expect if volume marks genuine information being priced: it confirms the move already under way and penalises the attempt to fade it. Volume is not a generic 'more-conviction' marker that improves whatever signal it is attached to — it is directional.

> **This revises the previous report's read on general gaps.** Measured on the Continuation side alone, volume looked close to inert there (+1.4 bps) and I described it that way. On the Reversal side the same variable is worth **-10.0 bps** — comparable in magnitude to the earnings effect and far outside the cost noise. Volume is informative on general gaps after all; the Continuation test simply could not see it, because both the high- and low-volume Continuation cohorts drift with the gap and the contrast is small. The Reversal cohort is where the two volume regimes actually diverge.

## The same events read in the gap direction

If following the counter-gap candle loses on high volume, the mechanical alternative is to fade it and stay with the gap. These are the identical events with the direction reversed.

> **Costs do not flip with the sign.** Gross flips exactly; net does not, because the 6.6 bps round trip is paid either way. A cohort at −13.1 bps net in the candle direction is not +13.1 the other way — it is gross +6.5 minus costs, so −0.1. Both sides of a small gross edge lose. Only where gross is large does the flip produce something tradeable.

**Post-Earnings (T+1)**

| Window | Group | n | Win rate | Gross | **NET** | net p |
|---|---|---:|---:|---:|---:|---:|
| 5 min (09:40) | Rev events, gap dir — High Vol | 3,913 | 49.7% | +1.0 | **-5.6** | 0.000 |
| 5 min (09:40) | Rev events, gap dir — Normal/Low | 3,643 | 46.1% | -5.1 | **-11.7** | 0.000 |
| 15 min (09:50) | Rev events, gap dir — High Vol | 3,954 | 51.7% | +6.5 | **-0.1** | 0.969 |
| 15 min (09:50) | Rev events, gap dir — Normal/Low | 3,787 | 43.5% | -12.5 | **-19.1** | 0.000 |
| 1 hour (10:35) | Rev events, gap dir — High Vol | 3,959 | 50.8% | +4.3 | **-2.3** | 0.501 |
| 1 hour (10:35) | Rev events, gap dir — Normal/Low | 3,785 | 45.8% | -13.0 | **-19.6** | 0.000 |

**General Gaps**

| Window | Group | n | Win rate | Gross | **NET** | net p |
|---|---|---:|---:|---:|---:|---:|
| 5 min (09:40) | Rev events, gap dir — High Vol | 12,902 | 55.7% | +7.6 | **+1.0** | 0.350 |
| 5 min (09:40) | Rev events, gap dir — Normal/Low | 41,184 | 51.7% | +0.9 | **-5.7** | 0.000 |
| 15 min (09:50) | Rev events, gap dir — High Vol | 13,041 | 58.8% | +18.4 | **+11.8** | 0.000 |
| 15 min (09:50) | Rev events, gap dir — Normal/Low | 42,102 | 53.9% | +5.9 | **-0.7** | 0.629 |
| 1 hour (10:35) | Rev events, gap dir — High Vol | 13,055 | 55.7% | +17.9 | **+11.3** | 0.000 |
| 1 hour (10:35) | Rev events, gap dir — Normal/Low | 42,214 | 53.8% | +7.2 | **+0.6** | 0.799 |

### The strongest general-gap cell found so far

- **15 min (09:50)**: staying with the gap when the first candle went against it *on high volume* — **+11.8 bps net**, 58.8% win rate, n = 13,041, p = 0.000
- **1 hour (10:35)**: staying with the gap when the first candle went against it *on high volume* — **+11.3 bps net**, 55.7% win rate, n = 13,055, p = 0.000

This is a larger net figure than anything the Continuation route produced on general gaps, on a sample of over 13,000 events, and it has a coherent mechanism: a counter-gap first candle on heavy volume looks like a failed reversal — supply being absorbed — after which the gap direction reasserts.

**Two reasons not to promote it yet.** It is a cell selected *after* seeing the results, and this investigation has now examined enough cohorts that some will clear p < 0.05 by construction; the p-value above is not adjusted for that search. And high-volume names carry the widest spreads, so the flat 6.6 bps cost is least defensible exactly here. The honest status is a hypothesis worth a clean out-of-sample test, not a validated edge.

## Volume composition of the two cohorts

| Universe | Cohort | n | High Vol | % High | Median vol ratio |
|---|---|---:|---:|---:|---:|
| Post-Earnings (T+1) | Continuation | 7,295 | 4,938 | 67.7% | 2.29 |
| Post-Earnings (T+1) | Reversal | 7,794 | 3,980 | 51.1% | 1.54 |
| General Gaps | Continuation | 55,751 | 20,471 | 36.7% | 1.11 |
| General Gaps | Reversal | 55,508 | 13,113 | 23.6% | 0.77 |

If the two cohorts carry similar volume profiles, then the difference in how volume acts on them is about direction rather than about one cohort simply being the higher-volume one.

---

_Reproducible from `lambda_strategy_validation/volume_reversal.py`; tables in `lambda_data/tables/volrev_*.csv`._