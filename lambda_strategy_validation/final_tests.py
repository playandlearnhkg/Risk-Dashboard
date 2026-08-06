"""
final_tests.py — Three closing tests, same strict no-look-ahead rules.

RULES (unchanged from tradeable_report.py)
  1. Pattern known at 09:45 — read only the three candles 09:30-09:45.
  2. All measurement starts at 09:45 — entry is m14, the close of the
     09:44 bar, which is the price at 09:45:00 and equals c3_close.
  3. SPY / sector direction from Open -> 09:45 only.
  4. Stage from the prior session.

TEST 1 — ultra-short holds: 09:45 -> 09:50 (m19), 09:55 (m24), 10:00 (m29).
TEST 2 — average move size of winners vs losers, gross of costs.
         signed_return = sign(gap) * (P_end / P_entry - 1)
         winners  = signed_return > 0   (continuation)
         losers   = signed_return < 0   (reversal)
         avg_win  = mean(signed_return | winner)          , in bps
         avg_loss = mean(-signed_return | loser)          , in bps, positive
         expectancy = win_rate*avg_win - (1-win_rate)*avg_loss
         Expectancy is the number that decides whether a win rate matters:
         a 56% win rate with a smaller average win than average loss is
         still a losing system.
TEST 3 — the cost reference. Reported alongside, NOT subtracted from the
         Test 2 tables: median round-trip cost using each event's own
         measured trailing Roll spread plus a 2 bps impact allowance,
         charged on both legs.

Run: python3 lambda_strategy_validation/final_tests.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import analysis as A  # noqa: E402
from tradeable_report import (  # noqa: E402
    ENTRY_MIN, load_bench_0945, load_wide, wilson,
)
from winrate_report import simple_first_candle  # noqa: E402

BASE = Path("/home/user/lambda_data")
OUT_DIR = BASE / "tables"
FEED = BASE / "final_feed.json"
REPORT = Path(__file__).resolve().parent / "FINAL_TESTS_REPORT.md"

N_BOOT = 1000
SMALL_SAMPLE = 150

ULTRA = {"09:45 -> 09:50": 19, "09:45 -> 09:55": 24, "09:45 -> 10:00": 29}
EARN_WINDOWS = {"09:45 -> 10:00": 29, "09:45 -> 10:30": 59, "09:45 -> Close": None}


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def rate_row(g: pd.DataFrame, labels: dict) -> dict:
    n = len(g)
    k = int(g["cont"].sum())
    lo, hi = wilson(k, n)
    rec = dict(labels)
    rec.update({"n_total": n, "n_continuation": k, "n_reversal": n - k,
                "win_rate": (k / n) if n else np.nan,
                "wilson_lo": lo, "wilson_hi": hi,
                "small_sample": "YES" if n < SMALL_SAMPLE else ""})
    rec["p_clustered"] = (A.clustered_rate_vs_half(
        g["cont"].astype(bool), g["date"], n_boot=N_BOOT)["p"] if n >= 30 else np.nan)
    return rec


def earn_row(g: pd.DataFrame, labels: dict) -> dict:
    """Average win / average loss / expectancy, all in bps, gross."""
    s = g["signed"].dropna()
    n = len(s)
    wins, losses = s[s > 0], s[s < 0]
    wr = len(wins) / n if n else np.nan
    avg_win = wins.mean() * 1e4 if len(wins) else np.nan
    avg_loss = -losses.mean() * 1e4 if len(losses) else np.nan
    boot = A.clustered_bootstrap(s, g["date"], n_boot=N_BOOT)
    rec = dict(labels)
    rec.update({
        "n_total": n, "n_win": len(wins), "n_loss": len(losses),
        "win_rate": wr,
        "avg_win_bps": avg_win, "avg_loss_bps": avg_loss,
        "win_minus_loss_bps": (avg_win - avg_loss) if n else np.nan,
        "payoff_ratio": (avg_win / avg_loss) if avg_loss else np.nan,
        "expectancy_bps": boot["stat"] * 1e4,
        "exp_ci_lo": boot["lo"] * 1e4, "exp_ci_hi": boot["hi"] * 1e4,
        "exp_p": boot["p"],
        "median_cost_bps": float(g["cost_bps"].median()),
        "small_sample": "YES" if n < SMALL_SAMPLE else "",
    })
    return rec


def cohorts(d: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    best = d[(d["stage_group"] == "Stage 3+4") & (d["spy_agree"] == "SPY Agree")]
    return [
        ("All events", d),
        ("Gap Up", d[d["gap_up"]]),
        ("Gap Down", d[~d["gap_up"]]),
        ("Simple: Continuation", d[d["pattern_simple"] == "Continuation (1st candle with gap)"]),
        ("Simple: Reversal", d[d["pattern_simple"] == "Reversal (1st candle against gap)"]),
        ("Stage 3+4 + SPY Agree", best),
        ("Best combo: Cont + Stage 3+4 + SPY Agree",
         best[best["pattern_simple"] == "Continuation (1st candle with gap)"]),
    ]


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

    wide = load_wide(ev)
    df = ev.merge(wide, on=["ticker", "date"], how="inner", suffixes=("", "_i"))
    df = df[df["session_open"].notna() & df["session_close"].notna()].copy()

    bench = load_bench_0945()
    spy = bench[bench["bench"] == "SPY"][["date", "ret_0945"]].rename(
        columns={"ret_0945": "spy_0945"})
    df = df.merge(spy, on="date", how="left")
    df["spy_agree"] = np.where(
        df["spy_0945"].isna() | (df["spy_0945"] == 0), None,
        np.where(np.sign(df["spy_0945"]) == np.sign(df["gap"]),
                 "SPY Agree", "SPY Disagree"))

    # Round-trip cost reference: each event's own trailing Roll spread on
    # both legs, plus 2 bps impact per leg. Reported, never subtracted here.
    spread = A.spread_series(df)
    df["cost_bps"] = 2.0 * (spread / 2.0 + 2.0)

    entry = df[f"m{ENTRY_MIN}"]
    sign = np.where(df["gap_up"], 1.0, -1.0)
    R: dict[str, pd.DataFrame] = {}

    # ---------------- TEST 1 ----------------
    rows = []
    for wname, wmin in ULTRA.items():
        d = df.copy()
        d["move"] = d[f"m{wmin}"] - entry
        n_flat = int((d["move"] == 0).sum())
        d = d[d["move"] != 0].copy()
        d["cont"] = d["gap_up"] == (d["move"] > 0)
        for label, sub in (("All events", d), ("Gap Up", d[d["gap_up"]]),
                           ("Gap Down", d[~d["gap_up"]]),
                           ("Simple: Continuation",
                            d[d["pattern_simple"] == "Continuation (1st candle with gap)"]),
                           ("Simple: Reversal",
                            d[d["pattern_simple"] == "Reversal (1st candle against gap)"])):
            if len(sub) < 30:
                continue
            rows.append(rate_row(sub, {"window": wname, "subgroup": label,
                                       "n_flat_excluded": n_flat}))
    R["test1_ultrashort"] = pd.DataFrame(rows)

    # ---------------- TEST 2 ----------------
    rows = []
    for wname, wmin in EARN_WINDOWS.items():
        end = df["session_close"] if wmin is None else df[f"m{wmin}"]
        d = df.copy()
        d["signed"] = sign * (end / entry - 1.0)
        d = d[d["signed"] != 0]
        for label, sub in cohorts(d):
            if len(sub) < 30:
                continue
            rows.append(earn_row(sub, {"window": wname, "subgroup": label}))
    R["test2_earn"] = pd.DataFrame(rows)

    # same, for the ultra-short windows, since Test 3 needs their economics
    rows = []
    for wname, wmin in ULTRA.items():
        d = df.copy()
        d["signed"] = sign * (d[f"m{wmin}"] / entry - 1.0)
        d = d[d["signed"] != 0]
        for label, sub in cohorts(d):
            if len(sub) < 30:
                continue
            rows.append(earn_row(sub, {"window": wname, "subgroup": label}))
    R["test2_earn_ultrashort"] = pd.DataFrame(rows)

    # ---------------- TEST 3: NET expectancy, properly ----------------
    # The Test 2 tables are gross. Comparing a gross expectancy against a
    # median cost by eye is not enough: the answer needs the cost charged
    # per event and the whole thing bootstrapped, so the net figure carries
    # its own confidence interval.
    best = df[(df["stage_group"] == "Stage 3+4") & (df["spy_agree"] == "SPY Agree")]
    net_cohorts = [
        ("All events", df),
        ("Simple: Continuation",
         df[df["pattern_simple"] == "Continuation (1st candle with gap)"]),
        ("Stage 3+4 + SPY Agree", best),
        ("Best combo: Cont + Stage 3+4 + SPY Agree",
         best[best["pattern_simple"] == "Continuation (1st candle with gap)"]),
    ]
    all_windows = {**ULTRA, "09:45 -> 10:30": 59, "09:45 -> Close": None}
    rows = []
    for wname, wmin in all_windows.items():
        end = df["session_close"] if wmin is None else df[f"m{wmin}"]
        for label, sub in net_cohorts:
            idx = sub.index
            gross = pd.Series(sign, index=df.index)[idx] * (end[idx] / entry[idx] - 1.0)
            net = (gross - df.loc[idx, "cost_bps"] / 1e4).dropna()
            if len(net) < 30:
                continue
            b = A.clustered_bootstrap(net, df.loc[net.index, "date"], n_boot=N_BOOT)
            g = A.clustered_bootstrap(gross.dropna(),
                                      df.loc[gross.dropna().index, "date"], n_boot=200)
            rows.append({"window": wname, "subgroup": label, "n_total": b["n"],
                         "gross_bps": g["stat"] * 1e4,
                         "median_cost_bps": float(df.loc[idx, "cost_bps"].median()),
                         "net_bps": b["stat"] * 1e4,
                         "net_ci_lo": b["lo"] * 1e4, "net_ci_hi": b["hi"] * 1e4,
                         "net_p": b["p"]})
    R["test3_net"] = pd.DataFrame(rows)

    meta = {"n_events": int(len(df)),
            "median_cost_bps": float(df["cost_bps"].median()),
            "p25_cost_bps": float(df["cost_bps"].quantile(0.25)),
            "p75_cost_bps": float(df["cost_bps"].quantile(0.75)),
            "entry_minute": ENTRY_MIN, "small_sample_threshold": SMALL_SAMPLE}

    for k, v in R.items():
        v.to_csv(OUT_DIR / f"{k}.csv", index=False)
    (BASE / "final_meta.json").write_text(json.dumps(meta, indent=1))
    FEED.write_text(json.dumps(
        {"meta": meta, **{k: json.loads(v.round(6).to_json(orient="records"))
                          for k, v in R.items()}}, separators=(",", ":")))
    log(f"wrote {len(R)} tables; median round-trip cost "
        f"{meta['median_cost_bps']:.1f} bps")

    from final_text import build  # noqa: E402
    REPORT.write_text(build(R, meta))
    log(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
