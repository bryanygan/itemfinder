"""Scrape Reddit via public JSON endpoints — no API key required.

Appends .json to Reddit URLs to get structured data. Respects rate limits.
Collects posts + comments from target subreddits within a configurable window.

Usage:
    python -m src.ingest.reddit_public
    python -m src.ingest.reddit_public --subreddits FashionReps DesignerReps
    python -m src.ingest.reddit_public --days 90 --skip-comments
"""

import argparse
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from src.common.config import (
    BATCH_SIZE,
    REDDIT_SEARCH_QUERIES,
    REDDIT_TARGET_SUBREDDITS,
)
from src.common.db import (
    get_connection,
    init_db,
    insert_raw_messages_reddit,
    insert_reddit_metadata,
)
from src.common.log_util import get_logger

log = get_logger("reddit_public")

# ---------------------------------------------------------------------------
# HTTP / rate-limit settings
# ---------------------------------------------------------------------------
_USER_AGENT = "itemfinder:demand-intel:v1.0 (research bot)"
_BASE_URL = "https://www.reddit.com"
_REQUEST_DELAY = 4.0  # seconds between requests (respectful for unauthenticated)
_RATE_LIMIT_DELAY = 30.0  # extra wait on 429 (generous to clear rate limits)
_MAX_RETRIES = 6
_BACKOFF_FACTOR = 2.0
_TIMEOUT = 30

_ITEMS_PER_PAGE = 100
_MAX_PAGES_LISTING = 10  # Reddit caps listings at ~1000 items
_MAX_PAGES_SEARCH = 5
_COMMENT_DEPTH = 5
_COMMENT_LIMIT = 200
_MAX_COMMENTS_PER_SUB = 500  # max posts to fetch comments for per subreddit

_SSL_CTX = ssl.create_default_context()

# Track request count for logging
_request_count = 0


def _fetch_json(url: str) -> dict | list | None:
    """Fetch JSON from a Reddit .json endpoint with retries + backoff."""
    global _request_count
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
    req = urllib.request.Request(url, headers=headers)

    for attempt in range(_MAX_RETRIES):
        try:
            time.sleep(_REQUEST_DELAY)
            with urllib.request.urlopen(req, context=_SSL_CTX, timeout=_TIMEOUT) as resp:
                raw = resp.read().decode("utf-8")
                _request_count += 1
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = _RATE_LIMIT_DELAY * _BACKOFF_FACTOR**attempt
                log.warning(f"  Rate limited (429), waiting {wait:.0f}s...")
                time.sleep(wait)
            elif e.code in (403, 451):
                log.warning(f"  Blocked ({e.code}) — subreddit may be private/quarantined")
                return None
            elif e.code == 404:
                log.warning(f"  Not found (404): {url}")
                return None
            else:
                log.warning(f"  HTTP {e.code}: {e.reason}")
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_REQUEST_DELAY * 2)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            log.warning(f"  Network error (attempt {attempt + 1}): {e}")
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_REQUEST_DELAY * _BACKOFF_FACTOR**attempt)
        except json.JSONDecodeError:
            log.warning(f"  Invalid JSON from {url}")
            return None

    log.error(f"  Failed after {_MAX_RETRIES} retries: {url}")
    return None


# ---------------------------------------------------------------------------
# Timestamp helper
# ---------------------------------------------------------------------------
def _ts_iso(utc_ts: float) -> str:
    return datetime.fromtimestamp(utc_ts, tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------
def _paginate_listing(
    base_url: str, cutoff_ts: float, max_pages: int = _MAX_PAGES_LISTING
) -> list[dict]:
    """Walk through a Reddit listing, collecting posts until cutoff or exhaustion."""
    posts: list[dict] = []
    after: str | None = None

    for _page in range(max_pages):
        url = base_url
        parts = [f"limit={_ITEMS_PER_PAGE}", "raw_json=1"]
        if after:
            parts.append(f"after={after}")
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{'&'.join(parts)}"

        data = _fetch_json(url)
        if not data or not isinstance(data, dict) or "data" not in data:
            break

        children = data["data"].get("children", [])
        if not children:
            break

        hit_cutoff = False
        for child in children:
            if child.get("kind") != "t3":
                continue
            post = child.get("data", {})
            if post.get("created_utc", 0) < cutoff_ts:
                hit_cutoff = True
                break
            posts.append(post)

        if hit_cutoff:
            break
        after = data["data"].get("after")
        if not after:
            break

    return posts


# ---------------------------------------------------------------------------
# Comment tree flattening
# ---------------------------------------------------------------------------
def _flatten_comments(
    node: dict | list, depth: int = 0, max_depth: int = _COMMENT_DEPTH
) -> list[dict]:
    """Recursively extract comments from Reddit's nested JSON structure."""
    comments: list[dict] = []
    if depth > max_depth:
        return comments

    if isinstance(node, list):
        for item in node:
            comments.extend(_flatten_comments(item, depth, max_depth))
        return comments

    kind = node.get("kind")
    if kind == "Listing":
        for child in node.get("data", {}).get("children", []):
            comments.extend(_flatten_comments(child, depth, max_depth))
    elif kind == "t1":
        d = node.get("data", {})
        body = d.get("body", "")
        if body and body not in ("[deleted]", "[removed]"):
            comments.append(d)
        replies = d.get("replies")
        if replies and isinstance(replies, dict):
            comments.extend(_flatten_comments(replies, depth + 1, max_depth))

    return comments


def _fetch_post_comments(subreddit: str, post_id: str) -> list[dict]:
    """Fetch the comment tree for a single post."""
    url = (
        f"{_BASE_URL}/r/{subreddit}/comments/{post_id}.json"
        f"?limit={_COMMENT_LIMIT}&depth={_COMMENT_DEPTH}&sort=top&raw_json=1"
    )
    data = _fetch_json(url)
    if not data or not isinstance(data, list) or len(data) < 2:
        return []
    return _flatten_comments(data[1])


# ---------------------------------------------------------------------------
# Row conversion (maps to existing DB schema)
# ---------------------------------------------------------------------------
def _post_to_rows(post: dict, subreddit: str):
    """Convert a Reddit post JSON -> (raw_row, meta_row) for DB insertion."""
    title = post.get("title", "")
    selftext = post.get("selftext", "")
    content = f"{title}\n\n{selftext}".strip() if selftext else title.strip()

    pid = post.get("id", "")
    if not pid or not content:
        return None, None

    msg_id = f"reddit_t3_{pid}"
    flair = (post.get("link_flair_text") or "").strip().lower() or None

    raw_row = (
        msg_id,
        subreddit.lower(),
        flair or "",
        "reddit",
        post.get("author", "[deleted]"),
        post.get("author_fullname"),
        _ts_iso(post.get("created_utc", 0)),
        content,
        "reddit_public",
        0 if post.get("is_self", True) else 1,
        post.get("score", 0),
    )

    meta_row = (
        msg_id,
        "submission",
        subreddit.lower(),
        flair,
        post.get("score", 0),
        post.get("upvote_ratio"),
        post.get("num_comments", 0),
        post.get("total_awards_received", 0),
        None,
        post.get("permalink", ""),
        0,
        0,  # author_karma not available without user endpoint
    )

    return raw_row, meta_row


def _comment_to_rows(comment: dict, subreddit: str, sub_id: str, op_author: str):
    """Convert a Reddit comment JSON -> (raw_row, meta_row)."""
    body = comment.get("body", "")
    cid = comment.get("id", "")
    if not cid or not body or body in ("[deleted]", "[removed]"):
        return None, None

    msg_id = f"reddit_t1_{cid}"
    author = comment.get("author", "[deleted]")

    raw_row = (
        msg_id,
        subreddit.lower(),
        "",
        "reddit",
        author,
        comment.get("author_fullname"),
        _ts_iso(comment.get("created_utc", 0)),
        body,
        "reddit_public",
        0,
        comment.get("score", 0),
    )

    meta_row = (
        msg_id,
        "comment",
        subreddit.lower(),
        None,
        comment.get("score", 0),
        None,
        0,
        comment.get("total_awards_received", 0),
        f"reddit_t3_{sub_id}",
        comment.get("permalink", ""),
        1 if author == op_author else 0,
        0,
    )

    return raw_row, meta_row


# ---------------------------------------------------------------------------
# Main collection logic
# ---------------------------------------------------------------------------
def collect_subreddit(
    subreddit: str,
    conn,
    *,
    days: int = 90,
    include_comments: bool = True,
    min_score_for_comments: int = 2,
    min_comments_for_fetch: int = 1,
    max_comment_posts: int = _MAX_COMMENTS_PER_SUB,
) -> dict:
    """Collect posts and comments from one subreddit.

    Strategies:
        1. /new  — paginate back to cutoff
        2. /top?t=quarter — high-engagement posts
        3. /hot  — currently trending
        4. /search — targeted keyword queries

    Returns: {submissions, comments, total}
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_ts = cutoff.timestamp()
    time_param = "quarter" if days <= 100 else ("year" if days <= 400 else "all")

    seen_ids: set[str] = set()
    comment_candidates: list[tuple[str, str, int, int]] = []  # pid, author, score, nc
    stats = {"submissions": 0, "comments": 0, "total": 0}

    raw_batch: list[tuple] = []
    meta_batch: list[tuple] = []

    def _flush():
        if raw_batch:
            insert_raw_messages_reddit(conn, list(raw_batch))
            insert_reddit_metadata(conn, list(meta_batch))
            raw_batch.clear()
            meta_batch.clear()

    def _ingest_posts(posts: list[dict]):
        for post in posts:
            pid = post.get("id", "")
            if not pid or pid in seen_ids:
                continue
            seen_ids.add(pid)

            raw_row, meta_row = _post_to_rows(post, subreddit)
            if raw_row is None:
                continue

            raw_batch.append(raw_row)
            meta_batch.append(meta_row)
            stats["submissions"] += 1

            score = post.get("score", 0)
            nc = post.get("num_comments", 0)
            if score >= min_score_for_comments and nc >= min_comments_for_fetch:
                comment_candidates.append(
                    (pid, post.get("author", "[deleted]"), score, nc)
                )

            if len(raw_batch) >= BATCH_SIZE:
                _flush()

    # --- 1. /new (most complete chronological coverage) ---
    log.info(f"  [{subreddit}] Fetching /new (back {days}d)...")
    new_posts = _paginate_listing(
        f"{_BASE_URL}/r/{subreddit}/new.json", cutoff_ts
    )
    _ingest_posts(new_posts)
    log.info(f"  [{subreddit}] /new -> {len(new_posts)} posts")

    # --- 2. /top (high-signal) ---
    log.info(f"  [{subreddit}] Fetching /top?t={time_param}...")
    top_posts = _paginate_listing(
        f"{_BASE_URL}/r/{subreddit}/top.json?t={time_param}", cutoff_ts
    )
    before = stats["submissions"]
    _ingest_posts(top_posts)
    log.info(
        f"  [{subreddit}] /top -> {len(top_posts)} posts "
        f"(+{stats['submissions'] - before} new)"
    )

    # --- 3. /hot (trending) ---
    hot_posts = _paginate_listing(
        f"{_BASE_URL}/r/{subreddit}/hot.json", cutoff_ts, max_pages=3
    )
    _ingest_posts(hot_posts)

    # --- 4. Search queries ---
    for query in REDDIT_SEARCH_QUERIES:
        encoded = urllib.parse.quote_plus(query)
        search_url = (
            f"{_BASE_URL}/r/{subreddit}/search.json"
            f"?q={encoded}&restrict_sr=1&sort=new&t={time_param}"
        )
        search_posts = _paginate_listing(search_url, cutoff_ts, max_pages=_MAX_PAGES_SEARCH)
        _ingest_posts(search_posts)

    _flush()
    log.info(f"  [{subreddit}] Posts complete: {stats['submissions']} unique submissions")

    # --- 5. Comments for high-engagement posts ---
    if include_comments and comment_candidates:
        comment_candidates.sort(key=lambda x: x[2] * (1 + x[3]), reverse=True)
        to_fetch = min(len(comment_candidates), max_comment_posts)
        log.info(
            f"  [{subreddit}] Fetching comments for top {to_fetch} "
            f"of {len(comment_candidates)} posts..."
        )

        for i, (pid, op_author, _score, _nc) in enumerate(
            comment_candidates[:to_fetch]
        ):
            comments = _fetch_post_comments(subreddit, pid)
            for c in comments:
                c_raw, c_meta = _comment_to_rows(c, subreddit, pid, op_author)
                if c_raw:
                    raw_batch.append(c_raw)
                    meta_batch.append(c_meta)
                    stats["comments"] += 1

            if len(raw_batch) >= BATCH_SIZE:
                _flush()

            if (i + 1) % 25 == 0:
                log.info(
                    f"  [{subreddit}] Comments progress: "
                    f"{i + 1}/{to_fetch} posts -> {stats['comments']} comments"
                )

        _flush()
        log.info(f"  [{subreddit}] Comments complete: {stats['comments']} comments")

    stats["total"] = stats["submissions"] + stats["comments"]
    return stats


def collect_all(
    subreddits: list[str] | None = None,
    *,
    days: int = 90,
    include_comments: bool = True,
    max_comment_posts: int = _MAX_COMMENTS_PER_SUB,
) -> int:
    """Collect data from all target subreddits and store in the database.

    Returns total messages collected.
    """
    global _request_count
    _request_count = 0

    conn = get_connection()
    init_db(conn)

    targets = subreddits or REDDIT_TARGET_SUBREDDITS
    log.info(
        f"Starting public Reddit collection: {len(targets)} subreddits, "
        f"{days}-day window, comments={'yes' if include_comments else 'no'}"
    )

    grand_total = 0
    for i, sub in enumerate(targets, 1):
        log.info(f"\n[{i}/{len(targets)}] r/{sub}")
        start = time.time()

        try:
            stats = collect_subreddit(
                sub,
                conn,
                days=days,
                include_comments=include_comments,
                max_comment_posts=max_comment_posts,
            )
            elapsed = time.time() - start
            log.info(
                f"  r/{sub} done: {stats['submissions']:,} posts, "
                f"{stats['comments']:,} comments ({elapsed:.0f}s, "
                f"{_request_count} total requests)"
            )
            grand_total += stats["total"]
        except Exception as e:
            log.error(f"  Failed r/{sub}: {e}")

    conn.close()
    log.info(
        f"\nCollection complete: {grand_total:,} total messages "
        f"from {len(targets)} subreddits ({_request_count} HTTP requests)"
    )
    return grand_total


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Collect Reddit data via public JSON endpoints (no API key)"
    )
    parser.add_argument(
        "--subreddits", nargs="+", default=None,
        help="Specific subreddits (default: all 15 targets)",
    )
    parser.add_argument(
        "--days", type=int, default=90,
        help="How many days back to collect (default: 90)",
    )
    parser.add_argument(
        "--skip-comments", action="store_true",
        help="Skip comment collection (much faster)",
    )
    parser.add_argument(
        "--max-comment-posts", type=int, default=_MAX_COMMENTS_PER_SUB,
        help=f"Max posts to fetch comments for per sub (default: {_MAX_COMMENTS_PER_SUB})",
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Quick mode: 30 days, no comments, reduced search",
    )
    args = parser.parse_args()

    days = 30 if args.quick else args.days
    comments = not args.skip_comments and not args.quick
    max_cp = 50 if args.quick else args.max_comment_posts

    total = collect_all(
        subreddits=args.subreddits,
        days=days,
        include_comments=comments,
        max_comment_posts=max_cp,
    )
    print(f"\nDone. Collected {total:,} messages from Reddit (public endpoints).")


if __name__ == "__main__":
    main()
