import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline import briefing, common, learn, radar, weekly


class ResearchCompanionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.day = dt.date(2026, 10, 28)

    def test_legal_stage_requires_primary_source_and_exact_evidence(self):
        for primary, quote, expected in [(False, "adopted", "unknown"), (True, "invented quote", "unknown"), (True, "adopted", "adopted")]:
            with self.subTest(primary=primary, quote=quote), \
                 patch.multiple(radar, DATA=self.root / "data", STATE=self.root / "state"), \
                 patch.object(radar, "utc_today", return_value=self.day), \
                 patch.object(radar, "gather", return_value=[{"title": "New policy adopted", "desc": "", "link": "https://official.example/policy", "source": "Official", "date": self.day.isoformat(), "primary": primary, "scope": "EU"}]), \
                 patch.object(radar, "llm_json", return_value={"items": [{"i": 0, "status": "adopted", "status_evidence": quote}]}), \
                 patch.object(radar, "log_week"):
                result = radar.run({"radar": {"events": []}}, {})
                self.assertEqual(result["items"][0]["status"], expected)
                self.assertEqual(result["items"][0]["url"], "https://official.example/policy")
                (self.root / "state" / "seen_radar.json").unlink()

    def test_feed_outage_is_not_reported_as_no_news(self):
        with patch.multiple(radar, STATE=self.root, MOCK=False), \
             patch.object(radar, "http_text", side_effect=RuntimeError("unreachable")):
            with self.assertRaisesRegex(RuntimeError, "All Radar sources failed"):
                radar.gather({}, {"radar": {"official_feeds": [{"url": "https://example.org/feed"}]}})

    def test_region_interleaving_and_official_domain_check(self):
        def feed(url, **kwargs):
            scope = "German" if "germany" in url else "European"
            return "<rss><channel>" + "".join(f"<item><title>{scope} news {i}</title><link>https://germany.example/story{i}</link><pubDate>Wed, 28 Oct 2026 00:00:00 GMT</pubDate></item>" for i in range(3)) + "</channel></rss>"
        with patch.multiple(radar, STATE=self.root, MOCK=False), patch.object(radar, "utc_today", return_value=self.day), patch.object(radar, "http_text", side_effect=feed):
            result = radar.gather({}, {"radar": {"official_feeds": [
                {"url": "https://germany.example/feed", "scope": "Germany"},
                {"url": "https://eu.example/feed", "scope": "EU"}]}})
        self.assertEqual([n["scope"] for n in result[:4]], ["Germany", "EU", "Germany", "EU"])
        self.assertTrue(result[0]["primary"])
        self.assertFalse(result[1]["primary"])

    def test_first_week_review_does_not_wait_for_sunday(self):
        with patch.object(weekly, "utc_today", return_value=self.day), \
             patch.object(weekly, "read_json", return_value={}), \
             patch.object(weekly, "llm_json", return_value={"themes": [], "next": []}):
            result = weekly.run({}, {})
        self.assertTrue(result["partial"])

    def test_briefing_preserves_sources_and_rejects_invented_source_indices(self):
        data, state = self.root / "data", self.root / "state"
        common.write_json(data / "today.json", {"items": [{"id": "P1", "title": "Real paper", "relevance": 5,
                          "source": {"url": "https://doi.org/real", "date": "2026-10-27"}}]})
        common.write_json(state / "radar_history.json", [{"id": "N1", "title": "Real news", "date": "2026-10-27", "url": "https://example.org/real"}])
        response = {"world": [{"source_i": -1}, {"source_i": 999}, {"source_i": 0, "what": "Source-backed update", "source": {"url": "https://fake.example"}}],
                    "reading": {"why": "Read methods", "questions": ["How was it validated?"], "url": "https://fake.example"}}
        with patch.multiple(briefing, DATA=data, STATE=state), \
             patch.object(briefing, "utc_today", return_value=self.day), \
             patch.object(briefing, "llm_json", return_value=response) as llm:
            result = briefing.run({}, {})
            self.assertEqual(len(result["world"]), 1)
            self.assertEqual(result["world"][0]["source"]["url"], "https://example.org/real")
            self.assertEqual(result["reading"]["source"]["url"], "https://doi.org/real")
            common.write_json(data / "briefing.json", result)
            self.assertEqual(briefing.run({}, {}), result)
            self.assertEqual(llm.call_count, 1)

    def test_learning_stage_is_progress_not_claimed_mastery(self):
        self.assertEqual(learn.learning_stage(0, {}), "Foundation")
        self.assertEqual(learn.learning_stage(20, {}), "Developing")
        self.assertEqual(learn.learning_stage(60, {}), "Advanced")

    def test_array_responses_are_normalised_and_wrong_shapes_retry(self):
        with patch.object(common, "MOCK", False), patch.object(common, "load_config", return_value={}), \
             patch.object(common, "_gemini", return_value=[{"q": "Question"}]):
            self.assertEqual(common.llm_json("test", mock={"questions": []}), {"questions": [{"q": "Question"}]})
        with patch.object(common, "MOCK", False), patch.object(common, "load_config", return_value={}), \
             patch.object(common, "_gemini", side_effect=["invalid", {"ok": True}]) as call:
            self.assertEqual(common.llm_json("test", mock={"ok": False}), {"ok": True})
            self.assertEqual(call.call_count, 2)

    def test_full_mock_digest_writes_every_section_without_touching_live_data(self):
        data, state = self.root / "data", self.root / "state"
        env = {**os.environ, "FM_DATA": str(data), "FM_STATE": str(state)}
        result = subprocess.run([sys.executable, "-m", "pipeline.build_digest", "--mock"], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        meta = json.loads((data / "meta.json").read_text())
        self.assertEqual(meta["errors"], {}, result.stderr)
        for name in ["today", "radar", "learn", "people", "tools", "debates", "defense", "weekly", "briefing", "map"]:
            self.assertTrue((data / f"{name}.json").exists(), name)
        paper = json.loads((data / "today.json").read_text())["items"][0]
        self.assertTrue(paper["critical"]["question"])
        self.assertTrue(paper["thesis"]["why"])


if __name__ == "__main__":
    unittest.main()
