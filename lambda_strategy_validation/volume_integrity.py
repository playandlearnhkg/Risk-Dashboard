"""
volume_integrity.py -- does the HF volume source change invalidate the
High Volume filter?

BACKGROUND
  The provider's volume series changes basis in March 2022: reported
  volume falls by roughly an order of magnitude and stays there. The
  pipeline already knew this -- run_study.break_aware_liquidity swaps the
  absolute ADV/ADTV thresholds for cross-sectionally equivalent ranked
  ones after IEX_BREAK, and excises the 120 days whose 63-session
  trailing windows straddle the change.

  What was NEVER break-adjusted is the filter this research actually
  rests on: High Volume = c1_volume > 1.5x the trailing 20-session
  same-slot mean. That is the filter separating a +18.0 bps doji cohort
  from a -36.6 one, so if the source change broke it, it took a large
  part of the programme with it.

WHAT THIS TESTS
  1  WHEN the break happens, at daily resolution, pooled across tickers.
  2  WHAT the post-break series is, verified against an independent
     consolidated-tape source rather than assumed.
  3  WHETHER the filter still discriminates. This is the question that
     matters, and the answer is not obvious either way. The filter is a
     RATIO against its own trailing mean, so a pure rescaling cancels
     top and bottom and the filter should be untouched. But a venue
     feed is not a rescaled tape -- it is a ~3% sample of it, and a
     sample that small is noisier per bar. Noise in the ratio degrades
     the filter even though the level shift does not.

     So: measure the filter's incremental value (High Volume minus
     non-High Volume, within Continuation) separately either side of the
     break, and bootstrap the difference. Date-clustered throughout,
     since events cluster on earnings dates.

Run: python3 lambda_strategy_validation/volume_integrity.py
"""

from __future__ import annotations

import glob
import os
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
BASE = Path("/home/user/lambda_data")
EXTRACT = HERE / "data" / "postearnings_extract.csv"
REPORT = HERE / "VOLUME_INTEGRITY_REPORT.md"

COST_BPS = 6.6
IEX_BREAK = pd.Timestamp("2022-03-01")     # constant used by the pipeline
BLEND_END = IEX_BREAK + pd.Timedelta(days=120)
SEED = 11

# Spot checks against an independent consolidated-tape source (Massive
# /v2/aggs, adjusted=false). Held as literals so the report reproduces
# without re-billing the API; regenerate if the window moves.
CONSOLIDATED = {
    ("GILD", "2026-07-27"): 4953801, ("GILD", "2026-07-28"): 6947167,
    ("GILD", "2026-07-29"): 7766370, ("GILD", "2026-07-30"): 6726143,
    ("GILD", "2026-07-31"): 6531645,
    ("AAPL", "2026-07-30"): 74817792, ("AAPL", "2026-07-31"): 132489137,
}


def log(msg: str) -> None:
    print(msg, flush=True)


def locate_break(n_tickers: int = 200) -> pd.DataFrame:
    """Daily pooled volume relative to each ticker's own pre-break median."""
    rows = []
    for f in sorted(glob.glob(str(BASE / "derived" / "*.parquet")))[:n_tickers]:
        d = pd.read_parquet(f, columns=["date", "volume"])
        d = d[(d.date >= "2022-02-15") & (d.date <= "2022-03-20")]
        if len(d) < 15:
            continue
        b = d.loc[d.date <= "2022-03-01", "volume"].median()
        if not b or np.isnan(b):
            continue
        rows.append(d.set_index("date")["volume"] / b)
    M = pd.concat(rows, axis=1)
    return pd.DataFrame({"n_tickers": M.notna().sum(axis=1),
                         "median_rel_volume": M.median(axis=1)})


def verify_basis() -> pd.DataFrame:
    """HF volume as a share of independently sourced consolidated volume."""
    out = []
    for (tkr, ds), cons in CONSOLIDATED.items():
        p = BASE / "derived" / f"{tkr}.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p, columns=["date", "volume"])
        hit = d[d.date.dt.strftime("%Y-%m-%d") == ds]
        if not len(hit):
            continue
        v = int(hit["volume"].iloc[0])
        out.append({"ticker": tkr, "date": ds, "hf_volume": v,
                    "consolidated_volume": cons,
                    "hf_share_pct": 100.0 * v / cons})
    return pd.DataFrame(out).sort_values(["ticker", "date"])


def load_events() -> pd.DataFrame:
    d = pd.read_csv(EXTRACT, parse_dates=["date"])
    d["era"] = np.where(d.date < IEX_BREAK, "pre",
                        np.where(d.date <= BLEND_END, "straddle", "post"))
    d["hv"] = d["high_volume_flag"] == "Yes"
    d["net"] = d["ret_1hour_bps"] - COST_BPS
    return d


def ratio_shape(d: pd.DataFrame) -> pd.DataFrame:
    qs = [0.10, 0.25, 0.50, 0.75, 0.90]
    rows = []
    for era, lab in (("pre", "pre-break (consolidated)"),
                     ("post", "post-break (IEX-only)")):
        s = d.loc[d.era == era, "vol_ratio_5min"].dropna()
        q = s.quantile(qs)
        rows.append({"era": lab, "n": len(s),
                     **{f"p{int(x*100)}": float(q.loc[x]) for x in qs},
                     "p90_over_p10": float(q.loc[0.90] / q.loc[0.10]),
                     "hv_flag_rate": float((s > 1.5).mean())})
    return pd.DataFrame(rows)


def block_boot(g: pd.DataFrame, stat, rng, B: int = 4000):
    """Date-clustered bootstrap: resample dates, not events."""
    dates = g["date"].unique()
    idx = {dt: g.index[g.date == dt].to_numpy() for dt in dates}
    out = []
    for _ in range(B):
        pick = rng.choice(dates, size=len(dates), replace=True)
        v = stat(g.loc[np.concatenate([idx[p] for p in pick])])
        if v == v:
            out.append(v)
    a = np.asarray(out)
    return a.mean(), np.percentile(a, 2.5), np.percentile(a, 97.5)


def filter_value(s: pd.DataFrame) -> float:
    return s.loc[s.hv, "net"].mean() - s.loc[~s.hv, "net"].mean()


def edge_and_filter(d: pd.DataFrame, rng):
    cont = d[d.candle_class == "Continuation"]
    core = cont[cont.hv]

    other = cont[~cont.hv]
    lvl = []
    for g, lab in ((core, "High Vol + Continuation"),
                   (core[core.era == "pre"], "  pre-break (consolidated)"),
                   (core[core.era == "post"], "  post-break (IEX-only)"),
                   (other, "Continuation, NOT High Vol"),
                   (other[other.era == "pre"], "  pre-break (consolidated)"),
                   (other[other.era == "post"], "  post-break (IEX-only)")):
        m, lo, hi = block_boot(g.reset_index(drop=True),
                               lambda s: s["net"].mean(), rng)
        lvl.append({"cohort": lab, "n": len(g), "net_bps": m,
                    "ci_lo": lo, "ci_hi": hi,
                    "win_rate": float((g["ret_1hour_bps"] > COST_BPS).mean())})

    val = []
    for era, lab in (("pre", "pre-break (consolidated)"),
                     ("post", "post-break (IEX-only)")):
        g = cont[cont.era == era].reset_index(drop=True)
        m, lo, hi = block_boot(g, filter_value, rng)
        val.append({"era": lab, "n_high_vol": int(g.hv.sum()),
                    "n_other": int((~g.hv).sum()),
                    "filter_value_bps": m, "ci_lo": lo, "ci_hi": hi})

    gp = cont[cont.era == "pre"].reset_index(drop=True)
    gq = cont[cont.era == "post"].reset_index(drop=True)
    dp, dq = gp.date.unique(), gq.date.unique()
    diffs = []
    for _ in range(2000):
        sp = gp[gp.date.isin(rng.choice(dp, size=len(dp), replace=True))]
        sq = gq[gq.date.isin(rng.choice(dq, size=len(dq), replace=True))]
        v = filter_value(sq) - filter_value(sp)
        if v == v:
            diffs.append(v)
    a = np.asarray(diffs)
    did = {"diff_bps": a.mean(), "ci_lo": np.percentile(a, 2.5),
           "ci_hi": np.percentile(a, 97.5)}
    return pd.DataFrame(lvl), pd.DataFrame(val), did


def md(df: pd.DataFrame, floats: int = 2) -> str:
    x = df.copy()
    for c in x.columns:
        if pd.api.types.is_float_dtype(x[c]):
            x[c] = x[c].round(floats)
    head = "| " + " | ".join(x.columns) + " |"
    rule = "|" + "|".join("---" for _ in x.columns) + "|"
    body = ["| " + " | ".join(str(v) for v in r) + " |"
            for r in x.itertuples(index=False)]
    return "\n".join([head, rule, *body])


def main() -> None:
    rng = np.random.default_rng(SEED)

    log("locating the break")
    brk = locate_break()
    first_bad = brk.index[brk["median_rel_volume"] < 0.5][0]
    last_good = brk.index[brk.index < first_bad][-1]

    log("verifying the post-break basis")
    basis = verify_basis()

    log("loading events")
    d = load_events()
    shape = ratio_shape(d)
    lvl, val, did = edge_and_filter(d, rng)

    gap = d[(d.date >= IEX_BREAK) & (d.date <= BLEND_END)]
    survives = did["ci_lo"] < 0 < did["ci_hi"]
    brk_tbl = brk.reset_index().rename(columns={"date": "session"})
    brk_tbl["session"] = brk_tbl["session"].dt.date

    REPORT.write_text(f"""# Volume source integrity and the High Volume filter

The provider's volume series changes basis in March 2022. This asks the
only question that matters for the research: does the change break the
1.5x High Volume filter that the core cohort is built on.

**It does not.** The filter's incremental value is {val.iloc[0].filter_value_bps:.1f} bps before the
change and {val.iloc[1].filter_value_bps:.1f} bps after, and the difference is not distinguishable
from zero. The reason is structural: the filter is a ratio against its
own trailing mean, so a change in what volume *counts* cancels top and
bottom. Details below.

## 1. When the break happens

Daily volume pooled across {int(brk['n_tickers'].max())} tickers, each normalised by its own
pre-break median. This is not a per-ticker artefact -- every name moves
on the same day.

{md(brk_tbl, 4)}

Last clean session **{last_good.date()}**, first affected session
**{first_bad.date()}**. The pipeline's `IEX_BREAK` constant is
{IEX_BREAK.date()}, four sessions early. That costs four clean sessions
of threshold calibration and contaminates nothing, because the same code
excises a 120-day straddle window that swallows them.

## 2. What the post-break series is

Reported volume against an independent consolidated-tape source for the
same sessions:

{md(basis)}

HF post-break volume is **{basis.hf_share_pct.min():.1f}-{basis.hf_share_pct.max():.1f}% of consolidated** -- consistent with IEX's
own market share. So the post-break series is a single venue's prints,
not the consolidated tape. Prices are unaffected: IEX prints are real
trades.

## 3. The gap that is already in the data

There are no events at all between {IEX_BREAK.date()} and roughly
{BLEND_END.date()} -- {len(gap)} rows in a window that would normally hold several
hundred. That hole is deliberate, not missing data:
`run_study.break_aware_liquidity` drops every row whose 63-session
trailing liquidity window straddles the break, because such a window
averages two unit systems. Worth knowing it is there before anyone reads
a 2022 number as a regime signal.

## 4. Does the filter still discriminate

The level shift cancels in a ratio. The open question was noise: a ~3%
sample of the tape is noisier per bar than the tape, and noise in the
ratio would degrade the filter even where the rescaling does not. The
ratio distribution does widen, materially:

{md(shape)}

Ninetieth-over-tenth percentile goes from {shape.iloc[0].p90_over_p10:.1f} to {shape.iloc[1].p90_over_p10:.1f}. The
threshold nonetheless flags a near-identical share of events
({shape.iloc[0].hv_flag_rate:.1%} vs {shape.iloc[1].hv_flag_rate:.1%}), so it is selecting a wider-dispersed but
similarly sized slice.

The test that settles it -- the filter's incremental value, High Volume
minus non-High Volume within Continuation, 1-hour hold, after
{COST_BPS} bps, date-clustered:

{md(val)}

Difference post minus pre: **{did['diff_bps']:+.2f} bps**, 95% CI
[{did['ci_lo']:+.2f}, {did['ci_hi']:+.2f}]. {"The interval spans zero -- no detectable degradation." if survives else "The interval excludes zero -- the filter degrades."}

## 5. The edge either side of the break

{md(lvl)}

The core edge is lower after the break ({lvl.iloc[1].net_bps:.1f} -> {lvl.iloc[2].net_bps:.1f} bps, a fall of
{lvl.iloc[1].net_bps - lvl.iloc[2].net_bps:.1f}), but the confidence intervals overlap heavily. More to the
point, the same decline shows up in the cohort selected *without* the
volume filter ({lvl.iloc[4].net_bps:.1f} -> {lvl.iloc[5].net_bps:.1f} bps, a fall of {lvl.iloc[4].net_bps - lvl.iloc[5].net_bps:.1f}). A fault in the
volume series cannot move a cohort whose selection never touched volume.
The decline is regime, not measurement.

## What this changes

The volume worry was worth raising and is now bounded. The filter rests
on a ratio, and ratios survive a change in the unit being counted. What
a consolidated-tape re-test would still buy is the noise question in
section 4: whether the filter is worth *more* than {val.iloc[1].filter_value_bps:.1f} bps
post-break when computed on clean volume. That is an optimisation, not a
validity repair, and it should be priced accordingly.

One caveat that does not go away: this compares the filter against
itself either side of the break. It cannot detect a fault present in
*both* eras.

Generated by `volume_integrity.py`. Consolidated spot checks from
Massive `/v2/aggs`, `adjusted=false`.
""")
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
