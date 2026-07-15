"""Model-agnostic click heuristics (ported from the 2nd-place milestone solution).

Pure stdlib, no GPU, operate only on the MOUSE (ACTION6) path. Off by default so
the harness is byte-identical to baseline unless a flag is set.

CLICK_DEADSIG=1 : "dead-signature" pruning. Each clicked object gets a
    position-invariant signature (colour + normalized cell shape). If clicking a
    signature never changes the frame CLICK_DEADSIG_K (default 2) times, further
    clicks on that class are suppressed for the rest of the level -- including the
    model's own repeat clicks. A signature that EVER changes the frame is protected
    (never suppressed). Reset per level (an L0-inert class may be the L1 win class).
"""
from __future__ import annotations

import os


def deadsig_enabled() -> bool:
    return os.environ.get("CLICK_DEADSIG", "0").strip().lower() in {"1", "true", "yes", "on"}


def deadsig_k() -> int:
    try:
        return max(1, int(os.environ.get("CLICK_DEADSIG_K", "2")))
    except ValueError:
        return 2


def _component_at(grid, row: int, col: int):
    """The 4-connected same-colour component containing (row, col), or None."""
    rows = len(grid)
    if rows == 0:
        return None
    if not (0 <= row < rows and 0 <= col < len(grid[row])):
        return None
    color = grid[row][col]
    seen: set[tuple[int, int]] = set()
    stack = [(row, col)]
    while stack:
        r, c = stack.pop()
        if (r, c) in seen:
            continue
        if not (0 <= r < rows and 0 <= c < len(grid[r])):
            continue
        if grid[r][c] != color:
            continue
        seen.add((r, c))
        stack.extend([(r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)])
    return color, seen


def click_signature(grid, row: int, col: int):
    """Position-invariant click target: (colour, frozenset of normalized offsets).
    Same colour+shape anywhere on the board -> same signature (like twins)."""
    comp = _component_at(grid, row, col)
    if comp is None:
        return None
    color, cells = comp
    if not cells:
        return None
    min_r = min(r for r, _ in cells)
    min_c = min(c for _, c in cells)
    return (int(color), frozenset((r - min_r, c - min_c) for r, c in cells))


class DeadSigTracker:
    """Per-level dead-click memory. Call reset() when a new level starts."""

    def __init__(self) -> None:
        self._counts: dict = {}
        self._dead: set = set()
        self._live: set = set()  # signatures that ever changed the frame -> protected

    def is_dead(self, sig) -> bool:
        return sig is not None and sig in self._dead

    def record(self, sig, board_changed: bool, k: int) -> None:
        if sig is None:
            return
        if board_changed:
            self._live.add(sig)
            self._dead.discard(sig)
            self._counts.pop(sig, None)
        elif sig not in self._live:
            self._counts[sig] = self._counts.get(sig, 0) + 1
            if self._counts[sig] >= k:
                self._dead.add(sig)

    def reset(self) -> None:
        self._counts.clear()
        self._dead.clear()
        self._live.clear()

    def dead_count(self) -> int:
        return len(self._dead)
