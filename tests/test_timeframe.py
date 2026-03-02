"""Tests for timeframe filtering across all analytics functions."""

import sqlite3
import unittest
from datetime import datetime, timedelta

from src.analytics.sales_intel import (
    brand_cross_sell, buyer_profiles, color_demand,
    conversion_tracking, inventory_recommendations,
    monthly_seasonality, size_demand, unmet_demand,
)
from src.analytics.trends import (
    channel_breakdown, daily_volume, sentiment_over_time,
    top_items_by_intent, trending_items,
)
from src.common.db import (
    init_db, insert_processed_mentions, insert_raw_messages,
    processed_mention_count, raw_message_count,
)
from src.process.scoring import compute_brand_scores, compute_item_scores


class TimeframeTestBase(unittest.TestCase):
    """Base class with seeded data spanning multiple time periods."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)
        self._seed()

    def tearDown(self):
        self.conn.close()

    def _seed(self):
        now = datetime.now()
        self.ts_recent = (now - timedelta(days=3)).isoformat()   # within 7d
        self.ts_mid = (now - timedelta(days=20)).isoformat()      # within 30d but not 7d
        self.ts_old = (now - timedelta(days=100)).isoformat()     # outside 90d
        self.since_7d = (now - timedelta(days=7)).isoformat()
        self.since_30d = (now - timedelta(days=30)).isoformat()
        self.since_90d = (now - timedelta(days=90)).isoformat()
        self.since_future = (now + timedelta(days=1)).isoformat()

        # Raw messages
        raws = [
            (f"r{i}", "general", "cat", "guild", f"user{i}", f"uid{i}",
             ts, f"content {i}", "src.json", 0, 0)
            for i, ts in enumerate([
                self.ts_recent, self.ts_recent, self.ts_recent,
                self.ts_mid, self.ts_mid,
                self.ts_old, self.ts_old, self.ts_old, self.ts_old,
            ])
        ]
        insert_raw_messages(self.conn, raws)

        # Processed mentions — spread across timeframes
        mentions = [
            # Recent (within 7d) — 5 mentions
            ("r0", self.ts_recent, "wtb", "user1", "Nike", "dunk", "black / size 10",
             "request", 0.8, "wtb nike dunk"),
            ("r0", self.ts_recent, "wtb", "user2", "Nike", "dunk", "white / size 9",
             "request", 0.75, "need nike dunk"),
            ("r1", self.ts_recent, "general", "user3", "Nike", "dunk", None,
             "satisfaction", 0.6, "nike dunk fire"),
            ("r1", self.ts_recent, "general", "user4", "Adidas", "yeezy", "size 11",
             "request", 0.7, "looking for yeezy"),
            ("r2", self.ts_recent, "pickups", "user5", "Adidas", "yeezy", None,
             "ownership", 0.5, "just copped yeezy"),
            # Mid (within 30d, not 7d) — 4 mentions
            ("r3", self.ts_mid, "general", "user1", "Nike", "dunk", "red / size 10",
             "request", 0.65, "anyone have nike dunk red"),
            ("r3", self.ts_mid, "general", "user2", "Puma", "suede", None,
             "regret", 0.55, "should have got puma suede"),
            ("r4", self.ts_mid, "wtb", "user3", "Nike", "air force", None,
             "request", 0.7, "wtb air force"),
            ("r4", self.ts_mid, "general", "user6", "Adidas", "yeezy", "size 12",
             "ownership", 0.5, "got my yeezy"),
            # Old (outside 90d) — 5 mentions
            ("r5", self.ts_old, "general", "user1", "Nike", "dunk", None,
             "request", 0.6, "old nike dunk request"),
            ("r5", self.ts_old, "general", "user2", "Nike", "dunk", None,
             "ownership", 0.5, "old nike dunk owned"),
            ("r6", self.ts_old, "general", "user3", "Adidas", "yeezy", None,
             "request", 0.65, "old yeezy request"),
            ("r7", self.ts_old, "general", "user4", "Puma", "suede", "blue / size 8",
             "satisfaction", 0.5, "old puma suede"),
            ("r8", self.ts_old, "general", "user5", "Puma", "suede", None,
             "neutral", 0.3, "old puma mention"),
        ]
        insert_processed_mentions(self.conn, mentions)


class TestDbCounts(TimeframeTestBase):
    def test_raw_count_all(self):
        self.assertEqual(raw_message_count(self.conn), 9)

    def test_raw_count_7d(self):
        count = raw_message_count(self.conn, since=self.since_7d)
        self.assertEqual(count, 3)

    def test_raw_count_30d(self):
        count = raw_message_count(self.conn, since=self.since_30d)
        self.assertEqual(count, 5)

    def test_mention_count_all(self):
        self.assertEqual(processed_mention_count(self.conn), 14)

    def test_mention_count_7d(self):
        count = processed_mention_count(self.conn, since=self.since_7d)
        self.assertEqual(count, 5)

    def test_mention_count_30d(self):
        count = processed_mention_count(self.conn, since=self.since_30d)
        self.assertEqual(count, 9)

    def test_mention_count_future(self):
        count = processed_mention_count(self.conn, since=self.since_future)
        self.assertEqual(count, 0)


class TestTrends(TimeframeTestBase):
    def test_channel_breakdown_all(self):
        result = channel_breakdown(self.conn)
        total = sum(r["total"] for r in result)
        self.assertEqual(total, 14)

    def test_channel_breakdown_7d(self):
        result = channel_breakdown(self.conn, since=self.since_7d)
        total = sum(r["total"] for r in result)
        self.assertEqual(total, 5)

    def test_daily_volume_all(self):
        result = daily_volume(self.conn)
        self.assertGreater(len(result), 0)

    def test_daily_volume_7d(self):
        all_days = daily_volume(self.conn)
        recent_days = daily_volume(self.conn, since=self.since_7d)
        self.assertLessEqual(len(recent_days), len(all_days))

    def test_top_items_by_intent_all(self):
        result = top_items_by_intent(self.conn, "request")
        total = sum(r["count"] for r in result)
        self.assertEqual(total, 7)  # all request mentions

    def test_top_items_by_intent_7d(self):
        result = top_items_by_intent(self.conn, "request", since=self.since_7d)
        total = sum(r["count"] for r in result)
        self.assertEqual(total, 3)  # only recent requests

    def test_sentiment_over_time_all(self):
        result = sentiment_over_time(self.conn)
        self.assertGreater(len(result), 0)

    def test_sentiment_over_time_7d(self):
        all_data = sentiment_over_time(self.conn)
        recent = sentiment_over_time(self.conn, since=self.since_7d)
        all_total = sum(r["count"] for r in all_data)
        recent_total = sum(r["count"] for r in recent)
        self.assertLessEqual(recent_total, all_total)

    def test_trending_items_returns_list(self):
        result = trending_items(self.conn, 10, since=self.since_30d)
        self.assertIsInstance(result, list)

    def test_trending_items_all(self):
        result = trending_items(self.conn, 10)
        self.assertIsInstance(result, list)


class TestSalesIntel(TimeframeTestBase):
    def test_unmet_demand_all(self):
        result = unmet_demand(self.conn, min_requests=2)
        self.assertIsInstance(result, list)

    def test_unmet_demand_7d(self):
        result = unmet_demand(self.conn, min_requests=1, since=self.since_7d)
        for item in result:
            self.assertGreater(item["demand_gap"], 0)

    def test_buyer_profiles_all(self):
        result = buyer_profiles(self.conn, min_activity=2)
        self.assertIsInstance(result, list)

    def test_buyer_profiles_7d(self):
        all_profiles = buyer_profiles(self.conn, min_activity=1)
        recent_profiles = buyer_profiles(self.conn, min_activity=1, since=self.since_7d)
        all_total = sum(p["total_mentions"] for p in all_profiles)
        recent_total = sum(p["total_mentions"] for p in recent_profiles)
        self.assertLessEqual(recent_total, all_total)

    def test_brand_cross_sell_all(self):
        result = brand_cross_sell(self.conn, min_overlap=1)
        self.assertIsInstance(result, list)

    def test_brand_cross_sell_7d(self):
        result = brand_cross_sell(self.conn, min_overlap=1, since=self.since_7d)
        self.assertIsInstance(result, list)

    def test_size_demand_all(self):
        result = size_demand(self.conn)
        self.assertIsInstance(result, list)

    def test_size_demand_7d(self):
        all_sizes = size_demand(self.conn)
        recent_sizes = size_demand(self.conn, since=self.since_7d)
        all_total = sum(s["total"] for s in all_sizes) if all_sizes else 0
        recent_total = sum(s["total"] for s in recent_sizes) if recent_sizes else 0
        self.assertLessEqual(recent_total, all_total)

    def test_color_demand_all(self):
        result = color_demand(self.conn)
        self.assertIsInstance(result, list)

    def test_inventory_recommendations_all(self):
        result = inventory_recommendations(self.conn)
        self.assertIsInstance(result, list)

    def test_inventory_recommendations_7d(self):
        result = inventory_recommendations(self.conn, since=self.since_7d)
        self.assertIsInstance(result, list)

    def test_monthly_seasonality_all(self):
        result = monthly_seasonality(self.conn)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_monthly_seasonality_7d(self):
        all_data = monthly_seasonality(self.conn)
        recent = monthly_seasonality(self.conn, since=self.since_7d)
        self.assertLessEqual(len(recent), len(all_data))

    def test_conversion_tracking_all(self):
        result = conversion_tracking(self.conn)
        self.assertIsInstance(result, list)

    def test_conversion_tracking_7d(self):
        result = conversion_tracking(self.conn, since=self.since_7d)
        self.assertIsInstance(result, list)


class TestScoring(TimeframeTestBase):
    def test_item_scores_all(self):
        scores = compute_item_scores(self.conn)
        self.assertGreater(len(scores), 0)

    def test_item_scores_7d(self):
        all_scores = compute_item_scores(self.conn)
        recent = compute_item_scores(self.conn, since=self.since_7d)
        all_total = sum(s["total_mentions"] for s in all_scores)
        recent_total = sum(s["total_mentions"] for s in recent)
        self.assertLessEqual(recent_total, all_total)

    def test_item_scores_future_empty(self):
        scores = compute_item_scores(self.conn, since=self.since_future)
        self.assertEqual(len(scores), 0)

    def test_brand_scores_all(self):
        scores = compute_brand_scores(self.conn)
        self.assertGreater(len(scores), 0)

    def test_brand_scores_7d(self):
        all_scores = compute_brand_scores(self.conn)
        recent = compute_brand_scores(self.conn, since=self.since_7d)
        all_total = sum(s["mentions"] for s in all_scores)
        recent_total = sum(s["mentions"] for s in recent)
        self.assertLessEqual(recent_total, all_total)

    def test_brand_scores_future_empty(self):
        scores = compute_brand_scores(self.conn, since=self.since_future)
        self.assertEqual(len(scores), 0)


class TestBackwardCompatibility(TimeframeTestBase):
    """Verify since=None returns same results as before (no parameter)."""

    def test_raw_count_compat(self):
        self.assertEqual(
            raw_message_count(self.conn),
            raw_message_count(self.conn, since=None),
        )

    def test_mention_count_compat(self):
        self.assertEqual(
            processed_mention_count(self.conn),
            processed_mention_count(self.conn, since=None),
        )

    def test_channel_breakdown_compat(self):
        self.assertEqual(
            channel_breakdown(self.conn),
            channel_breakdown(self.conn, since=None),
        )

    def test_item_scores_compat(self):
        a = compute_item_scores(self.conn)
        b = compute_item_scores(self.conn, since=None)
        self.assertEqual(len(a), len(b))
        for x, y in zip(a, b):
            self.assertEqual(x["brand"], y["brand"])
            self.assertEqual(x["total_mentions"], y["total_mentions"])

    def test_brand_scores_compat(self):
        a = compute_brand_scores(self.conn)
        b = compute_brand_scores(self.conn, since=None)
        self.assertEqual(len(a), len(b))


if __name__ == "__main__":
    unittest.main()
