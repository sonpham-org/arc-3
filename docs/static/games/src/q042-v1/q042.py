"""q042 Sonar Pips -- triangulate a hidden beacon from scarce distance readings."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

CELL, OX, OY, SIZE = 8, 8, 10, 6
BG, SEA, GRID, CURSOR, PROBE, PIP, BEACON, BAD = 9, 10, 0, 11, 15, 12, 14, 8
DIRS = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}
LEVELS = [
    {"name": "One Ping", "target": (2, 0), "probes": 1, "budget": 7},
    {"name": "Cross Bearings", "target": (4, 3), "probes": 2, "budget": 12},
    {"name": "Edge Echo", "target": (0, 5), "probes": 2, "budget": 13},
    {"name": "Sparse Sonar", "target": (5, 1), "probes": 2, "budget": 14},
    {"name": "Ambiguous Rings", "target": (3, 4), "probes": 3, "budget": 15},
    {"name": "Sonar Pips", "target": (5, 5), "probes": 3, "budget": 17},
]


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    @staticmethod
    def fill(frame, cell, color, inset=0):
        x, y = cell; px, py = OX + x * CELL, OY + y * CELL; frame[py + inset:py + CELL - inset, px + inset:px + CELL - inset] = color
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG
        for y in range(SIZE):
            for x in range(SIZE): self.fill(frame, (x, y), SEA, 1)
        for cell, distance in g.readings:
            self.fill(frame, cell, PROBE, 2); px, py = OX + cell[0] * CELL, OY + cell[1] * CELL
            for i in range(min(distance, 5)): frame[py + 1:py + 3, px + 1 + i:px + 2 + i] = PIP
        self.fill(frame, g.cursor, CURSOR, 2)
        for i in range(g.probes_left): frame[3:6, 9 + i * 9:15 + i * 9] = PROBE
        if g.failed: frame[59:63, 25:39] = BAD
        return frame


class Q042(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.target = self.cursor = (0, 0); self.readings = []; self.probes_left = self.budget_left = 0; self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q042", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [1, 2, 3, 4, 5, 6])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.target = tuple(s["target"]); self.cursor = (0, 0); self.readings = []; self.probes_left = s["probes"]; self.budget_left = s["budget"]; self.failed = False
    def step(self):
        action = self.action.id.value
        if action == 0: self.complete_action(); return
        self.budget_left -= 1
        if action in DIRS:
            dx, dy = DIRS[action]; self.cursor = (max(0, min(SIZE - 1, self.cursor[0] + dx)), max(0, min(SIZE - 1, self.cursor[1] + dy)))
        elif action == 6 and self.probes_left:
            distance = abs(self.cursor[0] - self.target[0]) + abs(self.cursor[1] - self.target[1]); self.readings.append((self.cursor, distance)); self.probes_left -= 1
        elif action == 5:
            if self.cursor == self.target: self.next_level()
            else: self.failed = True; self.lose()
        else: self.failed = True; self.lose()
        if self.budget_left <= 0: self.failed = True; self.lose()
        self.complete_action()
