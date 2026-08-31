"""Regenerate the durable 1,000-game implementation progress checkpoint."""

from __future__ import annotations
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TARGET = 1000


def game_order(path: Path):
    match = re.fullmatch(r"([qa])(\d+)-v\d+\.json", path.name)
    if not match:
        return (2, 10**9, path.name)
    return (0 if match.group(1) == "q" else 1, int(match.group(2)), path.name)


def main():
    records = []
    for path in sorted((ROOT / "research" / "games").glob("*-v1.json"), key=game_order):
        metadata = json.loads(path.read_text(encoding="utf-8"))
        if metadata.get("artifacts", {}).get("source") and (ROOT / metadata["artifacts"]["source"]).exists():
            records.append(metadata)
    batch_files = sorted(path.relative_to(ROOT).as_posix() for path in (ROOT / "research").glob("gpt-batch*-v1.json"))
    progress = {
        "schema_version": 1,
        "target_games": TARGET,
        "implemented_games": len(records),
        "remaining_games": TARGET - len(records),
        "completed_batches": batch_files,
        "game_ids": [record["game_id"] for record in records],
        "qualification_status": "prototype",
    }
    output = ROOT / "research" / "build-progress.json"
    output.write_text(json.dumps(progress, indent=2) + "\n", encoding="utf-8")
    print(f"{len(records)}/{TARGET} implemented; {TARGET - len(records)} remaining -> {output}")


if __name__ == "__main__": main()
