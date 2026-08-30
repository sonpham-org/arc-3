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
"""Wheel -- clear the green arcs by striking when the sweeping bar crosses them.

ACTION5 waits one step. ACTION6 (click anywhere) strikes. Every action advances the
wheel one step, so the whole game is deterministic and fully predictable in advance.

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

WAIT_COST = 1
STRIKE_COST = 3

# ---------------------------------------------------------------------------
# Colours (ARC-3 palette indices)
# ---------------------------------------------------------------------------

C_WHITE, C_LGRAY, C_GRAY, C_DGRAY, C_VDGRAY, C_BLACK = 0, 1, 2, 3, 4, 5
C_MAGENTA, C_LMAGENTA, C_RED, C_BLUE, C_LBLUE = 6, 7, 8, 9, 10
C_YELLOW, C_ORANGE, C_MAROON, C_GREEN, C_PURPLE = 11, 12, 13, 14, 15

GREEN, RED = "green", "red"
ARC_COLOR = {GREEN: C_GREEN, RED: C_RED}

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
        "name": "First Strike",                 # NEW: strike when the bar crosses green
        "bar_speed": 1, "lives": 5, "budget": 40,
        "arcs": [(1, 15, 14, 0, GREEN)],
    },
    {
        # NEW: red arcs cost a life. Three greens rather than one, because with a single
        # target a blind striker hits it roughly one try in six and cleared this level
        # 1 time in 8. Needing three clean hits before three lives run out collapses that.
        "name": "Hot Metal",
        "bar_speed": 1, "lives": 3, "budget": 64,
        "arcs": [(1, 8, 5, 0, GREEN), (1, 24, 5, 0, GREEN), (1, 40, 5, 0, GREEN),
                 (2, 14, 9, 0, RED), (2, 30, 9, 0, RED)],
    },
    {
        "name": "Drift",                        # NEW: the arcs move too
        "bar_speed": 1, "lives": 3, "budget": 48,
        "arcs": [(1, 8, 9, -1, GREEN), (2, 30, 9, 0, RED)],
    },
    {
        "name": "Crosswind",                    # NEW: differing speeds and directions
        "bar_speed": 1, "lives": 3, "budget": 84,
        "arcs": [(0, 5, 8, 2, GREEN), (2, 25, 8, -1, GREEN), (1, 40, 8, 1, RED)],
    },
    {
        # NEW: every clear speeds the bar up, so later shots need a re-derived period.
        "name": "Wind Up",
        "bar_speed": 1, "lives": 3, "budget": 96, "speed_up": True,
        # bar walks 1 -> 2 -> 3, so both greens stay negative and can never match it
        "arcs": [(0, 6, 8, -2, GREEN), (1, 26, 8, -1, GREEN), (2, 46, 8, 0, RED)],
    },
    {
        # NEW: two greens sweep together, so one strike can take both -- and the budget
        # only closes if it does.
        "name": "Double Tap",
        "bar_speed": 1, "lives": 3, "budget": 72,
        "arcs": [(0, 20, 9, -1, GREEN), (2, 20, 9, -1, GREEN), (1, 45, 7, 0, RED)],
    },
    {
        # NEW: every clear reverses the bar's direction.
        "name": "Backlash",
        "bar_speed": 1, "lives": 3, "budget": 96, "reverse": True,
        # bar flips between +1 and -1, so greens use magnitude 2 and never match either
        "arcs": [(0, 8, 8, 2, GREEN), (1, 28, 8, -2, GREEN), (2, 48, 8, 1, RED)],
    },
    {
        "name": "Gauntlet",                     # everything at once, three rings
        "bar_speed": 1, "lives": 3, "budget": 130, "speed_up": True, "reverse": True,
        # bar reaches magnitudes 1..3 in both signs; greens are stationary or magnitude 4
        "arcs": [(0, 4, 7, 0, GREEN), (1, 22, 7, 4, GREEN), (2, 40, 7, -4, GREEN),
                 (1, 12, 6, 1, RED), (2, 52, 6, -3, RED)],
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
        frame[:, :] = C_BLACK

        # Faint guide rings, so the radii the arcs live on are visible even when empty.
        for r in RINGS:
            for s in range(STEPS * 2):
                x, y = self._polar(r, s / 2.0)
                self._plot(frame, x, y, C_VDGRAY)

        # Arcs. Drawn two pixels thick so a thin ring still reads as an object.
        for arc in g.arcs:
            color = ARC_COLOR[arc["kind"]]
            radius = RINGS[arc["ring"]]
            for i in range(arc["len"] * 3):
                step = arc["start"] + i / 3.0
                for dr in (-1, 0, 1):
                    x, y = self._polar(radius + dr, step)
                    self._plot(frame, x, y, color)

        # The sweeping bar.
        for i in range((BAR_OUTER - BAR_INNER) * 3):
            radius = BAR_INNER + i / 3.0
            x, y = self._polar(radius, g.bar_angle)
            self._plot(frame, x, y, C_WHITE)
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
        self.bar_speed = 1
        self.lives = 0
        self.lives_max = 0
        self.budget_max = 0
        self.budget_left = 0
        self.speed_up = False
        self.reverse = False
        self.greens_at_start = 0

        levels = [Level(sprites=[], grid_size=(64, 64), data=ldef, name=ldef["name"])
                  for ldef in LEVELS]

        super().__init__(
            "wh",
            levels,
            Camera(0, 0, 64, 64, C_BLACK, C_BLACK, [self.display]),
            False,
            len(levels),
            [5, 6],              # 5 = wait one step, 6 = strike (click anywhere)
        )

    # -- level setup --------------------------------------------------------

    def on_set_level(self, level: Level) -> None:
        ldef = LEVELS[self.level_index]
        self.arcs = [{"ring": r, "start": s, "len": ln, "speed": sp, "kind": k}
                     for (r, s, ln, sp, k) in ldef["arcs"]]
        self.bar_angle = 0
        self.bar_speed = ldef["bar_speed"]
        self.lives = self.lives_max = ldef["lives"]
        self.budget_max = self.budget_left = ldef["budget"]
        self.speed_up = ldef.get("speed_up", False)
        self.reverse = ldef.get("reverse", False)
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
        """Every action moves the wheel exactly one step. This is what replaces real time."""
        self.bar_angle = _norm(self.bar_angle + self.bar_speed)
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

        if greens and not reds:
            if self.speed_up:
                self.bar_speed += 1 if self.bar_speed > 0 else -1
            if self.reverse:
                self.bar_speed = -self.bar_speed

    # -- engine entry point -------------------------------------------------

    def step(self) -> None:
        aid = self.action.id.value

        if aid == 6:                                   # strike
            self.budget_left -= STRIKE_COST
            self._strike()
            self._advance()
        elif aid == 5:                                 # wait
            self.budget_left -= WAIT_COST
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
