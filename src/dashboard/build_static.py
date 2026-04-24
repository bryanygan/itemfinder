"""Build static HTML site for Cloudflare Pages deployment.

Usage: python -m src.dashboard.build_static
Output: dist/index.html, dist/assets/style.css

Deploy: npx wrangler pages deploy dist --project-name=zr-itemfinder
"""

import json
import shutil
from datetime import datetime, timedelta
from html import escape
from pathlib import Path

import pandas as pd
import plotly.express as px

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
from src.process.scoring import compute_brand_scores, compute_item_scores

log = get_logger("build")
ROOT = Path(__file__).resolve().parent.parent.parent
DIST = ROOT / "dist"
ASSETS_SRC = Path(__file__).resolve().parent / "assets"

C = {"blue": "#3b82f6", "green": "#22c55e", "red": "#ef4444",
     "amber": "#f59e0b", "purple": "#8b5cf6", "cyan": "#06b6d4"}
THEME = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, system-ui, sans-serif", color="#9aa0b2", size=12),
    autosize=True,
    height=300,
    margin=dict(t=10, b=60, l=50, r=20),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
    xaxis=dict(gridcolor="#2d3044", zerolinecolor="#2d3044"),
    yaxis=dict(gridcolor="#2d3044", zerolinecolor="#2d3044"),
)

TIMEFRAMES = [
    ("7d", 7),
    ("14d", 14),
    ("30d", 30),
    ("60d", 60),
    ("90d", 90),
    ("all", None),
]


def _load(since: str | None = None):
    conn = get_connection()
    d = dict(
        raw=raw_message_count(conn, since=since),
        mentions=processed_mention_count(conn, since=since),
        items=compute_item_scores(conn, since=since),
        brands=compute_brand_scores(conn, since=since),
        trending=trending_items(conn, 20, since=since),
        channels=channel_breakdown(conn, since=since),
        daily=daily_volume(conn, since=since),
        req=top_items_by_intent(conn, "request", 30, since=since),
        sat=top_items_by_intent(conn, "satisfaction", 30, since=since),
        reg=top_items_by_intent(conn, "regret", 30, since=since),
        own=top_items_by_intent(conn, "ownership", 30, since=since),
        unmet=unmet_demand(conn, 3, since=since),
        profiles=buyer_profiles(conn, 20, since=since),
        cross=brand_cross_sell(conn, 10, since=since),
        sizes=size_demand(conn, since=since),
        colors=color_demand(conn, since=since),
        inv=inventory_recommendations(conn, since=since),
        season=monthly_seasonality(conn, since=since),
        conv=conversion_tracking(conn, since=since),
    )
    rows = conn.execute(
        "SELECT intent_type, COUNT(*) as count FROM processed_mentions "
        + ("WHERE timestamp >= ? " if since else "")
        + "GROUP BY intent_type",
        [since] if since else [],
    ).fetchall()
    d["intent_dist"] = [dict(r) for r in rows]
    conn.close()
    d["n_brands"] = len(d["brands"])
    d["n_items"] = len(d["items"])
    d["n_channels"] = len(d["channels"])
    d["profiles_flat"] = [
        {k: v for k, v in p.items() if k not in ("top_brands", "top_requests")}
        for p in d["profiles"]
    ]
    return d


# ── HTML helpers ──────────────────────────────────────────────────────────

def _kpi(value, label, color="#06b6d4", data_kpi=""):
    fmt = f"{value:,}" if isinstance(value, (int, float)) else escape(str(value))
    dattr = f' data-kpi="{data_kpi}"' if data_kpi else ""
    return (f'<div class="kpi-card"><div class="kpi-value" style="color:{color}"{dattr}>'
            f'{fmt}</div><div class="kpi-label">{escape(label)}</div></div>')


def _exp(html_content, color=""):
    cls = f"explainer {color}" if color else "explainer"
    return f'<div class="{cls}">{html_content}</div>'


def _sec(title, sub=""):
    s = f'<div class="section-sub">{escape(sub)}</div>' if sub else ""
    return f'<div class="section-title">{escape(title)}</div>{s}'


def _act(title, items):
    if not items:
        return ""
    li = "".join(f"<li>{escape(str(i))}</li>" for i in items)
    return f'<div class="action-box"><div class="action-title">{escape(title)}</div><ul>{li}</ul></div>'


def _chart(cid, title, sub=""):
    s = f'<div class="chart-sub">{escape(sub)}</div>' if sub else ""
    return (f'<div class="chart-card"><h3>{escape(title)}</h3>{s}'
            f'<div id="{cid}" class="chart-container"></div></div>')


def _table(rows, col_map, tbody_id="", max_rows=None):
    if not rows:
        return '<p style="color:#6b7280;padding:12px">No data available.</p>'
    cols = list(col_map.keys())
    thead = "".join(f'<th data-sort>{escape(col_map[c])}</th>' for c in cols)
    limit = rows[:max_rows] if max_rows else rows
    trs = []
    for r in limit:
        cells = []
        for c in cols:
            v = r.get(c, "")
            if isinstance(v, float):
                v = f"{v:.2f}"
            cells.append(f"<td>{escape(str(v))}</td>")
        trs.append(f'<tr>{"".join(cells)}</tr>')
    tid = f' id="{tbody_id}"' if tbody_id else ""
    return (f'<div class="table-wrap"><table class="data-table"><thead><tr>{thead}</tr>'
            f'</thead><tbody{tid}>{"".join(trs)}</tbody></table></div>')


# ── Figure builders ───────────────────────────────────────────────────────

def _fig(fig_obj):
    fig_obj.update_layout(**THEME)
    return json.loads(fig_obj.to_json())


def _build_figures(D):
    figs = {}
    bdf = pd.DataFrame(D["brands"]).head(15)
    if not bdf.empty:
        figs["fig-brands"] = _fig(px.bar(
            bdf, x="brand", y="mentions", color="trend_score",
            color_continuous_scale="Viridis",
            labels={"mentions": "Total Mentions", "trend_score": "Trend"}))
    idf = pd.DataFrame(D["intent_dist"])
    if not idf.empty:
        figs["fig-intent"] = _fig(px.pie(
            idf, values="count", names="intent_type",
            color_discrete_sequence=[C["blue"], C["green"], C["red"], C["amber"], "#6b7280"]))
    for key, xcol, data_key in [("fig-sizes", "size", "sizes"), ("fig-colors", "color", "colors")]:
        df = pd.DataFrame(D[data_key]).head(12)
        if not df.empty:
            figs[key] = _fig(px.bar(
                df, x=xcol, y=["requests", "owned"], barmode="group",
                color_discrete_sequence=[C["blue"], C["green"]],
                labels={"value": "Count", "variable": ""}))
    pdf = pd.DataFrame(D["profiles_flat"])
    if not pdf.empty:
        seg = pdf.groupby("segment").size().reset_index(name="count")
        figs["fig-segments"] = _fig(px.pie(
            seg, values="count", names="segment",
            color_discrete_sequence=[C["blue"], C["green"], C["red"], C["amber"], C["purple"]]))
        figs["fig-users"] = _fig(px.bar(
            pdf.head(15), x="user", y=["requests", "owned"], barmode="group",
            color_discrete_sequence=[C["blue"], C["green"]],
            labels={"value": "Count", "variable": ""}))
    ddf = pd.DataFrame(D["daily"])
    if not ddf.empty:
        figs["fig-daily"] = _fig(px.area(
            ddf, x="day", y=["requests", "satisfaction", "regret", "ownership"],
            color_discrete_sequence=[C["blue"], C["green"], C["red"], C["amber"]],
            labels={"value": "Mentions", "variable": "Signal", "day": "Date"}))
    mdf = pd.DataFrame(D["season"])
    if not mdf.empty:
        figs["fig-season"] = _fig(px.line(
            mdf, x="month", y=["total", "requests", "owned"],
            color_discrete_sequence=[C["purple"], C["blue"], C["green"]],
            labels={"value": "Mentions", "variable": "Type", "month": "Month"}))
    chdf = pd.DataFrame(D["channels"]).head(12)
    if not chdf.empty:
        figs["fig-ch-total"] = _fig(px.bar(
            chdf, x="channel", y="total", color="avg_score",
            color_continuous_scale="RdYlGn",
            labels={"total": "Mentions", "avg_score": "Signal Strength"}))
        figs["fig-ch-intent"] = _fig(px.bar(
            chdf.head(10), x="channel",
            y=["requests", "satisfaction", "regret", "ownership"], barmode="stack",
            color_discrete_sequence=[C["blue"], C["green"], C["red"], C["amber"]],
            labels={"value": "Count", "variable": "Signal"}))
    return figs


# ── Table HTML generators (for timeframe switching) ──────────────────────

def _build_tables(D):
    """Build all table HTML strings for this timeframe."""
    tables = {}
    tables["tbl-unmet"] = _table(D["unmet"][:20], {
        "brand": "Brand", "item": "Item", "requests": "People Asking",
        "owned": "People Who Have It", "demand_gap": "Unmet Gap",
        "unique_requesters": "Unique Buyers"})
    tables["tbl-inv"] = _table(D["inv"][:15], {
        "priority": "Priority", "brand": "Brand", "item": "Item",
        "demand_gap": "Demand Gap", "notes": "Why"})
    tables["tbl-profiles"] = _table(D["profiles_flat"][:50], {
        "user": "Username", "segment": "Segment", "requests": "Requests",
        "owned": "Purchased", "satisfied": "Happy Reviews",
        "regrets": "Missed Items", "buy_ratio": "Buy Ratio"})
    tables["tbl-cross"] = _table(D["cross"][:15], {
        "brand_a": "Brand A", "brand_b": "Brand B",
        "shared_users": "Customers in Common"})
    tables["tbl-conv"] = _table(D["conv"][:15], {
        "author": "Customer", "brand": "Brand", "requests": "Times Asked",
        "owned": "Times Bought", "satisfied": "Happy Reviews"})
    tables["tbl-items"] = _table(D["items"], {
        "brand": "Brand", "item": "Item", "variant": "Variant",
        "total_mentions": "Mentions", "request_count": "Requests",
        "satisfaction_count": "Happy", "regret_count": "Regret",
        "velocity": "Velocity", "final_score": "Score"}, tbody_id="items-tbody")
    tables["tbl-trending"] = _table(D["trending"][:20], {
        "brand": "Brand", "item": "Item", "recent_mentions": "This Period",
        "prev_mentions": "Last Period", "velocity": "Velocity"})
    tables["tbl-channels"] = _table(D["channels"], {
        "channel": "Channel", "total": "Total", "requests": "Buy Requests",
        "satisfaction": "Happy", "regret": "Missed Opp.",
        "ownership": "Purchases", "avg_score": "Strength"})
    tables["tbl-req"] = _table(D["req"][:15], {
        "brand": "Brand", "item": "Item", "count": "Requests", "avg_score": "Strength"})
    tables["tbl-sat"] = _table(D["sat"][:15], {
        "brand": "Brand", "item": "Item", "count": "Reviews", "avg_score": "Strength"})
    tables["tbl-reg"] = _table(D["reg"][:15], {
        "brand": "Brand", "item": "Item", "count": "Regret Mentions", "avg_score": "Strength"})
    tables["tbl-own"] = _table(D["own"][:15], {
        "brand": "Brand", "item": "Item", "count": "Purchases", "avg_score": "Strength"})
    return tables


def _build_kpis(D):
    return {
        "msgs": f"{D['raw']:,}",
        "mentions": f"{D['mentions']:,}",
        "brands": str(D["n_brands"]),
        "items": str(D["n_items"]),
        "channels": str(D["n_channels"]),
    }


def _build_actions(D):
    actions = []
    if D["unmet"]:
        t = D["unmet"][0]
        actions.append(f"Stock {t['brand']} {t['item']} -- {t['demand_gap']} people want it but cannot find it")
    if D["sizes"]:
        actions.append(f"Focus on sizes {', '.join(s['size'] for s in D['sizes'][:3])} -- most requested")
    if D["cross"]:
        c = D["cross"][0]
        actions.append(f"Bundle {c['brand_a']} + {c['brand_b']} -- {c['shared_users']} customers want both")
    return actions


# ── Tab content (uses data-tf-table containers for swapping) ─────────────

def _tab_overview(D):
    actions = _build_actions(D)
    p = ['<div class="page-content">']
    p.append(_exp(
        "<strong>Welcome to your Demand Intelligence Dashboard.</strong> "
        "This tool analyzes thousands of Discord + Reddit messages to find "
        "<strong>what people want to buy</strong>, "
        "<strong>what is trending</strong>, and "
        "<strong>where the biggest sales opportunities are</strong>. "
        "Every number comes from real conversations in your Discord servers and Reddit communities."))
    p.append('<div class="kpi-row">')
    p.append(_kpi(D["raw"], "Messages Scanned", C["cyan"], "msgs"))
    p.append(_kpi(D["mentions"], "Product Mentions", C["green"], "mentions"))
    p.append(_kpi(D["n_brands"], "Brands Detected", C["amber"], "brands"))
    p.append(_kpi(D["n_items"], "Item Combinations", C["red"], "items"))
    p.append(_kpi(D["n_channels"], "Channels Analyzed", C["purple"], "channels"))
    p.append("</div>")
    p.append(_exp(
        "<strong>Messages Scanned:</strong> Total Discord + Reddit messages processed. "
        "<strong>Product Mentions:</strong> Messages about a specific brand or item. "
        "<strong>Brands:</strong> Unique brands mentioned. "
        '<strong>Item Combinations:</strong> Unique brand + item pairs (e.g. "Balenciaga hoodie"). '
        "<strong>Channels:</strong> Channels / subreddits with product discussion.", "green"))
    p.append('<div class="two-col">')
    p.append(_chart("fig-brands", "Top 15 Brands by Mentions",
                     "Taller bars = more popular. Color shows trend momentum."))
    p.append(_chart("fig-intent", "What People Are Saying (Intent Breakdown)",
                     "Shows the mix of buying signals across your community."))
    p.append("</div>")
    p.append(_exp(
        "<strong>Intent types:</strong> "
        "<strong>Request</strong> = looking to buy. "
        "<strong>Ownership</strong> = just bought it. "
        "<strong>Satisfaction</strong> = positive review. "
        "<strong>Regret</strong> = missed opportunity. "
        "<strong>Neutral</strong> = mentioned without clear buying intent.", "purple"))
    p.append(f'<div id="act-overview">{_act("Top Actions Based on Your Data", actions)}</div>')
    p.append("</div>")
    return "\n".join(p)


def _tab_stock(D):
    p = ['<div class="page-content">']
    p.append(_exp(
        "<strong>Unmet Demand = Sales Opportunity.</strong> "
        "These items are <strong>actively requested</strong> but "
        "<strong>almost nobody has them yet</strong>. "
        "The bigger the gap between People Asking and People Who Have It, "
        "the bigger your opportunity.", "red"))
    p.append(_sec("Unmet Demand -- Items People Want but Cannot Get",
                   "Sorted by demand gap. Higher gap = bigger opportunity."))
    p.append('<div id="wrap-tbl-unmet">')
    p.append(_table(D["unmet"][:20], {
        "brand": "Brand", "item": "Item", "requests": "People Asking",
        "owned": "People Who Have It", "demand_gap": "Unmet Gap",
        "unique_requesters": "Unique Buyers"}))
    p.append('</div>')
    p.append(_sec("Inventory Recommendations",
                   "AI-prioritized stocking suggestions based on all demand signals."))
    p.append(_exp(
        "<strong>Priority levels:</strong> "
        "<strong>HIGH</strong> = 10+ unmet requests, stock immediately. "
        "<strong>MEDIUM</strong> = 5-9 unmet, strong opportunity. "
        "<strong>LOW</strong> = 2-4 unmet, worth watching.", "amber"))
    p.append('<div id="wrap-tbl-inv">')
    p.append(_table(D["inv"][:15], {
        "priority": "Priority", "brand": "Brand", "item": "Item",
        "demand_gap": "Demand Gap", "notes": "Why"}))
    p.append('</div>')
    p.append('<div class="two-col">')
    p.append(_chart("fig-sizes", "Most Requested Sizes",
                     "Blue = people asking. Green = people who own it."))
    p.append(_chart("fig-colors", "Most Requested Colors",
                     "Blue = people asking. Green = people who own it."))
    p.append("</div>")
    p.append(_exp(
        "<strong>Size &amp; Color Tip:</strong> "
        "When the blue bar (requests) is much taller than green (owned), "
        "people want it but cannot find it. Prioritize those variants.", "green"))
    p.append("</div>")
    return "\n".join(p)


def _tab_customers(D):
    p = ['<div class="page-content">']
    p.append(_exp(
        "<strong>Know your customers.</strong> "
        "We analyze each user's activity to understand buying behavior. "
        "<strong>Loyal Buyers</strong> buy often. "
        "<strong>High-Intent Prospects</strong> ask for a lot but buy little (untapped opportunity). "
        "<strong>Active Buyers</strong> moderate buying. "
        "<strong>Browsers</strong> window shopping. "
        "<strong>Casual</strong> light activity."))
    p.append('<div class="two-col">')
    p.append(_chart("fig-segments", "Customer Segments",
                     "How your community breaks down by buying behavior."))
    p.append(_chart("fig-users", "Top Users by Activity",
                     "Blue = items requested. Green = items bought."))
    p.append("</div>")
    p.append(_sec("Customer Profiles"))
    p.append(_exp(
        "<strong>Buy Ratio</strong> = what % of requests turned into purchases. "
        "0.50 means half their asks led to buying. "
        "Low ratio + high requests = target with offers.", "amber"))
    p.append('<div id="wrap-tbl-profiles">')
    p.append(_table(D["profiles_flat"][:50], {
        "user": "Username", "segment": "Segment", "requests": "Requests",
        "owned": "Purchased", "satisfied": "Happy Reviews",
        "regrets": "Missed Items", "buy_ratio": "Buy Ratio"}))
    p.append('</div>')
    p.append(_sec("Cross-Sell Opportunities",
                   "Brands the same customers discuss -- bundle these for higher sales."))
    p.append(_exp(
        "<strong>Cross-sell:</strong> "
        "If someone likes Brand A, they likely want Brand B too. "
        "Use this to create bundles or plan inventory together.", "purple"))
    p.append('<div id="wrap-tbl-cross">')
    p.append(_table(D["cross"][:15], {
        "brand_a": "Brand A", "brand_b": "Brand B",
        "shared_users": "Customers in Common"}))
    p.append('</div>')
    p.append(_sec("Conversions (Request to Purchase)",
                   "People who asked about a brand AND later bought it."))
    p.append(_exp(
        "High conversion brands are safer to stock heavily -- proven demand.", "green"))
    p.append('<div id="wrap-tbl-conv">')
    p.append(_table(D["conv"][:15], {
        "author": "Customer", "brand": "Brand", "requests": "Times Asked",
        "owned": "Times Bought", "satisfied": "Happy Reviews"}))
    p.append('</div>')
    p.append("</div>")
    return "\n".join(p)


def _tab_explorer(D):
    p = ['<div class="page-content">']
    p.append(_exp(
        "<strong>Search and explore all detected items.</strong> "
        "Type a brand or item name to filter. Click column headers to sort. "
        "<strong>Score</strong> combines popularity (20%), buying intent strength (50%), "
        "and trend momentum (30%) -- higher = more valuable to stock. "
        "<strong>Velocity</strong> shows trend direction: positive = rising, negative = cooling."))
    p.append('<div class="search-input" style="margin-bottom:16px">'
             '<input id="item-search" type="text" '
             'placeholder="Type a brand or item name to filter..."></div>')
    p.append('<div id="wrap-tbl-items">')
    p.append(_table(D["items"], {
        "brand": "Brand", "item": "Item", "variant": "Variant",
        "total_mentions": "Mentions", "request_count": "Requests",
        "satisfaction_count": "Happy", "regret_count": "Regret",
        "velocity": "Velocity", "final_score": "Score"}, tbody_id="items-tbody"))
    p.append('</div>')
    p.append("</div>")
    return "\n".join(p)


def _tab_trends(D):
    p = ['<div class="page-content">']
    p.append(_exp(
        "<strong>Track how demand changes over time.</strong> "
        "Spikes often correspond to new drops, restocks, or community hype events. "
        "The trending table shows what is gaining momentum <strong>right now</strong>."))
    p.append(_chart("fig-daily", "Daily Activity by Intent Type",
                     "Each color = a different signal. Spikes = high activity days."))
    p.append(_sec("Fastest Rising Items",
                   "Biggest increase in mentions this period vs. previous period."))
    p.append(_exp(
        "<strong>Velocity</strong> measures momentum. "
        "<strong>+2.0x</strong> means 3x more mentions than last period. "
        "High velocity + high requests = about to blow up.", "amber"))
    p.append('<div id="wrap-tbl-trending">')
    p.append(_table(D["trending"][:20], {
        "brand": "Brand", "item": "Item", "recent_mentions": "This Period",
        "prev_mentions": "Last Period", "velocity": "Velocity"}))
    p.append('</div>')
    p.append(_chart("fig-season", "Monthly Activity Patterns",
                     "Seasonal trends -- use this to plan inventory for busy months."))
    p.append("</div>")
    return "\n".join(p)


def _tab_channels(D):
    p = ['<div class="page-content">']
    p.append(_exp(
        "<strong>Not all channels are equal.</strong> "
        "WTB (Want to Buy) channels give the strongest buying signals. "
        "Pickups show actual purchases. General chat has more noise. "
        "Use this to understand <strong>where</strong> signals come from."))
    p.append('<div class="two-col">')
    p.append(_chart("fig-ch-total", "Mentions by Channel",
                     "Which channels produce the most product discussion."))
    p.append(_chart("fig-ch-intent", "Intent Mix per Channel",
                     "What type of messages each channel produces."))
    p.append("</div>")
    p.append(_exp(
        "<strong>Signal Strength (color):</strong> "
        "Green = high-quality buying signals (WTB, pickups). "
        "Yellow/red = lower intent (general chat). "
        "Prioritize green channels for stocking decisions.", "green"))
    p.append(_sec("Full Channel Data"))
    p.append('<div id="wrap-tbl-channels">')
    p.append(_table(D["channels"], {
        "channel": "Channel", "total": "Total", "requests": "Buy Requests",
        "satisfaction": "Happy", "regret": "Missed Opp.",
        "ownership": "Purchases", "avg_score": "Strength"}))
    p.append('</div>')
    p.append("</div>")
    return "\n".join(p)


def _tab_market_report(_D):
    """Static market intelligence report — March 2026."""
    bc, gc, rc, ac, pc = C["blue"], C["green"], C["red"], C["amber"], C["purple"]
    p = ['<div class="page-content">']
    p.append(_exp(
        "<strong>Live Market Intelligence Report — March 2026.</strong> "
        "Compiled from 4 research swarms across 21 subreddits including r/FashionReps, "
        "r/Repsneakers, r/DesignerReps, r/DHgate, r/QualityReps, r/weidianwarriors, and more. "
        "This report surfaces what is trending <strong>right now</strong> across the entire rep community — "
        "cross-referenced against your dashboard data to highlight gaps and opportunities."))

    # ── Key Dates callout ──────────────────────────────────────────────────
    p.append(_sec("Upcoming Release Calendar", "Stock reps ahead of these retail drops — W2C demand peaks at release."))
    p.append(f'<div class="action-box"><div class="action-title">Key Dates to Calendar</div><ul>'
             f'<li><strong>March 28, 2026</strong> — Virgil Abloh Archive x AJ1 High "Alaska" retail (~20k pairs). Rep demand peaks same week.</li>'
             f'<li><strong>May 22, 2026</strong> — Travis Scott x Jordan 1 Low Pink Pack retail. Source reps April–early May.</li>'
             f'<li><strong>Black Friday 2026</strong> — AJ4 OG "Bred" with OG Nike Air heel branding. Source reps September–October.</li>'
             f'<li><strong>December 12, 2026</strong> — AJ11 "Space Jam" + limited Galaxy variant. Source reps October–November.</li>'
             f'</ul></div>')

    # ── Sneakers Tier 1 ───────────────────────────────────────────────────
    p.append(_sec("Sneakers — Tier 1: Extreme Demand (Stock Now)"))
    p.append(_exp(f'<strong style="color:{rc}">These are the highest-priority items across all communities. '
                  f'Pre-release drops are already generating W2C posts.</strong>'))
    p.append('<div class="table-wrap"><table class="data-table"><thead><tr>'
             '<th data-sort>#</th><th data-sort>Item</th><th data-sort>Best Batch</th>'
             '<th data-sort>Rep Price</th><th>Key Signal</th></tr></thead><tbody>'
             '<tr><td>1</td><td><strong>Air Jordan 1 High — Chicago / Royal / Shadow</strong></td><td>LJR</td><td>$130–$160</td><td>All-time #1 W2C sneaker. Evergreen.</td></tr>'
             '<tr><td>2</td><td><strong>Air Jordan 4 — Thunder / Military Black / White Oreo</strong></td><td>PK</td><td>$120–$155</td><td>Most realistic silhouette to replicate. Thunder is #1 Jordan 4 colorway right now.</td></tr>'
             '<tr><td>3</td><td><strong>Travis Scott x Jordan 1 Low — Pink Pack</strong></td><td>LJR/PK</td><td>$140–$170</td><td>Retail May 22 — W2C requests already building. Stock ahead of drop.</td></tr>'
             '<tr><td>4</td><td><strong>Virgil Abloh Archive x AJ1 High "Alaska"</strong></td><td>LJR</td><td>$180–$250</td><td>Retail March 28, ~20k pairs globally. Most hyped sneaker of 2026.</td></tr>'
             '<tr><td>5</td><td><strong>Air Jordan 4 OG "Bred" (OG Nike Air heel)</strong></td><td>PK</td><td>$130–$155</td><td>Black Friday 2026 retail drop. Start sourcing Q2.</td></tr>'
             '</tbody></table></div>')

    # ── Sneakers Tier 2 ───────────────────────────────────────────────────
    p.append(_sec("Sneakers — Tier 2: High Demand (Core Inventory)"))
    p.append('<div class="table-wrap"><table class="data-table"><thead><tr>'
             '<th data-sort>#</th><th data-sort>Item</th><th data-sort>Best Batch</th>'
             '<th data-sort>Rep Price</th><th>Key Signal</th></tr></thead><tbody>'
             '<tr><td>6</td><td><strong>Nike Dunk Low "Panda"</strong></td><td>H12/OG</td><td>$80–$110</td><td>Evergreen — still #1 Dunk colorway 5 years running.</td></tr>'
             '<tr><td>7</td><td><strong>Adidas Samba OG / Collab Versions</strong></td><td>—</td><td>$40–$80</td><td>Search trend index hit 100 in Nov 2025. Wales Bonner / Sporty &amp; Rich drive most W2C.</td></tr>'
             '<tr><td>8</td><td><strong>Yeezy Boost 350 V2 — Zebra / Beluga / Static Black Reflective</strong></td><td>PK/GD</td><td>$100–$140</td><td>Demand stable post-Ye split. Zebra and Beluga are evergreen staples.</td></tr>'
             '<tr><td>9</td><td><strong>Nike Air Force 1 Low — Triple White / NOCTA</strong></td><td>PK/LJR</td><td>$75–$140</td><td>Most replicated Nike silhouette overall.</td></tr>'
             '<tr><td>10</td><td><strong>Air Jordan 11 "Space Jam"</strong></td><td>H12/OWF</td><td>$140–$175</td><td>Dec 12 retail + limited Galaxy variant = collector-level W2C demand.</td></tr>'
             '<tr><td>11</td><td><strong>New Balance 9060 — Sea Salt / Grey / No Sew 2026</strong></td><td>Emerging</td><td>$90–$125</td><td>Gen Z sneaker of 2026. Chunky tech runner trend is sustained.</td></tr>'
             '<tr><td>12</td><td><strong>New Balance 550 — White/Green, White/Navy</strong></td><td>Emerging</td><td>$85–$115</td><td>ALD cultural cachet still driving strong demand.</td></tr>'
             f'<tr><td>13</td><td><strong style="color:{gc}">ASICS Gel-Kayano 14 — JJJJound collabs / metallic</strong></td><td>Emerging</td><td>$80–$115</td><td><strong>Fastest-growing silhouette right now.</strong> Gorpcore + JJJJound credibility.</td></tr>'
             '<tr><td>14</td><td><strong>Balenciaga Triple S</strong></td><td>—</td><td>$60–$100</td><td>Saves $800+ vs. retail. Perennial top seller.</td></tr>'
             '<tr><td>15</td><td><strong>Travis Scott AJ1 Low — Mocha / Olive (prior releases)</strong></td><td>LJR/PK</td><td>$140–$175</td><td>Evergreen. Reverse swoosh accuracy is the #1 QC checkpoint.</td></tr>'
             '</tbody></table></div>')

    # ── Weidian Live Sales ─────────────────────────────────────────────────
    p.append(_sec("Weidian Live Sales Data", "Verified transaction volume from JadeShip — highest-confidence numbers in this report."))
    p.append(_exp(f'These items have <strong>confirmed purchase volume</strong>, not just discussion — real sales tracked across 24+ buying agents.', "green"))
    p.append('<div class="table-wrap"><table class="data-table"><thead><tr>'
             '<th>Item</th><th data-sort>Sales Signal</th></tr></thead><tbody>'
             '<tr><td><strong>NB P-6000 / LINK1 batch</strong></td><td>#1 on 3-month chart — 1,166 verified sales</td></tr>'
             '<tr><td><strong>Nike Air Max 95 style (REAL GX batch)</strong></td><td>#2 on 3-month chart — 863 verified sales</td></tr>'
             '<tr><td><strong>NB GATS "German Trainer" (Maggie Margiel batch)</strong></td><td>Appears on 7-day, 30-day AND 3-month charts — most consistent multi-timeframe performer</td></tr>'
             '<tr><td><strong>DC Series skate-style</strong></td><td>846 sales over 3 months — steady consistent performer</td></tr>'
             '</tbody></table></div>')

    # ── Apparel ────────────────────────────────────────────────────────────
    p.append(_sec("Apparel — Top 10"))
    p.append('<div class="table-wrap"><table class="data-table"><thead><tr>'
             '<th data-sort>#</th><th data-sort>Item</th><th data-sort>Rep Price</th><th>Demand Signal</th></tr></thead><tbody>'
             '<tr><td>1</td><td><strong>Fear of God Essentials Hoodie</strong></td><td>$20–$60</td><td>#1 most repped streetwear piece. Appears in every community.</td></tr>'
             '<tr><td>2</td><td><strong>Fear of God Essentials Sweatpants</strong></td><td>$25–$45</td><td>High bundle demand with the hoodie.</td></tr>'
             '<tr><td>3</td><td><strong>Supreme Box Logo Hoodie / Tee</strong></td><td>$15–$60</td><td>All-time staple. Tee as low as $15 on Kakobuy.</td></tr>'
             f'<tr><td>4</td><td><strong style="color:{gc}">BAPE Shark Hoodie</strong></td><td>$18–$50</td><td><strong>Comeback confirmed.</strong> Going viral in 2025–2026. Reps near-indistinguishable from retail.</td></tr>'
             '<tr><td>5</td><td><strong>Carhartt WIP Jacket / Beanie / Accessories</strong></td><td>$25–$60</td><td>Highest margin-to-risk ratio item on this list. Beanie especially.</td></tr>'
             '<tr><td>6</td><td><strong>Stone Island Patch Hoodie / Sweatshirt</strong></td><td>$35–$60</td><td>AW25 colorways in demand. Compass badge placement is key QC check.</td></tr>'
             '<tr><td>7</td><td><strong>Cargo Pants</strong> (Carhartt-style / Balenciaga / unbranded)</td><td>$25–$65</td><td>Cross-community trend. Appears in every subreddit cluster.</td></tr>'
             '<tr><td>8</td><td><strong>Moncler Maya Down Jacket</strong></td><td>$100–$200</td><td>Winter 2025–2026 peak. Down fill and arm badge stitching are QC priorities.</td></tr>'
             '<tr><td>9</td><td><strong>Arc\'teryx Beta AR / Alpha SV Jacket</strong></td><td>$100–$200</td><td>Gorpcore trend is sustained. GORE-TEX claims heavily discussed in communities.</td></tr>'
             f'<tr><td>10</td><td><strong>Oversized basics</strong> (blank hoodies, heavy tees, fleece sweats)</td><td>$20–$40</td><td>Weidian\'s <strong>highest price-to-quality category</strong>. Extended sizing 2XL–4XL is underserved.</td></tr>'
             '</tbody></table></div>')

    # ── Bags & Accessories ─────────────────────────────────────────────────
    p.append(_sec("Bags &amp; Accessories — Top 10"))
    p.append(_exp(f'Retail price inflation of <strong>25–60%</strong> on luxury bags is a structural tailwind for rep demand — '
                  f'not a cycle. Women\'s bag demand is <strong>growing fastest</strong>.', "purple"))
    p.append('<div class="table-wrap"><table class="data-table"><thead><tr>'
             '<th data-sort>#</th><th data-sort>Item</th><th data-sort>Rep Price</th><th>Demand Signal</th></tr></thead><tbody>'
             '<tr><td>1</td><td><strong>Chanel Classic Flap Bag</strong> (medium / jumbo)</td><td>$200–$600</td><td>#1 most repped bag in the world. Retail hikes are a structural demand tailwind.</td></tr>'
             '<tr><td>2</td><td><strong>Hermès Birkin / Kelly</strong></td><td>$300–$800</td><td>Kelly surpassed Birkin on TikTok in 2025. Retail quota system = reps are the only route.</td></tr>'
             '<tr><td>3</td><td><strong>Louis Vuitton Neverfull / Speedy</strong></td><td>$150–$400</td><td>LV Neverfull holds 100%+ resale value — fuels rep demand.</td></tr>'
             '<tr><td>4</td><td><strong>Bottega Veneta Padded Cassette / Jodie</strong></td><td>$200–$500</td><td>Daniel Lee-era designs remain most wanted. Jing factory specializes in BV weave.</td></tr>'
             '<tr><td>5</td><td><strong>Maison Margiela Tabi</strong> (boots + low sneakers)</td><td>$50–$90</td><td>High demand especially in women\'s sizes. Weidian showing consistent volume.</td></tr>'
             f'<tr><td>6</td><td><strong style="color:{gc}">Loro Piana Summer Walk Loafer</strong></td><td>$80–$150</td><td><strong>Surging.</strong> TikTok searches skyrocketing. Quiet luxury consumer. Retail $900+.</td></tr>'
             '<tr><td>7</td><td><strong>Van Cleef Alhambra Necklace</strong> (4-motif)</td><td>$15–$40</td><td>RepLadies-adjacent demand growing. High volume at low price = strong sell-through.</td></tr>'
             '<tr><td>8</td><td><strong>Rolex Submariner / Datejust</strong></td><td>$100–$200+</td><td>CSSBuy watch community is active. Movement grade (NH35 vs. clone) drives buying decisions.</td></tr>'
             '<tr><td>9</td><td><strong>Cuban chains / hip-hop jewelry</strong></td><td>Under $30</td><td>Carrie Jewelry seller: 41k+ transactions at 99.1% rating on DHgate.</td></tr>'
             '<tr><td>10</td><td><strong>Maison Margiela MM6 Numeric Hoodie</strong></td><td>$30–$50</td><td>Trending heavily on Mulebuy haul aggregations. Clean embroidery noted as strong.</td></tr>'
             '</tbody></table></div>')

    # ── Macro Trends ───────────────────────────────────────────────────────
    p.append(_sec("6 Macro Trends to Act On"))
    p.append(f'<div class="action-box"><div class="action-title" style="color:{ac}">1. Pre-release sourcing is your competitive advantage</div>'
             f'<p style="font-size:0.85rem;color:var(--text-secondary);margin:4px 0 0">Travis Scott Pink Pack (May), AJ4 Bred (Black Friday), AJ11 Space Jam (Dec 12) all have confirmed drops. W2C posts build months before retail — stock reps ahead of these windows.</p></div>')
    p.append(f'<div class="action-box"><div class="action-title" style="color:{bc}">2. 2026 tariffs are sending mainstream buyers your way</div>'
             f'<p style="font-size:0.85rem;color:var(--text-secondary);margin:4px 0 0">US import tariffs have pushed first-time buyers onto DHgate and rep communities. Lululemon leggings dupes and designer bags are the entry point for this new audience.</p></div>')
    p.append(f'<div class="action-box"><div class="action-title" style="color:{gc}">3. New Balance / ASICS are absorbing post-Samba demand</div>'
             f'<p style="font-size:0.85rem;color:var(--text-secondary);margin:4px 0 0">As Samba saturates, NB 9060, NB 550, NB 1906R, and ASICS GEL-Kayano 14 are absorbing the next wave. Batch quality is maturing fast — get ahead of it now.</p></div>')
    p.append(f'<div class="action-box"><div class="action-title" style="color:{pc}">4. Women\'s / RepLadies demand is a structural growth segment</div>'
             f'<p style="font-size:0.85rem;color:var(--text-secondary);margin:4px 0 0">Chanel, Hermès, LV bags, Margiela Tabi, Van Cleef jewelry, and Bottega bags are all surging on AllChinaBuy and Mulebuy. This is not a cycle.</p></div>')
    p.append(f'<div class="action-box"><div class="action-title" style="color:{gc}">5. Chinese domestic brands are the sleeper opportunity</div>'
             f'<p style="font-size:0.85rem;color:var(--text-secondary);margin:4px 0 0">Li-Ning "China Exclusive" colorways, ANTA Klay Thompson line, Xtep 160X running shoes — authentic Chinese domestic products unavailable in Western retail. No rep stigma, genuine product, unique colorways. $25–$55 through agents.</p></div>')
    p.append(f'<div class="action-box"><div class="action-title" style="color:{ac}">6. Extended sizing (2XL–4XL) is a market gap</div>'
             f'<p style="font-size:0.85rem;color:var(--text-secondary);margin:4px 0 0">r/BigBoiRepFashion signals that plus-size rep fashion is heavily underserved. Oversized hoodies, cargo pants, and BAPE Shark Hoodies in extended sizes are requested without adequate supply.</p></div>')

    # ── Dashboard alignment ────────────────────────────────────────────────
    p.append(_sec("Your Dashboard vs. This Report — Alignment Check"))
    p.append(_exp(
        "<strong>What your data already caught correctly:</strong> "
        "Various shoes gap (202) = Jordan 1s &amp; Dunks confirmed. "
        "Balenciaga gap (147) = Triple S confirmed top-10. "
        "Hoodie gap (140) = Essentials, BAPE, Supreme all confirmed. "
        "Yeezy gap (71) = Zebra/Beluga confirmed high-demand. "
        "Watch gap (141) = Rolex confirmed on CSSBuy.", "green"))
    p.append(_exp(
        "<strong>Items your dashboard is potentially underweighting:</strong> "
        "ASICS Gel-Kayano 14 (fastest growing — not in your top unmet list yet). "
        "Loro Piana loafers (quiet luxury surge — underrepresented in your subreddits). "
        "Li-Ning / ANTA domestic brands (new category entirely). "
        "Extended sizing demand (BigBoi segment).", "amber"))

    p.append(f'<p style="font-size:0.72rem;color:var(--text-muted);margin-top:24px">'
             f'Report generated March 13, 2026. Sources: r/FashionReps, r/DesignerReps, r/QualityReps, r/LuxuryReps, '
             f'r/Repsneakers, r/sneakerreps, r/repbudgetsneakers, r/DHgate, r/BudgetBatch, r/weidianwarriors, '
             f'r/CloseToRetail, r/BigBoiRepFashion, r/Sugargoo, r/Superbuy, r/cssbuy, r/MulebuyCommunity, r/AllChinabuy '
             f'+ JadeShip live Weidian sales data + community spreadsheet aggregators.</p>')
    p.append("</div>")
    return "\n".join(p)


def _tab_bst(_D):
    """BST resale pricing vs sourcing cost — ROI intelligence."""
    bc, gc, rc, ac, pc, cc = C["blue"], C["green"], C["red"], C["amber"], C["purple"], C["cyan"]
    p = ['<div class="page-content">']
    p.append(_exp(
        "<strong>BST Resale ROI Intelligence &mdash; April 24, 2026.</strong> "
        "Observed <strong>WTS SOLD</strong> price ranges from r/FashionRepsBST, r/Repsneakers, r/DesignerRepsBST, "
        "r/CloseToRetail, r/QualityRepsBST, r/sneakerreps, r/RepLadiesBST &mdash; mapped against realistic "
        "agent-landed sourcing costs (item + QC + allocated shipping) so you can see "
        "<strong>margin $, ROI%, and whether the top-tier batch is worth it</strong> before you buy. "
        "Red flags (saturation, QC risk, seasonality) called out per-row."))

    # ── ROI Calculator ────────────────────────────────────────────────────
    p.append(_sec("Quick ROI Filter", "Adjust your minimum ROI% &mdash; rows below repaint live."))
    p.append(
        '<div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap;margin:12px 0 16px;'
        'padding:12px 16px;background:var(--bg-surface);border:1px solid var(--border);border-radius:12px">'
        '<label style="font-size:0.85rem;color:var(--text-secondary)">Min ROI % '
        '<input id="roi-min" type="number" value="0" min="0" max="200" step="5" '
        'style="width:70px;margin-left:8px;padding:4px 8px;border-radius:6px;border:1px solid var(--border);'
        'background:var(--bg-surface);color:var(--text-primary)"></label>'
        '<label style="font-size:0.85rem;color:var(--text-secondary)">Category '
        '<select id="roi-cat" style="margin-left:8px;padding:4px 8px;border-radius:6px;border:1px solid var(--border);'
        'background:var(--bg-surface);color:var(--text-primary)">'
        '<option value="">All</option>'
        '<option>Sneakers</option><option>Apparel</option><option>Bags</option>'
        '<option>Watches</option><option>Accessories</option></select></label>'
        '<label style="font-size:0.85rem;color:var(--text-secondary)">Velocity '
        '<select id="roi-vel" style="margin-left:8px;padding:4px 8px;border-radius:6px;border:1px solid var(--border);'
        'background:var(--bg-surface);color:var(--text-primary)">'
        '<option value="">Any</option><option>Very High</option><option>High</option>'
        '<option>Med</option><option>Low</option></select></label>'
        '<span id="roi-count" style="font-size:0.8rem;color:var(--text-muted);margin-left:auto"></span>'
        '</div>'
    )

    # ── Master ROI Table ──────────────────────────────────────────────────
    # Data: category, brand, item, bst_low, bst_high, velocity, batch, rep_low, rep_high, roi_low, roi_high, rec
    rows = [
        # Sneakers
        ("Sneakers", "Jordan", "AJ1 High Chicago Lost & Found", 180, 230, "High", "LJR / GOD", 130, 155, 28, 58, "Top batch &mdash; scrutinized"),
        ("Sneakers", "Jordan", "AJ1 High Chicago OG 85", 170, 210, "Med", "LJR", 125, 145, 27, 56, "Top batch"),
        ("Sneakers", "Jordan", "AJ1 High Royal", 110, 140, "Med", "H12", 70, 85, 45, 75, "Mid fine"),
        ("Sneakers", "Jordan", "AJ1 High Shadow 2.0", 95, 125, "Med", "H12 / LJR", 70, 95, 25, 55, "Mid fine"),
        ("Sneakers", "Jordan", "AJ1 High Bred Toe", 110, 140, "Med", "LJR", 95, 115, 15, 32, "Top (toe shape picky)"),
        ("Sneakers", "Jordan", "AJ4 Thunder", 150, 185, "Med", "LJR", 110, 130, 25, 55, "Top batch"),
        ("Sneakers", "Jordan", "AJ4 White Oreo", 155, 195, "High", "LJR", 115, 135, 24, 56, "Top batch"),
        ("Sneakers", "Jordan", "AJ4 Military Blue", 145, 180, "Med", "LJR", 110, 130, 20, 50, "Top batch"),
        ("Sneakers", "Jordan", "AJ4 Bred Reimagined", 160, 200, "High", "LJR / AJ", 115, 140, 28, 60, "Top batch"),
        ("Sneakers", "Jordan", "AJ4 Black Cat", 135, 170, "Med", "LJR", 100, 125, 22, 55, "Top batch"),
        ("Sneakers", "Travis Scott", "AJ1 Low Mocha", 210, 270, "Very High", "LJR / G5", 145, 180, 30, 72, "Top batch &mdash; reverse swoosh scrutinized"),
        ("Sneakers", "Travis Scott", "AJ1 Low Olive", 195, 245, "High", "LJR", 145, 175, 22, 54, "Top batch"),
        ("Sneakers", "Travis Scott", "AJ1 Low Reverse Mocha", 225, 290, "Very High", "LJR / G5", 150, 185, 35, 75, "Top batch"),
        ("Sneakers", "Travis Scott", "AJ1 Low Pink Pack (W)", 175, 215, "Med", "LJR", 140, 165, 17, 40, "Top batch"),
        ("Sneakers", "Travis Scott", "AJ4 Cactus Jack", 240, 310, "Med", "LJR / G5", 170, 210, 26, 63, "Top batch"),
        ("Sneakers", "Travis Scott", "AJ4 Purple", 220, 280, "Med", "LJR", 165, 200, 22, 52, "Top batch"),
        ("Sneakers", "Nike", "Dunk Low Panda", 90, 115, "Very High", "H12 / LJR", 60, 80, 35, 75, "Mid fine &mdash; volume play"),
        ("Sneakers", "Nike", "Dunk Low Syracuse", 100, 130, "Med", "H12", 65, 85, 40, 75, "Mid fine"),
        ("Sneakers", "Nike", "Dunk Low Michigan", 95, 125, "Med", "H12", 65, 85, 35, 70, "Mid fine"),
        ("Sneakers", "Nike", "Dunk Low UNC", 95, 125, "Med", "H12", 65, 85, 35, 70, "Mid fine"),
        ("Sneakers", "Yeezy", "350 Zebra", 85, 110, "Low", "BASF / GP", 60, 75, 30, 55, "Saturated"),
        ("Sneakers", "Yeezy", "350 Beluga Reflective", 95, 125, "Low", "BASF", 65, 80, 35, 65, "Slow mover"),
        ("Sneakers", "Yeezy", "350 Static (non-refl)", 80, 100, "Low", "BASF", 60, 75, 22, 48, "Dead-ish"),
        ("Sneakers", "Yeezy", "350 Bred", 90, 120, "Low", "BASF", 65, 80, 28, 60, "Seasonal"),
        ("Sneakers", "Nike", "AF1 Triple White", 70, 90, "High", "LJR / M", 50, 65, 25, 60, "Mid fine &mdash; basic"),
        ("Sneakers", "Nike", "AF1 NOCTA Certified Lover", 140, 175, "Med", "LJR", 100, 125, 25, 55, "Top batch"),
        ("Sneakers", "Off-White", "AJ1 Chicago", 310, 400, "Med", "OWF / LJR", 220, 275, 28, 62, "Top only &mdash; heavy QC"),
        ("Sneakers", "Off-White", "AJ1 UNC / Alaska", 260, 340, "Med", "OWF", 200, 250, 22, 55, "Top only"),
        ("Sneakers", "Adidas", "Samba OG Black/White", 70, 90, "Very High", "LY", 45, 60, 35, 75, "Mid fine"),
        ("Sneakers", "Adidas", "Samba Wales Bonner", 105, 140, "High", "LY / top", 70, 90, 38, 70, "Mid fine"),
        ("Sneakers", "ASICS", "Gel-Kayano 14 Cream", 100, 130, "High", "Top tier", 65, 85, 40, 75, "Mid fine"),
        ("Sneakers", "ASICS", "JJJJound Kayano 14", 140, 180, "Med", "Top tier", 85, 110, 45, 80, "Top batch"),
        ("Sneakers", "New Balance", "550 White / Green", 85, 110, "High", "Top tier", 55, 70, 40, 80, "Mid fine"),
        ("Sneakers", "New Balance", "9060 Gray Day", 95, 120, "High", "Top tier", 60, 80, 40, 75, "Mid fine"),
        ("Sneakers", "New Balance", "1906R Silver / Black", 100, 130, "Med", "Top tier", 65, 85, 40, 70, "Mid fine"),
        ("Sneakers", "Salomon", "XT-6 Black", 125, 160, "Med", "Top tier", 75, 95, 45, 85, "Mid fine"),
        # Apparel
        ("Apparel", "Essentials", "Hoodie Taupe", 55, 75, "Very High", "Top Essentials", 28, 38, 55, 130, "Mid fine"),
        ("Apparel", "Essentials", "Hoodie Cement", 55, 75, "Very High", "Top", 28, 38, 55, 130, "Mid fine"),
        ("Apparel", "Essentials", "Sweatshorts Pit", 45, 65, "High", "Top", 22, 32, 60, 140, "Mid fine"),
        ("Apparel", "Essentials", "Sweatpants", 55, 75, "High", "Top", 28, 38, 55, 130, "Mid fine"),
        ("Apparel", "Supreme", "Box Logo Hoodie FW16 Red", 145, 195, "Med", "Ramen / top", 70, 95, 65, 145, "Top batch"),
        ("Apparel", "Supreme", "Box Logo Hoodie Black", 120, 165, "Med", "Top", 65, 90, 55, 125, "Top batch"),
        ("Apparel", "BAPE", "Shark Hoodie Black", 95, 135, "Med", "1:1 seller", 60, 80, 35, 85, "Top batch"),
        ("Apparel", "BAPE", "Shark Hoodie Purple Camo", 110, 150, "Med", "1:1", 65, 85, 45, 100, "Top batch"),
        ("Apparel", "Stone Island", "Hoodie (badge)", 90, 125, "High", "Top", 45, 65, 65, 140, "Mid fine &mdash; patch is the tell"),
        ("Apparel", "Stone Island", "Shadow Project Jacket", 180, 240, "Med", "Top", 110, 140, 45, 90, "Top batch"),
        ("Apparel", "Represent", "Owners Club Tee", 45, 65, "High", "Top", 20, 30, 85, 175, "Mid fine &mdash; huge ROI"),
        ("Apparel", "Represent", "Owners Club Hoodie", 85, 115, "High", "Top", 40, 55, 75, 145, "Mid fine"),
        ("Apparel", "Represent", "Owners Club Shorts", 55, 75, "High", "Top", 25, 35, 85, 160, "Mid fine"),
        ("Apparel", "Corteiz", "Tracksuit", 110, 145, "High", "Top", 55, 75, 70, 135, "Mid fine"),
        ("Apparel", "Corteiz", "Alcatraz Tee", 40, 60, "High", "Top", 18, 28, 75, 170, "Mid fine"),
        ("Apparel", "Hellstar", "Hoodie", 95, 130, "Med", "Top", 50, 70, 55, 120, "Top batch"),
        ("Apparel", "Hellstar", "Sweatpants", 75, 100, "Med", "Top", 40, 55, 50, 110, "Top batch"),
        ("Apparel", "Denim Tears", "Cotton Wreath Hoodie", 145, 190, "Med", "Top", 75, 100, 60, 125, "Top batch"),
        ("Apparel", "Arc'teryx", "Beta AR", 165, 225, "High", "1:1 seller", 95, 130, 45, 100, "Top batch"),
        ("Apparel", "Arc'teryx", "Atom LT", 110, 145, "High", "Top", 65, 85, 45, 95, "Mid fine"),
        ("Apparel", "Moncler", "Maya", 260, 340, "Med", "Top 1:1", 170, 220, 32, 72, "Top batch"),
        # Bags
        ("Bags", "Chanel", "Classic Flap Medium (caviar)", 380, 520, "High", "HG5 / Gold", 240, 320, 40, 85, "Top batch"),
        ("Bags", "Chanel", "Jumbo Caviar", 420, 580, "Med", "HG5", 260, 340, 50, 90, "Top batch"),
        ("Bags", "LV", "Neverfull MM", 180, 240, "Very High", "Top 1:1", 95, 130, 65, 125, "Top batch &mdash; date code"),
        ("Bags", "LV", "Speedy 25 / 30", 150, 210, "High", "Top", 85, 115, 55, 115, "Top batch"),
        ("Bags", "Hermès", "Birkin 25 / 30", 650, 950, "Med", "Top Togo", 380, 520, 55, 110, "Top batch"),
        ("Bags", "Goyard", "St. Louis", 220, 290, "High", "Top", 120, 160, 65, 120, "Top batch"),
        ("Bags", "Dior", "Book Tote (embroidered)", 220, 310, "High", "Top", 130, 170, 50, 110, "Top batch"),
        ("Bags", "Bottega", "Jodie (small)", 170, 230, "Med", "Top", 100, 135, 45, 95, "Top batch"),
        ("Bags", "Bottega", "Cassette", 155, 210, "Med", "Top", 95, 125, 40, 90, "Top batch"),
        # Watches
        ("Watches", "AP", "Royal Oak 15400", 520, 720, "Med", "VSF / APSF", 380, 500, 22, 55, "Top factory only"),
        ("Watches", "Rolex", "Submariner 116610LN", 430, 600, "High", "Clean / VSF", 310, 420, 25, 60, "Top factory"),
        ("Watches", "Rolex", "Submariner 124060", 460, 620, "High", "Clean", 330, 440, 25, 60, "Top factory"),
        ("Watches", "Rolex", "Daytona Panda", 540, 740, "High", "Clean / BT", 380, 510, 30, 65, "Top factory"),
        ("Watches", "Patek", "Nautilus 5711", 600, 850, "Med", "PPF / 3K", 430, 580, 28, 65, "Top factory"),
        # Accessories
        ("Accessories", "New Era", "ALD Cap", 45, 65, "Med", "Top", 22, 32, 60, 135, "Mid fine"),
        ("Accessories", "Hermès", "H Belt (reversible)", 95, 135, "Very High", "Top", 45, 60, 75, 150, "Top batch &mdash; buckle cast"),
        ("Accessories", "Van Cleef", "Alhambra 5-motif bracelet", 130, 180, "High", "925 silver", 65, 90, 70, 140, "Top batch"),
        ("Accessories", "Cartier", "Love Bracelet", 145, 200, "Very High", "Top 1:1", 75, 100, 70, 135, "Top batch"),
    ]

    # Compute midpoints & assemble table
    roi_rows_html = []
    for cat, brand, item, bl, bh, vel, batch, rl, rh, roi_l, roi_h, rec in rows:
        bst_mid = (bl + bh) / 2
        rep_mid = (rl + rh) / 2
        margin_mid = bst_mid - rep_mid
        roi_mid = round((margin_mid / rep_mid) * 100) if rep_mid else 0
        # Color code ROI
        if roi_mid >= 90:
            roi_color = gc
        elif roi_mid >= 50:
            roi_color = cc
        elif roi_mid >= 30:
            roi_color = ac
        else:
            roi_color = rc
        roi_rows_html.append(
            f'<tr data-cat="{cat}" data-vel="{vel}" data-roi="{roi_mid}">'
            f'<td>{cat}</td>'
            f'<td><strong>{brand}</strong> {item}</td>'
            f'<td>${bl}&ndash;${bh}</td>'
            f'<td>{vel}</td>'
            f'<td>{batch}</td>'
            f'<td>${rl}&ndash;${rh}</td>'
            f'<td>${round(margin_mid)}</td>'
            f'<td><strong style="color:{roi_color}">{roi_mid}%</strong> <span style="color:var(--text-muted);font-size:0.78rem">({roi_l}&ndash;{roi_h}%)</span></td>'
            f'<td>{rec}</td>'
            f'</tr>'
        )

    p.append(_sec("Master ROI Table", "BST sold range vs. agent-landed sourcing cost. ROI % uses midpoints; range shown in parentheses."))
    p.append(_exp(
        f'<strong style="color:{gc}">Green</strong> = 90%+ ROI (elite). '
        f'<strong style="color:{cc}">Cyan</strong> = 50&ndash;89% (strong). '
        f'<strong style="color:{ac}">Amber</strong> = 30&ndash;49% (ok). '
        f'<strong style="color:{rc}">Red</strong> = &lt;30% (marginal &mdash; only chase for volume or hype).'))
    p.append('<div class="table-wrap"><table class="data-table" id="roi-table"><thead><tr>'
             '<th data-sort>Category</th><th data-sort>Item</th>'
             '<th data-sort>BST Sold $</th><th data-sort>Velocity</th>'
             '<th data-sort>Best Batch</th><th data-sort>Source Cost $</th>'
             '<th data-sort>Margin $</th><th data-sort>ROI % (range)</th>'
             '<th>Batch Recommendation</th>'
             '</tr></thead><tbody id="roi-tbody">')
    p.extend(roi_rows_html)
    p.append('</tbody></table></div>')

    # ── Top 10 ROI Winners ───────────────────────────────────────────────
    p.append(_sec("Top 10 ROI Winners", "Highest mid-point ROI % across all tracked BST items. Weighted toward apparel/accessories."))
    p.append('<div class="table-wrap"><table class="data-table"><thead><tr>'
             '<th data-sort>#</th><th data-sort>Item</th><th data-sort>ROI % (mid)</th><th>Why It Wins</th>'
             '</tr></thead><tbody>'
             f'<tr><td>1</td><td><strong>Represent Owners Club Tee</strong></td><td><strong style="color:{gc}">~125%</strong></td><td>$25 source, $55 BST. Low QC risk, high velocity. Best $/unit apparel flip.</td></tr>'
             f'<tr><td>2</td><td><strong>Corteiz Alcatraz Tee</strong></td><td><strong style="color:{gc}">~120%</strong></td><td>Hype, low cost, fastest flip on r/FashionRepsBST.</td></tr>'
             f'<tr><td>3</td><td><strong>Represent OC Shorts</strong></td><td><strong style="color:{gc}">~120%</strong></td><td>Summer Apr&ndash;Jul velocity window. Bundle with tee for AOV lift.</td></tr>'
             f'<tr><td>4</td><td><strong>Herm&egrave;s H Belt</strong></td><td><strong style="color:{gc}">~110%</strong></td><td>Buckle cast is the only QC tell. $50 source, $115 BST.</td></tr>'
             f'<tr><td>5</td><td><strong>Supreme BLH FW16 Red</strong></td><td><strong style="color:{gc}">~105%</strong></td><td>Iconic colorway, scarcity premium, reliable top batch.</td></tr>'
             f'<tr><td>6</td><td><strong>Cartier Love Bracelet</strong></td><td><strong style="color:{gc}">~100%</strong></td><td>Year-round RepLadies demand. 1:1 is cheap ($80ish).</td></tr>'
             f'<tr><td>7</td><td><strong>Stone Island Hoodie (badge)</strong></td><td><strong style="color:{gc}">~100%</strong></td><td>Compass patch is all buyers inspect. Mid batch is safe.</td></tr>'
             f'<tr><td>8</td><td><strong>Essentials Sweatshorts Pit</strong></td><td><strong style="color:{gc}">~100%</strong></td><td>Cement/Taupe tier demand, $25 source.</td></tr>'
             f'<tr><td>9</td><td><strong>Corteiz Tracksuit</strong></td><td><strong style="color:{gc}">~100%</strong></td><td>Set pricing commands a premium vs. individual pieces.</td></tr>'
             f'<tr><td>10</td><td><strong>LV Neverfull MM</strong></td><td><strong style="color:{cc}">~95%</strong></td><td>High velocity + top batch passes the date-code QC.</td></tr>'
             '</tbody></table></div>')

    # ── Batch quality decision rule ──────────────────────────────────────
    p.append(_sec("Batch Decision Rule &mdash; Top vs. Mid"))
    p.append(_exp(
        "<strong>Heuristic:</strong> On <strong>hyped / scrutinized</strong> releases (Travis Scott, Off-White, Lost &amp; Found, Chicago, Bred Reimagined, Supreme BLH, Chanel flap, LV Neverfull, Herm&egrave;s Birkin), "
        "buyers inspect photos and <strong>will pay the delta</strong> for the top batch &mdash; take it. "
        "On <strong>basic colorways</strong> (Jordan Royal/Shadow, Panda Dunks, AF1 White, Samba OG, Essentials, Stone Island basic hoodies), "
        "H12 / mid-tier batches net <strong>higher ROI%</strong> because BST buyers don't pay enough of a delta to justify the LJR/top-batch markup.", "amber"))

    # ── Condition premiums ───────────────────────────────────────────────
    p.append(_sec("Condition Premium Cheatsheet"))
    p.append('<div class="table-wrap"><table class="data-table"><thead><tr>'
             '<th>Category</th><th>Condition</th><th>Premium vs. SOLD range</th>'
             '</tr></thead><tbody>'
             '<tr><td>Sneakers</td><td>DS (deadstock)</td><td>+10 to +15%</td></tr>'
             '<tr><td>Sneakers</td><td>VNDS</td><td>DS minus 5&ndash;10%</td></tr>'
             '<tr><td>Sneakers</td><td>Used (clean)</td><td>-20 to -35%</td></tr>'
             '<tr><td>Apparel</td><td>Tags on / NWT</td><td>+$10&ndash;$20 flat</td></tr>'
             '<tr><td>Apparel</td><td>Worn &amp; washed</td><td>-25 to -40%</td></tr>'
             '<tr><td>Bags</td><td>With dustbag &amp; authenticity card</td><td>+10 to +15%</td></tr>'
             '<tr><td>Bags</td><td>Missing dustbag</td><td>-10 to -15%</td></tr>'
             '<tr><td>Watches</td><td>Full set (box + papers)</td><td>+15 to +25%</td></tr>'
             '</tbody></table></div>')

    # ── Red flags ────────────────────────────────────────────────────────
    p.append(_sec("Red Flags &mdash; Avoid or Minimize"))
    p.append(f'<div class="action-box"><div class="action-title" style="color:{rc}">Saturated / slow movers</div>'
             f'<p style="font-size:0.85rem;color:var(--text-secondary);margin:4px 0 0">'
             f'<strong>Entire Yeezy 350 line</strong> (Zebra, Beluga, Static, Bred) &mdash; demand cooled since 2024. '
             f'Margin still technically exists but sell-through is slow. Don\'t build depth.</p></div>')
    p.append(f'<div class="action-box"><div class="action-title" style="color:{ac}">High return / dispute risk</div>'
             f'<p style="font-size:0.85rem;color:var(--text-secondary);margin:4px 0 0">'
             f'<strong>Off-White AJ1s</strong> (shape issues), <strong>TS Mochas</strong> (reverse swoosh stitching), '
             f'<strong>Chanel flaps</strong> (CC alignment). Always use top batches, budget ~$15 per order for QC reshoots.</p></div>')
    p.append(f'<div class="action-box"><div class="action-title" style="color:{bc}">Seasonal &mdash; time inventory carefully</div>'
             f'<p style="font-size:0.85rem;color:var(--text-secondary);margin:4px 0 0">'
             f'<strong>Moncler Maya</strong> and <strong>Arc\'teryx Beta AR</strong> spike Oct&ndash;Feb, dead May&ndash;Aug. '
             f'Don\'t stock outerwear in summer. <strong>Represent OC shorts</strong> reverse: dead Nov&ndash;Feb, peak Apr&ndash;Jul.</p></div>')
    p.append(f'<div class="action-box"><div class="action-title" style="color:{pc}">Meta takeaway &mdash; portfolio construction</div>'
             f'<p style="font-size:0.85rem;color:var(--text-secondary);margin:4px 0 0">'
             f'Apparel + accessories beat sneakers on <strong>ROI %</strong>; sneakers win on <strong>absolute $/unit</strong>. '
             f'The winning BST portfolio is <strong>apparel-heavy with mid-tier batches</strong> (Represent, Corteiz, Essentials, Stone Island, Hellstar), '
             f'plus 2&ndash;3 <strong>top-batch sneaker plays</strong> on scrutinized hype (TS Mocha, L&amp;F, Bred Reimagined), '
             f'plus <strong>high-velocity mid-tier sneakers</strong> (Panda Dunks, Samba, Kayano 14, NB 9060) for turn.</p></div>')

    p.append(f'<p style="font-size:0.72rem;color:var(--text-muted);margin-top:24px">'
             f'Pricing compiled April 24, 2026 from r/FashionRepsBST, r/Repsneakers, r/DesignerRepsBST, r/CloseToRetail, '
             f'r/QualityRepsBST, r/sneakerreps, r/RepLadiesBST WTS-SOLD posts. Source costs include agent-landed item + QC '
             f'+ allocated shipping ($15&ndash;$25 per sneaker pair, $8&ndash;$12 per apparel piece, $20&ndash;$35 per bag). '
             f'ROI % = (BST mid &minus; source mid) / source mid. Update monthly as colorways rotate.</p>')

    # ── Filter JS ─────────────────────────────────────────────────────────
    p.append("""
<script>
(function(){
  const minInput = document.getElementById('roi-min');
  const catSel = document.getElementById('roi-cat');
  const velSel = document.getElementById('roi-vel');
  const count = document.getElementById('roi-count');
  const tbody = document.getElementById('roi-tbody');
  if(!tbody) return;
  function apply(){
    const minV = parseFloat(minInput.value)||0;
    const cat = catSel.value;
    const vel = velSel.value;
    let shown = 0, total = 0;
    Array.from(tbody.rows).forEach(r=>{
      total++;
      const roi = parseFloat(r.dataset.roi)||0;
      const rc = r.dataset.cat, rv = r.dataset.vel;
      const pass = roi >= minV && (!cat || rc===cat) && (!vel || rv===vel);
      r.style.display = pass?'':'none';
      if(pass) shown++;
    });
    count.textContent = shown+' of '+total+' items';
  }
  [minInput, catSel, velSel].forEach(el=>{
    el.addEventListener('input', apply);
    el.addEventListener('change', apply);
  });
  apply();
})();
</script>""")

    p.append("</div>")
    return "\n".join(p)


def _tab_niche(_D):
    """Niche & lifestyle picks — jewelry, decor, collectibles, tech, hobbyist."""
    bc, gc, rc, ac, pc, cc = C["blue"], C["green"], C["red"], C["amber"], C["purple"], C["cyan"]
    p = ['<div class="page-content">']
    p.append(_exp(
        "<strong>Niche Picks &mdash; researched April 24, 2026.</strong> "
        "Beyond sneakers, hoodies, and designer bags &mdash; these are the "
        "<strong>lifestyle</strong>, <strong>jewelry</strong>, <strong>home decor</strong>, "
        "<strong>collectibles</strong>, and <strong>hobbyist</strong> categories that reselling "
        "communities are quietly moving serious volume in. Fewer sellers compete here, "
        "margins are better, and many items are <strong>genuine Taobao</strong> (not reps) &mdash; "
        "meaning zero legal/ethical friction for end buyers."))

    # ── Fastest Risers Callout ────────────────────────────────────────────
    p.append(_sec("Fastest Risers &mdash; April 2026", "Items with the sharpest velocity increase across niche categories."))
    p.append(f'<div class="action-box"><div class="action-title" style="color:{gc}">Top 6 Explosive Niche Trends</div><ul>'
             f'<li><strong style="color:{rc}">Pop Mart Labubu figures + bag charms</strong> &mdash; #1 rising collectible of 2026. BLACKPINK Lisa effect. Every major agent has a dedicated landing page.</li>'
             f'<li><strong>Chrome Hearts jewelry</strong> (CH Plus cross, floral rings, bandana bracelets) &mdash; huge on TikTok menswear, rap/skate crossover.</li>'
             f'<li><strong>Moissanite engagement rings</strong> &mdash; r/Moissanite 180k+ subs; 1&ndash;3ct solitaires at $150&ndash;$450 vs. $5k+ retail. Structural shift in engagement-ring market.</li>'
             f'<li><strong>Dyson Airwrap clones</strong> &mdash; TikTok + r/HairDye driven. Shark FlexStyle alt or generic 8-in-1 at $60&ndash;$180.</li>'
             f'<li><strong>Loewe tomato/basil/oregano candles</strong> + Aesop / Diptyque / Le Labo &mdash; candle-dupe category maturing.</li>'
             f'<li><strong>Jellycat plushies</strong> (Bartholomew Bear, Amuseable food) &mdash; TikTok viral, gift-market staple, minimal rep stigma.</li>'
             f'</ul></div>')

    # ── Jewelry Deep-Dive ────────────────────────────────────────────────
    p.append(_sec("Jewelry &mdash; Beyond Van Cleef &amp; Cartier Love", "These are the jewelry pieces r/RepLadies, r/FashionReps, and TikTok menswear are driving right now."))
    p.append(_exp(f'<strong style="color:{pc}">Men\'s jewelry is the most underserved segment</strong> &mdash; Chrome Hearts, David Yurman, and signet rings all have buyers and few sellers.', "purple"))
    p.append('<div class="table-wrap"><table class="data-table"><thead><tr>'
             '<th data-sort>Item</th><th data-sort>Rep Price</th><th data-sort>Trend</th><th>Signal / Source</th>'
             '</tr></thead><tbody>'
             '<tr><td><strong>Tiffany Hardwear graduated necklace</strong> (925 silver)</td><td>$45&ndash;$90</td><td>Rising</td><td>r/RepLadies + TikTok quiet-luxury. Sellers: XinHua, Zhenzhen (Weidian).</td></tr>'
             '<tr><td><strong>Tiffany Lock bangle</strong> (pave diamond)</td><td>$80&ndash;$180</td><td>Stable</td><td>Zendaya Challengers press revival Q1 2026.</td></tr>'
             '<tr><td><strong>Tiffany T-Smile pendant</strong></td><td>$40&ndash;$75</td><td>Stable</td><td>Gateway piece, high-volume DHgate seller.</td></tr>'
             '<tr><td><strong>Return to Tiffany heart tag</strong></td><td>$35&ndash;$60</td><td>Stable</td><td>Y2K / coquette TikTok revival.</td></tr>'
             '<tr><td><strong>Elsa Peretti Bean pendant</strong></td><td>$40&ndash;$80</td><td>Stable</td><td>Older RepLadies demo, loyal buyers.</td></tr>'
             f'<tr><td><strong style="color:{gc}">David Yurman cable bracelet</strong> (men\'s 5&ndash;8mm)</td><td>$60&ndash;$140</td><td>Rising</td><td>Men\'s underserved segment. r/RepTime &times; r/FashionReps crossover.</td></tr>'
             '<tr><td><strong>Bvlgari B.Zero1 4-band ring</strong></td><td>$70&ndash;$160</td><td>Stable</td><td>Rose gold variant strongest.</td></tr>'
             '<tr><td><strong>Bvlgari Serpenti Viper bracelet</strong></td><td>$90&ndash;$200</td><td>Rising</td><td>Zendaya campaign rerun.</td></tr>'
             '<tr><td><strong>Bvlgari Divas\' Dream earrings</strong></td><td>$55&ndash;$110</td><td>Stable</td><td>Niche but loyal.</td></tr>'
             f'<tr><td><strong style="color:{rc}">Chrome Hearts CH Plus cross pendant</strong></td><td>$40&ndash;$120</td><td>Rising hard</td><td>Huge TikTok menswear. Agents: Basetao, Superbuy.</td></tr>'
             '<tr><td><strong>Chrome Hearts floral / dagger ring</strong></td><td>$50&ndash;$150</td><td>Rising</td><td>Rap + skate crossover.</td></tr>'
             '<tr><td><strong>Chrome Hearts bandana / bracelet</strong></td><td>$60&ndash;$180</td><td>Stable-Rising</td><td>High-ticket accessory.</td></tr>'
             '<tr><td><strong>Cuban link chain</strong> (iced VVS moissanite 12&ndash;18mm)</td><td>$80&ndash;$400</td><td>Stable</td><td>DHgate: MoissaniteHipHop, TopGrillz.</td></tr>'
             '<tr><td><strong>Tennis chains</strong> (moissanite 3&ndash;5mm)</td><td>$70&ndash;$250</td><td>Rising</td><td>Men\'s engagement-adjacent piece.</td></tr>'
             '<tr><td><strong>Baroque pearl necklaces</strong> (men\'s 6&ndash;8mm)</td><td>$15&ndash;$45</td><td>Plateauing</td><td>Tyler the Creator / Harry Styles legacy.</td></tr>'
             f'<tr><td><strong style="color:{gc}">Vintage signet rings</strong> (crest / intaglio)</td><td>$25&ndash;$70</td><td>Rising</td><td>&quot;Old money&quot; TikTok + r/mensfashion.</td></tr>'
             '<tr><td><strong>Serpent / jaguar motif rings</strong> (Panth&egrave;re-style no-logo)</td><td>$40&ndash;$150</td><td>Rising</td><td>&quot;Animalia&quot; trend.</td></tr>'
             '<tr><td><strong>Herm&egrave;s Clic H bracelet</strong></td><td>$35&ndash;$75</td><td>Stable</td><td>Evergreen top-5 jewelry seller.</td></tr>'
             '<tr><td><strong>Herm&egrave;s Kelly bracelet</strong> (leather + gold)</td><td>$120&ndash;$280</td><td>Rising</td><td>Celebrity wrist-stack driver.</td></tr>'
             f'<tr><td><strong style="color:{rc}">Moissanite engagement rings</strong> (1&ndash;3ct solitaires)</td><td>$150&ndash;$450</td><td>Massive rise</td><td>r/Moissanite 180k+ subs. Agents: HeliosJewelry (Weidian), StarsGem (DHgate).</td></tr>'
             '</tbody></table></div>')

    # ── Watches Deep-Dive ────────────────────────────────────────────────
    p.append(_sec("Watches &mdash; Beyond Mainstream Submariner", "r/RepTime + RepGeek TD-list governed universe."))
    p.append('<div class="table-wrap"><table class="data-table"><thead><tr>'
             '<th data-sort>Item</th><th data-sort>Factory / Batch</th><th data-sort>Rep Price</th><th data-sort>Trend</th><th>Notes</th>'
             '</tr></thead><tbody>'
             '<tr><td><strong>AP Royal Oak 15400 / 15500</strong></td><td>ZF / APS</td><td>$280&ndash;$650</td><td>Stable</td><td>r/RepTime holy grail tier.</td></tr>'
             '<tr><td><strong>AP Royal Oak 15202 &quot;Jumbo&quot;</strong></td><td>ZF</td><td>$350&ndash;$700</td><td>Stable</td><td>Purist favorite.</td></tr>'
             '<tr><td><strong>Patek Nautilus 5711</strong> (Tiffany blue dial)</td><td>PPF / 3K</td><td>$380&ndash;$750</td><td>Stable</td><td>Still the most-asked piece on r/RepTime.</td></tr>'
             '<tr><td><strong>Patek 5712 / 5980</strong></td><td>PPF</td><td>$400&ndash;$800</td><td>Rising</td><td>Collectors trading up from 5711.</td></tr>'
             f'<tr><td><strong style="color:{ac}">Richard Mille RM 11-03 / RM 055</strong></td><td>KV / ZF</td><td>$180&ndash;$500</td><td>Rising</td><td>Skeletonized, TikTok-driven, flashy.</td></tr>'
             '<tr><td><strong>Rolex Daytona 116500LN</strong> (Panda / Inverse)</td><td>Clean / VSF</td><td>$280&ndash;$600</td><td>Evergreen</td><td>#1 chronograph rep.</td></tr>'
             '<tr><td><strong>Rolex GMT Pepsi / Batman 126710</strong></td><td>Clean / VSF</td><td>$260&ndash;$550</td><td>Stable</td><td>Top-3 Rolex rep overall.</td></tr>'
             '<tr><td><strong>Rolex Datejust 41 Wimbledon</strong></td><td>Clean</td><td>$220&ndash;$480</td><td>Rising</td><td>&quot;Quiet watch&quot; pick.</td></tr>'
             '<tr><td><strong>Rolex Explorer II Polar 226570</strong></td><td>Clean</td><td>$250&ndash;$500</td><td>Stable</td><td>Adventure-watch crowd.</td></tr>'
             '<tr><td><strong>Omega Speedmaster Professional</strong></td><td>OM</td><td>$200&ndash;$450</td><td>Stable</td><td>r/RepTime budget favorite.</td></tr>'
             '<tr><td><strong>Omega Seamaster 300M</strong> (No Time to Die)</td><td>VSF / OM</td><td>$220&ndash;$480</td><td>Stable</td><td>Bond-driver.</td></tr>'
             f'<tr><td><strong style="color:{gc}">Cartier Santos Medium</strong></td><td>BV / 3K</td><td>$180&ndash;$420</td><td>Rising</td><td>Unisex, TikTok quiet luxury.</td></tr>'
             '<tr><td><strong>Cartier Tank Must / Louis</strong></td><td>BV</td><td>$150&ndash;$380</td><td>Rising</td><td>Women\'s + dress watch segment.</td></tr>'
             '<tr><td><strong>Cartier Ballon Bleu 36mm</strong></td><td>3K</td><td>$170&ndash;$400</td><td>Stable</td><td>RepLadies staple.</td></tr>'
             '<tr><td><strong>Pagani Design PD-1662</strong> (Daytona homage)</td><td>Genuine</td><td>$60&ndash;$120</td><td>Rising</td><td>Legal non-logo homage. Huge r/Watches + AliExpress.</td></tr>'
             '<tr><td><strong>Steeldive SD1970</strong> (Sub homage)</td><td>Genuine</td><td>$90&ndash;$160</td><td>Rising</td><td>Hobbyist pick, swiss movement homage.</td></tr>'
             '<tr><td><strong>Apple Watch Ultra 2 clones</strong> (HK9 Ultra, S10 Ultra)</td><td>&mdash;</td><td>$35&ndash;$90</td><td>Rising</td><td>TikTok Shop heavy.</td></tr>'
             '</tbody></table></div>')

    # ── Home Decor ───────────────────────────────────────────────────────
    p.append(_sec("Home Decor &amp; Lifestyle &mdash; Taobao's Quiet Killer Category", "r/malelivingspace, r/DesignPorn, and WFH normalization driving demand."))
    p.append(_exp(f'<strong>Most of these are genuine Taobao products</strong> (real Timemore grinders, real Pop Mart, real Chinese ceramics) &mdash; not reps. Zero stigma, full legitimacy, arbitrage on shipping/markup.', "green"))
    p.append('<div class="table-wrap"><table class="data-table"><thead><tr>'
             '<th data-sort>Item</th><th data-sort>Price</th><th data-sort>Trend</th><th>Signal</th>'
             '</tr></thead><tbody>'
             '<tr><td><strong>Herman Miller Aeron replica</strong> (size B)</td><td>$180&ndash;$380</td><td>Rising</td><td>Post-WFH normalization. r/OfficeChairs.</td></tr>'
             '<tr><td><strong>Eames Lounge Chair + Ottoman</strong> (walnut / palisander)</td><td>$400&ndash;$900</td><td>Stable</td><td>r/malelivingspace staple.</td></tr>'
             '<tr><td><strong>Bearbrick 400% / 1000%</strong> (KAWS, Medicom collabs)</td><td>$30&ndash;$150</td><td>Rising</td><td>r/Bearbrick + Xiaohongshu driven.</td></tr>'
             '<tr><td><strong>KAWS Companion / Chum figures</strong></td><td>$40&ndash;$180</td><td>Stable</td><td>Gen Z collectible.</td></tr>'
             f'<tr><td><strong style="color:{rc}">Pop Mart Labubu &quot;Big Into Energy&quot; blind boxes</strong></td><td>$8&ndash;$35 each</td><td>Explosive</td><td>BLACKPINK Lisa. #1 rising collectible of 2026. Superbuy, CSSBuy, Allchinabuy all have landing pages.</td></tr>'
             '<tr><td><strong>Smiski figures</strong></td><td>$5&ndash;$15</td><td>Stable</td><td>Gift market, low-ticket volume.</td></tr>'
             f'<tr><td><strong style="color:{gc}">Jellycat plushies</strong> (Bartholomew, Amuseable food)</td><td>$15&ndash;$45</td><td>Rising massively</td><td>TikTok viral, r/Jellycat.</td></tr>'
             '<tr><td><strong>Aesop hand wash</strong> (Reverence, Resurrection)</td><td>$12&ndash;$25</td><td>Rising</td><td>Dupe category maturing.</td></tr>'
             '<tr><td><strong>Diptyque Baies / Figuier candles</strong></td><td>$20&ndash;$45</td><td>Stable</td><td>Signature scents.</td></tr>'
             '<tr><td><strong>Le Labo Santal 33</strong> candle + perfume</td><td>$25&ndash;$60</td><td>Rising</td><td>TikTok signature scent.</td></tr>'
             f'<tr><td><strong style="color:{gc}">Loewe tomato / basil / oregano candles</strong></td><td>$30&ndash;$70</td><td>Rising</td><td>TikTok-driven, &quot;tomato girl&quot; crossover.</td></tr>'
             '<tr><td><strong>Herm&egrave;s Avalon throw blanket</strong> (H pattern)</td><td>$80&ndash;$220</td><td>Rising</td><td>&quot;Rich home&quot; aesthetic.</td></tr>'
             '<tr><td><strong>Vitra miniature chair collection</strong></td><td>$30&ndash;$80 ea</td><td>Stable</td><td>Design-nerd gift pick.</td></tr>'
             '<tr><td><strong>Noguchi coffee table</strong></td><td>$180&ndash;$400</td><td>Stable</td><td>Evergreen design-porn staple.</td></tr>'
             '<tr><td><strong>Flos Arco floor lamp</strong></td><td>$220&ndash;$550</td><td>Rising</td><td>r/DesignPorn anchor piece.</td></tr>'
             '<tr><td><strong>Flos IC Lights</strong> pendant / table</td><td>$90&ndash;$220</td><td>Rising</td><td>Apartment-size option.</td></tr>'
             '<tr><td><strong>Artemide Tolomeo desk lamp</strong></td><td>$60&ndash;$150</td><td>Stable</td><td>WFH desk setup.</td></tr>'
             '<tr><td><strong>Tom Dixon Melt / Beat pendants</strong></td><td>$80&ndash;$200</td><td>Stable</td><td>Kitchen/dining lighting.</td></tr>'
             '<tr><td><strong>Timemore Chestnut C3 / Sculptor grinders</strong></td><td>$60&ndash;$180</td><td>Rising</td><td><strong>Genuine not rep.</strong> Huge on r/espresso.</td></tr>'
             '<tr><td><strong>Flair 58 espresso lever clones</strong></td><td>$150&ndash;$350</td><td>Rising</td><td>Coffee-nerd gear.</td></tr>'
             '</tbody></table></div>')

    # ── Tech & Gadgets ────────────────────────────────────────────────────
    p.append(_sec("Tech &amp; Gadgets"))
    p.append('<div class="table-wrap"><table class="data-table"><thead><tr>'
             '<th data-sort>Item</th><th data-sort>Rep Price</th><th data-sort>Trend</th><th>Signal</th>'
             '</tr></thead><tbody>'
             '<tr><td><strong>AirPods Max clones</strong> (Huaqiangbei 1:1)</td><td>$40&ndash;$110</td><td>Stable</td><td>r/RepAirPods established market.</td></tr>'
             '<tr><td><strong>AirPods Pro 2 clones</strong> (H2S / Hi-Fi)</td><td>$20&ndash;$55</td><td>Stable</td><td>High-volume low-ticket.</td></tr>'
             '<tr><td><strong>Sony WH-1000XM5 clones</strong></td><td>$40&ndash;$90</td><td>Rising</td><td>ANC headphone growth.</td></tr>'
             '<tr><td><strong>DualSense Edge custom shells / mods</strong></td><td>$25&ndash;$80</td><td>Rising</td><td>r/customcontrollers.</td></tr>'
             '<tr><td><strong>Keychron Q / Zoom75 / Neo80 keyboards</strong></td><td>$120&ndash;$350</td><td>Rising</td><td><strong>Genuine.</strong> r/MechanicalKeyboards Taobao group-buy culture.</td></tr>'
             f'<tr><td><strong style="color:{gc}">Oura Ring clones</strong> (RingConn, COLMI R02&ndash;R10)</td><td>$25&ndash;$90</td><td>Rising</td><td>Alt-to-Oura segment growing.</td></tr>'
             '<tr><td><strong>Ray-Ban Meta Wayfarer clones</strong></td><td>$35&ndash;$90</td><td>Rising</td><td>Post-Meta hype.</td></tr>'
             '<tr><td><strong>Apple Vision Pro clones</strong> (VisionSE)</td><td>$80&ndash;$250</td><td>Fading</td><td>Novelty, hype died.</td></tr>'
             '<tr><td><strong>Insta360 Ace / SJCAM action cams</strong></td><td>$80&ndash;$220</td><td>Rising</td><td><strong>Insta360 is genuine</strong> and rising fast.</td></tr>'
             f'<tr><td><strong style="color:{rc}">Dyson Airwrap clones</strong> (Shark FlexStyle alt, generic 8-in-1)</td><td>$60&ndash;$180</td><td>Explosive</td><td>TikTok + r/HairDye. Top beauty-tech rep of 2026.</td></tr>'
             '</tbody></table></div>')

    # ── Fragrance & Beauty ────────────────────────────────────────────────
    p.append(_sec("Fragrance &amp; Beauty &mdash; Dupe Economy"))
    p.append(_exp(f'r/fragranceclones is massive. Lattafa and Armaf are established &quot;clone houses&quot; whose pricing is already built into community norms.', "cyan"))
    p.append('<div class="table-wrap"><table class="data-table"><thead><tr>'
             '<th data-sort>Item</th><th data-sort>Rep Price</th><th data-sort>Trend</th><th>Signal</th>'
             '</tr></thead><tbody>'
             '<tr><td><strong>Creed Aventus clones</strong> (Lattafa Khamrah, Armaf Club de Nuit Intense)</td><td>$15&ndash;$40</td><td>Stable</td><td>#1 clone fragrance category.</td></tr>'
             '<tr><td><strong>Baccarat Rouge 540 dupes</strong> (Cloud by Ariana, Lattafa Asad)</td><td>$12&ndash;$35</td><td>Stable</td><td>Unisex powerhouse.</td></tr>'
             '<tr><td><strong>Dior Sauvage dupe</strong> (Armaf Ventana)</td><td>$15&ndash;$30</td><td>Stable</td><td>Men\'s gateway clone.</td></tr>'
             '<tr><td><strong>Tom Ford Oud Wood / Tobacco Vanille dupes</strong></td><td>$20&ndash;$45</td><td>Rising</td><td>Niche-scent trend.</td></tr>'
             '<tr><td><strong>YSL Libre dupe</strong> (Lattafa Yara)</td><td>$15&ndash;$30</td><td>Rising</td><td>TikTok women\'s driver.</td></tr>'
             '<tr><td><strong>Charlotte Tilbury Pillow Talk lipstick dupes</strong></td><td>$5&ndash;$12</td><td>Stable</td><td>r/MakeupAddiction.</td></tr>'
             '<tr><td><strong>Dior Lip Glow dupes</strong></td><td>$4&ndash;$10</td><td>Stable</td><td>TikTok volume.</td></tr>'
             '<tr><td><strong>La Mer Cr&egrave;me dupes</strong> (Beauty of Joseon + local)</td><td>$10&ndash;$30</td><td>Rising</td><td>K-beauty convergence.</td></tr>'
             '<tr><td><strong>Hakuhodo / Chikuhodo brush dupes</strong> (MyDestiny, Rownyeon)</td><td>$8&ndash;$30</td><td>Rising</td><td>Niche makeup-tools segment.</td></tr>'
             '</tbody></table></div>')

    # ── Small Leather Goods & Accessories ────────────────────────────────
    p.append(_sec("Small Leather Goods &amp; Accessories", "Under-covered in most rep lists. Lower ticket, better margin-to-risk."))
    p.append('<div class="table-wrap"><table class="data-table"><thead><tr>'
             '<th data-sort>Item</th><th data-sort>Rep Price</th><th data-sort>Trend</th><th>Signal</th>'
             '</tr></thead><tbody>'
             '<tr><td><strong>LV pocket organizer</strong> (Monogram / Damier)</td><td>$50&ndash;$120</td><td>Stable</td><td>Best-selling men\'s SLG.</td></tr>'
             '<tr><td><strong>Saint Laurent card holder</strong></td><td>$30&ndash;$70</td><td>Rising</td><td>Women\'s everyday piece.</td></tr>'
             '<tr><td><strong>Bottega Veneta Intrecciato long wallet</strong></td><td>$80&ndash;$180</td><td>Stable</td><td>Daniel Lee-era credibility.</td></tr>'
             '<tr><td><strong>Prada triangle card holder</strong> (Saffiano)</td><td>$35&ndash;$75</td><td>Rising</td><td>TikTok driver.</td></tr>'
             '<tr><td><strong>Goyard Saint-Sulpice card holder</strong></td><td>$45&ndash;$110</td><td>Rising</td><td>Chevron print = visual hook.</td></tr>'
             '<tr><td><strong>LV Initiales belt 40mm</strong></td><td>$40&ndash;$95</td><td>Stable</td><td>Evergreen men\'s.</td></tr>'
             '<tr><td><strong>Herm&egrave;s H belt</strong> (reversible)</td><td>$60&ndash;$150</td><td>Stable</td><td>Top-3 belt category.</td></tr>'
             '<tr><td><strong>Herm&egrave;s silk square 90cm</strong> (Brides de Gala)</td><td>$35&ndash;$90</td><td>Rising</td><td>&quot;Old money&quot; driver.</td></tr>'
             '<tr><td><strong>Burberry check cashmere scarf</strong></td><td>$40&ndash;$110</td><td>Stable</td><td>Winter anchor, AW driver.</td></tr>'
             '<tr><td><strong>LV Vivienne bag charm</strong></td><td>$40&ndash;$95</td><td>Rising</td><td>Bag-charm resurgence.</td></tr>'
             f'<tr><td><strong style="color:{rc}">Labubu bag charms</strong> (Pop Mart)</td><td>$10&ndash;$30</td><td>Explosive</td><td>#1 bag charm of 2026.</td></tr>'
             '<tr><td><strong>Jellycat bag charms</strong></td><td>$15&ndash;$35</td><td>Rising</td><td>Gift-market crossover.</td></tr>'
             '<tr><td><strong>Rimowa Original / Essential cabin</strong></td><td>$180&ndash;$380</td><td>Stable</td><td>Travel season driver.</td></tr>'
             '</tbody></table></div>')

    # ── Collectibles & Cultural ─────────────────────────────────────────
    p.append(_sec("Collectibles &amp; Cultural Niches"))
    p.append('<div class="table-wrap"><table class="data-table"><thead><tr>'
             '<th data-sort>Item</th><th data-sort>Price</th><th data-sort>Trend</th><th>Signal</th>'
             '</tr></thead><tbody>'
             '<tr><td><strong>Pok&eacute;mon booster boxes</strong> (Japanese 151, Terastal Festival)</td><td>$90&ndash;$180</td><td>Rising</td><td><strong>Genuine</strong> Taobao/Weidian proxy at Japan retail. r/PokemonTCG.</td></tr>'
             '<tr><td><strong>Retro NBA jerseys</strong> (Mitchell &amp; Ness style &mdash; Jordan, Kobe, Iverson)</td><td>$25&ndash;$60</td><td>Stable</td><td>Crosses into streetwear.</td></tr>'
             '<tr><td><strong>Premier League retro jerseys</strong> (Arsenal Invincibles, United 99)</td><td>$20&ndash;$50</td><td>Rising</td><td>Blokecore 2.0 driver.</td></tr>'
             '<tr><td><strong>Anime figures</strong> (One Piece, JJK, Demon Slayer &mdash; Bandai + GK)</td><td>$30&ndash;$200</td><td>Rising</td><td>r/AnimeFigures.</td></tr>'
             '<tr><td><strong>K-pop photocards</strong> (NewJeans, Stray Kids, aespa unofficial)</td><td>$2&ndash;$15</td><td>Stable</td><td>Fan segment, high frequency.</td></tr>'
             '<tr><td><strong>Assouline / Taschen coffee table books</strong> (reprints)</td><td>$25&ndash;$80</td><td>Rising</td><td>&quot;Shelf styling&quot; TikTok.</td></tr>'
             '<tr><td><strong>Japanese stationery</strong> (Midori, Hobonichi, Pilot)</td><td>$5&ndash;$40</td><td>Stable</td><td>Niche but loyal.</td></tr>'
             '</tbody></table></div>')

    # ── Hobbyist ─────────────────────────────────────────────────────────
    p.append(_sec("Hobbyist &amp; Interest-Based", "Low competition, high engagement, repeat-buyer communities."))
    p.append('<div class="table-wrap"><table class="data-table"><thead><tr>'
             '<th data-sort>Item</th><th data-sort>Price</th><th data-sort>Trend</th><th>Signal</th>'
             '</tr></thead><tbody>'
             '<tr><td><strong>Staunton chess sets</strong> (weighted, 3.75&quot; king, ebonized)</td><td>$40&ndash;$150</td><td>Stable</td><td>Queen\'s Gambit legacy.</td></tr>'
             '<tr><td><strong>Mont Blanc Meisterst&uuml;ck 149 replicas</strong></td><td>$30&ndash;$90</td><td>Stable</td><td>r/fountainpens cautious but present.</td></tr>'
             '<tr><td><strong>Namiki / Pilot Vanishing Point</strong> (proxy, genuine)</td><td>$80&ndash;$250</td><td>Rising</td><td>Japan-retail arbitrage.</td></tr>'
             '<tr><td><strong>Zippo customs / S.T. Dupont Ligne 2 clones</strong></td><td>$20&ndash;$80</td><td>Stable</td><td>Cigar-adjacent.</td></tr>'
             '<tr><td><strong>Humidors</strong> (Spanish cedar 50&ndash;100ct)</td><td>$40&ndash;$140</td><td>Stable</td><td>r/cigars.</td></tr>'
             '<tr><td><strong>Riedel Vinum / Zalto-style crystal stemware</strong></td><td>$20&ndash;$60 / 6</td><td>Rising</td><td>Wine aesthetic TikTok.</td></tr>'
             '<tr><td><strong>Baccarat Harcourt tumbler dupes</strong></td><td>$15&ndash;$45</td><td>Rising</td><td>&quot;Whiskey aesthetic&quot; driver.</td></tr>'
             '<tr><td><strong>Gongfu tea sets</strong> (Jianzhan, Yixing zisha)</td><td>$30&ndash;$200</td><td>Rising</td><td><strong>Genuine Chinese ceramics.</strong> r/tea + r/Teaware.</td></tr>'
             '</tbody></table></div>')

    # ── Strategy / Takeaways ─────────────────────────────────────────────
    p.append(_sec("Sourcing Strategy &amp; Agent Notes"))
    p.append(f'<div class="action-box"><div class="action-title" style="color:{gc}">Fastest risers to prioritize this quarter</div>'
             f'<p style="font-size:0.85rem;color:var(--text-secondary);margin:4px 0 0">'
             f'Pop Mart Labubu (figures + bag charms), Chrome Hearts jewelry, moissanite engagement rings, '
             f'Dyson Airwrap clones, Loewe / Aesop / Le Labo candles, Jellycat plushies.</p></div>')
    p.append(f'<div class="action-box"><div class="action-title" style="color:{pc}">Underserved segments with highest margin potential</div>'
             f'<p style="font-size:0.85rem;color:var(--text-secondary);margin:4px 0 0">'
             f'Men\'s jewelry (David Yurman, Chrome Hearts, signet rings), home lighting (Flos, Artemide, Tom Dixon), '
             f'coffee gear (Timemore, Flair), Gongfu tea ceramics.</p></div>')
    p.append(f'<div class="action-box"><div class="action-title" style="color:{bc}">Agent-specific sourcing notes</div>'
             f'<ul style="font-size:0.85rem;color:var(--text-secondary);margin:4px 0 0">'
             f'<li><strong>Superbuy + CSSBuy</strong> &mdash; lead for Pop Mart, Bearbrick, Labubu</li>'
             f'<li><strong>Basetao</strong> &mdash; Chrome Hearts jewelry authority</li>'
             f'<li><strong>Weidian direct</strong> (XinHua, Zhenzhen) &mdash; Tiffany / Cartier / Bvlgari jewelry</li>'
             f'<li><strong>DHgate</strong> &mdash; iced-out chains (MoissaniteHipHop, TopGrillz) + watch straps</li>'
             f'<li><strong>r/RepTime TD list</strong> &mdash; still governs all watch seller trust decisions</li>'
             f'<li><strong>AliExpress + Taobao</strong> &mdash; genuine homage watches (Pagani, Steeldive), Timemore, Insta360</li>'
             f'</ul></div>')
    p.append(f'<div class="action-box"><div class="action-title" style="color:{ac}">Fading &mdash; avoid fresh depth</div>'
             f'<p style="font-size:0.85rem;color:var(--text-secondary);margin:4px 0 0">'
             f'Fendi Karlito charms, Panerai Luminor, Gucci Marmont belts, Vision Pro clones. '
             f'Sell through existing stock; don\'t replenish.</p></div>')

    p.append(f'<p style="font-size:0.72rem;color:var(--text-muted);margin-top:24px">'
             f'Researched April 24, 2026. Sources: r/RepLadies, r/RepTime, r/FashionReps, r/Moissanite, r/Bearbrick, r/Jellycat, '
             f'r/AnimeFigures, r/malelivingspace, r/DesignPorn, r/OfficeChairs, r/espresso, r/fragranceclones, r/MechanicalKeyboards, '
             f'r/tea, TikTok menswear + quiet luxury tags, Xiaohongshu trend aggregation, Superbuy / CSSBuy / Allchinabuy landing pages.</p>')
    p.append("</div>")
    return "\n".join(p)


def _tab_summer(_D):
    """Summer 2026 inventory guide — April 24, 2026 research snapshot."""
    bc, gc, rc, ac, pc, cc = C["blue"], C["green"], C["red"], C["amber"], C["purple"], C["cyan"]
    p = ['<div class="page-content">']
    p.append(_exp(
        "<strong>Summer 2026 Inventory Guide &mdash; researched April 24, 2026.</strong> "
        "Compiled from live signals across r/FashionReps, r/Repsneakers, r/DesignerReps, r/QualityReps, "
        "r/RepLadies, r/WeidianWarriors and supporting Reddit/TikTok trend tracking. "
        "This is a <strong>summer-specific</strong> overlay &mdash; use alongside the March Market Report, which covers "
        "year-round evergreen demand. Stocking window: <strong>selling through end of August 2026</strong>. "
        "Order from agents now &mdash; typical QC + ship cycle is 3&ndash;5 weeks."))

    # ── Summer Calendar ───────────────────────────────────────────────────
    p.append(_sec("Summer Release &amp; Demand Calendar", "Windows where W2C demand peaks &mdash; source reps ahead of each."))
    p.append(f'<div class="action-box"><div class="action-title">Key Summer Dates</div><ul>'
             f'<li><strong>May 22, 2026</strong> &mdash; Travis Scott x Jordan 1 Low Pink Pack retail. Source LJR batch <strong>now</strong>, demand peaks release week.</li>'
             f'<li><strong>Early June</strong> &mdash; Governors Ball (NYC), Primavera wraps. Festival-fit W2C (graphic tees, mesh shorts, sunnies) spikes.</li>'
             f'<li><strong>June 27 &ndash; July 13, 2026</strong> &mdash; Wimbledon + Tour de France. Tenniscore/Lacoste/Prada Linea Rossa surge.</li>'
             f'<li><strong>Mid-July</strong> &mdash; rumored AJ4 &quot;Oxidized Green&quot; and AJ1 Low &quot;Vachetta Tan&quot; summer pack. Pre-order by late May.</li>'
             f'<li><strong>Rolling Loud (July) + Lollapalooza (Aug)</strong> &mdash; peak festival apparel cycle, bucket hats &amp; statement sunnies.</li>'
             f'<li><strong>Aug 1, 2026</strong> &mdash; back-to-school rep cycle kicks in. Essentials hoodies/sweats shift from shorts to crewnecks.</li>'
             f'</ul></div>')

    # ── Tier 1: Stock Now ─────────────────────────────────────────────────
    p.append(_sec("Tier 1 &mdash; Stock Now (12 SKUs)", "Highest velocity summer W2C items right now. Order this week."))
    p.append(_exp(f'<strong style="color:{rc}">Extreme demand, summer-coded, short fulfillment window.</strong> '
                  f'Every item below has active W2C threads from the last 10 days and is confirmed selling through summer.', "red"))
    p.append('<div class="table-wrap"><table class="data-table"><thead><tr>'
             '<th data-sort>#</th><th data-sort>Category</th><th data-sort>Item</th>'
             '<th data-sort>Best Batch</th><th data-sort>Rep Price</th><th>Summer Signal</th>'
             '</tr></thead><tbody>'
             '<tr><td>1</td><td>Sneaker</td><td><strong>Adidas Samba OG</strong> &mdash; White/Black, Cloud White/Green, Wales Bonner cream</td><td>H12 / GOD</td><td>$55&ndash;$85</td><td>Year 3 of Samba wave, still #1 W2C on r/FashionReps for summer. Wales Bonner pony-hair spiking.</td></tr>'
             '<tr><td>2</td><td>Sneaker</td><td><strong>ASICS Gel-Kayano 14</strong> &mdash; Cream/Silver, Birch/Sheet Rock</td><td>GOD</td><td>$80&ndash;$110</td><td>#1 &quot;quiet luxury runner&quot; for summer. Kith &amp; JJJJound collabs drive velocity.</td></tr>'
             '<tr><td>3</td><td>Apparel</td><td><strong>Essentials FOG Shorts + Sweat Shorts</strong> &mdash; Taupe, Cement, Black</td><td>Top-tier</td><td>$35&ndash;$55</td><td>Literal #1 summer apparel W2C every year. Bundles with hoodie in crossover months.</td></tr>'
             '<tr><td>4</td><td>Apparel</td><td><strong>Stone Island Marina/Cargo Shorts + Compass Tee</strong></td><td>H Quality</td><td>$40&ndash;$75</td><td>Coastal-luxe aesthetic, shorts as core driver. Compass badge placement is key QC check.</td></tr>'
             '<tr><td>5</td><td>Apparel</td><td><strong>Represent Owners Club Tee + Mesh Shorts</strong></td><td>&mdash;</td><td>$40&ndash;$65</td><td>Huge velocity spring 2026. Mesh shorts are the festival/gym crossover piece.</td></tr>'
             '<tr><td>6</td><td>Sandal</td><td><strong>Birkenstock Boston Suede</strong> &mdash; Taupe, Mocha, Tobacco</td><td>GD</td><td>$55&ndash;$85</td><td>#1 unisex summer clog. Three-season carryover with summer peak.</td></tr>'
             '<tr><td>7</td><td>Sandal</td><td><strong>Herm&egrave;s Oran</strong> &mdash; gold, black, white</td><td>Top</td><td>$80&ndash;$130</td><td>RepLadies summer staple. White/gold spikes with sundress/vacation season.</td></tr>'
             '<tr><td>8</td><td>Bag</td><td><strong>LV Pochette Accessoires + Speedy 25</strong> &mdash; Monogram, Damier Azur</td><td>GP / OG Factory</td><td>$150&ndash;$240</td><td>Damier Azur is <strong>summer-coded</strong> specifically. Top RepLadies summer pick.</td></tr>'
             '<tr><td>9</td><td>Bag</td><td><strong>Chanel 22 Mini/Small</strong> &mdash; white, beige, light blue caviar</td><td>Hong Kong / Shining</td><td>$280&ndash;$420</td><td>Light colorways drive summer sell-through. Dark caviar sits through August.</td></tr>'
             '<tr><td>10</td><td>Jewelry</td><td><strong>Van Cleef Alhambra Bracelet + Necklace</strong> &mdash; MOP, malachite, onyx</td><td>ZGO / Top</td><td>$60&ndash;$140</td><td>Perennial but peaks with sundress season. High volume at low price = strong sell-through.</td></tr>'
             '<tr><td>11</td><td>Accessory</td><td><strong>Gentle Monster Sunglasses</strong> &mdash; Her, Papas, Lang</td><td>&mdash;</td><td>$45&ndash;$75</td><td>Major summer W2C driver. TikTok-heavy Her model is the volume seller.</td></tr>'
             f'<tr><td>12</td><td>Accessory</td><td><strong style="color:{gc}">Aim&eacute; Leon Dore x New Era Caps</strong> &mdash; Mets, Yankees collabs</td><td>&mdash;</td><td>$35&ndash;$55</td><td><strong>Scarce retail, high rep velocity.</strong> Quiet-luxury cap of 2026.</td></tr>'
             '</tbody></table></div>')

    # ── Tier 2: Core ──────────────────────────────────────────────────────
    p.append(_sec("Tier 2 &mdash; Core Summer Inventory (18 SKUs)", "Solid sell-through all summer. Build depth across these."))
    p.append('<div class="table-wrap"><table class="data-table"><thead><tr>'
             '<th data-sort>#</th><th data-sort>Category</th><th data-sort>Item</th>'
             '<th data-sort>Best Batch</th><th data-sort>Rep Price</th><th>Summer Signal</th>'
             '</tr></thead><tbody>'
             '<tr><td>13</td><td>Sneaker</td><td><strong>Nike Dunk Low</strong> &mdash; Panda + summer palette (Strawberry, Coast, Sail Gum)</td><td>M Batch</td><td>$70&ndash;$95</td><td>Panda evergreen; pastels specific to Apr&ndash;Jul window.</td></tr>'
             '<tr><td>14</td><td>Sneaker</td><td><strong>Jordan 4</strong> &mdash; White Thunder, Military Blue, Bred Reimagined</td><td>PK / LJR</td><td>$90&ndash;$130</td><td>White/light colorways dominate summer Jordan W2C.</td></tr>'
             '<tr><td>15</td><td>Sneaker</td><td><strong>New Balance 1906R + 530</strong> &mdash; White/Silver/Navy</td><td>H12</td><td>$75&ndash;$100</td><td>Silver/chrome y2k aesthetic peaks in summer.</td></tr>'
             '<tr><td>16</td><td>Sneaker</td><td><strong>Adidas SL72 / Gazelle Indoor</strong> &mdash; retro tones</td><td>Retro Bold / GOD</td><td>$60&ndash;$90</td><td>Indie-sleaze / blokecore. Breathable suede pairs with summer shorts.</td></tr>'
             '<tr><td>17</td><td>Sneaker</td><td><strong>Salomon XT-6</strong> &mdash; Vanilla Ice, Bleached Sand</td><td>OG</td><td>$90&ndash;$130</td><td>Gorpcore into summer festival fits.</td></tr>'
             '<tr><td>18</td><td>Sneaker</td><td><strong>Travis Scott x AJ1 Low Pink Pack</strong> (retail May 22)</td><td>LJR / PK 4.0</td><td>$110&ndash;$160</td><td>Pre-order now. Reverse-swoosh accuracy is #1 QC check.</td></tr>'
             '<tr><td>19</td><td>Apparel</td><td><strong>Corteiz Alcatraz</strong> &mdash; shorts, cargos, tees</td><td>&mdash;</td><td>$35&ndash;$60</td><td>UK streetwear carrying into US summer. Alcatraz logo is the anchor.</td></tr>'
             '<tr><td>20</td><td>Apparel</td><td><strong>Hellstar</strong> &mdash; records shorts, sport shorts, tees</td><td>&mdash;</td><td>$40&ndash;$65</td><td>Softened from 2024 peak but steady. US-market dominant.</td></tr>'
             '<tr><td>21</td><td>Apparel</td><td><strong>Arc\'teryx Atom LT / Beta SL + Aerios Tee</strong></td><td>&mdash;</td><td>$70&ndash;$120</td><td>Gorpcore + rainy-festival cover-up. Men\'s dominant.</td></tr>'
             '<tr><td>22</td><td>Apparel</td><td><strong>Denim Tears Cotton Wreath</strong> &mdash; shorts + tees</td><td>&mdash;</td><td>$50&ndash;$80</td><td>Pharrell-driven summer core.</td></tr>'
             '<tr><td>23</td><td>Apparel</td><td><strong>Polo Ralph Lauren Polo Bear + Big Pony</strong></td><td>&mdash;</td><td>$35&ndash;$55</td><td>Preppy revival / coastal grandpa aesthetic.</td></tr>'
             '<tr><td>24</td><td>Apparel</td><td><strong>LV / Dior / Gucci Swim Trunks</strong> &mdash; monogram, logo tape</td><td>&mdash;</td><td>$45&ndash;$75</td><td>Vacation-pack staple. Logo visibility = sell-through.</td></tr>'
             '<tr><td>25</td><td>Women\'s</td><td><strong>Alo Yoga</strong> &mdash; Airlift leggings, bra, Sunny tank</td><td>&mdash;</td><td>$25&ndash;$45</td><td>Top r/RepLadies velocity through summer. Pilates Princess aesthetic.</td></tr>'
             '<tr><td>26</td><td>Women\'s</td><td><strong>Lululemon Align</strong> tanks + Everywhere Belt Bag</td><td>&mdash;</td><td>$20&ndash;$45</td><td>Entry-price rep driving volume, not margin.</td></tr>'
             '<tr><td>27</td><td>Bag</td><td><strong>Goyard St. Louis / Anjou Tote</strong></td><td>&mdash;</td><td>$130&ndash;$200</td><td>Beach / vacation tote. Chevron print is the visual hook.</td></tr>'
             '<tr><td>28</td><td>Bag</td><td><strong>Dior Book Tote Small</strong></td><td>&mdash;</td><td>$180&ndash;$280</td><td>Vacation bag for RepLadies. Oblique colorways for summer.</td></tr>'
             '<tr><td>29</td><td>Jewelry</td><td><strong>Cartier Love + Juste un Clou Bracelets</strong></td><td>ZGO / Top</td><td>$70&ndash;$160</td><td>Summer wrist-stack demand. 18k-plated versions are the volume tier.</td></tr>'
             '<tr><td>30</td><td>Sandal</td><td><strong>Adidas Adilette 22</strong> + classic Adilette</td><td>&mdash;</td><td>$25&ndash;$45</td><td>Pure volume seller. Pair with Essentials shorts fits.</td></tr>'
             '</tbody></table></div>')

    # ── Tier 3: Watch ─────────────────────────────────────────────────────
    p.append(_sec("Tier 3 &mdash; Watch List (10 SKUs)", "Emerging or niche. Test in small quantities."))
    p.append(_exp(f'<strong style="color:{ac}">Sample 5&ndash;10 units before going deep.</strong> These have real signal but are earlier in the curve or more niche.', "amber"))
    p.append('<div class="table-wrap"><table class="data-table"><thead><tr>'
             '<th data-sort>#</th><th data-sort>Category</th><th data-sort>Item</th>'
             '<th data-sort>Rep Price</th><th>Why Watch</th>'
             '</tr></thead><tbody>'
             '<tr><td>31</td><td>Sneaker</td><td><strong>Puma Speedcat / Mostro</strong></td><td>$60&ndash;$85</td><td>Low-profile trainer trend breaking through. Bella Hadid / Miu Miu halo.</td></tr>'
             '<tr><td>32</td><td>Sneaker</td><td><strong>Onitsuka Tiger Mexico 66</strong></td><td>$55&ndash;$80</td><td>Blokecore + Kill Bill revival. Stable, not explosive.</td></tr>'
             '<tr><td>33</td><td>Sneaker</td><td><strong>Nike V2K Run / P-6000</strong></td><td>$75&ndash;$100</td><td>Y2K chrome continuation. P-6000 is #1 Weidian seller (see March report).</td></tr>'
             '<tr><td>34</td><td>Bag</td><td><strong>Prada Raffia Tote / Loewe Basket Bag</strong></td><td>$140&ndash;$220</td><td>Tomato-girl / coastal aesthetic driver. Women\'s summer-only.</td></tr>'
             '<tr><td>35</td><td>Bag</td><td><strong>Pol&egrave;ne Numero Un Nano</strong></td><td>$130&ndash;$200</td><td>Rising quiet-luxury pick. TikTok-driven, low rep stigma.</td></tr>'
             '<tr><td>36</td><td>Sandal</td><td><strong>The Row Ginza Sandal Dupes</strong> (Taobao direct)</td><td>$80&ndash;$130</td><td>Emerging quiet-luxury sandal. Low-branded = QC on materials critical.</td></tr>'
             '<tr><td>37</td><td>Sandal</td><td><strong>Margiela Tabi Mary Janes + Tabi Flats</strong></td><td>$90&ndash;$140</td><td>Year-round but summer color pack spikes.</td></tr>'
             '<tr><td>38</td><td>Apparel</td><td><strong>Rhude Shorts</strong> &mdash; logo, basketball</td><td>$55&ndash;$85</td><td>Still moves but decelerating. Good margin if priced right.</td></tr>'
             '<tr><td>39</td><td>Apparel</td><td><strong>Aim&eacute; Leon Dore Tees + Rugby Shirts</strong></td><td>$40&ndash;$70</td><td>Quiet-luxury core, overlaps cap demand (Tier 1 #12).</td></tr>'
             '<tr><td>40</td><td>Accessory</td><td><strong>Miu Miu Sunglasses + Arc Logo Cap</strong></td><td>$45&ndash;$70</td><td>TikTok-driven. Women\'s heavy.</td></tr>'
             '</tbody></table></div>')

    # ── Macro trends ──────────────────────────────────────────────────────
    p.append(_sec("6 Summer Macro Trends Driving This List"))
    p.append(f'<div class="action-box"><div class="action-title" style="color:{bc}">1. Coastal grandpa + quiet luxury holdover</div>'
             f'<p style="font-size:0.85rem;color:var(--text-secondary);margin:4px 0 0">Aim&eacute; Leon Dore caps, Loro Piana loafers/polos, The Row sandals, Polo RL. '
             f'Drives neutral linen, boat-shoe silhouettes, gold jewelry. Older affluent buyers.</p></div>')
    p.append(f'<div class="action-box"><div class="action-title" style="color:{rc}">2. Tomato girl / Euro summer</div>'
             f'<p style="font-size:0.85rem;color:var(--text-secondary);margin:4px 0 0">Raffia / straw totes, red-white gingham, Mediterranean aesthetic. '
             f'Drives Prada raffia, Loewe basket, white linen shirts, gold Alhambra jewelry stacks. Women\'s-heavy.</p></div>')
    p.append(f'<div class="action-box"><div class="action-title" style="color:{gc}">3. Blokecore 2.0 / terrace revival</div>'
             f'<p style="font-size:0.85rem;color:var(--text-secondary);margin:4px 0 0">Retro football jerseys (Arsenal, Barca), Sambas, Gazelle Indoor, adidas track shorts. '
             f'Stock one or two marquee club jerseys (cheap on Taobao) as an impulse add-on.</p></div>')
    p.append(f'<div class="action-box"><div class="action-title" style="color:{pc}">4. Gorpcore light into summer</div>'
             f'<p style="font-size:0.85rem;color:var(--text-secondary);margin:4px 0 0">Salomon XT-6, Arc\'teryx Atom LT, HOKA. Festival + hiking crossover. '
             f'Lightweight shells sell through rainy festivals (Bonnaroo, Glastonbury).</p></div>')
    p.append(f'<div class="action-box"><div class="action-title" style="color:{ac}">5. Y2K chrome / silver</div>'
             f'<p style="font-size:0.85rem;color:var(--text-secondary);margin:4px 0 0">NB 530/1906R silver, metallic bags, Oakley revival. '
             f'Pair with dark denim shorts &amp; cropped tees &mdash; Gen Z summer uniform.</p></div>')
    p.append(f'<div class="action-box"><div class="action-title" style="color:{cc}">6. Pilates Princess / clean girl</div>'
             f'<p style="font-size:0.85rem;color:var(--text-secondary);margin:4px 0 0">Alo, Lulu, minimal Van Cleef / Cartier jewelry, white sneakers, Herm&egrave;s Oran. '
             f'Highest-ROI women\'s segment entering summer. Bundle Alo tank + Align leggings + belt bag.</p></div>')

    # ── Action summary ────────────────────────────────────────────────────
    p.append(_sec("Summer Stocking Strategy &mdash; How to Deploy Capital"))
    p.append(_exp(
        "<strong>Suggested split for a $5k summer budget:</strong> "
        "<strong>50% Tier 1</strong> ($2500 across 12 SKUs, ~$200 each &ndash; 2&ndash;4 units per SKU). "
        "<strong>35% Tier 2</strong> ($1750 across 18 SKUs, ~$100 each &ndash; 1&ndash;2 units per SKU). "
        "<strong>10% Tier 3 testing</strong> ($500 across 5&ndash;8 samples). "
        "<strong>5% reserve</strong> for Travis Scott Pink Pack pre-order spike late May.", "green"))
    p.append(_exp(
        "<strong>Gaps vs. your existing dashboard:</strong> "
        "Your current Unmet Demand table is weighted toward year-round items. "
        "Summer-specific SKUs missing / underweighted: "
        "<strong>Birkenstock Boston</strong>, <strong>Herm&egrave;s Oran</strong>, <strong>Damier Azur LV</strong>, "
        "<strong>Gentle Monster sunnies</strong>, <strong>Alhambra jewelry</strong>, <strong>ALD New Era caps</strong>, "
        "<strong>Represent mesh shorts</strong>, <strong>raffia/straw bags</strong>. "
        "These are worth stocking even if they don\'t show high Discord signal yet &mdash; they trend externally first.", "amber"))

    p.append(f'<p style="font-size:0.72rem;color:var(--text-muted);margin-top:24px">'
             f'Researched April 24, 2026. Valid through ~Aug 31, 2026. Sources: r/FashionReps, r/Repsneakers, '
             f'r/DesignerReps, r/QualityReps, r/RepLadies, r/WeidianWarriors, r/CloseToRetail, TikTok trend aggregators, '
             f'JadeShip live Weidian sales, Mulebuy / AllChinaBuy haul feeds.</p>')
    p.append("</div>")
    return "\n".join(p)


def _tab_signals(D):
    bc, gc, rc, ac = C["blue"], C["green"], C["red"], C["amber"]
    p = ['<div class="page-content">']
    p.append(_exp(
        "<strong>Four types of demand signals:</strong><br>"
        f'<strong style="color:{bc}">Requests</strong> -- Actively looking to buy.<br>'
        f'<strong style="color:{gc}">Satisfaction</strong> -- Positive reviews.<br>'
        f'<strong style="color:{rc}">Regret</strong> -- Wish they had bought it.<br>'
        f'<strong style="color:{ac}">Ownership</strong> -- Just received it.'))
    p.append('<div class="two-col"><div>')
    p.append(_sec("Most Requested (People Want These)"))
    p.append('<div id="wrap-tbl-req">')
    p.append(_table(D["req"][:15], {
        "brand": "Brand", "item": "Item", "count": "Requests", "avg_score": "Strength"}))
    p.append('</div>')
    p.append("</div><div>")
    p.append(_sec("Most Loved (High Satisfaction)"))
    p.append('<div id="wrap-tbl-sat">')
    p.append(_table(D["sat"][:15], {
        "brand": "Brand", "item": "Item", "count": "Reviews", "avg_score": "Strength"}))
    p.append('</div>')
    p.append("</div></div>")
    p.append('<div class="two-col"><div>')
    p.append(_sec("Missed Opportunities (Regret)"))
    p.append(_exp(
        "High regret = people want these but missed out. "
        "Stock them to capture pent-up demand.", "red"))
    p.append('<div id="wrap-tbl-reg">')
    p.append(_table(D["reg"][:15], {
        "brand": "Brand", "item": "Item", "count": "Regret Mentions", "avg_score": "Strength"}))
    p.append('</div>')
    p.append("</div><div>")
    p.append(_sec("Recently Purchased (Ownership)"))
    p.append(_exp(
        "Items people are actively buying. High ownership + high satisfaction "
        "= safe to keep stocking.", "green"))
    p.append('<div id="wrap-tbl-own">')
    p.append(_table(D["own"][:15], {
        "brand": "Brand", "item": "Item", "count": "Purchases", "avg_score": "Strength"}))
    p.append('</div>')
    p.append("</div></div></div>")
    return "\n".join(p)


# ── Page assembly ─────────────────────────────────────────────────────────

JS = r"""
// Tab switching
document.querySelectorAll('#tabs .tab').forEach(btn=>{
  btn.addEventListener('click',()=>{
    document.querySelectorAll('#tabs .tab').forEach(b=>b.classList.remove('tab--selected'));
    document.querySelectorAll('.tab-panel').forEach(p=>p.style.display='none');
    btn.classList.add('tab--selected');
    document.getElementById('tab-'+btn.dataset.tab).style.display='';
  });
});

// Render charts for current timeframe
function renderCharts(tf) {
  const figs = DATA[tf].figures;
  Object.entries(figs).forEach(([id,fig])=>{
    const el=document.getElementById(id);
    if(el)Plotly.react(el,fig.data,fig.layout,{displayModeBar:false,responsive:true});
  });
}

// Update KPIs
function updateKPIs(tf) {
  const kpis = DATA[tf].kpis;
  document.querySelectorAll('[data-kpi]').forEach(el=>{
    const key = el.dataset.kpi;
    if(kpis[key] !== undefined) el.textContent = kpis[key];
  });
  // Header stats
  const hs = document.querySelectorAll('.header-stat .num');
  if(hs[0]) hs[0].textContent = kpis.msgs || '';
  if(hs[1]) hs[1].textContent = kpis.mentions || '';
  if(hs[2]) hs[2].textContent = kpis.brands || '';
}

// Update tables
function updateTables(tf) {
  const tables = DATA[tf].tables;
  Object.entries(tables).forEach(([id,html])=>{
    const el = document.getElementById('wrap-'+id);
    if(el) el.innerHTML = html;
  });
  // Update actions
  const actEl = document.getElementById('act-overview');
  if(actEl && DATA[tf].actions !== undefined) actEl.innerHTML = DATA[tf].actions;
  // Re-bind sort handlers
  bindSortHandlers();
}

// Timeframe change handler
function switchTimeframe(tf) {
  updateKPIs(tf);
  renderCharts(tf);
  updateTables(tf);
}

// Timeframe dropdown
const tfSelect = document.getElementById('tf-select');
if(tfSelect) {
  tfSelect.addEventListener('change', function() {
    switchTimeframe(this.value);
  });
}

// Item search
const si=document.getElementById('item-search');
if(si){si.addEventListener('input',e=>{
  const t=e.target.value.toLowerCase();
  const tbody = document.getElementById('items-tbody');
  if(!tbody) return;
  Array.from(tbody.rows).forEach(r=>{
    r.style.display=r.textContent.toLowerCase().includes(t)?'':'none';
  });
});}

// Table sorting
function bindSortHandlers() {
  document.querySelectorAll('th[data-sort]').forEach(th=>{
    if(th._sortBound) return;
    th._sortBound = true;
    th.addEventListener('click',()=>{
      const tb=th.closest('table').querySelector('tbody');
      const rows=Array.from(tb.rows);
      const i=Array.from(th.parentNode.children).indexOf(th);
      const asc=th.dataset.dir!=='asc';th.dataset.dir=asc?'asc':'desc';
      rows.sort((a,b)=>{
        const av=a.cells[i]?.textContent||'',bv=b.cells[i]?.textContent||'';
        const an=parseFloat(av),bn=parseFloat(bv);
        if(!isNaN(an)&&!isNaN(bn))return asc?an-bn:bn-an;
        return asc?av.localeCompare(bv):bv.localeCompare(av);
      });
      rows.forEach(r=>tb.appendChild(r));
    });
  });
}

// Initial render
renderCharts('all');
bindSortHandlers();
"""


def _build_page(all_data, default_data):
    """Build the full HTML page with all timeframe data embedded."""
    tabs = [
        ("overview", "Overview", _tab_overview(default_data)),
        ("stock", "What to Stock", _tab_stock(default_data)),
        ("customers", "Customer Insights", _tab_customers(default_data)),
        ("explorer", "Item Explorer", _tab_explorer(default_data)),
        ("trends", "Market Trends", _tab_trends(default_data)),
        ("channels", "Channel Analysis", _tab_channels(default_data)),
        ("signals", "Demand Signals", _tab_signals(default_data)),
        ("report", "Market Report", _tab_market_report(default_data)),
        ("summer", "Summer 2026", _tab_summer(default_data)),
        ("niche", "Niche Picks", _tab_niche(default_data)),
        ("bst", "BST Resale ROI", _tab_bst(default_data)),
    ]
    nav = ""
    for i, (tid, label, _) in enumerate(tabs):
        cls = "tab tab--selected" if i == 0 else "tab"
        nav += f'<button class="{cls}" data-tab="{tid}">{label}</button>'
    panels = ""
    for i, (tid, _, content) in enumerate(tabs):
        disp = "" if i == 0 else ' style="display:none"'
        panels += f'<section id="tab-{tid}" class="tab-panel"{disp}>\n{content}\n</section>\n'

    tf_options = ""
    for tf_key, _ in TIMEFRAMES:
        label = "All Time" if tf_key == "all" else tf_key.upper().replace("D", " Days")
        sel = " selected" if tf_key == "all" else ""
        tf_options += f'<option value="{tf_key}"{sel}>{label}</option>'

    data_json = json.dumps(all_data, separators=(",", ":"))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>ZR ItemFinder &mdash; Demand Intelligence</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/style.css">
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js" charset="utf-8"></script>
</head>
<body>
<header class="site-header">
<div><h1>ZR ItemFinder</h1><div class="subtitle">Demand Intelligence for Resellers</div></div>
<div style="display:flex;align-items:center;gap:12px">
<select id="tf-select" style="padding:8px 12px;border-radius:8px;border:1px solid var(--border);background:var(--bg-surface);color:var(--text-primary);font-size:0.85rem;font-family:inherit;cursor:pointer">
{tf_options}
</select>
</div>
<div class="header-stats">
<div class="header-stat"><div class="num">{default_data["raw"]:,}</div><div class="lbl">Messages</div></div>
<div class="header-stat"><div class="num">{default_data["mentions"]:,}</div><div class="lbl">Mentions</div></div>
<div class="header-stat"><div class="num">{default_data["n_brands"]}</div><div class="lbl">Brands</div></div>
</div>
</header>
<nav class="custom-tabs" id="tabs">{nav}</nav>
{panels}
<footer style="border-top:1px solid var(--border);margin-top:32px">
<p style="color:var(--text-muted);font-size:0.75rem;text-align:center;padding:20px 0">
ZR ItemFinder v1.1 &mdash; Data from Discord + Reddit community analysis</p>
</footer>
<script>const DATA={data_json};{JS}</script>
</body>
</html>"""


# ── Build command ─────────────────────────────────────────────────────────

def build():
    log.info("Loading data for all timeframes...")
    now = datetime.now()

    all_tf_data = {}
    default_data = None

    for tf_key, days in TIMEFRAMES:
        since = (now - timedelta(days=days)).isoformat() if days else None
        label = tf_key
        log.info(f"  Loading {label}...")
        D = _load(since)

        figures = _build_figures(D)
        tables = _build_tables(D)
        kpis = _build_kpis(D)
        actions_html = _act("Top Actions Based on Your Data", _build_actions(D))

        all_tf_data[tf_key] = {
            "figures": figures,
            "tables": tables,
            "kpis": kpis,
            "actions": actions_html,
        }

        if tf_key == "all":
            default_data = D

    log.info(f"  {sum(len(v['figures']) for v in all_tf_data.values())} total charts across {len(TIMEFRAMES)} timeframes")

    log.info("Generating HTML...")
    html = _build_page(all_tf_data, default_data)

    DIST.mkdir(parents=True, exist_ok=True)
    (DIST / "assets").mkdir(exist_ok=True)
    (DIST / "index.html").write_text(html, encoding="utf-8")
    shutil.copy(ASSETS_SRC / "style.css", DIST / "assets" / "style.css")

    size_kb = len(html.encode("utf-8")) / 1024
    log.info(f"Static site built => {DIST}/ ({size_kb:.0f} KB)")
    log.info(f"Deploy with: npx wrangler pages deploy {DIST} --project-name=zr-itemfinder")


if __name__ == "__main__":
    build()
