# Volume source integrity and the High Volume filter

The provider's volume series changes basis in March 2022. This asks the
only question that matters for the research: does the change break the
1.5x High Volume filter that the core cohort is built on.

**It does not.** The filter's incremental value is 20.1 bps before the
change and 17.2 bps after, and the difference is not distinguishable
from zero. The reason is structural: the filter is a ratio against its
own trailing mean, so a change in what volume *counts* cancels top and
bottom. Details below.

## 1. When the break happens

Daily volume pooled across 199 tickers, each normalised by its own
pre-break median. This is not a per-ticker artefact -- every name moves
on the same day.

| session | n_tickers | median_rel_volume |
|---|---|---|
| 2022-02-15 | 199 | 0.9374 |
| 2022-02-16 | 199 | 0.8243 |
| 2022-02-17 | 199 | 0.9119 |
| 2022-02-18 | 199 | 0.9585 |
| 2022-02-22 | 199 | 1.011 |
| 2022-02-23 | 199 | 0.991 |
| 2022-02-24 | 199 | 1.3916 |
| 2022-02-25 | 199 | 1.0055 |
| 2022-02-28 | 199 | 1.0415 |
| 2022-03-01 | 199 | 1.0693 |
| 2022-03-02 | 199 | 1.0372 |
| 2022-03-03 | 199 | 0.9552 |
| 2022-03-04 | 199 | 1.0574 |
| 2022-03-07 | 199 | 0.1247 |
| 2022-03-08 | 199 | 0.1142 |
| 2022-03-09 | 198 | 0.0963 |
| 2022-03-10 | 199 | 0.0786 |
| 2022-03-11 | 199 | 0.0774 |
| 2022-03-14 | 197 | 0.0973 |
| 2022-03-15 | 198 | 0.0836 |
| 2022-03-16 | 199 | 0.1004 |
| 2022-03-17 | 199 | 0.0824 |
| 2022-03-18 | 199 | 0.0876 |

Last clean session **2022-03-04**, first affected session
**2022-03-07**. The pipeline's `IEX_BREAK` constant is
2022-03-01, four sessions early. That costs four clean sessions
of threshold calibration and contaminates nothing, because the same code
excises a 120-day straddle window that swallows them.

## 2. What the post-break series is

Reported volume against an independent consolidated-tape source for the
same sessions:

| ticker | date | hf_volume | consolidated_volume | hf_share_pct |
|---|---|---|---|---|
| AAPL | 2026-07-30 | 2208074 | 74817792 | 2.95 |
| AAPL | 2026-07-31 | 4261510 | 132489137 | 3.22 |
| GILD | 2026-07-27 | 186491 | 4953801 | 3.76 |
| GILD | 2026-07-28 | 262654 | 6947167 | 3.78 |
| GILD | 2026-07-29 | 294152 | 7766370 | 3.79 |
| GILD | 2026-07-30 | 216209 | 6726143 | 3.21 |
| GILD | 2026-07-31 | 211287 | 6531645 | 3.23 |

HF post-break volume is **3.0-3.8% of consolidated** -- consistent with IEX's
own market share. So the post-break series is a single venue's prints,
not the consolidated tape. Prices are unaffected: IEX prints are real
trades.

## 3. The gap that is already in the data

There are no events at all between 2022-03-01 and roughly
2022-06-29 -- 0 rows in a window that would normally hold several
hundred. That hole is deliberate, not missing data:
`run_study.break_aware_liquidity` drops every row whose 63-session
trailing liquidity window straddles the break, because such a window
averages two unit systems. Worth knowing it is there before anyone reads
a 2022 number as a regime signal.

## 4. Does the filter still discriminate

The level shift cancels in a ratio. The open question was noise: a ~3%
sample of the tape is noisier per bar than the tape, and noise in the
ratio would degrade the filter even where the rescaling does not. The
ratio distribution does widen, materially:

| era | n | p10 | p25 | p50 | p75 | p90 | p90_over_p10 | hv_flag_rate |
|---|---|---|---|---|---|---|---|---|
| pre-break (consolidated) | 10367 | 0.63 | 1.09 | 1.85 | 3.99 | 8.86 | 14.14 | 0.6 |
| post-break (IEX-only) | 5520 | 0.44 | 0.93 | 2.22 | 6.26 | 14.0 | 31.84 | 0.62 |

Ninetieth-over-tenth percentile goes from 14.1 to 31.8. The
threshold nonetheless flags a near-identical share of events
(59.6% vs 61.5%), so it is selecting a wider-dispersed but
similarly sized slice.

The test that settles it -- the filter's incremental value, High Volume
minus non-High Volume within Continuation, 1-hour hold, after
6.6 bps, date-clustered:

| era | n_high_vol | n_other | filter_value_bps | ci_lo | ci_hi |
|---|---|---|---|---|---|
| pre-break (consolidated) | 3211 | 1410 | 20.06 | 8.9 | 31.8 |
| post-break (IEX-only) | 1695 | 856 | 17.19 | 3.71 | 30.88 |

Difference post minus pre: **-3.17 bps**, 95% CI
[-16.10, +10.10]. The interval spans zero -- no detectable degradation.

## 5. The edge either side of the break

| cohort | n | net_bps | ci_lo | ci_hi | win_rate |
|---|---|---|---|---|---|
| High Vol + Continuation | 4906 | 30.38 | 23.75 | 37.91 | 0.57 |
|   pre-break (consolidated) | 3211 | 34.48 | 25.36 | 44.5 | 0.58 |
|   post-break (IEX-only) | 1695 | 22.7 | 12.76 | 32.11 | 0.54 |
| Continuation, NOT High Vol | 2266 | 10.87 | 5.38 | 16.35 | 0.54 |
|   pre-break (consolidated) | 1410 | 14.14 | 7.48 | 20.67 | 0.56 |
|   post-break (IEX-only) | 856 | 5.52 | -3.85 | 15.64 | 0.49 |

The core edge is lower after the break (34.5 -> 22.7 bps, a fall of
11.8), but the confidence intervals overlap heavily. More to the
point, the same decline shows up in the cohort selected *without* the
volume filter (14.1 -> 5.5 bps, a fall of 8.6). A fault in the
volume series cannot move a cohort whose selection never touched volume.
The decline is regime, not measurement.

## What this changes

The volume worry was worth raising and is now bounded. The filter rests
on a ratio, and ratios survive a change in the unit being counted. What
a consolidated-tape re-test would still buy is the noise question in
section 4: whether the filter is worth *more* than 17.2 bps
post-break when computed on clean volume. That is an optimisation, not a
validity repair, and it should be priced accordingly.

One caveat that does not go away: this compares the filter against
itself either side of the break. It cannot detect a fault present in
*both* eras.

Generated by `volume_integrity.py`. Consolidated spot checks from
Massive `/v2/aggs`, `adjusted=false`.
