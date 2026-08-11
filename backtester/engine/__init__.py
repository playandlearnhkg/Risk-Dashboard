"""Backtesting engine.

Import order matters only in that `calendar` and `config` have no
intra-package dependencies beyond each other, so they can be used
standalone in notebooks without pulling in the portfolio machinery.
"""

from engine.calendar import EXCHANGE_TZ, local_time_to_utc, session_date
from engine.config import BacktestConfig, ConfigError
from engine.data_loader import DataCatalog, DataError, DataLoader, parse_filename

__all__ = [
    "EXCHANGE_TZ", "local_time_to_utc", "session_date",
    "BacktestConfig", "ConfigError",
    "DataCatalog", "DataError", "DataLoader", "parse_filename",
]
