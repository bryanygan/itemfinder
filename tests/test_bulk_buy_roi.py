"""Tests for the bulk-buy ROI analysis module."""

import unittest

from src.analytics import bulk_buy_roi as roi


class TestComputeRoi(unittest.TestCase):
    def test_returns_enriched_items(self):
        out = roi.compute_roi(13.0)
        self.assertTrue(out)
        for r in out:
            for k in ("billable_kg", "unit_shipping_usd", "unit_profit_usd",
                      "margin_pct", "profit_per_kg_usd", "units_per_10kg",
                      "total_profit_10kg", "purchase_link"):
                self.assertIn(k, r)

    def test_sorted_by_profit_per_kg_desc(self):
        out = roi.compute_roi(13.0)
        scores = [r["profit_per_kg_usd"] for r in out]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_shipping_cost_scales_with_rate(self):
        low = roi.compute_roi(5.0)
        high = roi.compute_roi(25.0)
        # Match first by (brand,item) since sort order may shift
        low_map = {(r["brand"], r["item"]): r for r in low}
        high_map = {(r["brand"], r["item"]): r for r in high}
        sample_key = next(iter(low_map))
        self.assertLess(low_map[sample_key]["unit_shipping_usd"],
                        high_map[sample_key]["unit_shipping_usd"])
        # Profit per kg should be lower at the higher rate
        self.assertGreater(low_map[sample_key]["profit_per_kg_usd"],
                           high_map[sample_key]["profit_per_kg_usd"])

    def test_volumetric_multiplier_penalises_sneakers(self):
        out = roi.compute_roi(13.0)
        # Compare a Jewelry item vs a Sneakers item of similar weight class:
        # volumetric multiplier should make sneakers' billable_kg higher than
        # their raw weight in kg
        for r in out:
            if r["category"] == "Sneakers":
                self.assertGreater(r["billable_kg"], r["weight_g"] / 1000.0)
            elif r["category"] == "Jewelry":
                self.assertAlmostEqual(
                    r["billable_kg"], r["weight_g"] / 1000.0, places=3,
                )

    def test_jewelry_beats_sneakers_on_profit_per_kg(self):
        out = roi.compute_roi(13.0)
        jewelry = [r for r in out if r["category"] == "Jewelry"]
        sneakers = [r for r in out if r["category"] == "Sneakers"
                    and r.get("tier") == 4]
        self.assertTrue(jewelry)
        self.assertTrue(sneakers)
        best_jewelry = max(r["profit_per_kg_usd"] for r in jewelry)
        best_sneaker = max(r["profit_per_kg_usd"] for r in sneakers)
        # Expect at least a 10x gap (actual is ~50x)
        self.assertGreater(best_jewelry, best_sneaker * 10)

    def test_purchase_link_populated_for_known_brands(self):
        out = roi.compute_roi(13.0)
        ch = [r for r in out if r["brand"] == "Chrome Hearts"]
        self.assertTrue(ch)
        self.assertTrue(any(r["purchase_link"] for r in ch))


class TestTopRoiPicks(unittest.TestCase):
    def test_default_excludes_avoid_tier(self):
        picks = roi.top_roi_picks(13.0, top_n=20)
        self.assertTrue(all(r.get("tier") != 4 for r in picks))

    def test_include_avoid_when_flag_off(self):
        picks_with = roi.top_roi_picks(13.0, top_n=50, exclude_avoid=False)
        self.assertTrue(any(r.get("tier") == 4 for r in picks_with))

    def test_top_pick_is_chrome_hearts_at_default_rate(self):
        top = roi.top_roi_picks(13.0, top_n=1)
        self.assertEqual(top[0]["brand"], "Chrome Hearts")


class TestHeadlineFindings(unittest.TestCase):
    def test_shape(self):
        h = roi.headline_findings(13.0)
        self.assertEqual(h["rate_per_kg"], 13.0)
        self.assertGreater(h["best_profit_per_kg"], 0)
        self.assertGreater(h["best_units_per_10kg"], 0)
        self.assertGreater(h["best_total_profit_10kg"], 0)

    def test_worst_bulk_item_from_avoid_tier(self):
        h = roi.headline_findings(13.0)
        avoid_names = {
            f"{r['brand']} {r['item']}"
            for r in roi.BULK_BUY_ITEMS if r.get("tier") == 4
        }
        self.assertIn(h["worst_bulk_item"], avoid_names)


class TestCategorySummary(unittest.TestCase):
    def test_returns_every_category(self):
        summary = roi.category_summary(13.0)
        cats = {r["category"] for r in summary}
        # At least the core categories must appear
        for expected in ("Jewelry", "Accessories", "Tops", "Sneakers"):
            self.assertIn(expected, cats)

    def test_sorted_by_avg_profit_per_kg_desc(self):
        summary = roi.category_summary(13.0)
        scores = [r["avg_profit_per_kg"] for r in summary]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_jewelry_is_top_category(self):
        summary = roi.category_summary(13.0)
        self.assertEqual(summary[0]["category"], "Jewelry")


class TestRoiByTier(unittest.TestCase):
    def test_returns_all_four_tiers(self):
        by_tier = roi.roi_by_tier(13.0)
        for t in (1, 2, 3, 4):
            self.assertIn(t, by_tier)

    def test_tier1_is_light(self):
        by_tier = roi.roi_by_tier(13.0)
        for r in by_tier[1]:
            self.assertLess(r["weight_g"], 300)


class TestSummerPicks(unittest.TestCase):
    def test_summer_only_returns_summer_tagged_items(self):
        picks = roi.summer_only_picks(13.0, top_n=20)
        self.assertTrue(picks)
        for r in picks:
            self.assertEqual(r.get("seasonal"), "summer")

    def test_summer_only_excludes_avoid_tier(self):
        picks = roi.summer_only_picks(13.0, top_n=30)
        self.assertTrue(all(r.get("tier") != 4 for r in picks))

    def test_summer_picks_combines_all_season(self):
        # Use a large enough top_n that both functions return their full
        # filtered sets — order differs since all-season items rank high.
        strict = roi.summer_only_picks(13.0, top_n=200)
        combined = roi.summer_picks(13.0, top_n=200, include_all_season=True)
        strict_keys = {(r["brand"], r["item"]) for r in strict}
        combined_keys = {(r["brand"], r["item"]) for r in combined}
        self.assertTrue(strict_keys.issubset(combined_keys))
        self.assertGreater(len(combined_keys), len(strict_keys))

    def test_summer_picks_sorted_by_profit_per_kg(self):
        picks = roi.summer_only_picks(13.0, top_n=30)
        scores = [r["profit_per_kg_usd"] for r in picks]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_seasonal_split_keys(self):
        split = roi.seasonal_split(13.0)
        self.assertIn("summer", split)
        self.assertIn("all-season", split)

    def test_summer_sunglasses_outrank_summer_slides(self):
        # Sanity: highest-margin summer item (sunglasses) beats slides
        picks = roi.summer_only_picks(13.0, top_n=30)
        ppk = {(r["brand"], r["item"]): r["profit_per_kg_usd"] for r in picks}
        sg = ppk[("Chrome Hearts", "Silver Sunglasses (Boink! Summer)")]
        slide = ppk[("Adidas", "Adilette Slides")]
        self.assertGreater(sg, slide)


class TestBulkBuyItemsDataIntegrity(unittest.TestCase):
    REQUIRED = {
        "brand", "item", "category", "weight_g",
        "rep_cost_low", "rep_cost_high",
        "resell_low", "resell_high",
        "min_bulk_qty", "tier", "notes", "why_good",
    }

    def test_every_item_has_required_fields(self):
        for r in roi.BULK_BUY_ITEMS:
            missing = self.REQUIRED - set(r.keys())
            self.assertFalse(missing, f"{r.get('brand')} missing {missing}")

    def test_costs_and_resell_consistent(self):
        for r in roi.BULK_BUY_ITEMS:
            self.assertLessEqual(r["rep_cost_low"], r["rep_cost_high"])
            self.assertLessEqual(r["resell_low"], r["resell_high"])
            # Resell should generally exceed rep cost (at least on the high end)
            self.assertGreater(r["resell_high"], r["rep_cost_low"])

    def test_weight_positive(self):
        for r in roi.BULK_BUY_ITEMS:
            self.assertGreater(r["weight_g"], 0)

    def test_tiers_in_range(self):
        for r in roi.BULK_BUY_ITEMS:
            self.assertIn(r["tier"], (1, 2, 3, 4))


if __name__ == "__main__":
    unittest.main()
