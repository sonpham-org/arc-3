"""q052 Lens Bench -- assemble oriented fragments into a functional beam tool."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

BG, BENCH, LENS, CURSOR, BEAM, TARGET, FIXED, BAD = 7, 1, 10, 11, 12, 14, 3, 8
LEVELS = [
    {"name": "One Fragment", "start": [0], "coeff": [1], "target": 1, "fixed": [], "budget": 4},
    {"name": "Two Surfaces", "start": [0, 0], "coeff": [1, 1], "target": 3, "fixed": [], "budget": 8},
    {"name": "Opposed Curves", "start": [1, 0, 2], "coeff": [1, -1, 1], "target": 0, "fixed": [], "budget": 11},
    {"name": "Fixed Pane", "start": [2, 1, 0], "coeff": [1, 1, -1], "target": 2, "fixed": [1], "budget": 12},
    {"name": "Compound Lens", "start": [0, 3, 1, 2], "coeff": [1, -1, 1, 1], "target": 1, "fixed": [2], "budget": 15},
    {"name": "Lens Bench", "start": [3, 0, 2, 1, 0], "coeff": [1, -1, 1, -1, 1], "target": 2, "fixed": [1, 3], "budget": 18},
]


def exit_direction(angles, coeff): return sum(angle * sign for angle, sign in zip(angles, coeff)) % 4


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG; frame[10:54, 4:60] = BENCH; n = len(g.angles); gap = 44 // n
        frame[30:34, 5:58] = BEAM
        for i, angle in enumerate(g.angles):
            x = 12 + i * gap; frame[18:46, x:x + 5] = FIXED if i in g.fixed else (CURSOR if i == g.cursor else LENS)
            if angle % 2: frame[29:35, x - 3:x + 8] = LENS
            else: frame[22 + angle * 4:27 + angle * 4, x - 2:x + 7] = LENS
        direction = exit_direction(g.angles, g.coeff); dx, dy = {0: (1, 0), 1: (0, -1), 2: (-1, 0), 3: (0, 1)}[direction]; frame[29 + dy * 15:35 + dy * 15, 54 + dx * 5:59 + dx * 5] = BEAM
        tx, ty = {0: (59, 32), 1: (56, 12), 2: (5, 32), 3: (56, 48)}[g.target]; frame[ty - 3:ty + 4, tx - 3:tx + 4] = TARGET
        if g.failed: frame[59:63, 25:39] = BAD
        return frame


class Q052(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.angles = (); self.coeff = (); self.fixed = set(); self.target = self.cursor = self.budget_left = 0; self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q052", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [1, 2, 3, 4, 5])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.angles = tuple(s["start"]); self.coeff = tuple(s["coeff"]); self.fixed = set(s["fixed"]); self.target = s["target"]; self.cursor = 0; self.budget_left = s["budget"]; self.failed = False
    def step(self):
        action = self.action.id.value
        if action == 0: self.complete_action(); return
        self.budget_left -= 1
        if action == 3: self.cursor = (self.cursor - 1) % len(self.angles)
        elif action == 4: self.cursor = (self.cursor + 1) % len(self.angles)
        elif action in (1, 2) and self.cursor not in self.fixed:
            values = list(self.angles); values[self.cursor] = (values[self.cursor] + (-1 if action == 1 else 1)) % 4; self.angles = tuple(values)
        elif action == 5:
            if exit_direction(self.angles, self.coeff) == self.target: self.next_level()
            else: self.failed = True; self.lose()
        elif action not in (1, 2): self.failed = True; self.lose()
        if self.budget_left <= 0: self.failed = True; self.lose()
        self.complete_action()
