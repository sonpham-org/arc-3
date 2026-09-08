# Author: Claude Opus 5
# Date: 2026-08-27 09:20 (loss condition reworked 2026-09-02)
# PURPOSE: kr01 "Carry" -- an ARC-AGI-3 environment built to measure ONE thing: whether an
#   agent carries a hidden mapping across a level boundary. Level 1 hands the player a free
#   test bench that reveals which coloured core belongs in which shaped socket. From level 2
#   the bench is gone, the mapping is unchanged, and a wrong insertion jams the socket.
#   There is NO budget and nothing counts down: the level is lost only by BOARD STATE. Every
#   wrong insert jams its socket for a few actions AND trips one of three latches on the
#   tray rail; a latch releases on its own after a longer timeout, draining visibly as it
#   goes. When the third latch trips, the tray seizes: a bar slams across the cores and the
#   level fails. A mistake is therefore a cost (a locked socket, a lit bay that drains) and
#   only a third mistake made while two latches are still live is an ending. Remembering
#   the mapping never trips anything; re-deriving it by guessing jams three of every four
#   inserts and seizes the tray in a handful of clicks.
#   Later levels EXTEND the mapping (a fifth pair, forced by elimination), RE-SKIN the
#   sockets (outline, then figure/ground inversion) without re-teaching, and COMPOSE it
#   (compound sockets consume two cores in a geometrically ordered sequence).
#   The tray REMEMBERS for the player: every pairing seen to fit is drawn permanently on its
#   core (the shape, filled with the colour) and carried across levels, so the puzzle is
#   "learn once, apply later" without anything living in the player's head.
#   Core-knowledge priors only: objectness, geometry/topology, agentness. No text, no
#   glyphs, no digits, no cultural conventions. Click is the only verb.
# SRP/DRY check: Pass -- self-contained environment. No catalogued game tests cross-level
#   knowledge retention, so there is nothing to reuse; shape rasterisation is parametric so
#   one function serves every size and style.
"""Carry -- learn the colour/shape mapping on the bench, then keep it.

Click a core in the tray to select it. Click a socket to push the selected core in. A core
only fits the shape it belongs to; a core that does not fit jams the socket for a while and
trips a latch on the tray rail, which drains away over a longer while. Three live latches
seize the tray: a bar slams across the cores and the level is lost. Level 1 has a free
bench: testing a core against a bench pad never jams anything and the pad keeps the colour
that fits it. After level 1 the bench is gone but the mapping is the same.

7 levels. No RNG. No budget. Lose only by tripping three latches at the same time.
"""

import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

# ---------------------------------------------------------------------------
# Palette (ARC-3 indices)
# ---------------------------------------------------------------------------

C_WHITE, C_LGRAY, C_GRAY, C_DGRAY, C_VDGRAY, C_BLACK = 0, 1, 2, 3, 4, 5
C_MAGENTA, C_LMAGENTA, C_RED, C_BLUE, C_LBLUE = 6, 7, 8, 9, 10
C_YELLOW, C_ORANGE, C_MAROON, C_GREEN, C_PURPLE = 11, 12, 13, 14, 15

# ---------------------------------------------------------------------------
# The hidden mapping. Five colours, five shapes, one bijection, constant for the whole
# game. This is the ONLY thing the player has to carry from level 1 to level 7; nothing on
# screen after level 1 discloses it, and every wrong guess jams a socket and trips a latch.
# ---------------------------------------------------------------------------

SQ, TR, DI, CR, RI = 0, 1, 2, 3, 4          # square, triangle, diamond, cross, ring

MAP = {
    C_BLUE: CR,
    C_YELLOW: RI,
    C_GREEN: TR,
    C_MAGENTA: SQ,
    C_PURPLE: DI,
}
INV_MAP = {v: k for k, v in MAP.items()}

STYLE_SOLID, STYLE_OUTLINE, STYLE_INVERT = 0, 1, 2

# ---------------------------------------------------------------------------
# Geometry. One lattice of 13x13 socket slots fills the field; a compound socket eats two
# adjacent slots (a 13x13 head and a 9x9 tail joined by a bar).
# ---------------------------------------------------------------------------

COLS = (2, 18, 34, 50)       # slot x, pitch 16, cell 13 -> 3px gutters
ROWS = (6, 22, 38)           # slot y, pitch 16
CELL = 13
TAIL = 9
TAIL_DX, TAIL_DY = 18, 2     # offset of a compound's tail cell from its head cell

TRAY_Y = 53
TRAY_X = (2, 15, 28, 41, 54)
CORE = 9

BENCH_Y0, BENCH_Y1 = 4, 31   # bench platform band (inclusive rows)
BENCH_PAD_Y = 11

# ---------------------------------------------------------------------------
# The loss condition, as board state and nothing else. A wrong insert does two things to
# the socket it landed on: the socket JAMS (its shape turns red and refuses cores for a few
# actions) and it trips a LATCH (an orange frame closes around the whole socket and stays
# for longer, after the shape has gone grey and accepts cores again). A second wrong insert
# on the same socket while its first latch is live adds a second frame just inside the
# first. When the third latch is live anywhere on the board the tray seizes: a bar slams
# across the cores over a few frames and the level is lost. There is no bar, no pip row and
# no counter: the only pressure display is the sockets themselves glowing, and the seizure.
#
# Why latches are counted per JAM and not per jammed SOCKET: with only sockets counted, a
# board with two open sockets can never seize, so any blind policy that survives the opening
# finishes for free by retrying the same two sockets; measured, that leak alone put a random
# clicker above 1/1000 on every level at any socket-jam length under 20. A latch per jam
# closes it: the third wrong guess is fatal wherever it lands, including twice on one socket.
# ---------------------------------------------------------------------------

SEIZE_JAMS = 3                               # live latches that seize the tray
LATCH_INK = C_ORANGE                         # latch frame; not a core colour, not the jam red
SEP_Y = 51                                   # thin rule between field and tray
BAR_H = 3                                    # lock bar thickness
SLAM_PATH = (51, 53, 55, 56)                 # lock bar top row on each frame of the slam

# ---------------------------------------------------------------------------
# Levels. Each escalation ADDS a rule and keeps every earlier one:
#   1 Bench    free discovery apparatus; four pairs. A wrong insert jams for 2 actions and
#              trips a 2-action latch, so both glows are SEEN here -- but at most `latch`
#              latches can ever be live at once (one reject per action), so latch=2 cannot
#              seize: the tutorial is impossible to fail.
#   2 Recall   bench gone; a wrong insert jams the socket for `jam` actions and trips a
#              latch for `latch` actions; three live latches seize the tray
#   3 Extend   a fifth colour and a fifth shape; the new pair is forced by elimination
#   4 Reskin   sockets are drawn as outlines instead of filled bodies
#   5 Invert   sockets are drawn as figure/ground inversions (the shape is a hole)
#   6 Compose  compound sockets take two cores, head shape first then tail shape
#   7 Gauntlet compound sockets in all three presentations at once
#
# Tuning rule, measured not guessed (numbers in the plan doc): a latch tripped at action t
# is still live at action T iff T - t <= latch - 1, so the tray seizes exactly when three
# rejects fall inside a (latch - 1)-action span. A carrying player never rejects and is
# untouched by either timeout. A blind clicker fits a socket 1 time in 4 (5 colours: 1 in
# 5) and so can only clear a 10-stage level by luck -- ten fits inside its first dozen-odd
# socket hits -- and the latch length decides how many SPACED rejects that streak may
# contain: about 2 + (level length / latch). At latch 30, twice a carrying player's level,
# that is three, and the luck floor is ~1e-4 on the 4-colour level and ~2e-5 on the
# 5-colour ones. Longer latches buy little more and turn "wait one out" into a fiction;
# the socket jam stays at the original 5-6 so that one mistake locks one socket only
# briefly. `latch` is the same on every non-tutorial level: the pressure is a rule the
# player learns once, not a dial that is turned up.
#
# socket spec: (col, row, shape, style)                  -> simple, one stage
#              (col, row, head_shape, style, tail_shape) -> compound, two stages
# ---------------------------------------------------------------------------

_S, _O, _I = STYLE_SOLID, STYLE_OUTLINE, STYLE_INVERT

LEVELS = [
    {
        "name": "Bench",
        "cores": (C_MAGENTA, C_BLUE, C_YELLOW, C_GREEN),
        "bench": (SQ, TR, CR, RI),
        "sockets": ((0, 2, RI, _S), (1, 2, CR, _S), (2, 2, SQ, _S), (3, 2, TR, _S)),
        "jam": 2, "latch": 2,
    },
    {
        "name": "Recall",
        "cores": (C_YELLOW, C_GREEN, C_MAGENTA, C_BLUE),
        "bench": (),
        "sockets": ((0, 0, RI, _S), (1, 0, CR, _S), (2, 0, SQ, _S), (3, 0, TR, _S),
                    (0, 1, CR, _S), (1, 1, RI, _S), (2, 1, TR, _S), (3, 1, SQ, _S),
                    (1, 2, RI, _S), (2, 2, CR, _S)),
        "jam": 5, "latch": 30,
    },
    {
        "name": "Extend",
        "cores": (C_GREEN, C_PURPLE, C_BLUE, C_MAGENTA, C_YELLOW),
        "bench": (),
        "sockets": ((0, 0, DI, _S), (1, 0, TR, _S), (2, 0, RI, _S), (3, 0, CR, _S),
                    (0, 1, SQ, _S), (1, 1, DI, _S), (2, 1, CR, _S), (3, 1, RI, _S),
                    (1, 2, SQ, _S), (2, 2, TR, _S)),
        "jam": 5, "latch": 30,
    },
    {
        "name": "Reskin",
        "cores": (C_PURPLE, C_MAGENTA, C_YELLOW, C_GREEN, C_BLUE),
        "bench": (),
        "sockets": ((0, 0, CR, _O), (1, 0, SQ, _O), (2, 0, DI, _O), (3, 0, TR, _O),
                    (0, 1, RI, _O), (1, 1, TR, _O), (2, 1, SQ, _O), (3, 1, DI, _O),
                    (0, 2, RI, _O), (3, 2, CR, _O)),
        "jam": 5, "latch": 30,
    },
    {
        "name": "Invert",
        "cores": (C_BLUE, C_MAGENTA, C_GREEN, C_YELLOW, C_PURPLE),
        "bench": (),
        "sockets": ((0, 0, TR, _I), (1, 0, RI, _I), (2, 0, CR, _I), (3, 0, DI, _I),
                    (0, 1, SQ, _I), (1, 1, CR, _I), (2, 1, DI, _I), (3, 1, TR, _I),
                    (0, 2, RI, _I), (2, 2, SQ, _I)),
        "jam": 5, "latch": 30,
    },
    {
        "name": "Compose",
        "cores": (C_YELLOW, C_BLUE, C_PURPLE, C_GREEN, C_MAGENTA),
        "bench": (),
        "sockets": ((0, 0, CR, _S, SQ), (2, 0, RI, _S, DI),
                    (0, 1, TR, _S, CR), (2, 1, DI, _S), (3, 1, TR, _S),
                    (1, 2, SQ, _S), (2, 2, RI, _S)),
        "jam": 5, "latch": 30,
    },
    {
        "name": "Gauntlet",
        "cores": (C_MAGENTA, C_PURPLE, C_GREEN, C_YELLOW, C_BLUE),
        "bench": (),
        "sockets": ((0, 0, SQ, _S, RI), (2, 0, DI, _O, CR),
                    (0, 1, RI, _I, TR), (2, 1, CR, _S, DI),
                    (1, 2, TR, _O), (2, 2, SQ, _I)),
        "jam": 6, "latch": 30,
    },
]


# ---------------------------------------------------------------------------
# Parametric shape rasteriser. One definition per shape in normalised coordinates, so the
# same shape reads identically at the 13px head size and the 9px tail size. Cached because
# render_interface runs on every frame of every action.
# ---------------------------------------------------------------------------

_MASKS: dict = {}


def shape_mask(shape: int, size: int) -> np.ndarray:
    """Boolean size x size mask for `shape`."""
    key = (shape, size, 0)
    cached = _MASKS.get(key)
    if cached is not None:
        return cached
    c = (size - 1) / 2.0
    mask = np.zeros((size, size), dtype=bool)
    for yy in range(size):
        v = (yy - c) / c
        av = abs(v)
        for xx in range(size):
            u = (xx - c) / c
            au = abs(u)
            if shape == SQ:
                on = max(au, av) <= 0.78
            elif shape == DI:
                on = au + av <= 0.92
            elif shape == CR:
                on = (au <= 0.34 and av <= 0.85) or (av <= 0.34 and au <= 0.85)
            elif shape == RI:
                on = 0.42 <= max(au, av) <= 0.85
            else:                                        # TR, apex up
                on = -0.85 <= v <= 0.85 and au <= 0.95 * (v + 0.85) / 1.7
            mask[yy, xx] = on
    _MASKS[key] = mask
    return mask


def shape_outline(shape: int, size: int) -> np.ndarray:
    """Boundary cells of `shape` -- the mask minus its 4-connected interior."""
    key = (shape, size, 1)
    cached = _MASKS.get(key)
    if cached is not None:
        return cached
    src = shape_mask(shape, size)
    out = np.zeros_like(src)
    for yy in range(size):
        for xx in range(size):
            if not src[yy, xx]:
                continue
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                ny, nx = yy + dy, xx + dx
                if not (0 <= ny < size and 0 <= nx < size) or not src[ny, nx]:
                    out[yy, xx] = True
                    break
    _MASKS[key] = out
    return out


def _inside(px: int, py: int, x: int, y: int, w: int, h: int) -> bool:
    return x <= px < x + w and y <= py < y + h


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

class Kr01Display(RenderableUserDisplay):
    def __init__(self, game):
        self.game = game

    # -- primitives ---------------------------------------------------------

    @staticmethod
    def _blit(frame, x, y, mask, color):
        h, w = mask.shape
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(64, x + w), min(64, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        sub = mask[y0 - y:y1 - y, x0 - x:x1 - x]
        region = frame[y0:y1, x0:x1]
        region[sub] = color

    @staticmethod
    def _rect(frame, x, y, w, h, color):
        frame[max(0, y):min(64, y + h), max(0, x):min(64, x + w)] = color

    @staticmethod
    def _frame_box(frame, x, y, w, h, color):
        Kr01Display._rect(frame, x, y, w, 1, color)
        Kr01Display._rect(frame, x, y + h - 1, w, 1, color)
        Kr01Display._rect(frame, x, y, 1, h, color)
        Kr01Display._rect(frame, x + w - 1, y, 1, h, color)

    # -- socket stages ------------------------------------------------------

    def _draw_stage(self, frame, x, y, size, shape, style, state, color):
        """state: 'filled' | 'active' | 'jam' | 'ghost'."""
        if state == "filled":
            self._blit(frame, x, y, shape_mask(shape, size), color)
            self._frame_box(frame, x - 1, y - 1, size + 2, size + 2, C_WHITE)
            return
        if state == "ghost":
            self._blit(frame, x, y, shape_outline(shape, size), C_VDGRAY)
            return
        jammed = state == "jam"
        if style == STYLE_SOLID:
            self._blit(frame, x, y, shape_mask(shape, size), C_RED if jammed else C_GRAY)
        elif style == STYLE_OUTLINE:
            self._frame_box(frame, x, y, size, size, C_VDGRAY)
            self._blit(frame, x, y, shape_outline(shape, size),
                       C_RED if jammed else C_LGRAY)
        else:                                            # STYLE_INVERT
            self._rect(frame, x, y, size, size, C_RED if jammed else C_DGRAY)
            self._blit(frame, x, y, shape_mask(shape, size), C_BLACK)

    # -- whole frame --------------------------------------------------------

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        # Palette: the corpus is 60.3% greyscale and this game was 64% pure black. A maroon
        # ground is near-absent from the catalogue (0.0% of official pixels) and leaves the
        # five core colours -- magenta, blue, yellow, green, purple -- fully distinguishable,
        # which matters here because the whole game is a colour/shape mapping.
        g = self.game
        frame[:, :] = C_MAROON

        # Bench platform (level 1 only): a raised band that visually separates the free
        # apparatus from the sockets that actually count.
        if g.bench:
            # The bench must not be mistakable for the sockets: playtesting showed two rows
            # of same-grey shapes read as one thing. So the bench is a lit SURFACE carrying
            # solid light shapes, while sockets below are dark holes cut into plates --
            # different objects, not different shades of the same object.
            band_h = BENCH_Y1 - BENCH_Y0 + 1
            self._rect(frame, 0, BENCH_Y0, 64, band_h, C_DGRAY)
            # bright rails top and bottom mark it as apparatus, and only the bench has them
            self._rect(frame, 0, BENCH_Y0, 64, 1, C_LBLUE)
            self._rect(frame, 0, BENCH_Y1, 64, 1, C_LBLUE)
            for i, pad in enumerate(g.bench):
                x, y = pad["x"], pad["y"]
                self._rect(frame, x, y, CELL, CELL, C_DGRAY)
                if pad["found"] is not None:
                    self._blit(frame, x, y, shape_mask(pad["shape"], CELL), pad["found"])
                    self._frame_box(frame, x - 1, y - 1, CELL + 2, CELL + 2, C_WHITE)
                else:
                    # red, not maroon: maroon is now the ground, so a maroon reject flash
                    # would be invisible -- and this flash is the bench's only feedback
                    ink = C_RED if g.bench_flash == i else C_LGRAY
                    self._blit(frame, x, y, shape_mask(pad["shape"], CELL), ink)

        # Sockets.
        for s in g.sockets:
            stage = s["stage"]
            if len(s["cells"]) > 1:                      # compound connector bar
                hx, hy, hs = s["cells"][0]
                self._rect(frame, hx + hs, hy + 5, TAIL_DX - hs, 3,
                           C_LGRAY if stage >= 1 else C_VDGRAY)
            for i, (cx, cy, cs) in enumerate(s["cells"]):
                if i < stage:
                    state, color = "filled", s["fills"][i]
                elif i == stage:
                    state, color = ("jam" if s["jam"] > 0 else "active"), 0
                else:
                    state, color = "ghost", 0
                self._draw_stage(frame, cx, cy, cs, s["shapes"][i], s["style"], state, color)
            # Latch glow: one orange frame around the whole socket per live latch, the
            # second one just inside the first. Every 13px and 9px cell keeps its outermost
            # pixel ring free of shape, so the inner frame never touches the shape. The
            # frames outlive the red jam and survive the socket being filled, because the
            # latch is the tray's consequence, not the socket's.
            n = len(s["latch"])
            if n >= 1:
                self._frame_box(frame, s["x"] - 1, s["y"] - 1,
                                s["hit_w"] + 2, s["hit_h"] + 2, LATCH_INK)
            if n >= 2:
                self._frame_box(frame, s["x"], s["y"], s["hit_w"], s["hit_h"], LATCH_INK)

        # Tray. The tray remembers for the player: a core whose pairing has been DISCOVERED
        # (a fit anywhere, or a bench hit) is drawn as its shape filled with its colour on a
        # dark plate, with the same 9px rasteriser the socket tails use, and stays that way
        # across levels; an undiscovered core is a plain block. Nothing is ever shown that
        # the player has not seen happen, so the legend cannot be read by a blind policy.
        # A core whose every remaining target is already filled turns hollow (outline only):
        # colour recomputed from what the object currently affords, not from level data.
        need = g.colors_still_needed()
        for i, core in enumerate(g.cores):
            x, y, col = core["x"], core["y"], core["color"]
            live = col in need
            shape = g.known.get(col)
            if shape is None:
                if live:
                    self._rect(frame, x + 1, y + 1, CORE - 2, CORE - 2, col)
                else:
                    self._frame_box(frame, x + 1, y + 1, CORE - 2, CORE - 2, col)
            else:
                self._rect(frame, x, y, CORE, CORE, C_VDGRAY)
                mask = shape_mask(shape, CORE) if live else shape_outline(shape, CORE)
                self._blit(frame, x, y, mask, col)
            if g.selected == i and not g.seized():
                self._frame_box(frame, x - 1, y - 1, CORE + 2, CORE + 2, C_WHITE)

        # Rule between field and tray.
        self._rect(frame, 0, SEP_Y, 64, 1, C_RED if g.seized() else C_VDGRAY)

        # Seizure: the lock bar leaves the rule and slams down across the cores, one step per
        # frame, and stays there. Drawn last so it crosses everything in the tray. A second
        # red line closes the bottom of the tray once the bar has landed, so the final frame
        # reads as a caged tray even to a viewer who never saw the slam.
        if g.seized():
            top = SLAM_PATH[min(g.seize_frame, len(SLAM_PATH) - 1)]
            self._rect(frame, 0, top, 64, BAR_H, C_RED)
            if g.seize_frame >= len(SLAM_PATH) - 1:
                self._rect(frame, 0, 63, 64, 1, C_RED)

        # A click that changed nothing still has to be legible, or the agent cannot tell a
        # miss from a no-op. Only misses are marked; every other click visibly alters the
        # object it landed on.
        if g.click_mark is not None and g.last_result == "miss":
            mx, my = g.click_mark
            self._frame_box(frame, mx - 1, my - 1, 3, 3, C_WHITE)
        return frame


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class Kr01(ARCBaseGame):
    def __init__(self):
        self.display = Kr01Display(self)

        # on_set_level() is called from inside super().__init__(), so every attribute it
        # touches has to exist first.
        self.sockets: list = []
        self.cores: list = []
        self.bench: list = []
        self.bench_flash = -1
        self.selected = None
        self.jam_turns = 0
        self.latch_len = 1
        self.seize_frame = None
        self.click_mark = None
        self.last_result = ""
        # {colour: shape} the player has seen fit. Survives level changes and level resets;
        # a full reset (a new game) empties it. This is the whole cross-level state.
        self.known: dict = {}

        levels = [Level(sprites=[], grid_size=(64, 64), data=ldef, name=ldef["name"])
                  for ldef in LEVELS]

        super().__init__(
            "kr",
            levels,
            Camera(0, 0, 64, 64, C_MAROON, C_MAROON, [self.display]),
            False,
            len(levels),
            [6],                                          # click only
        )

    # -- level setup --------------------------------------------------------

    def on_set_level(self, level: Level) -> None:
        ldef = LEVELS[self.level_index]

        # The engine sets _full_reset only for a new game (RESET at action 0 or after WIN);
        # a level reset and next_level() leave it False, and the tray keeps its memory.
        if getattr(self, "_full_reset", True):
            self.known = {}

        self.sockets = []
        for spec in ldef["sockets"]:
            col, row, shape, style = spec[0], spec[1], spec[2], spec[3]
            x, y = COLS[col], ROWS[row]
            cells = [(x, y, CELL)]
            shapes = [shape]
            hit_w = CELL
            if len(spec) == 5:
                cells.append((x + TAIL_DX, y + TAIL_DY, TAIL))
                shapes.append(spec[4])
                hit_w = COLS[col + 1] + CELL - x
            self.sockets.append({
                "x": x, "y": y, "hit_w": hit_w, "hit_h": CELL,
                "cells": cells, "shapes": shapes, "style": style,
                "stage": 0, "fills": [], "jam": 0, "latch": [],
            })

        self.cores = [{"x": TRAY_X[i], "y": TRAY_Y, "color": c}
                      for i, c in enumerate(ldef["cores"])]

        self.bench = [{"x": COLS[i], "y": BENCH_PAD_Y, "shape": sh, "found": None}
                      for i, sh in enumerate(ldef["bench"])]
        self.bench_flash = -1

        # A core is pre-selected so the very first click on any socket does something.
        self.selected = 0 if self.cores else None
        self.jam_turns = ldef["jam"]
        self.latch_len = ldef["latch"]
        self.seize_frame = None
        self.click_mark = None
        self.last_result = ""

    # -- queries ------------------------------------------------------------

    def stage_shape(self, socket):
        """Shape the socket currently wants, or None when it is complete."""
        if socket["stage"] >= len(socket["shapes"]):
            return None
        return socket["shapes"][socket["stage"]]

    def colors_still_needed(self):
        """Colours some unfinished stage anywhere on the board is waiting for."""
        need = set()
        for s in self.sockets:
            for sh in s["shapes"][s["stage"]:]:
                need.add(INV_MAP[sh])
        return need

    def solved(self):
        return all(s["stage"] >= len(s["shapes"]) for s in self.sockets)

    def jam_count(self):
        """Sockets that refuse a core right now."""
        return sum(1 for s in self.sockets if s["jam"] > 0)

    def latch_count(self):
        """Live latches on the board -- the whole loss condition, and what the frames show."""
        return sum(len(s["latch"]) for s in self.sockets)

    def seized(self):
        return self.seize_frame is not None

    # -- click resolution ---------------------------------------------------

    def _click_core(self, index):
        if self.selected == index:
            self.last_result = "miss"
            return
        self.selected = index
        self.last_result = "select"

    def _click_bench(self, index):
        pad = self.bench[index]
        if pad["found"] is not None or self.selected is None:
            self.last_result = "miss"
            return
        color = self.cores[self.selected]["color"]
        if MAP[color] == pad["shape"]:
            pad["found"] = color
            self.known[color] = pad["shape"]
            self.last_result = "bench_hit"
        else:
            self.bench_flash = index
            self.last_result = "bench_miss"

    def _click_socket(self, index):
        s = self.sockets[index]
        want = self.stage_shape(s)
        if want is None or s["jam"] > 0 or self.selected is None:
            self.last_result = "miss"
            return
        color = self.cores[self.selected]["color"]
        if MAP[color] == want:
            s["fills"].append(color)
            s["stage"] += 1
            self.known[color] = want
            self.last_result = "fit"
        else:
            # A rejected core tells you nothing except that this pairing is wrong. It locks
            # the socket for a few actions and trips a latch on the tray for longer. Three
            # live latches seize the tray, which is what makes re-deriving the mapping by
            # trial more dangerous than remembering it.
            s["jam"] = self.jam_turns
            s["latch"].append(self.latch_len)
            self.last_result = "reject"

    def _handle_click(self, cx, cy):
        self.click_mark = (cx, cy)
        for i, core in enumerate(self.cores):
            if _inside(cx, cy, core["x"], core["y"], CORE, CORE):
                self._click_core(i)
                return
        for i, pad in enumerate(self.bench):
            if _inside(cx, cy, pad["x"], pad["y"], CELL, CELL):
                self._click_bench(i)
                return
        for i, s in enumerate(self.sockets):
            if _inside(cx, cy, s["x"], s["y"], s["hit_w"], s["hit_h"]):
                self._click_socket(i)
                return
        self.last_result = "miss"

    # -- engine entry point -------------------------------------------------

    def step(self) -> None:
        if self.seized():
            # Mid-slam. The click that seized the tray has already been resolved; these
            # extra frames only move the bar, so the action is not read again. Bounded by
            # len(SLAM_PATH) frames.
            self.seize_frame += 1
            if self.seize_frame >= len(SLAM_PATH) - 1:
                self.complete_action()
            return

        aid = self.action.id.value

        if aid == 6:
            self.bench_flash = -1
            for s in self.sockets:
                if s["jam"] > 0:
                    s["jam"] -= 1
                s["latch"] = [t - 1 for t in s["latch"] if t - 1 > 0]
            data = self.action.data or {}
            cx = int(data.get("x", -1))
            cy = int(data.get("y", -1))
            if 0 <= cx < 64 and 0 <= cy < 64:
                self._handle_click(cx, cy)
            else:
                self.click_mark = None
                self.last_result = "miss"

        if self.solved():
            self.next_level()
            self.complete_action()
            return

        if self.latch_count() >= SEIZE_JAMS:
            # Third live latch: the tray seizes. lose() now, and withhold complete_action()
            # so the engine calls step() again for the slam frames.
            self.seize_frame = 0
            self.lose()
            return

        self.complete_action()
