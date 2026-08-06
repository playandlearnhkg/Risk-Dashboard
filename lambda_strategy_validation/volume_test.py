"""
volume_test.py — Does opening-candle volume confirmation improve the
first-candle continuation signal?

Run on TWO universes with identical machinery:
  A. Post-earnings (the earnings event set used throughout, intraday210)
  B. General gaps 2021-2025 (the Stage 1 gap set, gapintraday)

VOLUME DEFINITION
  High Volume = c1_volume > 1.5 x the trailing 20-session mean of
  c1_volume for the SAME ticker and the SAME 09:30-09:35 slot.

  The trailing window is shifted by one session, so the current day never
  enters its own benchmark.

  A median-based denominator is carried alongside as a robustness check:
  c1_volume is strongly right-skewed (median ratio-to-mean is ~0.69), so a
  mean denominator makes 1.5x a roughly top-15% cut rather than a
  "half again above typical" cut. Both are reported.

  The 2022-03-01 IEX consolidated-tape change rescales reported volume by
  roughly 35x. A within-ticker ratio is almost immune to that (the share
  of sessions above 1.5x is 14.9% before and 16.0% after), but any window
  that STRADDLES the break mixes two unit systems in numerator and
  denominator. Those sessions are dropped.

Signal, entry and guards are identical to entry0935.py / gapstudy.py:
signal from the 09:30-09:35 candle, entry at the OPEN of the 09:35 bar,
events with no real print by 09:35 dropped.

Run: python3 lambda_strategy_validation/volume_test.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import analysis as A  # noqa: E402
from winrate_report import simple_first_candle, wilson  # noqa: E402

BASE = Path("/home/user/lambda_data")
OUT_DIR = BASE / "tables"
FEED = BASE / "volume_feed.json"
REPORT = Path(__file__).resolve().parent / "VOLUME_TEST_REPORT.md"

ENTRY_MIN = 5
SIGNAL_MIN = 4
N_BOOT = 1000
SMALL = 150
COST_BPS = 6.6
CONT = "Continuation (1st candle with gap)"

VOL_WINDOW = 20
VOL_MINP = 15
VOL_MULT = 1.5
BREAK = pd.Timestamp("2022-03-01")

WINDOWS = {"5 min (09:40)": 9, "15 min (09:50)": 19, "1 hour (10:35)": 64}
ATR_EDGE = [("Gap/ATR < 1.0", -np.inf, 1.0), ("Gap/ATR > 2.0", 2.0, np.inf)]


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def volume_features() -> pd.DataFrame:
    """Trailing same-slot volume benchmark, strictly prior-session."""
    p = pd.read_parquet(BASE / "panel.parquet",
                        columns=["ticker", "date", "c1_volume"])
    p["date"] = pd.to_datetime(p["date"])
    p = p.sort_values(["ticker", "date"]).reset_index(drop=True)
    g = p.groupby("ticker")["c1_volume"]
    p["vol_avg20"] = g.transform(
        lambda s: s.rolling(VOL_WINDOW, min_periods=VOL_MINP).mean().shift(1))
    p["vol_med20"] = g.transform(
        lambda s: s.rolling(VOL_WINDOW, min_periods=VOL_MINP)
        .median().shift(1))

    # Flag windows that straddle the IEX tape change: the oldest session in
    # the trailing window sits before the break while the current one is on
    # or after it, so numerator and denominator use different volume units.
    di = p["date"].astype("int64")
    wmin = di.groupby(p["ticker"]).transform(
        lambda s: s.rolling(VOL_WINDOW, min_periods=VOL_MINP).min().shift(1))
    p["vol_straddle"] = (wmin < BREAK.value) & (p["date"] >= BREAK)

    p["vol_ratio"] = p["c1_volume"] / p["vol_avg20"]
    p["vol_ratio_med"] = p["c1_volume"] / p["vol_med20"]
    return p[["ticker", "date", "c1_volume", "vol_avg20", "vol_ratio",
              "vol_ratio_med", "vol_straddle"]]


def load_wide(ev: pd.DataFrame, directory: Path, max_min: int) -> pd.DataFrame:
    want = set(zip(ev["ticker"], ev["date"]))
    frames = []
    files = sorted(directory.glob("*.parquet"))
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
                               columns=range(max_min))
    sess = raw.groupby(["ticker", "date"])[
        ["session_open", "session_close"]].first()
    wide.insert(0, "seed", sess["session_open"])
    wide = wide.ffill(axis=1).drop(columns="seed")
    wide.columns = [f"m{int(c)}" for c in wide.columns]
    opens = raw.pivot_table(index=["ticker", "date"], columns="minute",
                            values="open", aggfunc="first").reindex(
                                columns=range(max_min))
    opens.columns = [f"o{int(c)}" for c in opens.columns]
    return wide.join(opens).join(sess).reset_index()


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


def prep_earnings(vol: pd.DataFrame) -> pd.DataFrame:
    ev = pd.read_parquet(BASE / "events.parquet")
    ev["date"] = pd.to_datetime(ev["date"])
    ev = ev[ev["gap"] != 0].copy()
    ev["gap_up"] = ev["gap"] > 0
    ev["pattern"] = ev.apply(simple_first_candle, axis=1)
    panel = pd.read_parquet(BASE / "panel.parquet",
                            columns=["ticker", "date", "atr14"])
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel.sort_values(["ticker", "date"])
    panel["atr14_prev"] = panel.groupby("ticker")["atr14"].shift(1)
    ev = ev.merge(panel[["ticker", "date", "atr14_prev"]],
                  on=["ticker", "date"], how="left")
    ev = ev.merge(vol, on=["ticker", "date"], how="left")
    wide = load_wide(ev, BASE / "intraday210", 210)
    df = ev.merge(wide, on=["ticker", "date"], how="inner", suffixes=("", "_p"))
    df = df[df["session_open"].notna()]
    prev_close = df["open"] / (1.0 + df["gap"])
    df["gap_atr"] = (df["open"] - prev_close).abs() / df["atr14_prev"]
    return df


def prep_general(vol: pd.DataFrame) -> pd.DataFrame:
    tgt = pd.read_parquet(BASE / "gap_targets.parquet")
    tgt["date"] = pd.to_datetime(tgt["date"])
    p = pd.read_parquet(BASE / "panel.parquet",
                        columns=["ticker", "date", "c1_open", "c1_high",
                                 "c1_low", "c1_close"])
    p["date"] = pd.to_datetime(p["date"])
    ev = tgt.merge(p, on=["ticker", "date"], how="left")
    ev["gap_up"] = ev["gap"] > 0
    ev["pattern"] = ev.apply(simple_first_candle, axis=1)
    ev = ev.merge(vol, on=["ticker", "date"], how="left")
    wide = load_wide(ev, BASE / "gapintraday", 70)
    df = ev.merge(wide, on=["ticker", "date"], how="inner")
    return df[df["session_open"].notna()]


def finalize(df: pd.DataFrame, name: str) -> tuple[pd.DataFrame, dict]:
    n0 = len(df)
    early = [f"o{i}" for i in range(0, ENTRY_MIN + 1) if f"o{i}" in df.columns]
    df = df[df[early].notna().any(axis=1)].copy()
    n_noprint = n0 - len(df)
    df["entry_px"] = df[f"o{ENTRY_MIN}"].fillna(df[f"m{SIGNAL_MIN}"])
    df = df[df["entry_px"].notna()].copy()

    n1 = len(df)
    df = df[~df["vol_straddle"].fillna(False)].copy()
    n_straddle = n1 - len(df)
    n2 = len(df)
    df = df[df["vol_ratio"].notna()].copy()
    n_novol = n2 - len(df)

    df["high_vol"] = df["vol_ratio"] > VOL_MULT
    df["high_vol_med"] = df["vol_ratio_med"] > VOL_MULT
    cont = df[df["pattern"] == CONT]
    meta = {"universe": name, "n_events": int(len(df)),
            "n_cont": int(len(cont)),
            "n_dropped_noprint": int(n_noprint),
            "n_dropped_straddle": int(n_straddle),
            "n_dropped_novol": int(n_novol),
            "pct_high": float(cont["high_vol"].mean()),
            "pct_high_med": float(cont["high_vol_med"].mean()),
            "median_ratio": float(cont["vol_ratio"].median()),
            "start": str(df["date"].min().date()),
            "end": str(df["date"].max().date())}
    log(f"{name}: {len(df):,} events, {len(cont):,} continuation, "
        f"{meta['pct_high']*100:.1f}% high volume "
        f"(dropped {n_noprint:,} no-print, {n_straddle:,} straddle, "
        f"{n_novol:,} no-vol)")
    return df, meta


def run_universe(df: pd.DataFrame, name: str) -> dict[str, pd.DataFrame]:
    entry = df["entry_px"]
    gs = pd.Series(np.where(df["gap_up"], 1.0, -1.0), index=df.index)
    cont = df[df["pattern"] == CONT]
    R = {}

    rows = []
    for wname, wmin in WINDOWS.items():
        r = gs * (df[f"m{wmin}"] / entry - 1.0)
        groups = [("All Continuation", cont),
                  ("Cont + High Volume", cont[cont["high_vol"]]),
                  ("Cont + Normal/Low Vol", cont[~cont["high_vol"]])]
        for gname, sub in groups:
            s = r.reindex(sub.index).dropna()
            s = s[s != 0]
            if len(s) < 30:
                continue
            rows.append(stat_row(s, df.loc[s.index, "date"],
                                 {"universe": name, "window": wname,
                                  "group": gname}))
    R["main"] = pd.DataFrame(rows)

    # median-denominator robustness check
    rows = []
    for wname, wmin in WINDOWS.items():
        r = gs * (df[f"m{wmin}"] / entry - 1.0)
        for gname, sub in (("High Vol (median denom)",
                            cont[cont["high_vol_med"]]),
                           ("Normal/Low (median denom)",
                            cont[~cont["high_vol_med"]])):
            s = r.reindex(sub.index).dropna()
            s = s[s != 0]
            if len(s) < 30:
                continue
            rows.append(stat_row(s, df.loc[s.index, "date"],
                                 {"universe": name, "window": wname,
                                  "group": gname}))
    R["robust"] = pd.DataFrame(rows)

    # volume within Gap/ATR extremes
    rows = []
    for wname, wmin in WINDOWS.items():
        r = gs * (df[f"m{wmin}"] / entry - 1.0)
        for bname, lo_v, hi_v in ATR_EDGE:
            m = cont[(cont["gap_atr"] >= lo_v) & (cont["gap_atr"] < hi_v)]
            for gname, sub in (("High Volume", m[m["high_vol"]]),
                               ("Normal/Low", m[~m["high_vol"]])):
                s = r.reindex(sub.index).dropna()
                s = s[s != 0]
                if len(s) < 30:
                    continue
                rows.append(stat_row(s, df.loc[s.index, "date"],
                                     {"universe": name, "window": wname,
                                      "bucket": bname, "group": gname}))
    R["byatr"] = pd.DataFrame(rows)

    # How separable are volume and gap size at all? If large gaps are almost
    # always high-volume, the "which bucket does volume help more in"
    # question has no low-volume population to answer it with.
    b = pd.cut(cont["gap_atr"], [-np.inf, 1.0, 2.0, np.inf],
               labels=["Gap/ATR < 1.0", "Gap/ATR 1.0-2.0", "Gap/ATR > 2.0"])
    ct = (cont.assign(bucket=b).groupby("bucket", observed=False)["high_vol"]
          .agg(n="size", n_high="sum"))
    ct = ct.reset_index()
    ct["n_low"] = ct["n"] - ct["n_high"]
    ct["pct_high"] = ct["n_high"] / ct["n"]
    ct.insert(0, "universe", name)
    R["overlap"] = ct
    return R


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    vol = volume_features()
    log("volume features built")

    out: dict[str, pd.DataFrame] = {}
    metas = {}
    for key, prep, label in (("A", prep_earnings, "Post-Earnings (T+1)"),
                             ("B", prep_general, "General Gaps")):
        df, meta = finalize(prep(vol), label)
        metas[key] = meta
        for tname, tbl in run_universe(df, label).items():
            out[f"{key}_{tname}"] = tbl

    meta = {"cost_bps": COST_BPS, "small": SMALL, "vol_mult": VOL_MULT,
            "vol_window": VOL_WINDOW, "A": metas["A"], "B": metas["B"]}
    for k, v in out.items():
        v.to_csv(OUT_DIR / f"vol_{k}.csv", index=False)
    FEED.write_text(json.dumps(
        {"meta": meta, **{k: json.loads(v.round(6).to_json(orient="records"))
                          for k, v in out.items()}}, separators=(",", ":")))
    log(f"wrote {len(out)} tables")

    from volume_text import build  # noqa: E402
    REPORT.write_text(build(out, meta))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
