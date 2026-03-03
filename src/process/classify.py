"""Intent classification for Discord and Reddit messages."""

import re

from src.common.config import (
    FLAIR_INTENT_MAP,
    OWNERSHIP_KEYWORDS,
    REDDIT_OWNERSHIP_KEYWORDS,
    REDDIT_REGRET_KEYWORDS,
    REDDIT_REQUEST_KEYWORDS,
    REDDIT_SATISFACTION_KEYWORDS,
    REGRET_KEYWORDS,
    REQUEST_KEYWORDS,
    SATISFACTION_KEYWORDS,
)

# Pre-sort flair keys by length desc so longer keys match first in partial search
_FLAIR_KEYS_SORTED = sorted(FLAIR_INTENT_MAP.keys(), key=len, reverse=True)

# Strip emoji and decorative chars for flair matching
_EMOJI_RE = re.compile(
    r"[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\ufe00-\ufe0f]|[\u200d]",
    re.UNICODE,
)

# Combined keyword lists (Discord + Reddit)
_ALL_REQUEST_KW = REQUEST_KEYWORDS + REDDIT_REQUEST_KEYWORDS
_ALL_SATISFACTION_KW = SATISFACTION_KEYWORDS + REDDIT_SATISFACTION_KEYWORDS
_ALL_REGRET_KW = REGRET_KEYWORDS + REDDIT_REGRET_KEYWORDS
_ALL_OWNERSHIP_KW = OWNERSHIP_KEYWORDS + REDDIT_OWNERSHIP_KEYWORDS


def _keyword_score(text: str, keywords: list[str]) -> float:
    """Return a 0-1 score based on how many keywords match."""
    if not text:
        return 0.0
    matches = sum(1 for kw in keywords if kw in text)
    if matches == 0:
        return 0.0
    # Diminishing returns: first match is worth the most
    return min(1.0, 0.5 + 0.15 * matches)


def classify_intent(text_norm: str) -> tuple[str, float]:
    """Classify a normalized message into an intent type with confidence score.

    Uses combined Discord + Reddit keyword lists for broad coverage.

    Returns:
        (intent_type, intent_score) where intent_type is one of:
        'request', 'satisfaction', 'regret', 'ownership', 'neutral'
        and intent_score is 0.0-1.0
    """
    if not text_norm:
        return "neutral", 0.0

    scores = {
        "request": _keyword_score(text_norm, _ALL_REQUEST_KW),
        "regret": _keyword_score(text_norm, _ALL_REGRET_KW),
        "satisfaction": _keyword_score(text_norm, _ALL_SATISFACTION_KW),
        "ownership": _keyword_score(text_norm, _ALL_OWNERSHIP_KW),
    }

    best_intent = max(scores, key=scores.get)
    best_score = scores[best_intent]

    if best_score < 0.01:
        return "neutral", 0.0

    return best_intent, round(best_score, 3)


def classify_intent_from_channel(channel: str, text_norm: str) -> tuple[str, float]:
    """Use channel context to boost classification accuracy.

    Some channels strongly imply intent (e.g., WTB channel → request).
    """
    intent, score = classify_intent(text_norm)

    channel_lower = channel.lower()

    # WTB/request channels: boost request intent
    if any(tag in channel_lower for tag in ["wtb", "post-requirement"]):
        if intent == "neutral" and len(text_norm) > 5:
            return "request", 0.65
        if intent == "request":
            return "request", min(1.0, score + 0.15)

    # Pickup/WDYWT channels: boost ownership
    if any(tag in channel_lower for tag in ["latest-pickups", "wdywt", "pickups"]):
        if intent == "neutral" and len(text_norm) > 5:
            return "ownership", 0.55
        if intent == "ownership":
            return "ownership", min(1.0, score + 0.1)

    # Vouches: boost satisfaction
    if "vouch" in channel_lower:
        if intent == "neutral" and len(text_norm) > 5:
            return "satisfaction", 0.5
        if intent == "satisfaction":
            return "satisfaction", min(1.0, score + 0.1)

    # QC channels: slight ownership boost
    if any(tag in channel_lower for tag in ["qc", "quality-control"]):
        if intent == "neutral" and len(text_norm) > 5:
            return "ownership", 0.4

    return intent, score


def _clean_flair(flair: str) -> str:
    """Strip emoji, parens, brackets, and extra whitespace from flair text."""
    cleaned = _EMOJI_RE.sub("", flair)
    # Remove common decorative wrappers: (QC), [W2C], etc.
    cleaned = re.sub(r"[(){}\[\]]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def _match_flair(flair_clean: str) -> tuple[str, float] | None:
    """Try to match a cleaned flair against the FLAIR_INTENT_MAP.

    Returns (intent, score) or None.
    """
    # 1. Exact match on cleaned flair
    if flair_clean in FLAIR_INTENT_MAP:
        return FLAIR_INTENT_MAP[flair_clean]

    # 2. Split on common delimiters and try exact match on each segment
    segments = re.split(r"[/|,\-–—]+", flair_clean)
    for seg in segments:
        seg = seg.strip()
        if seg in FLAIR_INTENT_MAP:
            return FLAIR_INTENT_MAP[seg]

    # 3. Partial match — sorted longest-first to avoid short-key false positives
    for flair_key in _FLAIR_KEYS_SORTED:
        if flair_key in flair_clean:
            return FLAIR_INTENT_MAP[flair_key]

    return None


def classify_intent_from_flair(flair: str | None, text_norm: str) -> tuple[str, float]:
    """Use Reddit post flair to boost classification accuracy.

    Flair is the strongest intent signal on Reddit rep communities — post flairs
    like W2C, QC, REVIEW, HAUL directly indicate what the user is doing.

    Handles real-world flair formats including:
        - Emoji-decorated: "🎧in hand pics", "🌅qc", "🚩w2c"
        - Parenthesized: "(QC) Quality Check", "💯 qc request 💯"
        - Compound: "qc/lc", "review | help"
    """
    intent, score = classify_intent(text_norm)

    if not flair:
        return intent, score

    flair_clean = _clean_flair(flair)
    match = _match_flair(flair_clean)

    if match is None:
        return intent, score

    flair_intent, flair_score = match

    # Flair overrides keyword classification if stronger
    if flair_score > score:
        return flair_intent, flair_score
    # If same intent, boost the score
    if flair_intent == intent:
        return intent, min(1.0, score + 0.15)
    return flair_intent, flair_score
