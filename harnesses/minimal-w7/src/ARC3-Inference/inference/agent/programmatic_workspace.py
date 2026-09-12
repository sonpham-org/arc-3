"""Bounded persistent workspace and complete structured history for PRO-LONG mode."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable


LOG_NAME = "game_log.jsonl"
MAX_FILES = 32
MAX_FILE_BYTES = 512_000
MAX_TOTAL_BYTES = 2_000_000
MAX_RETURN_CHARS = 20_000
_FILE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,79}\.(?:py|json|jsonl|txt|md)$")


class WorkspaceError(ValueError):
    pass


def _frame_payload(frame: Any) -> dict[str, Any]:
    grid = [list(row) for row in getattr(frame, "grid", ())]
    digest = hashlib.sha256(
        json.dumps(grid, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "level": max(1, int(getattr(frame, "level", 1))),
        "step": max(0, int(getattr(frame, "step", 0))),
        "frame": digest,
        "grid": grid,
    }


class ProgrammaticWorkspace:
    """Host-owned file service; model code never receives host filesystem access."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _name(self, value: Any, *, writable: bool = False) -> str:
        if not isinstance(value, str) or not _FILE.fullmatch(value):
            raise WorkspaceError("file name must be a flat .py/.json/.jsonl/.txt/.md name")
        if writable and value == LOG_NAME:
            raise WorkspaceError(f"{LOG_NAME} is host-owned and read-only")
        return value

    def _path(self, value: Any, *, writable: bool = False) -> Path:
        return self.root / self._name(value, writable=writable)

    def sync_history(self, history: Iterable[Any]) -> dict[str, Any]:
        """Materialize the complete chronological game history as JSONL.

        Normal operation only appends.  If the runtime history is replaced or a
        partial file is detected, the host repairs the canonical log from the
        runtime state rather than exposing inconsistent memory to the model.
        """
        records = []
        for index, entry in enumerate(history):
            frame = getattr(entry, "frame", None)
            if frame is None:
                continue
            records.append({
                "action_index": index,
                "action": str(getattr(entry, "action", "") or ""),
                **_frame_payload(frame),
            })
        path = self.root / LOG_NAME
        existing: list[dict[str, Any]] = []
        if path.exists():
            try:
                existing = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
            except (OSError, UnicodeError, json.JSONDecodeError):
                existing = []
        def same_observation(old: Any, new: dict[str, Any]) -> bool:
            return isinstance(old, dict) and all(old.get(key) == value for key, value in new.items())

        prefix_ok = len(existing) <= len(records) and all(
            same_observation(old, new)
            for old, new in zip(existing, records)
        )
        if prefix_ok:
            records = [
                {**new, **({"outcome": old["outcome"]} if isinstance(old, dict) and "outcome" in old else {})}
                for old, new in zip(existing, records)
            ] + records[len(existing):]
        if prefix_ok and len(existing) < len(records):
            with path.open("a", encoding="utf-8", newline="\n") as handle:
                for record in records[len(existing):]:
                    handle.write(json.dumps(record, separators=(",", ":"), ensure_ascii=True) + "\n")
            mode = "appended"
        elif prefix_ok:
            mode = "unchanged"
        else:
            path.write_text(
                "".join(json.dumps(record, separators=(",", ":"), ensure_ascii=True) + "\n" for record in records),
                encoding="utf-8",
            )
            mode = "repaired"
        return {"entries": len(records), "mode": mode, "file": LOG_NAME}

    def record_outcomes(
        self,
        history: Iterable[Any],
        outcomes: Iterable[dict[str, Any]],
        final_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Attach real engine outcomes to the matching newest observations."""
        history = list(history)
        outcomes = [dict(item) for item in outcomes if isinstance(item, dict)]
        self.sync_history(history)
        path = self.root / LOG_NAME
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        start = max(0, len(records) - len(outcomes))
        allowed = {
            "action_num", "action", "board_changed", "reward", "level_completed",
            "game_over", "animation_frames", "animation_changed_frames",
            "animation_reminder", "animation_reminder_detail",
        }
        for offset, outcome in enumerate(outcomes):
            index = start + offset
            if index >= len(records):
                break
            clean = {key: outcome.get(key) for key in allowed if key in outcome}
            records[index]["outcome"] = clean
        if records and isinstance(final_summary, dict):
            outcome = records[-1].setdefault("outcome", {})
            for key in ("score", "state", "done", "run_complete", "valid_actions"):
                if key in final_summary:
                    outcome[key] = final_summary.get(key)
        path.write_text(
            "".join(json.dumps(record, separators=(",", ":"), ensure_ascii=True) + "\n" for record in records),
            encoding="utf-8",
        )
        return {"entries": len(records), "outcomes_attached": len(outcomes), "file": LOG_NAME}

    def _model_files(self) -> list[Path]:
        return sorted(
            path for path in self.root.iterdir()
            if path.is_file() and path.name != LOG_NAME and _FILE.fullmatch(path.name)
        )

    def _bounded_text(self, value: Any) -> str:
        if not isinstance(value, str):
            raise WorkspaceError("content must be text")
        encoded = value.encode("utf-8")
        if len(encoded) > MAX_FILE_BYTES:
            raise WorkspaceError(f"content exceeds {MAX_FILE_BYTES} bytes")
        return value

    def write(self, name: Any, content: Any, *, append: bool = False) -> dict[str, Any]:
        path = self._path(name, writable=True)
        content = self._bounded_text(content)
        current = path.read_text(encoding="utf-8") if append and path.exists() else ""
        combined = current + content
        if len(combined.encode("utf-8")) > MAX_FILE_BYTES:
            raise WorkspaceError(f"file exceeds {MAX_FILE_BYTES} bytes")
        files = self._model_files()
        if not path.exists() and len(files) >= MAX_FILES:
            raise WorkspaceError(f"workspace already contains {MAX_FILES} model files")
        other_bytes = sum(item.stat().st_size for item in files if item != path)
        if other_bytes + len(combined.encode("utf-8")) > MAX_TOTAL_BYTES:
            raise WorkspaceError(f"workspace exceeds {MAX_TOTAL_BYTES} model-authored bytes")
        path.write_text(combined, encoding="utf-8")
        return {"ok": True, "name": path.name, "bytes": path.stat().st_size, "append": bool(append)}

    def read(
        self,
        name: Any,
        *,
        start_line: int = 1,
        end_line: int | None = None,
        max_chars: int = 12_000,
    ) -> dict[str, Any]:
        path = self._path(name)
        if not path.is_file():
            raise WorkspaceError(f"workspace file not found: {path.name}")
        start = max(1, int(start_line))
        end = None if end_line is None else max(start, int(end_line))
        cap = min(MAX_RETURN_CHARS, max(1, int(max_chars)))
        lines = path.read_text(encoding="utf-8").splitlines()
        selected = lines[start - 1:end]
        text = "\n".join(selected)
        truncated = len(text) > cap
        if truncated:
            text = text[:cap]
        return {
            "ok": True,
            "name": path.name,
            "start_line": start,
            "end_line": min(len(lines), end if end is not None else len(lines)),
            "total_lines": len(lines),
            "truncated": truncated,
            "text": text,
        }

    def grep(
        self,
        pattern: Any,
        *,
        name: str = LOG_NAME,
        start_line: int = 1,
        end_line: int | None = None,
        max_matches: int = 40,
        max_chars: int = 12_000,
    ) -> dict[str, Any]:
        if not isinstance(pattern, str) or not pattern or len(pattern) > 200:
            raise WorkspaceError("grep pattern must contain 1..200 characters")
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            raise WorkspaceError(f"invalid grep regex: {exc}") from exc
        path = self._path(name)
        if not path.is_file():
            raise WorkspaceError(f"workspace file not found: {path.name}")
        first_line = max(1, int(start_line))
        last_line = None if end_line is None else max(first_line, int(end_line))
        matches = []
        searched_end = first_line - 1
        with path.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                if line_number < first_line:
                    continue
                if last_line is not None and line_number > last_line:
                    break
                searched_end = line_number
                line = raw_line.rstrip("\r\n")
                if regex.search(line):
                    matches.append({"line": line_number, "text": line})
                    if len(matches) >= min(200, max(1, int(max_matches))):
                        break
        cap = min(MAX_RETURN_CHARS, max(1, int(max_chars)))
        while matches and len(json.dumps(matches, ensure_ascii=True)) > cap:
            matches.pop()
        return {
            "ok": True,
            "name": path.name,
            "pattern": pattern,
            "matches": matches,
            "searched_start_line": first_line,
            "searched_end_line": searched_end,
        }

    def list(self) -> dict[str, Any]:
        files = []
        for path in sorted(self.root.iterdir()):
            if path.is_file() and _FILE.fullmatch(path.name):
                files.append({"name": path.name, "bytes": path.stat().st_size, "host_owned": path.name == LOG_NAME})
        return {"ok": True, "files": files}

    def source(self, name: Any) -> dict[str, Any]:
        path = self._path(name)
        if path.suffix != ".py" or not path.is_file():
            raise WorkspaceError("workspace.run requires an existing .py file")
        text = path.read_text(encoding="utf-8")
        if len(text.encode("utf-8")) > MAX_FILE_BYTES:
            raise WorkspaceError("helper source exceeds the workspace file limit")
        return {"ok": True, "name": path.name, "text": text}

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        try:
            op = request.get("op")
            if op == "write":
                return self.write(request.get("name"), request.get("content"), append=bool(request.get("append")))
            if op == "read":
                return self.read(
                    request.get("name"),
                    start_line=request.get("start_line", 1),
                    end_line=request.get("end_line"),
                    max_chars=request.get("max_chars", 12_000),
                )
            if op == "grep":
                return self.grep(
                    request.get("pattern"),
                    name=request.get("name", LOG_NAME),
                    start_line=request.get("start_line", 1),
                    end_line=request.get("end_line"),
                    max_matches=request.get("max_matches", 40),
                    max_chars=request.get("max_chars", 12_000),
                )
            if op == "list":
                return self.list()
            if op == "source":
                return self.source(request.get("name"))
            raise WorkspaceError("unknown workspace operation")
        except (OSError, UnicodeError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)[:300]}
