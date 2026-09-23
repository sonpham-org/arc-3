<!--
Author: Claude Opus 5.5 (for Mark Barney)
Date: 22-September-2026
PURPOSE: Home for every solved-level trace that carries the model's thinking, whatever model
or box produced it (Boss directive, 22-Sep-2026). Until today the only copy of the first one
sat in Bubba's private workspace on the Mac Mini, where nobody else on the project could see it.
SRP/DRY check: Pass -- record shape is extract_sft.py's; this file only says what is here.
-->

# Solved-level traces (with thinking)

**Rule (Boss, 22-Sep-2026):** any log of a level being solved is training data, whatever model
produced it. The bottleneck is the solve rate, not the model. Keep every solved-level run,
make sure its thinking is saved, run `ARC3-Inference/distill/extract_sft.py` on it, and put
the output here.

Record shape is exactly `extract_sft.py`'s (`id, game_id, pass_index, run, level, solved,
level_actions, num_messages, num_assistant_turns, num_images, messages`). Each record's images
sit in the sibling `<stem>_images/` folder, named by content hash.

## What is here

| file | game | what it is |
|---|---|---|
| `jethro-20260922-bp35.jsonl` | bp35 | level 1 of 9 completed; 34 assistant turns, reasoning on all 34 |

**Read it correctly:** the run did **not** win the game. `summary.txt` says `won: 0`; both
games were *cancelled* on the two-hour wall clock. This is one cleared level.

## The run it came from

- Run: `20260922_170936_20260921_boss-prompt-two-games`, model `qwen/qwen3.8-27b` (dense 27B
  NVFP4), picture on, thinking on, host `gx10-a424` per `deploy_meta.json`. The provenance
  log calls this "the Jethro run".
- Raw run directory is still **local only**: `~/bubba-workspace/arc3-sft/runs-jethro/` on the
  Mac Mini (about 20 MB, mostly request logs). It belongs in `gs://cellens-ai-artifacts/arc3-duck/`
  with the other raw runs; the Mini has no bucket login, so someone with access needs to upload it.

## Not SFT, but keep it: the reasoned loss

The same run also played **sk48**: 42 actions, zero levels, and reasoning captured on every
request (`sk48-d8078629_p0_requests.jsonl` in the run directory). The SFT extractor rightly
drops it. It is, however, the negative half of a preference pair -- the thing a DPO/GRPO stage
needs and that the 14-Sep pipeline review said we owned none of. Do not delete it.

## Not usable

The Mac Mini LM Studio runs of 21-22 Sep saved no reasoning at all, so they cannot be traces.
Anything on `as66` is test-only and never belongs here.
