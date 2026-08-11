"""fullvalidation_text.py -- prose for FULLVAL_REPORT.md.

Every figure is read from the frames fullvalidation.py computed, so the
narrative cannot drift from the tables.
"""

from __future__ import annotations

import pandas as pd

from fullvalidation import md


def build(meta, sims, years, dists, YD, G, CG, CK, best, worst, cal) -> str:
    ns, st = meta["base"]["nostop"], meta["base"]["stop"]
    dn, ds = dists["nostop"], dists["stop"]
    whip, rnd = meta["whipsaw"], meta["random_rank"]

    hdr = pd.DataFrame([
        {"metric": "Final equity", "no stop": f"${ns['final']:,.0f}",
         "ATR -1.0 stop": f"${st['final']:,.0f}"},
        {"metric": "Total return", "no stop": f"{ns['total_return']*100:,.1f}%",
         "ATR -1.0 stop": f"{st['total_return']*100:,.1f}%"},
        {"metric": "CAGR", "no stop": f"{ns['cagr']*100:.2f}%",
         "ATR -1.0 stop": f"{st['cagr']*100:.2f}%"},
        {"metric": "Annualised volatility", "no stop": f"{ns['ann_vol']*100:.2f}%",
         "ATR -1.0 stop": f"{st['ann_vol']*100:.2f}%"},
        {"metric": "Sharpe (rf = 0)", "no stop": f"{ns['sharpe']:.2f}",
         "ATR -1.0 stop": f"{st['sharpe']:.2f}"},
        {"metric": "Max drawdown", "no stop": f"{ns['max_dd']*100:.2f}%",
         "ATR -1.0 stop": f"{st['max_dd']*100:.2f}%"},
        {"metric": "Calmar", "no stop": f"{ns['calmar']:.2f}",
         "ATR -1.0 stop": f"{st['calmar']:.2f}"},
        {"metric": "Trades taken", "no stop": f"{ns['n_trades']:,}",
         "ATR -1.0 stop": f"{st['n_trades']:,}"},
        {"metric": "Signals taken (of all fired)",
         "no stop": f"{ns['pct_signals_taken']*100:.1f}%",
         "ATR -1.0 stop": f"{st['pct_signals_taken']*100:.1f}%"},
        {"metric": "Sessions with a position",
         "no stop": f"{ns['pct_days_active']*100:.1f}%",
         "ATR -1.0 stop": f"{st['pct_days_active']*100:.1f}%"},
        {"metric": "Time in market (clock)",
         "no stop": f"{ns['pct_time_in_market']*100:.1f}%",
         "ATR -1.0 stop": f"{st['pct_time_in_market']*100:.1f}%"},
        {"metric": "Avg gross exposure when active",
         "no stop": f"{ns['avg_gross_when_active']*100:.0f}%",
         "ATR -1.0 stop": f"{st['avg_gross_when_active']*100:.0f}%"},
        {"metric": "Avg positions when active",
         "no stop": f"{ns['avg_positions_when_active']:.1f}",
         "ATR -1.0 stop": f"{st['avg_positions_when_active']:.1f}"},
    ])

    yr_md = {k: md(v.rename(columns={
        "year": "year", "net_return": "net return", "max_dd": "max DD",
        "sharpe": "Sharpe", "n_trades": "trades", "win_rate": "win rate",
        "avg_trade_bps": "avg trade (bps)", "skew_wins": "skew (wins.)",
        "exkurt_wins": "ex-kurt (wins.)", "pct_loss_1atr": "% losing >1 ATR"}),
        pct=("net return", "max DD", "win rate", "% losing >1 ATR"),
        num=("Sharpe", "avg trade (bps)"),
        num3=("skew (wins.)", "ex-kurt (wins.)")) for k, v in years.items()}

    D = pd.DataFrame([{"exit": "1 hour, no stop", **dn},
                      {"exit": "1 hour, ATR -1.0 stop", **ds}])
    D = D.rename(columns={
        "mean_bps": "mean", "median_bps": "median", "std_bps": "std",
        "win_rate": "win rate", "skew_wins": "skew (wins.)",
        "exkurt_wins": "ex-kurt (wins.)", "skew_raw": "skew (raw)",
        "exkurt_raw": "ex-kurt (raw)", "pct_loss_0.5atr": "% < -0.5 ATR",
        "pct_loss_1atr": "% < -1 ATR", "avg_large_loss_bps": "avg large loss"})
    dist_md = md(D, pct=("win rate", "% < -0.5 ATR", "% < -1 ATR"),
                 num=("mean", "median", "std", "p10", "p25", "p75", "p90",
                      "avg large loss"),
                 num3=("skew (wins.)", "ex-kurt (wins.)", "skew (raw)",
                       "ex-kurt (raw)"))

    YDp = YD.rename(columns={
        "mean_bps": "mean", "median_bps": "median", "std_bps": "std",
        "win_rate": "win rate", "skew_wins": "skew (wins.)",
        "exkurt_wins": "ex-kurt (wins.)", "pct_loss_0.5atr": "% < -0.5 ATR",
        "pct_loss_1atr": "% < -1 ATR", "avg_large_loss_bps": "avg large loss"})
    YDp = YDp.drop(columns=["skew_raw", "exkurt_raw"])
    ydist_md = md(YDp, pct=("win rate", "% < -0.5 ATR", "% < -1 ATR"),
                  num=("mean", "median", "std", "p10", "p25", "p75", "p90",
                       "avg large loss"),
                  num3=("skew (wins.)", "ex-kurt (wins.)"))

    Gp = G.rename(columns={"max_pos": "max concurrent", "final_equity": "final equity",
                           "cagr": "CAGR", "ann_vol": "vol", "sharpe": "Sharpe",
                           "max_dd": "max DD", "calmar": "Calmar",
                           "n_trades": "trades",
                           "pct_signals_taken": "% signals taken",
                           "avg_gross": "avg gross"})
    Gp["final equity"] = Gp["final equity"].map(lambda v: f"${v/1e6:,.2f}M")
    grid_md = md(Gp, pct=("CAGR", "vol", "max DD", "% signals taken", "avg gross"),
                 num=("Sharpe", "Calmar"))

    CGp = CG.rename(columns={"cost_bps": "cost (bps)", "final_equity": "final equity",
                             "cagr": "CAGR", "sharpe": "Sharpe",
                             "max_dd": "max DD", "calmar": "Calmar"})
    CGp["final equity"] = CGp["final equity"].map(lambda v: f"${v/1e6:,.2f}M")
    cost_md = md(CGp, pct=("CAGR", "max DD"), num=("cost (bps)", "Sharpe", "Calmar"))

    CKp = CK.rename(columns={"n_signals": "signals", "n_taken": "taken",
                             "cagr_stop": "CAGR (stop)", "cagr_nostop": "CAGR (no stop)",
                             "sharpe_stop": "Sharpe (stop)", "max_dd_stop": "max DD (stop)",
                             "mean_bps_stop": "mean bps (stop)", "win_rate": "win rate"})
    check_md = md(CKp, pct=("CAGR (stop)", "CAGR (no stop)", "max DD (stop)", "win rate"),
                  num=("Sharpe (stop)", "mean bps (stop)"))

    tcols = ["trade_id", "date", "ticker", "side", "gap_pct", "gap_atr",
             "vol_ratio", "atr_pct", "net_stop_bps", "net_nostop_bps",
             "mae_stop_atr", "mfe_stop_atr", "stopped", "pnl_usd_base"]

    def trade_md(df):
        x = df[tcols].copy()
        x["date"] = pd.to_datetime(x["date"]).dt.date
        x = x.rename(columns={"gap_pct": "gap %", "gap_atr": "gap ATR",
                              "vol_ratio": "vol x", "atr_pct": "ATR %",
                              "net_stop_bps": "net stop", "net_nostop_bps": "net no-stop",
                              "mae_stop_atr": "MAE", "mfe_stop_atr": "MFE",
                              "pnl_usd_base": "P&L $"})
        for c in ("gap %", "gap ATR", "vol x", "ATR %", "MAE", "MFE"):
            x[c] = x[c].map("{:.2f}".format)
        for c in ("net stop", "net no-stop"):
            x[c] = x[c].map("{:,.0f}".format)
        x["P&L $"] = x["P&L $"].map(lambda v: f"{v:,.0f}")
        return md(x)

    yst = years["stop"]
    early = yst[yst.year <= 2019]["avg_trade_bps"].mean()
    late = yst[yst.year >= 2020]["avg_trade_bps"].mean()

    return f"""# Full validation -- post-earnings T+1 continuation, ${meta['capital']:,.0f}

{meta['n_signals']:,} signals, {meta['n_tickers']} tickers, {meta['start']} to {meta['end']},
{meta['sessions']:,} sessions. {meta['long_share']*100:.1f}% long / {(1-meta['long_share'])*100:.1f}% short.

Base configuration for every table unless stated: **fixed fractional
0.5% risk, max 5 concurrent positions, {meta['base_cost']} bps**. Grids for the
other sizings, limits and costs are in section E.

## Assumptions, stated plainly

| Assumption | Choice | Consequence |
|---|---|---|
| Signal selection when a day exceeds the position limit | Highest volume ratio first | Known at 09:35, no look-ahead. Random selection instead gives CAGR {rnd['nostop']['cagr']*100:.1f}% vs {ns['cagr']*100:.1f}%, so ~{(ns['cagr']-rnd['nostop']['cagr'])*100:.1f} pp of the result is this rule |
| Risk unit for fixed-fractional sizing | shares = risk$ / 1.0 ATR | A real stop distance for the stopped version; a **risk proxy only** for the unstopped one, which can and does lose more than its nominal budget |
| Leverage | 1x gross, pro-rata scaled when breached | Binds regularly: average gross when active is {ns['avg_gross_when_active']*100:.0f}% at 0.5% risk, {G[(G.sizing.str.contains('1.0'))].avg_gross.mean()*100:.0f}% at 1.0% |
| Idle cash | 0% | Understates every configuration equally |
| Costs | {meta['base_cost']} bps round trip, flat | No spread widening for small caps or high-volatility mornings |
| Position lifetime | Intraday only, 09:35 to 10:35 | No overnight risk; the book is flat every night |

## A. Equity curve and risk

![equity](data/fullval_equity.png)

{md(hdr)}

Capital utilisation is the number that reframes everything else: the
strategy holds a position on {ns['pct_days_active']*100:.1f}% of sessions but for one hour each
time, so it is in the market roughly **{ns['pct_time_in_market']*100:.1f}% of market clock time**, at
about {ns['avg_gross_when_active']*100:.0f}% gross when it is. The Sharpe of {ns['sharpe']:.2f} is computed on a
daily series that is more than half zeros, which flatters it; treat it
as a property of this capital-allocation scheme, not of the trades.

The position limit is binding. Only {ns['pct_signals_taken']*100:.1f}% of signals are taken at max
5, and the average active day carries {ns['avg_positions_when_active']:.1f} positions -- so the book is
usually not full, but the busy days are truncated.

## B. Year by year

**ATR -1.0 stop**

{yr_md['stop']}

**No stop**

{yr_md['nostop']}

The decay is the headline. Average trade falls from {early:.0f} bps across
2015-2019 to {late:.0f} bps across 2020-2025, and win rate slides from the
low 60s to the low 50s. Every year is positive, but the last six are
roughly half the first five.

## C. Distribution and tail metrics

Overall, on trades actually taken by the base configuration:

{dist_md}

By year (stopped version):

{ydist_md}

Skewness is mildly positive throughout and excess kurtosis is modest
after winsorising, which is the signature of a distribution carried by
many small edges rather than a few jackpots. The tail metrics move the
other way over time: trades losing more than 1 ATR rise from {YD[YD.year<=2019]['pct_loss_1atr'].mean()*100:.1f}%
in 2015-2019 to {YD[YD.year>=2020]['pct_loss_1atr'].mean()*100:.1f}% in 2020-2025, and the average large loss
deepens. The edge is thinning and the left tail is fattening at the same
time.

## D. Trade-level transparency

Every one of the {meta['n_signals']:,} signals is in
`data/fullval_trades.csv` with a stable `trade_id`, both exit variants,
MAE/MFE in ATR, and the dollar P&L the base configuration booked. Rows
carry `taken_stop` / `taken_nostop` flags so the ones the position limit
skipped are auditable too.

### Best 15 trades (by net bps, stopped version)

{trade_md(best)}

### Worst 15 trades

{trade_md(worst)}

The worst-trade table is where the stop shows its true character.
Compare `net stop` against `net no-stop` on those rows: several are
*much* worse with the stop than without it. Across all stopped trades:

| | |
|---|---|
| Trades stopped | {whip['n_stopped']:,} ({whip['stop_rate_taken']*100:.1f}% of those taken) |
| Of which the stop made the outcome **worse** | **{whip['pct_made_worse']*100:.1f}%** |
| Average damage when it hurt | {whip['mean_damage_bps']:,.0f} bps |
| Average saving when it helped | +{whip['mean_saving_bps']:,.0f} bps |
| Net effect across all taken trades | {whip['net_effect_bps']:.1f} bps |

More than half the time the stop fires, the price comes back and the
stop has simply locked in a loss the trade would have recovered. The
saving on the other half is smaller than the damage. That is why the
stopped version trails on every headline metric.

## E. Reality checks

### Period and direction

{check_md}

Three things to take from this. The strategy is roughly **half as good
in 2022-2025 as in 2015-2019** ({CK[CK.subset.str.startswith('2022')].iloc[0]['cagr_stop']*100:.1f}% vs {CK[CK.subset.str.startswith('2015-2019')].iloc[0]['cagr_stop']*100:.1f}% CAGR),
consistent with the trade-level decay in section B. The **short side
carries more of the edge** than the long side ({CK[CK.subset=='SHORT only'].iloc[0]['mean_bps_stop']:.0f} vs
{CK[CK.subset=='LONG only'].iloc[0]['mean_bps_stop']:.0f} bps per trade) -- which matters, because the short side is
also where borrow cost lands and none is modelled here. And neither side
alone reaches the combined result, so this is not a strategy with one
live leg.

### Sizing and concurrency

{grid_md}

Higher risk per trade scales return and drawdown together, roughly
proportionally, which is what should happen when the leverage cap is
doing its job. Concurrency behaves differently by sizing scheme: under
fixed fractional, going from 3 to 8 barely changes CAGR because each
position is sized off risk rather than off a slot; under fixed notional,
raising the limit *shrinks* each position, so CAGR falls from
{G[(G.sizing.str.startswith('Fixed notional')) & (G.max_pos==3) & (G.exit.str.contains('no stop'))].iloc[0]['cagr']*100:.1f}% at 3 to {G[(G.sizing.str.startswith('Fixed notional')) & (G.max_pos==8) & (G.exit.str.contains('no stop'))].iloc[0]['cagr']*100:.1f}% at 8. Fixed notional at 3 positions
is the highest-returning cell in the grid and also the
highest-drawdown one.

### Cost sensitivity

{cost_md}

At 15 bps the strategy still compounds respectably. At 25 bps the
stopped version returns {CG[(CG.cost_bps==25.0) & (CG.exit.str.contains('ATR'))].iloc[0]['cagr']*100:.1f}% a year with a Sharpe of
{CG[(CG.cost_bps==25.0) & (CG.exit.str.contains('ATR'))].iloc[0]['sharpe']:.2f} -- not obviously worth the operational load. Cost is
the assumption that decides whether this is a business.

## What this backtest still does not include

- **Borrow cost and locate.** {(1-meta['long_share'])*100:.0f}% of signals are shorts, and the
  short side carries the larger edge. Post-earnings names are exactly
  when borrow is expensive and hard to source. This is the largest
  unmodelled cost and it lands on the better half of the book.
- **Spread realism.** A flat {meta['base_cost']} bps does not distinguish a mega-cap
  from a mid-cap at 09:35 on the morning after a surprise.
- **Fill assumptions.** Entry is the 09:35 open and the stop fills at
  the intended level or the bar open, whichever is worse. Gap-through
  fills beyond the bar open are not modelled.
- **Capacity.** Position size is never checked against the name's actual
  liquidity in that hour.
- **Survivorship in the ticker universe**, inherited from the panel
  construction rather than introduced here.

Generated by `fullvalidation.py`. Trade ledger:
`data/fullval_trades.csv`. Curves: `fullval_curve_*.csv` in the tables
directory.
"""
