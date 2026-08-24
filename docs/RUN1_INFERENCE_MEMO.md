# Run 1 — Statistical Inference Memo

**Verdict:** C — no useful predictivity. H1 rejected.
**Scope:** Written from the Run 1 tables only (`results/run1/block_ic.csv`,
`decile_table.csv`, `quadrant_table.csv`, `run_report.json`). No new
hypothesis was tested, no parameter was changed, and the 252-session holdout
remains sealed.

**Sample:** SPY + IWM, 5-minute RTH bars, 2006-01-03 → 2022-02-28
(pre-IEX-break), 61 non-overlapping calendar blocks, n_eff 302,577.

---

## 1. What we can and cannot conclude about H1

### Can conclude

**H1 is rejected, decisively and consistently.**

H1 stated: higher `DQ` implies higher forward return — mean `r_1` ordering
Q1 > Q2 > 0 > Q3 > Q4, with a positive bucket gradient.

| Statistic | Observed | H1 predicts |
|---|---|---|
| mean IC across 61 blocks | **−0.02921** | positive |
| IC t-statistic | **−16.07** | ≥ +3.0 |
| blocks carrying the H1 sign | **3 of 61** (0.049) | ≥ 0.65 |
| bucket-index Spearman | **−0.619** | ≥ +0.60 |
| H2 quadrant spread | **−0.00685** | > 0 |
| H1 ordering respected | **False** | True |

Kill conditions **K2** (consistency < 0.50) and **K7** (sign reversed) both
fired. Under the pre-registration, either alone is Verdict C.

This is not a marginal miss. The point estimate has the wrong sign, and it has
the wrong sign in 58 of 61 independent calendar blocks spanning 16 years. The
one positive block (2019-01-10, IC +0.008) is the sole exception and is small.

### Cannot conclude

**We have not established that the reverse relationship is real, tradeable, or
transportable.** Specifically:

- **The reversal was never pre-registered**, so this sample provides no
  out-of-sample evidence for it. Every anti-mining protection in the design —
  the sign fixed in advance, the trial count, the sealed holdout — protects a
  *pre-declared* hypothesis. A hypothesis read off the result afterwards is
  protected by none of them.
- **The response is not monotone.** `shape_classification` returned
  `non_monotone`, and the decile table shows why: both extremes break the
  pattern. Decile 1 (most bearish) has mean `r_1` of **−0.0019**, where a clean
  reversal predicts the *most* positive value; decile 10 (most bullish) is
  **−0.0110**, less negative than decile 9's **−0.0165**. A relationship that
  weakens at both extremes is not the shape a simple fade rule assumes.
- **Nothing here separates signal from microstructure.** See §4.
- **Decile 5 must not be quoted.** Its lift of −0.2736 is the zero-crossing
  bucket (`frac_bullish` 0.0164), where `sign(DQ)` is set by rounding noise. It
  is flagged and excluded from the shape evidence by design, exactly as spec
  §3.5(e) requires.

---

## 2. Effect size: large in rank space, negligible in magnitude space

This is the most important number in the memo, and the two measures disagree
in an instructive way.

### In IC (rank) terms — statistically enormous

Mean IC −0.0292, t = −16.07. Against the pre-registered expectation band of
0.01–0.03, the magnitude sits at the top of "plausible genuine effect", and
the t-statistic is far past the ≥3.0 gate. Rank-wise, `DQ` orders next-bar
outcomes materially better than chance.

### In ATR terms — economically tiny

| Measure | Spread in ATR units |
|---|---|
| **H2 quadrant spread** (Q1 clean bull − Q4 clean bear) | **−0.00685** |
| Widest decile *mean* spread (bucket 4 → bucket 9) | 0.0345 |
| Widest decile *median* spread (bucket 1 → bucket 10) | 0.1465 |

Order-of-magnitude conversion, using the ~11.3 bp per-5-minute-bar figure
already stated in spec §0.2 (an illustration, **not** a new measurement on this
data):

| Measure | ≈ basis points | vs SPY round-trip cost ≈ 0.8 bp (§0.2) |
|---|---|---|
| H2 quadrant spread | ≈ **0.08 bp** | ~1/10 of cost |
| Widest decile mean spread | ≈ **0.39 bp** | ~1/2 of cost |

**The largest mean spread anywhere in the table is roughly half the cost of
one round trip.** The headline quadrant statistic is about a tenth of it.

### Why the two measures disagree

Compare mean against median in the decile table. Bucket 1: mean −0.0019,
median **+0.0769**. Bucket 10: mean −0.0110, median **−0.0696**. The median
gradient (≈0.147 ATR) is more than four times the mean gradient (≈0.035 ATR).

The Spearman IC is rank-based and tracks the median-like gradient. The means
are much weaker because **the fat tails run the other way** — the large moves
partially offset the typical ones. So the score sorts *ordinary* bars fairly
well and gets *large* bars wrong often enough to cancel most of the edge in
expectation.

An effect that is real in ranks and absent in means is the signature of
something you cannot monetise: you get paid in means, not in ranks.

---

## 3. What K_eff implies for generalisation

| Metric | Value |
|---|---|
| Instruments | 2 (SPY, IWM) |
| rho_bar | **+0.7910** |
| **K_eff** | **1.12** of 2 |
| Calendar blocks | 61 |

**Cross-sectionally this is a one-instrument study.** SPY and IWM agree in
direction (block-mean IC −0.0361 and −0.0228), but at 79% correlation that
agreement is close to one observation reported twice, not independent
replication. `K_eff = 1.12` says the second instrument added about 12%.

Consequences:

- **The time-series evidence is strong; the cross-sectional evidence is
  almost absent.** 58 of 61 blocks over 16 years is a genuine finding about
  *persistence through time* in this asset class. It says nothing about
  breadth.
- **Generalisation is limited to liquid US equity ETFs, pre-2022
  consolidated tape.** Not rates, credit, FX, commodities, single names, or
  the post-2022 IEX-sourced regime. This is not conservatism — the study
  attempted rates (TLT), gold (GLD), silver (SLV) and FX (FXE) and all four
  failed the untouched data-quality gate before any score was computed.
- **The rejection of H1 travels no further than the sample.** H1 is rejected
  *for liquid US equity ETFs in this era*. It is untested elsewhere. A future
  study on a different asset class starts from an open question, not from
  this rejection.
- **Survivorship remains.** SPY and IWM were chosen with hindsight of their
  survival, as recorded in the pre-registration limitations.

---

## 4. Why this is not a licence to trade the opposite sign

Five independent reasons, any one sufficient.

**1. The economics fail before anything else.** §2 above: the widest mean
spread in the entire table is ≈0.39 bp against a round-trip cost of ≈0.8 bp,
and the headline H2 statistic is ≈0.08 bp. A fade rule built on this loses to
costs by a wide margin before slippage, and the pre-registered position was
always that Stage 1 measures information, not tradeability.

**2. Rank edge does not pay; mean edge pays.** The effect is four times larger
in medians than in means because the tails offset. A strategy is paid the mean.

**3. The most likely mechanism is untradeable by construction.** A negative
close-to-close relationship at 5-minute horizons, strongest in medians and
weakest in tails, is the classic signature of **bid-ask bounce** — a bar
closing near its high tends to have closed on an offer, and the next print
reverts toward the mid. Step 2 measured lag-1 autocorrelation of the target at
−0.0088 and of the score at −0.0445, consistent with that reading. *This study
did not test that mechanism and cannot confirm it* — but it is the leading
candidate, and if it is the explanation then the "edge" is exactly the spread
you would pay to capture it. Fading microstructure noise means buying the
offer and selling the bid.

**4. The relationship is not monotone, so there is no clean rule to invert.**
Both extreme deciles break the pattern (§1). Inverting H1 gives a rule whose
strongest signals are its least reliable ones.

**5. Trading it would be acting on an unregistered hypothesis.** The reversal
has zero out-of-sample support. Every protection in this design applies to
H1, which was declared in advance. Turning a rejection into a position is the
precise failure — reading a direction off a sample and then acting on that
same sample — that the pre-registration exists to prevent. Spec §3.2 and K7
say so explicitly: a reversed sign is a rejection, not a finding.

---

## 5. What a new study would need to test fade / reversion

Not a continuation of this one. A **new study**, with a new pre-registration.
Minimum requirements:

**Declared before any data is touched**

1. **H1' with its sign fixed in advance** — e.g. "higher `DQ` implies *lower*
   forward return", stated as the primary hypothesis, not a fallback.
2. **A mechanism hypothesis that is separately falsifiable.** If the claim is
   information, it must survive controls for microstructure. If it is
   microstructure, it is not tradeable and the study should say so up front.
3. **A fresh trial count.** Run 1 consumed one trial; a reversal study starts
   its own family and carries its own multiple-testing correction.

**Data that this run has not seen**

4. **The sealed 252-session holdout is the only untouched data here**, and it
   is one look. It is enough to *confirm* a pre-declared reversal, not enough
   to *discover* one.
5. **Genuinely new data is preferable** — post-2022 (a different microstructure
   regime, which is itself the point), a different vendor, or a different
   market. Re-running on 2006–2022 SPY/IWM would be testing a hypothesis on
   the sample that generated it.

**Tests this run did not run**

6. **Microstructure controls.** Quote-midpoint returns rather than trade
   closes, or a one-bar entry delay, to separate reversion from bounce. If the
   effect dies on midpoints, it was the spread.
7. **Cost-aware evaluation from the start.** The pre-registered economic
   floor from §0.2 — a 5-minute directional bet on SPY needs ~54% hit rate to
   clear costs — should be a gate, not an afterthought.
8. **A monotonicity requirement that the observed shape would fail.** Run 1's
   response is `non_monotone`; a reversal study should declare in advance
   whether it requires monotonicity, and if so, this shape does not qualify.

**Cross-sectional breadth**

9. **More than one asset class**, which this source could not supply at
   5-minute resolution. Without it, `K_eff` stays near 1 and any result again
   speaks only to liquid US equity ETFs.

---

## Bottom line

Run 1 tested a specific, pre-declared claim — that continuous candle geometry
predicts *continuation* — on 16 years of clean data with every anti-mining
protection in place, and rejected it with a t-statistic of −16 across 58 of 61
independent blocks.

The reversed sign is a rejection of H1, not a discovery. Its economic size,
roughly a tenth of a round trip at the headline statistic, is consistent with
microstructure rather than information. Stage 2 stays locked; the idea is not
carried forward to filter testing.
