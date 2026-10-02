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
               attn: str = "", fast: bool = True, offload: bool = True, nvfp4: str = ""):
    from peft import LoraConfig, PeftModel, get_peft_model
    from transformers import AutoModelForImageTextToText
    if nvfp4:
        # the served NVFP4 experts (nvfp4_experts.py): the BF16 expert keys are skipped, the packed ones load after
        import nvfp4_experts
        nvfp4_experts.install_placeholder()
    dmap = device_map_for(model_dir, n_gpus, gpu_gib, even_layers=bool(nvfp4))
    extra = {"attn_implementation": attn} if attn else {}
    model = AutoModelForImageTextToText.from_pretrained(model_dir, dtype=torch.bfloat16, device_map=dmap, **extra)
    print("attention implementation:", getattr(model.config, "_attn_implementation", None), flush=True)
    if nvfp4:
        print("nvfp4 experts:", nvfp4_experts.load_packed(model, nvfp4), flush=True)
    run_table_on_cpu(model)
    model.config.use_cache = False
    for p in model.parameters():
        p.requires_grad_(False)
    if adapter:
        model = PeftModel.from_pretrained(model, adapter, is_trainable=True)
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
def mode_train(args) -> int:
    from transformers import AutoProcessor
    processor = AutoProcessor.from_pretrained(args.hf)
    recs = load_records(args.records)
    random.Random(args.seed).shuffle(recs)
    if args.limit:
        recs = recs[:args.limit]
    print(f"{len(recs)} records", flush=True)
    model = load_model(args.model, args.gpus, args.gpu_gib, args.rank, args.alpha, args.init_adapter, args.attn,
                       fast=bool(args.fast), offload=bool(args.offload), nvfp4=args.nvfp4)
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=args.lr, weight_decay=0.0, betas=(0.9, 0.99))
    dev = next(model.parameters()).device
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log = (out / "train_log.jsonl").open("a", encoding="utf-8")
    step, acc = 0, 0
    total = args.epochs * len(recs)
    for ep in range(args.epochs):
        for rec in recs:
            t0 = time.time()
            b = to_batch(processor, rec, dev)
            if not b["spans_ok"] or b["n_loss"] == 0 or b["input_ids"].shape[1] > args.max_tokens:
                log.write(json.dumps({"skip": rec["meta"].get("game"), "tokens": b["input_ids"].shape[1],
                                      "spans_ok": b["spans_ok"], "n_loss": b["n_loss"]}) + "\n")
                continue
            w = float(rec.get("meta", {}).get("weight", 1.0))
            try:
                lp = token_logprobs(model, b, grad=True)
                tw = trained_weights(b).to(lp.device)
                # per-sequence mean over trained tokens, each token weighted by its reply's weight (level efficiency)
                loss = -((tw * lp).sum() / max(1, lp.numel())) * w
                (loss / args.accum).backward()
            except torch.OutOfMemoryError as exc:
                # a record that does not fit is skipped, not fatal (multi-hour rounds); its partial gradients are
                # dropped with the accumulated ones of this step so no half-record update is applied
                lp = loss = None
                opt.zero_grad(set_to_none=True)
                import gc
                gc.collect()
                torch.cuda.empty_cache()
                log.write(json.dumps({"skip": rec["meta"].get("game"), "tokens": b["input_ids"].shape[1],
                                      "oom": str(exc)[:200]}) + "\n")
                log.flush()
                acc = (acc // args.accum) * args.accum
                continue
            acc += 1
            if acc % args.accum == 0:
                lr = args.lr * min(1.0, (step + 1) / max(1, args.warmup)) * \
                    0.5 * (1 + math.cos(math.pi * min(1.0, step / max(1, total / args.accum))))
                for g in opt.param_groups:
                    g["lr"] = lr
                torch.nn.utils.clip_grad_norm_(params, 1.0)
                opt.step()
                opt.zero_grad(set_to_none=True)
                step += 1
            log.write(json.dumps({"epoch": ep, "step": step, "game": rec["meta"].get("game"), "loss": loss.item(),
                                  "tokens": b["input_ids"].shape[1], "n_loss": b["n_loss"], "w": w,
                                  "sec": round(time.time() - t0, 1),
                                  "mem_gib": [round(torch.cuda.max_memory_allocated(i) / 2**30, 1)
                                              for i in range(torch.cuda.device_count())]}) + "\n")
            log.flush()
    model.save_pretrained(out)
    sha = adapter_sha(out)
    (out / "ADAPTER.json").write_text(json.dumps({"sha": sha, "rank": args.rank, "alpha": args.alpha,
                                                  "lr": args.lr, "records": len(recs), "steps": step,
                                                  "target_regex": TARGET_REGEX, "model": args.model}, indent=1))
    print("saved adapter", sha, flush=True)
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
    ap.add_argument("--attn", default="", help="attn_implementation (e.g. flex_attention); default = model default")
    ap.add_argument("--fast", type=int, default=1, help="1 = fast_qsa.py long-sequence path (0 = reference code)")
    ap.add_argument("--offload", type=int, default=1, help="1 = decoder-layer inputs wait in host RAM")
    ap.add_argument("--nvfp4", default="", help="served NVFP4 checkpoint dir: train through its experts (plan §3)")
    ap.add_argument("--ref-logprobs", default="", help="check: trained_logprobs.json of the same record to compare")
    ap.add_argument("--min-tokens", type=int, default=0, help="check: use the shortest record of at least N tokens")
    ap.add_argument("--profile-step", type=int, default=-1, help="check: profile this overfit step (-1 = none)")
    ap.add_argument("--ladder", default="", help="check: then time forward/backward at these lengths, e.g. 30000,60000")
    ap.add_argument("--ladder-records", default="", help="check: records glob for the ladder (default --records)")
    args = ap.parse_args()
    return mode_train(args) if args.mode == "train" else mode_check(args)


if __name__ == "__main__":
    raise SystemExit(main())
