# a424 Study Run — Findings and Config Rationale

Date: 2026-07-11

## Why a424 and not a108

`a108` stopped checking in to the Tailnet on **2026-07-07 01:28 UTC** and has
been unreachable since. Evidence it is the box, not our network:

- Tailscale control plane: `Online: False`, `LastHandshake: never`, `RxBytes: 0`.
- `KeyExpiry: 2026-10-01` — the node key is still **valid**, so this is *not* a
  key expiry. The machine simply stopped talking.
- `gx10-a424` (different machine, same tailnet) also cannot ping it, and DNS +
  mDNS lookups fail.
- a424 has `uptime = 62 days`, so there was no shared power event on Jul 7.

Most likely: a108 is hung, powered off, or dropped its network link. It needs a
physical/console check. `gx10-a424` is the same GB10 silicon, so all findings
transfer.

## Verified on a424

The riskiest unknown — does vLLM work on the Spark's aarch64 + Blackwell stack —
is **resolved**:

```
vllm       : 0.24.0
torch      : 2.11.0+cu130
device     : NVIDIA GB10
capability : (12, 1)          # sm_121 Blackwell
gpu mem    : 130.6 GB total
```

## The a108 `ft09` run scored 0.0 — why

Recorded in `tufa_duck_harness_a108_audit.md`: `state=gave_up, actions=6,
tokens=2445` in 10 minutes. Reading the harness source, that outcome is fully
explained and is **not** an agent-logic failure.

### 1. `gave_up` is a label, not a decision

There is no give-up counter anywhere in the codebase. `taaf/game.py:596-632`
stamps `gave_up` on *any* game whose play loop exits while still `playing`. The
only stop conditions (`solver.py:249-264`) are: WIN, `stop_event`,
`max_runtime_s_per_game`, `max_actions_per_game`. The run simply hit the clock.

### 2. Throughput is the binding constraint

Qwen3.6-27B is a **dense** model (64 layers; 48 linear-attention + 16
full-attention), so decode is memory-bandwidth-bound:

    GB10 bandwidth 273 GB/s / ~28 GB of FP8 weights ~= 9.7 tok/s ceiling

Observed: `2445 tokens / 600 s = 4.1 tok/s` — about 42% of ceiling, consistent
with `--enforce-eager` (CUDA graphs disabled). The agent was starved of tokens,
not ideas. Kaggle's RTX PRO 6000 has ~6x the bandwidth *and* batches 28 games.

### 3. Four config pathologies stacked on top

| Problem | Where | Effect |
|---|---|---|
| `MAX_RUNTIME_MINUTES=10` hardcoded | root `Makefile:86` (`a108-smoke-game`) | Overrides the config's 20 min. Game dies at 10 min. |
| `analyzer.yield_seconds` = 60 | `ARC3-Inference/Makefile:155` default (unset in every config; Python default is 0/disabled) | At ~4 tok/s **every turn** hits the 60 s budget and bounces back to the solver mid-thought. Momentum is discarded continuously. |
| `analyzer.max_output: 512` | `a108.qwen36.safe.json` | Truncates the model mid-plan (~400 tokens/action observed). A truncated tool call parses as *no* tool call, costing another turn. |
| ~~`include_tags: ["official"]`~~ | ~~all three a108 configs~~ | **RETRACTED — this was not a bug.** See "Correction" below. |

## Correction (2026-07-11)

An earlier revision of this document claimed `include_tags: ["official"]` selected
zero games, on the grounds that the 25 environment files are tagged
`keyboard_click` / `click` / `keyboard` and none carry an `official` tag. That was
wrong, and setting it to `[]` is what made the 25-game launch fail with
`At least one of --game, --include-tags official, or --kaggle-duck-public-harness
is required`.

`official` is **not** matched against game metadata. It is a sentinel:
`inference/framework/run.py:118-135` maps it to the hardcoded
`DUCK_HARNESS_PUBLIC_GAME_IDS` list in `inference/framework/kaggle.py:20`, which is
exactly the 25 official games. The a108 configs were correct.

The lesson: the tag names in `metadata.json` and the tag names the CLI accepts are
different namespaces. Read the selection code, not the data.

## Config deltas: `a424.qwen36.study.json`

Derived from `a108.qwen36.safe.json` with each pathology fixed:

| Key | safe | study | Why |
|---|---|---|---|
| `environment.include_tags` | `["official"]` | `[]` | `official` matches no game. |
| `environment.max_runtime_minutes` | 20 | 90 | At ~5 tok/s, wall clock buys tokens ~linearly. 90 min ~= 25k tokens. |
| `analyzer.max_output` | 512 | 0 | 0 = no cap (server default). Matches Kaggle. |
| `analyzer.yield_seconds` | (unset -> 60) | 900 | Stop bouncing every turn. Matches Kaggle's analyzer budget. |
| `analyzer.timeout` | 120 | 900 | Kaggle uses 900. A slow model must not trip the request timeout. |
| `analyzer.save_request_logs` | false | true | We are here to *study* the trace. |

Kept deliberately conservative for the first run (revisit after it works):
`enable_prefix_caching: false`, `extra_args: --enforce-eager`,
`analyzer.thinking: false` (the audit found native tool-call parsing required it
on this Qwen3.6/vLLM stack; Kaggle runs with thinking **on**).

## Known upstream bugs worth fixing

1. **Image tokens are mis-costed.** `_estimate_tokens` (`tool_agent.py:466-471`)
   JSON-serializes the whole message list — including base64 PNG data URLs — and
   charges `len/3`. Each 256x256 grid image is billed thousands of phantom
   "tokens", and images accumulate across 30 turns of history. This forces
   aggressive premature trimming of *real* reasoning.
2. **The world model can silently freeze.** The carryover is scraped from
   assistant **text** (`_extract_scientist_note`), but both nag-followups tell the
   model "Reply with a `python` tool call only; do not write assistant text
   before it". A compliant model emits no text, so the world model stops updating
   exactly when the agent is struggling.
3. **Token accounting undercounts.** `_finish_if_needed` calls `finish_game()`
   with no args, so `final_generated_tokens=0` — every token spent after the last
   successful action is never reported.

## Speed levers on GB10 (untested, ranked)

| Lever | Expected | Notes |
|---|---|---|
| NVFP4 instead of FP8 | ~1.6x | `nvidia/Qwen3.6-27B-NVFP4` is 21.9 GB vs 36 GB. Native FP4 tensor cores on Blackwell. `a108.qwen36.nvfp4.json` already exists. |
| Drop `--enforce-eager` | +30-60% | Re-enables CUDA graphs; closes the 4.1 -> ~9 tok/s gap. |
| Speculative decoding | 1.5-2.5x | The agent re-emits near-identical Python/grids; n-gram drafting should hit often. |
| Prefix caching | large (prefill) | The harness re-sends a ~30k-token prompt every request. Disabled today because vLLM flags the hybrid/Mamba cache as experimental. |
| Concurrency | aggregate only | Per-game stays ~5 tok/s. This is why Tufa runs 28 games at once. |

## Cost of running the real thing (GCP, from the billing catalog)

`g4-standard-48` = 1x **RTX PRO 6000 Blackwell 96 GB** — the *same* GPU Kaggle uses.

| Config | $/hr | ~3 h run |
|---|---|---|
| g4-standard-48 (RTX PRO 6000) on-demand | $3.40 | $10.21 |
| g4-standard-48 **spot** | **$1.36** | **$4.08** |
| a3-highgpu-1g (H100 80 GB) on-demand | $10.98 | $32.94 |
| a3-highgpu-1g **spot** | $5.98 | $17.95 |

Quota in project `cellensml`: `NVIDIA_H100` = **8 granted**; `NVIDIA_RTX_PRO_6000`
= **no grant** (needs a quota-increase request). Kaggle remains free (30 GPU-h/week)
on the identical GPU.

## Network gotcha on a424

a424 routes all traffic over **2.4 GHz Wi-Fi** (`wlP9s9`, SSID NETGEAR88,
-60 dBm) while its wired NIC `enp1s0f0np0` is **DOWN**. Measured throughput is
0.14-1.5 MB/s from *every* source (OVH, Tele2, HuggingFace alike) — this is what
stalled the 36 GB model pull, not HF rate limiting. **Plugging in Ethernet is the
single highest-leverage fix** for iteration speed on this box.
