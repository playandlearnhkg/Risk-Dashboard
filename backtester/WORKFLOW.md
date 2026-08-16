# Workflow

The order below is not a suggestion. Every step exists because skipping
it produced a wrong number at least once in this project.

```
   1. RESEARCH            form the idea, write the strategy class
          |
   2. VALIDATION GATE     --gate    ← must PASS before anything below
          |
          +--- FAIL ------> fix or abandon. No robustness, no sizing.
          |
          +--- NEEDS REVIEW -> a human decides, in writing, then re-runs
          |
          v  PASS
   3. FULL VALIDATION     --full-validation
   4. ROBUSTNESS          --robustness
   5. CAPACITY            --capacity
          |
   6. LIVE CONSIDERATION  sized off the WEAKEST sub-period, not the mean
```

## Why the gate comes second, not last

Robustness and capacity answer "how good is it, really". They are
expensive and they are meaningless if the strategy is looking at future
data or trading a cohort nobody intended. The gate answers the prior
question — *is this measuring what we think it is measuring* — and it is
cheap.

Running robustness on an unvalidated strategy produces a beautifully
detailed description of an artefact.

## What the gate checks

The five stages run in a fixed order, and the order is not cosmetic.
Each stage is more expensive than the one before it and meaningless
without it: measuring the parameter neighbourhood of a strategy that
reads the future prices the neighbourhood of a leak.

```
  1 INTEGRITY  ->  2 ADEQUACY  ->  3 PERFORMANCE  ->  4 SENSITIVITY  ->  5 BENCHMARKS
  is it real?      enough of it?   is there edge?     plateau or spike?   better than the obvious?
```

**1. Integrity — a failure here cannot be outvoted by any performance
number, and there is no override flag.**

| Check | Fails when |
|---|---|
| `no_lookahead` | the future changes a decision |
| `universe_applied` | reviews when no provider is set, so "every session" is a visible choice |
| `trades_exist` | zero trades: nothing can be judged |
| `stale_exits` | too many exits fell back to a stale close |

**2. Sample adequacy — nothing is broken, but nothing is proven either.**
Too few trades, too few tickers, too short a history, or one name
carrying the P&L all produce NEEDS REVIEW.

**3. Performance.** Expectancy, profit factor, share of positive years,
and cost headroom: the edge must survive a multiple of the assumed cost.

**4. Parameter sensitivity — is this a plateau, or one fitted point?**

Each of `signal.volume_ratio_min`, `signal.doji_max_body_ratio` and
`exit.hold_minutes` is moved ±10% and ±20% and the **whole path is
re-run** — signals regenerated, portfolio re-simulated. Re-costing the
baseline trade log would not do: two of those three are signal filters,
so changing them changes which trades exist at all.

| Check | Fails when |
|---|---|
| `sensitivity_stability` | under half the neighbourhood is still profitable |
| `sensitivity_spike` | the configured values earn more than 3× the median of their own neighbours |

`spike_ratio` is `baseline ÷ median(neighbours)`. **1.0 is a plateau.**
Well above 1.0 is what a fitted parameter looks like from the outside.
The ratio is NaN — and reported as such — whenever the neighbourhood
median is at or below zero, because a non-positive denominator turns a
collapsing neighbourhood into a large positive number that reads like
good news. This project has produced that exact artefact twice before.

Two things this stage refuses to do. It never reports a *better*
parameter value; the moment a gate starts returning the best cell it has
become the search process it exists to detect. And variants that
returned the baseline result unchanged are counted separately
(`n_binding`) and do not earn a pass — a filter loose enough to be inert
would otherwise sail through as "stable".

**5. Benchmarks — better than the obvious alternative?**

| Check | Fails when |
|---|---|
| `benchmark_vs_index` | Sharpe is at or below buy-and-hold over the *strategy's own window* |
| `benchmark_vs_longer_hold` | never fails; REVIEWS when holding the same names longer beat the configured hold by more than 0.10 Sharpe |

Buy-and-hold is priced over exactly the sessions the strategy traded,
not against a remembered long-run average, so a strategy that ran
through a bull market is measured against that bull market. The longer
holds re-run the identical signals with `exit.hold_minutes` at 2× and 4×,
capped at the session close (a wall-clock exit past 16:00 lands in a gap
with no bars and would fill every trade at a stale price).

The longer-hold check **reviews but never fails**: a longer hold winning
does not make the edge fake, it makes the chosen exit questionable, and
that is a judgement for a human with the research in front of them.

**The comparison that is not fair, and is printed anyway.** An intraday
book holding positions 7% of the clock has almost no volatility on the
other 93% of days, so its Sharpe is structurally flattered against an
index that is exposed every day. In this project's own research the
headline Sharpe was 2.82 while volatility on days capital was actually
working was 22.4%, not 6.7%. So `pct_days_active` and `deployed_vol` sit
in the same table as `sharpe`, the detail line says *"the strategy is
idle on 93% of sessions, so this margin is flattered"*, and **nothing is
silently adjusted** — there is no single defensible adjustment, and
inventing one would hide the problem rather than show it.

Both stages are expensive. `--no-extended` skips them, and skipping is
**visible**: the four checks still appear, as NEEDS REVIEW, saying they
were turned off. A skipped test and a passed test must never look alike
in the artefact.

Thresholds live in `GateThresholds`, are printed with every verdict, and
name the number each check compared against. Loosening one to make a run
pass therefore shows up in the artefact.

## Three verdicts, not two

`NEEDS REVIEW` exists because *"we cannot tell yet"* and *"this does not
work"* are different findings. Collapsing them into FAIL teaches people
to ignore the gate.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | PASS |
| 4 | FAIL |
| 5 | NEEDS REVIEW |

So `--gate` can sit in CI or a pre-commit hook without anyone reading
the output.

## Adding a new strategy

Four steps. The gate needs no changes for any of them.

**1. Write the class.** Implement `evaluate(view) -> Signal | None`.
The view holds prior completed sessions and today's bars up to the
decision instant, so trailing features are trailing by construction.
`.rolling`, `.ewm`, `.expanding` and negative `.shift` are refused at
construction time.

```python
from engine.pit import SessionView
from engine.strategy_base import Signal, StrategyBase

class MyStrategy(StrategyBase):
    def evaluate(self, view: SessionView) -> Signal | None:
        atr = view.prior.atr(self.config.signal.atr_period)
        if not (atr == atr) or atr <= 0:
            return None
        ...
        return Signal(ticker=view.ticker, session=view.session,
                      decision_ts=view.decision_ts, direction=+1,
                      entry_ts=view.decision_ts,
                      entry_price=view.entry_open, risk_unit=atr,
                      planned_exit_ts=view.decision_ts + pd.Timedelta(minutes=60),
                      features={"volume_ratio": ...})
```

Emit whatever the portfolio's selection rule ranks on — `volume_ratio`
by default — or the concurrency cap will raise rather than rank
arbitrarily.

**2. Write the config.** Copy an existing YAML. Unknown keys raise with
the valid alternatives, so a typo cannot silently disable a filter.

**3. Choose a universe.** `AllSessions()` if the strategy genuinely
trades every day — the gate will flag that for a human rather than
assume it. A `UniverseProvider` subclass otherwise.

**4. Run the gate.**

```python
from engine.data_loader import DataLoader
from engine.gate import run_gate

spy = DataLoader("data/benchmark").load("SPY")

res = run_gate(MyStrategy(cfg), cfg, frames, provider=my_provider,
               strategy_factory=lambda bars: MyStrategy(cfg),
               config_factory=MyStrategy,
               benchmark_bars=spy, benchmark_ticker="SPY")
print(res.report())
```

Or from the terminal:

```bash
python3 run_backtest.py --config config/strategies/my_strategy.yaml \
        --gate --benchmark SPY
```

Three optional arguments, and what each one buys:

| Argument | Without it |
|---|---|
| `strategy_factory(bars)` | the look-ahead check still runs but cannot catch a strategy holding a frame it captured at construction; the report says which form was used |
| `config_factory(config)` | sensitivity and longer-hold report NEEDS REVIEW. It defaults to `type(strategy)(config)`, which is correct for any strategy whose constructor takes only a config — pass one explicitly if yours takes more |
| `benchmark_bars` | `benchmark_vs_index` reports NEEDS REVIEW: no comparison was made, and that absence is a visible choice rather than a silent one |

**Keep the benchmark out of the tradeable universe.** The SPY fixture
lives in `data/benchmark/`, one directory down, because the catalog globs
a single level — so `DataLoader("data")` cannot see it and the strategy
can never trade the thing it is being compared with. A test asserts this.

## A worked example

`strategies/opening_range_breakout.py` is a second strategy sharing
nothing with the post-earnings one — no gap, no earnings calendar, no
volume filter, no candle classification. It exists to keep the gate
honest: a gate with one client is a gate shaped around that client.

Adding it immediately exposed one such case. The config refused
`volume_ratio_min: 0.0`, forcing every strategy to carry a volume
threshold shaped around the post-earnings strategy. Zero now means "no
filter", which is what it should always have meant.

```bash
python3 run_backtest.py --config config/strategies/opening_range_breakout.yaml --gate
```

## What passing and failing the new checks looks like

Both blocks below are real output from `_sensitivity_checks` and
`_benchmark_checks`, run on the two shapes.

**A strategy that clears them.** The neighbourhood earns what the chosen
values earn, and the index is well behind:

```
PASS         sensitivity_stability: 100% of 4 nearby parameter settings are still
             profitable; neighbourhood median 29.50 bps against a baseline 29.70 bps
PASS         sensitivity_spike: the configured values earn 1.01x the median of their
             own neighbours (1.0x would be a flat plateau)
PASS         benchmark_vs_index: Sharpe 2.82 vs SPY buy & hold 0.61 (margin +2.21);
             max drawdown -5.0% vs -34.0%; total return 100.0% vs 90.0%; the strategy
             is idle on 93% of sessions, so this margin is flattered
PASS         benchmark_vs_longer_hold: the configured hold has Sharpe 2.82; the best
             longer hold tested (hold 4x = 240 min) has 2.79 (margin +0.03). The
             configured hold is not beaten by simply waiting.
```

Note that the caveat is printed **on the passing line**. Passing is not a
reason to stop reading.

**A strategy that does not.** Same expectancy at the chosen point, but
it is a peak rather than a plateau, and the index beat it:

```
PASS         sensitivity_stability: 100% of 4 nearby parameter settings are still
             profitable; neighbourhood median 8.00 bps against a baseline 29.70 bps
FAIL         sensitivity_spike: the configured values earn 3.71x the median of their
             own neighbours (1.0x would be a flat plateau)
FAIL         benchmark_vs_index: Sharpe 0.44 vs SPY buy & hold 0.61 (margin -0.17);
             max drawdown -5.0% vs -34.0%; total return 100.0% vs 90.0%
NEEDS REVIEW benchmark_vs_longer_hold: the configured hold has Sharpe 0.44; the best
             longer hold tested (hold 4x = 240 min) has 1.30 (margin -0.86). Holding
             the same names longer did better, so the exit is doing work the entry
             filter is being credited with.
```

The first line of that second block is the one worth studying.
`sensitivity_stability` **passed** — every neighbour still made money, so
nothing looks broken. It took the spike ratio to show that the
neighbours made 8 bps while the chosen point made 29.7. A single
stability number would have missed it entirely, which is why there are
two checks and not one.

## Integrity still cannot be outvoted

The verdict rule is unchanged and deliberately crude: **any failing
check fails the run.** There is no weighting and no score, so nothing a
later stage produces can rescue an earlier one. A strategy with a
perfectly flat sensitivity surface and a Sharpe five times the index
still FAILS on a look-ahead leak, and a test asserts exactly that.

The reverse also holds, and is the reason sensitivity and benchmarking
were added at all: a strategy can be perfectly honest, adequately
sampled, profitable after costs — and still be a peak in parameter space
that a human would never have noticed from the headline numbers.

## What the gate deliberately does not do

It does not tune, rank, or pick a best variant. It runs one
configuration and judges it. The moment a gate starts searching for a
version that passes, it has become an overfitting engine wearing a
gate's clothes.
