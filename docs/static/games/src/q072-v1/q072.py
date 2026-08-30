"""q072 Honest Liar -- decode a guide whose visible state alternates truth and opposition."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

BG, PATH, GUIDE, HONEST, LIAR, PLAYER, DONE, BAD = 6, 1, 15, 14, 8, 9, 11, 13
DIRS = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}
OPPOSITE = {1: 2, 2: 1, 3: 4, 4: 3}
LEVELS = [
    {"name": "Honest Step", "route": [4, 4], "states": [1, 1]},
    {"name": "One Lie", "route": [1, 4, 4], "states": [1, 0, 1]},
    {"name": "Alternating Guide", "route": [1, 4, 2, 4], "states": [1, 0, 1, 0]},
    {"name": "Long Opposition", "route": [3, 1, 4, 2, 4], "states": [0, 0, 1, 0, 1]},
    {"name": "State Pattern", "route": [1, 1, 4, 2, 3, 4], "states": [0, 1, 0, 0, 1, 1]},
    {"name": "Honest Liar", "route": [4, 1, 3, 2, 4, 4, 1], "states": [1, 0, 0, 1, 0, 1, 0]},
]


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    @staticmethod
    def arrow(frame, action, x, y, color):
        dx, dy = DIRS[action]; frame[y - 2:y + 3, x - 2:x + 3] = color; frame[y + dy * 6 - 2:y + dy * 6 + 3, x + dx * 6 - 2:x + dx * 6 + 3] = color
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG; frame[8:55, 5:59] = PATH
        if g.index < len(g.route):
            honest = g.states[g.index]; signal = g.route[g.index] if honest else OPPOSITE[g.route[g.index]]; frame[12:22, 10:20] = HONEST if honest else LIAR; self.arrow(frame, signal, 42, 18, GUIDE)
        for i, action in enumerate(g.route):
            x = 9 + i * 7; frame[39:47, x:x + 5] = DONE if i < g.index else GUIDE
        frame[50:54, 8:56] = PLAYER
        if g.failed: frame[58:63, 24:40] = BAD
        return frame


class Q072(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.route = []; self.states = []; self.index = 0; self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q072", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [1, 2, 3, 4])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.route = list(s["route"]); self.states = list(s["states"]); self.index = 0; self.failed = False
    def step(self):
        action = self.action.id.value
        if action == 0: self.complete_action(); return
        if action != self.route[self.index]: self.failed = True; self.lose()
        else:
            self.index += 1
            if self.index == len(self.route): self.next_level()
        self.complete_action()
