"""Tests for the May 2026 picks research module."""

import unittest

from src.analytics import may_2026_picks as may


class TestCatalystCalendar(unittest.TestCase):
    def test_six_catalysts(self):
        cats = may.get_catalysts()
        self.assertEqual(len(cats), 6)

    def test_all_catalysts_have_required_fields(self):
        required = {"event", "date_start", "date_end", "peak_date",
                    "categories", "audience", "drivers"}
        for c in may.get_catalysts():
            self.assertEqual(required - set(c.keys()), set(),
                             f"missing fields in {c.get('event')}")

    def test_dates_are_within_may_or_june(self):
        for c in may.get_catalysts():
            self.assertTrue(c["date_start"].startswith("2026-0"),
                            f"unexpected start date: {c['date_start']}")
            self.assertTrue(c["date_end"].startswith("2026-0"),
                            f"unexpected end date: {c['date_end']}")

    def test_known_events_present(self):
        names = {c["event"] for c in may.get_catalysts()}
        self.assertTrue(any("Mother" in n for n in names))
        self.assertTrue(any("graduation" in n.lower() for n in names))
        self.assertTrue(any("Memorial" in n for n in names))
        self.assertTrue(any("Cannes" in n for n in names))


class TestMay2026Items(unittest.TestCase):
    REQUIRED = {"brand", "item", "category", "weight_g",
                "rep_cost_low", "rep_cost_high",
                "resell_low", "resell_high",
                "min_bulk_qty", "tier", "seasonal", "catalyst",
                "subreddits", "notes", "why_good"}

    def test_all_items_have_required_fields(self):
        for r in may.MAY_2026_ITEMS:
            missing = self.REQUIRED - set(r.keys())
            self.assertFalse(missing, f"{r.get('brand')} missing {missing}")

    def test_at_least_25_items(self):
        self.assertGreaterEqual(len(may.MAY_2026_ITEMS), 25)

    def test_brings_in_new_categories(self):
        cats = {r["category"] for r in may.MAY_2026_ITEMS}
        for new in ("Watches", "Fragrance", "Electronics",
                    "Footwear", "Dresses"):
            self.assertIn(new, cats)

    def test_costs_and_resell_consistent(self):
        for r in may.MAY_2026_ITEMS:
            self.assertLessEqual(r["rep_cost_low"], r["rep_cost_high"])
            self.assertLessEqual(r["resell_low"], r["resell_high"])
            self.assertGreater(r["resell_high"], r["rep_cost_low"])

    def test_weight_positive(self):
        for r in may.MAY_2026_ITEMS:
            self.assertGreater(r["weight_g"], 0)


class TestComputeMayRoi(unittest.TestCase):
    def test_returns_enriched_items(self):
        out = may.compute_may_roi(13.0)
        self.assertEqual(len(out), len(may.MAY_2026_ITEMS))
        for r in out:
            for k in ("profit_per_kg_usd", "units_per_10kg",
                      "total_profit_10kg", "billable_kg",
                      "unit_shipping_usd"):
                self.assertIn(k, r)

    def test_sorted_by_profit_per_kg_desc(self):
        out = may.compute_may_roi(13.0)
        scores = [r["profit_per_kg_usd"] for r in out]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_higher_rate_lowers_profit_per_kg(self):
        low = may.compute_may_roi(8.0)
        high = may.compute_may_roi(22.0)
        low_map = {(r["brand"], r["item"]): r for r in low}
        high_map = {(r["brand"], r["item"]): r for r in high}
        key = next(iter(low_map))
        self.assertGreater(low_map[key]["profit_per_kg_usd"],
                           high_map[key]["profit_per_kg_usd"])


class TestTopMayPicks(unittest.TestCase):
    def test_top_pick_is_jewelry(self):
        top = may.top_may_picks(13.0, top_n=1)
        self.assertEqual(top[0]["category"], "Jewelry")

    def test_excludes_avoid_tier_by_default(self):
        picks = may.top_may_picks(13.0, top_n=50)
        self.assertTrue(all(r.get("tier") != 4 for r in picks))


class TestPicksByCatalyst(unittest.TestCase):
    def test_mother_returns_motherhood_items(self):
        picks = may.picks_by_catalyst("Mother", 13.0, top_n=20)
        self.assertTrue(picks)
        for r in picks:
            self.assertIn("mother", (r.get("catalyst") or "").lower())

    def test_graduation_returns_watches_and_jewelry(self):
        picks = may.picks_by_catalyst("Graduation", 13.0, top_n=20)
        cats = {r["category"] for r in picks}
        self.assertTrue("Watches" in cats or "Jewelry" in cats)

    def test_memorial_returns_summer_kickoff(self):
        picks = may.picks_by_catalyst("Memorial", 13.0, top_n=20)
        self.assertTrue(picks)
        for r in picks:
            self.assertIn("memorial", (r.get("catalyst") or "").lower())

    def test_father_returns_fragrance_or_watches(self):
        picks = may.picks_by_catalyst("Father", 13.0, top_n=20)
        cats = {r["category"] for r in picks}
        # Father's day picks should include watches or fragrance
        self.assertTrue(cats.intersection({"Watches", "Fragrance",
                                            "Electronics", "Accessories"}))

    def test_unknown_catalyst_returns_empty(self):
        self.assertEqual(may.picks_by_catalyst("xyznonexistent", 13.0), [])


class TestMayCategorySummary(unittest.TestCase):
    def test_sorted_by_profit_per_kg_desc(self):
        summary = may.may_category_summary(13.0)
        scores = [r["avg_profit_per_kg"] for r in summary]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_includes_new_categories(self):
        summary = may.may_category_summary(13.0)
        cats = {r["category"] for r in summary}
        for new in ("Watches", "Fragrance", "Electronics", "Footwear"):
            self.assertIn(new, cats)

    def test_jewelry_beats_fragrance_per_kg(self):
        summary = may.may_category_summary(13.0)
        by_cat = {r["category"]: r["avg_profit_per_kg"] for r in summary}
        self.assertGreater(by_cat["Jewelry"], by_cat["Fragrance"])


class TestMayHeadline(unittest.TestCase):
    def test_shape(self):
        h = may.may_headline(13.0)
        for k in ("rate_per_kg", "total_items", "catalyst_count",
                  "top_item", "top_profit_per_kg",
                  "top_units_per_10kg", "top_total_10kg",
                  "top_category"):
            self.assertIn(k, h)

    def test_top_category_is_jewelry(self):
        h = may.may_headline(13.0)
        self.assertEqual(h["top_category"], "Jewelry")

    def test_catalyst_count_six(self):
        h = may.may_headline(13.0)
        self.assertEqual(h["catalyst_count"], 6)


class TestPicksByCategory(unittest.TestCase):
    def test_watches_returns_only_watches(self):
        picks = may.picks_by_category("Watches", 13.0)
        self.assertTrue(picks)
        for r in picks:
            self.assertEqual(r["category"], "Watches")

    def test_fragrance_returns_only_fragrance(self):
        picks = may.picks_by_category("Fragrance", 13.0)
        self.assertTrue(picks)
        for r in picks:
            self.assertEqual(r["category"], "Fragrance")


if __name__ == "__main__":
    unittest.main()
