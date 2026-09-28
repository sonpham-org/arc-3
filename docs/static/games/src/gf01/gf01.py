# Author: GPT-6 Astra
# Date: 2026-09-27 18:14
# PURPOSE: Graft's deterministic geometry, fixed levels, workshop rendering and ARC action adapter; shared transitions also drive its verification scripts.
# SRP/DRY check: Pass — searched existing custom/catalog games; no spatial welding utility exists; one transition owns all rules.
"""Click a piece, move with arrows. Touching pieces weld; fit the orange assembly in its mold."""

from collections import namedtuple
from math import isfinite

import numpy as np
from arcengine import ARCBaseGame, Camera, GameState, Level, RenderableUserDisplay

WIDTH, HEIGHT, CELL, OX, OY = 14, 11, 4, 4, 14
DIRECTIONS = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}
MATERIALS = (12, 9, 10, 14, 15, 3, 8)
State = namedtuple("State", "pieces groups selected alive done feedback pulse pointer")

LEVELS = [
    {"name": "First seam", "pieces": (((3, 5),), ((6, 5), (7, 5))),
     "target": ((8, 5), (9, 5), (10, 5)), "socket": (8, 5),
     "walls": tuple((x, y) for x in range(WIDTH) for y in (4, 6))},
    {"name": "Joining faces", "pieces": (((4, 5), (5, 5)),
      ((4, 1), (5, 1), (5, 2)), ((4, 8),),
      ((1, 4), (1, 5), (1, 6)), ((8, 5), (9, 5), (9, 6)),
      ((0, 1), (1, 1)), ((4, 10), (5, 10)), ((8, 0), (8, 1)), ((0, 9), (1, 9))),
     "target": ((7, 5), (8, 5), (7, 3), (8, 3), (8, 4), (7, 6),
                (7, 7), (8, 7), (6, 4), (6, 5), (6, 6), (9, 5), (10, 5), (10, 6),
                (5, 3), (6, 3), (5, 1), (5, 2), (5, 7), (6, 7)),
     "walls": (), "socket": (7, 5)},
    {"name": "Subassemblies", "pieces": (((4, 5), (4, 6)), ((4, 0), (4, 1)),
      ((0, 4), (0, 5), (1, 5)), ((0, 0), (1, 0)),
      ((9, 5), (10, 5), (10, 6)), ((7, 0), (8, 0), (8, 1)),
      ((4, 10), (5, 10)), ((0, 8), (0, 9)), ((10, 9), (10, 10)),
      ((12, 0), (13, 0), (12, 1), (13, 1))),
     "target": ((6, 5), (6, 6), (6, 3), (6, 4), (4, 4), (4, 5), (5, 5),
                (4, 3), (5, 3), (7, 5), (8, 5), (8, 6), (7, 3), (8, 3),
                (8, 4), (6, 7), (7, 7), (4, 6), (4, 7), (8, 7), (8, 8)),
     "walls": (), "socket": (6, 5)},
]


def initial(level):
    return State(tuple(tuple(p) for p in level["pieces"]),
                 tuple(range(len(level["pieces"]))), -1, True, False, "ready", 0, (3, 5))


def component_cells(state, group):
    return frozenset(cell for index, piece in enumerate(state.pieces)
                     if state.groups[index] == group for cell in piece)


def move_is_clear(level, state, group, action):
    dx, dy = DIRECTIONS[action]
    cells = component_cells(state, group)
    if not cells:
        return False
    moved = frozenset((x + dx, y + dy) for x, y in cells)
    occupied = frozenset(cell for index, piece in enumerate(state.pieces)
                         if state.groups[index] != group for cell in piece)
    return (all(0 <= x < WIDTH and 0 <= y < HEIGHT for x, y in moved)
            and not moved.intersection(occupied) and not moved.intersection(level["walls"]))


def transition(level, state, action, point=None):
    """Move whole components, then weld all edge contacts; only impossible marked joins lose."""
    if not state.alive or state.done:
        return state
    state = state._replace(pulse=1-state.pulse, feedback="refused")
    if action == 6:
        if point is None:
            return state
        state = state._replace(pointer=point)
        for index, piece in enumerate(state.pieces):
            if point in piece:
                return state._replace(selected=state.groups[index], feedback="selected")
        return state
    if action not in DIRECTIONS:
        return state
    selected = state.selected
    if not move_is_clear(level, state, selected, action):
        return state._replace(feedback="blocked")
    dx, dy = DIRECTIONS[action]
    pieces = tuple(tuple((x + dx, y + dy) for x, y in piece)
                   if state.groups[index] == selected else piece
                   for index, piece in enumerate(state.pieces))
    state = state._replace(pieces=pieces, feedback="moved")
    moving = component_cells(state, selected)
    fringe = {(x + sx, y + sy) for x, y in moving for sx, sy in DIRECTIONS.values()}
    touching = {state.groups[index] for index, piece in enumerate(pieces)
                if any(cell in fringe for cell in piece)} | {selected}
    if len(touching) > 1:
        merged = min(touching)
        groups = tuple(merged if group in touching else group for group in state.groups)
        state = state._replace(groups=groups, selected=merged, feedback="welded")
        marked = component_cells(state, groups[0])
        seed_x, seed_y = pieces[0][0]
        socket_x, socket_y = level["socket"]
        # The marked seed registers against the mold's visible orange pin.
        # Its location fixes the translation; an incompatible weld cannot be seated.
        fits = all((x+socket_x-seed_x, y+socket_y-seed_y) in level["target"] for x, y in marked)
        if not fits:
            return state._replace(alive=False, feedback="cracked")
    marked = component_cells(state, state.groups[0])
    return state._replace(done=marked == frozenset(level["target"])
                          and state.pieces[0][0] == level["socket"])


def legal_moves(level, state):
    """All genuinely movable component/direction pairs, used by blind-policy verification."""
    return [(group, action) for group in set(state.groups) for action in DIRECTIONS
            if move_is_clear(level, state, group, action)]


def click_for_group(state, group):
    return min(component_cells(state, group))


class GraftDisplay(RenderableUserDisplay):
    def __init__(self, game):
        self.game = game

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        game, state = self.game, self.game.st
        frame[:, :] = 1
        frame[12:60, 2:62] = 3
        frame[13:59, 3:61] = 0
        frame[OY:OY+HEIGHT*CELL:CELL, OX:OX+WIDTH*CELL:CELL] = 1
        # A permanently visible pictogram: separate materials, touching seam, rigid result.
        frame[3:8, 4:9] = 12
        frame[3:8, 12:17] = 9
        frame[5, 19:24] = 4
        frame[4:7, 23] = 4
        frame[3:8, 27:32] = 12
        frame[3:8, 32:37] = 9
        frame[4:7, 31:33] = 4
        frame[2:10, 46:61] = 4
        frame[3:9, 47:60] = 0
        frame[5:7, 50:57] = 12
        frame[4:8, 53:55] = 12
        # The mold remains visible as engraved hollow cells, never color matching.
        for x, y in game.lvl["target"]:
            px, py = OX+x*CELL, OY+y*CELL
            frame[py:py+CELL, px:px+CELL] = 3
            frame[py+1:py+3, px+1:px+3] = 1
        socket_x, socket_y = game.lvl["socket"]
        frame[OY+socket_y*CELL+1:OY+socket_y*CELL+3,
              OX+socket_x*CELL+1:OX+socket_x*CELL+3] = 12
        for x, y in game.lvl["walls"]:
            px, py = OX+x*CELL, OY+y*CELL
            frame[py:py+CELL, px:px+CELL] = 4
        occupied = {cell: index for index, piece in enumerate(state.pieces) for cell in piece}
        for index, piece in enumerate(state.pieces):
            for x, y in piece:
                px, py = OX+x*CELL, OY+y*CELL
                frame[py:py+CELL, px:px+CELL] = 4
                frame[py+1:py+3, px+1:px+3] = MATERIALS[index % len(MATERIALS)]
                # Solid material bridges make the merged object perceptually explicit.
                for dx, dy in ((1, 0), (0, 1)):
                    neighbor = occupied.get((x+dx, y+dy))
                    if neighbor is not None and state.groups[neighbor] == state.groups[index]:
                        if dx:
                            frame[py+1:py+3, px+3:px+5] = MATERIALS[index % len(MATERIALS)]
                        else:
                            frame[py+3:py+5, px+1:px+3] = MATERIALS[index % len(MATERIALS)]
                if state.groups[index] == state.selected:
                    frame[py, px] = 9 if state.pulse else 4
        # The orange seed's white center identifies the required component after welding.
        seed_x, seed_y = state.pieces[0][0]
        frame[OY+seed_y*CELL+1, OX+seed_x*CELL+1] = 0
        selected = component_cells(state, state.selected)
        left = min((x for x, _ in selected), default=3)*CELL+OX
        top = min((y for _, y in selected), default=5)*CELL+OY
        right = (max((x for x, _ in selected), default=3)+1)*CELL+OX
        bottom = (max((y for _, y in selected), default=5)+1)*CELL+OY
        edge = 8 if state.feedback in ("blocked", "cracked") else 9
        span = 2+state.pulse
        corners = ((left-1, top-1, 1, 1), (right, top-1, -1, 1),
                   (left-1, bottom, 1, -1), (right, bottom, -1, -1)) if selected else ()
        for px, py, sign_x, sign_y in corners:
            for offset in range(span):
                frame[py, px+sign_x*offset] = edge
                frame[py+sign_y*offset, px] = edge
        if state.feedback == "refused" or (not selected and state.feedback == "blocked"):
            px = max(1, min(62, OX+state.pointer[0]*CELL+2))
            py = max(1, min(62, OY+state.pointer[1]*CELL+2))
            frame[py-1:py+2, px] = 8
            frame[py, px-1:px+2] = 8 if state.pulse else 4
        if not state.alive:
            for x, y in game.lvl["target"]:
                px, py = OX+x*CELL, OY+y*CELL
                frame[py, px+1] = frame[py+1, px+2] = frame[py+2, px+1] = 8
        return frame


class Gf01(ARCBaseGame):
    def __init__(self):
        self.lvl, self.st = LEVELS[0], initial(LEVELS[0])
        self.display = GraftDisplay(self)
        levels = [Level(sprites=[], grid_size=(64, 64), data={}, name=level["name"])
                  for level in LEVELS]
        super().__init__("gf01", levels, Camera(0, 0, 64, 64, 1, 1, [self.display]),
                         False, len(levels), [1, 2, 3, 4, 6])

    def on_set_level(self, level):
        self.lvl = LEVELS[self.level_index]
        self.st = initial(self.lvl)

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
