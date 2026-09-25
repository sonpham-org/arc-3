# lacr-serving-variants — one vLLM flag changed, harness byte-identical to LA-CR

Local controller: `D:\codex-work\lacr-serving-variants-20260923` (`derive_arm.py --variant X`, `launch.py --variant X`).
Base: `la_clean_return_a` (21-Sep; 18.01 / 19.24 on all 25 at 132 min).

| variant | what | result |
|---|---|---|
| batched16k | `--max-num-batched-tokens 16384` | 16.63 (no effect) |
| effort_medium | `reasoning_effort=medium` (no thinking sentence) | 8.39 |
| effort_high | served template copy, milder xhigh sentence | 10.85 / 15.14 (25-Sep) |
| xxhigh | served template, xhigh sentence + reflect-before-acting | 13.63 |
| nopreserve | `preserve_thinking=false` | 2.68 (collapse) |
| spec (MTP k=1) | profiler leaves 8.6 GiB KV (4.5x @103k) | capacity gate failed |
| spec_ngram | n-gram drafting | 40% slower, corrupted a tool call |
| **mtp3** (25-Sep) | MTP k=3, `--kv-cache-memory-bytes` forced, batch 2048, three-rung ladder | 13.5 GiB: OOM at load; 13.0 GiB (k=3 and k=2): loads, OOM on the first request (GDN `solve_tril`) |

MTP budget on this card (vLLM dev20073, NVFP4, util 0.965): plain profile consumes 76.0 GiB and leaves 13.76 GiB of KV
(984k tokens, 9.55x of 102,985); the MTP drafter adds 5.2 GiB (81.2 GiB consumed) and leaves 8.6 GiB (463k tokens,
4.5x). Seven lanes at 103k need 721k tokens. The public single-Blackwell MTP recipe (139 tok/s single-stream, 420 tok/s
at 4 streams) holds only 9 GiB / 300k tokens of KV; it is a 1-to-4-stream configuration. MTP fits our lane count only at
7 x ~64k context, which is a different (context-pinned) arm, not a serving flag.
