import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SiteUiContractTests(unittest.TestCase):
    def test_catalog_snapshot_includes_total_runtime(self) -> None:
        schema = (ROOT / "railway" / "catalog_schema.sql").read_text(encoding="utf-8")
        self.assertIn("jsonb_build_object('duration_seconds', r.duration_seconds)", schema)

    def test_scoreboard_has_runtime_column_and_bucket_filter(self) -> None:
        page = (ROOT / "docs" / "internal.html").read_text(encoding="utf-8")
        self.assertIn('title="Total wall-clock runtime">Total runtime</th>', page)
        for bucket in (108, 132, 264):
            self.assertIn(f'data-runtime="{bucket}"', page)
        self.assertIn("RUNTIME_TOLERANCE_MINUTES = 2", page)
        self.assertIn("runtimeBucket(seconds)", page)

    def test_event_log_merges_and_selects_turn_rows(self) -> None:
        script = (ROOT / "docs" / "static" / "js" / "log.js").read_text(encoding="utf-8")
        styles = (ROOT / "docs" / "static" / "css" / "app.css").read_text(encoding="utf-8")
        self.assertIn('class="turn-group"', script)
        self.assertIn("group.cell.rowSpan += 1", script)
        self.assertIn('row.classList.add("selected-turn")', script)
        self.assertIn("table.log tr.selected-turn", styles)


if __name__ == "__main__":
    unittest.main()
