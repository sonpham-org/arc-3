# Branch replay: does the model need xhigh thinking for the whole level?

Son, 25-Sep-2026: *"I want to investigate how the model would do if we reduce its thinking efficiency. Take a
hard-7 run by our best harness (LA-CR). For each level that it solves, assume it is solved with N turns; for i
in 1..N, replay until finishing turn i, then generate traces from turn i+1 onward with the same prompt but
with high, medium and low thinking. Measure whether and how much action efficiency and token efficiency
change. If an alternative branch can, at some point in the level, switch to a more efficient thinking mode,
we may be able to train a LoRA that picks the next thinking mode and saves tokens without sacrificing
quality."* Later: *"Each branch plays until level solve / spending 2x more turns / spending 2x more actions."*
On scheduling: *"Main xhigh branch in 1 lane; at each checkpoint copy the KV cache to the remaining 6 lanes,
2 on low, 2 on medium, 2 on high."*

## Recording

`g4run-lacr-hard7-132-w7-20260924-92964fb0e9` (la_clean_return_hard7_132: 7 lanes, one wave, 7920 s per game,
temperature 1.0, xhigh thinking, no ledger compaction). 11 solved levels, 4,756 actions, 1,480 model responses.

| game | level | turns | actions | human baseline | level wall (s) |
|---|---|---|---|---|---|
| bp35 | 1 | 16 | 41 | 21 | 582 |
| g50t | 1 | 18 | 37 | 78 | 961 |
| g50t | 2 | 10 | 31 | 175 | 368 |
| g50t | 3 | 40 | 195 | 179 | 2659 |
| lf52 | 1 | 11 | 13 | 32 | 259 |
| lf52 | 2 | 151 | 707 | 81 | 5432 |
| ls20 | 1 | 10 | 31 | 22 | 795 |
| ls20 | 2 | 26 | 231 | 123 | 2338 |
| sk48 | 1 | 35 | 133 | 61 | 1739 |
| wa30 | 1 | 23 | 50 | 71 | 574 |
| wa30 | 2 | 35 | 281 | 119 | 2387 |

## How a branch is built (no re-generation of the prefix)

The harness transcript (`transcripts/<game>_p0.txt`) records every model response verbatim: `[THINKING]`,
`[ASSISTANT]`, the tool-call markup with the full code, `finish_reason`, and the per-turn outcome (step
executed / yielded after 60 s / request error). `branch_parse.py` turns it back into the exact request
sequence and validates every response against the transcript's own `reasoning_chars` / `content_chars` /
tool-call counts (all 1,480 match).

`branch_runner.py` (replaces `v12_run.py` on the VM) then, per job:

1. starts a fresh offline game and a fresh `ToolAgent` (bundle code, byte-identical);
2. for the first `replay_through_step` solver turns, `_chat_completion` returns the recorded responses; the
   recorded python snippets run in the real sandbox against the real engine, so frames, tool results, the
   runtime state and the persistent history are rebuilt exactly. Turn yields and the one request error are
   replayed too, so turn boundaries match; the displayed game clock is set to the recording's `time left`;
3. asserts at every turn that the live analysis step and action count equal the recording (replay divergence
   is an error, not a silent drift), and at the switch that the whole action prefix equals the recorded one
   (`prefix_ok`);
4. switches to live requests with the effort override and plays until the level is cleared, or 2x the
   original's remaining turns, or 2x its remaining actions (a 3x-wall-clock safety net protects the VM budget).

Effort override per request: `medium`/`low` = `chat_template_kwargs.reasoning_effort` (the Qwen3.8 template:
xhigh = the "think carefully" sentence, medium = no sentence, low = "keep it brief"); `high` = the request
carries a served template copy whose xhigh sentence is replaced by a milder one (same recipe as the
effort arms); `xhigh` = a fresh sample at the recording's own effort, the noise control.

KV sharing: vLLM prefix caching makes the "copy the KV cache to the other lanes" implicit. The seven
branches of one checkpoint (2 high, 2 medium, 2 low, 1 xhigh control) send a byte-identical prefix, are queued
adjacently and sharded to the same VM, so only the first prefill of a checkpoint pays for the prefix. The
xhigh main branch costs nothing: it is the recording.

## Plan and cost

`build_plan.py`: every turn of every solved level is a checkpoint (levels with more than 32 turns get 16
evenly spaced checkpoints, i.e. lf52 level 2); 178 checkpoints, 1,246 branches, 22,610 original-remaining-turn
units (~45 VM-hours at 50 s/turn). Checkpoints are ordered by position-in-level so partial coverage spans every
level; 12 shards (`derive_branch.py <pack> 12`) on 4-hour Spot g4-standard-48 VMs with the LA-CR arm's
golden image, serving flags, bundle, selftests and harness environment. Each shard resumes from its own
`runs/branch/results.jsonl` if relaunched.

## Metrics (`analyze_branches.py`)

- action ratio = branch live actions / recording's remaining actions from the same turn (solved branches);
- token ratio = branch completion tokens / recording's remaining generated tokens, the latter estimated from
  its reasoning+content+code characters with the tokens-per-char measured on the xhigh control branches;
- turn ratio, solve rate, per-level RHAE of the composite trajectory (human baseline / (prefix + branch));
- oracle switch value: at how many checkpoints a cheaper effort solved with no more actions than the
  recording, and the token saving if a router made exactly those switches.

## Files

`branch_parse.py`, `build_plan.py`, `branch_runner.py`, `derive_branch.py`, `launch_branch.py`,
`local_replay_test.py` (no-model fidelity test against the local engine), `analyze_branches.py`,
`arms/branch_lacr_s*of12/` (per-shard startup, runner, CONFIG, ADAPTER, ARM.json), `arms/branchpack.tgz`.
