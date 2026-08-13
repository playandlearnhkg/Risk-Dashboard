"""
universe.py -- which (ticker, session) pairs a strategy may even look at.

The engine owns the mechanism; a provider owns the policy. That split is
what lets a post-earnings strategy demand an earnings calendar while a
future momentum strategy supplies its own eligibility with no change to
`StrategyBase`.

THE DETAIL THAT DECIDES EVERYTHING: WHICH SESSION REACTS

A company reporting on day D is traded on a different session depending
on when it reported.

    BMO  before the open on D    ->  the reaction session is D
    AMC  after the close on D    ->  the reaction session is the NEXT
                                     trading session

Get this wrong and the entire cohort shifts by one session: every trade
lands on a day with no news, and the strategy quietly becomes a
volume filter on random days. It will still produce numbers.

UNKNOWN TIMING IS NOT GUESSED

Vendors frequently ship `time-not-supplied`. There is no honest way to
recover it from prices -- inferring "it must have been AMC because D+1
gapped" selects the session using the very move being traded, which is
look-ahead of the worst kind. So the default policy is SKIP, and the
count of skipped announcements is reported loudly. `assume_amc` exists
because AMC is the dominant US large-cap convention, but it is an
assumption and is labelled as one in the diagnostics.

HOW LOOK-AHEAD IS PREVENTED HERE

  * Eligibility for session S is derived from announcements that were
    public BEFORE S opened. An AMC print on D is public by the open of
    D+1; a BMO print on D is public by 09:30 on D. Nothing else counts.
  * Price and liquidity screens read the PRIOR session only. The event
    session's own price contains the gap being traded.
  * Market cap is taken as-of strictly before the session, from a
    supplied series -- never back-filled from today's share count.
  * The T+1 session is the next session IN THE TICKER'S OWN DATA, not
    calendar D+1, so holidays and halts cannot silently shift a trade.

HOW SURVIVORSHIP IS PREVENTED (AND WHERE IT IS NOT)

This module can only filter the tickers it is given. If the caller's
file list came from today's index membership, the survivorship is
already baked in before the provider sees anything, and no filter here
can undo it. `diagnostics()` reports the ticker count it worked with so
the gap is visible; the fix belongs upstream, in how the data was
collected.
"""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np
import pandas as pd

BMO = "bmo"
AMC = "amc"
UNKNOWN = "unknown"
VALID_TIMING = {BMO, AMC, UNKNOWN}
UNKNOWN_POLICIES = {"skip", "assume_amc", "assume_bmo"}

#: Accepted spellings for the announcement-timing column.
_TIMING_ALIASES = {
    "bmo": BMO, "before": BMO, "before-market-open": BMO,
    "before market open": BMO, "pre": BMO, "premarket": BMO,
    "amc": AMC, "after": AMC, "after-market-close": AMC,
    "after market close": AMC, "post": AMC, "aftermarket": AMC,
}


class UniverseError(Exception):
    """Raised when a universe source is malformed or unusable."""


# ------------------------------------------------------------- the interface

class UniverseProvider(ABC):
    """Answers: may this strategy evaluate (ticker, session)?

    Implementations return a mapping of ticker -> set of eligible
    session dates. A set rather than a mask because it composes cleanly
    and because `StrategyBase.run_many` already takes that shape.
    """

    @abstractmethod
    def eligible(self, frames: dict[str, pd.DataFrame],
                 start=None, end=None) -> dict[str, set[dt.date]]:
        raise NotImplementedError

    def diagnostics(self) -> dict:
        """What the provider did and what it threw away.

        Always report the drops. A universe filter that silently removes
        90% of candidates looks identical to one that removes 5% until
        somebody counts.
        """
        return {}

    def __and__(self, other: "UniverseProvider") -> "IntersectionUniverse":
        return IntersectionUniverse([self, other])


class AllSessions(UniverseProvider):
    """Every session in the data. The old implicit behaviour, made explicit.

    Kept so that "no filtering" is a deliberate choice a reader can see
    in the run header, rather than the absence of one.
    """

    def eligible(self, frames, start=None, end=None):
        out = {}
        for t, bars in frames.items():
            d = _sessions(bars, start, end)
            if d:
                out[t] = set(d)
        self._n = sum(len(v) for v in out.values())
        return out

    def diagnostics(self):
        return {"provider": "AllSessions",
                "eligible_pairs": getattr(self, "_n", 0),
                "note": "NO universe filtering applied"}


class IntersectionUniverse(UniverseProvider):
    """All constituent providers must agree."""

    def __init__(self, providers: list[UniverseProvider]) -> None:
        if not providers:
            raise UniverseError("IntersectionUniverse needs at least one provider")
        self.providers = providers

    def eligible(self, frames, start=None, end=None):
        acc: dict[str, set[dt.date]] | None = None
        for p in self.providers:
            e = p.eligible(frames, start, end)
            if acc is None:
                acc = {k: set(v) for k, v in e.items()}
            else:
                acc = {k: acc[k] & e.get(k, set()) for k in acc}
        return {k: v for k, v in (acc or {}).items() if v}

    def diagnostics(self):
        return {"provider": "Intersection",
                "parts": [p.diagnostics() for p in self.providers]}


# ------------------------------------------------------- the earnings source

class EarningsCalendar:
    """Announcement dates and timing, loaded from an explicit source.

    EXPECTED FORMAT -- CSV or Parquet, one row per announcement:

        ticker,announce_date,announce_time
        AAPL,2025-10-30,amc
        MSFT,2025-10-29,bmo
        NVDA,2025-11-19,

      ticker         must match the bar-file ticker, case-insensitive
      announce_date  the date the company REPORTED, not the date traded
      announce_time  bmo | amc | blank. Aliases accepted: before/after,
                     pre/post, "before market open", etc.

    A blank or unrecognised `announce_time` becomes `unknown` and is
    handled by the provider's `unknown_timing` policy -- it is never
    guessed here.
    """

    def __init__(self, table: pd.DataFrame, source: str = "<memory>") -> None:
        self.source = source
        self.table = self._normalise(table, source)

    # -- constructors -------------------------------------------------

    @classmethod
    def from_file(cls, path: Path | str) -> "EarningsCalendar":
        path = Path(path)
        if not path.is_file():
            raise UniverseError(f"earnings calendar not found: {path}")
        if path.suffix.lower() in (".parquet", ".pq"):
            t = pd.read_parquet(path)
        elif path.suffix.lower() in (".csv", ".txt"):
            t = pd.read_csv(path)
        else:
            raise UniverseError(f"unsupported earnings file type: {path.suffix}")
        return cls(t, str(path))

    @classmethod
    def from_dict(cls, mapping: dict[str, list]) -> "EarningsCalendar":
        """`{"AAPL": [("2025-10-30", "amc"), "2025-07-31"], ...}`

        A bare date with no timing becomes `unknown`, which the provider
        then handles by policy rather than by assumption.
        """
        rows = []
        for ticker, entries in mapping.items():
            for e in entries:
                if isinstance(e, (tuple, list)):
                    d, when = (list(e) + [None])[:2]
                else:
                    d, when = e, None
                rows.append({"ticker": ticker, "announce_date": d,
                             "announce_time": when})
        return cls(pd.DataFrame(rows), "<dict>")

    # -- internals ----------------------------------------------------

    @staticmethod
    def _normalise(t: pd.DataFrame, source: str) -> pd.DataFrame:
        cols = {c.lower().strip(): c for c in t.columns}
        need = ("ticker", "announce_date")
        missing = [c for c in need if c not in cols]
        if missing:
            raise UniverseError(
                f"{source}: earnings calendar missing column(s) {missing}. "
                f"Expected ticker, announce_date and optionally "
                f"announce_time; found {sorted(t.columns)}.")

        out = pd.DataFrame({
            "ticker": t[cols["ticker"]].astype(str).str.upper().str.strip(),
            "announce_date": pd.to_datetime(t[cols["announce_date"]],
                                            errors="coerce"),
        })
        if out["announce_date"].isna().any():
            n = int(out["announce_date"].isna().sum())
            raise UniverseError(f"{source}: {n} unparseable announce_date value(s)")
        out["announce_date"] = out["announce_date"].dt.date

        if "announce_time" in cols:
            raw = t[cols["announce_time"]].astype(str).str.lower().str.strip()
            out["announce_time"] = raw.map(_TIMING_ALIASES).fillna(UNKNOWN)
        else:
            out["announce_time"] = UNKNOWN
        return out.drop_duplicates().sort_values(
            ["ticker", "announce_date"]).reset_index(drop=True)

    # -- queries ------------------------------------------------------

    @property
    def tickers(self) -> set[str]:
        return set(self.table["ticker"].unique())

    def timing_mix(self) -> dict:
        v = self.table["announce_time"].value_counts()
        return {k: int(v.get(k, 0)) for k in (BMO, AMC, UNKNOWN)}

    def for_ticker(self, ticker: str) -> pd.DataFrame:
        return self.table[self.table["ticker"] == ticker.upper()]


# ---------------------------------------------------------- the concrete one

class PostEarningsUniverse(UniverseProvider):
    """Post-earnings T+1 sessions passing point-in-time screens.

    Every screen is evaluated on information available before the
    session opens. Nothing reads the session being traded.
    """

    def __init__(self, calendar: EarningsCalendar,
                 min_price: float = 0.0,
                 min_market_cap: float = 0.0,
                 min_adv_shares: float = 0.0,
                 min_adtv_usd: float = 0.0,
                 adv_lookback: int = 63,
                 market_caps: pd.DataFrame | None = None,
                 unknown_timing: str = "skip",
                 post_earnings_only: bool = True) -> None:
        if unknown_timing not in UNKNOWN_POLICIES:
            raise UniverseError(
                f"unknown_timing must be one of {sorted(UNKNOWN_POLICIES)}, "
                f"got {unknown_timing!r}")
        if min_market_cap > 0 and market_caps is None:
            raise UniverseError(
                "min_market_cap is set but no market_caps series was supplied. "
                "Market cap cannot be derived from price bars, and inferring "
                "it from today's share count would back-fill a number that "
                "did not exist at the time. Supply a (ticker, date, "
                "market_cap) frame or set min_market_cap to 0.")
        self.calendar = calendar
        self.min_price = min_price
        self.min_market_cap = min_market_cap
        self.min_adv_shares = min_adv_shares
        self.min_adtv_usd = min_adtv_usd
        self.adv_lookback = adv_lookback
        self.market_caps = _normalise_caps(market_caps)
        self.unknown_timing = unknown_timing
        self.post_earnings_only = post_earnings_only
        self._diag: dict = {}

    # -- the mapping --------------------------------------------------

    def eligible(self, frames, start=None, end=None):
        counts = {"candidate_sessions": 0, "after_earnings": 0,
                  "after_price": 0, "after_mcap": 0, "after_liquidity": 0,
                  "unknown_timing_skipped": 0, "no_next_session": 0,
                  "no_prior_session": 0, "tickers_without_earnings": 0}
        out: dict[str, set[dt.date]] = {}

        for ticker, bars in frames.items():
            sessions = _sessions(bars, None, None)     # full history first
            if not sessions:
                continue
            index = {d: i for i, d in enumerate(sessions)}
            counts["candidate_sessions"] += len(
                _sessions(bars, start, end))

            if self.post_earnings_only:
                ann = self.calendar.for_ticker(ticker)
                if ann.empty:
                    counts["tickers_without_earnings"] += 1
                    continue
                react = set()
                for _, r in ann.iterrows():
                    s, why = self._reaction_session(r, sessions, index)
                    if s is None:
                        counts[why] += 1
                        continue
                    react.add(s)
            else:
                react = set(sessions)
            counts["after_earnings"] += len(react)

            keep = set()
            daily = _daily(bars)
            for s in react:
                i = index.get(s)
                if i is None or i == 0:
                    counts["no_prior_session"] += 1
                    continue                    # nothing to screen on
                stage = self._screen(ticker, s, daily, sessions, i)
                # Count survivors cumulatively, so the diagnostic reads as
                # a funnel rather than a set of unrelated numbers.
                if stage >= 1:
                    counts["after_price"] += 1
                if stage >= 2:
                    counts["after_mcap"] += 1
                if stage >= 3:
                    counts["after_liquidity"] += 1
                    keep.add(s)

            keep = {d for d in keep if _in_window(d, start, end)}
            if keep:
                out[ticker] = keep

        counts["eligible_pairs"] = sum(len(v) for v in out.values())
        counts["eligible_tickers"] = len(out)
        self._diag = counts
        return out

    def _reaction_session(self, row, sessions: list[dt.date],
                          index: dict) -> tuple[dt.date | None, str]:
        """Map one announcement to the session that trades the reaction."""
        when = row["announce_time"]
        if when == UNKNOWN:
            if self.unknown_timing == "skip":
                return None, "unknown_timing_skipped"
            when = AMC if self.unknown_timing == "assume_amc" else BMO

        d = row["announce_date"]
        if when == BMO:
            # Reported before the open: the same session reacts, and only
            # if that session actually traded.
            return (d, "") if d in index else (None, "no_next_session")

        # AMC: the next session IN THIS TICKER'S OWN DATA. Calendar +1
        # would land on a weekend or holiday and silently drop the trade.
        nxt = _next_session(sessions, d)
        return (nxt, "") if nxt is not None else (None, "no_next_session")

    def _screen(self, ticker: str, session: dt.date, daily: pd.DataFrame,
                sessions: list[dt.date], i: int) -> int:
        """How far this session gets through the funnel: 0, 1, 2 or 3.

        All screens read the PRIOR session. None reads `session` -- its
        open contains the gap being traded, so screening on it would be
        selecting the cohort using the move itself.
        """
        prev = sessions[i - 1]
        prow = daily.loc[prev]

        if self.min_price > 0 and float(prow["close"]) < self.min_price:
            return 0

        if self.min_market_cap > 0:
            mc = self._cap_asof(ticker, session)
            if not np.isfinite(mc) or mc < self.min_market_cap:
                return 1

        if self.min_adv_shares > 0 or self.min_adtv_usd > 0:
            lo = max(0, i - self.adv_lookback)
            win = daily.iloc[lo:i]                 # excludes `session`
            if len(win) < self.adv_lookback:
                return 2                           # no partial baselines
            if self.min_adv_shares > 0 and float(win["volume"].mean()) < self.min_adv_shares:
                return 2
            if self.min_adtv_usd > 0:
                adtv = float((win["close"] * win["volume"]).mean())
                if adtv < self.min_adtv_usd:
                    return 2
        return 3

    def _cap_asof(self, ticker: str, session: dt.date) -> float:
        """Latest market cap STRICTLY BEFORE the session."""
        if self.market_caps is None:
            return float("nan")
        g = self.market_caps.get(ticker.upper())
        if g is None or not len(g):
            return float("nan")
        prior = g[g.index < session]
        return float(prior.iloc[-1]) if len(prior) else float("nan")

    def diagnostics(self):
        d = {"provider": "PostEarningsUniverse",
             "earnings_source": self.calendar.source,
             "timing_mix": self.calendar.timing_mix(),
             "unknown_timing_policy": self.unknown_timing,
             "min_price": self.min_price,
             "min_market_cap": self.min_market_cap,
             "min_adv_shares": self.min_adv_shares,
             "min_adtv_usd": self.min_adtv_usd,
             **self._diag}
        if self.unknown_timing != "skip":
            d["WARNING"] = (f"announcements with unknown timing were treated "
                            f"as {self.unknown_timing.replace('assume_', '').upper()}. "
                            f"That is an assumption, not data.")
        return d


# ------------------------------------------------------------------ helpers

def _sessions(bars: pd.DataFrame, start, end) -> list[dt.date]:
    if "session_date" not in bars.columns:
        raise UniverseError("bars must carry session_date; load with annotate=True")
    d = sorted(set(bars["session_date"]))
    return [x for x in d if _in_window(x, start, end)]


def _in_window(d: dt.date, start, end) -> bool:
    if start is not None and d < pd.Timestamp(start).date():
        return False
    if end is not None and d > pd.Timestamp(end).date():
        return False
    return True


def _next_session(sessions: list[dt.date], after: dt.date) -> dt.date | None:
    i = np.searchsorted(np.array(sessions, dtype="object"), after, side="right")
    return sessions[i] if i < len(sessions) else None


def _daily(bars: pd.DataFrame) -> pd.DataFrame:
    g = bars.groupby("session_date")
    return pd.DataFrame({"close": g["close"].last(),
                         "volume": g["volume"].sum()}).sort_index()


def _normalise_caps(caps: pd.DataFrame | None):
    """(ticker, date, market_cap) -> {ticker: Series indexed by date}."""
    if caps is None:
        return None
    cols = {c.lower().strip(): c for c in caps.columns}
    for need in ("ticker", "date", "market_cap"):
        if need not in cols:
            raise UniverseError(
                f"market_caps needs columns ticker, date, market_cap; "
                f"found {sorted(caps.columns)}")
    t = pd.DataFrame({
        "ticker": caps[cols["ticker"]].astype(str).str.upper(),
        "date": pd.to_datetime(caps[cols["date"]]).dt.date,
        "market_cap": pd.to_numeric(caps[cols["market_cap"]], errors="coerce"),
    }).dropna().sort_values(["ticker", "date"])
    return {k: g.set_index("date")["market_cap"]
            for k, g in t.groupby("ticker")}


def from_config(cfg, earnings_path=None, market_caps=None,
                unknown_timing: str = "skip") -> UniverseProvider:
    """Build the provider the config asks for.

    A config that demands `post_earnings_only` without a calendar is an
    error, not a silent fallback to every session. That silence is
    exactly the bug this module exists to close.
    """
    u = cfg.universe
    if not u.post_earnings_only:
        if u.min_price <= 0 and u.min_market_cap <= 0:
            return AllSessions()
        return PostEarningsUniverse(
            EarningsCalendar(pd.DataFrame(
                columns=["ticker", "announce_date", "announce_time"])),
            min_price=u.min_price, min_market_cap=u.min_market_cap,
            market_caps=market_caps, post_earnings_only=False)

    if earnings_path is None:
        raise UniverseError(
            "universe.post_earnings_only is true but no earnings calendar was "
            "supplied. Pass --earnings <file>, or set post_earnings_only: "
            "false and accept that the strategy will evaluate every session.")
    return PostEarningsUniverse(
        EarningsCalendar.from_file(earnings_path),
        min_price=u.min_price, min_market_cap=u.min_market_cap,
        market_caps=market_caps, unknown_timing=unknown_timing)
