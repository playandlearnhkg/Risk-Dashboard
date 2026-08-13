# Continuous Candle Scoring — Validation Framework (Stages B, C, D)

**Owner:** Lambda (Strategy Validator)
**Status:** Design specification. Nothing here has been tested. No result in this
document is a claim — every number below is either a definition, a hurdle, or a
power calculation.
**Purpose:** Determine whether a continuous candle-geometry score adds usable
quality to an *existing* edge, and to be able to conclude that it does **not**.

---

## 0. Framing, stated before any test is run

Three things must be written down before data is touched, because writing them
down afterwards is how backtests lie.

**0.1 The prior is unfavourable.** Single-bar OHLC geometry is the most heavily
data-mined feature set in retail and semi-professional trading. It is computable
from free data, has been public since Homma, and is present in every charting
package. The prior probability that a simple continuous re-encoding of it carries
standalone, cost-surviving, out-of-sample directional edge is low. The framework
below is therefore built to *reject*, and the burden of proof sits with the score.

**0.2 The standalone use case is near-certainly dead on cost arithmetic alone.**
Compute this before any backtest (Section D.7 formalises it):

| Instrument | σ per 5-min bar | E&#124;move&#124; ≈ 0.798σ | Round-trip cost | Break-even hit rate |
|---|---|---|---|---|
| SPY / ES (16% annualised vol) | ≈ 11.3 bp | ≈ 9.0 bp | ≈ 0.8 bp | **p ≥ 54.4%** |
| Liquid single name (25% ann. vol, 3 bp spread) | ≈ 17.7 bp | ≈ 14.1 bp | ≈ 4.0 bp | **p ≥ 64.2%** |
| Mid-cap (40% ann. vol, 6 bp spread) | ≈ 28.3 bp | ≈ 22.6 bp | ≈ 7.5 bp | **p ≥ 66.6%** |

Break-even is `p ≥ 0.5 · (1 + c_rt / E|move|)`, assuming symmetric win/loss
magnitude and full capture of the mean absolute move — an *optimistic* assumption
because directional bets get the adverse-selection side of the fill. Realistic
conditional hit rates for single-bar geometry are 51–54%. **Pre-registered
implication: if Stage B is used to justify standalone next-bar trading, the
answer is discard, and the test in B.3 is expected to confirm that.**

**0.3 The only credible use case has a different, much lower hurdle.** As a
*filter on an existing edge*, the score does not need to generate edge. It needs
to identify a subset of already-generated signals whose **net** expectancy is
below zero (or below the expectancy of the capital's next best use). Filtering
*removes* cost rather than adding it. A score with an information coefficient of
0.02 — economically worthless standalone — can be worth basis points per trade as
a filter if the existing edge's per-trade expectancy is large relative to costs
and the score's discrimination concentrates in the tails.

**This asymmetry is the entire reason to run the study.** Every stage below is
therefore evaluated twice: standalone (expected to fail; test it anyway so the
failure is documented rather than assumed) and as a conditional filter (the live
hypothesis).

**0.4 Pre-registration is mandatory.** Before the first test executes, commit a
`preregistration.yaml` to this repo containing: the feature list, the score
formulas with all constants fixed, the target definitions, the window schedule,
the cost model, the full list of hypotheses to be tested, the intended trial
count `N_trials`, and the Section D.9 decision gates verbatim. The commit hash of
that file goes in every results report. Any test not in the file is exploratory
and may not be cited in a keep/discard decision without a fresh pre-registration
and fresh out-of-sample data.

---

# 1. Stage B — Continuous Candle Scoring + Next-Candle Predictivity

## B.1 Single-candle continuous scoring

### B.1.1 Primitives

For bar `t` with open `O`, high `H`, low `L`, close `C`, volume `V`:

```
R  = H - L                      range
B  = C - O                      signed body
U  = H - max(O, C)              upper shadow
D  = min(O, C) - L              lower shadow
```

Identity (must be asserted in code as a unit test): `|B| + U + D = R`.

### B.1.2 Tier-1 features — pure intrabar geometry, scale-invariant

All are defined only where the validity gate in B.1.4 passes. All are bounded,
which matters: unbounded features let one outlier bar dominate a regression.

| Feature | Formula | Range | Meaning |
|---|---|---|---|
| `BD` body dominance | `B / R` | [−1, 1] | signed body share of range |
| `CL` close location | `(2C − H − L) / R` | [−1, 1] | where close sits in the range (+1 = on the high) |
| `SA` shadow asymmetry | `(D − U) / R` | [−1, 1] | rejection asymmetry |
| `WB` wick burden | `(U + D) / R = 1 − &#124;B&#124;/R` | [0, 1] | indecision / lack of conviction |
| `OL` open location | `(2O − H − L) / R` | [−1, 1] | where the bar opened in its own range |
| `CONV` conviction | `1 − WB = &#124;B&#124;/R` | [0, 1] | body share of range |

**Mandatory collinearity disclosure.** `BD`, `CL` and `SA` are not independent —
they are three views of one latent "where did price settle within the bar, and
how decisively" factor. Empirical pairwise |ρ| of 0.7–0.95 is expected. Before
any composite is built, run and report:

1. Pairwise Spearman matrix of Tier-1 features on the in-sample window.
2. PCA on the standardised Tier-1 block; report variance explained by PC1.

If PC1 explains > 80% of variance, the composite score is a single factor with
extra decoration, and the **parsimony test** in B.3.6 becomes a hard gate: the
composite must beat its own single best component out-of-sample, or the single
component wins and the composite is discarded.

### B.1.3 Tier-2 features — normalisation and context, explicitly separated

These use prior bars and are therefore *not* pure candle geometry. They are kept
in a separate tier so that any measured lift can be attributed correctly, and so
"the candle score works" cannot silently mean "the volatility normalisation
works".

| Feature | Formula (all inputs strictly ≤ `t`, ATR from bars ≤ `t−1`) |
|---|---|
| `RNG_Z` range magnitude | `R_t / ATR_n(t−1)`, `n = 20` bars, Wilder ATR |
| `RNG_P` range percentile | rank of `R_t` in trailing 500 same-time-of-day bars, strictly before `t` |
| `GAP` | `(O_t − C_{t−1}) / ATR_n(t−1)` |
| `BODY_ATR` | `B_t / ATR_n(t−1)` |

`ATR_n(t−1)` must be computed from bars `t−n … t−1` inclusive and **must exclude
bar `t`**. This is the single most common look-ahead bug in candle studies. It is
covered by the harness test in D.10.2.

### B.1.4 Zero-range and near-zero-range handling

A bar with `R = 0` makes every Tier-1 feature `0/0`. A bar with `R` of one or two
ticks makes them defined but pure microstructure noise — `CL` flips between −1 and
+1 on a single tick. Both must be handled, and they must be handled *without*
deleting bars, because deleting bars from a time series is a form of survivorship
bias inside the sample.

Define the noise floor at bar `t`, using only information through `t−1`:

```
eps_tick = k_tick * tick_size            k_tick = 2.0
eps_vol  = k_vol  * ATR_20(t-1)          k_vol  = 0.10
eps_t    = max(eps_tick, eps_vol)
```

Then apply **both** mechanisms:

**(a) Continuous confidence weight** — preferred, keeps the score continuous:

```
w_range(t) = R_t / (R_t + eps_t)          in [0, 1)
```

`w_range → 0` smoothly as the bar degenerates. It multiplies the final score, so
a near-doji contributes a near-zero score rather than a violently noisy one.

**(b) Hard validity flag** — for exclusion from *conditional statistics*:

```
valid(t) = (R_t >= eps_t) and (R_t > 0) and all(O,H,L,C finite)
           and (L <= min(O,C)) and (H >= max(O,C))
```

Rules:
- If `R_t = 0`: all Tier-1 features are `NaN`, never `0`. `NaN` is not a neutral
  score; encoding it as `0` silently injects a fake "neutral bar" into the
  distribution and biases every bucket mean.
- Bars with `valid(t) = False` remain in the time index (so the forward-return
  clock is unbroken) but are excluded from score-conditional buckets, and their
  **count and fraction must be reported in every results table**. If degenerate
  bars exceed 5% of a sample, the instrument or timeframe is too illiquid for
  this study and is dropped with that reason recorded.
- The unconditional baseline in B.3.4 must be recomputed on exactly the same
  filtered set used for the conditional statistic. Comparing a filtered
  conditional rate to an unfiltered baseline is a fabricated lift.

### B.1.5 Composite scores

Two constructions are built **in parallel and compared**. This is deliberate:
the analytic score cannot be accused of fitting, and the fitted score sets the
achievable ceiling. If the fitted score also fails out-of-sample, the idea is
dead and no amount of re-weighting will save it.

#### Construction 1 — A-priori analytic score (zero fitted parameters)

```
DIR_t  = (BD_t + CL_t + SA_t) / 3                    in [-1, 1]
CONV_t = 1 - WB_t                                     in [0,  1]
DQ_t   = DIR_t * CONV_t^gamma * w_range(t)            in (-1, 1)
```

with `gamma = 1.0`. Equal weights and `gamma = 1` are the **null choice** — they
are not optimised, and they are fixed at pre-registration. `DQ` is Directional
Quality: sign gives direction, magnitude gives quality.

Directional split, both continuous:

```
S_bull_t = max(DQ_t, 0)
S_bear_t = max(-DQ_t, 0)
```

*Justification for `CONV` as a multiplier rather than an additive term:* a bar
that closes near its high on a tiny body inside a huge range is not a strong
bullish bar, it is an indecisive bar that happened to tick up at the end.
Multiplying by conviction sends it toward zero, which is the intended semantic.
This is a design choice, not an empirical claim, and B.3.6 tests it against the
additive alternative as a pre-registered variant (counted in `N_trials`).

#### Construction 2 — Walk-forward fitted score (ceiling estimate)

On each walk-forward training window only (D.1), fit:

- **Model A:** L2-regularised logistic regression, `y = 1[r_{t+1} > 0]`,
  features = Tier-1 block. Regularisation strength selected by *inner* purged CV
  on the training window only.
- **Model B:** gradient-boosted trees, depth ≤ 3, ≤ 200 trees, early stopping on
  the inner CV fold. Depth cap is a pre-commitment against fitting noise.

Score = out-of-sample predicted probability, mapped to `2p̂ − 1` for comparability
with `DQ`.

Anti-leakage rules for the fitted path:
- Every scaler, encoder, percentile map and hyperparameter is fit on train only
  and applied frozen to test. No `fit_transform` on the full series, ever.
- Purge and embargo at the fold boundary (D.1.3).
- Class balance and the unconditional base rate are taken from the *training*
  window; the test window's base rate is never used to calibrate.

#### Rank normalisation (required for both constructions)

Raw `DQ` is not comparable across instruments, volatility regimes or times of
day. Convert to a trailing percentile:

```
DQ_pct(t) = percentile_rank of DQ_t within
            { DQ_s : s in the trailing 500 valid bars of the same
                     instrument and same intraday time-of-day bucket,
                     s < t  (strictly) }
```

- Window is **strictly prior**. The current bar is never in its own reference
  distribution.
- Time-of-day bucketing is mandatory intraday. The 09:35 bar and the 13:30 bar
  have different range, body and volume distributions; pooling them creates a
  score that is largely a clock.
- Minimum 250 observations in the reference window or `DQ_pct = NaN` (warm-up).
  Warm-up bars are excluded from statistics but retained in the index.

## B.2 Short-group scoring (2–4 consecutive candles)

Group `G_k(t) = {t−k+1, …, t}`, `k ∈ {2, 3, 4}`. Every feature uses only bars
through `t`, and the group score is stamped at the **close of bar `t`**.

### Method 1 — Weighted aggregate of single-bar scores

```
GS_agg(k, t) = sum_{i=0..k-1} rho^i * DQ_{t-i}  /  sum_{i=0..k-1} rho^i
```

with `rho = 0.70` fixed at pre-registration (recency-weighted; `rho = 1.0` — a
plain mean — is a pre-registered variant, counted in `N_trials`).

### Method 2 — Merged synthetic candle

Collapse the group into one bar and score it with the identical B.1.5 machinery:

```
O_g = O_{t-k+1}      H_g = max(H_{t-k+1..t})
L_g = min(L_{t-k+1..t})   C_g = C_t
```

`GS_merge(k, t) = DQ(O_g, H_g, L_g, C_g)`, with the same validity gate applied
using `eps` scaled to the group (`eps_g = max(k_tick·tick, k_vol·ATR_20(t−k))`).

This is the cleaner construction — it is exactly the single-bar score on a
higher timeframe — and it is the benchmark that Method 1 and Method 3 must beat
to justify their extra complexity.

### Method 3 — Group-specific geometry (adds information the merged bar destroys)

| Feature | Formula | Meaning |
|---|---|---|
| `EFF` displacement efficiency | `(C_t − O_{t−k+1}) / Σ_{i} R_i` | signed; how much travel became progress |
| `COH` sign coherence | `(1/k) Σ_i sign(B_i)` | do the bodies agree |
| `OVL` mean overlap | `(1/(k−1)) Σ_i overlap(i, i−1) / R_i` where `overlap = max(0, min(H_i,H_{i−1}) − max(L_i,L_{i−1}))` | congestion vs displacement |
| `EXP` range expansion | `R_t / mean(R_{t−k+1..t−1})` | is the last bar the impulse |

```
GS_geo(k, t) = (EFF + COH + (1 - OVL) * sign(EFF)) / 3 * w_range_group(t)
```

Equal weights, fixed. `EFF` is bounded in [−1, 1] by construction since
`|C_t − O_{t−k+1}| ≤ Σ R_i`.

### Pre-registered comparison

Test `GS_agg`, `GS_merge`, `GS_geo` for `k ∈ {2,3,4}` = **9 group variants**,
plus 1 single-bar analytic + 2 fitted = **12 scores in the primary family**.
This count enters the multiple-testing correction in D.4. It is fixed now and
may not grow.

## B.3 Next-candle predictability tests

### B.3.1 Target definitions (pre-registered, all reported, none dropped)

Three targets, because "the next candle closes in the same direction" is
ambiguous and the ambiguity is exploitable if left open:

| Target | Definition | Tradable from `C_t`? |
|---|---|---|
| `y_cc` | `sign(C_{t+1} − C_t)` | **Yes** — this is the primary target |
| `y_body` | `sign(C_{t+1} − O_{t+1})` | No — not decidable at `C_t` if `O_{t+1} ≠ C_t` |
| `r_norm` | `(C_{t+1} − C_t) / ATR_20(t)` — continuous | Yes — primary for IC, higher power |

`y_cc` is the primary binary target. `y_body` is reported because it is what
candlestick folklore actually claims, and the gap between `y_cc` and `y_body`
results is itself diagnostic: if the score predicts `y_body` but not `y_cc`, the
"edge" lives in the overnight/inter-bar gap and is not capturable.

`r_norm` is the primary continuous target — sign tests throw away magnitude
information and need roughly 3–5× the sample for the same power.

Horizons `h ∈ {1, 2, 3}` bars forward. For `h > 1`, targets overlap across
consecutive `t` and **must** be handled by D.4.2 (HAC / block bootstrap), or by
sub-sampling to non-overlapping observations.

**Zero-move handling:** exact `C_{t+1} = C_t` is common on 1-min bars in quiet
names. These observations are excluded from binary tests, their count is
reported, and the unconditional baseline is computed on the identical excluded
set. They are *retained* for `r_norm` (a zero return is information).

### B.3.2 Test (a) — does a high/low 5-min score raise same-direction probability?

**H0:** `P(y_cc = sign(DQ_t) | DQ_pct(t) ∈ bucket q) = P(y_cc = sign(DQ_t))`
for every bucket `q`.
**H1 (directional, pre-registered):** monotonically increasing in `|DQ_pct − 0.5|`
for the same-direction outcome.

Procedure, per walk-forward out-of-sample fold:

1. Bucket bars by `DQ_pct(t)` into deciles (10 buckets, fixed, using the
   trailing-percentile mapping from B.1.5 — never a fold-wide quantile cut,
   which would leak the fold's own distribution).
2. Per bucket: `n`, hit rate for `y_cc`, mean `r_norm`, median `r_norm`,
   degenerate-bar count.
3. **Lift** `Λ_q = HitRate_q − BaseRate_fold`, where `BaseRate_fold` is the
   unconditional `P(y_cc = +1)` on the *same fold, same filtered set, same
   time-of-day distribution*.
4. **Monotonicity test** — this is the primary evidence, not any single bucket.
   Jonckheere–Terpstra trend test across the 10 ordered buckets on `r_norm`, plus
   Spearman ρ between bucket index and bucket mean `r_norm`. A single outperforming
   bucket amid noise is a mining artefact; a monotone gradient is a signal.
5. **Information coefficient** — Spearman ρ(`DQ_t`, `r_norm(t)`) per fold. Report
   mean IC, IC standard deviation across folds, `t = mean(IC)/se(IC)` with `se`
   from the block bootstrap, and the fraction of folds with IC of the
   pre-registered sign.
6. **AUC** for `1[r_norm > 0]` vs `DQ_t`, reported as `AUC − 0.5`.

### B.3.3 Test (b) — do recent 1-min scores improve prediction of the next 5-min bar?

Decision stamp: the close of a 5-min bar boundary, `T`. Inputs: the group scores
of the last `m ∈ {3, 5}` completed **1-min** bars, i.e. bars `T−m+1 … T`, using
`GS_agg`, `GS_merge` and `GS_geo` at 1-min resolution.

Alignment rules — the leakage surface here is large and specific:

- Only 1-min bars whose close timestamp is `≤ T` may be used. A bar labelled
  `09:35` in most vendor feeds covers `09:35:00–09:35:59` and closes at
  `09:36:00`. Confirm the vendor's convention explicitly and record it in the
  pre-registration; an off-by-one here manufactures a spectacular fake edge.
- The 5-min bar ending at `T` and the last five 1-min bars ending at `T` cover
  the *same* data. Test (b) must therefore be run in two forms:
  - **(b-i) Incremental:** does the 1-min block add to the 5-min score? Nested
    comparison — fit/score with the 5-min feature block alone, then with 5-min +
    1-min block, and test the improvement (likelihood-ratio test for the logistic
    path; ΔIC with block-bootstrap CI for the analytic path).
  - **(b-ii) Standalone:** 1-min block only.
  Only **(b-i)** answers "improve prediction". Reporting (b-ii) alone would
  attribute the 5-min bar's own information to the 1-min layer.
- Session boundaries: the first 5-min bar of the session has no prior in-session
  1-min bars. Those decision points are excluded and counted, not backfilled from
  the prior session.

### B.3.4 Test (c) — strength of relationship, against the right baselines

Four benchmarks, all mandatory in every results table:

| Benchmark | Construction |
|---|---|
| **B1 Unconditional** | Fold base rate on the identical filtered set and time-of-day mix |
| **B2 Permutation null** | Shuffle `DQ` labels within the fold, 1,000 times, preserving both marginal distributions; report where the observed statistic falls in the null distribution |
| **B3 Existing edge alone** | The current edge's trade set, unfiltered, same period, net of costs |
| **B4 Buy-and-hold** | Same instrument, same period, net of one entry and one exit |

Reported metrics, **net of costs wherever a trade is simulated**:

- Hit rate and lift `Λ` with block-bootstrap 95% CI
- Mean `r_norm` per bucket, in ATR units and in basis points
- IC, IC-t, IC consistency (fraction of folds with correct-sign IC)
- AUC − 0.5
- Net expectancy per trade in bp, and net expectancy after the D.7 cost model
- Fraction of out-of-sample folds with positive net lift

**No gross-only number may appear in a summary table.** Gross figures are
permitted in diagnostic appendices, labelled as such.

### B.3.5 Test (d) — extreme vs moderate scores

The folklore claim is that extreme scores carry more information. Test it as a
shape hypothesis, not a threshold hunt:

1. Plot and tabulate mean `r_norm` and hit rate against `DQ_pct` across **20
   ventiles** — the full response curve, not a chosen cut.
2. Fit a monotone shape test (isotonic regression `R²` vs linear `R²`) and report
   whether the relationship is monotone, U-shaped, or noise.
3. Compare extreme tails (`DQ_pct ≤ 0.05` or `≥ 0.95`) against the moderate
   middle (`0.35–0.65`) with a two-proportion test and block-bootstrap CI.
4. **Tail sample size warning:** the 5% tail of a 100,000-bar sample is 5,000
   observations — below the power requirement in B.3.7 for any lift under ~2.5pp.
   If the tail cell is underpowered, the correct report is "underpowered,
   inconclusive", not a point estimate.
5. **Threshold plateau requirement:** if any threshold is later proposed, it must
   sit in a plateau of ≥ 20 percentile points over which the net metric varies by
   less than 25% of its value (D.5). A spike at one percentile is overfitting and
   is a hard kill.

### B.3.6 Parsimony gate

Complexity must pay for itself out-of-sample. Pre-registered ladder — each rung
must beat the one below it on OOS net metric, or the simpler rung wins and the
more complex one is discarded:

```
1. sign(BD)            (crude, 1 bit)
2. best single Tier-1 feature
3. DQ analytic composite
4. GS_merge (best k)
5. GS_agg / GS_geo
6. Fitted logistic
7. Fitted GBM
```

A composite that does not beat its own best component out-of-sample is discarded
in favour of the component. This gate exists because composite scores nearly
always look better in-sample by construction.

### B.3.7 Power and minimum detectable effect — computed before testing

One-sample proportion test, α = 0.05 two-sided, power = 0.80, base rate 52%:

`n = [z_{0.975}·√(p₀(1−p₀)) + z_{0.80}·√(p₁(1−p₁))]² / δ²`

| Lift δ to detect | Observations needed **in the conditional cell** | Total bars if cell = top decile |
|---|---|---|
| 1.0 pp | ≈ 19,600 | ≈ 196,000 |
| 1.5 pp | ≈ 8,700 | ≈ 87,000 |
| 2.0 pp | ≈ 4,900 | ≈ 49,000 |
| 3.0 pp | ≈ 2,200 | ≈ 22,000 |
| 5.0 pp | ≈ 780 | ≈ 7,800 |

Sanity check in calendar terms: 49,000 five-minute bars ≈ 628 US equity sessions
≈ **2.5 years of a single instrument** to detect a 2pp lift in the top decile.

**Effective sample size deflation is mandatory.** Pooling `K` instruments does
not give `K×` the data. With mean pairwise correlation `ρ̄` of contemporaneous
observations:

```
K_eff = K / (1 + (K - 1) * rho_bar)
```

Ten US large caps with `ρ̄ ≈ 0.30` give `K_eff ≈ 2.7`, not 10. Every reported
`n`, CI and t-statistic must use `n_eff`, and `ρ̄` must be estimated and
reported. Autocorrelation within an instrument is handled separately by the
block bootstrap (D.4.2).

If the available data cannot reach the required `n_eff` for the pre-registered
minimum detectable effect, the correct output is **"underpowered — no
conclusion"**. That is a legitimate and expected outcome, and it is not a reason
to lower the bar.

### B.3.8 Anti-look-ahead rules — Stage B checklist

Every one of these is a code-level assertion, not a convention:

1. All features at `t` are functions of `{O,H,L,C,V}_s` for `s ≤ t` only.
2. All rolling statistics (ATR, percentile, median volume, mean, std) use windows
   ending at `t−1` for normalisers and at `t` only for the bar's own geometry.
   **No full-sample `mean()`/`std()`/`quantile()` anywhere in the feature path.**
3. Targets are shifted with `.shift(-h)` at exactly one place in the codebase, and
   that function is unit-tested against a hand-built fixture.
4. Percentile maps are trailing and strictly exclusive of the current bar.
5. Timestamp convention (bar-open-labelled vs bar-close-labelled) is asserted once
   at load and recorded in the pre-registration.
6. Corporate actions: use split- and dividend-adjusted series consistently, and
   verify no adjustment factor applied to a historical bar uses a *later*
   adjustment event in a way that alters intrabar ratios. Ratios are
   scale-invariant, so multiplicative adjustment is safe; additive adjustment is
   not. Assert which the vendor uses.
7. No bar may be dropped from the index — only flagged.

---

# 2. Stage C — Context Filters, One at a Time

Four filters. Each is tested **alone** on top of the score before any combination
is attempted. Combination is Stage C.6 and is gated on individual results.

Common rules for all four:
- Every input is knowable at the close of the decision bar.
- Each filter is discretised into **terciles** using a *trailing* distribution
  (same rule as B.1.5: trailing 500 same-time-of-day observations, strictly prior).
  Terciles, not deciles, because filter cells subdivide the score cells and the
  power calculation in B.3.7 applies to the *intersection*.
- Lift is measured net of costs, per out-of-sample fold, never pooled-only.

## C.1 Filter 1 — Prior trend / higher-timeframe direction

**Calculation (recommended form — avoids the partial-bar trap entirely):**

```
TREND(t) = (C_t - EMA_span(t)) / ATR_20(t-1)
```

where `EMA_span` is computed on the **base timeframe** with `span` equal to the
higher timeframe in base-timeframe units — e.g. for a 5-min base and a 60-min
view, `span = 12`; for a daily view, `span = 78`.

*Why this form:* resampling to a higher timeframe and reading "the current 60-min
bar" is the classic intraday look-ahead bug — the current 60-min bar is not
complete until 60 minutes have passed. An EMA on the base timeframe is complete
at every base bar. If a genuine higher-timeframe bar is required, it must be the
**last fully closed** HTF bar as of `t`, and the code must assert
`htf_bar.close_time <= t`.

**Terciles:** down-trend / neutral / up-trend by trailing distribution of `TREND`.

**Pre-registered hypothesis:** the bullish score's lift is larger in the
up-trend tercile than the down-trend tercile (i.e. a positive interaction). Sign
declared in advance — a "discovered" reversal of sign post-hoc is a narrative,
not a finding, and must be reported as such.

## C.2 Filter 2 — Volume confirmation

```
RVOL(t) = V_t / median{ V_s : s in the same intraday time-of-day slot,
                        over the trailing 20 sessions, s < t (strictly) }
```

Time-of-day normalisation is non-negotiable intraday: raw volume is a U-shaped
clock, and an unnormalised volume filter is largely an "is it near the open or
close" filter wearing a disguise. Median, not mean, because volume is
right-skewed and news bars would dominate.

Trailing 20 **sessions** at the same slot, excluding the current session's
earlier slots (which would introduce a within-day drift).

**Terciles:** low / normal / high RVOL.
**Pre-registered hypothesis:** score lift is concentrated in the high-RVOL
tercile (conviction requires participation).
**Falsification value:** if lift is *flat* across RVOL terciles, the volume story
that every trading book tells is not present in this data, and must be reported
as absent.

## C.3 Filter 3 — Location relative to structure

Two variants, both pre-registered, both in ATR units:

```
LOC_vwap(t) = (C_t - VWAP_session(t)) / ATR_20(t-1)
LOC_or(t)   = (C_t - OR_mid(t)) / OR_range(t)
```

- `VWAP_session(t)` uses only bars from the session open through `t`. Safe — it is
  causal by construction. Assert it resets at the session boundary.
- `OR` = opening range over the first `k_or` minutes (`k_or = 15`, fixed).
  `LOC_or` is defined only for bars after the opening range completes;
  `OR_range = ORH − ORL`, with a degeneracy gate `OR_range ≥ eps` using the same
  B.1.4 machinery.

**Terciles:** below / at / above structure.
**Pre-registered hypothesis:** the score's directional information is stronger
when the score's direction agrees with the sign of `LOC` (continuation) — and the
opposite hypothesis (fade at extended locations) is *also* pre-registered as a
competing alternative, with the mean-reversion crossover point to be reported
rather than chosen.

## C.4 Filter 4 — Volatility / regime

Two components, tested separately:

```
VOL_RATIO(t)  = ATR_20(t-1) / ATR_100(t-1)
VOL_PCT(t)    = percentile rank of realised vol over the trailing 20 bars,
                within the trailing 500 same-time-of-day observations, s < t
EFF_RATIO(t)  = |C_t - C_{t-20}| / sum_{i=1..20} |C_{t-i+1} - C_{t-i}|
```

`EFF_RATIO` (Kaufman efficiency) separates trending from choppy regimes and is
strictly causal.

**Terciles** on `VOL_PCT` and on `EFF_RATIO` independently.
**Pre-registered hypothesis:** candle geometry carries continuation information
in high-`EFF_RATIO` (trending) regimes and reversal information in
low-`EFF_RATIO` (choppy) regimes. **This is a plausible story, which is precisely
why it must be pre-registered with an explicit sign before testing.** If the sign
comes out backwards, the finding is "hypothesis rejected", not "interesting
regime nuance".

## C.5 Lift measurement protocol (identical for all four filters)

For filter `F` with terciles `f ∈ {1,2,3}` and score buckets `q`:

1. **Conditional lift:** `Λ_{q,f} = HitRate_{q,f} − BaseRate_{fold,f}`. Note the
   baseline is conditioned on the filter tercile too — otherwise the filter's own
   unconditional effect is misattributed to the score.
2. **Interaction test (the real test):** the question is not "is the score good in
   cell (q,f)" but "does `F` change the score's slope". Fit, per fold:

   ```
   r_norm(t+1) = a + b1*DQ_t + b2*F_t + b3*(DQ_t * F_t) + e
   ```

   with HAC standard errors. `b3` is the claim. A significant `b1` with an
   insignificant `b3` means the filter adds nothing and is discarded.
3. **Net economic lift:** Δ(net expectancy per trade, bp) and Δ(total net PnL) on
   the existing edge's trade set, with the filter applied — both, always. A filter
   that raises per-trade expectancy while destroying total PnL has just made the
   strategy smaller, not better.
4. **Matched-count random-filter baseline — mandatory.** Any filter that removes
   `x%` of trades is compared against 1,000 random filters removing the same `x%`
   from the same trade set. Report the percentile of the real filter in that
   distribution. **A filter below the 95th percentile of random filters has not
   demonstrated skill**, regardless of its raw improvement. This is the single
   most effective test against "filtering improved things" illusions and is a hard
   gate in D.9.
5. **Consistency:** fraction of OOS folds with positive net lift. Reported
   alongside the pooled mean, always. A pooled mean driven by two folds out of
   forty is a regime artefact.
6. **Cell-count discipline:** report `n` for every cell. Any cell below the B.3.7
   power requirement is labelled "underpowered" in the table and may not carry a
   conclusion.

## C.6 Interaction with the Stage B predictability results

Gated sequence — do not proceed to a step until the prior one passes:

- If **B.3 produces no significant IC anywhere**, Stage C is still run, but only
  in filter-on-existing-edge form (C.5.3–C.5.4). The score-predictivity path is
  closed and reported closed.
- If B.3 produces IC only within a single filter tercile, that is a *conditional*
  finding requiring its own out-of-sample confirmation on data not used in B.3
  (D.3 reserves a final holdout for exactly this).
- Combining filters is permitted only after each has independently passed C.5's
  interaction test. Maximum **two** filters combined — with four filters, three
  terciles and ten score buckets, a three-filter combination creates 1,080 cells
  and guarantees spurious winners.
- Every filter tested adds to `N_trials`: 4 filters × 3 terciles × 12 scores is
  the enumeration ceiling, and the D.4 correction is applied over the whole
  declared family.

---

# 3. Stage D — Statistical Robustness Protocol

## D.1 Walk-forward evaluation — exact specification

### D.1.1 Windows

| Parameter | Value | Rationale |
|---|---|---|
| Training / estimation window | **126 sessions** (≈ 6 months) | ≈ 9,800 five-minute bars — enough for the fitted models, short enough to be regime-local |
| Out-of-sample window | **21 sessions** (≈ 1 month) | ≈ 1,640 bars per fold |
| Step | **21 sessions** | non-overlapping OOS, no bar scored twice |
| Minimum history required | **≥ 5 years** | yields **≥ 48 non-overlapping OOS folds** |
| Warm-up | 500 bars + 100 sessions before the first training window | percentile and ATR windows fully populated |

Both **rolling** (fixed 126-session lookback) and **anchored/expanding** (all
history to date) variants are run. Divergence between them is diagnostic:
anchored ≫ rolling implies the relationship is stable and slow; rolling ≫
anchored implies regime-local and fragile. Report both; the **weaker of the two**
is what the decision gates are applied to.

### D.1.2 The OOS record

Concatenate all 48+ OOS windows into a single out-of-sample track record. All
headline metrics are computed on this track only. In-sample figures appear in
appendices, labelled in-sample, and are never cited in a decision.

### D.1.3 Purge and embargo

- **Purge:** remove training observations whose target horizon `h` overlaps the
  test window start. For `h = 3` bars, purge the last 3 training bars.
- **Embargo:** drop **one full session** after each test window before training
  resumes. Intraday series carry overnight and multi-day autocorrelation;
  a bar-level embargo is insufficient.
- Feature lookbacks (500-bar percentile, ATR-100) mean training-window features
  can reach back across a boundary. That direction is harmless (past reaching
  further past). The forbidden direction — test features reaching into training
  targets — is eliminated by the purge. Assert both directions in code.

### D.1.4 Combinatorial purged cross-validation (secondary)

Run CPCV with `N = 12` groups, `k = 2` test groups per combination (66 paths) to
produce a *distribution* of OOS outcomes rather than a single path. Report the
5th percentile path alongside the mean. A strategy whose 5th-percentile path is
negative is fragile regardless of its mean. CPCV supplements, and does not
replace, the chronological walk-forward — only the chronological path reflects
deployable reality.

## D.2 Regime splits

Every headline result is decomposed across these pre-registered cells. Splits are
defined on information available **before** the session begins, so the split
itself carries no look-ahead.

| Split | Definition (all knowable ex ante) |
|---|---|
| Volatility | terciles of prior-20-session realised vol, assigned at session open |
| Direction | prior 20-session return sign, and prior 60-session return sign |
| Trendiness | prior-session `EFF_RATIO` terciles |
| Earnings proximity | −2 to +2 sessions around a scheduled report, using the **as-known-then** announcement calendar, not the restated one |
| Macro events | FOMC, CPI, NFP session flags from a fixed calendar |
| Intraday phase | first 15 min / midday / last 15 min |
| Session type | full session vs half session (holidays) |
| Unclean opening range | per the D.8 objective definition |

**Requirement:** the result must be positive in **≥ 3 of the 4 volatility ×
trend regime cells**, and no cell may be worse than −50% of the pooled mean.
A result that lives in one regime cell is a regime bet, not a candle score, and
must be reported and treated as such.

## D.3 Final holdout

The most recent **12 months** of data are sealed at the start of the project.
They are used exactly **once**, at the very end, for the configuration that has
already passed every gate. If the holdout contradicts the walk-forward result,
the verdict is **discard** — not "investigate why". A second look at the holdout
converts it into training data and destroys its only purpose.

## D.4 Multiple testing and the trial count

### D.4.1 Declared trial count

`N_trials` is enumerated in the pre-registration:

```
12 scores  ×  3 targets  ×  3 horizons                     = 108   (Stage B)
12 scores  ×  4 filters  ×  3 terciles                     = 144   (Stage C)
pre-registered variants (rho, gamma, additive form, k_or)  ≈  20
                                                    total  ≈ 272
```

Every executed test increments the counter, including tests that were run and
abandoned. **The counter is append-only and lives in version control.** A test
that was run and not reported is the definition of p-hacking.

### D.4.2 Corrections

- **Benjamini–Hochberg FDR at q = 0.10** across the declared family for the
  hypothesis-testing layer.
- **Autocorrelation and overlap:** Newey–West HAC standard errors with
  `lag = h − 1 + 78` (one session) for all regression t-statistics; **stationary
  block bootstrap** (Politis–Romano) with expected block length of one session
  (78 bars at 5-min) and 10,000 resamples for all CIs on hit rates, IC and
  expectancy.
- **Strategy selection bias:** where a best-of-`N` configuration is chosen, report
  **Deflated Sharpe Ratio** (Bailey & López de Prado) using the actual `N_trials`
  and the observed variance of trial Sharpes, and **Hansen's SPA** test against
  the benchmark set. A raw Sharpe on a selected configuration is not admissible
  evidence.
- **Cross-sectional dependence:** cluster standard errors by session date, since
  contemporaneous bars across instruments are strongly correlated.

## D.5 Threshold stability

No threshold is *selected*. The **entire response surface is reported**:

1. Net metric plotted against score threshold across the full 0–100 percentile
   range in 1-point steps, per fold and pooled.
2. **Plateau requirement:** the operating point must sit inside a contiguous band
   of ≥ **20 percentile points** over which the net metric stays within **±25%**
   of its value at the operating point. A peak narrower than 20 points is a
   **hard kill**.
3. **Perturbation test:** shift the threshold ±10 percentile points. Net metric
   must remain positive and above the D.9 gate at both perturbed points.
4. Thresholds are always expressed in **trailing-percentile space**, re-derived
   per fold, never as fixed raw score values. A fixed raw threshold silently
   embeds the full-sample distribution — a subtle but total look-ahead.
5. Report the *dispersion of the fold-wise optimal threshold*. If the per-fold
   optimum wanders across more than 30 percentile points, the parameter is not
   estimable and the configuration is discarded.

## D.6 Point-in-time universe

**Default recommendation: avoid the problem rather than solve it badly.**

- **Preferred universe:** index futures and large-liquid ETFs (ES/NQ, SPY/QQQ/IWM)
  plus a fixed list of continuously listed mega-caps. These have no survivorship
  problem because there is no membership selection.
- **If single-name breadth is required**, it must use a genuine point-in-time
  constituent history including delisted and removed tickers (CRSP, Norgate,
  Sharadar, or equivalent), with:
  - membership `as of` each date, never today's index membership backfilled;
  - delisted names retained through their final trading day, with the delisting
    return applied;
  - ticker-recycling handled by permanent security identifier (PERMNO / FIGI),
    never by ticker string;
  - liquidity screens applied with **trailing** data only (e.g. prior-20-session
    median dollar volume ≥ threshold), never with full-period averages.
- **If a point-in-time universe is unavailable, single names are not used.**
  Running the study on today's index members and disclosing the caveat is not an
  acceptable substitute — the bias is large and upward, and a disclosure does not
  remove it from the numbers.
- Free retail feeds (including Yahoo) do not provide point-in-time membership and
  silently drop delisted tickers. This is stated here so the constraint is not
  rediscovered halfway through.

## D.7 Cost model — full specification

Round-trip cost applied to every simulated trade:

```
c_rt = 2 * (half_spread + slippage + fees) + impact
```

| Component | Specification |
|---|---|
| `half_spread` | Median quoted spread / 2, measured **per instrument, per intraday time-of-day slot, per volatility tercile** — not one global number. Opening-15-minute spreads are multiples of midday spreads. |
| `slippage` | Marketable-limit assumption: cross the spread, plus adverse-selection add-on of `0.05 × R_t` for entries triggered by a directional signal |
| `fees` | Actual commission and exchange/regulatory fees per share/contract, converted to bp at the traded price |
| `impact` | For sizes above 1% of the bar's volume: square-root impact `k · σ_bar · √(size / ADV_bar)`. Below that, zero. Position sizing must be stated; unstated size means unstated cost. |
| Borrow | Short trades: overnight borrow if held across the close; intraday shorts require locate availability — names with no locate are excluded via a **point-in-time** locate proxy, or shorts are excluded entirely and that is stated |

**Sensitivity requirement:** every headline metric is reported at **1×, 2× and 3×**
the base cost model. **The configuration must remain above the D.9 gate at 2×.**
Cost estimates are the least reliable input in any intraday study, and a result
that dies between 1× and 2× is not a result.

Fill assumptions: entries at the next bar's open with slippage, or at the decision
bar's close only if the strategy can realistically transact at the close (it
usually cannot). Assume the pessimistic side of any ambiguity, and state which was
used.

## D.8 The practical case — ORB "wait vs take"

### D.8.1 Objective definition of "unclean" (fixed before testing)

An opening-range setup at breakout bar `t` is flagged **unclean** if **≥ 2** of
these hold — all computable at `t`:

```
1. OR_range / ATR_20(prior session) > 1.5          (abnormally wide OR)
2. mean overlap ratio of the OR bars > 0.70        (congestion, no displacement)
3. count of prior OR-boundary crosses in session >= 2   (prior failed breaks)
4. RVOL at the breakout bar < 1.0                  (unconfirmed participation)
5. |EFF| of the OR bars < 0.25                     (churn, no progress)
```

The threshold `2` and the five component thresholds are pre-registered. The
cleanliness definition may not be re-tuned after seeing results — if it is, the
study restarts on fresh data.

### D.8.2 The test

On the existing edge's ORB signal set, restricted to signals flagged unclean:

- **Arm 1 (control):** take every unclean signal. Net expectancy, net total PnL,
  hit rate, MAE/MFE distribution.
- **Arm 2 (score filter):** take only unclean signals whose breakout-bar candle
  score (or 2–4 bar group score) exceeds the trailing percentile operating point.
  Skipped signals produce no trade.
- **Arm 3 (matched-count random skip):** skip the same number of signals at
  random, 1,000 draws. This is the benchmark Arm 2 must beat.
- **Arm 4 (delayed entry variant):** wait for the next bar whose score qualifies,
  with a hard maximum wait of 3 bars and a defined invalidation (price returns
  inside the OR), then take. Compare against Arm 1.

### D.8.3 What a positive answer requires — all four, or it is negative

1. The **skipped** subset must have net expectancy significantly **below zero**
   (or below the cost hurdle) — one-sided test, block-bootstrap CI. Filtering out
   trades that were merely *less profitable* destroys total PnL and is not a win.
2. Arm 2 must exceed the **95th percentile** of the Arm 3 random-skip
   distribution.
3. Net **total** PnL must not fall by more than 10% relative to Arm 1 while
   per-trade expectancy rises — otherwise the filter is shrinking the strategy,
   and the same effect is available by trading smaller.
4. Positive net lift in ≥ 60% of the OOS folds, and in ≥ 3 of 4 volatility ×
   trend regime cells.

### D.8.4 The negative answer, written in advance

If the skipped subset's net expectancy is statistically indistinguishable from
the taken subset's, the conclusion is: **"the continuous candle score does not
discriminate outcome quality on unclean ORB setups; do not use it as a wait/take
filter."** This sentence is pre-committed so that a null result has somewhere to
go other than into a re-specification loop.

## D.9 Decision gates — pre-registered, numeric, applied to OOS only

Applied to the concatenated walk-forward OOS track (D.1.2), at **2× base cost**,
on the **weaker** of the rolling/anchored variants.

### KEEP as an enhancement — **all** of the following

| # | Gate |
|---|---|
| K1 | Net per-trade expectancy on the existing edge improves by **≥ 15%** relative **and** by an absolute margin ≥ 1× the round-trip cost |
| K2 | Beats the matched-count random filter at the **≥ 95th percentile** (C.5.4) |
| K3 | Positive net lift in **≥ 60%** of OOS folds |
| K4 | Positive in **≥ 3 of 4** volatility × trend regime cells; no cell worse than −50% of pooled mean |
| K5 | Survives at **2×** base cost (D.7) |
| K6 | Threshold plateau **≥ 20** percentile points, and ±10-point perturbation stays above gate (D.5) |
| K7 | Deflated Sharpe Ratio p < 0.05 at the declared `N_trials`; survives BH-FDR at q = 0.10 |
| K8 | Total net PnL does not fall > 10% vs. the unfiltered existing edge |
| K9 | Confirmed on the sealed 12-month holdout (D.3), single look |

### CONDITIONAL — further work, on new data only

Fails **≤ 2** of K1–K8, fails **none** of the hard kills below, and the direction
of the effect is consistent with the pre-registered hypothesis.
Permitted next steps: collect more data; extend the OOS period; test on a
pre-registered adjacent instrument set.
**Not permitted:** re-weighting the score, re-cutting thresholds, re-defining
"unclean", adding features, or changing the target — any of these restarts the
study with a new pre-registration and requires fresh out-of-sample data.

### DISCARD — **any single** hard kill

| # | Hard kill |
|---|---|
| D1 | Pooled OOS mean \|IC\| < 0.005, or IC t-statistic < 1.5 |
| D2 | Net lift ≤ 0 at **base** (1×) cost |
| D3 | Fails the matched-count random-filter test (below 95th percentile) |
| D4 | Positive-fold fraction < 50% |
| D5 | Threshold plateau < 20 percentile points, or per-fold optimal threshold dispersion > 30 points |
| D6 | Composite fails the B.3.6 parsimony gate **and** no single component passes independently |
| D7 | Effect confined to one regime cell |
| D8 | Holdout contradicts walk-forward |
| D9 | The harness fails any D.10 validation test — everything is void until the harness is fixed and all results are re-run |

**Discard is the default verdict.** The study ends in discard unless every KEEP
gate is met. There is no "promising, keep watching" outcome — that category is
where dead strategies go to consume attention.

## D.10 Harness validation — run before any real result is believed

These four tests validate the *pipeline*, not the strategy. They are the highest-
value safeguards in this document, because a leaking harness makes every other
protection cosmetic.

**D.10.1 Synthetic null test.** Run the entire pipeline end to end on:
(a) the real bars with forward returns randomly shuffled within each session;
(b) fully synthetic bars generated from a random walk with realistic intraday vol
seasonality and no embedded predictability.
**Expected: zero significant edge in both.** If the pipeline reports a
significant edge on data that contains none, the pipeline is broken. This is a
gate, not a diagnostic — no real result may be reported until it passes.

**D.10.2 Leakage canary.** Inject two synthetic features into the feature block:
- `canary_future = r_norm(t+1)` (pure future information)
- `canary_noise` = i.i.d. random

**Expected:** the future canary shows an enormous IC and AUC near 1.0; the noise
canary shows IC ≈ 0. If the future canary does **not** dominate, the target
alignment is wrong. If the noise canary shows significant IC, the significance
machinery is miscalibrated. Both directions must pass.

**D.10.3 Shift-invariance test.** Re-run the entire study with every feature
additionally lagged by one bar. Results should degrade *gracefully*. If they
degrade to nothing, the "edge" was contemporaneous-bar leakage. If they do not
degrade at all, the features are slow-moving and the effective sample size is far
smaller than the bar count suggests — recompute `n_eff`.

**D.10.4 Reproducibility.** Fixed random seeds, pinned library versions, and a
recorded data snapshot hash. Two independent runs must produce byte-identical
results. Vendors silently revise historical intraday bars; without a snapshot
hash, an irreproducible result cannot be distinguished from a leaking one.

---

# 4. Recommended Testing Order

Ordered so that the cheapest tests can kill the idea first. **Each step has an
explicit stop condition — if it triggers, stop and write the discard memo.**

| Step | Work | Stop condition |
|---|---|---|
| **0** | Pre-registration committed; `N_trials` enumerated; decision gates frozen | — |
| **1** | Data integrity: timestamp convention, adjustment convention, degenerate-bar audit, spread/cost measurement per slot and vol tercile | > 5% degenerate bars, or unverifiable timestamp convention |
| **2** | Cost hurdle arithmetic (§0.2) and power calculation (B.3.7) against the actual available sample | Required `n_eff` unreachable → **"underpowered, no conclusion"** |
| **3** | **Harness validation (D.10.1–D.10.4)** | Any failure → fix and restart; no results are valid |
| **4** | Unconditional base rates by instrument, time-of-day, regime; Tier-1 feature distributions; collinearity and PCA (B.1.2) | — |
| **5** | Single-bar IC on `r_norm`, walk-forward (B.3.2). Full response curve, no thresholds yet | D1 triggers → **discard the standalone path**, proceed to step 8 only |
| **6** | Group scores `k ∈ {2,3,4}`, three methods; parsimony ladder (B.2, B.3.6) | No group score beats single-bar → drop group layer, continue with single-bar |
| **7** | 1-min → 5-min incremental test (B.3.3 b-i) | No incremental IC → drop the 1-min layer and report it dropped |
| **8** | **Filter-on-existing-edge test** — the live hypothesis. Score applied to the existing edge's trade set; matched-count random baseline (C.5.3–C.5.4) | D2 or D3 triggers → **discard** |
| **9** | Extreme vs moderate response shape (B.3.5) | — |
| **10** | Context filters, **one at a time**, interaction tests (C.1–C.5) | Filters with insignificant `b3` are dropped and recorded as dropped |
| **11** | ORB unclean wait/take test (D.8) | D.8.3 conditions unmet → report the D.8.4 negative answer |
| **12** | At most two filters combined; full regime decomposition (D.2); cost sensitivity 1×/2×/3× | — |
| **13** | Threshold response surface and stability (D.5) | D5 triggers → **discard** |
| **14** | Deflated Sharpe / SPA at declared `N_trials`; BH-FDR (D.4) | K7 fails → **discard** |
| **15** | Sealed holdout, single look (D.3) | Contradiction → **discard** |
| **16** | Decision memo: KEEP / CONDITIONAL / DISCARD, with every gate's value tabulated | — |

Note the deliberate ordering of steps 5 and 8: the standalone predictivity test
comes first because it is cheap and most likely to fail, but a failure there does
**not** end the study — it closes the standalone path while leaving the filter
hypothesis open. Only D2/D3 at step 8 kills the whole idea.

---

# 5. Key Warnings and Failure-Mode Coverage

## 5.1 Failure modes and their specific safeguards

| Failure mode | How it appears | Safeguard in this design |
|---|---|---|
| **Look-ahead via off-by-one** | `.shift()` sign errors; vendor bar-timestamp convention misread | Single shift function, unit-tested (B.3.8.3); explicit convention assertion (B.3.8.5); leakage canary (D.10.2) |
| **Look-ahead via normalisation** | full-sample `mean`/`std`/`quantile` in scaling or thresholds | Trailing-only windows (B.1.5); percentile-space thresholds re-derived per fold (D.5.4); no `fit_transform` on full data (B.1.5) |
| **Look-ahead via higher timeframe** | reading the *current, incomplete* HTF bar | Base-timeframe EMA formulation (C.1); `close_time <= t` assertion |
| **Look-ahead via ATR in own bar** | `ATR` window includes bar `t` when normalising bar `t` | ATR windows end at `t−1` (B.1.3, B.3.8.2) |
| **Survivorship bias** | today's index members backfilled | PIT constituents with delisted names, or ETF/futures universe (D.6); free-feed limitation stated up front |
| **Narrow-window bias** | one favourable backtest period | ≥ 48 non-overlapping OOS folds (D.1); consistency ratio reported (C.5.5); regime decomposition (D.2); CPCV 5th-percentile path (D.1.4) |
| **Cost bias** | gross numbers, or a single global spread | Per-slot, per-vol-tercile cost model (D.7); no gross-only summary tables; 2× cost survival gate (K5) |
| **Narrative bias** | "it works in trends because momentum" — written after the fact | All hypotheses signed with a direction before testing (C.1–C.4); a reversed sign is a rejection, not a nuance |
| **Selection / p-hacking** | quiet iteration until something works | Append-only `N_trials` counter in version control (D.4.1); DSR and SPA at the true trial count; re-specification requires a new pre-registration and fresh data |
| **Threshold overfitting** | one magic percentile cut | Full response surface, plateau ≥ 20 points, ±10-point perturbation (D.5) |
| **Fake filter improvement** | removing trades raises average, looks like skill | Matched-count random-filter baseline as a **hard gate** (C.5.4, K2, D3) |
| **Pseudo-replication** | 100,000 correlated bars treated as 100,000 independent observations | `K_eff` cross-sectional deflation, session-clustered errors, block bootstrap, HAC (B.3.7, D.4.2) |
| **Silent bar deletion** | dropping doji/degenerate bars breaks the forward clock and shifts the baseline | Flag-don't-drop (B.1.4); baseline recomputed on the identical filtered set |
| **Irreproducibility** | vendor revises history; result cannot be re-derived | Data snapshot hash, pinned versions, fixed seeds (D.10.4) |
| **The agreeable-AI failure** | the analyst (human or model) finds what the sponsor wants | Discard is the default verdict (D.9); the negative conclusion is written before testing (D.8.4); every gate is numeric and pre-committed |

## 5.2 Warnings to carry into the work

1. **The cost hurdle in §0.2 is probably the whole answer for the standalone
   question.** Any test that appears to show a profitable standalone next-bar
   candle strategy on a liquid instrument should be treated as evidence of a bug
   until D.10 has been re-run and passed.

2. **`n_eff`, not `n`.** Intraday studies feel data-rich and are not. 100,000
   correlated bars across 10 correlated names may carry the statistical weight of
   fewer than 15,000 independent observations. Every confidence interval in this
   framework depends on getting this right.

3. **The 1-min → 5-min test overlaps itself.** The last five 1-min bars *are* the
   5-min bar. Only the incremental form (B.3.3 b-i) answers the question asked;
   the standalone form will look impressive and mean nothing.

4. **A filter that improves per-trade expectancy while cutting total PnL has not
   improved anything.** Both metrics, always, side by side (C.5.3, K8).

5. **Doji handling is a silent baseline-shifter.** Encoding a degenerate bar's
   score as `0` rather than `NaN` inserts a phantom cluster at the exact centre
   of the score distribution — which is where the "moderate score" bucket lives
   in test (d). This one bug can manufacture the entire extreme-vs-moderate
   finding.

6. **Time-of-day is a confounder in nearly every intraday feature.** Volume,
   range, spread and base rate all have strong intraday seasonality. Any feature
   not normalised by time-of-day slot risks being a clock in disguise, and any
   "edge" it shows is an intraday seasonality effect that costs more to trade
   than it pays.

7. **Re-specification is not iteration.** Changing the score, the threshold, the
   filter definition or the target after seeing results is a new study. It needs
   a new pre-registration and out-of-sample data that has not been looked at.
   The sealed holdout (D.3) exists to make this expensive, which is the point.

8. **Expect discard.** The framework is built so that a negative result is a
   complete, publishable, decision-ready output — not a failure to be worked
   around. If the study cannot end in "discard", it was not a test.

---

## Appendix — Pre-registration template

```yaml
prereg_version: 1
committed_at: <ISO timestamp>
git_commit: <hash of this file at freeze time>

data:
  instruments: []
  base_timeframe: 5min
  secondary_timeframe: 1min
  period: {start: , end: }
  holdout_sealed: {start: , end: }        # last 12 months, single look
  vendor: 
  bar_timestamp_convention: open_labelled | close_labelled
  adjustment_convention: multiplicative | additive
  snapshot_hash: 

features:
  tier1: [BD, CL, SA, WB, OL, CONV]
  tier2: [RNG_Z, RNG_P, GAP, BODY_ATR]
  degenerate_gate: {k_tick: 2.0, k_vol: 0.10, atr_n: 20}

scores:
  analytic: {weights: equal, gamma: 1.0}
  group: {methods: [agg, merge, geo], k: [2,3,4], rho: 0.70}
  fitted: {models: [logit_l2, gbm_depth3], inner_cv: purged}
  normalisation: {type: trailing_percentile, window: 500, tod_bucketed: true, min_obs: 250}

targets: {binary: [y_cc, y_body], continuous: [r_norm], horizons: [1,2,3]}

walk_forward: {train: 126, test: 21, step: 21, embargo: 1 session, purge: h-1 bars}

costs:
  model: per_slot_per_voltercile
  sensitivity: [1.0, 2.0, 3.0]
  gate_multiplier: 2.0

hypotheses:                                # signed BEFORE testing
  - {id: H1, statement: , predicted_sign: , test: }

n_trials_declared: 272
decision_gates: {keep: [K1..K9], discard: [D1..D9]}
negative_conclusion_text: <D.8.4 sentence, written now>
```
