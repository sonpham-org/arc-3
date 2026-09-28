# Author: GPT-6 Astra
# Date: 2026-09-28 13:10
# PURPOSE: Unbolt expansion: deterministic load transfer between a lifting jack, movable trestle, shelves and receivers; shared production rules for six visible physical puzzles and real API verification.
# SRP/DRY check: Pass — surveyed mechanical catalog neighbors; one pure transition owns geometry and settling, reused by smoke and random verification.
"""Click the jack, use arrows to roll/raise/lower it, and click bolts to remove them."""

from collections import namedtuple
from math import isfinite
import numpy as np
from arcengine import ARCBaseGame, Camera, GameState, Level, RenderableUserDisplay

WIDTH, FLOOR, CELL, OX, OY = 14, 9, 4, 4, 12
DIRECTIONS = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}
State = namedtuple("State", "positions pins jack selected alive done pulse feedback pointer trestle")
LEVELS = [
    {"name": "Supported release", "positions": ((6, 8),), "widths": (3,),
     "pins": (3,), "jack": (6, 9), "docks": (), "goal": (3, 8)},
    {"name": "Support transfer", "positions": ((3, 3), (8, 5), (3, 7)),
     "widths": (3, 3, 5), "pins": (3, 3, 3), "jack": (8, 6),
     "docks": ((5, 4), (8, 2)), "goal": (10, 8)},
    {"name": "Stack the steel", "positions": ((4, 4), (4, 7), (10, 8)),
     "widths": (3, 3, 3), "pins": (3, 3, 3), "jack": (4, 8),
     "docks": (), "goal": (10, 8), "trestle": (10, 4), "bounds": (3, 11)},
    {"name": "Exchange the glass", "positions": ((3, 8), (10, 7)),
     "widths": (3, 5), "pins": (3, 3), "jack": (3, 9),
     "docks": (), "goal": (10, 8), "goals": ((0, (10, 8)), (1, (3, 8))),
     "trestle": (4, 6), "bounds": (1, 12)},
    {"name": "Make room above", "positions": ((3, 8), (10, 7), (6, 6)),
     "widths": (3, 5, 3), "pins": (3, 3, 3), "jack": (6, 7),
     "docks": ((7, 4),), "goal": (10, 8), "goals": ((0, (10, 8)), (1, (3, 8))),
     "trestle": (9, 6), "bounds": (1, 12)},
    {"name": "Clear both bays", "positions": ((2, 8), (6, 8), (11, 7)),
     "widths": (3, 3, 5), "pins": (3, 3, 3), "jack": (6, 9),
     "docks": ((7, 4),), "goal": (8, 8),
     "goals": ((0, (8, 8)), (1, (12, 8)), (2, (3, 8))), "trestle": (9, 6)},
]


def initial(level):
    return State(level["positions"], level["pins"], level["jack"], False,
                 True, False, 0, "ready", level["jack"], level.get("trestle"))


def goals(level):
    return level.get("goals", ((0, level["goal"]),))


def trestle_cells(state):
    if state.trestle is None:
        return ()
    column, top = state.trestle
    # Include every coarse cell touched by the sloped visible legs and crossbar.
    return ((column, top),) + tuple((column+side, row)
        for row in range(top+1, FLOOR+2) for side in (-1, 0, 1))


def trestle_solid(state):
    # Rear legs sit behind the front jack rail, as the existing wall docks do.
    return () if state.trestle is None else (state.trestle,)


def trestle_loads(level, state):
    if state.trestle is None:
        return ()
    column, top = state.trestle
    return tuple(index for index in range(len(state.positions))
                 if (column, top-1) in beam_cells(level, state.positions, index))


def beam_cells(level, positions, index):
    center, row = positions[index]
    radius = level["widths"][index]//2
    return tuple((column, row) for column in range(center-radius, center+radius+1))


def supported(level, state, index, include_jack=True, excluding=()):
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
    if state.trestle is not None and state.trestle in below:
        return True
    return any(index != other and other not in excluding
               and below.intersection(beam_cells(level, state.positions, other))
               for other in range(len(state.positions)))


def settle(level, state):
    """Free steel settles; any uncontrolled drop of the glass core breaks it."""
    changed = True
    while changed:
        changed = False
        for index in sorted(range(len(state.positions)), key=lambda i: -state.positions[i][1]):
            if supported(level, state, index):
                continue
            if index in {item for item, _ in goals(level)}:
                return state._replace(alive=False, feedback="broken", pointer=state.positions[index])
            positions = list(state.positions)
            center, row = positions[index]
            positions[index] = (center, row+1)
            state = state._replace(positions=tuple(positions), feedback="settled")
            changed = True
    # Identical glass carriers are interchangeable between equally wide trays.
    actual = sorted((level["widths"][index], state.positions[index]) for index, _ in goals(level))
    expected = sorted((level["widths"][index], target) for index, target in goals(level))
    return state._replace(done=actual == expected and all(not state.pins[index] for index, _ in goals(level)))


def move_jack(level, state, action):
    if state.selected != "jack":
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
            # An independent receiver/trestle keeps the upper shelf when the
            # lower carried shelf descends out from underneath it.
            if dy > 0 and supported(level, state, index, include_jack=False, excluding=carried):
                continue
            if any(feet.intersection(beam_cells(level, state.positions, other)) for other in carried):
                carried.add(index)
    positions = tuple((x+dx, y+dy) if index in carried else (x, y)
                      for index, (x, y) in enumerate(state.positions))
    occupied = set(level["docks"]) | set(trestle_solid(state))
    for index in range(len(positions)):
        cells = beam_cells(level, positions, index)
        left, right = level.get("bounds", (0, WIDTH-1))
        if any(x < left or x > right or y < 0 or y >= FLOOR for x, y in cells):
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


def move_trestle(level, state, action):
    loaded = trestle_loads(level, state)
    if loaded:
        return state._replace(feedback="loaded", pointer=state.positions[loaded[0]])
    if action not in (3, 4):
        return state._replace(feedback="blocked", pointer=state.trestle)
    column, top = state.trestle
    moved = state._replace(trestle=(column+DIRECTIONS[action][0], top))
    if not 1 <= moved.trestle[0] <= WIDTH-2:
        return state._replace(feedback="blocked", pointer=state.trestle)
    obstacles = set(level["docks"])
    for index in range(len(state.positions)):
        obstacles.update(beam_cells(level, state.positions, index))
    if set(trestle_solid(moved)).intersection(obstacles):
        return state._replace(feedback="blocked", pointer=state.trestle)
    return settle(level, moved._replace(feedback="moved"))


def transition(level, state, action, point=None):
    if not state.alive or state.done:
        return state
    state = state._replace(pulse=1-state.pulse, feedback="refused")
    if action in DIRECTIONS:
        if state.selected == "trestle":
            return move_trestle(level, state, action)
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
        return state._replace(selected="jack", feedback="selected")
    if point in trestle_cells(state):
        return state._replace(selected="trestle", feedback="selected")
    return state


class UnboltDisplay(RenderableUserDisplay):
    def __init__(self, game):
        self.game = game

    def point(self, before, after):
        animation = self.game.animation
        fraction = 1 if animation is None else min(1, animation["index"]/6)
        fraction = fraction*fraction*(3-2*fraction)
        column = before[0]+(after[0]-before[0])*fraction
        row = before[1]+(after[1]-before[1])*fraction
        return OX+round(column*CELL), OY+round(row*CELL)

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        level, state = self.game.lvl, self.game.st
        before = self.game.animation["before"] if self.game.animation else state
        frame[:, :] = 4
        frame[10:59, 2:62] = 3
        frame[11:57, 3:61] = 5
        if "bounds" in level:
            left, right = level["bounds"]
            frame[12:48, OX:OX+left*CELL] = 3
            frame[12:48, OX+(right+1)*CELL:60] = 3
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
        for index, (goal_x, goal_y) in goals(level):
            radius = level["widths"][index]//2
            gx, gy = OX+(goal_x-radius)*CELL, OY+goal_y*CELL
            width = level["widths"][index]*CELL
            frame[gy+3:gy+5, gx:gx+width] = 10
            frame[gy:gy+5, gx-1] = frame[gy:gy+5, gx+width] = 10
        for column, row in level["docks"]:
            px, py = OX+column*CELL, OY+row*CELL
            frame[py:py+2, px:px+CELL] = 10
            frame[py+2:py+4, px+1:px+3] = 3
        if state.trestle is not None:
            tx, ty = state.trestle
            px, py = self.point(before.trestle, state.trestle)
            bottom = OY+FLOOR*CELL+3
            # A rear-rail A-frame: narrow contact saddle and visibly spread feet.
            for row in range(py+2, bottom):
                spread = round((row-py)/(bottom-py)*4)
                frame[row, px+1-spread:px+3-spread] = 14
                frame[row, px+1+spread:px+3+spread] = 14
            frame[bottom-1:bottom+1, px-4:px] = 14
            frame[bottom-1:bottom+1, px+4:px+8] = 14
            frame[bottom:bottom+2, px-3:px-1] = 1
            frame[bottom:bottom+2, px+5:px+7] = 1
            frame[py:py+2, px:px+4] = 14
            contact = trestle_loads(level, state) and (not self.game.animation or self.game.animation["index"] >= 6)
            frame[py, px:px+4] = 0 if contact else 10
            if state.selected == "trestle":
                frame[bottom+1, px-4:px+8] = 0
        jack_x, jack_top = state.jack
        px, py = self.point(before.jack, state.jack)
        base = OY+(FLOOR+1)*CELL
        frame[py:base+3, px+1:px+3] = 9
        frame[py:py+2, px:px+CELL] = 10
        frame[base+1:base+5, px-2:px+6] = 9
        frame[base+4:base+6, px-2:px] = frame[base+4:base+6, px+4:px+6] = 1
        for index, (center, row) in enumerate(state.positions):
            cells = beam_cells(level, state.positions, index)
            cup, by = self.point(before.positions[index], state.positions[index])
            bx = cup-level["widths"][index]//2*CELL
            width = level["widths"][index]*CELL
            fragile = index in {item for item, _ in goals(level)}
            frame[by:by+CELL, bx:bx+width] = 12 if fragile else 1
            frame[by+CELL-1, bx:bx+width] = 3
            # The middle underside cup is the jack docking point.
            frame[by+CELL-1, cup+1:cup+3] = 10
            if fragile:
                frame[by:by+2, cup+1:cup+3] = 0
            for side, end in ((1, cells[0][0]), (2, cells[-1][0])):
                ex = bx if side == 1 else bx+width-CELL
                if state.pins[index] & side:
                    frame[by:by+3, ex:ex+3] = 15
                    frame[by+1, ex+1] = 0
                else:
                    frame[by+1, ex+1] = 4
        # Pulse size changes on every action, including repeated rejected input.
        color = 8 if state.feedback in ("blocked", "broken", "refused") else 10
        frame[base, px-1:px+4+state.pulse] = color
        if state.selected == "jack":
            frame[base-1, px-1] = frame[base-1, px+4] = 0
        if state.feedback == "loaded":
            center, row = state.pointer
            lx, ly = OX+center*CELL, OY+row*CELL
            frame[ly-2, lx-2:lx+3+state.pulse] = 8
        if not state.alive:
            center, row = state.pointer
            bx, by = OX+center*CELL, OY+row*CELL
            frame[by, bx] = frame[by+1, bx+1] = frame[by+2, bx+2] = 8
            frame[by+1, bx+2] = frame[by+3, bx+1] = 5
        return frame


class Ub01(ARCBaseGame):
    def __init__(self):
        self.lvl, self.st = LEVELS[0], initial(LEVELS[0])
        self.animation = None
        self.display = UnboltDisplay(self)
        levels = [Level(sprites=[], grid_size=(64, 64), data={}, name=level["name"])
                  for level in LEVELS]
        super().__init__("ub01", levels, Camera(0, 0, 64, 64, 4, 4, [self.display]),
                         False, len(levels), [1, 2, 3, 4, 6])

    def on_set_level(self, level):
        self.lvl, self.st = LEVELS[self.level_index], initial(LEVELS[self.level_index])
        self.animation = None

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
        if self.animation is not None:
            self.animation["index"] += 1
            if self.animation["index"] == 8:
                self.animation = None
                self.finish_action()
            return
        point = None
        if action == 6:
            data = self.action.data or {}
            px, py = data.get("x", -100), data.get("y", -100)
            if (isinstance(px, (int, float)) and isinstance(py, (int, float))
                    and isfinite(px) and isfinite(py)):
                point = (int(px-OX)//CELL, int(py-OY)//CELL)
        before = self.st
        self.st = transition(self.lvl, before, action, point)
        if (self.st.positions, self.st.jack, self.st.trestle) != (before.positions, before.jack, before.trestle):
            self.animation = {"before": before, "index": 1}
            return
        self.finish_action()

    def finish_action(self):
        if not self.st.alive:
            self.lose()
        elif self.st.done:
            self.next_level()
        self.complete_action()
