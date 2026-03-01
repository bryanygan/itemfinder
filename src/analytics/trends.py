"""Trend detection and advanced analytics."""

import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta

from src.common.config import TREND_WINDOW_DAYS
from src.common.log_util import get_logger

log = get_logger("trends")


def _parse_ts(ts_str: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def trending_items(conn: sqlite3.Connection, top_n: int = 20) -> list[dict]:
    """Identify fastest-rising items by comparing recent vs previous window."""

    max_ts = conn.execute(
        "SELECT MAX(timestamp) FROM processed_mentions"
    ).fetchone()[0]
    if not max_ts:
        return []

    latest = _parse_ts(max_ts) or datetime.now()
    cutoff_recent = (latest - timedelta(days=TREND_WINDOW_DAYS)).isoformat()
    cutoff_prev = (latest - timedelta(days=TREND_WINDOW_DAYS * 2)).isoformat()

    rows = conn.execute("""
        SELECT brand, item, timestamp
        FROM processed_mentions
        WHERE (brand IS NOT NULL OR item IS NOT NULL)
          AND timestamp >= ?
    """, (cutoff_prev,)).fetchall()

    recent_counts: dict[tuple, int] = defaultdict(int)
    prev_counts: dict[tuple, int] = defaultdict(int)

    for r in rows:
        key = (r["brand"] or "Unknown", r["item"] or "Unknown")
        ts = _parse_ts(r["timestamp"])
        if not ts:
            continue
        if ts.isoformat() >= cutoff_recent:
            recent_counts[key] += 1
        else:
            prev_counts[key] += 1

    results = []
    for key in set(list(recent_counts.keys()) + list(prev_counts.keys())):
        recent = recent_counts.get(key, 0)
        prev = max(prev_counts.get(key, 0), 1)
        velocity = (recent - prev) / prev
        if recent >= 2:  # minimum threshold
            results.append({
                "brand": key[0],
                "item": key[1],
                "recent_mentions": recent,
                "prev_mentions": prev_counts.get(key, 0),
                "velocity": round(velocity, 3),
            })

    results.sort(key=lambda x: x["velocity"], reverse=True)
    return results[:top_n]


def channel_breakdown(conn: sqlite3.Connection) -> list[dict]:
    """Break down mentions by channel."""
    rows = conn.execute("""
        SELECT channel,
               COUNT(*) as total,
               SUM(CASE WHEN intent_type='request' THEN 1 ELSE 0 END) as requests,
               SUM(CASE WHEN intent_type='satisfaction' THEN 1 ELSE 0 END) as satisfaction,
               SUM(CASE WHEN intent_type='regret' THEN 1 ELSE 0 END) as regret,
               SUM(CASE WHEN intent_type='ownership' THEN 1 ELSE 0 END) as ownership,
               SUM(CASE WHEN intent_type='neutral' THEN 1 ELSE 0 END) as neutral,
               AVG(intent_score) as avg_score
        FROM processed_mentions
        GROUP BY channel
        ORDER BY total DESC
    """).fetchall()
    return [dict(r) for r in rows]


def daily_volume(conn: sqlite3.Connection) -> list[dict]:
    """Get daily mention counts for time-series visualization."""
    rows = conn.execute("""
        SELECT DATE(timestamp) as day,
               COUNT(*) as mentions,
               SUM(CASE WHEN intent_type='request' THEN 1 ELSE 0 END) as requests,
               SUM(CASE WHEN intent_type='satisfaction' THEN 1 ELSE 0 END) as satisfaction,
               SUM(CASE WHEN intent_type='regret' THEN 1 ELSE 0 END) as regret,
               SUM(CASE WHEN intent_type='ownership' THEN 1 ELSE 0 END) as ownership
        FROM processed_mentions
        GROUP BY DATE(timestamp)
        ORDER BY day
    """).fetchall()
    return [dict(r) for r in rows]


def top_items_by_intent(conn: sqlite3.Connection, intent: str, limit: int = 15) -> list[dict]:
    """Get top items for a specific intent type."""
    rows = conn.execute("""
        SELECT brand, item,
               COUNT(*) as count,
               AVG(intent_score) as avg_score
        FROM processed_mentions
        WHERE intent_type = ?
          AND (brand IS NOT NULL OR item IS NOT NULL)
        GROUP BY brand, item
        ORDER BY count DESC
        LIMIT ?
    """, (intent, limit)).fetchall()
    return [dict(r) for r in rows]


def sentiment_over_time(conn: sqlite3.Connection) -> list[dict]:
    """Weekly sentiment aggregation."""
    rows = conn.execute("""
        SELECT strftime('%Y-W%W', timestamp) as week,
               intent_type,
               COUNT(*) as count
        FROM processed_mentions
        WHERE intent_type != 'neutral'
        GROUP BY week, intent_type
        ORDER BY week
    """).fetchall()
    return [dict(r) for r in rows]
