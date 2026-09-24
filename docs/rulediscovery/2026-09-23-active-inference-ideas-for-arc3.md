<!--
Author: Claude Opus 5.5 (Bubba)
Date: 23-September-2026
PURPOSE: Records, nearly verbatim, the ideas from Parr, Pezzulo & Friston, "Active Inference: The Free
Energy Principle in Mind, Brain, and Behavior" (MIT Press, open access) that look useful for the
ARC-3 agent, as posted to #arc-3 on 23-Sep-2026 at OpenMind's request. Also records the earlier
proposal for an expected-free-energy style action selector. Nothing in the harness was changed.
Source text: ~/bubba-workspace/library/active-inference/book.clean.txt (PDF alongside it).
SRP/DRY check: Pass - first note on active inference for ARC-3; no earlier doc covers it.
-->

# Active inference ideas for ARC-3 (23-Sep-2026)

Requested by OpenMind in #arc-3. Sections read from the text file only: 2.8 (what expected free
energy is), 7.4 (information seeking), 7.5 (learning and novelty), Box 7.3 (structure learning),
and the passages on habits and precision.

## Why it fits

We have not really run RL yet, only prompt changes and the start of supervised fine-tuning. What we
have is the problem active inference was built for: extremely sparse reward (most plays score zero)
and an agent that does not pick informative actions. It often proposes the right hypothesis, then
measures instead of running the probe that would settle it.

## Six ideas from the book

1. **One objective for exploring and exploiting (eq. 2.6).**
   G(π) = −information gain − pragmatic value = expected ambiguity + risk, all in nats. The book
   presents this as dissolving the explore/exploit dilemma. For ARC-3: in the early turns of a level
   the goal is hidden, so the pragmatic term is near flat and information gain should drive action.
   That is the formal version of "press something to find out".

2. **Salience and novelty are different; novelty is our gap (7.4 vs 7.5).**
   Salience is information gain about hidden states (where am I, what is the goal). Novelty is
   information gain about model parameters. The book: "salience is to inference what novelty is to
   learning". In ARC-3 the main unknown is what each action does, the B (transition) matrix, so
   novelty is the term we are missing most.

3. **Novelty comes nearly free from counts.**
   With Dirichlet priors, parameter uncertainty is a function of pseudo-counts: how often an action
   was tried in a given context. Low counts mean high novelty. The book notes that "inhibition of
   return" falls out of this: the agent stops revisiting outcomes it is already confident about.
   That targets a failure we saw directly (the agent pressing right dozens of times in Skewer
   Kebabs). A per-(action, object/region) count bonus needs no extra model calls.

4. **Habits plus goal-directed planning.**
   Policy prior roughly softmax(ln E − γG), where E is a habit prior and γ is precision. Our solved-
   level traces fit here as E, a learned "what usually works" prior, while G stays computed online.
   γ sets how much to trust planning over habit.

5. **Structure learning / Bayesian model reduction (Box 7.3).**
   Keep one broad model and prune elements when that lowers free energy, without inverting every
   candidate model separately. For ARC-3: hold a broad set of mechanic hypotheses and cheaply drop
   the ones the observations contradict.

6. **Two timescales (7.6).**
   Slow beliefs (what the game's goal is) sit above fast ones (what this press just did). That
   matches the game-tier / level-tier notes our harness already carries, and supports carrying the
   learned mechanics across levels.

## Earlier proposal: an expected-free-energy action selector inside the harness

1. The model keeps a few explicit hypotheses about the mechanics, written as small predictors in the
   sandbox ("if I press X, cell Y changes like Z").
2. For each candidate action, run every hypothesis's prediction. Score the action by how much the
   hypotheses disagree (a stand-in for information gain), minus an action cost, since scoring
   rewards fewer actions.
3. Pick with softmax(−γG). After acting, reweight the hypotheses by which ones predicted the new frame.
4. Once a goal hypothesis looks credible, shift weight to the pragmatic term.

Costs: extra predictions each turn eat into a tight time budget, and hypotheses written by a language
model can be badly wrong.

## Cheapest first step

Add a count-based novelty bonus with inhibition of return to action choice; it needs no extra model
calls. Test offline first: check whether our solved levels show more novel early actions than
failed ones. If they do, wire it into the live harness.

## Caveat

The book's examples are small, fully specified discrete models. In ARC-3 the model has to supply the
state factorisation (which objects matter), and that is where it can go wrong.
