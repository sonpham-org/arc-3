"""QSA sparse decode micro-benchmark + closeness check (3-Oct-2026, daniel-draft kfuse). Pre-server script, free GPU,
patched install with qsakv4 (--kv4).

Reference = what qwen_sparse_attn_backend._forward_trtllm_sparse runs today on nvfp4_qsa KV: valid counts, the
NVFP4 -> FP8 gather into a page-aligned scratch (_compact_kv_nvfp4), FlashInfer trtllm_batch_decode_with_kv_cache
(XQA kernel_mha on sm120). Candidate = qsa_fused.qsa_nvfp4_fused_decode (same unpack arithmetic, no scratch).
Data: 12 layers x 852k-slot NVFP4 pools (5.9 GB, cold), 13 requests with 40-65k context on random 64-token pages,
per verify row 128 selected 16-token blocks (rows of one request share ~80% of them) + own tail, topk 2052.
Checks: fused vs reference max/mean abs diff, both vs an fp32 torch reference on the same FP8-rounded K/V,
determinism, CUDA-graph replay. Timing: CUDA graph over 12 layers at 52 rows (13-lane verify) and 13 rows (draft).
"""
import json
import math
import os
import sys
import time
import traceback

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qsa_fused import qsa_nvfp4_fused_decode  # noqa: E402
try:
    from qsa_union import qsa_nvfp4_union_decode  # noqa: E402
except Exception:
    qsa_nvfp4_union_decode = None
MODE = os.environ.get('KF_QSA_MODE', 'perrow')

DEV = torch.device("cuda")
T0 = time.time()
L, NREQ, HQ, HKV, D = 12, 13, 24, 2, 256
HALF = D // 2
PAGE = 64
CTX_MAX = 65536
NS = NREQ * CTX_MAX + PAGE
TOPK = 2052
SCALE = D ** -0.5


def emit(**kw):
    kw["t"] = round(time.time() - T0, 1)
    print(json.dumps(kw), flush=True)


def graph_time(fn, reps=10):
    s = torch.cuda.Stream()
    s.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(s):
        fn()
    torch.cuda.current_stream().wait_stream(s)
    torch.cuda.synchronize()
    g = torch.cuda.CUDAGraph()
    with torch.cuda.graph(g):
        fn()
    g.replay(); g.replay()
    torch.cuda.synchronize()
    e0, e1 = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
    e0.record()
    for _ in range(reps):
        g.replay()
    e1.record()
    torch.cuda.synchronize()
    del g
    return e0.elapsed_time(e1) * 1e3 / reps


def make_case(gen, rows_per_req):
    ctx = torch.randint(40000, CTX_MAX - 64, (NREQ,), generator=torch.Generator().manual_seed(1)).tolist()
    rows = NREQ * rows_per_req
    row_req = torch.arange(NREQ, dtype=torch.int64).repeat_interleave(rows_per_req)
    seq = torch.tensor([ctx[r] + j + 1 for r in range(NREQ) for j in range(rows_per_req)], dtype=torch.int32)
    idx = torch.full((rows, TOPK), -1, dtype=torch.int32)
    cg = torch.Generator().manual_seed(2)
    for r in range(NREQ):
        nblk = ctx[r] // 16
        base = torch.randperm(nblk - 1, generator=cg)[:128]
        for j in range(rows_per_req):
            blks = base.clone()
            swap = torch.rand(128, generator=cg) < 0.2
            blks[swap] = torch.randint(0, nblk - 1, (int(swap.sum()),), generator=cg)
            pos = (blks.sort().values[:, None] * 16 + torch.arange(16)[None, :]).flatten()
            pos = torch.unique(pos)
            tail = torch.arange(ctx[r], ctx[r] + j + 1)
            pos = torch.cat([pos[~torch.isin(pos, tail)], tail])[:TOPK]
            idx[r * rows_per_req + j, :pos.numel()] = pos.to(torch.int32)
    return row_req.to(DEV), seq.to(DEV), idx.to(DEV)


def main():
    from flashinfer.decode import trtllm_batch_decode_with_kv_cache
    from sglang.srt.layers.attention.qsa.sparse_attn import (
        qwen_sparse_kv_extraction_compact_nvfp4_triton, qwen_sparse_valid_counts_triton)
    gen = torch.Generator(device=DEV).manual_seed(0)
    layers = []
    for _ in range(L):
        kp = torch.randint(0, 256, (NS, HKV, HALF), dtype=torch.uint8, device=DEV, generator=gen)
        vp = torch.randint(0, 256, (NS, HKV, HALF), dtype=torch.uint8, device=DEV, generator=gen)
        ks = (torch.rand(NS, HKV, HALF // 8, device=DEV, generator=gen) * 0.5 + 0.05).to(torch.float8_e4m3fn)
        vs = (torch.rand(NS, HKV, HALF // 8, device=DEV, generator=gen) * 0.5 + 0.05).to(torch.float8_e4m3fn)
        kg = torch.full((1,), 0.75, dtype=torch.float32, device=DEV)
        vg = torch.full((1,), 1.25, dtype=torch.float32, device=DEV)
        layers.append((kp, vp, ks, vs, kg, vg))
    npages = NS // PAGE
    r2t = torch.zeros((NREQ + 1, 131072), dtype=torch.int32)
    perm = torch.randperm(npages - 1, generator=torch.Generator().manual_seed(3)) + 1
    for r in range(NREQ):
        pages = perm[r * (CTX_MAX // PAGE):(r + 1) * (CTX_MAX // PAGE)]
        r2t[r, :CTX_MAX] = (pages[:, None] * PAGE + torch.arange(PAGE)[None, :]).flatten().to(torch.int32)
    r2t = r2t.to(DEV)
    emit(kind="setup", pool_GB=round(L * sum(t.numel() * t.element_size() for t in layers[0]) / 1e9, 2))
    ws = torch.zeros(128 * 1024 * 1024, dtype=torch.uint8, device=DEV)
    fails = []
    summary = {}
    for rows_per_req in ((4, 6) if MODE == 'union' else (4, 1)):
        row_req, seq, idx = make_case(gen, rows_per_req)
        rows = row_req.numel()
        qs = [torch.randn(rows, HQ, D, device=DEV, generator=gen).bfloat16() for _ in range(L)]
        vcnt = torch.empty(rows, dtype=torch.int32, device=DEV)
        ppr = math.ceil(TOPK / PAGE)
        stride = ppr * PAGE
        cu = torch.arange(rows + 1, dtype=torch.int32, device=DEV) * stride
        bt = (torch.arange(rows, dtype=torch.int32, device=DEV)[:, None] * ppr
              + torch.arange(ppr, dtype=torch.int32, device=DEV)[None, :]).contiguous()
        sk = torch.empty(rows * stride, HKV, D, dtype=torch.float8_e4m3fn, device=DEV)
        sv = torch.empty_like(sk)
        outs_ref = [torch.empty(rows, HQ, D, dtype=torch.bfloat16, device=DEV) for _ in range(L)]

        def ref(l):
            qwen_sparse_valid_counts_triton(seq, idx, vcnt, rows, TOPK)
            kp, vp, ks, vs_, kg, vg = layers[l]
            qwen_sparse_kv_extraction_compact_nvfp4_triton(kp, vp, ks, vs_, kg, vg, r2t, row_req, idx, seq, cu,
                                                            sk, sv, rows, TOPK)
            kc = sk.view(-1, PAGE, HKV, D).permute(0, 2, 1, 3)
            vc = sv.view(-1, PAGE, HKV, D).permute(0, 2, 1, 3)
            o = trtllm_batch_decode_with_kv_cache(query=qs[l].contiguous(), kv_cache=(kc, vc), workspace_buffer=ws,
                                                  block_tables=bt, seq_lens=vcnt, max_seq_len=stride,
                                                  bmm1_scale=SCALE, bmm2_scale=1.0)
            outs_ref[l].copy_(o.view(rows, HQ, D))

        def fused(l, **kw):
            qwen_sparse_valid_counts_triton(seq, idx, vcnt, rows, TOPK)
            if MODE == 'union':
                kw.pop('v2', None)
                return qsa_nvfp4_union_decode(qs[l], layers[l], r2t, row_req, idx, seq, vcnt, SCALE, rows_per_req,
                                              131072, **kw)
            return qsa_nvfp4_fused_decode(qs[l], layers[l], r2t, row_req, idx, seq, vcnt, SCALE, **kw)

        for l in range(L):
            ref(l)
        torch.cuda.synchronize()
        # fp32 torch reference for 3 rows of layer 0 (same FP8-rounded K/V as the scratch)
        kp, vp, ks, vs_, kg, vg = layers[0]
        exact = {}
        for rr in (0, rows // 2, rows - 1):
            n = int(vcnt[rr].item())
            pos = idx[rr, :n].long()
            slots = r2t[row_req[rr], pos].long()

            def deq(p, s, gsc):
                raw = p[slots].to(torch.int32)  # [n, HKV, HALF]
                sc = s[slots].to(torch.float32).repeat_interleave(8, dim=-1) * gsc
                def e2m1(x):
                    mag = x & 7
                    e = (mag >> 1).float(); m = (mag & 1).float()
                    val = torch.where(mag < 2, 0.5 * m, torch.exp2(e - 1) * (1 + 0.5 * m))
                    return torch.where((x & 8) != 0, -val, val)
                lo = (e2m1(raw & 15) * sc).clamp(-448, 448).to(torch.float8_e4m3fn).float()
                hi = (e2m1(raw >> 4) * sc).clamp(-448, 448).to(torch.float8_e4m3fn).float()
                return torch.stack([lo, hi], -1).flatten(-2)  # [n, HKV, D]
            K = deq(kp, ks, kg); V = deq(vp, vs_, vg)
            q = qs[0][rr].float().view(HKV, HQ // HKV, D)
            sc = torch.einsum("hgd,nhd->hgn", q, K) * SCALE
            p = torch.softmax(sc, -1)
            o = torch.einsum("hgn,nhd->hgd", p, V).reshape(HQ, D)
            exact[rr] = o
        base = [(8, 32, 4, 2, False)]
        v2s = [(8, 32, 4, 2), (8, 16, 4, 2), (16, 32, 4, 2), (8, 32, 8, 2), (8, 64, 8, 2), (4, 32, 4, 2),
               (16, 16, 4, 2), (8, 32, 4, 1), (8, 32, 4, 3), (16, 64, 8, 2), (32, 32, 4, 2)]
        if MODE == 'union':
            base = []
            v2s = [(8, 32, 8, 2), (8, 16, 8, 2), (4, 32, 8, 2), (16, 32, 8, 2), (8, 32, 4, 2), (8, 64, 8, 2),
                   (8, 32, 8, 3)]
        configs = [dict(splits=s_, block_n=b_, warps=w_, stages=st_, v2=v_) for s_, b_, w_, st_, v_ in base] +                   [dict(splits=s_, block_n=b_, warps=w_, stages=st_, v2=True) for s_, b_, w_, st_ in v2s]
        t_ref = graph_time(lambda: [ref(l) for l in range(L)]) / L
        best = None
        for cfg in configs:
            try:
                o1 = [fused(l, **cfg).clone() for l in range(L)]
                o2 = fused(0, **cfg).clone()
                torch.cuda.synchronize()
                diff = max((a.float() - b.float()).abs().max().item() for a, b in zip(o1, outs_ref))
                mdiff = sum((a.float() - b.float()).abs().mean().item() for a, b in zip(o1, outs_ref)) / L
                refmax = max(b.float().abs().max().item() for b in outs_ref)
                bit = sum((a == b).float().mean().item() for a, b in zip(o1, outs_ref)) / L
                ex_f = max((o1[0][rr].float() - exact[rr]).abs().max().item() for rr in exact)
                ex_r = max((outs_ref[0][rr].float() - exact[rr]).abs().max().item() for rr in exact)
                det = bool(torch.equal(o1[0], o2))
                t_f = graph_time(lambda: [fused(l, **cfg) for l in range(L)]) / L
                # graph replay correctness: captured fused layer 0 vs eager
                g = torch.cuda.CUDAGraph()
                with torch.cuda.graph(g):
                    og = fused(0, **cfg)
                g.replay(); g.replay(); torch.cuda.synchronize()
                gok = bool(torch.equal(og, o1[0]))
                del g
                row = dict(kind="qsa", rows=rows, cfg=cfg, ref_us=round(t_ref, 1), fused_us=round(t_f, 1),
                           max_abs_diff_vs_ref=round(diff, 5), mean_abs_diff_vs_ref=round(mdiff, 6),
                           ref_absmax=round(refmax, 3), bitwise_equal_share=round(bit, 4),
                           fused_vs_fp32=round(ex_f, 5), ref_vs_fp32=round(ex_r, 5), deterministic=det,
                           graph_replay_ok=gok)
                emit(**row)
                if not det or not gok or ex_f > 2 * ex_r + 0.02:
                    fails.append((rows, cfg))
                if best is None or t_f < best[0]:
                    best = (t_f, cfg)
            except Exception:
                emit(kind="error", rows=rows, cfg=cfg, tb=traceback.format_exc()[-2500:])
        summary[rows] = dict(ref_us=round(t_ref, 1), best_fused_us=round(best[0], 1) if best else None,
                             best_cfg=best[1] if best else None)
        emit(kind="qsa_best", rows=rows, **summary[rows])
    emit(verdict="PASS" if not fails else "FAIL", fails=fails, summary=summary)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        emit(kind="fatal", tb=traceback.format_exc()[-4000:])
