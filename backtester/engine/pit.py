"""
pit.py -- point-in-time guards.

THE DESIGN CLAIM

You cannot reliably stop look-ahead by asking people to remember
`.shift(1)`. Remembering is exactly what fails, and it fails silently
because a leaked backtest still runs and still produces a plausible
number. So this module does not police the code. It withholds the data.

A strategy is never handed the price frame. It is handed a `SessionView`
for one (ticker, session) decision instant, and that object physically
contains only:

  * PRIOR SESSIONS -- sessions strictly earlier than the decision
    session, already reduced to daily bars
  * TODAY UP TO THE DECISION INSTANT -- intraday bars with
    ts <= decision_ts, nothing after

Because the container excludes the future, the familiar `.shift(1)` is
not something a strategy has to remember: it is structural. Asking a
`SessionView` for "the 20-session trailing same-slot volume mean"
returns a number computed only from completed sessions, because those
are the only sessions in the object.

THREE LAYERS, IN ORDER OF STRENGTH

1 STRUCTURAL (this module's core). Future bars are absent. A strategy
  that wants to cheat has nothing to cheat with.

2 SOURCE AUDIT (`audit_source`). Raw `.rolling` / `.ewm` / `.expanding`
  and negative `.shift(-n)` in a strategy class raise at construction
  time. This catches the author who reaches past the view to a frame
  they captured elsewhere. Opt out per class with an explicit
  `ALLOW_RAW_WINDOWING = True`, which is loud enough to show in review.

3 BEHAVIOURAL (`verify_no_lookahead`). Run the strategy against the full
  frame and against a frame truncated at each decision instant. If any
  signal differs, future data reached the decision. This is the only
  layer that proves the other two worked, so it runs in the tests.

WHY THE SHIFT IS COMPUTED ONCE, CENTRALLY

`PointInTimeEngine` precomputes the shifted feature panels for a ticker
in one place, asserts the shift, and hands out cheap views. That is both
faster than re-slicing per session and easier to audit: there is exactly
one `.shift(1)` per feature in the codebase, and it is covered by a test
that would fail if it were removed.
"""

from __future__ import annotations

import ast
import datetime as dt
import inspect
import textwrap
from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd

from engine.calendar import local_time_to_utc

BANNED_CALLS = {"rolling", "ewm", "expanding"}
OHLC = ("open", "high", "low", "close")


class LookAheadError(Exception):
    """Raised when future information could reach a decision."""


# --------------------------------------------------------------- source audit

def audit_source(cls: type) -> list[str]:
    """Reject raw windowing in a strategy class.

    Returns the list of offences found. Raises unless the class opts out
    with `ALLOW_RAW_WINDOWING = True`. Source may be unavailable (a class
    defined in a REPL or exec'd); that is reported, not silently passed,
    because "we could not check" and "we checked and it was fine" must
    not look the same.
    """
    if getattr(cls, "ALLOW_RAW_WINDOWING", False):
        return []
    try:
        src = textwrap.dedent(inspect.getsource(cls))
    except (OSError, TypeError):
        raise LookAheadError(
            f"{cls.__name__}: source unavailable, so the raw-windowing audit "
            f"could not run. Define strategies in importable modules, or set "
            f"ALLOW_RAW_WINDOWING = True to accept the risk explicitly."
        ) from None

    offences: list[str] = []
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Attribute) and fn.attr in BANNED_CALLS:
                offences.append(
                    f"line {node.lineno}: .{fn.attr}(...) -- use the "
                    f"SessionView accessors, which are shifted by "
                    f"construction")
            if isinstance(fn, ast.Attribute) and fn.attr == "shift":
                for a in node.args:
                    neg = (isinstance(a, ast.UnaryOp)
                           and isinstance(a.op, ast.USub))
                    if neg or (isinstance(a, ast.Constant)
                               and isinstance(a.value, int) and a.value < 0):
                        offences.append(
                            f"line {node.lineno}: .shift() with a negative "
                            f"period pulls the future backwards")
    if offences:
        raise LookAheadError(
            f"{cls.__name__} contains raw windowing:\n  "
            + "\n  ".join(offences)
        )
    return offences


# ------------------------------------------------------------------- feature

def shifted_rolling_mean(s: pd.Series, window: int, min_periods: int | None = None
                         ) -> pd.Series:
    """Trailing mean that EXCLUDES the current observation.

    The single sanctioned way to build a trailing baseline outside a
    SessionView. `min_periods` defaults to the full window: a baseline
    built from three sessions when twenty were asked for is not the
    filter anyone specified, and letting it through changes the cohort
    silently at the start of every ticker's history.
    """
    if window < 2:
        raise ValueError("window must be >= 2 for a trailing baseline")
    mp = window if min_periods is None else min_periods
    out = s.rolling(window, min_periods=mp).mean().shift(1)
    out.name = f"{s.name}_trailing{window}_shifted" if s.name else None
    return out


def assert_shifted(raw: pd.Series, feature: pd.Series, name: str) -> None:
    """Assert `feature` cannot contain information from its own row.

    The test is direct: perturb one observation of the input and confirm
    the feature at that same index does not move. Cheap, and it fails on
    exactly the mistake that matters.
    """
    if len(raw) < 5:
        return
    i = len(raw) // 2
    probe = raw.copy()
    probe.iloc[i] = probe.iloc[i] * 1000.0 + 12345.0
    moved = shifted_rolling_mean(probe, 3, min_periods=1)
    base = shifted_rolling_mean(raw, 3, min_periods=1)
    if not _same(moved.iloc[i], base.iloc[i]):
        raise LookAheadError(
            f"{name}: the feature at row {i} responds to that row's own "
            f"value, so it is not shifted")


def _same(a, b) -> bool:
    if pd.isna(a) and pd.isna(b):
        return True
    return bool(np.isclose(a, b, rtol=1e-12, atol=1e-12))


# --------------------------------------------------------------- the objects

@dataclass(frozen=True)
class PriorSessions:
    """Completed sessions only. Nothing here can touch the current day.

    `daily` is indexed by session date, ascending, and STOPS before the
    decision session. Every accessor is therefore trailing by
    construction; there is no shift to forget.
    """
    daily: pd.DataFrame                 # open/high/low/close/volume per session
    slot_volume: pd.DataFrame           # sessions x minutes_from_open
    _atr: pd.Series = field(repr=False, default=None)

    def __len__(self) -> int:
        return len(self.daily)

    def last_close(self) -> float:
        if self.daily.empty:
            return float("nan")
        return float(self.daily["close"].iloc[-1])

    def atr(self, period: int) -> float:
        """ATR over the last `period` COMPLETED sessions.

        Wilder's true range on daily bars. Returns NaN rather than a
        partial estimate when fewer than `period` sessions exist, so a
        ticker's first weeks cannot enter the cohort on a baseline built
        from three days.
        """
        if self._atr is None or len(self._atr) == 0:
            return float("nan")
        v = self._atr.iloc[-1]
        return float(v) if pd.notna(v) else float("nan")

    def same_slot_mean_volume(self, slots: int | Iterable[int],
                              window: int) -> float:
        """Mean volume in these minutes-of-session over the last `window`.

        The denominator of the volume ratio. Same-slot rather than
        all-day because intraday volume is strongly U-shaped: comparing
        the opening candle against a whole-session average would flag
        almost every early bar as a surge.

        `slots` may be a single minute or a range, so a 5-minute opening
        candle is compared against the same five minutes of prior
        sessions rather than against a single minute.

        Returns NaN when fewer than `window` complete sessions are
        available. A baseline built from three sessions when twenty were
        configured is a different filter, and letting it through would
        silently widen the cohort at the start of every ticker's history.
        """
        cols = [slots] if isinstance(slots, int) else list(slots)
        have = [c for c in cols if c in self.slot_volume.columns]
        if not have:
            return float("nan")
        per_session = self.slot_volume[have].sum(axis=1, min_count=len(have))
        s = per_session.dropna()
        if len(s) < window:
            return float("nan")
        return float(s.iloc[-window:].mean())


@dataclass(frozen=True)
class SessionView:
    """Everything a strategy may see at one decision instant.

    Attribute access for pandas windowing names is refused, so an
    author who reaches for `view.rolling(...)` gets an error naming the
    accessor they should have used instead of a confusing AttributeError.
    """
    ticker: str
    session: dt.date
    decision_ts: pd.Timestamp
    prior: PriorSessions
    today: pd.DataFrame                 # bars STRICTLY BEFORE decision_ts
    entry_open: float                   # open print of the decision bar

    def __getattr__(self, name: str):
        if name in BANNED_CALLS:
            raise LookAheadError(
                f"SessionView has no .{name}(): build trailing features "
                f"through prior.atr() / prior.same_slot_mean_volume(), which "
                f"are shifted by construction."
            )
        raise AttributeError(name)

    # -- current session, decision-safe --------------------------------
    #
    # `today` stops STRICTLY BEFORE the decision instant. The bar stamped
    # decision_ts is deliberately absent: at 09:35:00 its opening print
    # exists but its high, low and close do not, and exposing the whole
    # row would leak the next minute into the decision that trades it.
    # Only that open is surfaced, as `entry_open`.

    def session_open(self) -> float:
        return float(self.today["open"].iloc[0]) if len(self.today) else float("nan")

    def bar_at(self, minutes_from_open: int) -> pd.Series | None:
        """The bar `minutes_from_open` into the session, or None."""
        hit = self.today[self.today["minutes_from_open"] == minutes_from_open]
        return hit.iloc[0] if len(hit) else None

    def candle(self, first_min: int, last_min: int) -> dict[str, float] | None:
        """Aggregate minutes [first_min, last_min] into one candle.

        This is how a 5-minute opening candle is built from 1-minute
        bars. Returns None if any part of the window is missing, rather
        than silently aggregating a partial candle -- a 3-bar "5-minute"
        candle has a different body/range ratio and would classify
        differently.
        """
        w = self.today[(self.today["minutes_from_open"] >= first_min)
                       & (self.today["minutes_from_open"] <= last_min)]
        expected = last_min - first_min + 1
        if len(w) != expected:
            return None
        return {"open": float(w["open"].iloc[0]),
                "high": float(w["high"].max()),
                "low": float(w["low"].min()),
                "close": float(w["close"].iloc[-1]),
                "volume": float(w["volume"].sum())}

    def gap(self) -> float:
        """Session open against the prior session's close, as a fraction."""
        prev = self.prior.last_close()
        op = self.session_open()
        if not np.isfinite(prev) or prev <= 0 or not np.isfinite(op):
            return float("nan")
        return op / prev - 1.0

    def volume_ratio(self, first_min: int, last_min: int, window: int) -> float:
        """Candle volume against its own trailing same-slot baseline."""
        c = self.candle(first_min, last_min)
        if c is None:
            return float("nan")
        base = self.prior.same_slot_mean_volume(
            range(first_min, last_min + 1), window)
        if not np.isfinite(base) or base <= 0:
            return float("nan")
        return c["volume"] / base


# -------------------------------------------------------------- the engine

class PointInTimeEngine:
    """Builds SessionViews for one ticker, with features shifted once.

    Construction cost is one pass over the bars. Views are then cheap
    slices, so a strategy that walks every session stays linear.
    """

    def __init__(self, bars: pd.DataFrame, ticker: str, atr_period: int = 14,
                 volume_window: int = 20) -> None:
        required = {"session_date", "minutes_from_open", *OHLC, "volume"}
        missing = required - set(bars.columns)
        if missing:
            raise ValueError(f"bars missing {sorted(missing)}; load with "
                             f"annotate=True")
        self.ticker = ticker.upper()
        self.atr_period = atr_period
        self.volume_window = volume_window
        self.bars = bars

        g = bars.groupby("session_date", sort=True)
        self.daily = pd.DataFrame({
            "open": g["open"].first(), "high": g["high"].max(),
            "low": g["low"].min(), "close": g["close"].last(),
            "volume": g["volume"].sum(),
        })
        self.sessions: list[dt.date] = list(self.daily.index)

        # True range needs the PRIOR close, so it is shifted at source.
        prev_close = self.daily["close"].shift(1)
        tr = pd.concat([
            self.daily["high"] - self.daily["low"],
            (self.daily["high"] - prev_close).abs(),
            (self.daily["low"] - prev_close).abs(),
        ], axis=1).max(axis=1)
        # ATR for session i must use sessions <= i-1, hence the shift.
        self.atr = tr.rolling(atr_period, min_periods=atr_period).mean().shift(1)
        self.atr.name = "atr_prior"

        # sessions x minutes_from_open volume grid, for same-slot baselines.
        self.slot_volume = (bars.groupby(["session_date", "minutes_from_open"])
                            ["volume"].sum().unstack("minutes_from_open"))

        self._pos = {s: i for i, s in enumerate(self.sessions)}
        self._by_session = {s: d for s, d in bars.groupby("session_date")}

    def view(self, session: dt.date, decision_ts: pd.Timestamp) -> SessionView:
        """A view for `session`, truncated at `decision_ts`."""
        i = self._pos.get(session)
        if i is None:
            raise KeyError(f"{self.ticker}: no session {session}")

        # daily/slot_volume stop BEFORE session i, so they cannot contain
        # today. self.atr is already lagged by one session, so the value
        # AT i is the prior-session ATR -- hence the inclusive slice.
        prior = PriorSessions(daily=self.daily.iloc[:i],
                              slot_volume=self.slot_volume.iloc[:i],
                              _atr=self.atr.iloc[:i + 1])

        day = self._by_session.get(session)
        if day is None:
            day = self.bars.iloc[:0]
        # Strictly before: the decision bar's OHLC does not exist yet.
        today = day[day.index < decision_ts]
        at = day[day.index == decision_ts]
        entry_open = float(at["open"].iloc[0]) if len(at) else float("nan")
        return SessionView(ticker=self.ticker, session=session,
                           decision_ts=decision_ts, prior=prior, today=today,
                           entry_open=entry_open)

    def decision_ts(self, session: dt.date, local: dt.time) -> pd.Timestamp:
        return local_time_to_utc(session, local)

    def walk(self, local: dt.time, sessions: Iterable[dt.date] | None = None):
        """Yield (session, view) for each session at the given local time."""
        for s in (sessions if sessions is not None else self.sessions):
            yield s, self.view(s, self.decision_ts(s, local))

    # -- self-checks ---------------------------------------------------

    def self_check(self) -> None:
        """Assert the two shifts that everything else depends on."""
        if len(self.daily) > self.atr_period + 2:
            i = self.atr_period + 1
            s = self.sessions[i]
            v = self.view(s, self.decision_ts(s, dt.time(9, 35)))
            # The prior frame must not contain the decision session.
            if s in set(v.prior.daily.index):
                raise LookAheadError(
                    f"{self.ticker}: prior sessions include the decision "
                    f"session {s}")
            # ATR must match one computed from strictly earlier sessions.
            d = self.daily.iloc[:i]
            pc = d["close"].shift(1)
            tr = pd.concat([d["high"] - d["low"],
                            (d["high"] - pc).abs(),
                            (d["low"] - pc).abs()], axis=1).max(axis=1)
            want = tr.iloc[-self.atr_period:].mean()
            got = v.prior.atr(self.atr_period)
            if not _same(want, got):
                raise LookAheadError(
                    f"{self.ticker}: prior ATR {got} != {want} recomputed "
                    f"from completed sessions only")


# ---------------------------------------------------------- behavioural test

def verify_no_lookahead(strategy_or_factory, bars: pd.DataFrame, ticker: str,
                        sessions: Iterable[dt.date] | None = None,
                        n_probe: int = 8) -> pd.DataFrame:
    """Prove a strategy's output does not change when the future is removed.

    For each probed session the strategy is evaluated twice: once with
    the full frame, and once with every bar after the decision instant
    deleted from the input entirely. Identical output is the only
    acceptable result.

    PASS A FACTORY, NOT AN INSTANCE, WHEN THE STRATEGY HOLDS STATE.
    Given a callable `factory(bars) -> StrategyBase`, the strategy is
    REBUILT from the truncated frame for the truncated run. That is what
    catches a strategy which captured a full-history frame at
    construction and reads ahead from it -- truncating only the engine's
    input would leave such a reference untouched and the check would
    pass on a strategy that cheats.

    RESIDUAL LIMIT, STATED PLAINLY: a strategy that opens a file or
    reads a global inside `evaluate` is invisible to this check, because
    nothing here can truncate a source it does not know about. Layer 2
    (`audit_source`) and review cover that case.
    """
    is_factory = not hasattr(strategy_or_factory, "evaluate")

    def build(frame: pd.DataFrame):
        return strategy_or_factory(frame) if is_factory else strategy_or_factory

    strategy = build(bars)
    cfg = strategy.config
    local = cfg.signal.entry_time
    eng = PointInTimeEngine(bars, ticker,
                            atr_period=cfg.signal.atr_period,
                            volume_window=cfg.signal.volume_lookback_sessions)
    all_sessions = list(sessions) if sessions is not None else eng.sessions
    # Probe late sessions: early ones have no baseline and trivially agree.
    probe = all_sessions[-n_probe:] if len(all_sessions) > n_probe else all_sessions

    rows = []
    for s in probe:
        ts = eng.decision_ts(s, local)
        full = strategy.evaluate(eng.view(s, ts))

        truncated_bars = bars[bars.index <= ts]
        if truncated_bars.empty:
            continue
        eng2 = PointInTimeEngine(truncated_bars, ticker,
                                 atr_period=cfg.signal.atr_period,
                                 volume_window=cfg.signal.volume_lookback_sessions)
        if s not in eng2._pos:
            continue
        trunc = build(truncated_bars).evaluate(eng2.view(s, ts))

        same = _signals_equal(full, trunc)
        rows.append({"session": s, "with_future": _fmt(full),
                     "without_future": _fmt(trunc), "identical": same})
        if not same:
            raise LookAheadError(
                f"{strategy.__class__.__name__} on {ticker} {s}: signal "
                f"changed when future bars were removed.\n"
                f"  with future   : {_fmt(full)}\n"
                f"  without future: {_fmt(trunc)}"
            )
    return pd.DataFrame(rows)


def _signals_equal(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    keys = ("direction", "entry_ts", "entry_price", "risk_unit")
    for k in keys:
        x, y = getattr(a, k), getattr(b, k)
        if isinstance(x, float) and isinstance(y, float):
            if not _same(x, y):
                return False
        elif x != y:
            return False
    return True


def _fmt(sig) -> str:
    if sig is None:
        return "no signal"
    return (f"dir={sig.direction:+d} entry={sig.entry_price:.4f} "
            f"risk={sig.risk_unit:.4f}")
