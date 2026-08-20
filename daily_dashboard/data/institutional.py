"""
data/institutional.py — 13-F holdings for the nine tracked funds.
=================================================================

13-F is a quarterly snapshot filed up to 45 days after quarter end, so this
data is structurally stale — by the time you read it the position may be
gone. It is still worth tracking for two reasons: the direction of change
across several independent managers is informative even when the level is
old, and a position several funds opened simultaneously is a much stronger
statement than any single holding.

What it cannot tell you: shorts (13-F is long-only), non-US listings, and
anything held via derivatives. Treat absence as no information, never as a
negative signal.

The reported `value` column changed units in 2023 — older filings report
thousands of dollars, newer ones report whole dollars. `_normalise_value`
handles that; getting it wrong scales a position by 1000x.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd

from core.logging_setup import get_logger
from data.sec_data import SECClient

log = get_logger("data.institutional")


@dataclass
class InstitutionalStats:
    funds_requested: int = 0
    funds_processed: int = 0
    holdings: int = 0          # rows STORED, after per-ticker aggregation
    lines_parsed: int = 0      # 13-F line items matched to a ticker
    lines_merged: int = 0      # lines folded into an existing ticker by summing
    common_lines: int = 0      # common-stock lines (the conviction signal)
    option_lines: int = 0      # PUT/CALL lines, kept out of shares/value_usd
    principal_lines: int = 0   # PRN lines (convertible debt), not share counts
    multi_fund_opens: int = 0
    failed_funds: list[str] = field(default_factory=list)
    error: str = ""


def _normalise_value(value: float, shares: Optional[float]) -> float:
    """
    Coerce the reported value to whole dollars.

    Pre-2023 13-Fs report value in THOUSANDS. Detect by implied price: if
    value/shares comes out under $1, the value is almost certainly in
    thousands (a sub-$1 mean price across an institutional book is far less
    likely than a units mismatch).
    """
    if not shares or shares <= 0:
        return value
    implied_price = value / shares
    return value * 1000.0 if implied_price < 1.0 else value


def _parse_13f(xml_text: str) -> list[dict[str, Any]]:
    """Parse a 13-F information table into holding records."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(xml_text, "xml")
    except Exception:                              # noqa: BLE001
        return []

    out: list[dict[str, Any]] = []
    for entry in soup.find_all(re.compile(r"infoTable$", re.IGNORECASE)):
        def text(tag: str) -> Optional[str]:
            el = entry.find(re.compile(f"{tag}$", re.IGNORECASE))
            return el.get_text(strip=True) if el else None

        cusip = text("cusip")
        name = text("nameOfIssuer")
        try:
            value = float(text("value") or 0)
        except ValueError:
            value = 0.0

        shares = None
        amount_type = "SH"
        shrs_node = entry.find(re.compile(r"shrsOrPrnAmt$", re.IGNORECASE))
        if shrs_node:
            amt = shrs_node.find(re.compile(r"sshPrnamt$", re.IGNORECASE))
            if amt:
                try:
                    shares = float(amt.get_text(strip=True))
                except ValueError:
                    shares = None
            # sshPrnamtType is "SH" for a share count or "PRN" for a debt
            # PRINCIPAL amount. They are different units entirely: a PRN row
            # on a convertible bond reports dollars of principal, and adding
            # it to a share count produces nonsense. Citadel's DXCM line came
            # out at an implied $922/share for exactly this reason.
            type_node = shrs_node.find(re.compile(r"sshPrnamtType$", re.IGNORECASE))
            if type_node:
                amount_type = (type_node.get_text(strip=True) or "SH").upper()

        # putCall is ABSENT on a common-stock line and set to "Put" or "Call"
        # on an option line. Treating a missing tag as common stock is correct
        # and is what the 13-F format intends.
        put_call = (text("putCall") or "").strip().upper()

        if not cusip or shares is None:
            continue
        out.append({
            "cusip": cusip, "issuer": name, "shares": shares,
            "value_usd": _normalise_value(value, shares),
            "put_call": put_call,          # "", "PUT" or "CALL"
            "amount_type": amount_type,    # "SH" (shares) or "PRN" (principal)
        })
    return out


def _cusip_to_ticker(db) -> dict[str, str]:
    """
    Best-effort CUSIP -> ticker map.

    There is no free authoritative CUSIP directory, so this matches on issuer
    name against the universe. Coverage is partial by design; unmatched
    holdings are dropped rather than guessed at, because a wrong mapping
    silently attributes one fund's position to the wrong company.
    """
    rows = db.query(
        "SELECT ticker, company_name FROM universe "
        "WHERE kind = 'equity' AND company_name IS NOT NULL"
    )
    out: dict[str, str] = {}
    for r in rows:
        name = re.sub(r"[^a-z0-9 ]", "", (r["company_name"] or "").lower())
        name = re.sub(r"\b(inc|corp|corporation|co|company|ltd|plc|group|holdings|the)\b",
                      "", name).strip()
        if name:
            out[name] = r["ticker"]
    return out


def ingest(db, cfg, client: Optional[SECClient] = None) -> InstitutionalStats:
    """Fetch the most recent 13-F filings for each configured fund."""
    funds = cfg.get("data.institutional.funds", []) or []
    quarters = int(cfg.get("data.institutional.quarters_back", 2))
    stats = InstitutionalStats(funds_requested=len(funds))

    try:
        client = client or SECClient(cfg)
    except RuntimeError as exc:
        stats.error = str(exc)
        log.error("%s", exc)
        return stats

    name_map = _cusip_to_ticker(db)

    for fund in funds:
        cik = str(fund.get("cik", "")).zfill(10)
        fund_name = fund.get("name", cik)
        submissions = client.submissions(cik)
        if not submissions:
            stats.failed_funds.append(fund_name)
            continue

        recent = (submissions.get("filings") or {}).get("recent") or {}
        filings: list[tuple[str, str, str]] = []
        for i in range(len(recent.get("accessionNumber", []))):
            if not str(recent["form"][i]).upper().startswith("13F-HR"):
                continue
            filings.append((recent["accessionNumber"][i],
                            recent["filingDate"][i],
                            recent.get("reportDate", [""] * (i + 1))[i]))
            if len(filings) >= quarters:
                break

        if not filings:
            stats.failed_funds.append(fund_name)
            continue

        cik_num = str(int(cik))
        for accession, filed_date, report_date in filings:
            nodash = accession.replace("-", "")
            index = client._get(
                f"https://www.sec.gov/Archives/edgar/data/{cik_num}/{nodash}/index.json"
            )
            if not index:
                continue

            # The information table is the XML that is not the primary doc.
            xml_name = None
            for item in (index.get("directory", {}) or {}).get("item", []):
                fname = item.get("name", "")
                if fname.endswith(".xml") and "primary_doc" not in fname.lower():
                    xml_name = fname
                    break
            if not xml_name:
                continue

            xml = client._get(
                f"https://www.sec.gov/Archives/edgar/data/{cik_num}/{nodash}/{xml_name}",
                as_json=False,
            )
            if not xml:
                continue

            # AGGREGATE BEFORE INSERT.
            #
            # A 13-F lists the same issuer on several lines: different share
            # classes, separate lots, and PUT/CALL rows all carry the same
            # CUSIP-to-ticker mapping. The primary key is
            # (fund_cik, ticker, report_date), so inserting them one by one
            # made each line REPLACE the previous one and the fund's position
            # collapsed to whichever line happened to be parsed last.
            #
            # Measured on a real run before this fix: 4,766 parsed rows became
            # 1,799 stored rows — 62% of the data silently overwritten, and
            # every surviving position understated.
            #
            # Summing is the correct reduction: the fund's economic exposure to
            # a ticker is the total across its lines, not one arbitrary line.
            # Options are summed SEPARATELY from common stock.
            #
            # A 13-F reports a PUT on a name in the same shape as owning it,
            # and adding them together produces a number that means nothing:
            # a fund short 5m shares via puts would read as a large holder.
            # Citadel's pre-separation DXCM line came out at $84bn for exactly
            # this reason — overwhelmingly option notional, not conviction.
            #
            # shares/value_usd therefore carry COMMON STOCK ONLY, which is the
            # conviction signal Layer 2's Institutional Flow factor wants.
            # Option notional is kept alongside so nothing is thrown away and
            # a later factor can use it deliberately.
            merged: dict[tuple[str, str], dict[str, Any]] = {}
            parsed_lines = 0
            for holding in _parse_13f(xml):
                issuer = re.sub(r"[^a-z0-9 ]", "", (holding["issuer"] or "").lower())
                issuer = re.sub(
                    r"\b(inc|corp|corporation|co|company|ltd|plc|group|holdings|the)\b",
                    "", issuer).strip()
                ticker = name_map.get(issuer)
                if not ticker:
                    continue        # unmatched: drop rather than guess
                parsed_lines += 1

                period = report_date or filed_date
                key = (ticker, period)
                entry = merged.setdefault(key, {
                    "cusip": holding["cusip"],
                    "shares": 0.0, "value_usd": 0.0,
                    "put_value_usd": 0.0, "call_value_usd": 0.0,
                    "other_value_usd": 0.0,
                    "lines": 0,
                })
                entry["lines"] += 1

                kind = holding.get("put_call", "")
                value = holding["value_usd"] or 0.0

                if holding.get("amount_type", "SH") != "SH":
                    # PRN — debt principal, not shares. Value is still real
                    # money at risk in the name, so keep it, but never let it
                    # reach `shares` or the common-stock value.
                    entry["other_value_usd"] += value
                    stats.principal_lines += 1
                elif kind == "PUT":
                    entry["put_value_usd"] += value
                    stats.option_lines += 1
                elif kind == "CALL":
                    entry["call_value_usd"] += value
                    stats.option_lines += 1
                else:
                    entry["shares"] += holding["shares"] or 0.0
                    entry["value_usd"] += value
                    stats.common_lines += 1

            stats.lines_parsed += parsed_lines
            stats.lines_merged += parsed_lines - len(merged)

            rows = [
                (cik, fund_name, ticker, agg["cusip"], period,
                 agg["shares"], agg["value_usd"],
                 agg["put_value_usd"], agg["call_value_usd"],
                 agg["other_value_usd"])
                for (ticker, period), agg in merged.items()
            ]

            if rows:
                # Count what is actually stored, not what was submitted. The
                # old code reported the submitted count, which is how the
                # overwrite stayed invisible in the run summary.
                stats.holdings += db.upsert_many(
                    "institutional_holdings",
                    ["fund_cik", "fund_name", "ticker", "cusip", "report_date",
                     "shares", "value_usd", "put_value_usd", "call_value_usd",
                     "other_value_usd"],
                    rows,
                )

        stats.funds_processed += 1
        log.debug("13-F processed: %s", fund_name)

    stats.multi_fund_opens = len(multi_fund_openings(db, cfg))
    log.info("13-F: %d positions from %d/%d funds — %d lines "
             "(%d common, %d option, %d principal), %d merged — %d multi-fund opens",
             stats.holdings, stats.funds_processed, len(funds),
             stats.lines_parsed, stats.common_lines, stats.option_lines,
             stats.principal_lines, stats.lines_merged, stats.multi_fund_opens)
    return stats


# ---------------------------------------------------------------------------
# Derived signals — consumed by Layer 2's institutional factor
# ---------------------------------------------------------------------------

def fund_counts(db) -> pd.DataFrame:
    """Number of tracked funds holding each ticker, most recent quarter."""
    latest = db.scalar("SELECT MAX(report_date) FROM institutional_holdings")
    if not latest:
        return pd.DataFrame()
    # shares > 0 filters to funds actually holding the COMMON STOCK. A fund
    # whose only exposure is options is not a holder in the sense this factor
    # means, and counting it would overstate conviction.
    rows = db.query(
        "SELECT ticker, COUNT(DISTINCT fund_cik) AS n_funds, "
        "       SUM(value_usd) AS total_value, "
        "       SUM(COALESCE(put_value_usd,0))  AS put_value, "
        "       SUM(COALESCE(call_value_usd,0)) AS call_value "
        "FROM institutional_holdings WHERE report_date = ? AND shares > 0 "
        "GROUP BY ticker",
        (latest,),
    )
    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()


def net_change(db) -> pd.DataFrame:
    """
    Change in aggregate shares held between the two most recent quarters.

    Tickers absent from the prior quarter are new positions and are reported
    with `is_new = 1` — that is the input to the multi-fund opening flag.
    """
    dates = [r["report_date"] for r in db.query(
        "SELECT DISTINCT report_date FROM institutional_holdings "
        "ORDER BY report_date DESC LIMIT 2")]
    if len(dates) < 2:
        return pd.DataFrame()
    current, prior = dates[0], dates[1]

    rows = db.query(
        "SELECT c.ticker, "
        "  SUM(c.shares) AS shares_now, "
        "  COALESCE((SELECT SUM(p.shares) FROM institutional_holdings p "
        "            WHERE p.ticker = c.ticker AND p.report_date = ?), 0) AS shares_prior, "
        "  COUNT(DISTINCT c.fund_cik) AS n_funds_now "
        "FROM institutional_holdings c WHERE c.report_date = ? AND c.shares > 0 "
        "GROUP BY c.ticker",
        (prior, current),
    )
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame([dict(r) for r in rows])
    df["share_change"] = df["shares_now"] - df["shares_prior"]
    df["pct_change"] = df.apply(
        lambda r: ((r["shares_now"] / r["shares_prior"] - 1) * 100)
        if r["shares_prior"] > 0 else None, axis=1)
    df["is_new"] = (df["shares_prior"] == 0).astype(int)
    return df


def multi_fund_openings(db, cfg) -> dict[str, int]:
    """
    Tickers where N+ tracked funds opened a NEW position in the same quarter.

    Independent managers arriving at the same name simultaneously is the
    strongest signal available in 13-F data — far stronger than a single large
    holder, who may simply be rebalancing.
    """
    threshold = int(cfg.get("data.institutional.multi_fund_open_threshold", 3))
    dates = [r["report_date"] for r in db.query(
        "SELECT DISTINCT report_date FROM institutional_holdings "
        "ORDER BY report_date DESC LIMIT 2")]
    if len(dates) < 2:
        return {}
    current, prior = dates[0], dates[1]

    rows = db.query(
        "SELECT c.ticker, COUNT(DISTINCT c.fund_cik) AS n_new "
        "FROM institutional_holdings c "
        "WHERE c.report_date = ? AND c.shares > 0 AND NOT EXISTS ("
        "  SELECT 1 FROM institutional_holdings p "
        "  WHERE p.ticker = c.ticker AND p.fund_cik = c.fund_cik "
        "    AND p.report_date = ? AND p.shares > 0) "
        "GROUP BY c.ticker HAVING n_new >= ?",
        (current, prior, threshold),
    )
    return {r["ticker"]: r["n_new"] for r in rows}
