"""
data/providers.py — Provider abstraction for all external data.
===============================================================

Every other Layer 1 module talks to a Provider, never to yfinance/SEC/FRED
directly. That indirection exists for one concrete reason: TradingView MCP and
Futu OpenD are planned, and when they arrive the change should be a new class
in this file plus one line in config.yaml — not a rewrite of six ingest
modules and everything above them.

Current implementations
    YFinanceProvider   default. Free, no key, rate-limits aggressively.
    FMPProvider        used for fundamentals/transcripts when FMP_API_KEY set.
    PolygonProvider    stub with the shape filled in; needs POLYGON_API_KEY.
    TradingViewProvider / FutuProvider
                       explicit NotImplemented stubs marking the seams, so the
                       interface they must satisfy is unambiguous.

Shared behaviour lives in the base class: rate limiting, retry with
exponential backoff, and a hard rule that a provider NEVER raises on a data
miss. Missing data returns None or an empty frame; only genuine programming
errors propagate. Layers above are built to re-weight around gaps, and that
only works if a gap arrives as a gap rather than as a traceback.
"""

from __future__ import annotations

import datetime as dt
import random
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd

from core.logging_setup import get_logger

log = get_logger("data.providers")


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class RateLimiter:
    """
    Token-bucket-ish limiter. Thread-safe because yfinance batches internally.

    SEC publishes a hard 8 requests/second ceiling and blocks violators, so
    this is a compliance control, not just politeness.
    """

    def __init__(self, per_second: float):
        self.min_interval = 1.0 / per_second if per_second > 0 else 0.0
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        with self._lock:
            elapsed = time.monotonic() - self._last
            sleep_for = self.min_interval - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)
            self._last = time.monotonic()


def looks_rate_limited(exc: Exception) -> bool:
    """
    Is this exception a 429 / rate limit?

    yfinance swallows the HTTP layer and re-raises assorted exception types,
    so there is no status code to inspect — string matching is the only
    option available. Kept in one place rather than duplicated at each call
    site so the patterns can be extended as new phrasings appear.
    """
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(marker in text for marker in (
        "429", "too many requests", "rate limit", "rate-limit",
        "temporarily blocked", "throttl",
    ))


@dataclass
class RateLimitState:
    """
    Rate-limit accounting for one provider instance.

    Shared across an entire ingest run so the picture is cumulative: a stage
    that trips 429s should slow the NEXT stage down too, and the run summary
    (and the dashboard) needs to know the data is incomplete for that reason
    rather than because the tickers do not exist.
    """

    hits: int = 0                     # total 429s seen this run
    cooldowns: int = 0                # how many times we paused and waited
    pause_multiplier: float = 1.0     # grows after each hit
    aborted: bool = False             # stage gave up to protect the IP
    first_hit_at: Optional[str] = None

    @property
    def limited(self) -> bool:
        return self.hits > 0

    def record(self) -> None:
        self.hits += 1
        if self.first_hit_at is None:
            self.first_hit_at = dt.datetime.now().isoformat(timespec="seconds")

    def as_dict(self) -> dict[str, Any]:
        return {
            "rate_limited": self.limited,
            "hits": self.hits,
            "cooldowns": self.cooldowns,
            "aborted": self.aborted,
            "first_hit_at": self.first_hit_at,
        }


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class Provider(ABC):
    """Interface every data provider must satisfy."""

    name: str = "base"

    # --- selectability gates, checked by get_provider() before use ---------
    # implemented: False means the class is a documented stub. Selecting it in
    # config must fall back to yfinance with an explanation, never crash the
    # run mid-ingest.
    implemented: bool = True
    # requires_secret: name of the .env key without which the provider returns
    # empty frames. Missing it is treated as unavailable rather than allowed
    # to silently produce a working-looking provider that fetches nothing.
    requires_secret: str | None = None
    # requires_local_gateway: human description of a local process that must
    # already be running (Futu OpenD, TradingView Desktop with CDP). These
    # cannot be probed cheaply at construction time, so they are reported in
    # the unavailability reason rather than auto-detected.
    requires_local_gateway: str | None = None

    def preflight(self) -> tuple[bool, str]:
        """
        Can this provider actually be used right now?

        Returns (ok, reason). Called by get_provider() BEFORE the provider is
        handed to any ingest stage, so an unusable choice degrades at startup
        with one clear message instead of failing per-ticker deep in a loop.
        """
        if not self.implemented:
            detail = f" Needs {self.requires_local_gateway}." if self.requires_local_gateway else ""
            return False, f"'{self.name}' is not implemented yet.{detail}"
        if self.requires_secret and not self.cfg.has_secret(self.requires_secret):
            return False, f"'{self.name}' needs {self.requires_secret} in .env"
        return True, "ok"

    def __init__(self, cfg):
        self.cfg = cfg
        self.attempts = int(cfg.get("data.retry.attempts", 3))
        self.backoff_base = float(cfg.get("data.retry.backoff_base_sec", 2))
        self.jitter = bool(cfg.get("data.retry.jitter", True))
        self.timeout = int(cfg.get("data.timeouts.http_seconds", 20))
        self.cooldown_sec = float(cfg.get("data.rate_limits.yfinance_cooldown_sec", 90))
        self.limiter = RateLimiter(float(cfg.get("data.rate_limits.generic_per_sec", 5)))
        # Shared across the whole run so 429s accumulate rather than resetting
        # per stage — see RateLimitState.
        self.rate_limit = RateLimitState()

    # -- retry helper ------------------------------------------------------

    def _retry(self, fn, *args, label: str = "", **kwargs) -> Any:
        """
        Run `fn` with bounded exponential backoff.

        Returns None on persistent failure rather than raising — see the module
        docstring. The final failure is logged at WARNING so a systematically
        dead feed is visible in the run summary.
        """
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.attempts + 1):
            try:
                self.limiter.wait()
                return fn(*args, **kwargs)
            except Exception as exc:                       # noqa: BLE001
                last_exc = exc
                limited = looks_rate_limited(exc)
                if limited:
                    self.rate_limit.record()

                if attempt >= self.attempts:
                    break

                # FULL JITTER: sleep a random amount in [0, backoff], not the
                # backoff itself. Fixed backoff makes every ticker in a failed
                # batch retry at the same instant and re-trigger the same 429
                # together; randomising spreads the retries out.
                ceiling = self.backoff_base ** attempt
                if limited:
                    # A 429 means back off much harder than a transient error.
                    ceiling = max(ceiling, self.cooldown_sec)
                delay = random.uniform(0, ceiling) if self.jitter else ceiling

                log.debug("%s attempt %d/%d failed (%s%s); retrying in %.1fs",
                          label or fn.__name__, attempt, self.attempts,
                          "RATE LIMITED — " if limited else "", exc, delay)
                time.sleep(delay)

        if looks_rate_limited(last_exc) if last_exc else False:
            log.warning("%s gave up after %d attempts — RATE LIMITED (429)",
                        label or getattr(fn, "__name__", "call"), self.attempts)
        else:
            log.warning("%s failed after %d attempts: %s",
                        label or getattr(fn, "__name__", "call"),
                        self.attempts, last_exc)
        return None

    # -- interface ---------------------------------------------------------

    @abstractmethod
    def get_prices(self, tickers: list[str], start: dt.date,
                   end: Optional[dt.date] = None) -> pd.DataFrame:
        """
        Daily OHLCV.

        Returns a long-format frame with columns:
            ticker, date, open, high, low, close, adj_close, volume
        Long rather than wide because it maps straight onto the daily_prices
        table and avoids a reshape on every ingest.
        """

    @abstractmethod
    def get_fundamentals(self, ticker: str, period: str = "quarterly") -> dict[str, pd.DataFrame]:
        """
        Financial statements.

        Returns {'income': df, 'balance': df, 'cashflow': df} where each frame
        is indexed by line item with period-end dates as columns.
        """

    def get_short_interest(self, ticker: str) -> dict[str, Any]:
        """Short interest snapshot. Optional — default is empty."""
        return {}

    def get_estimates(self, ticker: str) -> dict[str, Any]:
        """Analyst estimates snapshot. Optional — default is empty."""
        return {}

    def get_earnings_dates(self, ticker: str, days_ahead: int = 30) -> pd.DataFrame:
        """Upcoming earnings. Optional — default is empty."""
        return pd.DataFrame()

    def healthcheck(self) -> tuple[bool, str]:
        """Cheap probe so run_data can report provider status up front."""
        return True, "not implemented"


# ---------------------------------------------------------------------------
# yfinance (default)
# ---------------------------------------------------------------------------

class YFinanceProvider(Provider):
    """
    Free default provider.

    Yahoo rate-limits hard (HTTP 429), especially from shared or cloud IPs.
    Everything here is batched and paced accordingly, and a 429 surfaces as
    missing data rather than an exception.
    """

    name = "yfinance"

    def __init__(self, cfg):
        super().__init__(cfg)
        self.batch_size = int(cfg.get("data.rate_limits.yfinance_batch_size", 25))
        self.pause = float(cfg.get("data.rate_limits.yfinance_pause_sec", 3.0))
        self.max_threads = int(cfg.get("data.rate_limits.yfinance_max_threads", 4))
        self.max_429 = int(cfg.get("data.rate_limits.yfinance_max_429", 6))
        self.backoff_growth = float(cfg.get("data.rate_limits.yfinance_backoff_growth", 1.6))

    # -- prices ------------------------------------------------------------

    def get_prices(self, tickers: list[str], start: dt.date,
                   end: Optional[dt.date] = None) -> pd.DataFrame:
        import yfinance as yf

        frames: list[pd.DataFrame] = []
        n_batches = (len(tickers) + self.batch_size - 1) // self.batch_size

        for bi, i in enumerate(range(0, len(tickers), self.batch_size), start=1):
            # ABORT GUARD. Once Yahoo has 429'd repeatedly, continuing hammers
            # an IP that is already being throttled and tends to extend the
            # block. Stop the stage and keep whatever was fetched — partial
            # data is the correct outcome, and the caller reports it as such.
            if self.rate_limit.hits >= self.max_429:
                self.rate_limit.aborted = True
                log.warning(
                    "Stopping price fetch after %d rate-limit hits — %d of %d "
                    "batches done. Keeping partial data; rerun later to resume.",
                    self.rate_limit.hits, bi - 1, n_batches)
                break

            batch = tickers[i:i + self.batch_size]
            log.debug("prices batch %d/%d (%d symbols)", bi, n_batches, len(batch))

            before = self.rate_limit.hits
            raw = self._retry(
                yf.download, batch, start=start, end=end, interval="1d",
                auto_adjust=False,     # keep close AND adj_close distinct
                progress=False,
                # Bounded concurrency. threads=True lets yfinance open one
                # connection per symbol, which is the fastest way to get
                # 429'd on a 500-ticker universe.
                threads=min(self.max_threads, len(batch)),
                group_by="column",
                timeout=self.timeout, label=f"yf.download[{len(batch)}]",
            )

            # ADAPTIVE PACING:each 429 widens the gap between batches for the
            # rest of the run. Yahoo's throttle is stateful, so easing off
            # after the first hit avoids compounding it.
            if self.rate_limit.hits > before:
                self.rate_limit.pause_multiplier *= self.backoff_growth
                self.rate_limit.cooldowns += 1
                cooldown = self.cooldown_sec + random.uniform(0, self.cooldown_sec * 0.25)
                log.warning("Rate limited (hit %d/%d) — cooling down %.0fs, "
                            "then continuing at %.1fs between batches",
                            self.rate_limit.hits, self.max_429, cooldown,
                            self.pause * self.rate_limit.pause_multiplier)
                time.sleep(cooldown)

            if raw is not None and len(raw) > 0:
                frames.append(self._normalise_ohlcv(raw, batch))

            if i + self.batch_size < len(tickers):
                gap = self.pause * self.rate_limit.pause_multiplier
                # Jitter the inter-batch gap too: a perfectly periodic request
                # pattern is itself easy to fingerprint and throttle.
                time.sleep(gap + random.uniform(0, gap * 0.3))

        if not frames:
            return pd.DataFrame(columns=["ticker", "date", "open", "high", "low",
                                         "close", "adj_close", "volume"])
        return pd.concat(frames, ignore_index=True)

    @staticmethod
    def _normalise_ohlcv(raw: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
        """Flatten yfinance's several possible shapes into one long frame."""
        field_map = {"Open": "open", "High": "high", "Low": "low",
                     "Close": "close", "Adj Close": "adj_close", "Volume": "volume"}
        out: list[pd.DataFrame] = []

        if isinstance(raw.columns, pd.MultiIndex):
            level0 = set(raw.columns.get_level_values(0))
            fields_on_level0 = bool(level0 & set(field_map))
            for tkr in tickers:
                try:
                    sub = raw.xs(tkr, axis=1, level=1) if fields_on_level0 \
                        else raw.xs(tkr, axis=1, level=0)
                except (KeyError, IndexError):
                    continue
                df = sub.rename(columns=field_map)
                df = df[[c for c in field_map.values() if c in df.columns]].copy()
                df = df.dropna(how="all")
                if df.empty:
                    continue
                df["ticker"] = tkr
                df["date"] = pd.to_datetime(df.index).tz_localize(None).normalize()
                out.append(df.reset_index(drop=True))
        else:
            if len(tickers) != 1:
                return pd.DataFrame()      # ambiguous; let the caller retry singly
            df = raw.rename(columns=field_map)
            df = df[[c for c in field_map.values() if c in df.columns]].copy()
            df = df.dropna(how="all")
            if not df.empty:
                df["ticker"] = tickers[0]
                df["date"] = pd.to_datetime(df.index).tz_localize(None).normalize()
                out.append(df.reset_index(drop=True))

        if not out:
            return pd.DataFrame()
        combined = pd.concat(out, ignore_index=True)
        for col in field_map.values():
            if col not in combined.columns:
                combined[col] = None
        combined["date"] = pd.to_datetime(combined["date"]).dt.strftime("%Y-%m-%d")
        return combined[["ticker", "date", "open", "high", "low",
                         "close", "adj_close", "volume"]]

    # -- fundamentals ------------------------------------------------------

    def get_fundamentals(self, ticker: str, period: str = "quarterly") -> dict[str, pd.DataFrame]:
        import yfinance as yf

        def _fetch() -> dict[str, pd.DataFrame]:
            t = yf.Ticker(ticker)
            if period == "quarterly":
                return {"income": t.quarterly_financials,
                        "balance": t.quarterly_balance_sheet,
                        "cashflow": t.quarterly_cashflow}
            return {"income": t.financials,
                    "balance": t.balance_sheet,
                    "cashflow": t.cashflow}

        result = self._retry(_fetch, label=f"fundamentals[{ticker}/{period}]")
        if not result:
            return {}
        return {k: v for k, v in result.items()
                if isinstance(v, pd.DataFrame) and not v.empty}

    # -- snapshots ---------------------------------------------------------

    def get_short_interest(self, ticker: str) -> dict[str, Any]:
        import yfinance as yf

        def _fetch() -> dict[str, Any]:
            info = yf.Ticker(ticker).info or {}
            return {
                "shares_short": info.get("sharesShort"),
                "short_ratio": info.get("shortRatio"),
                "short_percent_of_float": info.get("shortPercentOfFloat"),
            }

        return self._retry(_fetch, label=f"short_interest[{ticker}]") or {}

    def get_estimates(self, ticker: str) -> dict[str, Any]:
        import yfinance as yf

        def _fetch() -> dict[str, Any]:
            info = yf.Ticker(ticker).info or {}
            return {
                "forward_eps": info.get("forwardEps"),
                "forward_pe": info.get("forwardPE"),
                "target_mean": info.get("targetMeanPrice"),
                "target_high": info.get("targetHighPrice"),
                "target_low": info.get("targetLowPrice"),
                "analyst_count": info.get("numberOfAnalystOpinions"),
            }

        return self._retry(_fetch, label=f"estimates[{ticker}]") or {}

    def get_earnings_dates(self, ticker: str, days_ahead: int = 30) -> pd.DataFrame:
        import yfinance as yf

        def _fetch() -> pd.DataFrame:
            return yf.Ticker(ticker).get_earnings_dates(limit=12)

        raw = self._retry(_fetch, label=f"earnings_dates[{ticker}]")
        if raw is None or not isinstance(raw, pd.DataFrame) or raw.empty:
            return pd.DataFrame()

        df = raw.reset_index()
        date_col = next((c for c in df.columns if "date" in str(c).lower()), df.columns[0])
        df["earnings_date"] = pd.to_datetime(df[date_col], errors="coerce", utc=True)
        df = df.dropna(subset=["earnings_date"])
        df["earnings_date"] = df["earnings_date"].dt.tz_localize(None)

        today = pd.Timestamp.today().normalize()
        horizon = today + pd.Timedelta(days=days_ahead)
        df = df[(df["earnings_date"] >= today) & (df["earnings_date"] <= horizon)]
        if df.empty:
            return pd.DataFrame()

        eps_col = next((c for c in raw.columns if "estimate" in str(c).lower()), None)
        out = pd.DataFrame({
            "ticker": ticker,
            "earnings_date": df["earnings_date"].dt.strftime("%Y-%m-%d"),
            "eps_estimate": df[eps_col] if eps_col and eps_col in df else None,
        })
        return out

    def healthcheck(self) -> tuple[bool, str]:
        df = self.get_prices(["SPY"], dt.date.today() - dt.timedelta(days=10))
        if df is None or df.empty:
            return False, "no data for SPY (Yahoo may be rate-limiting this IP)"
        return True, f"SPY ok, {len(df)} rows"


# ---------------------------------------------------------------------------
# Optional / future providers
# ---------------------------------------------------------------------------

class FMPProvider(Provider):
    """Financial Modeling Prep. Used for transcripts and as a fundamentals alt."""

    name = "fmp"
    requires_secret = "FMP_API_KEY"
    BASE = "https://financialmodelingprep.com/api/v3"

    def __init__(self, cfg):
        super().__init__(cfg)
        self.api_key = cfg.secret("FMP_API_KEY")

    def _get(self, path: str, **params) -> Any:
        import requests
        if not self.api_key:
            return None
        params["apikey"] = self.api_key

        def _call():
            r = requests.get(f"{self.BASE}/{path}", params=params, timeout=self.timeout)
            r.raise_for_status()
            return r.json()

        return self._retry(_call, label=f"fmp:{path}")

    def get_prices(self, tickers, start, end=None) -> pd.DataFrame:
        rows: list[dict] = []
        for t in tickers:
            payload = self._get(f"historical-price-full/{t}",
                                **{"from": start.isoformat()})
            for bar in (payload or {}).get("historical", []):
                rows.append({
                    "ticker": t, "date": bar.get("date"),
                    "open": bar.get("open"), "high": bar.get("high"),
                    "low": bar.get("low"), "close": bar.get("close"),
                    "adj_close": bar.get("adjClose"), "volume": bar.get("volume"),
                })
        return pd.DataFrame(rows)

    def get_fundamentals(self, ticker: str, period: str = "quarterly") -> dict[str, pd.DataFrame]:
        p = "quarter" if period == "quarterly" else "annual"
        out: dict[str, pd.DataFrame] = {}
        for key, path in (("income", "income-statement"),
                          ("balance", "balance-sheet-statement"),
                          ("cashflow", "cash-flow-statement")):
            payload = self._get(f"{path}/{ticker}", period=p, limit=20)
            if payload:
                df = pd.DataFrame(payload)
                if "date" in df.columns:
                    out[key] = df.set_index("date").T
        return out

    def get_transcript(self, ticker: str, year: int, quarter: int) -> Optional[str]:
        payload = self._get(f"earning_call_transcript/{ticker}",
                            year=year, quarter=quarter)
        if isinstance(payload, list) and payload:
            return payload[0].get("content")
        return None

    def healthcheck(self) -> tuple[bool, str]:
        if not self.api_key:
            return False, "FMP_API_KEY not set"
        return (True, "key present") if self._get("profile/AAPL") else (False, "probe failed")


class PolygonProvider(Provider):
    """Polygon.io. Structure in place; enable by setting POLYGON_API_KEY."""

    name = "polygon"
    requires_secret = "POLYGON_API_KEY"
    BASE = "https://api.polygon.io"

    def __init__(self, cfg):
        super().__init__(cfg)
        self.api_key = cfg.secret("POLYGON_API_KEY")

    def get_prices(self, tickers, start, end=None) -> pd.DataFrame:
        import requests
        if not self.api_key:
            return pd.DataFrame()
        end = end or dt.date.today()
        rows: list[dict] = []
        for t in tickers:
            def _call(tk=t):
                url = (f"{self.BASE}/v2/aggs/ticker/{tk}/range/1/day/"
                       f"{start.isoformat()}/{end.isoformat()}")
                r = requests.get(url, params={"apiKey": self.api_key, "limit": 50000},
                                 timeout=self.timeout)
                r.raise_for_status()
                return r.json()

            payload = self._retry(_call, label=f"polygon:{t}")
            for bar in (payload or {}).get("results", []):
                rows.append({
                    "ticker": t,
                    "date": dt.datetime.utcfromtimestamp(bar["t"] / 1000).strftime("%Y-%m-%d"),
                    "open": bar.get("o"), "high": bar.get("h"), "low": bar.get("l"),
                    "close": bar.get("c"), "adj_close": bar.get("c"), "volume": bar.get("v"),
                })
        return pd.DataFrame(rows)

    def get_fundamentals(self, ticker, period="quarterly") -> dict[str, pd.DataFrame]:
        return {}

    def healthcheck(self) -> tuple[bool, str]:
        return (bool(self.api_key), "key present" if self.api_key else "POLYGON_API_KEY not set")


class TradingViewProvider(Provider):
    """
    NOT IMPLEMENTED — and a poor fit for this role. Read before implementing.

    TradingView has no REST data API here. Access is Chrome DevTools Protocol
    automation against the TradingView **Desktop** app, launched with
    `--remote-debugging-port=9222`, driven through tools like `tv_health_check`,
    `pine_set_source`, `pine_check`, `data_get_ohlcv` and
    `data_get_pine_tables`.

    Why it does not belong as `market_data`:
      * It is one symbol at a time through a UI automation surface. This role
        refreshes 530+ tickers daily; that is the wrong shape entirely.
      * The CDP link dies whenever the app restarts normally, and a relaunch
        clears attached studies from the chart.
      * Extraction goes through Pine `table.new()` cells read back as text —
        a rendering channel, not a data feed. `log.info()` is NOT readable.

    What it IS uniquely good for: order-flow footprint data via
    `request.footprint()` (Premium/Ultimate only) — buy/sell volume per price
    row, delta, POC/VAH/VAL, diagonal imbalances. Nothing free replicates that.

    RECOMMENDATION: when this is built, make it a separate specialist module
    (e.g. `data/footprint.py`) that stores footprint rows for a handful of
    watched symbols — not a drop-in `Provider` promising bulk OHLCV. Two known
    traps if you do: `ticksPerRow` must be `simple int` (a series like
    `ta.atr()` fails to compile), and `request.footprint()` returns `na` when a
    bar has no data, so every read needs `if not na(fp)`.
    """

    name = "tradingview"
    implemented = False
    requires_local_gateway = (
        "TradingView Desktop running with --remote-debugging-port=9222, "
        "plus Premium/Ultimate for footprint data"
    )

    def get_prices(self, tickers, start, end=None) -> pd.DataFrame:
        raise NotImplementedError(
            "TradingView provider not implemented. See the class docstring — "
            "it is a CDP automation surface suited to footprint extraction, "
            "not bulk daily OHLCV."
        )

    def get_fundamentals(self, ticker, period="quarterly") -> dict[str, pd.DataFrame]:
        raise NotImplementedError("TradingView provider not implemented")

    def healthcheck(self) -> tuple[bool, str]:
        return False, "not implemented (CDP automation surface — see docstring)"


class FutuProvider(Provider):
    """
    NOT IMPLEMENTED — but a genuinely good fit, and the closest to ready.

    Futu OpenD is a LOCAL gateway. You run the OpenD application on the same
    machine, logged into your account, listening on 127.0.0.1:11111, and the
    client connects to that socket. There is no cloud endpoint and no API key
    in .env — the credential is the logged-in OpenD session.

        from futu import OpenQuoteContext, KLType
        ctx = OpenQuoteContext(host="127.0.0.1", port=11111)
        ret, data, page_key = ctx.request_history_kline(
            "US.AAPL", start=..., end=..., ktype=KLType.K_DAY)

    Three things to get right when implementing:
      1. SYMBOL FORMAT. Futu wants a market prefix — "US.AAPL", not "AAPL".
         Translate at the provider boundary so no other layer learns about it.
      2. PAGINATION. `request_history_kline` returns `page_key`; loop until it
         is None or long histories silently truncate.
      3. CACHE TO DISK. Quota is per-account and finite. Write one parquet per
         symbol/date-range on fetch and check it before requesting, so a rerun
         costs nothing and an interrupted backfill is resumable. This matters
         more than it looks — without it, a crashed 500-ticker run burns the
         day's quota with nothing to show.

    `preflight()` cannot detect whether OpenD is actually running without
    attempting a connection, so this stays gated on `implemented` until the
    real client exists; at that point, replace this with a socket probe of
    127.0.0.1:11111 and report "OpenD not running" distinctly from "not built".
    """

    name = "futu"
    implemented = False
    requires_local_gateway = "FutuOpenD running and logged in on 127.0.0.1:11111"

    def get_prices(self, tickers, start, end=None) -> pd.DataFrame:
        raise NotImplementedError(
            "Futu provider not implemented. Requires FutuOpenD on "
            "127.0.0.1:11111 — see the class docstring."
        )

    def get_fundamentals(self, ticker, period="quarterly") -> dict[str, pd.DataFrame]:
        raise NotImplementedError("Futu provider not implemented")

    def healthcheck(self) -> tuple[bool, str]:
        return False, "not implemented (needs local OpenD gateway)"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

# Roles served by a Provider subclass and therefore configurable/fallback-able.
# Anything not listed here is a fixed source (FRED, SEC EDGAR) handled by its
# own module and is not subject to provider fallback.
PROVIDER_BACKED_ROLES = ("market_data", "fundamentals", "transcripts")

FIXED_SOURCES = {
    "macro": "FRED",
    "filings": "SEC EDGAR",
    "margin_debt": "FINRA (manual CSV)",
}

REGISTRY: dict[str, type[Provider]] = {
    "yfinance": YFinanceProvider,
    "fmp": FMPProvider,
    "polygon": PolygonProvider,
    "tradingview": TradingViewProvider,
    "futu": FutuProvider,
}


def get_provider(cfg, role: str = "market_data") -> Provider:
    """
    Build the provider configured for `role`, falling back to yfinance when
    the configured one cannot actually be used.

    THREE failure modes are handled here, all by degrading rather than
    raising. A data pull should never die at startup because of a config
    choice — the free default always works, and the run tells you loudly what
    it substituted and why.

      1. Unknown name        — typo in config.yaml
      2. Not implemented     — tradingview / futu stubs
      3. Missing credential  — fmp / polygon selected without their key

    Previously only case 1 was caught, so setting `market_data: tradingview`
    produced a provider that raised NotImplementedError on the first fetch,
    mid-ingest, after the universe stage had already run.
    """
    requested = cfg.get(f"data.providers.{role}", "yfinance")
    cls = REGISTRY.get(requested)

    # --- 1. unknown name ---------------------------------------------------
    if cls is None:
        log.warning(
            "Provider '%s' for role '%s' is not recognised — falling back to "
            "yfinance. Valid options: %s",
            requested, role, ", ".join(sorted(REGISTRY)),
        )
        provider = YFinanceProvider(cfg)
        log.info("Provider for %-14s → %s (fallback)", role, provider.name)
        return provider

    # --- 2 & 3. constructed, but check it can actually be used -------------
    try:
        provider = cls(cfg)
        usable, reason = provider.preflight()
    except Exception as exc:                           # noqa: BLE001
        usable, reason = False, f"failed to construct: {exc}"
        provider = None

    if usable:
        log.info("Provider for %-14s → %s", role, provider.name)
        return provider

    # Fall back. WARNING not ERROR: the run continues correctly, just not with
    # the provider that was asked for, and the user needs to see that clearly.
    log.warning("Provider '%s' for role '%s' is unavailable — %s", requested, role, reason)
    log.warning("  → falling back to yfinance for '%s'", role)

    fallback = YFinanceProvider(cfg)
    log.info("Provider for %-14s → %s (fallback from '%s')",
             role, fallback.name, requested)
    return fallback


def provider_report(cfg) -> list[tuple[str, str, str, str]]:
    """
    Per-role provider status, for the run summary.

    Returns (role, requested, effective, note) so run_data.py can show at a
    glance whether it is running on what was configured — a silent fallback
    that only appears in the log is easy to miss for weeks.
    """
    out: list[tuple[str, str, str, str]] = []
    # ONLY roles that actually route through get_provider() / REGISTRY.
    #
    # `macro` (FRED) and `filings` (SEC EDGAR) are deliberately excluded: they
    # are served by dedicated modules, not Provider subclasses, so looking them
    # up in REGISTRY produced a bogus "unknown provider — fell back to
    # yfinance" warning. They are reported separately as fixed sources.
    for role in PROVIDER_BACKED_ROLES:
        requested = cfg.get(f"data.providers.{role}")
        if requested is None:
            continue
        cls = REGISTRY.get(requested)
        if cls is None:
            out.append((role, requested, "yfinance", "unknown provider name"))
            continue
        try:
            usable, reason = cls(cfg).preflight()
        except Exception as exc:                       # noqa: BLE001
            usable, reason = False, str(exc)
        out.append((role, requested, requested if usable else "yfinance",
                    "" if usable else reason))
    return out
