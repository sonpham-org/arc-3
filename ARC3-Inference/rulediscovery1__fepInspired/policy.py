# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Action selection for the rule discovery prototype (OpenMind, #arc-3, 23-Sep-2026 21:03 ET),
#   following Parr, Pezzulo & Friston, "Active Inference" (eq. 2.6, sections 7.4-7.5, habits and
#   precision). For every candidate action a on the current board:
#     G(a) = - w_sal * salience(a) - w_nov * novelty(a) - w_prag * pragmatic(a) - w_emp * empowerment(a) + cost(a)
#       salience   = I(outcome; which rule set is true) = H[mixture predictive] - E_h H[p_h]: the
#                    disagreement between surviving hypotheses (information gain about structure)
#       novelty    = efe_trace_analysis.eig of the Dirichlet for a's handcolour context (information
#                    gain about parameters; count-based, gives inhibition of return for free)
#       pragmatic  = E_h E_{o~p_h}[ln C(o)] + expected goal progress on the board the rule set imagines
#       empowerment= early in a level only: how much pressing a is expected to add to what the agent
#                    knows it controls (buttons whose displacement of the controlled object is unknown,
#                    or all buttons before any controlled object is found)
#       cost       = per-action cost (the score rewards fewer actions); clicks and undo priced apart
#   Policy: P(a) proportional to exp(ln E(a) - gamma G(a)), E a habit prior over action kinds carried
#   across levels, gamma a precision that rises as the posterior over rule sets concentrates.
#   Thompson fast path: sample one rule set from the posterior and act greedily under it (no mixture).
#   BeamPlanner: once the posterior entropy is low and a goal is credible, breadth-first / beam search
#   in the MAP rule set's imagined boards (Scene.apply) toward the top goal; the agent replans when a
#   plan step's predicted label is wrong or surprise spikes.
#   Candidate actions: valid buttons (RESET too since 23-Sep-2026, with its own cost) plus one click per distinct (colour, shape) object,
#   at a cell of the object nearest its centre.
#   Not run yet: only py_compile was used.
# SRP/DRY check: Pass -- EIG from efe_trace_analysis (via beliefs.NoveltyModel), handcolour contexts via
#   rules.ContextBuilder (agency_contexts), predictive distributions from beliefs.BeliefState, goal
#   progress / preferences from goals.py, imagination from perception.Scene.apply. New: the EFE sum,
#   precision / habit softmax, empowerment proxy, Thompson path and the planner.
"""Expected free energy over candidate actions; Thompson fast path; beam planner."""
from __future__ import annotations

import math
import random
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Optional

from .beliefs import BeliefState, entropy, mixture
from .goals import GoalBeliefs, Preferences
from .perception import CLICK, RESET, Action, Scene, label_parts
from .rules import ContextBuilder, RuleContext, RuleSet, advance_since


# ---------------------------------------------------------------- candidates

def candidate_actions(scene: Scene, valid: list[str], max_clicks: int = 24, allow_reset: bool = False) -> list[Action]:
    acts = [Action(v) for v in valid if v not in (CLICK, RESET)]
    if allow_reset and RESET in valid:
        acts.append(Action(RESET))          # 23-Sep-2026: the agent may choose RESET (costed, see cost())
    if CLICK in valid:
        seen, objs = set(), []
        for c in sorted(scene.objects(), key=lambda c: -c.size):
            if c.type_key not in seen:
                seen.add(c.type_key)
                objs.append(c)
        for c in objs[:max_clicks]:
            r, col = scene.click_point(c)
            acts.append(Action(CLICK, r, col))
    return acts


def action_kind(a: Action) -> str:
    return "click" if a.is_click else a.name


# ---------------------------------------------------------------- habits and precision

class HabitPrior:
    """E: a prior over action kinds from what preceded clears (carried across levels of a play).
    Starts flat; `seed` can load counts from solved traces offline."""

    def __init__(self, pseudo: float = 1.0, seed: Optional[dict] = None, window: int = 8):
        self.pseudo = pseudo
        self.counts: Counter = Counter(seed or {})
        self.recent: deque = deque(maxlen=window)

    def log_prior(self, a: Action, kinds: list[str]) -> float:
        z = sum(self.counts[k] + self.pseudo for k in kinds)
        return math.log((self.counts[action_kind(a)] + self.pseudo) / z)

    def observe(self, a: Action, level_completed: bool) -> None:
        self.recent.append(action_kind(a))
        if level_completed:
            self.counts.update(self.recent)
            self.recent.clear()


def precision(gamma0: float, post_entropy: float, n_hyps: int, kappa: float = 2.0) -> float:
    """gamma rises from gamma0 to gamma0 * (1 + kappa) as the rule-set posterior concentrates."""
    h_max = math.log(max(n_hyps, 2))
    return gamma0 * (1.0 + kappa * max(0.0, 1.0 - post_entropy / h_max))


# ---------------------------------------------------------------- expected free energy

@dataclass
class PolicyConfig:
    w_sal: float = 1.0
    w_nov: float = 1.0
    w_prag: float = 1.0
    w_emp: float = 0.5
    emp_horizon: int = 12            # empowerment bonus fades out over the first N actions of a level
    cost_button: float = 0.05
    cost_click: float = 0.08
    cost_undo: float = 0.3
    gamma0: float = 4.0
    thompson: bool = False
    plan_entropy: float = 0.3        # plan when the rule-set posterior entropy is below this (nats)
    plan_goal_p: float = 0.5         # ... and the top goal's posterior is above this
    max_clicks: int = 24
    allow_reset: bool = True         # RESET is a candidate action (it restarts the level)
    cost_reset: float = 0.5


@dataclass
class ActionScore:
    action: Action
    salience: float
    novelty: float
    pragmatic: float
    empowerment: float
    cost: float
    G: float
    log_p: float = 0.0
    map_label: Optional[str] = None


@dataclass
class Decision:
    action: Action
    mode: str                         # efe | thompson | plan
    scores: list = field(default_factory=list)
    gamma: float = 0.0


def empowerment_bonus(ctx: ContextBuilder, a: Action, level_age: int, horizon: int) -> float:
    """Count-based proxy for how much a press adds to the known action -> controlled-object channel."""
    if not a.is_button or level_age >= horizon:
        return 0.0
    fade = 1.0 - level_age / horizon
    tr = ctx.state.agency.tracker
    if tr.controlled() is None:
        # presses of this button already logged against any candidate object type
        pressed = max((sum(stats[a.name].values()) for stats in tr.stats.values() if a.name in stats), default=0)
        return fade / (1.0 + pressed)
    return fade * (1.0 if tr.direction(a.name) is None else 0.0)


class EFEPolicy:
    def __init__(self, cfg: Optional[PolicyConfig] = None, seed: int = 0):
        self.cfg = cfg or PolicyConfig()
        self.rng = random.Random(seed)

    def cost(self, a: Action) -> float:
        if a.is_click:
            return self.cfg.cost_click
        if a.name == "ACTION7":
            return self.cfg.cost_undo
        if a.name == RESET:
            return self.cfg.cost_reset
        return self.cfg.cost_button

    def score(self, rc: RuleContext, beliefs: BeliefState, goals: GoalBeliefs, prefs: Preferences,
              ctx: ContextBuilder) -> ActionScore:
        preds = beliefs.predictions(rc)
        ws = [w for _, w, _, _ in preds]
        dists = [d for _, _, _, d in preds]
        mix = mixture(dists, ws)
        sal = max(entropy(mix) - sum(w * entropy(d) for w, d in zip(ws, dists)), 0.0)
        nov = beliefs.novelty.novelty(rc.hc_ctx)
        prag = 0.0
        for (h, w, pred, d) in preds:
            gain = 0.0
            if pred is not None and pred.effects:
                gain = goals.expected_gain(rc.scene, rc.scene.apply(pred.effects))
            prag += w * prefs.pragmatic(d, gain)
        emp = empowerment_bonus(ctx, rc.action, rc.level_age, self.cfg.emp_horizon)
        c = self.cost(rc.action)
        cfg = self.cfg
        G = -(cfg.w_sal * sal + cfg.w_nov * nov + cfg.w_prag * prag + cfg.w_emp * emp) + c
        top = max(preds, key=lambda t: t[1])
        return ActionScore(rc.action, sal, nov, prag, emp, c, G,
                           map_label=top[2].label if top[2] is not None else None)

    def choose(self, scene: Scene, valid: list[str], beliefs: BeliefState, goals: GoalBeliefs,
               prefs: Preferences, ctx: ContextBuilder, habits: HabitPrior, greedy: bool = False) -> Decision:
        cands = candidate_actions(scene, valid, self.cfg.max_clicks, self.cfg.allow_reset)
        if not cands:
            return Decision(Action(RESET), "efe")
        if self.cfg.thompson:
            return self.thompson(scene, cands, beliefs, goals, prefs, ctx)
        kinds = sorted({action_kind(a) for a in cands})
        gamma = precision(self.cfg.gamma0, beliefs.posterior_entropy(), len(beliefs.hyps))
        scores = [self.score(ctx.context(scene, a), beliefs, goals, prefs, ctx) for a in cands]
        for s in scores:
            s.log_p = habits.log_prior(s.action, kinds) - gamma * s.G
        m = max(s.log_p for s in scores)
        z = sum(math.exp(s.log_p - m) for s in scores)
        for s in scores:
            s.log_p = s.log_p - m - math.log(z)
        if greedy:
            pick = max(scores, key=lambda s: s.log_p)
        else:
            r, acc, pick = self.rng.random(), 0.0, scores[-1]
            for s in scores:
                acc += math.exp(s.log_p)
                if r <= acc:
                    pick = s
                    break
        return Decision(pick.action, "efe", scores, gamma)

    def thompson(self, scene, cands, beliefs, goals, prefs, ctx) -> Decision:
        """Sample one rule set, act greedily under it: pragmatic + novelty - cost (no mixture)."""
        w = beliefs.weights()
        h = self.rng.choices(beliefs.hyps, weights=w, k=1)[0]
        best, best_v = cands[0], -math.inf
        for a in cands:
            rc = ctx.context(scene, a)
            pred = h.ruleset.predict(rc)
            d = h.dist(pred, beliefs.backoff.dist(rc))
            gain = goals.expected_gain(scene, scene.apply(pred.effects)) if (pred and pred.effects) else 0.0
            v = prefs.pragmatic(d, gain) + self.cfg.w_nov * beliefs.novelty.novelty(rc.hc_ctx) - self.cost(a)
            if v > best_v:
                best, best_v = a, v
        return Decision(best, "thompson")


# ---------------------------------------------------------------- planning in the believed model

@dataclass
class Plan:
    actions: list
    expected: list                    # predicted label per step (to detect a wrong model)
    goal: str
    progress: float


class BeamPlanner:
    """Breadth-first / beam search over imagined boards under one rule set. A branch ends where the
    rule set is silent (the model does not know what happens there)."""

    def __init__(self, max_depth: int = 12, beam: int = 32, max_expansions: int = 4000):
        self.max_depth, self.beam, self.max_expansions = max_depth, beam, max_expansions

    def plan(self, scene: Scene, valid: list[str], ruleset: RuleSet, goals: GoalBeliefs,
             ctx: ContextBuilder, rc0: RuleContext) -> Optional[Plan]:
        top = goals.top_goal()
        if top is None:
            return None
        goal, _ = top
        start = goal.progress(scene, goals.base)
        frontier = [(scene, rc0.last_label, rc0.since, rc0.level_age, [], [])]
        seen = {scene.signature()}
        best: Optional[Plan] = None
        expansions = 0
        for _ in range(self.max_depth):
            children = []
            for sc, last, since, age, acts, labs in frontier:
                for a in candidate_actions(sc, valid):
                    expansions += 1
                    if expansions > self.max_expansions:
                        return best
                    rc = ctx.context(sc, a, last_label=last, since=since, level_age=age)
                    pred = ruleset.predict(rc)
                    if pred is None:
                        continue
                    nxt = sc.apply(pred.effects)
                    sig = nxt.signature()
                    if sig in seen:
                        continue
                    seen.add(sig)
                    p = goal.progress(nxt, goals.base)
                    path, plabs = acts + [a], labs + [pred.label]
                    if p >= goals.satisfied:
                        return Plan(path, plabs, goal.describe(), p)
                    if best is None or p > best.progress:
                        best = Plan(path, plabs, goal.describe(), p)
                    children.append((p, nxt, pred.label, advance_since(since, a, label_parts(pred.label)),
                                     age + 1, path, plabs))
            if not children:
                break
            children.sort(key=lambda t: -t[0])
            frontier = [(c[1], c[2], c[3], c[4], c[5], c[6]) for c in children[: self.beam]]
        return best if best is not None and best.progress > start else None
