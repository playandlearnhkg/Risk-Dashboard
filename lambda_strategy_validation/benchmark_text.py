"""benchmark_text.py -- prose for BENCHMARK_REPORT.md.

Every figure is read from the frames benchmark.py computed. Nothing is
retyped, so the narrative cannot drift from the tables.
"""

from __future__ import annotations

import pandas as pd

from benchmark import md


def build(ladder: pd.DataFrame, P: pd.DataFrame, REG: pd.DataFrame,
          COST: pd.DataFrame, meta: dict, E: pd.DataFrame) -> str:
    L = ladder.copy()
    L["ret_per_unit_risk"] = L["mean_net"] / L["std"]
    Lp = L.rename(columns={
        "exit": "exit rule", "mean_net": "mean net",
        "win_rate": "win rate", "std": "std dev",
        "spy_same_window": "SPY, same window", "excess_vs_spy": "excess vs SPY",
        "ret_per_unit_risk": "return / risk"})
    ladder_md = md(Lp, pct=("mean net", "median", "win rate", "std dev",
                            "SPY, same window", "excess vs SPY"),
                   num=("return / risk",))

    Pp = P.rename(columns={
        "total_return": "total return", "cagr": "CAGR",
        "ann_vol": "ann. vol", "sharpe": "Sharpe (rf=0)",
        "max_dd": "max drawdown", "calmar": "Calmar",
        "best_day": "best day", "worst_day": "worst day",
        "pct_days_deployed": "% days deployed"})
    port_md = md(Pp, pct=("total return", "CAGR", "ann. vol", "max drawdown",
                          "best day", "worst day", "% days deployed"),
                 num=("Sharpe (rf=0)", "Calmar"))

    Rp = REG.rename(columns={
        "beta_to_spy": "beta to SPY", "alpha_ann": "alpha, annualised",
        "corr_to_spy": "corr to SPY", "up_day_mean": "mean on SPY up days",
        "down_day_mean": "mean on SPY down days"})
    for c in ("beta to SPY", "corr to SPY"):        # 2dp would print 0.01
        Rp[c] = Rp[c].map("{:.4f}".format)
    reg_md = md(Rp, pct=("alpha, annualised", "mean on SPY up days",
                         "mean on SPY down days"))

    Cp = COST.rename(columns={"cost_bps": "round-trip cost (bps)",
                              "mean_net_bps": "mean net (bps)",
                              "win_rate": "win rate", "cagr": "strategy CAGR"})
    cost_md = md(Cp, pct=("win rate", "strategy CAGR"),
                 num=("round-trip cost (bps)", "mean net (bps)"))

    def row(name):
        return P[P.portfolio == name].iloc[0]

    ns, st = row("Strategy only, no stop"), row("Strategy only, ATR -1.0 stop")
    spy = row("SPY buy-and-hold")
    b70 = row("70% SPY + 30% strategy (stop)")
    ov = row("100% SPY + 25% strategy overlay (stop)")
    bk1 = row("Signal basket, long, 1 day hold")

    def lrow(sub):
        return L[L["exit"].str.contains(sub, regex=False)].iloc[0]

    h1 = lrow("STRATEGY 1 hour, no stop")
    s60 = lrow("60 days (~1 quarter) -- SIGNED")
    l60 = lrow("60 days (~1 quarter) -- LONG-ONLY")
    l1 = lrow("1 day -- LONG-ONLY")
    conc, dv = meta["concurrency"], meta["deployed_vol"]
    gross = h1["mean_net"] * 1e4 + meta["cost_bps"]
    c25 = COST[COST.cost_bps == 25.0].iloc[0]
    per_year = meta["n_trades"] / (meta["trading_days"] / 252)

    return f"""# Post-earnings T+1 continuation vs buy-and-hold

{meta['n_trades']:,} trades, {meta['n_tickers']} tickers, {meta['start']} to {meta['end']},
across {meta['trading_days']:,} trading sessions.

**One definitional fix.** The brief says "non-doji, body/range <= 0.10",
which is the doji condition rather than its complement. The cohort here
uses body/range **> 0.10**, i.e. genuinely non-doji, matching every
earlier report in this programme.

## Assumptions that drive the numbers

| Choice | What was assumed | Why it matters |
|---|---|---|
| Direction | Short on gap-down continuations | "Buy the same stock" and "hold the position longer" are different questions; both are reported |
| Capital | Sleeve equal-weights that day's signals, cash otherwise | Charges the strategy for idle days rather than annualising deployed hours only |
| Cash yield | Zero on idle cash, rf = 0 in Sharpe | Conservative: a real cash rate adds ~{meta['cash_add']['2%']*100:.1f} pp/yr at 2%, ~{meta['cash_add']['4%']*100:.1f} pp/yr at 4%, and subtracts nothing |
| Costs | Flat {meta['cost_bps']} bps round trip | The most exposed assumption here; sensitivity is in section D4 |
| Deployment | Signal on {meta['pct_days_with_signal']*100:.1f}% of sessions, ~{meta['pct_time_deployed']*100:.1f}% of market hours | The strategy is in cash the overwhelming majority of the time |

## A. Per-trade comparison

Entry is identical in every row: the open of the 09:35 bar. Only the
exit differs. LONG-ONLY buys regardless of gap direction; SIGNED holds
the strategy's own direction for longer.

{ladder_md}

Three things read straight off this table.

**Buying these names and holding is a losing trade at short horizons.**
One day long-only returns {l1['mean_net']*1e4:.0f} bps at a {l1['win_rate']*100:.1f}% win rate. Half the
signals are gap-down names and holding those long is simply the wrong
side.

**At long horizons you are buying beta, and slightly less of it than
SPY.** Sixty sessions long-only returns {l60['mean_net']*100:.2f}% against {l60['spy_same_window']*100:.2f}% for SPY
over the identical windows -- an excess of {l60['excess_vs_spy']*1e4:.0f} bps. You would have
done better owning the index.

**Holding the direction longer earns more per trade and much less per
unit of risk.** Sixty sessions signed returns {s60['mean_net']*1e4:.0f} bps against the
1-hour {h1['mean_net']*1e4:.0f} bps, but its standard deviation is {s60['std']/h1['std']:.0f}x larger, so
return-per-unit-risk falls from {h1['ret_per_unit_risk']:.3f} to {s60['ret_per_unit_risk']:.3f}. The extra return
costs far more risk than it is worth, and ties capital up for a quarter
instead of an hour.

## B and C. Portfolio level, with risk-adjusted metrics

{port_md}

## Is it market exposure in disguise?

{reg_md}

Beta to SPY is {REG.iloc[0]['beta_to_spy']:.3f}, correlation {REG.iloc[0]['corr_to_spy']:.3f}. Essentially all of the
return is alpha, and the strategy earns as much on SPY down days
({REG.iloc[0]['down_day_mean']*1e4:.0f} bps) as on up days ({REG.iloc[0]['up_day_mean']*1e4:.0f} bps). Whatever this is, it is
not disguised long exposure -- which is what makes it useful as an
overlay rather than a substitute.

## D. The four questions

**1. Does it add value on top of holding SPY?** Yes, and the blend is
the practical form. 70/30 lifts CAGR from {spy['cagr']*100:.1f}% to {b70['cagr']*100:.1f}% while
*lowering* volatility from {spy['ann_vol']*100:.1f}% to {b70['ann_vol']*100:.1f}% and cutting max drawdown
from {spy['max_dd']*100:.1f}% to {b70['max_dd']*100:.1f}%. Sharpe roughly doubles, {spy['sharpe']:.2f} to {b70['sharpe']:.2f}.
Improving all three axes at once is only possible because the
correlation is near zero.

The overlay version (100% SPY plus a 25% notional sleeve funded by
intraday buying power rather than by selling SPY) reaches a higher CAGR
still at {ov['cagr']*100:.1f}%, but inherits SPY's drawdown ({ov['max_dd']*100:.1f}%) because it never
reduces market exposure. Capital-split blend for risk reduction, overlay
for return.

**2. Is the 1-hour edge worth the activity versus longer holds?** On
risk-adjusted terms, clearly. The 1-hour hold has the best
return-per-unit-risk in section A ({h1['ret_per_unit_risk']:.3f}) and achieves it while using
capital ~{meta['pct_time_deployed']*100:.1f}% of market hours. Every longer hold is worse per unit
of risk and locks capital up for days or months. The
buy-and-hold-the-signal-names baskets confirm it from the portfolio
side: the 1-day long basket compounds at {bk1['cagr']*100:.1f}% a year with a {bk1['max_dd']*100:.1f}%
drawdown.

The caveat is that "worth it" here ignores the operational load: about
{per_year:.0f} trades a year, all at a fixed minute of the session.

**3. How does the ATR -1.0 stop compare in a portfolio context?** It
costs more than it saves. CAGR falls from {ns['cagr']*100:.1f}% to {st['cagr']*100:.1f}% and max
drawdown gets *worse*, {ns['max_dd']*100:.1f}% to {st['max_dd']*100:.1f}%. Sharpe drops {ns['sharpe']:.2f} to
{st['sharpe']:.2f}, Calmar {ns['calmar']:.2f} to {st['calmar']:.2f}.

What it does buy is a shallower worst day, {ns['worst_day']*100:.1f}% to {st['worst_day']*100:.1f}%,
firing on {meta['stop_rate']*100:.1f}% of trades. So it trims the single worst session
but not the drawdown that matters, because drawdowns here accumulate
from ordinary losing days rather than one catastrophic one. That is
consistent with what the stop work already found at trade level: it
truncates the tail and pays for it in expectancy.

**4. Where does this break?** Cost, before anything else.

{cost_md}

Gross edge is {gross:.1f} bps, so the strategy dies at roughly **{gross:.0f} bps round
trip**, about {gross/meta['cost_bps']:.1f}x the assumed cost. At 25 bps it still compounds
at {c25['cagr']*100:.1f}%, roughly SPY's rate, with none of SPY's drawdown. That is a
wide margin -- but 09:35 in a post-earnings name is exactly where
spreads are widest, and a flat {meta['cost_bps']} bps does not distinguish a
mega-cap from a mid-cap on the morning after a surprise.

## What these numbers do not include

- **Borrow.** Roughly half the trades are shorts. No borrow cost or
  locate constraint is modelled, and post-earnings names are exactly
  when borrow gets expensive and hard to source.
- **Concentration.** The sleeve holds {conc['mean']:.1f} names on an average deployed
  day, median {conc['median']:.0f}, and is in a **single name on {conc['pct_single_name']*100:.0f}% of deployed
  days** (p90 {conc['p90']:.0f} names, max {conc['max']}). The portfolio statistics are real,
  but they are not a diversified book's.
- **The Sharpe is flattered by idle days.** Volatility measured only on
  days capital is at work is {dv['no stop']*100:.1f}%, not the {ns['ann_vol']*100:.1f}% headline. Both are
  honest answers to different questions; anyone sizing the sleeve should
  use the deployed figure.
- **Capacity.** Nothing here constrains position size against a name's
  actual liquidity in that hour.

Generated by `benchmark.py`.
"""
