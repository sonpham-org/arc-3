# SGLang serving line for Qwen3.8-Flash-Next NVFP4 (25-Sep-2026)

Measurement VMs (not scored runs) that reproduce the `gabrielolympie/sglang-flashnext-sm120` recipe on our Spot
g4-standard-48 (1x RTX PRO 6000 96 GB) with the golden-image model payload, then measure it at the ARC harness's shape.
Stack: official sglang `qwen4-main-squashed` + the fork's six sm120 patches (WY/RecoverSSM, fp8 QSA tile dequant, fp32
prefill state, low-M Triton GEMM, fp8 weight-only copies, fp8 HC/lm_head), NEXTN MTP 3 steps / 4 draft tokens,
FR-Spec 64k hot-token map, fp8 e4m3 KV, page 64, mamba `extra_buffer` radix strategy, hierarchical (host RAM) cache.
Built inside `nvidia/cuda:13.0.3-devel-ubuntu24.04`; install takes ~4 min, weight load ~7 min, CUDA graph capture ~13 min.

## Scripts
- `bench_shape.py`: warm / cached / decode / grow phases at C x P (prompt tokens), per-request usage incl. cached_tokens.
- `bench_slots.py`: N harness-like games over S decode slots (8 turns, +2k tokens per turn, 1.5k generated, 3 s sandbox).
  Aggregate generated tok/s over the whole run, turn latency (queue + prefill + decode), TTFT.
- `sglang_bench_startup.sh`: MTP lossless / no MTP / MTP relaxed 0.3 at 7x39k, 7x78k, 4x39k, 1x39k.
- `sglang_parking_startup.sh` (VM #1: no host cache 5 slots, 7 resident), `sglang_parking2_startup.sh` (VM #2: host
  cache, 5 and 8 slots), `sglang_parking3_startup.sh` (slots 7/5/6 x 60k/80k/100k + fp8 copies off),
  `sglang_park100k_s{5,7}_startup.sh` (100k resident and parked), `sglang_park_s8_startup.sh` (8 slots),
  `sglang_poolmax2_startup.sh` (fp8 weight copies off vs fp8 MTP drafter). All serve at mem-fraction 0.965 with an
  automatic retry at 0.95 (0.98 OOMs during CUDA graph capture at every slot count).

## Results so far (aggregate generated tok/s; vLLM golden profile is ~310 at 7 x 103k)

Shape benchmark (`results/results_mtp_*.json`, 2k-token decodes):

| config | 7 x 39k | 4 x 39k | 1 x 39k | 7 x 78k |
|---|---|---|---|---|
| MTP lossless | 759 (130/stream) | 738 (202) | 248-273 | collapses (pool ~520k tokens) |
| MTP relaxed 0.3 (lossy) | 994 (159) | | | |

Games over slots (`results/park1`, `results/park2`; mem 0.95, pool 520,640 tokens, host pool 3.3M tokens):

| slots | games | start ctx | host cache | agg tok/s | median turn | TTFT |
|---|---|---|---|---|---|---|
| 5 | 9 | 30k | no | 318 | 33.8 s | 17.1 s |
| 5 | 12 | 45k | no | 316 | 54.2 s | 33.5 s |
| 7 | 7 | 39k | no (resident) | **627** | 11.1 s | 0.5 s |
| 7 | 7 | 60k | no (resident) | 328 | 28.9 s | 4.6 s |
| 5 | 5 | 39k | yes (resident) | 399 | 12.3 s | 0.4 s |
| 5 | 9 | 30k | yes | 511 | 16.3 s | 6.6 s |
| 5 | 12 | 45k | yes | **619** | 24.3 s | 12.8 s |
| 5 | 14 | 39k | yes | 492 | 37.2 s | 23.4 s |
| 8 | 14 | 39k | yes | 607 | 29.7 s | 11.3 s |
| 8 | 12 | 45k | yes | 554 | 25.9 s | 7.1 s |

Readings:
- Parking works on this hybrid model: the hierarchical cache doubles throughput when games outnumber slots
  (316 -> 619 at 12 games over 5 slots), because a slot never idles through a game's sandbox time.
- The GPU KV pool is the wall. 7 x 39k resident fits (627); 7 x 60k plus growth overflows 520k tokens and halves (328).
- KV is cheap (~12.4 B/token, fp8), so every GB freed is ~80k tokens. Weights load at 81.4 GB (NVFP4 + ~3.6 GB fp8
  weight copies), the 48-entry mamba cache is 2.7 GB, CUDA graphs ~1.9 GB. mem 0.98 OOMs at graph capture.
- MTP drafter is bf16 ("unquant") in every run so far; an fp8 drafter and dropping the fp8 weight copies are the two
  pool levers under test (`sglang_poolmax2_startup.sh`).

Pending: the 0.965 relaunch of the 60k/80k/100k sweep, 5- and 7-slot 100k, 8-slot, and pool-max VMs.
