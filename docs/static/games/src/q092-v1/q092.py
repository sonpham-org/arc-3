"""q092 Nesting Rooms -- solve inner boundaries that transform their containers."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

BG, ROOM, ACTIVE, TARGET, SEALED, CORE, BAD = 8, [7, 12, 10, 15, 11], 0, 14, 3, 6, 13
LEVELS = [
    {"name": "Inner Room", "start": [0], "target": [1], "influence": [], "budget": 3},
    {"name": "Room Changes Room", "start": [0, 0], "target": [1, 2], "influence": [1], "budget": 6},
    {"name": "Three Boundaries", "start": [2, 0, 1], "target": [0, 2, 3], "influence": [1, 2], "budget": 10},
    {"name": "Inverse Nest", "start": [1, 3, 0, 2], "target": [3, 0, 2, 1], "influence": [-1, 1, 2], "budget": 14},
    {"name": "Nested Carry", "start": [0, 1, 2, 3, 0], "target": [2, 0, 3, 1, 2], "influence": [1, 2, -1, 1], "budget": 18},
    {"name": "Nesting Rooms", "start": [3, 0, 2, 1, 3], "target": [1, 3, 0, 2, 1], "influence": [2, -1, 1, 2], "budget": 22},
]


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG; n = len(g.values)
        for i in range(n):
            inset = 5 + i * 5; color = SEALED if i < g.active else ROOM[g.values[i] % len(ROOM)]; frame[inset:64 - inset, inset:64 - inset] = color
            frame[inset + 2:inset + 5, 28:36] = TARGET if g.values[i] == g.target[i] else ACTIVE
        frame[28:36, 28:36] = CORE
        for i in range(min(10, g.budget_left)): frame[60:63, 3 + i * 6:7 + i * 6] = ACTIVE
        if g.failed: frame[2:5, 25:39] = BAD
        return frame


class Q092(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.values = []; self.target = []; self.influence = []; self.active = self.budget_left = 0; self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q092", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [1, 2, 5])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.values = list(s["start"]); self.target = list(s["target"]); self.influence = list(s["influence"]); self.active = 0; self.budget_left = s["budget"]; self.failed = False
    def step(self):
        action = self.action.id.value
        if action == 0: self.complete_action(); return
        self.budget_left -= 1
        if action in (1, 2): self.values[self.active] = (self.values[self.active] + (-1 if action == 1 else 1)) % 4
        elif action == 5:
            if self.values[self.active] != self.target[self.active]: self.failed = True; self.lose()
            else:
                if self.active < len(self.values) - 1: self.values[self.active + 1] = (self.values[self.active + 1] + self.influence[self.active]) % 4
                self.active += 1
                if self.active == len(self.values): self.next_level()
        else: self.failed = True; self.lose()
        if self.budget_left <= 0: self.failed = True; self.lose()
        self.complete_action()
