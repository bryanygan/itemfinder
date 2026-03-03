"""Ingest Reddit posts and comments into SQLite via PRAW.

Collects submissions and comments from target rep fashion subreddits.
Uses multiple collection strategies (top/new/hot/search) to maximize coverage.

Usage:
    python -m src.ingest.reddit_ingest
    python -m src.ingest.reddit_ingest --subreddits FashionReps DesignerReps
    python -m src.ingest.reddit_ingest --time-filter year --skip-comments
"""

import argparse
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from src.common.config import (
    BATCH_SIZE,
    REDDIT_COMMENT_LIMIT,
    REDDIT_LISTING_LIMIT,
    REDDIT_SEARCH_QUERIES,
    REDDIT_SORT_METHODS,
    REDDIT_TARGET_SUBREDDITS,
    REDDIT_TIME_FILTERS,
)
from src.common.db import (
    get_connection,
    init_db,
    insert_raw_messages_reddit,
    insert_reddit_metadata,
)
from src.common.log_util import get_logger

log = get_logger("reddit_ingest")

try:
    import praw
    HAS_PRAW = True
except ImportError:
    HAS_PRAW = False
    log.warning("praw not installed – run: pip install praw")


def _get_reddit_client() -> "praw.Reddit":
    """Create authenticated Reddit client from environment variables.

    Required env vars:
        REDDIT_CLIENT_ID     - from https://www.reddit.com/prefs/apps
        REDDIT_CLIENT_SECRET - from app registration
        REDDIT_USER_AGENT    - descriptive string (e.g. "itemfinder/1.0")

    Optional env vars:
        REDDIT_USERNAME      - for higher rate limits (script app)
        REDDIT_PASSWORD      - for script app authentication
    """
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    user_agent = os.environ.get("REDDIT_USER_AGENT", "itemfinder/1.0 demand-intelligence")

    if not client_id or not client_secret:
        raise EnvironmentError(
            "Reddit API credentials not found. Set these environment variables:\n"
            "  REDDIT_CLIENT_ID=your_client_id\n"
            "  REDDIT_CLIENT_SECRET=your_client_secret\n"
            "  REDDIT_USER_AGENT=itemfinder/1.0\n\n"
            "Get credentials at: https://www.reddit.com/prefs/apps\n"
            "Choose 'script' type for personal use."
        )

    username = os.environ.get("REDDIT_USERNAME")
    password = os.environ.get("REDDIT_PASSWORD")

    kwargs = {
        "client_id": client_id,
        "client_secret": client_secret,
        "user_agent": user_agent,
    }
    if username and password:
        kwargs["username"] = username
        kwargs["password"] = password

    reddit = praw.Reddit(**kwargs)
    log.info(f"Reddit client authenticated (read_only={reddit.read_only})")
    return reddit


def _ts_iso(utc_timestamp: float) -> str:
    """Convert Unix timestamp to ISO 8601 string."""
    return datetime.fromtimestamp(utc_timestamp, tz=timezone.utc).isoformat()


def _get_flair(submission) -> str | None:
    """Extract flair text from a submission, normalized to lowercase."""
    flair = submission.link_flair_text
    if flair:
        return flair.strip().lower()
    return None


def _total_awards(submission_or_comment) -> int:
    """Count total awards on a post/comment."""
    try:
        return submission_or_comment.total_awards_received or 0
    except AttributeError:
        return 0


def _author_name(thing) -> str:
    """Safely get author name (deleted users return None)."""
    if thing.author:
        return thing.author.name
    return "[deleted]"


def _author_id(thing) -> str | None:
    """Get author's Reddit ID if available."""
    if thing.author:
        try:
            return thing.author.id
        except Exception:
            return None
    return None


def _author_karma(thing) -> int:
    """Get combined karma for the author."""
    if thing.author:
        try:
            return thing.author.link_karma + thing.author.comment_karma
        except Exception:
            return 0
    return 0


def _submission_to_rows(submission, subreddit_name: str):
    """Convert a Reddit submission to raw_message + metadata row tuples.

    Returns: (raw_message_row, metadata_row)
    """
    # Combine title + selftext for full content
    title = submission.title or ""
    selftext = submission.selftext or ""
    content = f"{title}\n\n{selftext}".strip() if selftext else title.strip()

    if not content:
        return None, None

    msg_id = f"reddit_t3_{submission.id}"
    flair = _get_flair(submission)

    raw_row = (
        msg_id,                                    # id
        subreddit_name.lower(),                    # channel (subreddit)
        flair or "",                               # channel_category (flair)
        "reddit",                                  # guild
        _author_name(submission),                  # author
        _author_id(submission),                    # author_id
        _ts_iso(submission.created_utc),           # timestamp
        content,                                   # content
        "reddit_api",                              # source_file
        1 if submission.url and not submission.is_self else 0,  # has_attachment
        submission.score,                          # reaction_count (upvotes)
    )

    meta_row = (
        msg_id,                                    # message_id
        "submission",                              # post_type
        subreddit_name.lower(),                    # subreddit
        flair,                                     # flair
        submission.score,                          # score
        submission.upvote_ratio,                   # upvote_ratio
        submission.num_comments,                   # num_comments
        _total_awards(submission),                 # awards
        None,                                      # parent_id (submissions have no parent)
        submission.permalink,                      # permalink
        0,                                         # is_op
        _author_karma(submission),                 # author_karma
    )

    return raw_row, meta_row


def _comment_to_rows(comment, subreddit_name: str, submission_id: str,
                     submission_author: str):
    """Convert a Reddit comment to raw_message + metadata row tuples."""
    content = comment.body or ""
    if not content or content == "[deleted]" or content == "[removed]":
        return None, None

    msg_id = f"reddit_t1_{comment.id}"
    is_op = 1 if _author_name(comment) == submission_author else 0

    raw_row = (
        msg_id,
        subreddit_name.lower(),
        "",                                        # no flair on comments
        "reddit",
        _author_name(comment),
        _author_id(comment),
        _ts_iso(comment.created_utc),
        content,
        "reddit_api",
        0,
        comment.score,
    )

    meta_row = (
        msg_id,
        "comment",
        subreddit_name.lower(),
        None,
        comment.score,
        None,                                      # comments don't have upvote_ratio
        0,
        _total_awards(comment),
        f"reddit_t3_{submission_id}",              # parent submission
        comment.permalink if hasattr(comment, "permalink") else None,
        is_op,
        _author_karma(comment),
    )

    return raw_row, meta_row


def _collect_submissions(subreddit, method: str, time_filter: str = "year",
                         limit: int = REDDIT_LISTING_LIMIT):
    """Collect submissions using a specific sort method.

    Args:
        subreddit: PRAW subreddit object
        method: 'top', 'new', 'hot', or 'rising'
        time_filter: 'year', 'month', 'week', 'all' (only for 'top')
        limit: max submissions to fetch
    """
    if method == "top":
        return subreddit.top(time_filter=time_filter, limit=limit)
    elif method == "new":
        return subreddit.new(limit=limit)
    elif method == "hot":
        return subreddit.hot(limit=limit)
    elif method == "rising":
        return subreddit.rising(limit=min(limit, 100))  # rising has fewer results
    else:
        raise ValueError(f"Unknown sort method: {method}")


def _collect_search_results(subreddit, query: str, time_filter: str = "year",
                            limit: int = 250):
    """Search within a subreddit for specific query terms."""
    return subreddit.search(query, sort="relevance", time_filter=time_filter,
                            limit=limit)


def ingest_subreddit(reddit, subreddit_name: str, conn, *,
                     time_filter: str = "year",
                     sort_methods: list[str] | None = None,
                     search_queries: list[str] | None = None,
                     include_comments: bool = True,
                     comment_limit: int = REDDIT_COMMENT_LIMIT) -> dict:
    """Ingest all posts and comments from a single subreddit.

    Returns dict with counts: {submissions, comments, total}
    """
    if sort_methods is None:
        sort_methods = REDDIT_SORT_METHODS
    if search_queries is None:
        search_queries = REDDIT_SEARCH_QUERIES

    subreddit = reddit.subreddit(subreddit_name)
    seen_ids: set[str] = set()
    stats = {"submissions": 0, "comments": 0, "total": 0}

    raw_batch: list[tuple] = []
    meta_batch: list[tuple] = []

    def _flush():
        if raw_batch:
            insert_raw_messages_reddit(conn, raw_batch)
            insert_reddit_metadata(conn, meta_batch)
            raw_batch.clear()
            meta_batch.clear()

    def _process_submission(submission):
        """Process a single submission and optionally its comments."""
        if submission.id in seen_ids:
            return
        seen_ids.add(submission.id)

        raw_row, meta_row = _submission_to_rows(submission, subreddit_name)
        if raw_row is None:
            return

        raw_batch.append(raw_row)
        meta_batch.append(meta_row)
        stats["submissions"] += 1

        if include_comments and submission.num_comments > 0:
            try:
                submission.comments.replace_more(limit=comment_limit)
                sub_author = _author_name(submission)
                for comment in submission.comments.list():
                    c_raw, c_meta = _comment_to_rows(
                        comment, subreddit_name, submission.id, sub_author
                    )
                    if c_raw:
                        raw_batch.append(c_raw)
                        meta_batch.append(c_meta)
                        stats["comments"] += 1
            except Exception as e:
                log.warning(f"  Error expanding comments for {submission.id}: {e}")

        if len(raw_batch) >= BATCH_SIZE:
            _flush()

    # --- Strategy 1: Sorted listings (top/new/hot/rising) ---
    for method in sort_methods:
        log.info(f"  [{subreddit_name}] Collecting {method} posts (time={time_filter})")
        try:
            for submission in _collect_submissions(subreddit, method, time_filter):
                _process_submission(submission)
        except Exception as e:
            log.error(f"  [{subreddit_name}] Error in {method}: {e}")

        log.info(f"  [{subreddit_name}] After {method}: "
                 f"{stats['submissions']} submissions, {stats['comments']} comments")

    # --- Strategy 2: Targeted keyword searches ---
    for query in search_queries:
        log.info(f"  [{subreddit_name}] Searching: '{query}'")
        try:
            for submission in _collect_search_results(subreddit, query, time_filter):
                _process_submission(submission)
        except Exception as e:
            log.error(f"  [{subreddit_name}] Search error for '{query}': {e}")

    _flush()
    stats["total"] = stats["submissions"] + stats["comments"]
    return stats


def ingest_all(subreddits: list[str] | None = None,
               time_filter: str = "year",
               include_comments: bool = True) -> int:
    """Ingest posts and comments from all target subreddits.

    Args:
        subreddits: override list of subreddits (default: REDDIT_TARGET_SUBREDDITS)
        time_filter: 'year', 'month', 'week', 'all'
        include_comments: whether to expand and store comment trees

    Returns:
        Total number of messages inserted
    """
    if not HAS_PRAW:
        log.error("praw is required. Install with: pip install praw")
        return 0

    reddit = _get_reddit_client()
    conn = get_connection()
    init_db(conn)

    targets = subreddits or REDDIT_TARGET_SUBREDDITS
    log.info(f"Starting Reddit ingestion: {len(targets)} subreddits, "
             f"time_filter={time_filter}, comments={include_comments}")

    grand_total = 0
    for i, sub_name in enumerate(targets, 1):
        log.info(f"\n[{i}/{len(targets)}] Ingesting r/{sub_name}")
        start = time.time()

        try:
            stats = ingest_subreddit(
                reddit, sub_name, conn,
                time_filter=time_filter,
                include_comments=include_comments,
            )
            elapsed = time.time() - start
            log.info(
                f"  r/{sub_name} complete: {stats['submissions']:,} submissions, "
                f"{stats['comments']:,} comments ({elapsed:.1f}s)"
            )
            grand_total += stats["total"]
        except Exception as e:
            log.error(f"  Failed to ingest r/{sub_name}: {e}")

    conn.close()
    log.info(f"\nReddit ingestion complete: {grand_total:,} total messages")
    return grand_total


def main():
    parser = argparse.ArgumentParser(description="Ingest Reddit rep fashion data")
    parser.add_argument(
        "--subreddits", nargs="+", default=None,
        help="Specific subreddits to ingest (default: all targets)"
    )
    parser.add_argument(
        "--time-filter", choices=REDDIT_TIME_FILTERS, default="year",
        help="Time period for top posts and searches (default: year)"
    )
    parser.add_argument(
        "--skip-comments", action="store_true",
        help="Skip comment collection (faster, less data)"
    )
    args = parser.parse_args()

    total = ingest_all(
        subreddits=args.subreddits,
        time_filter=args.time_filter,
        include_comments=not args.skip_comments,
    )
    print(f"\nDone. Ingested {total:,} messages from Reddit.")


if __name__ == "__main__":
    main()
