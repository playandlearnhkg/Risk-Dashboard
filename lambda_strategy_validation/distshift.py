"""
distshift.py — how the return DISTRIBUTION moves across periods, and what
the ATR -1.0 stop and position sizing do to it.

Cohort (identical to REGIME_REPORT.md / SIZING_REPORT.md, built by
regime_sizing.build_cohort so the definitions cannot drift):
  post-earnings T+1, non-zero gap, High Volume (c1_volume > 1.5x the
  trailing 20-session same-slot mean), Continuation = first 5-minute
  candle closes with the gap and body/range > 0.10, entry at the open of
  the 09:35 bar, hold to 10:35, corrected universe screen, prior-session
  ATR(14), 6.6 bps round trip.

Configurations
  A  no stop, equal size
  B  ATR -1.0 stop (intrabar), equal size
  C  ATR -1.0 stop + three-tier sizing 1.25 / 1.0 / 0.5
  D  ATR -1.0 stop + fixed dollar risk, weight proportional to 1/ATR%

EVERYTHING IS PER UNIT OF AVERAGE NOTIONAL DEPLOYED
  For a weight vector w the reported per-trade series is

      contribution_i = w_i x (return_i - cost) / mean(w)

  so the mean of that series is the weighted return per unit of capital
  actually committed, and the percentiles and moments describe the P&L a
  book of that shape would experience. Without the normalisation a
  scheme that merely deploys less capital would look calmer and less
  profitable for no reason but leverage.

TWO KINDS OF "% LOSING MORE THAN 1 ATR", AND THEY ANSWER DIFFERENT THINGS
  Sizing cannot change whether a TRADE moved more than 1 ATR against
  entry -- that is a property of the price path. So the trade-count
  version is identical for B, C and D by construction, and only the stop
  moves it. What sizing changes is how much capital was standing in
  front of those moves, which is the NOTIONAL-WEIGHTED version. Both are
  reported; reading only the first would make sizing look inert.

Run: python3 lambda_strategy_validation/distshift.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from regime_sizing import PERIODS, build_cohort, wins_kurt  # noqa: E402
from stops import COST_BPS, ENTRY_MIN, OUT_DIR, log  # noqa: E402
from stopsummary import scan_intrabar  # noqa: E402

BASE = Path("/home/user/lambda_data")
FEED = BASE / "distshift_feed.json"
REPORT = Path(__file__).resolve().parent / "DISTSHIFT_REPORT.md"

CONFIGS = ["A — No stop, equal size",
           "B — ATR −1.0 stop, equal size",
           "C — ATR −1.0 stop + three-tier sizing",
           "D — ATR −1.0 stop + fixed dollar risk"]


def describe(w, r_bps, r_atr, label) -> dict:
    """Distribution of the per-unit-notional P&L contribution."""
    wm = w.mean()
    contrib = w * (r_bps - COST_BPS) / wm
    q = np.quantile(contrib, [0.10, 0.25, 0.50, 0.75, 0.90])
    sk_w, ku_w = wins_kurt(contrib)
    m05, m1, g1 = r_atr < -0.5, r_atr < -1.0, r_atr > 1.0
    tot_w = w.sum()
    rec = dict(label)
    rec.update({
        "n": len(r_bps),
        "mean_weight": float(wm), "max_weight": float(w.max()),
        "eff_n": float(tot_w ** 2 / (w ** 2).sum()),
        "mean_bps": float(contrib.mean()),
        "median_bps": float(q[2]),
        "std_bps": float(contrib.std()),
        "p10": float(q[0]), "p25": float(q[1]),
        "p75": float(q[3]), "p90": float(q[4]),
        "skew_w": sk_w, "kurtosis_w": ku_w,
        "skew_raw": float(stats.skew(contrib, bias=False)),
        "kurtosis_raw": float(stats.kurtosis(contrib, fisher=True,
                                             bias=False)),
        # trade-count basis: sizing cannot move these
        "pct_loss_05atr": float(m05.mean()),
        "pct_loss_1atr": float(m1.mean()),
        "pct_gain_1atr": float(g1.mean()),
        # notional-weighted basis: sizing does move these
        "w_pct_loss_05atr": float(w[m05].sum() / tot_w),
        "w_pct_loss_1atr": float(w[m1].sum() / tot_w),
        "w_pct_gain_1atr": float(w[g1].sum() / tot_w),
        "avg_large_loss_bps": float(contrib[m1].mean()) if m1.any()
        else np.nan,
        "sharpe_like": float(contrib.mean() / contrib.std())
        if contrib.std() else np.nan,
    })
    return rec


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    C = build_cohort()
    df, sign, entry, atr = C["df"], C["sign"], C["entry"], C["atr"]
    opens, adverse, close_exit = C["opens"], C["adverse"], C["close_exit"]
    r_bps, r_atr = C["r_bps"], C["r_atr"]
    yr, scr, gap_atr, vr = C["yr"], C["scr"], C["gap_atr"], C["vr"]

    # ATR -1.0, intrabar, on the whole cohort; sliced per period below.
    pnl10, st10, _ = scan_intrabar(sign, entry, opens, adverse, close_exit,
                                   -1.0 * atr)
    s_bps = pnl10 / entry * 1e4
    s_atr = pnl10 / atr
    log(f"ATR −1.0 stops {st10[scr].mean()*100:.1f}% of the screened cohort")

    high = (gap_atr > 1.5) | (vr > 5.0)
    low = (gap_atr < 0.8) & (vr < 3.0)
    w_tier = np.where(high, 0.5, np.where(low, 1.25, 1.0))
    atr_pct = atr / entry

    rows = []
    for plab, a_, b_ in PERIODS:
        m = scr & (yr >= a_) & (yr <= b_)
        if m.sum() < 30:
            continue
        # Scheme D is normalised WITHIN the period so mean weight is 1
        # there; otherwise a period with quieter names would look
        # systematically levered against the others.
        wd = 1.0 / atr_pct[m]
        wd = wd / wd.mean()
        ones = np.ones(int(m.sum()))
        specs = [
            (CONFIGS[0], ones, r_bps[m], r_atr[m]),
            (CONFIGS[1], ones, s_bps[m], s_atr[m]),
            (CONFIGS[2], w_tier[m], s_bps[m], s_atr[m]),
            (CONFIGS[3], wd, s_bps[m], s_atr[m]),
        ]
        for cname, w, rb, ra in specs:
            rows.append(describe(w, rb, ra,
                                 {"period": plab, "config": cname}))
        log(f"{plab}: n={int(m.sum()):,}, "
            f"stopped {st10[m].mean()*100:.1f}%")
    R = {"grid": pd.DataFrame(rows)}

    # Tier composition per period — the mix drives what scheme C does.
    rows = []
    for plab, a_, b_ in PERIODS:
        m = scr & (yr >= a_) & (yr <= b_)
        if m.sum() < 30:
            continue
        rows.append({
            "period": plab, "n": int(m.sum()),
            "pct_high": float(high[m].mean()),
            "pct_low": float(low[m].mean()),
            "pct_med": float((~high[m] & ~low[m]).mean()),
            "median_gap_atr": float(np.median(gap_atr[m])),
            "median_vol_ratio": float(np.median(vr[m])),
            "median_atr_pct": float(np.median(atr_pct[m]) * 100),
            "pct_stopped": float(st10[m].mean()),
        })
    R["mix"] = pd.DataFrame(rows)

    meta = {"cost_bps": COST_BPS, "n_screened": int(scr.sum()),
            "start": str(df["date"].min().date()),
            "end": str(df["date"].max().date()),
            "entry_min": ENTRY_MIN}
    for k, v in R.items():
        v.to_csv(OUT_DIR / f"ds_{k}.csv", index=False)
    FEED.write_text(json.dumps(
        {"meta": meta, **{k: json.loads(v.round(6).to_json(orient="records"))
                          for k, v in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables")

    from distshift_text import build  # noqa: E402
    REPORT.write_text(build(R, meta))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
