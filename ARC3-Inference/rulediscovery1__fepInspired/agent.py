# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026 (tensor-logic switches 24-September-2026)
# PURPOSE: The orchestrating agent of the rule discovery prototype (OpenMind, #arc-3, 23-Sep-2026
#   21:03 ET): perceive -> update beliefs -> propose hypotheses -> choose action, with the book's two
#   timescales made explicit.
#     - FastMemory (per level): the level's first board, the current plan and its position, level age.
#       Thrown away on every clear / RESET.
#     - SlowMemory (per play): the posterior over rule sets and its back-off / novelty counts, goal
#       beliefs, preferences, habit prior, play history (ContextBuilder). Carried across the levels of
#       ONE play only: round four found carrying counts within a game helps, while a prior pooled
#       from OTHER games hurt, so nothing here reads another game's beliefs.
#     - RuleDiscoveryAgent: start_play(first frame) / act() -> Action / observe(action, next frame,
#       flags). observe() builds the rule context BEFORE the outcome (prequential), perceives (the
#       Perceiver always advances pre = post), scores and updates beliefs, updates goals with the MAP
#       rule set's imagined board, advances play history, drops a plan whose prediction failed or on a
#       surprise spike, starts a new FastMemory on a level change, and re-proposes hypotheses every
#       few steps, on a spike and on a clear. act() follows a live plan, else plans when the posterior
#       is concentrated and a goal is credible, else picks by expected free energy.
#     - LLMAdvisor / TextSummaryAdvisor: the text interface for the harness model: a summary of the
#       top rule sets, goals and the most informative probe. The model is meant to theorise (propose
#       rules as code via rules.RuleProvider) rather than press buttons. No model is called here.
#     - HarnessAdapter: maps the harness's view (inference/agent/runtime_state.Frame: grid, step,
#       level; valid engine action names) to agent calls, and the agent's Action back to the payload the
#       sandbox's action() accepts ({"action": "UP"} or {"action": "MOUSE", "row": r, "col": c}; names via
#       inference.agent.action_names.to_model_action). The harness itself is not modified.
#     - Optional explorer (explore.ObjectContactExplorer, proposal step 1): when no plan is running, walk
#       with the learned movers to the nearest untouched object before falling back to the policy.
#     - Optional curiosity (curiosity.CuriosityDrive, OpenMind 23-Sep-2026 22:52 ET): EBUL last-layer
#       entropy gain; re-weights the policy's choice when no plan is being followed.
#     - AgentConfig.use_hdc (24-Sep-2026, HDC integration A/B): one switch that gives the ContextBuilder an
#       hdc_bridge.HdcState (ghost tape rule, soft wall map, common-fate grouping; hdc_pieces picks a subset).
#       Off by default: the same code path then behaves exactly as before, so both arms share seeds and code.
#     - AgentConfig.use_tl (24-Sep-2026, tensor-logic overhaul): the ContextBuilder gets a tl/relations.TLState (relational
#       perception + the tensor-logic learner, tl/bridge.make_tl); the proposer adds the learner's thresholded programs
#       (tl/rule.TLRule) to its candidates; a surprise spike runs the learner's structure test. tl_templates=False turns
#       the hand-written templates off (the tl_only arm: rules come from tensor logic alone; the explorer then takes its
#       mover from the learned program). tl_plan=True makes the explorer plan by forward-chaining reachability
#       (tl/plan.py). Off by default = the old behaviour, checked action for action.
# SRP/DRY check: Pass -- every component comes from the sibling modules; the harness action-name map is
#   imported from inference/agent/action_names.py, not restated. New: orchestration, memory split,
#   advisor text, adapter.
"""RuleDiscoveryAgent: perceive -> believe -> hypothesise -> act (two timescales)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from .beliefs import BeliefState, StepSurprise
from .goals import GoalBeliefs, Preferences
from .hypotheses import HypothesisProposer
from .perception import RESET, Action, Perceiver, Scene, Transition
from .policy import BeamPlanner, Decision, EFEPolicy, HabitPrior, Plan, PolicyConfig
from .rules import ContextBuilder, RuleProvider


@dataclass
class AgentConfig:
    propose_every: int = 5
    max_hypotheses: int = 8
    max_records: int = 600
    dl_weight: float = 1.0             # temperature on the MDL prior (beliefs.BeliefState)
    likelihood: str = "parts"          # beliefs.LIKELIHOOD: "parts" (event-level) or "label" (whole label)
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    greedy: bool = False               # argmax instead of sampling from the softmax policy
    seed: int = 0
    plan: bool = True
    use_hdc: bool = False              # HDC integration A/B (24-Sep-2026): the soft-computing pieces, hdc_bridge.py
    hdc_pieces: tuple = ("tape", "walls", "fate")   # which pieces when use_hdc (per-piece isolation)
    use_tl: bool = False               # tensor-logic overhaul (24-Sep-2026): relational perception + learned rules, tl/
    tl_templates: bool = True          # with use_tl: False = hand-written templates off (tensor-logic rules only)
    tl_plan: bool = True               # with use_tl: the explorer plans by forward-chaining reachability (tl/plan.py)
    tl_cfg: Any = None                 # tl.learner.TLConfig or None (defaults)


@dataclass
class FastMemory:
    """Per-level state (the fast timescale)."""
    level: int
    start: Scene
    plan: Optional[Plan] = None
    plan_step: int = 0
    steps: int = 0


@dataclass
class SlowMemory:
    """Per-play state carried across levels (the slow timescale)."""
    beliefs: BeliefState
    goals: GoalBeliefs
    prefs: Preferences
    habits: HabitPrior
    ctx: ContextBuilder


@dataclass
class StepReport:
    transition: Transition
    surprise: StepSurprise
    proposed: int = 0
    plan_dropped: bool = False


class LLMAdvisor(Protocol):
    def summarize(self, agent: "RuleDiscoveryAgent") -> str: ...
    def suggest_probe(self, agent: "RuleDiscoveryAgent") -> Optional[Action]: ...


class TextSummaryAdvisor:
    """Plain-text state for the harness model (no model call). Also names the most informative
    probe from the last decision (highest salience + novelty)."""

    def summarize(self, agent: "RuleDiscoveryAgent") -> str:
        s = agent.slow
        lines = [f"level {agent.fast.level}, {agent.fast.steps} actions this level, "
                 f"rule-set posterior entropy {s.beliefs.posterior_entropy():.2f} nats"]
        for i, (h, w) in enumerate(s.beliefs.top(3), 1):
            lines.append(f"hypothesis {i} (p={w:.2f}, {h.dl:.1f} nats of rules, miss rate {h.eps:.2f}):")
            lines += [f"  - {d}" for d in h.ruleset.describe()]
        for g, p in s.goals.top(3):
            lines.append(f"goal candidate (p={p:.2f}): {g.describe()}")
        ctl = s.ctx.state.agency.tracker.controlled()
        lines.append("controlled object: " + (f"colour {ctl[0]}" if ctl else "not found yet"))
        if agent.last_surprise is not None:
            ls = agent.last_surprise
            lines.append(f"last outcome {ls.label} (predicted {ls.predicted}), surprise {ls.surprisal:.2f} nats"
                         + (" -- SPIKE" if ls.spike else ""))
        probe = self.suggest_probe(agent)
        if probe is not None:
            lines.append(f"most informative probe: {probe.display()}")
        return "\n".join(lines)

    def suggest_probe(self, agent: "RuleDiscoveryAgent") -> Optional[Action]:
        d = agent.last_decision
        if d is None or not d.scores:
            return None
        return max(d.scores, key=lambda s: s.salience + s.novelty).action


class RuleDiscoveryAgent:
    def __init__(self, config: Optional[AgentConfig] = None, advisor: Optional[LLMAdvisor] = None,
                 provider: Optional[RuleProvider] = None, curiosity: Optional[Any] = None,
                 explorer: Optional[Any] = None):
        self.cfg = config or AgentConfig()
        self.curiosity = curiosity          # curiosity.CuriosityDrive (EBUL entropy), optional
        self.explorer = explorer            # explore.ObjectContactExplorer (touch untouched objects), optional
        self.advisor = advisor or TextSummaryAdvisor()
        self.proposer = HypothesisProposer(provider=provider)
        self.tl_source = None               # tl.bridge.TLSource when use_tl
        self.policy = EFEPolicy(self.cfg.policy, self.cfg.seed)
        self.planner = BeamPlanner()
        self.perceiver = Perceiver()
        self.valid: list[str] = []
        self.slow: Optional[SlowMemory] = None
        self.fast: Optional[FastMemory] = None
        self.last_decision: Optional[Decision] = None
        self.last_surprise: Optional[StepSurprise] = None
        self.n_steps = 0

    # -- lifecycle
    def start_play(self, grid, valid_actions: list[str], level: int = 0) -> None:
        self.valid = list(valid_actions)
        from . import beliefs as _b
        _b.LIKELIHOOD = self.cfg.likelihood
        scene = self.perceiver.begin(grid, level)
        hdc = None
        if self.cfg.use_hdc:
            from .hdc_bridge import HdcConfig, HdcState
            hdc = HdcState(HdcConfig(pieces=tuple(self.cfg.hdc_pieces)))
        tl = None
        if self.cfg.use_tl:
            from .tl.bridge import TLSource, make_tl
            tl = make_tl(self.cfg.tl_cfg)
            self.tl_source = TLSource(tl)
            self.proposer.tl = self.tl_source
            self.proposer.templates = self.cfg.tl_templates
            if self.explorer is not None and self.cfg.tl_plan:
                self.explorer.cfg.search = "tl"
        self.slow = SlowMemory(BeliefState(self.cfg.max_hypotheses, self.cfg.max_records,
                                           dl_weight=self.cfg.dl_weight), GoalBeliefs(),
                               Preferences(), HabitPrior(), ContextBuilder(hdc, tl))
        self.slow.ctx.begin(scene)
        self.fast = FastMemory(level, scene)
        self.slow.goals.bind_level(scene)
        self.n_steps = 0
        if self.curiosity is not None:
            self.curiosity.start(grid, self.perceiver.hud.mask)
        if self.explorer is not None:
            self.explorer.reset_level()

    def _new_level(self, scene: Scene, level: int) -> None:
        self.fast = FastMemory(level, scene)
        self.slow.goals.bind_level(scene)

    # -- acting
    def act(self) -> Action:
        scene = self.perceiver.current
        f, s = self.fast, self.slow
        if f.plan is not None and f.plan_step < len(f.plan.actions):
            a = f.plan.actions[f.plan_step]
            f.plan_step += 1
            self.last_decision = Decision(a, "plan")
            return a
        f.plan = None
        if self.explorer is not None:
            a = self.explorer.next_action(self)
            if a is not None:
                self.last_decision = Decision(a, "touch")
                return a
        if self.cfg.plan and self._ready_to_plan():
            rc0 = s.ctx.context(scene, Action(RESET))
            plan = self.planner.plan(scene, self.valid, s.beliefs.map_hypothesis().ruleset, s.goals, s.ctx, rc0)
            if plan is not None and plan.actions:
                f.plan, f.plan_step = plan, 1
                self.last_decision = Decision(plan.actions[0], "plan")
                return plan.actions[0]
        d = self.policy.choose(scene, self.valid, s.beliefs, s.goals, s.prefs, s.ctx, s.habits, self.cfg.greedy)
        if self.curiosity is not None:
            d = self.curiosity.rechoose(d)
        self.last_decision = d
        return d.action

    def _ready_to_plan(self) -> bool:
        s = self.slow
        top = s.goals.top_goal()
        return (top is not None and top[1] >= self.cfg.policy.plan_goal_p
                and s.beliefs.posterior_entropy() <= self.cfg.policy.plan_entropy
                and len(s.beliefs.map_hypothesis().ruleset) > 0)

    # -- observing
    def observe(self, action: Action, grid, level_completed: bool = False, game_over: bool = False,
                level: Optional[int] = None, valid_actions: Optional[list[str]] = None) -> StepReport:
        s, f = self.slow, self.fast
        if valid_actions is not None:
            self.valid = list(valid_actions)
        pre = self.perceiver.current
        rc = s.ctx.context(pre, action)                      # before the outcome: prequential
        tr = self.perceiver.observe(action, grid, level_completed, game_over, level)
        if self.curiosity is not None:
            self.curiosity.observe(action, grid, self.perceiver.hud.mask)
        sur = s.beliefs.observe(rc, tr)
        self.last_surprise = sur
        pred = s.beliefs.map_hypothesis().ruleset.predict(rc) if not tr.reset else None
        imagined = pre.apply(pred.effects) if (pred is not None and pred.effects) else None
        s.goals.observe(tr, imagined)
        s.prefs.observe(tr)
        s.habits.observe(action, tr.level_completed)
        s.ctx.observe(tr)
        if self.explorer is not None:
            self.explorer.observe(self, action, tr)
        rep = StepReport(tr, sur)
        if f.plan is not None:
            expected = f.plan.expected[f.plan_step - 1] if 0 < f.plan_step <= len(f.plan.expected) else None
            if sur.spike or expected != tr.label:
                f.plan = None
                rep.plan_dropped = True
        f.steps += 1
        self.n_steps += 1
        if tr.level_completed or tr.reset:
            self._new_level(self.perceiver.current, self.perceiver.level)
        if sur.spike and self.tl_source is not None and tr.scored:
            self.tl_source.surprise(tr.index)          # structure test pointed at the surprising step
        if sur.spike or tr.level_completed or self.n_steps % self.cfg.propose_every == 0:
            rep.proposed = self.propose()
        return rep

    def propose(self) -> int:
        s = self.slow
        summary = self.advisor.summarize(self)
        n = s.beliefs.add_rulesets(self.proposer.propose(s.beliefs, summary))
        s.beliefs.reduce()
        return n


# ---------------------------------------------------------------- harness adapter (interface only)

class HarnessAdapter:
    """Glue for later live use inside the harness loop (not wired in; the harness is untouched).
    Call on_state() with every new frame; send the returned payload through the sandbox's action()."""

    def __init__(self, agent: RuleDiscoveryAgent):
        self.agent = agent
        self.started = False
        self.last_level: Optional[int] = None
        self.pending: Optional[Action] = None

    def on_state(self, grid, level: int, valid_actions: list[str], game_over: bool = False) -> dict:
        if not self.started or self.pending is None:
            self.agent.start_play(grid, valid_actions, level)
            self.started = True
        else:
            cleared = self.last_level is not None and level > self.last_level
            self.agent.observe(self.pending, grid, level_completed=cleared, game_over=game_over, level=level,
                               valid_actions=valid_actions)
        self.last_level = level
        self.pending = self.agent.act()
        return self.to_harness(self.pending)

    def on_frame(self, frame: Any, valid_actions: list[str], game_over: bool = False) -> dict:
        """frame: inference.agent.runtime_state.Frame (grid tuple of tuples, step, level)."""
        return self.on_state(frame.grid, int(frame.level), valid_actions, game_over)

    @staticmethod
    def to_harness(a: Action) -> dict:
        from inference.agent.action_names import to_model_action   # the harness's own name map
        out = {"action": to_model_action(a.name)}
        if a.is_click:
            out["row"], out["col"] = int(a.row), int(a.col)
        return out
