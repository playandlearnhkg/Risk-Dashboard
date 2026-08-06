"""
winrate_report.py — Continuation PROBABILITY only. No average returns, no
net bps, no cost model. Every cell reports a count and a continuation
win rate.

DEFINITIONS (exactly as specified)
  Gap Up        : Open_T+1 >  Prior Close
  Gap Down      : Open_T+1 <  Prior Close
  Intraday Up   : Close_T+1 >  Open_T+1
  Intraday Down : Close_T+1 <  Open_T+1
  Continuation  : gap direction == intraday direction

Exact ties (Open == Prior Close, or Close == Open) are undefined under
these rules and are EXCLUDED, with the excluded count reported.

PATTERN SYSTEM 1 — the original 4-pattern classifier (unchanged), using
the three 5-minute candles 09:30-09:35, 09:35-09:40, 09:40-09:45:
  Strong Continuation+   : all three candles close in the gap direction
                           AND highs progress up (gap up) / lows progress
                           down (gap down)
  Moderate Continuation+ : >= 2 of 3 close in the gap direction and the
                           third is not a strong counter-move (its body
                           < 50% of the mean body of the other two)
  Early Reversal-        : majority close against the gap, OR a rejection
                           wick against the gap on candle 1 (wick > 60%
                           of that candle's range)
  Indecision0            : everything else

PATTERN SYSTEM 2 — simple online-style, FIRST 5-minute candle only
(09:30-09:35). Stated precisely so it is reproducible:
  body  = c1_close - c1_open
  range = c1_high  - c1_low
  Doji         : range == 0, or |body| / range < 0.10
  Continuation : otherwise, sign(body) == sign(gap)
  Reversal     : otherwise, sign(body) != sign(gap)

INFERENCE. Two intervals are shown side by side on purpose:
  wilson_lo/hi : Wilson 95% interval, which assumes observations are
                 independent. Simple and standard.
  p_clustered  : two-sided p vs a 50% null from a DATE-CLUSTERED bootstrap
                 (resampling whole trading dates). Dozens of firms report
                 the same evening and share the next day's market move, so
                 the independence assumption is false and the Wilson
                 interval is too narrow. Where they disagree, trust the
                 clustered p.

Run: python3 lambda_strategy_validation/winrate_report.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

import analysis as A  # noqa: E402
from horizons import load_wide  # noqa: E402

BASE = Path("/home/user/lambda_data")
EVENTS = BASE / "events.parquet"
OUT_DIR = BASE / "tables"
FEED = BASE / "winrate_feed.json"
REPORT = Path(__file__).resolve().parent / "WINRATE_REPORT.md"

SMALL_SAMPLE = 100          # cells below this are flagged
DOJI_BODY_FRACTION = 0.10   # |body| / range below this = doji
N_BOOT = 1000

PAT4_ORDER = ["Strong Continuation+", "Moderate Continuation+",
              "Indecision0", "Early Reversal-"]
PAT2_ORDER = ["Continuation (1st candle with gap)",
              "Reversal (1st candle against gap)", "Doji (1st candle)"]


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


# ---------------------------------------------------------------- pattern 2
def simple_first_candle(row: pd.Series) -> str | None:
    o, h, l, c = (row.get("c1_open"), row.get("c1_high"),
                  row.get("c1_low"), row.get("c1_close"))
    gap = row.get("gap")
    if any(pd.isna(x) for x in (o, h, l, c, gap)) or gap == 0:
        return None
    body = c - o
    rng = h - l
    if rng <= 0 or abs(body) / rng < DOJI_BODY_FRACTION:
        return "Doji (1st candle)"
    if (body > 0) == (gap > 0):
        return "Continuation (1st candle with gap)"
    return "Reversal (1st candle against gap)"


# ---------------------------------------------------------------- tabulation
def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (centre - half, centre + half)


def rate_row(g: pd.DataFrame, label_cols: dict, cont_col: str,
             up_col: str, clustered: bool = True) -> dict:
    """One row: counts of the two quadrant cells for this gap direction."""
    n = len(g)
    k = int(g[cont_col].sum())
    lo, hi = wilson(k, n)
    rec = dict(label_cols)
    rec.update({
        "n_total": n,
        "n_continuation": k,
        "n_reversal": n - k,
        "win_rate": (k / n) if n else np.nan,
        "wilson_lo": lo, "wilson_hi": hi,
        "small_sample": "YES" if n < SMALL_SAMPLE else "",
    })
    if clustered and n >= 30:
        r = A.clustered_rate_vs_half(g[cont_col].astype(bool), g["date"],
                                     n_boot=N_BOOT)
        rec["p_clustered"] = r["p"]
        rec["p_binomial"] = r["binom_p"]
    else:
        rec["p_clustered"] = np.nan
        rec["p_binomial"] = (float(stats.binomtest(k, n, 0.5).pvalue)
                             if n else np.nan)
    return rec


def split_table(df: pd.DataFrame, by: str | None, cont_col: str,
                up_col: str, order: list | None = None) -> pd.DataFrame:
    """Rows = subgroup x {Gap Up, Gap Down, Both}."""
    rows = []
    groups = [("All events", df)] if by is None else None
    if by is not None:
        vals = order if order else sorted(df[by].dropna().unique())
        groups = [(v, df[df[by] == v]) for v in vals]
    for name, g in groups:
        for gap_label, sub in (("Gap Up", g[g["gap_up"]]),
                               ("Gap Down", g[~g["gap_up"]]),
                               ("Both", g)):
            if len(sub) == 0:
                continue
            rows.append(rate_row(sub, {"subgroup": name, "gap": gap_label},
                                 cont_col, up_col))
    cols = ["subgroup", "gap", "n_total", "n_continuation", "n_reversal",
            "win_rate", "wilson_lo", "wilson_hi", "p_clustered",
            "p_binomial", "small_sample"]
    return pd.DataFrame(rows)[cols]


def quadrant_counts(df: pd.DataFrame, up_col: str) -> pd.DataFrame:
    ct = pd.crosstab(df["gap_up"], df[up_col])
    ct = ct.reindex(index=[False, True], columns=[False, True], fill_value=0)
    ct.index = ["Gap Down", "Gap Up"]
    ct.columns = ["Intraday Down", "Intraday Up"]
    out = ct.reset_index().rename(columns={"index": "quadrant"})
    out.columns = ["gap"] + list(ct.columns)
    tot = ct.to_numpy().sum()
    for c in ct.columns:
        out[f"{c} %"] = (out[c] / tot * 100).round(2)
    return out


# ---------------------------------------------------------------- main
def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ev = pd.read_parquet(EVENTS)
    ev["date"] = pd.to_datetime(ev["date"])
    n_raw = len(ev)

    # Ties are undefined under the stated rules -> excluded, and counted.
    tie_gap = int((ev["gap"] == 0).sum())
    tie_o2c = int((ev["o2c"] == 0).sum())
    ev = ev[(ev["gap"] != 0) & (ev["o2c"] != 0)].copy()
    ev["gap_up"] = ev["gap"] > 0
    ev["intraday_up"] = ev["o2c"] > 0
    ev["continuation"] = ev["gap_up"] == ev["intraday_up"]
    log(f"events {n_raw:,} -> {len(ev):,} after excluding "
        f"{tie_gap} gap ties and {tie_o2c} intraday ties")

    ev["pattern_simple"] = ev.apply(simple_first_candle, axis=1)
    ev["stage_group"] = np.where(ev["stage_prev"] == 2.0, "Stage 2",
                                 np.where(ev["stage_prev"].isin([3.0, 4.0]),
                                          "Stage 3+4", None))
    ev["spy_dir"] = np.where(ev["spy_o2c"] > 0, "SPY up", "SPY down")
    ev.loc[ev["spy_o2c"].isna(), "spy_dir"] = None
    ev["sector_dir"] = np.where(ev["sector_o2c"] > 0, "Sector ETF up",
                                "Sector ETF down")
    ev.loc[ev["sector_o2c"].isna(), "sector_dir"] = None

    R: dict[str, pd.DataFrame] = {}
    R["t1_quadrants"] = quadrant_counts(ev, "intraday_up")
    R["t1_rates"] = split_table(ev, None, "continuation", "intraday_up")
    R["t2_pattern4"] = split_table(ev[ev["pattern"].notna()], "pattern",
                                   "continuation", "intraday_up", PAT4_ORDER)
    R["t3_pattern_simple"] = split_table(ev[ev["pattern_simple"].notna()],
                                         "pattern_simple", "continuation",
                                         "intraday_up", PAT2_ORDER)

    # ---- Table 4: holding periods -------------------------------------
    log("loading intraday for holding-period windows")
    wide = load_wide(ev)
    hp = ev.merge(wide, on=["ticker", "date"], how="inner", suffixes=("", "_i"))
    hp = hp[hp["session_open"].notna() & hp["session_close"].notna()].copy()
    windows = {
        "Full day (Open -> Close)": ("session_open", "session_close"),
        "09:45 -> 10:00": ("m15", "m30"),
        "09:45 -> 10:15": ("m15", "m45"),
        "09:45 -> 11:00": ("m15", "m89"),
    }
    frames = []
    for label, (a, b) in windows.items():
        if a not in hp.columns or b not in hp.columns:
            log(f"  skipping {label}: missing column")
            continue
        d = hp.copy()
        move = d[b] - d[a]
        d = d[move != 0]
        d["win_up"] = move[move != 0] > 0
        d["cont_win"] = d["gap_up"] == d["win_up"]
        d["window"] = label
        frames.append(d)
    hold = pd.concat(frames, ignore_index=True)
    R["t4_holding"] = split_table(hold, "window", "cont_win", "win_up",
                                  list(windows))
    R["t4_quadrants"] = pd.concat(
        [quadrant_counts(hold[hold["window"] == w], "win_up").assign(window=w)
         for w in windows if (hold["window"] == w).any()], ignore_index=True)

    # ---- Tables 5-7 ----------------------------------------------------
    R["t5_spy"] = split_table(ev[ev["spy_dir"].notna()], "spy_dir",
                              "continuation", "intraday_up",
                              ["SPY up", "SPY down"])
    R["t6_sector"] = split_table(ev[ev["sector_dir"].notna()], "sector_dir",
                                 "continuation", "intraday_up",
                                 ["Sector ETF up", "Sector ETF down"])
    R["t7_stage"] = split_table(ev[ev["stage_group"].notna()], "stage_group",
                                "continuation", "intraday_up",
                                ["Stage 2", "Stage 3+4"])

    # ---- Table 8: gap-up / gap-down symmetry --------------------------
    # split_table already reports every table by gap direction, so Table 8
    # is those same splits presented side by side rather than a new cut.
    for key, src, by, order in (
        ("t8_pattern4", ev[ev["pattern"].notna()], "pattern", PAT4_ORDER),
        ("t8_simple", ev[ev["pattern_simple"].notna()], "pattern_simple", PAT2_ORDER),
        ("t8_stage", ev[ev["stage_group"].notna()], "stage_group", ["Stage 2", "Stage 3+4"]),
    ):
        t = split_table(src, by, "continuation", "intraday_up", order)
        R[key] = t[t["gap"] != "Both"].reset_index(drop=True)

    # ---- clean (non-overlapping) pattern check ------------------------
    # Tables 2/3 score the pattern against the FULL DAY, but the pattern is
    # built from 09:30-09:45, which is inside that window. This version
    # measures the forward window only, so the pattern cannot score itself.
    fwd = hp[hp["m15"].notna() & hp["session_close"].notna()].copy()
    move = fwd["session_close"] - fwd["m15"]
    fwd = fwd[move != 0]
    fwd["win_up"] = move[move != 0] > 0
    fwd["cont_win"] = fwd["gap_up"] == fwd["win_up"]
    R["t2_clean_0945_close"] = split_table(fwd[fwd["pattern"].notna()],
                                           "pattern", "cont_win", "win_up",
                                           PAT4_ORDER)
    R["t3_clean_0945_close"] = split_table(fwd[fwd["pattern_simple"].notna()],
                                           "pattern_simple", "cont_win",
                                           "win_up", PAT2_ORDER)

    # ---- best combinations --------------------------------------------
    combo = ev[ev["pattern_simple"].notna() & ev["stage_group"].notna()
               & ev["spy_dir"].notna()].copy()
    combo["combo"] = (combo["pattern_simple"].str.split(" (", regex=False).str[0] + " | "
                      + combo["stage_group"] + " | " + combo["spy_dir"])
    R["t9_combos"] = split_table(combo, "combo", "continuation", "intraday_up")

    meta = {"n_raw": n_raw, "n_used": int(len(ev)), "tie_gap": tie_gap,
            "tie_o2c": tie_o2c, "n_holding": int(len(hp)),
            "small_sample_threshold": SMALL_SAMPLE,
            "doji_body_fraction": DOJI_BODY_FRACTION}

    for k, v in R.items():
        v.to_csv(OUT_DIR / f"winrate_{k}.csv", index=False)
    (BASE / "winrate_meta.json").write_text(json.dumps(meta, indent=1))
    FEED.write_text(json.dumps(
        {"meta": meta, **{k: json.loads(v.round(6).to_json(orient="records"))
                          for k, v in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables + {FEED}")

    write_markdown(R, meta)
    log(f"wrote {REPORT}")


def md(df: pd.DataFrame) -> str:
    out = df.copy()
    if "win_rate" in out.columns:
        for c in ("win_rate", "wilson_lo", "wilson_hi"):
            out[c] = (out[c] * 100).map(lambda v: "" if pd.isna(v) else f"{v:.1f}%")
        for c in ("p_clustered", "p_binomial"):
            out[c] = out[c].map(lambda v: "" if pd.isna(v) else f"{v:.3f}")
        out = out.rename(columns={
            "n_total": "n", "n_continuation": "n cont", "n_reversal": "n rev",
            "win_rate": "Cont. win rate", "wilson_lo": "Wilson lo",
            "wilson_hi": "Wilson hi", "p_clustered": "p (clustered)",
            "p_binomial": "p (binomial)", "small_sample": "small n?"})
    for c in out.columns:
        if pd.api.types.is_float_dtype(out[c]):
            out[c] = out[c].map(lambda v: "" if pd.isna(v) else f"{v:.2f}")
    return out.to_markdown(index=False) + "\n"


def write_markdown(R: dict, meta: dict) -> None:
    from winrate_text import build  # noqa: E402
    REPORT.write_text(build(R, meta, md))


if __name__ == "__main__":
    main()
