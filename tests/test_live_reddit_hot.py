"""Tests for the live Reddit hot-threads cache module.

Network fetches are stubbed with a fake urlopen — no actual HTTP is made.
"""

import io
import json
import tempfile
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from src.analytics import live_reddit_hot as lrh


def _sample_reddit_payload(titles: list[str]) -> bytes:
    children = []
    for i, t in enumerate(titles):
        children.append({"data": {
            "id": f"id{i}",
            "title": t,
            "author": "u_test",
            "link_flair_text": "W2C" if i % 2 == 0 else "QC",
            "score": 100 + i,
            "upvote_ratio": 0.95,
            "num_comments": 5 + i,
            "permalink": f"/r/FashionReps/comments/id{i}/",
            "url": f"https://reddit.com/r/FashionReps/id{i}",
            "created_utc": 1_700_000_000 + i,
            "is_self": True,
            "selftext": f"body for {t}",
            "stickied": False,
            "over_18": False,
        }})
    payload = {"data": {"children": children}}
    return json.dumps(payload).encode("utf-8")


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestFetchHotThreads(unittest.TestCase):
    def test_parses_titles_and_flairs(self):
        body = _sample_reddit_payload(["W2C Jordan 1 OW", "QC Dunk Low"])
        with patch.object(urllib.request, "urlopen",
                          return_value=_FakeResponse(body)):
            posts = lrh.fetch_hot_threads("FashionReps", limit=10)
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0]["title"], "W2C Jordan 1 OW")
        self.assertEqual(posts[0]["flair"], "W2C")
        self.assertEqual(posts[1]["flair"], "QC")
        self.assertTrue(posts[0]["permalink"].startswith("https://www.reddit.com"))

    def test_skips_stickied_and_nsfw(self):
        payload = {"data": {"children": [
            {"data": {"id": "x1", "title": "pinned", "stickied": True,
                      "over_18": False, "created_utc": 1, "is_self": True}},
            {"data": {"id": "x2", "title": "nsfw", "stickied": False,
                      "over_18": True, "created_utc": 1, "is_self": True}},
            {"data": {"id": "x3", "title": "ok", "stickied": False,
                      "over_18": False, "created_utc": 1, "is_self": True}},
        ]}}
        body = json.dumps(payload).encode("utf-8")
        with patch.object(urllib.request, "urlopen",
                          return_value=_FakeResponse(body)):
            posts = lrh.fetch_hot_threads("FashionReps")
        self.assertEqual([p["title"] for p in posts], ["ok"])

    def test_network_failure_returns_empty(self):
        def raise_urlerr(*a, **kw):
            raise urllib.error.URLError("boom")
        with patch.object(urllib.request, "urlopen", side_effect=raise_urlerr):
            posts = lrh.fetch_hot_threads("FashionReps")
        self.assertEqual(posts, [])

    def test_malformed_json_returns_empty(self):
        with patch.object(urllib.request, "urlopen",
                          return_value=_FakeResponse(b"not json")):
            posts = lrh.fetch_hot_threads("FashionReps")
        self.assertEqual(posts, [])


class TestCacheRoundTrip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "cache.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_empty_cache_returns_stale(self):
        out = lrh.get_cached_hot("FashionReps", path=self.path)
        self.assertEqual(out["posts"], [])
        self.assertTrue(out["stale"])

    def test_refresh_then_read(self):
        body = _sample_reddit_payload(["Hot one", "Hot two"])
        with patch.object(urllib.request, "urlopen",
                          return_value=_FakeResponse(body)):
            summary = lrh.refresh_hot_cache(
                subreddits=["FashionReps"], path=self.path, sleep_between=0,
            )
        self.assertEqual(summary, {"FashionReps": 2})
        out = lrh.get_cached_hot("FashionReps", path=self.path)
        self.assertEqual(out["count"], 2)
        self.assertEqual(out["posts"][0]["title"], "Hot one")
        self.assertFalse(out["stale"])

    def test_stale_detected_after_ttl(self):
        old = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        cache = {
            "fetched_at": old,
            "subreddits": {"FashionReps": {
                "fetched_at": old,
                "posts": [{"title": "old post", "permalink": ""}],
            }},
        }
        self.path.write_text(json.dumps(cache), encoding="utf-8")
        out = lrh.get_cached_hot("FashionReps", path=self.path)
        self.assertTrue(out["stale"])
        self.assertEqual(out["count"], 1)

    def test_corrupt_cache_returns_empty(self):
        self.path.write_text("{not json", encoding="utf-8")
        out = lrh.get_cached_hot("FashionReps", path=self.path)
        self.assertEqual(out["posts"], [])
        self.assertTrue(out["stale"])

    def test_cache_status_summary(self):
        body = _sample_reddit_payload(["a", "b", "c"])
        with patch.object(urllib.request, "urlopen",
                          return_value=_FakeResponse(body)):
            lrh.refresh_hot_cache(
                subreddits=["FashionReps", "Repsneakers"],
                path=self.path, sleep_between=0,
            )
        status = lrh.cache_status(path=self.path)
        self.assertEqual(status["subreddit_count"], 2)
        self.assertEqual(status["total_posts"], 6)
        self.assertFalse(status["stale"])


class TestStaleDetection(unittest.TestCase):
    def test_none_is_stale(self):
        self.assertTrue(lrh._is_stale(None))

    def test_fresh_not_stale(self):
        recent = datetime.now(timezone.utc).isoformat()
        self.assertFalse(lrh._is_stale(recent, ttl_hours=6))

    def test_invalid_iso_is_stale(self):
        self.assertTrue(lrh._is_stale("not-a-date"))


if __name__ == "__main__":
    unittest.main()
