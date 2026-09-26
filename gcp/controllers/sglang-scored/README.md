# SGLang-served cv5-CR scored arms (25-Sep-2026) — hand-off

**What this is.** The first *scored* ARC-3 runs served by SGLang instead of vLLM. Harness arm = compaction v5
clean-return (cv5-CR: 50% context swap with a ledger compaction, action cap 14/return, time-only guidance), the
19-Sep `compaction_v5_clean_return_a` arm byte-for-byte except the serving stack, the lane count and the context.
Son's ask: "do compaction-v5 50% swap on 5 x 96k and 7 x 66k ... Vary the time limit per game accordingly" (+ 6 x 79k).

Status 26-Sep 00:45 UTC: first wave (launched ~23:45) FAILED at the serving gate on a bad test image (the 2x2 PNG hex blob
copied from the llama.cpp arm is not a valid PNG; SGLang 400s it). Everything before the gate passed on all three VMs:
build, all 6 patches, server up, smoke test incl. a real image and LANES concurrent long prompts. Fixed (gate now sends
the smoke test's 1x1 PNG); second wave launched 00:45 UTC, all in us-east4-c:

| arm dir | harness | lanes x context | decode slots | s/game | run id |
|---|---|---|---|---|---|
| `arms/cv5cr_sgl_c96k_w5` | cv5-CR (50% swap + ledger) | 5 x 98,304 | 5 | 1584 | `g4run-cv5cr-sgl-c96k-a132-w5-20260925-18d59720ff` |
| `arms/cv5cr_sgl_c79k_w6_g1584` | cv5-CR | 6 x 80,896 | 6 | 1584 | `g4run-cv5cr-sgl-c79k-a132-w6-20260925-2331af28c1` |
| `arms/cv5cr_sgl_c66k_w7` | cv5-CR | 7 x 67,584 | 7 | 2061 | `g4run-cv5cr-sgl-c66k-a132-w7-20260925-072d7d2e45` |
| `arms/cr_sgl_c39k_w7_noswap` | CR, no compaction, no 50% swap | 7 x 39,936 | 7 | 2061 | `g4run-cr-sgl-c39k-a132-w7-noswap-20260925-2e1e728db6` |
| `arms/cr_sgl_c39k_w11_s7_g2640_noswap` | CR, no compaction, no swap | 11 in flight x 39,936 | 7 (4 parked in host RAM) | 2640 | `g4run-cr-sgl-c39k-a132-w11s7-noswap-20260925-4964653851` |

Also running from the first wave: `g4run-cv5cr-sgl-c79k-a132-w6-20260925-27d38ab99a` (europe-west1-c, 6 x 80,896, 1320 s/game,
the old gate PNG) -- it will fail at the gate the same way; ignore it.

Clock rule: 7 lanes keep the pinned 2061 s (4 waves). Otherwise game_s = 7920 / ceil(25 / lanes): 5 or 6 lanes -> 5 waves
-> 1584 s; 11 lanes -> 3 waves -> 2640 s. Son asked whether proportional scaling would be fairer for 6 lanes (the 5th wave
is one game); not changed yet.

Expected timeline per VM: boot + build ~10 min, weights ~7, MTP graph capture ~13, gate + selftests ~15, then 132 min of
play. First score curve ~45 min after launch (~01:30 UTC), finals ~3 h after launch (~03:45 UTC).

Harness variants: `ARC3_SRC=cv5cr|cr` picks the source arm (cv5-CR = compaction_v5_clean_return_a, 19-Sep; CR =
clean_return_repeat132, 17-Sep; neither has the ledger in CR). `ARC3_SWAP=0` turns the 50% half-context swap off
(env + CONFIG_FLAGS + probe asserts; the live swap gate writes a `skipped` receipt), leaving plain oldest-turn trimming at
the input budget. `ARC3_SLOTS < ARC3_LANES` = games in flight above the server's decode slots (the runner's concurrency is
LANES; SGLang `--max-running-requests` is SLOTS; the hierarchical host cache parks the rest).

Bucket: `gs://cellens-ai-artifacts/arc3-duck/<run id>/` (startup.log, v12.log, score-observer/, DONE|FAILED markers,
`sglang-serving-gate.json`, `sglang-versions.txt`, `sgl-proxy.log`). Code objects: `gs://cellens-ai-artifacts/arc3-duck/code/sglang-cv5cr-v1/`.

## Why SGLang

The fork `gabrielolympie/sglang-flashnext-sm120` (six patches on official sglang `qwen4-main-squashed`) serves
Qwen3.8-Flash-Next NVFP4 on one RTX PRO 6000 at 440-755 tok/s aggregate at the harness shape, against 270-300 on every
vLLM scored run (`gcp/controllers/sglang-flashnext/README.md` in the arc-3 repo has the 60-row sweep). Ingredients:
NEXTN MTP (3 steps / 4 draft tokens, lossless acceptance, FR-Spec 64k token map), fp8 e4m3 KV, fp8 weight copies for
the low-batch GEMMs, hierarchical host-RAM cache (64 GB) so evicted prefixes come back from RAM instead of re-prefill.

Memory rule that fixes the lane/context pairs: GPU KV pool = 520k tokens at mem-fraction 0.95 (0.965 and 0.98 OOM);
`lanes x context` must fit or running requests get retracted (p90 turn 80-90 s). 5 x 98k = 492k, 6 x 81k = 485k,
7 x 68k = 473k. Parking (games in flight > lanes) is NOT in these runs; the runner's lane model is unchanged.

## How the arm is built (`derive_sgl.py`)

`ARC3_CTX=98304 ARC3_LANES=5 python derive_sgl.py` (also `ARC3_MEMFRAC`, `ARC3_HICACHE_GB`). It starts from the cv5-CR
source arm (`D:\codex-work\compaction-v5-clean-return132-20260919\arms\compaction_v5_clean_return_a`) and, like
`lacr-mtp64k/derive_c60k_mtp.py`, moves every 102985 / 94281 / 7-lane / 2061-s pin through the whole attestation chain:
runner (+ADAPTER effective sha), runtime_probe, CONFIG_FLAGS (+config_id via contract.py), candidate FEATURE_ARM.json,
release manifest, selftest bundle (feature_contract, live_half_swap_gate), startup pins and hashes. Then it rewrites
startup.sh:

1. **vLLM container + PLE/QSA/scheduler/retention overlays -> SGLang build.** Clones sglang + fork, applies the six
   patches (all must apply), builds a venv in `nvidia/cuda:13.0.3-devel-ubuntu24.04`, `docker commit`s it as
   `arc3-sglang:built` (~8 min). Model-mirror attestation and model-info are kept (run with the host python).
2. **start_server** runs `arc3-sglang:built` as container `flashnext` (name/hostname kept for the probe and teardown)
   with `bash /sgl/serve.sh --gpu-memory-utilization 0.95 --kv-cache-dtype fp8_e4m3 --max-model-len CTX --max-num-seqs LANES`.
   The wrapper keeps vLLM's flag names because `runtime_probe.py` reads them back from `docker inspect flashnext`
   (Config.Cmd) and maps them to SGLang flags; SGLang listens on :1235. `--privileged` because Spot hosts revoked the
   container's GPU cgroup rule mid-run twice today.
3. **Shim `sgl_proxy.py` on :1234** (the URL every harness component uses): `/v1/models` gains `max_model_len`;
   `/tokenize` with messages+tools+images is answered by a 1-token chat completion and its `usage.prompt_tokens`
   (renames the vLLM alias `reasoning` back to `reasoning_content` first); `preserve_thinking: true` is injected as a
   default `chat_template_kwargs` (vLLM had `--default-chat-template-kwargs`). Everything else passes through.
4. **Serving gate** replaces the vLLM native-context capacity gate: LANES concurrent 50k-token prompts, a vision
   request, a parsed tool call, and `/tokenize == usage.prompt_tokens` on text+tools, an image, and the selftest
   fixture (4 x 1024px images + reasoning history). Report `sglang-serving-gate.json`; `PYCAPACITYFINAL` asserts it.
5. Prefix reset -> `POST /flush_cache`; vLLM metrics sampler -> generic `/metrics` sampler (`sglang-metrics.jsonl`);
   gameplay metric capture greps `^sglang:`; the 60-s watchdog (restart on 3 missed probes) is kept.

Everything the `for bad in (...)` / `for must in (...)` blocks at the end of the derive check is a real anchor that broke
at least once; do not delete an assert to make it pass.

## Launch / monitor / collect

```bash
cd D:\codex-work\sglang-scored-20260925
set CLOUDSDK_PYTHON=C:\python312\python.exe
set ARC3_ARM_NAME=cv5cr_sgl_c96k_w5
python launch_396.py --dry-run --zones us-east4-c      # contract checks only
python launch_396.py --zones us-east4-c,us-east4-b,us-east4-a,europe-west1-c,europe-west1-b
```

Timeline per VM: build ~8 min, weights ~7 min, MTP CUDA graph capture ~13 min, gates + selftests ~15 min, then 132 min
of gameplay; the startup asserts uptime < 106 min before gameplay. Live score: `score-observer/` in the bucket (the
observer under-reports late scores; the final is in v12.log / the published run). Publish with
`scripts/publish_complete_run.py` (see the scratch `publish_all.sh` pattern in the arc-3 controllers).

## Known risks (each fails at the serving gate, ~30 min in, not mid-game)

- Vision through SGLang for this model class has not been exercised (the bench only sent text); the gate's vision
  request and the selftest fixture will tell.
- `/tokenize` == `usage.prompt_tokens` relies on identical rendering of the count request and the real request;
  the shim forwards the same `chat_template_kwargs` and adds `preserve_thinking` to both.
- `tool_choice` is not sent; the tool-call check asks the model to call the tool and requires a parsed call
  (`--tool-call-parser qwen3_coder`).
- A fresh SGLang server is 20-30% slower on its first few minutes (Triton JIT per shape); the caches live under
  `/opt/arc3/sgl/cache` and survive a watchdog restart.

## Next step after these score: parking

Games in flight > lanes needs a runner change (concurrency above the lane count, per-game clock =
7920 s x games_in_flight / 25) and `--max-running-requests` = lanes; the host cache already holds 30+ games at 100k.
The sweep says 2x games over slots is the sweet spot (11 over 7: 852 tok/s at 39k; 13 over 5: 475 at 100k) and 28 in
flight collapses.
