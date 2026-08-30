"""q101 Carousel Coordinates -- compose local controls with a rotating world frame."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

CELL, OX, OY, SIZE = 8, 12, 14, 5
BG, BOARD, GRID, WALL, PLAYER, GOAL, COMPASS, BAD = 12, 0, 10, 13, 6, 14, 9, 8
DIRS = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}
LEVELS = [
    {"name": "Quarter Turn", "start": (1, 2), "goal": (1, 0), "orientation": 1, "spin": 0, "walls": [], "budget": 5},
    {"name": "Upside Down", "start": (4, 1), "goal": (1, 1), "orientation": 2, "spin": 0, "walls": [], "budget": 6},
    {"name": "Turning Step", "start": (2, 2), "goal": (4, 3), "orientation": 0, "spin": 1, "walls": [], "budget": 8},
    {"name": "Carousel Wall", "start": (0, 4), "goal": (4, 0), "orientation": 3, "spin": 1, "walls": [(1, 3), (2, 3), (2, 1)], "budget": 14},
    {"name": "Counter Carousel", "start": (4, 4), "goal": (0, 0), "orientation": 2, "spin": -1, "walls": [(3, 4), (3, 2), (1, 2)], "budget": 16},
    {"name": "Carousel Coordinates", "start": (0, 2), "goal": (4, 2), "orientation": 1, "spin": 1, "walls": [(1, 1), (2, 1), (2, 3), (3, 3)], "budget": 20},
]


def rotate(vector, turns):
    dx, dy = vector
    for _ in range(turns % 4): dx, dy = -dy, dx
    return dx, dy


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    @staticmethod
    def fill(frame, cell, color, inset=0):
        x, y = cell; px, py = OX + x * CELL, OY + y * CELL; frame[py + inset:py + CELL - inset, px + inset:px + CELL - inset] = color
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG; frame[OY:OY + SIZE * CELL, OX:OX + SIZE * CELL] = BOARD
        for y in range(SIZE):
            for x in range(SIZE): self.fill(frame, (x, y), GRID, 1)
        for wall in g.walls: self.fill(frame, wall, WALL, 1)
        self.fill(frame, g.goal, GOAL, 1); self.fill(frame, g.goal, BOARD, 3)
        self.fill(frame, g.pos, PLAYER, 1); self.fill(frame, g.pos, 0, 3)
        cx, cy = 32, 7; frame[cy - 3:cy + 4, cx - 3:cx + 4] = BOARD
        dx, dy = rotate((0, -1), g.orientation); frame[cy + dy * 3 - 1:cy + dy * 3 + 2, cx + dx * 3 - 1:cx + dx * 3 + 2] = COMPASS
        for i in range(min(9, g.budget_left)): frame[59:62, 5 + i * 6:9 + i * 6] = COMPASS
        if g.failed: frame[2:5, 26:38] = BAD
        return frame


class Q101(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.pos = self.goal = (0, 0); self.walls = set(); self.orientation = self.spin = self.budget_left = 0; self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q101", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [1, 2, 3, 4])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.pos = tuple(s["start"]); self.goal = tuple(s["goal"]); self.walls = set(map(tuple, s["walls"])); self.orientation = s["orientation"]; self.spin = s["spin"]; self.budget_left = s["budget"]; self.failed = False
    def step(self):
        if self.action.id.value == 0: self.complete_action(); return
        if self.action.id.value not in DIRS: self.failed = True; self.lose(); self.complete_action(); return
        self.budget_left -= 1; dx, dy = rotate(DIRS[self.action.id.value], self.orientation); nxt = (self.pos[0] + dx, self.pos[1] + dy)
        if 0 <= nxt[0] < SIZE and 0 <= nxt[1] < SIZE and nxt not in self.walls: self.pos = nxt
        self.orientation = (self.orientation + self.spin) % 4
        if self.pos == self.goal: self.next_level()
        elif self.budget_left <= 0: self.failed = True; self.lose()
        self.complete_action()
