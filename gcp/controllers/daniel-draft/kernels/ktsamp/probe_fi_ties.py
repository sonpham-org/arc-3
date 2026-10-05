"""Probe (4-Oct-2026, daniel-draft kernels): how his sgl_kernel top_k_renorm_prob / top_p_renorm_prob treat ties and
boundaries, so a top-k-first target sampler can reproduce them exactly. Pre-server script, free GPU.
One JSON line per probe; last line {"verdict": "DONE"}."""
import json
import time

import torch

DEV = "cuda"
T0 = time.time()


def emit(**kw):
    kw["t"] = round(time.time() - T0, 2)
    print(json.dumps(kw), flush=True)


def main():
    from sgl_kernel import top_k_renorm_prob, top_p_renorm_prob
    V = 248320
    # 1. top-k with ties at the k-th value (bf16-like logits: many equal values)
    for k in (1, 5, 20):
        for n_tie in (2, 3, 5):
            p = torch.full((4, V), 1e-9, device=DEV)
            for r in range(4):
                p[r, :k - 1] = torch.linspace(0.5, 0.1, max(k - 1, 1), device=DEV)[: k - 1] if k > 1 else p[r, :0]
                tie = torch.arange(k - 1, k - 1 + n_tie, device=DEV) * (r + 1) % V
                p[r, k - 1 + 10 * r: k - 1 + 10 * r + n_tie] = 0.05
            p = p / p.sum(1, keepdim=True)
            out = top_k_renorm_prob(p, torch.full((4,), k, dtype=torch.int32, device=DEV))
            kept = (out > 0).sum(1).tolist()
            emit(probe="topk_ties", k=k, n_tie=n_tie, kept=kept,
                 kept_tie_ids=[torch.nonzero(out[r] > 0).flatten()[-n_tie - 1:].tolist() for r in range(2)])
    # 2. top-k on random rows of bf16-rounded logits (realistic ties), vs "keep >= k-th value" and "exactly k"
    g = torch.Generator(device=DEV).manual_seed(0)
    lg = (torch.randn((256, V), generator=g, device=DEV) * 3).to(torch.bfloat16).float()
    lg[:, :40] += 12.0
    lg = lg.to(torch.bfloat16).float()
    p = torch.softmax(lg / 0.6, -1)
    out = top_k_renorm_prob(p, torch.full((256,), 20, dtype=torch.int32, device=DEV))
    kth = p.topk(20, dim=1).values[:, -1:]
    ge = (p >= kth).sum(1)
    kept = (out > 0).sum(1)
    emit(probe="topk_bf16_rows", rows=256, rows_with_ties_at_k=int((ge > 20).sum()), kept_eq_20=int((kept == 20).sum()),
         kept_eq_ge=int((kept == ge).sum()), kept_hist=torch.bincount(kept, minlength=26)[15:26].tolist(),
         renorm_err=float((out.sum(1) - 1).abs().max()),
         value_vs_p_over_sum_maxrel=float(((out - torch.where(out > 0, p, 0) / torch.where(out > 0, p, 0).sum(1, keepdim=True)).abs()).max()))
    # which of the tied ones are kept when exactly 20? lowest index?
    rows = torch.nonzero((ge > 20) & (kept == 20)).flatten()[:4].tolist()
    info = []
    for r in rows:
        tied = torch.nonzero(p[r] == kth[r]).flatten().tolist()
        info.append(dict(row=r, tied_ids=tied[:8], kept_tied=[i for i in tied if out[r, i] > 0][:8]))
    emit(probe="topk_tie_pick", rows=info)
    # 3. top-p boundary: cumulative exactly at p, and ties straddling p
    for case, vals, tp in (("exact_boundary", [0.5, 0.45, 0.05], 0.95), ("above", [0.5, 0.44, 0.06], 0.95),
                           ("tie_straddle", [0.4, 0.2, 0.2, 0.2], 0.7), ("tie_straddle2", [0.4, 0.2, 0.2, 0.2], 0.6),
                           ("first_exceeds", [0.97, 0.03], 0.95), ("all", [0.25] * 4, 0.95)):
        p = torch.zeros((1, V), device=DEV)
        p[0, 100:100 + len(vals)] = torch.tensor(vals, device=DEV)
        out = top_p_renorm_prob(p, torch.tensor([tp], device=DEV))
        emit(probe="topp_boundary", case=case, vals=vals, top_p=tp, kept=torch.nonzero(out[0] > 0).flatten().tolist(),
             out=[round(float(x), 6) for x in out[0, 100:100 + len(vals)]])
    # 4. top-p on realistic rows after top-k 20: compare with "keep while exclusive cumsum < p" (sorted desc, ties by id)
    lg = (torch.randn((512, V), generator=g, device=DEV) * 2).to(torch.bfloat16).float()
    lg[:, :30] += torch.rand((512, 30), generator=g, device=DEV) * 14
    lg = lg.to(torch.bfloat16).float()
    p = torch.softmax(lg / 0.6, -1)
    pk = top_k_renorm_prob(p, torch.full((512,), 20, dtype=torch.int32, device=DEV))
    pp = top_p_renorm_prob(pk, torch.full((512,), 0.95, device=DEV))
    v, i = pk.topk(20, dim=1)
    excl = v.cumsum(1) - v
    mine = torch.zeros_like(pk)
    keep = excl < 0.95
    keep[:, 0] = True
    mine.scatter_(1, i, torch.where(keep, v, 0))
    mine = mine / mine.sum(1, keepdim=True)
    same = ((mine > 0) == (pp > 0)).all(1)
    emit(probe="topp_rows", rows=512, same_support=int(same.sum()), max_abs=float((mine - pp).abs().max()),
         diff_rows=[dict(n_fi=int((pp[r] > 0).sum()), n_mine=int((mine[r] > 0).sum()),
                         cum=[round(float(x), 5) for x in v[r].cumsum(0)[:6]])
                    for r in torch.nonzero(~same).flatten()[:5].tolist()])
    emit(verdict="DONE")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        emit(verdict="FAIL", error=traceback.format_exc()[-3000:])
