# Author: Claude Opus 5
# Date: 2026-09-12 (first cut 2026-09-07)
# PURPOSE: ng01 "Negative" -- an ARC-AGI-3 environment. The world is a 128-cell strip, eight
#   viewports wide; the 64x64 frame is a camera locked to the walker, so the world slides
#   under a stationary token and every step visibly redraws the screen. The strip is drawn
#   in exactly two colours: FIGURE (solid) and GROUND (passable). LEFT/RIGHT step one cell,
#   gravity is discrete and immediate, UP climbs a single step in front. ACTION5 inverts the
#   world: the solid family and the hole family trade places, so the block you stood on
#   becomes the hole and the holes become your floor -- staircases move to the other side of
#   a pit when you press it. Loss is being STRANDED (a reverse BFS over (position, polarity)
#   says the goal is unreachable). No budget, no lives, no bar, no pips.
#   2026-09-12, after a human playtest: vertical control and the marker vocabulary were both
#   rebuilt. A climb that is available is now MARKED on the cell it would land in; a refused
#   press is a one-frame red burst on the cell that blocked it instead of a 28-pixel outline
#   that persisted, cleared on unrelated presses and could repeat identically (pressing UP
#   twice into a wall used to change zero pixels); the inversion lock is a clamp drawn on the
#   world under the walker instead of a blue tint on half the token; ACTION2 is answered
#   rather than swallowed; and the scenery is cut by a seeded LCG into irregular hooks and
#   notches, because a tile list of same-size rectangles on a flat field read as a facade.
# SRP/DRY check: Pass -- self-contained environment. Nothing in the catalogue inverts
#   figure/ground, and the side-scrolling camera is new to this repo.
"""Negative -- walk right, and flip the world when the floor runs out.

ACTION3 / ACTION4 step one cell left / right (gravity pulls you down immediately).
ACTION1 climbs a one-cell step in front of you.  Whenever that climb is available the cell
it would land in is drawn as a light-blue hollow cell sitting on a light-blue lip, so the
key is pressed at a mark rather than pressed hopefully.
ACTION5 inverts the world.  It is refused when your own cell would turn solid, and a cell
where that is true wears a blue clamp around its floor and sides -- the lock is a property
of a place on the board, not a tint on the walker.
ACTION2 is not an action: gravity is immediate, so there is nothing to descend into.  It is
answered rather than swallowed -- the tile underfoot flashes red and the token shoves into
it -- and it is left out of available_actions so it costs an agent nothing.

Any refused press fills the cell that blocked it with red for exactly one frame and shoves
the token into it, by one pixel or two alternately so that two refusals running are never
the same picture.  Red appears nowhere else and never persists.

6 levels, 20-24 actions each. No RNG, no timer, no score and no counter of any kind.
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
C_GOAL = C_YELLOW          # goal ring, still reachable
C_DEAD = C_VDGRAY          # goal and walker once stranded -- the only dark pixels in the game

# Three marks, three jobs, and each one is a different colour AND a different shape in a
# different place, because the first build used one blue for two meanings and a playtester
# read the pair as random highlighting:
C_STEP = C_LBLUE           # STATUS, on the world ahead: the cell a climb would land in
C_CLAMP = C_BLUE           # STATUS, on the world underfoot: a socket where inversion is off
C_REFUSE = C_RED           # EVENT, one frame only: that press did nothing, and here is why

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

# Terrain is cut by a seeded 32-bit LCG rather than by a repeating tile list.  A tile list
# is what made the first build read as a building: the same chunk width and the same block
# height came back every N columns, and a regular grid of same-size rectangles on a flat
# field is a facade whatever colour it is painted.  The LCG is a pure function of its seed,
# so the world is still byte-identical on every run, but nothing in it repeats.
def _rnd(seed):
    """Deterministic integer stream.  nxt(lo, hi) -> lo..hi inclusive."""
    box = [(seed * 2654435761 + 97) & 0x7FFFFFFF]

    def nxt(lo, hi):
        box[0] = (1103515245 * box[0] + 12345) & 0x7FFFFFFF
        return lo + (box[0] >> 13) % (hi - lo + 1)
    return nxt


def _blank():
    """A world of open sky under a two-row bedrock roof."""
    g = [["."] * WORLD_W for _ in range(WORLD_H)]
    for y in range(CEIL):
        g[y] = ["="] * WORLD_W
    return g


def _skyline(g, seed, ch="="):
    """The background massif: chunks of 2-6 columns whose tops wander over rows 7-14, with
    a one-column notch every few cells so no ledge is ever a clean repeated rectangle."""
    nxt = _rnd(seed)
    x, top = 0, 11
    while x < WORLD_W:
        w = nxt(2, 6)
        top = max(7, min(14, top + nxt(-3, 3)))
        for _ in range(w):
            if x >= WORLD_W:
                return
            t = top if nxt(0, 4) else max(7, min(14, top + nxt(-2, 2)))
            for y in range(t, WORLD_H):
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

def _sky(g, seed):
    """Floating chunks between the roof and the play rows, cut to no two alike: widths 2-6,
    heights 1-3, tops anywhere in rows 4-7, spacing 2-6, and each one is MAT_A or MAT_B.

    Two jobs.  Visually they break the sky into an irregular scatter instead of a ruled band
    of same-size slabs.  Mechanically they are what makes inversion visible EVERYWHERE: they
    are seeded across the full 128-cell strip, so every camera position has mutable matter in
    it and a successful flip always repaints a large part of the frame, even out in the dead
    ground past the level's bounding walls.

    Physics-inert by construction.  No walkable surface in any level is above row 9, a climb
    needs the walker's own row-8 headroom clear, and nothing here is written below row 7."""
    nxt = _rnd(seed)
    x = 2
    while x < WORLD_W - 2:
        # Two overlapping lobes of different width, height and top, so the silhouette is a
        # step or a hook.  A plain rectangle here is what read as a window: give every chunk
        # at least one re-entrant corner and the scatter stops looking like glazing.
        ch = "#" if nxt(0, 1) else "o"
        # Never one row tall: a 4-pixel slab with a border top and bottom is a dash, and a
        # line of dashes at a constant height is a rule -- the exact regularity being cut out.
        # And the second lobe always juts out, sideways and vertically both, so no chunk can
        # come out a plain rectangle: a purple-outlined rectangle in a field is a window.
        w, h, y0 = nxt(2, 5), nxt(2, 3), nxt(3, 5)
        lw, lh = nxt(1, 3), nxt(2, 3)
        lx = x + w - 1 if nxt(0, 1) else x - lw + 1
        ly = y0 - 1 if nxt(0, 1) else y0 + h - 1
        lobes = [(x, w, y0, h), (lx, lw, ly, lh)]
        for lx, lw, ly, lh in lobes:
            for xx in range(lx, min(lx + lw, WORLD_W)):
                for yy in range(max(3, ly), min(ly + lh, 8)):
                    if g[yy][xx] == ".":
                        g[yy][xx] = ch
        x += w + nxt(2, 6)


# The roof hangs 2-5 rows deep in runs of 2-6 columns, with a one-column step every few
# cells, so the top edge of the frame is a ragged overhang and never a ruled 8-pixel band.
# Nothing walkable comes within four rows of the deepest chunk.
def _roof(g, seed):
    nxt = _rnd(seed)
    x = 0
    while x < WORLD_W:
        w, d = nxt(2, 6), nxt(2, 5)
        for _ in range(w):
            if x >= WORLD_W:
                return
            dd = d if nxt(0, 3) else nxt(2, 5)
            for y in range(dd):
                if g[y][x] == ".":
                    g[y][x] = "="
            x += 1


def _pocket(g, cells, ch):
    """Write an arbitrary sealed blob into the bedrock, or write nothing.

    A blob is only cut where every cell touching it -- all eight neighbours of every cell in
    it, diagonals included -- is FIXED, so no fall, no step and no inversion can ever reach
    the inside of one.  Because the shape is passed in as a cell list rather than a
    rectangle, pockets can be L-shaped, stepped or ragged."""
    cells = [(x, y) for x, y in cells if 0 <= x < WORLD_W and 0 <= y < WORLD_H]
    if not cells:
        return
    body = set(cells)
    for x, y in cells:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                n = (x + dx, y + dy)
                if n in body or n[1] >= WORLD_H:
                    continue
                if not 0 <= n[0] < WORLD_W or g[n[1]][n[0]] != "=":
                    return
    for x, y in cells:
        g[y][x] = ch


def _pockets(g, seed):
    """The deep mass at the bottom of the frame, broken up.

    The first build put one rectangle of a single size in one row of the bedrock every few
    columns, which is a row of windows in a wall and is exactly the real-world resemblance
    ARC bans.  These are the opposite: two overlapping bites of different widths at different
    depths, so the blob is a step or an L rather than a rectangle; the top row wanders over
    rows 11-14; and about a third of them are MAT rather than VOID, so they appear and vanish
    when the world inverts instead of sitting there as fixed holes."""
    nxt = _rnd(seed)
    x = 1
    while x < WORLD_W - 2:
        if nxt(0, 2) == 0:                 # ragged gaps, so the blobs are not evenly pitched
            x += nxt(2, 6)
            continue
        # Two bands.  The shallow one cuts into thick roof and into the lids over the locked
        # corridors, which is what gives those stretches any column-to-column variety at all.
        # The deep one breaks up the floor mass, and because that mass is only three rows
        # thick it is cut as NOTCHES that run off the bottom of the frame rather than as
        # closed holes: a closed hole in a three-row band lines up with its neighbours at the
        # only depth that fits, and a line of same-depth holes in a wall is a row of windows.
        deep = nxt(0, 2) > 0
        w = nxt(1, 5)
        y0 = nxt(12, 14) if deep else nxt(3, 8)
        h = (WORLD_H - y0) if deep and nxt(0, 3) else nxt(1, 3)
        ch = "." if nxt(0, 2) else ("#" if nxt(0, 1) else "o")
        cells = [(xx, yy) for xx in range(x, x + w)
                 for yy in range(y0, min(y0 + h, WORLD_H))]
        # a second bite of a different width, offset sideways and dropped a row or two, so
        # the blob is an L or a step and never a clean rectangle
        off = nxt(0, 1)
        w2, h2 = max(1, w - off - nxt(1, 2)), nxt(1, 2)
        cells += [(xx, yy) for xx in range(x + off, x + off + w2)
                  for yy in range(y0 + h, min(y0 + h + h2, WORLD_H))]
        # ...and sometimes a narrower bite on TOP as well, which is what stops the blobs
        # sharing a top edge. In a mass only three rows deep a common top edge is the
        # regularity that reads as a row of openings however ragged the bottoms are.
        if nxt(0, 1) and y0 > 0:
            tw, toff = max(1, w - nxt(0, 2)), nxt(0, 1)
            cells += [(xx, y0 - 1) for xx in range(x + toff, x + toff + tw)]
        _pocket(g, cells, ch)
        # Step by one or two columns, not by the blob's own width: most attempts then fail
        # the enclosure check (their neighbours are no longer FIXED) and the ones that
        # succeed cluster irregularly, which is both denser cover and less regular spacing
        # than walking the strip in blob-sized strides.
        x += nxt(1, 2)


def _bounds(g, west, east):
    """Three-cell step-ups that close the play region on both sides.  A one-cell climb
    cannot take them, so wandering off is cheap and never fatal -- it just ends at a wall."""
    _flat(g, west - 8, west - 1, 8)
    _flat(g, east + 1, east + 8, 8)


def _base(seed):
    g = _blank()
    _skyline(g, seed)
    return g


def _finish(g, seed):
    """Everything that is cut after a level has said what it wants: the overhang, the sky
    scatter and the sealed pockets, each on its own stream so the three layers do not line
    up with each other.  Run last, and all three only ever write into open cells, so a level
    feature is never overwritten by scenery."""
    _roof(g, seed + 101)
    _sky(g, seed + 211)
    _pockets(g, seed + 307)
    _pockets(g, seed + 409)    # a second sweep on its own stream: it lands where the first
                               # did not, and it cannot touch the first's blobs because they
                               # are no longer FIXED and so fail its enclosure check


# Every level's play region starts at this column, so the strip runs 40 cells off the left
# of the camera and 50 off the right: the frame is never the world, and what is ahead is
# genuinely hidden until the camera brings it in.
O = 40


# L1 "step" -- walking, the camera, the climb, and both directions of the flip.  The floor
# is FIXED end to end and the two doors are single columns, so inversion can never affect
# the ground: level 1 is strand-proof by construction and machine-checked to be so.  The
# sky scatter overhead is all MAT_A/MAT_B and swaps in place on the first press, so the very
# first inversion repaints a large part of the screen with no consequence at all.
def _l1():
    g = _base(11)
    _flat(g, O - 6, O + 26, 11)
    _rect(g, O + 3, O + 4, 10, 15, "=")       # the step: two cells wide, one cell up
    _rect(g, O + 7, O + 8, 8, 10, "#")        # door A -- shut until you invert
    _rect(g, O + 11, O + 12, 8, 10, "o")      # door B -- shut once you have
    _bounds(g, O - 6, O + 26)
    _finish(g, 11)
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
    g = _base(23)
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
    _finish(g, 23)
    return _rows(g, (O, 10), (O + 21, 9))


# L3 "stone" -- the pit inversion cannot undo.  Two FIXED stones are the only planks in the
# bridge that survive a flip, and they are the only unbordered cells over the pit, so where
# it is safe to press invert is drawn on the board.  Flipping anywhere else drops you four
# cells onto a floor with no footing at all: that is the strand, and it is what ends every
# policy that presses invert on a timer.
def _l3():
    g = _base(37)
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
    _finish(g, 37)
    return _rows(g, (O, 10), (O + 20, 10))


# L4 "gate" -- the inversion-locked corridor.  A MAT_A wall forces the flip; the corridor
# past it is two rows of MAT_B under a solid roof, so it is a plug in that same polarity and
# you must flip back on the one FIXED cell between them.  Inside, your own cell is MAT_B and
# inversion is refused for the whole length -- the cell under the walker wears the blue
# clamp the moment it steps in, so the lock is visible rather than remembered, and it stays
# drawn for every cell of the corridor rather than blinking.  Both ends stay open.
# Everything either side of the two FIXED cells is a MAT lid over a three-deep pit, which is
# what makes a wrong flip cost the level rather than nothing: an earlier build of this level
# refused wrong flips instead of punishing them, and a uniform random walk cleared it once
# in 6,000 attempts simply by diffusing east.
def _l4():
    g = _base(51)
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
    _finish(g, 51)
    return _rows(g, (O, 10), (O + 21, 11))


# L5 "basin" -- the polarity you cannot fix from inside.  The basin is three deep and made
# of MAT_B: in one polarity it is filled flush and you walk straight over it, in the other
# it is a pit whose walls have no footing and whose floor is MAT_B, so standing in it your
# own cell is MAT_B and inversion is refused.  The choice is made outside, where flipping
# is free and the fill is plainly visible from two screens away.
def _l5():
    g = _base(67)
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
    _finish(g, 67)
    return _rows(g, (O, 10), (O + 20, 10))


# L6 "weave" -- composes all three.  Flip to open the door, cross the MAT_B half of the
# bridge, flip on the stone, cross the MAT_A half, drop to corridor height, walk the locked
# corridor, and flip once more for the last wall.  Three inversions, every cue on screen
# when it is needed, and a four-deep pit under the whole bridge for anyone improvising.
def _l6():
    g = _base(83)
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
    _finish(g, 83)
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


def climb_target(grid, x, y, pol, f):
    """The cell ACTION1 would land the walker in, or None if the climb is refused here.

    One function, three callers: the move itself, the mark the display draws on that cell
    before the key is pressed, and the smoke test's zero-pixel audit.  Keeping them on one
    implementation is what makes the promise "if the step is marked, UP works" true rather
    than merely intended.
    """
    if y - 1 < 0:
        return None
    if (solid(grid, x + f, y, pol)
            and not solid(grid, x + f, y - 1, pol)
            and not solid(grid, x, y - 1, pol)):
        return (x + f, settle(grid, x + f, y - 1, pol))
    return None


def refusal(grid, state, aid):
    """What stopped this press: (cell to flash, shove_x, shove_y).

    Every refused press names a cell on the board rather than tweaking a marker on the
    walker, so the answer to "why didn't that work" is drawn where the obstacle is.
    """
    x, y, pol, f = state
    if aid in (3, 4):
        d = -1 if aid == 3 else 1
        return ((x + d, y), d, 0)                 # a wall beside you
    if aid == 1:
        if not solid(grid, x + f, y, pol):
            return ((x + f, y), f, 0)             # nothing in front to climb onto
        if solid(grid, x + f, y - 1, pol):
            return ((x + f, max(0, y - 1)), f, -1)  # that is a wall, not a one-cell step
        return ((x, max(0, y - 1)), 0, -1)        # no headroom above your own cell
    if aid == 5:
        return ((x, y), 0, 1)                     # your own cell would close on you
    return ((x, min(WORLD_H - 1, y + 1)), 0, 1)   # ACTION2: you are already on the ground


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
        t = climb_target(grid, x, y, pol, f)
        if t is not None:
            x, y = t
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

# The climb mark: a hollow cell where the walker would land, sitting on a two-pixel lip
# drawn across the top of the block it would climb. Together they read as one marked step,
# and they are drawn only while ACTION1 would actually work.
_STEP_CELL = tuple((dx, dy) for dy in range(CELL) for dx in range(CELL)
                   if dx in (0, CELL - 1) or dy in (0, CELL - 1))
_STEP_LIP = tuple((dx, dy) for dy in range(2) for dx in range(CELL))

# The lock clamp: a two-pixel socket around the bottom and both sides of the cell the walker
# is standing in. It is on the world, not on the walker -- the token keeps its own colour and
# its facing bite, and what changes is that the cell is visibly held shut.
_CLAMP = tuple(sorted(set(
    [(dx, dy) for dx in (-2, -1, CELL, CELL + 1) for dy in range(CELL + 2)]
    + [(dx, dy) for dx in range(-2, CELL + 2) for dy in (CELL, CELL + 1)])))


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

        bx, by = (g.wx - cam) * CELL, g.wy * CELL

        # Colour as affordance, recomputed every step, and both affordances are drawn ON THE
        # WORLD rather than on the token. Where a climb is available the landing cell is
        # marked, so ACTION1 is a key you press at a mark instead of a key you press hopefully
        # and watch do nothing. Where inversion is locked the cell the walker stands in wears
        # a clamp, so the lock is a property of a place.
        if not g.stranded:
            step = climb_target(g.grid, g.wx, g.wy, g.pol, g.facing)
            if step is not None:
                sx, sy = step
                self._blit(frame, (sx - cam) * CELL, sy * CELL, _STEP_CELL, C_STEP)
                self._blit(frame, (sx - cam) * CELL, (sy + 1) * CELL, _STEP_LIP, C_STEP)
            if solid(g.grid, g.wx, g.wy, 1 - g.pol):
                self._blit(frame, bx, by, _CLAMP, C_CLAMP)

        # When the goal has become unreachable the whole token goes dark -- the goal marker
        # alone is not enough, because a strand usually happens a screen or two from it and
        # the camera would not be showing it.
        col = C_DEAD if g.stranded else C_WALKER
        ox = oy = 0
        if g.flash and not g.stranded:
            # A refused press is an EVENT, not a status. For exactly one frame the cell that
            # blocked it is filled solid red and the walker sits inside a solid red burst,
            # shoved into the obstacle. The old build drew a one-pixel outline instead: 28
            # pixels, the same 28 pixels every time, so a second refusal changed nothing at
            # all and the outline read as a status colour. This cannot be read as a status --
            # it is the only red in the game and it is gone on the next press -- and the
            # burst grows by two pixels on the alternate press, so two refusals running are
            # never the same picture.
            (fx, fy), dx, dy = g.flash
            grow = 1 + g.pulse
            ox, oy = dx * grow, dy * grow
            self._blit(frame, (fx - cam) * CELL, fy * CELL, _BODY, C_REFUSE)
            self._fill(frame, bx - grow, by - CELL - grow,
                       CELL + 2 * grow, 2 * CELL + 2 * grow, C_REFUSE)
        self._blit(frame, bx + ox, by - CELL + oy,
                   _HEAD_R if g.facing > 0 else _HEAD_L, col)
        self._blit(frame, bx + ox, by + oy, _BODY, col)

        return frame

    @staticmethod
    def _blit(frame, px, py, shape, colour):
        for dx, dy in shape:
            x, y = px + dx, py + dy
            if 0 <= x < 64 and 0 <= y < 64:
                frame[y, x] = colour

    @staticmethod
    def _fill(frame, px, py, w, h, colour):
        x0, y0 = max(0, px), max(0, py)
        x1, y1 = min(64, px + w), min(64, py + h)
        if x1 > x0 and y1 > y0:
            frame[y0:y1, x0:x1] = colour

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
        self.flash = None
        self.pulse = 0
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
        self.flash = None
        self.pulse = 0
        self.stranded = False
        self.safe = safe_states(idx)
        self.pix = (world_pixels(idx, 0), world_pixels(idx, 1))

    # -- engine entry point -------------------------------------------------

    def step(self) -> None:
        aid = self.action.id.value
        self.flash = None
        state = (self.wx, self.wy, self.pol, self.facing)

        if aid == 2:
            # ACTION2 is deliberately NOT in available_actions. Gravity here is discrete and
            # immediate -- the walker is already resting on the first solid cell beneath it
            # every single frame -- so there is no descent to perform and a declared DOWN
            # would be a key that spends the harness's budget on nothing. What it must not be
            # is silent: the tile underfoot flashes and the token shoves down into it, which
            # says "you are already on the ground" on the first press instead of leaving the
            # player to infer it from a frame that did not change.
            self.pulse ^= 1
            self.flash = refusal(self.grid, state, 2)
            self.complete_action()
            return

        if aid not in ACTION_IDS:
            # RESET and anything unmapped: no state change, and never a loss.  Exploration
            # must cost nothing, so there is no `else: self.lose()` anywhere in this game.
            self.complete_action()
            return

        moved = apply_action(self.grid, state, aid)
        if moved[:3] == state[:3]:
            # Nothing about the world changed -- a wall, a ledge that is not there, or an
            # inversion that would bury the walker. Name the cell that stopped it.
            self.pulse ^= 1
            self.flash = refusal(self.grid, state, aid)
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
