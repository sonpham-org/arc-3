import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.export_execution_trace import assign_gameplay_slots, call_phase_summary, gameplay_concurrency, section_phase


class ExecutionTraceTopologyTests(unittest.TestCase):
    def test_phase_summary_preserves_semantic_order(self):
        step = {
            "context": {"sections": [{"source": "request", "content": "system + user"}]},
            "localContext": {
                "sections": [
                    {"label": "SYSTEM PROMPT", "kind": "system", "content": "system"},
                    {"label": "USER PROMPT", "kind": "tool", "content": "user"},
                    {"label": "THINKING", "kind": "reasoning", "content": "think"},
                    {"label": "TOOL CALL: python", "kind": "tool_call", "content": "call"},
                    {"label": "TOOL RESULT: python", "kind": "tool", "content": "result"},
                    {"label": "COMPACTION", "kind": "compaction", "content": "summary"},
                ]
            },
        }
        self.assertEqual(
            ["input", "reasoning", "tool_call", "input", "compact"],
            [phase["phase"] for phase in call_phase_summary(step)],
        )
        self.assertEqual("input", section_phase({"label": "TOOL RESULT: python", "kind": "tool"}))

    def test_slots_reuse_a_worker_only_after_its_game_finishes(self):
        started = datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc)
        ended = datetime(2026, 8, 22, 10, 10, tzinfo=timezone.utc)
        benchmark = {
            "game_runs": [
                {"game_id": "g1", "started_at": "2026-08-22T10:00:00Z", "ended_at": "2026-08-22T10:04:00Z"},
                {"game_id": "g2", "started_at": "2026-08-22T10:00:01Z", "ended_at": "2026-08-22T10:08:00Z"},
                {"game_id": "g3", "started_at": "2026-08-22T10:04:01Z", "ended_at": "2026-08-22T10:09:00Z"},
            ]
        }
        mapping, games = assign_gameplay_slots(benchmark, started, ended, 2)
        self.assertEqual({"g1": 0, "g2": 1, "g3": 0}, mapping)
        self.assertEqual([["g1", "g3"], ["g2"]], games)

    def test_concurrency_comes_from_atomic_launch_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "LAUNCH_STATE.json"
            path.write_text(json.dumps({"gameplay_concurrency": 28}), encoding="utf-8")
            self.assertEqual(28, gameplay_concurrency(Path(directory), 25))


if __name__ == "__main__":
    unittest.main()
