"""
test_battery.py — Standard Lambda validation battery (drafted per user
request in the absence of Sigma's exact "section 3" list). Swap in Sigma's
real tests when the design doc lands; the function signatures here are
generic enough that most rigor requirements map onto one of these.

Every function takes a `trades` DataFrame with at minimum:
  date, ticker, stage, gross_return, net_return  (net_return may be added
  later by cost_model.apply_costs_to_returns)
and returns a small summary DataFrame/dict — never a single pass/fail
verdict. Verdicts are assembled by the caller (the report generator),
consistent with "never vague" — every number must be traceable to one of
these tables.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def in_sample_out_of_sample_split(
    trades: pd.DataFrame, split_date: str, date_col: str = "date"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """IS = strictly before split_date (used to discover/tune anything),
    OOS = split_date onward (touched only once, for final validation)."""
    d = pd.to_datetime(trades[date_col])
    is_df = trades[d < pd.Timestamp(split_date)]
    oos_df = trades[d >= pd.Timestamp(split_date)]
    return is_df, oos_df


def walk_forward_windows(
    trades: pd.DataFrame, n_folds: int = 5, date_col: str = "date"
) -> list[dict]:
    """Expanding-window walk-forward: fold k trains on all data before its
    test window and tests on the next 1/n_folds slice, chronologically."""
    d = pd.to_datetime(trades[date_col]).sort_values()
    dates = d.unique()
    edges = np.array_split(dates, n_folds)
    results = []
    for i in range(1, n_folds):
        test_start, test_end = edges[i][0], edges[i][-1]
        train_end = edges[i - 1][-1]
        test_mask = (pd.to_datetime(trades[date_col]) >= test_start) & (
            pd.to_datetime(trades[date_col]) <= test_end
        )
        test_slice = trades[test_mask]
        results.append({
            "fold": i,
            "train_end": train_end,
            "test_start": test_start,
            "test_end": test_end,
            "n_trades": len(test_slice),
            "mean_net_return": test_slice["net_return"].mean() if len(test_slice) else np.nan,
            "win_rate": (test_slice["net_return"] > 0).mean() if len(test_slice) else np.nan,
        })
    return results


def bootstrap_mean_ci(
    returns: pd.Series, n_boot: int = 5000, ci: float = 0.95, seed: int = 42
) -> dict:
    """Block-free i.i.d. bootstrap CI on mean return. For overlapping/
    autocorrelated trade returns, switch to a block bootstrap before
    trusting this on real T+1 data (flagged for the report)."""
    rng = np.random.default_rng(seed)
    r = returns.dropna().to_numpy()
    if len(r) < 10:
        return {"mean": np.nan, "lo": np.nan, "hi": np.nan, "n": len(r)}
    boot_means = np.array([
        rng.choice(r, size=len(r), replace=True).mean() for _ in range(n_boot)
    ])
    alpha = (1 - ci) / 2
    return {
        "mean": r.mean(),
        "lo": np.quantile(boot_means, alpha),
        "hi": np.quantile(boot_means, 1 - alpha),
        "n": len(r),
    }


def stage_stratified_returns(trades: pd.DataFrame) -> pd.DataFrame:
    return (
        trades.groupby("stage")["net_return"]
        .agg(mean="mean", median="median", win_rate=lambda s: (s > 0).mean(), n="count")
        .reset_index()
    )


def year_by_year_returns(trades: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    d = pd.to_datetime(trades[date_col])
    return (
        trades.assign(year=d.dt.year)
        .groupby("year")["net_return"]
        .agg(mean="mean", median="median", win_rate=lambda s: (s > 0).mean(), n="count")
        .reset_index()
    )


def beta_filter_impact(
    trades: pd.DataFrame, beta_col: str = "beta", beta_max: float = 1.5
) -> pd.DataFrame:
    """Compares performance with vs. without a beta cap. `beta` must be
    pre-computed (e.g. 1yr daily beta vs SPY as of entry date) and joined
    onto `trades` upstream — this function only slices and compares."""
    if beta_col not in trades.columns:
        raise ValueError(
            f"'{beta_col}' not in trades — join beta before calling this"
        )
    unfiltered = trades["net_return"]
    filtered = trades.loc[trades[beta_col] <= beta_max, "net_return"]
    return pd.DataFrame([
        {"cohort": "all_trades", "mean": unfiltered.mean(),
         "win_rate": (unfiltered > 0).mean(), "n": len(unfiltered)},
        {"cohort": f"beta<={beta_max}", "mean": filtered.mean(),
         "win_rate": (filtered > 0).mean(), "n": len(filtered)},
    ])


def first_three_5min_pattern(intraday_5min: pd.DataFrame) -> pd.DataFrame:
    """
    PENDING intraday data (HF Data Library). Placeholder contract:
    intraday_5min must have columns [ticker, session_date, bar_index (0-77
    for a 6.5h session), open, high, low, close, volume] for T+1 sessions.
    Will classify each session's first three 5-min bars (gap direction,
    range, volume vs ADV) and correlate with the rest-of-session/next-day
    return. Not implemented — no 5-min data source connected yet.
    """
    raise NotImplementedError(
        "Requires 5-min/1-min T+1 bars from HF Data Library — not connected yet."
    )
