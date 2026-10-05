"""Is replayed data the same data? (4-Oct-2026, daniel-draft/replay; the pilot replays daniel-draftcap-a-1002, whose
first 30 minutes were also captured live.)

  python compare_live_replay.py --live LIVE_CAP --replay REPLAY_CAP --ckpt CKPT --mask MASK --hot HOT
                                --tuned draft_ft.pt --out OUT.json [--max-pairs 120] [--rows 384]

1. Same prompt, same positions: live requests are matched to replay requests with the identical prompt ids. At the
   positions the live request prefilled itself, compare the target's hidden stream (hc) live vs replayed: cosine,
   relative L2, and the target's next-token distribution from each (argmax agreement, KL over the 64k hot map).
2. Generated positions: each finished live answer, found again inside a replay prompt (the re-rendered turn). Over the
   stretch where tokens and prefix are identical, compare the live decode hc with the replayed prefill hc the same way.
3. Drafter score on the same conversations: for those answers, expected tokens kept per check under the served
   sampling (T0.6 / top-k 20 / top-p 0.95, rejection sampling, fp8 draft KV, 3 steps) on the live rows vs the replayed
   rows, for the stock and the tuned drafter (train_draft.py's evaluate math).
"""
import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capture_io  # noqa: E402
import draft_torch  # noqa: E402
import replay_rows  # noqa: E402
from capture_io import IMAGE_PAD_ID, emb_plan, load_capture, read_tensor, rope_positions, stitch  # noqa: E402
from draft_torch import MAP, GatedResidual, load_draft, read_tensors  # noqa: E402
from train_draft import EXPERT_PARAMS, query_rows  # noqa: E402

MSTEPS = 3


def ctx_hc(r, end):
    parts, pos = [], 0
    for s, e, path, head, row in r.segments:
        if s >= end:
            break
        e2 = min(e, end)
        parts.append(read_tensor(path, head, "hc", rows=(row, row + e2 - s)))
        pos = e2
    assert pos == end, (r.rid, pos, end)
    return torch.cat(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", required=True)
    ap.add_argument("--replay", required=True)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--mask", required=True)
    ap.add_argument("--hot", required=True)
    ap.add_argument("--tuned", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-pairs", type=int, default=120)
    ap.add_argument("--rows", type=int, default=384)
    a = ap.parse_args()
    dev = torch.device("cuda")
    draft_torch.FAKE_FP8_KV = True
    live, rep = load_capture(a.live), load_capture(a.replay)
    stitch(live)
    stitch(rep)
    for rq in (live, rep):
        capture_io.MROPE_SHAPES.update(capture_io.learn_mrope_shapes(rq))
    replay_rows.assign(rep, MSTEPS)
    key = lambda p: hashlib.blake2b(np.ascontiguousarray(p).tobytes(), digest_size=16).digest()  # noqa: E731
    rep_ok = [r for r in rep.values() if r.segments and r.prompt is not None]
    by_prompt = {}
    for r in rep_ok:
        by_prompt.setdefault(key(r.prompt), r)
    live_ok = sorted((r for r in live.values() if r.segments and r.prompt is not None), key=lambda r: r.first_seq)
    print(json.dumps({"live_requests": len(live_ok), "replay_requests": len(rep_ok)}), flush=True)

    hot = torch.load(a.hot)
    draft = load_draft(a.ckpt, a.mask, hot, dtype=torch.float32, device=dev)
    tm = GatedResidual(combine=False).to(dev)
    names = {"hc_norm": "model.language_model.hyper_connection_mixer.hc_norm.weight",
             "down": "model.language_model.hyper_connection_mixer.input_mix_weight_down.weight",
             "up": "model.language_model.hyper_connection_mixer.input_mix_weight_up.weight"}
    got = read_tensors(a.ckpt, list(names.values()))
    for attr, n in names.items():
        getattr(tm, attr).data = got[n].float().to(dev)
    tm.requires_grad_(False)
    W_hot = draft.lm_head[draft.hot]

    def target_logp(h):
        with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16):
            return F.log_softmax(F.linear(tm.mix(h.to(dev))[0], W_hot).float(), -1)

    def agree(h1, h2):
        h1f, h2f = h1.float().to(dev), h2.float().to(dev)
        cos = F.cosine_similarity(h1f, h2f, dim=-1)
        rel = (h1f - h2f).norm(dim=-1) / h1f.norm(dim=-1).clamp_min(1e-6)
        out = {"n": int(h1.shape[0]), "cos": float(cos.mean()), "cos_min": float(cos.min()), "rel_l2": float(rel.mean())}
        lp1, lp2 = [], []
        for i in range(0, h1.shape[0], 2048):
            lp1.append(target_logp(h1[i:i + 2048]))
            lp2.append(target_logp(h2[i:i + 2048]))
        l1, l2 = torch.cat(lp1), torch.cat(lp2)
        out["argmax_agree"] = float((l1.argmax(-1) == l2.argmax(-1)).float().mean())
        out["kl"] = float((l1.exp() * (l1 - l2)).sum(-1).mean())
        return out

    def merge(acc, d):
        n0, n = acc.get("n", 0), d["n"]
        for k_, v in d.items():
            if k_ in ("n", "cos_min"):
                continue
            acc[k_] = (acc.get(k_, 0.0) * n0 + v * n) / max(1, n0 + n)
        acc["cos_min"] = min(acc.get("cos_min", 1.0), d["cos_min"])
        acc["n"] = n0 + n

    # 1. prompt positions, identical prompts
    pr, pairs = {}, 0
    for r in live_ok:
        q = by_prompt.get(key(r.prompt))
        if q is None or not r.chunks:
            continue
        lo, hi = r.prefix, len(r.prompt)
        if hi - lo < 8:
            continue
        hi = min(hi, lo + 4096)
        h_live = ctx_hc(r, hi)[lo:hi]
        h_rep = ctx_hc(q, hi)[lo:hi]
        merge(pr, agree(h_live, h_rep))
        pairs += 1
        if pairs >= a.max_pairs:
            break
    pr["pairs"] = pairs
    print(json.dumps({"prompt_positions": pr}), flush=True)

    # 2. generated positions: live answer vs its re-rendered turn in a replay prompt
    rep_by_seq = sorted(rep_ok, key=lambda r: r.first_seq)
    ans = []  # (live r, replay q, g0, n_same, live rows, replay rows)
    for r in live_ok:
        capture_io.build_tokens(r)
        P = len(r.prompt)
        G = r.tokens[P:]
        if len(G) < 16 or G[-1] != replay_rows.IM_END or r.segments[-1][1] < len(r.tokens) - 1:
            continue
        q_hit = None
        for q in rep_by_seq:  # the replay request whose prompt starts with this prompt and carries the answer
            if len(q.prompt) <= P + 16 or q.prompt[P - 1] != r.prompt[P - 1] or not np.array_equal(q.prompt[:P], r.prompt):
                continue
            same = capture_io.lcp(q.prompt[P:], G)
            if same >= 16:
                q_hit = (q, same)
                break
        if q_hit is None:
            continue
        q, same = q_hit
        ans.append((r, q, P, same))
        if len(ans) >= a.max_pairs:
            break
    gen = {}
    for r, q, P, same in ans:
        hi = P + min(same, 2048) - 1  # live hc exists at decode rows < len(tokens) - 1
        merge(gen, agree(ctx_hc(r, hi)[P:hi], ctx_hc(q, hi)[P:hi]))
    gen["answers"] = len(ans)
    print(json.dumps({"generated_positions": gen}), flush=True)

    # 3. drafter score, same answers: live decode rows vs replayed span rows (same positions, identical stretch)
    def lp_steps(r, rows, replay):
        end = rows[-1] + MSTEPS + 1
        hc = ctx_hc(r, end).to(dev)
        toks = torch.as_tensor(r.tokens[: end + 1] if not replay else r.prompt[: end + 1], device=dev)
        rows_t = torch.as_tensor(rows, device=dev)
        tok, vecs = emb_plan(r, end)
        t = torch.as_tensor(tok, device=dev)
        t = torch.where(t >= draft.embed.shape[0], torch.full_like(t, IMAGE_PAD_ID), t).clamp_min(0)
        e_in = draft.embed[t]
        for s0, n, path, head, row in vecs:
            e_in[s0:s0 + n] = read_tensor(path, head, "mm_embeds", rows=(row, row + n)).to(dev, e_in.dtype)
        if replay:
            for g0, g1 in getattr(r, "gen_spans", []) or []:
                lo, hi = g0 - 1, min(g1 - 1, end)
                if lo < hi:
                    e_in[lo:hi] = draft.embed[toks[lo + 1:hi + 1]]
        rpos = rope_positions(r, end).to(dev)
        with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16):
            n_ctx = int(rows_t[-1]) + 1
            mixed = draft.forward_steps(hc[:n_ctx], e_in[:n_ctx], rows_t, toks, MSTEPS, rpos=rpos)
            lps = [F.log_softmax(draft.logits(m).float(), -1) for m in mixed]
        return hc, rows_t, lps

    def served(tl, T=0.6, k=20, p=0.95):
        lp = F.log_softmax(tl / T, -1)
        kth = lp.topk(k, -1).values[:, -1:]
        lp = F.log_softmax(lp.masked_fill(lp < kth, float("-inf")), -1)
        srt, idx = lp.exp().sort(-1, descending=True)
        drop = (srt.cumsum(-1) - srt) >= p
        return F.log_softmax(lp.masked_fill(torch.zeros_like(drop).scatter(1, idx, drop), float("-inf")), -1)

    def score(r, rows, replay):
        hc, rows_t, lps = lp_steps(r, rows, replay)
        chain = torch.ones(len(rows), device=dev)
        total = torch.ones(len(rows), device=dev)
        acc = []
        for s_, lp in enumerate(lps):
            sl = served(target_logp(hc[rows_t + s_ + 1]))
            a_rs = torch.minimum(sl.exp(), served(lp).exp()).sum(-1)
            acc.append(float(a_rs.mean()))
            chain = chain * a_rs
            total = total + chain
        return float(total.sum()), len(rows), acc

    def load_init(path):
        init = torch.load(path)
        own = dict(draft.named_parameters())
        bufs = dict(draft.named_buffers())
        with torch.no_grad():
            for ck, v in init.items():
                name = MAP.get(ck) or EXPERT_PARAMS[ck]
                (own.get(name) if name in own else bufs[name]).copy_(v.to((own.get(name) if name in own else bufs[name]).dtype))

    out = {"prompt_positions": pr, "generated_positions": gen}
    base = {k_: v.detach().clone() for k_, v in draft.named_parameters()}
    for label in ("stock", "tuned"):
        if label == "tuned":
            load_init(a.tuned)
        else:
            with torch.no_grad():
                for k_, v in draft.named_parameters():
                    v.copy_(base[k_])
        draft.eval()
        sums = {"live": [0.0, 0], "replay": [0.0, 0]}
        for r, q, P, same in ans:
            n = min(same, len(r.tokens) - P) - 1 - MSTEPS  # rows P-1 .. P+n-2 have identical tokens in both
            if n < 8:
                continue
            rows = list(range(P - 1, P - 1 + min(n, a.rows)))
            for side, rr, rp in (("live", r, False), ("replay", q, True)):
                t_, c_, _ = score(rr, rows, rp)
                sums[side][0] += t_
                sums[side][1] += c_
        out[label] = {s: round(v[0] / max(1, v[1]), 4) for s, v in sums.items()}
        out[label]["rows"] = sums["live"][1]
        print(json.dumps({label: out[label]}), flush=True)
    json.dump(out, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
