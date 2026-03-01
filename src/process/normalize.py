"""Text normalization for Discord messages."""

import re

# Compiled patterns for performance
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_MENTION_RE = re.compile(r"<@!?\d+>")
_CHANNEL_RE = re.compile(r"<#\d+>")
_EMOJI_CUSTOM_RE = re.compile(r"<a?:\w+:\d+>")
_MULTI_SPACE_RE = re.compile(r"\s+")
_DISCORD_FORMAT_RE = re.compile(r"~~.*?~~")  # strikethrough
_PRICE_TAG_RE = re.compile(r"\$\d+[\d,.]*\s*(shipped|obo|each|firm)?", re.IGNORECASE)
_SOLD_RE = re.compile(r"\bSOLD\b", re.IGNORECASE)


def normalize_text(text: str) -> str:
    """Clean and normalize a Discord message for analysis."""
    if not text:
        return ""

    t = text

    # Remove strikethrough text (usually sold items in listings)
    t = _DISCORD_FORMAT_RE.sub("", t)

    # Remove URLs
    t = _URL_RE.sub("", t)

    # Remove Discord mentions and channel refs
    t = _MENTION_RE.sub("", t)
    t = _CHANNEL_RE.sub("", t)

    # Remove custom emoji markup
    t = _EMOJI_CUSTOM_RE.sub("", t)

    # Remove price tags (not useful for demand analysis)
    t = _PRICE_TAG_RE.sub("", t)

    # Lowercase
    t = t.lower()

    # Normalize whitespace
    t = _MULTI_SPACE_RE.sub(" ", t).strip()

    return t


def is_spam_or_empty(text: str, min_length: int = 2) -> bool:
    """Check if a message is spam, too short, or non-useful."""
    if not text or len(text) < min_length:
        return True

    # Pure emoji or single character
    if len(text.strip()) <= 1:
        return True

    # Repetitive characters
    if len(set(text.replace(" ", ""))) <= 2 and len(text) > 3:
        return True

    return False


def is_listing(text: str) -> bool:
    """Detect if message is a sales listing (multiple items with prices)."""
    original = text if isinstance(text, str) else ""
    sold_count = len(_SOLD_RE.findall(original))
    price_count = len(_PRICE_TAG_RE.findall(original))
    return (sold_count + price_count) >= 3
