"""
make_followup_report.py — Render FOLLOWUP_REPORT.md from the horizon,
candle-pattern and market-filter tables, so the second report exists as
plain markdown rather than only as a published page.

Run: python3 lambda_strategy_validation/make_followup_report.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

BASE = Path("/home/user/lambda_data")
T = BASE / "tables"
OUT = Path(__file__).resolve().parent / "FOLLOWUP_REPORT.md"

PAT_ORDER = ["Strong Continuation+", "Moderate Continuation+",
             "Indecision0", "Early Reversal-"]


def md(df: pd.DataFrame, floatfmt: str = ".2f") -> str:
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_float_dtype(out[c]):
            out[c] = out[c].map(lambda v: "" if pd.isna(v) else format(v, floatfmt))
    return out.to_markdown(index=False) + "\n"


def main() -> None:
    grid = pd.read_csv(T / "horizon_grid.csv")
    bypat = pd.read_csv(T / "horizon_by_pattern.csv")
    mkt = pd.read_csv(T / "horizon_market_filter.csv")
    shapes = json.loads((BASE / "candle_shapes.json").read_text())

    L, A = [], None
    A = L.append
    A("# Lambda Follow-Up Report")
    A("")
    A("**Three questions: shorter holding periods, opening-candle patterns, and a "
      "tradeable market-agreement filter.**")
    A("")
    A("Sample: all 17,582 earnings T+1 sessions, 615 US large caps, 2015-2025, with "
      "1-minute bars from 09:30 to 11:00. All inference uses the date-clustered "
      "bootstrap; every trade is charged its own measured trailing Roll spread plus "
      "2 bps impact, on both legs.")
    A("")

    A("## 1. Does a shorter holding period help?")
    A("")
    A("**Verdict: no — every entry x exit cell is negative net of costs.**")
    A("")
    A("A shorter hold pays the same round-trip cost over a smaller slice of an "
      "already-small drift, so it is worse than holding to the close, not better. "
      "The specific horizon asked about, 09:45 -> 10:00, is -6.61 bps at p < 0.001.")
    A("")
    A(md(grid))

    A("## 2. What do the opening candle patterns look like?")
    A("")
    A("**Verdict: real discriminating power, but the pattern is a dependable veto "
      "and an unreliable trigger.**")
    A("")
    A("Each archetype below is the median of its three 5-minute candles, expressed "
      "in basis points from the session open and **oriented by gap direction** — a "
      "gap-down continuation and a gap-up continuation are flipped onto the same "
      "axis, so positive always means 'moving with the gap'.")
    A("")
    rows = []
    for pat in PAT_ORDER:
        p = next(x for x in shapes["patterns"] if x["pattern"] == pat)
        for i, c in enumerate(p["candles"], 1):
            rows.append({"pattern": pat, "candle": f"c{i} (09:{30+(i-1)*5:02d})",
                         "open": c["open"], "high": c["high"],
                         "low": c["low"], "close": c["close"]})
    A("Archetypal candle shapes (bps from session open, gap-oriented):")
    A("")
    A(md(pd.DataFrame(rows), ".1f"))
    meta = pd.DataFrame([{
        "pattern": p["pattern"], "n": p["n"], "share": p["share"],
        "median_abs_gap_bps": p["median_abs_gap_bps"],
        "full_session_continuation": p["continuation_rate_full_session"],
    } for p in shapes["patterns"]])
    A("Frequency and context:")
    A("")
    A(md(meta, ".3f"))
    A("Note: `full_session_continuation` is measured open-to-close and therefore "
      "*includes* the 09:30-09:45 window the pattern is built from. It is shown for "
      "context only. The tradeable numbers are the forward returns below, which "
      "start at 09:45 when the pattern completes.")
    A("")
    A("Forward performance by pattern, entering at 09:45:")
    A("")
    A(md(bypat))
    A("Only the negative side is significant. **Early Reversal-** is reliably bad at "
      "every horizon (-6.25 to -6.81 bps, p < 0.001 throughout). **Strong "
      "Continuation+** improves the longer it is held (-3.18 bps at 15 minutes "
      "rising to +12.38 bps at the close) but never reaches significance (best "
      "p = 0.15, n = 1,496).")
    A("")

    A("## 3. Market agreement — and a correction")
    A("")
    A("**Correction: Sigma's section-2C relative-beta filter is not tradeable, and "
      "the earlier result that it improved the edge (51.5% continuation, p = 0.008) "
      "is withdrawn.**")
    A("")
    A("The filter compares the stock's T+1 *open-to-close* return with SPY's and the "
      "sector's. That return is only known at 16:00, and 'continuation' is itself "
      "defined by the sign of that same return — so the filter conditions on the "
      "outcome it is being scored against. Splitting by whether SPY happened to "
      "agree with the gap that day shows how mechanical it is:")
    A("")
    A("| SPY agreed with gap? | Kept by filter | Excluded by filter |")
    A("|---|---|---|")
    A("| Yes | 80.7% continuation (n=6,421) | 0.6% continuation (n=2,321) |")
    A("| No | 22.0% continuation (n=6,372) | 98.0% continuation (n=2,226) |")
    A("")
    A("A filter that sorts outcomes into 0.6% and 98.0% buckets is reading the "
      "answer, not detecting a signal. The mild overall 'improvement' is only what "
      "survives after those two opposing effects nearly cancel.")
    A("")
    A("The tradeable rebuild uses only SPY's move from the open to the 09:45 entry — "
      "information actually on the screen at trade time — in both a raw and a "
      "beta-adjusted form:")
    A("")
    A(md(mkt))
    A("**Answer: the instinct is directionally right but not economically useful.** "
      "At a 15-minute hold, agreeing with SPY (-6.66 bps) and fighting it (-6.57 "
      "bps) are indistinguishable. Held to the close a genuine gap appears — "
      "agreeing -2.48 bps versus fighting -8.15 bps — so 'don't fight the tape' is "
      "mildly real over a full session. But the agreeing cohort's confidence "
      "interval still spans zero (p = 0.52): it reduces the loss, it does not create "
      "a profit. Beta-adjusting SPY's move changes nothing (-2.60 vs -2.48).")
    A("")
    A("## Bottom line")
    A("")
    A("None of the three refinements rescues the edge. Shorter horizons are worse; "
      "the candle pattern is only trustworthy as an avoid signal; and the market "
      "filter that appeared to help was measuring the outcome. The REJECT verdict in "
      "the main report stands.")
    A("")
    A("---")
    A("")
    A("_Reproducible from `lambda_strategy_validation/horizons.py`, "
      "`candle_shapes.py` and the CSVs in `lambda_data/tables/`._")

    OUT.write_text("\n".join(L))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
