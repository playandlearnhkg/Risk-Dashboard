# Paste into `/speckit.specify` — Feature 001

> Describes **what** and **why**, not how. Technology choices belong in
> `/speckit.plan` (file 03). Full detail is in `PRODUCT_SPEC.md` §18 (UI spec),
> §17 (data contracts) and §21 (acceptance criteria) — keep it open.
>
> After running this, run `/speckit.clarify` and answer its questions before planning.

---

Build a **Regime & Capital Flow** page that makes Meridian's Layer 0 output visible.

## Problem

Meridian's regime engine runs daily and produces a complete, useful assessment — regime
score, capital availability, eleven scored indicators, sector rotation rankings, asset
class preferences, and a weekly process checklist. **All of it prints to a terminal and
is then discarded.**

Historical regime data has been accumulating in a `regime_history` table since the engine
was built. **Nothing has ever read it.** A regime score of 55 means something different
climbing from 40 than falling from 70, and today that trajectory is invisible.

The result: the owner runs the engine, reads a wall of console text, and has no way to
see whether conditions are improving or deteriorating.

## Users and usage

Single user — the repository owner — checking conditions each morning as part of a
5-minute routine (`PRODUCT_SPEC.md` §20.1). Read-only. Consulted on a phone as often as
a laptop.

## Outcomes

1. Answer four questions on one screen, in this order: **What regime are we in? Is
   capital available? Which way is it moving? Do I trust today's reading?**
2. Make regime history visible as a trend, not just a level.
3. Make data quality impossible to miss — a reading built on partial data must never
   look like a confident call.

## Scope

**In scope**

- Read and display `daily_dashboard/output/regime_latest.json` — the full contract is in
  §17.1.
- Display **all eleven indicators**, including unavailable ones, with score, value,
  as-of date, effective source, weight, and error text where present.
- Show the core model explicitly: Money and Behaviour scores, the combination method,
  and **the arithmetic itself** (e.g. `√(85.9 × 94.8) = 90.2`). The model's central
  claim is multiplicative; showing the multiplication is the point.
- Capital Availability status, and the fact it derives from the **money half alone**.
- Historical trend charts from the `regime_history` table (§17.3), read-only.
- Sector rotation ranking (11 rows) and asset class preferences (10 rows).
- Weekly process checklist status.
- Provider and freshness status from `system_status.json` (§17.2), when present.
- All ten empty / partial / degraded states in §18.6.

**Out of scope**

- Any change to the existing Streamlit dashboard's eight tabs.
- Any change to `run_regime.py`, `run_data.py`, or Meridian's engine code.
- Layer 2 scoring, portfolio construction, or trade candidates — those layers do not
  exist.
- Writing to the database. This page is read-only.
- Any network call. The page reads local files only.

## Behavioural requirements

### Data access

- Read `regime_latest.json` and `system_status.json` as **files**. Do **not** import any
  Meridian module — Principle 4. Verifiable by grepping the page source for
  `import regime` / `from regime`.
- Open the SQLite database **read-only** (`file:...?mode=ro`). WAL mode means readers do
  not block an ingest, but a read-only handle also makes it impossible for a UI bug to
  corrupt ingest data.
- The page must render correctly when Meridian has **never run**: no output files, no
  database. That is an empty state, not an error.

### Trust and data quality — the requirement this feature exists to get right

- **Every entry in the `warnings[]` array must be rendered verbatim.** Never truncated,
  never hidden behind a click.
- When coverage is below 60%, the score must carry a **visible provisional treatment**
  and must not be presented as a clean regime call.
- Unavailable indicators are **listed**, not hidden — showing their error text and with
  their weight struck through to signal exclusion.
- Stale data must show its age. Compare against the series' **expected frequency**, not
  wall-clock days: a quarterly series 60 days old is current; a daily series 60 days old
  is broken. See §23.

  *Worked example, and the reason this matters.* The real output currently on disk reads
  `90.2 — Strong Risk-On`, computed from **two** behaviour indicators out of six, both of
  which happened to score near 100. The engine behaved correctly: it dropped the dead
  feeds, re-normalised, and warned. A page that renders `90.2 Strong Risk-On` without the
  caveat converts a correctly-hedged output into a false signal. **That is the failure
  mode this feature must prevent.**

### The two scores

If the Meridian **Regime Score** and the dashboard **Stress Score** ever appear together,
all six rules in §18.7 are mandatory — inline direction labels, no shared axis, no
arithmetic across them.

**Preferred: keep them on separate pages** and cross-link with the direction stated
(*"Systematic stress: 41/100 — higher is worse →"*). This eliminates the risk rather
than managing it, and is the recommended approach.

### Historical trends

- Regime Score, Money Score and Behaviour Score over time on a **fixed 0–100 axis**,
  never auto-scaled. An auto-scaled axis turns a 4-point wobble into an apparent regime
  change.
- The five regime bands shaded as background at 30 / 43 / 57 / 70.
- Window selector: 30 / 90 / 180 days / All. Default 90.
- Capital Availability history as **blocks**, not a line — it is a three-state label and
  the block boundaries are the information.
- Direction stated as a **word** (`improving` / `deteriorating` / `flat`) over the last 5
  and 20 runs, alongside the level.
- **Gaps must render as gaps.** `regime_history` has one row per *engine run*, not per
  calendar day, so weekends and skipped days are genuinely absent. Never forward-fill
  silently.
- Fewer than 2 rows: show *"Trend needs at least two runs. Run `run_regime.py` daily to
  build history."* — not a blank panel or a single floating point.

### Mobile

Fully usable at 390px:

- Single column; sections stack.
- Status bar sticky and compressed.
- **The warning indicator must be visible without scrolling.** A provisional score that
  looks confident on a phone is this page's worst failure mode.
- Tables scroll inside their own container; the page body never scrolls horizontally.
- Touch targets ≥ 44×44px. No hover-only information.

### Accessibility

Per Principle 6: every status carries a word beside its colour; the palette works on
both light and dark backgrounds; charts carry legends.

## Constraints

- **Additive only.** No file outside this feature's own files may be modified
  (except `PRODUCT_SPEC.md`, per the Done criterion below). The existing dashboard must
  run unchanged.
- Page load under 2 seconds with 180 days of history.
- No network access.
- Derive display labels locally. The JSON's auto-generated `label` field produces
  `"Mmf Aum"` and `"Audjpy"` — the page needs its own label map.
- The file payload **omits** `stance` for sectors and `name`/`stance` for asset classes,
  though `--json` stdout includes them (§17.1). Derive stance from `matrix_score` via the
  −2…+2 → label map rather than depending on a field that is only sometimes present.

## Acceptance

`PRODUCT_SPEC.md` §21 contains **46 numbered acceptance criteria** (AC-1 … AC-46)
covering data loading, correctness against the engine, all ten states, trends, mobile,
dual-score safety, and non-regression. Treat that list as the definition of done and
reference the AC numbers in tasks.

**A fixture already exists.** The real `daily_dashboard/output/regime_latest.json` from
the 2026-08-21 run exercises four of the ten states simultaneously — partial coverage
(behaviour 47%), a provider fallback (`transcripts`), a matrix-only sector scan (all
`momentum_pct` null), and four individually unavailable indicators. Use it as the primary
test fixture; fabricate one file per remaining state.

## Success looks like

The owner opens the page each morning, sees the regime and its trajectory in under ten
seconds, and can tell at a glance whether today's reading is trustworthy — without
opening a terminal, and without ever mistaking a partial reading for a confident one.
