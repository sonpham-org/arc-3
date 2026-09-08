# Author: Claude Opus 5
# Date: 2026-08-27 09:20 (board reshaped from a ring to a staff, and the budget bar and
#   progress pips replaced by state carried on the stones themselves, 2026-09-02; the
#   mechanics are untouched)
# PURPOSE: kd01 "Cadence" -- an ARC-AGI-3 environment built to MEASURE one specific
#   behaviour: committing to a whole plan instead of improvising one action at a time.
#   A vertical STAFF of stones runs down the middle of the board with a lock at its foot. A
#   strip beside the staff names the stones that must be struck, in order. The lock only
#   opens for the exact, UNINTERRUPTED run: any wrong strike, any strike on empty ground,
#   and any release (ACTION5) drops the mechanism back to zero. Single-stepping "try one,
#   look, try another" therefore can never solve it -- the whole sequence has to be worked
#   out from the board first and then delivered in one unbroken run, which is exactly what
#   batching several actions into one harness call produces.
#   Core-knowledge priors only: objectness, geometry, agentness.
#   No text, no glyphs, no digits, no bars, no pips, no cultural colour conventions.
# SRP/DRY check: Pass -- self-contained environment. Nothing in the catalogue enforces an
#   uninterrupted action sequence as its win condition, so there is nothing to reuse.
"""Cadence -- read the strip, then deliver the whole run without a single wrong move.

Click a stone to strike it. ACTION5 releases the mechanism (progress back to zero, cheap).
Striking the wrong stone, a dead stone, or bare ground STALLS the mechanism: progress resets
AND the stall costs several units of the action budget, so blind retrying runs you dry.

A struck stone's seat peg lights up while the run is alive; the plinth under the lock shows
the mechanism's state. Every live stone wears a halo whose colour is the budget tier. The
strip is on screen, fully readable, at all times: nothing in this game asks you to hold a
sequence in your head -- it asks you to work one out from what is drawn.

7 levels. No RNG. Lose by running the budget out.
"""

import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

# ---------------------------------------------------------------------------
# Colours (ARC-3 palette indices)
# ---------------------------------------------------------------------------

C_WHITE, C_LGRAY, C_GRAY, C_DGRAY, C_VDGRAY, C_BLACK = 0, 1, 2, 3, 4, 5
C_MAGENTA, C_LMAGENTA, C_RED, C_BLUE, C_LBLUE = 6, 7, 8, 9, 10
C_YELLOW, C_ORANGE, C_MAROON, C_GREEN, C_PURPLE = 11, 12, 13, 14, 15

# Reserved, never used as a stone colour, so each has exactly one meaning in this world:
#   C_YELLOW  -- "the lock wants striking" (plinth) and the strip marker that says so
#   C_LBLUE   -- "the mechanism is armed": the plinth, and the peg of every stone struck
#   C_WHITE   -- "the lock is opening", and the size-blob inside a size marker
#   C_BLACK   -- "the mechanism just stalled" (maroon is the field now)
#   C_LGRAY   -- the lock block itself (a fixed colour: the PLINTH under it carries state)
STONE_COLORS = (C_RED, C_BLUE, C_GREEN, C_MAGENTA, C_ORANGE, C_PURPLE)

# ---------------------------------------------------------------------------
# Geometry -- a vertical staff, read top to bottom. No bar, no pips: every piece of
# state lives on a world object (a stone's halo, a stone's peg, the plinth).
#
#   x:  6..10  strip column 1 (decoy, levels 6-7 only)
#      13..17  strip column 0
#      22..58  the staff: a 1-px rail at x=40 with a seat every 8 rows, stones hanging
#              alternately left (even slots) and right (odd slots) of the rail so six
#              stones and their halos fit in 64 rows and every stone keeps its own row band
#      36..44  the lock block (rows 55-59) standing on a 21-px plinth (rows 60-63)
# ---------------------------------------------------------------------------

RAIL_X = 40                      # the staff's rail; also the lock's centre line
STAFF_Y0 = 0                     # the rail runs from the top edge down into the lock
SLOT_DX = 14                     # stones hang this far left/right of the rail. Widened
                                 # from 10: at 10 the six seats read as one wobbly column,
                                 # which made the staff look like a signal head. At 14 the
                                 # zigzag is unmistakable and a radius-6 halo still fits
                                 # (40 +/- 14, +/- 6 -> 20..60 inside the 64px frame).
SLOT_Y0, SLOT_PITCH = 8, 8       # slot 0 is at the top; one seat every 8 rows
SLOT_POS = tuple((RAIL_X - SLOT_DX if i % 2 == 0 else RAIL_X + SLOT_DX,
                  SLOT_Y0 + i * SLOT_PITCH) for i in range(6))
# = ((30, 8), (50, 16), (30, 24), (50, 32), (30, 40), (50, 48))
# Same-side seats are 16 rows apart, so the halos of a radius-6 and a radius-5 stone
# (8 + 7 = 15) never touch. Slot 5 sits 7 rows above the lock block: it holds a ruin or
# a size <= 4 stone in every level, and a size-5 stone there would cross into the lock.
HALO_GAP = 1                     # black rows between a stone's edge and its halo ring

LOCK_X = RAIL_X                  # the lock block sits at the foot of the rail
LOCK_Y0, LOCK_Y1 = 55, 59        # rows of the lock block
LOCK_HALF = 4                    # block half-width: 9 px wide
LOCK_Y = (LOCK_Y0 + LOCK_Y1) // 2   # 55 -- the point the tests strike
PLINTH_Y0 = 60                   # the plinth: rows 60..63 ...
PLINTH_HALF = 10                 # ... and 21 px wide. Its colour is the mechanism's state.
DEAD_R = 5                       # dead stones always draw at this radius (no size to read)

STRIP_X = (13, 6)                # left x of strip column 0 / column 1
STRIP_Y0 = 2                     # first marker's top row
CELL_W, CELL_H, CELL_PITCH = 5, 5, 6      # strip marker cells, stacked downwards

STEP_COST = 1                    # a strike the mechanism accepted
RELEASE_COST = 1                 # ACTION5, a deliberate abort
STALL_FRAMES = 3                 # animation length of a stall
OPEN_FRAMES = 4                  # animation length of the lock opening

# Budget tiers: the budget is read in LAPS of eight actions, and the tier colour of the
# current lap is worn by every live stone as a halo. Borrowed from how AR25/BP35/LF52
# pack a long budget into a few pixels; here it is on the objects, not on a HUD.
TIERS = (C_LMAGENTA, C_GRAY, C_DGRAY, C_VDGRAY)  # final lap first: the halo fades
LAP = 8

# ---------------------------------------------------------------------------
# Levels
#
# nodes: (slot, colour, size, alive). size 1..5 -> drawn radius 2..6; a dead stone has
#        size 0 and draws at DEAD_R, so it can never be named by a size marker.
# runs:  one list of node indices per run. Between two runs the mechanism latches and the
#        LOCK ITSELF must be struck before the next run may start.
# keys:  per marker, how the strip names that stone -- "c" by colour, "s" by size.
# decoy: an extra strip column that is deliberately unsatisfiable: it names a stone that is
#        not on the staff. Exactly one of the two columns can actually be performed.
#
# ESCALATION -- one new rule per level, every earlier rule still in force:
#   1 strike the stones the strip names, in order      (2 long, forgiving budget)
#   2 + a wrong strike STALLS: it costs 3, not 1, and a stone may repeat
#       (7 strikes over 6 stones: the exact-DP blind clear rate is 1/376,000 at budget 21;
#        6 strikes was 1/44,000, and cutting the budget instead of the run only reaches
#        1/100,000 at budget 11, which leaves a human one early mistake)
#   3 + the strip names stones by SIZE, not by colour  (colourless stones; derive, do not read)
#   4 + colour markers and size markers mixed in one strip (two naming keys at once)
#   5 + two runs in a fixed order, latched by striking the lock
#   6 + a decoy strip column that names a stone that is not there
#   7 everything at once
#
# There is deliberately no rule that depends on history. An earlier build darkened the strip
# while the mechanism was armed, which asked the player to hold seven to ten items in mind;
# that is the one mechanic the ARC-3 team flagged as too hard for humans, and it was removed
# (2026-09-02). The strip is readable at every moment of every level.
# ---------------------------------------------------------------------------

LEVELS = [
    {
        "name": "First Pair",
        "budget": 24, "stall": 1,
        "nodes": [(0, C_RED, 3, True), (2, C_BLUE, 3, True), (4, C_GREEN, 3, True)],
        "runs": [[1, 0]],
        "keys": [["c", "c"]],
        "decoy": None, "decoy_first": False,
    },
    {
        "name": "Stall",
        "budget": 21, "stall": 3,
        "nodes": [(0, C_RED, 3, True), (1, C_BLUE, 3, True), (2, C_GREEN, 3, True),
                  (3, C_MAGENTA, 3, True), (4, C_ORANGE, 3, True), (5, C_PURPLE, 3, True)],
        # every stone once, then back to the first: the one repeat a 7-run over 6 stones
        # must contain is the easiest kind to hold in mind, and the strip stays lit here
        "runs": [[2, 5, 0, 3, 1, 4, 2]],
        "keys": [["c"] * 7],
        "decoy": None, "decoy_first": False,
    },
    {
        "name": "Weights",
        "budget": 21, "stall": 3,
        # colourless stones: the strip names them by size alone, and white stones read as
        # the same object as the white size-blob inside a strip marker. Five sizes, five
        # stones -- and a ruin in the sixth seat (dead, unnameable, a stall to strike) so the
        # seat count, and with it the blind clear rate (1/376,000), match level 2.
        "nodes": [(0, C_WHITE, 1, True), (1, C_WHITE, 4, True), (2, C_WHITE, 2, True),
                  (3, C_WHITE, 5, True), (4, C_WHITE, 3, True), (5, C_VDGRAY, 0, False)],
        "runs": [[3, 0, 4, 1, 2, 0, 3]],          # sizes 5 1 3 4 2 1 5
        "keys": [["s"] * 7],
        "decoy": None, "decoy_first": False,
    },
    {
        "name": "Mixed",
        "budget": 22, "stall": 3,
        # colour markers and size markers in ONE strip. Two stones share size 3, so no size
        # marker could name either of them; the strip names those two by colour. Both keys
        # have to be handled at once, on stones that carry both a colour and a size.
        "nodes": [(0, C_RED, 2, True), (1, C_BLUE, 5, True), (2, C_GREEN, 1, True),
                  (3, C_MAGENTA, 4, True), (4, C_PURPLE, 3, True), (5, C_ORANGE, 3, True)],
        "runs": [[1, 4, 0, 3, 5, 2, 1]],          # size5 purple size2 magenta orange size1 blue
        "keys": [["s", "c", "s", "c", "c", "s", "c"]],
        "decoy": None, "decoy_first": False,
    },
    {
        "name": "Two Runs",
        "budget": 24, "stall": 3,
        "nodes": [(0, C_RED, 2, True), (1, C_BLUE, 5, True), (2, C_GREEN, 1, True),
                  (3, C_MAGENTA, 4, True), (4, C_PURPLE, 3, True)],
        "runs": [[4, 1, 0, 3], [2, 0, 4, 1]],
        "keys": [["c", "s", "c", "s"], ["s", "c", "s", "c"]],
        "decoy": None, "decoy_first": False,
    },
    {
        "name": "Ghost Line",
        "budget": 22, "stall": 3,
        "nodes": [(0, C_GREEN, 3, True), (1, C_MAGENTA, 1, True), (2, C_BLUE, 4, True),
                  (3, C_PURPLE, 2, True), (4, C_RED, 5, True), (5, C_VDGRAY, 0, False)],
        "runs": [[2, 4, 0, 3, 1, 4, 2]],
        "keys": [["c", "s", "c", "s", "c", "c", "s"]],
        # names an orange stone; there is no orange stone on the staff.
        "decoy": [("c", C_GREEN), ("s", 5), ("c", C_BLUE), ("c", C_ORANGE),
                  ("s", 2), ("c", C_MAGENTA), ("s", 4)],
        "decoy_first": True,
    },
    {
        "name": "Full Cadence",
        "budget": 25, "stall": 3,
        "nodes": [(0, C_BLUE, 5, True), (1, C_PURPLE, 2, True), (2, C_RED, 4, True),
                  (3, C_GREEN, 1, True), (4, C_MAGENTA, 3, True), (5, C_VDGRAY, 0, False)],
        "runs": [[1, 3, 4, 0], [2, 4, 1, 0, 3]],
        "keys": [["s", "c", "s", "c"], ["c", "s", "c", "s", "c"]],
        "decoy": [("c", C_PURPLE), ("s", 1), ("c", C_MAGENTA), ("s", 5), ("sep", 0),
                  ("s", 4), ("c", C_ORANGE), ("s", 2), ("c", C_BLUE), ("s", 3)],
        "decoy_first": False,
    },
]


def node_radius(node):
    """Drawn radius of a stone. Dead stones have no size, so none can be named by size.
    The +1 spreads the five sizes over radii 2..6 so neighbouring sizes stay tellable."""
    return DEAD_R if not node["alive"] else node["size"] + 1


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

class Kd01Display(RenderableUserDisplay):
    def __init__(self, game):
        self.game = game

    @staticmethod
    def _plot(frame, x, y, color):
        if 0 <= x < 64 and 0 <= y < 64:
            frame[y, x] = color

    def _disc(self, frame, cx, cy, r, color):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r:
                    self._plot(frame, cx + dx, cy + dy, color)

    def _halo(self, frame, cx, cy, r, color):
        """A 1-px ring at radius r, built from pixel distance -- (r-1)^2 < d^2 <= r^2 --
        so it is closed at every radius; a sampled circle goes dotted as r grows."""
        lo, hi = (r - 1) * (r - 1), r * r
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                d = dx * dx + dy * dy
                if lo < d <= hi:
                    self._plot(frame, cx + dx, cy + dy, color)

    # -- strip ------------------------------------------------------------

    def _marker(self, frame, x0, y0, spec):
        kind, val = spec
        if kind == "c":
            frame[y0:y0 + CELL_H, x0:x0 + CELL_W] = val
        elif kind == "s":
            # a size marker: a white blob whose side equals the stone's size
            frame[y0:y0 + CELL_H, x0:x0 + CELL_W] = C_DGRAY
            k = max(1, min(CELL_W, val))
            ox = x0 + (CELL_W - k) // 2
            oy = y0 + (CELL_H - k) // 2
            frame[oy:oy + k, ox:ox + k] = C_WHITE
        else:
            # "sep" -- strike the lock itself. Drawn as the lock in miniature: a block
            # standing on a plinth, in the yellow the real plinth turns when it wants
            # striking, so the marker and the object it names share both shape and hue.
            frame[y0 + 3:y0 + CELL_H, x0:x0 + CELL_W] = C_YELLOW
            frame[y0:y0 + 3, x0 + 1:x0 + CELL_W - 1] = C_LGRAY

    def _column(self, frame, x0, specs):
        """One strip column, first marker at the top -- read it downwards."""
        y = STRIP_Y0
        for spec in specs:
            self._marker(frame, x0, y, spec)
            y += CELL_PITCH

    # -- main -------------------------------------------------------------

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game
        # Palette note: this game keeps a black ground on purpose, and it is the one
        # exception to the project's move away from black-and-grey. kd01 uses all sixteen
        # palette entries -- six for the stones the player must name, four budget tiers,
        # five plinth states -- so EVERY vivid background collides with something the
        # player has to identify. A purple ground was tried and made the purple stone
        # invisible. Correctness wins.
        frame[:, :] = C_MAROON

        # Strip columns, beside the staff -- readable at every moment of every level.
        for idx, specs in enumerate(g.strip_rows):
            self._column(frame, STRIP_X[idx], specs)

        # The staff: a rail from the top edge down into the lock.
        frame[STAFF_Y0:LOCK_Y0, RAIL_X] = C_VDGRAY

        # Budget tier, recomputed every step and worn by every live stone as a halo.
        tier = None
        if g.budget_max > 0 and g.budget_left > 0:
            laps_left = (g.budget_left - 1) // LAP           # 0 = final lap
            tier = TIERS[min(laps_left, len(TIERS) - 1)]

        struck = {ni for run in g.filled for ni in run}      # this attempt, all runs
        occupied = {node["slot"] for node in g.nodes}

        # Seats: every slot has a peg from the rail, visible when the seat is empty
        # (levels 1, 4, 5) so the staff reads as one object with six seats.
        for slot, (sx, sy) in enumerate(SLOT_POS):
            if slot not in occupied:
                x0, x1 = sorted((RAIL_X, sx))
                frame[sy, x0:x1 + 1] = C_VDGRAY

        # Stones, drawn halo -> peg -> disc so the peg reads as passing through the halo
        # and ending under the stone.
        for ni, node in enumerate(g.nodes):
            sx, sy = SLOT_POS[node["slot"]]
            r = node_radius(node)
            if node["alive"] and tier is not None:
                self._halo(frame, sx, sy, r + HALO_GAP + 1, tier)
            x0, x1 = sorted((RAIL_X, sx))
            if ni in struck:
                # PROGRESS: a struck stone's peg goes thick and light blue -- the armed
                # hue -- and stays so until the run breaks or the lock opens. Colour is
                # paired with shape (thickness) so the state survives a colour-blind read.
                frame[sy - 1:sy + 2, x0:x1 + 1] = C_LBLUE
            else:
                frame[sy, x0:x1 + 1] = C_VDGRAY
            if node["alive"]:
                # no outline: at radius 2 an outline eats the whole stone, and the
                # background is black already, so nothing needs separating
                self._disc(frame, sx, sy, r, node["color"])
            else:                                # a ruin: hollow, unstrikeable, unnameable
                self._disc(frame, sx, sy, r, C_DGRAY)
                self._disc(frame, sx, sy, r - 2, C_BLACK)

        # The lock: a fixed-colour block at the foot of the rail ...
        frame[LOCK_Y0:LOCK_Y1 + 1, LOCK_X - LOCK_HALF:LOCK_X + LOCK_HALF + 1] = C_LGRAY

        # ... standing on the plinth -- colour as affordance, recomputed every step.
        if g.anim_kind == "stall":
            plinth = C_BLACK
        elif g.anim_kind == "open":
            plinth = C_WHITE
        elif g.latched:
            plinth = C_YELLOW                    # same hue as the strip's lock marker
        elif g.armed():
            plinth = C_LBLUE
        else:
            plinth = C_GRAY
        frame[PLINTH_Y0:64, LOCK_X - PLINTH_HALF:LOCK_X + PLINTH_HALF + 1] = plinth
        return frame


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class Kd01(ARCBaseGame):
    def __init__(self):
        self.display = Kd01Display(self)

        # on_set_level() runs inside super().__init__(), so all of this must exist first.
        self.nodes = []
        self.runs = []
        self.keys = []
        self.strip_rows = []
        self.real_row = 0
        self.stall_cost = 1
        self.budget_max = 0
        self.budget_left = 0
        self.run_idx = 0
        self.progress = 0
        self.latched = False
        self.filled = []
        self.anim = 0
        self.anim_kind = None

        levels = [Level(sprites=[], grid_size=(64, 64), data=ldef, name=ldef["name"])
                  for ldef in LEVELS]

        super().__init__(
            "kd",
            levels,
            Camera(0, 0, 64, 64, C_BLACK, C_BLACK, [self.display]),
            False,
            len(levels),
            [5, 6],              # 6 = strike what you clicked, 5 = release the mechanism
        )

    # -- level setup --------------------------------------------------------

    def on_set_level(self, level: Level) -> None:
        ldef = LEVELS[self.level_index]
        self.nodes = [{"slot": s, "color": c, "size": z, "alive": a}
                      for (s, c, z, a) in ldef["nodes"]]
        self.runs = [list(r) for r in ldef["runs"]]
        self.keys = [list(k) for k in ldef["keys"]]
        self.stall_cost = ldef["stall"]
        self.budget_max = self.budget_left = ldef["budget"]

        real = self._real_specs()
        decoy = [tuple(m) for m in ldef["decoy"]] if ldef["decoy"] else None
        if decoy is None:
            self.strip_rows = [real]
            self.real_row = 0
        elif ldef["decoy_first"]:
            self.strip_rows = [decoy, real]
            self.real_row = 1
        else:
            self.strip_rows = [real, decoy]
            self.real_row = 0

        self._clear()

    def _real_specs(self):
        """The strip that actually opens the lock, in the exact form it is drawn."""
        specs = []
        for r_i, run in enumerate(self.runs):
            if r_i:
                specs.append(("sep", 0))
            for pos, ni in enumerate(run):
                node = self.nodes[ni]
                if self.keys[r_i][pos] == "c":
                    specs.append(("c", node["color"]))
                else:
                    specs.append(("s", node["size"]))
        return specs

    def _clear(self):
        """Drop the mechanism all the way back to rest."""
        self.run_idx = 0
        self.progress = 0
        self.latched = False
        self.filled = [[] for _ in self.runs]
        self.anim = 0
        self.anim_kind = None

    # -- queries ------------------------------------------------------------

    def armed(self):
        return self.latched or self.progress > 0 or self.run_idx > 0

    def total_steps(self):
        """Actions a flawless run costs: every strike, plus one lock strike between runs."""
        return sum(len(r) for r in self.runs) + len(self.runs) - 1

    def node_at(self, x, y):
        for i, node in enumerate(self.nodes):
            sx, sy = SLOT_POS[node["slot"]]
            r = node_radius(node)
            if (x - sx) ** 2 + (y - sy) ** 2 <= r * r:
                return i
        return None

    def on_lock(self, x, y):
        """The lock block (with a 1-px margin) and the plinth are one clickable object."""
        in_block = abs(x - LOCK_X) <= LOCK_HALF + 1 and LOCK_Y0 - 1 <= y <= 63
        in_plinth = abs(x - LOCK_X) <= PLINTH_HALF and y >= PLINTH_Y0
        return in_block or in_plinth

    def expected(self):
        """What the mechanism wants next: ('lock', None) or ('node', index)."""
        if self.latched:
            return ("lock", None)
        return ("node", self.runs[self.run_idx][self.progress])

    # -- simulation ---------------------------------------------------------

    def _stall(self):
        """Any wrong or interleaved action. Progress is lost AND the budget is bitten --
        cheap experiments would otherwise let a blind policy enumerate sequences."""
        self.budget_left -= self.stall_cost
        self._clear()
        self.anim = STALL_FRAMES
        self.anim_kind = "stall"

    def _release(self):
        """ACTION5. A deliberate, cheap abort -- and, by the law of this game, an
        interruption: it drops the mechanism to zero just like a wrong strike."""
        self.budget_left -= RELEASE_COST
        self._clear()

    def _advance_run(self):
        if self.run_idx == len(self.runs) - 1:
            self.anim = OPEN_FRAMES
            self.anim_kind = "open"
        else:
            self.latched = True

    def _click(self, x, y):
        ni = self.node_at(x, y)
        if ni is not None and self.nodes[ni]["alive"]:
            kind, want = self.expected()
            if kind == "node" and ni == want:
                self.budget_left -= STEP_COST
                self.filled[self.run_idx].append(ni)
                self.progress += 1
                if self.progress == len(self.runs[self.run_idx]):
                    self._advance_run()
                return
            self._stall()
            return
        if ni is None and self.on_lock(x, y):
            if self.latched:
                self.budget_left -= STEP_COST
                self.latched = False
                self.run_idx += 1
                self.progress = 0
                return
            self._stall()
            return
        self._stall()                            # dead stone, or bare ground

    def _resolve(self):
        if self.anim_kind == "open":
            self.anim_kind = None
            self.next_level()
            self.complete_action()
            return
        # A stall's colour is deliberately NOT cleared here. Agents read frame[-1], so
        # feedback that lives only in the intermediate animation frames is feedback nobody
        # sees; the plinth stays maroon until the next action clears it.
        if self.budget_left <= 0:
            self.budget_left = 0
            self.lose()
        self.complete_action()

    # -- engine entry point -------------------------------------------------

    def step(self) -> None:
        aid = self.action.id.value

        if aid == 0:                             # RESET still reaches step()
            self.anim = 0
            self.anim_kind = None
            self.complete_action()
            return

        if self.anim > 0:                        # bounded multi-frame feedback
            self.anim -= 1
            if self.anim > 0:
                return
            self._resolve()
            return

        self.anim_kind = None                    # clear the previous action's residue

        if aid == 6:
            data = self.action.data or {}
            self._click(int(data.get("x", 0)), int(data.get("y", 0)))
        elif aid == 5:
            self._release()
        else:
            self._stall()

        if self.anim > 0:
            return
        self._resolve()
