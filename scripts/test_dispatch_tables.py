"""
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: Drift test for the per-game dispatch tables in datasets/decision-steps/dispatch/.
Re-reads every cited game source and fails if a cited line no longer contains its cited text,
which is the failure mode that would silently turn every action_role_source citation in the
corpus into a lie after an upstream source refresh. Also checks the internal consistency the
tables claim for themselves: line numbers in range, no duplicate action entries, offered flags
agreeing with the declared available_actions, and the twelve in-scope games all present.
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

# The eight games pass B was scoped to, from the execution plan section 1(b), plus the four that
# have a recording on disk but had no table until 16-Sep-2026 (docs/plans/2026-09-16-pass-d-e-pilot.md).
IN_SCOPE = [
    "bp35-0a0ad940",
    "g50t-5849a774",
    "cd82-fb555c5d",
    "cn04-2fe56bfb",
    "wa30-ee6fef47",
    "lp85-305b61c3",
    "ls20-9607627b",
    "lf52-271a04aa",
    "dc22-fdcac232",
    "ft09-0d8bbf25",
    "ka59-38d34dbb",
    "m0r0-492f87ba",
]

VENDORED_ENGINE_VERSION = "0.9.3"
VENDORED_ENGINE_DIR = f"arcengine-{VENDORED_ENGINE_VERSION}"
ENGINE_REL = Path("vendor") / VENDORED_ENGINE_DIR / "arcengine" / "base_game.py"
# sha256 of the sdist the vendored tree was unpacked from, as pinned in
# tufa-arc-agi-framework/uv.lock before this tree existed. See vendor/README.md.
VENDORED_ENGINE_SDIST_SHA256 = (
    "76441c15fde092a071ca95edce5e643385ab270304f59c1172b460048fffcdfe"
)
VENDORED_ENGINE_SHA256 = {
    "LICENSE":
        "007869cd1102b771aa889a7669138fd95239259ff0b6dd943e926910e54aefe7",
    "PKG-INFO":
        "daa4cb74147139e896b7ca4953b2fc5caa3b375b0bc3b89c073db1efa98efd14",
    "README.md":
        "a077b1a5246494d012534dea4cd6ba4715021cc564a24622f0e9dedde0923ea9",
    "arcengine/OVERVIEW.md":
        "65f20764d5e3cd8efc55f55508046c29b75cb27e22d70eaa7f76b400cf5abd0d",
    "arcengine/README.md":
        "2cc4693553c2dd7342ae0cadf5a335f377c4d6cea9c2d8a29ec63468e26bbd21",
    "arcengine/__init__.py":
        "538961ed7fcd09401dc7157c5611ee9f1fdaa177eae751a4b61b16844ab4304b",
    "arcengine/base_game.py":
        "5b5f41f3bec4c0c97a727fda7326114991dc0d4a5642d489b40ee4aa87e6b15f",
    "arcengine/camera.py":
        "f06e16807b0f97d86cafb5481bb3969213f27768f789d898c6b8b07e957de397",
    "arcengine/enums.py":
        "94ebef48f6fe950a18679a1b991c366e8e28c32ab58c9335f385e19bea21950e",
    "arcengine/interfaces.py":
        "0cfc24178e9f1102fb4ccb5892141d91c3a9eec88eccab3402b9777a76532cd8",
    "arcengine/level.py":
        "f74db969772b251018b2fcce6ec42f3522adeef4e9c03c036e455d2a35e3215a",
    "arcengine/py.typed":
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "arcengine/sprites.py":
        "ea9d3d02c7db0814954134a0e0ea6a3cb9b80066930dbdbfc5865befb54c493f",
    "pyproject.toml":
        "e7119efd519d6ef680065dc5b2d905f33aa45b7b2a4d5682305f869b105bff5b",
}

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
            # The `engine` block cites a DIFFERENT source file and is checked against it by
            # test_every_engine_anchor_still_contains_its_cited_text below. Sweeping it in here
            # would resolve engine line numbers against game source and fail for the right
            # reason with entirely the wrong message.
            game_only = {k: v for k, v in table.items() if k != "engine"}
            for json_path, anchor in iter_anchors(game_only):
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

    def test_every_offered_action_has_an_entry(self):
        """Pass B's acceptance criterion, stated verbatim in the execution plan section 3:
        *every action offered in that game's available_actions has an entry*. The `offered`
        test above checks the forward direction only - it would pass with an entry missing
        entirely."""
        for game_id, table in self.tables.items():
            available = table["available_actions"]
            offered = available["declared"]
            if offered is None:  # cn04 declares none; fall back to what the recording showed
                offered = available["observed_in_recording"]
            self.assertIsNotNone(offered, f"{game_id}: no declared or observed action set")
            for action_id in offered:
                with self.subTest(game=game_id, action=action_id):
                    self.assertIn(
                        f"ACTION{action_id}",
                        table["actions"],
                        f"{game_id}: ACTION{action_id} is offered but has no dispatch entry",
                    )

    def test_every_action_entry_has_a_branch_and_an_effect(self):
        for game_id, table in self.tables.items():
            for name, entry in table["actions"].items():
                with self.subTest(game=game_id, action=name):
                    self.assertIsInstance(entry["branch"]["line"], int)
                    self.assertTrue(entry["effect"].strip())

    def test_every_table_carries_the_engine_block(self):
        """RESET is dispatched by the engine on every game, whether or not the game also has a
        branch of its own, so every table must carry the citation for it."""
        for game_id, table in self.tables.items():
            with self.subTest(game=game_id):
                engine = table["engine"]
                self.assertEqual(engine["package"], "arcengine")
                self.assertEqual(engine["version"], VENDORED_ENGINE_VERSION)
                self.assertEqual(engine["source_file"], str(ENGINE_REL))
                self.assertIn("RESET", engine["actions"])
                self.assertTrue(engine["actions"]["RESET"]["effect"].strip())
                self.assertTrue(engine["actions"]["RESET"]["offered"])

    def test_every_engine_anchor_still_contains_its_cited_text(self):
        """The same drift check, against the vendored engine instead of the game source.

        Before the engine was vendored, a RESET record could only be cited on the two games
        that carry their own RESET branch, which biased the corpus toward exactly the games
        least representative of how recovery works on this platform. The citation is only worth
        having if it is checked like every other one.
        """
        lines = (REPO_ROOT / ENGINE_REL).read_text().splitlines()
        checked = 0
        for game_id, table in self.tables.items():
            engine = table["engine"]
            self.assertEqual(
                engine["source_line_count"],
                len(lines),
                f"{game_id}: vendored engine line count changed; every anchor has moved",
            )
            for json_path, anchor in iter_anchors(engine):
                with self.subTest(game=game_id, at=json_path, line=anchor["line"]):
                    self.assertTrue(
                        1 <= anchor["line"] <= len(lines),
                        f"{game_id} {json_path}: line {anchor['line']} is outside "
                        f"{ENGINE_REL} (1..{len(lines)})",
                    )
                    actual = lines[anchor["line"] - 1]
                    self.assertIn(
                        anchor["text"],
                        actual,
                        f"{game_id} {json_path}: {ENGINE_REL}:{anchor['line']} no longer "
                        f"contains the cited text.\n"
                        f"  cited:  {anchor['text']}\n"
                        f"  actual: {actual.strip()}",
                    )
                checked += 1
        self.assertGreater(checked, 80, "engine anchor discovery found suspiciously few anchors")

    def test_the_vendored_engine_is_the_pinned_upstream_artefact(self):
        """The vendored tree is only a citable source while it is unmodified upstream code.

        Two independent checks, because the point of vendoring was to make the citation
        CHECKABLE and a tree anyone can quietly edit is not. The per-file digests catch a local
        edit; uv.lock carries the sdist sha256 that was pinned before this tree existed and
        catches the wrong version being dropped in wholesale.
        """
        import hashlib

        for relative, expected in VENDORED_ENGINE_SHA256.items():
            path = REPO_ROOT / "vendor" / VENDORED_ENGINE_DIR / relative
            with self.subTest(file=relative):
                self.assertTrue(path.is_file(), f"vendored {relative} is gone")
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    expected,
                    f"vendored {relative} has been modified; it is upstream code and every "
                    f"engine citation in the dispatch tables is measured against it",
                )
        lock = (REPO_ROOT / "tufa-arc-agi-framework" / "uv.lock").read_text()
        self.assertIn(
            VENDORED_ENGINE_SDIST_SHA256,
            lock,
            "uv.lock no longer pins the sdist this tree was unpacked from",
        )
        # The package's own stanza, not the bare `{ name = "arcengine" }` dependency
        # references that appear first in the file.
        _, _, stanza = lock.partition('\nname = "arcengine"\n')
        self.assertTrue(stanza, "uv.lock has no arcengine package stanza")
        self.assertIn(
            f'version = "{VENDORED_ENGINE_VERSION}"',
            stanza[:200],
            "uv.lock pins a different arcengine version than the one vendored",
        )

    def test_reset_is_never_reported_as_uncitable(self):
        """The blocker this vendoring exists to clear, asserted so it cannot come back.

        Six real lp85 RESET records sat unlandable in a trace-findings doc because the segmenter
        had no citation to emit for them. If any table ever again describes RESET as having no
        citable source, that state is back.
        """
        for game_id, table in self.tables.items():
            with self.subTest(game=game_id):
                note = table["unhandled_actions"]["note"]
                self.assertNotIn(
                    "which is not vendored",
                    note,
                    f"{game_id}: unhandled_actions still says the engine is not vendored",
                )

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
        named = []
        for game_id, table in self.tables.items():
            sib = table["sibling_builds"]
            for sibling in sib["siblings_in_manifests"]:
                named.append(sibling)
                with self.subTest(game=game_id, sibling=sibling):
                    self.assertNotIn(sibling, live)
                    self.assertIs(sib["sibling_is_a_live_build"], False)
        self.assertEqual(
            sorted(named),
            ["cn04-65d47d14", "dc22-4c9bff3e", "ka59-9f096b4a", "ls20-cb3b57cc", "m0r0-dadda488"],
            "the stale builds the replay manifests name for in-scope games",
        )

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
