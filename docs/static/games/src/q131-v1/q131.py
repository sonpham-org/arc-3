"""q131 Pulse Language -- compose grounded short, long, and separator pulses."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

BG, PAPER, SHORT, LONG, GAP, OBJECT, DIRECTION, BAD = 9, 0, 11, 7, 3, 14, 12, 8
LEVELS = [
    {"name": "One Short", "expected": [1], "object": 14, "direction": 4},
    {"name": "Long Reply", "expected": [2, 1], "object": 12, "direction": 1},
    {"name": "Two Words", "expected": [1, 3, 2], "object": 9, "direction": 3},
    {"name": "Ordered Phrase", "expected": [2, 1, 3, 1], "object": 6, "direction": 2},
    {"name": "Nested Command", "expected": [1, 2, 3, 2, 1], "object": 15, "direction": 4},
    {"name": "Pulse Language", "expected": [2, 1, 3, 1, 1, 3, 2], "object": 10, "direction": 1},
]


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG; frame[7:57, 5:59] = PAPER
        frame[13:25, 10:22] = g.object; frame[16:22, 13:19] = OBJECT
        dx, dy = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}[g.direction]; frame[18 + dy * 8:22 + dy * 8, 39 + dx * 8:43 + dx * 8] = DIRECTION; frame[18:22, 39:43] = DIRECTION
        for i, pulse in enumerate(g.buffer):
            x = 10 + i * 7
            if pulse == 1: frame[42:47, x:x + 3] = SHORT
            elif pulse == 2: frame[36:49, x:x + 3] = LONG
            else: frame[39:45, x:x + 2] = GAP
        for i in range(len(g.expected)): frame[52:55, 9 + i * 7:13 + i * 7] = GAP
        if g.failed: frame[2:5, 25:39] = BAD
        return frame


class Q131(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.expected = []; self.buffer = []; self.object = self.direction = 0; self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q131", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [1, 2, 3, 4, 5])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.expected = list(s["expected"]); self.buffer = []; self.object = s["object"]; self.direction = s["direction"]; self.failed = False
    def step(self):
        action = self.action.id.value
        if action == 0: self.complete_action(); return
        if action in (1, 2, 3) and len(self.buffer) < len(self.expected): self.buffer.append(action)
        elif action == 4 and self.buffer: self.buffer.pop()
        elif action == 5:
            if self.buffer == self.expected: self.next_level()
            else: self.failed = True; self.lose()
        self.complete_action()
