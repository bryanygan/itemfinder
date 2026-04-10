"""External market intelligence — curated trend data from Reddit communities,
QC platforms (doppel.fit, FinderQC, FindQC), Weidian/1688 live sales,
and mainstream hype releases.

Combines external trend signals with internal demand data to produce
purchase recommendations ranked by opportunity score.
"""

import sqlite3
from collections import defaultdict
from datetime import datetime

from src.common.log_util import get_logger

log = get_logger("market_intel")

# ── Curated external data (April 2026 research) ──────────────────────────

# Live Weidian sales data from JadeShip/RepArchive agent tracking (last 30 days)
WEIDIAN_TOP_SELLERS: list[dict] = [
    {"rank": 1, "item": "Cloudtilt", "brand": "On Running", "category": "Sneakers", "units_sold": 252, "platform": "Weidian", "trend": "rising"},
    {"rank": 2, "item": "GATs (German Army Trainers)", "brand": "Maison Margiela", "category": "Sneakers", "units_sold": 197, "platform": "Weidian", "trend": "rising"},
    {"rank": 3, "item": "Adios Pro 4", "brand": "Adidas", "category": "Sneakers", "units_sold": 187, "platform": "Weidian", "trend": "stable"},
    {"rank": 4, "item": "Samba OG", "brand": "Adidas", "category": "Sneakers", "units_sold": 168, "platform": "Weidian", "trend": "rising"},
    {"rank": 5, "item": "Dunk Low (various)", "brand": "Nike", "category": "Sneakers", "units_sold": 155, "platform": "Weidian", "trend": "stable"},
    {"rank": 6, "item": "9060", "brand": "New Balance", "category": "Sneakers", "units_sold": 142, "platform": "Weidian", "trend": "rising"},
    {"rank": 7, "item": "Jordan 1 High OG", "brand": "Jordan", "category": "Sneakers", "units_sold": 138, "platform": "Weidian", "trend": "stable"},
    {"rank": 8, "item": "350 V2", "brand": "Yeezy", "category": "Sneakers", "units_sold": 125, "platform": "Weidian", "trend": "cooling"},
    {"rank": 9, "item": "Leather Belt", "brand": "Various", "category": "Accessories", "units_sold": 118, "platform": "Weidian", "trend": "stable"},
    {"rank": 10, "item": "Jordan 4 Retro", "brand": "Jordan", "category": "Sneakers", "units_sold": 112, "platform": "Weidian", "trend": "stable"},
    {"rank": 11, "item": "Speed Trainer", "brand": "Balenciaga", "category": "Sneakers", "units_sold": 98, "platform": "Weidian", "trend": "stable"},
    {"rank": 12, "item": "Essentials Hoodie", "brand": "Fear of God", "category": "Clothing", "units_sold": 95, "platform": "Weidian", "trend": "stable"},
    {"rank": 13, "item": "Track Runner", "brand": "Balenciaga", "category": "Sneakers", "units_sold": 88, "platform": "Weidian", "trend": "cooling"},
    {"rank": 14, "item": "B23 High Top", "brand": "Dior", "category": "Sneakers", "units_sold": 82, "platform": "Weidian", "trend": "rising"},
    {"rank": 15, "item": "Fleece-Lined Pants", "brand": "Various", "category": "Clothing", "units_sold": 78, "platform": "Weidian", "trend": "cooling"},
]

# 1688 top sellers (bulk/budget segment)
PLATFORM_1688_TOP: list[dict] = [
    {"rank": 1, "item": "Air Force 1 Low White", "brand": "Nike", "category": "Sneakers", "units_sold": 320, "platform": "1688", "trend": "stable"},
    {"rank": 2, "item": "Essentials Sweatpants", "brand": "Fear of God", "category": "Clothing", "units_sold": 275, "platform": "1688", "trend": "rising"},
    {"rank": 3, "item": "Classic Flap Bag", "brand": "Chanel", "category": "Bags", "units_sold": 210, "platform": "1688", "trend": "rising"},
    {"rank": 4, "item": "Keepall 50", "brand": "Louis Vuitton", "category": "Bags", "units_sold": 195, "platform": "1688", "trend": "stable"},
    {"rank": 5, "item": "Dunk Low Panda", "brand": "Nike", "category": "Sneakers", "units_sold": 188, "platform": "1688", "trend": "stable"},
    {"rank": 6, "item": "Nuptse Jacket", "brand": "The North Face", "category": "Clothing", "units_sold": 165, "platform": "1688", "trend": "cooling"},
    {"rank": 7, "item": "Saddle Bag", "brand": "Dior", "category": "Bags", "units_sold": 155, "platform": "1688", "trend": "rising"},
    {"rank": 8, "item": "Hoodie Logo", "brand": "Chrome Hearts", "category": "Clothing", "units_sold": 148, "platform": "1688", "trend": "rising"},
    {"rank": 9, "item": "Cargo Pants", "brand": "Stone Island", "category": "Clothing", "units_sold": 135, "platform": "1688", "trend": "stable"},
    {"rank": 10, "item": "Cassette Bag", "brand": "Bottega Veneta", "category": "Bags", "units_sold": 128, "platform": "1688", "trend": "rising"},
]

# Reddit community trending items — aggregated from FashionReps (2.2M), Repsneakers
# (969K), QualityReps, CloseToRetail, 1688Reps, WeidianWarriors, RepBudgetSneakers
REDDIT_TRENDING: list[dict] = [
    # Sneakers — highest demand across all rep subs
    {"brand": "Jordan", "item": "Jordan 1 OW (Off-White)", "category": "Sneakers", "demand": "very_high", "best_batch": "LJR / OG", "price_range": "$30–50", "subreddits": "FashionReps, Repsneakers, QualityReps", "signal": "request"},
    {"brand": "Jordan", "item": "Travis Scott x AJ1 Low OG", "category": "Sneakers", "demand": "very_high", "best_batch": "LJR", "price_range": "$35–50", "subreddits": "Repsneakers, FashionReps", "signal": "request"},
    {"brand": "Nike", "item": "Dunk Low (various)", "category": "Sneakers", "demand": "very_high", "best_batch": "M Batch", "price_range": "$25–40", "subreddits": "RepBudgetSneakers, WeidianWarriors", "signal": "request"},
    {"brand": "Jordan", "item": "Travis Scott x AJ4 Cactus Jack", "category": "Sneakers", "demand": "very_high", "best_batch": "PK", "price_range": "$35–55", "subreddits": "Repsneakers, FashionReps", "signal": "request"},
    {"brand": "Yeezy", "item": "350 V2", "category": "Sneakers", "demand": "high", "best_batch": "PK BASF", "price_range": "$35–55", "subreddits": "FashionReps, RepBudgetSneakers", "signal": "request"},
    {"brand": "Jordan", "item": "Jordan 4 (various)", "category": "Sneakers", "demand": "high", "best_batch": "PK / LJR", "price_range": "$35–50", "subreddits": "Repsneakers, CloseToRetail", "signal": "request"},
    {"brand": "Jordan", "item": "Jordan 1 x Dior", "category": "Sneakers", "demand": "high", "best_batch": "LJR / OG", "price_range": "$40–60", "subreddits": "QualityReps, DesignerReps", "signal": "request"},
    {"brand": "Adidas", "item": "Samba OG", "category": "Sneakers", "demand": "high", "best_batch": "H12", "price_range": "$20–35", "subreddits": "WeidianWarriors, RepBudgetSneakers", "signal": "ownership"},
    {"brand": "New Balance", "item": "9060", "category": "Sneakers", "demand": "high", "best_batch": "—", "price_range": "$25–40", "subreddits": "FashionReps, WeidianWarriors", "signal": "satisfaction"},
    {"brand": "Maison Margiela", "item": "GATs", "category": "Sneakers", "demand": "high", "best_batch": "—", "price_range": "$25–45", "subreddits": "QualityReps, WeidianWarriors", "signal": "ownership"},
    # Clothing — streetwear dominates
    {"brand": "Fear of God", "item": "Essentials Hoodie / Sweats", "category": "Clothing", "demand": "very_high", "best_batch": "—", "price_range": "$15–30", "subreddits": "FashionReps, 1688Reps", "signal": "request"},
    {"brand": "Gallery Dept", "item": "Tees / Jeans / Hoodies", "category": "Clothing", "demand": "high", "best_batch": "—", "price_range": "$15–40", "subreddits": "QualityReps, FashionReps", "signal": "request"},
    {"brand": "Chrome Hearts", "item": "Hoodies / Jewelry", "category": "Clothing", "demand": "very_high", "best_batch": "—", "price_range": "$15–45", "subreddits": "QualityReps, FashionReps, DesignerReps", "signal": "request"},
    {"brand": "Sp5der", "item": "Hoodies / Pants", "category": "Clothing", "demand": "high", "best_batch": "—", "price_range": "$12–25", "subreddits": "FashionReps", "signal": "request"},
    {"brand": "Trapstar", "item": "Tracksuits / Hoodies", "category": "Clothing", "demand": "high", "best_batch": "—", "price_range": "$15–35", "subreddits": "FashionReps", "signal": "request"},
    {"brand": "Corteiz", "item": "Cargos / Hoodies", "category": "Clothing", "demand": "high", "best_batch": "—", "price_range": "$12–30", "subreddits": "FashionReps", "signal": "request"},
    {"brand": "Supreme", "item": "Box Logo Hoodie / Tees", "category": "Clothing", "demand": "high", "best_batch": "—", "price_range": "$15–35", "subreddits": "FashionReps, QualityReps", "signal": "request"},
    {"brand": "Stussy", "item": "Tees / Hoodies (8 Ball)", "category": "Clothing", "demand": "high", "best_batch": "—", "price_range": "$10–20", "subreddits": "FashionReps, RepBudgetSneakers", "signal": "satisfaction"},
    {"brand": "Amiri", "item": "Jeans / Tees", "category": "Clothing", "demand": "high", "best_batch": "—", "price_range": "$20–45", "subreddits": "QualityReps, DesignerReps", "signal": "request"},
    {"brand": "Off-White", "item": "Tees / Hoodies / Belts", "category": "Clothing", "demand": "moderate", "best_batch": "—", "price_range": "$10–30", "subreddits": "FashionReps", "signal": "request"},
    # Outerwear — seasonal prep
    {"brand": "Moncler", "item": "Maya Jacket / Vest", "category": "Outerwear", "demand": "high", "best_batch": "—", "price_range": "$50–90", "subreddits": "FashionReps, DesignerReps", "signal": "request"},
    {"brand": "Stone Island", "item": "Sweatshirts / Cargos", "category": "Outerwear", "demand": "high", "best_batch": "TopStoney", "price_range": "$20–40", "subreddits": "FashionReps", "signal": "ownership"},
    {"brand": "Arc'teryx", "item": "Beta LT / Shells", "category": "Outerwear", "demand": "high", "best_batch": "—", "price_range": "$40–70", "subreddits": "FashionReps, QualityReps", "signal": "request"},
    {"brand": "The North Face", "item": "Nuptse / Supreme Collab", "category": "Outerwear", "demand": "moderate", "best_batch": "—", "price_range": "$30–55", "subreddits": "FashionReps", "signal": "request"},
    # Luxury bags & accessories
    {"brand": "Louis Vuitton", "item": "Keepall / Neverfull", "category": "Bags", "demand": "very_high", "best_batch": "—", "price_range": "$45–120", "subreddits": "DesignerReps, FashionReps", "signal": "request"},
    {"brand": "Dior", "item": "Saddle Bag / B23", "category": "Bags", "demand": "high", "best_batch": "—", "price_range": "$40–90", "subreddits": "DesignerReps", "signal": "request"},
    {"brand": "Balenciaga", "item": "City Bag (comeback)", "category": "Bags", "demand": "high", "best_batch": "—", "price_range": "$45–85", "subreddits": "DesignerReps", "signal": "request"},
    {"brand": "Bottega Veneta", "item": "Cassette Bag", "category": "Bags", "demand": "high", "best_batch": "—", "price_range": "$50–100", "subreddits": "DesignerReps, LuxuryReps", "signal": "request"},
    {"brand": "Chanel", "item": "Classic Flap", "category": "Bags", "demand": "very_high", "best_batch": "—", "price_range": "$60–120", "subreddits": "DesignerReps, LuxuryReps", "signal": "request"},
    {"brand": "Prada / Miu Miu", "item": "Leather Goods", "category": "Bags", "demand": "rising", "best_batch": "—", "price_range": "$40–90", "subreddits": "DesignerReps", "signal": "request"},
]

# Batch quality guide — community consensus
BATCH_GUIDE: list[dict] = [
    {"shoe": "Jordan 1 (all colorways)", "best_batch": "LJR", "alt_batch": "OG", "tier": "Top", "notes": "Accurate shape, quality leather, flawless logos"},
    {"shoe": "Jordan 4 (all colorways)", "best_batch": "PK", "alt_batch": "LJR", "tier": "Top", "notes": "Best consistency and material quality"},
    {"shoe": "Nike Dunk Low", "best_batch": "M Batch", "alt_batch": "VT", "tier": "Top", "notes": "Best value-to-quality ratio across colorways"},
    {"shoe": "Off-White collabs", "best_batch": "OG", "alt_batch": "LJR", "tier": "Top", "notes": "Highest attention to detail on collab elements"},
    {"shoe": "Yeezy 350 V2", "best_batch": "PK BASF", "alt_batch": "LW", "tier": "Top", "notes": "BASF boost matches retail feel"},
    {"shoe": "Yeezy 700", "best_batch": "PK", "alt_batch": "OG", "tier": "Top", "notes": "Best overall shape and boost quality"},
    {"shoe": "Travis Scott AJ1", "best_batch": "LJR", "alt_batch": "GD", "tier": "Top", "notes": "Best suede quality and reverse swoosh placement"},
    {"shoe": "Travis Scott AJ4", "best_batch": "PK", "alt_batch": "LJR", "tier": "Top", "notes": "Closest materials and speckling to retail"},
    {"shoe": "Balenciaga Speed/Track", "best_batch": "GT", "alt_batch": "PK", "tier": "Mid", "notes": "Good text placement and knit quality"},
    {"shoe": "New Balance 550/9060", "best_batch": "—", "alt_batch": "H12", "tier": "Mid", "notes": "Improving; check recent QCs before buying"},
    {"shoe": "Adidas Samba", "best_batch": "H12", "alt_batch": "—", "tier": "Mid", "notes": "Budget-friendly; good for the price point"},
]

# 2026 upcoming hype releases driving future demand
UPCOMING_RELEASES: list[dict] = [
    {"item": "Travis Scott x AJ1 Low OG 'Pink Pack'", "brand": "Jordan / Travis Scott", "release": "Summer 2026", "hype": "very_high", "category": "Sneakers"},
    {"item": "J Balvin x Air Jordan 4", "brand": "Jordan / J Balvin", "release": "2026", "hype": "high", "category": "Sneakers"},
    {"item": "Virgil Abloh x Air Jordan 1 (new branding)", "brand": "Jordan / Virgil Abloh", "release": "2026", "hype": "very_high", "category": "Sneakers"},
    {"item": "Jordan Bin23 Series (limited craft)", "brand": "Jordan", "release": "2026", "hype": "high", "category": "Sneakers"},
    {"item": "Nike SB Dunk Low (new collabs)", "brand": "Nike SB", "release": "Ongoing 2026", "hype": "high", "category": "Sneakers"},
    {"item": "Caitlin Clark Nike Signature", "brand": "Nike", "release": "2026", "hype": "moderate", "category": "Sneakers"},
    {"item": "Nike LD-1000 Retro ('70s revival)", "brand": "Nike", "release": "Spring 2026", "hype": "moderate", "category": "Sneakers"},
]

# Subreddit community metrics
SUBREDDIT_STATS: list[dict] = [
    {"subreddit": "r/FashionReps", "members": 2_200_000, "signal_weight": 1.5, "focus": "General fashion reps", "top_brands": "FOG Essentials, Chrome Hearts, Supreme"},
    {"subreddit": "r/Repsneakers", "members": 969_000, "signal_weight": 1.5, "focus": "Sneaker reps", "top_brands": "Jordan, Nike Dunk, Yeezy"},
    {"subreddit": "r/DesignerReps", "members": 450_000, "signal_weight": 1.5, "focus": "Luxury & designer", "top_brands": "LV, Gucci, Dior, Balenciaga"},
    {"subreddit": "r/QualityReps", "members": 320_000, "signal_weight": 1.5, "focus": "High-quality/archive", "top_brands": "Raf Simons, Margiela, Chrome Hearts"},
    {"subreddit": "r/RepBudgetSneakers", "members": 229_000, "signal_weight": 1.3, "focus": "Budget sneaker finds", "top_brands": "Nike Dunk, Jordan 1, Samba"},
    {"subreddit": "r/FashionRepsBST", "members": 180_000, "signal_weight": 1.4, "focus": "Buy/Sell/Trade", "top_brands": "Supreme, Jordan, Off-White"},
    {"subreddit": "r/CloseToRetail", "members": 85_000, "signal_weight": 1.3, "focus": "Near-1:1 quality reps", "top_brands": "Jordan, Dunk, Yeezy"},
    {"subreddit": "r/WeidianWarriors", "members": 65_000, "signal_weight": 1.1, "focus": "Weidian finds/deals", "top_brands": "Budget picks, various"},
    {"subreddit": "r/1688Reps", "members": 45_000, "signal_weight": 1.2, "focus": "1688 bulk/budget", "top_brands": "Basics, bags, accessories"},
]

# Demand level numeric mapping for scoring
_DEMAND_SCORE = {"very_high": 1.0, "high": 0.75, "rising": 0.65, "moderate": 0.5, "cooling": 0.3}
_TREND_SCORE = {"rising": 1.0, "stable": 0.6, "cooling": 0.2}


def get_external_trending() -> list[dict]:
    """Return curated external trending items."""
    return REDDIT_TRENDING


def get_weidian_sales() -> list[dict]:
    """Return Weidian live sales data."""
    return WEIDIAN_TOP_SELLERS


def get_1688_sales() -> list[dict]:
    """Return 1688 live sales data."""
    return PLATFORM_1688_TOP


def get_batch_guide() -> list[dict]:
    """Return batch quality guide."""
    return BATCH_GUIDE


def get_upcoming_releases() -> list[dict]:
    """Return upcoming hype releases."""
    return UPCOMING_RELEASES


def get_subreddit_stats() -> list[dict]:
    """Return subreddit community stats."""
    return SUBREDDIT_STATS


def category_breakdown() -> list[dict]:
    """Break down external trending items by category."""
    cats: dict[str, dict] = defaultdict(lambda: {
        "very_high": 0, "high": 0, "moderate": 0, "rising": 0, "total": 0,
    })
    for item in REDDIT_TRENDING:
        c = cats[item["category"]]
        c[item["demand"]] = c.get(item["demand"], 0) + 1
        c["total"] += 1
    return [{"category": k, **v} for k, v in sorted(cats.items(), key=lambda x: -x[1]["total"])]


def platform_comparison() -> list[dict]:
    """Compare sales data across Weidian and 1688."""
    results = []
    for item in WEIDIAN_TOP_SELLERS:
        results.append({**item, "source": "Weidian"})
    for item in PLATFORM_1688_TOP:
        results.append({**item, "source": "1688"})
    results.sort(key=lambda x: -x["units_sold"])
    return results


def purchase_recommendations(conn: sqlite3.Connection | None = None,
                             since: str | None = None,
                             platform: str | None = None) -> list[dict]:
    """Generate scored purchase recommendations combining external trends
    with internal demand data when available."""
    recs: dict[str, dict] = {}

    # Score external trending items
    for item in REDDIT_TRENDING:
        key = f"{item['brand']}|{item['item']}"
        ext_score = _DEMAND_SCORE.get(item["demand"], 0.5)
        recs[key] = {
            "brand": item["brand"],
            "item": item["item"],
            "category": item["category"],
            "external_score": round(ext_score, 2),
            "internal_score": 0.0,
            "combined_score": 0.0,
            "best_batch": item.get("best_batch", "—"),
            "price_range": item.get("price_range", "—"),
            "subreddits": item.get("subreddits", "—"),
            "demand_level": item["demand"],
            "recommendation": "",
        }

    # Boost from Weidian/1688 actual sales data
    for item in WEIDIAN_TOP_SELLERS + PLATFORM_1688_TOP:
        key = f"{item['brand']}|{item['item']}"
        trend_boost = _TREND_SCORE.get(item["trend"], 0.5)
        vol_boost = min(item["units_sold"] / 300, 1.0)  # normalize to 0-1
        if key in recs:
            recs[key]["external_score"] = round(
                min(recs[key]["external_score"] + (trend_boost * 0.15) + (vol_boost * 0.15), 1.0), 2
            )
        else:
            recs[key] = {
                "brand": item["brand"],
                "item": item["item"],
                "category": item["category"],
                "external_score": round(0.4 + (trend_boost * 0.2) + (vol_boost * 0.2), 2),
                "internal_score": 0.0,
                "combined_score": 0.0,
                "best_batch": "—",
                "price_range": "—",
                "subreddits": "—",
                "demand_level": item["trend"],
                "recommendation": "",
            }

    # Enrich with internal DB data when available
    if conn:
        try:
            plat_clause = " AND message_id IN (SELECT id FROM raw_messages WHERE source_platform = ?)" if platform else ""
            plat_params = [platform] if platform else []
            since_clause = " AND timestamp >= ?" if since else ""
            since_params = [since] if since else []

            rows = conn.execute(f"""
                SELECT brand, item,
                       COUNT(*) as total,
                       SUM(CASE WHEN intent_type='request' THEN 1 ELSE 0 END) as requests,
                       SUM(CASE WHEN intent_type='regret' THEN 1 ELSE 0 END) as regret,
                       SUM(CASE WHEN intent_type='ownership' THEN 1 ELSE 0 END) as owned,
                       SUM(CASE WHEN intent_type='satisfaction' THEN 1 ELSE 0 END) as satisfied,
                       AVG(intent_score) as avg_score
                FROM processed_mentions
                WHERE (brand IS NOT NULL OR item IS NOT NULL)
                {plat_clause}{since_clause}
                GROUP BY brand, item
                HAVING total >= 2
            """, plat_params + since_params).fetchall()

            if rows:
                max_total = max(r["total"] for r in rows)
                for r in rows:
                    brand = r["brand"] or "Various"
                    item_name = r["item"] or "general"
                    for key, rec in recs.items():
                        if (brand.lower() in rec["brand"].lower()
                                or rec["brand"].lower() in brand.lower()):
                            vol_norm = r["total"] / max(max_total, 1)
                            intent_w = (r["requests"] * 0.8 + r["regret"] * 1.0
                                        + r["satisfied"] * 0.6 + r["owned"] * 0.4)
                            max_w = r["total"] * 1.0
                            intent_norm = intent_w / max(max_w, 1)
                            rec["internal_score"] = round(
                                min(0.5 * intent_norm + 0.3 * vol_norm + 0.2 * r["avg_score"], 1.0), 2
                            )
                            break
        except Exception as e:
            log.warning("Could not enrich with internal data: %s", e)

    # Compute combined score and generate recommendations
    for rec in recs.values():
        if rec["internal_score"] > 0:
            rec["combined_score"] = round(0.5 * rec["external_score"] + 0.5 * rec["internal_score"], 2)
        else:
            rec["combined_score"] = rec["external_score"]

        # Generate recommendation text
        if rec["combined_score"] >= 0.85:
            rec["recommendation"] = "BUY NOW — Top priority, very high demand"
        elif rec["combined_score"] >= 0.7:
            rec["recommendation"] = "STRONG BUY — High demand, stock immediately"
        elif rec["combined_score"] >= 0.55:
            rec["recommendation"] = "BUY — Good opportunity, solid demand"
        elif rec["combined_score"] >= 0.4:
            rec["recommendation"] = "WATCH — Monitor closely, moderate demand"
        else:
            rec["recommendation"] = "HOLD — Lower priority, check trends"

    result = sorted(recs.values(), key=lambda x: -x["combined_score"])
    return result


def demand_heatmap_data() -> list[dict]:
    """Prepare data for a brand x category demand heatmap."""
    data: dict[tuple, float] = defaultdict(float)
    for item in REDDIT_TRENDING:
        key = (item["brand"], item["category"])
        data[key] += _DEMAND_SCORE.get(item["demand"], 0.5)

    results = []
    for (brand, cat), score in data.items():
        results.append({"brand": brand, "category": cat, "demand_score": round(score, 2)})
    return sorted(results, key=lambda x: -x["demand_score"])


def trend_direction_summary() -> list[dict]:
    """Summarize trend directions across all Weidian/1688 items."""
    counts = defaultdict(int)
    for item in WEIDIAN_TOP_SELLERS + PLATFORM_1688_TOP:
        counts[item["trend"]] += 1
    return [{"direction": k, "count": v} for k, v in counts.items()]
