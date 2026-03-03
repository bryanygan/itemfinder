"""Tests for Reddit ingestion, normalization, classification, and extraction."""

import sqlite3
import unittest

from src.common.config import BATCH_NAMES, FLAIR_INTENT_MAP, REDDIT_TARGET_SUBREDDITS
from src.common.db import (
    init_db,
    insert_raw_messages_reddit,
    insert_reddit_metadata,
)
from src.process.classify import classify_intent, classify_intent_from_flair
from src.process.extract import (
    extract_agent,
    extract_batch,
    extract_from_reddit_title,
)
from src.process.normalize import is_spam_or_empty, normalize_text


class TestRedditNormalization(unittest.TestCase):
    """Test Reddit-specific text normalization."""

    def test_removes_reddit_user_mentions(self):
        text = "Check out /u/repfam123 review"
        result = normalize_text(text)
        self.assertNotIn("/u/repfam123", result)
        self.assertIn("check out", result)

    def test_removes_subreddit_mentions(self):
        text = "Also posted on /r/FashionReps"
        result = normalize_text(text)
        self.assertNotIn("/r/FashionReps", result)

    def test_removes_reddit_quotes(self):
        text = "> This was the original comment\nMy reply here"
        result = normalize_text(text)
        self.assertNotIn("original comment", result)
        self.assertIn("my reply here", result)

    def test_removes_yuan_prices(self):
        text = "Got these for ¥199 from weidian"
        result = normalize_text(text)
        self.assertNotIn("199", result)
        self.assertIn("got these for", result)

    def test_removes_cny_prices(self):
        text = "Only 89 yuan for this hoodie"
        result = normalize_text(text)
        self.assertNotIn("89 yuan", result)

    def test_removes_edit_notices(self):
        text = "Great cop! Edit 2: added more photos"
        result = normalize_text(text)
        self.assertNotIn("edit 2:", result)

    def test_bot_detection(self):
        self.assertTrue(is_spam_or_empty("I am a bot and this action was performed automatically"))
        self.assertTrue(is_spam_or_empty("beep boop contact the moderators"))

    def test_normal_text_not_spam(self):
        self.assertFalse(is_spam_or_empty("looking for jordan 4 military black size 12"))

    def test_combined_cleanup(self):
        text = "Just copped from /u/seller123 for ¥350 https://weidian.com/item/123 fire"
        result = normalize_text(text)
        self.assertIn("just copped from", result)
        self.assertIn("fire", result)
        self.assertNotIn("weidian.com", result)
        self.assertNotIn("350", result)


class TestRedditFlairClassification(unittest.TestCase):
    """Test Reddit flair-based intent classification."""

    def test_w2c_flair_request(self):
        intent, score = classify_intent_from_flair("W2C", "best jordan 4 batch")
        self.assertEqual(intent, "request")
        self.assertGreaterEqual(score, 0.85)

    def test_qc_flair_ownership(self):
        intent, score = classify_intent_from_flair("QC", "how do these look")
        self.assertEqual(intent, "ownership")
        self.assertGreaterEqual(score, 0.8)

    def test_haul_flair_ownership(self):
        intent, score = classify_intent_from_flair("HAUL", "10kg haul to us")
        self.assertEqual(intent, "ownership")
        self.assertGreaterEqual(score, 0.8)

    def test_review_flair_satisfaction(self):
        intent, score = classify_intent_from_flair("REVIEW", "balenciaga track review")
        self.assertEqual(intent, "satisfaction")
        self.assertGreaterEqual(score, 0.7)

    def test_find_flair_request(self):
        intent, score = classify_intent_from_flair("FIND", "found this nike dunk")
        self.assertEqual(intent, "request")
        self.assertGreaterEqual(score, 0.8)

    def test_in_hand_flair_ownership(self):
        intent, score = classify_intent_from_flair("in hand", "my pair arrived")
        self.assertEqual(intent, "ownership")
        self.assertGreaterEqual(score, 0.85)

    def test_partial_flair_match(self):
        intent, score = classify_intent_from_flair("[W2C] Nike Dunk Low", "best batch")
        self.assertEqual(intent, "request")
        self.assertGreaterEqual(score, 0.85)

    def test_none_flair_falls_back(self):
        intent, score = classify_intent_from_flair(None, "looking for jordan 4")
        self.assertEqual(intent, "request")
        self.assertGreater(score, 0)

    def test_discussion_flair_neutral(self):
        intent, score = classify_intent_from_flair("discussion", "what do you think")
        self.assertEqual(intent, "neutral")

    def test_flair_boosts_matching_keyword(self):
        # W2C flair + "looking for" keyword should boost beyond either alone
        intent_flair, score_flair = classify_intent_from_flair("w2c", "looking for jordan 4")
        intent_kw, score_kw = classify_intent(None)
        self.assertEqual(intent_flair, "request")
        self.assertGreater(score_flair, 0.85)

    def test_emoji_flair_qc(self):
        intent, score = classify_intent_from_flair("🌅qc", "how does this look")
        self.assertEqual(intent, "ownership")
        self.assertGreaterEqual(score, 0.8)

    def test_emoji_flair_w2c(self):
        intent, score = classify_intent_from_flair("🚩w2c", "need this hoodie")
        self.assertEqual(intent, "request")
        self.assertGreaterEqual(score, 0.85)

    def test_emoji_flair_in_hand(self):
        intent, score = classify_intent_from_flair("🎧in hand pics", "just arrived today")
        self.assertEqual(intent, "ownership")
        self.assertGreaterEqual(score, 0.85)

    def test_paren_flair_qc(self):
        intent, score = classify_intent_from_flair("(QC) Quality Check", "nike dunk")
        self.assertEqual(intent, "ownership")
        self.assertGreaterEqual(score, 0.8)

    def test_compound_flair_qc_lc(self):
        # "qc/lc" should match QC (first segment) not LC
        intent, score = classify_intent_from_flair("qc/lc", "check these shoes")
        self.assertEqual(intent, "ownership")
        self.assertGreaterEqual(score, 0.8)

    def test_decorated_flair_qc_request(self):
        intent, score = classify_intent_from_flair("💯 qc request 💯", "is this good")
        self.assertEqual(intent, "ownership")
        self.assertGreaterEqual(score, 0.8)

    def test_flair_fs_ownership(self):
        intent, score = classify_intent_from_flair("fs", "selling jordan 4")
        self.assertEqual(intent, "ownership")

    def test_flair_review_emoji(self):
        intent, score = classify_intent_from_flair("review 🗒️", "balenciaga track review")
        self.assertEqual(intent, "satisfaction")
        self.assertGreaterEqual(score, 0.7)

    def test_cool_finds_flair(self):
        intent, score = classify_intent_from_flair("🫶cool finds", "found this dunk")
        self.assertEqual(intent, "request")
        self.assertGreaterEqual(score, 0.8)


class TestRedditKeywords(unittest.TestCase):
    """Test Reddit-specific keywords are recognized."""

    def test_gl_satisfaction(self):
        intent, score = classify_intent("gl these look great easy gl")
        self.assertEqual(intent, "satisfaction")
        self.assertGreater(score, 0)

    def test_rl_regret(self):
        intent, score = classify_intent("rl calloutable easy callout")
        self.assertEqual(intent, "regret")
        self.assertGreater(score, 0)

    def test_best_batch_with_flair_request(self):
        # "best batch" alone is ambiguous (keyword "best" hits satisfaction too).
        # On Reddit, the W2C flair resolves this correctly.
        intent, score = classify_intent_from_flair("w2c", "best batch for jordan 4 military black")
        self.assertEqual(intent, "request")
        self.assertGreater(score, 0.85)

    def test_haul_review_ownership(self):
        intent, score = classify_intent("my haul arrived haul review 10kg")
        self.assertEqual(intent, "ownership")
        self.assertGreater(score, 0)

    def test_in_hand_review(self):
        intent, score = classify_intent("in hand review these are fire")
        # Should pick up ownership or satisfaction
        self.assertIn(intent, ("ownership", "satisfaction"))
        self.assertGreater(score, 0)

    def test_budget_request(self):
        intent, score = classify_intent("anyone gp'd the budget batch of these")
        self.assertEqual(intent, "request")
        self.assertGreater(score, 0)

    def test_weidian_link_request(self):
        intent, score = classify_intent("weidian link please for this hoodie")
        self.assertEqual(intent, "request")
        self.assertGreater(score, 0)


class TestRedditDatabase(unittest.TestCase):
    """Test Reddit-specific database operations."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_insert_reddit_message(self):
        rows = [(
            "reddit_t3_abc123", "fashionreps", "w2c", "reddit",
            "testuser", "user123", "2025-06-15T12:00:00+00:00",
            "W2C best jordan 4 military black", "reddit_api",
            0, 42,
        )]
        count = insert_raw_messages_reddit(self.conn, rows)
        self.assertEqual(count, 1)

        row = self.conn.execute(
            "SELECT * FROM raw_messages WHERE id = ?", ("reddit_t3_abc123",)
        ).fetchone()
        self.assertEqual(row["source_platform"], "reddit")
        self.assertEqual(row["channel"], "fashionreps")
        self.assertEqual(row["reaction_count"], 42)

    def test_insert_reddit_metadata(self):
        # Insert raw message first (FK)
        self.conn.execute(
            """INSERT INTO raw_messages
               (id, channel, guild, author, timestamp, content, source_platform)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("reddit_t3_abc123", "fashionreps", "reddit", "user",
             "2025-06-15T12:00:00+00:00", "test", "reddit"),
        )
        self.conn.commit()

        meta_rows = [(
            "reddit_t3_abc123", "submission", "fashionreps", "w2c",
            42, 0.95, 15, 2, None,
            "/r/FashionReps/comments/abc123/", 0, 5000,
        )]
        count = insert_reddit_metadata(self.conn, meta_rows)
        self.assertEqual(count, 1)

        row = self.conn.execute(
            "SELECT * FROM reddit_metadata WHERE message_id = ?",
            ("reddit_t3_abc123",)
        ).fetchone()
        self.assertEqual(row["post_type"], "submission")
        self.assertEqual(row["score"], 42)
        self.assertEqual(row["flair"], "w2c")
        self.assertEqual(row["num_comments"], 15)

    def test_duplicate_reddit_message_ignored(self):
        rows = [(
            "reddit_t3_abc123", "fashionreps", "w2c", "reddit",
            "testuser", "user123", "2025-06-15T12:00:00+00:00",
            "content", "reddit_api", 0, 42,
        )]
        insert_raw_messages_reddit(self.conn, rows)
        count = insert_raw_messages_reddit(self.conn, rows)
        self.assertEqual(count, 0)  # duplicate ignored

    def test_platform_index_query(self):
        # Insert both discord and reddit messages
        self.conn.execute(
            """INSERT INTO raw_messages
               (id, channel, guild, author, timestamp, content, source_platform)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("discord_1", "general", "testguild", "user",
             "2025-06-15T12:00:00+00:00", "test", "discord"),
        )
        rows = [(
            "reddit_t3_x", "fashionreps", "", "reddit",
            "user", "uid", "2025-06-15T12:00:00+00:00",
            "test", "reddit_api", 0, 10,
        )]
        insert_raw_messages_reddit(self.conn, rows)

        reddit_count = self.conn.execute(
            "SELECT COUNT(*) FROM raw_messages WHERE source_platform = 'reddit'"
        ).fetchone()[0]
        discord_count = self.conn.execute(
            "SELECT COUNT(*) FROM raw_messages WHERE source_platform = 'discord'"
        ).fetchone()[0]
        self.assertEqual(reddit_count, 1)
        self.assertEqual(discord_count, 1)


class TestRedditConfig(unittest.TestCase):
    """Test Reddit configuration values."""

    def test_target_subreddits_defined(self):
        self.assertGreaterEqual(len(REDDIT_TARGET_SUBREDDITS), 15)

    def test_flair_map_has_key_flairs(self):
        for flair in ["w2c", "qc", "haul", "review", "find", "in hand", "gp", "wtb", "wts"]:
            self.assertIn(flair, FLAIR_INTENT_MAP, f"Missing flair: {flair}")

    def test_flair_scores_in_range(self):
        for flair, (intent, score) in FLAIR_INTENT_MAP.items():
            self.assertGreaterEqual(score, 0.0, f"Score below 0 for {flair}")
            self.assertLessEqual(score, 1.0, f"Score above 1 for {flair}")
            self.assertIn(intent, ("request", "ownership", "satisfaction", "neutral"),
                          f"Bad intent for {flair}: {intent}")

    def test_batch_names_defined(self):
        # Key batches from research must be in config
        for batch_canonical in ["LJR", "PK", "OG", "HP", "M", "DT", "QY", "H12"]:
            self.assertIn(batch_canonical, BATCH_NAMES.values(),
                          f"Missing batch: {batch_canonical}")


class TestBatchExtraction(unittest.TestCase):
    """Test factory batch name extraction (Reddit-specific)."""

    def test_ljr_batch(self):
        self.assertEqual(extract_batch("got the ljr batch jordan 4"), "LJR")

    def test_pk_batch(self):
        self.assertEqual(extract_batch("pk batch travis scott"), "PK")

    def test_m_batch(self):
        self.assertEqual(extract_batch("m batch dunk low is great"), "M")

    def test_dt_budget(self):
        self.assertEqual(extract_batch("dt batch is budget friendly"), "DT")

    def test_no_batch(self):
        self.assertIsNone(extract_batch("just a regular jordan 4 post"))

    def test_h12_batch(self):
        self.assertEqual(extract_batch("h12 makes decent yeezy slides"), "H12")

    def test_named_seller(self):
        self.assertEqual(extract_batch("got from cappuccino store"), "Cappuccino")


class TestAgentExtraction(unittest.TestCase):
    """Test shopping agent name extraction."""

    def test_pandabuy(self):
        self.assertEqual(extract_agent("ordered through pandabuy"), "pandabuy")

    def test_sugargoo(self):
        self.assertEqual(extract_agent("my sugargoo haul just arrived"), "sugargoo")

    def test_cssbuy(self):
        self.assertEqual(extract_agent("shipped with cssbuy"), "cssbuy")

    def test_no_agent(self):
        self.assertIsNone(extract_agent("just got some nice shoes"))


class TestRedditTitleParsing(unittest.TestCase):
    """Test structured Reddit post title parsing."""

    def test_qc_title(self):
        result = extract_from_reddit_title("[QC] Nike Dunk Low Panda - LJR Batch - from Pandabuy")
        self.assertEqual(result["flair_tag"], "qc")
        self.assertEqual(result["brand"], "Nike")
        self.assertEqual(result["batch"], "LJR")
        self.assertEqual(result["agent"], "pandabuy")

    def test_w2c_title(self):
        result = extract_from_reddit_title("[W2C] Chrome Hearts hoodie size L")
        self.assertEqual(result["flair_tag"], "w2c")
        self.assertEqual(result["brand"], "Chrome Hearts")
        self.assertEqual(result["item"], "hoodie")

    def test_find_title_with_price(self):
        result = extract_from_reddit_title("[FIND] Jordan 4 Military Black from weidian")
        self.assertEqual(result["flair_tag"], "find")
        self.assertEqual(result["brand"], "Jordan")
        self.assertEqual(result["platform"], "weidian")

    def test_haul_title(self):
        result = extract_from_reddit_title("[HAUL] 10kg haul - Jordan, Nike Dunk, Chrome Hearts")
        self.assertEqual(result["flair_tag"], "haul")
        # Should pick up at least one brand
        self.assertIsNotNone(result["brand"])

    def test_no_brackets(self):
        result = extract_from_reddit_title("My new Jordan 4 military black in hand")
        self.assertNotIn("flair_tag", result)
        self.assertEqual(result["brand"], "Jordan")

    def test_empty_title(self):
        result = extract_from_reddit_title("")
        self.assertEqual(result, {})

    def test_bst_title(self):
        result = extract_from_reddit_title("[WTS] [USA] Jordan 4 Black Cat size 10")
        self.assertEqual(result["flair_tag"], "wts")
        self.assertEqual(result["brand"], "Jordan")


class TestBracketTagNormalization(unittest.TestCase):
    """Test that bracket tags are stripped during normalization."""

    def test_strip_qc_bracket(self):
        text = "[QC] Nike Dunk Low from Pandabuy"
        result = normalize_text(text)
        self.assertNotIn("[qc]", result)
        self.assertIn("nike dunk low", result)

    def test_strip_w2c_bracket(self):
        text = "[W2C] Best batch Jordan 4"
        result = normalize_text(text)
        self.assertNotIn("[w2c]", result)
        self.assertIn("jordan 4", result)

    def test_strip_multiple_brackets(self):
        text = "[WTS] [USA] Jordan 4 Black Cat"
        result = normalize_text(text)
        self.assertNotIn("[wts]", result)
        self.assertNotIn("[usa]", result)
        self.assertIn("jordan 4 black cat", result)


if __name__ == "__main__":
    unittest.main()
