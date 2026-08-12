"""
core_post_earnings.py -- the Core Post-Earnings Continuation strategy.

RULES, restated so the code can be read against them:

  the session gaps (open != prior close)
  the opening candle -- 09:30 to the entry minute -- traded on volume
    above `volume_ratio_min` times its own trailing same-slot mean
  that candle closed IN the gap direction and is not a doji
    (body / range > doji_max_body_ratio)
  enter at the open of the entry bar, long on a gap up, short on a gap
    down; hold `hold_minutes`

WHAT MAKES THIS SAFE RATHER THAN JUST CAREFUL

There is no `.shift()` anywhere below, and there is no way to add one,
because there is nothing here to shift. `view.prior` contains only
completed sessions and `view.today` stops strictly before the decision
instant, so every quantity used is trailing by construction. The only
value drawn from the entry minute is `view.entry_open`, which is the
opening print at exactly the decision instant -- knowable, unlike that
bar's high, low and close, which the view withholds.

The `evaluate` method is a pure function of the view. That is what lets
`verify_no_lookahead` prove the point by deleting the future and
checking the answer does not move.
"""

from __future__ import annotations

import pandas as pd

from engine.pit import SessionView
from engine.strategy_base import Signal, StrategyBase


class CorePostEarningsContinuation(StrategyBase):

    def evaluate(self, view: SessionView) -> Signal | None:
        cfg = self.config
        sig, ex = cfg.signal, cfg.exit

        # The opening candle runs from the open to the minute before
        # entry: with entry at 09:35 that is minutes 0-4 inclusive, and
        # its close is the 09:34 bar's close, printed at 09:35:00.
        entry_min = _minutes_from_open(sig.entry_time)
        if entry_min <= 0:
            return None
        candle = view.candle(0, entry_min - 1)
        if candle is None:
            return None

        # --- gap -------------------------------------------------------
        gap = view.gap()
        if not _finite(gap):
            return None
        if sig.gap_required and gap == 0.0:
            return None
        direction = 1 if gap > 0 else -1

        # --- volume ----------------------------------------------------
        vr = view.volume_ratio(0, entry_min - 1, sig.volume_lookback_sessions)
        if not _finite(vr) or vr <= sig.volume_ratio_min:
            return None

        # --- candle shape ----------------------------------------------
        rng = candle["high"] - candle["low"]
        if rng <= 0:
            return None                      # zero-range bar: no information
        body = candle["close"] - candle["open"]
        body_ratio = abs(body) / rng
        is_doji = body_ratio <= sig.doji_max_body_ratio
        closes_with_gap = (body > 0) == (gap > 0)

        if sig.candle == "continuation":
            if is_doji or not closes_with_gap:
                return None
        elif sig.candle == "reversal":
            if is_doji or closes_with_gap:
                return None
            direction = -direction           # fade the gap

        # --- risk unit --------------------------------------------------
        atr = view.prior.atr(sig.atr_period)
        if not _finite(atr) or atr <= 0:
            return None

        # --- direction override from config -----------------------------
        if cfg.direction == "long_only" and direction < 0:
            return None
        if cfg.direction == "short_only" and direction > 0:
            return None

        price = view.entry_open if sig.entry_price == "open" else view.entry_open
        if not _finite(price) or price <= 0:
            return None                      # no bar printed at the entry minute

        return Signal(
            ticker=view.ticker,
            session=view.session,
            decision_ts=view.decision_ts,
            direction=direction,
            entry_ts=view.decision_ts,
            entry_price=price,
            risk_unit=atr,
            planned_exit_ts=view.decision_ts + pd.Timedelta(minutes=ex.hold_minutes),
            features={
                "gap_pct": gap * 100.0,
                "gap_atr": abs(view.session_open() - view.prior.last_close()) / atr,
                "volume_ratio": vr,
                "body_over_range": body_ratio,
                "atr_pct": atr / price * 100.0,
                "candle_close": candle["close"],
                "candle_volume": candle["volume"],
            },
        )


def _minutes_from_open(entry_time) -> int:
    """Entry time as minutes since the 09:30 local open."""
    return (entry_time.hour * 60 + entry_time.minute) - (9 * 60 + 30)


def _finite(x: float) -> bool:
    return x == x and x not in (float("inf"), float("-inf"))
