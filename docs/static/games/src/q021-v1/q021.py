"""q021 Switchboard Diagnosis -- infer a hidden XOR wiring graph by intervention."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

BG, PANEL, WIRE, LEVER, ON, OFF, TARGET, BAD, WHITE = 4, 3, 2, 12, 11, 5, 9, 8, 0
LEVELS = [
    {"name": "One Wire", "masks": [0b1], "initial": 0, "target": 0b1, "tests": 2},
    {"name": "Separate Wires", "masks": [0b01, 0b10], "initial": 0, "target": 0b11, "tests": 3},
    {"name": "Shared Lamp", "masks": [0b11, 0b01], "initial": 0, "target": 0b10, "tests": 3},
    {"name": "Crossed Bank", "masks": [0b101, 0b110, 0b011], "initial": 0, "target": 0b110, "tests": 4},
    {"name": "Live Panel", "masks": [0b0011, 0b0110, 0b1100], "initial": 0b1111, "target": 0b0101, "tests": 4},
    {"name": "Diagnostic Gate", "masks": [0b1001, 0b0111, 0b1100, 0b1010], "initial": 0b0011, "target": 0b1110, "tests": 5},
]


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG; frame[7:57, 8:56] = PANEL
        n = len(g.masks); spacing = 42 // max(1, n)
        for i in range(n):
            y = 12 + i * spacing; frame[y:y + 6, 14:21] = LEVER if i == g.cursor else WIRE
            frame[y + 1:y + 5, 18:25] = WHITE if i == g.cursor else LEVER
        for j in range(n):
            y = 12 + j * spacing; active = bool(g.lamps & (1 << j)); wanted = bool(g.target & (1 << j))
            frame[y:y + 7, 43:50] = TARGET if wanted else WIRE; frame[y + 2:y + 5, 45:48] = ON if active else OFF
        # Unknown wiring is represented only by broken traces, never by the true graph.
        for y in range(13, 53, 6): frame[y, 26:40:3] = WIRE
        for i in range(g.tests_left): frame[60:63, 10 + i * 7:15 + i * 7] = ON
        if g.failed_commit: frame[2:5, 27:37] = BAD
        return frame


class Q021(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.masks = []; self.cursor = self.lamps = self.target = self.tests_left = 0; self.failed_commit = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q021", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [1, 2, 3, 4, 5, 6])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.masks = list(s["masks"]); self.cursor = 0; self.lamps = s["initial"]; self.target = s["target"]; self.tests_left = s["tests"]; self.failed_commit = False
    def step(self):
        aid = self.action.id.value
        if aid in (1, 3): self.cursor = (self.cursor - 1) % len(self.masks)
        elif aid in (2, 4): self.cursor = (self.cursor + 1) % len(self.masks)
        elif aid == 5 and self.tests_left:
            self.lamps ^= self.masks[self.cursor]; self.tests_left -= 1
        elif aid == 6:
            if self.lamps == self.target: self.next_level()
            else: self.failed_commit = True; self.lose()
        if self.tests_left <= 0 and self.lamps != self.target: self.lose()
        self.complete_action()
