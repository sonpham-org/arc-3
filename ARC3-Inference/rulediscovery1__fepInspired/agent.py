# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026 (tensor-logic switches 24-September-2026, debate three, four and five 25-September-2026)
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
#     - Debate picks (24-Sep-2026, OpenMind #arc-3 22:49 ET; Claude Opus 5.5 (Bubba)), each an AgentConfig switch, all off by
#       default = the old behaviour action for action: use_self (selfmodel.ContingentSelf in the ContextBuilder), tl_facing
#       (the Facing relation in tensor logic), use_epistemic (policy terms from epistemic.py; a non-moving button that is
#       informative here preempts the explorer for that step), use_archive (archive.GoExploreArchive: returns by RESET +
#       replay take precedence over explorer and policy), goal_contrast (goals.GoalBeliefs contrast evidence on clears).
#     - Stage one (25-Sep-2026, docs 2026-09-25-warehouse-expert-debate-2.md picks 1-2, OpenMind #arc-3 02:38 ET; Claude Opus
#       5.5 (Bubba)), each an AgentConfig switch, off by default = the old behaviour action for action:
#       explore_handoff: the explorer's trip is an option that ends on arrival (new contact with any object) or surprise
#         and hands the choice back to the EFE policy for a short dwell (explore.ExploreConfig.handoff);
#       use_budget: budget.BudgetModel reads the learned gauge from the raw boards; the policy's pragmatic term prices the
#         forecast run-out risk with the preference for a game over (PolicyConfig.w_budget); when the forecast says the
#         gauge is about to run out ("urgent") explorer trips and archive replays give way to the policy, and a RESET the
#         policy chooses then becomes an archive return (use_archive) whose replay fits the refilled budget (only when
#         urgent: a RESET chosen at any other time is left as it was).
#     - Debate three (25-Sep-2026, docs 2026-09-25-warehouse-expert-debate-3.md, OpenMind #arc-3 05:47 ET; Claude Opus 5.5
#       (Bubba)), each an AgentConfig switch, off by default:
#       handoff_efe (pick 1, replaces explore_handoff's cut-and-dwell): the explorer raises a CHECK on arrival / relative
#         surprise / blocked / trip end (explore.ExploreConfig.interrupt); _interrupt() then scores every candidate with the
#         EFE policy and takes the best action that does not move the self only if its G is below every moving action's
#         (continuing the trip is worth at least the best one-step move); else the same trip goes on (resumed);
#       contact_context (pick 2, needs use_epistemic): epistemic.ContactContext on the ContextBuilder; non-moving buttons
#         get novelty and effect information keyed on the self's contact neighbourhood (PolicyConfig.w_ceig);
#       budget_learn (pick 3, needs use_budget): budget.BudgetConfig.learn_end: lives reader, learnable end belief with
#         its information value, plan-aware urgency (the explorer trip's / archive replay's remaining steps).
#     - Debate four (25-Sep-2026, docs 2026-09-25-warehouse-expert-debate-4.md, OpenMind #arc-3 11:24 ET; Claude Opus 5.5
#       (Bubba)), each an AgentConfig switch, off by default, on top of debate three's kept configuration (handoff_efe):
#       option_value (pick 1): at an explorer check, "continuing" is the semi-Markov value of the trip, not the best move's
#         one-step G: G_cont = c + (G_target - c) / k, k = the trip's remaining steps (the next trip's, peeked, when the check
#         came at a trip's end or a block), c = the cost of a button press, G_target = the EFE of the trip's arriving move
#         with its local novelty taken at the target's colour (epistemic.LocalNovelty). k = 1 gives the arriving move's own
#         G; with no trip to continue the one-step comparison of debate three stays. Every check is logged (check_log:
#         step, trigger, what won, the action, k, G_cont, the best non-moving G, the best move's G) for the outside labeller;
#       try_once (pick 1): the first time a trip brings the self into contact with a colour it never touched this play, the
#         check presses the best non-moving button (tried min_tries times, still no learned move) there once, whatever the
#         comparison says;
#       goal_babble (pick 2): babble.GoalBabbler on the ContextBuilder: while no clear has happened and the budget is not
#         urgent, a goal sampled from the tied goal hypotheses is a preference in EFE (PolicyConfig.w_babble) and the beam
#         planner tries to reach it under a rule set drawn from the tempered posterior (every replan_every steps; the plan
#         takes precedence over explorer trips, not over archive returns); GoalBeliefs(soft_reach=True);
#       caused_contrast (pick 2): babble.CausedChange (the contingency self's idle vs active steps) weights the contrast
#         evidence of a clear by each goal's action-caused share (with goal_contrast).
#       contact_gated (pick 3, needs use_epistemic): debate three's contact-neighbourhood novelty, gated: the policy uses it
#         only once every button has been pressed at least GATE_TRIES times this play, and then only for a button that
#         still has no learned move (ContactContext.open; the probe on Ghost Twin seeds 0 / 4 / 7 had every button's move
#         learned by its seventh press, before every button reached ten presses, so the gate never opens for a button
#         there).
#     - Debate five (25-Sep-2026, docs 2026-09-25-openmind-agent-expert-debate-5.md picks 2 and 3, OpenMind #arc-3 17:14 ET;
#       Claude Opus 5.5 (Bubba)), each an AgentConfig switch, off by default, on top of debate four's kept d4_opt:
#       flat_prefs (pick 2): goals.Preferences(flat_until_clear=True): until the play's first clear every ordinary outcome's
#         learned preference is 0 (game-over aversion and the budget term stay), so before a clear expected free energy is
#         driven by information gain; after the first clear preferences are learned as before;
#       carry_library (pick 3): library.RuleLibrary: on a level clear, a RESET (the agent's or an archive return's) and a
#         lost life (budget.survived_ends went up) the rule sets that hold are stored; the posterior's MDL prior prices the
#         library's rules at a discount (BeliefState.library); after each such event the library's sets re-enter the
#         posterior by exact replay (add_rulesets); on a level change the self's learned moves are tempered to a starting
#         belief the new level can overturn (a RESET or lost life keeps the full counts). What already carried before
#         this switch, checked on Locksmith / Warehouse: the whole SlowMemory (rule-set posterior, goal beliefs,
#         preferences, habits, the self's learned moves, the explorer's press counts) survives clears and RESETs within a
#         play; only FastMemory, the explorer's per-level touch set and the archive's cells are per level.
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
from .perception import BUTTONS, RESET, Action, Perceiver, Scene, Transition
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
    # Debate picks (24-Sep-2026, docs 2026-09-24-warehouse-expert-debate.md); all default off = the old behaviour
    use_self: bool = False             # 1: contingency-based self (selfmodel.ContingentSelf)
    tl_facing: bool = False            # 2: the learned Facing relation in tensor logic (with use_tl)
    use_epistemic: bool = False        # 3: sampled-posterior disagreement + soft local-context novelty (epistemic.py)
    use_archive: bool = False          # 4: Go-Explore-style archive of object configurations (archive.py)
    goal_contrast: bool = False        # 5: goals from contrast after a clear (goals.GoalBeliefs contrast)
    # Stage one (25-Sep-2026, docs 2026-09-25-warehouse-expert-debate-2.md); default off = the old behaviour
    explore_handoff: bool = False      # explorer trip = option, ends on arrival / surprise, the policy then chooses
    use_budget: bool = False           # learned gauge forecast + game-over preference in EFE (budget.py)
    # Debate three (25-Sep-2026, docs 2026-09-25-warehouse-expert-debate-3.md); default off
    handoff_efe: bool = False          # 1: interrupting options: EFE-compared interruption, relative surprise, resume
    contact_context: bool = False      # 2: non-moving buttons keyed on the self's contact neighbourhood (epistemic.py)
    budget_learn: bool = False         # 3: learnable run-out belief (lives-gated information) + plan-aware urgency
    # Debate four (25-Sep-2026, docs 2026-09-25-warehouse-expert-debate-4.md); default off, need handoff_efe
    option_value: bool = False         # 1: continuing = the trip target's value spread over its remaining steps; check log
    try_once: bool = False             # 1: first contact with a new colour -> the best non-moving button, once
    goal_babble: bool = False          # 2: goal babbling over tied goals before the first clear (babble.py), soft reach
    caused_contrast: bool = False      # 2: contrast on a clear counts only action-caused progress (with goal_contrast)
    contact_gated: bool = False        # 3: contact novelty, only after every button was pressed GATE_TRIES times (moveless)
    # Debate five (25-Sep-2026, docs 2026-09-25-openmind-agent-expert-debate-5.md); default off
    flat_prefs: bool = False           # 2: flat outcome preferences until the play's first clear (goals.Preferences)
    carry_library: bool = False        # 3: rule library + MDL reuse discount + self-move carry-over (library.py)
    library_cfg: Any = None            # 3: library.LibraryConfig or None (defaults)


EPISTEMIC = {"w_dis": 1.0, "w_lnov": 1.0, "epi_preempt": 0.5}   # PolicyConfig values under use_epistemic
BUDGET = {"w_budget": 1.0}                                       # PolicyConfig values under use_budget
CONTACT = {"w_ceig": 1.0}                                        # PolicyConfig values under contact_context
BABBLE = {"w_babble": 2.0}                                       # PolicyConfig values under goal_babble (= Preferences' w_goal)
GATE_TRIES = 10                                                  # contact_gated: presses of every button before the gate opens


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
        if self.cfg.use_epistemic:
            import dataclasses
            self.cfg.policy = dataclasses.replace(self.cfg.policy, **EPISTEMIC)
        if self.cfg.use_budget:
            import dataclasses
            self.cfg.policy = dataclasses.replace(self.cfg.policy, **BUDGET)
        if self.cfg.contact_context or self.cfg.contact_gated:
            import dataclasses
            self.cfg.policy = dataclasses.replace(self.cfg.policy, **CONTACT)
        if self.cfg.goal_babble:
            import dataclasses
            self.cfg.policy = dataclasses.replace(self.cfg.policy, **BABBLE)
        if self.cfg.explore_handoff and explorer is not None:
            explorer.cfg.handoff = True
        if self.cfg.handoff_efe and explorer is not None:
            explorer.cfg.handoff = True
            explorer.cfg.interrupt = True
            explorer.cfg.try_once = self.cfg.try_once
        self.archive = None                 # archive.GoExploreArchive when use_archive
        self.budget = None                  # budget.BudgetModel when use_budget
        self.budget_resets = 0              # policy RESETs while the budget was urgent
        self.budget_returns = 0             # policy RESETs turned into archive returns
        self.budget_abandoned = 0           # explorer trips / archive replays dropped because the budget was urgent
        self.epi_preempts = 0
        self.check_log: list = []           # debate four: [step, trigger, won, action, k, G_cont, G_button, G_move] per check
        self.presses: dict = {}             # button -> presses this play (debate four pick 3's gate)
        self.babble = None                  # babble.GoalBabbler when goal_babble
        self.caused = None                  # babble.CausedChange when goal_babble or caused_contrast
        self.library = None                 # library.RuleLibrary when carry_library (debate five pick 3)
        self._ends_seen = 0                 # budget.survived_ends already handled (a lost life = a restart)
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
            tl_cfg = self.cfg.tl_cfg
            if self.cfg.tl_facing:
                import dataclasses
                from .tl.learner import TLConfig
                tl_cfg = dataclasses.replace(tl_cfg or TLConfig(), facing=True)
            tl = make_tl(tl_cfg)
            self.tl_source = TLSource(tl)
            self.proposer.tl = self.tl_source
            self.proposer.templates = self.cfg.tl_templates
            if self.explorer is not None and self.cfg.tl_plan:
                self.explorer.cfg.search = "tl"
        selfm = None
        if self.cfg.use_self:
            from .selfmodel import ContingentSelf
            selfm = ContingentSelf()
        ctx = ContextBuilder(hdc, tl, selfm, facing=self.cfg.tl_facing or self.cfg.use_epistemic)
        if self.cfg.use_epistemic:
            from .epistemic import LocalNovelty
            ctx.lnov = LocalNovelty()
        if self.cfg.contact_context or self.cfg.contact_gated:
            from .epistemic import ContactContext
            ctx.contact = ContactContext()
            ctx.contact.open = not self.cfg.contact_gated    # debate four pick 3: closed until every button was tried
        self.presses = {}
        goals = GoalBeliefs(contrast=self.cfg.goal_contrast, soft_reach=self.cfg.goal_babble,
                            track_prog=self.cfg.goal_babble or self.cfg.caused_contrast)
        self.babble = self.caused = None
        if self.cfg.goal_babble:                       # debate four pick 2
            from .babble import GoalBabbler
            self.babble = GoalBabbler(seed=self.cfg.seed)
            self.caused = self.babble.caused
            ctx.babble = self.babble
        elif self.cfg.caused_contrast:
            from .babble import CausedChange
            self.caused = CausedChange()
        if self.cfg.caused_contrast:
            goals.caused = self.caused
        self.slow = SlowMemory(BeliefState(self.cfg.max_hypotheses, self.cfg.max_records,
                                           dl_weight=self.cfg.dl_weight), goals,
                               Preferences(flat_until_clear=self.cfg.flat_prefs), HabitPrior(), ctx)
        self.library, self._ends_seen = None, 0
        if self.cfg.carry_library:                     # debate five pick 3
            from .library import RuleLibrary
            self.library = RuleLibrary(self.cfg.library_cfg)
            self.slow.beliefs.library = self.library
        self.slow.ctx.begin(scene)
        if self.cfg.use_archive:
            from .archive import GoExploreArchive
            self.archive = GoExploreArchive(seed=self.cfg.seed)
            self.archive.begin(ctx, scene, level)
        if self.cfg.use_budget:
            from .budget import BudgetConfig, BudgetModel
            self.budget = BudgetModel(BudgetConfig(learn_end=self.cfg.budget_learn))
            self.budget.c_over = -self.slow.prefs.c_game_over
            self.budget.reset_cost = self.cfg.policy.cost_reset
            self.budget.begin(grid)
            ctx.budget = self.budget
        self.fast = FastMemory(level, scene)
        self.slow.goals.bind_level(scene)
        self.n_steps = 0
        self.check_log = []
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
            babbled = f.plan.goal.startswith("babble:")
            if babbled:
                self.babble.plan_steps += 1
            self.last_decision = Decision(a, "babble" if babbled else "plan")
            return a
        f.plan = None
        cc = s.ctx.contact
        if self.cfg.contact_gated and cc is not None and not cc.open:   # debate four pick 3: open once, stays open
            buttons = [b for b in self.valid if b in BUTTONS]
            if buttons and all(self.presses.get(b, 0) >= GATE_TRIES for b in buttons):
                cc.open, cc.open_at = True, self.n_steps
        if self.budget is not None and self.cfg.budget_learn:   # debate three pick 3: what the current plan still needs
            ex, arc = self.explorer, self.archive
            self.budget.plan_left = (len(arc.queue) if arc is not None and arc.queue
                                     else len(ex.plan) if ex is not None and ex.plan else 0)
        urgent = self.budget is not None and self.budget.urgent(self.budget.plan_left)
        bb = self.babble
        if bb is not None:                             # debate four pick 2: babbling only before a clear, never urgent
            bb.on = bb.active(s.goals, urgent)
            if bb.on and bb.key is None:
                bb.sample(s.goals, scene, self.n_steps)
        if urgent:                                    # stage one: the gauge is about to run out, the policy chooses
            if self.archive is not None and self.archive.queue:
                self.archive.abandon()
                self.budget_abandoned += 1
            if self.explorer is not None and self.explorer.plan:
                self.explorer.plan, self.explorer.target = [], None
                self.budget_abandoned += 1
            return self._policy_step(scene, urgent)
        if self.archive is not None:                  # debate pick 4: a return to a rare configuration
            a = self.archive.next_action(self.valid)
            if a is not None:
                self.last_decision = Decision(a, "return")
                return a
        if bb is not None and bb.on and self.cfg.plan and bb.want_plan(self.n_steps):
            a = self._babble_plan(scene)
            if a is not None:
                return a
        if self.explorer is not None and not self._epistemic_preempt(scene):
            if self.cfg.handoff_efe and self.explorer.check is not None:
                a = self._interrupt(scene)            # debate three pick 1
                if a is not None:
                    return a
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
        return self._policy_step(scene, False)

    def _babble_plan(self, scene) -> Optional[Action]:
        """Debate four pick 2: plan toward the babbled goal with the beam planner under one rule set drawn from the
        tempered posterior; a plan found (progress above now) replaces the explorer's trip."""
        from .epistemic import sample_hypotheses
        s, f, bb = self.slow, self.fast, self.babble
        g = bb.goal(s.goals)
        if g is None:
            return None
        bb.plan_t = self.n_steps
        bb.attempts += 1
        i = sample_hypotheses(s.beliefs, bb.rng, 1, self.cfg.policy.dis_temp)[0]
        rs = s.beliefs.hyps[i].ruleset
        if len(rs) == 0:
            return None
        rc0 = s.ctx.context(scene, Action(RESET))
        plan = self.planner.plan(scene, self.valid, rs, s.goals, s.ctx, rc0, goal=g)
        if plan is None or not plan.actions:
            return None
        plan.goal = "babble: " + plan.goal
        f.plan, f.plan_step = plan, 1
        bb.plans += 1
        bb.plan_steps += 1
        if self.explorer is not None:                  # the trip in progress is dropped (as when the budget is urgent)
            self.explorer.plan, self.explorer.target = [], None
        self.last_decision = Decision(plan.actions[0], "babble")
        return plan.actions[0]

    def _policy_step(self, scene, urgent: bool) -> Action:
        s = self.slow
        if self.babble is not None and self.babble.on and self.babble.key is not None:
            self.babble.pref_decisions += 1
        d = self.policy.choose(scene, self.valid, s.beliefs, s.goals, s.prefs, s.ctx, s.habits, self.cfg.greedy)
        if self.curiosity is not None:
            d = self.curiosity.rechoose(d)
        if urgent and d.action.name == RESET:
            self.budget_resets += 1
            if self.archive is not None:              # stage one: the RESET becomes a return that fits the budget
                a = self.archive.start_return(self.budget.return_len())
                if a is not None:
                    self.budget_returns += 1
                    d = Decision(a, "return", d.scores, d.gamma)
        self.last_decision = d
        return d.action

    def _interrupt(self, scene) -> Optional[Action]:
        """Debate three pick 1: at an explorer check, interrupt the trip only if the best action that does not move the
        self beats (lower G) every action that does; continuing the trip is worth at least the best one-step move. Up to
        explorer.cfg.dwell interrupting actions per check; then the trip resumes. Debate four: with option_value the
        trip's own option value replaces the best move's G (_option_value); with try_once a new contact class gets one
        press of the best non-moving button first."""
        from .policy import candidate_actions
        ex, s, pc = self.explorer, self.slow, self.cfg.policy
        reason = ex.check
        log = self.cfg.option_value or self.cfg.try_once
        cands = candidate_actions(scene, self.valid, pc.max_clicks, pc.allow_reset)
        moving = [a for a in cands if a.is_button and s.ctx.controlled_direction(a.name) is not None]
        others = [a for a in cands if a.name != RESET and a not in moving]
        if not moving or not others or ex.dwell >= ex.cfg.dwell:
            if log:
                self.check_log.append([self.n_steps, reason, "dwell" if moving and others else "none",
                                       None, None, None, None, None])
            ex.check, ex.dwell, ex.try_pending = None, 0, False   # nothing the trip cannot do itself
            return None
        self.policy.draw(s.beliefs)
        scores = [self.policy.score(s.ctx.context(scene, a), s.beliefs, s.goals, s.prefs, s.ctx) for a in cands]
        g_move = min(sc.G for sc in scores if sc.action in moving)
        g_cont, k = (self._option_value(scores, g_move) if self.cfg.option_value else (g_move, None))
        best = min((sc for sc in scores if sc.action in others), key=lambda sc: sc.G)
        rec = [self.n_steps, reason, "trip", None, k, round(g_cont, 4), round(best.G, 4), round(g_move, 4)]
        if self.cfg.try_once and ex.try_pending:     # debate four pick 1: a new kind of contact, try it once
            ex.try_pending = False
            nm = [sc for sc in scores if sc.action in others and sc.action.is_button
                  and ex.tries.get(sc.action.name, 0) >= ex.cfg.min_tries]
            if nm:
                pick = min(nm, key=lambda sc: sc.G)
                ex.dwell += 1
                ex.interrupts["try_once"] = ex.interrupts.get("try_once", 0) + 1
                rec[2], rec[3], rec[6] = "try_once", pick.action.name, round(pick.G, 4)
                self.check_log.append(rec)
                self.last_decision = Decision(pick.action, "tryonce", scores)
                return pick.action
        if best.G < g_cont:
            ex.dwell += 1
            ex.interrupts[reason] = ex.interrupts.get(reason, 0) + 1
            if log:
                rec[2], rec[3] = "button", best.action.name
                self.check_log.append(rec)
            self.last_decision = Decision(best.action, "handoff", scores)
            return best.action
        if log:
            self.check_log.append(rec)
        ex.check, ex.dwell = None, 0
        return None

    def _option_value(self, scores: list, g_move: float) -> tuple:
        """Debate four pick 1: (G of continuing the trip, its remaining steps k). The trip's worth is its target: the EFE
        of the arriving move (the path's last button) with its local novelty taken at the target's colour, spread over the
        k steps left, each costing a button press: G_cont = c + (G_target - c) / k (semi-Markov option value). The trip in
        progress, else the next one the explorer would start here (peek); with none, the best move's one-step G."""
        ex, s, pc = self.explorer, self.slow, self.cfg.policy
        if ex.plan:
            path, target = ex.plan, ex.target
        else:
            found = ex.peek(self)
            if found is None:
                return g_move, 0
            path, target = found
        last = Action(path[-1][0])
        sc = next((x for x in scores if x.action == last), None)
        if sc is None or target is None:
            return g_move, 0
        g_t = sc.G
        ln = s.ctx.lnov
        if ln is not None and pc.w_lnov > 0:
            x = ln.code(frozenset({int(target.colour)}))
            m = ln.mem.get(last.name)
            n = 0.0 if (m is None or x is None) else max(float(ln.vsa.sim(m, x)), 0.0)
            g_t -= pc.w_lnov * (1.0 / (1.0 + n) - sc.local_novelty)
        k = len(path)
        c = pc.cost_button
        return c + (g_t - c) / k, k

    def _epistemic_preempt(self, scene) -> bool:
        """Debate pick 3: a button with no learned move (the explorer can only walk) that is informative HERE
        (sampled-posterior disagreement + local novelty >= epi_preempt) gets the step instead of the explorer."""
        pc = self.cfg.policy
        if pc.epi_preempt <= 0:
            return False
        s = self.slow
        tries = self.explorer.tries if self.explorer is not None else {}
        cands = [b for b in self.valid if b not in ("ACTION6", "RESET") and s.ctx.controlled_direction(b) is None
                 and tries.get(b, 0) >= 3]                   # tried, and still no learned move: not a walking button
        if not cands:
            return False
        self.policy.draw(s.beliefs)
        for b in cands:
            rc = s.ctx.context(scene, Action(b))
            dists = [d for _, _, _, d in s.beliefs.predictions(rc)]
            dis, lnov = self.policy.epistemic(rc, dists, s.ctx)
            if pc.w_dis * dis + pc.w_lnov * lnov >= pc.epi_preempt:
                self.epi_preempts += 1
                return True
        return False

    def _idle(self, tr) -> Optional[bool]:
        """Debate four pick 2 (babble.CausedChange): True = a button with a learned move did not move the self (the action
        did nothing to the agent), False = the self moved, None = not counted (non-moving button, no self, unscored)."""
        sm = self.slow.ctx.selfm
        if sm is None or sm.last_delta is None or not tr.scored:
            return None
        if tuple(sm.last_delta) != (0, 0):
            return False
        a = tr.action
        return True if (a.is_button and self.slow.ctx.controlled_direction(a.name) is not None) else None

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
        self.presses[action.name] = self.presses.get(action.name, 0) + 1
        rc = s.ctx.context(pre, action)                      # before the outcome: prequential
        if s.ctx.lnov is not None:                           # debate pick 3: count this (action, local context)
            s.ctx.lnov.observe(rc, s.ctx.controlled_direction)
        tr = self.perceiver.observe(action, grid, level_completed, game_over, level)
        if s.ctx.contact is not None:                        # debate three pick 2: visit + outcome in this contact
            s.ctx.contact.observe(rc, tr, s.ctx.controlled_direction)
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
        if self.caused is not None:                   # debate four pick 2: after the self has seen this step
            self.caused.observe(s.goals.last_prog, self._idle(tr))
        if self.babble is not None:
            self.babble.step(s.goals, tr, self.n_steps)
        if self.explorer is not None:
            self.explorer.observe(self, action, tr)
        if self.archive is not None:
            self.archive.observe(s.ctx, tr, self.perceiver.level)
        if self.budget is not None:
            self.budget.observe(tr, grid)
        rep = StepReport(tr, sur)
        if f.plan is not None:
            expected = f.plan.expected[f.plan_step - 1] if 0 < f.plan_step <= len(f.plan.expected) else None
            if sur.spike or expected != tr.label:
                f.plan = None
                rep.plan_dropped = True
        f.steps += 1
        self.n_steps += 1
        restart = self._restart(tr)
        if tr.level_completed or tr.reset:
            self._new_level(self.perceiver.current, self.perceiver.level)
        if restart is not None:                        # debate five pick 3: keep what held, carry it over
            self._carry(restart)
        if sur.spike and self.tl_source is not None and tr.scored:
            self.tl_source.surprise(tr.index)          # structure test pointed at the surprising step
        if sur.spike or tr.level_completed or self.n_steps % self.cfg.propose_every == 0:
            rep.proposed = self.propose()
        return rep

    def _restart(self, tr) -> Optional[str]:
        """Debate five pick 3: "clear", "reset" or "life" (the budget saw a run-out survived: a life lost, the level
        restarted) when the library is on and this step was one; else None. Snapshots before the level changes."""
        if self.library is None:
            return None
        why = "clear" if tr.level_completed else "reset" if tr.reset else None
        if self.budget is not None and self.budget.survived_ends > self._ends_seen:
            self._ends_seen = self.budget.survived_ends
            why = why or "life"
        if why is not None:
            self.library.snapshot(self.slow.beliefs, why, self.n_steps)
        return why

    def _carry(self, why: str) -> None:
        """Debate five pick 3: after a clear / restart the library's rule sets re-enter the posterior; on a new level the
        self's learned moves become a starting belief (library.temper_moves)."""
        if why == "clear":
            self.library.temper_moves(self.slow.ctx.selfm)
        self.library.seed(self.slow.beliefs)

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
