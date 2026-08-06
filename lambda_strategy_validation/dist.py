"""
dist.py — full return distribution for the strongest post-earnings setups.

Four groups, all High Volume, all Continuation, post-earnings T+1 only:

    1. HV + Continuation (All)
    2. HV + Continuation + Gap Up
    3. HV + Continuation + Gap Down
    4. HV + Continuation + Market Cap $3B-$10B

at four horizons: 5 min (09:40), 10 min (09:45), 15 min (09:50),
1 hour (10:35).

Universe, signal, entry, guards, volume definition and cost are imported
unchanged from volume_test.py, so these are the same events reported in
VOLUME_TEST_REPORT.md and GAPDIR_REPORT.md, now described rather than
merely averaged.

THREE RETURN SCALES, and they answer different questions.

  simple  r = sign x (P_end/P_entry - 1), in bps. The tradeable number:
          expectancy, win rate and payoff are all computed on this.
  log     l = sign x ln(P_end/P_entry). Reported for shape only. Taking
          logs compresses the right tail more than the left, so log skew
          is mechanically below simple skew; the pair is informative
          precisely because the gap between them measures how much of the
          simple skew is the arithmetic of compounding rather than the
          shape of the move.
  ATR     a = (signed price move) / prior-session ATR(14). Puts a $400
          stock and a $8 stock on one axis, which is the only honest way
          to ask "how often does a trade run 1.5 ATR in my favour".

SKEW AND KURTOSIS are the sample (Fisher) definitions: kurtosis is
EXCESS, so a normal distribution reads 0.0, not 3.0.

ZERO RETURNS are dropped, matching every previous report in this series
(a print-to-print move of exactly zero is a stale quote, not a flat
trade). This removes a spike at the median and, for the 5-minute window,
is not a negligible share -- the count is reported per cell.

Run: python3 lambda_strategy_validation/dist.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

import analysis as A  # noqa: E402
from volume_test import (  # noqa: E402
    COST_BPS, N_BOOT, SMALL, VOL_MULT, VOL_WINDOW, finalize, log,
    prep_earnings, volume_features,
)
from winrate_report import wilson  # noqa: E402

BASE = Path("/home/user/lambda_data")
OUT_DIR = BASE / "tables"
FEED = BASE / "dist_feed.json"
REPORT = Path(__file__).resolve().parent / "DIST_REPORT.md"

CONT = "Continuation (1st candle with gap)"

WINDOWS = {"5 min (09:40)": 9, "10 min (09:45)": 14,
           "15 min (09:50)": 19, "1 hour (10:35)": 64}

GROUPS = ["HV + Continuation (All)", "HV + Continuation + Gap Up",
          "HV + Continuation + Gap Down", "HV + Continuation + $3B-$10B"]

MCAP_LO, MCAP_HI = 3e9, 10e9
LOSS_ATR = -1.0   # "loses more than -1.0 ATR"
GAIN_ATR = 1.5    # "gains more than +1.5 ATR"


def describe(simple: pd.Series, logr: pd.Series, atr: pd.Series,
             dates: pd.Series, label: dict) -> dict:
    """Core metrics, distribution shape on both scales, and ATR tails."""
    n = len(simple)
    k = int((simple > 0).sum())
    lo, hi = wilson(k, n)
    bn = A.clustered_bootstrap(simple - COST_BPS / 1e4, dates, n_boot=N_BOOT)
    wins, losses = simple[simple > 0], simple[simple < 0]
    aw = wins.mean() * 1e4 if len(wins) else np.nan
    al = -losses.mean() * 1e4 if len(losses) else np.nan

    s_bps = simple * 1e4
    q = s_bps.quantile([0.10, 0.25, 0.50, 0.75, 0.90])

    # Skew and kurtosis are dominated by single observations in a sample
    # this heavy-tailed -- one 1-hour event (CAR, 2021-11-02, a real +100%
    # short squeeze) moves the headline skew from ~0.2 to ~15. The
    # winsorised pair describes the body of the distribution; the raw pair
    # describes what actually happened. Both are reported, neither alone.
    w_lo, w_hi = s_bps.quantile([0.01, 0.99])
    s_w = s_bps.clip(w_lo, w_hi)
    l_bps = logr * 1e4
    lw_lo, lw_hi = l_bps.quantile([0.01, 0.99])
    l_w = l_bps.clip(lw_lo, lw_hi)

    rec = dict(label)
    rec.update({
        # core
        "n": n, "n_dates": int(pd.Series(dates).nunique()),
        "win_rate": k / n if n else np.nan,
        "wilson_lo": lo, "wilson_hi": hi,
        "avg_win_bps": aw, "avg_loss_bps": al,
        "payoff_ratio": (aw / al) if al else np.nan,
        "net_bps": bn["stat"] * 1e4, "net_p": bn["p"],
        "net_ci_lo": bn["lo"] * 1e4, "net_ci_hi": bn["hi"] * 1e4,
        "mean_bps": float(s_bps.mean()),
        # distribution, simple
        "p10_bps": float(q.loc[0.10]), "p25_bps": float(q.loc[0.25]),
        "median_bps": float(q.loc[0.50]), "p75_bps": float(q.loc[0.75]),
        "p90_bps": float(q.loc[0.90]),
        "std_bps": float(s_bps.std()),
        "skew": float(stats.skew(s_bps, bias=False)),
        "kurtosis": float(stats.kurtosis(s_bps, fisher=True, bias=False)),
        # distribution, log
        "skew_log": float(stats.skew(l_bps, bias=False)),
        "kurtosis_log": float(stats.kurtosis(l_bps, fisher=True, bias=False)),
        "median_log_bps": float(l_bps.median()),
        # winsorised at 1/99 -- shape of the body, outliers capped not cut
        "skew_w": float(stats.skew(s_w, bias=False)),
        "kurtosis_w": float(stats.kurtosis(s_w, fisher=True, bias=False)),
        "skew_log_w": float(stats.skew(l_w, bias=False)),
        "kurtosis_log_w": float(stats.kurtosis(l_w, fisher=True, bias=False)),
        "mean_w_bps": float(s_w.mean()),
        "max_bps": float(s_bps.max()), "min_bps": float(s_bps.min()),
        "small": "YES" if n < SMALL else "",
    })

    a = atr.dropna()
    rec["n_atr"] = int(len(a))
    if len(a) >= 30:
        rec["pct_loss_gt_1atr"] = float((a < LOSS_ATR).mean())
        rec["pct_gain_gt_15atr"] = float((a > GAIN_ATR).mean())
        rec["median_atr_move"] = float(a.median())
        rec["p10_atr"] = float(a.quantile(0.10))
        rec["p90_atr"] = float(a.quantile(0.90))
    else:
        for c in ("pct_loss_gt_1atr", "pct_gain_gt_15atr", "median_atr_move",
                  "p10_atr", "p90_atr"):
            rec[c] = np.nan
    return rec


def run(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    entry = df["entry_px"]
    gs = pd.Series(np.where(df["gap_up"], 1.0, -1.0), index=df.index)
    hv_cont = df[(df["pattern"] == CONT) & df["high_vol"]]

    mcap = hv_cont[(hv_cont["market_cap_prev"] >= MCAP_LO)
                   & (hv_cont["market_cap_prev"] < MCAP_HI)]
    subs = [
        (GROUPS[0], hv_cont),
        (GROUPS[1], hv_cont[hv_cont["gap_up"]]),
        (GROUPS[2], hv_cont[~hv_cont["gap_up"]]),
        (GROUPS[3], mcap),
    ]
    log("group sizes: " + ", ".join(f"{g}={len(s):,}" for g, s in subs))

    rows, zeros = [], []
    for wname, wmin in WINDOWS.items():
        px = df[f"m{wmin}"]
        simple_all = gs * (px / entry - 1.0)
        log_all = gs * np.log(px / entry)
        # Signed price move over prior-session ATR(14).
        atr_all = gs * (px - entry) / df["atr14_prev"]
        for gname, sub in subs:
            s = simple_all.reindex(sub.index).dropna()
            n_raw = len(s)
            s = s[s != 0]
            if len(s) < 30:
                continue
            zeros.append({"window": wname, "group": gname, "n_raw": n_raw,
                          "n_zero": n_raw - len(s),
                          "pct_zero": (n_raw - len(s)) / n_raw})
            rows.append(describe(
                s, log_all.reindex(s.index), atr_all.reindex(s.index),
                df.loc[s.index, "date"],
                {"window": wname, "group": gname}))
    R = {"dist": pd.DataFrame(rows), "zeros": pd.DataFrame(zeros)}

    # Decile table for the headline group, so the shape is visible directly
    # rather than inferred from four quantiles and a skew number.
    rows = []
    for wname, wmin in WINDOWS.items():
        r = (gs * (df[f"m{wmin}"] / entry - 1.0)).reindex(hv_cont.index)
        r = r.dropna()
        r = r[r != 0] * 1e4
        for d in range(1, 10):
            rows.append({"window": wname, "decile": d * 10,
                         "bps": float(r.quantile(d / 10))})
    R["deciles"] = pd.DataFrame(rows)

    # The largest single moves, and what the headline shape looks like with
    # the biggest one removed. A skew of 15 that collapses to 0.2 on
    # deleting one row is a fact about that row, not about the strategy.
    rows = []
    for wname, wmin in WINDOWS.items():
        r = (gs * (df[f"m{wmin}"] / entry - 1.0)).reindex(hv_cont.index)
        r = r.dropna()
        r = r[r != 0]
        top = r.reindex(r.abs().sort_values(ascending=False).index[:5])
        for rank, (i, v) in enumerate(top.items(), 1):
            rows.append({"window": wname, "rank": rank,
                         "ticker": df.loc[i, "ticker"],
                         "date": str(df.loc[i, "date"].date()),
                         "bps": float(v * 1e4),
                         "entry_px": float(df.loc[i, "entry_px"]),
                         "gap_up": bool(df.loc[i, "gap_up"])})
        cut = r.drop(r.abs().idxmax())
        rows[-5]["skew_all"] = float(stats.skew(r * 1e4, bias=False))
        rows[-5]["skew_ex1"] = float(stats.skew(cut * 1e4, bias=False))
        rows[-5]["kurt_all"] = float(stats.kurtosis(r * 1e4, fisher=True,
                                                    bias=False))
        rows[-5]["kurt_ex1"] = float(stats.kurtosis(cut * 1e4, fisher=True,
                                                    bias=False))
        rows[-5]["mean_all_bps"] = float(r.mean() * 1e4)
        rows[-5]["mean_ex1_bps"] = float(cut.mean() * 1e4)
    R["outliers"] = pd.DataFrame(rows)

    # Market-cap coverage, since group 4 depends on a field missing for
    # roughly a ninth of events.
    R["mcap_cov"] = pd.DataFrame([{
        "n_hv_cont": len(hv_cont),
        "n_with_mcap": int(hv_cont["market_cap_prev"].notna().sum()),
        "n_3_10b": len(mcap),
        "median_mcap_b": float(mcap["market_cap_prev"].median() / 1e9),
        "median_price": float(mcap["entry_px"].median()),
        "median_roll_bps": float(mcap["roll_spread_bps_med63"].median())
        if "roll_spread_bps_med63" in mcap.columns else np.nan,
        "all_median_roll_bps": float(
            hv_cont["roll_spread_bps_med63"].median())
        if "roll_spread_bps_med63" in hv_cont.columns else np.nan,
    }])
    return R


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    vol = volume_features()
    log("volume features built")

    df, meta = finalize(prep_earnings(vol), "Post-Earnings (T+1)")
    hv_cont = df[(df["pattern"] == CONT) & df["high_vol"]]
    meta.update({"cost_bps": COST_BPS, "small": SMALL, "vol_mult": VOL_MULT,
                 "vol_window": VOL_WINDOW, "n_hv_cont": int(len(hv_cont)),
                 "loss_atr": LOSS_ATR, "gain_atr": GAIN_ATR,
                 "atr_coverage": float(hv_cont["atr14_prev"].notna().mean())})

    R = run(df)
    for k, v in R.items():
        v.to_csv(OUT_DIR / f"dist_{k}.csv", index=False)
    FEED.write_text(json.dumps(
        {"meta": meta, **{k: json.loads(v.round(6).to_json(orient="records"))
                          for k, v in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables")

    from dist_text import build  # noqa: E402
    REPORT.write_text(build(R, meta))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
