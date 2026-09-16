# Qwen3.8-27B fine-tuning: what the two Sparks actually look like, and the one blocker

**Date:** 15-September-2026
**Author:** Claude Opus 5 (Bubba)
**Directive:** Son Pham, #arc-3, 2026-09-15 21:03 EDT — remove Flash Next from the two DGX
Sparks, stand up a Qwen3.8-27B baseline on the pinned Kaggle duck harness, then SFT/RL until
held-out games improve. Companion document to the GPT Astra runbook Son attached.

Everything below was measured on the boxes at 2026-09-15 ~21:05 EDT, not read off the runbook.
Where a claim is a file read rather than a runtime observation, it says so.

---

## 1. Topology: it is one cluster, not two machines

| | a108 | a424 |
|---|---|---|
| tailnet | `100.118.4.20` (`gx10-a108`), active | `100.106.31.61` (`gx10-a424`), idle |
| GPU | 1 × NVIDIA GB10 | 1 × NVIDIA GB10 (inferred, see below) |
| my access | SSH as `son`, working | **`Permission denied (publickey,password)`** |
| disk | 916G total, 692G used, **178G free (80%)** | not measured — no access |

The vLLM serving Flash Next on a108 runs `--tensor-parallel-size 2
--distributed-executor-backend ray`, and `nvidia-smi` on a108 reports a single GB10. The ray
GCS address is `192.168.100.10:6379` — a private link network, not the tailnet. So rank 1 of
that tensor-parallel pair is on a424, which is why the directive says "2 DGX Sparks" for one
model. **Tearing down Flash Next frees both GPUs at once.** Recorded as inference from the TP
degree, the single local GPU and the private GCS address; `ray status` was not runnable
(no `ray` module on the a108 system Python).

## 2. Flash Next is idle, and Sherlock is not using it

- PID `584393`, `vllm serve /model --served-model-name RadixArk/Qwen3.8-Flash-Next-NVFP4`,
  `--max-model-len 32768 --max-num-seqs 22`, up since **Sun 13 Sep 02:37:16** (2d 18h).
- `/metrics` at the time of writing: `num_requests_running 0`, `num_requests_waiting 0`.
  Nothing is in flight; the teardown does not interrupt work.
- Weights: `~/models/Qwen3.8-Flash-Next-NVFP4` = **126G** on a108. Removing it takes a108
  from 178G free to roughly 304G free, which is what makes §4 possible.

**Sherlock does not depend on it.** `~/.hermes/config.yaml` on a108 has
`provider: "custom"`, `base_url: "http://localhost:11434/v1"`, `default: "qwen3.6:35b"` —
that is Ollama, and `:11434` is listening separately from vLLM's `:1234`. `ollama list` holds
`gpt-oss:120b`, `qwen3.6:35b`, `llama3.2:1b`. So the Flash Next removal and the Sherlock
repoint are **independent** changes; neither gates the other.

*Caveat:* that is the config file, not the effective runtime model. The hermes agent log could
not be grepped for the model actually being called. Before the weights are deleted, confirm
against the running process rather than the file.

**Unresolved and not discoverable here: what `5.6-terra` is.** The string appears nowhere in
`~/.hermes` and no such model is pulled in Ollama. This needs Son: cloud endpoint plus key, or
a local pull? If local, note that the 126G deletion is what buys the room for it.

## 3. The blocker: the 27B on disk is a serving artifact, not a training artifact

`~/models/Qwen3.8-27B-NVFP4` is present (22,568,192,096 bytes) and its `config.json` reads:

```
architectures: ["Qwen3_5ForConditionalGeneration"]   model_type: qwen3_5
quantization_config.quant_method: compressed-tensors
  group_0  weights: num_bits 8, type float, strategy channel
  group_1  weights: num_bits 4, type float, strategy tensor_group, group_size 16
```

That is **compressed-tensors NVFP4**, the format vLLM serves. The runbook's learner path is
Unsloth `FastModel.from_pretrained(..., load_in_4bit=True)`, which is **bitsandbytes NF4** — a
different 4-bit format with different quantization state. These are not interchangeable, and
the runbook's own warning ("an NF4-trained learner and a differently quantized server are not
automatically the same RL policy") is the same hazard seen from the other end.

Corroborating: `~/.cache/huggingface/hub/models--unsloth--Qwen3.8-27B-NVFP4` is **12K** — a
metadata stub with no weights. Nothing has pulled a trainable checkpoint onto this box.

**Consequence.** The learner needs the pinned upstream `Qwen/Qwen3.8-27B` at revision
`1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0` (≈54G BF16), quantized at load. 54G of download,
plus adapters, optimizer state, 50-step checkpoints and trace logs, against 178G free. **This
is the concrete reason the 126G teardown comes first, and it is a prerequisite rather than
housekeeping.**

The NVFP4 copy still earns its keep: it is the right artifact to *serve* for the §5 baseline
and for rollout collection, on one Spark, while the other trains.

**Second-order, unqualified:** Unsloth/bitsandbytes on ARM/GB10. The runbook flags it ("Spark
requires its ARM-compatible stack") and nothing here tests it. The 50–100 step qualification
on one node settles it; do not plan DDP before it passes.

## 4. The local configs do not mimic the Kaggle pins

Son asked for the Kaggle settings mirrored on tokens, context and lanes. Neither committed
config does:

| axis | `a108.qwen36.json` | `a424.qwen36.duck.json` | Kaggle pin (runbook) |
|---|---|---|---|
| model | Qwen3.6-27B-FP8 | Qwen3.6-27B-FP8 | Qwen3.8-27B (this experiment) |
| context window | 32,768 | 32,768 | **102,985** (94,281 input) |
| concurrent jobs / lanes | 2 | 25 | **7** |
| temperature | 0.6 | 0.6 | **1.0** |
| multimodal | `current_grid`, upscale 4 | `current_grid`, upscale 8, outline | `current_grid`, upscale 4 |
| request logs | off | on | **must be on, and extended** |

Two notes that matter more than the table:

1. `LOCAL_ANALYZER_CONTEXT_WINDOW` (from JSON `shared.context_window`) is the *agent's prompt
   budget* and is separate from vLLM `--max-model-len`; `kaggle.py` embeds the former and
   falls back to the latter. Both have to move, not one.
2. **7 lanes × ~103K context on one GB10 is the thing most likely to fail.** The currently
   running server is `--max-model-len 32768 --kv-cache-memory-bytes 12G --max-num-seqs 22`,
   i.e. a third of the target context. Son authorised adapting the time limit and nothing
   else, so the maximum feasible lanes × context should be **measured and reported as a
   finding**, not quietly reduced.
3. Prompt token counts must be recounted with the 27B processor and chat template. Flash Next
   counts do not transfer.

## 5. What is already verified

The duck harness pins its lineup in `ARC3-Inference/inference/framework/kaggle.py` as
`DUCK_HARNESS_PUBLIC_GAME_IDS`. Those 25 build ids are **byte-identical** to the 25 in
`datasets/decision-steps/current-builds.json`. The train/test split in
`datasets/splits/public25-train-test-split.json` is therefore a partition of exactly the games
the harness runs, and `scripts/test_train_test_split.py` asserts it — that guard fires when the
official lineup changes, which would silently invalidate any measurement taken across the split.

## 6. Order of operations

1. Confirm Sherlock's *effective* backend (process, not config), and get `5.6-terra` defined.
2. Get a424 SSH access. Item 1 cannot be completed without it: the ray worker and probably a
   weights copy live there.
3. Stop the Flash Next vLLM and its ray workers on both nodes; remove the 126G; verify free
   space on both.
4. Serve `Qwen3.8-27B-NVFP4` on one Spark at the Kaggle context. Measure max lanes × context;
   report the number.
5. Baseline the base 27B across all 25 games at the pinned settings, with the 108K
   generated-token hard cap enforced per game. This is the control; nothing downstream is
   interpretable without it.
6. **Re-check the split against the measured baseline.** If the base model scores zero on all
   seven held-out games, the test set cannot show improvement no matter what training does,
   and it must be redrawn against measured difficulty rather than human difficulty.
7. Only then: exact-response capture, dataset conversion, the 50–100 step qualification.

## 7. Open items owned by a human

- `5.6-terra`: undefined here.
- a424 credentials.
- Whether `as66` is used as a free generalisation probe. It is outside the live 25 by
  definition, so it is excluded from the split, and 15 recordings for it are already on disk —
  a never-trained-on environment at zero collection cost.
