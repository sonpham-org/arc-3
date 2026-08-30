"""q082 Borrowed Color -- preserve role identity while containers recolor every piece."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

BG, SHELF, ROLES, BORROWED, SOCKET, CURSOR, EVENT, BAD = 11, 10, [6, 9, 12, 14, 15, 7], [7, 12, 9, 6, 14, 15], 3, 0, 13, 8
LEVELS = [
    {"name": "One Borrowed Coat", "order": [1, 0], "events": [1], "budget": 5},
    {"name": "Container Colors", "order": [2, 0, 1], "events": [1, 2], "budget": 8},
    {"name": "Repeated Borrowing", "order": [3, 1, 0, 2], "events": [2, 1, 3], "budget": 13},
    {"name": "False Match", "order": [2, 4, 1, 3, 0], "events": [1, 3, 2], "budget": 24},
    {"name": "Color Carousel", "order": [5, 2, 4, 0, 3, 1], "events": [2, 4, 1, 3], "budget": 34},
    {"name": "Borrowed Color", "order": [3, 5, 1, 4, 0, 2], "events": [1, 5, 2, 4, 3], "budget": 34},
]


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG; frame[11:56, 4:60] = SHELF; n = len(g.order); gap = 48 // n
        for i, identity in enumerate(g.order):
            x = 9 + i * gap; color = ROLES[identity] if g.event_index == 0 else BORROWED[(identity + sum(g.events[:g.event_index])) % n]; frame[22:38, x:x + 7] = color; frame[26:34, x + 2:x + 5] = SHELF
            frame[43:51, x:x + 7] = SOCKET; frame[45:49, x + 2:x + 5] = ROLES[i]
            if i == g.cursor: frame[38:41, x - 1:x + 8] = CURSOR
        for i in range(len(g.events)): frame[4:7, 8 + i * 9:14 + i * 9] = EVENT if i >= g.event_index else SOCKET
        if g.failed: frame[59:63, 25:39] = BAD
        return frame


class Q082(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.order = []; self.events = []; self.event_index = self.cursor = self.budget_left = 0; self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q082", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [1, 3, 4, 5, 6])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.order = list(s["order"]); self.events = list(s["events"]); self.event_index = self.cursor = 0; self.budget_left = s["budget"]; self.failed = False
    def step(self):
        action = self.action.id.value
        if action == 0: self.complete_action(); return
        self.budget_left -= 1; n = len(self.order)
        if action == 1 and self.event_index < len(self.events): self.event_index += 1
        elif self.event_index < len(self.events): self.failed = True; self.lose()
        elif action == 3: self.cursor = (self.cursor - 1) % (n - 1)
        elif action == 4: self.cursor = (self.cursor + 1) % (n - 1)
        elif action == 5: self.order[self.cursor], self.order[self.cursor + 1] = self.order[self.cursor + 1], self.order[self.cursor]
        elif action == 6:
            if self.order == list(range(n)): self.next_level()
            else: self.failed = True; self.lose()
        else: self.failed = True; self.lose()
        if self.budget_left <= 0: self.failed = True; self.lose()
        self.complete_action()
