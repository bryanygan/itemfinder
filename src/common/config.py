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
SIZES = [
    "xxs", "xs", "s", "m", "l", "xl", "xxl", "xxxl",
    "2xl", "3xl", "4xl", "5xl",
    "us 4", "us 5", "us 6", "us 7", "us 8", "us 9",
    "us 10", "us 11", "us 12", "us 13", "us 14",
    "size 4", "size 5", "size 6", "size 7", "size 8", "size 9",
    "size 10", "size 11", "size 12", "size 13", "size 14",
    "eu 36", "eu 37", "eu 38", "eu 39", "eu 40", "eu 41",
    "eu 42", "eu 43", "eu 44", "eu 45", "eu 46", "eu 47",
]

COLORS = [
    "black", "white", "red", "blue", "green", "yellow", "pink",
    "purple", "orange", "grey", "gray", "brown", "cream", "beige",
    "navy", "olive", "teal", "maroon", "burgundy", "gold", "silver",
    "baby blue", "sky blue", "royal blue", "matcha", "matcha green",
    "mocha", "sail", "bone", "ivory", "sand", "slate",
    "bred", "chicago", "unc", "obsidian", "shadow",
    "oreo", "zebra", "beluga", "sesame", "butter",
    "university blue", "midnight navy", "cool grey",
    "fire red", "infrared", "cement", "military black",
]
