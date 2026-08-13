"""
config.py -- YAML to validated, frozen dataclasses.

WHY THE VALIDATION IS STRICT

A configuration-driven backtester fails in a specific, nasty way: a
mistyped key is silently ignored, the default is used instead, and the
run completes and produces a number. `volume_ratio_min: 1.5` typed as
`volume_ratio_mim: 1.5` would quietly disable the filter that defines
the cohort. So:

  * unknown keys RAISE, with the offending path and the valid keys
  * every enum-like field is checked against its allowed set
  * every numeric field is range-checked
  * the resulting objects are FROZEN, so nothing downstream can mutate
    the configuration mid-run and make the results irreproducible

Errors carry the dotted path (`signal.volume_ratio_min`) because a bare
"invalid value" in a nested config is a scavenger hunt.

WARNINGS VS ERRORS

Some combinations are legal but load-bearing enough that a silent run
would be misleading -- most importantly fixed-fractional sizing with the
stop DISABLED. Sizing then divides by 1 ATR as a risk PROXY, but nothing
bounds the loss at 1 ATR, so a "0.5% risk" trade can lose several times
that. That is a legitimate way to run the strategy; it just must not be
mistaken for a risk limit. Those cases are returned by `warnings()` for
the runner to print rather than raised.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from typing import Any

import yaml

from engine.calendar import parse_local_time

CANDLE_TYPES = {"continuation", "reversal", "any"}
DIRECTIONS = {"signed", "long_only", "short_only"}
SIZING_METHODS = {"fixed_risk_pct", "fixed_notional"}
EXIT_TYPES = {"time"}
STOP_TYPES = {"atr"}
# Only "open" is implementable. See _check_coherence for why.
ENTRY_PRICES = {"open", "close"}
RISK_UNITS = {"atr"}


class ConfigError(Exception):
    """Raised for any malformed or internally inconsistent configuration."""


def _check_keys(raw: dict, cls: type, path: str) -> None:
    known = {f.name for f in fields(cls)}
    unknown = set(raw) - known
    if unknown:
        raise ConfigError(
            f"{path}: unknown key(s) {sorted(unknown)}. "
            f"Valid keys are {sorted(known)}."
        )


def _num(raw: dict, key: str, path: str, *, lo=None, hi=None,
         lo_open=False, hi_open=False, default=None) -> float:
    if key not in raw:
        if default is None:
            raise ConfigError(f"{path}.{key}: required")
        return default
    v = raw[key]
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ConfigError(f"{path}.{key}: expected a number, got {v!r}")
    v = float(v)
    if lo is not None and (v <= lo if lo_open else v < lo):
        raise ConfigError(f"{path}.{key}: must be "
                          f"{'>' if lo_open else '>='} {lo}, got {v}")
    if hi is not None and (v >= hi if hi_open else v > hi):
        raise ConfigError(f"{path}.{key}: must be "
                          f"{'<' if hi_open else '<='} {hi}, got {v}")
    return v


def _choice(raw: dict, key: str, path: str, allowed: set[str],
            default: str | None = None) -> str:
    v = raw.get(key, default)
    if v is None:
        raise ConfigError(f"{path}.{key}: required, one of {sorted(allowed)}")
    if v not in allowed:
        raise ConfigError(f"{path}.{key}: {v!r} is not one of {sorted(allowed)}")
    return v


def _flag(raw: dict, key: str, path: str, default: bool) -> bool:
    v = raw.get(key, default)
    if not isinstance(v, bool):
        raise ConfigError(f"{path}.{key}: expected true/false, got {v!r}")
    return v


@dataclass(frozen=True)
class StrategyMeta:
    name: str
    version: str = "1.0"

    @classmethod
    def parse(cls, raw: dict, path: str = "strategy") -> StrategyMeta:
        _check_keys(raw, cls, path)
        if "name" not in raw:
            raise ConfigError(f"{path}.name: required")
        return cls(name=str(raw["name"]), version=str(raw.get("version", "1.0")))


@dataclass(frozen=True)
class UniverseConfig:
    """Point-in-time universe filters.

    These need an as-of reference source (earnings dates, market cap);
    none of them can be answered from the price file alone, and none is
    applied by DataLoader. They live here so the strategy layer can
    apply them against whatever universe provider is wired in.
    """
    post_earnings_only: bool = True
    min_price: float = 0.0
    min_market_cap: float = 0.0

    @classmethod
    def parse(cls, raw: dict, path: str = "universe") -> UniverseConfig:
        _check_keys(raw, cls, path)
        return cls(
            post_earnings_only=_flag(raw, "post_earnings_only", path, True),
            min_price=_num(raw, "min_price", path, lo=0.0, default=0.0),
            min_market_cap=_num(raw, "min_market_cap", path, lo=0.0, default=0.0),
        )


@dataclass(frozen=True)
class SignalConfig:
    volume_ratio_min: float
    candle: str
    doji_max_body_ratio: float
    gap_required: bool
    entry_time: dt.time                 # EXCHANGE LOCAL time, not UTC
    entry_price: str
    volume_lookback_sessions: int = 20   # trailing same-slot window
    atr_period: int = 14                 # prior-session ATR

    @classmethod
    def parse(cls, raw: dict, path: str = "signal") -> SignalConfig:
        _check_keys(raw, cls, path)
        if "entry_time" not in raw:
            raise ConfigError(f"{path}.entry_time: required, e.g. '09:35'")
        try:
            entry = parse_local_time(str(raw["entry_time"]))
        except ValueError as exc:
            raise ConfigError(f"{path}.entry_time: {exc}") from exc
        return cls(
            volume_ratio_min=_num(raw, "volume_ratio_min", path, lo=0.0,
                                  lo_open=True, default=1.0),
            candle=_choice(raw, "candle", path, CANDLE_TYPES, "any"),
            doji_max_body_ratio=_num(raw, "doji_max_body_ratio", path,
                                     lo=0.0, hi=1.0, hi_open=True, default=0.10),
            gap_required=_flag(raw, "gap_required", path, True),
            entry_time=entry,
            entry_price=_choice(raw, "entry_price", path, ENTRY_PRICES, "open"),
            volume_lookback_sessions=int(_num(
                raw, "volume_lookback_sessions", path, lo=2, default=20)),
            atr_period=int(_num(raw, "atr_period", path, lo=2, default=14)),
        )


@dataclass(frozen=True)
class StopConfig:
    enabled: bool = False
    type: str = "atr"
    multiple: float = 1.0

    @classmethod
    def parse(cls, raw: dict, path: str = "exit.stop") -> StopConfig:
        _check_keys(raw, cls, path)
        return cls(
            enabled=_flag(raw, "enabled", path, False),
            type=_choice(raw, "type", path, STOP_TYPES, "atr"),
            multiple=_num(raw, "multiple", path, lo=0.0, lo_open=True, default=1.0),
        )


@dataclass(frozen=True)
class ExitConfig:
    type: str = "time"
    hold_minutes: int = 60
    stop: StopConfig = StopConfig()

    @classmethod
    def parse(cls, raw: dict, path: str = "exit") -> ExitConfig:
        _check_keys(raw, cls, path)
        return cls(
            type=_choice(raw, "type", path, EXIT_TYPES, "time"),
            hold_minutes=int(_num(raw, "hold_minutes", path, lo=1, default=60)),
            stop=StopConfig.parse(raw.get("stop", {}) or {}, f"{path}.stop"),
        )


@dataclass(frozen=True)
class SizingConfig:
    method: str = "fixed_risk_pct"
    risk_pct: float = 0.005
    max_pct_equity_per_trade: float = 0.05
    risk_unit: str = "atr"

    @classmethod
    def parse(cls, raw: dict, path: str = "sizing") -> SizingConfig:
        _check_keys(raw, cls, path)
        return cls(
            method=_choice(raw, "method", path, SIZING_METHODS, "fixed_risk_pct"),
            risk_pct=_num(raw, "risk_pct", path, lo=0.0, hi=1.0,
                          lo_open=True, default=0.005),
            max_pct_equity_per_trade=_num(raw, "max_pct_equity_per_trade", path,
                                          lo=0.0, hi=1.0, lo_open=True,
                                          default=0.05),
            risk_unit=_choice(raw, "risk_unit", path, RISK_UNITS, "atr"),
        )


@dataclass(frozen=True)
class PortfolioConfig:
    max_concurrent_positions: int = 5
    starting_capital: float = 1_000_000.0
    max_gross_exposure: float = 1.0      # 1.0 == no leverage

    @classmethod
    def parse(cls, raw: dict, path: str = "portfolio") -> PortfolioConfig:
        _check_keys(raw, cls, path)
        return cls(
            max_concurrent_positions=int(_num(
                raw, "max_concurrent_positions", path, lo=1, default=5)),
            starting_capital=_num(raw, "starting_capital", path, lo=0.0,
                                  lo_open=True, default=1_000_000.0),
            max_gross_exposure=_num(raw, "max_gross_exposure", path, lo=0.0,
                                    lo_open=True, default=1.0),
        )


@dataclass(frozen=True)
class CostConfig:
    round_trip_bps: float = 0.0

    @classmethod
    def parse(cls, raw: dict, path: str = "costs") -> CostConfig:
        _check_keys(raw, cls, path)
        return cls(round_trip_bps=_num(raw, "round_trip_bps", path,
                                       lo=0.0, default=0.0))


@dataclass(frozen=True)
class DataConfig:
    """Optional. Where the bars live and what window to run over."""
    dir: str = "data"
    bar_size: str = "1m"
    start: str | None = None
    end: str | None = None
    validate: bool = True

    @classmethod
    def parse(cls, raw: dict, path: str = "data") -> DataConfig:
        _check_keys(raw, cls, path)
        return cls(
            dir=str(raw.get("dir", "data")),
            bar_size=str(raw.get("bar_size", "1m")),
            start=None if raw.get("start") is None else str(raw["start"]),
            end=None if raw.get("end") is None else str(raw["end"]),
            validate=_flag(raw, "validate", path, True),
        )


@dataclass(frozen=True)
class BacktestConfig:
    strategy: StrategyMeta
    universe: UniverseConfig
    signal: SignalConfig
    exit: ExitConfig
    direction: str
    sizing: SizingConfig
    portfolio: PortfolioConfig
    costs: CostConfig
    data: DataConfig
    source_path: str | None = None

    TOP_LEVEL = {"strategy", "universe", "signal", "exit", "direction",
                 "sizing", "portfolio", "costs", "data"}

    @classmethod
    def from_yaml(cls, path: Path | str) -> BacktestConfig:
        path = Path(path)
        if not path.is_file():
            raise ConfigError(f"config not found: {path}")
        with path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        if not isinstance(raw, dict):
            raise ConfigError(f"{path}: top level must be a mapping")
        cfg = cls.from_dict(raw)
        return cls(**{**cfg.__dict__, "source_path": str(path)})

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> BacktestConfig:
        unknown = set(raw) - cls.TOP_LEVEL
        if unknown:
            raise ConfigError(f"unknown top-level section(s) {sorted(unknown)}. "
                              f"Valid sections are {sorted(cls.TOP_LEVEL)}.")
        if "strategy" not in raw:
            raise ConfigError("strategy: section is required")

        direction = raw.get("direction", "signed")
        if direction not in DIRECTIONS:
            raise ConfigError(f"direction: {direction!r} is not one of "
                              f"{sorted(DIRECTIONS)}")

        cfg = cls(
            strategy=StrategyMeta.parse(raw["strategy"] or {}),
            universe=UniverseConfig.parse(raw.get("universe", {}) or {}),
            signal=SignalConfig.parse(raw.get("signal", {}) or {}),
            exit=ExitConfig.parse(raw.get("exit", {}) or {}),
            direction=direction,
            sizing=SizingConfig.parse(raw.get("sizing", {}) or {}),
            portfolio=PortfolioConfig.parse(raw.get("portfolio", {}) or {}),
            costs=CostConfig.parse(raw.get("costs", {}) or {}),
            data=DataConfig.parse(raw.get("data", {}) or {}),
        )
        cfg._check_coherence()
        return cfg

    def _check_coherence(self) -> None:
        """Cross-section checks that no single parser can see."""
        if self.signal.entry_price == "close":
            raise ConfigError(
                "signal.entry_price='close' is not implementable under "
                "point-in-time rules. The ENTRY bar's close does not exist at "
                "the decision instant, and the SIGNAL candle's close is a "
                "print that has already happened -- you cannot trade at it. "
                "Use 'open', which is the next print after the decision.")
        if self.signal.candle == "continuation" and not self.signal.gap_required:
            raise ConfigError(
                "signal: candle='continuation' is defined relative to the gap "
                "direction, so gap_required cannot be false."
            )
        if self.exit.type == "time" and self.exit.hold_minutes > 390:
            raise ConfigError(
                f"exit.hold_minutes={self.exit.hold_minutes} exceeds one "
                f"regular session (390 minutes). Multi-session holds need an "
                f"exit type that carries positions overnight."
            )
        if self.sizing.method == "fixed_notional" and self.portfolio.max_concurrent_positions < 1:
            raise ConfigError("portfolio.max_concurrent_positions must be >= 1 "
                              "for fixed_notional sizing")

    def warnings(self) -> list[str]:
        """Legal but easily-misread combinations, for the runner to print."""
        out: list[str] = []
        if self.sizing.method == "fixed_risk_pct" and not self.exit.stop.enabled:
            out.append(
                f"sizing.risk_pct={self.sizing.risk_pct:.3%} divides by "
                f"{self.sizing.risk_unit.upper()} as a risk PROXY, but "
                f"exit.stop.enabled is false. Nothing bounds the loss at one "
                f"unit, so a trade can lose several times the nominal risk "
                f"budget. This is a valid configuration, not a risk limit."
            )
        if self.costs.round_trip_bps == 0.0:
            out.append("costs.round_trip_bps is 0. Results will be gross of "
                       "all transaction costs.")
        if self.sizing.method == "fixed_notional":
            slot = 1.0 / self.portfolio.max_concurrent_positions
            if slot > self.sizing.max_pct_equity_per_trade:
                out.append(
                    f"sizing.method='fixed_notional' wants "
                    f"{slot:.1%} per slot but max_pct_equity_per_trade caps a "
                    f"position at {self.sizing.max_pct_equity_per_trade:.1%}, "
                    f"so the cap binds and gross exposure will only reach "
                    f"{self.portfolio.max_concurrent_positions * self.sizing.max_pct_equity_per_trade:.0%}, "
                    f"not 100%.")
        if self.portfolio.max_gross_exposure > 1.0:
            out.append(f"portfolio.max_gross_exposure="
                       f"{self.portfolio.max_gross_exposure:.2f} permits "
                       f"leverage; margin and borrow costs are not modelled.")
        return out

    def describe(self) -> str:
        """Flat, readable dump for the run header and results provenance."""
        lines: list[str] = []

        def walk(obj: Any, prefix: str) -> None:
            for f in fields(obj):
                v = getattr(obj, f.name)
                key = f"{prefix}{f.name}"
                if is_dataclass(v):
                    walk(v, f"{key}.")
                else:
                    lines.append(f"{key}: {v}")

        walk(self, "")
        return "\n".join(lines)
