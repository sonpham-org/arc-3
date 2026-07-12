# ARC-3 a108 Duck Harness

This workspace is a local recreation target for Tufa Labs' Duck Harness
ARC-AGI-3 solution, adapted for experiments on `a108` with Qwen 3.6.

Imported upstream components:

- `ARC3-Inference/`: the Duck inference harness, Python tool sandbox, prompts,
  local vLLM server wrapper, viewer, scoring, and trace tools.
- `tufa-arc-agi-framework/`: TAAF, the benchmark/game framework used by the
  harness.

Local additions:

- `ARC3-Inference/configs/a108.qwen36.json`: conservative local Qwen 3.6 config
  for a108.
- `ARC3-Inference/configs/a108.qwen36.safe.json`: verified first-run FP8
  profile for a108.
- `ARC3-Inference/configs/a108.qwen36.nvfp4.json`: alternate Qwen 3.6 NVFP4
  config for GB10/Spark testing.
- `docs/tufa_duck_harness_a108_audit.md`: implementation-oriented audit of the
  upstream harness.
- `docs/a108_runbook.md`: setup and smoke-test commands for a108.
- `docs/agent_walkthrough.md`: practical guide to the agent loop and trace
  files to study after a run.

The upstream `example-run/` directory is not included here because it is about
2.8 GB. Pull it separately if we need to mine Tufa's full trace corpus.

## Quick Start

From a machine with Tailscale access to the DGX Spark, use the root Makefile.
The default target follows the sibling `autoresearch-arena` convention:

```bash
A108_HOST=gx10-a108.tail57a229.ts.net
A108_ROOT=$HOME/GitHub/arc-3
```

```bash
make check-workspace
make a108-check-ssh
make a108-sync
make a108-check-env
make a108-install
make a108-download-model A108_CONFIG=configs/a108.qwen36.safe.json
make a108-server A108_CONFIG=configs/a108.qwen36.safe.json
make a108-smoke-chat A108_CONFIG=configs/a108.qwen36.safe.json
make a108-smoke-tool A108_CONFIG=configs/a108.qwen36.safe.json
make a108-smoke-game A108_CONFIG=configs/a108.qwen36.safe.json
make a108-score-latest A108_CONFIG=configs/a108.qwen36.safe.json
```

For the same sequence with per-step logs:

```bash
make a108-bootstrap-report
```

Reports are written under `reports/a108/<timestamp>/`.

To test the NVFP4 model instead of FP8, pass:

```bash
make a108-server A108_CONFIG=configs/a108.qwen36.nvfp4.json
```

Or, on `a108` directly:

```bash
cd ARC3-Inference
CONFIG_PATH=configs/a108.qwen36.safe.json make install-a108
CONFIG_PATH=configs/a108.qwen36.safe.json make download-model
CONFIG_PATH=configs/a108.qwen36.safe.json make server
```

Smoke test the model endpoint:

```bash
CONFIG_PATH=configs/a108.qwen36.safe.json make chat PROMPT="Answer in one sentence: what is 2+2?"
CONFIG_PATH=configs/a108.qwen36.safe.json make smoke-tool
```

Run one ARC-AGI-3 game:

```bash
CONFIG_PATH=configs/a108.qwen36.safe.json make interactive GAME=ft09 N_PASSES=1 CONCURRENT_JOBS=1 MAX_RUNTIME_MINUTES=10 RUN_NAME=a108-smoke-ft09
```

See [docs/a108_runbook.md](docs/a108_runbook.md) for the full runbook.
