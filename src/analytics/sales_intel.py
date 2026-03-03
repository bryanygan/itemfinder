"""Sales intelligence: unmet demand, buyer profiles, cross-sell, inventory recs."""

import sqlite3
from collections import defaultdict

from src.common.log_util import get_logger

log = get_logger("sales_intel")


def unmet_demand(conn: sqlite3.Connection, min_requests: int = 3,
                 since: str | None = None,
                 platform: str | None = None) -> list[dict]:
    """Items people request but rarely own — biggest sales opportunities."""
    since_clause = " AND timestamp >= ?" if since else ""
    plat_clause = " AND message_id IN (SELECT id FROM raw_messages WHERE source_platform = ?)" if platform else ""
    params = ([platform] if platform else []) + ([since] if since else []) + [min_requests]
    rows = conn.execute(f"""
        SELECT brand, item,
               SUM(CASE WHEN intent_type='request' THEN 1 ELSE 0 END) as requests,
               SUM(CASE WHEN intent_type='ownership' THEN 1 ELSE 0 END) as owned,
               SUM(CASE WHEN intent_type='satisfaction' THEN 1 ELSE 0 END) as satisfied,
               COUNT(DISTINCT author) as unique_users
        FROM processed_mentions
        WHERE (brand IS NOT NULL OR item IS NOT NULL)
        {plat_clause}{since_clause}
        GROUP BY brand, item
        HAVING requests >= ?
        ORDER BY requests DESC
    """, params).fetchall()

    results = []
    for r in rows:
        gap = r["requests"] - r["owned"]
        if gap < 2:
            continue
        results.append({
            "brand": r["brand"] or "Various",
            "item": r["item"] or "general",
            "requests": r["requests"],
            "owned": r["owned"],
            "demand_gap": gap,
            "unique_requesters": r["unique_users"],
            "satisfaction_rate": round(r["satisfied"] / max(r["owned"], 1), 2),
        })
    results.sort(key=lambda x: x["demand_gap"], reverse=True)
    return results


def buyer_profiles(conn: sqlite3.Connection, min_activity: int = 10,
                   since: str | None = None,
                   platform: str | None = None) -> list[dict]:
    """Profile top users: what they want, what they own, brand preferences."""
    parts, wp = [], []
    if since:
        parts.append("timestamp >= ?")
        wp.append(since)
    if platform:
        parts.append("message_id IN (SELECT id FROM raw_messages WHERE source_platform = ?)")
        wp.append(platform)
    where = "WHERE " + " AND ".join(parts) if parts else ""
    having_params = wp + [min_activity]
    rows = conn.execute(f"""
        SELECT author,
               COUNT(*) as total_mentions,
               SUM(CASE WHEN intent_type='request' THEN 1 ELSE 0 END) as requests,
               SUM(CASE WHEN intent_type='ownership' THEN 1 ELSE 0 END) as owned,
               SUM(CASE WHEN intent_type='satisfaction' THEN 1 ELSE 0 END) as satisfied,
               SUM(CASE WHEN intent_type='regret' THEN 1 ELSE 0 END) as regrets
        FROM processed_mentions
        {where}
        GROUP BY author
        HAVING total_mentions >= ?
        ORDER BY requests DESC
    """, having_params).fetchall()

    since_clause = " AND timestamp >= ?" if since else ""
    since_params = [since] if since else []
    plat_clause = " AND message_id IN (SELECT id FROM raw_messages WHERE source_platform = ?)" if platform else ""
    plat_params = [platform] if platform else []

    profiles = []
    for r in rows:
        # Get top brands for this user
        brand_rows = conn.execute(f"""
            SELECT brand, COUNT(*) as cnt FROM processed_mentions
            WHERE author = ? AND brand IS NOT NULL
            {plat_clause}{since_clause}
            GROUP BY brand ORDER BY cnt DESC LIMIT 5
        """, [r["author"]] + plat_params + since_params).fetchall()
        top_brands = [{"brand": b["brand"], "count": b["cnt"]} for b in brand_rows]

        # Get top requested items
        item_rows = conn.execute(f"""
            SELECT brand, item, COUNT(*) as cnt FROM processed_mentions
            WHERE author = ? AND intent_type = 'request'
                AND (brand IS NOT NULL OR item IS NOT NULL)
            {plat_clause}{since_clause}
            GROUP BY brand, item ORDER BY cnt DESC LIMIT 5
        """, [r["author"]] + plat_params + since_params).fetchall()
        top_requests = [
            {"brand": i["brand"] or "—", "item": i["item"] or "—", "count": i["cnt"]}
            for i in item_rows
        ]

        buy_ratio = r["owned"] / max(r["requests"], 1)
        profiles.append({
            "user": r["author"],
            "total_mentions": r["total_mentions"],
            "requests": r["requests"],
            "owned": r["owned"],
            "satisfied": r["satisfied"],
            "regrets": r["regrets"],
            "buy_ratio": round(buy_ratio, 2),
            "top_brands": top_brands,
            "top_requests": top_requests,
            "segment": _segment_user(r["requests"], r["owned"], buy_ratio),
        })

    return profiles


def _segment_user(requests: int, owned: int, buy_ratio: float) -> str:
    if buy_ratio >= 0.5 and owned >= 10:
        return "loyal_buyer"
    if requests >= 50 and buy_ratio < 0.3:
        return "high_intent_prospect"
    if owned >= 5 and requests >= 10:
        return "active_buyer"
    if requests >= 10:
        return "browser"
    return "casual"


def brand_cross_sell(conn: sqlite3.Connection, min_overlap: int = 5,
                     since: str | None = None,
                     platform: str | None = None) -> list[dict]:
    """Find brands frequently mentioned by the same users (cross-sell opportunities)."""
    since_clause = " AND timestamp >= ?" if since else ""
    plat_clause = " AND message_id IN (SELECT id FROM raw_messages WHERE source_platform = ?)" if platform else ""
    params = ([platform] if platform else []) + ([since] if since else [])
    rows = conn.execute(f"""
        SELECT author, brand FROM processed_mentions
        WHERE brand IS NOT NULL
        {plat_clause}{since_clause}
        GROUP BY author, brand
    """, params).fetchall()

    user_brands: dict[str, set] = defaultdict(set)
    for r in rows:
        user_brands[r["author"]].add(r["brand"])

    pairs: dict[tuple, int] = defaultdict(int)
    for brands in user_brands.values():
        bl = sorted(brands)
        for i in range(len(bl)):
            for j in range(i + 1, len(bl)):
                pairs[(bl[i], bl[j])] += 1

    results = [
        {"brand_a": a, "brand_b": b, "shared_users": cnt}
        for (a, b), cnt in sorted(pairs.items(), key=lambda x: -x[1])
        if cnt >= min_overlap
    ]
    return results[:30]


def size_demand(conn: sqlite3.Connection,
                since: str | None = None,
                platform: str | None = None) -> list[dict]:
    """Analyze which sizes are most requested."""
    since_clause = " AND timestamp >= ?" if since else ""
    plat_clause = " AND message_id IN (SELECT id FROM raw_messages WHERE source_platform = ?)" if platform else ""
    params = ([platform] if platform else []) + ([since] if since else [])
    rows = conn.execute(f"""
        SELECT variant, intent_type, COUNT(*) as cnt
        FROM processed_mentions
        WHERE variant IS NOT NULL
        {plat_clause}{since_clause}
        GROUP BY variant, intent_type
    """, params).fetchall()

    size_data: dict[str, dict] = defaultdict(lambda: {"requests": 0, "owned": 0, "total": 0})
    for r in rows:
        variant = r["variant"]
        # Extract just the size portion
        parts = variant.split(" / ")
        for part in parts:
            p = part.strip()
            if p.startswith("size "):
                d = size_data[p]
                d["total"] += r["cnt"]
                if r["intent_type"] == "request":
                    d["requests"] += r["cnt"]
                elif r["intent_type"] == "ownership":
                    d["owned"] += r["cnt"]

    results = [
        {"size": sz, **data}
        for sz, data in sorted(size_data.items(), key=lambda x: -x[1]["total"])
    ]
    return results


def color_demand(conn: sqlite3.Connection,
                 since: str | None = None,
                 platform: str | None = None) -> list[dict]:
    """Analyze which colors are most in demand."""
    since_clause = " AND timestamp >= ?" if since else ""
    plat_clause = " AND message_id IN (SELECT id FROM raw_messages WHERE source_platform = ?)" if platform else ""
    params = ([platform] if platform else []) + ([since] if since else [])
    rows = conn.execute(f"""
        SELECT variant, intent_type, COUNT(*) as cnt
        FROM processed_mentions
        WHERE variant IS NOT NULL
        {plat_clause}{since_clause}
        GROUP BY variant, intent_type
    """, params).fetchall()

    color_data: dict[str, dict] = defaultdict(lambda: {"requests": 0, "owned": 0, "total": 0})
    for r in rows:
        variant = r["variant"]
        parts = variant.split(" / ")
        for part in parts:
            p = part.strip()
            if not p.startswith("size "):
                d = color_data[p]
                d["total"] += r["cnt"]
                if r["intent_type"] == "request":
                    d["requests"] += r["cnt"]
                elif r["intent_type"] == "ownership":
                    d["owned"] += r["cnt"]

    results = [
        {"color": c, **data}
        for c, data in sorted(color_data.items(), key=lambda x: -x[1]["total"])
        if data["total"] >= 5
    ]
    return results


def inventory_recommendations(conn: sqlite3.Connection,
                              since: str | None = None,
                              platform: str | None = None) -> list[dict]:
    """Generate specific inventory recommendations based on demand signals."""
    unmet = unmet_demand(conn, min_requests=3, since=since, platform=platform)
    sizes = size_demand(conn, since=since, platform=platform)
    colors = color_demand(conn, since=since, platform=platform)

    top_sizes = [s["size"] for s in sizes[:5]]
    top_colors = [c["color"] for c in colors[:5]]

    recs = []
    for item in unmet[:20]:
        priority = "HIGH" if item["demand_gap"] >= 10 else "MEDIUM" if item["demand_gap"] >= 5 else "LOW"
        recs.append({
            "brand": item["brand"],
            "item": item["item"],
            "priority": priority,
            "demand_gap": item["demand_gap"],
            "unique_requesters": item["unique_requesters"],
            "recommended_sizes": top_sizes[:3],
            "recommended_colors": top_colors[:3],
            "notes": _generate_rec_note(item),
        })

    return recs


def _generate_rec_note(item: dict) -> str:
    parts = []
    if item["demand_gap"] >= 15:
        parts.append("Very high unmet demand")
    elif item["demand_gap"] >= 8:
        parts.append("Strong demand signal")
    if item["unique_requesters"] >= 5:
        parts.append(f"{item['unique_requesters']} unique users requesting")
    if item["satisfaction_rate"] >= 1.0 and item["owned"] >= 2:
        parts.append("High satisfaction when purchased")
    return "; ".join(parts) if parts else "Steady demand"


def monthly_seasonality(conn: sqlite3.Connection,
                        since: str | None = None,
                        platform: str | None = None) -> list[dict]:
    """Monthly mention volumes for seasonality analysis."""
    since_clause = " AND timestamp >= ?" if since else ""
    plat_clause = " AND message_id IN (SELECT id FROM raw_messages WHERE source_platform = ?)" if platform else ""
    params = ([platform] if platform else []) + ([since] if since else [])
    rows = conn.execute(f"""
        SELECT strftime('%Y-%m', timestamp) as month,
               COUNT(*) as total,
               SUM(CASE WHEN intent_type='request' THEN 1 ELSE 0 END) as requests,
               SUM(CASE WHEN intent_type='ownership' THEN 1 ELSE 0 END) as owned,
               COUNT(DISTINCT author) as unique_users
        FROM processed_mentions
        WHERE month IS NOT NULL
        {plat_clause}{since_clause}
        GROUP BY month ORDER BY month
    """, params).fetchall()
    return [dict(r) for r in rows]


def conversion_tracking(conn: sqlite3.Connection,
                        since: str | None = None,
                        platform: str | None = None) -> list[dict]:
    """Users who requested a brand AND later owned it — shows conversion."""
    since_clause = " AND timestamp >= ?" if since else ""
    plat_clause = " AND message_id IN (SELECT id FROM raw_messages WHERE source_platform = ?)" if platform else ""
    params = ([platform] if platform else []) + ([since] if since else [])
    rows = conn.execute(f"""
        SELECT author, brand,
               SUM(CASE WHEN intent_type='request' THEN 1 ELSE 0 END) as requests,
               SUM(CASE WHEN intent_type='ownership' THEN 1 ELSE 0 END) as owned,
               SUM(CASE WHEN intent_type='satisfaction' THEN 1 ELSE 0 END) as satisfied
        FROM processed_mentions
        WHERE brand IS NOT NULL
        {plat_clause}{since_clause}
        GROUP BY author, brand
        HAVING requests >= 2 AND owned >= 1
        ORDER BY requests DESC
    """, params).fetchall()
    return [dict(r) for r in rows[:30]]
