# Known limitations and TODOs

Status after step 7 plus the gate's sensitivity and benchmark stages.
Ordered by how badly each one would mislead you if you forgot about it,
not by how hard it is to fix.

## 1. Universe filters are ENFORCED (resolved)

`universe.post_earnings_only`, `min_price` and `min_market_cap` are now
applied by `engine/universe.py` and wired through
`StrategyBase.run_many(frames, eligible=...)`. A config that sets
`post_earnings_only: true` without an earnings calendar RAISES rather
than silently falling back to every session, and `min_market_cap`
without a point-in-time market-cap series raises for the same reason.

Two things about that enforcement still need a human:

- **Announcement timing is data, not inference.** BMO on day D reacts on
  D; AMC on D reacts on the next traded session. Rows with unknown
  timing are SKIPPED by default and counted in the diagnostics. The
  `assume_amc` / `assume_bmo` policies exist because many vendors ship
  `time-not-supplied`, but they are assumptions and the diagnostics
  label them as such. If most of your calendar is unknown, the default
  will produce very few signals -- that is the guard, not a fault.
- **Survivorship still enters upstream.** The provider can only filter
  the tickers it is handed. A file list drawn from today's index
  membership is already biased before it arrives, and nothing here can
  undo it. `diagnostics()` reports the ticker count so the gap is
  visible; the fix belongs in how the data was collected.

## 2. Ratios against a non-positive base are suppressed, not computed

`capacity._kept` returns NaN when the baseline P&L is zero or negative.
A "% of P&L kept" ratio inverts against a loss -- a loss deepening from
-881 to -1081 computes as 1.23, which reads as *kept 123%*. Every
friction in that module can only subtract, so a ratio above 1.0 always
means the denominator is wrong. On a losing sub-period you will see
blanks and an absolute `pnl_change` instead; that is intended.

## 3. `metrics.reprice` is exact per trade, approximate on the curve

Cost changes neither which trades fire nor when they exit, so per-trade
statistics re-cost exactly. It does change equity, and fixed-fractional
sizing reads equity, so the true path would size later trades
differently. The robustness suite therefore re-runs the Portfolio at
each cost rather than re-pricing; `reprice` exists for fast sweeps and
says so itself.

## 4. Costs are a flat round-trip figure

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

## 5. Execution simplifications

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

## 6. Scope limits enforced by config

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

## 7. Point-in-time guard — the one hole that is left

`verify_no_lookahead` catches leakage through the engine's inputs, and
when passed a **factory** it also rebuilds the strategy from truncated
data, which catches a strategy that captured a full-history frame at
construction.

It **cannot** see a strategy that opens a file or reads a global inside
`evaluate`. Nothing can truncate a source the checker does not know
about. `audit_source` and code review cover that case.
`tests/test_pit_strategy.py::t_instance_form_misses_captured_state`
asserts this limitation deliberately, so it stays visible.

## 8. The gate's sensitivity and benchmark stages have four blind spots

Both stages were added after step 7 and each has a boundary worth
knowing before a number from them is quoted.

- **The sensitivity sweep is one-at-a-time.** Each parameter moves alone.
  A strategy that is robust to any single parameter and fragile to a
  *pair* of them will pass. A full grid is combinatorially expensive and
  would itself start to look like a search; if you need it, run it
  deliberately and outside the gate.
- **The sweep is relative, so a parameter set to zero is skipped.**
  `volume_ratio_min: 0.0` means "no volume filter", and every relative
  step of zero is still zero. That parameter is reported as skipped with
  the reason, not silently passed.
- **`n_binding` is the number that matters on thin data.** If every
  variant returns the baseline result unchanged, the parameters never
  bound on that sample and the gate reports NEEDS REVIEW rather than
  perfect stability. On the fixtures — which produce one trade — this is
  exactly what happens, and it is correct.
- **Longer holds are intraday only.** `hold_minutes` is capped at the
  session close, so "held longer" means up to 16:00, never overnight and
  never multi-day. A multi-day comparison needs the portfolio loop that
  section 6 says does not exist yet. If a longer-hold row shows a high
  `time_stale` share the table says so in a note, because that row then
  understates what holding longer would really have done.

And one about the comparison itself: **the Sharpe margin over
buy-and-hold is structurally flattered for any strategy that is idle
most of the time**, because its volatility is computed over sessions
where it held nothing. `pct_days_active` and `deployed_vol` are printed
beside it and the detail line names the problem, but no adjustment is
applied — there is no single defensible one.

## 9. Smaller things

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
  is meaningless and should never be quoted. Because they lose money,
  every capacity ratio comes back blank on them by design -- that is the
  guard working, not a bug.
- **Sub-minute delay rows are interpolated.** Bars are one minute, so a
  60-second delay is exact and 30/90 seconds are linear interpolations
  between bracketing opens. The `exact` column says which is which.

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
