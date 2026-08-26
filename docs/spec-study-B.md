# Study B — Opening-Bar Predictivity Spec

**Status:** **FROZEN 2026-08-26.** All three §11 questions are answered, the
ticker list is locked, and `docs/preregistration-study-B.yaml` is written.
This file is the prose question; the yaml is the machine-checked freeze. From
here the yaml governs — where the two disagree, the yaml wins, and this file
is not edited to match a result.

**Locked universe: SPY, IWM, GLD, XLE, EEM.** TLT dropped on regime
selection (46.5% eligible in 2006–2009); UUP, FXE, IEF, SLV dropped on
coverage. Eligibility is the per-session rule E1–E6 in
`docs/STUDY_B_ELIGIBILITY.md` — an explicit specification change from Run 1's
whole-instrument 5% gate.

**Still not run:** no DQ, no IC, no target value, no Step 5. Awaiting operator
acceptance of the yaml.
**Relationship to other documents:** `docs/programme.md` (the file the upload
called `spec.md`) is the programme charter, not a frozen study spec — it holds
three studies (A done, B, C) and must not be treated as this study's freeze.
This file is the single official question for Study B, per constitution rule
2. A separate, machine-checked `docs/preregistration-study-B.yaml` is written
and frozen later, after this spec is accepted — mirroring how Run 1's prose
spec and `docs/preregistration.yaml` were kept separate. This file is not
iterated after data is seen (constitution rule 1); a SpecKit clarify/plan loop
belongs to the code that implements this spec, never to the claim itself.

**Formulas:** `BD`, `CL`, `SA`, `WB`, `CONV`, `DIR`, `DQ` and the degenerate
gate are defined once, in `docs/preregistration.yaml` (`score:` block). This
document references them by name and does not restate or vary them.

---

## 1. Claim and sign — two-sided

**Revised 2026-08-25.** The operator has explicitly not decided whether the
opening bar continues or fades, and does not want that decided by default
wording. Study B is **exploration of existence**, not a locked-direction
replication of Run 1's claim.

> **H1:** `DQ` on the true 09:30 bar is associated with the primary forward
> window T2. Direction is not assumed. Verdict A requires `|effect|` above
> the pre-declared floor and stability across blocks. The observed sign is
> reported as a description. A trading rule in that direction requires
> unused data.

Unpacking each clause, because each one closes a specific way this could
still turn into a locked claim by accident:

- **"Associated," not "continuation" or "fade."** Neither word appears in the
  claim itself. Both are named in §3 as competing, pre-declared readings of
  whatever sign is observed — not as the hypothesis.
- **"`|effect|` above the floor," not "positive IC above the floor."**
  Detection is on magnitude. §5's power table is therefore about detecting
  an effect of either sign, exactly as before — a two-sided test does not
  relax the floor, it removes the sign restriction on which side of the
  floor counts (see §5 caveat).
- **"Stability across blocks"** reuses Run 1's consistency-ratio machinery,
  generalised to two-sided: the requirement is that the *sign* is stable
  block-to-block (not necessarily positive), not that it matches a
  pre-declared direction.
- **"The observed sign is reported as a description"** — a finding of
  "negative and stable" is exactly as complete a Verdict A as "positive and
  stable." Neither is privileged. What is *not* permitted is choosing which
  competing mechanism (§3) explains a negative result after seeing that it
  is negative — the mechanisms are ranked by fit, not invented to fit.
- **"A trading rule in that direction requires unused data"** is the
  guardrail that replaces K7's old locked-sign role: whichever sign is
  observed, Study B has by construction just spent its data *discovering*
  that sign. Building a rule from it on the same sample is exactly the
  discovery-then-license-to-trade error the constitution exists to block,
  regardless of which direction the arrow points. A directional trading
  rule — either continuation or fade — is a separate, later study on data
  Study B has not touched.

**What this changes from the original draft, and why it is not weaker:**
the original locked H1 to continuation and treated a reversed sign as
outright rejection (K7). That was appropriate for a *replication* of Run 1's
already-declared direction. Study B is not that — its stated purpose is to
find out whether a relationship exists at all before describing its sign.
Locking a direction here would have made a negative, stable result
indistinguishable from noise in the gate logic, which is the opposite of
what "explore first, describe sign after" requires. The rigor moves instead
into §3 (mechanisms pre-declared before the sign is known) and into the
"unused data" clause above.

---

## 2. Target definitions

All three targets are **one observation per session per instrument** —
unlike Run 1's `r_1`, which was one observation per bar. This has a direct
power consequence worked out in §5: switching targets does not change the
observation count, only what each observation measures.

Causal normaliser: **`ATR_20` evaluated at the last 5-minute bar of the
prior session** — the same series `stage1.core.wilder_atr_prev` already
produces at that timestamp. No new ATR computation; the selector picks the
correct index. This is causal by construction, since it uses no information
from session `t`.

**Windows frozen 2026-08-25.** All three end-points below are locked. They do
not move after data is seen, and they did not move in response to any number,
because no target has been computed.

| Target | Definition | Role | Gates verdict? | Trial count |
|---|---|---|---|---|
| **T1** | `(Close_09:35 − Close_09:30) / ATR_20(prior close)` | **Diagnostic only** — bounce check | No | None. T1 is a control, not a hypothesis |
| **T2** | `(Close_12:00 − Close_09:35) / ATR_20(prior close)` | **PRIMARY pre-declared target** | **Yes** | 1 |
| **T3** | `(Close_15:55 − Close_09:35) / ATR_20(prior close)` | **Second pre-declared target** | No — always reported | 1 (its own increment) |

`15:55` is the open-labelled bar whose close is the official RTH close; on a
close-labelled feed the equivalent stamp is `16:00`. The bars this study reads
are open-labelled (`stage1.hf_prepare` detects and normalises the label), so
`15:55` is the stamp that appears in code. On an early-close half-day the
session's own last bar is the T3 end-point; `resample_to_5min` already builds
each session's grid to its own last observed bar rather than inventing
phantom afternoon rows.

### T3 promoted from diagnostic to a second pre-declared target

**Changed 2026-08-25 by operator decision.** In the previous draft T3 was
"secondary / diagnostic" and could not carry a result. It is now a *second
pre-declared target*: declared in advance, always reported, subject to the
same two-sided rule as T2 (§1 — magnitude above the floor, sign described not
assumed), and **carrying its own trial increment** in the frozen
pre-registration's multiple-testing budget. Two pre-declared targets means
**two trials, not one**; the yaml records `n_trials` accordingly and the
verdict gates are read against the corrected threshold, not the nominal one.

What promotion does **not** do, stated as a single sentence that is itself
frozen:

> **A T3-only effect with null T2 is NOT a second product.**

That sentence is the guardrail. T3 being pre-declared means a T3 result is
*admissible* — it is not read as noise merely because T2 was null — but T2
remains the target the verdict is decided on. A run that returns a stable T3
effect and a null T2 is reported as exactly that, and is a candidate for a
future study, not a finding this study delivers. **This sentence may be
changed only before `preregistration-study-B.yaml` is written.** After the
yaml is frozen it is closed, and changing it post-run is re-specification on
a result under constitution rule 3.

### T1 stays diagnostic only

T1 is not promoted and gets no trial increment, because it is not asking this
study's question. Its entire job is the bounce check in M3 (§3): it can
*explain away* part of a T2 or T3 result, and it cannot produce one.

**Pre-declared reading rule for T1 vs the pre-declared targets, fixed now,
before any number exists:**

> If T1 shows a negative, stable effect and **neither T2 nor T3** shows the
> same effect (in size and stability), T1 is read as **consistent with
> bid-ask bounce / spread mechanics**, not reported as a standalone fade
> signal. It is a diagnostic outcome, not a product of this study. Only if a
> pre-declared target — T2 for the verdict, T3 as reported — itself shows a
> stable effect does §3's mechanism ranking apply.

This rule exists so that a T1-only effect cannot quietly become "Study B
found a fade edge" by virtue of being computed and looking clean in
isolation. T1's whole role is as a control that can *explain away* part of
a T2 or T3 finding, not as a hypothesis competing for attention.

### Why T2 is primary

The programme goal (§0, `docs/programme.md`) is a filter for an ORB-style
setup: *"clean enough to take, sloppy enough to wait."* That decision is made
once, at or shortly after the open, and lived with for the trade's holding
period — not re-evaluated bar by bar. This reasoning is about **holding
period fit**, not about which sign is expected, and applies identically
whatever sign T2 turns out to carry:

- **T1 is too granular for the stated purpose**, and it is the horizon most
  exposed to the mechanism `docs/RUN1_INFERENCE_MEMO.md` flagged as the
  leading (untested) explanation for Run 1's own reversed tilt: bid-ask
  bounce. A single 5-minute transition immediately after the open is exactly
  where that effect would be strongest. Reporting T1 lets that be checked
  against T2 via the rule above; gating the verdict on T1 alone would risk
  re-measuring microstructure and calling it information, regardless of
  which sign it came back with.
- **T3 dilutes the signal with unrelated afternoon dynamics**, which is why
  it does not gate the verdict. A morning setup's information content, if
  any, should decay well before the close, and folding in six more hours of
  unrelated variance adds variance faster than it adds signal. That is an
  argument for T3 being *second*, not for T3 being *absent* — see below.
- **T2 matches the holding period an ORB-style filter actually cares about**
  and stays close enough to the open that a causal story from opening-bar
  geometry to outcome — in either direction — remains plausible.

### Why T3 is nonetheless pre-declared rather than dropped

The dilution argument says T3 is a *noisier* measurement of the same
underlying question, not a different question. A noisier measurement that is
declared in advance and costs one trial is worth having, for two reasons
fixed here before any number exists:

1. **It distinguishes decay from absence.** M1 (§3) predicts information
   arriving over the morning and then decaying; M2 predicts an overshoot
   unwinding and then stopping. Those two make different predictions about
   what T3 looks like relative to T2. With T3 unreported, both mechanisms
   are consistent with the same single number.
2. **Declaring it is strictly more honest than computing it as a
   "diagnostic."** A quantity that is computed and looked at is a trial
   whether or not the spec calls it one. Naming T3 a target and paying its
   trial increment prices that look correctly, instead of getting the look
   for free by labelling it.

The 09:35–12:00 window for T2 and the 09:35–close window for T3 are **frozen
as of 2026-08-25**, not provisional. Neither moves again.

---

## 3. Competing mechanisms (pre-declared)

Because §1 no longer names a direction, the space of possible explanations
for *whatever* sign is observed must be enumerated **now**, before any
number exists — otherwise a post-hoc story gets written to fit the result,
which is exactly the narrative failure mode the constitution exists to
block. Three mechanisms are pre-declared. After the run, the result may be
described as more consistent with one of these than the others. **A fourth
mechanism may not be introduced after seeing the data to explain a result
that doesn't fit the three below.**

| # | Mechanism | Predicts | Pre-declared signature in this study's own outputs |
|---|---|---|---|
| **M1** | **Continuation / ORB / overnight information.** A clean, decisive opening bar reflects real information (overnight news, gap conviction) that the market continues to digest through the morning. | Same-sign effect on T2 as `DQ`'s own sign; effect should *not* be concentrated in T1 alone, since information takes time to be reflected, not just the first 5 minutes. | Positive, stable T2; T1 similar sign but weaker or noisier than T2 (information keeps arriving after the first bar) |
| **M2** | **Fade / opening overshoot.** A decisive-looking opening bar reflects an overreaction (order-flow imbalance from open auctions, stop runs) that partially reverses once the imbalance clears. | Opposite-sign effect on T2 relative to `DQ`'s sign; plausibly present in both T1 and T2, but growing (not shrinking) from T1 to T2 as the overshoot unwinds over the morning. | Negative, stable T2; T1 same sign as T2 but smaller in magnitude |
| **M3** | **Bid-ask bounce / spread mechanics.** The opening bar's close is more likely to have printed on the bid or offer than at the true midpoint, so the very next print mechanically tends to move the other way — pure microstructure, no information content, and it should decay almost immediately. | Opposite-sign effect on T1 that **does not persist** to T2 — the signature §2's pre-declared T1-vs-T2 rule is built to catch. | Negative T1, effect at T2 much smaller or absent — the specific pattern that triggers §2's "read T1 as bounce, not a product" rule |

**How the ranking is read after the run — pre-declared, not chosen after
seeing numbers:**

- **T2 stable and same-signed as `DQ`, T1 weaker or noisier** → most
  consistent with **M1**.
- **T2 stable and opposite-signed to `DQ`, T1 same sign and smaller** →
  most consistent with **M2**.
- **T1 opposite-signed and large, T2 small or unstable** → most consistent
  with **M3**, and by §2's rule this is reported as a T1 diagnostic, not a
  Verdict A on T2.
- **None of the three patterns fit cleanly** → reported as exactly that:
  "does not match any pre-declared mechanism," not resolved by inventing a
  fourth story. This is a legitimate, complete outcome, not a gap to be
  patched.

Note the Run 1 precedent this table is built to be consistent with: Run 1's
all-day result was negative and stable at the bar level, and
`docs/RUN1_INFERENCE_MEMO.md` flagged M3 (bounce) as the leading untested
explanation *because* the effect was large in rank terms and negligible in
ATR/mean terms — the same diagnostic posture M3 uses here, now written down
in advance instead of reconstructed after the fact.

---

## 4. Missing-open rule

Per `docs/DATA_AUDIT.md`, HF's 09:30 bar is absent on **9.57% of SPY
sessions (389 / 4,066)** and **12.89% of IWM sessions (524 / 4,064)**. The
coverage screen (`docs/STUDY_B_COVERAGE.md`) reproduces both figures exactly
and extends them across the candidate universe: **9.2% to 45.3%**, with UUP
at 30.0% and FXE at 45.3%. Since
the official question is specifically about the 09:30 bar, this is not a
minor gap — it decides what "the first bar" means.

| Option | Definition | Effect |
|---|---|---|
| **Drop** (default) | Session excluded entirely if the true 09:30 bar is absent | Preserves the object of study exactly; costs ~10–13% of sessions |
| FirstLive | Score whichever RTH bar appears first that session | **Changes the object of study** — some sessions' "opening bar" would actually be a 09:35 or later bar, a different time-of-day distribution with different typical range and conviction. H1 as worded (§1) is a claim about the 09:30 bar specifically |

**Default: Drop.** The official question names the 09:30 bar. Substituting a
later bar on ~10–13% of sessions answers a different, unstated question and
would need its own H1 sentence ("the first *available* 5-minute bar"). Drop
is also the only option consistent with how a live ORB filter would actually
work: if the real 09:30 print is missing from *this* recording, that says
nothing about whether the live feed had it, and the honest response is "no
observation," not a silent substitution.

The power cost of Drop is carried through explicitly in §5 rather than
glossed over.

---

## 5. Universe and power (computed before freeze, t = 3.0)

**Universe answered 2026-08-25; ticker lock still pending the coverage
table.** The operator's answer to §11 Q1 was option (b) — name a specific,
correlation-aware list rather than accept the 2-name universe:

| | Names | Status |
|---|---|---|
| **Candidate primary (K=7)** | SPY, IWM, TLT, GLD, XLE, UUP, EEM | Proposed; **not all survive the data screen — see §5.0** |
| **Reserve (K=4)** | IEF, SLV, FXE, USO | Quality swap only, and only **before** any IC is computed |

Constraints attached to that answer, recorded here so they bind the yaml:

- **No QQQ + DIA + full XL\* set on top of SPY + IWM.** The failure mode being
  avoided is fake breadth: eleven US equity sector ETFs plus three US equity
  index ETFs is one observation reported fourteen times, and would push `K`
  up while pushing `ρ̄` up faster, *lowering* `K_eff`. The breadth ceiling
  below is why that trade is negative, not merely neutral.
- **At most one extra equity sector**, and XLE fills it — energy is the
  sector with the least index-like behaviour, which is the point of
  including one at all.
- **Reserve names are a quality swap, not an expansion.** A reserve name may
  replace a primary name that fails the data screen. Reserve names may not be
  added on top to raise `K`, and no swap happens after an IC exists.

Session counts and missing-open rates: `docs/DATA_AUDIT.md` and
`results/study_b_coverage/coverage.csv`. `n_eff` methodology:
`stage1.stats.effective_sample_size` (unchanged — see §10).
`K_eff = K / (1 + (K−1)·ρ̄)`.

### 5.0 The named universe does not survive the frozen data gate

The DATA-ONLY screen (`stage1/coverage_study_b.py`, run 2026-08-25 over
2006-01-03 → 2022-02-28) measured the frozen 5% degenerate-bar gate on all
eleven names. **Nine of the eleven fail it, including five of the seven
primary candidates.** Full table and reading: `docs/STUDY_B_COVERAGE.md`.

Only **SPY and IWM** pass the gate as it is currently written and scoped.
That is not a coincidence — they are the two names Run 1 already screened,
and the screen has not become easier.

The screen also surfaced a distinction the gate does not currently make: for
GLD, XLE, USO, TLT and EEM the failure is **whole-instrument** (thin midday
and afternoon bars) while the **09:30 bar itself is essentially never
degenerate when present** (0.00–0.51%). Study B reads one bar per session.
Whether the gate should therefore be scoped to that bar is a real question —
and it is a **specification change**, not a data finding. It is not decided
here, it collides with §8 as currently written, and it is put to the operator
in §11 Q3.

**Until that is answered, the power arithmetic below is given for both the
universe the gate currently permits and the universe the named list would
give if the gate were re-scoped.** Neither is presented as the answer.

**Two-sided testing does not change this table, and does not fix the 2-name
problem.** §1's revision removes the sign restriction on the *hypothesis*,
not on the *arithmetic*. `n_eff`, `K_eff` and the detectable-IC floor come
from the sampling variance of the estimator (`t = IC·√n_eff`), which is
identical whether the test asks "is IC positive" or "is `|IC|` large" —
going two-sided changes the critical value's interpretation, not `n_eff`
itself. A two-sided test at the same `α` is in fact very slightly *less*
sensitive per unit of `n_eff`, not more, because the same significance
budget is split across both tails instead of spent on one. **Concretely: the
2-name universe's detectable floor stays 0.049 whether H1 is signed or not.**
Going two-sided was the right response to genuine uncertainty about
direction — it is not, and must not be read as, a power upgrade.

**Caveat that must travel with every row below:** every `ρ̄` in the table is
an assumption, not a measurement.

- The **2-name row** reuses **0.79 / K_eff 1.12**, Run 1's measured value
  from *all-day* 5-minute bars.
- The **6- and 7-name rows** span ρ̄ = 0.30–0.50 as a planning range. That
  range is a judgement about a mixed equity/rates/commodity basket, not a
  number anyone has computed on opening bars.

In both cases the direction of the likely error is the same: the opening
print across correlated ETFs could plausibly be **more** tightly coupled
(shared overnight news, shared index-open mechanics) than the all-day
average, which would push `ρ̄` up, `K_eff` down and the detectable floor up.
**The rows below are therefore optimistic if they are wrong.** `ρ̄` must be
re-measured, not assumed, once real opening-bar scores exist — Step 2 of the
eventual run, before Step 5 — and if the measured `ρ̄` lands above 0.5 the
Verdict B expectation hardens rather than softens.

Session counts below are the **measured** `usable_T2` column from the coverage
screen — sessions surviving Drop, carrying a non-degenerate 09:30 bar with a
warm prior-session ATR, and carrying both closes T2 needs. They are not
assumptions.

| Universe | K | Per-instrument usable T2 sessions | ρ̄ | K_eff | n_eff | Detectable IC (t=3.0) | Verdict |
|---|---|---|---|---|---|---|---|
| **SPY + IWM** — what the gate permits today | 2 | 3,367 avg | 0.79 (Run 1, all-day, placeholder) | 1.12 | **3,771** | **0.049** | Outside 0.01–0.03 band; on the >0.05 "treat as a bug" threshold |
| Named list minus gate failures, gate re-scoped to the open (SPY, IWM, GLD, XLE, TLT, EEM — UUP excluded on coverage, see §5.0) | 6 | 3,326 avg | 0.30 | 2.40 | **7,982** | **0.034** | Above the band |
| " | 6 | 3,326 avg | 0.40 | 2.00 | **6,652** | **0.037** | Above the band |
| " | 6 | 3,326 avg | 0.50 | 1.71 | **5,688** | **0.040** | Above the band |
| Same plus USO from reserve | 7 | 3,317 avg | 0.30 | 2.50 | **8,293** | **0.033** | Above the band |
| " | 7 | 3,317 avg | 0.50 | 1.75 | **5,805** | **0.039** | Above the band |

**Honest statement, as required, and it is the central result of this
section:** expanding the universe **improves the power problem without
solving it.** The detectable floor moves from **0.049** (2 names) to roughly
**0.033–0.040** (6–7 names, depending on the realised `ρ̄`) — from sitting on
the "assume a bug" threshold to sitting just above the top of the plausible
0.01–0.03 band. That is a real gain and it is not enough: a true effect
anywhere in the plausible band is still invisible, and **Verdict B
(underpowered) remains the most likely outcome of this study under every row
of this table.**

This must be stated in the frozen pre-registration's `expected_effect_size`
field before the run, not discovered at Step 2. The correct posture going in
is that Study B is powered to detect only an unusually large opening-bar
effect (≳0.035), and that a null is uninformative rather than evidence of
absence.

**Two trials, not one (§2).** T2 and T3 are both pre-declared, so the
multiple-testing correction applies to a family of two. At a Bonferroni-style
correction the per-target critical `t` rises from 3.0 to roughly 3.2, which
raises every detectable-IC figure above by about 7% (e.g. the K=7, ρ̄=0.3 row
goes from 0.033 to ~0.035). This is priced in deliberately: the alternative —
computing T3 and not counting it — would understate the floor rather than
lower it.

### The breadth ceiling — why more names does not fully fix this

Holding the per-instrument session count fixed at ~3,320 (the history does
not grow), `K_eff` has a hard limit as `K → ∞`: **`K_eff → 1/ρ̄`**. This
gives a floor on the detectable IC that **no amount of breadth can cross**:

| ρ̄ | K_eff limit (K→∞) | n_eff limit | IC floor (t=3.0) |
|---|---|---|---|
| 0.30 | 3.33 | 11,046 | **0.029** |
| 0.40 | 2.50 | 8,293 | **0.033** |
| 0.50 | 2.00 | 6,634 | **0.037** |

Even an infinite universe of names correlated at ρ̄=0.5 cannot detect an
IC below 0.037. This is constitution rule 5 — *"more tickers do not create
more years"* — made quantitative for the opening-bar case: at these
correlations, no feasible universe reaches the **bottom** of the plausible
band.

**The 6–7 name universe is already close to that ceiling.** At ρ̄=0.3 the
K=7 row reaches n_eff 8,293 against a K→∞ limit of 11,046 — about 75% of
everything breadth can ever deliver. The remaining 25% would require adding
an unbounded number of names. This is the quantitative reason the operator's
"no QQQ + DIA + full XL\* set" constraint costs nothing: the names it
excludes are the highest-ρ̄ names available, and they sit on the flattest
part of this curve.

Reference points for what *would* be needed:

| Target IC | n_eff required (t=3.0) |
|---|---|
| 0.030 | 10,000 |
| 0.020 | 22,500 |
| 0.015 | 40,000 |
| 0.010 | 90,000 |

40,000–90,000 n_eff is not reachable by breadth at this session count under
either correlation regime. It is reachable only by **more history** (more
sessions), which this source does not have beyond what Run 1 already used.

**Implication for freeze:** if this study proceeds, it should proceed
expecting to detect only the **upper portion** of the plausible band
(≳0.025–0.03), and should say so in the frozen pre-registration's own
`expected_effect_size` field — not discover it at Step 2 and be surprised.

---

## 6. Holdout

Study-specific. **Not** Run 1's 252-session holdout treated as 252
observations — Run 1's holdout carried ~78 bars × 252 sessions per
instrument; Study B carries **one** observation per session.

Proposed default, sized to the same session-count convention as Run 1 for
comparability: **last 252 sessions**, sealed at freeze, one look, after
Step 5 on the evaluation history. Under the Drop rule (§4), the realised
observation count in that window is:

```
252 sessions x (usable_T2 / sessions)      # measured, coverage screen
  SPY  -> ~214 observations
  IWM  -> ~204 observations
  GLD  -> ~215     XLE -> ~197
  TLT  -> ~199     EEM -> ~209
```

These are per instrument and do not simply add: at ρ̄ = 0.3–0.5 a K=6 holdout
is worth roughly `K_eff` ≈ 1.7–2.4 independent instruments, so the effective
holdout is on the order of **350–500** observations, not 1,200. The exact
figure is re-derived on the locked universe once §11 Q3 is answered.

**Either way this is far below any detection threshold in §5.** That
is fine, because the holdout's role here is narrower than in Run 1: it can
only **confirm the sign observed on the evaluation history** — a one-sided
check that the same sign found and frozen at Step 5 still holds — not
re-estimate an effect size, not discover a new direction, and not serve as
a second exploration pass. Because H1 is now two-sided (§1), there is no
pre-declared direction for the holdout to check against; it checks whatever
sign the evaluation history produced, frozen before the holdout is opened.
This must be written into the frozen pre-registration explicitly, so a null
result on the holdout is not mistaken for a power failure of the holdout
itself — it is expected to be underpowered for estimation and is not being
asked to estimate anything.

Per constitution rule 7, it is looked at once, after the claim is frozen.

---

## 7. Source policy

- **HF Data Library may be used only under the missing-open rule in §4
  (Drop, by default).** No other accommodation for HF's incomplete opening
  coverage is in scope for this spec.
- **What HF cannot support, and must not be asked to:**
  - **Official open extremes.** `docs/DATA_AUDIT.md` §2 found SPY's opening
    range on `2010-05-06` misses the session low by 468 bp on a scale-free
    basis. Any use of the opening bar's high/low as an *extreme* (not just as
    an input to `DQ`'s ratio features) is unsupported by this source.
  - **MAE/MFE.** Excursion measures need reliable intraday extremes
    throughout the holding window, which §2 of the audit found HF
    understates on a material minority of big-move days. Out of scope for
    this study on this source.
- **Futu and any other vendor are out of scope for this spec unless
  explicitly named in a revision.** No IC is computed on Futu data under
  this study. If a Futu opening-bar series becomes available later, it
  requires its own spec section (universe, power, holdout) — not silent
  reuse of this one.

---

## 8. Out of scope

- All-day rerun of Study A (Run 1 is closed; see `docs/RUN1_INFERENCE_MEMO.md`)
- Fade / reversal read from Run 1's reversed sign
- Stage 2 — filtering live ORB trades
- Footprint / volume profile
- **Relaxing the 5% degenerate-bar gate** — i.e. raising the threshold above
  5% to admit an instrument. This remains out of scope and is not what §11
  Q3 asks. Q3 asks whether the gate's *scope* (all bars vs the 09:30 bar) is
  the right scope for a one-bar-per-session study; the 5% threshold itself
  does not move under either answer. The distinction matters: one is
  loosening a standard to fit a result, the other is asking whether the
  standard is pointed at the right measurement. Only the second is on the
  table, and only before any IC exists.
- Era restriction as a way to admit a failing instrument — closed by
  `docs/STUDY_B_COVERAGE.md` §4
- **Computing any IC before this spec is accepted**

---

## 9. Acceptance checks before any code or data work

- [x] Claim (§1) frozen — two-sided, no direction assumed
- [x] **Windows frozen (§2)** — T2 ends 12:00, T3 ends 15:55 open-labelled
      (official RTH close). Neither moves again.
- [x] **T2 confirmed PRIMARY and verdict-gating (§2)**
- [x] **T3 promoted to a second pre-declared target (§2)** — always reported,
      same two-sided rule, its own trial increment
- [x] **The sentence "a T3-only effect with null T2 is NOT a second product"
      recorded (§2)** — changeable only before the yaml is written
- [x] T1 confirmed diagnostic only, no trial increment, bounce check (§2)
- [x] Mechanism table (§3) accepted as pre-declared and closed to later addition
- [x] Missing-open rule (§4, Drop) frozen
- [x] Universe *answer* recorded (§5) — option (b), specific correlation-aware
      list, with the no-QQQ/DIA/XL\* and one-extra-sector constraints
- [x] Detectable IC written down (§5) — measured session counts, two-trial
      correction, and the breadth-ceiling table
- [x] **DATA-ONLY coverage screen run** — `docs/STUDY_B_COVERAGE.md`
- [x] **Coverage table accepted** (2026-08-26)
- [x] **§11 Q3 answered** — neither pooled option taken; the per-session
      eligibility rule E1–E6 replaces the instrument gate
      (`docs/STUDY_B_ELIGIBILITY.md`), with an explicit ATR-freshness
      condition
- [x] **DATA-ONLY eligibility screen run and accepted**
- [x] **Tickers locked: SPY, IWM, GLD, XLE, EEM** (TLT dropped on regime
      selection)
- [x] Holdout named and its thin observation count accepted in advance,
      re-derived on the locked universe (~345–470 effective)
- [x] Pointer confirmed: reuse `stage1.gates` canaries, `stage1.validate`,
      `stage1.power`, `stage1.run_all` — no rewrite (§10)
- [x] **`preregistration-study-B.yaml` written**
- [ ] **Operator accepts the yaml** ← blocking. No DQ, no IC, no Step 5
      until this box is ticked.

---

## 10. Mapping to the existing pipeline

**Reused unchanged — no rewrite, per programme instruction:**

- `stage1/core.py` — `candle_features`, `DQ`/`DIR`/`CONV` construction, the
  degenerate gate, `w_range`. The opening bar is scored with the identical
  function used on every other bar; nothing about the score changes.
- `stage1/io.py`, `stage1/validate.py` — same manifest, same resampling
  rules. SPY and IWM need **no new HF pull**: they are read from the
  already-validated bars in `data/clean/`. Any instrument added by the §11 Q3
  answer must be pulled through `stage1.hf_prepare` and passed through
  `stage1.validate` into `data/clean/` before it is scored — the coverage
  screen resampled those names in memory to measure them and deliberately
  wrote no clean bars, so nothing measured by the screen can be mistaken for
  validated study data.
  **If Q3 answer (b) is taken, `stage1.validate`'s whole-instrument 5% abort
  will reject GLD, XLE, TLT and EEM.** The re-scope is therefore not a
  no-code change: it needs an explicit, pre-registered scope parameter on the
  gate, declared in `preregistration-study-B.yaml` and not passed ad hoc on a
  command line.
- `stage1/gates.py` (synthetic null, future canary, noise canary, shift
  invariance) — must pass on the new session-indexed series before any real
  result is trusted, exactly as in Run 1. A leaking pipeline is a leaking
  pipeline regardless of what feeds it.
- `stage1/stats.py` — `effective_sample_size` (`K_eff`, `rho_bar`),
  `jonckheere_terpstra`, `evaluate_gates`. These operate on generic indexed
  series and are agnostic to how many bars a session contains.
- `stage1/core.py` — `information_coefficient`, `quadrant_table`,
  `permutation_null`. Same reasoning.
- `stage1/dataset.py` — `global_block_map` partitions by **session date**
  already; it needs no change to serve one-observation-per-session data.
- `stage1/run_all.py` — the validate → power → gates → test order and its
  stop-at-first-gate discipline apply unchanged.

**New code allowed — one thin, additive module:**

- An **opening-bar selector** (e.g. `stage1/opening_selector.py`) that, given
  already-validated 5-minute bars:
  1. Applies the Drop rule (§4) per session.
  2. Reads the `DQ` (and component) values already computed by
     `candle_features` on the 09:30 row only.
  3. Looks up `Close_09:35`, `Close_12:00`, `Close_15:55` from the same
     validated frame to build T1/T2/T3 (§2).
  4. Re-derives the trailing-percentile normalisation for a
     **one-observation-per-session** index — the existing
     `trailing_percentile` is bucketed by intraday time-of-day (30-minute
     slots, `docs/preregistration.yaml` §1.5) because Run 1 had 13 slots per
     session; Study B has exactly one slot (the open), so the window and
     `min_obs` must be re-expressed in **sessions**, not bars. This is a
     genuine new design decision, not a data change, and belongs in the
     frozen `preregistration-study-B.yaml`, not improvised in code.
  5. Emits one row per (instrument, session): score, T1, T2, T3, calendar
     block — a small file that Run 1's existing Step 5 machinery
     (`core.information_coefficient`, `core.bucket_table`,
     `core.quadrant_table`, `stats.jonckheere_terpstra`) can consume exactly
     as it consumes bar-level `r_1` today.

Nothing else changes. Scoring, `π₀`, the gate evaluator, and the canaries are
the parts of Run 1 that were tested hardest and caught real bugs (the
five-hour timezone shift, the silent NaN-alignment fault); reusing them
verbatim is the point, not an implementation detail.

---

## 11. Freeze questions — Q1 and Q2 answered, Q3 opened by the answer

### Q1 — Universe. **ANSWERED 2026-08-25: option (b).**

A specific correlation-aware list, not "add names later":

- **Candidate primary (K=7):** SPY, IWM, TLT, GLD, XLE, UUP, EEM
- **Reserve (K=4), quality swap only and only before any IC:** IEF, SLV,
  FXE, USO
- **Excluded by decision:** QQQ, DIA and the full XL\* sector set are not
  added on top of SPY + IWM. At most one extra equity sector, and XLE fills
  it.

Recorded in §5, with the reasoning for why the exclusion costs nothing
(those are the highest-`ρ̄` names available and sit on the flattest part of
the breadth curve).

**Status: answered, not yet executable.** The DATA-ONLY screen
(`docs/STUDY_B_COVERAGE.md`) found that **five of the seven primary
candidates and all four reserve names fail the frozen 5% degenerate-bar
gate.** UUP fails on every axis simultaneously and is out unconditionally.
That is what opens Q3 below.

### Q2 — Window ends. **ANSWERED 2026-08-25.**

- **T2 end locked at 12:00.** T2 remains the PRIMARY target and the only one
  that gates the verdict.
- **T3 end locked at the official RTH close** — `15:55` open-labelled, the
  equivalent close-labelled stamp being `16:00`.
- **T3 promoted** from diagnostic to a second pre-declared target: always
  reported, same two-sided rule as T2, **its own trial increment**. The
  family is therefore two trials, and §5 prices the correction.
- **T1 stays diagnostic only** — bounce check, no trial increment, cannot
  produce a result.
- **Frozen sentence, changeable only before the yaml is written:** *a T3-only
  effect with null T2 is NOT a second product.*

Recorded in §2. Neither window moves again.

### Q3 — Gate scope. **ANSWERED 2026-08-26 — neither (a) nor (b).**

The operator declined raw option (b) — a 09:30-only gate with no ATR rule —
and the answer taken instead is a **per-session eligibility rule, E1–E6**,
specified and measured in `docs/STUDY_B_ELIGIBILITY.md`:

- Run 1 gated **instruments**; Study B gates **sessions**, because it reads
  one bar per session. The *definition* of a degenerate bar does not move —
  `valid`, `w_range`, ε and the 5% figure are untouched. What moves is what
  the rule is applied to. **This is an explicit specification change and
  comparability with Run 1 is the accepted price.**
- The ATR condition option (b) lacked is E4/E5: pandas' `ewm` carries the
  last value forward across NaN, so a barely-traded prior session still
  yields a finite, stale `atr_prev`. A `notna()` check would pass exactly the
  sessions needing rejection.
- Instrument admission uses **two** floors — pooled eligible rate ≥ 70% and
  **per-era** eligible rate ≥ 70%. TLT passes the first and fails the second.

**Locked universe: SPY, IWM, GLD, XLE, EEM.** The text below is retained as
the record of what was considered and rejected.

<details>
<summary>Original Q3 as posed (superseded)</summary>

This question did not exist before Q1 was answered, and it is not a
re-opening of a settled choice — it is the consequence of naming instruments
whose data had not been screened.

The frozen 5% degenerate-bar gate is measured across **all** bars of a
session. Study B reads **one** bar per session. For five of the named
instruments those two things disagree sharply — GLD, XLE and USO are
0.00–0.03% degenerate at the 09:30 bar while failing 5.8–7.0%
whole-instrument; TLT and EEM are ~0.5% at the open while failing
15–21% whole-instrument (`docs/STUDY_B_COVERAGE.md` §3).

**To be clear about what is and is not being asked:** this is *not* a
proposal to raise the 5% threshold. The threshold does not move under either
answer. The question is whether the gate should be pointed at the bars this
study actually measures.

**Choose one:**

- **(a) Keep the gate whole-instrument, as Run 1 used it.** Universe becomes
  **SPY + IWM (K=2)**. Detectable IC floor **0.049**, sitting on the "assume
  a bug" threshold. Verdict B is close to certain. Study A and Study B keep
  an identical data standard, so results are directly comparable.
- **(b) Re-scope the gate to the 09:30 bar for this study only.** Universe
  becomes **SPY, IWM, GLD, XLE, TLT, EEM (K=6)** — UUP excluded on coverage
  regardless. Detectable IC floor **~0.034–0.040**. Verdict B still likely
  but no longer near-certain. Cost: Study B's data standard is no longer
  Study A's, and the screen that kept four instruments out of Run 1 is
  weakened for this study.

**Known risk that (b) does not remove, stated before the choice is made:**
every target divides by the prior-session `ATR_20`. An instrument whose
afternoon is 15–21% degenerate (TLT, EEM) is thin in a way that plausibly
contaminates that denominator even when its 09:30 bar is clean. Re-scoping
the gate to the open screens the numerator and leaves the denominator
unscreened. If (b) is chosen, the yaml should carry this as a named
limitation rather than let it surface as a surprise at Step 2.

**No recommendation is made here.** (a) is the conservative reading and
protects comparability; (b) buys the only material power improvement
available and is defensible on the grounds that a gate should measure what
the study measures. Both are legitimate; the trade is the operator's.

</details>

### One-way discipline

All three are one-way choices under constitution rule 1: made in writing,
before any IC existed. **All three are now closed**, and
`docs/preregistration-study-B.yaml` records them. Changing any of them after
Step 5 has run would be re-specification on a result, which voids the run
under constitution rule 3 just as surely as flipping a sign would.

---

## 12. Expected outcome, recorded before the run

`preregistration-study-B.yaml` carries this as `expected_verdict:
B_underpowered`. It is repeated here because it is the single most important
thing to have written down in advance:

**The detectable IC floor on the evaluation history is 0.040–0.046**, after
the two-trial correction (t = 3.21), the 250-session normalisation warm-up
and the 252-session holdout. The plausible band tops out at **0.03**.

**A true effect anywhere inside the plausible band is invisible to this study
by construction.** Verdict B is therefore the expected outcome unless `|IC|`
lands at the very top of, or above, the band.

This is written down so a null is read correctly when it arrives: **a null
here is uninformative, not evidence of absence.** It does not reject the
opening-bar hypothesis; it fails to test it at the resolution that would
matter.

One further consequence worth stating: 0.046 sits close to
`suspicion_threshold.IC` = 0.05. At ρ̄ ≥ 0.5 the smallest effect this study
could detect is already in territory the pre-registration says to treat as a
probable bug. If a result lands there, the pipeline canaries are re-run
before it is believed.

---

**Frozen. `docs/preregistration-study-B.yaml` governs from here. No DQ, no
IC, no Step 5 until the operator accepts the yaml.**
