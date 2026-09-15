#!/usr/bin/env python3.13
"""
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: Validate decision-step corpus JSONL against datasets/decision-steps/schema.json and
reject — never coerce — malformed records. Reads one or more .jsonl files, or directories that
are searched recursively for .jsonl — excluding *.candidate.jsonl, the unfinished output of
tools/segment.py — and emits one human-actionable message per failing field,
prefixed with file, 1-based line number, and a JSON-pointer-ish path into the record. Exits
non-zero if any record fails. Runs three layers of checking: (1) a self-contained draft
2020-12 evaluator covering exactly the keyword subset schema.json uses, which raises
UnsupportedKeyword at load time rather than silently under-validating if the schema ever grows
a keyword this engine cannot enforce; (2) a domain rule forbidding inlined frame pixels, since
the corpus references frames by (recording_guid, row_index, field) and never copies them;
(3) optional frame-reference resolution against the gitignored NDJSON recordings, which is
reported as SKIPPED in the summary line when the recordings are absent so a green run can
never be mistaken for a fully resolved one.
Contract: docs/trace-findings/2026-09-14-decision-step-corpus-v0-plan.md section 6.
Dependencies: Python 3.13 standard library only. No third-party packages by design — the
repo's scripts/test_*.py suite is stdlib-under-3.13 and this stays consistent with it.
SRP/DRY check: Pass — searched the repo before writing. research/benchmark-game.schema.json is
a schema document with no validator behind it; scripts/validate_idea_diversity.py is a TF-IDF
ledger collision detector, unrelated; railway/catalog_schema.sql is SQL DDL;
scripts/run_catalog.py validates run catalogs against hand-rolled rules for a different record
shape with no reusable schema engine. No JSON Schema evaluator and no record validator exists
in this repo to reuse, and `jsonschema` is not a dependency of any package here.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA = Path(__file__).resolve().parent / "schema.json"
DEFAULT_RECORDINGS = Path(__file__).resolve().parent / "v0" / "recordings"

# Keywords this engine enforces. Anything outside these two sets is a hard load-time error.
IMPLEMENTED_KEYWORDS = {
    "$ref",
    "additionalProperties",
    "allOf",
    "const",
    "else",
    "enum",
    "if",
    "items",
    "minItems",
    "minLength",
    "minimum",
    "pattern",
    "properties",
    "required",
    "then",
    "type",
}
# Annotation-only keywords: carry no assertion, safe to ignore.
ANNOTATION_KEYWORDS = {"$schema", "$id", "$comment", "title", "description", "examples"}

JSON_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


class UnsupportedKeyword(Exception):
    """Raised when schema.json uses a keyword this evaluator does not enforce."""


class SchemaAudit:
    """Recursively assert that every keyword in a schema document is enforced.

    Without this, adding a keyword to schema.json that the evaluator ignores would silently
    weaken validation while every test stayed green. Applied to the whole document at load
    time, including $defs, so unexercised branches are covered too.
    """

    SCHEMA_VALUED = ("if", "then", "else", "additionalProperties", "items")
    SCHEMA_MAP_VALUED = ("properties", "$defs")
    SCHEMA_LIST_VALUED = ("allOf",)

    @classmethod
    def audit(cls, schema: Any, path: str = "#") -> None:
        if isinstance(schema, bool):
            return
        if not isinstance(schema, dict):
            raise UnsupportedKeyword(f"{path}: schema must be an object or boolean")
        for key in schema:
            if key in ANNOTATION_KEYWORDS or key in IMPLEMENTED_KEYWORDS or key == "$defs":
                continue
            raise UnsupportedKeyword(
                f"{path}: keyword {key!r} is not enforced by this evaluator. "
                f"Implement it in validate.py or remove it from the schema; leaving it in "
                f"would validate less than the schema claims."
            )
        for key in cls.SCHEMA_VALUED:
            if key in schema:
                cls.audit(schema[key], f"{path}/{key}")
        for key in cls.SCHEMA_MAP_VALUED:
            for name, sub in schema.get(key, {}).items():
                cls.audit(sub, f"{path}/{key}/{name}")
        for key in cls.SCHEMA_LIST_VALUED:
            for index, sub in enumerate(schema.get(key, [])):
                cls.audit(sub, f"{path}/{key}/{index}")


def load_schema(path: Path) -> dict:
    schema = json.loads(path.read_text(encoding="utf-8"))
    SchemaAudit.audit(schema)
    return schema


def _type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if value is None:
        return "null"
    return type(value).__name__


def _matches_type(value: Any, expected: str) -> bool:
    # JSON has no bool/int distinction in Python's type system; JSON Schema does.
    if expected == "boolean":
        return isinstance(value, bool)
    if expected in ("integer", "number") and isinstance(value, bool):
        return False
    return isinstance(value, JSON_TYPES[expected])


def _resolve_ref(ref: str, root: dict) -> dict:
    if not ref.startswith("#/"):
        raise UnsupportedKeyword(f"only local '#/...' $ref is supported, got {ref!r}")
    node: Any = root
    for token in ref[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        node = node[token]
    return node


def validate_instance(value: Any, schema: Any, root: dict, path: str) -> list[str]:
    """Return a list of human-readable assertion failures for `value` against `schema`."""
    if schema is True:
        return []
    if schema is False:
        return [f"{path}: no value is allowed here"]

    errors: list[str] = []

    if "$ref" in schema:
        errors.extend(validate_instance(value, _resolve_ref(schema["$ref"], root), root, path))

    if "type" in schema:
        expected = schema["type"]
        options = expected if isinstance(expected, list) else [expected]
        if not any(_matches_type(value, option) for option in options):
            return errors + [
                f"{path}: expected type {' or '.join(options)}, got {_type_name(value)}"
            ]

    if "const" in schema and value != schema["const"]:
        errors.append(
            f"{path}: expected the constant {json.dumps(schema['const'])}, "
            f"got {json.dumps(value)}"
        )

    if "enum" in schema and value not in schema["enum"]:
        allowed = ", ".join(json.dumps(item) for item in schema["enum"])
        errors.append(f"{path}: {json.dumps(value)} is not one of [{allowed}]")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            if schema["minLength"] == 1:
                errors.append(f"{path}: must not be an empty string")
            else:
                errors.append(
                    f"{path}: must be at least {schema['minLength']} characters, "
                    f"got {len(value)}"
                )
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(
                f"{path}: {json.dumps(value)} does not match the required pattern "
                f"{schema['pattern']}"
            )

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: must be >= {schema['minimum']}, got {value}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(
                f"{path}: must have at least {schema['minItems']} items, got {len(value)}"
            )
        if "items" in schema:
            for index, item in enumerate(value):
                errors.extend(
                    validate_instance(item, schema["items"], root, f"{path}[{index}]")
                )

    if isinstance(value, dict):
        for name in schema.get("required", []):
            if name not in value:
                errors.append(f"{path}: missing required field {name!r}")
        properties = schema.get("properties", {})
        for name, sub_schema in properties.items():
            if name in value:
                errors.extend(
                    validate_instance(value[name], sub_schema, root, f"{path}.{name}")
                )
        if "additionalProperties" in schema:
            extra = [name for name in value if name not in properties]
            additional = schema["additionalProperties"]
            if additional is False:
                for name in sorted(extra):
                    errors.append(
                        f"{path}: unknown field {name!r} is not permitted "
                        f"(schema sets additionalProperties: false)"
                    )
            else:
                for name in sorted(extra):
                    errors.extend(
                        validate_instance(value[name], additional, root, f"{path}.{name}")
                    )

    for index, sub_schema in enumerate(schema.get("allOf", [])):
        errors.extend(validate_instance(value, sub_schema, root, path))

    if "if" in schema:
        branch = "then" if not validate_instance(value, schema["if"], root, path) else "else"
        if branch in schema:
            errors.extend(validate_instance(value, schema[branch], root, path))

    return errors


def find_inline_pixels(value: Any, path: str) -> list[str]:
    """Reject any nested array-of-arrays: frames are referenced, never copied in as pixels.

    Section 6 of the plan makes this its own acceptance criterion. additionalProperties: false
    already blocks it structurally, but this produces the message that says why.
    """
    errors: list[str] = []
    if isinstance(value, dict):
        for name, sub in value.items():
            errors.extend(find_inline_pixels(sub, f"{path}.{name}"))
    elif isinstance(value, list):
        if any(isinstance(item, list) for item in value):
            errors.append(
                f"{path}: looks like an inlined frame (nested array). Frames are referenced "
                f"by frame_ref (recording_guid, row_index, field) and are never copied into "
                f"the corpus as pixels."
            )
        else:
            for index, item in enumerate(value):
                errors.extend(find_inline_pixels(item, f"{path}[{index}]"))
    return errors


class FrameResolver:
    """Resolve frame_ref tuples against the NDJSON recordings, with a small line cache.

    Recordings are 70-140 MB apiece and gitignored, so this is opt-in on the directory
    existing. row_index is zero-based.

    `field` is a **dotted path** into the row, not a flat key: live API rows nest the frame at
    `data.frame`, so a flat `"frame"` resolves against nothing. A single-segment path is just a
    top-level key, so the flat form keeps working unchanged. See
    SCHEMA.md#frame-references for the path convention and for which grid in the list is
    "the frame".

    An empty list at the resolved path is rejected. Five rows of the real bp35 recording carry
    `data.frame: []`, and on those the path resolves while there is no grid to select — a
    "did it resolve" check alone would pass them and every consumer would then fail on
    `frame[-1]`. That is exactly the false-green shape this repo has been burned by before.
    """

    def __init__(self, recordings_dir: Path) -> None:
        self.recordings_dir = recordings_dir
        self._lines: dict[Path, list[str]] = {}

    def _read(self, path: Path) -> list[str]:
        if path not in self._lines:
            self._lines[path] = path.read_text(encoding="utf-8").splitlines()
        return self._lines[path]

    def check(self, record: dict, path: str) -> list[str]:
        ref = record.get("frame_ref")
        game_id = record.get("game_id")
        if not isinstance(ref, dict) or not isinstance(game_id, str):
            return []  # schema layer already reported this
        guid, row_index, field = ref.get("recording_guid"), ref.get("row_index"), ref.get("field")
        if not isinstance(guid, str) or not isinstance(row_index, int) or not isinstance(field, str):
            return []
        ndjson = self.recordings_dir / game_id / f"{guid}.ndjson"
        if not ndjson.is_file():
            return [f"{path}: recording not found at {ndjson}"]
        lines = self._read(ndjson)
        if row_index < 0 or row_index >= len(lines):
            return [
                f"{path}.row_index: {row_index} is out of range for {ndjson} "
                f"({len(lines)} rows, zero-based so the last valid index is {len(lines) - 1})"
            ]
        try:
            row = json.loads(lines[row_index])
        except json.JSONDecodeError as exc:
            return [f"{path}.row_index: row {row_index} of {ndjson} is not valid JSON: {exc}"]
        return self._walk(row, field, path, row_index, ndjson)

    @staticmethod
    def _walk(row: object, field: str, path: str, row_index: int, ndjson: Path) -> list[str]:
        """Walk the dotted `field` path into `row`, naming the segment that failed."""
        segments = field.split(".")
        where = f"row {row_index} of {ndjson}"
        current: object = row
        for depth, segment in enumerate(segments):
            # Say "path 'data.frame' ..." only when there is actually a path to talk about;
            # a one-segment field keeps the original, shorter sentence.
            at = "" if len(segments) == 1 else (
                f"path {field!r} (segment {depth + 1} of {len(segments)}): "
            )
            if not isinstance(current, dict):
                container = "row" if depth == 0 else ".".join(segments[:depth])
                return [
                    f"{path}.field: {where}: {at}cannot descend into {container!r} — "
                    f"it is {_type_name(current)}, not an object"
                ]
            if segment not in current:
                keys = ", ".join(sorted(current)) or "none"
                container = "row" if depth == 0 else ".".join(segments[:depth])
                return [
                    f"{path}.field: {where} has no field {segment!r} under {container!r} "
                    f"({at}keys there: {keys})"
                ]
            current = current[segment]
        if isinstance(current, list) and not current:
            return [
                f"{path}.field: {where}: {field!r} resolved to an empty list — there is no "
                f"frame to select. On the real recordings this happens on rows where the "
                f"engine emitted no frames at all; such a row cannot back a decision step."
            ]
        return []


#: Suffix written by tools/segment.py. A candidate carries only the fields pass A can measure;
#: the judgment fields are absent on purpose, so a candidate is deliberately NOT schema-valid.
#: Collecting one from a directory walk would turn `validate.py v0/episodes` red for a file that
#: is not meant to be finished yet, and — worse — would invite someone to "fix" the candidate by
#: filling the fields with anything that passes. They are skipped by directory walk, and still
#: validated (and rejected) when a caller names one explicitly, so the escape is deliberate
#: rather than silent.
CANDIDATE_SUFFIX = ".candidate.jsonl"


def collect_jsonl(targets: list[Path]) -> list[Path]:
    files: list[Path] = []
    for target in targets:
        if target.is_dir():
            files.extend(
                sorted(
                    path
                    for path in target.rglob("*.jsonl")
                    if not path.name.endswith(CANDIDATE_SUFFIX)
                )
            )
        elif target.is_file():
            files.append(target)
        else:
            raise FileNotFoundError(f"no such file or directory: {target}")
    return files


def validate_file(
    path: Path, schema: dict, resolver: FrameResolver | None
) -> tuple[int, list[str]]:
    """Return (records seen, error messages) for one JSONL file."""
    errors: list[str] = []
    seen = 0
    display = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        seen += 1
        prefix = f"{display}:{lineno}"
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{prefix}: not valid JSON: {exc}")
            continue
        if not isinstance(record, dict):
            errors.append(f"{prefix}: expected a JSON object, got {_type_name(record)}")
            continue
        record_errors = validate_instance(record, schema, schema, "$")
        record_errors.extend(find_inline_pixels(record, "$"))
        if resolver is not None:
            record_errors.extend(resolver.check(record, "$.frame_ref"))
        errors.extend(f"{prefix}: {message}" for message in record_errors)
    return seen, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate ARC-3 decision-step corpus JSONL against schema.json."
    )
    parser.add_argument(
        "targets",
        nargs="+",
        type=Path,
        help=".jsonl files, or directories searched recursively for .jsonl "
             "(*.candidate.jsonl is skipped by a directory walk; name one to validate it)",
    )
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument(
        "--recordings-dir",
        type=Path,
        default=DEFAULT_RECORDINGS,
        help="NDJSON recordings root for frame_ref resolution (default: %(default)s)",
    )
    parser.add_argument(
        "--require-frame-resolution",
        action="store_true",
        help="fail instead of skipping when the recordings directory is absent",
    )
    args = parser.parse_args(argv)

    try:
        schema = load_schema(args.schema)
    except UnsupportedKeyword as exc:
        print(f"SCHEMA ERROR: {exc}", file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError) as exc:
        print(f"SCHEMA ERROR: cannot load {args.schema}: {exc}", file=sys.stderr)
        return 2

    try:
        files = collect_jsonl(args.targets)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.recordings_dir.is_dir():
        resolver: FrameResolver | None = FrameResolver(args.recordings_dir)
        frame_status = f"FRAME-REF RESOLUTION: ON ({args.recordings_dir})"
    elif args.require_frame_resolution:
        print(
            f"ERROR: --require-frame-resolution was set but no recordings directory at "
            f"{args.recordings_dir}",
            file=sys.stderr,
        )
        return 2
    else:
        resolver = None
        frame_status = f"FRAME-REF RESOLUTION: SKIPPED (no recordings at {args.recordings_dir})"

    total_records = 0
    total_errors = 0
    for path in files:
        seen, errors = validate_file(path, schema, resolver)
        total_records += seen
        total_errors += len(errors)
        for message in errors:
            print(message)

    print(
        f"{len(files)} file(s), {total_records} record(s), {total_errors} error(s) | "
        f"{frame_status}"
    )
    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())
