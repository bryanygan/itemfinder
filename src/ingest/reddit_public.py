"""Scrape Reddit via public JSON endpoints — no API key required.

Appends .json to Reddit URLs to get structured data. Respects rate limits.
Collects posts + comments from target subreddits within a configurable window.
Supports proxy rotation and bandwidth tracking for large-scale collection.

Usage:
    python -m src.ingest.reddit_public
    python -m src.ingest.reddit_public --subreddits FashionReps DesignerReps
    python -m src.ingest.reddit_public --days 90 --skip-comments
    python -m src.ingest.reddit_public --proxy-file proxies/list1.txt --bandwidth-limit 2.8
    python -m src.ingest.reddit_public --proxy-file proxies/list1.txt --comments-only
"""

import argparse
import http.client
import json
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
_REQUEST_DELAY_PROXY = 0.5  # much faster with proxies (different IPs)
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


# ---------------------------------------------------------------------------
# Proxy pool and bandwidth tracking
# ---------------------------------------------------------------------------
class ProxyPool:
    """Round-robin proxy rotation from a file of host:port:user:pass lines."""

    def __init__(self, path: str | Path):
        self._proxies: list[str] = []
        self._index = 0
        self._lock = threading.Lock()

        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Proxy file not found: {path}")

        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) == 4:
                host, port, user, passwd = parts
                self._proxies.append(f"http://{user}:{passwd}@{host}:{port}")
            elif len(parts) == 2:
                host, port = parts
                self._proxies.append(f"http://{host}:{port}")

        if not self._proxies:
            raise ValueError(f"No valid proxies found in {path}")
        log.info(f"Loaded {len(self._proxies)} proxies from {path}")

    def next(self) -> str:
        """Get next proxy URL (round-robin, thread-safe)."""
        with self._lock:
            proxy = self._proxies[self._index % len(self._proxies)]
            self._index += 1
            return proxy

    def __len__(self) -> int:
        return len(self._proxies)


class BandwidthTracker:
    """Track bytes downloaded, enforce a limit."""

    def __init__(self, limit_gb: float):
        self._limit = int(limit_gb * 1024 * 1024 * 1024)
        self._used = 0
        self._lock = threading.Lock()

    def add(self, nbytes: int):
        with self._lock:
            self._used += nbytes

    @property
    def used_mb(self) -> float:
        return self._used / (1024 * 1024)

    @property
    def remaining_mb(self) -> float:
        return (self._limit - self._used) / (1024 * 1024)

    def has_budget(self) -> bool:
        """True if we haven't exceeded the limit."""
        return self._used < self._limit

    def summary(self) -> str:
        used = self._used / (1024 * 1024)
        limit = self._limit / (1024 * 1024)
        return f"{used:.1f}/{limit:.0f} MB ({used/limit*100:.1f}%)"


# Module-level instances (set by collect_all / main)
_proxy_pool: ProxyPool | None = None
_bw_tracker: BandwidthTracker | None = None


# ---------------------------------------------------------------------------
# Core fetch with proxy + bandwidth support
# ---------------------------------------------------------------------------
def _fetch_json(url: str) -> dict | list | None:
    """Fetch JSON from a Reddit .json endpoint with retries + backoff."""
    global _request_count

    if _bw_tracker and not _bw_tracker.has_budget():
        log.warning(f"  Bandwidth limit reached ({_bw_tracker.summary()}), stopping")
        return None

    delay = _REQUEST_DELAY_PROXY if _proxy_pool else _REQUEST_DELAY
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}

    for attempt in range(_MAX_RETRIES):
        # Build opener with proxy if available
        proxy_url = _proxy_pool.next() if _proxy_pool else None
        if proxy_url:
            proxy_handler = urllib.request.ProxyHandler({
                "http": proxy_url,
                "https": proxy_url,
            })
            opener = urllib.request.build_opener(proxy_handler)
        else:
            opener = urllib.request.build_opener()

        req = urllib.request.Request(url, headers=headers)

        try:
            time.sleep(delay)
            with opener.open(req, timeout=_TIMEOUT) as resp:
                raw_bytes = resp.read()
                raw = raw_bytes.decode("utf-8")
                _request_count += 1

                if _bw_tracker:
                    _bw_tracker.add(len(raw_bytes))

                return json.loads(raw)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                if _proxy_pool:
                    # With proxies, just rotate and retry quickly
                    log.debug(f"  429 on proxy, rotating (attempt {attempt + 1})")
                    time.sleep(1.0)
                else:
                    wait = _RATE_LIMIT_DELAY * _BACKOFF_FACTOR**attempt
                    log.warning(f"  Rate limited (429), waiting {wait:.0f}s...")
                    time.sleep(wait)
            elif e.code in (403, 451):
                if _proxy_pool and attempt < _MAX_RETRIES - 1:
                    # With proxies, 403 might be IP-specific — try another
                    log.debug(f"  403 on proxy, rotating (attempt {attempt + 1})")
                    time.sleep(0.5)
                else:
                    log.warning(f"  Blocked ({e.code}) -- subreddit may be private/quarantined")
                    return None
            elif e.code == 404:
                log.warning(f"  Not found (404): {url}")
                return None
            else:
                log.warning(f"  HTTP {e.code}: {e.reason}")
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(delay * 2)
        except (urllib.error.URLError, TimeoutError, OSError,
                http.client.IncompleteRead, ConnectionResetError) as e:
            log.warning(f"  Network error (attempt {attempt + 1}): {e}")
            if attempt < _MAX_RETRIES - 1:
                time.sleep(delay * _BACKOFF_FACTOR**attempt if not _proxy_pool else 1.0)
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
        if _bw_tracker and not _bw_tracker.has_budget():
            break

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
        1. /new  -- paginate back to cutoff
        2. /top?t=quarter -- high-engagement posts
        3. /hot  -- currently trending
        4. /search -- targeted keyword queries

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

    def _budget_ok():
        return not _bw_tracker or _bw_tracker.has_budget()

    # --- 1. /new (most complete chronological coverage) ---
    log.info(f"  [{subreddit}] Fetching /new (back {days}d)...")
    new_posts = _paginate_listing(
        f"{_BASE_URL}/r/{subreddit}/new.json", cutoff_ts
    )
    _ingest_posts(new_posts)
    log.info(f"  [{subreddit}] /new -> {len(new_posts)} posts")

    # --- 2. /top (high-signal) ---
    if _budget_ok():
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
    if _budget_ok():
        hot_posts = _paginate_listing(
            f"{_BASE_URL}/r/{subreddit}/hot.json", cutoff_ts, max_pages=3
        )
        _ingest_posts(hot_posts)

    # --- 4. Search queries ---
    if _budget_ok():
        for query in REDDIT_SEARCH_QUERIES:
            if not _budget_ok():
                break
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
    if include_comments and comment_candidates and _budget_ok():
        comment_candidates.sort(key=lambda x: x[2] * (1 + x[3]), reverse=True)
        to_fetch = min(len(comment_candidates), max_comment_posts)
        log.info(
            f"  [{subreddit}] Fetching comments for top {to_fetch} "
            f"of {len(comment_candidates)} posts..."
        )

        for i, (pid, op_author, _score, _nc) in enumerate(
            comment_candidates[:to_fetch]
        ):
            if not _budget_ok():
                log.info(f"  [{subreddit}] Bandwidth limit hit at comment {i}/{to_fetch}")
                break

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
                bw_info = f", bw={_bw_tracker.summary()}" if _bw_tracker else ""
                log.info(
                    f"  [{subreddit}] Comments progress: "
                    f"{i + 1}/{to_fetch} posts -> {stats['comments']} comments{bw_info}"
                )

        _flush()
        log.info(f"  [{subreddit}] Comments complete: {stats['comments']} comments")

    stats["total"] = stats["submissions"] + stats["comments"]
    return stats


# ---------------------------------------------------------------------------
# Comments-only collection (highest value per byte)
# ---------------------------------------------------------------------------
def collect_comments_only(conn, *, max_comment_posts: int = _MAX_COMMENTS_PER_SUB) -> int:
    """Fetch comments for existing posts that have no collected comments.

    Queries the DB for posts with num_comments > 0 but no collected comment rows,
    ordered by expected comment count (highest value first).
    """
    # Find subreddits with posts that have uncollected comments
    rows = conn.execute("""
        SELECT rmd.subreddit, rmd.message_id, rmd.num_comments,
               rmd.score as post_score, rm.author
        FROM reddit_metadata rmd
        JOIN raw_messages rm ON rm.id = rmd.message_id
        WHERE rmd.post_type = 'submission'
        AND rmd.num_comments > 0
        AND rmd.message_id NOT IN (
            SELECT DISTINCT rmd2.parent_id FROM reddit_metadata rmd2
            WHERE rmd2.post_type = 'comment' AND rmd2.parent_id IS NOT NULL
        )
        ORDER BY rmd.num_comments DESC
    """).fetchall()

    if not rows:
        log.info("No posts with uncollected comments found")
        return 0

    # Group by subreddit for logging
    sub_counts: dict[str, int] = {}
    for r in rows:
        sub = r["subreddit"]
        sub_counts[sub] = sub_counts.get(sub, 0) + 1

    total_posts = len(rows)
    log.info(
        f"Found {total_posts:,} posts with uncollected comments "
        f"across {len(sub_counts)} subreddits"
    )
    for sub, cnt in sorted(sub_counts.items(), key=lambda x: -x[1]):
        log.info(f"  r/{sub}: {cnt:,} posts")

    raw_batch: list[tuple] = []
    meta_batch: list[tuple] = []
    total_comments = 0
    posts_fetched = 0

    def _flush():
        if raw_batch:
            insert_raw_messages_reddit(conn, list(raw_batch))
            insert_reddit_metadata(conn, list(meta_batch))
            raw_batch.clear()
            meta_batch.clear()

    for r in rows:
        if _bw_tracker and not _bw_tracker.has_budget():
            log.info(f"Bandwidth limit reached ({_bw_tracker.summary()})")
            break

        subreddit = r["subreddit"]
        msg_id = r["message_id"]  # e.g. reddit_t3_abc123
        post_id = msg_id.replace("reddit_t3_", "")
        op_author = r["author"]

        comments = _fetch_post_comments(subreddit, post_id)
        for c in comments:
            c_raw, c_meta = _comment_to_rows(c, subreddit, post_id, op_author)
            if c_raw:
                raw_batch.append(c_raw)
                meta_batch.append(c_meta)
                total_comments += 1

        if len(raw_batch) >= BATCH_SIZE:
            _flush()

        posts_fetched += 1
        if posts_fetched % 50 == 0:
            bw_info = f", bw={_bw_tracker.summary()}" if _bw_tracker else ""
            log.info(
                f"  Comments-only progress: {posts_fetched:,}/{total_posts:,} posts "
                f"-> {total_comments:,} comments{bw_info}"
            )

    _flush()
    log.info(
        f"Comments-only complete: {total_comments:,} comments "
        f"from {posts_fetched:,} posts"
    )
    return total_comments


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
        + (f", proxies={len(_proxy_pool)}" if _proxy_pool else "")
        + (f", bw_limit={_bw_tracker.summary()}" if _bw_tracker else "")
    )

    grand_total = 0
    for i, sub in enumerate(targets, 1):
        if _bw_tracker and not _bw_tracker.has_budget():
            log.info(f"Bandwidth limit reached, stopping at sub {i}/{len(targets)}")
            break

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
            bw_info = f", bw={_bw_tracker.summary()}" if _bw_tracker else ""
            log.info(
                f"  r/{sub} done: {stats['submissions']:,} posts, "
                f"{stats['comments']:,} comments ({elapsed:.0f}s, "
                f"{_request_count} total requests{bw_info})"
            )
            grand_total += stats["total"]
        except Exception as e:
            log.error(f"  Failed r/{sub}: {e}")

    conn.close()
    bw_info = f", bandwidth={_bw_tracker.summary()}" if _bw_tracker else ""
    log.info(
        f"\nCollection complete: {grand_total:,} total messages "
        f"from {len(targets)} subreddits ({_request_count} HTTP requests{bw_info})"
    )
    return grand_total


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main():
    global _proxy_pool, _bw_tracker

    parser = argparse.ArgumentParser(
        description="Collect Reddit data via public JSON endpoints (no API key)"
    )
    parser.add_argument(
        "--subreddits", nargs="+", default=None,
        help="Specific subreddits (default: all targets)",
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
    parser.add_argument(
        "--proxy-file", type=str, default=None,
        help="Path to proxy list file (host:port:user:pass per line)",
    )
    parser.add_argument(
        "--bandwidth-limit", type=float, default=None,
        help="Max bandwidth in GB (e.g., 2.8 for 2.8 GB limit)",
    )
    parser.add_argument(
        "--comments-only", action="store_true",
        help="Only fetch comments for existing posts (skip post collection)",
    )
    args = parser.parse_args()

    # Setup proxy pool
    if args.proxy_file:
        _proxy_pool = ProxyPool(args.proxy_file)

    # Setup bandwidth tracking
    if args.bandwidth_limit:
        _bw_tracker = BandwidthTracker(args.bandwidth_limit)

    if args.comments_only:
        conn = get_connection()
        init_db(conn)
        total = collect_comments_only(conn, max_comment_posts=args.max_comment_posts)
        conn.close()
        bw_info = f" (bandwidth: {_bw_tracker.summary()})" if _bw_tracker else ""
        print(f"\nDone. Collected {total:,} comments{bw_info}.")
        return

    days = 30 if args.quick else args.days
    comments = not args.skip_comments and not args.quick
    max_cp = 50 if args.quick else args.max_comment_posts

    total = collect_all(
        subreddits=args.subreddits,
        days=days,
        include_comments=comments,
        max_comment_posts=max_cp,
    )
    bw_info = f" (bandwidth: {_bw_tracker.summary()})" if _bw_tracker else ""
    print(f"\nDone. Collected {total:,} messages from Reddit{bw_info}.")


if __name__ == "__main__":
    main()
