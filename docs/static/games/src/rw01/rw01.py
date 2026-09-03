# Author: Claude Opus 5
# Date: 2026-08-27 09:10
# PURPOSE: rw01 "Rewind" -- an ARC-AGI-3 environment built to make RESET a planning verb
#   instead of a surrender. The floor falls away behind the walker, so a run can never be
#   retraced; RESET is the only way back to the pad. What RESET restores is the *terrain*
#   (walker position, fallen tiles). What it deliberately does NOT restore is the state the
#   walker changed on purpose: lit beacons, sealed doors, tiles broken for good, and the pad
#   itself once an anchor has claimed it. So the only winning shape is: light something now,
#   rewind, spend it later. Every level past the tutorial is unreachable in a single run --
#   proved exhaustively over self-avoiding walks in smoke_test.py.
#   Core-knowledge priors only: objectness, topology, agentness. No text, no glyphs, no
#   numbers, no bars, no pips -- affordances are colours and the meter is the walker's body.
# SRP/DRY check: Pass -- self-contained environment. Nothing in the ~300-game catalogue
#   carries state across a RESET, so there is no prior art to reuse.
"""Rewind -- the floor falls behind you; rewinding is how you get back.

ACTION1/2/3/4 step up/down/left/right, ACTION6 clicks an adjacent tile to step onto it,
ACTION0 (RESET) rewinds the level. Rewinding restores the tiles and puts the walker back on
the pad, but everything the walker deliberately switched stays switched.

7 levels. No RNG. Lose by running the meter out, or by breaking the level beyond repair.
"""

from itertools import permutations as _permutations

import numpy as np
from arcengine import ARCBaseGame, Camera, GameState, Level, RenderableUserDisplay

# ---------------------------------------------------------------------------
# Palette (ARC-3 indices)
# ---------------------------------------------------------------------------

C_WHITE, C_LGRAY, C_GRAY, C_DGRAY, C_VDGRAY, C_BLACK = 0, 1, 2, 3, 4, 5
C_MAGENTA, C_LMAGENTA, C_RED, C_BLUE, C_LBLUE = 6, 7, 8, 9, 10
C_YELLOW, C_ORANGE, C_MAROON, C_GREEN, C_PURPLE = 11, 12, 13, 14, 15

C_FLOOR = C_MAROON        # a tile you can stand on (maroon: 0.0% of official pixels)
C_WALL = C_GRAY           # never passable, never changes
C_VOID = C_BLACK          # fell away this run -- comes back on a rewind
C_SCAR = C_DGRAY          # fell away for good -- ashen, and NOT the floor's colour
C_BRITTLE = C_ORANGE      # a tile that will scar instead of falling
C_PAD = C_LBLUE           # where a rewind puts the walker
C_GOAL = C_GREEN

# Four keyed colours. A beacon lights its colour; a door of that colour opens.
# Blue, not purple: purple is now the void behind the board, and a key drawn in the
# background's colour is invisible.
KEY_COLORS = (C_BLUE, C_YELLOW, C_MAGENTA, C_RED)

# ---------------------------------------------------------------------------
# Board geometry -- 9x8 tiles of 7px fills 63x56 of the 64x64 frame. Rows 0-7 are an inert
# band of field colour (the HUD that used to live there is gone). The origin stays at OY = 8
# because step() hit-tests clicks with the same OX/OY/CELL, and the game logic is frozen.
# ---------------------------------------------------------------------------

GRID_W, GRID_H = 9, 8
CELL = 7
OX, OY = 0, 8

# The walker IS the meter. It is a 5x5 figure with the corners knocked off -- 21 pixels
# inside the tile body -- and it fades as the meter drains: ceil(21 * left / max) of these
# pixels are lit, taken from the front of this tuple. The order walks a 2x2 Bayer tiling
# class by class, so holes open evenly across the figure instead of eating it from one
# side. The centre never drops, and the inner diagonals outlive the edge-mids so the last
# survivors form an X on the tile's body rather than lying along a lit beacon's white
# cross. Offsets are (dx, dy) inside the 5x5 body.
WALKER_PIXELS = (
    (2, 2),                                                  # the core: never drops
    (1, 1), (3, 3), (3, 1), (1, 3),                          # bayer 1: inner diagonals
    (0, 2), (4, 2), (2, 0), (2, 4),                          # bayer 0: edge-mids
    (1, 2), (3, 2), (1, 0), (3, 4), (3, 0), (1, 4),          # bayer 2
    (2, 1), (2, 3), (0, 1), (4, 3), (4, 1), (0, 3),          # bayer 3
)
C_WALKER = C_WHITE
# The final quarter of the meter: the thinning figure turns light magenta. Unused anywhere
# else on the board, and it still reads on the pad, the floor and a lit lamp's white cross,
# where a grey or white scatter of five pixels would not.
C_WALKER_LOW = C_LMAGENTA

DIRS = ((0, -1), (0, 1), (-1, 0), (1, 0))          # ACTION1..4 = up/down/left/right
DIR_OF_ACTION = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}

MOVE_COST = 1
RESET_COST = 2

# ---------------------------------------------------------------------------
# Map alphabet
# ---------------------------------------------------------------------------

WALL, FLOOR, BRITTLE, START, GOAL, ANCHOR = "#", ".", "~", "S", "G", "P"
BEACONS = {"A": 0, "B": 1, "C": 2, "D": 3}         # lights that colour, for good
GATES = {"a": 0, "b": 1, "c": 2, "d": 3}           # open only while that colour is lit

# ---------------------------------------------------------------------------
# Levels. Each map is GRID_H rows of GRID_W characters.
#
# The shape every level past the tutorial is built on: a spine with dead-end teeth.
# Stepping off a tile drops it, so once a run leaves the spine it is committed to one
# tooth and cannot come back -- one errand per run, and the only way to start another
# errand is to rewind. `latches` names the tiles that light one colour and wall a door of
# another shut permanently, so the order errands are run in becomes load-bearing.
# ---------------------------------------------------------------------------

LEVELS = [
    {
        # NEW: the floor falls behind you; a lit beacon survives the rewind and its door
        # stays open. The pad has exactly one legal exit, and that exit is a dead end, so
        # the lesson cannot be walked around.
        "name": "Rewind",
        "budget": 40,
        "map": ("#########",
                "#.......#",
                "#.......#",
                "#...G...#",
                "#.......#",
                "#...a...#",
                "####S####",
                "####A####"),
    },
    {
        # NEW: two beacons, and the door pair on the goal tooth needs both. One tooth per
        # run means the answer is two rewinds, not a cleverer path.
        "name": "Two Keys",
        "budget": 66,
        "map": ("#A#G#.#B#",
                "#.#a#.#.#",
                "#.#b#.#.#",
                "#.#.#.#.#",
                "#.#.#.#.#",
                "#.#.#.#.#",
                "#...S...#",
                "#########"),
    },
    {
        # NEW: a beacon parked behind another beacon's door, so the errands acquire an
        # order. Comb inverted so the shape has to be re-read, not recognised.
        "name": "Nested",
        "budget": 66,
        "map": ("#########",
                "#...S...#",
                "#.#.#.#a#",
                "#.#.#.#.#",
                "#.#b#.#.#",
                "#.#.#.#.#",
                "#.#.#.#.#",
                "#A#G#.#B#"),
    },
    {
        # NEW: brittle tiles. They scar instead of falling, and a scar survives the rewind
        # too -- persistence cuts both ways. The single brittle tile is the only way to the
        # far tooth, so that errand gets exactly one attempt in the whole level: step off
        # the bridge and rewind without finishing, and the level is over. Nesting stays
        # live -- the far beacon is behind the near beacon's door, so the order is forced
        # and a run wasted on the bridge is a run wasted on the only thing behind it.
        "name": "Brittle",
        "budget": 70,
        "map": ("#########",
                "#......A#",
                "#.#######",
                "#S#######",
                "#.#######",
                "#..a.b.G#",
                "#~#######",
                "#..a...B#"),
    },
    {
        # NEW: a latch -- lights one colour and walls a door of another colour shut for
        # good. It sits the same distance from the pad as the first beacon, so pulling it
        # early is the natural move and it strands the beacon behind the door it seals.
        "name": "Latch",
        "budget": 85,
        "map": ("#A#B#G#X#",
                "#.#.#c#.#",
                "#.#.#b#.#",
                "#.#a#.#.#",
                "#.#.#.#.#",
                "#.#.#.#.#",
                "#...S...#",
                "#########"),
        "latches": {"X": (2, 0)},          # lights magenta, seals purple
    },
    {
        # NEW: an anchor. Standing on one moves the pad there, and that move survives the
        # rewind -- the walker can aim where a rewind drops it. The anchor sits on the
        # spine past the brittle tile, so the rule demonstrates itself: the next rewind
        # lands somewhere new. Cross before lighting the near beacon and the level is
        # already lost.
        "name": "Anchor",
        "budget": 62,
        "map": ("#########",
                "#A###B#G#",
                "#.###.#b#",
                "#.###.#.#",
                "#.###a#.#",
                "#.###.#.#",
                "#S~~P...#",
                "#########"),
    },
    {
        # Everything at once, and this time nothing is on the road. The anchor is a
        # dead-end tooth, so crossing the brittle tile without spending that run on it
        # strands the walker on the far side forever. The latch is the nearest thing to the
        # pad -- three steps -- and pulling it first seals the door the second beacon sits
        # behind. Both mistakes are terminal, and both are the obvious move.
        "name": "Gauntlet",
        "budget": 110,
        "map": ("#A#B#P#D#",
                "#.#.#.#.#",
                "#.#a#.#c#",
                "#.#.#.#.#",
                "#S..~...#",
                "#.#.#.#d#",
                "#.#.#.#b#",
                "#X#.#.#G#"),
        "latches": {"X": (2, 0)},          # lights magenta, seals purple
    },
]


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

class Rw01Display(RenderableUserDisplay):
    """Every tile is repainted from what it currently affords, every frame.

    The whole vocabulary is solid-versus-hollow: a solid tile can be stood on, a hollow or
    empty one cannot. A door is a solid slab while shut and a pair of jambs once open. A
    beacon is an empty socket until it is lit, then a filled lamp with a white cross.

    There is no HUD. The meter is the walker itself: solid at full, dithered away pixel by
    pixel as it drains, a scatter of dots near the end. Nothing else counts anything.
    """

    def __init__(self, game):
        self.game = game

    # -- primitives ---------------------------------------------------------

    @staticmethod
    def _fill(frame, px, py, color):
        frame[py:py + CELL, px:px + CELL] = color

    @staticmethod
    def _tile(frame, px, py, color):
        """The 5x5 body of a tile -- leaves a 1px black gutter so the grid stays readable."""
        frame[py + 1:py + 6, px + 1:px + 6] = color

    @staticmethod
    def _ring(frame, px, py, color):
        frame[py + 1, px + 1:px + 6] = color
        frame[py + 5, px + 1:px + 6] = color
        frame[py + 1:py + 6, px + 1] = color
        frame[py + 1:py + 6, px + 5] = color

    @staticmethod
    def _cross(frame, px, py, color):
        frame[py + 3, px + 1:px + 6] = color
        frame[py + 1:py + 6, px + 3] = color

    @staticmethod
    def _corners(frame, px, py, color):
        for dy in (0, 6):
            for dx in (0, 6):
                frame[py + dy, px + dx] = color

    # -- one tile -----------------------------------------------------------

    def _draw_cell(self, frame, g, c, r):
        px, py = OX + c * CELL, OY + r * CELL
        ch = g.grid[r][c]
        cell = (c, r)

        if ch == WALL:
            self._fill(frame, px, py, C_WALL)
            return
        # When the walker has nowhere left to go, the pad lights up white -- including
        # when it has fallen away, because a rewind is exactly what brings it back.
        if cell == g.spawn and g.stuck:
            if cell in g.void or cell in g.scars:
                self._ring(frame, px, py, C_WHITE)
            else:
                self._tile(frame, px, py, C_WHITE)
            return
        if cell in g.scars:
            self._ring(frame, px, py, C_SCAR)          # hollow: gone for good
            return
        if cell in g.void:
            return                                     # black: gone until the rewind
        if ch in GATES:
            k = GATES[ch]
            if k in g.sealed:
                self._fill(frame, px, py, C_WALL)      # walled into the wall, colour kept
                self._ring(frame, px, py, KEY_COLORS[k])
                frame[py + 2:py + 5, px + 2:px + 5] = C_SCAR
            elif k in g.armed:
                frame[py, px:px + CELL] = KEY_COLORS[k]
                frame[py + 6, px:px + CELL] = KEY_COLORS[k]
                frame[py + 2:py + 5, px + 1:px + 6] = C_FLOOR
            else:
                self._fill(frame, px, py, KEY_COLORS[k])
            return
        if ch in BEACONS:
            k = BEACONS[ch]
            if k in g.armed:
                self._tile(frame, px, py, KEY_COLORS[k])
                self._cross(frame, px, py, C_WHITE)
            else:
                self._cross(frame, px, py, KEY_COLORS[k])
            return
        if ch in g.latch_spec:
            opens, seals = g.latch_spec[ch]
            if cell in g.used_latches:
                self._tile(frame, px, py, KEY_COLORS[opens])
                self._cross(frame, px, py, C_WHITE)
            else:
                self._cross(frame, px, py, KEY_COLORS[opens])
            self._corners(frame, px, py, KEY_COLORS[seals])
            return
        if ch == GOAL:
            self._tile(frame, px, py, C_GOAL)
            frame[py + 3, px + 3] = C_WHITE
            return
        if cell == g.spawn:                            # the stuck/white case is handled above
            self._tile(frame, px, py, C_PAD)
            return
        if ch == ANCHOR and cell not in g.claimed:
            self._tile(frame, px, py, C_PAD)
            frame[py + 2:py + 5, px + 2:px + 5] = C_BLACK   # hollow core: not the pad yet
            return
        if ch == BRITTLE:
            self._tile(frame, px, py, C_BRITTLE)
            return
        self._tile(frame, px, py, C_FLOOR)

    # -- the walker ---------------------------------------------------------

    def _draw_walker(self, frame, g):
        """The walker is the meter, drawn over whatever it stands on.

        ceil(21 * left / max) of WALKER_PIXELS are lit, in order, so the figure is solid at
        full meter and thins evenly as the meter drains; the centre never drops, so the
        walker can still be found at one unit left. In the final quarter it turns pink.
        A stuck walker (every neighbour wall, void or a shut door) keeps its hollow centre
        -- at which point the pad turns white as well -- unless the centre is all it has.
        """
        wx, wy = OX + g.pos[0] * CELL, OY + g.pos[1] * CELL
        total = len(WALKER_PIXELS)
        lit = 1
        if g.budget_max > 0 and g.budget_left > 0:
            lit = min(total, max(1, -(-(total * g.budget_left) // g.budget_max)))
        colour = C_WALKER if g.budget_left * 4 > g.budget_max else C_WALKER_LOW
        for dx, dy in WALKER_PIXELS[:lit]:
            frame[wy + 1 + dy, wx + 1 + dx] = colour
        if g.stuck and lit > 1:
            frame[wy + 3, wx + 3] = C_BLACK

    # -- frame --------------------------------------------------------------

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game
        # Palette: the corpus is 60.3% greyscale. Purple void, maroon floor -- both are
        # near-absent from the catalogue. The void must stay clearly "not floor", since a
        # fallen tile becoming void is the core feedback of this game. Rows 0-7 stay field
        # colour: no bar, no pips. The meter is the walker, and the board already shows
        # every lit colour (beacon filled, its doors open), every sealed door (walled up,
        # ringed in its colour) and every scar (hollow ring) where it happened.
        frame[:, :] = C_PURPLE

        for r in range(GRID_H):
            for c in range(GRID_W):
                self._draw_cell(frame, g, c, r)

        self._draw_walker(frame, g)
        return frame


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class Rw01(ARCBaseGame):
    def __init__(self):
        self.display = Rw01Display(self)

        # on_set_level() runs inside super().__init__(), so every attribute it touches --
        # and every attribute the display reads -- has to exist first.
        self.grid = LEVELS[0]["map"]
        self.latch_spec = {}
        self.pos = (0, 0)
        self.spawn = (0, 0)
        self.void = set()
        self.scars = set()
        self.armed = set()
        self.sealed = set()
        self.used_latches = set()
        self.claimed = set()
        self.keys_used = ()
        self.brittle_cells = ()
        self.latch_cells = ()
        self.goal_cell = (0, 0)
        self.budget_max = 0
        self.budget_left = 0
        self.stuck = False
        self._persist_level = -1
        self._win_cache = {}

        levels = [Level(sprites=[], grid_size=(64, 64), data=ldef, name=ldef["name"])
                  for ldef in LEVELS]

        super().__init__(
            "rw",
            levels,
            Camera(0, 0, 64, 64, C_PURPLE, C_PURPLE, [self.display]),
            False,
            len(levels),
            [0, 1, 2, 3, 4, 6],      # 0 = rewind, 1-4 = step, 6 = click an adjacent tile
        )

    # -- level setup --------------------------------------------------------

    def on_set_level(self, level: Level) -> None:
        """Rebuild the run, keep the record.

        This is the hinge the whole game turns on. The engine calls it for a new level AND
        for every RESET, so it is the one place that decides what a rewind costs the
        player. Terrain (walker, fallen tiles) is rebuilt every time. The record the
        player deliberately wrote -- lit colours, sealed doors, scars, where the pad is,
        and the meter -- is only rebuilt when the level actually changes, or when a lost
        game is being restarted from scratch.
        """
        ldef = LEVELS[self.level_index]
        self.grid = ldef["map"]
        self.latch_spec = ldef.get("latches", {})

        cells = [(c, r) for r in range(GRID_H) for c in range(GRID_W)]
        self.brittle_cells = tuple(x for x in cells if self.grid[x[1]][x[0]] == BRITTLE)
        self.latch_cells = tuple(x for x in cells if self.grid[x[1]][x[0]] in self.latch_spec)
        self.goal_cell = next(x for x in cells if self.grid[x[1]][x[0]] == GOAL)
        keys = set()
        for c, r in cells:
            ch = self.grid[r][c]
            if ch in GATES:
                keys.add(GATES[ch])
            elif ch in BEACONS:
                keys.add(BEACONS[ch])
            elif ch in self.latch_spec:
                keys.update(self.latch_spec[ch])
        self.keys_used = tuple(sorted(keys))

        restarting = self._state in (GameState.NOT_PLAYED, GameState.GAME_OVER,
                                     GameState.WIN)
        if self._persist_level != self.level_index or restarting:
            self.armed = set()
            self.sealed = set()
            self.used_latches = set()
            self.claimed = set()
            self.scars = set()
            self.spawn = next(x for x in cells if self.grid[x[1]][x[0]] == START)
            self.budget_max = self.budget_left = ldef["budget"]
            self._persist_level = self.level_index

        self.pos = self.spawn
        self.void = set()
        self._win_cache = {}
        self._refresh_stuck()

    def handle_reset(self) -> None:
        """A rewind is always a level rewind once play has started.

        The base class promotes a RESET to a full restart whenever `_action_count == 0`,
        and `_action_count` is zeroed by every level load -- so two rewinds in a row would
        throw the player back to level 1 with the score cleared. In a game whose central
        verb is RESET that is not an edge case, it is the main line.
        """
        if self._state in (GameState.NOT_PLAYED, GameState.WIN):
            self.full_reset()
        else:
            self.level_reset()

    # -- terrain ------------------------------------------------------------

    def _passable(self, cell, armed, sealed, scars, void=()):
        c, r = cell
        if not (0 <= c < GRID_W and 0 <= r < GRID_H):
            return False
        ch = self.grid[r][c]
        if ch == WALL or cell in scars or cell in void:
            return False
        if ch in GATES:
            k = GATES[ch]
            return k in armed and k not in sealed
        return True

    def _refresh_stuck(self):
        self.stuck = not any(
            self._passable((self.pos[0] + dx, self.pos[1] + dy),
                           self.armed, self.sealed, self.scars, self.void)
            for dx, dy in DIRS)

    def _enter(self, cell):
        """Apply whatever the tile does. Everything here is written to the record, which
        is exactly the state a rewind will not undo."""
        ch = self.grid[cell[1]][cell[0]]
        if ch in BEACONS:
            self.armed.add(BEACONS[ch])
        elif ch in self.latch_spec and cell not in self.used_latches:
            opens, seals = self.latch_spec[ch]
            self.armed.add(opens)
            self.sealed.add(seals)
            self.used_latches.add(cell)
        elif ch == ANCHOR:
            self.spawn = cell
            self.claimed.add(cell)

    def _try_move(self, cell):
        """Step onto an orthogonally adjacent tile. The tile left behind falls away --
        permanently if it was brittle."""
        c, r = cell
        if abs(c - self.pos[0]) + abs(r - self.pos[1]) != 1:
            return
        if not self._passable(cell, self.armed, self.sealed, self.scars, self.void):
            return
        left = self.pos
        self.void.add(left)
        if self.grid[left[1]][left[0]] == BRITTLE:
            self.scars.add(left)
        self.pos = cell
        self._enter(cell)

    # -- can this level still be finished? ----------------------------------

    def _reach(self, sources, armed, sealed):
        seen = set(sources)
        stack = list(seen)
        while stack:
            c, r = stack.pop()
            for dx, dy in DIRS:
                nxt = (c + dx, r + dy)
                if nxt not in seen and self._passable(nxt, armed, sealed, self.scars):
                    seen.add(nxt)
                    stack.append(nxt)
        return seen

    def _close(self, sources, armed, sealed):
        """Light every beacon the walker can still get to, then look again -- an opened
        door may expose another beacon. Mutates `armed`; returns the final reachable set."""
        reach = self._reach(sources, armed, sealed)
        for _ in range(len(KEY_COLORS) + 1):
            fresh = {BEACONS[self.grid[r][c]] for c, r in reach
                     if self.grid[r][c] in BEACONS} - armed
            if not fresh:
                break
            armed |= fresh
            reach = self._reach(sources, armed, sealed)
        return reach

    def _winnable(self):
        """An optimistic reachability closure over the permanent record.

        Deliberately generous: it ignores the tiles that fell this run and lets the walker
        travel from either the pad or its current tile, because a rewind restores the one
        and the current run still owns the other. So it can only ever be too kind -- it
        never calls a live level dead. What it does catch is the terminal case: a scar or a
        sealed door has cut the last route to the goal, and no ordering of the remaining
        errands puts it back. That ends the level immediately instead of leaving the player
        to spend the meter on a board that cannot be finished.

        Latches are the one thing that has to be searched rather than closed over, because
        pulling one takes passability away. Sealing late always dominates sealing early, so
        each candidate strategy is "light everything reachable, pull the next latch, repeat"
        and the search runs over the ordered sequences of latches -- five of them at most.
        """
        key = (self.pos, self.spawn, frozenset(self.armed), frozenset(self.sealed),
               frozenset(self.scars), frozenset(self.used_latches))
        cached = self._win_cache.get(key)
        if cached is not None:
            return cached

        open_latches = [x for x in self.latch_cells if x not in self.used_latches]
        sources = (self.pos, self.spawn)
        orders = [()]
        for k in range(1, len(open_latches) + 1):
            orders.extend(_permutations(open_latches, k))

        result = False
        for order in orders:
            armed = set(self.armed)
            sealed = set(self.sealed)
            reach = self._close(sources, armed, sealed)
            usable = True
            for cell in order:
                if cell not in reach:
                    usable = False
                    break
                opens, seals = self.latch_spec[self.grid[cell[1]][cell[0]]]
                armed.add(opens)
                sealed.add(seals)
                reach = self._close(sources, armed, sealed)
            if usable and self.goal_cell in reach:
                result = True
                break
        self._win_cache[key] = result
        return result

    # -- engine entry point -------------------------------------------------

    def step(self) -> None:
        aid = self.action.id.value

        if aid == 0:
            # handle_reset() has already rebuilt the run around this action; all that is
            # left is to charge for it. Rewinding is a move, not a mulligan.
            self.budget_left -= RESET_COST
        elif aid in DIR_OF_ACTION:
            self.budget_left -= MOVE_COST
            dx, dy = DIR_OF_ACTION[aid]
            self._try_move((self.pos[0] + dx, self.pos[1] + dy))
        elif aid == 6:
            self.budget_left -= MOVE_COST
            x = int(self.action.data.get("x", -1))
            y = int(self.action.data.get("y", -1))
            c, r = (x - OX) // CELL, (y - OY) // CELL
            if 0 <= c < GRID_W and 0 <= r < GRID_H and y >= OY:
                self._try_move((c, r))
        else:
            self.budget_left -= MOVE_COST

        self._refresh_stuck()

        if self.pos == self.goal_cell:
            self.next_level()
            self.complete_action()
            return

        if self.budget_left <= 0 or not self._winnable():
            self.budget_left = max(0, self.budget_left)
            self.lose()

        self.complete_action()
