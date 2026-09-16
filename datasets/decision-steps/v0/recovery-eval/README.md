<!--
Author: Claude Opus 5
Date: 16-September-2026
PURPOSE: Operator guide for the recovery eval: what one question is, what the model is and is not
shown, how an answer is scored, how to run it against a model server, and how the result is to be
read, written down before the first full run so the reading cannot be fitted to the numbers.
SRP/DRY check: Pass - tools/recovery_eval.py holds the mechanics and its docstring the contract;
the step-5 plan section 3 holds why the eval exists. This is the how-to-run and how-to-read.
-->

# Recovery eval, v0

**Status, 16-Sep-2026: built and tested; no result yet.** No full run has been made against any
model. The first will be the base Qwen3.8-27B on a108.

The behavioural check in the step-5 plan §3. It asks whether a model, told that a choice it made
from this exact board led to a failed attempt, makes a different choice.

## One question

Every question is a **fork** found by `tools/find_retries.py` in a human recording. On some level,
the player stood on a board and chose **X**, and that attempt failed (a death, or a RESET). Later,
on the **identical board**, the player chose **Y**, and that attempt cleared the level.

The model is put on that board and asked for one action, **twice**:

| condition | the prompt shows |
|---|---|
| `with_history` | the board, the action menu, **and** that it chose X here before, what X changed on the board, and that the attempt then failed |
| `no_history` | the board and the action menu only |

The two prompts are identical apart from the history block, and a test holds them to that.

**Never shown:** Y, anything from a pass-D record (rationale, expected observation, action role),
or anything from game source. RESET is not in the menu, because the question is which move to make
from this board. Boards are text in the harness's own glyphs, and actions carry the harness's names
(`LEFT`, `MOUSE row col`, `ACTION7`).

## Scoring: the answer is played on the real game

The recording is replayed in the offline engine up to the fork, the model's action is applied, and
the resulting board is compared with the boards X and Y leave. Two clicks a cell apart on one
object count as the same choice, the same rule the fork finder uses.

| bucket | meaning |
|---|---|
| `repeated_failed` | leaves the board X leaves |
| `matched_win` | leaves the board Y leaves |
| `no_effect` | changes nothing, beyond a step counter |
| `other` | a move that is neither |
| `not_offered` | an action not in the menu, or a click off the board |
| `unparsed` | no readable `ACTION:` line, or an unknown name |
| `no_answer` | the reply ran out of tokens, or was empty |

Every recording on disk replays frame for frame in arcengine 0.9.3 with `ONLY_RESET_LEVELS=true`.
`build` checks each question four ways and refuses a question that fails any of them:
- the engine stands on the recorded board;
- Y leaves the recorded board;
- X leaves the recorded board;
- X and Y leave different boards.

## What is in `items.jsonl`

**23 questions** from the 11 live-build recordings (as66 excluded). The fork finder finds 33 forks.
The other 10 were left out:
- 9 because an earlier failed attempt had already made the winning choice from that board, so the
  board does not decide the answer;
- 1 because it is the same board and the same two choices in the player's other g50t run.

**7 of the 23 carry a pass-E-kept record**, named in `record`. The other 16 need no annotation,
because a question is built from the recording alone. So they need no pass-E review and cost no
model calls to add.

| game | questions |
|---|---|
| bp35 | 5 |
| cn04 | 1 |
| dc22 | 4 |
| ft09 | 1 |
| g50t | 5 |
| ka59 | 2 |
| lp85 | 2 |
| ls20 | 1 |
| m0r0 | 2 |

## Running it

You need the recordings in `v0/recordings/` (gitignored) and **the exact game builds**. On a108
they are `~/flash-next-work/environment_files-11p44`; copy the game directories you need. Other
copies of `environment_files` on this team's machines hold other builds of cn04, dc22, ka59 and
m0r0. Pointed at one of those, the engine stops with `no build for <game_id>`: a build id that
does not match the recording is an error, not a silent replay of a different game.

```bash
export ARC3_ENVIRONMENTS_DIR=/path/to/environment_files
python3.13 tools/recovery_eval.py build
python3.13 tools/recovery_eval.py ask --run-dir datasets/decision-steps/v0/recovery-eval/runs/<name> --base-url http://127.0.0.1:1234/v1 --model qwen38-27b-nvfp4 --api-key-file <key file> --k 4
python3.13 tools/recovery_eval.py score --run-dir datasets/decision-steps/v0/recovery-eval/runs/<name>
```

About `ask`:
- It samples the way the 27B baseline pinned: temperature 1.0, top_p 0.95, top_k 20, thinking on.
- It uses the request builder the harness uses.
- It sends one request per question and condition with `n=k`.
- It appends every reply, including the reasoning, to `responses.jsonl`, and a re-run asks only
  what is missing.

`score` needs no model. It can be re-run at any time and writes `scored.jsonl` and
`summary.json`.

The a108 server listens on `127.0.0.1` only, so tunnel to it with
`ssh -N -L 11234:127.0.0.1:1234 son@100.118.4.20`. Its key is
`ARC3-Inference/.cache/arc3_runtime/server-api-key` on that box. A post-training comparison must
reuse the serving settings in `docs/trace-findings/2026-09-16-qwen38-27b-baseline-result.md`.

## How to read it — fixed before the first full run

1. **The number is the paired difference in `repeated_failed` rate**, `with_history` minus
   `no_history`, per question and pooled. Negative means the model steers away from a choice it
   was told failed.
2. **A question whose `no_history` repeat rate is already zero cannot show that.** Report how many
   questions have room, next to the pooled number.
3. **`matched_win` is secondary.** X failing does not make Y the only good move.
4. **Repeating X is not proven wrong.** X's attempt failed later, not necessarily because of X, so
   the eval measures whether being told changes the choice, not whether the choice is correct.
   That is the property the step-5 plan asks about.
5. **For the base model this is a starting number, not a result.** The comparison the eval exists
   for, base against tuned on the same questions and settings, needs a tuned model.
6. **Small.** 23 questions × k samples × 2 conditions. A per-question table goes with every pooled
   number, and a difference of a few samples is not reported as an effect.
7. **Not the harness.** One turn, text only, no tool loop, no image. It measures the model's choice
   on a board, not what the agent would do over a game.
8. **All nine games are training-side** in the 18/7 split. Dr. Fable's §0 already rules that
   human-replay questions on training games do not contaminate the eval.
