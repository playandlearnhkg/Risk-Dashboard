"""
margin_debt.py — FINRA margin statistics loading and analysis.
==============================================================

FINRA publishes margin statistics MONTHLY, roughly three to four weeks after
month end, at:

    https://www.finra.org/investors/insights/investing/margin-statistics

There is no free API, so this module reads a small CSV you maintain by hand
(data/margin_debt.csv). The app also lets you edit the table in the browser
and download the updated CSV, so you never have to open a text editor.

CSV schema
----------
    month                 YYYY-MM-01 (first of the month the figure refers to)
    debit_balances_musd   Debit balances in customers' securities margin
                          accounts, in MILLIONS of USD (FINRA's own unit)
    free_credit_cash_musd Free credit balances in customers' cash accounts
    free_credit_margin_musd
                          Free credit balances in customers' securities
                          margin accounts
    is_placeholder        TRUE/FALSE. Any TRUE row is example data. While ANY
                          row is a placeholder the leverage component is
                          EXCLUDED from the risk score and the UI says so.

Leaving `is_placeholder` TRUE is safe: the dashboard simply re-weights the
remaining risk components. It will never quietly score fabricated numbers.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

import config

DATA_DIR = Path(__file__).parent / "data"
CSV_PATH = DATA_DIR / "margin_debt.csv"

COLUMNS = [
    "month",
    "debit_balances_musd",
    "free_credit_cash_musd",
    "free_credit_margin_musd",
    "is_placeholder",
]


@dataclass
class MarginStats:
    """Everything the UI and the scorer need to know about leverage."""
    frame: pd.DataFrame            # full history, month-indexed
    latest_month: Optional[pd.Timestamp]
    latest_debit_musd: Optional[float]
    yoy_pct: Optional[float]           # year-over-year % change
    mom_pct: Optional[float]           # month-over-month % change
    pct_of_peak: Optional[float]       # 100 = at the all-time high
    peak_month: Optional[pd.Timestamp]
    net_credit_musd: Optional[float]   # free credit minus debit; negative =
                                       # investors are net borrowers
    pct_of_spx_mktcap: Optional[float]
    is_placeholder: bool               # True -> excluded from the risk score

    @property
    def usable(self) -> bool:
        """Only real data feeds the risk score."""
        return (not self.is_placeholder) and self.latest_debit_musd is not None


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNS)


@st.cache_data(ttl=60, show_spinner=False)
def load_csv(path_str: str) -> pd.DataFrame:
    """Read the margin debt CSV. Returns an empty frame if it is missing."""
    path = Path(path_str)
    if not path.exists():
        return _empty_frame()
    try:
        df = pd.read_csv(path, comment="#")
    except Exception:
        return _empty_frame()
    return _clean(df)


def parse_uploaded(buffer) -> pd.DataFrame:
    """Parse a user-uploaded CSV (same schema). Returns empty frame on error."""
    try:
        df = pd.read_csv(buffer, comment="#")
    except Exception:
        return _empty_frame()
    return _clean(df)


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce whatever we were given into the expected schema and dtypes."""
    if df is None or df.empty:
        return _empty_frame()

    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    if "month" not in df.columns:
        return _empty_frame()

    for col in COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA

    df["month"] = pd.to_datetime(df["month"], errors="coerce")
    for col in ("debit_balances_musd", "free_credit_cash_musd", "free_credit_margin_musd"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Accept TRUE/true/1/yes for the placeholder flag.
    df["is_placeholder"] = (
        df["is_placeholder"]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(["true", "1", "yes", "y"])
    )

    df = df.dropna(subset=["month"]).sort_values("month").reset_index(drop=True)
    return df[COLUMNS]


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Serialise the editable table back to CSV for download."""
    out = df.copy()
    if "month" in out.columns:
        out["month"] = pd.to_datetime(out["month"], errors="coerce").dt.strftime("%Y-%m-01")
    buf = io.StringIO()
    buf.write("# FINRA margin statistics. Units: millions of USD.\n")
    buf.write("# Source: https://www.finra.org/investors/insights/investing/margin-statistics\n")
    buf.write("# Set is_placeholder to FALSE once you have entered real figures.\n")
    out.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def analyse(df: pd.DataFrame, spx_level: Optional[float]) -> MarginStats:
    """
    Turn the raw monthly table into the derived leverage metrics.

    `spx_level` is the current S&P 500 index level, used with
    config.SP500_DIVISOR_BN to approximate index market cap.
    """
    if df is None or df.empty or df["debit_balances_musd"].dropna().empty:
        return MarginStats(
            frame=_empty_frame(), latest_month=None, latest_debit_musd=None,
            yoy_pct=None, mom_pct=None, pct_of_peak=None, peak_month=None,
            net_credit_musd=None, pct_of_spx_mktcap=None, is_placeholder=True,
        )

    d = df.dropna(subset=["debit_balances_musd"]).copy()
    d = d.sort_values("month").set_index("month")
    debit = d["debit_balances_musd"]

    latest_month = debit.index[-1]
    latest = float(debit.iloc[-1])

    # Year-over-year: compare against the observation closest to 12 months back
    # rather than assuming exactly 12 rows, so gaps in the table are tolerated.
    yoy = _pct_change_at_offset(debit, months=12)
    mom = _pct_change_at_offset(debit, months=1)

    peak = float(debit.max())
    peak_month = debit.idxmax()
    pct_of_peak = (latest / peak * 100.0) if peak else None

    # Net credit: free credit balances minus margin debt. Persistently negative
    # (investors owe more than their idle cash) is the leveraged state.
    credits = (
        d["free_credit_cash_musd"].fillna(0) + d["free_credit_margin_musd"].fillna(0)
    )
    has_credit = d[["free_credit_cash_musd", "free_credit_margin_musd"]].notna().any(axis=1)
    net_credit = float(credits.iloc[-1] - latest) if bool(has_credit.iloc[-1]) else None

    # Margin debt as a share of approximate S&P 500 market cap.
    # debit is in $mn; market cap = index level x divisor ($bn per point).
    pct_mktcap = None
    if spx_level:
        mktcap_musd = spx_level * config.SP500_DIVISOR_BN * 1_000.0  # $bn -> $mn
        if mktcap_musd > 0:
            pct_mktcap = latest / mktcap_musd * 100.0

    return MarginStats(
        frame=d.reset_index(),
        latest_month=latest_month,
        latest_debit_musd=latest,
        yoy_pct=yoy,
        mom_pct=mom,
        pct_of_peak=pct_of_peak,
        peak_month=peak_month,
        net_credit_musd=net_credit,
        pct_of_spx_mktcap=pct_mktcap,
        is_placeholder=bool(df["is_placeholder"].any()),
    )


def _pct_change_at_offset(series: pd.Series, months: int) -> Optional[float]:
    """Percent change vs the observation nearest `months` ago."""
    if series is None or len(series) < 2:
        return None
    target = series.index[-1] - pd.DateOffset(months=months)
    prior = series.loc[:target]
    if prior.empty:
        return None
    base = float(prior.iloc[-1])
    if base == 0:
        return None
    return (float(series.iloc[-1]) / base - 1.0) * 100.0
