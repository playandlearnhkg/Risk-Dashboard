"""
metrics.py -- performance, distribution and tail statistics.

Consumes what `Portfolio.run` already produces -- a trade log and a daily
equity curve -- and computes nothing from prices directly. That keeps
this module trivially point-in-time safe: it can only see trades that
already happened.

FOUR DECISIONS WORTH KNOWING

1 A DATE FILTER REBASES THE EQUITY CURVE. Restricting to 2022-2025 and
  then annualising over the original eleven years would charge the
  subset for the flat years before its first trade. `filter_period`
  therefore rebuilds equity from the filtered trades starting at the
  original capital, so CAGR is over the subset's OWN window. This is not
  cosmetic: it was the difference between 4.0% and 11.3% in the research.

2 REPRICING AT A DIFFERENT COST IS EXACT PER TRADE AND APPROXIMATE ON
  THE CURVE. Cost does not change which trades fire or when they exit,
  so per-trade statistics re-cost exactly. It DOES change equity, and
  fixed-fractional sizing reads equity, so the true path would size
  later trades differently. `reprice` holds the original notionals and
  says so; for an exact answer, re-run the Portfolio at the new cost.
  The robustness suite does the latter.

3 SHARPE USES rf = 0 AND IS COMPUTED ON THE DAILY EQUITY SERIES,
  including the days the strategy holds nothing. For a strategy deployed
  a few percent of the time that flatters the ratio, because idle days
  contribute zero variance. `deployed_vol` is reported alongside so the
  distinction is visible rather than buried.

4 SKEW AND KURTOSIS ARE REPORTED BOTH RAW AND WINSORISED at 1%/99%. One
  outlier can move raw kurtosis by an order of magnitude -- in the
  research a single squeeze took ordinary-session kurtosis from 56 to
  23,504 -- so the winsorised pair is the one to read, with the raw pair
  kept as the flag that an outlier exists.

THE STANDARD METRIC SET

Every field below is computed exactly once, here, and reused by the
validation report, the gate and the robustness suite -- none of them
recomputes a Sharpe or an expectancy independently, so there is only one
place these numbers can disagree with each other.

  Core performance    trade_stats()        n_trades, win_rate, avg_win,
                                            avg_loss, payoff_ratio,
                                            profit_factor, expectancy,
                                            expectancy_bps, expectancy_atr
  Risk & distribution  equity_stats()       ann_vol, max_dd, sharpe, calmar
                       distribution_stats() std_bps, skew/exkurt (raw +
                                            winsorised), p10/p25/p75/p90,
                                            pct_loss_gt_0_5atr,
                                            pct_loss_gt_1atr,
                                            pct_gain_gt_1atr,
                                            avg_large_loss_bps,
                                            mean_mae_atr, mean_mfe_atr
  Time & stability     evaluate()'s         by_year (return, max_dd,
                       by_year / by_side    win_rate, avg trade,
                                            pct_loss_gt_1atr) and by_side
                                            (long vs short, each stat above)
  Practical / cost     robustness.py        cost_stress, stop_comparison

`expectancy_atr` is the mean of `ret_atr`, which -- like the tail counts
above it -- is GROSS of cost. Cost expressed in ATR units is a few
thousandths and adding it would claim a precision the data does not
have; `expectancy_bps`, by contrast, IS net, because `pnl_bps` already
has cost subtracted. Reading one as net and the other as gross is a
feature of this data, not an inconsistency to fix.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

TRADING_DAYS = 252
WINSOR = (0.01, 0.99)

#: The trade-log columns this module guarantees downstream consumers.
STANDARD_COLUMNS = [
    "trade_id", "ticker", "date", "side", "entry_time", "exit_time",
    "entry_price", "exit_price", "pnl", "pnl_bps", "mae_atr", "mfe_atr",
    "gap_atr", "volume_ratio",
]


# ------------------------------------------------------------------ helpers

def standard_trade_log(trades: pd.DataFrame) -> pd.DataFrame:
    """Portfolio's trade log in the agreed column names and order.

    Extra columns are kept after the standard ones rather than dropped:
    the exit reason and the ATR are needed by the capacity suite, and
    silently discarding them here would make this function lossy.
    """
    if trades.empty:
        return pd.DataFrame(columns=STANDARD_COLUMNS)
    t = trades.copy()
    out = pd.DataFrame({
        "trade_id": t["trade_id"],
        "ticker": t["ticker"],
        "date": t["session"],
        "side": np.where(t["direction"] > 0, "LONG", "SHORT"),
        "entry_time": t["entry_ts"],
        "exit_time": t["exit_ts"],
        "entry_price": t["entry_price"],
        "exit_price": t["exit_price"],
        "pnl": t["net_pnl"],
        "pnl_bps": t["ret_bps"],
        "mae_atr": t["mae_atr"],
        "mfe_atr": t["mfe_atr"],
        "gap_atr": t.get("f_gap_atr", pd.Series(np.nan, index=t.index)),
        "volume_ratio": t.get("f_volume_ratio", pd.Series(np.nan, index=t.index)),
    })
    extra = [c for c in t.columns if c not in
             ("trade_id", "ticker", "session", "direction", "entry_ts",
              "exit_ts", "entry_price", "exit_price", "net_pnl", "ret_bps",
              "mae_atr", "mfe_atr", "f_gap_atr", "f_volume_ratio")]
    return pd.concat([out, t[extra]], axis=1)


def drawdown(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1.0


def _winsor(x: pd.Series) -> pd.Series:
    if len(x) < 10:
        return x
    lo, hi = x.quantile(list(WINSOR))
    return x.clip(lo, hi)


def rebuild_equity(trades: pd.DataFrame, capital: float,
                   calendar: pd.DatetimeIndex | None = None) -> pd.Series:
    """Daily equity from a trade log, compounding by session.

    Used whenever the trade set changes -- a period filter, a long-only
    subset, a re-cost -- because the original curve no longer describes
    the trades in hand.
    """
    if trades.empty:
        idx = calendar if calendar is not None else pd.DatetimeIndex([])
        return pd.Series(capital, index=idx, name="equity", dtype=float)
    by_day = trades.groupby("date")["pnl"].sum().sort_index()
    days = (sorted({*by_day.index, *(_to_dates(calendar) if calendar is not None else [])})
            if calendar is not None else list(by_day.index))
    eq, out = capital, []
    for d in days:
        eq += float(by_day.get(d, 0.0))
        out.append(eq)
    return pd.Series(out, index=pd.DatetimeIndex(days, name="date"),
                     name="equity", dtype=float)


def _to_dates(cal) -> list[dt.date]:
    return [v.date() if isinstance(v, pd.Timestamp) else v for v in cal]


# ------------------------------------------------------------------- blocks

def equity_stats(equity: pd.Series, capital: float | None = None) -> dict:
    """Return, risk and drawdown statistics from the equity curve."""
    if equity.empty or len(equity) < 2:
        return {k: np.nan for k in
                ("total_return", "cagr", "ann_vol", "sharpe", "max_dd",
                 "calmar", "worst_day", "best_day", "n_days")}
    base = capital if capital is not None else float(equity.iloc[0])
    r = equity.pct_change().fillna(equity.iloc[0] / base - 1.0)
    dd = drawdown(equity)
    yrs = len(equity) / TRADING_DAYS
    total = equity.iloc[-1] / base - 1.0
    cagr = (equity.iloc[-1] / base) ** (1 / yrs) - 1.0 if yrs > 0 else np.nan
    vol = r.std() * np.sqrt(TRADING_DAYS)
    mdd = dd.min()
    live = r[r != 0]
    return {
        "total_return": float(total), "cagr": float(cagr),
        "ann_vol": float(vol),
        "sharpe": float(cagr / vol) if vol else np.nan,
        "max_dd": float(mdd),
        "calmar": float(cagr / abs(mdd)) if mdd else np.nan,
        "worst_day": float(r.min()), "best_day": float(r.max()),
        "n_days": int(len(equity)),
        # Volatility on days capital was actually at work. The headline
        # Sharpe is computed on all days, most of which are zeros.
        "deployed_vol": float(live.std() * np.sqrt(TRADING_DAYS)) if len(live) > 1 else np.nan,
        "pct_days_active": float((r != 0).mean()),
    }


def trade_stats(trades: pd.DataFrame) -> dict:
    """Win rate, payoff and profit factor on realised, after-cost P&L."""
    if trades.empty:
        return {k: np.nan for k in
                ("n_trades", "win_rate", "avg_win", "avg_loss", "payoff_ratio",
                 "profit_factor", "expectancy", "expectancy_bps",
                 "expectancy_atr")}
    p = trades["pnl"]
    wins, losses = p[p > 0], p[p < 0]
    aw = float(wins.mean()) if len(wins) else np.nan
    al = float(-losses.mean()) if len(losses) else np.nan
    gl = float(-losses.sum())
    # GROSS of cost, unlike expectancy_bps -- see the module docstring.
    ratr = trades.get("ret_atr")
    return {
        "n_trades": int(len(trades)),
        "win_rate": float((p > 0).mean()),
        "avg_win": aw, "avg_loss": al,
        "payoff_ratio": (aw / al) if al else np.nan,
        "profit_factor": (float(wins.sum()) / gl) if gl else np.nan,
        "expectancy": float(p.mean()),
        "expectancy_bps": float(trades["pnl_bps"].mean()),
        "expectancy_atr": float(ratr.mean()) if ratr is not None else np.nan,
    }


def distribution_stats(trades: pd.DataFrame) -> dict:
    """Shape and tails, in bps and in ATR units."""
    if trades.empty:
        return {}
    b = trades["pnl_bps"]
    bw = _winsor(b)
    q = b.quantile([0.10, 0.25, 0.50, 0.75, 0.90])

    # Tail counts use the ATR-denominated return, which is the risk unit
    # the strategy is sized in. `ret_atr` is gross of cost; the cost in
    # ATR is tiny and adding it would imply a precision we do not have.
    ratr = trades.get("ret_atr")
    if ratr is None:
        ratr = pd.Series(np.nan, index=trades.index)
    return {
        "mean_bps": float(b.mean()), "median_bps": float(q.loc[0.50]),
        "std_bps": float(b.std()),
        "p10": float(q.loc[0.10]), "p25": float(q.loc[0.25]),
        "p75": float(q.loc[0.75]), "p90": float(q.loc[0.90]),
        "skew_raw": float(b.skew()), "exkurt_raw": float(b.kurt()),
        "skew_wins": float(bw.skew()), "exkurt_wins": float(bw.kurt()),
        "pct_loss_gt_0_5atr": float((ratr < -0.5).mean()),
        "pct_loss_gt_1atr": float((ratr < -1.0).mean()),
        "pct_gain_gt_1atr": float((ratr > 1.0).mean()),
        "avg_large_loss_bps": float(b[ratr < -1.0].mean())
        if (ratr < -1.0).any() else np.nan,
        "mean_mae_atr": float(trades["mae_atr"].mean()),
        "mean_mfe_atr": float(trades["mfe_atr"].mean()),
    }


# ------------------------------------------------------------------- report

@dataclass(frozen=True)
class Metrics:
    """Everything computed for one trade set. Frozen, so it is a record."""
    label: str
    capital: float
    overall: dict
    distribution: dict
    by_year: pd.DataFrame
    by_side: pd.DataFrame
    trades: pd.DataFrame
    equity: pd.Series
    drawdown: pd.Series
    meta: dict = field(default_factory=dict)

    def to_frames(self) -> dict[str, pd.DataFrame]:
        return {
            "overall": pd.DataFrame([self.overall]),
            "distribution": pd.DataFrame([self.distribution]),
            "by_year": self.by_year,
            "by_side": self.by_side,
            "trades": self.trades,
            "equity": self.equity.to_frame().assign(drawdown=self.drawdown),
        }

    def write(self, out_dir: Path | str, prefix: str = "") -> list[Path]:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        written = []
        for name, frame in self.to_frames().items():
            p = out_dir / f"{prefix}{name}.csv"
            frame.to_csv(p, index=(name == "equity"))
            written.append(p)
        return written

    def summary(self) -> str:
        o, d = self.overall, self.distribution

        def pct(k, nd=2):
            v = o.get(k, d.get(k))
            return "n/a" if v is None or pd.isna(v) else f"{v * 100:,.{nd}f}%"

        def num(k, nd=2):
            v = o.get(k, d.get(k))
            return "n/a" if v is None or pd.isna(v) else f"{v:,.{nd}f}"

        L = [f"{'=' * 64}", f"{self.label}", f"{'=' * 64}",
             f"period            {self.meta.get('start', '?')} .. "
             f"{self.meta.get('end', '?')}   ({o.get('n_days', 0):,} sessions)",
             f"capital           {self.capital:,.0f} -> "
             f"{self.equity.iloc[-1] if len(self.equity) else self.capital:,.0f}",
             "",
             "PERFORMANCE",
             f"  total return    {pct('total_return')}",
             f"  CAGR            {pct('cagr')}",
             f"  ann. volatility {pct('ann_vol')}"
             f"   (deployed days only: {pct('deployed_vol')})",
             f"  Sharpe (rf=0)   {num('sharpe')}",
             f"  max drawdown    {pct('max_dd')}",
             f"  Calmar          {num('calmar')}",
             f"  days active     {pct('pct_days_active')}",
             "",
             "TRADES",
             f"  n               {o.get('n_trades', 0):,}",
             f"  win rate        {pct('win_rate')}",
             f"  avg win / loss  {num('avg_win')} / {num('avg_loss')}",
             f"  payoff ratio    {num('payoff_ratio')}",
             f"  profit factor   {num('profit_factor')}",
             f"  expectancy      {num('expectancy')}  ({num('expectancy_bps')} bps, "
             f"{num('expectancy_atr', 3)} ATR gross)",
             "",
             "DISTRIBUTION (bps per trade)",
             f"  p10 / p25       {num('p10')} / {num('p25')}",
             f"  median          {num('median_bps')}",
             f"  p75 / p90       {num('p75')} / {num('p90')}",
             f"  skew   raw/wins {num('skew_raw', 3)} / {num('skew_wins', 3)}",
             f"  exkurt raw/wins {num('exkurt_raw', 3)} / {num('exkurt_wins', 3)}",
             "",
             "TAILS",
             f"  losing  > 0.5 ATR  {pct('pct_loss_gt_0_5atr')}",
             f"  losing  > 1.0 ATR  {pct('pct_loss_gt_1atr')}",
             f"  gaining > 1.0 ATR  {pct('pct_gain_gt_1atr')}",
             f"  avg large loss    {num('avg_large_loss_bps')} bps",
             f"  mean MAE / MFE    {num('mean_mae_atr', 3)} / "
             f"{num('mean_mfe_atr', 3)} ATR"]

        if len(self.by_side):
            L += ["", "LONG vs SHORT", _fmt(self.by_side)]
        if len(self.by_year):
            L += ["", "YEAR BY YEAR", _fmt(self.by_year)]
        return "\n".join(L)


def _fmt(df: pd.DataFrame) -> str:
    x = df.copy()
    for c in x.columns:
        if pd.api.types.is_float_dtype(x[c]):
            x[c] = x[c].map(lambda v: "" if pd.isna(v) else f"{v:,.3f}")
    return x.to_string(index=False)


# --------------------------------------------------------------- public API

def filter_period(trades: pd.DataFrame, capital: float,
                  start: str | dt.date | None = None,
                  end: str | dt.date | None = None) -> pd.DataFrame:
    """Restrict a trade log to a date window. Equity is rebuilt by caller."""
    if trades.empty:
        return trades
    d = pd.to_datetime(pd.Series(list(trades["date"]))).dt.date.to_numpy()
    keep = np.ones(len(trades), dtype=bool)
    if start is not None:
        keep &= d >= pd.Timestamp(start).date()
    if end is not None:
        keep &= d <= pd.Timestamp(end).date()
    return trades[keep].copy()


def reprice(trades: pd.DataFrame, cost_bps: float) -> pd.DataFrame:
    """Re-cost a trade log at a different round-trip rate.

    EXACT for per-trade statistics -- cost changes neither which trades
    fire nor when they exit. APPROXIMATE for the equity path, because
    fixed-fractional sizing reads equity and the true path would have
    sized later trades differently. Re-run the Portfolio for an exact
    answer; this exists for fast sweeps.
    """
    if trades.empty:
        return trades
    t = trades.copy()
    if "notional" not in t or "gross_pnl" not in t:
        raise KeyError("reprice needs 'notional' and 'gross_pnl'; pass the "
                       "standard_trade_log built from Portfolio output")
    t["cost"] = t["notional"] * cost_bps / 1e4
    t["pnl"] = t["gross_pnl"] - t["cost"]
    t["pnl_bps"] = np.where(t["notional"] > 0, t["pnl"] / t["notional"] * 1e4,
                            np.nan)
    return t


def evaluate(trades: pd.DataFrame, capital: float, label: str = "backtest",
             equity: pd.Series | None = None,
             calendar: pd.DatetimeIndex | None = None,
             start=None, end=None, cost_bps: float | None = None) -> Metrics:
    """The one entry point. Filter, re-cost, rebuild, then measure.

    Order matters: filter first so a re-cost is applied only to the
    trades in scope, then rebuild equity so the curve describes exactly
    the trade set being reported.
    """
    t = standard_trade_log(trades) if "session" in trades.columns else trades.copy()
    if start is not None or end is not None:
        t = filter_period(t, capital, start, end)
    if cost_bps is not None:
        t = reprice(t, cost_bps)

    # A curve is only reused when nothing changed the trade set.
    rebuilt = (start is not None or end is not None or cost_bps is not None
               or equity is None)
    eq = rebuild_equity(t, capital, calendar) if rebuilt else equity

    overall = {**equity_stats(eq, capital), **trade_stats(t)}
    dist = distribution_stats(t)

    years, sides = [], []
    if len(t):
        dser = pd.to_datetime(pd.Series(list(t["date"])))
        t = t.assign(_year=dser.dt.year.to_numpy())
        for y, g in t.groupby("_year"):
            ge = rebuild_equity(g, capital)
            years.append({"year": int(y), **_slim(equity_stats(ge, capital)),
                          **_slim(trade_stats(g)),
                          "skew_wins": distribution_stats(g)["skew_wins"],
                          "exkurt_wins": distribution_stats(g)["exkurt_wins"],
                          "pct_loss_gt_1atr":
                              distribution_stats(g)["pct_loss_gt_1atr"]})
        total = t["pnl"].sum()
        for s, g in t.groupby("side"):
            sides.append({"side": s, **_slim(trade_stats(g)),
                          "total_pnl": float(g["pnl"].sum()),
                          "pct_of_total_pnl":
                              float(g["pnl"].sum() / total) if total else np.nan})
        t = t.drop(columns="_year")

    meta = {"start": str(min(t["date"])) if len(t) else None,
            "end": str(max(t["date"])) if len(t) else None,
            "cost_bps": cost_bps, "equity_rebuilt": rebuilt}
    return Metrics(label=label, capital=capital, overall=overall,
                   distribution=dist, by_year=pd.DataFrame(years),
                   by_side=pd.DataFrame(sides), trades=t, equity=eq,
                   drawdown=drawdown(eq) if len(eq) else eq, meta=meta)


def _slim(d: dict) -> dict:
    keep = ("total_return", "cagr", "max_dd", "sharpe", "n_trades", "win_rate",
            "expectancy_bps", "payoff_ratio", "profit_factor")
    return {k: v for k, v in d.items() if k in keep}
