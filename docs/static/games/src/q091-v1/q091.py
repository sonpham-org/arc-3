"""q091 Workshop Orders -- infer a dependency tree of reusable subassemblies."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

BG, BENCH, SLOT, COLORS, SELECT, TOOL, TARGET, BAD = 6, 1, 13, [11, 7, 9, 10, 12, 14], 5, 3, 8, 8


def recipe(a, b, out, tool=0): return (a, b, out, tool)
LEVELS = [
    {"name": "First Joint", "parts": [1, 2], "tools": [], "target": 3, "recipes": [recipe(1, 2, 3)], "budget": 6},
    {"name": "Ordered Assembly", "parts": [1, 2, 4], "tools": [], "target": 7, "recipes": [recipe(1, 2, 3), recipe(3, 4, 7)], "budget": 9},
    {"name": "Parallel Modules", "parts": [1, 2, 4, 8], "tools": [], "target": 15, "recipes": [recipe(1, 4, 5), recipe(2, 8, 10), recipe(5, 10, 15)], "budget": 13},
    {"name": "Reusable Fixture", "parts": [1, 2, 4, 8], "tools": [16], "target": 15, "recipes": [recipe(1, 2, 3, 16), recipe(4, 8, 12, 16), recipe(3, 12, 15, 16)], "budget": 14},
    {"name": "Nested Orders", "parts": [1, 2, 4, 8, 16], "tools": [32], "target": 31, "recipes": [recipe(1, 8, 9), recipe(2, 16, 18), recipe(4, 9, 13, 32), recipe(13, 18, 31, 32)], "budget": 18},
    {"name": "Workshop Orders", "parts": [1, 2, 4, 8, 16, 32], "tools": [64, 128], "target": 63, "recipes": [recipe(1, 16, 17, 64), recipe(2, 8, 10, 128), recipe(4, 32, 36, 64), recipe(10, 17, 27, 128), recipe(27, 36, 63, 64)], "budget": 24},
]


def bits(mask): return [i for i in range(8) if mask & (1 << i)]


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    @staticmethod
    def xpos(i): return 8 + (i % 6) * 9
    def glyph(self, frame, mask, x, y, outline=SLOT):
        frame[y - 1:y + 9, x - 1:x + 8] = outline
        frame[y:y + 8, x:x + 7] = BG
        for bit in bits(mask):
            bx, by = bit % 3, bit // 3; frame[y + by * 3:y + by * 3 + 2, x + bx * 2:x + bx * 2 + 2] = COLORS[bit % len(COLORS)]
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG; frame[17:56, 3:61] = BENCH
        self.glyph(frame, g.target, 29, 4, TARGET)
        for i, mask in enumerate(g.parts):
            x, y = self.xpos(i), 24 + (i // 6) * 16; self.glyph(frame, mask, x, y, SELECT if i in g.selected else SLOT)
        for i, mask in enumerate(g.tools): self.glyph(frame, mask, 8 + i * 10, 58, TOOL)
        # The press itself is an abstract jaw. It exposes success/failure through motion.
        frame[43:48, 25:39] = SELECT; frame[48:52, 28:36] = SLOT
        for i in range(min(10, g.budget_left)): frame[12:15, 3 + i * 6:7 + i * 6] = TOOL
        if g.failed: frame[52:56, 27:37] = BAD
        return frame


class Q091(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.parts = []; self.tools = []; self.target = 0; self.recipes = []; self.selected = []; self.budget_left = 0; self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q091", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [5, 6])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.parts = list(s["parts"]); self.tools = list(s["tools"]); self.target = s["target"]; self.recipes = list(s["recipes"]); self.selected = []; self.budget_left = s["budget"]; self.failed = False
    def _index_at(self, x, y):
        candidates = [(abs(x - Display.xpos(i)) + abs(y - (24 + (i // 6) * 16)), i) for i in range(len(self.parts))]
        return min(candidates)[1] if candidates and min(candidates)[0] <= 9 else None
    def _click(self, x, y):
        i = self._index_at(x, y)
        if i is None: return
        if i in self.selected: self.selected.remove(i)
        elif len(self.selected) < 2: self.selected.append(i)
    def _combine(self):
        if len(self.selected) != 2: return
        i, j = sorted(self.selected); a, b = self.parts[i], self.parts[j]; self.selected = []
        for ra, rb, out, tool in self.recipes:
            if {a, b} == {ra, rb} and (not tool or tool in self.tools):
                self.parts.pop(j); self.parts.pop(i); self.parts.append(out); return
    def step(self):
        aid = self.action.id.value; self.budget_left -= 1
        if aid == 6: self._click(int(self.action.data.get("x", 0)), int(self.action.data.get("y", 0)))
        elif aid == 5:
            if self.target in self.parts: self.next_level()
            else: self._combine()
        if self.budget_left <= 0: self.failed = True; self.lose()
        self.complete_action()
