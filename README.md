# Systematic Risk Macro Dashboard

A personal, daily-use monitor for global systematic risk, built around the
question *"is the environment getting fragile enough that I should reduce
equity exposure?"*

Focus areas: **yen carry trade**, **interest rate differentials**,
**leverage**, **credit**, **oil**, and the **AI capex concentration** angle.

Free data only (Yahoo Finance + FRED + FINRA). No API keys. No paid feeds.

---

## Contents

1. [Quick start](#1-quick-start)
2. [Using it from your phone](#2-using-it-from-your-phone)
3. [What you must keep updated](#3-what-you-must-keep-updated)
4. [The risk scoring logic](#4-the-risk-scoring-logic)
5. [Files](#5-files)
6. [Customising it](#6-customising-it)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Quick start

You need **Python 3.9 or newer**. Check with `python3 --version`.

```bash
# 1. Go to the dashboard folder
cd risk-dashboard

# 2. Create an isolated environment (recommended — keeps these packages
#    from clashing with anything else on your machine)
python3 -m venv .venv

# 3. Activate it
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows PowerShell

# 4. Install the dependencies
pip install -r requirements.txt

# 5. Run it
streamlit run app.py
```

Your browser opens at `http://localhost:8501`. First load takes 20–40 seconds
while it pulls three years of history; after that it is cached for 30 minutes
and loads instantly.

To stop it: `Ctrl+C` in the terminal. To run it again later, re-activate the
environment (step 3) and run step 5.

**One-line restart script** — save this as `run.sh` (macOS/Linux) and
`chmod +x run.sh`:

```bash
#!/bin/bash
cd "$(dirname "$0")" && source .venv/bin/activate && streamlit run app.py
```

---

## 2. Using it from your phone

The dashboard is built to be readable on a phone — columns stack vertically
below 640px, the tab strip scrolls, and charts resize. But `streamlit run` on
your laptop is only reachable from your laptop. Pick one of these:

### Option A — Streamlit Community Cloud (free, best for daily phone use)

Always on, real URL, works from anywhere, no computer left running.

1. Push this `risk-dashboard/` folder to a GitHub repository.
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. **New app** → pick the repo and branch → set **Main file path** to
   `risk-dashboard/app.py` → **Deploy**.
4. You get a URL like `https://your-app.streamlit.app`.

**Make it feel like a real app:** open that URL on your phone →
**Share** → **Add to Home Screen**. It launches full-screen with its own icon.

Two things to know about hosted deployment:
- **Make it private.** In the app's settings, restrict viewer access to your
  own email — otherwise the URL is public. Your watchlist notes live in this
  app.
- **The filesystem resets on restart.** Margin debt edits and watchlist notes
  made in the browser will not survive a redeploy. Use the **Download CSV**
  button and commit the file to your repo to make changes permanent.

### Option B — Tailscale (free, private, stays on your own machine)

Best if you would rather nothing lives on someone else's server.

1. Install [Tailscale](https://tailscale.com/) on both your computer and phone,
   signed into the same account.
2. On your computer: `streamlit run app.py --server.address 0.0.0.0`
3. On your phone, visit `http://<your-computer-tailscale-name>:8501`

Works from anywhere in the world, fully private, but your computer has to be
awake and running the app.

### Option C — Same Wi-Fi only

```bash
streamlit run app.py --server.address 0.0.0.0
```

Then on your phone visit `http://<your-computer-LAN-IP>:8501` (find the IP with
`ipconfig getifaddr en0` on macOS, `hostname -I` on Linux, `ipconfig` on
Windows). Simplest option, but only on your home network.

---

## 3. What you must keep updated

The dashboard is honest about the difference between what it can fetch and
what it cannot. Three things need you:

| What | How often | Where | Why it is manual |
|---|---|---|---|
| **Japan 2y & 10y yields** | Weekly, or after any BOJ move | Sidebar | No free daily JGB feed exists anywhere |
| **BOJ policy rate** | When the BOJ moves | Sidebar | Same |
| **FINRA margin debt** | Monthly | Leverage tab | FINRA publishes a table, not an API |

Everything else — FX, US yields, credit spreads, VIX, commodities, the Fed
funds rate — updates itself.

**The Japanese yields matter most.** They drive the carry-trade differentials,
which drive the highest-weighted component in the model. Entering them takes
ten seconds from any bond quote page. To change the *defaults* so you do not
retype them each session, edit `MANUAL_JP_YIELDS` in `config.py`.

**Margin debt ships as clearly-labelled placeholder data.** Those numbers are
illustrative shapes, not real FINRA figures — so the leverage component is
**excluded from the risk score** and the model re-weights the other seven
components until you enter real data. Get the real numbers from
[finra.org/investors/insights/investing/margin-statistics](https://www.finra.org/investors/insights/investing/margin-statistics),
paste them into the editable table on the Leverage tab, untick
*Placeholder?*, and hit **Save to CSV**.

---

## 4. The risk scoring logic

Deliberately simple and fully auditable. Five steps:

### Step 1 — Every signal becomes a 0-to-1 stress score

Each raw number is compared against two thresholds in `config.THRESHOLDS`:
a **calm** value scoring 0.0 and a **stressed** value scoring 1.0, straight
line in between, clipped at both ends.

```
USDJPY 1-month change:  -2%  → 0.0 (calm)     -7%  → 1.0 (stressed)
VIX level:              15   → 0.0            32   → 1.0
HY spread 1m change:    +0.10pp → 0.0         +0.90pp → 1.0
```

It works in both directions, so "lower is worse" signals (USDJPY) and "higher
is worse" signals (VIX) use the same function.

### Step 2 — Signals blend into eight components

Using `config.SUB_WEIGHTS`. Within a component, **rates of change are weighted
above levels** — a spread that widened 100bp this month tells you more than a
spread that has been wide all year.

### Step 3 — Components blend into a 0-100 composite

| Component | Weight | Rationale |
|---|---:|---|
| Yen carry / FX stress | 20 | The transmission channel with the fastest global reach |
| Equity volatility | 15 | Where stress becomes visible and forces deleveraging |
| Credit spreads | 15 | Credit reprices risk before equities do |
| Leverage (margin debt) | 15 | Does not cause drawdowns; decides how violent they get |
| Rate differentials | 10 | The carry trade's reason to exist |
| Treasury volatility | 10 | Rate vol leads cross-asset vol |
| Commodities / oil | 10 | Constrains the policy response to a growth scare |
| Yield curve | 5 | Slow-moving — deliberately small |

**Missing data is dropped, not scored as zero.** If a feed dies, that
component is excluded and the remaining weights are re-normalised. The header
always shows what percentage of model weight actually had data.

### Step 4 — Escalation rules can override the average

A weighted average is bad at *combinations*. A wide rate differential is not
stress. A falling USDJPY is not necessarily stress. Both together, moving
fast, is the single most reliable systematic-risk setup here — and averaging
would bury it under seven calm components.

Four rules in `config.ESCALATIONS` force a **minimum** composite score:

| Rule | Fires when | Floors score at |
|---|---|---:|
| `carry_unwind` | USDJPY down >2% in a week **while** the US-JP 2y differential is still >2.0pp wide | 70 |
| `vol_backwardation` | VIX above VIX3M — near-term stress priced above longer-term | 66 |
| `credit_crack` | High-yield spreads widened >100bp in a month | 66 |
| `leverage_at_peak_and_vol_rising` | Margin debt within 3% of its record **while** VIX > 22 | 60 |

The first one is the point of the whole dashboard. Yen strength that is *not*
explained by rate convergence means positions are being liquidated, not
repriced — which is what made August 2024 far larger than the rate move
justified.

### Step 5 — The bands

| Score | Regime | What to do |
|---|---|---|
| **0–33** | 🟢 Low | Normal conditions. Nothing to do. |
| **34–61** | 🟡 Elevated | Stop *adding* leverage and exposure. Tighten stops. A "don't make it worse" signal, not a sell signal. |
| **62–100** | 🔴 High | Several independent systems stressed at once, or an escalation firing. Consider actively reducing equity exposure. |

### What this model is not

- **Not optimised.** The thresholds are judgement calls, not fitted to
  historical returns. That means it is not perfectly calibrated — and also not
  overfitted to crises that will never repeat in the same shape.
- **Deliberately prone to false positives.** A risk monitor that never warns
  early is useless. Expect ambers that resolve into nothing.
- **Blind to what is not in the data** — an exchange failure, a sovereign
  default, a war starting on a Sunday.
- **Not a trading system.** It describes the environment. Position sizing is
  still your decision.

---

## 5. Files

```
risk-dashboard/
├── app.py              Streamlit UI — all tabs and layout
├── config.py           ★ EVERY tunable knob: tickers, thresholds, weights,
│                         CB calendar, palette. Edit this, not the others.
├── data_sources.py     Yahoo + FRED fetching, caching, graceful failure
├── metrics.py          Raw feeds → the derived numbers shown on screen
├── scoring.py          The risk model: ramps, components, escalations
├── ui.py               Cards, sparklines, charts, CSS (incl. mobile stacking)
├── margin_debt.py      FINRA CSV loading and leverage analysis
├── requirements.txt
├── README.md
├── .streamlit/
│   └── config.toml     Theme + server settings
└── data/
    ├── margin_debt.csv Your FINRA figures (ships as placeholder)
    └── watchlist.json  Your notes (created on first save)
```

The split exists so that **you only ever need to open `config.py`** to change
how the dashboard behaves.

---

## 6. Customising it

All in `config.py`:

| Want to… | Change |
|---|---|
| Make a signal more/less twitchy | `THRESHOLDS` — narrow the `(calm, stress)` gap for more sensitivity |
| Change what the score cares about | `WEIGHTS` (or the sidebar sliders, for one session) |
| Change the blend inside a component | `SUB_WEIGHTS` |
| Change when the traffic light turns amber/red | `REGIME_BANDS` |
| Change the escalation triggers | `ESCALATION_PARAMS` |
| Add or fix central bank dates | `FOMC_MEETINGS`, `BOJ_MEETINGS`, `OTHER_EVENTS` |
| Track a different currency cross | `YF_TICKERS` + the loop in `metrics.py` |
| Fix the market-cap approximation | `SP500_DIVISOR_BN` |
| Refresh data more/less often | `CACHE_TTL_SECONDS` |

**The most useful customisation:** if you find yourself ignoring amber
readings, raise `REGIME_BANDS['elevated_above']` until amber means something
again. An alert you have trained yourself to ignore is worse than no alert.

⚠️ **The central bank dates are approximate and hardcoded.** Verify them
against [federalreserve.gov](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm)
and [boj.or.jp](https://www.boj.or.jp/en/mopo/mpmsche_minu/index.htm). A BOJ
surprise is the most likely single trigger for a carry unwind, so being a week
off matters.

---

## 7. Troubleshooting

**"No market data could be loaded"**
Yahoo Finance and FRED both need outbound HTTPS. Check your connection, then
press **Refresh data**. On a corporate network, a proxy may be blocking them.

**Some cards show "—" or "no data"**
Normal and by design. Yahoo occasionally drops a symbol (`^VIX3M` and `^MOVE`
are the usual offenders). The model excludes that component and re-weights;
the header tells you the coverage percentage. It usually resolves itself
within a few hours.

**All the FX / VIX / commodity cards are blank at once**
That is Yahoo Finance rate-limiting you (HTTP 429). It is common on shared and
cloud IP addresses, so you will see it on Streamlit Community Cloud more often
than on your laptop. The app detects this case and says so in a banner; FRED
data (US yields, curve, credit spreads, Fed funds) is unaffected, and the risk
score re-weights over what is left. It normally clears within the hour — press
**Refresh data** to retry. Data fetching runs under a hard time budget, so a
rate-limited Yahoo slows the first load but never hangs the dashboard.

**Light or dark mode**
Both work. Change `base` in `.streamlit/config.toml`, or switch on the fly from
the ☰ menu → Settings → Appearance. Cards inherit the theme's own text colour
over a neutral tint and the chart palette is mode-invariant, so nothing needs
to detect which theme is active.

**`ModuleNotFoundError` on launch**
The virtual environment is not active. Re-run `source .venv/bin/activate`
(macOS/Linux) or `.venv\Scripts\activate` (Windows), then
`pip install -r requirements.txt`.

**Data looks stale**
Everything is cached for 30 minutes. Press **Refresh data** to force a reload.
Note that FRED series (US yields, credit spreads) are genuinely published with
about a one-business-day lag — that is the data, not the cache.

**Charts are cramped on my phone**
Rotate to landscape for the stacked carry panels. Everything else is designed
for portrait. If columns are not stacking, you are probably on a tablet above
the 640px breakpoint — adjust the `@media` query in `ui.py`.

**It says my margin debt is placeholder even though I edited the CSV**
Untick the **Placeholder?** checkbox on every row (or set `is_placeholder` to
`FALSE` in the CSV). A single `TRUE` row flags the whole dataset — that is
deliberate, so half-updated data never scores as if it were real.

---

*Personal monitoring tool. Data from free public sources, provided without
warranty and occasionally wrong. Not investment advice.*
