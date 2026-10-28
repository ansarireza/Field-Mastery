import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline import radar, weekly


class MissingSectionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.today = dt.date(2026, 10, 28)
        self.cfg = {"radar": {"max_items": 12, "days_back": 7, "events": []}}
        self.news = [{"title": "Research funding call", "link": "https://example.org/call",
                      "date": self.today.isoformat(), "source": "Research fund"}]

    def run_radar(self, response):
        with patch.multiple(radar, DATA=self.root / "data", STATE=self.root / "state"), \
             patch.object(radar, "utc_today", return_value=self.today), \
             patch.object(radar, "gather", return_value=[dict(n) for n in self.news]), \
             patch.object(radar, "llm_json", return_value=response), \
             patch.object(radar, "log_week"):
            return radar.run(self.cfg, {"field_summary": "Urban ecosystems"})

    def test_object_and_bare_array_both_produce_news(self):
        item = {"i": 0, "title": "Research funding call", "urgency": 3}
        for response in ({"items": [item]}, [item]):
            with self.subTest(response=response):
                result = self.run_radar(response)
                self.assertEqual(result["items"][0]["url"], self.news[0]["link"])
                self.assertEqual(result["items"][0]["urgency"], 3)
                # Allow a second independent run against the same temporary state.
                (self.root / "state" / "seen_radar.json").unlink()

    def test_bad_entries_do_not_hide_valid_news(self):
        result = self.run_radar([[], None, {"i": -1}, {"i": 25}, {"i": 0, "urgency": "soon"}])
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["urgency"], 1)

    def test_wrong_response_shape_is_an_explicit_error(self):
        with self.assertRaisesRegex(ValueError, "list of news items"):
            self.run_radar({"items": "not a list"})

    def test_week_skips_wednesday_and_generates_on_sunday(self):
        with patch.object(weekly, "utc_today", return_value=self.today), \
             patch.object(weekly, "read_json", return_value={"date": "2026-10-25"}), \
             patch.object(weekly, "llm_json") as llm:
            self.assertIsNone(weekly.run({}, {}))
            llm.assert_not_called()
        sunday = dt.date(2026, 11, 1)
        with patch.object(weekly, "utc_today", return_value=sunday), \
             patch.object(weekly, "read_json", return_value={}), \
             patch.object(weekly, "llm_json", return_value={"themes": [], "learned": "", "next": []}):
            self.assertEqual(weekly.run({}, {})["date"], "2026-11-01")


if __name__ == "__main__":
    unittest.main()
