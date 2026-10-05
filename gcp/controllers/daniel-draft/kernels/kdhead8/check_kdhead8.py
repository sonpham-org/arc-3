"""kdhead8 patch-set check in the PATCHED install (4-Oct-2026, daniel-draft kernels). Pre-server script, free GPU.

The drafter's hot-vocab head = the target lm_head's rows at the ARC hot ids (65536 x 2560 bf16), loaded from the
model's safetensors and /kaggle/working/arc-hot-64k.pt. Stored as int8 rows (scale absmax/127) and as e4m3 rows
(his quantize_rowwise_fp8), then:
  kernel   kdh8 kernel vs fp32 math on the same 8-bit weights (the kernel adds no error beyond the stored weights)
  quality  draft logits vs the bf16 head on hidden states shaped like confident / unsure draft steps: logit error,
           top-1 agreement, and the draft q at T 0.6 / top-k 20 / top-p 0.95: total-variation distance and
           1 - sum(min(q_bf16, q_8bit)) (the acceptance a perfect draft would lose per token)
  timing   cuBLAS bf16 (served today) vs his rowwise-fp8 GEMV (<= 32 rows) vs kdh8 per config, at 10 / 13 / 40 /
           80 / 120 / 160 rows, cold weights (two copies alternate), in CUDA graphs
One JSON line per result; last line {"verdict": ...}.
"""
import json
import os
import time
import traceback
from pathlib import Path

import torch

DEV = torch.device("cuda")
T0 = time.time()
FAIL = []
MODEL_DIR = "/kaggle/input/models/dfranzen/intel-qwen3.8-flash-next-w4a16-autoround/transformers/default/1"
HOT = "/kaggle/working/arc-hot-64k.pt"


def emit(**kw):
    kw["t"] = round(time.time() - T0, 1)
    print(json.dumps(kw), flush=True)


def load_head():
    from safetensors import safe_open
    d = Path(MODEL_DIR)
    idx = json.loads((d / "model.safetensors.index.json").read_text())["weight_map"]
    keys = [k for k in idx if k.endswith("lm_head.weight")] or [k for k in idx if k.endswith("embed_tokens.weight")]
    key = keys[0]
    with safe_open(str(d / idx[key]), framework="pt", device="cuda") as f:
        w = f.get_tensor(key)
    ids = torch.tensor(torch.load(HOT), dtype=torch.long, device=DEV)
    emit(kind="head", key=key, full_shape=list(w.shape), dtype=str(w.dtype), hot=int(ids.numel()))
    return w.to(torch.bfloat16)[ids].contiguous()


def hidden_like(head, B, seed, conf):
    """h pointing at 1-4 ids' rows (plus noise), scaled so the top logit sits ~conf above the bulk."""
    g = torch.Generator(device=DEV).manual_seed(seed)
    V, K = head.shape
    h = torch.randn((B, K), generator=g, device=DEV) * 0.3
    for b in range(B):
        ids = torch.randint(0, V, (4,), generator=g, device=DEV)
        wts = torch.tensor([1.0, 0.6, 0.35, 0.2], device=DEV)
        h[b] += (wts[:, None] * head[ids].float() / head[ids].float().norm(dim=1, keepdim=True)).sum(0) * 3.0
    lg = h @ head.float().T
    gap = lg.max(1).values - lg.median(1).values
    h *= (conf / gap)[:, None]
    return h.to(torch.bfloat16)


def q_of(logits, T=0.6, k=20, p=0.95):
    x = logits.float() / T
    v, i = x.topk(k, dim=1)
    pr = torch.softmax(v, dim=1)
    cum = pr.cumsum(1)
    keep = (cum - pr) < p
    pr = pr * keep
    pr = pr / pr.sum(1, keepdim=True)
    q = torch.zeros_like(x)
    q.scatter_(1, i, pr)
    return q


def quality(M, head, mode):
    w8 = M.kdh8_quantize_head(head, mode)
    sc = M.rowwise_scale_of(w8)
    for conf in (8.0, 14.0, 22.0):
        h = hidden_like(head, 256, 5, conf)
        ref = (h.float() @ head.float().T)
        out = torch.empty((h.shape[0], head.shape[0]), dtype=torch.bfloat16, device=DEV)
        # kernel exactness: same 8-bit weights in fp32 math
        deq = w8.float() * sc[:, None]
        mine = M.kdh8_logits(h[:13], w8, sc, out[:13]).float()
        kref = (h[:13].float() @ deq.T)
        kerr = float(((mine - kref).abs() / kref.abs().clamp_min(1.0)).max())
        lg8 = M.kdh8_logits(h, w8, sc, out).float()
        lgb = (h @ head.T).float()   # the served bf16 product
        err = (lg8 - ref).abs()
        errb = (lgb - ref).abs()
        q8, qb = q_of(lg8), q_of(lgb)
        tv = 0.5 * (q8 - qb).abs().sum(1)
        loss = 1 - torch.minimum(q8, qb).sum(1)
        top1 = float((lg8.argmax(1) == lgb.argmax(1)).float().mean())
        top1p = float(qb.max(1).values.mean())
        emit(kind="quality", mode=mode, conf=conf, kernel_rel_err_vs_fp32_same_weights=kerr,
             logit_abs_err_rms=float(err.pow(2).mean().sqrt()), logit_abs_err_max=float(err.max()),
             bf16_logit_abs_err_rms=float(errb.pow(2).mean().sqrt()), top1_agree=top1, mean_top_q=top1p,
             tv_mean=float(tv.mean()), tv_p99=float(tv.quantile(0.99)), accept_loss_mean=float(loss.mean()),
             accept_loss_p99=float(loss.quantile(0.99)))
        if kerr > 2e-2:
            FAIL.append(("kernel", mode, conf, kerr))
    return w8


def graph_time(fns, reps=30):
    for f in fns[:2]:
        f()
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
    torch.cuda.synchronize()
    e0, e1 = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
    e0.record()
    for _ in range(reps):
        g.replay()
    e1.record()
    torch.cuda.synchronize()
    del g
    return round(e0.elapsed_time(e1) * 1e3 / (reps * len(fns)), 1)


def timing(M, head, w8i, w8f):
    heads = [head, head.clone()]                 # two copies: each call reads cold-ish weights (335 MB > L2)
    i8 = [w8i, M.kdh8_quantize_head(head, "int8")]
    f8 = [w8f, M.kdh8_quantize_head(head, "fp8")]
    best = {}
    for rows in (10, 13, 40, 80, 120, 160):
        h = torch.randn((rows, head.shape[1]), device=DEV).to(torch.bfloat16)
        out = torch.empty((rows, head.shape[0]), dtype=torch.bfloat16, device=DEV)
        r = {"cublas_bf16": graph_time([lambda w=w: torch.matmul(h, w.T) for w in heads * 2])}
        if rows <= 32:
            r["his_fp8_gemv"] = graph_time([lambda w=w: M.rowwise_fp8_lm_head_logits(h, _strip(w)) for w in f8 * 2])
        if rows <= 16:
            cfgs = [(16, bn, bk, 4, st) for bn in (32, 64, 128) for bk in (128, 256) for st in (3, 4)]
        else:
            cfgs = [(bm, bn, bk, wp, 3) for bm in (32, 64) for bn in (64, 128) for bk in (64, 128) for wp in (4, 8)]
        for c in cfgs:
            try:
                r["i8 %d/%d/%d/w%d/s%d" % c] = graph_time([lambda w=w: M.kdh8_logits(h, w, M.rowwise_scale_of(w), out, c)
                                                         for w in i8 * 2])
            except Exception as e:  # noqa: BLE001  (smem / register limits for some configs)
                r["i8 %d/%d/%d/w%d/s%d" % c] = None
        k = min((v, kk) for kk, v in r.items() if kk.startswith("i8") and v)
        try:
            cf = tuple(int(x.strip("ws")) for x in k[1][3:].split("/"))
            r["f8 best-i8-cfg"] = graph_time([lambda w=w: M.kdh8_logits(h, w, M.rowwise_scale_of(w), out, cf) for w in f8 * 2])
        except Exception:
            pass
        best[rows] = dict(cublas=r["cublas_bf16"], his=r.get("his_fp8_gemv"), kdh8=k[0], cfg=k[1], f8=r.get("f8 best-i8-cfg"))
        emit(kind="timing_us", rows=rows, best=best[rows], all={kk: v for kk, v in r.items() if v}, )
    emit(kind="timing_summary", best=best)


def _strip(w):
    """his GEMV path for an e4m3 head (no kdh8 tag)."""
    import sglang.kernels.ops.gemm.sm120_online_fp8 as M
    p = torch.nn.Parameter(w.data, requires_grad=False)
    setattr(p, M._SCALE_ATTR, M.rowwise_scale_of(w))
    return p


def main():
    import sglang.kernels.ops.gemm.sm120_online_fp8 as M
    assert hasattr(M, "kdh8_quantize_head"), "kdhead8 not installed"
    emit(kind="env", gpu=torch.cuda.get_device_name(), torch=torch.__version__, cfg=str(M._KDH8_CFG))
    head = load_head()
    w8i = quality(M, head, "int8")
    w8f = quality(M, head, "fp8")
    # served dispatch path: rowwise_fp8_lm_head_logits on the tagged head at 10 and 80 rows
    for rows in (10, 80, 300):
        h = torch.randn((rows, head.shape[1]), device=DEV).to(torch.bfloat16)
        a = M.rowwise_fp8_lm_head_logits(h, w8i).float()
        b = (h.float() @ (w8i.float() * M.rowwise_scale_of(w8i)[:, None]).T)
        rel = float(((a - b).abs() / b.abs().clamp_min(1.0)).max())
        emit(kind="dispatch", rows=rows, rel_err=rel, shape=list(a.shape))
        if rel > 2e-2:
            FAIL.append(("dispatch", rows, rel))
    timing(M, head, w8i, w8f)
    emit(verdict="PASS" if not FAIL else "FAIL", failures=[str(f) for f in FAIL][:20])


if __name__ == "__main__":
    try:
        main()
    except Exception:
        emit(verdict="FAIL", error=traceback.format_exc()[-4000:])
