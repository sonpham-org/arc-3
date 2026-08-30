"""q111 Silent Tutor -- transfer a demonstrated policy through visible frame changes."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

BG, STAGE, TUTOR, STUDENT, DONE, CUE, BAD = 11, 13, 7, 9, 14, 0, 8
DIRS = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}
LEVELS = [
    {"name": "Copy the Gesture", "demo": [4, 4], "rotation": 0, "mirror": False},
    {"name": "Turned Stage", "demo": [1, 4, 4], "rotation": 1, "mirror": False},
    {"name": "Mirror Lesson", "demo": [3, 1, 4], "rotation": 0, "mirror": True},
    {"name": "Rotated Routine", "demo": [1, 1, 4, 2], "rotation": 2, "mirror": False},
    {"name": "Mirrored Turn", "demo": [4, 1, 3, 3, 2], "rotation": 1, "mirror": True},
    {"name": "Silent Tutor", "demo": [1, 4, 2, 4, 1, 3], "rotation": 3, "mirror": True},
]


def transform(action, rotation, mirror):
    dx, dy = DIRS[action]
    if mirror: dx = -dx
    for _ in range(rotation % 4): dx, dy = -dy, dx
    return next(a for a, vector in DIRS.items() if vector == (dx, dy))


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    @staticmethod
    def arrow(frame, action, x, y, color):
        frame[y - 2:y + 3, x - 2:x + 3] = STAGE; dx, dy = DIRS[action]; frame[y - 1:y + 2, x - 1:x + 2] = color; frame[y + dy * 3 - 1:y + dy * 3 + 2, x + dx * 3 - 1:x + dx * 3 + 2] = color
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG; frame[8:29, 3:61] = STAGE; frame[35:57, 3:61] = STAGE
        for i, action in enumerate(g.demo): self.arrow(frame, action, 9 + i * 9, 19, TUTOR)
        for i, action in enumerate(g.expected): self.arrow(frame, action, 9 + i * 9, 46, DONE if i < g.progress else STUDENT)
        frame[31:34, 27:37] = CUE
        if g.mirror: frame[2:6, 3:13] = TUTOR
        for i in range(g.rotation): frame[2:6, 17 + i * 8:22 + i * 8] = STUDENT
        if g.failed: frame[59:63, 24:40] = BAD
        return frame


class Q111(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.demo = []; self.expected = []; self.progress = self.rotation = 0; self.mirror = self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q111", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [1, 2, 3, 4])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.demo = list(s["demo"]); self.rotation = s["rotation"]; self.mirror = s["mirror"]; self.expected = [transform(a, self.rotation, self.mirror) for a in self.demo]; self.progress = 0; self.failed = False
    def step(self):
        if self.action.id.value == 0: self.complete_action(); return
        if self.action.id.value != self.expected[self.progress]: self.failed = True; self.lose()
        else:
            self.progress += 1
            if self.progress == len(self.expected): self.next_level()
        self.complete_action()
