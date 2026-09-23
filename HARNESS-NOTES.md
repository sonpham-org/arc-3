<!--
Author: Claude Fable 5.1 (Dr. Fable), for Mark Barney
Date: 19-September-2026
PURPOSE: The one page an agent or a person reads first. Current recommendations for the harness,
the findings behind them, what is running, and what is open. Kept current: every write-up that
lands under docs/ updates this page the same day. Detail never lives here; every line cites the
dated write-up that owns it.
SRP/DRY check: Pass. This is an index and a recommendation sheet. CHANGELOG.md owns what changed
and when; docs/trace-findings/ own the evidence; docs/plans/ own the experiments.
-->

# ARC-3 harness notes — read this first

**Updated:** 19-Sep-2026. **Owner:** Mark Barney (Boss). **Written by:** Fable (Mark's agent).
**For:** Son Pham and any agent, local or cloud, working on the harness or the model.

How to use this page: read the recommendations, follow the citation if you want the evidence,
and post disagreement in `#arc3`. If you change the harness, the measurement rules in §2 are
the price of a claimed improvement.

---

## 1. Recommendations for the harness, in priority order

1. **Do not report a single-pass score delta as a result.** One game (`sb26`) swings the
   all-25 score by ±23 on its own, and the sd of a two-single-pass difference is ~21 points.
   Every "massive offline improvement" from one pass is inside that band until it repeats.
   → `docs/trace-findings/2026-09-17-seed-variance-and-the-sb26-jackpot.md` §3–§5

2. **Measure paired, per game, four passes, and count games improved / same / worse.** A sign
   test on 25 paired games has power; an arm total does not. Prefer low-variance proxies
   (tokens per action, actions per hour, levels per game) over final score. Report `sb26`
   on its own line or exclude it and say so.
   → same write-up, §6; driver: `ARC3-Inference/scripts/run_style_multipass.sh`,
   analysis: `ARC3-Inference/scripts/multipass_compare.py`

3. **The offline-vs-online gap is the model, not the harness arm.** On the seven games the
   27B never clears, Flash-Next clears every one at matched clock. Across Kaggle arms the
   arm labels are statistically indistinguishable; the checkpoint is separable. A harness
   change that moves these games offline on the 27B is worth a look; one that moves them on
   a different checkpoint is a model result wearing a harness label.
   → `docs/trace-findings/2026-09-17-the-slippery-seven.md` §3;
   `docs/trace-findings/2026-09-18-never-cleared-scope-and-failure-audit.md` §0.6–§0.7

4. **Delete false claims from the prompt before adding true ones.** The one prompt arm with a
   real, paired signal deleted four assertions ("puzzle", 64x64 world, HUD rule, 100% cap).
   Adding a menu of genre claims was proposed and rejected by the Boss: a wrong claim locks
   the agent into a wrong frame.
   → `harnesses/sparse-deletion/`, `docs/plans/2026-09-18-oracle-test-plan.md` §1

5. **Compact reasoning is a real efficiency win, not a score win.** Tokens per action
   874 → 595, 19 of 25 games improved, p = 0.007. Its +20 score delta was one `sb26` roll and
   is retired. Use the arm for throughput; do not cite the score.
   → `docs/compact-reasoning-style-experiment.md`;
   `docs/trace-findings/2026-09-17-seed-variance-and-the-sb26-jackpot.md` §5–§6

6. **Fix the score cap the prompt states.** The prompt tells the model the per-level cap is
   100%; the scoring code and the paper say 115%. Three caps are in use.
   → `docs/arc-agi-3-paper-reading.md` §1

7. **Every long run dies on the wall clock, not on a decision.** All audited never-cleared
   passes ended by time budget. Per-request latency (median 4–5 min at 7 lanes on a108) is
   the binding constraint on how many moves the agent gets; any harness change that lengthens
   the prompt or the reasoning costs moves. Budget it explicitly.
   → `docs/trace-findings/2026-09-18-never-cleared-scope-and-failure-audit.md` "Structural fact";
   oracle pass P2 in `docs/trace-findings/2026-09-18-oracle-relaunch-instructions.md`

## 2. What we know (each line cites its evidence)

- **Fine-tuning the 27B works and is measurable.** Round-1 LoRA adapter improves held-out loss
  on 40 of 40 records from six unseen games (t = −14.8). Small effect (~1% perplexity),
  uniform, not noise. Training-loss curves have no power to see it; held-out paired eval does.
  → `docs/trace-findings/2026-09-18-arc3-lora-round2-heldout-eval.md`
- **The competitor two points ahead says finetuning is priced out of reach. It is not, for us.**
  Two DGX Sparks, pipeline proven, rounds 1–3 complete. → seed-variance write-up §7
- **The training data:** the 27B's own winning traces (rounds 1–2) and 89 windowed human demo
  records / 2,281 turns from the Boss's play (round 3).
  → `docs/trace-findings/2026-09-18-human-demos-to-sft.md`
- **The game-mechanics corpus** (per-level rules for all 25 public games) exists in
  arc-explainer and is fetched by `tools/fetch_explainer_games.py`. It is the least-used asset
  in the project. → `docs/trace-findings/2026-09-18-state-of-play-notes.md` §1
- **No game of the 25 has never cleared a level, at any scope wider than one model on one box.**
  "Never cleared" is true only for five games under the 27B on a108. → failure audit §0.6

## 3. Running or blocked, as of 19-Sep-2026

| item | state |
|---|---|
| Oracle test (rulebook in prompt, slippery seven, 27B) | 2 control passes banked. **No valid rulebook pass**: pass 1 lost 30 of 70 requests to 900 s timeouts, pass 2 died when a108 was unplugged ~22:00 ET 18-Sep. Re-run blocked on vLLM being back up on a108. |
| LoRA round 3 (human demos, 178 steps) | **Finished** 18-Sep 22:56 ET on a424. Not yet evaluated. Next: held-out eval with `ARC3-Inference/distill/eval_lora.py`. |
| LoRA round 2 (model traces, 58 steps) | Finished. Held-out eval of round 1 published; round 2's own eval pending. |
| Compact-reasoning four-pass repeat | Passes landed; results section still pending in `docs/2026-09-18-arc3-compact-reasoning-multipass.md` §6. |
| Loop B / Loop A+B / Loop A wording arms on the **compaction-v5-clean-return** base (2 GCP runs each) | **LB and LAB done 21-Sep** (LB 12.46 / 12.22 overall, 2.82 / 2.71 hard-seven, 7 / 7 hard-seven levels — sentence retired; LAB 15.92 / 19.44 overall, 5.25 / 1.25 hard-seven, 10 / 5 levels — fails the hard-seven gate, beats both controls overall). **LA (Loop A deletions only) done 21-Sep**: 16.02 / 12.91 overall, 1.82 / 3.36 hard-seven, 6 / 8 levels (`g4run-la-v5-clean-return-{a,b}132-w7-20260921-{a6a2145506,80782fd682}`) — control-plus-a-bit, does not explain LAB's 19.44. Control: compaction-v5-clean-return pair 14.56 / 10.77. NB the spec calls this base "the 7.36 harness"; it is not — see the correction at the top of the spec and the Kaggle map below. → `docs/plans/2026-09-21-loop-b-arms-on-the-submission-harness.md` |
| Loop arms on the **shipped clean-return** base (no compaction), 2 GCP runs each | **Launched 21-Sep 21:20–23:40 ET** via `okay-bro-let-s-do-the/work/loop-clean-return132-20260921/run.py --mode {lab,la,lb}`: LAB-CR `…lab-clean-return-{b,c}132…{fe2cd50033,334f3de114}` (replicate a preempted at min 17, replaced by c), LA-CR `…la-clean-return-{a,b}132…{b4119c3bbb,45b8f4bbd8}`, LB-CR `…lb-clean-return-{a,b}132…{39cab88e84,af5db395ad}`. Controls: cap_return 15.95 / clean-return-repeat 13.58 / r3 15.65 (hard-seven 5.39 / 2.76 / 4.27). **LA-CR done 21-Sep 23:50 ET: 18.01 / 19.24 overall (hard-seven 3.53 / 3.85, 8 / 9 levels, 59 / 64 total)** — both replicates above all three controls, same per-game direction (ft09 +64, sb26 +55, ar25 +25, tr87 −44 in each); general-play gain, hard-seven flat. LAB-CR b / c **14.67 / 11.79** (hard-seven 1.51 / 3.59) — the B sentence subtracts ~5 on top of LA; **LB-CR a/b 12.03 / 14.53** (hard-seven 1.19 / 1.58, 5 / 5 levels) — the B sentence is −3 to −5 on every base it was tried on (v5, LA-v5, clean-return); retired for good. Across both bases LA is 4 runs mean 16.5 vs 5 controls mean 14.1. |
| **LA-RF** on clean-return (LA + `ARC3_PROMPT_ABLATE_TRANSITION=1` + genre reframe: system opener → "playing an interactive video game through an API", overview → genre-agnostic "Levels may be puzzles, arcade or physics challenges, navigation, or something else; do not assume the genre", orphaned "End of carried world model." line removed), 2 GCP runs | First launch (00:20 ET, `…{1fb6f2dd25,cb86cb1a03}`) **failed the on-VM `test_prompt_ablation.test_original_system_and_tool_identity` gate** (it replays the original `_build_system_prompt` from `ORIGINAL_PROMPT_SOURCE.json`; the reframe edits that literal) and self-deleted before gameplay — the local validate suite does not include that test. Fixed by carrying the same source edit into the packet snapshot via the shadow `selftest.tgz`; the 13 packet prompt tests now pass locally. **Relaunched 01:35 ET** `g4run-larf-clean-return-{a,b}132-w7-20260921-{7c94a35277,57cfed6860}` (a Spot-preempted at 01:31 during model load; replacement **c** `…525c916435` launched 02:45 ET). **Done 22-Sep ~05:00 ET: b 13.59 / c 14.90 overall (hard-seven 2.93 / 2.85, 8 / 7 levels)** — control band, −4 to −5 vs LA-CR's 18.01 / 19.24: the genre reframe + transition-coaching deletion HURT on top of the Loop A deletion. LA alone remains the best line. Launched via `loop-clean-return132-20260921/run.py --mode larf` (`rf_prompt.py`). Control: LA-CR 18.01 / 19.24. User 22-Sep: "Did we still mention ARC3 as a puzzle instead of video game? … generalize it a bit further" → "Yes, LA-RF". |
| **GLM-5.3-Flash-NVFP4 ceiling run** on the LA-CR candidate (model swap only; vLLM `glm53-flash` image, TP2, 2x RTX PRO 6000 `g4-standard-96`, `reasoning_effort=low`, parsers glm47/glm45, 7 lanes, 102985 ctx, no compaction) | Attempts 1–2 (02:10, 02:20 ET) died in startup plumbing (pip-less `uv` venv; unbound `$HOME`). **Attempt 3 (02:30, TP2) taught the real constraints**: HF download 189 GB in 3m48s (now mirrored at `model-flat/GLM-5.3-Flash-NVFP4`), vLLM `glm53-flash` (0.28.1rc1) resolves `Glm5NextForConditionalGeneration` and picks `FLASHINFER_MLA_SPARSE_SM120`, but (a) `--kv-cache-dtype fp8_e4m3` selects the `fp8_ds_mla` KV layout which asserts `pe_dim == 64` (DeepSeek-shaped) → engine-core crash on all three ladder rungs, and (b) weights take **88 GiB per card at TP2**, leaving no KV for 7×103k. **Attempt 4 (02:45 ET, `…-w4x-…-97236f051c`, TP4 on `g4-standard-192`, BF16 KV): memory fine (44.5 GiB/card) but the same crash on all rungs — the SM120 sparse-MLA backend forces the `fp8_ds_mla` KV layout regardless of `--kv-cache-dtype`, and GLM-5.3-Flash has `qk_rope_head_dim: 0` (rope-free DSA). BLOCKED UPSTREAM: vLLM issues #53963 / #55773 / #57578, open PR #55277 "Support NoPE sparse MLA (GLM-5.3-Flash) on the FlashInfer SM120 backend", open PR #54929 (Triton SM12x fallback). No released or nightly vLLM serves this model on RTX PRO 6000; SGLang's GLM-5.3-Flash work is AMD/Hopper. **Stopped at attempt 4 (03:05 ET).** Options: build vLLM from PR #55277 (hours, unreviewed), wait for merge, or use a datacenter-Blackwell/Hopper box. The other window's seven DeepSeek-V4.1-Flash 8x attempts tonight also all FAILED before gameplay, so the "better model" ceiling is open for both candidates. Launched from `D:/codex-work/glm53flash-la-clean-return132-20260922/` (`derive_arm.py` + `launch.py`, pattern from the DeepSeek derivation). Model downloaded from HF on the VM and mirrored to `model-flat/GLM-5.3-Flash-NVFP4` for reuse. Control: LA-CR 18.01 / 19.24. User 22-Sep: "you fcus on better model today" → "you can do 2 bro". Not a Kaggle candidate (needs 2 GPUs). |
| **GLM-5.3-Flash REAP50 IQ3_M (50% expert-pruned, 3-bit GGUF, `patrickbdevaney/…`) — single-GPU fit probe** | Needs a patched llama.cpp (mHC Sinkhorn op; upstream `761797ff` + the repo's 6k-line patch, audited: model code only). Probe #1 hit `unknown model architecture: glm5-next` on the stock image; #2 built fine but my `--version` check ran without `--gpus`; **#3 done 02:50 ET** (`arc3-probe-glm53-reap50-f3ca7f3966`; patched build 166 s, loads in 6 s): fits — **75.9 GB at 7×103k, 81.4 GB at 7×200k, 80.4 GB at 13×103k**; single lane 46.5 / 42.8 tok/s (4k / 60k); **7 lanes at cached 60k: 11.7 tok/s per lane, 81 aggregate**; 7×150k: 7.8 per lane, 54 aggregate; uncached prefill ~1,070 tok/s. Same llama.cpp ceiling as the Q2_0 Flash-Next probe (~80–88 aggregate at any lane count) vs vLLM Flash-Next ~46 per lane / 291 aggregate → a quarter of today's turns per game, on a 50%-pruned 3-bit model. **Single-GPU GLM route closed** unless a vLLM-servable pruned checkpoint appears. Results: `results-glm53-reap50-iq3m.json`. User: "try patrickbdevaney bro. Do it". |
| **Kaggle candidate: LA clean-return** (`kaggle-la-clean-return-20260921`, kernel `sonphamorg/arc3-flash-next-la-clean-return` v1, kernel id 135321730, dataset `arc3-la-clean-return-20260921`) | **Pushed 21-Sep 23:58 ET** for its private readiness run. Derived from the verified 7.36 kernel (351076929) with exactly the LA-CR delta: `ARC3_PROMPT_ABLATE_LOOP=1`, LA `EXPECTED_PROMPTS.json`, 2-flag `prompt_probe.py`, pinned system-prompt sha `1959faa9…`; `src/` byte-identical. config_id `08d8c44d…`. Competition submission not yet made — needs an explicit go after `verify_kaggle_readiness.py` passes. |
| GSQ-RCO Q2_0 GGUF (ISTA-DASLab) on llama.cpp — serving probe, no gameplay | **Done 21-Sep, parked.** Fits easily (7×103k: 50.6 GB; 7×200k: 62.8 GB; 13×103k: 61.2 GB on the 96 GB RTX PRO 6000) but llama.cpp does not batch decode across slots: aggregate decode ≈ 85–90 tok/s at any lane count at our context (per-lane 12 tok/s at 7×60k, 6 tok/s at 7×150k, 7 tok/s at 13×60k) vs vLLM NVFP4 ~291 aggregate / ~46 per lane. Uncached prefill 2.3–2.8k tok/s is its only win and we cache 89% of prefill. Also 2.4 bpw. Results: `D:/codex-work/gsq-rco-throughput-probe-20260921/results-*.json`. |
| **Kaggle submission → kernel map (verified 21-Sep via API)** | 7.36 (21-Sep) and 5.54 (20-Sep) are the **same** kernel version: `arc3-flash-next-clean-return-swap50` v351076929 (clean-return + search/scorer removal + 50% swap, **no compaction**). 6.49 / 5.94 / 5.02 (19 / 17 / 15-Sep) are one version of `search-scorer-swap50-ready` (349948540). 4.71 (18-Sep) `no-cap-swap50`. Compaction v5 has never been submitted. Same-code spread on Kaggle is ±0.9, so a single submission does not separate candidates. Re-derive from `competition_submissions(...).url`, never from candidate-folder order. |
| DeepSeek-V4.1-Flash ceiling run on 8x RTX PRO 6000 | **Ramped down 22-Sep (Son)** after 6 launches, 0 games: vLLM's V4.1 sparse attention is inconsistent on sm_120 (KV block 128 vs DeepGEMM 32/64, vllm#56702, closed not planned) and the community-patched path decodes at ~1 tok/s (vllm#56892). Weights load fine (EP, 38.6 GiB/GPU). Model stays staged in GCS. Revisit on H200/B200, or DeepSeek V4 Flash via ormandj's sm120 recipe. → `docs/plans/2026-09-21-deepseek-v41-flash-ceiling-run.md` |
| DeepSeek-V4.1-Flash tok/s probe (TP8) | **Moot 22-Sep**: the server does not come up on sm_120 without patches, and patched it runs eager at ~1 tok/s (vllm#56892). Scripts kept. → `gcp/launch_dsv41_flash_tps.sh` |
| **Adaptive thinking-mode router** (per-turn HIGH/MEDIUM switch when the game is settled) | **Design written 23-Sep**, nothing launched. Motivating measurement from existing runs: clean-return w7 at **264 min scores 25.07 / 7,129 actions** vs **13.6-15.7 / ~3,300 at 132 min** - time still buys score, no ceiling at 264, but **marginal** actions cost 358 each per point vs 229 inside 132 min (efficiency falls with the clock). **On the hard seven it is the reverse**: 230 marginal actions per point, and compaction-v5-CR is the most hard-seven-efficient arm (4.20 score/1k, 9.0 levels) despite being the worst overall - price the router on h7. Cost side: ~632 generated tokens per action. MEDIUM = thinking on + `max_tokens_override` + no-think retry (already expressible, no server change). Gated on a cheap MEDIUM speed check first. -> `docs/plans/2026-09-23-adaptive-thinking-mode-router.md` |
| Teacher-student RL arms (DeepSeek as explorer / judge / author; Flash-Next student) | **Plan written 22-Sep**, nothing built. **G1a done 22-Sep:** Flash-Next's attention / shared-expert / linear-attn tensors are BF16 and byte-identical between the served NVFP4 checkpoint and official BF16, so a LoRA merges in place with no requant. Next: G3 (GPU-free extractor + reward validator) and G2 (Flash-Next LoRA smoke, 8 GPUs). **Son reopened the 15-Sep no-teacher call on 22-Sep**; Arm C (DeepSeek live-play SFT cold start) is stage 1, Arm A on top. → `docs/plans/2026-09-22-teacher-student-rl-arms.md` |
| **MiMo-V2.6-Pro on 8x RTX PRO 6000 — direct agent arms** | **23-Sep:** baseline (tool agent, thinking on, DFlash) 34 actions / 1 level (lf52 L1 in 9) in 20 min; **v2 direct agent, thinking off: 3,095 actions / 0 levels** — tempo without competence. DFlash confirmed up on sm_120 (acceptance 3.2–4.3). **Overnight run launched 04:25Z**: direct agent, thinking capped 4k, batch 4, cached history, all 25 games, 132 min → `g4run-mimo26pro-direct-think4k-all25-132-20260923-v3blong`. Then decide H200/B200 per plan §2b-i. → `docs/plans/2026-09-22-teacher-student-rl-arms.md` |
| Box availability | Son said on 19-Sep the two boxes are free for others and he is moving to a 4090. **Open question: are a108 and a424 still ARC-3's?** Everything above depends on it. |

## 4. Open questions we would like answered

1. Idea or execution? The oracle test answers it, once a clean rulebook pass exists.
2. Does a mandatory first-contact probe phase (press every button once before theorising)
   move the seven? Planned, not built.
3. Does round 3's adapter (human demos) beat round 1's on held-out loss, and does any adapter
   move levels cleared in live play? Loss is a proxy; play is the metric.
4. What did Son's RL "sign of life" measure, and can it be run under the §1.2 rules?

## 5. Where things are

- Findings: `docs/trace-findings/` (dated, one question each). Plans: `docs/plans/`.
- What changed and when: `CHANGELOG.md`. Frozen baseline and every harness arm: `harnesses/README.md`.
- Runs on a108: `~/GitHub/arc-3/ARC3-Inference/runs/`. Oracle ledger: `~/arc3-oracle-20260918/guards/ledger.txt`.
- Training on a424: `~/arc3-round{1,2,3}/`.
- Team channel: Discord `#arc3`. Direction comes from there.
