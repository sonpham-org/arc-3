# What the harness should carry from turn to turn: describe the picture, stop re-measuring

Author: Claude Opus 5.5. Date: 25-September-2026. Asked by the Boss after reading one Ghost Twin trace.
For: the Boss's other assistant and Son, to think about before the next harness arm.
Builds on: `2026-09-11-sk48-mental-models.md` (wrong governing metaphor) and
`2026-09-25-opus5-arcprize-replays-failures.md` (wrong model stamped "confirmed", notes rebuilt from scratch).

## What started it

Run `g4run-no-cap264-w7-20260917-3de1c8f0dd`, Ghost Twin (g50t), turn 24
(https://arc3.sonpham.net/viewer.html#run=g4run-no-cap264-w7-20260917-3de1c8f0dd&game=g50t-5849a774&turn=24&frame=67).
The model calls the red pieces "snakes". They are hydraulic pistons. It got that name on level 1 and then
built everything on it: heads, tails, pinning. Every turn it lays a 6-pixel cell grid over the ASCII frame,
gets the alignment wrong, finds out, and writes a new measuring function (`ringpos`, `cell`, `cb`, `scan`,
`info`...). Eventually it gives up on understanding the board and plays long blind move sequences, then
resets.

The Boss's question: is this constant, and what should we keep in the model's limited context instead?

## Sources and method

The step files on the arc3-viewer Railway volume (`/srv/data/<run>/game-N-step-M.json`) were read
server-side, and only counts came back. Eight all-25 public-game runs were used: `no-cap264 …3de1c8f0dd`,
`cap-return132 …c8fb225fae`, `clean-return-repeat132 …9677f73fbf` and `…0cfc444a85`,
`cv5cr-all25-baseline-132-efforthigh …4f3ecf36cb`, `…effortmedium …5d764adf5b`,
`modes-all25-act-132 …0fd7afe3dd`, and `lacr-effort-high-a132 …222698fd16`. The byte and notes-slot counts
also include `cv5cr-hard7-memory_v2-132 …002d497d5a`. A level counts as "cleared" if the game reached a
higher level afterwards. The scripts are keyword and regex counts, so treat them as rough.

## Findings

**1. The model gets a picture every turn and mostly doesn't use it.** The system prompt in these runs
includes "User turns include an attached image of the current ARC grid". In the harness code that line is
only added when the image is actually attached (`vision_context.current_grid_image_enabled`). Its thinking
mentions the image in about a third of turns, and it reads the board from `current_frame.ascii` on most
turns. In the Ghost Twin trace it says "Looking at the image" once, then goes back to counting characters.
It almost never writes a plain-language description of the scene. *(High confidence that the image is sent.
The share of turns that mention it is a keyword count.)*

**2. The notes slot arrives empty.** Each user turn ends with "End of carried world model.", and the
model's notes are supposed to sit above that line. In every run read, including the `memory_v2` arm, nothing
is there except the runtime-budget line. What carries forward is the raw record of earlier turns
(`contextReconstruction.kind = prior_step_transcripts`): all the counting, code and printouts, and no
summary of what the model has learned. Son's harness source isn't in this checkout, so this is how the
turns were *recorded*. The code that fills the slot has not been read. *(High confidence on the records,
medium on the mechanism.)*

**3. Most of the helper code is rewritten from scratch.** The prompt says "Snippets are not saved, so
re-import or redefine needed helpers." Measured as bytes of `def` blocks that repeat a helper already
written earlier in the same game, by name or by normalised body:

| run | repeated share of helper code |
|---|---|
| no-cap264 | 70% |
| cap-return132 | 69% |
| cv5cr baseline efforthigh | 68% |
| lacr effort-high | 71% |
| cv5cr hard7 memory_v2 | 78% |

Code is only about 13–17% of what the model writes, though. Rewritten helpers come to roughly 5–8% of all
output. The rewriting is real waste, but it is the smaller cost.

**4. The big cost is thinking about where things are, not what they do.** Thinking makes up about 85% of
output. Location words (row, col, cell, pixel, offset, band...) outnumber rule words (rule, goal, because,
means, mechanic...) by roughly seven or eight to one, on cleared and stuck levels alike.

**5. Self-doubt doesn't separate wins from losses.** Across 672 game-level stretches, doubt words ("wait",
"hmm", "actually", "re-check", "wrong"...) per 1,000 words of thinking have a median of about 21 on cleared
levels and 18 on stuck ones. The helper-rewrite share and the ASCII-over-segmentation share are also about
the same. On long stuck levels (15+ turns) the rewrite share climbs to about three quarters. So the churn is
a tax on every level, not what decides one. What decides it is more likely the wrong governing idea
("snake", "tongue", "ball into socket"), which matches the two earlier notes. *(Medium confidence: rough
counts, no test of cause.)*

## Proposal: what to keep, what to drop

What the Boss wants is for the model to rely on the image and describe it in natural language. That is the
most important thing to keep.

1. **Start every turn from the picture, in words.** Before any code, the model writes a short
   plain-language description of what it sees: the pieces, what they look like they are for, what changed
   since last turn. It should name mechanisms by what they appear to do ("a piston that extends when...")
   and mark them as guesses.
2. **Carry that paragraph, not the transcript.** The description plus the current rule guesses and what
   has been ruled out are what fill the "carried world model" slot. Old raw turns (code, printouts, cell
   arithmetic) get dropped. This is also where "my model is wrong" can be written down and kept (see the
   Opus 5 note's falsification check).
3. **Keep helpers between turns.** Keep a small per-game toolbox of functions the model has already
   written, so it calls `find_player()` instead of rewriting it.
4. **Measure only to answer a named question.** Code is for settling a specific doubt the picture can't
   settle ("is that gap one cell or two?"), not for rebuilding the board every turn.

## Open questions for the next reader

- Where does Son's harness build the carried-world-model text, and why is it empty? Was it ever filled in
  an arm that scored well?
- Can the Qwen models we run actually read these 64×64 upscaled images well enough to describe them? The
  quickest test is to ask for descriptions of a few known boards and compare them with the arc-explainer
  write-ups.
- What does "describe, then carry the description" cost in tokens against what it saves by dropping the
  raw turns?
- None of this has been tied to a harness score yet (AGENTS.md §5). It is a design proposal backed by
  trace reading, not a result.
