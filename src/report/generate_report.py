"""Generate output files: report.md, items.csv, brands.csv, insights.json.

Usage: python -m src.report.generate_report
"""

import csv
import json
from pathlib import Path

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
    top_items_by_intent,
    trending_items,
)
from src.common.config import OUT_DIR
from src.common.db import get_connection, processed_mention_count, raw_message_count
from src.common.log_util import get_logger
from src.process.scoring import compute_brand_scores, compute_item_scores

log = get_logger("report")


def _ensure_out_dir():
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_items_csv(item_scores: list[dict]) -> Path:
    path = OUT_DIR / "items.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "brand", "item", "variant", "total_mentions",
            "request_count", "satisfaction_count", "regret_count",
            "ownership_count", "velocity", "final_score",
        ])
        writer.writeheader()
        for row in item_scores:
            writer.writerow({k: row[k] for k in writer.fieldnames})
    log.info(f"Wrote {len(item_scores)} rows to {path}")
    return path


def generate_brands_csv(brand_scores: list[dict]) -> Path:
    path = OUT_DIR / "brands.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "brand", "mentions", "avg_intent", "trend_score",
        ])
        writer.writeheader()
        for row in brand_scores:
            writer.writerow(row)
    log.info(f"Wrote {len(brand_scores)} rows to {path}")
    return path


def generate_insights_json(conn, item_scores: list[dict]) -> Path:
    path = OUT_DIR / "insights.json"

    top_requested = top_items_by_intent(conn, "request", 15)
    missed_opps = top_items_by_intent(conn, "regret", 15)
    most_loved = top_items_by_intent(conn, "satisfaction", 15)
    trending = trending_items(conn, 20)
    unmet = unmet_demand(conn, 3)
    sizes = size_demand(conn)
    colors = color_demand(conn)
    cross = brand_cross_sell(conn, 10)
    inv_recs = inventory_recommendations(conn)

    insights = {
        "top_requested": [
            {"brand": r["brand"], "item": r["item"], "count": r["count"]}
            for r in top_requested
        ],
        "missed_opportunities": [
            {"brand": r["brand"], "item": r["item"], "count": r["count"]}
            for r in missed_opps
        ],
        "most_loved": [
            {"brand": r["brand"], "item": r["item"], "count": r["count"]}
            for r in most_loved
        ],
        "trending_now": [
            {"brand": r["brand"], "item": r["item"],
             "velocity": r["velocity"], "recent": r["recent_mentions"]}
            for r in trending
        ],
        "unmet_demand": [
            {"brand": u["brand"], "item": u["item"],
             "requests": u["requests"], "owned": u["owned"],
             "demand_gap": u["demand_gap"]}
            for u in unmet[:20]
        ],
        "size_demand": sizes[:15],
        "color_demand": colors[:10],
        "cross_sell_pairs": [
            {"brand_a": c["brand_a"], "brand_b": c["brand_b"],
             "shared_users": c["shared_users"]}
            for c in cross[:15]
        ],
        "inventory_recommendations": [
            {"brand": r["brand"], "item": r["item"],
             "priority": r["priority"], "demand_gap": r["demand_gap"],
             "notes": r["notes"]}
            for r in inv_recs[:15]
        ],
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(insights, f, indent=2, ensure_ascii=False)
    log.info(f"Wrote insights to {path}")
    return path


def generate_report_md(conn, item_scores: list[dict],
                       brand_scores: list[dict]) -> Path:
    path = OUT_DIR / "report.md"
    total_raw = raw_message_count(conn)
    total_processed = processed_mention_count(conn)
    channels = channel_breakdown(conn)
    trending = trending_items(conn, 10)
    top_requested = top_items_by_intent(conn, "request", 10)
    missed_opps = top_items_by_intent(conn, "regret", 10)
    most_loved = top_items_by_intent(conn, "satisfaction", 10)

    # Sales intelligence
    unmet = unmet_demand(conn, 3)
    profiles = buyer_profiles(conn, 20)
    cross = brand_cross_sell(conn, 10)
    sizes = size_demand(conn)
    colors = color_demand(conn)
    inv_recs = inventory_recommendations(conn)
    seasonality = monthly_seasonality(conn)
    conversions = conversion_tracking(conn)

    lines = [
        "# Demand Intelligence Report",
        "",
        "## Executive Summary",
        "",
        f"- **Total messages analyzed:** {total_raw:,}",
        f"- **Actionable mentions extracted:** {total_processed:,}",
        f"- **Unique brands detected:** {len(brand_scores)}",
        f"- **Unique item combinations:** {len(item_scores)}",
        f"- **Channels analyzed:** {len(channels)}",
        "",
    ]

    # ---------------------------------------------------------------
    # SECTION 1: Top Requested
    # ---------------------------------------------------------------
    lines += ["## Top 10 Most Requested Items", ""]
    lines.append("| # | Brand | Item | Request Count | Avg Score |")
    lines.append("|---|-------|------|---------------|-----------|")
    for i, r in enumerate(top_requested[:10], 1):
        lines.append(
            f"| {i} | {r['brand'] or '---'} | {r['item'] or '---'} "
            f"| {r['count']} | {r['avg_score']:.2f} |"
        )
    lines.append("")

    # ---------------------------------------------------------------
    # SECTION 2: Top Brand+Item Combos (most actionable)
    # ---------------------------------------------------------------
    lines += ["## Top Brand + Item Combos Requested", ""]
    lines.append("| # | Brand | Item | Requests | Owned | Demand Gap |")
    lines.append("|---|-------|------|----------|-------|------------|")
    brand_items = [u for u in unmet if u["brand"] != "Various" and u["item"] != "general"]
    for i, u in enumerate(brand_items[:15], 1):
        lines.append(
            f"| {i} | {u['brand']} | {u['item']} "
            f"| {u['requests']} | {u['owned']} | {u['demand_gap']} |"
        )
    lines.append("")

    # ---------------------------------------------------------------
    # SECTION 3: Unmet Demand (stock these!)
    # ---------------------------------------------------------------
    lines += ["## Unmet Demand -- Items to Stock", "",
              "*Items people are requesting but almost nobody owns yet.*", ""]
    lines.append("| # | Brand | Item | Requests | Owned | Gap | Unique Users |")
    lines.append("|---|-------|------|----------|-------|-----|--------------|")
    for i, u in enumerate(unmet[:15], 1):
        lines.append(
            f"| {i} | {u['brand']} | {u['item']} "
            f"| {u['requests']} | {u['owned']} | {u['demand_gap']} | {u['unique_requesters']} |"
        )
    lines.append("")

    # ---------------------------------------------------------------
    # SECTION 4: Inventory Recommendations
    # ---------------------------------------------------------------
    lines += ["## Inventory Recommendations", ""]
    lines.append("| Priority | Brand | Item | Demand Gap | Notes |")
    lines.append("|----------|-------|------|------------|-------|")
    for r in inv_recs[:15]:
        lines.append(
            f"| **{r['priority']}** | {r['brand']} | {r['item']} "
            f"| {r['demand_gap']} | {r['notes']} |"
        )
    lines.append("")

    # ---------------------------------------------------------------
    # SECTION 5: Size & Color Demand
    # ---------------------------------------------------------------
    lines += ["## Size Demand", ""]
    lines.append("| Size | Total | Requests | Owned |")
    lines.append("|------|-------|----------|-------|")
    for s in sizes[:12]:
        lines.append(f"| {s['size']} | {s['total']} | {s['requests']} | {s['owned']} |")
    lines.append("")

    lines += ["## Color Demand", ""]
    lines.append("| Color | Total | Requests | Owned |")
    lines.append("|-------|-------|----------|-------|")
    for c in colors[:12]:
        lines.append(f"| {c['color']} | {c['total']} | {c['requests']} | {c['owned']} |")
    lines.append("")

    # ---------------------------------------------------------------
    # SECTION 6: Cross-Sell Pairs
    # ---------------------------------------------------------------
    lines += ["## Cross-Sell Opportunities", "",
              "*Brands frequently discussed by the same users. If someone buys Brand A, "
              "they likely want Brand B too.*", ""]
    lines.append("| Brand A | Brand B | Shared Users |")
    lines.append("|---------|---------|--------------|")
    for c in cross[:15]:
        lines.append(f"| {c['brand_a']} | {c['brand_b']} | {c['shared_users']} |")
    lines.append("")

    # ---------------------------------------------------------------
    # SECTION 7: Top Buyer Profiles
    # ---------------------------------------------------------------
    lines += ["## Top Buyer Profiles", ""]
    lines.append("| User | Segment | Requests | Owned | Buy Ratio | Top Brands |")
    lines.append("|------|---------|----------|-------|-----------|------------|")
    for p in profiles[:20]:
        brand_str = ", ".join(b["brand"] for b in p["top_brands"][:3])
        lines.append(
            f"| {p['user']} | {p['segment']} | {p['requests']} "
            f"| {p['owned']} | {p['buy_ratio']:.2f} | {brand_str} |"
        )
    lines.append("")

    # ---------------------------------------------------------------
    # SECTION 8: Conversions
    # ---------------------------------------------------------------
    lines += ["## Conversion Tracking (Request -> Purchase)", "",
              "*Users who requested a brand and later showed ownership.*", ""]
    lines.append("| User | Brand | Requested | Owned | Satisfied |")
    lines.append("|------|-------|-----------|-------|-----------|")
    for c in conversions[:15]:
        lines.append(
            f"| {c['author']} | {c['brand']} "
            f"| {c['requests']} | {c['owned']} | {c['satisfied']} |"
        )
    lines.append("")

    # ---------------------------------------------------------------
    # SECTION 9: Most Loved / Satisfaction
    # ---------------------------------------------------------------
    lines += ["## Most Loved Items", ""]
    lines.append("| # | Brand | Item | Satisfaction Count | Avg Score |")
    lines.append("|---|-------|------|--------------------|-----------|")
    for i, r in enumerate(most_loved[:10], 1):
        lines.append(
            f"| {i} | {r['brand'] or '---'} | {r['item'] or '---'} "
            f"| {r['count']} | {r['avg_score']:.2f} |"
        )
    lines.append("")

    # ---------------------------------------------------------------
    # SECTION 10: Trending Now
    # ---------------------------------------------------------------
    lines += ["## Trending Now (Velocity-Based)", ""]
    lines.append("| # | Brand | Item | Recent | Previous | Velocity |")
    lines.append("|---|-------|------|--------|----------|----------|")
    for i, r in enumerate(trending[:10], 1):
        lines.append(
            f"| {i} | {r['brand']} | {r['item']} "
            f"| {r['recent_mentions']} | {r['prev_mentions']} | {r['velocity']:+.1f}x |"
        )
    lines.append("")

    # ---------------------------------------------------------------
    # SECTION 11: Top Brands
    # ---------------------------------------------------------------
    lines += ["## Top Brands by Trend Score", ""]
    lines.append("| # | Brand | Mentions | Avg Intent | Trend Score |")
    lines.append("|---|-------|----------|------------|-------------|")
    for i, b in enumerate(brand_scores[:20], 1):
        lines.append(
            f"| {i} | {b['brand']} | {b['mentions']} "
            f"| {b['avg_intent']:.3f} | {b['trend_score']:.3f} |"
        )
    lines.append("")

    # ---------------------------------------------------------------
    # SECTION 12: Seasonality
    # ---------------------------------------------------------------
    lines += ["## Monthly Activity", ""]
    lines.append("| Month | Total | Requests | Owned | Unique Users |")
    lines.append("|-------|-------|----------|-------|--------------|")
    for s in seasonality:
        lines.append(
            f"| {s['month']} | {s['total']} | {s['requests']} "
            f"| {s['owned']} | {s['unique_users']} |"
        )
    lines.append("")

    # ---------------------------------------------------------------
    # SECTION 13: Channel Breakdown
    # ---------------------------------------------------------------
    lines += ["## Channel Breakdown", ""]
    lines.append("| Channel | Total | Requests | Satisfaction | Regret | Ownership |")
    lines.append("|---------|-------|----------|-------------|--------|-----------|")
    for ch in channels[:15]:
        lines.append(
            f"| {ch['channel']} | {ch['total']} | {ch['requests']} "
            f"| {ch['satisfaction']} | {ch['regret']} | {ch['ownership']} |"
        )
    lines.append("")

    # ---------------------------------------------------------------
    # Key Takeaways
    # ---------------------------------------------------------------
    lines += ["## Key Takeaways", ""]

    if brand_items:
        top3 = brand_items[:3]
        lines.append("**Top 3 items to stock immediately:**")
        for t in top3:
            lines.append(f"- {t['brand']} {t['item']} ({t['demand_gap']} unmet requests)")
        lines.append("")

    if sizes:
        top_sz = [s["size"] for s in sizes[:3]]
        lines.append(f"**Most requested sizes:** {', '.join(top_sz)}")
        lines.append("")

    if colors:
        top_cl = [c["color"] for c in colors[:3]]
        lines.append(f"**Most requested colors:** {', '.join(top_cl)}")
        lines.append("")

    if cross:
        lines.append("**Cross-sell insight:** customers who buy "
                      f"{cross[0]['brand_a']} also want {cross[0]['brand_b']} "
                      f"({cross[0]['shared_users']} users overlap)")
        lines.append("")

    if profiles:
        loyal = [p for p in profiles if p["segment"] == "loyal_buyer"]
        prospects = [p for p in profiles if p["segment"] == "high_intent_prospect"]
        if loyal:
            lines.append(f"**Loyal buyers (high conversion):** "
                          f"{', '.join(p['user'] for p in loyal[:5])}")
        if prospects:
            lines.append(f"**High-intent prospects (many requests, low purchases):** "
                          f"{', '.join(p['user'] for p in prospects[:5])}")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info(f"Wrote report to {path}")
    return path


def generate_all():
    """Generate all output files."""
    _ensure_out_dir()
    conn = get_connection()

    log.info("Computing item scores...")
    item_scores = compute_item_scores(conn)

    log.info("Computing brand scores...")
    brand_scores = compute_brand_scores(conn)

    log.info("Generating outputs...")
    generate_items_csv(item_scores)
    generate_brands_csv(brand_scores)
    generate_insights_json(conn, item_scores)
    generate_report_md(conn, item_scores, brand_scores)

    conn.close()
    log.info("All outputs generated in ./out/")


if __name__ == "__main__":
    generate_all()
