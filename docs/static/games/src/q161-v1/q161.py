"""q161 Wager Gate -- stop probing when physical evidence isolates a hypothesis."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

BG, TABLE, CARD, ALIVE, CURSOR, EVIDENCE, PRIZE, BAD = 13, 11, 1, 14, 9, 15, 7, 8
LEVELS = [
    {"name": "Certain Bet", "n": 2, "answer": 1, "clues": [0b10], "budget": 4},
    {"name": "Two Clues", "n": 3, "answer": 0, "clues": [0b011, 0b101], "budget": 7},
    {"name": "Narrowing Field", "n": 4, "answer": 2, "clues": [0b1110, 0b1101, 0b0110], "budget": 10},
    {"name": "Stop Early", "n": 5, "answer": 3, "clues": [0b11011, 0b01110, 0b11000, 0b01000], "budget": 13},
    {"name": "Weighted Table", "n": 6, "answer": 4, "clues": [0b111110, 0b110101, 0b011100, 0b110000, 0b010000], "budget": 16},
    {"name": "Wager Gate", "n": 6, "answer": 1, "clues": [0b101111, 0b011110, 0b100111, 0b001011, 0b000010], "budget": 18},
]


class Display(RenderableUserDisplay):
    def __init__(self, game): self.game = game
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game; frame[:, :] = BG; frame[8:57, 4:60] = TABLE; gap = 48 // g.n
        for i in range(g.n):
            x = 9 + i * gap; frame[18:37, x:x + 7] = CURSOR if i == g.cursor else CARD
            frame[21:34, x + 2:x + 5] = ALIVE if g.survivors & (1 << i) else BAD
        for i in range(g.clue_index): frame[43:48, 10 + i * 8:15 + i * 8] = EVIDENCE
        frame[2:6, 25:39] = PRIZE
        for i in range(min(10, g.budget_left)): frame[53:56, 5 + i * 6:9 + i * 6] = CARD
        if g.failed: frame[59:63, 25:39] = BAD
        return frame


class Q161(ARCBaseGame):
    def __init__(self):
        self.display = Display(self); self.n = self.answer = self.cursor = self.survivors = self.clue_index = self.budget_left = 0; self.clues = []; self.failed = False
        levels = [Level(sprites=[], grid_size=(64, 64), data=deepcopy(s), name=s["name"]) for s in LEVELS]
        super().__init__("q161", levels, Camera(0, 0, 64, 64, BG, BG, [self.display]), False, len(levels), [3, 4, 5, 6])
    def on_set_level(self, level):
        s = LEVELS[self.level_index]; self.n = s["n"]; self.answer = s["answer"]; self.clues = list(s["clues"]); self.cursor = self.clue_index = 0; self.survivors = (1 << self.n) - 1; self.budget_left = s["budget"]; self.failed = False
    def step(self):
        action = self.action.id.value; self.budget_left -= 1
        if action == 0: self.budget_left += 1; self.complete_action(); return
        if action == 3: self.cursor = (self.cursor - 1) % self.n
        elif action == 4: self.cursor = (self.cursor + 1) % self.n
        elif action == 5 and self.clue_index < len(self.clues):
            self.survivors &= self.clues[self.clue_index]; self.clue_index += 1
        elif action == 6:
            if self.cursor == self.answer: self.next_level()
            else: self.failed = True; self.lose()
        if self.budget_left <= 0: self.failed = True; self.lose()
        self.complete_action()
