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
