"""
portfolio.py -- capital, sizing, concurrency and execution.

Signals say "there is a trade here". This module answers "how much, was
it affordable, and what did it actually fill at". Those are separate
questions and keeping them separate is what stops a sizing bug from
looking like an edge.

SIX DECISIONS THAT MOVE THE RESULT, EACH MADE EXPLICITLY

1 WHICH SIGNALS GET TAKEN when a session produces more than
  `max_concurrent_positions`. Selection is by a configurable EX-ANTE key
  -- volume ratio by default -- with a deterministic ticker tiebreak.
  Never by realised P&L, never by anything unknown at the decision
  instant. `SelectionRule.RANDOM` exists so the contribution of the
  ranking itself can be measured rather than assumed.

2 WHAT THE RISK DENOMINATOR IS. Fixed-fractional sizing divides the risk
  budget by the distance to the stop: `stop.multiple x ATR` when a stop
  is enabled. With the stop DISABLED there is no such distance, so 1 ATR
  is used as a proxy and the position is genuinely unbounded -- the trade
  can and does lose several times its nominal risk. Config.warnings()
  says so on every run.

3 THE STOP CAN FIRE INSIDE THE ENTRY BAR. Entry is the open of the entry
  bar; that bar's low (long) or high (short) comes after the open and can
  reach the stop. Excluding the entry bar would quietly rescue every
  trade that was stopped in its first minute. It is included.

4 STOP FILLS ARE THE WORSE OF THE INTENDED LEVEL AND THE BAR OPEN. If a
  bar opens beyond the stop, the level was unobtainable and the open is
  the honest fill. `fill = min(stop, bar.open)` long, `max(...)` short.
  No bar is ever assumed to fill at a price better than it traded.

5 TIME EXITS FILL AT THE OPEN OF THE EXIT BAR, symmetric with entry. If
  that bar is missing -- a real occurrence in thin names -- the last
  close at or before the planned exit is used and the trade is flagged
  `exit_reason="time_stale"` rather than silently dropped or extended.

6 COSTS ARE CHARGED ONCE, as a round trip, on entry notional. The config
  field is named `round_trip_bps`; charging it on both legs would double
  it.

WHAT IS STILL NOT MODELLED, and would all reduce returns: borrow cost on
shorts, spread widening by name and volatility, market impact, partial
fills, and any capacity limit against the name's actual volume in the
hour traded.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass, field
from enum import Enum

import numpy as np
import pandas as pd

from engine.config import BacktestConfig
from engine.strategy_base import Signal


class SelectionRule(str, Enum):
    """How to choose when signals outnumber slots. Ex-ante only."""
    VOLUME_RATIO = "volume_ratio"    # strongest volume surge first
    GAP_ATR = "gap_atr"              # largest gap in ATR first
    TICKER = "ticker"                # alphabetical, i.e. deliberately naive
    RANDOM = "random"                # to price the ranking's contribution


@dataclass(frozen=True)
class Trade:
    trade_id: str
    ticker: str
    session: dt.date
    direction: int
    entry_ts: pd.Timestamp
    entry_price: float
    exit_ts: pd.Timestamp
    exit_price: float
    exit_reason: str                 # "time" | "stop" | "time_stale"
    shares: float
    notional: float
    weight: float                    # notional / equity at entry
    atr: float
    stop_price: float
    gross_pnl: float
    cost: float
    net_pnl: float
    ret_bps: float                   # net, on entry notional
    ret_atr: float                   # gross price move in ATR units
    mae_atr: float
    mfe_atr: float
    bars_held: int
    equity_before: float
    equity_after: float
    scaled: bool                     # gross cap forced a pro-rata reduction
    features: dict = field(default_factory=dict)


# ----------------------------------------------------------------- execution

def simulate_exit(sig: Signal, bars: pd.DataFrame, stop_price: float
                  ) -> tuple[pd.Timestamp, float, str, int, float, float]:
    """Walk the holding window and return the realised exit.

    Returns (exit_ts, exit_price, reason, bars_held, mae_atr, mfe_atr).

    The window runs from the entry bar INCLUSIVE to the planned exit bar
    INCLUSIVE. Including the entry bar matters: its low/high occur after
    the open we filled at, so a first-minute stop is real.
    """
    window = bars[(bars.index >= sig.entry_ts)
                  & (bars.index <= sig.planned_exit_ts)]
    if window.empty:
        raise ValueError(f"{sig.ticker} {sig.session}: no bars in the holding "
                         f"window {sig.entry_ts}..{sig.planned_exit_ts}")

    d = sig.direction
    # Excursions are measured against the fill, in ATR units, over the
    # window actually held -- truncated at the stop rather than run to
    # the planned exit, so a stop is not credited with moves it avoided.
    mae = 0.0
    mfe = 0.0
    hit_at: pd.Timestamp | None = None
    fill = float("nan")

    for ts, bar in window.iterrows():
        adverse = bar["low"] if d > 0 else bar["high"]
        favour = bar["high"] if d > 0 else bar["low"]
        mae = min(mae, d * (adverse - sig.entry_price) / sig.risk_unit)
        mfe = max(mfe, d * (favour - sig.entry_price) / sig.risk_unit)

        if np.isfinite(stop_price):
            breached = (bar["low"] <= stop_price) if d > 0 \
                else (bar["high"] >= stop_price)
            if breached:
                # The worse of the intended level and this bar's open.
                fill = min(stop_price, bar["open"]) if d > 0 \
                    else max(stop_price, bar["open"])
                hit_at = ts
                break

    if hit_at is not None:
        held = int(window.index.get_indexer([hit_at])[0]) + 1
        # Re-measure excursions over the truncated window only.
        trunc = window[window.index <= hit_at]
        mae, mfe = _excursions(trunc, sig)
        return hit_at, float(fill), "stop", held, mae, mfe

    # Time exit: the open of the planned exit bar, symmetric with entry.
    at = window[window.index == sig.planned_exit_ts]
    if len(at):
        return (sig.planned_exit_ts, float(at["open"].iloc[0]), "time",
                len(window), mae, mfe)

    # That bar never printed. Use the last close we actually have and say so.
    last_ts = window.index[-1]
    return (last_ts, float(window["close"].iloc[-1]), "time_stale",
            len(window), mae, mfe)


def _excursions(window: pd.DataFrame, sig: Signal) -> tuple[float, float]:
    d = sig.direction
    adverse = window["low"] if d > 0 else window["high"]
    favour = window["high"] if d > 0 else window["low"]
    mae = float((d * (adverse - sig.entry_price) / sig.risk_unit).min())
    mfe = float((d * (favour - sig.entry_price) / sig.risk_unit).max())
    return min(0.0, mae), max(0.0, mfe)


def stop_price_for(sig: Signal, cfg: BacktestConfig) -> float:
    if not cfg.exit.stop.enabled:
        return float("nan")
    dist = cfg.exit.stop.multiple * sig.risk_unit
    return sig.entry_price - sig.direction * dist


def risk_per_share(sig: Signal, cfg: BacktestConfig) -> float:
    """Distance to the stop, or 1 ATR as a proxy when there is no stop."""
    mult = cfg.exit.stop.multiple if cfg.exit.stop.enabled else 1.0
    return mult * sig.risk_unit


# ----------------------------------------------------------------- portfolio

class Portfolio:
    """Day-by-day capital simulation for intraday signals.

    Positions open and close inside one session, so equity compounds
    daily and there is no overnight carry to model. A strategy that held
    positions across sessions would need a different loop; the config
    refuses `hold_minutes` beyond one session precisely so this
    assumption cannot be violated silently.
    """

    def __init__(self, config: BacktestConfig,
                 selection: SelectionRule = SelectionRule.VOLUME_RATIO,
                 seed: int = 7) -> None:
        self.cfg = config
        self.selection = SelectionRule(selection)
        self.rng = np.random.default_rng(seed)

    # -- selection -----------------------------------------------------

    def _rank(self, day: pd.DataFrame) -> pd.DataFrame:
        """Order a session's signals by the ex-ante key, best first."""
        r = self.selection
        if r is SelectionRule.RANDOM:
            return day.iloc[self.rng.permutation(len(day))]
        if r is SelectionRule.TICKER:
            return day.sort_values("ticker", kind="stable")
        key = r.value
        if key not in day.columns:
            raise KeyError(
                f"selection rule {r.value!r} needs a '{key}' column on the "
                f"signal table; the strategy must emit it as a feature")
        # Deterministic tiebreak, so two runs cannot disagree.
        return day.sort_values([key, "ticker"], ascending=[False, True],
                               kind="stable")

    # -- sizing --------------------------------------------------------

    def _size(self, sigs: list[Signal], equity: float) -> np.ndarray:
        """Notional per signal, before the gross-exposure cap."""
        c = self.cfg
        n = len(sigs)
        if c.sizing.method == "fixed_risk_pct":
            budget = c.sizing.risk_pct * equity
            per_share = np.array([risk_per_share(s, c) for s in sigs])
            shares = budget / per_share
            notional = shares * np.array([s.entry_price for s in sigs])
        else:  # fixed_notional
            notional = np.full(n, equity / c.portfolio.max_concurrent_positions)

        cap = c.sizing.max_pct_equity_per_trade * equity
        return np.minimum(notional, cap)

    # -- the loop ------------------------------------------------------

    def run(self, signals: list[Signal], frames: dict[str, pd.DataFrame],
            calendar: pd.DatetimeIndex | None = None
            ) -> tuple[pd.DataFrame, pd.Series]:
        """Simulate. Returns (trade log, daily equity series)."""
        c = self.cfg
        equity = c.portfolio.starting_capital

        table = _signals_to_frame(signals)
        by_session: dict[dt.date, pd.DataFrame] = (
            {s: g for s, g in table.groupby("session")} if len(table) else {})

        # A DatetimeIndex yields Timestamps while Signal.session is a
        # datetime.date. Normalise, or every lookup silently misses and
        # the run books no trades at all.
        sessions = (_to_dates(calendar) if calendar is not None
                    else _sessions_from(frames))

        rows: list[dict] = []
        equity_curve: list[float] = []
        seq = 0

        for session in sessions:
            day = by_session.get(session)
            if day is not None and len(day):
                chosen = self._rank(day).head(
                    c.portfolio.max_concurrent_positions)
                sigs = [row["_signal"] for _, row in chosen.iterrows()]

                notional = self._size(sigs, equity)
                gross = notional.sum()
                limit = c.portfolio.max_gross_exposure * equity
                scaled = gross > limit
                if scaled and gross > 0:
                    notional = notional * (limit / gross)

                day_pnl = 0.0
                for sig, nt in zip(sigs, notional):
                    bars = frames[sig.ticker]
                    stop = stop_price_for(sig, c)
                    (x_ts, x_px, reason, held,
                     mae, mfe) = simulate_exit(sig, bars, stop)

                    shares = nt / sig.entry_price
                    move = sig.direction * (x_px - sig.entry_price)
                    gross_pnl = shares * move
                    cost = nt * c.costs.round_trip_bps / 1e4
                    net = gross_pnl - cost
                    day_pnl += net
                    seq += 1

                    rows.append(asdict(Trade(
                        trade_id=f"T{seq:05d}", ticker=sig.ticker,
                        session=sig.session, direction=sig.direction,
                        entry_ts=sig.entry_ts, entry_price=sig.entry_price,
                        exit_ts=x_ts, exit_price=x_px, exit_reason=reason,
                        shares=shares, notional=float(nt),
                        weight=float(nt) / equity, atr=sig.risk_unit,
                        stop_price=stop, gross_pnl=gross_pnl, cost=cost,
                        net_pnl=net,
                        ret_bps=net / nt * 1e4 if nt else float("nan"),
                        ret_atr=move / sig.risk_unit,
                        mae_atr=mae, mfe_atr=mfe, bars_held=held,
                        equity_before=equity, equity_after=float("nan"),
                        scaled=bool(scaled), features=dict(sig.features))))

                equity += day_pnl
                for r in rows[-len(sigs):]:
                    r["equity_after"] = equity

            equity_curve.append(equity)

        log = pd.DataFrame(rows)
        if len(log):
            feats = pd.json_normalize(log.pop("features")).add_prefix("f_")
            log = pd.concat([log.reset_index(drop=True), feats], axis=1)
        curve = pd.Series(equity_curve,
                          index=pd.DatetimeIndex(sessions, name="session"),
                          name="equity")
        return log, curve


def _signals_to_frame(signals: list[Signal]) -> pd.DataFrame:
    if not signals:
        return pd.DataFrame(columns=["ticker", "session", "_signal"])
    rows = []
    for s in signals:
        rows.append({"ticker": s.ticker, "session": s.session,
                     "_signal": s, **s.features})
    return pd.DataFrame(rows)


def _to_dates(calendar) -> list[dt.date]:
    """Coerce any date-like sequence to sorted datetime.date."""
    out = []
    for v in calendar:
        out.append(v.date() if isinstance(v, pd.Timestamp) else v)
    return sorted(out)


def _sessions_from(frames: dict[str, pd.DataFrame]) -> list[dt.date]:
    """Union of session dates across every ticker, ascending.

    Using the union rather than only the days that traded means idle
    sessions appear in the equity curve as flat, which is what makes the
    volatility and drawdown of a sparsely-deployed strategy honest.
    """
    out: set = set()
    for df in frames.values():
        out.update(df["session_date"].unique().tolist())
    return sorted(out)
