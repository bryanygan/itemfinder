"""Scoring system: compute demand scores for items and brands."""

import sqlite3
from datetime import datetime, timedelta

from src.common.config import (
    CHANNEL_WEIGHTS,
    DEFAULT_CHANNEL_WEIGHT,
    FINAL_SCORE_WEIGHTS,
    INTENT_WEIGHTS,
    TREND_WINDOW_DAYS,
)
from src.common.db import get_connection
from src.common.log_util import get_logger

log = get_logger("scoring")


def _channel_weight(channel: str) -> float:
    ch = channel.lower().strip()
    for key, weight in CHANNEL_WEIGHTS.items():
        if key in ch:
            return weight
    return DEFAULT_CHANNEL_WEIGHT


def compute_item_scores(conn: sqlite3.Connection,
                        since: str | None = None) -> list[dict]:
    """Compute final demand score for every (brand, item) pair."""

    since_clause = " AND timestamp >= ?" if since else ""
    params = [since] if since else []
    rows = conn.execute(f"""
        SELECT brand, item, variant, intent_type, intent_score, channel, timestamp
        FROM processed_mentions
        WHERE (brand IS NOT NULL OR item IS NOT NULL)
        {since_clause}
    """, params).fetchall()

    if not rows:
        log.warning("No processed mentions to score")
        return []

    # Find the latest timestamp for trend calculation
    max_ts_row = conn.execute(
        "SELECT MAX(timestamp) FROM processed_mentions"
        + (" WHERE timestamp >= ?" if since else ""),
        params,
    ).fetchone()
    if max_ts_row and max_ts_row[0]:
        try:
            latest = datetime.fromisoformat(max_ts_row[0].replace("Z", "+00:00"))
        except ValueError:
            latest = datetime.now()
    else:
        latest = datetime.now()

    cutoff_recent = latest - timedelta(days=TREND_WINDOW_DAYS)
    cutoff_prev = latest - timedelta(days=TREND_WINDOW_DAYS * 2)

    # Aggregate per (brand, item)
    items: dict[tuple, dict] = {}
    for r in rows:
        brand = r["brand"] or "Unknown"
        item = r["item"] or "Unknown"
        key = (brand, item)

        if key not in items:
            items[key] = {
                "brand": brand,
                "item": item,
                "variants": set(),
                "total_mentions": 0,
                "request_count": 0,
                "satisfaction_count": 0,
                "regret_count": 0,
                "ownership_count": 0,
                "neutral_count": 0,
                "weighted_intent_sum": 0.0,
                "recent_mentions": 0,
                "prev_mentions": 0,
            }

        d = items[key]
        d["total_mentions"] += 1

        intent = r["intent_type"]
        d[f"{intent}_count"] = d.get(f"{intent}_count", 0) + 1

        # Weighted intent contribution
        weight = INTENT_WEIGHTS.get(intent, 0.1)
        ch_weight = _channel_weight(r["channel"])
        d["weighted_intent_sum"] += r["intent_score"] * weight * ch_weight

        if r["variant"]:
            d["variants"].add(r["variant"])

        # Trend windows
        try:
            ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
            if ts >= cutoff_recent:
                d["recent_mentions"] += 1
            elif ts >= cutoff_prev:
                d["prev_mentions"] += 1
        except (ValueError, AttributeError):
            pass

    # Normalize and compute final scores
    max_mentions = max(d["total_mentions"] for d in items.values()) or 1
    max_intent = max(d["weighted_intent_sum"] for d in items.values()) or 1

    results = []
    for key, d in items.items():
        volume_score = d["total_mentions"] / max_mentions

        intent_score = d["weighted_intent_sum"] / max_intent

        # Trend velocity
        prev = max(d["prev_mentions"], 1)
        velocity = (d["recent_mentions"] - d["prev_mentions"]) / prev
        velocity_norm = max(0.0, min(1.0, (velocity + 1) / 2))  # normalize -1..inf to 0..1

        final_score = (
            FINAL_SCORE_WEIGHTS["intent"] * intent_score
            + FINAL_SCORE_WEIGHTS["velocity"] * velocity_norm
            + FINAL_SCORE_WEIGHTS["volume"] * volume_score
        )

        results.append({
            "brand": d["brand"],
            "item": d["item"],
            "variant": " | ".join(sorted(d["variants"])) if d["variants"] else "",
            "total_mentions": d["total_mentions"],
            "request_count": d["request_count"],
            "satisfaction_count": d["satisfaction_count"],
            "regret_count": d["regret_count"],
            "ownership_count": d["ownership_count"],
            "velocity": round(velocity, 3),
            "velocity_norm": round(velocity_norm, 3),
            "intent_score": round(intent_score, 4),
            "volume_score": round(volume_score, 4),
            "final_score": round(final_score, 4),
        })

    results.sort(key=lambda x: x["final_score"], reverse=True)
    log.info(f"Scored {len(results)} item combinations")
    return results


def compute_brand_scores(conn: sqlite3.Connection,
                         since: str | None = None) -> list[dict]:
    """Compute aggregate scores per brand."""
    since_clause = " AND timestamp >= ?" if since else ""
    params = [since] if since else []
    rows = conn.execute(f"""
        SELECT brand, intent_type, intent_score, channel, timestamp
        FROM processed_mentions
        WHERE brand IS NOT NULL
        {since_clause}
    """, params).fetchall()

    if not rows:
        return []

    max_ts_row = conn.execute(
        "SELECT MAX(timestamp) FROM processed_mentions WHERE brand IS NOT NULL"
        + (" AND timestamp >= ?" if since else ""),
        params,
    ).fetchone()
    if max_ts_row and max_ts_row[0]:
        try:
            latest = datetime.fromisoformat(max_ts_row[0].replace("Z", "+00:00"))
        except ValueError:
            latest = datetime.now()
    else:
        latest = datetime.now()

    cutoff_recent = latest - timedelta(days=TREND_WINDOW_DAYS)
    cutoff_prev = latest - timedelta(days=TREND_WINDOW_DAYS * 2)

    brands: dict[str, dict] = {}
    for r in rows:
        brand = r["brand"]
        if brand not in brands:
            brands[brand] = {
                "brand": brand,
                "mentions": 0,
                "intent_sum": 0.0,
                "recent": 0,
                "prev": 0,
            }
        b = brands[brand]
        b["mentions"] += 1
        weight = INTENT_WEIGHTS.get(r["intent_type"], 0.1)
        b["intent_sum"] += r["intent_score"] * weight

        try:
            ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
            if ts >= cutoff_recent:
                b["recent"] += 1
            elif ts >= cutoff_prev:
                b["prev"] += 1
        except (ValueError, AttributeError):
            pass

    max_mentions = max(b["mentions"] for b in brands.values()) or 1

    results = []
    for b in brands.values():
        avg_intent = b["intent_sum"] / b["mentions"] if b["mentions"] else 0
        prev = max(b["prev"], 1)
        velocity = (b["recent"] - b["prev"]) / prev
        trend_score = (
            0.4 * (b["mentions"] / max_mentions)
            + 0.3 * min(1.0, avg_intent)
            + 0.3 * max(0, min(1.0, (velocity + 1) / 2))
        )
        results.append({
            "brand": b["brand"],
            "mentions": b["mentions"],
            "avg_intent": round(avg_intent, 4),
            "trend_score": round(trend_score, 4),
        })

    results.sort(key=lambda x: x["trend_score"], reverse=True)
    log.info(f"Scored {len(results)} brands")
    return results
