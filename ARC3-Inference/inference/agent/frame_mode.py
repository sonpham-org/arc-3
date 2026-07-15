"""Harness-level frame mode: last-frame (default) vs full-frame animation.

`last`  -- the agent's runtime state carries only the settled post-action frame
           (`current_frame`); a multi-frame engine animation is collapsed to its
           final frame, exactly as the stock harness has always behaved.
`full`  -- the harness additionally captures every frame the engine produced for
           each action and exposes it to the agent's python sandbox as the
           `last_animation` global (one entry per action, each with `.frames`).

Selected by the run config via the ARC3_FRAME_MODE env var so a single bundle
can run either way -- no separate patched bundle. Default is `last`, so existing
runs are unchanged unless they opt in.
"""
from __future__ import annotations

import os


def frame_mode() -> str:
    mode = os.environ.get("ARC3_FRAME_MODE", "").strip().lower()
    return "full" if mode == "full" else "last"


def full_frame_enabled() -> bool:
    return frame_mode() == "full"
