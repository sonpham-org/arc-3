<!--
Author: Claude Opus 5 (Bubba)
Date: 18-September-2026
PURPOSE: Write-up for `ARC3-Inference/distill/recordings_to_sft.py` -- the converter that turns
the Boss's human ARC-3 replay recordings into the SFT record shape `distill/extract_sft.py`
already emits. Documents the observation-alignment proof, the reset/death decision, the
level-boundary reconciliation against humanPlay.generated.json, the serve-time window each record
is cut to, the measured counts, and an explicit list of what was NOT verified.
Updated 18-September-2026 (second pass) with the 30-turn serve-time window: section 2 is new,
sections 1, 8 and 9 carry the new counts, and every later section number shifted by one.
SRP/DRY check: Pass -- this is the only write-up for this converter; it does not restate
extract_sft.py's design, only where the human path differs.
-->

# Human replay recordings -> SFT records

**Date:** 18-September-2026 · **Converter:** `ARC3-Inference/distill/recordings_to_sft.py`
**Input:** `datasets/decision-steps/v0/recordings/<game>-<build>/<guid>.ndjson` (18 winning runs, 10,418 rows)
**Run index:** `~/GitHub/arc-explainer/shared/arc3Games/humanPlay.generated.json`
**Output:** the record shape of `distill/extract_sft.py` -- `id, game_id, pass_index, run, level,
solved, level_actions, num_messages, num_assistant_turns, num_images, messages`, one record per
cleared level, each cut to the last 30 decision steps ending at the move that cleared it.

---

## 1. Headline

| | records | assistant turns |
|---|---|---|
| **Human demos (this converter, default: 30-turn window)** | **130** | **3,190** |
| **Human demos, windowed, held-out fence applied** | **89** | **2,281** |
| Human demos, windowed, `--keep-failed-attempts` | 130 | 3,308 |
| Human demos, windowed, `--keep-failed-attempts` + fence | 89 | 2,350 |
| Human demos, `--whole-level` (the first-pass default) | 130 | 5,559 |
| Human demos, `--whole-level` + fence | 89 | 4,328 |
| Human demos, `--whole-level --keep-failed-attempts` | 130 | 9,451 |
| Existing model-rollout corpus (`sft_baseline` + `sft_massdata`) | 41 | 381 |

The four `--whole-level` rows reproduce the first pass **exactly** -- 130/5,559, 89/4,328,
130/9,451 -- which is the regression test for the windowing change: record counts do not move
(130 default, 89 fenced), only turns, images and tokens do. Record identity is also unchanged:
the 130 `id`s are the same set, and with tool-call ids normalised each windowed record's message
body is a **byte-exact tail** of its whole-level counterpart, 130 / 130.

The existing corpus was re-counted from `~/bubba-workspace/arc3-sft/out/` rather than taken on
faith: `sft_baseline.jsonl` 12 records / 113 turns, `sft_massdata.jsonl` 29 records / 268 turns
= 41 / 381. That matches the number in the brief.

So the human demos are **8.4x the turn count** of the entire existing corpus and land inside the
stated 2-5K turn target both fenced (2,281) and unfenced (3,190). Windowing is what put them there;
it was not adopted for that reason (section 2) but it is the effect.
**The comparison is not apples-to-apples and should not be read as one.**
A model turn is one `action([...])` call that may execute a BATCH of environment actions; a human
row is exactly one action. 5,559 human turns and 381 model turns are not the same unit. Batching
consecutive human actions into one turn would shrink the count and move it toward the target, but
that is a corpus-design change beyond this brief -- flagged as an open question, not done.

Per game (`billed` = the ARC-3 scorecard's action count for that run; `kept%` = turns surviving
BOTH the failed-attempt prune and the 30-turn window -- it is no longer a prune-only figure, and
it falls hardest on the long runs, which is exactly what windowing is for: `dc22` ran 1,320 billed
actions and now contributes 173 turns):

```
game              records   turns  billed   kept%
ar25-0c556536           8     237     887   26.7%
bp35-0a0ad940           9     246    1024   24.0%
cd82-fb555c5d           6     129     216   59.7%
cn04-2fe56bfb           6     163     454   35.9%
dc22-fdcac232           6     173    1320   13.1%
ft09-0d8bbf25           6      84     133   63.2%
g50t-5849a774          14     394    1069   36.9%   (two winning runs)
ka59-38d34dbb           7     194     598   32.4%
lp85-305b61c3           8     176     415   42.4%
ls20-9607627b           7     194     561   34.6%
m0r0-492f87ba           6     163     752   21.7%
r11l-495a7899           6     145     316   45.9%
s5i5-18d95033           8     220     507   43.4%
sb26-7fbdac44           8     143     143  100.0%
su15-1944f8ab           9     173     293   59.0%
tu93-0768757b           9     190     297   64.0%
vc33-5430563c           7     166     575   28.9%
```

17 game builds, 18 runs (g50t has two). Two separate cuts, tracked separately by the converter
because they are separate decisions:

- **4,008 rows dropped as failed attempts** (3,892 pre-marker moves + 116 markers), 43% of the
  billed actions -- the price of section 4's decision.
- **2,369 further rows dropped outside the 30-turn window** -- the price of section 2's.

5,559 - 2,369 = 3,190. Note how nearly the two cuts overlap: with `--keep-failed-attempts` the
window still yields 3,308 turns, only 118 more than the default. Once records are windowed to 30
turns the prune decision barely moves the corpus, because the last 30 moves of a cleared level are
almost always inside the successful attempt anyway. **That is a real change in the stakes of
section 4** -- the reset argument mattered a great deal at whole-level granularity and matters
very little at this one.

---

## 2. The serve-time window

A whole cleared level can run to hundreds of consecutive moves. **At serve time the agent never
sees a context like that**, so training on one teaches a conditioning the model cannot use.

### The number is read off the serving path, not chosen

`ToolAgent.analyze` rebuilds `self._history_messages` after every turn through
`_persistent_history_messages` (`ARC3-Inference/inference/agent/tool_agent.py:1882`). That method
does two things in order:

1. `_trim_messages_for_context` -- a **token** bound. Budget is
   `_context_budget_tokens` = `LOCAL_ANALYZER_CONTEXT_WINDOW` (default 32,768) - reply reserve
   (512) - `_REQUEST_SAFETY_MARGIN_TOKENS` (512) = **31,744**. On overflow it trims not to the
   budget but to `_CONTEXT_TRIM_LOW_WATER` x budget = **19,046**, so later turns append into the
   headroom instead of re-invalidating the prefix cache every request (`tool_agent.py:1901`).
2. `_keep_recent_history_turns(max_turns=_PERSISTENT_HISTORY_ASSISTANT_TURNS)` -- a **turn**
   bound. `_PERSISTENT_HISTORY_ASSISTANT_TURNS = 30` (`tool_agent.py:170`). It walks the history
   backwards and stops once it has seen 30 messages with `role == "assistant"`, **inclusive of
   the newest** (`tool_agent.py:1853`).

So **30 is the serve-time number**, it is a hard module constant with no environment override, and
it is applied last. The Boss's estimate of "about thirty" was exactly right; there is no
discrepancy to report. The converter does not hardcode it -- it imports
`_PERSISTENT_HISTORY_ASSISTANT_TURNS` and uses it as the `--window-turns` default, so if the
serving path changes the corpus follows instead of silently drifting.

The token bound is the looser of the two here and is environment-driven, so it does not set the
default. Section 8 reports where the windowed corpus actually lands against it: max 13,495 tokens,
**0 records over 19,046 and 0 over 31,744**. At whole-level granularity 41 records were over
19,046, 13 were over 31,744 and one was 89,633 -- i.e. before windowing the corpus contained
records that the serving path could not have produced under either bound. Both columns were
measured by the same probe (section 8); the first pass reported `>32K: 12`, which is a different
threshold from the 31,744 budget and is not interchangeable with it.

### The rule

For each cleared level, keep the **last `--window-turns` (default 30) decision steps, the last of
which is the move that cleared the level**. Drop the earlier prefix. `--whole-level` restores the
un-windowed behaviour without a code edit, the same way `--keep-failed-attempts` keeps the reset
decision auditable.

Three implementation details that are load-bearing:

- **The slice happens after the whole level is built, never during.** Each turn's user prompt is
  rendered from the *previous* turn's step summary. Slicing inside the build loop would make the
  first windowed turn render "No previous action sequence was captured." -- true of a level start,
  false of a mid-level window. Building all events and then slicing means the first turn of a
  window correctly reports the move that preceded it, which is what a serve-time request shows
  after eviction.
- **`action_num` stays global.** A windowed record's first turn is numbered by its true position
  in the run, not renumbered to 1. That matches serve time, where the step counter keeps climbing
  through compaction.
- **`level_actions` stays the full billed count** from `levelActions[]`. It is a fact about the
  level, not about the record, and the per-level assertions of section 5 are computed from
  `LevelCut.rows` and are therefore untouched by windowing. They all still pass for all 18 runs.

### The invariant is asserted, not asserted-in-prose

"Ends at the clearing move" is checked (`_is_clearing_move` on `LevelCut.kept[-1]`) before any
slice, and the converter raises if it does not hold. If pruning or filtering ever removed the
clearing move, every windowed record would end one move early and **no count would show it** --
turns, records and level totals would all still reconcile. Verified on the emitted corpus
independently: 0 of 130 records fail to end on the clearing move's tool result, 0 exceed 30 turns,
69 sit at exactly 30 and 61 are shorter (those levels were cleared in under 30 moves and are
emitted whole).

### It makes the largest known asymmetry worse, and that is the cost

A whole-level record starts at the level start, where `_LedgerShim`'s empty knowledge ledger is a
plausible state. **A windowed record starts mid-level, where the serving path would always carry a
populated, just-compacted ledger** -- compaction exists precisely to fold the evicted prefix into
it. So windowing takes the corpus's biggest train/serve gap (section 7, asymmetry 1: `world_model`
absent) and makes it strictly worse: the record now shows an empty ledger in the one position
where serve time guarantees a full one. This is a new cost introduced by this change, it is not
mitigated here, and it is listed again in section 9.

### Turns are still not batched

One human row remains exactly one assistant turn. The known asymmetry -- a model turn may batch
several environment actions into one `action([...])` call, a human row cannot -- is untouched by
this change, on purpose. One consequence worth stating: 30 serve-time assistant turns may cover
*more than* 30 environment actions, so a 30-row human window covers at most as much game time as
the serve-time window and often less. The turn count matches; the action coverage is a lower bound.

---

## 3. What the converter does

For each `WIN` entry in `humanPlay.generated.json` that has a recording on disk:

1. **Segment.** Split the session file on `full_reset: true` rows. One `<guid>.ndjson` can hold
   several whole-game attempts. Select the segment by an exact predicate -- terminal `state`
   equals the export's `state` AND billable action count equals the export's `actions` -- and
   hard-fail unless exactly one segment matches. `runIndex` happens to equal the segment index
   on all 18, but using it would fall back to segment 0 silently the first time it did not.
2. **Cut levels.** A row whose `levels_completed` reaches the current level number is the action
   that cleared it. Cross-checked against the export (section 5).
3. **Prune failed attempts.** Within each level keep only the suffix after the last level `RESET`
   or death (section 4).
4. **Align observations.** Decision step k is shown row k-1's settled board (section 6).
5. **Build messages** by driving the harness's own code, not a hand-rolled format (section 7).
6. **Window.** Keep the last 30 decision steps of each level, ending at the clearing move
   (section 2). `--whole-level` skips this step.
7. **Emit** one record per cleared level, `solved: true` by construction.

Levels after the last clear are dropped, matching `extract_sft.py`'s `only_solved` rule.

---

## 4. The reset decision

Three distinct things appear in the recordings, only two of which are called "reset":

| marker | what it is | how many |
|---|---|---|
| `full_reset: true` | restarts the whole GAME | segment boundary |
| `action_input.id == "RESET"`, `full_reset: false` | restarts the current LEVEL | 109 in cleared levels |
| `state: "GAME_OVER"` with `frame: []` | the player died | 7 across all 18 recordings |

The third one is not documented anywhere and was found by inspection. Those 7 rows carry an
**empty frame** and report `levels_completed: 0` spuriously; the next row is always a level
`RESET`. They are level failures.

**Decision: both level-restart markers end a failed attempt, so on each level only the suffix
after the LAST marker is kept, and the marker row itself is dropped too.**

Reason: the moves before a reset did not clear the level -- that is what the reset says about
them. Keeping them would label a failed line of play as a demonstration of solving. The marker
row is dropped as well, because a `RESET` turn shown without the failure that motivated it
teaches "reset for no reason", and a death row has no board to show at all. Reversible without
editing code via `--keep-failed-attempts` (windowed: 3,308 turns instead of 3,190; whole-level:
9,451 instead of 5,559), so the call is auditable rather than baked in. **Windowing shrinks what
this decision is worth** -- see the arithmetic at the end of section 1.

---

## 5. Level boundaries reconcile exactly

For all 18 runs, the per-level action counts derived from the row stream reproduce the export's
`levelActions[]` **exactly**, and the non-full `RESET` count reproduces `resets` **exactly**. The
converter asserts both and raises on a mismatch, so a future recording that disagrees fails loudly
instead of contributing silently-wrong levels.

That exactness required one correction. A naive count is off by +5 on bp35, +1 on g50t run 1 and
+1 on tu93 -- and the deltas are `5, 1, 1`, which is exactly the number of empty-frame death rows
in each of those three recordings (7 total, and the empty-frame row indices are byte-for-byte the
same set as the rows where `levels_completed` regresses). The ARC-3 scorecard does not bill a
death as an action on the level. Excluding those rows from the count makes all 18 match. **This is
not an unexplained mismatch; it is a fully reconciled one.**

Related, and worth stating because it contradicts a natural assumption: **`guid` is not a unique
run key.** `s5i5-18d95033/850dee42` holds two runs (runIndex 1 GAME_OVER, runIndex 2 WIN) in one
file, and `sb26-7fbdac44` has two distinct winning runs that BOTH carry `runIndex 0`. Record ids
therefore key on `guid[:8]`, not on `runIndex`.

---

## 6. The alignment proof

**Claim:** the board stored on row k is the board row k's action PRODUCED -- the outcome, not the
observation. Therefore decision step k must be shown row k-1's settled board.

**Proof, game-agnostic, over all 18 recordings.** Group the level-`RESET` rows by level. A reset
returns the level to its start state, so:

- if the stored board is the OUTCOME, every reset row on the same level must carry the *same*
  board (the level start);
- if the stored board is the OBSERVATION, a reset row must carry whatever the player had flailed
  into just before resetting, which differs from reset to reset.

Measured:

```
same-level reset groups with >1 reset : 28
  ... in which all reset rows carry a byte-identical 64x64 board : 28   (100%)
reset rows whose board equals the pre-reset board : 0 / 119          (0%)
```

28 for 28, and 0 for 119. The stored board is the outcome. This is the same off-by-one
`extract_sft.py` documents for rollout artifacts, and the recordings have the same structure.

Two weaker checks were tried first and are recorded because they are *not* proofs: the colour at a
MOUSE click site changes between the pre- and post-action board in only 25% of clicks overall
(0.0% on dc22, 95.9% on cn04), so click-site colour discriminates nothing. Frame equality across a
reset boundary is also not a discriminator on its own -- tu93's reset board differs from the same
level's earlier start board when a step counter is rendered into the grid.

**The proof was then re-run against the emitted corpus, not just the recordings.** An independent
script re-derived the observation chain from the raw ndjson (separate code path, no shared helpers
with the converter) and compared its SHA-1 to the PNG filename on every user turn:

```
observation images checked                              : 5,559
mismatched vs independent re-derivation                 : 0
images that are the OUTCOME board instead of observation : 0
```

That re-derivation was run against the whole-level corpus and **was not re-run after windowing**.
It does not need to be: each windowed record's message body is a byte-exact tail of its
whole-level counterpart (section 1), so its 3,190 images are a subset of the 5,559 verified here.
Windowing drops turns; it never rebuilds one.

The chain is threaded across the WHOLE segment before pruning, so a pruned level still starts from
the board the player actually saw, and a death row's empty frame does not break it (`prev_board`
advances only on framed rows).

---

## 7. No hand-rolled message format

Nothing about the wire format is re-implemented:

- **System prompt:** `tool_agent._build_system_prompt()` verbatim.
- **User prompt:** `tool_agent.ToolAgent._build_user_prompt()` verbatim, called with a shim object.
  That method reads exactly one attribute of `self` (`_summarized_knowledge_lines`), which the shim
  answers with "empty ledger". `previous_step_summary` is reconstructed from the previous row, so
  the "Executed actions: LEFT." / "You have progressed to a new level!" lines are real.
- **Level boundaries:** the previous level's last step summary is carried into the next level's
  first turn, so that turn reads "You have progressed to a new level!" as it does at serve time,
  rather than the cold-start "No previous sequence has been executed yet." Windowing changes the
  mix of first-turn prompts, which is the visible sign that the slice happens after the build and
  not during it:

  | first turn of the record says | whole level | 30-turn window |
  |---|---|---|
  | "No previous sequence has been executed yet." (level 1 cold start) | 18 | 17 |
  | "You have progressed to a new level!" | 112 | 46 |
  | a real preceding-action summary (mid-level window) | 0 | **67** |

  67 records now open mid-level with the move that actually preceded them, which is what a
  serve-time request shows after eviction. If the slice had been taken inside the build loop all
  67 would have opened with the cold-start line instead.
- **Messages:** a per-step transcript in the harness's labeled-section format
  (`[SYSTEM PROMPT] / [USER PROMPT] / [TOOL CALL: python] / [TOOL RESULT: python]`) handed to
  `inference.tools.traces._messages_from_sections` -- the same reconstructor `extract_sft.py` drives.
- **Images:** `extract_sft._ImageStore` / `_attach_images`, i.e.
  `inference.agent.vision_context.frame_to_png_bytes`, at `--upscale 4 --style plain` to match
  `extract_sft.py`'s defaults.
- **Action:** `inference.agent.action_names.to_model_action` for `ACTION1..7 -> UP/DOWN/LEFT/RIGHT/
  SPACE/MOUSE/ACTION7`, and `row = data.y, col = data.x` for MOUSE, matching
  `solver._model_mouse_action_data`.

An assistant turn is therefore exactly:

```json
{"role": "assistant", "tool_calls": [{"id": "call_00001", "type": "function",
  "function": {"name": "python", "arguments": "{\"code\": \"action(['LEFT'])\"}"}}]}
```

No `content`, no `reasoning`. The Boss's per-move rationale was never recorded and is not invented
here. His per-level notes are out of scope for this converter and come through arc-explainer's
`/api/arc3/dataset`.

### Known, deliberate train/serve asymmetries

1. **`world_model` is absent.** The serve-time `python` tool takes `{code, world_model}` and the
   user prompt is emphatic that the ledger must be revised before acting. A human demo has no
   ledger, so these records emit `code` only. **This is the largest gap between a human record and
   a model record in this corpus** and it is visible to the model: every human turn omits a
   parameter the prompt demands. **Windowing makes it worse**, not better: a windowed record opens
   mid-level, where serve time guarantees a populated, just-compacted ledger. See section 2.
2. **The tool result is reconstructed, not captured.** `action(...)`'s real return carries `reward`
   and an animation summary; a recording supports neither. The emitted result dict carries only
   keys the recording actually supports (`executed, action_name, action_display, state, score,
   valid_actions, board_changed, done, level_completed, game_over, run_complete`). Omitted rather
   than guessed.
3. **The system prompt is today's, not the one the Boss played under.** He played in the ARC-3 web
   UI with no system prompt at all. The records carry the current serving prompt so the human turns
   sit in the same context the model will see. `MULTIMODAL_CONTEXT` is defaulted to `current_grid`
   inside the converter and the multimodal block's presence is asserted before any record is
   written -- a bare shell leaves it unset, which strips "User turns include an attached image"
   out of the system prompt while every user turn still carries one.
4. **`RESET` never appears in the valid-actions line.** `available_actions` in a recording is a
   list of ints, mapped through `ACTION{i}`, so `RESET` cannot be produced -- on all 3,190 turns
   (5,559 before windowing; the omission is per-turn, so windowing changes the count and not the
   fact).
   Checked against the serving path: `solver.model_action_names()` calls
   `_engine_action_names(..., include_reset=self.reset_refusal() is None)`, so at serve time
   `RESET` IS listed whenever the reset guard allows it. This is a systematic lexical omission
   with wider reach than the `world_model` gap -- it touches every turn, not just the tool call.
   It is at least internally consistent: the corpus contains no RESET demonstrations by design
   (section 4), so it never shows an action it did not list.
5. **`--inline-images` is required for training.** `distill/corpus_adapter.adapt` decodes only
   `{"type": "image_url"}` inline base64; the file-path part `extract_sft.py` emits by default
   passes through with no PIL image attached. This is a pre-existing property of the adapter, not
   of this converter, but it bites here too.

---

## 8. It encodes, and now it fits

All **130** windowed records -- and, for the comparison below, all 130 whole-level records and the
89 fenced windowed records -- were run through the round-2 trainer's own encode path
(`distill/sft_batch.py` + `distill/corpus_adapter.py`, byte-identical on `main` and
`feat/arc3-lora-round2-eval`) against the real Qwen3.8-27B processor on `gx10-a424`, CPU only,
`CUDA_VISIBLE_DEVICES=""`. **No training or inference was launched. Nothing on a424 or a108 was
modified** -- the two trainer files, the corpora and the probe script were staged under `/tmp` and
removed afterwards.

```
130 / 130 records encoded without error
images attached == assistant turns on every record (3,190 / 3,190)

tokens per record : min 4,506 | p25 9,176 | median 12,557 | p75 13,179 | max 13,495
supervised tokens : 134,398 total
total tokens      : 1,473,947
>16,384 tokens: 0 records | >19,046: 0 | >31,744: 0 | >32,768: 0 | >65,536: 0
```

With the held-out fence applied (89 records): 89 / 89 encoded, 2,281 / 2,281 images, min 5,144 |
p25 10,615 | median 12,632 | p75 13,180 | **max 13,495**, 94,012 supervised tokens, 1,037,092
total, and again 0 records over any of the thresholds above.

**Against the first pass, this is the result that matters:**

Both columns below come from **the same probe run against both corpora**, not from stitching this
pass's numbers onto the first pass's. That matters for one row: the first pass reported `>32K: 12`,
and the serve-time budget is 31,744, not 32,768 -- re-measured, **13** whole-level records exceed
31,744 while 12 exceed 32,768. Quoting the old 12 against the new threshold would have been a
relabel presented as a measurement.

| | whole level | 30-turn window |
|---|---|---|
| records | 130 | 130 |
| assistant turns | 5,559 | 3,190 |
| median tokens | 13,220 | 12,557 |
| p75 tokens | 21,052 | 13,179 |
| max tokens | 89,633 | **13,495** |
| records > 16,384 tokens | 53 | **0** |
| records > 19,046 tokens (serve low-water) | 41 | **0** |
| records > 31,744 tokens (serve budget) | 13 | **0** |
| records > 65,536 tokens | 1 | **0** |

The whole-level column's totals reproduce the first pass exactly (230,618 supervised, 2,225,802
total, max 89,633), which is what establishes it is the same corpus; its median reads 13,220 here
against the first pass's 13,236 purely because this probe computes quantiles with
`statistics.quantiles`. **41 of 130 whole-level records exceeded even the low-water mark the
serving path trims to.**

The median barely moves because the median level was already short; the **tail collapses**. The
89,633-token record (`dc22-fdcac232/d13d39eb/L6`, 266 turns) is now 30 turns and ~13K tokens. The
length distribution that the first pass called "the finding to act on" is the thing this change
acted on: `sft_batch.py`'s own header warns that naive CE over the 27B vocab OOMs at
~20K tokens on a 121 GiB GB10, and **no windowed record reaches 14K**. Chunked CE is still
required for other corpora; it is no longer this corpus that stresses it.

One number changed meaning and should not be read as a regression: the first pass quoted
"~400 tokens per assistant turn", which was *total* tokens / turns (2,225,802 / 5,559). Per
**supervised** token it was 41.5/turn then (230,618 / 5,559) and is 42.1/turn now (134,398 /
3,190) -- unchanged, as it should be, since windowing drops whole turns rather than reshaping them.

---

## 9. What I did NOT verify

- **Whether these records fit in trainer memory.** They encode; that is all that was tested. No
  forward pass, no loss, no optimiser step. The windowed records are all under 14K tokens, which is
  under the ~20K figure `sft_batch.py` calls out -- but "under the number in a comment" is not a
  measurement, and no forward pass was run to confirm it.
- **That an empty knowledge ledger mid-level is trainable.** This is the cost windowing introduces
  (section 2) and it was not measured. Serve time guarantees a populated, just-compacted ledger at
  exactly the position where a windowed record shows an empty one. Whether that teaches the model
  to ignore the ledger, or is harmless because the ledger is absent on every human turn anyway, is
  unknown. Synthesising a ledger would mean inventing the Boss's reasoning, which this converter
  refuses to do; the honest options are to leave it, or to drop human demos from the ledger-bearing
  part of the loss. Neither was done here.
- **The +/-1 reading of "30 turns."** The window is 30 turns *inclusive* of the clearing move, so
  the clearing move is emitted with 29 prior turns in front of it. At serve time the model emits
  that action with up to 30 *prior* assistant turns in the prompt, because
  `_keep_recent_history_turns` counts the history carried in and the new turn is generated on top
  of it. The inclusive reading is what that function does to a history and is the plain reading of
  the brief; the off-by-one against generation time was not chased. `--window-turns 31` settles it
  either way.
- **Whether 30 is the right training window, as opposed to the right serve-time number.** 30 is
  measured off the serving path and matches it exactly. That it is also the best window to *train*
  on is an assumption. `--window-turns` exists so somebody can measure 15 or 60 instead.
- **Whether windowing changes what the corpus teaches, beyond length.** Windowed records are
  end-games: the last 30 moves before a clear. Early-level exploration -- the probing a model
  actually has to do on an unseen game -- is now dropped from every level that ran longer than 30
  moves, which is 69 of 130. The corpus is more "how a level ends" and less "how a level is
  figured out" than it was. Not measured, not obviously wrong, but it is a change in kind and not
  only in size.
- **Pixel fidelity of the regenerated boards.** `extract_sft.py` proved its renderer pixel-identical
  against captured request logs. Human recordings have no captured request logs -- the Boss played
  in a browser, nothing rendered a PNG for a model -- so there is nothing to compare against. The
  renderer is the same function; that is an argument from shared code, not a measurement.
- **That the recordings' boards match what the Boss actually saw on screen.** The ARC-3 web UI's
  own rendering was not compared to `frame_to_png_bytes` output. Colour mapping, HUD chrome and
  scale may differ.
- **`sb26/11021704`, `tr87/d6580644`, `wa30/65d8cd9c` were NOT pulled.** The brief marked pulling
  them optional; `tools/replay_scrape.py` was not run and these three winning runs contribute
  nothing. wa30 in particular is a 17-reset run and would likely lose most of its rows to the
  section 4 prune anyway.
- **Whether the pruned corpus trains better than the unpruned one.** The reset decision is argued,
  not measured. `--keep-failed-attempts` exists so somebody can measure it.
- **Whether one-action-per-turn is the right granularity.** See section 1. Not tested against a
  batched alternative.
- **The 7 empty-frame rows' true cause.** They are `GAME_OVER` with no frame and are always
  followed by a level `RESET`, and their count exactly explains the action-count delta. "The player
  died" is the reading that fits every observation; it was not confirmed against the ARC-3 API.
- **Anything about the multi-frame animation lists.** `frame` holds 0 to 372 entries per row; only
  `frame[-1]`, the settled board, is used. The intermediate animation frames are discarded, as they
  are in `current_frame` at serve time.
- **The three test-only / held-out games.** `--exclude-games` exists and mirrors
  `extract_sft.py`'s fence, but no fence was applied to the numbers above. **`as66`, `vc33`,
  `ar25`, `sb26`, `re86`, `su15`, `tr87`, `tu93` must be excluded before this corpus is used for
  training** -- five of those eight (`ar25`, `sb26`, `su15`, `tu93`, `vc33`) appear in the table in
  section 1, and fencing drops exactly their 41 records, 130 -> 89. `re86` has no winning run,
  `tr87`'s recording is missing, `as66` never appears.

## 10. Reproduce

```bash
cd ARC3-Inference
# default: 30-turn window, fenced -- 89 records / 2,281 turns
python distill/recordings_to_sft.py \
  --recordings-dir ../datasets/decision-steps/v0/recordings \
  --human-play ~/GitHub/arc-explainer/shared/arc3Games/humanPlay.generated.json \
  --out ../scratch/sft_human.jsonl --inline-images \
  --exclude-games vc33,ar25,sb26,re86,su15,tr87,tu93,as66

# the first pass's whole-level records, unchanged -- add --whole-level
# a different window -- add --window-turns 60
```

The encode probe of section 8 (read-only, CPU, no weights loaded):

```bash
scp ARC3-Inference/distill/{sft_batch.py,corpus_adapter.py} son@<a424>:/tmp/probe/
cd /tmp/probe && CUDA_VISIBLE_DEVICES="" python probe_encode.py \
  ~/models/Qwen3.8-27B-BF16 sft_human.jsonl
```
