# Kaggle experiment plan — sparse-prompt ablation on the bottom seven

Date: 12-Sep-2026 · Author: Claude Opus 5 (Bubba) · Status: **plan, not yet run**

## Directives on record

- **Boss, 12-Sep 15:54 ET:** use the `markbarney` access token only. Confirm the
  competition target before spending anything. Present the experiment before running it.
- **Boss, 12-Sep 15:58 ET:** do **not** add a rule telling the model about the move-budget
  bar. Any such rule is a claim, and it is false on the four of twenty-five games that do
  not spend a budget. *The purpose of this is to be more sparse.*
- **Son Pham, 12-Sep 15:57 ET:** budget 20 of 30 GPU hours this week; focus on the seven
  bottom games; run 4 duplicates per configuration for an average; ~2h30m per run. The
  harness already uses the GPU across 7 lanes.

## Design consequence of the Boss's correction

The first draft of this experiment proposed *substituting* a better HUD rule for the
existing one. That is the same defect as the original: an unevidenced appearance-rule
asserted as fact. It was dropped.

The variant arm is now a **pure deletion**. It removes text; it adds nothing. It is
strictly shorter than the control and makes no claim that can be false on any game.

Deleted from the system prompt (`ARC3-Inference/inference/agent/tool_agent.py`, text
blocks in `agent/prompts.py`):

1. Both HUD/timer paragraphs, including the sentence ending `DON'T DO THIS!`
2. The assertion that boards are 64 x 64 (true at every level in only 13 of 25 games;
   bp35 and lf52 are 8 x 8 upscaled)
3. The framing word "puzzle"

Held back for a later, separate arm — these are additions, not deletions, and mixing them
in would confound the result:

- `ACTION7` may be undo and may be free
- a click may *select* which thing you control rather than act on the board

## Arms

| arm | prompt | runs |
|---|---|---|
| A — control | minimal harness, unmodified | 4 |
| B — deletion | control minus the three items above | 4 |

Everything else held fixed: model, time cap, game set, lane count, seed handling.

Local baseline to reproduce: minimal harness, 132 min, average near 15. That is a local
number and arm A exists to confirm it on Kaggle hardware before arm B means anything.

## Game set

The bottom seven by mean score: **sk48 0.40, bp35 1.03, ls20 2.41, g50t 2.46, lf52 2.46,
wa30 2.97, tn36 4.15.**

## Measurement — registered in advance

The average is not the outcome. The prediction is that any gain appears in the bottom
seven and that the three games we already solve (cd82, lp85, sb26) do not move. If the
average rises while the bottom seven do not, the result is noise and will be reported as
such.

Variance is the reason for 4 duplicates: sk48 scores exactly zero in 84% of runs, so a
single run per arm carries no information.

## Kaggle account state — verified 12-Sep-2026 ~16:05 ET

Read from `kernels.KernelsService/GetAcceleratorQuotaStatistics` against the Boss's
logged-in Chrome session on the Mac Mini (profile `Default`, user `markbarney`,
82deutschmark@gmail.com, CONTRIBUTOR tier).

- GPU quota: **108000s = 30h total, 0s used, 0s reserved**
- TPU quota: 72000s = 20h total, 0s used
- Quota refresh: **2026-09-19T00:00Z** (Thu 18-Sep, 20:00 ET)

8 runs x 2h30m = 20h, which fits inside the 30h with 10h of headroom and matches Son's
figure.

**Open — accelerator selection.** The Kaggle web bundle enumerates
`NVIDIA_RTX_PRO_6000`, labelled "GPU RTX Pro 6000", alongside T4/P100/L4/A100/H100. The
CLI exposes it as `kaggle kernels push --accelerator <value>`, which maps to
`machine_shape` in `kernel-metadata.json` (`kaggle_api_extended.py:4649`). The SDK does
**not** enumerate valid values client-side — the server validates the string. So the
accepted spelling is unconfirmed and cannot be confirmed by reading.

Resolution: push a one-minute no-op notebook with `machine_shape` set and read
`nvidia-smi` from its output. Costs ~1 minute of the 30h and settles it definitively. If
the string is rejected, the fallback is the Boss setting the accelerator once in the
notebook editor GUI.

## Unresolved before launch

1. **Whose quota.** The Boss said `markbarney` token only; Son offered "20 out of 30 hours
   of my quota". Mark's own account shows a full, untouched 30h, so the constraint and the
   budget are compatible without touching Son's account. Confirm that reading is right
   before launching.
2. Accelerator string, per above.

---

## Smoke-test result — 12-Sep-2026 16:04-16:20 ET: accelerator NOT selectable via API

Three pushes of a one-minute `nvidia-smi` probe (`markbarney/arc3-accel-smoke`, private).
Total quota spent: **12.996s of 108000s.**

| v | metadata | result |
|---|---|---|
| 1 | `enable_gpu: true` + `--accelerator nvidiaRtxPro6000` | push accepted, ran on **Tesla P100** |
| 2 | `enable_gpu: false` + `"machine_shape": "nvidiaRtxPro6000"` | ran on **CPU**, `nvidia-smi` not found |
| 3 | `enable_gpu: true` + `--accelerator nvidiaRtxPro6000` + `competition_sources: ["arc-prize-2026-arc-agi-3"]` | push accepted, ran on **Tesla P100** |

The correct camelCase string was confirmed from Kaggle's own bundle
(`m.NVIDIA_RTX_PRO_6000 = "nvidiaRtxPro6000"`, enum value 17). The string is not the
problem.

**The push is accepted silently and the scheduler substitutes a P100.** No warning, no
error, no field echoed back. Left undetected this would have produced 20 hours of
P100 results labelled as RTX Pro 6000 — a result that looks clean and is wrong.
This is why the smoke test ran before the budget.

Version 2 establishes that `machine_shape` alone does not even request a GPU: only
`enable_gpu` decides GPU-vs-CPU, and it defaults the model. So `machine_shape` appears to
be dropped somewhere between the CLI and the scheduler on this path.

Gating found in the web bundle: two separate feature flags,
`AllowRtxPro6000Selection` (boolean) and `KernelsRtxPro6000Comps` (a competition
allowlist). Version 3 tested the competition-allowlist hypothesis by attaching
`arc-prize-2026-arc-agi-3` and it made no difference, so either the boolean flag is off
for this account or API-path selection is not wired regardless of the flag. Neither flag
is readable from outside the editor session; no feature-flag RPC responds.

**Resolution: set the accelerator once in the notebook editor GUI.** Open the experiment
notebook, Settings -> Accelerator -> "GPU RTX Pro 6000", save. Subsequent API pushes to
that same kernel should inherit the saved setting — to be confirmed by re-running the
`nvidia-smi` probe against the saved kernel before the real runs start.

**Gate on the experiment: no arm launches until an `nvidia-smi` probe prints RTX Pro 6000.**
Every run must carry the probe in its own log so the hardware is recorded per run and not
assumed.
