from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


CURATOR_TIMESTAMP = re.compile(r"Ledger revision (\d+), updated [^;]+;")


def normalized(row: dict) -> bytes:
    clone = json.loads(json.dumps(row))
    for message in clone.get("messages", []):
        content = message.get("content")
        blocks = content if isinstance(content, list) else [content]
        for block in blocks:
            if isinstance(block, str):
                message["content"] = CURATOR_TIMESTAMP.sub(r"Ledger revision \1, updated <TIMESTAMP>;", block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                block["text"] = CURATOR_TIMESTAMP.sub(
                    r"Ledger revision \1, updated <TIMESTAMP>;", block["text"]
                )
    return json.dumps(clone, sort_keys=True, separators=(",", ":")).encode("utf-8")


def first_rows(directory: Path) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for path in directory.glob("*_requests.jsonl"):
        with path.open(encoding="utf-8") as handle:
            first = handle.readline()
        if first:
            result[path.name] = json.loads(first)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("gcp", type=Path)
    parser.add_argument("kaggle", type=Path)
    args = parser.parse_args()
    left, right = first_rows(args.gcp), first_rows(args.kaggle)
    names = sorted(set(left) | set(right))
    mismatches = []
    for name in names:
        if name not in left or name not in right:
            mismatches.append({"file": name, "reason": "missing on one side"})
            continue
        a, b = normalized(left[name]), normalized(right[name])
        if a != b:
            mismatches.append(
                {
                    "file": name,
                    "gcp_sha256": hashlib.sha256(a).hexdigest(),
                    "kaggle_sha256": hashlib.sha256(b).hexdigest(),
                }
            )
    report = {"compared": len(names), "matched": len(names) - len(mismatches), "mismatches": mismatches}
    print(json.dumps(report, indent=2))
    raise SystemExit(1 if mismatches else 0)


if __name__ == "__main__":
    main()

