"""q121 Habit Hunter -- evade a predator that blocks the recent modal action."""

from __future__ import annotations
from collections import Counter
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

CELL, OX, OY, SIZE = 8, 8, 10, 6
BG, FLOOR, WALL, PLAYER, GOAL, HUNTER, TRACE, BAD = 7, 0, 15, 9, 14, 8, 12, 13
DIRS = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}
LEVELS = [
    {"name": "Break the Habit", "start": (1, 2), "goal": (4, 2), "history": [3, 3], "window": 2, "walls": [], "budget": 8},
    {"name": "Corner Prediction", "start": (1, 4), "goal": (4, 1), "history": [2, 2], "window": 3, "walls": [(2, 3)], "budget": 13},
    {"name": "Narrow Memory", "start": (0, 5), "goal": (5, 0), "history": [3, 3, 1], "window": 3, "walls": [(1, 4), (2, 2), (3, 2)], "budget": 18},
    {"name": "Learned Corridor", "start": (0, 3), "goal": (5, 3), "history": [4, 4, 4], "window": 4, "walls": [(2, 3), (2, 4), (4, 2)], "budget": 20},
    {"name": "Long Memory", "start": (5, 5), "goal": (0, 0), "history": [2, 2, 4, 4], "window": 5, "walls": [(4, 3), (3, 3), (1, 2)], "budget": 24},
    {"name": "Habit Hunter", "start": (0, 5), "goal": (5, 0), "history": [1, 1, 3, 4, 3], "window": 5, "walls": [(1, 3), (2, 3), (3, 1), (3, 2), (4, 4)], "budget": 28},
]


def prediction(history):
    if not history: return None
    counts = Counter(history); return max(range(1, 5), key=lambda action: (counts[action], -action))


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    @staticmethod
    def fill(frame, cell, color, inset=0):
        x, y = cell; px, py = OX + x * CELL, OY + y * CELL; frame[py + inset:py + CELL - inset, px + inset:px + CELL - inset] = color
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG
        for y in range(SIZE):
            for x in range(SIZE): self.fill(frame, (x, y), FLOOR, 1)
        for wall in g.walls: self.fill(frame, wall, WALL, 1)
        self.fill(frame, g.goal, GOAL, 1); self.fill(frame, g.goal, FLOOR, 3); self.fill(frame, g.pos, PLAYER, 1)
        forbidden = prediction(g.history)
        if forbidden:
            dx, dy = DIRS[forbidden]; x, y = g.pos; mark = (x + dx, y + dy)
            if 0 <= mark[0] < SIZE and 0 <= mark[1] < SIZE: self.fill(frame, mark, HUNTER, 2)
        for i, action in enumerate(g.history[-8:]): frame[3:7, 4 + i * 7:9 + i * 7] = TRACE if action != forbidden else HUNTER
        if g.failed: frame[59:63, 25:39] = BAD
        return frame


class Q121(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.pos = self.goal = (0, 0); self.history = []; self.walls = set(); self.window = self.budget_left = 0; self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q121", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [1, 2, 3, 4])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.pos = tuple(s["start"]); self.goal = tuple(s["goal"]); self.history = list(s["history"]); self.window = s["window"]; self.walls = set(map(tuple, s["walls"])); self.budget_left = s["budget"]; self.failed = False
    def step(self):
        action = self.action.id.value; self.budget_left -= 1
        if action == 0: self.budget_left += 1; self.complete_action(); return
        if action not in DIRS: self.failed = True; self.lose(); self.complete_action(); return
        if action == prediction(self.history): self.failed = True; self.lose(); self.complete_action(); return
        dx, dy = DIRS[action]; nxt = (self.pos[0] + dx, self.pos[1] + dy)
        if 0 <= nxt[0] < SIZE and 0 <= nxt[1] < SIZE and nxt not in self.walls: self.pos = nxt
        self.history = (self.history + [action])[-self.window:]
        if self.pos == self.goal: self.next_level()
        elif self.budget_left <= 0: self.failed = True; self.lose()
        self.complete_action()
