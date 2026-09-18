<!--
Author: Claude Opus 5 (Bubba)
Date: 18-September-2026
PURPOSE: Write-up for `ARC3-Inference/distill/recordings_to_sft.py` -- the converter that turns
the Boss's human ARC-3 replay recordings into the SFT record shape `distill/extract_sft.py`
already emits. Documents the observation-alignment proof, the reset/death decision, the
level-boundary reconciliation against humanPlay.generated.json, the measured counts, and an
explicit list of what was NOT verified.
SRP/DRY check: Pass -- this is the only write-up for this converter; it does not restate
extract_sft.py's design, only where the human path differs.
-->

# Human replay recordings -> SFT records

**Date:** 18-September-2026 · **Converter:** `ARC3-Inference/distill/recordings_to_sft.py`
**Input:** `datasets/decision-steps/v0/recordings/<game>-<build>/<guid>.ndjson` (18 winning runs, 10,418 rows)
**Run index:** `~/GitHub/arc-explainer/shared/arc3Games/humanPlay.generated.json`
**Output:** the record shape of `distill/extract_sft.py` -- `id, game_id, pass_index, run, level,
solved, level_actions, num_messages, num_assistant_turns, num_images, messages`, one record per
cleared level.

---

## 1. Headline

| | records | assistant turns |
|---|---|---|
| **Human demos (this converter, default)** | **130** | **5,559** |
| Human demos, `--keep-failed-attempts` | 130 | 9,451 |
| Human demos, with the held-out fence applied | 89 | 4,328 |
| Existing model-rollout corpus (`sft_baseline` + `sft_massdata`) | 41 | 381 |

The existing corpus was re-counted from `~/bubba-workspace/arc3-sft/out/` rather than taken on
faith: `sft_baseline.jsonl` 12 records / 113 turns, `sft_massdata.jsonl` 29 records / 268 turns
= 41 / 381. That matches the number in the brief.

So the human demos are **14.6x the turn count** of the entire existing corpus, and land above the
stated 2-5K turn target -- though **with the held-out test-set fence of section 8 applied it is
4,328 turns over 89 records, inside the target**. **The comparison is not apples-to-apples and should not be read as one.**
A model turn is one `action([...])` call that may execute a BATCH of environment actions; a human
row is exactly one action. 5,559 human turns and 381 model turns are not the same unit. Batching
consecutive human actions into one turn would shrink the count and move it toward the target, but
that is a corpus-design change beyond this brief -- flagged as an open question, not done.

Per game (`billed` = the ARC-3 scorecard's action count for that run; `kept%` = turns surviving
the failed-attempt prune):

```
game              records   turns  billed   kept%
ar25-0c556536           8     334     887   37.7%
bp35-0a0ad940           9     468    1024   45.7%
cd82-fb555c5d           6     216     216  100.0%
cn04-2fe56bfb           6     229     454   50.4%
dc22-fdcac232           6     643    1320   48.7%
ft09-0d8bbf25           6      84     133   63.2%
g50t-5849a774          14     655    1069   61.3%   (two winning runs)
ka59-38d34dbb           7     510     598   85.3%
lp85-305b61c3           8     201     415   48.4%
ls20-9607627b           7     454     561   80.9%
m0r0-492f87ba           6     337     752   44.8%
r11l-495a7899           6     161     316   50.9%
s5i5-18d95033           8     370     507   73.0%
sb26-7fbdac44           8     143     143  100.0%
su15-1944f8ab           9     190     293   64.8%
tu93-0768757b           9     190     297   64.0%
vc33-5430563c           7     374     575   65.0%
```

17 game builds, 18 runs (g50t has two). 3,892 rows were dropped as failed attempts and 116 as
attempt markers -- 4,008 rows, 43% of the billed actions. That is the price of section 3's
decision and it is deliberate.

---

## 2. What the converter does

For each `WIN` entry in `humanPlay.generated.json` that has a recording on disk:

1. **Segment.** Split the session file on `full_reset: true` rows. One `<guid>.ndjson` can hold
   several whole-game attempts. Select the segment by an exact predicate -- terminal `state`
   equals the export's `state` AND billable action count equals the export's `actions` -- and
   hard-fail unless exactly one segment matches. `runIndex` happens to equal the segment index
   on all 18, but using it would fall back to segment 0 silently the first time it did not.
2. **Cut levels.** A row whose `levels_completed` reaches the current level number is the action
   that cleared it. Cross-checked against the export (section 4).
3. **Prune failed attempts.** Within each level keep only the suffix after the last level `RESET`
   or death (section 3).
4. **Align observations.** Decision step k is shown row k-1's settled board (section 5).
5. **Build messages** by driving the harness's own code, not a hand-rolled format (section 6).
6. **Emit** one record per cleared level, `solved: true` by construction.

Levels after the last clear are dropped, matching `extract_sft.py`'s `only_solved` rule.

---

## 3. The reset decision

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
editing code via `--keep-failed-attempts` (9,451 turns instead of 5,559), so the call is
auditable rather than baked in.

---

## 4. Level boundaries reconcile exactly

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

## 5. The alignment proof

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

The chain is threaded across the WHOLE segment before pruning, so a pruned level still starts from
the board the player actually saw, and a death row's empty frame does not break it (`prev_board`
advances only on framed rows).

---

## 6. No hand-rolled message format

Nothing about the wire format is re-implemented:

- **System prompt:** `tool_agent._build_system_prompt()` verbatim.
- **User prompt:** `tool_agent.ToolAgent._build_user_prompt()` verbatim, called with a shim object.
  That method reads exactly one attribute of `self` (`_summarized_knowledge_lines`), which the shim
  answers with "empty ledger". `previous_step_summary` is reconstructed from the previous row, so
  the "Executed actions: LEFT." / "You have progressed to a new level!" lines are real.
- **Level boundaries:** the previous level's last step summary is carried into the next level's
  first turn, so that turn reads "You have progressed to a new level!" as it does at serve time,
  rather than the cold-start "No previous action sequence was captured." (112 of 130 records).
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
   parameter the prompt demands.
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
   list of ints, mapped through `ACTION{i}`, so `RESET` cannot be produced -- on all 5,559 turns.
   Checked against the serving path: `solver.model_action_names()` calls
   `_engine_action_names(..., include_reset=self.reset_refusal() is None)`, so at serve time
   `RESET` IS listed whenever the reset guard allows it. This is a systematic lexical omission
   with wider reach than the `world_model` gap -- it touches every turn, not just the tool call.
   It is at least internally consistent: the corpus contains no RESET demonstrations by design
   (section 3), so it never shows an action it did not list.
5. **`--inline-images` is required for training.** `distill/corpus_adapter.adapt` decodes only
   `{"type": "image_url"}` inline base64; the file-path part `extract_sft.py` emits by default
   passes through with no PIL image attached. This is a pre-existing property of the adapter, not
   of this converter, but it bites here too.

---

## 7. It encodes

All **130** records were run through the round-2 trainer's own encode path
(`distill/sft_batch.py` + `distill/corpus_adapter.py` from `feat/arc3-lora-round2-eval`) against
the real processor on `gx10-a424`, CPU only, `CUDA_VISIBLE_DEVICES=""`. **No training or inference
was launched. Nothing on a424 or a108 was modified** -- the two trainer files, the corpus and the
probe script were staged under `/tmp`.

```
130 / 130 records encoded without error
images attached == assistant turns on every record (5,559 / 5,559)

tokens per record : min 4,506 | p25 9,177 | median 13,236 | p75 20,994 | max 89,633
supervised tokens : 230,618 total
total tokens      : 2,225,802
mean              : ~400 tokens per assistant turn
>16K tokens: 53 records | >32K: 12 | >64K: 1
```

**The length distribution is the finding to act on.** The largest record
(`dc22-fdcac232/d13d39eb/L6`, 266 turns) is 89,633 tokens. `sft_batch.py`'s own header notes that
naive CE over the 27B vocab OOMs at ~20K tokens on a 121 GiB GB10 and that chunked CE is required,
not an optimisation -- 53 of these 130 records are past 16K and 12 are past 32K. Whether they fit
end to end at train time is a memory question this conversion did not answer.

---

## 8. What I did NOT verify

- **Whether these records fit in trainer memory.** They encode; that is all that was tested. No
  forward pass, no loss, no optimiser step. The 89,613-token record is well past the ~20K figure
  `sft_batch.py` calls out.
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
  section 3 prune anyway.
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

## 9. Reproduce

```bash
cd ARC3-Inference
python distill/recordings_to_sft.py \
  --recordings-dir ../datasets/decision-steps/v0/recordings \
  --human-play ~/GitHub/arc-explainer/shared/arc3Games/humanPlay.generated.json \
  --out ../scratch/sft_human.jsonl --inline-images \
  --exclude-games vc33,ar25,sb26,re86,su15,tr87,tu93,as66
```
