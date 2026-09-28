# Author: GPT-6 Astra
# Date: 2026-09-27 18:28
# PURPOSE: Deterministic support-transfer disassembly: a rolling jack carries released shelves while visible bolts and docks determine support; standalone ARC game and shared verification rules.
# SRP/DRY check: Pass — surveyed mechanical catalog neighbors; one pure transition owns geometry and settling, reused by smoke and random verification.
"""Click the jack, use arrows to roll/raise/lower it, and click bolts to remove them."""

from collections import namedtuple
from math import isfinite
import numpy as np
from arcengine import ARCBaseGame, Camera, GameState, Level, RenderableUserDisplay

WIDTH, FLOOR, CELL, OX, OY = 14, 9, 4, 4, 12
DIRECTIONS = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}
State = namedtuple("State", "positions pins jack selected alive done pulse feedback pointer")
LEVELS = [
    {"name": "Supported release", "positions": ((6, 8),), "widths": (3,),
     "pins": (3,), "jack": (6, 9), "docks": (), "goal": (3, 8)},
    {"name": "Take the load", "positions": ((5, 2), (5, 6)), "widths": (3, 3),
     "pins": (3, 3), "jack": (5, 10), "docks": ((9, 7), (11, 7)), "goal": (3, 8)},
    {"name": "Support transfer", "positions": ((6, 2), (6, 4), (6, 6)),
     "widths": (3, 3, 3), "pins": (3, 3, 3), "jack": (6, 10),
     "docks": ((10, 7), (12, 7), (1, 5), (3, 5)), "goal": (8, 8)},
]


def initial(level):
    return State(level["positions"], level["pins"], level["jack"], False,
                 True, False, 0, "ready", level["jack"])


def beam_cells(level, positions, index):
    center, row = positions[index]
    radius = level["widths"][index]//2
    return tuple((column, row) for column in range(center-radius, center+radius+1))


def supported(level, state, index, include_jack=True):
    center, row = state.positions[index]
    if row == FLOOR-1 or state.pins[index]:
        return True
    radius = level["widths"][index]//2
    if (include_jack and state.jack[1] == row+1
            and center-radius <= state.jack[0] <= center+radius):
        return True
    below = {(x, y+1) for x, y in beam_cells(level, state.positions, index)}
    if below.intersection(level["docks"]):
        return True
    return any(index != other and below.intersection(beam_cells(level, state.positions, other))
               for other in range(len(state.positions)))


def settle(level, state):
    """Free steel settles; any uncontrolled drop of the glass core breaks it."""
    changed = True
    while changed:
        changed = False
        for index in sorted(range(len(state.positions)), key=lambda i: -state.positions[i][1]):
            if supported(level, state, index):
                continue
            if index == 0:
                return state._replace(alive=False, feedback="broken")
            positions = list(state.positions)
            center, row = positions[index]
            positions[index] = (center, row+1)
            state = state._replace(positions=tuple(positions), feedback="settled")
            changed = True
    return state._replace(done=state.positions[0] == level["goal"] and state.pins[0] == 0)


def move_jack(level, state, action):
    if not state.selected:
        return state._replace(feedback="select")
    dx, dy = DIRECTIONS[action]
    column, top = state.jack
    new_jack = (column+dx, top+dy)
    if not (0 <= new_jack[0] < WIDTH and 0 <= new_jack[1] <= FLOOR+1):
        return state._replace(feedback="blocked")
    carried = {index for index, position in enumerate(state.positions)
               if position == (column, top-1) and not state.pins[index]
               and not (dy > 0 and supported(level, state, index, include_jack=False))}
    # Any free shelf resting directly on this load moves with it.
    for _ in state.positions:
        for index, position in enumerate(state.positions):
            if index in carried or state.pins[index]:
                continue
            feet = {(x, y+1) for x, y in beam_cells(level, state.positions, index)}
            if any(feet.intersection(beam_cells(level, state.positions, other)) for other in carried):
                carried.add(index)
    positions = tuple((x+dx, y+dy) if index in carried else (x, y)
                      for index, (x, y) in enumerate(state.positions))
    occupied = set(level["docks"])
    for index in range(len(positions)):
        cells = beam_cells(level, positions, index)
        if any(x < 0 or x >= WIDTH or y < 0 or y >= FLOOR for x, y in cells):
            return state._replace(feedback="blocked")
        if occupied.intersection(cells):
            return state._replace(feedback="blocked")
        occupied.update(cells)
    # Wall receivers sit behind the trolley rail; the mast is blocked by shelves themselves.
    mast = {(new_jack[0], row) for row in range(new_jack[1], FLOOR)}
    beam_occupancy = {cell for index in range(len(positions)) for cell in beam_cells(level, positions, index)}
    if mast.intersection(beam_occupancy):
        return state._replace(feedback="blocked")
    return settle(level, state._replace(positions=positions, jack=new_jack, feedback="moved"))


def transition(level, state, action, point=None):
    if not state.alive or state.done:
        return state
    state = state._replace(pulse=1-state.pulse, feedback="refused")
    if action in DIRECTIONS:
        return move_jack(level, state, action)
    if action != 6 or point is None:
        return state
    state = state._replace(pointer=point)
    column, row = point
    for index, (center, beam_row) in enumerate(state.positions):
        radius = level["widths"][index]//2
        for side, bolt_column in ((1, center-radius), (2, center+radius)):
            if point == (bolt_column, beam_row) and state.pins[index] & side:
                pins = list(state.pins)
                pins[index] &= ~side
                return settle(level, state._replace(pins=tuple(pins), feedback="unbolted"))
    if column == state.jack[0] and state.jack[1] <= row <= FLOOR+1:
        return state._replace(selected=True, feedback="selected")
    return state


class UnboltDisplay(RenderableUserDisplay):
    def __init__(self, game):
        self.game = game

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        level, state = self.game.lvl, self.game.st
        frame[:, :] = 4
        frame[10:59, 2:62] = 3
        frame[11:57, 3:61] = 5
        frame[OY+FLOOR*CELL:OY+FLOOR*CELL+2, OX:60] = 2
        # A glass vial and receiving cradle identify the protected object and destination.
        frame[2:8, 5:12] = 12
        frame[3:6, 7:10] = 0
        frame[4:8, 17:20] = 10
        frame[7:9, 16:21] = 9
        frame[5, 25:33] = 1
        frame[4:7, 32] = 1
        frame[7:9, 38:49] = 10
        frame[3:8, 38:40] = frame[3:8, 47:49] = 10
        goal_x, goal_y = level["goal"]
        gx, gy = OX+(goal_x-1)*CELL, OY+goal_y*CELL
        frame[gy+3:gy+5, gx:gx+12] = 10
        frame[gy:gy+5, gx-1] = frame[gy:gy+5, gx+12] = 10
        for column, row in level["docks"]:
            px, py = OX+column*CELL, OY+row*CELL
            frame[py:py+2, px:px+CELL] = 10
            frame[py+2:py+4, px+1:px+3] = 3
        jack_x, jack_top = state.jack
        px, py = OX+jack_x*CELL, OY+jack_top*CELL
        base = OY+(FLOOR+1)*CELL
        frame[py:base+3, px+1:px+3] = 9
        frame[py:py+2, px:px+CELL] = 10
        frame[base+1:base+5, px-2:px+6] = 9
        frame[base+4:base+6, px-2:px] = frame[base+4:base+6, px+4:px+6] = 1
        for index, (center, row) in enumerate(state.positions):
            cells = beam_cells(level, state.positions, index)
            bx, by = OX+cells[0][0]*CELL, OY+row*CELL
            width = level["widths"][index]*CELL
            frame[by:by+CELL, bx:bx+width] = 12 if index == 0 else 1
            frame[by+CELL-1, bx:bx+width] = 3
            # The middle underside cup is the jack docking point.
            cup = OX+center*CELL
            frame[by+CELL-1, cup+1:cup+3] = 10
            if index == 0:
                frame[by:by+2, cup+1:cup+3] = 0
            for side, end in ((1, cells[0][0]), (2, cells[-1][0])):
                ex = OX+end*CELL
                if state.pins[index] & side:
                    frame[by:by+3, ex:ex+3] = 15
                    frame[by+1, ex+1] = 0
                else:
                    frame[by+1, ex+1] = 4
        # Pulse size changes on every action, including repeated rejected input.
        color = 8 if state.feedback in ("blocked", "broken", "refused") else 10
        frame[base, px-1:px+4+state.pulse] = color
        if state.selected:
            frame[base-1, px-1] = frame[base-1, px+4] = 0
        if not state.alive:
            center, row = state.positions[0]
            bx, by = OX+center*CELL, OY+row*CELL
            frame[by, bx] = frame[by+1, bx+1] = frame[by+2, bx+2] = 8
            frame[by+1, bx+2] = frame[by+3, bx+1] = 5
        return frame


class Ub01(ARCBaseGame):
    def __init__(self):
        self.lvl, self.st = LEVELS[0], initial(LEVELS[0])
        self.display = UnboltDisplay(self)
        levels = [Level(sprites=[], grid_size=(64, 64), data={}, name=level["name"])
                  for level in LEVELS]
        super().__init__("ub01", levels, Camera(0, 0, 64, 64, 4, 4, [self.display]),
                         False, len(levels), [1, 2, 3, 4, 6])

    def on_set_level(self, level):
        self.lvl, self.st = LEVELS[self.level_index], initial(LEVELS[self.level_index])

    def handle_reset(self):
        if self._state in (GameState.NOT_PLAYED, GameState.WIN):
            self.full_reset()
        else:
            self.level_reset()

    def step(self):
        action = self.action.id.value
        if action == 0:
            self.complete_action()
            return
        point = None
        if action == 6:
            data = self.action.data or {}
            px, py = data.get("x", -100), data.get("y", -100)
            if (isinstance(px, (int, float)) and isinstance(py, (int, float))
                    and isfinite(px) and isfinite(py)):
                point = (int(px-OX)//CELL, int(py-OY)//CELL)
        self.st = transition(self.lvl, self.st, action, point)
        if not self.st.alive:
            self.lose()
        elif self.st.done:
            self.next_level()
        self.complete_action()
