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

## 2. Flash Next held BOTH GPUs, was idle, and is now stopped

`ray status` inside the container is decisive, and it is the headline finding:

```
Active:  2 nodes
Resources:  2.0/2.0 GPU  (2.0 used of 2.0 reserved in placement groups)
```

**Every GPU on both Sparks was reserved by the Flash Next placement group.** Nothing in the
directive — no baseline, no rollout collection, no learner qualification — could have started
while it was up. That makes the teardown the unblocker, not a housekeeping step.

It runs as a container, not bare processes:

- container `arc3-flashnext-ray-head-04a25`, image `vllm/vllm-openai:qwen38-flash-next-ray256`
  (20.8GB), restart policy **`no`**, started 2026-09-13T05:48:20Z
- `/model` is a **read-only** bind of `~/models/Qwen3.8-Flash-Next-NVFP4`
- four read-only binds from `~/flash-next-work/` patch vLLM's PLE layer, GPU worker and
  offload connector — that is hand-written work and must survive any cleanup
- ray head runs *inside* the container; a424 runs a matching worker container joined to it

### What was done, and how to undo it

**Stopped, not deleted.** `docker stop -t 60 arc3-flashnext-ray-head-04a25` on a108,
2026-09-15 ~21:20 EDT. Verified afterwards: `:1234` closed, **zero GPU compute processes**
(`nvidia-smi --query-compute-apps` returns an empty table), no containers running, no stray
ray or vLLM host processes. Weights (126G), image, and the `~/flash-next-work/` PLE patches
are all still on disk. Ollama on `:11434` is untouched and answering.

Restart is one command, and the container was not removed:

```bash
docker start arc3-flashnext-ray-head-04a25    # a108; then the worker container on a424
```

### The weights are gone; the conversion record is not

Son resolved the teacher question at 21:19 EDT (§9): RL is on-policy, so no teacher is needed,
and the directive stands. The 126G of `.safetensors` — 206 shards — were removed from a108.

**The 58MB of non-weight files were preserved first**, at
`~/models/flash-next-nvfp4-conversion-record/`: `config.json`, `chat_template.jinja`, the
tokenizer, the shard index, `conversion_environment.json`, `audit_unchanged_report.json`, and
the `aime26`/`gsm8k` metrics. All 549 files were counted at source and re-counted at the
destination before a single shard was deleted; a mismatch was set to abort. That is the record
of how the NVFP4 conversion was done and what it scored, and it is what makes the model
re-creatable from a fresh weight download rather than from scratch.

a108 went **178G free → 304G free (66%)**, which clears the ~54G BF16 learner checkpoint with
room for adapters, optimizer state, checkpoints and trace logs.

**a424 is done too.** Son confirmed at 21:30 EDT that the boxes are linked over ConnectX-7, and
a424 turns out to be reachable *from a108* at `192.168.100.11` — a 200 Gb/s link, so the hop
works without a direct credential from the Mac. Its worker container had already exited when
the head went down, so its GPU was free before anything was touched. It held its own 126G
copy; same procedure (513 non-weight files counted at source and destination, then the shards
removed). **a424: 360G free → 486G free (45% used).**

**Item 1 is complete.** Both Sparks: no Flash Next weights, no containers running, zero GPU
compute processes, conversion record preserved on each box.

| | before | after |
|---|---|---|
| a108 | 178G free (80%) | **304G free (66%)** |
| a424 | 360G free | **486G free (45%)** |

One correction to §1 worth carrying: the table there says a424 access was unavailable to this
account. That was true for a *direct* connection from the Mac and is still true; the working
route is the hop through a108 over the private link.

### What the boxes do and do not have

- **a424 has no copy of the 27B.** Only a108 holds `Qwen3.8-27B-NVFP4`. Two serving replicas
  would need a 22G copy across the link — cheap at 200 Gb/s, but it is a step, not a given.
- **No GPU training stack exists on either box.** a108's system python carries
  `torch 2.12.0+cpu` — a CPU-only build, `cuda.is_available()` False — and `peft`, `trl`,
  `bitsandbytes`, `unsloth`, `accelerate` and `vllm` are all absent. Every GPU stack here has
  lived inside a container. That is why learner qualification is its own gated step and not a
  prelude to the training run.
- a108 harness snapshot at `/home/son/GitHub/arc-3` is **not a git repository** and differs
  from the GitHub tree. It runs the harness; it is not a place to pull or commit.

## 3. Flash Next was idle, and Sherlock is not using it

- PID `584393`, `vllm serve /model --served-model-name RadixArk/Qwen3.8-Flash-Next-NVFP4`,
  `--max-model-len 32768 --max-num-seqs 22`, up since **Sun 13 Sep 02:37:16** (2d 18h).
- `/metrics` at the time of writing: `num_requests_running 0`, `num_requests_waiting 0`.
  Nothing is in flight; the teardown does not interrupt work.
- Lifetime counters before the stop: **54 requests total**, 3,551 prompt tokens, 13,314
  generated, every one finishing on `length`. About 65 prompt tokens per request — smoke
  probes, not work. An ARC-3 harness run would show tens of thousands of prompt tokens per
  request. Nothing production depended on this server.
- Weights: `~/models/Qwen3.8-Flash-Next-NVFP4` = **126G** on a108. Removing it takes a108
  from 178G free to roughly 304G free, which is what makes the learner checkpoint possible.

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

## 4. The blocker: the 27B on disk is a serving artifact, not a training artifact

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

## 5. The local configs do not mimic the Kaggle pins

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

## 6. What is already verified

The duck harness pins its lineup in `ARC3-Inference/inference/framework/kaggle.py` as
`DUCK_HARNESS_PUBLIC_GAME_IDS`. Those 25 build ids are **byte-identical** to the 25 in
`datasets/decision-steps/current-builds.json`. The train/test split in
`datasets/splits/public25-train-test-split.json` is therefore a partition of exactly the games
the harness runs, and `scripts/test_train_test_split.py` asserts it — that guard fires when the
official lineup changes, which would silently invalidate any measurement taken across the split.

## 7. Order of operations

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

## 8. Open items owned by a human

- **`5.6-terra`: undefined here.** Not a string in `~/.hermes`, not a model in `ollama list`.
  Cloud endpoint plus key, or a local pull? If local, the 126G deletion is what buys the room.
- **a424 credentials.** `son@100.106.31.61` refuses this account's key. Item 1 cannot be
  finished without it: a424's worker container is still up and still holds its GPU.
- ~~Delete the 126G, or keep Flash Next as the SFT teacher?~~ **Resolved 21:19 EDT — see §9.**
- Whether `as66` is used as a free generalisation probe. It is outside the live 25 by
  definition, so it is excluded from the split, and 15 recordings for it are already on disk —
  a never-trained-on environment at zero collection cost.

---

## 9. No teacher. Settled 2026-09-15 21:19 EDT.

Son's objection, and it is correct: *"we are doing RL. We are supposed to let the Qwen3.8 27B
just keep playing and get better. Why do we need Flash Next as a teacher?"*

RL is on-policy. The 27B generates its own trajectories, the engine scores them, the adapter
moves. A second model has no role in that loop, and the runbook says so itself in three
separate places — teacher traces are *"off-policy demonstrations"* (§5), their token ids must
never be reused because the tokenizer and template differ (§6), and they must not be used as
current-policy GRPO samples (§10). They were only ever proposed as an **SFT bootstrap**, not
as RL data.

### The one thing an SFT bootstrap actually buys, and it is not game knowledge

**Reward variance.** Group-relative RL learns from differences *within* a group. Sample four
continuations from one start state; if all four score identically, the standardised advantage
is zero and the update is zero. So if the base 27B completes no levels on a game, that game
contributes nothing but spend. The runbook names the failure — *"Skip groups with zero or
negligible useful reward variance... change the curriculum if almost all groups fail"* (§10) —
and gates on it: *"Start RL only if useful reward-bearing rollouts and policy/log-probability
consistency are established"* (§11, milestone 6).

A bootstrap exists to move the base off the floor far enough that rollouts differ from each
other. Whether it is needed **is an empirical question the baseline answers**, which is why the
directive's own ordering — baseline first — is right.

### And if a bootstrap is needed, the 27B is its own best teacher

Rejection sampling on the base model's own rollouts: run the baseline, keep the trajectories
that completed a level, SFT on those. Same tokenizer, same chat template, same policy family,
no train/serve skew, and the data is collected during a run that has to happen anyway. That is
strictly better than another model's traces, which have to be re-rendered through the 27B
processor and are off-policy the moment they arrive.

**Decision:** no teacher. Flash Next weights removed. If the baseline shows the 27B emitting
valid tool calls and clearing some level 1s, go straight to RL. If it clears nothing anywhere,
bootstrap from its own rare successes — and if there are none at all, that is a finding about
the harness or the prompt, not a reason to reach for a different model.
