"""q151 Pipes to Roads -- transfer a solved route across visual embodiments."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

BG, WATER, DESERT, PIPE, ROAD, ROUTE, PLAYER, GOAL, BAD = 10, 9, 12, 0, 3, 11, 6, 14, 8


def level(name, edges, path, pipe, road): return {"name": name, "edges": edges, "path": path, "pipe": pipe, "road": road}
LEVELS = [
    level("Straight Translation", [(0, 1), (1, 2)], [0, 1, 2], [(8, 14), (32, 14), (56, 14)], [(8, 47), (34, 42), (56, 51)]),
    level("Diamond Detour", [(0, 1), (0, 2), (1, 3), (2, 3)], [0, 2, 3], [(8, 14), (31, 7), (31, 21), (56, 14)], [(8, 48), (31, 55), (31, 39), (56, 48)]),
    level("Branch Role", [(0, 1), (0, 2), (1, 3), (2, 3), (2, 4), (3, 4)], [0, 2, 4], [(7, 14), (25, 7), (25, 21), (43, 7), (57, 14)], [(7, 48), (25, 55), (25, 40), (43, 55), (57, 48)]),
    level("Bent Analogy", [(0, 1), (0, 2), (1, 3), (2, 4), (3, 5), (4, 5), (3, 4)], [0, 1, 3, 5], [(6, 14), (22, 6), (22, 22), (40, 6), (40, 22), (58, 14)], [(6, 48), (22, 56), (22, 39), (40, 56), (40, 39), (58, 48)]),
    level("Crossing Embodiments", [(0, 1), (0, 2), (1, 3), (2, 3), (2, 4), (3, 5), (4, 5)], [0, 2, 4, 5], [(5, 14), (20, 6), (20, 22), (38, 6), (38, 22), (58, 14)], [(5, 48), (22, 57), (18, 39), (40, 57), (43, 39), (58, 48)]),
    level("Pipes to Roads", [(0, 1), (0, 2), (1, 3), (2, 4), (3, 4), (3, 5), (4, 6), (5, 6)], [0, 1, 3, 5, 6], [(4, 14), (18, 6), (18, 22), (34, 6), (34, 22), (49, 6), (60, 14)], [(4, 48), (18, 56), (18, 39), (34, 56), (34, 39), (49, 56), (60, 48)]),
]


def draw_line(frame, a, b, color, width=1):
    x0, y0 = a; x1, y1 = b; steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    for i in range(steps + 1):
        x = round(x0 + (x1 - x0) * i / steps); y = round(y0 + (y1 - y0) * i / steps); frame[max(0, y - width):min(64, y + width + 1), max(0, x - width):min(64, x + width + 1)] = color


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG; frame[2:29, 2:62] = WATER; frame[34:62, 2:62] = DESERT
        route_edges = {frozenset(pair) for pair in zip(g.path, g.path[1:])}
        for a, b in g.edges: draw_line(frame, g.pipe[a], g.pipe[b], ROUTE if frozenset((a, b)) in route_edges else PIPE, 1)
        for a, b in g.edges: draw_line(frame, g.road[a], g.road[b], ROAD, 1)
        for i, (x, y) in enumerate(g.pipe): frame[y - 2:y + 3, x - 2:x + 3] = ROUTE if i in g.path else PIPE
        for i, (x, y) in enumerate(g.road): frame[y - 2:y + 3, x - 2:x + 3] = GOAL if i == g.path[-1] else ROAD
        x, y = g.road[g.path[g.progress]]; frame[y - 3:y + 4, x - 3:x + 4] = PLAYER
        if g.failed: frame[30:34, 25:39] = BAD
        return frame


class Q151(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.edges = []; self.path = []; self.pipe = []; self.road = []; self.progress = 0; self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q151", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [6])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.edges = list(s["edges"]); self.path = list(s["path"]); self.pipe = list(map(tuple, s["pipe"])); self.road = list(map(tuple, s["road"])); self.progress = 0; self.failed = False
    def step(self):
        if self.action.id.value == 0: self.complete_action(); return
        x, y = int(self.action.data.get("x", 0)), int(self.action.data.get("y", 0)); index = min(range(len(self.road)), key=lambda i: abs(x - self.road[i][0]) + abs(y - self.road[i][1]))
        if index != self.path[self.progress + 1]: self.failed = True; self.lose()
        else:
            self.progress += 1
            if self.progress == len(self.path) - 1: self.next_level()
        self.complete_action()
