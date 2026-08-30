"""q031 Split Vessel -- discover and compose quantity-conserving machines."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

BG, GLASS, EMPTY, LIQUID, TARGET, ACTIVE, PIPE, BAD = 5, 9, 4, 10, 14, 11, 2, 8
LEVELS = [
    {"name": "Equal Glass", "start": [4, 0], "target": [2, 2], "ops": ["half01"], "budget": 3},
    {"name": "Third Cup", "start": [6, 0, 0], "target": [3, 2, 1], "ops": ["half01", "pour12"], "budget": 5},
    {"name": "Measured Cascade", "start": [5, 1, 0], "target": [3, 2, 1], "ops": ["pour01", "pour12", "rotate"], "budget": 7},
    {"name": "Turntable", "start": [8, 0, 0], "target": [2, 4, 2], "ops": ["half01", "half12", "rotate"], "budget": 6},
    {"name": "Long Division", "start": [7, 1, 0, 0], "target": [4, 2, 1, 1], "ops": ["balance01", "half12", "half23", "rotate"], "budget": 7},
    {"name": "Conservation Bench", "start": [9, 0, 0, 0], "target": [6, 1, 1, 1], "ops": ["pour01", "pour12", "pour23", "balance01", "rotate"], "budget": 10},
]


def apply_op(values, op):
    v = list(values)
    if op.startswith("pour"):
        a, b = map(int, op[-2:])
        if v[a] > 0: v[a] -= 1; v[b] += 1
    elif op.startswith("half"):
        a, b = map(int, op[-2:])
        if v[a] > 0 and v[a] % 2 == 0 and v[b] == 0:
            v[b] = v[a] // 2; v[a] //= 2
    elif op.startswith("balance"):
        a, b = map(int, op[-2:]); total = v[a] + v[b]
        v[a] = (total + 1) // 2; v[b] = total // 2
    elif op == "rotate": v = [v[-1]] + v[:-1]
    return tuple(v)


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG; n = len(g.values); width = 10; gap = 3; left = (64 - (n * width + (n - 1) * gap)) // 2
        for i, (value, wanted) in enumerate(zip(g.values, g.target)):
            x = left + i * (width + gap); frame[12:48, x:x + width] = GLASS; frame[15:45, x + 2:x + width - 2] = EMPTY
            h = min(28, value * 3); frame[45 - h:45, x + 2:x + width - 2] = LIQUID
            th = min(28, wanted * 3); frame[44 - th:46 - th, x + 1:x + width - 1] = TARGET
        # Machines are abstract pipe glyphs; selection is a warm glow.
        mleft = max(2, (64 - len(g.ops) * 11) // 2)
        for i, op in enumerate(g.ops):
            x = mleft + i * 11; c = ACTIVE if i == g.cursor else PIPE
            frame[52:59, x:x + 9] = c; frame[54:57, x + 2:x + 7] = BG
            if "half" in op: frame[50:53, x + 3:x + 6] = c
            elif "balance" in op: frame[50:52, x + 1:x + 8] = c
            elif op == "rotate": frame[50:53, x + 1:x + 3] = c; frame[50:53, x + 6:x + 8] = c
        for i in range(g.budget_left): frame[3:6, 4 + i * 6:8 + i * 6] = ACTIVE
        if g.failed: frame[7:10, 25:39] = BAD
        return frame


class Q031(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.values = self.target = (); self.ops = []; self.cursor = self.budget_left = 0; self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q031", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [1, 2, 3, 4, 5, 6])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.values = tuple(s["start"]); self.target = tuple(s["target"]); self.ops = list(s["ops"]); self.cursor = 0; self.budget_left = s["budget"]; self.failed = False
    def step(self):
        aid = self.action.id.value
        if aid in (1, 3): self.cursor = (self.cursor - 1) % len(self.ops)
        elif aid in (2, 4): self.cursor = (self.cursor + 1) % len(self.ops)
        elif aid == 5 and self.budget_left:
            before = sum(self.values); self.values = apply_op(self.values, self.ops[self.cursor]); assert sum(self.values) == before; self.budget_left -= 1
        elif aid == 6:
            if self.values == self.target: self.next_level()
            else: self.failed = True; self.lose()
        if self.budget_left <= 0 and self.values != self.target: self.lose()
        self.complete_action()
