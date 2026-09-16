<!--
Author: Claude Opus 5
Date: 16-September-2026
PURPOSE: Bring the Qwen3.8-27B baseline that ran on a108 overnight 15/16-Sep into the repo. Its
report exists only on that machine (~/arc3-baseline-20260916T013700Z/REPORT.md, written by the
agent Son directed). Records the per-game result, the answer to Dr. Fable's hard gate 1 (do the
seven held-out games score above zero on the base 27B), the settings a post-training eval has to
reuse, and the limits that make these numbers a floor rather than a measurement of the model.
SRP/DRY check: Pass - the readiness doc (2026-09-15-qwen27b-finetune-readiness.md) holds the
state of the boxes before the run; Dr. Fable's calls hold the gate; the split file holds the
partition. This holds only the run's result and what it closes.
-->

# The Qwen3.8-27B baseline: the held-out games are not at zero, so the split stands

**Run:** a108 (one GB10), 15-Sep 23:08 to 16-Sep ~05:10 EDT, directed by Son. All 25 public duck
games, one pass each. Harness run dir on a108:
`~/GitHub/arc-3/ARC3-Inference/runs/20260915_230835_qwen38-27b-baseline-25g/`. The agent's full
report, TPS sweeps and aggregation script are in `~/arc3-baseline-20260916T013700Z/`.

**Checked here, not copied:** all 25 per-game scores in the report match the harness's own
`score.json` to two decimals, and the seven games marked TEST are exactly the `test` list in
`datasets/splits/public25-train-test-split.json`.

## In short

- **Gate 1 is met.** 5 of the 7 held-out games scored above zero. vc33 cleared two levels and
  scored 8.99, the best result of the run. Only tr87 and tu93 scored zero. **The split is not
  redrawn.**
- **Overall: mean score 1.55, no game won, 11 of 25 games cleared at least one level.**
- **This is a floor.** Every game stopped on the 90-minute wall, having used about 30% of its
  108K generated-token budget. The model did not run out of budget; the run ran out of time.
- **The harness on a108 is not the in-tree harness.** It is an older snapshot, not a git
  checkout: it has no ACTION7 and no RESET guard, and it hides RESET from the model, as Dr.
  Fable's call 1.1 asked for this baseline.

## Per game

Pass@1 at temperature 1.0. Score is the harness score; tokens are generated tokens.

| game | half | levels | actions | tokens | score |
|---|---|---|---|---|---|
| vc33 | test | 2 of 7 | 30 | 36,738 | **8.99** |
| ar25 | test | 1 of 8 | 34 | 37,247 | 2.78 |
| sb26 | test | 1 of 8 | 71 | 39,111 | 2.78 |
| re86 | test | 1 of 8 | 30 | 37,550 | 2.23 |
| su15 | test | 1 of 9 | 53 | 41,868 | 2.03 |
| tr87 | test | 0 of 6 | 54 | 32,703 | 0 |
| tu93 | test | 0 of 9 | 102 | 30,226 | 0 |
| cn04 | train | 1 of 6 | 20 | 21,624 | 4.76 |
| r11l | train | 1 of 6 | 7 | 28,866 | 4.76 |
| sp80 | train | 1 of 6 | 40 | 30,075 | 4.76 |
| lp85 | train | 1 of 8 | 8 | 20,685 | 2.78 |
| s5i5 | train | 1 of 8 | 29 | 42,044 | 1.93 |
| ls20 | train | 1 of 7 | 42 | 31,401 | 0.98 |
| bp35, cd82, dc22, ft09, g50t, ka59, lf52, m0r0, sc25, sk48, tn36, wa30 | train | 0 | 3 to 137 | 24K to 38K | 0 |

| | games | cleared a level | mean score |
|---|---|---|---|
| test | 7 | 5 | 2.69 |
| train | 18 | 6 | 1.11 |
| all | 25 | 11 | 1.55 |

The test half scoring higher than the train half is **not a finding**. It is about two or three
games landing differently on one sample each, and vc33 alone is nearly half the test total. The
halves were balanced on human difficulty, not on how the agent does.

Of the bottom seven used in the Kaggle arms, only ls20 cleared a level (0.98). That comparison
crosses models, harnesses and time caps, so it says nothing about either model's strength.

## Limits carried from the run

1. **Time-capped at 90 minutes a game**, the agent's adaptation, not a Kaggle pin. Mean
   generated tokens per game were 32,815 against a 108K cap; the most was 42,044.
2. **39 model turns were lost** to the 900-second analyzer timeout, one or two in each of about
   14 games.
3. **g50t took only 3 actions** while generating 23,639 tokens, with 2 of its turns timed out.
   Read it as a harness failure, not a capability zero. A post-training "gain" on g50t could be
   nothing more than fewer timeouts.
4. **One pass at temperature 1.0.** Every per-game number is a single high-variance sample.
5. **Not a Kaggle-pin replica.** Besides ACTION7 and RESET, the snapshot has no context-swap and
   no search/scorer toggle.

## The settings a post-training comparison must reuse

The agent pinned these in `configs/a108.qwen38.baseline.json` (its `_pin` block) on a108 and left
the server running for that reason:

| | |
|---|---|
| served model | `~/models/Qwen3.8-27B-NVFP4` as `qwen38-27b-nvfp4`, vLLM 0.26.0 |
| context | 102,985 (`--max-model-len` and the harness window) |
| sampling | temperature 1.0, top_p 0.95, top_k 20, thinking on |
| lanes | 7 |
| per game | 90 minutes, 900 s analyzer timeout |
| image input | `current_grid` at upscale 4 |
| environments | `~/flash-next-work/environment_files-11p44`, all 25 builds exact |

Measured throughput at 7 lanes: about 59 generated tokens/s aggregate at a 12K-token context,
and no out-of-memory at any lane count. Memory was never the limit; latency was.

## What this closes, and what is running now

- **Dr. Fable's hard gate 1: closed, met.** The step-5 plan's §3 gate line points here.
- **Still open:** gate 2 (label the result as transfer within the public 25, and run as66 as
  the one out-of-lineup probe) applies to the post-training comparison, which does not exist yet.
- **Running on a108 now:** Son's mass-data run, 25 games × 4 passes at 25 lanes, started 16-Sep
  10:27 EDT with a 16-hour cap. Its own notes predict about 01:47 EDT on 17-Sep, with the last
  pass at risk of truncation. It generates rollouts; it is not a second baseline, because its
  lane count and 230-minute cap differ from the pins above.
- **a424** is idle, with no model on it.
