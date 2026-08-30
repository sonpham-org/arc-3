"""q002 Afterimage Mill -- observation writes programs; occlusion executes them."""

from __future__ import annotations

from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

CELL, OX, OY, W, H = 6, 14, 15, 6, 6
BG, FIELD, GRID, BRONZE, GOLD, CYAN, PALE, RED, GREEN, INK = 13, 4, 12, 3, 11, 9, 10, 8, 14, 0
DIRS = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}


def mill(cell, start, target, facing=4):
    return {"cell": cell, "start": start, "target": target, "facing": facing}


LEVELS = [
    {"name": "First Impression", "mills": [mill((0, 0), (1, 1), (4, 1))], "walls": [], "turns": {}, "budget": 12},
    {"name": "Falling Memory", "mills": [mill((5, 5), (4, 4), (4, 1), 1)], "walls": [], "turns": {}, "budget": 12},
    {"name": "Corner Recall", "mills": [mill((0, 5), (1, 4), (4, 1))], "walls": [(2, 2), (3, 2), (4, 2)], "turns": {}, "budget": 24},
    {"name": "Separate Instructions", "mills": [mill((0, 0), (1, 1), (4, 1)), mill((5, 5), (4, 4), (1, 4), 3)], "walls": [], "turns": {}, "budget": 28},
    {"name": "Bent Echo", "mills": [mill((0, 5), (1, 4), (4, 1), 1)], "walls": [(2, 2), (3, 2)], "turns": {(1, 1): 1}, "budget": 18},
    {"name": "Mill Floor", "mills": [mill((0, 0), (1, 1), (4, 1), 4), mill((5, 0), (4, 3), (1, 3), 3), mill((5, 5), (1, 5), (4, 4), 4)], "walls": [(2, 2), (3, 2), (2, 4), (3, 4)], "turns": {(4, 5): -1}, "budget": 28},
]


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    @staticmethod
    def box(frame, cell, color, inset=0):
        x, y = cell; px, py = OX + x * CELL, OY + y * CELL
        frame[py + inset:py + CELL - inset, px + inset:px + CELL - inset] = color
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG
        frame[OY:OY + H * CELL, OX:OX + W * CELL] = FIELD
        frame[OY:OY + H * CELL:CELL, OX:OX + W * CELL] = GRID
        frame[OY:OY + H * CELL, OX:OX + W * CELL:CELL] = GRID
        for c in g.walls:
            self.box(frame, c, BRONZE); self.box(frame, c, RED, 2)
        for c, turn in g.turns.items():
            self.box(frame, c, CYAN, 1)
            x, y = c; px, py = OX + x * CELL, OY + y * CELL
            frame[py + 2:py + 4, px + (4 if turn > 0 else 1)] = PALE
        for m in g.mills:
            self.box(frame, m["target"], GREEN, 1); self.box(frame, m["target"], INK, 2)
            self.box(frame, m["cell"], GOLD if m["open"] else BRONZE, 1)
            x, y = m["cell"]; px, py = OX + x * CELL, OY + y * CELL
            dx, dy = DIRS[m["memory"]]
            frame[py + 2 + dy:py + 4 + dy, px + 2 + dx:px + 4 + dx] = PALE
            self.box(frame, m["pos"], CYAN, 1); self.box(frame, m["pos"], PALE, 2)
        # Six discrete budget rivets; industrial rather than a conventional bar.
        lit = max(0, min(6, (g.budget_left * 6 + max(1, g.budget_max) - 1) // max(1, g.budget_max)))
        for i in range(6): frame[4:7, 16 + i * 6:19 + i * 6] = GOLD if i < lit else GRID
        return frame


class Q002(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.mills = []; self.walls = set(); self.turns = {}; self.budget_left = self.budget_max = 0
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q002", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [1, 2, 3, 4, 5, 6])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.walls = set(map(tuple, s["walls"])); self.turns = {tuple(k): v for k, v in s["turns"].items()}
        self.mills = []
        for a in s["mills"]:
            m = deepcopy(a); m["pos"] = tuple(m.pop("start")); m["target"] = tuple(m["target"]); m["cell"] = tuple(m["cell"]); m["memory"] = m.pop("facing"); m["open"] = True; self.mills.append(m)
        self.budget_left = self.budget_max = s["budget"]
    @staticmethod
    def _cell(x, y):
        if OX <= x < OX + W * CELL and OY <= y < OY + H * CELL: return ((x - OX) // CELL, (y - OY) // CELL)
        return None
    def _toggle(self, x, y):
        c = self._cell(x, y)
        for m in self.mills:
            if m["cell"] == c: m["open"] = not m["open"]
    def _pulse(self):
        occupied = {m["pos"] for m in self.mills}
        proposals = []
        for m in self.mills:
            if m["open"]: proposals.append(m["pos"]); continue
            dx, dy = DIRS[m["memory"]]; p = (m["pos"][0] + dx, m["pos"][1] + dy)
            if not (0 <= p[0] < W and 0 <= p[1] < H) or p in self.walls: p = m["pos"]
            proposals.append(p)
        counts = {p: proposals.count(p) for p in proposals}
        for m, p in zip(self.mills, proposals):
            if counts[p] == 1 and (p not in occupied or p == m["pos"]): m["pos"] = p
            if m["pos"] in self.turns:
                order = [1, 4, 2, 3]; i = order.index(m["memory"]); m["memory"] = order[(i + self.turns[m["pos"]]) % 4]
    def step(self):
        aid = self.action.id.value
        if aid in DIRS:
            for m in self.mills:
                if m["open"]: m["memory"] = aid
        elif aid == 5: self._pulse()
        elif aid == 6: self._toggle(int(self.action.data.get("x", 0)), int(self.action.data.get("y", 0)))
        self.budget_left -= 1
        if all(m["pos"] == m["target"] for m in self.mills): self.next_level()
        elif self.budget_left <= 0: self.lose()
        self.complete_action()
