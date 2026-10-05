"""Offline simulation of draft TREES and confidence-cut DRAFT DEPTH for Daniel Franzen's MTP drafter (3-Oct-2026,
daniel-draft spectree). Runs in the lab image (torch + GPU) next to the lobotomy/mtp trainer files.

  python spectree_sim.py --cap CAPDIR --ckpt CKPT --mask MASK.pt --hot HOT(.json|.pt) --out OUT
                         [--rows 24000 --window 128 --steps 7 --beam-k 1,2,4 --beam-steps 6 --fp8-kv]

Why the recorded tokens are enough: the live run sampled every token from the target (T 0.7, top-k 20, top-p 0.95;
speculative decoding is lossless), so the token that really came at each position is a sample of the target's
verify distribution p.
  * Target-only verify (his non-RS path, tree_speculative_sampling_target_only, one-hot drafts, thresholds 1.0) is the
    same as: draw x ~ p, descend into the child whose token is x, else stop with x as the bonus. So a chain or tree
    keeps exactly the longest prefix of the REAL continuation that it contains. Only the draft's distributions along
    the real path (teacher-forced) decide that for a static tree; for sglang's dynamic tree the draft is also run on
    every beam node (off-path nodes compete for the N-1 slots).
  * Rejection sampling (patch 0008 v2: d ~ q_rs, accept with min(1, p/q)): given the target produced t, the chance the
    draft had proposed and kept t is min(1, q_rs(t) / p(t)) (maximal coupling) -> an unbiased per-sample estimate.
Per sampled row p (row = target hc at p + token p+1; t_s = token p+1+s):
  teacher-forced chain, steps 1..S: rank of t_s in the draft's hot-map logits, draft top-1 probability (T 1),
  q1(t_s) (T 1), q_rs(t_s), p(t_s), sum_x min(p, q_rs) and p(argmax q) (expectations, for cross-checks), target top-1;
  dynamic tree, for each topk k (beam + rerank as spec_utils.select_top_k_tokens / organize_draft_results; topk 1 =
  the served free-running greedy chain): per level, the global score rank of the real token's node (BIG = absent),
  and for k = 1 the chain's top-1 probability and tokens (compared with the served draft tokens at verify starts).
Writes OUT/rows.npz and OUT/summary.json.
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capture_io  # noqa: E402
import draft_torch  # noqa: E402
from capture_io import IMAGE_PAD_ID, emb_plan, load_capture, rope_positions, stitch  # noqa: E402
from draft_torch import (IDX_D, IDX_H, IDX_RATIO, MAP, GatedResidual, gemma_rms, load_draft, qsa_mask,  # noqa: E402
                         read_tensors, rope)
from train_draft import HcStore  # noqa: E402

BIG = 1 << 20


def served(logits, temp, top_k, top_p):
    """SGLang's verify transform (softmax(l / T) -> top_k_renorm_prob -> top_p_renorm_prob) on [n, V] logits.
    Returns (idx [n, k], probs [n, k]) over the top-k ids, zero where top-p dropped (rows sum to 1)."""
    v, idx = logits.float().topk(top_k, -1)
    pr = torch.softmax(v / temp, -1)       # == softmax over the full row, renormalized on the top k
    keep = (pr.cumsum(-1) - pr) < top_p    # the smallest prefix reaching top_p
    pr = pr * keep
    return idx, pr / pr.sum(-1, keepdim=True)


def lookup(idx, pr, tok):
    """Probability of tok [n] under (idx, pr) [n, k]."""
    return ((idx == tok[:, None]) * pr).sum(-1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", required=True)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--mask", required=True)
    ap.add_argument("--hot", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--init", help="optional draft_ft.pt (dense tensors, checkpoint names)")
    ap.add_argument("--rows", type=int, default=24000)
    ap.add_argument("--window", type=int, default=128, help="contiguous rows per request")
    ap.add_argument("--steps", type=int, default=7, help="teacher-forced chain depth")
    ap.add_argument("--beam-k", default="1,2,4")
    ap.add_argument("--beam-steps", type=int, default=6, help="tree depth (levels) for k >= 2; k = 1 uses --steps")
    ap.add_argument("--chunk", type=int, default=128, help="beam nodes per draft pass")
    ap.add_argument("--temp", type=float, default=0.7)
    ap.add_argument("--top-k", type=int, default=20)
    ap.add_argument("--top-p", type=float, default=0.95)
    ap.add_argument("--fp8-kv", action="store_true", help="fp8 e4m3 draft KV (his launcher's draft KV dtype)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-requests", type=int, default=0, help="debug: stop after this many requests")
    a = ap.parse_args()
    draft_torch.FAKE_FP8_KV = a.fp8_kv
    S = a.steps
    ks = [int(x) for x in a.beam_k.split(",") if x.strip()]
    a.out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(a.seed)
    t0 = time.time()

    def log(**kw):
        kw["t"] = round(time.time() - t0, 1)
        print(json.dumps(kw), flush=True)

    reqs = load_capture(a.cap)
    failed = stitch(reqs)
    for k_, v_ in capture_io.learn_mrope_shapes(reqs).items():
        capture_io.MROPE_SHAPES.setdefault(k_, v_)
    need = S + 1

    def eligible(r):
        L = min(r.segments[-1][1], len(r.tokens) - 1)
        start = len(r.prompt) - 1
        return list(range(start, L - need + 1)) if L - need + 1 > start else []

    pool = [r for r in reqs.values() if r.segments and len(eligible(r)) >= 32]
    pool.sort(key=lambda r: r.rid)
    rng.shuffle(pool)
    chosen, total = [], 0
    for r in pool:
        el = eligible(r)
        w = min(a.window, len(el))
        i = rng.randrange(0, len(el) - w + 1)
        chosen.append((r, el[i:i + w]))
        total += w
        if total >= a.rows or (a.max_requests and len(chosen) >= a.max_requests):
            break
    log(event="data", requests=len(reqs), stitch_failed=len(failed), pool=len(pool), chosen=len(chosen), rows=total)
    store = HcStore([r for r, _ in chosen])
    log(event="hc_loaded", ram_gb=round(sum(t.numel() * 2 for t in store.files.values()) / 2 ** 30, 1))

    hot = torch.load(a.hot) if a.hot.endswith(".pt") else json.load(open(a.hot))
    dev = torch.device("cuda")
    draft = load_draft(a.ckpt, a.mask, hot, dtype=torch.float32, device=dev).eval()
    if a.init:
        init = torch.load(a.init)
        own = dict(draft.named_parameters())
        with torch.no_grad():
            for ck, v in init.items():
                if ck in MAP:
                    own[MAP[ck]].copy_(v.to(torch.float32))
        log(event="init", path=a.init, tensors=len(init))
    tm = GatedResidual(combine=False).to(dev)
    names = {"hc_norm": "model.language_model.hyper_connection_mixer.hc_norm.weight",
             "down": "model.language_model.hyper_connection_mixer.input_mix_weight_down.weight",
             "up": "model.language_model.hyper_connection_mixer.input_mix_weight_up.weight"}
    got = read_tensors(a.ckpt, list(names.values()))
    for attr, n in names.items():
        getattr(tm, attr).data = got[n].float().to(dev)
    W_full = draft.lm_head                       # [V, 2560] bf16, the target's lm_head (byte-equal, build check)
    HOT = draft.hot                              # sorted real ids of the hot map
    hot_index = torch.full((W_full.shape[0],), -1, dtype=torch.long, device=dev)
    hot_index[HOT] = torch.arange(HOT.numel(), device=dev)

    W_hot = draft.lm_head[HOT].contiguous()

    def dlogits(x):  # draft hot-map logits from a step's hc_out (draft.logits with the hot rows gathered once)
        m = draft.mixer.mix(x)[0]
        return F.linear(m, W_hot.to(m.dtype)).float()

    def step(x_in, tok, pos, ck, cv, mask, ek, ev):
        ys, res = draft.attn_hc.mix(draft.fuse(None, x_in, draft.embed[tok]))
        q, gate, k, v = draft.row_qkv(ys, pos)
        ek, ev = ek + [k], ev + [v]
        return draft.block_rest(draft.attend(q, gate, ck, cv, mask, ek, ev), res), ek, ev

    out = {k: [] for k in ("req", "pos", "ctx", "rank", "qmax", "q1t", "qrst", "pt", "rsexp", "grexp", "pmax",
                           "srv_acc", "srv_drf", "chain_tok")}
    for k in ks:
        out[f"brank{k}"] = []
        out[f"bconf{k}"] = []
    nrows = 0
    for ri, (r, rows) in enumerate(chosen):
        n = len(rows)
        end = rows[-1] + S + 1
        with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16):
            hc = store.context(r, end).to(dev, non_blocking=True)
            toks = torch.as_tensor(r.tokens[: end + 1], device=dev)
            rows_t = torch.as_tensor(rows, device=dev)
            tok, vecs = emb_plan(r, end)
            t = torch.as_tensor(tok, device=dev)
            t = torch.where(t >= draft.embed.shape[0], torch.full_like(t, IMAGE_PAD_ID), t).clamp_min(0)
            e_in = draft.embed[t]
            for s0, nn_, path, head, row in vecs:
                e_in[s0:s0 + nn_] = store.vec(path, head, row, nn_).to(dev, e_in.dtype)
            rpos = rope_positions(r, end).to(dev)
            # ---- step 1 (shared by the chain and every tree): forward_steps' first half ----
            y_all, (x0, xn) = draft.attn_hc.mix(draft.fuse(None, hc, e_in))
            ck, cv, kc = draft.ctx_keys(y_all, rpos)
            y1, r0, rn = y_all[rows_t], x0[rows_t], xn[rows_t]
            q, gate, _, _ = draft.row_qkv(y1, rpos[rows_t])
            iq = rope(gemma_rms(F.linear(y1, draft.index_qk[: IDX_H * IDX_D]).view(-1, IDX_H, IDX_D), draft.idx_q_norm),
                      rpos[rows_t])
            kmax = int(rows_t.max()) + 1
            mask = qsa_mask(iq, kc[: kmax // IDX_RATIO], rows_t, kmax)
            ck, cv = ck[:kmax], cv[:kmax]
            x1 = draft.block_rest(draft.attend(q, gate, ck, cv, mask), (r0, rn))
            del y_all, x0, xn, kc
            real = [toks[rows_t + 1 + s] for s in range(1, S + 1)]          # t_1..t_S
            # ---- teacher-forced chain (static trees, RS, confidence) ----
            cols = {k: [] for k in ("rank", "qmax", "q1t", "qrst", "pt", "rsexp", "grexp", "pmax")}
            x, ek, ev = x1, [], []
            for s in range(1, S + 1):
                if s > 1:
                    x, ek, ev = step(x, real[s - 2], rpos[rows_t + (s - 1)], ck, cv, mask, ek, ev)
                lg = dlogits(x)
                ts = real[s - 1]
                th = hot_index[ts]
                lt = lg.gather(1, th.clamp_min(0)[:, None]).squeeze(1)
                rank = torch.where(th >= 0, (lg > lt[:, None]).sum(-1), torch.full_like(th, BIG))
                q1 = torch.softmax(lg, -1)
                q1t = torch.where(th >= 0, q1.gather(1, th.clamp_min(0)[:, None]).squeeze(1), torch.zeros_like(lt))
                qi, qp = served(lg, a.temp, a.top_k, a.top_p)
                qi = HOT[qi]
                tl = F.linear(tm.mix(hc[rows_t + s])[0], W_full).float()       # target logits for t_s
                pi, pp = served(tl, a.temp, a.top_k, a.top_p)
                eq = pi[:, :, None] == qi[:, None, :]
                rsexp = (eq * torch.minimum(pp[:, :, None], qp[:, None, :])).sum((1, 2))
                cols["rank"].append(rank)
                cols["qmax"].append(q1.max(-1).values)
                cols["q1t"].append(q1t)
                cols["qrst"].append(lookup(qi, qp, ts))
                cols["pt"].append(lookup(pi, pp, ts))
                cols["rsexp"].append(rsexp)
                cols["grexp"].append(lookup(pi, pp, HOT[lg.argmax(-1)]))
                cols["pmax"].append(pp[:, 0])
                del lg, q1, tl
            for k_, v_ in cols.items():
                out[k_].append(torch.stack(v_, 1).float().cpu().numpy())
            del ek, ev, x
            # ---- dynamic trees (sglang topk k), k = 1 the free-running greedy chain ----
            for k in ks:
                D = S if k == 1 else a.beam_steps
                brank = torch.full((n, D), BIG, dtype=torch.long, device=dev)
                bconf = torch.zeros((n, D), device=dev)
                chain_tok = torch.zeros((n, D), dtype=torch.long, device=dev)
                bshal = {Dp: torch.full((n, Dp), BIG, dtype=torch.long, device=dev) for Dp in range(2, D)}
                for c0 in range(0, n, max(1, a.chunk // k)):
                    sl = slice(c0, min(n, c0 + max(1, a.chunk // k)))
                    m = sl.stop - sl.start
                    rr = rows_t[sl]
                    mrep = mask[sl].repeat_interleave(k, 0)
                    lg = dlogits(x1[sl])
                    pr = torch.softmax(lg, -1)
                    p1, i1 = pr.topk(k, -1)                               # level 1 (k nodes)
                    tok_lv = HOT[i1]                                      # [m, k]
                    scores = p1
                    all_scores = [p1]
                    on_score = torch.full((m, D), -1.0, device=dev)
                    hit = tok_lv == real[0][sl][:, None]
                    on = torch.where(hit.any(-1), hit.float().argmax(-1), torch.full((m,), -1, device=dev,
                                                                                    dtype=torch.long))
                    on_score[:, 0] = torch.where(on >= 0, p1.gather(1, on.clamp_min(0)[:, None]).squeeze(1),
                                                 torch.full((m,), -1.0, device=dev))
                    if k == 1:
                        bconf[sl, 0] = p1[:, 0]
                        chain_tok[sl, 0] = tok_lv[:, 0]
                    x_par = x1[sl].repeat_interleave(k, 0)
                    ek, ev = [], []
                    ar = torch.arange(m, device=dev)
                    for s in range(2, D + 1):
                        pos = rpos[rr.repeat_interleave(k) + (s - 1)]
                        x, ek, ev = step(x_par, tok_lv.reshape(-1), pos, ck, cv, mrep, ek, ev)
                        pr = torch.softmax(dlogits(x), -1)
                        pk, ik = pr.topk(k, -1)                           # [m*k, k]
                        expand = (scores[:, :, None] * pk.view(m, k, k)).reshape(m, k * k)
                        ctok = HOT[ik].view(m, k * k)
                        all_scores.append(expand)
                        # the real token's node at level s: a child of the real node at level s-1 (if in the beam)
                        child = ctok.view(m, k, k)[ar, on.clamp_min(0)]   # [m, k]
                        hit = (child == real[s - 1][sl][:, None]) & (on >= 0)[:, None]
                        cidx = on.clamp_min(0) * k + hit.float().argmax(-1)
                        has = hit.any(-1)
                        on_score[:, s - 1] = torch.where(has, expand.gather(1, cidx[:, None]).squeeze(1),
                                                         torch.full((m,), -1.0, device=dev))
                        cs_p, cs_i = expand.topk(k, -1)                   # the next beam
                        inb = (cs_i == cidx[:, None]) & has[:, None]
                        on = torch.where(inb.any(-1), inb.float().argmax(-1), torch.full_like(on, -1))
                        par = cs_i // k                                   # [m, k] beam parents
                        flat_par = (ar[:, None] * k + par).reshape(-1)
                        x_par = x[flat_par]
                        ek = [e[flat_par] for e in ek]
                        ev = [e[flat_par] for e in ev]
                        tok_lv = ctok.gather(1, cs_i)
                        scores = cs_p
                        if k == 1:
                            bconf[sl, s - 1] = pk[:, 0]
                            chain_tok[sl, s - 1] = tok_lv[:, 0]
                    allsc = torch.cat(all_scores, 1)                      # [m, k + (D-1) k^2]
                    rk = (allsc[:, None, :] > on_score[:, :, None]).sum(-1)
                    brank[sl] = torch.where(on_score >= 0, rk, torch.full_like(rk, BIG))
                    if k > 1:  # shallower trees (Dp levels = Dp draft steps): rerank among their own candidates
                        for Dp in range(2, D):
                            nc = k + (Dp - 1) * k * k
                            rk2 = (allsc[:, None, :nc] > on_score[:, :Dp, None]).sum(-1)
                            bshal[Dp][sl] = torch.where(on_score[:, :Dp] >= 0, rk2, torch.full_like(rk2, BIG))
                    del ek, ev, x_par, x, mrep
                out[f"brank{k}"].append(brank.cpu().numpy())
                out[f"bconf{k}"].append(bconf.cpu().numpy())
                if k > 1:
                    for Dp, v_ in bshal.items():
                        out.setdefault(f"bshal{k}_{Dp}", []).append(v_.cpu().numpy())
                if k == 1:
                    out["chain_tok"].append(chain_tok.cpu().numpy())
            del hc, mask, ck, cv, x1
        # served draft tokens at verify starts (row p = seq - 1): drf[1..] = its free-running chain, acc = its tokens
        by_seq = {int(seq): (int(acc), drf) for seq, acc, pred, drf, *_ in r.steps}
        sacc = np.full(n, -1, dtype=np.int64)
        sdrf = np.full((n, 3), -1, dtype=np.int64)
        for j, p in enumerate(rows):
            st = by_seq.get(p + 1)
            if st is not None:
                sacc[j] = st[0]
                d = np.asarray(st[1][1:4], dtype=np.int64)
                sdrf[j, :len(d)] = d
        out["srv_acc"].append(sacc)
        out["srv_drf"].append(sdrf)
        out["req"].append(np.full(n, ri, dtype=np.int64))
        out["pos"].append(np.asarray(rows, dtype=np.int64))
        out["ctx"].append(np.full(n, len(r.prompt), dtype=np.int64))
        nrows += n
        if ri % 10 == 0 or ri < 3:
            log(event="progress", requests=ri + 1, rows=nrows, ctx=int(end),
                greedy_w4_so_far=round(float(1 + np.cumprod(np.concatenate(out["rank"])[:, :3] == 0, 1)
                                             .sum(1).mean()), 4))
    arrs = {k: np.concatenate(v) for k, v in out.items() if v}
    np.savez_compressed(a.out / "rows.npz", **arrs)
    # ---- quick summary (the full analysis runs offline on rows.npz) ----
    rank, pt, qrst = arrs["rank"], arrs["pt"], arrs["qrst"]
    acc_rs = np.minimum(1.0, qrst / np.maximum(pt, 1e-9))
    summ = {"rows": int(nrows), "requests": len(chosen), "fp8_kv": a.fp8_kv,
            "p_t_zero_frac": [round(float((pt[:, s] <= 0).mean()), 4) for s in range(S)]}
    for W in range(2, S + 2):
        d = W - 1
        g = np.cumprod(rank[:, :d] == 0, 1).sum(1)
        rs = np.cumprod(acc_rs[:, :d], 1).sum(1)
        summ[f"chain_w{W}"] = {"greedy": round(float(1 + g.mean()), 4), "rs": round(float(1 + rs.mean()), 4),
                               "rs_expect": round(float(1 + np.cumprod(arrs["rsexp"][:, :d], 1).sum(1).mean()), 4),
                               "greedy_expect": round(float(1 + np.cumprod(arrs["grexp"][:, :d], 1).sum(1).mean()), 4)}
    st = arrs["srv_acc"] >= 0
    if st.any():
        ct, sd = arrs["chain_tok"][st][:, :3], arrs["srv_drf"][st]
        summ["served_check"] = {"verify_starts": int(st.sum()),
                                "agree_served_draft_by_depth": [round(float((ct[:, j] == sd[:, j]).mean()), 4)
                                                                for j in range(3)],
                                "served_acc_mean": round(float(arrs["srv_acc"][st].mean()), 4),
                                "sim_greedy_w4_same_rows": round(float(
                                    1 + np.cumprod(rank[st][:, :3] == 0, 1).sum(1).mean()), 4)}
    for k in ks:
        br = arrs[f"brank{k}"]
        D = br.shape[1]
        nodes = k + (D - 1) * k * k
        res = {}
        for N in range(2, min(nodes + 1, 17) + 1):
            okk = np.cumprod(br < (N - 1), 1).sum(1)
            res[str(N)] = round(float(1 + okk.mean()), 4)
        summ[f"tree_k{k}_D{D}"] = res
    (a.out / "summary.json").write_text(json.dumps(summ, indent=1))
    log(event="done", **{k: v for k, v in summ.items() if k.startswith("chain_w4") or k == "served_check"})


if __name__ == "__main__":
    main()
