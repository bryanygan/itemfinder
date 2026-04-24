"""Bulk-buy ROI analysis for $/kg shipping reality.

Given a per-kg shipping rate (default $13/kg, typical for volumetric air
shipping from a Chinese agent to the US/EU), this module ranks curated
rep-scene items by profit-per-kilogram-shipped — the metric that actually
matters when you're bulk-buying and shipping in one consolidated parcel.

The fundamental insight: sneakers look great in rep subs but get crushed
once shipping is factored in (1.2–1.5 kg each, with volumetric penalties
from the shoebox). Jewelry, belts, caps, sunglasses, wallets, socks, and
tees destroy sneakers on ROI/kg because they weigh a fraction and still
resell for $30–$120.

Data below comes from cross-referencing src/analytics/market_intel.py
(REDDIT_TRENDING, WEIDIAN_TOP_SELLERS, PURCHASE_LINKS), typical rep-scene
pricing observed on Weidian/Yupoo in April 2026, and real-world item
weights measured for comparable items.

Use BULK_BUY_ITEMS directly, or call compute_roi(rate_per_kg) to get a
ranked list with all-in costs, net margins, and profit-per-kg-shipped.
"""

from __future__ import annotations

from src.analytics.market_intel import PURCHASE_LINKS

# ── Shipping math ────────────────────────────────────────────────────────

DEFAULT_SHIPPING_RATE_USD_PER_KG = 13.0

# Volumetric multiplier: bulky items (shoes, large bags) pay for the box,
# not just the physical weight. 1.0 = density matches shipping formula;
# 1.3 = 30% penalty because the item dimensionally weighs more than it
# actually weighs. Based on typical agent shipping formulas (volume÷6000).
VOLUMETRIC_MULTIPLIER = {
    "Jewelry": 1.0,       # tiny, pack tight
    "Accessories": 1.0,   # belts, caps, wallets compress well
    "Eyewear": 1.05,      # case adds a little air
    "Socks": 1.0,
    "Tops": 1.05,         # folded tees/tanks, minor penalty
    "Hoodies": 1.15,      # thicker, more air
    "Bottoms": 1.1,
    "Outerwear": 1.3,     # puffers & shells take space
    "Sneakers": 1.35,     # shoebox = worst-case volumetric
    "Bags": 1.25,         # hollow, variable
    "Denim": 1.1,
}


# ── Curated bulk-buy candidates ──────────────────────────────────────────
# Each entry: realistic shipped weight (grams), rep cost range (USD),
# resell range (USD), and category. Weights include minimal packaging but
# assume bulk consolidation (no individual retail boxes).

BULK_BUY_ITEMS: list[dict] = [
    # ── TIER 1: Jewelry — highest profit density ─────────────────────────
    {
        "brand": "Chrome Hearts", "item": "Silver Ring (CH Plus / Dagger)",
        "category": "Jewelry", "weight_g": 35,
        "rep_cost_low": 20, "rep_cost_high": 45,
        "resell_low": 70, "resell_high": 130,
        "min_bulk_qty": 10,
        "tier": 1, "seasonal": "all-season",
        "subreddits": "QualityReps, FashionReps, DesignerReps",
        "notes": "patternerpp.x.yupoo.com — pack tight in small pouches. Nearly 100% margin per gram.",
        "why_good": "Tiniest footprint + highest markup multiplier in the entire market. Ship 30 pieces in under 1.1 kg.",
    },
    {
        "brand": "Chrome Hearts", "item": "Cross Pendant Necklace",
        "category": "Jewelry", "weight_g": 80,
        "rep_cost_low": 40, "rep_cost_high": 80,
        "resell_low": 120, "resell_high": 220,
        "min_bulk_qty": 5,
        "tier": 1,
        "subreddits": "QualityReps, DesignerReps, FashionReps",
        "notes": "Heavier silver = better perceived quality. Ship in a small jewelry box (negligible volumetric).",
        "why_good": "Flagship CH silver piece — consistent resale demand and Instagram-driven buyers.",
    },
    {
        "brand": "Chrome Hearts", "item": "Bracelet / Bangle",
        "category": "Jewelry", "weight_g": 55,
        "rep_cost_low": 30, "rep_cost_high": 60,
        "resell_low": 90, "resell_high": 160,
        "min_bulk_qty": 8,
        "tier": 1,
        "subreddits": "QualityReps, FashionReps",
        "notes": "Pairs well with ring sets. Pack 8–10 in a small parcel.",
        "why_good": "Low weight, broad appeal (unisex), easy to resell in sets.",
    },
    {
        "brand": "Gallery Dept", "item": "Chain / Charm Necklace",
        "category": "Jewelry", "weight_g": 60,
        "rep_cost_low": 25, "rep_cost_high": 50,
        "resell_low": 75, "resell_high": 140,
        "min_bulk_qty": 6,
        "tier": 1,
        "subreddits": "FashionReps, QualityReps",
        "notes": "Painted brass charms. Lower ceiling than CH but cheaper source cost.",
        "why_good": "Rising brand equity, sub-$1 shipping per piece.",
    },

    # ── TIER 1: Accessories — small, high margin ─────────────────────────
    {
        "brand": "Louis Vuitton", "item": "Monogram Belt",
        "category": "Accessories", "weight_g": 260,
        "rep_cost_low": 25, "rep_cost_high": 40,
        "resell_low": 85, "resell_high": 135,
        "min_bulk_qty": 5,
        "tier": 1,
        "subreddits": "DesignerReps, FashionReps",
        "notes": "Coil tightly, one per 260 g. Buyers always want LV belts — evergreen demand.",
        "why_good": "LV belts are the #1 entry-level designer flex. High unit velocity on Depop/Instagram.",
    },
    {
        "brand": "Off-White", "item": "Industrial Belt",
        "category": "Accessories", "weight_g": 220,
        "rep_cost_low": 15, "rep_cost_high": 25,
        "resell_low": 55, "resell_high": 95,
        "min_bulk_qty": 8,
        "tier": 1,
        "subreddits": "FashionReps",
        "notes": "Nylon — even lighter than leather. FakeLab or similar Weidian sellers.",
        "why_good": "Cheapest-to-source designer accessory. 3–4x markup common.",
    },
    {
        "brand": "Various", "item": "Leather Belt (generic designer)",
        "category": "Accessories", "weight_g": 250,
        "rep_cost_low": 10, "rep_cost_high": 20,
        "resell_low": 45, "resell_high": 80,
        "min_bulk_qty": 10,
        "tier": 1,
        "subreddits": "WeidianWarriors, 1688Reps",
        "notes": "1688 direct sourcing. WEIDIAN_TOP_SELLERS rank 9 (118 units/30d). Bulk-friendly.",
        "why_good": "1688 bulk pricing unlocks the highest % margin of any item on this list.",
    },
    {
        "brand": "Corteiz", "item": "CRTZ Fitted Cap",
        "category": "Accessories", "weight_g": 130,
        "rep_cost_low": 12, "rep_cost_high": 20,
        "resell_low": 38, "resell_high": 65,
        "min_bulk_qty": 10,
        "tier": 1,
        "subreddits": "FashionReps",
        "notes": "UK streetwear trending. Pack flat — caps crush to half-depth.",
        "why_good": "Cultural momentum (Corteiz cult following). Light enough to stack 10+ in 1.5 kg.",
    },
    {
        "brand": "Trapstar", "item": "Chenille Logo Cap",
        "category": "Accessories", "weight_g": 130,
        "rep_cost_low": 12, "rep_cost_high": 20,
        "resell_low": 35, "resell_high": 55,
        "min_bulk_qty": 10,
        "tier": 1,
        "subreddits": "FashionReps",
        "notes": "UK grime co-sign. Slightly lower ceiling than Corteiz but steady demand.",
        "why_good": "Low unit cost, zero volumetric penalty, fast-moving category.",
    },
    {
        "brand": "Supreme", "item": "Box Logo New Era Cap",
        "category": "Accessories", "weight_g": 140,
        "rep_cost_low": 15, "rep_cost_high": 25,
        "resell_low": 40, "resell_high": 70,
        "min_bulk_qty": 8,
        "tier": 1,
        "subreddits": "FashionReps, QualityReps",
        "notes": "Seasonal colorways — check current Supreme drops for hottest colors.",
        "why_good": "Evergreen hypebeast staple. Caps are the #1 lightweight margin play.",
    },
    {
        "brand": "Chrome Hearts", "item": "Sunglasses (Boink! / Sweet Leaf)",
        "category": "Eyewear", "weight_g": 170,
        "rep_cost_low": 35, "rep_cost_high": 60,
        "resell_low": 110, "resell_high": 200,
        "min_bulk_qty": 5,
        "tier": 1,
        "subreddits": "QualityReps, DesignerReps, FashionReps",
        "notes": "Retail $1000+. Rep sunglasses have one of the highest absolute margins per unit.",
        "why_good": "High-absolute-dollar margin in a light package. Ship without retail case to save 80g.",
    },
    {
        "brand": "Balenciaga", "item": "Shield Sunglasses",
        "category": "Eyewear", "weight_g": 180,
        "rep_cost_low": 30, "rep_cost_high": 55,
        "resell_low": 90, "resell_high": 160,
        "min_bulk_qty": 5,
        "tier": 1,
        "subreddits": "FashionReps, DesignerReps",
        "notes": "Still iconic despite brand controversy — demand softer than 2022 but stable.",
        "why_good": "Eye-catching resale pieces, sub-$2 shipping each.",
    },
    {
        "brand": "Louis Vuitton", "item": "Compact Wallet / Card Holder",
        "category": "Accessories", "weight_g": 130,
        "rep_cost_low": 18, "rep_cost_high": 35,
        "resell_low": 65, "resell_high": 110,
        "min_bulk_qty": 8,
        "tier": 1,
        "subreddits": "DesignerReps, FashionReps",
        "notes": "Palm-sized. Search DesignerReps for HyperPeter / Old Cobbler recs.",
        "why_good": "Wallets ship like envelopes. Great gift-market resale around holidays.",
    },
    {
        "brand": "Chanel", "item": "Classic Card Holder",
        "category": "Accessories", "weight_g": 120,
        "rep_cost_low": 20, "rep_cost_high": 40,
        "resell_low": 75, "resell_high": 130,
        "min_bulk_qty": 6,
        "tier": 1,
        "subreddits": "DesignerReps, LuxuryReps",
        "notes": "Quilted caviar/lamb leather small goods — female buyer base = high ticket.",
        "why_good": "Female-driven resale market, lower competition than men's reps.",
    },

    # ── TIER 2: Softs — good stackers ────────────────────────────────────
    {
        "brand": "Fear of God", "item": "Essentials Tee",
        "category": "Tops", "weight_g": 210,
        "rep_cost_low": 15, "rep_cost_high": 22,
        "resell_low": 35, "resell_high": 55,
        "min_bulk_qty": 12,
        "tier": 2,
        "subreddits": "FashionReps, 1688Reps",
        "notes": "Singor/Gman Weidian. Stack tightly — 10 tees = ~2.2 kg.",
        "why_good": "Highest-velocity streetwear tee. Essentials has mass retail recognition.",
    },
    {
        "brand": "Sp5der", "item": "Web Logo Tee",
        "category": "Tops", "weight_g": 220,
        "rep_cost_low": 10, "rep_cost_high": 18,
        "resell_low": 32, "resell_high": 55,
        "min_bulk_qty": 15,
        "tier": 2,
        "subreddits": "FashionReps",
        "notes": "ayfactory Yupoo. Buyer base leans younger — TikTok-driven demand.",
        "why_good": "Among the cheapest source costs on this list; rising brand.",
    },
    {
        "brand": "Gallery Dept", "item": "ATK Logo Tee",
        "category": "Tops", "weight_g": 210,
        "rep_cost_low": 15, "rep_cost_high": 25,
        "resell_low": 45, "resell_high": 70,
        "min_bulk_qty": 12,
        "tier": 2,
        "subreddits": "QualityReps, FashionReps",
        "notes": "Painted-splatter detail — QC photos essential for batch variance.",
        "why_good": "Highest resale ceiling of the streetwear tees. Still rising.",
    },
    {
        "brand": "Chrome Hearts", "item": "Dagger / Cross Tee",
        "category": "Tops", "weight_g": 230,
        "rep_cost_low": 20, "rep_cost_high": 35,
        "resell_low": 60, "resell_high": 95,
        "min_bulk_qty": 10,
        "tier": 2,
        "subreddits": "QualityReps, FashionReps, DesignerReps",
        "notes": "Heavyweight cotton — denser than standard streetwear tees but higher margin.",
        "why_good": "CH premium branding = highest-dollar tee margin in the rep market.",
    },
    {
        "brand": "Supreme", "item": "Box Logo Tee",
        "category": "Tops", "weight_g": 200,
        "rep_cost_low": 12, "rep_cost_high": 18,
        "resell_low": 35, "resell_high": 55,
        "min_bulk_qty": 15,
        "tier": 2,
        "subreddits": "FashionReps, QualityReps",
        "notes": "Mirror/Teenage Club Weidian. Seasonal colors move fastest.",
        "why_good": "Core hypebeast staple — always sells.",
    },
    {
        "brand": "Stussy", "item": "8 Ball Tee",
        "category": "Tops", "weight_g": 200,
        "rep_cost_low": 10, "rep_cost_high": 15,
        "resell_low": 25, "resell_high": 40,
        "min_bulk_qty": 15,
        "tier": 2,
        "subreddits": "FashionReps, RepBudgetSneakers",
        "notes": "Budget entry point. Good for high-volume low-margin strategy.",
        "why_good": "Cheapest source cost in streetwear tees — thin absolute margin but high unit velocity.",
    },
    {
        "brand": "Supreme", "item": "Logo Crew Socks (pack)",
        "category": "Socks", "weight_g": 80,
        "rep_cost_low": 6, "rep_cost_high": 10,
        "resell_low": 18, "resell_high": 30,
        "min_bulk_qty": 20,
        "tier": 2,
        "subreddits": "FashionReps",
        "notes": "Sell in 3-packs. Ship 25 pairs in ~2 kg.",
        "why_good": "Highest units-per-kilogram on this list. Low friction impulse buys.",
    },

    # ── TIER 3: Mid-weight — still good but watch weight ─────────────────
    {
        "brand": "Fear of God", "item": "Essentials Hoodie (thin)",
        "category": "Hoodies", "weight_g": 520,
        "rep_cost_low": 25, "rep_cost_high": 35,
        "resell_low": 75, "resell_high": 115,
        "min_bulk_qty": 6,
        "tier": 3,
        "subreddits": "FashionReps, 1688Reps",
        "notes": "Compress with vacuum bag to cut volumetric. 4-5 fit in a 2.5 kg parcel.",
        "why_good": "Highest-demand rep hoodie (WEIDIAN rank 12, Reddit very_high). Margin absorbs the weight.",
    },
    {
        "brand": "Sp5der", "item": "Web Hoodie",
        "category": "Hoodies", "weight_g": 500,
        "rep_cost_low": 15, "rep_cost_high": 25,
        "resell_low": 60, "resell_high": 95,
        "min_bulk_qty": 5,
        "tier": 3,
        "subreddits": "FashionReps",
        "notes": "Cheaper source than Essentials — ratio of profit/kg better at low end.",
        "why_good": "Best margin-per-kg among hoodies thanks to sub-$25 source cost.",
    },
    {
        "brand": "Various", "item": "Streetwear Shorts (Essentials/Stussy)",
        "category": "Bottoms", "weight_g": 270,
        "rep_cost_low": 15, "rep_cost_high": 25,
        "resell_low": 45, "resell_high": 75,
        "min_bulk_qty": 10,
        "tier": 2,
        "subreddits": "FashionReps",
        "notes": "Summer-skew demand — stock March–July. Light enough to bulk.",
        "why_good": "Summer cash cow — ships at half the weight of hoodies.",
    },

    # ── AVOID tier included so buyers see why to skip ──────────────────
    {
        "brand": "Jordan", "item": "Jordan 1 High (any colorway)",
        "category": "Sneakers", "weight_g": 1350,
        "rep_cost_low": 45, "rep_cost_high": 65,
        "resell_low": 130, "resell_high": 180,
        "min_bulk_qty": 4,
        "tier": 4,
        "subreddits": "Repsneakers, FashionReps, QualityReps",
        "notes": "1.35 kg with box (or 0.9 kg without). Volumetric penalty 1.35x. Better domestic-retail than bulk-ship.",
        "why_good": "AVOID for bulk — shipping eats 40–50% of margin. Only worth it for single-unit orders or high-demand retros.",
    },
    {
        "brand": "Nike", "item": "Dunk Low",
        "category": "Sneakers", "weight_g": 1250,
        "rep_cost_low": 25, "rep_cost_high": 40,
        "resell_low": 90, "resell_high": 130,
        "min_bulk_qty": 4,
        "tier": 4,
        "subreddits": "Repsneakers, RepBudgetSneakers, WeidianWarriors",
        "notes": "M Batch Weidian. Same weight problem — margin shrinks fast under shipping.",
        "why_good": "AVOID for bulk — per-unit shipping $21.90 volumetric. Only worth at quantity 2-3 max.",
    },
    {
        "brand": "Moncler", "item": "Maya Jacket",
        "category": "Outerwear", "weight_g": 950,
        "rep_cost_low": 50, "rep_cost_high": 90,
        "resell_low": 180, "resell_high": 280,
        "min_bulk_qty": 2,
        "tier": 4,
        "subreddits": "FashionReps, DesignerReps",
        "notes": "Volumetric penalty 1.3x — compressed puffers still ship heavy by volume.",
        "why_good": "AVOID for bulk — seasonal, volumetric-heavy. Single-pair orders in October only.",
    },
    {
        "brand": "The North Face", "item": "Nuptse Puffer",
        "category": "Outerwear", "weight_g": 1000,
        "rep_cost_low": 30, "rep_cost_high": 55,
        "resell_low": 100, "resell_high": 160,
        "min_bulk_qty": 2,
        "tier": 4,
        "subreddits": "FashionReps",
        "notes": "1688 rank 6 COOLING. Seasonal cooling further hurts margin.",
        "why_good": "AVOID — cooling demand + high volumetric weight + end of winter season.",
    },
    {
        "brand": "Louis Vuitton", "item": "Keepall 50 (duffle)",
        "category": "Bags", "weight_g": 1200,
        "rep_cost_low": 60, "rep_cost_high": 120,
        "resell_low": 210, "resell_high": 350,
        "min_bulk_qty": 2,
        "tier": 4,
        "subreddits": "DesignerReps, FashionReps",
        "notes": "Hollow = enormous volumetric. Flatten if possible, but still 1.25x penalty.",
        "why_good": "AVOID for bulk — large bags are volumetric nightmares. Single-unit drop-ship only.",
    },

    # ══════════════════════════════════════════════════════════════════════
    # SUMMER 2026 PICKS — approaching season, heavy demand curve starting now
    # Buy window: late April through July. Demand peaks June–August.
    # ══════════════════════════════════════════════════════════════════════
    {
        "brand": "Supreme", "item": "Bucket Hat (seasonal print)",
        "category": "Accessories", "weight_g": 115,
        "rep_cost_low": 14, "rep_cost_high": 22,
        "resell_low": 40, "resell_high": 70,
        "min_bulk_qty": 10,
        "tier": 1, "seasonal": "summer",
        "subreddits": "FashionReps, QualityReps",
        "notes": "Summer-peak demand (beach/festival season). Fold crushed for shipping.",
        "why_good": "SUMMER: Bucket hats 3x demand spike June-August. Ultra-light + high markup.",
    },
    {
        "brand": "Corteiz", "item": "Alcatraz Bucket Hat",
        "category": "Accessories", "weight_g": 110,
        "rep_cost_low": 12, "rep_cost_high": 20,
        "resell_low": 38, "resell_high": 60,
        "min_bulk_qty": 10,
        "tier": 1, "seasonal": "summer",
        "subreddits": "FashionReps",
        "notes": "UK-driven summer streetwear. Pairs with their cargo shorts.",
        "why_good": "SUMMER: Corteiz cult momentum plus festival-season peak = fast-mover.",
    },
    {
        "brand": "Prada", "item": "Nylon Bucket Hat (triangle logo)",
        "category": "Accessories", "weight_g": 140,
        "rep_cost_low": 18, "rep_cost_high": 30,
        "resell_low": 55, "resell_high": 95,
        "min_bulk_qty": 8,
        "tier": 1, "seasonal": "summer",
        "subreddits": "DesignerReps, FashionReps",
        "notes": "Still hot 4 years after the initial wave. Women's market drives summer resale.",
        "why_good": "SUMMER: Designer bucket flex. Highest resale ceiling of the bucket category.",
    },
    {
        "brand": "Chrome Hearts", "item": "Trucker / Mesh Cap",
        "category": "Accessories", "weight_g": 135,
        "rep_cost_low": 18, "rep_cost_high": 30,
        "resell_low": 55, "resell_high": 95,
        "min_bulk_qty": 8,
        "tier": 1, "seasonal": "summer",
        "subreddits": "QualityReps, FashionReps",
        "notes": "Trucker (mesh) style beats fitted for summer breathability demand.",
        "why_good": "SUMMER: CH trucker caps are the highest-ceiling summer headwear pick.",
    },
    {
        "brand": "Chrome Hearts", "item": "Silver Sunglasses (Boink! Summer)",
        "category": "Eyewear", "weight_g": 165,
        "rep_cost_low": 35, "rep_cost_high": 60,
        "resell_low": 115, "resell_high": 210,
        "min_bulk_qty": 6,
        "tier": 1, "seasonal": "summer",
        "subreddits": "QualityReps, DesignerReps, FashionReps",
        "notes": "Peak season for eyewear runs May–August. Same unit as all-season listing — stock deeper now.",
        "why_good": "SUMMER: Sunglasses demand doubles in summer. Double your jewelry-adjacent allocation.",
    },
    {
        "brand": "Fear of God", "item": "Essentials Shorts",
        "category": "Bottoms", "weight_g": 250,
        "rep_cost_low": 18, "rep_cost_high": 28,
        "resell_low": 55, "resell_high": 85,
        "min_bulk_qty": 10,
        "tier": 2, "seasonal": "summer",
        "subreddits": "FashionReps, 1688Reps",
        "notes": "Gman/Singor Weidian. Same brand anchor as Essentials hoodies but a third of the weight.",
        "why_good": "SUMMER: Essentials shorts outsell hoodies May–August and ship 50% lighter.",
    },
    {
        "brand": "Sp5der", "item": "Logo Shorts / Sweatshorts",
        "category": "Bottoms", "weight_g": 240,
        "rep_cost_low": 14, "rep_cost_high": 22,
        "resell_low": 48, "resell_high": 75,
        "min_bulk_qty": 10,
        "tier": 2, "seasonal": "summer",
        "subreddits": "FashionReps",
        "notes": "Matches the hoodie for bundled sets. TikTok-driven summer push.",
        "why_good": "SUMMER: Sp5der is festival-core for 2026. Bulk-friendly weight + cult demand.",
    },
    {
        "brand": "Gallery Dept", "item": "Painter Shorts",
        "category": "Bottoms", "weight_g": 280,
        "rep_cost_low": 22, "rep_cost_high": 35,
        "resell_low": 70, "resell_high": 115,
        "min_bulk_qty": 6,
        "tier": 2, "seasonal": "summer",
        "subreddits": "QualityReps, FashionReps",
        "notes": "Splatter-paint detail — request QC for even coverage.",
        "why_good": "SUMMER: Highest-resale-ceiling shorts on this list. Summer hype piece.",
    },
    {
        "brand": "Sp5der", "item": "Web Logo Tank Top",
        "category": "Tops", "weight_g": 160,
        "rep_cost_low": 10, "rep_cost_high": 18,
        "resell_low": 32, "resell_high": 55,
        "min_bulk_qty": 15,
        "tier": 2, "seasonal": "summer",
        "subreddits": "FashionReps",
        "notes": "Lighter than tee + same resale — summer-only win.",
        "why_good": "SUMMER: Tanks ship ~25% lighter than tees but resell for nearly the same.",
    },
    {
        "brand": "Gallery Dept", "item": "Sleeveless Painted Tank",
        "category": "Tops", "weight_g": 170,
        "rep_cost_low": 15, "rep_cost_high": 25,
        "resell_low": 45, "resell_high": 75,
        "min_bulk_qty": 10,
        "tier": 2, "seasonal": "summer",
        "subreddits": "QualityReps, FashionReps",
        "notes": "Summer festival flex. Layer with gold chains for Instagram merchandising.",
        "why_good": "SUMMER: Premium tank with 70%+ margin — fills Gallery Dept summer portfolio.",
    },
    {
        "brand": "Palm Angels", "item": "Logo Swim Shorts",
        "category": "Bottoms", "weight_g": 200,
        "rep_cost_low": 18, "rep_cost_high": 30,
        "resell_low": 55, "resell_high": 95,
        "min_bulk_qty": 8,
        "tier": 2, "seasonal": "summer",
        "subreddits": "FashionReps, DesignerReps",
        "notes": "Polyester = ultra-light. Miami / pool crowd buyer base.",
        "why_good": "SUMMER: Swim shorts are pure summer-only demand. Zero competition for reps.",
    },
    {
        "brand": "Versace", "item": "Barocco Swim Shorts",
        "category": "Bottoms", "weight_g": 200,
        "rep_cost_low": 22, "rep_cost_high": 38,
        "resell_low": 65, "resell_high": 120,
        "min_bulk_qty": 6,
        "tier": 2, "seasonal": "summer",
        "subreddits": "DesignerReps, FashionReps",
        "notes": "Bold prints = Instagram-driven summer resale.",
        "why_good": "SUMMER: Highest-ceiling rep swim shorts. Low competition in the rep scene.",
    },
    {
        "brand": "Polo Ralph Lauren", "item": "Big Pony Polo Shirt",
        "category": "Tops", "weight_g": 240,
        "rep_cost_low": 14, "rep_cost_high": 22,
        "resell_low": 42, "resell_high": 70,
        "min_bulk_qty": 12,
        "tier": 2, "seasonal": "summer",
        "subreddits": "FashionReps, RepBudgetSneakers",
        "notes": "Prep revival running through 2026. 1688 sourcing very cheap.",
        "why_good": "SUMMER: Polos are summer uniform for 18–25 buyers. High velocity, moderate margin.",
    },
    {
        "brand": "Casablanca", "item": "Silk Short-Sleeve Shirt",
        "category": "Tops", "weight_g": 230,
        "rep_cost_low": 20, "rep_cost_high": 35,
        "resell_low": 70, "resell_high": 120,
        "min_bulk_qty": 6,
        "tier": 2, "seasonal": "summer",
        "subreddits": "FashionReps, DesignerReps",
        "notes": "Silk/polyester prints — lightweight, high-design-value resale.",
        "why_good": "SUMMER: Underserved rep category. Tennis-club aesthetic trending hard.",
    },
    {
        "brand": "Adidas", "item": "Adilette Slides",
        "category": "Sneakers", "weight_g": 520,
        "rep_cost_low": 12, "rep_cost_high": 20,
        "resell_low": 35, "resell_high": 55,
        "min_bulk_qty": 6,
        "tier": 3, "seasonal": "summer",
        "subreddits": "RepBudgetSneakers, FashionReps",
        "notes": "Much lighter than full sneakers — ~500g per pair vs 1.3 kg.",
        "why_good": "SUMMER: Only footwear on this list that makes bulk-buy sense. Ship 15+ pairs per 10 kg.",
    },
    {
        "brand": "Yeezy", "item": "Slides (Pure / Bone / Onyx)",
        "category": "Sneakers", "weight_g": 550,
        "rep_cost_low": 18, "rep_cost_high": 28,
        "resell_low": 50, "resell_high": 80,
        "min_bulk_qty": 5,
        "tier": 3, "seasonal": "summer",
        "subreddits": "Repsneakers, RepBudgetSneakers",
        "notes": "Demand dipped post-Yeezy-beef but still strong summer pickup.",
        "why_good": "SUMMER: Yeezy slides move 2x in summer vs winter. Better margin than full sneaker reps.",
    },
    {
        "brand": "Balenciaga", "item": "Pool Slides",
        "category": "Sneakers", "weight_g": 580,
        "rep_cost_low": 22, "rep_cost_high": 35,
        "resell_low": 60, "resell_high": 100,
        "min_bulk_qty": 4,
        "tier": 3, "seasonal": "summer",
        "subreddits": "FashionReps, DesignerReps",
        "notes": "Designer slide flex — still strong despite brand cooldown.",
        "why_good": "SUMMER: Designer slides fill the luxury-casual summer slot. Decent bulk density.",
    },
]


# ── Analysis functions ──────────────────────────────────────────────────

def _billable_kg(weight_g: int, category: str) -> float:
    mult = VOLUMETRIC_MULTIPLIER.get(category, 1.1)
    return (weight_g * mult) / 1000.0


def _link_for(brand: str, item: str) -> str:
    """Fuzzy-match PURCHASE_LINKS for a best-link URL."""
    key = f"{brand}|{item}"
    info = PURCHASE_LINKS.get(key)
    if not info:
        b_low = brand.lower()
        for k, v in PURCHASE_LINKS.items():
            kb, ki = k.split("|", 1)
            if b_low in kb.lower() or kb.lower() in b_low:
                info = v
                break
    if not info:
        return ""
    return (info.get("weidian") or info.get("yupoo") or info.get("taobao")
            or info.get("spreadsheet") or info.get("resource") or "")


def compute_roi(rate_per_kg: float = DEFAULT_SHIPPING_RATE_USD_PER_KG,
                items: list[dict] | None = None) -> list[dict]:
    """Return items enriched with per-unit shipping, margin, and
    profit-per-kg-shipped, sorted by profit-per-kg descending.
    """
    source = items if items is not None else BULK_BUY_ITEMS
    out = []
    for it in source:
        cat = it["category"]
        avg_cost = (it["rep_cost_low"] + it["rep_cost_high"]) / 2
        avg_resell = (it["resell_low"] + it["resell_high"]) / 2
        billable_kg = _billable_kg(it["weight_g"], cat)
        unit_ship = round(billable_kg * rate_per_kg, 2)
        unit_profit = round(avg_resell - avg_cost - unit_ship, 2)
        margin_pct = round(unit_profit / avg_resell * 100, 1) if avg_resell else 0.0
        # Profit per kilogram of shipping consumed — the bulk-buy metric
        profit_per_kg = round(unit_profit / billable_kg, 2) if billable_kg else 0.0
        # Bulk parcel projection — how many units fit in a 10kg parcel
        units_per_10kg = int(10 / billable_kg) if billable_kg else 0

        out.append({
            **it,
            "avg_rep_cost": round(avg_cost, 2),
            "avg_resell": round(avg_resell, 2),
            "billable_kg": round(billable_kg, 3),
            "unit_shipping_usd": unit_ship,
            "unit_profit_usd": unit_profit,
            "margin_pct": margin_pct,
            "profit_per_kg_usd": profit_per_kg,
            "units_per_10kg": units_per_10kg,
            "total_profit_10kg": round(unit_profit * units_per_10kg, 2),
            "purchase_link": _link_for(it["brand"], it["item"]),
        })
    out.sort(key=lambda r: -r["profit_per_kg_usd"])
    return out


def top_roi_picks(rate_per_kg: float = DEFAULT_SHIPPING_RATE_USD_PER_KG,
                  top_n: int = 10,
                  exclude_avoid: bool = True) -> list[dict]:
    """Return the top N items by profit-per-kg. Optionally drop tier 4 (AVOID)."""
    enriched = compute_roi(rate_per_kg)
    if exclude_avoid:
        enriched = [r for r in enriched if r.get("tier") != 4]
    return enriched[:top_n]


def roi_by_tier(rate_per_kg: float = DEFAULT_SHIPPING_RATE_USD_PER_KG) -> dict:
    """Group ROI-enriched items by tier."""
    enriched = compute_roi(rate_per_kg)
    by_tier: dict[int, list[dict]] = {1: [], 2: [], 3: [], 4: []}
    for r in enriched:
        by_tier.setdefault(r.get("tier", 2), []).append(r)
    return by_tier


def category_summary(rate_per_kg: float = DEFAULT_SHIPPING_RATE_USD_PER_KG) -> list[dict]:
    """Average profit-per-kg and margin per category."""
    enriched = compute_roi(rate_per_kg)
    agg: dict[str, dict] = {}
    for r in enriched:
        c = r["category"]
        agg.setdefault(c, {
            "category": c, "items": 0, "profit_per_kg_sum": 0.0,
            "margin_sum": 0.0, "avg_weight_g": 0.0,
        })
        a = agg[c]
        a["items"] += 1
        a["profit_per_kg_sum"] += r["profit_per_kg_usd"]
        a["margin_sum"] += r["margin_pct"]
        a["avg_weight_g"] += r["weight_g"]
    out = []
    for a in agg.values():
        n = max(a["items"], 1)
        out.append({
            "category": a["category"],
            "items": a["items"],
            "avg_profit_per_kg": round(a["profit_per_kg_sum"] / n, 2),
            "avg_margin_pct": round(a["margin_sum"] / n, 1),
            "avg_weight_g": round(a["avg_weight_g"] / n, 1),
        })
    out.sort(key=lambda r: -r["avg_profit_per_kg"])
    return out


def summer_picks(rate_per_kg: float = DEFAULT_SHIPPING_RATE_USD_PER_KG,
                 top_n: int = 15,
                 include_all_season: bool = True) -> list[dict]:
    """Items marked seasonal='summer' plus (optionally) all-season
    jewelry/accessories that pull through in summer. Ranked by ROI/kg.
    """
    enriched = compute_roi(rate_per_kg)
    want = {"summer"}
    if include_all_season:
        # All-season items that benefit from summer pull-through (eyewear,
        # caps, belts, jewelry). Exclude explicitly winter items.
        want.add("all-season")
    picks = [
        r for r in enriched
        if r.get("seasonal", "all-season") in want
        and r.get("tier") != 4
    ]
    return picks[:top_n]


def summer_only_picks(rate_per_kg: float = DEFAULT_SHIPPING_RATE_USD_PER_KG,
                      top_n: int = 15) -> list[dict]:
    """Strictly summer-tagged items — the new-season opportunity list."""
    enriched = compute_roi(rate_per_kg)
    picks = [r for r in enriched if r.get("seasonal") == "summer"
             and r.get("tier") != 4]
    return picks[:top_n]


def seasonal_split(rate_per_kg: float = DEFAULT_SHIPPING_RATE_USD_PER_KG) -> dict:
    """Group ROI-enriched items by seasonal tag."""
    enriched = compute_roi(rate_per_kg)
    out: dict[str, list[dict]] = {}
    for r in enriched:
        key = r.get("seasonal", "all-season")
        out.setdefault(key, []).append(r)
    return out


def headline_findings(rate_per_kg: float = DEFAULT_SHIPPING_RATE_USD_PER_KG) -> dict:
    """One-line takeaway stats for the tab header."""
    enriched = compute_roi(rate_per_kg)
    winners = [r for r in enriched if r.get("tier") != 4]
    avoids = [r for r in enriched if r.get("tier") == 4]
    top = winners[0] if winners else None
    worst = sorted(avoids, key=lambda r: r["profit_per_kg_usd"])[0] if avoids else None
    return {
        "rate_per_kg": rate_per_kg,
        "best_item": f"{top['brand']} {top['item']}" if top else "—",
        "best_profit_per_kg": top["profit_per_kg_usd"] if top else 0,
        "best_units_per_10kg": top["units_per_10kg"] if top else 0,
        "best_total_profit_10kg": top["total_profit_10kg"] if top else 0,
        "worst_bulk_item": f"{worst['brand']} {worst['item']}" if worst else "—",
        "worst_profit_per_kg": worst["profit_per_kg_usd"] if worst else 0,
        "winners_tracked": len(winners),
        "avoids_flagged": len(avoids),
    }
