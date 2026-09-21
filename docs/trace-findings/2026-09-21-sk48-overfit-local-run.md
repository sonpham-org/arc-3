<!--
Author: Claude Opus 5 (Bubba subagent)
Date: 21-September-2026
PURPOSE: Record the deliberately-overfit sk48 arm run entirely on the Mac Mini: stock
Qwen3.8-27B-MLX-4bit served by LM Studio, the local ARCEngine build of sk48 played in-process,
and the Boss's own sk48 write-up injected into every user turn. Records exactly what was
injected and removed, the endpoint and budget, the measured per-action cost, what happened
level by level, and a plain verdict on whether a maximally-told 27B can play this game on this
box. Also records a coordination conflict found mid-run.
SRP/DRY check: Pass -- harnesses/oracle-rules/MANIFEST.md owns the injection mechanism's
design and docs/plans/2026-09-18-oracle-test-plan.md owns arm O's experimental design. This
holds only this one local, deliberately-contaminated diagnostic run and its result.
-->

# Telling a 27B exactly what Skewer Kebabs is, on the Mac Mini

**This is not a benchmark arm.** The model was told the game's name and its full mechanics up
front, which is precisely the variable a benchmark holds out. Its score is not comparable to
the a108 0.00 on sk48, and nothing here should be read as a measurement of the model. Boss's
directive, #arc-3, 21-Sep-2026: *"I want to specifically overfit to SK48 in the harness and see
if the model can do it... The reasoning traces it produces might then be of more value for
reinforcement learning."* The deliverable is the trace, not the score.

## The setup

| | |
|---|---|
| model | `~/.lmstudio/models/lmstudio-community/Qwen3.8-27B-MLX-4bit` (15G), the **stock** Qwen3.8-27B |
| quant | MLX 4-bit, group size 64. The a108 arms run unsloth **NVFP4** — same model family, **not the same artifact** |
| endpoint | LM Studio OpenAI-compatible, `http://127.0.0.1:1234/v1`, model id `qwen/qwen3.8-27b`, 208,384 context |
| vision | Confirmed present (`Qwen3_5ForConditionalGeneration`, `vision_config`, `preprocessor_config.json`) and verified with a live image round-trip before launch |
| game | `~/GitHub/arc-explainer/external/ARCEngine/environment_files/sk48` → resolves to `sk48-d8078629`, played in-process by `inference/framework/solver.py`. No arcprize.org play session |
| harness | `~/GitHub/arc-3/ARC3-Inference`, in-tree, `.venv` Python 3.12.12 built fresh on arm64 (`uv sync`; `vllm` is an optional extra and was not needed) |
| launcher | `scripts/run_sk48_overfit_local.sh` |

`ACTION7` is exposed: every turn logs
`valid_actions=UP,DOWN,LEFT,RIGHT,MOUSE,ACTION7`. That matters, because the injected text makes
Undo load-bearing.

### Pre-flight gates, all passed before launch

- **Tool calling round-trips.** `scripts/smoke_tool_call.py --provider vllm` against LM Studio:
  `tool smoke passed: parsed 1 tool call(s)`. LM Studio does not reject the vLLM-shaped
  `top_k` / `chat_template_kwargs` extras.
- **Vision round-trips.** A two-color 64×64 PNG was described correctly ("two distinct colors
  in the image: red and blue"), 106 completion tokens in 8.8s.
- **The treatment fires.** `scripts/test_oracle_injection.py --rules-dir <overfit dir> --games sk48`:
  mean first-turn user prompt goes from **413 chars (untreated) to 10,025 chars (treated)**,
  the block is re-sent on turn 5 as well as turn 0, and exactly 1 copy lives in a 3-turn
  request. The marker guard passes at 1/1 treated and 0/1 untreated, and correctly **refuses** a
  deliberate double-injection. Every launched run logs
  `oracle rules loaded ... block_chars=9611`.

## What was injected

Via the existing arm-O mechanism — `inference/agent/oracle_rules.py`, selected by
`ARC3_ORACLE_RULES_DIR`, injected at the **top of every user turn** and stripped from retained
history so exactly one copy is live. Nothing new was invented; `harnesses/oracle-rules/` owns
this design.

The treatment directory is **not** the pending arm-O `datasets/explainer-games/rulebooks/`,
which was deliberately left alone. A new directory
`datasets/explainer-games/rulebooks-sk48-overfit/` holds a single `sk48.txt` of **9,611
characters** (~3.2K tokens). Two reasons it had to be hand-built rather than re-rendered:
`datasets/explainer-games/games.json` was fetched 18-Sep and does **not** contain the Boss's
level 1–8 notes added today (`5e0da566`, `3f9c2405`, `54b8bb68`, `b6ebceb3`, `9a8c8840`); and
`tools/render_rulebooks.py` deliberately strips exactly the fields this arm wants
(`informalName`, `simpleExplanation`, `mechanicsExplanation`, `playerObservations`).

`datasets/explainer-games/` is gitignored, so **the injected text is quoted verbatim in
Appendix A** of this document. That is the only way this run is reproducible.

Its content, all sourced from the Boss's own write-up at `arc-explainer` HEAD
(`shared/arc3Games/sk48.ts`) rather than from a fresh reading of the game source:

1. **The game's name, first line, in capitals** — `THIS GAME IS CALLED "SKEWER KEBABS" (game
   code sk48). It has 8 levels.` The stock system prompt opens *"You are a coding agent solving
   a grid-based puzzle game"* and never names the game. That is the thing being changed.
2. **The Boss's plain-language framing**, in spirit and largely in his words: it is a meat
   skewer and the boxes are meat; the bottom strip is the order the kebab is wanted in; it is
   physics, so you must push a piece against something immovable to skewer it; **Undo (ACTION7)
   is load-bearing, not a convenience**; on later levels you move pieces out of the way first;
   on level 3 you knock a kebab back off the skewer to re-pick the pieces in the wanted order.
3. `simpleExplanation` and the full `mechanicsExplanation`, verbatim.
4. All 20 level-1 `mechanicsBreakdown` bullets, verbatim.
5. Every per-level bullet for levels 3–8, verbatim, each paired with **the Boss's note for that
   level** from `playerObservations` — including his 21-Sep notes that clicking does nothing
   until level 6, that level 7's two skewers share the one green, and that level 8 forces the
   two skewers to cooperate.
6. A closing five-step "how to play it well", which is the only editorialised part.

## What was removed

One line, one hunk, in `ARC3-Inference/inference/agent/prompts.py`, from
`VISUAL_GAME_ADDENDUM`:

```diff
-    "A common failure mode is to mistake a segmented edge bar for clickable puzzle pieces. If a repeated strip of small blocks sits flush against the top, bottom, left, or right border and actions only change that strip while the interior board stays the same, classify it as HUD/timer state, not as an object to click through segment by segment. DON'T DO THIS!\n"
```

In sk48 that strip **is** the win condition — it is the reference skewer showing the wanted
colour order. The live prompt was telling the model to ignore the answer. The adjacent, milder
"a long horizontal or vertical line near an edge is a timer or remaining-steps bar" line was
**left in**, because in sk48 it is true: the long line above the bottom strip really is the
energy bar.

## The budget, and why it had to be revised twice

Stated up front: **one game, one pass, serial (`--n-passes 1 --concurrent-jobs 1`), 240 minutes
of wall clock per game, 1800s analyzer timeout, context window 49,152.** Sampling is the
config's analyzer default (temperature 0.6, top_p 0.95, top_k 20, thinking on).

Two reference numbers frame what "clearing level 1" costs. The harness's own
`base_actions_per_level` for `sk48-d8078629` is `[61, 177, 101, 103, 230, 181, 125, 92]`, and
the Boss's write-up records an engine run clearing **level 1 in 14 moves**. So a level-1 clear
is somewhere between 14 and 61 actions.

**Measured generation throughput on this box: ~10.8 tokens/sec** (clean, uncontended). That is
the floor everything else sits on.

### Run 1 — untuned, killed at 23 minutes

`20260921_162713_20260921_sk48-overfit-oracle-local-mlx`. Kept on disk as the untuned-pace
evidence.

The defaults are `LOCAL_ANALYZER_TOOL_STEPS=12` and `LOCAL_ANALYZER_MAX_OUTPUT=0`
(server-default, i.e. unbounded). The model spent **four requests and 23 minutes inside
`action 1 / analysis_step 1` and never called `action(...)` once.** Every python call came back
`step_executed=False`, and the harness re-prompted with *"The previous `python` call inspected
the frame but did not execute `action(...)`."* The prompt grew 6,565 → 9,325 → 14,706 → 17,847
tokens as each inspection result was appended.

| request | prompt tok | completion tok | wall |
|---|---|---|---|
| 1 | 6,565 | 320 | 118.1s |
| 2 | 9,325 | 4,734 | 551.9s (contended — see below) |
| 3 | 14,706 | 2,722 | 252.6s |
| 4 | 17,847 | 5,510 | 448.0s |

At 12 permitted tool steps this is ~50 minutes per game action. Against a 14-to-61-action level
that is a pre-determined null, so it was stopped rather than run to the wall.

**A contention artifact is recorded in that run's `CONTENTION-NOTE.md`,** written by a peer
sub-agent: a second harness process was briefly pointed at the same single-slot LM Studio
endpoint between 20:27Z and 20:38Z, which is what makes request 2's 551.9s unrepresentative.
Request 3 onward is clean. I did not launch that process; see *Coordination conflict* below.

### Run 2 — over-tightened, killed at 9 minutes

`20260921_165207_..._-bounded`. `TOOL_STEPS=3`, `MAX_OUTPUT=3000`. This failed the opposite
way: requests 2 and 3 both returned `finish=length tool_calls=0` at exactly 2,999 completion
tokens. The cap truncated the thinking block **before** the model could emit its tool call.
Read carelessly that looks like a tool-call format failure; it is not, it is a budget artifact,
and it is exactly why the cap cannot simply be set low.

### Run 3 — the arm of record

`20260921_170341_20260921_sk48-overfit-oracle-local-mlx-bounded2`. `TOOL_STEPS=3`,
`MAX_OUTPUT=7000`, everything else unchanged. 7,000 tokens is high enough that a normal turn
completes (the untuned run's turns landed at 2.7K–5.5K) and low enough to bound the worst case.

Capping the loop is not a compromise of the overfit hypothesis — it is aligned with it. A model
that has been handed the mechanics should not need 16,000 characters of reasoning re-deriving
them.

## What actually happened

**Status at the time of writing (17:40 EDT): still running, no level cleared yet, and the
earlier zero-action reading has been corrected — see the correction below before reading the
table.**

### The injection worked, and that is the solid finding

The model's own `world_model` ledger, written by it on turn 1, reads:

> `"game": "Skew Kebab (sk48), 8 levels. L1: one rod (pink handle, gray zigzag bar) + rail;`
> `column of red/blue/green beads; bottom reference strip is the win condition (order red,`
> `green, blue per rules)."`

It names the game, identifies the rod and handle, locates the beads, and — the line the removed
HUD rule would have argued it out of — states that **the bottom reference strip is the win
condition**, in the right colour order. In the untuned run it also correctly recorded the
push-block mechanic, the free Undo, and the 196-energy budget, and it read the board accurately
from the ASCII frame, resolving the rail to columns 16–22 and the bead column to 42–45.

That is the strongest evidence in this run and it is not in doubt: **told plainly what the game
is, the model understood it.**

### Correction: three of the four runs were mis-configured by me, not by the harness

My first three runs produced zero game actions, and I initially wrote that up as a property of
the model. That was wrong, and the error was mine.

`LOCAL_ANALYZER_TOOL_STEPS` defaults to **12**: within one analysis step the model gets up to
twelve `python` calls, accumulating inspection results in context, with twelve chances to
converge on an `action(...)` call. Reading an early 551.9s request as raw slowness — it was in
fact **endpoint contention** from a peer process, as that run's own `CONTENTION-NOTE.md`
records — I cut the loop to 3 steps to save wall clock. That is a ceiling I imposed, and
`inference/agent/tool_agent.py` confirms it proves nothing: **the final tool step carries no
forced-action escalation.** The same "you did not execute `action(...)`" follow-up is used at
step 3 as at step 1, so a run capped at 3 simply gets cut off earlier and starts a fresh
analysis step from a thinner context. I built a treadmill and then measured it.

| run | tool steps | max output | outcome | reading |
|---|---|---|---|---|
| 1 untuned | 12 (default) | unbounded | killed at request **4 of 12** | inconclusive — killed mid-loop, and partly contended |
| 2 | 3 | 3,000 | `finish=length`, thinking truncated before the tool call | inconclusive — cap artifact |
| 3 | 3 | 7,000 | 3 requests, 2 inspections, 0 actions | inconclusive — imposed ceiling |
| 4 of record | 12 (default) | 10,000 | **running**, sole client, full 240 min | the faithful test |

So the honest statement of what is known: **the model has not yet moved a piece, and the first
three attempts to measure that were confounded by my own tuning.** Run 4 — launched 17:38 EDT
with the harness defaults restored, output raised to 10,000 tokens so thinking is not
truncated, a single client on the endpoint, and no early kill — is the first configuration that
actually tests the question.

### What is genuinely measured

- **Generation throughput: ~10.8 tokens/sec**, clean and uncontended. That is real and it is
  this box's hard limit.
- **Reasoning volume is large**: single requests produced 20,242 and 21,088 characters of
  reasoning. At 10.8 tok/s that is nine to ten minutes of wall clock per request. With the
  default twelve tool steps, one analysis step can legitimately cost over an hour here.
- **A level-1 clear is 14 actions at best** (the engine run in the Boss's write-up) and 61 at
  the harness's own `base_actions_per_level`. Even granting convergence, that arithmetic is
  brutal on this box.
- **It is not a tool-call format failure** (calls parse; the pre-flight smoke test passed) and
  **not a context blowout** (window 49,152; largest prompt seen 17,847 tokens).

## Verdict

**Partial, and deliberately not stated more strongly than the evidence supports.**

1. **Telling it worked — this part is settled.** Given the name, the mechanics and the Boss's
   own notes, the model correctly identified Skewer Kebabs, the reference strip as the win
   condition, the required colour order, and the board geometry. Comprehension was not the
   bottleneck. That is a real point in favour of the overfit idea and of removing the HUD line,
   and it is worth having on its own.

2. **Whether it can execute is still open.** It has not yet converted that correct,
   handed-to-it plan into an `action(...)` call. But the three runs that showed zero actions
   were configured by me in a way that could not have shown otherwise, so they are not evidence
   about the model. Run 4 is the first fair test and it is still going.

3. **This box is a poor instrument regardless.** At ~10.8 tok/s with 20K-character reasoning
   blocks, every knob that bounds the inspection loop also truncates the reasoning that is the
   deliverable — run 2 demonstrates that directly. Even a well-behaved model would struggle to
   reach 14 actions here inside 240 minutes.

**No level cleared, no action taken so far, and the score is 0.00 — and that 0.00 carries no
information about the model.** It must not be quoted, and specifically must not be set beside
the a108 0.00 on sk48 as though the two measured the same thing.

**What would settle it.** The same treatment on a box that generates at 50+ tok/s — which is
exactly the a424 arm a peer sub-agent launched at 16:50 EDT (see below). There, a 20K-character
reasoning block costs seconds rather than ten minutes, and "will it act once it has been told?"
gets a clean answer. Read this run as the local feasibility probe it turned out to be; read the
a424 arms for the capability answer.

**A cheap follow-up worth one run:** the harness accepts batched actions (`action(actions)`,
already encouraged at `prompts.py:145`) and the injected text ends with a five-step plan. A
variant that pushes the model to commit to a short opening sequence *before* inspecting — or
that hands it the first three moves outright — would test execution directly rather than
through a perception loop this box cannot afford.

## Coordination conflict found mid-run — flagged, not resolved

Two files appeared **inside this run's own directory** while it was running, written by a peer
Bubba sub-agent, not by me:

- `BRIEF-READ-ME-FIRST.md` (16:35 EDT) — a "STANDING BRIEF" attributed to HermesAstra and
  relayed by the Boss, which states that it *"supersedes any earlier verbal instruction to the
  sk48 sub-agents."*
- `CONTENTION-NOTE.md` (16:46 EDT) — the endpoint-contention record cited above.

The peer is real and concurrent: a process was observed at 16:50 EDT opening an SSH session to
`son@100.106.31.61` to start `run_sk48_a424.sh` in a tmux session named `arm1`. That is the
a424 base-vs-LoRA comparison the brief describes.

I have **not** silently adopted the brief in place of my own instructions. Where they agree, no
issue — the brief's §1 (this Mac run is a separate diagnostic, not comparable to the a424 arms
or to a108) and §2 (capture traces unchanged; the deliverable is the trace, not the score) say
the same thing my directive says, and both are honoured here. Two points genuinely diverge and
are the Boss's call, not mine:

1. **Report location.** I was told to write `2026-09-21-sk48-overfit-local-run.md`; the brief
   §6 names `2026-09-21-sk48-oracle-reasoning-comparison.md`. That second document spans the
   a424 arms and is the peer's deliverable, so I wrote the file I was asked for and cross-refer
   to theirs rather than overwriting it.
2. **Use of the traces.** My directive frames these traces as potentially valuable *for
   reinforcement learning*. The brief §5 says the opposite: oracle-privileged, potentially
   contaminated, **no SFT extraction, no RL, no corpus ingestion**. I have not ingested
   anything either way, and the fence below holds regardless — but if these traces are wanted
   for RL, that is now an explicit conflict that needs the Boss or Dr. Fable to settle.

## Contamination fence — intact

The run dirs are named `*-oracle-*` on purpose. `distill/extract_sft.py` refuses such a
directory with exit code 2 and no override (`ARC3-Inference/distill/README.md`). These
transcripts contain the answer key to sk48; standard SFT extraction is therefore fenced off,
and I did not rename anything to dodge it. Using this material for RL needs an explicit call,
per the conflict above.

## Where the artifacts are

```
~/bubba-workspace/arc3-sft/runs/
  20260921_162713_20260921_sk48-overfit-oracle-local-mlx/           # run 1, untuned pace evidence
  20260921_165207_20260921_sk48-overfit-oracle-local-mlx-bounded/   # run 2, over-tight cap
  20260921_170341_20260921_sk48-overfit-oracle-local-mlx-bounded2/  # run 3, imposed-ceiling
  20260921_173838_20260921_sk48-overfit-oracle-local-mlx-faithful/   # run 4, arm of record
~/bubba-workspace/arc3-run/sk48-overfit-*.log                       # launcher stdout
~/GitHub/arc-3/datasets/explainer-games/rulebooks-sk48-overfit/sk48.txt   # treatment (gitignored)
~/GitHub/arc-3/scripts/run_sk48_overfit_local.sh                    # launcher
```

Each run dir holds `transcripts/`, `requests.jsonl`, `prompts/prompt.log`, `artifacts/`
(`*_events.jsonl`, `*_viewer_data.json`, `*_tool_runtime_state.json`), `benchmark.json`,
`summary.txt` and `diagnostics.html`, the same layout as the a108 runs.

## Appendix A — the injected text, verbatim

The treatment lives at `datasets/explainer-games/rulebooks-sk48-overfit/sk48.txt`, which is
gitignored. It is 9,611 characters. Reproduced here in full so this run can be rebuilt:

```text
THIS GAME IS CALLED "SKEWER KEBABS" (game code sk48). It has 8 levels.

WHAT THE GAME IS, IN PLAIN WORDS:
You are holding a meat skewer. The colored boxes on the board are pieces of meat. The
strip at the very bottom of the screen shows you a reference skewer for each skewer that
counts -- that strip IS the win condition, it is the order the kebab is wanted in. You
extend your skewer to skewer the pieces in the order the reference strip shows it wants
them.

It is physics, not magic. You cannot just walk up to a piece of meat and have it appear on
the skewer. You have to PUSH the piece against something that will not move -- the board
edge, a wall, or another piece that is already stuck -- and then the skewer slides through
it and it is skewered. That is the single most important mechanic in this game.

To get a piece OFF the skewer you use Undo (ACTION7). Undo is LOAD-BEARING in this game,
not a convenience. This is a push-block puzzle: pushing is one-directional, and retracting
or sliding the skewer does NOT pull a pushed piece back where it came from. A bad
extension can permanently scramble the board with no way to recover it by further play.
Undo is the only thing that can take a push back. Use it freely and often -- it is free,
it costs no energy, and you can press it repeatedly all the way back to the start of the
level. When a plan goes wrong, UNDO; do not try to play your way out of it.

On the later levels you must move pieces out of the way first before you can build the
order you want. On level 3 you knock a kebab back off the skewer so you can pick the
pieces up again in the order the reference wants them.

ONE-PARAGRAPH SUMMARY:
You extend, pull back and slide a skewer to push colored beads around and skewer them.
Get the beads on each skewer into the same color order as the reference skewer shown at
the bottom before you run out of energy.

FULL MECHANICS:
Each rod sticks out of a square handle. Pressing the rod's own direction extends it one
segment, pressing the opposite way pulls it back one segment, and pressing sideways slides
the whole rod one step along the striped rail beside its handle (no rail, no slide).
Extending doesn't pass through loose beads -- it pushes each one ahead of the tip -- but a
bead that can't be pushed any further (board edge, wall, or another stuck bead) stays put
and the rod slides through it, skewering it. Beads already on the rod ride along when it
extends, get dragged back when it retracts, and get carried when it slides; a slide that
would push a bead off the board doesn't happen, and the tip can't go past the board edge
or into a wall. The strip at the bottom holds a reference rod for each rod that counts:
the level clears when the beads on each matching rod, read outward from its handle, have
the reference's colors in the same order, and a white dot marks each position that already
matches. From level 3 there are fixed rods you can't move, and on level 4 the references
belong to two fixed rods while your own rod is only a tool. Solid black walls appear on
levels 5 and 6, and from level 6 you switch between two rods by clicking a handle. Every
direction press costs 1 of the level's 196 energy; clicks and undo are free, undo restores
rods and beads but not energy, and running out of energy ends the game.

RULES THAT APPLY FROM LEVEL 1:
- Press the direction the selected rod points (away from its handle) to extend it one segment. Press the opposite direction to pull it back one segment. It never shrinks below the one segment under its handle.
- Press a sideways direction to slide the whole rod, handle and all, one step along the striped gray rail beside the handle. Where the rail ends, or with no rail, nothing moves.
- Every direction press costs 1 energy, even when nothing moves.
- Undo (ACTION7) puts the rods and beads back as they were before your last move that changed something, and you can keep pressing it back to the level start. It is free, but it does not give back energy.
- RESET restores the level with full energy.
- The strip below the long line at the bottom shows a reference rod with a row of colored beads for each rod that counts, matched to it by handle color. The level clears when the beads on each of those rods, read outward from its handle, have the reference's colors in the same order.
- Only the first as many beads as the reference holds are checked; extra beads further out on the rod don't matter.
- Your rod is a gray zigzag bar sticking out of a pink square handle. Beads are small colored squares. Level 1 has one rod, a rail beside its handle, and a column of red, blue and green beads to be skewered as red, green, blue.
- Extending pushes a loose bead just ahead of the tip along in front of it, and beads already on the rod ride forward with it.
- A bead that can't be pushed any further (board edge, wall, or another bead that is stuck) stays where it is and the rod slides through it. That is how a bead gets skewered.
- Pulling the rod back drags the beads on it back toward the handle. A bead right next to the handle has nowhere to go, so the rod pulls out of it and leaves it loose.
- Sliding carries every bead on the rod and pushes loose beads in its way. If a bead would be pushed off the board, the slide doesn't happen.
- The tip can't go past the edge of the board. An extension that would do that does nothing, and still costs 1.
- Each level gives 196 energy, and only direction presses spend it. Clicks and undo are free.
- When energy hits 0 the game is over. There are no lives. A move that clears the level with your last point still counts.
- The long line above the bottom strip is the energy bar: gray for energy left, dark gray for energy spent. It refills at the start of each level.
- A white dot appears on a reference bead whenever the bead in the same position on the matching rod has the same color, so you can see which positions are already right.
- When a bead gets newly skewered, an outline in the bead's color flashes around it for a moment.
- The selected rod's handle has a white inside and its rod is drawn a lighter gray. Its reference in the bottom strip lights up the same way.
- On a clear, all the beads on the rods flash white a few times before the next level loads.

LEVEL 3 ADDS:
- A fixed rod appears: a vertical rod with a black handle and a yellow center, which you can't select or move. Your rod passes straight through it. A bead on it can slide up and down along it (your rod can carry it that way), but nothing can push it sideways off the rod.
- Boss's note: on this level you knock a kebab back off the skewer so you can pick the pieces up again in the order the reference wants them. Undo is how you do that.

LEVEL 4 ADDS:
- The rods you must fill can be ones you don't control. On level 4 the two references belong to the two fixed rods at the top (light blue and yellow centers), and your pink rod has no reference at all: it is only a tool for moving beads onto them.
- Boss's note: level 4 starts with pieces already on the skewers. The meat-skewer picture still explains it.

LEVEL 5 ADDS:
- Solid black wall squares appear on levels 5 and 6. The tip can't extend into one and beads can't be pushed into one.
- Boss's note: a black box blocks the skewer with red boxes behind it. He clicked on everything on the screen and clicking changed nothing -- clicks only switch between rods you control, and there is only one rod until level 6, so clicking does nothing before then. Work the level out by experimenting with the direction presses.

LEVEL 6 ADDS:
- Two rods you control, pink and purple. Click a rod's handle, or its reference in the bottom strip, to switch to it. Switching is free, and clicking anything else does nothing.
- The purple rod hangs down from the top and slides left and right along a rail across the top. The two rods pass straight through each other.
- Boss's note: clicking does nothing in this game until level 6 of 8. From there it is how you switch skewers. Each skewer is matched to its own reference at the bottom. They are not always pairs, and a skewer does not have to match a partner.

LEVEL 7 ADDS:
- The two rods have to share a bead. The board has one green bead, two blue and two red, and both references want green in the middle: pink wants blue, green, blue and purple wants red, green, red. The one green has to end up where the two rods cross, counting for both.
- Boss's note: level 7 is insane -- the two skewers have to work together because they share the green peas.

LEVEL 8 ADDS:
- Pink's rail shrinks to two segments, so the pink rod can barely slide up or down and can't get to the lower half of the board. The green bead starts down there, straight below the purple rod, so only purple can bring it up. Pink wants blue then green; purple wants red then orange.
- Boss's note: the purple skewer can reach the bottom of the board; the pink one on the left can't. The fiendish part: you absolutely have to work with the other skewer to win level 8.

HOW TO PLAY IT WELL:
1. Read the bottom strip FIRST. It tells you the exact color order you are being asked for.
2. Work out which direction your skewer points, and which way it slides.
3. To skewer a piece, get it pinned against the board edge, a wall, or an already-stuck
   piece, then extend through it.
4. Order matters. The piece nearest the handle is the first color in the reference.
5. If a push goes wrong, press ACTION7 (Undo) immediately. Do not spend energy trying to
   play your way out of a bad board.
```

