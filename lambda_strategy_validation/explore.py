"""
explore.py — Per-ticker and per-sector breakdown of the gap-continuation
result, plus the data feed for the interactive explorer.

THE MULTIPLE-COMPARISONS PROBLEM (why this file is not just a leaderboard):
scanning ~600 tickers at p < 0.05 produces ~30 "significant" names by pure
chance even if the edge does not exist anywhere. A ranked table of the best
performers is therefore worse than useless — it is a machine for generating
false confidence. Every per-ticker p-value here is accompanied by:

  * a Benjamini-Hochberg FDR q-value (how many discoveries survive when the
    whole family of tests is accounted for), and
  * an explicit expected-false-positive count, so the number of "winners"
    can be compared against what noise alone would produce.

Beta-adjusted (abnormal) returns are reported alongside raw returns: an
earnings edge should live in the stock-specific move, not in the market
having risen that day.

Run: python3 lambda_strategy_validation/explore.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

import analysis as A  # noqa: E402

BASE = Path("/home/user/lambda_data")
EVENTS = BASE / "events.parquet"
OUT_DIR = BASE / "tables"
FEED = BASE / "explorer_feed.json"

MIN_EVENTS = 12          # below this a per-ticker rate is noise
ALPHA = 0.05


def benjamini_hochberg(p: np.ndarray, alpha: float = ALPHA) -> np.ndarray:
    """Return BH q-values for a family of p-values."""
    p = np.asarray(p, dtype=float)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order]
    q = ranked * n / (np.arange(n) + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.clip(q, 0, 1)
    return out


def per_group(ev: pd.DataFrame, key: str, min_events: int) -> pd.DataFrame:
    rows = []
    for name, g in ev.groupby(key, observed=True):
        g = g.dropna(subset=["signed_o2c"])
        if len(g) < min_events:
            continue
        net = A.net_of_costs(g, 1.0, 2.0)
        cont = g["continuation"].astype(float)
        # Binomial p on the continuation rate; the clustered bootstrap is
        # too slow to run per-ticker across 600 names, so the family-wide
        # FDR correction below is what carries the inferential weight.
        succ = int(cont.sum())
        p_rate = float(stats.binomtest(succ, len(cont), 0.5).pvalue)
        t_net = stats.ttest_1samp(net.dropna(), 0.0) if net.notna().sum() > 2 else None
        rows.append({
            key: name,
            "n_events": int(len(g)),
            "continuation_rate": float(cont.mean()),
            "p_rate": p_rate,
            "gross_bps": float(g["signed_o2c"].mean() * 1e4),
            "net_bps": float(net.mean() * 1e4),
            "p_net": float(t_net.pvalue) if t_net is not None else np.nan,
            "abnormal_bps": float(g["signed_ab"].mean() * 1e4)
            if "signed_ab" in g.columns else np.nan,
            "beta": float(g["beta"].median()) if "beta" in g.columns else np.nan,
            "spy_o2c_bps": float(g["spy_o2c"].mean() * 1e4),
            "sector_o2c_bps": float(g["sector_o2c"].mean() * 1e4),
            "win_rate": float((net > 0).mean()),
            "median_gap_bps": float(g["gap"].abs().median() * 1e4),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["q_rate"] = benjamini_hochberg(df["p_rate"].to_numpy())
    df["q_net"] = benjamini_hochberg(df["p_net"].fillna(1.0).to_numpy())
    return df.sort_values("net_bps", ascending=False).reset_index(drop=True)


def main() -> None:
    ev = pd.read_parquet(EVENTS)
    ev["date"] = pd.to_datetime(ev["date"])
    # Signed abnormal (beta-adjusted) return in the gap direction.
    if "ab_o2c" in ev.columns:
        ev["signed_ab"] = np.where(ev["gap_up"], ev["ab_o2c"], -ev["ab_o2c"])

    by_ticker = per_group(ev, "ticker", MIN_EVENTS)
    by_sector = per_group(ev, "sector", MIN_EVENTS)

    sec_map = ev.groupby("ticker")["sector"].first()
    by_ticker["sector"] = by_ticker["ticker"].map(sec_map)

    n_tests = len(by_ticker)
    n_sig_raw = int((by_ticker["p_rate"] < ALPHA).sum())
    n_sig_fdr = int((by_ticker["q_rate"] < ALPHA).sum())
    expected_false = ALPHA * n_tests
    summary = {
        "n_tickers_tested": n_tests,
        "n_significant_uncorrected": n_sig_raw,
        "expected_false_positives": round(expected_false, 1),
        "n_significant_after_fdr": n_sig_fdr,
        "n_events": int(len(ev)),
        "overall_continuation": float(ev["continuation"].mean()),
    }
    print(json.dumps(summary, indent=2))

    by_ticker.to_csv(OUT_DIR / "per_ticker.csv", index=False)
    by_sector.to_csv(OUT_DIR / "per_sector.csv", index=False)

    # --- feed for the interactive explorer -------------------------------
    cols = ["ticker", "sector", "date", "gap", "o2c", "spy_o2c", "sector_o2c",
            "beta", "stage_prev", "continuation", "signed_o2c", "pattern"]
    slim = ev[[c for c in cols if c in ev.columns]].copy()
    slim["date"] = slim["date"].dt.strftime("%Y-%m-%d")
    for c in ("gap", "o2c", "spy_o2c", "sector_o2c", "signed_o2c"):
        if c in slim.columns:
            slim[c] = (slim[c] * 1e4).round(1)          # bps
    slim["beta"] = slim["beta"].round(2)
    slim["stage_prev"] = slim["stage_prev"].fillna(0).astype(int)
    slim["continuation"] = slim["continuation"].astype(int)

    feed = {
        "summary": summary,
        "by_ticker": json.loads(by_ticker.round(4).to_json(orient="records")),
        "by_sector": json.loads(by_sector.round(4).to_json(orient="records")),
        "events": json.loads(slim.to_json(orient="records")),
    }
    FEED.write_text(json.dumps(feed, separators=(",", ":")))
    print("wrote", FEED, f"{FEED.stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    main()
