"""Per-subreddit deep-dive analytics.

Joins processed_mentions with reddit_metadata to analyze demand signals
within individual subreddit communities, cross-references curated external
trend data, and produces purchase recommendations ranked by the specific
community's demand signal — not just aggregate platform trends.

Used by the dashboard's "Subreddit Deep Dive" tab to answer:
  - Which items are hottest in r/FashionReps vs r/Repsneakers right now?
  - Which items rise fastest inside a specific community?
  - Which items have cross-community demand (best purchase candidates)?
"""

import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta

from src.analytics.market_intel import (
    PURCHASE_LINKS,
    REDDIT_TRENDING,
    WEIDIAN_TOP_SELLERS,
    _DEMAND_SCORE,
    _TREND_SCORE,
)
from src.common.config import (
    DEFAULT_SUBREDDIT_WEIGHT,
    REDDIT_TARGET_SUBREDDITS,
    SUBREDDIT_WEIGHTS,
    TREND_WINDOW_DAYS,
)
from src.common.log_util import get_logger

log = get_logger("subreddit_deep_dive")


# ── Helpers ──────────────────────────────────────────────────────────────

def _parse_ts(ts_str: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _sub_weight(subreddit: str) -> float:
    return SUBREDDIT_WEIGHTS.get(subreddit.lower(), DEFAULT_SUBREDDIT_WEIGHT)


def _lookup_purchase_link(brand: str, item: str) -> dict:
    """Fuzzy-match PURCHASE_LINKS by brand/item keywords."""
    if not brand and not item:
        return {}
    key = f"{brand}|{item}"
    if key in PURCHASE_LINKS:
        return PURCHASE_LINKS[key]
    b_low = (brand or "").lower()
    i_low = (item or "").lower()
    for k, v in PURCHASE_LINKS.items():
        k_brand, k_item = k.split("|", 1)
        kb, ki = k_brand.lower(), k_item.lower()
        if b_low and (b_low in kb or kb in b_low):
            if not i_low or (i_low in ki or ki in i_low):
                return v
    return {}


def _best_link(info: dict) -> str:
    return (info.get("weidian") or info.get("yupoo") or info.get("taobao")
            or info.get("spreadsheet") or info.get("resource") or "")


# ── Core query helpers ────────────────────────────────────────────────────

def get_tracked_subreddits() -> list[str]:
    """Return the list of monitored subreddits from config."""
    return list(REDDIT_TARGET_SUBREDDITS)


def available_subreddits(conn: sqlite3.Connection) -> list[dict]:
    """List subreddits with mention counts actually present in the DB."""
    rows = conn.execute("""
        SELECT rm.subreddit as subreddit,
               COUNT(DISTINCT pm.mention_id) as mentions,
               COUNT(DISTINCT pm.message_id) as posts
        FROM reddit_metadata rm
        LEFT JOIN processed_mentions pm ON pm.message_id = rm.message_id
        GROUP BY rm.subreddit
        ORDER BY mentions DESC
    """).fetchall()
    return [dict(r) for r in rows]


def subreddit_kpis(conn: sqlite3.Connection, subreddit: str,
                   since: str | None = None) -> dict:
    """Summary counts for a single subreddit."""
    params = [subreddit]
    since_clause = ""
    if since:
        since_clause = " AND pm.timestamp >= ?"
        params.append(since)

    row = conn.execute(f"""
        SELECT COUNT(DISTINCT pm.message_id) as posts,
               COUNT(*) as mentions,
               COUNT(DISTINCT pm.brand) as brands,
               SUM(CASE WHEN pm.intent_type='request' THEN 1 ELSE 0 END) as requests,
               SUM(CASE WHEN pm.intent_type='satisfaction' THEN 1 ELSE 0 END) as satisfied,
               SUM(CASE WHEN pm.intent_type='regret' THEN 1 ELSE 0 END) as regret,
               SUM(CASE WHEN pm.intent_type='ownership' THEN 1 ELSE 0 END) as owned,
               AVG(pm.intent_score) as avg_score
        FROM processed_mentions pm
        JOIN reddit_metadata rm ON rm.message_id = pm.message_id
        WHERE rm.subreddit = ?
        {since_clause}
    """, params).fetchone()

    d = dict(row) if row else {}
    d["subreddit"] = subreddit
    d["signal_weight"] = _sub_weight(subreddit)
    d["avg_score"] = round(d.get("avg_score") or 0.0, 3)
    return d


def subreddit_top_items(conn: sqlite3.Connection, subreddit: str,
                        limit: int = 25,
                        since: str | None = None) -> list[dict]:
    """Top items by mention count within a single subreddit."""
    params: list = [subreddit]
    since_clause = ""
    if since:
        since_clause = " AND pm.timestamp >= ?"
        params.append(since)
    params.append(limit)

    rows = conn.execute(f"""
        SELECT pm.brand, pm.item,
               COUNT(*) as mentions,
               SUM(CASE WHEN pm.intent_type='request' THEN 1 ELSE 0 END) as requests,
               SUM(CASE WHEN pm.intent_type='satisfaction' THEN 1 ELSE 0 END) as satisfied,
               SUM(CASE WHEN pm.intent_type='regret' THEN 1 ELSE 0 END) as regret,
               SUM(CASE WHEN pm.intent_type='ownership' THEN 1 ELSE 0 END) as owned,
               AVG(pm.intent_score) as avg_score
        FROM processed_mentions pm
        JOIN reddit_metadata rm ON rm.message_id = pm.message_id
        WHERE rm.subreddit = ?
          AND (pm.brand IS NOT NULL OR pm.item IS NOT NULL)
          {since_clause}
        GROUP BY pm.brand, pm.item
        HAVING mentions >= 1
        ORDER BY mentions DESC, requests DESC
        LIMIT ?
    """, params).fetchall()
    return [dict(r) for r in rows]


def subreddit_rising_items(conn: sqlite3.Connection, subreddit: str,
                           top_n: int = 15,
                           since: str | None = None) -> list[dict]:
    """Fastest-rising items inside a subreddit (recent vs prior window)."""
    params: list = [subreddit]
    since_clause = ""
    if since:
        since_clause = " AND pm.timestamp >= ?"
        params.append(since)

    max_ts = conn.execute(f"""
        SELECT MAX(pm.timestamp)
        FROM processed_mentions pm
        JOIN reddit_metadata rm ON rm.message_id = pm.message_id
        WHERE rm.subreddit = ?
        {since_clause}
    """, params).fetchone()[0]
    if not max_ts:
        return []

    latest = _parse_ts(max_ts) or datetime.now()
    cutoff_recent = (latest - timedelta(days=TREND_WINDOW_DAYS)).isoformat()
    cutoff_prev = (latest - timedelta(days=TREND_WINDOW_DAYS * 2)).isoformat()
    if since and since > cutoff_prev:
        cutoff_prev = since

    rows = conn.execute("""
        SELECT pm.brand, pm.item, pm.timestamp
        FROM processed_mentions pm
        JOIN reddit_metadata rm ON rm.message_id = pm.message_id
        WHERE rm.subreddit = ?
          AND (pm.brand IS NOT NULL OR pm.item IS NOT NULL)
          AND pm.timestamp >= ?
    """, [subreddit, cutoff_prev]).fetchall()

    recent: dict[tuple, int] = defaultdict(int)
    prev: dict[tuple, int] = defaultdict(int)
    for r in rows:
        key = (r["brand"] or "Unknown", r["item"] or "Unknown")
        if r["timestamp"] >= cutoff_recent:
            recent[key] += 1
        else:
            prev[key] += 1

    results = []
    for key in set(list(recent.keys()) + list(prev.keys())):
        rc = recent.get(key, 0)
        pc = max(prev.get(key, 0), 1)
        velocity = (rc - pc) / pc
        if rc >= 2:
            results.append({
                "brand": key[0],
                "item": key[1],
                "recent_mentions": rc,
                "prev_mentions": prev.get(key, 0),
                "velocity": round(velocity, 3),
            })
    results.sort(key=lambda x: x["velocity"], reverse=True)
    return results[:top_n]


def subreddit_flair_signals(conn: sqlite3.Connection, subreddit: str,
                            since: str | None = None) -> list[dict]:
    """Distribution of post flairs inside a subreddit (flair = strongest intent signal)."""
    params: list = [subreddit]
    since_clause = ""
    if since:
        since_clause = " AND rm2.timestamp >= ?"
        params.append(since)

    rows = conn.execute(f"""
        SELECT COALESCE(NULLIF(TRIM(rm.flair), ''), '(none)') as flair,
               COUNT(*) as posts,
               AVG(rm.score) as avg_score,
               AVG(rm.num_comments) as avg_comments
        FROM reddit_metadata rm
        JOIN raw_messages rm2 ON rm2.id = rm.message_id
        WHERE rm.subreddit = ?
          {since_clause}
        GROUP BY flair
        ORDER BY posts DESC
    """, params).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["avg_score"] = round(d.get("avg_score") or 0, 1)
        d["avg_comments"] = round(d.get("avg_comments") or 0, 1)
        out.append(d)
    return out


def cross_subreddit_matrix(conn: sqlite3.Connection,
                           top_items: int = 20,
                           since: str | None = None) -> list[dict]:
    """For the top items across Reddit, show mention counts per subreddit.
    Items appearing in multiple subreddits = higher confidence purchases.
    """
    params_top: list = []
    since_top = ""
    if since:
        since_top = " WHERE pm.timestamp >= ?"
        params_top.append(since)
    params_top.append(top_items)

    top_rows = conn.execute(f"""
        SELECT pm.brand, pm.item, COUNT(*) as total
        FROM processed_mentions pm
        JOIN reddit_metadata rm ON rm.message_id = pm.message_id
        {since_top}
        {"AND" if since else "WHERE"} (pm.brand IS NOT NULL OR pm.item IS NOT NULL)
        GROUP BY pm.brand, pm.item
        ORDER BY total DESC
        LIMIT ?
    """, params_top).fetchall()
    if not top_rows:
        return []

    keys = [(r["brand"], r["item"]) for r in top_rows]

    rows = conn.execute(f"""
        SELECT pm.brand, pm.item, rm.subreddit, COUNT(*) as cnt
        FROM processed_mentions pm
        JOIN reddit_metadata rm ON rm.message_id = pm.message_id
        {since_top}
        GROUP BY pm.brand, pm.item, rm.subreddit
    """, params_top[:-1] if since else []).fetchall()

    by_item: dict[tuple, dict] = {k: {"brand": k[0] or "Unknown",
                                       "item": k[1] or "Unknown",
                                       "total_mentions": 0,
                                       "subreddit_count": 0,
                                       "subreddits": {}}
                                  for k in keys}
    for r in rows:
        k = (r["brand"], r["item"])
        if k not in by_item:
            continue
        by_item[k]["subreddits"][r["subreddit"]] = r["cnt"]

    out = []
    for k in keys:
        rec = by_item[k]
        rec["subreddit_count"] = len(rec["subreddits"])
        rec["total_mentions"] = sum(rec["subreddits"].values())
        rec["top_subreddits"] = ", ".join(
            f"{s} ({c})" for s, c in sorted(rec["subreddits"].items(),
                                            key=lambda x: -x[1])[:5]
        )
        out.append(rec)
    out.sort(key=lambda r: (-r["subreddit_count"], -r["total_mentions"]))
    return out


# ── Purchase recommendations per subreddit ───────────────────────────────

def subreddit_purchase_recommendations(conn: sqlite3.Connection,
                                       subreddit: str,
                                       since: str | None = None,
                                       limit: int = 25) -> list[dict]:
    """Blend a subreddit's internal demand with curated external data
    and weight by that subreddit's signal strength to produce a ranked
    "best items to buy" list specific to this community.
    """
    weight = _sub_weight(subreddit)

    # Gather internal counts for this subreddit
    top_items = subreddit_top_items(conn, subreddit, limit=60, since=since)
    max_ment = max((r["mentions"] for r in top_items), default=1)

    recs: dict[str, dict] = {}

    for r in top_items:
        brand = r["brand"] or "Various"
        item = r["item"] or "general"
        key = f"{brand}|{item}"

        # Internal intent-weighted score
        intent_weighted = (r["requests"] * 0.8 + r["regret"] * 1.0
                           + r["satisfied"] * 0.6 + r["owned"] * 0.4)
        max_intent = r["mentions"] * 1.0
        intent_norm = intent_weighted / max(max_intent, 1)
        volume_norm = r["mentions"] / max(max_ment, 1)
        avg_score = r.get("avg_score") or 0.0
        internal = min(0.5 * intent_norm + 0.3 * volume_norm + 0.2 * avg_score, 1.0)

        # Community-weighted signal
        community_score = round(min(internal * weight, 1.0), 3)

        # External cross-reference
        ext_match = None
        for ext in REDDIT_TRENDING:
            eb = ext["brand"].lower()
            ei = ext["item"].lower()
            if brand.lower() in eb or eb in brand.lower():
                if not item or item == "general" or item.lower() in ei or ei in item.lower():
                    ext_match = ext
                    break
        ext_score = _DEMAND_SCORE.get(ext_match["demand"], 0.5) if ext_match else 0.0

        # Weidian live-sales boost
        weidian_boost = 0.0
        weidian_match = None
        for ws in WEIDIAN_TOP_SELLERS:
            if (brand.lower() in ws["brand"].lower()
                    or ws["brand"].lower() in brand.lower()):
                if item == "general" or item.lower() in ws["item"].lower() \
                        or ws["item"].lower() in item.lower():
                    weidian_match = ws
                    weidian_boost = _TREND_SCORE.get(ws["trend"], 0.4) * 0.2
                    break

        combined = round(
            min(0.55 * community_score + 0.3 * ext_score + weidian_boost, 1.0), 3
        )

        # Determine action
        if combined >= 0.85:
            action = "BUY NOW — Top pick for this community"
        elif combined >= 0.7:
            action = "STRONG BUY — High demand inside this sub"
        elif combined >= 0.55:
            action = "BUY — Solid community demand"
        elif combined >= 0.4:
            action = "WATCH — Monitor momentum"
        else:
            action = "HOLD — Weak signal"

        links = _lookup_purchase_link(brand, item)

        recs[key] = {
            "brand": brand,
            "item": item,
            "mentions": r["mentions"],
            "requests": r["requests"],
            "regret": r["regret"],
            "satisfied": r["satisfied"],
            "owned": r["owned"],
            "community_score": community_score,
            "external_score": round(ext_score, 2),
            "weidian_trend": weidian_match["trend"] if weidian_match else "—",
            "units_sold_30d": weidian_match["units_sold"] if weidian_match else 0,
            "combined_score": combined,
            "recommendation": action,
            "best_batch": (ext_match or {}).get("best_batch", links.get("batch", "—")),
            "price_range": (ext_match or {}).get("price_range", "—"),
            "purchase_link": _best_link(links),
            "purchase_notes": links.get("notes", ""),
        }

    # Also seed with external items tagged to this subreddit so we never
    # show an empty page on a fresh DB
    sub_norm = subreddit.lower().lstrip("r/")
    for ext in REDDIT_TRENDING:
        tags = (ext.get("subreddits") or "").lower()
        if sub_norm not in tags:
            continue
        key = f"{ext['brand']}|{ext['item']}"
        if key in recs:
            continue
        links = _lookup_purchase_link(ext["brand"], ext["item"])
        ext_score = _DEMAND_SCORE.get(ext["demand"], 0.5)
        combined = round(min(ext_score * weight, 1.0), 3)
        recs[key] = {
            "brand": ext["brand"],
            "item": ext["item"],
            "mentions": 0,
            "requests": 0,
            "regret": 0,
            "satisfied": 0,
            "owned": 0,
            "community_score": 0.0,
            "external_score": round(ext_score, 2),
            "weidian_trend": "—",
            "units_sold_30d": 0,
            "combined_score": combined,
            "recommendation": "WATCH — External signal only (no internal mentions)",
            "best_batch": ext.get("best_batch", "—"),
            "price_range": ext.get("price_range", "—"),
            "purchase_link": _best_link(links),
            "purchase_notes": links.get("notes", ""),
        }

    out = sorted(recs.values(), key=lambda x: -x["combined_score"])
    return out[:limit]


# ── Cross-community summary ──────────────────────────────────────────────

def all_subreddits_summary(conn: sqlite3.Connection,
                           since: str | None = None) -> list[dict]:
    """One row per subreddit with KPIs — used for an overview chart."""
    subs = available_subreddits(conn)
    out = []
    for s in subs:
        kpis = subreddit_kpis(conn, s["subreddit"], since=since)
        kpis["members"] = None  # optional: could map from curated SUBREDDIT_STATS
        out.append(kpis)
    out.sort(key=lambda r: -(r.get("mentions") or 0))
    return out


def best_items_across_subreddits(conn: sqlite3.Connection,
                                 top_n: int = 25,
                                 since: str | None = None) -> list[dict]:
    """Items appearing across the most communities, weighted by each
    community's signal weight. This is the "safest bets" list — demand
    isn't isolated to one subreddit.
    """
    matrix = cross_subreddit_matrix(conn, top_items=80, since=since)
    out = []
    for row in matrix:
        weighted = 0.0
        for sub, cnt in row["subreddits"].items():
            weighted += cnt * _sub_weight(sub)
        links = _lookup_purchase_link(row["brand"], row["item"])
        out.append({
            "brand": row["brand"],
            "item": row["item"],
            "subreddit_count": row["subreddit_count"],
            "total_mentions": row["total_mentions"],
            "weighted_score": round(weighted, 2),
            "top_subreddits": row["top_subreddits"],
            "purchase_link": _best_link(links),
            "best_batch": links.get("batch", "—"),
            "purchase_notes": links.get("notes", ""),
        })
    out.sort(key=lambda r: (-r["weighted_score"], -r["subreddit_count"]))
    return out[:top_n]
