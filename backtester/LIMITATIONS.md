# Known limitations and TODOs

Status after step 4. Ordered by how badly each one would mislead you if
you forgot about it, not by how hard it is to fix.

## 1. BLOCKING — the universe filters are parsed but never applied

`universe.post_earnings_only`, `min_price` and `min_market_cap` are
validated and carried on the config object, and **nothing reads them.**

That means the strategy currently evaluates **every session of every
ticker**, not post-earnings T+1 sessions. On the synthetic fixtures this
is invisible because they contain no earnings information at all. On
real data it silently changes the strategy into something else: a
volume-and-continuation filter applied to all days, which is not what
any of the research measured.

This is deliberate rather than forgotten. Every one of those filters
needs a point-in-time reference source — an earnings calendar with
announcement timestamps, a market-cap series as-of each date — and
answering them from the price file would reintroduce survivorship and
restatement bias through the back door.

The hook already exists: `StrategyBase.run_many(frames, eligible=...)`
takes a `{ticker: {session, ...}}` mapping. Wiring a universe provider
into it is the next real piece of work.

**Until that is wired, treat signal counts from real data as an upper
bound, not a cohort.**

## 2. Metrics are a stub (step 5)

`engine/metrics.py` is seven lines of docstring. The trade log and equity
curve exist and are correct; nothing yet computes CAGR, drawdown,
Sharpe, Calmar, profit factor, payoff ratio, winsorised skew/kurtosis or
the year-by-year table from them.

## 3. Costs are a flat round-trip figure

`costs.round_trip_bps` is charged once on entry notional and does not
vary by name, price, volatility or time of day. Real spreads at 09:35 in
a post-earnings mid-cap are materially wider than in a mega-cap, and the
research showed the edge dies at roughly 36 bps round trip — so the cost
model is the assumption most likely to decide whether this is a business.

Not modelled at all:

- **borrow cost and locate on shorts**, which is the largest omission,
  because roughly half the signals are short and the short side carried
  the larger edge in the research
- market impact
- partial fills
- any capacity limit against the name's actual volume in that hour

## 4. Execution simplifications

- **Bar labelling is assumed LEFT-labelled**: the bar stamped 09:35
  covers 09:35:00–09:36:00. If your vendor stamps the right edge, the
  session filter and every entry is off by one minute. Check this before
  trusting a single number.
- **Stop fills** use the worse of the intended level and the bar open.
  Within-bar path is unknown, so a bar that touched the stop and
  recovered is assumed to have filled — correct for a resting stop
  order, pessimistic for a mental stop.
- **Gap-through beyond the bar open** is not modelled; the open is
  treated as the worst obtainable price.
- **`exit_reason="time_stale"`** marks trades whose exit bar never
  printed. They are kept with the last available close. Filter on this
  column before reporting if it is material in your data.

## 5. Scope limits enforced by config

- `exit.type` supports only `time`. No trailing stops, targets, or
  signal-based exits.
- `exit.stop.type` supports only `atr`.
- `exit.hold_minutes` is capped at 390 (one session). The portfolio loop
  assumes positions open and close within a session, and the config
  refuses longer holds so that assumption cannot be violated silently.
  Multi-session holds need a different loop.
- `signal.entry_price` accepts only `open`. `close` is rejected with an
  explanation: the entry bar's close does not exist at the decision
  instant, and the signal candle's close is a print that already
  happened and cannot be traded at.

## 6. Point-in-time guard — the one hole that is left

`verify_no_lookahead` catches leakage through the engine's inputs, and
when passed a **factory** it also rebuilds the strategy from truncated
data, which catches a strategy that captured a full-history frame at
construction.

It **cannot** see a strategy that opens a file or reads a global inside
`evaluate`. Nothing can truncate a source the checker does not know
about. `audit_source` and code review cover that case.
`tests/test_pit_strategy.py::t_instance_form_misses_captured_state`
asserts this limitation deliberately, so it stays visible.

## 7. Smaller things

- **Selection under the concurrency cap** uses a fixed RNG seed (7) for
  `SelectionRule.RANDOM`, so a "random" run is one reproducible draw,
  not a distribution. To price the ranking's contribution properly, loop
  over seeds.
- **Memory**: `DataLoader` reads whole files. A few hundred tickers of
  1-minute bars over ten years will not fit comfortably; loading is
  per-ticker by design, but `load_many` holds them all at once.
- **`Portfolio.run` flattens `Signal.features` with `json_normalize`**,
  which is convenient and slow at large trade counts.
- **No logging framework.** Diagnostics print to stdout.
- **Fixtures are random walks.** They exercise the plumbing; their P&L
  is meaningless and should never be quoted.

## What is NOT a limitation

These were checked and are correct, so nobody needs to re-investigate:

- Timezones and DST. Sessions are defined in `America/New_York` and
  resolved per session; a 09:35 entry lands on 09:35 local in both EDT
  and EST. Pinned by `t_dst_transition` and `t_local_time_to_utc_dst`.
- Half days. Session end comes from the data, not a holiday table.
- Overlapping vendor files. Resolved to the later-issued extract, with
  the count reported in `df.attrs["duplicates_dropped"]`.
- Missing bars stay missing. Nothing is forward-filled.
- Trailing statistics. ATR and the volume baseline exclude the current
  session structurally, not by a `.shift()` anyone has to remember.
