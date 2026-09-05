"""Fail-closed release checks for the champion reasoning-only GCP arms."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent
BASELINE = ROOT / "v12-run-kaggle11p44-2fc2be2e8d0db29b23d588413603d5bc5f36096b5e9fe092f9a3a38f3f1d4ee2.py"
REFLECTION = ROOT / "v12-run-kaggle11p44-reflectionv3-8fa07e58d23da92db1fabb2102f70a6f12b7bebdd82e5dc2fd326b6268fd7d4a.py"
REFINEMENT = ROOT / "v12-run-kaggle11p44-refinement-b0910d2bae2424b78f39f1df71d38b69b08c567152f1869ad2ceac1fc8c86ae6.py"
PRIOR_REFINEMENT = Path(
    r"C:\Users\celle\Documents\Codex\2026-09-03\qu\work\gcp-direct-refinement\runner-audit"
) / "v12-run-flashnext-policy-004f44051a6ae98adb4e48ef91f775e6398401504381e900f9f208b8b758354b.py"
LAUNCHER = ROOT / "launch_champion_stall_ab.ps1"


class ChampionReasoningArmTests(unittest.TestCase):
    def test_reflection_runner_is_exact_baseline_plus_activation(self) -> None:
        baseline = BASELINE.read_text(encoding="utf-8")
        candidate = REFLECTION.read_text(encoding="utf-8")
        candidate = candidate.replace(
            '"""GCP runner for the locked ARC3 Kaggle 11.44 RTDv12 + Reflection V3 arm.\n\n'
            "The bundle pickle stores an older 28-worker/7,920-second scheduler. The scored\n"
            "Kaggle notebook overrides it after unpickling, so this runner must do the same\n"
            "and fail closed if the exact 22-worker/6,480-second lock is not established.\n"
            "The sole reasoning delta is activation of the bundle's existing guarded,\n"
            'same-context post-level Reflection V3 mechanism.\n"""',
            '"""GCP runner for the locked ARC3 Kaggle 11.44 RTDv12 baseline.\n\n'
            "The bundle pickle stores an older 28-worker/7,920-second scheduler. The scored\n"
            "Kaggle notebook overrides it after unpickling, so this runner must do the same\n"
            'and fail closed if the exact 22-worker/6,480-second lock is not established.\n"""',
        )
        candidate = candidate.replace(
            'assert os.environ["ARC3_SAME_CONTEXT_LEVEL_REFLECTION_ENABLED"] == "1"\n'
            'assert os.environ.get("ARC3_SAME_CONTEXT_LEVEL_REFLECTION_VERSION", "3") == "3"',
            'assert "ARC3_SAME_CONTEXT_LEVEL_REFLECTION_ENABLED" not in os.environ',
        )
        candidate = candidate.replace(
            '"cap14, fixed30, Reflection V3 enabled, request logs off"',
            '"cap14, fixed30, reflection dormant, request logs off"',
        )
        self.assertEqual(candidate, baseline)

    def test_refinement_policy_code_matches_previously_tested_policy(self) -> None:
        prior_tree = ast.parse(PRIOR_REFINEMENT.read_text(encoding="utf-8"))
        candidate_tree = ast.parse(REFINEMENT.read_text(encoding="utf-8"))
        prior_functions = {
            node.name: ast.dump(node, include_attributes=False)
            for node in prior_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        candidate_functions = {
            node.name: ast.dump(node, include_attributes=False)
            for node in candidate_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertEqual(candidate_functions, prior_functions)

    def test_refinement_runner_preserves_champion_runtime_contract(self) -> None:
        source = REFINEMENT.read_text(encoding="utf-8")
        for required in (
            'POLICY != "refinement"',
            'bm.solver.max_runtime_s_per_game == 6480.0',
            'bm.solver.concurrency == 22',
            'bm.solver.save_request_logs is False',
            'os.environ["ARC3_ACTION_CAP"] == "14"',
            'os.environ["ARC3_POST_LEVEL_UNCAPPED_TURNS"] == "0"',
            '"ARC3_SAME_CONTEXT_LEVEL_REFLECTION_ENABLED" not in os.environ',
            'len(game_ids) == 25',
            'timedelta(hours=11, minutes=20)',
        ):
            self.assertIn(required, source)
        self.assertNotIn("taaf_grafts", source)
        self.assertEqual(source.count("asyncio.run(bm.run("), 1)

    def test_content_hashes_match_immutable_names(self) -> None:
        for path in (REFLECTION, REFINEMENT):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertIn(digest, path.name)

    def test_launcher_wires_six_clean_champion_cells(self) -> None:
        source = LAUNCHER.read_text(encoding="utf-8")
        for required in (
            "[switch]$ChampionReflectionV3",
            "[switch]$ChampionRefinement",
            "export ARC3_SAME_CONTEXT_LEVEL_REFLECTION_VERSION=3",
            "export ARC3_REASONING_POLICY=refinement",
            "ChampionReflectionV3 must remain a sole-delta champion arm.",
            "ChampionRefinement must remain a sole-delta champion arm.",
        ):
            self.assertIn(required, source)


if __name__ == "__main__":
    unittest.main()
