"""
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: Tests for datasets/decision-steps/validate.py against the committed fixture corpus.
Covers, with real fixture files on disk rather than inline literals: every valid-tier record
passing; one invalid fixture per failure mode producing a specific, human-readable message and
a non-zero exit; the turn-0 contract (both last_action and last_result null, still required,
and both-or-neither) and that it is expressed without any keyword the evaluator cannot
enforce; all six frame-reference resolution failures being distinguishable (missing
recording, row out of range, flat field miss, dotted segment miss, descent into a
non-object, and an empty frame list); that a dotted frame_ref.field really resolves
against the re-pulled recordings when they are present, and is skipped rather than
failed when they are not; the
summary line announcing SKIPPED when the gitignored recordings are absent, so a green run is
never mistaken for a resolved one; and the schema evaluator's unsupported-keyword guard firing
at top level and inside $defs, which is what keeps the hand-rolled draft 2020-12 subset from
silently under-validating if schema.json grows a keyword the engine cannot enforce. A coverage
test asserts every file under fixtures/invalid/ has an expectation here, so adding a fixture
without asserting on it fails the suite.
Run from the repo root: python3.13 -m unittest scripts.test_decision_step_validator -v
SRP/DRY check: Pass — matches the existing scripts/test_*.py unittest convention (see
scripts/test_run_catalog.py); no shared test helper module exists in scripts/ to reuse, each
test file is self-contained. The validator is loaded through importlib because its package
directory name, decision-steps, is hyphenated and therefore not importable by name.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = REPO_ROOT / "datasets" / "decision-steps"
FIXTURES = CORPUS_DIR / "fixtures"


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "decision_step_validate", CORPUS_DIR / "validate.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validate = _load_validator()


def run_cli(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = validate.main(list(argv))
    return code, out.getvalue() + err.getvalue()


def absent_recordings_dir() -> str:
    """A recordings path guaranteed not to exist.

    Deliberately not the default datasets/decision-steps/v0/recordings: step 3's scraper
    creates that directory, and a test that inherits the default silently changes meaning the
    day it first runs. It did — the valid/ fixtures cite real bp35 and g50t guids, so once the
    recordings landed, resolution switched itself on underneath tests that were only ever
    asserting record shape. Shape-only tests say so explicitly.
    """
    return str(Path(tempfile.mkdtemp(prefix="decision-steps-absent-")) / "no-recordings-here")


def run_shape_only(*argv: str) -> tuple[int, str]:
    """Validate structure with frame resolution provably off."""
    return run_cli(*argv, "--recordings-dir", absent_recordings_dir())


# One entry per file in fixtures/invalid/. The substring is the part of the message a human
# needs in order to fix the row.
INVALID_EXPECTATIONS = {
    "missing-required-field": "$.decision: missing required field 'expected_observation'",
    "wrong-type-level": "$.level: expected type integer, got string",
    "empty-rationale": "$.decision.rationale: must not be an empty string",
    "unknown-extra-field": "unknown field 'notes' is not permitted",
    "unknown-action-name": '$.decision.action.action: "ACTION9" is not one of',
    "bad-boundary-reason": '$.segment.boundary_reason: "bridge_built" is not one of',
    "bad-guid": "$.frame_ref.recording_guid:",
    "negative-row-index": "$.frame_ref.row_index: must be >= 0, got -1",
    "action_role_source-without-line": "$.action_role_source:",
    "bad-rationale-provenance": '$.rationale_provenance: "recovered" is not one of ["annotated"]',
    "schema-version-drift": '$.schema_version: expected the constant "0.1", got "0.2"',
    "action-args-missing-col": "$.last_action.args: missing required field 'col'",
    "turn-zero-null-action-with-result": "$.last_result: expected type null, got object",
    "turn-zero-null-result-with-action": "$.last_action: expected type null, got object",
    "turn-zero-last-action-omitted": "$: missing required field 'last_action'",
    "inline-frame-pixels": "looks like an inlined frame (nested array)",
    "negative-without-corrected-decision": "$: missing required field 'corrected_decision'",
    "negative-with-expectation-held": "$.outcome.expectation_held: expected the constant false",
    "not-json": "not valid JSON",
    "not-an-object": "expected a JSON object, got array",
}


class SchemaDocumentTests(unittest.TestCase):
    def test_schema_loads_and_every_keyword_is_enforced(self):
        schema = validate.load_schema(CORPUS_DIR / "schema.json")
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["properties"]["schema_version"]["const"], "0.1")

    def test_audit_rejects_an_unimplemented_keyword_at_top_level(self):
        with self.assertRaises(validate.UnsupportedKeyword) as ctx:
            validate.SchemaAudit.audit({"type": "object", "maxProperties": 3})
        self.assertIn("maxProperties", str(ctx.exception))

    def test_audit_rejects_an_unimplemented_keyword_nested_in_defs(self):
        schema = {
            "type": "object",
            "properties": {"a": {"$ref": "#/$defs/thing"}},
            "$defs": {"thing": {"type": "array", "uniqueItems": True}},
        }
        with self.assertRaises(validate.UnsupportedKeyword) as ctx:
            validate.SchemaAudit.audit(schema)
        self.assertIn("uniqueItems", str(ctx.exception))

    def test_audit_rejects_an_unimplemented_keyword_nested_under_then(self):
        schema = {"if": {"const": 1}, "then": {"type": "string", "maxLength": 4}}
        with self.assertRaises(validate.UnsupportedKeyword) as ctx:
            validate.SchemaAudit.audit(schema)
        self.assertIn("maxLength", str(ctx.exception))


class ValidRecordTests(unittest.TestCase):
    def test_every_tier_fixture_passes(self):
        code, output = run_shape_only(str(FIXTURES / "valid"))
        self.assertEqual(code, 0, output)
        self.assertIn("0 error(s)", output)

    def test_all_three_tiers_are_represented(self):
        tiers = set()
        for path in sorted((FIXTURES / "valid").glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    tiers.add(json.loads(line)["tier"])
        self.assertEqual(tiers, {"gold", "silver", "negative"})


class TurnZeroTests(unittest.TestCase):
    """The first decision of an episode has no predecessor, so both fields carry null.

    Three things are asserted together because they are one contract: the record is
    expressible, the keys are still required so a forgotten field errors rather than reading
    as turn 0, and the pair is both-or-neither.
    """

    TURN_ZERO = FIXTURES / "valid" / "gold-bp35-turn-zero.jsonl"

    def test_the_turn_zero_fixture_is_genuinely_both_null(self):
        record = json.loads(self.TURN_ZERO.read_text(encoding="utf-8").splitlines()[0])
        self.assertIsNone(record["last_action"])
        self.assertIsNone(record["last_result"])
        self.assertEqual(record["frame_ref"]["row_index"], 0)

    def test_the_turn_zero_fixture_passes(self):
        code, output = run_shape_only(str(self.TURN_ZERO))
        self.assertEqual(code, 0, output)

    def test_both_fields_stay_required_so_an_omission_is_not_read_as_turn_zero(self):
        schema = validate.load_schema(CORPUS_DIR / "schema.json")
        self.assertIn("last_action", schema["required"])
        self.assertIn("last_result", schema["required"])

    def test_nullability_needs_no_keyword_the_evaluator_cannot_enforce(self):
        """Nullability is a type array, not anyOf/oneOf. load_schema is the real assertion.

        It audits the whole document and raises UnsupportedKeyword on any keyword outside
        IMPLEMENTED_KEYWORDS, so this passing means the turn-0 edit did not reach for one.
        """
        validate.load_schema(CORPUS_DIR / "schema.json")
        raw = json.loads((CORPUS_DIR / "schema.json").read_text(encoding="utf-8"))
        for absent in ("anyOf", "oneOf", "not"):
            self.assertNotIn(absent, validate.IMPLEMENTED_KEYWORDS)
        self.assertEqual(
            raw["properties"]["last_action"]["type"], ["object", "null"]
        )
        self.assertEqual(
            raw["properties"]["last_result"]["type"], ["object", "null"]
        )


class InvalidRecordTests(unittest.TestCase):
    def test_every_invalid_fixture_is_rejected_with_its_own_message(self):
        for name, expected in INVALID_EXPECTATIONS.items():
            with self.subTest(fixture=name):
                path = FIXTURES / "invalid" / f"{name}.jsonl"
                self.assertTrue(path.is_file(), f"missing fixture {path}")
                code, output = run_shape_only(str(path))
                self.assertEqual(code, 1, output)
                self.assertIn(expected, output)

    def test_error_lines_carry_file_and_line_number(self):
        code, output = run_shape_only(str(FIXTURES / "invalid" / "empty-rationale.jsonl"))
        self.assertEqual(code, 1)
        self.assertIn("datasets/decision-steps/fixtures/invalid/empty-rationale.jsonl:1:", output)

    def test_every_invalid_fixture_has_an_expectation(self):
        on_disk = {path.stem for path in (FIXTURES / "invalid").glob("*.jsonl")}
        self.assertEqual(
            on_disk,
            set(INVALID_EXPECTATIONS),
            "fixtures/invalid/ and INVALID_EXPECTATIONS are out of sync",
        )

    def test_bad_rows_are_rejected_not_coerced(self):
        """A directory containing one good and one bad row fails the whole run."""
        code, output = run_shape_only(
            str(FIXTURES / "valid" / "gold-g50t-ghost-construction.jsonl"),
            str(FIXTURES / "invalid" / "wrong-type-level.jsonl"),
        )
        self.assertEqual(code, 1, output)
        self.assertIn("2 record(s), 1 error(s)", output)


class FrameResolutionTests(unittest.TestCase):
    RECORDINGS = FIXTURES / "recordings"

    def test_resolvable_reference_passes_with_resolution_on(self):
        code, output = run_cli(
            str(FIXTURES / "frame-resolution" / "resolvable.jsonl"),
            "--recordings-dir",
            str(self.RECORDINGS),
        )
        self.assertEqual(code, 0, output)
        self.assertIn("FRAME-REF RESOLUTION: ON", output)

    def test_missing_recording_file(self):
        code, output = run_cli(
            str(FIXTURES / "frame-resolution" / "missing-recording.jsonl"),
            "--recordings-dir",
            str(self.RECORDINGS),
        )
        self.assertEqual(code, 1)
        self.assertIn("recording not found at", output)

    def test_row_index_out_of_range(self):
        code, output = run_cli(
            str(FIXTURES / "frame-resolution" / "row-out-of-range.jsonl"),
            "--recordings-dir",
            str(self.RECORDINGS),
        )
        self.assertEqual(code, 1)
        self.assertIn("is out of range for", output)
        self.assertIn("last valid index is 3", output)

    def test_field_absent_on_the_resolved_row(self):
        code, output = run_cli(
            str(FIXTURES / "frame-resolution" / "missing-field-on-row.jsonl"),
            "--recordings-dir",
            str(self.RECORDINGS),
        )
        self.assertEqual(code, 1)
        self.assertIn("has no field 'frame'", output)

    absent_dir = staticmethod(absent_recordings_dir)

    def test_absent_recordings_dir_is_announced_as_skipped_in_the_summary(self):
        code, output = run_cli(
            str(FIXTURES / "frame-resolution" / "missing-recording.jsonl"),
            "--recordings-dir",
            self.absent_dir(),
        )
        self.assertEqual(code, 0, output)
        self.assertIn("FRAME-REF RESOLUTION: SKIPPED", output)

    def test_require_frame_resolution_fails_when_recordings_are_absent(self):
        code, output = run_cli(
            str(FIXTURES / "valid"),
            "--recordings-dir",
            self.absent_dir(),
            "--require-frame-resolution",
        )
        self.assertEqual(code, 2)
        self.assertIn("--require-frame-resolution was set", output)


class DottedFramePathTests(unittest.TestCase):
    """frame_ref.field is a dotted path, because live API rows nest the frame at data.frame.

    The stand-in recording these resolve against mirrors the live row shape (timestamp + data,
    frame a list of grids) rather than the flat one the older fixtures use, so both forms stay
    covered: flat single-segment by FrameResolutionTests, nested by these.
    """

    RECORDINGS = FIXTURES / "recordings"
    NESTED = FIXTURES / "frame-resolution"

    def _run(self, name: str) -> tuple[int, str]:
        return run_cli(str(self.NESTED / f"{name}.jsonl"), "--recordings-dir", str(self.RECORDINGS))

    def test_dotted_path_resolves(self):
        code, output = self._run("nested-resolvable")
        self.assertEqual(code, 0, output)
        self.assertIn("FRAME-REF RESOLUTION: ON", output)

    def test_a_missing_segment_names_the_segment_and_its_container(self):
        code, output = self._run("nested-path-miss")
        self.assertEqual(code, 1)
        self.assertIn("has no field 'frames' under 'data'", output)
        self.assertIn("path 'data.frames' (segment 2 of 2)", output)
        self.assertIn("keys there: action_input", output)

    def test_descending_into_a_non_object_is_rejected(self):
        code, output = self._run("nested-descend-into-non-object")
        self.assertEqual(code, 1)
        self.assertIn("cannot descend into 'data.frame'", output)
        self.assertIn("it is array, not an object", output)

    def test_an_empty_frame_list_is_rejected_not_treated_as_resolved(self):
        """data.frame: [] resolves as a path and still has no frame in it.

        Five rows of the real 1,030-row bp35 recording are exactly this shape (indices 215,
        370, 390, 572 and 807). A path-resolved check alone would pass them and every consumer
        would then fail selecting the last grid.
        """
        code, output = self._run("nested-empty-frame-list")
        self.assertEqual(code, 1)
        self.assertIn("resolved to an empty list", output)

    def test_the_flat_form_is_just_a_one_segment_path(self):
        """No churn: a field with no dot still means a top-level key."""
        errors = validate.FrameResolver._walk(
            {"frame": [[0]]}, "frame", "$.frame_ref", 0, Path("x.ndjson")
        )
        self.assertEqual(errors, [])


class RealRecordingTests(unittest.TestCase):
    """The gold fixtures cite real guids; when step 3 has run, they must really resolve.

    Skipped rather than failed when the recordings are absent — they are gitignored and 200 MB.
    """

    RECORDINGS = CORPUS_DIR / "v0" / "recordings"
    GOLD = [
        "gold-bp35-turn-zero",
        "gold-bp35-undo-compare",
        "gold-g50t-ghost-construction",
    ]

    def test_gold_fixtures_resolve_against_the_re_pulled_recordings(self):
        if not self.RECORDINGS.is_dir():
            self.skipTest(f"no recordings at {self.RECORDINGS}; run tools/replay_scrape.py known")
        targets = [str(FIXTURES / "valid" / f"{name}.jsonl") for name in self.GOLD]
        code, output = run_cli(*targets, "--require-frame-resolution")
        self.assertEqual(code, 0, output)
        self.assertIn("FRAME-REF RESOLUTION: ON", output)


class CliTests(unittest.TestCase):
    def test_missing_target_is_a_usage_error_not_a_pass(self):
        code, output = run_cli(str(FIXTURES / "does-not-exist.jsonl"))
        self.assertEqual(code, 2)
        self.assertIn("no such file or directory", output)

    def test_directory_targets_are_searched_recursively(self):
        code, output = run_shape_only(str(FIXTURES / "valid"))
        self.assertEqual(code, 0, output)
        self.assertIn("5 file(s), 6 record(s)", output)


if __name__ == "__main__":
    unittest.main()
