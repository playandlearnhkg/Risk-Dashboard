"""Backtesting engine.

`calendar`, `config` and `pit` have no dependency on the portfolio
machinery, so they can be used standalone in a notebook.
"""

from engine.calendar import EXCHANGE_TZ, local_time_to_utc, session_date
from engine.config import BacktestConfig, ConfigError
from engine.data_loader import DataCatalog, DataError, DataLoader, parse_filename
from engine.pit import (LookAheadError, PointInTimeEngine, PriorSessions,
                        SessionView, audit_source, shifted_rolling_mean,
                        verify_no_lookahead)
from engine.strategy_base import Signal, StrategyBase

__all__ = [
    "EXCHANGE_TZ", "local_time_to_utc", "session_date",
    "BacktestConfig", "ConfigError",
    "DataCatalog", "DataError", "DataLoader", "parse_filename",
    "LookAheadError", "PointInTimeEngine", "PriorSessions", "SessionView",
    "audit_source", "shifted_rolling_mean", "verify_no_lookahead",
    "Signal", "StrategyBase",
]
