"""Harness-level frame mode: last-frame (default) vs full-frame animation.

`full`  (default) -- the harness captures every frame the engine produced for
           each action and exposes it to the agent's python sandbox as the
           `last_animation` global (one entry per action, each with `.frames`),
           plus a running `frame_stats` gauge. The settled `current_frame` is
           still always present; the extra frames are the agent's to use or
           ignore, per turn, as it judges the motion informative.
`last`  -- collapse each engine animation to its final frame only, exactly as
           the stock harness always behaved. Kept as the ablation arm for A/B.

Selected by the run config via the ARC3_FRAME_MODE env var so a single bundle
can run either way -- no separate patched bundle. Default is `full`; set
ARC3_FRAME_MODE=last for the last-frame-only ablation.
"""
from __future__ import annotations

import os


def frame_mode() -> str:
    mode = os.environ.get("ARC3_FRAME_MODE", "").strip().lower()
    return "last" if mode == "last" else "full"


def full_frame_enabled() -> bool:
    return frame_mode() == "full"
