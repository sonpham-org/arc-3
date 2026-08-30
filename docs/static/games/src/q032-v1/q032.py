"""q032 Parity Forge -- reach exact patterns with pairwise parity-preserving strikes."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

BG, FORGE, OFF, ON, LINK, CURSOR, TARGET, BAD = 13, 12, 3, 11, 15, 9, 14, 8
LEVELS = [
    {"name": "Paired Spark", "start": 0b00, "target": 0b11, "n": 2, "pairs": [(0, 1)], "budget": 3},
    {"name": "Moving Pair", "start": 0b001, "target": 0b100, "n": 3, "pairs": [(0, 1), (1, 2)], "budget": 6},
    {"name": "Even Class", "start": 0b0011, "target": 0b1100, "n": 4, "pairs": [(0, 1), (1, 2), (2, 3)], "budget": 9},
    {"name": "Ring Parity", "start": 0b00011, "target": 0b11000, "n": 5, "pairs": [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)], "budget": 12},
    {"name": "Cross Strike", "start": 0b001001, "target": 0b100100, "n": 6, "pairs": [(0, 1), (1, 2), (2, 5), (5, 4), (4, 3), (3, 0)], "budget": 15},
    {"name": "Parity Forge", "start": 0b001011, "target": 0b110010, "n": 6, "pairs": [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0), (1, 4)], "budget": 18},
]


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG; frame[9:55, 4:60] = FORGE; gap = 46 // g.n
        for i in range(g.n):
            x = 10 + i * gap; frame[20:34, x:x + 7] = ON if g.bits & (1 << i) else OFF; frame[15:18, x:x + 7] = TARGET if g.target & (1 << i) else OFF
        for i, (a, b) in enumerate(g.pairs):
            x = 7 + i * 7; frame[43:49, x:x + 5] = CURSOR if i == g.cursor else LINK
            frame[50:53, x:x + 2] = a + 6; frame[50:53, x + 3:x + 5] = b + 6
        if g.failed: frame[59:63, 25:39] = BAD
        return frame


class Q032(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.bits = self.target = self.n = self.cursor = self.budget_left = 0; self.pairs = []; self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q032", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [3, 4, 5, 6])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.bits = s["start"]; self.target = s["target"]; self.n = s["n"]; self.pairs = list(map(tuple, s["pairs"])); self.cursor = 0; self.budget_left = s["budget"]; self.failed = False
    def step(self):
        action = self.action.id.value
        if action == 0: self.complete_action(); return
        self.budget_left -= 1
        if action == 3: self.cursor = (self.cursor - 1) % len(self.pairs)
        elif action == 4: self.cursor = (self.cursor + 1) % len(self.pairs)
        elif action == 5:
            a, b = self.pairs[self.cursor]; self.bits ^= (1 << a) | (1 << b)
        elif action == 6:
            if self.bits == self.target: self.next_level()
            else: self.failed = True; self.lose()
        else: self.failed = True; self.lose()
        if self.budget_left <= 0: self.failed = True; self.lose()
        self.complete_action()
