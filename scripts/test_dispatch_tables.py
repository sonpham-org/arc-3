"""
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: Drift test for the per-game dispatch tables in datasets/decision-steps/dispatch/.
Re-reads every cited game source and fails if a cited line no longer contains its cited text,
which is the failure mode that would silently turn every action_role_source citation in the
corpus into a lie after an upstream source refresh. Also checks the internal consistency the
tables claim for themselves: line numbers in range, no duplicate action entries, offered flags
agreeing with the declared available_actions, and the eight in-scope games all present.
SRP/DRY check: Pass - scripts/test_decision_step_validator.py covers the record schema and the
recordings; this covers only the dispatch tables. Nothing about the record contract is retested
here.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DISPATCH_DIR = REPO_ROOT / "datasets" / "decision-steps" / "dispatch"

# The eight games pass B was scoped to, from the execution plan section 1(b).
IN_SCOPE = [
    "bp35-0a0ad940",
    "g50t-5849a774",
    "cd82-fb555c5d",
    "cn04-2fe56bfb",
    "wa30-ee6fef47",
    "lp85-305b61c3",
    "ls20-9607627b",
    "lf52-271a04aa",
]

ACTION_NAMES = {f"ACTION{i}" for i in range(1, 8)} | {"RESET"}


def load_tables() -> dict[str, dict]:
    return {
        path.stem: json.loads(path.read_text())
        for path in sorted(DISPATCH_DIR.glob("*.json"))
    }


def iter_anchors(node, trail="$"):
    """Yield (json_path, anchor) for every object carrying both `line` and `text`."""
    if isinstance(node, dict):
        if isinstance(node.get("line"), int) and isinstance(node.get("text"), str):
            yield trail, node
        for key, value in node.items():
            yield from iter_anchors(value, f"{trail}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from iter_anchors(value, f"{trail}[{index}]")


class DispatchTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = load_tables()
        cls.sources = {}
        for game_id, table in cls.tables.items():
            path = REPO_ROOT / table["source_file"]
            cls.sources[game_id] = path.read_text().splitlines()

    def test_every_in_scope_game_has_a_table(self):
        self.assertEqual(sorted(self.tables), sorted(IN_SCOPE))

    def test_source_files_exist_and_line_count_matches(self):
        for game_id, table in self.tables.items():
            with self.subTest(game=game_id):
                path = REPO_ROOT / table["source_file"]
                self.assertTrue(path.is_file(), f"{table['source_file']} is gone")
                self.assertEqual(
                    table["source_line_count"],
                    len(self.sources[game_id]),
                    f"{game_id}: source line count changed; every anchor below it has moved",
                )

    def test_every_anchor_still_contains_its_cited_text(self):
        """The drift check. This is the whole point of the file."""
        checked = 0
        for game_id, table in self.tables.items():
            lines = self.sources[game_id]
            for json_path, anchor in iter_anchors(table):
                with self.subTest(game=game_id, at=json_path, line=anchor["line"]):
                    self.assertTrue(
                        1 <= anchor["line"] <= len(lines),
                        f"{game_id} {json_path}: line {anchor['line']} is outside "
                        f"{table['source_file']} (1..{len(lines)})",
                    )
                    actual = lines[anchor["line"] - 1]
                    self.assertIn(
                        anchor["text"],
                        actual,
                        f"{game_id} {json_path}: {table['source_file']}:{anchor['line']} "
                        f"no longer contains the cited text.\n"
                        f"  cited:  {anchor['text']}\n"
                        f"  actual: {actual.strip()}",
                    )
                checked += 1
        self.assertGreater(checked, 150, "anchor discovery found suspiciously few anchors")

    def test_action_names_are_real(self):
        for game_id, table in self.tables.items():
            with self.subTest(game=game_id):
                self.assertTrue(set(table["actions"]) <= ACTION_NAMES)
                self.assertTrue(set(table["unhandled_actions"]["actions"]) <= ACTION_NAMES)
                overlap = set(table["actions"]) & set(table["unhandled_actions"]["actions"])
                self.assertEqual(overlap, set(), f"{game_id}: action both handled and unhandled")

    def test_offered_flag_agrees_with_declared_available_actions(self):
        """`offered` is what stops a record citing a branch no API call can reach."""
        for game_id, table in self.tables.items():
            declared = table["available_actions"]["declared"]
            if declared is None:
                continue  # cn04 declares none; its `offered` comes from the recording
            offered_ids = {f"ACTION{i}" for i in declared}
            for name, entry in table["actions"].items():
                if name == "RESET":
                    continue  # engine-level, always accepted, never declared
                with self.subTest(game=game_id, action=name):
                    self.assertEqual(
                        entry["offered"],
                        name in offered_ids,
                        f"{game_id} {name}: offered={entry['offered']} but declared "
                        f"available_actions={declared}",
                    )

    def test_every_action_entry_has_a_branch_and_an_effect(self):
        for game_id, table in self.tables.items():
            for name, entry in table["actions"].items():
                with self.subTest(game=game_id, action=name):
                    self.assertIsInstance(entry["branch"]["line"], int)
                    self.assertTrue(entry["effect"].strip())

    def test_sibling_verdicts_are_present_and_decided(self):
        """Pass B was told to settle this per game; an absent verdict is a failure."""
        for game_id, table in self.tables.items():
            with self.subTest(game=game_id):
                sib = table["sibling_builds"]
                self.assertIn("verdict", sib)
                self.assertIsInstance(sib["may_cite_sibling_source"], bool)
                self.assertFalse(
                    sib["may_cite_sibling_source"],
                    f"{game_id}: no sibling citation is permitted anywhere - see "
                    f"datasets/decision-steps/dispatch/README.md",
                )
                self.assertTrue(sib["reason"].strip())

    def test_every_in_scope_game_is_itself_a_live_build(self):
        """The eligibility rule from commit 649e53a: a run counts only if its game_id is still
        the live build. A table for a stale build would be labelling a game that no longer
        ships."""
        live = {
            build["game_id"]
            for build in json.loads(
                (REPO_ROOT / "datasets" / "decision-steps" / "current-builds.json").read_text()
            )["builds"]
        }
        for game_id in self.tables:
            with self.subTest(game=game_id):
                self.assertIn(game_id, live, f"{game_id} is no longer a live build")

    def test_no_sibling_named_in_a_table_is_a_live_build(self):
        """Ties the measured finding to the eligibility rule: citations do not transfer between
        builds, AND every sibling we could have been tempted to cite is out of scope anyway. If
        a lineup change ever makes a named sibling live, that is worth failing over."""
        live = {
            build["game_id"]
            for build in json.loads(
                (REPO_ROOT / "datasets" / "decision-steps" / "current-builds.json").read_text()
            )["builds"]
        }
        named = 0
        for game_id, table in self.tables.items():
            sib = table["sibling_builds"]
            for sibling in sib["siblings_in_manifests"]:
                named += 1
                with self.subTest(game=game_id, sibling=sibling):
                    self.assertNotIn(sibling, live)
                    self.assertIs(sib["sibling_is_a_live_build"], False)
        self.assertEqual(named, 2, "expected exactly cn04-65d47d14 and ls20-cb3b57cc")

    def test_the_two_games_with_a_real_sibling_record_the_measurement(self):
        self.assertEqual(
            self.tables["ls20-9607627b"]["sibling_builds"]["siblings_with_source"],
            ["ls20-cb3b57cc"],
        )
        measurement = self.tables["ls20-9607627b"]["sibling_builds"]["measurement"]
        self.assertNotEqual(
            measurement["this_build_dispatch_line"],
            measurement["sibling_build_dispatch_line"],
            "if these ever agree the sibling finding needs re-measuring, not asserting",
        )
        self.assertEqual(
            self.tables["cn04-2fe56bfb"]["sibling_builds"]["siblings_with_source"], []
        )


if __name__ == "__main__":
    unittest.main()
