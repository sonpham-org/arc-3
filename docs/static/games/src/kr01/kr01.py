# Author: Claude Opus 5
# Date: 2026-08-27 09:20
# PURPOSE: kr01 "Carry" -- an ARC-AGI-3 environment built to measure ONE thing: whether an
#   agent carries a hidden mapping across a level boundary. Level 1 hands the player a free
#   test bench that reveals which coloured core belongs in which shaped socket at zero
#   budget cost. From level 2 the bench is gone, the mapping is unchanged, and a wrong
#   insertion costs a large slice of budget and jams the socket. Remembering wins in a
#   handful of clicks; re-deriving the mapping costs more budget than the level grants.
#   Later levels EXTEND the mapping (a fifth pair, forced by elimination), RE-SKIN the
#   sockets (outline, then figure/ground inversion) without re-teaching, and COMPOSE it
#   (compound sockets consume two cores in a geometrically ordered sequence).
#   Core-knowledge priors only: objectness, geometry/topology, agentness. No text, no
#   glyphs, no digits, no cultural conventions. Click is the only verb.
# SRP/DRY check: Pass -- self-contained environment. No catalogued game tests cross-level
#   knowledge retention, so there is nothing to reuse; shape rasterisation is parametric so
#   one function serves every size and style.
"""Carry -- learn the colour/shape mapping on the bench, then keep it.

Click a core in the tray to select it. Click a socket to push the selected core in. A core
only fits the shape it belongs to. Level 1 has a free bench: testing a core against a bench
pad costs nothing and the pad keeps the colour that fits it. After level 1 the bench is
gone but the mapping is the same.

7 levels. No RNG. Lose by running the budget to zero.
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
# screen after level 1 discloses it, and every wrong guess is paid for in budget.
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

HUD_Y0, HUD_Y1 = 0, 3        # budget bar occupies rows 0..2
SEP_Y = 51                   # thin rule between field and tray

BENCH_Y0, BENCH_Y1 = 4, 31   # bench platform band (inclusive rows)
BENCH_PAD_Y = 11
BENCH_FREE = 60              # free bench tests; afterwards a test costs one budget unit

SELECT_COST = 1
INSERT_COST = 1
MISS_COST = 1

# ---------------------------------------------------------------------------
# Levels. Each escalation ADDS a rule and keeps every earlier one:
#   1 Bench    free discovery apparatus; four pairs
#   2 Recall   bench gone; a wrong insert costs ~10 budget and jams the socket for 5 turns
#
# Budget tuning rule, measured not guessed: what defeats a memoryless re-deriving agent is
# TOLERANCE -- how many wrong inserts fit in the spare budget -- and spare budget also pays
# for its extra selection churn. Every level therefore keeps
#     carrying-policy cost + 1.0..1.3 x wrong_cost  <=  budget  <  cost + 2 x wrong_cost
# which leaves an agent that remembers ~6-8 free misclicks but lets one wrong insert stand,
# never two. Raising the spare to 1.7x wrong_cost triples the re-deriving agent's win rate.
#   3 Extend   a fifth colour and a fifth shape; the new pair is forced by elimination
#   4 Reskin   sockets are drawn as outlines instead of filled bodies
#   5 Invert   sockets are drawn as figure/ground inversions (the shape is a hole)
#   6 Compose  compound sockets take two cores, head shape first then tail shape
#   7 Gauntlet compound sockets in all three presentations at once
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
        "wrong": 2, "jam": 0, "budget": 44,
    },
    {
        "name": "Recall",
        "cores": (C_YELLOW, C_GREEN, C_MAGENTA, C_BLUE),
        "bench": (),
        "sockets": ((0, 0, RI, _S), (1, 0, CR, _S), (2, 0, SQ, _S), (3, 0, TR, _S),
                    (0, 1, CR, _S), (1, 1, RI, _S), (2, 1, TR, _S), (3, 1, SQ, _S),
                    (1, 2, RI, _S), (2, 2, CR, _S)),
        "wrong": 10, "jam": 5, "budget": 26,
    },
    {
        "name": "Extend",
        "cores": (C_GREEN, C_PURPLE, C_BLUE, C_MAGENTA, C_YELLOW),
        "bench": (),
        "sockets": ((0, 0, DI, _S), (1, 0, TR, _S), (2, 0, RI, _S), (3, 0, CR, _S),
                    (0, 1, SQ, _S), (1, 1, DI, _S), (2, 1, CR, _S), (3, 1, RI, _S),
                    (1, 2, SQ, _S), (2, 2, TR, _S)),
        "wrong": 11, "jam": 5, "budget": 26,
    },
    {
        "name": "Reskin",
        "cores": (C_PURPLE, C_MAGENTA, C_YELLOW, C_GREEN, C_BLUE),
        "bench": (),
        "sockets": ((0, 0, CR, _O), (1, 0, SQ, _O), (2, 0, DI, _O), (3, 0, TR, _O),
                    (0, 1, RI, _O), (1, 1, TR, _O), (2, 1, SQ, _O), (3, 1, DI, _O),
                    (0, 2, RI, _O), (3, 2, CR, _O)),
        "wrong": 11, "jam": 5, "budget": 26,
    },
    {
        "name": "Invert",
        "cores": (C_BLUE, C_MAGENTA, C_GREEN, C_YELLOW, C_PURPLE),
        "bench": (),
        "sockets": ((0, 0, TR, _I), (1, 0, RI, _I), (2, 0, CR, _I), (3, 0, DI, _I),
                    (0, 1, SQ, _I), (1, 1, CR, _I), (2, 1, DI, _I), (3, 1, TR, _I),
                    (0, 2, RI, _I), (2, 2, SQ, _I)),
        "wrong": 11, "jam": 5, "budget": 26,
    },
    {
        "name": "Compose",
        "cores": (C_YELLOW, C_BLUE, C_PURPLE, C_GREEN, C_MAGENTA),
        "bench": (),
        "sockets": ((0, 0, CR, _S, SQ), (2, 0, RI, _S, DI),
                    (0, 1, TR, _S, CR), (2, 1, DI, _S), (3, 1, TR, _S),
                    (1, 2, SQ, _S), (2, 2, RI, _S)),
        "wrong": 12, "jam": 5, "budget": 27,
    },
    {
        "name": "Gauntlet",
        "cores": (C_MAGENTA, C_PURPLE, C_GREEN, C_YELLOW, C_BLUE),
        "bench": (),
        "sockets": ((0, 0, SQ, _S, RI), (2, 0, DI, _O, CR),
                    (0, 1, RI, _I, TR), (2, 1, CR, _S, DI),
                    (1, 2, TR, _O), (2, 2, SQ, _I)),
        "wrong": 13, "jam": 6, "budget": 28,
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
            self._blit(frame, x, y, shape_mask(shape, size), C_MAROON if jammed else C_GRAY)
        elif style == STYLE_OUTLINE:
            self._frame_box(frame, x, y, size, size, C_VDGRAY)
            self._blit(frame, x, y, shape_outline(shape, size),
                       C_MAROON if jammed else C_LGRAY)
        else:                                            # STYLE_INVERT
            self._rect(frame, x, y, size, size, C_MAROON if jammed else C_DGRAY)
            self._blit(frame, x, y, shape_mask(shape, size), C_BLACK)

    # -- whole frame --------------------------------------------------------

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game
        frame[:, :] = C_BLACK

        # Bench platform (level 1 only): a raised band that visually separates the free
        # apparatus from the sockets that actually count.
        if g.bench:
            # The bench must not be mistakable for the sockets: playtesting showed two rows
            # of same-grey shapes read as one thing. So the bench is a lit SURFACE carrying
            # solid light shapes, while sockets below are dark holes cut into plates --
            # different objects, not different shades of the same object.
            band_h = BENCH_Y1 - BENCH_Y0 + 1
            live = g.bench_uses < BENCH_FREE
            self._rect(frame, 0, BENCH_Y0, 64, band_h, C_DGRAY if live else C_BLACK)
            # bright rails top and bottom mark it as apparatus, and only the bench has them
            rail = C_LBLUE if live else C_VDGRAY
            self._rect(frame, 0, BENCH_Y0, 64, 1, rail)
            self._rect(frame, 0, BENCH_Y1, 64, 1, rail)
            for i, pad in enumerate(g.bench):
                x, y = pad["x"], pad["y"]
                self._rect(frame, x, y, CELL, CELL, C_DGRAY)
                if pad["found"] is not None:
                    self._blit(frame, x, y, shape_mask(pad["shape"], CELL), pad["found"])
                    self._frame_box(frame, x - 1, y - 1, CELL + 2, CELL + 2, C_WHITE)
                else:
                    ink = C_MAROON if g.bench_flash == i else C_LGRAY
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

        # Tray. A core whose every remaining target is already filled turns hollow: colour
        # recomputed from what the object currently affords, not from level data.
        need = g.colors_still_needed()
        for i, core in enumerate(g.cores):
            x, y = core["x"], core["y"]
            if core["color"] in need:
                self._rect(frame, x + 1, y + 1, CORE - 2, CORE - 2, core["color"])
            else:
                self._frame_box(frame, x + 1, y + 1, CORE - 2, CORE - 2, core["color"])
            if g.selected == i:
                self._frame_box(frame, x - 1, y - 1, CORE + 2, CORE + 2, C_WHITE)

        # Rule between field and tray.
        self._rect(frame, 0, SEP_Y, 64, 1, C_VDGRAY)

        # Budget bar -- a bar, never a number. Recoloured by how much is left.
        span = 61
        left = max(0, g.budget_left)
        filled = 0 if g.budget_max <= 0 else int(round(span * left / g.budget_max))
        self._rect(frame, 1, HUD_Y0, span, HUD_Y1, C_DGRAY)
        if filled > 0:
            if left * 2 > g.budget_max:
                bar = C_GREEN
            elif left * 4 > g.budget_max:
                bar = C_ORANGE
            else:
                bar = C_RED
            self._rect(frame, 1, HUD_Y0, filled, HUD_Y1, bar)

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
        self.bench_uses = 0
        self.bench_flash = -1
        self.selected = None
        self.wrong_cost = 0
        self.jam_turns = 0
        self.budget_max = 0
        self.budget_left = 0
        self.click_mark = None
        self.last_result = ""

        levels = [Level(sprites=[], grid_size=(64, 64), data=ldef, name=ldef["name"])
                  for ldef in LEVELS]

        super().__init__(
            "kr",
            levels,
            Camera(0, 0, 64, 64, C_BLACK, C_BLACK, [self.display]),
            False,
            len(levels),
            [6],                                          # click only
        )

    # -- level setup --------------------------------------------------------

    def on_set_level(self, level: Level) -> None:
        ldef = LEVELS[self.level_index]

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
                "stage": 0, "fills": [], "jam": 0,
            })

        self.cores = [{"x": TRAY_X[i], "y": TRAY_Y, "color": c}
                      for i, c in enumerate(ldef["cores"])]

        self.bench = [{"x": COLS[i], "y": BENCH_PAD_Y, "shape": sh, "found": None}
                      for i, sh in enumerate(ldef["bench"])]
        self.bench_uses = 0
        self.bench_flash = -1

        # A core is pre-selected so the very first click on any socket does something.
        self.selected = 0 if self.cores else None
        self.wrong_cost = ldef["wrong"]
        self.jam_turns = ldef["jam"]
        self.budget_max = self.budget_left = ldef["budget"]
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

    # -- click resolution ---------------------------------------------------

    def _click_core(self, index):
        if self.selected == index:
            self.budget_left -= MISS_COST
            self.last_result = "miss"
            return
        self.selected = index
        self.budget_left -= SELECT_COST
        self.last_result = "select"

    def _click_bench(self, index):
        pad = self.bench[index]
        free = self.bench_uses < BENCH_FREE
        self.bench_uses += 1
        if not free:
            self.budget_left -= MISS_COST
        if pad["found"] is not None or self.selected is None:
            self.last_result = "miss"
            return
        color = self.cores[self.selected]["color"]
        if MAP[color] == pad["shape"]:
            pad["found"] = color
            self.last_result = "bench_hit"
        else:
            self.bench_flash = index
            self.last_result = "bench_miss"

    def _click_socket(self, index):
        s = self.sockets[index]
        want = self.stage_shape(s)
        if want is None or s["jam"] > 0 or self.selected is None:
            self.budget_left -= MISS_COST
            self.last_result = "miss"
            return
        color = self.cores[self.selected]["color"]
        if MAP[color] == want:
            s["fills"].append(color)
            s["stage"] += 1
            self.budget_left -= INSERT_COST
            self.last_result = "fit"
        else:
            # A rejected core tells you nothing except that this pairing is wrong, and it
            # costs several turns of budget plus the socket for several turns. That is what
            # makes re-deriving the mapping more expensive than remembering it.
            self.budget_left -= self.wrong_cost
            s["jam"] = self.jam_turns
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
        self.budget_left -= MISS_COST
        self.last_result = "miss"

    # -- engine entry point -------------------------------------------------

    def step(self) -> None:
        aid = self.action.id.value

        if aid == 6:
            self.bench_flash = -1
            for s in self.sockets:
                if s["jam"] > 0:
                    s["jam"] -= 1
            data = self.action.data or {}
            cx = int(data.get("x", -1))
            cy = int(data.get("y", -1))
            if 0 <= cx < 64 and 0 <= cy < 64:
                self._handle_click(cx, cy)
            else:
                self.budget_left -= MISS_COST
                self.click_mark = None
                self.last_result = "miss"

        if self.solved():
            self.next_level()
            self.complete_action()
            return

        if self.budget_left <= 0:
            self.budget_left = max(0, self.budget_left)
            self.lose()

        self.complete_action()
