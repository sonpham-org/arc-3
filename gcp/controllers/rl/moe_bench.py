"""MoE expert compute on this GPU: F.grouped_mm (what transformers runs) vs one padded bmm (4-Oct-2026).

On sm_120, torch's grouped_mm showed up as 512 separate mm calls per call (~16k per layer fwd+bwd at 115k tokens).
This times the expert part alone (sorted tokens -> gate_up -> SiLU*up -> down -> weighted sum back), forward and
forward+backward (input gradients only; experts are frozen), for uniform and skewed routing.

  python moe_bench.py [--tokens 32768]
"""
from __future__ import annotations

import argparse
import json
import math
import time

import torch
import torch.nn.functional as F

E, H, I, K = 512, 2560, 640, 10
DEV = torch.device("cuda")


def timed(fn, reps=3):
    best = math.inf
    for _ in range(reps):
        torch.cuda.synchronize()
        t = time.perf_counter()
        fn()
        torch.cuda.synchronize()
        best = min(best, time.perf_counter() - t)
    return round(best, 4)


def route(t: int, skew: float, g) -> tuple[torch.Tensor, torch.Tensor]:
    pop = torch.distributions.Dirichlet(torch.full((E,), skew)).sample().to(DEV) if skew else torch.ones(E, device=DEV)
    logits = torch.log(pop)[None, :] + torch.randn(t, E, device=DEV, generator=g)
    w, idx = logits.topk(K, dim=-1)
    return idx, torch.softmax(w, dim=-1).to(torch.bfloat16)


def grouped(x, idx, w, gu, dn):
    flat = idx.reshape(-1)
    order = torch.argsort(flat)
    xs = x[order // K]
    counts = torch.bincount(flat, minlength=E)
    offs = torch.cumsum(counts, 0).to(torch.int32)
    h = F.grouped_mm(xs, gu.transpose(-2, -1), offs=offs)
    g_, u = h.chunk(2, dim=-1)
    y = F.grouped_mm(F.silu(g_) * u, dn.transpose(-2, -1), offs=offs)
    y = y * w.reshape(-1)[order, None]
    out = torch.zeros_like(x)
    return out.index_add(0, order // K, y)


def padded(x, idx, w, gu, dn):
    flat = idx.reshape(-1)
    order = torch.argsort(flat)
    counts = torch.bincount(flat, minlength=E)
    cap = int(counts.max())
    start = torch.cumsum(counts, 0) - counts
    pos = torch.arange(flat.numel(), device=DEV) - start[flat[order]]          # row inside its expert
    slot = flat[order] * cap + pos
    xs = x.new_zeros(E * cap, H)
    xs = xs.index_copy(0, slot, x[order // K])
    h = torch.bmm(xs.view(E, cap, H), gu.transpose(-2, -1))
    g_, u = h.chunk(2, dim=-1)
    y = torch.bmm(F.silu(g_) * u, dn.transpose(-2, -1)).view(E * cap, H)[slot]
    y = y * w.reshape(-1)[order, None]
    return torch.zeros_like(x).index_add(0, order // K, y)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokens", type=int, default=32768)
    a = ap.parse_args()
    g = torch.Generator(device=DEV).manual_seed(0)
    gu = (torch.randn(E, 2 * I, H, device=DEV) * 0.02).to(torch.bfloat16)
    dn = (torch.randn(E, H, I, device=DEV) * 0.02).to(torch.bfloat16)
    x = torch.randn(a.tokens, H, device=DEV).to(torch.bfloat16)
    gy = torch.randn_like(x)
    for skew in (0, 1.0, 0.3):
        idx, w = route(a.tokens, skew, g)
        counts = torch.bincount(idx.reshape(-1), minlength=E)
        row = {"tokens": a.tokens, "skew": skew, "max_over_mean": round(float(counts.max() / counts.float().mean()), 2)}
        ref = grouped(x, idx, w, gu, dn).float()
        alt = padded(x, idx, w, gu, dn).float()
        row["padded_rel_maxdiff"] = round(float((alt - ref).abs().max() / ref.abs().max()), 5)
        for name, f in (("grouped", grouped), ("padded", padded)):
            row[f"{name}_fwd_s"] = timed(lambda: f(x, idx, w, gu, dn))

            def fb(f=f):
                xx = x.detach().requires_grad_(True)
                f(xx, idx, w, gu, dn).backward(gy)
            row[f"{name}_fwdbwd_s"] = timed(fb)
        from torch.profiler import ProfilerActivity, profile
        with profile(activities=[ProfilerActivity.CUDA, ProfilerActivity.CPU]) as p:
            xx = x.detach().requires_grad_(True)
            grouped(xx, idx, w, gu, dn).backward(gy)
            torch.cuda.synchronize()
        row["grouped_mm_calls"] = int(sum(e.count for e in p.key_averages() if e.key == "aten::mm"))
        print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
