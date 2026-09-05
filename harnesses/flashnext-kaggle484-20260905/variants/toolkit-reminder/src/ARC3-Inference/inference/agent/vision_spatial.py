# Author: GPT-6 Astra
# Date: 2026-09-05
# PURPOSE: Optional bounded CPU spatial geometry, local crops and explicit-grid BFS
# for the shared vision adapter; no inferred mechanics or gameplay execution.
# SRP/DRY check: Pass — consume adapter components; share spans and BFS internally.
"""Pure spatial operations on one <=64x64 frame."""

from __future__ import annotations

from collections import deque

from inference.utils.grid_utils import ARC_COLOR_CHARS


COMPONENT_OPS = {"mask", "topology", "relations"}
TEMPORAL_OPS = set()
DOCS = {
    "crop": "crop(rows,cols,frame='current'): inclusive [start,end] ranges, at most32x32. Returns bbox,origin,shape,ascii. Coordinates remain frame-relative; out-of-bounds requests fail.",
    "mask": "mask(object_id,frame='current',connectivity=4): exact component bbox,area and spans [row,col_start,col_end] inclusive. Includes all component pixels, not its filled bounding box.",
    "topology": "topology(object_id,frame='current',connectivity=4): perimeter4 and holes with area,bbox,point,spans. Complement uses8-connectivity for4-connected objects and4 for8; holes are enclosed nonmember pixels, not semantic objects.",
    "relations": "relations(object_ids=None,frame='current',connectivity=4,limit=256): pair bbox comparisons, actual edge/corner contact counts, color/shape equality. Default first32 objects; explicit<=64; limit1..2048. Reports selection/output truncation; bbox containment is not true containment.",
    "path": "path(start,goal,passable,frame='current',diagonal=False): BFS status,path,distance,explored. Points are[row,col]; passable is ARC characters or indices. Each step costs1; diagonals forbid corner cutting. Caller supplies movement assumptions; no actions execute.",
    "reachable": "reachable(start,passable,frame='current',diagonal=False): BFS area,bbox,point,spans,explored,max_distance. Explicit passable colors; unit steps; diagonals forbid corner cutting. Exact<=4096-pixel region under these assumptions, not inferred game movement.",
}
_ORTH = ((-1, 0), (0, -1), (0, 1), (1, 0))
_EIGHT = _ORTH + ((-1, -1), (-1, 1), (1, -1), (1, 1))
_OPTIONS = {
    "crop": {"rows", "cols"}, "mask": {"object_id"}, "topology": {"object_id"},
    "relations": {"object_ids", "limit"}, "path": {"start", "goal", "passable", "diagonal"},
    "reachable": {"start", "passable", "diagonal"},
}


def _integer(value, name, minimum=0, maximum=None):
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f"{name} must be an integer in the allowed range (not bool).")
    return value


def _grid_shape(grid):
    if not isinstance(grid, (tuple, list)) or not 1 <= len(grid) <= 64:
        raise ValueError("A nonempty current grid with at most64 rows is required.")
    if not isinstance(grid[0], (tuple, list)) or not 1 <= len(grid[0]) <= 64:
        raise ValueError("Grid requires1..64 columns.")
    width = len(grid[0])
    for row in grid:
        if not isinstance(row, (tuple, list)) or len(row) != width:
            raise ValueError("Grid must be rectangular.")
        for color in row:
            _integer(color, "Grid color", 0, 15)
    return len(grid), width


def _point(value, name, height, width):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{name} must be [row,col].")
    return (_integer(value[0], f"{name} row", 0, height - 1), _integer(value[1], f"{name} col", 0, width - 1))


def _geometry(cells):
    if not cells:
        return {"area": 0, "bbox": None, "point": None}
    top = min(row for row, _ in cells)
    left = min(col for _, col in cells)
    bottom = max(row for row, _ in cells)
    right = max(col for _, col in cells)
    point = min(cells, key=lambda cell: (
        (2 * cell[0] - top - bottom) ** 2 + (2 * cell[1] - left - right) ** 2,
        cell[0], cell[1],
    ))
    return {"area": len(cells), "bbox": [top, left, bottom, right], "point": list(point)}


def _spans(cells):
    spans = []
    for row, col in sorted(cells):
        if spans and spans[-1][0] == row and spans[-1][2] == col - 1:
            spans[-1][2] = col
        else:
            spans.append([row, col, col])
    return spans


def _component_index(components, grid, height, width):
    if not isinstance(components, (list, tuple)) or len(components) > 4096:
        raise ValueError("Bounded component data is required.")
    result, occupied = {}, set()
    for component in components:
        if not isinstance(component, dict):
            raise ValueError("Components must be mappings.")
        object_id = _integer(component.get("id"), "Component id", 0, 4095)
        if object_id in result:
            raise ValueError("Component ids must be unique.")
        raw_cells = component.get("cells")
        if not isinstance(raw_cells, (list, tuple)) or not 1 <= len(raw_cells) <= 4096:
            raise ValueError("Each component needs bounded member cells.")
        members = frozenset(_point(cell, "Member", height, width) for cell in raw_cells)
        if len(members) != len(raw_cells) or occupied.intersection(members):
            raise ValueError("Component cells must be unique and disjoint.")
        occupied.update(members)
        color = component.get("color")
        if not isinstance(color, str) or len(color) != 1 or color not in ARC_COLOR_CHARS:
            raise ValueError("Component color must be an ARC character.")
        if any(ARC_COLOR_CHARS[grid[row][col]] != color for row, col in members):
            raise ValueError("Component cells do not match their color.")
        geometry = _geometry(members)
        if component.get("pixels") != len(members) or component.get("bbox") != geometry["bbox"]:
            raise ValueError("Component area/bbox must match its cells.")
        shape_hash = component.get("shape_hash")
        if not isinstance(shape_hash, str) or not shape_hash:
            raise ValueError("Component shape_hash is required.")
        result[object_id] = {"id": object_id, "color": color, "cells": members, "shape_hash": shape_hash, **geometry}
    return result


def _selected(index, object_id):
    object_id = _integer(object_id, "object_id", 0, 4095)
    if object_id not in index:
        raise ValueError("object_id is absent from this frame's components.")
    return index[object_id]


def _crop(grid, options, height, width):
    bounds = []
    for name, size in (("rows", height), ("cols", width)):
        interval = options.get(name)
        if not isinstance(interval, (list, tuple)) or len(interval) != 2:
            raise ValueError(f"{name} must be an inclusive [start,end] range.")
        start = _integer(interval[0], name, 0, size - 1)
        end = _integer(interval[1], name, start, size - 1)
        if end - start + 1 > 32:
            raise ValueError("Crops are limited to32 rows and32 columns.")
        bounds.append((start, end))
    (top, bottom), (left, right) = bounds
    return {
        "status": "ok", "bbox": [top, left, bottom, right], "origin": [top, left],
        "shape": [bottom - top + 1, right - left + 1],
        "ascii": "\n".join("".join(ARC_COLOR_CHARS[color] for color in grid[row][left:right + 1]) for row in range(top, bottom + 1)),
    }


def _mask(component):
    spans = _spans(component["cells"])
    return {"status": "ok", "object_id": component["id"], "bbox": list(component["bbox"]),
            "area": component["area"], "spans": spans, "span_count": len(spans), "truncated": False}


def _topology(component, height, width, connectivity):
    members = component["cells"]
    perimeter = sum((row + dr, col + dc) not in members for row, col in members for dr, dc in _ORTH)
    complement_connectivity = 8 if connectivity == 4 else 4
    directions = _EIGHT if complement_connectivity == 8 else _ORTH
    remaining = {(row, col) for row in range(height) for col in range(width)} - members
    holes = []
    for row in range(height):
        for col in range(width):
            start = (row, col)
            if start not in remaining:
                continue
            remaining.remove(start)
            group, queue = {start}, [start]
            exterior = False
            while queue:
                r, c = queue.pop()
                exterior |= r in (0, height - 1) or c in (0, width - 1)
                for dr, dc in directions:
                    neighbor = (r + dr, c + dc)
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        group.add(neighbor)
                        queue.append(neighbor)
            if not exterior:
                holes.append({"id": len(holes), **_geometry(group), "spans": _spans(group)})
    return {"status": "ok", "object_id": component["id"], "area": component["area"],
            "perimeter4": perimeter, "connectivity": connectivity,
            "complement_connectivity": complement_connectivity,
            "hole_count": len(holes), "hole_area": sum(hole["area"] for hole in holes),
            "holes": holes, "truncated": False}


def _relations(index, options):
    requested = options.get("object_ids")
    selection_truncated = False
    if requested is None:
        ids = sorted(index)[:32]
        selection_truncated = len(index) > 32
    else:
        if not isinstance(requested, (list, tuple)) or len(requested) > 64:
            raise ValueError("object_ids must be a list of at most64 unique ids.")
        ids = [_selected(index, object_id)["id"] for object_id in requested]
        if len(set(ids)) != len(ids):
            raise ValueError("object_ids must be unique.")
    limit = _integer(options.get("limit", 256), "limit", 1, 2048)
    owner = {cell: object_id for object_id in ids for cell in index[object_id]["cells"]}
    edge_counts, corner_counts = {}, {}
    for (row, col), object_id in owner.items():
        for dr, dc, counts in ((0, 1, edge_counts), (1, 0, edge_counts), (1, -1, corner_counts), (1, 1, corner_counts)):
            other = owner.get((row + dr, col + dc))
            if other is not None and other != object_id:
                pair = tuple(sorted((object_id, other)))
                counts[pair] = counts.get(pair, 0) + 1
    pairs = []
    pair_count = len(ids) * (len(ids) - 1) // 2
    for offset, a_id in enumerate(ids):
        for b_id in ids[offset + 1:]:
            if len(pairs) >= limit:
                break
            a, b = index[a_id], index[b_id]
            at, al, ab, ar = a["bbox"]
            bt, bl, bb, br = b["bbox"]
            overlap_rows = max(0, min(ab, bb) - max(at, bt) + 1)
            overlap_cols = max(0, min(ar, br) - max(al, bl) + 1)
            pair = tuple(sorted((a_id, b_id)))
            pairs.append({
                "a": a_id, "b": b_id, "same_color": a["color"] == b["color"],
                "same_shape": a["shape_hash"] == b["shape_hash"],
                "a_left_of_b": ar < bl, "a_above_b": ab < bt,
                "b_left_of_a": br < al, "b_above_a": bb < at,
                "bbox_overlap_area": overlap_rows * overlap_cols,
                "a_bbox_contains_b": at <= bt and al <= bl and ab >= bb and ar >= br,
                "b_bbox_contains_a": bt <= at and bl <= al and bb >= ab and br >= ar,
                "bbox_distance_manhattan": max(0, bt - ab, at - bb) + max(0, bl - ar, al - br),
                "bbox_center_delta": [(bt + bb - at - ab) / 2, (bl + br - al - ar) / 2],
                "edge_contacts": edge_counts.get(pair, 0), "corner_contacts": corner_counts.get(pair, 0),
            })
    return {"status": "ok", "object_count": len(index), "selected_ids": ids,
            "selected_count": len(ids), "selection_truncated": selection_truncated,
            "pair_count": pair_count, "relations": pairs, "returned_count": len(pairs),
            "limit": limit, "truncated": len(pairs) < pair_count}


def _passable(value):
    if not isinstance(value, (str, list, tuple)) or not 1 <= len(value) <= 16:
        raise ValueError("passable must contain1..16 ARC characters or indices.")
    colors = set()
    for color in value:
        if type(color) is int:
            colors.add(_integer(color, "passable color", 0, 15))
        elif isinstance(color, str) and len(color) == 1 and color in ARC_COLOR_CHARS:
            colors.add(ARC_COLOR_CHARS.index(color))
        else:
            raise ValueError("passable entries must be ARC characters or integer indices.")
    return colors


def _bfs(grid, start, passable, diagonal, goal=None):
    height, width = len(grid), len(grid[0])
    start_index = start[0] * width + start[1]
    parent = [-2] * (height * width)
    distance = [-1] * (height * width)
    parent[start_index], distance[start_index] = -1, 0
    queue = deque([start_index])
    explored = 0
    while queue:
        current = queue.popleft()
        explored += 1
        row, col = divmod(current, width)
        if goal == (row, col):
            break
        for dr, dc in (_EIGHT if diagonal else _ORTH):
            r, c = row + dr, col + dc
            if not (0 <= r < height and 0 <= c < width) or grid[r][c] not in passable:
                continue
            if dr and dc and (grid[row][c] not in passable or grid[r][col] not in passable):
                continue
            adjacent = r * width + c
            if parent[adjacent] != -2:
                continue
            parent[adjacent] = current
            distance[adjacent] = distance[current] + 1
            queue.append(adjacent)
    return parent, distance, explored


def _navigation(operation, grid, options, height, width):
    start = _point(options.get("start"), "start", height, width)
    goal = _point(options.get("goal"), "goal", height, width) if operation == "path" else None
    passable = _passable(options.get("passable"))
    diagonal = options.get("diagonal", False)
    if type(diagonal) is not bool:
        raise ValueError("diagonal must be bool.")
    result = {"status": "ok", "start": list(start), "passable": [ARC_COLOR_CHARS[color] for color in sorted(passable)],
              "diagonal": diagonal, "corner_cutting": False, "explored": 0, "truncated": False}
    if operation == "path":
        result.update({"goal": list(goal), "path": [], "distance": None})
    else:
        result.update({"area": 0, "bbox": None, "point": None, "spans": [], "span_count": 0, "max_distance": None})
    if grid[start[0]][start[1]] not in passable:
        result["status"] = "blocked_start"
        return result
    if goal is not None and grid[goal[0]][goal[1]] not in passable:
        result["status"] = "blocked_goal"
        return result
    parent, distance, result["explored"] = _bfs(grid, start, passable, diagonal, goal)
    if goal is not None:
        target = goal[0] * width + goal[1]
        if parent[target] == -2:
            result["status"] = "unreachable"
            return result
        result["distance"] = distance[target]
        path = []
        while target != -1:
            path.append(list(divmod(target, width)))
            target = parent[target]
        result["path"] = path[::-1]
    else:
        cells = {divmod(index, width) for index, value in enumerate(parent) if value != -2}
        spans = _spans(cells)
        result.update({**_geometry(cells), "spans": spans, "span_count": len(spans), "max_distance": max(distance)})
    return result


def run(operation, grid, options, *, components=None, previous_grid=None,
        previous_components=None, transition_status="missing_previous", connectivity=4):
    """Dispatch one bounded spatial calculation; unused temporal inputs stay inert."""
    if not isinstance(operation, str) or operation not in _OPTIONS:
        raise ValueError("Unknown spatial operation.")
    if not isinstance(options, dict) or any(key not in _OPTIONS[operation] for key in options):
        raise ValueError("Unknown or malformed spatial options.")
    if type(connectivity) is not int or connectivity not in (4, 8):
        raise ValueError("connectivity must be4 or8 (not bool).")
    height, width = _grid_shape(grid)
    if operation == "crop":
        return _crop(grid, options, height, width)
    if operation in {"path", "reachable"}:
        return _navigation(operation, grid, options, height, width)
    index = _component_index(components, grid, height, width)
    if operation == "relations":
        return _relations(index, options)
    component = _selected(index, options.get("object_id"))
    if operation == "mask":
        return _mask(component)
    return _topology(component, height, width, connectivity)
