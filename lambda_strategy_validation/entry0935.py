"""
entry0935.py — Re-test with entry at 09:35, immediately after the first
5-minute candle closes.

STRICT NO-LOOK-AHEAD
  Signal : the 09:30-09:35 candle closes in the gap direction.
  Entry  : the OPEN of the 09:35 bar (minute 5) — the first print AFTER
           the signal candle has completed.

           This is deliberately more conservative than transacting at
           `c1_close`. The signal is derived from `c1_close`, so filling at
           that same print would mean buying the exact tick that generated
           the signal: if that print sat on the offer, the rule selects for
           an upward-biased entry price and the measured forward return
           inherits the reversal. Taking the next bar's open removes that
           overlap entirely — signal and fill are separate prints.

           Where minute 5 has no trade, the prevailing (forward-filled)
           price is used instead, which is what a trader would face.
  SPY / sector : Open -> 09:35 only (benchmark m4 close / session open - 1).
  Stage  : prior session.
  ATR    : prior-session ATR(14); Gap/ATR uses the overnight gap in price
           terms divided by that ATR. Both terms known before the open.

WINDOWS (all from 09:35): 09:40 = m9, 09:45 = m14, 09:50 = m19,
10:35 = m64, Close = session close.

Run: python3 lambda_strategy_validation/entry0935.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import analysis as A  # noqa: E402
from tradeable_report import load_bench_0945  # noqa: E402
from winrate_report import simple_first_candle, wilson  # noqa: E402

BASE = Path("/home/user/lambda_data")
INTRADAY_DIR = BASE / "intraday210"
OUT_DIR = BASE / "tables"
FEED = BASE / "entry35_feed.json"
REPORT = Path(__file__).resolve().parent / "ENTRY_0935_REPORT.md"

ENTRY_MIN = 5              # the 09:35 bar; entry = its OPEN
SIGNAL_MIN = 4             # close of the 09:34 bar == c1_close (signal only)
BENCH_MIN = 4              # SPY/sector measured Open -> 09:35
MAX_MIN = 210
N_BOOT = 1000
SMALL = 150
COST_BPS = 6.6             # median round-trip cost established earlier

WINDOWS = {"09:35 -> 09:40": 9, "09:35 -> 09:45": 14, "09:35 -> 09:50": 19,
           "09:35 -> 10:35": 64, "09:35 -> Close": None}
DIST_WINDOWS = ["09:35 -> 09:40", "09:35 -> 09:45", "09:35 -> 09:50"]
ATR_BUCKETS = [("Gap/ATR < 1.0", -np.inf, 1.0), ("Gap/ATR 1.0-2.0", 1.0, 2.0),
               ("Gap/ATR > 2.0", 2.0, np.inf)]
CONT = "Continuation (1st candle with gap)"


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def load_wide(ev: pd.DataFrame) -> pd.DataFrame:
    want = set(zip(ev["ticker"], ev["date"]))
    frames = []
    files = sorted(INTRADAY_DIR.glob("*.parquet"))
    for i, f in enumerate(files, 1):
        try:
            d = pd.read_parquet(f)
        except Exception:  # noqa: BLE001
            continue
        if d.empty:
            continue
        d["date"] = pd.to_datetime(d["date"])
        d = d[[(t, dt) in want for t, dt in zip(d["ticker"], d["date"])]]
        if not d.empty:
            frames.append(d)
        if i % 250 == 0:
            log(f"  {i}/{len(files)} files")
    raw = pd.concat(frames, ignore_index=True)
    wide = raw.pivot_table(index=["ticker", "date"], columns="minute",
                           values="close", aggfunc="last").reindex(
                               columns=range(MAX_MIN))
    sess = raw.groupby(["ticker", "date"])[["session_open", "session_close"]].first()
    wide.insert(0, "seed", sess["session_open"])
    wide = wide.ffill(axis=1).drop(columns="seed")
    wide.columns = [f"m{int(c)}" for c in wide.columns]

    # Opens are needed because the entry is the OPEN of the 09:35 bar, not a
    # close. They are NOT forward-filled: a minute with no trade has no open,
    # and those rows fall back to the prevailing forward-filled close.
    opens = raw.pivot_table(index=["ticker", "date"], columns="minute",
                            values="open", aggfunc="first").reindex(
                                columns=range(MAX_MIN))
    opens.columns = [f"o{int(c)}" for c in opens.columns]
    return wide.join(opens).join(sess).reset_index()


def load_bench_0935() -> pd.DataFrame:
    b = pd.read_parquet(BASE / "bench_intraday.parquet")
    b["date"] = pd.to_datetime(b["date"])
    at = b[b["minute"] <= BENCH_MIN].sort_values("minute")
    at = at.groupby(["bench", "date"]).agg(px=("close", "last"),
                                           open_=("bench_open", "first")).reset_index()
    at["ret_0935"] = at["px"] / at["open_"] - 1.0
    return at[["bench", "date", "ret_0935"]]


def stat_row(s: pd.Series, dates: pd.Series, label: dict) -> dict:
    n = len(s)
    k = int((s > 0).sum())
    lo, hi = wilson(k, n)
    b = A.clustered_bootstrap(s, dates, n_boot=N_BOOT)
    net = s - COST_BPS / 1e4
    bn = A.clustered_bootstrap(net, dates, n_boot=N_BOOT)
    rec = dict(label)
    rec.update({"n": n, "win_rate": k / n if n else np.nan,
                "wilson_lo": lo, "wilson_hi": hi,
                "gross_bps": b["stat"] * 1e4, "gross_p": b["p"],
                "net_bps": bn["stat"] * 1e4, "net_p": bn["p"],
                "net_ci_lo": bn["lo"] * 1e4, "net_ci_hi": bn["hi"] * 1e4,
                "small": "YES" if n < SMALL else ""})
    return rec


def dist_row(s: pd.Series, label: dict) -> dict:
    b = s * 1e4
    rec = dict(label)
    rec.update({"n": len(b), "mean_bps": b.mean(), "median_bps": b.median(),
                "p10": b.quantile(0.10), "p25": b.quantile(0.25),
                "p75": b.quantile(0.75), "p90": b.quantile(0.90),
                "pct_gt_100": (b > 100).mean() * 100,
                "pct_lt_m100": (b < -100).mean() * 100,
                "win_mean": b[b > 0].mean(), "win_median": b[b > 0].median(),
                "loss_mean": b[b < 0].mean(), "loss_median": b[b < 0].median()})
    return rec


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ev = pd.read_parquet(BASE / "events.parquet")
    ev["date"] = pd.to_datetime(ev["date"])
    ev = ev[ev["gap"] != 0].copy()
    ev["gap_up"] = ev["gap"] > 0
    ev["pattern_simple"] = ev.apply(simple_first_candle, axis=1)
    ev["stage_group"] = np.where(ev["stage_prev"] == 2.0, "Stage 2",
                                 np.where(ev["stage_prev"].isin([3.0, 4.0]),
                                          "Stage 3+4", None))

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
    # LOOK-AHEAD GUARD. The close series is forward-filled from a seed of
    # `session_open`, which is the first Open of the session -- for a name
    # that does not trade until, say, 09:50, that seed is a price from AFTER
    # the intended entry. Any event with no real print by 09:35 would
    # therefore "enter" at a future price. Such events are dropped outright
    # rather than filled. (They were never in the pattern cohorts, which
    # require real 09:30-09:35 candle data, but they did contaminate the
    # All-events rows: the 784 of them averaged about -95 bps.)
    early = [f"o{i}" for i in range(0, ENTRY_MIN + 1) if f"o{i}" in df.columns]
    has_early_print = df[early].notna().any(axis=1)
    n_drop = int((~has_early_print).sum())
    df = df[has_early_print].copy()

    # Entry = open of the 09:35 bar; if that minute itself did not trade, the
    # prevailing price from an earlier REAL print is used.
    df["entry_px"] = df[f"o{ENTRY_MIN}"].fillna(df[f"m{SIGNAL_MIN}"])
    df = df[df["entry_px"].notna()].copy()
    n_open = int(df[f"o{ENTRY_MIN}"].notna().sum())
    log(f"dropped {n_drop:,} events with no real print by 09:35 (look-ahead guard)")
    log(f"events with a 09:35 entry price: {len(df):,} "
        f"({n_open:,} from a real 09:35 open, "
        f"{len(df)-n_open:,} from an earlier real print)")

    bench = load_bench_0935()
    spy = bench[bench["bench"] == "SPY"][["date", "ret_0935"]].rename(
        columns={"ret_0935": "spy_0935"})
    df = df.merge(spy, on="date", how="left")
    sec = bench.rename(columns={"bench": "sector_etf", "ret_0935": "sector_0935"})
    df = df.merge(sec, on=["sector_etf", "date"], how="left")
    df["spy_agree"] = np.where(
        df["spy_0935"].isna() | (df["spy_0935"] == 0), None,
        np.where(np.sign(df["spy_0935"]) == np.sign(df["gap"]),
                 "SPY Agree", "SPY Disagree"))
    df["sector_agree"] = np.where(
        df["sector_0935"].isna() | (df["sector_0935"] == 0), None,
        np.where(np.sign(df["sector_0935"]) == np.sign(df["gap"]),
                 "Sector Agree", "Sector Disagree"))

    prev_close = df["open"] / (1.0 + df["gap"])
    df["gap_atr"] = (df["open"] - prev_close).abs() / df["atr14_prev"]

    entry = df["entry_px"]
    sign = np.where(df["gap_up"], 1.0, -1.0)
    cont = df[df["pattern_simple"] == CONT]

    R: dict[str, pd.DataFrame] = {}

    # ---------- 1. holding periods ----------
    rows = []
    for wname, wmin in WINDOWS.items():
        end = df["session_close"] if wmin is None else df[f"m{wmin}"]
        g = pd.Series(sign, index=df.index) * (end / entry - 1.0)
        g = g[g != 0]
        cohorts = [("All events", df), ("Gap Up", df[df["gap_up"]]),
                   ("Gap Down", df[~df["gap_up"]]),
                   ("Simple Continuation", cont),
                   ("Simple Continuation, Gap Up", cont[cont["gap_up"]]),
                   ("Simple Continuation, Gap Down", cont[~cont["gap_up"]])]
        for cname, sub in cohorts:
            s = g.reindex(sub.index).dropna()
            if len(s) < 30:
                continue
            rows.append(stat_row(s, df.loc[s.index, "date"],
                                 {"window": wname, "cohort": cname}))
    R["t1_holding"] = pd.DataFrame(rows)

    # ---------- 2. context filters, each on its own ----------
    rows = []
    for wname, wmin in WINDOWS.items():
        end = df["session_close"] if wmin is None else df[f"m{wmin}"]
        g = pd.Series(sign, index=df.index) * (end / entry - 1.0)
        g = g[g != 0]
        for col, vals in (("spy_agree", ["SPY Agree", "SPY Disagree"]),
                          ("sector_agree", ["Sector Agree", "Sector Disagree"]),
                          ("stage_group", ["Stage 2", "Stage 3+4"])):
            for v in vals:
                sub = cont[cont[col] == v]
                s = g.reindex(sub.index).dropna()
                if len(s) < 30:
                    continue
                rows.append(stat_row(s, df.loc[s.index, "date"],
                                     {"window": wname, "filter": col, "bucket": v}))
    R["t2_filters"] = pd.DataFrame(rows)

    # ---------- 3. Gap/ATR ----------
    rows = []
    for wname, wmin in WINDOWS.items():
        end = df["session_close"] if wmin is None else df[f"m{wmin}"]
        g = pd.Series(sign, index=df.index) * (end / entry - 1.0)
        g = g[g != 0]
        for bname, lo_v, hi_v in ATR_BUCKETS:
            sub = cont[(cont["gap_atr"] >= lo_v) & (cont["gap_atr"] < hi_v)]
            s = g.reindex(sub.index).dropna()
            if len(s) < 30:
                continue
            rows.append(stat_row(s, df.loc[s.index, "date"],
                                 {"window": wname, "bucket": bname}))
    R["t3_gapatr"] = pd.DataFrame(rows)

    # ---------- 4. distribution ----------
    rows = []
    big = cont[cont["gap_atr"] > 2.0]
    for wname in DIST_WINDOWS:
        wmin = WINDOWS[wname]
        end = df["session_close"] if wmin is None else df[f"m{wmin}"]
        g = pd.Series(sign, index=df.index) * (end / entry - 1.0)
        g = g[g != 0]
        for cname, sub in (("Simple Continuation", cont),
                           ("Simple Continuation, Gap/ATR > 2.0", big)):
            s = g.reindex(sub.index).dropna()
            if len(s) < 30:
                continue
            rows.append(dist_row(s, {"window": wname, "cohort": cname}))
    R["t4_distribution"] = pd.DataFrame(rows)

    # ---------- 5. gross vs net for the key groups ----------
    rows = []
    for wname, wmin in WINDOWS.items():
        end = df["session_close"] if wmin is None else df[f"m{wmin}"]
        g = pd.Series(sign, index=df.index) * (end / entry - 1.0)
        g = g[g != 0]
        for cname, sub in (("Simple Continuation", cont),
                           ("Simple Continuation, Gap/ATR > 2.0", big)):
            s = g.reindex(sub.index).dropna()
            if len(s) < 30:
                continue
            rows.append(stat_row(s, df.loc[s.index, "date"],
                                 {"window": wname, "cohort": cname}))
    R["t5_net"] = pd.DataFrame(rows)

    meta = {"n_events": int(len(df)), "entry_minute": ENTRY_MIN,
            "n_real_open": n_open, "n_dropped_no_print": n_drop,
            "cost_bps": COST_BPS, "small": SMALL,
            "n_cont": int(len(cont)), "n_big": int(len(big))}

    for k, v in R.items():
        v.to_csv(OUT_DIR / f"e35_{k}.csv", index=False)
    (BASE / "entry35_meta.json").write_text(json.dumps(meta, indent=1))
    FEED.write_text(json.dumps(
        {"meta": meta, "windows": list(WINDOWS),
         **{k: json.loads(v.round(6).to_json(orient="records"))
            for k, v in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables")

    from entry0935_text import build  # noqa: E402
    REPORT.write_text(build(R, meta, list(WINDOWS)))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
