"""Drafter acceptance by SEGMENT (reasoning / tool-call wrapper / tool-call code body / other), offline on a capture
(4-Oct-2026, daniel-draft spectree; Son: "does drafter accuracy differ between reasoning and tool calls, and could
drafting depth be set per segment?"). Runs in the lab image (torch + GPU) next to the lobotomy/mtp trainer files.

  python segment_sim.py --cap CAPDIR --ckpt CKPT --mask MASK.pt --hot HOT.json --tokenizer tokenizer.json --out OUT
                        [--rows 50000 --window 64 --steps 8 --fp8-kv]

Segments (qwen3_coder template, special tokens <think>=248068 </think>=248069 <tool_call>=248058 </tool_call>=248059):
  0 think  <think> .. </think> inclusive (generation starts inside when the prompt's last <think> is still open)
  1 wrap   <tool_call> .. </tool_call> outside think, except the parameter values
  2 body   parameter values inside a tool call: text after "<parameter=NAME>\n" up to "\n</parameter>"
  3 other  everything else (text after </think>, <|im_end|>, ...)
A token's segment is that of its first character (per-token text from the tokenizer, special tokens included).
Rows: row p (target hc at p, token p+1) drafts t_d = token p+1+d, d = 1..S; a row's segment = segment of t_1 (the
first drafted token = where the verify step starts). Per row and depth, as spectree_sim.py's teacher-forced chain:
rank of t_d in the draft's logits, q_rs(t_d), p(t_d) under the served transform, sum_x min(p, q_rs), target top-1.
Windows: per request one uniformly random window of --window rows plus one starting at a random tool-call token
(oversamples tool calls; per-segment numbers are conditional on the segment, so the mix does not bias them).
Also, from ALL captured data (no GPU): generated-token counts by segment, parameter names, and every decode step's
lanes (seq_len, accept_len) -> segment of the lane's first drafted token (seq_len + 1) = live acceptance by segment
and the per-step segment mix. Writes OUT/rows.npz, OUT/steps.npz, OUT/segstats.json.
"""
import argparse
import json
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capture_io  # noqa: E402
import draft_torch  # noqa: E402
from capture_io import IMAGE_PAD_ID, emb_plan, load_capture, read_header, read_tensor, rope_positions, stitch  # noqa: E402
from draft_torch import IDX_D, IDX_H, IDX_RATIO, MAP, GatedResidual, gemma_rms, load_draft, qsa_mask, read_tensors, rope  # noqa: E402
from train_draft import HcStore  # noqa: E402

BIG = 1 << 20
THINK, WRAP, BODY, OTHER = 0, 1, 2, 3
NAMES = ["think", "wrap", "body", "other"]
T_OPEN, T_CLOSE, TC_OPEN, TC_CLOSE = 248068, 248069, 248058, 248059
PARAM = re.compile(r"<parameter=([^>\n]*)>\n?")


def served(logits, temp, top_k, top_p):
    v, idx = logits.float().topk(top_k, -1)
    pr = torch.softmax(v / temp, -1)
    keep = (pr.cumsum(-1) - pr) < top_p
    pr = pr * keep
    return idx, pr / pr.sum(-1, keepdim=True)


def lookup(idx, pr, tok):
    return ((idx == tok[:, None]) * pr).sum(-1)


class Labeler:
    def __init__(self, tokenizer_json):
        from tokenizers import Tokenizer
        tk = Tokenizer.from_file(tokenizer_json)
        n = tk.get_vocab_size(with_added_tokens=True)
        self.text = [tk.decode([i], skip_special_tokens=False) for i in range(n)]
        self.params = Counter()

    def body_spans(self, ids, a, b, lab):
        """Label parameter values of the tool call ids[a:b] as BODY."""
        strs = [self.text[t] if 0 <= t < len(self.text) else "" for t in ids[a:b]]
        offs = np.cumsum([0] + [len(s) for s in strs])
        txt = "".join(strs)
        for m in PARAM.finditer(txt):
            self.params[m.group(1)] += 1
            s = m.end()
            e = txt.find("</parameter>", s)
            e = len(txt) if e < 0 else (e - 1 if e > s and txt[e - 1] == "\n" else e)
            if e <= s:
                continue
            j0 = int(np.searchsorted(offs[:-1], s, side="left"))      # first token starting at/after s
            j1 = int(np.searchsorted(offs[:-1], e, side="left"))      # tokens starting before e
            lab[a + j0:a + j1] = BODY

    def label(self, tokens, prompt_len):
        """Segment per position (prompt positions -1)."""
        n = len(tokens)
        lab = np.full(n, -1, dtype=np.int8)
        pr = tokens[:prompt_len]
        lo = np.flatnonzero(pr == T_OPEN)
        lc = np.flatnonzero(pr == T_CLOSE)
        state = THINK if lo.size and (not lc.size or lo[-1] > lc[-1]) else OTHER
        tc = None
        for i in range(prompt_len, n):
            t = int(tokens[i])
            if t == T_OPEN:
                state = THINK
                lab[i] = THINK
            elif t == T_CLOSE:
                lab[i] = THINK
                state = OTHER
            elif state == THINK:
                lab[i] = THINK
            elif t == TC_OPEN:
                state, tc = WRAP, i
                lab[i] = WRAP
            elif t == TC_CLOSE:
                lab[i] = WRAP
                if tc is not None:
                    self.body_spans(tokens, tc, i + 1, lab)
                state, tc = OTHER, None
            else:
                lab[i] = WRAP if state == WRAP else OTHER
        if state == WRAP and tc is not None:
            self.body_spans(tokens, tc, n, lab)
        return lab


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", required=True)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--mask", required=True)
    ap.add_argument("--hot", required=True)
    ap.add_argument("--tokenizer", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--init", help="optional draft_ft.pt (dense tensors, checkpoint names)")
    ap.add_argument("--rows", type=int, default=50000)
    ap.add_argument("--window", type=int, default=64)
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--temp", type=float, default=0.7)
    ap.add_argument("--top-k", type=int, default=20)
    ap.add_argument("--top-p", type=float, default=0.95)
    ap.add_argument("--fp8-kv", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--stats-only", action="store_true", help="segment counts + decode steps only (no GPU)")
    ap.add_argument("--holdout-games", action="store_true",
                    help="rows only from the games train_draft.py --split game --seed 0 --holdout 0.2 held out on THIS "
                    "capture (the drafter tuned on it never saw them)")
    a = ap.parse_args()
    draft_torch.FAKE_FP8_KV = a.fp8_kv
    S = a.steps
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
    L = Labeler(a.tokenizer)
    seg = {}
    gen = Counter()
    for r in reqs.values():
        if r.tokens is None or r.prompt is None:
            continue
        seg[r.rid] = L.label(r.tokens, len(r.prompt))
        g = seg[r.rid][len(r.prompt):]
        for s_ in range(4):
            gen[NAMES[s_]] += int((g == s_).sum())
    log(event="labels", requests=len(seg), generated=dict(gen), params=dict(L.params.most_common(12)),
        stitch_failed=len(failed))

    # ---- decode steps: every lane of every captured verify step ----
    st_lab, st_acc, st_id, st_bs = [], [], [], []
    nstep, mism = 0, 0
    for path in sorted(Path(a.cap).glob("*_decode_*.mtpc")):
        head = read_header(path)
        meta = read_tensor(path, head, "meta").numpy()
        rids = head["rids"]
        steps, cur = [], []
        for k, rid in enumerate(rids):
            if rid in {rids[j] for j in cur}:
                steps.append(cur)
                cur = []
            cur.append(k)
        if cur:
            steps.append(cur)
        if len(steps) != head.get("steps", len(steps)):
            mism += 1
        for lanes in steps:
            for k in lanes:
                rid, sq, ac = rids[k], int(meta[k, 0]), int(meta[k, 1])
                lb = seg.get(rid)
                v = -1
                if lb is not None:
                    v = int(lb[sq + 1]) if sq + 1 < len(lb) else (int(lb[sq]) if sq < len(lb) else -1)
                st_lab.append(v)
                st_acc.append(ac)
                st_id.append(nstep)
                st_bs.append(len(lanes))
            nstep += 1
    np.savez_compressed(a.out / "steps.npz", lab=np.asarray(st_lab, np.int8), acc=np.asarray(st_acc, np.int16),
                        step=np.asarray(st_id, np.int32), bs=np.asarray(st_bs, np.int16))
    lab_a, acc_a = np.asarray(st_lab), np.asarray(st_acc)
    live = {NAMES[s_]: {"lanes": int((lab_a == s_).sum()), "tokens_per_step": round(float(acc_a[lab_a == s_].mean()), 4)}
            for s_ in range(4) if (lab_a == s_).any()}
    stats = {"generated_tokens": dict(gen), "params": dict(L.params.most_common(20)), "decode_steps": nstep,
             "step_split_mismatch_files": mism, "lanes_unknown": int((lab_a < 0).sum()), "live_by_segment": live}
    (a.out / "segstats.json").write_text(json.dumps(stats, indent=1))
    log(event="steps", **stats)
    if a.stats_only:
        return

    # ---- rows: one random window + one tool-call window per request ----
    need = S + 1

    def eligible(r):
        Lr = min(r.segments[-1][1], len(r.tokens) - 1)
        start = len(r.prompt) - 1
        return list(range(start, Lr - need + 1)) if Lr - need + 1 > start else []

    pool = [r for r in reqs.values() if r.segments and r.rid in seg and len(eligible(r)) >= 32]
    if a.holdout_games:  # replicate train_draft.py's game split (global random seeded 0, then one shuffle)
        import train_draft as TD
        rl = [r for r in reqs.values() if r.segments and TD.query_rows(r)]
        groups = TD.chains(rl)
        size = lambda g: sum(len(TD.query_rows(r)) for r in g)  # noqa: E731
        big = sorted((g for g in groups if size(g) >= 5000), key=size, reverse=True)
        random.seed(0)
        random.shuffle(big)
        system = TD.system_prefix(rl)
        keys = list(dict.fromkeys(TD.game_key(g, system) for g in big))
        held = set(keys[:max(2, int(round(len(keys) * 0.2)))])
        hold = [r for g in big if TD.game_key(g, system) in held for r in g]
        hold_ids = {r.rid for r in hold}
        log(event="holdout", requests=len(rl), chains=len(groups), game_chains=len(big), games=len(keys),
            held_games=len(held), holdout_rows=sum(len(TD.query_rows(r)) for r in hold))
        pool = [r for r in pool if r.rid in hold_ids]
    pool.sort(key=lambda r: r.rid)
    rng.shuffle(pool)
    chosen, total = [], 0
    for r in pool:
        el = eligible(r)
        w = min(a.window, len(el))
        i = rng.randrange(0, len(el) - w + 1)
        rows = set(el[i:i + w])
        lb = seg[r.rid]
        tool = [p for p in el if lb[p + 2] in (WRAP, BODY)]
        if tool:
            p0 = rng.choice(tool)
            j = el.index(p0)
            rows |= set(el[j:j + w])
        rows = sorted(rows)
        chosen.append((r, rows))
        total += len(rows)
        if total >= a.rows:
            break
    log(event="data", pool=len(pool), chosen=len(chosen), rows=total)
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
    W_full = draft.lm_head
    HOT = draft.hot
    hot_index = torch.full((W_full.shape[0],), -1, dtype=torch.long, device=dev)
    hot_index[HOT] = torch.arange(HOT.numel(), device=dev)
    W_hot = draft.lm_head[HOT].contiguous()

    def dlogits(x):
        m = draft.mixer.mix(x)[0]
        return F.linear(m, W_hot.to(m.dtype)).float()

    def step(x_in, tok, pos, ck, cv, mask, ek, ev):
        ys, res = draft.attn_hc.mix(draft.fuse(None, x_in, draft.embed[tok]))
        q, gate, k, v = draft.row_qkv(ys, pos)
        ek, ev = ek + [k], ev + [v]
        return draft.block_rest(draft.attend(q, gate, ck, cv, mask, ek, ev), res), ek, ev

    out = {k: [] for k in ("req", "pos", "seg", "rank", "qmax", "qrst", "pt", "rsexp", "pmax", "srv_acc")}
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
            y_all, (x0, xn) = draft.attn_hc.mix(draft.fuse(None, hc, e_in))
            ck, cv, kc = draft.ctx_keys(y_all, rpos)
            y1, r0, rn = y_all[rows_t], x0[rows_t], xn[rows_t]
            q, gate, _, _ = draft.row_qkv(y1, rpos[rows_t])
            iq = rope(gemma_rms(F.linear(y1, draft.index_qk[: IDX_H * IDX_D]).view(-1, IDX_H, IDX_D), draft.idx_q_norm),
                      rpos[rows_t])
            kmax = int(rows_t.max()) + 1
            mask = qsa_mask(iq, kc[: kmax // IDX_RATIO], rows_t, kmax)
            ck, cv = ck[:kmax], cv[:kmax]
            x = draft.block_rest(draft.attend(q, gate, ck, cv, mask), (r0, rn))
            del y_all, x0, xn, kc
            real = [toks[rows_t + 1 + s] for s in range(1, S + 1)]
            cols = {k: [] for k in ("rank", "qmax", "qrst", "pt", "rsexp", "pmax")}
            ek, ev = [], []
            for s in range(1, S + 1):
                if s > 1:
                    x, ek, ev = step(x, real[s - 2], rpos[rows_t + (s - 1)], ck, cv, mask, ek, ev)
                lg = dlogits(x)
                ts = real[s - 1]
                th = hot_index[ts]
                lt = lg.gather(1, th.clamp_min(0)[:, None]).squeeze(1)
                rank = torch.where(th >= 0, (lg > lt[:, None]).sum(-1), torch.full_like(th, BIG))
                qi, qp = served(lg, a.temp, a.top_k, a.top_p)
                qi = HOT[qi]
                tl = F.linear(tm.mix(hc[rows_t + s])[0], W_full).float()
                pi, pp = served(tl, a.temp, a.top_k, a.top_p)
                eq = pi[:, :, None] == qi[:, None, :]
                cols["rank"].append(rank)
                cols["qmax"].append(torch.softmax(lg, -1).max(-1).values)
                cols["qrst"].append(lookup(qi, qp, ts))
                cols["pt"].append(lookup(pi, pp, ts))
                cols["rsexp"].append((eq * torch.minimum(pp[:, :, None], qp[:, None, :])).sum((1, 2)))
                cols["pmax"].append(pp[:, 0])
                del lg, tl
            for k_, v_ in cols.items():
                out[k_].append(torch.stack(v_, 1).float().cpu().numpy())
            del ek, ev, x, hc, mask, ck, cv
        lb = seg[r.rid]
        P = np.asarray(rows)
        out["seg"].append(np.stack([lb[P + 1 + d] for d in range(1, S + 1)], 1))
        by_seq = {int(sq): int(ac) for sq, ac, *_ in r.steps}
        out["srv_acc"].append(np.asarray([by_seq.get(p + 1, -1) for p in rows], dtype=np.int64))
        out["req"].append(np.full(n, ri, dtype=np.int64))
        out["pos"].append(P.astype(np.int64))
        nrows += n
        if ri % 25 == 0 or ri < 3:
            log(event="progress", requests=ri + 1, rows=nrows, ctx=int(end))
    arrs = {k: np.concatenate(v) for k, v in out.items() if v}
    np.savez_compressed(a.out / "rows.npz", **arrs)
    acc_rs = np.minimum(1.0, arrs["qrst"] / np.maximum(arrs["pt"], 1e-9))
    summ = {}
    for s_ in range(4):
        m = arrs["seg"][:, 0] == s_
        if m.any():
            summ[NAMES[s_]] = {"rows": int(m.sum()),
                               "rs_w4": round(float(1 + np.cumprod(acc_rs[m, :3], 1).sum(1).mean()), 4),
                               "rs_w8": round(float(1 + np.cumprod(acc_rs[m, :7], 1).sum(1).mean()), 4)}
    log(event="done", rows=nrows, **summ)


if __name__ == "__main__":
    main()
