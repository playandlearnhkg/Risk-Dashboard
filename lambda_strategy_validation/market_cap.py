"""
market_cap.py — Point-in-time historical market cap via SEC EDGAR (free,
no key) x daily close price (from data_ingest / HF Data Library).

WHY NOT THE NASDAQ EARNINGS-CALENDAR API'S marketCap FIELD:
Verified by cross-check (2026-08-05): querying
api.nasdaq.com/api/calendar/earnings?date=2019-01-29 returns AAPL with
marketCap="$4,515,147,408,400" — that is Apple's market cap TODAY, not on
2019-01-29 (real value then was ~$700B). The field is a live snapshot the
API stamps onto every row regardless of the requested date. Using it for
any date but "today" is a severe look-ahead-bias bug. Do not use it.
The eps/surprise/fiscalQuarterEnding fields on already-reported rows ARE
genuinely historical (AAPL's 2019-01-29 entry: eps $4.18 vs forecast
$4.17, matching Apple's actual reported Q1 FY2019 results) — see
earnings_calendar.py, which uses only those fields.

METHOD USED HERE INSTEAD:
  1. Ticker -> CIK via SEC's static company_tickers.json.
  2. Point-in-time shares outstanding via SEC EDGAR's companyconcept API
     (us-gaap:CommonStockSharesOutstanding), keyed on the FILING date
     (`filed`), not the fiscal period end date (`end`) — using `end` would
     leak information forward to before it was actually public.
  3. Forward-fill shares outstanding across trading days between filings,
     multiply by that day's close price (from data_ingest.fetch_daily).

SECOND BUG CAUGHT AND FIXED HERE — split adjustment mismatch:
HF Data Library's close price is split-adjusted (both its 'clean' and
'raw' download variants — verified identical values, so neither is truly
unadjusted). SEC's raw shares-outstanding count, correctly, is NOT
adjusted for splits that happen after a filing (a 10-Q filed pre-split
reports the real share count that existed then). Multiplying
split-adjusted price x un-adjusted-for-future-splits shares understates
market cap by the cumulative split ratio for any date before a later
split (verified: AAPL 2019-01-29 came out ~$178B before this fix, vs a
real market cap then of ~$700-750B — off by ~4.2x, matching AAPL's
Aug-2020 4:1 split).

Fix: detect split-sized jumps directly in the raw shares series (a
ticker-agnostic ratio test — no hardcoded split calendar) and scale
historical share counts up by the cumulative ratio of every later split,
so the shares series lands on the same split-adjusted basis as price.
Known limitation: a single-filing share-count change from a huge
buyback/issuance (rare but not impossible, esp. for small caps) could be
misdetected as a split; SPLIT_RATIO_BAND is set conservatively to reduce
that risk but this should be spot-checked per ticker before trusting it
at scale.

Caveat: this is basic shares outstanding, not fully-diluted or float-
adjusted market cap. Good enough for a >$3B threshold screen; flag if
Sigma's design needs float-adjusted cap specifically.
"""

from __future__ import annotations

import pandas as pd
import requests

SEC_HEADERS = {"User-Agent": "Lambda Strategy Validation research@example.com"}
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
CONCEPT_URL_TEMPLATE = (
    "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}"
    "/us-gaap/CommonStockSharesOutstanding.json"
)

# A quarter-over-quarter shares-outstanding ratio outside this band is
# treated as a probable stock split/reverse-split rather than routine
# buyback/issuance drift.
SPLIT_RATIO_BAND = (0.4, 2.5)

_TICKER_CIK_CACHE: dict[str, int] | None = None


def _load_ticker_cik_map() -> dict[str, int]:
    global _TICKER_CIK_CACHE
    if _TICKER_CIK_CACHE is None:
        resp = requests.get(TICKERS_URL, headers=SEC_HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        _TICKER_CIK_CACHE = {
            row["ticker"].upper(): int(row["cik_str"]) for row in data.values()
        }
    return _TICKER_CIK_CACHE


def ticker_to_cik(ticker: str) -> int:
    m = _load_ticker_cik_map()
    try:
        return m[ticker.upper()]
    except KeyError:
        raise ValueError(f"No SEC CIK found for ticker {ticker!r}")


def fetch_shares_outstanding_history(ticker: str, timeout: int = 30) -> pd.DataFrame:
    """
    Returns one row per SEC filing that disclosed shares outstanding, with
    columns [filed, end, shares, form]. `filed` is the date this figure
    became public — that is the correct column to use for point-in-time
    joins. Deduplicated to the latest filing per `filed` date.
    """
    cik = ticker_to_cik(ticker)
    url = CONCEPT_URL_TEMPLATE.format(cik=cik)
    resp = requests.get(url, headers=SEC_HEADERS, timeout=timeout)
    resp.raise_for_status()
    units = resp.json()["units"]["shares"]
    df = pd.DataFrame(units)[["filed", "end", "val", "form"]].rename(
        columns={"val": "shares"}
    )
    df["filed"] = pd.to_datetime(df["filed"])
    df["end"] = pd.to_datetime(df["end"])
    df = df.sort_values("filed").drop_duplicates("filed", keep="last")
    return df.reset_index(drop=True)


def split_adjust_shares(shares_hist: pd.DataFrame) -> pd.Series:
    """
    Takes fetch_shares_outstanding_history's output and returns a Series
    (indexed by `filed`) of shares outstanding scaled onto a split-adjusted
    basis consistent with split-adjusted price data — see module docstring
    for why this is necessary and how splits are detected.
    """
    s = shares_hist.set_index("filed")["shares"].astype(float)
    ratios = s / s.shift(1)
    is_split = (ratios < SPLIT_RATIO_BAND[0]) | (ratios > SPLIT_RATIO_BAND[1])
    # cumulative_forward[i] = product of every later detected split ratio,
    # so multiplying today's raw shares by it lands on today's-basis scale.
    split_ratio_at_step = ratios.where(is_split, 1.0).fillna(1.0)
    cumulative_forward = split_ratio_at_step[::-1].cumprod()[::-1].shift(-1).fillna(1.0)
    return s * cumulative_forward


def point_in_time_market_cap(daily_close: pd.Series, ticker: str) -> pd.Series:
    """
    daily_close: Series indexed by trading date, SPLIT-ADJUSTED (e.g.
    daily['close'] from data_ingest.fetch_daily using the HF Data Library
    price, which is split-adjusted). Returns market cap indexed the same
    way, NaN before the first SEC filing date on record.
    """
    shares_hist = fetch_shares_outstanding_history(ticker)
    shares_adj = split_adjust_shares(shares_hist)
    shares_daily = shares_adj.reindex(daily_close.index, method="ffill")
    return daily_close * shares_daily
