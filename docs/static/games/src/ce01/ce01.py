# Author: GPT-6 Astra
# Date: 2026-09-27 18:53
# PURPOSE: Crease is a deterministic ARC-AGI-3 paper-folding environment. Stable
# original sheet cells map into folded stacks; punches remove every layer, and
# ACTION7 physically unfolds without restoring paper. NumPy and arcengine render
# the visible reference, working sheet, crease lines, and expendable punch dies.
# SRP/DRY check: Pass — searched existing games; no reusable layered-paper model.
"""Fold toward an arrow, click to aim, ACTION5 cuts, ACTION7 unfolds."""

import math
from collections import namedtuple
from functools import lru_cache

import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

SIZE = 10
CELL = 3
OX, OY = 1, 22
TX, TY = 33, 22
ACTION_IDS = (1, 2, 3, 4, 5, 6, 7)
PAPER, EDGE, BOARD, HOLE, CYAN, RED, GREEN = 0, 2, 4, 5, 10, 8, 14

# Targets are fixed original-paper coordinates, never generated at runtime.
LEVELS = (
    dict(name="Pair", target=((0, 1), (3, 1)), dies=1, offset=(0, 0), missing=()),
    dict(name="Butterfly", target=((0, 1), (9, 1), (1, 3), (8, 3), (3, 4),
         (6, 4), (2, 6), (7, 6), (4, 8), (5, 8)), dies=5, offset=(0, 0), missing=()),
    dict(name="Four reflections", target=((0, 0), (9, 0), (3, 1), (6, 1), (1, 2),
         (8, 2), (0, 3), (3, 3), (4, 3), (5, 3), (6, 3), (9, 3), (2, 4), (7, 4),
         (2, 5), (7, 5), (0, 6), (3, 6), (4, 6), (5, 6), (6, 6), (9, 6), (1, 7),
         (8, 7), (3, 8), (6, 8), (0, 9), (9, 9)), dies=7, offset=(0, 0), missing=()),
    dict(name="Offset crease", target=((3, 1), (4, 1), (1, 3), (6, 3), (2, 5),
         (5, 5), (0, 7), (7, 7), (3, 8), (4, 8)), dies=5, offset=(-1, 0), missing=()),
    dict(name="Changing layers", target=((0, 0), (9, 0), (1, 1), (4, 1), (5, 1),
         (8, 1), (2, 2), (3, 2), (6, 2), (7, 2), (0, 3), (9, 3), (4, 4), (5, 4),
         (0, 6), (9, 6), (2, 7), (3, 7), (6, 7), (7, 7), (1, 8), (4, 8), (5, 8),
         (8, 8)), dies=7, offset=(0, 0), missing=()),
    dict(name="Notched flower", target=((3, 0), (4, 0), (6, 1), (2, 2), (5, 2),
         (0, 3), (7, 3), (3, 4), (4, 4), (3, 5), (4, 5), (0, 6), (1, 6), (6, 6),
         (7, 6), (2, 7), (5, 7), (1, 8), (2, 8), (5, 8), (6, 8), (3, 9), (4, 9)),
         dies=7, offset=(-1, 0), missing=((0, 0), (1, 0), (0, 1), (1, 1),
         (8, 8), (9, 8), (8, 9), (9, 9))),
)


PaperState = namedtuple("PaperState", "positions holes history used failed aimed", defaults=(0, (), 0, False, None))


@lru_cache(maxsize=None)
def original_cells(index):
    missing = LEVELS[index]["missing"]
    return tuple((x, y) for y in range(4 if index == 0 else SIZE) for x in range(4 if index == 0 else SIZE)
                 if (x, y) not in missing)


def initial_state(index):
    return PaperState(original_cells(index))


@lru_cache(maxsize=None)
def target_bits(index):
    return sum(1 << cell for cell, point in enumerate(original_cells(index))
               if point in LEVELS[index]["target"])


def crease_lines(index, state):
    xs, ys = zip(*state.positions)
    dx, dy = LEVELS[index]["offset"] if not state.history else (0, 0)
    return (min(xs) + (max(xs) - min(xs) + 1) // 2 + dx,
            min(ys) + (max(ys) - min(ys) + 1) // 2 + dy)


def stacks(state):
    result = {}
    for cell, point in enumerate(state.positions):
        if not state.holes & (1 << cell):
            result[point] = result.get(point, 0) | (1 << cell)
    return result


def transition(index, state, action, point=None):
    """One shared transition for the real environment and verification rollouts."""
    if state.failed:
        return state, "refuse"
    if action == 7:
        if not state.history:
            return state, "refuse"
        return state._replace(positions=state.history[-1], history=state.history[:-1], aimed=None), "unfold"
    if action == 6:
        if point not in stacks(state):
            return state, "refuse"
        return state._replace(aimed=point), "aim"
    if action == 5:
        layer_bits = stacks(state).get(state.aimed, 0)
        if not layer_bits or state.used >= LEVELS[index]["dies"]:
            return state, "refuse"
        holes = state.holes | layer_bits
        used = state.used + 1
        failed = bool(holes & ~target_bits(index))
        failed |= used == LEVELS[index]["dies"] and holes != target_bits(index)
        if index == 0 and failed:
            return state, "refuse"
        return state._replace(holes=holes, used=used, failed=failed, aimed=None), "punch"
    if action not in (1, 2, 3, 4):
        return state, "refuse"
    if index == 0 and (action in (1, 2) or state.history):
        return state, "refuse"
    cx, cy = crease_lines(index, state)
    axis, crease = (1, cy) if action in (1, 2) else (0, cx)
    moving_high = action in (1, 3)
    values = [point[axis] for point in state.positions]
    if not min(values) < crease <= max(values):
        return state, "refuse"
    moved = []
    for point in state.positions:
        target = list(point)
        if (point[axis] >= crease) == moving_high:
            target[axis] = 2 * crease - 1 - point[axis]
        if not 0 <= target[axis] < (4 if index == 0 else SIZE):
            return state, "refuse"
        moved.append(tuple(target))
    return state._replace(positions=tuple(moved), history=state.history + (state.positions,), aimed=None), "fold"


def is_clear(index, state):
    return not state.failed and not state.history and state.holes == target_bits(index)


def layout(index):
    return (4, 7, 2, 22, 34, 22) if index == 0 else (10, 3, 1, 22, 33, 22)


CONTROL_ACTIONS = (1, 2, 3, 4, 5, 7)


def decode_click(index, x, y):
    """The pictured buttons and paper share this real click decoder."""
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return 6, None
    if not math.isfinite(x) or not math.isfinite(y):
        return 6, None
    for button, action in enumerate(CONTROL_ACTIONS):
        if 2 + button * 10 <= x < 10 + button * 10 and 2 <= y < 14:
            return action, None
    size, cell, ox, oy, _tx, _ty = layout(index)
    if ox <= x < ox + size * cell and oy <= y < oy + size * cell:
        return 6, (int((x - ox) // cell), int((y - oy) // cell))
    return 6, None


def tutorial_action(state):
    if state.holes:
        return 7
    if not state.history:
        return 3
    return 5 if state.aimed is not None else 6


class CreaseDisplay(RenderableUserDisplay):
    def __init__(self, game):
        self.game = game

    @staticmethod
    def rect(image, x, y, width, height, color):
        left, top = max(0, int(x)), max(0, int(y))
        right, bottom = min(64, int(x + width)), min(64, int(y + height))
        if right > left and bottom > top:
            image[top:bottom, left:right] = color

    def ring(self, image, x, y, radius, color, thickness=1):
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if (radius - thickness) ** 2 <= dx * dx + dy * dy <= radius ** 2:
                    self.rect(image, x + dx, y + dy, 1, 1, color)

    @staticmethod
    def aperture_pixel(cell, col, row):
        if cell > 3:
            return 1 <= col <= 5 and 1 <= row <= 5 and not (col in (1, 5) and row in (1, 5))
        return col in (1, 2) and row in (1, 2)

    def aperture(self, image, x, y, cell, color=5):
        for row in range(cell):
            for col in range(cell):
                if self.aperture_pixel(cell, col, row):
                    self.rect(image, x + col, y + row, 1, 1, color)

    def icon(self, image, action, cx, cy, color):
        if action in (1, 2):
            direction = -1 if action == 1 else 1
            self.rect(image, cx, cy - 3, 1, 7, color)
            for distance in range(3):
                self.rect(image, cx - distance, cy + direction * (3 - distance), 2 * distance + 1, 1, color)
        elif action in (3, 4):
            direction = -1 if action == 3 else 1
            self.rect(image, cx - 3, cy, 7, 1, color)
            for distance in range(3):
                self.rect(image, cx + direction * (3 - distance), cy - distance, 1, 2 * distance + 1, color)
        elif action == 5:
            self.rect(image, cx, cy - 4, 1, 6, color)
            self.rect(image, cx - 2, cy - 1, 5, 1, color)
            self.rect(image, cx - 1, cy, 3, 1, color)
            self.rect(image, cx - 3, cy + 3, 3, 1, color)
            self.rect(image, cx + 1, cy + 3, 3, 1, color)
        else:
            # Two outlined leaves share a central hinge and open sideways.
            for side in (-1, 1):
                self.rect(image, cx + side * 3, cy - 2, 1, 5, color)
                for distance in range(1, 4):
                    bend = 1 if distance == 1 else 0
                    self.rect(image, cx + side * distance, cy - 2 + bend, 1, 1, color)
                    self.rect(image, cx + side * distance, cy + 2 + bend, 1, 1, color)
            self.rect(image, cx, cy, 1, 4, color)

    def controls(self, image, index, state):
        game = self.game
        suggested = tutorial_action(state) if index == 0 else 0
        for button, action in enumerate(CONTROL_ACTIONS):
            x = 2 + button * 10
            disabled = bool(index == 0 and (action in (1, 2) or (action in (3, 4) and state.history)))
            disabled |= action == 5 and state.aimed is None
            disabled |= action == 7 and not state.history
            border = 10 if action == suggested else 2
            refused = game.event == "refuse" and action == game.last_action
            if refused:
                border = 8
            self.rect(image, x, 2, 8, 12, border)
            self.rect(image, x + 1, 3, 6, 10, 4 if not disabled else 3)
            shift = game.pulse if refused else 0
            self.icon(image, action, x + 3, 8 + shift, 2 if disabled else 0)

    def sheet(self, image, index, state, ox, oy, target=False):
        _size, cell, _ox, _oy, _tx, _ty = layout(index)
        points = set(original_cells(index) if target else state.positions)
        depth = 1 if target else min(3, len(state.history) + 1)
        for x, y in points:
            self.rect(image, ox + x * cell + 1, oy + y * cell + depth, cell, cell, 2)
        for x, y in points:
            self.rect(image, ox + x * cell, oy + y * cell, cell, cell, 0)
        # Tiny intersections keep a coherent sheet while allowing cell alignment.
        for x, y in points:
            if x and y and (x - 1, y) in points and (x, y - 1) in points:
                self.rect(image, ox + x * cell, oy + y * cell, 1, 1, 1)
        remaining = stacks(state)
        for x, y in points:
            hole = (x, y) in LEVELS[index]["target"] if target else (x, y) not in remaining
            if hole:
                self.aperture(image, ox + x * cell, oy + y * cell, cell)

    def creases(self, image, index, state):
        """Only show hinges that the shared transition can actually fold."""
        _size, cell, ox, oy, _tx, _ty = layout(index)
        points = set(state.positions)
        crease_x, crease_y = crease_lines(index, state)
        valid = {action for action in (1, 2, 3, 4)
                 if transition(index, state, action)[1] == "fold"}
        if valid & {3, 4}:
            for row in range(_size * cell):
                paper_y = row // cell
                if row % 4 < 2 and (crease_x - 1, paper_y) in points and (crease_x, paper_y) in points:
                    self.rect(image, ox + crease_x * cell, oy + row, 1, 1, 1)
        if index and valid & {1, 2}:
            for col in range(_size * cell):
                paper_x = col // cell
                if col % 4 < 2 and (paper_x, crease_y - 1) in points and (paper_x, crease_y) in points:
                    self.rect(image, ox + col, oy + crease_y * cell, 1, 1, 1)

    def folding(self, image, index, animation):
        before, after = animation["before"], animation["after"]
        flat, folded = (before, after) if animation["kind"] == "fold" else (after, before)
        _size, cell, ox, oy, _tx, _ty = layout(index)
        changed = next((old, new) for old, new in zip(flat.positions, folded.positions) if old != new)
        axis = 0 if changed[0][0] != changed[1][0] else 1
        crease = (changed[0][axis] + changed[1][axis] + 1) / 2
        progress = min(1.0, animation["frame"] / 23)
        cosine = math.cos(math.pi * progress)
        if animation["kind"] == "unfold":
            cosine = -cosine
        groups = {}
        for number, point in enumerate(flat.positions):
            groups[point] = groups.get(point, 0) | (1 << number)
        moving = {old for old, new in zip(flat.positions, folded.positions) if old != new}
        for x, y in groups:
            if (x, y) in moving:
                continue
            self.rect(image, ox + x * cell + 1, oy + y * cell + 2, cell, cell, 2)
        for (x, y), bits in groups.items():
            if (x, y) in moving:
                continue
            self.rect(image, ox + x * cell, oy + y * cell, cell, cell, 0)
            if not bits & ~before.holes:
                self.aperture(image, ox + x * cell, oy + y * cell, cell)
        for (x, y), bits in groups.items():
            if (x, y) not in moving:
                continue
            start = x if axis == 0 else y
            first = crease + (start - crease) * cosine
            last = crease + (start + 1 - crease) * cosine
            low, width = min(first, last), max(1, abs(last - first) * cell)
            xx, yy = (ox + low * cell, oy + y * cell) if axis == 0 else (ox + x * cell, oy + low * cell)
            self.rect(image, round(xx), round(yy), width if axis == 0 else cell,
                      cell if axis == 0 else width, 1 if abs(cosine) < 0.7 else 0)
            if not bits & ~before.holes:
                for row in range(cell):
                    for col in range(cell):
                        if not self.aperture_pixel(cell, col, row):
                            continue
                        hx, hy = x + (col + 0.5) / cell, y + (row + 0.5) / cell
                        if axis == 0:
                            hx = crease + (hx - crease) * cosine
                        else:
                            hy = crease + (hy - crease) * cosine
                        self.rect(image, int(ox + hx * cell), int(oy + hy * cell), 1, 1, 5)
        # The crease stays in place while the entire flap turns around it.
        if axis == 0:
            self.rect(image, ox + crease * cell, oy, 1, layout(index)[0] * cell, 2)
        else:
            self.rect(image, ox, oy + crease * cell, layout(index)[0] * cell, 1, 2)

    def render_interface(self, frame):
        game, image = self.game, np.full((64, 64), 3, dtype=np.int8)
        state, index = game.paper, game.level_index
        size, cell, ox, oy, tx, ty = layout(index)
        self.controls(image, index, state)
        # A small checkered flag labels the fixed reference; no changing HUD marks.
        self.rect(image, tx + 11, 16, 1, 5, 1)
        for row in range(3):
            for col in range(5):
                self.rect(image, tx + 12 + col, 16 + row, 1, 1, 0 if (row + col) % 2 else 5)
        self.sheet(image, index, state, tx, ty, target=True)
        animation = game.animation
        if animation and animation["kind"] in ("fold", "unfold"):
            self.folding(image, index, animation)
        else:
            shown = animation["after"] if animation and animation["frame"] >= 6 else state
            self.sheet(image, index, shown, ox, oy)
            if not animation:
                self.creases(image, index, state)
            aim = state.aimed
            if index == 0 and tutorial_action(state) == 6:
                target_cell = original_cells(0).index(LEVELS[0]["target"][0])
                aim = state.positions[target_cell]
            if aim is not None and not animation:
                xx, yy = ox + aim[0] * cell + cell // 2, oy + aim[1] * cell + cell // 2
                thickness = 1 + game.pulse if state.aimed is not None else 1
                self.ring(image, xx, yy, max(2, cell // 2), 12, thickness)
                if state.aimed is not None:
                    self.rect(image, xx, yy, 1, 1, 12)
            if animation and animation["kind"] == "punch":
                aim = animation["before"].aimed
                xx, yy = ox + aim[0] * cell + cell // 2, oy + aim[1] * cell + cell // 2
                radius = max(1, 5 - animation["frame"] // 2)
                if animation["frame"] < 8:
                    self.ring(image, xx, yy, radius, 4)
        if game.event == "refuse" and game.last_action == 6 and game.last_click is not None:
            xx, yy = game.last_click
            self.ring(image, xx, yy, 2 + game.pulse, 8)
        for die in range(LEVELS[index]["dies"]):
            xx = 3 + die * 5
            self.rect(image, xx, 57, 3, 4, 1 if die >= state.used else 4)
            self.rect(image, xx + 1, 58, 1, 2, 0 if die >= state.used else 3)
        if state.failed:
            self.rect(image, ox, oy - 1, size * cell, 1, 8)
        return image


class Ce01(ARCBaseGame):
    def __init__(self):
        self.display = CreaseDisplay(self)
        self.paper = initial_state(0)
        self.last_action, self.pulse, self.event = 0, 0, ""
        self.last_click = None
        self.animation = None
        levels = [Level(sprites=[], grid_size=(64, 64), data={"index": index}, name=level["name"])
                  for index, level in enumerate(LEVELS)]
        super().__init__("ce01", levels, Camera(0, 0, 64, 64, 3, 3, [self.display]),
                         False, len(levels), list(ACTION_IDS))

    def on_set_level(self, level):
        self.paper = initial_state(level.get_data("index"))
        self.last_action, self.pulse, self.event, self.animation = 0, 0, "", None
        self.last_click = None

    def handle_reset(self):
        if self._score == len(LEVELS):
            self.full_reset()
        else:
            self.level_reset()

    def finish(self, after):
        self.paper = after
        self.animation = None
        if self.paper.failed:
            self.lose()
        elif is_clear(self.level_index, self.paper):
            self.next_level()
        self.complete_action()

    def step(self):
        if self.action.id.value == 0:
            self.complete_action()
            return
        if self.animation is not None:
            self.animation["frame"] += 1
            if self.animation["frame"] >= self.animation["total"] - 1:
                self.finish(self.animation["after"])
            return
        action, point = self.action.id.value, None
        self.last_click = None
        if action == 6:
            click_x, click_y = self.action.data.get("x"), self.action.data.get("y")
            if all(isinstance(value, (int, float)) and math.isfinite(value) for value in (click_x, click_y)):
                self.last_click = tuple(max(0, min(63, int(value))) for value in (click_x, click_y))
            action, point = decode_click(self.level_index, click_x, click_y)
        before = self.paper
        after, self.event = transition(self.level_index, before, action, point)
        self.last_action, self.pulse = action, self.pulse ^ 1
        if self.event in ("fold", "unfold", "punch"):
            # Keep the final matching sheet visible before the engine advances.
            # Fifty-nine local frames plus its level-change frame stay at sixty.
            total = 59 if is_clear(self.level_index, after) else 30 if self.event in ("fold", "unfold") else 12
            self.animation = dict(kind=self.event, before=before, after=after, frame=0,
                                  total=total)
            return
        self.finish(after)
