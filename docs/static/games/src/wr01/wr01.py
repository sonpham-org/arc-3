# Author: Claude Opus 5
# Date: 2026-09-12
# PURPOSE: wr01 "Warren" -- an ARC-AGI-3 environment whose world is 192x192 pixels, a 3x3 grid
#   of 64x64 screens, with a camera that pans on BOTH axes as the walker moves. Chambers are
#   joined by portals rather than corridors. A portal does not have a fixed exit: it reads the
#   walker's own signature -- what the walker is carrying -- through its lens (object count,
#   object shape, or enclosed-hole count) and delivers the walker to whichever chamber that
#   value points at. So navigation is classification, not geometry: to go somewhere else you
#   pick something up or put something down. A portal used once shuts behind you, so the warren
#   is a shrinking graph and the order of travel matters. Three tools -- prong, eye, mesh --
#   attach to the walker, grant a capability each, and are the only thing in the game that
#   survives a level boundary. Every portal draws a miniature of the chamber it would send you
#   to RIGHT NOW, recoloured every frame, so nothing in the game depends on memory.
# SRP/DRY check: Pass -- self-contained environment. The transition function `apply` is the
#   single source of truth for the rules; the display, the loss test, the smoke-test solver and
#   the random gate all drive it rather than re-implementing it.
"""Warren -- portals that sort you by what you carry.

ACTION1/2/3/4 move the walker one cell up/down/left/right. ACTION5 takes what is under the
walker, or sets a carried object down on a cradle. Walking into a portal uses it at once: the
portal reads what the walker carries, and sends the walker to the chamber that value points at.
A portal shuts after one use and is drawn barred. A prong re-opens one shut portal per level.
An eye draws what is lying in a portal's destination inside the portal's mouth. A mesh lets
the walker cross a chasm. Tools stay with the walker into the next level. Reach the well.

8 levels. No RNG. No budget, no lives, no counters, no bars, no pips.
"""

from collections import deque

import numpy as np
from arcengine import ARCBaseGame, Camera, GameState, Level, RenderableUserDisplay

# ---------------------------------------------------------------------------
# Palette (ARC-3 indices). Primaries are the under-used end: maroon, purple,
# magenta, light magenta, orange, yellow. Greys and black are structure only.
# ---------------------------------------------------------------------------

C_WHITE, C_LGRAY, C_GRAY, C_DGRAY, C_VDGRAY, C_BLACK = 0, 1, 2, 3, 4, 5
C_MAGENTA, C_LMAGENTA, C_RED, C_BLUE, C_LBLUE = 6, 7, 8, 9, 10
C_YELLOW, C_ORANGE, C_MAROON, C_GREEN, C_PURPLE = 11, 12, 13, 14, 15

C_ROCK = C_MAROON        # the solid the warren is cut out of (maroon: 0.0% of official pixels)
C_VEIN = C_PURPLE        # mineral speckle in the rock
C_SEAM = C_DGRAY         # thin diagonal seams in the rock
C_LIP = C_GRAY           # the carved lip where floor meets rock
C_FLOOR = C_PURPLE       # chamber floor
C_TILE = C_MAGENTA       # floor patterning
C_RECESS = C_LGRAY       # alcove lip
C_VOID = C_BLACK         # a chasm
C_VOID_EDGE = C_VDGRAY
C_SEAL = C_LMAGENTA      # the chamber's emblem inlaid in its floor
C_GOAL = C_YELLOW        # the well
C_CRADLE = C_LGRAY
C_ENTRY = C_LGRAY

C_BODY = C_WHITE         # the walker's core
C_BODY_SHUT = C_GRAY     # the walker once the warren has closed around it

C_LIVE = C_LMAGENTA      # portal preview: an ordinary chamber with a way onward
C_HOME = C_YELLOW        # portal preview: the chamber holding the well
C_DEAD = C_DGRAY         # portal preview: a chamber with nothing left
C_BARRED = C_VDGRAY      # a portal already used
C_REFUSE = C_WHITE       # the mark a refused press leaves

# ---------------------------------------------------------------------------
# Geometry. 32x32 cells of 6px = 192x192px = exactly a 3x3 grid of 64x64 screens.
# Chambers live in nine 10x10-cell slots at origins 0, 11, 22, with a 1-cell rock
# seam between them. The camera window is 64x64px and pans on both axes.
# ---------------------------------------------------------------------------

CELL = 6
WORLD_CELLS = 32
WORLD_PX = WORLD_CELLS * CELL          # 192
VIEW = 64
CAM_MAX = WORLD_PX - VIEW              # 128
SLOT_ORIGIN = (0, 11, 22)

DIRS = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}
ACTION_DIR = {1: "U", 2: "D", 3: "L", 4: "R"}
TAKE = 5

# ---------------------------------------------------------------------------
# Glyphs. Every bitmap is a tuple of equal-length strings; '#' is ink.
# Shape carries every distinction, colour only reinforces it.
# ---------------------------------------------------------------------------

# Signature objects: what the walker can carry, and what the lenses read.
#   holes = enclosed voids in the glyph, which is what the hole lens counts.
SIG = {
    "SLAB": dict(color=C_ORANGE, holes=0, glyph=(
        ".####.",
        "######",
        "######",
        "######",
        "######",
        ".####.")),
    "HOOP": dict(color=C_MAGENTA, holes=1, glyph=(
        ".####.",
        "#....#",
        "#....#",
        "#....#",
        "#....#",
        ".####.")),
    "STACK": dict(color=C_YELLOW, holes=2, glyph=(
        "######",
        "#....#",
        "######",
        "#....#",
        "######",
        "......")),
    "COMB": dict(color=C_LMAGENTA, holes=0, glyph=(
        "####..",
        "####..",
        "..####",
        "..####",
        "####..",
        "####..")),
}
# The 2x2 stamp each carried object leaves on the walker. Four distinguishable
# patterns, so two carried objects are readable on a 6x6 body.
STAMP = {
    "SLAB": ("##", "##"),
    "HOOP": ("#.", ".#"),
    "STACK": ("#.", "#."),
    "COMB": ("##", "#."),
}

# Tools. Attached to the walker's flanks and corners, never counted by any lens,
# and the only thing that survives a level boundary.
GEAR = {
    "PRONG": dict(color=C_PURPLE, glyph=(
        "..##..",
        "..##..",
        ".####.",
        ".####.",
        "######",
        "######")),
    "EYE": dict(color=C_LBLUE, glyph=(
        "..##..",
        ".####.",
        "##..##",
        "##..##",
        ".####.",
        "..##..")),
    "MESH": dict(color=C_GREEN, glyph=(
        "#..#..",
        ".#..#.",
        "..#..#",
        "#..#..",
        ".#..#.",
        "..#..#")),
}
GEAR_ORDER = ("PRONG", "EYE", "MESH")

# Chamber emblems. Identity is pure shape: the floor inlay is a flat light-magenta
# marking, and a portal preview draws the same shape recoloured by what walking
# into that portal would currently mean.
SEALS = {
    "DIAMOND": (
        "..##..",
        ".####.",
        "######",
        "######",
        ".####.",
        "..##.."),
    "TRIAD": (
        "######",
        "......",
        "######",
        "......",
        "######",
        "......"),
    "STEP": (
        "######",
        "#####.",
        "####..",
        "###...",
        "##....",
        "#....."),
    "ARCH": (
        ".####.",
        "##..##",
        "#....#",
        "#....#",
        "#....#",
        "#....#"),
    "COIL": (
        "######",
        "#.....",
        "#.####",
        "#.#..#",
        "#.#.##",
        "#.#..."),
    "CLEFT": (
        "##....",
        "..##..",
        "....##",
        "....##",
        "..##..",
        "##...."),
    "WEDGE": (
        "#....#",
        "##..##",
        ".####.",
        ".####.",
        "##..##",
        "#....#"),
}

# ---------------------------------------------------------------------------
# Chamber templates. 10x10 cells each, deliberately asymmetric so no two
# chambers in a level share a silhouette and nothing reads as a tiled grid of
# rooms.  '#' rock (wall thickness varies with the silhouette), '.' floor,
# ':' patterned floor, 'o' alcove, '~' chasm.
# ---------------------------------------------------------------------------

TEMPLATES = {
    "LOBE": (
        "###..#####",
        "##.....###",
        "#.......##",
        "#..:::...#",
        "#.::::::.#",
        "#.:::::..#",
        "##..::...#",
        "###.....o#",
        "####....##",
        "#####.####"),
    "SPUR": (
        "##########",
        "#....#####",
        "#.::.#####",
        "#.::.....#",
        "#.::.:::.#",
        "#....:::.#",
        "####.:::.#",
        "####....o#",
        "######...#",
        "##########"),
    "FORK": (
        "###....###",
        "#....#...#",
        "#.::..::.#",
        "#.::::::.#",
        "##.::::.##",
        "#..::::..#",
        "#.:....:.#",
        "#o.....o.#",
        "###....###",
        "##########"),
    "RIM": (
        "##########",
        "##......##",
        "#o.::::.##",
        "##.::::..#",
        "#..::::.##",
        "##.::::..#",
        "#o.::::.##",
        "##......o#",
        "###.....##",
        "##########"),
    "CREST": (
        "#####.####",
        "###...:.##",
        "##..::::.#",
        "#..::::..#",
        "#.::::..##",
        "#.:::..###",
        "#..::..###",
        "##....####",
        "###..#####",
        "##########"),
    # A blind pocket. It holds no mouth and no well, so being sorted into one is the
    # end of the run -- which is why every mouth that leads to one is drawn dark.
    "NOOK": (
        "##########",
        "####...###",
        "###.::..##",
        "##..::..##",
        "##.....###",
        "###o..####",
        "##########",
        "##########",
        "##########",
        "##########"),
    "PIT": (
        "##########",
        "#........#",
        "#.::::::.#",
        "#.:~~~~:.#",
        "#.:~~~~:.#",
        "#.:~~~~:.#",
        "#.::::::.#",
        "#o......o#",
        "##......##",
        "##########"),
}

FLOOR_CHARS = ".:o"
PASSABLE_CHARS = ".:o~"


# ---------------------------------------------------------------------------
# Lenses. A lens reduces what the walker carries to one small hashable value.
# ---------------------------------------------------------------------------

def lens_value(lens, kinds):
    """kinds is a tuple of signature-object names, in pickup order."""
    if lens == "COUNT":
        return len(kinds)
    if lens == "SHAPE":
        return tuple(sorted(kinds))
    if lens == "HOLE":
        return sum(SIG[k]["holes"] for k in kinds)
    raise ValueError(lens)


# ---------------------------------------------------------------------------
# Levels. Eight, each 11-18 actions, ~118 in total, which is what the harness
# actually gets. Every level adds one rule and keeps every earlier one.
#   slot     which of the nine 10x10 slots the chamber occupies
#   entry    the pad a portal delivers the walker onto (chamber-local cell)
#   portals  {"at": top-left of a 2x2 mouth, "lens": ..., "map": {value: chamber}}
#   objects  (kind, local cell); every signature object's cell is also a cradle
#   goal     top-left of the 2x2 well
# ---------------------------------------------------------------------------

def _blind(at, dest):
    """A mouth that leads into a blind pocket whatever the walker is carrying. It is drawn
    dark for every signature, so it is a visible warning and never a hidden trap."""
    return dict(at=at, lens="COUNT", map={0: dest, 1: dest, 2: dest})


def _nook(slot, seal):
    return dict(slot=slot, tpl="NOOK", seal=seal, entry=(4, 3))


LEVELS = [
    # -- L1: one mouth, one reading, nothing to carry, nothing to lose. ------
    dict(name="Sorting", start=(0, (4, 1)), chambers=[
        dict(slot=(1, 2), tpl="LOBE", seal="CLEFT", entry=(4, 1),
             portals=[dict(at=(6, 6), lens="COUNT", map={0: 1})]),
        dict(slot=(0, 0), tpl="CREST", seal="DIAMOND", entry=(3, 1), goal=(2, 5)),
    ]),
    # -- L2: five chambers in a chain. Every chamber offers four mouths and only
    #        one has anything behind it; the nearest is never the one. Reading the
    #        mouth beats reading the distance. Nothing to carry yet. ------------
    dict(name="Nearer", start=(0, (4, 4)), chambers=[
        dict(slot=(1, 1), tpl="FORK", seal="ARCH", entry=(4, 4), portals=[
            _blind((4, 2), 5), _blind((2, 2), 6), _blind((6, 3), 5),
            _blind((4, 6), 6), dict(at=(2, 5), lens="COUNT", map={0: 1})]),
        dict(slot=(2, 0), tpl="RIM", seal="COIL", entry=(4, 4), portals=[
            _blind((2, 2), 5), _blind((5, 2), 6), _blind((3, 6), 5),
            dict(at=(6, 4), lens="COUNT", map={0: 2})]),
        dict(slot=(0, 0), tpl="LOBE", seal="STEP", entry=(4, 4), portals=[
            _blind((1, 3), 6), _blind((6, 3), 5), _blind((2, 1), 6),
            _blind((2, 5), 5), dict(at=(4, 6), lens="COUNT", map={0: 3})]),
        dict(slot=(0, 2), tpl="SPUR", seal="CLEFT", entry=(5, 4), portals=[
            _blind((6, 5), 5), _blind((6, 3), 6), _blind((1, 1), 5),
            _blind((3, 3), 6), dict(at=(1, 3), lens="COUNT", map={0: 4})]),
        dict(slot=(2, 2), tpl="CREST", seal="DIAMOND", entry=(3, 4), goal=(5, 4),
             portals=[_blind((1, 3), 5), _blind((2, 5), 6), _blind((3, 1), 5),
                      _blind((5, 2), 6)]),
        _nook((1, 0), "TRIAD"), _nook((1, 2), "WEDGE"),
    ]),
    # -- L3: the mouths read what the walker carries. Two things lie about; the
    #        one mouth with anything behind it wants exactly one of them held,
    #        and the next one wants two. Empty hands and full hands both end it.
    dict(name="Holding", start=(0, (4, 4)), chambers=[
        dict(slot=(1, 1), tpl="FORK", seal="ARCH", entry=(4, 4),
             objects=[("SLAB", (3, 4)), ("HOOP", (5, 4))], portals=[
                 _blind((4, 2), 3), _blind((2, 2), 4), _blind((6, 3), 3),
                 _blind((4, 6), 4),
                 dict(at=(2, 5), lens="COUNT", map={0: 3, 1: 1, 2: 4})]),
        dict(slot=(2, 0), tpl="RIM", seal="COIL", entry=(4, 4),
             objects=[("STACK", (2, 5))], portals=[
                 dict(at=(2, 2), lens="COUNT", map={0: 3, 1: 4, 2: 2}),
                 _blind((5, 2), 4), _blind((4, 5), 3), _blind((6, 4), 4)]),
        dict(slot=(0, 2), tpl="CREST", seal="DIAMOND", entry=(3, 4), goal=(5, 4),
             portals=[_blind((1, 3), 3), _blind((2, 5), 4), _blind((3, 1), 3),
                      _blind((5, 2), 4)]),
        _nook((1, 0), "TRIAD"), _nook((0, 0), "WEDGE"),
    ]),
    # -- L4: mouths shut behind them. Two mouths reach the same chamber and only
    #        one of them is still needed later, so the order of use is the puzzle.
    dict(name="Shutting", start=(0, (4, 4)), chambers=[
        dict(slot=(1, 2), tpl="FORK", seal="ARCH", entry=(4, 4), portals=[
            _blind((4, 2), 3), _blind((2, 5), 4), _blind((4, 6), 3),
            dict(at=(2, 2), lens="COUNT", map={0: 1, 1: 2, 2: 3}),
            dict(at=(6, 3), lens="COUNT", map={0: 1, 1: 3, 2: 4})]),
        dict(slot=(0, 0), tpl="LOBE", seal="STEP", entry=(4, 4),
             objects=[("SLAB", (5, 4))], portals=[
                 dict(at=(2, 1), lens="COUNT", map={0: 3, 1: 0, 2: 4}),
                 _blind((6, 3), 4), _blind((4, 6), 3), _blind((1, 3), 4),
                 _blind((2, 5), 3)]),
        dict(slot=(2, 1), tpl="CREST", seal="COIL", entry=(3, 4), goal=(5, 4),
             portals=[_blind((1, 3), 3), _blind((2, 5), 4), _blind((3, 1), 3),
                      _blind((5, 2), 4)]),
        _nook((1, 0), "TRIAD"), _nook((2, 2), "WEDGE"),
    ]),
    # -- L5: the prong. It forces one shut mouth back open, once per level, and
    #        the only route through needs the same mouth twice. Tools start here
    #        and are the one thing that crosses a level boundary. --------------
    dict(name="Prong", start=(0, (3, 4)), chambers=[
        dict(slot=(1, 1), tpl="CREST", seal="TRIAD", entry=(3, 4),
             objects=[("PRONG", (3, 3))], portals=[
                 dict(at=(5, 2), lens="COUNT", map={0: 1, 1: 2, 2: 3}),
                 _blind((1, 3), 3), _blind((2, 5), 4), _blind((3, 1), 3)]),
        dict(slot=(0, 2), tpl="SPUR", seal="CLEFT", entry=(5, 4),
             objects=[("SLAB", (5, 5)), ("STACK", (4, 5))], portals=[
                 dict(at=(1, 3), lens="COUNT", map={0: 3, 1: 0, 2: 4}),
                 _blind((6, 3), 4), _blind((6, 5), 3), _blind((1, 1), 4),
                 _blind((3, 3), 3)]),
        dict(slot=(2, 0), tpl="RIM", seal="COIL", entry=(4, 4), goal=(3, 6),
             portals=[_blind((2, 2), 3), _blind((5, 2), 4), _blind((6, 4), 3)]),
        _nook((1, 0), "DIAMOND"), _nook((2, 2), "WEDGE"),
    ]),
    # -- L6: the reading changes. This mouth counts enclosed holes, not objects,
    #        so a slab and a stack are not interchangeable -- and the mouth after
    #        it wants empty hands, so something has to go back down on a cradle.
    dict(name="Reading", start=(0, (4, 4)), chambers=[
        dict(slot=(0, 1), tpl="FORK", seal="ARCH", entry=(4, 4),
             objects=[("STACK", (5, 5)), ("SLAB", (3, 4))], portals=[
                 _blind((4, 2), 3), _blind((2, 2), 4), _blind((2, 5), 3),
                 # nothing is keyed to a hole-less signature: hold the slab, or hold
                 # nothing, and this mouth is an empty socket that will not take you
                 dict(at=(6, 3), lens="HOLE", map={1: 4, 2: 1, 3: 4})]),
        dict(slot=(2, 2), tpl="LOBE", seal="DIAMOND", entry=(4, 4), cradles=[(5, 4)],
             portals=[dict(at=(2, 1), lens="COUNT", map={0: 2, 1: 3, 2: 4}),
                      _blind((1, 3), 4), _blind((6, 3), 3), _blind((4, 6), 4),
                      _blind((2, 5), 3)]),
        dict(slot=(1, 0), tpl="CREST", seal="STEP", entry=(3, 4), goal=(5, 4),
             portals=[_blind((1, 3), 3), _blind((2, 5), 4), _blind((3, 1), 3),
                      _blind((5, 2), 4)]),
        _nook((1, 2), "TRIAD"), _nook((0, 0), "WEDGE"),
    ]),
    # -- L7: the eye, and two readings in one level. The first mouth sorts by
    #        shape -- which object, not how many -- and the second by count.
    dict(name="Readings", start=(0, (4, 4)), chambers=[
        dict(slot=(1, 1), tpl="FORK", seal="ARCH", entry=(4, 4),
             objects=[("EYE", (4, 5)), ("HOOP", (3, 4)), ("COMB", (5, 4))], portals=[
                 _blind((4, 2), 3), _blind((2, 2), 4), _blind((2, 5), 3),
                 dict(at=(6, 3), lens="SHAPE", map={(): 3, ("HOOP",): 1,
                                                    ("COMB",): 4,
                                                    ("COMB", "HOOP"): 3})]),
        dict(slot=(0, 2), tpl="RIM", seal="COIL", entry=(4, 4), cradles=[(3, 4)],
             portals=[dict(at=(2, 2), lens="COUNT", map={0: 2, 1: 3, 2: 4}),
                      _blind((5, 2), 4), _blind((4, 5), 3), _blind((6, 4), 4),
                      _blind((2, 6), 3)]),
        dict(slot=(2, 0), tpl="CREST", seal="STEP", entry=(3, 4), goal=(5, 4),
             portals=[_blind((1, 3), 3), _blind((2, 5), 4), _blind((3, 1), 3),
                      _blind((5, 2), 4)]),
        _nook((0, 0), "TRIAD"), _nook((2, 2), "WEDGE"),
    ]),
    # -- L8: all four systems at once. Holes then count, mouths that shut, the
    #        prong as slack, and a well lying at the bottom of a chasm that only
    #        the mesh can be walked across. ------------------------------------
    dict(name="Warren", start=(0, (4, 4)), chambers=[
        dict(slot=(0, 1), tpl="FORK", seal="ARCH", entry=(4, 4),
             objects=[("MESH", (4, 5)), ("HOOP", (3, 4)), ("SLAB", (5, 4))], portals=[
                 _blind((4, 2), 3), _blind((2, 2), 4), _blind((2, 5), 3),
                 dict(at=(6, 3), lens="HOLE", map={0: 3, 1: 1, 2: 4})]),
        dict(slot=(2, 0), tpl="RIM", seal="COIL", entry=(4, 4), cradles=[(3, 4)],
             portals=[dict(at=(2, 2), lens="COUNT", map={0: 2, 1: 3, 2: 4}),
                      _blind((5, 2), 4), _blind((3, 6), 3), _blind((6, 4), 4)]),
        dict(slot=(2, 2), tpl="PIT", seal="DIAMOND", entry=(4, 1), goal=(3, 4),
             portals=[_blind((1, 1), 3), _blind((7, 1), 4), _blind((1, 6), 3)]),
        _nook((1, 2), "TRIAD"), _nook((0, 0), "WEDGE"),
    ]),
]

# ---------------------------------------------------------------------------
# World build. Turns a level record into flat lookups over world cells.
# ---------------------------------------------------------------------------

class World:
    __slots__ = ("idx", "name", "chars", "chambers", "cell_chamber", "portal_at",
                 "portals", "cradles", "objects", "kind", "goal_cells", "start",
                 "inlays", "entries")


def _blocks(x, y):
    return [(x + dx, y + dy) for dy in (0, 1) for dx in (0, 1)]


def _inlay_spot(cells, busy):
    """Best 2x2 all-floor block near the chamber centre, one clear cell away from
    anything the walker can act on, so the emblem never reads as an object."""
    if not cells:
        return None
    cx = sum(c[0] for c in cells) / len(cells)
    cy = sum(c[1] for c in cells) / len(cells)
    pad = {(b[0] + dx, b[1] + dy) for b in busy
           for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    best = None
    for (x, y) in cells:
        blk = [(x + dx, y + dy) for dy in range(2) for dx in range(2)]
        if any(c not in cells or c in pad for c in blk):
            continue
        d = abs(x + 0.5 - cx) + abs(y + 0.5 - cy)
        if best is None or d < best[0]:
            best = (d, (x, y))
    return best[1] if best else None


def build(idx):
    lv = LEVELS[idx]
    w = World()
    w.idx, w.name = idx, lv["name"]
    w.chars, w.cell_chamber, w.portal_at = {}, {}, {}
    w.chambers, w.portals, w.objects, w.inlays, w.entries = [], [], [], [], []
    w.kind = {}
    cradles, goals = set(), set()

    for cid, ch in enumerate(lv["chambers"]):
        ox, oy = SLOT_ORIGIN[ch["slot"][0]], SLOT_ORIGIN[ch["slot"][1]]
        tpl = TEMPLATES[ch["tpl"]]
        cells = set()
        for ly, row in enumerate(tpl):
            for lx, c in enumerate(row):
                wc = (ox + lx, oy + ly)
                w.chars[wc] = c
                if c in PASSABLE_CHARS:
                    cells.add(wc)
                    w.cell_chamber[wc] = cid
        busy = set()
        pl = []
        for pidx, p in enumerate(ch.get("portals", ())):
            pc = frozenset((ox + a, oy + b) for a, b in _blocks(*p["at"]))
            assert all(w.chars[c] in FLOOR_CHARS for c in pc), (idx, cid, p["at"])
            for c in pc:
                w.portal_at[c] = (cid, pidx)
            busy |= set(pc)
            pl.append(dict(cells=pc, lens=p["lens"], map=dict(p["map"]),
                           at=(ox + p["at"][0], oy + p["at"][1])))
        w.portals.append(pl)
        gcells = frozenset()
        if "goal" in ch:
            gcells = frozenset((ox + a, oy + b) for a, b in _blocks(*ch["goal"]))
            assert all(c in cells for c in gcells), (idx, cid, "goal")
            goals |= set(gcells)
            busy |= set(gcells)
        for kindname, lc in ch.get("objects", ()):
            wc = (ox + lc[0], oy + lc[1])
            assert w.chars[wc] in FLOOR_CHARS, (idx, cid, lc)
            oid = len(w.objects)
            w.objects.append((oid, kindname, wc))
            w.kind[oid] = kindname
            if kindname in SIG:
                cradles.add(wc)
            busy.add(wc)
        for lc in ch.get("cradles", ()):
            wc = (ox + lc[0], oy + lc[1])
            assert w.chars[wc] in FLOOR_CHARS, (idx, cid, lc)
            cradles.add(wc)
            busy.add(wc)
        entry = (ox + ch["entry"][0], oy + ch["entry"][1])
        assert w.chars[entry] in FLOOR_CHARS, (idx, cid, "entry")
        w.entries.append(entry)
        busy.add(entry)
        w.chambers.append(dict(cid=cid, seal=ch["seal"], cells=frozenset(cells),
                               goal=gcells, entry=entry, slot=ch["slot"]))
        solid_floor = {c for c in cells if w.chars[c] in FLOOR_CHARS}
        w.inlays.append(_inlay_spot(solid_floor, busy))

    w.cradles = frozenset(cradles)
    w.goal_cells = frozenset(goals)
    scid, slc = lv["start"]
    so = (SLOT_ORIGIN[lv["chambers"][scid]["slot"][0]],
          SLOT_ORIGIN[lv["chambers"][scid]["slot"][1]])
    w.start = (so[0] + slc[0], so[1] + slc[1])
    assert w.chars[w.start] in FLOOR_CHARS, (idx, "start")
    return w


WORLDS = [build(i) for i in range(len(LEVELS))]

# ---------------------------------------------------------------------------
# Rules. `apply` is the ONE definition of what a press does. The display, the
# loss test, the smoke-test solver and the random gate all drive it.
#
# state = (pos, carried, placements, spent, gear, key_used)
#   pos         world cell of the walker
#   carried     tuple of object ids, pickup order; at most CARRY
#   placements  frozenset of (oid, cell) for signature objects lying on the floor
#   spent       frozenset of (cid, pidx) mouths already used
#   gear        frozenset of tool names attached to the walker
#   key_used    the prong's one re-opening has been spent this level
# ---------------------------------------------------------------------------

CARRY = 2
PRESSES = ("U", "D", "L", "R", "T")     # T is ACTION5


def start_state(w, gear=frozenset()):
    return (w.start, (),
            frozenset((oid, c) for oid, k, c in w.objects),
            frozenset(), frozenset(gear), False)


def kinds_of(w, carried):
    return tuple(w.kind[o] for o in carried)


def passable(w, cell, gear):
    c = w.chars.get(cell)
    if c is None or c == "#":
        return False
    if c == "~":
        return "MESH" in gear
    return True


def floor_object(w, placements, cell):
    for oid, c in placements:
        if c == cell:
            return oid
    return None


def mouth_state(w, state, cid, pidx):
    """What the mouth (cid, pidx) is doing for this walker, right now.
    Returns ('barred', None) | ('hollow', None) | ('open', dest_cid)."""
    lens = w.portals[cid][pidx]
    if (cid, pidx) in state[3] and not ("PRONG" in state[4] and not state[5]):
        return ("barred", None)
    dest = lens["map"].get(lens_value(lens["lens"], kinds_of(w, state[1])))
    if dest is None:
        return ("hollow", None)
    return ("open", dest)


def apply(w, state, press):
    """Pure transition. Returns (next_state, outcome). Outcome is one of
    move / bump / port / win / barred / hollow / pick / drop / gear / refuse."""
    pos, carried, placements, spent, gear, key_used = state
    if press == "T":
        oid = floor_object(w, placements, pos)
        if oid is not None:
            k = w.kind[oid]
            if k in GEAR:
                return ((pos, carried, placements - {(oid, pos)}, spent,
                         gear | {k}, key_used), "gear")
            if len(carried) < CARRY:
                return ((pos, carried + (oid,), placements - {(oid, pos)}, spent,
                         gear, key_used), "pick")
            return (state, "refuse")
        if carried and pos in w.cradles:
            oid = carried[-1]
            return ((pos, carried[:-1], placements | {(oid, pos)}, spent,
                     gear, key_used), "drop")
        return (state, "refuse")

    dx, dy = DIRS[press]
    nxt = (pos[0] + dx, pos[1] + dy)
    if not passable(w, nxt, gear):
        return (state, "bump")
    if nxt in w.portal_at:
        cid, pidx = w.portal_at[nxt]
        kindq, dest = mouth_state(w, state, cid, pidx)
        if kindq != "open":
            return (state, kindq)
        reopened = (cid, pidx) in spent
        return ((w.entries[dest], carried, placements, spent | {(cid, pidx)},
                 gear, key_used or reopened), "port")
    if nxt in w.goal_cells:
        return ((nxt, carried, placements, spent, gear, key_used), "win")
    return ((nxt, carried, placements, spent, gear, key_used), "move")


# ---------------------------------------------------------------------------
# Level analysis. The forward closure from the start is small (a few thousand
# states), so it is computed once per (level, gear) and cached at module level.
# `winnable` is then an O(1) lookup, which is what makes the portal previews
# truthful without costing anything at render time.
# ---------------------------------------------------------------------------

_ANALYSIS = {}


def analyse(idx, gear=frozenset()):
    key = (idx, frozenset(gear))
    got = _ANALYSIS.get(key)
    if got is not None:
        return got
    w = WORLDS[idx]
    s0 = start_state(w, gear)
    seen, rev, wins = {s0}, {}, set()
    q = deque([s0])
    while q:
        s = q.popleft()
        for press in PRESSES:
            ns, oc = apply(w, s, press)
            if oc == "win":
                wins.add(s)
                continue
            if ns == s:
                continue
            rev.setdefault(ns, set()).add(s)
            if ns not in seen:
                seen.add(ns)
                q.append(ns)
    win = set(wins)
    q = deque(wins)
    while q:
        s = q.popleft()
        for p in rev.get(s, ()):
            if p not in win:
                win.add(p)
                q.append(p)
    got = (seen, win)
    _ANALYSIS[key] = got
    return got


def winnable(idx, state, gear=frozenset()):
    return state in analyse(idx, gear)[1]


# ---------------------------------------------------------------------------
# Drawing helpers. All coordinates are screen pixels; everything clips.
# ---------------------------------------------------------------------------

def _px(frame, x, y, col):
    if 0 <= x < VIEW and 0 <= y < VIEW:
        frame[y, x] = col


def _fill(frame, x, y, w, h, col):
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + w, VIEW), min(y + h, VIEW)
    if x1 > x0 and y1 > y0:
        frame[y0:y1, x0:x1] = col


def _ring(frame, x, y, w, h, col, skip=()):
    for i in range(w):
        if ("top", i) not in skip:
            _px(frame, x + i, y, col)
        if ("bot", i) not in skip:
            _px(frame, x + i, y + h - 1, col)
    for j in range(h):
        if ("lft", j) not in skip:
            _px(frame, x, y + j, col)
        if ("rgt", j) not in skip:
            _px(frame, x + w - 1, y + j, col)


def _bm(frame, x, y, bitmap, col, scale=1):
    for j, row in enumerate(bitmap):
        for i, c in enumerate(row):
            if c == "#":
                if scale == 1:
                    _px(frame, x + i, y + j, col)
                else:
                    _fill(frame, x + i * scale, y + j * scale, scale, scale, col)


def camera(pos):
    cx = min(max(pos[0] * CELL + CELL // 2 - VIEW // 2, 0), CAM_MAX)
    cy = min(max(pos[1] * CELL + CELL // 2 - VIEW // 2, 0), CAM_MAX)
    return cx, cy


LENS_SKIP = {
    "COUNT": frozenset(),
    "SHAPE": frozenset([("top", 5), ("top", 6), ("bot", 5), ("bot", 6),
                        ("lft", 5), ("lft", 6), ("rgt", 5), ("rgt", 6)]),
    "HOLE": frozenset([("top", 0), ("top", 11), ("bot", 0), ("bot", 11),
                       ("lft", 0), ("lft", 11), ("rgt", 0), ("rgt", 11)]),
}


class Wr01Display(RenderableUserDisplay):
    def __init__(self, game):
        self.game = game

    # -- terrain ---------------------------------------------------------

    def _rock(self, frame, cx, cy):
        X, Y = np.meshgrid(np.arange(cx, cx + VIEW), np.arange(cy, cy + VIEW))
        out = np.full((VIEW, VIEW), C_ROCK, dtype=frame.dtype)
        out[(X + 2 * Y) % 23 == 0] = C_SEAM
        out[(11 * X + 7 * Y) % 53 == 0] = C_VEIN
        frame[:, :] = out

    def _floor(self, frame, w, cx, cy):
        for cell, ch in w.chars.items():
            if ch == "#":
                continue
            x, y = cell[0] * CELL - cx, cell[1] * CELL - cy
            if x + CELL <= 0 or y + CELL <= 0 or x >= VIEW or y >= VIEW:
                continue
            if ch == "~":
                _fill(frame, x, y, CELL, CELL, C_VOID)
                for d, (dx, dy) in DIRS.items():
                    n = (cell[0] + dx, cell[1] + dy)
                    if w.chars.get(n) != "~":
                        if d == "U":
                            _fill(frame, x, y, CELL, 1, C_VOID_EDGE)
                        elif d == "D":
                            _fill(frame, x, y + CELL - 1, CELL, 1, C_VOID_EDGE)
                        elif d == "L":
                            _fill(frame, x, y, 1, CELL, C_VOID_EDGE)
                        else:
                            _fill(frame, x + CELL - 1, y, 1, CELL, C_VOID_EDGE)
                continue
            _fill(frame, x, y, CELL, CELL, C_FLOOR)
            if ch == ":":
                _px(frame, x + 2, y + 3, C_TILE)
            elif ch == "o":
                _ring(frame, x, y, CELL, CELL, C_RECESS)
            # the carved lip where this floor cell meets solid rock
            for d, (dx, dy) in DIRS.items():
                n = (cell[0] + dx, cell[1] + dy)
                if w.chars.get(n, "#") != "#":
                    continue
                if d == "U":
                    _fill(frame, x, y, CELL, 1, C_LIP)
                elif d == "D":
                    _fill(frame, x, y + CELL - 1, CELL, 1, C_LIP)
                elif d == "L":
                    _fill(frame, x, y, 1, CELL, C_LIP)
                else:
                    _fill(frame, x + CELL - 1, y, 1, CELL, C_LIP)

    def _furniture(self, frame, w, cx, cy):
        g = self.game
        for ch in w.chambers:
            spot = w.inlays[ch["cid"]]
            if spot:
                _bm(frame, spot[0] * CELL - cx, spot[1] * CELL - cy,
                    SEALS[ch["seal"]], C_SEAL, scale=2)
        for cell in w.cradles:
            x, y = cell[0] * CELL - cx, cell[1] * CELL - cy
            _ring(frame, x + 1, y + 1, CELL - 2, CELL - 2, C_CRADLE)
        for cell in w.entries:
            x, y = cell[0] * CELL - cx, cell[1] * CELL - cy
            for dx, dy in ((0, 0), (CELL - 1, 0), (0, CELL - 1), (CELL - 1, CELL - 1)):
                _px(frame, x + dx, y + dy, C_ENTRY)
        for ch in w.chambers:
            if not ch["goal"]:
                continue
            gx = min(c[0] for c in ch["goal"]) * CELL - cx
            gy = min(c[1] for c in ch["goal"]) * CELL - cy
            _fill(frame, gx, gy, 2 * CELL, 2 * CELL, C_GOAL)
            _fill(frame, gx + 2, gy + 2, 2 * CELL - 4, 2 * CELL - 4, C_ORANGE)
            _fill(frame, gx + 4, gy + 4, 2 * CELL - 8, 2 * CELL - 8, C_GOAL)
        for oid, kind, _c in w.objects:
            cell = None
            for o, c in g.state[2]:
                if o == oid:
                    cell = c
                    break
            if cell is None:
                continue
            spec = SIG.get(kind) or GEAR[kind]
            _bm(frame, cell[0] * CELL - cx, cell[1] * CELL - cy,
                spec["glyph"], spec["color"])

    # -- portals ---------------------------------------------------------

    def _mouth(self, frame, w, cid, pidx, cx, cy):
        g = self.game
        p = w.portals[cid][pidx]
        x, y = p["at"][0] * CELL - cx, p["at"][1] * CELL - cy
        if x + 2 * CELL <= 0 or y + 2 * CELL <= 0 or x >= VIEW or y >= VIEW:
            return
        shut = g.shut
        kindq, dest = ("barred", None) if shut else mouth_state(w, g.state, cid, pidx)
        reopen = kindq == "open" and (cid, pidx) in g.state[3]
        col = C_DEAD
        if kindq == "open":
            post = (w.entries[dest], g.state[1], g.state[2],
                    g.state[3] | {(cid, pidx)}, g.state[4], g.state[5] or reopen)
            if winnable(w.idx, post, g.entry_gear):
                col = C_HOME if w.chambers[dest]["goal"] else C_LIVE
        # the rim carries the same reading as the sigil inside it, so a mouth worth
        # walking into is legible at a glance and a barren one recedes
        fcol = C_BARRED if kindq == "barred" else (C_PURPLE if reopen else col)
        _fill(frame, x, y, 2 * CELL, 2 * CELL, C_BLACK)
        _ring(frame, x, y, 2 * CELL, 2 * CELL, fcol, LENS_SKIP[p["lens"]])
        if kindq == "barred":
            for k in range(-2 * CELL, 2 * CELL, 3):
                for i in range(2 * CELL):
                    j = i + k
                    if 0 <= j < 2 * CELL:
                        _px(frame, x + i, y + j, C_BARRED)
            return
        if kindq == "hollow":
            # nothing the walker is carrying keys this lens: an empty socket
            _ring(frame, x + 4, y + 4, 2 * CELL - 8, 2 * CELL - 8, C_DEAD)
            return
        _bm(frame, x + 3, y + 3, SEALS[w.chambers[dest]["seal"]], col)
        if "EYE" in g.state[4]:
            cells = w.chambers[dest]["cells"]
            found = [w.kind[o] for o, c in sorted(g.state[2]) if c in cells][:4]
            corners = ((x + 1, y + 1), (x + 2 * CELL - 3, y + 1),
                       (x + 1, y + 2 * CELL - 3), (x + 2 * CELL - 3, y + 2 * CELL - 3))
            for k, (sx, sy) in zip(found, corners):
                if k in SIG:
                    _bm(frame, sx, sy, STAMP[k], SIG[k]["color"])
                else:
                    _fill(frame, sx, sy, 2, 2, GEAR[k]["color"])

    # -- the walker ------------------------------------------------------

    def _walker(self, frame, w, cx, cy):
        g = self.game
        pos, carried, _pl, _sp, gear, key_used = g.state
        x, y = pos[0] * CELL - cx, pos[1] * CELL - cy
        body = C_BODY_SHUT if g.shut else C_BODY
        _fill(frame, x + 1, y + 1, CELL - 2, CELL - 2, C_VDGRAY)   # the hollow it carries in
        _ring(frame, x, y, CELL, CELL, body)                       # the walker's shell
        # carried objects sit inside the shell, on opposite diagonals
        for oid, (sx, sy) in zip(carried, ((x + 1, y + 1), (x + 3, y + 3))):
            k = w.kind[oid]
            _bm(frame, sx, sy, STAMP[k], C_BODY_SHUT if g.shut else SIG[k]["color"])
        # tools clamp onto the shell itself: prong left, eye right, mesh top and bottom
        if "PRONG" in gear:
            col = C_DGRAY if (key_used or g.shut) else GEAR["PRONG"]["color"]
            _fill(frame, x, y + 1, 1, CELL - 2, col)
        if "EYE" in gear:
            col = C_DGRAY if g.shut else GEAR["EYE"]["color"]
            _fill(frame, x + CELL - 1, y + 1, 1, CELL - 2, col)
        if "MESH" in gear:
            col = C_DGRAY if g.shut else GEAR["MESH"]["color"]
            _fill(frame, x + 1, y, CELL - 2, 1, col)
            _fill(frame, x + 1, y + CELL - 1, CELL - 2, 1, col)

    def _mark(self, frame, cx, cy):
        m = self.game.mark
        if not m:
            return
        cell, kindq = m
        x, y = cell[0] * CELL - cx, cell[1] * CELL - cy
        if kindq == "refuse":
            # nothing here to take and nothing to set down: the shell strikes through
            for i in range(1, CELL - 1):
                _px(frame, x + i, y + i, C_REFUSE)
                _px(frame, x + CELL - 1 - i, y + i, C_REFUSE)
            return
        _ring(frame, x, y, CELL, CELL, C_REFUSE)
        if kindq == "barred":
            for i in range(CELL):
                _px(frame, x + i, y + i, C_REFUSE)
        elif kindq == "hollow":
            _fill(frame, x + 2, y + 2, 2, 2, C_REFUSE)

    # -- frame -----------------------------------------------------------

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game
        w = WORLDS[g.level_index]
        cx, cy = camera(g.state[0])
        g.cam = (cx, cy)
        self._rock(frame, cx, cy)
        self._floor(frame, w, cx, cy)
        self._furniture(frame, w, cx, cy)
        for cid, pl in enumerate(w.portals):
            for pidx in range(len(pl)):
                self._mouth(frame, w, cid, pidx, cx, cy)
        self._walker(frame, w, cx, cy)
        self._mark(frame, cx, cy)
        return frame


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class Wr01(ARCBaseGame):
    def __init__(self):
        self.display = Wr01Display(self)

        # on_set_level() runs inside super().__init__(), so everything it and
        # the display touch has to exist first.
        self.carry_gear = frozenset()      # tools; the only thing that crosses a level
        self.entry_gear = frozenset()      # what the walker had when this level began
        self._entry_level = None
        self.state = start_state(WORLDS[0])
        self.shut = False
        self.mark = None
        self.cam = (0, 0)

        levels = [Level(sprites=[], grid_size=(VIEW, VIEW), data=ld, name=ld["name"])
                  for ld in LEVELS]

        super().__init__(
            "wr",
            levels,
            Camera(0, 0, VIEW, VIEW, C_ROCK, C_ROCK, [self.display]),
            False,
            len(levels),
            [1, 2, 3, 4, 5],          # d-pad plus one take/set verb
        )

    # -- level setup ------------------------------------------------------

    def on_set_level(self, level: Level) -> None:
        """Rebuild the chamber state. Tools survive a level boundary; on a retry of
        the same level the walker gets back exactly the tools it arrived with, so a
        failed attempt cannot quietly hand it gear it had not earned."""
        i = self.level_index
        if self._entry_level != i:
            self.entry_gear = self.carry_gear
            self._entry_level = i
        else:
            self.carry_gear = self.entry_gear
        self.state = start_state(WORLDS[i], self.entry_gear)
        self.shut = False
        self.mark = None
        self.cam = camera(self.state[0])

    def handle_reset(self) -> None:
        """The base class promotes a RESET to a full restart when `_action_count == 0`,
        and every level load zeroes it, so a RESET on the first action of a level would
        throw the walker back to level 1. Full restart only from NOT_PLAYED and WIN --
        and a full restart is the one thing that takes the tools away again."""
        if self._state in (GameState.NOT_PLAYED, GameState.WIN):
            self.carry_gear = frozenset()
            self.entry_gear = frozenset()
            self._entry_level = None
            self.full_reset()
        else:
            self.level_reset()

    # -- engine entry point ----------------------------------------------

    def step(self) -> None:
        aid = self.action.id.value
        self.mark = None
        if aid in ACTION_DIR or aid == TAKE:
            press = ACTION_DIR.get(aid, "T")
            w = WORLDS[self.level_index]
            nxt, outcome = apply(w, self.state, press)
            if outcome == "win":
                self.state = nxt
                self.next_level()
                self.complete_action()
                return
            if outcome in ("bump", "barred", "hollow"):
                dx, dy = DIRS[press]
                self.mark = ((self.state[0][0] + dx, self.state[0][1] + dy), outcome)
            elif outcome == "refuse":
                self.mark = (self.state[0], "refuse")
            self.state = nxt
            if outcome == "gear":
                self.carry_gear = nxt[4]
            # The warren closes only when it can no longer be solved -- and every
            # move that gets there was drawn as a dark mouth before it was pressed.
            if not winnable(w.idx, self.state, self.entry_gear):
                self.shut = True
                self.lose()
        # aid == 0: handle_reset() has already rebuilt the level.
        self.complete_action()

