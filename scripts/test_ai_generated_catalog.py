import json
from pathlib import Path
import unittest

from build_ai_generated_catalog import CATEGORY, MANIFEST_PATH, research_entries


ROOT = Path(__file__).resolve().parents[1]


class AiGeneratedCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.ai_entries = [entry for entry in cls.manifest if entry.get("category") == CATEGORY]

    def test_all_research_games_are_published_once(self):
        expected = research_entries()
        metadata_count = len(list((ROOT / "research" / "games").glob("*.json")))
        self.assertEqual(metadata_count, len(expected))
        self.assertEqual(expected, self.ai_entries)
        ids = [entry["id"] for entry in self.manifest]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_entry_has_browser_artifacts(self):
        for entry in self.ai_entries:
            source = ROOT / "docs" / "static" / "games" / "src" / entry["id"] / entry["src_file"]
            thumbnail = ROOT / "docs" / "static" / "img" / "games" / f"{entry['id']}.png"
            self.assertTrue(source.is_file(), entry["id"])
            self.assertTrue(thumbnail.is_file(), entry["id"])


if __name__ == "__main__":
    unittest.main()
