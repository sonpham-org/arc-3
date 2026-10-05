"""LoRA trainer for Flash-Next on ARC-3 records (plan: docs/plans/2026-10-01-rl-on-burst-games.md §3, B6).

Trains one LoRA on the BF16 tensors that every served form shares (full attention, linear attention, shared
expert; the MTP head excluded), through the full model with every routed expert frozen. Records come from
build_records.py (round 0: the model's own efficient wins) or from the try runner (expert iteration: the best try
of each mixed group). Loss = cross-entropy on the model's own generated tokens only (render.py loss mask),
weighted per record (meta.weight, default 1).

Long sequences (~100k tokens) never materialize full logits: one forward to the last hidden state, then the
head and the loss in chunks over the trained positions only (each chunk checkpointed).

Modes:
  train   records -> adapter (+ train_log.jsonl)
  check   G1: forward one record, print per-token log-probs of the trained tokens (for the served = trained
          comparison), then overfit it for --steps steps and require the loss to fall (gradients reach the LoRA)

Usage (8-GPU box):
  python lora_train.py train --model /mnt/m/bf16 --hf /opt/rl/hf --records 'g0/*/records/*.jsonl.gz' --out adapters/r0
  python lora_train.py check --model /mnt/m/bf16 --hf /opt/rl/hf --records one.jsonl.gz --steps 5 --out g1/
"""
from __future__ import annotations

import argparse
import glob
import gzip
import hashlib
import json
import math
import os
import random
import re
import shutil
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")    # before torch touches CUDA
import torch
import torch.nn.functional as F
from torch.utils.checkpoint import checkpoint

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render  # noqa: E402

# The shared BF16 tensors (plan §3). Anchored at the decoder stack so the MTP head (mtp.layers.*) is excluded.
TARGET_REGEX = (r"model\.language_model\.layers\.\d+\."
                r"(self_attn\.(q_proj|k_proj|v_proj|o_proj)"
                r"|linear_attn\.(in_proj_qkv|in_proj_z|out_proj)"
                r"|mlp\.shared_expert\.(gate_proj|up_proj|down_proj))")
NGRAM_TABLE = "ple.ple_embedding"           # the 51B n-gram table: host RAM, never on a GPU


# ------------------------------------------------------------------------------------------------ data
def load_records(pattern: str, limit: int = 0) -> list[dict]:
    recs = []
    for path in sorted(glob.glob(pattern)):
        opener = gzip.open if path.endswith(".gz") else open
        with opener(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    recs.append(json.loads(line))
                    if limit and len(recs) >= limit:
                        return recs
    return recs


def to_batch(processor, record: dict, device) -> dict:
    r = render.render(processor, record, add_generation_prompt=False)
    ids = torch.tensor([r["input_ids"]], dtype=torch.long, device=device)
    mask = torch.tensor([r["loss_mask"]], dtype=torch.bool, device=device)
    weights = torch.tensor([r["loss_weights"]], dtype=torch.float32, device=device)
    vision = {k: (v.to(device) if hasattr(v, "to") else v) for k, v in r["vision"].items()}
    return {"input_ids": ids, "loss_mask": mask, "loss_weights": weights, "vision": vision,
            "n_loss": r["n_loss_tokens"], "spans_ok": r["n_assistant_spans"] == r["n_assistant_messages"]}


def trained_weights(batch: dict) -> torch.Tensor:
    """Per-token loss weights in the same order as token_logprobs' output (trained positions, position 0 excluded)."""
    pos = batch["loss_mask"][0].nonzero().squeeze(-1)
    pos = pos[pos > 0]
    return batch["loss_weights"][0][pos]


# ------------------------------------------------------------------------------------------------ model
def _pin(dmap: dict, meta, target: str, device) -> None:
    """Map `target` to `device`, splitting whichever mapped ancestor covers it (accelerate maps whole modules)."""
    key = next((k for k in dmap if k == target or k == "" or target.startswith(k + ".")), None)
    if key is None or key == target:
        dmap[target] = device
        return
    dev = dmap.pop(key)
    sub = meta.get_submodule(key) if key else meta
    for child, _ in sub.named_children():
        dmap[f"{key}.{child}" if key else child] = dev
    _pin(dmap, meta, target, device)


def device_map_for(model_dir: str, n_gpus: int, gpu_gib: int, even_layers: bool = False) -> dict:
    """Layers spread over the GPUs; the 51B n-gram table and the MTP head (not trained) in host RAM."""
    from accelerate import infer_auto_device_map, init_empty_weights
    from transformers import AutoConfig, AutoModelForImageTextToText
    cfg = AutoConfig.from_pretrained(model_dir)
    with init_empty_weights():
        meta = AutoModelForImageTextToText.from_config(cfg)
    no_split = sorted({type(m).__name__ for n, m in meta.named_modules() if n.endswith("layers.0")})
    mem = {i: f"{gpu_gib}GiB" for i in range(n_gpus)}
    mem["cpu"] = "1400GiB"
    names = [n for n, _ in meta.named_modules()]
    cpu = [n for n in names if n.endswith(NGRAM_TABLE)]
    mtp = sorted((n for n in names if n.split(".")[-1] == "mtp"), key=len)[:1]
    # take the table and MTP out of the plan so the GPU budget is spent only on the layers that run on GPUs ...
    for n in cpu + mtp:
        parent, _, child = n.rpartition(".")
        setattr(meta.get_submodule(parent) if parent else meta, child, torch.nn.Module())
    # balanced: weights spread evenly (~equal per GPU) so every GPU keeps the same headroom for activations;
    # the first run (1-Oct) without it left 20+ layers on the CPU.
    from accelerate.utils import get_balanced_memory
    # dtype: the meta model is built in float32; without it the planner sizes the weights at twice their served
    # BF16 size and spills ~20 layers to the CPU (1-Oct smoke)
    bal = get_balanced_memory(meta, max_memory=mem, no_split_module_classes=no_split, low_zero=False,
                              dtype=torch.bfloat16)
    dmap = infer_auto_device_map(meta, max_memory=bal, no_split_module_classes=no_split, dtype=torch.bfloat16)
    # ... then pin them to host RAM in the final map
    for n in cpu + mtp:
        _pin(dmap, meta, n, "cpu")
    if even_layers:
        # packed NVFP4 experts (loaded after this map, invisible to the planner) are the bulk of each layer: spread
        # the decoder layers evenly by count so every GPU holds the same share of them
        n_layers = sum(1 for n in names if re.fullmatch(r"model\.language_model\.layers\.\d+", n))
        for k in list(dmap):
            hit = re.match(r"model\.language_model\.layers\.(\d+)(\.|$)", k)
            if hit and dmap[k] != "cpu":
                dmap[k] = int(hit.group(1)) * n_gpus // n_layers
    on_cpu = sorted(k for k, v in dmap.items() if v == "cpu" and not any(k == c or k.startswith(c + ".") for c in cpu + mtp)
                    and not any(c.startswith(k + ".") for c in cpu + mtp))
    print("device map:", {str(d): sum(1 for v in dmap.values() if v == d) for d in set(dmap.values())},
          "| pinned to cpu:", cpu + mtp, "| other modules on cpu:", on_cpu[:12], flush=True)
    if on_cpu and os.environ.get("ARC3_ALLOW_CPU_LAYERS") != "1":
        raise RuntimeError(f"{len(on_cpu)} modules would run on the CPU (raise --gpu-gib or add GPUs): {on_cpu[:6]}")
    return dmap


def run_table_on_cpu(model) -> list[str]:
    """Execute the n-gram table lookup ON THE CPU and send only the looked-up rows to the GPU.

    accelerate treats a module mapped to "cpu" as offloaded: it keeps the weights on the CPU but copies them to the
    execution GPU at every forward. For the 51B table that is a 95 GiB copy (1-Oct smoke OOM). The table is frozen
    and only gathered from, so: materialize its weights on the CPU, drop accelerate's hook, and wrap its forward to
    run on the CPU under no_grad (nothing upstream of it trains)."""
    from accelerate.hooks import remove_hook_from_module
    from accelerate.utils import set_module_tensor_to_device
    done = []
    for name, mod in model.named_modules():
        if not name.endswith(NGRAM_TABLE):
            continue
        hook = getattr(mod, "_hf_hook", None)
        wmap = getattr(hook, "weights_map", None)
        for pname, t in list(mod.named_parameters(recurse=True)) + list(mod.named_buffers(recurse=True)):
            if t.device.type == "meta":
                if wmap is None:
                    raise RuntimeError(f"{name}.{pname} is on meta and no offload map holds it")
                set_module_tensor_to_device(mod, pname, "cpu", value=wmap[pname])
            elif t.device.type != "cpu":
                set_module_tensor_to_device(mod, pname, "cpu", value=t.to("cpu"))
        remove_hook_from_module(mod, recurse=True)
        parent = model.get_submodule(name.rsplit(".", 1)[0])
        gpu = next((p.device for p in parent.parameters() if p.device.type == "cuda"), torch.device("cuda:0"))
        inner = mod.forward

        def forward(input_ids, *args, _inner=inner, _gpu=gpu, **kwargs):
            with torch.no_grad():
                out = _inner(input_ids.to("cpu"), *args, **kwargs)
            return out.to(_gpu)

        mod.forward = forward
        done.append(f"{name} -> cpu, out to {gpu}")
    print("n-gram table runs on the CPU:", done, flush=True)
    return done


def load_model(model_dir: str, n_gpus: int, gpu_gib: int, rank: int, alpha: int, adapter: str = "",
               attn: str = "", fast: bool = True, offload: bool = True, nvfp4: str = "", seed: int = 0,
               experts_source: str = "", experts_stacked: str = "", ple_cache_dir: str = "", view_dir: str = ""):
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForImageTextToText
    if nvfp4:
        # the served NVFP4 experts (nvfp4_experts.py): the BF16 expert keys are skipped, the packed ones load after
        import nvfp4_experts
        nvfp4_experts.install_placeholder()
    if ple_cache_dir:
        # 4-Oct: the n-gram table is never loaded; its per-record output comes from ple_cache.precompute
        import ple_cache
        ple_cache.install(ple_cache_dir)
    if nvfp4 or ple_cache_dir:
        # 4-Oct: read neither the BF16 routed experts (the packed ones load separately) nor, with the cache, the table
        import ple_cache
        dt, de = bool(ple_cache_dir), bool(nvfp4)
        model_dir = str(ple_cache.model_view(model_dir, view_dir or ple_cache.default_view_dir(model_dir, dt, de),
                                             drop_table=dt, drop_experts=de))
    dmap = device_map_for(model_dir, n_gpus, gpu_gib, even_layers=bool(nvfp4))
    extra = {"attn_implementation": attn} if attn else {}
    model = AutoModelForImageTextToText.from_pretrained(model_dir, dtype=torch.bfloat16, device_map=dmap, **extra)
    print("attention implementation:", getattr(model.config, "_attn_implementation", None), flush=True)
    if nvfp4:
        print("nvfp4 experts:", nvfp4_experts.load_packed(model, nvfp4, source=experts_source or None,
                                                          stacked_dir=experts_stacked or None), flush=True)
    if not ple_cache_dir:
        run_table_on_cpu(model)
    model.config.use_cache = False
    for p in model.parameters():
        p.requires_grad_(False)
    # The LoRA init is random: seed it here, so every process (one copy or each of --dp N) starts from the same
    # adapter whatever ran before it (2-Oct: a two-copy run started from a different init than a one-copy run).
    torch.manual_seed(seed)
    if adapter:
        # Not PeftModel.from_pretrained: on a model whose device map includes the CPU it re-dispatches everything
        # with "auto" over all visible GPUs, moving the CPU-pinned n-gram table to a GPU (2-Oct resume test: "cuda:3
        # and cpu"). The same LoRA is built in place instead and the saved weights are copied into it.
        from peft import set_peft_model_state_dict
        from safetensors.torch import load_file
        acfg = json.loads((Path(adapter) / "adapter_config.json").read_text())
        model = get_peft_model(model, LoraConfig(r=acfg["r"], lora_alpha=acfg["lora_alpha"], lora_dropout=0.0,
                                                 bias="none", target_modules=acfg.get("target_modules") or TARGET_REGEX))
        res = set_peft_model_state_dict(model, load_file(str(Path(adapter) / "adapter_model.safetensors")))
        missing = [k for k in res.missing_keys if "lora_" in k]
        if missing or res.unexpected_keys:
            raise RuntimeError(f"adapter {adapter} does not fit: missing {missing[:3]}, unexpected {res.unexpected_keys[:3]}")
        print(f"adapter loaded from {adapter}", flush=True)
    else:
        model = get_peft_model(model, LoraConfig(r=rank, lora_alpha=alpha, lora_dropout=0.0, bias="none",
                                                 target_modules=TARGET_REGEX))
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    if fast:
        # long records: vectorized QSA selection, gathered sparse attention, no S x S masks (fast_qsa.py);
        # offload: each decoder layer's input waits in host RAM between forward and backward
        import fast_qsa
        print("fast path:", fast_qsa.install(model, offload=offload), flush=True)
    # checkpointing only runs in training mode (1-Oct smoke OOMed in eval mode: every activation was kept)
    model.train()
    n_train = sum(p.numel() for p in model.parameters() if p.requires_grad)
    n_mods = sum(1 for n, _ in model.named_modules() if n.endswith("lora_A"))
    print(f"lora: {n_mods} target modules, {n_train/1e6:.1f}M trainable params", flush=True)
    if n_mods == 0:
        raise RuntimeError("TARGET_REGEX matched nothing: module names changed?")
    return model


def _inner(model):
    """(decoder returning last_hidden_state, lm_head) under the peft wrapper."""
    base = model.get_base_model() if hasattr(model, "get_base_model") else model
    return base.model, base.lm_head


def token_logprobs(model, batch: dict, chunk: int = 2048, grad: bool = False) -> torch.Tensor:
    """Log-probabilities of the trained tokens (teacher-forced), computed chunk by chunk."""
    decoder, head = _inner(model)
    out = decoder(input_ids=batch["input_ids"], use_cache=False, **batch["vision"])
    hidden = out.last_hidden_state if hasattr(out, "last_hidden_state") else out[0]
    ids = batch["input_ids"][0]
    pos = batch["loss_mask"][0].nonzero().squeeze(-1)          # positions of trained tokens
    pos = pos[pos > 0]
    src = pos - 1                                              # the hidden state that predicts each of them
    pieces = []
    for i in range(0, len(src), chunk):
        s = src[i:i + chunk]
        t = ids[pos[i:i + chunk]]

        def piece(h, s=s, t=t):
            logits = head(h[0, s.to(h.device)]).float()
            return torch.log_softmax(logits, dim=-1).gather(-1, t.to(logits.device)[:, None]).squeeze(-1)

        pieces.append(checkpoint(piece, hidden, use_reentrant=False) if grad else piece(hidden))
    return torch.cat([p.to(pieces[0].device) for p in pieces]) if pieces else torch.zeros(0)


def adapter_sha(path: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(path.glob("adapter_model*.safetensors")):
        h.update(f.read_bytes())
    return h.hexdigest()[:16]


# ------------------------------------------------------------------------------------------------ modes
def _dp() -> tuple[int, int]:
    """(rank, world) of this copy under --dp; (0, 1) for a single copy."""
    return int(os.environ.get("ARC3_DP_RANK", "0")), int(os.environ.get("ARC3_DP_WORLD", "1"))


def _allreduce_grads(params, world: int) -> None:
    """Average the LoRA gradients over the data-parallel copies: gloo through host memory, one flat tensor of the
    adapter's ~61M floats (~1 s per optimizer step, against minutes of compute per record)."""
    import torch.distributed as dist
    flat = torch.cat([(p.grad if p.grad is not None else torch.zeros_like(p)).detach().float().reshape(-1).cpu()
                      for p in params])
    dist.all_reduce(flat)
    flat /= world
    off = 0
    for p in params:
        n = p.numel()
        p.grad = flat[off:off + n].view_as(p).to(device=p.device, dtype=p.dtype)
        off += n


def _broadcast_params(params) -> None:
    """Copy 0's adapter to every copy. The LoRA init is random, and averaged gradients keep copies identical only if
    they start identical."""
    import torch.distributed as dist
    flat = torch.cat([p.detach().float().reshape(-1).cpu() for p in params])
    dist.broadcast(flat, src=0)
    off = 0
    with torch.no_grad():
        for p in params:
            n = p.numel()
            p.copy_(flat[off:off + n].view_as(p).to(device=p.device, dtype=p.dtype))
            off += n


def _copies_agree(params) -> tuple[float, float]:
    """(min, max) over the copies of the sum of every adapter weight: equal when the copies are in step."""
    import torch.distributed as dist
    s = torch.tensor([sum(float(p.detach().double().sum()) for p in params)], dtype=torch.float64)
    lo, hi = s.clone(), s.clone()
    dist.all_reduce(lo, op=dist.ReduceOp.MIN)
    dist.all_reduce(hi, op=dist.ReduceOp.MAX)
    return lo.item(), hi.item()


# ------------------------------------------------------------------------------------------------ relative credit
# 4-Oct restart (Son: "if a trace is better than average then it is positive", and worse is negative): records carry
# per-reply advantages that can be negative (build_records.level_advantages). Pushing a sequence's probability down
# has no floor, so the update is PPO's: per token, the ratio to the probability at the START of the round is clipped
# to [1 - clip, 1 + clip] in the direction the advantage pushes, plus a k3 KL penalty to that same start.
KL_CAP = float(os.environ.get("ARC3_KL_CAP", "5"))     # k3 is exact up to d = 5 (a 148x drop), linear past it


def id_of(rec: dict) -> str:
    return hashlib.sha256(json.dumps(rec.get("meta", {}), sort_keys=True).encode()).hexdigest()[:20]


def clipped_loss(lp: torch.Tensor, old: torch.Tensor, adv: torch.Tensor, clip: float, kl_coef: float,
                 clip_high: float | None = None, cispo: bool = False, norm_tokens: float | None = None):
    """-(sum over trained tokens of the objective - kl_coef * k3) / n, r = exp(lp - old). Returns (loss, stats).
    Objective: PPO's min(r A, clip(r) A) with clip(r) in [1 - clip, 1 + clip_high] (clip_high: DAPO's clip-higher, a
    larger upper bound so unlikely tokens can rise; default = clip); or with cispo, CISPO's (MiniMax-M1)
    sg(clip(r)) * A * log p: the ratio is clipped as a WEIGHT and every token keeps its gradient (PPO's clip zeroes the
    gradient of clipped tokens; 4-Oct n0 had 8.5% of tokens clipped by step 2). n: the record's trained tokens
    (per-record mean, the default), or norm_tokens (a constant: the dataset's mean trained tokens per record), which
    weighs every token alike across records (DAPO / Dr. GRPO token-level normalization)."""
    hi = clip if clip_high is None else clip_high
    ratio = torch.exp(lp - old)
    clipped = ratio.clamp(1 - clip, 1 + hi)
    if cispo:
        obj = clipped.detach() * adv * lp
    else:
        obj = torch.minimum(ratio * adv, clipped * adv)
    d = old - lp
    # k3 = e^d - d - 1, continued linearly past d = KL_CAP (slope e^c - 1): 4-Oct n0, one record whose sc25 tokens had
    # dropped ~e^10 below the round's start gave k3 = 2402 and a loss of +121; the pull-back stays, the explosion goes
    c = KL_CAP
    kl = torch.where(d > c, (math.exp(c) - 1) * (d - c) + (math.exp(c) - c - 1), torch.exp(d.clamp(max=c)) - d.clamp(max=c) - 1)
    n = float(norm_tokens) if norm_tokens else max(1, lp.numel())
    loss = -(obj - kl_coef * kl).sum() / n
    with torch.no_grad():
        stats = {"ratio_mean": round(ratio.mean().item(), 5),
                 "clip_frac": round(((ratio - clipped).abs() > 0).float().mean().item(), 4),
                 "kl": round(kl.mean().item(), 6), "adv_mean": round(adv.mean().item(), 4)}
    return loss, stats


def _ple_record(args, rec: dict) -> None:
    """With --ple-cache, the record whose cached n-gram embedding the next forward reads."""
    if getattr(args, "ple_cache", ""):
        import ple_cache
        ple_cache.set_record(id_of(rec))


def old_logprobs(model, processor, recs: list[dict], rank: int, world: int, args, out: Path, dev) -> dict:
    """Every record's trained-token log-probs under the round's STARTING adapter (no grad), computed once before the
    first update and saved, so a resumed run keeps the same reference. Each copy computes every world-th record;
    all copies then read every copy's file (same VM, same --out)."""
    mine = out / f"old_logprobs_rank{rank}.pt"
    if not mine.exists():
        cache, t0 = {}, time.time()
        for i, r in enumerate(recs):
            if i % world != rank:
                continue
            b = to_batch(processor, r, dev)
            if not b["spans_ok"] or b["n_loss"] == 0 or b["input_ids"].shape[1] > args.max_tokens:
                continue
            _ple_record(args, r)
            try:
                with torch.no_grad():
                    cache[id_of(r)] = token_logprobs(model, b).float().cpu()
            except torch.OutOfMemoryError:
                torch.cuda.empty_cache()          # the training step will skip this record too
            print(f"old log-probs {len(cache)} ({time.time() - t0:.0f}s)", flush=True)
        torch.save(cache, mine)
    if world > 1:
        import torch.distributed as dist
        dist.barrier()
    merged = {}
    for f in sorted(out.glob("old_logprobs_rank*.pt")):
        merged.update(torch.load(f, map_location="cpu"))
    print(f"old log-probs ready: {len(merged)} records", flush=True)
    return merged


def spawn_dp(args) -> int:
    """--dp N: N copies of the model, each on gpus/N cards, each training every N-th record; their gradients are
    averaged at every optimizer step, so it is the same training on the same records, about N times sooner. The
    copies talk over gloo on this host; each logs its own records to train_log.jsonl; copy 0 saves the adapter."""
    import socket
    import subprocess
    per = args.gpus // args.dp
    if per < 1 or per * args.dp != args.gpus:
        raise SystemExit("--gpus must be a multiple of --dp")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    # the cards this job may use: the parent's CUDA_VISIBLE_DEVICES when set (4-Oct RL box: the trainer has cards
    # 4-7, the rollout servers 0-3), else 0..gpus-1; copy r gets its own slice of that list
    vis = [c for c in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if c.strip()] or \
        [str(g) for g in range(args.gpus)]
    if len(vis) < args.gpus:
        raise SystemExit(f"--gpus {args.gpus} but CUDA_VISIBLE_DEVICES lists {len(vis)} cards")
    procs = []
    for r in range(args.dp):
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=",".join(vis[g] for g in range(r * per, (r + 1) * per)),
                   ARC3_DP_RANK=str(r), ARC3_DP_WORLD=str(args.dp), ARC3_DP_INIT=f"tcp://127.0.0.1:{port}")
        procs.append(subprocess.Popen([sys.executable, str(Path(__file__).resolve())] + sys.argv[1:], env=env))
    codes = [None] * len(procs)
    while any(c is None for c in codes):
        time.sleep(5)
        codes = [p.poll() for p in procs]
        if any(c not in (None, 0) for c in codes):     # a failed copy leaves the others waiting in a collective
            for p in procs:
                if p.poll() is None:
                    p.terminate()
            codes = [p.wait() for p in procs]
    print(f"dp copies exited {codes}", flush=True)
    return 0 if all(c == 0 for c in codes) else 1


# ------------------------------------------------------------------------------------------------ checkpoints
# Spot VMs stop without warning; a round is hours of records. With --ckpt-every, copy 0 keeps the adapter, the
# optimizer and the position in --out; rerunning the same command into the same --out resumes there.
CKPT = "ckpt.json"


def order_sig(recs: list[dict]) -> str:
    """Fingerprint of the training order: a checkpoint resumes only the run that wrote it."""
    h = hashlib.sha256()
    for r in recs:
        h.update(hashlib.sha256(json.dumps(r, sort_keys=True).encode()).digest())
    return h.hexdigest()[:16]


def save_ckpt(model, opt, out: Path, state: dict) -> None:
    """Adapter + optimizer in out/ckpt-<step>/, then ckpt.json replaced atomically after a sync: a stop at any moment
    leaves the previous checkpoint or this one, never half of one."""
    t0 = time.time()
    sync = getattr(os, "sync", lambda: None)
    d = out / f"ckpt-{state['step']:05d}"
    tmp = out / f".tmp-{d.name}"
    shutil.rmtree(tmp, ignore_errors=True)
    model.save_pretrained(tmp)
    torch.save(opt.state_dict(), tmp / "optim.pt")
    shutil.rmtree(d, ignore_errors=True)
    tmp.rename(d)
    sync()
    (out / f"{CKPT}.tmp").write_text(json.dumps(dict(state, dir=d.name, at=round(time.time()))))
    os.replace(out / f"{CKPT}.tmp", out / CKPT)
    sync()
    for old in out.glob("ckpt-*"):
        if old.name != d.name:
            shutil.rmtree(old, ignore_errors=True)
    print(f"checkpoint {d.name}: epoch {state['epoch']}, {state['done']} records done ({time.time() - t0:.0f} s)",
          flush=True)


def load_ckpt(out: Path, sig: str) -> dict | None:
    p = out / CKPT
    if not p.exists():
        return None
    st = json.loads(p.read_text())
    if st.get("order") != sig:
        raise SystemExit(f"{p} belongs to other records (or another order): use a new --out, or delete it to start over")
    if not (out / st["dir"] / "optim.pt").exists():
        raise SystemExit(f"{p} names {st['dir']}, which is incomplete")
    return st


def clear_ckpt(out: Path) -> None:
    (out / CKPT).unlink(missing_ok=True)
    for d in list(out.glob("ckpt-*")) + list(out.glob(".tmp-ckpt-*")):
        shutil.rmtree(d, ignore_errors=True)


def prepare_out(args) -> None:
    """Once per run (not per copy), before training. A rerun into the same --out either resumes its checkpoint,
    keeping the log rows of the records trained before it (rows after it are trained again), or starts over,
    keeping the earlier log under a dated name."""
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log = out / "train_log.jsonl"
    if args.ckpt_every and (out / CKPT).exists():
        st = json.loads((out / CKPT).read_text())
        lines = [l for l in log.read_text(encoding="utf-8").splitlines() if l.strip()] if log.exists() else []
        keep, rows, total = [], 0, 0
        for line in lines:
            row = json.loads(line)
            if "loss" in row or "skip" in row:          # one row per record: trained, too long, or out of memory
                total += 1
                if rows >= st["rows"]:
                    continue
                rows += 1
            elif rows >= st["rows"] and total > rows:
                continue
            keep.append(line)
        keep.append(json.dumps({"resume": {k: st[k] for k in ("epoch", "done", "step")}, "rows_kept": rows,
                                "rows_dropped": total - rows, "at": round(time.time())}))
        tmp = out / "train_log.jsonl.tmp"
        tmp.write_text("\n".join(keep) + "\n", encoding="utf-8")
        os.replace(tmp, log)
        print(f"resuming {out}: step {st['step']}, epoch {st['epoch']}, {st['done']} records done; log keeps {rows} "
              f"record rows, drops {total - rows}", flush=True)
    elif log.exists() and log.stat().st_size:
        old = out / time.strftime("train_log.%Y%m%dT%H%M%S.jsonl", time.gmtime(log.stat().st_mtime))
        log.rename(old)
        print(f"no checkpoint in {out}: starting over; the earlier log is now {old.name}", flush=True)


def mode_train(args) -> int:
    from transformers import AutoProcessor
    rank, world = _dp()
    if world > 1:
        import torch.distributed as dist
        dist.init_process_group("gloo", init_method=os.environ["ARC3_DP_INIT"], rank=rank, world_size=world)
    processor = AutoProcessor.from_pretrained(args.hf)
    recs = load_records(args.records)
    random.Random(args.seed).shuffle(recs)
    if args.longest:   # memory tests: the longest records first
        recs = [r for _, _, r in sorted(((len(render.render(processor, r)["input_ids"]), i, r)
                                         for i, r in enumerate(recs)), key=lambda t: (-t[0], t[1]))]
    if args.limit:
        recs = recs[:args.limit]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sig = order_sig(recs)
    ck = load_ckpt(out, sig) if args.ckpt_every else None
    ep0, done0, step = (ck["epoch"], ck["done"], ck["step"]) if ck else (0, 0, 0)
    accum = max(1, args.accum // world)              # records per copy per step: the global batch stays --accum
    total_steps = max(1, math.ceil(math.ceil(len(recs) / world) / accum) * args.epochs)
    print(f"{len(recs)} records" + (f" (copy {rank} of {world})" if world > 1 else "")
          + (f"; resuming at step {step}: epoch {ep0}, {done0} records done" if ck else ""), flush=True)
    model = load_model(args.model, args.gpus // world, args.gpu_gib, args.rank, args.alpha,
                       str(out / ck["dir"]) if ck else args.init_adapter,
                       args.attn, fast=bool(args.fast), offload=bool(args.offload), nvfp4=args.nvfp4, seed=args.seed,
                       experts_source=args.experts_source, experts_stacked=args.experts_stacked,
                       ple_cache_dir=args.ple_cache)
    params = [p for p in model.parameters() if p.requires_grad]
    if world > 1:
        _broadcast_params(params)
    opt = torch.optim.AdamW(params, lr=args.lr, weight_decay=0.0, betas=(0.9, 0.99))
    if ck:
        opt.load_state_dict(torch.load(out / ck["dir"] / "optim.pt", map_location="cpu"))
    elif args.init_optim:
        # 4-Oct: rounds continue the previous round's optimizer too. R1 (3-Oct) restarted Adam on R0's adapter: its
        # first steps move every LoRA entry by ~lr whatever the gradient, and the copy-paste looping began there.
        opt.load_state_dict(torch.load(args.init_optim, map_location="cpu"))
        print(f"optimizer state loaded from {args.init_optim}", flush=True)
    dev = next(model.parameters()).device
    old_lp = old_logprobs(model, processor, recs, rank, world, args, out, dev) if args.clip > 0 else {}
    # --token-norm token: every record's loss is divided by the SAME number, the mean trained tokens per record
    norm_tokens = (sum(len(v) for v in old_lp.values()) / max(1, len(old_lp))) if args.token_norm == "token" and old_lp else None
    log = (out / "train_log.jsonl").open("a", encoding="utf-8")
    stopped = False
    for ep in range(ep0, args.epochs):
        skip = done0 if ep == ep0 else 0
        todo = recs[skip:]
        # each copy takes every world-th record; the lists are padded to one length so every copy reaches every
        # optimizer step (a None slot trains nothing and still joins the step's gradient average)
        mine = todo[rank::world]
        slots = mine + [None] * (math.ceil(len(todo) / world) - len(mine))
        for i, rec in enumerate(slots):
            t0 = time.time()
            loss = b = None
            w = 1.0
            if rec is not None:
                b = to_batch(processor, rec, dev)
                if not b["spans_ok"] or b["n_loss"] == 0 or b["input_ids"].shape[1] > args.max_tokens:
                    log.write(json.dumps({"skip": rec["meta"].get("game"), "tokens": b["input_ids"].shape[1],
                                          "spans_ok": b["spans_ok"], "n_loss": b["n_loss"], "rank": rank}) + "\n")
                    rec = None
            if rec is not None and args.clip > 0 and id_of(rec) not in old_lp:
                # no starting log-probs (it ran out of memory there): it would here too
                log.write(json.dumps({"skip": rec["meta"].get("game"), "tokens": b["input_ids"].shape[1],
                                      "no_old_logprobs": True, "rank": rank}) + "\n")
                rec = None
            if rec is not None:
                w = float(rec.get("meta", {}).get("weight", 1.0))
                _ple_record(args, rec)
                try:
                    lp = token_logprobs(model, b, grad=True)
                    tw = trained_weights(b).to(lp.device)
                    if args.clip > 0:
                        loss, stats = clipped_loss(lp, old_lp[id_of(rec)].to(lp.device), tw, args.clip, args.kl,
                                                   clip_high=args.clip_high, cispo=args.loss == "cispo",
                                                   norm_tokens=norm_tokens)
                        loss = loss * w
                    else:
                        # per-sequence mean over trained tokens, each token weighted by its reply's weight
                        loss = -((tw * lp).sum() / max(1, lp.numel())) * w
                        stats = {}
                    (loss / accum).backward()
                except torch.OutOfMemoryError as exc:
                    # a record that does not fit is skipped, not fatal (multi-hour rounds); this copy drops its
                    # partial gradients for the step so no half-record update is applied
                    lp = loss = None
                    opt.zero_grad(set_to_none=True)
                    import gc
                    gc.collect()
                    torch.cuda.empty_cache()
                    log.write(json.dumps({"skip": rec["meta"].get("game"), "tokens": b["input_ids"].shape[1],
                                          "oom": str(exc)[:200], "rank": rank}) + "\n")
                    log.flush()
                    rec = None
            if (i + 1) % accum == 0 or i == len(slots) - 1:
                if world > 1:
                    _allreduce_grads(params, world)
                lr = args.lr * min(1.0, (step + 1) / max(1, args.warmup)) * \
                    0.5 * (1 + math.cos(math.pi * min(1.0, step / total_steps)))
                for g in opt.param_groups:
                    g["lr"] = lr
                torch.nn.utils.clip_grad_norm_(params, 1.0)
                opt.step()
                opt.zero_grad(set_to_none=True)
                step += 1
                if world > 1 and step - (ck["step"] if ck else 0) <= 2:
                    lo, hi = _copies_agree(params)
                    if lo != hi:
                        raise RuntimeError(f"data-parallel copies differ after step {step}: {lo!r} vs {hi!r}")
                done = min(len(recs), skip + (i + 1) * world)
                nxt = (ep, done) if done < len(recs) else (ep + 1, 0)
                if args.ckpt_every and rank == 0 and step % args.ckpt_every == 0 and nxt[0] < args.epochs:
                    save_ckpt(model, opt, out, {"order": sig, "epoch": nxt[0], "done": nxt[1], "step": step,
                                                "rows": nxt[0] * len(recs) + nxt[1], "records": len(recs),
                                                "world": world})
                stopped = bool(args.stop_after and step >= args.stop_after)
            if rec is not None:
                log.write(json.dumps({"epoch": ep, "step": step, "game": rec["meta"].get("game"), "loss": loss.item(),
                                      "pass": rec["meta"].get("pass"), "adv": rec["meta"].get("advantage"), **stats,
                                      "tokens": b["input_ids"].shape[1], "n_loss": b["n_loss"], "w": w,
                                      "sec": round(time.time() - t0, 1), "rank": rank,
                                      "mem_gib": [round(torch.cuda.max_memory_allocated(k) / 2**30, 1)
                                                  for k in range(torch.cuda.device_count())]}) + "\n")
            log.flush()
            if stopped:
                break
        if stopped:
            break
    if world > 1:
        dist.barrier()
    if stopped:
        print(f"stopped after step {step} (--stop-after); rerun into {out} to resume", flush=True)
    elif rank == 0:
        model.save_pretrained(out)
        torch.save(opt.state_dict(), out / "optim.pt")        # the next round continues it (--init-optim)
        sha = adapter_sha(out)
        (out / "ADAPTER.json").write_text(json.dumps({"sha": sha, "rank": args.rank, "alpha": args.alpha,
                                                      "lr": args.lr, "records": len(recs), "steps": step, "dp": world,
                                                      "clip": args.clip, "kl": args.kl, "clip_high": args.clip_high,
                                                      "loss": args.loss, "token_norm": args.token_norm,
                                                      "init_adapter": args.init_adapter, "init_optim": args.init_optim,
                                                      "target_regex": TARGET_REGEX, "model": args.model}, indent=1))
        print("saved adapter", sha, flush=True)
        clear_ckpt(out)
    if world > 1:
        dist.destroy_process_group()
    return 0


def mode_check(args) -> int:
    from transformers import AutoProcessor
    processor = AutoProcessor.from_pretrained(args.hf)
    recs = load_records(args.records, limit=0 if args.min_tokens else 1)
    if args.min_tokens:          # pick the shortest record at or above this length (memory / speed ladder)
        sized = sorted((len(render.render(processor, r)["input_ids"]), i) for i, r in enumerate(recs))
        pick = next((i for n, i in sized if n >= args.min_tokens), sized[-1][1])
        rec = recs[pick]
    else:
        rec = recs[0]
    model = load_model(args.model, args.gpus, args.gpu_gib, args.rank, args.alpha, attn=args.attn,
                       fast=bool(args.fast), offload=bool(args.offload), nvfp4=args.nvfp4)
    dev = next(model.parameters()).device
    b = to_batch(processor, rec, dev)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    mem = lambda: [round(torch.cuda.max_memory_allocated(i) / 2**30, 1) for i in range(torch.cuda.device_count())]
    t0 = time.time()
    with torch.no_grad():
        lp0 = token_logprobs(model, b)
    torch.cuda.synchronize()
    fwd = time.time() - t0
    (out / "trained_logprobs.json").write_text(json.dumps({
        "input_ids": b["input_ids"][0].tolist(), "loss_positions": b["loss_mask"][0].nonzero().squeeze(-1).tolist(),
        "logprobs": lp0.tolist(), "forward_sec": fwd}))
    print(f"tokens {b['input_ids'].shape[1]}, trained {b['n_loss']}, spans_ok {b['spans_ok']}, "
          f"mean logprob {lp0.mean().item():.4f}, forward {fwd:.1f}s, peak GiB {mem()}", flush=True)
    if args.fast:
        import fast_qsa
        if fast_qsa.TIE_STATS is not None:      # ARC3_QSA_TIE_STATS=1: ties at the sparse-attention cut
            print("qsa selection ties:", fast_qsa.TIE_STATS, "ref picker" if fast_qsa.REF_SELECT else "", flush=True)
    if args.ref_logprobs:        # same record through another path (e.g. the reference code): compare per token
        ref = json.loads(Path(args.ref_logprobs).read_text())
        same_ids = ref["input_ids"] == b["input_ids"][0].tolist()
        r, f = torch.tensor(ref["logprobs"]), lp0.float().cpu()
        if same_ids and r.shape == f.shape:
            d = (r - f).abs()
            print(f"vs reference: same tokens, mean |dlogp| {d.mean().item():.4f}, max {d.max().item():.3f}, "
                  f"mean logp {r.mean().item():.4f} -> {f.mean().item():.4f}", flush=True)
            (out / "COMPARE.json").write_text(json.dumps({"mean_abs": d.mean().item(), "max_abs": d.max().item(),
                                                          "ref_mean": r.mean().item(), "new_mean": f.mean().item()}))
        else:
            print(f"vs reference: different tokens ({len(ref['input_ids'])} vs {b['input_ids'].shape[1]})", flush=True)
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=args.lr)
    losses = []
    for s in range(args.steps):
        t0 = time.time()
        prof = None
        if s == args.profile_step:          # where the step's GPU time goes (top kernels by CUDA time)
            prof = torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU,
                                                      torch.profiler.ProfilerActivity.CUDA])
            prof.__enter__()
        loss = -token_logprobs(model, b, grad=True).mean()
        loss.backward()
        opt.step()
        opt.zero_grad(set_to_none=True)
        losses.append(loss.item())
        if prof is not None:
            torch.cuda.synchronize()
            prof.__exit__(None, None, None)
            table = prof.key_averages().table(sort_by="cuda_time_total", row_limit=30)
            (out / "PROFILE.txt").write_text(table)
            print(table, flush=True)
        print(f"step {s} loss {loss.item():.4f} ({time.time()-t0:.1f}s) mem "
              f"{[round(torch.cuda.max_memory_allocated(i)/2**30,1) for i in range(torch.cuda.device_count())]}",
              flush=True)
    ok = len(losses) >= 2 and losses[-1] < losses[0] - 1e-3
    model.save_pretrained(out / "adapter")
    (out / "CHECK.json").write_text(json.dumps({"losses": losses, "loss_falls": ok, "forward_sec": fwd,
                                                "tokens": int(b["input_ids"].shape[1]), "n_loss": b["n_loss"],
                                                "adapter_sha": adapter_sha(out / "adapter")}, indent=1))
    print("CHECK", "PASS" if ok else "FAIL", losses, flush=True)
    if args.ladder:
        ladder(model, processor, args, out, dev)
    return 0 if ok else 1


def ladder(model, processor, args, out: Path, dev) -> None:
    """Forward (no grad) and one forward+backward on the shortest record at or above each length: time + peak GiB."""
    import gc
    recs = load_records(args.ladder_records or args.records)
    sized = sorted((len(render.render(processor, r)["input_ids"]), i) for i, r in enumerate(recs))
    print("ladder records:", len(recs), "longest", sized[-1][0] if sized else 0, flush=True)
    n_gpu = torch.cuda.device_count()
    mem = lambda: [round(torch.cuda.max_memory_allocated(i) / 2**30, 1) for i in range(n_gpu)]
    rows = []
    for target in [int(x) for x in args.ladder.split(",") if x.strip()]:
        pick = next((i for n, i in sized if n >= target), None)
        if pick is None:
            rows.append({"target": target, "skip": "no record that long"})
            continue
        b = to_batch(processor, recs[pick], dev)
        row = {"target": target, "tokens": int(b["input_ids"].shape[1]), "trained": b["n_loss"],
               "game": recs[pick].get("meta", {}).get("game")}
        for i in range(n_gpu):
            torch.cuda.reset_peak_memory_stats(i)
        t0 = time.time()
        with torch.no_grad():
            lp = token_logprobs(model, b)
        torch.cuda.synchronize()
        row.update(forward_sec=round(time.time() - t0, 1), forward_gib=mem(), mean_logp=round(lp.mean().item(), 4))
        for i in range(n_gpu):
            torch.cuda.reset_peak_memory_stats(i)
        t0 = time.time()
        try:
            loss = -token_logprobs(model, b, grad=True).mean()
            loss.backward()
            torch.cuda.synchronize()
            row.update(step_sec=round(time.time() - t0, 1), step_gib=mem())
        except torch.OutOfMemoryError as exc:
            row.update(step="OOM", step_gib=mem(), error=str(exc)[:300])
        loss = None
        model.zero_grad(set_to_none=True)
        gc.collect()
        torch.cuda.empty_cache()
        rows.append(row)
        print("ladder", json.dumps(row), flush=True)
        (out / "LADDER.json").write_text(json.dumps(rows, indent=1))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["train", "check"])
    ap.add_argument("--model", required=True, help="HF-layout checkpoint dir (BF16 or dequantized served experts)")
    ap.add_argument("--hf", required=True, help="processor dir (tokenizer, chat template, preprocessor)")
    ap.add_argument("--records", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--gpus", type=int, default=8)
    ap.add_argument("--gpu-gib", type=int, default=78)
    ap.add_argument("--rank", type=int, default=32)
    ap.add_argument("--alpha", type=int, default=64)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--accum", type=int, default=8)
    ap.add_argument("--warmup", type=int, default=5)
    ap.add_argument("--max-tokens", type=int, default=131072)
    ap.add_argument("--steps", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0, help="train on the first N shuffled records (0 = all)")
    ap.add_argument("--init-adapter", default="", help="continue from this adapter (the previous round)")
    ap.add_argument("--init-optim", default="", help="train: continue the previous round's optimizer (its optim.pt)")
    ap.add_argument("--clip", type=float, default=0.0, help="train: > 0 = clipped relative-credit update (PPO ratio "
                    "to the round's starting adapter, e.g. 0.2); records' weights are advantages and may be negative")
    ap.add_argument("--kl", type=float, default=0.0, help="train: k3 KL penalty to the round's starting adapter")
    ap.add_argument("--clip-high", type=float, default=None, help="train (--clip): upper clip bound 1 + this (DAPO clip-higher, e.g. 0.28; default = --clip)")
    ap.add_argument("--loss", default="ppo", choices=["ppo", "cispo"], help="train (--clip): ppo = clipped objective; cispo = clipped ratio as a stop-gradient weight on A * log p (every token keeps its gradient)")
    ap.add_argument("--token-norm", default="record", choices=["record", "token"], help="train (--clip): record = mean over each record's trained tokens; token = divide by the dataset's mean trained tokens per record")
    ap.add_argument("--dp", type=int, default=1, help="train: copies of the model on gpus/dp cards each "
                    "(every dp-th record each, gradients averaged per step)")
    ap.add_argument("--longest", action="store_true", help="train: longest records first (memory tests)")
    ap.add_argument("--ckpt-every", type=int, default=0, help="train: keep a resumable checkpoint in --out every N "
                    "optimizer steps; the same command rerun into the same --out resumes there (Spot VMs; 0 = off)")
    ap.add_argument("--stop-after", type=int, default=0, help="train: stop after N optimizer steps (resume tests)")
    ap.add_argument("--attn", default="", help="attn_implementation (e.g. flex_attention); default = model default")
    ap.add_argument("--fast", type=int, default=1, help="1 = fast_qsa.py long-sequence path (0 = reference code)")
    ap.add_argument("--offload", type=int, default=1, help="1 = decoder-layer inputs wait in host RAM")
    ap.add_argument("--nvfp4", default="", help="served NVFP4 checkpoint dir: train through its experts (plan §3)")
    ap.add_argument("--experts-source", default="", choices=["", "gpu", "host", "mmap"],
                    help="train: where packed experts wait between uses (nvfp4_experts.SOURCE; mmap = one shared page-"
                         "cache copy for every --dp copy, from --experts-stacked)")
    ap.add_argument("--experts-stacked", default="", help="nvfp4_experts.py stack output dir (for --experts-source mmap)")
    ap.add_argument("--ple-cache", default="", help="train: n-gram embeddings per record in this dir (computed first by "
                                                     "ple_cache.precompute if missing); the 51B table is never loaded")
    ap.add_argument("--ref-logprobs", default="", help="check: trained_logprobs.json of the same record to compare")
    ap.add_argument("--min-tokens", type=int, default=0, help="check: use the shortest record of at least N tokens")
    ap.add_argument("--profile-step", type=int, default=-1, help="check: profile this overfit step (-1 = none)")
    ap.add_argument("--ladder", default="", help="check: then time forward/backward at these lengths, e.g. 30000,60000")
    ap.add_argument("--ladder-records", default="", help="check: records glob for the ladder (default --records)")
    args = ap.parse_args()
    if args.mode == "train" and "ARC3_DP_RANK" not in os.environ:
        prepare_out(args)
        if args.ple_cache:
            # the n-gram embeddings first, in their own process: the ~95 GiB table it holds is gone before any
            # training process starts
            import subprocess
            subprocess.run([sys.executable, str(HERE / "ple_cache.py"), "precompute", "--model", args.model,
                            "--hf", args.hf, "--records", args.records, "--out", args.ple_cache], check=True)
        if args.ple_cache or args.nvfp4:
            import ple_cache
            dt, de = bool(args.ple_cache), bool(args.nvfp4)
            ple_cache.model_view(args.model, ple_cache.default_view_dir(args.model, dt, de), drop_table=dt,
                                 drop_experts=de)                                 # once per box, before the copies
        if args.dp > 1:
            return spawn_dp(args)
    return mode_train(args) if args.mode == "train" else mode_check(args)


if __name__ == "__main__":
    raise SystemExit(main())
