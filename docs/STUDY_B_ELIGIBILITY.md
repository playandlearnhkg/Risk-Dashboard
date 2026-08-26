# Study B — Proposed Per-Session Eligibility Rule

**Status:** proposal, DATA-ONLY. Nothing here is a result. No `DQ`, no IC, no
T1/T2/T3 value and no hypothesis test was computed. **No ticker is locked and
no `preregistration-study-B.yaml` is written until this table is accepted.**

- Code: `stage1/eligibility_study_b.py`
- Output: `results/study_b_eligibility/eligibility.csv`, `.json`
- Window: 2006-01-03 → 2022-02-28, pre-IEX-break
- Universe screened: SPY, IWM, GLD, XLE, TLT, EEM
  (UUP, FXE, IEF, SLV excluded by operator decision; no 2019-era restart)

---

## 1. What is being changed, stated plainly

**Run 1 gated instruments. This proposal gates sessions.**

| | Run 1 (`docs/preregistration.yaml`) | Study B proposal |
|---|---|---|
| Unit of admission | **Instrument** | **Session** |
| Test | whole-instrument degenerate-bar fraction ≤ 5% | six per-session conditions, below |
| Effect of failing | instrument refused entry entirely | that session produces no observation |
| Instrument-level floor | the 5% gate *is* the floor | **new:** eligible-session rate ≥ 70% |

This is an **explicit specification change**, not a reinterpretation of the
existing gate. It is proposed because Study B reads one bar per session, so the
session is the natural unit of admission — but the change must be recorded as a
change, and it has a real cost, set out in §6.

The underlying **definition** of a degenerate bar does not move. `valid`,
`w_range`, ε and the 5% figure itself are untouched in
`docs/preregistration.yaml`. What moves is what the rule is applied *to*.

---

## 2. The failure mode the rule is built around

This is the reason a "09:30-only gate" without an ATR condition — which the
operator declined — would have been unsafe, and it is worth stating precisely
because it is not obvious from reading the code.

`core.wilder_atr_prev` is a Wilder EWM. **pandas' `ewm` does not propagate
NaN — it carries the last value forward:**

```
pd.Series([1., 2., nan, nan, 4.]).ewm(alpha=.5, adjust=False).mean()
  ->  [nan, 1.5, 1.5, 1.5, 3.6875]
```

So a prior session that barely traded still yields a **finite, entirely
ordinary-looking `atr_prev`** — silently stale, potentially by days. Every
Study B target divides by that number.

The consequence for rule design: a condition of the form `atr_prev.notna()`
is worthless here. It passes exactly the sessions that most need rejecting.
The rule must test **freshness of the inputs**, not presence of the output.
That is what conditions E4 and E5 do, and it is why they exist.

---

## 3. The proposed rule

A session `t` for instrument `i` yields an observation **iff all six hold**:

| # | Condition | Threshold (proposed) | What it protects |
|---|---|---|---|
| **E1** | A priced bar exists at 09:30 on session `t` | — | The Drop rule (`spec-study-B.md` §4). The object of study is the 09:30 bar; a later bar is not a substitute |
| **E2** | That 09:30 bar passes the frozen `valid` flag | unchanged from `preregistration.yaml` | Non-degenerate geometry: range > 0 and range ≥ ε. A flat bar has no `BD`/`CL`/`SA` |
| **E3** | Session `t−1` exists and is within N calendar days | **≤ 5 days** | A vendor hole. Without it, "prior session" can silently mean three weeks earlier across a data gap |
| **E4** | Priced bars in the 20-bar window ending at `t−1`'s last bar | **≥ 16 of 20** | **ATR freshness (§2).** This is the window `atr_prev` nominally sits on; below this it is mostly carried-forward |
| **E5** | Share of session `t−1`'s grid rows that are priced | **≥ 80%** | Wilder's memory is longer than 20 bars (half-life ≈ 13.5 bars, ~95% of weight in ~58). A prior session that was thin all day contaminates the ATR even if its last 100 minutes were dense |
| **E6** | `atr_prev` at the 09:30 bar is finite and ≥ 1 tick | **≥ 0.01** | Divide-by-near-zero. Necessary but, per §2, nowhere near sufficient on its own |

Then, for target coverage:

```
usable_T2 = eligible AND Close_09:35 present AND Close_12:00 present
usable_T3 = eligible AND Close_09:35 present AND Close_15:55 present
```

**Instrument-level floor, replacing Run 1's 5% gate:** admit instrument `i`
only if its **eligible-session rate ≥ 70%**. §6 explains why a per-session
rule still needs an instrument-level floor.

### Why these thresholds and not others

E4 and E5 are the two judgement calls, so both are swept in §5 rather than
asserted. The short version:

- **E4 at 20/20 is not achievable** and would not mean what it looks like.
  SPY's empty-grid fraction is 3.5%, so an average 20-bar window carries
  ~19.3 priced bars and demanding all 20 fails routinely on healthy sessions.
  The STRICT row in §5 shows this: it cuts **SPY itself to 53%**. A threshold
  that rejects half of the cleanest instrument in the sample is measuring the
  grid, not the market.
- **16/20 (80%) is the tightest defensible setting.** It is far enough below
  20 to tolerate ordinary grid holes and far enough above 12 to reject a
  genuinely stale ATR.
- **E5 at 80%** is set to match E4 so the two conditions express one standard
  at two timescales, rather than two arbitrary numbers.

---

## 4. Results — sessions surviving the rule (PROPOSED thresholds)

| Ticker | Sessions | Eligible | Eligible rate | **usable T2** | **usable T3** | Worst era rate | Worst era |
|---|---|---|---|---|---|---|---|
| SPY | 4,066 | 3,667 | 90.19% | **3,443** | **3,390** | 86.89% | 14–17 |
| IWM | 4,064 | 3,527 | 86.79% | **3,269** | **3,271** | 84.41% | 14–17 |
| GLD | 4,064 | 3,675 | 90.43% | **3,459** | **3,538** | 88.87% | 10–13 |
| XLE | 4,064 | 3,431 | 84.42% | **3,146** | **3,205** | 81.93% | 14–17 |
| EEM | 4,064 | 3,576 | 87.99% | **3,360** | **3,382** | 77.09% | 06–09 |
| **TLT** | 4,064 | 3,311 | 81.47% | **3,109** | **3,152** | **46.51%** | **06–09** |

All six clear the pooled 70% floor. **TLT does not clear the per-era floor.**

### Where the sessions are lost (attrition in rule order)

Each column counts sessions removed from those still standing after the
conditions before it — so the numbers sum to the total loss without
double-counting.

| Ticker | E1 no 09:30 | E2 open degenerate | E3 no prior | E4 ATR stale | E5 prior thin | E6 ATR unusable |
|---|---|---|---|---|---|---|
| SPY | 389 | 1 | 0 | 7 | 2 | 0 |
| IWM | 524 | 0 | 0 | 11 | 2 | 0 |
| GLD | 374 | 1 | 0 | 12 | 2 | 0 |
| XLE | 606 | 1 | 0 | 25 | 1 | 0 |
| EEM | 453 | 19 | 0 | 12 | 2 | 2 |
| **TLT** | 532 | 18 | 0 | **158** | **45** | 0 |

Two things this table settles:

1. **E1 — the missing 09:30 bar — is almost the entire cost of the rule.**
   For five of six names, E2–E6 together remove between 3 and 28 further
   sessions out of ~4,000. The ATR conditions are cheap insurance, not a
   second gate. That is the answer to "does adding an ATR rule cost the
   universe?" — no, it does not.
2. **TLT is the exception and by an order of magnitude.** 158 sessions lost
   to a stale ATR window against 7–25 for everything else. TLT is the only
   name where the ATR-freshness condition is doing heavy lifting, which is
   the same thing as saying TLT is the only name whose prior sessions are
   routinely too thin to normalise against.

### Eligible rate by era (PROPOSED)

| Ticker | 06–09 | 10–13 | 14–17 | 18–22 |
|---|---|---|---|---|
| SPY | 0.908 | 0.895 | 0.869 | 0.935 |
| IWM | 0.874 | 0.864 | 0.844 | 0.889 |
| GLD | 0.897 | 0.889 | 0.922 | 0.909 |
| XLE | 0.864 | 0.847 | 0.819 | 0.847 |
| EEM | **0.771** | 0.911 | 0.922 | 0.915 |
| **TLT** | **0.465** | 0.938 | 0.918 | 0.932 |

**This is the most important table in the document.** Five names are flat
across sixteen years — their eligible sessions are drawn roughly evenly from
every regime. TLT is not: it loses **more than half of 2006–2009** and is
then normal for the rest of the sample.

The pooled rate (81.47%) hides this completely. An instrument-level floor
that only looked at the pooled figure would admit TLT without comment.

---

## 5. Threshold sweep

The two judgement calls (E4, E5) swept, so the proposed setting is a choice
between shown alternatives rather than an assertion.

| Variant | E4 | E5 | E3 gap | SPY | IWM | GLD | XLE | EEM | TLT |
|---|---|---|---|---|---|---|---|---|---|
| **Loose** | ≥12/20 | ≥60% | ≤7d | 3,676 | 3,539 | 3,689 | 3,457 | 3,590 | 3,411 |
| **Proposed** | ≥16/20 | ≥80% | ≤5d | 3,667 | 3,527 | 3,675 | 3,431 | 3,576 | 3,311 |
| **Strict** | 20/20 | ≥90% | ≤4d | 2,174 | 2,022 | 2,117 | 1,807 | 2,068 | 1,724 |

(Eligible sessions. Rates: Loose 84–91%, Proposed 81–90%, Strict **42–53%**.)

Reading:

- **Loose → Proposed costs almost nothing** for five names (9–26 sessions)
  and costs TLT 100. The tightening is doing exactly one thing: separating
  TLT from the rest. That is a reason to trust the threshold, not to suspect
  it — it was not chosen to produce that separation, and moving it either way
  by a wide margin leaves the other five names untouched.
- **Strict is not a viable option and should not be read as "the safe
  choice."** Requiring all 20 bars priced cuts **SPY itself to 53%** and
  every name to 42–53%. At a 3.5% empty-grid rate an average 20-bar window
  holds ~19.3 priced bars, so 20/20 rejects healthy sessions for having an
  ordinary grid hole. It measures the vendor's grid, not the market.

The proposed setting sits at the top of the range where the rule still
discriminates between instruments rather than between grid artefacts.

---

## 6. What this rule does NOT fix

Stated before any ticker is locked, because each of these is a limitation the
frozen yaml should carry rather than a surprise for Step 2.

**1. Eligible sessions are a selected subsample, not a random one.** Sessions
are excluded for illiquidity, and illiquidity correlates with volatility
regime, holidays, and crisis periods. Even for the five era-flat names, the
~10–16% of excluded sessions are not a random 10–16%. Run 1 did not have this
problem in the same form: it admitted whole instruments and used every
session of them. **This is the real cost of moving the gate from instrument
to session, and it is not removable by choosing better thresholds.** What the
per-era floor does is bound the damage, not eliminate it.

**2. The ATR conditions screen freshness, not accuracy.** E4 and E5 establish
that `atr_prev` was computed from bars that actually existed. They cannot
establish that its *level* is right — an HF session that recorded 85% of its
bars may still understate the day's true range, exactly as
`docs/DATA_AUDIT.md` §2 found on big-move days. Every target divides by this
number, so a systematically understated ATR inflates every target
symmetrically. That is a scale effect rather than a sign effect, but it means
target magnitudes are not directly comparable to Run 1's.

**3. It does not improve power.** Under PROPOSED, mean usable T2 across the
six names is ~3,298 sessions:

| Universe | K | mean usable T2 | ρ̄ | K_eff | n_eff | Detectable IC (t=3.0) |
|---|---|---|---|---|---|---|
| All six | 6 | 3,298 | 0.30 | 2.40 | 7,914 | **0.034** |
| All six | 6 | 3,298 | 0.40 | 2.00 | 6,595 | **0.037** |
| All six | 6 | 3,298 | 0.50 | 1.71 | 5,647 | **0.040** |
| Five (no TLT) | 5 | 3,335 | 0.35 | 2.13 | 7,096 | **0.036** |
| Five (no TLT) | 5 | 3,335 | 0.45 | 1.79 | 5,957 | **0.039** |

**Verdict B (underpowered) remains the expected outcome under every row**, as
`spec-study-B.md` §5 already states. The eligibility rule makes the universe
*admissible*; it does not make the study *powered*. Nothing in this document
changes that, and it should not be read as having done so.

**4. It is a spec change, and comparability with Run 1 is the price.** Study A
and Study B will no longer have admitted data by the same procedure. Any
statement of the form "Study B found X where Study A found Y" carries an
asterisk from here on.

---

## 7. The one decision this table forces: TLT

Keeping TLT under the pooled floor alone means accepting an instrument that
contributes **less than half** of the 2006–2009 era — the financial crisis,
which for a long-duration Treasury ETF is the single most information-bearing
stretch of the sample. The sessions TLT would contribute are conditioned on
its having traded densely, in the era when it most often did not.

The cost of dropping it is small but not zero:

- At fixed ρ̄, dropping TLT moves the detectable floor from 0.034 to 0.035 —
  negligible.
- Realistically ρ̄ **rises** when TLT goes, because TLT is the only
  non-equity, non-commodity name left; SPY, IWM, XLE and EEM are all equity
  and GLD is the sole diversifier. Allowing for that, the floor moves roughly
  0.035 → 0.039, about 10%.
- **The diversification loss is the real cost, and it is not captured by the
  IC floor at all.** Dropping TLT makes Study B a study of equity ETFs plus
  gold, which narrows what any result would generalise to — the same
  limitation `RUN1_INFERENCE_MEMO.md` §3 recorded against Run 1.

**Recommendation: drop TLT, admit the other five.** The era table is a
measured selection problem with a known direction; the power loss is a
modelled ~10% on a floor that already fails to reach the plausible band under
every scenario. Trading a real bias for a marginal change in a number that is
not going to be decisive either way is the right trade. EEM at 77.1% in
06–09 is the next-weakest and clears the floor with room; it should be
recorded as a named watch-item rather than excluded.

That is a recommendation, not a decision. The alternatives are equally
specifiable and both are legitimate:

- **Admit all six**, with TLT's era imbalance recorded as an explicit
  limitation in the yaml.
- **Pause Study B.** Nothing in this document argues against that, and §6.3
  is the strongest case for it: the universe is now admissible, and the study
  is still expected to return Verdict B.

---

**No ticker is locked and no `preregistration-study-B.yaml` is written until
this table is accepted.**

