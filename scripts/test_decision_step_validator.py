"""
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: Tests for datasets/decision-steps/validate.py against the committed fixture corpus.
Covers, with real fixture files on disk rather than inline literals: every valid-tier record
passing; one invalid fixture per failure mode producing a specific, human-readable message and
a non-zero exit; all three frame-reference resolution failures being distinguishable; the
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
        code, output = run_cli(str(FIXTURES / "valid"))
        self.assertEqual(code, 0, output)
        self.assertIn("0 error(s)", output)

    def test_all_three_tiers_are_represented(self):
        tiers = set()
        for path in sorted((FIXTURES / "valid").glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    tiers.add(json.loads(line)["tier"])
        self.assertEqual(tiers, {"gold", "silver", "negative"})


class InvalidRecordTests(unittest.TestCase):
    def test_every_invalid_fixture_is_rejected_with_its_own_message(self):
        for name, expected in INVALID_EXPECTATIONS.items():
            with self.subTest(fixture=name):
                path = FIXTURES / "invalid" / f"{name}.jsonl"
                self.assertTrue(path.is_file(), f"missing fixture {path}")
                code, output = run_cli(str(path))
                self.assertEqual(code, 1, output)
                self.assertIn(expected, output)

    def test_error_lines_carry_file_and_line_number(self):
        code, output = run_cli(str(FIXTURES / "invalid" / "empty-rationale.jsonl"))
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
        code, output = run_cli(
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

    @staticmethod
    def absent_dir() -> str:
        """A path guaranteed not to exist.

        Deliberately not datasets/decision-steps/v0/recordings: step 3 creates that directory,
        and these two tests assert the *absent* behaviour. Pointing them at real project state
        would make them flip the day the scraper first runs.
        """
        return str(Path(tempfile.mkdtemp(prefix="decision-steps-absent-")) / "no-recordings-here")

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


class CliTests(unittest.TestCase):
    def test_missing_target_is_a_usage_error_not_a_pass(self):
        code, output = run_cli(str(FIXTURES / "does-not-exist.jsonl"))
        self.assertEqual(code, 2)
        self.assertIn("no such file or directory", output)

    def test_directory_targets_are_searched_recursively(self):
        code, output = run_cli(str(FIXTURES / "valid"))
        self.assertEqual(code, 0, output)
        self.assertIn("4 file(s), 5 record(s)", output)


if __name__ == "__main__":
    unittest.main()
