"""Bounded, optional structural evidence over discrete color grids."""
from __future__ import annotations

from collections import Counter, defaultdict
from itertools import product
from typing import Any

from inference.utils.grid_utils import ARC_COLOR_CHARS


COMPONENT_OPS = {"groups", "hud", "lattice", "symmetry"}
TEMPORAL_OPS = {"background", "hud"}
DOCS = {
    "groups": "groups(background,frame='current',connectivity=4,limit=128): background is ARC chars/indices; foreground unions return component_ids, colors, bbox, pixels, point. Connectivity hypotheses, not semantic objects; limit<=256.",
    "background": "background(frame='current'): ranked color area/border/stability evidence, score_gap and ambiguity. Comparable previous frame used when available; rankings never establish semantic background or remove pixels.",
    "hud": "hud(frame='current',connectivity=4,limit=32): thin edge-component candidates with bbox, border and latest-change evidence. One transition cannot establish timer/HUD behavior; limit<=128.",
    "lattice": "lattice(frame='current',connectivity=4,min_period=2,max_period=16,limit=8): alternative origin/spacing proposals and axis support/contradictions from repeated component edges. Periods2..32, limit<=16; weak evidence may yield no 2D proposal.",
    "cells": "cells(origin,spacing,shape,frame='current'): pairs [row,col], [height,width], [rows,cols]; <=256 cells with bbox, center, exact color_counts, dominant_color, mixed/partial flags. Every cell must start in bounds; edge clipping is explicit.",
    "symmetry": "symmetry(frame='current',object_id=None,connectivity=4): eight D4 transforms with exact/mismatch evidence, full-frame colors or one cropped component mask. Rectangular quarter-turn/diagonal shape mismatches are explicit.",
}
_OPTIONS = {
    "groups": {"background", "limit"}, "background": set(), "hud": {"limit"},
    "lattice": {"min_period", "max_period", "limit"},
    "cells": {"origin", "spacing", "shape"}, "symmetry": {"object_id"},
}
_ORTH = ((-1, 0), (0, -1), (0, 1), (1, 0))
_DIAG = ((-1, -1), (-1, 1), (1, -1), (1, 1))


def _integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in {low}..{high}.")
    return value


def _pair(value, name, low, high):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{name} must be a two-integer pair.")
    return tuple(_integer(item, name, low, high) for item in value)


def _grid_shape(grid):
    if not isinstance(grid, (list, tuple)) or len(grid) > 64:
        raise ValueError("Grid must have at most 64 rows.")
    width = len(grid[0]) if grid and isinstance(grid[0], (list, tuple)) else 0
    if width > 64:
        raise ValueError("Grid must have at most 64 columns.")
    for row in grid:
        if not isinstance(row, (list, tuple)) or len(row) != width:
            raise ValueError("Grid must be rectangular.")
        if any(type(color) is not int or not 0 <= color <= 15 for color in row):
            raise ValueError("Grid colors must be integers 0..15.")
    return len(grid), width


def _colors(value):
    values = list(value) if isinstance(value, str) else value if isinstance(value, (list, tuple)) else [value]
    if len(values) > 16:
        raise ValueError("At most 16 background colors are allowed.")
    result = set()
    for color in values:
        if type(color) is int and 0 <= color <= 15:
            result.add(color)
        elif isinstance(color, str) and len(color) == 1 and color in ARC_COLOR_CHARS:
            result.add(ARC_COLOR_CHARS.index(color))
        else:
            raise ValueError("Background colors must be ARC characters or integers 0..15.")
    return result


def _geometry(cells):
    top = min(row for row, col in cells)
    bottom = max(row for row, col in cells)
    left = min(col for row, col in cells)
    right = max(col for row, col in cells)
    point = min(cells, key=lambda cell: (
        (2 * cell[0] - top - bottom) ** 2 + (2 * cell[1] - left - right) ** 2, cell))
    return {"bbox": [top, left, bottom, right], "pixels": len(cells), "point": list(point)}


def _components(components, grid, rows, cols):
    if not isinstance(components, (list, tuple)) or len(components) > 4096:
        raise ValueError("Complete frame components are required (at most 4096).")
    occupied = set()
    identifiers = set()
    for component in components:
        if not isinstance(component, dict):
            raise ValueError("Components must be mappings.")
        identifier = component.get("id")
        _integer(identifier, "component id", 0, 4095)
        if identifier in identifiers:
            raise ValueError("Component IDs must be unique.")
        identifiers.add(identifier)
        cells = component.get("cells")
        if not isinstance(cells, (list, tuple)) or not cells or len(cells) > 4096:
            raise ValueError("Each component needs bounded member cells.")
        for cell in cells:
            row, col = _pair(cell, "component cell", 0, 63)
            if row >= rows or col >= cols or (row, col) in occupied:
                raise ValueError("Component cells must be in bounds and disjoint.")
            if component.get("color") != ARC_COLOR_CHARS[grid[row][col]]:
                raise ValueError("Component color does not match its cells.")
            occupied.add((row, col))
        if len(occupied) > 4096:
            raise ValueError("Component cells exceed the frame bound.")
        geometry = _geometry([tuple(cell) for cell in cells])
        if list(component.get("bbox", [])) != geometry["bbox"] or component.get("pixels") != len(cells):
            raise ValueError("Component geometry is inconsistent.")
        if not isinstance(component.get("shape_hash"), str) or len(component["shape_hash"]) > 128:
            raise ValueError("Component shape_hash must be a bounded string.")
    if len(occupied) != rows * cols:
        raise ValueError("Components must cover the full frame.")
    return components


def _comparable(grid, previous_grid, transition_status):
    return (transition_status == "ok" and previous_grid is not None
            and _grid_shape(grid) == _grid_shape(previous_grid))


def _groups(grid, options, components, connectivity):
    if "background" not in options:
        raise ValueError("groups requires explicit background colors.")
    backgrounds = _colors(options["background"])
    limit = _integer(options.get("limit", 128), "limit", 1, 256)
    rows, cols = _grid_shape(grid)
    components = _components(components, grid, rows, cols)
    membership = {tuple(cell): component["id"] for component in components for cell in component["cells"]}
    visited = set()
    groups = []
    total = 0
    directions = _ORTH + (_DIAG if connectivity == 8 else ())
    for row in range(rows):
        for col in range(cols):
            if grid[row][col] in backgrounds or (row, col) in visited:
                continue
            cells = []
            stack = [(row, col)]
            visited.add((row, col))
            while stack:
                cell = stack.pop()
                cells.append(cell)
                for dr, dc in directions:
                    nr, nc = cell[0] + dr, cell[1] + dc
                    if (0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in visited
                            and grid[nr][nc] not in backgrounds):
                        visited.add((nr, nc))
                        stack.append((nr, nc))
            if len(groups) < limit:
                counts = Counter(grid[r][c] for r, c in cells)
                groups.append({"id": total, **_geometry(cells),
                               "component_ids": sorted({membership[cell] for cell in cells}),
                               "colors": [{"color": ARC_COLOR_CHARS[color], "pixels": count}
                                          for color, count in sorted(counts.items())],
                               "multicolor": len(counts) > 1})
            total += 1
    return {"status": "ok", "background": [ARC_COLOR_CHARS[color] for color in sorted(backgrounds)],
            "connectivity": connectivity, "groups": groups, "group_count": total,
            "truncated": total > limit, "limit": limit,
            "interpretation": "Connectivity hypotheses; original components are unchanged."}


def _background(grid, previous_grid, transition_status):
    rows, cols = _grid_shape(grid)
    comparable = _comparable(grid, previous_grid, transition_status)
    area = rows * cols
    counts = Counter(color for row in grid for color in row)
    border = {(r, c) for r in range(rows) for c in range(cols)
              if r in (0, rows - 1) or c in (0, cols - 1)}
    border_counts = Counter(grid[r][c] for r, c in border)
    stable = Counter(grid[r][c] for r in range(rows) for c in range(cols)
                     if comparable and grid[r][c] == previous_grid[r][c])
    previous_counts = Counter(color for row in previous_grid for color in row) if comparable else {}
    candidates = []
    for color, pixels in counts.items():
        area_fraction = pixels / area
        border_fraction = border_counts[color] / len(border) if border else 0.0
        stability = stable[color] / pixels if comparable else None
        score = (0.5 * area_fraction + 0.3 * border_fraction + 0.2 * stability if comparable
                 else 0.6 * area_fraction + 0.4 * border_fraction)
        sides = []
        if any(grid[0][c] == color for c in range(cols)): sides.append("top")
        if any(grid[rows - 1][c] == color for c in range(cols)): sides.append("bottom")
        if any(grid[r][0] == color for r in range(rows)): sides.append("left")
        if any(grid[r][cols - 1] == color for r in range(rows)): sides.append("right")
        candidates.append({"color": ARC_COLOR_CHARS[color], "pixels": pixels,
                           "area_fraction": round(area_fraction, 6), "border_pixels": border_counts[color],
                           "border_fraction": round(border_fraction, 6), "border_sides": sides,
                           "previous_pixels": previous_counts.get(color, 0) if comparable else None,
                           "stable_pixels": stable[color] if comparable else None,
                           "stable_fraction": round(stability, 6) if comparable else None,
                           "evidence_score": round(score, 6)})
    candidates.sort(key=lambda item: (-item["evidence_score"], ARC_COLOR_CHARS.index(item["color"])))
    gap = candidates[0]["evidence_score"] - candidates[1]["evidence_score"] if len(candidates) > 1 else None
    return {"status": "ok" if area else "empty", "candidates": candidates,
            "stability_available": comparable, "transition_status": transition_status,
            "score_weights": {"area": 0.5, "border": 0.3, "stability": 0.2} if comparable
            else {"area": 0.6, "border": 0.4, "stability": 0.0},
            "score_gap": round(gap, 6) if gap is not None else None,
            "similar_top_evidence": gap is not None and gap <= 0.1,
            "ambiguous": len(candidates) > 1, "semantic_background": None,
            "interpretation": "Color evidence ranking, not a background classification."}


def _hud(grid, options, components, previous_grid, transition_status):
    limit = _integer(options.get("limit", 32), "limit", 1, 128)
    rows, cols = _grid_shape(grid)
    components = _components(components, grid, rows, cols)
    comparable = _comparable(grid, previous_grid, transition_status)
    candidates = []
    for component in components:
        top, left, bottom, right = component["bbox"]
        height, width = bottom - top + 1, right - left + 1
        horizontal = height <= 4 and width >= max(2, 2 * height) and (top == 0 or bottom == rows - 1)
        vertical = width <= 4 and height >= max(2, 2 * width) and (left == 0 or right == cols - 1)
        if not horizontal and not vertical:
            continue
        cells = component["cells"]
        changed = sum(grid[r][c] != previous_grid[r][c] for r, c in cells) if comparable else None
        sides = [side for side, yes in (("top", top == 0), ("bottom", bottom == rows - 1),
                                       ("left", left == 0), ("right", right == cols - 1)) if yes]
        candidates.append({"object_id": component["id"], "color": component["color"],
                           "bbox": list(component["bbox"]), "pixels": component["pixels"],
                           "orientation": "horizontal" if horizontal else "vertical",
                           "border_sides": sides, "aspect_ratio": round(max(height, width) / min(height, width), 6),
                           "border_pixels": sum(r in (0, rows - 1) or c in (0, cols - 1) for r, c in cells),
                           "latest_changed_pixels": changed,
                           "latest_changed_fraction": round(changed / len(cells), 6) if comparable else None})
    candidates.sort(key=lambda item: (-(item["latest_changed_pixels"] or 0), -item["aspect_ratio"],
                                      -item["pixels"], item["object_id"]))
    return {"status": "candidates" if candidates else "none", "candidates": candidates[:limit],
            "candidate_count": len(candidates), "truncated": len(candidates) > limit, "limit": limit,
            "comparison_available": comparable, "evidence_window_transitions": int(comparable),
            "transition_status": transition_status, "persistent_hud_behavior": "not_established",
            "timer_classification": "undetermined",
            "interpretation": "Thin edge-component evidence only; interior overlays are not covered."}


def _lattice(grid, options, components):
    low = _integer(options.get("min_period", 2), "min_period", 2, 32)
    high = _integer(options.get("max_period", 16), "max_period", 2, 32)
    limit = _integer(options.get("limit", 8), "limit", 1, 16)
    if high < low:
        raise ValueError("max_period must be at least min_period.")
    rows, cols = _grid_shape(grid)
    components = _components(components, grid, rows, cols)
    families = defaultdict(list)
    for component in components:
        box = component["bbox"]
        families[(component["color"], component["shape_hash"], box[2] - box[0], box[3] - box[1])].append(component)
    repeated = [(key, items) for key, items in families.items() if len(items) >= 3]
    repeated.sort(key=lambda item: (-len(item[1]), item[0]))
    chosen = repeated[:64]
    axes = [{}, {}]
    for family, items in chosen:
        for axis in (0, 1):
            for edge in ("start", "end"):
                coordinates = sorted({item["bbox"][axis if edge == "start" else axis + 2]
                                      + (edge == "end") for item in items})
                if len(coordinates) < 3:
                    continue
                for period in range(low, high + 1):
                    phases = defaultdict(list)
                    for coordinate in coordinates:
                        phases[coordinate % period].append(coordinate)
                    for origin, aligned in phases.items():
                        if len(aligned) < 3 or len(aligned) * 2 < len(coordinates):
                            continue
                        pairs = sum(b - a == period for a, b in zip(aligned, aligned[1:]))
                        span_bins = (aligned[-1] - aligned[0]) // period + 1
                        if not pairs or len(aligned) * 2 < span_bins:
                            continue
                        coverage = len(aligned) / span_bins
                        off_lattice = len(coordinates) - len(aligned)
                        score = pairs + coverage + len(aligned) / len(coordinates)
                        evidence = {"origin": origin, "spacing": period, "aligned_positions": len(aligned),
                                    "off_lattice_positions": off_lattice, "adjacent_pairs": pairs,
                                    "span_bins": span_bins, "coverage": round(coverage, 6),
                                    "positions": aligned, "color": family[0], "shape_hash": family[1],
                                    "edge": edge, "evidence_score": round(score, 6), "source_count": 1}
                        key = (origin, period)
                        previous = axes[axis].get(key)
                        if previous is None or score > previous["evidence_score"]:
                            evidence["source_count"] += previous["source_count"] if previous else 0
                            axes[axis][key] = evidence
                        else:
                            previous["source_count"] += 1
    axis_limit = min(16, max(4, limit))
    ranked = [sorted(axis.values(), key=lambda value: (-value["evidence_score"], value["spacing"], value["origin"]))
              for axis in axes]
    selected = [axis[:axis_limit] for axis in ranked]
    proposals = [{"origin": [row["origin"], col["origin"]], "spacing": [row["spacing"], col["spacing"]],
                  "row_evidence": {key: row[key] for key in ("aligned_positions", "off_lattice_positions", "adjacent_pairs", "edge")},
                  "col_evidence": {key: col[key] for key in ("aligned_positions", "off_lattice_positions", "adjacent_pairs", "edge")},
                  "evidence_score": round(row["evidence_score"] + col["evidence_score"], 6),
                  "independent_axis_evidence": True}
                 for row, col in product(*selected)]
    proposals.sort(key=lambda item: (-item["evidence_score"], item["spacing"], item["origin"]))
    return {"status": "proposals" if proposals else "weak_evidence" if any(ranked) else "no_evidence",
            "proposals": proposals[:limit], "proposal_count": len(proposals), "limit": limit,
            "axis_candidates": {"rows": selected[0], "cols": selected[1]},
            "axis_candidate_counts": {"rows": len(ranked[0]), "cols": len(ranked[1])},
            "truncated": (len(proposals) > limit or any(len(axis) > axis_limit for axis in ranked)
                          or len(repeated) > 64),
            "families_considered": len(chosen), "repeated_family_count": len(repeated),
            "work_truncated": len(repeated) > 64, "limits": {"families": 64, "axis_candidates": axis_limit},
            "interpretation": "Alternative component-edge hypotheses, not a proven cell grid; no GCD inference."}


def _cells(grid, options):
    if any(key not in options for key in ("origin", "spacing", "shape")):
        raise ValueError("cells requires origin, spacing, and shape pairs.")
    origin = _pair(options["origin"], "origin", 0, 63)
    spacing = _pair(options["spacing"], "spacing", 1, 64)
    shape = _pair(options["shape"], "shape", 1, 256)
    if shape[0] * shape[1] > 256:
        raise ValueError("At most 256 cells may be requested.")
    rows, cols = _grid_shape(grid)
    if any(origin[axis] + (shape[axis] - 1) * spacing[axis] >= size
           for axis, size in enumerate((rows, cols))):
        raise ValueError("Every requested cell must start inside the frame.")
    cells = []
    for row in range(shape[0]):
        for col in range(shape[1]):
            top, left = origin[0] + row * spacing[0], origin[1] + col * spacing[1]
            requested = [top, left, top + spacing[0] - 1, left + spacing[1] - 1]
            bottom, right = min(requested[2], rows - 1), min(requested[3], cols - 1)
            counts = Counter(grid[r][c] for r in range(top, bottom + 1) for c in range(left, right + 1))
            dominant_count = max(counts.values())
            dominant = [color for color, count in sorted(counts.items()) if count == dominant_count]
            cells.append({"index": [row, col], "bbox": [top, left, bottom, right],
                          "requested_bbox": requested, "center": [(top + bottom) / 2, (left + right) / 2],
                          "pixels": sum(counts.values()),
                          "color_counts": [{"color": ARC_COLOR_CHARS[color], "count": count}
                                           for color, count in sorted(counts.items())],
                          "dominant_color": ARC_COLOR_CHARS[dominant[0]] if len(dominant) == 1 else None,
                          "dominant_colors": [ARC_COLOR_CHARS[color] for color in dominant],
                          "dominant_count": dominant_count, "mixed": len(counts) > 1,
                          "partial": bottom != requested[2] or right != requested[3]})
    return {"status": "ok", "origin": list(origin), "spacing": list(spacing), "shape": list(shape),
            "cells": cells, "cell_count": len(cells), "limit": 256, "truncated": False,
            "mixed_cells": sum(cell["mixed"] for cell in cells),
            "partial_cells": sum(cell["partial"] for cell in cells)}


def _symmetry(grid, options, components):
    rows, cols = _grid_shape(grid)
    object_id = options.get("object_id")
    box = [0, 0, rows - 1, cols - 1]
    mode = "frame_colors"
    if object_id is not None:
        _integer(object_id, "object_id", 0, 4095)
        components = _components(components, grid, rows, cols)
        component = next((item for item in components if item["id"] == object_id), None)
        if component is None:
            raise ValueError("No component with that object_id.")
        box = list(component["bbox"])
        member = {tuple(cell) for cell in component["cells"]}
        grid = tuple(tuple(int((r, c) in member) for c in range(box[1], box[3] + 1))
                     for r in range(box[0], box[2] + 1))
        rows, cols = _grid_shape(grid)
        mode = "component_mask"
    if not rows or not cols:
        return {"status": "empty", "mode": mode, "object_id": object_id, "shape": [rows, cols],
                "bbox": box, "transforms": [], "exact_transforms": []}
    base = [list(row) for row in grid]
    transpose = [list(row) for row in zip(*base)]
    variants = {
        "identity": base, "rot90": [row[::-1] for row in transpose],
        "rot180": [row[::-1] for row in base[::-1]], "rot270": transpose[::-1],
        "flip_lr": [row[::-1] for row in base], "flip_ud": base[::-1],
        "transpose": transpose, "anti_transpose": [row[::-1] for row in transpose[::-1]],
    }
    transforms = []
    for name, transformed in variants.items():
        changed_shape = [len(transformed), len(transformed[0])]
        shape_match = changed_shape == [rows, cols]
        mismatch = sum(a != b for old, new in zip(base, transformed) for a, b in zip(old, new)) if shape_match else None
        transforms.append({"transform": name, "transformed_shape": changed_shape, "shape_match": shape_match,
                           "exact": shape_match and mismatch == 0, "mismatch_count": mismatch,
                           "mismatch_fraction": round(mismatch / (rows * cols), 6) if shape_match else None})
    return {"status": "ok", "mode": mode, "object_id": object_id, "shape": [rows, cols], "bbox": box,
            "transforms": transforms, "exact_transforms": [item["transform"] for item in transforms if item["exact"]]}


def run(operation, grid, options, *, components=None, previous_grid=None,
        previous_components=None, transition_status="missing_previous", connectivity=4) -> dict[str, Any]:
    """Return geometry/evidence only; inputs are never mutated."""
    if not isinstance(operation, str) or operation not in _OPTIONS:
        raise ValueError("Unknown structure operation.")
    if not isinstance(options, dict):
        raise ValueError("Options must be a mapping.")
    if any(key not in _OPTIONS[operation] for key in options):
        raise ValueError("Unknown option for structure operation.")
    if type(connectivity) is not int or connectivity not in (4, 8):
        raise ValueError("connectivity must be 4 or 8.")
    _grid_shape(grid)
    if operation == "groups": return _groups(grid, options, components, connectivity)
    if operation == "background": return _background(grid, previous_grid, transition_status)
    if operation == "hud": return _hud(grid, options, components, previous_grid, transition_status)
    if operation == "lattice": return _lattice(grid, options, components)
    if operation == "cells": return _cells(grid, options)
    return _symmetry(grid, options, components)
