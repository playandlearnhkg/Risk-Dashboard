# Edge Memory: Post-Earnings High-Volume Continuation

**File:** `edge_Vol_Earning_Memory.md` (repo root)
**Last updated:** 2026-08-16
**Purpose:** Single source of truth so any new session starts with full
context. Read this first.

**Rule for this file:** every number below is traceable to a named
report in `lambda_strategy_validation/`. If a figure has no source, it
does not belong here. Do not add remembered numbers.

---

## 1. Core edge definition

**Post-Earnings T+1 High-Volume Continuation**

| Element | Specification |
|---|---|
| Universe | US stocks, post-earnings T+1, non-zero gap |
| Screen | price ≥ $10, mkt cap ≥ $3B, corrected within-year liquidity rank (`screen_v2`) |
| Signal | first 5-min volume > 1.5 × trailing 20-session same-slot mean, **and** Continuation candle |
| Continuation | 09:30–09:35 candle closes **in** the gap direction and is not a doji |
| Doji | body / range ≤ 0.10 (so non-doji is **> 0.10**) |
| Entry | open of the 09:35 bar, market |
| Exit | 10:35 (1 hour) |
| Direction | signed by the gap — long gap-up, short gap-down |
| Costs | 6.6 bps round trip; sensitivity at 10 / 15 / 25 / 35 |

**No cap on gap size, and no floor.** Gaps in the cohort run 0.00%–36.9%
(0–14.2 ATR). 42% of trades have gaps under 0.5 ATR and that bucket
carries 45% of all P&L — the *smallest* gaps are the largest
contributor. Capping at 1 ATR costs 2.5 bps of mean and cuts std 16%.

---

## 2. Validated results

### Capitalised backtest — $1M, 0.5% risk, max 5 concurrent, 6.6 bps
*(FULLVAL_REPORT.md — 4,270 screened trades, 515 tickers, 2015–2025)*

| | No stop | ATR −1.0 stop |
|---|---|---|
| Final equity | $6.62M | $5.18M |
| CAGR | 18.79% | 16.17% |
| Ann. vol | 6.66% | 6.42% |
| Sharpe (rf=0) | 2.82 | 2.52 |
| Max drawdown | −6.46% | **−7.06% (worse)** |
| Time in market | 7.4% of clock time | same |

**The Sharpe is flattered by idle days.** Volatility on days capital is
actually working is 22.4%, not 6.7%. Size off the deployed figure.

### vs SPY *(BUYHOLD_REPORT.md)*
Strategy $6.62M vs SPY $3.74M. Correlation **0.016**, beta 0.0075.
Beats SPY in only 5 of 11 years — but the strategy returned 7–32% *every
year*, so who wins is decided by what SPY did. It beat SPY by ~30 points
in both down years (2018, 2022) and lost in every year SPY returned
> ~18%. No negative rolling 12-month window in the sample, against SPY's
15.8%.

### Decay is real *(FULLVAL, VOLUME_INTEGRITY)*
Average trade 36 bps (2015–19) → 22 bps (2020–25). CAGR 23.3% vs 11.3%.
Trades losing > 1 ATR rose 10.0% → 12.0% while the edge thinned.
**Size off the recent half, not the full sample.**

### Costs decide it *(FULLVAL)*
6.6 bps → 18.8% CAGR · 15 → 12.7% · **25 → 5.8%**. Gross edge 35.7 bps,
so the edge dies near **36 bps round trip**, ~5.4× the assumption.

### Long vs short *(FULLVAL)*
Short 30.5 bps/trade vs long 20.4. **The better half is the one with
unmodelled borrow cost.**

---

## 3. Behavioural findings — three commonly misremembered

### 3.1 Losers at 5 minutes RECOVER — do not cut them early
*(PATH_REPORT.md. This is the opposite of the intuitive reading.)*

Conditioning is on the **09:40 (5-minute) status**, not 15 or 30 min.

| Status at 09:40 | % profitable at 10:35 | Subsequent move 09:41→10:35 |
|---|---|---|
| Losers | 41.6% (39.8% net) | **+30.1 bps — largest of any bucket** |
| Winners | 70.5% (68.9% net) | +5.8 bps |

The worst 5-minute losers (−100 bps down at 09:40) go on to make
+37.0 bps. They still finish the hour at −64 bps, so it is a partial
recovery, not a round trip. **Cutting at 09:40 realises −66.2 bps and
forgoes +30.1 bps.** Five minutes is too early to judge this setup.

### 3.2 The ATR −1.0 stop is mostly whipsaw
Of 391 trades it fires on, **57.3% would have ended better without it**.
Average damage −138 bps vs +108 bps saved. Net −3.7 bps/trade, and max
drawdown gets *worse*.

### 3.3 One hour is the sweet spot, but barely
*(LONGHOLD_REPORT.md)* 1 hour +30.1 bps; 2 hours +33.0 bps (the extra
hour adds +3.0 bps, CI [−0.5, +6.6], p=0.105 — not significant); beyond
2 hours adds nothing. **"Front-loaded" refers to entry-delay decay
(§3.4), not to the edge being concentrated in the first 15–30 minutes.**

### 3.4 Being late is expensive *(TIMING_REPORT.md)*
Signal known at 09:35; only the fill moves; exit stays 10:35.

| Fill | Net bps | Edge kept |
|---|---|---|
| 09:35 | 29.65 | 100% |
| 09:36 | 23.74 | **80%** |
| 09:40 | 14.90 | 50% |
| 09:50 | −1.59 | negative |

**One minute late costs 5.9 bps — 20% of the edge, more than the entire
6.6 bps cost assumption.**

### 3.5 Other confirmed results
- **Limit entries lose.** No limit rule beat the market order *even on
  filled trades*; patience cost more than the better price gained
  (ENTRYLIMITS_REPORT.md).
- **Overnight residual ≈ 0** (OVERNIGHT_REPORT.md).
- **High gap/ATR + very high volume**: higher mean *and* fatter left tail.

---

## 4. Data integrity — known and bounded

### 4.1 The volume series changes basis on 2022-03-07
*(VOLUME_INTEGRITY_REPORT.md)* Not 2022-03-01; the pipeline's
`IEX_BREAK` constant is four sessions early (harmless). From that date
HF volume is **IEX-only prints, 3.0–3.8% of consolidated**, verified
against an independent source. Volume *falls* ~10×; it does not rise.

**The filter survives it.** It is a ratio against its own trailing mean,
so the rescaling cancels. Incremental value 20.3 bps pre-break vs
17.0 post; difference −2.9 bps, 95% CI [−15.4, +11.6]. Prices are
unaffected — IEX prints are real trades.

### 4.2 A deliberate 4-month hole
No events exist between 2022-03-01 and 2022-06-29.
`run_study.break_aware_liquidity` excises every row whose 63-session
trailing window straddles the break. **Do not read a 2022 number as a
regime signal.**

---

## 5. Engine status and the reconciliation

`backtester/` — steps 1–7 complete plus universe provider and validation
gate. **159 assertions across seven suites.** See `WORKFLOW.md` and
`LIMITATIONS.md` in that folder.

### What was reconciled against the research
*(`backtester/tools/reconcile_research.py`, 1,103 trades, 60 tickers)*

| Check | Result |
|---|---|
| Entry price vs `entry_px_0935` | **100.00% exact**, max diff 0.0000 bps |
| 1-hour return, matched convention | **100.00% exact**, max diff 0.0000 bps |
| MAE (ATR) | 95.7% within 0.001 |

**One convention difference, and it matters when comparing numbers.**
The research exits at the **close of the 10:34 bar** (`EXIT_MIN = 64`);
the engine exits at the **open of the 10:35 bar**. Both are the instant
10:35:00, different prints. Gap: **+0.187 bps mean, sd 5.29, max 32.6
on a single trade.** The tool reports both.

### NOT reconciled — do not assume these match
ATR, volume ratio, candle classification, universe selection. Their
inputs no longer exist on disk. The research kept 1-minute bars only in
a **±1 session window around each event** (3 sessions, 90 minutes each),
so ATR(14) and the 20-session volume baseline cannot be recomputed. The
engine correctly emits zero signals on that data.

**Blocker:** continuous 1-minute bars covering ≥20 sessions before each
event, plus an earnings calendar with BMO/AMC timing. Even 20 tickers
over 2 years would unblock cohort reconciliation.

### The gate
`--gate`, exit codes 0 PASS / 5 NEEDS REVIEW / 4 FAIL. Integrity checks
(look-ahead, universe applied, trades exist) **cannot be outvoted by
performance and have no override**. Thresholds live in
`GateThresholds`, are printed with every verdict, and each check names
what it compared against.

**Mandatory sequence:**
```
RESEARCH → GATE → (PASS, or REVIEW justified in writing)
        → FULL VALIDATION → ROBUSTNESS → CAPACITY → LIVE
```
Running robustness on an unvalidated strategy produces a beautifully
detailed description of an artefact.

---

## 6. Open questions, priority order

1. **Conditional hold to the close.** Given status at 5/15/30/60 min,
   what is the expectancy *and full distribution* if held to 16:00?
   §3.1 shows 5-min losers recover materially by 10:35 — the open
   question is whether that continues to the close. Distribution, not
   averages.
2. **4-minute candle** (09:30–09:34, enter 09:34). Retention is 90.3%
   and the skipped minute moves +10.2 bps in the eventual direction, so
   the upper bound is ~9.2 bps (≈31% uplift). **Not testable on current
   data** — a 4-min volume ratio needs a trailing baseline over minutes
   0–3 on *non-event* sessions.
3. **High-volume Reversal.** Fade vs follow; 15-minute behaviour;
   relative strength vs SPY.
4. **Borrow cost on the short side** — the largest unmodelled cost, and
   it lands on the better-performing leg.
5. **Walk-forward / regime stability** beyond the period splits.

---

## 7. Live execution notes

- Backtest assumes a fill *at* the 09:35 open. No manual process
  achieves that. **If consistently 1–2 min slow, realistic expectancy is
  20–24 bps, not 29.7** — that gap is execution, not decay.
- Pre-stage tickets + hotkeys is the fastest manual method on IBKR.
- Native IBKR conditional orders cannot express candle-close + volume
  ratio.
- Automation via Futu OpenD + `futu-api` is installed and the real fix.
  OpenD must run on the local machine (GUI login required).
- Still to build: broker reconciliation, state persistence, kill switch,
  order logging, market-hours guards. Signal logic is ~10% of a live
  system.

---

## 8. How to behave in a new session

1. Read this file first.
2. **Never skip the gate** for a new variant or strategy.
3. Report distributions and year-by-year, not headline averages alone.
4. Separate validated from experimental explicitly.
5. **Check ratios whose denominator can be small or negative.** This
   project produced "kept 123% of edge" out of a growing loss and
   "largest name is 273% of P&L" from cancelling winners and losers.
   Both are now guarded; the pattern recurs.
6. When a number here conflicts with a report, **the report wins** —
   then fix this file.

---

## 9. One-paragraph status

A real, low-beta (β≈0.008), post-earnings high-volume continuation edge
that survives realistic capital constraints: 18.8% CAGR on $1M at 0.5%
risk with a −6.5% drawdown, deployed 7.4% of clock time. It has roughly
halved since 2020, dies near 36 bps round trip, and carries unmodelled
borrow on its better-performing short leg. The new engine's *execution
path* reconciles exactly against the research; its *signal path* is
unverified and blocked on continuous 1-minute data plus an earnings
calendar. Highest-priority research is the conditional hold-to-close
decision — noting that 5-minute losers recover +30.1 bps by 10:35, so
early stops are contraindicated. Live execution speed is worth ~6 bps
per trade and is the most certain available improvement.

---
**End of memory file**
