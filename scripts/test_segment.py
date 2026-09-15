"""
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: Acceptance test for pass A (tools/segment.py). The binding criterion from
docs/plans/2026-09-15-step4-segment-and-label-execution.md section 3 is that the segmenter
reproduces the segment cuts, frame refs and outcome.observed numbers of the four hand-built
records in bp35-0a0ad940__c935ca1b-...__l5-death-undo-reset-00.jsonl, including the five
empty-frame rows (215, 370, 390, 572, 807) never being used as frame targets. That reproduction
is asserted here against the real 138 MB recording, and skipped - not faked - when the recording
is absent, matching RealRecordingTests in test_decision_step_validator.py. Also covers the three
guarantees a candidate file must carry: not collected by a validate.py directory walk, rejected
when named explicitly, and gitignored.
SRP/DRY check: Pass - test_decision_step_validator.py owns the record schema and the recordings'
row-reconcile rule; test_dispatch_tables.py owns the dispatch tables. This owns only the
segmenter. The hand-built expectations below are transcribed from the committed episode, not
recomputed by a second implementation of the same rules.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

import segment  # noqa: E402

CORPUS = REPO_ROOT / "datasets" / "decision-steps"
RECORDINGS = CORPUS / "v0" / "recordings"
EPISODES = CORPUS / "v0" / "episodes"

GAME_ID = "bp35-0a0ad940"
GUID = "c935ca1b-dfee-4be1-9574-bf4cc80c5b89"
RECORDING = RECORDINGS / GAME_ID / f"{GUID}.ndjson"
HAND_BUILT = EPISODES / f"{GAME_ID}__{GUID}__l5-death-undo-reset-00.jsonl"

# SCHEMA.md: the five rows of this recording that carry data.frame: [].
EMPTY_FRAME_ROWS = [215, 370, 390, 572, 807]

# Transcribed from the four hand-built records. row_index -> (frame_ref row, cells changed).
# `None` means the decision row's own frame list is empty, so there is no cell count to state.
EXPECTED = {
    213: (212, 47),
    214: (213, 1661),
    215: (214, None),
    216: (214, 1720),
}
EXPECTED_SEGMENTS = [([213, 214], "episode_start"), ([215, 216], "death")]


def run_segmenter(rows: str, prefix: str = "bp35-l5") -> list[dict]:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "segment.py"),
         "--game-id", GAME_ID, "--guid", GUID, "--rows", rows,
         "--segment-prefix", prefix, "--stdout"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        raise AssertionError(f"segment.py failed:\n{result.stderr}")
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


def run_validator(*args: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(CORPUS / "validate.py"), *args],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    return result.returncode, result.stdout + result.stderr


def cells_from_observed(text: str) -> int | None:
    match = re.match(r"^(\d+) cells changed ", text)
    return int(match.group(1)) if match else None


class RequiresRecording(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not RECORDING.is_file():
            raise unittest.SkipTest(
                f"no recording at {RECORDING}; run "
                f"python3.13 tools/replay_scrape.py known"
            )


class Bp35ReproductionTests(RequiresRecording):
    """The acceptance gate. If any of these fail, pass A has not been delivered."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.records = run_segmenter("213:216")
        cls.hand_built = [
            json.loads(line) for line in HAND_BUILT.read_text().splitlines() if line.strip()
        ]

    def test_hand_built_episode_is_still_four_records(self):
        self.assertEqual(len(self.hand_built), 4, "the ground truth changed; re-derive first")

    def test_one_record_per_row_in_the_window(self):
        self.assertEqual([r["source"]["row_index"] for r in self.records], [213, 214, 215, 216])

    def test_segment_cuts_match_the_hand_built_records(self):
        """Group consecutive records by segment id and compare rows + reason to the ground truth."""
        grouped: list[tuple[str, list[int], str]] = []
        for record in self.records:
            segment_id = record["segment"]["id"]
            reason = record["segment"]["boundary_reason"]
            row = record["source"]["row_index"]
            if grouped and grouped[-1][0] == segment_id:
                grouped[-1][1].append(row)
            else:
                grouped.append((segment_id, [row], reason))
        self.assertEqual([(rows, reason) for _, rows, reason in grouped], EXPECTED_SEGMENTS)

    def test_boundary_reason_is_constant_within_each_segment(self):
        by_segment: dict[str, set[str]] = {}
        for record in self.records:
            by_segment.setdefault(record["segment"]["id"], set()).add(
                record["segment"]["boundary_reason"]
            )
        for segment_id, reasons in by_segment.items():
            self.assertEqual(len(reasons), 1, f"{segment_id} carries {reasons}")

    def test_the_failed_undo_does_not_cut_a_segment(self):
        """Row 215 is an ACTION7 - an `undo` event by name - but its frame list is empty, so it
        changed nothing and cannot be a boundary. It belongs inside the recovery segment."""
        by_row = {r["source"]["row_index"]: r for r in self.records}
        self.assertEqual(by_row[215]["segment"]["id"], by_row[216]["segment"]["id"])
        self.assertEqual(by_row[215]["segment"]["boundary_reason"], "death")

    def test_frame_refs_match_the_hand_built_records(self):
        actual = {r["source"]["row_index"]: r["frame_ref"]["row_index"] for r in self.records}
        expected = {row: ref for row, (ref, _) in EXPECTED.items()}
        self.assertEqual(actual, expected)
        for record in self.records:
            self.assertEqual(record["frame_ref"]["field"], "data.frame")
            self.assertEqual(record["frame_ref"]["recording_guid"], GUID)

    def test_row_216_frame_ref_skips_the_empty_row(self):
        """The one row of the four that discriminates the rule. A naive `row - 1` would give 215
        and every outcome number after it would be wrong, while the other three rows still passed."""
        by_row = {r["source"]["row_index"]: r for r in self.records}
        self.assertEqual(by_row[216]["frame_ref"]["row_index"], 214)
        self.assertNotEqual(by_row[216]["frame_ref"]["row_index"], 215)

    def test_outcome_observed_numbers_match_the_hand_built_records(self):
        actual = {
            r["source"]["row_index"]: cells_from_observed(r["outcome"]["observed"])
            for r in self.records
        }
        self.assertEqual(actual, {row: cells for row, (_, cells) in EXPECTED.items()})

    def test_outcome_numbers_agree_with_the_committed_episode_text(self):
        """Cross-check against the episode file itself, not just the transcription above."""
        for record in self.hand_built:
            row = record["source"]["row_index"]
            expected_cells = EXPECTED[row][1]
            if expected_cells is None:
                continue
            self.assertIn(
                str(expected_cells),
                record["outcome"]["observed"],
                f"row {row}: the hand-built record no longer states {expected_cells}",
            )

    def test_level_last_action_and_last_result_match(self):
        by_row = {r["source"]["row_index"]: r for r in self.records}
        hand = {r["source"]["row_index"]: r for r in self.hand_built}
        for row in EXPECTED:
            with self.subTest(row=row):
                self.assertEqual(by_row[row]["level"], hand[row]["level"])
                self.assertEqual(by_row[row]["last_action"], hand[row]["last_action"])
                self.assertEqual(by_row[row]["last_result"], hand[row]["last_result"])

    def test_judgment_fields_are_absent_and_derivable_fields_are_present(self):
        for record in self.records:
            for absent in ("tier", "memory_in", "action_role", "corrected_decision"):
                self.assertNotIn(absent, record)
            self.assertNotIn("rationale", record["decision"])
            self.assertNotIn("expected_observation", record["decision"])
            self.assertNotIn("memory_out", record["decision"])
            self.assertNotIn("expectation_held", record["outcome"])
            for present in ("schema_version", "game_id", "source", "segment", "level",
                            "frame_ref", "ascii", "decision", "outcome",
                            "action_role_source", "rationale_provenance"):
                self.assertIn(present, record)

    def test_action_role_source_cites_the_dispatch_table(self):
        by_row = {r["source"]["row_index"]: r for r in self.records}
        self.assertIn("bp35.py:4504", by_row[213]["action_role_source"])   # ACTION3
        self.assertIn("bp35.py:4524", by_row[215]["action_role_source"])   # ACTION7
        self.assertIn("bp35.py:4529", by_row[216]["action_role_source"])   # RESET
        pattern = re.compile(r"^[^\s:]+:[0-9]+([ \t].*)?$")
        for record in self.records:
            self.assertRegex(record["action_role_source"], pattern)


class EmptyFrameRowTests(RequiresRecording):
    """All five empty-frame rows, not just the one inside the acceptance window."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rows = segment.load_rows(RECORDING, 0, max(EMPTY_FRAME_ROWS) + 2)

    def test_exactly_those_five_rows_are_empty(self):
        actual = [row.index for row in self.rows if segment.is_degenerate(row)]
        self.assertEqual(actual, EMPTY_FRAME_ROWS)

    def test_no_frame_ref_ever_lands_on_an_empty_row(self):
        empty = set(EMPTY_FRAME_ROWS)
        for row in range(1, max(EMPTY_FRAME_ROWS) + 2):
            with self.subTest(row=row):
                self.assertNotIn(segment.frame_ref_row(self.rows, row), empty)

    def test_the_row_after_each_empty_row_reaches_back_two(self):
        for empty_row in EMPTY_FRAME_ROWS:
            with self.subTest(empty_row=empty_row):
                self.assertEqual(segment.frame_ref_row(self.rows, empty_row + 1), empty_row - 1)

    def test_an_empty_row_is_never_a_boundary_event(self):
        for empty_row in EMPTY_FRAME_ROWS:
            with self.subTest(empty_row=empty_row):
                self.assertIsNone(segment.boundary_event(self.rows, empty_row))


class LevelChangeRefusalTests(RequiresRecording):
    """boundary_reason has no value for a level transition, so segment.py refuses rather than
    stretching `episode_start` over a state change."""

    def test_a_window_spanning_a_level_change_is_refused(self):
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "tools" / "segment.py"),
             "--game-id", GAME_ID, "--guid", GUID, "--rows", "176:182",
             "--segment-prefix", "bp35-l4", "--stdout"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("spans a level change", result.stderr)
        self.assertIn("boundary_reason has no value", result.stderr)


class CandidateFileTests(RequiresRecording):
    """The three guarantees an unfinished record must carry."""

    SLUG = "pytest-candidate-guarantees"

    def _write(self) -> Path:
        subprocess.run(
            [sys.executable, str(REPO_ROOT / "tools" / "segment.py"),
             "--game-id", GAME_ID, "--guid", GUID, "--rows", "213:216",
             "--segment-prefix", "bp35-l5", "--slug", self.SLUG],
            capture_output=True, text=True, cwd=REPO_ROOT, check=True,
        )
        path = EPISODES / f"{GAME_ID}__{GUID}__{self.SLUG}{segment.CANDIDATE_SUFFIX}"
        self.assertTrue(path.is_file())
        self.addCleanup(path.unlink)
        return path

    def test_candidate_is_not_collected_by_a_directory_walk(self):
        self._write()
        code, output = run_validator(str(EPISODES), "--require-frame-resolution")
        self.assertEqual(code, 0, output)
        self.assertNotIn(self.SLUG, output)

    def test_candidate_is_rejected_when_named_explicitly(self):
        path = self._write()
        code, output = run_validator(str(path))
        self.assertEqual(code, 1, output)
        for field in ("tier", "memory_in", "action_role", "rationale"):
            self.assertIn(f"missing required field '{field}'", output)

    def test_candidate_suffix_is_gitignored(self):
        path = self._write()
        result = subprocess.run(
            ["git", "check-ignore", "-v", str(path)],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        self.assertEqual(result.returncode, 0, "candidate files are not gitignored")
        self.assertIn("*.candidate.jsonl", result.stdout)


if __name__ == "__main__":
    unittest.main()
