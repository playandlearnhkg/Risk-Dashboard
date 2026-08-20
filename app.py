"""
app.py — Systematic Risk Macro Dashboard
========================================

Run locally:      streamlit run app.py
Run for phone:    streamlit run app.py --server.address 0.0.0.0
(see README.md for always-on hosting so it works from anywhere)

Layout
------
  Sidebar        How to use, refresh, manual inputs, weight sliders
  Overview       The regime call and why
  Carry & FX     USDJPY, crosses, rate differentials
  Rates          US/JP yields, curve, policy, meeting calendar
  Commodities    Oil, gold, copper
  Leverage       FINRA margin debt (editable)
  Stress         VIX, credit, correlation regime
  Watchlist      Your own notes and event tracking
  Methodology    What every number means and how the score is built
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd
import streamlit as st

import config
import data_sources as ds
import data_sources_panel
import margin_debt as mdbt
import metrics as mx
import scoring
import ui

APP_DIR = Path(__file__).parent
WATCHLIST_PATH = APP_DIR / "data" / "watchlist.json"

st.set_page_config(
    page_title="Systematic Risk Monitor",
    page_icon="📉",
    layout="wide",
    initial_sidebar_state="collapsed",   # phone-friendly: content first
)


# ===========================================================================
# SIDEBAR
# ===========================================================================

def render_sidebar(seeds: dict, md=None) -> dict:
    """
    Draw the sidebar and return the manual-input overrides it collected.

    `seeds` comes from ds.jp_rate_seeds() — the latest FRED monthly Japanese
    values, so the inputs open with something real instead of a stale constant.
    `md` is passed through to the data-sources panel so it can report feed
    health without making any additional network calls.
    """
    with st.sidebar:
        st.markdown("### How to use this dashboard")
        st.markdown(
            """
**Sixty seconds, every morning:**

1. Read the **regime banner** at the top. Green means carry on; amber means
   stop adding risk; red means actively reduce equity exposure.
2. If it is amber or red, look at the **component bars** underneath — they
   tell you *which* thing broke.
3. Check the **escalation flags**. These fire on specific dangerous
   combinations and are the ones that matter most.
4. Glance at **USDJPY 1-week** and the **VIX term structure**. Those two move
   first when a systematic event is starting.

**Once a month:** update FINRA margin debt on the Leverage tab.

**Whenever the BOJ moves:** update the Japanese yields below.

This is a monitoring tool, not a trading signal. It tells you when the
*environment* is fragile, not when to buy or sell any specific thing.
            """
        )

        st.divider()

        # -- Refresh ---------------------------------------------------------
        if st.button("Refresh data", width="stretch", type="primary"):
            st.cache_data.clear()
            st.rerun()

        st.divider()

        # -- Manual inputs ---------------------------------------------------
        st.markdown("### Japanese rates")
        st.caption(
            "No free **daily** JGB feed exists, so these open pre-filled from "
            "FRED's **monthly** Japanese series and you refine them by hand. "
            "They drive the carry-trade differentials — the highest-weighted "
            "part of the model — so keeping them current matters more than "
            "anything else on this panel."
        )

        jp2y = st.number_input(
            "Japan 2-year yield (%)", value=float(seeds["JP2Y"]["value"]),
            min_value=-1.0, max_value=6.0, step=0.05, format="%.3f",
            help="The 2-year is what actually prices the carry trade. FRED has "
                 "no Japanese 2-year series, so this is seeded from the "
                 "3-month interbank rate — an anchor, not the real yield. "
                 "Type the actual 2-year JGB yield for an accurate "
                 "differential.",
        )
        st.caption(f"↳ {seeds['JP2Y']['source']}")

        jp10y = st.number_input(
            "Japan 10-year yield (%)", value=float(seeds["JP10Y"]["value"]),
            min_value=-1.0, max_value=8.0, step=0.05, format="%.3f",
        )
        st.caption(f"↳ {seeds['JP10Y']['source']}")

        boj = st.number_input(
            "BOJ policy rate (%)", value=float(seeds["BOJ_RATE"]["value"]),
            min_value=-1.0, max_value=6.0, step=0.05, format="%.3f",
            help="Seeded from the FRED call money rate, which tracks the BOJ's "
                 "uncollateralised overnight target closely.",
        )
        st.caption(f"↳ {seeds['BOJ_RATE']['source']}")

        if not all(seeds[k]["is_live"] for k in seeds):
            st.warning(
                "FRED's Japanese series did not load, so one or more values "
                "fell back to the constants in `config.py`. Check them.",
                icon="⚠️",
            )

        st.divider()

        # -- Weights ---------------------------------------------------------
        st.divider()
        data_sources_panel.render(md, in_sidebar=True)

        st.divider()
        st.markdown("### Risk model weights")
        st.caption(
            "Change what the composite cares about. Defaults live in "
            "`config.py` → `WEIGHTS`; these sliders override them for this "
            "session only."
        )
        overrides = {}
        with st.expander("Adjust component weights"):
            for key, default in config.WEIGHTS.items():
                label = key.replace("_", " ").title()
                overrides[key] = st.slider(
                    label, min_value=0.0, max_value=40.0,
                    value=float(default), step=1.0, key=f"w_{key}",
                )
            st.caption(
                "Set a weight to 0 to drop a component entirely. Remaining "
                "weights are re-normalised automatically."
            )

        st.divider()
        window = st.select_slider(
            "Chart window", options=[90, 180, 365, 730],
            value=365, format_func=lambda d: f"{d//30} months" if d < 365 else f"{d//365} year(s)",
        )

    return {
        "JP2Y": jp2y, "JP10Y": jp10y, "BOJ_RATE": boj,
        "JP2Y_source": seeds["JP2Y"]["source"],
        "JP10Y_source": seeds["JP10Y"]["source"],
        "FED_FUNDS": config.MANUAL_POLICY_RATES["FED_FUNDS"],
        "_weights": overrides, "_window": window,
    }


# ===========================================================================
# WATCHLIST PERSISTENCE
# ===========================================================================

def load_watchlist() -> dict:
    if WATCHLIST_PATH.exists():
        try:
            return json.loads(WATCHLIST_PATH.read_text())
        except Exception:
            pass
    return {"notes": "", "events": [], "updated": None}


def save_watchlist(data: dict) -> bool:
    try:
        WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        data["updated"] = dt.datetime.now().isoformat(timespec="seconds")
        WATCHLIST_PATH.write_text(json.dumps(data, indent=2))
        return True
    except Exception:
        return False


# ===========================================================================
# TAB 1 — REGIME OVERVIEW
# ===========================================================================

def tab_overview(m: mx.Metrics, a: scoring.RiskAssessment) -> None:
    ui.regime_banner(a.regime, a.composite, a.coverage_pct)
    st.markdown(scoring.explain(a, m))

    # -- Escalation flags: the highest-signal thing on the page -------------
    if a.escalations:
        st.markdown("#### Escalation flags firing")
        for rule_id, floor, desc in a.escalations:
            ui.alert("high", rule_id.replace("_", " ").title(),
                     f"{desc}<br><em>Floors the composite at {floor:.0f}.</em>")
    else:
        st.markdown("#### Escalation flags")
        ui.alert("low", "None firing",
                 "No dangerous signal <em>combinations</em> detected. The four "
                 "rules watch for: carry unwind, VIX backwardation, credit "
                 "cracking, and peak leverage meeting rising volatility.")

    st.divider()

    # -- Headline numbers ---------------------------------------------------
    st.markdown("#### The five that move first")
    c1, c2, c3, c4, c5 = st.columns(5)

    carry = a.component("carry_fx")
    with c1:
        ui.metric_card(
            "USDJPY", ui.fmt(m.usdjpy, 2),
            deltas=[("1d", m.usdjpy_1d), ("1w", m.usdjpy_1w), ("1m", m.usdjpy_1m)],
            good_direction="up",   # yen weakening = carry intact = calmer
            level=carry.level if carry else None,
            series=m.usdjpy_series, sub="Falling = yen strengthening = carry stress",
        )
    with c2:
        ev = a.component("equity_vol")
        ts_note = "—"
        if m.vix_ratio is not None:
            ts_note = ("Backwardation — acute stress" if m.vix_ratio > 1.0
                       else "Contango — normal")
        ui.metric_card(
            "VIX", ui.fmt(m.vix, 2),
            deltas=[("VIX/3M", m.vix_ratio)], good_direction=None,
            level=ev.level if ev else None, series=m.vix_series,
            sub=ts_note, delta_decimals=3, delta_suffix="",
        )
    with c3:
        rd = a.component("rate_diff")
        ui.metric_card(
            "US–JP 2y differential", ui.fmt(m.diff_2y, 2, "pp"),
            deltas=[("3m", m.diff_2y_change_3m)], good_direction=None,
            level=rd.level if rd else None, series=m.diff_2y_series,
            sub="Wide = carry fuel · narrowing = exit trigger",
            delta_suffix="pp",
        )
    with c4:
        cr = a.component("credit")
        credit_val = (ui.fmt(m.hy_oas, 2, "pp") if m.credit_kind == "oas"
                      else ui.fmt(ds.percentile_of_latest(m.credit_series), 0, "th pct"))
        ui.metric_card(
            "High-yield spread", credit_val,
            deltas=[("1m", m.hy_oas_change_1m)], good_direction="down",
            level=cr.level if cr else None, series=m.credit_series,
            sub=m.credit_source, delta_suffix="pp",
        )
    with c5:
        lv = a.component("leverage")
        ms = m.margin
        val = "—"
        if ms and ms.latest_debit_musd:
            val = f"${ms.latest_debit_musd / 1_000_000:.2f}T"
        is_placeholder = bool(ms and ms.is_placeholder and ms.latest_debit_musd)
        ui.metric_card(
            "Margin debt", val,
            deltas=[("YoY", ms.yoy_pct if ms else None)], good_direction="down",
            level=lv.level if lv else None,
            # "No data" would be wrong next to a visible number — the data is
            # there, it is just not real, so say which.
            level_text="Placeholder" if is_placeholder else None,
            sub=("Example figures — replace with FINRA data to score this"
                 if is_placeholder else
                 (f"FINRA, {ms.latest_month:%b %Y}" if ms and ms.latest_month else "—")),
            delta_decimals=1,
        )

    st.divider()

    # -- Component breakdown ------------------------------------------------
    left, right = st.columns([3, 2])
    with left:
        st.markdown("#### Component scores")
        st.caption("Stress score 0–100 per component, with its model weight. "
                   "Sorted worst first.")
        ui.component_bars(a.components)

    with right:
        st.markdown("#### What is driving it")
        drivers = a.top_drivers[:4]
        if not drivers:
            st.caption("No components available.")
        for c in drivers:
            st.markdown(
                f"{ui.chip(c.level)} **{c.label}** — "
                f"{(c.score or 0) * 100:.0f}/100",
                unsafe_allow_html=True,
            )
            st.caption(c.note)


# ===========================================================================
# TAB 2 — CURRENCY & CARRY TRADE
# ===========================================================================

def tab_carry(m: mx.Metrics, a: scoring.RiskAssessment, window: int) -> None:
    st.markdown("### Currency & carry trade")
    st.caption(
        "The yen carry trade borrows in yen at near-zero cost and buys "
        "higher-yielding assets. When the yen strengthens, those positions "
        "lose money on the funding leg and get closed — which means selling "
        "the assets, wherever in the world they are."
    )

    carry = a.component("carry_fx")

    c1, c2, c3 = st.columns(3)
    with c1:
        ui.metric_card(
            "USDJPY", ui.fmt(m.usdjpy, 2),
            deltas=[("1d", m.usdjpy_1d), ("1w", m.usdjpy_1w), ("1m", m.usdjpy_1m)],
            good_direction="up", level=carry.level if carry else None,
            series=m.usdjpy_series, spark_days=window,
        )
    with c2:
        ui.metric_card(
            "US–JP 2y differential", ui.fmt(m.diff_2y, 2, "pp"),
            deltas=[("3m", m.diff_2y_change_3m)], good_direction=None,
            series=m.diff_2y_series, spark_days=window, delta_suffix="pp",
            sub=f"US {ui.fmt(m.us2y, 2)}% − JP {ui.fmt(m.jp2y, 2)}%",
        )
    with c3:
        ui.metric_card(
            "US–JP 10y differential", ui.fmt(m.diff_10y, 2, "pp"),
            good_direction=None, series=m.diff_10y_series, spark_days=window,
            sub=f"US {ui.fmt(m.us10y, 2)}% − JP {ui.fmt(m.jp10y, 2)}%",
        )

    # -- The specific warning the user asked for ---------------------------
    p = config.ESCALATION_PARAMS
    if (m.usdjpy_1w is not None and m.diff_2y is not None
            and m.usdjpy_1w < p["carry_unwind_usdjpy_1w"]
            and m.diff_2y > p["carry_unwind_min_diff"]):
        ui.alert(
            "high", "Carry unwind pattern detected",
            f"USDJPY is down {m.usdjpy_1w:.2f}% in a week while the 2-year "
            f"differential is still {m.diff_2y:.2f}pp wide. Yen strength that "
            "is <em>not</em> explained by rate convergence is the signature of "
            "position liquidation rather than an orderly repricing. This is the "
            "pattern that preceded the August 2024 unwind.",
        )
    elif m.usdjpy_1w is not None and m.usdjpy_1w < -1.0:
        ui.alert(
            "elevated", "Yen firming",
            f"USDJPY down {m.usdjpy_1w:.2f}% over the week. Not yet at the "
            f"{p['carry_unwind_usdjpy_1w']:.0f}% weekly threshold, but worth "
            "watching if it continues.",
        )
    else:
        ui.alert("low", "No carry unwind signature",
                 "Yen moves are within normal range relative to the rate "
                 "differential.")

    st.divider()

    # -- The main chart -----------------------------------------------------
    st.markdown("#### USDJPY against the yield differentials")
    view = st.radio(
        "Chart view", ["Stacked panels (recommended)", "Indexed overlay (=100)"],
        horizontal=True, label_visibility="collapsed",
    )
    if view.startswith("Stacked"):
        ui.carry_panel_chart(m.usdjpy_series, m.diff_2y_series,
                             m.diff_10y_series, days=window)
        st.caption(
            "Two panels on one shared time axis rather than a dual-axis "
            "overlay: with two y-scales, how closely the lines appear to track "
            "each other depends on where the scales are pinned, which is "
            "exactly the judgement you do not want an axis to make for you. "
            "Look for **divergence** — the yen strengthening while the "
            "differential stays wide."
        )
    else:
        ui.indexed_chart(
            {"USDJPY": m.usdjpy_series, "2y differential": m.diff_2y_series,
             "10y differential": m.diff_10y_series},
            days=window,
        )
        st.caption("Both series indexed to 100 at the start of the window, so "
                   "relative moves are directly comparable on one axis.")

    st.info(
        "**Note on the differential history:** the Japanese leg is a single "
        "manually-entered number, so the historical *shape* of the "
        "differential is driven by the US leg. That is a reasonable "
        "approximation — the US leg is far more volatile — but the level is "
        "only as current as the JGB yield you typed in the sidebar.",
        icon="ℹ️",
    )

    st.divider()

    # -- High-carry crosses -------------------------------------------------
    st.markdown("#### High-carry crosses")
    st.caption("These carry more yield than USDJPY and unwind harder. AUDJPY "
               "is the classic risk barometer; MXNJPY is the highest-carry.")

    cross_cols = st.columns(max(1, len(m.crosses)))
    for col, (name, data) in zip(cross_cols, m.crosses.items()):
        with col:
            dd = data["dd60"]
            lvl = "low"
            if dd is not None:
                lvl = "high" if dd <= -8 else ("elevated" if dd <= -2 else "low")
            ui.metric_card(
                name, ui.fmt(data["level"], 2),
                deltas=[("1d", data["d1"]), ("1w", data["w1"]), ("1m", data["m1"])],
                good_direction="up", level=lvl, series=data["series"],
                spark_days=window,
                sub=f"{ui.fmt(dd, 1, '%')} from 60-day high",
            )

    if m.crosses:
        ui.indexed_chart(
            {name: d["series"] for name, d in m.crosses.items()},
            title="Carry crosses, indexed to 100", days=window,
        )
        with st.expander("Table view"):
            rows = [{
                "Cross": name, "Level": round(d["level"], 3) if d["level"] else None,
                "1d %": round(d["d1"], 2) if d["d1"] is not None else None,
                "1w %": round(d["w1"], 2) if d["w1"] is not None else None,
                "1m %": round(d["m1"], 2) if d["m1"] is not None else None,
                "vs 60d high %": round(d["dd60"], 2) if d["dd60"] is not None else None,
            } for name, d in m.crosses.items()]
            ui.table_view(pd.DataFrame(rows))


# ===========================================================================
# TAB 3 — INTEREST RATES & POLICY
# ===========================================================================

def tab_rates(m: mx.Metrics, a: scoring.RiskAssessment, window: int) -> None:
    st.markdown("### Interest rates & policy")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ui.metric_card("US 2-year", ui.fmt(m.us2y, 2, "%"),
                       deltas=[("1w", m.us2y_1w)], good_direction=None,
                       series=m.us2y_series, spark_days=window,
                       delta_suffix="pp", sub="Policy expectations")
    with c2:
        ui.metric_card("US 10-year", ui.fmt(m.us10y, 2, "%"),
                       deltas=[("1w", m.us10y_1w)], good_direction=None,
                       series=m.us10y_series, spark_days=window,
                       delta_suffix="pp", sub="Growth + term premium")
    with c3:
        ui.metric_card("US 30-year", ui.fmt(m.us30y, 2, "%"),
                       deltas=[("1w", m.us30y_1w)], good_direction=None,
                       series=m.us30y_series, spark_days=window,
                       delta_suffix="pp", sub="Fiscal / duration risk")
    with c4:
        ui.metric_card("Japan 10-year", ui.fmt(m.jp10y, 2, "%"),
                       sub=f"Source: {m.jp10y_source}")

    c1, c2, c3 = st.columns(3)
    with c1:
        curve = a.component("curve")
        slope_note = "Inverted" if (m.curve_10_2 or 0) < 0 else "Positive"
        ui.metric_card(
            "Yield curve (10y − 2y)", ui.fmt(m.curve_10_2, 2, "pp"),
            deltas=[("3m", m.curve_change_3m)], good_direction=None,
            level=curve.level if curve else None, series=m.curve_10_2_series,
            spark_days=window, delta_suffix="pp", sub=slope_note,
        )
    with c2:
        rv = a.component("rate_vol")
        ui.metric_card(
            "Treasury volatility", ui.fmt(m.rate_vol_level, 1),
            deltas=[("pctile", m.rate_vol_pctile)], good_direction="down",
            level=rv.level if rv else None, series=m.rate_vol_series,
            spark_days=window, delta_decimals=0, delta_suffix="th",
            sub=m.rate_vol_source,
        )
    with c3:
        ui.metric_card(
            "Policy rate gap", ui.fmt(m.policy_gap, 2, "pp"),
            sub=(f"Fed {ui.fmt(m.fed_funds, 2)}% · BOJ {ui.fmt(m.boj_rate, 2)}% "
                 f"(BOJ entered manually)"),
        )

    if m.curve_change_3m is not None and m.curve_change_3m > 0.25 and (m.curve_10_2 or 0) < 0.5:
        ui.alert(
            "elevated", "Curve steepening from a flat/inverted base",
            f"The 10y−2y slope has moved {m.curve_change_3m:+.2f}pp in three "
            "months from a low base. Historically, recessions have begun as "
            "the curve <em>re-steepens</em> out of inversion (the front end "
            "falling as cuts get priced), not while it is inverted.",
        )

    st.divider()
    st.markdown("#### Yield levels")
    ui.line_chart(
        {"US 2y": m.us2y_series, "US 10y": m.us10y_series, "US 30y": m.us30y_series},
        title="US Treasury yields (%)", days=window, unit="%", height=300,
    )
    ui.line_chart(
        {"10y − 2y": m.curve_10_2_series}, title="Yield curve slope (pp)",
        days=window, unit="pp", height=220, hline=0.0, hline_label="inversion",
    )

    st.divider()

    # -- Central bank calendar ---------------------------------------------
    st.markdown("#### Upcoming policy meetings")
    st.caption(
        "⚠️ These dates are **hardcoded approximations** in `config.py` "
        "(`FOMC_MEETINGS` / `BOJ_MEETINGS`). Verify against federalreserve.gov "
        "and boj.or.jp — a BOJ surprise is the single most likely trigger for "
        "a carry unwind, so being off by a week matters."
    )

    events = (ui.next_events(config.FOMC_MEETINGS, "FOMC", 3)
              + ui.next_events(config.BOJ_MEETINGS, "BOJ", 3)
              + [(dt.date.fromisoformat(d), (dt.date.fromisoformat(d) - dt.date.today()).days, lbl)
                 for d, lbl in config.OTHER_EVENTS
                 if dt.date.fromisoformat(d) >= dt.date.today()])
    events = sorted(events)[:8]

    if events:
        rows = [{
            "Date": d.isoformat(),
            "Days away": days,
            "Event": label,
            "Window": "⚠️ within 2 weeks" if days <= 14 else "",
        } for d, days, label in events]
        ui.table_view(pd.DataFrame(rows))
    else:
        st.caption("No upcoming events in the hardcoded calendar — update config.py.")


# ===========================================================================
# TAB 4 — COMMODITIES & INFLATION
# ===========================================================================

def tab_commodities(m: mx.Metrics, a: scoring.RiskAssessment, window: int) -> None:
    st.markdown("### Commodities & inflation proxies")
    st.caption(
        "Oil is scored on the SIZE of its move, not the direction: a spike is "
        "a supply/inflation shock that constrains central banks, a collapse is "
        "a demand/growth shock. Both are macro events."
    )

    comm = a.component("commodity")
    c1, c2, c3 = st.columns(3)
    with c1:
        ui.metric_card(
            "WTI crude", ui.fmt(m.wti, 2, prefix="$"),
            deltas=[("1w", m.wti_1w), ("1m", m.wti_1m)], good_direction=None,
            level=comm.level if comm else None, series=m.wti_series,
            spark_days=window,
            sub=(f"20d realised vol {ui.fmt(m.wti_vol, 1, '%')} "
                 f"({ui.fmt(m.wti_vol_pctile, 0)}th pctile of 3y)"),
        )
    with c2:
        ui.metric_card("Gold", ui.fmt(m.gold, 2, prefix="$"),
                       deltas=[("1w", m.gold_1w)], good_direction=None,
                       series=m.gold_series, spark_days=window,
                       sub="Rising gold + rising real rates = stress hedging")
    with c3:
        ui.metric_card("Copper", ui.fmt(m.copper, 3, prefix="$"),
                       deltas=[("1w", m.copper_1w)], good_direction="up",
                       series=m.copper_series, spark_days=window,
                       sub="Global growth proxy")

    # -- Oil volatility note ------------------------------------------------
    if m.wti_vol_pctile is not None:
        if m.wti_vol_pctile >= 90:
            ui.alert("high", "Oil volatility at an extreme",
                     f"20-day realised volatility is at the "
                     f"{m.wti_vol_pctile:.0f}th percentile of the last three "
                     "years. Energy shocks feed straight into inflation "
                     "expectations and reduce the room central banks have to "
                     "respond to a growth scare.")
        elif m.wti_vol_pctile >= 60:
            ui.alert("elevated", "Oil volatility above normal",
                     f"20-day realised volatility at the {m.wti_vol_pctile:.0f}th "
                     "percentile of the last three years.")
        else:
            ui.alert("low", "Oil volatility normal",
                     f"20-day realised volatility at the {m.wti_vol_pctile:.0f}th "
                     "percentile of the last three years — no energy shock in "
                     "progress.")

    st.divider()
    ui.indexed_chart(
        {"WTI": m.wti_series, "Gold": m.gold_series, "Copper": m.copper_series},
        title="Commodities, indexed to 100 at window start", days=window, height=310,
    )
    st.caption(
        "Indexed to a common base so three very different price scales share "
        "one honest axis. Gold outperforming copper is the classic "
        "'defensive over cyclical' tell."
    )

    if m.copper_series is not None and m.gold_series is not None:
        ratio = (m.copper_series / m.gold_series).dropna()
        ui.line_chart({"Copper / Gold": ratio},
                      title="Copper-to-gold ratio (growth vs fear)",
                      days=window, height=220)
        st.caption("Falling ratio = the market is paying up for safety over "
                   "industrial growth.")


# ===========================================================================
# TAB 5 — LEVERAGE & POSITIONING
# ===========================================================================

def tab_leverage(m: mx.Metrics, a: scoring.RiskAssessment) -> None:
    st.markdown("### Leverage & positioning")
    st.caption(
        "Leverage does not cause a selloff — it decides how violent one "
        "becomes. Record margin debt still rising is the condition under which "
        "an ordinary 5% drop turns into a forced-selling 15%."
    )

    ms = m.margin

    if ms is None or ms.latest_debit_musd is None:
        ui.alert("na", "No margin debt data",
                 "Add data below or upload a CSV. This component is currently "
                 "excluded from the risk score.")
    elif ms.is_placeholder:
        ui.alert(
            "elevated", "Placeholder data in use",
            "The margin figures below are <strong>illustrative examples, not "
            "real FINRA data</strong>. The leverage component is excluded from "
            "the risk score until you enter real numbers and set "
            "<code>is_placeholder</code> to FALSE.",
        )

    lv = a.component("leverage")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        val = f"${ms.latest_debit_musd / 1_000_000:.3f}T" if ms and ms.latest_debit_musd else "—"
        ui.metric_card(
            "Margin debt", val,
            level=lv.level if lv else None,
            level_text=("Placeholder" if ms and ms.is_placeholder
                        and ms.latest_debit_musd else None),
            sub=(f"FINRA debit balances, {ms.latest_month:%B %Y}"
                 if ms and ms.latest_month else "—"),
        )
    with c2:
        ui.metric_card(
            "Year-over-year", ui.fmt(ms.yoy_pct if ms else None, 1, "%", signed=True),
            deltas=[("MoM", ms.mom_pct if ms else None)], good_direction="down",
            delta_decimals=1, sub="Above +30% YoY has marked past manias",
        )
    with c3:
        ui.metric_card(
            "vs record high", ui.fmt(ms.pct_of_peak if ms else None, 1, "%"),
            sub=(f"Peak: {ms.peak_month:%b %Y}" if ms and ms.peak_month is not None else "—"),
        )
    with c4:
        ui.metric_card(
            "% of S&P 500 market cap",
            ui.fmt(ms.pct_of_spx_mktcap if ms else None, 2, "%"),
            sub=f"Approx. — divisor {config.SP500_DIVISOR_BN} $bn/pt in config.py",
        )

    # -- The warning --------------------------------------------------------
    if ms and ms.usable and ms.pct_of_peak is not None and ms.yoy_pct is not None:
        if ms.pct_of_peak >= 99 and ms.yoy_pct >= 25:
            ui.alert(
                "high", "Record margin debt, rising fast",
                f"Margin debt is at {ms.pct_of_peak:.1f}% of its all-time high "
                f"and up {ms.yoy_pct:.1f}% year over year. Peak leverage plus "
                "rapid expansion is the classic pre-drawdown configuration — "
                "the marginal buyer is borrowing, which means the marginal "
                "seller will be forced.",
            )
        elif ms.pct_of_peak >= 95 and ms.yoy_pct >= 15:
            ui.alert("elevated", "Leverage building",
                     f"Margin debt is at {ms.pct_of_peak:.1f}% of its record and "
                     f"growing {ms.yoy_pct:.1f}% year over year.")
        elif ms.yoy_pct < 0 and ms.pct_of_peak < 95:
            ui.alert("elevated", "Leverage contracting from a peak",
                     f"Margin debt is {100 - ms.pct_of_peak:.1f}% below its "
                     "record and falling year over year. Deleveraging that has "
                     "already started often coincides with, rather than "
                     "precedes, equity weakness.")
        else:
            ui.alert("low", "Leverage not at an extreme",
                     f"{ms.pct_of_peak:.1f}% of record, {ms.yoy_pct:+.1f}% YoY.")

    if ms and ms.net_credit_musd is not None:
        state = ("net borrowers" if ms.net_credit_musd < 0 else "net creditors")
        st.caption(
            f"**Investor credit balances:** free credit minus margin debt is "
            f"${ms.net_credit_musd / 1_000_000:+.3f}T — investors are {state}. "
            "A deeply negative number means there is little idle cash to buy a dip."
        )

    st.divider()

    # -- Charts -------------------------------------------------------------
    if ms and not ms.frame.empty:
        frame = ms.frame.set_index("month")
        c1, c2 = st.columns(2)
        with c1:
            ui.bar_chart(frame["debit_balances_musd"] / 1_000_000,
                         title="Margin debt ($ trillions)", unit="T", height=280)
        with c2:
            yoy = frame["debit_balances_musd"].pct_change(12) * 100
            ui.line_chart({"YoY %": yoy.dropna()},
                          title="Margin debt, year-over-year % change",
                          days=3650, height=280, hline=0.0, unit="%")

    st.divider()

    # -- Data entry ---------------------------------------------------------
    st.markdown("#### Update the data")
    st.caption(
        "FINRA publishes monthly, about three weeks after month end: "
        "finra.org/investors/insights/investing/margin-statistics — "
        "units are **millions of USD**. Edit the table, then Save. Set "
        "`is_placeholder` to FALSE on rows you have verified."
    )

    edited = st.data_editor(
        ms.frame if ms and not ms.frame.empty else mdbt.load_csv(str(mdbt.CSV_PATH)),
        num_rows="dynamic", width="stretch", key="margin_editor",
        column_config={
            "month": st.column_config.DateColumn("Month", format="YYYY-MM-DD"),
            "debit_balances_musd": st.column_config.NumberColumn(
                "Margin debt ($mn)", format="%d"),
            "free_credit_cash_musd": st.column_config.NumberColumn(
                "Free credit, cash ($mn)", format="%d"),
            "free_credit_margin_musd": st.column_config.NumberColumn(
                "Free credit, margin ($mn)", format="%d"),
            "is_placeholder": st.column_config.CheckboxColumn(
                "Placeholder?", help="Tick = example data, excluded from the score"),
        },
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Save to CSV", width="stretch"):
            try:
                mdbt.CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
                mdbt.CSV_PATH.write_bytes(mdbt.to_csv_bytes(edited))
                st.cache_data.clear()
                # Drop the editor's widget state so it re-reads from the file
                # instead of replaying the edits on top of the saved data.
                st.session_state.pop("margin_editor", None)
                st.success("Saved. Re-scoring…")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not write the file: {exc}. Use Download instead.")
    with c2:
        st.download_button(
            "Download CSV", data=mdbt.to_csv_bytes(edited),
            file_name="margin_debt.csv", mime="text/csv",
            width="stretch",
        )
    with c3:
        uploaded = st.file_uploader("Upload CSV", type=["csv"],
                                    label_visibility="collapsed")
        if uploaded is not None:
            # The uploader keeps returning the same file on every rerun, so
            # without this signature check the st.rerun() below would loop
            # forever, rewriting the CSV each pass.
            signature = (uploaded.name, uploaded.size)
            if st.session_state.get("_margin_upload_sig") != signature:
                st.session_state["_margin_upload_sig"] = signature
                parsed = mdbt.parse_uploaded(uploaded)
                if parsed.empty:
                    st.error("Could not parse that file — check the column names.")
                else:
                    mdbt.CSV_PATH.write_bytes(mdbt.to_csv_bytes(parsed))
                    st.cache_data.clear()
                    st.session_state.pop("margin_editor", None)
                    st.success(f"Loaded {len(parsed)} rows.")
                    st.rerun()

    st.info(
        "**On hosted deployments** (Streamlit Community Cloud and similar) the "
        "filesystem resets when the app restarts. Use *Download CSV* to keep "
        "your copy, and commit it to the repo to make it permanent.",
        icon="ℹ️",
    )


# ===========================================================================
# TAB 6 — SENTIMENT & STRESS
# ===========================================================================

def tab_stress(m: mx.Metrics, a: scoring.RiskAssessment, window: int) -> None:
    st.markdown("### Sentiment & stress")

    ev = a.component("equity_vol")
    cr = a.component("credit")

    c1, c2, c3 = st.columns(3)
    with c1:
        ui.metric_card("VIX", ui.fmt(m.vix, 2),
                       level=ev.level if ev else None, series=m.vix_series,
                       spark_days=window, sub="30-day implied equity volatility")
    with c2:
        note = "—"
        lvl = None
        if m.vix_ratio is not None:
            if m.vix_ratio > 1.0:
                note, lvl = "BACKWARDATION — acute near-term stress", "high"
            elif m.vix_ratio > 0.95:
                note, lvl = "Flat — the curve is warning", "elevated"
            else:
                note, lvl = "Contango — normal", "low"
        ui.metric_card("VIX term structure", ui.fmt(m.vix_ratio, 3),
                       level=lvl, sub=f"VIX / VIX3M · {note}")
    with c3:
        credit_val = (ui.fmt(m.hy_oas, 2, "pp") if m.credit_kind == "oas"
                      else ui.fmt(m.credit_series.iloc[-1] if m.credit_series is not None else None, 3))
        ui.metric_card(
            "High-yield spread", credit_val,
            deltas=[("1m", m.hy_oas_change_1m)], good_direction="down",
            level=cr.level if cr else None, series=m.credit_series,
            spark_days=window, delta_suffix="pp", sub=m.credit_source,
        )

    st.markdown("**Term structure, in plain English:** VIX3M above VIX (ratio "
                "below 1) is the normal state — the market always charges more "
                "for longer-dated uncertainty. When the ratio goes above 1, "
                "traders are paying more to hedge the next month than the next "
                "quarter, which only happens when something is breaking now.")

    st.divider()

    # -- Cross-asset correlation regime -------------------------------------
    st.markdown("#### Cross-asset correlation regime")
    corr = m.stock_bond_corr
    if corr is None:
        st.caption("Correlation unavailable — needs both SPX and TLT history.")
    else:
        if corr > 0.3:
            lvl, desc = "high", (
                "Stocks and bonds are moving <strong>together</strong>. Treasuries "
                "are not hedging equity risk right now, so a 60/40-style portfolio "
                "is carrying more effective risk than its history implies, and "
                "diversification will not save you in a drawdown. This is the "
                "inflation-shock regime."
            )
        elif corr > 0.0:
            lvl, desc = "elevated", (
                "Weakly positive stock/bond correlation. The bond hedge is "
                "impaired but not absent."
            )
        elif corr > -0.3:
            lvl, desc = "elevated", (
                "Correlation is near zero — bonds are neither hedging nor "
                "hurting. Transitional regime."
            )
        else:
            lvl, desc = "low", (
                "Solidly negative correlation — bonds are hedging equities as "
                "they do in a growth-scare regime. Diversification is working."
            )
        ui.alert(lvl, f"60-day stock/bond correlation: {corr:+.2f}", desc)

    st.divider()
    ui.line_chart({"VIX": m.vix_series}, title="VIX", days=window, height=250,
                  hline=20, hline_label="20")

    if m.credit_series is not None:
        label = ("High-yield OAS (pp)" if m.credit_kind == "oas"
                 else "HYG / LQD ratio")
        ui.line_chart({label: m.credit_series}, title=label, days=window, height=250)
        st.caption(
            "Credit usually reprices before equities: high-yield borrowers feel "
            "a funding squeeze before shareholders feel an earnings one."
        )

    if m.spx_series is not None:
        ui.line_chart({"S&P 500": m.spx_series}, title="S&P 500", days=window,
                      height=250)
        st.caption(
            f"Currently {ui.fmt(m.spx_drawdown, 1, '%')} from its 1-year high. "
            "Note that price is a *confirming* indicator here — by the time the "
            "index has moved, the signals above have usually already fired."
        )


# ===========================================================================
# TAB 7 — WATCHLIST
# ===========================================================================

def tab_watchlist() -> None:
    st.markdown("### Key events & watchlist")

    wl = load_watchlist()

    st.markdown("#### Your notes")
    st.caption(
        "Token unlocks, earnings that matter, geopolitical dates, positions "
        "you want to trim on a signal. Saved to `data/watchlist.json`."
    )
    notes = st.text_area(
        "Notes", value=wl.get("notes", ""), height=220,
        label_visibility="collapsed",
        placeholder=(
            "e.g.\n"
            "- BOJ Sep meeting: risk of another hike, watch USDJPY into it\n"
            "- Trim NDX exposure 25% if composite score > 62 for 3 straight days\n"
            "- Large lockup expiry <TICKER> mid-month\n"
            "- Watch: US 2y below 3.5% would compress the JP differential fast"
        ),
    )
    c1, c2 = st.columns([1, 4])
    with c1:
        if st.button("Save notes", width="stretch", type="primary"):
            wl["notes"] = notes
            if save_watchlist(wl):
                st.success("Saved.")
            else:
                st.warning("Could not write to disk (read-only host?). "
                           "Copy your notes elsewhere.")
    with c2:
        if wl.get("updated"):
            st.caption(f"Last saved {wl['updated']}")

    st.divider()

    # -- AI capex reminder --------------------------------------------------
    st.markdown("#### AI capex & growth-contribution check")
    st.markdown(
        """
A structural reminder rather than a live feed — these are the questions to
re-ask each quarter, in the spirit of the Bridgewater-style analysis of how
much current growth is coming from a single capital-spending cycle:

- **How much of GDP growth is AI-related capex?** When a large share of
  measured growth comes from data-centre construction, chips and power, the
  economy is more cyclical than headline resilience suggests. Capex cycles
  turn fast and they turn together.
- **Is that capex debt-financed or cash-financed?** Hyperscalers spending free
  cash flow is a very different systemic risk from vendor financing, private
  credit, and SPV structures. Watch the shift toward borrowed funding — that
  is when a capex slowdown becomes a credit event.
- **Are the returns showing up?** Capex justified by future revenue is fine
  until the revenue timeline slips. Watch for depreciation schedules
  lengthening — a sign of earnings being managed rather than earned.
- **Concentration:** when a handful of names drive both index earnings *and*
  index weight, the diversification in a broad index fund is smaller than it
  appears, and correlated selling hits everything at once.
- **The energy link:** AI capex is a power story too. It ties the tech cycle
  to the commodity and rates picture on the other tabs.

**Why this sits in a systematic-risk dashboard:** every other signal here is
about the *plumbing* of leverage. This one is about whether the underlying
growth story is broad or narrow. A narrow one turns a valuation reset into a
macro event.
        """
    )

    st.divider()
    st.markdown("#### Standing checklist")
    st.markdown(
        """
- [ ] Central bank meetings in the next 2 weeks? (see the Rates tab)
- [ ] Any BOJ policy surprise risk — the number one carry-unwind trigger
- [ ] Month-end / quarter-end rebalancing flows
- [ ] Options expiry (third Friday) — gamma effects around big levels
- [ ] Large token or share unlocks in positions you hold
- [ ] Geopolitical dates: elections, sanction deadlines, OPEC meetings
- [ ] Earnings from the handful of names that carry index earnings growth
        """
    )


# ===========================================================================
# TAB 8 — METHODOLOGY
# ===========================================================================

def tab_methodology(a: scoring.RiskAssessment) -> None:
    st.markdown("### Methodology & notes")

    with st.expander("Why the yen carry trade and rate differentials matter",
                     expanded=True):
        st.markdown(
            """
For three decades Japan has had the lowest policy rate in the developed world.
That makes the yen the world's funding currency: borrow yen at near-zero,
convert, and buy anything that yields more — US Treasuries, Mexican bonds,
Australian dollars, US tech equities. The position pays the yield difference
plus whatever the asset does.

Two things make this systemically important rather than merely interesting:

1. **It is enormous and invisible.** The trade is spread across hedge funds,
   Japanese institutions, and retail margin accounts, most of it off-balance
   sheet. Nobody knows the true size, which means nobody can price the unwind
   risk properly.
2. **It unwinds all at once.** The position is short yen and long risk assets.
   When the yen strengthens, you lose on the funding leg *and* face a margin
   call, so you sell the asset and buy back yen — which strengthens the yen
   further and triggers the next person. It is a reflexive loop, and it does
   not care which asset you own.

**What to watch, and why the combination matters more than either part:**

- A **wide differential** is not a risk signal. It is the *fuel* — it tells you
  the position is large and profitable, so there is a lot to unwind.
- A **narrowing differential** (the Fed cutting, the BOJ hiking) removes the
  reason to hold the trade and starts an orderly exit.
- **Yen strengthening sharply while the differential is still wide** is the
  dangerous case. Nothing fundamental has changed, so the move is *positioning*
  — someone is being forced out. That is what happened in August 2024, when a
  BOJ hike alongside weak US data caused a violent global unwind well out of
  proportion to the rate move itself.

This dashboard flags exactly that case as the `carry_unwind` escalation.
            """
        )

    with st.expander("Why high margin debt plus strong risk assets is a warning"):
        st.markdown(
            """
Margin debt is not a timing tool. Its level tells you almost nothing about
*when* a drawdown starts — leverage can build for years. What it tells you is
**how a drawdown will behave once it starts**.

The mechanism: margin borrowing is collateralised by the securities it buys.
When prices fall, the collateral falls with the loan. Below a maintenance
threshold the broker issues a margin call, and if it is not met they liquidate
— at market, immediately, regardless of value. That selling pushes prices down,
which triggers the next margin call.

This is why leverage converts a normal correction into a cascade. A 5% drop in
an unleveraged market is a 5% drop. The same drop with record margin debt is
the first 5% of a much larger one, because the second leg is mechanical rather
than discretionary.

The specific configuration that matters:

- **Record levels + rapid growth (>25-30% YoY)** — the marginal buyer is
  borrowing to buy. Every past mania looked like this at the top.
- **Record levels + rising volatility** — brokers raise margin requirements
  when volatility rises, forcing deleveraging even without a price decline.
  This dashboard flags that combination explicitly.
- **Negative net credit balances** — investors' idle cash is far below their
  borrowings, so there is no dry powder to buy the dip.

The honest caveat: margin debt is monthly and published with a three-week lag.
By the time a fall shows up in the data, the deleveraging is well underway. Use
it to understand *fragility*, not to time an exit.
            """
        )

    with st.expander("How to read the overall regime score"):
        st.markdown(
            f"""
**The mechanics, in full.**

*Step 1 — every signal becomes a 0-1 stress score.* Each raw number is compared
against two thresholds in `config.THRESHOLDS`: a *calm* value that scores 0 and
a *stressed* value that scores 1, with a straight line between them. It works in
both directions, so "USDJPY down 7%" and "VIX at 32" both land at 1.0.

*Step 2 — signals blend into eight components* using `config.SUB_WEIGHTS`.
Within a component, rates of change are generally weighted above levels: a
spread widening 100bp in a month tells you more than a spread that has been
wide for a year.

*Step 3 — components blend into the composite* using `config.WEIGHTS`:

| Component | Weight | Why |
|---|---|---|
| Yen carry / FX | {config.WEIGHTS['carry_fx']:.0f} | The transmission channel with the fastest global reach |
| Equity volatility | {config.WEIGHTS['equity_vol']:.0f} | Where stress becomes visible and forces deleveraging |
| Credit spreads | {config.WEIGHTS['credit']:.0f} | Repricing usually leads equities |
| Leverage | {config.WEIGHTS['leverage']:.0f} | Sets the severity of any drawdown |
| Rate differentials | {config.WEIGHTS['rate_diff']:.0f} | The carry trade's reason to exist |
| Treasury volatility | {config.WEIGHTS['rate_vol']:.0f} | Rate vol precedes cross-asset vol |
| Commodities | {config.WEIGHTS['commodity']:.0f} | Constrains the policy response |
| Yield curve | {config.WEIGHTS['curve']:.0f} | Slow-moving; small weight by design |

**A component with no data is dropped and the rest are re-weighted.** A dead
feed never silently scores zero. Current coverage: **{a.coverage_pct:.0f}%** of
total model weight.

*Step 4 — escalation rules can floor the score.* A weighted average is poor at
combinations: a wide differential is not stress, a falling USDJPY is not
necessarily stress, but both together moving fast is the most reliable setup in
this dashboard. Four rules in `config.ESCALATIONS` catch these patterns and
force a minimum score regardless of the average.

*Step 5 — the bands:*

- **Low (0–{config.REGIME_BANDS['elevated_above']:.0f})** — normal conditions.
  Nothing to do.
- **Elevated ({config.REGIME_BANDS['elevated_above']:.0f}–{config.REGIME_BANDS['high_above']:.0f})**
  — deterioration underway. Stop adding leverage, stop adding to positions,
  tighten stops. This is a *don't make it worse* signal, not a sell signal.
- **High ({config.REGIME_BANDS['high_above']:.0f}+)** — several independent
  systems stressed at once, or an escalation rule firing. Consider actively
  reducing equity exposure.

**Honest limitations — read these once.**

- The thresholds are **judgement, not optimisation.** Nothing here is fitted to
  historical returns, which means it will not be perfectly calibrated — but it
  also means it is not overfitted to crises that will not repeat.
- **False positives are the design choice.** A risk monitor that never flags
  early is useless. Expect amber readings that resolve into nothing.
- **It cannot see what is not in the data**: an exchange failure, a sovereign
  default, a war starting on a Sunday.
- **Margin debt lags by weeks**; Japanese yields are whatever you last typed.
- **Do not trade the score mechanically.** It describes the environment. The
  position sizing decision is still yours.
            """
        )

    with st.expander("Data sources and their limitations"):
        st.markdown(
            """
| What | Source | Refresh | Watch out for |
|---|---|---|---|
| FX (USDJPY, crosses) | Yahoo Finance | Intraday, ~15m delay | Weekend gaps |
| US Treasury yields | FRED (DGS2/10/30) | Daily, ~1 business day lag | Not intraday |
| Yield curve | FRED (T10Y2Y) | Daily | — |
| Fed funds | FRED (DFF) | Daily | Effective rate, not the target range |
| High-yield spread | FRED (BAMLH0A0HYM2) | Daily, 1 day lag | Falls back to HYG/LQD |
| VIX & VIX3M | Yahoo Finance | Intraday | VIX3M occasionally unavailable |
| Treasury volatility | Yahoo `^MOVE`, else a realised-vol proxy | Daily | Proxy is scored as a percentile, so the units do not need to match |
| Commodities | Yahoo futures (CL=F, GC=F, HG=F) | Intraday | Front-month roll causes small jumps |
| **Japan yields** | **Manual entry** | **When you type it** | **No free daily JGB feed exists** |
| **BOJ policy rate** | **Manual entry** | **When you type it** | — |
| **Margin debt** | **Manual / CSV from FINRA** | **Monthly, ~3 week lag** | Placeholder data is excluded from scoring |
| Central bank dates | Hardcoded in `config.py` | Never — verify yourself | Approximate |

**Everything degrades gracefully.** If a feed dies, the dashboard shows "no
data", drops that component, and re-weights the rest rather than crashing or
silently scoring zero.
            """
        )

    with st.expander("Changing the thresholds"):
        st.markdown(
            """
Everything tunable lives in **`config.py`**:

- **`THRESHOLDS`** — `(calm, stress)` pairs per signal. Widen the gap to make a
  signal less twitchy; move both toward zero to make it more sensitive.
- **`WEIGHTS`** — how much each component matters. The sidebar sliders override
  these for the current session; edit the file to make it permanent.
- **`SUB_WEIGHTS`** — the blend within each component.
- **`ESCALATIONS` / `ESCALATION_PARAMS`** — the pattern rules and their trigger
  levels.
- **`REGIME_BANDS`** — where Low becomes Elevated becomes High.
- **`FOMC_MEETINGS` / `BOJ_MEETINGS`** — the calendar.
- **`SP500_DIVISOR_BN`** — the market cap approximation.

A reasonable first customisation: if you find yourself ignoring amber readings,
raise `REGIME_BANDS['elevated_above']` until amber means something to you again.
An alert you have learned to ignore is worse than no alert.
            """
        )


# ===========================================================================
# MAIN
# ===========================================================================

def main() -> None:
    ui.inject_css()

    # -- Header -------------------------------------------------------------
    head_l, head_r = st.columns([3, 2])
    with head_l:
        st.markdown("## Systematic Risk Monitor")
        st.caption("Yen carry · rate differentials · leverage · credit · commodities")

    # -- Load ---------------------------------------------------------------
    # Data is loaded BEFORE the sidebar so the Japanese-rate inputs can be
    # seeded from FRED rather than from a hardcoded constant. Streamlit places
    # sidebar widgets by container, not by call order, so this is safe.
    with st.spinner("Loading market data…"):
        md = ds.load_market_data()
        margin_raw = mdbt.load_csv(str(mdbt.CSV_PATH))

    if md.yahoo.empty and md.fred.empty:
        st.error(
            "No market data could be loaded. Check your internet connection, "
            "then press **Refresh data** below. If you are behind a proxy or "
            "firewall, Yahoo Finance and FRED both need outbound HTTPS."
        )
        if st.button("Refresh data"):
            st.cache_data.clear()
            st.rerun()
        return

    manual = render_sidebar(ds.jp_rate_seeds(md), md=md)
    window = manual["_window"]
    weights = manual["_weights"]

    spx_level = md.latest(md.yf("SPX"))
    margin_stats = mdbt.analyse(margin_raw, spx_level)
    m = mx.compute(md, manual, margin_stats)
    assessment = scoring.assess(m, weight_overrides=weights)

    # -- Freshness line -----------------------------------------------------
    with head_r:
        latest_dates = [d for d in (
            md.as_of(md.yf("USDJPY")), md.as_of(md.fr("US10Y")),
            md.as_of(md.yf("VIX")),
        ) if d is not None]
        newest = max(latest_dates).isoformat() if latest_dates else "unknown"
        st.markdown(
            f"<div style='text-align:right;padding-top:14px'>"
            f"<div style='font-size:0.75rem;opacity:0.6'>"
            f"Fetched {md.fetched_at:%Y-%m-%d %H:%M} · newest observation {newest}"
            f"</div></div>",
            unsafe_allow_html=True,
        )
        if st.button("↻ Refresh data", width="stretch"):
            st.cache_data.clear()
            st.rerun()

    # Yahoo rate-limits aggressively (HTTP 429), and shared cloud IPs get hit
    # hardest — so a totally empty Yahoo feed alongside a working FRED feed is
    # a specific, common, self-healing condition. Say so plainly rather than
    # leaving the user to wonder why half the cards are blank.
    if md.yahoo.empty and not md.fred.empty:
        st.warning(
            "**Yahoo Finance returned nothing** (usually HTTP 429 rate "
            "limiting — common on shared or cloud IP addresses). FX, VIX and "
            "commodity cards are blank and their components are excluded from "
            "the score. FRED data below is unaffected. This normally clears "
            "within an hour; press **Refresh data** to retry.",
            icon="⚠️",
        )
    elif assessment.missing:
        st.caption(f"⚠️ Unavailable right now: {', '.join(assessment.missing)}. "
                   "Model re-weighted over the remaining components.")

    # -- Tabs ---------------------------------------------------------------
    tabs = st.tabs([
        "Overview", "Carry & FX", "Rates", "Commodities",
        "Leverage", "Stress", "Watchlist", "Methodology",
    ])
    with tabs[0]:
        tab_overview(m, assessment)
    with tabs[1]:
        tab_carry(m, assessment, window)
    with tabs[2]:
        tab_rates(m, assessment, window)
    with tabs[3]:
        tab_commodities(m, assessment, window)
    with tabs[4]:
        tab_leverage(m, assessment)
    with tabs[5]:
        tab_stress(m, assessment, window)
    with tabs[6]:
        tab_watchlist()
    with tabs[7]:
        tab_methodology(assessment)

    st.divider()
    st.caption(
        "Personal monitoring tool. Data from Yahoo Finance, FRED and FINRA — "
        "free sources, provided without warranty and occasionally wrong. "
        "Not investment advice."
    )


if __name__ == "__main__":
    main()
