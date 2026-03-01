"""Generate output files: report.md, items.csv, brands.csv, insights.json.

Usage: python -m src.report.generate_report
"""

import csv
import json
from pathlib import Path

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

    # Top 10 Requested Items
    lines += ["## Top 10 Most Requested Items", ""]
    lines.append("| # | Brand | Item | Request Count | Avg Score |")
    lines.append("|---|-------|------|---------------|-----------|")
    for i, r in enumerate(top_requested[:10], 1):
        lines.append(
            f"| {i} | {r['brand'] or '—'} | {r['item'] or '—'} "
            f"| {r['count']} | {r['avg_score']:.2f} |"
        )
    lines.append("")

    # Missed Opportunities
    lines += ["## Top Missed Opportunities (Regret Mentions)", ""]
    lines.append("| # | Brand | Item | Regret Count | Avg Score |")
    lines.append("|---|-------|------|--------------|-----------|")
    for i, r in enumerate(missed_opps[:10], 1):
        lines.append(
            f"| {i} | {r['brand'] or '—'} | {r['item'] or '—'} "
            f"| {r['count']} | {r['avg_score']:.2f} |"
        )
    lines.append("")

    # Most Loved
    lines += ["## Most Loved Items (Satisfaction Mentions)", ""]
    lines.append("| # | Brand | Item | Satisfaction Count | Avg Score |")
    lines.append("|---|-------|------|--------------------|-----------|")
    for i, r in enumerate(most_loved[:10], 1):
        lines.append(
            f"| {i} | {r['brand'] or '—'} | {r['item'] or '—'} "
            f"| {r['count']} | {r['avg_score']:.2f} |"
        )
    lines.append("")

    # Trending Now
    lines += ["## Trending Now (Velocity-Based)", ""]
    lines.append("| # | Brand | Item | Recent | Previous | Velocity |")
    lines.append("|---|-------|------|--------|----------|----------|")
    for i, r in enumerate(trending[:10], 1):
        lines.append(
            f"| {i} | {r['brand']} | {r['item']} "
            f"| {r['recent_mentions']} | {r['prev_mentions']} | {r['velocity']:+.1f}x |"
        )
    lines.append("")

    # Top Brands
    lines += ["## Top Brands by Trend Score", ""]
    lines.append("| # | Brand | Mentions | Avg Intent | Trend Score |")
    lines.append("|---|-------|----------|------------|-------------|")
    for i, b in enumerate(brand_scores[:15], 1):
        lines.append(
            f"| {i} | {b['brand']} | {b['mentions']} "
            f"| {b['avg_intent']:.3f} | {b['trend_score']:.3f} |"
        )
    lines.append("")

    # Channel Breakdown
    lines += ["## Channel Breakdown", ""]
    lines.append("| Channel | Total | Requests | Satisfaction | Regret | Ownership |")
    lines.append("|---------|-------|----------|-------------|--------|-----------|")
    for ch in channels[:15]:
        lines.append(
            f"| {ch['channel']} | {ch['total']} | {ch['requests']} "
            f"| {ch['satisfaction']} | {ch['regret']} | {ch['ownership']} |"
        )
    lines.append("")

    # Key Insights
    lines += [
        "## Key Insights",
        "",
    ]

    if top_requested:
        top = top_requested[0]
        lines.append(
            f"- **Highest demand:** {top['brand'] or 'Various'} {top['item'] or 'items'} "
            f"with {top['count']} request mentions"
        )

    if missed_opps:
        top = missed_opps[0]
        lines.append(
            f"- **Biggest missed opportunity:** {top['brand'] or 'Various'} {top['item'] or 'items'} "
            f"— users regret not buying ({top['count']} mentions)"
        )

    if most_loved:
        top = most_loved[0]
        lines.append(
            f"- **Most loved:** {top['brand'] or 'Various'} {top['item'] or 'items'} "
            f"with {top['count']} satisfaction mentions"
        )

    if brand_scores:
        lines.append(
            f"- **Most discussed brand:** {brand_scores[0]['brand']} "
            f"({brand_scores[0]['mentions']} mentions)"
        )

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
