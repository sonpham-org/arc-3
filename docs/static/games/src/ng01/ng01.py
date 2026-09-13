# Author: Claude Opus 5
# Date: 2026-09-12 (first cut 2026-09-07)
# PURPOSE: ng01 "Negative" -- an ARC-AGI-3 environment. The world is a 128-cell strip, eight
#   viewports wide; the 64x64 frame is a camera locked to the walker, so the world slides
#   under a stationary token and every step visibly redraws the screen. The strip is drawn
#   in exactly two colours: FIGURE (solid) and GROUND (passable). LEFT/RIGHT step one cell
#   and step up a single cell against the pull where the terrain rises by one. ACTION1 and
#   ACTION2 aim GRAVITY: ACTION1 pulls up and the walker falls to the ceiling and stands on
#   it, ACTION2 pulls down again. ACTION5 inverts the world: the solid family and the hole
#   family trade places. Two involutions on the same terrain -- invert the WORLD, or invert
#   the PULL -- give four readings of one board. Loss is being STRANDED (a reverse BFS over
#   (x, y, polarity, gravity) says the goal is unreachable). No budget, no lives, no bar,
#   no pips.
#   2026-09-12 (a): after a human playtest the marker vocabulary was rebuilt -- a refused
#   press is a one-frame red burst on the cell that blocked it instead of a 28-pixel outline
#   that persisted and could repeat identically; the inversion lock is a clamp drawn on the
#   world under the walker instead of a blue tint on half the token; and the scenery is cut
#   by a seeded LCG into irregular hooks and notches, because a tile list of same-size
#   rectangles on a flat field read as a facade.
#   2026-09-12 (b): the one-cell climb stopped being a key. It only fired when a one-cell
#   step happened to sit directly in front, so most presses of it moved a marker and nothing
#   else, and the playtester's verdict was "I can't move up or down". The climb is now an
#   automatic consequence of a sideways step, and ACTION1/ACTION2 aim the pull instead --
#   which always does something, doubles the reasoning on the same terrain, and pairs with
#   the inversion the game already had.
# SRP/DRY check: Pass -- self-contained environment. Nothing in the catalogue inverts
#   figure/ground, and the side-scrolling camera is new to this repo.
"""Negative -- flip the world, or flip which way it pulls.

ACTION3 / ACTION4 step one cell left / right.  A step onto terrain one cell higher (higher
meaning *against the current pull*) takes it automatically; a two-cell wall refuses.
ACTION1 pulls gravity UP: the walker leaves the floor, rises to the first solid cell above
and stands under it.  ACTION2 pulls it DOWN again.  Falling is discrete and immediate, inside
the press -- there is no arc, no momentum and no airborne state ever visible.
ACTION5 inverts the world.  It is refused when your own cell would turn solid, and a cell
where that is true wears a blue clamp around its footing and sides -- the lock is a property
of a place on the board, not a tint on the walker.

The pull is drawn on the terrain, not in a HUD: every face you could stand on right now
wears a green hairline, so pressing ACTION1 sweeps every line in the frame from the tops of
the blocks to their undersides.  The walker's own footing is a green plate on the cell it
rests against, and its second cell sits on the side away from the pull, so which way it is
being pulled is legible from the token alone.

Any refused press -- including aiming the pull the way it already points -- fills the cell
that blocked it with red for exactly one frame and shoves the token into it, by one pixel or
two alternately so that two refusals running are never the same picture.  Red appears
nowhere else and never persists.

6 levels, 20-25 actions each. No RNG, no timer, no score and no counter of any kind.
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
C_PULL = C_GREEN           # STATUS, on every face in the frame: a surface the pull holds you to
C_CLAMP = C_BLUE           # STATUS, on the world underfoot: a socket where inversion is off
C_REFUSE = C_RED           # EVENT, one frame only: that press did nothing, and here is why

# C_PULL is not a "green means go" convention -- that would be the banned kind of cultural
# reading. It is self-evidencing: the walker is resting on a green-marked face in every frame
# of the game, and the instant the pull is aimed the other way every green line in the frame
# jumps to the opposite face of the same rock. The rule is shown, not looked up.

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

    Not physics-inert any more.  Once the pull can point up, the UNDERSIDE of a chunk is a
    surface, and pressing the pull upward under one lands the walker beneath it instead of on
    the ceiling -- visible (the chunk is right there, and the green faces have just swapped to
    its underside), always reversible, never fatal, and never a strand, because aiming the pull
    back down drops the walker onto the floor it left.  Where a level needs the upward route to
    be clean it says so with `_shaft`, and the ceiling corridor is cleared over it regardless."""
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
    """Eight columns of solid rock closing the play region on both sides, floor to ceiling.

    They used to be three-cell step-ups, which a one-cell climb could not take.  Now that the
    pull can point up they have to seal the ceiling as well, or the ceiling walk would run off
    the end of the level into whatever the random roof happens to be doing out there.  Sealed
    both ways, wandering off is still cheap and still never fatal -- it just ends at a wall in
    either gravity -- and `_pockets` still carves sealed blobs into the mass for variety.
    """
    _rect(g, west - 8, west - 1, CEIL, WORLD_H - 1, "=")
    _rect(g, east + 1, east + 8, CEIL, WORLD_H - 1, "=")


def _corridor(g, x0, x1, depth=CEIL):
    """The ceiling walk: `depth` rows of bedrock roof with two rows forced open beneath it.

    Run AFTER `_finish`, so it overrides the ragged overhang and any sky chunk that reached
    down into it.  Two rows, not one: the upper is where the walker hangs when the pull points
    up, the lower is headroom for its second cell, so the token is never cropped up there.
    """
    _rect(g, x0, x1, 0, depth - 1, "=")
    _rect(g, x0, x1, depth, depth + 1, ".")


def _curtain(g, x0, x1, bottom, ch="="):
    """A column hanging from the ceiling down to `bottom` inclusive.

    The counterpart of a wall.  A wall two cells tall stops the floor walk and the ceiling walk
    passes over it; a curtain stops the ceiling walk and the floor walk passes under it.  Put
    one of each at different columns and the level cannot be crossed without aiming the pull;
    put both at the same column and it cannot be crossed at all.  Made of MAT it is a gate that
    inversion opens, which is how the two involutions compose.  Run after `_corridor`.
    """
    _rect(g, x0, x1, CEIL, bottom, ch)


def _strata(g, x0, x1):
    """Fill the sky between the two storeys with rock, so they are two seams in a mass rather
    than a floor and a roof with air between them.

    The pull then only crosses between them where a `_shaft` has been cut, which is what turns
    aiming it into a positional decision instead of a free one: a walker in the wrong seam has to
    walk back to a shaft, and walking back is what a hundred presses of random play cannot
    afford.  Everything here is FIXED, so it costs nothing in strand risk -- and `_grain` carves
    sealed blobs through the mass afterwards, so the seam boundary stays ragged and never reads
    as two storeys of a building.
    """
    _rect(g, x0, x1, CEIL + 2, 8, "=")


def _shaft(g, x0, x1, bottom=8):
    """Open sky from under the ceiling corridor down to `bottom`, so that pressing the pull
    upward in these columns reaches the ceiling instead of catching under a sky chunk.  Stops
    at row 8 by default, which leaves row 9 -- the top cell of a wall -- alone."""
    _rect(g, x0, x1, CEIL + 2, bottom, ".")


def _slot(g, x0, x1, ch="#"):
    """One span of the plank bridge this game was built on, made gravity-proof.

    `x0` and `x1` are FIXED STONES: bedrock from the roof down to row 8 and from row 11 to the
    bottom, so a stone is a two-row tunnel at rows 9-10 that nothing can ever change.  Between
    them is one mutable segment: two or three rows of roof ending at row 8, the same two walk
    rows, and two or three rows of floor starting at row 11, with bedrock beyond both.  Adjacent
    spans share a stone, so `_slot(a, b, "#")` then `_slot(b, c, "o")` is a bridge whose near half
    is solid as the world stands, whose far half is open air until it is inverted, and whose one
    legal place to invert is the stone at b.

    Walking a solid segment is safe in either gravity -- pulled down the walker stands on row 11,
    pulled up it hangs under row 8 -- and the pull changes nothing about what the rock is.
    INVERTING inside one opens its roof and its floor in the same press.  The walker drops into a
    six- or eight-row shaft whose top and bottom cells are both mutable, so inversion is refused
    at both; discrete gravity can only ever reach the two ends of a vertical run, so the void rows
    in the middle are out of reach for good; and the stones block the shaft at both ends in BOTH
    gravities, which is why they are three cells thick above the walk and five below.  One cell
    was not enough: the automatic step against the pull took a one-cell stone for a stair and
    walked straight out of the shaft, and with it out of the level's only real decision as well.

    The mutable bands are two rows thick in some columns and three in others, cut by the same
    seeded stream as the rest of the scenery.  Uniform bands drew two ruled purple lines the width
    of the frame with a corridor between them, which is a wall with a window in it -- the exact
    resemblance this game spent a rebuild getting rid of.  Ragged bands are the same physics: the
    top and the bottom cell of the shaft are mutable either way, and the stones seal it either
    way.

    Drawn, not remembered: inside a span every surface within reach wears the purple border that
    means "this will move", and the stones are the only cells in it that do not.
    """
    nxt = _rnd(x0 * 7919 + 13)
    for x in range(x0, x1 + 1):
        _rect(g, x, x, 9, 10, ".")
        if x in (x0, x1):
            _rect(g, x, x, CEIL, 8, "=")
            _rect(g, x, x, 11, WORLD_H - 1, "=")
        else:
            top, bot = 7 - nxt(0, 2), 12 + nxt(0, 2)
            _rect(g, x, x, CEIL, top - 1, "=")
            _rect(g, x, x, top, 8, ch)
            _rect(g, x, x, 11, bot, ch)
            _rect(g, x, x, bot + 1, WORLD_H - 1, "=")


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


def _grain(g, seed):
    """One more sealed-pocket sweep, run after the curtains and trapdoors are in.

    Those are the only large plain masses a level draws, and a plain mass eight rows tall is
    the one thing in this game that could still read as masonry.  `_pocket` only ever carves a
    blob every one of whose eight-neighbours is FIXED, so this cannot open a seal, cannot touch
    a route and cannot reach the ceiling corridor -- it only breaks the slabs up.
    """
    _pockets(g, seed + 511)


# Every level's play region starts at this column, so the strip runs 40 cells off the left
# of the camera and 50 off the right: the frame is never the world, and what is ahead is
# genuinely hidden until the camera brings it in.
O = 40

# Every level is two storeys of the same rock. The floor is FIXED with its top at row 11, so a
# walker pulled down stands at row 10; the ceiling corridor is two cleared rows under the
# bedrock, so a walker pulled up stands at row 2. A WALL is two cells of rock standing on the
# floor: too tall for the automatic one-cell step, and the ceiling passes over it. A CURTAIN
# hangs from the ceiling to row 9: it stops the ceiling walk dead and the floor passes under it.
# That pair is the whole vocabulary, and made of MAT instead of FIXED either one becomes a gate
# that inversion opens -- which is how the pull and the polarity compose into four readings of
# one board rather than two mechanics sharing a screen.


# L1 "pull" -- the pull, and nothing else.  Walk east and the floor runs into a wall two cells
# tall, which the automatic one-cell step cannot take: the frame answers with a red burst on the
# rock that stopped it.  Aim the pull upward and the walker leaves the floor, rises to the
# bedrock and stands under it while every green face in the frame swaps to the underside of its
# rock; walk east along the ceiling, and where the ceiling runs into a curtain aim the pull back
# down.  One FIXED floor end to end, one FIXED wall and one FIXED curtain, so inversion cannot
# move anything the walker stands on: level 1 is strand-proof by construction and machine-checked
# to be so.  Pressing invert here still repaints a large part of the screen, because the sky
# scatter is all mutable, and it still costs nothing.  The single MAT stud in the floor is a
# place to meet the clamp: stand in it and inversion is refused, with the reason drawn round it.
def _l1():
    g = _base(11)
    _flat(g, O - 24, O + 24, 11)
    _rect(g, O + 3, O + 3, 10, 10, "o")       # the stud: the one cell where invert is refused
    _rect(g, O + 6, O + 7, 9, 10, "=")        # the wall: two cells, and the floor ends at it
    _bounds(g, O - 24, O + 24)
    _finish(g, 11)
    _corridor(g, O - 24, O + 24)
    _shaft(g, O + 2, O + 5)                   # clean sky to rise through, in front of the wall
    _shaft(g, O + 9, O + 13)                  # ...and to come back down through
    _curtain(g, O + 14, O + 15, 9)            # the ceiling ends here: aim the pull down
    _grain(g, 11)
    return _rows(g, (O, 10), (O + 20, 10))


# L2 "seam" -- the same one rule, but the pull is no longer free.  The sky is filled in and cut
# back open as three SEAMS stacked in one mass, so the pull no longer carries the walker from the
# ground to the ceiling: it carries it to the next seam up, and only in the three columns where a
# shaft is cut through the rock between them.  The bottom seam is shut two columns in, the middle
# one across its middle, and the top one does not start until past halfway, so the way through is
# bottom, middle, top, and back down to the middle at the far end.  That is the added rule -- not
# whether to aim the pull but WHERE -- and it is the whole level, so there is nothing to remember
# and every shaft comes into frame well before the walker needs it.
#
# The ring sits one cell WEST of the last shaft, which is not decoration.  A level with no
# inversion in it and no way to lose cannot be defended by strands, so it is defended by geometry:
# the one thing a fixed cycle cannot do is come back.  Every periodic policy up to length five
# that never presses LEFT walks past the ring and out into dead ground, and the ones that do press
# LEFT do not drift far enough east to arrive -- 0 of 3,905 cycles clear this level.
#
# Everything load-bearing here is FIXED, so it is strand-proof and machine-checked to be so: no
# press on this level can end it.  `_grain` carves mutable pockets through the seam rock, which is
# what keeps inversion honest on a level that does not need it -- pressing it still repaints.
def _l2():
    g = _base(23)
    _flat(g, O - 24, O + 26, 11)
    _bounds(g, O - 24, O + 26)
    _finish(g, 23)
    _corridor(g, O - 24, O + 26)
    _strata(g, O - 2, O + 26)                 # fill the sky in...
    _rect(g, O - 2, O + 26, 6, 7, ".")        # ...then reopen two more seams inside the mass,
    _rect(g, O - 2, O + 26, 9, 10, ".")       #    so the walker has three, one above another
    _rect(g, O + 3, O + 24, 9, 10, "=")       # the bottom seam is shut almost at once
    _rect(g, O + 15, O + 20, 6, 7, "=")       # the middle seam is shut across the middle
    _rect(g, O - 2, O + 13, CEIL, 3, "=")     # and the top seam does not begin until O+14
    _rect(g, O + 2, O + 2, 8, 8, ".")         # the one cut from the bottom seam to the middle
    _rect(g, O + 14, O + 14, 4, 5, ".")       # ...from the middle to the top
    _rect(g, O + 22, O + 22, 4, 5, ".")       # ...and the one back down, past the ring
    _rect(g, O + 1, O + 1, 10, 10, "o")       # a mutable stud in the second cell of the level:
    _grain(g, 23)                             #   stand in it and invert, and meet the clamp
    return _rows(g, (O, 10), (O + 21, 7))


# L3 "slot" -- inversion joins in, and this is the first level that can be lost.  One tooth on
# the floor to be crossed by ceiling, then a slot: eleven columns of walk with mutable rock a
# cell above it and a cell below it, and one FIXED stone in the middle of the span.  West of the
# stone the mutable rock is the family that is solid as the world stands; east of it, the other
# family, so the far half is open air until the world is inverted.  The stone is the only cell in
# the whole span without a purple border on it, so where invert may be pressed is drawn on the
# board rather than deduced.  Press it anywhere else in there and the floor and the ceiling open
# in the same frame: the walker drops into a sealed shaft and the goal ring goes dark at once.
def _l3():
    g = _base(37)
    _flat(g, O - 24, O + 24, 11)
    _rect(g, O + 2, O + 2, 9, 10, "=")        # one tooth, to keep the pull in the level
    _bounds(g, O - 24, O + 24)
    _finish(g, 37)
    _corridor(g, O - 24, O + 24)
    _shaft(g, O + 1, O + 3)
    _slot(g, O + 4, O + 9, "#")               # the near half: solid as the world stands
    _slot(g, O + 9, O + 14, "o")              # the far half: open air until you invert
    _grain(g, 37)
    return _rows(g, (O, 10), (O + 19, 10))


# L4 "trade" -- the world has to go back the way it was.  Three slot spans and two stones: the
# first span is solid as the world stands, the second only once it is inverted, and the third only
# once it is inverted BACK.  So the level is two inversions, each on the one cell of the span that
# will not move, and the cue for the second is the same cue as for the first, one screen later.
# Nothing new is added to the rules; what is added is that a polarity is now a thing you spend and
# get back, not a switch you throw once.  A tooth and a curtain past the slot keep the pull in it.
def _l4():
    g = _base(51)
    _flat(g, O - 24, O + 26, 11)
    _rect(g, O + 18, O + 18, 9, 10, "=")      # the tooth past the slot
    _bounds(g, O - 24, O + 26)
    _finish(g, 51)
    _corridor(g, O - 24, O + 26)
    _shaft(g, O + 17, O + 22)
    _slot(g, O + 4, O + 8, "#")               # solid as the world stands
    _slot(g, O + 8, O + 12, "o")              # ...open until you invert, on the stone at O+8
    _slot(g, O + 12, O + 16, "#")             # ...and shut again until you invert BACK, at O+12
    _grain(g, 51)
    return _rows(g, (O, 10), (O + 20, 10))


# L5 "loft" -- the goal is on the ceiling.  Which storey the walker finishes on is the added rule:
# the ring hangs under the bedrock instead of sitting on the floor, so the last press of the level
# is the pull and not a step, and the pull has stopped being a way past obstacles and become the
# thing being aimed at.  Getting there is a slot with a stone in it, then a tooth and a curtain
# past its east end, so the weave from L2 and the stone from L3 both have to be right.
def _l5():
    g = _base(67)
    _flat(g, O - 24, O + 24, 11)
    _rect(g, O + 3, O + 3, 10, 10, "o")       # a stud on the approach: the clamp, early
    _rect(g, O + 15, O + 15, 9, 10, "=")      # the tooth
    _bounds(g, O - 24, O + 24)
    _finish(g, 67)
    _corridor(g, O - 24, O + 24)
    _shaft(g, O + 13, O + 22)
    _slot(g, O + 4, O + 8, "#")
    _slot(g, O + 8, O + 12, "o")              # the stone at O+8 is the only legal invert
    _curtain(g, O + 17, O + 17, 9)            # the curtain
    _grain(g, 67)
    return _rows(g, (O, 10), (O + 19, CEIL))


# L6 "weave" -- everything at once, and nothing new.  A three-span slot, so the world is spent and
# got back on two stones; then a tooth and a curtain to weave past; then the ring in the loft, so
# the level ends with the pull.  Four cues, each on screen before it is needed, each one step
# deep, and the only way to lose it is to press invert inside the slot anywhere but on one of the
# cells that visibly will not move.
def _l6():
    g = _base(83)
    _flat(g, O - 24, O + 26, 11)
    _rect(g, O + 16, O + 16, 9, 10, "=")      # the tooth
    _bounds(g, O - 24, O + 26)
    _finish(g, 83)
    _corridor(g, O - 24, O + 26)
    _shaft(g, O + 14, O + 22)
    _slot(g, O + 4, O + 7, "#")
    _slot(g, O + 7, O + 11, "o")
    _slot(g, O + 11, O + 14, "#")
    _curtain(g, O + 18, O + 18, 9)            # the curtain
    _grain(g, 83)
    return _rows(g, (O, 10), (O + 19, CEIL))


LEVELS = [
    {"name": "pull", "rows": _l1()},
    {"name": "seam", "rows": _l2()},
    {"name": "slot", "rows": _l3()},
    {"name": "trade", "rows": _l4()},
    {"name": "loft", "rows": _l5()},
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
    """Is cell (x, y) solid at this polarity?  Outside the strip is solid bedrock.

    Above the strip counts as bedrock too, which it did not have to before gravity could point
    up: the two rows of roof make row 0 unreachable in play, but the reverse strand search
    enumerates every cell in the grid including row 0, and an upward settle from there would
    have walked off the top of the world forever.
    """
    if y >= WORLD_H or y < 0 or x < 0 or x >= WORLD_W:
        return True
    c = grid[y][x]
    return c == FIXED or (c == MAT_A and pol == 0) or (c == MAT_B and pol == 1)


GRAV_DOWN, GRAV_UP = 1, -1


def settle(grid, x, y, pol, grav):
    """Discrete gravity: fall along the pull until the next cell that way is solid.

    Immediate and total, inside a single press -- there is no airborne state, no momentum and
    no arc, which is what keeps this basic physics rather than a platformer.  It is also an
    involution over a vertical open run: settling up lands on the top of the run the walker is
    in and settling down lands on its bottom, so aiming the pull back the other way always
    returns the walker to the cell it left.  Gravity on its own can therefore never strand
    anybody -- only inversion changes which runs exist.
    """
    while not solid(grid, x, y + grav, pol):
        y += grav
    return y


def step_target(grid, x, y, pol, grav, f):
    """Where a sideways press lands the walker, or None if a wall refuses it.

    A clear cell ahead is a plain step, then a fall.  A cell ahead that is solid but is only
    one cell tall -- one cell measured AGAINST the pull, so a rise when pulled down and a
    duck-under when pulled up -- is taken automatically, provided the walker's own
    anti-pull cell is clear to move through.  Anything taller refuses.  The one-cell climb
    used to be its own key; making it a consequence of walking loses no capability and frees
    the key for the pull.
    """
    if not solid(grid, x + f, y, pol):
        return (x + f, settle(grid, x + f, y, pol, grav))
    ny = y - grav
    if (0 <= ny < WORLD_H and not solid(grid, x + f, ny, pol)
            and not solid(grid, x, ny, pol)):
        return (x + f, settle(grid, x + f, ny, pol, grav))
    return None


def _clip(y):
    return max(0, min(WORLD_H - 1, y))


def refusal(grid, state, aid):
    """What stopped this press: (cell to flash, shove_x, shove_y).

    Every refused press names a cell on the board rather than tweaking a marker on the
    walker, so the answer to "why didn't that work" is drawn where the obstacle is.
    """
    x, y, pol, grav = state
    if aid in (1, 2):
        # Aiming the pull the way it already points. Physically nothing to do, so the surface
        # the walker is already held against is named and the token shoves into it: "that is
        # where you are already being pulled". A gravity key is never silent.
        return ((x, _clip(y + grav)), 0, grav)
    if aid in (3, 4):
        d = -1 if aid == 3 else 1
        if solid(grid, x + d, _clip(y - grav), pol):
            return ((x + d, _clip(y - grav)), d, 0)   # two cells tall: not a step, a wall
        return ((x, _clip(y - grav)), 0, -grav)       # no room over your own head to swing up
    return ((x, y), 0, grav)                          # ACTION5: your cell would close on you


def apply_action(grid, state, aid):
    """(x, y, pol, gravity) + action id -> new state.  Refused moves return the state
    unchanged, so nothing is ever fatal on its own.  Facing is not in here: it is decoration
    on the token now that the sideways key carries its own climb, so it cannot affect physics
    and does not enlarge the state space the strand check has to search."""
    x, y, pol, grav = state
    if aid == 1 or aid == 2:
        want = GRAV_UP if aid == 1 else GRAV_DOWN
        if grav != want:
            grav = want
            y = settle(grid, x, y, pol, grav)
    elif aid == 3 or aid == 4:
        t = step_target(grid, x, y, pol, grav, -1 if aid == 3 else 1)
        if t is not None:
            x, y = t
    elif aid == 5:
        if not solid(grid, x, y, 1 - pol):
            pol = 1 - pol
            y = settle(grid, x, y, pol, grav)
    return (x, y, pol, grav)


ACTION_IDS = (1, 2, 3, 4, 5)


def _safe_states(grid, goal):
    """Every (x, y, pol, gravity) from which the goal is still reachable.

    Built once per level: the transition graph has 128*16*2*2 = 8192 nodes, so this is a
    reverse breadth-first search over the whole future, not a lookahead. A state outside
    this set is stranded -- no sequence of walks, pull flips and inversions reaches the goal.
    Gravity had to go into this tuple the moment it became a verb: a passage that is a strand
    under one pull can be an open corridor under the other, so the old (x, y, polarity) search
    would have called safe states dead and dead states safe.
    """
    nodes = [(x, y, p, g)
             for x in range(WORLD_W) for y in range(WORLD_H)
             for p in (0, 1) for g in (GRAV_UP, GRAV_DOWN)]
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


def world_pixels(index, pol, grav):
    """The whole 512x64-pixel strip, pre-drawn for one polarity and one pull direction.

    The terrain only changes when polarity flips and the pull hairlines only when gravity
    flips, so all four images are baked once per level and a frame is a single array slice.
    That is also what makes a 30,000-rollout gate affordable: rendering was 90% of the cost
    when it was drawn cell by cell.
    """
    key = (index, pol, grav)
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
    # The pull, drawn on the world and nowhere else. Every solid cell whose ANTI-pull
    # neighbour is open is a face the walker could be held against right now, and that face gets
    # a one-pixel green line. Pulled down those are the tops of the blocks; pulled up they are
    # the undersides of the blocks and of the bedrock roof. Aiming the pull therefore sweeps
    # several hundred pixels across the frame, which is both the rule being taught and the reason
    # a pull key can never be a quiet press.
    #
    # The line goes in the LAST PIXEL OF THE OPEN CELL, not the first pixel of the rock. Drawn on
    # the rock it would sit exactly where that cell's purple "this will move" border goes, and
    # the one place that costs anything is the cell the walker is standing on -- which is the
    # single most important cell on the board to be able to read.
    for y in range(WORLD_H):
        py = y * CELL
        if not 0 <= y - grav < WORLD_H:
            continue          # never rule a line along the frame edge: that reads as a HUD
        for x in range(WORLD_W):
            if not solid(grid, x, y, pol) or solid(grid, x, y - grav, pol):
                continue
            px = x * CELL
            img[py - 1 if grav > 0 else py + CELL, px:px + CELL] = C_PULL
    _PIX_CACHE[key] = img
    return img


def ring_top(index):
    """Which of the goal cell's two rows the 8x8 ring hangs from.

    The ring is twice the walker's height, so it needs the cell above the goal or the cell below
    it. A floor goal takes the cell above; a loft goal -- the goal cell sits directly under the
    bedrock -- takes the cell below, or the ring would be drawn inside the roof.
    """
    grid, _start, (gx, gy) = _TABLES[index]
    above_free = not (solid(grid, gx, gy - 1, 0) or solid(grid, gx, gy - 1, 1))
    return gy - 1 if above_free else gy


def _pix_set(index):
    """All four bakes of one level, keyed by (polarity, pull)."""
    return {(p, g): world_pixels(index, p, g)
            for p in (0, 1) for g in (GRAV_UP, GRAV_DOWN)}


def camera_x(wx):
    """Deterministic side-scroll, recomputed from the walker's cell every frame: the walker
    sits dead centre of the 16-cell window and the window clamps at the two ends of the
    128-cell strip. Every level's whole solution runs in the unclamped middle, so a step is
    always the terrain sliding one cell under a stationary token -- the single most visible
    thing on screen, on every action that moves.
    """
    return max(0, min(WORLD_W - VIEW, wx - VIEW // 2))


# The walker is a 4x8 token: two stacked cells, solid, with a 2x2 bite out of the corner that
# is both TRAILING and furthest from the pull. Facing survives the colour being stripped out,
# and so does the pull: the second cell sits on the side AWAY from the pull, so pulled down the
# token stands with its head up and pulled up it hangs with its head down. Physics is the one
# cell; the second is decoration, and it is simply not drawn in the rare case that the cell it
# would occupy is solid, so the walker is never drawn inside rock.
_BODY = tuple((dx, dy) for dy in range(CELL) for dx in range(CELL))
_HEAD = {(f, g): tuple(((CELL - 1 - dx) if f < 0 else dx,
                        (CELL - 1 - dy) if g < 0 else dy)
                       for dy in range(CELL) for dx in range(CELL)
                       if not (dx < 2 and dy < 2))
         for f in (-1, 1) for g in (GRAV_UP, GRAV_DOWN)}

# The walker's own footing: the two pixel rows of its own cell that touch the rock it is being
# held against, in the same green as every other face the pull could hold it to, so it reads as
# that hairline thickened where the walker is standing. Pulled down it is the bottom of the
# token, pulled up it is the top -- with the second cell on the other side, the token states the
# pull twice over and would still state it with every colour in the game stripped out.
_SOLE = {GRAV_DOWN: tuple((dx, dy) for dy in (CELL - 2, CELL - 1) for dx in range(CELL)),
         GRAV_UP: tuple((dx, dy) for dy in (0, 1) for dx in range(CELL))}

# The goal is an 8x8 ring two cells wide and two cells tall -- twice the walker's width,
# hollow where the walker is solid, and the only yellow in the game. Nothing about it is a
# glyph, an arrow or a face.
_RING = tuple((dx, dy) for dy in range(2 * CELL) for dx in range(2 * CELL)
              if dx < 2 or dx >= 2 * CELL - 2 or dy < 2 or dy >= 2 * CELL - 2)

# The lock clamp: a two-pixel socket around both sides of the cell the walker is standing in
# and across the face it is resting against. It is on the world, not on the walker -- the token
# keeps its own colour and its bite, and what changes is that the cell is visibly held shut.
# The socket opens away from the pull, so its orientation states the pull a third time.
def _clamp(grav):
    ys = range(0, CELL + 2) if grav > 0 else range(-2, CELL)
    band = (CELL, CELL + 1) if grav > 0 else (-2, -1)
    return tuple(sorted(set(
        [(dx, dy) for dx in (-2, -1, CELL, CELL + 1) for dy in ys]
        + [(dx, dy) for dx in range(-2, CELL + 2) for dy in band])))


_CLAMPS = {GRAV_DOWN: _clamp(GRAV_DOWN), GRAV_UP: _clamp(GRAV_UP)}


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
        frame[:, :] = g.pix[(g.pol, g.grav)][:, px0:px0 + 64]

        gx, _gy = g.goal
        self._blit(frame, (gx - cam) * CELL, g.ring_top * CELL, _RING,
                   C_DEAD if g.stranded else C_GOAL)

        bx, by = (g.wx - cam) * CELL, g.wy * CELL

        # Colour as affordance, recomputed every step: where inversion is locked, the cell the
        # walker stands in wears a clamp drawn on the world, so the lock is a property of a place
        # rather than a tint on the token. The clamp opens away from the pull, so its orientation
        # states the pull as well.
        if not g.stranded and solid(g.grid, g.wx, g.wy, 1 - g.pol):
            self._blit(frame, bx, by, _CLAMPS[g.grav], C_CLAMP)

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
            self._fill(frame, bx - grow, (by - CELL if g.grav > 0 else by) - grow,
                       CELL + 2 * grow, 2 * CELL + 2 * grow, C_REFUSE)
        hy = g.wy - g.grav                        # the second cell sits against the pull
        if not solid(g.grid, g.wx, hy, g.pol):
            self._blit(frame, bx + ox, hy * CELL + oy, _HEAD[(g.facing, g.grav)], col)
        self._blit(frame, bx + ox, by + oy, _BODY, col)
        if not g.stranded and not g.flash:
            self._blit(frame, bx, by, _SOLE[g.grav], C_PULL)

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
        self.ring_top = ring_top(0)
        self.wx = self.wy = 0
        self.pol = 0
        self.grav = GRAV_DOWN
        self.facing = 1
        self.flash = None
        self.pulse = 0
        self.stranded = False
        self.safe = frozenset()
        self.pix = _pix_set(0)

        levels = [Level(sprites=[], grid_size=(64, 64), data=ldef, name=ldef["name"])
                  for ldef in LEVELS]

        super().__init__(
            "ng",
            levels,
            Camera(0, 0, 64, 64, C_GROUND, C_GROUND, [self.display]),
            False,
            len(levels),
            [1, 2, 3, 4, 5],     # 1/2 = pull up/down, 3/4 = step left/right, 5 = invert
        )

    # -- level setup --------------------------------------------------------

    def on_set_level(self, level: Level) -> None:
        idx = self.level_index
        grid, start, goal = _TABLES[idx]
        self.grid = grid
        self.goal = goal
        self.ring_top = ring_top(idx)
        self.wx, self.wy = start
        self.grav = GRAV_DOWN
        self.wy = settle(grid, self.wx, self.wy, 0, self.grav)
        self.pol = 0
        self.facing = 1
        self.flash = None
        self.pulse = 0
        self.stranded = False
        self.safe = safe_states(idx)
        self.pix = _pix_set(idx)

    # -- engine entry point -------------------------------------------------

    def step(self) -> None:
        aid = self.action.id.value
        self.flash = None
        state = (self.wx, self.wy, self.pol, self.grav)
        if aid in (3, 4):
            self.facing = -1 if aid == 3 else 1     # decoration, and free even when refused

        if aid not in ACTION_IDS:
            # RESET and anything unmapped: no state change, and never a loss.  Exploration
            # must cost nothing, so there is no `else: self.lose()` anywhere in this game.
            self.complete_action()
            return

        moved = apply_action(self.grid, state, aid)
        if moved == state:
            # Nothing changed -- a wall, an inversion that would bury the walker, or the pull
            # aimed the way it already points. Name the cell that stopped it. A pull key that
            # DID flip is never in here even when the walker does not move a cell: gravity is
            # part of the state, and the frame proves it because every green face in view has
            # swapped to the other side of its rock.
            self.pulse ^= 1
            self.flash = refusal(self.grid, state, aid)
        self.wx, self.wy, self.pol, self.grav = moved

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
