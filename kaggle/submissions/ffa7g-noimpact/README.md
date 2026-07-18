# ffa7g no_impact — Kaggle submission (staged, not submitted)

The statistical-band no_impact bundle (frame-full + ACTION7 + animation + goal-guidance
+ no_impact band; **no** advance_hud world model) staged for the ARC-AGI-3 competition.

- **Source dataset:** `sonphamorg/taaf-kaggle-source-ffa7g` (private) — unpacked
  `bundle-v12ffa7g.tgz` (band-only; verified: 0 `advance_hud`, has `_HousekeepingBand`).
- **Kernel:** `sonphamorg/arc3-ffa7g-no-impact` (private).
- **Datasets attached:** our source + public `driessmit1/arc3-vllm-h100-wheelhouse-v3`
  (vllm 0.19) + `driessmit1/vrfai-qwen3-6-27b-fp8-hf-snapshot` (the served model) — the
  same wheelhouse/model the bundle's setup_commands.json hardcodes.
- **Notebook:** fastcommit template; a normal commit plays offline with a ~15-min cap
  (validation only), real scoring happens on the competition rerun (`KAGGLE_IS_COMPETITION_RERUN`).

**Status:** dataset + kernel pushed private; commit run triggered. NOT submitted to the
competition — that is a manual click on a successful committed version.
