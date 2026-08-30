"""q171 Elastic Balance -- redistribute tension by moving coupled anchors."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

BG, CANVAS, BAND, ANCHOR, CURSOR, TARGET, LOCK, BAD = 15, 0, 6, 9, 11, 14, 3, 8
LEVELS = [
    {"name": "First Stretch", "start": [1, 3], "target": [3, 3], "coupled": False, "locked": [], "budget": 5},
    {"name": "Three Anchors", "start": [1, 4, 2], "target": [3, 2, 4], "coupled": False, "locked": [], "budget": 12},
    {"name": "Fixed Peg", "start": [2, 4, 1, 3], "target": [4, 4, 3, 1], "coupled": False, "locked": [1], "budget": 14},
    {"name": "Shared Tension", "start": [2, 2, 2], "target": [3, 0, 3], "coupled": True, "locked": [], "budget": 10},
    {"name": "Elastic Cascade", "start": [3, 3, 3, 3], "target": [2, 2, 4, 1], "coupled": True, "locked": [], "budget": 14},
    {"name": "Elastic Balance", "start": [4, 4, 4, 4, 4], "target": [4, 5, 2, 4, 5], "coupled": True, "locked": [], "budget": 20},
]


def adjust(values, index, delta, coupled, locked):
    out = list(values)
    if index in locked or not 0 <= out[index] + delta <= 8: return tuple(out)
    changes = {index: delta}
    if coupled:
        for neighbor in (index - 1, index + 1):
            if 0 <= neighbor < len(out) and neighbor not in locked: changes[neighbor] = -delta
    if any(not 0 <= out[i] + change <= 8 for i, change in changes.items()): return tuple(out)
    for i, change in changes.items(): out[i] += change
    return tuple(out)


def line(frame, a, b, color):
    x0, y0 = a; x1, y1 = b; steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    for i in range(steps + 1):
        x = round(x0 + (x1 - x0) * i / steps); y = round(y0 + (y1 - y0) * i / steps); frame[y - 1:y + 2, x - 1:x + 2] = color


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG; frame[6:58, 4:60] = CANVAS; n = len(g.values); xs = [9 + round(i * 46 / max(1, n - 1)) for i in range(n)]; points = [(x, 50 - value * 5) for x, value in zip(xs, g.values)]
        for a, b in zip(points, points[1:]): line(frame, a, b, BAND)
        for i, ((x, y), wanted) in enumerate(zip(points, g.target)):
            ty = 50 - wanted * 5; frame[ty - 1:ty + 2, x - 3:x + 4] = TARGET; frame[y - 3:y + 4, x - 3:x + 4] = LOCK if i in g.locked else (CURSOR if i == g.cursor else ANCHOR)
        if g.coupled: frame[2:5, 22:42] = BAND
        for i in range(min(9, g.budget_left)): frame[60:63, 5 + i * 6:9 + i * 6] = ANCHOR
        if g.failed: frame[2:5, 25:39] = BAD
        return frame


class Q171(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.values = self.target = (); self.locked = set(); self.cursor = self.budget_left = 0; self.coupled = self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q171", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [1, 2, 3, 4])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.values = tuple(s["start"]); self.target = tuple(s["target"]); self.locked = set(s["locked"]); self.coupled = s["coupled"]; self.cursor = 0; self.budget_left = s["budget"]; self.failed = False
    def step(self):
        action = self.action.id.value; self.budget_left -= 1
        if action == 0: self.budget_left += 1; self.complete_action(); return
        if action == 3: self.cursor = (self.cursor - 1) % len(self.values)
        elif action == 4: self.cursor = (self.cursor + 1) % len(self.values)
        elif action in (1, 2): self.values = adjust(self.values, self.cursor, -1 if action == 1 else 1, self.coupled, self.locked)
        if self.values == self.target: self.next_level()
        elif self.budget_left <= 0: self.failed = True; self.lose()
        self.complete_action()
