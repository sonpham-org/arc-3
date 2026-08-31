# Author: Claude Opus 5
# Date: 2026-08-27 09:20
# PURPOSE: kd01 "Cadence" -- an ARC-AGI-3 environment built to MEASURE one specific
#   behaviour: committing to a whole plan instead of improvising one action at a time.
#   A ring of stones surrounds a lock. A strip above the ring names the stones that must be
#   struck, in order. The lock only opens for the exact, UNINTERRUPTED run: any wrong strike,
#   any strike on empty ground, and any release (ACTION5) drops the mechanism back to zero.
#   Single-stepping "try one, look, try another" therefore can never solve it -- the whole
#   sequence has to be worked out from the board first and then delivered in one unbroken
#   run, which is exactly what batching several actions into one harness call produces.
#   Core-knowledge priors only: objectness, geometry, counting-as-pips, agentness.
#   No text, no glyphs, no digits, no cultural colour conventions.
# SRP/DRY check: Pass -- self-contained environment. Nothing in the catalogue enforces an
#   uninterrupted action sequence as its win condition, so there is nothing to reuse.
"""Cadence -- read the strip, then deliver the whole run without a single wrong move.

Click a stone to strike it. ACTION5 releases the mechanism (progress back to zero, cheap).
Striking the wrong stone, a dead stone, or bare ground STALLS the mechanism: progress resets
AND the stall costs several units of the action budget, so blind retrying runs you dry.

The lock's pips show how far into the run you are. Once the mechanism is armed the strip
goes dark (level 3 onwards) -- you cannot re-read it mid-run without breaking the run.

7 levels. No RNG. Lose by running the budget out.
"""

import math

import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

# ---------------------------------------------------------------------------
# Colours (ARC-3 palette indices)
# ---------------------------------------------------------------------------

C_WHITE, C_LGRAY, C_GRAY, C_DGRAY, C_VDGRAY, C_BLACK = 0, 1, 2, 3, 4, 5
C_MAGENTA, C_LMAGENTA, C_RED, C_BLUE, C_LBLUE = 6, 7, 8, 9, 10
C_YELLOW, C_ORANGE, C_MAROON, C_GREEN, C_PURPLE = 11, 12, 13, 14, 15

# Reserved, never used as a stone colour, so each has exactly one meaning in this world:
#   C_YELLOW  -- "the lock wants striking" (hub) and the strip marker that says so
#   C_LBLUE   -- "the mechanism is armed"
#   C_WHITE   -- "the lock is opening", and the size-blob inside a size marker
#   C_MAROON  -- "the mechanism just stalled"
STONE_COLORS = (C_RED, C_BLUE, C_GREEN, C_MAGENTA, C_ORANGE, C_PURPLE)

# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

CX, CY = 32, 38                  # centre of the lock, and of the stone ring
SLOT_R = 20                      # radius the stones sit on
SLOT_POS = ((52, 38), (42, 55), (22, 55), (12, 38), (22, 21), (42, 21))

HUB_R = 5                        # drawn radius of the lock hub
HUB_CLICK_R = 13                 # the whole lock assembly is one clickable object
PIP_R = (8, 12)                  # radii of the run-1 and run-2 pip rings
DEAD_R = 5                       # dead stones always draw at this radius (no size to read)

BAR_Y, BAR_X0, BAR_X1 = 0, 1, 63          # budget bar
STRIP_Y = (3, 9)                          # top-left y of strip row 0 / row 1
CELL_W, CELL_H, CELL_PITCH = 5, 5, 6      # strip marker cells

STEP_COST = 1                    # a strike the mechanism accepted
RELEASE_COST = 1                 # ACTION5, a deliberate abort
STALL_FRAMES = 3                 # animation length of a stall
OPEN_FRAMES = 4                  # animation length of the lock opening

# ---------------------------------------------------------------------------
# Levels
#
# nodes: (slot, colour, size, alive). size 1..5 -> drawn radius 2..6; a dead stone has
#        size 0 and draws at DEAD_R, so it can never be named by a size marker.
# runs:  one list of node indices per run. Between two runs the mechanism latches and the
#        LOCK ITSELF must be struck (the hub) before the next run may start.
# keys:  per marker, how the strip names that stone -- "c" by colour, "s" by size.
# decoy: an extra strip row that is deliberately unsatisfiable: it names a stone that is
#        not on the ring. Exactly one of the two rows can actually be performed.
#
# ESCALATION -- one new rule per level, every earlier rule still in force:
#   1 strike the stones the strip names, in order      (2 long, forgiving budget)
#   2 + a wrong strike STALLS: it costs 3, not 1       (brute force now runs you dry)
#   3 + the strip goes dark while the mechanism is armed, and a stone may repeat
#   4 + the strip names stones by SIZE, not by colour  (derive, do not read)
#   5 + two runs in a fixed order, latched by striking the lock; mixed colour/size naming
#   6 + a decoy strip row that names a stone that is not there
#   7 everything at once
# ---------------------------------------------------------------------------

LEVELS = [
    {
        "name": "First Pair",
        "budget": 24, "stall": 1, "hide": False,
        "nodes": [(0, C_RED, 3, True), (2, C_BLUE, 3, True), (4, C_GREEN, 3, True)],
        "runs": [[1, 0]],
        "keys": [["c", "c"]],
        "decoy": None, "decoy_first": False,
    },
    {
        "name": "Stall",
        "budget": 21, "stall": 3, "hide": False,
        "nodes": [(0, C_RED, 3, True), (1, C_BLUE, 3, True), (2, C_GREEN, 3, True),
                  (3, C_MAGENTA, 3, True), (4, C_ORANGE, 3, True), (5, C_PURPLE, 3, True)],
        "runs": [[2, 5, 0, 3, 1, 4]],
        "keys": [["c"] * 6],
        "decoy": None, "decoy_first": False,
    },
    {
        "name": "Dark Run",
        "budget": 21, "stall": 3, "hide": True,
        "nodes": [(0, C_PURPLE, 3, True), (1, C_GREEN, 3, True), (2, C_RED, 3, True),
                  (3, C_ORANGE, 3, True), (4, C_MAGENTA, 3, True), (5, C_BLUE, 3, True)],
        "runs": [[3, 0, 0, 4, 2, 5]],
        "keys": [["c"] * 6],
        "decoy": None, "decoy_first": False,
    },
    {
        "name": "Weights",
        "budget": 22, "stall": 3, "hide": True,
        # colourless stones: at this level the strip names them by size alone, and white
        # stones read as the same object as the white size-blob inside a strip marker
        "nodes": [(0, C_WHITE, 1, True), (1, C_WHITE, 4, True), (2, C_WHITE, 2, True),
                  (3, C_WHITE, 5, True), (4, C_WHITE, 3, True)],
        "runs": [[3, 0, 4, 1, 2, 0, 3]],
        "keys": [["s"] * 7],
        "decoy": None, "decoy_first": False,
    },
    {
        "name": "Two Runs",
        "budget": 24, "stall": 3, "hide": True,
        "nodes": [(0, C_RED, 2, True), (1, C_BLUE, 5, True), (2, C_GREEN, 1, True),
                  (3, C_MAGENTA, 4, True), (4, C_PURPLE, 3, True)],
        "runs": [[4, 1, 0, 3], [2, 0, 4, 1]],
        "keys": [["c", "s", "c", "s"], ["s", "c", "s", "c"]],
        "decoy": None, "decoy_first": False,
    },
    {
        "name": "Ghost Line",
        "budget": 22, "stall": 3, "hide": True,
        "nodes": [(0, C_GREEN, 3, True), (1, C_MAGENTA, 1, True), (2, C_BLUE, 4, True),
                  (3, C_PURPLE, 2, True), (4, C_RED, 5, True), (5, C_VDGRAY, 0, False)],
        "runs": [[2, 4, 0, 3, 1, 4, 2]],
        "keys": [["c", "s", "c", "s", "c", "c", "s"]],
        # names an orange stone; there is no orange stone on the ring.
        "decoy": [("c", C_GREEN), ("s", 5), ("c", C_BLUE), ("c", C_ORANGE),
                  ("s", 2), ("c", C_MAGENTA), ("s", 4)],
        "decoy_first": True,
    },
    {
        "name": "Full Cadence",
        "budget": 25, "stall": 3, "hide": True,
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
    The +1 keeps the largest stone clear of the outer pip ring at PIP_R[1]."""
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

    def _ring(self, frame, cx, cy, r, color):
        """Circle outline sampled by PIXEL DISTANCE -- a fixed sample count leaves a big
        radius dotted, which is the rendering gap that bit the earlier games."""
        n = max(8, int(4 * math.pi * r) + 1)
        for i in range(n):
            th = 2.0 * math.pi * i / n
            self._plot(frame, int(round(cx + r * math.cos(th))),
                       int(round(cy + r * math.sin(th))), color)

    # -- strip ------------------------------------------------------------

    def _marker(self, frame, x0, y0, spec, hidden):
        if hidden:
            frame[y0:y0 + CELL_H, x0:x0 + CELL_W] = C_VDGRAY
            return
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
        else:                                   # "sep" -- strike the lock itself
            frame[y0:y0 + CELL_H, x0:x0 + CELL_W] = C_YELLOW
            frame[y0 + 1:y0 + CELL_H - 1, x0 + 1:x0 + CELL_W - 1] = C_BLACK

    def _row(self, frame, y0, specs, hidden):
        span = len(specs) * CELL_PITCH - (CELL_PITCH - CELL_W)
        x = max(0, (64 - span) // 2)
        for spec in specs:
            self._marker(frame, x, y0, spec, hidden)
            x += CELL_PITCH

    # -- main -------------------------------------------------------------

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game
        # Palette note: this game keeps a black ground on purpose, and it is the one
        # exception to the project's move away from black-and-grey. kd01 uses all sixteen
        # palette entries -- six for the stones the player must name, plus five hub states --
        # so EVERY vivid background collides with something the player has to identify. A
        # purple ground was tried and made the purple stone invisible. Correctness wins.
        frame[:, :] = C_BLACK

        # Budget bar. Neutral colour: the hub carries the affordance, not the bar.
        span = BAR_X1 - BAR_X0
        frame[BAR_Y:BAR_Y + 2, BAR_X0:BAR_X1] = C_DGRAY
        if g.budget_max > 0 and g.budget_left > 0:
            filled = max(1, int(span * g.budget_left / g.budget_max))
            frame[BAR_Y:BAR_Y + 2, BAR_X0:BAR_X0 + filled] = C_LGRAY

        # Strip rows. Dark while the mechanism is armed on levels that hide it: you cannot
        # look the answer up again without first breaking your run.
        hidden = g.hide_when_armed and g.armed()
        for idx, specs in enumerate(g.strip_rows):
            self._row(frame, STRIP_Y[idx], specs, hidden)

        # The track the stones sit on, so the ring reads as one object even where empty.
        self._ring(frame, CX, CY, SLOT_R, C_VDGRAY)

        # Stones.
        for node in g.nodes:
            sx, sy = SLOT_POS[node["slot"]]
            r = node_radius(node)
            if node["alive"]:
                # no outline: at radius 2 an outline eats the whole stone, and the
                # background is black already, so nothing needs separating
                self._disc(frame, sx, sy, r, node["color"])
            else:                                # a ruin: hollow, unstrikeable, unnameable
                self._disc(frame, sx, sy, r, C_DGRAY)
                self._disc(frame, sx, sy, r - 2, C_BLACK)

        # The lock: one pip ring per run, one pip per required strike, filled with the
        # colour of the stone that filled it. This is the progress display -- without it
        # the rule would be undiscoverable.
        for r_i, run in enumerate(g.runs):
            radius = PIP_R[min(r_i, len(PIP_R) - 1)]
            self._ring(frame, CX, CY, radius, C_VDGRAY)
            k = len(run)
            done = g.filled[r_i]
            for i in range(k):
                # the outer ring is offset half a pip so the two rings never stack into
                # one radial bar and become unreadable
                th = -0.5 * math.pi + 2.0 * math.pi * (i + 0.5 * r_i) / k
                px = int(round(CX + radius * math.cos(th)))
                py = int(round(CY + radius * math.sin(th)))
                col = C_DGRAY
                if i < len(done):
                    col = g.nodes[done[i]]["color"]
                    if col == C_VDGRAY:
                        col = C_WHITE
                frame[py - 1:py + 2, px - 1:px + 2] = col

        # Hub -- colour as affordance, recomputed every step.
        if g.anim_kind == "stall":
            hub = C_MAROON
        elif g.anim_kind == "open":
            hub = C_WHITE
        elif g.latched:
            hub = C_YELLOW                       # same hue as the strip's separator marker
        elif g.armed():
            hub = C_LBLUE
        else:
            hub = C_GRAY
        self._disc(frame, CX, CY, HUB_R, hub)
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
        self.hide_when_armed = False
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
        self.hide_when_armed = ldef["hide"]
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
        """Actions a flawless run costs: every strike, plus one hub latch between runs."""
        return sum(len(r) for r in self.runs) + len(self.runs) - 1

    def node_at(self, x, y):
        for i, node in enumerate(self.nodes):
            sx, sy = SLOT_POS[node["slot"]]
            r = node_radius(node)
            if (x - sx) ** 2 + (y - sy) ** 2 <= r * r:
                return i
        return None

    def on_hub(self, x, y):
        return (x - CX) ** 2 + (y - CY) ** 2 <= HUB_CLICK_R ** 2

    def expected(self):
        """What the mechanism wants next: ('hub', None) or ('node', index)."""
        if self.latched:
            return ("hub", None)
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
        if ni is None and self.on_hub(x, y):
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
        # sees; the hub stays maroon until the next action clears it.
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
