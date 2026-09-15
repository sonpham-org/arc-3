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
without asserting on it fails the suite. Also covers the two replay manifests --
published-replays.json and first-party-replays.json -- for row shape, per-file guid
uniqueness, _provenance.count, .games, .state_counts and (first-party only)
.total_actions all agreeing with the actual rows
they summarise, every first-party row
carrying an attribution, and above all that the two files share no guid, which is the
invariant that keeps each file's provenance claim true of every row in it. And the leaderboard
reference file human-leaderboards.json: its entry shape, that as66 is the only game returning
zero rows, that all 250 rows are WIN at score 100 while the blog's 250 are not, and above all
that no row carries a guid -- the property that makes those runs permanently unfetchable and
this file a measurement rather than a third replay manifest. Those manifest
tests read the committed JSON only and never call the API, so the suite stays green when
three.arcprize.org is not.
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


def finished_episodes(directory):
    """Episode files that are FINISHED records, never segmenter candidates.

    tools/segment.py writes *.candidate.jsonl with the judgment fields absent, so a candidate is
    deliberately not schema-valid -- an unfinished record must never be mistakable for a finished
    one. validate.py does not collect them either; these globs must agree with it.
    """
    return [p for p in sorted(directory.glob("*.jsonl")) if not p.name.endswith(".candidate.jsonl")]


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


class Bp35MoveBudgetTests(unittest.TestCase):
    """The bp35 per-level move budget, asserted against the recording rather than described.

    bp35 increments a move counter on every action including ACTION7 (bp35.py:4528) and zeroes it
    on RESET (bp35.py:4533) and on level change (bp35.py:4543). render_interface loses the level
    when that counter hits a level-dependent budget: 64 for levels 1-6 (bp35.py:4413, :4421), 128
    for 7-9 (bp35.py:4436), 192 for level 10 (bp35.py:4404), where the level number is
    _current_level_index + 1 (bp35.py:4537) and levels_completed is that index.

    The falsifiable part is the "never above" half: the loss checks are exact equality, so a
    reconstructed counter that sails past its budget while the state is still NOT_FINISHED would
    refute the whole reading. Skipped when the gitignored recording is absent.
    """

    RECORDING = (
        CORPUS_DIR / "v0" / "recordings" / "bp35-0a0ad940"
        / "c935ca1b-dfee-4be1-9574-bf4cc80c5b89.ndjson"
    )

    @staticmethod
    def budget(level_index):
        level_number = level_index + 1
        if level_number == 10:
            return 192
        return 64 if level_number <= 6 else 128

    def rows(self):
        if not self.RECORDING.is_file():
            self.skipTest(f"no recording at {self.RECORDING}; run tools/replay_scrape.py known")
        with self.RECORDING.open() as handle:
            return [json.loads(line)["data"] for line in handle]

    def counters(self):
        """Yield (row_index, level_index, counter, state, action) for every executed row.

        Refused rows — frame [] — are skipped: the action never reached the game, so it cannot
        have moved the counter.
        """
        counter = 0
        previous_level = None
        for index, row in enumerate(self.rows()):
            if not (row.get("frame") or []):
                continue
            level = row.get("levels_completed")
            if previous_level is not None and level != previous_level:
                counter = 0
            previous_level = level
            action = (row.get("action_input") or {}).get("id")
            counter = 0 if action == "RESET" else counter + 1
            yield index, level, counter, row.get("state"), action

    def test_no_row_ever_exceeds_its_level_budget(self):
        over = [
            (index, level, counter)
            for index, level, counter, _, _ in self.counters()
            if counter > self.budget(level)
        ]
        self.assertEqual(over, [], "counter passed a budget the source loses at on equality")

    def test_every_row_that_reaches_its_budget_is_a_loss(self):
        at_budget = [
            (index, level, counter, state, action)
            for index, level, counter, state, action in self.counters()
            if counter == self.budget(level)
        ]
        self.assertEqual(
            [(index, action) for index, _, _, _, action in at_budget],
            [(806, "ACTION6"), (936, "ACTION7")],
        )
        for index, _, _, state, _ in at_budget:
            self.assertEqual(state, "GAME_OVER", f"row {index} hit budget without losing")

    def test_undo_spends_from_the_budget_it_does_not_refund_it(self):
        """Row 936 is the load-bearing observation: an ACTION7 that ended the level.

        If undo were free, or refunded the move it reverted, no ACTION7 could ever be the row
        that reaches the budget.
        """
        budget_deaths = [
            (index, action)
            for index, level, counter, state, action in self.counters()
            if counter == self.budget(level) and state == "GAME_OVER"
        ]
        self.assertIn((936, "ACTION7"), budget_deaths)


class RefusedActionRowTests(unittest.TestCase):
    """The five ACTION7-on-a-dead-board rows are refusals, not undos that did nothing.

    win_levels is a per-game constant — 9 on every bp35 row that carries a game state. The rows
    with an empty frame list carry win_levels 0 as well, which no game state can produce, so the
    envelope was never populated. That distinction is what the negative record's outcome.observed
    now asserts, and it is the difference between "retry the undo" and "this action is unavailable
    in this state".
    """

    RECORDING = Bp35MoveBudgetTests.RECORDING
    REFUSED = [215, 370, 390, 572, 807]

    def rows(self):
        if not self.RECORDING.is_file():
            self.skipTest(f"no recording at {self.RECORDING}; run tools/replay_scrape.py known")
        with self.RECORDING.open() as handle:
            return [json.loads(line)["data"] for line in handle]

    def test_empty_frame_rows_are_exactly_the_known_refusals(self):
        rows = self.rows()
        empty = [i for i, row in enumerate(rows) if not (row.get("frame") or [])]
        self.assertEqual(empty, self.REFUSED)

    def test_refused_rows_carry_an_unpopulated_envelope(self):
        rows = self.rows()
        for index in self.REFUSED:
            row = rows[index]
            self.assertEqual((row.get("action_input") or {}).get("id"), "ACTION7")
            self.assertEqual(row.get("state"), "GAME_OVER")
            self.assertEqual(row.get("win_levels"), 0, f"row {index} looks populated")
            self.assertEqual(row.get("levels_completed"), 0)

    def test_every_other_row_carries_the_real_win_levels(self):
        rows = self.rows()
        others = {
            row.get("win_levels")
            for i, row in enumerate(rows)
            if i not in set(self.REFUSED)
        }
        self.assertEqual(others, {9})


class ReplayManifestTests(unittest.TestCase):
    """The two replay manifests, and the one invariant that keeps them worth having.

    published-replays.json claims its rows are "linked from the ARC blog post" and
    first-party-replays.json claims its rows are ours. Those claims only mean something while
    no guid sits in both files, so that disjointness is asserted rather than trusted. Offline
    by design — these read the committed JSON and never call the API, so the suite does not go
    red when three.arcprize.org does.
    """

    PUBLISHED = CORPUS_DIR / "published-replays.json"
    FIRST_PARTY = CORPUS_DIR / "first-party-replays.json"
    ROW_FIELDS = (
        "game_id", "guid", "state", "levels_completed", "actions", "resets", "published_at",
    )

    def load(self, path):
        return json.loads(path.read_text())

    def test_both_manifests_have_the_same_row_shape(self):
        for path in (self.PUBLISHED, self.FIRST_PARTY):
            with self.subTest(manifest=path.name):
                doc = self.load(path)
                self.assertEqual(list(doc), ["_provenance", "replays"])
                for field in ("what", "why", "collected", "count", "caveats", "fields"):
                    self.assertIn(field, doc["_provenance"])
                for index, row in enumerate(doc["replays"]):
                    for field in self.ROW_FIELDS:
                        self.assertIn(field, row, f"{path.name} row {index} lacks {field}")
                    self.assertIn(row["state"], {"WIN", "GAME_OVER", "NOT_FINISHED"})

    def test_each_manifest_count_matches_its_row_count(self):
        """Cheap guard on the real future failure: a row appended, the count left behind."""
        for path in (self.PUBLISHED, self.FIRST_PARTY):
            with self.subTest(manifest=path.name):
                doc = self.load(path)
                self.assertEqual(doc["_provenance"]["count"], len(doc["replays"]))

    def test_each_manifest_games_and_state_counts_match_its_rows(self):
        """Same drift as count, same guard. Both files summarise their own rows in
        _provenance; a summary nobody checks is just a comment that looks like data."""
        for path in (self.PUBLISHED, self.FIRST_PARTY):
            with self.subTest(manifest=path.name):
                doc = self.load(path)
                rows = doc["replays"]
                provenance = doc["_provenance"]
                self.assertEqual(provenance["games"], len({row["game_id"] for row in rows}))
                observed: dict[str, int] = {}
                for row in rows:
                    observed[row["state"]] = observed.get(row["state"], 0) + 1
                self.assertEqual(provenance["state_counts"], dict(sorted(observed.items())))

    def test_first_party_total_actions_matches_its_rows(self):
        """The summary field that actually drifted, now checked like the three that did not.

        total_actions sat at 5480 from 2026-09-15 until the evening of the same day, while the
        rows summed to 6933 -- the 15:20 ET refresh appended dc22 (1320) and ft09 (133), updated
        count, games and state_counts, and left this one behind. The three that stayed correct
        are exactly the three this class already asserted. published-replays.json has no such
        field, so this is first-party only.
        """
        doc = self.load(self.FIRST_PARTY)
        self.assertEqual(
            doc["_provenance"]["total_actions"],
            sum(row["actions"] for row in doc["replays"]),
            "total_actions drifted from the rows it summarises",
        )

    def test_guids_are_unique_within_each_manifest(self):
        for path in (self.PUBLISHED, self.FIRST_PARTY):
            with self.subTest(manifest=path.name):
                guids = [row["guid"] for row in self.load(path)["replays"]]
                self.assertEqual(len(guids), len(set(guids)))

    def test_the_two_manifests_share_no_guid(self):
        published = {row["guid"] for row in self.load(self.PUBLISHED)["replays"]}
        ours = {row["guid"] for row in self.load(self.FIRST_PARTY)["replays"]}
        self.assertEqual(
            published & ours,
            set(),
            "a guid in both manifests makes one file's provenance claim false for that row",
        )

    def test_every_first_party_guid_is_attributed(self):
        """The file exists to carry provenance, so a row with no attribution is a bug."""
        doc = self.load(self.FIRST_PARTY)
        attribution = doc["_provenance"]["attribution"]
        for row in doc["replays"]:
            with self.subTest(guid=row["guid"]):
                self.assertIn(row["guid"], attribution)
                self.assertTrue(attribution[row["guid"]].strip())


class HumanLeaderboardTests(unittest.TestCase):
    """human-leaderboards.json -- the reference measurement, and the limit that makes it one.

    The file exists because published-replays.json's "curated best-of" caveat was an inference
    nobody had measured. These rows are the real best-of it now gets compared against. The one
    property that must never be assumed away: a leaderboard row has a user_name and NO guid, so
    those runs are permanently unfetchable and nothing downstream may try to label or join them.
    Asserted here rather than left in prose, so the day the endpoint starts returning a guid the
    suite says so. Offline by design -- reads the committed JSON, never calls the API.
    """

    LEADERBOARDS = CORPUS_DIR / "human-leaderboards.json"
    ROW_FIELDS = ("user_name", "end_state", "score", "actions", "resets", "published_at")
    GUID_LIKE = ("guid", "replay_guid", "recording_guid", "session_guid", "id", "uuid")

    def load(self):
        return json.loads(self.LEADERBOARDS.read_text())

    def test_provenance_matches_the_shape_the_sibling_manifests_are_held_to(self):
        doc = self.load()
        self.assertEqual(list(doc), ["_provenance", "leaderboards"])
        for field in ("what", "why", "collected", "count", "caveats", "fields"):
            self.assertIn(field, doc["_provenance"])

    def test_every_entry_has_the_declared_shape(self):
        doc = self.load()
        live = {b["game_id"] for b in json.loads((CORPUS_DIR / "current-builds.json").read_text())["builds"]}
        for entry in doc["leaderboards"]:
            with self.subTest(game=entry["game_id"]):
                self.assertEqual(entry["leaderboard_id"], entry["game_id"].split("-")[0])
                self.assertEqual(len(entry["leaderboard_id"]), 4)
                self.assertEqual(entry["row_count"], len(entry["rows"]))
                baseline = entry["baseline_actions"]
                if entry["game_id"] in live:
                    self.assertEqual(entry["baseline_total_actions"], sum(baseline))
                else:
                    self.assertIsNone(baseline, "only as66 is off current-builds.json")
                    self.assertIsNone(entry["baseline_total_actions"])
                for index, row in enumerate(entry["rows"]):
                    self.assertEqual(list(row), list(self.ROW_FIELDS), f"row {index} shape drifted")

    def test_no_leaderboard_row_carries_a_guid(self):
        """The whole reason this file is not a third replay manifest.

        No guid means no /api/sessions document and no recording -- these runs are visible and
        permanently unfetchable. A row that grew one would be a new capability, not a detail.
        """
        for entry in self.load()["leaderboards"]:
            for index, row in enumerate(entry["rows"]):
                with self.subTest(game=entry["game_id"], row=index):
                    for key in row:
                        self.assertNotIn(
                            key.lower(),
                            self.GUID_LIKE,
                            "a leaderboard row grew an identifier; it may now be fetchable, "
                            "and the file's central caveat needs re-reading rather than patching",
                        )

    def test_summary_fields_match_the_rows_they_summarise(self):
        """Same guard as the manifests', and for the same reason: first-party-replays.json's
        total_actions drifted precisely because nothing checked it."""
        doc = self.load()
        provenance, entries = doc["_provenance"], doc["leaderboards"]
        rows = [row for entry in entries for row in entry["rows"]]
        self.assertEqual(provenance["count"], len(entries))
        self.assertEqual(provenance["games"], len({e["game_id"] for e in entries}))
        self.assertEqual(provenance["total_rows"], len(rows))
        observed: dict[str, int] = {}
        for row in rows:
            observed[row["end_state"]] = observed.get(row["end_state"], 0) + 1
        self.assertEqual(provenance["state_counts"], dict(sorted(observed.items())))

    def test_as66_is_the_only_game_with_no_leaderboard_rows(self):
        """Observed 2026-09-15: all 25 current builds return 10, as66 returns 0. Recorded as a
        fact about the endpoint, not as an explanation of why as66 left the lineup."""
        empty = sorted(e["game_id"] for e in self.load()["leaderboards"] if e["row_count"] == 0)
        self.assertEqual(empty, ["as66-821a4dcad9c2"])

    def test_the_leaderboard_is_a_best_of_and_the_blog_set_is_not(self):
        """The measurement the corrected published-replays.json caveat rests on.

        If this ever fails, that caveat is citing numbers the files no longer carry.
        """
        rows = [r for e in self.load()["leaderboards"] for r in e["rows"]]
        self.assertEqual(len(rows), 250)
        self.assertTrue(all(r["end_state"] == "WIN" for r in rows))
        self.assertTrue(all(r["score"] == 100 for r in rows))

        blog = json.loads((CORPUS_DIR / "published-replays.json").read_text())["replays"]
        self.assertEqual(sum(1 for r in blog if r["state"] != "WIN"), 111)
        self.assertEqual({r["published_at"][:10] for r in blog}, {"2026-03-22"})
        self.assertEqual(
            {r["published_at"][:10] for r in rows} & {"2026-03-22"},
            set(),
            "the two sets are disjoint by timestamp; there is no guid to disjoin them by",
        )


class BoundaryReasonTests(unittest.TestCase):
    """boundary_reason is a closed enum; the schema, the docs and the episodes must agree."""

    EXPECTED = [
        "episode_start",
        "level_advance",
        "camera_shift",
        "bridge_edit",
        "ghost_construction",
        "extent_change",
        "death",
        "reset",
        "undo",
    ]

    def _enum(self):
        schema = json.loads((CORPUS_DIR / "schema.json").read_text())
        return schema["properties"]["segment"]["properties"]["boundary_reason"]["enum"]

    def test_enum_is_exactly_the_documented_set(self):
        self.assertEqual(self._enum(), self.EXPECTED)

    def test_every_value_is_documented_in_schema_md(self):
        doc = (CORPUS_DIR / "SCHEMA.md").read_text()
        table = doc.split("## Boundary reasons", 1)
        self.assertEqual(len(table), 2, "SCHEMA.md has no 'Boundary reasons' section")
        for value in self._enum():
            self.assertIn(f"`{value}`", table[1], f"{value} is not documented")

    def test_every_value_used_by_an_episode_or_fixture_is_in_the_enum(self):
        allowed = set(self._enum())
        seen = set()
        roots = [CORPUS_DIR / "v0" / "episodes", FIXTURES / "valid"]
        for root in roots:
            if not root.is_dir():
                continue
            for path in (finished_episodes(root) if root.name == "episodes" else sorted(root.glob("*.jsonl"))):
                for line in path.read_text().splitlines():
                    if line.strip():
                        seen.add(json.loads(line)["segment"]["boundary_reason"])
        self.assertTrue(seen, "no records found to check")
        self.assertEqual(seen - allowed, set())


class RealEpisodeTests(unittest.TestCase):
    """The labelled episodes under v0/episodes are the corpus itself.

    Unlike fixtures/, these cite real rows of real recordings, so they are validated with
    frame resolution REQUIRED — a record that points at a row that does not exist, or at an
    empty frame list, is a labelling bug and must fail here rather than pass quietly.
    """

    EPISODES = CORPUS_DIR / "v0" / "episodes"
    RECORDINGS = CORPUS_DIR / "v0" / "recordings"

    def test_every_episode_validates_with_frame_resolution_required(self):
        if not self.RECORDINGS.is_dir():
            self.skipTest(f"no recordings at {self.RECORDINGS}; run tools/replay_scrape.py known")
        self.assertTrue(self.EPISODES.is_dir(), f"no episodes at {self.EPISODES}")
        code, output = run_cli(str(self.EPISODES), "--require-frame-resolution")
        self.assertEqual(code, 0, output)
        self.assertIn("FRAME-REF RESOLUTION: ON", output)

    def test_shape_is_valid_even_without_the_recordings(self):
        self.assertTrue(self.EPISODES.is_dir(), f"no episodes at {self.EPISODES}")
        code, output = run_shape_only(str(self.EPISODES))
        self.assertEqual(code, 0, output)

    def test_boundary_reason_is_constant_within_a_segment(self):
        """boundary_reason names the event a segment was cut at — one value per segment.id.

        SCHEMA.md states this; without the test the field silently degrades into "what happened
        on this row", which is not what it is called.
        """
        by_segment: dict[str, set[str]] = {}
        for path in finished_episodes(self.EPISODES):
            for line in path.read_text().splitlines():
                if not line.strip():
                    continue
                segment = json.loads(line)["segment"]
                by_segment.setdefault(segment["id"], set()).add(segment["boundary_reason"])
        self.assertTrue(by_segment, "no records found to check")
        for segment_id, reasons in sorted(by_segment.items()):
            with self.subTest(segment=segment_id):
                self.assertEqual(len(reasons), 1, f"{segment_id} carries {sorted(reasons)}")

    def test_negative_records_carry_a_corrected_decision(self):
        found = 0
        for path in finished_episodes(self.EPISODES):
            for line in path.read_text().splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                if record["tier"] == "negative":
                    found += 1
                    self.assertIn("corrected_decision", record, path.name)
                    self.assertFalse(record["outcome"]["expectation_held"], path.name)
        self.assertGreater(found, 0, "no negative-tier records in the corpus")


class RecordingRowReconcileTests(unittest.TestCase):
    """The session API's action/reset totals against the NDJSON row counts.

    rows  = 1 + session.actions + rows submitted while the board was already GAME_OVER
    RESETs = 1 + session.resets

    The leading 1 in both is row 0, which carries full_reset: true and is counted by the API as
    neither. Verified on all five recordings on disk. The third term was bp35-only until
    2026-09-15, when the Boss's second g50t run came back with one: row 347, an ACTION2 sent to a
    board the previous row had already flipped to GAME_OVER, returning an empty frame list. So it
    is neither a bp35 quirk nor an ACTION7 quirk.
    Skipped rather than failed when the recordings are absent — they are gitignored and 270 MB.
    """

    RECORDINGS = CORPUS_DIR / "v0" / "recordings"

    # (game_id, guid, api_actions, api_resets, expected rows submitted while GAME_OVER).
    # A tuple rather than a game_id-keyed dict since 2026-09-15: g50t now has two recordings on
    # disk, the Boss's two runs on the same build, and a game_id key could only hold one.
    EXPECTED = (
        ("bp35-0a0ad940", "c935ca1b-dfee-4be1-9574-bf4cc80c5b89", 1024, 13, 5),
        ("g50t-5849a774", "4f0689d0-7d06-4be7-91ac-31cb9a800b85", 533, 9, 0),
        ("g50t-5849a774", "58483738-cfaf-4e57-8c55-4c9c593bbab5", 536, 8, 1),
        ("cd82-fb555c5d", "496ee425-9705-409f-8410-463a2229627e", 216, 0, 0),
        ("cn04-2fe56bfb", "f714032e-914d-4bb5-bc95-386dfacebca0", 454, None, 0),
    )

    def _tally(self, path):
        rows = resets = dead = 0
        first_is_full_reset = False
        previous_state = None
        with path.open() as handle:
            for index, line in enumerate(handle):
                if not line.strip():
                    continue
                data = json.loads(line)["data"]
                rows += 1
                action_id = (data.get("action_input") or {}).get("id")
                if action_id == "RESET":
                    resets += 1
                if index == 0 and data.get("full_reset"):
                    first_is_full_reset = True
                if previous_state == "GAME_OVER" and action_id != "RESET":
                    dead += 1
                previous_state = data.get("state")
        return rows, resets, dead, first_is_full_reset

    def test_row_counts_reconcile_against_the_session_totals(self):
        if not self.RECORDINGS.is_dir():
            self.skipTest(f"no recordings at {self.RECORDINGS}; run tools/replay_scrape.py known")
        checked = 0
        for game_id, guid, actions, resets, dead_rows in self.EXPECTED:
            path = self.RECORDINGS / game_id / f"{guid}.ndjson"
            if not path.is_file():
                continue
            checked += 1
            with self.subTest(game=game_id, guid=guid):
                rows, reset_rows, dead, first_is_full_reset = self._tally(path)
                self.assertTrue(first_is_full_reset, "row 0 is not the full_reset row")
                self.assertEqual(dead, dead_rows, "rows submitted while GAME_OVER")
                self.assertEqual(rows - 1 - dead, actions, "rows - 1 - dead != session actions")
                if resets is not None:
                    self.assertEqual(reset_rows - 1, resets, "RESET rows - 1 != session resets")
        if checked == 0:
            self.skipTest("none of the expected recordings are on disk")

    def test_no_record_points_at_a_row_submitted_while_dead(self):
        """The five bp35 dead-board rows carry an empty frame list; a frame_ref there is a bug."""
        episodes = CORPUS_DIR / "v0" / "episodes"
        forbidden = {("c935ca1b-dfee-4be1-9574-bf4cc80c5b89", row) for row in (215, 370, 390, 572, 807)}
        for path in finished_episodes(episodes):
            for line in path.read_text().splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                reference = record["frame_ref"]
                self.assertNotIn(
                    (reference["recording_guid"], reference["row_index"]),
                    forbidden,
                    f"{path.name} points frame_ref at a dead-board row with no frame",
                )


class CurrentBuildTests(unittest.TestCase):
    """Boss directive 15-Sep-2026: a run is only usable if its build is still the live build.

    ls20 in the ARC-3 preview is not the ls20 that ships now, so a replay on a replaced build is
    a replay of a different game whatever its date. Build id is the checkable form of that rule.
    current-builds.json is a dated snapshot; these tests read it offline and never call the API.
    """

    BUILDS = CORPUS_DIR / "current-builds.json"
    EPISODES = CORPUS_DIR / "v0" / "episodes"

    def _live(self):
        doc = json.loads(self.BUILDS.read_text())
        return {b["game_id"] for b in doc["builds"]}

    def test_snapshot_holds_twenty_five_builds_with_source(self):
        live = self._live()
        self.assertEqual(len(live), 25)
        src = REPO_ROOT / "docs" / "static" / "games" / "src"
        missing = sorted(g for g in live if not (src / g).is_dir())
        self.assertEqual(missing, [], "current builds with no game source in the repo")

    def test_every_labelled_record_is_on_a_current_build(self):
        """The corpus itself. A record on a replaced build documents a game that no longer exists."""
        live = self._live()
        checked = 0
        for path in finished_episodes(self.EPISODES):
            for number, line in enumerate(path.read_text().splitlines(), 1):
                if not line.strip():
                    continue
                checked += 1
                record = json.loads(line)
                with self.subTest(file=path.name, line=number):
                    self.assertIn(record["game_id"], live)
        self.assertGreater(checked, 0, "no labelled records found to check")

    def test_manifest_eligibility_is_reported_not_silently_assumed(self):
        """Both manifests legitimately carry ineligible rows; the counts must stay stated.

        published-replays.json is a record of what the blog linked and first-party-replays.json of
        what the Boss played -- neither is filtered, on purpose. This asserts the split is the one
        the README documents, so a lineup change surfaces here rather than in a labelling pass.
        """
        live = self._live()
        for name, expected_eligible, expected_total in (
            ("published-replays.json", 100, 250),
            ("first-party-replays.json", 21, 26),
        ):
            doc = json.loads((CORPUS_DIR / name).read_text())
            replays = doc.get("replays") or doc.get("rows") or doc.get("items")
            eligible = [r for r in replays if r["game_id"] in live]
            with self.subTest(manifest=name):
                self.assertEqual(len(replays), expected_total)
                self.assertEqual(
                    len(eligible),
                    expected_eligible,
                    "eligibility drifted -- re-snapshot current-builds.json and update the README",
                )


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
