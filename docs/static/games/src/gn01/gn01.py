# Author: Claude Opus 5
# Date: 2026-08-27 14:20
# PURPOSE: gn01 "Genus" -- an ARC-AGI-3 environment built on a single topological invariant:
#   how many enclosed empty regions (holes) an object has. Blobs must be carried into the
#   gate that has the same number of holes. Colour, silhouette and size are progressively
#   stripped away as cues until hole count is the only signal left, then occlusion (lids)
#   and near-closures (a 1px channel means the cavity is NOT a hole) are layered on top.
#   Deliberately NOT nesting depth -- official game tu93 already encodes counting that way.
#   Core-knowledge priors only: objectness + geometry/topology. No text, no glyphs, no
#   numbers rendered anywhere; counts are always shown as repeated shapes.
# SRP/DRY check: Pass -- self-contained environment. No other catalogued game uses
#   topological genus as its rule, so there is nothing to reuse.
"""Genus -- sort each blob into the gate with the same number of holes.

Click a blob to pick it up (a frame appears round its cell), then click a gate to drop it
in. A correct gate accepts and the blob is gone; a wrong gate rejects, costs a life and
hands the blob back. Lids can be clicked away to reveal what they cover. Every click costs
budget; dropping costs more than picking up, so guessing is expensive.

7 levels. No RNG. Lose by running out of lives or budget.
"""

import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

# ---------------------------------------------------------------------------
# Colours (ARC-3 palette indices).
#
# Palette policy: the catalogued corpus is 60% greyscale, so this game is built on the
# under-used vivid end. The field is deep MAROON, never black. Grey/black appear only as
# structure -- the budget-bar track, the rule line under the field, the 1px seam that marks
# a lid as a separate object lying on top. Every meaning-carrying object is vivid.
#
# A hole is drawn in the field colour, because that is what a hole IS: background enclosed
# by body. That also makes the near-closed cavities of level 5 honest -- the channel is
# simply background reaching in from outside.
# ---------------------------------------------------------------------------

C_WHITE, C_LGRAY, C_GRAY, C_DGRAY, C_VDGRAY, C_BLACK = 0, 1, 2, 3, 4, 5
C_MAGENTA, C_LMAGENTA, C_RED, C_BLUE, C_LBLUE = 6, 7, 8, 9, 10
C_YELLOW, C_ORANGE, C_MAROON, C_GREEN, C_PURPLE = 11, 12, 13, 14, 15

C_FIELD = C_MAROON        # background wash and the colour of every void
C_GATE = C_ORANGE         # receptacles
C_GATE_ARMED = C_LBLUE    # gate rim while a blob is held -- affordance, recomputed each step
C_ACCEPT = C_LBLUE        # gate flashes bright on accept
C_REJECT = C_MAROON       # gate goes dark (reads as "shut") on reject
C_LID = C_MAGENTA         # occluders
C_SEAM = C_BLACK          # 1px structural seam round a lid
C_HOLD = C_GREEN          # frame round the cell of the held blob
C_RULE = C_VDGRAY         # structural rule line between field and gates
C_BAR_OK, C_BAR_LOW = C_YELLOW, C_MAGENTA
C_PIP_ON, C_PIP_OFF = C_ORANGE, C_VDGRAY

# The four body colours. On level 1 they agree with hole count; from level 2 they are
# scrambled, so colour becomes a decoy. Purple is the darkest of the four, so no lid is
# ever placed on a purple blob (lid magenta on purple body would be a low-contrast pair).
BODY = (C_YELLOW, C_LMAGENTA, C_LBLUE, C_PURPLE)

# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

GRID = 64

BAR_Y, BAR_X0, BAR_X1 = 1, 1, 62      # budget bar, 2 rows tall
PIP_Y, PIP_X0, PIP_STEP = 4, 1, 5     # life pips, 3x3 each

CELL_W, CELL_H = 20, 18               # a specimen cell: the whole rect is clickable
CELL_X = (1, 22, 43)
CELL_Y = (8, 27)
BLOB_OX, BLOB_OY = 2, 1               # 15x15 blob art inset inside its cell

RULE_Y = 46
GATE_W, GATE_H = 15, 14
GATE_X = (0, 16, 32, 48)
GATE_Y = 47

BLOB = 15                             # blob art is a 15x15 grid

SELECT_COST = 1
DEPOSIT_COST = 3                      # the test costs more than the setup, so brute force
LID_COST = 2                          # cannot simply try every gate on every blob
MISS_COST = 1
ANIM_FRAMES = 3

# ---------------------------------------------------------------------------
# Blob construction
#
# Three silhouettes. All of them are solid across rows 3..11 and columns 0..14, which is
# what makes every hole slot and every escape channel valid on every silhouette -- so a
# hole in the same place looks the same whatever the outline, and from level 3 on the
# outline is identical anyway ("cross" is the canonical one).
#
# The canonical shape used to be "round". It was changed after rendering frames to PNG and
# looking at them: a disc with two holes reads unmistakably as a FACE, and a real-world
# picture prior is exactly what the benchmark bans -- their own study found models chasing
# the wrong goal because an environment reminded them of something familiar.
# ---------------------------------------------------------------------------

SILHOUETTES = {
    "round": [
        "....#######....",
        "..###########..",
        ".#############.",
        "###############",
        "###############",
        "###############",
        "###############",
        "###############",
        "###############",
        "###############",
        "###############",
        ".#############.",
        "..###########..",
        "....#######....",
        ".....#####.....",
    ],
    "block": [
        "..###########..",
        ".#############.",
        "###############",
        "###############",
        "###############",
        "###############",
        "###############",
        "###############",
        "###############",
        "###############",
        "###############",
        "###############",
        "###############",
        ".#############.",
        "..###########..",
    ],
    "cross": [
        "...#########...",
        "...#########...",
        "...#########...",
        "###############",
        "###############",
        "###############",
        "###############",
        "###############",
        "###############",
        "###############",
        "###############",
        "###############",
        "...#########...",
        "...#########...",
        "...#########...",
    ],
}

# Four cavity slots, each a 3x3 square. Big enough that a hole is never ambiguous at 64x64.
HOLE_XY = {"tl": (3, 4), "tr": (9, 4), "bl": (3, 8), "br": (9, 8)}

# A "gap" carves the same cavity plus a 1px channel out to the nearest edge, on the
# cavity's middle row. The cavity then touches the outside and is NOT a hole. Visually the
# difference is a 3px wall present or absent -- unmistakable, but only if you actually
# trace connectivity instead of counting dark pixels.
CHANNEL = {"tl": (0, 2, 5), "tr": (12, 14, 5), "bl": (0, 2, 9), "br": (12, 14, 9)}

# A lid covers one slot completely and overhangs the blob's edge, so it reads as an object
# lying on top rather than as part of the blob. Coordinates are cell-local.
LID_RECT = {"tl": (1, 2, 9, 7), "tr": (9, 2, 9, 7),
            "bl": (1, 8, 9, 7), "br": (9, 8, 9, 7)}

HOLE, GAP = "hole", "gap"

# Gate hole layouts, gate-local, each cavity 3x3 on rows 5..7 with solid walls all round.
GATE_HOLES = {
    0: (),
    1: ((6, 5),),
    2: ((3, 5), (9, 5)),
    3: ((1, 5), (6, 5), (11, 5)),
}


def _blob_mask(silhouette, feats):
    """Body mask for a blob: silhouette minus every carved cavity (and channel)."""
    mask = np.zeros((BLOB, BLOB), dtype=bool)
    for y, row in enumerate(SILHOUETTES[silhouette]):
        for x, ch in enumerate(row):
            mask[y, x] = ch == "#"
    for slot, kind in feats:
        hx, hy = HOLE_XY[slot]
        mask[hy:hy + 3, hx:hx + 3] = False
        if kind == GAP:
            x0, x1, cy = CHANNEL[slot]
            mask[cy, x0:x1 + 1] = False
    return mask


def _gate_mask(n_holes):
    mask = np.ones((GATE_H, GATE_W), dtype=bool)
    for (hx, hy) in GATE_HOLES[n_holes]:
        mask[hy:hy + 3, hx:hx + 3] = False
    return mask


GATE_MASKS = {n: _gate_mask(n) for n in GATE_HOLES}   # built once; the renderer is hot


def count_holes(mask):
    """Number of background components enclosed by `mask`.

    Background is 4-connected, so a 1px straight channel really does open a cavity to the
    outside and no diagonal leak can be mistaken for one. The mask is padded first so the
    flood always starts in genuine outside space.
    """
    h, w = mask.shape
    bg = np.ones((h + 2, w + 2), dtype=bool)
    bg[1:h + 1, 1:w + 1] = ~mask
    seen = np.zeros_like(bg)

    def flood(sy, sx):
        stack = [(sy, sx)]
        seen[sy, sx] = True
        while stack:
            y, x = stack.pop()
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h + 2 and 0 <= nx < w + 2 and bg[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))

    flood(0, 0)
    holes = 0
    for y in range(h + 2):
        for x in range(w + 2):
            if bg[y, x] and not seen[y, x]:
                holes += 1
                flood(y, x)
    return holes


# ---------------------------------------------------------------------------
# Levels
#
# Escalation adds a rule each time and never repeals one:
#   L1 colour agrees with hole count (redundant cue -- the rule is taught, not guessed)
#   L2 colour scrambled: same colour/different count and same count/different colour
#   L3 one silhouette for every blob, so the outline carries nothing
#   L4 lids hide cavities, so the visible count under-reports the true one
#   L5 near-closed cavities: a 1px channel means it is not a hole
#   L6 lids and channels together, two lives
#   L7 all of it, more of both, tightest budget
#
# Each blob is (cell, silhouette, colour, ((slot, kind), ...)). Lids are (cell, slot).
# "gates" is the left-to-right order of gate hole counts; it is permuted every level so
# gate identity has to be read off the gate's own topology, not memorised as a position.
# ---------------------------------------------------------------------------

Y, LM, LB, PU = BODY[0], BODY[1], BODY[2], BODY[3]

LEVELS = [
    {
        "name": "Two Kinds",
        "lives": 6, "budget": 50,
        "gates": (1, 3, 0, 2),
        "blobs": [
            (0, "round", Y, (("tl", HOLE),)),
            (2, "block", Y, (("br", HOLE),)),
            (3, "cross", LM, (("tl", HOLE), ("tr", HOLE))),
            (5, "round", LM, (("bl", HOLE), ("br", HOLE))),
        ],
        "lids": [],
    },
    {
        # NEW: colour is scrambled. Yellow now covers a 2-hole and a 0-hole blob; light
        # blue covers a 1-hole and a 2-hole blob. Anything learned about hue on L1 is
        # actively wrong here, which is the point.
        "name": "False Colours",
        "lives": 3, "budget": 44,
        "gates": (2, 0, 3, 1),
        "blobs": [
            (0, "round", LB, (("tl", HOLE),)),
            (1, "block", Y, (("tl", HOLE), ("br", HOLE))),
            (2, "cross", LM, (("tl", HOLE), ("tr", HOLE), ("bl", HOLE))),
            (3, "round", Y, ()),
            # Six specimens, not five. With five, a policy that has the click grammar but
            # not the rule cleared this level about one run in 71 -- it only needed five
            # correct 1-in-4 guesses before its third mistake. A sixth pushes that under
            # 1/500 and fills the sixth cell, which was sitting empty.
            (4, "round", PU, (("tr", HOLE), ("bl", HOLE), ("br", HOLE))),
            (5, "block", LB, (("tr", HOLE), ("bl", HOLE))),
        ],
        "lids": [],
    },
    {
        # NEW: one silhouette everywhere. The harness's outline tracer returns the same
        # boundary for all six blobs, so the count has to come from the interior pixels.
        "name": "One Silhouette",
        "lives": 3, "budget": 44,
        "gates": (3, 1, 2, 0),
        "blobs": [
            (0, "cross", LM, ()),
            (1, "cross", LB, (("tr", HOLE),)),
            (2, "cross", Y, (("tl", HOLE), ("br", HOLE))),
            (3, "cross", PU, (("tl", HOLE), ("tr", HOLE), ("bl", HOLE))),
            (4, "cross", LM, (("bl", HOLE),)),
            (5, "cross", LB, (("tl", HOLE), ("bl", HOLE))),
        ],
        "lids": [],
    },
    {
        # NEW: lids. A lidded blob shows fewer holes than it has, so sorting on what is
        # visible is wrong. Clicking a lid removes it for 2 budget -- cheaper than the life
        # a wrong gate costs, which is the lesson.
        "name": "Under The Lid",
        "lives": 3, "budget": 52,
        "gates": (0, 2, 1, 3),
        "blobs": [
            (0, "cross", Y, (("tl", HOLE), ("tr", HOLE))),
            (1, "cross", LB, (("tl", HOLE),)),
            (2, "cross", LM, (("tl", HOLE), ("tr", HOLE), ("bl", HOLE))),
            (3, "cross", Y, ()),
            (4, "cross", LM, (("br", HOLE),)),
            (5, "cross", LB, (("tl", HOLE), ("bl", HOLE))),
        ],
        "lids": [(0, "tl"), (2, "bl"), (4, "br")],
    },
    {
        # NEW: near-closed cavities. Same 3x3 void, but a 1px channel joins it to the
        # outside, so it is a bay and not a hole. This is the level that breaks any policy
        # counting dark pixels rather than reasoning about connectivity.
        "name": "Almost Closed",
        "lives": 3, "budget": 44,
        "gates": (1, 0, 3, 2),
        "blobs": [
            (0, "cross", Y, (("tl", HOLE), ("tr", GAP))),
            (1, "cross", LM, (("tl", GAP),)),
            (2, "cross", LB, (("tl", HOLE), ("tr", HOLE), ("bl", GAP))),
            (3, "cross", PU, (("tl", HOLE), ("tr", HOLE), ("bl", HOLE))),
            (4, "cross", Y, (("bl", HOLE),)),
            (5, "cross", LM, (("tl", GAP), ("br", GAP))),
        ],
        "lids": [],
    },
    {
        # NEW: lids and channels at once, and one life fewer. A lid may be hiding a real
        # hole or a bay, so what is under it still has to be looked at.
        "name": "Census",
        "lives": 2, "budget": 48,
        "gates": (2, 3, 0, 1),
        "blobs": [
            (0, "cross", LB, (("tl", HOLE), ("tr", GAP))),
            (1, "cross", Y, (("tl", HOLE), ("tr", HOLE))),
            (2, "cross", LM, (("tl", GAP), ("bl", HOLE), ("br", HOLE))),
            (3, "cross", LB, (("tl", HOLE), ("tr", HOLE), ("bl", HOLE))),
            (4, "cross", Y, (("bl", GAP),)),
            (5, "cross", LM, (("tl", HOLE), ("br", GAP))),
        ],
        "lids": [(0, "tl"), (2, "br"), (5, "tl")],
    },
    {
        "name": "Full Census",
        "lives": 2, "budget": 48,
        "gates": (3, 2, 1, 0),
        "blobs": [
            (0, "cross", PU, (("tl", HOLE), ("tr", HOLE), ("bl", GAP))),
            (1, "cross", Y, (("tl", GAP), ("tr", GAP))),
            (2, "cross", LM, (("tl", HOLE), ("tr", HOLE), ("bl", HOLE))),
            (3, "cross", LB, (("br", HOLE),)),
            (4, "cross", Y, (("tl", HOLE), ("br", GAP))),
            (5, "cross", LM, (("tl", HOLE), ("tr", HOLE))),
        ],
        "lids": [(2, "bl"), (3, "br"), (4, "tl"), (5, "tr")],
    },
]


def cell_origin(cell):
    return CELL_X[cell % 3], CELL_Y[cell // 3]


_BLOB_CACHE = {}


def blob_data(silhouette, feats):
    """(mask, hole count) for a blob spec, memoised -- on_set_level runs on every level
    entry and every engine reset, and the flood fill is not free. Masks are never mutated
    (a lid is drawn over the top, a sorted blob is dropped from the list), so sharing one
    array between levels is safe."""
    key = (silhouette, feats)
    if key not in _BLOB_CACHE:
        mask = _blob_mask(silhouette, feats)
        _BLOB_CACHE[key] = (mask, count_holes(mask))
    return _BLOB_CACHE[key]


# ---------------------------------------------------------------------------
# Build-time validation. Every one of these has a matching failure mode in the brief, so
# they run at import and take the game down loudly rather than shipping a broken level.
# ---------------------------------------------------------------------------

def _validate():
    for n in GATE_HOLES:
        assert count_holes(_gate_mask(n)) == n, f"gate art for {n} does not have {n} holes"
    for li, ldef in enumerate(LEVELS):
        assert sorted(ldef["gates"]) == [0, 1, 2, 3], f"L{li + 1} gate set"
        cells = [b[0] for b in ldef["blobs"]]
        assert len(set(cells)) == len(cells), f"L{li + 1} two blobs in one cell"
        counts = set()
        for (cell, sil, colour, feats) in ldef["blobs"]:
            n = count_holes(_blob_mask(sil, feats))
            declared = sum(1 for _, k in feats if k == HOLE)
            assert n == declared, f"L{li + 1} cell {cell}: art shows {n} holes, meant {declared}"
            assert n in ldef["gates"], f"L{li + 1} cell {cell}: no gate accepts {n}"
            counts.add(n)
        for (cell, slot) in ldef["lids"]:
            blob = next(b for b in ldef["blobs"] if b[0] == cell)
            assert blob[2] != PU, f"L{li + 1} cell {cell}: lid on a purple blob (low contrast)"
            assert any(s == slot for s, _ in blob[3]), f"L{li + 1} cell {cell}: lid covers nothing"
        # A level whose blobs all share one hole count is solvable by picking a gate at
        # random once and repeating -- that is the "one broad winning condition" trap.
        assert len(counts) >= 2, f"L{li + 1} every blob has the same hole count"


_validate()


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

class Gn01Display(RenderableUserDisplay):
    def __init__(self, game):
        self.game = game

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game
        frame[:, :] = C_FIELD

        # -- budget bar: length is the signal, colour is the second, redundant one -------
        span = BAR_X1 - BAR_X0
        frame[BAR_Y:BAR_Y + 2, BAR_X0:BAR_X1] = C_VDGRAY
        if g.budget_max > 0 and g.budget_left > 0:
            filled = max(1, int(span * g.budget_left / g.budget_max))
            colour = C_BAR_OK if g.budget_left * 3 > g.budget_max else C_BAR_LOW
            frame[BAR_Y:BAR_Y + 2, BAR_X0:BAR_X0 + filled] = colour

        # -- life pips ------------------------------------------------------------------
        for i in range(g.lives_max):
            x = PIP_X0 + i * PIP_STEP
            if x + 3 <= GRID:
                frame[PIP_Y:PIP_Y + 3, x:x + 3] = C_PIP_ON if i < g.lives else C_PIP_OFF

        # -- structural rule line separating the field from the gates -------------------
        frame[RULE_Y, 0:GRID] = C_RULE

        # -- blobs ----------------------------------------------------------------------
        for blob in g.blobs:
            ox, oy = cell_origin(blob["cell"])
            ox += BLOB_OX
            oy += BLOB_OY
            sub = frame[oy:oy + BLOB, ox:ox + BLOB]
            sub[blob["mask"]] = blob["colour"]

        # -- lids, drawn over the blobs with a 1px seam so they read as separate objects -
        for lid in g.lids:
            if not lid["alive"]:
                continue
            x0, y0, w, h = lid["rect"]
            frame[y0 - 1:y0 + h + 1, x0 - 1:x0 + w + 1] = C_SEAM
            frame[y0:y0 + h, x0:x0 + w] = C_LID

        # -- the held blob's cell gets a frame: selection carried by shape, not by hue ---
        if g.held is not None:
            cx, cy = cell_origin(g.held["cell"])
            x0, y0 = cx - 1, cy - 1
            x1, y1 = cx + CELL_W, cy + CELL_H
            frame[y0, x0:x1 + 1] = C_HOLD
            frame[y1, x0:x1 + 1] = C_HOLD
            frame[y0:y1 + 1, x0] = C_HOLD
            frame[y0:y1 + 1, x1] = C_HOLD

        # -- gates ----------------------------------------------------------------------
        for gi, n in enumerate(g.gates):
            gx = GATE_X[gi]
            slab = C_GATE
            if g.flash is not None and g.flash[0] == gi:
                slab = C_ACCEPT if g.flash[1] == "good" else C_REJECT
            sub = frame[GATE_Y:GATE_Y + GATE_H, gx:gx + GATE_W]
            sub[GATE_MASKS[n]] = slab
            # Colour as affordance, recomputed every step: the gates only do anything
            # while a blob is held, and they show it by lighting their rim.
            if g.held is not None and g.flash is None:
                frame[GATE_Y, gx:gx + GATE_W] = C_GATE_ARMED
                frame[GATE_Y + GATE_H - 1, gx:gx + GATE_W] = C_GATE_ARMED
                frame[GATE_Y:GATE_Y + GATE_H, gx] = C_GATE_ARMED
                frame[GATE_Y:GATE_Y + GATE_H, gx + GATE_W - 1] = C_GATE_ARMED

        return frame


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class Gn01(ARCBaseGame):
    def __init__(self):
        self.display = Gn01Display(self)

        # on_set_level() runs inside super().__init__(), so all of this must exist first.
        self.blobs = []
        self.lids = []
        self.gates = (0, 1, 2, 3)
        self.held = None
        self.flash = None
        self.lives = 0
        self.lives_max = 0
        self.budget_max = 0
        self.budget_left = 0
        self._anim = 0

        levels = [Level(sprites=[], grid_size=(GRID, GRID), data=ldef, name=ldef["name"])
                  for ldef in LEVELS]

        super().__init__(
            "gn",
            levels,
            Camera(0, 0, GRID, GRID, C_FIELD, C_FIELD, [self.display]),
            False,
            len(levels),
            [6],                     # click-only: click a blob, click a gate, click a lid
        )

    # -- level setup --------------------------------------------------------

    def on_set_level(self, level: Level) -> None:
        ldef = LEVELS[self.level_index]
        self.gates = ldef["gates"]
        self.blobs = []
        for (cell, sil, colour, feats) in ldef["blobs"]:
            mask, holes = blob_data(sil, feats)
            self.blobs.append({"cell": cell, "colour": colour, "mask": mask,
                               "holes": holes})
        self.lids = []
        for (cell, slot) in ldef["lids"]:
            cx, cy = cell_origin(cell)
            lx, ly, lw, lh = LID_RECT[slot]
            self.lids.append({"cell": cell, "alive": True,
                              "rect": (cx + lx, cy + ly, lw, lh)})
        self.held = None
        self.flash = None
        self._anim = 0
        self.lives = self.lives_max = ldef["lives"]
        self.budget_max = self.budget_left = ldef["budget"]

    # -- click resolution ---------------------------------------------------

    def _click(self, x, y):
        for lid in self.lids:                                   # lids sit on top
            if lid["alive"]:
                lx, ly, lw, lh = lid["rect"]
                if lx <= x < lx + lw and ly <= y < ly + lh:
                    self.budget_left -= LID_COST
                    lid["alive"] = False
                    return

        for blob in self.blobs:                                 # pick up / put down / swap
            cx, cy = cell_origin(blob["cell"])
            if cx <= x < cx + CELL_W and cy <= y < cy + CELL_H:
                self.budget_left -= SELECT_COST
                self.held = None if self.held is blob else blob
                return

        for gi, n in enumerate(self.gates):                     # deposit
            gx = GATE_X[gi]
            if gx <= x < gx + GATE_W and GATE_Y <= y < GATE_Y + GATE_H:
                if self.held is None:
                    self.budget_left -= MISS_COST               # a gate is inert empty-handed
                    return
                self.budget_left -= DEPOSIT_COST
                blob = self.held
                self.held = None
                if n == blob["holes"]:
                    self.blobs.remove(blob)
                    self.flash = (gi, "good")
                else:
                    self.lives -= 1                             # a cost, never an instant end
                    self.flash = (gi, "bad")
                self._anim = ANIM_FRAMES
                return

        self.budget_left -= MISS_COST                           # empty field / HUD

    # -- resolution ---------------------------------------------------------

    def _settle(self):
        if not self.blobs:
            self.next_level()
            return
        if self.lives <= 0 or self.budget_left <= 0:
            self.lives = max(0, self.lives)
            self.budget_left = max(0, self.budget_left)
            self.lose()

    # -- engine entry point -------------------------------------------------

    def step(self) -> None:
        if self._anim > 0:
            self._anim -= 1
            if self._anim == 0:
                self.flash = None        # cleared before the final render, so the last
                self._settle()           # frame of the action is always a clean board
                self.complete_action()
            return

        if self.action.id.value == 6:
            data = self.action.data or {}
            x, y = int(data.get("x", -1)), int(data.get("y", -1))
            if 0 <= x < GRID and 0 <= y < GRID:
                self._click(x, y)
            else:
                self.budget_left -= MISS_COST
            if self._anim > 0:
                return                   # a flash is running; finish on its last frame

        # RESET and anything unexpected fall through: no cost, no death, just a frame.
        self._settle()
        self.complete_action()
