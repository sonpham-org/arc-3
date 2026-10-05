"""kdsamp patch-set check in the PATCHED install (4-Oct-2026, daniel-draft kernels). Pre-server script, free GPU.

spec_utils.sample_draft_proposal (kdsamp: top-k-first draft proposal) vs the rs path (_rs_sample_draft_proposal:
softmax(logits / T) -> flashinfer top-k renorm -> top-p renorm -> Gumbel draw over the whole hot vocab), on synthetic
draft logits shaped like a drafter's (a few strong ids over a 64k heavy-tailed floor), T 0.6 / top-k 20 / top-p 0.95
(the ARC harness) plus greedy, top-k off, small top-p, bf16 logits:
  q        max |q_new - q_rs| over the row, same support, mass of q_rs outside the new support
  draw     X ~ q_new: chi-square over the support from 400k draws (B = 1024 identical rows x 400 calls), and
           topk_p == q_new[X] exactly, X always in the support
  graph    capture on static buffers, replay with fresh logits: q equals eager, draws change between replays
  cands    candidate count per row (cap 512) at each chunk size: overflow rate
  timing   rs path vs kdsamp in a CUDA graph at B = 1 / 10 / 13, V = 65536, chunk 256 / 512 / 1024 / 2048
One JSON line per result; last line {"verdict": ...}.
"""
import json
import math
import time
import traceback

import torch

DEV = torch.device("cuda")
T0 = time.time()
FAIL = []
V = 65536


def emit(**kw):
    kw["t"] = round(time.time() - T0, 1)
    print(json.dumps(kw), flush=True)


def logits_like(B, seed, peaks=(1, 30), spread=6.0):
    """Floor ~ N(0, 2) plus a heavy tail, then 1-30 ids lifted to 8..22: a drafter row's shape."""
    g = torch.Generator(device=DEV).manual_seed(seed)
    x = torch.randn((B, V), generator=g, device=DEV) * 2.0
    x += torch.empty((B, V), device=DEV).exponential_(1.0, generator=g) * 0.8
    for b in range(B):
        n = int(torch.randint(peaks[0], peaks[1] + 1, (1,), generator=g, device=DEV))
        ids = torch.randperm(V, generator=g, device=DEV)[:n]
        x[b, ids] = 8.0 + torch.rand(n, generator=g, device=DEV) * (spread + 8.0)
    return x


def params(B, T=0.6, k=20, p=0.95):
    return (torch.full((B, 1), T, device=DEV), torch.full((B,), k, dtype=torch.int32, device=DEV),
            torch.full((B,), p, dtype=torch.float32, device=DEV))


def compare_q(S, label, logits, T, k, p, expect_same_support=True):
    qa, pa, ia = S._rs_sample_draft_proposal(logits, T, k, p)
    qb, pb, ib = S.sample_draft_proposal(logits, T, k, p)
    torch.cuda.synchronize()
    md = float((qa - qb).abs().max())
    sa, sb = qa > 0, qb > 0
    same = (sa == sb).all(dim=1)
    outside = float((qa * (~sb)).sum(dim=1).max())
    rowsum = float((qb.sum(dim=1) - 1).abs().max())
    xin = bool(sb.gather(1, ib).all())
    pmatch = bool(torch.equal(qb.gather(1, ib), pb))
    ok = xin and pmatch and rowsum < 1e-5   # correctness: X drawn inside q's support, q(X) returned, q sums to 1
    agree = md < 2e-6 and bool(same.all())  # same truncation as the rs path (expected unless top-k > 32 / off)
    emit(kind="q", label=label, rows=logits.shape[0], max_abs_diff=md, same_support_rows=int(same.sum()),
         rs_mass_outside_new_support_max=outside, support_size_new=[int(x) for x in sb.sum(1)[:10]],
         support_size_rs=[int(x) for x in sa.sum(1)[:10]], rowsum_err=rowsum, x_in_support=xin, p_equals_qx=pmatch,
         ok=ok, agree=agree)
    if not ok or (expect_same_support and (outside > 0.02 or md > 1e-3)):
        FAIL.append(("q", label))


def chi_square(S, seed=3, calls=400, B=1024):
    base = logits_like(1, seed, peaks=(12, 12), spread=2.0)
    logits = base.expand(B, V).contiguous()
    T, k, p = params(B, 0.6, 20, 0.95)
    counts = torch.zeros(V, device=DEV)
    q0 = None
    for _ in range(calls):
        q, pq, x = S.sample_draft_proposal(logits, T, k, p)
        if q0 is None:
            q0 = q[0].clone()
        counts += torch.bincount(x.view(-1), minlength=V).float()
        if not bool(torch.equal(q.gather(1, x), pq)):
            FAIL.append(("chi:p!=q[x]",))
    torch.cuda.synchronize()
    n = counts.sum()
    sup = q0 > 0
    outside = float(counts[~sup].sum())
    exp_ = q0[sup] * n
    chi = float(((counts[sup] - exp_) ** 2 / exp_).sum())
    dof = int(sup.sum()) - 1
    z = (chi - dof) / math.sqrt(2 * max(dof, 1))
    ok = outside == 0 and abs(z) < 4.5
    emit(kind="draw_chi_square", draws=int(n), support=int(sup.sum()), chi2=round(chi, 2), dof=dof, z=round(z, 2),
         draws_outside_support=outside, top_q=[round(float(v), 4) for v in q0[sup].sort(descending=True).values[:8]],
         ok=ok)
    if not ok:
        FAIL.append(("chi", z, outside))


def graph_check(S, B=10):
    logits = logits_like(B, 21)
    T, k, p = params(B)
    S.sample_draft_proposal(logits, T, k, p)
    s = torch.cuda.Stream()
    s.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(s):
        S.sample_draft_proposal(logits, T, k, p)
    torch.cuda.current_stream().wait_stream(s)
    torch.cuda.synchronize()
    g = torch.cuda.CUDAGraph()
    with torch.cuda.graph(g):
        q, pq, x = S.sample_draft_proposal(logits, T, k, p)
    oks, draws = [], []
    for seed in (31, 32, 33):
        f = logits_like(B, seed)
        logits.copy_(f)
        g.replay()
        torch.cuda.synchronize()
        qe, _, _ = S.sample_draft_proposal(f, T, k, p)
        torch.cuda.synchronize()
        oks.append(bool(torch.equal(q, qe)) and bool(torch.equal(q.gather(1, x), pq)) and bool((q.gather(1, x) > 0).all()))
    logits.copy_(logits_like(B, 40, peaks=(20, 20), spread=0.5))
    for _ in range(8):
        g.replay()
        torch.cuda.synchronize()
        draws.append(x.view(-1).tolist())
    varied = len({tuple(d) for d in draws}) > 1
    ok = all(oks) and varied
    emit(kind="graph_replay", rows=B, q_equal_eager=oks, draws_vary_between_replays=varied, ok=ok)
    if not ok:
        FAIL.append(("graph", oks, varied))


def cand_stats(S, ch):
    S._KDS_CH = ch
    B = 256
    logits = logits_like(B, 50)
    T, k, p = params(B)
    import triton
    nch = triton.cdiv(V, ch)
    nchp = triton.next_power_of_2(nch)
    cmax = torch.empty((B, nchp), dtype=torch.float32, device=DEV)
    cnt = torch.empty((B,), dtype=torch.int32, device=DEV)
    cand = torch.empty((B, S._KDS_CAP), dtype=torch.int64, device=DEV)
    q = torch.empty((B, V), dtype=torch.float32, device=DEV)
    S._kds_chunk_max_kernel[(B, nch)](logits, logits.stride(0), cmax, cnt, V, NCHP=nchp, CH=ch)
    S._kds_collect_kernel[(B, nch)](logits, logits.stride(0), cmax, cnt, cand, q, V, nch, NCHP=nchp, CH=ch,
                                    KSEL=S._KDS_KSEL, CAP=S._KDS_CAP)
    torch.cuda.synchronize()
    c = cnt.float()
    emit(kind="candidates", chunk=ch, rows=B, mean=round(float(c.mean()), 1), max=int(c.max()),
         p99=float(c.quantile(0.99)), overflow_rows=int((cnt > S._KDS_CAP).sum()))


def graph_time(fn, reps=50, per=8):
    fn()
    s = torch.cuda.Stream()
    s.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(s):
        fn()
    torch.cuda.current_stream().wait_stream(s)
    torch.cuda.synchronize()
    g = torch.cuda.CUDAGraph()
    with torch.cuda.graph(g):
        for _ in range(per):
            fn()
    g.replay()
    torch.cuda.synchronize()
    e0, e1 = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
    e0.record()
    for _ in range(reps):
        g.replay()
    e1.record()
    torch.cuda.synchronize()
    del g
    return round(e0.elapsed_time(e1) * 1e3 / (reps * per), 2)


def timing(S):
    out = {}
    for B in (1, 10, 13):
        logits = logits_like(B, 60)
        T, k, p = params(B)
        r = {"rs": graph_time(lambda: S._rs_sample_draft_proposal(logits, T, k, p))}
        for ch in (256, 512, 1024, 2048):
            S._KDS_CH = ch
            r[f"kds{ch}"] = graph_time(lambda: S.sample_draft_proposal(logits, T, k, p))
        emit(kind="timing_us_per_call", rows=B, V=V, **r)
        out[B] = r
    return out


def main():
    import sglang.srt.speculative.spec_utils as S
    assert hasattr(S, "_kds_sample_draft_proposal"), "kdsamp not installed"
    emit(kind="env", gpu=torch.cuda.get_device_name(), torch=torch.__version__, triton=__import__("triton").__version__,
         on=S._KDS_ON, chunk=S._KDS_CH, cap=S._KDS_CAP, ksel=S._KDS_KSEL)
    ch0 = S._KDS_CH
    B = 64
    cases = [("arc T0.6 k20 p0.95", 0.6, 20, 0.95, True), ("greedy T1 k1", 1.0, 1, 1.0, True),
             ("T1 k5 p0.5", 1.0, 5, 0.5, True), ("T0.7 k32 p1", 0.7, 32, 1.0, True),
             ("T0.6 k-off p0.95 (truncated to 32)", 0.6, 1 << 30, 0.95, False),
             ("T1 k-off p1 (truncated to 32)", 1.0, 1 << 30, 1.0, False)]
    for label, T_, k_, p_, same in cases:
        for ch in (512, 1024):
            S._KDS_CH = ch
            try:
                compare_q(S, f"{label} ch{ch}", logits_like(B, 7), *params(B, T_, k_, p_), expect_same_support=same)
            except Exception:
                FAIL.append(("q-crash", label, ch))
                emit(kind="error", where=label, tb=traceback.format_exc()[-3000:])
    S._KDS_CH = ch0
    mixed_T = torch.tensor([[0.6], [1.0], [0.7], [0.6]] * 4, device=DEV)
    mixed_k = torch.tensor([20, 1, 20, 7] * 4, dtype=torch.int32, device=DEV)
    mixed_p = torch.tensor([0.95, 1.0, 0.8, 0.95] * 4, device=DEV)
    for label, args in (("mixed rows", (logits_like(16, 8), mixed_T, mixed_k, mixed_p)),
                        ("int64 top_k", (logits_like(16, 10), params(16)[0], params(16)[1].long(), params(16)[2]))):
        try:
            compare_q(S, label, *args)
        except Exception:
            FAIL.append(("q-crash", label))
            emit(kind="error", where=label, tb=traceback.format_exc()[-3000:])
    try:  # bf16 logits: the kdsamp path alone (correctness), the rs path may not take bf16 probs
        lg = logits_like(16, 9).to(torch.bfloat16)
        q, pq, x = S.sample_draft_proposal(lg, *params(16))
        ok = bool(torch.equal(q.gather(1, x), pq)) and bool((pq > 0).all()) and float((q.sum(1) - 1).abs().max()) < 1e-5
        emit(kind="q", label="bf16 logits (kdsamp only)", ok=ok, dtype=str(q.dtype))
        if not ok:
            FAIL.append(("q", "bf16"))
    except Exception:
        FAIL.append(("q-crash", "bf16"))
        emit(kind="error", where="bf16", tb=traceback.format_exc()[-3000:])
    for fn in (chi_square, graph_check):
        try:
            fn(S)
        except Exception:
            FAIL.append((fn.__name__ + "-crash",))
            emit(kind="error", where=fn.__name__, tb=traceback.format_exc()[-3000:])
    for ch in (256, 512, 1024, 2048):
        try:
            cand_stats(S, ch)
        except Exception:
            emit(kind="error", where=f"cands {ch}", tb=traceback.format_exc()[-3000:])
    S._KDS_CH = ch0
    try:
        timing(S)
    except Exception:
        emit(kind="error", where="timing", tb=traceback.format_exc()[-3000:])
    S._KDS_CH = ch0
    emit(verdict="PASS" if not FAIL else "FAIL", failures=[str(f) for f in FAIL][:20])


if __name__ == "__main__":
    try:
        main()
    except Exception:
        emit(verdict="FAIL", error=traceback.format_exc()[-4000:])
