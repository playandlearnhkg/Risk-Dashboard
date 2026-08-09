"""
effectiveness.py — full effectiveness comparison of the four risk
configurations across the three periods.

Cohort and configurations are identical to DISTSHIFT_REPORT.md and are
built by regime_sizing.build_cohort, so nothing can drift:

  post-earnings T+1, non-zero gap, High Volume (c1_volume > 1.5x the
  trailing 20-session same-slot mean), Continuation = first 5-minute
  candle closes with the gap and body/range > 0.10, entry at the open of
  the 09:35 bar, hold to 10:35, corrected universe screen, prior-session
  ATR(14), 6.6 bps.

  A  no stop, equal size
  B  ATR -1.0 stop (intrabar), equal size
  C  ATR -1.0 stop + three-tier sizing 1.25 / 1.0 / 0.5
  D  ATR -1.0 stop + fixed dollar risk, weight proportional to 1/ATR%

WHAT IS NEW RELATIVE TO THE LAST REPORT
  Profit factor, MAE and MFE, and the share of NET produced by the best
  decile of trades. Three notes on how these are computed, because each
  has a defensible alternative:

  * PROFIT FACTOR is computed on the realised, AFTER-COST contribution
    series -- the sum of profitable trades divided by the absolute sum
    of losing ones, where "profitable" means it cleared the 6.6 bps.
    That is the number a trader would reconcile against a P&L blotter.
    A pre-cost version is carried in the CSV for reference.

  * MAE AND MFE ARE MEASURED OVER THE ACTUAL HOLDING WINDOW, so a
    stopped trade's excursions are truncated at its stop minute rather
    than run to 10:35. Measuring them to a fixed hour would credit the
    stop with excursions it never experienced. Because sizing does not
    change WHEN a trade exits, the trade-level MAE and MFE are identical
    for B, C and D; the notional-weighted versions are not, and both are
    reported.

  * BEST-DECILE SHARE is the sum of the top 10% of contributions divided
    by the sum of all of them. Where total NET is small the ratio
    explodes, which is itself informative and is left unsmoothed.

Run: python3 lambda_strategy_validation/effectiveness.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from regime_sizing import PERIODS, build_cohort, wins_kurt  # noqa: E402
from stops import COST_BPS, ENTRY_MIN, EXIT_MIN, OUT_DIR, log  # noqa: E402

BASE = Path("/home/user/lambda_data")
FEED = BASE / "effectiveness_feed.json"
REPORT = Path(__file__).resolve().parent / "EFFECTIVENESS_REPORT.md"

CONFIGS = ["A — No stop, equal size",
           "B — ATR −1.0 stop, equal size",
           "C — ATR −1.0 stop + three-tier sizing",
           "D — ATR −1.0 stop + fixed dollar risk"]


def scan_with_exit(sign, entry, opens, adverse, close_exit, level):
    """Intrabar stop that also reports the minute each trade exited."""
    n = len(entry)
    sadv = sign[:, None] * (adverse - entry[:, None])
    sopen = sign[:, None] * (opens - entry[:, None])
    hit = np.zeros_like(sadv, dtype=bool)
    hit[:, ENTRY_MIN:] = sadv[:, ENTRY_MIN:] <= level[:, None]
    hit &= ~np.isnan(sadv)
    stopped = hit.any(axis=1)
    first = np.where(stopped, hit.argmax(axis=1), EXIT_MIN)

    pnl = np.where(stopped, np.nan, close_exit)
    idx = np.arange(n)
    if stopped.any():
        bo = sopen[idx[stopped], first[stopped]]
        lv = level[stopped]
        pnl[stopped] = np.where(np.isnan(bo), lv, np.minimum(bo, lv))
    return pnl, stopped, first


def excursions(sign, entry, atr, highs, lows, exit_idx):
    """MAE and MFE in ATR over each trade's own holding window."""
    n = len(entry)
    fav_src = np.where(sign[:, None] > 0, highs, lows)
    adv_src = np.where(sign[:, None] > 0, lows, highs)
    sfav = sign[:, None] * (fav_src - entry[:, None])
    sadv = sign[:, None] * (adv_src - entry[:, None])
    cols = np.arange(sadv.shape[1])
    live = (cols[None, :] >= ENTRY_MIN) & (cols[None, :] <= exit_idx[:, None])
    mae = np.full(n, np.nan)
    mfe = np.full(n, np.nan)
    with np.errstate(invalid="ignore"):
        a = np.where(live, sadv, np.nan)
        f = np.where(live, sfav, np.nan)
        allnan_a = np.all(np.isnan(a), axis=1)
        allnan_f = np.all(np.isnan(f), axis=1)
        mae[~allnan_a] = np.nanmin(a[~allnan_a], axis=1)
        mfe[~allnan_f] = np.nanmax(f[~allnan_f], axis=1)
    return mae / atr, mfe / atr


def pack(w, r_bps, r_atr, mae, mfe, label) -> dict:
    wm = w.mean()
    net = w * (r_bps - COST_BPS) / wm            # after-cost contribution
    gross = w * r_bps / wm
    q = np.quantile(net, [0.10, 0.25, 0.50, 0.75, 0.90])
    sk_w, ku_w = wins_kurt(net)

    pos, neg = net[net > 0], net[net < 0]
    pf = (pos.sum() / abs(neg.sum())) if neg.sum() else np.nan
    gpos, gneg = gross[gross > 0], gross[gross < 0]
    pf_gross = (gpos.sum() / abs(gneg.sum())) if gneg.sum() else np.nan

    k = int(len(pos))
    aw = pos.mean() if len(pos) else np.nan
    al = -neg.mean() if len(neg) else np.nan

    order = np.sort(net)[::-1]
    top = max(1, int(round(0.10 * len(net))))
    tot = net.sum()
    best_share = float(order[:top].sum() / tot) if tot != 0 else np.nan

    m05, m1, g1 = r_atr < -0.5, r_atr < -1.0, r_atr > 1.0
    tw = w.sum()
    rec = dict(label)
    rec.update({
        "n": len(r_bps), "mean_weight": float(wm),
        "eff_n": float(tw ** 2 / (w ** 2).sum()),
        "win_rate": k / len(net),
        "avg_win_bps": aw, "avg_loss_bps": al,
        "payoff_ratio": (aw / al) if al else np.nan,
        "net_bps": float(net.mean()), "median_bps": float(q[2]),
        "std_bps": float(net.std()),
        "sharpe_like": float(net.mean() / net.std()) if net.std() else np.nan,
        "p10": float(q[0]), "p25": float(q[1]),
        "p75": float(q[3]), "p90": float(q[4]),
        "skew_w": sk_w, "kurtosis_w": ku_w,
        "profit_factor": pf, "profit_factor_gross": pf_gross,
        "pct_loss_05atr": float(m05.mean()),
        "pct_loss_1atr": float(m1.mean()),
        "pct_gain_1atr": float(g1.mean()),
        "w_pct_loss_1atr": float(w[m1].sum() / tw),
        "w_pct_gain_1atr": float(w[g1].sum() / tw),
        "avg_large_loss_bps": float(net[m1].mean()) if m1.any() else np.nan,
        "mae_atr": float(np.nanmean(mae)),
        "mfe_atr": float(np.nanmean(mfe)),
        "w_mae_atr": float(np.nansum(w * mae) / tw),
        "w_mfe_atr": float(np.nansum(w * mfe) / tw),
        "best_decile_share": best_share,
    })
    return rec


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    C = build_cohort()
    df, sign, entry, atr = C["df"], C["sign"], C["entry"], C["atr"]
    opens, adverse, close_exit = C["opens"], C["adverse"], C["close_exit"]
    highs, lows = C["highs"], C["lows"]
    r_bps, r_atr = C["r_bps"], C["r_atr"]
    yr, scr, gap_atr, vr = C["yr"], C["scr"], C["gap_atr"], C["vr"]

    pnl10, st10, exit10 = scan_with_exit(sign, entry, opens, adverse,
                                         close_exit, -1.0 * atr)
    s_bps = pnl10 / entry * 1e4
    s_atr = pnl10 / atr
    exitA = np.full(len(df), EXIT_MIN)

    maeA, mfeA = excursions(sign, entry, atr, highs, lows, exitA)
    maeB, mfeB = excursions(sign, entry, atr, highs, lows, exit10)
    log(f"MAE A {np.nanmean(maeA[scr]):.3f} ATR, B {np.nanmean(maeB[scr]):.3f}")

    high = (gap_atr > 1.5) | (vr > 5.0)
    low = (gap_atr < 0.8) & (vr < 3.0)
    w_tier = np.where(high, 0.5, np.where(low, 1.25, 1.0))
    atr_pct = atr / entry

    rows = []
    for plab, a_, b_ in PERIODS:
        m = scr & (yr >= a_) & (yr <= b_)
        if m.sum() < 30:
            continue
        wd = 1.0 / atr_pct[m]
        wd = wd / wd.mean()
        ones = np.ones(int(m.sum()))
        specs = [
            (CONFIGS[0], ones, r_bps[m], r_atr[m], maeA[m], mfeA[m]),
            (CONFIGS[1], ones, s_bps[m], s_atr[m], maeB[m], mfeB[m]),
            (CONFIGS[2], w_tier[m], s_bps[m], s_atr[m], maeB[m], mfeB[m]),
            (CONFIGS[3], wd, s_bps[m], s_atr[m], maeB[m], mfeB[m]),
        ]
        for cname, w, rb, ra, ma, mf in specs:
            rows.append(pack(w, rb, ra, ma, mf,
                             {"period": plab, "config": cname}))
        log(f"{plab}: n={int(m.sum()):,}")
    R = {"grid": pd.DataFrame(rows)}

    meta = {"cost_bps": COST_BPS, "n_screened": int(scr.sum()),
            "start": str(df["date"].min().date()),
            "end": str(df["date"].max().date())}
    for k, v in R.items():
        v.to_csv(OUT_DIR / f"eff_{k}.csv", index=False)
    FEED.write_text(json.dumps(
        {"meta": meta, **{k: json.loads(v.round(6).to_json(orient="records"))
                          for k, v in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables")

    from effectiveness_text import build  # noqa: E402
    REPORT.write_text(build(R, meta))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
