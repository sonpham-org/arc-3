<!--
Author: Claude Opus 5
Date: 19-September-2026
PURPOSE: Plan and pilot spec for writing the reasoning our action-only demonstrations lack, with
Claude Fable 5.1 as annotator, auditor and grader and GPT-6 Astra's public replays as a
calibration set and a second demo source, all run from a Claude desktop session. Records where
this sits against Son's 15-Sep no-teacher call, the hindsight leak it must not produce, how the
loop runs without API scripts, the checks, the pilot's games, arms and stages, and the decision
rule written before the run.
SRP/DRY check: Pass. The annotation causality rule and the falsifiability gate come from
docs/plans/2026-09-15-step4-segment-and-label-execution.md (passes D and E) and are cited, not
restated. The demo converter and its alignment proof are
docs/trace-findings/2026-09-18-human-demos-to-sft.md. Vendor replay facts are
docs/trace-findings/2026-09-17-vendor-replay-coherence.md. This file holds only the backfill
experiment.
-->

# Reasoning backfill: Fable writes the thinking our demos lack, and we check it cannot cheat

**Status:** plan, 19-Sep-2026. Not approved, nothing built, nothing run. The oracle-test and
compact-multipass results were not in the repo when this was written.

## 0. The question

Our best demonstration data has no reasoning in it. The Boss's human runs (130 records / 3,190
turns windowed; 89 / 2,281 with the held-out fence) are actions only: no think block, and no
`world_model` ledger, which the serving prompt demands on every turn. The converter write-up
calls the missing ledger the largest train/serve gap in the corpus and refuses, correctly, to
invent the Boss's reasoning (`trace-findings/2026-09-18-human-demos-to-sft.md` §7, §9).

Two questions:

1. Can a frontier model (Claude Fable 5.1) write that reasoning, meaning the ledger and a short
   think block per step, **without cheating off the future**, and is what it writes right?
2. Can the checks that tell us it is right also serve as a learning signal that needs neither a
   human nor a teacher?

The pilot answers question 1 on three games and prices question 2. **It trains nothing.**

## 1. Where this sits against the no-teacher call

Son's 15-Sep call stands: no teacher model; RL is on-policy; any bootstrap comes from the 27B's
own wins by rejection sampling (`trace-findings/2026-09-15-qwen27b-finetune-readiness.md` §9,
`plans/2026-09-16-dr-fable-calls-on-the-step5-review.md` §0). Fable can play three roles here,
and they are not equally compatible with that call:

| role | what Fable does | trained text comes from | against the no-teacher call |
|---|---|---|---|
| **G, grader** | scores reasoning: support, correctness | nobody; it is a reward or a filter | compatible: an on-policy reward can come from anywhere |
| **F, filter** | accepts or rejects the 27B's *own* rationales for demo actions | the 27B | compatible: it is the rejection sampling the call prescribes, with a better filter |
| **T, author** | writes the rationale that gets trained on | Fable | **reopens the call**, narrowly: off-policy reasoning text, not trajectories |

The pilot exercises T and G, because T is the hardest role to make clean and G is what judges
it. Phase 2 (§9) puts T against F. If the 27B's own rationales pass the same checks at a similar
rate, no teacher is needed and the call stands untouched. **Training on T text needs Son's
explicit say-so.**

## 2. The failure this must not produce: hindsight leak

An annotator who has seen the whole run writes "heading for the green goal" at step 3, when
nothing at step 3 shows a goal. SFT on that teaches the 27B to hold confident beliefs without
evidence, which is already its worst habit: lf52 scored 1.818 on all four control passes, the
same wrong model each time (`trace-findings/2026-09-14-training-pipeline-proposal-and-ordering.md`).
The step-4 plan named the same risk for pass D ("leaking source knowledge into `memory_in`
produces a record that teaches clairvoyance") and handled it with an instruction. This plan
enforces it by construction and then measures it.

**A leak, as measured here, is a claim that is both unsupported by anything shown so far and
correct against the rulebook.** Unsupported and wrong is a bad guess; the 27B makes those on its
own, and hindsight did not cause it. Unsupported and right is the signature of having seen the
answer.

## 3. The two models

**Claude Fable 5.1** (`claude-fable-5-1`) runs as subagents of a Claude desktop session, in three
roles. No instance plays two roles on the same run.

- **Annotator.** Walks a run one step at a time and writes the reasoning and ledger for the action
  actually taken (§4).
- **Auditor.** A fresh instance that walks the same run by the same progressive reveal and, at
  each step with new claims, labels each one *supported*, *fair hypothesis* or *unsupported*
  before it is shown anything later. This is pass E's "an agent that did not write it", applied
  per claim.
- **Grader.** After a lane finishes, with the game's rulebook in hand, marks every ledger claim
  *correct*, *wrong* or *unverifiable*, and lists rulebook mechanics the ledger never found. It
  sees the whole run; it judges correctness, not support, so it does not need to be causal.

**GPT-6 Astra** cannot be called from the Claude window. It enters only through its public
replays, pulled with unauthenticated GETs by `tools/replay_scrape.py`. It is used two ways, per
`trace-findings/2026-09-17-vendor-replay-coherence.md`:

- **Calibration set: default-harness runs.** These carry prose reasoning in the visible `output`
  field on 90-100% of actions (mean 164-242 characters per action, by effort setting). That prose
  is what Astra thought at the time, written before it saw the next frame. Hide it, have Fable
  annotate the run blind, then compare. It is the only material we have where the in-the-moment
  reasoning is known, so it is the only direct test of whether backfill recovers reasoning or
  invents it.
- **Second demo source: provider-adapter runs (phase 2).** These clear all 25 games with bare
  action outputs (`"ACTION6 40 33"`, 9 characters) and a reasoning summary on only 3-12% of
  actions. They are action-only demos like the Boss's and get backfilled the same way; the sparse
  summaries are free contemporaneous anchors (§9). Their 100% win rate is probably a publication
  filter, not a harness effect (same write-up, Caveats).

Astra-derived text enters no training corpus until someone has read OpenAI's terms on training
with outputs and signed off; the same goes for Fable-authored text under Anthropic's terms.
Owner: Son. The pilot trains nothing and is not blocked on this.

## 4. How it runs from the Claude window

No API keys and no scripts that call models. A Claude Code session in the desktop app is the
orchestrator, Fable runs as its subagents, and Python does everything mechanical.

### 4.1 Pieces

| piece | what | status |
|---|---|---|
| `tools/backfill/stage_steps.py` | recording to one packet per decision step (§4.2), in a staging dir outside the repo | new |
| `tools/backfill/check_steps.py` | mechanical checks M1-M3 (§6), run on each annotation as it lands | new |
| `.claude/agents/backfill-annotator.md` | subagent definition, `model: fable`, `tools: Read` | new |
| `.claude/agents/backfill-auditor.md` | same shape, auditor brief | new |
| `.claude/agents/backfill-grader.md` | same shape, grader brief; the only role given a rulebook path | new |
| `tools/replay_scrape.py` | pulls the Boss runs and the Astra runs, frames kept | reuse; Astra runs go to their own `--recordings-dir`, never into `v0/recordings/` (the human corpus) |
| `tools/fetch_explainer_games.py`, `tools/render_rulebooks.py` | rulebooks for the grader and for arm H-rules | reuse |
| `ARC3-Inference/distill/recordings_to_sft.py` | segmenting, death and reset handling, the observation alignment | import; do not re-derive |

The alignment is the detail most likely to go wrong. The human-demos write-up proved that the
board stored on row k is the *outcome* of row k's action (28 of 28 same-level reset groups
identical, 0 of 119 reset rows equal to the pre-reset board), so decision step k is shown row
k-1's board. The stager imports that logic.

### 4.2 The packet for decision step t

- The board the player saw (row t-1's settled frame) as a PNG at 8x upscale, plus the full 64x64
  text grid at level starts only.
- **What the previous action did:** a mechanical diff of row t-1 against row t-2, as a changed-cell
  count, connected changed regions with bounding box and colour before and after, and the
  level-complete and game-over flags.
- State, `levels_completed`, available actions.
- **The action the player took at step t.**

Not in the packet: row t's resulting board. It arrives in packet t+1 as "what your last action
did", after the annotation for step t has been written and checked.

### 4.3 The loop, per lane

1. The orchestrator spawns an annotator with the brief (§4.4) and packet 1.
2. The annotator replies with one JSON annotation (§4.5).
3. The orchestrator appends it to the lane's `annotations.jsonl`, runs `check_steps.py` on it, and
   only then sends packet t+1 with `SendMessage`. The future is never in the annotator's context
   and never on disk anywhere it is told about.
4. **Every 30 steps the annotator is retired.** A fresh one starts, seeded with the last ledger and
   one-line summaries of the last 30 steps. Thirty is `_PERSISTENT_HISTORY_ASSISTANT_TURNS`, the
   serve-time window, so the annotator lives under the same memory rules as the 27B: its ledger
   must be enough to carry the game forward, which is exactly the ledger we want to teach. It also
   keeps context bounded.
5. The auditor walks the lane afterwards by the same reveal (§3).
6. The grader runs once per lane at the end.

Failed attempts, deaths and resets are annotated like any other step. The SFT converter's prune
(human-demos write-up §4) drops those turns later, but what they taught stays in the ledger that
is carried forward. Action-only records cannot express that at all.

**Residual hole, accepted for the pilot:** the annotator has `Read`, so nothing physically stops
it from opening a raw recording if it goes looking. The brief forbids it, the staging dir holds
only past packets, and the leak measure (§6) would show the effect if it happened.

If Son opts into a Workflow run, the loop is mechanical enough to script: eight annotator lanes
plus their auditors and graders. Otherwise the session drives it directly.

### 4.4 The annotator brief, core rules

- Write the reasoning a strong player would have had **at this step, from what this run has shown
  so far and nothing else.** You know which action they took; explain why a good player takes it
  now.
- "Probing: I don't know what ACTION5 does yet" is a good answer. So is "I can't see why they did
  this"; say so with `explains_action: cannot_explain` rather than inventing a reason.
- Every ledger claim is tagged `VERIFIED(step N)` or `HYPOTHESIS`, the harness's own convention
  (the `world_model` parameter description in `tool_agent.py`). `VERIFIED` needs a step you were
  shown where it happened.
- No genre labels ("this is Sokoban") unless the evidence forces them. The Boss rejected genre
  framing for the agent on 18-Sep for exactly this reason (`plans/2026-09-18-oracle-test-plan.md`
  §1).
- Predict what the action will do, in the structured form below, before you see it.
- Keep the reasoning under 600 characters, in the order observation, hypothesis, uncertainty,
  next experiment (step 3 of the training-pipeline proposal). The cap is a knob; if the
  compact-reasoning multipass settles a style, follow it.

### 4.5 One annotation

```json
{
  "step": 57,
  "reasoning": "Last RIGHT moved the orange 2x2 two cells right; the gray bar did not move. ...",
  "world_model": {
    "action_semantics": "RIGHT: orange 2x2 moves +2 cols VERIFIED(step 55). ACTION5: HYPOTHESIS rotates the selected piece.",
    "object_taxonomy": "...", "hud_map": "...", "win_pattern": "", "level_log": "",
    "cross_level_notes": "", "world_model": "...", "goal_model": "HYPOTHESIS ...",
    "recent_findings": "...", "open_questions": "...", "current_plan": "...",
    "strategy_log": "...", "failed_probes": "..."
  },
  "prediction": {
    "board_changes": true, "level_complete": false, "game_over": false,
    "changed_colors": ["orange"], "text": "orange moves 2 right unless the wall blocks it"
  },
  "explains_action": "confident | plausible | probe | cannot_explain"
}
```

The ledger keys are exactly `_LEDGER_GAME_KEYS` plus `_LEDGER_LEVEL_KEYS` from `tool_agent.py`, so
an annotation drops straight into the `world_model` argument of a training record.

## 5. The pilot

### 5.1 Games and runs

All three are training-split games (`datasets/splits/public25-train-test-split.json`). None of
the seven held-out games is touched, and `as66` never is.

| game | why this one | Boss run | Astra calibration run |
|---|---|---|---|
| `ft09` | short and clean (133 actions, 6/6); the sanity lane | `99084b22` | default harness, scored 1.000: `237e4950` |
| `cn04` | the 27B states the right weld rule at step 15 and reverts at step 21; object-dependent verb | `f714032e` (454 actions, 6/6) | default harness, scored 1.000: `3cd20b12` |
| `g50t` | slippery seven; Astra's largest harness gap (default 0.030, provider adapter 1.000); human win against our zero | `4f0689d0` (533 actions, 7/7) | none. Astra's best default run scored 0.030, so its prose is a failing player's, not a calibration target |

**Caps.** Each Boss run is annotated from its first row to the end of whichever level is in
progress at step 100, with a hard stop at 150. Astra calibration runs use the same rule at 80 and
120. Per-level step counts were **not** measured while writing this (the recordings are not on
this machine); the stager reports them before anything is sent to a model.

### 5.2 Arms

| arm | material | annotator given the rulebook? | answers |
|---|---|---|---|
| **H-blind** | 3 Boss runs | no | the main question: clean and correct without privilege? |
| **H-rules** | the same 3 Boss runs | yes, under the same citation rules | does privilege buy accuracy, and at what leak cost? |
| **A-cal** | 2 Astra default runs, prose hidden | no | does backfill recover what the player actually thought? |

Roughly 800-1,100 annotated steps in total, plus the auditor and grader passes over them.

### 5.3 Stages

- **Stage 0, smoke: 30 steps of `ft09`, H-blind.** Exercises the loop, packets, checkers and JSON
  end to end, and measures seconds per step and session usage per step. Nothing else runs until
  all 30 annotations pass M1 and a person has read ten of them.
- **Stage 1, the pilot.** All eight lanes. H-blind and H-rules on the same run are separate lanes
  and never share an instance.
- **Stage 2.** Audit, grade, write up in `docs/trace-findings/`.

Usage is the Claude plan's, not API dollars. Stage 0's per-step figure is multiplied out for
stage 1, and for the full corpus in phase 2, before either starts.

## 6. What gets measured

Mechanical, per step, as each annotation lands (`check_steps.py`):

- **M1, format.** It parses; ledger keys are a subset of the harness keys; the action named
  matches the recording.
- **M2, citations.** Every `VERIFIED(step N)` has N ≤ t, and step N's diff is non-empty. If the
  claim names a colour, that colour is among step N's changed cells. Weak but mechanical,
  reported as a rate.
- **M3, prediction.** The structured prediction against row t's actual outcome: exact match on
  `board_changes`, `level_complete` and `game_over`, Jaccard on `changed_colors`. Reported **as
  lift over a trivial predictor** that repeats the previous step's outcome and never predicts a
  clear or a death. Without that baseline an accuracy says nothing, because most steps are "the
  same thing happens again".

Model-based, after the fact:

- **M4, support (auditor).** For each new claim: supported, fair hypothesis or unsupported.
- **M5, correctness (grader).** For each claim: correct, wrong or unverifiable against the
  rulebook; plus the rulebook mechanics the ledger never found by the lane's last step.
- **Leak rate.** Claims that are M4-unsupported **and** M5-correct, over all new claims, per arm
  and per game.
- **M6, calibration (A-cal only).** The grader maps both Fable's ledger and Astra's prose to
  rulebook mechanics. For each mechanic: the step it first appears in Fable's ledger against the
  step it first appears in Astra's prose; and agreement on the goal belief at each level end.
  Fable much earlier than Astra *and* M4-unsupported is a leak the causal reveal did not stop,
  most likely from Fable's priors rather than from the future.
- **M7, cannot-explain rate.** Steps where the annotator could not explain the player's move.
  This sizes the question queue we would put to the Boss (§9, item 5).
- **Hand read.** Twenty random steps per arm, read by a person with the M-scores hidden until
  after.

## 7. Decision rule, written before the run

The thresholds are proposals. Son confirms or changes them before stage 1 starts, and they are
not moved after results are seen.

| result | reading | next |
|---|---|---|
| H-blind leak ≤ 5% of new claims, M3 lift > 0 on all three games, hand read agrees | backfill is clean | phase 2 (§9) with H-blind settings |
| H-rules leak at 2x H-blind or more | the rulebook leaks through the citation rules | phase 2 annotates blind only; H-rules output stays pilot-only |
| H-rules leak about equal to H-blind and M5 clearly higher | privilege helps without leaking | phase 2 considers H-rules, with the auditor as a per-claim gate |
| H-blind leak > 15% | causal reveal is not enough (priors, genre talk) | tighten the brief and rerun stage 0; if that does not move it, stop |
| A-cal: Fable's beliefs routinely arrive well before Astra's, unsupported | the method manufactures prescience even blind | stop; this is the failure §2 exists to catch |
| M7 above about 30% | Fable cannot read the Boss's play | phase 2 needs the human anchors (§9, item 5) first |

Not results: a single lane, an arm total summed over games, or anything from the 30-step smoke
run.

## 8. Fences

- **No held-out game, ever.** The seven test games and `as66` are not annotated in any arm.
- **H-rules output is fenced like oracle transcripts** (`plans/2026-09-18-oracle-test-plan.md`
  §5): its annotator had the answer key. It enters no SFT corpus unless phase 2 explicitly decides
  otherwise on the §7 evidence, and then only claims the auditor passed.
- **Astra-derived text is fenced** until the terms are checked (§3).
- Pilot outputs (packets, annotations, audits, grades) live in the session scratch directory and a
  run folder named `*-backfill-pilot-*`, not under `datasets/`. The write-up carries the numbers.

## 9. Phase 2, if the pilot is clean (not approved by this plan)

1. **Backfill all 89 fenced human records.** Annotate the full training-side runs, then add an
   `--annotations` input to `recordings_to_sft.py` that fills each assistant turn's reasoning and
   `world_model`. A side effect worth having: a 30-turn window that opens mid-level now opens with
   a populated ledger, which closes the gap windowing made worse (human-demos write-up §2).
2. **Three-way LoRA comparison on a424** with the round-2 paired evaluator, on held-out games:
   bare demos, Fable-backfilled demos (T), and 27B-self-rationalized demos (F: the 27B writes its
   own rationale for each demo action on a108, under the same brief and checks, and Fable only
   grades). If F is about as good as T, the teacher is not needed and the no-teacher call stands.
3. **Astra provider-adapter runs as more demos**, training-split games only, backfilled the same
   way, with their 3-12% contemporaneous summaries as anchors the ledger may not contradict. Behind
   the terms check.
4. **The checks as reward, handed to the RL task.** M3 (prediction), M4 (support) and M5 (belief
   correctness) are candidate process-reward terms for on-policy RL. That is role G, entirely
   inside the no-teacher call. Keep them small next to level clears so the policy cannot farm the
   grader. They are also dense, which matters here: every lead measured so far has dissolved into
   seed variance when judged on level clears alone.
5. **Human anchors from the Games page.** Log the action stream in Feedback games (today
   `collect()` in `docs/static/js/games-feedback.js` keeps counts only), and at level clear, reset
   or death ask one line: "what did you just figure out?". Each line pins *when* a belief became
   justified, so an annotator may not state it earlier. M7's cannot-explain steps are the first
   questions to put to the Boss about his own runs.

## 10. Not verified while writing

- Per-level step counts for the three Boss runs and two Astra runs. The recordings are not on this
  machine; the stager measures them first.
- That `.claude/agents` frontmatter accepts the `fable` alias. The full id `claude-fable-5-1` is
  the fallback.
- That Fable reads an 8x PNG of a 64x64 board reliably. The diff and the level-start text grid are
  there in case it does not; stage 0's hand read is the test.
- Seconds per step and usage per step. Stage 0 measures both.
- That `replay_scrape.py`'s guid mode resolves Astra session guids to game ids the way it does
  human guids. It uses the same `/api/sessions/<guid>` endpoint, but it has not been tried on an
  Astra guid.
- Which of Astra's six default configurations each chosen guid is. The order within each block of
  six is unverified (`docs/astra/README.md`); the guids here were picked by score, not by label.
- Whether any of this helps a trained model. Phase 2's comparison is the only thing that can say
  so.
