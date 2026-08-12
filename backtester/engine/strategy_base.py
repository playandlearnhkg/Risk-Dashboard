"""
strategy_base.py -- the contract every strategy implements.

A strategy answers ONE question: given everything knowable at a single
decision instant, is there a trade, and what are its parameters?

    evaluate(view: SessionView) -> Signal | None

It never sees the price frame, never chooses its own timestamps, and
never sizes itself. Those belong to the engine, the config and the
portfolio respectively, and keeping them out is what makes a strategy
testable in isolation.

WHAT THE BASE CLASS ENFORCES

  * `audit_source` runs at construction. A subclass containing raw
    `.rolling` / `.ewm` / `.expanding`, or a negative `.shift`, refuses
    to instantiate.
  * `run()` builds views through PointInTimeEngine, so the future is
    absent from the object the subclass receives.
  * `Signal` is frozen and validated, so a strategy cannot emit a
    direction of 0, a non-positive entry price, or a risk unit of zero
    that would later divide by itself in sizing.

WHAT IT DELIBERATELY DOES NOT DO

  * No universe filtering. `post_earnings_only` and `min_market_cap` are
    point-in-time questions needing an as-of source; answering them from
    the price file would reintroduce survivorship bias through the back
    door. They are passed in via `context`.
  * No position sizing, no cost model, no exit simulation. Step 4.
"""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterable

import numpy as np
import pandas as pd

from engine.config import BacktestConfig
from engine.pit import PointInTimeEngine, SessionView, audit_source


@dataclass(frozen=True)
class Signal:
    """One decision. Everything the portfolio needs, nothing it doesn't."""
    ticker: str
    session: dt.date
    decision_ts: pd.Timestamp
    direction: int                      # +1 long, -1 short
    entry_ts: pd.Timestamp
    entry_price: float
    risk_unit: float                    # ATR at the decision, for sizing/stops
    planned_exit_ts: pd.Timestamp
    features: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.direction not in (1, -1):
            raise ValueError(f"direction must be +1 or -1, got {self.direction}")
        if not np.isfinite(self.entry_price) or self.entry_price <= 0:
            raise ValueError(f"entry_price must be positive and finite, "
                             f"got {self.entry_price}")
        if not np.isfinite(self.risk_unit) or self.risk_unit <= 0:
            raise ValueError(
                f"risk_unit must be positive and finite, got {self.risk_unit}. "
                f"A zero or NaN risk unit would divide by itself in sizing; "
                f"return None instead of emitting an unsizeable signal.")
        if self.planned_exit_ts <= self.entry_ts:
            raise ValueError("planned_exit_ts must be after entry_ts")
        if self.entry_ts < self.decision_ts:
            raise ValueError(
                f"entry_ts {self.entry_ts} precedes decision_ts "
                f"{self.decision_ts}: a trade cannot be entered before the "
                f"information that justified it existed")


class StrategyBase(ABC):
    """Subclass this. Implement `evaluate`. Nothing else is required."""

    #: Set True only with a written reason; it disables the source audit.
    ALLOW_RAW_WINDOWING: bool = False

    def __init__(self, config: BacktestConfig) -> None:
        audit_source(type(self))
        self.config = config

    # -- the one method a subclass must write --------------------------

    @abstractmethod
    def evaluate(self, view: SessionView) -> Signal | None:
        """Return a Signal for this decision instant, or None.

        `view` contains prior completed sessions and today's bars up to
        the decision instant. There is nothing else to consult, which is
        the point.
        """
        raise NotImplementedError

    # -- provided ------------------------------------------------------

    def engine_for(self, bars: pd.DataFrame, ticker: str) -> PointInTimeEngine:
        s = self.config.signal
        return PointInTimeEngine(bars, ticker, atr_period=s.atr_period,
                                 volume_window=s.volume_lookback_sessions)

    def run(self, bars: pd.DataFrame, ticker: str,
            sessions: Iterable[dt.date] | None = None,
            self_check: bool = True) -> list[Signal]:
        """Walk sessions and collect signals for one ticker."""
        eng = self.engine_for(bars, ticker)
        if self_check:
            eng.self_check()
        out: list[Signal] = []
        for _session, view in eng.walk(self.config.signal.entry_time, sessions):
            sig = self.evaluate(view)
            if sig is not None:
                out.append(sig)
        return out

    def run_many(self, frames: dict[str, pd.DataFrame],
                 eligible: dict[str, set] | None = None) -> pd.DataFrame:
        """Run across tickers and return a tidy signal table.

        `eligible` optionally restricts each ticker to a set of sessions
        -- this is where a point-in-time earnings calendar or universe
        screen plugs in, without the strategy ever loading it itself.
        """
        rows: list[dict] = []
        for ticker, bars in frames.items():
            sess = None if eligible is None else sorted(eligible.get(ticker, ()))
            if sess is not None and not sess:
                continue
            for s in self.run(bars, ticker, sessions=sess):
                rows.append({"ticker": s.ticker, "session": s.session,
                             "decision_ts": s.decision_ts,
                             "direction": s.direction, "entry_ts": s.entry_ts,
                             "entry_price": s.entry_price,
                             "risk_unit": s.risk_unit,
                             "planned_exit_ts": s.planned_exit_ts,
                             **s.features})
        cols = ["ticker", "session", "decision_ts", "direction", "entry_ts",
                "entry_price", "risk_unit", "planned_exit_ts"]
        df = pd.DataFrame(rows)
        if df.empty:
            return pd.DataFrame(columns=cols)
        return df.sort_values(["session", "ticker"]).reset_index(drop=True)
