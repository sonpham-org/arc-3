"""Bounded correspondence evidence and exact pattern search; never game actions."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from inference.utils.grid_utils import ARC_COLOR_CHARS


COMPONENT_OPS = {"track"}
TEMPORAL_OPS = {"track"}
TRACK_COMPARISON_LIMIT = 100_000
FIND_CELL_CHECK_LIMIT = 250_000
DOCS = {
    "track": "track(max_distance=16, allow_recolor=False, limit=128): latest-pair shape/color candidates, mutual-unique matches, unmatched IDs and shared-displacement groups. Duplicate ambiguity stays explicit; matches are evidence, not stable identities. Refuses boundaries. At most 100k pair checks; complete/search_complete/truncated report limits.",
    "find": "find(pattern, transforms=False, limit=32): exact bbox/transform matches for <=32x32 ASCII rows or numeric rows with None wildcards; optional D4. complete=False means output or work was limited; search_complete distinguishes those cases. At most 250k cell checks. No approximate matching.",
}


def _integer(value: Any, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer from {low} through {high}, not bool.")
    return value


def _boolean(value: Any, name: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{name} must be bool.")
    return value


def _component_records(components, grid):
    if not isinstance(components, (list, tuple)) or len(components) > 4096:
        raise ValueError("Tracking requires at most 4096 component records per frame.")
    height, width = len(grid), len(grid[0]) if grid else 0
    records, identifiers = [], set()
    for component in components:
        if not isinstance(component, dict):
            raise ValueError("Components must be mappings.")
        identifier = _integer(component.get("id"), "component id", 0, 4095)
        if identifier in identifiers:
            raise ValueError("Component IDs must be unique within each frame.")
        identifiers.add(identifier)
        bbox = component.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4 or any(type(v) is not int for v in bbox):
            raise ValueError("Component bbox must have four integer coordinates.")
        top, left, bottom, right = bbox
        if not (0 <= top <= bottom < height and 0 <= left <= right < width):
            raise ValueError("Component bbox is outside its frame.")
        color, signature = component.get("color"), component.get("shape_hash")
        if type(color) is not str or len(color) != 1 or color not in ARC_COLOR_CHARS:
            raise ValueError("Component color must be an ARC color character.")
        if type(signature) is not str or not 1 <= len(signature) <= 128:
            raise ValueError("Component shape_hash must be a bounded string.")
        area = _integer(component.get("pixels"), "component pixels", 1, height * width)
        records.append({"id": identifier, "color": color, "shape": signature,
                        "area": area, "top": top, "left": left,
                        "height": bottom - top + 1, "width": right - left + 1})
    return sorted(records, key=lambda item: item["id"])


def _pair(before, after):
    displacement = [after["top"] - before["top"], after["left"] - before["left"]]
    moved = displacement != [0, 0]
    recolored = before["color"] != after["color"]
    kind = "moved_recolored" if moved and recolored else "moved" if moved else "recolored" if recolored else "unchanged"
    return {"previous_id": before["id"], "current_id": after["id"],
            "displacement": displacement, "distance": sum(abs(value) for value in displacement),
            "previous_color": before["color"], "current_color": after["color"],
            "kind": kind, "changed": moved or recolored}


def _track(grid, options, components, previous_grid, previous_components, transition_status):
    allowed = {"max_distance", "allow_recolor", "limit"}
    if set(options) - allowed:
        raise ValueError("Unknown track option.")
    distance = _integer(options.get("max_distance", 16), "max_distance", 0, 128)
    recolor = _boolean(options.get("allow_recolor", False), "allow_recolor")
    limit = _integer(options.get("limit", 128), "limit", 1, 256)
    if not isinstance(transition_status, str):
        raise ValueError("transition_status must be a string.")
    status = transition_status
    if status in {"ok", "unchanged"}:
        if previous_grid is None or previous_components is None:
            status = "missing_previous"
        elif (len(grid), len(grid[0]) if grid else 0) != (len(previous_grid), len(previous_grid[0]) if previous_grid else 0):
            status = "shape_boundary"
    result = {"status": status, "comparable": False, "complete": False,
              "search_complete": False, "truncated": False, "work_limit_reached": False,
              "comparison_count": 0, "comparison_limit": TRACK_COMPARISON_LIMIT,
              "limit": limit, "distance_metric": "Manhattan displacement of matching-shape bounding boxes",
              "candidates": [], "candidate_count": None, "candidate_count_is_exact": False,
              "matches": [], "match_count": None, "unmatched_previous": None,
              "unmatched_current": None, "ambiguous_previous": None, "ambiguous_current": None,
              "counts": {}, "co_motion": [], "co_motion_group_count": None}
    if status not in {"ok", "unchanged"}:
        return result
    before = _component_records(previous_components, previous_grid)
    after = _component_records(components, grid)

    def key(record):
        shape = (record["shape"], record["area"], record["height"], record["width"])
        return shape if recolor else (*shape, record["color"])

    by_shape = defaultdict(list)
    for index, record in enumerate(after):
        by_shape[key(record)].append(index)
    previous_degree, current_degree = [0] * len(before), [0] * len(after)
    first_candidate = [None] * len(before)
    candidates, candidate_count, comparisons = [], 0, 0
    exhausted = False
    for previous_index, old in enumerate(before):
        for current_index in by_shape.get(key(old), ()):
            if comparisons >= TRACK_COMPARISON_LIMIT:
                exhausted = True
                break
            comparisons += 1
            new = after[current_index]
            if abs(new["top"] - old["top"]) + abs(new["left"] - old["left"]) > distance:
                continue
            candidate_count += 1
            previous_degree[previous_index] += 1
            current_degree[current_index] += 1
            if first_candidate[previous_index] is None:
                first_candidate[previous_index] = current_index
            if len(candidates) < limit:
                candidates.append(_pair(old, new))
        if exhausted:
            break
    result.update({"status": "work_limit" if exhausted else "ok", "comparable": True,
                   "comparison_count": comparisons, "search_complete": not exhausted,
                   "work_limit_reached": exhausted, "candidates": candidates,
                   "candidate_count": candidate_count, "candidate_count_is_exact": not exhausted})
    if exhausted:
        # A later edge could invalidate an earlier apparent unique match. Do not
        # certify matches or label unseen components as disappeared/appeared.
        result["truncated"] = True
        return result

    matches = []
    for index, old in enumerate(before):
        current_index = first_candidate[index]
        if previous_degree[index] == 1 and current_degree[current_index] == 1:
            matches.append(_pair(old, after[current_index]))
    id_lists = {
        "unmatched_previous": [item["id"] for index, item in enumerate(before) if previous_degree[index] == 0],
        "unmatched_current": [item["id"] for index, item in enumerate(after) if current_degree[index] == 0],
    }
    # Degree-one nodes attached to an ambiguous node are also unresolved.
    matched_previous = {item["previous_id"] for item in matches}
    matched_current = {item["current_id"] for item in matches}
    id_lists["ambiguous_previous"] = [item["id"] for index, item in enumerate(before)
                                        if previous_degree[index] and item["id"] not in matched_previous]
    id_lists["ambiguous_current"] = [item["id"] for index, item in enumerate(after)
                                       if current_degree[index] and item["id"] not in matched_current]
    groups = defaultdict(list)
    for match in matches:
        if match["displacement"] != [0, 0]:
            groups[tuple(match["displacement"])].append([match["previous_id"], match["current_id"]])
    co_motion = [{"displacement": list(displacement), "pairs": pairs[:limit],
                  "pair_count": len(pairs), "truncated": len(pairs) > limit}
                 for displacement, pairs in sorted(groups.items()) if len(pairs) >= 2]
    truncated = (candidate_count > limit or len(matches) > limit or len(co_motion) > limit
                 or any(len(values) > limit for values in id_lists.values())
                 or any(group["truncated"] for group in co_motion))
    result.update({"matches": matches[:limit], "match_count": len(matches),
                   **{name: values[:limit] for name, values in id_lists.items()},
                   "counts": {name: len(values) for name, values in id_lists.items()},
                   "co_motion": co_motion[:limit], "co_motion_group_count": len(co_motion),
                   "complete": not truncated, "truncated": truncated})
    return result


def _pattern(value):
    if isinstance(value, str):
        value = value.splitlines()
    if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= 32:
        raise ValueError("pattern must have 1 through 32 nonempty rows.")
    ascii_rows = all(isinstance(row, str) for row in value)
    numeric_rows = all(isinstance(row, (list, tuple)) for row in value)
    if not ascii_rows and not numeric_rows:
        raise ValueError("Use either all ASCII rows or all numeric rows.")
    width = len(value[0])
    if not 1 <= width <= 32 or any(len(row) != width for row in value):
        raise ValueError("pattern must be rectangular with 1 through 32 columns.")
    if ascii_rows:
        if any(character not in ARC_COLOR_CHARS for row in value for character in row):
            raise ValueError("ASCII pattern contains an unknown ARC color character.")
        return tuple(tuple(ARC_COLOR_CHARS.index(character) for character in row) for row in value)
    for row in value:
        for cell in row:
            if cell is not None:
                _integer(cell, "pattern color", 0, 15)
    return tuple(tuple(row) for row in value)


def _rotate(pattern):
    return tuple(tuple(pattern[len(pattern) - 1 - row][col] for row in range(len(pattern)))
                 for col in range(len(pattern[0])))


def _variants(pattern, transforms):
    unique = {}
    for reflected in (False, True) if transforms else (False,):
        current = tuple(tuple(reversed(row)) for row in pattern) if reflected else pattern
        for rotation in range(4) if transforms else (0,):
            name = ("flip_lr" if reflected else "identity") if rotation == 0 else (
                f"flip_lr_rot{rotation * 90}" if reflected else f"rot{rotation * 90}")
            unique.setdefault(current, []).append(name)
            current = _rotate(current)
    return list(unique.items())


def _find(grid, options):
    if set(options) - {"pattern", "transforms", "limit"}:
        raise ValueError("Unknown find option.")
    pattern = _pattern(options.get("pattern"))
    transforms = _boolean(options.get("transforms", False), "transforms")
    limit = _integer(options.get("limit", 32), "limit", 1, 256)
    height, width = len(grid), len(grid[0]) if grid else 0
    variants = _variants(pattern, transforms)
    positions_total = sum(max(0, height - len(candidate) + 1) * max(0, width - len(candidate[0]) + 1)
                          for candidate, _ in variants)
    matches, found, checked, cell_checks = [], 0, 0, 0
    exhausted = False
    for candidate, names in variants:
        rows, cols = len(candidate), len(candidate[0])
        for top in range(max(0, height - rows + 1)):
            for left in range(max(0, width - cols + 1)):
                matches_here = True
                for row in range(rows):
                    for col in range(cols):
                        if cell_checks >= FIND_CELL_CHECK_LIMIT:
                            exhausted = True
                            break
                        cell_checks += 1  # Wildcard visits count toward the bound too.
                        value = candidate[row][col]
                        if value is not None and grid[top + row][left + col] != value:
                            matches_here = False
                            break
                    if exhausted or not matches_here:
                        break
                if exhausted:
                    break
                checked += 1
                if matches_here:
                    found += 1
                    if len(matches) < limit:
                        matches.append({"bbox": [top, left, top + rows - 1, left + cols - 1],
                                        "transforms": list(names)})
            if exhausted:
                break
        if exhausted:
            break
    truncated = exhausted or found > len(matches)
    return {"status": "work_limit" if exhausted else "ok", "matches": matches,
            "matches_found": found, "match_count_is_exact": not exhausted,
            "complete": not truncated, "search_complete": not exhausted, "truncated": truncated,
            "work_limit_reached": exhausted, "cell_checks": cell_checks,
            "cell_check_limit": FIND_CELL_CHECK_LIMIT, "positions_checked": checked,
            "positions_total": positions_total, "limit": limit,
            "variants": [{"shape": [len(candidate), len(candidate[0])], "transforms": names}
                         for candidate, names in variants]}


def run(operation, grid, options, *, components=None, previous_grid=None,
        previous_components=None, transition_status="missing_previous", connectivity=4):
    if type(options) is not dict:
        raise ValueError("Matching options must be a mapping.")
    if type(connectivity) is not int or connectivity not in (4, 8):
        raise ValueError("connectivity must be 4 or 8.")
    if operation == "track":
        return _track(grid, options, components, previous_grid, previous_components, transition_status)
    if operation == "find":
        return _find(grid, options)
    raise ValueError("Unknown matching operation.")
