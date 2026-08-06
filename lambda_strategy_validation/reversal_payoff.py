"""
reversal_payoff.py — Part 1: the Reversal side of the first-candle signal.
Part 2: average win / average loss / payoff ratio for Continuation, split
by Gap/ATR.

Entry, rules and look-ahead guards are identical to entry0935.py: signal
from the 09:30-09:35 candle, entry at the OPEN of the 09:35 bar, prior-day
ATR(14), events with no real print by 09:35 dropped.

SIGN CONVENTION — the one judgement call in this report, stated plainly.

  For the CONTINUATION cohort the trade is in the gap direction, as before.

  For the REVERSAL cohort the first candle closed AGAINST the gap, so the
  natural tradeable rule is "follow the candle", i.e. trade AGAINST the
  gap. All Reversal figures here are therefore signed in the CANDLE's
  direction:

      reversal_return = -sign(gap) * (P_end / P_entry - 1)

  Under that convention both cohorts express the same single rule — follow
  the first 5-minute candle — so their numbers are directly comparable.
  The gap-direction view of the same events is simply the negative of
  every Reversal figure below.

Run: python3 lambda_strategy_validation/reversal_payoff.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import analysis as A  # noqa: E402
from entry0935 import (  # noqa: E402
    ATR_BUCKETS, COST_BPS, CONT, ENTRY_MIN, N_BOOT, SIGNAL_MIN, SMALL,
    WINDOWS, load_wide,
)
from winrate_report import simple_first_candle, wilson  # noqa: E402

BASE = Path("/home/user/lambda_data")
OUT_DIR = BASE / "tables"
FEED = BASE / "revpay_feed.json"
REPORT = Path(__file__).resolve().parent / "REVERSAL_PAYOFF_REPORT.md"

REV = "Reversal (1st candle against gap)"
PAYOFF_WINDOWS = ["09:35 -> 09:40", "09:35 -> 09:45", "09:35 -> 09:50"]


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def stat_row(s: pd.Series, dates: pd.Series, label: dict) -> dict:
    n = len(s)
    k = int((s > 0).sum())
    lo, hi = wilson(k, n)
    b = A.clustered_bootstrap(s, dates, n_boot=N_BOOT)
    bn = A.clustered_bootstrap(s - COST_BPS / 1e4, dates, n_boot=N_BOOT)
    wins, losses = s[s > 0], s[s < 0]
    aw = wins.mean() * 1e4 if len(wins) else np.nan
    al = -losses.mean() * 1e4 if len(losses) else np.nan
    rec = dict(label)
    rec.update({"n": n, "win_rate": k / n if n else np.nan,
                "wilson_lo": lo, "wilson_hi": hi,
                "avg_win_bps": aw, "avg_loss_bps": al,
                "payoff_ratio": (aw / al) if al else np.nan,
                "gross_bps": b["stat"] * 1e4, "gross_p": b["p"],
                "net_bps": bn["stat"] * 1e4, "net_p": bn["p"],
                "net_ci_lo": bn["lo"] * 1e4, "net_ci_hi": bn["hi"] * 1e4,
                "small": "YES" if n < SMALL else ""})
    return rec


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ev = pd.read_parquet(BASE / "events.parquet")
    ev["date"] = pd.to_datetime(ev["date"])
    ev = ev[ev["gap"] != 0].copy()
    ev["gap_up"] = ev["gap"] > 0
    ev["pattern_simple"] = ev.apply(simple_first_candle, axis=1)

    panel = pd.read_parquet(BASE / "panel.parquet",
                            columns=["ticker", "date", "atr14"])
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel.sort_values(["ticker", "date"])
    panel["atr14_prev"] = panel.groupby("ticker")["atr14"].shift(1)
    ev = ev.merge(panel[["ticker", "date", "atr14_prev"]],
                  on=["ticker", "date"], how="left")

    wide = load_wide(ev)
    df = ev.merge(wide, on=["ticker", "date"], how="inner", suffixes=("", "_p"))
    df = df[df["session_open"].notna() & df["session_close"].notna()]

    early = [f"o{i}" for i in range(0, ENTRY_MIN + 1) if f"o{i}" in df.columns]
    df = df[df[early].notna().any(axis=1)].copy()
    df["entry_px"] = df[f"o{ENTRY_MIN}"].fillna(df[f"m{SIGNAL_MIN}"])
    df = df[df["entry_px"].notna()].copy()
    log(f"events after look-ahead guard: {len(df):,}")

    prev_close = df["open"] / (1.0 + df["gap"])
    df["gap_atr"] = (df["open"] - prev_close).abs() / df["atr14_prev"]

    entry = df["entry_px"]
    gap_sign = pd.Series(np.where(df["gap_up"], 1.0, -1.0), index=df.index)
    rev = df[df["pattern_simple"] == REV]
    cont = df[df["pattern_simple"] == CONT]
    log(f"Reversal n={len(rev):,}  Continuation n={len(cont):,}")

    R: dict[str, pd.DataFrame] = {}

    # ---------- PART 1A: reversal holding periods ----------
    rows = []
    for wname, wmin in WINDOWS.items():
        end = df["session_close"] if wmin is None else df[f"m{wmin}"]
        raw = (end / entry - 1.0)
        # signed in the CANDLE direction = against the gap
        r_ret = -gap_sign * raw
        for cname, sub in (("All Reversal", rev),
                           ("Gap Up Reversal", rev[rev["gap_up"]]),
                           ("Gap Down Reversal", rev[~rev["gap_up"]])):
            s = r_ret.reindex(sub.index).dropna()
            s = s[s != 0]
            if len(s) < 30:
                continue
            rows.append(stat_row(s, df.loc[s.index, "date"],
                                 {"window": wname, "cohort": cname}))
    R["p1a_reversal_holding"] = pd.DataFrame(rows)

    # ---------- PART 1B: reversal x Gap/ATR ----------
    rows = []
    for wname, wmin in WINDOWS.items():
        end = df["session_close"] if wmin is None else df[f"m{wmin}"]
        r_ret = -gap_sign * (end / entry - 1.0)
        for bname, lo_v, hi_v in ATR_BUCKETS:
            sub = rev[(rev["gap_atr"] >= lo_v) & (rev["gap_atr"] < hi_v)]
            s = r_ret.reindex(sub.index).dropna()
            s = s[s != 0]
            if len(s) < 30:
                continue
            rows.append(stat_row(s, df.loc[s.index, "date"],
                                 {"window": wname, "bucket": bname}))
    R["p1b_reversal_gapatr"] = pd.DataFrame(rows)

    # ---------- PART 2: continuation payoff by Gap/ATR ----------
    rows = []
    for wname in PAYOFF_WINDOWS:
        wmin = WINDOWS[wname]
        end = df["session_close"] if wmin is None else df[f"m{wmin}"]
        c_ret = gap_sign * (end / entry - 1.0)
        for bname, lo_v, hi_v in ATR_BUCKETS:
            sub = cont[(cont["gap_atr"] >= lo_v) & (cont["gap_atr"] < hi_v)]
            s = c_ret.reindex(sub.index).dropna()
            s = s[s != 0]
            if len(s) < 30:
                continue
            rows.append(stat_row(s, df.loc[s.index, "date"],
                                 {"window": wname, "bucket": bname}))
    R["p2_continuation_payoff"] = pd.DataFrame(rows)

    # ---------- final comparison ----------
    rows = []
    for wname in PAYOFF_WINDOWS:
        wmin = WINDOWS[wname]
        end = df["session_close"] if wmin is None else df[f"m{wmin}"]
        raw = (end / entry - 1.0)
        for bname, lo_v, hi_v in ATR_BUCKETS:
            for side, sub, sgn in (("Continuation", cont, gap_sign),
                                   ("Reversal", rev, -gap_sign)):
                m = sub[(sub["gap_atr"] >= lo_v) & (sub["gap_atr"] < hi_v)]
                s = (sgn * raw).reindex(m.index).dropna()
                s = s[s != 0]
                if len(s) < 30:
                    continue
                rows.append(stat_row(s, df.loc[s.index, "date"],
                                     {"window": wname, "bucket": bname,
                                      "side": side}))
    R["p3_compare"] = pd.DataFrame(rows)

    # ---------- supplementary: gap direction only, candle ignored ----------
    # The Part 1B result implies the candle may not be the operative signal
    # on large gaps. Measure the no-filter gap-direction trade for reference.
    rows = []
    for wname in PAYOFF_WINDOWS:
        wmin = WINDOWS[wname]
        end = df["session_close"] if wmin is None else df[f"m{wmin}"]
        g_ret = gap_sign * (end / entry - 1.0)
        for bname, lo_v, hi_v in ATR_BUCKETS:
            # Restrict to events whose first candle is classifiable: an event
            # with no 09:30-09:35 candle could not be traded by ANY of these
            # rules, so including it would not be a like-for-like universe.
            # (208 such events average -98 to -416 bps and would flatter the
            # candle filter by dragging the no-filter baseline down.)
            sub = df[(df["gap_atr"] >= lo_v) & (df["gap_atr"] < hi_v)
                     & df["pattern_simple"].notna()]
            s = g_ret.reindex(sub.index).dropna()
            s = s[s != 0]
            if len(s) < 30:
                continue
            rows.append(stat_row(s, df.loc[s.index, "date"],
                                 {"window": wname, "bucket": bname,
                                  "side": "Gap direction, no candle filter"}))
    R["p4_gapdir"] = pd.DataFrame(rows)

    meta = {"n_events": int(len(df)), "n_rev": int(len(rev)),
            "n_cont": int(len(cont)), "cost_bps": COST_BPS, "small": SMALL}
    for k, v in R.items():
        v.to_csv(OUT_DIR / f"rp_{k}.csv", index=False)
    (BASE / "revpay_meta.json").write_text(json.dumps(meta, indent=1))
    FEED.write_text(json.dumps(
        {"meta": meta, **{k: json.loads(v.round(6).to_json(orient="records"))
                          for k, v in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables")

    from reversal_text import build  # noqa: E402
    REPORT.write_text(build(R, meta))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
