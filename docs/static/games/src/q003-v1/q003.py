"""q003 Blind Growth -- direct an organism by aiming observation away from growth."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

CELL, OX, OY, SIZE = 7, 11, 16, 6
BG, SOIL, GRID, WALL, BRANCH, TIP, GOAL, EYE, BAD = 14, 13, 12, 3, 10, 11, 6, 9, 8
DIRS = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}
OPPOSITE = {1: 2, 2: 1, 3: 4, 4: 3}
LEVELS = [
    {"name": "Grow Unseen", "start": (1, 2), "goal": (4, 2), "walls": [], "budget": 7},
    {"name": "Turn the Gaze", "start": (1, 4), "goal": (4, 1), "walls": [], "budget": 13},
    {"name": "Pruned Corner", "start": (0, 5), "goal": (5, 0), "walls": [(2, 3), (2, 2)], "budget": 21},
    {"name": "Blind Corridor", "start": (0, 2), "goal": (5, 2), "walls": [(2, 2), (2, 3), (4, 1)], "budget": 23},
    {"name": "Held Direction", "start": (5, 5), "goal": (0, 0), "walls": [(4, 3), (3, 3), (1, 2)], "budget": 25},
    {"name": "Blind Growth", "start": (0, 5), "goal": (5, 0), "walls": [(1, 3), (2, 3), (3, 1), (3, 2), (4, 4)], "budget": 29},
]


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    @staticmethod
    def fill(frame, cell, color, inset=0):
        x, y = cell; px, py = OX + x * CELL, OY + y * CELL; frame[py + inset:py + CELL - inset, px + inset:px + CELL - inset] = color
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG; frame[OY:OY + SIZE * CELL, OX:OX + SIZE * CELL] = SOIL
        for y in range(SIZE):
            for x in range(SIZE): self.fill(frame, (x, y), GRID, 1)
        for wall in g.walls: self.fill(frame, wall, WALL, 1)
        for cell in g.trail: self.fill(frame, cell, BRANCH, 2)
        self.fill(frame, g.goal, GOAL, 1); self.fill(frame, g.tip, TIP, 1)
        frame[4:11, 28:36] = EYE; dx, dy = DIRS[g.facing]; frame[6 + dy * 5:9 + dy * 5, 30 + dx * 5:34 + dx * 5] = 0
        if g.failed: frame[60:63, 25:39] = BAD
        return frame


class Q003(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.tip = self.goal = (0, 0); self.trail = []; self.walls = set(); self.facing = self.budget_left = 0; self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q003", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [1, 2, 3, 4, 5])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.tip = tuple(s["start"]); self.goal = tuple(s["goal"]); self.trail = [self.tip]; self.walls = set(map(tuple, s["walls"])); self.facing = 3; self.budget_left = s["budget"]; self.failed = False
    def step(self):
        action = self.action.id.value
        if action == 0: self.complete_action(); return
        self.budget_left -= 1
        if action in DIRS: self.facing = action
        elif action == 5:
            dx, dy = DIRS[OPPOSITE[self.facing]]; nxt = (self.tip[0] + dx, self.tip[1] + dy)
            if not (0 <= nxt[0] < SIZE and 0 <= nxt[1] < SIZE) or nxt in self.walls or nxt in self.trail: self.failed = True; self.lose()
            else: self.tip = nxt; self.trail.append(nxt)
        else: self.failed = True; self.lose()
        if self.tip == self.goal: self.next_level()
        elif self.budget_left <= 0: self.failed = True; self.lose()
        self.complete_action()
