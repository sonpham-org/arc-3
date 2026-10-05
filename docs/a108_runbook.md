# a108 Duck Harness Runbook

This workspace contains a Tufa Duck Harness-style ARC-AGI-3 runner adapted for
local a108 / DGX Spark experiments.

## Layout

- `ARC3-Inference/`: solver, prompts, Python tool sandbox, local vLLM server
  wrapper, viewer, scoring tools.
- `tufa-arc-agi-framework/`: TAAF game/benchmark/deployment framework.
- `ARC3-Inference/configs/a108.qwen36.json`: conservative local Qwen 3.6
  config for a108.
- `ARC3-Inference/configs/a108.qwen36.safe.json`: safer first-run FP8 config
  with prefix caching disabled and vLLM eager mode enabled.
- `ARC3-Inference/configs/a108.qwen36.nvfp4.json`: alternate Qwen 3.6 NVFP4
  config for GB10/Spark testing.
- `docs/tufa_duck_harness_a108_audit.md`: code audit and design notes.

The upstream `example-run/` directory was not imported because it is about
2.8 GB. Pull it separately only if we need the full Tufa trace corpus locally.

## Current Status (5-Oct-2026)

a108 (Cletus) is back up. It went dark 28-Sep-2026 ~21:05 ET with no clean shutdown
(the NVIDIA driver logged out-of-memory and RAM jumped to ~105 GB minutes before; cause
unproven: power supply or a hard freeze under load). Son brought it back 5-Oct-2026
~00:57 ET, and 01:30-02:03 ET it got the full NVIDIA update:

- DGX OS 7.2.3 -> 7.6.0 (OTA meta 26.09.2)
- kernel 6.17.0-1014 -> 7.0.0-1019-nvidia
- driver 580.126.09 -> 580.178.04
- BIOS GX10DGX.0103.2026.0129 -> 0105.2026.0505, EC 0x02000004 -> 0x02000006,
  UEFI 0x03000007 / 0x00000516

Files, home dir and docker images were untouched; stable since. Log on the box:
`/home/son/update-logs/2026-10-05-update.log`.

a424 (Jethro) is **not** updated (still 7.2.3 / 580.126.09 / old BIOS) because it is
serving a live ARC vLLM container.

**Two-box tensor-parallel runs cannot work yet.** The 200G direct cable between a108 and
a424 is not connected: a424's ConnectX ports show no carrier, and on a108 the new
`dgx-spark-mlnx-hotplug` package powers the ConnectX card off entirely when no cable is
present (it does not show in `lspci`). The NVIDIA Spark Mellanox firmware manager will also
want to update the ConnectX firmware once a cable is connected. Both boxes talk over Wi-Fi
only.

## Hardware Check

From a machine with Tailscale access to the DGX Spark:

```bash
make check-workspace
make a108-check-ssh
make a108-sync
make a108-check-env
```

For a full sync/install/server/smoke run with logs:

```bash
make a108-bootstrap-report
```

This stops on the first failing step and writes logs to
`reports/a108/<timestamp>/`.

The root Makefile defaults to the Tailnet FQDN used by the sibling
`autoresearch-arena` repo:

```bash
A108_HOST=gx10-a108.tail57a229.ts.net
A108_ROOT=$HOME/GitHub/arc-3
```

Override those if your SSH alias or target path differs:

```bash
make a108-sync A108_HOST=user@host A108_ROOT=/data/arc-3
```

## First-Time Setup on a108

From the local workspace:

```bash
make a108-install
make a108-download-model A108_CONFIG=configs/a108.qwen36.safe.json
```

Or directly on a108:

```bash
cd /path/to/arc-3/ARC3-Inference
CONFIG_PATH=configs/a108.qwen36.json make install-a108
CONFIG_PATH=configs/a108.qwen36.safe.json make download-model
```

`install-a108` installs base locked project dependencies, installs the local
editable TAAF checkout, then installs vLLM with:

```bash
uv pip install --python .venv/bin/python -U vllm --torch-backend=auto
```

That avoids the upstream x86_64-only vLLM wheel URL in the generic `server`
extra.

The first Qwen3.6 FP8 run needs to fetch many safetensor shards. Pre-caching
with `make download-model` keeps the GPU free and gives visible Hugging Face
download progress instead of hiding the transfer inside vLLM startup.

## Start the Model Server

From the local workspace:

```bash
make a108-server
```

For the first a108 run, prefer the safer profile:

```bash
make a108-server A108_CONFIG=configs/a108.qwen36.safe.json A108_SERVER_TAIL_ON_WAIT=false
```

Or directly on a108:

```bash
cd /path/to/arc-3/ARC3-Inference
CONFIG_PATH=configs/a108.qwen36.json make server
```

The safe config keeps the same model and Qwen tool/reasoning parser but sets:

- `server.enable_prefix_caching=false`
- `server.extra_args=--enforce-eager`
- `environment.concurrent_jobs=1`
- `environment.environments_dir=/home/son/GitHub/arc-agi-3/environment_files`
- `VLLM_USE_DEEP_GEMM=0` from the Makefile server environment
- `analyzer.thinking=false` so Qwen emits native OpenAI tool calls instead of
  reasoning text without a tool call

After chat/tool/game smoke tests pass, re-enable prefix caching and compiled
execution only if startup and generation are stable on the installed vLLM build.

Useful logs and state:

- Server log: `.cache/arc3_runtime/arc3-inference-server.log` unless `/shared`
  exists, in which case caches move under `/shared/$USER/arc3_runtime`.
- API key: `.cache/arc3_runtime/server-api-key` or the matching `/shared`
  path.
- Health endpoint: `http://127.0.0.1:1234/v1/models`.

From the local workspace:

```bash
make a108-check-server
make a108-tail-server
make a108-stop-server
```

## Smoke Test Chat

From the local workspace:

```bash
make a108-smoke-chat
```

Or directly on a108:

```bash
cd /path/to/arc-3/ARC3-Inference
CONFIG_PATH=configs/a108.qwen36.json make chat PROMPT="Answer in one sentence: what is 2+2?"
```

## Smoke Test Tool Calling

From the local workspace:

```bash
make a108-smoke-tool
```

Or directly on a108:

```bash
cd /path/to/arc-3/ARC3-Inference
CONFIG_PATH=configs/a108.qwen36.json make smoke-tool
```

## First Game Smoke

Start with one game and one pass:

From the local workspace:

```bash
make a108-smoke-game
```

Or directly on a108:

```bash
cd /path/to/arc-3/ARC3-Inference
CONFIG_PATH=configs/a108.qwen36.json make interactive GAME=ft09 N_PASSES=1 CONCURRENT_JOBS=1 MAX_RUNTIME_MINUTES=10 RUN_NAME=a108-smoke-ft09
```

Then score it:

```bash
make a108-score-latest
CONFIG_PATH=configs/a108.qwen36.json make score_run SCORE_RUN_DIR=runs/<run-dir>
```

Verified a108 smoke result:

- Run: `runs/20260704_210146_a108-smoke-ft09`
- Model: `Qwen/Qwen3.6-27B-FP8`
- Server: vLLM 0.24.0, `configs/a108.qwen36.safe.json`
- Result: completed end-to-end, `score=0.0`, `state=gave_up`,
  `actions=6`, `tokens=2445`
- Main bottleneck: model requests are slow enough that the 10-minute cap hit
  after two analyzer read timeouts.

## First Public Set Run

After the single-game smoke passes:

```bash
cd /path/to/arc-3/ARC3-Inference
CONFIG_PATH=configs/a108.qwen36.json make interactive RUN_NAME=a108-qwen36-public-n1
```

The config defaults to the official public set, `N_PASSES=1`, and
`CONCURRENT_JOBS=2`.

## Tuning Knobs

- Increase `CONCURRENT_JOBS` only after server stability is proven.
- Try `shared.context_window=65536` after the 32k path works.
- Try `server.gpu_memory_utilization=0.90` only after startup succeeds.
- Keep `configs/a108.qwen36.safe.json` as the known-good startup baseline.
- If FP8 is slow or fragile on GB10, test the NVFP4 config:

```bash
make a108-server A108_CONFIG=configs/a108.qwen36.nvfp4.json
```

Then run the harness with:

```bash
make a108-smoke-game A108_CONFIG=configs/a108.qwen36.nvfp4.json
```
