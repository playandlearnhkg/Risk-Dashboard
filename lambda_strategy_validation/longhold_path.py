"""
longhold_path.py — two tests on the strongest post-earnings setup
(High Volume + Continuation, entry at the open of the 09:35 bar).

TEST 1 — longer holding periods
  1 hour (10:35), 2 hours (11:35), until 12:00, until the close (16:00).
  The close uses the session's official closing price, not an intraday
  bar, so the "until close" trade is a real marked-to-close exit.

TEST 2 — path dependence conditional on the 5-minute mark
  Group A = trades profitable at 09:40; Group B = trades losing at 09:40.
  Their behaviour is then followed to 10 min, 15 min and 1 hour.

  MEASUREMENT-ERROR CAVEAT, and why there are two subsequent-return
  columns. Splitting on the sign of the 09:40 return and then measuring
  the move *from that same 09:40 print* shares one price between the
  classifier and the outcome. Whatever noise sits in that print -- a
  trade at the offer rather than the bid -- enters the classification
  positively and the subsequent return negatively. That alone
  manufactures apparent mean reversion, with no economics behind it.

  So the subsequent return is computed twice:
      sub_m9   from the 09:40 close   (shares the classifying price)
      sub_o10  from the 09:40 bar's next open (one minute later, so the
               classifier and the outcome share no print)
  The difference between the two is an estimate of the bounce artefact.
  Only sub_o10 supports a claim about what happens next.

Everything else -- universe, signal, entry, guards, volume definition,
cost, clustered inference -- is imported unchanged from volume_test.py.

Run: python3 lambda_strategy_validation/longhold_path.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import analysis as A  # noqa: E402
from volume_test import (  # noqa: E402
    COST_BPS, N_BOOT, SMALL, VOL_MULT, VOL_WINDOW, finalize, log,
    prep_earnings, volume_features,
)
from winrate_report import wilson  # noqa: E402

BASE = Path("/home/user/lambda_data")
OUT_DIR = BASE / "tables"
FEED = BASE / "longpath_feed.json"
REPORT_LONG = Path(__file__).resolve().parent / "LONGHOLD_REPORT.md"
REPORT_PATH = Path(__file__).resolve().parent / "PATH_REPORT.md"

CONT = "Continuation (1st candle with gap)"

# minute index k = close of the bar starting 09:30+k, so the clock time is
# 09:30 + k + 1 minutes.
LONG_WINDOWS = {"1 hour (10:35)": 64, "2 hours (11:35)": 124,
                "Until 12:00": 149}
CLOSE_LABEL = "Until close (16:00)"

MARK = 9                       # 09:40, the conditioning point
PATH_WINDOWS = {"10 min (09:45)": 14, "15 min (09:50)": 19,
                "1 hour (10:35)": 64}


def core(s: pd.Series, dates: pd.Series, label: dict) -> dict:
    """n, win rate, avg win/loss, payoff, net expectancy, quantiles."""
    n = len(s)
    k = int((s > 0).sum())
    lo, hi = wilson(k, n)
    bn = A.clustered_bootstrap(s - COST_BPS / 1e4, dates, n_boot=N_BOOT)
    wins, losses = s[s > 0], s[s < 0]
    aw = wins.mean() * 1e4 if len(wins) else np.nan
    al = -losses.mean() * 1e4 if len(losses) else np.nan
    b = s * 1e4
    q = b.quantile([0.10, 0.25, 0.50, 0.75, 0.90])
    rec = dict(label)
    rec.update({
        "n": n, "n_dates": int(pd.Series(dates).nunique()),
        "win_rate": k / n if n else np.nan, "wilson_lo": lo, "wilson_hi": hi,
        "avg_win_bps": aw, "avg_loss_bps": al,
        "payoff_ratio": (aw / al) if al else np.nan,
        "mean_bps": float(b.mean()),
        "net_bps": bn["stat"] * 1e4, "net_p": bn["p"],
        "net_ci_lo": bn["lo"] * 1e4, "net_ci_hi": bn["hi"] * 1e4,
        "median_bps": float(q.loc[0.50]), "p10_bps": float(q.loc[0.10]),
        "p25_bps": float(q.loc[0.25]), "p75_bps": float(q.loc[0.75]),
        "p90_bps": float(q.loc[0.90]), "std_bps": float(b.std()),
        "small": "YES" if n < SMALL else "",
    })
    return rec


# ---------------------------------------------------------------------------
# TEST 1
# ---------------------------------------------------------------------------

def test_long(df: pd.DataFrame, hv: pd.DataFrame) -> dict[str, pd.DataFrame]:
    entry = df["entry_px"]
    gs = pd.Series(np.where(df["gap_up"], 1.0, -1.0), index=df.index)

    targets = [(name, df[f"m{k}"]) for name, k in LONG_WINDOWS.items()]
    targets.append((CLOSE_LABEL, df["session_close"]))

    rows = []
    for wname, px in targets:
        r = (gs * (px / entry - 1.0)).reindex(hv.index).dropna()
        r = r[r != 0]
        rows.append(core(r, df.loc[r.index, "date"], {"window": wname}))
    R = {"long": pd.DataFrame(rows)}

    # Marginal contribution of each extra leg of holding time: what the
    # position earns between one exit point and the next.
    rows = []
    prev_name, prev_px = "Entry (09:35)", entry
    for wname, px in targets:
        r = (gs * (px / prev_px - 1.0)).reindex(hv.index).dropna()
        b = A.clustered_bootstrap(r, df.loc[r.index, "date"], n_boot=N_BOOT)
        rows.append({"leg": f"{prev_name} → {wname}", "n": int(len(r)),
                     "gross_bps": b["stat"] * 1e4, "p": b["p"],
                     "lo": b["lo"] * 1e4, "hi": b["hi"] * 1e4,
                     "win_rate": float((r > 0).mean()),
                     "median_bps": float(r.median() * 1e4)})
        prev_name, prev_px = wname, px
    R["legs"] = pd.DataFrame(rows)
    return R


# ---------------------------------------------------------------------------
# TEST 2
# ---------------------------------------------------------------------------

def test_path(df: pd.DataFrame, hv: pd.DataFrame) -> dict[str, pd.DataFrame]:
    entry = df["entry_px"]
    gs = pd.Series(np.where(df["gap_up"], 1.0, -1.0), index=df.index)

    r5 = (gs * (df[f"m{MARK}"] / entry - 1.0)).reindex(hv.index)
    r5 = r5.dropna()
    r5 = r5[r5 != 0]
    gA = r5[r5 > 0].index      # profitable at 09:40
    gB = r5[r5 < 0].index      # losing at 09:40
    log(f"5-min split: A (winners) {len(gA):,}, B (losers) {len(gB):,}")

    px5 = df[f"m{MARK}"]
    px5b = df[f"o{MARK + 1}"]          # next print, breaks the shared price

    rows, tr = [], []
    for wname, wk in PATH_WINDOWS.items():
        px = df[f"m{wk}"]
        cum = gs * (px / entry - 1.0)
        sub9 = gs * (px / px5 - 1.0)
        sub10 = gs * (px / px5b - 1.0)
        for gname, idx in (("A — winning at 09:40", gA),
                           ("B — losing at 09:40", gB)):
            c = cum.reindex(idx).dropna()
            c = c[c != 0]
            if len(c) < 30:
                continue
            rec = core(c, df.loc[c.index, "date"],
                       {"window": wname, "group": gname})
            # gross-profitable vs profitable after costs: the question
            # "still profitable" has two defensible answers, so give both.
            rec["pct_gross_pos"] = float((c > 0).mean())
            rec["pct_net_pos"] = float((c > COST_BPS / 1e4).mean())
            s9 = sub9.reindex(c.index).dropna()
            s10 = sub10.reindex(c.index).dropna()
            b9 = A.clustered_bootstrap(s9, df.loc[s9.index, "date"],
                                       n_boot=N_BOOT)
            b10 = A.clustered_bootstrap(s10, df.loc[s10.index, "date"],
                                        n_boot=N_BOOT)
            rec.update({
                "sub_m9_bps": b9["stat"] * 1e4, "sub_m9_p": b9["p"],
                "sub_o10_bps": b10["stat"] * 1e4, "sub_o10_p": b10["p"],
                "sub_o10_lo": b10["lo"] * 1e4, "sub_o10_hi": b10["hi"] * 1e4,
                "sub_m9_median": float(s9.median() * 1e4),
                "sub_o10_median": float(s10.median() * 1e4),
                "sub_o10_win": float((s10 > 0).mean()),
                "n_sub_o10": int(len(s10)),
            })
            rows.append(rec)

            tr.append({"window": wname, "group": gname, "n": int(len(c)),
                       "pct_pos": float((c > 0).mean()),
                       "pct_net_pos": float((c > COST_BPS / 1e4).mean())})
    R = {"path": pd.DataFrame(rows), "transition": pd.DataFrame(tr)}

    # Reference: the unconditional cohort at the same horizons, so the
    # conditional numbers can be read against a baseline.
    rows = []
    for wname, wk in PATH_WINDOWS.items():
        c = (gs * (df[f"m{wk}"] / entry - 1.0)).reindex(r5.index).dropna()
        c = c[c != 0]
        rows.append(core(c, df.loc[c.index, "date"],
                         {"window": wname, "group": "All (unconditional)"}))
    R["baseline"] = pd.DataFrame(rows)

    # Magnitude of the 5-minute move matters as much as its sign: a trade
    # 2 bps up is not the same signal as one 80 bps up.
    rows = []
    q = r5.quantile([0.25, 0.5, 0.75])
    buckets = [("Losing, worse than p25", -np.inf, q.loc[0.25]),
               ("Losing, mild", q.loc[0.25], 0.0),
               ("Winning, mild", 0.0, q.loc[0.75]),
               ("Winning, better than p75", q.loc[0.75], np.inf)]
    for wname, wk in PATH_WINDOWS.items():
        cum = gs * (df[f"m{wk}"] / entry - 1.0)
        sub10 = gs * (df[f"m{wk}"] / px5b - 1.0)
        for bname, blo, bhi in buckets:
            idx = r5[(r5 > blo) & (r5 <= bhi)].index
            c = cum.reindex(idx).dropna()
            c = c[c != 0]
            if len(c) < 30:
                continue
            s10 = sub10.reindex(c.index).dropna()
            b10 = A.clustered_bootstrap(s10, df.loc[s10.index, "date"],
                                        n_boot=N_BOOT)
            rows.append({"window": wname, "bucket": bname, "n": int(len(c)),
                         "mean_5min_bps": float(r5.reindex(idx).mean() * 1e4),
                         "cum_mean_bps": float(c.mean() * 1e4),
                         "cum_win": float((c > 0).mean()),
                         "sub_o10_bps": b10["stat"] * 1e4,
                         "sub_o10_p": b10["p"]})
    R["by_magnitude"] = pd.DataFrame(rows)
    R["split"] = pd.DataFrame([{
        "n_classified": int(len(r5)), "n_win": int(len(gA)),
        "n_lose": int(len(gB)), "pct_win": float(len(gA) / len(r5)),
        "mean_5min_win_bps": float(r5.reindex(gA).mean() * 1e4),
        "mean_5min_lose_bps": float(r5.reindex(gB).mean() * 1e4),
        "p25_5min_bps": float(q.loc[0.25] * 1e4),
        "p75_5min_bps": float(q.loc[0.75] * 1e4),
    }])
    return R


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    vol = volume_features()
    log("volume features built")

    df, meta = finalize(prep_earnings(vol), "Post-Earnings (T+1)")
    hv = df[(df["pattern"] == CONT) & df["high_vol"]]
    log(f"HV continuation n={len(hv):,}")
    meta.update({"cost_bps": COST_BPS, "small": SMALL, "vol_mult": VOL_MULT,
                 "vol_window": VOL_WINDOW, "n_hv_cont": int(len(hv))})

    R = {**test_long(df, hv), **test_path(df, hv)}
    for k, v in R.items():
        v.to_csv(OUT_DIR / f"lp_{k}.csv", index=False)
    FEED.write_text(json.dumps(
        {"meta": meta, **{k: json.loads(v.round(6).to_json(orient="records"))
                          for k, v in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables")

    from longhold_path_text import build_long, build_path  # noqa: E402
    REPORT_LONG.write_text(build_long(R, meta))
    REPORT_PATH.write_text(build_path(R, meta))
    log(f"wrote {REPORT_LONG} and {REPORT_PATH}")


if __name__ == "__main__":
    main()
