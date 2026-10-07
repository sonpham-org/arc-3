# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026 (debate four and five 25-September-2026)
# PURPOSE: Goal inference and preferences for the rule discovery prototype (OpenMind, #arc-3,
#   23-Sep-2026 21:03 ET). In active-inference terms: beliefs about the hidden goal (a slow-timescale
#   state) and the prior preferences C over outcomes that give the pragmatic term of expected free
#   energy.
#     - Goal templates over colours (not positions, so a goal carries to the next level's layout):
#       ReachGoal (an object of colour a touches one of colour b), MatchGoal (the shapes shown in
#       colour a equal those in colour b), FillGoal (colour a's cells get converted away), EmptyGoal
#       (colour a's objects are removed), AlignGoal (objects of colours a and b share a row or
#       column), CountGoal (exactly k objects of colour a). Each has progress(scene) in [0, 1]
#       (1 = satisfied) and a description length for an Occam prior.
#     - GoalBeliefs: log posterior per goal. On a level clear: likelihood eps + (1 - eps) p^kappa where
#       p is the goal's progress on the board the clearing action was taken on (or on the board the
#       MAP rule set imagines after it, whichever is higher): a goal that was one action from done
#       explains the clear. On an ordinary step whose resulting board SATISFIES a goal without a
#       clear: likelihood `false_alarm` (strong evidence against it). Carried across levels within a
#       play (slow memory); new goals appearing on a new level enter at the median evidence so far.
#     - Preferences: log preference ln C(o) over outcome labels: level_clear high, game_over low,
#       outcomes that preceded a game over penalised, plus an online version of
#       heldout_yardstick.clear_table (p(clear within k steps | outcome), shrunk to the base rate) as
#       a learned relative preference; pragmatic(dist, goal gain) = E[ln C] + expected goal progress.
#   Round-four evidence says the label-only pragmatic signal is weak (within-play AUC 0.59, no
#   transfer across games); the goal-progress term is the new, untested part.
#   Not run yet: only py_compile was used.
#   24-Sep-2026 debate pick 5 (OpenMind 22:49 ET; Claude Opus 5.5 (Bubba)): GoalBeliefs(contrast=True) keeps the level's
#   boards (thinned to max_boards) and, on a clear, adds contrast evidence per goal:
#     contrast_w * ln[(eps + p_win^kappa) / (eps + mean over the level's other boards of p^kappa)]
#   so a goal that is distinctive of the clearing board gains and one that held all along does not. Off by default.
#   25-Sep-2026 debate four, pick 2 (docs 2026-09-25-warehouse-expert-debate-4.md, OpenMind #arc-3 11:24 ET; Claude Opus 5.5
#   (Bubba)), both off by default: soft_reach=True: a goal whose resulting board satisfies it without a clear loses
#   ln(soft_fa) once per stretch of being satisfied (not on every step), and its total such loss is floored at ln(fa_floor)
#   (reaching it weakens it, never kills it; the Warehouse target is fully covered one step before the win). With
#   track_prog the scored step's progress per goal is kept in last_prog (babble.CausedChange / GoalBabbler read it).
#   caused (a babble.CausedChange, set by the agent under caused_contrast): on a clear, a goal's progress on the clearing
#   board is multiplied by its action-caused share before both the clear likelihood and the contrast use it, so a goal
#   whose progress changes whatever the agent does (a step bar, a clock) cannot explain the clear.
#   25-Sep-2026 debate five, pick 2 (docs 2026-09-25-openmind-agent-expert-debate-5.md, OpenMind #arc-3 17:14 ET; Claude
#   Opus 5.5 (Bubba)), off by default: Preferences(flat_until_clear=True): until the play's first clear every ordinary
#   outcome's log preference is 0 (the learned "p(clear soon | outcome) / base rate" is uninformative with no clear and
#   priced the most common outcome as the least wanted); the fixed clear / game-over preferences, the game-over aversion
#   (c_avoid on outcomes seen before a game over) and the budget term (policy.py, c_game_over) stay. After the first clear
#   log_pref is the learned one, from counts kept all along. The goal-progress half of pragmatic() is unchanged.
# SRP/DRY check: Pass -- box gap from feature_detectors.gap, clear-window length from heldout_yardstick
#   (PRAG_K); the online clear table re-states hy.clear_table's estimator incrementally (hy's version
#   needs whole training traces, not usable online). Goal templates are new.
"""Goal hypotheses (reach, match, fill, empty, align, count) and preferences C."""
from __future__ import annotations

import math
import statistics
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import ClassVar, Optional

from ._distill import fd, hy
from .perception import Scene, Transition


# ---------------------------------------------------------------- level baseline

@dataclass
class LevelBaseline:
    """Counts on the level's first board (Fill / Empty progress is relative to them)."""
    cells: dict = field(default_factory=dict)
    objs: dict = field(default_factory=dict)

    @staticmethod
    def of(scene: Scene) -> "LevelBaseline":
        cells, objs = Counter(), Counter()
        for c in scene.objects():
            cells[c.colour] += c.size
            objs[c.colour] += 1
        return LevelBaseline(dict(cells), dict(objs))


def _box(c) -> tuple:
    return (c.y0, c.x0, c.y1, c.x1)


def _centre(c) -> tuple[float, float]:
    return ((c.y0 + c.y1) / 2.0, (c.x0 + c.x1) / 2.0)


# ---------------------------------------------------------------- goal templates

class Goal:
    template: ClassVar[str] = "goal"

    def progress(self, scene: Scene, base: LevelBaseline) -> float:
        raise NotImplementedError

    def description_length(self) -> float:
        raise NotImplementedError

    def key(self) -> tuple:
        return (self.template,) + tuple(vars(self).values())

    def describe(self) -> str:
        return repr(self)


LN16 = math.log(16)


@dataclass(frozen=True)
class ReachGoal(Goal):
    template: ClassVar[str] = "reach"
    a: int
    b: int

    def progress(self, scene, base):
        A, B = scene.colour_objects(self.a), scene.colour_objects(self.b)
        if not A or not B:
            return 0.0
        g = min(fd.gap(_box(x), _box(y)) for x in A for y in B)
        return 1.0 / (1.0 + g)

    def description_length(self):
        return math.log(6) + 2 * LN16

    def describe(self):
        return f"get colour {self.a} to touch colour {self.b}"


@dataclass(frozen=True)
class MatchGoal(Goal):
    template: ClassVar[str] = "match"
    a: int
    b: int

    def progress(self, scene, base):
        sa = {c.shape for c in scene.colour_objects(self.a)}
        sb = {c.shape for c in scene.colour_objects(self.b)}
        if not sa or not sb:
            return 0.0
        return len(sa & sb) / len(sa | sb)

    def description_length(self):
        return math.log(6) + 2 * LN16

    def describe(self):
        return f"make the colour-{self.a} shapes match the colour-{self.b} shapes"


@dataclass(frozen=True)
class FillGoal(Goal):
    template: ClassVar[str] = "fill"
    a: int

    def progress(self, scene, base):
        n0 = base.cells.get(self.a, 0)
        if n0 == 0:
            return 0.0
        return 1.0 - min(scene.colour_cells(self.a), n0) / n0

    def description_length(self):
        return math.log(6) + LN16

    def describe(self):
        return f"convert every colour-{self.a} cell"


@dataclass(frozen=True)
class EmptyGoal(Goal):
    template: ClassVar[str] = "empty"
    a: int

    def progress(self, scene, base):
        n0 = base.objs.get(self.a, 0)
        if n0 == 0:
            return 0.0
        return 1.0 - min(len(scene.colour_objects(self.a)), n0) / n0

    def description_length(self):
        return math.log(6) + LN16

    def describe(self):
        return f"remove every colour-{self.a} object"


@dataclass(frozen=True)
class AlignGoal(Goal):
    template: ClassVar[str] = "align"
    a: int
    b: int

    def progress(self, scene, base):
        A, B = scene.colour_objects(self.a), scene.colour_objects(self.b)
        if not A or not B:
            return 0.0
        d = min(min(abs(_centre(x)[0] - _centre(y)[0]), abs(_centre(x)[1] - _centre(y)[1])) for x in A for y in B)
        return 1.0 / (1.0 + d)

    def description_length(self):
        return math.log(6) + 2 * LN16

    def describe(self):
        return f"line colour {self.a} up with colour {self.b}"


@dataclass(frozen=True)
class CountGoal(Goal):
    template: ClassVar[str] = "count"
    a: int
    k: int

    def progress(self, scene, base):
        return 1.0 / (1.0 + abs(len(scene.colour_objects(self.a)) - self.k))

    def description_length(self):
        return math.log(6) + LN16 + (2 * math.floor(math.log2(self.k + 1)) + 1) * math.log(2)

    def describe(self):
        return f"leave exactly {self.k} colour-{self.a} objects"


def enumerate_goals(scene: Scene, max_colours: int = 10) -> list[Goal]:
    """Every goal template instantiated on the colours of this board (pairs ordered)."""
    cols = scene.colours()[:max_colours]
    base = LevelBaseline.of(scene)
    out: list[Goal] = []
    for a in cols:
        out += [FillGoal(a), EmptyGoal(a), CountGoal(a, 1)]
        if base.objs.get(a, 0) > 1:
            out.append(CountGoal(a, base.objs[a] - 1))
        for b in cols:
            if a != b:
                out += [ReachGoal(a, b), AlignGoal(a, b)]
                if a < b:
                    out.append(MatchGoal(a, b))
    return out


# ---------------------------------------------------------------- beliefs over goals

class GoalBeliefs:
    """Posterior over goal hypotheses, carried across the levels of one play."""

    def __init__(self, eps_clear: float = 0.05, false_alarm: float = 0.1, kappa: float = 2.0,
                 satisfied: float = 0.999, contrast: bool = False, contrast_w: float = 1.0, max_boards: int = 64,
                 soft_reach: bool = False, soft_fa: float = 0.5, fa_floor: float = 0.05, track_prog: bool = False):
        self.eps_clear, self.false_alarm, self.kappa, self.satisfied = eps_clear, false_alarm, kappa, satisfied
        self.goals: dict = {}                  # key -> Goal
        self.loglik: dict = {}                 # key -> accumulated log likelihood
        self.base = LevelBaseline()
        self.n_clears = 0
        # debate pick 5 (24-Sep-2026): goals from contrast. The boards of the current level (thinned to max_boards) are
        # the "rest" the clearing board is contrasted with.
        self.contrast, self.contrast_w, self.max_boards = contrast, contrast_w, max_boards
        self.boards: list = []
        self.board_level: Optional[int] = None
        self._thin = 1
        self._seen = 0
        self.contrast_log: list = []           # (clear number, top goal after the contrast update, its mass)
        # debate four pick 2: soft reach (see the header), per-step progress, caused-change weighting of contrast
        self.soft_reach, self.soft_fa, self.fa_floor = soft_reach, soft_fa, fa_floor
        self.track_prog = track_prog or soft_reach
        self.sat: set = set()                  # goals satisfied on the previous scored board (soft reach)
        self.fa_loss: dict = {}                # goal key -> total soft false-alarm loss so far (<= 0)
        self.last_prog: Optional[dict] = None  # goal key -> progress on the last scored step's board
        self.caused = None                     # babble.CausedChange (AgentConfig.caused_contrast)

    def bind_level(self, scene: Scene) -> None:
        """New level: new baseline; goals for colours not seen before join at the median evidence."""
        self.base = LevelBaseline.of(scene)
        self.sat = set()
        if self.contrast and scene.level != self.board_level:
            self.boards, self.board_level, self._thin, self._seen = [], scene.level, 1, 0
        start = statistics.median(self.loglik.values()) if self.loglik else 0.0
        for g in enumerate_goals(scene):
            k = g.key()
            if k not in self.goals:
                self.goals[k] = g
                self.loglik[k] = start

    def log_post(self) -> dict:
        return {k: -g.description_length() + self.loglik[k] for k, g in self.goals.items()}

    def posterior(self) -> dict:
        lp = self.log_post()
        if not lp:
            return {}
        m = max(lp.values())
        e = {k: math.exp(v - m) for k, v in lp.items()}
        z = sum(e.values())
        return {k: v / z for k, v in e.items()}

    def top(self, n: int = 3) -> list[tuple[Goal, float]]:
        post = self.posterior()
        return [(self.goals[k], p) for k, p in sorted(post.items(), key=lambda t: -t[1])[:n]]

    def entropy(self) -> float:
        return -sum(p * math.log(p) for p in self.posterior().values() if p > 0)

    def observe(self, tr: Transition, imagined: Optional[Scene] = None) -> None:
        """imagined: the MAP rule set's predicted board after tr.action on tr.pre (for clears the real
        post board belongs to the next level, so this is the best guess of the winning board)."""
        self.last_prog = None
        if tr.reset or not self.goals:
            return
        if tr.level_completed:
            self.n_clears += 1
            rest = self.boards
            for k, g in self.goals.items():
                p = g.progress(tr.pre, self.base)
                if imagined is not None:
                    p = max(p, g.progress(imagined, self.base))
                if self.caused is not None:           # debate four pick 2: only the action-caused part of the progress
                    p *= self.caused.share(k)
                self.loglik[k] += math.log(self.eps_clear + (1 - self.eps_clear) * p ** self.kappa)
                if self.contrast and rest:
                    # contrast: how much more the clearing board satisfies g than the level's other boards did
                    # (a goal that holds all the time explains nothing about the clear)
                    typical = sum(g.progress(b, self.base) ** self.kappa for b in rest) / len(rest)
                    self.loglik[k] += self.contrast_w * math.log((self.eps_clear + p ** self.kappa)
                                                                 / (self.eps_clear + typical))
            if self.contrast:
                top = self.top_goal()
                if top is not None:
                    self.contrast_log.append((self.n_clears, top[0].describe(), round(top[1], 3)))
            return
        if self.contrast and tr.scored and tr.post is not None:
            self._seen += 1
            if self._seen % self._thin == 0:
                self.boards.append(tr.post)
                if len(self.boards) > self.max_boards:          # keep every other board, sample half as often
                    self.boards = self.boards[::2]
                    self._thin *= 2
        if tr.scored and tr.post is not None and self.track_prog:
            self.last_prog = {k: g.progress(tr.post, self.base) for k, g in self.goals.items()}
            for k, p in self.last_prog.items():
                if p < self.satisfied:
                    self.sat.discard(k)
                elif not self.soft_reach:
                    self.loglik[k] += math.log(self.false_alarm)
                elif k not in self.sat:               # debate four: once per stretch, floored (weakens, never kills)
                    lost = self.fa_loss.get(k, 0.0)
                    step = max(math.log(self.soft_fa), math.log(self.fa_floor) - lost)
                    self.loglik[k] += min(step, 0.0)
                    self.fa_loss[k] = lost + min(step, 0.0)
                    self.sat.add(k)
        elif tr.scored and tr.post is not None:
            for k, g in self.goals.items():
                if g.progress(tr.post, self.base) >= self.satisfied:
                    self.loglik[k] += math.log(self.false_alarm)

    def expected_gain(self, now: Scene, nxt: Scene) -> float:
        """Posterior-expected progress change from `now` to `nxt`."""
        return sum(p * (self.goals[k].progress(nxt, self.base) - self.goals[k].progress(now, self.base))
                   for k, p in self.posterior().items())

    def top_goal(self) -> Optional[tuple[Goal, float]]:
        t = self.top(1)
        return t[0] if t else None


# ---------------------------------------------------------------- preferences C

class Preferences:
    """ln C(o): what outcomes the agent prefers (pragmatic value = expected ln C)."""

    def __init__(self, c_clear: float = 3.0, c_game_over: float = -6.0, c_avoid: float = -2.0,
                 k: int = hy.PRAG_K, prior_n: float = 5.0, flat_until_clear: bool = False):
        self.c_clear, self.c_game_over, self.c_avoid = c_clear, c_game_over, c_avoid
        self.k, self.prior_n = k, prior_n
        self.recent: deque = deque(maxlen=k)
        self.hits: Counter = Counter()
        self.n: Counter = Counter()
        self.avoid: Counter = Counter()
        # debate five pick 2: before the play's first clear the learned relative preference is flat (0 for every ordinary
        # outcome); counts are still kept, so after the first clear log_pref is exactly the learned one
        self.flat_until_clear = flat_until_clear
        self.cleared = False

    def observe(self, tr: Transition) -> None:
        if tr.reset:
            self.recent.clear()
            return
        self.n[tr.label] += 1
        self.recent.append(tr.label)
        if tr.level_completed:
            self.cleared = True
            for lab in self.recent:
                self.hits[lab] += 1
            self.recent.clear()
        elif tr.game_over:
            for lab in self.recent:
                if lab != "game_over":
                    self.avoid[lab] += 1
            self.recent.clear()

    def base_rate(self) -> float:
        tot = sum(self.n.values())
        return (sum(self.hits.values()) + 1.0) / (tot + 2.0)

    def log_pref(self, label: str) -> float:
        if label == "level_clear":
            return self.c_clear
        if label == "game_over":
            return self.c_game_over
        if self.flat_until_clear and not self.cleared:
            # no clear yet = no evidence about what is wanted: "the most common outcome is the least wanted" (log v/b
            # with no hits) is a self-made prior; only the game-over aversion (outcomes seen before a game over) stays
            return self.c_avoid if self.avoid[label] else 0.0
        b = self.base_rate()
        v = (self.hits[label] + self.prior_n * b) / (self.n[label] + self.prior_n)
        return math.log(v / b) + (self.c_avoid if self.avoid[label] else 0.0)

    def pragmatic(self, dist: dict, goal_gain: float = 0.0, w_goal: float = 2.0) -> float:
        return sum(p * self.log_pref(o) for o, p in dist.items()) + w_goal * goal_gain
