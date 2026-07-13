"""Pre-cache a Hugging Face model snapshot for vLLM startup."""
from __future__ import annotations

import argparse
import json
from typing import Any

from huggingface_hub import snapshot_download


def _patterns(raw: str) -> list[str] | str | None:
    value = (raw or "").strip()
    if not value or value == "[]":
        return None
    try:
        parsed: Any = json.loads(value)
    except json.JSONDecodeError:
        parts = value.split()
        return parts or None
    if not parsed:
        return None
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    return str(parsed)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--allow-patterns", default="")
    parser.add_argument("--ignore-patterns", default="")
    parser.add_argument("--max-workers", type=int, default=8)
    args = parser.parse_args()

    print(f"Downloading {args.model} with max_workers={args.max_workers}", flush=True)
    path = snapshot_download(
        repo_id=args.model,
        allow_patterns=_patterns(args.allow_patterns),
        ignore_patterns=_patterns(args.ignore_patterns),
        max_workers=args.max_workers,
    )
    print(f"Cached {args.model} at {path}", flush=True)


if __name__ == "__main__":
    main()
