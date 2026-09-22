<!--
Author: Claude Fable 5.1, for Son Pham
Date: 22-September-2026
PURPOSE: Plan for using DeepSeek-V4.1-Flash as a teacher in three graded roles (explorer, judge,
author) to break the zero-variance problem that stalls on-policy RL on ARC-3, with Flash-Next as
the student. Pre-registers the arms, the reward terms, the audit that can kill the judge, the
measurement, and the decision rule, before anything is built. Records which arms reopen Son's
15-Sep no-teacher call and which do not.
SRP/DRY check: Pass. The no-teacher call and the reward-variance argument are cited to
finetune-readiness §9, not restated. The human-recording format and its alignment proof are
cited to distill/recordings_to_sft.py. The decision-step falsifiability rule is cited to
datasets/decision-steps/SCHEMA.md. Flash-Next sizing and the requant risk are in
memory/flash-next-is-the-kaggle-model.md and summarised once here. The ceiling run is
plans/2026-09-21-deepseek-v41-flash-ceiling-run.md and is a gate, not a section.
-->

# Teacher-student RL arms: DeepSeek as explorer, judge, author — in that order

**Status:** plan, 22-Sep-2026. Nothing built, nothing trained. Gate G0 (the ceiling run) is in
flight in another session and is not owned here.
**Call reopened:** Son, 22-Sep-2026, in this session: "Yes, I reopen 15-Sep call." Teacher text may
be trained on, under §5's conditions. Arm C is therefore stage 1 (cold start), Arm A stage 2 on top.
**Requested by:** Son, 22-Sep-2026 ("Is it possible to use DeepSeek Flash v4.1 like a teacher
model? … the issue is the quality of training data … if no levels are completed then there is
no signal").

## 0. The call this touches

Son's 15-Sep call: no teacher, RL is on-policy, bootstrap only from the student's own wins
(`trace-findings/2026-09-15-qwen27b-finetune-readiness.md` §9). On 22-Sep Son reopened it
("Yes, I reopen 15-Sep call"). The grading below is kept because it still says what each arm
costs in on-policy purity; it no longer gates Arm C.

| arm | teacher supplies | text trained on | reopens the call? |
|---|---|---|---|
| **A** explorer | start states (action prefixes), nothing else | student's own | no |
| **B** judge | a within-group ranking used as a shaping reward | student's own | softly: teacher shapes reward, writes nothing |
| **C** author | level-clearing play segments, rejection-sampled | teacher's | yes, fully; **authorised 22-Sep** |

## 1. The problem, stated as arithmetic

Group-relative RL (GRPO and kin) updates on the standardised advantage *within* a group of
continuations from one start state. If all N continuations get the same reward, the advantage
is zero and the group contributes nothing (readiness §9, "Reward variance"). On the hard seven,
the student clears nothing from the level start, so **every** group is flat: spend without
gradient. Slow rollouts (Son, 22-Sep) make this worse but are not the cause; fast rollouts of
nothing are still nothing.

A teacher can therefore help in exactly three ways, and the arms map onto them:

1. **Put the student where signal exists** (A). From three steps before a clear, some
   continuations clear and some do not; the group has variance.
2. **Make the reward denser** (A2, B). A per-step verifiable term gives variance even when
   nobody clears; a judge's ranking gives variance when the outcome is flat.
3. **Move the student off the floor with data** (C). Only if 1 and 2 are not enough.

## 2. Student

**Flash-Next** (`Qwen3.8-Flash-Next`, 125B / 6B active + 51B PLE + 4B MTP), because it is the
model that scores on Kaggle; the 27B was the student so far only because it fit a GB10. Facts
that bound the plan (memory `flash-next-is-the-kaggle-model`):

- The repo's LoRA pipeline (`ARC3-Inference/distill/train_lora.py`, rounds 1–3) is 27B-only.
  A Flash-Next path is new work: BF16 base (~360 GB) sharded over 8× RTX PRO 6000, LoRA on
  attention + shared expert, routed experts / PLE / MTP frozen.
- Serving is NVFP4 (`RadixArk/…-NVFP4`, 135 GB). **G1a, 22-Sep, settled without a GPU:** ModelOpt's
  `ignore` list leaves `*.self_attn.*`, `*.linear_attn.*`, `*.mlp.shared_expert*`, `*hyper_connection*`,
  `*.ple.*`, embeddings and `lm_head` unquantized, and ranged byte-compares of
  `layers.3.self_attn.q_proj` (BF16 [12288, 2560]), `o_proj`, `shared_expert.down_proj` and
  `layers.4.linear_attn.in_proj_qkv` show them **byte-identical** to the official
  `Qwen/Qwen3.8-Flash-Next` BF16 release. So a LoRA on attention + shared expert merges into BF16
  tensors that already live inside the served checkpoint: **no requantization, no `--enable-lora`
  dependency, the serving stack (pinned image, PLE patch, overlays) unchanged.** Only the 512 routed
  experts are NVFP4, and they are frozen. The requant risk in the earlier draft applied only to a
  merge that touched experts; it no longer applies. Evals stay on the served form regardless.
- Architecture facts that fix the LoRA targets (`config.json`, `qwen4_exp`): hidden 2560, 48 layers,
  **12 full-attention layers** (every 4th: 3, 7, …, 47; q/k/v/o, 24 heads × 256, 2 KV heads) and 36
  Gated-DeltaNet `linear_attn` layers (in_proj_qkv/z/a/b, out_proj); shared expert 640 wide;
  routed MoE 512 × 640, top-10. Targets: `self_attn.{q,k,v,o}_proj`, `linear_attn.{in_proj_*,out_proj}`,
  `mlp.shared_expert.{gate,up,down}_proj`. Frozen: routed experts, PLE, MTP, vision, hyper-connections.
- Until G2 (§7) passes, the **27B remains the proving ground** for the extractor, the reward and
  the audit; those three are model-agnostic.

## 3. Arm A — explorer: reverse curriculum + verifiable prediction reward + throughput

### A0. When the teacher steps in: a trigger that needs no human score

Son asked (22-Sep) for a universal rule, since human scores exist for only some games. None are
needed:

- **Ceiling:** the engine reports `win_levels` next to `levels_completed` on every state (see the
  recording row format in `distill/recordings_to_sft.py`), and `WIN` when the game is done. "Has
  the student reached max on this game" is `levels_completed == win_levels`.
- **Stuck:** the zero-variance statistic GRPO already computes. Per `(game, level)` below
  `win_levels`, if the student's clear rate from the level start is 0 over **M = 20 consecutive
  groups** (160 rollouts at horizon H) and the prediction reward is not separating branches
  either, that level is stuck and a teacher prefix is requested.
- **Unteachable for now:** if the teacher cannot clear that level either, it is flagged and stays
  on the prediction-reward-only path; nothing is invented for it.
- **Human scores** are used only to order spend: levels humans clear easily are tried first,
  because there the gap is most likely the student's rather than the game's.

The trigger is re-evaluated after every curriculum advance, so a level unlocked at k = 1 is
re-checked from the level start before the teacher is asked again.

### A1. Start states from demonstrations, teacher's and human

The ARC-3 engine is deterministic under action replay: across all 18 human recordings, every
non-full reset row carries the byte-identical level start board
(`distill/recordings_to_sft.py`, "OBSERVATION ALIGNMENT"). So a start state is just a game plus
an action prefix, and the extractor is small:

```
for each (game, recording, clear_row) in demos:
    for k in K_SCHEDULE:
        prefix = action_input rows [.. clear_row - k]
        g = taaf.game.Game(ArcadeSpec(environments_dir), game)      # fresh env
        replay prefix via arcengine.ActionInput; assert board == recording row board   # alignment check
        emit {game_id, guid, row_index: clear_row-k, k, level, prefix, board_sha}
```

Two demo sources, same manifest format:

- **The Boss's recordings**: 130 records / 3,190 turns; 89 records / 2,281 turns behind the
  held-out fence (`trace-findings/2026-09-18-human-demos-to-sft.md`). Already on disk on the Mac;
  not in this checkout. Zero GPU cost. **This is the arm's first data and it needs no teacher.**
- **DeepSeek live play**: the ceiling run's traces, kept only where it cleared a level. Adds
  coverage on games the Boss did not play. Its *text* is discarded here; only the action
  sequence is used.

`K_SCHEDULE = [1, 2, 4, 8, 16, 32]`. Train at k until the clear rate from k exceeds 50 %, then
advance. This is a reverse curriculum (Florensa-style); the student is never shown the teacher's
reasoning, only placed nearer the goal.

**Held-out fence** applies unchanged: no start state from a held-out game enters training.

### A2. A verifiable per-step reward the engine already gives

Every decision record demands an `expected_observation` "that the next frame either confirms or
refutes" (`datasets/decision-steps/SCHEMA.md`, "The unit"). At serve time the student emits a
`world_model` ledger; add a structured expectation field and score it against the real next
frame:

| claim form | checked by | reward |
|---|---|---|
| `board_changed: true/false` | frame diff | +1 correct / −1 wrong |
| `level_changed: true/false` | `levels_completed` delta | +1 / −1 |
| `cells: [{r, c, color}]` (≤ 8 cells) | exact lookup on the next settled board | fraction correct |
| unparseable / absent | — | 0, and the turn is logged |

Per-step reward `r_pred ∈ [−2, 3]`, scaled to `λ_pred = 0.1` against a level clear of 10. It
does not teach *what to do*; it teaches *knowing what the buttons do*, which is the hard seven's
failure mode (lf52: the same wrong world model on four passes). It gives variance in every group,
teacher or not. Reward hacking is bounded: claims are cheap to make but only correct claims pay,
and "no claim" pays nothing.

### A3. Throughput: rollouts and training on separate boxes

Flash-Next NVFP4 is 135 GB: **two RTX PRO 6000 per replica**. A `g4-standard-384` serves four
replicas at 40+ lanes each; per-lane latency is irrelevant for rollouts, aggregate tok/s is what
counts, and the KV headroom measured on the DeepSeek box (14 M-token pool) shows how far lanes can
go on this card. Training (BF16 LoRA, ~360 GB base) needs a second 8-GPU box. Neither shares a
box with the other.

Rollout protocol: for each start state in the current k-bucket, N = 8 continuations, horizon
H = 3k + 8 steps, reward = 10·(level cleared within H) + λ_pred·Σ r_pred. Groups with zero reward
spread are skipped (readiness §9's own rule), and the skip rate is the curriculum's health metric.

## 4. Arm B — judge: DeepSeek ranks the branches the engine cannot separate

Arm A plus one shaping term. When a group's outcome reward is flat, DeepSeek-V4.1-Flash sees the
start frame, the N continuations (actions and frames, **not** the student's reasoning), and
ranks them by "which made progress toward something the frames show". The ranking becomes a
Bradley-Terry score per branch, standardised within the group, weighted `λ_judge = 0.2`.

**The audit that can kill it, run before it is used:** take 300 groups whose outcome *is* known
within H (from Arm A rollouts at small k). Hide the outcome, get the judge's ranking, compute
Kendall τ between the judge's rank and the outcome rank. Adopt only if τ ≥ 0.3 with 95 % CI above
0. Re-run the audit every 2,000 groups; if τ falls below 0.2, the term is dropped and the run
continues as Arm A. Without this, an LLM judge is a reward the policy learns to please.

Cost: one DeepSeek forward per branch on frames only; at 16B active decode this is cheap on the
8-GPU box and needs no training text from the teacher.

## 5. Arm C — author: distil level-clearing segments (stage 1, the cold start)

Authorised 22-Sep. Why it comes first: reasoning is the product (the ledger is what the harness
serves), and RL can only select among reasoning the base already produces; where the base has
none, SFT on strong live traces installs the form in a few hundred steps (the R1-style cold
start). Why it cannot be last: SFT is imitation, and a 6B-active student imitating a 552B
teacher will produce confident ledgers it cannot back. Arm A on top, with the prediction reward,
is what punishes confident-and-wrong. Conditions:

1. DeepSeek plays **live** (the ceiling harness), never annotates in hindsight. This is what
   keeps the hindsight leak out (`plans/2026-09-19-reasoning-backfill-pilot.md` §2).
2. Keep only segments that end in a level clear (rejection sampling on outcome). A strong model's
   confident wrong world models are the student's worst existing habit and must not be taught.
3. Re-render through Flash-Next's tokenizer and chat template; recount tokens; window to the
   serve-time history depth exactly as `recordings_to_sft.py` does for human demos.
4. SFT, then Arm A on top. The SFT is a bootstrap, not the result.

Gate: the ceiling run (G0) must show DeepSeek clearing levels on the games that matter. Levels
DeepSeek cannot clear have no traces and stay on the pure on-policy path (§3, A2 as the only dense
signal). **Imitation check before A starts:** the SFT-only model, on its served form, must be no
worse than base on held-out live play; if it is, the cold start taught form without capacity and
A is not run on top of it until the data is re-filtered.

## 6. Measurement and decision rule, fixed now

**Primary:** levels cleared in live play under the frozen harness clock (2,061 s per game,
7 lanes), on (a) the hard seven and (b) the held-out games, two runs per arm, scored paired
per game against the arm's own control (the same student, same harness, no adapter).
**Secondary:** held-out paired loss via `distill/eval_lora.py`, **on the served form** of the
model (adapter-on-NVFP4 or requantized merge).

| decision | rule |
|---|---|
| Arm A adopted | hard-seven clears ≥ control + 2 over the two runs, and held-out loss not worse |
| Arm B's judge term kept | audit τ ≥ 0.3 at start and ≥ 0.2 on every re-audit, and Arm B ≥ Arm A + 1 clear |
| Arm C data exists for a level | G0 (or a later teacher run) shows DeepSeek clearing that level |
| Arm A starts on top of C | SFT-only model, served form, not worse than base on held-out live play |
| Curriculum healthy | zero-spread group skip rate < 50 % at the current k |

Seed variance on this benchmark is 3.33–6.67 % from seeds alone (`docs/how-this-feeds-kaggle.md`);
a one-level difference on one run is noise and is not read.

## 7. Order of work, with gates

| gate | what | needs GPU | owner |
|---|---|---|---|
| G0 | ceiling run result: does DeepSeek clear what the 27B cannot | 8× RTX (in flight) | other session |
| G1 | ~~`--enable-lora` check~~ **Done 22-Sep (G1a, no GPU):** LoRA targets are BF16 and byte-identical between served NVFP4 and official BF16 → merge in place, no requant. `--enable-lora` (G1b) is optional, only if unmerged adapters are ever wanted | none | done |
| G2 | Flash-Next BF16 LoRA smoke: one step on one record, adapter loads, eval runs on served form | 8× RTX | this session |
| G3 | start-state extractor + prediction-reward validator on the Boss's recordings, on the 27B, no training | none (CPU + engine) | this session |
| G4 | Arm C cold start: outcome-filtered teacher segments → re-render → LoRA SFT → imitation check on served form | 8× RTX (teacher play is G0's output) | this session |
| G5 | Arm A on top: reverse curriculum from the same teacher prefixes, GRPO with engine + prediction reward (27B plumbing proof first) | 8× + 8× RTX | this session |
| G6 | judge audit (300 groups, τ), then Arm B; judge also grades rationale support/correctness | + 8× RTX for DeepSeek | this session |

G3 is the next concrete thing to build and it is GPU-free: the extractor, the replay-alignment
check, the reward parser, and their tests against the recordings. G2 (the Flash-Next LoRA smoke on
8 GPUs) now has a known merge path: train on the official BF16 base, add ΔW to the identical
tensors in the RadixArk checkpoint, re-run its own `validate_checkpoint_report` on the result.

## 8. What this plan does not do

- It does not touch the ceiling run or its scripts; that work is owned elsewhere.
- It does not budget a second 8-GPU Spot box while one is running in the same region:
  `PREEMPTIBLE_NVIDIA_RTX_PRO_6000_GPUS` is 8 per region (memory `deepseek-v41-flash-on-rtx-pro-6000`).
- It does not propose 27B GRPO on a GB10; that was ruled out
  (`trace-findings/2026-09-16-a108-training-stack.md` §7) and the fleet changes the arithmetic
  only for Flash-Next-sized serving plus a separate training box.
- It trains on teacher text only as §5 specifies: live play, outcome-filtered, held-out games excluded, imitation-checked before RL.
