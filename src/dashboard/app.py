"""ZR ItemFinder — Demand Intelligence Dashboard.

A production-ready web dashboard that turns Discord chat analysis into
actionable sales intelligence. Every metric is explained in plain English.

Usage: python -m src.dashboard.app
"""

import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, callback, dcc, html

from src.analytics.sales_intel import (
    brand_cross_sell, buyer_profiles, color_demand,
    conversion_tracking, inventory_recommendations,
    monthly_seasonality, size_demand, unmet_demand,
)
from src.analytics.trends import (
    channel_breakdown, daily_volume, top_items_by_intent, trending_items,
)
from src.common.db import get_connection, processed_mention_count, raw_message_count
from src.common.log_util import get_logger
from src.dashboard.components import (
    C_AMBER, C_BLUE, C_CYAN, C_GREEN, C_PURPLE, C_RED,
    action_box, chart_card, empty_fig, explainer, kpi,
    make_table, section, style_fig,
)
from src.process.scoring import compute_brand_scores, compute_item_scores

log = get_logger("dashboard")


# ── Data loading ──────────────────────────────────────────────────────────

def _load():
    conn = get_connection()
    d = dict(
        raw=raw_message_count(conn),
        mentions=processed_mention_count(conn),
        items=compute_item_scores(conn),
        brands=compute_brand_scores(conn),
        trending=trending_items(conn, 20),
        channels=channel_breakdown(conn),
        daily=daily_volume(conn),
        req=top_items_by_intent(conn, "request", 30),
        sat=top_items_by_intent(conn, "satisfaction", 30),
        reg=top_items_by_intent(conn, "regret", 30),
        own=top_items_by_intent(conn, "ownership", 30),
        unmet=unmet_demand(conn, 3),
        profiles=buyer_profiles(conn, 20),
        cross=brand_cross_sell(conn, 10),
        sizes=size_demand(conn),
        colors=color_demand(conn),
        inv=inventory_recommendations(conn),
        season=monthly_seasonality(conn),
        conv=conversion_tracking(conn),
    )
    rows = conn.execute(
        "SELECT intent_type, COUNT(*) as count "
        "FROM processed_mentions GROUP BY intent_type"
    ).fetchall()
    d["intent_dist"] = pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
    conn.close()
    return d


D = _load()


def _df(key):
    return pd.DataFrame(D[key]) if D[key] else pd.DataFrame()


items_df = _df("items")
brands_df = _df("brands")
channels_df = _df("channels")
daily_df = _df("daily")
unmet_df = _df("unmet")
sizes_df = _df("sizes")
colors_df = _df("colors")
cross_df = _df("cross")
inv_df = _df("inv")
season_df = _df("season")
conv_df = _df("conv")
trending_df = _df("trending")
req_df = _df("req")
sat_df = _df("sat")
reg_df = _df("reg")
own_df = _df("own")
profiles_df = pd.DataFrame([
    {k: v for k, v in p.items() if k not in ("top_brands", "top_requests")}
    for p in D["profiles"]
]) if D["profiles"] else pd.DataFrame()
n_brands = len(brands_df)
n_items = len(items_df)


# ── App setup ─────────────────────────────────────────────────────────────

app = Dash(
    __name__,
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap",
    ],
    suppress_callback_exceptions=True,
)
app.title = "ZR ItemFinder — Demand Intelligence"


# ── Tab 1: Overview ───────────────────────────────────────────────────────

def _overview():
    actions = []
    if not unmet_df.empty:
        t = unmet_df.iloc[0]
        actions.append(f"Stock {t['brand']} {t['item']} — {t['demand_gap']} people want it but can't find it")
    if not sizes_df.empty:
        actions.append(f"Focus on sizes {', '.join(sizes_df.head(3)['size'].tolist())} — most requested")
    if not cross_df.empty:
        c = cross_df.iloc[0]
        actions.append(f"Bundle {c['brand_a']} + {c['brand_b']} — {c['shared_users']} customers want both")

    return html.Div([
        explainer([
            html.Strong("Welcome to your Demand Intelligence Dashboard. "),
            "This tool analyzes thousands of Discord messages from your community to find ",
            html.Strong("what people want to buy"), ", ",
            html.Strong("what's trending"), ", and ",
            html.Strong("where the biggest sales opportunities are"),
            ". Every number here comes from real conversations in your Discord servers.",
        ]),
        html.Div([
            kpi(D["raw"], "Messages Scanned", C_CYAN),
            kpi(D["mentions"], "Product Mentions", C_GREEN),
            kpi(n_brands, "Brands Detected", C_AMBER),
            kpi(n_items, "Item Combinations", C_RED),
            kpi(len(D["channels"]), "Channels Analyzed", C_PURPLE),
        ], className="kpi-row"),
        explainer([
            html.Strong("Messages Scanned: "), "Total Discord messages we processed. ",
            html.Strong("Product Mentions: "), "Messages where someone talked about a specific brand or item. ",
            html.Strong("Brands: "), "Unique brands people mentioned. ",
            html.Strong("Item Combinations: "), "Unique brand + item pairs (e.g. 'Balenciaga hoodie'). ",
            html.Strong("Channels: "), "Discord channels with product discussion.",
        ], "green"),
        html.Div([
            chart_card("Top 15 Brands by Mentions",
                       "Taller bars = more popular. Color shows trend momentum (brighter = rising).",
                       dcc.Graph(
                           figure=style_fig(px.bar(
                               brands_df.head(15), x="brand", y="mentions",
                               color="trend_score", color_continuous_scale="Viridis",
                               labels={"mentions": "Total Mentions", "trend_score": "Trend"},
                           )) if not brands_df.empty else empty_fig(),
                           config={"displayModeBar": False},
                       )),
            chart_card("What People Are Saying (Intent Breakdown)",
                       "Shows the mix of buying signals across your community.",
                       dcc.Graph(
                           figure=style_fig(px.pie(
                               D["intent_dist"], values="count", names="intent_type",
                               color_discrete_sequence=[C_BLUE, C_GREEN, C_RED, C_AMBER, "#6b7280"],
                           )) if not D["intent_dist"].empty else empty_fig(),
                           config={"displayModeBar": False},
                       )),
        ], className="two-col"),
        explainer([
            html.Strong("Intent types: "),
            html.Strong("Request"), " = looking to buy. ",
            html.Strong("Ownership"), " = just bought it. ",
            html.Strong("Satisfaction"), " = positive review. ",
            html.Strong("Regret"), " = missed opportunity. ",
            html.Strong("Neutral"), " = mentioned without clear buying intent.",
        ], "purple"),
        action_box("Top Actions Based on Your Data", actions) if actions else html.Div(),
    ], className="page-content")


# ── Tab 2: What to Stock ─────────────────────────────────────────────────

def _stock():
    return html.Div([
        explainer([
            html.Strong("Unmet Demand = Sales Opportunity. "),
            "These items are ", html.Strong("actively requested"),
            " but ", html.Strong("almost nobody has them yet"),
            ". The bigger the gap between 'People Asking' and 'People Who Have It', ",
            "the bigger your opportunity. Stock these to fill real demand.",
        ], "red"),
        section("Unmet Demand — Items People Want but Can't Get",
                "Sorted by demand gap. Higher gap = bigger opportunity."),
        make_table(unmet_df.head(20), {
            "brand": "Brand", "item": "Item", "requests": "People Asking",
            "owned": "People Who Have It", "demand_gap": "Unmet Gap",
            "unique_requesters": "Unique Buyers",
        }),
        section("Inventory Recommendations",
                "AI-prioritized stocking suggestions based on all demand signals."),
        explainer([
            html.Strong("Priority levels: "),
            html.Strong("HIGH"), " = 10+ unmet requests, stock immediately. ",
            html.Strong("MEDIUM"), " = 5-9 unmet requests, strong opportunity. ",
            html.Strong("LOW"), " = 2-4 unmet requests, worth watching.",
        ], "amber"),
        make_table(inv_df.head(15), {
            "priority": "Priority", "brand": "Brand", "item": "Item",
            "demand_gap": "Demand Gap", "notes": "Why",
        }),
        html.Div([
            chart_card("Most Requested Sizes",
                       "Blue = people asking. Green = people who own it.",
                       dcc.Graph(
                           figure=style_fig(px.bar(
                               sizes_df.head(12), x="size", y=["requests", "owned"],
                               barmode="group", color_discrete_sequence=[C_BLUE, C_GREEN],
                               labels={"value": "Count", "variable": ""},
                           )) if not sizes_df.empty else empty_fig(),
                           config={"displayModeBar": False},
                       )),
            chart_card("Most Requested Colors",
                       "Blue = people asking. Green = people who own it.",
                       dcc.Graph(
                           figure=style_fig(px.bar(
                               colors_df.head(12), x="color", y=["requests", "owned"],
                               barmode="group", color_discrete_sequence=[C_BLUE, C_GREEN],
                               labels={"value": "Count", "variable": ""},
                           )) if not colors_df.empty else empty_fig(),
                           config={"displayModeBar": False},
                       )),
        ], className="two-col"),
        explainer([
            html.Strong("Size & Color Tip: "),
            "When the blue bar (requests) is much taller than green (owned), ",
            "people want it but can't find it. Prioritize those variants.",
        ], "green"),
    ], className="page-content")


# ── Tab 3: Customer Insights ─────────────────────────────────────────────

def _customers():
    return html.Div([
        explainer([
            html.Strong("Know your customers. "),
            "We analyze each user's Discord activity to understand buying behavior. ",
            html.Strong("Loyal Buyers"), " buy often. ",
            html.Strong("High-Intent Prospects"), " ask for a lot but buy little (untapped opportunity). ",
            html.Strong("Active Buyers"), " moderate buying. ",
            html.Strong("Browsers"), " window shopping. ",
            html.Strong("Casual"), " light activity.",
        ]),
        html.Div([
            chart_card("Customer Segments",
                       "How your community breaks down by buying behavior.",
                       dcc.Graph(
                           figure=style_fig(px.pie(
                               profiles_df.groupby("segment").size().reset_index(name="count")
                               if not profiles_df.empty
                               else pd.DataFrame({"segment": [], "count": []}),
                               values="count", names="segment",
                               color_discrete_sequence=[C_BLUE, C_GREEN, C_RED, C_AMBER, C_PURPLE],
                           )),
                           config={"displayModeBar": False},
                       )),
            chart_card("Top Users by Activity",
                       "Blue = items requested. Green = items bought.",
                       dcc.Graph(
                           figure=style_fig(px.bar(
                               profiles_df.head(15), x="user", y=["requests", "owned"],
                               barmode="group", color_discrete_sequence=[C_BLUE, C_GREEN],
                               labels={"value": "Count", "variable": ""},
                           )) if not profiles_df.empty else empty_fig(),
                           config={"displayModeBar": False},
                       )),
        ], className="two-col"),
        section("Customer Profiles"),
        explainer([
            html.Strong("Buy Ratio"), " = what % of requests turned into purchases. ",
            "0.50 means half their asks led to buying. ",
            "Low ratio + high requests = target with offers.",
        ], "amber"),
        make_table(profiles_df.head(50), {
            "user": "Username", "segment": "Segment", "requests": "Requests",
            "owned": "Purchased", "satisfied": "Happy Reviews",
            "regrets": "Missed Items", "buy_ratio": "Buy Ratio",
        }),
        section("Cross-Sell Opportunities",
                "Brands the same customers discuss — bundle these for higher sales."),
        explainer([
            html.Strong("Cross-sell: "),
            "If someone likes Brand A, they likely want Brand B too. ",
            "Use this to create bundles or plan inventory together.",
        ], "purple"),
        make_table(cross_df.head(15), {
            "brand_a": "Brand A", "brand_b": "Brand B",
            "shared_users": "Customers in Common",
        }),
        section("Conversions (Request to Purchase)",
                "People who asked about a brand AND later bought it."),
        explainer(
            "High conversion brands are safer to stock heavily — proven demand.",
            "green",
        ),
        make_table(conv_df.head(15), {
            "author": "Customer", "brand": "Brand", "requests": "Times Asked",
            "owned": "Times Bought", "satisfied": "Happy Reviews",
        }),
    ], className="page-content")


# ── Tab 4: Item Explorer ─────────────────────────────────────────────────

def _explorer():
    return html.Div([
        explainer([
            html.Strong("Search and explore all detected items. "),
            "Type a brand or item name to filter. Click column headers to sort. ",
            html.Strong("Score"), " combines popularity (20%), buying intent strength (50%), ",
            "and trend momentum (30%) — higher = more valuable to stock. ",
            html.Strong("Velocity"), " shows trend direction: positive = rising, negative = cooling.",
        ]),
        html.Div([
            dcc.Input(id="item-search", type="text",
                      placeholder="Type a brand or item name to filter..."),
        ], className="search-input", style={"marginBottom": "16px"}),
        html.Div(id="items-table-container"),
    ], className="page-content")


# ── Tab 5: Market Trends ─────────────────────────────────────────────────

def _trends():
    return html.Div([
        explainer([
            html.Strong("Track how demand changes over time. "),
            "Spikes often correspond to new drops, restocks, or community hype events. ",
            "The trending table shows what's gaining momentum ",
            html.Strong("right now"), ".",
        ]),
        chart_card("Daily Activity by Intent Type",
                   "Each color = a different signal. Spikes = high activity days.",
                   dcc.Graph(
                       figure=style_fig(px.area(
                           daily_df, x="day",
                           y=["requests", "satisfaction", "regret", "ownership"],
                           color_discrete_sequence=[C_BLUE, C_GREEN, C_RED, C_AMBER],
                           labels={"value": "Mentions", "variable": "Signal", "day": "Date"},
                       )) if not daily_df.empty else empty_fig(),
                       config={"displayModeBar": False}, style={"height": "350px"},
                   )),
        section("Fastest Rising Items",
                "Biggest increase in mentions this period vs. previous period."),
        explainer([
            html.Strong("Velocity"), " measures momentum. ",
            html.Strong("+2.0x"), " means 3x more mentions than last period. ",
            "High velocity + high requests = about to blow up.",
        ], "amber"),
        make_table(trending_df.head(20), {
            "brand": "Brand", "item": "Item", "recent_mentions": "This Period",
            "prev_mentions": "Last Period", "velocity": "Velocity",
        }),
        chart_card("Monthly Activity Patterns",
                   "Seasonal trends — use this to plan inventory for busy months.",
                   dcc.Graph(
                       figure=style_fig(px.line(
                           season_df, x="month", y=["total", "requests", "owned"],
                           color_discrete_sequence=[C_PURPLE, C_BLUE, C_GREEN],
                           labels={"value": "Mentions", "variable": "Type", "month": "Month"},
                       )) if not season_df.empty else empty_fig(),
                       config={"displayModeBar": False}, style={"height": "300px"},
                   )),
    ], className="page-content")


# ── Tab 6: Channel Analysis ──────────────────────────────────────────────

def _channels_tab():
    return html.Div([
        explainer([
            html.Strong("Not all channels are equal. "),
            "WTB (Want to Buy) channels give the strongest buying signals. ",
            "Pickups show actual purchases. General chat has more noise. ",
            "Use this to understand ", html.Strong("where"), " signals come from.",
        ]),
        html.Div([
            chart_card("Mentions by Channel",
                       "Which channels produce the most product discussion.",
                       dcc.Graph(
                           figure=style_fig(px.bar(
                               channels_df.head(12), x="channel", y="total",
                               color="avg_score", color_continuous_scale="RdYlGn",
                               labels={"total": "Mentions", "avg_score": "Signal Strength"},
                           )) if not channels_df.empty else empty_fig(),
                           config={"displayModeBar": False},
                       )),
            chart_card("Intent Mix per Channel",
                       "What type of messages each channel produces.",
                       dcc.Graph(
                           figure=style_fig(px.bar(
                               channels_df.head(10), x="channel",
                               y=["requests", "satisfaction", "regret", "ownership"],
                               barmode="stack",
                               color_discrete_sequence=[C_BLUE, C_GREEN, C_RED, C_AMBER],
                               labels={"value": "Count", "variable": "Signal"},
                           )) if not channels_df.empty else empty_fig(),
                           config={"displayModeBar": False},
                       )),
        ], className="two-col"),
        explainer([
            html.Strong("Signal Strength (color): "),
            "Green = high-quality buying signals (WTB, pickups). ",
            "Yellow/red = lower intent (general chat). ",
            "Prioritize green channels for stocking decisions.",
        ], "green"),
        section("Full Channel Data"),
        make_table(channels_df, {
            "channel": "Channel", "total": "Total", "requests": "Buy Requests",
            "satisfaction": "Happy", "regret": "Missed Opp.",
            "ownership": "Purchases", "avg_score": "Strength",
        }),
    ], className="page-content")


# ── Tab 7: Demand Signals ────────────────────────────────────────────────

def _signals():
    return html.Div([
        explainer([
            html.Strong("Four types of demand signals:"), html.Br(),
            html.Strong("Requests", style={"color": C_BLUE}),
            " — Actively looking to buy ('WTB', 'looking for', 'need').", html.Br(),
            html.Strong("Satisfaction", style={"color": C_GREEN}),
            " — Positive reviews ('fire', 'love it', '10/10').", html.Br(),
            html.Strong("Regret", style={"color": C_RED}),
            " — Wish they'd bought it ('should have copped', 'missed out').", html.Br(),
            html.Strong("Ownership", style={"color": C_AMBER}),
            " — Just received it ('just copped', 'in hand').",
        ]),
        html.Div([
            html.Div([
                section("Most Requested (People Want These)"),
                make_table(req_df.head(15), {
                    "brand": "Brand", "item": "Item",
                    "count": "Requests", "avg_score": "Strength",
                }),
            ], style={"flex": "1", "minWidth": "300px"}),
            html.Div([
                section("Most Loved (High Satisfaction)"),
                make_table(sat_df.head(15), {
                    "brand": "Brand", "item": "Item",
                    "count": "Reviews", "avg_score": "Strength",
                }),
            ], style={"flex": "1", "minWidth": "300px"}),
        ], className="two-col"),
        html.Div([
            html.Div([
                section("Missed Opportunities (Regret)"),
                explainer(
                    "High regret = people want these but missed out. "
                    "Stock them to capture pent-up demand.", "red",
                ),
                make_table(reg_df.head(15), {
                    "brand": "Brand", "item": "Item",
                    "count": "Regret Mentions", "avg_score": "Strength",
                }),
            ], style={"flex": "1", "minWidth": "300px"}),
            html.Div([
                section("Recently Purchased (Ownership)"),
                explainer(
                    "Items people are actively buying. High ownership + high satisfaction "
                    "= safe to keep stocking.", "green",
                ),
                make_table(own_df.head(15), {
                    "brand": "Brand", "item": "Item",
                    "count": "Purchases", "avg_score": "Strength",
                }),
            ], style={"flex": "1", "minWidth": "300px"}),
        ], className="two-col"),
    ], className="page-content")


# ── Main layout ───────────────────────────────────────────────────────────

app.layout = html.Div([
    html.Div([
        html.Div([
            html.H1("ZR ItemFinder"),
            html.Div("Demand Intelligence for Resellers", className="subtitle"),
        ]),
        html.Div([
            html.Div([html.Div(f"{D['raw']:,}", className="num"),
                       html.Div("Messages", className="lbl")], className="header-stat"),
            html.Div([html.Div(f"{D['mentions']:,}", className="num"),
                       html.Div("Mentions", className="lbl")], className="header-stat"),
            html.Div([html.Div(str(n_brands), className="num"),
                       html.Div("Brands", className="lbl")], className="header-stat"),
        ], className="header-stats"),
    ], className="site-header"),

    dcc.Tabs(className="custom-tabs", children=[
        dcc.Tab(label="Overview", children=_overview(),
                className="tab", selected_className="tab--selected"),
        dcc.Tab(label="What to Stock", children=_stock(),
                className="tab", selected_className="tab--selected"),
        dcc.Tab(label="Customer Insights", children=_customers(),
                className="tab", selected_className="tab--selected"),
        dcc.Tab(label="Item Explorer", children=_explorer(),
                className="tab", selected_className="tab--selected"),
        dcc.Tab(label="Market Trends", children=_trends(),
                className="tab", selected_className="tab--selected"),
        dcc.Tab(label="Channel Analysis", children=_channels_tab(),
                className="tab", selected_className="tab--selected"),
        dcc.Tab(label="Demand Signals", children=_signals(),
                className="tab", selected_className="tab--selected"),
    ]),

    html.Div([
        html.P("ZR ItemFinder v1.0 — Data from Discord community analysis",
               style={"color": "var(--text-muted)", "fontSize": "0.75rem",
                       "textAlign": "center", "padding": "20px 0"}),
    ], style={"borderTop": "1px solid var(--border)", "marginTop": "32px"}),
])


# ── Callbacks ─────────────────────────────────────────────────────────────

@callback(Output("items-table-container", "children"), Input("item-search", "value"))
def _filter_items(term):
    df = items_df.copy()
    if df.empty:
        return html.P("No data.", style={"color": "#6b7280"})
    if term:
        mask = (df["brand"].str.contains(term, case=False, na=False)
                | df["item"].str.contains(term, case=False, na=False))
        df = df[mask]
    return make_table(df.head(100), {
        "brand": "Brand", "item": "Item", "variant": "Variant",
        "total_mentions": "Mentions", "request_count": "Requests",
        "satisfaction_count": "Happy", "regret_count": "Regret",
        "velocity": "Velocity", "final_score": "Score",
    })


# ── Entry point ───────────────────────────────────────────────────────────

def main():
    log.info("Starting dashboard at http://127.0.0.1:8050")
    app.run(debug=True, host="127.0.0.1", port=8050)


if __name__ == "__main__":
    main()
