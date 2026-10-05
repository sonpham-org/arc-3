# Spend human trace review on decisions that can improve RL

**Author:** Codex · **Date:** 5 October 2026  
**For:** Mark, Son, and assistants working on the RL loop  
**Status:** Proposal for review. No model calls, training, or product changes are authorized by this document.

## Recommendation

Use a small model to find specific, consequential mistakes worth a human's attention. Keep game outcomes as the automatic performance signal. Ask humans to resolve an uncertain claim or diagnose a recurring failure, rather than rank whole traces whose results we already know.

Mark's time is the scarce resource. The first success criterion is **useful, actionable findings per minute of human review**, not how many traces we label. The eventual criterion is better gameplay on untouched evaluation games.

A Haiku or GPT-Luna model is a candidate for this narrow reading task, not an assumed reliable judge. Start offline on existing training traces. Compare candidate models on the same small sample before choosing one; no claim about their relative accuracy or cost is established here.

## What exists and what is missing

The [current review page](../../README.md#trace-review-which-way-forward-is-better-rl) presents paths from a shared context, collects preferences and turn marks, and exports ratings. The [indexer](../../scripts/trace_review_index.py) now preserves turn input and ordered thinking, tool calls, and results. The [review server](../../railway/rl_review.py) also provides trees, outcomes, and candidate states for further sampling. Reuse these rather than build another trace store.

These observations are based on committed code at `efc37de8b`; those review/indexer files were unchanged on fetched main at `b8511a6bb`. The separate, live training worker has **not** been inspected. Storing a rating is not evidence that the trainer consumes it. The training owner must identify the consumer and its exact use before we commission sustained annotation.

There is relevant experience already: the [September evidence review](2026-09-16-pass-d-e-pilot.md#4-pass-e--how-it-is-kept-independent) caught claims based on unavailable knowledge, a supposedly new experiment that had already been tried, and missing evidence in the export itself. Those are useful starting categories, not proof a smaller model can reproduce the results.

## Divide the work by who can answer it

| Question | First choice |
|---|---|
| Did the level clear, and how many actions did it take? | Engine records and existing score calculation |
| Did the tool fail, or did the board stay unchanged? | Recorded tool results and frame comparison |
| Do two passages make incompatible claims about the same situation? | Small model, with exact citations |
| Is this contradiction explained by a reset, changed state, or new evidence? | Small model checks first; human resolves consequential ambiguity |
| Is this a useful experiment, a misleading conclusion, or a repeated mistake worth correcting? | Focused human judgment when evidence does not settle it |
| Does acting on that correction improve play? | Matched continuation experiments and gameplay evaluation |

Success does not establish that every thought was correct; failure does not establish that every experiment was bad. Conversely, convincing prose does not establish useful reasoning. A failed test can be informative without visibly advancing the board.

## The small model should make allegations with evidence

Give it one decision episode: the relevant earlier claim or observation, the focal turn's actual input, its reasoning and executed action, and the immediate result. Use bounded overlapping windows for recent turns and retrieve older exact passages when needed. A summary may locate evidence; it cannot replace it. Missing or truncated context must be explicit.

Ask for at most one principal issue per episode, or **no issue / insufficient context**. Its response should contain:

- A category: incompatible claims, unsupported certainty, repeated disproven experiment, or mismatch between stated plan and executed action.
- Exact source references and short quotes for both sides of the allegation; frame or action references where relevant.
- One sentence explaining the possible conflict, including whether a state change could explain it.
- One human question and the practical consequence if the allegation is true.

For example, using invented passages: turn 12 says “the plate stayed active after I left”; turn 19 says “I must remain on it” and abandons a route. The question is: **Did anything happen between these turns that makes the later claim valid?** The reviewer can answer without solving the whole game.

Do not treat changed beliefs as errors. “I thought X; this test shows Y” is good updating. Check level changes, resets, object identity, resource state, uncertainty language, and whether the claim was corrected before action. Identical pixels alone do not prove identical hidden state. Repeating an action can be justified by a changed state or a noisy result.

A text-only model must not invent visual facts. Start with text/tool-result conflicts it can actually check. Route visual uncertainty to the board viewer; only add image interpretation if it earns its extra cost and accuracy is measured. Validate quote references mechanically and treat transcript text as data, never as instructions to the reviewer model.

The initial judge should not see the final win/loss, score, model identity, or human verdict. It can see the immediate observation needed to check the focal claim. After that judgment, outcomes can help prioritize the queue. This separates “was the claim supported then?” from hindsight about the ending.

## Give Mark a short queue with a clear purpose

Each card should show the allegation, the two cited passages, the relevant board/action evidence, and one question. Put the model's claim beside the raw evidence; do not make a generated summary the only thing the human reads. Expand the surrounding trace on demand.

Answers: **confirmed issue**, **reasonable revision or experiment**, **insufficient evidence**, or **skip**. A short correction is optional. Confirming a contradiction must not silently mean approving a replacement action or labeling the whole turn bad. Record exactly which judgment the human made.

Prefer recurrent failures that affect a decision and suggest a possible intervention. Group duplicate instances by failure pattern, keep representative examples, and show recurrence counts. Do not ask Mark to adjudicate the same mistake twenty times. Keep a small random sample of unflagged episodes to find what the filter misses; unflagged does not mean correct.

Set a session budget, such as ten minutes, and let it end without clearing the backlog. An empty queue is healthy. No required essays, exhaustive turn ratings, or generic “which path is better?” questions. Pairwise review remains useful when comparable outcomes leave a specific unresolved decision, with the question stated explicitly.

## How this could improve training

There are three different uses, and we should test them in order:

1. **Debug the harness or data.** A missing observation, misleading tool response, or bad context export may explain the behavior. Fixing that can beat teaching the model around it. Route such findings to an assistant rather than repeatedly to Mark.
2. **Target better experiments.** Use confirmed issues to choose existing restart/fork candidates. From the same complete environment state and the same solver context, compare ordinary continuation with a brief correction supported by evidence available at that point. Keep budgets matched and replicate promising results. A merged tree node or identical screen alone is not sufficient. Track this as an assisted experimental arm, not as the unaided benchmark score.
3. **Use evidence of improvement for learning.** Before collecting training labels at scale, name the consumer. One possible path is outcome-based RL on those additional rollouts, retaining the existing reward definition. Another is supervised learning on verified successful recovery continuations under the existing solved-level rule. Human-confirmed diagnosis alone is not a complete SFT target. If a teacher-only correction was supplied, preserve its provenance and test an explicit distillation design; simply removing that input can create an impossible training example.

Do not begin by subtracting reward whenever the small model says “contradiction.” It could punish useful revision or encourage the solver to hide uncertainty. A human agreement label initially evaluates the triage model; it is not automatically a calibrated process reward. Likewise, a downstream win does not prove one particular statement caused it.

Visible reasoning is evidence we can inspect, not guaranteed access to the actual cause of a decision. [Anthropic's faithfulness study](https://www.anthropic.com/research/reasoning-models-dont-say-think) found that reasoning text sometimes omitted influences on answers. That study was not an ARC gameplay evaluation; it supports checking behavior as well as text, not abandoning trace review.

The [round 4 proposal](2026-09-19-arc3-lora-round4-spec.md) already warns against manufacturing rationales and presenting them as human knowledge. Preserve separate provenance for model suspicion, human judgment, proposed correction, and observed continuation outcome.

## A small pilot before any new system

Start with about 50 decision episodes from training games, spread across successful and failed plays, different runs, and several failure patterns. Use existing exports and a temporary results file. No new database, reward model, or live inference service is needed to answer the first question.

Have one or two candidate small models read the same episodes with a short fixed prompt. Compare their selected cases with a simple baseline, such as repeated no-change actions, and a random sample. Independently shuffle the source of cards during review where practical. Do not pay for a large-model second opinion on every turn.

Measure confirmed actionable issues per human minute, false alarms, duplicates, insufficient-context cases, and the cost per useful finding. Audit a random unflagged sample for misses; do not report population recall from the flagged cases alone. Keep some episodes untouched while adjusting the prompt. Model confidence is a sorting hint until checked against human judgments.

**Proposed stop rule:** if most surfaced cases are dismissed, already explained, or have no plausible downstream action, fix the filter or stop. Continue only if it finds more useful issues per human minute than the simple and random baselines. These are proposed decision criteria, not measured results.

Then try a handful of matched recovery experiments. Scale annotation only after that produces a useful intervention; claim training value only after the resulting change improves unassisted gameplay. Follow the repo's ex-`ft09` reporting and replicate promising evaluations two or three times. Fewer contradictions in prose is a diagnostic, not the score we optimize.

## Boundaries and questions for the RL owner

Keep the initial pipeline offline. If useful, it can later inspect completed turns asynchronously. A live coach is a separate intervention with latency and behavior costs and should be evaluated separately.

Apply the active experiment's training fence to source games and all their copies, recolors, traces, and forks **before** triage or judge tuning. The review module's default five-game fence differs from the [seven-game SFT partition](../../datasets/splits/public25-train-test-split.json), and current main also has held-out variants in [test-only games](../../datasets/test-only-games/README.md). Do not assume either list authorizes training across experiments. Resolve the experiment's owner and split, retain `as66` and all test-only variants as excluded, and keep evaluation inspection out of prompt tuning and training-label production.

Before implementation, reviewers should answer:

1. Which worker will consume confirmed findings, and is the first intervention a harness fix, extra sampling, or training data?
2. Can we restore both the environment and the exact model context for a meaningful continuation comparison?
3. Which experiment and game-family fence govern this work?
4. What human-time budget and pilot result justify continuing?

My recommended first move is the offline triage pilot plus a few verified recovery experiments. The small model earns its place by saving human attention; human attention earns its place by producing changes that improve play.
