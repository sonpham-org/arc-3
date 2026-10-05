"""kidx patch-set check in the PATCHED install (4-Oct-2026, Kernel optimizations thread). Pre-server script, free GPU.

kidx scores target-verify rows per request (qsa/mqa.py grouped tilelang kernel) instead of per row. Checks:
1. bitwise: grouped (rows_per_req = 4, 6, 8) vs his per-row kernel on synthetic verify batches: 10 requests,
   compressed lengths 25-33k (100-131k tokens), random page tables, ascending row lengths inside a request, page
   tables of the earlier rows TRUNCATED to their own length (the kernel must take pages from the last row), and
   padding requests (all rows length 1);
2. CUDA-graph replay with fresh inputs;
3. timing, COLD (distinct key pools > 3x L2 per graph walk): per-row vs grouped at 4 / 6 / 8 rows per request.
One JSON line per result; last line {"verdict": ...}.
"""
import json
import math
import time

import torch

DEV = torch.device("cuda")
T0 = time.time()
FAIL = []
HEADS, HD, PAGE = 8, 128, 16   # 4 real indexer heads padded to 8 (the fused prep writes the padding), head_dim 128


def emit(**kw):
    kw["t"] = round(time.time() - T0, 1)
    print(json.dumps(kw), flush=True)


def graph_time(fns, reps=10):
    s = torch.cuda.Stream()
    s.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(s):
        for f in fns[:2]:
            f()
    torch.cuda.current_stream().wait_stream(s)
    torch.cuda.synchronize()
    g = torch.cuda.CUDAGraph()
    with torch.cuda.graph(g):
        for f in fns:
            f()
    g.replay()
    g.replay()
    torch.cuda.synchronize()
    e0, e1 = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
    e0.record()
    for _ in range(reps):
        g.replay()
    e1.record()
    torch.cuda.synchronize()
    del g
    return e0.elapsed_time(e1) * 1e3 / (reps * len(fns))


def make_batch(reqs, rpr, gen, pad_reqs=0, min_len=25000, max_len=33000):
    """Verify-shaped batch: reqs x rpr rows, page tables per row (earlier rows truncated), lengths ascending."""
    base = torch.randint(min_len, max_len, (reqs,), generator=gen).tolist()
    max_pages = math.ceil((max_len + rpr) / PAGE) + 1
    total_pages = sum(math.ceil((b + rpr) / PAGE) for b in base) + 8
    k_cache = (torch.randn(total_pages, PAGE, 1, HD, generator=gen) * 0.5).to(torch.bfloat16).to(DEV)
    perm = torch.randperm(total_pages, generator=gen)
    rows = (reqs + pad_reqs) * rpr
    q = torch.zeros(rows, HEADS, HD, dtype=torch.bfloat16)
    q[:, :4] = (torch.randn(rows, 4, HD, generator=gen)).to(torch.bfloat16)
    pt = torch.full((rows, max_pages), -1, dtype=torch.int32)
    lens = torch.ones(rows, dtype=torch.int32)
    used = 0
    for r, b in enumerate(base):
        need = math.ceil((b + rpr) / PAGE)
        pages = perm[used:used + need].to(torch.int32)
        used += need
        for t in range(rpr):
            row = r * rpr + t
            ln = b + t + 1 if t % 2 else b + t   # ascending, sometimes equal steps
            lens[row] = ln
            own = math.ceil(ln / PAGE)
            pt[row, :own] = pages[:own]        # earlier rows: table truncated to their own length
    for row in range(reqs * rpr, rows):        # padding requests: length 1, request 0's first page
        lens[row] = 1
        pt[row, 0] = pt[0, 0]
    max_model_len = max_pages * PAGE
    return q.to(DEV), k_cache, pt.to(DEV), lens.to(DEV), max_model_len


def check_bitwise(M):
    gen = torch.Generator().manual_seed(3)
    for rpr in (4, 6, 8):
        for pad in (0, 1):
            q, kc, pt, lens, mml = make_batch(10, rpr, gen, pad_reqs=pad)
            a = M.tilelang_qsa_mqa_decode(q, kc, pt, lens, mml, None, 1)
            b = M.tilelang_qsa_mqa_decode(q, kc, pt, lens, mml, None, rpr)
            torch.cuda.synchronize()
            eq = bool(torch.equal(a, b))
            ninf_a, ninf_b = int(torch.isinf(a).sum()), int(torch.isinf(b).sum())
            ref = M.torch_qsa_mqa_decode(q, kc, pt.clamp_min(0), lens, mml)
            fin = torch.isfinite(ref)
            err = ((b[fin] - ref[fin]).abs().max() / ref[fin].abs().max()).item()
            emit(kind="bitwise", rows_per_req=rpr, pad_reqs=pad, rows=int(q.shape[0]), bitwise_equal=eq,
                 inf_counts=[ninf_a, ninf_b], err_vs_torch_ref=round(err, 6))
            if not eq:
                FAIL.append(("bitwise", rpr, pad))


def check_graph(M):
    gen = torch.Generator().manual_seed(5)
    q, kc, pt, lens, mml = make_batch(10, 4, gen)
    out = {}
    s = torch.cuda.Stream()
    s.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(s):
        M.tilelang_qsa_mqa_decode(q, kc, pt, lens, mml, None, 4)
    torch.cuda.current_stream().wait_stream(s)
    torch.cuda.synchronize()
    g = torch.cuda.CUDAGraph()
    with torch.cuda.graph(g):
        out["y"] = M.tilelang_qsa_mqa_decode(q, kc, pt, lens, mml, None, 4)
    ok = True
    for _ in range(3):
        q.copy_(torch.randn_like(q.float()).to(torch.bfloat16))
        kc.copy_((torch.randn_like(kc.float()) * 0.5).to(torch.bfloat16))
        g.replay()
        torch.cuda.synchronize()
        ok &= bool(torch.equal(out["y"], M.tilelang_qsa_mqa_decode(q, kc, pt, lens, mml, None, 1)))
    emit(kind="graph_replay", ok=ok)
    if not ok:
        FAIL.append(("graph",))


def check_timing(M):
    gen = torch.Generator().manual_seed(9)
    for rpr in (4, 6, 8):
        q, kc, pt, lens, mml = make_batch(10, rpr, gen)
        pool_bytes = kc.numel() * 2
        R = max(4, int(3 * 128e6 / pool_bytes) + 1)
        pools = [kc] + [kc.clone() for _ in range(R - 1)]
        t1 = graph_time([lambda i=i: M.tilelang_qsa_mqa_decode(q, pools[i], pt, lens, mml, None, 1)
                         for i in range(R)])
        tg = graph_time([lambda i=i: M.tilelang_qsa_mqa_decode(q, pools[i], pt, lens, mml, None, rpr)
                         for i in range(R)])
        key_mb = sum(math.ceil(int(lens[r * rpr + rpr - 1]) / PAGE) for r in range(10)) * PAGE * HD * 2 / 1e6
        emit(kind="timing_cold", rows_per_req=rpr, rows=int(q.shape[0]), R=R, per_row_us=round(t1, 2),
             grouped_us=round(tg, 2), saving_us=round(t1 - tg, 2), key_MB_once=round(key_mb, 1),
             grouped_key_GBps=round(key_mb / tg * 1e3 / 1e3, 0))
        del pools
        torch.cuda.empty_cache()


def main():
    try:
        import sglang.srt.layers.attention.qsa.mqa as M
        assert hasattr(M, "_tilelang_qsa_mqa_decode_grouped_kernel"), "patched mqa.py not installed"
        emit(kind="env", kidx_enabled=M._KIDX_ENABLED, tilelang=M.HAS_TILELANG)
        for f in (check_bitwise, check_graph, check_timing):
            try:
                f(M)
            except Exception as e:
                import traceback
                emit(kind="error", where=f.__name__, err=repr(e)[:400], tb=traceback.format_exc()[-1800:])
                FAIL.append((f.__name__, "exception"))
    except Exception as e:
        import traceback
        emit(kind="error", where="import", err=repr(e)[:400], tb=traceback.format_exc()[-1800:])
        FAIL.append(("import",))
    emit(verdict="PASS" if not FAIL else "FAIL", fails=FAIL[:20])


if __name__ == "__main__":
    main()
