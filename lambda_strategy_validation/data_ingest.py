"""
data_ingest.py — Pull real data from HF Data Library (elkassabgidata MCP
server, "bars" dataset) and aggregate 1-min bars to daily OHLCV.

Auth: reads the API key from the ELKASSABGIDATA_KEY environment variable.
Never hardcode the key in this file or commit it anywhere in the repo.

Download endpoint returns per-ticker full-history 1-minute bars (source:
hfdatalibrary.com). Known caveats from the provider (carry into every
report using this data):
  - Survivorship bias in the ticker universe pre-2022 (delisted/acquired
    names before that point may be under-represented).
  - IEX source break on 2026-03-01-equivalent cutover: volumes are not
    directly comparable across the source transition (see `source` column
    in the raw bars: 'pitrading' vs 'iex').
  - 1-minute bars, not tick data — intraday microstructure stats (spread
    estimators, jump tests) are approximations built on 1-min sampling.
"""

from __future__ import annotations

import io
import os

import pandas as pd
import requests

DOWNLOAD_URL_TEMPLATE = (
    "https://api.hfdatalibrary.com/v1/download/{ticker}"
    "?version=clean&format=parquet&via=mcp"
)


def _api_key() -> str:
    key = os.environ.get("ELKASSABGIDATA_KEY")
    if not key:
        raise RuntimeError(
            "Set ELKASSABGIDATA_KEY in the environment before calling data_ingest."
        )
    return key


def fetch_1min_bars(ticker: str, timeout: int = 60) -> pd.DataFrame:
    """Downloads full-history clean 1-min bars for one ticker."""
    url = DOWNLOAD_URL_TEMPLATE.format(ticker=ticker.upper())
    resp = requests.get(url, headers={"X-API-Key": _api_key()}, timeout=timeout)
    resp.raise_for_status()
    return pd.read_parquet(io.BytesIO(resp.content))


def bars_to_daily(bars: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate 1-min bars to daily OHLCV. Session-first Open, session-last
    Close, max High, min Low, summed Volume. Index = trading date.
    """
    df = bars.copy()
    df["date"] = pd.to_datetime(df["datetime"]).dt.normalize()
    daily = df.groupby("date").agg(
        open=("Open", "first"),
        high=("High", "max"),
        low=("Low", "min"),
        close=("Close", "last"),
        volume=("Volume", "sum"),
        n_bars=("Close", "count"),
    )
    daily.index.name = "date"
    return daily


def fetch_daily(ticker: str) -> pd.DataFrame:
    """Convenience wrapper: download + aggregate in one call."""
    return bars_to_daily(fetch_1min_bars(ticker))
