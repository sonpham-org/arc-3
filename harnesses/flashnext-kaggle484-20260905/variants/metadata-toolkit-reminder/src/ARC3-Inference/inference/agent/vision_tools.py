"""Bounded dispatch/cache adapter for optional CPU perception and planning tools."""
from __future__ import annotations

import json

from inference.agent import vision_spatial, vision_structure, vision_matching


_MODULES = (vision_spatial, vision_structure, vision_matching)
EXTRA_DOCS = {name: doc for module in _MODULES for name, doc in module.DOCS.items()}
_OWNERS = {name: module for module in _MODULES for name in module.DOCS}
EXTRA_INDEX = {
    "crop": "Local ASCII crop.", "mask": "Exact object row spans.",
    "topology": "Object holes and perimeter.", "relations": "Contact and bounding-box relations.",
    "path": "Pixel path through explicit passable colors.", "reachable": "Reachable pixel region.",
    "groups": "Multicolor unions excluding explicit background.",
    "background": "Background color evidence.", "hud": "Thin edge-region evidence.",
    "lattice": "Supported grid spacing/origin proposals.", "cells": "Explicit grid-cell color counts.",
    "symmetry": "Exact reflection/rotation evidence.",
    "track": "Latest-pair motion candidates; ambiguity preserved.",
    "find": "Exact/wildcard template search.",
}


def _grid(frame):
    return tuple(tuple(frame.cells[row * frame.cols:(row + 1) * frame.cols]) for row in range(frame.rows))


def _components(cache, frame, connectivity):
    # Import at call time to avoid a module cycle. Both passes reuse the original
    # component implementation so IDs/hashes remain identical to vision.objects.
    from inference.agent.cpu_vision import _component_cells, _objects

    def compute():
        result = _objects(frame, connectivity)
        members = _component_cells(frame.cells, frame.rows, frame.cols, connectivity)
        for item, (_, cells) in zip(result, members):
            item["cells"] = [list(cell) for cell in cells]
        return result

    return cache._cached(("tool-components-v1", frame.rows, frame.cols, frame.cells, connectivity), compute)


def run_extra(cache, message):
    operation = message["operation"]
    module = _OWNERS[operation]
    options = {key: value for key, value in message.items() if key not in {"type", "operation"}}
    frame_name = options.pop("frame", "current")
    if type(frame_name) is not str or frame_name not in {"current", "previous"}:
        raise ValueError("frame must be 'current' or 'previous'.")
    if operation == "track" and frame_name != "current":
        raise ValueError("track uses the latest previous/current pair.")
    connectivity = options.pop("connectivity", 4)
    if type(connectivity) is not int or connectivity not in (4, 8):
        raise ValueError("connectivity must be 4 or 8 (not bool).")
    try:
        encoded_options = json.dumps(options, sort_keys=True, allow_nan=False, ensure_ascii=True, separators=(",", ":"))
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError("Vision arguments must be finite JSON values.") from exc
    if len(encoded_options) > 32768:
        raise ValueError("Vision arguments exceed the 32 KiB limit.")
    observation = cache._current if frame_name == "current" else cache._previous
    if observation is None:
        raise ValueError(f"No {frame_name} frame is available.")
    frame = observation.frame
    temporal = operation in module.TEMPORAL_OPS
    status = cache._status if frame_name == "current" else "missing_previous"
    previous = cache._previous if temporal and frame_name == "current" else None
    comparable = previous is not None and status == "ok"
    key = ("vision-tools-v1", operation, frame.rows, frame.cols, frame.cells, connectivity, encoded_options)
    if temporal:
        key += (cache._session, cache._epoch, observation.frame_id,
                previous.frame_id if previous else None,
                previous.frame.cells if previous else None, cache._action, status)

    def compute():
        need_components = operation in module.COMPONENT_OPS
        if operation == "symmetry" and options.get("object_id") is None:
            need_components = False
        if operation == "track" and not comparable:
            need_components = False
        components = _components(cache, frame, connectivity) if need_components else None
        prior_components = (_components(cache, previous.frame, connectivity)
                            if operation == "track" and comparable else None)
        return module.run(
            operation, _grid(frame), options, components=components,
            previous_grid=_grid(previous.frame) if comparable else None,
            previous_components=prior_components, transition_status=status, connectivity=connectivity,
        )

    result = cache._cached(key, compute)
    # Geometry can be reused at a later observation; attach fresh metadata only
    # after retrieval. No caller mutation can enter the encoded host cache.
    result["frame_id"] = observation.frame_id
    if temporal:
        result.update({"before_frame_id": previous.frame_id if previous else None,
                       "after_frame_id": observation.frame_id,
                       "action": cache._action if frame_name == "current" else None,
                       "transition_status": status})
    return result
