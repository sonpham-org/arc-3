<!--
Author: Claude Opus 5.5, for Son Pham
Date: 1-October-2026
PURPOSE: The RL plan Son asked for on 1-Oct ("time we finally go at the heart of this"): train Flash-Next on
the games where it is weak but sometimes brilliant. Answers his six questions (which brain, LoRA or full,
teacher or not, how many and how long the rollouts, how to store a growing tree of traces, what humans do),
gives the target levels measured from 83 finished runs, the loop, the build list, the gates, the cost, and the
decisions that are his. G0 code (target map, tree store, reward, fork seeding, record builder) is built with
this plan; nothing has been trained.
SRP/DRY check: Pass. The LoRA-target and no-requant facts for the RadixArk NVFP4 checkpoint are
plans/2026-09-22-teacher-student-rl-arms.md §2 (G1a); this plan adds the same check for Daniel's Intel W4A16.
The test-5 / train-11 split and the served-form checks are plans/2026-09-29-flash-next-lora-teacher-poc.md
§3 and §6, cited, not restated. Fork mechanics are gcp/controllers/live-injection/ and branch-replay/.
The prune -> repair -> capture -> draft runbook is gcp/controllers/sglang-scored/lobotomy/README.md.
-->

# RL on the burst games: plan (1-Oct-2026)

**Status:** plan + G0 built and run (results in §9a). Nothing trained, no training box booked.
**Asked for by:** Son, 1-Oct: RL on games where the harness is weak but shows occasional bursts of brilliance;
later, more hand-made games.

## 0. The short answers

1. **Which brain?** One adapter, trained through the **full** Flash-Next (all 512 experts), sitting in the
   parts that every brain shares. Attention, linear attention and the shared expert are the same BF16 bytes in the
   official model, in our pruned NVFP4 Frankenstein, and in Daniel's Intel 4-bit model (checked today, §3). So the
   adapter drops into any of them with no re-quantizing. The Frankenstein parts (expert cut, repair net, draft)
   are speed parts: they get re-fitted after the adapter, as the runbook already does.
2. **LoRA or full?** LoRA on those shared parts. Full fine-tuning buys nothing for RL and costs a 64-GPU cluster
   plus re-quantizing the experts, which would round most of a small RL update away (§3, table).
3. **Teacher?** Not for the burst games: the game is the teacher, and the model's own rare wins are the signal.
   Gemini 3.8 Flash only at dead ends (all 8 tries fail): it is shown a winning path for that level (a burst run or
   ARC's human replay) plus the failed tries, and writes a few general rules as a hint; the game decides which hinted
   tries win. Two ways to train on them get tested (hint kept in the prompt vs removed), §0c. Teacher-written
   thoughts are not trained (they hurt thinking models). Opus as a live reviewer was blocked by an API safeguard on 2
   of 5 reviews on 30-Sep. Gemini 4 Argon is gated (§0c). Terms risk on training with Gemini output: §0c item 8.
4. **Rollouts?** The unit is **one level from a saved moment**, not a whole game. 8 tries per moment up front (16
   when all 8 agree on a moment that has been won before), until the level clears or ~40 turns / 1.5x the
   reference's remaining actions and tokens. About 200 moments per round: ~40M tokens, ~17 GPU-h, ~2 h on 8 one-GPU
   VMs. One round per day to start (§5).
5. **Tree?** Yes. Firestore holds the index (moments, tries, groups, rounds; small documents, live writes from the
   VMs, the same database as the run scores), GCS holds the payloads (exact requests and replies). Every saved
   moment is replayable exactly, because the engine is deterministic (§6).
6. **Humans?** Four jobs, most valuable first: make games (the curriculum is the hand-made and evolved games;
   the public 25 are the tutorial); demos for levels nobody has cleared; a 10-minute check per round that the
   top-rewarded wins are understanding, not luck; one-line hints at dead ends, like Gemini's (§7).

This is the order you asked for on 29-Sep: keep the winners and fine-tune on them (expert iteration) first; RL
with negatives (GRPO) only if that plateaus.

## 0b. How we RL forward, step by step (revised after the 1-Oct research pass, §0c)

Each step has one question it answers and a stop rule. Teacher = Gemini 3.8 Flash (Son, 1-Oct: "it is fine"),
subject to the terms question in §0c.

| step | what | answers | cost | stop if |
|---|---|---|---|---|
| **1. Pipe test** (round 0) | Train the LoRA on the 4,635 winning turns already logged (train games, easy six out), merge into Daniel's 4-bit model, serve it in his notebook, 2 R16 runs vs 2 control | does training Flash-Next help or hurt at all, and does train -> merge -> serve -> score work end to end | one 8-GPU box ~1 day + ~10 GPU-h of runs | it hurts the test five: inspect before going on (the 27B fine-tunes hurt) |
| **2. Try runner** (in parallel with 1) | Port the fork runner to Daniel's harness (his W4A16 server: 4-bit weights, 16-bit activations, the stable kind for RL), replaying from his request logs. 50 frontier moments x **8 tries up front** | how many groups are mixed, clear rate per level, tokens per try | ~5 GPU-h | fewer than ~30% of groups mixed: move moments later in the level |
| **3. Teacher test, no training** (alongside 2) | ~30 dead moments: (a) 8 tries with a Gemini hint (Gemini sees a winning path for that level: a burst run or ARC's human replay); (c) the student starting 5 / 10 / 20 moves before the goal on that path; (d) Gemini scoring existing groups blind (does it rank wins above losses?) | which teacher route opens dead levels at all | ~5 GPU-h + a few dollars of Gemini | none of them moves the dead moments: walls stay out of scope for now |
| **4. Expert-iteration rounds 1-2** (short) | ~200 moments a round x 8 tries (16 when the first 8 all agree on a moment that has been won before); keep the best try of each mixed group; fine-tune; merge; redeploy | do burst levels become reliable (train-side clear rate from moments, every round) | per round ~17 GPU-h of tries (~2 h on 8 VMs) + 2-8 h of the box | a round lowers the train-side clear rate: roll it back |
| **5. Held-out screen** | test five, 2 runs per arm, then 4 more for the best | did habits transfer to games we never trained on | ~10-20 GPU-h | train up, test flat = memorized: more games, not more rounds |
| **6. RL with negatives** | Switch when expert iteration stalls or the model's answers get samey (a known failure of winners-only training): GRPO from the same groups, KL anchor, per-turn values from the tree (the clear rate before and after each turn), routing replay, rollouts on the same weights being trained | can pushing down the losing habit add more | same as 4 | unstable: back to expert iteration |
| **7. More games** | Community + hand-made games, frontier measured from two plays each, same loop | does variety lift the hidden set | grows with the game count | - |

Rough total for steps 1-5: ~250-400 GPU-h over about a week.

## 0c. What the 1-Oct research pass changed (four short reports, sources in each line)

1. **Fork 8 up front, not 4 then 4.** With a 20% moment, all of the first 4 fail 41% of the time (0.8^4), so the
   "4 then 4" rule throws away exactly the hard moments; 8 tries make a mixed group 83% likely. Group size matters a
   lot in a 2026 agent-RL ablation (CANOPY, arXiv 2609.01245: 8 vs 32 tries per task cost 16 points; also: keep a KL
   anchor, stay on-policy, average the loss per sequence). Weight moments by p(1-p) instead of a hard 20-80% cut
   (LILO, arXiv 2502.12272).
2. **Keep expert iteration short.** Winners-only training learns fastest early, then the model's answers get samey and
   RL with negatives overtakes it (arXiv 2504.11343); positives-only narrows pass@k, negatives keep it (arXiv
   2506.01347). Expert iteration with a growing horizon still reached 64.8% on WebVoyager (TTI, arXiv 2506.07976).
3. **The tree gives per-turn credit for free.** Fork clear rates are Monte Carlo values (VinePPO, arXiv 2410.01679):
   a turn's advantage = value after it minus value before it. Steps that reach the same board across forks can be
   compared as their own group (GiGPO, arXiv 2505.10978: +12% ALFWorld, +9% WebShop over GRPO). No critic needed.
4. **Teacher design: hints yes, teacher-written thoughts no.** Distilling a thinking model from a hinted copy cost up to
   17% and cut its checking and backtracking (arXiv 2607.05184), so design (b) (the 30-Sep live-injection rewrite
   trained into weights) is dropped. Hints work when the hint writer SEES THE ANSWER, not because it is stronger
   (NuRL arXiv 2509.25666; PSP arXiv 2609.29051): give Gemini a winning path for the level plus the failed tries,
   ask for 3-6 general rules. Two arms to test: hint kept in the prompt during training (PSP: AppWorld 9.4 vs GRPO 4.6,
   and its "hint removed" variant scored 2.0 and acted as if it had seen the hint) vs hint removed with an importance
   correction and no ratio clipping (Guide, arXiv 2506.13923: small gains; clipping diverged; hinting every problem hurt).
   Our default "remove the hint" is the weaker of the two in the closest (agent) evidence.
5. **Roll out on W4A16, not NVFP4, once we use ratios.** NVFP4 rollouts against a BF16 trainer collapsed after ~150
   steps in QUADS (arXiv 2607.15810; activation quantization); weight-only 4-bit stayed stable. Daniel's AutoRound
   W4A16 is weight-only. Expert iteration needs no ratios, so step 4 is unaffected.
6. **Trainer:** RadixArk's Miles (their slime fork) is the only framework found with Flash-Next RL + LoRA + routing
   replay + SGLang alignment (trainer-vs-SGLang log-prob gap 0.008-0.013 with routing replay), tested on GB300s; NVIDIA's
   paths are validated at 4k context only. Plan: our HF+peft trainer for expert iteration (no ratios needed; G1 measures
   its speed at ~100k context); Miles' trainer for the GRPO step, after a one-box smoke test on RTX PRO 6000. Known limit:
   LoRA should cover the MLP side; ours covers the shared expert only, because routed-expert LoRA means re-quantizing.
7. **Gemini 3.8 Flash facts:** GA since 2-Sep; 1M context; thinking level LOW/MEDIUM/HIGH (temperature is ignored, so
   diverse hints need separate calls); introductory price $0.75 / $3.75 per 1M tokens in/out (batch half) until
   31-Dec, so ~$34 per 1,000 hint calls of 40k tokens. ARC lists it at 35% on ARC-AGI-3 with its provider adapter at high
   thinking (6-10% in the standard harness). Gemini 4 Argon is limited to a "Fairwind Program" for now.
8. **Terms risk (Son's call):** the research agent quoted Google Cloud Service Specific Terms §17(b): output from an
   AI/ML service may not be used to "create or improve models similar to a Google Model", with the Agent Platform
   exemption not covering Google pre-trained models like Gemini. My own one-page check could not confirm the wording
   (the page is long). If it holds, every Gemini route (hints, paths, judging) trains on Gemini output in some form. The
   model's own wins and ARC's human replays are clean. Kaggle rules: open-source system and weights, outside data
   "reasonably accessible to all" at "minimal cost", nothing explicit on closed-model outputs.

## 1. The targets: levels the model clears sometimes

From the 83 finished runs since 28-Sep in Firestore (79 ours, 4 Daniel's notebook). `reach(k)` = share of runs
that cleared at least k levels. A **frontier level** is cleared by 5-60% of runs: the model can do it, and a
recorded win exists to start from. Script: `D:\codex-work\rl-20261001\frontier.py` -> `frontier.json`.

| game | group | reach by level (%) | frontier levels |
|---|---|---|---|
| bp35 | hard | 100 25 6 0 0 0 0 0 0 | 2, 3 |
| g50t | hard | 84 64 16 5 1 0 0 | 3, (4) |
| ls20 | hard | 94 58 43 12 0 0 0 | 2, 3, 4 |
| sk48 | hard | 66 8 2 0 0 0 0 0 | 2 (and 1) |
| wa30 | hard | 100 64 43 8 0 0 0 0 0 | 3, 4 |
| cn04 | medium | 99 64 45 40 16 6 | 3, 4, 5, 6 |
| ka59 | medium | 100 98 90 76 66 11 0 | 6 |
| m0r0 | medium | 99 90 67 52 28 2 | 4, 5 |
| r11l | medium | 100 92 69 59 43 31 | 4, 5, 6 |
| s5i5 | medium | 100 90 54 30 18 13 0 0 | 3, 4, 5, 6 |
| sc25 | medium | 95 94 89 67 27 11 | 5, 6 |
| sp80 | medium | 100 43 33 17 2 0 | 2, 3, 4 |
| tu93 | medium | 98 98 94 92 82 66 63 42 7 | 8, 9 |
| vc33 | medium | 100 100 100 78 61 52 34 | 6, 7 |
| *tn36* | *hard, test* | 99 65 33 18 8 4 1 | *3, 4, 5 (one full clear)* |
| *lf52* | *hard, test* | 99 69 41 2 0 ... | *3* |
| *su15* | *medium, test* | 100 94 90 52 16 13 8 2 0 | *4, 5, 6, 7* |
| *re86* | *medium, test* | 98 98 95 93 82 24 1 0 | *6* |
| *dc22* | *medium, test* | 96 93 81 64 0 0 | *none (wall at 5)* |

What this says:
- **There is signal without any teacher.** Even the hard games have levels the model clears a third to half the
  time (ls20 L2-3, wa30 L3, sp80 L2-3). From a moment inside such a level, some of 8 tries win and some lose.
  That difference is all GRPO and expert iteration need.
- **The biggest burst, tn36 (one full 7/7 clear, in Daniel's run A), is a fenced test game**, and so are su15 and
  lf52. That is a good thing for the proof: if training on the other games lifts tn36 and su15, the model learned
  habits, not answers. Your call in §10.
- The easy six have no frontier left (they are won or lost outright), so they are not targets.
- cn04, r11l and vc33 were left out of R16 as coin-flips. They are not test games, so they join the training set:
  they have the widest frontiers of all.

**Training pool (proof of concept):** the 11 train games + cn04, r11l, vc33, plus community and hand-made games
whose frontier we measure the same way (two plays each; the 29-Sep review already lists 85 "close" games).
**Never trained:** the test 5 and as66.

## 2. The loop

```
   play (current model)            pick moments                  try 8 times             keep / score
 runs of the training games ──► inside frontier levels ──► from each moment, live ──► reward = the level's
 (also the control numbers)     (clear rate 20-80%)         until clear or cap         Kaggle score
                                                                                            │
   merge + redeploy  ◄──── train the adapter (round k) ◄──── winners (+ losers, later) ◄─────┘
```

One round:
1. **Pick moments.** From runs and from earlier tries: turns inside frontier levels, preferring moments whose
   measured clear rate is 20-80% (most to learn), deeper levels first (a level k counts k times in the score).
   Start late in the level (high clear rate), move earlier as the model improves (reverse curriculum).
2. **Try.** 8 continuations per moment on the current model, same harness, same temperature as submission.
3. **Score each try** with the scorer's own level formula: cleared -> `min(1.15, (human / actions)^2)`, where
   actions = actions before the moment + the try's actions; not cleared -> 0. A try that runs past its token cap
   counts as not cleared, so slow thinking is punished the way the clock punishes it.
4. **Train.** Rounds 0-3: expert iteration = fine-tune on the best try of each group that beat the group's mean
   (only the model's own tokens; prompts, tool output and the replayed past are masked). Later rounds, if this
   plateaus: GRPO with negatives (§5).
5. **Merge, check, redeploy**, next round. The test games are not looked at between rounds.

**Round 0 needs no new play:** the winning level segments already in the runs are expert-iteration data (the
model's own wins, filtered to the efficient ones). It is also the cheapest end-to-end test of
train -> merge -> serve -> score.

## 3. What we train (questions 1 and 2)

**Checked today:** Daniel's model (`Intel ... W4A16-AutoRound`, the one his notebook serves) was quantized with
`--ignore_layers lm_head,embed_tokens,visual,linear_attn,self_attn,hyper_connection,mlp.gate,shared_expert,
in_proj_a,in_proj_b,ple,mtp,indexer`. So in his model, as in the RadixArk NVFP4 we serve (checked 22-Sep), these
stay BF16: full attention (12 layers), linear attention (36 layers), the shared expert (48 layers), the router.
Only the 512 routed experts are 4-bit, and they differ between the two (int4 group-128 vs NVFP4).

**So the adapter lives in the shared BF16 tensors** and one adapter merges into both stacks in minutes, byte-for-
byte outside those tensors. The trainer runs the **full 512 experts** with the served 4-bit values dequantized
(exactly what the rollout server computes), because:
- Daniel's notebook, our base since 1-Oct, serves all 512 experts;
- at 336-384 kept our cut model is within ~0.01-0.02 token KL of the full one, so an adapter learned on the full
  model carries over; the repair net and draft are re-fitted after the merge (runbook step, ~1-3 h);
- training through the cut would teach the adapter to patch pruning damage, which does not carry back to the full
  model and ties skill to a serving trick.

| option | trains | to train | ships as | Daniel's stack | ours | verdict |
|---|---|---|---|---|---|---|
| **LoRA on shared BF16 parts** | ~60M (rank 32) | one 8-GPU box | merged into BF16 tensors | yes, no requant | yes, no requant | **start here** |
| full fine-tune of shared BF16 parts | ~3B | + ~50 GB optimizer | ~6 GB of tensors | yes | yes | if LoRA saturates |
| + router | +63M | small | BF16 router rows | yes | expert cut and repair net must be redone | later ablation |
| routed experts (LoRA or full) | 120B | 64+ big GPUs (NVIDIA's own recipe: 64 H100, validated at 4k context) | re-quantize to 4-bit; a small RL update mostly rounds away | requant | requant | no |

Why LoRA is enough here: an RL episode carries very little information (about one bit: cleared or not, how fast),
and published comparisons find LoRA matches full fine-tuning for policy-gradient RL even at low rank, provided the
MLP side is covered (Thinking Machines, "LoRA Without Regret", Sep 2025). The shared expert is our MLP-side target.

**Training stack (G1 measures it):** transformers 5.18 (Flash-Next's `qwen4_exp` is native since 5.16) + peft 0.21,
experts frozen and dequantized from the served checkpoint, the 51B n-gram table in host RAM, the sparse-attention
indexer frozen (NVIDIA's trainer freezes it too), long context handled as "past without gradient, last turns with
gradient". NVIDIA's NeMo AutoModel/RL support this model, but validated only at 4k context on 64 H100s; our
turns run at ~100k context on one 8x RTX PRO 6000 box, so we use their model code as reference, not their recipe.

## 4. The teacher (question 3)

- **Burst levels: none.** The engine is a perfect judge (deterministic, exact score), and the model already wins
  there sometimes. Expert iteration turns "sometimes" into "usually".
- **Dead levels** (8 of 8 tries fail, or no run has ever cleared it) need outside help. Three kinds, none of which
  puts the teacher's words into the weights:
  1. **Where to fork.** The teacher reads a moment's record (frames, actions, the model's notes; no future) and
     marks the turn where a wrong goal got locked in. Forks there have the sharpest credit.
  2. **A hint at the dead end.** One or two sentences about *how to test*, never the answer ("LEFT and RIGHT in one
     batch can't tell you which one moved it"). 4 of the 8 tries get it in the prompt. If hinted tries win, the
     group is no longer flat. For training, the hint is **removed** from the context: the model is trained to
     produce the winning continuation without being told.
  3. **A path to start from.** For levels no run has cleared, a recorded winning path (Gemini playing, or a human
     demo) gives moments near the goal to fork from.
- **Gemini 4:** Son, 1-Oct: "we can use Gemini 4 now as a teacher". On Vertex it is the publisher model
  `gemini-4-argon` (launch stage GA), but `cellensml` gets "not found or no access" on generateContent in every
  region tried (global, us-central1, us-east1/4/5, us-west1, us-south1, europe-west1/4, asia-northeast1), and
  Son's other projects don't have the Vertex API on. Needed: the model enabled for `cellensml` in Model Garden, or
  an AI Studio key in a file. Gemini 3.8 Flash works on `cellensml` today; its public replays clear 6 of 7 levels
  of g50t, where we average 1.7. Plan: build the juncture service on 3.8 Flash; switch the model name when
  Gemini 4 answers.
- **Opus:** blocked by an API safeguard ("reasoning_extraction") on 2 of the 5 live reviews on 30-Sep (one review,
  one check). Not dependable inside the loop.
- **Gemini 3.8 Flash as the reviewer, probed 1-Oct** (`D:\codex-work\rl-20261001\gemini_review_probe.py`): the same
  brief and the same five 30-Sep packets Opus saw (33-58k tokens each, Vertex global endpoint). It agreed with Opus on
  g50t, ls20 and wa30 ("leave"); on m0r0 it left the model alone where Opus rewrote (and Opus's own checker had failed
  that rewrite for overclaiming); on bp35, where Opus was blocked, it wrote an evidence-cited rewrite (the click
  itself ends the game; the "wedged in a channel" belief is refuted). 6-43 s per review. Five packets are an
  anecdote, not a calibration; the forks decide whether its hints help.
- **Terms:** with the hint removed before training, no Gemini text is trained on. If you later want Gemini's
  words in the weights, that is a terms check like the Opus one (your call).

## 5. Rollouts (question 4)

Measured (branch replay, 1,173 tries from inside levels the model had cleared): 56-86% of tries clear; a try costs
~66k tokens from early in a level, ~35k from the middle, ~9k from the last third.

| knob | value | why |
|---|---|---|
| unit | one level from a saved moment | a whole game is 80-130 min and dozens of levels: no usable credit |
| tries per moment | 8: play 4, add 4 only if the first 4 disagree | saves ~30%; a 4-0 split teaches nothing |
| cap | level clear, or 40 turns, or 1.5x the reference's remaining actions, or 1.5x its remaining tokens | time is the real limit on Kaggle |
| which moments | measured clear rate 20-80%; deeper levels first; late -> early | most learning per GPU-hour |
| moments per round | ~200 (~1,100-1,600 tries, ~30M tokens) | ~2-4 h on 8 one-GPU VMs at ~600 tok/s each |
| how often | one round = try -> train -> merge -> redeploy; 1 per day at first | the policy is fixed inside a round |
| where | the stack we submit (Daniel's server + harness); ours until his fork runner is ported | train where you play |

Stability, in order of use: expert iteration (no ratios, cannot run away); then GRPO with the clipped ratio
against the logged rollout log-probabilities, ratios truncated at 2 (fixes server-vs-trainer differences), a small
KL to the round-0 model, and **routing replay** (record each token's expert choice in the server, force it in the
trainer) if the MoE routing disagreement is large. Routing replay is the published fix for exactly this failure in
MoE RL (R3, arXiv 2510.11370); Qwen's GSPO (sequence-level ratio) is the alternative.

## 6. The tree (question 5)

**Two identities.** A *game state* is a game plus the list of actions from its start (the engine is deterministic,
so that list rebuilds the board exactly). A *moment* is a point in one trajectory: game state **plus** the model's
context (its past thinking and notes). Tries fork from moments; values are also pooled per game state, so two
trajectories that reach the same board share what was learned there.

| Firestore collection (`ai-namespace`) | one document per | key fields |
|---|---|---|
| `rl_moments` | forkable moment | game, level, turn, actions before, state key, source (run or try), policy, harness, tries, clears, value, status |
| `rl_tries` | one try | moment, group, policy, kind (plain / hint), outcome (cleared, actions, turns, tokens), reward, payload URI |
| `rl_groups` | tries from one moment under one policy and kind | rewards, mean, spread, mixed?, round |
| `rl_rounds` | round | policy in / out (adapter sha), moments, mixed share, train-side clear rate, eval runs |

GCS, `gs://cellens-ai-artifacts/arc3-rl/<campaign>/`: per try, the exact requests and replies (images included)
as gzipped JSONL, plus token ids and log-probabilities once the proxy logs them. Firestore is the index only: small
documents, live writes from the VMs (the run-score collection already works this way), queries like "open moments
in sp80 level 3 with clear rate 20-80%".

What the tree buys: moment selection by value; reverse curriculum for free (a win's later moments are easier);
"value cliffs" (consecutive moments of one trajectory whose clear rate drops sharply mark the turn where it went
wrong, without any teacher); dedupe; and a page per level on the site showing every attempt as a tree.

Code: `gcp/controllers/rl/rl_tree.py` (store, IDs, value updates, moment selection; tests run without Firestore).

The tree is the RL part of a wider store for every trace we generate, so the data outlives this experiment:
[2026-10-01-arc3-trace-lake.md](2026-10-01-arc3-trace-lake.md) (canonical episodes with model / harness / game versions,
prefix and image dedupe, per-level index of all runs, dataset manifests, adapter lineage).

## 7. Humans (question 6)

1. **Games.** RL generalizes only as far as the variety it trains on. The public 25 are a tutorial built to be
   unlike the hidden set (AGENTS.md). The hand-made and evolved games are the curriculum; each new game adds new
   "first contact" moments, the skill hidden games test.
2. **Demos** for levels nobody has cleared: the Boss's recordings (130 records) as action paths to start from.
3. **A 10-minute check per round:** read the 10 highest-reward wins. Understanding or luck? (The 29-Sep review
   rated ~85 of 478 cleared community levels as luck.) Luck-flagged wins are dropped from training.
4. **Hints at dead ends,** same mechanism as Gemini's, written as habits, never as a game's answer.

## 8. What counts as success (fixed now)

- **Primary:** levels on the 5 fenced test games, R16 runs (`ARC3_GAME_SUBSET=r16`), adapter vs no adapter, same
  day, same stack. Screen 2 runs per arm; confirm with 4 more; ~8 for a claim (2 runs need ~+3 levels).
- **Secondary:** train-game levels (memorization shows up here first), tokens per action, tool errors, draft
  acceptance, tok/s.
- **Final:** one Kaggle submission when a confirmed gain exists.

| result | reading | next |
|---|---|---|
| test 5 up, train up | habits learned | scale: more games, more rounds |
| train up, test flat | games memorized | more variety (community + hand-made games), not more rounds |
| both up, tokens per action up a lot | wins bought with time | tighten the token cap |
| both down | the 27B round-3 pattern | inspect the data filter and rank; roll the round back |

## 8b. Sign of life, and how to tell good training from bad (Son, 1-Oct)

**The main chart: per game x level, the clear rate and the moves needed to clear it, per model version.** Every
episode and try is in the trace store with its model version (`lake_levels`: game, level, cleared, actions, score,
policy_id), so this chart is a query, not a project.

**Sign of life = the probe set moves.** A fixed set of ~60 moments on frontier levels of the training games, chosen once
and never trained on directly, replayed with 8 tries by every new model version (~480 tries, ~12M tokens, ~40 min on 8
VMs). Pooled over 60 moments the clear rate has a standard error of ~2-3 points, so a 5-7 point change is visible after
one round, where a full 25-game run swings +-5 points of score on its own. Alive = clear rate up or moves-to-clear down
on most frontier levels, with no drop on levels the base model already clears. A second probe set on the test five
(forks for measuring only, never trained on) would give the same early read on transfer; that relaxes the 29-Sep "never
forked" rule for those games, so it is Son's call.

**Good vs bad training, read every round:**

| read | good | bad, and what it usually means |
|---|---|---|
| probe clear rate, moves to clear | up / down | flat while the training loss falls: memorizing the records, not learning |
| levels the base already clears | unchanged | down: forgetting; lower the learning rate or mix in base wins |
| thinking tokens per turn, moves per turn | about the same | thinking grows: slower on the clock even if per-move play is better |
| tool errors, malformed calls | same or fewer | up: the format is drifting |
| distance from the base model (KL on fixed turns) | small, growing slowly | jumps: the round moved too far; roll back |
| variety between tries of one moment | stays | collapses (all 8 tries identical): winners-only training has run its course; switch to GRPO |
| test five, full R16 runs | up, or flat early | down: stop and inspect |

**Fast vs slow:** tries are inference on the already-tuned Combo A stack (~17 GPU-h per 200-moment round, ~2 h on 8 VMs);
training is small (round 0 is 8M trained tokens, a 61M-parameter LoRA) and its speed matters little as long as a round
fits in hours; evaluation is the same full runs as today. A round should take about half a day end to end.

**What there is to tune in training:** mostly the data (which moments, which tries, the weights), then the method
(expert iteration vs GRPO, KL anchor, tries per moment), then a few numbers (learning rate, rank, epochs). The harness is
frozen for the whole RL series (changing prompts mid-series makes the old data stale), and the inference work already
done is reused as-is for the tries. The new engineering is correctness (exact prompts, merge, served = trained), not speed.

## 9. Build list, gates, cost

| item | what | GPU | state |
|---|---|---|---|
| B0 | frontier map from Firestore runs | none | **done** (`frontier.py`, `frontier.json`) |
| B1 | tree store: Firestore index + GCS payloads, moment selection | none | **built with this plan** |
| B2 | reward = the scorer's level formula; group stats; expert-iteration pick; GRPO advantages | none | **built with this plan** |
| B3 | seed moments from runs: map turns to levels, keep frontier levels | none | **built with this plan** |
| B4 | training records from request logs: exact chat template, loss mask on the model's own tokens | none | **built with this plan** (Daniel's runs log requests; our scored runs do not: `save_request_logs` is off, so ours need a replay pass) |
| B5 | try runner: N plain / hint tries from a moment, caps, reward to Firestore | 1-GPU VMs | **built** (`try_driver.py`, `derive_tries.py`, `queue_tries.py`); local replay exact; first campaign after the Combo A seeds |
| B6 | trainer: qwen4_exp + LoRA, served experts, long context; expert-iteration loss, later GRPO | 4-GPU box | **runs on the real model** (§9b): fast sparse attention, served 4-bit experts; long-record ladder in progress |
| B7 | merge into W4A16 and NVFP4; zero check, served = trained, mutation, boot, canary | 8-GPU box | **written** (`merge_lora.py`); zero / match / mutation checks pass on the tiny model; boot and served = trained are G1 |
| B8 | Gemini juncture service (packet without the future -> hint) | none | after G2 |
| B9 | exact token + log-probability logging in the proxy | none | before GRPO |

| gate | what | GPU | rough cost |
|---|---|---|---|
| G0 | B0-B4 + tests; round-0 data count | none | done/today |
| G1 | trainer forward matches the server on captured turns; one LoRA step; merge; boot; checks | one 8x RTX PRO 6000 box | ~1 day |
| G2 | B5 on ~50 frontier moments x 8 tries: share of mixed groups, tokens per try, clear rates; Gemini hints on ~10 dead groups | 8 one-GPU VMs | ~15 GPU-h |
| G3 | round 0 (own wins) -> merge -> screen (2+2 R16 runs) | box + 4 VMs | ~1 day |
| G4 | rounds 1-3 (expert iteration from moments) -> screen -> confirm | box + 8 VMs | ~3-4 days |
| G5 | GRPO with negatives, only if G4 plateaus | same | later |

Per round: ~15-25 GPU-h of tries + 2-8 h of the training box (G1 measures the trainer's speed; a sloppy MoE forward
is the risk). Quota: 8 Spot RTX PRO 6000 per region, so the training box takes one region and the try VMs another.
If Spot H200/B200 is available, the trainer is 3-5x faster on it; worth one quota check.

## 9a. G0 results (1-Oct, from Daniel's four GCP runs)

Ran on a CPU VM in us-central1 (`g0_vm_startup.sh`; the local link is ~40 KB/s). Output:
`gs://cellens-ai-artifacts/arc3-rl/rl-1001a/g0/`.

- **Moments:** 254 forkable moments written to Firestore `rl_moments` (campaign `rl-1001a`), across 12 training
  games: ls20 46, m0r0 38, cn04 34, r11l 26, ka59 18, wa30 18, tu93 17, sp80 16, bp35 12, sc25 12, vc33 11, sk48 6.
  g50t and s5i5 have none yet: these four runs did not clear their frontier levels.
- **Round-0 data:** 220 records holding 4,635 of the model's own winning turns (thinking + tool call): 8.0M trained
  tokens inside 24.9M tokens of context. Records are per game, so the easy six can be left out at training time.
- **Exact tokens:** rendering the logged requests with the official template came out exactly 11 tokens short of the
  server's own count, on every request. Cause: the server (SGLang 0.5.19 "pennyroyal") re-serializes each tool
  through its request model, adding `"strict": false` and `"defer_loading": null`. `render.server_tools` copies that,
  and the rendered prompt then equals the logged count exactly: **220 of 220 records, zero difference**
  (`check_records.py`). Every record maps one generated span to each assistant message (220 of 220).
- **Trainer and merge, tiny model on CPU** (`test_trainer_tiny.py`, transformers 5.18 `qwen4_exp`): the LoRA hits
  exactly the ten intended module kinds and not the MTP head; the chunked log-probs equal the model's own logits;
  the loss falls; a zero adapter merges byte-identical; the merged checkpoint matches the LoRA model; a sign-flipped
  merge is caught. The GPU kernels for linear attention (`flash-linear-attention`, `causal-conv1d`) were not
  installed there, so transformers used its slow reference code; G1 installs them.

## 9b. G1 trainer results (2-Oct, 4x RTX PRO 6000 box `arc3-rl-train4-20261002`, us-south1-b)

The trainer service polls `gs://cellens-ai-artifacts/arc3-rl/trainer/train4-1002/jobs/`; job logs land in `.../out/`.

- **The reference model code cannot train our records as is.** transformers' sparse-attention picker (QSA indexer)
  loops over every token in Python, and the model builds a dense token-by-token mask (10 GB at 100k tokens). Our
  round-0 records average ~100k tokens. `fast_qsa.py` replaces both for training (batch 1, no cache): the same picks
  computed in batches, attention over only the picked keys, no dense mask, and each layer's input parked in host RAM
  between forward and backward. Checked against the reference (`test_fast_qsa.py`, 16 checks): identical picks at the
  real model's size (4,096 tokens, past the 2,048 budget), outputs and gradients within BF16 rounding, identical LoRA
  gradients with the host-RAM parking. On the real model, a 12k-token forward went from 41 s to 8 s.
- **Training works on the real model at 12k tokens:** loss on one record 0.354 -> 0.350 -> 0.321 over 3 steps,
  ~60 s per step (profile pending). Same record, fast vs reference forward: mean |difference in log-prob| 0.07 per
  token (max 2.1). Suspected cause: blocks the picker scores exactly zero, where the two tie-break differently; the
  server's own tie-break is unknown. To settle with server log-probs (B9).
- **Memory was the wall:** with BF16 experts each GPU holds ~57 GB of weights, and a training step on a 77k-91k token
  record ran out of memory. Plan §3 already said to train through the served 4-bit experts; `nvfp4_experts.py` does it:
  the RadixArk checkpoint's packed experts stay 4-bit on the GPUs (1.33 GiB per layer instead of 4.69), and each layer
  unpacks its 512 experts only while it runs. Checked (`test_nvfp4.py`): unpacked weights vs the official BF16 experts
  cosine 0.9955 (9.5% relative error, normal for 4-bit) at layers 0/23/47; the opposite nibble order fails (1.41);
  the module matches transformers' own expert code. Activations stay BF16 here; the server also rounds them to 4-bit
  (not reproduced yet). Length ladder with 4-bit experts: running.
- **Our harness logs no token counts** (request-log responses carry no usage). Two consequences, both handled: moment
  seeding sizes each turn from its transcript (reasoning + tool-call characters / 3.5); the try runner now saves the
  server's usage for every live request, so the exact-token check on our SGLang build runs on the first tries.
- **Ladder with the 4-bit experts (job 015):** weights ~26 GiB per GPU (was ~60). 12k: forward 13 s, step 71-88 s.
  **77.6k-token record trains: step 218 s, peak 87 GiB.** 91k, 109k, 118k ran out of memory; the failing allocations
  (5.2-5.6 GiB) are exactly the expert block's per-token buffers (tokens x 10 experts x 2,560). Profile of a 12k step:
  52% of GPU time in one kernel, the backward of the key/value gather in the sparse attention (sort-based). Fixes
  in code (tests pass): gather by `index_select` into float32 (atomic backward), experts run in 16k-token chunks,
  cheaper 4-bit unpacking (one table lookup per byte). **Job 020 with the fixes:** 12k step 31 s (was ~60-70);
  77.6k step 193 s, peak 73 GiB (was 218 s / 87); **91k now trains (230 s, peak 81 GiB)**; 109k and 118k still run
  out of memory on GPU 0 (92-93 GiB; GPU 0 also holds the embeddings and vision tower). For fork tries this is moot:
  the plan trains only the live turns, with the history computed without gradient.
- **The 0.07 gap (fast vs reference, same record):** not ties (6 of 116,244 picks tied at the cut), not the picks (the
  reference picker inside the fast path gives the same 0.072), not train vs eval mode (reference: 0.0000 between
  modes, it is deterministic). What is left is the attention arithmetic itself (float32 gather vs SDPA kernel);
  untested whether two equivalent reference kernels (eager vs SDPA) differ as much (job 021 was cancelled).

## 9c. Human review page (2-Oct)

Published privately: https://claude.ai/artifact/1wrN6rXfKP5oiFMYP7juPj ("ARC3 Fork Review"). Per moment it replays the
current level up to the decision point in 3 seconds, lets the reviewer scroll back through every action with the
model's thinking for that turn, and shows the tries from that moment side by side (outcome, actions, replay in the
big frame). The reviewer picks one, flags bad ones, adds a note; picks are stored in the page's database (one
document per reviewer and moment, `labels/<moment>~<reviewer>`), and other reviewers' picks show only after saving.
Data comes from `review_export.py` (try campaign -> one compact JSON per moment, frames delta-encoded); the test five
are never exported. Today it holds one real sample moment (no tries yet). Mark and invitees need Contributor access
(or Editor if invited by email) to save picks.

## 9d. Paused (Son, 2-Oct ~01:35 EDT)

"The trace gen is so low ... tomorrow I'll just focus on 1 game." State at the pause:
- Seed runs `giantrlseed{a,b,c,d}1001` (Combo A + request logs) finish on their own ~06:10 UTC.
- Try campaign `rl-1002a`: 24 moments x 8 tries (sp80, ls20, wa30, r11l; 6 each, from levels the seeds had already
  cleared), 4 spot VMs `rltry_rl1002a_vm{0-3}`, 16 lanes each, stop on their own at their 3-hour deadline (~08:30
  UTC). Results: `gs://cellens-ai-artifacts/arc3-rl/tries/rl-1002a/results/` (+ events/ for the review page).
  77 moments in Firestore `rl_moments` (campaign rl-1002a).
- Trainer VM `arc3-rl-train4-20261002` stopped after job 020 (disk kept: BF16 model, 4-bit experts, records).
- Not started: round-0 data from the finished seeds (`submit_g0c.sh`), round-0 training, filling the review page.

## 9e. First try batch, and the one-game plan (2-Oct, Son: "focus on RL-ing just ONE GAME")

What the first 144 results of `rl-1002a` showed (05:50 UTC):
- **3 of 4 VMs broke their server**: each try first replays the recorded game to the fork (2-15 min; r11l took 15),
  then all 16 tries go live at the same moment with 60-100k-token prompts; SGLang answered 500, then dropped
  connections (96 tries lost: 88 connection errors, 7 replay divergences at step 2, 1 tokenizer 500).
- **The token cap was the main "failure"**: on the healthy VM (ls20 level 2, 6 forks x 8), 37 of 48 tries stopped at
  the cap (20-28k tokens = 1.5x the reference's transcript-estimated tokens, 3-10 turns), 11 cleared. Wins took 4-13
  turns and 30-101 actions (human 123). Per fork: 0/8, 1/8, 2/8, 0/8, 0/8, 8/8 (the 8/8 fork: all 30 actions, identical).

One-game loop (recommended game ls20: frontier L2-L4, burst pattern confirmed above, not fenced):
- Tree: every turn start of every ls20 trajectory (seed runs, site runs, every try) is a node with tries / clears /
  best actions; tries add their own turns as new nodes.
- Round: ~40 nodes x 8 tries -> train on the wins (most efficient win per node + one different win) -> merge ->
  fresh full ls20 games + fixed probe nodes + test five unchanged -> next round. GRPO on mixed groups once rollout
  log-probs are logged (B9).
- Node priority: outcome uncertainty (mixed groups teach most; all-win teaches only speed; all-lose nothing without
  help) x level gate (earliest level not reliably cleared first) x value-cliff bonus (a node at 6/8 whose next turn
  on the same path is 1/8: the mistake is in that turn) + a small bonus for untried nodes. Not raw score.
- Budget per round: ~70% mixed nodes and cliffs; ~20% new nodes from the latest tries and one step earlier in the
  level (reverse curriculum: the real game starts at the level start); ~10% stuck nodes (0/8 twice) at higher
  temperature or with a hint. Retire 8/8-twice nodes (except speed). Watch pass@1 vs pass@8 on the probe nodes.
- Runner fixes first: stagger the live start (one try per fork prefills, the other 7 reuse the cached prompt), no
  token cap (40 turns + the game clock), one replay per fork instead of 8, all VMs on the one game. Trainer: train
  only the live turns, history computed without gradient (the §3 long-context method).

**Stopped (Son, 2-Oct ~02:20 EDT: "stop all works ... much more optimization before keeping working").** Final batch:
192 tries, 66 valid (ls20 48: 11 cleared; r11l 18: 9 cleared), all in GCS + the lake. All try VMs deleted; trainer and
G0 VMs stopped (disks kept). Written but not deployed or tested: the runner fixes above in `try_driver.py`, and
`derive_tries.py --vm-hours` (long-lived workers that pull from one standing queue, Son's design). Not written: the
tree supervisor (keeps N workers alive, tops up the queue from the Firestore tree, adds tries' turns as new nodes).
What to optimize before restarting, by measured cost:
- **Replay before every try:** 2-15 min per try, repeated by all 8 tries of a fork (r11l: 15 min). Replay once per
  fork, or save the replayed state and fork from it.
- **Live switch:** 16 tries sending 60-100k-token prompts at once crashed 3 of 4 servers (fix written, untested).
- **Try length:** 7-13 min per try even when healthy; a healthy VM finished 48 tries in ~25 min at 16 lanes.
- **Trainer:** 77-91k-token records take 3-4 min per step; 109k+ runs out of memory on GPU 0; only one of the 4 GPUs
  works at a time (layers are split across them in sequence).

## 9f. Memory plan for rollouts and training (2-Oct, Son: "optimize while reducing the risk of OOM")

**What we know (measured, or from the Main innovation thread on Combo A):**
- Try VM (1x RTX PRO 6000, ~177 GiB host RAM). GPU KV pool 1,935,872 tokens at mem 0.98 = ~19 full 101,888-token
  contexts; 19 decode slots; Mamba cache 95. Their gate fires 19 concurrent ~95k prompts and gets all 19 back in
  ~30 s with no errors, so a burst of big prompts alone does not crash the GPU side.
- Host RAM is the tight wall. The server's host cache (51 GB KV + 12.6 GB Mamba + 3 GB QSA) plus the n-gram table's
  64 GiB pinned block (47.7 GiB of data) leave ~22 GB on a 185 GB VM. Our try VMs sat at 145-149 GiB of 177 all
  along (~28 free) with 16 tries replaying. On 1-Oct one sandbox spike made the kernel kill SGLang. Last night's
  server death at the live switch fits that pattern, but is not proven: the restart overwrote the server log.
- Replay costs 3-28 s per recorded turn with 16 tries replaying as threads of one process (the "fast" harness fix
  was already on). Suspects: Python lock contention between the 16 threads, and per-turn harness work.
- Trainer (4x RTX PRO 6000, 708 GB RAM): ~26 GB of weights per GPU with 4-bit experts; peaks 73 GB at 77.6k
  tokens and 81 GB at 91k; out of memory at 109k+ on GPU 0 (embeddings + image model + 12 layers).

**GPU memory model of a try VM (Combo A on one RTX PRO 6000; from the seed-A and try-vm0 server logs and the
SGLang source in D:\codex-work\mtp-research\sglang-official). It only holds for this exact config (fp8 KV, mem 0.98,
MTP on, 336-expert NVFP4, page 64):**
- Fixed: weights ~57.6 GiB; CUDA graphs ~1.2 GB; free for activations 2.4 GB after allocation (the log warns
  down to 0.84 GiB free in play).
- Per token, full-attention KV (12 layers + the MTP layer, fp8): 1,938,176 tokens = 22.2 + 1.8 GB, ~12.3 KB per
  token. 19 x 101,888 fits exactly, so running requests can never overflow it. In 2 h of normal play it peaked at
  80% (median 51%).
- Per request, linear-attention states (36 layers): 95 slots x ~55 MB = 5.3 GB. Each running request holds 4 slots
  (one working state plus two tracking copies for prefix reuse, and one more). 19 running = 76 slots = 80%, all game
  long; the other 19 slots hold saved prefix states (more on host via HiCache). This, not KV tokens, caps
  concurrency: max_running_requests 19.
- Prefix reuse needs all of: the same server process (nothing is shared across VMs or after a restart); token-exact
  prompts (64-token pages); and a saved linear-attention state at the matched point. The server saves that state
  only at the last 64-token boundary of each 4,096-token prefill piece and every 256 decoded tokens, and keeps it
  only until evicted. Measured: 89% of prompt tokens came from cache in normal play (each turn extends the last).
  Our 8-try forks arrived together, so hits stopped where a sibling's prefill had reached (53-70k of ~120k).
- Precision: the server's KV cache is fp8; the trainer computes attention in BF16. Same tokens, different numbers:
  emulate fp8 K/V in the trainer before trusting log-prob ratios (GRPO).
- Levers to test, one at a time, with the Main thread's concurrency gate: extra_buffer_lazy (second tracking copy
  only on demand: 3 slots per request instead of 4); int8 saved states (about 2x the saved-prefix capacity); the
  host cache size.
- Test before committing (1 VM, ~1 h): (a) 1 fork x 8 with a 1-token warm-up, expect each try's cached tokens =
  prompt minus at most 63; (b) 2 and 3 forks x 8 (24 tries over 19 running): queueing, hits, slots, RAM, tokens/s;
  (c) extra_buffer_lazy on/off.

**Rollout guards (try VMs):**
1. The kernel kills a sandbox, never the server: oom_score_adj -1000 on the SGLang processes, +500 on sandboxes.
2. Cap each sandbox's memory (RLIMIT_AS, e.g. 3 GB): a runaway model-written script ends its own try only.
3. Free host RAM: the exact-size n-gram pin (+16 GiB, Main thread's Kaggle kit `install_ple_exact_pin_patch.py`;
   not in the GCP startup yet: apply it inside the container before the server starts, like the QSA HiCache patch,
   and check the server log for "ARC3_PLE_EXACT_PIN_V1 exact: 47.68 GiB"; a "fallback" warning means the 64 GiB
   block is still there) and a smaller host cache on try VMs (64 -> 32 GB). Tries of one fork share their prompt,
   so parking matters less. Target: at least 40 GB free at peak.
4. Memory watchdog in the try driver (5 s samples): below 25 GB free, start no new try or live switch; below 15 GB,
   stop the newest tries cleanly.
5. Evidence on every VM: 5 s RAM/GPU samples and kernel OOM lines copied to the run folder; restarts write to
   sglang-restart<N>.log so the first traceback survives. The Main thread wants that traceback: their leading theory
   for the Kaggle runs that ended early is SGLang dying or stalling under load with ~110 open games.
6. Warm, then fan out: per fork, one 1-token warm-up request loads the shared prompt into the cache; then the 8
   tries go. One cold prompt at a time per VM.
7. Lanes: 16 now; 19-24 (3 forks at once) only after a test shows 40 GB free at peak.

**Replay:** measure one replay alone vs 16 at once (no model needed). If the lock is the cause: replay each fork
once and fork the process (the 8 tries share memory copy-on-write), or one process per fork. If it is per-turn work:
skip work that cannot change the state (viewer, HTML, transcript rewrites) during replay, keeping the exactness
checks.

**Training guards:**
1. Train only the live part of a try; compute the history once without gradient (prefix cache, read-only during
   the gradient pass). Memory then depends on the live part (usually 5-30k tokens), which removes the 109k+ OOM;
   expected 2-3x faster per record; the 8 tries of a fork share one history pass. Must match the full-sequence
   log-probs on the live tokens (test).
2. Predict each record's peak from its length (ladder fit); split or skip what does not fit; an OOM skips the
   record instead of killing the job.
3. Rebalance GPU 0 (embeddings and the image model move to the last GPU).
4. Host RAM: preallocate the pinned offload buffers once (~100 GB at 100k) next to the n-gram table (~100 GB BF16,
   or ~50 GB with the served FP8 table); ~200 of 708 GB.
5. Later: two 2-GPU replicas in data parallel once per-replica memory fits 2 GPUs (~2x throughput).

**Order, each proven on one VM before the next:** (1) replay profile; (2) rollout guards + a 3-fork x 8 stress
test with RAM evidence; (3) warm-then-fan-out, checked with the server's cached-token counts; (4) trainer prefix
cache, exactness and the 118k ladder; (5) ls20 on 4 long-lived workers + the tree supervisor.

## 10. Decisions

Settled by Son, 1-Oct:
- **Where RL plays: our stack, the "giant"** (Son: "our stack is competitive"; the Main innovation thread named it
  the best current stack). Arms `cr_sgl_c99k_w25_s19_g7920_giantsl336{a,b,c,d}1001`: all-25 44.4, hard-7 11.0,
  107 levels over 4 runs (no R16 / test-five numbers yet). Model: RadixArk NVFP4, uneven per-layer 336-expert cut
  (`lobotomy/assets/freq_keep336g_mtp.pt`, ARC3_PRUNE_PERLAYER=1), repair net `corr_k336gd`, draft `ft336gs`, T 0.6,
  25 lanes over 19 slots (priority gate), context 101,888, KV fp8 + 64 GB HiCache. Harness: the cr source with the
  P19 T06 knobs (blindspot fixes, test discipline, compact state, UNDO named, honest restart 60 s, no clock
  inheritance) plus the Daniel bundle v2 subset and the priority gate. Builder: `D:\codex-work\clkchk\giant_run.sh`.
  For RL tries: turn on ARC3_QSA_HICACHE=1 (fixes stale sparse-attention keys on prefixes reloaded from host RAM) and
  save_request_logs; freeze ARC3_TOOLFIX to whatever the submission will use (it changes the tool output the model sees).
  **Pinned with the Main thread, 1-Oct evening:** KV cache fp8_e4m3 + HiCache (the 4-bit KV runs are a slow experiment,
  not in any candidate). Pin `giantsl336` (1-Oct) today; if tonight's combo finals (~23:20 EDT) beat it, the submission
  becomes `giantcmba` or `giantcmbla` (both with ARC3_QSA_HICACHE=1 and ARC3_TOOLFIX=all; 23 lanes over 19 slots, swap
  keep 0.3) and the Main thread will say which. Match: T 0.6, 25 lanes / 19 slots / priority gate 19, context 101,888,
  mem 0.98, Mamba 95, draft ft336gs, repair net corr_k336gd, uneven 336 mask.
  **Final pin (Main thread, 1-Oct ~23:20 EDT): Combo A, arm `cr_sgl_c99k_w25_s19_g7920_giantcmba1001`.** 2 runs: all-25
  44.7 (44.71 / 44.66), hard-7 15.7 (19.8 / 11.6), 111 levels, ~804 tok/s, vs the giant's 44.4 / 11.0 / 107. It is the giant
  plus ARC3_TOOLFIX=all, ARC3_QSA_HICACHE=1, priority gate 23 over 19 server slots (25 lanes), ARC3_SWAP_KEEP=0.3; same
  T 0.6, context 101,888, fp8 KV, mem 0.98, Mamba 95. Combo B (A + death ledger) was worse (41.5 / 5.5). Combo A is
  also the next Kaggle candidate if Son approves, so RL plays where we submit.
- **Round-0 turns are weighted by efficiency** (Son, 1-Oct): each trained reply carries its level's score,
  min(1.15, (human / our moves)^2), so a level won in the human's moves weighs ~1 and in 3x the moves ~0.11
  (`build_records.records_for_game(..., human=...)`, per-token weights in `render.py` / `lora_train.py`).
- **Fence kept:** lf52, tn36, re86, dc22, su15 are never trained.
- **Gemini: clean data first.** Own wins and ARC's human replays now; Gemini arms after the terms check.
- **No 8-GPU box.** Son asked for a cheaper box: 4 GPUs needs no new code; 2 GPUs (maybe 1) needs a 4-bit
  training path (experts kept 4-bit on the card, unpacked on the fly), tested first on the tiny model on CPU.

What this changes in §0b:
- **Step 1's data comes from giant runs, not Daniel's.** Training on one harness's prompts and playing in another is a
  transfer bet. Giant runs have request logs off, but the fork runner's replay-only mode re-plays a run's recorded
  replies through the real harness without a model, so a CPU VM can regenerate the exact prompts of the 4 giant control
  runs (and tonight's combos) with save_request_logs on. Daniel's 4,635 turns stay as a fallback and a check.
- **Step 2's port is small:** the live-injection runner already forks our crfix 336 arm; it needs the giant's arm
  config, the replay-only data pass above, and the try kind ("plain" x 8, rewards to Firestore).
- **Re-check exact tokens on our server build:** the 11-token tool-serialization fix was measured on Daniel's SGLang
  0.5.19; the golden image may differ, so the first giant replay with request logs gets the same 0-difference check.

Still open: Son's OK on the 4-bit path (2-GPU box) and on efficiency-weighted turns in round 0.

## 11. Not verified

- That the trainer fits ~100k-token records on 4x RTX PRO 6000 with the 4-bit experts, and how fast (§9b). G1.
- ~~That re-tokenizing logged replies reproduces the served tokens exactly.~~ Prompt token counts now match
  Daniel's server exactly (§9a). Still open: the same check on our SGLang image, once our runs log requests.
- That Daniel's harness forks exactly (ours does: 12 of 12 local replays matched).
- That SGLang returns usable log-probabilities under the speculative draft. B9, before GRPO.
- The rollout numbers in §5 on this model and harness (they come from the 22-Sep vLLM branch replay). G2.
- Whether expert iteration moves the test 5 at all. That is the experiment.
