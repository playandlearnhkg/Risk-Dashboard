"""
strategy_base.py -- STEP 3, not yet implemented.

Contract sketch, recorded now so the loader and config above are built
against something concrete.

A strategy is a pure function of point-in-time information:

    signals(bars, context) -> DataFrame indexed by (ticker, session_date)

with at minimum the columns:

    entry_ts        UTC instant of the entry bar, resolved from
                    config.signal.entry_time via calendar.local_time_to_utc
    direction       +1 long, -1 short
    entry_price     price at entry_ts per config.signal.entry_price
    risk_unit       the ATR (or other unit) used for sizing and stops
    exit_ts         planned time exit
    features        whatever the filter used, retained for the trade log

THE ONE RULE: every input to `signals` for session S must be derivable
from bars strictly before the decision instant on S. Rolling statistics
are shifted by one session before use; the current bar never enters its
own baseline. `engine.pit` will hold the guards that enforce this, and
strategies are expected to build features through them rather than
calling .rolling() directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from engine.config import BacktestConfig


class StrategyBase(ABC):
    def __init__(self, config: BacktestConfig) -> None:
        self.config = config

    @abstractmethod
    def signals(self, bars: pd.DataFrame, context: dict) -> pd.DataFrame:
        """Point-in-time signals for one ticker. See module docstring."""
        raise NotImplementedError
