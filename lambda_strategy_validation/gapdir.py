"""
gapdir.py — High Volume signals split by GAP DIRECTION (up vs down),
post-earnings universe only.

Four groups, all conditioned on High Volume:

    1. High Volume + Continuation + Gap Up      (long,  with the gap)
    2. High Volume + Continuation + Gap Down    (short, with the gap)
    3. High Volume + Reversal + Gap Up          (short, with the candle)
    4. High Volume + Reversal + Gap Down        (long,  with the candle)

plus the "fade the candle" read of groups 3 and 4 — the same Reversal
events traded in the GAP direction instead of the candle direction.

Definitions, entry, guards, cost and volume machinery are imported
unchanged from volume_test.py so this is a pure re-cut of the same events.

SIGN CONVENTION (unchanged from the earlier reports)
  Continuation returns are signed in the GAP direction.
  Reversal returns are signed in the CANDLE direction (= against the gap).
  Both therefore express one rule: follow the first 5-minute candle.
  The "fade the candle" table re-signs the Reversal events in the gap
  direction. Costs do NOT flip with the sign — the 6.6 bps round trip is
  paid on either side — so a fade figure is not the negative of the
  follow figure.

MARKET-DRIFT CONTROL
  A gap-up continuation trade is long and a gap-down continuation trade is
  short, so any index drift over the holding window is added to one group
  and subtracted from the other. That is a mechanical asymmetry, not a
  signal property, and on a 2021-2025 sample it flatters the long side.
  Each group therefore also carries a beta-1 SPY-adjusted expectancy:

      adjusted = raw - direction x SPY return over the same clock window

  Beta-1, not a fitted beta — it removes the drift, not the exposure.

Run: python3 lambda_strategy_validation/gapdir.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import analysis as A  # noqa: E402
from volume_test import (  # noqa: E402
    COST_BPS, ENTRY_MIN, N_BOOT, SIGNAL_MIN, SMALL, VOL_MULT, VOL_WINDOW,
    finalize, log, prep_earnings, volume_features,
)
from winrate_report import wilson  # noqa: E402

BASE = Path("/home/user/lambda_data")
OUT_DIR = BASE / "tables"
FEED = BASE / "gapdir_feed.json"
REPORT = Path(__file__).resolve().parent / "GAPDIR_REPORT.md"

CONT = "Continuation (1st candle with gap)"
REV = "Reversal (1st candle against gap)"

# Only the two horizons asked for.
WINDOWS = {"15 min (09:50)": 19, "1 hour (10:35)": 64}


def bench_returns() -> pd.DataFrame:
    """SPY return from the entry minute to each window end, per date.

    Entry is the open of the 09:35 bar; the benchmark file carries closes
    only, so the close of the 09:34 bar is used as the entry proxy. Over a
    one-minute gap on SPY that distinction is immaterial to a drift
    control.
    """
    b = pd.read_parquet(BASE / "bench_intraday.parquet")
    b = b[b["bench"] == "SPY"]
    b["date"] = pd.to_datetime(b["date"])
    w = b.pivot_table(index="date", columns="minute", values="close",
                      aggfunc="last")
    out = pd.DataFrame(index=w.index)
    entry = w[SIGNAL_MIN]
    for wname, wmin in WINDOWS.items():
        if wmin in w.columns:
            out[f"spy_{wmin}"] = w[wmin] / entry - 1.0
    return out.reset_index()


def stat_row(s: pd.Series, dates: pd.Series, label: dict,
             adj: pd.Series | None = None) -> dict:
    """Win rate, expectancy, payoff — clustered by calendar date."""
    n = len(s)
    k = int((s > 0).sum())
    lo, hi = wilson(k, n)
    b = A.clustered_bootstrap(s, dates, n_boot=N_BOOT)
    bn = A.clustered_bootstrap(s - COST_BPS / 1e4, dates, n_boot=N_BOOT)
    wins, losses = s[s > 0], s[s < 0]
    aw = wins.mean() * 1e4 if len(wins) else np.nan
    al = -losses.mean() * 1e4 if len(losses) else np.nan
    rec = dict(label)
    rec.update({"n": n, "n_dates": int(pd.Series(dates).nunique()),
                "win_rate": k / n if n else np.nan,
                "wilson_lo": lo, "wilson_hi": hi,
                "avg_win_bps": aw, "avg_loss_bps": al,
                "payoff_ratio": (aw / al) if al else np.nan,
                "gross_bps": b["stat"] * 1e4, "gross_p": b["p"],
                "net_bps": bn["stat"] * 1e4, "net_p": bn["p"],
                "net_ci_lo": bn["lo"] * 1e4, "net_ci_hi": bn["hi"] * 1e4,
                "small": "YES" if n < SMALL else ""})
    if adj is not None:
        a = adj.reindex(s.index).dropna()
        if len(a) >= 30:
            ba = A.clustered_bootstrap(a - COST_BPS / 1e4,
                                       pd.Series(dates).reindex(a.index),
                                       n_boot=N_BOOT)
            rec["net_adj_bps"] = ba["stat"] * 1e4
            rec["net_adj_p"] = ba["p"]
            rec["n_adj"] = int(len(a))
        else:
            rec["net_adj_bps"] = np.nan
            rec["net_adj_p"] = np.nan
            rec["n_adj"] = int(len(a))
    return rec


def run(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    entry = df["entry_px"]
    gs = pd.Series(np.where(df["gap_up"], 1.0, -1.0), index=df.index)
    hv = df["high_vol"]

    cont_u = df[(df["pattern"] == CONT) & hv & df["gap_up"]]
    cont_d = df[(df["pattern"] == CONT) & hv & ~df["gap_up"]]
    rev_u = df[(df["pattern"] == REV) & hv & df["gap_up"]]
    rev_d = df[(df["pattern"] == REV) & hv & ~df["gap_up"]]
    log(f"high-volume cells: cont/up {len(cont_u):,}, cont/down "
        f"{len(cont_d):,}, rev/up {len(rev_u):,}, rev/down {len(rev_d):,}")

    R: dict[str, pd.DataFrame] = {}

    def rows_for(spec, table_label):
        rows = []
        for wname, wmin in WINDOWS.items():
            raw = df[f"m{wmin}"] / entry - 1.0
            spy = df[f"spy_{wmin}"]
            for gname, sub, sign in spec:
                d = sign * raw
                a = sign * (raw - spy)
                s = d.reindex(sub.index).dropna()
                s = s[s != 0]
                if len(s) < 30:
                    continue
                rows.append(stat_row(
                    s, df.loc[s.index, "date"],
                    {"table": table_label, "window": wname, "group": gname},
                    adj=a))
        return pd.DataFrame(rows)

    # --- 1. the four requested groups, signed "follow the first candle" ---
    R["main"] = rows_for([
        ("HV + Continuation + Gap Up", cont_u, gs),
        ("HV + Continuation + Gap Down", cont_d, gs),
        ("HV + Reversal + Gap Up", rev_u, -gs),
        ("HV + Reversal + Gap Down", rev_d, -gs),
    ], "main")

    # --- 2. fade the candle: same Reversal events, gap direction ---
    R["fade"] = rows_for([
        ("Fade Reversal + Gap Up (stay long the gap)", rev_u, gs),
        ("Fade Reversal + Gap Down (stay short the gap)", rev_d, gs),
    ], "fade")

    # --- 3. Normal/Low volume controls, same four cells ---
    lv = ~df["high_vol"]
    R["control"] = rows_for([
        ("LV + Continuation + Gap Up",
         df[(df["pattern"] == CONT) & lv & df["gap_up"]], gs),
        ("LV + Continuation + Gap Down",
         df[(df["pattern"] == CONT) & lv & ~df["gap_up"]], gs),
        ("LV + Reversal + Gap Up",
         df[(df["pattern"] == REV) & lv & df["gap_up"]], -gs),
        ("LV + Reversal + Gap Down",
         df[(df["pattern"] == REV) & lv & ~df["gap_up"]], -gs),
    ], "control")

    # --- 4. are the up and down cohorts comparable? ---
    comp = []
    for cname, sub in (("HV + Continuation + Gap Up", cont_u),
                       ("HV + Continuation + Gap Down", cont_d),
                       ("HV + Reversal + Gap Up", rev_u),
                       ("HV + Reversal + Gap Down", rev_d)):
        comp.append({
            "group": cname, "n": len(sub),
            "median_abs_gap_bps": float(sub["gap"].abs().median() * 1e4),
            "median_gap_atr": float(sub["gap_atr"].median()),
            "median_vol_ratio": float(sub["vol_ratio"].median()),
            "median_entry_px": float(sub["entry_px"].median()),
            "start": str(sub["date"].min().date()),
            "end": str(sub["date"].max().date()),
        })
    R["profile"] = pd.DataFrame(comp)

    # --- 5. gap-direction mix per year: is the split time-concentrated? ---
    hvs = df[hv & df["pattern"].isin([CONT, REV])].copy()
    hvs["year"] = hvs["date"].dt.year
    yr = (hvs.assign(up=hvs["gap_up"].astype(int))
          .groupby(["year", "pattern"])["up"]
          .agg(n="size", n_up="sum").reset_index())
    yr["pct_up"] = yr["n_up"] / yr["n"]
    R["byyear"] = yr

    # --- 6. SPY drift actually present over each window ---
    drift = []
    for wname, wmin in WINDOWS.items():
        for dname, sub in (("Gap Up days", df[df["gap_up"]]),
                           ("Gap Down days", df[~df["gap_up"]])):
            s = sub[f"spy_{wmin}"].dropna()
            if len(s) < 30:
                continue
            drift.append({"window": wname, "cohort": dname, "n": len(s),
                          "mean_spy_bps": float(s.mean() * 1e4),
                          "median_spy_bps": float(s.median() * 1e4)})
    R["drift"] = pd.DataFrame(drift)
    return R


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    vol = volume_features()
    log("volume features built")

    df, meta = finalize(prep_earnings(vol), "Post-Earnings (T+1)")
    df = df.merge(bench_returns(), on="date", how="left")
    log(f"benchmark merged, spy coverage "
        f"{df['spy_19'].notna().mean()*100:.1f}%")

    hv = df[df["high_vol"] & df["pattern"].isin([CONT, REV])]
    meta.update({
        "cost_bps": COST_BPS, "small": SMALL, "vol_mult": VOL_MULT,
        "vol_window": VOL_WINDOW, "entry_min": ENTRY_MIN,
        "n_hv_signals": int(len(hv)),
        "pct_gap_up_all": float(df["gap_up"].mean()),
        "pct_gap_up_hv": float(hv["gap_up"].mean()),
        "spy_coverage": float(df["spy_19"].notna().mean()),
    })

    out = run(df)
    for k, v in out.items():
        v.to_csv(OUT_DIR / f"gapdir_{k}.csv", index=False)
    FEED.write_text(json.dumps(
        {"meta": meta, **{k: json.loads(v.round(6).to_json(orient="records"))
                          for k, v in out.items()}}, separators=(",", ":")))
    log(f"wrote {len(out)} tables")

    from gapdir_text import build  # noqa: E402
    REPORT.write_text(build(out, meta))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
