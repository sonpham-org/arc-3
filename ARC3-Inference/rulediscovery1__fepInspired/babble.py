# Author: Claude Opus 5.5 (Bubba)
# Date: 25-September-2026
# PURPOSE: Debate four, pick 2 (docs 2026-09-25-warehouse-expert-debate-4.md Round 4, design in
#   docs 2026-09-25-warehouse-expert-debate-2.md Rounds 4-5; OpenMind #arc-3 11:24 ET; Claude Opus 5.5 (Bubba)): "stage two",
#   goals before the first clear, for the rule discovery agent (AgentConfig.goal_babble / caused_contrast).
#     - CausedChange: which goals' progress the agent's ACTIONS change, as opposed to change that happens anyway (a ticking
#       bar). It reuses the contingency self (selfmodel.ContingentSelf): a step is IDLE when a button with a learned move
#       was pressed and the self did not move (the action did nothing to the agent), ACTIVE when the self moved; presses of
#       non-moving buttons and steps where the self is unknown are left out (an interact may grab something without the
#       self moving). Per goal: how often its progress changed on active and on idle steps. Caused share
#       = 1 - P(change | idle) / P(change | active), with P(change | idle) shrunk toward "never" by k_idle pseudo-steps (a
#       stated prior: change is taken as caused until it is seen happening while the agent does nothing); a goal whose
#       progress never changed keeps share 1. A ticking bar changes on idle steps as often as on active ones: share ~ 0.
#       A step bar that drains only when the agent moves (Locksmith) is action-caused by that test, so the ambient
#       convention of epistemic.ContactContext is added: a goal whose progress changed on at least ambient_share of the
#       counted steps (after min_steps of them), whatever the action, is a clock, not a goal: share 0.
#       goals.GoalBeliefs multiplies its contrast evidence on a clear by this share (caused_contrast), so the next clear
#       cannot name the step bar.
#     - GoalBabbler (intrinsically motivated goal exploration, "goal babbling"): while the play has had no clear and the
#       budget is not urgent, sample one goal from the TIED goal hypotheses (posterior at least `tie` of the top goal's),
#       among those whose change is caused (share >= min_share) and not satisfied now, weighted by its babble weight x its
#       caused share x a small compression tie-breaker exp(w_mdl ln(1 + components removed when it holds)) (an MDL prior:
#       goal boards tend to have fewer pieces than start boards; small on purpose). The sampled goal enters the EFE policy
#       as a PREFERENCE (policy.EFEPolicy.score: G -= w_prag x w_babble x the rule-set-weighted progress the action is
#       imagined to make on it) and the agent tries to reach it with the existing beam planner under a rule set drawn
#       from the tempered posterior (epistemic.sample_hypotheses). Soft updates: reaching the goal without a clear
#       multiplies its weight by `soft` (weakens, never kills: floor w_min); new progress multiplies it by `gain` (capped at
#       w_max: prefer goals where the agent makes progress); `patience` steps without new progress end the episode with
#       weight x `stall`. A clear ends babbling for the play. goals.GoalBeliefs(soft_reach=True) is the matching change
#       to the goal posterior: a goal reached without a clear loses ln(soft_fa) once per stretch of being satisfied, with
#       the total loss floored at ln(fa_floor), instead of ln(false_alarm) on every such step. That defuses the known
#       Warehouse trap: its target is fully covered one step before the win while the last box is still held.
#   Nothing here reads game internals; goals are goals.py's templates, the self is the agent's own.
# SRP/DRY check: Pass -- goal templates and posterior from goals.py, the self's displacement and learned moves from
#   selfmodel.py (via rules.ContextBuilder), posterior draws from epistemic.sample_hypotheses, planning from
#   policy.BeamPlanner. New: the caused-change contingency per goal and the babbling episode bookkeeping.
"""Goal babbling over tied goal hypotheses, and which goals the agent's actions (not time) change."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Optional


@dataclass
class BabbleConfig:
    tie: float = 0.125         # candidate goals: posterior at least this share of the top goal's
    min_share: float = 0.25    # ... whose progress changes are at least this share action-caused
    w_mdl: float = 0.1         # compression tie-breaker weight (per nat of components removed)
    patience: int = 40         # steps without new progress on the sampled goal before its episode ends
    soft: float = 0.5          # weight factor: reached without a clear
    stall: float = 0.8         # weight factor: episode ended without new progress
    gain: float = 1.25         # weight factor: new progress (learning progress)
    w_min: float = 0.05
    w_max: float = 4.0
    replan_every: int = 20     # steps between planning attempts toward the same goal
    k_idle: float = 2.0        # pseudo-steps shrinking P(change | idle) toward 0
    ambient_share: float = 0.3 # progress changing on this share of counted steps = a clock (as epistemic.ContactContext)
    min_steps: int = 10        # ... after this many counted steps
    max_log: int = 120


class CausedChange:
    """Per goal: progress changes on active steps (the self moved) and idle steps (a moving button did nothing)."""

    def __init__(self, k_idle: float = 2.0, ambient_share: float = 0.3, min_steps: int = 10):
        self.k_idle, self.ambient_share, self.min_steps = k_idle, ambient_share, min_steps
        self.stats: dict = {}                  # goal key -> [active steps, changed, idle steps, changed]
        self.last: dict = {}                   # goal key -> progress on the previous scored board
        self.idle_steps = 0
        self.active_steps = 0

    def observe(self, prog: Optional[dict], idle: Optional[bool]) -> None:
        """prog: goal key -> progress on this step's board (None: a RESET / clear / unscored step, forget the last
        board); idle: True / False as in the header, None = not counted."""
        if prog is None:
            self.last = {}
            return
        if idle is not None and self.last:
            self.idle_steps += int(idle)
            self.active_steps += int(not idle)
            for k, p in prog.items():
                p0 = self.last.get(k)
                if p0 is None:
                    continue
                st = self.stats.setdefault(k, [0, 0, 0, 0])
                ch = int(abs(p - p0) > 1e-9)
                if idle:
                    st[2] += 1
                    st[3] += ch
                else:
                    st[0] += 1
                    st[1] += ch
        self.last = prog

    def share(self, k) -> float:
        st = self.stats.get(k)
        if st is None or (st[1] == 0 and st[3] == 0):
            return 1.0
        n = st[0] + st[2]
        if n >= self.min_steps and st[1] + st[3] >= self.ambient_share * n:
            return 0.0                                  # changes on most steps whatever the action: a clock
        pa = st[1] / st[0] if st[0] else 1.0
        pi = st[3] / (st[2] + self.k_idle)
        return 0.0 if pa <= 0 else min(max(1.0 - pi / pa, 0.0), 1.0)


def components_removed(goal, scene) -> int:
    """How many pieces satisfying `goal` would take off this board (the compression tie-breaker's count)."""
    t = goal.template
    if t in ("fill", "empty"):
        return len(scene.colour_objects(goal.a))
    if t == "count":
        return max(len(scene.colour_objects(goal.a)) - goal.k, 0)
    return 0


class GoalBabbler:
    def __init__(self, cfg: Optional[BabbleConfig] = None, seed: int = 0):
        self.cfg = cfg or BabbleConfig()
        self.rng = random.Random(seed * 104729 + 11)   # own stream: never shifts the policy's or the curiosity's draws
        self.caused = CausedChange(self.cfg.k_idle, self.cfg.ambient_share, self.cfg.min_steps)
        self.w: dict = {}                              # goal key -> babble weight (1 until updated)
        self.on = False                                # set by the agent before each decision
        self.key = None                                # the goal of the current episode
        self.start_t = 0
        self.best = 0.0
        self.since = 0
        self.plan_t = -10 ** 9
        self.done = False                              # a clear happened: no more babbling this play
        self.episodes = self.reached = self.stalled = 0
        self.attempts = self.plans = self.plan_steps = self.pref_decisions = 0
        self.tried: dict = {}                          # goal description -> episodes
        self.log: list = []                            # [step, event, goal, weight after]

    # -- episodes
    def active(self, goals, urgent: bool) -> bool:
        if goals.n_clears > 0 and not self.done:
            self.done = True
            self._end(None, "clear")
        return not self.done and not urgent

    def weight(self, k) -> float:
        return self.w.get(k, 1.0)

    def candidates(self, goals, scene) -> list:
        post = goals.posterior()
        if not post:
            return []
        pmax = max(post.values())
        out = []
        for k, p in post.items():
            if p < self.cfg.tie * pmax or self.caused.share(k) < self.cfg.min_share:
                continue
            if goals.goals[k].progress(scene, goals.base) >= goals.satisfied:
                continue
            out.append(k)
        return out

    def sample(self, goals, scene, t: int):
        cands = self.candidates(goals, scene)
        if not cands:
            return None
        ws = [self.weight(k) * self.caused.share(k)
              * math.exp(self.cfg.w_mdl * math.log1p(components_removed(goals.goals[k], scene))) for k in cands]
        if sum(ws) <= 0:
            return None
        self.key = self.rng.choices(cands, weights=ws, k=1)[0]
        g = goals.goals[self.key]
        self.start_t, self.since = t, 0
        self.best = g.progress(scene, goals.base)
        self.episodes += 1
        d = g.describe()
        self.tried[d] = self.tried.get(d, 0) + 1
        self._log(t, "start", d)
        return g

    def goal(self, goals):
        return None if self.key is None else goals.goals.get(self.key)

    def _log(self, t, event, desc) -> None:
        if len(self.log) < self.cfg.max_log:
            self.log.append([t, event, desc, round(self.weight(self.key), 3) if self.key is not None else None])

    def _end(self, t, event) -> None:
        self.key = None

    def _scale(self, f: float) -> None:
        self.w[self.key] = min(max(self.weight(self.key) * f, self.cfg.w_min), self.cfg.w_max)

    def step(self, goals, tr, t: int) -> None:
        """After an observed step (goals already updated): soft updates of the current episode's goal."""
        if self.key is None:
            return
        if tr.reset or tr.level_completed:
            self._log(t, "level", goals.goals[self.key].describe())
            self._end(t, "level")
            return
        if not tr.scored or tr.post is None:
            return
        g = goals.goals[self.key]
        p = (goals.last_prog or {}).get(self.key)
        if p is None:
            p = g.progress(tr.post, goals.base)
        if p >= goals.satisfied:                      # reached, and no clear: weaken, never kill
            self._scale(self.cfg.soft)
            self.reached += 1
            self._log(t, "reached", g.describe())
            self._end(t, "reached")
        elif p > self.best + 1e-9:
            self.best, self.since = p, 0
            self._scale(self.cfg.gain)
        else:
            self.since += 1
            if self.since >= self.cfg.patience:
                self._scale(self.cfg.stall)
                self.stalled += 1
                self._log(t, "stalled", g.describe())
                self._end(t, "stalled")

    # -- the preference and planning
    def gain(self, goals, now, nxt) -> float:
        """Progress the imagined board `nxt` makes on the current goal over `now`."""
        g = self.goal(goals)
        if g is None:
            return 0.0
        return g.progress(nxt, goals.base) - g.progress(now, goals.base)

    def want_plan(self, t: int) -> bool:
        return self.key is not None and (self.plan_t < self.start_t or t - self.plan_t >= self.cfg.replan_every)

    def weights_report(self, goals, n: int = 8) -> list:
        """[goal, babble weight, caused share] for the goals whose weight moved, largest change first."""
        rows = [(goals.goals[k].describe(), round(w, 3), round(self.caused.share(k), 3))
                for k, w in self.w.items() if k in goals.goals]
        return sorted(rows, key=lambda r: -abs(math.log(r[1])))[:n]
