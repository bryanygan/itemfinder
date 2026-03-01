"""Interactive Plotly Dash dashboard.

Usage: python -m src.dashboard.app
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, Input, Output, callback, dash_table, dcc, html

try:
    import dash_bootstrap_components as dbc
    HAS_DBC = True
except ImportError:
    HAS_DBC = False

from src.analytics.sales_intel import (
    brand_cross_sell,
    buyer_profiles,
    color_demand,
    conversion_tracking,
    inventory_recommendations,
    monthly_seasonality,
    size_demand,
    unmet_demand,
)
from src.analytics.trends import (
    channel_breakdown,
    daily_volume,
    sentiment_over_time,
    top_items_by_intent,
    trending_items,
)
from src.common.db import get_connection, processed_mention_count, raw_message_count
from src.common.log_util import get_logger
from src.process.scoring import compute_brand_scores, compute_item_scores

log = get_logger("dashboard")

TAB_STYLE = {"backgroundColor": "#1e1e22", "color": "#aaa"}
TAB_SELECTED = {"backgroundColor": "#333", "color": "#fff"}

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_data():
    conn = get_connection()
    data = {
        "raw_count": raw_message_count(conn),
        "mention_count": processed_mention_count(conn),
        "item_scores": compute_item_scores(conn),
        "brand_scores": compute_brand_scores(conn),
        "trending": trending_items(conn, 20),
        "channels": channel_breakdown(conn),
        "daily": daily_volume(conn),
        "sentiment": sentiment_over_time(conn),
        "top_requested": top_items_by_intent(conn, "request", 30),
        "top_satisfaction": top_items_by_intent(conn, "satisfaction", 30),
        "top_regret": top_items_by_intent(conn, "regret", 30),
        "top_ownership": top_items_by_intent(conn, "ownership", 30),
        # Sales intel
        "unmet": unmet_demand(conn, 3),
        "profiles": buyer_profiles(conn, 20),
        "cross_sell": brand_cross_sell(conn, 10),
        "sizes": size_demand(conn),
        "colors": color_demand(conn),
        "inv_recs": inventory_recommendations(conn),
        "seasonality": monthly_seasonality(conn),
        "conversions": conversion_tracking(conn),
    }

    rows = conn.execute("""
        SELECT brand, item, variant, intent_type, intent_score, channel,
               DATE(timestamp) as day, author
        FROM processed_mentions
    """).fetchall()
    data["all_mentions"] = pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()

    conn.close()
    return data


DATA = _load_data()

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

external_stylesheets = [dbc.themes.DARKLY] if HAS_DBC else []
app = Dash(__name__, external_stylesheets=external_stylesheets,
           suppress_callback_exceptions=True)
app.title = "Demand Intelligence Dashboard"

# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

def kpi_card(title: str, value, color: str = "#17a2b8"):
    return html.Div([
        html.H6(title, style={"color": "#aaa", "marginBottom": "4px", "fontSize": "0.85rem"}),
        html.H3(f"{value:,}" if isinstance(value, int) else str(value),
                 style={"color": color, "fontWeight": "bold"}),
    ], style={
        "background": "#2a2a2e", "borderRadius": "8px", "padding": "16px",
        "textAlign": "center", "flex": "1", "minWidth": "150px",
    })


def make_table(df: pd.DataFrame, page_size: int = 12):
    if df.empty:
        return html.P("No data available", style={"color": "#888"})
    return dash_table.DataTable(
        data=df.to_dict("records"),
        columns=[{"name": c, "id": c} for c in df.columns],
        page_size=page_size,
        sort_action="native",
        filter_action="native",
        style_table={"overflowX": "auto"},
        style_cell={
            "backgroundColor": "#1e1e22", "color": "#ddd",
            "border": "1px solid #444", "textAlign": "left",
            "padding": "6px 10px", "fontSize": "0.85rem",
        },
        style_header={
            "backgroundColor": "#333", "fontWeight": "bold",
            "border": "1px solid #555",
        },
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#252529"},
        ],
    )

# ---------------------------------------------------------------------------
# DataFrames
# ---------------------------------------------------------------------------

items_df = pd.DataFrame(DATA["item_scores"]) if DATA["item_scores"] else pd.DataFrame()
brands_df = pd.DataFrame(DATA["brand_scores"]) if DATA["brand_scores"] else pd.DataFrame()
channels_df = pd.DataFrame(DATA["channels"]) if DATA["channels"] else pd.DataFrame()
daily_df = pd.DataFrame(DATA["daily"]) if DATA["daily"] else pd.DataFrame()
unmet_df = pd.DataFrame(DATA["unmet"]) if DATA["unmet"] else pd.DataFrame()
sizes_df = pd.DataFrame(DATA["sizes"]) if DATA["sizes"] else pd.DataFrame()
colors_df = pd.DataFrame(DATA["colors"]) if DATA["colors"] else pd.DataFrame()
cross_df = pd.DataFrame(DATA["cross_sell"]) if DATA["cross_sell"] else pd.DataFrame()
profiles_df = pd.DataFrame([
    {k: v for k, v in p.items() if k not in ("top_brands", "top_requests")}
    for p in DATA["profiles"]
]) if DATA["profiles"] else pd.DataFrame()
inv_df = pd.DataFrame(DATA["inv_recs"]) if DATA["inv_recs"] else pd.DataFrame()
season_df = pd.DataFrame(DATA["seasonality"]) if DATA["seasonality"] else pd.DataFrame()
conv_df = pd.DataFrame(DATA["conversions"]) if DATA["conversions"] else pd.DataFrame()

n_brands = len(brands_df) if not brands_df.empty else 0
n_items = len(items_df) if not items_df.empty else 0

# ---------------------------------------------------------------------------
# Tab 1: Overview
# ---------------------------------------------------------------------------

overview_tab = html.Div([
    html.Div([
        kpi_card("Messages Analyzed", DATA["raw_count"], "#17a2b8"),
        kpi_card("Mentions Extracted", DATA["mention_count"], "#28a745"),
        kpi_card("Unique Brands", n_brands, "#ffc107"),
        kpi_card("Item Combinations", n_items, "#dc3545"),
        kpi_card("Channels", len(DATA["channels"]), "#6f42c1"),
    ], style={"display": "flex", "gap": "12px", "flexWrap": "wrap", "marginBottom": "24px"}),

    html.Div([
        html.Div([
            html.H5("Top Brands by Mentions", style={"color": "#ddd"}),
            dcc.Graph(
                figure=px.bar(
                    brands_df.head(15), x="brand", y="mentions",
                    color="trend_score", color_continuous_scale="Viridis",
                    labels={"mentions": "Total Mentions", "trend_score": "Trend Score"},
                ).update_layout(
                    template="plotly_dark", paper_bgcolor="#1e1e22",
                    plot_bgcolor="#1e1e22", margin=dict(t=10),
                ) if not brands_df.empty else go.Figure().update_layout(
                    template="plotly_dark", paper_bgcolor="#1e1e22",
                ),
                config={"displayModeBar": False},
            ),
        ], style={"flex": "1"}),
        html.Div([
            html.H5("Intent Distribution", style={"color": "#ddd"}),
            dcc.Graph(
                figure=px.pie(
                    DATA["all_mentions"].groupby("intent_type").size().reset_index(
                        name="count") if not DATA["all_mentions"].empty else pd.DataFrame(
                        {"intent_type": [], "count": []}),
                    values="count", names="intent_type",
                    color_discrete_sequence=["#17a2b8", "#28a745", "#dc3545", "#ffc107", "#6c757d"],
                ).update_layout(
                    template="plotly_dark", paper_bgcolor="#1e1e22", margin=dict(t=10),
                ),
                config={"displayModeBar": False},
            ),
        ], style={"flex": "1"}),
    ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}),
], style={"padding": "16px"})

# ---------------------------------------------------------------------------
# Tab 2: Top Items (with search)
# ---------------------------------------------------------------------------

top_items_tab = html.Div([
    html.Div([
        html.Label("Search items:", style={"color": "#aaa"}),
        dcc.Input(id="item-search", type="text", placeholder="Search brand or item...",
                  style={"width": "300px", "padding": "6px", "borderRadius": "4px",
                         "border": "1px solid #555", "background": "#2a2a2e", "color": "#ddd"}),
    ], style={"marginBottom": "16px"}),
    html.Div(id="items-table-container"),
], style={"padding": "16px"})


@callback(Output("items-table-container", "children"), Input("item-search", "value"))
def update_items_table(search):
    df = items_df.copy()
    if df.empty:
        return html.P("No data", style={"color": "#888"})
    if search:
        mask = (
            df["brand"].str.contains(search, case=False, na=False)
            | df["item"].str.contains(search, case=False, na=False)
        )
        df = df[mask]
    cols = ["brand", "item", "variant", "total_mentions", "request_count",
            "satisfaction_count", "regret_count", "velocity", "final_score"]
    return make_table(df[cols].head(100))


# ---------------------------------------------------------------------------
# Tab 3: Sales Intel (NEW)
# ---------------------------------------------------------------------------

sales_tab = html.Div([
    # Unmet demand
    html.H5("Unmet Demand -- Items to Stock", style={"color": "#dc3545"}),
    html.P("Items people request but almost nobody owns.", style={"color": "#888", "fontSize": "0.85rem"}),
    make_table(unmet_df[["brand", "item", "requests", "owned", "demand_gap",
                          "unique_requesters"]].head(20)) if not unmet_df.empty else html.P("No data"),

    html.Hr(style={"borderColor": "#444", "margin": "24px 0"}),

    # Inventory recommendations
    html.H5("Inventory Recommendations", style={"color": "#28a745", "marginTop": "8px"}),
    make_table(inv_df[["priority", "brand", "item", "demand_gap",
                        "notes"]].head(15)) if not inv_df.empty else html.P("No data"),

    html.Hr(style={"borderColor": "#444", "margin": "24px 0"}),

    # Size + Color demand side by side
    html.Div([
        html.Div([
            html.H5("Size Demand", style={"color": "#ffc107"}),
            dcc.Graph(
                figure=px.bar(
                    sizes_df.head(12), x="size", y=["requests", "owned"],
                    barmode="group",
                    color_discrete_sequence=["#17a2b8", "#28a745"],
                ).update_layout(
                    template="plotly_dark", paper_bgcolor="#1e1e22",
                    plot_bgcolor="#1e1e22", margin=dict(t=10),
                ) if not sizes_df.empty else go.Figure(),
                config={"displayModeBar": False},
            ),
        ], style={"flex": "1"}),
        html.Div([
            html.H5("Color Demand", style={"color": "#ffc107"}),
            dcc.Graph(
                figure=px.bar(
                    colors_df.head(12), x="color", y=["requests", "owned"],
                    barmode="group",
                    color_discrete_sequence=["#17a2b8", "#28a745"],
                ).update_layout(
                    template="plotly_dark", paper_bgcolor="#1e1e22",
                    plot_bgcolor="#1e1e22", margin=dict(t=10),
                ) if not colors_df.empty else go.Figure(),
                config={"displayModeBar": False},
            ),
        ], style={"flex": "1"}),
    ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}),

    html.Hr(style={"borderColor": "#444", "margin": "24px 0"}),

    # Cross-sell
    html.H5("Cross-Sell Opportunities", style={"color": "#6f42c1"}),
    html.P("Brands frequently discussed by the same users.", style={"color": "#888", "fontSize": "0.85rem"}),
    make_table(cross_df.head(20)) if not cross_df.empty else html.P("No data"),
], style={"padding": "16px"})

# ---------------------------------------------------------------------------
# Tab 4: Buyer Profiles (NEW)
# ---------------------------------------------------------------------------

buyers_tab = html.Div([
    html.Div([
        html.Div([
            html.H5("User Segments", style={"color": "#ddd"}),
            dcc.Graph(
                figure=px.pie(
                    profiles_df.groupby("segment").size().reset_index(name="count")
                    if not profiles_df.empty else pd.DataFrame({"segment": [], "count": []}),
                    values="count", names="segment",
                    color_discrete_sequence=["#17a2b8", "#28a745", "#dc3545", "#ffc107", "#6f42c1"],
                ).update_layout(
                    template="plotly_dark", paper_bgcolor="#1e1e22", margin=dict(t=10),
                ),
                config={"displayModeBar": False},
            ),
        ], style={"flex": "1", "maxWidth": "400px"}),
        html.Div([
            html.H5("Top Users by Request Volume", style={"color": "#ddd"}),
            dcc.Graph(
                figure=px.bar(
                    profiles_df.head(15), x="user", y=["requests", "owned"],
                    barmode="group",
                    color_discrete_sequence=["#17a2b8", "#28a745"],
                    labels={"value": "Count", "variable": "Type"},
                ).update_layout(
                    template="plotly_dark", paper_bgcolor="#1e1e22",
                    plot_bgcolor="#1e1e22", margin=dict(t=10),
                ) if not profiles_df.empty else go.Figure(),
                config={"displayModeBar": False},
            ),
        ], style={"flex": "2"}),
    ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}),

    html.H5("All User Profiles", style={"color": "#ddd", "marginTop": "24px"}),
    make_table(profiles_df[["user", "segment", "requests", "owned", "satisfied",
                             "regrets", "buy_ratio"]].head(50)) if not profiles_df.empty else html.P("No data"),

    html.Hr(style={"borderColor": "#444", "margin": "24px 0"}),

    html.H5("Conversion Tracking (Request -> Purchase)", style={"color": "#28a745"}),
    make_table(conv_df.head(20)) if not conv_df.empty else html.P("No data"),
], style={"padding": "16px"})

# ---------------------------------------------------------------------------
# Tab 5: Trends Over Time
# ---------------------------------------------------------------------------

trends_tab = html.Div([
    html.Div([
        html.H5("Daily Mention Volume", style={"color": "#ddd"}),
        dcc.Graph(
            figure=px.area(
                daily_df, x="day", y=["requests", "satisfaction", "regret", "ownership"],
                labels={"value": "Mentions", "variable": "Intent"},
                color_discrete_sequence=["#17a2b8", "#28a745", "#dc3545", "#ffc107"],
            ).update_layout(
                template="plotly_dark", paper_bgcolor="#1e1e22",
                plot_bgcolor="#1e1e22", margin=dict(t=10),
                xaxis_title="Date", yaxis_title="Mentions",
            ) if not daily_df.empty else go.Figure().update_layout(
                template="plotly_dark", paper_bgcolor="#1e1e22",
            ),
            config={"displayModeBar": False}, style={"height": "350px"},
        ),
    ]),
    html.Div([
        html.Div([
            html.H5("Monthly Seasonality", style={"color": "#ddd", "marginTop": "24px"}),
            dcc.Graph(
                figure=px.line(
                    season_df, x="month", y=["total", "requests", "owned"],
                    labels={"value": "Mentions", "variable": "Type"},
                    color_discrete_sequence=["#6f42c1", "#17a2b8", "#28a745"],
                ).update_layout(
                    template="plotly_dark", paper_bgcolor="#1e1e22",
                    plot_bgcolor="#1e1e22", margin=dict(t=10),
                ) if not season_df.empty else go.Figure(),
                config={"displayModeBar": False}, style={"height": "300px"},
            ),
        ]),
    ]),
    html.Div([
        html.H5("Fastest Rising Items", style={"color": "#ddd", "marginTop": "24px"}),
        make_table(pd.DataFrame(DATA["trending"])) if DATA["trending"] else html.P("No trend data"),
    ]),
], style={"padding": "16px"})

# ---------------------------------------------------------------------------
# Tab 6: Channel Breakdown
# ---------------------------------------------------------------------------

channel_tab = html.Div([
    html.Div([
        html.Div([
            html.H5("Mentions by Channel", style={"color": "#ddd"}),
            dcc.Graph(
                figure=px.bar(
                    channels_df.head(15), x="channel", y="total",
                    color="avg_score", color_continuous_scale="RdYlGn",
                    labels={"total": "Mentions", "avg_score": "Avg Intent Score"},
                ).update_layout(
                    template="plotly_dark", paper_bgcolor="#1e1e22",
                    plot_bgcolor="#1e1e22", margin=dict(t=10),
                ) if not channels_df.empty else go.Figure(),
                config={"displayModeBar": False},
            ),
        ], style={"flex": "1"}),
        html.Div([
            html.H5("Intent Mix per Channel", style={"color": "#ddd"}),
            dcc.Graph(
                figure=px.bar(
                    channels_df.head(10), x="channel",
                    y=["requests", "satisfaction", "regret", "ownership"],
                    barmode="stack",
                    color_discrete_sequence=["#17a2b8", "#28a745", "#dc3545", "#ffc107"],
                ).update_layout(
                    template="plotly_dark", paper_bgcolor="#1e1e22",
                    plot_bgcolor="#1e1e22", margin=dict(t=10),
                ) if not channels_df.empty else go.Figure(),
                config={"displayModeBar": False},
            ),
        ], style={"flex": "1"}),
    ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}),
    html.Div([
        html.H5("Full Channel Data", style={"color": "#ddd", "marginTop": "24px"}),
        make_table(channels_df),
    ]),
], style={"padding": "16px"})

# ---------------------------------------------------------------------------
# Tab 7: Sentiment / Intent
# ---------------------------------------------------------------------------

sentiment_tab = html.Div([
    html.Div([
        html.Div([
            html.H5("Top Requested", style={"color": "#17a2b8"}),
            make_table(pd.DataFrame(DATA["top_requested"]).head(15)),
        ], style={"flex": "1"}),
        html.Div([
            html.H5("Most Loved", style={"color": "#28a745"}),
            make_table(pd.DataFrame(DATA["top_satisfaction"]).head(15)),
        ], style={"flex": "1"}),
    ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}),
    html.Div([
        html.Div([
            html.H5("Missed Opportunities (Regret)", style={"color": "#dc3545"}),
            make_table(pd.DataFrame(DATA["top_regret"]).head(15)),
        ], style={"flex": "1"}),
        html.Div([
            html.H5("Currently Owned", style={"color": "#ffc107"}),
            make_table(pd.DataFrame(DATA["top_ownership"]).head(15)),
        ], style={"flex": "1"}),
    ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap", "marginTop": "24px"}),
], style={"padding": "16px"})

# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------

app.layout = html.Div([
    html.H2("Demand Intelligence Dashboard",
            style={"textAlign": "center", "color": "#ddd", "padding": "16px 0 8px"}),
    dcc.Tabs([
        dcc.Tab(label="Overview", children=overview_tab,
                style=TAB_STYLE, selected_style=TAB_SELECTED),
        dcc.Tab(label="Sales Intel", children=sales_tab,
                style=TAB_STYLE, selected_style=TAB_SELECTED),
        dcc.Tab(label="Buyer Profiles", children=buyers_tab,
                style=TAB_STYLE, selected_style=TAB_SELECTED),
        dcc.Tab(label="Top Items", children=top_items_tab,
                style=TAB_STYLE, selected_style=TAB_SELECTED),
        dcc.Tab(label="Trends", children=trends_tab,
                style=TAB_STYLE, selected_style=TAB_SELECTED),
        dcc.Tab(label="Channels", children=channel_tab,
                style=TAB_STYLE, selected_style=TAB_SELECTED),
        dcc.Tab(label="Intent", children=sentiment_tab,
                style=TAB_STYLE, selected_style=TAB_SELECTED),
    ], style={"marginBottom": "0"}),
], style={"backgroundColor": "#1a1a1e", "minHeight": "100vh", "fontFamily": "system-ui, sans-serif"})


def main():
    log.info("Starting dashboard at http://127.0.0.1:8050")
    app.run(debug=True, host="127.0.0.1", port=8050)


if __name__ == "__main__":
    main()
