# Stage 1 — Pure Predictivity Test for a Continuous Candle Score

**Owner:** Lambda (Strategy Validator)
**Status:** Design specification. Nothing has been tested. No number below is a
result — every figure is a definition, a threshold, or a power calculation.

**The single question this stage answers:**

> Does a continuous score built only from a candle's (or a 2–4 bar group's)
> internal OHLC geometry contain any statistically detectable information about
> the direction or signed magnitude of the near-term future, before any decision
> boundary is involved?

**Explicitly out of scope for Stage 1** — no existing edge, no entry/exit rules,
no position sizing, no trade counts, no P/L, no context filters, no fitted
models. Those belong to the later stages in
`CANDLE_SCORING_VALIDATION_FRAMEWORK.md`, which is only reached if Stage 1
returns "predictivity detected".

---

## 0. Design premises, fixed before any data is touched

**0.1 Zero fitted parameters.** Every constant in this design (weights, `rho`,
`gamma`, window lengths, bucket counts) is fixed at pre-registration and is a
*null* choice — equal weights, unit exponents, round numbers. Nothing is
optimised.

This matters more than it looks. **With no fitting, there is no train/test
leakage surface at all.** The only remaining leakage surfaces are (a) feature
causality and (b) target alignment. That collapses the anti-cheating problem from
a large one to two auditable ones, and it is why Stage 1 needs no walk-forward
train/test split — only non-overlapping evaluation blocks (§4.1).

**0.2 Realistic expectation, pre-registered.** A genuine effect here is **1–3
percentage points** of lift, or an information coefficient of **0.01–0.03**.
This is written down now so it constrains interpretation later:

| Observed effect | Pre-registered interpretation |
|---|---|
| IC < 0.01, lift < 1pp | Below the detection floor — **no useful predictivity** |
| IC 0.01–0.03, lift 1–3pp | Plausible genuine effect — evaluate against §6 gates |
| IC 0.03–0.05, lift 3–5pp | Unusually strong — **elevated scrutiny**, full §7 audit required |
| IC > 0.05, lift > 5pp | **Treat as a bug until proven otherwise.** Do not report as a finding until every §7 check passes and the leakage canary (§5.6) has been re-run |

A large result on a heavily data-mined public feature set is evidence about the
pipeline, not about the market.

**0.3 The default verdict is "no useful predictivity."** The design must be able
to return that cleanly, and §6 defines it numerically before testing.

**0.4 No trading simulation.** Stage 1 is purely statistical. If any illustrative
P/L is shown, it is labelled illustrative and reported net of a stated cost
assumption — but it carries **no weight** in the §6 decision, because the whole
point of narrowing to Stage 1 is to separate the information question from the
economic question.

---

## 1. Exact scoring formulas

### 1.1 Primitives

For bar `t` with open `O`, high `H`, low `L`, close `C`:

```
R = H - L                  range
B = C - O                  signed body
U = H - max(O, C)          upper shadow
D = min(O, C) - L          lower shadow
```

Assert as a unit test: `|B| + U + D == R` (within float tolerance), and
`L <= min(O,C) <= max(O,C) <= H`.

### 1.2 Components (all scale-invariant, all bounded)

| Symbol | Name | Formula | Range |
|---|---|---|---|
| `BD` | body / range | `B / R` | [−1, 1] |
| `CL` | close location | `(2C − H − L) / R` | [−1, 1] |
| `SA` | shadow asymmetry | `(D − U) / R` | [−1, 1] |
| `WB` | wick burden | `(U + D) / R` | [0, 1] |
| `CONV` | conviction | `1 − WB = \|B\| / R` | [0, 1] |

`CL` is the standard close-location value rescaled to [−1, 1]: `CL = 2·(C−L)/R − 1`.
`+1` means the bar closed exactly on its high.

Upper and lower shadow ratios are recoverable as `U/R = (WB − SA)/2` and
`D/R = (WB + SA)/2`, so they are not listed separately — including them as extra
features would be pure redundancy.

**Mandatory disclosure before any result is reported:** `BD`, `CL` and `SA` are
strongly collinear by construction (expect pairwise |ρ| of 0.7–0.95). Report the
Spearman matrix and PC1 variance share of the standardised `{BD, CL, SA}` block.
If PC1 explains > 80%, state plainly that the composite is one factor with
decoration — and §6 gate G7 then requires the composite to beat its best single
component.

### 1.3 The two continuous scores

**Direction (signed):**

```
DIR_t = (BD_t + CL_t + SA_t) / 3          in [-1, 1]
```

**Conviction (unsigned):**

```
CONV_t = 1 - WB_t = |B_t| / R_t           in [0, 1]
```

**Directional Quality — the primary composite:**

```
DQ_t = DIR_t * CONV_t^gamma * w_range(t)  in (-1, 1),  gamma = 1.0
```

`DIR` and `CONV` are kept as separate exported axes because they are the two axes
of the quadrant analysis in §3.2. `DQ` is their product and is the primary 1-D
score.

*Why `CONV` multiplies rather than adds:* a bar closing near its high on a tiny
body inside a wide range is indecisive, not bullish. Multiplication sends it
toward zero, which is the intended meaning. This is a design choice, not a
claim — the additive form `(DIR + sign(DIR)·CONV)/2` is a pre-registered variant
counted in `N_trials` (§5.5).

### 1.4 Zero-range and near-zero-range bars

Noise floor at bar `t`, using only information through `t−1`:

```
eps_tick = 2.0 * tick_size
eps_vol  = 0.10 * ATR_20(t-1)
eps_t    = max(eps_tick, eps_vol)
```

`ATR_20(t−1)` is Wilder ATR over bars `t−20 … t−1` and **must exclude bar `t`**.

Two mechanisms, both applied:

**(a) NaN, never zero.**

```
if R_t == 0:  BD, CL, SA, WB, CONV, DIR, DQ  =  NaN
```

A degenerate bar's score is *unknown*, not *neutral*. Encoding it as `0` inserts
a phantom cluster at the exact centre of the score distribution — which is
precisely where the "middle bucket" lives in the extreme-vs-middle comparison of
§3.4. This one substitution can manufacture the entire finding.

**(b) Continuous confidence weight.**

```
w_range(t) = R_t / (R_t + eps_t)          in [0, 1)
```

Smooth, no cliff: a near-doji contributes a near-zero score rather than a
violently noisy one (`CL` flips between −1 and +1 on a single tick when `R` is
two ticks wide).

**(c) Hard validity flag** for exclusion from bucket statistics:

```
valid(t) = R_t >= eps_t  and  R_t > 0  and  all(O,H,L,C finite)
           and L <= min(O,C) and H >= max(O,C)
```

Rules:
- Invalid bars are **flagged, never dropped from the index**. Deleting rows
  breaks the forward-return clock and silently changes which bar `t+1` is.
- Invalid bars are excluded from bucket statistics, and their **count and
  percentage are reported in every table**.
- If invalid bars exceed **5%** of a sample, the instrument/timeframe combination
  is too coarse for this study and is dropped with that reason recorded.
- The unconditional baseline (§3.5) is recomputed on the **identical filtered
  set**. Comparing a filtered conditional rate against an unfiltered baseline
  fabricates lift.

### 1.5 Trailing normalisation (required before bucketing)

Raw `DQ` is not comparable across instruments, volatility regimes or times of
day. Convert to a strictly-prior percentile:

```
DQ_pct(t) = fraction of { DQ_s : s in the trailing W valid bars of the same
                          instrument AND the same time-of-day slot, s < t }
            that are strictly less than DQ_t
```

- `W = 500`, minimum 250 observations or `DQ_pct = NaN` (warm-up).
- **Strictly prior.** The current bar is never a member of its own reference
  distribution.
- **Time-of-day bucketing is mandatory intraday.** The 09:35 bar and the 13:30
  bar have different range, body and volume distributions. Pooling them produces
  a score that is substantially a clock, and any "edge" it shows is intraday
  seasonality.
- **Slot width = 30 minutes, not one bar.** This is a correction found by
  running the reference implementation. Bucketing by the *exact* 5-minute slot
  gives 78 groups per session, so a 500-observation reference window needs
  **500 sessions (~2 years) of history per slot** before a single bar is scored —
  on a 300-session sample it left 3,880 of 23,380 valid bars scored, an 83% loss.
  Coarsening to 30-minute blocks (13 groups) recovers 20,130 of 23,380 while
  still removing the intraday seasonality, which is the entire purpose of the
  bucketing. Slot width is a pre-registered constant, not a tuning knob.
- `CONV_pct` and `DIR_pct` are computed the same way, for the quadrant axes.

**A fold-wide or full-sample `quantile()` cut is forbidden.** It embeds the
distribution of data that had not yet happened — a total, and very common,
look-ahead.

### 1.6 Optional short-group score (2–4 bars)

Group `G_k(t) = {t−k+1 … t}`, `k ∈ {2, 3, 4}`, stamped at the **close of bar `t`**.
Two methods only — keep Stage 1 small:

**Method M — merged synthetic candle** (preferred; it is exactly the single-bar
score on a higher timeframe, so it needs no new machinery):

```
O_g = O_{t-k+1}
H_g = max(H_{t-k+1..t})
L_g = min(L_{t-k+1..t})
C_g = C_t
GS_merge(k,t) = DQ(O_g, H_g, L_g, C_g)
```

with `eps_g = max(2·tick, 0.10·ATR_20(t−k))`.

**Method A — recency-weighted aggregate:**

```
GS_agg(k,t) = sum_{i=0..k-1} rho^i * DQ_{t-i}  /  sum_{i=0..k-1} rho^i,   rho = 0.70
```

**Constraint:** a group never spans a session boundary. Groups whose window
crosses the open are excluded and counted.

**Parsimony rule:** a group score is retained only if it beats the single-bar
`DQ` on the primary metric. Extra complexity that does not pay for itself is
discarded, not kept "for completeness".

---

## 2. Forward horizons and targets

### 2.1 Definitions

All measured **from the close of the decision bar `t`** — the only price at which
the information in `DQ_t` exists.

| Target | Formula | Type |
|---|---|---|
| `r_1` | `(C_{t+1} − C_t) / ATR_20(t−1)` | continuous, **primary** |
| `r_2` | `(C_{t+2} − C_t) / ATR_20(t−1)` | continuous |
| `r_3` | `(C_{t+3} − C_t) / ATR_20(t−1)` | continuous |
| `y_h` | `sign(r_h)` for `h ∈ {1,2,3}` | binary direction |
| `y_body` | `sign(C_{t+1} − O_{t+1})` | binary, **diagnostic only** |

**`r_1` is the primary target.** Continuous targets carry magnitude information
and need roughly 3–5× less data than sign tests for the same power (§8).

`y_body` — "does the next candle close bullish" — is the folklore claim, but it
is **not** decidable from `C_t` when `O_{t+1} ≠ C_t`. It is reported as a
diagnostic because the gap between `y_1` and `y_body` results is informative: if
the score predicts `y_body` but not `y_1`, the apparent information sits in the
inter-bar gap and is an artefact of bar construction, not a forecast.

**ATR normalisation uses `ATR_20(t−1)`** — the same causal quantity used in the
noise floor. Normalising by a volatility estimate that includes bar `t+1` would
be a direct leak.

### 2.2 Session-boundary rule (non-negotiable intraday)

```
r_h(t) is defined only if bars t and t+h belong to the SAME session.
```

Otherwise `r_h(t) = NaN`. An overnight gap is not a 5-minute forward return, and
including it injects overnight variance — typically 3–10× a single intraday
bar's — into a small subset of observations, which will dominate every bucket
mean it lands in.

Count and report the excluded end-of-session observations.

### 2.3 Zero-move handling

Exact `C_{t+h} = C_t` is common on 1-minute bars in quiet names.
- **Binary tests:** excluded, count reported, baseline recomputed on the
  identical excluded set.
- **Continuous tests:** retained. A zero return is information.

### 2.4 Overlap warning

`r_2` and `r_3` overlap across consecutive `t`. Every standard error, CI and
t-statistic on `h > 1` **must** use the block bootstrap or HAC treatment in §5.2.
Treating overlapping multi-bar returns as independent inflates t-statistics by
roughly `√h`.

### 2.5 The 1-minute → next 5-minute test

Decision stamp: a 5-minute boundary `T`. Inputs: `GS_merge(m, T)` and
`GS_agg(m, T)` computed on **1-minute** bars for `m ∈ {3, 5}`. Target: `r_1` on
the **next 5-minute bar**, i.e. `(C^{5m}_{T+1} − C^{5m}_T) / ATR^{5m}_20(T−1)`.

Two critical alignment rules:

1. **Vendor timestamp convention must be verified and recorded.** A bar labelled
   `09:35` usually covers `09:35:00–09:35:59` and closes at `09:36:00`. Only
   1-minute bars whose *close* time is `≤ T` are admissible. An off-by-one here
   manufactures a spectacular fake edge and is the most likely single source of a
   large false positive in this whole design.

2. **The last five 1-minute bars ARE the 5-minute bar.** They cover identical
   data. For `m = 5` this is not an independent information source, so the honest
   question is *incremental*:

   - **(i) Standalone:** IC of the 1-minute group score alone.
   - **(ii) Incremental:** partial Spearman of the 1-minute group score with
     `r_1`, **controlling for the 5-minute `DQ_T`**. Equivalently, regress the
     1-min score on `DQ_T`, take the residual, and correlate the residual with
     `r_1`.

   **Only (ii) answers "do the 1-minute bars add anything."** Form (i) will look
   impressive and mean nothing — it is largely re-measuring the 5-minute bar.

---

## 3. Bucketing and quadrant method

Three views, in increasing granularity. All bucket boundaries come from the
**trailing percentiles** of §1.5 — never from the evaluation sample.

### 3.1 View 1 — Signed decile ladder (primary, 1-D)

Ten buckets on `DQ_pct(t)`: `[0,0.1), [0.1,0.2), … [0.9,1.0]`.
Bucket 1 = strongest bearish geometry, bucket 10 = strongest bullish.

This is the primary view because the **shape across the ladder** is the evidence,
not any single bucket. A monotone gradient across ten ordered buckets is hard to
produce by chance; one outperforming bucket amid nine noisy ones is the expected
appearance of no effect.

### 3.2 View 2 — The quadrant (2-D, the requested view)

Two axes, both knowable at the close of bar `t`:

```
X axis: DIR_t          split at 0        (natural, meaningful zero)
Y axis: CONV_pct(t)    split at 0.5      (trailing median, per time-of-day slot)
```

|  | **CONV_pct ≥ 0.5** (decisive) | **CONV_pct < 0.5** (indecisive) |
|---|---|---|
| **DIR > 0** | **Q1 — Clean Bull** | **Q2 — Messy Bull** |
| **DIR < 0** | **Q4 — Clean Bear** | **Q3 — Messy Bear** |

Bars with `DIR = 0` exactly, or `valid = False`, form a reported fifth group
`Q0 — Undefined` and are excluded from the quadrant statistics.

**The pre-registered hypothesis, with signs declared in advance:**

```
H1:  mean r_1 (Q1)  >  mean r_1 (Q2)  >  0  >  mean r_1 (Q3)  >  mean r_1 (Q4)
H2:  the spread [mean r_1(Q1) - mean r_1(Q4)]  >  0
```

`H2` — the clean-bull minus clean-bear spread — is the **headline quadrant
statistic**. It is a difference, so the market's unconditional drift cancels out
of it, which makes it the most robust single number in this design.

If the observed sign is the reverse of `H1`, the result is **"hypothesis
rejected"**. It is not "interesting mean-reversion nuance". Reversed signs are
reported as rejections; re-interpreting them after the fact is exactly the
narrative bias this design exists to prevent.

### 3.3 View 3 — 5×5 response grid (diagnostic)

`DIR_pct` quintiles × `CONV_pct` quintiles = 25 cells. Report mean `r_1`,
concordance, and `n` per cell as a heatmap.

Purpose: read the *shape* of the relationship. Specifically, test whether
conviction amplifies direction — the surface should tilt more steeply along the
`DIR` axis as `CONV` rises. This is a diagnostic only; with 25 cells, individual
cell significance is meaningless and must not be quoted.

### 3.4 Extreme versus middle

Pre-registered, from View 1:

- **Extremes:** `DQ_pct ≤ 0.10` or `DQ_pct ≥ 0.90`
- **Middle:** `0.40 ≤ DQ_pct ≤ 0.60`
- **Statistic:** `|mean r_1|` in extremes vs `|mean r_1|` in middle, and
  concordance in extremes vs middle, both with block-bootstrap CIs.
- **Shape test:** isotonic regression `R²` vs linear `R²` across the 20 ventiles
  of `DQ_pct`, to classify the response as monotone, U-shaped, or noise.

**Power warning, stated in advance:** the 10% tail of a 50,000-bar sample is
5,000 bars — below the requirement in §8 for any lift under ~2pp. If the tail
cell is underpowered, the correct output is **"underpowered — inconclusive"**,
not a point estimate with a confident sign.

### 3.5 Metrics per bucket, and the correct baseline

For each bucket `q`, report: `n`, `n_eff`, invalid-bar %, and:

**(a) Concordance** — probability the forward move agrees with the score's sign:

```
conc_q = P( sign(r_h) == sign(DQ_t) | bucket q ),  zero moves excluded
```

**(b) Mean and median signed return** in ATR units, with block-bootstrap 95% CI.
Report median alongside mean — a mean driven by three bars is not an effect.

**(c) Lift versus the correct unconditional baseline.**

This is the most important and most-often-botched line in the whole design. The
naive baseline of **50% is wrong**, and it is biased in a predictable direction.

If the market drifts up over the sample, `P(r > 0) > 0.5`. If bullish bars are
also more common, `P(DQ > 0) > 0.5`. Then concordance exceeds 50% **with zero
predictivity**, purely from the two marginals. A 5-year US equity sample will
produce exactly this and it looks like an edge.

The correct bucket-conditional baseline:

```
pi_0(q) = f_q * P(r_h > 0)  +  (1 - f_q) * P(r_h < 0)
```

where `f_q` = fraction of bars **in bucket q** with `DQ_t > 0`, and `P(r_h > 0)`,
`P(r_h < 0)` are computed on the **same evaluation block, same filtered set,
same time-of-day mix**.

```
Lift_q = conc_q - pi_0(q)
```

For a pure-bullish bucket (`f_q = 1`) this correctly reduces to
`Lift = conc − P(r>0)`, i.e. the drift is removed rather than harvested.

**(d) Permutation-null position.** Shuffle `DQ_pct` labels within the evaluation
block 1,000 times, preserving both marginal distributions and the time-of-day
mix, recomputing the full bucket statistic each time. Report where the observed
value falls in that null distribution. This is the empirical version of (c) and
it catches baseline errors that the analytic formula misses.

**(e) The zero-crossing bucket is not interpretable.** One decile contains
`DQ = 0` and therefore has a mixed sign (`0 < f_q < 1`). For bars with `|DQ|`
near zero, `sign(DQ)` is set by rounding noise, so concordance in that bucket is
unstable by construction — the reference implementation's null run produces a
−9.0pp "lift" there on data containing no information whatsoever, purely from
this effect.

Rule: **flag the bucket where `0 < f_q < 1` in every table and exclude it from
the monotonicity test and from any conclusion.** It is a boundary artefact, not
a middle-bucket finding. Note this also means the extreme-vs-middle comparison
of §3.4 must use the *magnitude* metric `|mean r_1|` rather than concordance,
since the middle bucket is exactly where sign is least defined.

---

## 4. Evaluation windows

### 4.1 Non-overlapping blocks

Because Stage 1 fits nothing (§0.1), no train/test split is needed. What *is*
needed is proof that the effect is not one favourable period.

```
Partition the full history into consecutive, non-overlapping blocks
of 63 sessions (one calendar quarter).
Compute every statistic independently within each block.
Require >= 20 blocks  (i.e. >= 5 years of history).
```

Report per block: IC, quadrant spread `H2`, extreme-bucket lift, `n`, `n_eff`.

**Headline outputs are the distribution across blocks, not the pooled number:**

- mean and median of the per-block statistic
- **consistency ratio** = fraction of blocks with the pre-registered sign
- the worst block and the best block
- a binomial test on the consistency ratio against `p = 0.5`

A pooled statistic driven by 2 blocks out of 20 is a regime artefact, and the
pooled number alone conceals that completely.

### 4.2 Rolling view (secondary, visual)

Rolling 126-session IC, stepped 21 sessions, plotted over time. Used to spot
regime dependence and structural breaks. Because rolling windows overlap, this
view carries **no independent statistical weight** and no p-value may be quoted
from it.

### 4.3 Sealed holdout

The most recent **12 months** are sealed at project start and looked at **once**,
at the end, for the configuration that has already passed §6. If the holdout
contradicts the blocks, the verdict is **no useful predictivity** — not
"investigate why". A second look converts the holdout into training data and
destroys its only function.

---

## 5. Statistical evaluation

### 5.1 Primary statistic — the information coefficient

```
IC_b = Spearman rank correlation( DQ_t , r_1(t) )   within block b
```

Spearman, not Pearson: rank correlation is immune to the fat tails of intraday
returns, where three news bars can otherwise set the entire result.

Report: `mean(IC)`, `sd(IC)` across blocks, `t = mean(IC) / se(IC)` with `se`
from the block bootstrap, and the consistency ratio.

### 5.2 Dependence handling

- **Stationary block bootstrap** (Politis–Romano), expected block length = one
  session (78 bars at 5-min), 10,000 resamples. Used for every CI on IC,
  concordance, bucket means and the quadrant spread.
- **HAC (Newey–West)** standard errors with `lag = h − 1 + 78` for any regression
  t-statistic.
- **Cluster by session date** where multiple instruments are pooled —
  contemporaneous bars across instruments are strongly correlated.
- **Effective sample size.** Pooling `K` instruments with mean pairwise
  correlation `ρ̄` gives

  ```
  K_eff = K / (1 + (K - 1) * rho_bar)
  ```

  Ten US large-caps at `ρ̄ ≈ 0.30` give `K_eff ≈ 2.7`, not 10. Every `n`, CI and
  t-statistic must be reported on `n_eff`, and `ρ̄` must be estimated and shown.

### 5.3 Monotonicity — the primary shape evidence

Across the ten ordered buckets of View 1:
- **Jonckheere–Terpstra** trend test on `r_1` (p-value)
- **Spearman ρ** between bucket index and bucket mean `r_1`
- **Isotonic vs linear `R²`** on the 20 ventiles

A monotone gradient is the signature of information. A single strong bucket is
the signature of mining.

### 5.4 Permutation null

Every headline statistic — IC, `H2` spread, extreme-vs-middle difference,
per-bucket lift — is accompanied by its position in a 1,000-draw permutation
null built by shuffling scores within block while preserving marginals and
time-of-day mix. Reported as an empirical p-value.

### 5.5 Multiple testing

Declared, append-only trial count, committed to version control:

```
3 scores (DQ single-bar, GS_merge, GS_agg)
  x 4 targets (r_1, r_2, r_3, y_body)
  x 3 bucketing views                            = 36
group k in {2,3,4} and 1-min m in {3,5} variants  ≈ 15
pre-registered form variants (gamma, rho, additive, DIR_pct split)  ≈ 8
                                          N_trials ≈ 59
```

- **Benjamini–Hochberg FDR at q = 0.10** across the whole declared family.
- Every executed test increments the counter, **including tests run and
  abandoned**. A test run and not reported is the definition of p-hacking.
- `N_trials` is frozen at pre-registration. If it needs to grow, the study
  restarts with a new pre-registration.

### 5.6 Pipeline validation — run before any real result is believed

These validate the *code*, not the hypothesis. A leaking pipeline makes every
other safeguard cosmetic. **All four are gates.**

| Test | Procedure | Required outcome |
|---|---|---|
| **Synthetic null** | Run the full pipeline on (a) real bars with `r_1` shuffled within session, and (b) synthetic random-walk bars with realistic intraday volatility seasonality and no embedded predictability | **Zero significant results in both.** Any "edge" found on data containing none means the pipeline is broken |
| **Future canary** | Inject `canary = r_1(t)` as a synthetic score | IC ≈ 1.0. If it is not enormous, the target alignment is wrong |
| **Noise canary** | Inject an i.i.d. random score | IC ≈ 0 and p-values uniform. If it shows significance, the significance machinery is miscalibrated |
| **Shift invariance** | Re-run with every feature lagged one extra bar | Should degrade *gracefully*. Degrading to nothing means the "edge" was contemporaneous-bar leakage. Not degrading at all means the features are slow-moving and `n_eff` is far below the bar count — recompute it |

Plus: fixed seeds, pinned library versions, and a recorded data-snapshot hash.
Two independent runs must produce byte-identical output. Vendors silently revise
historical intraday bars; without a snapshot hash an irreproducible result cannot
be distinguished from a leaking one.

---

## 6. Pre-registered decision criteria

Applied to the block distribution of §4.1, after §5.5 correction, and only once
all four §5.6 gates have passed.

### Verdict A — **PREDICTIVITY DETECTED** (proceed to the filter stage)

**All seven** must hold:

| # | Gate |
|---|---|
| G1 | `\|mean IC\|` across blocks **≥ 0.010** on the primary target `r_1` |
| G2 | IC t-statistic **≥ 3.0** on `n_eff`, block-bootstrap `se` |
| G3 | Consistency ratio **≥ 0.65** of blocks with the pre-registered sign (binomial p < 0.05 at ≥ 20 blocks) |
| G4 | Monotonicity: Jonckheere–Terpstra **p < 0.05** and bucket-index Spearman **ρ ≥ 0.60** |
| G5 | Quadrant spread `H2` **> 0** with block-bootstrap 95% CI excluding zero, **and** the `H1` ordering respected in sign |
| G6 | Survives the permutation null at **p < 0.01**, and BH-FDR at **q = 0.10** |
| G7 | The composite `DQ` beats its best single component (`BD`, `CL`, or `SA`) on mean IC — otherwise the component is promoted and the composite discarded |

The t-threshold is **3.0, not 1.96**, deliberately: with `N_trials ≈ 59` on a
publicly mined feature set, a 2-sigma result is the expected yield of noise.

### Verdict B — **INCONCLUSIVE / UNDERPOWERED**

Available `n_eff` falls short of the §8 requirement for the minimum detectable
effect, **or** the effect direction is consistent but 1–2 gates fail on precision
rather than sign.

Permitted next steps: acquire more history; add weakly-correlated instruments;
extend to more blocks.
**Not permitted:** re-weighting the score, changing `gamma`/`rho`, re-cutting
buckets, changing the target, or adding features. Any of those is a new study
requiring fresh pre-registration and untouched data.

### Verdict C — **NO USEFUL PREDICTIVITY** (default; stop here)

**Any one** of these is sufficient:

| # | Kill condition |
|---|---|
| K1 | `\|mean IC\|` < 0.005, or IC t < 1.5 |
| K2 | Consistency ratio < 0.50 — the sign is a coin flip across blocks |
| K3 | No monotonicity (JT p > 0.10) **and** no significant extreme-vs-middle difference |
| K4 | Quadrant spread `H2` CI includes zero |
| K5 | Observed statistic inside the permutation null's central 95% |
| K6 | Effect present in only one or two of ≥ 20 blocks |
| K7 | Sign is the **reverse** of the pre-registered `H1`, at any strength — a rejected hypothesis, to be reported as such and not re-interpreted |
| K8 | Any §5.6 pipeline gate fails — everything is void until fixed and fully re-run |

**Verdict C is the default.** The study ends in C unless every gate of Verdict A
is met. There is no "promising, worth watching" category — that is where dead
hypotheses go to consume attention.

**Written now, so a null result has somewhere to go:**

> *"A continuous score built from single-candle OHLC geometry shows no
> statistically detectable information about near-term forward returns at the
> tested horizons. The idea is not carried forward to filter testing."*

---

## 7. The most likely ways this test could still cheat

Short list, ranked by probability of actually occurring.

| # | Cheat | Why it happens | Prevented by |
|---|---|---|---|
| 1 | **Timestamp off-by-one** (bar labelled by open vs by close) | Vendor conventions differ and are rarely documented | §2.5 convention assertion at load; future/noise canaries (§5.6); shift-invariance test |
| 2 | **Drift mistaken for skill** — using 50% as the concordance baseline | Upward-drifting samples make concordance > 50% with zero information | The `pi_0(q)` formula in §3.5(c) plus the permutation null in §3.5(d) |
| 3 | **Full-sample quantiles for bucketing** | `df['DQ'].quantile()` is one line and feels harmless | Trailing strictly-prior percentiles only (§1.5); explicit prohibition |
| 4 | **ATR includes the current bar** | Off-by-one in the rolling window used for normalisation | ATR windows end at `t−1` (§1.4, §2.1); asserted in code |
| 5 | **Zeroed doji bars** | `fillna(0)` is the reflex | NaN mandate (§1.4a); invalid-bar counts in every table |
| 6 | **Overnight gaps counted as intraday returns** | `shift(-1)` does not know about session boundaries | Same-session rule (§2.2) |
| 7 | **Time-of-day confounding** | Volume, range, spread and base rate all have strong intraday seasonality; an unnormalised score is partly a clock | Time-of-day-bucketed trailing percentiles (§1.5) |
| 8 | **Pseudo-replication** — 100k correlated bars treated as 100k independent | Intraday data feels abundant and is not | `n_eff` and `K_eff` (§5.2); block bootstrap; session clustering |
| 9 | **Overlap inflation on `r_2`/`r_3`** | Overlapping targets inflate t-stats by ~√h | Block bootstrap and HAC (§5.2, §2.4) |
| 10 | **Silent iteration** — trying variants until one works | No one records the abandoned runs | Append-only `N_trials` in version control (§5.5); BH-FDR; t ≥ 3.0 |
| 11 | **1-min score re-measuring the 5-min bar** | The last five 1-min bars *are* the 5-min bar | Incremental/partial-correlation form only (§2.5.2) |
| 12 | **Post-hoc sign flip** — "it mean-reverts, which also makes sense" | Both signs have a plausible story | Signs pre-registered in `H1`; a reversal is kill condition K7 |
| 13 | **Cherry-picked block** | One good quarter carries the pooled mean | Consistency ratio and worst-block reporting (§4.1); K6 |
| 14 | **Survivorship in the instrument list** | Today's index members backfilled | Use index futures / large ETFs, which have no membership selection (§8.3). Single names require genuine point-in-time constituents including delisted tickers, or they are not used |
| 15 | **Silent data revision** | Vendors restate intraday history | Snapshot hash, pinned versions, fixed seeds (§5.6) |

---

## 8. Minimum data requirements

### 8.1 For the IC test (primary)

Approximately `t ≈ IC · √n`, so `n ≈ (t / IC)²` **effective independent
observations**:

| True IC | `n_eff` for t = 3.0 |
|---|---|
| 0.010 | ≈ 90,000 |
| 0.015 | ≈ 40,000 |
| 0.020 | ≈ 22,500 |
| 0.030 | ≈ 10,000 |
| 0.050 | ≈ 3,600 |

### 8.2 For the bucket concordance test

One-sample proportion, α = 0.05 two-sided, power 0.80, baseline 0.50:

| Lift to detect | `n_eff` **within the bucket** | Total bars if bucket = top decile |
|---|---|---|
| 1.0 pp | ≈ 19,600 | ≈ 196,000 |
| 1.5 pp | ≈ 8,700 | ≈ 87,000 |
| 2.0 pp | ≈ 4,900 | ≈ 49,000 |
| 3.0 pp | ≈ 2,200 | ≈ 22,000 |

Calendar check: 49,000 five-minute bars ≈ **629 US sessions ≈ 2.5 years of a
single instrument** — to detect a 2pp lift in the top decile, before any `n_eff`
deflation.

Note the ~4× advantage of the continuous IC test over the binary concordance
test at the same effect size. **Run the IC test first** (§9).

### 8.3 History budget — corrected arithmetic

An earlier draft of this section said "5 years" and "100 sessions warm-up". Both
were wrong, and the error only became visible when the trailing percentile was
bucketed by time of day (§1.5). The correct calculation:

**Warm-up is measured in sessions, not bars.** The percentile reference window
holds `min_obs` observations *of the same time-of-day slot*. With 30-minute
slots there are 13 slots per session, so reaching `min_obs = 250` takes **250
sessions** — regardless of how many bars per session the instrument has. The
reference implementation confirms this exactly: 300 synthetic sessions × 78 bars
= 23,400 bars, of which 3,250 (= 13 slots × 250) are unscored warm-up, leaving
20,130 scored.

```
warm-up      250 sessions   (min_obs = 250, consumed before the first score)
evaluation  1260 sessions   (>= 20 blocks x 63 sessions, section 4.1)
holdout      252 sessions   (12 months sealed, section 4.3)
                 ----
total       1762 sessions   ~= 7 years per instrument
```

| Requirement | Specification |
|---|---|
| **Minimum history** | **7 years** per instrument at `min_obs = 250` — *not* 5. See the resolution options below |
| Minimum raw bars | **≥ 150,000** five-minute bars of *scored* (post-warm-up) data across the pooled universe |
| Instruments | **3–6**, chosen for **low mutual correlation** — e.g. an equity index future, a rates future, a large-cap FX pair, a liquid crypto pair |
| Universe | Futures and large ETFs preferred — **no survivorship problem, because there is no membership selection**. Free retail feeds do not provide point-in-time index membership and silently drop delisted tickers, so single-name universes are not used unless a genuine PIT constituent history is available |

**Resolution options if 7 years is not obtainable.** These change pre-registered
constants, so **one must be chosen and frozen before Step 0**, not after seeing
results:

| Option | Change | Total history needed | Cost |
|---|---|---|---|
| **A** (default) | keep `min_obs = 250`, `W = 500`, blocks of 63 | ~7 years | none |
| **B** | `min_obs = 125`, `W = 250` | ~6 years | noisier percentile estimates; the score is a rank, so this degrades precision, not validity |
| **C** | blocks of 42 sessions, still ≥ 20 blocks | ~6 years | fewer observations per block, wider per-block CIs |
| **D** | pool more instruments, keep per-instrument history short | unchanged per instrument | **does not work** — blocks are calendar periods, so pooling adds width, not length. §4.1 needs ≥ 20 *time* blocks |

Because nothing in Stage 1 is fitted (§0.1), `min_obs` and `W` are precision
parameters rather than overfitting risks — but they are still pre-registered
constants, and changing them after seeing a result is a new study.

**Option D is called out explicitly because it is the tempting wrong answer.**
Adding instruments raises `n` per block and helps the power calculations of §8.1
and §8.2; it does nothing for the ≥ 20-block consistency requirement, which is
the safeguard against a single favourable period. Short history cannot be bought
with breadth.

**On pooling:** adding ten correlated US large-caps is close to useless — `K_eff`
lands near 2.7 (§5.2). Adding four weakly-correlated instruments across asset
classes genuinely multiplies the sample. The trade-off is that the effect may not
be homogeneous across them, so **report per-instrument IC alongside the pooled
figure**. If the effect exists in one instrument only, that is a K6-style
single-regime finding, not a general property of candle geometry.

**Realistic assessment:** with 5 years across 4 weakly-correlated instruments
(≈ 390,000 raw bars, `n_eff` plausibly 120,000–200,000 after deflation), this
design can reliably detect an IC of **≥ 0.015** and a top-decile lift of
**≥ 1.5pp**. Effects smaller than that are **not detectable with this data**, and
the honest output in that case is Verdict B, not a hopeful point estimate.

---

## 9. Recommended execution order

Cheapest kills first. Each step has an explicit stop condition.

| Step | Work | Stop condition |
|---|---|---|
| 0 | Pre-registration committed: formulas, constants, `H1` signs, `N_trials`, §6 gates, Verdict C sentence | — |
| 1 | Data integrity: timestamp convention, adjustment convention, session calendar, invalid-bar audit | > 5% invalid bars, or unverifiable timestamp convention |
| 2 | `n_eff` / `K_eff` estimation vs §8 requirement | Below requirement → **Verdict B, stop** |
| 3 | **Pipeline validation (§5.6) — all four gates** | Any failure → fix and restart; no result is valid before this |
| 4 | Marginal distributions: `P(r_h > 0)`, `P(DQ > 0)`, time-of-day base rates, collinearity + PC1 | — |
| 5 | **Single-bar `DQ` IC on `r_1`**, per block (§5.1) — the cheapest decisive test | K1 or K2 triggers → **Verdict C, stop** |
| 6 | View 1 decile ladder + monotonicity (§3.1, §5.3) | K3 triggers → **Verdict C, stop** |
| 7 | View 2 quadrant, `H1`/`H2` (§3.2) | K4 or K7 triggers → **Verdict C, stop** |
| 8 | Extreme vs middle, ventile response curve (§3.4) | — |
| 9 | Horizons `r_2`, `r_3`, with overlap correction | — |
| 10 | Group scores `k ∈ {2,3,4}`; retained only if they beat single-bar `DQ` | — |
| 11 | 1-min → 5-min **incremental** test (§2.5.2) | No incremental IC → drop the 1-min layer, record it dropped |
| 12 | View 3 5×5 grid (diagnostic), per-instrument IC breakdown | — |
| 13 | Permutation nulls, BH-FDR at declared `N_trials` (§5.4, §5.5) | G6 fails → **Verdict C** |
| 14 | Sealed holdout, single look (§4.3) | Contradiction → **Verdict C** |
| 15 | Verdict memo: every gate tabulated with its observed value | — |

Step 5 is the whole study in compressed form. If the mean IC across 20 blocks is
0.002 with a consistency ratio of 0.55, the answer is already known and steps
6–15 are documentation.

---

## Appendix A — Pre-registration template

```yaml
prereg_version: 1
stage: 1_predictivity_only
committed_at: <ISO timestamp>
git_commit: <hash of this file at freeze>

data:
  instruments: []                       # 3-6, low mutual correlation
  base_timeframe: 5min
  secondary_timeframe: 1min
  period: {start: , end: }
  holdout_sealed: {start: , end: }       # last 12 months, single look
  vendor:
  bar_timestamp_convention: open_labelled | close_labelled   # VERIFY, do not assume
  adjustment_convention: multiplicative | additive
  session_calendar_source:
  snapshot_hash:

score:
  components: [BD, CL, SA, WB, CONV]
  DIR: mean(BD, CL, SA)                  # equal weights, fixed
  CONV: 1 - WB
  DQ: DIR * CONV^gamma * w_range
  gamma: 1.0
  degenerate_gate: {k_tick: 2.0, k_vol: 0.10, atr_n: 20}
  zero_range_policy: NaN                 # never 0
  normalisation: {type: trailing_percentile, window: 500,
                  tod_bucketed: true, min_obs: 250, strictly_prior: true}
  group: {methods: [merge, agg], k: [2,3,4], rho: 0.70,
          cross_session: forbidden}

targets:
  primary: r_1
  continuous: [r_1, r_2, r_3]
  binary: [y_1, y_2, y_3]
  diagnostic_only: [y_body]
  atr_normaliser: ATR_20(t-1)
  same_session_required: true
  zero_move_policy: {binary: exclude, continuous: retain}

bucketing:
  view1: {type: decile, on: DQ_pct}
  view2: {type: quadrant, x: sign(DIR), y: CONV_pct >= 0.5}
  view3: {type: grid_5x5, x: DIR_pct, y: CONV_pct, diagnostic_only: true}
  extremes: [0.00-0.10, 0.90-1.00]
  middle: [0.40-0.60]
  baseline_formula: "pi_0(q) = f_q*P(r>0) + (1-f_q)*P(r<0)"

evaluation:
  blocks: {length_sessions: 63, min_blocks: 20, overlapping: false}
  rolling_view: {window: 126, step: 21, statistical_weight: none}
  bootstrap: {type: stationary_block, mean_block: 78, resamples: 10000}
  permutation: {draws: 1000, preserve: [marginals, time_of_day_mix]}
  n_eff_required: true

hypotheses:                              # SIGNS FIXED BEFORE TESTING
  H1: "mean r_1: Q1 > Q2 > 0 > Q3 > Q4"
  H2: "quadrant spread mean r_1(Q1) - mean r_1(Q4) > 0"

n_trials_declared: 59
expected_effect_size: {IC: [0.01, 0.03], lift_pp: [1, 3]}
suspicion_threshold: {IC: 0.05, lift_pp: 5}     # above this => assume bug

decision_gates: {detected: [G1..G7], inconclusive: B, none: [K1..K8]}
default_verdict: no_useful_predictivity
negative_conclusion_text: >
  A continuous score built from single-candle OHLC geometry shows no
  statistically detectable information about near-term forward returns at
  the tested horizons. The idea is not carried forward to filter testing.
```

---

## Appendix B — Reference implementation

`docs/stage1_reference.py` implements the feature block, the causal trailing
percentile, the session-aware forward returns, the bucket statistics with the
corrected baseline, and the permutation null. It is deliberately written for
correctness and auditability rather than speed — the trailing percentile is
`O(n·W)` by design, so that "strictly prior" is visible in the code rather than
implied by a library default.

Its self-test reproduces the future canary, the noise canary and the synthetic
null of §5.6. Run `python docs/stage1_reference.py` before trusting any output
from a faster reimplementation. Dependencies are numpy and pandas only.

**Verified output** (300 synthetic sessions of random-walk bars with a
deliberate upward drift — data containing no information at all):

```
  Gate 1  synthetic null  : IC = -0.00659   PASS
  Gate 2  future canary   : IC = +1.00000   PASS
  Gate 3  noise canary    : IC = -0.00740   PASS

  Drift trap (this data contains NO information, only drift):
    P(r > 0) on the sample      : 0.5331   <- not 0.50, so 0.50 is wrong
    bullish buckets, conc - 0.50: +0.0284  <- the naive baseline's fake 'edge'
    bullish buckets, conc - pi_0: -0.0047  <- corrected, collapses toward 0
    quadrant spread H2          : -0.0116  <- drift cancels in a difference
```

The middle line is the point of the whole exercise. On data with **zero**
predictivity, the naive 50% baseline reports a **+2.84 percentage point** edge
on the bullish buckets — comfortably inside the 1–3pp band that §0.2 declares
as "plausible genuine effect". The corrected baseline `pi_0(q)` collapses it to
−0.47pp.

Any Stage 1 result that does not use `pi_0(q)` is measuring drift, and it will
land squarely in the range that looks most credible.

---

## Relationship to the later stages

`CANDLE_SCORING_VALIDATION_FRAMEWORK.md` covers filter-on-existing-edge testing,
context filters, walk-forward with purge/embargo, the full cost model, and
promote/discard gates. **It is reached only on Verdict A.** On Verdict B or C,
this stage is the end of the study.
