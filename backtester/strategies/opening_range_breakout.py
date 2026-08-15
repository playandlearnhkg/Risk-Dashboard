"""
opening_range_breakout.py -- a SECOND strategy, to prove the gate is not
tailored to the first.

Rule: build a range from the session open to the minute before entry. If
the entry bar's opening print is above that range, go long; below, go
short; inside, stand aside. Hold for `hold_minutes`.

It shares nothing with the post-earnings strategy except the base class:
no gap, no earnings calendar, no volume filter, no candle classification.
It uses `AllSessions` for its universe because it genuinely trades every
day, and the gate flags that choice for a human rather than assuming it
is fine.

Like every strategy here it contains no `.shift()` and no `.rolling()`,
because `view.today` stops before the decision instant and `view.prior`
holds only completed sessions. The source audit would refuse to
instantiate this class otherwise.
"""

from __future__ import annotations

import pandas as pd

from engine.pit import SessionView
from engine.strategy_base import Signal, StrategyBase


class OpeningRangeBreakout(StrategyBase):

    def evaluate(self, view: SessionView) -> Signal | None:
        sig, ex = self.config.signal, self.config.exit

        entry_min = (sig.entry_time.hour * 60 + sig.entry_time.minute) - 570
        if entry_min <= 0:
            return None
        rng = view.candle(0, entry_min - 1)
        if rng is None:
            return None

        px = view.entry_open
        if not (px == px) or px <= 0:
            return None

        if px > rng["high"]:
            direction = 1
        elif px < rng["low"]:
            direction = -1
        else:
            return None                      # inside the range: no edge claimed

        if self.config.direction == "long_only" and direction < 0:
            return None
        if self.config.direction == "short_only" and direction > 0:
            return None

        atr = view.prior.atr(sig.atr_period)
        if not (atr == atr) or atr <= 0:
            return None

        width = rng["high"] - rng["low"]
        return Signal(
            ticker=view.ticker, session=view.session,
            decision_ts=view.decision_ts, direction=direction,
            entry_ts=view.decision_ts, entry_price=px, risk_unit=atr,
            planned_exit_ts=view.decision_ts + pd.Timedelta(minutes=ex.hold_minutes),
            features={
                "range_width_atr": width / atr,
                "breakout_atr": abs(px - (rng["high"] if direction > 0
                                          else rng["low"])) / atr,
                "range_volume": rng["volume"],
                # The gate's default selection rule ranks on volume_ratio,
                # so a strategy that does not compute one must still emit
                # something rankable or the ranking silently fails.
                "volume_ratio": view.volume_ratio(0, entry_min - 1,
                                                  sig.volume_lookback_sessions),
                "gap_atr": abs(view.gap()) * view.session_open() / atr
                if view.prior.last_close() == view.prior.last_close() else float("nan"),
            },
        )
