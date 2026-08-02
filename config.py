"""
config.py — Every tunable knob for the Systematic Risk Macro Dashboard.
=======================================================================

This is the ONLY file you should need to edit to change the dashboard's
behaviour. Tickers, data series, risk thresholds, component weights and the
central-bank calendar all live here.

HOW THE RISK SCORE WORKS (short version — full write-up in the app's
"Methodology / Notes" expander):

    * Each signal is converted to a 0.0 -> 1.0 "stress score" by comparing its
      current value against two thresholds: CALM_AT and STRESS_AT.
          score = 0.0  when the value is at (or beyond) CALM_AT
          score = 1.0  when the value is at (or beyond) STRESS_AT
          score ramps linearly in between
      This works in either direction: if STRESS_AT < CALM_AT, the signal is
      "lower is worse" (e.g. USDJPY falling = yen strengthening = stress).

    * Signals are combined into a weighted average, rescaled 0-100.
      Any signal whose data is unavailable is dropped and the remaining
      weights are re-normalised, so a missing feed never silently scores 0.

    * A small set of ESCALATION rules can force the regime higher regardless
      of the weighted average. These encode the "this specific combination is
      dangerous" patterns that an average would wash out — above all, the yen
      carry unwind.

To make the dashboard more or less trigger-happy, edit THRESHOLDS below.
To change what matters most, edit WEIGHTS.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. DATA SOURCES
# ---------------------------------------------------------------------------

# --- Yahoo Finance tickers -------------------------------------------------
# Keys are the internal names used throughout the app; values are the Yahoo
# symbols. If a symbol ever stops resolving, the app degrades gracefully and
# shows "n/a" rather than crashing.
YF_TICKERS: dict[str, str] = {
    # FX — the carry-trade complex
    "USDJPY": "USDJPY=X",     # the funding pair everyone watches
    "AUDJPY": "AUDJPY=X",     # classic high-beta carry cross
    "NZDJPY": "NZDJPY=X",     # second high-carry cross
    "MXNJPY": "MXNJPY=X",     # highest-carry of the majors-adjacent crosses
    "EURJPY": "EURJPY=X",
    "DXY": "DX-Y.NYB",        # broad dollar
    # Equities
    "SPX": "^GSPC",
    "NDX": "^NDX",
    # Volatility
    "VIX": "^VIX",
    "VIX3M": "^VIX3M",        # 3-month VIX — used for term structure
    "MOVE": "^MOVE",          # Treasury vol. Often unavailable; we fall back
                              # to a realised-vol proxy computed from DGS10.
    # Commodities
    "WTI": "CL=F",
    "GOLD": "GC=F",
    "COPPER": "HG=F",
    # Credit proxies (used if the FRED OAS series is unavailable)
    "HYG": "HYG",             # high-yield corporate bond ETF
    "LQD": "LQD",             # investment-grade corporate bond ETF
    "TLT": "TLT",             # long Treasuries
    # US yields from Yahoo — fallback only; FRED is the primary source
    "US10Y_YF": "^TNX",
    "US30Y_YF": "^TYX",
    "US05Y_YF": "^FVX",
}

# --- FRED series (via pandas-datareader) -----------------------------------
# FRED is the primary source for yields and credit spreads: cleaner, official,
# and free. Daily series lag by roughly one business day.
FRED_SERIES: dict[str, str] = {
    "US2Y": "DGS2",             # 2-Year Treasury constant maturity (daily, %)
    "US10Y": "DGS10",           # 10-Year Treasury (daily, %)
    "US30Y": "DGS30",           # 30-Year Treasury (daily, %)
    "CURVE_10_2": "T10Y2Y",     # 10y minus 2y spread (daily, %)
    "FED_FUNDS": "DFF",         # Effective Fed Funds Rate (daily, %)
    "HY_OAS": "BAMLH0A0HYM2",   # ICE BofA US High Yield Option-Adjusted Spread
    "IG_OAS": "BAMLC0A0CM",     # ICE BofA US Corporate (IG) OAS
    "VIX_FRED": "VIXCLS",       # VIX from FRED — backup for Yahoo
    "WTI_FRED": "DCOILWTICO",   # WTI from FRED — backup for Yahoo
    # Japan. FRED carries these MONTHLY only, so they lag by up to ~6 weeks.
    # They are used to SEED the sidebar inputs with something real rather than
    # a stale hardcoded guess; override them in the sidebar for daily use.
    "JP10Y_MONTHLY": "IRLTLT01JPM156N",     # long-term (10y) government bond
    "JP_OVERNIGHT": "IRSTCI01JPM156N",      # call money — proxy for BOJ policy
    "JP3M_MONTHLY": "IR3TIB01JPM156N",      # 3-month interbank — short-end anchor
}

# How far back to pull history. 3 years gives enough data for percentile-based
# signals (MOVE proxy, oil vol) to be meaningful without slowing the app down.
HISTORY_YEARS: int = 3

# Cache lifetime in seconds. Market data refreshes every 30 min by default;
# the "Refresh data" button clears the cache immediately regardless.
CACHE_TTL_SECONDS: int = 1800


# ---------------------------------------------------------------------------
# 2. MANUAL INPUTS
#    Things that have no reliable free daily feed. All are overridable live
#    from the sidebar — these are just the starting defaults.
# ---------------------------------------------------------------------------

# Japanese government bond yields, in percent.
#
# WHY MANUAL: there is no free, reliable, DAILY JGB feed anywhere.
#
# You should rarely need to touch these numbers. On startup the sidebar seeds
# itself from FRED's monthly Japanese series (see FRED_SERIES above) and tells
# you the source and date of each seed. These constants are only the
# last-resort fallback for when FRED is unreachable — which is why they are
# deliberately conservative rather than precise.
#
# The one worth typing by hand is the 2-year: it is what actually prices the
# carry trade, and FRED has no 2-year Japanese series, so it gets seeded from
# the 3-month interbank rate instead (an anchor, not the real thing).
MANUAL_JP_YIELDS: dict[str, float] = {
    "JP2Y": 1.20,   # fallback only — seeded from FRED 3-month interbank
    "JP10Y": 2.50,  # fallback only — seeded from FRED monthly 10-year
}

# Policy rates, in percent. Both are seeded from FRED at runtime:
# Fed funds from DFF (daily), BOJ from the call money rate (monthly).
# These constants are the fallback if FRED is unreachable.
MANUAL_POLICY_RATES: dict[str, float] = {
    "FED_FUNDS": 3.60,
    "BOJ_RATE": 0.85,
}

# When the fallback constants above were last reviewed. The UI shows the
# live FRED seed date instead whenever a seed is available, so a stale
# constant cannot quietly become the displayed number.
MANUAL_INPUTS_AS_OF: str = "2026-08-02"

# S&P 500 market cap ≈ index level × divisor. The divisor drifts slowly with
# share issuance/buybacks and index changes; it sits in the mid-8-billions.
# Used only for the "margin debt as % of market cap" approximation.
# To refresh: divide the published S&P 500 total market cap by the index level.
SP500_DIVISOR_BN: float = 8.40  # $bn of market cap per index point


# ---------------------------------------------------------------------------
# 3. CENTRAL BANK CALENDAR
#    APPROXIMATE — verify against federalreserve.gov and boj.or.jp.
#    Dates are the final (decision) day of each meeting, ISO format.
# ---------------------------------------------------------------------------
FOMC_MEETINGS: list[str] = [
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
    "2027-01-27", "2027-03-17",
]

BOJ_MEETINGS: list[str] = [
    "2026-01-23", "2026-03-19", "2026-05-01", "2026-06-16",
    "2026-07-31", "2026-09-18", "2026-10-30", "2026-12-18",
    "2027-01-22", "2027-03-18",
]

# Other recurring events worth a countdown. Add your own freely.
OTHER_EVENTS: list[tuple[str, str]] = [
    ("2026-08-21", "Jackson Hole symposium (approx.)"),
    ("2026-09-30", "US fiscal year end"),
]


# ---------------------------------------------------------------------------
# 4. RISK SCORING
# ---------------------------------------------------------------------------

# --- Component weights -----------------------------------------------------
# These are relative, not required to sum to 100 (they get normalised), but
# keeping them at 100 makes them easy to reason about as percentages.
# Any component with no data is dropped and the rest are re-weighted.
WEIGHTS: dict[str, float] = {
    "carry_fx": 20.0,      # yen strength + high-beta cross drawdown
    "rate_diff": 10.0,     # US-Japan 2y differential compression
    "rate_vol": 10.0,      # MOVE index / Treasury realised vol
    "curve": 5.0,          # 10y-2y slope behaviour
    "equity_vol": 15.0,    # VIX level + term structure
    "credit": 15.0,        # high-yield spreads
    "leverage": 15.0,      # FINRA margin debt
    "commodity": 10.0,     # oil shock and oil volatility
}

# --- Thresholds ------------------------------------------------------------
# For every signal: (CALM_AT, STRESS_AT).
#   score 0.0 at CALM_AT, 1.0 at STRESS_AT, linear in between, clipped.
#   If STRESS_AT < CALM_AT the signal is "lower is worse".
# Tune these to make the dashboard more or less sensitive.
THRESHOLDS: dict[str, tuple[float, float]] = {
    # --- Carry / FX ---
    # USDJPY 1-month % change. Yen strengthening (negative) is the stress case.
    # -2% starts to matter, -7% is a genuine unwind.
    "usdjpy_1m_pct": (-2.0, -7.0),
    # USDJPY 1-week % change — the fast-unwind tell.
    "usdjpy_1w_pct": (-1.0, -4.0),
    # Drawdown of the high-beta carry cross (AUDJPY) from its 60-day high, %.
    "carry_cross_drawdown_pct": (-2.0, -8.0),

    # --- Rate differentials ---
    # 3-month change in the US-Japan 2y differential, in percentage points.
    # Compression removes the reason to hold the carry trade.
    "diff_2y_change_3m": (-0.15, -0.75),
    # Absolute level of the US-Japan 2y differential, percentage points.
    # A WIDE differential is not itself stress — it is the fuel. It only
    # scores when combined with yen strength (see ESCALATIONS).
    "diff_2y_level": (1.0, 4.0),

    # --- Rate volatility ---
    # Percentile (0-100) of the MOVE index (or its proxy) over trailing 3y.
    "rate_vol_pctile": (60.0, 92.0),

    # --- Curve ---
    # 3-month change in the 10y-2y slope, percentage points. Rapid
    # bull-steepening out of inversion has historically preceded recessions.
    "curve_steepening_3m": (0.25, 1.00),

    # --- Equity volatility ---
    "vix_level": (15.0, 32.0),
    # VIX / VIX3M. Above 1.0 = backwardation = acute stress.
    "vix_term_structure": (0.92, 1.05),

    # --- Credit ---
    # High-yield OAS level, in percentage points.
    "hy_oas_level": (3.0, 6.0),
    # 1-month change in HY OAS, percentage points — widening is the signal.
    "hy_oas_change_1m": (0.10, 0.90),
    # Fallback when FRED OAS is unavailable: HYG/LQD ratio drawdown from its
    # 6-month high, %.
    "hyg_lqd_drawdown_pct": (-1.0, -5.0),

    # --- Leverage ---
    # FINRA margin debt year-over-year % change. Rapid expansion is the
    # warning; contraction from a peak means the unwind has already begun.
    "margin_debt_yoy": (10.0, 30.0),
    # How close margin debt is to its all-time high, % (100 = at the record).
    "margin_debt_vs_peak": (90.0, 100.0),

    # --- Commodities ---
    # Absolute 1-month % move in WTI — a shock in EITHER direction is a
    # macro signal (supply shock up, demand collapse down).
    "oil_abs_move_1m": (8.0, 25.0),
    # Percentile (0-100) of WTI 20-day realised volatility over trailing 3y.
    "oil_vol_pctile": (60.0, 90.0),
}

# --- Within-component signal weights ---------------------------------------
# Several components blend more than one signal. These control the blend.
# Each inner dict is normalised, so only the ratios matter.
SUB_WEIGHTS: dict[str, dict[str, float]] = {
    "carry_fx": {
        "usdjpy_1m_pct": 0.35,          # the trend
        "usdjpy_1w_pct": 0.40,          # the acceleration — weighted highest
        "carry_cross_drawdown_pct": 0.25,
    },
    "rate_diff": {
        "diff_2y_change_3m": 0.70,      # compression is the actionable signal
        "diff_2y_level": 0.30,          # level alone is fuel, not fire
    },
    "equity_vol": {
        "vix_level": 0.60,
        "vix_term_structure": 0.40,
    },
    "credit": {
        "hy_oas_change_1m": 0.60,       # rate of change beats level
        "hy_oas_level": 0.40,
    },
    "leverage": {
        "margin_debt_yoy": 0.55,
        "margin_debt_vs_peak": 0.45,
    },
    "commodity": {
        "oil_abs_move_1m": 0.60,
        "oil_vol_pctile": 0.40,
    },
}

# --- Regime bands ----------------------------------------------------------
# Composite score 0-100 maps to a regime label.
REGIME_BANDS: dict[str, float] = {
    "elevated_above": 34.0,   # >= this is Elevated
    "high_above": 62.0,       # >= this is High
}

# --- Escalation rules ------------------------------------------------------
# Pattern-based overrides. Each rule can floor the composite score at a
# minimum value, so a dangerous *combination* cannot be averaged away.
# Evaluated in scoring.py; keyed by rule id -> (floor_score, description).
ESCALATIONS: dict[str, tuple[float, str]] = {
    "carry_unwind": (
        70.0,
        "Yen strengthening fast (USDJPY down >2% in a week) while the US-Japan "
        "2y differential is still wide (>2.0pp). This is the signature of a "
        "forced carry-trade unwind rather than an orderly rate-driven move.",
    ),
    "vol_backwardation": (
        66.0,
        "VIX term structure in backwardation (VIX above VIX3M) — the options "
        "market is pricing near-term stress above longer-term stress.",
    ),
    "credit_crack": (
        66.0,
        "High-yield spreads widened more than 100bp in a month — credit is "
        "repricing risk faster than equities.",
    ),
    "leverage_at_peak_and_vol_rising": (
        60.0,
        "Margin debt within 3% of its record high while volatility is already "
        "elevated — maximum leverage meeting rising volatility is the classic "
        "setup for a forced-selling cascade.",
    ),
}

# Escalation rule parameters — separated out so they are as tunable as the
# rest of the thresholds.
ESCALATION_PARAMS: dict[str, float] = {
    "carry_unwind_usdjpy_1w": -2.0,   # USDJPY 1-week % change below this...
    "carry_unwind_min_diff": 2.0,     # ...while 2y differential above this
    "vol_backwardation_ratio": 1.00,  # VIX/VIX3M above this
    "credit_crack_oas_1m": 1.00,      # HY OAS 1-month widening (pp) above this
    "leverage_peak_proximity": 97.0,  # margin debt >= this % of record
    "leverage_vix_trigger": 22.0,     # ...while VIX above this
}


# ---------------------------------------------------------------------------
# 5. COLOUR PALETTE
# ---------------------------------------------------------------------------
# Every colour here is MODE-INVARIANT: the same value is used whether the app
# is rendered light or dark.
#
# WHY, because this is not an obvious choice: Streamlit gives Python no
# reliable way to know which theme the browser actually painted.
# `st.context.theme` reports the *client's* preference, which disagrees with a
# config-pinned theme, and the pinned theme wins on screen — so any palette
# picked in Python can end up inverted (white cards on a black page).
#
# Rather than guess, the design avoids needing to know:
#   * Surfaces and borders are neutral greys at low alpha. Grey at 10% over a
#     dark page reads as a lighter card; over a light page as a darker one.
#     Correct in both, automatically.
#   * Text inherits Streamlit's own colour and uses opacity for hierarchy.
#   * Line and status colours are steps that clear contrast on BOTH surfaces.
#
# The series hues below are validated for colour-vision deficiency as an
# ordered set. Slots 3 and 4 (aqua, yellow) fall below 3:1 on a light
# background, which is why every chart carries a legend and a table view —
# colour is never the only channel. Keep that pairing if you change these.
PALETTE: dict[str, str] = {
    # Categorical series, in fixed assignment order. Never cycle past slot 4:
    # add a fifth series only by folding others into "Other" or faceting.
    "series_1": "#3987e5",   # blue
    "series_2": "#eb6834",   # orange
    "series_3": "#1baf7a",   # aqua
    "series_4": "#eda100",   # yellow

    # Status colours. RESERVED — never reuse one as a series colour, and
    # always pair with a word, never colour alone.
    "good": "#0ca30c",
    "warning": "#fab219",
    "serious": "#ec835a",
    "critical": "#d03b3b",

    # Chrome. Neutral greys at alpha so they work over any background.
    "surface_tint": "rgba(128,128,128,0.10)",   # card fill
    "border": "rgba(128,128,128,0.28)",
    "grid": "rgba(128,128,128,0.22)",           # chart gridlines (hairline)
    "axis": "rgba(128,128,128,0.45)",           # chart axis rules
    "muted": "#8b8b8b",                          # axis ticks and captions
    "track": "rgba(128,128,128,0.18)",          # score-bar track
}

# Maps a risk level to a status colour key and its display label.
# The label is what makes the colour redundant rather than load-bearing.
LEVEL_STYLE: dict[str, tuple[str, str]] = {
    "low": ("good", "Low"),
    "elevated": ("warning", "Elevated"),
    "high": ("critical", "High"),
    "na": ("muted", "No data"),
}
