"""Refresh the Subreddit Deep Dive "hot threads" cache.

Hits https://www.reddit.com/r/<sub>/hot.json for each tracked subreddit and
writes the results to data/live_hot_cache.json. The dashboard reads that
cache to render the "Hot on r/<sub> right now" panel without making any
network calls during page render.

Usage:
    python scripts/refresh_live_hot.py
    python scripts/refresh_live_hot.py --subreddits FashionReps Repsneakers
    python scripts/refresh_live_hot.py --limit 25 --sleep 0.5
    python scripts/refresh_live_hot.py --status
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.analytics.live_reddit_hot import (
    cache_status, refresh_hot_cache,
)
from src.common.log_util import get_logger

log = get_logger("refresh_live_hot")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--subreddits", nargs="+", default=None,
                   help="Specific subreddits (default: all tracked)")
    p.add_argument("--limit", type=int, default=15,
                   help="Max posts per subreddit (default: 15)")
    p.add_argument("--sleep", type=float, default=1.5,
                   help="Seconds to sleep between subreddit fetches")
    p.add_argument("--status", action="store_true",
                   help="Print current cache status and exit")
    args = p.parse_args()

    if args.status:
        print(json.dumps(cache_status(), indent=2))
        return 0

    summary = refresh_hot_cache(
        subreddits=args.subreddits,
        limit=args.limit,
        sleep_between=args.sleep,
    )
    total = sum(summary.values())
    log.info("Refresh complete: %d posts across %d subreddits",
             total, len(summary))
    for sub, n in sorted(summary.items(), key=lambda x: -x[1]):
        log.info("  r/%s: %d", sub, n)
    return 0 if total else 1


if __name__ == "__main__":
    sys.exit(main())
