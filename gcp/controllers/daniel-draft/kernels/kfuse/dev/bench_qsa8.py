"""FP8-KV QSA sparse decode micro-benchmark + closeness check (4-Oct-2026, daniel-draft kfuse8). Pre-server script,
his ORIGINAL QSA files (no qsakv4/qsaring).

Reference = his _forward_trtllm_sparse on an fp8_e4m3 pool: valid counts, _compact_kv into a page-aligned FP8 scratch,
FlashInfer trtllm_batch_decode_with_kv_cache (XQA kernel_mha on sm120). Candidates (qsa_fp8.py): per-row fused
kernel; gather-once union kernel (verify rows in request-major groups of W).
Data: 12 layers x fp8 pools (10 requests x 64k slots), 10 requests with 40-65k context on random 64-token pages; per
verify row 512 selected 4-token blocks (rows of one request share ~80% of them) + own tail, topk 2051 (his layout).
Rows: W = 1 (draft), 4, 6, 8 per request. Checks vs reference and vs an fp32 torch reference; determinism; graph replay.
"""
import json
import math
import os
import sys
import time
import traceback

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qsa_fp8 import qsa_fp8_fused_decode, qsa_fp8_union_decode  # noqa: E402

DEV = torch.device("cuda")
T0 = time.time()
L, NREQ, HQ, HKV, D = 12, 10, 24, 2, 256
PAGE, CTX_MAX = 64, 65536
NS = NREQ * CTX_MAX + PAGE
TOPK = 2051
SCALE = D ** -0.5
MAXPOS = 131072


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


def make_case(W):
    ctx = torch.randint(40000, CTX_MAX - 64, (NREQ,), generator=torch.Generator().manual_seed(1)).tolist()
    rows = NREQ * W
    row_req = torch.arange(NREQ, dtype=torch.int64).repeat_interleave(W)
    seq = torch.tensor([ctx[r] + j + 1 for r in range(NREQ) for j in range(W)], dtype=torch.int32)
    idx = torch.full((rows, TOPK), -1, dtype=torch.int32)
    cg = torch.Generator().manual_seed(2 + W)
    for r in range(NREQ):
        nblk = ctx[r] // 4
        base = torch.randperm(nblk - 1, generator=cg)[:512]
        for j in range(W):
            vis = ctx[r] + j + 1
            blks = base.clone()
            swap = torch.rand(512, generator=cg) < 0.2
            blks[swap] = torch.randint(0, nblk - 1, (int(swap.sum()),), generator=cg)
            blks = torch.unique(blks)[:512]
            pos = (blks[:, None] * 4 + torch.arange(4)[None, :]).flatten()
            tail_start = (vis // 4) * 4
            tail = torch.arange(tail_start, vis)
            pos = torch.cat([pos[pos < tail_start], tail])[:TOPK]
            idx[r * W + j, :pos.numel()] = pos.to(torch.int32)
    return row_req.to(DEV), seq.to(DEV), idx.to(DEV)


def main():
    from flashinfer.decode import trtllm_batch_decode_with_kv_cache
    from sglang.srt.layers.attention.qsa.sparse_attn import (
        qwen_sparse_kv_extraction_compact_triton, qwen_sparse_valid_counts_triton)
    gen = torch.Generator(device=DEV).manual_seed(0)
    layers = []
    for _ in range(L):
        k = (torch.randn(NS, HKV, D, device=DEV, generator=gen) * 2).to(torch.float8_e4m3fn)
        v = (torch.randn(NS, HKV, D, device=DEV, generator=gen) * 2).to(torch.float8_e4m3fn)
        layers.append((k, v))
    npages = NS // PAGE
    r2t = torch.zeros((NREQ + 1, MAXPOS), dtype=torch.int32)
    perm = torch.randperm(npages - 1, generator=torch.Generator().manual_seed(3)) + 1
    for r in range(NREQ):
        pages = perm[r * (CTX_MAX // PAGE):(r + 1) * (CTX_MAX // PAGE)]
        r2t[r, :CTX_MAX] = (pages[:, None] * PAGE + torch.arange(PAGE)[None, :]).flatten().to(torch.int32)
    r2t = r2t.to(DEV)
    emit(kind="setup", pool_GB=round(L * 2 * NS * HKV * D / 1e9, 2))
    ws = torch.zeros(128 * 1024 * 1024, dtype=torch.uint8, device=DEV)
    fails, summary = [], {}
    for W in (4, 1, 6, 8):
        row_req, seq, idx = make_case(W)
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
            kb, vb = layers[l]
            qwen_sparse_kv_extraction_compact_triton(kb, vb, r2t, row_req, idx, seq, cu, sk, sv, rows, TOPK)
            kc = sk.view(-1, PAGE, HKV, D).permute(0, 2, 1, 3)
            vc = sv.view(-1, PAGE, HKV, D).permute(0, 2, 1, 3)
            o = trtllm_batch_decode_with_kv_cache(query=qs[l].contiguous(), kv_cache=(kc, vc), workspace_buffer=ws,
                                                  block_tables=bt, seq_lens=vcnt, max_seq_len=stride,
                                                  bmm1_scale=SCALE, bmm2_scale=1.0)
            outs_ref[l].copy_(o.view(rows, HQ, D))

        for l in range(L):
            ref(l)
        torch.cuda.synchronize()
        exact = {}
        kb, vb = layers[0]
        for rr in (0, rows // 2, rows - 1):
            n = int(vcnt[rr].item())
            slots = r2t[row_req[rr], idx[rr, :n].long()].long()
            K = kb[slots].float(); V = vb[slots].float()
            qv = qs[0][rr].float().view(HKV, HQ // HKV, D)
            p = torch.softmax(torch.einsum("hgd,nhd->hgn", qv, K) * SCALE, -1)
            exact[rr] = torch.einsum("hgn,nhd->hgd", p, V).reshape(HQ, D)
        t_ref = graph_time(lambda: [ref(l) for l in range(L)]) / L
        cands = [("row", dict(splits=s, block_n=b, warps=w, stages=st))
                 for s, b, w, st in ((8, 32, 4, 2), (8, 64, 8, 2), (16, 32, 4, 2), (4, 32, 4, 2), (8, 32, 4, 3))]
        if W > 1 and qsa_fp8_union_decode is not None:
            cands += [("union", dict(splits=s, block_n=b, warps=w, stages=st, dsplit=ds))
                      for s, b, w, st, ds in ((8, 32, 8, 2, 2), (8, 32, 8, 2, 4), (4, 32, 8, 2, 2), (16, 32, 8, 2, 2),
                                              (8, 64, 8, 2, 2), (8, 32, 4, 2, 4))]
        best = {}
        for kind, cfg in cands:
            def fused(l, kind=kind, cfg=cfg):
                qwen_sparse_valid_counts_triton(seq, idx, vcnt, rows, TOPK)
                kb_, vb_ = layers[l]
                if kind == "row":
                    return qsa_fp8_fused_decode(qs[l], kb_, vb_, r2t, row_req, idx, seq, vcnt, SCALE, **cfg)
                return qsa_fp8_union_decode(qs[l], kb_, vb_, r2t, row_req, idx, seq, vcnt, SCALE, W, MAXPOS, **cfg)
            try:
                o1 = [fused(l).clone() for l in range(L)]
                o2 = fused(0).clone()
                torch.cuda.synchronize()
                diff = max((a.float() - b.float()).abs().max().item() for a, b in zip(o1, outs_ref))
                refmax = max(b.float().abs().max().item() for b in outs_ref)
                ex_f = max((o1[0][rr].float() - exact[rr]).abs().max().item() for rr in exact)
                ex_r = max((outs_ref[0][rr].float() - exact[rr]).abs().max().item() for rr in exact)
                det = bool(torch.equal(o1[0], o2))
                t_f = graph_time(lambda: [fused(l) for l in range(L)]) / L
                g = torch.cuda.CUDAGraph()
                with torch.cuda.graph(g):
                    og = fused(0)
                g.replay(); g.replay(); torch.cuda.synchronize()
                gok = bool(torch.equal(og, o1[0]))
                del g
                emit(kind="qsa8", W=W, rows=rows, impl=kind, cfg=cfg, ref_us=round(t_ref, 1), fused_us=round(t_f, 1),
                     max_abs_diff_vs_ref=round(diff, 5), ref_absmax=round(refmax, 3), fused_vs_fp32=round(ex_f, 5),
                     ref_vs_fp32=round(ex_r, 5), deterministic=det, graph_replay_ok=gok)
                if not det or not gok or ex_f > 2 * ex_r + 0.02:
                    fails.append((W, kind, cfg))
                if kind not in best or t_f < best[kind][0]:
                    best[kind] = (round(t_f, 1), cfg)
            except Exception:
                emit(kind="error", W=W, impl=kind, cfg=cfg, tb=traceback.format_exc()[-2000:])
        summary[W] = dict(ref_us=round(t_ref, 1), **{k: v for k, v in best.items()})
        emit(kind="qsa8_best", W=W, rows=rows, **summary[W])
    emit(verdict="PASS" if not fails else "FAIL", fails=fails, summary=summary)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        emit(kind="fatal", tb=traceback.format_exc()[-4000:])
