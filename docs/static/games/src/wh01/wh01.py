# Author: Claude Opus 5
# Date: 2026-08-27 01:10
# PURPOSE: wh01 "Wheel" -- an ARC-AGI-3 environment. A bar sweeps around the centre while
#   coloured arcs orbit at several radii, each with its own length, speed and direction.
#   Striking while the bar overlaps green arcs clears them; striking red, or empty space,
#   costs a life. Turn-based: every action advances the wheel exactly one step, so timing
#   becomes PREDICTION (where will the bar be in N steps) rather than reflex, which the
#   benchmark bans. Core-knowledge priors only: geometry and agentness, no text or glyphs.
#   Implements the arcengine ARCBaseGame contract; consumed by the Pyodide browser player,
#   the CLI agent, and the duck-harness bundle.
# SRP/DRY check: Pass -- self-contained environment. Only 4 of ~300 catalogued games use
#   polar geometry at all and none is a rotational-alignment game, so nothing to reuse.
"""Wheel -- line the bar up with the green arcs and strike.

LEFT / RIGHT turn the bar one step. Clicking strikes whatever the bar currently crosses.
Every action also advances the orbiting arcs one step, so the targets keep moving while
you aim: you are intercepting, not waiting.

8 levels. No RNG. Lose by running out of lives or budget.
"""

import math

import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

# ---------------------------------------------------------------------------
# Geometry -- angles are integer steps so alignment is exact, never a float compare
# ---------------------------------------------------------------------------

STEPS = 60                   # angular resolution of the whole wheel (6 degrees per step)
CX, CY = 32, 38              # wheel centre (pushed down; HUD occupies the top rows)
RINGS = (11, 16, 21)         # radii the arcs may occupy
BAR_INNER, BAR_OUTER = 3, 24 # the sweeping bar spans these radii

TURN_COST = 1
STRIKE_COST = 3

# ---------------------------------------------------------------------------
# Colours (ARC-3 palette indices)
# ---------------------------------------------------------------------------

C_WHITE, C_LGRAY, C_GRAY, C_DGRAY, C_VDGRAY, C_BLACK = 0, 1, 2, 3, 4, 5
C_MAGENTA, C_LMAGENTA, C_RED, C_BLUE, C_LBLUE = 6, 7, 8, 9, 10
C_YELLOW, C_ORANGE, C_MAROON, C_GREEN, C_PURPLE = 11, 12, 13, 14, 15

GREEN, RED = "green", "red"
# The two arc kinds are drawn green and ORANGE, not green and red. Two reasons: the field is
# maroon (see C_FIELD) and red-on-maroon is the one pairing that loses contrast, and ARC
# forbids leaning on cultural convention, so "red means bad" was never carrying meaning
# anyway -- the player learns which kind hurts by striking one.
ARC_COLOR = {GREEN: C_GREEN, RED: C_ORANGE}

# Palette choice: measured across all 773 catalogued games, greyscale is 60.3% of every
# pixel and this game was 84% pure black. Maroon and purple are the only genuinely dark
# entries in the ARC-3 palette, and maroon is 0.0% of official pixels -- so a maroon field
# with purple guide rings is both legible and unlike anything in the corpus.
C_FIELD = C_MAROON
C_RING = C_PURPLE

HUD_BAR_Y, HUD_BAR_X0, HUD_BAR_X1 = 0, 1, 63
LIFE_Y, LIFE_X = 3, 2

# ---------------------------------------------------------------------------
# Levels. Each arc is (ring_index, start_step, length_steps, speed, kind).
# speed is angular steps per tick, signed; 0 means the arc is stationary.
#
# TRAP: a green arc whose speed EQUALS the bar's rotates in lockstep with it and can never
# be struck -- the relative angle never changes. This must hold for EVERY bar speed the
# level can reach, not just the starting one: speed_up walks the bar through 1,2,3... and
# reverse flips its sign, so a green that is safe at the start can become unreachable
# after the first clear. Greens here keep signs/magnitudes the bar never takes.
# Reds may match (an unreachable red is merely inert, not unfair).
# ---------------------------------------------------------------------------

LEVELS = [
    {
        "name": "First Turn",                   # NEW: turn the bar, strike the green
        "lives": 5, "budget": 40,
        "arcs": [(1, 15, 12, 0, GREEN)],
    },
    {
        # NEW: red arcs cost a life. Three greens rather than one: with a single target a
        # blind striker hits it roughly one try in six, which is not a measurement.
        "name": "Hot Metal",
        "lives": 4, "budget": 60,
        "arcs": [(1, 6, 5, 0, GREEN), (1, 22, 5, 0, GREEN), (1, 38, 5, 0, GREEN),
                 (1, 13, 6, 0, RED), (1, 29, 6, 0, RED)],
    },
    {
        "name": "Drift",                        # NEW: the arcs orbit while you aim
        "lives": 3, "budget": 60,
        "arcs": [(1, 8, 7, 1, GREEN), (1, 30, 7, 1, GREEN), (1, 48, 7, 1, RED)],
    },
    {
        "name": "Two Rings",                    # NEW: a second radius, opposing directions
        "lives": 3, "budget": 76,
        "arcs": [(0, 5, 6, 1, GREEN), (2, 25, 6, -1, GREEN), (0, 33, 6, -1, GREEN),
                 (2, 47, 7, 1, RED)],
    },
    {
        # NEW: two greens hold the same angle on different rings, so one strike takes both
        # -- and the budget only closes if it does.
        # A third green off the shared angle: with only the aligned pair, one lucky strike
        # cleared the whole level and random play won ~1 in 36. Needing a second, separate
        # hit takes it to zero.
        # Two lives, not three: by this level the rule is known and aiming is deliberate,
        # so a human rarely mis-strikes, while blind striking dies twice as fast. Greens
        # are also narrowed and red coverage widened.
        # A fourth green and a fourth red. Measured at ~1/250 with three greens and two
        # lives: the aligned pair is one wide target, so a single lucky strike still bought
        # two thirds of the level. Needing three separate hits, against more red coverage,
        # is what closes it -- more required hits beats a tighter budget every time here.
        "name": "Double Tap",
        "lives": 2, "budget": 72,
        "arcs": [(0, 20, 4, -1, GREEN), (2, 20, 4, -1, GREEN), (1, 33, 3, 2, GREEN),
                 (0, 47, 3, -2, GREEN),
                 (1, 40, 11, 0, RED), (1, 6, 11, 0, RED), (0, 44, 9, 0, RED),
                 (2, 38, 10, 1, RED), (2, 4, 8, -1, RED)],
    },
    {
        # Third red added: with two, blind striking survived long enough to win ~1 in 181.
        "name": "Three Rings",                  # NEW: the third radius joins in
        "lives": 2, "budget": 96,
        "arcs": [(0, 4, 5, 2, GREEN), (1, 20, 5, -1, GREEN), (2, 36, 5, 1, GREEN),
                 (0, 28, 8, -2, RED), (2, 52, 8, -1, RED), (1, 44, 8, 1, RED)],
    },
    {
        # NEW: reds sit immediately beside greens, so the bar must land in a narrow window
        # rather than anywhere on the arc.
        "name": "Needle",
        "lives": 3, "budget": 96,
        "arcs": [(0, 10, 4, 1, GREEN), (1, 26, 4, -1, GREEN), (2, 42, 4, 1, GREEN),
                 (0, 15, 8, 1, RED), (1, 31, 8, -1, RED), (2, 47, 8, 1, RED)],
    },
    {
        # Two lives, not three, and a fourth red. This level had never actually been
        # measured -- the broken detector reported it 0/2000 while detecting nothing,
        # because the last level calls win() instead of advancing level_index. Its first
        # real measurement was ~1/500.
        "name": "Gauntlet",                     # five greens, four reds, all three rings
        "lives": 2, "budget": 140,
        "arcs": [(0, 3, 5, 2, GREEN), (0, 30, 5, 2, GREEN), (1, 17, 5, -1, GREEN),
                 (2, 33, 5, 3, GREEN), (2, 50, 5, 3, GREEN),
                 (1, 40, 7, 1, RED), (2, 10, 7, -2, RED), (0, 45, 6, -3, RED),
                 (1, 5, 8, 2, RED)],
    },
]


def _norm(step):
    return step % STEPS


def _covers(start, length, angle):
    """True if the arc starting at `start` spanning `length` steps covers `angle`."""
    return _norm(angle - start) < length


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

class Wh01Display(RenderableUserDisplay):
    def __init__(self, game):
        self.game = game

    @staticmethod
    def _polar(radius, step):
        theta = 2.0 * math.pi * step / STEPS
        return int(round(CX + radius * math.cos(theta))), int(round(CY + radius * math.sin(theta)))

    def _plot(self, frame, x, y, color):
        if 0 <= x < 64 and 0 <= y < 64:
            frame[y, x] = color

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        g = self.game
        frame[:, :] = C_FIELD

        # Sampling has to scale with radius or the curve comes out dotted: an outer ring is
        # ~132 px around, so a fixed sample count leaves visible gaps. Two samples per
        # pixel of arc length keeps every stroke solid.
        def samples_for(radius, span_steps):
            return max(2, int(2 * 2 * math.pi * radius * span_steps / STEPS) + 1)

        # Faint guide rings, so the radii the arcs live on are visible even when empty.
        for r in RINGS:
            n = samples_for(r, STEPS)
            for s in range(n):
                x, y = self._polar(r, STEPS * s / n)
                self._plot(frame, x, y, C_RING)

        # Arcs, three pixels thick so a thin ring still reads as a solid object.
        for arc in g.arcs:
            color = ARC_COLOR[arc["kind"]]
            radius = RINGS[arc["ring"]]
            n = samples_for(radius + 1, arc["len"])
            for i in range(n + 1):
                step = arc["start"] + arc["len"] * i / n
                for dr in (-1, 0, 1):
                    x, y = self._polar(radius + dr, step)
                    self._plot(frame, x, y, color)

        # The bar the player turns.
        n = (BAR_OUTER - BAR_INNER) * 3
        for i in range(n + 1):
            radius = BAR_INNER + (BAR_OUTER - BAR_INNER) * i / n
            x, y = self._polar(radius, g.bar_angle)
            self._plot(frame, x, y, C_WHITE)
            # widen the tip so the aiming end is unmistakable
            if radius > BAR_OUTER - 4:
                self._plot(frame, x + 1, y, C_WHITE)
                self._plot(frame, x, y + 1, C_WHITE)
        # Hub: recoloured by what the bar is currently over -- colour as affordance, and
        # the one cue that makes "strike now" learnable without being told.
        hub = C_LGRAY
        if g._reds_under_bar():
            hub = C_RED
        elif g._greens_under_bar():
            hub = C_GREEN
        frame[CY - 1:CY + 2, CX - 1:CX + 2] = hub

        # HUD: budget bar.
        span = HUD_BAR_X1 - HUD_BAR_X0
        filled = 0 if g.budget_max <= 0 else int(span * g.budget_left / g.budget_max)
        frame[HUD_BAR_Y:HUD_BAR_Y + 2, HUD_BAR_X0:HUD_BAR_X1] = C_DGRAY
        if filled > 0:
            frame[HUD_BAR_Y:HUD_BAR_Y + 2, HUD_BAR_X0:HUD_BAR_X0 + filled] = (
                C_GREEN if g.budget_left * 4 > g.budget_max else C_ORANGE)

        # HUD: lives as pips, and remaining greens as pips on the right.
        for i in range(g.lives_max):
            x = LIFE_X + i * 4
            if x + 2 < 64:
                frame[LIFE_Y:LIFE_Y + 3, x:x + 3] = C_RED if i < g.lives else C_VDGRAY
        remaining = len(g._greens())
        for i in range(g.greens_at_start):
            x = 63 - (i + 1) * 4
            if x >= 0:
                frame[LIFE_Y:LIFE_Y + 3, x:x + 3] = C_VDGRAY if i < remaining else C_GREEN
        return frame


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class Wh01(ARCBaseGame):
    def __init__(self):
        self.display = Wh01Display(self)

        # on_set_level() runs inside super().__init__(), so these must all exist first.
        self.arcs = []
        self.bar_angle = 0
        self.lives = 0
        self.lives_max = 0
        self.budget_max = 0
        self.budget_left = 0
        self.greens_at_start = 0

        levels = [Level(sprites=[], grid_size=(64, 64), data=ldef, name=ldef["name"])
                  for ldef in LEVELS]

        super().__init__(
            "wh",
            levels,
            Camera(0, 0, 64, 64, C_FIELD, C_FIELD, [self.display]),
            False,
            len(levels),
            [3, 4, 6],           # 3/4 = turn the bar, 6 = strike (click anywhere)
        )

    # -- level setup --------------------------------------------------------

    def on_set_level(self, level: Level) -> None:
        ldef = LEVELS[self.level_index]
        self.arcs = [{"ring": r, "start": s, "len": ln, "speed": sp, "kind": k}
                     for (r, s, ln, sp, k) in ldef["arcs"]]
        self.bar_angle = 0
        self.lives = self.lives_max = ldef["lives"]
        self.budget_max = self.budget_left = ldef["budget"]
        self.greens_at_start = sum(1 for a in self.arcs if a["kind"] == GREEN)

    # -- queries ------------------------------------------------------------

    def _greens(self):
        return [a for a in self.arcs if a["kind"] == GREEN]

    def _under_bar(self, kind):
        return [a for a in self.arcs
                if a["kind"] == kind and _covers(a["start"], a["len"], self.bar_angle)]

    def _greens_under_bar(self):
        return self._under_bar(GREEN)

    def _reds_under_bar(self):
        return self._under_bar(RED)

    # -- simulation ---------------------------------------------------------

    def _advance(self):
        """The arcs orbit one step per action. The bar only moves when the player turns it,
        so the world keeps moving while you aim -- interception, not waiting."""
        for arc in self.arcs:
            arc["start"] = _norm(arc["start"] + arc["speed"])

    def _strike(self):
        greens = self._greens_under_bar()
        reds = self._reds_under_bar()
        for arc in greens:
            self.arcs.remove(arc)
        # Any mis-strike costs a life: a red under the bar, or nothing under it at all.
        if reds or not greens:
            self.lives -= 1

    # -- engine entry point -------------------------------------------------

    def step(self) -> None:
        aid = self.action.id.value

        if aid == 6:                                   # strike whatever the bar crosses
            self.budget_left -= STRIKE_COST
            self._strike()
            self._advance()
        elif aid == 3:                                 # turn the bar anticlockwise
            self.budget_left -= TURN_COST
            self.bar_angle = _norm(self.bar_angle - 1)
            self._advance()
        elif aid == 4:                                 # turn the bar clockwise
            self.budget_left -= TURN_COST
            self.bar_angle = _norm(self.bar_angle + 1)
            self._advance()

        if not self._greens():
            self.next_level()
            self.complete_action()
            return

        if self.lives <= 0 or self.budget_left <= 0:
            self.lives = max(0, self.lives)
            self.budget_left = max(0, self.budget_left)
            self.lose()

        self.complete_action()
