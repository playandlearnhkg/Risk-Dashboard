"""
run_study.py — Execute every test in Sigma section 3 against the assembled
panel and write REPORT.md.

Run: python3 lambda_strategy_validation/run_study.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import analysis as A  # noqa: E402
from assemble import BASE, PANEL_PATH  # noqa: E402

REPORT_PATH = Path(__file__).resolve().parent / "REPORT.md"
TABLES_DIR = BASE / "tables"

VOL_METRICS = ["true_range", "atr14", "tr_pct", "hl_over_open", "rv_5min", "parkinson"]
STAGE_NAMES = {2.0: "Stage 2 (Advancing)", 3.0: "Stage 3 (Topping)",
               4.0: "Stage 4 (Declining)"}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def md(df: pd.DataFrame, floatfmt: str = ".4f") -> str:
    if df is None or len(df) == 0:
        return "_(no observations)_\n"
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_float_dtype(out[c]):
            out[c] = out[c].map(lambda v: "" if pd.isna(v) else format(v, floatfmt))
    return out.to_markdown(index=False) + "\n"


# ---------------------------------------------------------------------------

def apply_universe(panel: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Sigma section 1 filters, evaluated on the session BEFORE the event.

    Market cap is unavailable for tickers SEC's current-ticker map cannot
    resolve (delisted or renamed during the window). Dropping those would
    compound the dataset's survivorship bias, so a liquidity proxy is used
    for them — and validated here before it is trusted.
    """
    known = panel[panel["market_cap_prev"].notna()]
    liquid_known = known[known["adtv_ok_prev"] == True]  # noqa: E712
    if len(liquid_known):
        proxy_violation = float((liquid_known["market_cap_prev"] <= 3e9).mean())
    else:
        proxy_violation = np.nan

    mcap_effective = panel["mcap_ok_prev"].astype("boolean")
    proxied = panel["market_cap_prev"].isna()
    mcap_effective = mcap_effective.where(~proxied, panel["adtv_ok_prev"].astype("boolean"))

    keep = (
        panel["price_ok_prev"].astype("boolean").fillna(False)
        & panel["adv_ok_prev"].astype("boolean").fillna(False)
        & panel["adtv_ok_prev"].astype("boolean").fillna(False)
        & mcap_effective.fillna(False)
    )
    diag = {
        "proxy_violation_rate": proxy_violation,
        "n_rows_total": int(len(panel)),
        "n_rows_universe": int(keep.sum()),
        "n_tickers_mcap_known": int(panel.loc[panel["market_cap_prev"].notna(), "ticker"].nunique()),
        "n_tickers_mcap_proxied": int(panel.loc[proxied, "ticker"].nunique()),
        "pct_events_proxied": float(proxied[keep].mean()) if keep.any() else np.nan,
    }
    return panel[keep].copy(), diag


def add_regimes(ev: pd.DataFrame, spy_vol: pd.Series) -> pd.DataFrame:
    df = ev.copy()
    df["year"] = df["date"].dt.year
    df["era"] = np.where(df["date"] < "2020-01-01", "2015-2019", "2020-2025")
    df["spy_vol"] = spy_vol.reindex(df["date"]).to_numpy()
    thresh = df["spy_vol"].median()
    df["vol_regime"] = np.where(df["spy_vol"] > thresh, "High vol", "Low vol")
    df["stage_name"] = df["stage_prev"].map(STAGE_NAMES)
    for col, src in (("size_mcap", "market_cap_prev"), ("size_adtv", "adtv_63_prev")):
        try:
            df[col] = pd.qcut(df[src], 3, labels=["Small", "Mid", "Large"])
        except Exception:  # noqa: BLE001 - degenerate distribution
            df[col] = pd.NA
    return df


def main() -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    log("loading panel")
    panel = pd.read_parquet(PANEL_PATH)
    panel["date"] = pd.to_datetime(panel["date"])
    log(f"panel rows={len(panel):,} tickers={panel['ticker'].nunique()}")

    universe, diag = apply_universe(panel)
    log(f"universe rows={len(universe):,}  diag={diag}")

    # Volatility elevation needs the full (unfiltered-by-event) series to
    # build each ticker-quarter baseline, so it runs on the universe frame.
    vol_ev = A.volatility_elevation(universe, VOL_METRICS)
    log(f"events with volatility baseline: {len(vol_ev):,}")

    ev = A.add_event_features(vol_ev)
    ev = ev.dropna(subset=["gap", "o2c"])
    spy_vol = (panel[panel["ticker"] == panel["ticker"].iloc[0]]
               .set_index("date")["rv_5min"])  # placeholder, replaced below
    spy_src = BASE / "vars" / "SPY.parquet"
    if spy_src.exists():
        sv = pd.read_parquet(spy_src)
        spy_vol = pd.Series(sv["rv_5min"].rolling(21).mean().to_numpy(),
                            index=pd.to_datetime(sv["trade_date"]))
    ev = add_regimes(ev, spy_vol)
    log(f"final event set: {len(ev):,} events, {ev['ticker'].nunique()} tickers, "
        f"{ev['date'].nunique()} distinct dates")

    results: dict[str, pd.DataFrame] = {}

    # --- 3.1 Volatility elevation -----------------------------------------
    results["vol_overall"] = A.summarise_volatility(ev, VOL_METRICS)
    results["vol_by_stage"] = A.summarise_volatility(ev, VOL_METRICS, ["stage_name"])
    results["vol_by_size"] = A.summarise_volatility(ev, ["tr_pct", "rv_5min"], ["size_adtv"])

    # --- 3.2 Four-quadrant -------------------------------------------------
    results["quadrant_counts"] = A.quadrant_table(ev).reset_index().rename(
        columns={"index": "gap"})
    results["quadrant_overall"] = A.quadrant_stats(ev)
    results["quadrant_by_stage"] = A.quadrant_stats(ev, ["stage_name"])
    results["quadrant_by_gapdir"] = A.quadrant_stats(ev, ["gap_up"])

    # --- 3.3 Relative beta filter -----------------------------------------
    have_bench = ev[ev["beta_ok"].notna()]
    results["beta_filter"] = pd.concat([
        A.quadrant_stats(have_bench).assign(cohort="all (benchmarked)"),
        A.quadrant_stats(have_bench[have_bench["beta_ok"] == True]).assign(  # noqa: E712
            cohort="beta filter applied"),
        A.quadrant_stats(have_bench[have_bench["beta_ok"] == False]).assign(  # noqa: E712
            cohort="excluded (opposite both)"),
    ], ignore_index=True)
    results["beta_by_stage"] = A.quadrant_stats(
        have_bench[have_bench["beta_ok"] == True], ["stage_name"])  # noqa: E712

    # --- 3.4 Opening three 5-minute candles --------------------------------
    pat = ev[ev["pattern"].notna()]
    dist = pat["pattern"].value_counts(dropna=False).rename_axis("pattern").reset_index(
        name="n")
    dist["share"] = dist["n"] / dist["n"].sum()
    results["pattern_distribution"] = dist
    results["pattern_continuation"] = A.quadrant_stats(pat, ["pattern"])
    results["pattern_expectancy"] = A.expectancy_table(pat, ["pattern"])
    results["pattern_plus_vs_not"] = A.expectancy_table(pat, ["pattern_plus"])
    # Sensitivity: same analysis with the interpreted rejection-wick clause
    # removed, to show whether any pattern effect depends on that choice.
    pat_nw = ev[ev["pattern_nowick"].notna()]
    results["pattern_sensitivity_nowick"] = A.expectancy_table(
        pat_nw, ["pattern_plus_nowick"])
    results["pattern_dist_nowick"] = (
        pat_nw["pattern_nowick"].value_counts().rename_axis("pattern")
        .reset_index(name="n"))

    # --- 3.5 Full interaction ---------------------------------------------
    full = pat[(pat["stage_prev"] == 2.0) & (pat["pattern_plus"]) &
               (pat["beta_ok"] == True)]  # noqa: E712
    results["full_interaction"] = A.expectancy_table(full, ["gap_up"]) if len(full) else pd.DataFrame()
    results["full_interaction_all"] = A.expectancy_table(full, ["stage_name"]) if len(full) else pd.DataFrame()

    # --- 3.6 Robustness ----------------------------------------------------
    results["by_year"] = A.quadrant_stats(ev, ["year"])
    results["by_era"] = A.quadrant_stats(ev, ["era"])
    results["by_volregime"] = A.quadrant_stats(ev, ["vol_regime"])
    results["by_size"] = A.quadrant_stats(ev, ["size_adtv"])
    results["expectancy_by_year"] = A.expectancy_table(ev, ["year"])

    # --- 3.7 Costs ---------------------------------------------------------
    results["cost_ladder"] = A.cost_ladder(ev)
    results["cost_by_stage"] = A.expectancy_table(ev, ["stage_name"])

    # --- BMO/AMC contamination diagnostic ---------------------------------
    # If most reporters were after-hours, the T+1 session should carry the
    # volatility spike and the announcement session should look ordinary.
    # Elevated volatility on the announcement day itself means a material
    # share reported BEFORE the open and Sigma's T+1 is one session late
    # for them. This measures that directly instead of just flagging it.
    if "is_ann_day" in universe.columns:
        base = universe[~universe["is_t1"] & ~universe["is_ann_day"]]
        med = base.groupby(["ticker", base["date"].dt.to_period("Q")])["tr_pct"].median()
        rows = []
        for label, mask in (("announcement session (T+0)", universe["is_ann_day"]),
                            ("first session after (T+1)", universe["is_t1"])):
            g = universe[mask].copy()
            key = list(zip(g["ticker"], g["date"].dt.to_period("Q")))
            g["base"] = med.reindex(key).to_numpy()
            ratio = (g["tr_pct"] / g["base"]).replace([np.inf, -np.inf], np.nan)
            b = A.clustered_bootstrap(ratio - 1.0, g["date"])
            rows.append({"session": label, "n": b["n"],
                         "median_tr_ratio": float(ratio.median()),
                         "mean_excess": b["stat"], "ci_lo": b["lo"],
                         "ci_hi": b["hi"]})
        results["timing_diag"] = pd.DataFrame(rows)
    results["timing_known"] = pd.DataFrame([{
        "note": "share of events whose announcement time-of-day is known",
        "known_time_share": float((ev["ann_time"].notna() &
                                   (ev["ann_time"] != "time-not-supplied")).mean()),
    }])

    for name, df in results.items():
        if isinstance(df, pd.DataFrame) and len(df):
            df.to_csv(TABLES_DIR / f"{name}.csv", index=False)
    (BASE / "diagnostics.json").write_text(json.dumps(diag, indent=2, default=str))
    ev.to_parquet(BASE / "events.parquet", index=False)
    log(f"wrote {len(results)} tables + events.parquet")

    write_report(ev, results, diag)
    log(f"wrote {REPORT_PATH}")


def write_report(ev: pd.DataFrame, R: dict, diag: dict) -> None:
    from report_text import build_report  # noqa: E402
    REPORT_PATH.write_text(build_report(ev, R, diag))


if __name__ == "__main__":
    main()
