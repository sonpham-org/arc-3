"""
Author: Claude Opus 5
Date: 15-September-2026
PURPOSE: Guards for tools/build_sft.py, the bridge from finished decision-step records to
training examples. The corpus existed for four steps with nothing downstream reading it, so the
binding claim here is narrow and checkable: a finished record becomes an example the distiller's
format accepts, an UNFINISHED one never does, and the two things that would cause train/serve
skew - engine action names leaking to the model, and a board rendered by anything other than the
harness's own renderer - are asserted rather than assumed.

Also covers FrameResolver.resolve(), added to validate.py so consumers can fetch the grid a
frame_ref names instead of growing a second recording reader.

SRP/DRY check: Pass - test_decision_step_validator.py owns the schema and the resolver's
check() contract; test_segment.py owns pass A. This owns only record -> training example.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
sys.path.insert(0, str(REPO_ROOT / "datasets" / "decision-steps"))

import build_sft  # noqa: E402
from validate import FrameResolver  # noqa: E402

CORPUS = REPO_ROOT / "datasets" / "decision-steps"
FIXTURES = CORPUS / "fixtures" / "frame-resolution"
RECORDINGS = CORPUS / "v0" / "recordings"
EPISODES = CORPUS / "v0" / "episodes"

PROMPT = "SYSTEM PROMPT UNDER TEST"
SOURCE = "test"


def record(**overrides) -> dict:
    """A minimal finished record. Overrides replace whole top-level keys."""
    base = {
        "schema_version": "0.2",
        "tier": "gold",
        "game_id": "bp35-0a0ad940",
        "source": {"kind": "human_replay", "recording_guid": "g", "row_index": 10},
        "segment": {"id": "seg-00", "boundary_reason": "episode_start"},
        "level": 5,
        "memory_in": {"goal": "clear level 5", "known_mechanics": ["ACTION3 moves left"]},
        "last_action": {"action": "ACTION3"},
        "last_result": {"board_changed": True, "level_changed": False, "run_ended": False},
        "decision": {
            "action": {"action": "ACTION3"},
            "rationale": "step left again",
            "expected_observation": "a small local change",
        },
        "outcome": {"observed": "47 cells changed", "expectation_held": True},
        "rationale_provenance": "annotated",
    }
    base.update(overrides)
    return base


GRID = [[0, 1], [2, 3]]


class ResolveTests(unittest.TestCase):
    """FrameResolver.resolve() returns a board, or refuses - never a wrong board."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="build-sft-resolve-"))
        (self.tmp / "bp35-0a0ad940").mkdir(parents=True)
        self.ndjson = self.tmp / "bp35-0a0ad940" / "g.ndjson"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, *rows: dict) -> None:
        self.ndjson.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    def _ref(self, row_index: int = 0) -> dict:
        return record(frame_ref={"recording_guid": "g", "row_index": row_index, "field": "data.frame"})

    def test_returns_the_settled_grid_not_the_first(self):
        """The frame is a LIST of grids and the settled board is the LAST one - the convention
        SCHEMA.md settled against the engine. Taking frame[0] would hand every consumer the
        board as it looked before the action resolved, which still renders and is still wrong."""
        first, settled = [[1, 1], [1, 1]], [[9, 9], [9, 9]]
        self._write({"data": {"frame": [first, settled]}})
        self.assertEqual(FrameResolver(self.tmp).resolve(self._ref()), settled)

    def test_a_bare_grid_is_returned_as_is(self):
        """A field that holds one grid rather than a list of them keeps working."""
        grid = [[4, 2], [0, 7]]
        self._write({"data": {"frame": grid}})
        self.assertEqual(FrameResolver(self.tmp).resolve(self._ref()), grid)

    def test_an_empty_frame_list_raises(self):
        """Five rows of the real bp35 recording carry an empty frame list. A record must never
        be built on one - there is no board there to have looked at."""
        self._write({"data": {"frame": []}})
        with self.assertRaises(ValueError):
            FrameResolver(self.tmp).resolve(self._ref())

    def test_a_missing_recording_raises(self):
        with self.assertRaises(ValueError):
            FrameResolver(self.tmp).resolve(
                record(frame_ref={"recording_guid": "absent", "row_index": 0, "field": "data.frame"})
            )

    def test_an_out_of_range_row_raises(self):
        """Returning a wrong board would be silent corruption; refusing is the only safe answer."""
        self._write({"data": {"frame": [[[1]]]}})
        with self.assertRaises(ValueError):
            FrameResolver(self.tmp).resolve(self._ref(row_index=99))


class FinishedRecordTests(unittest.TestCase):
    """Only a record a mind finished may train."""

    def test_finished_record_is_finished(self):
        self.assertTrue(build_sft.is_finished(record()))

    def test_missing_rationale_is_not_finished(self):
        """A pass-A candidate has the judgment fields absent. It must never become an example -
        training on a machine-filled rationale teaches the model to narrate, not to reason."""
        for field in build_sft.JUDGMENT_FIELDS:
            decision = dict(record()["decision"])
            decision.pop(field)
            self.assertFalse(
                build_sft.is_finished(record(decision=decision)),
                f"a record missing {field!r} was treated as finished",
            )

    def test_blank_rationale_is_not_finished(self):
        decision = dict(record()["decision"], rationale="   ")
        self.assertFalse(build_sft.is_finished(record(decision=decision)))


class ActionVocabularyTests(unittest.TestCase):
    """The model has never seen an engine action name. Emitting one is train/serve skew."""

    def test_engine_names_are_translated_for_the_model(self):
        example = build_sft.build_example(record(), GRID, PROMPT, SOURCE)
        self.assertEqual(example["action"], "LEFT")

    def test_engine_names_never_reach_the_model_in_prose(self):
        """Annotators write against the game source and say ACTION3 in the rationale and the
        remembered mechanics. Showing the model an engine name in the same turn where it must
        answer in model vocabulary is train/serve skew, and it reads perfectly well, so nothing
        but an assertion catches it. This caught it."""
        rec = record(
            memory_in={"goal": "clear it", "known_mechanics": ["ACTION3 moves left"],
                       "hypotheses": ["ACTION5 does nothing"], "current_plan": "press ACTION4"},
            decision={"action": {"action": "ACTION3"},
                      "rationale": "ACTION3 stepped left last time",
                      "expected_observation": "ACTION3 moves one cell"},
            outcome={"observed": "ACTION3 changed 47 cells", "expectation_held": True},
        )
        blob = json.dumps(build_sft.build_example(rec, GRID, PROMPT, SOURCE)["messages"])
        for engine in ("ACTION1", "ACTION2", "ACTION3", "ACTION4", "ACTION5", "ACTION6"):
            self.assertNotIn(engine, blob, f"{engine} leaked to the model in prose")
        self.assertIn("LEFT stepped left last time", blob)

    def test_action7_survives_translation_in_prose(self):
        """ACTION7 and RESET are the model's own names for those actions. Rewriting them would
        be the same bug pointed the other way."""
        rec = record(memory_in={"known_mechanics": ["ACTION7 reverts the previous action"]})
        blob = json.dumps(build_sft.build_example(rec, GRID, PROMPT, SOURCE)["messages"])
        self.assertIn("ACTION7 reverts", blob)

    def test_a_clicked_cell_carries_its_coordinates(self):
        decision = {
            "action": {"action": "ACTION6", "args": {"row": 12, "col": 44}},
            "rationale": "click it",
            "expected_observation": "the cell changes",
        }
        example = build_sft.build_example(record(decision=decision), GRID, PROMPT, SOURCE)
        self.assertEqual(example["action"], "MOUSE(12,44)")

    def test_action7_and_reset_pass_through_as_themselves(self):
        """Both are exposed to the model under their own names by the harness's mapping."""
        for name in ("ACTION7", "RESET"):
            decision = dict(record()["decision"], action={"action": name})
            example = build_sft.build_example(record(decision=decision), GRID, PROMPT, SOURCE)
            self.assertEqual(example["action"], name)


class BoardRenderingTests(unittest.TestCase):
    """The board must be rendered by the harness's renderer, not a second implementation."""

    def test_board_uses_the_harness_colour_characters(self):
        from inference.utils.grid_utils import format_grid_ascii

        example = build_sft.build_example(record(), GRID, PROMPT, SOURCE)
        user = next(m["content"] for m in example["messages"] if m["role"] == "user")
        self.assertIn(format_grid_ascii(GRID), user)

    def test_board_shape_is_stated(self):
        example = build_sft.build_example(record(), GRID, PROMPT, SOURCE)
        user = next(m["content"] for m in example["messages"] if m["role"] == "user")
        self.assertIn("Grid shape: 2 x 2", user)


class RecoveryTests(unittest.TestCase):
    """The reason the corpus exists: a falsified expectation, and what the player did next."""

    def test_a_held_expectation_does_not_teach_recovery(self):
        example = build_sft.build_example(record(), GRID, PROMPT, SOURCE)
        self.assertFalse(example["teaches_recovery"])

    def test_a_falsified_expectation_teaches_recovery(self):
        outcome = {"observed": "nothing changed", "expectation_held": False}
        example = build_sft.build_example(record(outcome=outcome), GRID, PROMPT, SOURCE)
        self.assertTrue(example["teaches_recovery"])
        tool = next(m["content"] for m in example["messages"] if m["role"] == "tool")
        self.assertIn("does NOT match", tool)

    def test_a_verified_correction_becomes_the_final_turn(self):
        """Without this the example stops at 'you were wrong' and teaches nothing about fixing it."""
        outcome = {"observed": "nothing changed", "expectation_held": False}
        corrected = {
            "action": {"action": "RESET"},
            "rationale": "undo is dead, restart the level",
            "expected_observation": "the level reopens",
        }
        example = build_sft.build_example(
            record(outcome=outcome, corrected_decision=corrected), GRID, PROMPT, SOURCE
        )
        self.assertTrue(example["has_verified_correction"])
        self.assertEqual(example["messages"][-1]["role"], "assistant")
        self.assertIn("RESET", example["messages"][-1]["content"])

    def test_expectation_is_stated_before_the_action(self):
        """Ordering is load-bearing: an expectation written after the action cannot be refuted
        by the tool result that follows, which is the whole training signal."""
        example = build_sft.build_example(record(), GRID, PROMPT, SOURCE)
        assistant = next(m["content"] for m in example["messages"] if m["role"] == "assistant")
        self.assertLess(
            assistant.index("I expect:"), assistant.index("Action:"),
            "the expectation must precede the action or the tool result cannot falsify it",
        )


class CullTests(unittest.TestCase):
    """The unit is the level, not the run. A stumble on a level the player never cleared is
    flailing, and marking it as recovery would weight a training mix towards losing."""

    SOLVED = {"win-9": 9, "died-on-2": 1, "died-first": 0}

    def _rec(self, guid, level):
        return record(source={"kind": "human_replay", "recording_guid": guid, "row_index": 1},
                      level=level)

    def test_a_cleared_level_counts(self):
        """level is a COUNT, so a record at level 5 was played during the 6th; a run that
        finished 9 cleared it."""
        self.assertIs(build_sft.level_was_solved(self._rec("win-9", 5), self.SOLVED), True)

    def test_the_level_the_player_died_on_does_not(self):
        self.assertIs(build_sft.level_was_solved(self._rec("died-on-2", 1), self.SOLVED), False)

    def test_an_earlier_level_of_a_losing_run_still_counts(self):
        """This is the whole reason non-winning runs stay in scope: a run that cleared one level
        and then died still produced that one good level."""
        self.assertIs(build_sft.level_was_solved(self._rec("died-on-2", 0), self.SOLVED), True)

    def test_a_run_that_cleared_nothing_contributes_nothing(self):
        self.assertIs(build_sft.level_was_solved(self._rec("died-first", 0), self.SOLVED), False)

    def test_an_unknown_run_is_unknown_not_assumed_good(self):
        self.assertIsNone(build_sft.level_was_solved(self._rec("not-in-manifest", 3), self.SOLVED))

    def test_a_falsified_expectation_on_an_unsolved_level_is_not_recovery(self):
        """The gate that makes the flag mean what it says."""
        outcome = {"observed": "died", "expectation_held": False}
        example = build_sft.build_example(record(outcome=outcome), GRID, PROMPT, SOURCE, solved=False)
        self.assertFalse(example["teaches_recovery"])

    def test_the_same_record_on_a_solved_level_is_recovery(self):
        outcome = {"observed": "recovered", "expectation_held": False}
        example = build_sft.build_example(record(outcome=outcome), GRID, PROMPT, SOURCE, solved=True)
        self.assertTrue(example["teaches_recovery"])


class RunEndedTests(unittest.TestCase):
    """Schema 0.2. Without it a post-death record reads like an ordinary step."""

    def test_the_model_is_told_the_run_ended(self):
        rec = record(last_result={"board_changed": True, "level_changed": False, "run_ended": True})
        user = next(m["content"] for m in build_sft.build_example(rec, GRID, PROMPT, SOURCE)["messages"]
                    if m["role"] == "user")
        self.assertIn("ENDED THE RUN", user)

    def test_an_ordinary_step_is_not_announced_as_a_death(self):
        user = next(m["content"] for m in build_sft.build_example(record(), GRID, PROMPT, SOURCE)["messages"]
                    if m["role"] == "user")
        self.assertNotIn("ENDED THE RUN", user)


class ShapeTests(unittest.TestCase):
    """The example must match what the distiller's builder emits."""

    def test_carries_the_distiller_fields(self):
        example = build_sft.build_example(record(), GRID, PROMPT, SOURCE)
        for field in ("id", "game_id", "level", "messages", "num_messages"):
            self.assertIn(field, example)
        self.assertEqual(example["num_messages"], len(example["messages"]))

    def test_roles_are_in_conversation_order(self):
        example = build_sft.build_example(record(), GRID, PROMPT, SOURCE)
        self.assertEqual(
            [m["role"] for m in example["messages"]], ["system", "user", "assistant", "tool"]
        )

    def test_the_system_prompt_records_where_it_came_from(self):
        """A fine-tune run with the stand-in prompt is a skewed fine-tune. It must be traceable
        from the output alone."""
        example = build_sft.build_example(record(), GRID, PROMPT, SOURCE)
        self.assertEqual(example["system_prompt_source"], SOURCE)
        self.assertEqual(example["messages"][0]["content"], PROMPT)


class RealCorpusTests(unittest.TestCase):
    """End to end on the committed corpus. Skipped, not faked, when recordings are absent."""

    def setUp(self):
        if not RECORDINGS.is_dir() or not any(RECORDINGS.iterdir()):
            self.skipTest("recordings are gitignored; re-pull with tools/replay_scrape.py")

    def test_every_committed_record_becomes_an_example(self):
        resolver = FrameResolver(RECORDINGS)
        built = 0
        for _path, _lineno, rec in build_sft.iter_records(EPISODES):
            self.assertTrue(build_sft.is_finished(rec), "a committed record is unfinished")
            grid = resolver.resolve(rec)  # raises if the board cannot be seen
            build_sft.build_example(rec, grid, PROMPT, SOURCE)
            built += 1
        self.assertGreater(built, 0, "no committed records were found to convert")

    def test_the_death_undo_reset_triple_produces_the_recovery_arc(self):
        """The bp35 episode is the shape the corpus exists for: a fatal step, an undo that
        fails on a dead board, and the reset that recovers. If the bridge cannot carry that
        through to an example, it is not carrying the payload."""
        resolver = FrameResolver(RECORDINGS)
        examples = [
            build_sft.build_example(rec, resolver.resolve(rec), PROMPT, SOURCE)
            for _p, _l, rec in build_sft.iter_records(EPISODES)
        ]
        recovery = [e for e in examples if e["has_verified_correction"]]
        self.assertTrue(recovery, "no example carries a falsified expectation plus its correction")
        arc = recovery[0]
        self.assertEqual(arc["messages"][-1]["role"], "assistant")
        self.assertIn("RESET", arc["messages"][-1]["content"])


if __name__ == "__main__":
    unittest.main()
