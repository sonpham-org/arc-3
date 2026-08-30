"""q012 Private Appetites -- infer stable preferences and allocate unique resources."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

BG, TABLE, AGENTS, ITEMS, SAMPLE, CURSOR, DONE, BAD = 10, 1, [6, 9, 12, 15, 7, 14], [14, 11, 9, 12, 6, 15], 3, 0, 13, 8
LEVELS = [
    {"name": "One Appetite", "prefs": [0], "shown": [0], "budget": 4},
    {"name": "Different Tastes", "prefs": [1, 0], "shown": [0, 1], "budget": 7},
    {"name": "Choice History", "prefs": [2, 0, 1], "shown": [0, 1, 2], "budget": 11},
    {"name": "Missing Demonstration", "prefs": [1, 3, 0, 2], "shown": [0, 1, 2], "budget": 15},
    {"name": "Fair Allocation", "prefs": [4, 1, 3, 0, 2], "shown": [0, 1, 3], "budget": 19},
    {"name": "Private Appetites", "prefs": [2, 5, 1, 4, 0, 3], "shown": [0, 2, 3, 5], "budget": 28},
]


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG; frame[9:56, 4:60] = TABLE; n = len(g.prefs); gap = 48 // n
        for i in range(n):
            x = 9 + i * gap; frame[17:31, x:x + 7] = DONE if i in g.assigned else AGENTS[i]
            if i in g.shown: frame[10:14, x + 1:x + 6] = ITEMS[g.prefs[i]]
            frame[39:49, x:x + 7] = ITEMS[i]
            if i == g.item_cursor: frame[50:53, x - 1:x + 8] = CURSOR
            if i == g.agent_cursor: frame[32:35, x - 1:x + 8] = SAMPLE
        if g.failed: frame[59:63, 25:39] = BAD
        return frame


class Q012(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.prefs = []; self.shown = set(); self.assigned = set(); self.used = set(); self.agent_cursor = self.item_cursor = self.budget_left = 0; self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q012", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [1, 2, 3, 4, 5])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.prefs = list(s["prefs"]); self.shown = set(s["shown"]); self.assigned = set(); self.used = set(); self.agent_cursor = self.item_cursor = 0; self.budget_left = s["budget"]; self.failed = False
    def step(self):
        action = self.action.id.value
        if action == 0: self.complete_action(); return
        self.budget_left -= 1; n = len(self.prefs)
        if action == 1: self.item_cursor = (self.item_cursor - 1) % n
        elif action == 2: self.item_cursor = (self.item_cursor + 1) % n
        elif action == 3: self.agent_cursor = (self.agent_cursor - 1) % n
        elif action == 4: self.agent_cursor = (self.agent_cursor + 1) % n
        elif action == 5:
            if self.agent_cursor in self.assigned or self.item_cursor in self.used or self.prefs[self.agent_cursor] != self.item_cursor: self.failed = True; self.lose()
            else: self.assigned.add(self.agent_cursor); self.used.add(self.item_cursor)
        else: self.failed = True; self.lose()
        if len(self.assigned) == n: self.next_level()
        elif self.budget_left <= 0: self.failed = True; self.lose()
        self.complete_action()
