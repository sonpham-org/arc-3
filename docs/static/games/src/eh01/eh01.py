# Author: Claude Opus 5
# Date: 2026-09-12 09:40
# PURPOSE: eh01 "Echo" -- an ARC-AGI-3 environment in which UNDO is the only sense organ.
#   The corridor's shape is lit, but what lies IN each cell is dark -- and a dark cell is DRAWN
#   dark: a purple field under a grey stipple that reads as static, next to the flat pink of a
#   cell you have lit. Walking into a cell tells you nothing; pressing UNDO (ACTION7) retreats
#   one cell and permanently lights the cell you just left. The retreat lands on a cell that
#   pays for it: every corridor cell can absorb two retreats, then it scars and is closed
#   forever -- and a retreat off ground you have ALREADY lit showed you nothing, so it burns
#   two marks instead of one. Looking is therefore rationed by geometry: a junction is the only
#   vantage for its own arms, so a crossroads can be inspected exactly twice before it seals
#   under you. Holes are only dangerous while unlit: walking on THROUGH an unlit hole drops you
#   back to the entrance and turns that cell into rock; a lit hole is simply a wall you walk
#   around. Keys are taken by lighting them; the ring out opens when the last key is in, and it
#   too must be seen before it can be entered. There is no budget, no lives, no counter and no
#   HUD: the afterimages and the scars are the entire display of state, and the loss is purely
#   topological -- ground you can no longer reach caves back into the rock the moment the way is
#   cut, and a wing you have finished caves in BEFORE you can step into it.
#   Core-knowledge priors only: objectness, topology, agentness.
# SRP/DRY check: Pass -- self-contained environment. Nothing in the catalogue spends a
#   look-budget through an undo stack, so there is no prior art to reuse; the rule functions
#   here are imported by smoke_test.py and random_gate.py rather than duplicated.
"""Echo -- undo is how you see.

ACTION1/2/3/4 walk up/down/left/right. ACTION7 (UNDO) steps back the way you just came and
permanently lights the cell you just left, showing floor, hole, key or ring. The cell you
retreat ONTO pays one of its two marks -- two, if the cell you retreated off was already lit
and the look showed you nothing. At zero marks a cell scars: you may step off it, never back
onto it. Walking forward off an unlit cell resolves it the hard way, and an unlit hole drops
you back to the entrance and becomes rock. Light every key, then walk into the opened ring.
RESET retries the level.

Every refusal answers: a walk into stone flashes the stone red, an UNDO with nothing behind
you flashes a white halo on the walker, and an UNDO onto a scar flashes that scar white. The
flash alternates between a full and an inset form, so pressing a refused key twice still moves
pixels both times.

7 levels. No RNG. No budget, no lives, no counters.
"""

from collections import deque

import numpy as np
from arcengine import ARCBaseGame, Camera, GameState, Level, RenderableUserDisplay

# ---------------------------------------------------------------------------
# Palette (ARC-3 indices) -- built on the under-used vivid end, never black-on-grey
# ---------------------------------------------------------------------------

C_WHITE, C_LGRAY, C_GRAY, C_DGRAY, C_VDGRAY, C_BLACK = 0, 1, 2, 3, 4, 5
C_MAGENTA, C_LMAGENTA, C_RED, C_BLUE, C_LBLUE = 6, 7, 8, 9, 10
C_YELLOW, C_ORANGE, C_MAROON, C_GREEN, C_PURPLE = 11, 12, 13, 14, 15

C_ROCK = C_MAROON        # the stone the corridor is cut through (maroon: 0.0% of official px)
C_DARK = C_PURPLE        # a corridor cell whose contents are still unknown
C_NOISE = C_VDGRAY       # the stipple laid over it: the texture of having no information
C_LIT = C_LMAGENTA       # an afterimage: flat, untextured -- a cell you have lit
C_MARK = C_MAROON        # a remaining retreat, cut into the top of the afterimage as a notch
C_SCAR = C_ORANGE        # a cell whose marks are spent: filled, crossed, never enterable
C_CUT = C_VDGRAY         # corridor no longer connected to you: dead structure, not meaning
C_GHOST = C_GRAY         # what that dead ground still holds, drawn but out of reach
C_KEY = C_YELLOW
C_LOCK = C_MAGENTA       # the exit ring while it is closed
C_OPEN = C_LBLUE         # the exit ring once every key is in
C_PIT = C_BLACK          # the hole itself
C_RIM = C_MAGENTA        # its rim
C_YOU = C_BLUE           # the walker, and nothing else on the board is ever blue
C_DEAD = C_GRAY
C_NO = C_RED             # a walk refused by stone: the stone answers
C_BACK = C_WHITE         # a retreat refused: nothing behind you, or a scar behind you

# ---------------------------------------------------------------------------
# Board geometry -- 6x6 cells of 10px, centred in the 64x64 frame. No HUD band.
# Small and dense on purpose: step-look-step costs three actions per cell of progress, so a
# level that fits the harness's ~120-action game has to be short in CELLS, not in rules.
# ---------------------------------------------------------------------------

GRID = 6
CELL = 10
OFF = (64 - GRID * CELL) // 2
LOOKS = 2                # retreats a corridor cell can absorb before it scars

DIRS = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}
ORDER = ("U", "D", "L", "R")
ACTION_DIR = {1: "U", 2: "D", 3: "L", 4: "R"}
UNDO = 7
ACTIONS = [1, 2, 3, 4, UNDO]

WALL, FLOOR, START, TRAP, KEY, EXIT = "#", ".", "S", "T", "K", "E"


def neighbours(cell):
    return [(cell[0] + dx, cell[1] + dy) for dx, dy in DIRS.values()]


def origin(cell):
    """Top-left pixel of a cell."""
    return OFF + cell[0] * CELL, OFF + cell[1] * CELL


# ---------------------------------------------------------------------------
# Levels. Walls are visible from the first frame; contents are not. Escalation adds a rule
# and never scales one up -- every earlier rule stays in force. The ladder is Echo, Key, Fork,
# Order, Side, Weave, Echoes, exactly as before; only the corridors are shorter.
#
# The governing geometry: the ONLY vantage from which a cell can be lit is a neighbour you
# can stand on, so a junction is the sole vantage for each of its own branches. Two marks per
# cell therefore means a crossroads may be inspected twice and then seals. Dead-end pockets
# are visible in the walls, which is what makes the safe order inferable rather than guessed.
# ---------------------------------------------------------------------------

LEVELS = [
    {
        # NEW: everything. A press moves you into the dark; UNDO steps back and lights what you
        # stood on; the cell you land on spends a mark; the exit ring has to be lit before it
        # can be walked into. One corridor, one dead-end stub with a hole in it, and the ring
        # at the far end -- a retreat can only ever cut off ground BEHIND you, so on a corridor
        # whose ring is at the end there is nothing here that can strand you. No keys yet.
        "name": "Echo",
        "map": ("######",
                "##ST##",
                "##.###",
                "##..##",
                "###.##",
                "###E##"),
    },
    {
        # NEW: keys, and a ring that stays shut without them. Lighting a key is what takes it,
        # so a key has to be stepped on and retreated from -- which is the look you were going
        # to spend on that cell anyway. That is why almost every cell holds one: the key is
        # what makes the look compulsory. The two-cell pocket above the entrance is the first
        # thing you meet, and the entrance is the only vantage for both it and the road on:
        # sweep the pocket and walk back out first, or the last mark buys the road and seals
        # the keys in behind a scar.
        "name": "Key",
        "map": ("#K####",
                "#K####",
                "#SK###",
                "##KK##",
                "#KK###",
                "##KE##"),
    },
    {
        # NEW: a junction, and the scar. Its two arms can only be looked into from the junction
        # itself, so the second look burns it out under you -- you may step off a scar, never
        # back onto it. Both arms end in a ring here, so the commitment itself cannot cost you
        # the level; every key is on the stem in, and the stem has to be swept in order.
        "name": "Fork",
        "map": ("#E#E##",
                "#.K.##",
                "##K###",
                "#KK###",
                "##KKK#",
                "#KS###"),
    },
    {
        # NEW: the arms are no longer equal. One is a two-cell pocket with a key at the bottom;
        # the other is the road to the only ring. Sweep the pocket, walk back out, then spend
        # the junction on the road. Spend it on the road first and the key is behind a scar;
        # look into both before sweeping either and neither side is whole.
        "name": "Order",
        "map": ("##K###",
                "##K###",
                "#SKK##",
                "###KK#",
                "##KK##",
                "###E##"),
    },
    {
        # NEW: a hole in a doorway. The cell in front of the ring has two mouths, both drawn in
        # the walls, and a hole fills the near one: light it and that way in is rock for good.
        # Nothing is lost -- the long way round is right there on the map -- but it is the
        # first cell on this board whose contents decide which SIDE you may enter from.
        "name": "Side",
        "map": ("#K####",
                "#K####",
                "#SK###",
                "##KT##",
                "#KKK##",
                "###E##"),
    },
    {
        # NEW: a key lying in the open road rather than at the bottom of a pocket. Walking over
        # it in the dark lights it and leaves it lying there -- only a retreat picks it up -- so
        # it stays on the floor as a block until you come back and step off it the other way.
        # The spine here is nothing but such keys, alternating with pockets left and right.
        "name": "Weave",
        "map": ("##S###",
                "#KK###",
                "##KKK#",
                "#KK###",
                "##KK##",
                "##E###"),
    },
    {
        # Everything at once, and NEW: a crossroads. Three dark arms, two marks -- one arm can
        # never be looked into at all, and the one that is a single dead-end cell is the one to
        # leave alone: on this board every key lies on a road or at the bottom of a pocket,
        # never in a stub.
        "name": "Echoes",
        "map": ("######",
                "##K###",
                "##K###",
                "#TKKKK",
                "##K#K#",
                "##S#E#"),
    },
]


# ---------------------------------------------------------------------------
# Rules as pure functions -- shared by the game, its smoke test and its gate
# ---------------------------------------------------------------------------

def parse(rows):
    """-> (cells, start, exits, keys, content). content maps every cell to its glyph."""
    cells, content, keys, exits = set(), {}, set(), set()
    start = None
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch == WALL:
                continue
            cells.add((c, r))
            content[(c, r)] = FLOOR if ch == START else ch
            if ch == START:
                start = (c, r)
            elif ch == EXIT:
                exits.add((c, r))
            elif ch == KEY:
                keys.add((c, r))
    return frozenset(cells), start, frozenset(exits), frozenset(keys), content


def component(src, passable):
    """Cells reachable from src by walking. src is included even when it is itself a scar --
    you may always step OFF a scar, you simply may never step back onto one."""
    seen = {src}
    q = deque([src])
    while q:
        p = q.popleft()
        for n in neighbours(p):
            if n in passable and n not in seen:
                seen.add(n)
                q.append(n)
    return seen


# ---------------------------------------------------------------------------
# Display -- the board IS the state. Marks are the pressure gauge and they live on the floor.
# ---------------------------------------------------------------------------

class Eh01Display(RenderableUserDisplay):
    """Repainted from current state every frame.

    rock          flat maroon, no texture
    unlit cell    deep purple under a grey stipple -- static, the texture of no information
    afterimage    FLAT light magenta, with one notch per retreat it can still absorb
    scar          filled orange with a maroon cross: spent, and closed for good
    cut off       the same cell in grey the instant it stops being connected to you
    key           a yellow block while it lies there, a small yellow socket once taken
    exit          a closed magenta ring; a light-blue ring with a gap once every key is in
    hole          a black diamond with a hot rim on rock -- it is a wall now
    you           a solid blue diamond in a blue frame, and nothing else on the board is blue:
                  solid when you know what you stand on, and punched through with a window of
                  the stipple itself when you do not
    refusals      stone you walked into flashes red; an UNDO with nothing behind you flashes a
                  white halo on the walker; an UNDO onto a scar flashes that scar white
    """

    def __init__(self, game):
        self.game = game

    # -- primitives ---------------------------------------------------------

    @staticmethod
    def _fill(frame, px, py, color):
        frame[py:py + CELL, px:px + CELL] = color

    @staticmethod
    def _box(frame, px, py, r0, r1, c0, c1, color):
        frame[py + r0:py + r1 + 1, px + c0:px + c1 + 1] = color

    @staticmethod
    def _ring(frame, px, py, r0, r1, c0, c1, color):
        frame[py + r0, px + c0:px + c1 + 1] = color
        frame[py + r1, px + c0:px + c1 + 1] = color
        frame[py + r0:py + r1 + 1, px + c0] = color
        frame[py + r0:py + r1 + 1, px + c1] = color

    @classmethod
    def _band(cls, frame, px, py, inset, thick, color):
        """A square band `thick` pixels wide, `inset` pixels in from the cell edge."""
        for i in range(thick):
            cls._ring(frame, px, py, inset + i, CELL - 1 - inset - i,
                      inset + i, CELL - 1 - inset - i, color)

    @staticmethod
    def _diamond(frame, px, py, reach, color, hole=0):
        mid = (CELL - 1) / 2.0
        for r in range(CELL):
            for c in range(CELL):
                d = abs(r - mid) + abs(c - mid)
                if d <= reach and not (hole and abs(r - mid) < hole and abs(c - mid) < hole):
                    frame[py + r, px + c] = color

    @staticmethod
    def _stipple(frame, px, py, color):
        """The texture of an unlit cell: a sparse regular dither, unmistakably not flat."""
        for r in range(1, CELL - 1):
            for c in range(1, CELL - 1):
                if r % 3 in (1, 2) and c % 3 in (1, 2):
                    frame[py + r, px + c] = color

    @classmethod
    def _edge_bar(cls, frame, px, py, d, thick, color):
        """A bar along one side of a cell -- which side you were refused on."""
        if d == "U":
            frame[py:py + thick, px:px + CELL] = color
        elif d == "D":
            frame[py + CELL - thick:py + CELL, px:px + CELL] = color
        elif d == "L":
            frame[py:py + CELL, px:px + thick] = color
        elif d == "R":
            frame[py:py + CELL, px + CELL - thick:px + CELL] = color

    # -- one cell -----------------------------------------------------------

    def _draw_cell(self, frame, g, cell, reach):
        px, py = origin(cell)
        lit = cell in g.revealed
        what = g.content[cell]

        if lit and what == TRAP:                       # a lit hole is rock with a pit in it
            self._fill(frame, px, py, C_ROCK)
            self._diamond(frame, px, py, (CELL - 1) / 2.0, C_RIM)
            self._diamond(frame, px, py, (CELL - 1) / 2.0 - 2.0, C_PIT)
            return

        if g.looks[cell] <= 0:                         # scar
            self._fill(frame, px, py, C_SCAR)
            for i in range(CELL):
                for j in (0, 1):
                    frame[py + i, px + min(i + j, CELL - 1)] = C_ROCK
                    frame[py + i, px + max(CELL - 1 - i - j, 0)] = C_ROCK
            return

        # Ground you can no longer reach collapses back into the rock, leaving only a ghost of
        # what it held. Recomputed every frame, so a scar closes a wing of the map on sight.
        cut = cell not in reach
        base = C_ROCK if cut else (C_LIT if lit else C_DARK)
        self._fill(frame, px, py, base)
        if not cut and not lit:
            self._stipple(frame, px, py, C_NOISE)      # you have no information about this cell
        if cut:                                        # the ground caves in; its outline stays
            self._band(frame, px, py, 1, 1, C_CUT)

        if lit:                                        # marks only ever ride an afterimage
            if not cut:                                # ...and mean nothing on ground you lost
                self._box(frame, px, py, 1, 2, 1, 2, C_MARK)
                if g.looks[cell] >= 2:
                    self._box(frame, px, py, 1, 2, CELL - 3, CELL - 2, C_MARK)

            if what == KEY:
                col = C_GHOST if cut else C_KEY
                if cell in g.keys_taken:
                    self._box(frame, px, py, 4, 5, 4, 5, col)        # the socket it left
                else:
                    self._box(frame, px, py, 3, 6, 3, 6, col)        # the block still lying there
            elif what == EXIT:
                col = C_GHOST if cut else (C_OPEN if g.keys <= g.keys_taken else C_LOCK)
                self._ring(frame, px, py, 2, CELL - 3, 2, CELL - 3, col)
                self._ring(frame, px, py, 3, CELL - 4, 3, CELL - 4, col)
                if g.keys <= g.keys_taken:                           # the ring breaks open
                    self._box(frame, px, py, CELL - 4, CELL - 3, 4, CELL - 5, base)

    # -- the walker, and the answer to a refused key ------------------------

    def _draw_walker(self, frame, g):
        px, py = origin(g.pos)
        color = C_DEAD if g.dead else C_YOU
        self._band(frame, px, py, 0, 1, color)
        # Solid when you know your ground; punched through with a window of the stipple itself
        # when you do not -- the hole in the token IS the texture of the unknown.
        self._diamond(frame, px, py, (CELL - 1) / 2.0 - 1.0, color,
                      hole=0 if g.pos in g.revealed else 2.0)

    def _draw_flash(self, frame, g):
        kind, cell, d = g.flash
        phase = g.pulse & 1
        px, py = origin(g.pos)
        if kind == "block":
            inside = cell is not None and 0 <= cell[0] < GRID and 0 <= cell[1] < GRID
            if inside:
                bx, by = origin(cell)
                if phase:
                    self._box(frame, bx, by, 2, CELL - 3, 2, CELL - 3, C_NO)
                else:
                    self._fill(frame, bx, by, C_NO)
            else:
                # A walk off the edge of the world has no cell to flash, so the walker's own
                # cell carries it: a red band, which no other refusal draws.
                self._band(frame, px, py, phase, 2 - phase, C_NO)
            self._edge_bar(frame, px, py, d, 4 - 2 * phase, C_NO)
        elif kind == "empty":
            self._band(frame, px, py, phase, 1, C_BACK)
            self._band(frame, px, py, 3 + phase, 1, C_BACK)
        elif kind == "scar":
            bx, by = origin(cell)
            self._band(frame, bx, by, phase, 3 - phase, C_BACK)
            self._edge_bar(frame, px, py, d, 3 - phase, C_BACK)

    # -- frame --------------------------------------------------------------

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game
        frame[:, :] = C_ROCK
        reach = component(g.pos, g.passable()) - g.dead_wings()
        for cell in g.cells:
            self._draw_cell(frame, g, cell, reach)
        self._draw_walker(frame, g)
        if g.flash is not None:
            self._draw_flash(frame, g)
        return frame


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class Eh01(ARCBaseGame):
    def __init__(self):
        self.display = Eh01Display(self)

        # on_set_level() runs inside super().__init__(), and the display reads all of this,
        # so every attribute has to exist before super() is called.
        self.cells = frozenset()
        self.content = {}
        self.keys = frozenset()
        self.start = (0, 0)
        self.exits = frozenset()
        self.pos = (0, 0)
        self.revealed = set()
        self.looks = {}
        self.keys_taken = set()
        self.trail = None
        self.dead = False
        self.flash = None
        self.pulse = 0

        levels = [Level(sprites=[], grid_size=(64, 64), data=ldef, name=ldef["name"])
                  for ldef in LEVELS]

        super().__init__(
            "eh",
            levels,
            Camera(0, 0, 64, 64, C_ROCK, C_ROCK, [self.display]),
            False,
            len(levels),
            list(ACTIONS),           # d-pad plus UNDO. ACTION7 is ours to implement.
        )

    # -- level setup --------------------------------------------------------

    def on_set_level(self, level: Level) -> None:
        """Rebuild from the level constants: every cell dark, every mark restored. Runs on a
        new level and on every RESET, so a lost level is retried on a clean corridor."""
        i = self.level_index
        self.cells, self.start, self.exits, self.keys, self.content = parse(
            LEVELS[i]["map"])
        self.pos = self.start
        self.revealed = {self.start}
        self.looks = {c: LOOKS for c in self.cells}
        self.keys_taken = set()
        self.trail = None
        self.dead = False
        self.flash = None
        self.pulse = 0

    def handle_reset(self) -> None:
        """The base class promotes a RESET to a full restart whenever `_action_count == 0`,
        and every level load zeroes `_action_count` -- so a RESET as the first action on a
        level would throw the player back to level 1. Full restart only from NOT_PLAYED and
        WIN; a level retry otherwise."""
        if self._state in (GameState.NOT_PLAYED, GameState.WIN):
            self.full_reset()
        else:
            self.level_reset()

    # -- rules --------------------------------------------------------------

    def passable(self):
        """Cells you may still walk INTO: not scarred, not a hole you have already lit."""
        return {c for c in self.cells
                if self.looks[c] > 0 and not (c in self.revealed and self.content[c] == TRAP)}

    def _refuse(self, kind, cell, d):
        """A key that does nothing is a broken game, so nothing does nothing: every refusal
        paints one frame. `pulse` alternates the form so that pressing a refused key twice in
        a row still moves pixels on the second press as well as the first."""
        self.flash = (kind, cell, d)
        self.pulse += 1

    def _light(self, cell):
        """Lighting is permanent, and lighting a key is what takes it."""
        self.revealed.add(cell)
        if self.content[cell] == KEY:
            self.keys_taken.add(cell)

    def _walk(self, d):
        dx, dy = DIRS[d]
        nxt = (self.pos[0] + dx, self.pos[1] + dy)
        if nxt not in self.passable():
            self._refuse("block", nxt, d)            # rock, scar or a lit hole: it answers red
            return
        here = self.pos
        if here not in self.revealed:
            # Stepping on THROUGH an unlit cell resolves it with your feet, not your eyes.
            self.revealed.add(here)                  # ...and a key walked over is not taken
            if self.content[here] == TRAP:
                self.pos = self.start                # the floor gives way: back to the entrance
                self.trail = None                    # ...and the hole is rock from now on
                return
        self.trail = here
        self.pos = nxt

    def _undo(self):
        back = self.trail
        # One step deep, deliberately: the retreat is always "back the way you just came", so
        # nothing on this board ever asks the player to remember a route (Son's rule). A
        # retreat consumes the step it undoes, so UNDO twice in a row has nothing to undo.
        if back is None:
            self._refuse("empty", None, None)        # a white halo, and no way back out of it
            return
        d = next((k for k, (dx, dy) in DIRS.items()
                  if (self.pos[0] + dx, self.pos[1] + dy) == back), None)
        if self.looks[back] <= 0:
            self._refuse("scar", back, d)            # the scar behind you flashes white
            return
        # A look at ground you have already lit is a look at nothing, and it burns the cell
        # you land on twice as deep. The cell under you is visibly dark or lit, so this asks
        # the player to remember nothing -- only to look where there is something to see.
        cost = 1 if self.pos not in self.revealed else 2
        self.trail = None
        self._light(self.pos)
        self.looks[back] = max(0, self.looks[back] - cost)
        self.pos = back

    def dead_wings(self):
        """Standing on a scar, every side you could step to is a side you can never come back
        from. A side you have already lit end to end, holding no ring and no key still out, is
        finished -- so draw it dark BEFORE the step rather than after. This leaks nothing: it
        only darkens ground the player has already seen all of."""
        if self.looks[self.pos] > 0:
            return set()
        p = self.passable() - {self.pos}
        out = set()
        for n in neighbours(self.pos):
            if n not in p:
                continue
            wing = component(n, p)
            alive = (any(c not in self.revealed for c in wing)
                     or any(c in self.exits and c in self.revealed for c in wing)
                     or any(c in self.keys - self.keys_taken for c in wing))
            if not alive:
                out |= wing
        return out

    # -- the only two endings -----------------------------------------------

    def _settle(self):
        if (self.pos in self.exits and self.pos in self.revealed
                and self.keys <= self.keys_taken):
            self.next_level()
            return True
        if self.pos not in self.revealed:
            return False                             # never judge a cell you cannot see yet
        reach = component(self.pos, self.passable())
        lost = not (self.exits & reach)
        for k in self.keys - self.keys_taken:
            if k not in reach or not any(
                    n in reach and self.looks[n] > 0 for n in neighbours(k)):
                lost = True                          # nowhere left to retreat onto and take it
        if lost:
            self.dead = True
            self.lose()
        return False

    # -- engine entry point -------------------------------------------------

    def step(self) -> None:
        self.flash = None                            # last frame's answer, spent
        aid = self.action.id.value
        if aid in ACTION_DIR:
            self._walk(ACTION_DIR[aid])
        elif aid == UNDO:
            self._undo()
        # aid == 0: handle_reset() already rebuilt the level; nothing else to do.
        self._settle()
        self.complete_action()
