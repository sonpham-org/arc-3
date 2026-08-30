"""Add implemented research games to the browser catalog.

Research metadata is the source of truth.  The generated entries point at the
already-versioned source and thumbnail artifacts under ``docs/static`` and are
kept in a separate ``ai-generated`` category.  Re-running this command is
idempotent: existing entries in that category are replaced, not duplicated.

Usage:
    python scripts/build_ai_generated_catalog.py
    python scripts/build_ai_generated_catalog.py --check
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
METADATA_DIR = ROOT / "research" / "games"
MANIFEST_PATH = ROOT / "docs" / "static" / "games" / "manifest.json"
CATEGORY = "ai-generated"
PUBLISHABLE_STATUSES = {"prototype", "qualified", "sealed"}


def _path_inside_repo(relative: str, *, field: str) -> Path:
    path = (ROOT / relative).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(f"{field} escapes repository root: {relative}") from exc
    if not path.is_file():
        raise FileNotFoundError(f"{field} does not exist: {relative}")
    return path


def _class_name(source: str, source_path: Path) -> str:
    tree = ast.parse(source, filename=str(source_path))
    matches = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            name = base.id if isinstance(base, ast.Name) else None
            if name == "ARCBaseGame":
                matches.append(node.name)
                break
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one ARCBaseGame subclass in {source_path}, found {matches}"
        )
    return matches[0]


def _game_number(metadata_path: Path) -> tuple[int, str]:
    match = re.fullmatch(r"q(\d+)-v\d+\.json", metadata_path.name)
    return (int(match.group(1)), metadata_path.name) if match else (10**9, metadata_path.name)


def research_entries() -> list[dict]:
    entries = []
    for metadata_path in sorted(METADATA_DIR.glob("*.json"), key=_game_number):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("status") not in PUBLISHABLE_STATUSES:
            continue

        code = metadata["game_id"]
        version = metadata["version"]
        game_id = f"{code}-{version}"
        artifacts = metadata["artifacts"]
        source_path = _path_inside_repo(artifacts["source"], field="source")
        thumbnail_path = _path_inside_repo(artifacts["thumbnail"], field="thumbnail")
        if thumbnail_path.suffix.lower() != ".png":
            raise ValueError(f"thumbnail must be PNG: {thumbnail_path}")

        source_bytes = source_path.read_bytes()
        actual_hash = hashlib.sha256(source_bytes).hexdigest()
        expected_hash = artifacts["source_sha256"]
        if actual_hash != expected_hash:
            raise ValueError(
                f"source hash mismatch for {game_id}: {actual_hash} != {expected_hash}"
            )

        mechanics = metadata.get("mechanics", {})
        tags = [
            "ai-generated",
            metadata.get("author_partition", "unknown"),
            mechanics.get("primary", ""),
            *mechanics.get("secondary", []),
        ]
        entry = {
            "id": game_id,
            "title": metadata.get("public_title") or metadata.get("internal_title") or code.upper(),
            "class_name": _class_name(source_bytes.decode("utf-8"), source_path),
            "src_file": source_path.name,
            "tags": list(dict.fromkeys(tag for tag in tags if tag)),
            "default_fps": 6,
            "category": CATEGORY,
            "official": False,
        }
        description = str(mechanics.get("novelty_claim") or "").strip()
        if description:
            entry["description"] = description
        entries.append(entry)

    ids = [entry["id"] for entry in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate AI-generated game ids")
    return entries


def expected_manifest() -> list[dict]:
    current = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    base = [entry for entry in current if entry.get("category") != CATEGORY]
    research = research_entries()
    base_ids = {entry["id"] for entry in base}
    collisions = sorted(base_ids & {entry["id"] for entry in research})
    if collisions:
        raise ValueError(f"AI-generated ids collide with the base catalog: {collisions}")
    return [*base, *research]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if manifest.json does not match the generated catalog",
    )
    args = parser.parse_args()

    current = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    expected = expected_manifest()
    research_count = sum(entry.get("category") == CATEGORY for entry in expected)
    if args.check:
        if current != expected:
            raise SystemExit(
                "AI-generated catalog is stale; run scripts/build_ai_generated_catalog.py"
            )
        print(f"catalog current: {len(expected)} games ({research_count} AI-generated)")
        return

    MANIFEST_PATH.write_text(
        json.dumps(expected, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"{len(expected)} games -> {MANIFEST_PATH}")
    print(f"AI-generated: {research_count}")


if __name__ == "__main__":
    main()
