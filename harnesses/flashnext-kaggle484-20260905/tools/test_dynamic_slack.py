"""Unit tests for the champion Dynamic Slack transplant."""

from __future__ import annotations

import inspect
import os
import pathlib
import pickle
import sys
import tempfile
import types
import unittest
from enum import Enum
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent
CANDIDATE = ROOT / os.environ.get("ARC3_TEST_CANDIDATE", "candidate-dynamicslack")


class _GameAction(Enum):
    ACTION1 = 1
    ACTION2 = 2
    ACTION3 = 3
    ACTION4 = 4
    ACTION5 = 5
    ACTION6 = 6
    RESET = 7


class _GameState(Enum):
    WIN = 1
    PLAYING = 2


class _OperationMode(Enum):
    OFFLINE = "offline"
    ONLINE = "online"
    COMPETITION = "competition"


arcengine = types.ModuleType("arcengine")
arcengine.GameAction = _GameAction
arcengine.GameState = _GameState
arcengine.enums = types.SimpleNamespace(GameAction=_GameAction, GameState=_GameState)
sys.modules.setdefault("arcengine", arcengine)

arc_agi = types.ModuleType("arc_agi")
arc_agi.__path__ = []
arc_agi.OperationMode = _OperationMode
arc_agi.Arcade = type("Arcade", (), {})
arc_agi.EnvironmentScorecard = type("EnvironmentScorecard", (), {})
arc_agi.EnvironmentWrapper = type("EnvironmentWrapper", (), {})
arc_agi_base = types.ModuleType("arc_agi.base")
arc_agi_base.OperationMode = _OperationMode
arc_agi.base = arc_agi_base
sys.modules.setdefault("arc_agi", arc_agi)
sys.modules.setdefault("arc_agi.base", arc_agi_base)

taaf = types.ModuleType("taaf")
taaf.__path__ = [str(CANDIDATE / "src" / "tufa-arc-agi-framework" / "src" / "taaf")]
sys.modules.setdefault("taaf", taaf)

for repo in sorted((CANDIDATE / "src").iterdir(), reverse=True):
    for import_root in (repo / "src", repo):
        if import_root.is_dir():
            sys.path.insert(0, str(import_root))

from inference.framework.solver import HarnessSolver, _DynamicSlackAllocator


EXPECTED_SOLVER = (
    CANDIDATE / "src" / "ARC3-Inference" / "inference" / "framework" / "solver.py"
).resolve()
if Path(inspect.getfile(_DynamicSlackAllocator)).resolve() != EXPECTED_SOLVER:
    raise ImportError("Test did not import the selected candidate solver")


class DynamicSlackTests(unittest.TestCase):
    def make_allocator(self, log_path: Path | None = None) -> _DynamicSlackAllocator:
        return _DynamicSlackAllocator(
            baseline_seconds=100,
            concurrency=2,
            total_games=3,
            safe_deadline_monotonic=200,
            grant_fraction=0.75,
            max_extra_seconds=50,
            initialized_at_monotonic=0,
            log_path=log_path,
        )

    def test_early_finish_is_shared_with_active_and_queued_games(self) -> None:
        allocator = self.make_allocator()
        allocator.start(0, now=0)
        allocator.start(1, now=0)
        allocator.finish(0, now=40)

        snapshot = allocator.snapshot(now=40)
        self.assertAlmostEqual(allocator.limit_seconds(1), 122.5)
        self.assertAlmostEqual(allocator.limit_seconds(2), 122.5)
        self.assertAlmostEqual(snapshot["bank_seconds"], 15.0)
        self.assertAlmostEqual(snapshot["reserved_queued_extra_seconds"], 22.5)
        self.assertEqual(snapshot["queued_count"], 1)
        self.assertEqual(snapshot["active_count"], 1)
        self.assertEqual(snapshot["completed_count"], 1)

    def test_empty_queue_releases_safe_tail_headroom_with_cap(self) -> None:
        allocator = self.make_allocator()
        allocator.start(0, now=0)
        allocator.start(1, now=0)
        allocator.finish(0, now=40)
        allocator.start(2, now=50)

        self.assertAlmostEqual(allocator.limit_seconds(1), 150.0)
        self.assertAlmostEqual(allocator.limit_seconds(2), 150.0)
        self.assertLessEqual(allocator.limit_seconds(1), 150.0)
        self.assertLessEqual(allocator.limit_seconds(2), 150.0)

    def test_scheduler_writes_auditable_events(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "dynamic-slack-scheduler.jsonl"
            allocator = self.make_allocator(log_path)
            allocator.start(0, now=0)
            allocator.finish(0, now=25)
            contents = log_path.read_text(encoding="utf-8")
            self.assertIn('"event": "initialized"', contents)
            self.assertIn('"event": "started"', contents)
            self.assertIn('"event": "finished"', contents)

    def test_champion_pickle_activates_allocator_settings_from_environment(self) -> None:
        benchmark_path = CANDIDATE / "benchmark_initial.pkl"
        with patch.object(pathlib, "PosixPath", Path), patch.dict(
            os.environ,
            {
                "ARC3_DYNAMIC_SLACK_ENABLED": "1",
                "ARC3_DYNAMIC_SLACK_GRANT_FRACTION": "0.75",
                "ARC3_DYNAMIC_SLACK_MAX_EXTRA_SECONDS": "1200",
            },
        ), benchmark_path.open("rb") as stream:
            benchmark = pickle.load(stream)

        self.assertTrue(benchmark.solver.dynamic_slack_enabled)
        self.assertEqual(benchmark.solver.dynamic_slack_grant_fraction, 0.75)
        self.assertEqual(benchmark.solver.dynamic_slack_max_extra_seconds, 1200.0)
        # The locked runner applies these two values after unpickling.
        benchmark.solver.max_runtime_s_per_game = 6480.0
        benchmark.solver.concurrency = 22
        self.assertEqual(benchmark.solver.max_runtime_s_per_game, 6480.0)
        self.assertEqual(benchmark.solver.concurrency, 22)

    def test_solver_runtime_limit_uses_allocator_grant(self) -> None:
        solver = HarnessSolver(max_runtime_s_per_game=100)
        solver._dynamic_slack_allocator = self.make_allocator()
        solver._dynamic_slack_allocator.start(0, now=0)
        solver._dynamic_slack_allocator.start(1, now=0)
        solver._dynamic_slack_allocator.finish(0, now=40)
        self.assertAlmostEqual(solver.runtime_limit_seconds_for_game(1), 122.5)


if __name__ == "__main__":
    unittest.main()
