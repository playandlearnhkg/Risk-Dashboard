"""
overnight.py — residual edge in the session AFTER the trade, on two
universes.

TEST 1 — post-earnings
  Cohort: High Volume + Continuation (non-doji), the setup used
  throughout this series. Enter at the 09:35 open on T+1 and hold to the
  T+1 CLOSE (not 10:35 -- this test needs the day's full result to
  classify the trade). Split into Winners and Losers on that result, then
  measure T+1 close -> T+2 close, signed in the trade's direction.

TEST 2 — ordinary non-earnings days
  Every session in the panel that passes the prior-session liquidity
  screen and is NOT a post-earnings T+1 day. The "trade" is long the
  stock from the open to the close of day T; Winners are sessions that
  closed above their open. The following period is measured T close ->
  T+1 close, LONG, because an ordinary session carries no signal
  direction of its own to sign it with.

A NOTE ON "OVERNIGHT"
  Both designs specify close -> close, which is a full session plus the
  gap that precedes it, not the gap alone. That is what is reported as
  the headline return. The gap component is broken out separately in
  section C so the two are not conflated.

ATR SCALING
  The ">1 ATR" thresholds use ATR(14) as of the classifying day's close
  -- known at the moment the hold-overnight decision would be made, so
  no look-ahead. This is a different (later) ATR than the entry-day ATR
  used in the stop reports, and deliberately so.

LIQUIDITY SCREEN
  `universe_ok_prev` in the panel: price >= $10, ADV >= 500k shares,
  ADTV >= $50M, market cap >= $3B, all evaluated on the PRIOR session so
  the screen is point-in-time.

Run: python3 lambda_strategy_validation/overnight.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

import analysis as A  # noqa: E402
from doji import G_CONT, classify  # noqa: E402
from volume_test import (  # noqa: E402
    COST_BPS, ENTRY_MIN, N_BOOT, SIGNAL_MIN, VOL_MULT, VOL_WINDOW,
    load_wide, log, volume_features,
)
from winrate_report import wilson  # noqa: E402

BASE = Path("/home/user/lambda_data")
OUT_DIR = BASE / "tables"
FEED = BASE / "overnight_feed.json"
REPORT = Path(__file__).resolve().parent / "OVERNIGHT_REPORT.md"

START, END = "2015-01-01", "2025-12-31"

# DATA SEAM. The panel's price basis changes between 2022-03-04 and the
# next session: 28 liquid names show close-to-close moves of 10x to 21x
# in one step (AMZN 2911 -> 138, GOOGL 2637 -> 125, NVDA 229 -> 21),
# which are split adjustments applied from that date rather than real
# returns. It sits alongside the known 2022-03-01 IEX tape change already
# handled in volume_test.py. Every close-to-close observation spanning
# that boundary is dropped, for all tickers rather than only the visibly
# broken ones, since the basis change affects the series not the name.
# Genuine extremes elsewhere (GME 2021, the COVID crash) are KEPT.
SEAM = pd.Timestamp("2022-03-04")


def shape(r: pd.Series, atr_r: pd.Series, dates: pd.Series,
          label: dict) -> dict:
    n = len(r)
    k = int((r > 0).sum())
    lo, hi = wilson(k, n)
    b = A.clustered_bootstrap(r, dates, n_boot=N_BOOT)
    bps = r * 1e4
    q = bps.quantile([0.10, 0.25, 0.50, 0.75, 0.90])
    rec = dict(label)
    rec.update({
        "n": n, "win_rate": k / n if n else np.nan,
        "wilson_lo": lo, "wilson_hi": hi,
        "mean_bps": float(bps.mean()),
        "boot_p": b["p"], "ci_lo": b["lo"] * 1e4, "ci_hi": b["hi"] * 1e4,
        "median_bps": float(q.loc[0.50]),
        "p10_bps": float(q.loc[0.10]), "p25_bps": float(q.loc[0.25]),
        "p75_bps": float(q.loc[0.75]), "p90_bps": float(q.loc[0.90]),
        "std_bps": float(bps.std()),
        "skew": float(stats.skew(bps, bias=False)),
        "kurtosis": float(stats.kurtosis(bps, fisher=True, bias=False)),
        "pct_loss_1atr": float((atr_r < -1.0).mean()),
        "n_atr": int(atr_r.notna().sum()),
    })
    # Pooled means weight a date by how many names it contributes, so a
    # single busy day can dominate. The date-equal-weighted mean is what a
    # daily-rebalanced equal-weight book would actually earn, and the two
    # can differ materially. Both are reported.
    dm = pd.Series(r.to_numpy(), index=pd.Series(dates).to_numpy()) \
        .groupby(level=0).mean()
    se = dm.std() / np.sqrt(len(dm)) if len(dm) > 1 else np.nan
    rec.update({
        "n_dates": int(len(dm)),
        "dw_mean_bps": float(dm.mean() * 1e4),
        "dw_se_bps": float(se * 1e4) if se == se else np.nan,
        "dw_t": float(dm.mean() / se) if se and se == se else np.nan,
    })
    return rec


# ---------------------------------------------------------------------------
# TEST 1
# ---------------------------------------------------------------------------

def test_earnings() -> dict[str, pd.DataFrame]:
    vol = volume_features()
    ev = pd.read_parquet(BASE / "events.parquet")
    ev["date"] = pd.to_datetime(ev["date"])
    ev = ev[ev["gap"] != 0].copy()
    ev["gap_up"] = ev["gap"] > 0
    ev = ev.merge(vol, on=["ticker", "date"], how="left")
    ev = classify(ev)

    panel = pd.read_parquet(BASE / "panel.parquet",
                            columns=["ticker", "date", "open", "close",
                                     "atr14"])
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel.sort_values(["ticker", "date"]).reset_index(drop=True)
    g = panel.groupby("ticker")
    # T+2 = the next trading row for that ticker.
    panel["next_open"] = g["open"].shift(-1)
    panel["next_close"] = g["close"].shift(-1)
    panel["next_date"] = g["date"].shift(-1)

    ev = ev.merge(panel[["ticker", "date", "close", "atr14", "next_open",
                         "next_close", "next_date"]],
                  on=["ticker", "date"], how="left", suffixes=("", "_pnl"))

    wide = load_wide(ev, BASE / "intraday210", 210)
    df = ev.merge(wide, on=["ticker", "date"], how="inner", suffixes=("", "_w"))
    early = [f"o{i}" for i in range(0, ENTRY_MIN + 1) if f"o{i}" in df.columns]
    df = df[df[early].notna().any(axis=1)].copy()
    df["entry_px"] = df[f"o{ENTRY_MIN}"].fillna(df[f"m{SIGNAL_MIN}"])
    df = df[df["entry_px"].notna()]
    df = df[~df["vol_straddle"].fillna(False)]
    df = df[df["vol_ratio"].notna()]
    df = df[(df["vol_ratio"] > VOL_MULT) & (df["klass"] == G_CONT)]
    df = df[df["next_close"].notna() & df["close_pnl"].notna()
            & (df["atr14"] > 0)].copy()
    n_pre = len(df)
    df = df[df["date"] != SEAM].copy()
    df = df.reset_index(drop=True)
    log(f"earnings cohort with a T+2: {len(df):,} "
        f"(dropped {n_pre - len(df)} spanning the data seam)")

    sign = np.where(df["gap_up"], 1.0, -1.0)
    day = sign * (df["close_pnl"].to_numpy(float)
                  / df["entry_px"].to_numpy(float) - 1.0)
    on = sign * (df["next_close"].to_numpy(float)
                 / df["close_pnl"].to_numpy(float) - 1.0)
    gap = sign * (df["next_open"].to_numpy(float)
                  / df["close_pnl"].to_numpy(float) - 1.0)
    atr_r = on * df["close_pnl"].to_numpy(float) / df["atr14"].to_numpy(float)

    winner = day > 0
    groups = [("Winners at T+1 close", winner),
              ("Losers at T+1 close", ~winner),
              ("All trades", np.ones(len(df), dtype=bool))]

    rows = []
    for name, m in groups:
        rows.append(shape(pd.Series(on[m]), pd.Series(atr_r[m]),
                          df.loc[m, "date"], {"group": name}))
        rows[-1]["mean_day_bps"] = float(day[m].mean() * 1e4)
    R = {"e_perf": pd.DataFrame(rows)}

    # ---- C. gap behaviour ----
    rows = []
    for name, m in groups:
        gm = gap[m]
        same = gm > 0
        rows.append({
            "group": name, "n": int(m.sum()),
            "mean_gap_bps": float(gm.mean() * 1e4),
            "median_gap_bps": float(np.median(gm) * 1e4),
            "pct_same_dir": float(same.mean()),
            "pct_against": float((gm < 0).mean()),
            "avg_fav_gap_bps": float(gm[same].mean() * 1e4)
            if same.any() else np.nan,
            "avg_unfav_gap_bps": float(gm[gm < 0].mean() * 1e4)
            if (gm < 0).any() else np.nan,
            # how much of the close-to-close move is the gap itself
            "gap_share_of_move": float(gm.mean() / on[m].mean())
            if on[m].mean() != 0 else np.nan,
        })
    R["e_gap"] = pd.DataFrame(rows)
    return R


# ---------------------------------------------------------------------------
# TEST 2
# ---------------------------------------------------------------------------

def test_ordinary() -> dict[str, pd.DataFrame]:
    cols = ["ticker", "date", "open", "close", "atr14", "universe_ok_prev",
            "is_t1"]
    p = pd.read_parquet(BASE / "panel.parquet", columns=cols)
    p["date"] = pd.to_datetime(p["date"])
    p = p[(p["date"] >= START) & (p["date"] <= END)]
    p = p.sort_values(["ticker", "date"]).reset_index(drop=True)
    g = p.groupby("ticker")
    p["next_close"] = g["close"].shift(-1)

    n0 = len(p)
    p = p[p["universe_ok_prev"].fillna(False)]
    n1 = len(p)
    # Drop the earnings sessions this series has already studied, and the
    # session before one, since its close-to-close lands on a T+1.
    p["next_is_t1"] = g["is_t1"].shift(-1)
    p = p[~p["is_t1"].fillna(False) & ~p["next_is_t1"].fillna(False)]
    n2 = len(p)
    p = p[p["next_close"].notna() & (p["atr14"] > 0)
          & (p["open"] > 0) & (p["close"] > 0)].copy()
    n3 = len(p)
    p = p[p["date"] != SEAM].copy()
    n_seam = n3 - len(p)
    log(f"ordinary sessions: {n0:,} → {n1:,} liquid → {n2:,} non-earnings "
        f"→ {n3:,} usable → {len(p):,} after dropping {n_seam} seam rows")

    day = (p["close"] / p["open"] - 1.0).to_numpy(float)
    on = (p["next_close"] / p["close"] - 1.0).to_numpy(float)
    atr_r = on * p["close"].to_numpy(float) / p["atr14"].to_numpy(float)

    winner = day > 0
    rows = []
    for name, m in (("Winners on day T", winner),
                    ("Losers on day T", ~winner),
                    ("All sessions", np.ones(len(p), dtype=bool))):
        rows.append(shape(pd.Series(on[m]), pd.Series(atr_r[m]),
                          p.loc[m, "date"], {"group": name}))
        rows[-1]["mean_day_bps"] = float(day[m].mean() * 1e4)
    R = {"o_perf": pd.DataFrame(rows)}

    meta = {"n_sessions": int(len(p)), "n_tickers": int(p["ticker"].nunique()),
            "start": str(p["date"].min().date()),
            "end": str(p["date"].max().date()),
            "n_raw": n0, "n_liquid": n1, "n_nonearn": n2, "n_seam": n_seam}
    R["o_meta"] = pd.DataFrame([meta])

    # The largest surviving moves, so the reader can confirm the remaining
    # tail is real market history and not more broken data.
    top = p.reindex(pd.Series(np.abs(on), index=p.index)
                    .sort_values(ascending=False).index[:8])
    R["o_extremes"] = pd.DataFrame({
        "ticker": top["ticker"].to_numpy(),
        "date": [str(d.date()) for d in top["date"]],
        "close": top["close"].to_numpy(),
        "next_close": top["next_close"].to_numpy(),
        "ret_bps": (top["next_close"].to_numpy() / top["close"].to_numpy()
                    - 1.0) * 1e4,
    })
    return R


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    R = {**test_earnings(), **test_ordinary()}

    meta = {"cost_bps": COST_BPS, "vol_mult": VOL_MULT,
            "vol_window": VOL_WINDOW, "start": START, "end": END}
    for k, v in R.items():
        v.to_csv(OUT_DIR / f"on_{k}.csv", index=False)
    FEED.write_text(json.dumps(
        {"meta": meta, **{k: json.loads(v.round(6).to_json(orient="records"))
                          for k, v in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables")

    from overnight_text import build  # noqa: E402
    REPORT.write_text(build(R, meta))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
