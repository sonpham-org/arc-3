# Author: Claude Opus 5
# Date: 2026-09-07
# PURPOSE: pr01 "Press" -- an ARC-AGI-3 environment with no goal object at all. Slabs of a
#   machine push in from the frame edge, one cell per action, each side stopping at its own
#   notch cut into the housing. The player wins by still standing when every slab has
#   stopped, and loses by being under one. Nothing to reach, collect or press.
#
#   2026-09-07 rework. The first cut drew the surviving rectangle on the floor as a pink
#   outline, which handed the player the answer: walk inside the box and wait. That removed
#   all the reasoning and made the rest of the display meaningless. It is gone. What is left
#   is four notches in the housing -- one per advancing side, each marking where THAT slab
#   stops -- and a board of pillar chambers. Several chambers look equally like shelter; the
#   intersection of the notch planes decides which one actually survives, and the chamber
#   walls decide whether it can be reached in time. Nothing relies on memory: every notch,
#   including the one for a second closing, is on screen from frame 0.
#
#   Each level adds one rule: pillar chambers, a press from two sides only, a cracked pillar
#   that gives way as the slab arrives, a second closing that invalidates the first shelter,
#   a piston in the corridor, and all of it at once. Core-knowledge priors only -- objectness,
#   geometry, basic physics, agentness. No text, glyphs, numbers, bars or pips.
# SRP/DRY check: Pass -- self-contained. The rules live in one pure function, `transition`,
#   which the game, the smoke-test solver and the gate's exact counter all share.
"""Press -- survive a room that closes in.

ACTION1/2/3/4 step up/down/left/right. Every action, every advancing slab moves one cell.
Each slab stops level with its own notch in the housing. Be somewhere all four stop short of.
7 levels, no RNG, d-pad only.
"""

from collections import namedtuple

import numpy as np
from arcengine import ARCBaseGame, Camera, GameState, Level, RenderableUserDisplay

# ---------------------------------------------------------------------------
# Palette (ARC-3 indices). The under-used end: purple floor, maroon machine, orange
# pillars, magenta player, yellow pressing face. Grey is structure only -- the housing.
# Nothing else in the game is magenta, and nothing else is white.
# ---------------------------------------------------------------------------

C_WHITE, C_LGRAY = 0, 1
C_MAGENTA, C_LMAGENTA, C_YELLOW, C_ORANGE, C_MAROON, C_PURPLE = 6, 7, 11, 12, 13, 15

C_FLOOR = C_PURPLE       # the room
C_WALL = C_MAROON        # slab body, piston body, and the housing they all slide out of
C_FACE = C_YELLOW        # the leading face of a slab, 2px, and the piston's nose
C_PILLAR = C_ORANGE      # static chamber walls; a hollow one is cracked and will give way
C_PLAYER = C_LMAGENTA    # the player's body -- nothing else on the board is pink
C_PLAYER_EDGE = C_MAGENTA  # its rounded corners: the only round thing in the game
C_HOUSING = C_MAROON     # same material as the slabs: this is all one machine
C_MARK = C_WHITE         # notch: where the slab beside it stops on THIS closing
C_MARK_NEXT = C_LGRAY    # a dimmer, shorter notch: where it stops on the closing after

# ---------------------------------------------------------------------------
# Geometry -- 15x15 cells of 4px = 60px of board inside a 2px housing = 64x64.
# 4px cells make a slab's one-cell advance a 4px jump: consecutive frames differ obviously.
# ---------------------------------------------------------------------------

W = 15
CELL = 4
OX = OY = 2
BOARD = W * CELL          # 60
CENTRE = (W // 2, W // 2)

DIR_OF_ACTION = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}

SIDES = ("T", "B", "L", "R")


def side_dist(i, x, y):
    """How many cells cell (x, y) sits in front of side i's slab."""
    return (y, W - 1 - y, x, W - 1 - x)[i]


# ---------------------------------------------------------------------------
# Levels
#
# `depths` gives, per advancing side, the front value that side stops at, one entry per
# closing phase. front f on side T means rows 0..f-1 are slab, so a cell survives T iff
# y >= f; the face rests on cell row f-1, which is where T's notch is cut. A side absent
# from `depths` never moves and shows no slab -- that asymmetry is visible on frame 0.
# Every advancing side starts at front 1, so the machine is already touching the frame
# edge before the first action, and the first action visibly thickens it.
#
# `map` is the board. '#' pillar, 'o' cracked pillar (drawn hollow -- it gives way when a
# face reaches one cell from it), '@' the player's start, '~' piston track, '*' piston
# track and its starting cell, '.' floor.
# ---------------------------------------------------------------------------

# Sixteen chambers of 3x3: pillar walls down columns 3, 7, 11 and across rows 3, 7, 11,
# each of the twenty-four chamber-to-chamber walls pierced by exactly one doorway. The
# doorways are deliberately not aligned, so no straight run and no short repeating key
# cycle threads the maze. Which chamber survives is never the nearest one, never the
# middle one and never simply the one furthest from the deepest slab -- it is whichever
# one every notch plane agrees on, and reaching it costs most of the actions available.
MAZE = [
    "...#.......#...",   # 0   doorway through column 7
    "...#...#.......",   # 1   doorway through column 11
    ".......#...#...",   # 2   doorway through column 3
    ".#####.##.###.#",   # 3   doorways at x=0, 6, 9, 13
    ".......#...#...",   # 4   doorway through column 3
    "...#...#.......",   # 5   doorway through column 11
    "...#.......#...",   # 6   doorway through column 7
    "##.#.#####.###.",   # 7   doorways at x=2, 4, 10, 14
    "...#...#.......",   # 8   doorway through column 11
    "...#.......#...",   # 9   doorway through column 7
    ".......#...#...",   # 10  doorway through column 3
    "#.###.##.###.##",   # 11  doorways at x=1, 5, 8, 12
    ".......#...#...",   # 12  doorway through column 3
    "...#...#.......",   # 13  doorway through column 11
    "...#.......#...",   # 14  doorway through column 7
]


def maze(**edits):
    """MAZE with single cells overwritten: maze(c7_6="@") sets (x=7, y=6)."""
    rows = [list(r) for r in MAZE]
    for key, ch in edits.items():
        x, y = (int(v) for v in key[1:].split("_"))
        rows[y][x] = ch
    return ["".join(r) for r in rows]


LEVELS = [
    {
        # NEW: the machine. Four slabs, already touching the frame on frame 0, each moving
        # one cell per action and stopping level with its own notch. Empty room, symmetric,
        # four cells of slack in every direction -- move off the top edge and you cannot
        # fail. This level exists to show the mechanism honestly, nothing else.
        "name": "Room",
        "depths": {"T": [5], "B": [5], "L": [5], "R": [5]}, "pause": 0,
        "map": ["..............."] * 3
               + [".......@......."]
               + ["..............."] * 11,
    },
    {
        # NEW: chambers, and slabs that stop at different depths. Three sides move and the
        # bottom does not: the bottom notch is missing entirely, the top slab stops seven
        # cells in, the right one grinds nearly the whole way across. Sixteen chambers look
        # alike. Six of them satisfy one plane. Exactly one satisfies all three, and it is
        # neither the nearest, nor the middle, nor the far corner.
        "name": "Pocket",
        "depths": {"T": [8], "B": [4], "R": [12]}, "pause": 0,
        "map": maze(c6_3="@"),
    },
    {
        # NEW: two slabs that face each other stop on the same line. The bottom one travels
        # eleven cells and the top one two, and they come to rest on either side of a single
        # pillar row -- so the surviving floor is not a chamber at all, it is that row's
        # doorways. The third slab, from the left, decides which of them. Walking into any
        # room is fatal here however deep in it you stand; you have to end up standing in a
        # hole in a wall.
        "name": "Vise",
        "depths": {"T": [3], "B": [11], "L": [6]}, "pause": 0,
        "map": maze(c5_8="@"),
    },
    {
        # NEW: a cracked pillar, drawn hollow. It gives way when a face arrives one cell
        # from it, and not before. The room is the one from Pocket, but the doorway the
        # route needs is plugged: push against it, it holds, the top face lands beside it,
        # it opens, step through. The way round exists and is too slow -- the smoke test
        # pins that replacing the crack with a solid pillar makes the level unwinnable.
        "name": "Crack",
        "depths": {"T": [8], "B": [4], "R": [12]}, "pause": 0,
        "map": maze(c6_5="@", c4_7="o"),
    },
    {
        # NEW: a second closing. Every slab stops on its white notch, holds, then the left
        # one moves again to the shorter magenta notch beyond it. Three chambers survive
        # the first closing and only the far one survives the second, so the shelter that
        # is obviously right when the machine first stops is the one that kills you. The
        # magenta notch has been on screen since frame 0 saying so.
        "name": "Twice",
        "depths": {"T": [8, 8], "B": [4, 4], "L": [4, 12]}, "pause": 3,
        "map": maze(c6_3="@"),
    },
    {
        # NEW: a piston, made of the same machine -- maroon body, yellow nose pointing at
        # the cell it takes next. It shuttles across the corridor the route has to use and
        # presses whatever it steps onto. Walking straight through walks into it; you cross
        # behind it, on the side it is leaving.
        "name": "Sweep",
        "depths": {"B": [12], "L": [8], "R": [4]}, "pause": 0,
        "map": maze(c4_4="@", c4_6="~", c5_6="~", c6_6="~", c7_6="*"),
    },
    {
        # Everything at once, on the room from Twice: two closings, a cracked pillar in
        # the doorway of the chamber that survives the second one, and a piston shuttling
        # inside that chamber. Both additions are load-bearing -- plugging the crack with
        # a solid pillar makes the level unwinnable, and the piston takes the clear rate
        # from 1/95m to 1/1.27bn.
        "name": "Gauntlet",
        "depths": {"T": [8, 8], "B": [4, 4], "L": [4, 12]}, "pause": 3,
        "map": maze(c6_3="@", c11_8="o", c12_8="~", c13_8="~", c14_8="*"),
    },
]


# ---------------------------------------------------------------------------
# Pure rules
# ---------------------------------------------------------------------------

State = namedtuple("State", "pos fronts phase hold midx mdir crumbled alive done")


class Lvl:
    """A level's constants, precomputed once."""

    def __init__(self, ldef):
        self.name = ldef["name"]
        self.pause = ldef["pause"]
        dep = ldef["depths"]
        self.nphase = max(len(v) for v in dep.values())
        self.targets = [tuple(dep[s][k] if s in dep else 0 for s in SIDES)
                        for k in range(self.nphase)]
        self.f0 = tuple(1 if s in dep else 0 for s in SIDES)
        self.moving = tuple(i for i in range(4) if self.f0[i])

        grid = ldef["map"]
        assert len(grid) == W and all(len(r) == W for r in grid), "map must be 15x15"
        pillars, cracked, track, start, m_at = set(), set(), [], None, 0
        for y, row in enumerate(grid):
            for x, ch in enumerate(row):
                if ch == "#":
                    pillars.add((x, y))
                elif ch == "o":
                    cracked.add((x, y))
                elif ch == "@":
                    start = (x, y)
                elif ch in "~*":
                    if ch == "*":
                        m_at = len(track)
                    track.append((x, y))
        assert start is not None, f"{self.name}: no '@' in the map"
        self.pillars = frozenset(pillars)
        self.cracked = frozenset(cracked)
        self.start = start
        self.track = track
        self.m_at = m_at
        self.m_dir = -1 if track and m_at == len(track) - 1 else 1

        self.sd = {(x, y): tuple(side_dist(i, x, y) for i in range(4))
                   for y in range(W) for x in range(W)}

        prev, total = self.f0, 0
        for k, t in enumerate(self.targets):
            assert all(t[i] >= prev[i] for i in range(4)), f"{self.name}: slab moves backwards"
            total += max(t[i] - prev[i] for i in range(4)) + (self.pause if k else 0)
            prev = t
        self.total = total

    def rect(self, phase=-1):
        """(x0, x1, y0, y1) inclusive -- the cells no slab reaches by the end of `phase`."""
        t = self.targets[phase]
        return t[2], W - 1 - t[3], t[0], W - 1 - t[1]


def crushed(lvl, fronts, cell):
    sd = lvl.sd[cell]
    return any(sd[i] < fronts[i] for i in range(4))


def _crumbled(lvl, fronts, seen):
    """A cracked pillar gives way once a face is within one cell of it, and stays given."""
    out = set(seen)
    for c in lvl.cracked:
        if min(lvl.sd[c][i] - fronts[i] for i in lvl.moving) <= 1:
            out.add(c)
    return frozenset(out)


def initial(lvl):
    return State(lvl.start, lvl.f0, 0, 0, lvl.m_at, lvl.m_dir,
                 _crumbled(lvl, lvl.f0, ()), True, False)


def mover_next(lvl, st):
    """Index and direction of the piston after its next step (it bounces at track ends)."""
    if not lvl.track:
        return st.midx, st.mdir
    ni, d = st.midx + st.mdir, st.mdir
    if not 0 <= ni < len(lvl.track):
        d = -d
        ni = st.midx + d
    return ni, d


def blocked(lvl, st, cell):
    x, y = cell
    if not (0 <= x < W and 0 <= y < W):
        return True
    if crushed(lvl, st.fronts, cell) or cell in lvl.pillars:
        return True
    if cell in lvl.cracked and cell not in st.crumbled:
        return True
    return bool(lvl.track) and lvl.track[st.midx] == cell


def transition(lvl, st, aid):
    """One action. Order: the player steps, the piston steps, every slab that has not
    reached its notch advances one cell (or the hold between closings burns an action),
    the crush is checked, cracked pillars beside a face give way."""
    if st.done or not st.alive:
        return st
    pos = st.pos
    if aid in DIR_OF_ACTION:
        dx, dy = DIR_OF_ACTION[aid]
        nxt = (pos[0] + dx, pos[1] + dy)
        if not blocked(lvl, st, nxt):
            pos = nxt
    alive = True
    midx, mdir = st.midx, st.mdir
    if lvl.track:
        midx, mdir = mover_next(lvl, st)
        if lvl.track[midx] == pos:
            alive = False

    fronts, phase, hold, done = list(st.fronts), st.phase, st.hold, False
    if hold > 0:
        hold -= 1
    else:
        target = lvl.targets[phase]
        for i in range(4):
            if fronts[i] < target[i]:
                fronts[i] += 1
        if tuple(fronts) == target:
            if phase == lvl.nphase - 1:
                done = True
            else:
                phase += 1
                hold = lvl.pause
    fronts = tuple(fronts)
    if crushed(lvl, fronts, pos):
        alive = False
    return State(pos, fronts, phase, hold, midx, mdir,
                 _crumbled(lvl, fronts, st.crumbled), alive, done)


# ---------------------------------------------------------------------------
# Display -- recomputed from the state every frame
# ---------------------------------------------------------------------------

class Pr01Display(RenderableUserDisplay):
    def __init__(self, game):
        self.game = game

    @staticmethod
    def _px(cell):
        return OX + cell[0] * CELL, OY + cell[1] * CELL

    def _notches(self, frame, lvl, st):
        """One notch per advancing side, cut into the housing beside it, level with the cell
        its face comes to rest on. Full-length and white for the closing under way; half
        length and magenta for the closing after it. Four planes, never joined into a
        rectangle: the player has to intersect them."""
        for k in range(st.phase, lvl.nphase):
            now = k == st.phase
            colour = C_MARK if now else C_MARK_NEXT
            length, off = (CELL, 0) if now else (2, 1)
            for i, side in enumerate(SIDES):
                if not lvl.f0[i]:
                    continue
                # A slab whose next target is where it already stops has no second notch;
                # drawing one would paint a dimmer stub over the middle of its live notch.
                if not now and lvl.targets[k][i] == lvl.targets[k - 1][i]:
                    continue
                d = lvl.targets[k][i]
                idx = d - 1 if side in ("T", "L") else W - d
                p = (OY if side in ("T", "B") else OX) + idx * CELL + off
                if side in ("T", "B"):
                    frame[p:p + length, 0:OX] = colour
                    frame[p:p + length, 64 - OX:64] = colour
                else:
                    frame[0:OY, p:p + length] = colour
                    frame[64 - OY:64, p:p + length] = colour

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game
        lvl, st = g.lvl, g.st
        frame[:, :] = C_HOUSING
        board = frame[OY:OY + BOARD, OX:OX + BOARD]
        board[:, :] = C_FLOOR

        fT, fB, fL, fR = st.fronts
        # Slab bodies: flat maroon mass, no texture -- the face is the only bright thing.
        if fT:
            board[:fT * CELL, :] = C_WALL
        if fB:
            board[(W - fB) * CELL:, :] = C_WALL
        if fL:
            board[:, :fL * CELL] = C_WALL
        if fR:
            board[:, (W - fR) * CELL:] = C_WALL

        for cell in lvl.pillars | lvl.cracked:
            if crushed(lvl, st.fronts, cell) or cell in st.crumbled:
                continue
            px, py = self._px(cell)
            frame[py:py + CELL, px:px + CELL] = C_PILLAR
            if cell in lvl.cracked:
                frame[py + 1:py + 3, px + 1:px + 3] = C_FLOOR   # hollow: this one will open

        # Leading faces last, clipped to the open room, so the machine reads as four solid
        # bright edges closing on the player rather than a decorative border.
        y0, y1 = fT * CELL, (W - fB) * CELL
        x0, x1 = fL * CELL, (W - fR) * CELL
        if x0 < x1 and y0 < y1:
            if fT:
                board[y0 - 2:y0, x0:x1] = C_FACE
            if fB:
                board[y1:y1 + 2, x0:x1] = C_FACE
            if fL:
                board[y0:y1, x0 - 2:x0] = C_FACE
            if fR:
                board[y0:y1, x1:x1 + 2] = C_FACE

        # The piston: a pressing face with a body behind it, like the slabs, but a whole
        # cell of it. Yellow leads, maroon trails, so the block is bright wherever it is --
        # a maroon-bodied piston vanished against the maroon housing at the board edge --
        # and the maroon tail says which way it came from, so the yellow says where it goes.
        if lvl.track:
            cell = lvl.track[st.midx]
            if not crushed(lvl, st.fronts, cell):
                px, py = self._px(cell)
                frame[py:py + CELL, px:px + CELL] = C_FACE
                nx, ny = lvl.track[mover_next(lvl, st)[0]]
                if nx > cell[0]:
                    frame[py:py + CELL, px:px + 2] = C_WALL
                elif nx < cell[0]:
                    frame[py:py + CELL, px + 2:px + CELL] = C_WALL
                elif ny > cell[1]:
                    frame[py:py + 2, px:px + CELL] = C_WALL
                else:
                    frame[py + 2:py + CELL, px:px + CELL] = C_WALL

        # The player: a full-cell pink token with darker rounded corners. It is the only
        # pink thing anywhere and the only one with a rounded outline, so it stays findable
        # against the orange chamber walls. Flattened to a line once the machine closes.
        px, py = self._px(st.pos)
        if st.alive:
            frame[py:py + CELL, px:px + CELL] = C_PLAYER
            frame[py, px] = frame[py, px + 3] = C_PLAYER_EDGE
            frame[py + 3, px] = frame[py + 3, px + 3] = C_PLAYER_EDGE
        else:
            frame[py + 2, px:px + CELL] = C_PLAYER

        self._notches(frame, lvl, st)
        return frame


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

LVLS = [Lvl(d) for d in LEVELS]


class Pr01(ARCBaseGame):
    def __init__(self):
        self.display = Pr01Display(self)
        # on_set_level() runs inside super().__init__(); these must exist first.
        self.lvl = LVLS[0]
        self.st = initial(self.lvl)
        levels = [Level(sprites=[], grid_size=(64, 64), data=d, name=d["name"])
                  for d in LEVELS]
        super().__init__(
            "pr",
            levels,
            Camera(0, 0, 64, 64, C_HOUSING, C_HOUSING, [self.display]),
            False,
            len(levels),
            [1, 2, 3, 4],
        )

    def on_set_level(self, level: Level) -> None:
        self.lvl = LVLS[self.level_index]
        self.st = initial(self.lvl)

    def handle_reset(self) -> None:
        """The base class promotes a RESET to a full restart whenever `_action_count == 0`,
        and `_action_count` is zeroed by every level load -- so a RESET taken as the first
        action of a level would throw the player back to level 1. Full restart only from
        NOT_PLAYED and WIN; anywhere else a RESET retries the level that is open."""
        if self._state in (GameState.NOT_PLAYED, GameState.WIN):
            self.full_reset()
        else:
            self.level_reset()

    def step(self) -> None:
        aid = self.action.id.value
        if aid == 0:
            # handle_reset() has already rebuilt the level; nothing to charge.
            self.complete_action()
            return
        # Any other action -- including the unadvertised 5/6/7 -- is a step that does not
        # move. The machine advances regardless: standing still is never free.
        self.st = transition(self.lvl, self.st, aid)
        if not self.st.alive:
            self.lose()
        elif self.st.done:
            self.next_level()
        self.complete_action()
