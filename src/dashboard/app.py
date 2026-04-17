"""ZR ItemFinder — Demand Intelligence Dashboard.

A production-ready web dashboard that turns Discord chat analysis into
actionable sales intelligence. Every metric is explained in plain English.

Usage: python -m src.dashboard.app
"""

from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, Input, Output, callback, dcc, html

from src.analytics.market_intel import (
    category_breakdown as mi_category_breakdown,
    demand_heatmap_data,
    get_1688_sales,
    get_batch_guide,
    get_external_trending,
    get_subreddit_stats,
    get_upcoming_releases,
    get_watch_factory_guide,
    get_weidian_sales,
    platform_comparison,
    purchase_recommendations,
    trend_direction_summary,
)
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

TIMEFRAME_OPTIONS = [
    {"label": "7 Days", "value": "7"},
    {"label": "14 Days", "value": "14"},
    {"label": "30 Days", "value": "30"},
    {"label": "60 Days", "value": "60"},
    {"label": "90 Days", "value": "90"},
    {"label": "All Time", "value": "all"},
]

PLATFORM_OPTIONS = [
    {"label": "Combined", "value": "all"},
    {"label": "Discord", "value": "discord"},
    {"label": "Reddit", "value": "reddit"},
]

_PLATFORM_LABELS = {"all": "Discord + Reddit", "discord": "Discord", "reddit": "Reddit"}


# ── Data loading ──────────────────────────────────────────────────────────

def _load(since: str | None = None, platform: str | None = None):
    plat = platform if platform and platform != "all" else None
    conn = get_connection()
    d = dict(
        raw=raw_message_count(conn, since=since, platform=plat),
        mentions=processed_mention_count(conn, since=since, platform=plat),
        items=compute_item_scores(conn, since=since, platform=plat),
        brands=compute_brand_scores(conn, since=since, platform=plat),
        trending=trending_items(conn, 20, since=since, platform=plat),
        channels=channel_breakdown(conn, since=since, platform=plat),
        daily=daily_volume(conn, since=since, platform=plat),
        req=top_items_by_intent(conn, "request", 30, since=since, platform=plat),
        sat=top_items_by_intent(conn, "satisfaction", 30, since=since, platform=plat),
        reg=top_items_by_intent(conn, "regret", 30, since=since, platform=plat),
        own=top_items_by_intent(conn, "ownership", 30, since=since, platform=plat),
        unmet=unmet_demand(conn, 3, since=since, platform=plat),
        profiles=buyer_profiles(conn, 20, since=since, platform=plat),
        cross=brand_cross_sell(conn, 10, since=since, platform=plat),
        sizes=size_demand(conn, since=since, platform=plat),
        colors=color_demand(conn, since=since, platform=plat),
        inv=inventory_recommendations(conn, since=since, platform=plat),
        season=monthly_seasonality(conn, since=since, platform=plat),
        conv=conversion_tracking(conn, since=since, platform=plat),
        platform_label=_PLATFORM_LABELS.get(platform or "all", "Discord + Reddit"),
    )
    # Intent distribution with platform filter
    plat_clause = " AND message_id IN (SELECT id FROM raw_messages WHERE source_platform = ?)" if plat else ""
    plat_params = [plat] if plat else []
    since_clause = " AND timestamp >= ?" if since else ""
    since_params = [since] if since else []
    rows = conn.execute(
        "SELECT intent_type, COUNT(*) as count "
        "FROM processed_mentions "
        "WHERE 1=1" + plat_clause + since_clause
        + " GROUP BY intent_type",
        plat_params + since_params,
    ).fetchall()
    d["intent_dist"] = pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
    conn.close()
    return d


def _df(data, key):
    return pd.DataFrame(data[key]) if data[key] else pd.DataFrame()


# ── App setup ─────────────────────────────────────────────────────────────

app = Dash(
    __name__,
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap",
    ],
    suppress_callback_exceptions=True,
)
app.title = "ZR ItemFinder — Demand Intelligence"


# ── Tab builders (all take data dict D) ──────────────────────────────────

def _overview(D):
    items_df = _df(D, "items")
    brands_df = _df(D, "brands")
    unmet_df = _df(D, "unmet")
    sizes_df = _df(D, "sizes")
    cross_df = _df(D, "cross")
    n_brands = len(brands_df)
    n_items = len(items_df)

    actions = []
    if not unmet_df.empty:
        t = unmet_df.iloc[0]
        actions.append(f"Stock {t['brand']} {t['item']} — {t['demand_gap']} people want it but can't find it")
    if not sizes_df.empty:
        actions.append(f"Focus on sizes {', '.join(sizes_df.head(3)['size'].tolist())} — most requested")
    if not cross_df.empty:
        c = cross_df.iloc[0]
        actions.append(f"Bundle {c['brand_a']} + {c['brand_b']} — {c['shared_users']} customers want both")

    plabel = D.get("platform_label", "Discord + Reddit")
    return html.Div([
        explainer([
            html.Strong("Welcome to your Demand Intelligence Dashboard. "),
            f"This tool analyzes thousands of {plabel} messages from your community to find ",
            html.Strong("what people want to buy"), ", ",
            html.Strong("what's trending"), ", and ",
            html.Strong("where the biggest sales opportunities are"),
            f". Every number here comes from real conversations across {plabel}.",
        ]),
        html.Div([
            kpi(D["raw"], "Messages Scanned", C_CYAN),
            kpi(D["mentions"], "Product Mentions", C_GREEN),
            kpi(n_brands, "Brands Detected", C_AMBER),
            kpi(n_items, "Item Combinations", C_RED),
            kpi(len(D["channels"]), "Channels Analyzed", C_PURPLE),
        ], className="kpi-row"),
        explainer([
            html.Strong("Messages Scanned: "), f"Total {plabel} messages we processed. ",
            html.Strong("Product Mentions: "), "Messages where someone talked about a specific brand or item. ",
            html.Strong("Brands: "), "Unique brands people mentioned. ",
            html.Strong("Item Combinations: "), "Unique brand + item pairs (e.g. 'Balenciaga hoodie'). ",
            html.Strong("Channels: "), "Channels / subreddits with product discussion.",
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


def _stock(D):
    unmet_df = _df(D, "unmet")
    inv_df = _df(D, "inv")
    sizes_df = _df(D, "sizes")
    colors_df = _df(D, "colors")

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


def _customers(D):
    profiles_df = pd.DataFrame([
        {k: v for k, v in p.items() if k not in ("top_brands", "top_requests")}
        for p in D["profiles"]
    ]) if D["profiles"] else pd.DataFrame()
    cross_df = _df(D, "cross")
    conv_df = _df(D, "conv")

    return html.Div([
        explainer([
            html.Strong("Know your customers. "),
            "We analyze each user's activity to understand buying behavior. ",
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


def _explorer(D):
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


def _trends(D):
    daily_df = _df(D, "daily")
    trending_df = _df(D, "trending")
    season_df = _df(D, "season")

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


def _channels_tab(D):
    channels_df = _df(D, "channels")

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


def _signals(D):
    req_df = _df(D, "req")
    sat_df = _df(D, "sat")
    reg_df = _df(D, "reg")
    own_df = _df(D, "own")

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


# ── Market Intelligence tab ──────────────────────────────────────────────

def _market_intel(D):
    """External market intelligence — Reddit trends, Weidian/1688 sales,
    batch guides, upcoming releases, and purchase recommendations."""

    ext_trending = pd.DataFrame(get_external_trending())
    weidian_df = pd.DataFrame(get_weidian_sales())
    sales_1688_df = pd.DataFrame(get_1688_sales())
    batch_df = pd.DataFrame(get_batch_guide())
    watch_df = pd.DataFrame(get_watch_factory_guide())
    releases_df = pd.DataFrame(get_upcoming_releases())
    subs_df = pd.DataFrame(get_subreddit_stats())
    cat_df = pd.DataFrame(mi_category_breakdown())
    plat_df = pd.DataFrame(platform_comparison())
    heatmap_raw = demand_heatmap_data()
    trend_dirs = pd.DataFrame(trend_direction_summary())

    # Purchase recommendations (enriched with internal data if available)
    try:
        conn = get_connection()
        recs = purchase_recommendations(conn)
        conn.close()
    except Exception:
        recs = purchase_recommendations()
    recs_df = pd.DataFrame(recs)

    # ── KPI row ──
    total_items_tracked = len(ext_trending)
    very_high = len(ext_trending[ext_trending["demand"] == "very_high"]) if not ext_trending.empty else 0
    total_weidian_sold = weidian_df["units_sold"].sum() if not weidian_df.empty else 0
    total_1688_sold = sales_1688_df["units_sold"].sum() if not sales_1688_df.empty else 0
    total_subs_reach = subs_df["members"].sum() if not subs_df.empty else 0
    n_categories = ext_trending["category"].nunique() if not ext_trending.empty else 0

    # ── Demand heatmap ──
    if heatmap_raw:
        hm_df = pd.DataFrame(heatmap_raw)
        brands_hm = hm_df["brand"].unique().tolist()
        cats_hm = hm_df["category"].unique().tolist()
        z = []
        for cat in cats_hm:
            row = []
            for brand in brands_hm:
                match = hm_df[(hm_df["brand"] == brand) & (hm_df["category"] == cat)]
                row.append(match["demand_score"].values[0] if not match.empty else 0)
            z.append(row)
        heatmap_fig = go.Figure(data=go.Heatmap(
            z=z, x=brands_hm, y=cats_hm,
            colorscale=[[0, "#1a1d27"], [0.3, "#1e3a5f"], [0.6, "#3b82f6"], [1, "#22c55e"]],
            hovertemplate="Brand: %{x}<br>Category: %{y}<br>Demand: %{z:.2f}<extra></extra>",
        ))
        heatmap_fig.update_layout(xaxis_tickangle=-45)
    else:
        heatmap_fig = go.Figure()

    # ── Weidian sales bar chart ──
    if not weidian_df.empty:
        weidian_fig = px.bar(
            weidian_df.sort_values("units_sold", ascending=True),
            x="units_sold", y="item", orientation="h",
            color="trend",
            color_discrete_map={"rising": C_GREEN, "stable": C_BLUE, "cooling": C_AMBER},
            labels={"units_sold": "Units Sold (30d)", "item": "", "trend": "Trend"},
            custom_data=["brand"],
        )
        weidian_fig.update_traces(
            hovertemplate="<b>%{customdata[0]}</b> %{y}<br>Units: %{x}<extra></extra>"
        )
    else:
        weidian_fig = go.Figure()

    # ── 1688 sales bar chart ──
    if not sales_1688_df.empty:
        fig_1688 = px.bar(
            sales_1688_df.sort_values("units_sold", ascending=True),
            x="units_sold", y="item", orientation="h",
            color="trend",
            color_discrete_map={"rising": C_GREEN, "stable": C_BLUE, "cooling": C_AMBER},
            labels={"units_sold": "Units Sold (30d)", "item": "", "trend": "Trend"},
            custom_data=["brand"],
        )
        fig_1688.update_traces(
            hovertemplate="<b>%{customdata[0]}</b> %{y}<br>Units: %{x}<extra></extra>"
        )
    else:
        fig_1688 = go.Figure()

    # ── Category breakdown pie ──
    if not cat_df.empty:
        cat_fig = px.pie(
            cat_df, values="total", names="category",
            color_discrete_sequence=[C_BLUE, C_GREEN, C_PURPLE, C_AMBER, C_RED, C_CYAN],
        )
    else:
        cat_fig = go.Figure()

    # ── Subreddit reach bar ──
    if not subs_df.empty:
        subs_fig = px.bar(
            subs_df.sort_values("members", ascending=True),
            x="members", y="subreddit", orientation="h",
            color="signal_weight",
            color_continuous_scale=[[0, "#f59e0b"], [0.5, "#3b82f6"], [1, "#22c55e"]],
            labels={"members": "Members", "subreddit": "", "signal_weight": "Signal Weight"},
        )
    else:
        subs_fig = go.Figure()

    # ── Trend direction donut ──
    if not trend_dirs.empty:
        trend_colors = {"rising": C_GREEN, "stable": C_BLUE, "cooling": C_AMBER}
        trend_fig = px.pie(
            trend_dirs, values="count", names="direction",
            color="direction", color_discrete_map=trend_colors,
            hole=0.5,
        )
    else:
        trend_fig = go.Figure()

    # ── Platform comparison: top 15 across both platforms ──
    if not plat_df.empty:
        top15 = plat_df.head(15)
        plat_comp_fig = px.bar(
            top15.sort_values("units_sold", ascending=True),
            x="units_sold", y="item", orientation="h",
            color="source",
            color_discrete_map={"Weidian": C_PURPLE, "1688": C_CYAN},
            labels={"units_sold": "Units Sold", "item": "", "source": "Platform"},
            custom_data=["brand"],
        )
        plat_comp_fig.update_traces(
            hovertemplate="<b>%{customdata[0]}</b> %{y}<br>Units: %{x}<extra></extra>"
        )
    else:
        plat_comp_fig = go.Figure()

    # ── Recommendation score distribution ──
    if not recs_df.empty:
        top_recs = recs_df.head(20)
        recs_fig = px.bar(
            top_recs.sort_values("combined_score", ascending=True),
            x="combined_score", y=top_recs.apply(
                lambda r: f"{r['brand']} — {r['item']}", axis=1
            ).values[::-1] if not top_recs.empty else [],
            orientation="h",
            color="combined_score",
            color_continuous_scale=[[0, "#ef4444"], [0.5, "#f59e0b"], [1, "#22c55e"]],
            labels={"combined_score": "Opportunity Score", "y": ""},
        )
    else:
        recs_fig = go.Figure()

    # ── Build the page ──
    return html.Div([
        # Header explainer
        explainer([
            html.Strong("Market Intelligence — External Trend Analysis. "),
            "This page combines data from ",
            html.Strong("15+ Reddit communities"), " (FashionReps, Repsneakers, RepTime, DesignerReps, RepLadies, etc.), ",
            html.Strong("Weidian/1688 live sales"), " (JadeShip/RepArchive agent tracking), ",
            html.Strong("QC platforms"), " (doppel.fit, FinderQC, FindQC), and ",
            html.Strong("upcoming releases"), " to identify the best items to purchase right now. ",
            "Covers ", html.Strong("sneakers, clothing, bags, jewelry, watches, accessories, "
            "eyewear, home decor, fragrances, and tech accessories"), ". ",
            "Data reflects April 2026 market conditions.",
        ]),

        # KPI Row
        html.Div([
            kpi(total_items_tracked, "Items Tracked", C_CYAN),
            kpi(n_categories, "Categories", C_BLUE),
            kpi(very_high, "Very High Demand", C_RED),
            kpi(f"{total_weidian_sold:,}", "Weidian Sales (30d)", C_PURPLE),
            kpi(f"{total_1688_sold:,}", "1688 Sales (30d)", C_AMBER),
            kpi(f"{total_subs_reach / 1_000_000:.1f}M", "Reddit Reach", C_GREEN),
        ], className="kpi-row"),

        # ── Purchase Recommendations ──
        section("Purchase Recommendations",
                "Ranked by combined opportunity score (external trends + internal demand signals)."),
        explainer([
            html.Strong("Scoring: "),
            "Items are scored 0–1 by combining Reddit demand signals, Weidian/1688 live sales "
            "velocity, and internal community data. ",
            html.Strong("BUY NOW"), " (0.85+) = top priority. ",
            html.Strong("STRONG BUY"), " (0.70+) = stock immediately. ",
            html.Strong("BUY"), " (0.55+) = solid opportunity. ",
            html.Strong("WATCH"), " (0.40+) = monitor.",
        ], "green"),
        chart_card("Top 20 Purchase Opportunities — Ranked by Score",
                   "Green = high opportunity. Red = lower priority. Hover for details.",
                   dcc.Graph(
                       figure=style_fig(recs_fig),
                       config={"displayModeBar": False},
                       style={"height": "520px"},
                   )),
        make_table(recs_df.head(30), {
            "brand": "Brand", "item": "Item", "category": "Category",
            "combined_score": "Score", "demand_level": "Demand",
            "best_batch": "Best Batch", "price_range": "Price",
            "recommendation": "Action",
        }),

        # ── Live Sales Data ──
        section("Live Sales Data — What People Are Actually Buying",
                "Agent-tracked purchases from Weidian and 1688 over the last 30 days."),
        explainer([
            html.Strong("Why this matters: "),
            "Reddit shows what people ", html.Strong("want"), ". Weidian/1688 sales show what people ",
            html.Strong("actually buy"), ". Items trending in both = highest confidence picks.",
        ], "amber"),
        html.Div([
            chart_card("Weidian Top Sellers (30 Days)",
                       "Green = rising trend. Blue = stable. Amber = cooling.",
                       dcc.Graph(
                           figure=style_fig(weidian_fig),
                           config={"displayModeBar": False},
                           style={"height": "580px"},
                       )),
            chart_card("1688 Top Sellers (30 Days)",
                       "Bulk/budget segment. Green = rising. Blue = stable.",
                       dcc.Graph(
                           figure=style_fig(fig_1688),
                           config={"displayModeBar": False},
                           style={"height": "580px"},
                       )),
        ], className="two-col"),

        # ── Platform comparison ──
        chart_card("Cross-Platform Top Sellers — Weidian vs 1688",
                   "Purple = Weidian. Cyan = 1688. Items appearing on both platforms = strong signal.",
                   dcc.Graph(
                       figure=style_fig(plat_comp_fig),
                       config={"displayModeBar": False},
                       style={"height": "520px"},
                   )),

        # ── Demand Heatmap & Category Breakdown ──
        section("Market Demand Analysis",
                "How demand distributes across brands and product categories."),
        html.Div([
            chart_card("Brand × Category Demand Heatmap",
                       "Brighter = higher demand. Use this to spot undersaturated brand-category combos.",
                       dcc.Graph(
                           figure=style_fig(heatmap_fig),
                           config={"displayModeBar": False},
                           style={"height": "450px"},
                       )),
            chart_card("Demand by Category",
                       "Which product categories drive the most interest.",
                       dcc.Graph(
                           figure=style_fig(cat_fig),
                           config={"displayModeBar": False},
                       )),
        ], className="two-col"),

        # ── Trend Direction & Subreddit Reach ──
        html.Div([
            chart_card("Trend Direction (Weidian + 1688)",
                       "Overall market momentum across tracked items.",
                       dcc.Graph(
                           figure=style_fig(trend_fig),
                           config={"displayModeBar": False},
                       )),
            chart_card("Subreddit Reach & Signal Weight",
                       "Larger communities with higher weights = strongest demand signals.",
                       dcc.Graph(
                           figure=style_fig(subs_fig),
                           config={"displayModeBar": False},
                           style={"height": "450px"},
                       )),
        ], className="two-col"),

        # ── Reddit Trending Items Table ──
        section("Reddit Community Trending Items",
                "Aggregated from 9+ subreddits with 4.5M+ combined members."),
        explainer([
            html.Strong("Data sources: "),
            "r/FashionReps (2.2M), r/Repsneakers (969K), r/RepTime (600K), "
            "r/DesignerReps (450K), r/DHgate (350K), r/QualityReps (320K), "
            "r/RepLadies (250K), r/RepBudgetSneakers (229K), r/FashionRepsBST (180K), "
            "r/ChinaTime (180K), r/CloseToRetail, r/WeidianWarriors, r/1688Reps, "
            "r/DecorReps, and more.",
        ], "purple"),
        make_table(ext_trending, {
            "brand": "Brand", "item": "Item", "category": "Category",
            "demand": "Demand Level", "best_batch": "Best Batch",
            "price_range": "Price Range", "subreddits": "Active Subreddits",
            "signal": "Signal Type",
        }, page_size=15),

        # ── Subreddit Intelligence ──
        section("Subreddit Intelligence",
                "Community breakdown showing focus areas and top brands per subreddit."),
        make_table(subs_df, {
            "subreddit": "Subreddit", "members": "Members",
            "signal_weight": "Signal Weight", "focus": "Focus Area",
            "top_brands": "Top Brands Discussed",
        }),

        # ── Batch Quality Guide ──
        section("Batch Quality Guide",
                "Community-consensus best batches for the most popular sneaker models."),
        explainer([
            html.Strong("How to read: "),
            "Each shoe model has a recommended 'best batch' (factory run). ",
            html.Strong("LJR"), " = top for Jordans. ",
            html.Strong("PK"), " = top for J4s/Yeezys. ",
            html.Strong("M Batch"), " = best value Dunks. ",
            html.Strong("OG"), " = best for Off-White collabs.",
        ], "green"),
        make_table(batch_df, {
            "shoe": "Shoe Model", "best_batch": "Best Batch",
            "alt_batch": "Alternative", "tier": "Tier",
            "notes": "Community Notes",
        }),

        # ── Watch Factory Guide ──
        section("Watch Factory Guide",
                "Community-consensus best factories for the most popular watch models."),
        explainer([
            html.Strong("How to read: "),
            "Each watch model has a recommended 'best factory'. ",
            html.Strong("Clean / VS"), " = top for Rolex. ",
            html.Strong("ZF"), " = top for AP Royal Oak & Omega Speedmaster. ",
            html.Strong("VS"), " = dominates Omega Seamaster. ",
            html.Strong("GF / BV"), " = best for Cartier Santos.",
        ], "amber"),
        make_table(watch_df, {
            "watch": "Watch Model", "best_factory": "Best Factory",
            "alt_factory": "Alternative", "tier": "Tier",
            "notes": "Community Notes",
        }),

        # ── Upcoming Releases ──
        section("Upcoming Releases — Future Demand Drivers",
                "Retail releases across sneakers, watches, jewelry, and more that drive demand."),
        explainer([
            html.Strong("Strategy tip: "),
            "Pre-stock items before their retail release date. "
            "Demand for reps spikes 2–4 weeks before and after official drops.",
        ], "red"),
        make_table(releases_df, {
            "item": "Release", "brand": "Brand",
            "release": "Expected Date", "hype": "Hype Level",
            "category": "Category",
        }),

        # ── QC Platform Guide ──
        section("QC & Discovery Platforms",
                "Tools for finding and verifying items before purchase."),
        explainer([
            html.Strong("doppel.fit"), " — QC photo finder and product discovery platform. "
            "Browse thousands of QC photos from popular agents. ",
            html.Br(),
            html.Strong("FinderQC"), " (finderqc.com) — 5,000+ curated products with QC photos, "
            "prices in USD. Spreadsheet updated daily, sold-out items auto-replaced. ",
            html.Br(),
            html.Strong("FindQC"), " (findqc.com) — QC photos and video finder for CNFans, "
            "Kakobuy, and other shopping agents. ",
            html.Br(),
            html.Strong("JadeShip/RepArchive"), " — Live sales tracking across Weidian, 1688, "
            "Taobao with agent purchase data powering the charts above.",
        ]),

    ], className="page-content")


# ── Main layout ───────────────────────────────────────────────────────────

# Load initial data (all time) for first render
_D0 = _load()

app.layout = html.Div([
    html.Div([
        html.Div([
            html.H1("ZR ItemFinder"),
            html.Div("Demand Intelligence for Resellers", className="subtitle"),
        ]),
        html.Div([
            dcc.Dropdown(
                id="platform-selector",
                options=PLATFORM_OPTIONS,
                value="all",
                clearable=False,
                style={"width": "140px", "backgroundColor": "#252836",
                       "color": "#e8eaed", "borderColor": "#2d3044"},
            ),
            dcc.Dropdown(
                id="timeframe-dropdown",
                options=TIMEFRAME_OPTIONS,
                value="all",
                clearable=False,
                style={"width": "140px", "backgroundColor": "#252836",
                       "color": "#e8eaed", "borderColor": "#2d3044"},
            ),
        ], style={"display": "flex", "alignItems": "center", "gap": "12px"}),
        html.Div([
            html.Div([html.Div(id="hdr-platform", children="Discord + Reddit",
                                className="num", style={"fontSize": "0.85rem"}),
                       html.Div("Source", className="lbl")], className="header-stat"),
            html.Div([html.Div(id="hdr-msgs", children=f"{_D0['raw']:,}", className="num"),
                       html.Div("Messages", className="lbl")], className="header-stat"),
            html.Div([html.Div(id="hdr-mentions", children=f"{_D0['mentions']:,}", className="num"),
                       html.Div("Mentions", className="lbl")], className="header-stat"),
            html.Div([html.Div(id="hdr-brands", children=str(len(_D0["brands"])), className="num"),
                       html.Div("Brands", className="lbl")], className="header-stat"),
        ], className="header-stats"),
    ], className="site-header"),

    dcc.Tabs(className="custom-tabs", children=[
        dcc.Tab(label="Overview", children=html.Div(id="overview-content"),
                className="tab", selected_className="tab--selected"),
        dcc.Tab(label="Market Intelligence", children=html.Div(id="market-intel-content"),
                className="tab", selected_className="tab--selected"),
        dcc.Tab(label="What to Stock", children=html.Div(id="stock-content"),
                className="tab", selected_className="tab--selected"),
        dcc.Tab(label="Customer Insights", children=html.Div(id="customers-content"),
                className="tab", selected_className="tab--selected"),
        dcc.Tab(label="Item Explorer", children=html.Div(id="explorer-content"),
                className="tab", selected_className="tab--selected"),
        dcc.Tab(label="Market Trends", children=html.Div(id="trends-content"),
                className="tab", selected_className="tab--selected"),
        dcc.Tab(label="Channel Analysis", children=html.Div(id="channels-content"),
                className="tab", selected_className="tab--selected"),
        dcc.Tab(label="Demand Signals", children=html.Div(id="signals-content"),
                className="tab", selected_className="tab--selected"),
    ]),

    # Hidden store for items data (used by search callback)
    dcc.Store(id="items-store"),

    html.Div([
        html.P("ZR ItemFinder v1.2 — Data from Discord + Reddit + Weidian + 1688 market intelligence",
               style={"color": "var(--text-muted)", "fontSize": "0.75rem",
                       "textAlign": "center", "padding": "20px 0"}),
    ], style={"borderTop": "1px solid var(--border)", "marginTop": "32px"}),
])


# ── Timeframe callback ───────────────────────────────────────────────────

@callback(
    [Output("overview-content", "children"),
     Output("market-intel-content", "children"),
     Output("stock-content", "children"),
     Output("customers-content", "children"),
     Output("explorer-content", "children"),
     Output("trends-content", "children"),
     Output("channels-content", "children"),
     Output("signals-content", "children"),
     Output("hdr-msgs", "children"),
     Output("hdr-mentions", "children"),
     Output("hdr-brands", "children"),
     Output("items-store", "data"),
     Output("hdr-platform", "children")],
    [Input("timeframe-dropdown", "value"),
     Input("platform-selector", "value")],
)
def update_dashboard(days, platform):
    if days and days != "all":
        since = (datetime.now() - timedelta(days=int(days))).isoformat()
    else:
        since = None
    D = _load(since, platform=platform or "all")
    items_df = _df(D, "items")
    return [
        _overview(D),
        _market_intel(D),
        _stock(D),
        _customers(D),
        _explorer(D),
        _trends(D),
        _channels_tab(D),
        _signals(D),
        f"{D['raw']:,}",
        f"{D['mentions']:,}",
        str(len(D["brands"])),
        items_df.to_dict("records") if not items_df.empty else [],
        D["platform_label"],
    ]


# ── Item search callback ─────────────────────────────────────────────────

@callback(
    Output("items-table-container", "children"),
    [Input("item-search", "value"),
     Input("items-store", "data")],
)
def _filter_items(term, items_data):
    if not items_data:
        return html.P("No data.", style={"color": "#6b7280"})
    df = pd.DataFrame(items_data)
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
