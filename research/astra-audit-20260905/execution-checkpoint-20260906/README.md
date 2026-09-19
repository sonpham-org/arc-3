# ARC-3 execution checkpoint — 6 September 2026

This checkpoint preserves the final context-budget matrix, the CPU KV resume investigation, and the accounting needed to interpret earlier reference runs. Derived interactive traces for the ten matrix arms and two historical references are published on the ARC3 site and recorded under `website-publication/`. Raw source trajectories, service logs, cloud identities, and deployment state remain outside the public repository. Their immutable hashes are recorded under `provenance/`.

## Main result

The best completed arm is **43,313 context tokens per lane with 11 lanes**, scoring **27.6609712731** across all 25 games. It completed 79 levels and won three games. All ten selected matrix arms completed all 25 games with no final failure marker.

| Context/lane | Lanes | Final score | Levels | Wins | Action-attached tokens |
|---:|---:|---:|---:|---:|---:|
| 43,313 | 11 | **27.6610** | 79 | 3 | 4,565,676 |
| 102,985 | 7 | 24.6980 | 72 | 2 | 3,344,092 |
| 144,179 | 5 | 22.9610 | 71 | 1 | 2,910,041 |
| 68,063 | 7 | 21.4993 | 72 | 0 | 3,590,275 |
| 180,224 | 4 | 20.5309 | 66 | 0 | 3,021,734 |

The 21,656-context/22-lane arm scored 3.4846, but it is not a clean test of lane count. Reserving 8,192 output tokens and 512 safety tokens left only 12,952 input tokens. The arm remained active and completed the suite, so its poor score is consistent with a severe history-retention confound; the evidence does not isolate the cause.

## CPU KV resume status

The source-to-CPU-to-GPU mechanism preserved every audited checkpoint byte and semantic owner slice at 3,200, 64,000, and 129,600 cached-token boundaries. The long audit verified 387 of 387 transfer chains.

The original numerical gate failed. A live layer trace showed that resident repeats, CPU-restored repeats, and cold recomputations first diverged at `layer.3.self_attn.indexer`. The selected request metadata and PyTorch RNG fingerprints matched. At that layer the selected token-index multiset matched while its order changed. Because GPU-only resident and cold paths also failed, that experiment did not isolate CPU transfer as the cause. The deterministic ordering control and its longer-context validation are recorded under `cache-resume/`; asynchronous and gameplay validation remain separate gates.

The ordering control passed serial text CPU-resume parity at all three boundaries: **405 of 405** transfer chains and **27 of 27** resident-to-CPU prediction pairs were exact. Long cold recomputation still failed the unchanged distribution tolerance, so the conservative full probe remains red and CPU parking stays disabled for gameplay pending asynchronous, multimodal/multi-turn, throughput, and quality validation.

## Contents

- [`context-matrix/`](context-matrix/README.md): design, exact minute-132 values, final scores, and the 22-lane validity warning.
- [`cache-resume/`](cache-resume/README.md): frozen transfer instrumentation, probes, trace tooling, candidates, and sanitized findings.
- [`comparisons/`](comparisons/README.md): reference-run resource accounting and full-context cache interpretation.
- [`website-publication/`](website-publication/README.md): production trace URLs, scores, policies, and immutable publication hashes.
- [`provenance/`](provenance/): raw-artifact index and a manifest of every file in this checkpoint.

Scores use the 25-game denominator and are already on the 0–100 ARC scale. Final scores are equal-time suite outcomes, not token-matched comparisons. Action-attached token totals can omit successful responses that did not produce a later action.
