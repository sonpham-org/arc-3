# Astra trace and Qwen context audit

The initial replay review was completed on 5 September 2026. The linked 6 September execution checkpoint adds separately identified live inference experiments, score collections, and CPU-cache diagnostics; it does not change the competition harness.

- [Public replay audit](trace-review.md): matched Astra runs, token counters, retained state, and transfer limits.
- [Confidence and memory options](context-memory-options.md): overgeneralization, Qwen3.8-27B, quantization, expert offload, and bounded experiments.
- [Replay measurements](replay-metrics.json): exposed usage counters, public recording URLs, and SHA-256 hashes for five recordings.
- [6 September execution checkpoint](execution-checkpoint-20260906/README.md): final ten-arm context matrix, score-27.66 result, CPU KV resume audit, layer-trace diagnosis, and sanitized reproducibility bundle.

The strongest working hypothesis is that a durable, compact game model lets the agent reason less during predictable execution. The replays do not isolate this effect from model capability, context management, or other harness differences, and do not establish a Qwen score improvement.

The operating constraints remain one RTX PRO 6000, the existing main-model allocation, and approximately 2.7M generated tokens across 25 games (108k/game advisory target). The public games are development evidence, not proof of generalization to unseen competition games. New gameplay comparisons should continue to use the verified baseline lineage and preserve the exact model, prompt, and resource identities needed for a fair arm comparison.

## Provenance and reproduction

The original documentation branch started from arc-3 commit `afc3de7`; the execution checkpoint was merged forward with the current default branch before publication. The checkpoint labels saved-artifact analysis separately from fresh 6 September live observations.

For each recording in `replay-metrics.json`, retrieve `recording_url` and check the SHA-256 of its raw response bytes. The response is newline-delimited JSON. For each row, parse `data.action_input.reasoning` when it is a JSON string, then sum the exposed `usage` counters once. `output_tokens` already includes `output_tokens_details.reasoning_tokens`; do not add those together. RESET records count when usage exists. WA30 Standard has one RESET without usage, so its sum is explicitly a logged-token total.

Public decision notes and occasional reasoning summaries are available; complete encrypted reasoning and compaction state are not. Source recordings and downloaded source snapshots remain in the originating local task workspace, outside this repository. The small measurement file preserves their URLs and hashes; raw frames, third-party source copies, and transcripts are not bundled here.

Read public mechanics as examples of representation and hypothesis testing. Do not feed game-specific solutions into an evaluation prompt or use these few games as the only acceptance set.
