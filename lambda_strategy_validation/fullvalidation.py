"""
fullvalidation.py -- a capitalised, auditable backtest of the
post-earnings T+1 continuation strategy.

Every earlier report in this programme measured the edge in basis points
per trade. This one puts $1,000,000 behind it and asks what actually
happens to the account, which introduces three things bps cannot show:
position sizing, a cap on concurrent positions, and a leverage limit.

COHORT (unchanged, built by regime_sizing.build_cohort so it cannot drift)
  post-earnings T+1, non-zero gap, High Volume (c1_volume > 1.5x the
  trailing 20-session same-slot mean), Continuation = first 5-minute
  candle closes with the gap and body/range > 0.10, entry at the open of
  the 09:35 bar, exit 10:35, corrected universe screen (screen_v2),
  prior-session ATR(14).

DECISIONS THAT A READER MUST SEE, BECAUSE EACH ONE MOVES THE ANSWER

1 WHICH SIGNALS GET TAKEN when a day produces more than the concurrency
  limit. Any rule that peeks at outcomes would flatter the result, so
  selection is by volume ratio, highest first -- a quantity fully known
  at 09:35. A random-selection variant is reported alongside so the
  reader can see how much of the result is that choice.

2 WHAT "RISK" MEANS for fixed-fractional sizing. Shares = risk dollars /
  1.0 ATR. For the stopped version that is a real stop distance. For the
  UNSTOPPED version there is no stop, so 1 ATR is a risk PROXY, not a
  loss limit -- an unstopped trade can and does lose more than the
  nominal risk budget. Sizing is kept identical across the two so the
  exit rule is the only thing that differs.

3 THE LEVERAGE CAP BINDS, OFTEN. At 1% risk and a typical 2-3% ATR, one
  position already wants ~40% of equity, so 1x gross forces pro-rata
  scaling on busy days. That is reported rather than hidden, because it
  means "1% risk" does not deliver 1% risk once the book is full.

Idle cash earns 0%, which understates every configuration equally.

Run: python3 lambda_strategy_validation/fullvalidation.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from effectiveness import excursions, scan_with_exit
from regime_sizing import build_cohort, wins_kurt
from stops import COST_BPS, EXIT_MIN, OUT_DIR, log

BASE = Path("/home/user/lambda_data")
HERE = Path(__file__).resolve().parent
FEED = BASE / "fullval_feed.json"
REPORT = HERE / "FULLVAL_REPORT.md"
TRADES_CSV = HERE / "data" / "fullval_trades.csv"

CAPITAL = 1_000_000.0
START, END = "2015-01-01", "2025-12-31"
TRADING_DAYS = 252
COSTS = [6.6, 10.0, 15.0, 25.0]
MAXPOS = [3, 5, 8]
SIZINGS = [("frac0.5", "Fixed fractional, 0.5% risk"),
           ("frac1.0", "Fixed fractional, 1.0% risk"),
           ("notional", "Fixed notional, equity / max positions")]
EXITS = [("nostop", "1 hour, no stop"), ("stop", "1 hour, ATR -1.0 stop")]
BASE_CFG = ("frac0.5", 5, 6.6)


# ------------------------------------------------------------------ engine

def simulate(T: pd.DataFrame, cal: pd.DatetimeIndex, sizing: str, maxpos: int,
             cost_bps: float, retcol: str, rank: str = "vol") -> dict:
    """Day-by-day capital simulation. Positions are intraday, so the book
    opens and closes within each session and equity compounds daily."""
    eq = CAPITAL
    equity = np.empty(len(cal))
    gross_used = np.zeros(len(cal))
    n_open = np.zeros(len(cal), dtype=int)
    taken_idx: list[int] = []
    taken_pnl: list[float] = []
    taken_notional: list[float] = []

    by_day = {d: g for d, g in T.groupby("date")}
    rng = np.random.default_rng(7)

    for i, day in enumerate(cal):
        g = by_day.get(day)
        if g is not None and len(g):
            if rank == "vol":
                g = g.sort_values("vol_ratio", ascending=False)
            else:
                g = g.iloc[rng.permutation(len(g))]
            g = g.head(maxpos)

            if sizing == "notional":
                notional = np.full(len(g), eq / maxpos)
            else:
                risk_pct = 0.005 if sizing == "frac0.5" else 0.010
                shares = (risk_pct * eq) / g["atr"].to_numpy()
                notional = shares * g["entry_px"].to_numpy()

            tot = notional.sum()
            if tot > eq:                      # 1x gross cap, pro-rata
                notional = notional * (eq / tot)
                tot = eq

            pnl = notional * (g[retcol].to_numpy() - cost_bps) / 1e4
            eq += pnl.sum()
            gross_used[i] = tot / (eq - pnl.sum()) if eq - pnl.sum() else 0.0
            n_open[i] = len(g)
            taken_idx.extend(g.index.tolist())
            taken_pnl.extend(pnl.tolist())
            taken_notional.extend(notional.tolist())
        equity[i] = eq

    E = pd.Series(equity, index=cal)
    r = E.pct_change().fillna(E.iloc[0] / CAPITAL - 1.0)
    dd = E / E.cummax() - 1.0
    yrs = len(cal) / TRADING_DAYS
    cagr = (E.iloc[-1] / CAPITAL) ** (1 / yrs) - 1.0
    vol = r.std() * np.sqrt(TRADING_DAYS)
    active = n_open > 0
    return {
        "equity": E, "ret": r, "dd": dd,
        "final": E.iloc[-1], "total_return": E.iloc[-1] / CAPITAL - 1.0,
        "cagr": cagr, "ann_vol": vol, "sharpe": cagr / vol if vol else np.nan,
        "max_dd": dd.min(), "calmar": cagr / abs(dd.min()) if dd.min() else np.nan,
        "n_trades": len(taken_idx),
        "pct_signals_taken": len(taken_idx) / len(T),
        "pct_days_active": float(active.mean()),
        "pct_time_in_market": float(active.mean()) / 6.5,
        "avg_gross_when_active": float(gross_used[active].mean()) if active.any() else 0.0,
        "avg_positions_when_active": float(n_open[active].mean()) if active.any() else 0.0,
        "taken_idx": taken_idx, "taken_pnl": taken_pnl,
        "taken_notional": taken_notional,
    }


# ----------------------------------------------------------------- metrics

def dist_pack(x: pd.Series, atr_ret: pd.Series) -> dict:
    """Distribution and tail metrics on a series of trade returns (bps)."""
    q = x.quantile([0.10, 0.25, 0.50, 0.75, 0.90])
    sk_w, ku_w = wins_kurt(x)
    big = atr_ret < -1.0
    return {
        "n": len(x), "mean_bps": x.mean(), "median_bps": q.loc[0.50],
        "std_bps": x.std(), "win_rate": float((x > 0).mean()),
        "p10": q.loc[0.10], "p25": q.loc[0.25], "p75": q.loc[0.75],
        "p90": q.loc[0.90],
        "skew_wins": sk_w, "exkurt_wins": ku_w,
        "skew_raw": float(x.skew()), "exkurt_raw": float(x.kurt()),
        "pct_loss_0.5atr": float((atr_ret < -0.5).mean()),
        "pct_loss_1atr": float(big.mean()),
        "avg_large_loss_bps": float(x[big].mean()) if big.any() else np.nan,
    }


def year_table(T: pd.DataFrame, sim: dict, cal, retcol: str,
               cost: float) -> pd.DataFrame:
    sub = T.loc[sim["taken_idx"]].copy()
    sub["net_bps"] = sub[retcol] - cost
    sub["net_atr"] = sub[retcol.replace("bps", "atr")] - sub["cost_atr"]
    E, dd = sim["equity"], sim["dd"]
    rows = []
    for yr, g in sub.groupby(sub["date"].dt.year):
        mask = cal.year == yr
        ey = E[mask]
        r = ey.pct_change().dropna()
        start = E[cal < ey.index[0]]
        base = start.iloc[-1] if len(start) else CAPITAL
        vol = r.std() * np.sqrt(TRADING_DAYS)
        ann = ey.iloc[-1] / base - 1.0
        d = dd[mask]
        rows.append({
            "year": yr, "net_return": ann, "max_dd": d.min(),
            "sharpe": (ann / vol) if vol else np.nan,
            "n_trades": len(g), "win_rate": float((g.net_bps > 0).mean()),
            "avg_trade_bps": g.net_bps.mean(),
            "skew_wins": wins_kurt(g.net_bps)[0],
            "exkurt_wins": wins_kurt(g.net_bps)[1],
            "pct_loss_1atr": float((g.net_atr < -1.0).mean()),
        })
    return pd.DataFrame(rows)


def md(df: pd.DataFrame, pct=(), num=(), num3=()) -> str:
    x = df.copy()
    for c in pct:
        if c in x:
            x[c] = x[c].map(lambda v: "" if pd.isna(v) else f"{v*100:,.2f}%")
    for c in num:
        if c in x:
            x[c] = x[c].map(lambda v: "" if pd.isna(v) else f"{v:,.2f}")
    for c in num3:
        if c in x:
            x[c] = x[c].map(lambda v: "" if pd.isna(v) else f"{v:,.3f}")
    head = "| " + " | ".join(x.columns) + " |"
    rule = "|" + "|".join("---" for _ in x.columns) + "|"
    body = ["| " + " | ".join(str(v) for v in r) + " |"
            for r in x.itertuples(index=False)]
    return "\n".join([head, rule, *body])


def plot_curves(sims: dict, meta: dict) -> None:
    """Equity on a log axis, drawdown beneath it, both exits together."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(2, 1, figsize=(11, 7), sharex=True,
                           gridspec_kw={"height_ratios": [2, 1]})
    colours = {"nostop": "#1f4e79", "stop": "#c0504d"}
    for k, lab in EXITS:
        s = sims[k]
        ax[0].plot(s["equity"].index, s["equity"], lw=1.3, color=colours[k],
                   label=f"{lab} -- ${s['final']/1e6:.2f}M, "
                         f"CAGR {s['cagr']*100:.1f}%, DD {s['max_dd']*100:.1f}%")
        ax[1].fill_between(s["dd"].index, s["dd"] * 100, 0, alpha=0.35,
                           color=colours[k], lw=0)
    ax[0].axhline(CAPITAL, color="grey", lw=0.8, ls="--")
    ax[0].set_yscale("log")
    ax[0].set_ylabel("Equity (USD, log)")
    ax[0].set_title(f"Post-earnings T+1 continuation -- ${CAPITAL/1e6:.0f}M, "
                    f"{meta['base_sizing']} risk, max {meta['base_maxpos']} "
                    f"concurrent, {meta['base_cost']} bps")
    ax[0].legend(loc="upper left", fontsize=9, frameon=False)
    ax[0].grid(alpha=0.25)
    ax[1].set_ylabel("Drawdown (%)")
    ax[1].grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(HERE / "data" / "fullval_equity.png", dpi=130)
    plt.close(fig)


# -------------------------------------------------------------------- main

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (HERE / "data").mkdir(parents=True, exist_ok=True)
    C = build_cohort()
    df, sign, entry, atr = C["df"], C["sign"], C["entry"], C["atr"]
    opens, adverse, close_exit = C["opens"], C["adverse"], C["close_exit"]
    highs, lows = C["highs"], C["lows"]
    r_bps, r_atr, scr = C["r_bps"], C["r_atr"], C["scr"]

    pnl_s, stopped, exit_s = scan_with_exit(sign, entry, opens, adverse,
                                            close_exit, -1.0 * atr)
    s_bps, s_atr = pnl_s / entry * 1e4, pnl_s / atr
    exit_ns = np.full(len(df), EXIT_MIN)
    mae_ns, mfe_ns = excursions(sign, entry, atr, highs, lows, exit_ns)
    mae_s, mfe_s = excursions(sign, entry, atr, highs, lows, exit_s)

    keep = scr & (df["date"] >= START).to_numpy() & (df["date"] <= END).to_numpy()
    log(f"screened cohort in window: {keep.sum():,}")

    T = pd.DataFrame({
        "date": df.loc[keep, "date"].to_numpy(),
        "ticker": df.loc[keep, "ticker"].to_numpy(),
        "side": np.where(sign[keep] > 0, "LONG", "SHORT"),
        "entry_px": entry[keep], "atr": atr[keep],
        "atr_pct": atr[keep] / entry[keep] * 100,
        "gap_pct": df.loc[keep, "gap"].to_numpy() * 100,
        "gap_atr": C["gap_atr"][keep], "vol_ratio": C["vr"][keep],
        "ret_nostop_bps": r_bps[keep], "ret_nostop_atr": r_atr[keep],
        "ret_stop_bps": s_bps[keep], "ret_stop_atr": s_atr[keep],
        "stopped": stopped[keep], "cost_atr": C["cost_atr"][keep],
        "mae_nostop_atr": mae_ns[keep], "mfe_nostop_atr": mfe_ns[keep],
        "mae_stop_atr": mae_s[keep], "mfe_stop_atr": mfe_s[keep],
    }).sort_values(["date", "ticker"]).reset_index(drop=True)
    T.insert(0, "trade_id", [f"T{i:05d}" for i in range(1, len(T) + 1)])
    T = T.set_index("trade_id", drop=False)

    cal = pd.DatetimeIndex(sorted(pd.read_parquet(
        BASE / "derived" / "SPY.parquet", columns=["date"])["date"]))
    cal = cal[(cal >= START) & (cal <= END)]

    sz0, mp0, ct0 = BASE_CFG
    sims = {k: simulate(T, cal, sz0, mp0, ct0, f"ret_{k}_bps") for k, _ in EXITS}

    # ---- grids
    grid = []
    for sz, szlab in SIZINGS:
        for mp in MAXPOS:
            for ek, elab in EXITS:
                s = simulate(T, cal, sz, mp, ct0, f"ret_{ek}_bps")
                grid.append({"sizing": szlab, "max_pos": mp, "exit": elab,
                             "final_equity": s["final"], "cagr": s["cagr"],
                             "ann_vol": s["ann_vol"], "sharpe": s["sharpe"],
                             "max_dd": s["max_dd"], "calmar": s["calmar"],
                             "n_trades": s["n_trades"],
                             "pct_signals_taken": s["pct_signals_taken"],
                             "avg_gross": s["avg_gross_when_active"]})
    G = pd.DataFrame(grid)

    cost_grid = []
    for c in COSTS:
        for ek, elab in EXITS:
            s = simulate(T, cal, sz0, mp0, c, f"ret_{ek}_bps")
            cost_grid.append({"cost_bps": c, "exit": elab,
                              "final_equity": s["final"], "cagr": s["cagr"],
                              "sharpe": s["sharpe"], "max_dd": s["max_dd"],
                              "calmar": s["calmar"]})
    CG = pd.DataFrame(cost_grid)

    rnd = {k: simulate(T, cal, sz0, mp0, ct0, f"ret_{k}_bps", rank="random")
           for k, _ in EXITS}

    # ---- per-year and distribution on the base config
    years = {k: year_table(T, sims[k], cal, f"ret_{k}_bps", ct0) for k, _ in EXITS}
    dists = {}
    for k, _ in EXITS:
        sub = T.loc[sims[k]["taken_idx"]]
        dists[k] = dist_pack(sub[f"ret_{k}_bps"] - ct0,
                             sub[f"ret_{k}_atr"] - sub["cost_atr"])
    ydist = []
    sub0 = T.loc[sims["stop"]["taken_idx"]].copy()
    for yr, g in sub0.groupby(sub0["date"].dt.year):
        ydist.append({"year": yr, **dist_pack(g["ret_stop_bps"] - ct0,
                                              g["ret_stop_atr"] - g["cost_atr"])})
    YD = pd.DataFrame(ydist)

    # ---- reality checks
    # A subset that starts late must be annualised over ITS OWN window,
    # not the full eleven years, or the flat stretch before its first
    # trade is charged against it as if it were a losing period.
    checks = []
    for lab, mask, cwin in (
            ("Full sample 2015-2025", T["date"].notna(), cal),
            ("2022-2025 only", T["date"] >= "2022-01-01", cal[cal >= "2022-01-01"]),
            ("2015-2019 only", T["date"] < "2020-01-01", cal[cal < "2020-01-01"]),
            ("LONG only", T["side"] == "LONG", cal),
            ("SHORT only", T["side"] == "SHORT", cal)):
        s = simulate(T[mask], cwin, sz0, mp0, ct0, "ret_stop_bps")
        sn = simulate(T[mask], cwin, sz0, mp0, ct0, "ret_nostop_bps")
        g = T[mask]
        checks.append({"subset": lab, "n_signals": int(mask.sum()),
                       "n_taken": s["n_trades"],
                       "cagr_stop": s["cagr"], "cagr_nostop": sn["cagr"],
                       "sharpe_stop": s["sharpe"], "max_dd_stop": s["max_dd"],
                       "mean_bps_stop": (g["ret_stop_bps"] - ct0).mean(),
                       "win_rate": float((g["ret_stop_bps"] - ct0 > 0).mean())})
    CK = pd.DataFrame(checks)

    # ---- trade ledger
    L = T.copy()
    for k, _ in EXITS:
        L[f"taken_{k}"] = L.index.isin(sims[k]["taken_idx"])
    pnl_map = dict(zip(sims["stop"]["taken_idx"], sims["stop"]["taken_pnl"]))
    notl_map = dict(zip(sims["stop"]["taken_idx"], sims["stop"]["taken_notional"]))
    L["pnl_usd_base"] = L.index.map(pnl_map)
    L["notional_usd_base"] = L.index.map(notl_map)
    L["net_stop_bps"] = L["ret_stop_bps"] - ct0
    L["net_nostop_bps"] = L["ret_nostop_bps"] - ct0
    L.to_csv(TRADES_CSV, index=False)
    log(f"wrote {TRADES_CSV} ({len(L):,} rows)")

    cols = ["trade_id", "date", "ticker", "side", "gap_pct", "gap_atr",
            "vol_ratio", "atr_pct", "net_stop_bps", "net_nostop_bps",
            "mae_stop_atr", "mfe_stop_atr", "stopped", "pnl_usd_base"]
    taken = L[L["taken_stop"]].copy()
    best = taken.nlargest(15, "net_stop_bps")[cols]
    worst = taken.nsmallest(15, "net_stop_bps")[cols]

    # Whipsaw accounting: a stop only helps if the price does not come
    # back. Split the stopped trades by whether the stop actually
    # improved the outcome versus letting the trade run to 10:35.
    tk = T.loc[sims["stop"]["taken_idx"]]
    wsub = tk[tk["stopped"]]
    diff = wsub["ret_stop_bps"] - wsub["ret_nostop_bps"]
    whip = {"n_stopped": int(len(wsub)),
            "stop_rate_taken": float(tk["stopped"].mean()),
            "pct_made_worse": float((diff < 0).mean()),
            "mean_damage_bps": float(diff[diff < 0].mean()),
            "mean_saving_bps": float(diff[diff >= 0].mean()),
            "net_effect_bps": float((tk["ret_stop_bps"] - tk["ret_nostop_bps"]).mean())}

    meta = {"capital": CAPITAL, "base_sizing": sz0, "base_maxpos": mp0,
            "whipsaw": whip,
            "base_cost": ct0, "n_signals": len(T),
            "n_tickers": int(T.ticker.nunique()),
            "start": str(T.date.min().date()), "end": str(T.date.max().date()),
            "sessions": len(cal),
            "long_share": float((T.side == "LONG").mean()),
            "stop_rate": float(T.stopped.mean()),
            "random_rank": {k: {"cagr": v["cagr"], "sharpe": v["sharpe"],
                                "max_dd": v["max_dd"]} for k, v in rnd.items()},
            "base": {k: {kk: v[kk] for kk in
                         ("final", "total_return", "cagr", "ann_vol", "sharpe",
                          "max_dd", "calmar", "n_trades", "pct_signals_taken",
                          "pct_days_active", "pct_time_in_market",
                          "avg_gross_when_active", "avg_positions_when_active")}
                     for k, v in sims.items()}}

    for name, obj in (("fullval_grid", G), ("fullval_cost", CG),
                      ("fullval_checks", CK), ("fullval_yeardist", YD),
                      ("fullval_year_stop", years["stop"]),
                      ("fullval_year_nostop", years["nostop"])):
        obj.to_csv(OUT_DIR / f"{name}.csv", index=False)
    for k, _ in EXITS:
        sims[k]["equity"].rename("equity").to_frame().assign(
            drawdown=sims[k]["dd"]).to_csv(OUT_DIR / f"fullval_curve_{k}.csv")
    FEED.write_text(json.dumps({"meta": meta, "dists": dists}, default=float,
                               separators=(",", ":")))

    plot_curves(sims, meta)

    from fullvalidation_text import build  # noqa: E402
    REPORT.write_text(build(meta, sims, years, dists, YD, G, CG, CK,
                            best, worst, cal))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
