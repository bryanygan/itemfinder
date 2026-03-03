"""Runner script for Reddit data ingestion + processing pipeline.

Automatically uses the public JSON scraper (no API key needed).
Falls back to PRAW if Reddit API credentials are set in environment.

Usage:
    # Full pipeline: ingest from Reddit then process all data
    python scripts/run_reddit.py

    # Ingest only (skip processing)
    python scripts/run_reddit.py --ingest-only

    # Process only (if data already ingested)
    python scripts/run_reddit.py --process-only

    # Specific subreddits
    python scripts/run_reddit.py --subreddits FashionReps DesignerReps

    # Quick mode (30 days, no comments)
    python scripts/run_reddit.py --quick

    # Control comment collection
    python scripts/run_reddit.py --days 90 --max-comment-posts 200

Optional environment variables (enables PRAW mode for higher throughput):
    REDDIT_CLIENT_ID=your_client_id
    REDDIT_CLIENT_SECRET=your_client_secret
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.common.log_util import get_logger

log = get_logger("run_reddit")


def _has_api_credentials() -> bool:
    return bool(os.environ.get("REDDIT_CLIENT_ID") and os.environ.get("REDDIT_CLIENT_SECRET"))


def main():
    parser = argparse.ArgumentParser(description="Reddit ingestion + processing pipeline")
    parser.add_argument("--subreddits", nargs="+", default=None,
                        help="Specific subreddits to ingest")
    parser.add_argument("--days", type=int, default=90,
                        help="Days of history to collect (default: 90)")
    parser.add_argument("--skip-comments", action="store_true",
                        help="Skip comment collection")
    parser.add_argument("--max-comment-posts", type=int, default=500,
                        help="Max posts per sub to fetch comments for (default: 500)")
    parser.add_argument("--ingest-only", action="store_true",
                        help="Only ingest, don't run processing pipeline")
    parser.add_argument("--process-only", action="store_true",
                        help="Only process, don't ingest (use existing data)")
    parser.add_argument("--quick", action="store_true",
                        help="Quick mode: 30 days, no comments")
    parser.add_argument("--force-public", action="store_true",
                        help="Force public JSON scraper even if API credentials exist")
    args = parser.parse_args()

    if not args.process_only:
        use_praw = _has_api_credentials() and not args.force_public

        if use_praw:
            log.info("=== Phase 1: Reddit Ingestion (PRAW — API key detected) ===")
            from src.ingest.reddit_ingest import ingest_all

            time_filter = "month" if args.quick else ("quarter" if args.days <= 100 else "year")
            include_comments = not args.skip_comments and not args.quick

            total = ingest_all(
                subreddits=args.subreddits,
                time_filter=time_filter,
                include_comments=include_comments,
            )
        else:
            log.info("=== Phase 1: Reddit Ingestion (Public JSON — no API key) ===")
            from src.ingest.reddit_public import collect_all

            days = 30 if args.quick else args.days
            include_comments = not args.skip_comments and not args.quick
            max_cp = 50 if args.quick else args.max_comment_posts

            total = collect_all(
                subreddits=args.subreddits,
                days=days,
                include_comments=include_comments,
                max_comment_posts=max_cp,
            )

        log.info(f"Ingestion complete: {total:,} messages from Reddit")

    if not args.ingest_only:
        log.info("\n=== Phase 2: Processing Pipeline ===")
        from src.process.pipeline import run_pipeline

        mentions = run_pipeline()
        log.info(f"Processing complete: {mentions:,} mentions extracted")

    log.info("\nDone! Run the dashboard to see results:")
    log.info("  python -m src.dashboard.app")


if __name__ == "__main__":
    main()
