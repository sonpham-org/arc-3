<!--
Author: Claude Opus 5.5 (Bubba)
Date: 23-September-2026
PURPOSE: Architecture, active-inference mapping, evidence trail, run instructions and known gaps
for the rule discovery prototype written at OpenMind's request in #arc-3 (23-Sep-2026 21:03 ET).
The code is written but has NOT been run: only python3 -m py_compile was used on it.
SRP/DRY check: Pass - package README; the design record is provenance event 560271a2, the evidence
is ~/bubba-workspace/docs/2026-09-23-efe-trace-analysis-first3.md and the book notes are
~/bubba-workspace/docs/2026-09-23-active-inference-ideas-for-arc3.md (cited, not restated).
-->

# rulediscovery1__fepInspired: a rule discovery agent for ARC-3 (prototype, not yet run)

OpenMind asked: "build a prototype of such a rule discovery system for ARC, consider what you learned
about the free energy principle. Don't yet run the code." This is that prototype. The language model
stops pressing buttons and becomes a theorist; the loop around it (perceive, believe, experiment,
plan) is explicit, measurable and cheap, and every piece can be scored offline on saved plays before
spending Kaggle hours.

Status: written only. Nothing in this folder has been executed except `python3 -m py_compile`.
No harness, prompt, Kaggle job or Jethro file was changed; nothing is committed.

## Architecture

```
 frame (64x64 grid) + flags
        |
        v
 perception.py   Perceiver: HUD mask -> components (object_events) -> tracked objects
        |        Transition: action, pre/post Scene, label in the object_events alphabet
        |        invariant: pre of step t+1 == post of step t
        v
 rules.py        ContextBuilder: RuleContext BEFORE the outcome (agency tracker, handcolour
        |        context, previous label, previous label of this context, per-scope "steps since")
        v
 beliefs.py      BeliefState  ----------------------------------------------+
        |          shared chained back-off (round7.Model): hc -> hc+last    |
        |          hypotheses h = RuleSet + DL + loglik + KT miss rate      |
        |          p_h(o) = (1-eps)[o = rule prediction] + eps p_backoff(o) |
        |          posterior  ~ exp(-dl_weight*DL + loglik)                 |
        |          surprise, Bayesian surprise, spike monitor               |
        |          BMR (drop rules), prune to top K                         |
        |          NoveltyModel: Dirichlet per context, EIG, Dirichlet BMR  |
        v                                                                   |
 hypotheses.py   TemplateFitter (Move, Toggle, Contact, Counter, NoOp,      |
        |        Persist) + RuleProvider (stub for model-written CodeRules) |
        |        RuleSetBuilder: beam search by the posterior's own score --+
        v
 goals.py        GoalBeliefs (reach / match / fill / empty / align / count, updated on clears and
        |        on "satisfied but no clear"), Preferences ln C(o)
        v
 policy.py       G(a) = -salience -novelty -pragmatic -empowerment + cost
        |        P(a) ~ E(a)^1 * exp(-gamma G(a)); Thompson fast path;
        |        BeamPlanner in imagined boards when the posterior is concentrated
        v
 agent.py        RuleDiscoveryAgent (fast memory per level, slow memory per play),
                 TextSummaryAdvisor (text for the harness model), HarnessAdapter
 offline_eval.py replay saved plays: prequential nats vs the chain back-off, policy agreement
```

`_distill.py` is the only file that touches `sys.path`; it re-exports the round-four-to-seven modules
from `../distill/` (object_events, agency_contexts, feature_detectors, heldout_yardstick,
efe_trace_analysis; round7 and ebul_perception lazily). Nothing there is copied or edited.

## Mapping to active inference (Parr, Pezzulo & Friston)

| Concept | Where | How |
|---|---|---|
| Likelihood / observation model A | perception.py | frames -> objects -> event labels; hand-built first, the EBUL residual left for later |
| Transition model B | rules.py, beliefs.py | a posterior over rule sets (structures), each a decision list predicting next-step events, over a shared back-off count model |
| Novelty (information gain about parameters, 7.5) | beliefs.NoveltyModel, policy | efe_trace_analysis.eig of the Dirichlet per handcolour context: count-based, gives inhibition of return |
| Salience (information gain about hidden states / structure, 7.4) | policy.EFEPolicy.score | H[mixture predictive] - E_h H[p_h]: where surviving rule sets disagree |
| Expected free energy G (eq. 2.6) | policy.py | -salience - novelty - pragmatic - empowerment + action cost |
| Prior preferences C | goals.Preferences | ln C(o): clears high, game over low, outcomes before a game over penalised, online p(clear soon given o) |
| Hidden goal state | goals.GoalBeliefs | reach / match / fill / empty / align / count over colours, updated on clears and on satisfied-without-clear |
| Precision gamma | policy.precision | rises as the rule-set posterior concentrates |
| Habits E | policy.HabitPrior | prior over action kinds that preceded clears; carried across levels |
| Bayesian model reduction (Box 7.3) | beliefs.BeliefState.reduce, beliefs.dirichlet_bmr | drop a rule when the reduced set has higher posterior (exact by replay); closed-form Dirichlet BMR to ask whether a context needs its own distribution |
| Structure learning | hypotheses.py | template fitting + beam composition by the posterior score; model-written rules via RuleProvider |
| Two timescales (7.6) | agent.FastMemory / SlowMemory | fast: plan, level baseline; slow: rules, counts, goals, habits across the levels of one play |
| Surprise / Bayesian surprise | beliefs.StepSurprise | -ln p under the mixture; KL between rule-set posteriors; spikes trigger re-proposal and replanning |
| Empowerment (early exploration) | policy.empowerment_bonus | count proxy for learning which object the buttons control; fades over the first actions of a level |

## Evidence from 23-Sep-2026 behind each choice

- Object-event outcomes were the biggest single gain in round four; the rule language predicts
  exactly those labels (object_events alphabet), so rule sets and counts are scored on one yardstick.
- The stale "before" board in efe_trace_analysis.analyse reversed round three's sign; the Perceiver
  always advances the board and two tests pin it (perception and the full agent loop).
- Round seven: the previous outcome carries timers, continuing pushes and toggles (+0.16 nats/step
  held out), but only under the chained back-off (specific -> general); under the plain back-off the
  same key costs 0.4. Hence the shared back-off is round7.Model(chain=True) keyed handcolour ->
  handcolour + previous label, and PersistRule / CounterRule condition on previous events.
- Carrying counts across passes of one game helped; a prior pooled from other games hurt. Slow memory
  is per play and never reads another game.
- Scoring discipline: prequential nats, held-out folds, within one play, paired bootstrap;
  offline_eval.py reuses heldout_yardstick for all of it and selects its few settings on training
  folds only.
- EBUL only for the residual: it is not in this prototype; the obvious slot is a second back-off
  expert mixed 50/50 with the chain (the round-seven best arm).

## How to run later (not done yet)

From `~/GitHub/arc-3/ARC3-Inference/`:

```
python -m pytest rulediscovery1__fepInspired/tests            # the repo's pytest testpaths point at tests/, so name the folder
python -m rulediscovery1__fepInspired.offline_eval --n 250 --split pass --workers 8
python -m rulediscovery1__fepInspired.offline_eval --n 250 --split game --workers 8
```

Live use (after the offline numbers justify it): construct `RuleDiscoveryAgent`, wrap it in
`HarnessAdapter`, call `on_frame(frame, valid_actions)` with each `runtime_state.Frame`, and send the
returned payload through the sandbox's `action()`. `HarnessAdapter.to_harness` imports
`inference.agent.action_names`, which loads the harness package. The harness is not modified.

## Known gaps

- Never executed. Expect the first run to surface bugs; the tests are the first thing to run.
- Rule price: at full MDL price a MoveRule costs about 14 nats, and the chained back-off learns
  deterministic, position-free regularities in a few steps, so rules only pay where they see
  something the counts cannot (look-ahead into walls, contacts, imagined boards for planning).
  `dl_weight` tempers the prior; offline_eval selects it on training folds. Rule sets are scored by
  replay on the steps they were fitted on (two-part code); a purely prequential variant would score
  them only after proposal.
- The language-model rule source is a stub (`StubLLMRuleProvider` returns nothing);
  `InProcessSandbox` is not an isolation boundary; model code must go through the harness sandbox.
- MoveRule moves every instance of a type unless the agency tracker has found the controlled one
  (crates in a push game); pushes of chains, momentum and multi-cell steps are not in the templates.
- Goals are colour-level templates; the likelihood of a clear under a goal uses the progress on the
  last board before the clear (or the MAP-imagined one). The pragmatic label signal was weak in round
  four (within-play AUC 0.59); the goal-progress term is untested.
- The planner follows only the MAP rule set and stops where it is silent; no chance nodes.
- HUD mask is estimated online on a window; a mask change restarts object identity.
- "Lazy" import of round7 buys little: every BeliefState builds a round7.Model, so the first one
  imports round7 -> round4 -> the EBUL modules (numpy / scipy only), and ebul_perception globs the
  trace folders at import. Harmless offline; for live use, round7.Model could move to a small module
  of its own in distill/ (not done: distill/ files were not to be edited).
- Unit tests assert structure (fitted parameters, rule set vs a deliberately wrong one, replay equals
  online scoring), not that rules beat the counts-only model; that is offline_eval's question.
- Mixture over labels treats a label outside one hypothesis's vocabulary as zero there (its unseen
  slot keeps the mass), which slightly understates salience between new labels.
- Cost: offline policy ranking scores every candidate action under every hypothesis at every step;
  use `--no-rank` for the likelihood numbers alone.

## Next steps

1. Run the tests; fix what breaks.
2. Offline, pass and game splits: does the rule-set mixture beat the chain back-off in prequential
   nats, per game type, CIs clear of zero? Which rules survive per game (results JSON lists them)?
3. Does the EFE top choice agree with the actions that preceded clears more than with the rest?
4. Wire the model: send `TextSummaryAdvisor.summarize` to it and parse proposed CodeRules through the
   harness sandbox; score them with the same posterior.
5. Only then a live two-pass A/B inside the harness.

## Local game simulator (env.py, verify_env.py, play_live.py) — 23-Sep-2026

`env.GameEnv` runs a game's own source (docs/static/games/src/) on the vendored ARC engine, so the
simulation is exact; default is Locksmith (ls20, build 9607627b, the Kaggle build). Needs Python 3.10+:
use `ARC3-Inference/.venv/bin/python`.

- `python -m rulediscovery1__fepInspired.verify_env` replays every recorded play and checks every board.
  Locksmith: 43 plays, 5916 of 5916 boards and level counters match, 3.6 s.
- `python -m rulediscovery1__fepInspired.play_live --budget 300 --seeds 3` plays the rule agent and a
  random baseline live, with RESET offered as the harness does. First run (300 actions, 3 seeds): no
  level cleared by either. The perceiver's HUD mask works live (each arrow reads as a clean move of the
  piece, a blocked move reads as residue only), yet the posterior stays "counts only", so the agent never
  plans; it never sends RESET and spends all three lives by about 129 actions. Random survives the 300
  actions only because it hits RESET, which restores the lives.

Locksmith mechanics (read from the source, consistent with the traces): the player block moves one
cell per arrow key; walls block. A key shown bottom-left has a shape, a colour and a rotation; stepping
on a shape, colour or rotation tile cycles that attribute (some tiles ride a track and move each turn).
Walking onto a lock with a matching key opens it; opening every lock clears the level (7 levels). Each
move drains a step bar (1 or 2 per move, set per level; 42 moves per life on level one); refill pickups restore it. An empty bar costs one of 3 lives and
resets the player, key and pickups; the third loss is game over. Spring pads shove the player; some
levels are fogged outside a radius around the player.

Level one, measured on the simulator (breadth-first search over the real game): 89 reachable states,
shortest clear 13 moves (left 3, up 4 to the rotation tile, right 3, up 3 into the lock); only the key's
rotation differs from the lock. The language-model harness cleared level one in 30 of 43 recorded plays,
median about 21 actions.

## Object-contact explorer and d-pad rule (24-Sep-2026)
- `explore.py` (ObjectContactExplorer): trips with the fitted mover to the least recently touched object.
  Pass `explorer=ObjectContactExplorer()` to RuleDiscoveryAgent. Locksmith level one: 10 of 10 seeds.
- `rules.PadMoveRule`: one rule for all arrows of a sprite.
- `game_sweep.py`: random / agent / agent+explorer on any local game build (Ghost Twin and Warehouse
  Associates: no levels yet).
