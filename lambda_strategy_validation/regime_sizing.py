"""
regime_sizing.py — two linked studies on the post-earnings T+1 edge.

STUDY 1 — has the edge decayed, and is recent weakness a left-tail story?
  The core cohort by year and by period (2015-2019, 2020-2022,
  2023-2025), with and without the full universe screen, plus whether an
  ATR -1.0 stop is worth more now than it used to be.

STUDY 2 — conviction / risk-based position sizing.
  Four schemes on the SCREENED cohort, using only entry-time risk
  factors (gap/ATR and the opening volume ratio).

HOW THE FOUR SCHEMES ARE MADE COMPARABLE
  Every scheme is a vector of notional weights, and results are reported
  per unit of AVERAGE notional deployed:

      return_per_unit = sum(w_i * r_i) / sum(w_i)

  Without that normalisation a scheme that simply deploys less capital
  would look better on risk and worse on return for no reason other than
  leverage. The mean raw weight is reported alongside so the
  de-leveraging is visible rather than hidden.

  Scheme D is the one that needs the argument spelled out. Risking a
  fixed dollar amount per ATR means

      shares  = R / ATR_dollars
      notional = shares x price = R x price / ATR_dollars = R / ATR_pct

  so its notional weight is proportional to 1 / (ATR as a share of
  price). That makes it expressible in the same units as A, B and C
  rather than only in risk units -- and it also exposes the practical
  problem, which is that a very low-volatility name attracts a very
  large position. The weight distribution is reported for that reason.

WIN RATE IS IDENTICAL ACROSS SCHEMES by construction: every weight is
positive, so sizing cannot change the sign of a trade. The same is true
of "% of trades losing more than 1 ATR", which is a property of the
trade rather than of the position, so what changes -- and what is
reported -- is those trades' CONTRIBUTION to the book.

Run: python3 lambda_strategy_validation/regime_sizing.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

import analysis as A  # noqa: E402
from doji import G_CONT, classify  # noqa: E402
from stops import (  # noqa: E402
    COST_BPS, ENTRY_MIN, EXIT_MIN, MAX_MIN, N_BOOT, OUT_DIR, SIGNAL_MIN,
    VOL_MULT, load_paths, log, mat,
)
from stopsummary import scan_intrabar  # noqa: E402
from volume_test import volume_features  # noqa: E402
from winrate_report import wilson  # noqa: E402

BASE = Path("/home/user/lambda_data")
FEED = BASE / "regime_sizing_feed.json"
REPORT_Y = Path(__file__).resolve().parent / "REGIME_REPORT.md"
REPORT_S = Path(__file__).resolve().parent / "SIZING_REPORT.md"

PERIODS = [("2015–2019", 2015, 2019), ("2020–2022", 2020, 2022),
           ("2023–2025", 2023, 2025)]
SMALL = 150


def wins_kurt(x: np.ndarray) -> tuple[float, float]:
    lo, hi = np.quantile(x, [0.01, 0.99])
    c = np.clip(x, lo, hi)
    return (float(stats.skew(c, bias=False)),
            float(stats.kurtosis(c, fisher=True, bias=False)))


def pack(r_bps, r_atr, cost_atr, dates, label) -> dict:
    n = len(r_bps)
    if n == 0:
        return dict(label, n=0)
    k = int((r_bps > 0).sum())
    lo, hi = wilson(k, n)
    vals = pd.Series(r_bps / 1e4 - COST_BPS / 1e4).reset_index(drop=True)
    clus = pd.Series(np.asarray(dates)).reset_index(drop=True)
    b = A.clustered_bootstrap(vals, clus, n_boot=N_BOOT)
    wins, losses = r_bps[r_bps > 0], r_bps[r_bps < 0]
    aw = wins.mean() if len(wins) else np.nan
    al = -losses.mean() if len(losses) else np.nan
    m1, m05 = r_atr < -1.0, r_atr < -0.5
    sk_w, ku_w = wins_kurt(r_bps)
    rec = dict(label)
    rec.update({
        "n": n, "win_rate": k / n, "wilson_lo": lo, "wilson_hi": hi,
        "net_bps": b["stat"] * 1e4, "net_p": b["p"],
        "net_atr": float((r_atr - cost_atr).mean()),
        "avg_win_bps": aw, "avg_loss_bps": al,
        "payoff_ratio": (aw / al) if al else np.nan,
        "median_bps": float(np.median(r_bps)),
        "p10_bps": float(np.quantile(r_bps, 0.10)),
        "pct_loss_05atr": float(m05.mean()),
        "pct_loss_1atr": float(m1.mean()),
        "avg_large_loss_bps": float(r_bps[m1].mean()) if m1.any() else np.nan,
        "avg_large_loss_atr": float(r_atr[m1].mean()) if m1.any() else np.nan,
        "std_bps": float(r_bps.std()),
        "skew": float(stats.skew(r_bps, bias=False)),
        "kurtosis": float(stats.kurtosis(r_bps, fisher=True, bias=False)),
        "skew_w": sk_w, "kurtosis_w": ku_w,
        "small": "YES" if n < SMALL else "",
    })
    return rec


def weighted(w, r_bps, r_atr, cost_atr, label) -> dict:
    """Per unit of average notional deployed."""
    tot = w.sum()
    pr = w * r_bps / tot * len(w)      # per-trade contribution, rescaled
    n = len(r_bps)
    k = int((r_bps > 0).sum())
    net_bps = float((w * (r_bps - COST_BPS)).sum() / tot)
    net_atr = float((w * (r_atr - cost_atr)).sum() / tot)
    wins, losses = pr[r_bps > 0], pr[r_bps < 0]
    aw = wins.mean() if len(wins) else np.nan
    al = -losses.mean() if len(losses) else np.nan
    m1 = r_atr < -1.0
    rec = dict(label)
    rec.update({
        "n": n, "mean_weight": float(w.mean()), "max_weight": float(w.max()),
        "win_rate": k / n,
        "net_bps": net_bps, "net_atr": net_atr,
        "avg_win_bps": aw, "avg_loss_bps": al,
        "payoff_ratio": (aw / al) if al else np.nan,
        "pct_loss_1atr": float(m1.mean()),
        "avg_large_loss_bps": float(pr[m1].mean()) if m1.any() else np.nan,
        "std_bps": float(pr.std()),
        "sharpe_like": net_bps / float(pr.std()) if pr.std() else np.nan,
        "share_of_pnl_highrisk": np.nan,
    })
    return rec


def build_cohort():
    """Core cohort plus the corrected universe screen.

    Shared with distshift.py so the two studies cannot drift apart on
    cohort or screen definition.
    """
    vol = volume_features()
    log("volume features built")

    ev = pd.read_parquet(BASE / "events.parquet")
    ev["date"] = pd.to_datetime(ev["date"])
    ev = ev[ev["gap"] != 0].copy()
    ev["gap_up"] = ev["gap"] > 0

    panel = pd.read_parquet(
        BASE / "panel.parquet",
        columns=["ticker", "date", "atr14", "universe_ok_prev",
                 "price_ok_prev", "mcap_ok_prev", "adtv_63_prev"])
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel.sort_values(["ticker", "date"]).reset_index(drop=True)
    panel["atr14_prev"] = panel.groupby("ticker")["atr14"].shift(1)

    # THE ORIGINAL SCREEN IS BROKEN FROM 2022 ONWARD.
    # The 2022-03-01 IEX consolidated-tape change rescales reported
    # volume, so a fixed 500k-share / $50M threshold stops measuring
    # liquidity and starts measuring which side of the break a row sits
    # on: ADV pass rates fall from ~85% to 4.6% and ADTV from ~73% to
    # 1.9%, while price and market-cap pass rates are unchanged. Any
    # "screened" cohort built on it is really a 2015-2021 cohort.
    #
    # screen_v2 keeps the price and market-cap tests as-is and replaces
    # the two volume tests with a WITHIN-YEAR cross-sectional rank,
    # calibrated so the pass rate matches what the dollar threshold
    # admitted before the break. A relative screen is immune to a
    # level shift in the units.
    panel["yr"] = panel["date"].dt.year
    pre = panel[panel["yr"] <= 2021]
    target = float((pre["adtv_63_prev"] >= 50e6).mean())
    thr = panel.groupby("yr")["adtv_63_prev"].transform(
        lambda s: s.quantile(max(0.0, 1.0 - target)))
    panel["liq_ok_v2"] = panel["adtv_63_prev"] >= thr
    panel["screen_v2"] = (panel["price_ok_prev"].fillna(False)
                          & panel["mcap_ok_prev"].fillna(False)
                          & panel["liq_ok_v2"].fillna(False))
    log(f"screen_v2 target pass rate {target:.3f}; "
        f"overall {panel['screen_v2'].mean():.3f}")

    ev = ev.drop(columns=["universe_ok_prev"], errors="ignore")
    ev = ev.merge(panel[["ticker", "date", "atr14_prev", "universe_ok_prev",
                         "screen_v2"]],
                  on=["ticker", "date"], how="left")
    ev = ev.merge(vol, on=["ticker", "date"], how="left", suffixes=("", "_v"))
    ev = classify(ev)

    paths = load_paths(ev)
    df = ev.merge(paths, on=["ticker", "date"], how="inner",
                  suffixes=("", "_p"))
    early = [f"open{i}" for i in range(0, ENTRY_MIN + 1)]
    df = df[df[early].notna().any(axis=1)].copy()
    df["entry_px"] = df[f"open{ENTRY_MIN}"].fillna(df[f"close{SIGNAL_MIN}"])
    df = df[df["entry_px"].notna()]
    df = df[~df["vol_straddle"].fillna(False) & df["vol_ratio"].notna()]
    df = df[(df["vol_ratio"] > VOL_MULT) & (df["klass"] == G_CONT)]
    df = df[df["atr14_prev"].notna() & (df["atr14_prev"] > 0)]
    df = df.reset_index(drop=True)

    ccols = [f"close{m}" for m in range(MAX_MIN)]
    cm = df[ccols].copy()
    cm.insert(0, "seed", df["session_open"])
    df[ccols] = cm.ffill(axis=1).drop(columns="seed")
    df = df[df[f"close{EXIT_MIN}"].notna()].reset_index(drop=True)
    log(f"core cohort: {len(df):,}")

    sign = np.where(df["gap_up"], 1.0, -1.0)
    entry = df["entry_px"].to_numpy(float)
    atr = df["atr14_prev"].to_numpy(float)
    closes = df[ccols].to_numpy(float)
    opens, highs, lows = mat(df, "open"), mat(df, "high"), mat(df, "low")
    adverse = np.where(sign[:, None] > 0, lows, highs)
    close_exit = sign * (closes[:, EXIT_MIN] - entry)

    r_bps = close_exit / entry * 1e4
    r_atr = close_exit / atr
    cost_atr = (COST_BPS / 1e4) * entry / atr
    yr = df["date"].dt.year.to_numpy()
    scr_old = df["universe_ok_prev"].fillna(False).to_numpy()
    scr = df["screen_v2"].fillna(False).to_numpy()

    # Diagnostic for the report: how each screen's coverage moves by year.
    cov = pd.DataFrame({"year": yr, "old": scr_old, "v2": scr}) \
        .groupby("year").agg(n=("old", "size"), old_pass=("old", "mean"),
                             v2_pass=("v2", "mean")).reset_index()
    prev_close = (df["open"] / (1.0 + df["gap"])).to_numpy(float)
    gap_atr = np.abs(df["open"].to_numpy(float) - prev_close) / atr
    vr = df["vol_ratio"].to_numpy(float)
    dates = df["date"]

    return dict(df=df, sign=sign, entry=entry, atr=atr, closes=closes,
                opens=opens, highs=highs, lows=lows, adverse=adverse,
                close_exit=close_exit, r_bps=r_bps, r_atr=r_atr,
                cost_atr=cost_atr, yr=yr, scr=scr, scr_old=scr_old,
                gap_atr=gap_atr, vr=vr, dates=dates, cov=cov,
                target=target)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    C = build_cohort()
    df, sign, entry, atr = C['df'], C['sign'], C['entry'], C['atr']
    closes, opens, adverse = C['closes'], C['opens'], C['adverse']
    close_exit, r_bps, r_atr = C['close_exit'], C['r_bps'], C['r_atr']
    cost_atr, yr, scr = C['cost_atr'], C['yr'], C['scr']
    gap_atr, vr, dates = C['gap_atr'], C['vr'], C['dates']
    cov, target = C['cov'], C['target']

    R: dict[str, pd.DataFrame] = {}

    # ================= STUDY 1 =================
    R["coverage"] = cov

    rows = []
    for uni, m0 in (("All (no screen)", np.ones(len(df), bool)),
                    ("Screened", scr)):
        for y in sorted(set(yr)):
            m = m0 & (yr == y)
            if m.sum() < 30:
                continue
            rows.append(pack(r_bps[m], r_atr[m], cost_atr[m], dates[m],
                             {"universe": uni, "bucket": str(y),
                              "kind": "year"}))
        for lab, a_, b_ in PERIODS:
            m = m0 & (yr >= a_) & (yr <= b_)
            if m.sum() < 30:
                continue
            rows.append(pack(r_bps[m], r_atr[m], cost_atr[m], dates[m],
                             {"universe": uni, "bucket": lab,
                              "kind": "period"}))
    R["yearly"] = pd.DataFrame(rows)

    # ---- does the ATR -1.0 stop earn its place more recently? ----
    pnl10, st10, _ = scan_intrabar(sign, entry, opens, adverse, close_exit,
                                   -1.0 * atr)
    s_bps = pnl10 / entry * 1e4
    s_atr = pnl10 / atr
    rows = []
    for uni, m0 in (("All (no screen)", np.ones(len(df), bool)),
                    ("Screened", scr)):
        for lab, a_, b_ in PERIODS:
            m = m0 & (yr >= a_) & (yr <= b_)
            if m.sum() < 30:
                continue
            base_net = float(r_bps[m].mean() - COST_BPS)
            stop_net = float(s_bps[m].mean() - COST_BPS)
            base_tail = float((r_atr[m] < -1.0).mean()) * 100
            stop_tail = float((s_atr[m] < -1.0).mean()) * 100
            cost = base_net - stop_net
            cut = base_tail - stop_tail
            rows.append({
                "universe": uni, "period": lab, "n": int(m.sum()),
                "base_net": base_net, "stop_net": stop_net,
                "cost_bps": cost,
                "base_tail_pct": base_tail, "stop_tail_pct": stop_tail,
                "tail_cut_pp": cut,
                "efficiency": cut / cost if cost > 0 else np.nan,
                "pct_stopped": float(st10[m].mean()),
            })
    R["stopvalue"] = pd.DataFrame(rows)

    # ================= STUDY 2 =================
    sm = scr
    log(f"screened cohort for sizing: {sm.sum():,}")
    rb, ra, ca = r_bps[sm], r_atr[sm], cost_atr[sm]
    g, v = gap_atr[sm], vr[sm]

    high = (g > 1.5) | (v > 5.0)
    low = (g < 0.8) & (v < 3.0)
    med = ~high & ~low

    schemes = {}
    schemes["C — Equal size (baseline)"] = np.ones(sm.sum())
    schemes["A — Two tier (0.5× high risk)"] = np.where(high, 0.5, 1.0)
    wB = np.where(high, 0.5, np.where(low, 1.25, 1.0))
    schemes["B — Three tier (1.25 / 1.0 / 0.5)"] = wB
    wB2 = np.where(high, 0.5, np.where(low, 1.5, 1.0))
    schemes["B2 — Three tier (1.5 / 1.0 / 0.5)"] = wB2
    atr_pct = atr[sm] / entry[sm]
    wD = 1.0 / atr_pct
    wD = wD / wD.mean()
    schemes["D — Fixed dollar risk (∝ 1/ATR%)"] = wD

    rows = []
    for nm, w in schemes.items():
        rows.append(weighted(w, rb, ra, ca, {"scheme": nm}))
    R["schemes"] = pd.DataFrame(rows)

    # equal-size decomposition
    tot_pnl = (rb - COST_BPS).sum()
    m1 = ra < -1.0
    rows = []
    for nm, m in (("High Risk", high), ("Medium", med), ("Low Risk", low),
                  ("Low + Medium", low | med)):
        if m.sum() < 30:
            continue
        rows.append({
            "group": nm, "n": int(m.sum()),
            "share_of_trades": float(m.mean()),
            "net_bps": float(rb[m].mean() - COST_BPS),
            "net_atr": float((ra[m] - ca[m]).mean()),
            "win_rate": float((rb[m] > 0).mean()),
            "avg_win_bps": float(rb[m][rb[m] > 0].mean()),
            "avg_loss_bps": float(-rb[m][rb[m] < 0].mean()),
            "payoff_ratio": float(rb[m][rb[m] > 0].mean()
                                  / -rb[m][rb[m] < 0].mean()),
            "std_bps": float(rb[m].std()),
            "pct_loss_1atr": float(m1[m].mean()),
            "avg_large_loss_bps": float(rb[m][m1[m]].mean())
            if m1[m].any() else np.nan,
            "share_of_total_pnl": float((rb[m] - COST_BPS).sum() / tot_pnl),
            "share_of_large_losses": float(m1[m].sum() / m1.sum())
            if m1.sum() else np.nan,
        })
    R["groups"] = pd.DataFrame(rows)

    meta = {"cost_bps": COST_BPS, "small": SMALL, "n_core": int(len(df)),
            "n_screened": int(sm.sum()),
            "start": str(df["date"].min().date()),
            "end": str(df["date"].max().date()),
            "pct_high": float(high.mean()), "pct_low": float(low.mean()),
            "screen_target": float(target),
            "pct_med": float(med.mean())}
    for k, v_ in R.items():
        v_.to_csv(OUT_DIR / f"rs_{k}.csv", index=False)
    FEED.write_text(json.dumps(
        {"meta": meta, **{k: json.loads(v_.round(6).to_json(orient="records"))
                          for k, v_ in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables")

    from regime_sizing_text import build_regime, build_sizing  # noqa: E402
    REPORT_Y.write_text(build_regime(R, meta))
    REPORT_S.write_text(build_sizing(R, meta))
    log(f"wrote {REPORT_Y} and {REPORT_S}")


if __name__ == "__main__":
    main()
