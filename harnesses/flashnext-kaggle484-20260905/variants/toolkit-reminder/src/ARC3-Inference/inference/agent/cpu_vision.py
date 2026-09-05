# Author: GPT-6 Astra
# Date: 2026-09-05
# PURPOSE: Provide optional CPU vision and a shared bounded host JSON cache for
# completed legacy segmentation results, while keeping segmentation in the guest.
# SRP/DRY check: Pass — reuse the result LRU and ARC symbols; no algorithm duplication.
"""CPU-only observation helpers. No game actions, filesystem, network or GPU use."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import itertools
import json
from typing import Any, Callable

from inference.utils.grid_utils import ARC_COLOR_CHARS
from inference.agent.vision_tools import EXTRA_DOCS, EXTRA_INDEX, run_extra


_SESSIONS = itertools.count(1)
_ORTHOGONAL = ((-1, 0), (0, -1), (0, 1), (1, 0))
_DIAGONAL = _ORTHOGONAL + ((-1, -1), (-1, 1), (1, -1), (1, 1))
_MAX_REGIONS = 64
_MAX_CELLS = 4096
# Bump when the unchanged guest algorithm changes. This pins the parent source,
# including its color-dependent hashes, contours, containment and ordering.
_LEGACY_SEGMENTATION_NAMESPACE = "segment_layer:e9499bd859b4488455b481d3f0577a2c59feba9f78b92f20befc5d294ee09ee0"
_MAX_SEGMENTATION_BYTES = 4 * 1024 * 1024
_DOCS = {
    "objects": (
        "objects(frame='current',connectivity=4) -> list of {id,color,bbox,pixels,point,shape_hash,frame_id}. "
        "frame: current/previous; connectivity:4/8; bbox inclusive; point is a member pixel. "
        "Includes background; IDs are frame-local; shape_hash ignores color/translation."
    ),
    "changes": (
        "changes(details=False) -> status,action,changed_count,bbox,color_transitions,regions,frame IDs. "
        "Latest settled pair only; <=64 regions. details adds <=4096 changed cells. "
        "Boundary/missing counts are null. Equal pixels do not prove a no-op."
    ),
    "help": "help() -> short method index; help('method') -> signature, fields and caveat.",
    **EXTRA_DOCS,
}
_HELP_INDEX = {"objects": "Same-color components.", "changes": "Latest settled pixel differences.",
               "help": "help('method') for compact usage.", **EXTRA_INDEX}


@dataclass(frozen=True)
class _Frame:
    cells: bytes
    rows: int
    cols: int
    step: int
    level: int


@dataclass(frozen=True)
class _Observation:
    frame: _Frame
    frame_id: str


def _integer(value: Any, *, name: str, minimum: int, maximum: int | None = None) -> int:
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        limit = f" through {maximum}" if maximum is not None else " or greater"
        raise ValueError(f"{name} must be an integer {minimum}{limit} (not bool).")
    return value


def _read_frame(raw: Any) -> _Frame | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("Frame must be a mapping or None.")
    grid = raw.get("grid")
    if not isinstance(grid, (list, tuple)) or not 1 <= len(grid) <= 64:
        raise ValueError("Frame requires a nonempty numeric grid with at most 64 rows.")
    if not isinstance(grid[0], (list, tuple)) or not 1 <= len(grid[0]) <= 64:
        raise ValueError("Frame grid requires 1 through 64 columns.")
    cols = len(grid[0])
    cells = bytearray()
    for row in grid:
        if not isinstance(row, (list, tuple)) or len(row) != cols:
            raise ValueError("Frame grid must be rectangular.")
        for value in row:
            cells.append(_integer(value, name="Grid color", minimum=0, maximum=15))
    return _Frame(
        bytes(cells), len(grid), cols,
        _integer(raw.get("step"), name="Frame step", minimum=0),
        _integer(raw.get("level"), name="Frame level", minimum=1),
    )


def _component_cells(cells: bytes, rows: int, cols: int, connectivity: int, *, mask=False):
    """Linear flood fill; deterministic scan and traversal also canonicalize shapes."""
    visited = bytearray(len(cells))
    neighbors = _ORTHOGONAL if connectivity == 4 else _DIAGONAL
    for start in range(len(cells)):
        if visited[start] or (mask and not cells[start]):
            continue
        color = cells[start]
        visited[start] = 1
        pending = [start]
        members = []
        while pending:
            index = pending.pop()
            row, col = divmod(index, cols)
            members.append((row, col))
            for row_delta, col_delta in neighbors:
                next_row, next_col = row + row_delta, col + col_delta
                if not (0 <= next_row < rows and 0 <= next_col < cols):
                    continue
                adjacent = next_row * cols + next_col
                if not visited[adjacent] and cells[adjacent] == color:
                    visited[adjacent] = 1
                    pending.append(adjacent)
        yield color, members


def _geometry(members: list[tuple[int, int]]) -> dict[str, Any]:
    top = min(row for row, _ in members)
    left = min(col for _, col in members)
    bottom = max(row for row, _ in members)
    right = max(col for _, col in members)
    point = min(members, key=lambda cell: (
        (2 * cell[0] - top - bottom) ** 2 + (2 * cell[1] - left - right) ** 2,
        cell[0], cell[1],
    ))
    return {"bbox": [top, left, bottom, right], "pixels": len(members), "point": list(point)}


def _objects(frame: _Frame, connectivity: int) -> list[dict[str, Any]]:
    result = []
    for color, members in _component_cells(frame.cells, frame.rows, frame.cols, connectivity):
        geometry = _geometry(members)
        top, left = geometry["bbox"][:2]
        # DFS order is deterministic for fixed geometry and neighborhood, independent
        # of color/translation. Canonicalize across 4/8 requests with a bounded linear
        # counting pass over member offsets, avoiding sorting or per-object bbox scans.
        normalized = bytearray()
        row_buckets = [[] for _ in range(geometry["bbox"][2] - top + 1)]
        for row, col in members:
            row_buckets[row - top].append(col - left)
        for row, columns in enumerate(row_buckets):
            if not columns:
                continue
            column_bits = 0
            for col in columns:
                column_bits |= 1 << col
            while column_bits:
                bit = column_bits & -column_bits
                normalized.extend((row, bit.bit_length() - 1))
                column_bits ^= bit
        result.append({
            "id": len(result), "color": ARC_COLOR_CHARS[color], **geometry,
            "shape_hash": hashlib.sha256(normalized).hexdigest(),
        })
    return result


def _segmentation_key(grid: Any, color_chars: Any) -> tuple | None:
    """Only cache ordinary exactly representable inputs; unusual inputs fall back."""
    if type(grid) not in (list, tuple) or len(grid) > 64:
        return None
    if type(color_chars) not in (str, list, tuple) or len(color_chars) != 16:
        return None
    if any(type(char) is not str or len(char) != 1 for char in color_chars):
        return None
    palette = tuple(color_chars)
    if set(palette) != set(ARC_COLOR_CHARS):
        return None
    if grid and type(grid[0]) not in (list, tuple):
        return None
    width = len(grid[0]) if grid else 0
    if width > 64:
        return None
    cells = bytearray()
    for row in grid:
        if type(row) not in (list, tuple) or len(row) != width:
            return None
        for color in row:
            if type(color) is not int or not 0 <= color <= 15:
                return None
            cells.append(color)
    return (_LEGACY_SEGMENTATION_NAMESPACE, len(grid), width, bytes(cells), palette)


def _valid_segmentation_value(value: Any, key: tuple) -> bool:
    """Bound and check the legacy JSON schema without redoing segmentation.

    This verifies structure and inexpensive grid invariants, not the contour or
    containment algorithm itself. Only completed guest results should be published.
    """
    if type(value) is not dict or len(value) != 2 or set(value) != {"nodes", "adjacency_list"}:
        return False
    nodes, adjacency = value["nodes"], value["adjacency_list"]
    _, height, width, cells, palette = key
    area = height * width
    if type(nodes) is not list or len(nodes) > area or type(adjacency) is not list:
        return False
    if not area:
        return not nodes and not adjacency
    node_count = len(nodes)
    if not node_count:
        return False
    max_edges = height * max(0, width - 1) + max(0, height - 1) * width
    if len(adjacency) > max_edges:
        return False
    total_pixels = 0
    expected_counts = {char: 0 for char in palette}
    actual_counts = dict(expected_counts)
    for color in cells:
        expected_counts[palette[color]] += 1
    parents = [-1] * node_count
    for node_id, node in enumerate(nodes):
        if type(node) is not dict or len(node) != 6 or set(node) != {"id", "color", "hash", "pixels", "boundary", "children"}:
            return False
        if type(node["id"]) is not int or node["id"] != node_id:
            return False
        color, shape_hash, pixels = node["color"], node["hash"], node["pixels"]
        if type(color) is not str or color not in expected_counts:
            return False
        if type(shape_hash) is not str or len(shape_hash) != 16 or any(char not in "0123456789abcdef" for char in shape_hash):
            return False
        if type(pixels) is not int or not 1 <= pixels <= area:
            return False
        total_pixels += pixels
        if total_pixels > area:
            return False
        actual_counts[color] += pixels
        boundary, children = node["boundary"], node["children"]
        if type(boundary) is not list or not 1 <= len(boundary) <= 8 * pixels + 16:
            return False
        for point in boundary:
            if type(point) is not list or len(point) != 2:
                return False
            row, col = point
            if type(row) is not int or type(col) is not int or not (0 <= row < height and 0 <= col < width):
                return False
            if palette[cells[row * width + col]] != color:
                return False
        if type(children) is not list or len(children) >= node_count:
            return False
        previous_child = -1
        for child in children:
            if type(child) is not int or not 0 <= child < node_count or child <= previous_child or child == node_id:
                return False
            if parents[child] != -1:
                return False
            parents[child] = node_id
            previous_child = child
    if total_pixels != area or actual_counts != expected_counts:
        return False
    # A containment forest must have no cycles; this is bounded linear validation.
    marks = bytearray(node_count)
    for start in range(node_count):
        cursor, chain = start, []
        while cursor != -1 and marks[cursor] == 0:
            marks[cursor] = 1
            chain.append(cursor)
            cursor = parents[cursor]
        if cursor != -1 and marks[cursor] == 1:
            return False
        for node_id in chain:
            marks[node_id] = 2
    previous_pair = (-1, -1)
    for pair in adjacency:
        if type(pair) is not list or len(pair) != 2:
            return False
        left, right = pair
        if type(left) is not int or type(right) is not int or not 0 <= left < right < node_count:
            return False
        if (left, right) <= previous_pair:
            return False
        previous_pair = (left, right)
    return True


def _encode_segmentation(value: dict) -> bytes | None:
    """Bound serialized storage before joining chunks into a retained entry."""
    chunks, size = [], 0
    encoder = json.JSONEncoder(ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    for chunk in encoder.iterencode(value):
        encoded = chunk.encode("utf-8")
        size += len(encoded)
        if size > _MAX_SEGMENTATION_BYTES:
            return None
        chunks.append(encoded)
    return b"".join(chunks)


class VisionCache:
    """Bounded LRU of serialized results plus two <=64x64 immutable observations.

    retained_bytes counts encoded result bytes, not Python object overhead/RSS.
    Exact geometry keys are separately bounded by max_entries and grid dimensions.
    A new instance is required at the host's full-state-path/game boundary.
    """

    def __init__(self, *, max_bytes: int = 4 * 1024 * 1024, max_entries: int = 128):
        self._max_bytes = _integer(max_bytes, name="max_bytes", minimum=0, maximum=4 * 1024 * 1024)
        self._max_entries = _integer(max_entries, name="max_entries", minimum=0, maximum=128)
        self._cache: OrderedDict[tuple, bytes] = OrderedDict()
        self._retained_bytes = 0
        self._hits = self._misses = self._computations = 0
        # Attempts at known methods, including invalid arguments/missing-frame errors.
        self._api_calls = {name: 0 for name in (*_DOCS, "segmentation")}
        self._segmentation_stats = {
            "gets": 0, "hits": 0, "misses": 0, "noncacheable": 0,
            "puts": 0, "stored": 0, "rejected": 0, "completed_computations": 0,
        }
        self._session = next(_SESSIONS)
        self._epoch = 0
        self._sequence = 0
        self._current: _Observation | None = None
        self._previous: _Observation | None = None
        self._action: str | None = None
        self._status = "missing_current"

    def _observation(self, frame: _Frame, *, epoch: int | None = None) -> _Observation:
        self._sequence += 1
        return _Observation(frame, f"v{self._session}:e{self._epoch if epoch is None else epoch}:o{self._sequence}:l{frame.level}:s{frame.step}")

    @staticmethod
    def _tail(state: dict, current: _Frame) -> tuple[_Frame | None, str | None]:
        history = state.get("history", [])
        if not isinstance(history, (list, tuple)):
            raise ValueError("history must be a list or tuple.")
        if not history:
            return None, None
        last = history[-1]
        if not isinstance(last, dict):
            raise ValueError("History entries must be mappings.")
        last_frame = _read_frame(last.get("frame"))
        action = last.get("action")
        if action is not None and (not isinstance(action, str) or len(action) > 512):
            raise ValueError("History action must be a string of at most 512 characters or None.")
        action = action.strip() if isinstance(action, str) else None
        if last_frame == current:
            if len(history) < 2:
                return None, action or None
            preceding = history[-2]
            if not isinstance(preceding, dict):
                raise ValueError("History entries must be mappings.")
            return _read_frame(preceding.get("frame")), action or None
        # A history without the current post-action frame cannot name its action.
        return last_frame, None

    def observe(self, state: dict, *, executed_actions=None) -> None:
        if not isinstance(state, dict):
            raise ValueError("Vision state must be a mapping.")
        if executed_actions is not None:
            if not isinstance(executed_actions, (list, tuple)) or len(executed_actions) > 4096:
                raise ValueError("executed_actions must be a bounded actual-action list.")
            if any(not isinstance(item, str) or not item.strip() or len(item) > 512 for item in executed_actions):
                raise ValueError("Actual executed actions must be nonempty strings of at most 512 characters.")
        actions = tuple(executed_actions or ())
        incoming = _read_frame(state.get("current_frame"))
        if incoming is None:
            if self._current is not None:
                self._epoch += 1
            self._current = self._previous = None
            self._action = None
            self._status = "missing_current"
            return
        prior_frame, history_action = self._tail(state, incoming)
        last_result = state.get("last_action_result")
        if last_result is None:
            last_result = {}
        if not isinstance(last_result, dict):
            raise ValueError("last_action_result must be a mapping or None.")
        old_current = self._current
        if not actions and old_current is not None and incoming == old_current.frame:
            return  # Inspection must not advance an observation or erase its action.

        # For one actual action, the host's previously observed frame is authoritative.
        # For batches, use the chronological penultimate history frame, even if equal.
        if len(actions) == 1 and old_current is not None:
            prior_frame = old_current.frame
        elif prior_frame is None and old_current is not None:
            prior_frame = old_current.frame
        action = actions[-1] if actions else history_action
        if action is None and last_result.get("executed") is True:
            for key in ("action_display", "action_name"):
                value = last_result.get(key)
                if isinstance(value, str) and value.strip():
                    action = value[:512]
                    break
        def is_reset(name):
            return bool(name and name.strip() and name.strip().upper().split()[0] in {"RESET", "RESTART", "ACTION0"})

        reset_action = is_reset(action)
        reset_count = sum(is_reset(name) for name in actions) if actions else int(reset_action)
        status = "ok"
        if prior_frame is None:
            status = "missing_previous"
        elif reset_action or incoming.step <= prior_frame.step:
            status = "reset_boundary"
        elif incoming.level != prior_frame.level:
            status = "level_boundary"
        elif (incoming.rows, incoming.cols) != (prior_frame.rows, prior_frame.cols):
            status = "shape_boundary"
        elif incoming.step != prior_frame.step + 1:
            status = "nonconsecutive"

        boundary_from_current = old_current is not None and (
            incoming.level != old_current.frame.level or incoming.step <= old_current.frame.step
            or (incoming.rows, incoming.cols) != (old_current.frame.rows, old_current.frame.cols)
        )
        boundary = status in {"reset_boundary", "level_boundary", "shape_boundary"}
        prior_epoch = self._epoch
        self._epoch += max(reset_count, int(boundary or boundary_from_current))
        previous_epoch = self._epoch - int(boundary)
        previous = None
        if prior_frame is not None:
            if previous_epoch == prior_epoch:
                for known in (self._current, self._previous):
                    if known is not None and known.frame == prior_frame:
                        previous = known
                        break
            if previous is None:
                previous = self._observation(prior_frame, epoch=previous_epoch)
        self._previous = previous
        self._current = self._observation(incoming)
        self._action = action
        self._status = status

    def _cached(self, key: tuple, compute: Callable[[], Any]) -> Any:
        encoded = self._cache.get(key)
        if encoded is not None:
            self._hits += 1
            self._cache.move_to_end(key)
            return json.loads(encoded)
        self._misses += 1
        self._computations += 1
        value = compute()
        encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        self._store_serialized(key, encoded)
        return json.loads(encoded)

    def _store_serialized(self, key: tuple, encoded: bytes) -> bool:
        """All vision features share one LRU; duplicate publications never overwrite."""
        if key in self._cache or not self._max_entries or len(encoded) > self._max_bytes:
            return False
        while self._cache and (
            len(self._cache) >= self._max_entries or self._retained_bytes + len(encoded) > self._max_bytes
        ):
            _, removed = self._cache.popitem(last=False)
            self._retained_bytes -= len(removed)
        self._cache[key] = encoded
        self._retained_bytes += len(encoded)
        return True

    def _segmentation_get(self, grid: Any, color_chars: Any) -> dict:
        key = _segmentation_key(grid, color_chars)
        self._segmentation_stats["gets"] += 1
        if key is not None:
            encoded = self._cache.get(key)
            if encoded is not None:
                self._hits += 1
                self._segmentation_stats["hits"] += 1
                self._cache.move_to_end(key)
                return {"hit": True, "cacheable": True, "value": json.loads(encoded)}
        self._misses += 1
        self._segmentation_stats["misses"] += 1
        if key is None:
            self._segmentation_stats["noncacheable"] += 1
        return {"hit": False, "cacheable": key is not None}

    def _segmentation_put(self, grid: Any, color_chars: Any, value: Any) -> bool:
        self._segmentation_stats["puts"] += 1
        key = _segmentation_key(grid, color_chars)
        if key is None or key in self._cache or not _valid_segmentation_value(value, key):
            self._segmentation_stats["rejected"] += 1
            return False
        # A get miss can time out in the guest; only completed validated publications
        # count as computations. A duplicate put does not count the same entry twice.
        self._computations += 1
        self._segmentation_stats["completed_computations"] += 1
        encoded = _encode_segmentation(value)
        stored = encoded is not None and self._store_serialized(key, encoded)
        self._segmentation_stats["stored" if stored else "rejected"] += 1
        return stored

    def _changes(self, details: bool) -> dict[str, Any]:
        result = {
            "status": self._status,
            "before_frame_id": self._previous.frame_id if self._previous else None,
            "after_frame_id": self._current.frame_id if self._current else None,
            "action": self._action, "changed_count": None, "bbox": None,
            "color_transitions": [], "regions": [], "region_count": None,
            "regions_truncated": False,
        }
        if details:
            result.update({"cells": [], "cells_truncated": False})
        if self._status != "ok":
            return result
        before, after = self._previous.frame, self._current.frame
        changed = bytearray(len(after.cells))
        transitions: dict[tuple[int, int], int] = {}
        exact = []
        top, left, bottom, right = after.rows, after.cols, -1, -1
        count = 0
        for index, (old, new) in enumerate(zip(before.cells, after.cells)):
            if old == new:
                continue
            changed[index] = 1
            row, col = divmod(index, after.cols)
            top, left, bottom, right = min(top, row), min(left, col), max(bottom, row), max(right, col)
            transitions[(old, new)] = transitions.get((old, new), 0) + 1
            count += 1
            if details and len(exact) < _MAX_CELLS:
                exact.append([row, col, ARC_COLOR_CHARS[old], ARC_COLOR_CHARS[new]])
        regions = []
        region_count = 0
        for _, members in _component_cells(bytes(changed), after.rows, after.cols, 4, mask=True):
            region_count += 1
            if len(regions) < _MAX_REGIONS:
                regions.append(_geometry(members))
        result.update({
            "status": "ok" if count else "unchanged", "changed_count": count,
            "bbox": [top, left, bottom, right] if count else None,
            "color_transitions": [
                {"before": ARC_COLOR_CHARS[old], "after": ARC_COLOR_CHARS[new], "count": amount}
                for (old, new), amount in sorted(transitions.items())
            ],
            "regions": regions, "region_count": region_count,
            "regions_truncated": region_count > len(regions),
        })
        if details:
            result.update({"cells": exact, "cells_truncated": count > len(exact)})
        return result

    def handle(self, message: dict) -> Any:
        if not isinstance(message, dict):
            raise ValueError("Vision request must be a mapping.")
        if "type" in message and message["type"] != "vision":
            raise ValueError("Vision RPC type must be 'vision'.")
        operation = message.get("operation")
        if isinstance(operation, str) and operation in EXTRA_DOCS:
            self._api_calls[operation] += 1
            return run_extra(self, message)
        if isinstance(operation, str) and operation in {"segmentation_get", "segmentation_put"}:
            if operation == "segmentation_get":
                self._api_calls["segmentation"] += 1
            allowed = {"type", "operation", "grid", "color_chars"}
            if operation == "segmentation_put":
                allowed.add("value")
            if any(key not in allowed for key in message):
                raise ValueError("Unknown option for internal segmentation operation.")
            if operation == "segmentation_get":
                return self._segmentation_get(message.get("grid"), message.get("color_chars"))
            return self._segmentation_put(message.get("grid"), message.get("color_chars"), message.get("value"))
        if not isinstance(operation, str) or operation not in {"objects", "changes", "help"}:
            raise ValueError("Unknown vision operation; expected objects, changes, or help.")
        self._api_calls[operation] += 1
        allowed = {"type", "operation"} | {
            "objects": {"frame", "connectivity"}, "changes": {"details"}, "help": {"topic"},
        }[operation]
        if any(key not in allowed for key in message):
            raise ValueError("Unknown option for vision operation.")
        if operation == "help":
            topic = message.get("topic")
            if topic is not None and (not isinstance(topic, str) or topic not in _DOCS):
                raise ValueError("Help topic must name a vision method, or be None.")
            return dict(_HELP_INDEX) if topic is None else {topic: _DOCS[topic]}
        if operation == "objects":
            frame_name = message.get("frame", "current")
            if not isinstance(frame_name, str) or frame_name not in {"current", "previous"}:
                raise ValueError("frame must be 'current' or 'previous'.")
            connectivity = message.get("connectivity", 4)
            if type(connectivity) is not int or connectivity not in (4, 8):
                raise ValueError("connectivity must be 4 or 8 (not bool).")
            observation = self._current if frame_name == "current" else self._previous
            if observation is None:
                raise ValueError(f"No {frame_name} frame is available.")
            frame = observation.frame
            objects = self._cached(
                ("objects", frame.rows, frame.cols, frame.cells, connectivity),
                lambda: _objects(frame, connectivity),
            )
            for component in objects:
                component["frame_id"] = observation.frame_id
            return objects
        details = message.get("details", False)
        if type(details) is not bool:
            raise ValueError("details must be a bool.")
        key = (
            "changes", self._session, self._epoch,
            self._previous.frame_id if self._previous else None,
            self._current.frame_id if self._current else None,
            self._action, self._status, details,
        )
        return self._cached(key, lambda: self._changes(details))

    def stats(self) -> dict[str, Any]:
        return {
            "hits": self._hits, "misses": self._misses, "computations": self._computations,
            "entries": len(self._cache), "retained_bytes": self._retained_bytes,
            "max_bytes": self._max_bytes, "max_entries": self._max_entries,
            "session_id": self._session, "epoch": self._epoch,
            "api_calls": dict(self._api_calls),
            "segmentation": dict(self._segmentation_stats),
        }
