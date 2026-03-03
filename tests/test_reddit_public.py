"""Tests for the public Reddit JSON scraper (no API key)."""

import json
import sqlite3
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from src.common.db import init_db, insert_raw_messages_reddit, insert_reddit_metadata
from src.ingest.reddit_public import (
    _comment_to_rows,
    _flatten_comments,
    _post_to_rows,
    _ts_iso,
    collect_subreddit,
)


class TestTimestamp(unittest.TestCase):
    def test_ts_iso_format(self):
        # 2025-06-15 12:00:00 UTC
        ts = 1750003200.0
        result = _ts_iso(ts)
        self.assertIn("2025-06-15", result)
        self.assertIn("+00:00", result)

    def test_ts_iso_zero(self):
        result = _ts_iso(0)
        self.assertIn("1970-01-01", result)


class TestPostToRows(unittest.TestCase):
    def _make_post(self, **overrides):
        base = {
            "id": "abc123",
            "title": "[QC] Nike Dunk Low Panda - LJR Batch",
            "selftext": "How do these look? From Pandabuy.",
            "author": "testuser",
            "author_fullname": "t2_xyz",
            "created_utc": 1750003200.0,
            "score": 42,
            "upvote_ratio": 0.95,
            "num_comments": 15,
            "link_flair_text": "QC",
            "permalink": "/r/FashionReps/comments/abc123/qc_nike_dunk/",
            "is_self": True,
            "url": "https://reddit.com/r/FashionReps/comments/abc123/",
            "total_awards_received": 2,
            "subreddit": "FashionReps",
        }
        base.update(overrides)
        return base

    def test_basic_post_conversion(self):
        post = self._make_post()
        raw, meta = _post_to_rows(post, "FashionReps")

        self.assertIsNotNone(raw)
        self.assertEqual(raw[0], "reddit_t3_abc123")
        self.assertEqual(raw[1], "fashionreps")
        self.assertEqual(raw[2], "qc")  # flair
        self.assertEqual(raw[3], "reddit")
        self.assertEqual(raw[4], "testuser")
        self.assertIn("Nike Dunk Low Panda", raw[7])  # content
        self.assertIn("Pandabuy", raw[7])
        self.assertEqual(raw[8], "reddit_public")
        self.assertEqual(raw[10], 42)  # score

        self.assertEqual(meta[0], "reddit_t3_abc123")
        self.assertEqual(meta[1], "submission")
        self.assertEqual(meta[4], 42)
        self.assertEqual(meta[5], 0.95)
        self.assertEqual(meta[6], 15)

    def test_empty_content_returns_none(self):
        post = self._make_post(title="", selftext="")
        raw, meta = _post_to_rows(post, "test")
        self.assertIsNone(raw)

    def test_no_id_returns_none(self):
        post = self._make_post(id="")
        raw, meta = _post_to_rows(post, "test")
        self.assertIsNone(raw)

    def test_no_flair(self):
        post = self._make_post(link_flair_text=None)
        raw, meta = _post_to_rows(post, "test")
        self.assertEqual(raw[2], "")  # empty string for channel_category
        self.assertIsNone(meta[3])

    def test_link_post_has_attachment(self):
        post = self._make_post(is_self=False)
        raw, meta = _post_to_rows(post, "test")
        self.assertEqual(raw[9], 1)  # has_attachment

    def test_self_post_no_attachment(self):
        post = self._make_post(is_self=True)
        raw, meta = _post_to_rows(post, "test")
        self.assertEqual(raw[9], 0)

    def test_deleted_author(self):
        post = self._make_post(author="[deleted]")
        raw, meta = _post_to_rows(post, "test")
        self.assertEqual(raw[4], "[deleted]")

    def test_flair_normalization(self):
        post = self._make_post(link_flair_text="  W2C  ")
        raw, meta = _post_to_rows(post, "test")
        self.assertEqual(raw[2], "w2c")
        self.assertEqual(meta[3], "w2c")


class TestCommentToRows(unittest.TestCase):
    def _make_comment(self, **overrides):
        base = {
            "id": "def456",
            "body": "GL these look great, easy green light",
            "author": "commenter1",
            "author_fullname": "t2_abc",
            "created_utc": 1750010000.0,
            "score": 10,
            "permalink": "/r/FashionReps/comments/abc123/qc/def456/",
            "total_awards_received": 0,
        }
        base.update(overrides)
        return base

    def test_basic_comment_conversion(self):
        c = self._make_comment()
        raw, meta = _comment_to_rows(c, "FashionReps", "abc123", "poster")

        self.assertEqual(raw[0], "reddit_t1_def456")
        self.assertEqual(raw[1], "fashionreps")
        self.assertEqual(raw[4], "commenter1")
        self.assertIn("GL these look great", raw[7])
        self.assertEqual(raw[10], 10)

        self.assertEqual(meta[1], "comment")
        self.assertEqual(meta[8], "reddit_t3_abc123")
        self.assertEqual(meta[10], 0)  # not OP

    def test_op_comment_detected(self):
        c = self._make_comment(author="poster")
        raw, meta = _comment_to_rows(c, "test", "abc123", "poster")
        self.assertEqual(meta[10], 1)  # is_op

    def test_deleted_comment_returns_none(self):
        c = self._make_comment(body="[deleted]")
        raw, meta = _comment_to_rows(c, "test", "abc123", "poster")
        self.assertIsNone(raw)

    def test_removed_comment_returns_none(self):
        c = self._make_comment(body="[removed]")
        raw, meta = _comment_to_rows(c, "test", "abc123", "poster")
        self.assertIsNone(raw)

    def test_empty_id_returns_none(self):
        c = self._make_comment(id="")
        raw, meta = _comment_to_rows(c, "test", "abc123", "poster")
        self.assertIsNone(raw)


class TestFlattenComments(unittest.TestCase):
    def test_simple_listing(self):
        tree = {
            "kind": "Listing",
            "data": {
                "children": [
                    {
                        "kind": "t1",
                        "data": {
                            "id": "c1",
                            "body": "Nice shoes!",
                            "author": "user1",
                            "replies": "",
                        },
                    },
                    {
                        "kind": "t1",
                        "data": {
                            "id": "c2",
                            "body": "GL for sure",
                            "author": "user2",
                            "replies": "",
                        },
                    },
                ],
            },
        }
        comments = _flatten_comments(tree)
        self.assertEqual(len(comments), 2)
        self.assertEqual(comments[0]["body"], "Nice shoes!")

    def test_nested_replies(self):
        tree = {
            "kind": "Listing",
            "data": {
                "children": [
                    {
                        "kind": "t1",
                        "data": {
                            "id": "c1",
                            "body": "Parent comment",
                            "author": "user1",
                            "replies": {
                                "kind": "Listing",
                                "data": {
                                    "children": [
                                        {
                                            "kind": "t1",
                                            "data": {
                                                "id": "c2",
                                                "body": "Child reply",
                                                "author": "user2",
                                                "replies": "",
                                            },
                                        }
                                    ]
                                },
                            },
                        },
                    }
                ]
            },
        }
        comments = _flatten_comments(tree)
        self.assertEqual(len(comments), 2)
        bodies = [c["body"] for c in comments]
        self.assertIn("Parent comment", bodies)
        self.assertIn("Child reply", bodies)

    def test_deleted_comments_excluded(self):
        tree = {
            "kind": "Listing",
            "data": {
                "children": [
                    {
                        "kind": "t1",
                        "data": {"id": "c1", "body": "[deleted]", "replies": ""},
                    },
                    {
                        "kind": "t1",
                        "data": {"id": "c2", "body": "Real comment", "replies": ""},
                    },
                ],
            },
        }
        comments = _flatten_comments(tree)
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0]["body"], "Real comment")

    def test_depth_limit(self):
        # Build a chain 10 levels deep
        def _nest(depth):
            if depth <= 0:
                return ""
            return {
                "kind": "Listing",
                "data": {
                    "children": [
                        {
                            "kind": "t1",
                            "data": {
                                "id": f"c{depth}",
                                "body": f"Level {depth}",
                                "author": "u",
                                "replies": _nest(depth - 1),
                            },
                        }
                    ]
                },
            }

        tree = _nest(10)
        # Default max_depth=5 should limit results
        comments = _flatten_comments(tree, max_depth=5)
        self.assertLessEqual(len(comments), 6)  # root + 5 levels

    def test_more_node_skipped(self):
        tree = {
            "kind": "Listing",
            "data": {
                "children": [
                    {"kind": "more", "data": {"count": 50, "children": ["x", "y"]}},
                    {
                        "kind": "t1",
                        "data": {"id": "c1", "body": "Real", "replies": ""},
                    },
                ],
            },
        }
        comments = _flatten_comments(tree)
        self.assertEqual(len(comments), 1)

    def test_empty_listing(self):
        tree = {"kind": "Listing", "data": {"children": []}}
        self.assertEqual(_flatten_comments(tree), [])

    def test_list_input(self):
        """Test that a list of nodes is handled (Reddit returns array at top level)."""
        items = [
            {"kind": "Listing", "data": {"children": []}},
            {
                "kind": "Listing",
                "data": {
                    "children": [
                        {"kind": "t1", "data": {"id": "c1", "body": "Hi", "replies": ""}}
                    ]
                },
            },
        ]
        comments = _flatten_comments(items)
        self.assertEqual(len(comments), 1)


class TestCollectSubredditIntegration(unittest.TestCase):
    """Integration test: mock HTTP, verify DB rows."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)

    def tearDown(self):
        self.conn.close()

    def _listing_response(self, posts, after=None):
        """Build a Reddit-style listing JSON response."""
        return {
            "kind": "Listing",
            "data": {
                "after": after,
                "children": [
                    {"kind": "t3", "data": p} for p in posts
                ],
            },
        }

    def _comment_response(self, post_data, comments):
        """Build a Reddit-style comments JSON response."""
        return [
            {"kind": "Listing", "data": {"children": [{"kind": "t3", "data": post_data}]}},
            {
                "kind": "Listing",
                "data": {
                    "children": [
                        {"kind": "t1", "data": c} for c in comments
                    ],
                },
            },
        ]

    @patch("src.ingest.reddit_public._fetch_json")
    @patch("src.ingest.reddit_public._REQUEST_DELAY", 0)
    def test_collects_posts_and_comments(self, mock_fetch):
        now = datetime.now(timezone.utc).timestamp()

        post = {
            "id": "post1",
            "title": "[W2C] Jordan 4 Military Black",
            "selftext": "Looking for LJR batch",
            "author": "user1",
            "author_fullname": "t2_u1",
            "created_utc": now - 3600,
            "score": 25,
            "upvote_ratio": 0.92,
            "num_comments": 5,
            "link_flair_text": "W2C",
            "permalink": "/r/FashionReps/comments/post1/",
            "is_self": True,
            "total_awards_received": 0,
        }

        comment1 = {
            "id": "c1",
            "body": "LJR is the best batch for J4s",
            "author": "helper1",
            "author_fullname": "t2_h1",
            "created_utc": now - 3000,
            "score": 8,
            "permalink": "/r/FashionReps/comments/post1/c1/",
            "total_awards_received": 0,
            "replies": "",
        }

        # Build responses: new listing, top listing (empty), hot (empty),
        # search queries (empty), comment fetch
        listing_with_post = self._listing_response([post])
        empty_listing = self._listing_response([])
        comment_resp = self._comment_response(post, [comment1])

        # The mock returns different things depending on the URL
        def side_effect(url):
            if "/comments/post1.json" in url:
                return comment_resp
            if "/new.json" in url and "after=" not in url:
                return listing_with_post
            return empty_listing

        mock_fetch.side_effect = side_effect

        stats = collect_subreddit(
            "FashionReps",
            self.conn,
            days=7,
            include_comments=True,
            min_score_for_comments=1,
            min_comments_for_fetch=1,
            max_comment_posts=10,
        )

        self.assertEqual(stats["submissions"], 1)
        self.assertEqual(stats["comments"], 1)

        # Verify DB
        raw_count = self.conn.execute("SELECT COUNT(*) FROM raw_messages").fetchone()[0]
        self.assertEqual(raw_count, 2)  # 1 post + 1 comment

        meta_count = self.conn.execute("SELECT COUNT(*) FROM reddit_metadata").fetchone()[0]
        self.assertEqual(meta_count, 2)

        post_row = self.conn.execute(
            "SELECT * FROM raw_messages WHERE id = ?", ("reddit_t3_post1",)
        ).fetchone()
        self.assertEqual(post_row["source_platform"], "reddit")
        self.assertEqual(post_row["channel"], "fashionreps")
        self.assertIn("Jordan 4 Military Black", post_row["content"])

    @patch("src.ingest.reddit_public._fetch_json")
    @patch("src.ingest.reddit_public._REQUEST_DELAY", 0)
    def test_deduplicates_across_strategies(self, mock_fetch):
        now = datetime.now(timezone.utc).timestamp()
        post = {
            "id": "dup1",
            "title": "Test Post",
            "selftext": "",
            "author": "user1",
            "created_utc": now - 100,
            "score": 10,
            "upvote_ratio": 0.9,
            "num_comments": 0,
            "link_flair_text": None,
            "permalink": "/r/test/comments/dup1/",
            "is_self": True,
            "total_awards_received": 0,
        }

        listing = self._listing_response([post])

        # Return same post from every strategy
        mock_fetch.return_value = listing

        stats = collect_subreddit(
            "test", self.conn, days=7, include_comments=False
        )

        # Should only count once despite appearing in /new, /top, /hot, searches
        self.assertEqual(stats["submissions"], 1)

    @patch("src.ingest.reddit_public._fetch_json")
    @patch("src.ingest.reddit_public._REQUEST_DELAY", 0)
    def test_respects_cutoff_date(self, mock_fetch):
        now = datetime.now(timezone.utc).timestamp()
        recent = {
            "id": "recent1", "title": "Recent", "selftext": "",
            "author": "u", "created_utc": now - 3600,
            "score": 5, "upvote_ratio": 0.9, "num_comments": 0,
            "link_flair_text": None, "permalink": "/r/t/r/",
            "is_self": True, "total_awards_received": 0,
        }
        old = {
            "id": "old1", "title": "Old Post", "selftext": "",
            "author": "u", "created_utc": now - (100 * 86400),  # 100 days ago
            "score": 5, "upvote_ratio": 0.9, "num_comments": 0,
            "link_flair_text": None, "permalink": "/r/t/o/",
            "is_self": True, "total_awards_received": 0,
        }

        listing = self._listing_response([recent, old])
        empty = self._listing_response([])

        def side_effect(url):
            if "/new.json" in url and "after=" not in url:
                return listing
            return empty

        mock_fetch.side_effect = side_effect

        stats = collect_subreddit("test", self.conn, days=90, include_comments=False)
        self.assertEqual(stats["submissions"], 1)  # only recent, old is beyond 90d


class TestDatabaseSchemaCompat(unittest.TestCase):
    """Verify rows from public scraper match the DB schema exactly."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_raw_row_inserts_correctly(self):
        raw_row = (
            "reddit_t3_test1", "fashionreps", "w2c", "reddit",
            "author", "t2_xyz", "2025-06-15T12:00:00+00:00",
            "test content", "reddit_public", 0, 42,
        )
        count = insert_raw_messages_reddit(self.conn, [raw_row])
        self.assertEqual(count, 1)

        row = self.conn.execute(
            "SELECT * FROM raw_messages WHERE id = ?", ("reddit_t3_test1",)
        ).fetchone()
        self.assertEqual(row["source_platform"], "reddit")
        self.assertEqual(row["source_file"], "reddit_public")

    def test_meta_row_inserts_correctly(self):
        # Insert raw first (FK)
        self.conn.execute(
            """INSERT INTO raw_messages
               (id, channel, guild, author, timestamp, content, source_platform)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("reddit_t3_m1", "test", "reddit", "u",
             "2025-06-15T12:00:00+00:00", "c", "reddit"),
        )
        self.conn.commit()

        meta_row = (
            "reddit_t3_m1", "submission", "test", "w2c",
            42, 0.95, 15, 2, None, "/r/test/m1/", 0, 0,
        )
        count = insert_reddit_metadata(self.conn, [meta_row])
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
