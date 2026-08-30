"""q041 Keyhole Budget -- spend scarce observations before navigating a hidden route."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

CELL, OX, OY = 6, 8, 8
BG, UNKNOWN, FLOOR, WALL, PLAYER, GOAL, REVEAL, FRAGILE, KEY, DOOR, BAD = 5, 4, 3, 2, 10, 14, 9, 12, 11, 6, 8
DIRS = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}
LEVELS = [
    {"name": "First Glimpse", "map": ["########", "#S....G#", "########", "########", "########", "########", "########", "########"], "looks": 2, "steps": 8},
    {"name": "Forked Dark", "map": ["########", "#S..#..#", "###.#.G#", "#.....##", "########", "########", "########", "########"], "looks": 4, "steps": 14},
    {"name": "Held Aperture", "map": ["########", "#S...###", "###..###", "##...G##", "########", "########", "########", "########"], "looks": 3, "steps": 14},
    {"name": "Hidden Latch", "map": ["########", "#S.k####", "###.####", "##..d.G#", "########", "########", "########", "########"], "looks": 4, "steps": 16},
    {"name": "Vanishing Floor", "map": ["########", "#S!!...#", "####.#G#", "#....###", "########", "########", "########", "########"], "looks": 4, "steps": 16},
    {"name": "Keyhole Budget", "map": ["########", "#S..#k##", "##!.#.##", "#..!...#", "#.###d.#", "#.....G#", "########", "########"], "looks": 6, "steps": 28},
]


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    @staticmethod
    def fill(frame, c, color, inset=0):
        x, y = c; px, py = OX + x * CELL, OY + y * CELL; frame[py + inset:py + CELL - inset, px + inset:px + CELL - inset] = color
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG
        for y in range(8):
            for x in range(8):
                c = (x, y); ch = g.grid[y][x]
                if c not in g.revealed and c not in (g.pos, g.goal): self.fill(frame, c, UNKNOWN); continue
                color = WALL if ch == "#" else FLOOR; self.fill(frame, c, color)
                if ch == "!" and c not in g.collapsed: self.fill(frame, c, FRAGILE, 2)
                elif ch == "k" and not g.has_key: self.fill(frame, c, KEY, 2)
                elif ch == "d": self.fill(frame, c, DOOR if not g.has_key else FLOOR, 1)
        self.fill(frame, g.goal, GOAL, 1); self.fill(frame, g.goal, BG, 2)
        self.fill(frame, g.pos, PLAYER, 1); self.fill(frame, g.pos, REVEAL, 2)
        for i in range(g.looks_left): frame[59:62, 8 + i * 8:13 + i * 8] = REVEAL
        for i in range(min(8, g.steps_left)): frame[3:5, 8 + i * 6:12 + i * 6] = PLAYER
        if g.failed: frame[1:4, 27:37] = BAD
        return frame


class Q041(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.grid = []; self.pos = self.goal = (0, 0); self.revealed = set(); self.collapsed = set(); self.looks_left = self.steps_left = 0; self.has_key = self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q041", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [1, 2, 3, 4, 5, 6])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.grid = list(s["map"]); self.revealed = set(); self.collapsed = set(); self.has_key = self.failed = False
        for y, row in enumerate(self.grid):
            for x, ch in enumerate(row):
                if ch == "S": self.pos = (x, y)
                elif ch == "G": self.goal = (x, y)
        self.looks_left, self.steps_left = s["looks"], s["steps"]; self._reveal(self.pos, free=True)
    @staticmethod
    def _cell(x, y):
        if OX <= x < OX + 48 and OY <= y < OY + 48: return ((x - OX) // CELL, (y - OY) // CELL)
        return None
    def _reveal(self, center, free=False):
        if center is None or (not free and self.looks_left <= 0): return
        if not free: self.looks_left -= 1
        cx, cy = center
        for y in range(max(0, cy - 1), min(8, cy + 2)):
            for x in range(max(0, cx - 1), min(8, cx + 2)): self.revealed.add((x, y))
    def _move(self, aid):
        dx, dy = DIRS[aid]; old = self.pos; p = (old[0] + dx, old[1] + dy); self.steps_left -= 1
        if not (0 <= p[0] < 8 and 0 <= p[1] < 8) or p not in self.revealed: self.failed = True; self.lose(); return
        ch = self.grid[p[1]][p[0]]
        if ch == "#" or p in self.collapsed or (ch == "d" and not self.has_key): self.failed = True; self.lose(); return
        self.pos = p
        if self.grid[old[1]][old[0]] == "!": self.collapsed.add(old)
        if ch == "k": self.has_key = True
        if self.pos == self.goal: self.next_level()
    def step(self):
        aid = self.action.id.value
        if aid in DIRS: self._move(aid)
        elif aid == 6: self._reveal(self._cell(int(self.action.data.get("x", 0)), int(self.action.data.get("y", 0))))
        if self.steps_left <= 0 and self.pos != self.goal: self.lose()
        self.complete_action()
