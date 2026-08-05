"""
earnings_calendar.py — Historical earnings report dates via the free,
unauthenticated Nasdaq calendar API.

VALIDATED FIELDS ONLY: a row is only trustworthy as a confirmed historical
earnings date if it carries an actual `eps` (and `surprise`) value — that
means the report had genuinely happened by the time the API was queried.
Rows with only `epsForecast` and no `eps` are upcoming/scheduled entries;
for dates further in the past we also saw tickers that could not have
existed yet (e.g. a company appearing on a 2015 query despite not IPO'ing
until 2020), so upcoming-only rows on old dates should not be trusted at
all. `fetch_confirmed_earnings` filters to actual-only rows for this
reason.

DO NOT USE THE `marketCap` FIELD FROM THIS API FOR ANYTHING HISTORICAL —
it reflects today's market cap regardless of the date queried (verified:
AAPL 2019-01-29 query returned today's ~$4.5T cap, not the real ~$700B of
the time). Use market_cap.py instead.

No API key. Respect the source: this is a light per-day JSON endpoint,
not built for bulk scraping — throttle calls (see fetch_range) and cache
results locally rather than re-fetching the same date repeatedly.
"""

from __future__ import annotations

import time

import pandas as pd
import requests

NASDAQ_URL = "https://api.nasdaq.com/api/calendar/earnings"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def fetch_confirmed_earnings(date: str, timeout: int = 15) -> pd.DataFrame:
    """
    date: 'YYYY-MM-DD'. Returns rows with a confirmed actual EPS result
    only (excludes upcoming/scheduled-only entries). Columns: symbol,
    name, eps, eps_forecast, surprise, fiscal_quarter_ending, time.
    """
    resp = requests.get(NASDAQ_URL, headers=HEADERS, params={"date": date}, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()
    rows = (payload.get("data") or {}).get("rows") or []
    df = pd.DataFrame(rows)
    if df.empty or "eps" not in df.columns:
        return pd.DataFrame(columns=[
            "date", "symbol", "name", "eps", "eps_forecast", "surprise",
            "fiscal_quarter_ending", "time",
        ])
    confirmed = df[df["eps"].notna() & (df["eps"] != "")].copy()
    confirmed["date"] = date
    confirmed = confirmed.rename(columns={
        "symbol": "symbol", "name": "name", "eps": "eps",
        "epsForecast": "eps_forecast", "surprise": "surprise",
        "fiscalQuarterEnding": "fiscal_quarter_ending", "time": "time",
    })
    cols = ["date", "symbol", "name", "eps", "eps_forecast", "surprise",
            "fiscal_quarter_ending", "time"]
    return confirmed[[c for c in cols if c in confirmed.columns]].reset_index(drop=True)


def fetch_range(start: str, end: str, sleep_seconds: float = 0.5) -> pd.DataFrame:
    """
    Pulls confirmed earnings for every business day in [start, end].
    sleep_seconds throttles requests — this is a per-day endpoint on a
    free public API, not built for bulk historical scraping; be polite.
    A 2015-2025 pull is ~2,600 business days -> budget ~20-25 min at the
    default throttle. Consider caching the result to disk once run.
    """
    dates = pd.bdate_range(start, end)
    frames = []
    for i, d in enumerate(dates):
        frames.append(fetch_confirmed_earnings(d.strftime("%Y-%m-%d")))
        if sleep_seconds:
            time.sleep(sleep_seconds)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
