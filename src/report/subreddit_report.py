"""Markdown report exporter for the Subreddit Deep Dive.

Produces a shopping-list-style markdown report per subreddit combining:
  - community KPIs
  - top items and fastest-rising items
  - flair signal distribution
  - ranked purchase recommendations (with weidian/yupoo links where available)
  - cross-subreddit "safe bets"
  - live hot threads (if the local cache exists)

Usage:
    python -m src.report.subreddit_report                         # all tracked subs
    python -m src.report.subreddit_report --subreddits FashionReps Repsneakers
    python -m src.report.subreddit_report --since 2026-04-01

Output lands in out/subreddit_reports/<subreddit>.md.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

from src.analytics.live_reddit_hot import get_cached_hot
from src.analytics.subreddit_deep_dive import (
    available_subreddits,
    best_items_across_subreddits,
    get_tracked_subreddits,
    subreddit_flair_signals,
    subreddit_kpis,
    subreddit_purchase_recommendations,
    subreddit_rising_items,
    subreddit_top_items,
)
from src.common.config import OUT_DIR
from src.common.db import get_connection
from src.common.log_util import get_logger

log = get_logger("subreddit_report")

REPORT_DIR = OUT_DIR / "subreddit_reports"


def _md_table(rows: list[dict], cols: list[tuple[str, str]]) -> str:
    """Build a simple pipe-delimited Markdown table.

    cols is a list of (key, header) pairs. Missing keys render as '—'.
    """
    if not rows:
        return "_No data._\n"
    header = "| " + " | ".join(h for _, h in cols) + " |"
    sep = "|" + "|".join("---" for _ in cols) + "|"
    lines = [header, sep]
    for r in rows:
        cells = []
        for key, _ in cols:
            v = r.get(key)
            if v is None or v == "":
                cells.append("—")
            elif isinstance(v, float):
                cells.append(f"{v:.2f}")
            else:
                cells.append(str(v).replace("|", "\\|").replace("\n", " "))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def _fmt_link(url: str) -> str:
    if not url:
        return "—"
    short = url.replace("https://", "").replace("http://", "")
    if len(short) > 60:
        short = short[:57] + "..."
    return f"[{short}]({url})"


def build_subreddit_report(conn, subreddit: str,
                           since: str | None = None) -> str:
    """Assemble the markdown report for one subreddit."""
    kpis = subreddit_kpis(conn, subreddit, since=since)
    top = subreddit_top_items(conn, subreddit, limit=15, since=since)
    rising = subreddit_rising_items(conn, subreddit, top_n=10, since=since)
    flairs = subreddit_flair_signals(conn, subreddit, since=since)
    recs = subreddit_purchase_recommendations(conn, subreddit,
                                              since=since, limit=20)
    cross = best_items_across_subreddits(conn, top_n=15, since=since)
    hot = get_cached_hot(subreddit)

    # Linkify purchase_link columns for Markdown
    for r in recs:
        r["purchase_link_md"] = _fmt_link(r.get("purchase_link", ""))
    for r in cross:
        r["purchase_link_md"] = _fmt_link(r.get("purchase_link", ""))

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    header = [
        f"# Subreddit Deep Dive — r/{subreddit}",
        "",
        f"_Generated {now}_",
        "",
        f"- **Signal Weight:** `{kpis.get('signal_weight', 0):.2f}x`",
        f"- **Posts with Mentions:** {kpis.get('posts') or 0}",
        f"- **Product Mentions:** {kpis.get('mentions') or 0}",
        f"- **Unique Brands:** {kpis.get('brands') or 0}",
        f"- **Buy Requests:** {kpis.get('requests') or 0}",
        f"- **Regret Mentions:** {kpis.get('regret') or 0}",
        f"- **Ownership Mentions:** {kpis.get('owned') or 0}",
        f"- **Average Intent Score:** {kpis.get('avg_score', 0):.2f}",
        "",
    ]
    if since:
        header.insert(3, f"_Window: since {since}_")
        header.insert(4, "")

    sections = ["\n".join(header)]

    # Purchase Recommendations
    sections.append("## Top Buy Recommendations\n")
    sections.append(
        "Ranked by a blend of this sub's weighted demand, external Reddit "
        "trend score, and Weidian live-sales data.\n"
    )
    sections.append(_md_table(recs, [
        ("brand", "Brand"), ("item", "Item"),
        ("combined_score", "Score"), ("recommendation", "Action"),
        ("best_batch", "Best Batch"), ("price_range", "Price"),
        ("mentions", "Mentions"), ("requests", "Req"),
        ("regret", "Regret"), ("owned", "Own"),
        ("weidian_trend", "Weidian"), ("units_sold_30d", "Units/30d"),
        ("purchase_link_md", "Purchase Link"),
    ]))

    # Top items
    sections.append("## Most Mentioned Items\n")
    sections.append(_md_table(top, [
        ("brand", "Brand"), ("item", "Item"),
        ("mentions", "Mentions"), ("requests", "Requests"),
        ("satisfied", "Satisfaction"), ("regret", "Regret"),
        ("owned", "Owned"), ("avg_score", "Intent"),
    ]))

    # Rising items
    sections.append("## Fastest Rising Items\n")
    if rising:
        sections.append(
            "_Velocity = (recent mentions − prior period) / prior period._\n"
        )
    sections.append(_md_table(rising, [
        ("brand", "Brand"), ("item", "Item"),
        ("recent_mentions", "Recent"), ("prev_mentions", "Prior"),
        ("velocity", "Velocity"),
    ]))

    # Flair signals
    sections.append("## Flair Distribution\n")
    sections.append(
        "The strongest intent signal on Reddit — **W2C** is active buyers, "
        "**QC**/**Review** is recent purchases.\n"
    )
    sections.append(_md_table(flairs[:15], [
        ("flair", "Flair"), ("posts", "Posts"),
        ("avg_score", "Avg Upvotes"), ("avg_comments", "Avg Comments"),
    ]))

    # Cross-subreddit safe bets
    sections.append("## Cross-Subreddit Safe Bets\n")
    sections.append(
        "Items in demand across multiple tracked subreddits (less risk, "
        "broader audience).\n"
    )
    sections.append(_md_table(cross, [
        ("brand", "Brand"), ("item", "Item"),
        ("subreddit_count", "# Subs"),
        ("total_mentions", "Total"), ("weighted_score", "Weighted"),
        ("top_subreddits", "Top Subs"),
        ("purchase_link_md", "Purchase Link"),
    ]))

    # Live hot threads
    sections.append(f"## Hot Right Now on r/{subreddit}\n")
    if hot.get("posts"):
        sections.append(
            f"_Cache fetched {hot.get('fetched_at') or 'unknown'} — "
            f"{'stale' if hot.get('stale') else 'fresh'}._\n"
        )
        hot_rows = [
            {
                "title": p.get("title", ""),
                "flair": p.get("flair") or "—",
                "upvotes": p.get("score", 0),
                "comments": p.get("num_comments", 0),
                "link": _fmt_link(p.get("permalink", "")),
            }
            for p in hot["posts"][:15]
        ]
        sections.append(_md_table(hot_rows, [
            ("title", "Title"), ("flair", "Flair"),
            ("upvotes", "Upvotes"), ("comments", "Comments"),
            ("link", "Link"),
        ]))
    else:
        sections.append(
            "_No live cache. Run `python scripts/refresh_live_hot.py` "
            "to populate._\n"
        )

    sections.append("")
    sections.append(
        "---\n_ZR ItemFinder — Subreddit Deep Dive report._\n"
    )
    return "\n".join(sections)


def write_subreddit_report(conn, subreddit: str,
                           since: str | None = None,
                           out_dir: Path = REPORT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    md = build_subreddit_report(conn, subreddit, since=since)
    path = out_dir / f"{subreddit}.md"
    path.write_text(md, encoding="utf-8")
    log.info("Wrote %s (%d bytes)", path, len(md))
    return path


def _resolve_targets(conn, requested: list[str] | None) -> list[str]:
    if requested:
        return requested
    db_subs = [r["subreddit"] for r in available_subreddits(conn)]
    if db_subs:
        return db_subs
    return list(get_tracked_subreddits())


def generate_all(subreddits: list[str] | None = None,
                 since: str | None = None) -> list[Path]:
    conn = get_connection()
    try:
        targets = _resolve_targets(conn, subreddits)
        out = []
        for s in targets:
            out.append(write_subreddit_report(conn, s, since=since))
    finally:
        conn.close()
    log.info("Wrote %d subreddit reports to %s", len(out), REPORT_DIR)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--subreddits", nargs="+", default=None,
                   help="Specific subreddits (default: all with data)")
    p.add_argument("--since", type=str, default=None,
                   help="ISO timestamp or 'Nd' (e.g. 30d) for a rolling window")
    args = p.parse_args()

    since = args.since
    if since and since.endswith("d") and since[:-1].isdigit():
        days = int(since[:-1])
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()

    generate_all(subreddits=args.subreddits, since=since)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
