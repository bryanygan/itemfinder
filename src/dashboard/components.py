"""Reusable UI components for the ZR ItemFinder dashboard."""

import plotly.graph_objects as go
from dash import dash_table, html

# ── Color palette matching CSS variables ──
C_BLUE = "#3b82f6"
C_GREEN = "#22c55e"
C_RED = "#ef4444"
C_AMBER = "#f59e0b"
C_PURPLE = "#8b5cf6"
C_CYAN = "#06b6d4"

CHART_THEME = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, system-ui, sans-serif", color="#9aa0b2", size=12),
    margin=dict(t=10, b=40, l=50, r=20),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
    xaxis=dict(gridcolor="#2d3044", zerolinecolor="#2d3044"),
    yaxis=dict(gridcolor="#2d3044", zerolinecolor="#2d3044"),
)


def style_fig(fig):
    """Apply consistent dark theme to any Plotly figure."""
    return fig.update_layout(**CHART_THEME)


def empty_fig():
    """Return a themed empty figure for missing-data scenarios."""
    return style_fig(go.Figure())


def explainer(content, color=""):
    """Info box explaining a metric in plain English.

    color: 'green', 'red', 'amber', 'purple', or '' (default blue).
    content: a string or a list of Dash children (html.Strong, html.Br, etc.)
    """
    cls = f"explainer {color}" if color else "explainer"
    children = content if not isinstance(content, str) else [html.Span(content)]
    return html.Div(children, className=cls)


def action_box(title, items):
    """Action callout with a title and bullet-point list."""
    return html.Div([
        html.Div(title, className="action-title"),
        html.Ul([html.Li(i) for i in items]),
    ], className="action-box")


def kpi(value, label, color=C_CYAN):
    """Single KPI card with a large number and label."""
    fmt = f"{value:,}" if isinstance(value, (int, float)) and not isinstance(value, bool) else str(value)
    return html.Div([
        html.Div(fmt, className="kpi-value", style={"color": color}),
        html.Div(label, className="kpi-label"),
    ], className="kpi-card")


def section(title, subtitle=""):
    """Section header with optional subtitle."""
    parts = [html.Div(title, className="section-title")]
    if subtitle:
        parts.append(html.Div(subtitle, className="section-sub"))
    return html.Div(parts)


def chart_card(title, subtitle, chart):
    """Wrap a dcc.Graph in a styled card with title."""
    children = [html.H3(title)]
    if subtitle:
        children.append(html.Div(subtitle, className="chart-sub"))
    children.append(chart)
    return html.Div(children, className="chart-card")


def make_table(df, col_map=None, page_size=12):
    """Styled DataTable with optional column renaming.

    col_map: dict of {df_column: 'Display Name'} — only listed columns shown.
    If None, shows all columns with auto-prettified names.
    """
    if df is None or df.empty:
        return html.P("No data available.", style={"color": "#6b7280", "padding": "12px"})
    if col_map:
        show = [c for c in col_map if c in df.columns]
        cols = [{"name": col_map[c], "id": c} for c in show]
        data = df[show].to_dict("records")
    else:
        cols = [{"name": c.replace("_", " ").title(), "id": c} for c in df.columns]
        data = df.to_dict("records")
    return dash_table.DataTable(
        data=data, columns=cols, page_size=page_size,
        sort_action="native", filter_action="native",
        style_table={"overflowX": "auto"},
    )
