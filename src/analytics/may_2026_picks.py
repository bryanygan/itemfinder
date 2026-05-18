"""May 2026 Demand Research — Updated Picks by Calendar Catalyst.

Reflects the specific demand drivers active mid-May 2026:

  - Mother's Day aftermath (May 11) — female-driven luxury runs 2-3 weeks
    after, peak Chanel WOC + LV Mini Pochette + Cartier jewelry resale
  - College graduation season (May 15 – June 7) — luxury gift window:
    Rolex Sub, AP Royal Oak, Patek Nautilus, Cartier Tank, AirPods Max
  - Memorial Day Weekend (May 23–26) — US summer kickoff; sliders,
    sunglasses, swim shorts, bucket hats spike 3-4x in mention volume
  - Cannes Film Festival (May 13–24) — celebrity-driven luxury bag/jewelry
    moments that boost rep demand 2-3 weeks later (peak through June)
  - Festival circuit (Hangout May 16-18, Boston Calling May 23-25,
    Sunfest, etc.) — festival fashion: tanks, bucket hats, cargo shorts,
    statement jewelry
  - Pre-Father's Day inventory window (May 26 – June 14) — watches,
    wallets, sunglasses, fragrance — stock-up timing

Items below are NEW additions on top of bulk_buy_roi.BULK_BUY_ITEMS,
tuned for May-specific demand drivers. ROI math reuses compute_roi()
from bulk_buy_roi.py so the $/kg ranking stays consistent.

Methodology notes for reviewers:
  - Weights measured from comparable retail items
  - Rep costs from late-April / mid-May 2026 Weidian + Yupoo observations
  - Resell ranges conservative US aftermarket (Depop / Grailed / Instagram)
  - Each item is tagged with which catalyst is the primary driver
"""

from __future__ import annotations

from src.analytics.bulk_buy_roi import (
    DEFAULT_SHIPPING_RATE_USD_PER_KG,
    compute_roi,
)

# ── Catalyst calendar ────────────────────────────────────────────────────

MAY_2026_CATALYSTS: list[dict] = [
    {
        "event": "Mother's Day aftermath",
        "date_start": "2026-05-04",
        "date_end": "2026-05-25",
        "peak_date": "2026-05-11",
        "categories": ["Bags", "Jewelry", "Accessories"],
        "audience": "Female-driven luxury, 25-45 demographic",
        "drivers": (
            "Mother's Day fell May 11. Female luxury rep resale runs hot for "
            "2-3 weeks after the holiday — buyers reward themselves or pick "
            "up gifted-style pieces. Chanel WOC, LV Mini Pochette, Cartier "
            "Love Bracelet, VCA Alhambra all see 30-50% mention spikes."
        ),
    },
    {
        "event": "College graduation season",
        "date_start": "2026-05-15",
        "date_end": "2026-06-07",
        "peak_date": "2026-05-23",
        "categories": ["Watches", "Eyewear", "Electronics", "Accessories"],
        "audience": "Parents gifting graduates, 18-25 graduates",
        "drivers": (
            "Peak gifting window. ~40% of US college graduates receive a "
            "luxury accessory. Watches dominate: AP Royal Oak, Rolex Sub, "
            "Patek Nautilus, Cartier Tank. AirPods Max / Pro 2 reps are "
            "the most common electronics gift. Sunglasses + wallet combos "
            "for both genders."
        ),
    },
    {
        "event": "Memorial Day Weekend (US summer kickoff)",
        "date_start": "2026-05-23",
        "date_end": "2026-05-26",
        "peak_date": "2026-05-25",
        "categories": ["Eyewear", "Footwear", "Bottoms", "Accessories"],
        "audience": "Mass-market 16-35, pool/beach destinations",
        "drivers": (
            "Pool/beach season opener. Largest retail weekend of the year "
            "before summer. Slides, sunglasses, swim shorts, bucket hats "
            "spike 3-4x in mention volume across FashionReps and "
            "RepBudgetSneakers in the 10 days leading up. Most successful "
            "stock-up is May 1-15."
        ),
    },
    {
        "event": "Cannes Film Festival",
        "date_start": "2026-05-13",
        "date_end": "2026-05-24",
        "peak_date": "2026-05-18",
        "categories": ["Bags", "Jewelry", "Eyewear", "Dresses"],
        "audience": "Aspirational luxury, female-skewed",
        "drivers": (
            "Red-carpet press cycles boost specific designer rep demand "
            "2-3 weeks later. Chanel Classic Flap, Bottega Veneta Jodie, "
            "Dior 30 Montaigne and select Tiffany / VCA pieces ride the "
            "celebrity halo. Followed by wedding-guest dress demand for "
            "Réalisation Par-style slip dresses."
        ),
    },
    {
        "event": "Hangout Music Festival & wider festival circuit",
        "date_start": "2026-05-16",
        "date_end": "2026-05-31",
        "peak_date": "2026-05-17",
        "categories": ["Tops", "Bottoms", "Accessories"],
        "audience": "Festival demo 18-28, streetwear-heavy",
        "drivers": (
            "Hangout (Gulf Shores May 16-18), Boston Calling (May 23-25), "
            "Sunfest are May festival anchors. Festival fashion: tanks, "
            "bucket hats, statement jewelry, cargo shorts. Sp5der, "
            "Trapstar, Corteiz dominate streetwear; Chrome Hearts and "
            "Gallery Dept fill the premium tier."
        ),
    },
    {
        "event": "Pre-Father's Day prep",
        "date_start": "2026-05-26",
        "date_end": "2026-06-14",
        "peak_date": "2026-06-10",
        "categories": ["Watches", "Accessories", "Fragrance", "Eyewear"],
        "audience": "Gifting demo 25-55, predominantly female buyers",
        "drivers": (
            "Father's Day falls June 14. Watches, wallets, sunglasses, "
            "fragrance (Tom Ford, Creed Aventus, Le Labo Santal 33). "
            "Stock-up window is late May. Watch + fragrance combos move "
            "as bundles on Instagram resale."
        ),
    },
]


# ── New May 2026 picks ───────────────────────────────────────────────────
# Each entry mirrors BULK_BUY_ITEMS schema with extra fields:
#   catalyst: primary May 2026 demand driver
#   seasonal: 'summer' (Memorial+), 'spring' (Mother's Day window),
#             'all-season', or 'gift-season'

MAY_2026_ITEMS: list[dict] = [
    # ── WATCHES — grad season + Father's Day prep ────────────────────────
    {
        "brand": "Rolex", "item": "Submariner Date 41mm",
        "category": "Watches", "weight_g": 180,
        "rep_cost_low": 90, "rep_cost_high": 180,
        "resell_low": 280, "resell_high": 520,
        "min_bulk_qty": 4,
        "tier": 1, "seasonal": "gift-season",
        "catalyst": "Graduation + Father's Day",
        "subreddits": "RepTime, DesignerReps, FashionReps",
        "notes": "Clean factory or VS factory. Movement quality varies — pay attention to QC.",
        "why_good": "MAY: #1 luxury rep watch by demand. Grad gift staple. Ships at 180 g.",
    },
    {
        "brand": "Audemars Piguet", "item": "Royal Oak 41mm",
        "category": "Watches", "weight_g": 190,
        "rep_cost_low": 120, "rep_cost_high": 240,
        "resell_low": 360, "resell_high": 720,
        "min_bulk_qty": 3,
        "tier": 1, "seasonal": "gift-season",
        "catalyst": "Graduation",
        "subreddits": "RepTime, DesignerReps",
        "notes": "ZF or BF factory. Tapisserie dial accuracy is the QC priority.",
        "why_good": "MAY: Highest absolute margin per unit on this list ($400+ on a 190 g item).",
    },
    {
        "brand": "Patek Philippe", "item": "Nautilus 5711",
        "category": "Watches", "weight_g": 170,
        "rep_cost_low": 130, "rep_cost_high": 260,
        "resell_low": 380, "resell_high": 760,
        "min_bulk_qty": 3,
        "tier": 1, "seasonal": "gift-season",
        "catalyst": "Graduation",
        "subreddits": "RepTime, DesignerReps",
        "notes": "PF or 3K factory. Discontinued retail = elevated demand.",
        "why_good": "MAY: Retail discontinuation keeps rep demand elevated. Premium grad pick.",
    },
    {
        "brand": "Cartier", "item": "Tank Must (women's)",
        "category": "Watches", "weight_g": 85,
        "rep_cost_low": 50, "rep_cost_high": 110,
        "resell_low": 180, "resell_high": 340,
        "min_bulk_qty": 5,
        "tier": 1, "seasonal": "gift-season",
        "catalyst": "Mother's Day + Graduation",
        "subreddits": "DesignerReps, FashionReps",
        "notes": "GF factory. Female-skewed grad gift, also Mother's Day pull-through.",
        "why_good": "MAY: Crosses two catalysts (Mother's Day + female grad). 85 g — lightest watch pick.",
    },

    # ── JEWELRY — Mother's Day + grad ────────────────────────────────────
    {
        "brand": "Cartier", "item": "Love Bracelet",
        "category": "Jewelry", "weight_g": 65,
        "rep_cost_low": 40, "rep_cost_high": 80,
        "resell_low": 160, "resell_high": 290,
        "min_bulk_qty": 6,
        "tier": 1, "seasonal": "gift-season",
        "catalyst": "Mother's Day + Graduation",
        "subreddits": "DesignerReps, QualityReps",
        "notes": "Screwdriver-included version preferred. Plate quality varies — request QC.",
        "why_good": "MAY: Crosses Mother's Day + grad. Higher-ceiling than CH silver, similar weight.",
    },
    {
        "brand": "Van Cleef & Arpels", "item": "Alhambra Necklace (single motif)",
        "category": "Jewelry", "weight_g": 50,
        "rep_cost_low": 35, "rep_cost_high": 70,
        "resell_low": 140, "resell_high": 250,
        "min_bulk_qty": 8,
        "tier": 1, "seasonal": "gift-season",
        "catalyst": "Mother's Day + Cannes halo",
        "subreddits": "DesignerReps, LuxuryReps",
        "notes": "MOP variant is the bestseller. Onyx and turquoise secondary.",
        "why_good": "MAY: Cannes red-carpet visibility + Mother's Day = sustained May demand.",
    },
    {
        "brand": "Tiffany & Co.", "item": "T-Smile Necklace",
        "category": "Jewelry", "weight_g": 45,
        "rep_cost_low": 25, "rep_cost_high": 50,
        "resell_low": 90, "resell_high": 170,
        "min_bulk_qty": 10,
        "tier": 1, "seasonal": "gift-season",
        "catalyst": "Graduation",
        "subreddits": "DesignerReps, FashionReps",
        "notes": "Rose gold colorway moves fastest in May.",
        "why_good": "MAY: Affordable luxury entry point — popular grad gift under $200 retail equivalent.",
    },
    {
        "brand": "Cartier", "item": "Juste un Clou Bracelet",
        "category": "Jewelry", "weight_g": 60,
        "rep_cost_low": 45, "rep_cost_high": 85,
        "resell_low": 170, "resell_high": 290,
        "min_bulk_qty": 5,
        "tier": 1, "seasonal": "gift-season",
        "catalyst": "Graduation",
        "subreddits": "DesignerReps, QualityReps",
        "notes": "Easier to QC than Love bracelet — no screwdriver mechanism.",
        "why_good": "MAY: Unisex appeal broadens grad gift audience vs Love bracelet.",
    },

    # ── BAGS — Mother's Day + Cannes ────────────────────────────────────
    {
        "brand": "Chanel", "item": "Wallet on Chain (WOC)",
        "category": "Bags", "weight_g": 420,
        "rep_cost_low": 70, "rep_cost_high": 130,
        "resell_low": 210, "resell_high": 380,
        "min_bulk_qty": 3,
        "tier": 2, "seasonal": "gift-season",
        "catalyst": "Mother's Day + Cannes",
        "subreddits": "DesignerReps, LuxuryReps, FashionReps",
        "notes": "187 factory for top tier. Caviar or lambskin — caviar more durable.",
        "why_good": "MAY: Mother's Day flagship piece. Smaller and lighter than Classic Flap.",
    },
    {
        "brand": "Louis Vuitton", "item": "Mini Pochette Accessoires",
        "category": "Bags", "weight_g": 180,
        "rep_cost_low": 30, "rep_cost_high": 55,
        "resell_low": 95, "resell_high": 170,
        "min_bulk_qty": 5,
        "tier": 1, "seasonal": "gift-season",
        "catalyst": "Mother's Day",
        "subreddits": "DesignerReps, FashionReps",
        "notes": "HyperPeter recommended seller. Mono and Damier both move.",
        "why_good": "MAY: Tiny LV with WOC-like functionality. Best-margin LV under 200 g.",
    },
    {
        "brand": "Bottega Veneta", "item": "Mini Jodie",
        "category": "Bags", "weight_g": 380,
        "rep_cost_low": 55, "rep_cost_high": 100,
        "resell_low": 180, "resell_high": 320,
        "min_bulk_qty": 3,
        "tier": 2, "seasonal": "gift-season",
        "catalyst": "Cannes + Mother's Day",
        "subreddits": "DesignerReps, LuxuryReps",
        "notes": "Jing factory commonly cited. Intrecciato weave consistency is the QC priority.",
        "why_good": "MAY: Cannes red-carpet visibility drives 2-3 week post-festival lift.",
    },

    # ── FOOTWEAR — Memorial Day kickoff ─────────────────────────────────
    {
        "brand": "Hermès", "item": "Oran Sandal",
        "category": "Footwear", "weight_g": 380,
        "rep_cost_low": 35, "rep_cost_high": 65,
        "resell_low": 125, "resell_high": 230,
        "min_bulk_qty": 4,
        "tier": 2, "seasonal": "summer",
        "catalyst": "Memorial Day + summer kickoff",
        "subreddits": "DesignerReps, FashionReps",
        "notes": "H-cutout accuracy is the make-or-break QC point. Gold/silver/black move fastest.",
        "why_good": "MAY: The single most-requested summer sandal in DesignerReps. Memorial Day must-stock.",
    },
    {
        "brand": "Gucci", "item": "Horsebit Princetown Slide",
        "category": "Footwear", "weight_g": 480,
        "rep_cost_low": 35, "rep_cost_high": 60,
        "resell_low": 115, "resell_high": 200,
        "min_bulk_qty": 4,
        "tier": 2, "seasonal": "summer",
        "catalyst": "Memorial Day",
        "subreddits": "DesignerReps, FashionReps",
        "notes": "Leather or suede versions. Hardware finish accuracy varies — request close-ups.",
        "why_good": "MAY: Smart-casual summer slide that crosses to office wear. Steady May-September run.",
    },
    {
        "brand": "Birkenstock", "item": "Boston Clog (Suede)",
        "category": "Footwear", "weight_g": 620,
        "rep_cost_low": 20, "rep_cost_high": 35,
        "resell_low": 65, "resell_high": 115,
        "min_bulk_qty": 3,
        "tier": 3, "seasonal": "summer",
        "catalyst": "Memorial Day transition",
        "subreddits": "FashionReps, RepBudgetSneakers",
        "notes": "Taupe and Mocha suede are the two top colorways. 1688 sourcing is unusually cheap.",
        "why_good": "MAY: Lifestyle staple — moves all summer. Cheap source cost offsets weight.",
    },

    # ── FRAGRANCE — Father's Day prep + gift season ─────────────────────
    {
        "brand": "Tom Ford", "item": "Tobacco Vanille (50 ml)",
        "category": "Fragrance", "weight_g": 320,
        "rep_cost_low": 18, "rep_cost_high": 32,
        "resell_low": 55, "resell_high": 100,
        "min_bulk_qty": 6,
        "tier": 2, "seasonal": "gift-season",
        "catalyst": "Father's Day prep",
        "subreddits": "FashionReps, DesignerReps",
        "notes": "1688 fragrance houses — search 'TF tobacco vanille 50ml'. Quality varies widely.",
        "why_good": "MAY: Highest-demand TF rep. Stock now for June 14 sell-through.",
    },
    {
        "brand": "Creed", "item": "Aventus (100 ml)",
        "category": "Fragrance", "weight_g": 380,
        "rep_cost_low": 25, "rep_cost_high": 48,
        "resell_low": 85, "resell_high": 150,
        "min_bulk_qty": 5,
        "tier": 2, "seasonal": "gift-season",
        "catalyst": "Father's Day prep",
        "subreddits": "FashionReps, DesignerReps",
        "notes": "Batch code consistency matters for QC. Pineapple-forward batches are most-loved.",
        "why_good": "MAY: The Father's Day fragrance king. Pre-stock May for guaranteed June sales.",
    },
    {
        "brand": "Le Labo", "item": "Santal 33 (50 ml)",
        "category": "Fragrance", "weight_g": 280,
        "rep_cost_low": 20, "rep_cost_high": 38,
        "resell_low": 62, "resell_high": 115,
        "min_bulk_qty": 6,
        "tier": 2, "seasonal": "all-season",
        "catalyst": "Universal gift",
        "subreddits": "FashionReps, DesignerReps",
        "notes": "Hand-written label is the key authenticity marker — rep accuracy varies.",
        "why_good": "MAY: Unisex universal gift. Crosses all May catalysts.",
    },
    {
        "brand": "Maison Margiela", "item": "Replica Beach Walk (100 ml)",
        "category": "Fragrance", "weight_g": 360,
        "rep_cost_low": 18, "rep_cost_high": 32,
        "resell_low": 55, "resell_high": 100,
        "min_bulk_qty": 6,
        "tier": 2, "seasonal": "summer",
        "catalyst": "Memorial Day + summer",
        "subreddits": "FashionReps",
        "notes": "Beach Walk specifically is the summer-skewed MM rep.",
        "why_good": "MAY: Summer-coded fragrance. Pairs naturally with Memorial Day weekend gift sales.",
    },

    # ── ELECTRONICS — grad gifts ────────────────────────────────────────
    {
        "brand": "Apple", "item": "AirPods Max (replica)",
        "category": "Electronics", "weight_g": 460,
        "rep_cost_low": 38, "rep_cost_high": 65,
        "resell_low": 110, "resell_high": 185,
        "min_bulk_qty": 3,
        "tier": 2, "seasonal": "gift-season",
        "catalyst": "Graduation",
        "subreddits": "DHgate, FashionReps",
        "notes": "DHgate 1:1 versions. Pop-up animation, find-my detection accuracy varies.",
        "why_good": "MAY: Top grad electronics gift. High absolute margin — but QC carefully.",
    },
    {
        "brand": "Apple", "item": "AirPods Pro 2 (replica)",
        "category": "Electronics", "weight_g": 80,
        "rep_cost_low": 18, "rep_cost_high": 32,
        "resell_low": 55, "resell_high": 95,
        "min_bulk_qty": 8,
        "tier": 1, "seasonal": "gift-season",
        "catalyst": "Graduation",
        "subreddits": "DHgate",
        "notes": "1:1 Hi-Master version. Look for noise cancellation indicator working.",
        "why_good": "MAY: 80 g, $35+ profit/unit. Highest-velocity electronics rep on this list.",
    },
    {
        "brand": "Apple", "item": "Apple Watch Ultra 2 (replica)",
        "category": "Electronics", "weight_g": 220,
        "rep_cost_low": 35, "rep_cost_high": 65,
        "resell_low": 100, "resell_high": 180,
        "min_bulk_qty": 4,
        "tier": 2, "seasonal": "gift-season",
        "catalyst": "Graduation + Father's Day prep",
        "subreddits": "DHgate, FashionReps",
        "notes": "Watch face accuracy + app store mimicry are QC priorities.",
        "why_good": "MAY: Crosses grad + Father's Day. Lighter than full headphones.",
    },

    # ── FESTIVAL specific ───────────────────────────────────────────────
    {
        "brand": "Trapstar", "item": "Mesh Festival Tank",
        "category": "Tops", "weight_g": 140,
        "rep_cost_low": 12, "rep_cost_high": 22,
        "resell_low": 38, "resell_high": 65,
        "min_bulk_qty": 12,
        "tier": 1, "seasonal": "summer",
        "catalyst": "Festival circuit",
        "subreddits": "FashionReps",
        "notes": "Mesh fabric ships even lighter than standard tanks.",
        "why_good": "MAY: Festival uniform. Sub-150 g — exceptional density.",
    },
    {
        "brand": "Corteiz", "item": "Guerillaz Cargo Shorts",
        "category": "Bottoms", "weight_g": 320,
        "rep_cost_low": 18, "rep_cost_high": 30,
        "resell_low": 55, "resell_high": 95,
        "min_bulk_qty": 8,
        "tier": 2, "seasonal": "summer",
        "catalyst": "Festival circuit",
        "subreddits": "FashionReps",
        "notes": "Cropped cargo is the May 2026 hottest cut.",
        "why_good": "MAY: Hangout / Boston Calling demographic uniform. Cult demand pricing.",
    },
    {
        "brand": "Sp5der", "item": "Web Logo Headband",
        "category": "Accessories", "weight_g": 45,
        "rep_cost_low": 8, "rep_cost_high": 15,
        "resell_low": 25, "resell_high": 45,
        "min_bulk_qty": 20,
        "tier": 1, "seasonal": "summer",
        "catalyst": "Festival circuit",
        "subreddits": "FashionReps",
        "notes": "Tiny — pack 100+ in 5 kg. Ultra-niche but cult buyer base.",
        "why_good": "MAY: Sub-50 g festival accessory. Highest unit-density item in this entire research.",
    },

    # ── DRESS — Cannes / wedding-guest demand ───────────────────────────
    {
        "brand": "Réalisation Par", "item": "Naomi Slip Dress",
        "category": "Dresses", "weight_g": 210,
        "rep_cost_low": 18, "rep_cost_high": 32,
        "resell_low": 55, "resell_high": 95,
        "min_bulk_qty": 8,
        "tier": 2, "seasonal": "summer",
        "catalyst": "Cannes + wedding season",
        "subreddits": "FashionReps, QualityReps",
        "notes": "Floral and leopard prints are evergreen movers.",
        "why_good": "MAY: Wedding-guest demand peaks May-September. Light, packable, near-zero rep competition.",
    },
    {
        "brand": "Hill House", "item": "Nap Dress (replica)",
        "category": "Dresses", "weight_g": 260,
        "rep_cost_low": 18, "rep_cost_high": 30,
        "resell_low": 55, "resell_high": 95,
        "min_bulk_qty": 8,
        "tier": 2, "seasonal": "summer",
        "catalyst": "Mother's Day + wedding season",
        "subreddits": "FashionReps",
        "notes": "Cotton fabric weight reads as quality — even cheap reps photograph well.",
        "why_good": "MAY: TikTok-driven demand from women 25-40. Strongest May-July run.",
    },

    # ── MISC SUMMER OPENERS ─────────────────────────────────────────────
    {
        "brand": "Stussy", "item": "Beach Towel (logo)",
        "category": "Accessories", "weight_g": 360,
        "rep_cost_low": 12, "rep_cost_high": 22,
        "resell_low": 38, "resell_high": 70,
        "min_bulk_qty": 6,
        "tier": 2, "seasonal": "summer",
        "catalyst": "Memorial Day kickoff",
        "subreddits": "FashionReps",
        "notes": "Folds tight enough that volumetric stays low.",
        "why_good": "MAY: Memorial Day weekend gift / lifestyle prop. Cheap source, high markup.",
    },
    {
        "brand": "Goyard", "item": "Saint Louis PM Tote",
        "category": "Bags", "weight_g": 450,
        "rep_cost_low": 65, "rep_cost_high": 120,
        "resell_low": 200, "resell_high": 340,
        "min_bulk_qty": 3,
        "tier": 2, "seasonal": "summer",
        "catalyst": "Cannes + beach season",
        "subreddits": "DesignerReps, LuxuryReps",
        "notes": "Chevron pattern hand-painted — accuracy varies wildly by factory.",
        "why_good": "MAY: Goyard tote is the May-September wealthy-beach-club signal. Strong sustained run.",
    },
]


# ── Helpers ─────────────────────────────────────────────────────────────

def get_catalysts() -> list[dict]:
    """Return the May 2026 catalyst calendar."""
    return list(MAY_2026_CATALYSTS)


def compute_may_roi(rate_per_kg: float = DEFAULT_SHIPPING_RATE_USD_PER_KG) -> list[dict]:
    """Run the bulk-buy ROI math over the May items list."""
    return compute_roi(rate_per_kg, items=MAY_2026_ITEMS)


def top_may_picks(rate_per_kg: float = DEFAULT_SHIPPING_RATE_USD_PER_KG,
                  top_n: int = 15,
                  exclude_avoid: bool = True) -> list[dict]:
    enriched = compute_may_roi(rate_per_kg)
    if exclude_avoid:
        enriched = [r for r in enriched if r.get("tier") != 4]
    return enriched[:top_n]


def picks_by_catalyst(catalyst_substr: str,
                      rate_per_kg: float = DEFAULT_SHIPPING_RATE_USD_PER_KG,
                      top_n: int = 12) -> list[dict]:
    """Filter May items to ones whose catalyst tag matches a substring
    (e.g. 'Mother', 'Graduation', 'Memorial', 'Cannes', 'Festival', 'Father')."""
    needle = catalyst_substr.lower()
    enriched = compute_may_roi(rate_per_kg)
    matches = [r for r in enriched
               if needle in (r.get("catalyst") or "").lower()
               and r.get("tier") != 4]
    return matches[:top_n]


def picks_by_category(category: str,
                      rate_per_kg: float = DEFAULT_SHIPPING_RATE_USD_PER_KG) -> list[dict]:
    enriched = compute_may_roi(rate_per_kg)
    return [r for r in enriched if r.get("category") == category]


def may_category_summary(rate_per_kg: float = DEFAULT_SHIPPING_RATE_USD_PER_KG) -> list[dict]:
    """Average profit/kg and average margin per category for the May list."""
    enriched = compute_may_roi(rate_per_kg)
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


def may_headline(rate_per_kg: float = DEFAULT_SHIPPING_RATE_USD_PER_KG) -> dict:
    enriched = compute_may_roi(rate_per_kg)
    winners = [r for r in enriched if r.get("tier") != 4]
    top = winners[0] if winners else None
    by_cat = may_category_summary(rate_per_kg)
    return {
        "rate_per_kg": rate_per_kg,
        "total_items": len(MAY_2026_ITEMS),
        "catalyst_count": len(MAY_2026_CATALYSTS),
        "top_item": f"{top['brand']} {top['item']}" if top else "—",
        "top_profit_per_kg": top["profit_per_kg_usd"] if top else 0,
        "top_units_per_10kg": top["units_per_10kg"] if top else 0,
        "top_total_10kg": top["total_profit_10kg"] if top else 0,
        "top_category": by_cat[0]["category"] if by_cat else "—",
        "top_category_profit": by_cat[0]["avg_profit_per_kg"] if by_cat else 0,
    }
