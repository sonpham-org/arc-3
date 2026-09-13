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

    def test_viewer_has_turn_links_and_debugger_handoff(self) -> None:
        viewer = (ROOT / "docs" / "viewer.html").read_text(encoding="utf-8")
        main = (ROOT / "docs" / "static" / "js" / "main.js").read_text(encoding="utf-8")
        debugger = (ROOT / "docs" / "arc-debugger.html").read_text(encoding="utf-8")
        self.assertIn('id="share-turn"', viewer)
        self.assertIn('id="rt-debugger"', viewer)
        self.assertIn("parseViewerHash", main)
        self.assertIn("turn: frame.analysis_step", main)
        self.assertIn("ARC DEBUGGER", debugger)
        self.assertIn("Resume this turn on both Sparks", debugger)
        self.assertIn('id="context-so-far"', debugger)
        self.assertIn('readonly', debugger)
        self.assertIn('id="temperature" type="number" min="0" max="2" step="0.1" value="1"', debugger)
        self.assertIn('id="top-p" type="number" min="0.01" max="1" step="0.01" value="0.95"', debugger)
        self.assertIn('id="top-k" type="number" min="0" max="100" step="1" value="20"', debugger)

    def test_debugger_uses_authenticated_same_origin_relay(self) -> None:
        page = (ROOT / "docs" / "arc-debugger.html").read_text(encoding="utf-8")
        script = (ROOT / "docs" / "static" / "js" / "arc-debugger.js").read_text(encoding="utf-8")
        entrypoint = (ROOT / "railway" / "entrypoint.sh").read_text(encoding="utf-8")
        self.assertIn('data-debugger-api="/api/v1/debugger"', page)
        self.assertNotIn("tail1528b6.ts.net", page)
        self.assertIn("Railway's ARC tailnet relay is offline", script)
        self.assertIn('/v1/preview', script)
        self.assertIn("--tun=userspace-networking", entrypoint)
        self.assertIn('/srv/data/.tailscale', entrypoint)


if __name__ == "__main__":
    unittest.main()
