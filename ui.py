"""
ui.py — Presentation layer: styling, metric cards, sparklines and charts.
=========================================================================

Two conventions are enforced here and worth knowing if you edit this file:

  * COLOUR NEVER CARRIES MEANING ALONE. Every risk flag pairs its colour with
    a word ("Low" / "Elevated" / "High") and a shape, so the dashboard still
    works for colour-vision-deficient readers and in greyscale.

  * NO DUAL-AXIS CHARTS. Plotting two different scales on one plot invents a
    correlation from the arbitrary alignment of the axes — which is exactly
    the mistake you must not make when eyeballing USDJPY against a yield
    differential. Instead, `carry_panel_chart` stacks two plots on a shared
    time axis (true co-movement, honest scales), and `indexed_chart` offers a
    single-axis overlay with both series indexed to 100.
"""

from __future__ import annotations

import datetime as dt
from typing import Optional, Sequence

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import config


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
# There is deliberately no theme detection here. See the long comment on
# config.PALETTE: Streamlit cannot tell Python which theme was actually
# painted, so the palette is built to be correct in both.

def palette() -> dict[str, str]:
    return config.PALETTE


def level_color(level: str) -> str:
    role, _ = config.LEVEL_STYLE.get(level, ("muted", "No data"))
    return config.PALETTE.get(role, config.PALETTE["muted"])


def level_label(level: str) -> str:
    return config.LEVEL_STYLE.get(level, ("muted", "No data"))[1]


# ---------------------------------------------------------------------------
# Global CSS
# ---------------------------------------------------------------------------

def inject_css() -> None:
    """
    Injected once per run. Handles the card system and — importantly for a
    dashboard checked on a phone — forces Streamlit's horizontal column blocks
    to stack vertically below 640px instead of squeezing into unreadable slivers.

    Note how little colour is hardcoded: cards inherit Streamlit's text colour
    and sit on a translucent grey tint, so they render correctly in light and
    dark without the app ever knowing which one is active.
    """
    pal = palette()
    st.markdown(
        f"""
<style>
:root {{
  --surface: {pal['surface_tint']};
  --border: {pal['border']};
  --track: {pal['track']};
  --good: {pal['good']};
  --warning: {pal['warning']};
  --critical: {pal['critical']};
}}

/* Tighter top padding so the regime banner is visible without scrolling. */
.block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1400px; }}

/* ---------- Metric card ---------- */
.rk-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px 14px;
  margin-bottom: 10px;
  min-height: 104px;
  display: flex; flex-direction: column; justify-content: space-between;
}}
.rk-card-head {{ display: flex; align-items: center; gap: 6px; margin-bottom: 2px; }}
/* Hierarchy comes from opacity on the INHERITED text colour, so it reads
   correctly whether that colour is near-black or near-white. */
.rk-label {{
  font-size: 0.72rem; letter-spacing: 0.04em; text-transform: uppercase;
  font-weight: 600; line-height: 1.25; opacity: 0.62;
}}
.rk-value {{
  font-size: 1.55rem; font-weight: 650; color: inherit;
  line-height: 1.15; margin: 2px 0 4px 0;
}}
.rk-sub {{ font-size: 0.72rem; opacity: 0.6; line-height: 1.35; }}
.rk-deltas {{ display: flex; flex-wrap: wrap; gap: 5px; margin-top: 2px; }}
.rk-delta {{
  font-size: 0.7rem; font-weight: 600; padding: 1px 6px; border-radius: 5px;
  background: rgba(128,128,128,0.16); font-variant-numeric: tabular-nums;
  white-space: nowrap; opacity: 0.85;
}}
.rk-delta.up {{ color: {pal['good']}; opacity: 1; }}
.rk-delta.down {{ color: {pal['critical']}; opacity: 1; }}
.rk-spark {{ margin-top: 6px; height: 28px; }}

/* ---------- Chart title (rendered above the figure, not inside it) ---------- */
.rk-chart-title {{
  font-size: 0.82rem; font-weight: 600; opacity: 0.72;
  margin: 10px 0 -4px 2px; line-height: 1.3;
}}

/* ---------- Status chip: colour + word + dot, never colour alone ---------- */
.rk-chip {{
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 0.68rem; font-weight: 700; letter-spacing: 0.03em;
  padding: 2px 8px; border-radius: 999px; text-transform: uppercase;
  border: 1px solid currentColor; white-space: nowrap;
}}
.rk-dot {{ width: 7px; height: 7px; border-radius: 50%; background: currentColor; }}

/* ---------- Regime banner ---------- */
.rk-banner {{
  border: 1px solid var(--border); border-left-width: 6px;
  border-radius: 12px; padding: 18px 22px; margin-bottom: 14px;
  background: var(--surface);
}}
.rk-banner-label {{
  font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.08em;
  font-weight: 700; opacity: 0.62;
}}
.rk-banner-value {{ font-size: 2.6rem; font-weight: 700; line-height: 1.1; margin: 2px 0; }}
.rk-banner-score {{ font-size: 0.95rem; font-weight: 600; opacity: 0.8; }}

/* ---------- Component score bar ---------- */
.rk-bar-row {{ display: flex; align-items: center; gap: 10px; margin: 7px 0; }}
.rk-bar-name {{ flex: 0 0 190px; font-size: 0.8rem; opacity: 0.8; }}
.rk-bar-track {{
  flex: 1 1 auto; height: 9px; border-radius: 5px;
  background: var(--track); overflow: hidden; min-width: 60px;
}}
.rk-bar-fill {{ height: 100%; border-radius: 5px; }}
.rk-bar-val {{
  flex: 0 0 78px; text-align: right; font-size: 0.76rem;
  font-variant-numeric: tabular-nums; opacity: 0.75;
}}

/* ---------- Alert box ---------- */
.rk-alert {{
  border-radius: 9px; padding: 11px 14px; margin: 7px 0;
  border: 1px solid currentColor; font-size: 0.85rem; line-height: 1.5;
}}
.rk-alert strong {{ letter-spacing: 0.02em; }}

/* ---------- MOBILE: stack columns instead of squeezing them ---------- */
@media (max-width: 640px) {{
  [data-testid="stHorizontalBlock"] {{ flex-direction: column !important; gap: 0 !important; }}
  [data-testid="stColumn"] {{
    width: 100% !important; flex: 1 1 100% !important; min-width: 100% !important;
  }}
  .block-container {{ padding-left: 0.7rem; padding-right: 0.7rem; padding-top: 1.4rem; }}
  .rk-value {{ font-size: 1.35rem; }}
  .rk-banner-value {{ font-size: 2.05rem; }}
  .rk-bar-name {{ flex: 0 0 120px; font-size: 0.74rem; }}
  .rk-card {{ min-height: 0; }}
  /* Let the tab strip scroll horizontally rather than wrap into a wall. */
  [data-baseweb="tab-list"] {{ overflow-x: auto !important; flex-wrap: nowrap !important; }}
}}
</style>
""",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Small primitives
# ---------------------------------------------------------------------------

def _clean(html: str) -> str:
    """Collapse a multi-line HTML literal so Streamlit doesn't see a code block."""
    return "".join(line.strip() for line in html.strip().splitlines())


def fmt(value: Optional[float], decimals: int = 2, suffix: str = "",
        prefix: str = "", signed: bool = False, thousands: bool = False) -> str:
    """Format a number for display, or return an em dash if it is missing."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    spec = f",.{decimals}f" if thousands else f".{decimals}f"
    if signed:
        spec = "+" + spec
    return f"{prefix}{value:{spec}}{suffix}"


def chip(level: str, text: Optional[str] = None) -> str:
    """Status chip HTML: coloured dot + word. Never colour alone."""
    color = level_color(level)
    label = text or level_label(level)
    return _clean(f"""
        <span class="rk-chip" style="color:{color}">
          <span class="rk-dot"></span>{label}
        </span>
    """)


def sparkline_svg(series: Optional[pd.Series], color: str,
                  days: int = 90, width: int = 150, height: int = 28) -> str:
    """
    Inline SVG sparkline. Deliberately not a Plotly figure: a dashboard with
    twenty small charts loads noticeably faster on a phone with plain SVG,
    and a sparkline has no axes or tooltips to lose.
    """
    if series is None or len(series.dropna()) < 3:
        return ""
    s = series.dropna()
    cutoff = s.index[-1] - pd.Timedelta(days=days)
    s = s.loc[cutoff:]
    if len(s) < 3:
        return ""

    lo, hi = float(s.min()), float(s.max())
    span = hi - lo
    pad = 3
    usable_h = height - 2 * pad

    if span == 0:                                    # flat line
        points = [(i / (len(s) - 1) * width, height / 2) for i in range(len(s))]
    else:
        points = [
            (i / (len(s) - 1) * width,
             pad + (1 - (float(v) - lo) / span) * usable_h)
            for i, v in enumerate(s.values)
        ]

    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    end_x, end_y = points[-1]
    return _clean(f"""
        <svg class="rk-spark" viewBox="0 0 {width} {height}" width="100%"
             height="{height}" preserveAspectRatio="none" aria-hidden="true">
          <polyline points="{path}" fill="none" stroke="{color}"
                    stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>
          <circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="2.4" fill="{color}"/>
        </svg>
    """)


def _delta_chip(label: str, value: Optional[float], good_direction: Optional[str],
                decimals: int = 2, suffix: str = "%") -> str:
    """
    One delta pill. `good_direction` is 'up', 'down' or None:
      'up'   -> a rise is coloured as good
      'down' -> a fall is coloured as good
      None   -> neutral, no colour judgement (e.g. gold, copper)

    The sign is always printed, so the colour is reinforcement rather than the
    only way to read the direction.
    """
    if value is None:
        return f'<span class="rk-delta">{label} —</span>'

    cls = "rk-delta"
    if good_direction == "up":
        cls += " up" if value >= 0 else " down"
    elif good_direction == "down":
        cls += " up" if value <= 0 else " down"

    return f'<span class="{cls}">{label} {value:+.{decimals}f}{suffix}</span>'


def metric_card(
    label: str,
    value: str,
    deltas: Sequence[tuple[str, Optional[float]]] = (),
    good_direction: Optional[str] = None,
    level: Optional[str] = None,
    sub: str = "",
    series: Optional[pd.Series] = None,
    spark_days: int = 90,
    delta_decimals: int = 2,
    delta_suffix: str = "%",
    level_text: Optional[str] = None,
) -> None:
    """
    Render one metric card. The workhorse of the whole dashboard.

    `level_text` overrides the chip's wording without changing its colour —
    used where "No data" would be misleading, e.g. a margin-debt card that has
    a value but is excluded from the score because the value is a placeholder.
    """
    pal = palette()
    spark_color = level_color(level) if level and level != "na" else pal["series_1"]

    chip_html = (f'<div style="margin-left:auto">{chip(level, level_text)}</div>'
                 if level else "")
    delta_html = "".join(
        _delta_chip(name, val, good_direction, delta_decimals, delta_suffix)
        for name, val in deltas
    )
    sub_html = f'<div class="rk-sub">{sub}</div>' if sub else ""
    spark_html = sparkline_svg(series, spark_color, days=spark_days) if series is not None else ""

    st.markdown(_clean(f"""
        <div class="rk-card">
          <div>
            <div class="rk-card-head">
              <span class="rk-label">{label}</span>{chip_html}
            </div>
            <div class="rk-value">{value}</div>
            <div class="rk-deltas">{delta_html}</div>
            {sub_html}
          </div>
          {spark_html}
        </div>
    """), unsafe_allow_html=True)


def alert(level: str, title: str, body: str) -> None:
    """A coloured callout that always states its severity in words."""
    color = level_color(level)
    st.markdown(_clean(f"""
        <div class="rk-alert" style="color:{color}">
          <strong>{level_label(level).upper()} · {title}</strong><br>
          <span style="opacity:0.82">{body}</span>
        </div>
    """), unsafe_allow_html=True)


def regime_banner(regime: str, composite: float, coverage: float) -> None:
    """The hero. One number, one word, colour-coded, readable at arm's length."""
    color = level_color(regime)
    label = level_label(regime)
    st.markdown(_clean(f"""
        <div class="rk-banner" style="border-left-color:{color}">
          <div class="rk-banner-label">Overall systematic risk</div>
          <div class="rk-banner-value" style="color:{color}">{label}</div>
          <div class="rk-banner-score">
            Composite score <strong>{composite:.0f}</strong> / 100
            &nbsp;·&nbsp; <span style="opacity:0.62">
            data coverage {coverage:.0f}% of model weight</span>
          </div>
        </div>
    """), unsafe_allow_html=True)


def component_bars(components) -> None:
    """Horizontal bars showing each component's stress score. Sorted worst-first."""
    pal = palette()
    ordered = sorted(
        components,
        key=lambda c: (c.score is None, -(c.score or 0)),
    )
    rows = []
    for c in ordered:
        if c.score is None:
            rows.append(_clean(f"""
                <div class="rk-bar-row">
                  <div class="rk-bar-name">{c.label}</div>
                  <div class="rk-bar-track"></div>
                  <div class="rk-bar-val" style="color:{pal['muted']}">no data</div>
                </div>
            """))
            continue
        color = level_color(c.level)
        pct = c.score * 100
        rows.append(_clean(f"""
            <div class="rk-bar-row">
              <div class="rk-bar-name">{c.label}</div>
              <div class="rk-bar-track">
                <div class="rk-bar-fill" style="width:{pct:.0f}%;background:{color}"></div>
              </div>
              <div class="rk-bar-val">{pct:.0f} · w{c.weight:.0f}</div>
            </div>
        """))
    st.markdown("".join(rows), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def _chart_title(title: str) -> None:
    """
    Chart titles are rendered as HTML ABOVE the figure, never inside it.

    Two reasons: a Plotly title and a top-anchored horizontal legend occupy the
    same strip and collide (the legend wins, the title is unreadable); and a
    title in page typography matches every other heading on the dashboard
    instead of being a slightly-different font rendered into the plot canvas.
    """
    if title:
        st.markdown(f'<div class="rk-chart-title">{title}</div>',
                    unsafe_allow_html=True)


def _base_layout(fig: go.Figure, height: int,
                 top_margin: Optional[int] = None) -> go.Figure:
    """Shared Plotly styling: recessive chrome, hairline grid, no clutter."""
    pal = palette()

    # Note there is no `title` here by design — see _chart_title above. Passing
    # `title=None` would be worse than omitting it: Plotly.js renders a null
    # title as the literal string "undefined".
    layout = dict(
        height=height,
        margin=dict(l=8, r=8, t=top_margin if top_margin is not None else 26, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, -apple-system, 'Segoe UI', sans-serif",
                  size=11, color=pal["muted"]),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left",
                    x=0, bgcolor="rgba(0,0,0,0)"),
        dragmode=False,          # touch drags should scroll the page, not pan
    )
    fig.update_layout(**layout)
    fig.update_xaxes(showgrid=False, showline=True, linecolor=pal["axis"],
                     linewidth=1, ticks="outside", tickcolor=pal["axis"],
                     tickfont=dict(size=10, color=pal["muted"]))
    fig.update_yaxes(showgrid=True, gridcolor=pal["grid"], gridwidth=1,
                     zeroline=False, showline=False,
                     tickfont=dict(size=10, color=pal["muted"]))
    return fig


def _plot(fig: go.Figure) -> None:
    """Render with touch-friendly config."""
    st.plotly_chart(
        fig,
        width="stretch",
        config={"displayModeBar": False, "scrollZoom": False,
                "staticPlot": False, "responsive": True},
    )


def line_chart(series_map: dict[str, pd.Series], title: str = "",
               height: int = 260, days: int = 365,
               hline: Optional[float] = None, hline_label: str = "",
               unit: str = "") -> None:
    """
    Single-axis line chart. Series sharing an axis must share units — if they
    do not, use `carry_panel_chart` or `indexed_chart` instead.
    """
    pal = palette()
    colors = [pal["series_1"], pal["series_2"], pal["series_3"], pal["series_4"]]
    fig = go.Figure()

    plotted = 0
    for i, (name, s) in enumerate(series_map.items()):
        if s is None or s.dropna().empty:
            continue
        s = s.dropna()
        s = s.loc[s.index[-1] - pd.Timedelta(days=days):]
        if s.empty:
            continue
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values, name=name, mode="lines",
            line=dict(color=colors[i % len(colors)], width=2),
            hovertemplate=f"<b>{name}</b>: %{{y:,.2f}}{unit}<extra></extra>",
        ))
        plotted += 1

    if plotted == 0:
        st.caption("No data available for this chart.")
        return

    if hline is not None:
        fig.add_hline(y=hline, line_width=1, line_color=pal["axis"],
                      annotation_text=hline_label,
                      annotation_font=dict(size=10, color=pal["muted"]),
                      annotation_position="top left")

    # A single series needs no legend box — the title names it.
    fig.update_layout(showlegend=plotted > 1)
    _chart_title(title)
    _plot(_base_layout(fig, height))


def carry_panel_chart(usdjpy: Optional[pd.Series],
                      diff_2y: Optional[pd.Series],
                      diff_10y: Optional[pd.Series],
                      days: int = 365, height: int = 420) -> None:
    """
    USDJPY over the yield differentials, as two stacked panels sharing one
    time axis.

    This is deliberately NOT a dual-axis chart. With two y-scales, the visual
    "correlation" between the lines is an artefact of how the scales happen to
    be aligned — and this specific comparison (does the yen move with, or
    against, the rate differential?) is exactly the judgement you do not want
    an arbitrary axis alignment to make for you. Stacked panels show real
    co-movement and real divergence, with each series on its own honest scale.
    """
    pal = palette()
    if usdjpy is None and diff_2y is None and diff_10y is None:
        st.caption("No data available for this chart.")
        return

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.09,
        row_heights=[0.5, 0.5],
        subplot_titles=("USDJPY (higher = weaker yen)",
                        "US minus Japan yield differential (pp)"),
    )

    if usdjpy is not None and not usdjpy.dropna().empty:
        s = usdjpy.dropna()
        s = s.loc[s.index[-1] - pd.Timedelta(days=days):]
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values, name="USDJPY", mode="lines",
            line=dict(color=pal["series_1"], width=2),
            hovertemplate="<b>USDJPY</b>: %{y:,.2f}<extra></extra>",
        ), row=1, col=1)

    for s, name, color in (
        (diff_2y, "2-year differential", pal["series_2"]),
        (diff_10y, "10-year differential", pal["series_3"]),
    ):
        if s is None or s.dropna().empty:
            continue
        s = s.dropna()
        s = s.loc[s.index[-1] - pd.Timedelta(days=days):]
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values, name=name, mode="lines",
            line=dict(color=color, width=2),
            hovertemplate=f"<b>{name}</b>: %{{y:,.2f}}pp<extra></extra>",
        ), row=2, col=1)

    # Left-align the subplot titles to match every other chart heading.
    for ann in fig.layout.annotations:
        ann.font.size = 11
        ann.font.color = pal["muted"]
        ann.x = 0
        ann.xanchor = "left"

    # Extra top margin: the subplot titles live above the first plot and get
    # clipped at the default spacing.
    fig = _base_layout(fig, height, top_margin=30)
    fig.update_layout(legend=dict(orientation="h", y=-0.09, yanchor="top", x=0))
    _plot(fig)


def indexed_chart(series_map: dict[str, pd.Series], title: str = "",
                  days: int = 365, height: int = 300) -> None:
    """
    Overlay several series on ONE axis by indexing each to 100 at the start of
    the window. The honest way to compare differently-scaled series on a
    single plot: relative moves are directly comparable, and no arbitrary
    axis alignment can fake a correlation.
    """
    pal = palette()
    colors = [pal["series_1"], pal["series_2"], pal["series_3"], pal["series_4"]]
    fig = go.Figure()

    plotted = 0
    for i, (name, s) in enumerate(series_map.items()):
        if s is None or s.dropna().empty:
            continue
        s = s.dropna()
        s = s.loc[s.index[-1] - pd.Timedelta(days=days):]
        if s.empty or float(s.iloc[0]) == 0:
            continue
        indexed = s / float(s.iloc[0]) * 100.0
        fig.add_trace(go.Scatter(
            x=indexed.index, y=indexed.values, name=name, mode="lines",
            line=dict(color=colors[i % len(colors)], width=2),
            hovertemplate=f"<b>{name}</b>: %{{y:,.1f}}<extra></extra>",
        ))
        plotted += 1

    if plotted == 0:
        st.caption("No data available for this chart.")
        return

    fig.add_hline(y=100, line_width=1, line_color=pal["axis"])
    fig.update_layout(showlegend=plotted > 1)
    _chart_title(title or "Indexed to 100 at window start")
    _plot(_base_layout(fig, height))


def bar_chart(series: Optional[pd.Series], title: str = "", height: int = 280,
              unit: str = "", highlight_last: bool = True) -> None:
    """Bar chart for the monthly margin debt series."""
    pal = palette()
    if series is None or series.dropna().empty:
        st.caption("No data available for this chart.")
        return
    s = series.dropna()

    # One series, one colour — with the latest bar emphasised rather than
    # given a second meaning.
    colors = [pal["series_1"]] * len(s)
    if highlight_last:
        colors[-1] = pal["series_2"]

    fig = go.Figure(go.Bar(
        x=s.index, y=s.values, marker_color=colors,
        marker_line_width=0,
        hovertemplate=f"%{{x|%b %Y}}: %{{y:,.0f}}{unit}<extra></extra>",
    ))
    fig.update_layout(showlegend=False, bargap=0.25)
    _chart_title(title)
    _plot(_base_layout(fig, height))


def table_view(df: pd.DataFrame, caption: str = "") -> None:
    """
    The table twin every chart should have. Tooltips enhance; they never gate
    access to a value.
    """
    if df is None or df.empty:
        st.caption("No data.")
        return
    st.dataframe(df, width="stretch", hide_index=True)
    if caption:
        st.caption(caption)


# ---------------------------------------------------------------------------
# Calendar helper
# ---------------------------------------------------------------------------

def next_events(dates: Sequence[str], label: str, count: int = 3
                ) -> list[tuple[dt.date, int, str]]:
    """Upcoming (date, days_away, label) tuples from a hardcoded date list."""
    today = dt.date.today()
    out = []
    for d in dates:
        try:
            parsed = dt.date.fromisoformat(d)
        except ValueError:
            continue
        if parsed >= today:
            out.append((parsed, (parsed - today).days, label))
    return sorted(out)[:count]
