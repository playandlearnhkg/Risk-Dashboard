"""
data_sources_panel.py — "Where is this data coming from?" panel.
================================================================

Answers two questions without opening a log file:

  1. Which provider is serving each kind of data, and did any of them quietly
     fall back to a different one?
  2. Is the data I am looking at COMPLETE, or was it truncated by rate
     limiting?

Two independent sources feed it:

  * THIS dashboard's own live feeds (Yahoo, FRED), whose health is derived
    from the MarketData object already loaded for the page. Nothing extra is
    fetched.
  * MERIDIAN's provider assignments, read from
    `daily_dashboard/output/system_status.json` if that file exists. Read as
    a FILE rather than by importing Meridian, so the dashboard works whether
    or not Meridian is installed, configured, or has ever run.

Colour never carries the meaning on its own — every state is also a word.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Optional

import streamlit as st

import ui

# Meridian writes here. Relative to this file so it resolves from any cwd.
MERIDIAN_STATUS = Path(__file__).parent / "daily_dashboard" / "output" / "system_status.json"


def _read_meridian_status(path: Path = MERIDIAN_STATUS) -> dict[str, Any]:
    try:
        if path.exists():
            return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _age_str(iso: Optional[str]) -> str:
    """Human-readable age. Staleness is the thing that matters here."""
    if not iso:
        return "unknown"
    try:
        when = dt.datetime.fromisoformat(iso)
    except ValueError:
        return "unknown"
    delta = dt.datetime.now() - when
    hours = delta.total_seconds() / 3600
    if hours < 1:
        return f"{int(delta.total_seconds() // 60)} min ago"
    if hours < 24:
        return f"{int(hours)}h ago"
    return f"{int(hours // 24)}d ago"


def _row(label: str, value: str, state: str = "ok", note: str = "") -> str:
    """One source row: name → provider, with a state word."""
    colour = {
        "ok": ui.palette()["good"],
        "warn": ui.palette()["warning"],
        "bad": ui.palette()["critical"],
        "idle": ui.palette()["muted"],
    }.get(state, ui.palette()["muted"])
    symbol = {"ok": "●", "warn": "▲", "bad": "✕", "idle": "○"}.get(state, "○")
    note_html = (f'<div style="font-size:0.68rem;opacity:0.65;margin:1px 0 0 14px">'
                 f'{note}</div>') if note else ""
    return (
        f'<div style="margin:3px 0">'
        f'<span style="color:{colour};font-size:0.7rem">{symbol}</span> '
        f'<span style="font-size:0.74rem;opacity:0.75">{label}</span>'
        f'<span style="float:right;font-size:0.74rem;font-weight:600">{value}</span>'
        f'</div>{note_html}'
    )


def render(md=None, in_sidebar: bool = True) -> None:
    """
    Draw the panel.

    `md` is the dashboard's MarketData, used to derive live feed health with
    no extra network calls. Pass None to show only Meridian's status.
    """
    container = st.sidebar if in_sidebar else st
    status = _read_meridian_status()

    with container:
        st.markdown("### Data sources")

        # ---- this dashboard's own feeds -----------------------------------
        rows: list[str] = []
        if md is not None:
            yahoo_ok = not md.yahoo.empty
            fred_ok = not md.fred.empty
            rows.append(_row(
                "Market / FX / VIX",
                "Yahoo Finance",
                "ok" if yahoo_ok else "bad",
                "" if yahoo_ok else "no data — likely rate limited (HTTP 429)",
            ))
            rows.append(_row(
                "Rates / credit / macro",
                "FRED",
                "ok" if fred_ok else "bad",
                "" if fred_ok else "unreachable",
            ))
            rows.append(_row("Margin debt", "FINRA", "ok", "manual CSV, monthly"))
        st.markdown("".join(rows), unsafe_allow_html=True)

        # ---- rate-limit banner --------------------------------------------
        # The single most useful thing this panel can tell you: whether what
        # you are looking at is complete.
        if md is not None and md.yahoo.empty and not md.fred.empty:
            st.markdown(
                f'<div style="border-left:3px solid {ui.palette()["critical"]};'
                f'padding:7px 10px;margin:8px 0;font-size:0.72rem;'
                f'background:rgba(128,128,128,0.10);border-radius:0 6px 6px 0">'
                f'<strong>Data incomplete — rate limited.</strong><br>'
                f'Yahoo returned nothing (HTTP 429). FX, VIX, commodity and '
                f'equity cards are blank and their components are excluded '
                f'from the score. FRED data is unaffected. Usually clears '
                f'within an hour.</div>',
                unsafe_allow_html=True,
            )

        # ---- Meridian ------------------------------------------------------
        if not status:
            st.caption("Meridian: no status file — has not run yet.")
            return

        st.markdown("**Meridian (Layer 1)**")
        providers = status.get("providers", [])
        fell_back = [p for p in providers if p.get("fell_back")]

        prov_rows = [
            _row(
                p["role"].replace("_", " ").title(),
                p["effective"],
                "warn" if p.get("fell_back") else "ok",
                f"configured '{p['requested']}' — {p.get('note','')}"
                if p.get("fell_back") else "",
            )
            for p in providers
        ]
        for f in status.get("fixed_sources", []):
            prov_rows.append(_row(f["role"].replace("_", " ").title(),
                                  f["effective"], "ok"))
        st.markdown("".join(prov_rows), unsafe_allow_html=True)

        if fell_back:
            st.markdown(
                f'<div style="border-left:3px solid {ui.palette()["warning"]};'
                f'padding:6px 10px;margin:6px 0;font-size:0.7rem;'
                f'background:rgba(128,128,128,0.10);border-radius:0 6px 6px 0">'
                f'<strong>{len(fell_back)} provider fallback'
                f'{"s" if len(fell_back) > 1 else ""}.</strong> '
                f'Meridian is not using what config.yaml asks for.</div>',
                unsafe_allow_html=True,
            )

        # ---- Meridian rate limiting / freshness ----------------------------
        rl = status.get("rate_limit") or {}
        if rl.get("rate_limited"):
            detail = (f"{rl.get('hits', 0)} hit(s), "
                      f"{rl.get('cooldowns', 0)} cooldown(s)")
            if rl.get("aborted"):
                detail += " — fetch STOPPED EARLY, prices are partial"
            st.markdown(
                f'<div style="border-left:3px solid {ui.palette()["critical"]};'
                f'padding:6px 10px;margin:6px 0;font-size:0.7rem;'
                f'background:rgba(128,128,128,0.10);border-radius:0 6px 6px 0">'
                f'<strong>Last ingest was rate limited.</strong><br>{detail}. '
                f'Rerun locally to fill the gaps.</div>',
                unsafe_allow_html=True,
            )

        cov = status.get("price_coverage") or {}
        last = status.get("last_ingest") or {}
        bits = []
        if cov.get("latest_date"):
            bits.append(f"prices to {cov['latest_date']}")
        if cov.get("tickers"):
            stale = cov.get("stale_tickers") or 0
            bits.append(f"{cov['tickers']} tickers"
                        + (f", {stale} stale" if stale else ""))
        if last.get("finished_at"):
            bits.append(f"ingest {_age_str(last['finished_at'])}")
        if bits:
            st.caption(" · ".join(bits))
