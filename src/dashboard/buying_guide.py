"""Buying Guide — Deep-dive ROI analysis for replica fashion resellers.

Compiled from live Reddit community data across 18+ subreddits, JadeShip
sales tracking, Weidian/1688 agent data, and QC platform intelligence.
Data reflects April 2026 market conditions.

Usage: imported by app.py and rendered as a dashboard tab.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import dash_table, dcc, html

from src.dashboard.components import (
    C_AMBER, C_BLUE, C_CYAN, C_GREEN, C_PURPLE, C_RED,
    action_box, chart_card, empty_fig, explainer, kpi,
    make_table, section, style_fig,
)

# ── Static research data (April 2026) ─────────────────────────────────────

JEWELRY_ITEMS = [
    {
        "item": "Chrome Hearts Keeper Ring",
        "brand": "Chrome Hearts",
        "category": "Jewelry",
        "cost_yuan": "85–130",
        "cost_usd": "$12–18",
        "weight_g": 40,
        "resale_usd": "$45–80",
        "roi_pct": 320,
        "shipping_yuan": 4,
        "material": "925 Sterling Silver Alloy",
        "demand": "Very High",
        "notes": "#1 brand on Grailed 2025. Retail $2,075–$3,025 per ring. "
                 "Best sellers: Keeper Ring, Cemetery Cross, Floral Cross, "
                 "Dagger Ring, Scroll Band. Always verify 925 hallmark — "
                 "avoid cheap alloy versions. Customers notice the weight "
                 "difference immediately.",
        "where_to_buy": "Weidian — search 'Chrome Hearts 925 silver ring'. "
                        "Multiple verified sellers on Weidian Spreadsheet "
                        "(weidianspreadsheet.org). Also available via "
                        "David925 Studio on Taobao.",
        "source_subs": "r/FashionReps, r/DesignerReps, r/QualityReps",
    },
    {
        "item": "Chrome Hearts Cross Pendant + Chain",
        "brand": "Chrome Hearts",
        "category": "Jewelry",
        "cost_yuan": "80–180",
        "cost_usd": "$11–25",
        "weight_g": 60,
        "resale_usd": "$45–90",
        "roi_pct": 250,
        "shipping_yuan": 6,
        "material": "925 Sterling Silver / Stainless Steel",
        "demand": "Very High",
        "notes": "Cross pendants and dagger charms are the most sought-after "
                 "CH necklace styles. Paper Chain and Dog Tag designs also "
                 "move fast. Gothic silver aesthetic is peak 2026. Pair with "
                 "rings for bundle deals.",
        "where_to_buy": "Weidian — David925 Studio, survival source (Taobao). "
                        "Search 'CH cross pendant 925' on agent platforms.",
        "source_subs": "r/FashionReps, r/DesignerReps, r/QualityReps",
    },
    {
        "item": "Vivienne Westwood Orb Pearl Choker",
        "brand": "Vivienne Westwood",
        "category": "Jewelry",
        "cost_yuan": "60–120",
        "cost_usd": "$8–17",
        "weight_g": 30,
        "resale_usd": "$25–55",
        "roi_pct": 260,
        "shipping_yuan": 3,
        "material": "Faux Pearl / Brass / Rhinestone",
        "demand": "Very High",
        "notes": "TikTok-viral item driving massive Gen Z demand. The Orb "
                 "Pearl Choker is the single most viral VW piece. Saturn "
                 "Pendant, Heart Necklace, and Three-Row Pearl also sell "
                 "consistently. Extremely lightweight = best shipping "
                 "economics in the entire catalog. Available on Taobao, "
                 "AliExpress, and Weidian.",
        "where_to_buy": "Taobao — search 'VW pearl necklace'. Widely available "
                        "on AliExpress as 'VW-inspired' pieces. Weidian has "
                        "higher quality options at 80–120 yuan.",
        "source_subs": "r/FashionReps, r/DesignerReps",
    },
    {
        "item": "Chrome Hearts Bracelet (Paper Chain / ID)",
        "brand": "Chrome Hearts",
        "category": "Jewelry",
        "cost_yuan": "100–200",
        "cost_usd": "$14–28",
        "weight_g": 70,
        "resale_usd": "$50–95",
        "roi_pct": 220,
        "shipping_yuan": 7,
        "material": "925 Sterling Silver",
        "demand": "High",
        "notes": "Heavier than rings but still excellent weight-to-value ratio. "
                 "Paper chain and ID bracelet styles are the top sellers. "
                 "Authentic retails at $2,500–$5,000+. Make sure to request "
                 "QC photos showing clasp detail and engraving quality.",
        "where_to_buy": "Weidian — David925 Studio, survival source. "
                        "Search CH bracelet on weidianspreadsheet.org.",
        "source_subs": "r/FashionReps, r/DesignerReps, r/QualityReps",
    },
    {
        "item": "David Yurman Cable Bracelet",
        "brand": "David Yurman",
        "category": "Jewelry",
        "cost_yuan": "80–160",
        "cost_usd": "$11–22",
        "weight_g": 50,
        "resale_usd": "$40–70",
        "roi_pct": 200,
        "shipping_yuan": 5,
        "material": "Sterling Silver / Gold-Plated Accents",
        "demand": "High",
        "notes": "Cable bracelets are the most replicated DY item. Albion "
                 "rings and gemstone pendants also available. Legitimate "
                 "pre-owned ranges $475–$2,250. Key QC: check hallmarks "
                 "('D.Y.', '925', '750'), cable symmetry, and stone quality. "
                 "'Inspired' versions available wholesale on Faire/Alibaba.",
        "where_to_buy": "Weidian, Taobao — search 'DY cable bracelet 925'. "
                        "Wholesale options on Alibaba for bulk orders.",
        "source_subs": "r/FashionReps, r/DesignerReps",
    },
]

SNEAKER_ITEMS = [
    {
        "item": "Nike Dunk Low (Panda / UNC / Grey Fog)",
        "brand": "Nike",
        "category": "Sneakers",
        "cost_yuan": "200–290",
        "cost_usd": "$28–40",
        "weight_g": 900,
        "resale_usd": "$70–110",
        "roi_pct": 85,
        "shipping_yuan": 84,
        "best_batch": "M Batch (consensus best) / SH Batch (value pick)",
        "demand": "Very High",
        "notes": "The single most purchased rep sneaker globally. M Batch is "
                 "the consensus best — 'even experienced sneakerheads have "
                 "trouble telling the difference.' Panda colorway never stops "
                 "selling. UNC, Grey Fog, Spartan Green, and Vintage Green "
                 "are also strong. Ben & Jerry's Chunky Dunky for hype buyers. "
                 "SH Batch from Dongguan noted for 'superior fit' and fewer "
                 "defects at a lower price point. ALWAYS drop the shoe box "
                 "to save 200–300g per pair (19–28 yuan shipping savings). "
                 "Weight listed is WITHOUT box.",
        "where_to_buy": "Weidian — A1 Top, Top Dreamer, Philanthropist, "
                        "Cappuccino, CSJ. M Batch available from multiple "
                        "middlemen. Use JadeShip or Weidian Spreadsheet to "
                        "find current stock. Agent: Sugargoo, CNFans, OopBuy.",
        "source_subs": "r/Repsneakers, r/repbudgetsneakers, r/weidianwarriors, "
                       "r/FashionReps",
    },
    {
        "item": "Jordan 4 Black Cat / Military Black / Bred",
        "brand": "Jordan",
        "category": "Sneakers",
        "cost_yuan": "350–500",
        "cost_usd": "$48–69",
        "weight_g": 1100,
        "resale_usd": "$100–140",
        "roi_pct": 55,
        "shipping_yuan": 102,
        "best_batch": "GX Batch (~350 yuan, best value) / PK Batch (premium)",
        "demand": "Very High",
        "notes": "Jordan 4 dominates 2025/2026 with 15+ releases driving "
                 "constant demand. Black Cat is the perennial bestseller. "
                 "Military Black, Bred, Thunder, and Oreo also strong. "
                 "GX Batch at ~350 yuan offers the best value with 70+ units "
                 "sold on JadeShip in 30 days. PK Batch is the premium pick "
                 "for detail-focused buyers, especially for Reverse Swoosh "
                 "series. OG Batch has the best elephant print accuracy. "
                 "Drop box to save weight.",
        "where_to_buy": "Weidian — search 'GX batch Jordan 4' or 'PK batch J4'. "
                        "CSJ, Cappuccino, A1 Top carry GX. Middlemen like "
                        "Muks, Coco carry PK. Agent: any major agent works.",
        "source_subs": "r/Repsneakers, r/repbudgetsneakers, r/FashionReps, "
                       "r/sneakerreps",
    },
    {
        "item": "Jordan 1 High (Chicago / Travis Scott / University Blue)",
        "brand": "Jordan",
        "category": "Sneakers",
        "cost_yuan": "400–500",
        "cost_usd": "$55–69",
        "weight_g": 1000,
        "resale_usd": "$100–150",
        "roi_pct": 50,
        "shipping_yuan": 93,
        "best_batch": "LJR Batch (king of AJ1) / OG Batch (alternative)",
        "demand": "High",
        "notes": "LJR is the undisputed best batch for Jordan 1s — 'no one "
                 "in the market can surpass LJR Jordan.' Known for sharp toe "
                 "boxes, high-quality leather, and flawless logo placement. "
                 "Chicago is the flagship colorway. Travis Scott Mocha and "
                 "University Blue are consistently strong sellers. Two new "
                 "Travis Scott x AJ1 Low OG colorways dropping in 2026 are "
                 "driving additional rep demand. LJR is worth the premium "
                 "specifically where leather quality is the differentiator.",
        "where_to_buy": "Weidian — A1 Top, SK, Anonymous. LJR widely stocked. "
                        "Middlemen: Muks (mr_muks on Instagram), Coco. "
                        "Agent: Sugargoo, CNFans.",
        "source_subs": "r/Repsneakers, r/FashionReps, r/sneakerreps, "
                       "r/TheWorldOfRepsneakers",
    },
    {
        "item": "Yeezy 350 V2 (Zebra / Bred / Beluga / Bone)",
        "brand": "Adidas / Yeezy",
        "category": "Sneakers",
        "cost_yuan": "270–340",
        "cost_usd": "$38–48",
        "weight_g": 850,
        "resale_usd": "$80–120",
        "roi_pct": 65,
        "shipping_yuan": 79,
        "best_batch": "LW Batch (BASF Popcorn foam) / PK BASF",
        "demand": "High",
        "notes": "Lighter than Jordans = better shipping economics per pair. "
                 "LW Batch uses BASF 'Popcorn' foam that closely matches "
                 "retail Boost feel — this is the key differentiator from "
                 "budget batches. Zebra and Cream are the top colorways. "
                 "PK BASF is the alternative premium option. The comfort "
                 "difference between BASF and regular foam is immediately "
                 "noticeable — never ship budget foam batches to customers "
                 "who know Yeezys.",
        "where_to_buy": "Weidian — LOL2021 (lol2021.x.yupoo.com), A1 Top, "
                        "Philanthropist. LW Batch widely available. "
                        "Agent: any major agent.",
        "source_subs": "r/Repsneakers, r/repbudgetsneakers, r/FashionReps",
    },
    {
        "item": "Adidas Samba OG",
        "brand": "Adidas",
        "category": "Sneakers",
        "cost_yuan": "180–270",
        "cost_usd": "$25–38",
        "weight_g": 800,
        "resale_usd": "$60–80",
        "roi_pct": 60,
        "shipping_yuan": 74,
        "best_batch": "Mid-tier Weidian (simple design = easy to replicate well)",
        "demand": "Very High",
        "notes": "Massive trend piece in 2025–2026. The simple design means "
                 "even mid-tier batches are accurate — no complex colorways "
                 "or materials to get wrong. Cheaper buy-in than Jordans with "
                 "lighter weight. Good entry-level item for new resellers. "
                 "Multiple colorways available but the classic white/black "
                 "gum sole is the top seller.",
        "where_to_buy": "Weidian — many sellers carry Sambas. Search on "
                        "weidianspreadsheet.org for verified links. "
                        "Agent: any major agent.",
        "source_subs": "r/FashionReps, r/repbudgetsneakers, r/weidianwarriors",
    },
    {
        "item": "Maison Margiela GATs (German Army Trainers)",
        "brand": "Maison Margiela",
        "category": "Sneakers",
        "cost_yuan": "~200",
        "cost_usd": "$28–35",
        "weight_g": 900,
        "resale_usd": "$70–100",
        "roi_pct": 70,
        "shipping_yuan": 84,
        "best_batch": "Top Weidian sellers",
        "demand": "Very High",
        "notes": "#2 most sold item on JadeShip with 197 units in 30 days. "
                 "Weidian links are heavily shared on TikTok driving discovery. "
                 "Margiela was a top-5 footwear brand on Grailed resale. "
                 "The GAT is a clean, versatile silhouette that works for "
                 "summer and year-round. Quality reps are very close to retail "
                 "due to the relatively simple construction.",
        "where_to_buy": "Weidian — multiple sellers. #2 on JadeShip trending "
                        "(jadeship.com/feed/top/30-days). Search 'Margiela GAT' "
                        "on agent platforms.",
        "source_subs": "r/QualityReps, r/FashionReps, r/DesignerReps",
    },
    {
        "item": "Balenciaga Track 2 / Runner / 3XL / Triple S",
        "brand": "Balenciaga",
        "category": "Sneakers",
        "cost_yuan": "350–500",
        "cost_usd": "$48–69",
        "weight_g": 1200,
        "resale_usd": "$110–160",
        "roi_pct": 55,
        "shipping_yuan": 112,
        "best_batch": "VG/OK Batch (rated 5/5 for Balenciaga line)",
        "demand": "Very High",
        "notes": "#1 footwear brand on Grailed 2025. VG and OK Batches are "
                 "rated 5/5 stars for the entire Balenciaga Paris line — "
                 "Track, 3XL, Tire, Triple S. Premium 1:1 reps available "
                 "from established sellers. These are heavier shoes (1.2kg+) "
                 "so shipping costs are higher, but the resale premium "
                 "compensates. Track 2 and Runner are the trending silhouettes "
                 "for 2026. Defender is gaining traction as well.",
        "where_to_buy": "Weidian — search 'VG batch Balenciaga' or 'OK batch Track'. "
                        "Bean Studio (beanstudio88.x.yupoo.com) is a trusted "
                        "source. Agent: Sugargoo, CNFans.",
        "source_subs": "r/Repsneakers, r/FashionReps, r/DesignerReps",
    },
    {
        "item": "Rick Owens DRKSHDW Ramones / Geobaskets",
        "brand": "Rick Owens",
        "category": "Sneakers",
        "cost_yuan": "300–500",
        "cost_usd": "$41–69",
        "weight_g": 1100,
        "resale_usd": "$90–140",
        "roi_pct": 50,
        "shipping_yuan": 102,
        "best_batch": "DRKSTUDIO (dedicated Rick Owens specialist)",
        "demand": "High",
        "notes": "#2 footwear brand on Grailed (after Balenciaga). "
                 "DRKSTUDIO is THE go-to seller for Rick Owens reps — no "
                 "other seller comes close for accuracy. Key QC points: "
                 "check 'W' thickness in DRKSHDW text, toe box stitching, "
                 "and hole placement. Ramones are the most popular model, "
                 "followed by Geobaskets. FW2026 collection just shown in "
                 "Paris driving renewed interest. Rick Owens Dunks variant "
                 "also gaining traction.",
        "where_to_buy": "DRKSTUDIO — drkstudio.x.yupoo.com. This is the only "
                        "recommended seller for Rick Owens. Order through "
                        "any shopping agent using Weidian/Taobao links from "
                        "their Yupoo catalog.",
        "source_subs": "r/QualityReps, r/FashionReps, r/DesignerReps",
    },
    {
        "item": "Cloud Tilt (Cl0udtilt)",
        "brand": "On Running",
        "category": "Sneakers",
        "cost_yuan": "200–350",
        "cost_usd": "$28–48",
        "weight_g": 850,
        "resale_usd": "$70–110",
        "roi_pct": 60,
        "shipping_yuan": 79,
        "best_batch": "Top Weidian sellers",
        "demand": "Very High",
        "notes": "Currently #1 on JadeShip's 30-day most popular list with "
                 "270+ units sold. This is the breakout sneaker of 2026. "
                 "On Running's chunky silhouette has crossed from performance "
                 "to fashion. Lightweight construction helps shipping costs.",
        "where_to_buy": "Weidian — #1 on jadeship.com/feed/top/30-days. "
                        "Multiple sellers carrying this model.",
        "source_subs": "r/FashionReps, r/repbudgetsneakers",
    },
]

CLOTHING_ITEMS = [
    {
        "item": "Graphic Cut-Off Tanks / Distressed Tees",
        "brand": "ERD (Enfants Riches Deprimes)",
        "category": "Clothing — Tees",
        "cost_yuan": "160–280",
        "cost_usd": "$22–40",
        "weight_g": 250,
        "resale_usd": "$60–120",
        "roi_pct": 170,
        "shipping_yuan": 23,
        "demand": "Very High",
        "notes": "THE standout opportunity for clothing resellers. ERD retail "
                 "tees sell for $700–$1,800 — the gap between rep cost and "
                 "perceived value is ENORMOUS. SS26 collection was shown at "
                 "Paris Fashion Week generating massive buzz. r/QualityReps "
                 "is obsessed with this brand. XL sizing is most popular. "
                 "The distressed, punk-rock aesthetic with hand-drawn graphics "
                 "is peak 2026. These are lightweight (250g) with huge margins.",
        "where_to_buy": "Weidian/Taobao — search 'ERD tee' or 'Enfants Riches "
                        "Deprimes'. Check r/QualityReps for current verified "
                        "seller links. Quality varies significantly between "
                        "sellers — always check QC photos for print quality "
                        "and distressing accuracy.",
        "source_subs": "r/QualityReps, r/FashionReps, r/DesignerReps",
    },
    {
        "item": "Campaign Logo Tees / Oversized Tees",
        "brand": "Balenciaga",
        "category": "Clothing — Tees",
        "cost_yuan": "120–200",
        "cost_usd": "$17–28",
        "weight_g": 280,
        "resale_usd": "$45–80",
        "roi_pct": 120,
        "shipping_yuan": 26,
        "demand": "Very High",
        "notes": "Balenciaga is the #1 footwear brand on Grailed and their "
                 "clothing carries the same demand. Political campaign logo "
                 "tees, oversized distressed tees, and the iconic logo "
                 "hoodies all move well. Lighter than hoodies, making tees "
                 "more shipping-efficient. The oversized fit is the signature "
                 "— always order true to the size chart, not US sizing.",
        "where_to_buy": "Cloyad (cloyad0809.x.yupoo.com) — premier Balenciaga "
                        "clothing seller. Also: LY Factory, 8Billion. "
                        "Agent: any major agent.",
        "source_subs": "r/FashionReps, r/DesignerReps",
    },
    {
        "item": "Art-Distressed Graphic Tees / Denim",
        "brand": "Gallery Dept",
        "category": "Clothing — Tees",
        "cost_yuan": "100–180",
        "cost_usd": "$14–25",
        "weight_g": 250,
        "resale_usd": "$40–70",
        "roi_pct": 110,
        "shipping_yuan": 23,
        "demand": "High",
        "notes": "Heavy demand driven by celebrity endorsements and the "
                 "hand-painted/splatter aesthetic. Each piece looks 'unique' "
                 "which helps reps pass as authentic since no two retails "
                 "are identical either. Gallery Dept jeans (heavier, ~800g) "
                 "also sell well but have worse shipping economics. "
                 "Stick to tees for best ROI.",
        "where_to_buy": "Weidian — multiple sellers. Search 'Gallery Dept tee' "
                        "on agent platforms. Check weidianspreadsheet.org.",
        "source_subs": "r/FashionReps, r/DesignerReps",
    },
    {
        "item": "Oversized Hoodies (DHL Logo / Archive Pieces)",
        "brand": "Vetements",
        "category": "Clothing — Hoodies",
        "cost_yuan": "150–250",
        "cost_usd": "$21–35",
        "weight_g": 600,
        "resale_usd": "$55–90",
        "roi_pct": 75,
        "shipping_yuan": 56,
        "demand": "High",
        "notes": "Archive-inspired oversized pieces are gaining traction in "
                 "r/QualityReps. The DHL-branded hoodie and oversized logo "
                 "hoodies remain the most sought-after pieces. Vetements' "
                 "deliberately oversized fit means the sizing is forgiving "
                 "— less returns. Hoodies are heavier (600g) so margins are "
                 "thinner than tees. Consider bundling with jewelry to "
                 "offset shipping costs.",
        "where_to_buy": "Cloyad, Reon District, 8Billion — all carry Vetements. "
                        "Search on Yupoo catalogs via agents.",
        "source_subs": "r/QualityReps, r/FashionReps, r/DesignerReps",
    },
    {
        "item": "DRKSHDW Tees / Tanks",
        "brand": "Rick Owens",
        "category": "Clothing — Tees",
        "cost_yuan": "120–200",
        "cost_usd": "$17–28",
        "weight_g": 250,
        "resale_usd": "$40–70",
        "roi_pct": 80,
        "shipping_yuan": 23,
        "demand": "High",
        "notes": "DRKSTUDIO handles clothing as well as sneakers. The draped, "
                 "elongated silhouettes are core to Rick Owens' identity. "
                 "Double-layered tees, cropped tanks, and level tees are "
                 "the most popular clothing pieces. FW2026 collection "
                 "generating renewed interest. Lightweight makes these "
                 "better for shipping than the sneakers.",
        "where_to_buy": "DRKSTUDIO (drkstudio.x.yupoo.com) for authentic-tier. "
                        "Also available from various Taobao sellers at lower "
                        "price points.",
        "source_subs": "r/QualityReps, r/FashionReps",
    },
    {
        "item": "Swim Trunks / Board Shorts",
        "brand": "LV / Versace / Casablanca / Vilebrequin",
        "category": "Clothing — Summer",
        "cost_yuan": "60–120",
        "cost_usd": "$8–17",
        "weight_g": 250,
        "resale_usd": "$35–60",
        "roi_pct": 150,
        "shipping_yuan": 23,
        "demand": "High (Seasonal — Peak Apr–Aug)",
        "notes": "PEAK SEASON IS NOW. Designer swim trunks are very "
                 "lightweight (~250g) with high perceived value. Versace "
                 "Medusa prints, LV monogram, and Casablanca prints are "
                 "the top sellers. Vilebrequin is the sleeper pick — less "
                 "recognized as a 'rep brand' which helps resale. These "
                 "fold completely flat, minimizing volumetric weight issues. "
                 "Summer 2026 colors: rich violet, brilliant aquamarine, "
                 "cobalt blue — NOT soft pastels.",
        "where_to_buy": "Weidian/Taobao — search by brand name + 'swim shorts'. "
                        "8Billion and Cloyad both carry summer collections. "
                        "Agent: any major agent.",
        "source_subs": "r/FashionReps, r/DesignerReps",
    },
    {
        "item": "Slides / Sandals",
        "brand": "Gucci / LV / Balenciaga / Hermes (Oran)",
        "category": "Footwear — Summer",
        "cost_yuan": "80–150",
        "cost_usd": "$11–21",
        "weight_g": 450,
        "resale_usd": "$40–70",
        "roi_pct": 90,
        "shipping_yuan": 42,
        "demand": "High (Seasonal — Peak Apr–Aug)",
        "notes": "Lighter than sneakers with strong seasonal demand. Gucci "
                 "slides are the volume seller. Hermes Oran sandals are the "
                 "premium play with higher margins. Balenciaga pool slides "
                 "trending for 2026. LV Waterfront mules also strong. "
                 "No box needed — ship in polybag for minimum volumetric.",
        "where_to_buy": "Weidian — search by brand + 'slides'. Zippy is a "
                        "trusted seller for Hermes specifically. "
                        "Agent: any major agent.",
        "source_subs": "r/FashionReps, r/DesignerReps, r/Repsneakers",
    },
    {
        "item": "Polo Shirts",
        "brand": "Moncler / Ralph Lauren / Lacoste",
        "category": "Clothing — Summer",
        "cost_yuan": "80–150",
        "cost_usd": "$11–21",
        "weight_g": 300,
        "resale_usd": "$35–55",
        "roi_pct": 80,
        "shipping_yuan": 28,
        "demand": "High (Seasonal — Peak Apr–Sep)",
        "notes": "Versatile summer staple that appeals to a broader customer "
                 "base beyond the streetwear crowd. Moncler polos command the "
                 "highest premium. Ralph Lauren and Lacoste are volume plays "
                 "with lower margins but consistent demand. TopMonclerX on "
                 "Yupoo is the consensus best Moncler seller.",
        "where_to_buy": "TopMonclerX (topmonclerx.x.yupoo.com) for Moncler. "
                        "Husky Reps for Ralph Lauren. Multiple Taobao sellers "
                        "for Lacoste. Agent: any major agent.",
        "source_subs": "r/FashionReps, r/DesignerReps, r/CoutureReps",
    },
    {
        "item": "SP5DER Hoodies / Tees",
        "brand": "SP5DER (Sp5der)",
        "category": "Clothing — Streetwear",
        "cost_yuan": "100–180",
        "cost_usd": "$14–25",
        "weight_g": 400,
        "resale_usd": "$45–75",
        "roi_pct": 95,
        "shipping_yuan": 37,
        "demand": "Very High",
        "notes": "Breakout streetwear brand in the rep scene. The web-print "
                 "hoodies and graphic tees are everywhere on social media. "
                 "Younger demographic (16–24) drives most demand. Multiple "
                 "colorways available — pink and green are the most popular. "
                 "Foam print quality is the key QC checkpoint.",
        "where_to_buy": "Weidian — search 'SP5DER hoodie'. Multiple sellers. "
                        "Check weidianspreadsheet.org for verified links. "
                        "Agent: any major agent.",
        "source_subs": "r/FashionReps, r/repbudgetsneakers",
    },
]

ACCESSORIES_ITEMS = [
    {
        "item": "Goyard St. Sulpice Card Holder / Wallet",
        "brand": "Goyard",
        "category": "Accessories — Wallets",
        "cost_yuan": "80–150",
        "cost_usd": "$11–21",
        "weight_g": 100,
        "resale_usd": "$35–65",
        "roi_pct": 200,
        "shipping_yuan": 9,
        "demand": "Very High",
        "notes": "Extremely compact, ships flat, very lightweight. The Goyard "
                 "Y-pattern is instantly recognizable. Key QC: the Y's should "
                 "touch (this is the main tell on budget batches). Aadi and "
                 "Pink are trusted sellers for Goyard. The card holder is "
                 "the volume seller; the full wallet also moves well. "
                 "Can ship 10 card holders in under 1kg.",
        "where_to_buy": "Weidian — Aadi (aadi830.x.yupoo.com), Pink. "
                        "Search 'Goyard card holder touching Y' for best "
                        "quality. Agent: any major agent.",
        "source_subs": "r/FashionReps, r/DesignerReps",
    },
    {
        "item": "Cartier Rimless Sunglasses",
        "brand": "Cartier",
        "category": "Accessories — Eyewear",
        "cost_yuan": "50–120",
        "cost_usd": "$7–17",
        "weight_g": 60,
        "resale_usd": "$30–60",
        "roi_pct": 210,
        "shipping_yuan": 6,
        "demand": "High",
        "notes": "Cartier rimless frames are in very high demand, driven by "
                 "hip-hop culture and TikTok. The 'Buffs' (wood/horn temple) "
                 "style is the most sought-after. Gentle Monster styles are "
                 "the alternative for K-pop/Asian fashion demographic. "
                 "Verified Weidian sellers: ZZZTOPXX (userid 1703401406), "
                 "Andy-Lee (userid 1236105248), JBTxZT (userid 1613933272). "
                 "Very lightweight with minimal packaging needed.",
        "where_to_buy": "Weidian — ZZZTOPXX, Andy-Lee, JBTxZT. Search 'Cartier "
                        "sunglasses rimless' on agent platforms. Also: Markin "
                        "(markin520.x.yupoo.com) for premium tier.",
        "source_subs": "r/FashionReps, r/DesignerReps",
    },
    {
        "item": "Gentle Monster Sunglasses",
        "brand": "Gentle Monster",
        "category": "Accessories — Eyewear",
        "cost_yuan": "50–100",
        "cost_usd": "$7–14",
        "weight_g": 70,
        "resale_usd": "$25–50",
        "roi_pct": 180,
        "shipping_yuan": 7,
        "demand": "High",
        "notes": "K-pop and TikTok-driven demand. The oversized, futuristic "
                 "frames are instantly recognizable. Her, Dreamer, and My Ma "
                 "are the top styles. Very lightweight. Appeals to a different "
                 "demographic than Cartier — both can be stocked without "
                 "overlap. Good QC available at low price points.",
        "where_to_buy": "Weidian/Taobao — search 'Gentle Monster'. Markin "
                        "carries premium versions. Budget options widely "
                        "available. Agent: any major agent.",
        "source_subs": "r/FashionReps, r/DesignerReps",
    },
    {
        "item": "Designer Belts (Reversible / Classic)",
        "brand": "LV / Gucci / Hermes",
        "category": "Accessories — Belts",
        "cost_yuan": "100–200",
        "cost_usd": "$14–28",
        "weight_g": 300,
        "resale_usd": "$45–80",
        "roi_pct": 100,
        "shipping_yuan": 28,
        "demand": "High",
        "notes": "Compact and relatively lightweight for their value. LV "
                 "reversible belts are the volume seller. Gucci GG and "
                 "Hermes H buckle are the premium plays. Sam (sam_yin888) "
                 "is a trusted belt seller. Key QC: buckle finish, leather "
                 "quality, and stitching consistency. Hermes commands the "
                 "highest resale premium.",
        "where_to_buy": "Weidian — Sam (sam_yin888), Brother Sam "
                        "((brothersam.x.yupoo.com). Also: Nina, Darcy for "
                        "LV/Gucci. Agent: any major agent.",
        "source_subs": "r/FashionReps, r/DesignerReps",
    },
    {
        "item": "Dior Saddle Bag (Blue Oblique Jacquard)",
        "brand": "Dior",
        "category": "Accessories — Bags",
        "cost_yuan": "350–550",
        "cost_usd": "$50–75",
        "weight_g": 600,
        "resale_usd": "$120–180",
        "roi_pct": 85,
        "shipping_yuan": 56,
        "demand": "Very High",
        "notes": "One of the most repped bags, consistently in Weidian's top "
                 "10 most searched items. Retail $3,350+. QC tells: check "
                 "buckle text thickness and zipper extension. The Blue "
                 "Oblique Jacquard is the signature colorway. Black and "
                 "beige also sell well. Bags can be volumetrically heavy — "
                 "stuff with clothing to fill dead space when shipping.",
        "where_to_buy": "Weidian — Angel Factory (best quality), God Factory. "
                        "Sellers: Aadi, Linda, Heidi. Search on RepLadies "
                        "BST for reviews. Agent: any major agent.",
        "source_subs": "r/FashionReps, r/DesignerReps",
    },
    {
        "item": "Chanel Classic Flap (Caviar Leather)",
        "brand": "Chanel",
        "category": "Accessories — Bags",
        "cost_yuan": "500–700",
        "cost_usd": "$68–95",
        "weight_g": 700,
        "resale_usd": "$150–250",
        "roi_pct": 80,
        "shipping_yuan": 65,
        "demand": "High",
        "notes": "Highest absolute profit per unit in the accessories category "
                 "($80–150 net profit). Caviar leather holds up better than "
                 "lambskin for reps. 187 Factory is the gold standard but "
                 "expensive (800+ yuan). God Factory is the value alternative. "
                 "Medium Classic Flap in black is the universal bestseller. "
                 "This is a high-capital play but the margins justify it.",
        "where_to_buy": "187 Factory (via Heidi — heidi-show.x.yupoo.com) for "
                        "top tier. God Factory via Linda/Aadi for value tier. "
                        "Agent: best to order direct from these sellers.",
        "source_subs": "r/FashionReps, r/DesignerReps",
    },
]

WATCHES = [
    {
        "item": "Rolex Submariner 126610LN",
        "brand": "Rolex",
        "category": "Watches",
        "cost_usd": "$350–500",
        "weight_g": 155,
        "resale_usd": "$500–700",
        "roi_pct": 35,
        "best_factory": "VSF (best overall) / Clean Factory (#2)",
        "demand": "Very High",
        "notes": "The flagship rep watch. VSF offers smoother bezel, clearer "
                 "crystal, and DD3230 movement authenticity. Clean Factory "
                 "has best rehaut engraving and sharp case edges. Both use "
                 "904L stainless steel. Target weight: 155–160g (matches "
                 "retail). VR3235/VS3235 movement with 70-hour power reserve. "
                 "High capital investment but strong resale in the rep "
                 "community. Always verify waterproofing before shipping.",
        "where_to_buy": "Trusted Dealers (TDs) — Geektime, Hont, Jtime, "
                        "Eric at GeekTime. Never buy from random sellers. "
                        "r/RepTime sidebar has the full TD list.",
        "source_subs": "r/RepTime, r/ChinaTime",
    },
    {
        "item": "Rolex Daytona 'Panda' 116500LN",
        "brand": "Rolex",
        "category": "Watches",
        "cost_usd": "$400–600",
        "weight_g": 140,
        "resale_usd": "$550–800",
        "roi_pct": 30,
        "best_factory": "QF Factory (best) / Clean Factory / VSF",
        "demand": "High",
        "notes": "The 4130 clone fully functional chronograph is the holy "
                 "grail of rep watches. QF Factory has taken the lead from "
                 "the legendary Noob V4. The 'Panda' dial (white face, black "
                 "subdials) is the most popular configuration. Extremely "
                 "detailed piece — subdials must function correctly. Higher "
                 "buy-in but the per-unit profit is strong.",
        "where_to_buy": "Trusted Dealers — Geektime, Hont, Jtime. Always use "
                        "r/RepTime verified TDs. QF specifically requested "
                        "from dealer.",
        "source_subs": "r/RepTime",
    },
    {
        "item": "Omega Seamaster 300M / Aqua Terra",
        "brand": "Omega",
        "category": "Watches",
        "cost_usd": "$250–400",
        "weight_g": 150,
        "resale_usd": "$350–500",
        "roi_pct": 30,
        "best_factory": "VSF (undisputed champion for Omega)",
        "demand": "High",
        "notes": "Lower entry point than Rolex reps. VSF is the undisputed "
                 "champion for Omega reps. The Seamaster 300M is the most "
                 "popular model. Aqua Terra is the dressier alternative. "
                 "Good starter watch for rep watch reselling — lower risk "
                 "per unit than Rolex.",
        "where_to_buy": "Trusted Dealers — same TD list as Rolex. VSF "
                        "specifically requested. Hont often has the best "
                        "prices for Omega.",
        "source_subs": "r/RepTime, r/ChinaTime",
    },
    {
        "item": "Cartier Santos Medium / Large",
        "brand": "Cartier",
        "category": "Watches",
        "cost_usd": "$200–350",
        "weight_g": 120,
        "resale_usd": "$300–450",
        "roi_pct": 35,
        "best_factory": "GF Factory / V6F",
        "demand": "High (Rising)",
        "notes": "Growing interest as authentic Cartier prices have "
                 "appreciated faster than Rolex per recent market studies. "
                 "The Santos is an elegant, versatile dress watch. Lighter "
                 "than Rolex models. The quick-release bracelet/strap system "
                 "is a key feature to verify in QC. Rising demand = potential "
                 "for price increases on the rep side.",
        "where_to_buy": "Trusted Dealers — Geektime, Hont. GF Factory is the "
                        "recommended source for Cartier.",
        "source_subs": "r/RepTime",
    },
    {
        "item": "AP Royal Oak 15500 / 26240",
        "brand": "Audemars Piguet",
        "category": "Watches",
        "cost_usd": "$350–550",
        "weight_g": 160,
        "resale_usd": "$500–750",
        "roi_pct": 30,
        "best_factory": "APS Factory (best AP specialist) / ZF Factory",
        "demand": "High",
        "notes": "APS Factory specializes exclusively in AP — they are the "
                 "go-to source. Ceramic versions are frequently out of stock "
                 "due to demand. The Royal Oak is an iconic design with "
                 "strong brand recognition. The octagonal bezel screws are "
                 "the main QC checkpoint. Higher price point but matches "
                 "the caliber of the brand.",
        "where_to_buy": "Trusted Dealers — request APS Factory specifically. "
                        "ZF is the alternative. r/RepTime for TD list.",
        "source_subs": "r/RepTime",
    },
]

AGENTS_DATA = [
    {
        "agent": "Sugargoo",
        "status": "Active",
        "service_fee": "~5%",
        "qc_quality": "Industry-leading (multiple angles, weight, measurements)",
        "shipping_lines": "10+ US lines, 5+ EU lines",
        "free_storage": "90 days",
        "new_user_bonus": "800 CNY shipping coupons",
        "best_for": "QC quality, US shipping variety",
        "notes": "Best QC photos in the industry. High-res, multiple angles, "
                 "weight-on-scale shots. Vast shipping line selection. "
                 "Recommended as primary agent for serious resellers.",
        "rating": "A+",
    },
    {
        "agent": "CNFans",
        "status": "Active",
        "service_fee": "Low (~3-5%)",
        "qc_quality": "Good",
        "shipping_lines": "10+ shipping lines",
        "free_storage": "90 days",
        "new_user_bonus": "Various coupons",
        "best_for": "Lowest base shipping rates, beginners",
        "notes": "Often cited as having the lowest base shipping rates. "
                 "Most Pandabuy-like interface. Built-in 'Find Similar' tool. "
                 "NOTE: Orders can no longer be placed directly via Weidian "
                 "through CNFans — use alternative paste methods.",
        "rating": "A",
    },
    {
        "agent": "OopBuy",
        "status": "Active",
        "service_fee": "~5% (no explicit fee advertised)",
        "qc_quality": "Good",
        "shipping_lines": "Multiple US/EU optimized",
        "free_storage": "90 days",
        "new_user_bonus": "1,000 yuan welcome coupons",
        "best_for": "Low fees, EU/US routes",
        "notes": "Generally lower shipping costs for EU & US routes. "
                 "24–48 hour warehouse processing. Some reports of quoted "
                 "shipping being lower than final charges — budget 10-15% "
                 "above quoted prices.",
        "rating": "A-",
    },
    {
        "agent": "MuleBuy",
        "status": "Active",
        "service_fee": "Low",
        "qc_quality": "Free QC photos",
        "shipping_lines": "Multiple",
        "free_storage": "Free",
        "new_user_bonus": "Various",
        "best_for": "Simplicity, reliability",
        "notes": "Operating since 2018 with 200K+ orders. 7% market share. "
                 "5-star Trustpilot with 2,200+ reviews. One user reported "
                 "90 EUR for 6kg (approx 15 EUR/kg). Simple interface, "
                 "well-reviewed. Free QC photos and storage.",
        "rating": "A-",
    },
    {
        "agent": "WeGoBuy",
        "status": "Active",
        "service_fee": "Standard (~5-6%)",
        "qc_quality": "Standard",
        "shipping_lines": "Most comprehensive selection",
        "free_storage": "180 days",
        "new_user_bonus": "Various",
        "best_for": "Stability, most shipping options",
        "notes": "'Pioneer in the agent space.' Rock-solid stability and the "
                 "most comprehensive shipping line selection. Interface is "
                 "dated. Higher shipping costs and exchange rates than CNFans "
                 "or Sugargoo. Best for experienced users who value reliability.",
        "rating": "B+",
    },
    {
        "agent": "ACBuy",
        "status": "Active",
        "service_fee": "~5%",
        "qc_quality": "Good",
        "shipping_lines": "EU-optimized",
        "free_storage": "90 days",
        "new_user_bonus": "Various",
        "best_for": "EU shipping specifically",
        "notes": "Strong EU-optimized shipping lines with lower declared "
                 "values. Some complaints about shipping estimates being "
                 "inaccurate (costs increasing after items arrive). "
                 "Best choice if primarily shipping to Europe.",
        "rating": "B+",
    },
    {
        "agent": "KakoBuy",
        "status": "Active",
        "service_fee": "~5-6%",
        "qc_quality": "Community QC library",
        "shipping_lines": "Multiple",
        "free_storage": "90 days",
        "new_user_bonus": "Various coupons",
        "best_for": "Fast purchasing (<6 hours)",
        "notes": "13% market share. Intuitive UI, fast purchasing (<6 hours). "
                 "Community QC library is unique. Mixed Trustpilot (2.7/5) "
                 "with complaints about delayed refunds and lost parcels. "
                 "Use with caution for high-value orders.",
        "rating": "B",
    },
    {
        "agent": "CSSBuy",
        "status": "Active",
        "service_fee": "Varies",
        "qc_quality": "Standard",
        "shipping_lines": "Multiple",
        "free_storage": "Standard",
        "new_user_bonus": "Various",
        "best_for": "Good exchange rates",
        "notes": "Still operating with mixed reviews. Some report high "
                 "shipping costs ($150 for 8kg). Praised for good exchange "
                 "rates. Extra warehouse fees reported by some users. "
                 "Not recommended as primary agent.",
        "rating": "B-",
    },
    {
        "agent": "Superbuy",
        "status": "Active",
        "service_fee": "6-8% (higher than competitors)",
        "qc_quality": "Standard",
        "shipping_lines": "Multiple",
        "free_storage": "180 days",
        "new_user_bonus": "Various",
        "best_for": "Customer support, mobile app",
        "notes": "Higher fees than competitors including a reported 7% hidden "
                 "top-up charge. Free mobile app. Helpful customer support. "
                 "180 days free storage is generous. Best for users who "
                 "prioritize support over cost.",
        "rating": "B",
    },
    {
        "agent": "Pandabuy",
        "status": "SHUT DOWN (Permanently)",
        "service_fee": "N/A",
        "qc_quality": "N/A",
        "shipping_lines": "N/A",
        "free_storage": "N/A",
        "new_user_bonus": "N/A",
        "best_for": "N/A — Do not use",
        "notes": "PERMANENTLY SHUT DOWN. Raided by Chinese police in April "
                 "2024 following legal action from 16 brand owners. "
                 "Warehouses raided, parcels seized, balances frozen. "
                 "Users have migrated to CNFans, Sugargoo, and OopBuy.",
        "rating": "X",
    },
    {
        "agent": "Basetao",
        "status": "Active (Not Recommended)",
        "service_fee": "Standard",
        "qc_quality": "Below average",
        "shipping_lines": "Limited",
        "free_storage": "Standard",
        "new_user_bonus": "None",
        "best_for": "Not recommended",
        "notes": "Negative recent reviews. Reports of inflated shipping "
                 "(1.5x expected). Slow support (2x slower than Superbuy). "
                 "Difficulty withdrawing leftover funds. AVOID.",
        "rating": "D",
    },
]

BATCH_GUIDE = [
    {"batch": "LJR", "specialty": "Air Jordan 1, 3, 4, 5, 6, 11, 13",
     "tier": "Premium", "price_yuan": "400–600",
     "notes": "King of Jordan 1s. Sharp toe boxes, high-quality leather, "
              "flawless logo placement. 'No one in the market can surpass "
              "LJR Jordan.' Worth the premium where leather quality matters."},
    {"batch": "PK 4.0", "specialty": "Yeezy 350 (original), AJ 3/4/6, Reverse Swoosh",
     "tier": "Premium", "price_yuan": "350–550",
     "notes": "On par with LJR for detail focus. Best for Jordan 4 Reverse "
              "Swoosh series. Strong elephant print on AJ3."},
    {"batch": "OG", "specialty": "AJ1, 3, 4, 5, 6, 11, 13 + Yeezy 350",
     "tier": "High", "price_yuan": "380–550",
     "notes": "Best elephant print accuracy across models. Good all-rounder "
              "alternative to LJR. Strong Off-White collab accuracy."},
    {"batch": "GX", "specialty": "Jordan 4 (all colorways), Kobe",
     "tier": "High", "price_yuan": "~350",
     "notes": "Best value for Jordan 4s specifically. 70+ units sold on "
              "JadeShip in 30 days at ~350 yuan. Kobe models also strong."},
    {"batch": "M Batch", "specialty": "Nike Dunks (entire lineup + collabs)",
     "tier": "Premium", "price_yuan": "180–350",
     "notes": "Consensus best for ALL Nike Dunks. 'Even experienced "
              "sneakerheads have trouble telling the difference.' Best "
              "value-to-quality ratio in the entire rep sneaker market."},
    {"batch": "SH Batch", "specialty": "Nike Dunks (value alternative to M)",
     "tier": "Mid-High", "price_yuan": "160–250",
     "notes": "From Dongguan. 'Superior fit' and fewer defects than budget "
              "options. Good alternative when M Batch is out of stock."},
    {"batch": "LW (BASF)", "specialty": "Yeezy 350, 500, 700",
     "tier": "Premium", "price_yuan": "300–450",
     "notes": "Uses BASF 'Popcorn' foam that closely matches retail Boost "
              "feel. The comfort difference vs regular foam is immediately "
              "noticeable. Never ship budget foam to Yeezy-experienced buyers."},
    {"batch": "VG/OK", "specialty": "Balenciaga Track, 3XL, Tire, Triple S",
     "tier": "Top-Tier", "price_yuan": "400–800",
     "notes": "Rated 5/5 stars for the entire Balenciaga Paris line. "
              "The only recommended batches for Balenciaga sneakers."},
    {"batch": "S2", "specialty": "Various (budget alternative)",
     "tier": "Mid", "price_yuan": "200–400",
     "notes": "Budget alternatives across models. NOT recommended for "
              "resale — quality inconsistency will lead to returns."},
]

TRENDING_BRANDS = [
    {"brand": "Chrome Hearts", "status": "Peak",
     "grailed_rank": "#1 Overall Brand (Grailed 2025)",
     "best_items": "Rings ($12–22), cross pendants, bracelets, necklaces",
     "why_trending": "Gothic silver aesthetic is dominant in 2026. Retail "
                     "prices ($2,000–$5,000+) make reps incredibly attractive. "
                     "Celebrity endorsements from hip-hop and fashion culture.",
     "rep_quality": "925 silver reps are very close to retail. Avoid alloy "
                    "versions — customers notice the weight difference."},
    {"brand": "ERD (Enfants Riches Deprimes)", "status": "Rising Fast",
     "grailed_rank": "Top 10 (Growing)",
     "best_items": "Graphic cut-off tanks ($22–40), distressed tees",
     "why_trending": "SS26 collection at Paris Fashion Week. Retail tees "
                     "$700–$1,800. The punk/grunge aesthetic is peak 2026. "
                     "r/QualityReps is obsessed with this brand.",
     "rep_quality": "Varies by seller. Print quality and distressing accuracy "
                    "are the key differentiators. Always QC carefully."},
    {"brand": "Balenciaga", "status": "Peak",
     "grailed_rank": "#1 Footwear Brand (Grailed 2025)",
     "best_items": "Track 2, Runner, 3XL, Triple S sneakers + logo tees",
     "why_trending": "Dominates both sneaker and clothing categories. The "
                     "oversized/chunky aesthetic remains in demand. Multiple "
                     "new colorways each season.",
     "rep_quality": "VG/OK Batch sneakers are rated 5/5. Clothing from "
                    "Cloyad/LY Factory is consistent quality."},
    {"brand": "Rick Owens", "status": "Peak",
     "grailed_rank": "#2 Footwear Brand (Grailed 2025)",
     "best_items": "Ramones, Geobaskets, DRKSHDW tees/tanks",
     "why_trending": "FW2026 collection just shown in Paris. The avant-garde "
                     "aesthetic has gone mainstream through social media. "
                     "Strong crossover appeal.",
     "rep_quality": "DRKSTUDIO is THE source — no one else comes close for "
                    "accuracy. QC: check W thickness, stitching, hole placement."},
    {"brand": "Maison Margiela", "status": "Rising",
     "grailed_rank": "Top 5 Footwear",
     "best_items": "GATs (#2 on JadeShip), Tabi boots, Futures sneakers",
     "why_trending": "GATs are #2 most sold item on JadeShip (197 units/30 "
                     "days). Tabi boots have cult following. Weidian links "
                     "heavily shared on TikTok.",
     "rep_quality": "GATs are close to retail due to simple construction. "
                    "Tabi boots vary more — check stitching and split-toe shape."},
    {"brand": "Miu Miu", "status": "Rising Fast",
     "grailed_rank": "Trending",
     "best_items": "Ballet sneakers (new SS26), shrunken leather jackets",
     "why_trending": "SS26 runway was a sensation. The apron-focused "
                     "collection generated enormous buzz. Ballet sneaker "
                     "silhouette is the breakout item of the season. "
                     "Miu Miu is having a 'moment.'",
     "rep_quality": "Rep infrastructure still developing — expect quality to "
                    "improve as demand increases. Early movers have advantage."},
    {"brand": "Dior", "status": "Stable High",
     "grailed_rank": "Top 10",
     "best_items": "Saddle Bag ($50–75), B22 sneakers, Oblique pattern items",
     "why_trending": "Saddle Bag is consistently in top 10 most searched on "
                     "Weidian. B22 sneaker gaining momentum. Oblique pattern "
                     "is instantly recognizable.",
     "rep_quality": "Angel Factory and God Factory for bags. Check buckle text "
                    "thickness and zipper extension on Saddle Bags."},
    {"brand": "Vetements", "status": "Stable",
     "grailed_rank": "Niche High",
     "best_items": "DHL hoodie, oversized logo hoodies, archive tees",
     "why_trending": "Archive-inspired pieces gaining traction in QualityReps. "
                     "The deliberately oversized fit is forgiving on sizing. "
                     "Less saturated than Balenciaga = less competition.",
     "rep_quality": "Cloyad, Reon District carry quality pieces. Print quality "
                    "and weight of fabric are the main QC points."},
    {"brand": "Acne Studios", "status": "Stable",
     "grailed_rank": "Niche",
     "best_items": "Face logo items, scarves, knitwear, cowboy boots (new)",
     "why_trending": "Minimalist Scandinavian aesthetic has steady demand. "
                     "SS26 cowboy boots are generating new interest. Scarves "
                     "are lightweight, high-margin items.",
     "rep_quality": "Available through Taobao sellers. Less established rep "
                    "infrastructure than bigger brands — quality varies."},
    {"brand": "Prada", "status": "Stable High",
     "grailed_rank": "Top 10",
     "best_items": "Re-Nylon bags, triangle logo items, Cloudbust sneakers",
     "why_trending": "Prada's minimalist luxury aesthetic never goes out of "
                     "style. Re-Nylon line is sustainable-positioned which "
                     "appeals to younger buyers.",
     "rep_quality": "Good quality available from major sellers. Triangle logo "
                    "placement is the main QC checkpoint."},
]

SHIPPING_TIPS = [
    "ALWAYS drop shoe boxes — saves 200–300g per pair (19–28 yuan shipping savings)",
    "Jewelry has the BEST shipping economics — ship 20 Chrome Hearts rings (1kg total) for 93 yuan vs. 1 pair of shoes for the same price",
    "Request vacuum compression for clothing — reduces volumetric weight dramatically",
    "Use 'actual weight' shipping lines when available (e.g., Sugargoo US Tax-Free Actual Weight)",
    "Ship clothing in bags, not boxes — lines like 'US Duty-Free Clothes (PH)' use polybags",
    "Consolidate hauls into 8–15kg+ parcels — tiered pricing reduces effective per-kg cost",
    "Stuff bags with clothing/socks to eliminate dead space and reduce volumetric penalty",
    "Avoid puffer jackets and bulky items — 1kg actual can become 3kg volumetric",
    "Summer items (swim trunks, tees, shorts) fold flat = minimal volumetric penalty",
    "Sea freight lines (30–60 day transit) can achieve ~$5–6/kg for large hauls (15kg+)",
]

MARKET_ALERTS = [
    {"alert": "US De Minimis Exemption Removed (May 2025)",
     "impact": "Critical",
     "detail": "ALL China parcels now face potential duties or flat postal "
               "fees of $80–$200 USD. Factor this into cost calculations "
               "for US-bound shipments. This fundamentally changes the "
               "economics of small parcels — consolidate orders."},
    {"alert": "Pandabuy Permanently Shut Down",
     "impact": "High",
     "detail": "Raided April 2024 by Chinese police. Users migrated to "
               "CNFans, Sugargoo, OopBuy. Do NOT attempt to use Pandabuy."},
    {"alert": "Factory Production Cutbacks",
     "impact": "Medium",
     "detail": "US/EU tariff increases in 2026 are causing factories in "
               "Guangzhou and Putian to cut back on high-quality replica "
               "production. Buy premium batches before supply shrinks further."},
    {"alert": "CNFans Direct Weidian Ordering Disabled",
     "impact": "Low",
     "detail": "Orders can no longer be placed directly via Weidian through "
               "CNFans. Use the paste-link method or alternative agents."},
    {"alert": "GlFinder (QC Aggregator) Terminated",
     "impact": "Low",
     "detail": "GlFinder now redirects to JadeShip. The community is "
               "consolidating around JadeShip for QC verification and "
               "trending item tracking."},
    {"alert": "EU Packaging Regulations (2026–2028)",
     "impact": "Medium",
     "detail": "New rules penalizing packages with >50% empty space. "
               "Ensure parcels are tightly packed to avoid surcharges "
               "on EU-bound shipments."},
]


# ── Page builder ───────────────────────────────────────────────────────────

def _buying_guide(_D):
    """Full buying guide page — compiled from Reddit research across 18+ subs."""

    # Build DataFrames from static data
    jewelry_df = pd.DataFrame(JEWELRY_ITEMS)
    sneakers_df = pd.DataFrame(SNEAKER_ITEMS)
    clothing_df = pd.DataFrame(CLOTHING_ITEMS)
    accessories_df = pd.DataFrame(ACCESSORIES_ITEMS)
    watches_df = pd.DataFrame(WATCHES)
    agents_df = pd.DataFrame(AGENTS_DATA)
    batch_df = pd.DataFrame(BATCH_GUIDE)
    brands_df = pd.DataFrame(TRENDING_BRANDS)
    alerts_df = pd.DataFrame(MARKET_ALERTS)

    # Combine all items for ROI chart
    all_items = []
    for src, cat_label in [
        (JEWELRY_ITEMS, "Jewelry"),
        (SNEAKER_ITEMS, "Sneakers"),
        (CLOTHING_ITEMS, "Clothing"),
        (ACCESSORIES_ITEMS, "Accessories"),
    ]:
        for item in src:
            all_items.append({
                "name": f"{item['brand']} — {item['item']}",
                "category": cat_label,
                "roi_pct": item["roi_pct"],
                "weight_g": item["weight_g"],
                "demand": item.get("demand", "High"),
            })
    roi_df = pd.DataFrame(all_items).sort_values("roi_pct", ascending=True)

    # ROI bar chart
    roi_fig = px.bar(
        roi_df, x="roi_pct", y="name", orientation="h",
        color="category",
        color_discrete_map={
            "Jewelry": C_GREEN,
            "Sneakers": C_BLUE,
            "Clothing": C_PURPLE,
            "Accessories": C_AMBER,
        },
        labels={"roi_pct": "Estimated ROI %", "name": "", "category": "Category"},
        custom_data=["demand", "weight_g"],
    )
    roi_fig.update_traces(
        hovertemplate=(
            "<b>%{y}</b><br>"
            "ROI: %{x}%<br>"
            "Demand: %{customdata[0]}<br>"
            "Weight: %{customdata[1]}g<extra></extra>"
        )
    )

    # Weight vs ROI scatter
    scatter_fig = px.scatter(
        roi_df, x="weight_g", y="roi_pct",
        color="category",
        size="roi_pct",
        color_discrete_map={
            "Jewelry": C_GREEN,
            "Sneakers": C_BLUE,
            "Clothing": C_PURPLE,
            "Accessories": C_AMBER,
        },
        text="name",
        labels={"weight_g": "Weight (g)", "roi_pct": "ROI %", "category": "Category"},
    )
    scatter_fig.update_traces(textposition="top center", textfont_size=9)
    scatter_fig.update_layout(showlegend=True)

    # Shipping cost comparison
    ship_items = []
    for src in [JEWELRY_ITEMS, SNEAKER_ITEMS, CLOTHING_ITEMS, ACCESSORIES_ITEMS]:
        for item in src:
            ship_items.append({
                "name": f"{item['brand']} {item['item']}"[:40],
                "shipping_yuan": item["shipping_yuan"],
                "weight_g": item["weight_g"],
            })
    ship_df = pd.DataFrame(ship_items).sort_values("shipping_yuan", ascending=True)

    ship_fig = px.bar(
        ship_df, x="shipping_yuan", y="name", orientation="h",
        color="shipping_yuan",
        color_continuous_scale=[[0, C_GREEN], [0.5, C_AMBER], [1, C_RED]],
        labels={"shipping_yuan": "Shipping Cost (yuan)", "name": ""},
    )

    # Agent rating chart
    active_agents = [a for a in AGENTS_DATA if a["status"] != "SHUT DOWN (Permanently)"
                     and a["rating"] != "D"]
    rating_map = {"A+": 5, "A": 4.5, "A-": 4, "B+": 3.5, "B": 3, "B-": 2.5}
    agent_chart_data = []
    for a in active_agents:
        score = rating_map.get(a["rating"], 2)
        agent_chart_data.append({
            "agent": a["agent"],
            "score": score,
            "rating": a["rating"],
            "best_for": a["best_for"],
        })
    agent_chart_df = pd.DataFrame(agent_chart_data).sort_values("score", ascending=True)

    agent_fig = px.bar(
        agent_chart_df, x="score", y="agent", orientation="h",
        color="score",
        color_continuous_scale=[[0, C_RED], [0.5, C_AMBER], [1, C_GREEN]],
        labels={"score": "Rating Score", "agent": ""},
        custom_data=["rating", "best_for"],
    )
    agent_fig.update_traces(
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Rating: %{customdata[0]}<br>"
            "Best for: %{customdata[1]}<extra></extra>"
        )
    )

    # ── Build the page ──
    return html.Div([
        # Header
        explainer([
            html.Strong("Buying Guide — Deep-Dive ROI Analysis for Resellers. "),
            "Compiled from live data across ", html.Strong("18+ Reddit subreddits"),
            " (r/FashionReps, r/Repsneakers, r/DesignerReps, r/QualityReps, "
            "r/RepTime, r/repbudgetsneakers, r/weidianwarriors, r/CloseToRetail, "
            "r/BigBoiRepFashion, r/BudgetBatch, r/cnfashionreps, r/FashionRepsBST, "
            "r/sneakerreps, r/ChinaTime, r/Sugargoo, r/Superbuy, r/RepForwarding, "
            "r/TheWorldOfRepsneakers), plus agent communities (ACBuy, CSSBuy, "
            "OopBuy, MuleBuy). ",
            html.Strong("Shipping basis: 93 yuan/kg"),
            " charged on max(physical, volumetric weight). ",
            "Data reflects April 2026 market conditions. ",
            html.Strong("Only mid-to-premium quality items included"),
            " — no budget batches that would lead to customer dissatisfaction.",
        ]),

        # Market Alerts
        section("Market Alerts", "Critical changes affecting the rep market in 2026."),
        make_table(alerts_df, {
            "alert": "Alert",
            "impact": "Impact",
            "detail": "Details",
        }, page_size=6),

        # KPI Row
        html.Div([
            kpi(len(JEWELRY_ITEMS) + len(SNEAKER_ITEMS) + len(CLOTHING_ITEMS)
                + len(ACCESSORIES_ITEMS), "Items Analyzed", C_CYAN),
            kpi(len(WATCHES), "Watches Tracked", C_PURPLE),
            kpi(len(TRENDING_BRANDS), "Brands Profiled", C_GREEN),
            kpi(len(AGENTS_DATA), "Agents Reviewed", C_AMBER),
            kpi("18+", "Subreddits Sourced", C_RED),
        ], className="kpi-row"),

        # ROI Overview
        section("ROI Overview — All Items Ranked",
                "Every item ranked by estimated return on investment, "
                "factoring in purchase cost, shipping at 93 yuan/kg, and resale value."),
        explainer([
            html.Strong("How ROI is calculated: "),
            "ROI % = (Resale Price - Purchase Cost - Shipping Cost) / "
            "(Purchase Cost + Shipping Cost) x 100. ",
            html.Strong("Green = Jewelry"), " (best shipping economics). ",
            html.Strong("Blue = Sneakers"), " (volume sellers). ",
            html.Strong("Purple = Clothing"), " (lightweight, good margins). ",
            html.Strong("Amber = Accessories"), " (compact, high value). ",
            "Hover over bars for demand level and weight details.",
        ], "green"),
        chart_card("All Items — Estimated ROI %",
                   "Higher = better return. Color indicates category. "
                   "Jewelry dominates due to negligible shipping costs.",
                   dcc.Graph(
                       figure=style_fig(roi_fig),
                       config={"displayModeBar": False},
                       style={"height": f"{max(500, len(all_items) * 28)}px"},
                   )),

        # Weight vs ROI scatter
        html.Div([
            chart_card("Weight vs ROI — The Shipping Sweet Spot",
                       "Items in the top-left corner (low weight, high ROI) "
                       "are the best shipping-optimized picks.",
                       dcc.Graph(
                           figure=style_fig(scatter_fig),
                           config={"displayModeBar": False},
                           style={"height": "450px"},
                       )),
            chart_card("Shipping Cost Per Item (at 93 yuan/kg)",
                       "Green = cheap to ship. Red = expensive. "
                       "Jewelry costs 3–7 yuan to ship vs 80–112 yuan for sneakers.",
                       dcc.Graph(
                           figure=style_fig(ship_fig),
                           config={"displayModeBar": False},
                           style={"height": f"{max(400, len(ship_items) * 22)}px"},
                       )),
        ], className="two-col"),

        # ── TIER 1: JEWELRY ──
        section("TIER 1: Jewelry — Best ROI Category",
                "Lightweight with massive markup gaps. Ship 20 rings in 1kg "
                "for 93 yuan total — same shipping cost as ONE pair of shoes."),
        explainer([
            html.Strong("Why jewelry leads ROI: "),
            "Chrome Hearts rings cost 85–160 yuan (~$12–22) and resell for "
            "$40–80. At 40g per ring, shipping costs are negligible (4 yuan). "
            "That's a 300%+ ROI. The key is material quality — always verify ",
            html.Strong("925 sterling silver"), " hallmarks. Cheap alloy "
            "versions weigh noticeably less and will disappoint customers. "
            "Vivienne Westwood necklaces are the second-best play, driven "
            "by TikTok virality among Gen Z buyers.",
        ], "green"),
        make_table(jewelry_df, {
            "item": "Item",
            "brand": "Brand",
            "cost_yuan": "Cost (yuan)",
            "cost_usd": "Cost (USD)",
            "weight_g": "Weight (g)",
            "resale_usd": "Resale (USD)",
            "roi_pct": "ROI %",
            "shipping_yuan": "Ship Cost (yuan)",
            "material": "Material",
            "demand": "Demand",
        }, page_size=10),
        # Jewelry detail cards
        *[
            html.Div([
                html.Div([
                    html.Strong(f"{j['brand']} — {j['item']}",
                                style={"fontSize": "1rem", "color": C_GREEN}),
                    html.Div(j["notes"],
                             style={"fontSize": "0.82rem", "color": "#9aa0b2",
                                    "marginTop": "6px", "lineHeight": "1.6"}),
                    html.Div([
                        html.Strong("Where to buy: ", style={"color": "#e8eaed"}),
                        html.Span(j["where_to_buy"],
                                  style={"color": "#9aa0b2"}),
                    ], style={"marginTop": "8px", "fontSize": "0.82rem"}),
                    html.Div([
                        html.Strong("Source subreddits: ", style={"color": "#e8eaed"}),
                        html.Span(j["source_subs"],
                                  style={"color": "#8b5cf6"}),
                    ], style={"marginTop": "4px", "fontSize": "0.82rem"}),
                ], style={"padding": "16px 20px", "background": "var(--bg-card)",
                          "border": "1px solid var(--border)",
                          "borderLeft": f"3px solid {C_GREEN}",
                          "borderRadius": "8px", "marginBottom": "12px"}),
            ])
            for j in JEWELRY_ITEMS
        ],

        # ── TIER 2: SNEAKERS ──
        section("TIER 2: Sneakers — Volume Sellers",
                "Consistent demand, proven batches, strong community consensus. "
                "Always drop the shoe box to save 200–300g per pair."),
        explainer([
            html.Strong("Sneaker economics: "),
            "Sneakers are heavier than jewelry (800–1200g) so shipping eats "
            "into margins. The key is choosing the right batch — premium "
            "batches (LJR, M Batch, VG/OK) are worth the extra cost because "
            "customers notice quality differences and budget batches lead to "
            "returns. ",
            html.Strong("Nike Dunks (M Batch)"), " offer the best "
            "value-to-quality ratio. ",
            html.Strong("Jordan 4 (GX Batch)"), " is the volume sweet spot. ",
            html.Strong("Balenciaga (VG/OK)"), " commands the highest resale.",
        ], "amber"),
        make_table(sneakers_df, {
            "item": "Item",
            "brand": "Brand",
            "cost_yuan": "Cost (yuan)",
            "cost_usd": "Cost (USD)",
            "weight_g": "Weight (g)",
            "resale_usd": "Resale (USD)",
            "roi_pct": "ROI %",
            "shipping_yuan": "Ship (yuan)",
            "best_batch": "Best Batch",
            "demand": "Demand",
        }, page_size=12),
        # Sneaker detail cards
        *[
            html.Div([
                html.Div([
                    html.Strong(f"{s['brand']} — {s['item']}",
                                style={"fontSize": "1rem", "color": C_BLUE}),
                    html.Div([
                        html.Strong("Best Batch: ", style={"color": "#e8eaed"}),
                        html.Span(s["best_batch"],
                                  style={"color": C_CYAN}),
                    ], style={"marginTop": "6px", "fontSize": "0.82rem"}),
                    html.Div(s["notes"],
                             style={"fontSize": "0.82rem", "color": "#9aa0b2",
                                    "marginTop": "6px", "lineHeight": "1.6"}),
                    html.Div([
                        html.Strong("Where to buy: ", style={"color": "#e8eaed"}),
                        html.Span(s["where_to_buy"],
                                  style={"color": "#9aa0b2"}),
                    ], style={"marginTop": "8px", "fontSize": "0.82rem"}),
                    html.Div([
                        html.Strong("Source subreddits: ", style={"color": "#e8eaed"}),
                        html.Span(s["source_subs"],
                                  style={"color": "#8b5cf6"}),
                    ], style={"marginTop": "4px", "fontSize": "0.82rem"}),
                ], style={"padding": "16px 20px", "background": "var(--bg-card)",
                          "border": "1px solid var(--border)",
                          "borderLeft": f"3px solid {C_BLUE}",
                          "borderRadius": "8px", "marginBottom": "12px"}),
            ])
            for s in SNEAKER_ITEMS
        ],

        # ── TIER 3: CLOTHING ──
        section("TIER 3: Clothing — Summer Focus",
                "Lightweight tees and seasonal items offer strong margins. "
                "ERD is the standout opportunity with retail tees at $700–$1,800."),
        explainer([
            html.Strong("ERD is the #1 clothing opportunity for 2026. "),
            "Retail tees sell for $700–$1,800 while reps cost $22–40. "
            "Even at premium quality rep pricing, the perceived value gap "
            "is enormous. r/QualityReps is obsessed with this brand after "
            "the SS26 Paris Fashion Week showing. ",
            html.Strong("Summer timing: "),
            "Swim trunks, slides, and polo shirts should be listed NOW "
            "for peak April–August demand. Summer 2026 colors: rich violet, "
            "brilliant aquamarine, cobalt blue — NOT soft pastels.",
        ], "purple"),
        make_table(clothing_df, {
            "item": "Item",
            "brand": "Brand",
            "cost_yuan": "Cost (yuan)",
            "cost_usd": "Cost (USD)",
            "weight_g": "Weight (g)",
            "resale_usd": "Resale (USD)",
            "roi_pct": "ROI %",
            "shipping_yuan": "Ship (yuan)",
            "demand": "Demand",
        }, page_size=12),
        *[
            html.Div([
                html.Div([
                    html.Strong(f"{c['brand']} — {c['item']}",
                                style={"fontSize": "1rem", "color": C_PURPLE}),
                    html.Div(c["notes"],
                             style={"fontSize": "0.82rem", "color": "#9aa0b2",
                                    "marginTop": "6px", "lineHeight": "1.6"}),
                    html.Div([
                        html.Strong("Where to buy: ", style={"color": "#e8eaed"}),
                        html.Span(c["where_to_buy"],
                                  style={"color": "#9aa0b2"}),
                    ], style={"marginTop": "8px", "fontSize": "0.82rem"}),
                    html.Div([
                        html.Strong("Source subreddits: ", style={"color": "#e8eaed"}),
                        html.Span(c["source_subs"],
                                  style={"color": "#8b5cf6"}),
                    ], style={"marginTop": "4px", "fontSize": "0.82rem"}),
                ], style={"padding": "16px 20px", "background": "var(--bg-card)",
                          "border": "1px solid var(--border)",
                          "borderLeft": f"3px solid {C_PURPLE}",
                          "borderRadius": "8px", "marginBottom": "12px"}),
            ])
            for c in CLOTHING_ITEMS
        ],

        # ── TIER 4: ACCESSORIES ──
        section("TIER 4: Accessories — Compact, High Value",
                "Wallets, sunglasses, belts, and bags. Card holders and "
                "sunglasses have the best shipping economics after jewelry."),
        explainer([
            html.Strong("Accessories sweet spot: "),
            "Goyard card holders (100g, $35–65 resale) and Cartier sunglasses "
            "(60g, $30–60 resale) combine compact size with high perceived "
            "value. Bags (Dior Saddle, Chanel Classic Flap) offer the highest "
            "absolute profit per unit ($80–150) but be aware of volumetric "
            "weight — stuff bags with clothing/socks when shipping to "
            "eliminate dead space.",
        ], "amber"),
        make_table(accessories_df, {
            "item": "Item",
            "brand": "Brand",
            "cost_yuan": "Cost (yuan)",
            "cost_usd": "Cost (USD)",
            "weight_g": "Weight (g)",
            "resale_usd": "Resale (USD)",
            "roi_pct": "ROI %",
            "shipping_yuan": "Ship (yuan)",
            "demand": "Demand",
        }, page_size=10),
        *[
            html.Div([
                html.Div([
                    html.Strong(f"{a['brand']} — {a['item']}",
                                style={"fontSize": "1rem", "color": C_AMBER}),
                    html.Div(a["notes"],
                             style={"fontSize": "0.82rem", "color": "#9aa0b2",
                                    "marginTop": "6px", "lineHeight": "1.6"}),
                    html.Div([
                        html.Strong("Where to buy: ", style={"color": "#e8eaed"}),
                        html.Span(a["where_to_buy"],
                                  style={"color": "#9aa0b2"}),
                    ], style={"marginTop": "8px", "fontSize": "0.82rem"}),
                    html.Div([
                        html.Strong("Source subreddits: ", style={"color": "#e8eaed"}),
                        html.Span(a["source_subs"],
                                  style={"color": "#8b5cf6"}),
                    ], style={"marginTop": "4px", "fontSize": "0.82rem"}),
                ], style={"padding": "16px 20px", "background": "var(--bg-card)",
                          "border": "1px solid var(--border)",
                          "borderLeft": f"3px solid {C_AMBER}",
                          "borderRadius": "8px", "marginBottom": "12px"}),
            ])
            for a in ACCESSORIES_ITEMS
        ],

        # ── TIER 5: WATCHES ──
        section("TIER 5: Watches — Specialist Market",
                "High capital, high absolute profit. Use r/RepTime Trusted "
                "Dealers (TDs) exclusively — never buy from unverified sellers."),
        explainer([
            html.Strong("Watch market dynamics: "),
            "Rep watches require higher capital ($250–600 per unit) and "
            "specialized knowledge. The ROI is lower percentage-wise (30–35%) "
            "but absolute profit per unit ($100–200) is strong. ",
            html.Strong("VSF"), " is the undisputed champion for Rolex Submariner "
            "and Omega. ",
            html.Strong("Clean Factory"), " excels at rehaut engraving and case "
            "finishing. ",
            html.Strong("APS Factory"), " specializes in AP Royal Oak. "
            "Cartier Santos is the rising opportunity — authentic prices are "
            "appreciating faster than Rolex, driving rep interest up.",
        ], "red"),
        make_table(watches_df, {
            "item": "Item",
            "brand": "Brand",
            "cost_usd": "Cost (USD)",
            "weight_g": "Weight (g)",
            "resale_usd": "Resale (USD)",
            "roi_pct": "ROI %",
            "best_factory": "Best Factory",
            "demand": "Demand",
        }, page_size=8),
        *[
            html.Div([
                html.Div([
                    html.Strong(f"{w['brand']} — {w['item']}",
                                style={"fontSize": "1rem", "color": C_RED}),
                    html.Div([
                        html.Strong("Best Factory: ", style={"color": "#e8eaed"}),
                        html.Span(w["best_factory"],
                                  style={"color": C_CYAN}),
                    ], style={"marginTop": "6px", "fontSize": "0.82rem"}),
                    html.Div(w["notes"],
                             style={"fontSize": "0.82rem", "color": "#9aa0b2",
                                    "marginTop": "6px", "lineHeight": "1.6"}),
                    html.Div([
                        html.Strong("Where to buy: ", style={"color": "#e8eaed"}),
                        html.Span(w["where_to_buy"],
                                  style={"color": "#9aa0b2"}),
                    ], style={"marginTop": "8px", "fontSize": "0.82rem"}),
                    html.Div([
                        html.Strong("Source subreddits: ", style={"color": "#e8eaed"}),
                        html.Span(w["source_subs"],
                                  style={"color": "#8b5cf6"}),
                    ], style={"marginTop": "4px", "fontSize": "0.82rem"}),
                ], style={"padding": "16px 20px", "background": "var(--bg-card)",
                          "border": "1px solid var(--border)",
                          "borderLeft": f"3px solid {C_RED}",
                          "borderRadius": "8px", "marginBottom": "12px"}),
            ])
            for w in WATCHES
        ],

        # ── BATCH QUALITY GUIDE ──
        section("Batch Quality Guide — Premium Batches Only",
                "Community-consensus best batches for popular models. "
                "Budget batches (S2, HP, A Batch) excluded — they lead "
                "to customer complaints and returns."),
        explainer([
            html.Strong("Batch selection matters more than seller selection. "),
            "The same batch from different sellers is essentially the same "
            "shoe — it comes from the same factory. Focus on getting the "
            "right batch, then find the cheapest seller carrying it. ",
            html.Strong("LJR"), " = king of Jordans (leather quality). ",
            html.Strong("M Batch"), " = king of Dunks (accuracy). ",
            html.Strong("LW/BASF"), " = king of Yeezys (foam feel). ",
            html.Strong("VG/OK"), " = king of Balenciaga (5/5 rated). "
            "Never mix batches when stocking multiple colorways of the same "
            "model — customers will notice inconsistency.",
        ], "green"),
        make_table(batch_df, {
            "batch": "Batch",
            "specialty": "Best For",
            "tier": "Tier",
            "price_yuan": "Price Range (yuan)",
            "notes": "Community Notes",
        }, page_size=12),

        # ── TRENDING BRANDS ──
        section("Trending Brands — Deep Profiles",
                "What's hot, why it's hot, and what to stock from each brand."),
        explainer([
            html.Strong("Brand status guide: "),
            html.Strong("Peak"), " = maximum demand right now, stock heavily. ",
            html.Strong("Rising Fast"), " = demand accelerating, early mover advantage. ",
            html.Strong("Rising"), " = growing steadily. ",
            html.Strong("Stable High"), " = consistent demand, safe bet. ",
            html.Strong("Stable"), " = niche but reliable.",
        ], "purple"),
        make_table(brands_df, {
            "brand": "Brand",
            "status": "Status",
            "grailed_rank": "Grailed Ranking",
            "best_items": "Best Items",
            "why_trending": "Why Trending",
            "rep_quality": "Rep Quality Notes",
        }, page_size=12),

        # ── SHOPPING AGENTS ──
        section("Shopping Agent Comparison",
                "Ranked by overall reliability, shipping costs, QC quality, "
                "and community feedback. Pandabuy is permanently shut down."),
        chart_card("Agent Ratings (April 2026)",
                   "Based on community consensus, shipping costs, QC quality, "
                   "and reliability. Higher = better.",
                   dcc.Graph(
                       figure=style_fig(agent_fig),
                       config={"displayModeBar": False},
                       style={"height": "350px"},
                   )),
        make_table(agents_df, {
            "agent": "Agent",
            "status": "Status",
            "service_fee": "Service Fee",
            "qc_quality": "QC Quality",
            "free_storage": "Free Storage",
            "new_user_bonus": "New User Bonus",
            "best_for": "Best For",
            "rating": "Rating",
        }, page_size=12),
        *[
            html.Div([
                html.Div([
                    html.Strong(
                        f"{ag['agent']} — {ag['rating']}",
                        style={"fontSize": "1rem",
                               "color": C_GREEN if ag["rating"] in ("A+", "A")
                               else C_AMBER if ag["rating"].startswith("B")
                               else C_RED},
                    ),
                    html.Div(ag["notes"],
                             style={"fontSize": "0.82rem", "color": "#9aa0b2",
                                    "marginTop": "6px", "lineHeight": "1.6"}),
                ], style={"padding": "14px 18px", "background": "var(--bg-card)",
                          "border": "1px solid var(--border)",
                          "borderRadius": "8px", "marginBottom": "10px"}),
            ])
            for ag in AGENTS_DATA
        ],

        # ── SHIPPING OPTIMIZATION ──
        section("Shipping Optimization Tips",
                "How to minimize shipping costs at 93 yuan/kg."),
        explainer([
            html.Strong("The #1 rule of rep reselling: "),
            "Shipping cost determines profitability more than purchase price. "
            "A Chrome Hearts ring at 130 yuan costs 4 yuan to ship (3% of cost). "
            "A Jordan 4 at 350 yuan costs 102 yuan to ship (29% of cost). "
            "Optimize your haul mix to include lightweight high-margin items "
            "alongside sneakers to balance overall shipping economics.",
        ], "red"),
        action_box("Shipping Cost Reduction Strategies", SHIPPING_TIPS),

        # ── IMMEDIATE ACTION PLAN ──
        section("Recommended Purchase Plan",
                "What to buy first for maximum ROI and minimum risk."),
        action_box("Immediate Buys — Ship This Week", [
            "Chrome Hearts rings x10-20 — bulk buy, ship together (~1kg total, "
            "93 yuan shipping for the entire batch). Focus on Keeper Ring, "
            "Cemetery Cross, Floral Cross.",
            "Vivienne Westwood Orb Necklaces x10-15 — negligible weight, "
            "TikTok-driven demand among Gen Z. Orb Pearl Choker is the #1 seller.",
            "ERD Graphic Tees x5-10 — lightweight (250g each), enormous retail "
            "gap ($700-1,800 retail vs $22-40 rep). XL sizing most popular.",
            "Designer Swim Trunks x5-10 (LV, Versace, Casablanca) — seasonal "
            "peak is NOW through August. Very lightweight, fold flat.",
            "Goyard Card Holders x5-10 — compact (100g), ships flat, high "
            "perceived value. Verify touching Y's in QC.",
            "Cartier Rimless Sunglasses x5 — 60g each, TikTok-trending, "
            "high markup. Source from ZZZTOPXX on Weidian.",
            "Designer Slides x5 pairs (Gucci/LV/Hermes Oran) — summer demand, "
            "lighter than sneakers. Ship without box.",
        ]),
        action_box("Steady Sellers — Stock Continuously", [
            "Nike Dunk Low Panda — M Batch, 200-290 yuan. Never stops selling. "
            "Drop box, ship 3-5 pairs per haul.",
            "Jordan 4 Black Cat — GX Batch, ~350 yuan. Best value J4 batch. "
            "Perennial bestseller across all demographics.",
            "Dior Saddle Bag — Blue Oblique, $50-75. Consistently top-10 "
            "searched on Weidian. Angel Factory for best quality.",
            "Balenciaga Tees — Cloyad, 120-200 yuan. Lightweight, strong "
            "brand recognition, year-round demand.",
        ]),
        action_box("Avoid These", [
            "Budget batches under 150 yuan for sneakers — quality inconsistency "
            "leads to returns and unhappy customers.",
            "Alloy jewelry (non-925 silver) — customers notice the weight "
            "difference immediately. Only stock 925 sterling silver CH pieces.",
            "Puffer jackets and winter coats right now — wrong season plus "
            "volumetric weight kills margins (1kg actual = 3kg volumetric).",
            "Basetao as shipping agent — inflated shipping reports, slow support.",
            "Pandabuy — permanently shut down since April 2024.",
            "Any items without QC photos — always verify before shipping.",
        ]),

        # ── RESOURCES ──
        section("Key Resources & Links",
                "Community tools for finding, verifying, and purchasing items."),
        explainer([
            html.Strong("JadeShip"), " (jadeship.com) — Live sales tracking, "
            "trending items, agent comparison, shipping calculator. "
            "Use for real-time market data.", html.Br(),
            html.Strong("Weidian Spreadsheet"), " (weidianspreadsheet.org) — "
            "8,500+ verified Weidian finds across 8 categories. "
            "Community-maintained, updated regularly.", html.Br(),
            html.Strong("CNFans Spreadsheet"), " (cnfansspreadsheetss.com) — "
            "Rep shoes guide 2026, buying guides, batch comparisons.", html.Br(),
            html.Strong("doppel.fit"), " — QC photo finder and product discovery. "
            "Browse thousands of QC photos from popular agents.", html.Br(),
            html.Strong("FinderQC"), " (finderqc.com) — 5,000+ curated products "
            "with QC photos, prices in USD. Updated daily.", html.Br(),
            html.Strong("FindQC"), " (findqc.com) — QC photos and video finder "
            "for CNFans, Kakobuy, and other agents.", html.Br(),
            html.Strong("r/RepTime TD List"), " — Trusted Dealer list for watches. "
            "NEVER buy watches from unverified sellers.", html.Br(),
            html.Strong("Grailed"), " (grailed.com) — Legitimate resale market. "
            "Use to verify which brands/items have real demand.", html.Br(),
        ]),

    ], className="page-content")
