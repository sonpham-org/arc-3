<!--
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: Running changelog for the decision-step corpus work in this repo, newest first.
Exists so a reviewer joining cold can see where the work stands without reading fifteen pull
requests. Covers the corpus pipeline (datasets/decision-steps/, tools/replay_scrape.py,
scripts/test_decision_step_validator.py) and its trace findings. It does NOT change
the harnesses, which are frozen artifacts; where an entry documents a harness defect it is a
written finding about code this work leaves untouched, never a record of a change to it. The
in-tree `ARC3-Inference/` harness is a different matter: the 16-Sep RESET-guard entry below is
a real change to it, and further entries may be.
SRP/DRY check: Pass — plans live in docs/plans/ and docs/trace-findings/, schema semantics in
datasets/decision-steps/SCHEMA.md. This file only records what changed, when, and why.
-->

# Changelog

Newest first. Versioning is date-based; this work is pre-1.0 and the schema is pinned at
`0.2` — `run_ended` took that number in `7dcaa62`, and the per-game `boundary_reason` redesign
that had reserved it no longer has a number reserved.

---

## 17-Sep-2026 — the LoRA run was training 64 of its 208 adapters, and why

`tools/assert_lora_gradients.py` — a pre-flight that fails a training round before it starts if
any LoRA `lora_B` parameter is not receiving a gradient — plus
`docs/trace-findings/2026-09-17-lora-gradient-rootcause.md`, the root cause it was written for.

A LoRA step measured on the `unsloth/Qwen3.8-27B-NVFP4` checkpoint on the DGX Spark a424 reached
`loss.backward()` cleanly, reported a falling loss, and delivered a gradient to **64 of 208
adapters**. The 144 dead ones were not slow — `lora_B` sat at its zero init with an exactly-zero
gradient, and since `dL/dA ∝ B` their `lora_A` could never start moving either. Permanently inert.

Cause: that checkpoint's `quantization_config` fake-quantizes **input activations** on precisely
the seven projections the adapter targets (`self_attn.q|k|v|o_proj`,
`linear_attn.in_proj_qkv|in_proj_z|out_proj`) plus `lm_head`. compressed-tensors implements
activation quantization by replacing the module's `forward`, and the quantize call it inserts runs
under `@torch.no_grad()` — so the input is detached and **no gradient can cross a targeted
module**. peft conceals it: its added `lora_B(lora_A(x))` branch keeps `requires_grad` alive, and
because `lora_B` is zero-initialised that branch carries exactly zero backwards. The 64 survivors
are `o_proj` and `out_proj` in every layer — the only targets whose output lands on the residual
stream, so gradient reaches them without traversing a quantized module. `dequantize=True` does not
help; it decompresses the weights and leaves the patched forward in place.

Established on CPU with a tiny randomly-initialised model of the same architecture: the failure
does **not** reproduce under any combination of `eager`/`sdpa`, `use_cache` on/off, gradient
checkpointing on/off, fp32/bf16 — and reproduces exactly, module for module, the moment the base
layers' inputs are detached. Confirmed against the compressed-tensors and transformers source.

Fix: train from the plain BF16 checkpoint, or call
`disable_compressed_tensors_fake_quant(model)` after `from_pretrained` and before
`get_peft_model`. **The fix has not been run against the 27B** — that needs a GPU, which was in
use by another job — so the pre-flight is the gate: run it first on the next GPU session.
`--self-test` proves the check on CPU in seconds, green on a healthy model and red on this defect.

---

## Where this stands — 16-Sep-2026

Read this first if you are picking the work up cold.

**The corpus's role changed on 15-Sep.** Son's no-teacher decision (`7074b67`) means the 27B
bootstraps from its own rollouts, so these records are **the recovery eval, plus at most a
small mix-in**, not SFT teacher data. The four review questions in PR #21 are answered in
`docs/plans/2026-09-16-dr-fable-calls-on-the-step5-review.md`; read that before the plan.

**The goal.** A corpus of *decision steps*, not winning move sequences. Each record pairs the
board a player saw with the action they chose, a short **falsifiable** rationale, and an
`expected_observation` that the next frame either confirms or refutes. The metric it exists to
move is **recovery after falsification**, which is structurally absent from every trace we
hold. Spec: `docs/trace-findings/2026-09-14-decision-step-corpus-v0-plan.md`.

**Status of the four planned steps.**

| step | what | state |
|---|---|---|
| 1 | ACTION7 executes end to end | **done**, on `main` |
| 2 | JSON schema + validator | **done**, on `main` |
| 3 | replay scraper + guid inventory | **done**, on `main` |
| 4 | segment and label the corpus | **started** — A and B on `main`; the first D pass ran on lp85, was blocked on `action_role_source` for RESET, and is now **unblocked and landed** (the engine is vendored); C/E not begun |

**A second work line opened 15-Sep-2026 (Son Pham).** Stand a Qwen3.8-27B baseline on the
pinned Kaggle duck harness, then SFT/RL until *held-out* games improve. The train/test
partition it needs is done and guarded — `datasets/splits/public25-train-test-split.json`,
18 training / 7 held out. The hardware it needs is not: see
`docs/trace-findings/2026-09-15-qwen27b-finetune-readiness.md` for the measured state of the
two Sparks and the checkpoint-format blocker. **Update 16-Sep: the base 27B baseline ran on a108 and 5 of the 7
held-out games score above zero, so the split stands** —
`docs/trace-findings/2026-09-16-qwen38-27b-baseline-result.md`. That line does not change this corpus work; the
corpus is its teacher data, which is why the three games carrying labelled episodes are
forced into the training half.

**What exists right now.** **156 tests, all passing** — 65 + 15 + 33 + 33 + 10 across
`test_decision_step_validator`, `test_dispatch_tables`, `test_segment`, `test_build_sft` and
`test_train_test_split`.
Run those four by name: `pytest scripts/` collects 58 errors from unrelated suites in this repo
and tells you nothing about this work. The validator file gained 6 when `ProvenanceProseTests`
landed in `1fdfb37`, `test_build_sft` is new in `2469e82`, and the dispatch and segment files
gained 4 and 2 with the engine vendoring.

**That 156 assumes the recordings are on disk, and no single total is reproducible without
them.** From a genuinely clean clone it is **65 (11 skipped) + 15 + 4-of-9 (5 skipped) + 33 (2
skipped) + 10**. `test_train_test_split` needs no recordings and runs clean either way. `test_segment` *collects a different number of tests* in the two cases — five of its
classes skip in `setUpClass`, which unittest reports as one skip per class rather than per test,
so 4 + 5 class-skips expands to 4 + 29 when the recordings are there. Both numbers are real;
quote the split rather than a bare total, or the next reader cannot reproduce either. **280** human replay guids
inventoried across two manifests that are deliberately not merged — 250 published plus **30**
first-party, the latter having gone 28 → 30 in `1fdfb37` with the `ls20/7537433d` and
`m0r0/2134c482` wins — plus 250 leaderboard rows that carry no guid and never can be
fetched. **11 live-build recordings on disk, plus 15 for as66** — counted as
`find v0/recordings -name '*.ndjson'`, partitioned on the as66 directory. Do not use the
`ls */*.ndjson` glob a previous revision of this line cited: run from `v0/recordings/` it sweeps
as66 in with the rest and reports 26. The 11 went 9 → 11 when the `ls20` and `m0r0` recordings
were pulled this evening. **12 labelled records** across 3 games — still a demonstration of shape, not a corpus, but it now holds a completed falsification/correction pair and the recovery-versus-abandonment distinction. The 6 that `validate.py` used to reject for a reason no annotator could fix have landed; see the entry directly below. `tools/segment.py` now emits the
mechanical portion of a record (cuts, frame refs, measured outcome, source citation) so that
annotation is three judgment fields rather than a whole record.

**The one rule that governs step 4.** A run counts only if its `game_id` is **still the live
build** — an early replay is a replay of a different game. That leaves **100 of the blog's 250**
and **25 of the Boss's 30**, and every current build has game source, so citation is no longer a
constraint. Execution plan, with the selection rule and the five passes:
`docs/plans/2026-09-15-step4-segment-and-label-execution.md`.

**Open questions carried, not closed.** (1) is **closed** — see below. (2) `boundary_reason` carries
per-game values, which will not survive 25 games. (3) `level` is `levels_completed`, a count —
during play of the Nth level it reads N−1, so `"level": 5` means the 6th, and an episode
spanning a `level_advance` cut now shows it. All three are flagged in `SCHEMA.md` or the tool
docstrings; none has been quietly widened.

**Closed since the last entry.** Two. `last_result` could not express "that action ended the
run", so post-death records read like ordinary steps; schema 0.2's `run_ended` closes it, and
the segmenter measures a *flip* to `GAME_OVER` rather than its presence, so one death yields one
marker. And `boundary_reason` had no value for a level transition, so the segmenter refused any
window spanning one; `level_advance` closed that — see the 15-Sep (earlier) entry, including
what the refusal was hiding.

**Read the entry directly below before anything else.** It records a defect in
`ARC3-Inference/inference/framework/solver.py:171-172` that filters `RESET` out of the action
menu the model is shown, on every game — which, on a game like ls20 whose only recovery
primitive is RESET, is a candidate mechanical explanation for the agent's scores. **Nothing was
changed on the strength of it**; it is a written proposal for the Boss and Dr. Fable. That entry
also withdraws an over-broad claim about the recording reconcile rule and corrects two figures.

**Next.** Passes D (annotate, one agent per game) and E (the adversarial falsification gate) on
the 13 recordings already on disk. Pass C (pull the rest) is **off** unless the eval needs more
rows. On the harness track, the RESET-guard arm is built and verified (`harnesses/reset-guard/`),
run as Kaggle jobs 11 and 12 with a same-cap arm-B control. **Update 16-Sep: D and E piloted,
see the entry below -- the gate cut 12 of 23 and the corpus holds 11 records.** E is the one that decides whether any of it
is worth having: a record whose `expected_observation` the cited next frame can neither confirm
nor refute gets cut, not softened.

---

## 2026-09-16 — the chat template was silently eating every chain of thought (Claude Opus 5)

`distill/extract_sft.py` emits `reasoning` on assistant messages. The 27B's
`chat_template.jinja` reads `message.reasoning_content`, and its jinja macro renders `''` for a
missing field instead of raising. So `processor.apply_chat_template()` over our corpus **drops
every chain of thought, silently** — and since 56 of the 113 baseline assistant turns carry no
`content` at all (reasoning plus a tool call, no prose), those 56 turns render as an *empty
assistant message*. Trained on as-is, the model is taught to say nothing on half its turns.

Nothing in the corpus is wrong; the loss is entirely at the record → template seam, which until
now lived nowhere and was being re-derived by each consumer. New `distill/chat_adapter.py` owns
it: maps `reasoning` → `reasoning_content`, coerces `tool_call.arguments` from a JSON string to
the mapping the template demands (it raises otherwise), normalises absent `content` to `''` so
it cannot render as the string `"None"`, and decodes the inline base64 PNG parts to PIL images
in template order. It deep-copies, so caller records are not mutated. `extract_sft.py` is
untouched.

Verified against the real `Qwen3VLProcessor` for Qwen3.8-27B on gx10-a424, not asserted:
a 6-assistant-turn record renders 6 `<think>` blocks with the reasoning text present in the
output, and its 5 image parts expand to 320 image tokens — **64 tokens/frame, confirming exactly
the estimate the extraction write-up flagged as unverified** ((256/16)²/4 for 256×256 frames at
`patch_size` 16 with spatial merge 2). Re-measured whole-corpus token lengths under the real
processor come in ~1% above the estimates (max 53,956 vs 53,258 estimated); the conclusion that
**0 of 41 records exceed a 64K budget** holds.

Found while standing up the LoRA training path on a424. Full measurement record, including a
separate and more serious finding — that gradient reaches only 64 of 208 LoRA adapters on that
stack — is in `2026-09-16-a424-lora-step-measurement.md` (Bubba's workspace, not this repo).

---

## 2026-09-16 — the SFT extractor is verified against captured frames, and two alignment bugs are out (Claude Opus 5)

`ARC3-Inference/distill/extract_sft.py` was conceptually right and factually wrong in two
places. Both are fixed, and the fix is now checkable rather than argued.

**The board each turn was trained on was the wrong board.** `_analysis_events` attached an
analysis event's own `board` to that event's user message. That board is the state the event's
actions *produced*. The observation a step was decided from is the *previous* event's board —
`initial.board` for the first step. Verified against the run's own request logs: the step-1
request carries exactly one image and it is the `initial` board, never `analysis[0].board`. In
two of four spot-checked games the first action left the board unchanged, which is how this
survived. The chain is now built from the whole ordered event list before level grouping, so a
level's first step correctly takes its observation from the previous level. `traces.py` is
untouched. Baseline regression holds at 12 records / 113 assistant turns / 11 games; unique
rendered images move 73 → 69, which is the expected fingerprint.

**Records collided across passes.** `build_records` globs every `*_viewer_data.json`, and
`game_id` carries no pass suffix, so `ar25 p0 L1` and `ar25 p1 L1` emitted the same `id` and the
contributing-games counter deduped two real trajectories into one. `pass_index` is now part of
the `id` and a record field. This only bites multi-pass runs — i.e. the massdata corpus.

**New: `distill/verify_frames.py`.** Runs with `save_request_logs: true` store the exact
multimodal payload the model received, inline base64 and all. This decodes those frames and
compares them to what the extractor regenerates. Compare **pixels, not bytes** — the serving path
and Pillow pick different PNG encoder settings for the same raster, so identical images differ in
file size and byte comparison reports 0/17 on frames that are pixel-identical.

The run configs carry no multimodal block, so the `--upscale 4 --style plain` defaults were
unverified. A sweep settles it: that combination reproduces 55/58 frames, every other combination
of `upscale ∈ {1,2,3,4,6,8} × style ∈ {plain, outline}` reproduces 0. Coverage is complete — all
25 baseline games and both passes of all 14 contributing massdata games, i.e. every image part in
the corpus. Baseline: 399/415 frames overall, **102/102 of the frames that reach the corpus**.
Massdata: 480/511 and 251/253. Across the combined corpus that is **353/355 (99.4%)**. The two
exceptions are isolated single frames (`sp80-589a99af_p0` index 12, `tu93-0768757b_p0` index 1)
with matching frames either side; cause not established. Nearly all other divergence is in games
and levels the rejection sampler discards, where the harness emitted fewer images than analysis
events. The module's `FIDELITY CAVEAT` (`save_request_logs: false`, "exact image bytes are not
stored") was stale and is rewritten.

**New: `distill/corpus_stats.py`.** Token and shape measurement over an emitted corpus. Text is
tokenized; base64 image payloads are excluded and image tokens reported separately as a labelled
estimate, because running a text tokenizer over a data URL produces a number with no
relationship to what the vision encoder charges.

**What the corpus actually is.** Baseline plus both massdata passes on disk: 41 records, **381
trainable assistant turns**, 355 image parts, 1,270,599 measured text tokens. Nothing exceeds the
~64K trainer budget — largest record 53,258 tokens, median 34,829, **0 of 41 over**, and that
holds regardless of the vision-token estimate (that record carries 27 frames; at 4× the estimate
it reaches ~58.4K). Yield by
pass: baseline 23.9% (233/973 env actions at cleared levels, 11/25 games), massdata p0 34.8%
(411/1,182, 12/25), massdata p1 in progress 30.5% (267/875, 12/25).

Two notes for whoever reads a target number off this. The widely-quoted "233 usable turns" is an
**env-action** count, `sum(actions_per_level[:levels_completed])`; it reproduces exactly, but the
trainable figure from those same 11 games is 113 assistant turns, roughly 2:1. And four full
massdata passes plus the baseline project to ~600–700 turns against a 2–5K first-LoRA target. No
extractor change closes that: 11–12 of 25 games clearing exactly one level each is the ceiling.
The lever is game count and difficulty spread, or accepting lower-credit data — not the pipeline.

Findings write-up with the full tables: `docs/2026-09-16-arc3-sft-extraction.md` in the Bubba
workspace.

---

## 2026-09-16 — The recovery eval runner

`tools/recovery_eval.py`, questions in `datasets/decision-steps/v0/recovery-eval/items.jsonl`, how
to run and read it in that directory's `README.md`. The step-5 plan's §3 check, built.

**One question per fork.** A player chose X on a board and the attempt failed; later, on the same
board, chose Y and cleared the level. The model gets the board and is asked for one action, once
told that X failed here and once not told. **The answer is played on the real game.** The
recording is replayed in the offline engine to the fork and the answer applied, and the result is
compared with the boards X and Y leave. So it scores choices, not action text. Every recording on
disk replays frame for frame.

**23 questions, 7 of them with a pass-E-kept record.** The other 16 come straight from the
recordings, so they need no annotation and no review calls. They include the 9 forks in dc22, ft09,
ka59 and m0r0. The reading is fixed in the README before any full run: the paired difference in
how often the model repeats X, with history against without. `scripts/test_recovery_eval.py` (18
tests) holds the prompts to showing no Y and no record judgments, and checks that each recorded
choice scores as itself in the engine. `frame_evidence.diff_text` now delegates to `diff_grids`,
with identical output.

---

## 2026-09-16 — The Qwen3.8-27B baseline lands in the repo, and gate 1 is met

`docs/trace-findings/2026-09-16-qwen38-27b-baseline-result.md`. The baseline Son directed ran on
a108 overnight, but its report existed only on that machine. All 25 public games, one pass each:
mean score 1.55, no wins, 11 games cleared a level. **5 of the 7 held-out games score above zero
(vc33 8.99), so Dr. Fable's hard gate 1 is met and the split is not redrawn.** Every game stopped
on the 90-minute wall at about 30% of its token budget, so the numbers are a floor. The per-game
scores were checked against the harness's own `score.json`. The step-5 plan's gate line now
points to the result.

---

## 2026-09-16 — Passes D and E, piloted on the recordings on disk

`docs/plans/2026-09-16-pass-d-e-pilot.md`. Dr. Fable's item 2.

**Pass E is built and it cuts about half.** `tools/pass_e_review.py` sends each record to a
separate headless Opus reviewer with no tools and no project context, with evidence rendered from
the recording by `tools/frame_evidence.py`. On the 12 records already on `main` it cut 8, all
for source knowledge in `memory_in` (all seven lp85 records, and bp35 row 214). A control of
three planted defects was cut 3 of 3. Cut records are deleted.

**Pass D writes fork records.** `tools/find_retries.py` finds where the attempt that cleared a
level chose differently from a failed attempt on the identical board. 11 written, 7 survived pass
E. The corpus now holds 11 records. The recount of the material (11 recordings, 117 moments, no
cull) does not match the step-5 plan's 13 / 132 / 128.

The segmenter's acceptance test now reads a frozen copy of the four bp35 records under
`fixtures/segmenter/`, since one of them was cut. The split's pinned-game list gains g50t and ls20;
the partition itself is unchanged.

---

## 2026-09-16 — the RESET guard lands in the in-tree harness (Claude Opus 5)

`docs/plans/2026-09-16-intree-reset-guard-port.md`. The in-tree agent harness could not press
RESET: `_engine_action_names` dropped it from every menu the model sees. Arm I built and
verified that guard against a frozen bundle (`harnesses/reset-guard/`, PR #23); this ports the
behaviour onto `ARC3-Inference/inference/framework/solver.py` and
`ARC3-Inference/inference/agent/prompts.py`, so the harness this repo actually runs has it too.

**RESET was hidden, not blocked.** `taaf/game.py` injects RESET (id 0) into
`available_actions` unconditionally, and `step_env`'s availability gate has always passed it,
so a model that typed `RESET` in arms A–H executed one. The new
`scripts/test_reset_guard_intree.py` demonstrates that against a pre-port checkout, not from
argument. Filtering the menu alone would therefore have guarded nothing; the refusal lives in
`step_env`.

**The guard, unchanged from the reviewed arm.** `_RESET_MIN_ACTION_GAP = 20`. A model RESET is
refused when the previous executed action was a RESET — which covers the game's opening and the
harness's own auto-reset after a death — and when it would land within 20 actions of the last
model-chosen RESET. Auto-resets never consume that window. A refusal spends no action and
returns `stop_reason="reset_rate_limited"`; mid-batch it stops the batch, which is what
`step_env` already did for an unavailable action. Accepted and refused RESETs print
`RESET_GUARD` lines and each game prints a `RESET_GUARD_SUMMARY`, the shape
`kaggle/experiments/sparse-deletion/count_resets.py` reads.

**A call site the bundle patch never had to cover.** The frozen patch guards three menus; in
tree there are **four** — the analyzer turn, the error payload, the executed-action payload,
and the `solver turn start` log line, which is new since the patch was written. It is routed
through the guard too, so the log cannot report a menu the model was not offered. `include_reset`
defaults to `False`, so a missed site would compile and silently keep RESET hidden; the check
that matters is zero remaining `_engine_action_names(self.game)`, and there are zero.

**`prompts.py`** gains the arm's one 251-character bullet, verbatim, after the
`action(actions)` contract lines.

**Verified, not assumed.** `py_compile` on all three files; 0 unguarded and 4 guarded menu call
sites by grep; and 22 assertions in `scripts/test_reset_guard_intree.py` passing against the
live `ls20-9607627b` build through TAAF's offline `GameAPI` with `ONLY_RESET_LEVELS=true` —
opening refused, one move then accepted, level reset rather than full reset, counts as an
action, twice-in-a-row refused, both edges of the 20-action window, a batch stopping at a
refused RESET and reporting `stopped_early`, and an auto-reset refusing the next RESET without
spending the window.

This file's `PURPOSE` header claimed it records no changes to `ARC3-Inference`. That is no
longer true, so the header is amended to say so; no other prose in the file is altered. The
section heading stays date-only, per this file's stated date-based versioning — `0.2` belongs
to the corpus schema and is not bumped here.

`harnesses/`, `kaggle/` and `vendor/` are untouched, including
`taaf/game_api.py`'s process-wide `ONLY_RESET_LEVELS=true` — without that pin arcengine
full-resets whenever its action counter is zero, which `set_level` zeroes at the top of every
level, so a model RESET on a fresh level would zero the run.

---

## 2026-09-16 — Dr. Fable's calls on the step-5 review, and the corpus changes job

`docs/plans/2026-09-16-dr-fable-calls-on-the-step5-review.md`. PR #21 asked four questions;
these are the answers, posted as the PR review and then written down because a review is not
a document the next session reads.

**The corpus is the eval now, not the teacher.** Son's no-teacher decision removed the role
the corpus was specified for. `README.md`'s first line, the step-5 plan's status block and the
"Where this stands" section above now say so. The split's training-only constraint on bp35,
cn04 and lp85 is left in place as harmless; drop it on any redraw.

**RESET: measured, not argued.** The 27B baseline runs pinned with RESET hidden. One Kaggle arm
on the bottom seven exposes RESET behind a guard (never twice in a row, at most one per 20
actions) and reports reset rate next to level clears. The review's option (c) is dropped; the
"chose RESET on a live board" records stay as eval rows. The ls20 fact that decides it: RESET
on a live board refills three lives and the step meter, so on four 21-step levels it is how a
human wins, and the harness cannot make that move on any game.

**Ceiling: pilot only.** Passes D and E on the 13 recordings on disk; pass C is off.

**Measurement: two gates.** Held-out games must score above zero on the base 27B or the split
is redrawn on measured agent difficulty; the 18/7 result is labelled as transfer within the
public 25, with as66 as the one out-of-lineup probe.

**Convention: imposed.** Schema and validator changes go through a PR that names the migration
and ships the script. `validate.py` already refuses a stale `schema_version`; that stays.

**Also fixed:** `SCHEMA.md`'s field table still said `schema_version` was `"0.1"`; it is `"0.2"`.

---

## 2026-09-15 (newest) — the 18/7 split for the Qwen3.8-27B experiment

Son Pham's directive of 21:03 EDT opens a second line of work in this repo: stand a
Qwen3.8-27B baseline on the pinned Kaggle duck harness, then SFT and RL until *held-out*
games improve. That requires a train/test partition of the 25 live public builds, and it
requires the two DGX Sparks cleared of Flash Next first. This entry covers the split, which
is done, and records the measured state of the hardware, which is not.

### `datasets/splits/public25-train-test-split.json` — 18 training, 7 held out

Generated by `tools/make_train_test_split.py`; no RNG, no seed, same inputs produce the same
file, and `scripts/test_train_test_split.py` asserts that by regenerating and comparing.

**Training (18):** bp35 cd82 cn04 dc22 ft09 g50t ka59 lf52 lp85 ls20 m0r0 r11l s5i5 sc25
sk48 sp80 tn36 wa30
**Held out (7):** ar25 re86 sb26 su15 tr87 tu93 vc33

Difficulty is the mean of three z-scored human-derived signals — `baseline_total_actions`
(the dominant cost axis under a 108K generated-token per-game cap), level count, and the
median actions the ten fastest human *winners* spent — cut into terciles. The ranking passes
inspection at both ends: cd82 easiest (6 levels, 171 baseline), lf52 hardest (10 levels,
1,339 baseline, 792 median).

**Stratified on two axes, not one.** Difficulty alone would have leaked input modality. The
lineup is 13 `keyboard_click`, 7 `click`, 4 `keyboard` and one untagged; a test set drawn on
difficulty alone can take every `click` game into training, at which point "improvement on
held-out games" is confounded with interface transfer and a reasoning gain is not separable
from an interface gain. The held-out seven hold the proportional quota — 4 / 2 / 1 — and
terciles 2 easy / 3 medium / 2 hard, against train's 6 / 6 / 6. Mean difficulty agrees to
1e-4. Every test set meeting the modality quota was enumerated exhaustively (29,700 of them)
and scored on tercile match, then mean gap, then spread; ties break on sorted game id.

**A leak was found and closed rather than noted.** The unconstrained split put bp35, cn04 and
lp85 — every game with labelled decision-step records — into the held-out set. That corpus is
the SFT teacher data this repo exists to produce, so the held-out measurement would have been
contaminated before a step was trained. Games carrying episodes in
`datasets/decision-steps/v0/episodes/` are now training-only, derived from what is on disk so
the constraint tracks the corpus as it grows rather than going stale as a hardcoded list.

A property that fell out rather than being aimed at: six of the seven held-out games are ones
the Boss has never played, and the seventh (re86) he has never won. There are no first-party
human recordings behind the held-out set at all, so there is no human-trace contamination
route into it either.

**The caveat that matters, and it is written into the file, not just here.** This is *human*
difficulty. Nothing in this repo measures per-game agent difficulty — `ARC3-Inference/runs`
is empty — so the model's ordering may differ. After the base-27B baseline lands, check that
the held-out seven are not uniformly zero. **A test set the base model scores zero on cannot
show improvement no matter what training does**, and in that case the split must be redrawn
against measured scores.

Ten tests. The two load-bearing guards were poison-checked: moving lp85 into the held-out set
fails the leakage guard, and deleting one id from `DUCK_HARNESS_PUBLIC_GAME_IDS` fails the
lineup guard with the message telling the reader to regenerate rather than edit the
assertion. That lineup guard exists because the split is only meaningful over the games the
harness actually runs — verified byte-identical between `kaggle.py` and
`current-builds.json` at the time of writing.

### `docs/trace-findings/2026-09-15-qwen27b-finetune-readiness.md` — measured, and one blocker

Written against the boxes, not against the runbook. Three findings worth carrying:

1. **The two Sparks are one cluster, and Flash Next held every GPU on it.** `ray status`
   reports 2 active nodes and `2.0/2.0 GPU (2.0 used of 2.0 reserved in placement groups)`.
   Nothing in the directive could have started while it was up, so the teardown is the
   unblocker rather than housekeeping. It was idle when measured — 0 running, 0 waiting, and
   54 requests across its whole 2d18h lifetime, all finishing on `length` at ~65 prompt tokens
   each, i.e. smoke probes. **The a108 container has been stopped** (`docker stop`, restart
   policy `no`); a108's GPU now shows zero compute processes. The 126G of weights, the image
   and the hand-written PLE patches in `~/flash-next-work/` were all left in place, and
   `docker start arc3-flashnext-ray-head-04a25` puts it back. a424's worker container still
   holds its GPU and needs access this account does not have.
2. **Sherlock is not on Flash Next**, so the removal and the model repoint are independent
   changes and neither gates the other. Its config points at Ollama on `:11434`; that is a
   file read, and the effective runtime backend should be confirmed against the process
   before weights are deleted.
3. **The 27B on disk cannot be trained as-is.** `~/models/Qwen3.8-27B-NVFP4` is a
   compressed-tensors checkpoint — the format vLLM serves — while the runbook's learner path
   is Unsloth's bitsandbytes NF4. Different formats, not interchangeable, and the Unsloth
   entry in the HF cache is a 12K metadata stub with no weights. The learner needs the pinned
   BF16 upstream at ≈54G, against 178G free. **That is the concrete reason the 126G teardown
   is a prerequisite and not housekeeping.**

Also recorded: the committed a108/a424 configs diverge from the Kaggle pins on exactly the
axes the directive named — context 32,768 against 102,985, lanes 2 or 25 against 7,
temperature 0.6 against 1.0 — and 7 lanes at ~103K context on one GB10 is the likeliest
failure point. The directive authorised adapting the time limit and nothing else, so maximum
feasible lanes × context is to be measured and reported, not quietly reduced.

**No teacher — settled at 21:19 EDT, and Son was right.** The runbook proposed Flash Next as an
SFT teacher; the directive said remove it. Son's objection is that RL is on-policy, so a second
model has no role in the loop, and the runbook concedes the point three times over: teacher
traces are off-policy demonstrations (§5), their token ids cannot be reused across a different
tokenizer and template (§6), and they must not be used as current-policy GRPO samples (§10).
They were only ever an SFT *bootstrap*.

The one thing a bootstrap buys is **reward variance**, not game knowledge: group-relative RL
learns from differences within a group, so a game the base model never scores on contributes
zero gradient and pure spend. Whether that bootstrap is needed is what the baseline measures —
which is why the directive's own ordering is right. And if it is needed, the better source is
the 27B's own successful rollouts by rejection sampling: same tokenizer, same template, no
train/serve skew, collected during a run that has to happen anyway.

So the weights went. 206 shards, 126G, removed from a108 — **178G free → 304G free**, which
clears the ~54G BF16 learner checkpoint with room for adapters, optimizer state and trace logs.
The 58MB of non-weight files were preserved first at
`~/models/flash-next-nvfp4-conversion-record/` — config, chat template, tokenizer, shard index,
`conversion_environment.json`, the unchanged-audit report and the aime26/gsm8k metrics. All 549
were counted at source and re-counted at the destination before a shard was touched, with a
mismatch set to abort. That record is what makes the model re-creatable from a fresh weight
download instead of from scratch. a424 still holds its own GPU and probably its own copy.

Nothing in `ARC3-Inference` was touched.

---

## 2026-09-15 (latest)

### ls20: three lives a level, a 42 that is often 21, and a RESET that refills both

`docs/trace-findings/2026-09-15-ls20-lives-and-the-filtered-reset.md`. The game mechanic behind
the Boss's ls20 win, written because `first-party-replays.json`'s ls20 attribution cites it and
because the step-budget half was not written down anywhere. The harness half is **not**
duplicated — it is owned by the evening-session entry below and cited from section 4.

**Lives are per LEVEL.** `ls20.py:1821` sets three, inside `on_set_level` (`:1778`); budget
exhaustion spends one (`:1950`, `:1961`); the third ends the run (`:1962-1963`). RESET re-enters
the hook through the engine (`base_game.py:205 → :305 → :326 → :328 → :164`) and so refills
lives *and* the step meter.

**Measured, not inferred.** The pips render at frame row 61, x=56/59/62, colour 8. Across all
562 rows they take exactly three states — 419 rows at three lives, 140 at two, 3 at one — and
never reach zero, which is the same fact as the recording carrying no `GAME_OVER` row. **Row 454
is the mechanic in one row:** one life left, RESET pressed, three lives back, `levels_completed`
unchanged. All three of that run's resets were taken on a *live* board, so RESET on ls20 is a
life refill bought for a level restart, not recovery from death.

**The "42-step budget" is 42 on three levels and 21 on four.** All seven declare
`StepCounter: 42`, but the meter drains by `StepsDecrement`, default **2** (`ls20.py:1771`),
overridden to 1 only on levels 1, 4 and 6 (`:724`, `:1088`, `:1324`). Derived by *parsing the
level objects*, not by reading line proximity in `LEVELS_SPEC` — the partial-read mistake
`AGENTS.md` warns about, which would have mapped the overrides to the wrong levels. A record
claiming "42 moves on this level" is wrong on four of seven.

**Three of the line numbers this was asked to check were wrong, and section 5 lists them.** Two
off-by-ones (`:1962` is the test, `:1963` is the `lose()`; the harness filter is
`solver.py:171-172`, not `:170-171`), and one substantive: the claim that `solver.py:752` would
reject a RESET anyway is **false** — `taaf/game.py:188-193` always re-adds RESET (0) to
`available_actions`, so that gate passes. It is one filter, not two, which makes the proposed
harness fix a one-place change. Verified in this tree, not relayed.

---


### The RESET blocker is cleared: arcengine is vendored, and six stranded records land

Committed direct to `main` at the Boss's instruction.

**The blocker, restated in one line.** `action_role_source` must cite a `<path>:<line>`, `RESET`
is dispatched by the engine rather than by the games, and the engine was not in this repo — so a
`RESET` step could only be labelled on the 2 of 8 in-scope games (`bp35`, `lf52`) that happen to
carry their own branch. `RESET` is the only recovery primitive on **19 of the 25 live builds**,
and recovery after falsification is the metric this corpus exists to move. The corpus could
record recovery only on the games least representative of how recovery works. That is a
selection effect introduced by a regex.

**Resolved by option 3 of the four the lp85 doc listed: vendor the engine.** That doc called it
"the largest change"; measured, it is the smallest. `arcengine` is **2,342 lines**, **MIT**, the
**only release ever published** on PyPI, already declared at
`tufa-arc-agi-framework/pyproject.toml:9` and already pinned in `uv.lock` — whose sdist sha256
the downloaded tarball matched exactly, a chain that predates this work. It is unpacked
unmodified at `vendor/arcengine-0.9.3/`; `vendor/README.md` carries the provenance and the scope
limit. Why not the other three, in one line each: relaxing the pattern (1) permanently weakens
the field for every record to fix one action on six games; citing the dispatch table (2) cites
*an absence* and would have been the only citation class with no drift guard; accepting the bias
(4) writes the selection effect down permanently instead of removing it. Full argument:
`docs/trace-findings/2026-09-15-lp85-step-budget-and-the-uncitable-reset.md` §5.

**What landed.** `tools/segment.py`'s `citation()` gained an engine fallback — game source
first, because a game's own branch is what distinguishes that build, then the engine. All eight
dispatch tables gained an `engine` block with 13 anchors each, drift-checked against the
vendored file exactly as game anchors already were, plus a per-file sha256 guard and a check
that `uv.lock` still pins the sdist the tree came from. And the six records that had been
carried verbatim in that doc because they could not be written are now at
`v0/episodes/lp85-305b61c3__129ddf21…__reset-recovery-and-abandonment.jsonl`, 6 records, 0
errors, frame resolution **ON**. They were re-emitted by the segmenter and compared
field-for-field against the doc's transcription before landing rather than pasted; every
mechanical field agreed.

**The five level-8 rows are the reason this was worth doing.** Every `RESET` record before them
followed a death. These follow none — the board is alive, 11 to 42 of 64 budget cells spent — so
`action_role` now separates *recovery from a dead board* from *abandoning a plan on a live one*.
A corpus that cannot tell those apart teaches "reset when dead", which is the easy half. Row 176
is also the first completed falsification/correction pair whose halves are separate records: the
negative record on row 175 is the falsified decision, and 176 is the correction the player
actually made.

**A defect on `main` that this uncovered, and that was stopping everything.** Schema 0.2
migrated every fixture and every committed record and added `run_ended` to the segmenter's
output — but left `tools/segment.py`'s `SCHEMA_VERSION` at `"0.1"`. **Every record pass A
emitted was rejected by `validate.py` on the version alone.** A whole-pipeline stop, invisible
because no test compared the two constants. Fixed; `SchemaVersionTests` now asserts they agree.

**An apparent contradiction the vendored source resolved rather than left hanging.**
`base_game.py:278` skips the action-count increment for `RESET`, which looks like it contradicts
the reconcile rule in `datasets/decision-steps/README.md`, where `RESET` rows *are* counted as
actions. They are two different counters: `ls20` reports 561 actions over 562 rows containing 3
non-boot `RESET`s, where `ARCBaseGame._action_count` would give 558. The session API's counter is
not the engine's, and `vendor/README.md` says so.

**Scope limit, stated not implied.** It is **not** verifiable from this repo that
`three.arcprize.org` runs 0.9.3 — the service exposes no engine version. 0.9.3 is the only
arcengine ever published and the one this repo pins, so a citation into it is a citation into
the only arcengine anyone can read. Every emitted citation carries
`[arcengine 0.9.3, engine-level: …]` so it claims that and not more.

**Not done, deliberately.** No harness code was touched. `ACTION7` is **not** resolved by this —
it has no engine branch either, and on the 19 builds that do not offer it there is nothing to
cite because there is nothing that runs. Five new guards were poison-checked: vendored-file
edit, engine anchor drift, a note reverting to "not vendored", segmenter/schema version drift,
and the `uv.lock` pin.

---

## 2026-09-15

### Evening session: five human wins, and a harness defect that says the agent cannot press RESET

Written for a reviewer picking this up cold. Every file:line below was opened in this tree
before it was written down; where a claim is not verifiable from this tree it says so.

**No ARC3-Inference or harness code was changed by this entry, and none should be on the
strength of it.** The `solver.py:171` item is a written proposal. Whether to act on it is the
Boss's and Dr. Fable's call.

#### The headline: the agent is never shown RESET

`ARC3-Inference/inference/framework/solver.py:171-172` contains `if name == "RESET": continue`,
inside `_engine_action_names()` (`:164`). That function builds the `valid_actions` list on both
payload paths — the error payload at `:692` and the per-action payload at `:928` — and
`valid_actions` is what gets rendered into the model's prompt as "Valid actions right now"
(`agent/tool_agent.py:1408`). **RESET is filtered out before the model ever sees it.**

The only RESET the harness issues is `_execute_auto_reset()` (`:825-827`), fired by the runner
loop at `:347-352` *after* `_is_engine_game_over()` is already true. That is cleanup, not
strategy: by then the run is over and the reset cannot be used to recover from anything.

**Correction to an earlier reading of this, from Sherlock, re-verified here and accepted.** It
was originally called a two-gate problem, on the claim that the execution-side membership check
at `solver.py:752` (`if action.id.value not in self.game.current_state.available_actions`) would
also reject a RESET. That is wrong. `tufa-arc-agi-framework/src/taaf/game.py:188-193` defines
`available_actions` as "Legal action ids, with RESET (0) always present" and re-adds `0`
unconditionally when it is absent. The execution gate passes. **Deleting the one filter at
`:171-172` is the whole fix.**

Sherlock also correctly noted that `taaf/game_api.py:222` sets
`os.environ["ONLY_RESET_LEVELS"] = "true"` process-wide immediately after `arcade.make`, which
is what stops an at-level-start RESET from restarting the entire run; the code comment at
`:215-221` describes precisely the arcengine behaviour we had independently observed on as66.
One nit for the record: Sherlock cited the filter at `solver.py:119-120`; in this tree it is
`:171-172`.

#### Why it matters, measured on ls20

`docs/static/games/src/ls20-9607627b/ls20.py` gives a per-level life budget the agent has no
way to refill:

- `:1821` — `self.aqygnziho = 3`, inside `on_set_level` (`:1778`). Three lives **per level**,
  not per run.
- `:1950` + `:1961` — running the per-level step meter out (`not _step_counter_ui.mfyzdfvxsm()`,
  the decrement-then-test at `:1487-1490`) costs one life.
- `:1962-1963` — `if self.aqygnziho == 0: self.lose()`. The **third** loss on a single level
  ends the whole run.
- `:1525-1529` — the three pips render at frame rows 61–62, x = 56/59/62, colour
  `tqogkgimes` = 8 (`:1458`), lit while `aqygnziho > i`.
- `:1778-1782` → `:1794` → `:1773-1776` — RESET re-runs `on_set_level`, which re-clones the
  pristine level (`:1780`), resets lives to 3 (`:1821`), and calls `wbcenorpju()` (`:1794`),
  which refills the step meter via `nzukewekzr()` (`:1492-1493`). Note the hop: `:1773-1776`
  lives in `wbcenorpju`, not in `on_set_level` — an earlier draft of this entry cited it as
  though it were inline, and it is not. RESET is the only mid-level refill that exists.

Confirmed on tape, not just in source. Tracking `frame[61][56|59|62] == 8` across all 562 rows
of the Boss's winning run (`ls20-9607627b/7537433d-…`), the pip count changes exactly seven
times: 3→2 at row 36, 2→3 at 81, 3→2 at 225, 2→3 at 277 (all level advances), then **3→2 at
408 and 2→1 at 451** on the final level — one timeout from `lose()` — and **1→3 at row 454, a
RESET**. He went on to win, at score 100. The run's other mid-run RESET, at row 135, left the
pip count at 3: a reset spent purely to refill the step meter, with no life lost.

ls20 is also one of the **19 live builds with no ACTION7** — checked across
`docs/static/games/src/*/`, where the six that do carry it are ar25, bp35, lf52 (conditionally,
`[7] if STORES_UNDO`), sb26, sk48 and su15. So on ls20 the agent's only recovery primitive is
the one the harness filters out. That is a plausible mechanical cause for ls20 scoring badly,
and it costs one line to test.

#### Five human wins from the Boss, all re-derived from tape

| game | guid | state | levels | actions | baseline | resets | score |
|---|---|---|---|---|---|---|---|
| ka59 | `1333b2ee` | WIN | 7 | 598 | 730 | 2 | 84.57 |
| lp85 | `129ddf21` | WIN | 8 | 415 | 388 | 6 | 76.39 |
| ls20 | `7537433d` | WIN | 7 | 561 | 776 | 3 | **100** |
| m0r0 | `2134c482` | WIN | 6 | 752 | 1107 | 10 | **100** |
| g50t | `58483738` | WIN | 7 | 536 | 879 | 8 | 82.12 |

Every cell checked against the 18:50 EDT scorecard snapshot
(`arc3-run/boss-replays/boss-runs-2245.json`); `baseline` is the sum of
`level_baseline_actions`. The g50t row carried two blanks in draft — they are filled here, not
dropped. All five recordings are on disk and gitignored
(`.gitignore:34`, `datasets/decision-steps/v0/recordings/`).

**lp85 is the best tier-3 source in the corpus.** It is a one-action game — `available_actions`
is `(6,)` on all 416 rows of the tape, a click carrying x/y — with no undo, so its single death
(row 175, `state: GAME_OVER` on level 6) followed by a working RESET at row 176 is a falsified
prediction with an observed correction and *no* alternative recovery to argue about. It carries
five further resets, at rows 269, 294, 311, 365 and 386, every one of them at
`levels_completed: 7` (the 8th level, per the `level` note at `SCHEMA.md:213`) and every one
preceded by a `NOT_FINISHED` row — plans abandoned as unwinnable, not boards that killed the
player.

#### The reconcile rule, stated with its exceptions

The rule is `rows = 1 + api.actions` (plus any rows recorded past the terminal state) and
`RESET rows = 1 + api.resets`. A previous draft said it "holds exactly on every recording we
hold." **It does not, and the claim is withdrawn.** Measured across all 26 recordings on disk:

- **Holds exactly on 9 of the 11 live-build recordings** — cd82, cn04, dc22, ft09,
  `g50t/4f0689d0`, ka59, lp85, ls20, m0r0. Each ends on a single terminal row, so the
  post-terminal term is zero.
- **Fails on `bp35/c935ca1b`**: 1030 rows against `1 + 1024 = 1025`. The tape ends cleanly on
  one `WIN` row, so this is not trailing junk — the API's `actions` is **5 short of the tape**.
- **Fails on `g50t/58483738`** — a row in the table above: 538 rows against `1 + 536 = 537`,
  again ending on one clean `WIN` row. The API is **1 short**. Its RESET side still reconciles
  (9 rows = 1 + 8).
- **Does not apply to the 15 as66 recordings at all**: they contain **zero** `RESET` rows while
  the API reports up to 9, and four of them are not in the scorecard snapshot. That is a
  different recorder, and it should not be counted as agreement or as disagreement.

#### A rule we were following that nobody wrote down

In `arc-explainer`, three consecutive CHANGELOG entries kept the session `score` off the game
pages, each citing the one before it: 9.74.0 (cd82, 59.9), 9.78.0 (ka59, 84.57) and 9.79.0
(lp85, 76.39). The stated justification in 9.74.0 is that the score "sits on a different scale
from the Human Records card." **It does not** — the leaderboard endpoint feeding that card
returns the same scale, and the ka59 and lp85 entries *say so in writing* while omitting the
score anyway, attributing the omission to "the owner's direction." The Boss's position, as given
to this session, is that no such direction was given; that is his account and cannot be
established from any tree, so it is recorded as his and not as verified.

Two corrections to how this was first written up. **The rule did not suppress two perfect 100s
— both are on the page.** 9.80.0 prints ls20's `score: 100` and 9.81.0 prints m0r0's, each
breaking the precedent on the record and explaining why. **And the backfill is promised, not
landed:** 9.81.0 defers the reconciliation to "9.82.0, immediately below this entry," and
`### Version 9.82.0` does not exist in `arc-explainer/CHANGELOG.md`. That forward reference is
dangling as of this commit. cd82, ka59 and lp85 are still without their scores.

Standing note for future agents, which is the durable part: do not carry an editorial omission
forward as policy because a previous entry did. If an entry says "at the owner's direction,"
verify that before inheriting it.

#### Inventory, from the 18:50 EDT scorecard pull

Scorecards via `arcprize.org/api/user/scorecards` (browser cookie), detail via
`arcprize.org/api/user/scorecards/<card_id>` — that second path is the working one;
`/api/scorecard/<id>` and `/api/scorecards/<id>` both 404. 50 cards, which is a hard cap: `next`
is a page size, not a cursor.

**The threshold matters, so it is stated.** "Real play" below means `levels_completed > 0`.
On that threshold: **25 live-build runs with real play, across 18 of the 25 live games; 11 games
won** (bp35, cd82, cn04, dc22, ft09, g50t, ka59, lp85, ls20, m0r0, r11l); **7 never played on a
live build** (ar25, s5i5, sb26, su15, tr87, tu93, vc33); **7 played but not won** — sk48 reached
level 6, tn36 5, sc25 4, lf52 2, and re86 / sp80 / wa30 one each. Switching the threshold to
`actions > 0` gives 34 runs across 19 games and moves tr87 out of "never played" into "played,
zero levels," which is why the threshold is written down rather than assumed.

Caveat worth carrying: **110 of the Boss's 144 live-build run rows have zero recorded actions** —
sessions opened and batch-published. An earlier draft said 117 of 144; 144 is right, 110 is the
figure the snapshot supports and 117 could not be reproduced from any snapshot on disk. ar25 and
the live vc33 build (`vc33-5430563c`) look played but are empty shells; vc33's 358-action
`GAME_OVER` run is on `vc33-9851e02b`, a superseded build.

#### Still open, carried deliberately rather than quietly closed

- RESET has no citable `action_role_source` in most games — `arcengine` is not vendored, so only
  bp35 and lf52 have citable in-source RESET/ACTION7 implementations. This is what blocked the
  first D pass on lp85.
- The two reconcile exceptions above: the API's `actions` undercounts the tape on
  `bp35/c935ca1b` by 5 and on `g50t/58483738` by 1. Cause unknown; not investigated here.
- Whether to change `solver.py:171`. Not ours to decide.

---

### Schema 0.2: `run_ended`, and the cull is per level not per run

**The gap is closed.** `last_result` gained `run_ended`, so a record can finally say "that action
ended the run". Without it a post-death record read exactly like an ordinary step, which in a
corpus built to teach recovery after being wrong was the one thing it must never fail to say.
Field add, so `schema_version` goes to **0.2**; 0.1 reserved that number for the per-game
`boundary_reason` redesign and the reservation is **released rather than quietly ignored** -
this arrived first, and versions are cheaper than two meanings for one number.

The segmenter measures it: a **flip** to `GAME_OVER`, not the presence of it. The five rows of
the bp35 recording that sit at `GAME_OVER` because the run was already over would otherwise each
be read as a fresh death - five markers on one death. Measured across the committed records, one
carries it: the row where the player has just been killed and is about to try the undo that
fails. Every fixture and record migrated; the version-drift fixture moved to 0.3 so it keeps
failing for the reason it is named for rather than quietly becoming valid.

**The cull, and the Boss's question that forced it.** Asked why we would want human runs that
don't win. Mostly right, and the flag was wrong: `teaches_recovery` marked any falsified
expectation, including the death spiral on the level the player never cleared. Weighting a
training mix towards those teaches flailing.

The unit is the **level**, not the run - the same rule the distiller already applies to its own
play. A stumble on a level that was then cleared is a recovery that demonstrably worked; a
stumble on the level the player died on is flailing. Measured on the eligible material: **only 2
of 100 published runs cleared nothing at all**, and the 48 that never won still hold **229 of the
615 solved levels** - 37% of the material. Culling those runs wholesale would throw away more
than a third of the corpus; culling the unsolved levels inside them throws away exactly the
flailing. `--keep-unsolved` exists and is off.

Tests 112 -> 121. Two more guards poison-checked: the recovery gate, and culling levels rather
than runs.

---

### The bridge: a finished record becomes a training example

`tools/build_sft.py`. Steps 1-4 built a labelling machine whose output nothing downstream read -
the distiller's own SFT builder has never heard of this corpus, so a finished record was a
document, not training data. This closes that, and it was built before more annotation on
purpose: annotating at volume without knowing a record can be trained on is the expensive way to
find out it cannot.

**What it is for.** The distiller rejection-samples the harness's own play and keeps only turns
on **solved** levels, so it structurally discards every moment where a player was wrong and then
fixed it. That moment is the one thing this corpus holds and nothing else in the tree can
produce. Examples carrying it are marked `teaches_recovery` so a training mix can weight them.
That flag is the payload, not a convenience.

**It runs.** All five committed records convert; three carry a falsified expectation and one
carries the full arc - a fatal step, an undo that returns nothing on a dead board, and the reset
that recovers - with the correction **observed in the recording**, not reasoned out by an
annotator.

**Two things are taken from the harness rather than invented, because getting them wrong is
train/serve skew:** the board is rendered by the same function that renders it at serve time, and
actions are emitted in model vocabulary. The system prompt is deliberately **not** - the live one
is bound to the tool loop and is config-dependent, so it is a flag, and every example records
which prompt built it. Running a real fine-tune on the built-in stand-in would be a skewed
fine-tune, and the output says so on every row.

**A defect the tests found, not review.** Annotators write records against the game source, so
the remembered mechanics and the rationale say `ACTION3` - while the model must answer `LEFT` and
has never seen an engine name. The prose reads perfectly well either way, which is why nothing
but an assertion catches it. Engine names are now translated everywhere the model reads, and
`ACTION7`/`RESET` are left alone because those are already the model's own names for them.

`FrameResolver` gained `resolve()` - `check()` said whether a reference was sound but could not
hand back the grid, and the alternative was a second recording reader. Same cache, same path
walk, and it raises rather than returning a board from a row nobody asked for.

Tests 88 -> 112. Three guards poison-checked: prose translation, the unfinished-record refusal,
and taking the settled frame rather than the first.

**Not done:** no new annotation, no recordings pulled, no schema change. One real gap remains and
it is now the binding one - a record cannot say "that action ended the run", which is exactly the
signal the recovery examples exist to teach.

---

## 2026-09-15 (earlier)

### The ka59 and lp85 wins, the undo survey, and a RESET that cannot be cited

Committed direct to `main` at the Boss's instruction. Three pieces of work; the third one
stopped short of its target on purpose and the stop is the interesting part.

**1. Two rows, both re-fetched rather than transcribed.** `ka59-38d34dbb` /
`1333b2ee-…` (WIN, 7 levels, 598 actions, 2 resets, 84.574) and `lp85-305b61c3` /
`129ddf21-…` (WIN, 8 levels, 415 actions, 6 resets, 76.389). Every field was pulled from
`/api/sessions` at ingest and compared against the analysis notes that proposed them; all
agreed. Attribution is a checked `card_id` match against a fresh `/api/user/scorecards` pull —
both cards carry `user_name: "Mark"`. Recordings on disk, gitignored, both reconciling:
`599 = 1 + 598 + 0` with 3 RESET rows, `416 = 1 + 415 + 0` with 7.

`lp85` pins the reconcile rule's third term from the side `g50t` could not. It holds the only
`GAME_OVER` row in any first-party recording (175), and the row after it is a `RESET` that
**executed**, so it counts as an action and the dead-row term stays 0. A rule that counted every
row following a `GAME_OVER` would read 415 as 414.

**Five derived fields were stranded by the row count, not three.** Two are new drift from this
change; three were already stale. `README.md`'s eligibility table read `20 | 25` against a test
asserting `21 | 26`, left behind by the 18:00 `g50t` row. The step-4 plan's §0 table read
`20 | 25 | 16 | 64`, and its `games` and `resets` columns count the *eligible* subset — which
nothing stated, recovered by replaying the definition against the 25-row manifest. This file's
own standing status said 8 recordings on disk when there were 7. Everything is recomputed from
the rows now.

**2. Undo is a per-game design axis, not a platform affordance.**
`docs/trace-findings/2026-09-15-undo-is-not-a-platform-default.md` surveys `ACTION7` across all
25 live builds with a `file:line` for every one. **6 offer it** — `ar25`, `bp35`, `lf52`,
`sb26`, `sk48`, `su15` — and **19 do not**, with zero occurrences of `GameAction.ACTION7` in all
nineteen sources. The Retrodict harness's "prefer undo over RESET" rule is therefore not risky
advice on 19 of 25 games; it is **unimplementable**. This also promotes the earlier `as66`
observation from a quirk of a withdrawn game to the majority case.

Derived twice, because static enumeration under-reports and we can prove it: `cn04` passes no
`available_actions` at all (`cn04.py:824`), `arcengine` is not vendored, and `:1171`'s
`[1,2,3,4,5]` is a filter *over* the offered set rather than the set. Static would have said
five actions; row 0 of its recording says six. The guard that makes the 19 negatives safe is the
whole-file `GameAction.ACTION7` grep, not the declaration. Two decoys are documented so a
word-search does not re-find them: `ls20`'s `_undo_x`/`_undo_y` is the engine rolling NPC movers
back on a blocked move (`ls20.py:1947`, its only call site), and `sc25`'s `_undo_state`
(`sc25.py:1833`) is assigned once and never read.

**3. `lp85`'s loss condition is a step budget — and its RESET steps cannot be labelled.**
`docs/trace-findings/2026-09-15-lp85-step-budget-and-the-uncitable-reset.md`.

The mechanic first, because it is the durable half. `lp85` has no hazard: you lose by running
out of steps on a level (`lp85.py:21416`, counter at `:21282-21284`). The counter **decrements
then tests**, so the step that zeroes it *is* the losing step — there is no state between "one
left" and `GAME_OVER` — and the win test runs first (`:21412`), so a final click that clears the
level still clears it. Column 0 of the frame is a 64-cell bar rendering the consumed
**fraction** of the budget — it advances by `64/StepCounter` cells per **effective** click and
never on a click that hit no button, which is 1 cell per click on levels 2–8 and **5 on level
1**, so cells read as steps only where the budget is 64. A first draft of the write-up claimed
1:1 generally; it was wrong and the correction is in the doc. Confirmed across the recording:
a no-op click does not advance the bar (rows 172 → 173), `63 → 64` at the death, and every one
of the six RESETs refills it to zero consumed. **20 of the 101 clicks on level 6 and 34 of the
157 on level 8 did nothing at all**, and the bar is the only feedback channel that distinguishes
them. This makes `lp85` the second game after `bp35` whose recovery
economics are measured rather than assumed, and the two agree where they overlap: RESET refunds
the whole level budget at no step cost. The undo doc's "not measured" line now points here.

It also reframes the five level-8 resets. At **11, 19, 13, 42 and 16 of 64** steps consumed,
none was under budget pressure — they are plans abandoned as unwinnable, on a game where RESET
is the only way to unwind an arrangement because there is no undo.

**The stop.** `tools/segment.py` cut all seven wanted rows without refusing anything, but six of
the seven are `RESET` steps, and it emits `UNCITABLE: RESET has no dispatch branch in …` for
every one — correctly: `Lp85.step` has exactly one branch, `ACTION6`, and RESET is handled by
`arcengine`, which is not vendored. `schema.json`'s `action_role_source` pattern
`^[^\s:]+:[0-9]+([ \t].*)?$` admits no spelling of "engine-level, source not in this repo", so
`validate.py` rejects all six. **Nothing was overridden and no schema or tool was changed** —
the standing rule is to stop and report. The six records are carried verbatim in the write-up,
because `*.candidate.jsonl` is gitignored and they would otherwise have been lost.

This is not an `lp85` quirk. The one RESET record the corpus already holds validates only
because `bp35` *happens* to carry its own `GameAction.RESET` branch (`bp35.py:4529`). Put beside
the undo survey it composes into a selection effect: on 19 of 25 builds RESET is the sole
recovery primitive, recovery-after-falsification is the metric this corpus exists to move, and
recovery steps can currently only be labelled on builds that happen to vendor a RESET branch.
Four options are listed for whoever owns the call; none is implemented.

**What did land from pass 3:** one record,
`lp85-305b61c3__129ddf21-…__l6-budget-exhaustion.jsonl`, row 175, tier `negative`, passing
`validate.py --require-frame-resolution`. It is the **falsified half of a pair whose corrected
half is blocked** and is not the pair that was asked for.


### A second g50t win, a caveat withdrawn, and the leaderboard that withdrew it

Committed direct to `main` at the Boss's instruction. Three things, one of which is a
correction to this repo's own prose rather than to anything upstream.

**1. The Boss won `g50t-5849a774` a second time** — guid `58483738-cfaf-4e57-8c55-4c9c593bbab5`,
7 levels, 536 actions, 8 resets, score 82.124. Row 26 of `first-party-replays.json`.
Attribution is a checked match, not an inference from the date: the session document's
`card_id` `475182c6-…` was looked up in a fresh `/api/user/scorecards` pull and that card carries
`user_name: "Mark"`. The 70 MB recording stays gitignored, verified with `git check-ignore`
before the commit.

That row made three things visible that nothing had checked:

- **`_provenance.total_actions` had drifted.** It read `5480` against rows summing to `6933` —
  the sum through the `cn04` row. The 15:20 ET refresh that appended `dc22` and `ft09` updated
  `count`, `games` and `state_counts` and left `total_actions` behind. The three that stayed
  correct are exactly the three `ReplayManifestTests` asserted; the one that drifted is the one
  nothing asserted. The file's own doctrine — *"a summary nobody checks is just a comment that
  looks like data"* — was true of the file. Now `7469`, recomputed, with a test.
- **The reconcile rule's third term is not a bp35 quirk.** This recording carries one of its
  own: row 347, an `ACTION2` sent to a board the previous row had already flipped to
  `GAME_OVER`, empty frame list, uncounted by the API. `538 − 1 boot − 1 dead = 536` actions and
  `9 RESET rows − 1 = 8` resets; the rule holds exactly. One recording had the behaviour, so it
  got attributed to that recording's game *and* that recording's action — a second game and a
  second action is the cheapest possible correction of a sample-size-one generalisation.
  `RecordingRowReconcileTests.EXPECTED` is keyed by guid now, since g50t is the first game with
  two recordings on disk.
- **It is the only same-player-same-build pair either manifest holds.** Against the shared
  baseline `[78,175,179,230,96,54,67]`, `level_actions` went `[43,67,68,55,173,62,65]` →
  `[17,31,74,94,186,91,43]`. Levels 1, 2 and 7 improved, 3, 4 and 6 got worse, and the total
  barely moved — 533 → 536 — because the two cancelled. **Levels 5 and 6 are the only ones over
  baseline on either run**, 1.80× then 1.94× and 1.15× then 1.69×, and the API's own
  `level_scores` name the same two: 26.6 and 35.2 against 115 everywhere else. Learning showed
  up as *redistribution*, not net reduction.

**2. A caveat in `published-replays.json` was wrong and is withdrawn.** It said the blog's 250
were *"a curated best-of, not a random sample of human play."* The best-of half was an inference
from the list's shape and nobody had measured it. The blog's own heading was **not** re-read and
is not asserted either way; what is claimed is a comparison.

**3. `datasets/decision-steps/human-leaderboards.json`** is what that comparison is against —
`POST arcprize.org/api/leaderboards/<4-char id>`, **unauthenticated**, pulled for all 25 current
builds plus `as66`. A corrected caveat citing numbers nobody can re-read is not a correction, so
the numbers are committed.

| | leaderboard (250 rows) | blog set (250 rows) |
|---|---|---|
| wins | 250 / 250 | 139 / 250 |
| score | 100 on every row | — |
| resets | non-zero on 24, max 6 | max 30 |
| median actions, on the 10 comparable builds | 29,179 total | 64,425 total — **2.21×** |

Higher on *every one* of the ten, 1.55× to 2.93×. **The consequence cuts the opposite way to
the caveat it replaces: the blog set is not speedrun play.** 111 of its 250 rows are not wins
and its wins take about twice the actions — exploration, wrong turns and recovery, which is
exactly what this corpus wants and exactly what a best-of would have stripped out. It is still
not a *random* sample; nothing measured says how the 250 were chosen, only that it was not for
speed.

**Disjointness is by timestamp, not action count**, because there is no id to match on: every
blog row is `published_at 2026-03-22` and no leaderboard row is. That settles all 25 games at
once. Action ranges do not — `g50t`, `cd82` and `lp85` are disjoint, `bp35`, `ft09` and `sb26`
overlap. The first framing tried was the ranges; it does not generalise, and the file says so.

Three limits are written into the new file rather than left to be rediscovered: a leaderboard
row carries a `user_name` and **no guid**, so those 250 runs are visible and permanently
unfetchable and nothing may try to label or join them; `baseline_total_actions` is a per-**game**
constant, established by the Boss's two g50t runs reporting identical
`level_baseline_actions` while their `level_actions` differed on all seven levels; and
`as66-821a4dcad9c2` returns **zero** rows while all 25 current builds return exactly ten — HTTP
200, well-formed, empty — recorded as observed, with *why* explicitly not guessed at. That last
is now a row in the as66 finding doc as an independent surface that omits the game.

`scripts.test_decision_step_validator`: **52 tests → 59**, all passing. Both new guards
poison-checked — a planted `guid` on a leaderboard row fails with the intended message, an
`as66` `row_count` of 1 fails the zero-rows assertion — and both restored.

---

## 2026-09-15

### bp35 recovery mechanics, measured — and a correction to a labelled record

Committed direct to `main`. The Boss pushed back on this repo's reading of bp35's ACTION7/RESET
behaviour, and on a claim that it conflicted with the Retrodict harness's "prefer undo over RESET,
never two RESETs in a row" heuristic. He was right on every count. Going back to the traces turned
up something better than what was given up. Full write-up:
`docs/trace-findings/2026-09-15-bp35-undo-costs-a-move.md`.

**The find: bp35 has a per-level move budget and undo spends from it.** The move counter increments
on every action *including* ACTION7 (`bp35.py:4528`) and is zeroed only by RESET (`:4533`) and by a
level change (`:4543`). `render_interface` loses the level on exact equality with a level-dependent
budget — 64 for levels 1–6 (`:4413`, `:4421`), 128 for 7–9 (`:4436`), 192 for 10 (`:4404`).
Reconstructed across all 1,030 rows: **no row exceeds its budget**, and the counter reaches it
exactly twice, both `GAME_OVER` — row 806 (`ACTION6`) and row **936 (`ACTION7`), an undo that ended
the level**. So RESET refunds the whole level budget and undo does not, which makes "prefer undo
over RESET" a budget tradeoff rather than free advice.

**The correction: the empty ACTION7 rows are refusals, not undos that returned nothing.** The game
code cannot emit an empty frame list — `bp35.py:1455` always returns at least one grid. The five
rows carry `win_levels: 0` alongside `frame: []`, where all 1,029 other rows carry `win_levels: 9`;
that is an unpopulated envelope, so the action was refused in the engine layer above `bp35.py`. The
distinction is the difference between "retry the undo" and "this action is unavailable in this
state", so the negative record's `outcome.observed` and `action_role_source` were corrected. Its
`rationale` was **not** — it is a correct statement of what the player believed, which is the point
of a rationale.

**The RESET rule, sharpened.** Confirmed against all 302 non-initial RESET rows in the fifteen as66
recordings, zero exceptions: RESET restores the current level's start snapshot, and when the board is
*already* at that snapshot it escalates to a full restart to level 1. Retrodict's "never two RESETs
in a row" catches 2 of the 3 observed restarts and misses the third — a single RESET issued right
after completing a level. The correct guard is *never RESET a board you have not yet changed*.

**Also settled.** The preview set had no undo: January as66 rows carry
`"available_actions": [1, 2, 3, 4, 6]`, and RESET is present throughout as id 0. And bp35's 16
`GAME_OVER` rows decompose as **11 real deaths** (9 in-game, 2 budget) plus **5 refused envelopes** —
an earlier summary said "five", counting only the refusals.

**Not confirmed, and left that way.** RESET as a visible no-op has a source mechanism
(`bp35.py:447`) but **no instance in our six live-build recordings**; every RESET row's settled frame
differs from the one before it. Source explanation is not an observation.

**Guards.** +6 tests (88 → 94), each poison-checked: the budget holds on every row, only rows 806 and
936 reach it, row 936 is an `ACTION7`, the empty-frame rows are exactly the five known refusals and
carry `win_levels: 0`, and every other row carries 9.

**For step 4.** A budget death and an in-game death both land on `boundary_reason: death` today and
call for opposite corrections — "take a different route" versus "take a shorter one". Flagged, not
widened.

---

### `boundary_reason` gets a value for a level transition: `level_advance`

Committed direct to `main`. Passes A and B shipped with the level-transition gap **refused**
rather than papered over: `boundary_reason` had no value for one, so `tools/segment.py` rejected
any `--rows` window that spanned a level change and named the row to split at. That was the
honest move at the time. It was also hiding two wrong answers, not one.

**What the refusal was hiding, measured on the 40 level transitions in the six live-build
recordings on disk** (bp35 9, g50t 7, cd82 6, cn04 6, dc22 6, ft09 6):

| what the segmenter would have said | count |
|---|---|
| `extent_change` — a cn04 word about a held part growing, applied to a whole new level | **25** |
| nothing at all — no boundary, a segment running straight through a level change | **15** |

So the choice was never "refuse or label correctly"; it was "refuse, or ship 25 plausible-looking
lies and 15 silent misses".

**The fix.**

- **`schema.json`** — `level_advance` added to the `boundary_reason` enum. `enum` is already in
  `validate.py`'s supported-keyword audit (`validate.py:49`), so this adds **zero new evaluator
  surface**, the same discipline the turn-0 fix and the dotted `frame_ref.field` followed.
- **`tools/segment.py` rule 6** — a rise in `levels_completed` on a settled row is
  `level_advance`, and it **outranks** the frame-delta heuristics. All 40 transitions now label
  correctly; nothing else on the 1,030-row bp35 recording is labelled `level_advance`, and there
  is a test that walks every row to prove it.
- **A falling level count is still refused.** Unobserved in all 40 transitions, and it should be
  impossible — `RESET` restores a level's opening snapshot, it does not un-complete a level. If
  one appears, the row schema means something other than what the tool reads, and that is worth
  stopping for rather than labelling.

**Stated as a decision, not a measurement:** where `level_advance` sits in the priority order —
below `death`/`reset`/`undo`, above `camera_shift`/`extent_change` — is unfalsified *and*
unexercised. Every one of the 40 transition rows carries `ACTION1`–`ACTION6` with state
`NOT_FINISHED` or `WIN`; never `RESET`, never `ACTION7`, never `GAME_OVER`. A test asserts that
claim so it fails loudly if it ever goes stale.

**`schema_version` stays `0.1`, and the rule is now written down** rather than implied and
quietly relied on. Adding a value to a closed enum does not bump it: no record already written
becomes invalid and `validate.py` rejects an unknown value under either version, so a reader
pinned to `0.1` cannot mis-read a `0.1` record. Adding, removing or retyping a **field** does
bump it. `0.2` is reserved for the per-game `boundary_reason` redesign, which is the real
version-worthy change — spending it on an enum value would leave nothing to call that.
Precedent named, not hidden: commit `73f512415` added `episode_start` and `extent_change` the
same way.

**Tests: 81 → 88.** Eight new, one deleted (the refusal test). Every new guard was
poison-checked the way pass B's nine were — the rule broken, the failure confirmed by its own
message, the file restored. The acceptance gate still holds: the four hand-built bp35 records
reproduce exactly.

**One thing this makes visible rather than causes.** `level` is `levels_completed`, a count, so
the records before a `level_advance` cut read one lower than the records after it. That is
correct and it still reads like an off-by-one. Flagged in `SCHEMA.md`, unchanged here — renaming
the field or switching it to a 1-based index is a field change and *would* bump
`schema_version`.

**Not touched:** `last_result` still cannot say "that action ended the run" — a different open
question, and the plan owner's call.

---

## 2026-09-15 (later still)

### Step 4 passes A and B: per-game dispatch tables, and `tools/segment.py`

PR #19. The premise, measured on the five hand-built records: most of a decision-step record is
**mechanical** — segment boundaries, frame references, the observed outcome, the source
citation. Only three fields need a mind: the rationale, the `expected_observation`, and the
memory delta. So automate the rest and spend the judgment where it counts.

- **`datasets/decision-steps/dispatch/` — 8 per-game tables** mapping action → handler →
  file:line, read once per game and reused by every record in it. Citation stops being the
  bottleneck.
- **`tools/segment.py`** emits candidate records with the judgment fields **absent**. Candidates
  are gitignored, are not collected by a directory walk, and are deliberately not schema-valid,
  so an unfinished record cannot be mistaken for a finished one.
- **Acceptance: the segmenter reproduced the four hand-built bp35 records exactly, first run** —
  cuts, frame refs, measured numbers, level, `last_action`/`last_result`. No disagreement to
  adjudicate.

Four corrections that came out of doing it, worth more than the code:

1. **Line numbers do not transfer between builds of the same game.** `ft09` settles it: two
   builds with byte-identical dispatch code, citation still off by 22 lines from an added
   licence header. Semantics transfer; citations must be re-derived per build.
2. **A branching action must not be cited at one of its branches.** Running the segmenter on
   cn04 found the segmenter citing `ACTION5`'s rotation call — when the entire cn04 finding is
   that ACTION5 rotates some parts and expands others. Citation now stops at the branch and
   lists the sites as `branch-dependent`.
3. **bp35 declares `available_actions = [3,4,6,7]`**, and its move handler reads only the sign
   of `dx` — so ACTION1, ACTION2 and ACTION3 are all a step left, and ACTION5 is literally
   `pass`. The earlier hand-written table implied otherwise.
4. **`arcengine` is not vendored**, so only bp35 and lf52 can cite `ACTION7`/`RESET` to a line.
   Elsewhere those rows are described, not cited — marked uncitable rather than faked.

**Not done:** passes C, D and E. No annotation, no recordings pulled for the selected runs, no
enum widened. `wa30`, `lp85`, `ls20` and `lf52` have source but **no recording on disk**, so
their tables are unchecked against play. The `camera_shift` / `extent_change` heuristics are the
weakest output and need pass D to confirm. `args` mapping `row=y, col=x` is an **unverified
assumption**, flagged in the docstring and covered by no test.

**81 tests pass**, up from 46. Nine guards were poison-checked — each made to fail, confirmed by
its message, then restored.

---

## 2026-09-15 (later)

### Eligibility settled: only runs on a **current build** count

Boss directive. ARC Prize rebuilt these games as the benchmark firmed up, so an early replay is
a replay of a *different game* — ls20 in the preview is not the ls20 that ships now. Encoded as
**build-currency** rather than a date cutoff, because build id is the precise, checkable form of
that reasoning: date is the symptom, the build hash is the test.

- `datasets/decision-steps/current-builds.json` — dated snapshot of the 25 live builds, read
  **offline** by `CurrentBuildTests`; the tests never call the API.
- **The source-coverage constraint is gone.** All 25 current builds have a directory under
  `docs/static/games/src/`. The earlier "16 of 36 builds have no source" figure was counting
  *stale* builds, which this rule excludes anyway. `action_role_source` is no longer a limit on
  what can be labelled.
- **Eligible material:** 100 of the blog's 250 (the other 150 sit on 15 builds that have since
  been replaced) and 20 of the Boss's 25. Neither manifest is filtered — each is a record of
  what it claims to be, and filtering would make its own provenance false — so eligibility is
  applied at selection time and the counts are asserted by a test.
- **as66 leaves corpus scope.** Not in the live lineup, so none of its 15 recordings are corpus
  input. The finding stands on its own and the recordings stay on disk.
- **One judgement call, reversible in a line:** build-currency keeps 100 March rows whose builds
  never changed. If the intent was strictly "September only", drop those and the eligible set is
  the Boss's 20 runs alone.
- **Reservation:** build id is the only version signal the API exposes; that it changes when and
  only when the game changes is **assumed, not verified**. Re-snapshot after any lineup change.

Also: episode globs now exclude `*.candidate.jsonl`, matching what `validate.py` already did.
Segmenter candidates carry no judgment fields and are deliberately not schema-valid, so an
unfinished record can never be mistaken for a finished one. 46 tests pass; the new build guard
was poison-checked.

---

## 2026-09-15

### as66 — an environment that is not in the live lineup, and 15 runs that still serve

`docs/trace-findings/2026-09-15-as66-the-withdrawn-26th-game.md`.

`as66-821a4dcad9c2` is absent from the authenticated `/api/games` list (25 games, none of them
as66) and absent from the blog's 250 published replays — but `/api/sessions` and
`/api/recordings` still return `200` for it. **15 runs pulled: 2 human, 13 agent, all 7–15
January 2026, 28 MB.** Why it is absent was *not* established and is not claimed.

Two findings worth a reviewer's time:

- **It is the only environment where we hold human and agent play on the same game.** The
  human reached level 6 of 9 using 9 resets; **11 of 13 agent runs never passed level 1**. Two
  agent runs are almost entirely RESET — `4a218928` is 98 RESETs in 101 actions, `75928ec9` is
  195 in 103. as66 offers **no ACTION7**, so reset is the only recovery verb, and the agent
  used it as its whole strategy.
- **The January recordings are an older row schema** and the reconcile rule below does **not**
  hold on any of them: integer `action_input.id` instead of strings, `score` instead of
  `levels_completed`, no `full_reset` boot marker, and a trailing all-null row. Candidate
  rules were tested; none covers all fifteen. **Recorded as unresolved.** Any segmenter must
  branch on schema version.

Blocked for the corpus by the same constraint as 143 other runs: no source in
`docs/static/games/src/`, and no sibling build to fall back on. If that source can be
obtained, this becomes the most valuable environment in the set.

### Refreshed the first-party replay manifest — 2 new wins, `dc22` becomes citable (#18)

Re-pulled the Boss's scorecards four hours after the first snapshot. Two wins played in
between: `dc22-fdcac232` (6 levels, 1320 actions, 8 resets) and `ft09-0d8bbf25` (6 levels, 133
actions, 4 resets, score 100, under baseline on every level). Manifest is now **25 rows, 20
builds, 8 WIN / 6 GAME_OVER / 11 NOT_FINISHED**, still disjoint from the published 250.

- **`dc22` level 5 is the densest exploration seam we hold** — 740 actions against a 324
  baseline, after being *under* baseline on the four levels before it.
- **`dc22` changes what is citable.** The blog's 250 carry `dc22-4c9bff3e`, which has no source
  directory; this build has one. A game that could not meet acceptance now can, because it was
  played on a current build. `ft09` is the opposite and equally useful: same build as the
  blog's ten ft09 rows, so the two are directly comparable.
- **Pagination settled.** `arcprize.org/api/user/scorecards` returns 50 items and its `next`
  field is a page size, not a cursor — `?at=50` returns the identical 50 `card_id`s. The
  50-card cap is real and the file remains a floor. All 50 resolved with zero failures, which
  **supersedes an earlier 429 report that could not be verified from the artefacts**. Per-card
  runs come from `GET /api/user/scorecards/<card_id>`; `/api/scorecard/<id>` is 401 and
  `/api/user/replays` is 404.

### Step 4 execution plan (#17)

`docs/plans/2026-09-15-step4-segment-and-label-execution.md`. The source-coverage constraint
(130 of 273 runs eligible), reset count as the selection rule (683 resets across those runs,
six games carrying 561), and five passes: segmenter → dispatch tables → pull → annotate →
**adversarial falsifiability gate**.

Two commitments made up front: pass E **deletes** records rather than softening them and
reports the cut count, and `memory_in` may never contain game-source knowledge — the source is
for `action_role_source` only, or the record teaches clairvoyance.

### Step 4 opens: `boundary_reason` widened, row counts reconciled, first real records (#16)

- **`boundary_reason` gained `episode_start` and `extent_change`.** The six original values all
  name a state *change*, so none could say "the episode opens here"; and cn04 has an event none
  covered — `ACTION5` dispatches on the selected part, stepping it through its sprite stack at
  `cn04.py:1070` when it has more than one entry and only rotating at `:1072` when it does not.
  `SCHEMA.md` gained a **Boundary reasons** section and states the real limit: per-game values
  do not scale to 25 games. Flagged, not redesigned.
- **`boundary_reason` is a property of the segment, not the record.** Decided here, because the
  field name admits either reading; every record sharing a `segment.id` must carry the same
  value, and a test enforces it.
- **Session `actions` versus recording rows — reconciled exactly, on every recording:**

  ```
  recording rows = 1 + session.actions + rows submitted while the board was already GAME_OVER
  RESET rows     = 1 + session.resets
  ```

  The leading `1` is row 0, which carries `full_reset: true` and the API counts as neither. The
  third term is non-zero only on bp35, where it is **5** — rows 215, 370, 390, 572, 807 each
  submit `ACTION7` to a board the preceding row already flipped to `GAME_OVER`, returning
  `data.frame: []`. The README previously said there was "no clean rule"; there is, and
  `RecordingRowReconcileTests` asserts it. **A record must never point `frame_ref` at one of
  those five rows** — the frame list is empty and the resolver rejects it.
- **First labelled records**, in `datasets/decision-steps/v0/episodes/`, validated with frame
  resolution *required*. The bp35 episode is the **tier-3 shape taken from human play**: a step
  that kills the run, `ACTION7` failing on the dead board, and the `RESET` that recovers — the
  corrected decision is *observed*, not invented. `ACTION7` is the one dispatch branch that
  does not first push an undo snapshot (`bp35.py:4524` against `:4496 :4501 :4506 :4511 :4516
  :4521`); `RESET` restores the level-start snapshot (`:4529` → `:447`). That triple occurs
  five times in one recording.

### cn04 `ACTION5` has two meanings, and levels 1–4 teach the wrong one (#15)

`docs/trace-findings/2026-09-15-cn04-object-dependent-verb.md`. Measured: all 12 `ACTION5`
presses on level indices 0–2 conserved the painted-cell count exactly; from level index 3 on,
39 of 65 did not. A re-verification pass on 12-Sep had deleted this observation as fabricated;
it was not, and the correction is in the study docs.

### Earlier the same day

- **#14** — the Boss's cn04 win added to the first-party manifest, the run that found the
  level-5 rule inversion.
- **#13** — first-party manifest corrected to 22 rows, all attributed to the Boss. **#12 was
  merged into an already-merged branch and its content never reached `main`**; #13 re-targeted
  it. Check `git merge-base --is-ancestor` before trusting a green merge badge.
- **#11** — `tools/replay_scrape.py`, the dotted `frame_ref.field` path, and
  `published-replays.json`: **250 blog-linked human replay guids**, 139 WIN across 25 games.
  `data.frame` is a *list* of grids and the settled board is `frame[-1]`, cited to
  `taaf/game.py:175` and `kd01.py:515`.
- **#10** — the JSON schema, `validate.py`, and the fixture corpus. `row_index` is **zero-based**,
  settled against a real recording. Turn-0 records are expressible: `last_action` and
  `last_result` are required and explicitly nullable, both-or-neither.
- **#9** — ACTION7 round-trip landed, unblocking recovery behaviour in both traces and labels.
