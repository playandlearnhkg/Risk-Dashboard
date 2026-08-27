# Paste into `/speckit.constitution`

> Every principle below is **already true** in this repository and traceable to code,
> config, or a decision recorded in `PRODUCT_SPEC.md` §11. Nothing here is aspirational.
> Spec Kit's guidance is not to invent standards to fill the template — so this is
> deliberately short.

---

Establish the constitution for this repository from the principles below. These are
existing, evidenced practices, not new proposals. Preserve the rationale — each principle
exists because violating it has already caused, or would cause, a specific failure.

## Context

One repository, two applications:

- **risk-dashboard** (repo root) — a working Streamlit app scoring global systematic
  risk. In daily use.
- **Meridian** (`daily_dashboard/`) — a 7-layer long/short equity system. Layers 0
  (regime engine) and 1 (data infrastructure) are built and running, ~5,200 lines.
  Layers 2–7 are specification only; six package directories contain nothing but an
  empty `__init__.py`.

Single maintainer. Personal capital, not a product. No authentication, no multi-tenancy.
Authoritative reference: `PRODUCT_SPEC.md`.

## Principle 1 — Missing data is dropped, never scored as neutral

If an input is unavailable, its component is **excluded** and the remaining weights are
**re-normalised**. A missing feed must never be scored as 0, as 50, or as "average".
"No data" and "perfectly average" are different statements and the system must never
conflate them.

Every score that can be computed from partial inputs must report **coverage** — the
share of indicator weight that actually had data — alongside the score itself.

*Evidence:* `regime/indicators.weighted_score()`, `scoring.assess()`,
`scoring._blend()`. Placeholder margin data is explicitly excluded rather than treated
as calm (`scoring._leverage`).

## Principle 2 — The two composite scores are never conflated

The system produces two 0–100 scores that run in **opposite directions**:

- **Stress Score** (risk-dashboard): 100 = maximum danger
- **Regime Score** (Meridian Layer 0): 100 = maximum risk-on

Never refer to "the score" unqualified in code, comments, UI text, or documentation.
Never compute a difference, ratio, average, or combined gauge across the two — they
share a range by coincidence, not by construction.

*Evidence:* `PRODUCT_SPEC.md` §16.1, §18.7. This is the highest-severity open risk in
the system.

## Principle 3 — Configuration, not code

Thresholds, weights, tickers, and series IDs live in `daily_dashboard/config.yaml`
(Meridian) and `config.py` (dashboard). Code reads them; code does not hardcode them.
A new tunable belongs in config even when hardcoding would be shorter.

Corollary: **no fitted or backtested parameters.** Every threshold is a judgement call,
chosen to be readable and editable. Introducing optimisation is a separate, deliberate
decision with its own methodology — not something a feature slips in.

## Principle 4 — The two applications are coupled by files, never by imports

The dashboard reads Meridian's output as **files on disk**
(`daily_dashboard/output/system_status.json`). It does not import Meridian modules.
Meridian does not import the dashboard.

This is what lets the dashboard run with **zero setup** on a machine where Meridian has
never been installed or run. Any new integration point uses the same seam: read a file,
degrade gracefully when it is absent, never make one application a prerequisite for the
other.

*Evidence:* `data_sources_panel.py` module docstring; `core/status.py`;
`PRODUCT_SPEC.md` §5.3.

## Principle 5 — Data correctness is verified against real data

Six data-corruption bugs have been found in this repository. **Every one failed silently
and reported success** — 13-F rows collapsing under a primary-key collision, option
positions merged into common stock, convertible debt counted as shares, Form 4 fetching
the HTML rendering instead of the XML, `fcf_yield` NULL across the entire universe.

Therefore: a green run proves nothing on its own. A change to data handling is not done
until verified against real data with a stated check — a row count, a known-correct
value, a before/after comparison. Record the verification in the commit message.

## Principle 6 — Accessibility: colour is never the only channel

Every status carries a **word** beside its colour. Charts carry a legend and a table
view. No information is hover-only; everything must be reachable by tap and by keyboard.

The palette is **mode-invariant**: Streamlit gives Python no reliable way to know which
theme the browser painted, so surfaces are neutral greys at low alpha and text inherits
colour. Do not introduce a colour that only works on one background.

*Evidence:* `config.PALETTE` comments; `ui.py`.

## Principle 7 — Comments explain why, not what

The codebase is dense with reasoning about *why* a formula has its shape — the `× 1000`
unit rescale in `net_liquidity`, the deliberate inversion in `yoy_ramp`, the
mode-invariant palette, the XSL prefix strip in Form 4 fetching. Several of these encode
bugs that were expensive to find.

**Read the comment before changing the code near it.** New code matches this density and
this style: explain the non-obvious decision, not the obvious mechanics.

## Principle 8 — Bulk Yahoo Finance access is local-only

Yahoo returns HTTP 429 persistently from shared and cloud IPs. Full-universe price
refresh (~530 tickers) must run on a local machine. Rate-limit mitigation exists
(batching, jitter, cooldowns, abort thresholds) but does not remove the constraint.

Features must therefore **degrade gracefully under rate limiting** rather than assume
data is present, and must **say so visibly** when data is partial.

*Evidence:* `config.yaml` `rate_limits`; `data/providers.py`; `PRODUCT_SPEC.md` §8.3.

## Principle 9 — Existing behaviour is preserved

The Streamlit dashboard is in daily use. A feature adds; it does not silently change
what is already working. Any change to an existing scoring path, threshold, or displayed
value is called out explicitly in the spec and justified — never bundled into unrelated
work.

## Principle 10 — Documentation tracks reality

`PRODUCT_SPEC.md` is the system-level authority. When a feature changes what the system
does, updating the affected sections is **part of Done**, not follow-up work.

Where documentation and code disagree, **the code is correct and the document is stale**
— fix the document.

---

## Governance

- Principles 1, 2, 4 and 5 are **non-negotiable**. A spec that requires violating one is
  wrong and must be revised, not waived.
- Principles 3, 6, 7, 8, 9, 10 may be deviated from only with the deviation stated
  explicitly in the feature's `spec.md` and a reason recorded.
- Amend this constitution when a **new** decision is made — not to make it look complete.
