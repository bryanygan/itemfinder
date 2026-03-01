"""Tests for intent classification and entity extraction."""

import unittest

from src.process.classify import classify_intent, classify_intent_from_channel
from src.process.extract import extract_all, extract_brand, extract_item, extract_variant
from src.process.normalize import is_spam_or_empty, normalize_text


class TestNormalization(unittest.TestCase):
    def test_removes_urls(self):
        text = "check this out https://example.com/foo nice"
        self.assertNotIn("http", normalize_text(text))

    def test_removes_mentions(self):
        self.assertEqual(normalize_text("hey <@123456> sup"), "hey sup")

    def test_lowercases(self):
        self.assertEqual(normalize_text("HELLO WORLD"), "hello world")

    def test_collapses_whitespace(self):
        self.assertEqual(normalize_text("too   many   spaces"), "too many spaces")

    def test_spam_detection(self):
        self.assertTrue(is_spam_or_empty(""))
        self.assertTrue(is_spam_or_empty("a"))
        self.assertTrue(is_spam_or_empty("aaaa"))  # repetitive
        self.assertFalse(is_spam_or_empty("looking for sp5der hoodie"))


class TestClassification(unittest.TestCase):
    def test_request_intent(self):
        intent, score = classify_intent("looking for sp5der hoodie size l")
        self.assertEqual(intent, "request")
        self.assertGreater(score, 0.0)

    def test_wtb_intent(self):
        intent, score = classify_intent("wtb chrome hearts ring")
        self.assertEqual(intent, "request")

    def test_satisfaction_intent(self):
        intent, score = classify_intent("these are fire bro so good")
        self.assertEqual(intent, "satisfaction")

    def test_regret_intent(self):
        intent, score = classify_intent("should've bought the black ones missed out")
        self.assertEqual(intent, "regret")

    def test_ownership_intent(self):
        intent, score = classify_intent("just copped the gallery dept tee")
        self.assertEqual(intent, "ownership")

    def test_neutral(self):
        intent, score = classify_intent("hello everyone")
        self.assertEqual(intent, "neutral")

    def test_channel_boost_wtb(self):
        intent, score = classify_intent_from_channel("wtb", "sp5der hoodie large")
        self.assertEqual(intent, "request")
        self.assertGreater(score, 0.5)

    def test_channel_boost_pickups(self):
        intent, score = classify_intent_from_channel("latest-pickups", "new gallery dept tee")
        self.assertEqual(intent, "ownership")


class TestExtraction(unittest.TestCase):
    def test_brand_sp5der(self):
        self.assertEqual(extract_brand("sp5der hoodie size l"), "Sp5der")

    def test_brand_chrome_hearts(self):
        self.assertEqual(extract_brand("chrome hearts ring black"), "Chrome Hearts")

    def test_brand_alias_ch(self):
        self.assertEqual(extract_brand("need a ch ring"), "Chrome Hearts")

    def test_brand_alias_lv(self):
        self.assertEqual(extract_brand("looking for lv bag"), "Louis Vuitton")

    def test_brand_gallery_dept(self):
        self.assertEqual(extract_brand("gallery dept tee size l"), "Gallery Dept")

    def test_brand_none(self):
        self.assertIsNone(extract_brand("hello world"))

    def test_item_hoodie(self):
        self.assertEqual(extract_item("sp5der hoodie size l"), "hoodie")

    def test_item_tee(self):
        self.assertEqual(extract_item("gallery dept tee"), "tee")

    def test_item_ring(self):
        self.assertEqual(extract_item("chrome hearts ring"), "ring")

    def test_item_shoes(self):
        self.assertEqual(extract_item("looking for some new shoes"), "shoes")

    def test_no_false_positive_hat(self):
        """'hat' should not match inside 'that', 'what', 'chat'."""
        self.assertIsNone(extract_item("what is that"))
        self.assertIsNone(extract_item("i think that is cool"))
        self.assertIsNone(extract_item("check the chat"))

    def test_hat_standalone(self):
        self.assertEqual(extract_item("looking for a hat"), "hat")

    def test_canonical_normalization(self):
        self.assertEqual(extract_item("i love hoodies"), "hoodie")
        self.assertEqual(extract_item("nice sneakers"), "shoes")
        self.assertEqual(extract_item("some hats"), "hat")

    def test_variant_color_and_size(self):
        variant = extract_variant("black hoodie size l")
        self.assertIn("black", variant)
        self.assertIn("size L", variant)

    def test_variant_shoe_size(self):
        variant = extract_variant("jordan 1 size 13")
        self.assertIn("size 13", variant)

    def test_extract_all(self):
        result = extract_all("looking for sp5der hoodie black size l")
        self.assertEqual(result["brand"], "Sp5der")
        self.assertEqual(result["item"], "hoodie")
        self.assertIsNotNone(result["variant"])


if __name__ == "__main__":
    unittest.main()
