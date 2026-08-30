"""q191 Event Compression -- act on causal event boundaries, not raw frames."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

BG, SCREEN, TRACK, ACTOR, EVENT, CAPTURE, BAD = 8, 4, 1, 15, 14, 11, 13
LEVELS = [
    {"name": "One Boundary", "period": 5, "events": [2], "reverse": False, "budget": 6},
    {"name": "Two Boundaries", "period": 6, "events": [1, 4], "reverse": False, "budget": 10},
    {"name": "Uneven Cycle", "period": 8, "events": [3, 6], "reverse": False, "budget": 12},
    {"name": "Reversed Routine", "period": 7, "events": [2, 5], "reverse": True, "budget": 14},
    {"name": "Nested Events", "period": 10, "events": [2, 7, 4], "reverse": True, "budget": 24},
    {"name": "Event Compression", "period": 12, "events": [3, 9, 5, 1], "reverse": True, "budget": 34},
]


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG; frame[8:54, 5:59] = SCREEN
        x = 10 + round(44 * g.phase / max(1, g.period - 1)); frame[22:38, x - 4:x + 5] = ACTOR
        if g.event_index < len(g.events) and g.phase == g.events[g.event_index]: frame[18:42, x - 2:x + 3] = EVENT
        for i in range(g.period):
            color = TRACK
            if i == g.phase: color = ACTOR
            frame[46:50, 8 + i * 4:11 + i * 4] = color
        for i in range(len(g.events)): frame[4:7, 7 + i * 10:13 + i * 10] = CAPTURE if i < g.event_index else TRACK
        if g.direction < 0: frame[57:61, 4:18] = ACTOR
        if g.failed: frame[57:61, 24:40] = BAD
        return frame


class Q191(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.events = []; self.period = self.phase = self.event_index = self.direction = self.budget_left = 0; self.reverse = self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q191", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [5, 6])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.period = s["period"]; self.events = list(s["events"]); self.reverse = s["reverse"]; self.phase = self.event_index = 0; self.direction = 1; self.budget_left = s["budget"]; self.failed = False
    def step(self):
        action = self.action.id.value; self.budget_left -= 1
        if action == 0: self.budget_left += 1; self.complete_action(); return
        if action == 6:
            if self.phase != self.events[self.event_index]: self.failed = True; self.lose(); self.complete_action(); return
            self.event_index += 1
            if self.event_index == len(self.events): self.next_level(); self.complete_action(); return
            if self.reverse: self.direction *= -1
        self.phase = (self.phase + self.direction) % self.period
        if self.budget_left <= 0: self.failed = True; self.lose()
        self.complete_action()
