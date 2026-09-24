# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Small synthetic ARC-3-like worlds for the rule discovery prototype's tests (written, NOT
#   run). 64 x 64 boards so the floor is a background component (object_events treats components
#   above BACKGROUND_AREA = 512 cells as background), with everything away from the border so the HUD
#   mask never triggers.
#     - MoverEnv: a 2x2 colour-3 piece moved by ACTION1-4 (up, down, left, right) one cell, blocked by
#       a colour-5 wall column and the edge; optional timer: a colour-7 bar grows one cell every Nth
#       press (the Ghost Twin / Locksmith pattern from round seven).
#     - ToggleEnv: a 3x3 colour-9 tile that a click toggles 9 <-> 8, plus a static colour-2 tile.
#     - feed(): the agent's perceive -> believe -> advance-history order without the policy, for
#       tests of fitting and beliefs.
# SRP/DRY check: Pass -- test fixtures only; uses the package's own Perceiver / ContextBuilder /
#   BeliefState in the same order as agent.RuleDiscoveryAgent.observe.
"""Synthetic worlds and a feeding loop for the tests."""
from __future__ import annotations

from typing import Optional

from rulediscovery1__fepInspired.beliefs import BeliefState
from rulediscovery1__fepInspired.perception import Action, Perceiver
from rulediscovery1__fepInspired.rules import ContextBuilder

H = W = 64
FLOOR, MOVER, WALL, BAR, TILE_A, TILE_B, STATIC = 0, 3, 5, 7, 9, 8, 2
BAR_Y, BAR_X = 44, 10
DIRS = {"ACTION1": (-1, 0), "ACTION2": (1, 0), "ACTION3": (0, -1), "ACTION4": (0, 1)}
RIGHT = Action("ACTION4")
LEFT = Action("ACTION3")
UP = Action("ACTION1")


def blank() -> list[list[int]]:
    return [[FLOOR] * W for _ in range(H)]


def put(g, y: int, x: int, h: int, w: int, c: int) -> None:
    for r in range(y, y + h):
        for k in range(x, x + w):
            g[r][k] = c


class MoverEnv:
    def __init__(self, y: int = 20, x: int = 20, wall_x: Optional[int] = None, timer_every: int = 0,
                 size: int = 2):
        self.y, self.x, self.wall_x, self.timer_every, self.size = y, x, wall_x, timer_every, size
        self.bar = 3
        self.presses = 0

    def board(self) -> list[list[int]]:
        g = blank()
        if self.wall_x is not None:
            for r in range(8, 56):
                g[r][self.wall_x] = WALL
        put(g, BAR_Y, BAR_X, 1, self.bar, BAR)
        put(g, self.y, self.x, self.size, self.size, MOVER)
        return g

    def blocked(self, ny: int, nx: int) -> bool:
        if ny < 4 or nx < 4 or ny + self.size > H - 4 or nx + self.size > W - 4:
            return True
        return self.wall_x is not None and nx <= self.wall_x < nx + self.size

    def step(self, a: Action):
        d = DIRS.get(a.name)
        if d is not None:
            ny, nx = self.y + d[0], self.x + d[1]
            if not self.blocked(ny, nx):
                self.y, self.x = ny, nx
        self.presses += 1
        if self.timer_every and self.presses % self.timer_every == 0:
            self.bar += 1
        return self.board(), False, False


class ToggleEnv:
    TILE = (30, 30)
    OTHER = (30, 40)

    def __init__(self):
        self.colour = TILE_A

    def board(self) -> list[list[int]]:
        g = blank()
        put(g, self.TILE[0], self.TILE[1], 3, 3, self.colour)
        put(g, self.OTHER[0], self.OTHER[1], 3, 3, STATIC)
        return g

    def click_tile(self) -> Action:
        return Action("ACTION6", self.TILE[0] + 1, self.TILE[1] + 1)

    def click_other(self) -> Action:
        return Action("ACTION6", self.OTHER[0] + 1, self.OTHER[1] + 1)

    def step(self, a: Action):
        if a.is_click and self.TILE[0] <= a.row < self.TILE[0] + 3 and self.TILE[1] <= a.col < self.TILE[1] + 3:
            self.colour = TILE_B if self.colour == TILE_A else TILE_A
        return self.board(), False, False


def feed(env, actions: list[Action], beliefs: Optional[BeliefState] = None):
    """Perceive -> believe -> advance history for each action (agent.observe order, no policy).
    Returns (beliefs, context builder, perceiver, transitions)."""
    p, ctx = Perceiver(), ContextBuilder()
    b = beliefs or BeliefState()
    p.begin(env.board())
    trs = []
    for a in actions:
        grid, lc, go = env.step(a)
        rc = ctx.context(p.current, a)
        tr = p.observe(a, grid, lc, go)
        b.observe(rc, tr)
        ctx.observe(tr)
        trs.append(tr)
    return b, ctx, p, trs


def mover_comp(scene):
    return next(c for c in scene.objects() if c.colour == MOVER)
