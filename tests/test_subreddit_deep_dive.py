"""Tests for the per-subreddit deep-dive analytics module."""

import sqlite3
import unittest

from src.analytics.subreddit_deep_dive import (
    all_subreddits_summary,
    available_subreddits,
    best_items_across_subreddits,
    cross_subreddit_matrix,
    get_tracked_subreddits,
    subreddit_flair_signals,
    subreddit_kpis,
    subreddit_purchase_recommendations,
    subreddit_rising_items,
    subreddit_top_items,
)
from src.common.config import REDDIT_TARGET_SUBREDDITS, SUBREDDIT_WEIGHTS
from src.common.db import init_db


def _seed_subreddit_data(conn: sqlite3.Connection) -> None:
    """Populate raw_messages, reddit_metadata and processed_mentions with
    a small mixed dataset across multiple subreddits for assertions."""
    rows = [
        # id, subreddit, brand, item, intent, score, flair, ts
        ("r1", "FashionReps", "Jordan", "Jordan 1 OW (Off-White)", "request", 0.9, "W2C", "2026-04-10T10:00:00"),
        ("r2", "FashionReps", "Jordan", "Jordan 1 OW (Off-White)", "request", 0.85, "W2C", "2026-04-15T10:00:00"),
        ("r3", "FashionReps", "Nike", "Dunk Low (various)", "ownership", 0.7, "QC", "2026-04-12T10:00:00"),
        ("r4", "FashionReps", "Chrome Hearts", "Hoodies / Jewelry", "satisfaction", 0.6, "Review", "2026-04-18T10:00:00"),
        ("r5", "Repsneakers", "Jordan", "Jordan 1 OW (Off-White)", "request", 0.9, "W2C", "2026-04-19T10:00:00"),
        ("r6", "Repsneakers", "Nike", "Dunk Low (various)", "request", 0.8, "W2C", "2026-04-20T10:00:00"),
        ("r7", "Repsneakers", "Yeezy", "350 V2", "regret", 0.95, None, "2026-04-21T10:00:00"),
        ("r8", "DesignerReps", "Louis Vuitton", "Keepall / Neverfull", "request", 0.9, "W2C", "2026-04-22T10:00:00"),
        # Rising item: many recent mentions, few earlier
        ("r9", "FashionReps", "Sp5der", "Hoodies / Pants", "request", 0.9, "W2C", "2026-04-20T10:00:00"),
        ("r10", "FashionReps", "Sp5der", "Hoodies / Pants", "request", 0.9, "W2C", "2026-04-21T10:00:00"),
        ("r11", "FashionReps", "Sp5der", "Hoodies / Pants", "request", 0.9, "W2C", "2026-04-22T10:00:00"),
    ]
    raw = [
        (r[0], f"r/{r[1]}", None, r[1], "alice", "u_alice",
         r[7], f"test {r[2]} {r[3]}", "test", 0, 0, "reddit")
        for r in rows
    ]
    conn.executemany(
        """INSERT INTO raw_messages
           (id, channel, channel_category, guild, author, author_id,
            timestamp, content, source_file, has_attachment, reaction_count,
            source_platform) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        raw,
    )
    meta = [
        (r[0], "post", r[1], r[6], 120, 0.95, 15, 0, None,
         f"/r/{r[1]}/{r[0]}", 1, 1000)
        for r in rows
    ]
    conn.executemany(
        """INSERT INTO reddit_metadata
           (message_id, post_type, subreddit, flair, score, upvote_ratio,
            num_comments, awards, parent_id, permalink, is_op, author_karma)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        meta,
    )
    mentions = [
        (r[0], r[7], f"r/{r[1]}", "alice", r[2], r[3], None, r[4], r[5], "text")
        for r in rows
    ]
    conn.executemany(
        """INSERT INTO processed_mentions
           (message_id, timestamp, channel, author, brand, item, variant,
            intent_type, intent_score, text_norm)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        mentions,
    )
    conn.commit()


class SubredditDeepDiveBase(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)
        _seed_subreddit_data(self.conn)

    def tearDown(self):
        self.conn.close()


class TestConfigHelpers(unittest.TestCase):
    def test_tracked_subreddits_matches_config(self):
        self.assertEqual(get_tracked_subreddits(), list(REDDIT_TARGET_SUBREDDITS))


class TestAvailableSubreddits(SubredditDeepDiveBase):
    def test_lists_subs_with_counts(self):
        subs = available_subreddits(self.conn)
        names = {s["subreddit"] for s in subs}
        self.assertIn("FashionReps", names)
        self.assertIn("Repsneakers", names)
        self.assertIn("DesignerReps", names)

    def test_fashionreps_has_most_mentions(self):
        subs = available_subreddits(self.conn)
        # FashionReps has 6 rows in seed
        top = subs[0]
        self.assertEqual(top["subreddit"], "FashionReps")
        self.assertGreaterEqual(top["mentions"], 6)


class TestSubredditKpis(SubredditDeepDiveBase):
    def test_counts_intents_correctly(self):
        k = subreddit_kpis(self.conn, "FashionReps")
        self.assertEqual(k["subreddit"], "FashionReps")
        # 7 seed rows in FashionReps: 5 request + 1 ownership + 1 satisfaction
        self.assertEqual(k["mentions"], 7)
        self.assertEqual(k["requests"], 5)
        self.assertEqual(k["owned"], 1)
        self.assertEqual(k["satisfied"], 1)

    def test_signal_weight_from_config(self):
        k = subreddit_kpis(self.conn, "FashionReps")
        self.assertAlmostEqual(
            k["signal_weight"], SUBREDDIT_WEIGHTS["fashionreps"], places=3
        )

    def test_unknown_sub_gets_default_weight(self):
        k = subreddit_kpis(self.conn, "somebrandnewsub")
        self.assertGreater(k["signal_weight"], 0)
        self.assertLess(k["signal_weight"], 1.0)


class TestSubredditTopItems(SubredditDeepDiveBase):
    def test_returns_items_scoped_to_subreddit(self):
        items = subreddit_top_items(self.conn, "DesignerReps")
        brands = {i["brand"] for i in items}
        self.assertEqual(brands, {"Louis Vuitton"})

    def test_sorts_by_mentions_desc(self):
        items = subreddit_top_items(self.conn, "FashionReps")
        counts = [i["mentions"] for i in items]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_sp5der_aggregates(self):
        items = subreddit_top_items(self.conn, "FashionReps")
        sp5der = next(i for i in items if i["brand"] == "Sp5der")
        self.assertEqual(sp5der["mentions"], 3)
        self.assertEqual(sp5der["requests"], 3)


class TestSubredditRisingItems(SubredditDeepDiveBase):
    def test_detects_recent_surge(self):
        rising = subreddit_rising_items(self.conn, "FashionReps")
        # Sp5der has 3 recent mentions clustered at the end — expect positive velocity
        sp5der = [r for r in rising if r["brand"] == "Sp5der"]
        self.assertTrue(sp5der)
        self.assertGreater(sp5der[0]["velocity"], 0)


class TestSubredditFlairSignals(SubredditDeepDiveBase):
    def test_w2c_dominates_fashionreps(self):
        flairs = subreddit_flair_signals(self.conn, "FashionReps")
        w2c = next((f for f in flairs if f["flair"] == "W2C"), None)
        self.assertIsNotNone(w2c)
        # 5 rows in seed have W2C flair in FashionReps
        self.assertEqual(w2c["posts"], 5)


class TestCrossSubredditMatrix(SubredditDeepDiveBase):
    def test_jordan_1_spans_multiple_subs(self):
        matrix = cross_subreddit_matrix(self.conn, top_items=10)
        j1 = next(r for r in matrix
                  if r["brand"] == "Jordan" and "OW" in r["item"])
        self.assertGreaterEqual(j1["subreddit_count"], 2)
        self.assertIn("FashionReps", j1["subreddits"])
        self.assertIn("Repsneakers", j1["subreddits"])


class TestBestItemsAcrossSubreddits(SubredditDeepDiveBase):
    def test_returns_weighted_scores(self):
        best = best_items_across_subreddits(self.conn, top_n=10)
        self.assertTrue(best)
        top = best[0]
        self.assertIn("weighted_score", top)
        self.assertGreater(top["weighted_score"], 0)

    def test_cross_subreddit_items_rank_high(self):
        best = best_items_across_subreddits(self.conn, top_n=15)
        # Items present in multiple subs should beat single-sub items
        multi_sub = [b for b in best if b["subreddit_count"] >= 2]
        self.assertTrue(multi_sub)


class TestSubredditPurchaseRecommendations(SubredditDeepDiveBase):
    def test_returns_scored_recommendations(self):
        recs = subreddit_purchase_recommendations(self.conn, "FashionReps")
        self.assertTrue(recs)
        for r in recs:
            self.assertIn("combined_score", r)
            self.assertIn("recommendation", r)
            self.assertIn("purchase_link", r)
            self.assertGreaterEqual(r["combined_score"], 0.0)
            self.assertLessEqual(r["combined_score"], 1.0)

    def test_jordan_1_ow_gets_purchase_link(self):
        recs = subreddit_purchase_recommendations(self.conn, "FashionReps")
        j1 = next((r for r in recs
                   if r["brand"] == "Jordan" and "OW" in r["item"]), None)
        self.assertIsNotNone(j1)
        # PURCHASE_LINKS has a weidian link for this exact key
        self.assertIn("weidian.com", j1["purchase_link"])

    def test_sorted_by_combined_score_desc(self):
        recs = subreddit_purchase_recommendations(self.conn, "FashionReps")
        scores = [r["combined_score"] for r in recs]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_signal_weight_affects_score(self):
        # FashionReps (1.5x) should score its Jordan 1 OW higher than a
        # low-weight agent sub with the same data pattern.
        high_recs = subreddit_purchase_recommendations(self.conn, "FashionReps")
        # Seed an identical row in a low-weight sub
        self.conn.execute(
            "INSERT INTO raw_messages (id, channel, author, timestamp, content, source_platform) "
            "VALUES ('x1', 'r/Sugargoo', 'alice', '2026-04-22T10:00:00', 't', 'reddit')"
        )
        self.conn.execute(
            "INSERT INTO reddit_metadata (message_id, post_type, subreddit, flair) "
            "VALUES ('x1', 'post', 'Sugargoo', 'W2C')"
        )
        self.conn.execute(
            "INSERT INTO processed_mentions "
            "(message_id, timestamp, channel, author, brand, item, intent_type, intent_score) "
            "VALUES ('x1', '2026-04-22T10:00:00', 'r/Sugargoo', 'alice', 'Jordan', "
            "'Jordan 1 OW (Off-White)', 'request', 0.9)"
        )
        self.conn.commit()
        low_recs = subreddit_purchase_recommendations(self.conn, "Sugargoo")

        def score_of(recs, brand, item_substr):
            for r in recs:
                if r["brand"] == brand and item_substr in r["item"]:
                    return r["community_score"]
            return 0.0

        # Both subs have exactly one Jordan 1 OW mention, identical intent.
        # FashionReps (1.5x weight) should outscore Sugargoo (0.9x).
        high = score_of(high_recs, "Jordan", "OW")
        low = score_of(low_recs, "Jordan", "OW")
        self.assertGreater(high, low)


class TestAllSubredditsSummary(SubredditDeepDiveBase):
    def test_lists_every_sub_with_data(self):
        summary = all_subreddits_summary(self.conn)
        names = {s["subreddit"] for s in summary}
        self.assertEqual(
            names, {"FashionReps", "Repsneakers", "DesignerReps"}
        )

    def test_sorted_by_mentions_desc(self):
        summary = all_subreddits_summary(self.conn)
        counts = [s["mentions"] for s in summary]
        self.assertEqual(counts, sorted(counts, reverse=True))


class TestPurchaseRecommendationsEmpty(unittest.TestCase):
    """Regression: on a fresh DB, the page still shows external-only recs
    for subreddits tagged in REDDIT_TRENDING."""

    def test_empty_db_still_returns_external_recs_for_tagged_sub(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_db(conn)
        recs = subreddit_purchase_recommendations(conn, "FashionReps")
        # REDDIT_TRENDING has many items tagged "FashionReps"
        self.assertTrue(recs)
        # None should claim internal mentions
        self.assertTrue(all(r["mentions"] == 0 for r in recs))
        conn.close()


if __name__ == "__main__":
    unittest.main()
