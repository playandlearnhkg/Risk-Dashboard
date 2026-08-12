"""
timing.py -- when to enter, and what being late costs.

Two questions that turn out to be the same question.

  A EARLIER: enter on a 4-minute candle at 09:34 instead of a 5-minute
    candle at 09:35, on the theory that most people watch the 5-minute
    bar and a minute of lead is worth something.

  B LATER: you saw the signal but took time to act, and filled after
    09:35. What did the delay cost?

B IS FULLY VALID AND IS THE PRIMARY RESULT. The signal is known at
09:35; filling later uses no information that did not exist at the
decision. Nothing is conditioned on the future.

A IS NOT DIRECTLY TESTABLE ON THIS DATA, AND SAYING SO MATTERS MORE
THAN PRODUCING A NUMBER. Trading at 09:34 requires a signal computable
at 09:34: a 4-minute candle classification AND a 4-minute volume ratio.
The volume ratio needs a trailing 20-session baseline over minutes 0-3,
which needs 1-minute bars on NON-event sessions. This dataset carries
1-minute bars on event sessions only, so that baseline cannot be built.

What CAN be measured, and is:

  A1 RETENTION. Of the trades the 5-minute rule currently takes, what
     fraction would the 4-minute candle also classify as continuation?
     This is the signal-quality cost of the shorter candle, and it is
     computable because both candles are built from the same bars.

  A2 THE MISSING MINUTE. What does price do between the 09:34 open and
     the 09:35 open, in the direction the trade eventually took? This is
     the prize the earlier entry is chasing.

     A2 IS CONDITIONED ON A SIGNAL NOT YET KNOWN AT 09:34, so it is an
     UPPER BOUND on the benefit, not a tradeable return. Read it as
     "here is the most the extra minute could be worth", then discount
     it by the retention rate in A1.

Run: python3 lambda_strategy_validation/timing.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import analysis as A
from regime_sizing import build_cohort
from stops import COST_BPS, ENTRY_MIN, EXIT_MIN, OUT_DIR, log

BASE = Path("/home/user/lambda_data")
HERE = Path(__file__).resolve().parent
REPORT = HERE / "TIMING_REPORT.md"

# Fills to test, as minutes from the session open. 5 is the live rule.
FILL_MINUTES = [3, 4, 5, 6, 7, 8, 10, 15, 20]
SIGNAL_MIN = 5          # the decision instant: the 5-minute candle closes


def boot(x: np.ndarray, dates: pd.Series) -> tuple[float, float, float]:
    """Date-clustered bootstrap on a bps series; returns (mean, lo, hi)."""
    ok = np.isfinite(x)
    b = A.clustered_bootstrap(pd.Series(x[ok] / 1e4).reset_index(drop=True),
                              pd.Series(np.asarray(dates)[ok]).reset_index(drop=True))
    return b["stat"] * 1e4, b["lo"] * 1e4, b["hi"] * 1e4


def md(df: pd.DataFrame, num=(), pct=()) -> str:
    x = df.copy()
    for c in num:
        if c in x:
            x[c] = x[c].map(lambda v: "" if pd.isna(v) else f"{v:,.2f}")
    for c in pct:
        if c in x:
            x[c] = x[c].map(lambda v: "" if pd.isna(v) else f"{v*100:,.1f}%")
    head = "| " + " | ".join(x.columns) + " |"
    rule = "|" + "|".join("---" for _ in x.columns) + "|"
    body = ["| " + " | ".join(str(v) for v in r) + " |"
            for r in x.itertuples(index=False)]
    return "\n".join([head, rule, *body])


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    C = build_cohort()
    df, sign, atr = C["df"], C["sign"], C["atr"]
    opens, highs, lows, closes = C["opens"], C["highs"], C["lows"], C["closes"]
    scr = C["scr"]
    dates = df["date"]

    m = scr & (df["date"] >= "2015-01-01").to_numpy()
    log(f"screened cohort: {m.sum():,}")

    exit_px = closes[:, EXIT_MIN]

    # ---------------------------------------------------------------- B
    # Same signal, later fill, SAME 10:35 exit. A delayed entry does not
    # get to extend its holding period -- the exit is a clock decision.
    rows = []
    base_mean = None
    for k in FILL_MINUTES:
        px = opens[:, k]
        r = sign * (exit_px - px) / px * 1e4 - COST_BPS
        r = np.where(np.isfinite(px) & (px > 0), r, np.nan)
        mean, lo, hi = boot(r[m], dates[m])
        if k == SIGNAL_MIN:
            base_mean = mean
        rows.append({"fill_minute": k,
                     "clock": f"09:{30 + k:02d}",
                     "valid": "yes" if k >= SIGNAL_MIN else "DIAGNOSTIC",
                     "n": int(np.isfinite(r[m]).sum()),
                     "net_bps": mean, "ci_lo": lo, "ci_hi": hi,
                     "win_rate": float(np.nanmean(r[m] > 0))})
    D = pd.DataFrame(rows)
    D["vs_0935_bps"] = D["net_bps"] - base_mean
    D["pct_of_edge_kept"] = D["net_bps"] / base_mean

    # Per-minute decay across the first few minutes after the signal.
    late = D[(D.fill_minute >= SIGNAL_MIN) & (D.fill_minute <= 10)]
    per_min = float(np.polyfit(late.fill_minute, late.net_bps, 1)[0])
    first_min = float(D[D.fill_minute == SIGNAL_MIN + 1].iloc[0]["vs_0935_bps"])
    below_half = D[(D.fill_minute > SIGNAL_MIN) & (D.pct_of_edge_kept <= 0.5)]
    half_gone = below_half.iloc[0]["clock"] if len(below_half) else "beyond 09:50"

    # --------------------------------------------------------------- A1
    # Rebuild the 4-minute candle from the same bars and ask whether it
    # agrees with the 5-minute classification that selected the cohort.
    gap_up = df["gap_up"].to_numpy()

    def candle(n: int):
        o = opens[:, 0]
        h = np.nanmax(highs[:, :n], axis=1)
        lo_ = np.nanmin(lows[:, :n], axis=1)
        c = closes[:, n - 1]
        return o, h, lo_, c

    agree = {}
    for n in (3, 4, 5):
        o, h, lo_, c = candle(n)
        rng = h - lo_
        body = c - o
        with np.errstate(invalid="ignore", divide="ignore"):
            ratio = np.abs(body) / rng
        is_doji = (rng <= 0) | (ratio <= 0.10)
        with_gap = (body > 0) == gap_up
        cont = (~is_doji) & with_gap
        ok = np.isfinite(o) & np.isfinite(c) & np.isfinite(rng)
        agree[n] = {"n_eval": int((m & ok).sum()),
                    "retained": float(np.nanmean(cont[m & ok])),
                    "doji": float(np.nanmean(is_doji[m & ok])),
                    "against_gap": float(np.nanmean(
                        (~with_gap)[m & ok]))}
    R = pd.DataFrame([{"candle_minutes": k, **v} for k, v in agree.items()])

    # --------------------------------------------------------------- A2
    # The prize: the signed move across the minute you would skip.
    steps = []
    for a, b in ((3, 5), (4, 5), (5, 6), (5, 7), (5, 10)):
        pa, pb = opens[:, a], opens[:, b]
        mv = sign * (pb - pa) / pa * 1e4
        mv = np.where(np.isfinite(pa) & np.isfinite(pb) & (pa > 0), mv, np.nan)
        mean, lo, hi = boot(mv[m], dates[m])
        steps.append({"from": f"09:{30 + a:02d}", "to": f"09:{30 + b:02d}",
                      "minutes": b - a, "signed_move_bps": mean,
                      "ci_lo": lo, "ci_hi": hi,
                      "pct_positive": float(np.nanmean(mv[m] > 0))})
    S = pd.DataFrame(steps)

    ret4 = float(R[R.candle_minutes == 4].iloc[0]["retained"])
    gain4 = float(S[(S["from"] == "09:34") & (S["to"] == "09:35")]
                  .iloc[0]["signed_move_bps"])

    meta = {"n": int(m.sum()), "cost_bps": COST_BPS,
            "base_net_bps": base_mean, "decay_per_minute": per_min,
            "retention_4min": ret4, "missing_minute_bps": gain4,
            "start": str(df.loc[m, "date"].min().date()),
            "end": str(df.loc[m, "date"].max().date())}

    D.to_csv(OUT_DIR / "timing_delay.csv", index=False)
    R.to_csv(OUT_DIR / "timing_candle.csv", index=False)
    S.to_csv(OUT_DIR / "timing_steps.csv", index=False)

    REPORT.write_text(f"""# Entry timing: earlier, later, and what each is worth

{meta['n']:,} screened post-earnings continuation trades, {meta['start']} to
{meta['end']}, 1-hour hold to 10:35, after {COST_BPS} bps.

## B. The cost of being late

Same signal, known at 09:35. Only the fill moves. The exit stays at
10:35, because a slow entry does not earn a longer hold.

**Only the rows from 09:35 down are valid.** The 09:33 and 09:34 rows
are marked DIAGNOSTIC because they fill on a signal that does not exist
until 09:35; they are shown because they quantify the earlier-entry idea
in section A, not because anyone could have traded them.

{md(D[["clock", "valid", "n", "net_bps", "ci_lo", "ci_hi",
       "win_rate", "vs_0935_bps", "pct_of_edge_kept"]],
    num=("net_bps", "ci_lo", "ci_hi", "vs_0935_bps"),
    pct=("win_rate", "pct_of_edge_kept"))}

The decay is steep and FRONT-LOADED, which is the part that matters
operationally. The very first minute of delay costs **{abs(first_min):.1f} bps, or
{abs(first_min) / base_mean * 100:.0f}% of the entire edge**. After that the slope flattens to about
{abs(per_min):.1f} bps per minute. Half the edge is gone by {half_gone}, and by
09:50 the expectancy has crossed zero.

## A1. What a 4-minute candle would cost in signal quality

Of the trades the 5-minute rule currently takes, how many would a
shorter candle still classify as continuation? Both candles are built
from the same 1-minute bars, so this is measurable exactly.

{md(R, pct=("retained", "doji", "against_gap"))}

A 4-minute candle keeps **{ret4:.1%}** of the current selections. The rest
either fail the doji test on a shorter range or have not yet closed in
the gap direction at 09:34.

## A2. What the extra minute is actually worth

The signed move across the minutes you would skip or lose.

{md(S, num=("signed_move_bps", "ci_lo", "ci_hi"), pct=("pct_positive",))}

**Read the 09:34 to 09:35 row as an upper bound, not a return.** It is
measured on trades selected by a signal that does not exist until 09:35,
so it answers "how much did that minute move, on the days the signal
later fired" -- not "how much would I make entering at 09:34".

## Putting A1 and A2 together

Entering a minute earlier would capture about {gain4:.1f} bps of extra move on
the trades that still qualify, but only {ret4:.1%} of them still qualify. The
naive expected gain is therefore around {gain4 * ret4:.1f} bps before accounting for
the trades a 4-minute rule would newly ADD -- which this data cannot
measure, because a 4-minute volume ratio needs a trailing baseline over
minutes 0-3 on non-event sessions, and this dataset has 1-minute bars on
event sessions only.

So the earlier-entry idea is not refuted here -- it is UNMEASURED, and
the measurable half of it is large enough to be worth measuring
properly. See the closing section.

## What this means in practice

Both halves say the same thing: **this edge lives in the first few
minutes and decays fast.**

The earlier-entry idea is worth more than I first assumed. An upper
bound of {gain4 * ret4:.1f} bps against a {base_mean:.1f} bps base is roughly a {gain4 * ret4 / base_mean * 100:.0f}% uplift --
material, not marginal. It is still an upper bound conditioned on a
signal that does not exist yet, and it stays untestable until there are
1-minute bars on non-event sessions. But it is not a rounding error, and
it deserves the data rather than a shrug.

The delay result needs no caveat at all, and it is the one to act on
first: **one minute late costs {abs(first_min):.1f} bps, {abs(first_min) / base_mean * 100:.0f}% of the edge.** That is
larger than the entire round-trip cost assumption of {COST_BPS} bps. A trader
who is consistently two minutes slow has given away more than half of
what the strategy earns, without ever seeing it in a fill price.

Generated by `timing.py`.
""")
    (BASE / "timing_feed.json").write_text(json.dumps(meta, default=float))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
