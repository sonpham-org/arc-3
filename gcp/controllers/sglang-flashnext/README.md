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

Games over slots (`results/*/slots_*.json`; 8 turns per game, +2k tokens per turn, 1.5k generated, 3 s sandbox; mem 0.95 unless
noted, GPU pool 520k tokens at 0.95 / 595k at 0.965 / 702k at 0.98; host pool 64 GB = 3.3M tokens except g22/g28 at 96 GB).
Slot count is the first token of the config name (p1/p2 = 5 slots, p1b = 8, p3 = 7 resident, pm2 = 7). 44 completed rows:

| VM | config | games | start ctx | host cache | fp8 copies | agg tok/s | median turn | p90 turn | TTFT |
|---|---|---|---|---|---|---|---|---|---|
| fp8draft | `fp8draft_g11_100k` | 11 | 100k | yes | fp8 drafter | **430** | 31.9 s | 41.6 s | 19.2 s |
| fp8draft | `fp8draft_g7_100k` | 7 | 100k | yes | fp8 drafter | **324** | 18.9 s | 91.1 s | 5.7 s |
| fp8draft | `fp8draft_g7_39k` | 7 | 39k | yes | fp8 drafter | **523** | 11.9 s | 16.3 s | 0.4 s |
| fp8draft | `fp8draft_g7_60k` | 7 | 60k | yes | fp8 drafter | **518** | 11.9 s | 24.6 s | 0.5 s |
| park1 | `p2_g12_45k` | 12 | 45k | no | on | **316** | 54.1 s | 59.2 s | 33.5 s |
| park1 | `p2_g9_30k` | 9 | 30k | no | on | **318** | 33.8 s | 60.1 s | 17.1 s |
| park1 | `p3_g7_39k` | 7 | 39k | no | on | **627** | 11.1 s | 22.4 s | 0.5 s |
| park1 | `p3_g7_60k` | 7 | 60k | no | on | **328** | 28.9 s | 38.8 s | 4.6 s |
| park2 | `p1_g12_45k` | 12 | 45k | yes | on | **619** | 24.3 s | 31.5 s | 12.8 s |
| park2 | `p1_g14_39k` | 14 | 39k | yes | on | **492** | 37.1 s | 45.2 s | 23.4 s |
| park2 | `p1_g5_39k` | 5 | 39k | yes | on | **399** | 12.2 s | 18.0 s | 0.4 s |
| park2 | `p1_g9_30k` | 9 | 30k | yes | on | **511** | 16.3 s | 60.6 s | 6.6 s |
| park2 | `p1b_g12_45k` | 12 | 45k | yes | on | **554** | 25.9 s | 36.5 s | 7.0 s |
| park2 | `p1b_g14_39k` | 14 | 39k | yes | on | **606** | 29.7 s | 38.4 s | 11.3 s |
| poolmax2 | `pm2_nofp8_g11_100k` | 11 | 100k | yes | off | **452** | 28.0 s | 40.0 s | 12.5 s |
| poolmax2 | `pm2_nofp8_g7_100k` | 7 | 100k | yes | off | **385** | 12.3 s | 92.4 s | 1.0 s |
| poolmax2 | `pm2_nofp8_g7_60k` | 7 | 60k | yes | off | **436** | 13.8 s | 30.5 s | 0.5 s |
| s5_100k | `s5_g5_100k` | 5 | 100k | yes | on | **326** | 9.6 s | 78.3 s | 0.6 s |
| s5_100k | `s5_g7_100k` | 7 | 100k | yes | on | **449** | 17.8 s | 27.9 s | 3.2 s |
| s5_100k | `s5_g9_100k` | 9 | 100k | yes | on | **431** | 26.4 s | 36.4 s | 11.1 s |
| s5_100k | `s5_g9_80k` | 9 | 80k | yes | on | **486** | 23.1 s | 29.9 s | 9.4 s |
| s5g11 | `s5_g11_100k` | 11 | 100k | yes | on | **346** | 32.5 s | 84.7 s | 18.9 s |
| s5g11 | `s5_g11_80k` | 11 | 80k | yes | on | **396** | 34.0 s | 50.5 s | 17.4 s |
| s5g11 | `s5_g13_100k` | 13 | 100k | yes | on | **475** | 35.8 s | 43.4 s | 22.5 s |
| s5g11 | `s5_g9_100k_rep` | 9 | 100k | yes | on | **446** | 24.4 s | 31.9 s | 10.5 s |
| s7_100k | `s7_g11_100k` | 11 | 100k | yes | on | **421** | 32.6 s | 41.1 s | 19.8 s |
| s7_100k | `s7_g11_80k` | 11 | 80k | yes | on | **427** | 32.3 s | 47.6 s | 14.7 s |
| s7_100k | `s7_g7_100k` | 7 | 100k | yes | on | **305** | 19.9 s | 91.2 s | 6.8 s |
| s7_100k | `s7_g9_100k` | 9 | 100k | yes | on | **437** | 25.3 s | 32.1 s | 13.0 s |
| s8 | `s8_g12_45k` | 12 | 45k | yes | on | **556** | 24.2 s | 37.1 s | 7.1 s |
| s8 | `s8_g12_60k` | 12 | 60k | yes | on | **542** | 26.1 s | 38.0 s | 8.8 s |
| s8 | `s8_g12_80k` | 12 | 80k | yes | on | **454** | 31.8 s | 44.1 s | 16.5 s |
| s8 | `s8_g8_60k` | 8 | 60k | yes | on | **495** | 11.6 s | 78.5 s | 0.8 s |
| sweep56 | `s5_g9_100k` | 9 | 100k | yes | on | **409** | 25.3 s | 34.1 s | 11.4 s |
| sweep56 | `s5_g9_60k` | 9 | 60k | yes | on | **470** | 16.5 s | 66.2 s | 6.6 s |
| sweep56 | `s5_g9_80k` | 9 | 80k | yes | on | **455** | 25.0 s | 30.1 s | 10.6 s |
| sweep56 | `s6_g10_60k` | 10 | 60k | yes | on | **541** | 21.1 s | 36.5 s | 6.8 s |
| sweep56 | `s6_g10_80k` | 10 | 80k | yes | on | **495** | 25.3 s | 33.6 s | 9.8 s |
| sweep7 | `s7_g11_100k` | 11 | 100k | yes | on | **440** | 30.7 s | 42.4 s | 18.2 s |
| sweep7 | `s7_g11_60k` | 11 | 60k | yes | on | **408** | 26.7 s | 78.2 s | 9.6 s |
| sweep7 | `s7_g11_80k` | 11 | 80k | yes | on | **484** | 28.2 s | 35.1 s | 13.0 s |
| sweep7 | `s7_g7_60k` | 7 | 60k | yes | on | **462** | 13.0 s | 27.3 s | 0.4 s |
| sweep7 | `s7_g7_80k` | 7 | 80k | yes | on | **517** | 13.1 s | 21.6 s | 0.5 s |
| sweep7 | `s7nofp8_g11_60k` | 11 | 60k | yes | off | **473** | 28.1 s | 43.0 s | 8.7 s |

Readings (25-Sep, after the 0.95 sweep):
- mem-fraction: 0.98 OOMs in CUDA graph capture; 0.965 passes health then OOMs on the first request (lazy Triton kernels) when
  the fp8 weight copies are on; 0.95 is the ceiling. fp8 copies off allows 0.965-0.98 but costs ~6% decode (462 vs 436 at 7x60k).
- The fp8 MTP drafter flag does nothing useful: the drafter loads from the NVFP4 checkpoint either way and the pool shrank to 487k.
- Pool rule: slots x (context + generation) must fit the GPU pool or the scheduler retracts running requests (p90 turn 80-90 s).
  At 100k that is 5 slots; 7 resident at 100k drops to 305-385.
- Parking (games in flight > slots) lifts aggregate 15-50% and removes the retraction tail; deeper parking keeps improving on a warm
  server (5 slots at 100k: 7 games 449, 9 games 431/446, 13 games 475). The first config on a fresh server reads 10-15% low.
- Slot count 5-8 barely matters once parked; context does: 45-60k ~540-560, 80k ~455-495, 100k ~420-475 (all vs ~290 on the vLLM
  scored runs). Host pool: 128 GB failed (the mamba component adds ~30% on top; 176 GB host), 96 GB fits.
- Parking works on this hybrid model: the hierarchical cache doubles throughput when games outnumber slots
  (316 -> 619 at 12 games over 5 slots), because a slot never idles through a game's sandbox time.
- The GPU KV pool is the wall. 7 x 39k resident fits (627); 7 x 60k plus growth overflows 520k tokens and halves (328).
- KV is cheap (~12.4 B/token, fp8), so every GB freed is ~80k tokens. Weights load at 81.4 GB (NVFP4 + ~3.6 GB fp8
  weight copies), the 48-entry mamba cache is 2.7 GB, CUDA graphs ~1.9 GB. mem 0.98 OOMs at graph capture.
- MTP drafter is bf16 ("unquant") in every run so far; an fp8 drafter and dropping the fp8 weight copies are the two
  pool levers under test (`sglang_poolmax2_startup.sh`).

Pending: the 0.965 relaunch of the 60k/80k/100k sweep, 5- and 7-slot 100k, 8-slot, and pool-max VMs.
