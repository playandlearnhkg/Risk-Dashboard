"""
data/fundamentals.py — Financial statements and the 24 derived ratios.
======================================================================

Two stages, deliberately separated:

  1. INGEST raw statement line items into `fundamentals` (long format), exactly
     as the provider reported them. No arithmetic, no interpretation.
  2. DERIVE the 24 ratios into `fundamental_ratios`.

The separation matters because vendors rename line items constantly. When a
ratio comes out wrong, keeping the untouched raw values means you can see
whether the vendor changed a label or the ratio maths is broken — you cannot
do that if the only thing stored is the computed output.

THE 24 RATIOS
    Profitability   roe, roa, gross_margin, operating_margin, net_margin
    Growth          revenue_growth_yoy, revenue_growth_qoq,
                    earnings_growth_yoy, earnings_growth_qoq
    Balance sheet   debt_to_equity, current_ratio, working_capital,
                    total_liabilities, retained_earnings
    Cash            fcf_yield, cfo_to_ni, accruals_ratio
    Efficiency      asset_turnover, ar_to_revenue
    Other           ebit, rd_expense, shares_outstanding, dividends_paid,
                    buybacks

Line-item lookup is alias-based (`_pick`). Every vendor spells these
differently and the spelling changes between versions, so each concept carries
a list of candidate labels and the first match wins.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Iterable, Optional

import numpy as np
import pandas as pd

from core.logging_setup import get_logger

log = get_logger("data.fundamentals")


@dataclass
class FundamentalStats:
    tickers_requested: int = 0
    tickers_ingested: int = 0
    tickers_failed: int = 0
    line_items: int = 0
    ratio_rows: int = 0
    failed_tickers: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Line-item aliases
# ---------------------------------------------------------------------------
# Ordered by preference. Matching is case-insensitive and ignores spaces, so
# "Total Revenue", "TotalRevenue" and "total revenue" all resolve.

ALIASES: dict[str, list[str]] = {
    "revenue": ["Total Revenue", "TotalRevenue", "Revenue", "OperatingRevenue"],
    "cogs": ["Cost Of Revenue", "CostOfRevenue", "Cost Of Goods Sold"],
    "gross_profit": ["Gross Profit", "GrossProfit"],
    "operating_income": ["Operating Income", "OperatingIncome",
                         "Total Operating Income As Reported"],
    "net_income": ["Net Income", "NetIncome",
                   "Net Income Common Stockholders",
                   "NetIncomeCommonStockholders",
                   "Net Income From Continuing Operation Net Minority Interest"],
    "ebit": ["EBIT", "Ebit", "Operating Income", "OperatingIncome"],
    "pretax_income": ["Pretax Income", "PretaxIncome", "Income Before Tax"],
    "rd_expense": ["Research And Development", "ResearchAndDevelopment",
                   "Research Development"],
    "interest_expense": ["Interest Expense", "InterestExpense"],

    "total_assets": ["Total Assets", "TotalAssets"],
    "total_liabilities": ["Total Liabilities Net Minority Interest",
                          "TotalLiabilitiesNetMinorityInterest",
                          "Total Liabilities", "TotalLiabilities"],
    "total_equity": ["Total Equity Gross Minority Interest",
                     "Stockholders Equity", "StockholdersEquity",
                     "Total Stockholder Equity", "TotalEquityGrossMinorityInterest"],
    "current_assets": ["Current Assets", "CurrentAssets",
                       "Total Current Assets", "TotalCurrentAssets"],
    "current_liabilities": ["Current Liabilities", "CurrentLiabilities",
                            "Total Current Liabilities", "TotalCurrentLiabilities"],
    "total_debt": ["Total Debt", "TotalDebt"],
    "long_term_debt": ["Long Term Debt", "LongTermDebt"],
    "short_term_debt": ["Current Debt", "CurrentDebt", "Short Long Term Debt"],
    "cash": ["Cash And Cash Equivalents", "CashAndCashEquivalents",
             "Cash Cash Equivalents And Short Term Investments"],
    "receivables": ["Accounts Receivable", "AccountsReceivable",
                    "Receivables", "Net Receivables"],
    "retained_earnings": ["Retained Earnings", "RetainedEarnings"],
    "shares_outstanding": ["Ordinary Shares Number", "OrdinarySharesNumber",
                           "Share Issued", "ShareIssued",
                           "Common Stock Shares Outstanding"],

    "cfo": ["Operating Cash Flow", "OperatingCashFlow",
            "Total Cash From Operating Activities",
            "Cash Flow From Continuing Operating Activities"],
    "capex": ["Capital Expenditure", "CapitalExpenditure", "Capital Expenditures"],
    "free_cash_flow": ["Free Cash Flow", "FreeCashFlow"],
    "dividends_paid": ["Cash Dividends Paid", "CashDividendsPaid",
                       "Dividends Paid", "Common Stock Dividend Paid"],
    "buybacks": ["Repurchase Of Capital Stock", "RepurchaseOfCapitalStock",
                 "Common Stock Payments", "Purchase Of Stock"],
}


def _norm(label: object) -> str:
    return str(label).lower().replace(" ", "").replace("_", "").replace("-", "")


def _pick(frame: Optional[pd.DataFrame], concept: str,
          column) -> Optional[float]:
    """
    Fetch one concept from a statement frame for a given period column.

    Returns None rather than 0.0 when absent: a missing line item and a real
    zero mean different things, and conflating them silently corrupts every
    ratio built on top.
    """
    if frame is None or frame.empty or column not in frame.columns:
        return None

    lookup = {_norm(idx): idx for idx in frame.index}
    for alias in ALIASES.get(concept, []):
        key = _norm(alias)
        if key in lookup:
            value = frame.loc[lookup[key], column]
            if isinstance(value, pd.Series):
                value = value.iloc[0]
            if value is None or (isinstance(value, float) and np.isnan(value)):
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


def _safe_div(num: Optional[float], den: Optional[float]) -> Optional[float]:
    """Division that yields None instead of raising or returning inf."""
    if num is None or den is None or den == 0:
        return None
    try:
        result = num / den
    except (TypeError, ZeroDivisionError):
        return None
    return None if (np.isnan(result) or np.isinf(result)) else float(result)


def _growth(curr: Optional[float], prior: Optional[float]) -> Optional[float]:
    """
    Percent growth, guarded against a negative or zero base.

    Growth off a negative base is not meaningful — a loss shrinking from -100
    to -50 is not "+50% growth" — so those return None rather than a number
    that would rank confidently and wrongly in a percentile.
    """
    if curr is None or prior is None or prior <= 0:
        return None
    return (curr / prior - 1.0) * 100.0


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------

def _statement_rows(ticker: str, period: str, statement: str,
                    frame: pd.DataFrame, fetched_at: str) -> list[tuple]:
    """Flatten a statement frame into long-format rows."""
    rows: list[tuple] = []
    for column in frame.columns:
        try:
            period_end = pd.Timestamp(column).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue
        for item in frame.index:
            value = frame.loc[item, column]
            if isinstance(value, pd.Series):
                value = value.iloc[0]
            if value is None or (isinstance(value, float) and np.isnan(value)):
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            rows.append((ticker, period, period_end, statement,
                         str(item), numeric, fetched_at))
    return rows


def ingest(db, provider, tickers: Iterable[str], cfg) -> FundamentalStats:
    """Fetch statements for each ticker and store raw line items."""
    tickers = list(tickers)
    stats = FundamentalStats(tickers_requested=len(tickers))
    periods = cfg.get("data.fundamentals.periods", ["quarterly", "annual"])
    fetched_at = dt.datetime.now().isoformat(timespec="seconds")

    for i, ticker in enumerate(tickers, 1):
        if i % 50 == 0:
            log.info("  fundamentals %d/%d…", i, len(tickers))

        got_any = False
        for period in periods:
            statements = provider.get_fundamentals(ticker, period=period)
            if not statements:
                continue
            rows: list[tuple] = []
            for statement, frame in statements.items():
                if isinstance(frame, pd.DataFrame) and not frame.empty:
                    rows.extend(_statement_rows(ticker, period, statement,
                                                frame, fetched_at))
            if rows:
                stats.line_items += db.upsert_many(
                    "fundamentals",
                    ["ticker", "period", "period_end", "statement",
                     "item", "value", "fetched_at"],
                    rows,
                )
                got_any = True

        if got_any:
            stats.tickers_ingested += 1
        else:
            stats.tickers_failed += 1
            stats.failed_tickers.append(ticker)

    log.info("Fundamentals: %d line items for %d tickers (%d failed)",
             stats.line_items, stats.tickers_ingested, stats.tickers_failed)
    return stats


# ---------------------------------------------------------------------------
# Derived ratios
# ---------------------------------------------------------------------------

def _load_statements(db, ticker: str, period: str) -> dict[str, pd.DataFrame]:
    """Rebuild statement frames (item x period_end) from the long table."""
    rows = db.query(
        "SELECT period_end, statement, item, value FROM fundamentals "
        "WHERE ticker = ? AND period = ?", (ticker, period),
    )
    if not rows:
        return {}
    df = pd.DataFrame([dict(r) for r in rows])
    out: dict[str, pd.DataFrame] = {}
    for statement, group in df.groupby("statement"):
        pivot = group.pivot_table(index="item", columns="period_end",
                                  values="value", aggfunc="last")
        # Newest period first, matching how providers present statements.
        out[statement] = pivot[sorted(pivot.columns, reverse=True)]
    return out


def compute_ratios_for(db, ticker: str, period: str,
                       market_cap: Optional[float] = None) -> list[dict]:
    """
    Compute the 24 ratios for every stored period-end of one ticker.

    `market_cap` is needed for fcf_yield; when absent that single ratio is
    None and the rest are unaffected.
    """
    statements = _load_statements(db, ticker, period)
    if not statements:
        return []

    income = statements.get("income")
    balance = statements.get("balance")
    cashflow = statements.get("cashflow")

    columns: list[str] = []
    for frame in (income, balance, cashflow):
        if frame is not None:
            columns.extend(str(c) for c in frame.columns)
    period_ends = sorted(set(columns), reverse=True)   # newest first
    if not period_ends:
        return []

    results: list[dict] = []
    for idx, pe in enumerate(period_ends):
        prior_q = period_ends[idx + 1] if idx + 1 < len(period_ends) else None
        # YoY comparison: 4 quarters back for quarterly, 1 period for annual.
        yoy_offset = 4 if period == "quarterly" else 1
        prior_y = (period_ends[idx + yoy_offset]
                   if idx + yoy_offset < len(period_ends) else None)

        revenue = _pick(income, "revenue", pe)
        cogs = _pick(income, "cogs", pe)
        gross_profit = _pick(income, "gross_profit", pe)
        if gross_profit is None and revenue is not None and cogs is not None:
            gross_profit = revenue - cogs
        operating_income = _pick(income, "operating_income", pe)
        net_income = _pick(income, "net_income", pe)
        ebit = _pick(income, "ebit", pe) or operating_income
        rd_expense = _pick(income, "rd_expense", pe)

        total_assets = _pick(balance, "total_assets", pe)
        total_liabilities = _pick(balance, "total_liabilities", pe)
        total_equity = _pick(balance, "total_equity", pe)
        if total_equity is None and total_assets is not None and total_liabilities is not None:
            total_equity = total_assets - total_liabilities
        current_assets = _pick(balance, "current_assets", pe)
        current_liabilities = _pick(balance, "current_liabilities", pe)
        total_debt = _pick(balance, "total_debt", pe)
        if total_debt is None:
            lt = _pick(balance, "long_term_debt", pe)
            st = _pick(balance, "short_term_debt", pe)
            total_debt = (lt or 0) + (st or 0) if (lt is not None or st is not None) else None
        receivables = _pick(balance, "receivables", pe)
        retained_earnings = _pick(balance, "retained_earnings", pe)
        shares_outstanding = _pick(balance, "shares_outstanding", pe)

        cfo = _pick(cashflow, "cfo", pe)
        capex = _pick(cashflow, "capex", pe)
        fcf = _pick(cashflow, "free_cash_flow", pe)
        if fcf is None and cfo is not None and capex is not None:
            # capex is reported negative by most vendors; adding is correct.
            fcf = cfo + capex
        dividends_paid = _pick(cashflow, "dividends_paid", pe)
        buybacks = _pick(cashflow, "buybacks", pe)

        prior_revenue_q = _pick(income, "revenue", prior_q) if prior_q else None
        prior_revenue_y = _pick(income, "revenue", prior_y) if prior_y else None
        prior_ni_q = _pick(income, "net_income", prior_q) if prior_q else None
        prior_ni_y = _pick(income, "net_income", prior_y) if prior_y else None

        working_capital = (current_assets - current_liabilities) \
            if (current_assets is not None and current_liabilities is not None) else None

        # Accruals = (NI - CFO) / TA. High positive accruals mean earnings are
        # not backed by cash, which is one of the most durable negative
        # predictors in the literature. Layer 2 inverts this.
        accruals_ratio = None
        if net_income is not None and cfo is not None and total_assets:
            accruals_ratio = (net_income - cfo) / total_assets

        results.append({
            "ticker": ticker, "period": period, "period_end": pe,
            "roe": _mult100(_safe_div(net_income, total_equity)),
            "roa": _mult100(_safe_div(net_income, total_assets)),
            "gross_margin": _mult100(_safe_div(gross_profit, revenue)),
            "operating_margin": _mult100(_safe_div(operating_income, revenue)),
            "net_margin": _mult100(_safe_div(net_income, revenue)),
            "revenue_growth_yoy": _growth(revenue, prior_revenue_y),
            "revenue_growth_qoq": _growth(revenue, prior_revenue_q),
            "earnings_growth_yoy": _growth(net_income, prior_ni_y),
            "earnings_growth_qoq": _growth(net_income, prior_ni_q),
            "debt_to_equity": _safe_div(total_debt, total_equity),
            "fcf_yield": _mult100(_safe_div(fcf, market_cap)) if market_cap else None,
            "current_ratio": _safe_div(current_assets, current_liabilities),
            "ar_to_revenue": _safe_div(receivables, revenue),
            "cfo_to_ni": _safe_div(cfo, net_income),
            "accruals_ratio": accruals_ratio,
            "retained_earnings": retained_earnings,
            "working_capital": working_capital,
            "total_liabilities": total_liabilities,
            "ebit": ebit,
            "rd_expense": rd_expense,
            "shares_outstanding": shares_outstanding,
            "dividends_paid": dividends_paid,
            "buybacks": buybacks,
            "asset_turnover": _safe_div(revenue, total_assets),
        })
    return results


def _mult100(value: Optional[float]) -> Optional[float]:
    return None if value is None else value * 100.0


RATIO_COLUMNS = [
    "ticker", "period", "period_end", "roe", "roa", "gross_margin",
    "operating_margin", "net_margin", "revenue_growth_yoy", "revenue_growth_qoq",
    "earnings_growth_yoy", "earnings_growth_qoq", "debt_to_equity", "fcf_yield",
    "current_ratio", "ar_to_revenue", "cfo_to_ni", "accruals_ratio",
    "retained_earnings", "working_capital", "total_liabilities", "ebit",
    "rd_expense", "shares_outstanding", "dividends_paid", "buybacks",
    "asset_turnover", "computed_at",
]


def compute_all_ratios(db, tickers: Iterable[str], cfg,
                       market_caps: Optional[dict[str, float]] = None) -> int:
    """Compute and store ratios for every ticker/period. Returns rows written."""
    tickers = list(tickers)
    periods = cfg.get("data.fundamentals.periods", ["quarterly", "annual"])
    market_caps = market_caps or {}
    computed_at = dt.datetime.now().isoformat(timespec="seconds")

    total = 0
    for i, ticker in enumerate(tickers, 1):
        if i % 100 == 0:
            log.info("  ratios %d/%d…", i, len(tickers))
        rows: list[tuple] = []
        for period in periods:
            for record in compute_ratios_for(db, ticker, period,
                                             market_caps.get(ticker)):
                record["computed_at"] = computed_at
                rows.append(tuple(record.get(c) for c in RATIO_COLUMNS))
        if rows:
            total += db.upsert_many("fundamental_ratios", RATIO_COLUMNS, rows)

    log.info("Computed %d ratio rows", total)
    return total


def market_caps(db, period: str = "quarterly") -> dict[str, float]:
    """
    Latest shares outstanding x latest close, per ticker.

    Reads shares outstanding from the RAW `fundamentals` table, NOT from
    `fundamental_ratios`.

    That distinction is the whole point of this function. Ratios are computed
    *after* market caps are needed — `compute_all_ratios` takes them as an
    argument — so on a first run `fundamental_ratios` is still empty, every
    lookup misses, and `fcf_yield` comes out NULL for the entire universe
    while the run reports success. The raw table is populated one stage
    earlier and is always available by the time this is called.
    """
    # The raw `item` label is whatever the provider called it, so match on
    # the same alias list the ratio code uses.
    aliases = ALIASES.get("shares_outstanding", [])
    if not aliases:
        return {}
    placeholders = ",".join("?" * len(aliases))

    rows = db.query(
        f"""
        SELECT f.ticker, f.value AS shares, p.close AS close
        FROM fundamentals f
        JOIN (
            SELECT ticker, MAX(period_end) AS pe
            FROM fundamentals
            WHERE period = ? AND item IN ({placeholders}) AND value > 0
            GROUP BY ticker
        ) latest ON latest.ticker = f.ticker AND latest.pe = f.period_end
        JOIN (
            SELECT ticker, MAX(date) AS d FROM daily_prices GROUP BY ticker
        ) lp ON lp.ticker = f.ticker
        JOIN daily_prices p ON p.ticker = lp.ticker AND p.date = lp.d
        WHERE f.period = ? AND f.item IN ({placeholders}) AND f.value > 0
        """,
        (period, *aliases, period, *aliases),
    )

    caps: dict[str, float] = {}
    for r in rows:
        shares, close = r["shares"], r["close"]
        if shares and close and shares > 0 and close > 0:
            # Several aliases can match the same period; keep the largest,
            # which is the total share count rather than a single class.
            caps[r["ticker"]] = max(caps.get(r["ticker"], 0.0), float(shares) * float(close))
    return caps


def get_latest_ratios(db, period: str = "quarterly") -> pd.DataFrame:
    """Most recent ratio row per ticker — the shape Layer 2 consumes."""
    rows = db.query(
        "SELECT r.* FROM fundamental_ratios r "
        "JOIN (SELECT ticker, MAX(period_end) AS pe FROM fundamental_ratios "
        "      WHERE period = ? GROUP BY ticker) latest "
        "  ON r.ticker = latest.ticker AND r.period_end = latest.pe "
        "WHERE r.period = ?", (period, period),
    )
    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()


def get_ratio_history(db, ticker: str, period: str = "quarterly",
                      limit: int = 20) -> pd.DataFrame:
    """
    Ratio history oldest-first.

    Layer 2's trend sub-factors (gross-margin trend, ROE stability, revenue
    growth acceleration, Piotroski's rising/falling tests) all need this.
    """
    rows = db.query(
        "SELECT * FROM fundamental_ratios WHERE ticker = ? AND period = ? "
        "ORDER BY period_end DESC LIMIT ?", (ticker, period, limit),
    )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([dict(r) for r in rows]).iloc[::-1].reset_index(drop=True)
