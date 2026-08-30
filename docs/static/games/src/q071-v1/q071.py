"""q071 Season Shift -- revise terrain rules at visible environmental change points."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

CELL, OX, OY = 6, 8, 9
BG, FLOOR, WALL, PLAYER, GOAL, WARM, COLD, CHANGE, FRAGILE, DEAD, WHITE = 14, 1, 13, 12, 0, 11, 9, 15, 10, 3, 0
DIRS = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}
LEVELS = [
    {"name": "Green Season", "map": ["########", "#SaaaG##", "########", "########", "########", "########", "########", "########"], "period": 6, "budget": 10},
    {"name": "Cold Crossing", "map": ["########", "#SbbbG##", "########", "########", "########", "########", "########", "########"], "period": 2, "budget": 12},
    {"name": "Alternating Beds", "map": ["########", "#Saab###", "###bG###", "########", "########", "########", "########", "########"], "period": 2, "budget": 16},
    {"name": "Changed Climate", "map": ["########", "#SaaM###", "###abG##", "########", "########", "########", "########", "########"], "period": 3, "budget": 18},
    {"name": "No Return", "map": ["########", "#S!!a###", "###baG##", "########", "########", "########", "########", "########"], "period": 2, "budget": 18},
    {"name": "Season Shift", "map": ["########", "#Sa!b###", "#b#bM###", "#a!abG##", "########", "########", "########", "########"], "period": 2, "budget": 28},
]


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    @staticmethod
    def fill(frame, c, color, inset=0):
        x, y = c; px, py = OX + x * CELL, OY + y * CELL; frame[py + inset:py + CELL - inset, px + inset:px + CELL - inset] = color
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG
        for y, row in enumerate(g.grid):
            for x, ch in enumerate(row):
                c = (x, y); color = WALL if ch == "#" else FLOOR; self.fill(frame, c, color)
                if ch == "a": self.fill(frame, c, WARM if g._open("a") else DEAD, 1)
                elif ch == "b": self.fill(frame, c, COLD if g._open("b") else DEAD, 1)
                elif ch == "M": self.fill(frame, c, CHANGE, 1); self.fill(frame, c, WHITE, 2)
                elif ch == "!" and c not in g.collapsed: self.fill(frame, c, FRAGILE, 1)
        self.fill(frame, g.goal, GOAL, 1); self.fill(frame, g.goal, BG, 2)
        self.fill(frame, g.pos, PLAYER, 1); self.fill(frame, g.pos, WHITE, 2)
        phase_color = COLD if g.phase else WARM
        frame[2:6, 4:60] = DEAD; frame[2:6, 4:4 + int(56 * g.until_shift / g.period)] = phase_color
        if g.reversed: frame[59:62, 22:42] = CHANGE
        return frame


class Q071(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.grid = []; self.pos = self.goal = (0, 0); self.phase = self.until_shift = self.period = self.budget_left = 0; self.reversed = False; self.collapsed = set()
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q071", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [1, 2, 3, 4, 5])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.grid = list(s["map"]); self.phase = 0; self.period = self.until_shift = s["period"]; self.budget_left = s["budget"]; self.reversed = False; self.collapsed = set()
        for y, row in enumerate(self.grid):
            for x, ch in enumerate(row):
                if ch == "S": self.pos = (x, y)
                elif ch == "G": self.goal = (x, y)
    def _open(self, ch): return (ch == "a") == (self.phase == (1 if self.reversed else 0))
    def _tick(self):
        self.until_shift -= 1
        if self.until_shift <= 0: self.phase = 1 - self.phase; self.until_shift = self.period
    def _move(self, aid):
        dx, dy = DIRS[aid]; old = self.pos; p = (old[0] + dx, old[1] + dy)
        if 0 <= p[0] < 8 and 0 <= p[1] < 8:
            ch = self.grid[p[1]][p[0]]
            if ch != "#" and p not in self.collapsed and (ch not in "ab" or self._open(ch)):
                self.pos = p
                if self.grid[old[1]][old[0]] == "!": self.collapsed.add(old)
                if ch == "M": self.reversed = not self.reversed
                if p == self.goal:
                    self.next_level()
                    return True
        return False
    def step(self):
        aid = self.action.id.value; self.budget_left -= 1
        completed = self._move(aid) if aid in DIRS else False
        if completed:
            pass
        elif self.budget_left > 0:
            self._tick()
        else:
            self.lose()
        self.complete_action()
