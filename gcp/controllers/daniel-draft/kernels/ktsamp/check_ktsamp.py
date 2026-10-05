"""ktsamp patch-set check in the PATCHED install (4-Oct-2026, daniel-draft kernels). Pre-server script, free GPU.

eagle_utils._kts_target_probs (top-k-first target p) vs his dense chain (softmax(logits / T) -> sgl_kernel
top_k_renorm_prob -> top_p_renorm_prob, rows repeated per draft token) on target-shaped logits (V = 248,320, rounded
to bf16 like the lm_head output, so ties are common): same support (ties kept like flashinfer), max |dp|; tie-heavy
rows; mixed requests (greedy / top-k 5 / top-p 0.5); top-p off; then the chain rejection-sampling kernel fed from each
p with the same coins and draft q: identical accept counts and tokens; overflow counter; time per verify at 40 / 80 /
120 / 160 rows. One JSON line per result; last line {"verdict": ...}.
"""
import json
import time
import traceback

import torch

DEV = "cuda"
T0 = time.time()
FAIL = []
V = 248320


def emit(**kw):
    kw["t"] = round(time.time() - T0, 1)
    print(json.dumps(kw), flush=True)


def logits_like(R, seed, spread=14.0, n_top=30, base=2.0):
    g = torch.Generator(device=DEV).manual_seed(seed)
    x = torch.randn((R, V), generator=g, device=DEV) * base
    top = torch.randint(0, V, (R, n_top), generator=g, device=DEV)
    x.scatter_(1, top, torch.rand((R, n_top), generator=g, device=DEV) * spread + 6.0)
    return x.to(torch.bfloat16).float()  # lm_head output is bf16


def dense(logits, T, k, p, W, need_k=True, need_p=True):
    from sgl_kernel import top_k_renorm_prob, top_p_renorm_prob
    et = torch.repeat_interleave(T, W, dim=0)
    pr = torch.softmax(logits / et, dim=-1)
    if need_k:
        pr = top_k_renorm_prob(pr, torch.repeat_interleave(k, W, dim=0))
    if need_p:
        pr = top_p_renorm_prob(pr, torch.repeat_interleave(p, W, dim=0))
    return pr


def compare(E, label, logits, T, k, p, W, need_p=True, strict=True):
    a = dense(logits, T, k, p, W, need_p=need_p)
    b = E._kts_target_probs(logits, T, k, p, W, need_p)
    torch.cuda.synchronize()
    sa, sb = a > 0, b > 0
    same = (sa == sb).all(1)
    md = float((a - b).abs().max())
    rel = float(((a - b).abs() / a.clamp_min(1e-30)).masked_fill(~sa, 0).max())
    rs = float((b.sum(1) - 1).abs().max())
    ok = bool(same.all()) and md < 1e-5 and rs < 1e-5
    bad = torch.nonzero(~same).flatten()[:3].tolist()
    emit(kind="p", label=label, rows=logits.shape[0], W=W, same_support_rows=int(same.sum()), max_abs_diff=md,
         max_rel_diff_on_support=rel, rowsum_err=rs, support_sizes=[int(x) for x in sb.sum(1)[:12]],
         mismatch=[dict(row=r, n_dense=int(sa[r].sum()), n_kts=int(sb[r].sum())) for r in bad], ok=ok)
    if strict and not ok:
        FAIL.append(("p", label))
    return a, b


def chain_compare(E, a, b, bs, W, seed):
    """Same coins and draft q into his chain kernel from both p: accept counts / tokens must match."""
    from sglang.kernels.ops.speculative.reject_sampling import chain_speculative_sampling_triton
    g = torch.Generator(device=DEV).manual_seed(seed)
    tp_a, tp_b = a.view(bs, W, V), b.view(bs, W, V)
    q = torch.zeros_like(tp_a)
    # draft q: the target p slightly perturbed on its support (like a good drafter)
    q.copy_(tp_a * torch.rand(tp_a.shape, generator=g, device=DEV).mul(0.6).add(0.7))
    q = q / q.sum(-1, keepdim=True).clamp_min(1e-30)
    draft = torch.multinomial(q[:, :-1].reshape(-1, V).clamp_min(0), 1, generator=g).view(bs, W - 1)
    cand = torch.cat([torch.zeros((bs, 1), dtype=torch.long, device=DEV), draft], 1)
    ridx = torch.arange(bs * W, device=DEV, dtype=torch.long).view(bs, W)
    coins = torch.rand((bs, W - 1), generator=g, device=DEV)
    coins_f = torch.rand((bs,), generator=g, device=DEV)
    outs = []
    for tp in (tp_a, tp_b):
        pred = torch.full((bs * W,), -1, dtype=torch.int32, device=DEV)
        acc_i = torch.full((bs, W), -1, dtype=torch.int32, device=DEV)
        acc_n = torch.zeros(bs, dtype=torch.int32, device=DEV)
        chain_speculative_sampling_triton(predicts=pred, accept_index=acc_i, accept_token_num=acc_n, candidates=cand,
                                          retrive_index=ridx, retrive_next_token=None, retrive_next_sibling=None,
                                          uniform_samples=coins, uniform_samples_for_final_sampling=coins_f,
                                          target_probs=tp.contiguous(), draft_probs=q[:, : W - 1].contiguous(),
                                          threshold_single=1.0, threshold_acc=1.0, deterministic=True)
        outs.append((pred.clone(), acc_n.clone()))
    torch.cuda.synchronize()
    same_n = float((outs[0][1] == outs[1][1]).float().mean())
    same_tok = float((outs[0][0] == outs[1][0]).float().mean())
    emit(kind="chain", bs=bs, W=W, same_accept_count=same_n, same_tokens=same_tok,
         mean_accept=float(outs[0][1].float().mean()))
    if same_n < 0.995:
        FAIL.append(("chain", same_n))


def timing(E, reps=20):
    res = {}
    for R, W in ((40, 4), (80, 8), (120, 12), (160, 16)):
        bs = R // W
        lg = logits_like(R, 70)
        T = torch.full((bs, 1), 0.6, device=DEV)
        k = torch.full((bs,), 20, dtype=torch.int32, device=DEV)
        p = torch.full((bs,), 0.95, device=DEV)
        r = {}
        for name, fn in (("dense", lambda: dense(lg, T, k, p, W)),
                         ("ktsamp", lambda: E._kts_target_probs(lg, T, k, p, W, True))):
            for _ in range(3):
                fn()
            torch.cuda.synchronize()
            e0, e1 = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
            e0.record()
            for _ in range(reps):
                fn()
            e1.record()
            torch.cuda.synchronize()
            r[name] = round(e0.elapsed_time(e1) * 1e3 / reps, 1)
        emit(kind="timing_us_per_verify", rows=R, W=W, **r)
        res[R] = r
    return res


def main():
    import sglang.srt.speculative.eagle_utils as E
    from sglang.srt.sampling.sampling_batch_info import SamplingBatchInfo
    assert hasattr(E, "_kts_target_probs"), "ktsamp not installed"
    assert "kts_max_top_k" in SamplingBatchInfo.__dataclass_fields__
    emit(kind="env", gpu=torch.cuda.get_device_name(), torch=torch.__version__, on=E._KTS_ON, ch=E._KTS_CH, cap=E._KTS_CAP)
    for W, bs in ((4, 10), (8, 10), (16, 10)):
        R = bs * W
        lg = logits_like(R, W)
        T = torch.full((bs, 1), 0.6, device=DEV)
        k = torch.full((bs,), 20, dtype=torch.int32, device=DEV)
        p = torch.full((bs,), 0.95, device=DEV)
        a, b = compare(E, f"arc W{W}", lg, T, k, p, W)
        chain_compare(E, a, b, bs, W, seed=W)
    # flat rows: top-k boundary ties and top-p ties (few strong ids, many bf16-equal ones)
    lg = logits_like(64, 5, spread=1.0, n_top=60, base=0.5)
    compare(E, "flat tie-heavy", lg, torch.full((16, 1), 0.6, device=DEV), torch.full((16,), 20, dtype=torch.int32,
            device=DEV), torch.full((16,), 0.95, device=DEV), 4)
    # mixed requests
    W = 4
    T = torch.tensor([[1.0], [0.6], [1.0], [0.7]] * 4, device=DEV)
    k = torch.tensor([1, 20, 5, 32] * 4, dtype=torch.int32, device=DEV)
    p = torch.tensor([1.0, 0.95, 0.5, 1.0] * 4, device=DEV)
    compare(E, "mixed greedy/k5 p0.5/k32", logits_like(64, 6), T, k, p, W)
    compare(E, "top-p off", logits_like(64, 7), torch.full((16, 1), 0.6, device=DEV),
            torch.full((16,), 20, dtype=torch.int32, device=DEV), torch.ones(16, device=DEV), 4, need_p=False)
    ovf = int(E._kts_overflow(torch.device(DEV)).item())
    emit(kind="overflow_rows", n=ovf)
    if ovf:
        FAIL.append(("overflow", ovf))
    try:
        timing(E)
    except Exception:
        emit(kind="error", where="timing", tb=traceback.format_exc()[-3000:])
    emit(verdict="PASS" if not FAIL else "FAIL", failures=[str(f) for f in FAIL][:20])


if __name__ == "__main__":
    try:
        main()
    except Exception:
        emit(verdict="FAIL", error=traceback.format_exc()[-4000:])
