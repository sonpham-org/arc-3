# Author: GPT-6 Astra
# Date: 2026-09-27 18:35
# PURPOSE: Crease is a deterministic ARC-AGI-3 paper-folding environment. Stable
# original sheet cells map into folded stacks; punches remove every layer, and
# ACTION7 physically unfolds without restoring paper. NumPy and arcengine render
# the visible reference, working sheet, crease lines, and expendable punch dies.
# SRP/DRY check: Pass — searched existing games; no reusable layered-paper model.
"""Fold toward an arrow, click to aim, ACTION5 cuts, ACTION7 unfolds."""

from collections import namedtuple
from functools import lru_cache

import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

SIZE = 10
CELL = 3
OX, OY = 3, 20
TX, TY = 41, 26
ACTION_IDS = (1, 2, 3, 4, 5, 6, 7)
PAPER, EDGE, BOARD, HOLE, CYAN, RED, GREEN = 0, 2, 4, 5, 10, 8, 14

# Targets are fixed original-paper coordinates, never generated at runtime.
LEVELS = (
    dict(name="Pair", target=((1, 2), (8, 2)), dies=1, offset=(0, 0), missing=()),
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
    return tuple((x, y) for y in range(SIZE) for x in range(SIZE)
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
        if not 0 <= target[axis] < SIZE:
            return state, "refuse"
        moved.append(tuple(target))
    return state._replace(positions=tuple(moved), history=state.history + (state.positions,), aimed=None), "fold"


def is_clear(index, state):
    return not state.failed and not state.history and state.holes == target_bits(index)


def click_point(x, y):
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return None
    if OX <= x < OX + SIZE * CELL and OY <= y < OY + SIZE * CELL:
        return int((x - OX) // CELL), int((y - OY) // CELL)
    return None


class CreaseDisplay(RenderableUserDisplay):
    def __init__(self, game):
        self.game = game

    def render_interface(self, frame):
        game, image = self.game, np.full((64, 64), BOARD, dtype=np.int8)
        state, index = game.paper, game.level_index
        image[2:17, 1:63] = 5
        # Four arrow stamps are spatial examples of the four folding controls.
        for action, center in ((1, 7), (2, 17), (3, 27), (4, 37)):
            image[5:14, center - 4:center + 5] = 3
            color = CYAN if action == game.last_action else 1
            if action in (1, 2):
                image[7:12, center] = color
                yy = 7 if action == 1 else 11
                image[yy, center - 2:center + 3] = color
                image[yy + (1 if action == 1 else -1), center - 1:center + 2] = color
            else:
                image[9, center - 2:center + 3] = color
                xx = center - 2 if action == 3 else center + 2
                image[7:12, xx] = color
                image[8:11, xx + (1 if action == 3 else -1)] = color
        # Dies physically leave their holder after a cut. No arbitrary move budget.
        for die in range(LEVELS[index]["dies"]):
            xx = 3 + die * 5
            image[55:61, xx:xx + 4] = EDGE
            image[56:60, xx + 1:xx + 3] = 0 if die >= state.used else 5
        occupied = stacks(state)
        all_points = set(state.positions)
        for x, y in sorted(all_points):
            xx, yy = OX + x * CELL, OY + y * CELL
            count = sum(point == (x, y) for point in state.positions)
            image[yy:yy + CELL, xx:xx + CELL] = EDGE
            image[yy:yy + CELL - 1, xx:xx + CELL - 1] = PAPER
            if count > 1:
                image[yy + 2, xx:xx + min(2, count)] = CYAN
            if (x, y) not in occupied:
                image[yy:yy + 2, xx:xx + 2] = HOLE
        # Empty reference cells retain an outline; requested holes are dark and large.
        image[TY - 3:TY + 22, TX - 2:TX + 22] = CYAN
        image[TY - 2:TY + 21, TX - 1:TX + 21] = BOARD
        for x, y in original_cells(index):
            xx, yy = TX + x * 2, TY + y * 2
            image[yy:yy + 2, xx:xx + 2] = 0
            if (x, y) in LEVELS[index]["target"]:
                image[yy:yy + 2, xx:xx + 2] = HOLE
        cx, cy = crease_lines(index, state)
        xs, ys = zip(*state.positions)
        if min(xs) < cx <= max(xs):
            image[OY + min(ys) * CELL:OY + (max(ys) + 1) * CELL:2, OX + cx * CELL - 1] = CYAN
        if min(ys) < cy <= max(ys):
            image[OY + cy * CELL - 1, OX + min(xs) * CELL:OX + (max(xs) + 1) * CELL:2] = CYAN
        # Open-book pictogram on the final control represents physical unfold.
        image[6:13, 47:53] = 0
        image[6:13, 54:60] = 1
        image[5:14, 53] = CYAN
        if game.last_action == 7:
            image[14:16, 46:61] = CYAN
        # Punch press: the mouth lights only once the player has aimed it.
        image[54:62, 46:60] = 2
        image[56:60, 48:58] = 5
        image[54:58, 52:55] = CYAN if state.aimed is not None else 1
        if state.aimed is not None:
            xx, yy = OX + state.aimed[0] * CELL, OY + state.aimed[1] * CELL
            image[yy - 1:yy + 4, xx - 1] = CYAN
            image[yy - 1:yy + 4, xx + 3] = CYAN
            image[yy - 1, xx - 1:xx + 4] = CYAN
            image[yy + 3, xx - 1:xx + 4] = CYAN
        if game.event_point is not None:
            x, y = game.event_point
            xx, yy = OX + x * CELL, OY + y * CELL
            color = RED if game.event == "refuse" or state.failed else CYAN
            inset = game.pulse
            image[max(0, yy - 1):min(64, yy + 5), max(0, xx - 1 + inset)] = color
            image[max(0, yy - 1 + inset), max(0, xx - 1):min(64, xx + 5)] = color
        elif game.event == "refuse":
            # The fold stamp itself changes on each refused action.
            xx = {1: 7, 2: 17, 3: 27, 4: 37, 5: 53, 7: 53}.get(game.last_action, 52)
            yy = 54 if game.last_action == 5 else 5
            image[yy:yy + 7, xx - 2 + game.pulse:xx + 2 + game.pulse] = RED
        if state.failed:
            image[OY - 2, OX:OX + 32] = RED
            image[OY + 33, OX:OX + 32] = RED
        return image


class Ce01(ARCBaseGame):
    def __init__(self):
        self.display = CreaseDisplay(self)
        self.paper = initial_state(0)
        self.last_action = 0
        self.pulse = 0
        self.event = ""
        self.event_point = None
        levels = [Level(sprites=[], grid_size=(64, 64), data={"index": index}, name=level["name"])
                  for index, level in enumerate(LEVELS)]
        super().__init__("ce01", levels, Camera(0, 0, 64, 64, BOARD, BOARD, [self.display]),
                         False, len(levels), list(ACTION_IDS))

    def on_set_level(self, level):
        self.paper = initial_state(level.get_data("index"))
        self.last_action, self.pulse, self.event, self.event_point = 0, 0, "", None

    def step(self):
        action = self.action.id.value
        if action == 0:
            self.complete_action()
            return
        point = None
        if action == 6:
            point = click_point(self.action.data.get("x"), self.action.data.get("y"))
        event_point = self.paper.aimed if action == 5 else point
        self.paper, self.event = transition(self.level_index, self.paper, action, point)
        self.last_action, self.event_point = action, event_point
        self.pulse ^= 1
        if self.paper.failed:
            self.lose()
        elif is_clear(self.level_index, self.paper):
            self.next_level()
        self.complete_action()
