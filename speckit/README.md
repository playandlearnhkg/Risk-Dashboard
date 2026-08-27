# Spec Kit bootstrap kit

Ready-to-paste inputs for developing this repository with
[GitHub Spec Kit](https://github.com/github/spec-kit) (Spec-Driven Development).

**These files are inputs, not outputs.** Each one is text you paste into a Spec Kit
slash command. Spec Kit generates the real artifacts (`constitution.md`, `spec.md`,
`plan.md`, `tasks.md`) into `.specify/` and `specs/` itself. Nothing here duplicates
what Spec Kit produces.

Everything is derived from `PRODUCT_SPEC.md`. Where a file says "see §N", that is a
section of `PRODUCT_SPEC.md` — keep it open alongside.

---

## Files

| File | Paste into | Purpose |
|---|---|---|
| `01-constitution.md` | `/speckit.constitution` | Project guardrails. Every principle is already true in this repo — none invented |
| `02-specify-regime-page.md` | `/speckit.specify` | **Feature 001** — the Regime & Capital Flow page |
| `03-plan-regime-page.md` | `/speckit.plan` | Technical approach for Feature 001, incl. the Marimo/Streamlit decision |
| `04-tasks-and-quality.md` | `/speckit.tasks`, `/speckit.checklist`, `/speckit.analyze` | Task generation guidance and the acceptance checklist |
| `05-specify-layer2-scoring.md` | `/speckit.specify` | **Feature 002** — Layer 2 scoring engine. Do NOT start this yet; see below |

---

## Setup

### 1. Install Spec Kit

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@vX.Y.Z
```

> Replace `vX.Y.Z` with the current release tag from
> <https://github.com/github/spec-kit/releases>. **This kit does not pin a version** —
> the CLI moves quickly and a stale tag here would be worse than none.
> Verify with `specify self check` after installing.

### 2. Initialise in this repo

Spec Kit modifies the working tree, so start clean:

```bash
cd path/to/risk-dashboard
git checkout -b speckit/init
git status          # must be clean before proceeding

specify init --here --force --integration claude
```

Use `--integration copilot` for GitHub Copilot instead. Run `specify integration list`
to see all supported agents.

`--here` initialises in the current directory rather than creating a new project.
`--force` is required because the directory is not empty.

### 3. Confirm what it created

```bash
git status --short          # review before committing
```

Expect `.specify/` and an agent command directory (`.claude/commands/` for Claude Code).
**Commit this separately from any feature work** — Spec Kit's own guidance is to keep
tooling updates distinct from artifact evolution.

---

## Workflow

Run these as slash commands inside your agent (Claude Code or Copilot in VS Code):

```
/speckit.constitution   ← paste 01-constitution.md          (once, project-wide)
/speckit.specify        ← paste 02-specify-regime-page.md   (creates specs/001-.../)
/speckit.clarify        ← run it; answer its questions
/speckit.plan           ← paste 03-plan-regime-page.md
/speckit.tasks          ← paste the task guidance in 04
/speckit.analyze        ← catches spec/plan/task inconsistencies BEFORE any code
/speckit.checklist      ← paste the checklist section in 04
/speckit.implement      ← writes code
/speckit.converge       ← appends whatever remains; repeat implement+converge until done
```

Do not skip `/speckit.clarify` and `/speckit.analyze`. They are the cheap steps that
catch a misunderstanding before it becomes a thousand lines of code.

---

## Brownfield: which persistence model

Spec Kit offers three. **Use "Living Spec"** for this repository: `spec.md` is the
contract, and when behaviour changes you update the spec first and regenerate
`plan.md` / `tasks.md` downstream.

Reason: `PRODUCT_SPEC.md` already works that way — it is the authority on intent and is
explicitly marked stale-if-it-disagrees-with-code (§15). A second document with different
update semantics would compete with it.

**How the two documents relate — decide this once and stick to it:**

| Document | Owns |
|---|---|
| `PRODUCT_SPEC.md` | The system as a whole: what exists, the formulas, the contracts, the constraints. Product-level and durable |
| `specs/NNN-*/spec.md` | One increment: what changes, and how it is verified. Feature-level and disposable once shipped |

After each feature ships, update the affected `PRODUCT_SPEC.md` sections to describe the
new reality. **AC-46 in §21 already requires this** — treat it as part of Done, not
paperwork afterwards.

---

## Scope discipline — read this before starting

Spec Kit's own guidance for existing projects:

> "Start with a feature, bug fix, or modernization slice that can be reviewed
> independently. Do not make 'document the entire existing system' your first feature
> unless that inventory is itself the intended deliverable."

You have already done the inventory — that is what `PRODUCT_SPEC.md` is. So the first
feature is **not** "specify Meridian". It is the Regime & Capital Flow page: bounded,
independently reviewable, and it already has 46 acceptance criteria written (§21).

**Order matters, and the recommendation is Feature 001 first:**

| | Feature 001 — Regime page | Feature 002 — Layer 2 scoring |
|---|---|---|
| Size | One page, ~1 week | 8 factors, ~40 sub-factors, weeks |
| Inputs | All exist (§17 contracts, real fixture on disk) | Needs a complete Layer 1 dataset |
| Blocked by | Nothing | The full 503-ticker run, still outstanding |
| Value now | Makes Layer 0 visible — it currently prints to a terminal nobody reads | The largest single piece of remaining value |
| Risk of going first | Low. New files only, zero regression surface | High. Big surface, no working reference, and it depends on data quality nobody has validated |

Feature 001 also teaches you the Spec Kit loop on something small enough to throw away
if the workflow does not suit you.

---

## Constitution: why it is short

Spec Kit's guidance is explicit:

> "Do not invent standards merely to fill the constitution template."

`01-constitution.md` therefore contains **only** principles already evidenced in the
repository — every one traces to a code comment, a config file, or a design decision
recorded in `PRODUCT_SPEC.md` §11. If a principle looks missing, it is missing on
purpose: it was not already true, so asserting it would make the constitution fiction.

Add to it when you make a *new* decision, not to make it look complete.

---

## Known limits of this kit

- **The Spec Kit release tag is not pinned here.** Check the releases page. If the CLI
  surface has changed again since this was written, the *prompts* still apply — only the
  command names would need adjusting.
- **The commands were verified against the Spec Kit README as of 2026-08-26.** They are
  namespaced (`/speckit.specify`, not `/specify`) and init takes `--integration`
  (not `--ai`). Both changed from earlier versions.
- **Feature 002's prompt is a starting point, not a finished spec.** Layer 2's detail
  lives in `daily_dashboard/SPEC.md` §"LAYER 2"; the prompt points there rather than
  restating ~40 sub-factors that would immediately drift.
