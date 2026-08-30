"""q081 Shell Identity -- track persistent identity through independent shell shuffles."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

BG, PLINTH, SHELLS, CORE, SOCKET, SELECT, SHUFFLE, BAD = 5, 3, [9, 11, 6, 12, 10, 14], [14, 10, 12, 9, 11, 6], 2, 0, 4, 8


def event(kind, a, b): return (kind, a, b)
LEVELS = [
    {"name": "One Exchange", "n": 3, "events": [event("pos", 0, 2)], "target": [0, 1, 2], "adjacent": False, "budget": 7},
    {"name": "False Colors", "n": 3, "events": [event("app", 0, 1), event("pos", 1, 2)], "target": [0, 1, 2], "adjacent": False, "budget": 9},
    {"name": "Two Motions", "n": 4, "events": [event("pos", 0, 3), event("app", 1, 2), event("pos", 0, 1)], "target": [0, 1, 2, 3], "adjacent": False, "budget": 12},
    {"name": "Neighbor Hands", "n": 4, "events": [event("pos", 0, 2), event("app", 0, 3), event("pos", 1, 3)], "target": [0, 1, 2, 3], "adjacent": True, "budget": 16},
    {"name": "Rotating Gallery", "n": 5, "events": [event("pos", 0, 4), event("app", 1, 3), event("pos", 1, 2), event("app", 0, 2)], "target": [0, 1, 2, 3, 4], "adjacent": True, "budget": 20},
    {"name": "Shell Identity", "n": 6, "events": [event("pos", 0, 5), event("app", 1, 4), event("pos", 2, 4), event("app", 0, 3), event("pos", 1, 3), event("app", 2, 5)], "target": [0, 1, 2, 3, 4, 5], "adjacent": True, "budget": 34},
]


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    @staticmethod
    def xpos(i, n): return 7 + i * (50 // max(1, n - 1)) if n > 1 else 32
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG; frame[42:48, 3:61] = PLINTH
        for i, body in enumerate(g.bodies):
            x = self.xpos(i, len(g.bodies)); shell = SHELLS[body["appearance"]]
            frame[24:41, x - 5:x + 6] = shell; frame[20:25, x - 3:x + 4] = shell
            frame[29:36, x - 3:x + 4] = BG
            if g.event_index == 0: frame[31:34, x - 2:x + 3] = CORE[body["identity"]]
            if g.selected == i: frame[17:20, x - 4:x + 5] = SELECT
            frame[50:57, x - 5:x + 6] = SOCKET; frame[52:55, x - 2:x + 3] = CORE[g.target[i]]
        for i in range(len(g.events)):
            frame[5:9, 8 + i * 8:13 + i * 8] = SHUFFLE if i >= g.event_index else SELECT
        if g.failed: frame[60:63, 25:39] = BAD
        return frame


class Q081(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.bodies = []; self.events = []; self.target = []; self.event_index = self.selected = None; self.adjacent = False; self.budget_left = 0; self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q081", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [5, 6])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.bodies = [{"identity": i, "appearance": i} for i in range(s["n"])]; self.events = list(s["events"]); self.target = list(s["target"]); self.event_index = 0; self.selected = None; self.adjacent = s["adjacent"]; self.budget_left = s["budget"]; self.failed = False
    @staticmethod
    def _slot(x, n):
        positions = [Display.xpos(i, n) for i in range(n)]; return min(range(n), key=lambda i: abs(x - positions[i])) if 2 <= x <= 62 else None
    def _advance(self):
        if self.event_index >= len(self.events): return
        kind, a, b = self.events[self.event_index]
        if kind == "pos": self.bodies[a], self.bodies[b] = self.bodies[b], self.bodies[a]
        else: self.bodies[a]["appearance"], self.bodies[b]["appearance"] = self.bodies[b]["appearance"], self.bodies[a]["appearance"]
        self.event_index += 1
    def _click(self, x):
        if self.event_index < len(self.events): return False
        i = self._slot(x, len(self.bodies))
        if i is None: return False
        if self.selected is None: self.selected = i; return False
        j = self.selected; self.selected = None
        if i != j and (not self.adjacent or abs(i - j) == 1): self.bodies[i], self.bodies[j] = self.bodies[j], self.bodies[i]
        if [b["identity"] for b in self.bodies] == self.target:
            self.next_level()
            return True
        return False
    def step(self):
        aid = self.action.id.value; self.budget_left -= 1
        completed = False
        if aid == 5: self._advance()
        elif aid == 6: completed = self._click(int(self.action.data.get("x", 0)))
        if self.budget_left <= 0 and not completed: self.failed = True; self.lose()
        self.complete_action()
