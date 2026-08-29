"""Generate a reproducible, non-semantic audit of the public ARC3 game sources.

This intentionally records only mechanically observable source properties. It does
not infer a game's objective or reasoning demands from names, thumbnails, or code
shape; those claims require controlled play or verified replays.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs" / "static" / "games" / "manifest.json"
OUTPUT_PATH = ROOT / "research" / "official-public-surface-audit.json"
ACTION_PATTERN = re.compile(r"(?:GameAction\.)?ACTION([1-7])")
RANDOM_PATTERN = re.compile(r"\b(?:random|np\.random|numpy\.random)\b")


def git_revision() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or None


def source_record(entry: dict[str, object]) -> dict[str, object]:
    source_path = (
        ROOT
        / "docs"
        / "static"
        / "games"
        / "src"
        / str(entry["id"])
        / str(entry["src_file"])
    )
    raw = source_path.read_bytes()
    text = raw.decode("utf-8")
    tree = ast.parse(text, filename=str(source_path))
    functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    action_ids = sorted({int(value) for value in ACTION_PATTERN.findall(text)})
    tags = [str(tag) for tag in entry.get("tags", [])]
    return {
        "id": entry["id"],
        "title": entry["title"],
        "source": str(source_path.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_bytes": len(raw),
        "source_lines": text.count("\n") + 1,
        "class_count": len(classes),
        "function_count": len(functions),
        "declares_step": "step" in functions,
        "declares_render": "render" in functions,
        "action_ids_referenced": action_ids,
        "input_tags": tags,
        "click_surface": any("click" in tag for tag in tags) or "ACTION6" in text,
        "undo_surface": "ACTION7" in text,
        "randomness_reference": bool(RANDOM_PATTERN.search(text)),
        "multi_level_reference": "next_level" in text,
        "game_over_reference": "game_over" in text,
        "default_fps": entry.get("default_fps"),
        "tile_scale": entry.get("tile_scale"),
    }


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    official = [entry for entry in manifest if entry.get("official") is True]
    records = [source_record(entry) for entry in official]
    action_histogram = Counter(
        action
        for record in records
        for action in record["action_ids_referenced"]
    )
    payload = {
        "schema_version": 1,
        "generated_from_commit": git_revision(),
        "manifest": str(MANIFEST_PATH.relative_to(ROOT)).replace("\\", "/"),
        "scope": "Official public demonstration games present in the browser manifest.",
        "interpretation_boundary": (
            "Static source-surface facts only. This file does not label objectives, "
            "mechanics, or cognitive demands; those require source-plus-play or replay evidence."
        ),
        "counts": {
            "official_games": len(records),
            "click_surface": sum(record["click_surface"] for record in records),
            "undo_surface": sum(record["undo_surface"] for record in records),
            "randomness_reference": sum(
                record["randomness_reference"] for record in records
            ),
            "multi_level_reference": sum(
                record["multi_level_reference"] for record in records
            ),
            "action_reference_histogram": {
                str(action): action_histogram[action] for action in sorted(action_histogram)
            },
        },
        "games": records,
    }
    OUTPUT_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUTPUT_PATH.relative_to(ROOT)} ({len(records)} games)")


if __name__ == "__main__":
    main()
