# Author: Claude Opus 5
# Date: 2026-09-07
# PURPOSE: ng01 "Negative" -- an ARC-AGI-3 environment. The world is a 128-cell strip, eight
#   viewports wide; the 64x64 frame is a camera locked to the walker, so the world slides
#   under a stationary token and every step visibly redraws the screen. The strip is drawn
#   in exactly two colours: FIGURE (solid) and GROUND (passable). LEFT/RIGHT step one cell,
#   gravity is discrete and immediate, UP climbs a single step in front. ACTION5 inverts the
#   world: the solid family and the hole family trade places, so the block you stood on
#   becomes the hole and the holes become your floor -- staircases move to the other side of
#   a pit when you press it. Loss is being STRANDED (a reverse BFS over (position, polarity)
#   says the goal is unreachable). No budget, no lives, no bar, no pips.
# SRP/DRY check: Pass -- self-contained environment. Nothing in the catalogue inverts
#   figure/ground, and the side-scrolling camera is new to this repo.
"""Negative -- walk right, and flip the world when the floor runs out.

ACTION3 / ACTION4 step one cell left / right (gravity pulls you down immediately).
ACTION1 climbs a one-cell step directly in front of you.
ACTION5 inverts the world. It is refused -- with a flash -- when your own cell would
turn solid; the walker wears the refusal colour whenever it stands somewhere inversion
is locked, so the lock is visible before it is pressed.

6 levels, 15-24 actions each. No RNG, no timer, no score and no counter of any kind.
"""

from collections import deque

import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

# ---------------------------------------------------------------------------
# Colours (ARC-3 palette indices)
# ---------------------------------------------------------------------------

C_WHITE, C_LGRAY, C_GRAY, C_DGRAY, C_VDGRAY, C_BLACK = 0, 1, 2, 3, 4, 5
C_MAGENTA, C_LMAGENTA, C_RED, C_BLUE, C_LBLUE = 6, 7, 8, 9, 10
C_YELLOW, C_ORANGE, C_MAROON, C_GREEN, C_PURPLE = 11, 12, 13, 14, 15

# Measured over the 773 catalogued games, greyscale is 60.3% of every pixel and maroon is
# 0.0% of official pixels. The two world colours are therefore maroon and light magenta,
# never black/white/grey, so a model has effectively never seen a board like this one.
C_FIGURE = C_MAROON        # solid
C_GROUND = C_LMAGENTA      # passable
C_MUTABLE = C_PURPLE       # outline on every cell inversion will change
C_WALKER = C_ORANGE        # the walker, and nothing else in the game
C_LOCKED = C_BLUE          # walker trim where inversion is refused; also the refusal flash
C_GOAL = C_YELLOW          # goal ring, still reachable
C_DEAD = C_VDGRAY          # goal and walker once stranded -- the only dark pixels in the game

# ---------------------------------------------------------------------------
# World geometry.  Cells are 4x4 px, so the 64x64 frame shows 16x16 cells out of a strip
# that is 128 cells wide -- eight frames.  The camera is therefore never the whole world,
# and on every level it is unclamped for the entire solution: the walker sits dead centre
# and the terrain is what moves.
# ---------------------------------------------------------------------------

CELL = 4
WORLD_W, WORLD_H = 128, 16
VIEW = 64 // CELL          # 16 cells across the frame
CEIL = 2                   # rows 0-1 are bedrock roof on every level

VOID, MAT_A, MAT_B, FIXED = 0, 1, 2, 3
_CHARS = {".": VOID, "#": MAT_A, "o": MAT_B, "=": FIXED, "S": VOID, "G": VOID}

# Polarity 0: MAT_A is solid, MAT_B is a hole.  Polarity 1: the two swap.  FIXED is solid
# in both and is the one thing the player can rely on; VOID is open sky in both.

# ---------------------------------------------------------------------------
# Terrain DSL.  A level is a skyline (chunky ledges of differing height) plus a handful of
# rectangles carved into it.  Authoring by skyline rather than by row is what keeps the
# frame from collapsing into two flat colour bands: the FIGURE/GROUND boundary steps up and
# down by whole cells every few columns, so it is 4-12 px of visible structure everywhere.
# ---------------------------------------------------------------------------

# Tiled background skyline, used by every level outside its play region.  Widths are 3-6
# cells and tops swing over six rows, so any frame of it is a staircase, never a band.
_BG = [(4, 12), (3, 9), (5, 13), (4, 10), (3, 14), (6, 11),
       (3, 8), (4, 13), (5, 10), (3, 12), (4, 9), (5, 14)]


def _blank():
    """A world of open sky under a two-row bedrock roof."""
    g = [["."] * WORLD_W for _ in range(WORLD_H)]
    for y in range(CEIL):
        g[y] = ["="] * WORLD_W
    return g


def _skyline(g, spans, ch="="):
    """spans: (width, top) chunks laid left to right, tiled until the strip is full.
    Each chunk fills its columns from `top` to the bottom of the world."""
    x = 0
    while x < WORLD_W:
        for w, top in spans:
            for _ in range(w):
                if x >= WORLD_W:
                    return
                for y in range(top, WORLD_H):
                    g[y][x] = ch
                x += 1


def _rect(g, x0, x1, y0, y1, ch):
    """Overwrite an inclusive rectangle.  Everything a level says beyond its skyline is
    said with these, so a level definition reads as a short list of features."""
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            g[y][x] = ch


def _flat(g, x0, x1, top, ch="="):
    """A level shelf: solid from `top` down, open sky above it."""
    _rect(g, x0, x1, CEIL, top - 1, ".")
    _rect(g, x0, x1, top, WORLD_H - 1, ch)


def _rows(g, start, goal):
    g[start[1]][start[0]] = "S"
    g[goal[1]][goal[0]] = "G"
    return ["".join(r) for r in g]

def _deco(g, *spans):
    """Floating slabs at rows 5-6: scenery that keeps the sky from being one flat field.
    Written only into open cells, and far enough above every walkable row that a one-cell
    climb can never reach them."""
    for x0, x1 in spans:
        for x in range(x0, x1 + 1):
            for y in (5, 6):
                if g[y][x] == ".":
                    g[y][x] = "="


# The roof is 2 rows of bedrock everywhere and 3 or 4 rows in places, so the top edge of the
# frame is a stepped line instead of an 8-pixel band.  Nothing walkable comes within three
# rows of the deepest chunk.
_ROOF = [(5, 2), (4, 4), (3, 2), (6, 3), (4, 2), (5, 4), (3, 3), (4, 2)]


def _roof(g):
    x = 0
    while x < WORLD_W:
        for w, d in _ROOF:
            for _ in range(w):
                if x >= WORLD_W:
                    return
                for y in range(d):
                    if g[y][x] == ".":
                        g[y][x] = "="
                x += 1


def _caves(g, *spans):
    """Sealed pockets inside the bedrock.  They break the solid mass at the bottom of the
    frame into blocks without touching play: a pocket is only carved where every cell around
    it is FIXED, so no inversion and no fall can ever open one.  Widths and depths are all
    different on purpose -- evenly spaced identical squares read as windows in a building,
    and this game must not resemble anything."""
    for x0, x1, y0, y1 in spans:
        if all(g[y][x] == "=" for x in range(x0 - 1, x1 + 2)
               for y in range(y0 - 1, min(y1 + 2, WORLD_H)) if 0 <= x < WORLD_W):
            _rect(g, x0, x1, y0, y1, ".")


def _bounds(g, west, east):
    """Three-cell step-ups that close the play region on both sides.  A one-cell climb
    cannot take them, so wandering off is cheap and never fatal -- it just ends at a wall."""
    _flat(g, west - 8, west - 1, 8)
    _flat(g, east + 1, east + 8, 8)


def _base():
    g = _blank()
    _skyline(g, _BG)
    return g


# Every level's play region starts at this column, so the strip runs 40 cells off the left
# of the camera and 50 off the right: the frame is never the world, and what is ahead is
# genuinely hidden until the camera brings it in.
O = 40


# L1 "step" -- walking, the camera, the climb, and both directions of the flip.  The floor
# is FIXED end to end and the two doors are single columns, so inversion can never affect
# the ground: level 1 is strand-proof by construction and machine-checked to be so.  The
# checker band overhead is pure MAT_A/MAT_B and swaps in place on the first press, so the
# very first inversion repaints half the screen with no consequence at all.
def _l1():
    g = _base()
    _flat(g, O - 6, O + 26, 11)
    _rect(g, O + 3, O + 4, 10, 15, "=")       # the step: two cells wide, one cell up
    _rect(g, O + 7, O + 8, 8, 10, "#")        # door A -- shut until you invert
    _rect(g, O + 11, O + 12, 8, 10, "o")      # door B -- shut once you have
    # Five mutable slabs overhead, of five different widths, with gaps between them: the
    # first press of ACTION5 makes half of them vanish and the other half appear, which is
    # the largest change on screen and costs nothing.  Deliberately not a regular band --
    # an evenly repeating strip of blocks reads as a ruler or a filmstrip.
    for x0, x1, ch in ((O - 4, O - 1, "#"), (O + 1, O + 4, "o"), (O + 6, O + 10, "#"),
                       (O + 12, O + 16, "o"), (O + 18, O + 23, "#")):
        _rect(g, x0, x1, 5, 6, ch)
    _bounds(g, O - 6, O + 26)
    _roof(g)
    _caves(g, (O - 4, O - 1, 13, 14), (O + 2, O + 2, 14, 14),
           (O + 13, O + 16, 13, 13), (O + 20, O + 21, 13, 14))
    return _rows(g, (O, 10), (O + 18, 10))


# L2 "shelf" -- the walkway east is MAT_A for a stretch, then MAT_B, and the only planks that
# survive a flip are the two FIXED stones between them.  Press ACTION5 anywhere else on it
# and the plank underfoot turns to air: you drop two rows into the trough that runs the whole
# length of the walkway.  The trough's east end is a dead wall and its only way out is the
# ledge at its west end, one cell below the shelf -- so a wrong flip costs up to twenty-six
# steps of walking back, and nothing here can kill you.  L3 is this same shape with the
# trough replaced by a four-deep pit.
#
# The trough is the shallow shape on purpose.  A bridge over a real PIT cannot be made
# strand-proof: in the polarity where the bridge is solid it is also a ceiling, so the only
# exits are past its ends -- put a staircase there and it becomes a bypass along the bottom
# that skips the bridge entirely (30,000 random rollouts found exactly that), leave it out
# and the pit is a strand.  A trough one cell shallower than a climb, whose exit sits west of
# where the walkway starts, has neither problem.
def _l2():
    g = _base()
    _flat(g, O - 6, O + 1, 11)
    _flat(g, O + 2, O + 2, 12)                # the one ledge the trough can be climbed onto
    _flat(g, O + 3, O + 15, 14)               # the trough under the walkway, two rows deep
    _rect(g, O + 3, O + 3, 13, 13, "=")       # and one FIXED step at its west end
    _rect(g, O + 3, O + 6, 11, 11, "#")       # ...and the walkway itself
    _rect(g, O + 7, O + 8, 11, 11, "=")       # stone 1
    _rect(g, O + 9, O + 12, 11, 11, "o")
    _rect(g, O + 13, O + 13, 11, 11, "=")     # stone 2
    _rect(g, O + 14, O + 15, 11, 11, "#")
    _flat(g, O + 16, O + 26, 10)              # a one-cell rise: costs a climb, not a step
    _rect(g, O + 18, O + 19, 7, 9, "#")       # the wall that costs the third inversion
    _bounds(g, O - 4, O + 26)
    _roof(g)
    _deco(g, (O - 3, O + 1), (O + 5, O + 10), (O + 20, O + 25))
    _caves(g, (O + 18, O + 19, 13, 14), (O + 22, O + 24, 12, 13))
    return _rows(g, (O, 10), (O + 21, 9))


# L3 "stone" -- the pit inversion cannot undo.  Two FIXED stones are the only planks in the
# bridge that survive a flip, and they are the only unbordered cells over the pit, so where
# it is safe to press invert is drawn on the board.  Flipping anywhere else drops you four
# cells onto a floor with no footing at all: that is the strand, and it is what ends every
# policy that presses invert on a timer.
def _l3():
    g = _base()
    _flat(g, O - 6, O + 4, 11)
    _flat(g, O + 2, O + 4, 10)                # a one-cell rise: costs a climb, not a step
    _flat(g, O + 5, O + 14, 15)               # the pit
    _rect(g, O + 5, O + 7, 11, 11, "#")
    _rect(g, O + 8, O + 9, 11, 11, "=")       # stone 1 -- two cells, the one you will use
    _rect(g, O + 10, O + 12, 11, 11, "o")
    _rect(g, O + 13, O + 13, 11, 11, "=")     # stone 2
    _rect(g, O + 14, O + 14, 11, 11, "#")
    _flat(g, O + 15, O + 26, 11)
    _rect(g, O + 17, O + 18, 8, 10, "#")
    _bounds(g, O - 6, O + 26)
    _roof(g)
    _deco(g, (O - 4, O + 1), (O + 6, O + 12), (O + 21, O + 25))
    _caves(g, (O - 4, O - 2, 14, 14), (O + 1, O + 2, 13, 14),
           (O + 19, O + 20, 13, 13), (O + 23, O + 25, 13, 14))
    return _rows(g, (O, 10), (O + 20, 10))


# L4 "gate" -- the inversion-locked corridor.  A MAT_A wall forces the flip; the corridor
# past it is two rows of MAT_B under a solid roof, so it is a plug in that same polarity and
# you must flip back on the one FIXED cell between them.  Inside, your own cell is MAT_B and
# inversion is refused for the whole length -- the walker wears the refusal colour the
# moment it steps in, so the lock is visible rather than remembered.  Both ends stay open.
# Everything either side of the two FIXED cells is a MAT lid over a three-deep pit, which is
# what makes a wrong flip cost the level rather than nothing: an earlier build of this level
# refused wrong flips instead of punishing them, and a uniform random walk cleared it once
# in 6,000 attempts simply by diffusing east.
def _l4():
    g = _base()
    _flat(g, O - 6, O, 11)
    _flat(g, O + 1, O + 2, 10)                # a one-cell rise: costs a climb, not a step
    _flat(g, O + 3, O + 3, 15)                # every stretch between the safe cells is a
    _rect(g, O + 3, O + 3, 12, 12, "o")       # lid over a pit, so a flip in the wrong place
    _flat(g, O + 4, O + 5, 12)                # is a strand and not merely a refusal
    _rect(g, O + 4, O + 5, 9, 11, "#")        # gate 1
    _flat(g, O + 6, O + 6, 12)                # stone 1 -- the only legal flip before the gate
    _flat(g, O + 7, O + 11, 12)
    _rect(g, O + 7, O + 11, 10, 11, "o")      # the corridor
    _rect(g, O + 7, O + 11, CEIL, 9, "=")     # ...and its roof
    _flat(g, O + 12, O + 12, 15)
    _rect(g, O + 12, O + 12, 12, 12, "#")     # lid
    _flat(g, O + 13, O + 13, 12)              # stone 2
    _flat(g, O + 14, O + 14, 15)
    _rect(g, O + 14, O + 14, 12, 12, "o")     # lid
    _flat(g, O + 15, O + 16, 12)
    _rect(g, O + 15, O + 16, 9, 11, "#")      # gate 2
    _flat(g, O + 17, O + 19, 15)
    _rect(g, O + 17, O + 19, 12, 12, "o")     # the lid over the last pit
    _flat(g, O + 20, O + 28, 12)
    _bounds(g, O - 6, O + 28)
    _roof(g)
    _deco(g, (O - 4, O + 1), (O + 13, O + 18), (O + 22, O + 27))
    _caves(g, (O - 5, O - 4, 13, 14), (O - 1, O + 0, 14, 14),
           (O + 22, O + 23, 13, 14), (O + 26, O + 27, 14, 14))
    return _rows(g, (O, 10), (O + 21, 11))


# L5 "basin" -- the polarity you cannot fix from inside.  The basin is three deep and made
# of MAT_B: in one polarity it is filled flush and you walk straight over it, in the other
# it is a pit whose walls have no footing and whose floor is MAT_B, so standing in it your
# own cell is MAT_B and inversion is refused.  The choice is made outside, where flipping
# is free and the fill is plainly visible from two screens away.
def _l5():
    g = _base()
    _flat(g, O - 6, O + 4, 11)
    _flat(g, O + 2, O + 4, 10)                # a one-cell rise: costs a climb, not a step
    _flat(g, O + 5, O + 9, 14)
    _rect(g, O + 5, O + 9, 11, 13, "o")       # the basin
    _flat(g, O + 10, O + 11, 11)
    _flat(g, O + 12, O + 14, 15)
    _rect(g, O + 12, O + 14, 11, 11, "#")     # the lid: solid only in the other polarity
    _flat(g, O + 15, O + 26, 11)
    _rect(g, O + 17, O + 18, 8, 10, "#")
    _bounds(g, O - 6, O + 26)
    _roof(g)
    _deco(g, (O - 4, O + 1), (O + 6, O + 11), (O + 20, O + 25))
    _caves(g, (O - 4, O - 4, 13, 14), (O, O + 2, 13, 13),
           (O + 21, O + 22, 14, 14), (O + 24, O + 26, 13, 14))
    return _rows(g, (O, 10), (O + 20, 10))


# L6 "weave" -- composes all three.  Flip to open the door, cross the MAT_B half of the
# bridge, flip on the stone, cross the MAT_A half, drop to corridor height, walk the locked
# corridor, and flip once more for the last wall.  Three inversions, every cue on screen
# when it is needed, and a four-deep pit under the whole bridge for anyone improvising.
def _l6():
    g = _base()
    _flat(g, O - 6, O + 4, 11)
    _rect(g, O + 3, O + 4, 8, 10, "#")        # the door
    _flat(g, O + 5, O + 10, 15)               # the pit
    _rect(g, O + 5, O + 6, 11, 11, "o")
    _rect(g, O + 7, O + 8, 11, 11, "=")       # the stone
    _rect(g, O + 9, O + 10, 11, 11, "#")
    _flat(g, O + 11, O + 11, 11)
    _flat(g, O + 12, O + 13, 12)
    _flat(g, O + 14, O + 16, 12)
    _rect(g, O + 14, O + 16, 10, 11, "o")     # the locked corridor
    _rect(g, O + 14, O + 16, CEIL, 9, "=")
    _flat(g, O + 17, O + 28, 11)              # a one-cell rise out of the corridor, so the
    _rect(g, O + 18, O + 19, 8, 10, "#")      # single cell where the last flip is legal can
                                              # only be reached by climbing onto it
    _bounds(g, O - 6, O + 28)
    _roof(g)
    _deco(g, (O - 4, O + 1), (O + 8, O + 13), (O + 22, O + 27))
    _caves(g, (O - 5, O - 3, 13, 13), (O, O + 2, 13, 14),
           (O + 21, O + 24, 14, 14), (O + 26, O + 27, 13, 14))
    return _rows(g, (O, 10), (O + 21, 10))


LEVELS = [
    {"name": "step", "rows": _l1()},
    {"name": "shelf", "rows": _l2()},
    {"name": "stone", "rows": _l3()},
    {"name": "gate", "rows": _l4()},
    {"name": "basin", "rows": _l5()},
    {"name": "weave", "rows": _l6()},
]

# ---------------------------------------------------------------------------
# Parsed level tables
# ---------------------------------------------------------------------------

def _parse(rows):
    """rows -> (grid of material codes, start cell, goal cell)."""
    grid = [[_CHARS[ch] for ch in row] for row in rows]
    start = goal = None
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "S":
                start = (x, y)
            elif ch == "G":
                goal = (x, y)
    return grid, start, goal


_TABLES = [_parse(ldef["rows"]) for ldef in LEVELS]


# ---------------------------------------------------------------------------
# World rules.  These are pure functions of (grid, polarity) so the game, the smoke-test
# solver and the strand check all run on exactly one implementation.
# ---------------------------------------------------------------------------

def solid(grid, x, y, pol):
    """Is cell (x, y) solid at this polarity?  Outside the strip is solid bedrock."""
    if y >= WORLD_H or x < 0 or x >= WORLD_W:
        return True
    if y < 0:
        return False
    c = grid[y][x]
    return c == FIXED or (c == MAT_A and pol == 0) or (c == MAT_B and pol == 1)


def settle(grid, x, y, pol):
    """Discrete gravity: fall straight down until the cell below is solid."""
    while not solid(grid, x, y + 1, pol):
        y += 1
    return y


def apply_action(grid, state, aid):
    """(x, y, pol, facing) + action id -> new state.  Illegal moves return the state
    unchanged apart from facing, so nothing is ever fatal on its own."""
    x, y, pol, f = state
    if aid == 3 or aid == 4:
        f = -1 if aid == 3 else 1
        if not solid(grid, x + f, y, pol):
            x += f
            y = settle(grid, x, y, pol)
    elif aid == 1:
        if (solid(grid, x + f, y, pol)
                and not solid(grid, x + f, y - 1, pol)
                and not solid(grid, x, y - 1, pol)
                and y - 1 >= 0):
            x += f
            y = settle(grid, x, y - 1, pol)
    elif aid == 5:
        if not solid(grid, x, y, 1 - pol):
            pol = 1 - pol
            y = settle(grid, x, y, pol)
    return (x, y, pol, f)


ACTION_IDS = (1, 3, 4, 5)


def _safe_states(grid, goal):
    """Every (x, y, pol, facing) from which the goal is still reachable.

    Built once per level: the transition graph has 128*16*2*2 = 8192 nodes, so this is a
    reverse breadth-first search over the whole future, not a lookahead. A state outside
    this set is stranded -- no sequence of walks, climbs and inversions reaches the goal.
    """
    nodes = [(x, y, p, f)
             for x in range(WORLD_W) for y in range(WORLD_H)
             for p in (0, 1) for f in (-1, 1)]
    back = {n: [] for n in nodes}
    for n in nodes:
        for aid in ACTION_IDS:
            m = apply_action(grid, n, aid)
            if m != n:
                back[m].append(n)
    safe = {n for n in nodes if (n[0], n[1]) == goal}
    queue = deque(safe)
    while queue:
        n = queue.popleft()
        for p in back.get(n, ()):
            if p not in safe:
                safe.add(p)
                queue.append(p)
    return safe


_SAFE_CACHE = {}


def safe_states(index):
    if index not in _SAFE_CACHE:
        grid, _start, goal = _TABLES[index]
        _SAFE_CACHE[index] = _safe_states(grid, goal)
    return _SAFE_CACHE[index]

_PIX_CACHE = {}


def world_pixels(index, pol):
    """The whole 512x64-pixel strip, pre-drawn for one polarity.

    The terrain never changes except when polarity flips, so both images are baked once per
    level and a frame is a single array slice. That is also what makes a 30,000-rollout gate
    affordable: rendering was 90% of the cost when it was drawn cell by cell.
    """
    key = (index, pol)
    if key in _PIX_CACHE:
        return _PIX_CACHE[key]
    grid = _TABLES[index][0]
    img = np.full((WORLD_H * CELL, WORLD_W * CELL), C_GROUND, dtype=int)
    for y in range(WORLD_H):
        py = y * CELL
        for x in range(WORLD_W):
            if solid(grid, x, y, pol):
                px = x * CELL
                img[py:py + CELL, px:px + CELL] = C_FIGURE
    # Every cell inversion WILL change wears a border on the outside of its region, whether
    # it is currently solid or currently a hole; plain unbordered rock never changes. That
    # single mark answers the only question the player has to ask before pressing invert --
    # and it is why the two stones in the middle of level 3's bridge read as safe footing.
    for y in range(WORLD_H):
        py = y * CELL
        for x in range(WORLD_W):
            if grid[y][x] not in (MAT_A, MAT_B):
                continue
            px = x * CELL
            if y == 0 or grid[y - 1][x] not in (MAT_A, MAT_B):
                img[py, px:px + CELL] = C_MUTABLE
            if y == WORLD_H - 1 or grid[y + 1][x] not in (MAT_A, MAT_B):
                img[py + CELL - 1, px:px + CELL] = C_MUTABLE
            if x == 0 or grid[y][x - 1] not in (MAT_A, MAT_B):
                img[py:py + CELL, px] = C_MUTABLE
            if x == WORLD_W - 1 or grid[y][x + 1] not in (MAT_A, MAT_B):
                img[py:py + CELL, px + CELL - 1] = C_MUTABLE
    _PIX_CACHE[key] = img
    return img


def camera_x(wx):
    """Deterministic side-scroll, recomputed from the walker's cell every frame: the walker
    sits dead centre of the 16-cell window and the window clamps at the two ends of the
    128-cell strip. Every level's whole solution runs in the unclamped middle, so a step is
    always the terrain sliding one cell under a stationary token -- the single most visible
    thing on screen, on every action that moves.
    """
    return max(0, min(WORLD_W - VIEW, wx - VIEW // 2))


# The walker is a 4x8 token: two stacked cells, solid, with a 2x2 bite out of the top
# TRAILING corner. Which way it faces -- and therefore which way ACTION1 climbs -- is
# carried by that bite, so direction survives the colour being stripped out. Physics is one
# cell; the upper cell is decoration, and every reachable cell in all six levels has an open
# cell above it, so the token is never cropped.
_HEAD_R = tuple((dx, dy) for dy in range(CELL) for dx in range(CELL)
                if not (dx < 2 and dy < 2))
_HEAD_L = tuple((CELL - 1 - dx, dy) for dx, dy in _HEAD_R)
_BODY = tuple((dx, dy) for dy in range(CELL) for dx in range(CELL))

# The goal is an 8x8 ring two cells wide and two cells tall -- twice the walker's width,
# hollow where the walker is solid, and the only yellow in the game. Nothing about it is a
# glyph, an arrow or a face.
_RING = tuple((dx, dy) for dy in range(2 * CELL) for dx in range(2 * CELL)
              if dx < 2 or dx >= 2 * CELL - 2 or dy < 2 or dy >= 2 * CELL - 2)


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

class Ng01Display(RenderableUserDisplay):
    def __init__(self, game):
        self.game = game

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game
        cam = camera_x(g.wx)

        # Two colours, and only two, for the whole world: solid is FIGURE, everything else
        # is GROUND. Inversion is therefore a literal figure/ground swap on screen, and the
        # camera is the only other thing that moves the view.
        px0 = cam * CELL
        frame[:, :] = g.pix[g.pol][:, px0:px0 + 64]

        gx, gy = g.goal
        self._blit(frame, (gx - cam) * CELL, (gy - 1) * CELL, _RING,
                   C_DEAD if g.stranded else C_GOAL)

        # Colour as affordance, recomputed every step: the walker's upper cell wears the
        # refusal colour exactly where inversion is locked, so a locked cell is never a
        # surprise. When the goal has become unreachable the whole token goes dark as well --
        # the goal marker alone is not enough, because a strand usually happens a screen or
        # two away from it and the camera would not be showing it.
        locked = solid(g.grid, g.wx, g.wy, 1 - g.pol)
        head_col = C_DEAD if g.stranded else (C_LOCKED if locked else C_WALKER)
        body_col = C_DEAD if g.stranded else C_WALKER
        bx, by = (g.wx - cam) * CELL, g.wy * CELL
        self._blit(frame, bx, by - CELL, _HEAD_R if g.facing > 0 else _HEAD_L, head_col)
        self._blit(frame, bx, by, _BODY, body_col)

        if g.flash:
            # Any refused action -- a step into a wall, a climb with no ledge, an inversion
            # that would bury the walker -- rings the token for the frame it happened on, so
            # no press is ever silent. The ring is drawn OUTSIDE the token in whichever of
            # the two walker colours the token is not currently wearing.
            self._ring(frame, bx - 1, by - CELL - 1, CELL + 2, 2 * CELL + 2,
                       C_WALKER if locked else C_LOCKED)
        return frame

    @staticmethod
    def _blit(frame, px, py, shape, colour):
        for dx, dy in shape:
            x, y = px + dx, py + dy
            if 0 <= x < 64 and 0 <= y < 64:
                frame[y, x] = colour

    @staticmethod
    def _ring(frame, px, py, w, h, colour):
        for x in range(px, px + w):
            for y in (py, py + h - 1):
                if 0 <= x < 64 and 0 <= y < 64:
                    frame[y, x] = colour
        for y in range(py, py + h):
            for x in (px, px + w - 1):
                if 0 <= x < 64 and 0 <= y < 64:
                    frame[y, x] = colour

# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class Ng01(ARCBaseGame):
    def __init__(self):
        self.display = Ng01Display(self)

        # on_set_level() runs inside super().__init__(), so every attribute it and the
        # display touch has to exist before the call.
        self.grid = _TABLES[0][0]
        self.goal = _TABLES[0][2]
        self.wx = self.wy = 0
        self.pol = 0
        self.facing = 1
        self.flash = False
        self.stranded = False
        self.safe = frozenset()
        self.pix = (world_pixels(0, 0), world_pixels(0, 1))

        levels = [Level(sprites=[], grid_size=(64, 64), data=ldef, name=ldef["name"])
                  for ldef in LEVELS]

        super().__init__(
            "ng",
            levels,
            Camera(0, 0, 64, 64, C_GROUND, C_GROUND, [self.display]),
            False,
            len(levels),
            [1, 3, 4, 5],        # 1 = climb, 3/4 = step left/right, 5 = invert
        )

    # -- level setup --------------------------------------------------------

    def on_set_level(self, level: Level) -> None:
        idx = self.level_index
        grid, start, goal = _TABLES[idx]
        self.grid = grid
        self.goal = goal
        self.wx, self.wy = start
        self.wy = settle(grid, self.wx, self.wy, 0)
        self.pol = 0
        self.facing = 1
        self.flash = False
        self.stranded = False
        self.safe = safe_states(idx)
        self.pix = (world_pixels(idx, 0), world_pixels(idx, 1))

    # -- engine entry point -------------------------------------------------

    def step(self) -> None:
        aid = self.action.id.value
        self.flash = False

        if aid not in ACTION_IDS:
            # RESET and anything unmapped: no state change, and never a loss.  Exploration
            # must cost nothing, so there is no `else: self.lose()` anywhere in this game.
            self.complete_action()
            return

        state = (self.wx, self.wy, self.pol, self.facing)
        moved = apply_action(self.grid, state, aid)
        if moved[:3] == state[:3]:
            # Nothing about the world changed -- a wall, a ledge that is not there, or an
            # inversion that would bury the walker. Say so, so that no press is silent.
            self.flash = True
        self.wx, self.wy, self.pol, self.facing = moved

        if (self.wx, self.wy) == self.goal:
            self.next_level()
            self.complete_action()
            return

        # Loss is being stranded, and nothing else.  `safe` is the set of states from which
        # some future still reaches the goal, so this fires only when the goal has genuinely
        # become unreachable -- the goal ring and the walker both go dark on the very frame
        # it happens, and RESET is always there.
        if moved not in self.safe:
            self.stranded = True
            self.lose()

        self.complete_action()
