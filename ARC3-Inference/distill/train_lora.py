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
# Must be set before torch initialises its allocator. At the 17-Sep round-1 OOM, 7.43 GiB of a
# 104.6 GiB cap was reserved-but-unallocated -- pure fragmentation, 7% of the budget.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch
from transformers import AutoConfig, AutoModelForImageTextToText, AutoProcessor
from peft import LoraConfig, get_peft_model
from peft.tuners.lora import LoraLayer

from sft_batch import build_encoder, loss_chunked

# The LoRA target set is fixed by measurement, not taste: 16 self-attention layers plus 48
# gated-delta layers = 208 modules, 39,583,744 trainable params (0.1445%). A different count
# means the model shape changed underneath us and the run must stop.
TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "in_proj_qkv", "in_proj_z", "out_proj"]
EXPECTED_MODULES = 208
EXPECTED_TRAINABLE = 39_583_744
# The floor exists to stop a unified-memory overrun reaching the kernel OOM killer. It must be
# consistent with the allocator cap or it is not a safety boundary, just a latent abort:
# set_per_process_memory_fraction(0.86) caps torch at 104.6 GiB of 121.63, so MemAvailable can
# never exceed ~17 GiB while torch is near its cap, and ~13 GiB once the ~4 GiB of system
# processes are counted. A 16.0 floor was therefore unreachable for the longest records, and it
# aborted round 1 at step 3/8 -- on a micro-step that had just COMPLETED at 12.3 GiB.
# 8.0 is defensible because the cap, not the floor, is what bounds this process, and because the
# only bystanders on this box are hermes-agent and two monitor scripts (~100 MB combined). If
# something large is running -- the 56 GB download that was lost on 16-Sep, say -- raise it.
MIN_AVAIL_GIB = 8.0
# The sequence ceiling is MEASURED, not assumed, because it has been wrong twice. 65,536
# kernel-OOM-killed the box on 16-Sep. A brief then carried "49,152 max safe" forward, but the
# 16-Sep measurement doc had already bracketed the real ceiling between 35,258 (peak 88.80 GiB,
# fits) and 46,849 (does not fit) -- and 46,849 duly OOMed on the first round-1 attempt. 35,258
# is the largest length directly measured to fit under full fwd + chunked CE + bwd + AdamW, so
# it is the conservative default; --probe raises it to whatever this box actually tolerates.
MAX_SEQ = 35_258


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
    p.add_argument("--save-every", type=int, default=2,
                   help="Save a step-tagged adapter every N optimiser steps. Round 1 spent 29 "
                        "minutes of GPU on 3 real steps and died holding no model artifact.")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--max-seq", type=int, default=MAX_SEQ)
    p.add_argument("--probe", action="store_true",
                   help="Before training, measure the real sequence ceiling by running a full "
                        "fwd+bwd on the longest records descending until one fits.")
    p.add_argument("--probe-ladder", default=None,
                   help="Comma-separated descending lengths to probe. Default: the longest 4 "
                        "record lengths in the corpus that are <= --probe-start.")
    p.add_argument("--probe-start", type=int, default=45_056,
                   help="Do not probe above this; 46,849 is already measured NOT to fit.")
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
    cfg = AutoConfig.from_pretrained(args.model)
    assert getattr(cfg, "quantization_config", None) is None, (
        "checkpoint carries a quantization_config; NVFP4 fake-quantises input activations "
        "under no_grad and severs LoRA gradient on all 7 target projections")

    encode = build_encoder(proc, cfg)

    # When probing, hold on to everything up to --probe-start; the real cap is decided on the
    # GPU a few minutes from now and records dropped here could not be recovered.
    measure_ceiling = args.probe_start if args.probe else args.max_seq
    rows, kept, over, nosup = [], [], [], []
    t0 = time.time()
    for rec in records:
        _enc, seq, nsup, nimg = encode(rec)
        del _enc  # keep lengths, not tensors -- 40 encoded records will not fit in RAM
        row = {"id": rec["id"], "game_id": rec["game_id"], "level": rec.get("level"),
               "tokens": seq, "supervised": nsup, "images": nimg,
               "turns": rec["num_assistant_turns"]}
        rows.append(row)
        if seq > measure_ceiling:
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
        print(f"SKIPPED {len(over)} record(s) over {measure_ceiling} tokens: "
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

    by_id = {r["id"]: r for r in records}

    def hidden_states(b):
        kw = {k: v for k, v in b.items() if k != "labels"}
        return mm(**kw, use_cache=False).last_hidden_state[0]

    def loss_for(h, labels):
        return loss_chunked(h, labels, HEAD_W, HEAD_B, use_checkpoint=True)

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

    def batch_for(rec):
        enc, seq, nsup, nimg = encode(rec)
        return ({k: (v.to("cuda:0") if torch.is_tensor(v) else v) for k, v in enc.items()},
                seq, nsup, nimg)

    def fwd_bwd(batch):
        """One full forward + chunked CE + backward. Returns (loss value, supervised count)."""
        h = hidden_states(batch)
        loss, n = loss_for(h, batch["labels"])
        (loss / args.grad_accum).backward()
        torch.cuda.synchronize()
        lv = float(loss.detach())
        del h, loss
        return lv, n

    def release():
        """Return cached allocator blocks. Deliberately does NOT touch gradients: called every
        micro-step, a zero_grad here would wipe the accumulation window and silently turn every
        grad_accum window into a single-record step -- with a loss curve that looks normal. It
        also must not reset peak stats, which would turn peak_GiB from a running max into a
        per-window figure."""
        gc.collect()
        torch.cuda.empty_cache()

    def clear():
        """Full reset between standalone attempts (probe, or a discarded accumulation window)."""
        opt.zero_grad(set_to_none=True)
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()

    # ---------------------------------------------------------------- probe
    # The sequence ceiling has now been wrong twice from extrapolation, so measure it. Probing
    # DESCENDING means the first success ends the probe, and every success also records a
    # peak-memory point -- the pass/fail boundary alone would not tell round 2 anything.
    final_cap = args.max_seq
    if args.probe:
        banner("PROBE - measuring the real sequence ceiling on this box")
        if args.probe_ladder:
            ladder = [int(x) for x in args.probe_ladder.split(",")]
        else:
            ladder = sorted({r["tokens"] for r in kept if r["tokens"] <= args.probe_start},
                            reverse=True)[:4]
        by_tokens = {r["tokens"]: r for r in kept}
        probe_log = []
        for L in ladder:
            row = by_tokens[L]
            clear()
            guard(f"probe {L}")
            print(f"  probing {L} tokens ({row['id']}) ...", flush=True)
            t = time.time()
            try:
                lv, n = fwd_bwd(batch_for(by_id[row["id"]])[0])
            except torch.OutOfMemoryError as e:
                clear()
                probe_log.append({"tokens": L, "fits": False, "error": str(e).split(".")[0]})
                print(f"  {L}: DOES NOT FIT", flush=True)
                continue
            peak = round(torch.cuda.max_memory_allocated() / 2**30, 2)
            dt = round(time.time() - t, 1)
            probe_log.append({"tokens": L, "fits": True, "peak_GiB": peak,
                              "seconds": dt, "loss": round(lv, 4)})
            print(f"  {L}: FITS | peak {peak} GiB | {dt}s | {L/dt:.1f} tok/s", flush=True)
            final_cap = L
            break
        clear()
        R["probe"] = {"ladder": ladder, "results": probe_log, "measured_cap": final_cap}
        save()
        if not any(r["fits"] for r in probe_log):
            print(f"  no probed length fit; falling back to the measured-safe default "
                  f"{args.max_seq}", flush=True)
            final_cap = args.max_seq
        print(f"MEASURED CAP: {final_cap} tokens", flush=True)

    # ---------------------------------------------------------------- final corpus + schedule
    dropped_by_cap = [r for r in kept if r["tokens"] > final_cap]
    kept = [r for r in kept if r["tokens"] <= final_cap]
    if dropped_by_cap:
        print(f"dropped {len(dropped_by_cap)} record(s) over the {final_cap}-token cap: "
              f"{[(r['id'], r['tokens']) for r in dropped_by_cap]}", flush=True)
    if not kept:
        print("no records survive the measured cap", file=sys.stderr)
        return 1

    # Micro-step 1 is pinned to the SHORTEST record so the step-0 gradient census -- the
    # pre-flight that has to pass before anything else matters -- executes before the run's
    # riskiest allocation. On the first round-1 attempt a long record OOMed inside the first
    # backward and the census never ran at all.
    order = sorted(range(len(kept)), key=lambda i: kept[i]["tokens"])
    head, tail = order[:1], order[1:]
    random.Random(args.seed).shuffle(tail)
    order = head + tail

    micro_total = len(order) * args.epochs
    total_steps = max(1, -(-micro_total // args.grad_accum))
    # No warmup: at this many optimiser steps a warmup phase would consume most of the run, and
    # LoRA starts from an identity map (lora_B = 0) so there is no early-step instability to
    # warm past -- which is the usual reason for it.
    if args.schedule == "cosine":
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(1, total_steps))
    else:
        sched = torch.optim.lr_scheduler.LinearLR(opt, start_factor=1.0, end_factor=0.0,
                                                  total_iters=max(1, total_steps))

    final_tokens = sum(r["tokens"] for r in kept) * args.epochs
    R["final_corpus"] = {
        "cap": final_cap,
        "records": len(kept),
        "turns": sum(r["turns"] for r in kept),
        "images": sum(r["images"] for r in kept),
        "total_tokens": sum(r["tokens"] for r in kept),
        "dropped_by_cap": [(r["id"], r["tokens"]) for r in dropped_by_cap],
        "first_record_pinned_shortest": kept[order[0]]["id"],
    }
    R["schedule"] = {"total_optimiser_steps": total_steps, "micro_steps": micro_total}
    save()
    print(f"plan: {len(kept)} records / {micro_total} micro-steps, "
          f"grad_accum={args.grad_accum} -> {total_steps} optimiser steps, "
          f"{final_tokens:,} tokens", flush=True)

    # ---------------------------------------------------------------- train
    banner("TRAIN")
    log: list[dict] = []
    R["log"] = log
    # Per-micro-step record. The order is FIXED across epochs, so every record is re-visited
    # once per epoch and `micro_log` is the one training-side signal free of the accumulation-
    # window confound that made round 1's step curve unreadable: round 1's step-to-step
    # differences were dominated by WHICH records landed in each window (within-window spread
    # 0.4866-0.6599, larger than any step delta). Grouped by record id, this is the same
    # record at four points in training -- a paired comparison, not a moving average.
    micro_log: list[dict] = []
    R["micro_log"] = micro_log
    step = 0
    micro = 0
    in_window = 0
    tokens_done = 0
    accum_loss = 0.0
    micro_seconds: list[float] = []
    oom_skipped: list[tuple] = []
    t_start = time.time()
    torch.cuda.reset_peak_memory_stats()
    step0_census = None
    total_planned_tokens = sum(r["tokens"] for r in kept) * args.epochs

    def do_step(epoch):
        nonlocal step, in_window, accum_loss
        # Census BEFORE opt.step(), while this step's gradients are still attached.
        cen = census() if (step % args.census_every == 0) else None
        torch.nn.utils.clip_grad_norm_(params, 1.0)
        opt.step()
        opt.zero_grad(set_to_none=True)
        sched.step()
        step += 1
        el = time.time() - t_start
        tps = tokens_done / el
        rem = (total_planned_tokens - tokens_done) / max(tps, 1e-9)
        # NOTE: loss is divided by the fixed grad_accum, so a short window -- the final one, or
        # one shortened by an OOM discard -- under-weights its step. Recorded rather than
        # corrected, so the curve stays comparable across steps; `loss_window_mean` is the
        # per-record figure to read instead when `window` != grad_accum.
        entry = {"step": step, "epoch": epoch, "micro": micro, "window": in_window,
                 "loss": round(accum_loss / args.grad_accum, 4),
                 "loss_window_mean": round(accum_loss / max(in_window, 1), 4),
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
              f"(window {in_window}, mean {entry['loss_window_mean']:.4f}) "
              f"lr {entry['lr']:.2e} {tps:.1f} tok/s "
              f"ETA {entry['eta_remaining_h']:.2f}h peak {entry['peak_GiB']} GiB", flush=True)
        accum_loss = 0.0
        in_window = 0
        save()
        if args.save_every and step % args.save_every == 0:
            d = out_dir / f"adapter-step{step}"
            model.save_pretrained(str(d))
            R.setdefault("intermediate_adapters", []).append(str(d))
            print(f"  saved intermediate adapter -> {d}", flush=True)
            save()
        gc.collect()
        torch.cuda.empty_cache()

    for epoch in range(args.epochs):
        for oi in order:
            row = kept[oi]
            rec = by_id[row["id"]]
            release()
            a_before = avail()
            guard(f"micro-step {micro}")
            t_mb = time.time()
            try:
                batch, seq, nsup, nimg = batch_for(rec)
                h = hidden_states(batch)
                loss, n = loss_for(h, batch["labels"])
                if micro == 0:
                    assert loss.requires_grad, "loss has no grad_fn -- nothing will train"
                (loss / args.grad_accum).backward()
                torch.cuda.synchronize()
                lv = float(loss.detach())
                del h, loss, batch
            except (torch.OutOfMemoryError, MemoryError):
                # A backward that dies partway leaves SOME parameters with gradients. Those are
                # not a valid partial sum, so the whole accumulation window is discarded rather
                # than stepped on -- keeping them would quietly train on garbage.
                oom_skipped.append((row["id"], row["tokens"], a_before))
                clear()
                accum_loss = 0.0
                in_window = 0
                print(f"  [e{epoch}] OOM/low-memory on {row['id']} ({row['tokens']} tokens, "
                      f"{a_before} GiB avail) -- record skipped and the accumulation window "
                      f"discarded", flush=True)
                R["oom_skipped"] = oom_skipped
                save()
                continue
            dt = time.time() - t_mb
            micro_seconds.append(dt)
            micro_log.append({"epoch": epoch, "micro": micro + 1, "id": row["id"],
                              "game": row["game_id"].split("-")[0], "level": row["level"],
                              "tokens": seq, "supervised": nsup, "loss": round(lv, 6),
                              "seconds": round(dt, 1)})
            accum_loss += lv
            tokens_done += seq
            micro += 1
            in_window += 1
            print(f"  [e{epoch} micro {micro}/{micro_total}] {row['id']} "
                  f"seq {seq} sup {nsup} img {nimg} loss {lv:.4f} "
                  f"{dt:.1f}s {seq/dt:.0f} tok/s avail {a_before}->{avail()} GiB", flush=True)

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

            if in_window == args.grad_accum:
                do_step(epoch)

    # An OOM discard means `micro` never reaches `micro_total`, so the tail window cannot be
    # flushed by a counter check inside the loop -- it has to be flushed here or its records
    # are computed and then thrown away.
    if in_window > 0:
        do_step(args.epochs - 1)

    R["wall_seconds"] = round(time.time() - t_start, 1)
    R["measured_tokens_per_s"] = round(tokens_done / max(time.time() - t_start, 1e-9), 1)
    R["micro_step_seconds"] = {
        "n": len(micro_seconds),
        "median": round(sorted(micro_seconds)[len(micro_seconds) // 2], 1) if micro_seconds else None,
        "min": round(min(micro_seconds), 1) if micro_seconds else None,
        "max": round(max(micro_seconds), 1) if micro_seconds else None,
    }
    R["oom_skipped"] = oom_skipped
    R["optimiser_steps_completed"] = step

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
