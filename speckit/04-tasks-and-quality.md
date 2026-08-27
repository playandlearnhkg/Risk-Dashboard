# Task generation and quality gates — Feature 001

Three separate commands. Use the matching section below for each.

---

## A. Paste into `/speckit.tasks`

Generate tasks from the spec and plan, following the seven-step sequencing in the plan.

**Rules for the breakdown:**

1. **Reference acceptance criteria by number.** Every task states which of AC-1 … AC-46
   (`PRODUCT_SPEC.md` §21) it satisfies. An AC covered by no task is a gap; a task
   covering no AC is scope creep.
2. **Pure logic before rendering.** Loader, label mapping, staleness and direction
   calculations are all tasks that complete and pass tests before any UI task starts.
3. **Each of the ten states in §18.6 is its own task**, with its fixture named. They are
   not a single "handle edge cases" task — this is where the feature's value is.
4. **The mobile pass is tasks, not a checklist item.** Minimum: viewport verification at
   320/375/390/768, the sticky warning indicator (AC-32), touch targets, and horizontal
   scroll containment.
5. **Additive-only is a standing constraint.** No task may modify a file outside the
   feature's own directory, except the final `PRODUCT_SPEC.md` update task.
6. **Order by dependency, and mark what can run in parallel.** Loader tests gate
   everything; the sector, asset-class and weekly-process panels are independent of each
   other.

**Explicitly include these, which are easy to miss:**

- Copy the real `daily_dashboard/output/regime_latest.json` (2026-08-21) into
  `tests/fixtures/` as the primary fixture, before writing loader tests.
- Build the display-label map — the JSON's own `label` field yields `"Mmf Aum"`,
  `"Audjpy"`, `"Vix Level"`.
- Derive sector/asset-class `stance` locally; the file payload omits it (§17.1).
- Resolve paths from the repository root, not the working directory (§22.2).
- Verify the `√(money × behaviour)` arithmetic renders and evaluates correctly (AC-9).
- A final task updating `PRODUCT_SPEC.md` §18 to describe what was built (AC-46).

---

## B. Paste into `/speckit.checklist`

Generate a review checklist for this feature. Derive it from the 46 acceptance criteria
in `PRODUCT_SPEC.md` §21, grouped as:

| Group | ACs | Focus |
|---|---|---|
| Data loading | 1–5 | No Meridian imports, read-only DB, no network, degrades without files |
| Correctness | 6–11 | Every displayed number matches `regime_latest.json` exactly |
| States | 12–22 | All ten states in §18.6, each driven by a named fixture |
| Trends | 23–29 | Fixed axis, bands, gaps as gaps, direction words, <2-row case |
| Mobile | 30–35 | Four viewports, sticky warning, touch targets, no hover-only |
| Dual-score safety | 36–40 | Never unqualified, direction inline, no arithmetic across |
| Non-regression | 41–46 | Additive only, dashboard unchanged, tests, spec updated |

**Weight the checklist toward the states group.** A page that renders the happy path
beautifully and the degraded paths carelessly is worse than no page — it converts a
correctly-hedged engine output into a false signal. That is the specific failure this
feature exists to prevent.

**Two checks that must be manual, not automated:**

- Load the real 2026-08-21 fixture on a **390px viewport** and confirm the coverage
  warning is visible without scrolling. A desktop window will not reveal this.
- Read the rendered page as a tired person at 7am would. If `90.2 Strong Risk-On` reads
  as confident, the feature has failed regardless of what the tests say.

---

## C. Run `/speckit.analyze` before any code

No paste needed — it cross-checks spec, plan and tasks for inconsistency.

**Resolve everything it raises before `/speckit.implement`.** Pay particular attention
to:

- ACs with no covering task, and tasks covering no AC
- Any task that would modify a file outside the feature directory (violates the
  additive-only constraint and AC-41)
- Any implied change to `run_regime.py`, `run_data.py`, or the existing dashboard —
  all are explicitly out of scope
- Contradictions between the spec's "no network" constraint and any task implying a fetch

---

## D. After implementing

```
/speckit.implement     → writes code
/speckit.converge      → assesses against spec/plan/tasks, appends what remains
```

Repeat `implement` → `converge` until converge reports nothing remaining. Then:

1. Run the checklist from section B, including the two manual checks.
2. Confirm `git diff --stat` shows only the feature's own files plus `PRODUCT_SPEC.md`.
3. Confirm the existing dashboard still runs: `streamlit run app.py`, all eight tabs.
4. Confirm the page renders on a machine where Meridian has never run — rename
   `daily_dashboard/output/` and reload.

**Then update `PRODUCT_SPEC.md`:**

- §3.8 — historical trends: ⚠️ → ✅
- §4 — Layer 7 status
- §17.5 — `regime_history` "Read by dashboard?" ❌ → ✅
- §18 — mark built; record deviations from the spec as built
- §10.1 — remove the "data collected but never displayed" gap
- §24.3 item 16 — the UI spec is no longer unreviewed

That last one matters: §24 is the document's honesty record. Keeping it current is what
makes the rest of the document trustworthy.
