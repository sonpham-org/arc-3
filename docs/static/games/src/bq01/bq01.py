# Author: Claude Opus 5
# Date: 2026-08-27 09:40
# PURPOSE: bq01 "Balance" -- an ARC-AGI-3 environment. Blocks are carried from a supply
#   yard onto the pans of a balance scale; a level clears when the beam is released and
#   hangs level with the required number of blocks aboard. A block's weight is its AREA in
#   cells (never a printed number -- ARC bans glyphs), so early levels are read directly
#   off the geometry. From the middle of the game a DENSE block appears whose weight is not
#   its size, and the only way to learn its true value is to weigh it against blocks of
#   known weight and chain the results. That transitive, comparison-driven inference is the
#   cognitive demand; nothing in the ~300-game corpus tests it. Implements the arcengine
#   ARCBaseGame contract; consumed by the Pyodide browser player, the CLI agent and the
#   duck-harness bundle.
# SRP/DRY check: Pass -- self-contained environment. The three catalogued "weight" games
#   (wp01, pw01, vt01) are sokoban pressure-plate puzzles with a threshold, not balances:
#   no relative magnitude, no comparison of two sides, nothing to reuse.
"""Balance -- load the pans until the beam hangs level.

Click a block to pick it up, click a pan to drop it in, click a block already on a pan to
take it back. The beam is LATCHED while you rearrange: press ACTION5 to release it and
see which way it goes. A level clears when the beam is released, every pan carries at
least one block, the two sides of every beam weigh the same, and exactly the required
number of blocks (the pip row, top-left) is aboard.

A block's weight is the number of cells it is built from -- count the bright pips. Orange
riveted blocks are the exception: their weight is NOT their size. Usually they are heavier
than they look; by the last level one of them is lighter. The only way to find out is to put
one on a pan and weigh it against blocks you already know.

8 levels, each adding exactly one rule. Fully deterministic -- no RNG anywhere. You lose
by running out of action budget, or of weighings once those are rationed.
"""

import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

# ---------------------------------------------------------------------------
# Palette. The catalogued corpus is 60% greyscale and maroon is 0.0% of official
# pixels, so this game is built on the unused end: a maroon field, magenta and orange
# objects, purple apparatus. Greys and black appear only as structure -- the rule line
# under the yard, the 1px gutter that keeps adjacent blocks countable, dead sockets.
# Every distinction below is also carried by shape or position, never by hue alone.
# ---------------------------------------------------------------------------

C_WHITE, C_LGRAY, C_GRAY, C_DGRAY, C_VDGRAY, C_BLACK = 0, 1, 2, 3, 4, 5
C_MAGENTA, C_LMAGENTA, C_RED, C_BLUE, C_LBLUE = 6, 7, 8, 9, 10
C_YELLOW, C_ORANGE, C_MAROON, C_GREEN, C_PURPLE = 11, 12, 13, 14, 15

FIELD = C_MAROON            # the board itself
RULE = C_BLACK              # gutters, gridlines, the yard divider
APPARATUS = C_PURPLE        # beam, pivot, hangers
SOCKET = C_VDGRAY           # outline of a block that has left the yard

BODY = (C_MAGENTA, C_ORANGE)      # honest, dense
PIP = (C_LMAGENTA, C_YELLOW)      # one pip per cell -> the weight is countable
SELECT_RING = C_YELLOW
LATCH = C_YELLOW

PAN_LATCHED, PAN_HEAVY, PAN_LIGHT, PAN_LEVEL = C_PURPLE, C_RED, C_LBLUE, C_GREEN

# ---------------------------------------------------------------------------
# Geometry. Two layouts: one beam (levels 1-5) and two stacked beams (6-8).
# ---------------------------------------------------------------------------

CELL = 3                    # pixels per weight-cell
YARD_W = 21                 # yard width in cells (== 63px)
PAN_CX = (15, 48)           # x of the two hang points; the stand sits midway
PIVOT_X = (PAN_CX[0] + PAN_CX[1]) // 2
COL_W = 3                   # width of the central stand
BEAM_X0, BEAM_X1 = 8, 55    # the beam is drawn past its hang points

# One beam (levels 1-5) or two stacked beams sharing one stand (6-8). Every value is
# chosen so the lowest dish at full tilt still clears the yard divider, and so the upper
# beam's dish never reaches the lower beam's stroke.
GEO = {
    1: {"beams": [(16, 5)], "drop": 4, "tray_h": 4, "tray_w": 8,
        "yard_y": 41, "yard_rows": 7},
    2: {"beams": [(9, 3), (29, 3)], "drop": 2, "tray_h": 3, "tray_w": 9,
        "yard_y": 47, "yard_rows": 5},
}

BAR_Y, BAR_X0, BAR_X1 = 0, 1, 63          # action-budget bar
PIP_Y = 2                                 # both pip rows
QUOTA_X, QUOTA_PITCH = 2, 4               # 3x3 squares, left: blocks required aboard
WEIGH_X1, WEIGH_PITCH = 62, 2             # 1x3 bars, right: weighings left

CLICK_COST = 1
WEIGH_COST = 3
SWING_FRAMES = 3            # the beam visibly swings into its answer

# ---------------------------------------------------------------------------
# Block shapes. A block of weight w is built from w cells, so its AREA is its weight and
# a human reads it by counting. Shapes stay <= 6 cells wide; only weights above 12 are
# three cells tall, and those never appear on the two-beam layout.
# ---------------------------------------------------------------------------

SHAPES = {
    1: ("#",),
    2: ("##",),
    3: ("###",),
    4: ("##", "##"),
    5: ("###", "##."),
    6: ("###", "###"),
    7: ("####", "###."),
    8: ("####", "####"),
    9: ("#####", "####."),
    10: ("#####", "#####"),
    11: ("######", "#####."),
    12: ("######", "######"),
    13: ("#####", "#####", "###.."),
    14: ("#####", "#####", "####."),
    15: ("#####", "#####", "#####"),
    16: ("######", "######", "####.."),
    17: ("######", "######", "#####."),
    18: ("######", "######", "######"),
}


def shape_of(size):
    rows = SHAPES[size]
    cells = frozenset((x, y) for y, row in enumerate(rows)
                      for x, ch in enumerate(row) if ch == "#")
    return max(len(r) for r in rows), len(rows), cells


# ---------------------------------------------------------------------------
# Levels. Each block is (visible_size, true_weight); they differ only for DENSE blocks.
# "quota" is how many blocks must be aboard -- shown as the pip row, never as a digit.
# "weighs" caps the number of releases (0 = unlimited).
#
# Each level adds exactly one rule and keeps every earlier one:
#   1 place a block, release the beam, read the tip
#   2 no single pair balances -- sums must be combined
#   3 the quota is smaller than the supply, so blocks must be left behind
#   4 a DENSE block: weight is not size, and must be discovered by weighing
#   5 weighings are rationed, so comparisons have to be chosen
#   6 a second beam sharing the same supply: balancing one unbalances the other
#   7 two dense blocks at once
#   8 everything, at full size
# ---------------------------------------------------------------------------

LEVELS = [
    {
        # Two identical blocks and two pans. Impossible to get wrong for more than a few
        # actions, and the first release teaches the whole verb set.
        "name": "First Tip", "scales": 1, "quota": 2, "budget": 36, "weighs": 0,
        "blocks": [(6, 6), (6, 6)],
    },
    {
        # NEW: seven distinct sizes and exactly one split that balances, so a single
        # matching pair is never the answer -- the sides have to be added up.
        "name": "Two Piles", "scales": 1, "quota": 7, "budget": 44, "weighs": 0,
        "blocks": [(13, 13), (10, 10), (9, 9), (4, 4), (3, 3), (2, 2), (1, 1)],
    },
    {
        # NEW: the pip row asks for seven of the eight blocks, so one must stay behind and
        # WHICH one is the puzzle.
        "name": "Leave One", "scales": 1, "quota": 7, "budget": 50, "weighs": 0,
        "blocks": [(13, 13), (9, 9), (7, 7), (5, 5), (4, 4), (3, 3), (2, 2), (1, 1)],
    },
    {
        # NEW: the orange riveted block is DENSE -- two cells but thirteen units. Sizes are
        # now a lie: several splits that look level by area are not, so the value has to be
        # weighed out against blocks of known weight before the level can be solved.
        "name": "Dead Weight", "scales": 1, "quota": 8, "budget": 80, "weighs": 0,
        "blocks": [(9, 9), (7, 7), (6, 6), (5, 5), (4, 4), (3, 3), (2, 2), (1, 1),
                   (2, 13)],
    },
    {
        # NEW: weighings are rationed (the bar pips, top-right). Scanning candidate values
        # one at a time runs out; halving the interval does not.
        "name": "Few Tries", "scales": 1, "quota": 8, "budget": 80, "weighs": 8,
        "blocks": [(10, 10), (8, 8), (6, 6), (5, 5), (4, 4), (3, 3), (2, 2), (1, 1),
                   (3, 14)],
    },
    {
        # NEW: a second beam, fed from the same yard. Every block spent settling one beam
        # is a block the other beam no longer has -- balancing becomes a joint constraint
        # rather than one sum.
        "name": "Two Beams", "scales": 2, "quota": 8, "budget": 92, "weighs": 9,
        "blocks": [(9, 9), (7, 7), (6, 6), (4, 4), (3, 3), (2, 2), (1, 1), (2, 16)],
    },
    {
        # NEW: two dense blocks at once, so two unknowns must be pinned down before either
        # beam can be settled -- and one of the nine blocks still has to be left behind.
        "name": "Both Lie", "scales": 2, "quota": 8, "budget": 130, "weighs": 12,
        "blocks": [(9, 9), (8, 8), (5, 5), (4, 4), (3, 3), (2, 2), (1, 1),
                   (2, 17), (3, 9)],
    },
    {
        # NEW: a dense block can also be LIGHTER than it looks. The wide riveted block
        # weighs three, less than the smallest honest block on the board, which retires
        # the one heuristic that has worked so far ("riveted means heavy") and leaves
        # weighing as the only way to know anything.
        "name": "Full Weight", "scales": 2, "quota": 8, "budget": 136, "weighs": 12,
        "blocks": [(7, 7), (6, 6), (5, 5), (4, 4), (3, 3), (2, 2), (1, 1),
                   (2, 17), (8, 3)],
    },
]


# ---------------------------------------------------------------------------
# Packing. Blocks pile into a tray under gravity and sit in fixed sockets in the yard.
# ---------------------------------------------------------------------------

def pack_tray(items, width, height):
    """Lowest-then-leftmost placement, so a pan reads as a pile. None if it will not fit."""
    occ = [[False] * width for _ in range(height)]
    out = []
    for (w, h, cells) in items:
        spot = None
        for oy in range(height - h, -1, -1):
            for ox in range(0, width - w + 1):
                if all(not occ[oy + cy][ox + cx] for (cx, cy) in cells):
                    spot = (ox, oy)
                    break
            if spot:
                break
        if spot is None:
            return None
        ox, oy = spot
        for (cx, cy) in cells:
            occ[oy + cy][ox + cx] = True
        out.append(spot)
    return out


def pack_yard(items, width, height, gx=1, gy=1):
    """Reading order with a gutter, so every block in the supply is a separate object."""
    occ = [[False] * width for _ in range(height)]
    out = []
    for (w, h, _cells) in items:
        spot = None
        for oy in range(0, height - h + 1):
            for ox in range(0, width - w + 1):
                if all(not occ[y][x]
                       for y in range(oy, min(height, oy + h + gy))
                       for x in range(ox, min(width, ox + w + gx))):
                    spot = (ox, oy)
                    break
            if spot:
                break
        if spot is None:
            return None
        ox, oy = spot
        for y in range(oy, min(height, oy + h + gy)):
            for x in range(ox, min(width, ox + w + gx)):
                occ[y][x] = True
        out.append(spot)
    return out


def spread_yard(items, width, height):
    """Use the whole supply band: widen the gutters until the blocks stop fitting, then
    centre what slack is left. Keeps the board full instead of a tidy heap in one corner."""
    best = None
    for gy in range(3, 0, -1):
        for gx in range(3, 0, -1):
            slots = pack_yard(items, width, height, gx, gy)
            if slots is not None:
                best = slots
                break
        if best:
            break
    if best is None:
        return None
    used = max(oy + h for (_w, h, _c), (_ox, oy) in zip(items, best))
    off = (height - used) // 2
    return [(ox, oy + off) for (ox, oy) in best]


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

class Bq01Display(RenderableUserDisplay):
    def __init__(self, game):
        self.game = game

    # -- primitives ---------------------------------------------------------

    @staticmethod
    def _rect(frame, x, y, w, h, color):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(64, x + w), min(64, y + h)
        if x1 > x0 and y1 > y0:
            frame[y0:y1, x0:x1] = color

    def _block(self, frame, px, py, cells, dense, ring=False):
        body, pip = BODY[dense], PIP[dense]
        for (cx, cy) in cells:
            x0, y0 = px + cx * CELL, py + cy * CELL
            self._rect(frame, x0, y0, CELL, CELL, body)
            if 0 <= y0 + 1 < 64 and 0 <= x0 + 1 < 64:
                frame[y0 + 1, x0 + 1] = pip
        # A 1px black gutter on the right and bottom of every silhouette edge. Adjacent
        # blocks in a pan therefore always have one dark line between them and stay
        # countable; a dense block rules EVERY cell, which is its second, non-colour tell.
        for (cx, cy) in cells:
            x0, y0 = px + cx * CELL, py + cy * CELL
            if dense or (cx + 1, cy) not in cells:
                self._rect(frame, x0 + CELL - 1, y0, 1, CELL, RULE)
            if dense or (cx, cy + 1) not in cells:
                self._rect(frame, x0, y0 + CELL - 1, CELL, 1, RULE)
        if ring:
            xs = [px + cx * CELL for (cx, _cy) in cells]
            ys = [py + cy * CELL for (_cx, cy) in cells]
            x0, y0 = min(xs) - 1, min(ys) - 1
            w = max(xs) + CELL - x0 + 1
            h = max(ys) + CELL - y0 + 1
            self._rect(frame, x0, y0, w, 1, SELECT_RING)
            self._rect(frame, x0, y0 + h - 1, w, 1, SELECT_RING)
            self._rect(frame, x0, y0, 1, h, SELECT_RING)
            self._rect(frame, x0 + w - 1, y0, 1, h, SELECT_RING)

    # -- panels -------------------------------------------------------------

    def _hud(self, frame):
        g = self.game
        span = BAR_X1 - BAR_X0
        self._rect(frame, BAR_X0, BAR_Y, span, 2, RULE)
        filled = 0 if g.budget_max <= 0 else int(span * max(0, g.budget_left) / g.budget_max)
        if filled > 0:
            self._rect(frame, BAR_X0, BAR_Y, filled, 2,
                       C_LMAGENTA if g.budget_left * 4 > g.budget_max else C_ORANGE)

        placed = g.placed_count()
        if placed > g.quota:
            lit = C_RED
        elif placed == g.quota:
            lit = C_GREEN
        else:
            lit = C_MAGENTA
        for i in range(g.quota):
            x = QUOTA_X + i * QUOTA_PITCH
            if x + 3 > 64:
                break
            self._rect(frame, x, PIP_Y, 3, 3, lit if i < placed else SOCKET)

        if g.weigh_max:
            # widen the ticks when there is room, so a small ration stays easy to count
            wide = g.weigh_max <= 9
            pitch, width = (3, 2) if wide else (WEIGH_PITCH, 1)
            for i in range(g.weigh_max):
                x = WEIGH_X1 - (i + 1) * pitch
                if x < QUOTA_X + g.quota * QUOTA_PITCH:
                    break
                self._rect(frame, x, PIP_Y, width, 3,
                           C_YELLOW if i < g.weigh_left else SOCKET)

    def _stand(self, frame):
        """One central column carries every beam -- and gives the two-beam levels a single
        object rather than two floating ones."""
        g = self.game
        top = g.geo["beams"][0][0] - 2
        bottom = g.geo["yard_y"] - 4
        self._rect(frame, PIVOT_X - COL_W // 2, top, COL_W, bottom - top, APPARATUS)
        self._rect(frame, PIVOT_X - 4, bottom, 9, 2, APPARATUS)

    def _scale(self, frame, s):
        g = self.game
        beam_y, amp = g.geo["beams"][s]
        tray_w = g.geo["tray_w"]
        lift = amp * g.tilt[s] * g.frac
        yl, yr = beam_y + lift, beam_y - lift
        sums = g.scale_sums(s)

        for side in (0, 1):
            pan = 2 * s + side
            x0, top = g.tray_origin(pan)
            rim = top + g.geo["tray_h"] * CELL
            end_y = int(round(yl if side == 0 else yr))

            if g.arrested:
                color = PAN_LATCHED
            elif sums[0] == sums[1]:
                color = PAN_LEVEL
            else:
                color = PAN_HEAVY if (sums[0] > sums[1]) == (side == 0) else PAN_LIGHT

            # cord down to the dish, then the dish itself: two full-height walls and the
            # rim the blocks rest on. The rim colour is the reading; its HEIGHT is the
            # same reading again, so the tip survives any colour confusion.
            self._rect(frame, PAN_CX[side], end_y, 1, max(1, top - end_y), APPARATUS)
            self._rect(frame, x0 - 2, rim, tray_w * CELL + 4, 2, color)
            self._rect(frame, x0 - 2, rim - 5, 2, 5, color)
            self._rect(frame, x0 + tray_w * CELL, rim - 5, 2, 5, color)
            if g.arrested:
                # A latched pan hangs level and so does a balanced one; that is the one
                # pair of states colour alone could confuse. Break the rim into dashes so
                # "no reading yet" is a different SHAPE, not just a different hue.
                for x in range(x0 - 2, x0 + tray_w * CELL + 2, 2):
                    self._rect(frame, x, rim, 1, 2, FIELD)

            for i in g.pans[pan]:
                b = g.blocks[i]
                ox, oy = g.pan_pos[pan][i]
                self._block(frame, x0 + ox * CELL, top + oy * CELL, b["cells"],
                            b["dense"], ring=(g.selected == i))

        # the beam last, so it reads as one continuous bar in front of the stand
        for x in range(BEAM_X0, BEAM_X1 + 1):
            t = (x - PAN_CX[0]) / (PAN_CX[1] - PAN_CX[0])
            self._rect(frame, x, int(round(yl + (yr - yl) * t)) - 1, 1, 3, APPARATUS)
        # latch: a clamp across the stand, present only while the beam is held
        if g.arrested:
            self._rect(frame, PIVOT_X - 3, beam_y + 2, 7, 1, LATCH)
            self._rect(frame, PIVOT_X - 3, beam_y - 3, 7, 1, LATCH)

    def _yard(self, frame):
        g = self.game
        y0 = g.geo["yard_y"]
        self._rect(frame, 0, y0 - 2, 64, 1, RULE)
        for i, b in enumerate(g.blocks):
            ox, oy = b["slot"]
            px, py = ox * CELL, y0 + oy * CELL
            if b["at"] >= 0:                       # dead socket: where it came from
                for (cx, cy) in b["cells"]:
                    self._rect(frame, px + cx * CELL, py + cy * CELL, CELL, CELL, SOCKET)
                    self._rect(frame, px + cx * CELL + 1, py + cy * CELL + 1,
                               CELL - 2, CELL - 2, FIELD)
                continue
            sel = g.selected == i
            self._block(frame, px, py - (2 if sel else 0), b["cells"], b["dense"], ring=sel)

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game
        frame[:, :] = FIELD
        self._hud(frame)
        self._stand(frame)
        for s in range(g.n_scales):
            self._scale(frame, s)
        self._yard(frame)
        return frame


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class Bq01(ARCBaseGame):
    def __init__(self):
        self.display = Bq01Display(self)

        # on_set_level() runs inside super().__init__(), so every attribute it or the
        # renderer touches has to exist first.
        self.blocks = []
        self.pans = []
        self.pan_pos = []
        self.n_scales = 1
        self.geo = GEO[1]
        self.quota = 0
        self.selected = None
        self.arrested = True
        self.tilt = [0]
        self.frac = 0.0
        self.budget_max = self.budget_left = 0
        self.weigh_max = self.weigh_left = 0
        self._swing = 0
        self._pending_win = False

        levels = [Level(sprites=[], grid_size=(64, 64), data=ldef, name=ldef["name"])
                  for ldef in LEVELS]

        super().__init__(
            "bq",
            levels,
            Camera(0, 0, 64, 64, C_BLACK, C_BLACK, [self.display]),
            False,
            len(levels),
            [5, 6],              # 5 = release the beam, 6 = click a block or a pan
        )

    # -- level setup --------------------------------------------------------

    def on_set_level(self, level: Level) -> None:
        ldef = LEVELS[self.level_index]
        self.n_scales = ldef["scales"]
        self.geo = GEO[self.n_scales]
        self.quota = ldef["quota"]
        self.budget_max = self.budget_left = ldef["budget"]
        self.weigh_max = self.weigh_left = ldef["weighs"]

        self.blocks = []
        for size, weight in ldef["blocks"]:
            w, h, cells = shape_of(size)
            self.blocks.append({"size": size, "weight": weight, "dense": weight != size,
                                "w": w, "h": h, "cells": cells, "slot": (0, 0), "at": -1})
        slots = spread_yard([(b["w"], b["h"], b["cells"]) for b in self.blocks],
                            YARD_W, self.geo["yard_rows"])
        if slots is None:
            raise ValueError(f"level {self.level_index}: supply does not fit the yard")
        for b, slot in zip(self.blocks, slots):
            b["slot"] = slot

        self.pans = [[] for _ in range(2 * self.n_scales)]
        self.pan_pos = [{} for _ in range(2 * self.n_scales)]
        self.tilt = [0] * self.n_scales
        self.arrested = True
        self.frac = 0.0
        self._swing = 0
        self._pending_win = False
        # One block starts in hand, so the very first click on a pan does something
        # visible rather than being spent discovering that a block must be picked first.
        self.selected = 0 if self.blocks else None

    # -- queries ------------------------------------------------------------

    def placed_count(self):
        return sum(1 for b in self.blocks if b["at"] >= 0)

    def scale_sums(self, s):
        return (sum(self.blocks[i]["weight"] for i in self.pans[2 * s]),
                sum(self.blocks[i]["weight"] for i in self.pans[2 * s + 1]))

    def tray_origin(self, pan):
        """Top-left of a pan's cell grid, following the beam wherever it currently hangs."""
        s, side = pan // 2, pan % 2
        beam_y, amp = self.geo["beams"][s]
        lift = amp * self.tilt[s] * self.frac
        end_y = beam_y + (lift if side == 0 else -lift)
        x0 = PAN_CX[side] - self.geo["tray_w"] * CELL // 2
        return x0, int(round(end_y)) + self.geo["drop"]

    def block_origin(self, i):
        b = self.blocks[i]
        if b["at"] < 0:
            ox, oy = b["slot"]
            return ox * CELL, self.geo["yard_y"] + oy * CELL - (2 if self.selected == i else 0)
        x0, top = self.tray_origin(b["at"])
        ox, oy = self.pan_pos[b["at"]][i]
        return x0 + ox * CELL, top + oy * CELL

    def _block_at(self, x, y):
        for i, b in enumerate(self.blocks):
            px, py = self.block_origin(i)
            for (cx, cy) in b["cells"]:
                if (px + cx * CELL <= x < px + (cx + 1) * CELL
                        and py + cy * CELL <= y < py + (cy + 1) * CELL):
                    return i
        return None

    def _tray_at(self, x, y):
        for pan in range(2 * self.n_scales):
            x0, top = self.tray_origin(pan)
            rim = top + self.geo["tray_h"] * CELL
            if (x0 - 2 <= x < x0 + self.geo["tray_w"] * CELL + 2
                    and top - 2 <= y <= rim + 1):
                return pan
        return None

    def settled(self):
        """Every beam carries something on both sides and weighs the same either side."""
        for s in range(self.n_scales):
            left, right = self.scale_sums(s)
            if not self.pans[2 * s] or not self.pans[2 * s + 1] or left != right:
                return False
        return True

    # -- mutation -----------------------------------------------------------

    def _repack(self, pan):
        items = [(self.blocks[i]["w"], self.blocks[i]["h"], self.blocks[i]["cells"])
                 for i in self.pans[pan]]
        spots = pack_tray(items, self.geo["tray_w"], self.geo["tray_h"])
        if spots is None:
            return False
        self.pan_pos[pan] = {i: spots[k] for k, i in enumerate(self.pans[pan])}
        return True

    def _arrest(self):
        """Any change to the load re-latches the beam: the last reading is now stale."""
        self.arrested = True
        self.frac = 0.0

    def place(self, i, pan):
        if self.blocks[i]["at"] >= 0:
            return False
        self.pans[pan].append(i)
        if not self._repack(pan):                  # the pan is physically full
            self.pans[pan].pop()
            self._repack(pan)
            return False
        self.blocks[i]["at"] = pan
        self.selected = None
        self._arrest()
        return True

    def take_back(self, i):
        pan = self.blocks[i]["at"]
        if pan < 0:
            return False
        self.pans[pan].remove(i)
        self.blocks[i]["at"] = -1
        self._repack(pan)
        self.selected = i
        self._arrest()
        return True

    def _handle_click(self, x, y):
        hit = self._block_at(x, y)
        if hit is not None:
            if self.blocks[hit]["at"] >= 0:
                self.take_back(hit)
            else:
                self.selected = None if self.selected == hit else hit
            return
        pan = self._tray_at(x, y)
        if pan is not None and self.selected is not None:
            self.place(self.selected, pan)

    def _release(self):
        """Unlatch: the beam swings to the true reading and the level is judged."""
        self.arrested = False
        self.frac = 0.0
        for s in range(self.n_scales):
            left, right = self.scale_sums(s)
            self.tilt[s] = 1 if left > right else (-1 if left < right else 0)
        if self.weigh_max:
            self.weigh_left -= 1
        self._pending_win = self.settled() and self.placed_count() == self.quota
        self._swing = SWING_FRAMES

    # -- engine entry point -------------------------------------------------

    def _resolve(self):
        if self._pending_win:
            self.next_level()
            self.complete_action()
            return
        if self.budget_left <= 0 or (self.weigh_max and self.weigh_left <= 0):
            self.budget_left = max(0, self.budget_left)
            self.weigh_left = max(0, self.weigh_left)
            self.lose()
        self.complete_action()

    def step(self) -> None:
        # A release animates: the beam swings over a few frames so the direction it goes
        # is read from motion as well as from colour. Bounded, so the browser never hangs.
        if self._swing > 0:
            self._swing -= 1
            self.frac = 1.0 - self._swing / SWING_FRAMES
            if self._swing == 0:
                self._resolve()
            return

        aid = self.action.id.value
        if aid == 6:
            self.budget_left -= CLICK_COST
            self._handle_click(int(self.action.data.get("x", 0)),
                               int(self.action.data.get("y", 0)))
        elif aid == 5:
            self.budget_left -= WEIGH_COST
            self._release()
            return                                 # animate; _resolve() finishes it

        self._resolve()
