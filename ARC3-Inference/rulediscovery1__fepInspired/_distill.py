# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: The single import shim between the rulediscovery1__fepInspired package and the round-four-to-seven
#   analysis code in ../distill/. distill/ is not a package: its modules import each other as
#   top-level names after putting their own folder on sys.path (e.g. `import object_events as oe`).
#   This module does that path insert exactly once and re-exports the modules the prototype reuses,
#   so every other file in the package writes `from ._distill import oe, ag, efe, hy, fd` and never
#   touches sys.path itself. Heavy modules (round7 pulls in the EBUL training stack through round4;
#   ebul_perception globs the trace folders at import) are loaded lazily on first use.
#   Reused (imported, never copied):
#     object_events (oe)       -- board_comps, match_events, canonical, Step, Trace, load, NOVEL, MASKED
#     agency_contexts (ag)     -- AgencyTracker, AgencyPerception, look_ahead, touching, BUTTONS
#     efe_trace_analysis (efe) -- eig, kl_dirichlet, Beliefs, hud_mask, MOUSE_RE, BASE_OUTCOMES
#     heldout_yardstick (hy)   -- TypePriorBeliefs, folds, support_of, clear_table, NOVEL
#     feature_detectors (fd)   -- PlayState, View, DETECTORS (incl. last_label), label_kind
#     round7 (lazy)            -- Model(chain=True): the chained specific -> general back-off
#     ebul_perception (lazy)   -- trace_paths(n)
#   Nothing is executed at import beyond the distill modules' own imports.
# SRP/DRY check: Pass -- one place owns the path hack; distill/ files are not edited or copied.
"""One import shim into ../distill (not a package)."""
from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

DISTILL_DIR = Path(__file__).resolve().parent.parent / "distill"
if str(DISTILL_DIR) not in sys.path:
    sys.path.insert(0, str(DISTILL_DIR))

import agency_contexts as ag  # noqa: E402
import efe_trace_analysis as efe  # noqa: E402
import feature_detectors as fd  # noqa: E402
import heldout_yardstick as hy  # noqa: E402
import object_events as oe  # noqa: E402

_LAZY: dict[str, ModuleType] = {}


def round7() -> ModuleType:
    """distill/round7.py, imported on first use (it imports round4 / EBUL modules, numpy+scipy only)."""
    if "round7" not in _LAZY:
        import round7 as _r7  # noqa: E402
        _LAZY["round7"] = _r7
    return _LAZY["round7"]


def ebul_perception() -> ModuleType:
    """distill/ebul_perception.py, imported on first use (for trace_paths)."""
    if "ep" not in _LAZY:
        import ebul_perception as _ep  # noqa: E402
        _LAZY["ep"] = _ep
    return _LAZY["ep"]


def chain_model(vocab0: list[str]):
    """A fresh round7.Model with the chained back-off (level i backs off to level i-1, level 0 to the
    play's pooled outcome distribution, same beta as the yardstick)."""
    return round7().Model(vocab0, chain=True)


__all__ = ["ag", "efe", "fd", "hy", "oe", "round7", "ebul_perception", "chain_model", "DISTILL_DIR"]
