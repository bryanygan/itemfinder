"""Central configuration for the demand intelligence system."""

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = ROOT_DIR / "data" / "app.db"
OUT_DIR = ROOT_DIR / "out"

DATA_DIRS = [
    Path(r"C:\Users\prinp\Downloads\ZRServerBackup"),
    Path(r"C:\Users\prinp\Downloads\ZRBSTBackup"),
]

BATCH_SIZE = 1000

# ---------------------------------------------------------------------------
# Channel relevance weights — higher = more signal for item/brand analysis
# ---------------------------------------------------------------------------
CHANNEL_WEIGHTS = {
    "wtb": 1.5,
    "post-requirement": 1.5,
    "latest-pickups": 1.3,
    "wdywt": 1.2,
    "general": 1.0,
    "customer-chat": 1.1,
    "vouches": 1.1,
    "wts-vouches": 1.0,
    "quality-control": 1.0,
    "previous-qcs": 1.0,
    "zr-picks": 1.2,
    "clothes": 1.2,
    "shoes": 1.2,
    "boxless-shoes": 1.2,
    "watches": 1.2,
    "curated-by-mav": 1.2,
    "discounted-stuff": 1.1,
}
DEFAULT_CHANNEL_WEIGHT = 0.3

# ---------------------------------------------------------------------------
# Brand alias dictionary  (alias → canonical name)
# ---------------------------------------------------------------------------
BRAND_ALIASES: dict[str, str] = {
    # Luxury / Designer
    "lv": "Louis Vuitton", "louis vuitton": "Louis Vuitton", "vuitton": "Louis Vuitton",
    "vutton": "Louis Vuitton", "louie": "Louis Vuitton",
    "gucci": "Gucci", "gc": "Gucci",
    "prada": "Prada",
    "balenciaga": "Balenciaga", "bale": "Balenciaga", "balenci": "Balenciaga",
    "dior": "Dior", "christian dior": "Dior",
    "givenchy": "Givenchy",
    "bottega veneta": "Bottega Veneta", "bottega": "Bottega Veneta", "bv": "Bottega Veneta",
    "hermes": "Hermès", "hermès": "Hermès",
    "celine": "Celine", "céline": "Celine",
    "saint laurent": "Saint Laurent", "ysl": "Saint Laurent", "sl": "Saint Laurent",
    "amiri": "Amiri",
    "off-white": "Off-White", "off white": "Off-White", "ow": "Off-White",
    "chrome hearts": "Chrome Hearts", "ch": "Chrome Hearts",
    "vivienne westwood": "Vivienne Westwood", "vivienne": "Vivienne Westwood", "vw": "Vivienne Westwood",
    "rick owens": "Rick Owens", "rick": "Rick Owens",
    "maison margiela": "Maison Margiela", "margiela": "Maison Margiela", "mm": "Maison Margiela",
    "gats": "Maison Margiela",
    "goyard": "Goyard",
    "versace": "Versace",
    "fendi": "Fendi",
    "burberry": "Burberry",
    "alexander mcqueen": "Alexander McQueen", "mcqueen": "Alexander McQueen",
    "valentino": "Valentino",
    "loewe": "Loewe",
    "tom ford": "Tom Ford",
    "jacquemus": "Jacquemus",

    # Streetwear
    "supreme": "Supreme",
    "stussy": "Stüssy", "stüssy": "Stüssy",
    "bape": "BAPE", "a bathing ape": "BAPE",
    "palace": "Palace",
    "corteiz": "Corteiz", "crtz": "Corteiz",
    "gallery dept": "Gallery Dept", "gallery": "Gallery Dept", "gd": "Gallery Dept",
    "gallery dept.": "Gallery Dept",
    "sp5der": "Sp5der", "spider": "Sp5der", "spyder": "Sp5der",
    "represent": "Represent",
    "essentials": "Fear of God Essentials", "fog": "Fear of God Essentials",
    "fear of god": "Fear of God Essentials",
    "palm angels": "Palm Angels", "pa": "Palm Angels",
    "rhude": "Rhude",
    "human made": "Human Made",
    "kith": "Kith",
    "trapstar": "Trapstar",
    "eric emanuel": "Eric Emanuel", "ee": "Eric Emanuel",
    "hellstar": "Hellstar",
    "broken planet": "Broken Planet",
    "cpfm": "Cactus Plant Flea Market", "cactus plant flea market": "Cactus Plant Flea Market",
    "vlone": "VLONE",
    "just don": "Just Don",
    "sicko": "Sicko",
    "revenge": "Revenge",
    "cav empt": "Cav Empt", "c.e": "Cav Empt",

    # Sportswear / Sneakers
    "nike": "Nike",
    "jordan": "Jordan", "aj": "Jordan", "air jordan": "Jordan",
    "adidas": "Adidas",
    "yeezy": "Yeezy",
    "new balance": "New Balance", "nb": "New Balance",
    "asics": "ASICS",
    "puma": "Puma",
    "travis scott": "Travis Scott", "ts": "Travis Scott",
    "dunk": "Nike Dunk", "dunks": "Nike Dunk",

    # Outerwear / Premium
    "carhartt": "Carhartt WIP", "carhartt wip": "Carhartt WIP",
    "a cold wall": "A-Cold-Wall*", "acw": "A-Cold-Wall*",
    "acne studios": "Acne Studios", "acne": "Acne Studios",
    "stone island": "Stone Island", "si": "Stone Island", "stoney": "Stone Island",
    "moncler": "Moncler",
    "canada goose": "Canada Goose", "cg": "Canada Goose",
    "the north face": "The North Face", "tnf": "The North Face", "north face": "The North Face",
    "arc'teryx": "Arc'teryx", "arcteryx": "Arc'teryx",

    # Watches / Accessories
    "rolex": "Rolex",
    "omega": "Omega",
    "cartier": "Cartier",
    "ap": "Audemars Piguet", "audemars piguet": "Audemars Piguet",
    "patek philippe": "Patek Philippe", "patek": "Patek Philippe",
    "richard mille": "Richard Mille", "rm": "Richard Mille",

    # Other
    "kanye": "Kanye West", "kanye west": "Kanye West", "ye": "Kanye West",
    "travis": "Travis Scott",
    "murakami": "Takashi Murakami",
}

# Sorted by length desc so longer aliases match first
BRAND_ALIASES_SORTED = sorted(BRAND_ALIASES.items(), key=lambda x: len(x[0]), reverse=True)

# ---------------------------------------------------------------------------
# Item-type keywords
# ---------------------------------------------------------------------------
ITEM_TYPES = [
    "hoodie", "hoodies", "pullover",
    "tee", "tees", "t-shirt", "t-shirts", "shirt", "shirts",
    "shorts", "short",
    "pants", "trousers", "joggers", "sweatpants", "trackpants",
    "jacket", "jackets", "puffer", "windbreaker", "bomber",
    "sweater", "sweaters", "crewneck", "sweatshirt",
    "shoes", "sneakers", "kicks",
    "bag", "bags", "backpack", "tote", "side bag", "messenger", "duffel",
    "hat", "hats", "cap", "caps", "beanie", "beanies", "bucket hat",
    "ring", "rings", "necklace", "necklaces", "bracelet", "bracelets",
    "chain", "chains", "pendant", "pendants",
    "watch", "watches",
    "belt", "belts",
    "sunglasses", "glasses", "shades",
    "wallet", "wallets",
    "socks",
    "slides", "sandals",
    "pillow",
    "keychain",
]

# ---------------------------------------------------------------------------
# Intent classification keywords  (keyword → (intent_type, base_score))
# ---------------------------------------------------------------------------
REQUEST_KEYWORDS = [
    "looking for", "anyone got", "anyone have", "who has", "who got",
    "need", "w2c", "wtb", "want to buy", "want to cop",
    "link?", "link pls", "send link", "where can i",
    "where to get", "where to find", "where to cop",
    "can someone find", "does anyone sell", "iso",
    "in search of", "searching for", "tryna find", "tryna cop",
    "tryna get", "wanna cop", "wanna get", "looking to buy",
    "dm me if you have", "dm if you got",
]

SATISFACTION_KEYWORDS = [
    "fire", "so good", "worth it", "love it", "love these", "love this",
    "amazing", "incredible", "10/10", "best", "perfect",
    "happy with", "glad i got", "no regrets", "insane quality",
    "heat", "grail", "must have", "must cop", "goated",
    "clean af", "crazy good", "beautiful", "gorgeous",
    "exceeded expectations", "blown away",
]

REGRET_KEYWORDS = [
    "should've bought", "should have bought", "shouldve bought",
    "should've copped", "should have copped", "shouldve copped",
    "missed out", "wish i got", "wish i bought", "wish i copped",
    "regret not", "regret not buying", "regret not copping",
    "sold out before", "too late", "slept on",
    "why didn't i", "why didnt i", "kicking myself",
    "should've gotten", "should have gotten",
    "can't believe i didn't", "cant believe i didnt",
]

OWNERSHIP_KEYWORDS = [
    "just got", "just copped", "just picked up", "just arrived",
    "picked up", "copped", "in hand", "arrived",
    "my pair", "my new", "added to collection",
    "finally got", "came in today", "came in the mail",
    "got mine", "mine came", "wearing", "rocking",
    "got these", "got this", "have this", "have these",
    "i own", "i have",
]

# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------
INTENT_WEIGHTS = {
    "request": 0.8,
    "regret": 1.0,
    "satisfaction": 0.6,
    "ownership": 0.4,
    "neutral": 0.1,
}

FINAL_SCORE_WEIGHTS = {
    "intent": 0.5,
    "velocity": 0.3,
    "volume": 0.2,
}

TREND_WINDOW_DAYS = 7

# ---------------------------------------------------------------------------
# Reddit configuration
# ---------------------------------------------------------------------------
REDDIT_TARGET_SUBREDDITS = [
    # Core fashion rep communities (highest signal)
    "FashionReps",
    "DesignerReps",
    "FashionRepsBST",
    "QualityReps",
    "RepFashion",
    "LuxuryReps",
    # Sneaker rep communities
    "Repsneakers",
    "sneakerreps",
    "repbudgetsneakers",
    "TheWorldOfRepsneakers",
    # Niche / size-specific
    "BigBoiRepFashion",
    "CloseToRetail",
    "BudgetBatch",
    "weidianwarriors",
    # Budget / marketplace
    "DHgate",
    # Shipping agents (secondary signal)
    "Sugargoo",
    "Superbuy",
    "cssbuy",
    "MulebuyCommunity",
    "AllChinabuy",
    "Acbuyofficial",
]

# Subreddit relevance weights — mirrors CHANNEL_WEIGHTS logic
SUBREDDIT_WEIGHTS: dict[str, float] = {
    "fashionreps": 1.5,
    "designerreps": 1.5,
    "fashionrepsbst": 1.4,  # buy/sell/trade = strong intent
    "qualityreps": 1.5,     # high-quality rep discussion
    "repsneakers": 1.5,     # 969K subs, massive sneaker community
    "sneakerreps": 1.4,     # 311K subs, sneaker reps
    "repfashion": 1.3,      # general rep fashion
    "luxuryreps": 1.3,      # luxury-focused
    "dhgate": 1.2,          # budget finds, strong demand signals
    "repbudgetsneakers": 1.3,
    "bigboirepfashion": 1.3,  # size-specific demand
    "closetoretail": 1.3,    # quality-focused demand
    "budgetbatch": 1.2,
    "theworldofrepsneakers": 1.2,
    "weidianwarriors": 1.1,  # finds-focused
    "sugargoo": 0.9,         # agent discussion (some demand signal)
    "superbuy": 0.9,
    "cssbuy": 0.9,
    "mulebuycommunity": 0.9,
    "allchinabuy": 0.9,
    "acbuyofficial": 0.9,
}
DEFAULT_SUBREDDIT_WEIGHT = 0.5

# Reddit post flair → intent mapping (strongest signal source on Reddit)
# Research: flairs are standardized across rep subs and are the #1 intent signal
FLAIR_INTENT_MAP: dict[str, tuple[str, float]] = {
    # Request flairs — user is looking for something
    "w2c": ("request", 0.90),
    "wtc": ("request", 0.90),
    "wtb": ("request", 0.90),   # BST: want to buy
    "find": ("request", 0.85),
    "looking for": ("request", 0.85),
    "iso": ("request", 0.85),
    "interest check": ("request", 0.75),
    "ic": ("request", 0.75),    # interest check abbreviation
    "lc": ("request", 0.60),    # legit check = considering purchase
    "legit check": ("request", 0.60),
    "pc": ("request", 0.55),    # price check = considering purchase

    # Ownership flairs — user already purchased
    "qc": ("ownership", 0.85),
    "quality check": ("ownership", 0.85),
    "in hand": ("ownership", 0.90),
    "in-hand": ("ownership", 0.90),
    "haul": ("ownership", 0.85),
    "shipping": ("ownership", 0.70),
    "arrived": ("ownership", 0.90),
    "pickup": ("ownership", 0.85),
    "wdywt": ("ownership", 0.80),
    "gp": ("ownership", 0.80),  # guinea pig = first buyer testing batch

    # Satisfaction flairs — positive experience
    "review": ("satisfaction", 0.80),
    "positive review": ("satisfaction", 0.90),
    "top tier": ("satisfaction", 0.85),
    "retail comparison": ("satisfaction", 0.80),

    # Sale/Trade flairs — user owns and is selling (strong ownership signal)
    "wts": ("ownership", 0.85),   # want to sell
    "fs": ("ownership", 0.85),    # for sale
    "ft": ("ownership", 0.70),    # for trade
    "wtt": ("ownership", 0.70),   # want to trade

    # Informational (lower weight but still useful)
    "guide": ("neutral", 0.20),
    "news": ("neutral", 0.15),
    "discussion": ("neutral", 0.30),
    "question": ("neutral", 0.25),
    "meme": ("neutral", 0.05),
    "shitpost": ("neutral", 0.05),
    "meta": ("neutral", 0.10),
    "mod post": ("neutral", 0.05),
}

# ---------------------------------------------------------------------------
# Batch names — factory batch identifiers (key entity on Reddit rep subs)
# Research: batch names are critical for understanding quality expectations
# ---------------------------------------------------------------------------
BATCH_NAMES: dict[str, str] = {
    # Top tier batches
    "ljr": "LJR", "ljr batch": "LJR",
    "pk": "PK", "pk batch": "PK", "pk basf": "PK", "pk 4.0": "PK",
    "og batch": "OG", "og": "OG",
    "gd batch": "GD", "gd": "GD",
    "god batch": "God",
    # Mid tier batches
    "hp batch": "HP", "hp": "HP",
    "m batch": "M", "m batch": "M",
    "fk batch": "FK", "fk": "FK",
    "vt batch": "VT", "vt": "VT",
    "gt batch": "GT",
    "gp batch": "GP Batch",
    "ln5": "LN5", "ln5 batch": "LN5",
    "h12": "H12", "h12 batch": "H12",
    "x batch": "X",
    "s2 batch": "S2",
    "top dreamer": "Top Dreamer",
    "cz batch": "CZ",
    # Budget batches
    "qy batch": "QY", "qy": "QY",
    "dt batch": "DT", "dt": "DT",
    "st batch": "ST",
    "dg batch": "DG",
    "get batch": "GET",
    "wtg": "WTG",  # Wood Table Guy (budget seller)
    "csj": "CSJ",
    "passerby": "Passerby",
    "cappuccino": "Cappuccino",
    "a1 top": "A1 Top",
}
BATCH_NAMES_SORTED = sorted(BATCH_NAMES.items(), key=lambda x: len(x[0]), reverse=True)

# Agent/middleman services (for context extraction, not scoring)
AGENT_NAMES = [
    "pandabuy", "sugargoo", "superbuy", "cssbuy", "css buy",
    "wegobuy", "mulebuy", "allchinabuy", "acbuy",
    "cnfans", "hoobuy", "kakobuy", "joyabuy", "oopbuy",
    "basetao", "ytaopal", "hagobuy", "ezbuycn",
]

# Seller platforms (for link/context detection)
SELLER_PLATFORMS = ["weidian", "taobao", "1688", "yupoo", "tmall"]

# Reddit-specific intent keywords (supplement existing keywords)
# Research: gathered from actual community language patterns across 15+ subs
REDDIT_REQUEST_KEYWORDS = [
    "w2c", "wtc", "wtb", "where to cop", "best batch",
    "who has the best", "best seller for",
    "anyone gp'd", "anyone gp", "has anyone tried",
    "budget batch", "looking for a good",
    "any good", "best version of", "closest to retail",
    "best rep of", "top tier",
    "recommend a seller", "recommend seller",
    "pandabuy link", "weidian link", "taobao link",
    "agent link", "link please", "drop the link",
    "which batch", "which seller", "which agent",
    "any reps of", "anyone know where",
    "does anyone have a link", "need a link",
    "best for the price", "bang for buck",
    "tts?", "true to size?", "how does it fit",
    "size up or down", "what size should i get",
    "is this batch good", "is this seller good",
    "better batch", "worth the upgrade",
]

REDDIT_SATISFACTION_KEYWORDS = [
    "gl", "green light", "looks good", "easy gl",
    "big gl", "fat gl", "instant gl", "auto gl",
    "retail comparison", "retail vs", "passed as retail",
    "uncalloutable", "not calloutable", "on feet no one can tell",
    "top tier batch", "god tier",
    "worth every penny", "steal for the price",
    "budget king", "goat seller", "best seller",
    "insane for the price", "crazy for the price",
    "better than expected", "pleasantly surprised",
    "daily wear", "beaters", "love these",
    "suede is alive", "materials are great", "quality is insane",
    "compliments", "got compliments",
    "no flaws", "flawless", "can't complain",
]

REDDIT_REGRET_KEYWORDS = [
    "rl", "red light", "calloutable", "easy callout",
    "instant callout", "anyone can tell",
    "oos", "out of stock", "sold out",
    "discontinued", "batch flaw",
    "waste of money", "not worth it", "not worth the hype",
    "should have gone with", "went with wrong batch",
    "overpaid", "underpaid for quality",
    "returning", "refund", "dispute",
    "bait and switch", "b&s",
    "dead link", "dl", "link dead",
    "cobblestone boost", "wrong color", "wrong size",
    "seized", "got seized", "customs seized",
    "stitching is off", "shape is off", "color is off",
    "glue stains", "loose threads",
    "don't buy from", "avoid this seller",
]

REDDIT_OWNERSHIP_KEYWORDS = [
    "haul review", "my haul", "haul arrived",
    "in hand pics", "in hand photos", "in hand review",
    "just shipped", "just arrived",
    "gp review", "gp'd this", "guinea pig",
    "warehouse pics", "warehouse photos",
    "shipped with", "used agent",
    "on feet", "on foot", "fit pic", "fit pics",
    "unboxing", "just unboxed",
    "day 1 wear", "first wear", "worn for",
    "my collection", "added to the rotation",
    "shipped via", "ems", "sal", "arrived in",
    "declared at", "split haul",
    "vacuum sealed", "rehearsal shipping",
]

# Time periods for Reddit data collection
REDDIT_TIME_FILTERS = ["year", "month", "week", "all"]

# Sort methods to maximize post coverage per subreddit
REDDIT_SORT_METHODS = ["top", "new", "hot", "rising"]

# Max items per API listing (Reddit hard limit is ~1000)
REDDIT_LISTING_LIMIT = 1000

# Max comments to expand per submission (0 = expand all)
REDDIT_COMMENT_LIMIT = 0

# Search queries to run per subreddit for targeted intent signals
REDDIT_SEARCH_QUERIES = [
    "w2c",
    "looking for",
    "best batch",
    "haul review",
    "in hand",
    "regret",
    "missed out",
    "slept on",
    "restock",
    "out of stock",
    "GL",
    "RL",
    "budget",
    "top tier",
]

# ---------------------------------------------------------------------------
# Channels to skip entirely (non-item discussion)
# ---------------------------------------------------------------------------
SKIP_CHANNELS = {
    "food-channel", "workout", "rules", "welcome-and-rules",
    "about-us", "roles", "extra-roles", "read-me",
    "moderator-only", "admin-set-up", "staff-chat",
    "server-locked", "beef-channel", "text-channel",
    "vouches-notification", "introduction",
    "what-to-do-for-digital-arbitrage", "mav-buyback-guarantee",
}

# Sizes for variant extraction
# Extended for BigBoiRepFashion (US 15-16, EU 48-50, 6XL+)
SIZES = [
    "xxs", "xs", "s", "m", "l", "xl", "xxl", "xxxl",
    "2xl", "3xl", "4xl", "5xl", "6xl",
    "us 4", "us 4.5", "us 5", "us 5.5", "us 6", "us 6.5",
    "us 7", "us 7.5", "us 8", "us 8.5", "us 9", "us 9.5",
    "us 10", "us 10.5", "us 11", "us 11.5", "us 12", "us 12.5",
    "us 13", "us 14", "us 15", "us 16",
    "size 4", "size 5", "size 6", "size 7", "size 8", "size 9",
    "size 10", "size 11", "size 12", "size 13", "size 14",
    "size 15", "size 16",
    "eu 36", "eu 37", "eu 38", "eu 39", "eu 40", "eu 41",
    "eu 42", "eu 43", "eu 44", "eu 45", "eu 46", "eu 47",
    "eu 48", "eu 49", "eu 50",
]

# Colorways — includes sneaker-specific colorway names used on Reddit
COLORS = [
    "black", "white", "red", "blue", "green", "yellow", "pink",
    "purple", "orange", "grey", "gray", "brown", "cream", "beige",
    "navy", "olive", "teal", "maroon", "burgundy", "gold", "silver",
    "baby blue", "sky blue", "royal blue", "matcha", "matcha green",
    "mocha", "sail", "bone", "ivory", "sand", "slate",
    # Jordan/Nike colorways
    "bred", "chicago", "unc", "obsidian", "shadow",
    "oreo", "zebra", "beluga", "sesame", "butter",
    "university blue", "midnight navy", "cool grey",
    "fire red", "infrared", "cement", "military black",
    "panda", "reverse panda", "photon dust",
    "dark mocha", "light smoke grey", "hyper royal",
    "black cat", "thunder", "lightning", "playoff",
    "taxi", "cherry", "lucky green", "pine green",
    "travis scott", "ts", "reverse mocha",
    "off white", "off-white",
    "georgetown", "michigan", "kentucky", "syracuse", "st johns",
    "chlorophyll", "medium curry", "argon",
    # Yeezy colorways
    "slate", "bone", "onyx", "granite", "salt",
    "mx oat", "mx rock", "sand taupe",
    # New Balance colorways
    "sea salt", "rain cloud", "grey day",
    "protection pack", "jjjjound",
]
