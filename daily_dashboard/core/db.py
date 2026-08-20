"""
core/db.py — SQLite schema and access helpers.
==============================================

All Layer 1 tables live here so the schema is readable in one place rather
than scattered across ten ingest modules.

Design notes:
  * WAL journal mode, so a long ingest does not block the dashboard reading.
  * Every table has an explicit PRIMARY KEY chosen to make re-ingest
    idempotent -- rerunning a fetch UPSERTs rather than duplicating.
  * Snapshot tables (estimates, short interest) key on (ticker, snapshot_date)
    because their whole purpose is to accumulate history the vendor does not
    give you. Layer 2's revisions factor is built from these snapshots, so a
    row must never be overwritten with a later value under the same date.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

SCHEMA = """
-- ---------------------------------------------------------------- universe
CREATE TABLE IF NOT EXISTS universe (
    ticker        TEXT PRIMARY KEY,
    company_name  TEXT,
    gics_sector   TEXT,
    sub_industry  TEXT,
    is_constituent INTEGER DEFAULT 1,   -- 0 once dropped from the index
    kind          TEXT DEFAULT 'equity', -- equity | benchmark | sector_etf | regime
    first_seen    TEXT,
    last_seen     TEXT
);
CREATE INDEX IF NOT EXISTS ix_universe_sector ON universe(gics_sector);
CREATE INDEX IF NOT EXISTS ix_universe_kind   ON universe(kind);

-- ------------------------------------------------------------ daily prices
CREATE TABLE IF NOT EXISTS daily_prices (
    ticker    TEXT NOT NULL,
    date      TEXT NOT NULL,
    open      REAL,
    high      REAL,
    low       REAL,
    close     REAL,
    adj_close REAL,
    volume    REAL,
    PRIMARY KEY (ticker, date)
);
CREATE INDEX IF NOT EXISTS ix_prices_date ON daily_prices(date);

-- ------------------------------------------------------------- fundamentals
-- Long/narrow rather than one column per line item: vendors rename and add
-- fields constantly, and a wide table means a schema migration every time.
CREATE TABLE IF NOT EXISTS fundamentals (
    ticker      TEXT NOT NULL,
    period      TEXT NOT NULL,     -- 'quarterly' | 'annual'
    period_end  TEXT NOT NULL,
    statement   TEXT NOT NULL,     -- 'income' | 'balance' | 'cashflow'
    item        TEXT NOT NULL,
    value       REAL,
    fetched_at  TEXT,
    PRIMARY KEY (ticker, period, period_end, statement, item)
);
CREATE INDEX IF NOT EXISTS ix_fund_ticker ON fundamentals(ticker, period);

-- The 24 derived ratios, one row per ticker/period-end.
CREATE TABLE IF NOT EXISTS fundamental_ratios (
    ticker              TEXT NOT NULL,
    period              TEXT NOT NULL,
    period_end          TEXT NOT NULL,
    roe                 REAL,
    roa                 REAL,
    gross_margin        REAL,
    operating_margin    REAL,
    net_margin          REAL,
    revenue_growth_yoy  REAL,
    revenue_growth_qoq  REAL,
    earnings_growth_yoy REAL,
    earnings_growth_qoq REAL,
    debt_to_equity      REAL,
    fcf_yield           REAL,
    current_ratio       REAL,
    ar_to_revenue       REAL,
    cfo_to_ni           REAL,
    accruals_ratio      REAL,
    retained_earnings   REAL,
    working_capital     REAL,
    total_liabilities   REAL,
    ebit                REAL,
    rd_expense          REAL,
    shares_outstanding  REAL,
    dividends_paid      REAL,
    buybacks            REAL,
    asset_turnover      REAL,
    computed_at         TEXT,
    PRIMARY KEY (ticker, period, period_end)
);

-- ------------------------------------------------------------- SEC filings
CREATE TABLE IF NOT EXISTS filings (
    accession    TEXT PRIMARY KEY,
    ticker       TEXT NOT NULL,
    cik          TEXT,
    form         TEXT,
    filed_date   TEXT,
    period       TEXT,
    primary_doc  TEXT,
    url          TEXT,
    fetched_at   TEXT
);
CREATE INDEX IF NOT EXISTS ix_filings_ticker ON filings(ticker, form, filed_date);

-- Extracted narrative sections (Risk Factors, MD&A) for Layer 3.
CREATE TABLE IF NOT EXISTS filing_sections (
    accession   TEXT NOT NULL,
    section     TEXT NOT NULL,     -- 'risk_factors' | 'mdna'
    content     TEXT,
    char_count  INTEGER,
    PRIMARY KEY (accession, section)
);

CREATE TABLE IF NOT EXISTS insider_transactions (
    accession       TEXT NOT NULL,
    ticker          TEXT NOT NULL,
    insider_name    TEXT,
    insider_title   TEXT,
    is_senior       INTEGER DEFAULT 0,   -- CEO/CFO/President/Chairman
    is_director     INTEGER DEFAULT 0,
    transaction_date TEXT,
    code            TEXT,                -- P, S, A, M, F ...
    is_signal       INTEGER DEFAULT 0,   -- 1 only for open-market P and S
    shares          REAL,
    price           REAL,
    value_usd       REAL,
    shares_after    REAL,
    filed_date      TEXT,
    PRIMARY KEY (accession, insider_name, transaction_date, code, shares, price)
);
CREATE INDEX IF NOT EXISTS ix_insider_ticker ON insider_transactions(ticker, transaction_date);

-- ------------------------------------------------------ institutional 13-F
CREATE TABLE IF NOT EXISTS institutional_holdings (
    fund_cik     TEXT NOT NULL,
    fund_name    TEXT,
    ticker       TEXT NOT NULL,
    cusip        TEXT,
    report_date  TEXT NOT NULL,
    shares       REAL,
    value_usd    REAL,
    PRIMARY KEY (fund_cik, ticker, report_date)
);
CREATE INDEX IF NOT EXISTS ix_inst_ticker ON institutional_holdings(ticker, report_date);

-- --------------------------------------------------------- market snapshots
CREATE TABLE IF NOT EXISTS short_interest (
    ticker                 TEXT NOT NULL,
    snapshot_date          TEXT NOT NULL,
    shares_short           REAL,
    short_ratio            REAL,
    short_percent_of_float REAL,
    PRIMARY KEY (ticker, snapshot_date)
);

CREATE TABLE IF NOT EXISTS analyst_estimates (
    ticker            TEXT NOT NULL,
    snapshot_date     TEXT NOT NULL,
    forward_eps       REAL,
    forward_pe        REAL,
    target_mean       REAL,
    target_high       REAL,
    target_low        REAL,
    analyst_count     INTEGER,
    PRIMARY KEY (ticker, snapshot_date)
);

CREATE TABLE IF NOT EXISTS earnings_calendar (
    ticker        TEXT NOT NULL,
    earnings_date TEXT NOT NULL,
    eps_estimate  REAL,
    is_confirmed  INTEGER DEFAULT 0,
    fetched_at    TEXT,
    PRIMARY KEY (ticker, earnings_date)
);

CREATE TABLE IF NOT EXISTS transcripts (
    ticker      TEXT NOT NULL,
    period      TEXT NOT NULL,
    call_date   TEXT,
    content     TEXT,
    PRIMARY KEY (ticker, period)
);

-- ------------------------------------------------------------ Layer 0 state
-- Every regime run is appended, never replaced: the history is what lets you
-- see the regime deteriorating over weeks rather than only its level today.
CREATE TABLE IF NOT EXISTS regime_history (
    run_date        TEXT PRIMARY KEY,
    composite_score REAL,
    regime_label    TEXT,
    money_score     REAL,
    behavior_score  REAL,
    capital_status  TEXT,
    detail_json     TEXT,
    created_at      TEXT
);

CREATE TABLE IF NOT EXISTS weekly_process_log (
    step_id      TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    notes        TEXT,
    PRIMARY KEY (step_id, completed_at)
);

-- --------------------------------------------------------------- run audit
CREATE TABLE IF NOT EXISTS ingest_log (
    run_id      TEXT NOT NULL,
    stage       TEXT NOT NULL,
    status      TEXT,
    rows        INTEGER,
    message     TEXT,
    started_at  TEXT,
    finished_at TEXT,
    PRIMARY KEY (run_id, stage)
);
"""


class Database:
    """Thin SQLite wrapper. Not an ORM on purpose -- the queries stay visible."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # WAL lets the dashboard read while an ingest writes.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # -- writes ------------------------------------------------------------

    def upsert_many(self, table: str, columns: Sequence[str],
                    rows: Iterable[Sequence[Any]]) -> int:
        """
        Insert-or-replace a batch. Returns the number of rows written.

        REPLACE rather than INSERT OR IGNORE: a re-fetch should refresh a row
        (vendors restate), and every table's primary key is chosen so that
        replacing is the correct behaviour.
        """
        rows = list(rows)
        if not rows:
            return 0
        placeholders = ",".join("?" * len(columns))
        sql = (f"INSERT OR REPLACE INTO {table} ({','.join(columns)}) "
               f"VALUES ({placeholders})")
        with self.connect() as conn:
            conn.executemany(sql, rows)
        return len(rows)

    def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        with self.connect() as conn:
            conn.execute(sql, params)

    # -- reads -------------------------------------------------------------

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(sql, params).fetchall()

    def scalar(self, sql: str, params: Sequence[Any] = ()) -> Any:
        rows = self.query(sql, params)
        return rows[0][0] if rows else None

    def last_price_date(self, ticker: str) -> str | None:
        """Newest stored date for a ticker — drives incremental fetching."""
        return self.scalar(
            "SELECT MAX(date) FROM daily_prices WHERE ticker = ?", (ticker,)
        )

    def table_count(self, table: str) -> int:
        return int(self.scalar(f"SELECT COUNT(*) FROM {table}") or 0)

    def counts(self) -> dict[str, int]:
        """Row counts for the run summary."""
        tables = [
            "universe", "daily_prices", "fundamentals", "fundamental_ratios",
            "filings", "filing_sections", "insider_transactions",
            "institutional_holdings", "short_interest", "analyst_estimates",
            "earnings_calendar", "transcripts", "regime_history",
        ]
        out: dict[str, int] = {}
        for t in tables:
            try:
                out[t] = self.table_count(t)
            except sqlite3.Error:
                out[t] = -1
        return out
