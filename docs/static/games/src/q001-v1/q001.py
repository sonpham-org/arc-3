"""q001 "Quiet Field" -- control motion by controlling observation.

The movable white observer does not push the pieces. Instead, magenta "shy"
pieces advance around their tracks only while occluded, and yellow "bold"
pieces advance only while visible. ACTION1-4 move the observer, ACTION5 emits
one world pulse, and ACTION6 rotates a clicked shutter. A level clears when
every piece is resting in its hollow socket on the same pulse.

The environment is deterministic, turn based, uses no text or cultural symbols,
and teaches one demand at a time across eight levels. The visual grammar is a
continuous dark field with dotted tracks, crescent/star-like moving pieces,
occluding ribbons, and line-of-sight rays; it intentionally avoids the flat
colored tile-maze look common in the imported catalog.
"""

from __future__ import annotations

from copy import deepcopy

import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay


# Frame and board geometry ---------------------------------------------------

CELL = 4
BOARD_W = 12
BOARD_H = 12
OX = 8
OY = 12

# ARC palette indices.
C_WHITE, C_LGRAY, C_GRAY, C_DGRAY, C_VDGRAY, C_BLACK = 0, 1, 2, 3, 4, 5
C_MAGENTA, C_LMAGENTA, C_RED, C_BLUE, C_LBLUE = 6, 7, 8, 9, 10
C_YELLOW, C_ORANGE, C_MAROON, C_GREEN, C_PURPLE = 11, 12, 13, 14, 15

K_SHY = "shy"
K_BOLD = "bold"
KIND_COLOR = {K_SHY: C_MAGENTA, K_BOLD: C_YELLOW}
KIND_CORE = {K_SHY: C_LMAGENTA, K_BOLD: C_ORANGE}

DIRS = {
    1: (0, -1),
    2: (0, 1),
    3: (-1, 0),
    4: (1, 0),
}


def _vwall(x: int, y0: int, y1: int) -> set[tuple[int, int]]:
    return {(x, y) for y in range(y0, y1 + 1)}


def _hwall(y: int, x0: int, x1: int) -> set[tuple[int, int]]:
    return {(x, y) for x in range(x0, x1 + 1)}


def _orb(kind, path, target, *, start=0, flips=()):
    return {
        "kind": kind,
        "path": tuple(path),
        "target": int(target),
        "start": int(start),
        "flips": tuple(int(i) for i in flips),
    }


# Each level adds a demand. Paths are deliberately short enough to read as a
# whole, while later coprime loop lengths and shutters prevent a random pulse
# policy from synchronizing the board reliably.
LEVELS = [
    {
        "name": "Occluded Motion",
        "eye": (2, 2),
        "walls": _vwall(5, 0, 6),
        "shutters": [],
        "orbs": [
            _orb(K_SHY, [(8, 2), (8, 3), (8, 4)], 2),
        ],
        "budget": 18,
    },
    {
        "name": "Observed Motion",
        "eye": (2, 2),
        "walls": set(),
        "shutters": [],
        "orbs": [
            _orb(K_BOLD, [(7, 2), (8, 2), (9, 2), (10, 2)], 3),
        ],
        "budget": 18,
    },
    {
        "name": "Opposite Temperaments",
        "eye": (2, 2),
        "walls": _vwall(6, 0, 5),
        "shutters": [],
        "orbs": [
            _orb(K_SHY, [(9, 2), (9, 3), (9, 4), (8, 4)], 2),
            _orb(K_BOLD, [(3, 8), (4, 8), (5, 8), (5, 9), (4, 9)], 3),
        ],
        "budget": 42,
    },
    {
        "name": "Selective Shadow",
        "eye": (5, 5),
        "walls": _vwall(5, 0, 4) | _vwall(7, 7, 11),
        "shutters": [],
        "orbs": [
            _orb(K_SHY, [(9, 1), (9, 2), (10, 2), (10, 3), (9, 3)], 3),
            _orb(K_SHY, [(9, 9), (8, 9), (8, 10), (9, 10), (10, 10), (10, 9)], 2),
        ],
        "budget": 54,
    },
    {
        "name": "Rotating Veil",
        "eye": (2, 5),
        "walls": _vwall(6, 0, 4) | _vwall(6, 6, 11),
        "shutters": [{"cell": (6, 5), "closed": True}],
        "orbs": [
            _orb(K_SHY, [(9, 3), (10, 3), (10, 4), (9, 4)], 2),
            _orb(K_BOLD, [(9, 7), (10, 7), (10, 8), (9, 8), (8, 8)], 3),
        ],
        "budget": 58,
    },
    {
        "name": "Changed Temperament",
        "eye": (0, 0),
        "walls": _vwall(6, 0, 5),
        "shutters": [],
        "orbs": [
            _orb(
                K_SHY,
                [(9, 2), (9, 3), (9, 4), (8, 4), (8, 3), (8, 2)],
                5,
                flips=(1,),
            ),
        ],
        "budget": 52,
    },
    {
        "name": "Two Veils",
        "eye": (1, 5),
        "walls": (_vwall(5, 0, 3) | _vwall(5, 5, 11)
                  | _vwall(8, 0, 6) | _vwall(8, 8, 11)),
        "shutters": [
            {"cell": (5, 4), "closed": True},
            {"cell": (8, 7), "closed": False},
        ],
        "orbs": [
            _orb(K_SHY, [(10, 1), (10, 2), (11, 2), (11, 3), (10, 3)], 3),
            _orb(K_BOLD, [(6, 7), (6, 8), (7, 8), (7, 9), (6, 9), (6, 10)], 4),
            _orb(K_SHY, [(10, 9), (9, 9), (9, 10), (10, 10), (11, 10), (11, 9), (10, 8)], 5),
        ],
        "budget": 76,
    },
    {
        "name": "Quiet Field",
        "eye": (1, 6),
        "walls": (_vwall(4, 0, 4) | _vwall(4, 6, 11)
                  | _vwall(8, 0, 2) | _vwall(8, 4, 8) | _vwall(8, 10, 11)
                  | _hwall(6, 5, 7)),
        "shutters": [
            {"cell": (4, 5), "closed": True},
            {"cell": (8, 3), "closed": False},
            {"cell": (8, 9), "closed": True},
        ],
        "orbs": [
            _orb(K_SHY, [(10, 1), (11, 1), (11, 2), (10, 2), (9, 2)], 3),
            _orb(K_BOLD, [(6, 2), (7, 2), (7, 3), (6, 3), (5, 3), (5, 2)], 4),
            _orb(K_SHY, [(10, 7), (11, 7), (11, 8), (10, 8), (9, 8), (9, 7), (10, 6)], 5,
                 flips=(2,)),
            _orb(K_BOLD, [(6, 9), (7, 9), (7, 10), (6, 10), (5, 10), (5, 9), (6, 8), (7, 8)], 6),
        ],
        "budget": 110,
    },
]


def _bresenham(a: tuple[int, int], b: tuple[int, int]):
    """Yield grid cells on the segment, including endpoints."""
    x0, y0 = a
    x1, y1 = b
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        yield x0, y0
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


class QuietFieldDisplay(RenderableUserDisplay):
    def __init__(self, game):
        self.game = game

    @staticmethod
    def _cell_px(cell):
        x, y = cell
        return OX + x * CELL, OY + y * CELL

    def _cell_fill(self, frame, cell, color):
        px, py = self._cell_px(cell)
        frame[py:py + CELL, px:px + CELL] = color

    def _draw_track(self, frame, path):
        # Tracks are dotted threads rather than colored tiles. Consecutive path
        # cells are Manhattan-adjacent in authored levels.
        centers = []
        for cell in path:
            px, py = self._cell_px(cell)
            centers.append((px + 1, py + 1))
            frame[py + 1:py + 3, px + 1:px + 3] = C_DGRAY
        for (ax, ay), (bx, by) in zip(centers, centers[1:] + centers[:1]):
            steps = max(abs(ax - bx), abs(ay - by), 1)
            for i in range(steps + 1):
                x = ax + (bx - ax) * i // steps
                y = ay + (by - ay) * i // steps
                if i % 2 == 0 and 0 <= x < 64 and 0 <= y < 64:
                    frame[y, x] = C_GRAY

    def _draw_socket(self, frame, cell):
        px, py = self._cell_px(cell)
        frame[py:py + CELL, px:px + CELL] = C_GREEN
        frame[py + 1:py + 3, px + 1:px + 3] = C_BLACK

    def _draw_orb(self, frame, orb):
        px, py = self._cell_px(orb["path"][orb["index"]])
        color = KIND_COLOR[orb["kind"]]
        core = KIND_CORE[orb["kind"]]
        frame[py:py + CELL, px:px + CELL] = C_BLACK
        if orb["kind"] == K_SHY:
            # Crescent: visually asymmetric but not a familiar semantic icon.
            frame[py:py + CELL, px:px + 3] = color
            frame[py + 1:py + 3, px + 1:px + 3] = C_BLACK
            frame[py + 1, px] = core
        else:
            # Radial burst: distinct from the crescent even under grayscale.
            frame[py + 1:py + 3, px:px + CELL] = color
            frame[py:py + CELL, px + 1:px + 3] = color
            frame[py + 1:py + 3, px + 1:px + 3] = core

    def _draw_eye(self, frame):
        px, py = self._cell_px(self.game.eye)
        frame[py:py + CELL, px:px + CELL] = C_BLACK
        frame[py, px + 1:px + 3] = C_WHITE
        frame[py + 1:py + 3, px:px + CELL] = C_WHITE
        frame[py + 3, px + 1:px + 3] = C_WHITE
        frame[py + 1:py + 3, px + 1:px + 3] = C_BLUE

    def _draw_wall(self, frame, cell):
        px, py = self._cell_px(cell)
        frame[py:py + CELL, px:px + CELL] = C_MAROON
        frame[py, px:px + CELL] = C_ORANGE
        frame[py + 2, px + 1:px + CELL] = C_RED

    def _draw_shutter(self, frame, shutter):
        px, py = self._cell_px(shutter["cell"])
        frame[py:py + CELL, px:px + CELL] = C_VDGRAY
        if shutter["closed"]:
            frame[py:py + CELL, px + 1:px + 3] = C_LBLUE
            frame[py, px] = C_WHITE
            frame[py + 3, px + 3] = C_WHITE
        else:
            frame[py + 1:py + 3, px:px + CELL] = C_LBLUE
            frame[py, px + 3] = C_WHITE
            frame[py + 3, px] = C_WHITE

    def _draw_visibility(self, frame):
        # A sparse ray makes the causal observation relation legible without
        # flooding the board or giving away future movement.
        for orb in self.game.orbs:
            pos = orb["path"][orb["index"]]
            if not self.game.is_visible(pos):
                continue
            cells = list(_bresenham(self.game.eye, pos))
            for i, cell in enumerate(cells[1:-1], 1):
                if i % 2:
                    px, py = self._cell_px(cell)
                    frame[py + 2, px + 2] = C_BLUE

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        game = self.game
        frame[:, :] = C_BLACK

        # Continuous field: subtle stipple, no tile outlines.
        frame[OY:OY + BOARD_H * CELL, OX:OX + BOARD_W * CELL] = C_VDGRAY
        frame[OY + 1:OY + BOARD_H * CELL:4, OX + 1:OX + BOARD_W * CELL:4] = C_DGRAY

        for orb in game.orbs:
            self._draw_track(frame, orb["path"])
            self._draw_socket(frame, orb["path"][orb["target"]])

        for wall in game.walls:
            self._draw_wall(frame, wall)
        for shutter in game.shutters:
            self._draw_shutter(frame, shutter)

        self._draw_visibility(frame)
        for orb in game.orbs:
            self._draw_orb(frame, orb)
        self._draw_eye(frame)

        # Pulse/action budget as paired side rails. No digits or text.
        frame[2:10, 1:3] = C_DGRAY
        frame[2:10, 61:63] = C_DGRAY
        ratio = 0.0 if game.budget_max <= 0 else game.budget_left / game.budget_max
        filled = max(0, min(8, int(round(8 * ratio))))
        if filled:
            color = C_LBLUE if ratio > 0.25 else C_RED
            frame[10 - filled:10, 1:3] = color
            frame[10 - filled:10, 61:63] = color

        # Current pulse emits a brief horizontal glint in the HUD.
        if game.pulse_flash:
            frame[5:7, 5:59] = C_LGRAY

        return frame


class Q001(ARCBaseGame):
    def __init__(self):
        self.display = QuietFieldDisplay(self)
        self.eye = (0, 0)
        self.walls = set()
        self.shutters = []
        self.orbs = []
        self.budget_max = 0
        self.budget_left = 0
        self.pulse_flash = False

        levels = [
            Level(sprites=[], grid_size=(64, 64), data=deepcopy(spec), name=spec["name"])
            for spec in LEVELS
        ]
        super().__init__(
            "q001",
            levels,
            Camera(0, 0, 64, 64, C_BLACK, C_BLACK, [self.display]),
            False,
            len(levels),
            [1, 2, 3, 4, 5, 6],
        )

    def on_set_level(self, level: Level) -> None:
        spec = LEVELS[self.level_index]
        self.eye = tuple(spec["eye"])
        self.walls = set(spec["walls"])
        self.shutters = deepcopy(spec["shutters"])
        self.orbs = []
        for authored in spec["orbs"]:
            orb = deepcopy(authored)
            orb["index"] = orb.pop("start")
            self.orbs.append(orb)
        self.budget_max = self.budget_left = int(spec["budget"])
        self.pulse_flash = False

    def _opaque_cells(self) -> set[tuple[int, int]]:
        return self.walls | {
            tuple(shutter["cell"])
            for shutter in self.shutters
            if shutter["closed"]
        }

    def is_visible(self, cell: tuple[int, int]) -> bool:
        opaque = self._opaque_cells()
        for between in list(_bresenham(self.eye, cell))[1:-1]:
            if between in opaque:
                return False
        return True

    def _move_eye(self, aid: int) -> None:
        dx, dy = DIRS[aid]
        x = max(0, min(BOARD_W - 1, self.eye[0] + dx))
        y = max(0, min(BOARD_H - 1, self.eye[1] + dy))
        self.eye = (x, y)

    @staticmethod
    def _display_to_cell(x: int, y: int):
        if not (OX <= x < OX + BOARD_W * CELL and OY <= y < OY + BOARD_H * CELL):
            return None
        return (x - OX) // CELL, (y - OY) // CELL

    def _toggle_shutter(self, x: int, y: int) -> None:
        cell = self._display_to_cell(x, y)
        if cell is None:
            return
        for shutter in self.shutters:
            if tuple(shutter["cell"]) == cell:
                shutter["closed"] = not shutter["closed"]
                return

    def _pulse(self) -> None:
        visible_before = [self.is_visible(orb["path"][orb["index"]]) for orb in self.orbs]
        for orb, visible in zip(self.orbs, visible_before):
            active = (orb["kind"] == K_BOLD and visible) or (
                orb["kind"] == K_SHY and not visible
            )
            if not active:
                continue
            orb["index"] = (orb["index"] + 1) % len(orb["path"])
            if orb["index"] in orb["flips"]:
                orb["kind"] = K_BOLD if orb["kind"] == K_SHY else K_SHY

    def _is_solved(self) -> bool:
        return all(orb["index"] == orb["target"] for orb in self.orbs)

    def step(self) -> None:
        aid = self.action.id.value
        self.pulse_flash = False

        if aid in DIRS:
            self._move_eye(aid)
        elif aid == 5:
            self.pulse_flash = True
            self._pulse()
        elif aid == 6:
            self._toggle_shutter(
                int(self.action.data.get("x", 0)),
                int(self.action.data.get("y", 0)),
            )

        self.budget_left -= 1

        if self._is_solved():
            self.next_level()
        elif self.budget_left <= 0:
            self.budget_left = 0
            self.lose()

        self.complete_action()
