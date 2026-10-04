"""qsa_kernel (fused Triton) against fast_qsa.sparse_attention (gathered, float32) on random inputs (GPU).

Author: Claude Opus 5.5 (4-Oct-2026). Picks are built like fast_qsa.select_tokens: per query, the top 512 of its
complete 4-token blocks (random scores here) as token positions, then its own incomplete block's tokens, -1 = empty.
Checks per length: output and dq / dk / dv (relative max difference, cosine), then times fwd and fwd+bwd of both.

  python test_qsa_kernel.py --tokens 4096,32768,115000
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fast_qsa  # noqa: E402
import qsa_kernel  # noqa: E402

H, KVH, D, R, TOPK = 24, 2, 256, 4, 512
DEV = torch.device("cuda")


def picks(s: int, seed: int = 0) -> torch.Tensor:
    g = torch.Generator(device=DEV).manual_seed(seed)
    nb = s // R
    k_sel = min(TOPK, nb)
    out = torch.full((s, k_sel * R + R - 1), -1, dtype=torch.int32, device=DEV)
    ar_r, ar_t = torch.arange(R, device=DEV), torch.arange(R - 1, device=DEV)
    for a in range(0, s, 1024):
        e = min(s, a + 1024)
        qpos = torch.arange(a, e, device=DEV)
        nc = (qpos + 1) // R
        if k_sel:
            sc = torch.rand(e - a, nb, generator=g, device=DEV)
            sc = sc.masked_fill(torch.arange(nb, device=DEV)[None, :] >= nc[:, None], float("-inf"))
            val, blk = sc.topk(k_sel, dim=-1)
            tok = (blk[..., None] * R + ar_r).flatten(1)
            out[a:e, : k_sel * R] = torch.where(torch.isfinite(val).repeat_interleave(R, dim=1), tok, -1).to(torch.int32)
        tail = nc[:, None] * R + ar_t
        out[a:e, k_sel * R:] = torch.where(tail <= qpos[:, None], tail, -1).to(torch.int32)
    return out


def timed(fn, reps: int = 2) -> float:
    best = math.inf
    for _ in range(reps):
        torch.cuda.synchronize()
        t = time.perf_counter()
        fn()
        torch.cuda.synchronize()
        best = min(best, time.perf_counter() - t)
    return round(best, 4)


def one(s: int, compare: bool) -> dict:
    torch.manual_seed(s)
    scale = 1.0 / math.sqrt(D)
    q = (torch.randn(1, H, s, D, device=DEV) * 2).to(torch.bfloat16)
    k = (torch.randn(1, KVH, s, D, device=DEV) * 2).to(torch.bfloat16)
    v = torch.randn(1, KVH, s, D, device=DEV).to(torch.bfloat16)
    idx = picks(s)
    gy = torch.randn(1, s, H, D, device=DEV).to(torch.bfloat16)
    res = {"tokens": s, "picks_per_query": idx.shape[1]}

    def run(fn):
        qq, kk, vv = (x.detach().requires_grad_(True) for x in (q, k, v))
        y = fn(qq, kk, vv, idx, scale)
        y.backward(gy)
        return y.detach().float(), qq.grad.float(), kk.grad.float(), vv.grad.float()

    if compare:
        ref = run(fast_qsa.sparse_attention)
        new = run(qsa_kernel.sparse_attention)
        for name, a, b in zip(("out", "dq", "dk", "dv"), new, ref):
            res[f"{name}_rel_maxdiff"] = round(float((a - b).abs().max() / b.abs().max().clamp_min(1e-12)), 5)
            res[f"{name}_cos"] = round(float(torch.nn.functional.cosine_similarity(a.flatten(), b.flatten(), dim=0)), 6)
        del ref, new
    for name, fn in (("kernel", qsa_kernel.sparse_attention), ("gather", fast_qsa.sparse_attention)):
        if name == "gather" and s > 40000 and not compare:
            continue
        res[f"{name}_fwd_s"] = timed(lambda: fn(q, k, v, idx, scale))

        def fb():
            qq, kk, vv = (x.detach().requires_grad_(True) for x in (q, k, v))
            fn(qq, kk, vv, idx, scale).backward(gy)
        res[f"{name}_fwdbwd_s"] = timed(fb)
    res["peak_gib"] = round(torch.cuda.max_memory_allocated() / 2**30, 1)
    torch.cuda.reset_peak_memory_stats()
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokens", default="4096,32768,115000")
    ap.add_argument("--no-compare-above", type=int, default=200000, help="skip the gather comparison above this length")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    rows = []
    for s in [int(x) for x in a.tokens.split(",")]:
        r = one(s, compare=s <= a.no_compare_above)
        print(json.dumps(r), flush=True)
        rows.append(r)
    if a.out:
        Path(a.out).write_text(json.dumps(rows, indent=1))
    ok = all(r.get("out_cos", 1) > 0.9999 and r.get("dq_cos", 1) > 0.999 and r.get("dk_cos", 1) > 0.999
             and r.get("dv_cos", 1) > 0.999 for r in rows)
    print("PASS" if ok else "FAIL", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
