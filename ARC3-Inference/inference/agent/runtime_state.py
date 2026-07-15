"""Structured runtime state shared with created Python tools."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from inference.utils.grid_utils import format_grid_ascii


RUNTIME_STATE_FILENAME = "tool_runtime_state.json"


@dataclass(frozen=True)
class Frame:
    grid: tuple[tuple[int, ...], ...]
    step: int
    level: int

    @property
    def shape(self) -> tuple[int, int]:
        rows = len(self.grid)
        cols = max((len(row) for row in self.grid), default=0)
        return rows, cols

    @property
    def ascii(self) -> str:
        return format_grid_ascii(self.grid)

    def __str__(self) -> str:
        rows, cols = self.shape
        return (
            f"Level: {self.level}\n"
            f"Step: {self.step}\n"
            f"Grid shape: {rows} x {cols}\n"
            f"Grid contents:\n{self.ascii}"
        )


@dataclass(frozen=True)
class HistoryEntry:
    action: str
    frame: Frame


def normalize_grid(raw: Any) -> tuple[tuple[int, ...], ...]:
    if not isinstance(raw, (list, tuple)):
        return ()
    rows: list[tuple[int, ...]] = []
    for row in raw:
        if not isinstance(row, (list, tuple)):
            continue
        cells: list[int] = []
        for cell in row:
            try:
                cells.append(int(cell))
            except (TypeError, ValueError):
                cells.append(0)
        rows.append(tuple(cells))
    return tuple(rows)


def frame_from_payload(payload: Any) -> Frame | None:
    if not isinstance(payload, dict):
        return None
    try:
        step = max(0, int(payload.get("step", 0) or 0))
    except (TypeError, ValueError):
        step = 0
    try:
        level = max(1, int(payload.get("level", 1) or 1))
    except (TypeError, ValueError):
        level = 1
    return Frame(
        grid=normalize_grid(payload.get("grid")),
        step=step,
        level=level,
    )


def frame_to_payload(frame: Frame | None) -> dict[str, Any] | None:
    if frame is None:
        return None
    return {
        "grid": [list(row) for row in frame.grid],
        "step": frame.step,
        "level": frame.level,
    }


def history_entry_from_payload(payload: Any) -> HistoryEntry | None:
    if not isinstance(payload, dict):
        return None
    frame = frame_from_payload(payload.get("frame"))
    if frame is None:
        return None
    return HistoryEntry(action=str(payload.get("action", "")).strip(), frame=frame)


def history_entry_to_payload(entry: HistoryEntry) -> dict[str, Any]:
    return {
        "action": entry.action,
        "frame": frame_to_payload(entry.frame),
    }


def load_runtime_state(path: Path) -> tuple[Frame | None, list[HistoryEntry]]:
    if not path.exists():
        return None, []
    payload = json.loads(path.read_text(encoding="utf-8"))
    current_frame = frame_from_payload(payload.get("current_frame"))
    history_entries = [
        entry
        for raw_entry in payload.get("history", [])
        for entry in [history_entry_from_payload(raw_entry)]
        if entry is not None
    ]
    return current_frame, history_entries


def write_runtime_state(
    path: Path,
    *,
    current_frame: Frame | None,
    history: list[HistoryEntry],
    last_animation: dict[str, Any] | None = None,
    frame_stats: dict[str, Any] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "current_frame": frame_to_payload(current_frame),
        "history": [history_entry_to_payload(entry) for entry in history],
    }
    # Only present in full-frame mode; their absence is what makes a state file
    # read back as last-frame (see load_last_animation / load_frame_stats).
    if last_animation is not None:
        payload["last_animation"] = last_animation
    if frame_stats is not None:
        payload["frame_stats"] = frame_stats
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def load_frame_stats(path: Path) -> dict[str, Any]:
    """Running per-action animation gauge for the game so far; {} in last-frame
    mode or for older states, so the sandbox global is just an empty dict then."""
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    stats = payload.get("frame_stats")
    return stats if isinstance(stats, dict) else {}


def load_last_animation(path: Path) -> tuple[int, list[tuple[str, list[Frame]]]]:
    """(total_actions, [(action, [frames]), ...]) for full-frame mode.

    Returns (0, []) when the state has no last_animation -- i.e. last-frame mode,
    or any older state file -- so callers degrade to last-frame automatically."""
    if not path.exists():
        return 0, []
    payload = json.loads(path.read_text(encoding="utf-8"))
    anim = payload.get("last_animation")
    if not isinstance(anim, dict):
        return 0, []
    entries: list[tuple[str, list[Frame]]] = []
    for item in anim.get("entries", []):
        if not isinstance(item, dict):
            continue
        frames = [f for f in (frame_from_payload(p) for p in item.get("frames", [])) if f is not None]
        entries.append((str(item.get("action", "")), frames))
    return int(anim.get("total_actions", 0) or 0), entries
