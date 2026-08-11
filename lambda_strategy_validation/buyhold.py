"""
buyhold.py -- the same $1,000,000 in SPY instead.

FULLVAL_REPORT put a million dollars behind the strategy. This asks the
obvious next question on identical terms: same start date, same end
date, same calendar, same starting capital.

WHY A CAGR COMPARISON ALONE WOULD MISLEAD

The strategy runs at ~52% gross for one hour a day and sits in cash the
rest of the time, so its annualised volatility is about a third of
SPY's. Comparing raw CAGR rewards it for a risk level it never takes and
punishes it for the same reason. Three framings are therefore reported:

  RAW          what each actually returned on $1M
  RISK-MATCHED what the strategy would return scaled to SPY's volatility
               -- reported but flagged, because reaching that scale needs
               leverage the brief forbids
  BLENDED      the practical form: capital split between SPY and the
               strategy sleeve, plus an overlay variant funded by
               intraday buying power rather than by selling SPY

The blends are the only ones that a person could actually run at 1x.

Run: python3 lambda_strategy_validation/buyhold.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from fullvalidation import (BASE_CFG, CAPITAL, EXITS, TRADING_DAYS, md,
                            simulate)
from effectiveness import scan_with_exit
from regime_sizing import build_cohort
from stops import EXIT_MIN, OUT_DIR, log

BASE = Path("/home/user/lambda_data")
HERE = Path(__file__).resolve().parent
REPORT = HERE / "BUYHOLD_REPORT.md"
START, END = "2015-01-01", "2025-12-31"
BLENDS = [(0.90, 0.10), (0.80, 0.20), (0.70, 0.30), (0.50, 0.50)]
OVERLAY = 0.30


def stats(r: pd.Series, label: str) -> dict:
    eq = CAPITAL * (1.0 + r).cumprod()
    yrs = len(r) / TRADING_DAYS
    cagr = (eq.iloc[-1] / CAPITAL) ** (1 / yrs) - 1.0
    vol = r.std() * np.sqrt(TRADING_DAYS)
    dd = (eq / eq.cummax() - 1.0)
    return {"portfolio": label, "final_equity": eq.iloc[-1],
            "cagr": cagr, "ann_vol": vol,
            "sharpe": cagr / vol if vol else np.nan,
            "max_dd": dd.min(),
            "calmar": cagr / abs(dd.min()) if dd.min() else np.nan,
            "worst_day": r.min(), "worst_month": r.resample("ME").apply(
                lambda s: (1 + s).prod() - 1).min(),
            "_eq": eq, "_dd": dd, "_r": r}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    C = build_cohort()
    df, sign, entry, atr = C["df"], C["sign"], C["entry"], C["atr"]
    pnl_s, _, _ = scan_with_exit(sign, entry, C["opens"], C["adverse"],
                                 C["close_exit"], -1.0 * atr)
    keep = (C["scr"] & (df["date"] >= START).to_numpy()
            & (df["date"] <= END).to_numpy())
    T = pd.DataFrame({
        "date": df.loc[keep, "date"].to_numpy(),
        "ticker": df.loc[keep, "ticker"].to_numpy(),
        "entry_px": entry[keep], "atr": atr[keep],
        "vol_ratio": C["vr"][keep],
        "ret_nostop_bps": C["r_bps"][keep],
        "ret_stop_bps": pnl_s[keep] / entry[keep] * 1e4,
    }).sort_values(["date", "ticker"]).reset_index(drop=True)
    T.index = [f"T{i:05d}" for i in range(1, len(T) + 1)]

    spy = pd.read_parquet(BASE / "derived" / "SPY.parquet",
                          columns=["date", "close"]).sort_values("date")
    spy = spy[(spy.date >= START) & (spy.date <= END)].set_index("date")["close"]
    cal = pd.DatetimeIndex(spy.index)
    spy_r = spy.pct_change().fillna(0.0)

    sz0, mp0, ct0 = BASE_CFG
    sims = {k: simulate(T, cal, sz0, mp0, ct0, f"ret_{k}_bps") for k, _ in EXITS}
    strat = {k: v["equity"].pct_change().fillna(
        v["equity"].iloc[0] / CAPITAL - 1.0) for k, v in sims.items()}
    log(f"strategy vol {strat['nostop'].std()*np.sqrt(TRADING_DAYS):.4f}, "
        f"spy vol {spy_r.std()*np.sqrt(TRADING_DAYS):.4f}")

    rows = [stats(spy_r, "SPY buy-and-hold")]
    for k, lab in EXITS:
        rows.append(stats(strat[k], f"Strategy only, {lab}"))

    # Risk-matched: scale to SPY's volatility. Records the leverage it
    # would take, because the brief caps gross at 1x.
    scale = (spy_r.std() / strat["nostop"].std())
    rows.append(stats(strat["nostop"] * scale,
                      f"Strategy, no stop, scaled to SPY vol ({scale:.1f}x)"))

    for ws, wr in BLENDS:
        rows.append(stats(ws * spy_r + wr * strat["stop"],
                          f"{int(ws*100)}% SPY + {int(wr*100)}% strategy (stop)"))
    rows.append(stats(spy_r + OVERLAY * strat["stop"],
                      f"100% SPY + {int(OVERLAY*100)}% strategy overlay (stop)"))

    P = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")}
                      for r in rows])
    curves = {r["portfolio"]: r for r in rows}

    # Year by year, strategy vs SPY.
    yr = []
    for y in sorted(set(cal.year)):
        m = cal.year == y
        sp = (1 + spy_r[m]).prod() - 1
        sn = (1 + strat["nostop"][m]).prod() - 1
        ss = (1 + strat["stop"][m]).prod() - 1
        yr.append({"year": y, "SPY": sp, "strategy_nostop": sn,
                   "strategy_stop": ss, "diff_nostop": sn - sp,
                   "beat_spy": sn > sp})
    Y = pd.DataFrame(yr)

    # Rolling 12-month, to show how often each is under water.
    roll = {}
    for lab, r in (("SPY", spy_r), ("Strategy (no stop)", strat["nostop"]),
                   ("Strategy (stop)", strat["stop"])):
        rr = (1 + r).rolling(TRADING_DAYS).apply(np.prod, raw=True) - 1
        rr = rr.dropna()
        roll[lab] = {"pct_negative": float((rr < 0).mean()),
                     "worst": float(rr.min()), "best": float(rr.max()),
                     "median": float(rr.median())}
    R = pd.DataFrame(roll).T.reset_index().rename(columns={"index": "series"})

    plot(curves, spy_r, strat)

    meta = {"start": str(cal[0].date()), "end": str(cal[-1].date()),
            "sessions": len(cal), "capital": CAPITAL,
            "base": f"{sz0}, max {mp0}, {ct0} bps",
            "scale_to_spy_vol": float(scale),
            "beat_years": int(Y.beat_spy.sum()), "n_years": int(len(Y)),
            "corr": float(np.corrcoef(spy_r, strat["nostop"])[0, 1])}
    P.to_csv(OUT_DIR / "buyhold_portfolios.csv", index=False)
    Y.to_csv(OUT_DIR / "buyhold_years.csv", index=False)
    R.to_csv(OUT_DIR / "buyhold_rolling.csv", index=False)

    from buyhold_text import build  # noqa: E402
    REPORT.write_text(build(P, Y, R, meta))
    log(f"wrote {REPORT}")


def plot(curves: dict, spy_r, strat) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    show = ["SPY buy-and-hold", "Strategy only, 1 hour, no stop",
            "Strategy only, 1 hour, ATR -1.0 stop",
            "70% SPY + 30% strategy (stop)"]
    cols = ["#888888", "#1f4e79", "#c0504d", "#2e7d32"]
    fig, ax = plt.subplots(2, 1, figsize=(11, 7), sharex=True,
                           gridspec_kw={"height_ratios": [2, 1]})
    for lab, c in zip(show, cols):
        r = curves[lab]
        ax[0].plot(r["_eq"].index, r["_eq"], lw=1.3, color=c,
                   label=f"{lab} -- ${r['final_equity']/1e6:.2f}M, "
                         f"CAGR {r['cagr']*100:.1f}%, DD {r['max_dd']*100:.1f}%")
        ax[1].plot(r["_dd"].index, r["_dd"] * 100, lw=1.0, color=c, alpha=0.85)
    ax[0].axhline(CAPITAL, color="grey", lw=0.8, ls=":")
    ax[0].set_yscale("log")
    ax[0].set_ylabel("Equity (USD, log)")
    ax[0].set_title("$1M: strategy vs SPY buy-and-hold, same calendar")
    ax[0].legend(loc="upper left", fontsize=8.5, frameon=False)
    ax[0].grid(alpha=0.25)
    ax[1].set_ylabel("Drawdown (%)")
    ax[1].grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(HERE / "data" / "buyhold_equity.png", dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    main()
