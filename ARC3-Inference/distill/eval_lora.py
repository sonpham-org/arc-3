#!/usr/bin/env python3
# Author: Claude Opus 5 (Bubba)
# Date: 18-September-2026
# PURPOSE: Held-out evaluator for the ARC-3 LoRA adapters -- the measurement round 1 never
#   made. Scores N adapter "arms" (plus the base model, reached by disabling every adapter)
#   against the held-out corpus built by `extract_sft.py --only-games`, i.e. exactly the
#   games training was fenced away from. Loads the 27B ONCE and toggles adapters via PEFT's
#   multi-adapter API, so every arm sees a bit-identical batch: two separate processes would
#   re-encode the images and any preprocessing nondeterminism would land in the delta and
#   read as learning. Reports PAIRED per-record deltas and a token-weighted corpus aggregate,
#   because with ~40 records the between-record spread (round 1 measured 0.4866-0.6599 within
#   a single accumulation window) swamps any plausible effect and unpaired means are useless.
#   Also does a generation round-trip, closing round 1's NOT-VERIFIED #2.
#   Forward-only under no_grad, so the 43,687-token TRAINING cap does not apply -- capping the
#   eval there would rebuild round 1's long-record bias inside the measurement meant to detect it.
# SRP/DRY check: Pass -- the label mask and chunked CE are imported from `sft_batch.py`, the
#   same code the trainer runs; the held-out selection lives in `extract_sft.py`. This module
#   only loads arms, scores, and reports.
"""Base-vs-adapter held-out evaluation for the ARC-3 LoRA rounds."""
from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch
from transformers import AutoConfig, AutoModelForImageTextToText, AutoProcessor
from peft import PeftModel

from sft_batch import build_encoder, loss_chunked

BASE_ARM = "base"
MIN_AVAIL_GIB = 8.0


def avail() -> float:
    line = [l for l in open("/proc/meminfo") if l.startswith("MemAvailable")][0]
    return round(int(line.split()[1]) / 2**20, 2)


def banner(s: str) -> None:
    print("\n" + "=" * 78 + f"\n== {s}\n" + "=" * 78, flush=True)


def release() -> None:
    gc.collect()
    torch.cuda.empty_cache()


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus", required=True, help="Held-out JSONL from extract_sft.py --only-games.")
    p.add_argument("--model", default="/home/son/models/Qwen3.8-27B-BF16")
    p.add_argument("--adapter", action="append", default=[],
                   help="NAME=/path/to/adapter, repeatable. 'base' is always evaluated and is "
                        "not an adapter -- it is every adapter disabled on the same weights.")
    p.add_argument("--out", required=True, help="Output JSON report path.")
    p.add_argument("--subset-arm", action="append", default=[],
                   help="Arm names scored on the --subset-n sample only (the intermediate "
                        "ladder). Arms not listed are scored on the full corpus.")
    p.add_argument("--subset-n", type=int, default=12,
                   help="Size of the deterministic length-spread subset for --subset-arm.")
    p.add_argument("--max-seq", type=int, default=0,
                   help="Drop records over N tokens. 0 = no cap (the default: eval is "
                        "forward-only and is not bound by the training cap).")
    p.add_argument("--measure-only", action="store_true",
                   help="Corpus token stats on CPU, then stop before any GPU allocation.")
    p.add_argument("--throughput-probe", type=int, default=0,
                   help="Score only the first N records (longest first) and extrapolate the "
                        "wall clock, instead of guessing it.")
    p.add_argument("--gen-tokens", type=int, default=96,
                   help="Greedy tokens for the generation round-trip. 0 disables it.")
    p.add_argument("--gen-record", default=None,
                   help="Record id for the generation round-trip (default: shortest).")
    return p.parse_args(argv)


def length_spread_subset(rows, n):
    """Deterministic subset spanning the length range.

    Sorted by token count, then evenly spaced indices. A random sample of 12 from 40 can
    easily miss the long tail entirely, and record length is the strongest confound in this
    corpus -- the intermediate ladder must not be scored on a systematically shorter set than
    the full arms it is compared against.
    """
    ordered = sorted(rows, key=lambda r: r["tokens"])
    if n >= len(ordered):
        return list(ordered)
    idx = [round(i * (len(ordered) - 1) / (n - 1)) for i in range(n)]
    seen, out = set(), []
    for i in idx:
        if i not in seen:
            seen.add(i)
            out.append(ordered[i])
    return out


def main(argv=None) -> int:
    args = _parse_args(argv)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    arms = {}
    for spec in args.adapter:
        if "=" not in spec:
            print(f"--adapter needs NAME=/path, got {spec!r}", file=sys.stderr)
            return 2
        name, path = spec.split("=", 1)
        if name == BASE_ARM:
            print(f"'{BASE_ARM}' is reserved: it is the no-adapter arm", file=sys.stderr)
            return 2
        if not Path(path).exists():
            print(f"adapter path does not exist: {path}", file=sys.stderr)
            return 2
        arms[name] = path
    subset_arms = set(args.subset_arm)
    unknown = subset_arms - set(arms)
    if unknown:
        print(f"--subset-arm names no such arm: {sorted(unknown)}", file=sys.stderr)
        return 2

    R: dict = {"model": args.model, "corpus": args.corpus,
               "config": {k: v for k, v in vars(args).items()},
               "arms": {BASE_ARM: None, **arms}}

    def save():
        out_path.write_text(json.dumps(R, indent=2))

    records = [json.loads(l) for l in open(args.corpus, encoding="utf-8")]
    print(f"loaded {len(records)} held-out records from {args.corpus}", flush=True)

    # ------------------------------------------------------------ corpus measurement (CPU)
    banner("HELD-OUT CORPUS MEASUREMENT (CPU, through the real processor)")
    proc = AutoProcessor.from_pretrained(args.model)
    cfg = AutoConfig.from_pretrained(args.model)
    assert getattr(cfg, "quantization_config", None) is None, (
        "checkpoint carries a quantization_config; the NVFP4 build is not the one trained on")
    encode = build_encoder(proc, cfg)

    rows, skipped = [], []
    t0 = time.time()
    for rec in records:
        _enc, seq, nsup, nimg = encode(rec)
        del _enc
        row = {"id": rec["id"], "game_id": rec["game_id"], "level": rec.get("level"),
               "tokens": seq, "supervised": nsup, "images": nimg,
               "turns": rec["num_assistant_turns"]}
        if nsup == 0 or (args.max_seq and seq > args.max_seq):
            skipped.append(row)
        else:
            rows.append(row)
    print(f"measured {len(records)} records in {time.time() - t0:.1f}s", flush=True)

    toks = sorted(r["tokens"] for r in rows)
    from collections import Counter
    R["corpus"] = {
        "records_in": len(records), "records_scored": len(rows), "skipped": len(skipped),
        "skipped_rows": skipped,
        "turns": sum(r["turns"] for r in rows),
        "supervised_tokens": sum(r["supervised"] for r in rows),
        "total_tokens": sum(toks),
        "tokens_min": toks[0] if toks else 0,
        "tokens_median": toks[len(toks) // 2] if toks else 0,
        "tokens_max": toks[-1] if toks else 0,
        "games": dict(sorted(Counter(r["game_id"].split("-")[0] for r in rows).items())),
    }
    R["corpus_rows"] = rows
    print(json.dumps({k: v for k, v in R["corpus"].items() if k != "skipped_rows"}, indent=1), flush=True)
    save()
    if not rows:
        print("no scorable held-out records", file=sys.stderr)
        return 1
    if args.measure_only:
        print("--measure-only: stopping before GPU allocation")
        return 0

    subset_ids = {r["id"] for r in length_spread_subset(rows, args.subset_n)}
    R["subset_ids"] = sorted(subset_ids)

    # ------------------------------------------------------------ load
    banner("LOAD")
    torch.cuda.set_per_process_memory_fraction(0.86)
    t0 = time.time()
    model = AutoModelForImageTextToText.from_pretrained(
        args.model, dtype=torch.bfloat16, device_map="cuda:0")
    model.eval()
    R["load_seconds"] = round(time.time() - t0, 1)
    print(f"loaded in {R['load_seconds']}s: {type(model).__name__}", flush=True)

    peft_model = None
    for i, (name, path) in enumerate(arms.items()):
        if peft_model is None:
            peft_model = PeftModel.from_pretrained(model, path, adapter_name=name)
        else:
            peft_model.load_adapter(path, adapter_name=name)
        print(f"  adapter loaded: {name} <- {path}", flush=True)
    if peft_model is None:
        print("no adapters given; only the base arm will be scored", flush=True)
    scored_model = peft_model if peft_model is not None else model

    # The trainer calls the language stack directly rather than through the PeftModel wrapper.
    # LoRA injection is in-place at module level so a disabled adapter is still bypassed on
    # this path, but the enable/disable switch must be flipped on the PeftModel object.
    cond = scored_model.base_model.model if peft_model is not None else model
    mm = cond.model
    HEAD_W = cond.lm_head.weight
    HEAD_B = getattr(cond.lm_head, "bias", None)

    def score(batch):
        with torch.no_grad():
            kw = {k: v for k, v in batch.items() if k != "labels"}
            h = mm(**kw, use_cache=False).last_hidden_state[0]
            loss, n = loss_chunked(h, batch["labels"], HEAD_W, HEAD_B, use_checkpoint=False)
            lv = float(loss)
            del h, loss
        return lv, n

    class arm_ctx:
        """Select an arm. `base` disables every adapter on the SAME loaded weights, so the
        base arm is not a different model -- it is this model with the delta switched off."""
        def __init__(self, name):
            self.name = name
            self._cm = None

        def __enter__(self):
            if peft_model is None:
                return
            if self.name == BASE_ARM:
                self._cm = peft_model.disable_adapter()
                self._cm.__enter__()
            else:
                peft_model.set_adapter(self.name)

        def __exit__(self, *exc):
            if self._cm is not None:
                self._cm.__exit__(*exc)
                self._cm = None
            return False

    arm_names = [BASE_ARM] + list(arms)

    # ------------------------------------------------------------ sanity gate
    # Before spending hours: prove the toggle actually changes the number. If base and an
    # adapter arm score IDENTICALLY on the same record, the adapter is not being applied and
    # every downstream figure is a comparison of the model with itself.
    if arms:
        banner("SANITY GATE - does the adapter change the loss at all?")
        probe_row = min(rows, key=lambda r: r["tokens"])
        probe_rec = next(r for r in records if r["id"] == probe_row["id"])
        enc, _, _, _ = encode(probe_rec)
        batch = {k: (v.to("cuda:0") if torch.is_tensor(v) else v) for k, v in enc.items()}
        gate = {}
        for nm in arm_names:
            with arm_ctx(nm):
                lv, n = score(batch)
            gate[nm] = round(lv, 6)
            print(f"  {nm:<16} loss {lv:.6f} over {n} supervised tokens", flush=True)
        del batch, enc
        release()
        R["sanity_gate"] = {"record": probe_row["id"], "losses": gate}
        save()
        identical = [nm for nm in arms if gate[nm] == gate[BASE_ARM]]
        R["sanity_gate"]["arms_identical_to_base"] = identical
        if identical:
            print(f"\nSTOP: arms {identical} score bit-identically to base -- the adapter is "
                  f"not being applied. Refusing to report a model compared with itself.",
                  file=sys.stderr)
            save()
            return 1
        print("  gate PASSED: every adapter arm differs from base", flush=True)
        save()

    # ------------------------------------------------------------ generation round-trip
    if args.gen_tokens and arms:
        banner("GENERATION ROUND-TRIP")
        gen_row = (next((r for r in rows if r["id"] == args.gen_record), None)
                   if args.gen_record else min(rows, key=lambda r: r["tokens"]))
        gen_rec = next(r for r in records if r["id"] == gen_row["id"])
        # Generation must run the FULL image-text-to-text model with the KV cache, not the
        # bare language stack the loss path uses.
        msgs_all = gen_rec["messages"]
        cut = max(i for i, m in enumerate(msgs_all) if m["role"] == "assistant")
        from corpus_adapter import adapt as _adapt
        msgs, imgs = _adapt(msgs_all[:cut])
        text = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        genc = proc(text=[text], images=imgs if imgs else None, return_tensors="pt")
        genc = {k: (v.to("cuda:0") if torch.is_tensor(v) else v) for k, v in genc.items()}
        in_len = genc["input_ids"].shape[1]
        # Assistant turns in this corpus carry `reasoning` + `tool_calls`, not `content` --
        # the policy's output IS a tool call. Record both so the generated text can be judged
        # against what the rollout actually did.
        ref = msgs_all[cut]
        gen_out = {"record": gen_row["id"], "prompt_tokens": in_len,
                   "reference_next_assistant": {
                       "reasoning": ref.get("reasoning"),
                       "tool_calls": ref.get("tool_calls"),
                       "content": ref.get("content")},
                   "outputs": {}}
        for nm in arm_names:
            with arm_ctx(nm):
                with torch.no_grad():
                    t = time.time()
                    ids = scored_model.generate(**genc, max_new_tokens=args.gen_tokens,
                                                do_sample=False, use_cache=True)
            txt = proc.tokenizer.decode(ids[0][in_len:], skip_special_tokens=True)
            gen_out["outputs"][nm] = {"text": txt, "seconds": round(time.time() - t, 1)}
            print(f"  --- {nm} ({gen_out['outputs'][nm]['seconds']}s) ---\n{txt}\n", flush=True)
            release()
        pairs = {nm: gen_out["outputs"][nm]["text"] for nm in arm_names}
        gen_out["differs_from_base"] = {nm: pairs[nm] != pairs[BASE_ARM] for nm in arms}
        R["generation"] = gen_out
        del genc
        release()
        save()

    # ------------------------------------------------------------ scoring
    # Records OUTER, arms INNER. One encode per record, bit-identical batch across arms, and
    # an incremental JSON that leaves usable PAIRED data if this dies at record 30 of 40.
    banner("SCORING - records outer, arms inner")
    order = sorted(rows, key=lambda r: -r["tokens"])
    if args.throughput_probe:
        order = order[:args.throughput_probe]
        print(f"--throughput-probe: scoring {len(order)} record(s), longest first", flush=True)
    per_record = []
    R["per_record"] = per_record
    t_start = time.time()
    by_id = {r["id"]: r for r in records}
    for k, row in enumerate(order, 1):
        want = arm_names if row["id"] in subset_ids else [a for a in arm_names if a not in subset_arms]
        release()
        a_before = avail()
        t_rec = time.time()
        try:
            enc, seq, nsup, nimg = encode(by_id[row["id"]])
            batch = {kk: (v.to("cuda:0") if torch.is_tensor(v) else v) for kk, v in enc.items()}
            ent = {"id": row["id"], "game": row["game_id"].split("-")[0], "level": row["level"],
                   "tokens": seq, "supervised": nsup, "loss": {}}
            for nm in want:
                with arm_ctx(nm):
                    lv, n = score(batch)
                ent["loss"][nm] = round(lv, 6)
                ent["supervised_scored"] = n
            del batch, enc
        except torch.OutOfMemoryError as e:
            release()
            per_record.append({"id": row["id"], "tokens": row["tokens"], "oom": True,
                               "avail_GiB": a_before, "error": str(e).split(".")[0]})
            print(f"[{k}/{len(order)}] {row['id']} {row['tokens']} tok: OOM, skipped", flush=True)
            save()
            continue
        for nm in want:
            if nm != BASE_ARM:
                ent.setdefault("delta_vs_base", {})[nm] = round(
                    ent["loss"][nm] - ent["loss"][BASE_ARM], 6)
        ent["seconds"] = round(time.time() - t_rec, 1)
        ent["avail_GiB"] = a_before
        ent["peak_GiB"] = round(torch.cuda.max_memory_allocated() / 2**30, 2)
        per_record.append(ent)
        dlt = " ".join(f"{nm}{ent.get('delta_vs_base', {}).get(nm, 0):+.4f}" for nm in want if nm != BASE_ARM)
        print(f"[{k}/{len(order)}] {ent['id']} {seq} tok base {ent['loss'][BASE_ARM]:.4f} | "
              f"{dlt} | {ent['seconds']}s | peak {ent['peak_GiB']} GiB avail {a_before}", flush=True)
        save()
        if args.throughput_probe and k == len(order):
            done_tok = sum(e["tokens"] for e in per_record if not e.get("oom"))
            el = time.time() - t_start
            n_arms = len(arm_names)
            tps = done_tok * n_arms / el
            full_tok = sum(r["tokens"] for r in rows)
            print(f"\nMEASURED eval throughput: {tps:.1f} tok/s across {n_arms} arm(s)\n"
                  f"extrapolated full-corpus wall clock: "
                  f"{full_tok * n_arms / tps / 3600:.2f} h", flush=True)
            R["throughput_probe"] = {"records": len(order), "seconds": round(el, 1),
                                     "tokens_per_s_all_arms": round(tps, 1),
                                     "extrapolated_full_hours": round(full_tok * n_arms / tps / 3600, 2)}
            save()
            return 0

    # ------------------------------------------------------------ aggregate
    banner("AGGREGATE")
    scored = [e for e in per_record if not e.get("oom")]
    summary = {}
    for nm in arm_names:
        have = [e for e in scored if nm in e["loss"]]
        if not have:
            continue
        # TOKEN-WEIGHTED is the headline: sum(CE) / sum(supervised tokens). The record-mean is
        # reported beside it and is NOT the same number -- it weights a 40-token record equally
        # with a 4,000-token one. Round 1's phantom 0.1508 was exactly this class of divisor slip.
        sum_ce = sum(e["loss"][nm] * e["supervised_scored"] for e in have)
        sum_n = sum(e["supervised_scored"] for e in have)
        summary[nm] = {
            "records": len(have),
            "supervised_tokens": sum_n,
            "token_weighted_loss": round(sum_ce / sum_n, 6),
            "token_weighted_ppl": round(float(torch.exp(torch.tensor(sum_ce / sum_n))), 4),
            "record_mean_loss": round(sum(e["loss"][nm] for e in have) / len(have), 6),
        }
    # Paired stats: with ~40 records the between-record spread swamps the effect, so the sign
    # count on PAIRED deltas is the informative statistic, not the difference of two means.
    for nm in arms:
        have = [e for e in scored if nm in e["loss"] and BASE_ARM in e["loss"]]
        if not have:
            continue
        d = [e["loss"][nm] - e["loss"][BASE_ARM] for e in have]
        better = sum(1 for x in d if x < 0)
        mean_d = sum(d) / len(d)
        var = sum((x - mean_d) ** 2 for x in d) / (len(d) - 1) if len(d) > 1 else 0.0
        sd = var ** 0.5
        summary[nm]["paired_vs_base"] = {
            "n": len(d),
            "improved": better,
            "worsened": len(d) - better,
            "mean_delta": round(mean_d, 6),
            "sd_delta": round(sd, 6),
            "se_delta": round(sd / len(d) ** 0.5, 6) if len(d) > 1 else None,
            "t_stat": round(mean_d / (sd / len(d) ** 0.5), 3) if sd > 0 and len(d) > 1 else None,
            "min_delta": round(min(d), 6),
            "max_delta": round(max(d), 6),
        }
    R["summary"] = summary
    R["wall_seconds"] = round(time.time() - t_start, 1)
    save()
    print(json.dumps(summary, indent=2), flush=True)
    print(f"\nwrote {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
