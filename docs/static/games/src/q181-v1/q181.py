"""q181 Affordance Debt -- shortcuts create matching obstacles in a later room."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

CELL, OX, TOP, BOTTOM, W, H = 5, 14, 5, 35, 7, 5
BG, FIRST, FUTURE, WALL, PLAYER, GOAL, SHORTCUT, DEBT, BAD = 6, 14, 9, 3, 10, 0, 12, 8, 13
DIRS = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}
LEVELS = [
    {"name": "Tomorrow's Wall", "first": ["#######", "#S.a.G#", "#.....#", "#######", "#######"], "future": ["#######", "#S...G#", "#######", "#######", "#######"], "debts": {"a": [(3, 1)]}, "budget": 22},
    {"name": "Long Way Now", "first": ["#######", "#S.a.G#", "#..#..#", "#.....#", "#######"], "future": ["#######", "#S...G#", "#.###.#", "#.....#", "#######"], "debts": {"a": [(3, 1)]}, "budget": 28},
    {"name": "Twin Debts", "first": ["#######", "#S.abG#", "#.....#", "#######", "#######"], "future": ["#######", "#S...G#", "#######", "#######", "#######"], "debts": {"a": [(2, 1)], "b": [(4, 1)]}, "budget": 24},
    {"name": "Debt Shape", "first": ["#######", "#S.a.G#", "#.#.#.#", "#.....#", "#######"], "future": ["#######", "#S...G#", "#.#.#.#", "#.....#", "#######"], "debts": {"a": [(3, 1), (3, 3)]}, "budget": 32},
    {"name": "Choose the Scar", "first": ["#######", "#S.a.G#", "#..#..#", "#..b..#", "#######"], "future": ["#######", "#S...G#", "#.#.#.#", "#.....#", "#######"], "debts": {"a": [(3, 1)], "b": [(2, 3), (3, 3), (4, 3)]}, "budget": 34},
    {"name": "Affordance Debt", "first": ["#######", "#S.a..#", "#.#.#G#", "#..b..#", "#######"], "future": ["#######", "#S...G#", "#.#.#.#", "#.....#", "#######"], "debts": {"a": [(3, 1), (4, 1)], "b": [(2, 3), (3, 3), (4, 3)]}, "budget": 38},
]


def locate(grid, char):
    for y, row in enumerate(grid):
        for x, value in enumerate(row):
            if value == char: return x, y
    raise ValueError(char)


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    @staticmethod
    def draw_room(frame, grid, oy, field, debts, active, pos):
        frame[oy - 2:oy + H * CELL + 2, OX - 2:OX + W * CELL + 2] = 0 if active else field
        for y, row in enumerate(grid):
            for x, char in enumerate(row):
                px, py = OX + x * CELL, oy + y * CELL; color = WALL if char == "#" else field
                if (x, y) in debts: color = DEBT
                frame[py:py + CELL, px:px + CELL] = color
                if char in "abc": frame[py + 1:py + 4, px + 1:px + 4] = SHORTCUT
                elif char == "G": frame[py + 1:py + 4, px + 1:px + 4] = GOAL
        px, py = OX + pos[0] * CELL, oy + pos[1] * CELL; frame[py + 1:py + 4, px + 1:px + 4] = PLAYER
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG; top_pos = g.pos if g.phase == 0 else locate(g.first, "G"); bottom_pos = g.pos if g.phase == 1 else locate(g.future, "S")
        self.draw_room(frame, g.first, TOP, FIRST, set(), g.phase == 0, top_pos); self.draw_room(frame, g.future, BOTTOM, FUTURE, g.debt_cells, g.phase == 1, bottom_pos)
        for i in range(min(10, g.budget_left)): frame[62:64, 3 + i * 6:7 + i * 6] = PLAYER
        if g.failed: frame[31:34, 25:39] = BAD
        return frame


class Q181(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.first = self.future = []; self.debts = {}; self.debt_cells = set(); self.pos = (0, 0); self.phase = self.budget_left = 0; self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q181", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [1, 2, 3, 4])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.first = list(s["first"]); self.future = list(s["future"]); self.debts = {key: set(map(tuple, cells)) for key, cells in s["debts"].items()}; self.debt_cells = set(); self.phase = 0; self.pos = locate(self.first, "S"); self.budget_left = s["budget"]; self.failed = False
    def step(self):
        if self.action.id.value == 0: self.complete_action(); return
        if self.action.id.value not in DIRS: self.failed = True; self.lose(); self.complete_action(); return
        self.budget_left -= 1; dx, dy = DIRS[self.action.id.value]; nxt = (self.pos[0] + dx, self.pos[1] + dy); grid = self.first if self.phase == 0 else self.future
        if 0 <= nxt[0] < W and 0 <= nxt[1] < H and grid[nxt[1]][nxt[0]] != "#" and not (self.phase == 1 and nxt in self.debt_cells): self.pos = nxt
        if self.phase == 0 and grid[self.pos[1]][self.pos[0]] in self.debts: self.debt_cells |= self.debts[grid[self.pos[1]][self.pos[0]]]
        if self.pos == locate(grid, "G"):
            if self.phase == 0: self.phase = 1; self.pos = locate(self.future, "S")
            else: self.next_level()
        elif self.budget_left <= 0: self.failed = True; self.lose()
        self.complete_action()
