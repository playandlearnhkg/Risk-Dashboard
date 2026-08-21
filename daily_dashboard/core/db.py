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


def _insider_table_ddl(name: str = "insider_transactions") -> str:
    """
    DDL for `insider_transactions`, parameterised by table name.

    Named rather than inlined because the primary-key migration has to build
    this table a second time under a temporary name, and two copies of a
    fifteen-column DDL is exactly how a migration ends up writing a table that
    does not match the schema.

    ON line_no. It is the transaction's position within its Form 4 document,
    and it is part of the key on purpose. A single Form 4 legitimately reports
    the same (date, code, shares, price) more than once -- a sale executed in
    several fills at one price, or an award split across plans, is filed as
    separate rows. Under the previous key those rows collided and INSERT OR
    REPLACE silently collapsed them into one, understating both the share
    count and the dollar flow. Observed as 153 parsed but 152 stored.
    """
    return f"""
CREATE TABLE IF NOT EXISTS {name} (
    accession       TEXT NOT NULL,
    line_no         INTEGER NOT NULL DEFAULT 0,
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
    PRIMARY KEY (accession, line_no)
);"""


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

{insider_table}
CREATE INDEX IF NOT EXISTS ix_insider_ticker ON insider_transactions(ticker, transaction_date);

-- ------------------------------------------------------ institutional 13-F
-- shares / value_usd hold COMMON STOCK ONLY. Option positions are kept in
-- their own columns so a fund's conviction in the underlying is never
-- conflated with a hedge or a levered bet. See data/institutional.py.
CREATE TABLE IF NOT EXISTS institutional_holdings (
    fund_cik       TEXT NOT NULL,
    fund_name      TEXT,
    ticker         TEXT NOT NULL,
    cusip          TEXT,
    report_date    TEXT NOT NULL,
    shares         REAL,      -- common stock only
    value_usd      REAL,      -- common stock only
    put_value_usd  REAL,      -- notional of PUT positions, informational
    call_value_usd REAL,      -- notional of CALL positions, informational
    other_value_usd REAL,     -- PRN rows (convertible debt), not share counts
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
""".format(insider_table=_insider_table_ddl())


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

    # Columns added after a table first shipped. CREATE TABLE IF NOT EXISTS
    # will not alter an existing table, so a database created before a schema
    # change keeps the old shape and every INSERT naming a new column fails.
    # Each entry is (table, column, SQL type) and is applied idempotently.
    MIGRATIONS: list[tuple[str, str, str]] = [
        ("institutional_holdings", "put_value_usd", "REAL"),
        ("institutional_holdings", "call_value_usd", "REAL"),
        ("institutional_holdings", "other_value_usd", "REAL"),
    ]

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            self._migrate(conn)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """Add any columns missing from an older database, in place."""
        for table, column, coltype in self.MIGRATIONS:
            try:
                existing = {
                    row["name"] for row in
                    conn.execute(f"PRAGMA table_info({table})").fetchall()
                }
            except sqlite3.Error:
                continue                       # table not created yet
            if not existing or column in existing:
                continue
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
            except sqlite3.Error:
                pass                           # raced with another writer

        self._rebuild_insider_table(conn)

    def _rebuild_insider_table(self, conn: sqlite3.Connection) -> None:
        """
        Move `insider_transactions` onto its (accession, line_no) primary key.

        SQLite cannot ALTER a PRIMARY KEY, so an existing database keeps the
        old key -- (accession, insider_name, transaction_date, code, shares,
        price) -- and keeps losing duplicate transaction lines on every
        ingest. The only fix is a table rebuild.

        Rows already in the database were themselves de-duplicated by the old
        key, so lines lost before this migration are gone; re-fetching those
        Form 4s restores them. What this guarantees is that no FUTURE ingest
        drops a line.

        Copy-then-swap, inside an EXPLICIT transaction. Both details matter.
        Python's sqlite3 only opens a transaction for DML, so DDL otherwise
        runs in autocommit and a failure halfway through would leave the
        database with the old table dropped and the new one half-filled. The
        explicit BEGIN makes the whole swap land or not at all. executescript
        is avoided here for the same reason -- it commits before it runs.
        """
        try:
            info = conn.execute(
                "PRAGMA table_info(insider_transactions)").fetchall()
        except sqlite3.Error:
            return
        if not info or any(row["name"] == "line_no" for row in info):
            return                             # fresh table, or already done

        col_list = ",".join(row["name"] for row in info)
        conn.execute("BEGIN")
        try:
            conn.execute(_insider_table_ddl("insider_transactions_new"))
            # ROW_NUMBER over rowid preserves the filing's original row order,
            # so line_no matches the order the parser produced.
            conn.execute(
                f"INSERT INTO insider_transactions_new ({col_list}, line_no) "
                f"SELECT {col_list}, "
                f"ROW_NUMBER() OVER (PARTITION BY accession ORDER BY rowid) - 1 "
                f"FROM insider_transactions"
            )
            conn.execute("DROP INDEX IF EXISTS ix_insider_ticker")
            conn.execute("DROP TABLE insider_transactions")
            conn.execute("ALTER TABLE insider_transactions_new "
                         "RENAME TO insider_transactions")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_insider_ticker "
                         "ON insider_transactions(ticker, transaction_date)")
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise

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
