"""Intent classification for Discord messages."""

from src.common.config import (
    OWNERSHIP_KEYWORDS,
    REGRET_KEYWORDS,
    REQUEST_KEYWORDS,
    SATISFACTION_KEYWORDS,
)


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

    Returns:
        (intent_type, intent_score) where intent_type is one of:
        'request', 'satisfaction', 'regret', 'ownership', 'neutral'
        and intent_score is 0.0-1.0
    """
    if not text_norm:
        return "neutral", 0.0

    scores = {
        "request": _keyword_score(text_norm, REQUEST_KEYWORDS),
        "regret": _keyword_score(text_norm, REGRET_KEYWORDS),
        "satisfaction": _keyword_score(text_norm, SATISFACTION_KEYWORDS),
        "ownership": _keyword_score(text_norm, OWNERSHIP_KEYWORDS),
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
