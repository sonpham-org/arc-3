"""q061 Split Couriers -- each room displays the other courier's hidden hazards."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

CELL, OY, LOX, ROX = 5, 18, 2, 34
BG_LEFT, BG_RIGHT, FLOOR, WALL, LEFT, RIGHT, HAZARD, GHOST, GOAL, SWITCH, GATE, WHITE = 10, 7, 1, 3, 9, 6, 8, 2, 14, 11, 12, 0
DIRS = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}


def pair(name, left, right, budget): return {"name": name, "left": left, "right": right, "budget": budget}
LEVELS = [
    pair("Across the Glass", ["######", "#S...#", "#..xG#", "######", "######", "######"], ["######", "#S.xG#", "#....#", "######", "######", "######"], 16),
    pair("Crossed Warnings", ["######", "#S.x.#", "#.#..#", "#...G#", "######", "######"], ["######", "#S...#", "#.##x#", "#...G#", "######", "######"], 24),
    pair("Alternating Steps", ["######", "#S...#", "#xx#.#", "#...G#", "######", "######"], ["######", "#S#..#", "#..x.#", "#x..G#", "######", "######"], 28),
    pair("Remote Latch", ["######", "#S.s##", "###..#", "#...G#", "######", "######"], ["######", "#S.dG#", "#....#", "######", "######", "######"], 28),
    pair("Two Latches", ["######", "#S.s.#", "#x##d#", "#...G#", "######", "######"], ["######", "#S.d.#", "#.#xs#", "#...G#", "######", "######"], 36),
    pair("Split Couriers", ["######", "#S.x.#", "#..s.#", "#x.dG#", "######", "######"], ["######", "#S.d.#", "#..#.#", "#xs.G#", "######", "######"], 42),
]


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    @staticmethod
    def fill(frame, ox, c, color, inset=0):
        x, y = c; px, py = ox + x * CELL, OY + y * CELL; frame[py + inset:py + CELL - inset, px + inset:px + CELL - inset] = color
    def room(self, frame, grid, other, pos, ox, body, active):
        for y in range(6):
            for x in range(6):
                ch = grid[y][x]; c = (x, y); self.fill(frame, ox, c, WALL if ch == "#" else FLOOR)
                # The room carries a small projection of hazards in the other room.
                if other[y][x] == "x": self.fill(frame, ox, c, GHOST, 2)
                if ch == "G": self.fill(frame, ox, c, GOAL, 1)
                elif ch == "s": self.fill(frame, ox, c, SWITCH, 2)
                elif ch == "d": self.fill(frame, ox, c, GATE, 1)
        self.fill(frame, ox, pos, WHITE if active else body, 1); self.fill(frame, ox, pos, body, 2)
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :32] = BG_LEFT; frame[:, 32:] = BG_RIGHT; self.room(frame, g.left, g.right, g.pos[0], LOX, LEFT, g.active == 0); self.room(frame, g.right, g.left, g.pos[1], ROX, RIGHT, g.active == 1)
        frame[12:52, 31:33] = WHITE
        for i in range(min(10, g.budget_left)): frame[4:7, 3 + i * 6:7 + i * 6] = LEFT if i % 2 == 0 else RIGHT
        if g.failed: frame[57:61, 25:39] = HAZARD
        return frame


class Q061(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.left = self.right = []; self.pos = [(0, 0), (0, 0)]; self.goals = [(0, 0), (0, 0)]; self.active = self.budget_left = 0; self.switches = [False, False]; self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q061", levels, Camera(0, 0, 64, 64, BG_LEFT, BG_LEFT, [self.display]), False, len(levels), [1, 2, 3, 4, 5])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.left, self.right = list(s["left"]), list(s["right"]); self.pos = []; self.goals = []; self.active = 0; self.switches = [False, False]; self.failed = False; self.budget_left = s["budget"]
        for grid in (self.left, self.right):
            start = goal = (0, 0)
            for y, row in enumerate(grid):
                for x, ch in enumerate(row):
                    if ch == "S": start = (x, y)
                    elif ch == "G": goal = (x, y)
            self.pos.append(start); self.goals.append(goal)
    def _move(self, aid):
        dx, dy = DIRS[aid]; i = self.active; grid = self.left if i == 0 else self.right; x, y = self.pos[i]; p = (x + dx, y + dy)
        if not (0 <= p[0] < 6 and 0 <= p[1] < 6): return
        ch = grid[p[1]][p[0]]
        if ch == "#" or ch == "x" or (ch == "d" and not self.switches[1 - i]): self.failed = True; self.lose(); return
        self.pos[i] = p
        if ch == "s": self.switches[i] = True
        if self.pos == self.goals: self.next_level()
    def step(self):
        aid = self.action.id.value; self.budget_left -= 1
        if aid in DIRS: self._move(aid)
        elif aid == 5: self.active = 1 - self.active
        if self.budget_left <= 0: self.lose()
        self.complete_action()
