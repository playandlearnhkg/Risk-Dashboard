# Study B — Opening-Bar Predictivity Spec

**Status:** DRAFT. Not accepted. **Do not implement until the user accepts
this spec.** Two freeze questions are open and blocking — §11 — and no yaml
or code is written until they are answered.
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

| Target | Definition | Role |
|---|---|---|
| **T1** | `(Close_09:35 − Close_09:30) / ATR_20(prior close)` | Secondary / diagnostic |
| **T2** | `(Close_12:00 − Close_09:35) / ATR_20(prior close)` | **PRIMARY** |
| **T3** | `(Close_15:55 − Close_09:35) / ATR_20(prior close)` | Secondary / diagnostic |

T1 and T3 are reported on every run, exactly as Run 1 reported `y_body`
alongside primary `r_1` — never gating the verdict, always disclosed.

**Pre-declared reading rule for T1 vs T2, fixed now, before either number
exists:**

> If T1 shows a negative, stable effect and T2 does not show the same effect
> (in size and stability), T1 is read as **consistent with bid-ask
> bounce / spread mechanics**, not reported as a standalone fade signal. It
> is a diagnostic outcome, not a second product of this study. Only if T2
> — the primary target — itself shows a stable effect does §3's mechanism
> ranking apply to the headline result.

This rule exists so that a T1-only effect cannot quietly become "Study B
found a fade edge" by virtue of being computed and looking clean in
isolation. T1's whole role is as a control that can *explain away* part of
a T2 finding, not as a second hypothesis competing for attention.

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
- **T3 dilutes the signal with unrelated afternoon dynamics.** A morning
  setup's information content, if any, should decay well before the close;
  folding in six more hours of unrelated variance is not the ORB-filter
  question, whichever direction that information runs.
- **T2 matches the holding period an ORB-style filter actually cares about**
  and stays close enough to the open that a causal story from opening-bar
  geometry to outcome — in either direction — remains plausible.

The 09:35–12:00 window is provisional — a placeholder that can be tightened
(e.g. 09:35–10:30) at freeze time. It must not move after data is seen. This
is one of the two freeze questions still open; see §10.

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
sessions (389 / 4,066)** and **12.89% of IWM sessions (524 / 4,064)**. Since
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

Session counts and missing-open rates: `docs/DATA_AUDIT.md`. `n_eff`
methodology: `stage1.stats.effective_sample_size` (unchanged — see §10).
`K_eff = K / (1 + (K−1)·ρ̄)`.

**Two-sided testing does not change this table, and does not fix the 2-name
problem.** §1's revision removes the sign restriction on the *hypothesis*,
not on the *arithmetic*. `n_eff`, `K_eff` and the detectable-IC floor come
from the sampling variance of the estimator (`t = IC·√n_eff`), which is
identical whether the test asks "is IC positive" or "is `|IC|` large" —
going two-sided changes the critical value's interpretation, not `n_eff`
itself. A two-sided test at the same `α` is in fact very slightly *less*
sensitive per unit of `n_eff`, not more, because the same significance
budget is split across both tails instead of spent on one. **Concretely: the
2-name universe's detectable floor stays 0.047 whether H1 is signed or not.**
Going two-sided was the right response to genuine uncertainty about
direction — it is not, and must not be read as, a power upgrade.

**Caveat that must travel with every row below:** `K_eff` for the 2-name
row reuses **1.12**, Run 1's measured value from *all-day* 5-minute bars. It
is a placeholder for the opening bar specifically, not a measurement — the
opening print across correlated ETFs could plausibly be *more* tightly
coupled (shared overnight news, shared index-open mechanics) than the
all-day average. This must be re-measured, not assumed, once real opening-bar
scores exist (Step 2 of the eventual run, before Step 5).

| Universe | Per-instrument usable sessions (Drop rule) | ρ̄ | K_eff | n_eff | Detectable IC (t=3.0) | Verdict |
|---|---|---|---|---|---|---|
| **SPY + IWM** (K=2) | 3,609 avg | 0.79 (Run 1, all-day, placeholder) | 1.12 | **4,042** | **0.047** | Outside 0.01–0.03 band; sits at the edge of the >0.05 "treat as a bug" zone |
| ~50 names, ρ̄=0.3 | 3,609 (assumed avg) | 0.30 | 3.19 | **11,495** | **0.028** | Barely inside the plausible band, at its top edge |
| ~50 names, ρ̄=0.5 (more realistic at the open) | 3,609 (assumed avg) | 0.50 | 1.96 | **7,077** | **0.036** | Outside the band, elevated |

**Honest statement, as required:** with the 2-name universe, this study is
very likely to hit **Verdict B (underpowered)** before any score is even
computed — its detectable floor (0.047) sits almost exactly on the
pre-registered "assume a bug" threshold (0.05) from `docs/preregistration.yaml`
`suspicion_threshold`. A true effect anywhere in the plausible 0.01–0.03 band
would be invisible to a 2-name opening-bar study.

### The breadth ceiling — why more names does not fully fix this

Holding the per-instrument session count fixed at ~3,609 (the history does
not grow), `K_eff` has a hard limit as `K → ∞`: **`K_eff → 1/ρ̄`**. This
gives a floor on the detectable IC that **no amount of breadth can cross**:

| ρ̄ | K_eff limit (K→∞) | n_eff limit | IC floor (t=3.0) |
|---|---|---|---|
| 0.30 | 3.33 | 12,031 | **0.027** |
| 0.50 | 2.00 | 7,219 | **0.035** |

Even an infinite universe of names correlated at ρ̄=0.5 cannot detect an
IC below 0.035. This is constitution rule 5 — *"more tickers do not create
more years"* — made quantitative for the opening-bar case: at these
correlations, no feasible universe reaches the **bottom** of the plausible
band. Reference points for what *would* be needed:

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
252 sessions x (1 - missing_open_rate)
  SPY (9.57%)  -> ~228 observations
  IWM (12.89%) -> ~220 observations
```

**~220–230 observations is far below any detection threshold in §5.** That
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
- Relaxing the 5% degenerate-bar gate to keep TLT, GLD or FXE
- **Computing any IC before this spec is accepted**

---

## 9. Acceptance checks before any code or data work

- [ ] Claim (§1) frozen — two-sided, no direction assumed
- [ ] Primary target (§2, T2) frozen; T1/T3 confirmed as reported-not-gating,
      per the T1-vs-T2 bounce reading rule in §2
- [ ] Mechanism table (§3) accepted as pre-declared and closed to later addition
- [ ] Missing-open rule (§4, Drop) frozen
- [ ] Universe frozen, with its detectable-IC floor (§5) accepted as a known
      limitation rather than discovered later
- [ ] Detectable IC written down (§5) — including the breadth-ceiling table
- [ ] Holdout named and its thin observation count (§6) accepted in advance
- [ ] Pointer confirmed: reuse `stage1.gates` canaries, `stage1.validate`,
      `stage1.power`, `stage1.run_all` — no rewrite (§10)

---

## 10. Mapping to the existing pipeline

**Reused unchanged — no rewrite, per programme instruction:**

- `stage1/core.py` — `candle_features`, `DQ`/`DIR`/`CONV` construction, the
  degenerate gate, `w_range`. The opening bar is scored with the identical
  function used on every other bar; nothing about the score changes.
- `stage1/io.py`, `stage1/validate.py` — same manifest, same 5% abort, same
  resampling rules. Study B needs **no new HF pull** for SPY/IWM: it reads
  the already-validated bars in `data/clean/`.
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

## 11. Freeze questions still open — blocking

Everything above this line is drafted and internally consistent, but two
choices belong to the operator, not to this document, and neither has been
answered yet. **No `preregistration-study-B.yaml` and no code (including the
opening-bar selector in §10) is written until both are answered.**

1. **Universe.** §5 shows the 2-name universe (SPY + IWM) has a detectable
   floor of IC 0.047 — almost exactly on the pre-registered "assume a bug"
   threshold, meaning a true effect anywhere in the plausible 0.01–0.03 band
   would be invisible to it, and the study would very likely return
   **Verdict B (underpowered)** at Step 2 before any score is computed. §5
   also shows that breadth has a hard ceiling at these correlations (IC
   0.027–0.035, never reaching below it, however many names are added).

   **Choose one:**
   - **(a)** Accept the 2-name universe as is, accepting that Verdict B is
     the likely outcome and treating a successful run past Step 2 as a
     bonus rather than an expectation.
   - **(b)** Name a larger universe now — not "add some names later," but a
     specific list, sized and its `ρ̄`/`K_eff` re-estimated (§5's 0.3/0.5
     rows are planning assumptions, not a menu) — understanding it still
     cannot reach the bottom of the plausible band per the breadth-ceiling
     result.

2. **T2 window end.** §2 fixed T2 as 09:35–12:00 as a *provisional*
   placeholder, reasoned from holding-period fit, not derived from data.

   **Choose one:**
   - **(a)** Freeze 12:00 as written.
   - **(b)** Change it now — e.g. 09:35–10:30 for a tighter ORB-length hold —
     before any freeze, not after seeing how either version performs.

Both are one-way choices under constitution rule 1: made now, in writing,
before data is touched. Changing either after Step 5 has run would be
re-specification on a result, which voids the run under constitution rule 3
just as surely as flipping a sign would.

---

**Do not implement until the user accepts this spec.**
