# The Qwen3-27B training-pipeline proposal, and why the order is wrong

**Date:** 14-Sep-2026
**Author:** Claude Opus 5 (Bubba)
**Status:** Recorded for decision. Nothing built, nothing spent.

## What was proposed

Forwarded into `#arc-3` on 14-Sep by the Boss, from another assistant. Verbatim shape:

1. **Base model** — Qwen3-27B, QLoRA/SFT so an adapter trains without a big GPU pool.
2. **Environment loop** — Qwen inside a real ARC-3 agent loop: observe → reason → act →
   receive → update beliefs → repeat.
3. **Training representation** — synthetic-game trajectories converted to examples carrying
   current frame, relevant previous frames/actions, known mechanics, current hypotheses,
   inferred goal, current plan. Target is `<think>observation → hypothesis → uncertainty →
   next experiment</think>` followed by `ACTION(...)`.
4. **Explicit memory** — external structured memory (`known_mechanics`, `tested_actions`,
   `hypotheses`, `goal`, `current_plan`) that the model updates as it plays, rather than
   remembering implicitly.
5. **Train exploration, not just winning** — include information-gathering trajectories and
   failed/inefficient ones, so the model learns which experiments are informative rather
   than imitating winning action sequences.
6. **Preference/RL** — DPO on better-vs-worse decisions once SFT gives a competent reasoner,
   then GRPO/RL against actual game success.

Stated goal: not memorising the 25 public games, but training a reusable
exploration → hypothesis → planning → action → feedback loop that transfers to unseen games.

## The architecture is right

No argument with the shape. It matches what our own traces say is broken. Every failure mode
we have logged this week is a *loop* failure, not a perception failure or an execution
failure:

- `2026-09-13-job1-control-baseline.md` — lf52 scores **1.818 on all four control passes,
  zero variance**. Same wrong model, same wall, four times. That is a loop that cannot
  invalidate its own hypothesis.
- `2026-09-12-cn04-weld-vs-pair.md` — cn04 states *"the weld broke, meaning no permanent
  weld"* at step 15, which is correct, and reverts at step 21.
- `2026-09-12-sc25-sigil-caster-six-runs.md` — sc25 writes the winning square at turn 21 and
  goes back to typing codes.
- The human replays (`2026-09-13-g50t-human-win-vs-our-zero.md`,
  `2026-09-13-bp35-human-win-replay.md`) beat baseline pace on the levels they understood.
  Execution is not the bottleneck. Model formation is.

So steps 2–5 are aimed at the correct organ.

## The order is wrong, and it's expensive in the wrong place

**Steps 1–2 are not the bottleneck. Step 5 is — and step 5 is a data problem we have not
solved.**

The proposal needs trajectories that demonstrate *informative* exploration. Inventory of what
we actually own:

| Source | Volume | Usable as SFT target? |
|---|---|---|
| Our arm transcripts (jobs 1–8) | 28 passes per arm, 380K–884K chars each | **No.** Near all of them are a model holding a wrong hypothesis for 300 actions. SFT on this teaches the failure. |
| Boss's human replays (g50t `4f0689d0`, bp35 `c935ca1b`) | 2 wins, 533 + 1,024 actions | **Partially.** They are action streams. There is no reasoning channel to distil — the `<think>` block the proposal wants does not exist in them. |
| Synthetic games (`autoresearch-arena/arc3games/`) | authored, growing | Environments, not trajectories. Still need a competent player to generate the traces. |

That is the circularity: step 5 wants traces from a good explorer, and the point of the
pipeline is to build a good explorer. Whoever generates the seed traces has to already be
better than what we are shipping.

## Step 4 is testable today, for free

The one part of the proposal that costs nothing to falsify is the **external structured
memory**. That is Son's compaction arm, from
`2026-09-13-meeting-summary-vs-experiment-queue.md`. The harness compacts by dropping oldest
turns, which drops learned world-model facts (the canonical case being *orange is the AI* in
wa30). It re-injects `known_mechanics` / `hypotheses` into the user prompt so they survive
compaction.

This is exactly the proposal's step 4, run as a prompt/harness intervention with **zero
training**.

- If persisting structured beliefs across compaction **moves level clears**, that is direct
  evidence the loop-with-memory architecture is the right thing to distil, and the ~$200 of
  fine-tuning is buying something we have measured.
- If it **does not move**, we would be paying to train a loop that does not help — and we
  would not know that until after the money was spent.

## Recommended order

1. **Arm I** (structured memory across compaction) — specced, not yet built, zero training cost.
2. **Generate traces from whichever arm wins.** Present standings below; arm C (mechanics
   possibility) is the leader, arm H (ACTION7) is unscored.
3. **Then SFT**, seeded from those traces, with the proposal's representation (step 3) intact.
4. DPO/GRPO after, as proposed.

The proposal's steps stay in the proposal's order. What changes is that steps 1 and 6 do not
start until step 4 has produced a number.

## Standings this decision rests on

Level clears, bottom seven, passes 0–2. Every arm after B is stacked on the deletion arm, so
**15 is the number to beat.**

| Arm | Job | Level clears |
|---|---|---|
| A — control | 1 | 10 |
| B — pure deletion | 2 | **15** |
| C — mechanics possibility | 4 | **16** |
| E — image-first (no ASCII turn 1) | 7 | 11 |
| F — commit-prompt | 8 | 13 |
| D — glyph consonants | 6 | 12 |
| H — ACTION7 round-trip | 10 | running |
| G — visual-first | 9 | queued |
| I — structured memory across compaction | — | not built |

Caveat stated plain: n=3 per game. Most single-game deltas are one pass wide. The arms that
moved up are the two that changed what the model is *allowed to believe* — deletion removed
false priors, mechanics removed a false ceiling. Nothing that changed the *representation*
(glyphs, image-first) has helped yet.

## Label correction

`2026-09-13-meeting-summary-vs-experiment-queue.md:68` recommended the compaction arm as
"arm D". **That letter was already taken** — arm D is the glyph-consonant arm that shipped as
job 6. The compaction arm is **arm I** from here on. The earlier doc is left as written; this
is the correction of record.

## What is not being claimed

- Not claiming the training pipeline will fail. Claiming it is unfalsifiable until arm I runs.
- Not claiming 27B is the wrong base. No opinion; untested here.
- The $200 figure and the Unsloth/vLLM+PyTorch tooling call came from the 13-Sep meeting
  (`2026-09-13-meeting-summary-vs-experiment-queue.md`), not from this proposal, and are not
  independently verified.
