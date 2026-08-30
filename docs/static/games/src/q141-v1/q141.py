"""q141 Branch Ledger -- preserve counterfactual outcomes across sandbox resets."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

BG, PAGE, TAB, UNKNOWN, CURSOR, TARGET, INK, BAD = 1, 10, 7, 3, 11, 14, 15, 8
LEVELS = [
    {"name": "Two Futures", "outcomes": [9, 14], "target": 14, "probes": 2},
    {"name": "Saved Comparison", "outcomes": [12, 6, 9], "target": 6, "probes": 2},
    {"name": "Branch Ledger", "outcomes": [7, 11, 15, 10], "target": 15, "probes": 3},
    {"name": "Sparse Sandbox", "outcomes": [13, 9, 14, 12, 6], "target": 12, "probes": 4},
    {"name": "Late Alternative", "outcomes": [10, 7, 13, 9, 11], "target": 11, "probes": 5},
    {"name": "Irreversible Choice", "outcomes": [6, 12, 10, 15, 9, 14], "target": 14, "probes": 6},
]


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG; frame[6:58, 4:60] = PAGE
        frame[10:20, 27:37] = TARGET; frame[12:18, 29:35] = g.target
        n = len(g.outcomes); gap = 50 // n
        for i in range(n):
            x = 8 + i * gap; frame[26:34, x:x + 7] = CURSOR if i == g.cursor else TAB; frame[28:32, x + 2:x + 5] = UNKNOWN
            frame[41:49, x:x + 7] = TAB; frame[43:47, x + 2:x + 5] = g.ledger[i] if g.ledger[i] is not None else UNKNOWN
        for i in range(g.probes_left): frame[53:56, 8 + i * 7:13 + i * 7] = INK
        if g.failed: frame[2:5, 25:39] = BAD
        return frame


class Q141(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.outcomes = []; self.ledger = []; self.cursor = self.target = self.probes_left = 0; self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q141", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [3, 4, 5, 6])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.outcomes = list(s["outcomes"]); self.ledger = [None] * len(self.outcomes); self.cursor = 0; self.target = s["target"]; self.probes_left = s["probes"]; self.failed = False
    def step(self):
        action = self.action.id.value
        if action == 0: self.complete_action(); return
        if action == 3: self.cursor = (self.cursor - 1) % len(self.outcomes)
        elif action == 4: self.cursor = (self.cursor + 1) % len(self.outcomes)
        elif action == 5 and self.probes_left:
            self.ledger[self.cursor] = self.outcomes[self.cursor]; self.probes_left -= 1
        elif action == 6:
            if self.outcomes[self.cursor] == self.target: self.next_level()
            else: self.failed = True; self.lose()
        self.complete_action()
