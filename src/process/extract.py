"""Entity extraction: brand, item, variant from normalized text."""

import re

from src.common.config import (
    BRAND_ALIASES_SORTED,
    COLORS,
    ITEM_TYPES,
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


def extract_all(text: str) -> dict:
    """Extract brand, item, and variant from text.

    Returns dict with keys: brand, item, variant
    """
    return {
        "brand": extract_brand(text),
        "item": extract_item(text),
        "variant": extract_variant(text),
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
