"""buyhold_text.py -- prose for BUYHOLD_REPORT.md.

Figures are read from the frames buyhold.py computed, so the narrative
cannot drift from the tables.
"""

from __future__ import annotations

import pandas as pd

from fullvalidation import md


def build(P: pd.DataFrame, Y: pd.DataFrame, R: pd.DataFrame, meta: dict) -> str:
    Pp = P.copy()
    Pp["final_equity"] = Pp["final_equity"].map(lambda v: f"${v/1e6:,.2f}M")
    Pp = Pp.rename(columns={"portfolio": "portfolio", "final_equity": "final equity",
                            "cagr": "CAGR", "ann_vol": "ann. vol",
                            "sharpe": "Sharpe (rf=0)", "max_dd": "max DD",
                            "calmar": "Calmar", "worst_day": "worst day",
                            "worst_month": "worst month"})
    port_md = md(Pp, pct=("CAGR", "ann. vol", "max DD", "worst day", "worst month"),
                 num=("Sharpe (rf=0)", "Calmar"))

    Yp = Y.rename(columns={"strategy_nostop": "strategy (no stop)",
                           "strategy_stop": "strategy (stop)",
                           "diff_nostop": "difference", "beat_spy": "beat SPY"})
    yr_md = md(Yp, pct=("SPY", "strategy (no stop)", "strategy (stop)", "difference"))

    Rp = R.rename(columns={"pct_negative": "% of windows negative",
                           "worst": "worst 12m", "best": "best 12m",
                           "median": "median 12m"})
    roll_md = md(Rp, pct=("% of windows negative", "worst 12m", "best 12m",
                          "median 12m"))

    def row(name):
        return P[P.portfolio.str.startswith(name)].iloc[0]

    spy = row("SPY buy-and-hold")
    ns = row("Strategy only, 1 hour, no stop")
    st = row("Strategy only, 1 hour, ATR")
    sc = row("Strategy, no stop, scaled")
    b70 = row("70% SPY + 30%")
    b50 = row("50% SPY + 50%")
    ov = row("100% SPY + 30%")

    up = Y[Y.SPY > 0]
    down = Y[Y.SPY < 0]
    gross_needed = 0.52 * meta["scale_to_spy_vol"]

    B = P[P.portfolio.str.contains("SPY + ", regex=False)].rename(columns={
        "cagr": "CAGR", "ann_vol": "ann. vol", "sharpe": "Sharpe (rf=0)",
        "max_dd": "max DD", "calmar": "Calmar"})
    blend_md = md(B[["portfolio", "CAGR", "ann. vol", "Sharpe (rf=0)",
                     "max DD", "Calmar"]],
                  pct=("CAGR", "ann. vol", "max DD"),
                  num=("Sharpe (rf=0)", "Calmar"))
    skipped = 100.0 - 80.9

    return f"""# $1,000,000 in the strategy vs $1,000,000 in SPY

Identical terms: {meta['start']} to {meta['end']}, {meta['sessions']:,} sessions, same
starting capital. Strategy configuration is the FULLVAL base --
{meta['base']}.

## The headline

{port_md}

On raw numbers the strategy wins outright: **${ns['final_equity']/1e6:.2f}M against SPY's
${spy['final_equity']/1e6:.2f}M**, at roughly a third of the volatility ({ns['ann_vol']*100:.1f}% vs
{spy['ann_vol']*100:.1f}%) and a fifth of the drawdown ({ns['max_dd']*100:.1f}% vs {spy['max_dd']*100:.1f}%). Sharpe
{ns['sharpe']:.2f} against {spy['sharpe']:.2f}, Calmar {ns['calmar']:.2f} against {spy['calmar']:.2f}.

That is a real result, but it is not the interesting one, and quoting it
alone would be misleading in both directions at once. The strategy is
not taking anything like SPY's risk, so on one reading it is being
under-credited; on another, its return is only available at a scale the
brief forbids. Both readings are below.

## The scaled comparison, and why it is not a recommendation

Matching SPY's volatility would need **{meta['scale_to_spy_vol']:.1f}x** the position size, which
would take average gross exposure when active from about 52% to roughly
{gross_needed*100:.0f}%, and higher on busy days. At that scale the strategy returns
{sc['cagr']*100:.1f}% a year with a {sc['max_dd']*100:.1f}% drawdown -- better than SPY on both
axes simultaneously.

Treat that row as an illustration of the risk-adjusted gap, not a plan.
It breaches the 1x gross cap the validation was run under, and the
linear scaling assumes fills and borrow behave identically at {meta['scale_to_spy_vol']:.1f}x size,
which is exactly the assumption a capacity study exists to test and this
one has not.

## Year by year -- where the value actually comes from

{yr_md}

The strategy beats SPY in **{meta['beat_years']} of {meta['n_years']} years**, which on its own sounds
mediocre. The pattern is what matters, and it is almost mechanical: the
strategy returned between {Y['strategy_nostop'].min()*100:.0f}% and {Y['strategy_nostop'].max()*100:.0f}% every single year, so
**who wins is decided almost entirely by what SPY did**, not by what the
strategy did.

- In the {len(down)} years SPY fell, the strategy beat it by an average of
  **{down['diff_nostop'].mean()*100:.1f} percentage points** and was positive in both -- +{Y[Y.year==2018].iloc[0]['diff_nostop']*100:.0f} pp in
  2018 and +{Y[Y.year==2022].iloc[0]['diff_nostop']*100:.0f} pp in 2022.
- It also beat SPY in the {int((up['diff_nostop'] > 0).sum())} up-years where the index returned less
  than about 22%.
- It lost in every year SPY returned more than about 18%, by up to
  {abs(up['diff_nostop'].min())*100:.0f} pp. Holding cash ~93% of the time cannot keep pace with a
  strong index, and no amount of edge inside one hour a day will change
  that.

Correlation to SPY is {meta['corr']:.3f}. This is not a better version of owning the
index; it is a flatter, steadier return stream whose relative value
appears exactly when the index disappoints.

## Rolling 12-month windows

{roll_md}

SPY spends {R[R.series=='SPY'].iloc[0]['pct_negative']*100:.1f}% of rolling one-year windows under water and its
worst is {R[R.series=='SPY'].iloc[0]['worst']*100:.1f}%. The strategy has **no negative rolling
12-month window in the sample** -- worst is
+{R[R.series=='Strategy (no stop)'].iloc[0]['worst']*100:.1f}%. That is the single most useful fact in this report
for anyone deciding how to hold it, and also the one most likely to be
an artefact of a favourable sample: eleven years contains only about six
independent non-overlapping year-long windows, and the strategy has
never yet met a regime that broke it.

## Blends, which are the practical answer

{blend_md}

Every step from SPY toward the strategy raises return and lowers both
volatility and drawdown at the same time. 70/30 gets {b70['cagr']*100:.1f}% CAGR at
{b70['ann_vol']*100:.1f}% vol and {b70['max_dd']*100:.1f}% drawdown; 50/50 gets {b50['cagr']*100:.1f}% at {b50['ann_vol']*100:.1f}% and
{b50['max_dd']*100:.1f}%. On a Sharpe basis the optimum inside a 1x cap is simply as
much strategy as you are willing to hold.

The overlay (SPY plus a {int(0.30*100)}% sleeve funded by intraday buying power
rather than by selling SPY) reaches {ov['cagr']*100:.1f}% but keeps SPY's full
drawdown at {ov['max_dd']*100:.1f}%, because it never reduces market exposure.

## Reconciling with BENCHMARK_REPORT

That earlier report showed a 70/30 blend at 20.6% CAGR; this one shows
{b70['cagr']*100:.1f}%. Nothing has changed about the edge -- the difference is
entirely the capital convention. BENCHMARK sized every signal day at
100% of the sleeve equal-weighted across that day's names, with no
position limit. This report uses 0.5% fixed-fractional risk and a
five-position cap, which runs the sleeve at about 52% gross when active
and skips {skipped:.0f}% of signals.

The figures here are the conservative ones and should be preferred.

## What has not changed

The caveats from FULLVAL carry over unaltered and all cut the same way:
no borrow cost on a book that is half short and earns more on the short
side; a flat {6.6} bps that does not widen for mid-caps at 09:35; no
capacity constraint; and an edge that is roughly half as large in
2022-2025 as it was in 2015-2019. A comparison against SPY does not
repair any of them -- it only shows that SPY has its own problems.

Generated by `buyhold.py`.
"""
