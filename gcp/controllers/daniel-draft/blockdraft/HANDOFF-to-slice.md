# Drafter / DFlash scoping: handoff from Main innovation thread to Slice and dice the brain (4-Oct-2026)

Son, 4-Oct ~13:40 ET: "All the kernel work should belong to Slice and dice the brain." Main reads that as: serving
speed (kernels, the MTP chain drafter, block/DFlash drafters) is yours; Main keeps submissions, Kaggle packaging, run
tracking and the score site. Everything below is yours to keep, change or drop.

## Results so far (offline, held-out games, T0.6 / top-k 20 / top-p 0.95, tokens kept per check)

| job | what | block drafter w4 / w6 / w8 | chain drafter on the same rows w4 / w6 / w8 |
|---|---|---|---|
| bd3 (done, 20k steps) | 3 layers, MLP 6144, MTP-shaped 4-stream input, window 2048 | 2.45 / 2.68 / 2.77 | 3.04 / 3.76 / 4.19 |
| bd4 (20k, ~done) | same + a second capture (daniel-bench-kv4cap-1003, ~2x data), --disk | 2.58 / 2.87 / 2.98 | 3.17 / 4.04 / 4.63 |

- The block drafter is well behind the chain drafter at equal positions. Its one pass vs the chain's three (0.83 ms per
  chain step, ~1.8 ms per extra verified position at 10 lanes) does not close that gap yet.
- More data helps (+0.2 at w8 from 2x data), and the train/held-out gap is large, so it is data-hungry.
- Earlier small runs: collapsed input (mixed hidden) is weaker than the 4-stream input; context window size is irrelevant.
- bd4's game split may leak: about 47 game keys for about 25 games (image-hash keys differ across the two captures).
- Chain recipes (your lab worker, VM arc3-dlab-1004ch, results gs://cellens-ai-artifacts/arc3-duck/daniel-draft/results/daniel-draftcap-a-1002/jobs/):
  ch-base5 (tuned, 5 steps, no training) served-RS kept 3.77; ch-tvd (TV loss from stock, 3 steps) 2.82 -> 3.058 at
  step 1500 vs tuned 3.041: a small lossless gain so far. ch-deep5 and ch-experts are queued behind it.

## Machines (all on Main's tab; plans end in STOP, so each powers off after its last job)

- arc3-bdraft-1004b (us-east5-b): bd3 done -> stopping.
- arc3-bdraft-1004c (us-east5-c): bd4 at its end -> stopping.
- arc3-dlab-1004ch (us-east5-c): ch-tvd running, then ch-deep5, ch-experts, STOP.
  Plan gs://cellens-ai-artifacts/arc3-duck/daniel-draft/plans/arc3-dlab-1004ch.txt. Remove STOP to queue more.
- Block-drafter plans: gs://cellens-ai-artifacts/arc3-duck/daniel-draft/blockdraft/plans/<vm>.txt, results .../blockdraft/results/<vm>/.

## Code (D:\codex-work\daniel-draft\blockdraft\)

- train_block.py: block drafter trainer + evaluator. Same-rows chain ladder via draft_torch forward_steps with fake fp8
  KV; TV + CE loss with slot weights; --feat mtp|mixer, --disk for captures bigger than RAM. Uses the lab's
  train_draft/capture_io helpers (daniel-draft/code).
- bd_worker.sh: VM startup = your dlab_worker setup + a plan queue; metadata bd-extra-caps adds capture runs.
- make_aux_capture_cell.py: NOT LAUNCHED. Multi-depth capture: copies the stream after layers 11/23/35 (env
  ARC3_AUX_LAYERS) into one fixed GPU buffer inside Qwen4ExpModel.forward (CUDA-graph safe), and widens both V6 capture
  calls to cat(hc_47, aux) [T, 40960], so files/writer/stitcher stay unchanged and the draft still gets only hc_47. It
  builds on your make_capture_cell.py without editing it. Checked: every anchor matches once in Daniel's wheel
  (qwen4_exp.py + V6-patched eagle_worker_v2.py) and both files compile. Never run on a GPU. Before a run: 4x width
  means 4x pinned pages/prefill slots (~2 GB + ~6.7 GB) and a higher ARC3_MTP_CAPTURE_MAX_GB (builder default 330).
  Offline split: hc[:, :10240] = layer 47, hc[:, 10240*(k+1):10240*(k+2)] = layer ARC3_AUX_LAYERS[k]; train_block.py
  has no --aux input yet.
- Upstream speed-PR survey (phase 1a): D:\codex-work\flashnext-upstream-diff\REPORT.md. None of the 11 Flash-Next
  serving PRs are in Daniel's fork; first check is whether IndexShare is on for the MTP draft steps.

## Open ideas, in my order

1. Chain drafter: finish ch-tvd/deep5/experts; if TV loss holds, a TV-tuned chain drafter is a cheap lossless ship.
2. Multi-layer target features (Son's ask, DFlash/EAGLE-3 style): capture with make_aux_capture_cell.py, A/B top-only
   vs multi-layer on the same capture, for the chain drafter as well as the block drafter.
3. Block drafter: more data before more architecture; fix the game split first.
