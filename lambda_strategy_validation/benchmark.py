"""
benchmark.py -- the post-earnings T+1 continuation strategy against
buy-and-hold.

COHORT (identical to EFFECTIVENESS/DISTSHIFT, built by
regime_sizing.build_cohort so it cannot drift):
  post-earnings T+1, non-zero gap, High Volume (c1_volume > 1.5x the
  trailing 20-session same-slot mean), Continuation = first 5-minute
  candle closes with the gap and body/range > 0.10, entry at the open of
  the 09:35 bar, corrected universe screen (screen_v2), prior-session
  ATR(14), 6.6 bps round trip.

  Two exits: 10:35 unconditional, and an intrabar ATR -1.0 stop.

THREE DECISIONS THAT DRIVE EVERY NUMBER BELOW

1 DIRECTION. The strategy is short on gap-down continuations, so
  "buy-and-hold the same stock" and "hold the strategy's position
  longer" are different questions. Both are reported: LONG-ONLY answers
  "should I just have bought it", SIGNED answers "is one hour the right
  holding period".

2 CAPITAL. The strategy holds a position for one hour on days a signal
  fires and cash otherwise, so a daily return series is built by
  equal-weighting that day's signals and assigning zero to every other
  session. That is the honest series for a sleeve that cannot be
  levered: it charges the strategy for the days it sits idle.

3 CASH YIELD. The base case pays nothing on idle cash and uses rf = 0
  in the Sharpe ratio, which is the conservative choice for a strategy
  deployed ~1% of the time -- a realistic cash rate would ADD to the
  strategy and to every blend, and subtract nothing. The size of that
  omission is quantified rather than waved at.

Run: python3 lambda_strategy_validation/benchmark.py
"""

from __future__ import annotations

import glob
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from effectiveness import scan_with_exit
from regime_sizing import build_cohort
from stops import COST_BPS, EXIT_MIN, OUT_DIR, log

BASE = Path("/home/user/lambda_data")
HERE = Path(__file__).resolve().parent
FEED = BASE / "benchmark_feed.json"
REPORT = HERE / "BENCHMARK_REPORT.md"

START, END = "2015-01-01", "2025-12-31"
HOLDS = [(1, "1 day"), (5, "5 days"), (20, "20 days"), (60, "60 days (~1 quarter)")]
TRADING_DAYS = 252
BLENDS = [(0.80, 0.20), (0.70, 0.30)]
OVERLAY_W = 0.25


# ---------------------------------------------------------------- returns

def spy_daily() -> pd.Series:
    d = pd.read_parquet(BASE / "derived" / "SPY.parquet", columns=["date", "close"])
    d = d[(d.date >= START) & (d.date <= END)].sort_values("date")
    return d.set_index("date")["close"].pct_change().dropna()


MAXH = max(n for n, _ in HOLDS)


def forward_holds(df: pd.DataFrame, entry: np.ndarray):
    """Closes for the MAXH sessions from entry, and the hold ladder.

    N = 1 means the close of the entry session itself, so the ladder
    starts where the strategy's own day ends rather than skipping it.
    The full close matrix is kept so the basket portfolios can be run as
    genuinely overlapping positions rather than approximated.
    """
    px = np.full((len(df), MAXH), np.nan)
    for tkr, idx in df.groupby("ticker").groups.items():
        p = BASE / "derived" / f"{tkr}.parquet"
        if not p.exists():
            continue
        s = pd.read_parquet(p, columns=["date", "close"]).sort_values("date")
        dates, closes = s["date"].to_numpy(), s["close"].to_numpy(float)
        pos = np.searchsorted(dates, df.loc[idx, "date"].to_numpy())
        rows = df.index.get_indexer(idx)
        for k in range(MAXH):
            tgt = pos + k
            ok = tgt < len(closes)
            px[rows[ok], k] = closes[tgt[ok]]
    R = pd.DataFrame({f"h{n}": px[:, n - 1] / entry - 1.0 for n, _ in HOLDS})
    return R, px


def spy_window(dates: pd.Series, spy_close: pd.Series) -> pd.DataFrame:
    """SPY's return over the identical calendar window, per trade."""
    idx = spy_close.index.to_numpy()
    vals = spy_close.to_numpy(float)
    pos = np.searchsorted(idx, dates.to_numpy())
    base = np.clip(pos - 1, 0, len(vals) - 1)      # prior close, so an
    out = {}                                        # N=1 hold is one session
    for n, _ in HOLDS:
        tgt = np.clip(pos + n - 1, 0, len(vals) - 1)
        out[f"spy{n}"] = vals[tgt] / vals[base] - 1.0
    return pd.DataFrame(out)


def basket_curve(E: pd.DataFrame, px: np.ndarray, entry: np.ndarray,
                 n: int, cal: pd.DatetimeIndex) -> pd.Series:
    """Equal-weight long basket, positions genuinely overlapping.

    Each trade is one position opened at the 09:35 entry price and closed
    at the Nth session close. On every session the portfolio return is
    the mean across whatever positions are open, so days with many
    concurrent names are diversified and days with none earn zero.
    """
    day_ret = np.full((len(E), n), np.nan)
    day_ret[:, 0] = px[:, 0] / entry - 1.0 - COST_BPS / 1e4
    for k in range(1, n):
        day_ret[:, k] = px[:, k] / px[:, k - 1] - 1.0
    ipos = np.searchsorted(cal.to_numpy(), E["date"].to_numpy())
    tot = np.zeros(len(cal))
    cnt = np.zeros(len(cal))
    for k in range(n):
        col = day_ret[:, k]
        tgt = ipos + k
        ok = (tgt < len(cal)) & ~np.isnan(col)
        np.add.at(tot, tgt[ok], col[ok])
        np.add.at(cnt, tgt[ok], 1.0)
    return pd.Series(np.where(cnt > 0, tot / np.maximum(cnt, 1), 0.0), index=cal)


# ---------------------------------------------------------------- metrics

def curve_stats(r: pd.Series, deployed: float | None = None) -> dict:
    eq = (1.0 + r).cumprod()
    yrs = len(r) / TRADING_DAYS
    cagr = eq.iloc[-1] ** (1.0 / yrs) - 1.0
    vol = r.std() * np.sqrt(TRADING_DAYS)
    dd = (eq / eq.cummax() - 1.0).min()
    return {"total_return": eq.iloc[-1] - 1.0, "cagr": cagr,
            "ann_vol": vol, "sharpe": cagr / vol if vol else np.nan,
            "max_dd": dd, "calmar": cagr / abs(dd) if dd else np.nan,
            "best_day": r.max(), "worst_day": r.min(),
            "pct_days_deployed": deployed}


def md(df: pd.DataFrame, pct=(), num=()) -> str:
    x = df.copy()
    for c in pct:
        if c in x:
            x[c] = x[c].map(lambda v: "" if pd.isna(v) else f"{v*100:,.2f}%")
    for c in num:
        if c in x:
            x[c] = x[c].map(lambda v: "" if pd.isna(v) else f"{v:,.2f}")
    head = "| " + " | ".join(x.columns) + " |"
    rule = "|" + "|".join("---" for _ in x.columns) + "|"
    body = ["| " + " | ".join(str(v) for v in r) + " |"
            for r in x.itertuples(index=False)]
    return "\n".join([head, rule, *body])


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    C = build_cohort()
    df, sign, entry, atr = C["df"], C["sign"], C["entry"], C["atr"]
    opens, adverse, close_exit = C["opens"], C["adverse"], C["close_exit"]
    r_bps, scr = C["r_bps"], C["scr"]

    stop_pnl, stopped, _ = scan_with_exit(sign, entry, opens, adverse,
                                          close_exit, -1.0 * atr)
    s_bps = stop_pnl / entry * 1e4

    keep = scr & (df["date"] >= START).to_numpy() & (df["date"] <= END).to_numpy()
    log(f"screened cohort in window: {keep.sum():,} of {len(df):,}")

    E = df.loc[keep, ["ticker", "date"]].reset_index(drop=True)
    E["sign"] = sign[keep]
    E["net_nostop"] = r_bps[keep] / 1e4 - COST_BPS / 1e4
    E["net_stop"] = s_bps[keep] / 1e4 - COST_BPS / 1e4
    E["stopped"] = stopped[keep]
    ent = entry[keep]
    F, px = forward_holds(E, ent)
    spy_px = pd.read_parquet(BASE / "derived" / "SPY.parquet",
                             columns=["date", "close"]).sort_values("date")
    spy_px = spy_px.set_index("date")["close"]
    E = pd.concat([E, F, spy_window(E["date"], spy_px)], axis=1)

    # ---- A. per-trade ladder
    rows = [{"exit": "STRATEGY 1 hour, no stop", "n": len(E),
             "mean_net": E.net_nostop.mean(), "median": E.net_nostop.median(),
             "win_rate": float((E.net_nostop > 0).mean()), "std": E.net_nostop.std()},
            {"exit": "STRATEGY 1 hour, ATR -1.0 stop", "n": len(E),
             "mean_net": E.net_stop.mean(), "median": E.net_stop.median(),
             "win_rate": float((E.net_stop > 0).mean()), "std": E.net_stop.std()}]
    for n, lab in HOLDS:
        for mode, signed in (("LONG-ONLY", False), ("SIGNED (strategy direction)", True)):
            v = E[f"h{n}"] * (E["sign"] if signed else 1.0) - COST_BPS / 1e4
            b = E[f"spy{n}"] * (E["sign"] if signed else 1.0)
            m = v.notna() & b.notna()
            rows.append({"exit": f"hold to close, {lab} -- {mode}", "n": int(m.sum()),
                         "mean_net": v[m].mean(), "median": v[m].median(),
                         "win_rate": float((v[m] > 0).mean()), "std": v[m].std(),
                         "spy_same_window": b[m].mean(),
                         "excess_vs_spy": v[m].mean() - b[m].mean()})
    ladder = pd.DataFrame(rows)

    # ---- B/C. portfolio
    spy = spy_daily()
    cal = spy.index
    daily_ns = E.groupby("date")["net_nostop"].mean().reindex(cal).fillna(0.0)
    daily_st = E.groupby("date")["net_stop"].mean().reindex(cal).fillna(0.0)
    dep = float((E.groupby("date").size().reindex(cal).fillna(0) > 0).mean())

    basket = {lab: basket_curve(E, px, ent, n, cal) for n, lab in HOLDS[:2]}

    curves = {
        "Strategy only, no stop": daily_ns,
        "Strategy only, ATR -1.0 stop": daily_st,
        "SPY buy-and-hold": spy,
        f"Signal basket, long, {HOLDS[0][1]} hold": basket[HOLDS[0][1]],
        f"Signal basket, long, {HOLDS[1][1]} hold": basket[HOLDS[1][1]],
    }
    for ws, wr in BLENDS:
        curves[f"{int(ws*100)}% SPY + {int(wr*100)}% strategy (stop)"] = \
            ws * spy + wr * daily_st
    curves[f"100% SPY + {int(OVERLAY_W*100)}% strategy overlay (stop)"] = \
        spy + OVERLAY_W * daily_st

    stats = []
    for k, v in curves.items():
        d = dep if k.startswith("Strategy only") else None
        stats.append({"portfolio": k, **curve_stats(v, d)})
    P = pd.DataFrame(stats)

    # Does the strategy add anything SPY does not already give you?
    # Regress the strategy's daily series on SPY's; alpha is what is
    # left after paying for whatever market exposure it carries.
    reg = []
    for k, v in (("no stop", daily_ns), ("ATR -1.0 stop", daily_st)):
        b, a = np.polyfit(spy.to_numpy(), v.to_numpy(), 1)
        reg.append({"strategy": k, "beta_to_spy": b,
                    "alpha_ann": a * TRADING_DAYS,
                    "corr_to_spy": float(np.corrcoef(spy, v)[0, 1]),
                    "up_day_mean": float(v[spy > 0].mean()),
                    "down_day_mean": float(v[spy < 0].mean())})
    REG = pd.DataFrame(reg)

    # Cost sensitivity. A flat 6.6 bps is the most exposed assumption in
    # the whole comparison, so show where the edge actually dies rather
    # than only reporting the base case.
    gross = E["net_nostop"] + COST_BPS / 1e4
    cost_rows = []
    for c in (6.6, 10.0, 15.0, 25.0, 35.0):
        v = gross - c / 1e4
        dv = v.groupby(E["date"]).mean().reindex(cal).fillna(0.0)
        cost_rows.append({"cost_bps": c, "mean_net_bps": v.mean() * 1e4,
                          "win_rate": float((v > 0).mean()),
                          "cagr": curve_stats(dv)["cagr"]})
    COST = pd.DataFrame(cost_rows)

    # Concurrency: how many names share the sleeve on a deployed day.
    per_day = E.groupby("date").size()
    conc = {"mean": float(per_day.mean()), "median": float(per_day.median()),
            "pct_single_name": float((per_day == 1).mean()),
            "p90": float(per_day.quantile(0.90)), "max": int(per_day.max())}

    # Volatility measured only on days capital is actually at work.
    live = daily_ns[daily_ns != 0]
    live_st = daily_st[daily_st != 0]
    deployed_vol = {"no stop": float(live.std() * np.sqrt(TRADING_DAYS)),
                    "stop": float(live_st.std() * np.sqrt(TRADING_DAYS))}

    # Cash-yield sensitivity: what an idle-cash rate would add.
    cash_add = {f"{r:.0%}": r * (1 - dep * (1 / 6.5)) for r in (0.02, 0.04)}

    meta = {"n_trades": int(len(E)), "n_tickers": int(E.ticker.nunique()),
            "start": str(E.date.min().date()), "end": str(E.date.max().date()),
            "cost_bps": COST_BPS, "pct_days_with_signal": dep,
            "pct_time_deployed": dep / 6.5, "stop_rate": float(E.stopped.mean()),
            "cash_add": cash_add, "concurrency": conc,
            "deployed_vol": deployed_vol,
            "trading_days": int(len(cal))}
    REG.to_csv(OUT_DIR / "bench_reg.csv", index=False)
    COST.to_csv(OUT_DIR / "bench_cost.csv", index=False)
    ladder.to_csv(OUT_DIR / "bench_ladder.csv", index=False)
    P.to_csv(OUT_DIR / "bench_portfolio.csv", index=False)
    FEED.write_text(json.dumps({"meta": meta,
                                "ladder": json.loads(ladder.round(6).to_json(orient="records")),
                                "portfolio": json.loads(P.round(6).to_json(orient="records")),
                                "reg": json.loads(REG.round(6).to_json(orient="records")),
                                "cost": json.loads(COST.round(6).to_json(orient="records"))},
                               separators=(",", ":")))

    from benchmark_text import build  # noqa: E402
    REPORT.write_text(build(ladder, P, REG, COST, meta, E))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
