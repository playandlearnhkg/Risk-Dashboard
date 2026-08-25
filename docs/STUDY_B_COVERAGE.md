# Study B — DATA-ONLY Coverage Screen

**Purpose:** decide which instruments Study B can lawfully ask its question
of, **before** tickers are locked and before `preregistration-study-B.yaml`
is written.

**What was computed:** coverage and the frozen 5% degenerate-bar gate.
**What was NOT computed:** no `DQ`, no IC, no forward return, no T1/T2/T3
value, no hypothesis test. Presence and validity only. The screen touches
`core.candle_features` for exactly one column — the frozen `valid` flag — and
drops the score columns on the next line, so the gate lives in one place and
cannot drift.

- Code: `stage1/coverage_study_b.py`
- Output: `results/study_b_coverage/coverage.csv`, `coverage.json`
- Window: **2006-01-03 → 2022-02-28**, pre-IEX-break, same as Run 1
- Run: 2026-08-25. SPY and IWM read from the Run 1 validated bars in
  `data/clean/`; the other nine pulled live from HF and resampled through the
  unchanged `stage1.hf_prepare` rules (RTH before resample, incomplete bins
  dropped, holes left NaN, nothing forward-filled).

---

## 1. The table

| Ticker | Role | Sessions | 09:30 missing | Usable (Drop) | Usable T2 | Usable T3 | Invalid frac | **5% gate** | 09:30 degen when present | Earliest era passing 5% | Empty grid |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **SPY** | primary | 4,066 | 9.57% | 3,676 | 3,452 | 3,399 | **3.87%** | **PASS** | 0.00% | 2006 | 3.54% |
| **IWM** | primary | 4,064 | 12.89% | 3,540 | 3,282 | 3,283 | **4.21%** | **PASS** | 0.00% | 2006 | 3.72% |
| GLD | primary | 4,064 | 9.20% | 3,689 | 3,471 | 3,552 | 5.82% | **FAIL** | 0.00% | 2019 | 3.96% |
| XLE | primary | 4,064 | 14.91% | 3,457 | 3,169 | 3,229 | 6.98% | **FAIL** | 0.00% | 2018 | 4.51% |
| TLT | primary | 4,064 | 13.09% | 3,514 | 3,209 | 3,304 | 15.19% | **FAIL** | 0.51% | 2019 | 9.86% |
| EEM | primary | 4,064 | 11.15% | 3,592 | 3,374 | 3,396 | 20.86% | **FAIL** | 0.50% | never | 3.91% |
| UUP | primary | 3,602 | **29.96%** | 835 | **480** | 684 | **93.92%** | **FAIL** | **66.90%** | never | 46.68% |
| USO | reserve | 3,997 | 12.33% | 3,502 | 3,265 | 3,384 | 6.43% | **FAIL** | 0.03% | 2015 | 5.68% |
| SLV | reserve | 3,984 | 10.22% | 3,246 | 3,004 | 3,098 | 46.95% | **FAIL** | 9.25% | never | 6.90% |
| IEF | reserve | 4,062 | 27.65% | 2,742 | 1,864 | 2,335 | 56.65% | **FAIL** | 6.70% | never | 30.19% |
| FXE | reserve | 3,911 | **45.26%** | 2,077 | **815** | 1,443 | 66.08% | **FAIL** | 2.99% | never | 61.99% |

Column definitions are in the module docstring; the two that carry the most
weight:

- **Usable T2** — sessions surviving the §4 Drop rule *and* carrying a
  non-degenerate 09:30 bar with a warm prior-session ATR *and* carrying both
  closes T2 needs (09:35 and 12:00). This is the number that goes into the
  power arithmetic, not `sessions`.
- **09:30 degen when present** — the degenerate-bar rate restricted to
  sessions where a 09:30 bar actually exists. It separates "no recording" from
  "flat bar", which the whole-instrument `invalid_fraction` conflates.

**Cross-check:** SPY 9.57% / IWM 12.89% missing-open reproduce
`docs/DATA_AUDIT.md` exactly, and SPY 3.87% / IWM 4.21% reproduce the Run 1
validator. The screen is measuring the same thing the frozen pipeline
measures.

---

## 2. Headline: nine of eleven names fail the frozen gate

**Only SPY and IWM pass the 5% degenerate-bar gate as it is currently
written.** Five of the seven **primary** candidates fail — GLD, XLE, TLT,
EEM, UUP — and all four reserve names fail.

This is not a near miss for most of them. GLD (5.82%) and USO (6.43%) are
close to the line; TLT (15.19%), EEM (20.86%), SLV (46.95%), IEF (56.65%),
FXE (66.08%) and UUP (93.92%) are not close to anything.

Two of these were **already known to fail** from Run 1 and are unchanged
here: TLT at 15.19% and GLD at 5.82% in the *primary* list, SLV at 46.95%
and FXE at 66.08% in the *reserve* list. `docs/spec-study-B.md` §8 currently
lists "relaxing the 5% degenerate-bar gate to keep TLT, GLD or FXE" as
explicitly **out of scope**, so the proposed universe and the current spec
contradict each other. That contradiction is put to the operator in §11 Q3
rather than resolved here.

### UUP is unusable on any reading

UUP is the one name that fails on every independent axis at once: 3,602
sessions (shortest history), 29.96% of opens missing, 93.92% whole-instrument
degenerate, and — decisively — **66.90% of its 09:30 bars are flat even when
present**. Only **480 sessions** survive to a usable T2. There is no version
of the gate, no era restriction and no missing-open rule under which UUP
contributes information to this study. It should be dropped regardless of how
Q3 is answered.

---

## 3. The distinction the gate does not currently make

Study B reads **one bar per session** — the 09:30 bar. The frozen gate
measures degeneracy across **all** bars in the session. For five names those
two things disagree sharply:

| Ticker | Whole-instrument invalid | 09:30 degen when present | Where the failure lives |
|---|---|---|---|
| GLD | 5.82% | **0.00%** | Midday / afternoon only |
| XLE | 6.98% | **0.00%** | Midday / afternoon only |
| USO | 6.43% | **0.03%** | Midday / afternoon only |
| TLT | 15.19% | **0.51%** | Overwhelmingly away from the open |
| EEM | 20.86% | **0.50%** | Overwhelmingly away from the open |
| SLV | 46.95% | 9.25% | Both — open is also degraded |
| IEF | 56.65% | 6.70% | Both — open is also degraded |
| FXE | 66.08% | 2.99% | Whole-instrument, plus 45% of opens simply absent |
| UUP | 93.92% | **66.90%** | Everywhere, including the open |

The opening bar is the most liquid bar of the day, so this pattern is what
one would expect if the gate is doing its job on afternoon illiquidity while
Study B's actual measurement surface is clean. **That is an argument, not a
decision.** Re-scoping the gate to the 09:30 bar would:

- **Gain:** a defensible 6-name universe (SPY, IWM, GLD, XLE, TLT, EEM),
  moving the detectable-IC floor from 0.049 to ~0.034–0.040 (`spec-study-B.md` §5).
- **Cost:** the gate stops being the gate Run 1 used, so Study B's data
  standard and Study A's are no longer the same standard. Comparisons between
  them get an asterisk. It also weakens a protection that has already done
  real work — it is what stopped four instruments entering Run 1.
- **Risk it does not remove:** a name whose *afternoon* is 20% degenerate
  (EEM, TLT) is thin in a way that plausibly shows up in the prior-session
  ATR normaliser, which every target divides by, even when the 09:30 bar
  itself is clean. Re-scoping the gate to the open does not screen the
  denominator.

That last point is the reason I am not recommending the re-scope as an
obvious call. It is a genuine spec change with a genuine cost.

---

## 4. Era restriction is not a way out

The `earliest_era_passing_5pct` column asks: is there a later start date from
which this instrument would pass the gate on the remaining window? For most
names the answer is no, and where it is yes the price is the study.

| Ticker | Earliest passing era | Sessions remaining to 2022-02-28 |
|---|---|---|
| USO | 2015 | ~1,800 |
| XLE | 2018 | ~1,050 |
| GLD | 2019 | ~800 |
| TLT | 2019 | ~800 |
| EEM, SLV, IEF, FXE, UUP | **never** | — |

Trading ~3,300 usable sessions for ~800 to buy one extra instrument is a
straight loss: the session count enters `n_eff` linearly and `K_eff` is
capped by the breadth ceiling. Cutting history to add breadth moves in
exactly the wrong direction, and it would also mean the universe no longer
shares a common window. **Era restriction is closed as an option.**

---

## 5. Coverage of T2 and T3 endpoints

For every name that survives at all, the T3 endpoint is available on *more*
sessions than the T2 endpoint (e.g. GLD 3,552 vs 3,471; TLT 3,304 vs 3,209).
The 12:00 bar is missing slightly more often than the closing bar. This is a
small effect for the healthy names and does not change any ranking, but it
means **T2 and T3 will not run on identical session sets**. Two consequences
for the yaml, neither of them optional:

1. The two targets' `n_eff` figures must be computed separately, not shared.
2. Any T2-vs-T3 comparison (§3's mechanism ranking depends on one) must be
   made on the **intersection** of the two session sets, or the difference
   between them partly reflects which sessions each target could be computed
   on rather than how the effect decays.

---

## 6. What this table decides and what it does not

**Decides:**
- UUP is out, unconditionally (§2).
- Era restriction is closed (§4).
- SPY + IWM are usable under the gate exactly as frozen.
- T2 and T3 need separate session accounting (§5).

**Does not decide — operator call, put in `spec-study-B.md` §11 Q3:**
- Whether the 5% gate stays whole-instrument (→ universe is SPY + IWM, K=2,
  detectable floor 0.049, Verdict B near-certain) or is re-scoped to the
  09:30 bar (→ universe is SPY, IWM, GLD, XLE, TLT, EEM, K=6, floor
  ~0.034–0.040, Verdict B still likely).

**Not in question either way:** under every option on the table, Study B goes
in expecting **Verdict B (underpowered)** for any effect in the plausible
0.01–0.03 band. The universe expansion narrows that gap; it does not close
it. That should be accepted before the run, not discovered at Step 2.

---

**No ticker is locked and no pre-registration is written until this table is
accepted.**
