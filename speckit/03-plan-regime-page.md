# Paste into `/speckit.plan` — Feature 001

> Run `/speckit.clarify` first and answer its questions. This is the **how**.
>
> ⚠️ **Section 1 contains a decision only the owner can make.** Resolve it before
> pasting — the rest of the plan branches on it.

---

## 1. Framework decision — resolve this first

The stated direction (`PRODUCT_SPEC.md` §9) is to move from **Streamlit → Marimo** and
**pandas → Polars**. No migration code exists; the direction is documented only.

This feature is a **new page with no regression surface**, which makes it the natural
place to evaluate Marimo — §9's recommended sequencing puts exactly this step third,
before touching any existing tab.

| | Option A — Marimo | Option B — Streamlit |
|---|---|---|
| Evaluates the target stack | ✅ On real work, zero risk to the working app | ❌ Defers the question again |
| Reuses `ui.py` chart helpers | ❌ Needs porting or rewriting | ✅ Directly |
| Reuses the mode-invariant palette | ⚠️ Concepts carry, code does not | ✅ Directly |
| Team familiarity | ❌ New | ✅ ~1,300 lines of app.py already written |
| Risk if it goes badly | Throw away one page | None |

**Recommendation: Option A (Marimo)**, because the cost of being wrong is one discarded
page and the value of finding out is a decision currently blocking a much larger
migration. Nothing in the feature spec depends on the framework — the same spec builds
either way.

**If you choose Option B**, delete the Marimo-specific items in §3 and §4 below; every
other section stands unchanged.

> **Polars is explicitly out of scope for this feature**, whichever framework is chosen.
> Mixing a framework migration and a dataframe migration in one increment means a failure
> cannot be attributed to either. §9 sequences Polars separately, starting bottom-up in
> `daily_dashboard/data/` — not here.

## 2. Architecture

Standalone page. **Additive only** — no file outside this feature's own files is
modified.

```
regime_page/                    ← new, self-contained
  ├── loader.py                 read JSON + SQLite, return typed structures
  ├── labels.py                 display names, stance map, age/staleness logic
  ├── charts.py                 trend + capital-history figures
  └── page.py                   layout and rendering
tests/
  └── test_regime_page.py       pure-logic tests
```

Layering rule: `page.py` renders; it does not parse or compute. Anything with a
right answer independent of the UI lives in `loader.py` / `labels.py` and is unit-tested
without the framework loaded. This is what makes AC-45 achievable and what makes a
future framework swap cheap.

## 3. Data access

**Inputs, all local, no network:**

| Source | Path | Required |
|---|---|---|
| `regime_latest.json` | `daily_dashboard/output/` | Yes — empty state without it |
| `regime_history` | `cache/meridian.db`, **read-only** | No — trends degrade |
| `system_status.json` | `daily_dashboard/output/` | No — provider strip degrades |

Rules:

- Resolve paths relative to the repository root, not the working directory. The owner's
  checkout has a doubled `daily_dashboard` path segment (§22.2) — a relative path that
  assumes the wrong cwd will resolve to something plausible and wrong.
- SQLite read-only: `sqlite3.connect("file:...?mode=ro", uri=True)`.
- **Every field is optional.** `system_status.json` is written by *merge* from two entry
  points, `money_score`/`behavior_score` can be null, and four of eleven indicators were
  null in the most recent real run. Parse defensively; never assume a key exists.
- Load once per render, not per widget.

**Contract reference:** §17.1 (regime_latest), §17.2 (system_status), §17.3
(regime_history). Field lists and real examples are there — do not re-derive them.

## 4. Rendering

- **Charts: Plotly.** Already a dependency, framework-agnostic, and the only charting
  code in the repo (`ui.py`) uses it. Keeps the framework decision reversible.
- **Palette: mode-invariant** — neutral greys at low alpha, text inherits colour. Copy
  the *approach* from `config.PALETTE`; do not import from the dashboard (Principle 4
  applies to code as well as data).
- **Chart titles rendered as HTML above the figure**, not inside Plotly. Plotly titles
  collide with legends and render `undefined` when `None` — a bug already fixed once in
  `ui.py`.
- Fixed 0–100 y-axis on the trend chart. Regime bands as background shapes at
  30 / 43 / 57 / 70.
- Gaps in `regime_history` must break the line. Plot against real dates; do not
  reindex to a continuous range.

## 5. Testing

`pytest`. There is **no existing test suite** — this feature introduces one, so keep it
narrow and useful rather than aiming for coverage.

**Unit tests (no framework, no I/O):**

- Stance mapping: −2…+2 → label, including out-of-range input
- Staleness classification against expected frequency, not wall-clock days
- Direction word (`improving`/`deteriorating`/`flat`) over 5 and 20 runs, including
  fewer rows than the window
- Label mapping (`mmf_aum` → `"MMF AUM"`, not `"Mmf Aum"`)
- Loader parsing: absent file, malformed JSON, null halves, null indicators, absent
  optional blocks

**Fixtures:**

- **Primary: the real `regime_latest.json` from 2026-08-21.** Copy it into
  `tests/fixtures/`. It exercises partial coverage, a provider fallback, a matrix-only
  sector scan, and four null indicators — four of the ten states, with no fabrication.
- One minimal fabricated file per remaining state (§18.6 states 1, 2, 4, 5, 6, 9).

**Manual verification:** the ten states, and mobile at 320 / 375 / 390 / 768px.

## 6. Sequencing

Each step is independently reviewable. Do not start the next until the previous is green.

1. **Loader + labels + tests.** No UI. Proves parsing against the real fixture, including
   every degraded case. The highest-risk logic, verified before any rendering exists.
2. **Static page.** Status bar, core model panel with the arithmetic shown, indicator
   tables. Numbers must match the engine exactly (AC-6 … AC-11).
3. **All ten states.** Drive each with a fixture. This is where most of the value is —
   do not treat it as polish.
4. **Trends.** Charts, window selector, gap handling, direction words.
5. **Sector / asset class / weekly process panels.**
6. **Provider and freshness strip.**
7. **Mobile pass.** Every viewport, every touch target.
8. **Update `PRODUCT_SPEC.md`** — mark §18 built, record deviations (AC-46).

## 7. Risks

| Risk | Mitigation |
|---|---|
| Marimo lacks an equivalent for tabs / expanders / sticky elements | Identify equivalents in step 2, before committing further. Falling back to Streamlit costs one page |
| A partial reading still looks confident | The single most important outcome. AC-14, AC-22, AC-32 exist for this. Verify on a phone viewport, not a desktop window |
| Contract drift — `--json` and the file emit different shapes (§17.1) | Read the **file** only. Derive `stance` locally rather than depending on a sometimes-present field |
| Path resolution on the owner's nested checkout (§22.2) | Resolve from repo root; assert the file exists and show the resolved path in the empty state |
| Silent forward-fill hides missing runs | AC-26. Test explicitly with a deleted mid-series row |
| Scope creep into Layer 2 | The spec's out-of-scope list is binding. Layer 2 is Feature 002 |

## 8. Definition of done

AC-1 … AC-46 in `PRODUCT_SPEC.md` §21, all passing, verified against the real
2026-08-21 fixture plus one fabricated file per remaining state — **plus** §18 of
`PRODUCT_SPEC.md` updated to describe what was actually built.
