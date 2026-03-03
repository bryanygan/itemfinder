"""Entity extraction: brand, item, variant, batch from normalized text."""

import re

from src.common.config import (
    AGENT_NAMES,
    BATCH_NAMES_SORTED,
    BRAND_ALIASES_SORTED,
    COLORS,
    ITEM_TYPES,
    SELLER_PLATFORMS,
    SIZES,
)

# ---------------------------------------------------------------------------
# Canonical item normalization (plural → singular, etc.)
# ---------------------------------------------------------------------------
ITEM_CANONICAL = {
    "hoodies": "hoodie", "pullover": "hoodie",
    "tees": "tee", "t-shirt": "tee", "t-shirts": "tee", "shirts": "shirt",
    "shorts": "shorts",
    "trousers": "pants", "joggers": "pants", "sweatpants": "pants", "trackpants": "pants",
    "jackets": "jacket", "puffer": "jacket", "windbreaker": "jacket", "bomber": "jacket",
    "sweaters": "sweater", "crewneck": "sweater", "sweatshirt": "sweater",
    "sneakers": "shoes", "kicks": "shoes",
    "bags": "bag", "tote": "bag", "side bag": "bag", "messenger": "bag", "duffel": "bag",
    "hats": "hat", "caps": "cap", "beanies": "beanie",
    "rings": "ring", "necklaces": "necklace", "bracelets": "bracelet",
    "chains": "chain", "pendants": "pendant",
    "watches": "watch",
    "belts": "belt",
    "glasses": "sunglasses", "shades": "sunglasses",
    "wallets": "wallet",
    "sandals": "slides",
}

# Items that need word-boundary matching to avoid false positives
# (these appear as substrings in common English words)
_ITEMS_NEEDING_BOUNDARY = {
    "hat", "hats", "cap", "caps", "ring", "rings", "chain", "chains",
    "short", "shorts", "belt", "belts", "slides",
    "socks", "pendant", "pendants", "shirt", "shirts",
    "bag", "bags", "tee", "tees", "watch",
}

# Pre-compile item regex patterns — use word boundaries for all items
_ITEM_REGEXES: list[tuple[re.Pattern, str]] = []
for _item in sorted(ITEM_TYPES, key=len, reverse=True):
    _canonical = ITEM_CANONICAL.get(_item, _item)
    _ITEM_REGEXES.append((
        re.compile(rf"\b{re.escape(_item)}\b", re.IGNORECASE),
        _canonical,
    ))

# Pre-compile size and color patterns
_SIZE_PATTERNS = sorted(SIZES, key=len, reverse=True)
_COLOR_PATTERNS = sorted(COLORS, key=len, reverse=True)

# Shoe size pattern: "size 13", "sz 13", "US13", "EU 44"
_SHOE_SIZE_RE = re.compile(
    r"\b(?:size|sz|us|eu)\s*(\d{1,2}(?:\.\d)?)\b", re.IGNORECASE
)

# Letter size pattern: "size L", "sz M", standalone "XL"
_LETTER_SIZE_RE = re.compile(
    r"\b(?:size|sz)\s*(xxs|xs|s|m|l|xl|xxl|xxxl|2xl|3xl)\b", re.IGNORECASE
)


def extract_brand(text: str) -> str | None:
    """Extract the most likely brand from normalized text."""
    if not text:
        return None

    for alias, canonical in BRAND_ALIASES_SORTED:
        # Use word boundary matching for short aliases to avoid false positives
        if len(alias) <= 2:
            if re.search(rf"\b{re.escape(alias)}\b", text):
                return canonical
        else:
            if alias in text:
                return canonical

    return None


def extract_item(text: str) -> str | None:
    """Extract item type from normalized text using word-boundary matching."""
    if not text:
        return None

    for pattern, canonical in _ITEM_REGEXES:
        if pattern.search(text):
            return canonical

    return None


def extract_variant(text: str) -> str | None:
    """Extract variant info (color + size) from normalized text."""
    if not text:
        return None

    parts = []

    # Extract color
    for color in _COLOR_PATTERNS:
        if color in text:
            parts.append(color)
            break  # take first (longest) match

    # Extract size
    m = _SHOE_SIZE_RE.search(text)
    if m:
        parts.append(f"size {m.group(1)}")
    else:
        m = _LETTER_SIZE_RE.search(text)
        if m:
            parts.append(f"size {m.group(1).upper()}")
        else:
            # Check for standalone size words
            for sz in ["xxl", "xxxl", "2xl", "3xl", "xl", "xs", "xxs"]:
                if re.search(rf"\b{sz}\b", text, re.IGNORECASE):
                    parts.append(f"size {sz.upper()}")
                    break

    return " / ".join(parts) if parts else None


def extract_batch(text: str) -> str | None:
    """Extract factory batch name from text (Reddit-specific entity).

    Batch names like LJR, PK, M batch, HP are critical quality identifiers
    in rep communities. They indicate which factory made the item.
    """
    if not text:
        return None

    for alias, canonical in BATCH_NAMES_SORTED:
        if len(alias) <= 2:
            # Short batch names need word boundaries to avoid false positives
            if re.search(rf"\b{re.escape(alias)}\b", text):
                return canonical
        else:
            if alias in text:
                return canonical

    return None


def extract_agent(text: str) -> str | None:
    """Extract shopping agent name from text."""
    if not text:
        return None
    for agent in AGENT_NAMES:
        if agent in text:
            return agent
    return None


def extract_seller_platform(text: str) -> str | None:
    """Extract seller platform (weidian, taobao, 1688, yupoo) from text."""
    if not text:
        return None
    for platform in SELLER_PLATFORMS:
        if platform in text:
            return platform
    return None


# Reddit title bracket pattern: [QC], [W2C], [FIND], [REVIEW], etc.
_TITLE_BRACKET_RE = re.compile(r"\[([^\]]+)\]")


def extract_from_reddit_title(title: str) -> dict:
    """Parse structured Reddit post titles for entities.

    Reddit rep community titles follow patterns like:
        [QC] Nike Dunk Low Panda - LJR Batch - from Pandabuy
        [W2C] Best batch Chrome Hearts hoodie size L
        [FIND] ¥199 - Jordan 4 Military Black - WTG Store
        [HAUL] 10kg haul to US - Jordan, Nike, Chrome Hearts

    Returns dict with: flair_tag, brand, item, variant, batch, agent
    """
    if not title:
        return {}

    result = {}
    title_lower = title.lower()

    # Extract bracket tags (often duplicate the flair)
    brackets = _TITLE_BRACKET_RE.findall(title)
    if brackets:
        result["flair_tag"] = brackets[0].lower().strip()

    # Standard extraction on the full title
    result["brand"] = extract_brand(title_lower)
    result["item"] = extract_item(title_lower)
    result["variant"] = extract_variant(title_lower)
    result["batch"] = extract_batch(title_lower)
    result["agent"] = extract_agent(title_lower)
    result["platform"] = extract_seller_platform(title_lower)

    return result


def extract_all(text: str) -> dict:
    """Extract brand, item, variant, and batch from text.

    Returns dict with keys: brand, item, variant, batch
    """
    return {
        "brand": extract_brand(text),
        "item": extract_item(text),
        "variant": extract_variant(text),
        "batch": extract_batch(text),
    }


def extract_items_from_listing(text: str) -> list[dict]:
    """Extract multiple items from a sales listing.

    Listings typically have one item per line with brand + item + size + price.
    """
    results = []
    lines = text.split("\n")
    for line in lines:
        line = line.strip().lower()
        if not line or len(line) < 5:
            continue
        entities = extract_all(line)
        if entities["brand"] or entities["item"]:
            results.append(entities)
    return results
