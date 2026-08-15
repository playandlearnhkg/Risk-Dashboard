"""
reconcile_research.py -- does the new engine reproduce the old numbers?

WHAT CANNOT BE CHECKED, AND WHY

A full end-to-end reproduction is impossible with the data on disk, and
saying so is more useful than producing a number that looks like a
match. The research kept 1-minute bars only in a +/-1 session window
around each event: three sessions per event, 90 minutes each, with a
median calendar gap of three days between sessions. The engine's two
core features need history that is simply not there:

    ATR(14)                14 consecutive prior SESSIONS of full-session
                           high/low. Available: 1, and only 90 minutes
                           of it.
    volume ratio           a 20-session trailing same-slot mean.
                           Available: 1 prior session.

Run the strategy on this and both come back NaN, so it emits zero
signals. That is the engine refusing to invent a baseline, which is
correct behaviour and useless for reconciliation.

WHAT CAN BE CHECKED, EXACTLY

The EXECUTION path. Given the same bars and the same decision, does the
engine fill where the research filled, exit where it exited, and compute
the same return? Signals are built directly from the research cohort --
its direction and its ATR -- and everything after that is the engine's:
the 09:35 entry price is looked up from bars by the engine's own
timestamp resolution, the exit is `simulate_exit`, and the return is the
Portfolio's arithmetic.

That validates entry fill, exit fill, return arithmetic, MAE/MFE and the
DST-aware timestamp mapping against 4,270 known-good trades. It does NOT
validate ATR, the volume ratio, the candle classification or the
universe filter, because the inputs to those no longer exist. Those are
listed as unverified rather than quietly assumed.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.portfolio import simulate_exit          # noqa: E402
from engine.strategy_base import Signal             # noqa: E402

NY = ZoneInfo("America/New_York")
INTRA = Path("/home/user/lambda_data/intraday90")
EXTRACT = ROOT.parent / "lambda_strategy_validation" / "data" / "postearnings_extract.csv"
ENTRY_MIN = 5
# The engine exits at the OPEN of the 10:35 bar, symmetric with its
# entry. The research exited at the CLOSE of the 10:34 bar (its
# EXIT_MIN = 64). Both are the instant 10:35:00; they are different
# prints. Both are computed below, because the difference is a
# convention choice worth seeing rather than a bug worth hiding.
EXIT_MIN_ENGINE = 65
EXIT_MIN_RESEARCH = 64
COST_BPS = 6.6


def to_engine_bars(raw: pd.DataFrame) -> pd.DataFrame:
    """minute-index bars -> the engine's UTC contract.

    Minute 0 is 09:30 New York. Building the timestamp in exchange-local
    time and converting exercises the same DST path the loader uses, so
    a timezone regression would show up here as a missing bar.
    """
    ts = [pd.Timestamp(dt.datetime.combine(d.date(), dt.time(9, 30), tzinfo=NY)
                       + dt.timedelta(minutes=int(m))).tz_convert("UTC")
          for d, m in zip(raw["date"], raw["minute"])]
    out = raw[["open", "high", "low", "close", "volume"]].astype(float).copy()
    out.index = pd.DatetimeIndex(ts, name="ts")
    out["session_date"] = [d.date() for d in raw["date"]]
    out["minutes_from_open"] = raw["minute"].to_numpy()
    return out.sort_index()


def main(n_tickers: int = 60) -> int:
    ext = pd.read_csv(EXTRACT, parse_dates=["date"])
    core = ext[(ext.high_volume_flag == "Yes")
               & (ext.candle_class == "Continuation")].copy()
    core["sess"] = core["date"].dt.date

    avail = {p.stem for p in INTRA.glob("*.parquet")}
    tickers = [t for t in core["ticker"].value_counts().index if t in avail][:n_tickers]

    rows = []
    for tkr in tickers:
        raw = pd.read_parquet(INTRA / f"{tkr}.parquet")
        raw["date"] = pd.to_datetime(raw["date"])
        bars = to_engine_bars(raw)
        have = set(bars["session_date"])

        for _, r in core[core.ticker == tkr].iterrows():
            s = r["sess"]
            if s not in have:
                continue
            day = bars[bars["session_date"] == s]
            entry_ts = day.index[day["minutes_from_open"] == ENTRY_MIN]
            exit_ts = day.index[day["minutes_from_open"] == EXIT_MIN_ENGINE]
            res_ts = day.index[day["minutes_from_open"] == EXIT_MIN_RESEARCH]
            if not len(entry_ts) or not len(exit_ts) or not len(res_ts):
                continue

            direction = 1 if r["gap_direction"] == "Up" else -1
            atr = float(r["atr14_prev"])
            if not np.isfinite(atr) or atr <= 0:
                continue

            # Entry price comes from the BARS via the engine's timestamp,
            # not from the extract -- that is the thing being tested.
            px = float(bars.loc[entry_ts[0], "open"])
            sig = Signal(ticker=tkr, session=s, decision_ts=entry_ts[0],
                         direction=direction, entry_ts=entry_ts[0],
                         entry_price=px, risk_unit=atr,
                         planned_exit_ts=exit_ts[0])
            x_ts, x_px, reason, held, mae, mfe = simulate_exit(
                sig, bars, float("nan"))

            eng_bps = direction * (x_px - px) / px * 1e4
            # Same engine, research's exit print: isolates the convention.
            match_bps = direction * (
                float(bars.loc[res_ts[0], "close"]) - px) / px * 1e4
            rows.append({
                "ticker": tkr, "date": s, "side": "LONG" if direction > 0 else "SHORT",
                "engine_entry": px, "research_entry": float(r["entry_px_0935"]),
                "engine_exit": x_px, "exit_reason": reason,
                "engine_bps": eng_bps, "matched_bps": match_bps,
                "research_bps": float(r["ret_1hour_bps"]),
                "engine_mae_atr": mae, "research_mae_atr": float(r["mae_1h_atr"]),
                "atr14_prev": atr, "gap_atr": float(r["gap_atr"]),
                "vol_ratio_5min": float(r["vol_ratio_5min"]),
                "gap_pct": float(r["gap_pct"]),
            })

    d = pd.DataFrame(rows)
    if d.empty:
        print("no overlapping trades found")
        return 1

    d["entry_diff_bps"] = (d.engine_entry / d.research_entry - 1.0) * 1e4
    d["ret_diff_bps"] = d.engine_bps - d.research_bps
    d["matched_diff_bps"] = d.matched_bps - d.research_bps
    d["mae_diff"] = d.engine_mae_atr - d.research_mae_atr
    d.to_csv(ROOT / "results" / "reconciliation.csv", index=False)

    def band(x, tol):
        return float((x.abs() <= tol).mean())

    print(f"reconciled {len(d):,} trades across {d.ticker.nunique()} tickers, "
          f"{d.date.min()} .. {d.date.max()}\n")
    print("ENTRY PRICE  engine bar lookup vs research entry_px_0935")
    print(f"  exact (<0.01 bps)   {band(d.entry_diff_bps, 0.01):.2%}")
    print(f"  within 1 bp         {band(d.entry_diff_bps, 1.0):.2%}")
    print(f"  max abs diff        {d.entry_diff_bps.abs().max():.4f} bps\n")
    print("1-HOUR RETURN, MATCHED CONVENTION  (engine arithmetic, "
          "research's 10:34 close)")
    print(f"  exact (<0.01 bps)   {band(d.matched_diff_bps, 0.01):.2%}")
    print(f"  max abs diff        {d.matched_diff_bps.abs().max():.4f} bps")
    print(f"  mean matched        {d.matched_bps.mean():.3f} bps")
    print(f"  mean research       {d.research_bps.mean():.3f} bps\n")
    print("1-HOUR RETURN, ENGINE CONVENTION  (10:35 open, symmetric with entry)")
    print(f"  exact vs research   {band(d.ret_diff_bps, 0.01):.2%}")
    print(f"  max abs diff        {d.ret_diff_bps.abs().max():.4f} bps")
    print(f"  mean engine         {d.engine_bps.mean():.3f} bps")
    gap = d.engine_bps - d.matched_bps
    print(f"  convention gap      {gap.mean():+.3f} bps mean, "
          f"sd {gap.std():.2f}, max |{gap.abs().max():.1f}|\n")
    print("MAE (ATR)  engine excursions vs research mae_1h_atr")
    print(f"  within 0.001        {band(d.mae_diff, 0.001):.2%}")
    print(f"  max abs diff        {d.mae_diff.abs().max():.4f}\n")

    worst = d.reindex(d.ret_diff_bps.abs().sort_values(ascending=False).index)
    print("largest return disagreements")
    print(worst.head(5)[["ticker", "date", "side", "engine_bps",
                         "research_bps", "ret_diff_bps"]].round(3).to_string(index=False))

    print("\n\nSAMPLE TRADES FOR MANUAL CHECK")
    print("=" * 118)
    smp = d.sample(min(10, len(d)), random_state=5).sort_values("date")
    cols = ["ticker", "date", "side", "gap_pct", "gap_atr", "vol_ratio_5min",
            "atr14_prev", "engine_entry", "research_entry", "engine_exit",
            "engine_bps", "matched_bps", "research_bps"]
    print(smp[cols].round(4).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
