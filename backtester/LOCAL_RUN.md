# Running locally with your own data

This guide does NOT use `--teleport`. Teleport needs a recent CLI and a
matching cloud session, and it failed once already with
`No --teleport flag exists in this Claude Code CLI (v2.1.183)`. Nothing
here depends on it.

**The context is not in the chat session. It is in this repository.**
Everything the cloud session learned is committed here as files, so a
fresh local Claude session that reads them starts with the same
knowledge. That is why this works without teleport.

---

## 1. Install (once)

```powershell
# PowerShell. Node is not needed; this is the native installer.
irm https://claude.ai/install.ps1 | iex
claude --version
```

If `claude --version` prints something older than **2.1.223**, update
before doing anything else -- that is the version that first shipped
`--teleport`, and an old CLI is what produced the earlier error:

```powershell
claude update
```

You also need Python 3.11+ with four packages:

```powershell
python --version
pip install "pandas>=2.0" "pyarrow>=12.0" "numpy>=1.24" "PyYAML>=6.0" tzdata
```

`tzdata` is **required on Windows** and not optional: Windows ships no
system timezone database, and every session boundary in this engine is
defined in `America/New_York`. Without it the engine raises
`ZoneInfoNotFoundError` at import.

## 2. Get the code

```powershell
cd $HOME
git clone https://github.com/playandlearnhkg/Risk-Dashboard.git
cd Risk-Dashboard
git checkout claude/lambda-strategy-validation-mcdf3u
cd backtester
python tests/run_all.py
```

`run_all.py` must print **ALL SUITES PASSED** (200 assertions across six
suites). If it does not, stop -- the engine is broken on your machine and
no result it produces afterwards means anything. The most likely cause on
Windows is the missing `tzdata` above.

Do NOT clone into `C:\Windows\system32`. `cd $HOME` first, as above.

## 3. Point the engine at your data

Your files almost certainly are not in the engine's format. The engine
wants `{TICKER}_{YYYYMMDD}_{YYYYMMDD}_1m.parquet`, UTC-indexed, with
float open/high/low/close/volume. `tools/import_local.py` converts
whatever you have.

**Inspect first. Always.**

```powershell
python tools/import_local.py "D:\path\to\your\data\*.csv" --inspect
```

This writes nothing. It prints which column it thinks is the timestamp,
**how it decided the timezone**, and the first bars rendered in New York
time. Read that output before continuing.

> The session open must read **09:30** in NY time.
> `04:00` also appearing is fine -- that is pre-market, and the loader
> filters it out. But if the open reads `14:30` or `05:30`, **the
> timezone is wrong**. Stop. A wrong timezone shifts every entry to a
> different minute, the backtest still runs, and every number it
> produces is wrong in a way no summary statistic will reveal.

If the tool cannot decide (it refuses rather than guessing), tell it:

```powershell
python tools/import_local.py "D:\data\*.csv" --inspect --assume-tz "America/New_York"
# or --assume-tz UTC
```

When the inspection looks right, drop `--inspect` to write:

```powershell
python tools/import_local.py "D:\data\*.csv" --out data
```

Files holding one ticker with no ticker column need `--ticker AAPL`.
Files holding many tickers are split automatically.

Then confirm the engine agrees with what is on disk:

```powershell
python run_backtest.py --config config/strategies/core_post_earnings.yaml --audit
```

`--audit` compares each filename's declared date range against the file's
actual contents and reports mismatches. It does not run a backtest.

## 4. Run

The order is fixed and each step exists because skipping it produced a
wrong number at least once. See `WORKFLOW.md`.

```powershell
# a. What does the strategy actually fire on? Look at real signals first.
python run_backtest.py --config config/strategies/core_post_earnings.yaml --signals

# b. THE GATE. Must pass before any performance number is trustworthy.
python run_backtest.py --config config/strategies/core_post_earnings.yaml --gate

# c. Only after the gate passes:
python run_backtest.py --config config/strategies/core_post_earnings.yaml --full-validation
python run_backtest.py --config config/strategies/core_post_earnings.yaml --robustness
python run_backtest.py --config config/strategies/core_post_earnings.yaml --capacity
```

Exit codes: `0` PASS, `5` NEEDS REVIEW, `4` FAIL.

### The universe matters

The Core strategy is defined on **post-earnings T+1 sessions**, not every
session. Without an earnings calendar the gate will flag that, correctly,
as measuring a different strategy:

```powershell
python run_backtest.py --config config/strategies/core_post_earnings.yaml --gate `
    --earnings data\earnings_calendar.csv --market-caps data\market_caps.csv
```

The repo already contains a real, resolved post-earnings dataset at
`..\lambda_strategy_validation\data\postearnings_extract.csv` -- 16,188
rows, 2015-01-07 to 2025-12-22, with point-in-time market caps and a
`passes_universe_screen` flag (9,345 pass). That is the cohort the
original research used, and it is the fastest way to get a correct
universe without sourcing a calendar.

`--no-universe` runs every session. It is a diagnostic, not the strategy,
and the runner prints a warning saying so.

## 5. Continue this work with a local Claude session

```powershell
cd $HOME\Risk-Dashboard
claude
```

Then, as the first message:

> Read `edge_Vol_Earning_Memory.md`, `backtester/WORKFLOW.md`,
> `backtester/LIMITATIONS.md` and `backtester/LOCAL_RUN.md`. I have
> imported my own data into `backtester/data`. Continue the Priority 1
> validation from there.

Those four files carry the state: the validated numbers and their
sources, the five gate stages, the known limitations, and this guide.
A local session that reads them is caught up.

---

## What is already done, and what is not

**Done and committed:**
- The engine: loader, config, point-in-time guard, portfolio, metrics,
  universe provider, robustness, capacity, and the five-stage validation
  gate. 200 assertions, all passing.
- `tools/import_local.py` (this guide's step 3) and
  `tools/massive_ingest.py` (for the massive/Polygon REST API).
- The standard metric set: expectancy in bps **and** ATR, median,
  winsorised skew/kurtosis, 10/25/75/90 percentiles, % losing >0.5 and
  >1.0 ATR, % gaining >1.0 ATR, average large loss, year-by-year,
  long/short, cost sweep, stop-vs-no-stop, MAE/MFE.

**Not done -- the open questions:**
- **Tests 3 and 4** (volume-ratio sweep, four-quadrant analysis) need
  small new report builders. They do not exist yet.
- **The AAPL ack-test is incomplete.** Entry price and gap were checked
  against real data; the volume ratio and ATR14 were not.
- **A live data-quality discrepancy, unresolved.** On AAPL 2025-10-31,
  the old HF-derived extract and real Massive data disagree materially:

  | | Old extract | Real Massive |
  |---|---|---|
  | Gap % | +0.61% | **+2.07%** |
  | Candle (09:30-09:34) | "Indecisive" | body/range **0.81**, decisive |

  Direction and the broad shape agree; magnitude and candle character do
  not. The working hypothesis is that this is a consequence of the
  **2022-03-07 IEX source break** already documented in
  `VOLUME_INTEGRITY_REPORT.md`: post-break HF data is IEX-only prints,
  3-4% of the consolidated tape, and sampling that thin a slice over
  five minutes can miss the real price action. That would mean the break
  damages **candle classification**, not just volume -- which matters,
  because candle shape gates whether a trade fires at all.

  **This is unconfirmed on one event.** It needs the same comparison
  across many events before it is treated as a finding.
