#!/usr/bin/env python3
"""Learn a small cross-game predicate ledger from live ARC3 action events.

The worker is intentionally separate from the gameplay process. It reads compact
summaries derived from ``*_events.jsonl`` files, calls a CPU-hosted
OpenAI-compatible model, and atomically publishes a bounded JSON ledger. The main
agent only reads that ledger when ``ARC3_COMMON_THEMES_PATH`` is explicitly set.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any


SYSTEM_PROMPT = """You maintain a tiny transfer-learning ledger for unrelated grid games.
Infer only generic visual/gameplay themes and predicates that could help a different game.
Rules:
- Every claim must cite at least two distinct support_games from the supplied observations.
- Never include exact coordinates, board dumps, game-specific solutions, or a game identifier in statement text.
- Do not claim a rule is universal. Use confidence low, medium, or high.
- Prefer testable predicates such as 'if an edge strip changes while interior components stay fixed, treat it as possible HUD'.
- Contradictions or common traps belong in cautions.
- Return JSON only: {"themes": [...], "predicates": [...], "cautions": [...]}. Each item is
  {"statement": string, "support_games": [string, ...], "confidence": "low|medium|high"}.
- Keep at most 8 themes, 12 predicates, and 8 cautions, each statement under 240 characters.
"""


def _component_signature(board: list[list[int]]) -> list[dict[str, int]]:
    height = len(board)
    width = len(board[0]) if height else 0
    seen: set[tuple[int, int]] = set()
    components: list[dict[str, int]] = []
    for row in range(height):
        for col in range(width):
            if (row, col) in seen:
                continue
            color = int(board[row][col])
            stack = [(row, col)]
            seen.add((row, col))
            size = 0
            min_r = max_r = row
            min_c = max_c = col
            edge = 0
            while stack:
                r, c = stack.pop()
                size += 1
                min_r, max_r = min(min_r, r), max(max_r, r)
                min_c, max_c = min(min_c, c), max(max_c, c)
                edge += int(r in (0, height - 1) or c in (0, width - 1))
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nr, nc = r + dr, c + dc
                    if (
                        0 <= nr < height
                        and 0 <= nc < width
                        and (nr, nc) not in seen
                        and int(board[nr][nc]) == color
                    ):
                        seen.add((nr, nc))
                        stack.append((nr, nc))
            components.append(
                {
                    "color": color,
                    "pixels": size,
                    "height": max_r - min_r + 1,
                    "width": max_c - min_c + 1,
                    "edge_pixels": edge,
                }
            )
    components.sort(key=lambda item: (-item["pixels"], item["color"]))
    return components[:16]


def _compact_event(game_id: str, event: dict[str, Any], previous_board: list[list[int]] | None) -> dict[str, Any] | None:
    if event.get("type") != "action":
        return None
    board = event.get("board")
    if not isinstance(board, list) or not board or not all(isinstance(row, list) for row in board):
        return None
    changed = None
    edge_changed = None
    if previous_board and len(previous_board) == len(board) and len(previous_board[0]) == len(board[0]):
        height, width = len(board), len(board[0])
        changes = [
            (r, c)
            for r in range(height)
            for c in range(width)
            if previous_board[r][c] != board[r][c]
        ]
        changed = len(changes)
        edge_changed = sum(r in (0, height - 1) or c in (0, width - 1) for r, c in changes)
    return {
        "game_id": game_id,
        "level": event.get("level"),
        "action": event.get("action_display") or event.get("action_name"),
        "reward": event.get("reward"),
        "board_changed": event.get("board_changed"),
        "level_completed": bool(event.get("level_completed")),
        "game_over": bool(event.get("game_over")),
        "changed_cells": changed,
        "changed_edge_cells": edge_changed,
        "components": _component_signature(board),
    }


def _game_id(path: Path) -> str:
    name = path.name
    for suffix in ("_events.jsonl", ".jsonl"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name.rsplit("_p", 1)[0]


def collect_new_observations(events_dir: Path, cursor: dict[str, int]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    observations: list[dict[str, Any]] = []
    updated = dict(cursor)
    for path in sorted(events_dir.rglob("*_events.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        key = str(path.resolve())
        start = min(max(0, int(cursor.get(key, 0))), len(lines))
        parsed: list[dict[str, Any]] = []
        complete_count = 0
        for line in lines:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                break
            if isinstance(value, dict):
                parsed.append(value)
            complete_count += 1
        previous_board = None
        if start > 0:
            for prior in reversed(parsed[:start]):
                if isinstance(prior.get("board"), list):
                    previous_board = prior["board"]
                    break
        for event in parsed[start:]:
            compact = _compact_event(_game_id(path), event, previous_board)
            if compact is not None:
                observations.append(compact)
            if isinstance(event.get("board"), list):
                previous_board = event["board"]
        updated[key] = complete_count
    return observations, updated


def _post_chat(base_url: str, model: str, current: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {"current_ledger": current, "new_observations": observations},
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ],
        "temperature": 0.2,
        "top_p": 0.9,
        "max_tokens": 1200,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        result = json.loads(response.read().decode("utf-8"))
    content = str(result["choices"][0]["message"].get("content") or "")
    start, end = content.find("{"), content.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("sidecar model did not return a JSON object")
    parsed = json.loads(content[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("sidecar ledger is not an object")
    return parsed


def _sanitize(payload: dict[str, Any], observed_games: set[str]) -> dict[str, Any]:
    limits = {"themes": 8, "predicates": 12, "cautions": 8}
    output: dict[str, Any] = {"updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    for key, limit in limits.items():
        items: list[dict[str, Any]] = []
        values = payload.get(key)
        if not isinstance(values, list):
            values = []
        for value in values:
            if not isinstance(value, dict):
                continue
            statement = " ".join(str(value.get("statement") or "").split())[:240]
            support = sorted(
                {
                    str(game).strip()
                    for game in value.get("support_games", [])
                    if str(game).strip() in observed_games
                }
            )
            confidence = str(value.get("confidence") or "low").lower()
            if statement and len(support) >= 2 and confidence in {"low", "medium", "high"}:
                items.append({"statement": statement, "support_games": support, "confidence": confidence})
            if len(items) >= limit:
                break
        output[key] = items
    return output


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return default


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def run_once(args: argparse.Namespace) -> int:
    cursor = _load_json(args.cursor, {})
    if not isinstance(cursor, dict):
        cursor = {}
    observations, updated_cursor = collect_new_observations(args.events_dir, cursor)
    games = {str(item["game_id"]) for item in observations}
    if len(observations) < args.min_events or len(games) < args.min_games:
        _atomic_write(args.cursor, updated_cursor)
        return 0
    current = _load_json(args.output, {})
    if not isinstance(current, dict):
        current = {}
    selected = observations[-args.max_events :]
    learned = _post_chat(args.base_url, args.model, current, selected)
    _atomic_write(args.output, _sanitize(learned, games))
    _atomic_write(args.cursor, updated_cursor)
    return len(selected)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cursor", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:1235/v1")
    parser.add_argument("--model", default="Qwen/Qwen3-30B-A3B-GGUF")
    parser.add_argument("--min-events", type=int, default=12)
    parser.add_argument("--min-games", type=int, default=2)
    parser.add_argument("--max-events", type=int, default=96)
    parser.add_argument("--poll-seconds", type=float, default=20.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    while True:
        try:
            count = run_once(args)
            if count:
                print(f"sidecar learned from {count} observations", flush=True)
        except Exception as exc:
            print(f"sidecar cycle failed: {exc}", flush=True)
        if args.once:
            return 0
        time.sleep(max(1.0, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
