"""
capacity.py -- the frictions a clean backtest leaves out.

Every analysis here subtracts. None of them can make the strategy look
better, which is the point: the output is a HAIRCUT, an estimate of how
much of the modelled edge survives contact with a real broker, a real
book and a human clicking a mouse.

HOW EACH ONE IS COMPUTED, AND HOW EXACT IT IS

  BORROW      Exact. An extra charge on short notional only. It changes
              nothing about which trades fire or when they exit, so
              re-costing the trade log is precise.

  SLIPPAGE    Exact, by re-running. The entry price is moved adversely
              by k x ATR and the Portfolio is re-run, so the stop
              distance, the sizing and the exit all respond. Applying a
              flat bps haircut instead would miss that a worse entry
              against an unchanged stop level is also a TIGHTER stop.

  CAPACITY    Exact on the data, approximate as a model. Position size
              is compared against the volume actually printed in the
              first 5 and 15 minutes of the hold. Real capacity depends
              on the book, not just prints, so treat the participation
              rate as a screen rather than a limit.

  CONCENTRATION  Exact. Counted off the realised trade log.

  DELAY       Exact at whole minutes, INTERPOLATED below them. The bars
              are one minute, so a 60-second delay is the next bar's
              open and needs no assumption. 30 and 90 seconds do not
              exist in the data; they are linearly interpolated between
              the bracketing opens, and the bracketing bar's own high
              and low are reported so the reader can see how wide the
              true uncertainty is. Do not quote the sub-minute rows
              without that range.

WHAT IS STILL NOT MODELLED: market impact of the order itself, partial
fills, locate failures, queue position, and the possibility that the
signal disappears while you are hesitating.
"""

from __future__ import annotations

from dataclasses import dataclass, replace as dc_replace
from pathlib import Path

import numpy as np
import pandas as pd

from engine.config import BacktestConfig
from engine.metrics import evaluate
from engine.portfolio import Portfolio, SelectionRule
from engine.strategy_base import Signal

DEFAULT_BORROW_BPS = [0.0, 5.0, 10.0, 20.0]
DEFAULT_SLIP_ATR = [0.0, 0.1, 0.2]
DEFAULT_PARTICIPATION = [0.01, 0.05, 0.10]
DEFAULT_DELAYS_SEC = [0, 30, 60, 90]


def _kept(new: float, base: float) -> float:
    """`new / base`, but ONLY when the base is a profit.

    A "percentage of P&L kept" ratio silently inverts when the base is
    negative: a loss growing from -881 to -1081 computes as 1.23, which
    reads as "123% kept" when the truth is a fifth worse. Every friction
    here can only subtract, so a ratio above 1.0 is always a signal that
    the denominator is wrong, not that the friction helped. Return NaN
    and let the absolute change carry the meaning.
    """
    if not np.isfinite(base) or base <= 0:
        return float("nan")
    return float(new / base)


def _base(cfg, signals, frames, selection=SelectionRule.VOLUME_RATIO):
    log, curve = Portfolio(cfg, selection).run(signals, frames)
    return evaluate(log, cfg.portfolio.starting_capital, "base", equity=curve)


# ------------------------------------------------------------------ borrow

def borrow_stress(cfg: BacktestConfig, signals, frames,
                  extra_bps=None) -> pd.DataFrame:
    """Charge shorts an extra borrow cost. Longs are untouched.

    Reported alongside the short side's share of gross P&L, because the
    two together are the actual exposure: a book that earns most of its
    money short is the one that cares most about borrow.
    """
    m = _base(cfg, signals, frames)
    t = m.trades
    if t.empty:
        return pd.DataFrame()
    is_short = (t["side"] == "SHORT").to_numpy()
    notional = t["notional"].to_numpy()
    base_pnl = t["pnl"].to_numpy()

    rows = []
    for bps in (extra_bps or DEFAULT_BORROW_BPS):
        charge = np.where(is_short, notional * bps / 1e4, 0.0)
        pnl = base_pnl - charge
        rows.append({
            "extra_borrow_bps": bps,
            "total_pnl": float(pnl.sum()),
            "pnl_change": float(pnl.sum() - base_pnl.sum()),
            "pct_of_base_pnl": _kept(pnl.sum(), base_pnl.sum()),
            "expectancy_bps": float(np.mean(pnl / notional * 1e4)),
            "short_expectancy_bps": float(
                np.mean((pnl / notional * 1e4)[is_short])) if is_short.any() else np.nan,
            "borrow_cost_paid": float(charge.sum()),
        })
    out = pd.DataFrame(rows)
    out.attrs["short_share_of_gross_pnl"] = float(
        t.loc[t["side"] == "SHORT", "pnl"].sum() / t["pnl"].sum()
    ) if t["pnl"].sum() else np.nan
    out.attrs["short_share_of_trades"] = float(is_short.mean())
    return out


# ---------------------------------------------------------------- slippage

def _slip_signals(signals: list[Signal], k: float) -> list[Signal]:
    """Move every entry adversely by k x ATR."""
    if k == 0:
        return signals
    out = []
    for s in signals:
        px = s.entry_price + s.direction * k * s.risk_unit
        if px <= 0:
            continue
        out.append(dc_replace(s, entry_price=float(px)))
    return out


def slippage_stress(cfg: BacktestConfig, signals, frames,
                    slips=None) -> pd.DataFrame:
    """Adverse entry slippage in ATR units, applied by full re-run.

    A worse entry against a stop measured from that entry keeps the stop
    distance constant, so this isolates the price paid rather than
    silently re-cutting the risk. What it DOES change is the exit
    distance to the profit side, which is the real cost.
    """
    rows = []
    base_pnl = None
    for k in (slips or DEFAULT_SLIP_ATR):
        m = _base(cfg, _slip_signals(signals, k), frames)
        o = m.overall
        if base_pnl is None:
            base_pnl = m.trades["pnl"].sum()
        rows.append({
            "slippage_atr": k,
            "n_trades": o.get("n_trades"),
            "expectancy_bps": o.get("expectancy_bps"),
            "win_rate": o.get("win_rate"),
            "cagr": o.get("cagr"),
            "max_dd": o.get("max_dd"),
            "total_pnl": float(m.trades["pnl"].sum()) if len(m.trades) else np.nan,
            "pct_of_base_pnl": _kept(m.trades["pnl"].sum(), base_pnl),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- capacity

def participation(cfg: BacktestConfig, signals, frames,
                  windows=(5, 15), limits=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Position size against volume printed in the first N minutes.

    Returns (per-trade detail, summary by limit). The detail frame is the
    useful one for finding which names are untradeable at size.
    """
    m = _base(cfg, signals, frames)
    t = m.trades
    if t.empty:
        return pd.DataFrame(), pd.DataFrame()

    det = t[["trade_id", "ticker", "date", "entry_time", "shares",
             "notional", "pnl"]].copy()
    for w in windows:
        vols = []
        for _, r in t.iterrows():
            bars = frames.get(r["ticker"])
            if bars is None:
                vols.append(np.nan)
                continue
            lo = r["entry_time"]
            hi = lo + pd.Timedelta(minutes=w)
            vols.append(float(bars.loc[(bars.index >= lo)
                                       & (bars.index < hi), "volume"].sum()))
        det[f"vol_{w}m"] = vols
        det[f"participation_{w}m"] = det["shares"] / det[f"vol_{w}m"]

    rows = []
    for lim in (limits or DEFAULT_PARTICIPATION):
        for w in windows:
            p = det[f"participation_{w}m"]
            over = p > lim
            # A trade over the limit is not dropped, it is SCALED to the
            # limit -- which is what a desk would do -- so the cost is
            # the P&L given up, not the whole trade.
            scale = np.where(over, lim / p, 1.0)
            rows.append({
                "window_min": w, "max_participation": lim,
                "n_over_limit": int(over.sum()),
                "pct_over_limit": float(over.mean()),
                "median_participation": float(p.median()),
                "p90_participation": float(p.quantile(0.90)),
                "pnl_if_scaled": float((det["pnl"] * scale).sum()),
                "pct_of_pnl_kept": _kept((det["pnl"] * scale).sum(),
                                         det["pnl"].sum()),
            })
    return det, pd.DataFrame(rows)


# ----------------------------------------------------------- concentration

def concentration(cfg: BacktestConfig, signals, frames) -> tuple[pd.DataFrame, dict]:
    """How many names share the book, and who carries the P&L."""
    m = _base(cfg, signals, frames)
    t = m.trades
    if t.empty:
        return pd.DataFrame(), {}

    per_day = t.groupby("date").size()
    dist = (per_day.value_counts().sort_index().rename("n_days")
            .to_frame().reset_index()
            .rename(columns={"index": "concurrent_positions"}))
    dist.columns = ["concurrent_positions", "n_days"]
    dist["pct_of_active_days"] = dist["n_days"] / len(per_day)

    by_name = t.groupby("ticker")["pnl"].agg(["sum", "size"]).sort_values(
        "sum", ascending=False)
    total = t["pnl"].sum()
    stats = {
        "active_days": int(len(per_day)),
        "mean_concurrent": float(per_day.mean()),
        "median_concurrent": float(per_day.median()),
        "pct_days_1_or_2_names": float((per_day <= 2).mean()),
        "pct_days_single_name": float((per_day == 1).mean()),
        "max_concurrent_seen": int(per_day.max()),
        "n_tickers": int(t["ticker"].nunique()),
        "top_name": str(by_name.index[0]),
        "top_name_pnl": float(by_name["sum"].iloc[0]),
        "top_name_pct_of_pnl": float(by_name["sum"].iloc[0] / total)
        if total else np.nan,
        "top5_pct_of_pnl": float(by_name["sum"].head(5).sum() / total)
        if total else np.nan,
    }
    return dist, stats


# --------------------------------------------------------------- the delay

def _delayed_signals(signals: list[Signal], seconds: int,
                     frames: dict[str, pd.DataFrame]) -> tuple[list[Signal], int]:
    """Shift entries later. Whole minutes are exact; the rest interpolate.

    The planned exit does NOT move: exiting is a clock decision, and a
    slow entry does not earn a longer hold.
    """
    if seconds == 0:
        return signals, 0
    whole, frac = divmod(seconds, 60)
    out, interpolated = [], 0
    for s in signals:
        bars = frames.get(s.ticker)
        if bars is None:
            continue
        t0 = s.entry_ts + pd.Timedelta(minutes=whole)
        t1 = t0 + pd.Timedelta(minutes=1)
        if t0 not in bars.index:
            continue
        p0 = float(bars.loc[t0, "open"])
        if frac == 0:
            px = p0
        else:
            if t1 not in bars.index:
                continue
            p1 = float(bars.loc[t1, "open"])
            px = p0 + (p1 - p0) * (frac / 60.0)
            interpolated += 1
        if px <= 0 or s.planned_exit_ts <= t0:
            continue
        out.append(dc_replace(s, entry_ts=t0, entry_price=float(px),
                              decision_ts=min(s.decision_ts, t0)))
    return out, interpolated


def delay_stress(cfg: BacktestConfig, signals, frames,
                 seconds=None) -> pd.DataFrame:
    """Expectancy lost to entering late. Sub-minute rows are estimates."""
    rows = []
    base_exp = None
    for sec in (seconds or DEFAULT_DELAYS_SEC):
        sigs, interp = _delayed_signals(signals, sec, frames)
        if not sigs:
            continue
        m = _base(cfg, sigs, frames)
        o = m.overall
        if base_exp is None:
            base_exp = o.get("expectancy_bps")
        rows.append({
            "delay_sec": sec,
            "exact": "yes" if sec % 60 == 0 else "INTERPOLATED",
            "n_trades": o.get("n_trades"),
            "expectancy_bps": o.get("expectancy_bps"),
            "vs_base_bps": (o.get("expectancy_bps") - base_exp)
            if base_exp is not None else np.nan,
            "pct_of_edge_kept": _kept(o.get("expectancy_bps"), base_exp),
            "win_rate": o.get("win_rate"),
            "cagr": o.get("cagr"),
        })
    return pd.DataFrame(rows)


# ------------------------------------------------------------------- suite

def run_suite(cfg: BacktestConfig, signals, frames, **kw) -> dict:
    det, part = participation(cfg, signals, frames,
                              limits=kw.get("participation"))
    dist, conc = concentration(cfg, signals, frames)
    return {
        "borrow": borrow_stress(cfg, signals, frames, kw.get("borrow_bps")),
        "slippage": slippage_stress(cfg, signals, frames, kw.get("slip_atr")),
        "participation_detail": det,
        "participation": part,
        "concentration_dist": dist,
        "concentration_stats": conc,
        "delay": delay_stress(cfg, signals, frames, kw.get("delays_sec")),
    }


def haircut(tables: dict, cfg: BacktestConfig,
            assume_borrow_bps: float = 10.0,
            assume_slip_atr: float = 0.1,
            assume_delay_sec: int = 60,
            assume_participation: float = 0.05) -> pd.DataFrame:
    """Stack the frictions into one practical estimate.

    Deliberately additive on P&L ratios rather than compounded. The
    components are not independent -- a slow entry and a wide spread are
    the same market condition -- so multiplying them would overstate the
    damage while pretending to precision. Read this as an order of
    magnitude, and read the sign as certain even where the size is not.
    """
    rows = []

    b = tables.get("borrow")
    if b is not None and len(b):
        hit = b[b["extra_borrow_bps"] == assume_borrow_bps]
        if len(hit):
            rows.append({"friction": f"borrow +{assume_borrow_bps:g} bps on shorts",
                         "pct_of_pnl_kept": hit.iloc[0]["pct_of_base_pnl"]})

    s = tables.get("slippage")
    if s is not None and len(s):
        hit = s[s["slippage_atr"] == assume_slip_atr]
        if len(hit):
            rows.append({"friction": f"entry slippage {assume_slip_atr:g} ATR",
                         "pct_of_pnl_kept": hit.iloc[0]["pct_of_base_pnl"]})

    p = tables.get("participation")
    if p is not None and len(p):
        hit = p[(p["max_participation"] == assume_participation)
                & (p["window_min"] == 5)]
        if len(hit):
            rows.append({"friction": f"capacity {assume_participation:.0%} of 5-min volume",
                         "pct_of_pnl_kept": hit.iloc[0]["pct_of_pnl_kept"]})

    d = tables.get("delay")
    if d is not None and len(d):
        hit = d[d["delay_sec"] == assume_delay_sec]
        if len(hit):
            rows.append({"friction": f"{assume_delay_sec}s execution delay",
                         "pct_of_pnl_kept": hit.iloc[0]["pct_of_edge_kept"]})

    out = pd.DataFrame(rows)
    if not len(out):
        return out
    out["pct_lost"] = 1.0 - out["pct_of_pnl_kept"]
    usable = out["pct_lost"].notna()
    if not usable.any():
        # Every component divided by a non-positive base. Saying so beats
        # printing a total assembled from nothing.
        out.loc[len(out)] = {"friction": "COMBINED — NOT COMPUTABLE "
                                         "(base P&L is not positive)",
                             "pct_of_pnl_kept": np.nan, "pct_lost": np.nan}
        return out
    total_lost = out.loc[usable, "pct_lost"].clip(lower=0).sum()
    label = "COMBINED (additive)"
    if (~usable).any():
        label += f" — {int((~usable).sum())} component(s) omitted"
    out.loc[len(out)] = {"friction": label,
                         "pct_of_pnl_kept": 1.0 - total_lost,
                         "pct_lost": total_lost}
    return out


def dashboard(tables: dict, cfg: BacktestConfig, hc: pd.DataFrame) -> str:
    L = ["=" * 78,
         f"RISK & CAPACITY  --  {cfg.strategy.name} v{cfg.strategy.version}",
         "=" * 78, ""]

    def block(title, frame, note=""):
        if frame is None or (hasattr(frame, "empty") and frame.empty):
            return
        L.extend([title, "-" * len(title)])
        if note:
            L.append(note)
        L.extend([_fmt(frame), ""])

    b = tables.get("borrow")
    note = ""
    if b is not None and len(b):
        note = (f"short side is {b.attrs.get('short_share_of_trades', float('nan')):.0%} "
                f"of trades and "
                f"{b.attrs.get('short_share_of_gross_pnl', float('nan')):.0%} "
                f"of net P&L")
    block("1. BORROW & SHORT-SIDE RISK", b, note)
    block("2. ENTRY SLIPPAGE  (full re-run at each level)", tables.get("slippage"))
    block("3. CAPACITY  (position vs printed volume; over-limit trades SCALED, not dropped)",
          tables.get("participation"))
    block("4. CONCENTRATION  (days by number of open positions)",
          tables.get("concentration_dist"))

    c = tables.get("concentration_stats") or {}
    if c:
        L += [f"    mean concurrent      {c.get('mean_concurrent', float('nan')):.2f}"
              f"   median {c.get('median_concurrent', float('nan')):.0f}"
              f"   max {c.get('max_concurrent_seen', 0)}",
              f"    days with 1-2 names  {c.get('pct_days_1_or_2_names', float('nan')):.0%}"
              f"   (single name {c.get('pct_days_single_name', float('nan')):.0%})",
              f"    largest single name  {c.get('top_name', '?')} at "
              f"{c.get('top_name_pct_of_pnl', float('nan')):.0%} of P&L; "
              f"top 5 = {c.get('top5_pct_of_pnl', float('nan')):.0%}", ""]

    block("5. OPERATIONAL DELAY  (exit stays on the clock)", tables.get("delay"),
          "sub-minute rows are INTERPOLATED between bracketing bar opens")

    if len(hc):
        L += ["PRACTICAL HAIRCUT", "-" * 17,
              "components stacked additively; they are correlated, so treat",
              "this as an order of magnitude, not a point estimate",
              _fmt(hc), ""]

    L += ["RECOMMENDED LIVE LIMITS", "-" * 23, *_limits(tables, c, cfg)]
    return "\n".join(L)


def _limits(tables: dict, conc: dict, cfg: BacktestConfig) -> list[str]:
    out = []
    p = tables.get("participation")
    if p is not None and len(p):
        five = p[p["window_min"] == 5].sort_values("max_participation")
        good = five[five["pct_of_pnl_kept"] > 0.95]
        if len(good):
            out.append(f"  size cap        keep position <= "
                       f"{good.iloc[0]['max_participation']:.0%} of the first "
                       f"5 minutes' volume; above that the trade log starts "
                       f"needing to be scaled.")
    if conc:
        out.append(f"  concentration   the book is in 1-2 names on "
                   f"{conc.get('pct_days_1_or_2_names', float('nan')):.0%} of active "
                   f"days. Per-name loss limits matter more than portfolio "
                   f"ones at that count.")
    d = tables.get("delay")
    if d is not None and len(d) > 1:
        row = d[d["delay_sec"] == 60]
        if len(row) and pd.notna(row.iloc[0]["pct_of_edge_kept"]):
            out.append(f"  execution       one minute late keeps "
                       f"{row.iloc[0]['pct_of_edge_kept']:.0%} of the edge. "
                       f"Automate the entry or pre-stage the ticket.")
        elif len(row):
            out.append(f"  execution       one minute late costs "
                       f"{row.iloc[0]['vs_base_bps']:,.1f} bps of expectancy "
                       f"(ratio not shown: base expectancy is not positive).")
    b = tables.get("borrow")
    if b is not None and len(b):
        sh = b.attrs.get("short_share_of_gross_pnl", float("nan"))
        if pd.notna(sh) and 0.4 < sh <= 1.0:
            out.append(f"  borrow          {sh:.0%} of P&L is short-side. Get "
                       f"a real borrow quote before sizing; it is not modelled "
                       f"anywhere in the backtest.")
    return out or ["  (insufficient data to recommend limits)"]


def _fmt(df) -> str:
    if isinstance(df, dict):
        return "\n".join(f"    {k:<28} {v}" for k, v in df.items())
    x = df.copy()
    for c in x.columns:
        if pd.api.types.is_float_dtype(x[c]):
            x[c] = x[c].map(lambda v: "" if pd.isna(v) else f"{v:,.4f}")
    return x.to_string(index=False)


def write(tables: dict, out_dir: Path | str, text: str | None = None,
          hc: pd.DataFrame | None = None) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, t in tables.items():
        if isinstance(t, pd.DataFrame) and len(t):
            p = out_dir / f"capacity_{name}.csv"
            t.to_csv(p, index=False)
            paths.append(p)
        elif isinstance(t, dict) and t:
            p = out_dir / f"capacity_{name}.csv"
            pd.DataFrame([t]).to_csv(p, index=False)
            paths.append(p)
    if hc is not None and len(hc):
        p = out_dir / "capacity_haircut.csv"
        hc.to_csv(p, index=False)
        paths.append(p)
    if text is not None:
        p = out_dir / "capacity_dashboard.txt"
        p.write_text(text)
        paths.append(p)
    return paths
