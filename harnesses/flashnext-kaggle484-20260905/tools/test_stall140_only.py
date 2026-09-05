"""Verify the sole gameplay delta in the locked champion Stall-140 bundle."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import sys
import tempfile
import types
import unittest
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent
CANDIDATE = ROOT / os.environ.get("ARC3_TEST_CANDIDATE", "candidate")
LOCKED_RUNNER = ROOT / (
    "v12-run-kaggle11p44-"
    "2fc2be2e8d0db29b23d588413603d5bc5f36096b5e9fe092f9a3a38f3f1d4ee2.py"
)

# The production engine is supplied by the ARC Foundation runtime.  These
# import-only enum shims let the isolated unit test load the bundled framework
# without changing or vendoring any production module.
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


arcengine = types.ModuleType("arcengine")
arcengine.GameAction = _GameAction
arcengine.GameState = _GameState
arcengine.enums = types.SimpleNamespace(
    GameAction=_GameAction,
    GameState=_GameState,
)
sys.modules.setdefault("arcengine", arcengine)

# Load only the two bundled TAAF modules needed by the solver.  This avoids
# importing optional competition backends that are absent outside the image.
taaf = types.ModuleType("taaf")
taaf.__path__ = [str(CANDIDATE / "src" / "tufa-arc-agi-framework" / "src" / "taaf")]
sys.modules.setdefault("taaf", taaf)

for repo in sorted((CANDIDATE / "src").iterdir(), reverse=True):
    for import_root in (repo / "src", repo):
        if import_root.is_dir():
            sys.path.insert(0, str(import_root))

import inference.framework.solver as solver_module
from inference.framework.solver import (
    STALL_ACTION_LIMIT,
    HarnessSolver,
    _HarnessGameSession,
)


EXPECTED_SOLVER = (
    CANDIDATE / "src" / "ARC3-Inference" / "inference" / "framework" / "solver.py"
).resolve()
if Path(inspect.getfile(_HarnessGameSession)).resolve() != EXPECTED_SOLVER:
    raise ImportError("Test did not import the candidate solver")


def make_session(
    root: Path,
    *,
    levels_completed: int,
    number_of_levels: int,
    actions_per_level: list[int],
) -> _HarnessGameSession:
    run = SimpleNamespace(
        game_id="test01",
        levels_completed=levels_completed,
        number_of_levels=number_of_levels,
        actions_per_level=list(actions_per_level),
        state="playing",
        history=[object()] * sum(actions_per_level),
        solver_note=None,
    )
    game = SimpleNamespace(game_run=run)
    solver = HarnessSolver(max_runtime_s_per_game=6_480)
    return _HarnessGameSession(
        solver=solver,
        game=game,
        analyzer=SimpleNamespace(total_tokens=0),
        game_index=3,
        pass_index=0,
        state_path=root / "test01_p0_tool_runtime_state.json",
        transcript_path=root / "test01_p0.txt",
        analysis_html_relpath="solver_analysis/test01_p0.html",
        stop_event=solver._stop_event,
        viewer_data_path=root / "test01_p0_viewer_data.json",
    )


class Stall140OnlyTests(unittest.TestCase):
    def test_unresolved_level_stops_at_140_and_emits_one_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = make_session(
                root,
                levels_completed=1,
                number_of_levels=5,
                actions_per_level=[12, 140, 0, 0, 0],
            )
            self.assertEqual(STALL_ACTION_LIMIT, 140)
            self.assertTrue(session.stall_action_limit_reached())
            artifact = root / "test01_p0_stall_guard.json"
            payload = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertEqual(payload["level"], 2)
            self.assertEqual(payload["level_actions"], 140)
            self.assertEqual(payload["levels_completed"], 1)
            first_contents = artifact.read_bytes()
            self.assertTrue(session.stall_action_limit_reached())
            self.assertEqual(artifact.read_bytes(), first_contents)

    def test_139_actions_keeps_playing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = make_session(
                Path(directory),
                levels_completed=0,
                number_of_levels=2,
                actions_per_level=[139, 0],
            )
            self.assertFalse(session.stall_action_limit_reached())

    def test_completion_on_action_140_resets_the_counter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = make_session(
                Path(directory),
                levels_completed=1,
                number_of_levels=2,
                actions_per_level=[140, 0],
            )
            self.assertFalse(session.stall_action_limit_reached())

    def test_should_stop_integrates_the_guard(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = make_session(
                Path(directory),
                levels_completed=0,
                number_of_levels=2,
                actions_per_level=[140, 0],
            )
            with patch.object(solver_module, "_is_run_complete", return_value=False):
                self.assertTrue(session.should_stop())

    def test_locked_runner_applies_and_asserts_post_unpickle_settings(self) -> None:
        contents = LOCKED_RUNNER.read_bytes()
        self.assertEqual(
            hashlib.sha256(contents).hexdigest(),
            "2fc2be2e8d0db29b23d588413603d5bc5f36096b5e9fe092f9a3a38f3f1d4ee2",
        )
        source = contents.decode("utf-8")
        required_lines = (
            'bm.solver.max_runtime_s_per_game = float(os.environ["ARC3_MAX_RUNTIME_S_PER_GAME"])',
            'bm.solver.concurrency = int(os.environ["ARC3_BENCHMARK_CONCURRENCY"])',
            "bm.solver.save_request_logs = False",
            "assert bm.solver.max_runtime_s_per_game == 6480.0",
            "assert bm.solver.concurrency == 22",
            'assert os.environ["ARC3_ACTION_CAP"] == "14"',
            'assert os.environ["ARC3_POST_LEVEL_UNCAPPED_TURNS"] == "0"',
            'assert "ARC3_SAME_CONTEXT_LEVEL_REFLECTION_ENABLED" not in os.environ',
            'assert len(game_ids) == 25, f"exact baseline requires 25 games, got {len(game_ids)}"',
        )
        for line in required_lines:
            self.assertIn(line, source)


if __name__ == "__main__":
    unittest.main()
