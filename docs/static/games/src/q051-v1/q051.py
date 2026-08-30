"""q051 Scaffold -- assemble load-bearing paths from finite struts."""

from __future__ import annotations
from copy import deepcopy
from math import hypot
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

BG, VOID, FAINT, THIN, THICK, NODE, LOAD, OK, BAD = 11, 9, 10, 0, 12, 5, 13, 14, 8


def spec(name, nodes, edges, source, sink, load, stock, budget):
    return {"name": name, "nodes": nodes, "edges": edges, "source": source, "sink": sink, "load": load, "stock": stock, "budget": budget}


LEVELS = [
    spec("First Span", [(8, 32), (32, 32), (56, 32)], [(0, 1), (1, 2)], 0, 2, 1, 3, 8),
    spec("Two Ways Across", [(7, 32), (31, 16), (31, 48), (57, 32)], [(0, 1), (1, 3), (0, 2), (2, 3)], 0, 3, 2, 4, 12),
    spec("Heavy Crossing", [(8, 38), (31, 23), (56, 38)], [(0, 1), (1, 2)], 0, 2, 2, 4, 8),
    spec("Braced Deck", [(6, 38), (24, 20), (24, 48), (42, 20), (42, 48), (58, 38)], [(0, 1), (0, 2), (1, 2), (1, 3), (2, 4), (3, 4), (3, 5), (4, 5)], 0, 5, 2, 8, 16),
    spec("False Anchorage", [(5, 34), (20, 14), (20, 50), (34, 32), (48, 14), (48, 50), (59, 34)], [(0, 1), (0, 2), (1, 3), (2, 3), (1, 4), (2, 5), (3, 4), (3, 5), (4, 6), (5, 6)], 0, 6, 2, 7, 18),
    spec("Scaffold", [(4, 34), (17, 14), (17, 34), (17, 54), (34, 14), (34, 34), (34, 54), (49, 14), (49, 34), (49, 54), (60, 34)], [(0, 1), (0, 2), (0, 3), (1, 2), (2, 3), (1, 4), (2, 5), (3, 6), (4, 5), (5, 6), (4, 7), (5, 8), (6, 9), (7, 8), (8, 9), (7, 10), (8, 10), (9, 10)], 0, 10, 3, 12, 26),
]


def line(frame, a, b, color, width=1):
    x0, y0 = a; x1, y1 = b; steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    for i in range(steps + 1):
        x = x0 + (x1 - x0) * i // steps; y = y0 + (y1 - y0) * i // steps
        frame[max(0, y - width + 1):min(64, y + width), max(0, x - width + 1):min(64, x + width)] = color


def max_flow(nodes, edges, active, source, sink):
    cap = {}
    for idx, (a, b) in enumerate(edges):
        c = active.get(idx, 0)
        if c: cap[(a, b)] = cap.get((a, b), 0) + c; cap[(b, a)] = cap.get((b, a), 0) + c
    flow = 0
    while True:
        parent = {source: None}; queue = [source]
        for u in queue:
            for v in range(len(nodes)):
                if v not in parent and cap.get((u, v), 0) > 0: parent[v] = u; queue.append(v)
        if sink not in parent: return flow
        v = sink
        while parent[v] is not None:
            u = parent[v]; cap[(u, v)] -= 1; cap[(v, u)] = cap.get((v, u), 0) + 1; v = u
        flow += 1


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG; frame[8:58, 2:62] = VOID
        for i, (a, b) in enumerate(g.edges):
            strength = g.active.get(i, 0); line(frame, g.nodes[a], g.nodes[b], THICK if strength == 2 else THIN if strength == 1 else FAINT, 2 if strength == 2 else 1)
        for i, (x, y) in enumerate(g.nodes):
            c = LOAD if i in (g.source, g.sink) else NODE; frame[y - 2:y + 3, x - 2:x + 3] = c; frame[y - 1:y + 2, x - 1:x + 2] = BG
        frame[2:6, 2:10] = THICK if g.material == 2 else THIN
        for i in range(g.stock_left): frame[60:63, 4 + i * 5:7 + i * 5] = THICK if g.material == 2 else THIN
        for i in range(g.load): frame[2:6, 50 + i * 4:53 + i * 4] = LOAD
        if g.failed: frame[28:36, 27:37] = BAD
        return frame


class Q051(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.nodes = []; self.edges = []; self.active = {}; self.source = self.sink = self.load = self.stock_left = self.budget = 0; self.material = 1; self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q051", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [1, 2, 3, 4, 5, 6])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.nodes = list(map(tuple, s["nodes"])); self.edges = list(map(tuple, s["edges"])); self.active = {}; self.source = s["source"]; self.sink = s["sink"]; self.load = s["load"]; self.stock_left = s["stock"]; self.budget = s["budget"]; self.material = 1; self.failed = False
    def _edge_at(self, x, y):
        best = None
        for i, (a, b) in enumerate(self.edges):
            ax, ay = self.nodes[a]; bx, by = self.nodes[b]; dx, dy = bx - ax, by - ay
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / max(1, dx * dx + dy * dy)))
            d = hypot(x - (ax + t * dx), y - (ay + t * dy))
            if best is None or d < best[0]: best = (d, i)
        return best[1] if best and best[0] <= 4 else None
    def _toggle(self, x, y):
        idx = self._edge_at(x, y)
        if idx is None: return
        if idx in self.active: self.stock_left += self.active.pop(idx)
        elif self.stock_left >= self.material: self.active[idx] = self.material; self.stock_left -= self.material
    def step(self):
        aid = self.action.id.value; self.budget -= 1
        if aid in (3, 4): self.material = 3 - self.material
        elif aid == 6: self._toggle(int(self.action.data.get("x", 0)), int(self.action.data.get("y", 0)))
        elif aid == 5:
            if max_flow(self.nodes, self.edges, self.active, self.source, self.sink) >= self.load: self.next_level()
            else: self.failed = True; self.lose()
        if self.budget <= 0: self.lose()
        self.complete_action()
