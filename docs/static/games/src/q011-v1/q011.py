"""q011 Courtesy Lines -- infer stable yielding preferences by arranging encounters."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

BG, STREET, CURB = 10, 1, 11
AGENT = [9, 11, 6, 12, 10, 14]
SELECT, REVERSE, GOAL, BAD = 0, 8, 2, 8
RANK = {0: 2, 1: 0, 2: 4, 3: 1, 4: 5, 5: 3}
LEVELS = [
    {"name": "First Courtesy", "order": [1, 0], "reverse": [], "rotate": False, "budget": 5},
    {"name": "Three at the Crossing", "order": [1, 0, 2], "reverse": [], "rotate": False, "budget": 9},
    {"name": "Stable Preference", "order": [3, 0, 1, 2], "reverse": [], "rotate": False, "budget": 15},
    {"name": "Opposite Lane", "order": [0, 2, 3, 1], "reverse": [1], "rotate": False, "budget": 18},
    {"name": "Roundabout", "order": [4, 1, 3, 0, 2], "reverse": [2], "rotate": True, "budget": 24},
    {"name": "Courtesy Lines", "order": [1, 5, 3, 0, 2, 4], "reverse": [1, 3], "rotate": True, "budget": 34},
]


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    @staticmethod
    def xpos(i, n): return 7 + i * (50 // max(1, n - 1)) if n > 1 else 32
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG; frame[20:45, 2:62] = STREET; frame[18:20, 2:62] = CURB; frame[45:47, 2:62] = CURB
        n = len(g.order)
        for i, identity in enumerate(g.order):
            x = self.xpos(i, n); c = AGENT[identity]
            frame[27:42, x - 4:x + 5] = c; frame[23:29, x - 3:x + 4] = c
            # Silhouette—not just color—identifies each stable preference.
            if identity % 3 == 0: frame[21:24, x - 1:x + 2] = c
            elif identity % 3 == 1: frame[25:28, x - 6:x - 3] = c
            else: frame[25:28, x + 3:x + 6] = c
        for i in range(n - 1):
            x = (self.xpos(i, n) + self.xpos(i + 1, n)) // 2
            frame[47:52, x - 2:x + 3] = REVERSE if i in g.reverse else CURB
            if i == g.cursor: frame[52:56, x - 3:x + 4] = SELECT
        # Empty ordered bays communicate the terminal arrangement without naming ranks.
        for i, identity in enumerate(g.target):
            x = self.xpos(i, n); frame[7:14, x - 4:x + 5] = GOAL; frame[9:12, x - 2:x + 3] = AGENT[identity]
        for i in range(min(10, g.budget_left)): frame[60:63, 3 + i * 6:7 + i * 6] = CURB
        if g.failed: frame[2:5, 27:37] = BAD
        return frame


class Q011(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.order = self.target = []; self.reverse = set(); self.cursor = self.budget_left = 0; self.rotate_enabled = self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q011", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [1, 2, 3, 4, 5, 6])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.order = list(s["order"]); self.target = sorted(self.order, key=lambda x: RANK[x], reverse=True); self.reverse = set(s["reverse"]); self.cursor = 0; self.rotate_enabled = s["rotate"]; self.budget_left = s["budget"]; self.failed = False
    def _encounter(self):
        a, b = self.order[self.cursor:self.cursor + 2]; should_swap = RANK[a] < RANK[b]
        if self.cursor in self.reverse: should_swap = not should_swap
        if should_swap: self.order[self.cursor], self.order[self.cursor + 1] = b, a
        if self.order == self.target: self.next_level()
    def step(self):
        aid = self.action.id.value; self.budget_left -= 1; n = len(self.order)
        if aid in (1, 3): self.cursor = (self.cursor - 1) % (n - 1)
        elif aid in (2, 4): self.cursor = (self.cursor + 1) % (n - 1)
        elif aid == 5: self._encounter()
        elif aid == 6 and self.rotate_enabled: self.order = self.order[1:] + self.order[:1]
        if self.budget_left <= 0: self.failed = True; self.lose()
        self.complete_action()
