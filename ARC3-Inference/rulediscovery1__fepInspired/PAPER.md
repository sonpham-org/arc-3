<!--
Author: Claude Opus 5.5 (Bubba)
Date: 23-September-2026
PURPOSE: Short paper-style description of the rule-discovery prototype in this package, requested by
OpenMind in #arc-3 (21:24 ET). Explains what ARC-3 measures, the offline evidence that shaped the
design, the architecture module by module, the free-energy formulation, the policy, the evaluation
plan, limitations, and references. Companion to README.md (how to use). Nothing in this package has
been executed yet; statements about behaviour describe intended design, not measured results.
SRP/DRY check: Pass - README.md covers usage; this file covers rationale and literature only.
-->

# Rule Discovery for ARC-3 as Active Inference over Small Programs

*Prototype write-up, 23 September 2026. Code in this folder is written but not yet run.*

## Abstract

ARC-3 games give no instructions: an agent must discover what its actions do and what wins a level,
from few interactions it chooses itself, and then compose those rules into a plan. We describe a
prototype agent that treats this as active inference over a space of small rule programs. Frames
are parsed into objects and step-wise events; a template-based rule language predicts next-step
events; rule sets are weighted by their prequential code length with an Occam prior and pruned by
Bayesian model reduction; actions are chosen by expected free energy, whose epistemic part is the
disagreement between surviving rule sets plus count-based novelty and whose pragmatic part comes
from inferred goal hypotheses. A planner takes over once beliefs concentrate and replans on surprise.
The design follows directly from an offline analysis of about 300 recorded Flash-Next plays, which
showed that event-level outcome descriptions, the previous step's outcome, and chained back-off are
what make action outcomes predictable.

## 1. What ARC-3 measures

If reasoning means learning rules and combining them into valid conclusions, ARC-3 measures
reasoning with two twists: the agent collects its own data (experiment design is part of the task),
and efficiency counts (few actions, few observations). Three other factors are bundled into the
score: perception (turning pixels into objects and events), exploration policy (whether the
informative action is tried at all), and execution. In our recorded plays of a language-model agent,
failures are dominated by perception and exploration, not by failure to compose known rules: the
agent often states the right hypothesis and never runs the probe that would settle it.

## 2. Evidence from the offline trace analysis

Seven offline rounds on recorded plays (53 to 250 plays, 20 games; scoring = prequential nats per
step of an online Dirichlet-categorical model, within one play, held-out plays and held-out whole
games, paired bootstrap intervals) established:

- **Outcome description matters most.** Describing each step's change as object events (moved by
  dx, dy; recoloured; appeared; vanished) made every context model beat a context-free baseline by a
  wide margin; crude "how many cells changed" outcomes hid almost all structure.
- **Static board features saturate quickly.** After button identity and the clicked object's shape
  and colour, 36 further hand-built detectors added nothing on held-out games.
- **The previous step's outcome carries the missing information** (timers that tick every second
  step, pushes that continue, toggles that flip), but only under a *chained* back-off from the
  specific context to the general one; with a flat back-off it hurts.
- **Learned perception is useful as a residual.** A small EBUL-style ternary code trained to be
  predictive, blended 50/50 with the hand-built model, adds a small reliable gain; alone it loses,
  and on unseen games it is no better than random weights.
- **Method lesson.** A replay bug (the pre-action board was never advanced) reversed the headline of
  three rounds; the prototype's tests pin the board advance explicitly.

## 3. Architecture

| Module | Role |
|---|---|
| `perception.py` | Frame to `Scene` (objects: colour, shape type, bounding box), `HudMasker` for status strips, `ObjectTracker` across frames, `Perceiver` turning each step into a `Transition` with its event label (reuses the offline event coder). |
| `rules.py` | The rule language. `MoveRule`, `ClickToggleRule`, `ContactRule`, `CounterRule`, `NoOpRule`, `PersistRule` (repeat the previous event), and `CodeRule` for programs proposed by a language model, run through a sandbox interface. Each rule has a description length (`DLContext`). A `RuleSet` predicts a distribution over next-step events. |
| `hypotheses.py` | `TemplateFitter` instantiates rules consistent with the transitions seen so far; `RuleSetBuilder` combines them; `HypothesisProposer` also accepts language-model proposals (stubbed: `StubLLMRuleProvider` returns nothing). |
| `beliefs.py` | `BeliefState`: posterior over rule sets from Occam prior and prequential likelihood, with a `BackoffModel` so unexplained events do not zero a hypothesis; `NoveltyModel` (Dirichlet counts); closed-form `dirichlet_bmr` for Bayesian model reduction; `SurpriseMonitor` (surprisal and Bayesian surprise per step). |
| `goals.py` | Goal hypotheses (`ReachGoal`, `MatchGoal`, `FillGoal`, `EmptyGoal`, `AlignGoal`, `CountGoal`) scored on level clears and failures; `Preferences` turn them into pragmatic value. |
| `policy.py` | `EFEPolicy`: expected free energy per candidate action, `HabitPrior`, adaptive `precision`, `empowerment_bonus`, Thompson fast path; `BeamPlanner` for planning in the believed model. |
| `agent.py` | `RuleDiscoveryAgent`: perceive, update beliefs, propose hypotheses, choose action. `FastMemory` per level, `SlowMemory` (rules, goal beliefs) across levels within a play. `TextSummaryAdvisor` produces a short summary for a language model; `HarnessAdapter` is the interface to the existing agent harness. |
| `offline_eval.py` | Replays recorded plays: prequential nats of the belief model and agreement between the policy's chosen probe and the recorded action. |

## 4. Free-energy formulation

**Generative model.** Hidden state is the scene; the transition model (the book's B) is the unknown
rule set. Observations are event labels. Learning the rule set is parameter/structure learning.

**Beliefs.** For rule set *R* with description length *L(R)* (in nats), the log posterior after
steps 1..t is −λ·*L(R)* + Σ ln p(o_s | R, context_s), where λ (`dl_weight`, default 1 = plain
two-part MDL) is a temperature on the Occam prior. It exists because the chained back-off count
model already learns regular behaviour within a few steps, so at full price a rule may rarely pay
for itself within one play; the offline evaluator compares λ = 1 and λ = 0.25 and is meant to pick
λ on training games only. In the log posterior above, each predictive term is the rule set's
prediction mixed with a chained back-off count model (specific context, then the hand-built colour
key, then pooled outcomes). This is the prequential (minimum-description-length) code length.
Structure is pruned by Bayesian model reduction: for a Dirichlet-categorical, the evidence of a
reduced prior given the full posterior has a closed form, so extra structure is removed when it does
not pay for itself.

**Expected free energy of an action a.** G(a) = −[w_sal · salience(a) + w_nov · novelty(a)
+ w_prag · pragmatic(a) + w_emp · empowerment(a)] + cost(a), as in `EFEPolicy.score`, where

- *salience* is the expected information gain about which rule set is true: the mutual information
  between the next event and the rule-set identity under the current posterior (disagreement among
  survivors, as in BALD);
- *novelty* is the expected information gain about count parameters from Dirichlet pseudo-counts,
  which yields inhibition of return automatically;
- *pragmatic* is the expected log preference under goal hypotheses weighted by their posterior;
- *empowerment* is a bonus early in a level for actions that reveal what the agent controls;
- *cost* differs for buttons, clicks and undo, because ARC-3 rewards action efficiency.

**Policy.** P(a) ∝ exp(ln E(a) − γ G(a)), with habit prior E and precision γ that rises from γ0
toward γ0(1 + κ) as the rule-set posterior entropy falls (explore while uncertain, commit once
confident). A Thompson path samples one rule set and acts greedily under it when compute is short.

**Two timescales.** Fast beliefs (this level's layout, recent events) reset per level; slow beliefs
(rules, goal hypotheses) carry across levels within a play.

## 5. Planning

Once the posterior concentrates, `BeamPlanner` searches the believed model for an action sequence
that satisfies the most probable goal hypothesis, minimising actions. Execution monitors surprise;
a spike (an event the model assigned low probability) indicates a broken rule and triggers belief
update and replanning.

## 6. Evaluation plan

1. Unit tests on synthetic grids (mover against a wall, toggle, timer every second step, board
   advance). Written, not run. They check structure (the wall rule is found; a true rule set
   outscores a wrong one); they deliberately do not claim that rules beat the count model, which
   is left to the offline run.
2. Offline: prequential nats on held-out whole games within one play, compared with the round-seven
   baselines; agreement of chosen probes with informative recorded actions.
3. Live: a harness mode where the agent (or its `TextSummaryAdvisor` feeding the language model)
   acts, A/B against the current prompt on the Flash-Next bottom seven, two passes per arm on Kaggle,
   judged by levels cleared and actions used.

## 7. Limitations

- Nothing has been executed; all behaviour claims are design intent.
- Open question: whether explicit rules beat the chained back-off count model at all within one
  play, or only help the policy (probe choice, planning) while the count model does the predicting.
- The rule language covers common mechanics only; unusual games need `CodeRule` proposals, and the
  language-model provider is a stub.
- Goal hypotheses are a fixed menu; games with novel win conditions will be missed until proposals
  arrive.
- Object parsing is connected components with a background threshold; multi-part objects and
  animated boards can break it.
- Planning cost grows quickly with click targets; the beam and candidate caps are untuned.

## References

*Compiled from memory on 23 September 2026. Titles, years and author lists must be checked before
any external use.*

- Chollet, F. (2019). On the Measure of Intelligence. arXiv.
- Parr, T., Pezzulo, G., & Friston, K. J. (2022). *Active Inference: The Free Energy Principle in
  Mind, Brain, and Behavior.* MIT Press.
- Friston, K., Rigoli, F., Ognibene, D., Mathys, C., Fitzgerald, T., & Pezzulo, G. (2015). Active
  inference and epistemic value. *Cognitive Neuroscience.*
- Friston, K., FitzGerald, T., Rigoli, F., Schwartenbeck, P., O'Doherty, J., & Pezzulo, G. (2016).
  Active inference and learning. *Neuroscience & Biobehavioral Reviews.*
- Friston, K., FitzGerald, T., Rigoli, F., Schwartenbeck, P., & Pezzulo, G. (2017). Active
  inference: a process theory. *Neural Computation.*
- Friston, K., Parr, T., & Zeidman, P. (2018). Bayesian model reduction. arXiv.
- Schwartenbeck, P., Passecker, J., Hauser, T. U., FitzGerald, T. H., Kronbichler, M., & Friston,
  K. J. (2019). Computational mechanisms of curiosity and goal-directed exploration. *eLife.*
- Lindley, D. V. (1956). On a measure of the information provided by an experiment. *Annals of
  Mathematical Statistics.*
- Seung, H. S., Opper, M., & Sompolinsky, H. (1992). Query by committee. *COLT.*
- Houlsby, N., Huszár, F., Ghahramani, Z., & Lengyel, M. (2011). Bayesian active learning for
  classification and preference learning. arXiv.
- Russo, D., & Van Roy, B. (2014). Learning to optimize via information-directed sampling. *NeurIPS.*
- Thompson, W. R. (1933). On the likelihood that one unknown probability exceeds another in view of
  the evidence of two samples. *Biometrika.*
- Osband, I., Russo, D., & Van Roy, B. (2013). (More) efficient reinforcement learning via posterior
  sampling. *NeurIPS.*
- Klyubin, A. S., Polani, D., & Nehaniv, C. L. (2005). Empowerment: a universal agent-centric
  measure of control. *IEEE CEC.*
- Tsividis, P. A., et al. (2021). Human-level reinforcement learning through theory-based modeling,
  exploration, and planning. arXiv.
- Tang, H., Key, D., & Ellis, K. (2024). WorldCoder, a model-based LLM agent: building world models
  by writing code and interacting with the environment. arXiv.
- Dawid, A. P. (1984). Present position and potential developments: some personal views.
  Statistical theory: the prequential approach. *JRSS A.*
- Grünwald, P. D. (2007). *The Minimum Description Length Principle.* MIT Press.
- Willems, F. M. J., Shtarkov, Y. M., & Tjalkens, T. J. (1995). The context-tree weighting method:
  basic properties. *IEEE Transactions on Information Theory.*
- Itti, L., & Baldi, P. (2009). Bayesian surprise attracts human attention. *Vision Research.*
