"""q062 Relay Shadows -- align bodies using complementary shadow-only evidence."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

BG, SKY, GROUND, BODIES, SHADOW, CURSOR, SUN, GOAL, BAD = 12, 10, 1, [6, 9, 11, 14, 15, 7], 3, 0, 11, 13, 8
LEVELS = [
    {"name": "One Shadow Swap", "order": [1, 0], "light": 1, "budget": 4},
    {"name": "Three Silhouettes", "order": [2, 0, 1], "light": 1, "budget": 7},
    {"name": "Long Light", "order": [3, 1, 0, 2], "light": 2, "budget": 13},
    {"name": "Reverse Sun", "order": [2, 4, 1, 3, 0], "light": -1, "budget": 15},
    {"name": "Overlapping Shadows", "order": [5, 2, 4, 0, 3, 1], "light": 2, "budget": 33},
    {"name": "Relay Shadows", "order": [3, 5, 1, 4, 0, 2], "light": -2, "budget": 24},
]


def target(n, light): return tuple(sorted(range(n), key=lambda identity: ((identity * abs(light) + (1 if light < 0 else 0)) % n, identity)))


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG; frame[6:31, 3:61] = SKY; frame[35:59, 3:61] = GROUND; n = len(g.order); gap = 48 // n; frame[9:14, 5 if g.light > 0 else 54:10 if g.light > 0 else 59] = SUN
        for i, identity in enumerate(g.order):
            x = 9 + i * gap; h = 6 + identity * 2; frame[29 - h:29, x:x + 6] = BODIES[identity]
            length = 4 + ((identity * abs(g.light) + (1 if g.light < 0 else 0)) % n) * 3; frame[43:48, x:x + min(length, gap + 5)] = SHADOW
            if i == g.cursor: frame[31:34, x - 1:x + 7] = CURSOR
        wanted = target(n, g.light)
        for i, identity in enumerate(wanted):
            x = 9 + i * gap; frame[53:57, x:x + 6] = GOAL if identity == g.order[i] else SHADOW
        if g.failed: frame[60:63, 25:39] = BAD
        return frame


class Q062(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.order = []; self.light = self.cursor = self.budget_left = 0; self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q062", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [3, 4, 5, 6])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.order = list(s["order"]); self.light = s["light"]; self.cursor = 0; self.budget_left = s["budget"]; self.failed = False
    def step(self):
        action = self.action.id.value
        if action == 0: self.complete_action(); return
        self.budget_left -= 1; n = len(self.order)
        if action == 3: self.cursor = (self.cursor - 1) % (n - 1)
        elif action == 4: self.cursor = (self.cursor + 1) % (n - 1)
        elif action == 5: self.order[self.cursor], self.order[self.cursor + 1] = self.order[self.cursor + 1], self.order[self.cursor]
        elif action == 6:
            if tuple(self.order) == target(n, self.light): self.next_level()
            else: self.failed = True; self.lose()
        else: self.failed = True; self.lose()
        if self.budget_left <= 0: self.failed = True; self.lose()
        self.complete_action()
