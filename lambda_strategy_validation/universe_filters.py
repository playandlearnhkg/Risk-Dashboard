"""
universe_filters.py — Apply the Sigma universe screen:
  Market Cap > $3B, ADV >= 500k shares, ADTV >= $50M, Price >= $10

IMPORTANT LIMITATION: market cap requires point-in-time shares-outstanding
history, which is not derivable from OHLCV alone and has NOT been sourced
yet (see status report). The other three filters are pure functions of
price/volume and are fully implemented and ready to run.

All filters are computed on a trailing window (default 3 months / 63
trading days) to avoid one-day spikes flipping a name in/out of the
universe, and are meant to be re-applied at each rebalance/decision date
(point-in-time), never with a single static snapshot over 2015-2025 —
that would introduce survivorship/look-ahead bias.
"""

from __future__ import annotations

import pandas as pd

ADV_MIN_SHARES = 500_000
ADTV_MIN_DOLLARS = 50_000_000
PRICE_MIN = 10.0
MARKET_CAP_MIN = 3_000_000_000
DEFAULT_WINDOW = 63  # ~3 months of trading days


def rolling_liquidity_filters(
    daily: pd.DataFrame, window: int = DEFAULT_WINDOW
) -> pd.DataFrame:
    """
    daily: DataFrame with 'close' and 'volume' columns, indexed by date.
    Returns a DataFrame with adv, adtv, price_ok/adv_ok/adtv_ok booleans
    and a combined `liquidity_ok` (excludes market cap — see module docstring).
    """
    df = daily.copy()
    df.columns = [c.lower() for c in df.columns]
    for col in ("close", "volume"):
        if col not in df.columns:
            raise ValueError(f"daily frame must have a '{col}' column")

    df["adv"] = df["volume"].rolling(window, min_periods=window).mean()
    df["dollar_volume"] = df["close"] * df["volume"]
    df["adtv"] = df["dollar_volume"].rolling(window, min_periods=window).mean()

    df["price_ok"] = df["close"] >= PRICE_MIN
    df["adv_ok"] = df["adv"] >= ADV_MIN_SHARES
    df["adtv_ok"] = df["adtv"] >= ADTV_MIN_DOLLARS
    df["liquidity_ok"] = df["price_ok"] & df["adv_ok"] & df["adtv_ok"]
    return df


def apply_market_cap_filter(
    liquidity_df: pd.DataFrame, market_cap: pd.Series
) -> pd.DataFrame:
    """
    market_cap: a Series of point-in-time market cap, aligned/reindexed to
    liquidity_df's index (forward-filled from whatever frequency the source
    provides — e.g. quarterly shares outstanding x daily close).
    Call this once a real market-cap source (HF Data Library / fundamentals
    feed) is connected; until then `universe_ok` should not be trusted.
    """
    df = liquidity_df.copy()
    df["market_cap"] = market_cap.reindex(df.index).ffill()
    df["market_cap_ok"] = df["market_cap"] > MARKET_CAP_MIN
    df["universe_ok"] = df["liquidity_ok"] & df["market_cap_ok"]
    return df
