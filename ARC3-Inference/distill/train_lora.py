#!/usr/bin/env python3
# Author: Claude Opus 5 (Bubba)
# Date: 17-September-2026
# PURPOSE: Round-1 LoRA SFT trainer for ARC-3 distillation -- fine-tunes Qwen3.8-27B (BF16
#   checkpoint, NOT the NVFP4 one) on the rejection-sampled corpus produced by
#   `distill/extract_sft.py`. Runs on a single NVIDIA GB10 (gx10-a424) where memory is UNIFIED,
#   so an over-allocation invokes the kernel OOM killer instead of raising a catchable torch
#   error -- hence the MemAvailable floor guard before every allocation and the hard sequence
#   cap. Reuses the exact forward/backward recipe proven by the 17-Sep gradient census
#   (`step_bf16.py`): AutoModelForImageTextToText, frozen vision tower, chunked cross-entropy
#   over a detached lm_head, and gradient checkpointing -- both of the latter are REQUIRED, not
#   optional (naive CE OOMs at ~20K tokens, checkpointing-off OOMs at 10K).
# SRP/DRY check: Pass -- the corpus->processor mapping lives in `corpus_adapter.py`, record
#   selection and the test-set fence live in `extract_sft.py`. This module only measures the
#   corpus, builds batches, and runs the optimisation loop. The gradient census is folded in
#   here rather than shipped as a separate pre-flight script so that a silent gradient failure
#   cannot hide between the pre-flight and the run that matters.
"""Round-1 LoRA SFT trainer for ARC-3 distillation on a single GB10."""
from __future__ import annotations

import argparse
import gc
import json
import os
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch
import torch.nn.functional as F
from torch.utils.checkpoint import checkpoint
from transformers import AutoConfig, AutoModelForImageTextToText, AutoProcessor
from peft import LoraConfig, get_peft_model
from peft.tuners.lora import LoraLayer

from corpus_adapter import adapt

# The LoRA target set is fixed by measurement, not taste: 16 self-attention layers plus 48
# gated-delta layers = 208 modules, 39,583,744 trainable params (0.1445%). A different count
# means the model shape changed underneath us and the run must stop.
TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "in_proj_qkv", "in_proj_z", "out_proj"]
EXPECTED_MODULES = 208
EXPECTED_TRAINABLE = 39_583_744
CE_CHUNK = 2048
MIN_AVAIL_GIB = 16.0
# 49,152 is the measured ceiling on this box. 65,536 kernel-OOM-killed it, taking unrelated
# processes down with it, so this is a hard skip and not a truncation.
MAX_SEQ = 49_152


def avail() -> float:
    line = [l for l in open("/proc/meminfo") if l.startswith("MemAvailable")][0]
    return round(int(line.split()[1]) / 2**20, 2)


def mem() -> dict:
    return {"cuda_alloc_GiB": round(torch.cuda.memory_allocated() / 2**30, 2),
            "cuda_peak_GiB": round(torch.cuda.max_memory_allocated() / 2**30, 2),
            "sys_avail_GiB": avail()}


def guard(label: str) -> None:
    a = avail()
    if a < MIN_AVAIL_GIB:
        raise MemoryError(
            f"refusing {label}: only {a} GiB MemAvailable (floor {MIN_AVAIL_GIB}); GB10 memory "
            f"is unified, so an overrun invokes the kernel OOM killer rather than raising")


def banner(s: str) -> None:
    print("\n" + "=" * 78 + f"\n== {s}\n" + "=" * 78, flush=True)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus", required=True, help="SFT JSONL from extract_sft.py.")
    p.add_argument("--model", default="/home/son/models/Qwen3.8-27B-BF16")
    p.add_argument("--out-dir", required=True, help="Checkpoint / adapter output dir.")
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--grad-accum", type=int, default=4)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--schedule", choices=["cosine", "linear"], default="cosine")
    p.add_argument("--census-every", type=int, default=2, help="Gradient census every N optimiser steps.")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--max-seq", type=int, default=MAX_SEQ)
    p.add_argument("--measure-only", action="store_true", help="Corpus token stats only; no GPU.")
    args = p.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "train_report.json"
    R: dict = {"model": args.model, "corpus": args.corpus,
               "config": {k: v for k, v in vars(args).items()}}

    def save():
        report_path.write_text(json.dumps(R, indent=2))

    records = [json.loads(l) for l in open(args.corpus, encoding="utf-8")]
    print(f"loaded {len(records)} records from {args.corpus}", flush=True)

    # ---------------------------------------------------------------- corpus measurement
    # Done BEFORE the model load and on CPU. Token length has to be measured through the
    # processor, not a text tokenizer: one board PNG per decision turn expands into a large
    # vision-token block, and a text-only count undercounts badly enough to admit a record
    # that blows the sequence cap.
    banner("CORPUS MEASUREMENT (CPU, through the real processor)")
    proc = AutoProcessor.from_pretrained(args.model)
    tok = proc.tokenizer
    cfg = AutoConfig.from_pretrained(args.model)
    assert getattr(cfg, "quantization_config", None) is None, (
        "checkpoint carries a quantization_config; NVFP4 fake-quantises input activations "
        "under no_grad and severs LoRA gradient on all 7 target projections")

    IM_START = tok.convert_tokens_to_ids("<|im_start|>")
    IM_END = tok.convert_tokens_to_ids("<|im_end|>")
    ASSIST = tok.encode("assistant", add_special_tokens=False)[0]
    IMG_TOK = cfg.image_token_id

    def encode(rec):
        msgs, imgs = adapt(rec["messages"])
        text = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)
        enc = proc(text=[text], images=imgs if imgs else None, return_tensors="pt")
        i_ids = enc["input_ids"][0]
        labels = torch.full_like(i_ids, -100)
        n_sup, i = 0, 0
        while i < len(i_ids) - 1:
            if i_ids[i] == IM_START and i_ids[i + 1] == ASSIST:
                j = i + 2
                while j < len(i_ids) and i_ids[j] != IM_END:
                    j += 1
                e = min(j + 1, len(i_ids))
                labels[i + 2:e] = i_ids[i + 2:e]
                n_sup += e - (i + 2)
                i = j + 1
            else:
                i += 1
        labels[i_ids == IMG_TOK] = -100
        enc["labels"] = labels.unsqueeze(0)
        return enc, int(i_ids.shape[0]), n_sup, len(imgs)

    rows, kept, over, nosup = [], [], [], []
    t0 = time.time()
    for rec in records:
        _enc, seq, nsup, nimg = encode(rec)
        del _enc  # keep lengths, not tensors -- 40 encoded records will not fit in RAM
        row = {"id": rec["id"], "game_id": rec["game_id"], "level": rec.get("level"),
               "tokens": seq, "supervised": nsup, "images": nimg,
               "turns": rec["num_assistant_turns"]}
        rows.append(row)
        if seq > args.max_seq:
            over.append(row)
        elif nsup == 0:
            nosup.append(row)
        else:
            kept.append(row)
    print(f"measured {len(rows)} records in {time.time() - t0:.1f}s", flush=True)

    toks = sorted(r["tokens"] for r in kept)
    stats = {
        "records_in": len(rows),
        "over_max_seq": len(over),
        "over_max_seq_ids": [(r["id"], r["tokens"]) for r in over],
        "zero_supervised_dropped": len(nosup),
        "records_trained": len(kept),
        "turns_trained": sum(r["turns"] for r in kept),
        "images_trained": sum(r["images"] for r in kept),
        "supervised_tokens": sum(r["supervised"] for r in kept),
        "total_tokens": sum(toks),
        "tokens_min": toks[0] if toks else 0,
        "tokens_median": toks[len(toks) // 2] if toks else 0,
        "tokens_max": toks[-1] if toks else 0,
        "games": dict(sorted(Counter(r["game_id"].split("-")[0] for r in kept).items())),
    }
    R["corpus"] = stats
    R["corpus_rows"] = rows
    print(json.dumps({k: v for k, v in stats.items() if k != "over_max_seq_ids"}, indent=1), flush=True)
    if over:
        print(f"SKIPPED {len(over)} record(s) over {args.max_seq} tokens: "
              f"{[(r['id'], r['tokens']) for r in over]}", flush=True)
    save()

    # 241.9 tok/s is the median measured on this box by the 17-Sep census at seq 10,592.
    est_h = stats["total_tokens"] * args.epochs / 241.9 / 3600
    print(f"\nETA estimate (prior 241.9 tok/s): {est_h:.2f} h for {args.epochs} epoch(s)", flush=True)
    R["eta_estimate_hours_prior"] = round(est_h, 2)
    save()
    if args.measure_only:
        print("--measure-only: stopping before GPU allocation")
        return 0
    if not kept:
        print("no trainable records survived the filters", file=sys.stderr)
        return 1

    # ---------------------------------------------------------------- load
    banner("LOAD")
    guard("load")
    torch.cuda.set_per_process_memory_fraction(0.86)
    R["sys_avail_before_load_GiB"] = avail()
    t0 = time.time()
    model = AutoModelForImageTextToText.from_pretrained(
        args.model, dtype=torch.bfloat16, device_map="cuda:0")
    R["load_seconds"] = round(time.time() - t0, 1)
    print(f"loaded in {R['load_seconds']}s: {type(model).__name__}", flush=True)

    # The vision tower is frozen: this round adapts the reasoning policy, not the perception
    # front-end, and the corpus is far too small to move a vision encoder without damaging it.
    for n, prm in model.named_parameters():
        if "visual" in n:
            prm.requires_grad_(False)

    banner("LoRA")
    model = get_peft_model(model, LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.0, bias="none",
        task_type="CAUSAL_LM", target_modules=TARGETS))
    cond = model.base_model.model
    mm = cond.model
    HEAD_W = cond.lm_head.weight
    HEAD_B = getattr(cond.lm_head, "bias", None)

    matched = Counter()
    for n, mod in model.named_modules():
        if isinstance(mod, LoraLayer):
            matched[n.rsplit(".", 1)[-1]] += 1
    trainable = sum(prm.numel() for prm in model.parameters() if prm.requires_grad)
    n_vis_train = sum(1 for n, prm in model.named_parameters()
                      if "visual" in n and prm.requires_grad)
    model.print_trainable_parameters()
    R["lora"] = {"matched_counts": dict(matched), "matched_total": sum(matched.values()),
                 "trainable_params": trainable, "trainable_vision_params": n_vis_train}
    save()
    assert sum(matched.values()) == EXPECTED_MODULES, \
        f"expected {EXPECTED_MODULES} LoRA modules, got {sum(matched.values())}"
    assert trainable == EXPECTED_TRAINABLE, \
        f"expected {EXPECTED_TRAINABLE} trainable params, got {trainable}"
    assert n_vis_train == 0, "vision tower is not frozen"
    print(f"shape OK: {EXPECTED_MODULES} modules, {trainable:,} trainable, vision frozen")

    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    model.train()

    params = [prm for prm in model.parameters() if prm.requires_grad]
    opt = torch.optim.AdamW(params, lr=args.lr)

    order = list(range(len(kept)))
    rng = random.Random(args.seed)
    rng.shuffle(order)
    by_id = {r["id"]: r for r in records}
    micro_total = len(order) * args.epochs
    total_steps = max(1, -(-micro_total // args.grad_accum))
    # No warmup: at ~10 optimiser steps a warmup phase would consume most of the run. LoRA
    # starts from an identity map (lora_B = 0) so there is no early-step instability to warm
    # past, which is the usual reason for it.
    if args.schedule == "cosine":
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(1, total_steps))
    else:
        sched = torch.optim.lr_scheduler.LinearLR(opt, start_factor=1.0, end_factor=0.0,
                                                  total_iters=max(1, total_steps))
    R["schedule"] = {"total_optimiser_steps": total_steps, "micro_steps": micro_total}
    print(f"plan: {micro_total} micro-steps, grad_accum={args.grad_accum} "
          f"-> {total_steps} optimiser steps", flush=True)

    def hidden_states(b):
        kw = {k: v for k, v in b.items() if k != "labels"}
        return mm(**kw, use_cache=False).last_hidden_state[0]

    def ce_chunk(h, lab):
        return F.cross_entropy(F.linear(h, HEAD_W, HEAD_B).float(), lab, reduction="sum")

    def loss_chunked(h, labels):
        hs, labs = h[:-1], labels[0][1:]
        n = int((labs != -100).sum())
        if n == 0:
            raise ValueError("zero supervised tokens")
        loss = hs.new_zeros((), dtype=torch.float32)
        for i in range(0, hs.shape[0], CE_CHUNK):
            hc, lc = hs[i:i + CE_CHUNK], labs[i:i + CE_CHUNK]
            k = lc != -100
            if bool(k.any()):
                loss = loss + checkpoint(ce_chunk, hc[k], lc[k], use_reentrant=False)
        return loss / n, n

    def census():
        """Per-adapter-type gradient census. A silent gradient failure -- the exact bug the
        NVFP4 checkpoint caused -- looks like a perfectly normal loss curve, so this is the
        only thing that distinguishes learning from an expensive no-op."""
        out = {}
        for which in ("lora_A", "lora_B"):
            d = defaultdict(lambda: {"n": 0, "none": 0, "nonzero": 0, "abs_sum": 0.0})
            for nm, prm in model.named_parameters():
                if f".{which}." not in nm or not prm.requires_grad:
                    continue
                leaf = nm.split(f".{which}")[0].rsplit(".", 1)[-1]
                e = d[leaf]
                e["n"] += 1
                if prm.grad is None:
                    e["none"] += 1
                else:
                    s = float(prm.grad.abs().sum())
                    e["abs_sum"] += s
                    if s > 0:
                        e["nonzero"] += 1
            tot = sum(v["n"] for v in d.values())
            nz = sum(v["nonzero"] for v in d.values())
            out[which] = {"total": tot, "nonzero": nz,
                          "by_type": {k: {**v, "abs_sum": round(v["abs_sum"], 6)}
                                      for k, v in d.items()}}
            print(f"  census {which}: {nz} / {tot} nonzero", flush=True)
        return out

    # ---------------------------------------------------------------- train
    banner("TRAIN")
    log: list[dict] = []
    R["log"] = log
    step = 0
    micro = 0
    tokens_done = 0
    accum_loss = 0.0
    t_start = time.time()
    torch.cuda.reset_peak_memory_stats()
    step0_census = None

    for epoch in range(args.epochs):
        for oi in order:
            row = kept[oi]
            rec = by_id[row["id"]]
            guard(f"micro-step {micro}")
            enc, seq, nsup, nimg = encode(rec)
            batch = {k: (v.to("cuda:0") if torch.is_tensor(v) else v) for k, v in enc.items()}
            t_mb = time.time()
            h = hidden_states(batch)
            loss, n = loss_chunked(h, batch["labels"])
            if micro == 0:
                assert loss.requires_grad, "loss has no grad_fn -- nothing will train"
            (loss / args.grad_accum).backward()
            torch.cuda.synchronize()
            lv = float(loss.detach())
            accum_loss += lv
            tokens_done += seq
            micro += 1
            del h, loss, batch, enc
            print(f"  [e{epoch} micro {micro}/{micro_total}] {row['id']} "
                  f"seq {seq} sup {nsup} img {nimg} loss {lv:.4f} "
                  f"{time.time() - t_mb:.1f}s avail {avail()} GiB", flush=True)

            # The step-0 census runs after the FIRST backward, on a fresh adapter. lora_B must
            # be 208/208 nonzero; lora_A is expected to be 0/208 here because B initialises to
            # zero, so A has no signal path until B moves. This IS the pre-flight.
            if micro == 1:
                step0_census = census()
                R["step0_census"] = step0_census
                save()
                nzb = step0_census["lora_B"]["nonzero"]
                assert nzb == EXPECTED_MODULES, (
                    f"STOP: only {nzb}/{EXPECTED_MODULES} lora_B adapters have nonzero "
                    f"gradient -- training would be a no-op")
                print(f"  PRE-FLIGHT PASS: lora_B {nzb}/{EXPECTED_MODULES} nonzero", flush=True)

            if micro % args.grad_accum == 0 or micro == micro_total:
                # Census BEFORE opt.step(), while this step's gradients are still attached.
                cen = census() if (step % args.census_every == 0) else None
                torch.nn.utils.clip_grad_norm_(params, 1.0)
                opt.step()
                opt.zero_grad(set_to_none=True)
                sched.step()
                step += 1
                el = time.time() - t_start
                tps = tokens_done / el
                rem = (stats["total_tokens"] * args.epochs - tokens_done) / max(tps, 1e-9)
                entry = {"step": step, "epoch": epoch, "micro": micro,
                         "loss": round(accum_loss / args.grad_accum, 4),
                         "lr": opt.param_groups[0]["lr"],
                         "elapsed_s": round(el, 1), "tokens_done": tokens_done,
                         "tokens_per_s": round(tps, 1),
                         "eta_remaining_h": round(rem / 3600, 2),
                         "peak_GiB": round(torch.cuda.max_memory_allocated() / 2**30, 2),
                         "sys_avail_GiB": avail()}
                if cen:
                    entry["census"] = {"lora_A_nonzero": cen["lora_A"]["nonzero"],
                                       "lora_B_nonzero": cen["lora_B"]["nonzero"]}
                log.append(entry)
                print(f"== STEP {step}/{total_steps} loss {entry['loss']:.4f} "
                      f"lr {entry['lr']:.2e} {tps:.1f} tok/s "
                      f"ETA {entry['eta_remaining_h']:.2f}h peak {entry['peak_GiB']} GiB", flush=True)
                accum_loss = 0.0
                save()
                gc.collect()
                torch.cuda.empty_cache()

    R["wall_seconds"] = round(time.time() - t_start, 1)
    R["measured_tokens_per_s"] = round(tokens_done / max(time.time() - t_start, 1e-9), 1)

    banner("SAVE")
    adapter_dir = out_dir / "adapter"
    model.save_pretrained(str(adapter_dir))
    proc.save_pretrained(str(adapter_dir))
    R["adapter_dir"] = str(adapter_dir)
    save()
    print(f"wrote adapter -> {adapter_dir}", flush=True)
    print(f"wrote report  -> {report_path}", flush=True)

    banner("DONE")
    print(f"steps {step} | wall {R['wall_seconds']}s | {R['measured_tokens_per_s']} tok/s")
    if log:
        print(f"loss first -> last: {log[0]['loss']:.4f} -> {log[-1]['loss']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
