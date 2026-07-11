# Tufa Duck Harness Audit for a108

Date: 2026-07-04

## Goal

Recreate a Duck Harness-style ARC-AGI-3 solution that runs locally on `a108`
(DGX Spark / GB10-class hardware) with a Qwen 3.6 model.

## What Tufa Built

The harness is a coding-agent loop wrapped as a TAAF solver:

1. TAAF starts ARC-AGI-3 games and exposes `GameAPI` state/action execution.
2. `HarnessSolver` creates one `ToolAgent` per game run.
3. `ToolAgent` calls an OpenAI-compatible chat endpoint, normally local vLLM.
4. The only model-facing tool is `python`.
5. The Python sandbox receives structured runtime state:
   - `current_frame`
   - `previous_frame`
   - `history`
   - `transitions`
   - `last_action_result`
   - `valid_actions`
   - `action(actions)`
6. The model writes Python to inspect the board and call `action(...)`.
7. The solver records transcripts, viewer events, action traces, and scores.

Important files in upstream:

- `ARC3-Inference/inference/agent/tool_agent.py`
- `ARC3-Inference/inference/agent/python_tool_sandbox.py`
- `ARC3-Inference/inference/agent/prompts.py`
- `ARC3-Inference/inference/framework/solver.py`
- `ARC3-Inference/inference/framework/run.py`
- `ARC3-Inference/Makefile`
- `ARC3-Inference/configs/inference.json`
- `tufa-arc-agi-framework/src/taaf/benchmark.py`
- `tufa-arc-agi-framework/src/taaf/game.py`

## Core Agent Contract

The model never receives raw numeric grids as normal prompt text. Instead, the
tool runtime exposes:

- `current_frame.ascii`: letter-coded 64x64 board.
- `current_frame.segmentation`: connected components with color, shape hash,
  pixel count, boundary, children, and adjacency.
- `history` and `transitions`: action/frame history.
- `action(actions)`: executes one or more real actions.

Model-facing actions are:

- `UP`
- `DOWN`
- `LEFT`
- `RIGHT`
- `SPACE`
- `MOUSE(row=..., col=...)`

The raw engine names map through:

- `ACTION1 -> UP`
- `ACTION2 -> DOWN`
- `ACTION3 -> LEFT`
- `ACTION4 -> RIGHT`
- `ACTION5 -> SPACE`
- `ACTION6 -> MOUSE`

## What Is Worth Keeping

Keep these parts almost unchanged:

- TAAF `Benchmark` / `GameAPI` orchestration.
- `HarnessSolver` adapter.
- The Python sandbox architecture.
- The action batching and terminal-state stop logic.
- Prompt logging, transcripts, viewer data, score files.
- Per-run API key generation and server health checks.
- Tool-call recovery from XML-like markup.
- Context trimming and compact world-model carryover.

## What Needs Changing for a108

The upstream server dependency path is not Spark-ready:

- `pyproject.toml` pins a vLLM wheel URL ending in `x86_64.whl`.
- DGX Spark uses an Arm CPU, so that wheel is the wrong install artifact.
- We need an a108-specific install path using a current vLLM package/build that
  supports GB10 / Blackwell Arm.

The upstream model naming is Kaggle-shaped:

- Tufa config uses `vrfai/Qwen3.6-27B-FP8`.
- The Kaggle helper uses a Kaggle dataset mirror of that model.
- For local a108, prefer a direct Hugging Face model id:
  - `Qwen/Qwen3.6-27B-FP8` for FP8.
  - `nvidia/Qwen3.6-27B-NVFP4` or another validated NVFP4 checkpoint if GB10
    serving is more reliable/efficient.

The upstream deployment code is more than we need:

- Kaggle packaging can be ignored initially.
- Slurm local-server pooling can be ignored initially.
- Start with single-node inline execution:
  - one local vLLM server,
  - small `n_passes`,
  - low `concurrent_jobs`,
  - local run directory.

## Initial a108 Config Shape

Start with a new config, not the upstream default:

```json
{
  "shared": {
    "model_name": "Qwen/Qwen3.6-27B-FP8",
    "base_url": "http://127.0.0.1:1234/v1",
    "provider": "vllm",
    "context_window": 32768
  },
  "experiments": {
    "root_dir": "runs"
  },
  "environment": {
    "include_tags": ["official"],
    "games": [],
    "max_runtime_minutes": 20,
    "n_passes": 1,
    "concurrent_jobs": 2
  },
  "deployment": {
    "target": "inline",
    "wait": true,
    "source_repos": ["../tufa-arc-agi-framework"]
  },
  "server": {
    "backend": "vllm",
    "host": "127.0.0.1",
    "port": 1234,
    "tensor_parallel_size": 1,
    "dtype": "auto",
    "gpu_memory_utilization": 0.85,
    "trust_remote_code": true,
    "generation_config": "vllm",
    "language_model_only": false,
    "enable_prefix_caching": true,
    "tool_call_parser": "qwen3_coder",
    "reasoning_parser": "qwen3",
    "default_chat_template_kwargs": {
      "preserve_thinking": true
    }
  },
  "analyzer": {
    "thinking": true,
    "temperature": 0.6,
    "top_p": 0.95,
    "top_k": 20,
    "timeout": 120,
    "tool_steps": 0,
    "tool_timeout": 30,
    "tool_output_tokens": 1024,
    "save_request_logs": false
  },
  "multimodal": {
    "context": "current_grid",
    "upscale": 4
  }
}
```

Then tune:

- `concurrent_jobs`: start at 1-2; increase only after vLLM is stable.
- `context_window`: start at 32768; try 65536 later.
- `gpu_memory_utilization`: start below Tufa's 0.92 on Spark.
- `language_model_only`: set true only if we disable image input.
- `model_name`: try NVFP4 on GB10 if FP8 is slow or fragile.

## Implemented Workspace Setup

Implemented in this workspace:

- Imported `ARC3-Inference/` and `tufa-arc-agi-framework/` from Tufa's
  open-source harness.
- Skipped upstream `example-run/` because it is about 2.8 GB.
- Added `ARC3-Inference/configs/a108.qwen36.json`.
- Added `ARC3-Inference/configs/a108.qwen36.safe.json` for first-run a108
  startup with prefix caching disabled and `--enforce-eager`.
- Added `ARC3-Inference/configs/a108.qwen36.nvfp4.json`.
- Added `make install-a108`, selected by `server.install_target` in the a108
  config.
- Added `make download-model` / `make a108-download-model` to pre-cache Qwen
  checkpoints before starting vLLM.
- Added `make smoke-tool` to test Qwen/vLLM tool calling before running games.
- Added root-level `make a108-*` targets for SSH check, rsync, install, server,
  server lifecycle/logs, chat smoke, tool smoke, game smoke, and scoring.
- Added `scripts/check_a108_env.sh` for target-side hardware/software checks.
- Added `scripts/a108_bootstrap_report.sh` and `make a108-bootstrap-report`
  for a logged first full setup/smoke sequence.
- Added `docs/a108_runbook.md`.

## Next Milestones

1. Verify hostname/network access to `a108`.
2. Run `make a108-sync` and `make a108-check-env`.
3. Run `make a108-install` on `a108`.
4. Pre-cache the first model with
   `make a108-download-model A108_CONFIG=configs/a108.qwen36.safe.json`.
5. Start the model server with
   `make a108-server A108_CONFIG=configs/a108.qwen36.safe.json`.
6. Run server smoke tests:
   - `/v1/models`
   - simple chat
   - `make smoke-tool`
   - tool-call markup recovery
7. Run one official game, one pass, 10-20 minute cap.
8. Run the 25-game set with `n_passes=1`.
9. Compare score and transcript failures against Tufa's bundled `example-run`.

## a108 Runtime Findings

On a108, `Qwen/Qwen3.6-27B-FP8` resolves to
`Qwen3_5ForConditionalGeneration` in vLLM 0.24.0. A first attempt with prefix
caching and compiled execution reached model-load but did not bind the OpenAI
API while the model shards were still being fetched. The safer profile removes
several variables for initial validation:

- Prefix caching is disabled because vLLM marks this model's Mamba cache mode
  as experimental.
- `--enforce-eager` disables torch.compile/CUDAGraph startup work.
- `VLLM_USE_DEEP_GEMM=0` avoids a DeepGemm warmup failure observed on GB10:
  `RuntimeError: ... Unknown recipe`.
- `analyzer.thinking=false` is required for native OpenAI tool-call parsing on
  the tested Qwen3.6/vLLM stack; with thinking enabled, the model produced
  reasoning text but no parsed `tool_calls`.
- `environment.environments_dir` points at
  `/home/son/GitHub/arc-agi-3/environment_files`, because the Tufa exposition
  build rejects the old `__auto__` offline-environment sentinel.

The practical first-run workflow is to pre-cache the model with
`download-model`, then launch vLLM from a complete local Hugging Face cache.

Verified on a108:

- `make a108-check-server A108_CONFIG=configs/a108.qwen36.safe.json`: passed.
- `make a108-smoke-chat A108_CONFIG=configs/a108.qwen36.safe.json`: returned
  `2 + 2 equals 4.`
- `make a108-smoke-tool A108_CONFIG=configs/a108.qwen36.safe.json`: parsed one
  native `python` tool call.
- `make a108-smoke-game A108_CONFIG=configs/a108.qwen36.safe.json`: completed
  `ft09-0d8bbf25` end-to-end but scored `0.0` after 10 minutes
  (`state=gave_up`, `actions=6`, `tokens=2445`).

## Improvement Direction After Reproduction

High-ROI improvements:

- Add deterministic frame-diff summaries.
- Add richer segmentation features: bounding boxes, centroids, holes, symmetry,
  line/rectangle classification, stable HUD detection.
- Persist structured JSON world state instead of only text summaries.
- Mine successful traces into per-game hints/controllers.
- Add a controller cache for public games once mechanics are discovered.
- Build small deterministic solvers for games where a trace reveals the rule.

## Current Access Path

The sibling `autoresearch-arena` repo identifies the a108 Tailnet host as:

```bash
gx10-a108.tail57a229.ts.net
```

The root Makefile now defaults to that FQDN. The hardware and installed
software still need to be verified on the actual box with:

```bash
make a108-check-ssh
make a108-sync
make a108-check-env
```
