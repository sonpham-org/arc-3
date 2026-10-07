# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Debate pick 4 (docs 2026-09-24-warehouse-expert-debate.md, OpenMind #arc-3 22:49 ET): a Go-Explore-style
#   archive of OBJECT CONFIGURATIONS, per level (Ecoffet et al.: remember the cells you reached and how, return to the
#   rare ones, explore from there).
#     - Cell key: a coarse summary of the board without the agent itself and without clocks: the sorted (row, column,
#       shape) of every object that is not part of the controlled piece and does not lie entirely on "clock lines".
#       Colour is left out on purpose (a highlight that recolours an object does not make a new configuration); a moved,
#       carried, removed or reshaped object does. The controlled piece is the contingency self when that is on
#       (selfmodel.ContingentSelf), else the controlled instance with its common-fate / relational group.
#       Clock lines: rows / columns within `band` of the border that changed on at least `clock_share` of this level's
#       steps (a step bar that ticks every few actions, too slowly for the perceiver's HUD mask, would otherwise make
#       every step a new configuration; the same test as efe_trace_analysis.hud_mask with a lower share).
#     - Per cell: the shortest action path from the level start (the last RESET or level entry) that reached it, visits,
#       times chosen, failed returns.
#     - Return: when an attempt has gone `stagnation` steps without reaching a new cell, pick a cell other than the start
#       with probability proportional to 1/sqrt(1 + chosen) * 1/sqrt(1 + visits) (Go-Explore's count scores), press RESET
#       and replay its path (the "return by replay" variant for deterministic games; no simulator state is restored).
#       After the replay the reached cell is compared with the target (a miss is counted and the cell is dropped after two
#       misses); then the agent's normal policy explores from there.
#     - Hindsight: every reached configuration is kept as a practice goal: the return IS the attempt to reach it again, and
#       the arrival rate is recorded. (Only the return-by-replay form is built; no goal-conditioned policy is trained.)
#   Nothing here reads game internals: only the agent's boards, its own actions and its self estimate.
#   25-Sep-2026 stage one (Claude Opus 5.5 (Bubba)): the return start is its own method, start_return(max_len), so a RESET
#   the policy chose on budget grounds (budget.py, AgentConfig.use_budget) can become a return whose replay fits the
#   refilled budget; abandon() drops a replay in progress. Stagnation returns are unchanged.
# SRP/DRY check: Pass -- boards and components are perception.Scene's, the self estimate the ContextBuilder's. New: the
#   configuration key, the per-level archive and the replay return.
"""Go-Explore-style archive of object configurations with return by replay."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Optional

from .perception import BUTTONS, RESET, Action


@dataclass
class ArchiveConfig:
    stagnation: int = 40          # steps of an attempt without a new cell before a return starts
    max_path: int = 80            # cells whose path from the level start is longer are not returned to
    max_failed: int = 2
    band: int = 4                 # clock lines are looked for this close to the border
    clock_share: float = 0.2
    clock_min_steps: int = 10


@dataclass
class Cell:
    path: tuple                   # Actions from the level start
    visits: int = 0
    chosen: int = 0
    failed: int = 0


def self_ids(ctx, scene) -> set:
    """Component ids of the controlled piece on `scene` (contingency self, else controlled instance + group)."""
    sm = getattr(ctx, "selfm", None)
    if sm is not None:
        f = sm.frame(scene)
        return set(f.ids) if f is not None else set()
    rc = ctx.context(scene, Action(BUTTONS[0]))
    if rc.agent is None:
        return set()
    ids = {rc.agent.id}
    if rc.tl is not None:
        ids |= set(rc.tl.group.get(rc.agent.id, ()))
    if rc.fate:
        ids |= set(rc.fate.get(rc.agent.id, ()))
    return ids


def config_key(scene, exclude: set, clock_rows: frozenset = frozenset(), clock_cols: frozenset = frozenset()) -> tuple:
    def clock(c):
        return (all(y in clock_rows for y in range(c.y0, c.y1 + 1))
                or all(x in clock_cols for x in range(c.x0, c.x1 + 1)))
    return tuple(sorted((c.y0, c.x0, c.shape) for c in scene.objects() if c.id not in exclude and not clock(c)))


class GoExploreArchive:
    def __init__(self, cfg: Optional[ArchiveConfig] = None, seed: int = 0):
        self.cfg = cfg or ArchiveConfig()
        self.rng = random.Random(seed * 1009 + 101)
        self.level: Optional[int] = None
        self.cells: dict = {}
        self.path: list = []
        self.since_new = 0
        self.queue: list = []
        self.target: Optional[tuple] = None
        self.start_key: Optional[tuple] = None
        self.row_changes: dict = {}
        self.col_changes: dict = {}
        self.level_steps = 0
        # bookkeeping (reported by game_sweep)
        self.cells_per_level: list = []
        self.returns = 0
        self.arrived = 0
        self.missed = 0
        self.new_after_return = 0
        self.exploring_from = False

    def _new_level(self, level: int) -> None:
        if self.level is not None:
            self.cells_per_level.append(len(self.cells))
        self.level = level
        self.cells, self.path, self.since_new, self.queue, self.target = {}, [], 0, [], None
        self.start_key = None
        self.exploring_from = False
        self.row_changes, self.col_changes, self.level_steps = {}, {}, 0

    def begin(self, ctx, scene, level: int) -> None:
        self._new_level(level)
        self.start_key = self.key(ctx, scene)
        self.cells[self.start_key] = Cell(())

    def clocks(self) -> tuple:
        if self.level_steps < self.cfg.clock_min_steps:
            return frozenset(), frozenset()
        n = self.cfg.clock_share * self.level_steps
        return (frozenset(y for y, k in self.row_changes.items() if k >= n),
                frozenset(x for x, k in self.col_changes.items() if k >= n))

    def key(self, ctx, scene) -> tuple:
        return config_key(scene, self_ids(ctx, scene), *self.clocks())

    def _count_changes(self, pre, post) -> None:
        a, b = pre.comps.arr, post.comps.arr
        if a.shape != b.shape:
            return
        h, w = a.shape
        k = self.cfg.band
        diff = a != b
        self.level_steps += 1
        for y in list(range(min(k, h))) + list(range(max(h - k, k), h)):
            if diff[y].any():
                self.row_changes[y] = self.row_changes.get(y, 0) + 1
        for x in list(range(min(k, w))) + list(range(max(w - k, k), w)):
            if diff[:, x].any():
                self.col_changes[x] = self.col_changes.get(x, 0) + 1

    def total_cells(self) -> int:
        return sum(self.cells_per_level) + len(self.cells)

    # -- after every step
    def observe(self, ctx, tr, level: int) -> None:
        if tr.level_completed or level != self.level:
            self._new_level(level)
            if tr.post is not None:
                self.start_key = self.key(ctx, tr.post)
                self.cells[self.start_key] = Cell(())
            return
        if tr.post is None:
            return
        clocks0 = self.clocks()
        if not tr.reset and tr.pre is not None:
            self._count_changes(tr.pre, tr.post)
        if self.clocks() != clocks0:       # a clock line was found: re-key what can be re-keyed (the start), drop the rest
            self.cells, self.start_key = {}, None
        sm = getattr(ctx, "selfm", None)
        if sm is not None and sm.frame(tr.post) is None and not tr.reset:
            self.path.append(tr.action)          # the self is not known on this board: its key would hold the agent
            self.since_new += 1
            return
        key = self.key(ctx, tr.post)
        if tr.reset:
            self.path, self.since_new = [], 0
            if not self.queue:
                self.target = None
            self.start_key = key
            self.cells.setdefault(key, Cell(()))
            return
        if self.start_key is None:          # the keys were just redefined: this attempt's start is not known, use now
            self.start_key = key
        self.path.append(tr.action)
        c = self.cells.get(key)
        if c is None:
            self.cells[key] = Cell(tuple(self.path))
            self.since_new = 0
            if self.exploring_from:
                self.new_after_return += 1
        else:
            c.visits += 1
            if len(self.path) < len(c.path):
                c.path = tuple(self.path)
            self.since_new += 1
        if self.target is not None and not self.queue:
            if key == self.target:
                self.arrived += 1
            else:
                self.missed += 1
                t = self.cells.get(self.target)
                if t is not None:
                    t.failed += 1
            self.target = None
            self.exploring_from = True

    # -- before an action
    def next_action(self, valid: list) -> Optional[Action]:
        if self.queue:
            a = self.queue.pop(0)
            if a.name != RESET and a.name not in valid:
                self.queue, self.target = [], None          # the replay cannot be played here: give it up
                return None
            return a
        if self.since_new < self.cfg.stagnation or RESET not in valid:
            return None
        return self.start_return()

    def start_return(self, max_len: Optional[int] = None) -> Optional[Action]:
        """RESET + a replay queued to a rare cell whose path is at most max_len (default cfg.max_path) long, or None.
        Called by next_action on stagnation, and (stage one, AgentConfig.use_budget) when the policy chose RESET."""
        lim = self.cfg.max_path if max_len is None else min(max_len, self.cfg.max_path)
        cands = [(k, c) for k, c in self.cells.items() if k != self.start_key and 0 < len(c.path) <= lim
                 and c.failed < self.cfg.max_failed]
        self.since_new = 0
        if not cands:
            return None
        w = [1.0 / math.sqrt(1 + c.chosen) / math.sqrt(1 + c.visits) for _, c in cands]
        k, c = self.rng.choices(cands, weights=w, k=1)[0]
        c.chosen += 1
        self.returns += 1
        self.queue = list(c.path)
        self.target = k
        self.exploring_from = False
        return Action(RESET)

    def abandon(self) -> None:
        """Drop a replay in progress (the budget needs the step); the target counts as neither reached nor missed."""
        self.queue, self.target = [], None
