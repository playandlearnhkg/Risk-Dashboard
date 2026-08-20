"""
data/sec_data.py — SEC EDGAR filings, sections, and Form 4 insider data.
========================================================================

Covers:
    10-K   latest, with Item 1A "Risk Factors" extracted for Layer 3
    10-Q   latest, with Item 2 "MD&A" extracted
    8-K    recent material events
    Form 4 insider transactions over the configured lookback

COMPLIANCE. SEC requires a User-Agent identifying the requester with a working
email and enforces 10 requests/second; this module is capped at 8 (config) and
refuses to start without SEC_USER_AGENT. Getting this wrong gets an IP blocked,
so the limiter is shared across every call in the module rather than per-call.

THE FORM 4 SIGNAL DISTINCTION — the substantive part of this file.
Most Form 4 rows are compensation mechanics, not opinions about value:

    P  open-market PURCHASE   — the insider chose to buy with their own money
    S  open-market SALE       — a decision, though a noisy one (diversification,
                                tax, scheduled 10b5-1 plans all produce sales)
    A  grant / award          — the company gave them shares
    M  option exercise        — converting existing compensation
    F  tax withholding        — shares surrendered to cover tax on a vest
    G  gift, C  conversion, D  disposition to issuer

Only P and S are stored with `is_signal = 1`. Counting an A or an M as
"insider buying" is the single most common way insider data gets misread — a
vesting event is not a vote of confidence. Everything is stored so the raw
record stays auditable, but Layer 2 filters on `is_signal`.

Two flags are computed on top, both configurable:
    is_senior     CEO / CFO / President / Chairman — weighted 3x by Layer 2
    cluster buy   3+ distinct insiders buying within 30 days (see cluster_buys)
"""

from __future__ import annotations

import datetime as dt
import re
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

import pandas as pd

from core.logging_setup import get_logger
from data.providers import RateLimiter

log = get_logger("data.sec")

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{doc}"
TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"


@dataclass
class SECStats:
    tickers_requested: int = 0
    tickers_processed: int = 0
    filings: int = 0
    sections: int = 0
    insider_rows: int = 0
    signal_rows: int = 0
    cluster_flags: int = 0
    failed: list[str] = field(default_factory=list)
    error: str = ""


class SECClient:
    """Rate-limited EDGAR client. One instance per run, shared by all fetchers."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.user_agent = cfg.sec_user_agent()      # raises if unset/invalid
        self.timeout = int(cfg.get("data.timeouts.http_seconds", 20))
        self.limiter = RateLimiter(float(cfg.get("data.rate_limits.sec_edgar_per_sec", 8)))
        self._cik_map: Optional[dict[str, str]] = None
        self._session = None

    @property
    def session(self):
        import requests
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": self.user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Host": "data.sec.gov",
            })
        return self._session

    def _get(self, url: str, as_json: bool = True) -> Any:
        """Rate-limited GET. Returns None on failure rather than raising."""
        self.limiter.wait()
        try:
            headers = {"Host": "www.sec.gov"} if "www.sec.gov" in url else {}
            resp = self.session.get(url, timeout=self.timeout, headers=headers)
            if resp.status_code == 429:
                # Back off hard: SEC escalates to an IP block on repeats.
                log.warning("SEC returned 429 — backing off 10s")
                time.sleep(10)
                return None
            resp.raise_for_status()
            return resp.json() if as_json else resp.text
        except Exception as exc:                       # noqa: BLE001
            log.debug("SEC GET failed %s: %s", url, exc)
            return None

    # -- CIK resolution ----------------------------------------------------

    def cik_for(self, ticker: str) -> Optional[str]:
        """Ticker -> zero-padded 10-digit CIK, from SEC's own mapping file."""
        if self._cik_map is None:
            payload = self._get(TICKER_MAP_URL)
            self._cik_map = {}
            if isinstance(payload, dict):
                for entry in payload.values():
                    sym = str(entry.get("ticker", "")).upper()
                    if sym:
                        self._cik_map[sym] = str(entry.get("cik_str", "")).zfill(10)
            log.debug("loaded %d CIK mappings", len(self._cik_map))
        # Yahoo uses BRK-B, SEC uses BRK-B too, but some sources use BRK.B.
        return (self._cik_map.get(ticker.upper())
                or self._cik_map.get(ticker.upper().replace("-", ".")))

    def submissions(self, cik: str) -> Optional[dict]:
        return self._get(SUBMISSIONS_URL.format(cik=cik))


# ---------------------------------------------------------------------------
# Filing index
# ---------------------------------------------------------------------------

def _recent_filings(submissions: dict, forms: Iterable[str],
                    since: Optional[dt.date] = None) -> list[dict]:
    """Flatten the submissions 'recent' block into filing records."""
    recent = (submissions.get("filings") or {}).get("recent") or {}
    if not recent:
        return []

    wanted = {f.upper() for f in forms}
    out: list[dict] = []
    n = len(recent.get("accessionNumber", []))
    for i in range(n):
        form = str(recent["form"][i]).upper()
        # "10-K/A" and "4/A" are amendments of the forms we want.
        base = form.split("/")[0]
        if base not in wanted:
            continue
        filed = recent["filingDate"][i]
        if since:
            try:
                if dt.date.fromisoformat(filed) < since:
                    continue
            except ValueError:
                continue
        accession = recent["accessionNumber"][i]
        out.append({
            "accession": accession,
            "accession_nodash": accession.replace("-", ""),
            "form": form,
            "filed_date": filed,
            "period": recent.get("reportDate", [None] * n)[i],
            "primary_doc": recent.get("primaryDocument", [None] * n)[i],
        })
    return out


def _section_text(html: str, kind: str) -> Optional[str]:
    """
    Extract Risk Factors or MD&A from a filing's HTML.

    Regex-based on purpose: these documents have no consistent structure, and
    a full parse buys nothing over anchoring on the item headings. The result
    feeds an LLM in Layer 3, so approximate boundaries are acceptable — what
    matters is capturing the right region, not exact edges.
    """
    try:
        from bs4 import BeautifulSoup
        text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    except Exception:                              # noqa: BLE001
        text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)

    if kind == "risk_factors":
        start_pat = r"item\s*1a\.?\s*risk\s*factors"
        end_pat = r"item\s*1b\.?\s*unresolved|item\s*2\.?\s*propert"
    else:
        start_pat = (r"item\s*2\.?\s*management.s\s*discussion|"
                     r"item\s*7\.?\s*management.s\s*discussion")
        end_pat = (r"item\s*3\.?\s*quantitative|item\s*7a\.?\s*quantitative|"
                   r"item\s*4\.?\s*controls")

    starts = [m.end() for m in re.finditer(start_pat, text, re.IGNORECASE)]
    if not starts:
        return None
    # The last occurrence is the body; earlier ones are the table of contents.
    start = starts[-1]
    tail = text[start:]
    end_match = re.search(end_pat, tail, re.IGNORECASE)
    section = tail[:end_match.start()] if end_match else tail[:200_000]
    section = section.strip()
    return section if len(section) > 500 else None


# ---------------------------------------------------------------------------
# Form 4 parsing
# ---------------------------------------------------------------------------

def _raw_xml_doc(primary_doc: str) -> str:
    """
    Strip SEC's XSL rendering prefix to get the machine-readable XML.

    EDGAR lists a Form 4's primary document as e.g. "xslF345X06/form4.xml",
    which is the human-readable HTML rendering — fetching it yields styled
    markup with no <nonDerivativeTransaction> elements, so the parser silently
    finds zero transactions. The raw XML lives at the same path with the
    xsl* directory removed.
    """
    if "/" in primary_doc:
        head, _, tail = primary_doc.partition("/")
        if head.lower().startswith("xsl"):
            return tail
    return primary_doc


def _parse_form4(xml_text: str, ticker: str, accession: str,
                 cfg) -> list[dict]:
    """
    Parse a Form 4 XML document into transaction records.

    Non-derivative table only: derivative rows (options, RSUs) are
    compensation instruments whose economics do not map onto the simple
    "insider bought/sold N shares at $P" signal Layer 2 uses.
    """
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(xml_text, "xml")
    except Exception:                              # noqa: BLE001
        return []

    owner = soup.find("reportingOwner")
    name, title = None, ""
    is_director = False
    if owner:
        name_tag = owner.find("rptOwnerName")
        name = name_tag.get_text(strip=True) if name_tag else None
        rel = owner.find("reportingOwnerRelationship")
        if rel:
            officer_title = rel.find("officerTitle")
            title = officer_title.get_text(strip=True) if officer_title else ""
            director_tag = rel.find("isDirector")
            is_director = bool(director_tag and
                               director_tag.get_text(strip=True) in ("1", "true"))
            if not title and is_director:
                title = "Director"

    senior_titles = [t.lower() for t in cfg.get("data.sec.senior_titles", [])]
    title_l = (title or "").lower()
    is_senior = any(st in title_l for st in senior_titles)

    signal_codes = set(cfg.get("data.sec.signal_codes", ["P", "S"]))

    def _num(node, tag: str) -> Optional[float]:
        el = node.find(tag)
        if not el:
            return None
        value = el.find("value")
        text = (value or el).get_text(strip=True)
        try:
            return float(text)
        except (TypeError, ValueError):
            return None

    rows: list[dict] = []
    for txn in soup.find_all("nonDerivativeTransaction"):
        code_el = txn.find("transactionCode")
        code = code_el.get_text(strip=True).upper() if code_el else ""

        date_el = txn.find("transactionDate")
        txn_date = None
        if date_el:
            value = date_el.find("value")
            txn_date = (value or date_el).get_text(strip=True)[:10]

        shares = _num(txn, "transactionShares")
        price = _num(txn, "transactionPricePerShare")
        shares_after = _num(txn, "sharesOwnedFollowingTransaction")

        acq_el = txn.find("transactionAcquiredDisposedCode")
        acq = ""
        if acq_el:
            value = acq_el.find("value")
            acq = (value or acq_el).get_text(strip=True).upper()

        if shares is None:
            continue
        # Sign the value: disposals negative, acquisitions positive, so a
        # simple SUM over a window gives net dollar flow.
        signed = shares if acq == "A" else -shares
        value_usd = signed * price if price else None

        rows.append({
            "accession": accession, "ticker": ticker,
            "insider_name": name or "unknown",
            "insider_title": title,
            "is_senior": int(is_senior),
            "is_director": int(is_director),
            "transaction_date": txn_date,
            "code": code,
            "is_signal": int(code in signal_codes),
            "shares": signed,
            "price": price,
            "value_usd": value_usd,
            "shares_after": shares_after,
        })
    return rows


INSIDER_COLUMNS = [
    "accession", "ticker", "insider_name", "insider_title", "is_senior",
    "is_director", "transaction_date", "code", "is_signal", "shares",
    "price", "value_usd", "shares_after", "filed_date",
]


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------

def ingest(db, cfg, tickers: Iterable[str], client: Optional[SECClient] = None,
           fetch_sections: bool = True) -> SECStats:
    """Fetch filings, extract sections, and parse Form 4s for each ticker."""
    tickers = list(tickers)
    stats = SECStats(tickers_requested=len(tickers))

    try:
        client = client or SECClient(cfg)
    except RuntimeError as exc:
        stats.error = str(exc)
        log.error("%s", exc)
        return stats

    forms = cfg.get("data.sec.forms", ["10-K", "10-Q", "8-K", "4"])
    lookback = int(cfg.get("data.sec.insider_lookback_days", 180))
    since = dt.date.today() - dt.timedelta(days=lookback)
    fetched_at = dt.datetime.now().isoformat(timespec="seconds")

    for i, ticker in enumerate(tickers, 1):
        if i % 25 == 0:
            log.info("  SEC %d/%d…", i, len(tickers))

        cik = client.cik_for(ticker)
        if not cik:
            stats.failed.append(ticker)
            continue
        submissions = client.submissions(cik)
        if not submissions:
            stats.failed.append(ticker)
            continue

        filings = _recent_filings(submissions, forms, since=since)
        if not filings:
            stats.tickers_processed += 1
            continue

        cik_num = str(int(cik))     # archive paths use the unpadded CIK
        filing_rows: list[tuple] = []
        for f in filings:
            url = ARCHIVE_URL.format(cik=cik_num, accession=f["accession_nodash"],
                                     doc=f["primary_doc"] or "")
            filing_rows.append((f["accession"], ticker, cik, f["form"],
                                f["filed_date"], f["period"], f["primary_doc"],
                                url, fetched_at))
        stats.filings += db.upsert_many(
            "filings",
            ["accession", "ticker", "cik", "form", "filed_date", "period",
             "primary_doc", "url", "fetched_at"],
            filing_rows,
        )

        # --- narrative sections: latest 10-K and 10-Q only -----------------
        if fetch_sections:
            for form, section in (("10-K", "risk_factors"), ("10-Q", "mdna")):
                latest = next((f for f in filings if f["form"].startswith(form)), None)
                if not latest:
                    continue
                already = db.scalar(
                    "SELECT COUNT(*) FROM filing_sections WHERE accession=? AND section=?",
                    (latest["accession"], section),
                )
                if already:
                    continue      # documents are immutable; never refetch
                url = ARCHIVE_URL.format(cik=cik_num,
                                         accession=latest["accession_nodash"],
                                         doc=latest["primary_doc"] or "")
                html = client._get(url, as_json=False)
                if not html:
                    continue
                text = _section_text(html, section)
                if text:
                    stats.sections += db.upsert_many(
                        "filing_sections", ["accession", "section", "content", "char_count"],
                        [(latest["accession"], section, text, len(text))],
                    )

        # --- Form 4 --------------------------------------------------------
        insider_rows: list[tuple] = []
        for f in filings:
            if not f["form"].startswith("4"):
                continue
            already = db.scalar(
                "SELECT COUNT(*) FROM insider_transactions WHERE accession = ?",
                (f["accession"],),
            )
            if already:
                continue
            url = ARCHIVE_URL.format(cik=cik_num, accession=f["accession_nodash"],
                                     doc=_raw_xml_doc(f["primary_doc"] or ""))
            xml = client._get(url, as_json=False)
            if not xml:
                continue
            for record in _parse_form4(xml, ticker, f["accession"], cfg):
                record["filed_date"] = f["filed_date"]
                insider_rows.append(tuple(record.get(c) for c in INSIDER_COLUMNS))

        if insider_rows:
            written = db.upsert_many("insider_transactions", INSIDER_COLUMNS, insider_rows)
            stats.insider_rows += written
            stats.signal_rows += sum(1 for r in insider_rows if r[8] == 1)

        stats.tickers_processed += 1

    stats.cluster_flags = len(cluster_buys(db, cfg))
    log.info("SEC: %d filings, %d sections, %d insider rows (%d signal) for %d tickers",
             stats.filings, stats.sections, stats.insider_rows,
             stats.signal_rows, stats.tickers_processed)
    return stats


# ---------------------------------------------------------------------------
# Derived insider signals — consumed by Layer 2's insider factor
# ---------------------------------------------------------------------------

def cluster_buys(db, cfg) -> dict[str, dict[str, Any]]:
    """
    Tickers where 3+ DISTINCT insiders made open-market purchases within the
    configured window.

    Distinct is the operative word: one executive buying on three consecutive
    days is one opinion, not three. Cluster buying is a stronger signal than
    any single purchase because it is hard to explain away as a personal
    liquidity event.
    """
    window = int(cfg.get("data.sec.cluster_buy_window_days", 30))
    min_insiders = int(cfg.get("data.sec.cluster_buy_min_insiders", 3))
    cutoff = (dt.date.today() - dt.timedelta(days=window)).isoformat()

    rows = db.query(
        "SELECT ticker, COUNT(DISTINCT insider_name) AS n_insiders, "
        "       SUM(value_usd) AS net_value, "
        "       SUM(CASE WHEN is_senior = 1 THEN 1 ELSE 0 END) AS senior_buys "
        "FROM insider_transactions "
        "WHERE code = 'P' AND is_signal = 1 AND transaction_date >= ? "
        "GROUP BY ticker HAVING n_insiders >= ?",
        (cutoff, min_insiders),
    )
    return {
        r["ticker"]: {
            "insiders": r["n_insiders"],
            "net_value_usd": r["net_value"],
            "senior_buys": r["senior_buys"],
            "window_days": window,
        }
        for r in rows
    }


def net_insider_flow(db, days: int = 90) -> pd.DataFrame:
    """
    Net open-market dollar flow per ticker over `days`.

    Senior (CEO/CFO) activity is returned as a separate column so Layer 2 can
    apply its 3x weighting without re-querying.
    """
    cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    rows = db.query(
        "SELECT ticker, "
        "  SUM(value_usd) AS net_value, "
        "  SUM(CASE WHEN is_senior = 1 THEN value_usd ELSE 0 END) AS senior_value, "
        "  COUNT(DISTINCT insider_name) AS n_insiders, "
        "  SUM(CASE WHEN code = 'P' THEN 1 ELSE 0 END) AS n_buys, "
        "  SUM(CASE WHEN code = 'S' THEN 1 ELSE 0 END) AS n_sells "
        "FROM insider_transactions "
        "WHERE is_signal = 1 AND transaction_date >= ? GROUP BY ticker",
        (cutoff,),
    )
    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
