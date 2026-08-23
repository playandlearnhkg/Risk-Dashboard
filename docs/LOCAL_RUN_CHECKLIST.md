# Stage 1 — Local Run Checklist

Read once before the first local run. Everything here is procedure, not theory;
the reasoning lives in `CANDLE_SCORING_STAGE1_PREDICTIVITY.md`.

---

## 0. Resolve the source discrepancy FIRST

`preregistration.yaml` currently declares:

```yaml
data:
  source: hfdatalibrary.com
  era_restriction: pre_iex_break
  era_end: 2022-02-28
  resampling: {min_minutes_per_bar: 4, ...}
```

If the local run uses **Futu** data (or anything else), that block is wrong and
must be corrected **before** any step runs. Correcting it now is legitimate —
no result has been seen. Correcting it after is not.

What changes with the source:

| Field | If Futu / other | Why it matters |
|---|---|---|
| `source` | change it | the record must say what produced the numbers |
| `era_restriction` / `era_end` | **probably drop entirely** | the IEX break is an HF Data Library artefact. Another vendor has its own breaks, or none |
| `known_limitations` | rewrite | HF's survivorship note does not describe a different vendor |
| `resampling` | drop if bars arrive as 5-minute | those rules describe *our* 1-min→5-min step. If someone else aggregated, the rules were theirs and are unknown — which is what the provenance checks in `stage1.inspect` and `stage1.validate` exist to probe |

**Do not leave a stale source block in place "because it is nearly right".**
The pre-registration is the record of what was decided; a wrong record is worse
than no record.

---

## 1. Environment

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-stage1.txt
export PYTHONPATH=.
```

Pinned versions are part of the result (spec 5.6), not an implementation
detail: library upgrades silently change rank-tie handling and rolling-window
edges. `stage1.run_all` stamps the versions it actually used into
`run_report.json`. If those differ from `requirements-stage1.txt`, the run is
not comparable to an earlier one.

Verify the pipeline before pointing it at real data:

```bash
python tests/test_stage1.py        # 29 tests, no pytest needed
python docs/stage1_reference.py    # section 5.6 gates on synthetic bars
```

Both must pass. If they do not, nothing downstream is trustworthy.

---

## 2. Describe the data before declaring anything

```bash
python -m stage1.inspect /path/to/bars/*.csv --emit-manifest data/manifest.yaml
```

Reports column mapping, timestamp form, timezone, **bar label**, session window,
bars per session, inferred tick, and the fingerprints of someone else's
resampling. Writes a draft manifest.

Then fill in by hand the two things bars cannot reveal:

- `adjustment` — multiplicative or none. **Additive is rejected**; it corrupts
  intrabar ratios.
- `vendor` — for the record.

---

## 3. Run

```bash
python -m stage1.run_all --manifest data/manifest.yaml --out results/run1
```

Runs steps 1 → 2 → 3 → 5 in order and stops at the first gate. It refuses to
start unless the pre-registration reads `FROZEN_ANALYSIS`.

The order is not a convenience. Each step can end the study and each is cheaper
than the one after it. Running them out of order, or continuing past a failure
"just to look", is how a study talks itself into a result.

Expected runtime at 4 instruments × ~4,000 sessions (≈1.25M bars): **20–30
minutes**, dominated by the Jonckheere–Terpstra permutations in Step 5.

### What the outcomes mean

| Outcome | Meaning | Next |
|---|---|---|
| `STOPPED_AT_STEP_1` | red flag in the data | fix the data or the manifest |
| `STOPPED_AT_STEP_2` | **Verdict B — underpowered** | get more *history*. More instruments will not help (see §5) |
| `STOPPED_AT_STEP_3` | **K8 — pipeline untrustworthy** | fix and re-run everything; no earlier number stands |
| `STOPPED_AT_STEP_5` | **Verdict C — no useful predictivity** | a complete result. Record it and stop |
| `COMPLETED_THROUGH_STEP_5` | no kill gate fired | continue to execution steps 6+ |

`COMPLETED_THROUGH_STEP_5` is **not** Verdict A. Verdict A needs all of G1–G7,
and G5–G7 require the bootstrap CI, FDR correction and component comparison
from steps 7, 12 and 13. Step 5 leaves them showing `--`, by design: a gate
that has not been run has not been passed.

---

## 4. Record

Commit after the run:

- `docs/preregistration.yaml` with the data half filled from
  `data/clean/data_manifest.json` and `manifest_status: VERIFIED`
- `results/run1/run_report.json` — deliberately un-gitignored; it is the audit
  trail (environment, pre-registration state, which gate stopped the run)
- `n_trials_executed` incremented, and the trial appended to `trial_log`

The trial counter is append-only and includes runs that were abandoned. A test
run and not reported is the definition of p-hacking.

---

## 5. The traps, in the order they are likely to bite

1. **Breadth is not length.** Pooling 400 tickers raises `n` per block; it
   creates no additional blocks, because blocks are calendar periods. The ≥20
   block requirement is the safeguard against a single favourable period and
   only more *history per instrument* satisfies it. This is the most likely
   mistake to make after a Verdict B.

2. **`K_eff`, not `K`.** Ten correlated US large caps carry the weight of about
   2.7 independent series. Step 2 measures and prints this; do not argue with it.

3. **A big result is a bug report.** Pre-registered expectation is IC 0.01–0.03.
   Above **IC 0.05 or 5pp lift**, treat it as a defect until every §5.6 gate has
   been re-run. On a feature set this heavily mined, a large effect is evidence
   about the pipeline, not the market.

4. **The 50% baseline is wrong** and biased in the flattering direction. The
   pipeline uses `pi_0(q) = f_q·P(r>0) + (1−f_q)·P(r<0)`. On drifting data with
   *zero* information the naive baseline reports +2.84pp — squarely inside the
   1–3pp band that looks most credible. Never quote a lift computed against 0.5.

5. **The zero-crossing decile is uninterpretable.** For tiny |DQ| the sign is
   set by rounding noise. It is flagged and excluded from the shape evidence,
   and it will show a large nonsense lift. Ignore it.

6. **The holdout is looked at once.** `split_holdout` removes the last 252
   sessions everywhere upstream. A second look converts it into training data.

7. **Re-specification is a new study.** Changing the score, threshold, target or
   instruments after seeing a result requires a fresh pre-registration and
   untouched data. The sealed holdout exists to make that expensive.

---

## 6. If Step 5 returns Verdict C

That is the expected outcome and a complete deliverable. Write it up using
`negative_conclusion_text` from the pre-registration, record which gates fired,
and stop. Stage 2 stays locked.

There is deliberately no "promising, worth watching" category. That is where
dead hypotheses go to consume attention.
