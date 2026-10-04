# RL recipe speed: rollouts and trainer (4-Oct-2026)

Author: Claude Opus 5.5 (the "concise reasoning / RL math" thread). Son, 4-Oct: "optimize the recipe to the teeth
first ... optimize both the rollout and the training so that it is as fast as possible". The RL plan and RL v2
threads were asked to hold changes to the trainer and the rollout server while this lands.

Everything here was measured on our G4 RTX PRO 6000 VMs; numbers are per GPU unless said otherwise.

## Rollouts (gcp/controllers/gtree-rollout)

| | rl2 round 2 (3-Oct) | speed1 (4-Oct) |
|---|---|---|
| server tokens generated / s | ~500 (finished tries) | ~800 (server counters, 15-min window) |
| finished tries / hour | 46 | 117 (easier nodes in this campaign) |
| lanes busy | ~64% (siblings waited for the slowest) | 12-13 of 13, nothing queued |

Changes:
- `rollout_driver.py`: a node forks each sibling when a lane comes free and gives the lane back when that sibling
  exits; while it waits for a lane the parent reaps its own finished children (no deadlock). Unstarted siblings at
  the deadline are reported as `not_started`. `serve()` restorers default `lanes // 5 + 2`. Test G in
  `test_rl_server.py` (30/30 on the old harness and on the kv4s13 harness).
- `build_rl_notebook.py`: default base = the fastest scored build `clkchk/daniel-nb/sbt06tfrskv4s13` (notebook
  e7e455081e62: 4-bit QSA KV, 13 slots, toolfast, RS); `--legacy` builds the 3-Oct one; `--set KEY=VALUE` overrides
  env after the base cell (e.g. `--lanes 16 --set ARC3_SRV_MAXREQ=16`, run speed2: 858 tok/s over 29 min vs 804,
  the server holds ~14 running with 1-2 queued; worth it, small).
- `runner/rl-vm-startup.sh`: uploads the base build's `/metrics` log (`metrics.jsonl`) with the other logs.
- Known, not fixed: coached siblings reuse only the system prompt from the warm-up request (the hybrid model can
  resume only where a recurrent state was saved, i.e. at the end of the warm-up request); stock siblings reuse it
  all. Costs ~5% on coached rounds; the server option `--mamba-radix-cache-strategy extra_buffer` (official SGLang)
  may fix it if Daniel's build has it.

## Trainer (gcp/controllers/rl)

One training step on a 115k-token record (one decoder layer of each type timed on one GPU, `bench_layers.py`;
the sum matched the real 351 s step):

| | 3-Oct | 4-Oct |
|---|---|---|
| indexed-attention layer (x12), fwd+bwd | 19.8 s | 3.8 s |
| linear-attention layer (x36), fwd+bwd | 2.5 s | 2.3 s (2.0 with the fused mix) |
| step estimate | 328 s | 129 s (about 115 s with the fused mix) |

- `qsa_kernel.py`: QSA sparse attention as fused Triton kernels (forward: online softmax over each query's own picks
  read straight from K/V; backward: dq in registers, dK/dV by atomic add). Against the gather path: output cosine
  0.999999, dq/dk/dv cosine >= 0.999994 at 4k, 32k and 115k tokens; 115k: forward 0.08 s vs 3.42 s, forward +
  backward 0.79 s vs 13.54 s (relaxed atomics for dK/dV, `ARC3_QSA_ATOMIC_SEM`; 1.12 s with Triton's default fenced
  ones). `ARC3_QSA_ATTN=kernel` (default still `gather` until the full-model check below). Every launch runs on its
  tensors' GPU (a model split over GPUs, as in check mode, hit an illegal address on cuda:0 before that).
- Selection cache: the replay in backward reuses the forward's picks (compact int16 block ids, ~120 MB per layer);
  `ARC3_QSA_SEL_VERIFY=1` recomputes and requires equality (passed). `ARC3_QSA_SEL_CACHE=0` turns it off.
- Offload copies on a side stream per GPU, the previous layer's input prefetched to ITS GPU in backward
  (`ARC3_OFFLOAD_STREAM=0` off);
  exact-size page-locked offload buffers (`ARC3_PIN_EXACT`, on): the caching allocator had rounded each 2.5 GB
  buffer to 4 GB (~192 GB per training process).
- `ARC3_HC_COMPILE=1`: the hyper-connection mix as one compiled function shared by all layers: 0.26 -> 0.13 s per mix
  at 115k, outputs within ~0.5% relative (BF16 rounding).
- Loading reads neither the BF16 routed experts nor (with the cache) the n-gram table: `ple_cache.model_view` gives
  from_pretrained a symlinked copy of the checkpoint whose index omits them (four copies loading at once had pushed
  host RAM past 600 GB and the kernel killed one).
- One copy per GPU (`--dp 4 --gpus 4`): `nvfp4_experts.py stack` writes the packed experts once (190 s); with
  `--experts-source mmap --experts-stacked DIR` every copy maps the same files (one page-cache copy) and copies each
  layer to its GPU when used. `ple_cache.py` + `--ple-cache` (n-gram embeddings per record, the table never loaded)
  exists for the 20M-base HF checkpoint (~95 GiB table); the trainer's /opt/m/bf16 table is 10M x 160 (~3.2 GB), so it
  is not needed there.
- Measured and dropped: FlexAttention (exact at 32k, but dense-equivalent and int32 overflow at 115k; guarded off),
  LoRA in BF16 (-2%), padded-bmm experts (9x slower on skewed routing; torch's grouped_mm on sm_120 is a loop of 512
  mm at ~116 TFLOPS each, close to the FLOP cost).

## Full-model results (4-GPU test VM, real records, 4-Oct)

| | 3-Oct trainer | 4-Oct trainer |
|---|---|---|
| one copy over 4 GPUs, 108k record: forward / step | 88.8 s / 287-325 s | 36.8 s / 117-134 s |
| 4 copies (one per GPU), ~115k records: per record per copy | - | 110-113 s (first record 505 s: compile + cold reads) |
| records per hour on the 4-GPU box (training step only) | ~10 | ~130 |

- Per-token log-probs of the same 108k record, gather vs kernel + fused mix: mean |dlogp| 0.039 (max 1.6; the 2-Oct fast
  path vs reference was 0.07); mean log-prob -0.1865 -> -0.1725. Same records' losses, 3-Oct trainer vs 4 copies with
  everything on: 0.0985/0.0983, 0.2938/0.2959, 0.2301/0.2308, 0.2095/0.2084. Loss falls in both check runs.
- Host RAM with 4 copies: 476 GB of 708 (each copy ~109 GB of exact-pinned layer inputs; the experts are one shared
  58 GB page-cache copy; the n-gram table is never loaded by a copy).
- Defaults now: `ARC3_QSA_ATTN=kernel`, `ARC3_HC_COMPILE=1`, selection cache on, side-stream copies on, exact pinning
  on. `ARC3_QSA_ATTN=gather ARC3_HC_COMPILE=0` gives the 3-Oct numerics back.

## How to run it (trainer box, e.g. arc3-rl-train4e)

Once per box (the stacked experts survive on the disk):

    /opt/rl/venv/bin/python nvfp4_experts.py stack --ckpt /opt/m/daniel --out /opt/m/daniel-stacked     # ~190 s

Per job: the n0 command plus four copies, mapped experts and the n-gram cache (the dense-only checkpoint view
`/opt/m/bf16-view-notable-noexperts` and the per-record n-gram embeddings are built by the job itself, first time ~5 min):

    ARC3_OFFLOAD_MIN_ELEMS=1239040000 ARC3_MOE_TOKEN_CHUNK=32768 ARC3_NVFP4_CHUNK=128     /opt/rl/venv/bin/python lora_train.py train --model /opt/m/bf16 --hf /opt/m/bf16 --nvfp4 /opt/m/daniel         --gpus 4 --dp 4 --gpu-gib 86 --experts-source mmap --experts-stacked /opt/m/daniel-stacked         --ple-cache /opt/m/work/ple/<job> --records '<records glob>' --out /opt/m/work/out/<job>         --clip 0.2 --kl 0.05 --epochs 1 --accum 4 --lr 5e-5 --warmup 2 --rank 32 --alpha 64 --max-tokens 121000 --ckpt-every 1

`--accum` is the global batch (records per optimizer step); with --dp 4 each copy takes accum // 4 of them. Each copy
peaked at ~83 GB of its GPU on 118k-token records. The trainer service's job JSON just needs this command line.

## Still open

- Kernel backward without atomics (key-centric dK/dV): ~0.5 s per indexed layer, ~5% of a step.
- A persistent Inductor/Triton cache on the trainer disk (`TORCHINDUCTOR_CACHE_DIR`, `TRITON_CACHE_DIR`) to cut the
  first record's warm-up (505 s vs 110 s) on every job.
- Pipeline (needs the RL plan thread): RL v1 records from rollout-server stock tries at frontier nodes instead of
  full-game panels; merged weights shipped as the changed tensors only (~6 GB instead of rewriting 72 GB); rollout
  servers kept alive between rounds; old log-probs from the serving engine (would drop the ~25% old-log-prob pass but
  changes the PPO reference, Son's call).
- Coached siblings' first-request cache miss (above).

## Test VMs and data

- `arc3-rlspeed-bench1` (1 GPU) and `arc3-rlspeed-dp4` (4 GPU), us-central1-c: clean Deep Learning image + a copy of
  the trainer snapshot `arc3-rl-train4-snap-20261003` as a second disk. Never boot the trainer snapshot itself: its
  hand-made systemd job service would poll the real job queue.
- Results: `gs://cellens-ai-artifacts/arc3-rl/speed/` (bench1-1004, dp4-1004); rollout campaigns speed1 / speed2
  under `gs://cellens-ai-artifacts/arc3-gtree/v1/rl/`. Work dir `D:\codex-work\rl-speed-20261004` (pre-change code
  tarballs in `baseline/`).
