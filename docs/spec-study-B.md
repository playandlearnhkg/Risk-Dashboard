# Study B — Opening-Bar Predictivity Spec

**Status:** DRAFT. Not accepted. **Do not implement until the user accepts
this spec.**
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

## 1. Claim and sign

> **H1:** On a 5-minute RTH bar, a higher Directional Quality (`DQ`) score on
> the **09:30 opening bar** is followed by a better forward outcome in the
> same direction (continuation), over a pre-declared forward window.

**Sign is locked:** positive. Higher `DQ` at the open → higher signed forward
return.

**A reversed sign is K7 — a rejection of H1, not a fade product.** Exactly as
in Run 1, if the observed relationship runs the opposite way, the finding is
"H1 rejected for the opening bar", full stop. Testing a fade hypothesis on the
opening bar requires its own spec, its own sign declared in advance, and data
this study has not touched. Constitution rule 3 applies without exception.

---

## 2. Target definitions

All three targets are **one observation per session per instrument** —
unlike Run 1's `r_1`, which was one observation per bar. This has a direct
power consequence worked out in §4: switching targets does not change the
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

### Why T2 is primary

The programme goal (§0, `docs/programme.md`) is a filter for an ORB-style
setup: *"clean enough to take, sloppy enough to wait."* That decision is made
once, at or shortly after the open, and lived with for the trade's holding
period — not re-evaluated bar by bar.

- **T1 is too granular for the stated purpose**, and it is the horizon most
  exposed to the mechanism `docs/RUN1_INFERENCE_MEMO.md` flagged as the
  leading (untested) explanation for Run 1's own reversed tilt: bid-ask
  bounce. A single 5-minute transition immediately after the open is exactly
  where that effect would be strongest. Reporting T1 lets that be checked;
  gating the verdict on it would risk re-measuring microstructure and calling
  it information.
- **T3 dilutes the signal with unrelated afternoon dynamics.** A morning
  setup's information content, if any, should decay well before the close;
  folding in six more hours of unrelated variance is not the ORB-filter
  question.
- **T2 matches the holding period an ORB-style filter actually cares about**
  and stays close enough to the open that a causal story from opening-bar
  geometry to outcome remains plausible.

The 09:35–12:00 window is provisional — a placeholder that can be tightened
(e.g. 09:35–10:30) at freeze time. It must not move after data is seen.

---

## 3. Missing-open rule

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

The power cost of Drop is carried through explicitly in §4 rather than
glossed over.

---

## 4. Universe and power (computed before freeze, t = 3.0)

Session counts and missing-open rates: `docs/DATA_AUDIT.md`. `n_eff`
methodology: `stage1.stats.effective_sample_size` (unchanged — see §9).
`K_eff = K / (1 + (K−1)·ρ̄)`.

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

## 5. Holdout

Study-specific. **Not** Run 1's 252-session holdout treated as 252
observations — Run 1's holdout carried ~78 bars × 252 sessions per
instrument; Study B carries **one** observation per session.

Proposed default, sized to the same session-count convention as Run 1 for
comparability: **last 252 sessions**, sealed at freeze, one look, after
Step 5 on the evaluation history. Under the Drop rule (§3), the realised
observation count in that window is:

```
252 sessions x (1 - missing_open_rate)
  SPY (9.57%)  -> ~228 observations
  IWM (12.89%) -> ~220 observations
```

**~220–230 observations is far below any detection threshold in §4.** That
is fine, because the holdout's role here is narrower than in Run 1: it can
only **confirm the sign** of an already-frozen effect (a one-sided check
against the pre-declared H1 direction), not re-estimate an effect size or
serve as a second discovery pass. This must be written into the frozen
pre-registration explicitly, so a null result on the holdout is not
mistaken for a power failure of the holdout itself — it is expected to be
underpowered for estimation and is not being asked to estimate anything.

Per constitution rule 7, it is looked at once, after the claim is frozen.

---

## 6. Source policy

- **HF Data Library may be used only under the missing-open rule in §3
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

## 7. Out of scope

- All-day rerun of Study A (Run 1 is closed; see `docs/RUN1_INFERENCE_MEMO.md`)
- Fade / reversal read from Run 1's reversed sign
- Stage 2 — filtering live ORB trades
- Footprint / volume profile
- Relaxing the 5% degenerate-bar gate to keep TLT, GLD or FXE
- **Computing any IC before this spec is accepted**

---

## 8. Acceptance checks before any code or data work

- [ ] Claim (§1) and sign frozen
- [ ] Primary target (§2, T2) frozen; T1/T3 confirmed as reported-not-gating
- [ ] Missing-open rule (§3, Drop) frozen
- [ ] Universe frozen, with its detectable-IC floor (§4) accepted as a known
      limitation rather than discovered later
- [ ] Detectable IC written down (§4) — including the breadth-ceiling table
- [ ] Holdout named and its thin observation count (§5) accepted in advance
- [ ] Pointer confirmed: reuse `stage1.gates` canaries, `stage1.validate`,
      `stage1.power`, `stage1.run_all` — no rewrite (§9)

---

## 9. Mapping to the existing pipeline

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
  1. Applies the Drop rule (§3) per session.
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

**Do not implement until the user accepts this spec.**
