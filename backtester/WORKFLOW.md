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

**Integrity — a failure here cannot be outvoted by any performance
number, and there is no override flag.**

| Check | Fails when |
|---|---|
| `no_lookahead` | the future changes a decision |
| `universe_applied` | reviews when no provider is set, so "every session" is a visible choice |
| `trades_exist` | zero trades: nothing can be judged |
| `stale_exits` | too many exits fell back to a stale close |

**Sample adequacy — nothing is broken, but nothing is proven either.**
Too few trades, too few tickers, too short a history, or one name
carrying the P&L all produce NEEDS REVIEW.

**Performance.** Expectancy, profit factor, share of positive years, and
cost headroom: the edge must survive a multiple of the assumed cost.

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
from engine.gate import run_gate

res = run_gate(MyStrategy(cfg), cfg, frames, provider=my_provider,
               strategy_factory=lambda bars: MyStrategy(cfg))
print(res.report())
```

Pass `strategy_factory` whenever the strategy holds state. It makes the
look-ahead check strictly stronger by rebuilding the strategy from
truncated data, which catches a strategy holding a frame it captured at
construction. Without it the check still runs and the report says which
form was used.

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

## What the gate deliberately does not do

It does not tune, rank, or pick a best variant. It runs one
configuration and judges it. The moment a gate starts searching for a
version that passes, it has become an overfitting engine wearing a
gate's clothes.
