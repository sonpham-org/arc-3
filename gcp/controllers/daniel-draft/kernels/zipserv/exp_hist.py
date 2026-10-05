"""BF16 exponent histogram of every dense weight a decode step reads (4-Oct-2026, Kernel optimizations thread; Son's go:
"start with the profile run and the ZipServ histogram").

Gate for ZipServ-style lossless BF16 compression (ASPLOS '26, arXiv 2603.17435, TCA-TBE): per weight matrix, the 7 most
common exponents must form a consecutive window (BaseExp+1 .. BaseExp+7, chosen once per matrix); those weights cost
3 + 8 = 11 bits (3-bit code + sign/mantissa), every other weight 3 + 16 = 19 bits. Bits per weight = 11 + 8 * (1 - cover).
The paper reports 95-97% coverage (~11.3 bits) on LLaMA-3 / Mistral. Go/no-go: coverage >= ~95% on the big BF16 matrices.

Runs as a make_bench_notebook.py --pre-script (his venv, before the server; CPU only: raw safetensors headers + numpy
memmap, no torch CUDA except one device-properties query). Reads:
  target   /kaggle/input/models/dfranzen/intel-qwen3.8-flash-next-w4a16-autoround/... (every BF16 tensor of
           model.language_model.* except routed experts, embed_tokens, visual.*; plus lm_head, mtp.*)
  drafter  /kaggle/input/models/cellens/daniel-drafter-tuned/... (every BF16 tensor; the served drafter)
Writes /kaggle/working/zipserv_hist.json (per tensor: file, name, shape, bytes, 256-bin exponent histogram) and prints
JSON summary lines (stdout lines starting with "{" are kept by the pre-script cell).
"""
import glob
import json
import os
import re
import struct
import subprocess
import time

import numpy as np

T0 = time.time()
TARGET_GLOB = "/kaggle/input/models/dfranzen/intel-qwen3.8-flash-next-w4a16-autoround/**/model.safetensors.index.json"
DRAFT_GLOB = "/kaggle/input/models/cellens/daniel-drafter-tuned/**/*.safetensors"
OUT = "/kaggle/working/zipserv_hist.json"
SKIP = re.compile(r"(\.experts\.\d+\.)|embed_tokens|^model\.visual\.|ngram_embedding|layer_multipliers|ngram_heads")
CHUNK = 64 << 20   # elements per numpy pass (128 MB of BF16)


def emit(**kw):
    kw["t"] = round(time.time() - T0, 1)
    print(json.dumps(kw), flush=True)


def header(path):
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        h = json.loads(f.read(n))
    return 8 + n, h


def exp_hist(path, base, off0, off1):
    """256-bin histogram of the BF16 exponent field over bytes [off0, off1) of the data region."""
    mm = np.memmap(path, dtype=np.uint16, mode="r", offset=base + off0, shape=((off1 - off0) // 2,))
    hist = np.zeros(256, dtype=np.int64)
    for i in range(0, mm.shape[0], CHUNK):
        e = ((mm[i:i + CHUNK] >> 7) & 0xFF).astype(np.uint8)
        hist += np.bincount(e, minlength=256)
    return hist


def window7(hist):
    """Best consecutive 7-exponent window: (cover fraction, BaseExp) with exponents BaseExp+1..BaseExp+7."""
    tot = hist.sum()
    if tot == 0:
        return 0.0, -1
    c = np.convolve(hist, np.ones(7, dtype=np.int64), mode="valid")   # c[j] = sum hist[j..j+6]
    j = int(c.argmax())
    return float(c[j] / tot), j - 1


def top7_any(hist):
    tot = hist.sum()
    return float(np.sort(hist)[-7:].sum() / tot) if tot else 0.0


def entropy_bits(hist):
    p = hist[hist > 0] / hist.sum()
    return float(-(p * np.log2(p)).sum())


def scan(files, label, rows):
    for path in files:
        base, h = header(path)
        for name, meta in h.items():
            if name == "__metadata__" or meta.get("dtype") != "BF16" or SKIP.search(name):
                continue
            o0, o1 = meta["data_offsets"]
            hist = exp_hist(path, base, o0, o1)
            cov, be = window7(hist)
            rows.append(dict(src=label, file=os.path.basename(path), name=name, shape=meta["shape"], bytes=o1 - o0,
                             hist=hist.tolist(), cover7=round(cov, 5), base_exp=be, top7_any=round(top7_any(hist), 5),
                             entropy=round(entropy_bits(hist), 3)))


def device_facts():
    out = {}
    try:
        import torch   # his venv; properties only, no kernels
        p = torch.cuda.get_device_properties(0)
        out.update(name=p.name, sms=p.multi_processor_count, total_mem_gb=round(p.total_memory / 2**30, 1),
                   l2_mb=round(getattr(p, "L2_cache_size", 0) / 2**20, 1))
    except Exception as e:
        out["torch_err"] = repr(e)[:300]
    try:
        q = subprocess.run(["nvidia-smi", "--query-gpu=clocks.max.memory,clocks.max.sm,memory.total,driver_version",
                            "--format=csv,noheader"], capture_output=True, text=True, timeout=30)
        out["nvidia_smi"] = q.stdout.strip()
    except Exception as e:
        out["smi_err"] = repr(e)[:200]
    return out


def main():
    emit(stage="device", **device_facts())
    rows = []
    idx = sorted(glob.glob(TARGET_GLOB, recursive=True))
    if idx:
        wm = json.load(open(idx[0]))["weight_map"]
        d = os.path.dirname(idx[0])
        shards = sorted({f for n, f in wm.items() if not SKIP.search(n)})
        emit(stage="target", dir=d, shards=len(shards))
        scan([os.path.join(d, s) for s in shards], "target", rows)
    else:
        emit(stage="target", error="index not found", glob=TARGET_GLOB)
    dfiles = sorted(glob.glob(DRAFT_GLOB, recursive=True))
    emit(stage="drafter", files=[os.path.basename(f) for f in dfiles])
    scan(dfiles, "drafter", rows)
    json.dump(rows, open(OUT, "w"))

    def summ(sel, tag):
        b = sum(r["bytes"] for r in sel)
        if not b:
            return
        cov = sum(r["cover7"] * r["bytes"] for r in sel) / b
        worst = sorted(sel, key=lambda r: r["cover7"])[:3]
        emit(stage="summary", group=tag, tensors=len(sel), gb=round(b / 1e9, 3), cover7_byte_weighted=round(cov, 4),
             bits_per_weight=round(11 + 8 * (1 - cov), 2), saved_gb=round(b / 1e9 * (1 - (11 + 8 * (1 - cov)) / 16), 3),
             min_cover7=round(min(r["cover7"] for r in sel), 4),
             worst=[(r["name"][-60:], r["cover7"], round(r["bytes"] / 1e6, 1)) for r in worst])

    def role(n):
        for k in ("lm_head", "linear_attn.in_proj", "linear_attn.out_proj", "self_attn.indexer", "self_attn",
                  "shared_expert_gate", "shared_expert", "mlp.gate", "hyper_connection", "ple."):
            if k in n:
                return k
        return "other"

    tgt = [r for r in rows if r["src"] == "target" and not r["name"].startswith("mtp.")]
    summ(tgt, "target_all")
    summ([r for r in tgt if r["bytes"] >= 8 << 20], "target_big_ge8MB")
    for k in sorted({role(r["name"]) for r in tgt}):
        summ([r for r in tgt if role(r["name"]) == k], "target:" + k)
    summ([r for r in rows if r["src"] == "drafter"], "drafter_all")
    emit(stage="done", tensors=len(rows), out=OUT)


if __name__ == "__main__":
    main()
