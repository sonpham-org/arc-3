# Author: Claude Opus 5
# Date: 2026-09-07 09:10
# PURPOSE: eh01 "Echo" -- an ARC-AGI-3 environment in which UNDO is the only sense organ.
#   The corridor's shape is lit, but what lies IN each cell is dark. Walking into a cell tells
#   you nothing; pressing UNDO (ACTION7) retreats one cell and permanently lights the cell you
#   just left, so you learn a cell only by stepping onto it and backing out. The retreat lands
#   on a cell that pays for it: every corridor cell can absorb two retreats, then it scars and
#   is closed forever -- and a retreat off ground you have ALREADY lit showed you nothing, so
#   it burns two marks instead of one. Looking is therefore rationed by geometry: a junction is
#   the only vantage for its own arms, so a crossroads can be inspected exactly twice before it
#   seals under you. Holes are only dangerous while unlit: walking on THROUGH an unlit hole
#   drops you back to the entrance and turns that cell into rock; a lit hole is simply a wall
#   you walk around. Keys are taken by lighting them; the ring out opens when the last key is
#   in, and it too must be seen before it can be entered. There is no budget, no lives, no
#   counter and no HUD: the afterimages and the scars are the entire display of state, and the
#   loss is purely topological -- ground you can no longer reach caves back into the rock the
#   moment the way is cut, and a wing you have finished caves in BEFORE you can step into it.
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
C_LIT = C_LMAGENTA       # an afterimage: a cell you have lit, and can retreat onto
C_MARK = C_MAROON        # a remaining retreat, cut into the top of the afterimage as a notch
C_SCAR = C_ORANGE        # a cell whose marks are spent: filled, crossed, never enterable
C_CUT = C_VDGRAY         # corridor no longer connected to you: dead structure, not meaning
C_GHOST = C_GRAY         # what that dead ground still holds, drawn but out of reach
C_KEY = C_YELLOW
C_LOCK = C_MAGENTA       # the exit ring while it is closed
C_OPEN = C_LBLUE         # the exit ring once every key is in
C_PIT = C_BLACK          # the hole itself
C_RIM = C_MAGENTA        # its rim
C_YOU = C_WHITE
C_DEAD = C_GRAY

# ---------------------------------------------------------------------------
# Board geometry -- 8x8 cells of 8px fill the 64x64 frame exactly. No HUD band.
# ---------------------------------------------------------------------------

GRID = 8
CELL = 8
LOOKS = 2                # retreats a corridor cell can absorb before it scars

DIRS = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}
ORDER = ("U", "D", "L", "R")
ACTION_DIR = {1: "U", 2: "D", 3: "L", 4: "R"}
UNDO = 7
ACTIONS = [1, 2, 3, 4, UNDO]

WALL, FLOOR, START, TRAP, KEY, EXIT = "#", ".", "S", "T", "K", "E"


def neighbours(cell):
    return [(cell[0] + dx, cell[1] + dy) for dx, dy in DIRS.values()]


# ---------------------------------------------------------------------------
# Levels. Walls are visible from the first frame; contents are not. Escalation adds a rule
# and never scales one up -- every earlier rule stays in force.
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
        # can be walked into. One corridor, one dead-end stub with a trap in it, and no
        # junction whose branches you need both of -- nothing here can strand you.
        "name": "Echo",
        "map": ("###S####",
                "###.####",
                "###...T#",
                "#####.##",
                "##....##",
                "##.#####",
                "##E#####",
                "########"),
    },
    {
        # NEW: keys, and a ring that stays shut without them. Lighting a key is what takes it,
        # so a key has to be stepped on and retreated from. Both keys hang two cells down a
        # visible dead-end pocket, and a pocket's mouth is the only vantage for the pocket AND
        # for the road on: sweep the pocket first and you walk back out through a mouth that
        # still has a mark, look down the road first and the mouth burns with the key behind it.
        "name": "Key",
        "map": ("##K#####",
                "##.#K#K#",
                "##.#.#.#",
                "#S.....#",
                "#T####.#",
                "###....#",
                "###.####",
                "###E####"),
    },
    {
        # NEW: a junction, and the scar. Its two arms can only be looked into from the junction
        # itself, so the second look burns it out under you -- you may step off a scar, never
        # back onto it. Both arms end in a ring here, so the commitment itself cannot cost you
        # the level; only the pockets on the road in still have to be swept in order.
        "name": "Fork",
        "map": ("###K####",
                "#K#.#K##",
                "#.#.#.##",
                "#S....##",
                "####.###",
                "T......T",
                "#.####.#",
                "#E####E#"),
    },
    {
        # NEW: the arms are no longer equal. One is a two-cell pocket with the second key at
        # the bottom; the other is the long road to the only ring. Sweep the pocket, walk back
        # out, then spend the junction on the road. Spend it on the road first and the key is
        # behind a scar; look into both before sweeping either and neither side is whole.
        "name": "Order",
        "map": ("##K#####",
                "##.#K###",
                "##.#.###",
                "#S...###",
                "####.###",
                "#......K",
                "#.######",
                "#..E####"),
    },
    {
        # NEW: a hole in a doorway. The room with the second key has two mouths, both drawn in
        # the walls, and a hole fills one of them: light it and that way in is rock for good.
        # Nothing is lost -- the other mouth is right there on the map -- but it is the first
        # cell on this board whose contents decide which SIDE of a room you may enter from.
        "name": "Side",
        "map": ("##K#####",
                "##.#####",
                "#S.##K##",
                "##.##.##",
                "##.....T",
                "##T.##.#",
                "##.K##.#",
                "######E#"),
    },
    {
        # NEW: a key lying in the open road rather than at the bottom of a pocket. Walking over
        # it in the dark lights it and leaves it lying there -- only a retreat picks it up -- so
        # it stays on the floor as a block until you come back and step off it the other way.
        "name": "Weave",
        "map": ("##K###K#",
                "##.###.#",
                "##.###.#",
                "#S.....#",
                "#T####.#",
                "###.K..#",
                "#...#T##",
                "#E######"),
    },
    {
        # Everything at once, and NEW: a crossroads. Three dark arms, two marks -- one arm can
        # never be looked into at all, and the one that is a single dead-end cell is the one to
        # leave alone: on this board every key lies at the bottom of a pocket, never in a stub.
        "name": "Echoes",
        "map": ("###S####",
                "#K..##K#",
                "###.##.#",
                "#......#",
                "#K#T#.##",
                "#####.##",
                "#####E##",
                "########"),
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

    rock          flat maroon, no marks
    unlit cell    deep purple, no marks -- you have never seen inside it
    afterimage    light magenta, with one block per retreat it can still absorb
    scar          filled orange with a maroon cross: spent, and closed for good
    cut off       the same cell in grey the instant it stops being connected to you
    key           a yellow plus while it lies there, a small yellow dot once taken
    exit          a closed magenta ring; a light-blue ring with a gap once every key is in
    trap          a black diamond with a hot rim on rock -- it is a wall now
    you           a white border round your cell: solid when you know what you stand on,
                  four corner ticks when you do not
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

    @staticmethod
    def _diamond(frame, px, py, reach, color):
        for r in range(CELL):
            for c in range(CELL):
                if abs(r - 3.5) + abs(c - 3.5) <= reach:
                    frame[py + r, px + c] = color

    # -- one cell -----------------------------------------------------------

    def _draw_cell(self, frame, g, cell, reach):
        px, py = cell[0] * CELL, cell[1] * CELL
        lit = cell in g.revealed
        what = g.content[cell]

        if lit and what == TRAP:                       # a lit trap is rock with a hole in it
            self._fill(frame, px, py, C_ROCK)
            self._diamond(frame, px, py, 3.0, C_RIM)
            self._diamond(frame, px, py, 2.0, C_PIT)
            return

        if g.looks[cell] <= 0:                         # scar
            self._fill(frame, px, py, C_SCAR)
            for i in range(CELL):
                frame[py + i, px + i] = C_ROCK
                frame[py + i, px + CELL - 1 - i] = C_ROCK
            return

        # Ground you can no longer reach collapses back into the rock, leaving only a ghost of
        # what it held. Recomputed every frame, so a scar closes a wing of the map on sight.
        cut = cell not in reach
        base = C_ROCK if cut else (C_LIT if lit else C_DARK)
        self._fill(frame, px, py, base)
        if cut:                                        # the ground caves in; its outline stays
            self._ring(frame, px, py, 1, CELL - 2, 1, CELL - 2, C_CUT)

        if lit:                                        # marks only ever ride an afterimage
            if not cut:                                # ...and mean nothing on ground you lost
                self._box(frame, px, py, 1, 2, 1, 2, C_MARK)
                if g.looks[cell] >= 2:
                    self._box(frame, px, py, 1, 2, 5, 6, C_MARK)

            if what == KEY:
                col = C_GHOST if cut else C_KEY
                if cell in g.keys_taken:
                    self._box(frame, px, py, 4, 5, 3, 4, col)        # the socket it left
                else:
                    self._box(frame, px, py, 3, 6, 2, 5, col)        # the block still lying there
            elif what == EXIT:
                if g.keys <= g.keys_taken:
                    col = C_GHOST if cut else C_OPEN
                    self._ring(frame, px, py, 3, 6, 1, 6, col)
                    frame[py + 6, px + 2:px + 6] = base              # the ring breaks open
                else:
                    self._ring(frame, px, py, 3, 6, 1, 6, C_GHOST if cut else C_LOCK)

    # -- frame --------------------------------------------------------------

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game
        frame[:, :] = C_ROCK
        reach = component(g.pos, g.passable()) - g.dead_wings()
        for cell in g.cells:
            self._draw_cell(frame, g, cell, reach)

        px, py = g.pos[0] * CELL, g.pos[1] * CELL
        color = C_DEAD if g.dead else C_YOU
        if g.pos in g.revealed:
            self._ring(frame, px, py, 0, CELL - 1, 0, CELL - 1, color)   # you know your ground
        else:
            for r0, dr in ((0, 1), (CELL - 1, -1)):                      # ...or you do not
                for c0, dc in ((0, 1), (CELL - 1, -1)):
                    for i in range(3):
                        frame[py + r0, px + c0 + dc * i] = color
                        frame[py + r0 + dr * i, px + c0] = color
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
        """Cells you may still walk INTO: not scarred, not a trap you have already lit."""
        return {c for c in self.cells
                if self.looks[c] > 0 and not (c in self.revealed and self.content[c] == TRAP)}

    def _light(self, cell):
        """Lighting is permanent, and lighting a key is what takes it."""
        self.revealed.add(cell)
        if self.content[cell] == KEY:
            self.keys_taken.add(cell)

    def _walk(self, d):
        dx, dy = DIRS[d]
        nxt = (self.pos[0] + dx, self.pos[1] + dy)
        if nxt not in self.passable():
            return                                   # rock, scar or a lit trap: free no-op
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
        # retreat consumes the step it undoes, so UNDO twice in a row is a free no-op.
        if back is None:
            return                                   # nothing to step back along: free no-op
        if self.looks[back] <= 0:
            return                                   # a scar cannot catch you: free no-op
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
        aid = self.action.id.value
        if aid in ACTION_DIR:
            self._walk(ACTION_DIR[aid])
        elif aid == UNDO:
            self._undo()
        # aid == 0: handle_reset() already rebuilt the level; nothing else to do.
        self._settle()
        self.complete_action()
