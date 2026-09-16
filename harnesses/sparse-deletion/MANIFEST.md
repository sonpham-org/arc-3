<!--
Author: Claude Opus 5 (Bubba)
Date: 12-September-2026
PURPOSE: Registry entry for the sparse-deletion prompt arm — what it derives from, the
exact diff, the run shape, and the pre-registered prediction. Deliberately records the
deviation from the house ex-ft09 metric so it is a stated choice, not a later surprise.
SRP/DRY check: Pass — the harnesses/README.md rules require one MANIFEST per variant;
this is that file for this variant and duplicates no other.
-->

# sparse-deletion — prompt arm

## Derives from
`keithtyser/duck-qwen38-nvfp4-mtp-vllm-smoke-v1` (the duck harness bundle that the
community RTX PRO 6000 notebook runs), **not** `baseline-v12`. Reason: that bundle is the
one that reaches the RTX PRO 6000 with Qwen3.8-Flash-Next-NVFP4, and its `preamble.txt`
shows the solver is `HarnessSolver(label='duck-harness')` over our own
`src/ARC3-Inference` tree — so our `inference/agent/prompts.py` **is** its live prompt
source. Verified by grep before anything was built: the duck bundle's `prompts.py`
carries the literal `DON'T DO THIS!` paragraph.

Published arm bundle: `markbarney/taaf-duck-sparse-deletion` (private).

## The diff — deletion only, nothing added
Serving stack, model, runtime, solver loop, and scorer are byte-identical. The assembled
system prompt goes **12,358 → 11,668 chars** (−690, −5.6%):

1. the `"long horizontal or vertical line near an edge is a timer or remaining-steps bar
   ... do not get distracted by it"` paragraph — **deleted**
2. the `"segmented edge bar ... classify it as HUD/timer state ... DON'T DO THIS!"`
   paragraph — **deleted**
3. `"64 x 64"` struck from the board-size line (the ARC-symbol rendering fact is kept)
4. the word `"puzzle"` struck from the framing, in `prompts.py` and in
   `tool_agent._build_system_prompt`'s opener

Patches in `patch/`. Why deletion and not a better-worded rule: a substitute rule is
still a claim, and any claim is wrong on the games it does not cover — 21 of 25 games
spend a move budget, so "the bar is your budget" would be a false prior on four of them.
This arm is strictly shorter than the control and asserts nothing new, so it cannot be
wrong on a game it does not apply to.

## Why these four
Measured against all 25 public game sources, not inferred from traces:
- only **13 of 25** declare 64×64 at every level; `bp35` and `lf52` are 8×8 upscaled, and
  seven games change grid size between levels
- `sk48` puts four long segmented strips on screen; one is the rod (the whole mechanic),
  one is the goal spec, one is a click target for switching skewers. The HUD rule fires
  on all of them
- **21 of 25** games decrement a move budget and `lose()` at zero — the bar the prompt
  tells the agent to look away from is the loss condition
- "puzzle" has no word for carried state, a world bigger than the view, or a solved thing
  coming un-solved. All three are already true of games we lose

## Run shape
7 lanes × 4 passes in one 132-minute job. `max_runtime_s_per_game=2061` (34m21s),
`target.max_runtime_s=7920`, `concurrency=7` so the four passes run as sequential waves.
`diagnostics._run_pass_stats` only yields σ/SEM at `n_passes ≥ 2`, so 4 is what kills a
fluke score.

**Lanes (the bottom seven, by mean score across the 163 FlashNext runs):**
`sk48` 0.40 · `bp35` 1.03 · `ls20` 2.41 · `g50t` 2.46 · `lf52` 2.46 · `wa30` 2.97 ·
`tn36` 4.15.

## Metric deviation — stated on purpose
`harnesses/README.md` says score on ex-`ft09` all-25. This experiment does **not**: it
scores the bottom seven only, because the prediction is about those games specifically
and an all-25 average would dilute a real effect below the noise floor. `ft09` is not in
the lane set at all. The null-check job (`job3`) covers `cd82`/`lp85`/`sb26` plus four
mid games, which is where an all-25-style regression would show up.

## Pre-registered prediction (written before any arm ran)
The gain lands in the bottom seven; `cd82`, `lp85`, and `sb26` do not move. If the
average rises but the bottom seven do not, that is noise and it gets called noise.

## Provenance guard
Every arm's log carries, before a single game is played: `nvidia-smi`, the `prompts.py`
SHA-256, and the length + SHA-256 of the **assembled** system prompt, plus a hard assert
that the arm's probe strings are present (control) or absent (deletion). Confirmed
locally first — control `5d6b0afd…` with all four probes present, arm `fae0af40…` with
all four absent. A prompt A/B that never confirms the text changed in the running process
is the same mistake as trusting a requested accelerator.

## Score
Pending — job 0 (smoke) queued 12-Sep-2026 16:4x ET.
