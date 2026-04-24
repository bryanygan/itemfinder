"""Live Reddit "hot posts" feed with on-disk cache.

Hits the public https://www.reddit.com/r/<sub>/hot.json endpoint to fetch the
current hot threads for a subreddit, extracts the fields useful for demand
intelligence (title, flair, upvotes, comments, permalink, timestamp), and
caches the result to data/live_hot_cache.json so dashboard renders don't
wait on network I/O.

Used by the Subreddit Deep Dive tab to show "What's hot on r/<sub> right
now" alongside the internal DB analysis. Degrades gracefully: if no cache
exists and network fetch fails, the UI simply shows an empty state with
instructions to run scripts/refresh_live_hot.py.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from src.common.config import REDDIT_TARGET_SUBREDDITS, ROOT_DIR
from src.common.log_util import get_logger

log = get_logger("live_reddit_hot")

CACHE_PATH: Path = ROOT_DIR / "data" / "live_hot_cache.json"
_USER_AGENT = "python:itemfinder-live-hot:1.0 (+subreddit-deep-dive)"
_DEFAULT_TIMEOUT = 8.0
_DEFAULT_LIMIT = 15
_DEFAULT_TTL_HOURS = 6


def _hot_url(subreddit: str, limit: int) -> str:
    safe = subreddit.strip().strip("/").lstrip("r/")
    return f"https://www.reddit.com/r/{safe}/hot.json?limit={int(limit)}"


def _parse_post(raw: dict) -> dict:
    """Extract the fields we care about from a Reddit post object."""
    d = raw.get("data", {})
    created = d.get("created_utc") or 0
    selftext = d.get("selftext") or ""
    snippet = selftext[:240].replace("\n", " ").strip()
    return {
        "id": d.get("id", ""),
        "title": d.get("title", "").strip(),
        "author": d.get("author", ""),
        "flair": d.get("link_flair_text") or "",
        "score": int(d.get("score") or 0),
        "upvote_ratio": float(d.get("upvote_ratio") or 0.0),
        "num_comments": int(d.get("num_comments") or 0),
        "permalink": "https://www.reddit.com" + (d.get("permalink") or ""),
        "url": d.get("url", ""),
        "created_iso": datetime.fromtimestamp(
            created, tz=timezone.utc
        ).isoformat() if created else "",
        "is_self": bool(d.get("is_self")),
        "stickied": bool(d.get("stickied")),
        "over_18": bool(d.get("over_18")),
        "snippet": snippet,
    }


def fetch_hot_threads(subreddit: str, limit: int = _DEFAULT_LIMIT,
                      timeout: float = _DEFAULT_TIMEOUT) -> list[dict]:
    """Fetch the current hot threads for a subreddit. Returns [] on failure."""
    url = _hot_url(subreddit, limit)
    req = urllib.request.Request(
        url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
        payload = json.loads(raw)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
            OSError, json.JSONDecodeError) as e:
        log.warning("fetch_hot_threads(%s) failed: %s", subreddit, e)
        return []

    children = (payload or {}).get("data", {}).get("children", []) or []
    posts = []
    for c in children:
        try:
            p = _parse_post(c)
        except Exception as e:  # defensive — malformed entries shouldn't kill the run
            log.debug("skip malformed post: %s", e)
            continue
        if p["stickied"] or p["over_18"]:
            continue
        posts.append(p)
    return posts


# ── Cache I/O ────────────────────────────────────────────────────────────

def _empty_cache() -> dict:
    return {"fetched_at": None, "subreddits": {}}


def _load_cache(path: Path = CACHE_PATH) -> dict:
    if not path.exists():
        return _empty_cache()
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "subreddits" not in data:
            return _empty_cache()
        return data
    except (OSError, json.JSONDecodeError) as e:
        log.warning("cache read failed (%s) — returning empty", e)
        return _empty_cache()


def _save_cache(cache: dict, path: Path = CACHE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, sort_keys=True)
    tmp.replace(path)


def get_cached_hot(subreddit: str, path: Path = CACHE_PATH) -> dict:
    """Return {posts: [...], fetched_at: iso, stale: bool} for a subreddit."""
    cache = _load_cache(path)
    sub_entry = cache.get("subreddits", {}).get(subreddit) or {}
    fetched_at = sub_entry.get("fetched_at") or cache.get("fetched_at")
    posts = sub_entry.get("posts") or []
    stale = _is_stale(fetched_at)
    return {
        "subreddit": subreddit,
        "posts": posts,
        "fetched_at": fetched_at,
        "stale": stale,
        "count": len(posts),
    }


def _is_stale(fetched_at: str | None, ttl_hours: int = _DEFAULT_TTL_HOURS) -> bool:
    if not fetched_at:
        return True
    try:
        ts = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600.0
    return age_h > ttl_hours


def refresh_hot_cache(subreddits: list[str] | None = None,
                      limit: int = _DEFAULT_LIMIT,
                      path: Path = CACHE_PATH,
                      sleep_between: float = 1.5) -> dict:
    """Fetch hot threads for each subreddit and write the cache.
    Returns a summary of counts per subreddit."""
    subs = subreddits or list(REDDIT_TARGET_SUBREDDITS)
    cache = _load_cache(path)
    cache["subreddits"] = cache.get("subreddits", {})

    summary: dict[str, int] = {}
    for i, s in enumerate(subs):
        if i > 0 and sleep_between > 0:
            time.sleep(sleep_between)
        posts = fetch_hot_threads(s, limit=limit)
        cache["subreddits"][s] = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "posts": posts,
        }
        summary[s] = len(posts)
        log.info("r/%s: cached %d hot threads", s, len(posts))

    cache["fetched_at"] = datetime.now(timezone.utc).isoformat()
    _save_cache(cache, path)
    return summary


def cache_status(path: Path = CACHE_PATH) -> dict:
    cache = _load_cache(path)
    subs = cache.get("subreddits", {}) or {}
    return {
        "fetched_at": cache.get("fetched_at"),
        "stale": _is_stale(cache.get("fetched_at")),
        "subreddit_count": len(subs),
        "total_posts": sum(len(v.get("posts") or []) for v in subs.values()),
        "subreddits": {k: len(v.get("posts") or []) for k, v in subs.items()},
        "path": str(path),
    }
