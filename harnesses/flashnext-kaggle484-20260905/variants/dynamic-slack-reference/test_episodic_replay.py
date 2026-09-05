from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("ARC3_REPLAY_ENABLED", "1")
os.environ.setdefault("ARC3_REPLAY_ARM", "B")
os.environ.setdefault("LOCAL_ANALYZER_MODEL_ID", "test-model")

from inference.agent.python_tool_sandbox import run_sandboxed_python
from inference.agent.runtime_state import Frame, HistoryEntry, write_runtime_state
from inference.agent import tool_agent


def frame_payload(grid: list[list[int]], *, step: int, level: int = 1) -> dict:
    return {
        "ascii": "",
        "step": step,
        "level": level,
        "shape": [len(grid), len(grid[0]) if grid else 0],
        "grid": grid,
    }


def replay_state(*, enabled: bool = True, length: int = 3) -> dict:
    first = [[0, 0], [0, 0]]
    second = [[0, 1], [0, 0]]
    entries = [
        {"action": "", "frame": frame_payload(first, step=0)},
        {"action": "DOWN", "frame": frame_payload(second, step=1)},
        {"action": "UP", "frame": frame_payload(first, step=2)},
    ]
    while len(entries) < length:
        value = len(entries) % 16
        grid = [[value for _ in range(64)] for _ in range(64)]
        entries.append(
            {
                "action": "RIGHT",
                "frame": frame_payload(grid, step=len(entries)),
            }
        )
    return {
        "current_frame": entries[-1]["frame"],
        "history": entries,
        "replay_enabled": enabled,
        "valid_actions": ["UP", "DOWN"],
        "last_action_result": {},
        "last_animation": None,
    }


class EpisodicReplayTest(unittest.TestCase):
    def run_code(self, code: str, state: dict) -> dict:
        def reject_actions(_: list[dict]) -> dict:
            raise AssertionError("replay inspection must not execute actions")

        return run_sandboxed_python(
            code=code,
            timeout_seconds=10,
            initial_state=state,
            action_handler=reject_actions,
        )

    def test_exact_repeat_and_next_action(self) -> None:
        result = self.run_code(
            "current=replay.event(3); matches=replay.find(state_hash=current['state_hash']); "
            "previous=matches[1]; following=replay.event(previous['event_id']+1); "
            "result={'previous':previous['event_id'],'action':following['action'],"
            "'changed':following['changed_count']}",
            replay_state(),
        )
        self.assertEqual(
            result["result"],
            {"previous": 1, "action": "DOWN", "changed": 1},
        )
        self.assertEqual(result["action_results"], [])
        self.assertGreaterEqual(result["replay_usage"]["call_count"], 3)
        self.assertEqual(result["replay_usage"]["methods"]["find"], 1)

    def test_replay_is_absent_when_disabled(self) -> None:
        result = self.run_code("result=replay.stats()", replay_state(enabled=False))
        self.assertIn("NameError", result["error"])
        self.assertEqual(result["replay_usage"]["call_count"], 0)

    def test_trigger_is_c_only_and_exact(self) -> None:
        frame_a = Frame(grid=((0, 0), (0, 0)), step=0, level=1)
        frame_b = Frame(grid=((0, 1), (0, 0)), step=1, level=1)
        repeated = [
            HistoryEntry(action="", frame=frame_a),
            HistoryEntry(action="DOWN", frame=frame_b),
            HistoryEntry(action="UP", frame=frame_a),
        ]
        original = tool_agent._REPLAY_TRIGGER_REMINDER
        try:
            tool_agent._REPLAY_TRIGGER_REMINDER = False
            agent = tool_agent.ToolAgent()
            self.assertIn("Lossless replay memory:", agent._system_prompt)
            self.assertIn("replay.repeated_states()", tool_agent._PYTHON_TOOL_DESCRIPTION)
            prompt_b = agent._build_user_prompt(
                2,
                valid_actions=["UP", "DOWN"],
                current_frame=frame_a,
                history_entries=repeated,
            )
            self.assertNotIn("Replay trigger:", prompt_b)

            tool_agent._REPLAY_TRIGGER_REMINDER = True
            prompt_c = agent._build_user_prompt(
                2,
                valid_actions=["UP", "DOWN"],
                current_frame=frame_a,
                history_entries=repeated,
            )
            self.assertIn("Replay trigger:", prompt_c)
            novel = agent._build_user_prompt(
                1,
                valid_actions=["UP", "DOWN"],
                current_frame=frame_b,
                history_entries=repeated[:2],
            )
            self.assertNotIn("Replay trigger:", novel)
        finally:
            tool_agent._REPLAY_TRIGGER_REMINDER = original

    def test_usage_log_is_host_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "game_tool_runtime_state.json"
            tool_agent._append_replay_usage_log(
                path,
                {"call_count": 2, "methods": {"stats": 1, "find": 1}, "calls": []},
            )
            log_path = path.with_name("game_tool_runtime_state_replay_usage.jsonl")
            self.assertTrue(log_path.exists())
            self.assertIn('"call_count":2', log_path.read_text(encoding="utf-8"))

    def test_tool_agent_production_state_path_exposes_replay(self) -> None:
        frame_a = Frame(grid=((0, 0), (0, 0)), step=0, level=1)
        frame_b = Frame(grid=((0, 1), (0, 0)), step=1, level=1)
        history = [
            HistoryEntry(action="", frame=frame_a),
            HistoryEntry(action="DOWN", frame=frame_b),
            HistoryEntry(action="UP", frame=frame_a),
        ]
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "game_tool_runtime_state.json"
            write_runtime_state(state_path, current_frame=frame_a, history=history)
            agent = tool_agent.ToolAgent()
            dispatched = agent._run_python_tool(
                state_path,
                {"code": "result=replay.stats()"},
            )
            self.assertIn('"events": 3', dispatched.content)
            usage_path = state_path.with_name(
                "game_tool_runtime_state_replay_usage.jsonl"
            )
            self.assertTrue(usage_path.exists())
            self.assertIn('"stats":1', usage_path.read_text(encoding="utf-8"))

    def test_two_hundred_event_lookup_is_cpu_small(self) -> None:
        started = time.perf_counter()
        result = self.run_code(
            "result={'stats':replay.stats(),'repeats':len(replay.repeated_states())}",
            replay_state(length=200),
        )
        elapsed = time.perf_counter() - started
        self.assertFalse(result.get("error"), result.get("error"))
        self.assertEqual(result["result"]["stats"]["events"], 200)
        self.assertLess(elapsed, 2.0)


if __name__ == "__main__":
    unittest.main()
