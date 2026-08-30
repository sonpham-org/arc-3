"""q022 Counterweight Lab -- discover coupled platform effects and exact ratios."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

BG, LAB, PLATFORM, WEIGHT, TARGET, CURSOR, ENERGY, BAD = 15, 0, 3, 12, 14, 9, 11, 8
LEVELS = [
    {"name": "One Counterweight", "start": [1, 3], "target": [3, 1], "moves": [(1, -1)], "budget": 4},
    {"name": "Shared Cable", "start": [1, 1], "target": [3, 3], "moves": [(1, 1), (2, -1)], "budget": 5},
    {"name": "Unequal Pulleys", "start": [0, 4, 2], "target": [2, 3, 3], "moves": [(1, -1, 0), (0, 1, 1), (2, 0, -1)], "budget": 9},
    {"name": "Crossed Rig", "start": [1, 3, 1], "target": [4, 1, 2], "moves": [(1, -1, 0), (1, 0, 1), (0, 2, -1)], "budget": 11},
    {"name": "Ratio Bank", "start": [2, 2, 2, 2], "target": [4, 1, 4, 1], "moves": [(2, -1, 0, 0), (0, 0, 2, -1), (1, 1, -1, -1)], "budget": 13},
    {"name": "Counterweight Lab", "start": [1, 4, 1, 4], "target": [4, 1, 3, 2], "moves": [(1, -1, 0, 0), (0, 0, 1, -1), (1, 0, 1, -1), (0, -1, 1, 0)], "budget": 17},
]


def apply(values, delta):
    out = tuple(value + change for value, change in zip(values, delta)); return out if all(0 <= value <= 6 for value in out) else tuple(values)


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG; frame[7:57, 5:59] = LAB; n = len(g.values); gap = 46 // n
        for i, (value, wanted) in enumerate(zip(g.values, g.target)):
            x = 10 + i * gap; y = 48 - value * 5; ty = 48 - wanted * 5; frame[y:y + 4, x:x + gap - 3] = PLATFORM; frame[ty - 1:ty + 1, x:x + gap - 3] = TARGET; frame[y - 5:y, x + 2:x + 6] = WEIGHT
        for i in range(len(g.moves)): frame[52:57, 8 + i * 12:17 + i * 12] = CURSOR if i == g.cursor else WEIGHT
        for i in range(min(8, g.budget_left)): frame[2:5, 7 + i * 7:12 + i * 7] = ENERGY
        if g.failed: frame[59:63, 25:39] = BAD
        return frame


class Q022(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.values = self.target = (); self.moves = []; self.cursor = self.budget_left = 0; self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q022", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [3, 4, 5, 6])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.values = tuple(s["start"]); self.target = tuple(s["target"]); self.moves = list(map(tuple, s["moves"])); self.cursor = 0; self.budget_left = s["budget"]; self.failed = False
    def step(self):
        action = self.action.id.value
        if action == 0: self.complete_action(); return
        self.budget_left -= 1
        if action == 3: self.cursor = (self.cursor - 1) % len(self.moves)
        elif action == 4: self.cursor = (self.cursor + 1) % len(self.moves)
        elif action == 5: self.values = apply(self.values, self.moves[self.cursor])
        elif action == 6:
            if self.values == self.target: self.next_level()
            else: self.failed = True; self.lose()
        else: self.failed = True; self.lose()
        if self.budget_left <= 0: self.failed = True; self.lose()
        self.complete_action()
