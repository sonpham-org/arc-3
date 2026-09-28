<!--
Author: Claude Opus 5.5 (Bubba sub-agent, moe-pruning-research)
Date: 27-September-2026
PURPOSE: Review of the "lobotomize the model / fewer active parameters" line for the ARC-3 competition
model (Qwen3.8 Flash-Next, a 512-expert mixture-of-experts model served on one RTX PRO 6000 on Kaggle).
Records what Son Pham's expert-pruning runs are and what is (not) documented about how he chose the
experts, surveys the published work on expert pruning / merging / fewer-active-experts with links,
ties it to ARC-3 (long agentic games, tool calls, vision), and ranks next experiments by payoff and cost.
Inputs: sonpham-org/arc-3 (all remote branches), Son's Kaggle notebook source, Son's Railway run store
(read-only), local Kaggle outputs under bubba-workspace/arc3-kaggle, public papers and model cards.
SRP/DRY check: Pass — no prior pruning review exists in bubba-workspace or sonpham-org/arc-3 (searched
all branches for prune/REAP/expert); serving numbers are taken from Son's chart as relayed, not re-derived.
-->

# Expert pruning and fewer active parameters for Flash-Next — review (27-Sep-2026)

## 1. The one thing to get right

**Pruning experts is a memory lever, not a quality lever.** Cutting 128 of 512 routed experts per
layer shrinks the resident weights. At a fixed memory fraction that space goes to the KV cache
(Son's chart: 736k → 1.97M tokens at mem 0.985), which lets more games run at once with longer
context (16 × 103k instead of 7 × ~100k). The score jump (21.4 → 33.9 on the 132-minute all-25
suite, one run, replicate pending) comes from *more concurrent games with enough context*, not from a
smarter model. Son's own control shows it: pruned at 7 games scored 19.7, about the same as unpruned J'
at 21.4 — i.e. pruning cost little and bought nothing by itself. Pruning also does not shrink per-token
KV (attention layers are untouched) and does not reduce *active* parameters per token (routing still
picks top-10 of the remaining experts).

The other lever, **fewer active experts per token (top-k reduction / expert skipping)**, is the
opposite: it saves compute per token (speed), saves no memory. The two stack.

## 2. Son's pruning work — what exists and what is documented

What I found (read-only):

- **Four pruned runs** on Son's run store, all 27-Sep, all tagged `prune384` (keep 384 of 512):
  `cr-sglang-c100k-w16-prune384`, `cr-sglang-c79k-w19-prune384`, `lacr-sglang-c100k-w13-prune384`,
  `lacr-sglang-c79k-w19-prune384`. Sources are his GCS runs `g4run-{cr,lacr}-sgl-c{100,79}k-a132-w{16,19,13}-20260927-*`.
  Artifacts were written from `D:\codex-work\arc3-sglang-parking\logs\...` (his Windows box drives it).
- **The model label is static harness metadata.** Pruned and unpruned (J' 7×103k) runs carry the
  identical resource string "RadixArk/Qwen3.8-Flash-Next-NVFP4 · RadixArk NVFP4 routed experts; served by
  SGLang (sglang-flashnext-sm120 patches …)". Nothing in the run data says which experts were cut.
- **sonpham-org/arc-3, all 55 remote branches:** no pruning code, doc or commit. The only REAP mention is
  in `HARNESS-NOTES.md` on `docs/deepseek-v41-ceiling-run`: a GLM-5.3-Flash REAP50 3-bit GGUF fit probe on
  llama.cpp that was closed ("unless a vLLM-servable pruned checkpoint appears").
- **Son's Kaggle notebook** (`arc3-flash-next-clean-return-sglang`): no pruning. It is the J' SGLang arm.
  His Kaggle datasets (serving parts A/B/C, runtime) date from late August — no pruned checkpoint uploaded yet.
- **Public pruned Flash-Next checkpoints exist** (see §3.1), including a REAP keep-384 build and an NVFP4
  REAP keep-448 build. The `prune384` name matches the public REAP-384 count, but that is suggestive only:
  the public 384 build is MLX / bf16, not the NVFP4 form Son's patched SGLang serves.

**Not documented anywhere I can read:** the selection method (REAP saliency? frequency? someone's
manifest?), the calibration data it was computed on, whether it is per-layer uniform, and whether
"super experts" were protected. **Ask Son for the kept-expert manifest and the calibration traffic.**
That is the artifact that determines whether his result transfers to Kaggle and whether an
ARC-calibrated manifest could do better.

## 3. Public work

### 3.1 Expert pruning

- **REAP — Router-weighted Expert Activation Pruning** (Cerebras; ICLR 2026).
  [arXiv 2510.13999](https://arxiv.org/abs/2510.13999), [code](https://github.com/CerebrasResearch/reap),
  [blog](https://www.cerebras.ai/blog/reap). Saliency of expert *j* = mean over tokens routed to *j* of
  (router gate value × L2 norm of the expert's output). Averaged only over tokens that actually route to
  the expert, so a rarely-used but important expert is not cut just for being rare. Pruning is uniform per
  layer (same fraction in each layer). Key results: on Qwen3-480B-Coder-FP8 at 50% pruning, 97.6% of
  non-agentic coding and 96.7% of SWE-Bench (agentic) retained; on Qwen3-30B-A3B, pruning beats merging on
  generation (50% compression coding 0.541 vs M-SMoE 0.397 vs HC-SMoE 0.364).
  **Calibration domain is decisive:** on Qwen3-30B coding, calibrating on generic web text (C4) *collapsed*
  several compressed models to 0% accuracy, while code-domain calibration held up. Cerebras publishes
  pruned checkpoints (e.g. [Qwen3-Coder-REAP-246B-A35B-FP8](https://huggingface.co/cerebras/Qwen3-Coder-REAP-246B-A35B-FP8)).
- **Flash-Next REAP builds on Hugging Face** (community):
  - [sh0wie/Qwen3.8-Flash-Next-REAP-384-MLX-4bit](https://huggingface.co/sh0wie/Qwen3.8-Flash-Next-REAP-384-MLX-4bit)
    (and a bf16 sibling): keep 384 of 512 per layer, top-10 routing unchanged, REAP saliency on ~686k tokens
    of *agentic-coding* traffic, kept-expert manifest shipped as a JSON file. HumanEval 92.1% vs 93.9% stock
    (single run). Vision tower intact but **only text was evaluated**. Keep-288 builds also exist
    ([collection](https://huggingface.co/collections/sh0wie/qwen38-flash-next-reap)).
  - [lee-chang-93/Qwen3.8-Flash-Next-NVFP4-REAP-k448](https://huggingface.co/lee-chang-93/Qwen3.8-Flash-Next-NVFP4-REAP-k448):
    NVFP4, keep 448, REAP on production traffic, **5 "super experts" explicitly protected**, 28 experts found
    never active. Loads on the same NVFP4 paths as the original (card names vLLM / TRT-LLM; says vision and
    MTP need specific vLLM settings). Card warns only ~48% of its calibration data was used.
- **Super Experts** ([arXiv 2507.23279](https://arxiv.org/abs/2507.23279)): a tiny set of experts produce the
  extreme activation outliers that attention sinks depend on. Pruning just three of 6,144 experts made
  Qwen3-30B-A3B produce repetitive, useless output. Any pruning manifest must protect them; frequency- or
  saliency-only rules can miss them.
- **Not All Experts are Equal** (ACL 2024, [arXiv 2402.14800](https://arxiv.org/abs/2402.14800)): early
  task-agnostic / task-specific expert pruning plus dynamic skipping; the origin of "calibrate on your task."
- **AIMER** ([arXiv 2603.18492](https://arxiv.org/pdf/2603.18492)): calibration-free task-agnostic pruning.
  Listed for completeness; not read in depth.

### 3.2 Expert merging

- **MC-SMoE / M-SMoE** (ICLR 2024, [arXiv 2310.01334](https://arxiv.org/abs/2310.01334),
  [code](https://github.com/UNITES-Lab/MC-SMoE)): group experts around dominant ones by routing policy,
  frequency-weighted average, then low-rank compress.
- **HC-SMoE** (ICML 2025, [arXiv 2410.08589](https://arxiv.org/abs/2410.08589),
  [code](https://github.com/wazenmai/HC-SMoE)): hierarchical clustering on expert outputs, then merge; up to
  50% fewer experts retraining-free.
- **Verdict for us:** REAP's analysis shows merging collapses the router's input-dependent control (late-layer
  output spread shrinks up to 100× in many-expert models) and loses to pruning on *generation*. We generate
  long reasoning; skip merging.

### 3.3 Fewer active experts per token

- **Training-free halving of activated experts** ([arXiv 2609.04575](https://arxiv.org/html/2609.04575v1)).
  Most relevant finding: naively lowering top-k and renormalising the gate weights over the fewer experts
  over-amplifies the expert branch ("gain miscalibration"). Fix: activate k₁ experts but normalise by the
  probability mass of a wider top-k₂. On Qwen3.5-397B-A17B (512 experts, trained top-10 — the same shape as
  Flash-Next), k 10→5: naive −2.10 MMLU points (significant), fixed −0.55 (not significant). On
  Qwen3.6-35B-A3B k 8→4: naive −4.65, fixed −0.35. Routed-expert compute halves; end-to-end ≈17% faster per
  token; memory unchanged. **Caveats: 2k-token context only, no agentic or tool tasks, and the
  perplexity-best k₂ was significantly worse on MMLU than the MMLU-best k₂** — tune on the task, not on loss.
- **ACE — calibration-free expert skipping** ([arXiv 2609.05228](https://arxiv.org/html/2609.05228)):
  per-token skip of low-contribution expert slots, always keeps the top-1; at 50–60% skipping beats prior
  dynamic methods; measured 1.41× per-output-token speedup at batch 1 on A100. Batch-1 speedups may not
  survive 16-way batched serving.
- **LExI** ([arXiv 2509.02753](https://arxiv.org/abs/2509.02753)): data-free per-layer active-expert counts
  from weights alone; claims same throughput as expert pruning with ~10% better accuracy on Qwen1.5-MoE.
- **Dynamic/zero-expert routing** (ZEDA, reported in search results on Qwen3-30B-A3B and GLM-4.7-Flash:
  ~half of expert activations replaced by zero experts, ~1.2× end-to-end) — not verified against the source.

### 3.4 Qwen3-Next / Flash-Next specifics

Flash-Next has a shared expert on every MoE layer (640 wide, BF16, from Son's teacher-student plan on the
ceiling-run branch) plus 512 NVFP4 routed experts, top-10. The shared expert is never pruned by REAP-style
methods, which is a safety net: every token still gets the dense path. No paper I found evaluates pruning or
top-k reduction on Qwen3-Next-family models in long-context agentic or vision settings.

## 4. What matters for ARC-3

- **Our regime is untested by the literature.** Every result above is on short-context text benchmarks
  (HumanEval, MMLU, GSM8K, SWE-Bench at most). ARC-3 turns are long agentic transcripts: system prompt,
  board state, thinking, Python tool calls, tool results, at 79k–103k context, sometimes with images.
- **Calibration domain decides the outcome** (REAP's C4 collapse). A manifest calibrated on agentic coding
  (the public 384 build) is *close* to our distribution (we play by writing Python) but not the same; the
  grid-perception and game-rule text is not represented. That argues for an ARC-trace-calibrated manifest.
- **Vision and tool path risk.** Experts that fire mainly on image tokens or on the tool-call syntax could be
  rare in text calibration and get cut. The public REAP-384 card evaluated text only. Hard games (our "hard
  seven") are where a subtle loss would show first; pruned 16×103k hard-7 moved 3.3 → 5.0, so no sign of harm
  yet, but that is one run.
- **Calibration data we already have:**
  - Son's run store holds per-turn step files with the full reconstructed transcript per turn (system prompt,
    user prompt, thinking, tool call, tool result). Flagged "input not exact" (reconstructed from prior-step
    transcripts), which is fine for saliency statistics. This is the best corpus: it is exactly what the model
    sees and writes.
  - Local Kaggle outputs (bubba-workspace/arc3-kaggle, several hundred game-plays of event logs) are mostly
    board/action state, not token text — useful to pick *which* games/turns, not as calibration text by itself.
  - **Held-out games must be filtered out before any calibration or tuning:** vc33, ar25, sb26, re86, su15,
    tr87, tu93, as66. Locally they are a small slice (a couple of plays each, tr87 nine); the bulk (tn36,
    sk48, g50t, bp35, ls20, lf52, wa30, …) remains. On Son's suite runs the held-out games are in every
    all-25 run, so filter by game id per step file.

## 5. Next experiments, ranked

1. **Replicate pruned 16×103k and put it on Kaggle with startup kit v5** (Son's proposed next kernel).
   Payoff: highest — it is the only lever with a measured big gain. Cost: one GCP replicate (Son) plus one
   Kaggle run; needs the pruned NVFP4 checkpoint uploaded as a Kaggle dataset first (none exists yet).
   Blocker: the kept-expert manifest must be known and fixed so Kaggle runs the same model Son tested.
2. **ARC-trace-calibrated REAP manifest vs Son's manifest, same 16×103k shape.** Run REAP saliency over
   several thousand non-held-out step transcripts (text; include image turns if the harness sends them),
   protect super experts, keep 384. Compare on the hard seven and all-25. Payoff: medium-high if Son's
   manifest came from generic or coding data; it may also allow a deeper cut safely. Cost: the saliency pass
   needs the full BF16 or NVFP4 model resident with router/expert hooks — an 8-GPU or big-GPU GCP job (Son),
   not Kaggle. Scoring the result can run on Kaggle.
3. **Prune-ratio sweep at the 16–19 game shape** (keep 448 / 384 / 320). Son's chart: 34% pruned at 28×57k
   scored 28.7, but that confounds prune depth with shorter context. Hold games×context fixed and vary only
   the prune to see where quality breaks. Cost: three GCP suite runs; Kaggle only for the winner.
4. **Lower top-k with corrected normalisation (k 10 → 6–8, normalise over top-10 mass) on top of pruning.**
   Payoff: speed (more turns per game in the time limit), no memory change; the paper's 512-expert top-10
   model lost nothing significant at half k on short tasks. Cost: low compute, but **it is a code patch, not a
   config flip** — editing the experts-per-token setting gives the naive renormalisation the paper shows is
   harmful; the router in Son's patched SGLang needs a separate normalisation width (not checked whether it
   already has one). Must be tested on long agentic games, where the paper has no evidence. GCP first.
5. **Skip:** expert merging (loses to pruning on generation; adds a new checkpoint format), and more
   prompt/sampling tweaks on J' (Son found no gain).

**Kaggle vs GCP.** Kaggle's weekly GPU budget fits scoring runs of a finished checkpoint (items 1, and the
winners of 2–4). Building manifests (item 2), ratio sweeps (3) and the router patch shake-out (4) belong on
Son's GCP. Nothing here should touch Jethro or Son's machines from our side.

## 6. Open questions for Son

- Which experts did you cut, and on what traffic was the ranking computed? (Manifest file, please.)
- Were super experts / the MTP drafter / vision path checked?
- Is the 7-game pruned 19.7 vs J' 21.4 within run-to-run noise on your suite?
