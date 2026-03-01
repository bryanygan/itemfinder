"""Tests for the scoring system."""

import sqlite3
import unittest
from datetime import datetime, timedelta

from src.common.db import init_db, insert_processed_mentions
from src.process.scoring import compute_brand_scores, compute_item_scores


class TestScoring(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)
        self._seed_data()

    def tearDown(self):
        self.conn.close()

    def _seed_data(self):
        now = datetime.now()
        recent = now - timedelta(days=2)
        older = now - timedelta(days=10)

        mentions = [
            ("m1", recent.isoformat(), "general", "user1", "Sp5der", "hoodie", "black / size L",
             "request", 0.7, "looking for sp5der hoodie"),
            ("m2", recent.isoformat(), "general", "user2", "Sp5der", "hoodie", None,
             "request", 0.65, "need sp5der hoodie"),
            ("m3", recent.isoformat(), "wtb", "user3", "Sp5der", "hoodie", "size M",
             "request", 0.8, "wtb sp5der hoodie"),
            ("m4", older.isoformat(), "general", "user4", "Chrome Hearts", "ring", "black",
             "satisfaction", 0.6, "chrome hearts ring is fire"),
            ("m5", older.isoformat(), "general", "user5", "Gallery Dept", "tee", None,
             "ownership", 0.5, "just copped gallery dept tee"),
            ("m6", recent.isoformat(), "general", "user6", "Gallery Dept", "tee", "size L",
             "regret", 0.75, "should've bought gallery dept tee"),
        ]
        insert_processed_mentions(self.conn, mentions)

    def test_item_scores_not_empty(self):
        scores = compute_item_scores(self.conn)
        self.assertGreater(len(scores), 0)

    def test_sp5der_highest_score(self):
        scores = compute_item_scores(self.conn)
        sp5der = [s for s in scores if s["brand"] == "Sp5der" and s["item"] == "hoodie"]
        self.assertEqual(len(sp5der), 1)
        # Sp5der hoodie has 3 request mentions (recent) — should score high
        self.assertGreater(sp5der[0]["final_score"], 0.3)

    def test_request_counts(self):
        scores = compute_item_scores(self.conn)
        sp5der = [s for s in scores if s["brand"] == "Sp5der" and s["item"] == "hoodie"][0]
        self.assertEqual(sp5der["request_count"], 3)

    def test_brand_scores(self):
        brands = compute_brand_scores(self.conn)
        self.assertGreater(len(brands), 0)
        brand_names = [b["brand"] for b in brands]
        self.assertIn("Sp5der", brand_names)
        self.assertIn("Chrome Hearts", brand_names)

    def test_brand_mention_counts(self):
        brands = compute_brand_scores(self.conn)
        sp5der = [b for b in brands if b["brand"] == "Sp5der"][0]
        self.assertEqual(sp5der["mentions"], 3)


if __name__ == "__main__":
    unittest.main()
