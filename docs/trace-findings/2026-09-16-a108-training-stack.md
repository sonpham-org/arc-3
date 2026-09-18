<!--
Author: Claude Opus 5 (Bubba sub-agent, arc3-train-stack-a108)
Date: 16-September-2026
PURPOSE: Record of the training-stack build on the DGX Spark box gx10-a108 — wheel provenance
for the CUDA-capable aarch64 torch, what was installed into /home/son/arc3-train-venv, the
proof it sees the GB10, an end-to-end LoRA SFT smoke test over the 11 decision-step v0 records,
and honest answers on 27B LoRA feasibility, NVFP4 trainability, and what a first RL loop needs.
Written while vLLM PID 765547 and the 25-lane harness were live; every constraint they impose is
recorded here so the next session does not have to re-derive them.
SRP/DRY check: Pass — sole record of this build. Does not restate SCHEMA.md (field contract) or
AGENTS.md (workspace doctrine); cites both instead.
-->

# a108 training stack — build report

**Box:** `gx10-a108`, `ssh son@100.118.4.20` · aarch64 · Ubuntu · driver 580.126.09
**GPU:** NVIDIA GB10, compute capability **sm_121** `(12, 1)` · 121G unified memory
**Venv built:** `/home/son/arc3-train-venv` (fresh, self-contained, 4.9G)
**Artifacts:** `/home/son/arc3-train-stack-setup/` (logs, converter, data, smoke output)

---

## 1. Live-job protection — status at end of work

| check | result |
|---|---|
| vLLM PID 765547 alive | **YES** — etime `16:20:36`, cmd unchanged |
| `curl http://127.0.0.1:1234/v1/models` | **401** |
| `curl http://127.0.0.1:1234/health` | **200** |
| harness PID 818305 alive | YES — etime `03:30:37`, `inference-taaf-run`, 25 lanes × 4 passes |
| live venv torch unchanged | **YES** — `ARC3-Inference/.venv/bin/python -c "import torch;print(torch.__version__)"` → `2.11.0+cu130` |
| free / disk | 113G used of 121G, 7G available · 297G free on `/` |

(All figures are the **last** observation, taken after every install and the smoke test.)

**Correction to the brief:** `/v1/models` returning 401 is *by design*, not a fault. The server
was started with an API key (the harness reads it from
`ARC3-Inference/.cache/arc3_runtime/server-api-key`). **`/health` is the correct unauthenticated
liveness probe and it returns 200.** A future session that probes `/v1/models` unauthenticated
and sees 401 must not conclude the server is down.

Nothing in this work touched the GPU, the live venv, or any live PID. The smoke test ran with
`CUDA_VISIBLE_DEVICES=""` (CPU-only) for exactly this reason.

**Observed timeline note (reported, not reconciled):** the brief said "~16h into a ~15.3h-budget
job finishing ~05:47Z 2026-09-17". What I observed: vLLM up since Sep15 (16h18m), harness started
10:27 local with `--max-runtime-minutes 230` and `--max-experiment-runtime-minutes 960`. I did not
try to reconcile these; I report what `ps` showed.

---

## 2. Wheel provenance — where CUDA torch actually comes from

**Answer: the public PyTorch cu130 index. No NVIDIA-special index, no cached wheel.**

```
https://download.pytorch.org/whl/cu130
  -> torch-2.11.0+cu130-cp312-cp312-manylinux_2_28_aarch64.whl   (420,247,044 bytes)
```

How this was established, not guessed:
- `curl https://download.pytorch.org/whl/cu130/torch/` → 200, and the listing contains the exact
  aarch64 cp312 filename above (cp310/311/312/313/313t/314/314t all present).
- The live venv's `torch-2.11.0+cu130.dist-info/WHEEL` shows
  `Tag: cp312-cp312-manylinux_2_28_aarch64`, matching that wheel exactly. `INSTALLER` says `uv`;
  there is no `direct_url.json`, so it came from an index, not a local file.
- **No cached wheel exists.** `~/.cache/uv/` holds only `sdists-v9/` and `interpreter-v4/` — the
  wheel cache has been cleaned. `find ~/.cache -name 'torch-2.11*'` returns nothing. The
  "copy the cached wheel" fallback was checked and is not available.
- CUDA runtime deps resolve transitively from **`https://pypi.nvidia.com`** (cublas, cudnn_cu13,
  cufft, cusolver, cusparse, nccl_cu13, nvshmem_cu13, …) — pip follows these automatically.

**Premise correction:** `uv` **is** installed, at `/home/son/.local/bin/uv`. It is not on the
login `PATH` for a non-interactive ssh, which is why it looked absent. This matters as a *hazard*:
`uv pip install` / `uv sync` walk **up** from cwd to find a project, so run from anywhere under
`~/GitHub/arc-3/ARC3-Inference/` they would target the **live** venv and reconcile it against
`uv.lock` (which pins torch 2.10.0) — killing PID 765547's run. **I deliberately used stdlib
`venv` + the new venv's own `pip` by absolute path throughout, and never invoked `uv`.**

---

## 3. What was installed

Two-step, so the resolver could not move torch:

```bash
python3 -m venv /home/son/arc3-train-venv

/home/son/arc3-train-venv/bin/pip install --only-binary :all: \
  --index-url https://download.pytorch.org/whl/cu130 "torch==2.11.0+cu130"

echo "torch==2.11.0+cu130" > constraints.txt
/home/son/arc3-train-venv/bin/pip install --only-binary :all: --constraint constraints.txt \
  transformers datasets accelerate peft trl safetensors sentencepiece hf_transfer numpy
/home/son/arc3-train-venv/bin/pip install --only-binary :all: --constraint constraints.txt \
  compressed-tensors        # added to answer Q2 from the real checkpoint config
```

`--only-binary :all:` was used on **every** command, so a source build would have been a hard
error rather than something to notice and abort. **Zero source builds occurred**
(`grep -ci "Building wheel" install-stack.log` → `0`). `sentencepiece` and `hf_transfer`, the two
most likely to need a compiler, both had prebuilt aarch64 wheels. **Nothing was skipped or
deferred.**

Logs: `install-torch.log`, `install-stack.log`.

---

## 4. Proof it works

### 4.1 CUDA sees the GB10

```
$ /home/son/arc3-train-venv/bin/python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available(), torch.cuda.get_device_capability(), torch.cuda.get_device_name(0))"
2.11.0+cu130 13.0 True (12, 1) NVIDIA GB10
```

`is_available() == True`, capability `(12, 1)` = sm_121. Run as a one-shot that exits
immediately; `free -g` before/after showed available 5G → 5G, no lasting CUDA context.

### 4.2 Versions

```
torch         2.11.0+cu130 | cuda 13.0 | avail True | cap (12, 1)
transformers  5.17.0
peft          0.21.0
trl           1.13.0
accelerate    1.15.0
datasets      5.0.1
safetensors   0.8.0
numpy         2.5.3
sentencepiece 0.2.2
hf_transfer   ok (imports)
compressed-tensors 0.18.0
```

torch was re-printed after step two and had **not** moved.

### 4.3 End-to-end LoRA SFT smoke test — PASSED

Run **CPU-only** (`CUDA_VISIBLE_DEVICES=""`) to keep the GPU untouched while vLLM holds it.
Script `smoke_sft.py`, model `HuggingFaceTB/SmolLM2-135M-Instruct`, LoRA r=8 on `q_proj`/`v_proj`,
20 steps over all 11 records via the converter's chat-template output.

```
records: 11
trainable params: 460,800 || all params: 134,975,808 || trainable%: 0.3414
step  1:  loss 3.0597   mean_token_accuracy 0.4203
step 20:  loss 3.0091   mean_token_accuracy 0.4778   grad_norm 0.3122776448726654
          num_tokens 10,828
FINAL_TRAIN_LOSS 3.1135064244270323   (mean over all 20 steps)
```

**What this does and does not prove.** It proves the full path executed end-to-end —
record → converter → chat template → tokenizer → peft attach → forward/backward → optimizer —
across 20 completed optimizer steps, and the **non-zero `grad_norm` (0.3123) at step 20 confirms
gradients actually reached the LoRA adapter** rather than the run merely not crashing.

It does **not** show learning, and none is claimed. Only steps 1 and 20 were flushed as separate
log lines, and at `per_device_train_batch_size=1` over 11 records those are two *different single
examples*, not a trend. `FINAL_TRAIN_LOSS 3.1135` is the mean over all 20 steps and is **higher
than both** sampled points, so the intermediate steps were noisier — 20 steps on 11 records is far
too few to read a loss curve.

**No truncation:** the 11 records tokenize to min 351 / median 604 / **max 693** tokens under this
tokenizer, against `max_length=1024` — 0 records over. Every assistant target was seen in full.

Peak memory impact was negligible; `free` available stayed 5–8G throughout and the live job was
unaffected.

**Finding from the first attempt (which failed):** base `SmolLM2-135M` has **no**
`tokenizer.chat_template`, so `SFTTrainer` raised
`ValueError: Cannot use chat template functions because tokenizer.chat_template is not set`.
The `-Instruct` variant carries one. Any model used with this converter must ship a chat
template or be given one explicitly.

### 4.4 The converter

`~/GitHub/arc-3/scripts/decision_steps_to_chat.py` on the **Mac** (written, **not committed, not
pushed**, as instructed). Copied to a108 at
`/home/son/arc3-train-stack-setup/decision_steps_to_chat.py`. Converts all 11 records.

**Schema correction — the brief got the field paths wrong.** Per `SCHEMA.md` and the actual
records, `rationale`, `expected_observation`, `memory_out` and `action` are **nested under
`decision`**, not top-level. `memory_in` *is* top-level but is an **input**, not a target. The
converter emits input = `memory_in` + `last_action` + `last_result` (+ `ascii` when present),
target = a single JSON object carrying `decision.rationale`, `decision.memory_out`,
`decision.action`, `decision.expected_observation` — JSON so the target stays parseable and
scorable instead of free prose.

**Data finding that matters more:** **`ascii` is `null` in all 11 records.** v0 carries no board
observation in-record — only `frame_ref` pointers into recordings that are not in the dataset
directory. As it stands, a model trained on this corpus learns to produce a rationale from
*structured memory alone*, having never seen the board. Rationale targets are short (130–259
chars). Whatever is decided about scale, the missing observation channel is the blocking issue
for this corpus, not the record count.

**a108 did not have the corpus** — `/home/son/GitHub/arc-3/datasets/` does not exist there. The
9 files were copied to `/home/son/arc3-train-stack-setup/data/`.

---

## 5. Q1 — Can a 27B LoRA SFT physically run on this box?

**Exact size, from the checkpoint's own safetensors headers** (not recalled constants):

```
stored elements            20,294,595,512
  of which packed 4-bit     7,486,832,640  (nvfp4 packs 2 values per byte -> x2)
real parameters            27,781,428,152  = 27.78B
BF16 resident weights      51.7 GB
```

Architecture (`config.json` → `text_config`): 64 layers, hidden 5120, intermediate 17408,
**vocab 248,320**, 24 Q heads / 4 KV heads / head_dim 256, and a **hybrid stack of 48
`linear_attention` + 16 `full_attention` layers**, `tie_word_embeddings: false`.

The dominant term is **not** the weights and **not** the KV cache — it is the **logits tensor**,
because the vocab is 248K. Per token the logits are `248320 × 2 B = 0.47 MB` (bf16), and a naive
`nn.CrossEntropyLoss` upcasts to fp32 **and** holds a same-size gradient: `248320 × 4 × 2 =
1.9 MB/token`. Activations under gradient checkpointing are comparatively cheap at
`64 × 5120 × 2 = 0.625 MiB/token`, plus ~0.127 MiB/token in-layer recompute peak.

| seq | ckpt act | recompute | logits bf16 | CE fp32+grad | **total, naive CE** | **total, fused/chunked CE** |
|---:|---:|---:|---:|---:|---:|---:|
| 2,048 | 1.2G | 0.3G | 0.9G | 3.8G | 59.5G | 54.8G |
| 8,192 | 5.0G | 1.0G | 3.8G | 15.2G | 78.2G | 59.3G |
| 12,288 | 7.5G | 1.5G | 5.7G | 22.7G | **90.7G** | 62.3G |
| 16,384 | 10.0G | 2.0G | 7.6G | 30.3G | **103.2G** | 65.3G |
| 32,768 | 20.0G | 4.1G | 15.2G | 60.6G | 153.1G ✗ | 77.3G |
| 65,536 | 40.0G | 8.1G | 30.3G | 121.2G | 252.9G ✗ | 101.4G |
| 94,000 | 57.4G | 11.7G | 43.5G | 173.9G | 339.7G ✗ | **122.3G ✗** |

(51.7G weights + ~1.5G LoRA/grads/Adam included in both totals; batch size 1.)

**Plain answers:**
- **With a naive cross-entropy head it stops fitting between 16K and 20K tokens.** 12K fits at
  ~91G; 16K is at ~103G and already over the practical ceiling once you leave room for the OS and
  fragmentation; 32K is dead at 153G.
- **With fused/chunked cross-entropy** (Liger-style, or `logits_to_keep`, or a chunked LM head —
  none of which is installed yet) the logits term collapses and the limit becomes activations:
  **~64K fits at ~101G; 94K does not, at ~122G against 121G total.** There is no headroom at 94K
  even with everything done right.
- **Right now, none of it runs at all.** vLLM was started with `--gpu-memory-utilization 0.9` on
  121G of *unified* memory and `free` shows ~113–115G used with 5–8G available. **Any 27B
  training must wait for the live job to finish.** The numbers above assume the box to itself.
- The 22G on disk is an inference artifact and does **not** translate into a 22G training
  footprint — see Q2.

---

## 6. Q2 — Is NVFP4 trainable?

**Checked, not recalled.** Source read on the box:
`/home/son/arc3-train-venv/lib/python3.12/site-packages/transformers/quantizers/quantizer_compressed_tensors.py`

- **L146–149**, `is_trainable`: `return not self.use_fp8_kernel`, with the comment
  *"The FP8 kernel path is inference-only; load with `dequantize=True` to fine-tune."*
- **L154–160**, `is_qat_trainable`: `False` if `use_fp8_kernel`, else
  `self.quantization_config.dequantize or not self.quantization_config.is_quantization_compressed`.
- **L114**, `_process_model_before_weight_loading`: `apply_quantization_config(model, remaining_config, run_compressed=False)`.
- **L120–127**, `_process_model_after_weight_loading`: with `dequantize=False` the weights are
  *left compressed* and a hook *"decompresses them on the first forward pass instead."*
- `peft` 0.21.0 has **no compressed-tensors awareness at all** —
  `grep -rn "compressed" .../peft/` returns only `lora/velora.py` "compressed *activations*",
  which is unrelated.

**Empirically, against this checkpoint's real `quantization_config`** (no weights loaded):

```
use_optimized_inference : False
use_fp8_kernel          : False
is_quantization_compressed: True
dequantize              : False
IS_TRAINABLE            : True
IS_QAT_TRAINABLE        : False
  group_0: fmt=float-quantized      wbits=8 fp8_scheme=True   (attn q/k/v/o, lm_head, layers 56-63 mlp)
  group_1: fmt=nvfp4-pack-quantized wbits=4 fp8_scheme=False  (mlp gate/up/down)
```

**Answer: transformers will not *block* a LoRA attach — `is_trainable` is `True` — but this buys
you nothing, and a BF16 base is required in substance.** The reason is the decompression path:
whether you pass `dequantize=True` (decompress at load) or leave `dequantize=False` (hook
decompresses on first forward), **the weights end up materialised in BF16 either way.**

This was confirmed rather than inferred from the docstring. In
`compressed_tensors/compressors/model_compressors/model_compressor.py`:
**L260** registers `ct_decompress_hook` via `register_forward_pre_hook`; **L257–258** show the
hook body calls `decompress_model(model)` and notes *"decompress_model already removes the hook
via remove_decompression_hook"*; **L272–273** do `model.ct_decompress_hook.remove()` then
`delattr(model, "ct_decompress_hook")`. **The decompression is one-shot and persistent** — it
fires once, rewrites the module weights, and unregisters itself. It is not a per-forward
decompress-and-free, so peak memory does not stay near 22G. The BF16-resident conclusion holds. The 22G
NVFP4 file becomes ~51.7G resident the moment you train on it. There is no 4-bit-resident
training path here the way bitsandbytes QLoRA gives you one — `peft` has no kernel for
`nvfp4-pack-quantized`, and QAT is explicitly off (`is_qat_trainable: False`, because this
checkpoint is compressed and `dequantize` is False).

Practical consequence: **you can manufacture a BF16 base from this checkpoint by dequantizing it,
and that is probably the cheapest path — but the result is NVFP4-quality weights upcast to BF16,
not the original BF16 weights.** Whether that lossy round-trip is an acceptable SFT starting point
is a real decision with a quality cost attached. **That is the Boss's call, and I have not
pre-empted it — no weights were downloaded and nothing was dequantized.**

---

## 7. Q3 — What would the first RL loop actually need?

**27B GRPO on one GB10 is not feasible, and I would not try it.** GRPO needs three things resident
at once: a trainable policy, a rollout engine fast enough to generate groups of completions, and
(unless you use the LoRA adapter-disable trick to stand in for it) a reference model. At 27B that
is 51.7G for the policy plus a rollout copy of similar order, before a single KV cache byte for
generation — and ARC-3 prompts run 12K–94K tokens, which is precisely where KV cache stops being a
rounding error. On 121G of *shared* unified memory, with the serving stack needing to live
alongside training, there is no arrangement of that which fits. Adapter-disable removes the
reference copy and chunked CE removes the logits blowup, and it still does not fit once rollouts
need their own weights and cache. A realistic first loop is a **1.5B–4B policy** — Qwen3-1.7B or
Qwen3-4B class — where BF16 policy is 3.4–8G, a vLLM rollout copy is the same again, and the
remaining ~100G goes to KV cache for concurrent long-context rollouts, which is where it will
actually be spent. The stack would be `trl`'s `GRPOTrainer` with `use_vllm=True` pointed at a
**separate** vLLM server process (trl 1.13 supports `vllm_server_url`), plus a programmatic reward
over the corpus's own structure — `expected_observation` against the next frame is the natural
reward signal, and it is the reason that field exists. **I did not install `vllm` or `verl`**: both
pull ray and a vLLM resolve that would have fought the live venv's torch pin and near-certainly
triggered source builds, violating constraints 1 and 2. That install belongs in its own venv,
after the live run ends. Honest caveat: at 1.7B–4B you are not going to see 27B-class reasoning —
this first loop is for proving the reward plumbing and the rollout path, not for a result worth
reporting as capability.

---

## 8. Deliberately NOT done

| not done | why |
|---|---|
| No `uv` invoked, anywhere | walks up to the live `ARC3-Inference` project and would reconcile its venv against `uv.lock` (torch 2.10.0), killing PID 765547 |
| Nothing written to `ARC3-Inference/.venv` | constraint 1 |
| No `vllm`, no `verl`, no `ray` | would fight the torch pin and pull source builds; belongs in its own venv after the run |
| No `flash-attn` / `deepspeed` / `bitsandbytes` / `xformers` | constraint 2 — all are source builds on aarch64/sm_121 |
| No model weights downloaded beyond SmolLM2-135M-Instruct (~270MB) for the smoke test | constraint 4; the BF16-base decision is the Boss's |
| Nothing dequantized, no GPU used | live job holds ~113G of 121G; smoke test forced to CPU |
| Converter not committed or pushed | as instructed — left on the Mac for review |

---

## 9. First tasks for the next session (after the live run ends)

1. Re-run the smoke test **on GPU** (drop `CUDA_VISIBLE_DEVICES=""`) to confirm the CUDA training
   path, not just the CPU one. This is the one piece of evidence this report does not have.
2. Decide the BF16-base question (Q2) — dequantize-from-NVFP4 vs. pull a real BF16 base.
3. If 27B SFT proceeds, install a fused/chunked cross-entropy before anything else; without it the
   ceiling is ~16K tokens instead of ~64K (§5).
4. Resolve the missing observation channel in the corpus (§4.4) — `ascii` is null in all 11 records.
