"""Block drafter scoping trainer (DFlash plan phase 2; 4-Oct-2026, Son: "5-10 GPU hours is not bad, give it a try").

A DSpark-style block drafter for Qwen3.8-Flash-Next on Daniel's stack, trained and scored offline on a stored MTP
capture (capture_io .mtpc: the target's pre-mixer 4-stream hc [T, 10240] per position + token ids), against the tuned
chained MTP drafter (draft_ft.pt) on the SAME held-out games and rows.

Block at anchor p (row p = target hc_p, token p+1 known; same convention as train_draft.py):
  features   f_j = target_mixer.mix(hc_j)  [2560], the big model's own 10240->2560 merge (frozen, copied)
  context    shared keys/values from f_j for the W most recent positions j <= p, computed ONCE and reused by every
             layer (served memory = one layer of K/V per token, like today's drafter), rounded through fp8 as served
  slots      i = 0..B-1 at positions p+1+i: slot 0 = embed(token p+1) + base, slots 1.. = mask + base, base =
             proj(f_p) + a learned slot offset; slot i predicts token p+2+i; slots attend to the context window and
             to each other (bidirectional inside the block)
  layers     L dense layers: gated attention shaped like the MTP layer (24 q / 2 kv heads x 256, partial rope, q/k
             gemma-RMS; initialised from the MTP layer) + SwiGLU MLP (down zero-init)
  head       gemma-RMS -> the target's frozen lm_head rows over the 64k hot map
Loss per slot i vs the target distribution for token p+2+i (target_logp(hc[p+1+i]), teacher-forced), both at the
served temperature: 0.9 TV + 0.1 CE (DSpark), weighted exp(-i / gamma) (DFlash position decay), + KL on slots 0-1.
Eval (served sampling: temperature, top-k, top-p; rejection sampling a_i = sum min(p_i, q_i)): expected tokens kept
per verify step at width W = 1 + sum_{s=1}^{W-1} prod_{i<s} a_i, for W = 2..B+1, block and chain on the same rows.

Run on a daniel-draft lab VM (blockdraft/bd_worker.sh injects --cap/--ckpt/--mask/--hot/--tuned/--out):
  python train_block.py --cap CAP --ckpt CKPT --mask MASK --hot HOT --tuned draft_ft.pt --out OUT [--steps 3000 ...]
"""
import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capture_io  # noqa: E402
import draft_torch as DT  # noqa: E402
import train_draft as TD  # noqa: E402
from capture_io import IMAGE_PAD_ID, emb_plan, load_capture, rope_positions, stitch  # noqa: E402
from draft_torch import H, HC, HD, NKV, NQ, GatedResidual, fp8_round, gemma_rms, load_draft, read_tensors, rope  # noqa: E402

TARGET_MIX = {"hc_norm": "model.language_model.hyper_connection_mixer.hc_norm.weight",
              "down": "model.language_model.hyper_connection_mixer.input_mix_weight_down.weight",
              "up": "model.language_model.hyper_connection_mixer.input_mix_weight_up.weight"}


class DiskStore:
    """TD.HcStore's interface (context, vec, rows) reading hc rows from the .mtpc files on demand instead of holding
    every capture in host RAM (one capture is ~70 GB; --disk lets several captures train on one lab VM)."""

    def __init__(self, reqs):
        self.files = None

    @staticmethod
    def rows(path, head, a, b):
        return capture_io.read_tensor(path, head, "hc", rows=(a, b))

    def context(self, r, end):
        parts, pos = [], 0
        for s, e, path, head, row in r.segments:
            if s >= end:
                break
            e2 = min(e, end)
            parts.append(self.rows(path, head, row, row + e2 - s))
            pos = e2
        assert pos == end
        return torch.cat(parts)

    @staticmethod
    def vec(path, head, row, n):
        return capture_io.read_tensor(path, head, "mm_embeds", rows=(row, row + n))


def hc_slice(store, r, lo, hi):
    """Target hc rows for positions [lo, hi) of request r (from RAM with TD.HcStore, from disk with DiskStore)."""
    parts = []
    for s, e, path, head, row in r.segments:
        a, b = max(s, lo), min(e, hi)
        if a < b:
            if isinstance(store, DiskStore):
                parts.append(store.rows(path, head, row + a - s, row + b - s))
            else:
                parts.append(store.files[path][row + a - s: row + b - s])
    out = torch.cat(parts)
    assert out.shape[0] == hi - lo, (out.shape, lo, hi)
    return out


class Layer(nn.Module):
    def __init__(self, mlp):
        super().__init__()
        self.attn_norm = nn.Parameter(torch.zeros(H))
        self.q_proj = nn.Parameter(torch.zeros(NQ * 2 * HD, H))
        self.k_proj = nn.Parameter(torch.zeros(NKV * HD, H))
        self.v_proj = nn.Parameter(torch.zeros(NKV * HD, H))
        self.q_norm = nn.Parameter(torch.zeros(HD))
        self.k_norm = nn.Parameter(torch.zeros(HD))
        self.o_proj = nn.Parameter(torch.zeros(H, NQ * HD))
        self.mlp_norm = nn.Parameter(torch.zeros(H))
        self.gate = nn.Parameter(torch.randn(mlp, H) * 0.02)
        self.up = nn.Parameter(torch.randn(mlp, H) * 0.02)
        self.down = nn.Parameter(torch.zeros(H, mlp))


class BlockDraft(nn.Module):
    def __init__(self, layers, mlp, block, window):
        super().__init__()
        self.B, self.W = block, window
        self.feat_norm = nn.Parameter(torch.zeros(H))
        self.feat_proj = nn.Parameter(torch.eye(H))
        self.emb_norm = nn.Parameter(torch.zeros(H))
        self.emb_proj = nn.Parameter(torch.zeros(H, H))
        self.mask = nn.Parameter(torch.zeros(H))
        self.slot = nn.Parameter(torch.zeros(block, H))
        self.ctx_norm = nn.Parameter(torch.zeros(H))
        self.ctx_k = nn.Parameter(torch.zeros(NKV * HD, H))
        self.ctx_v = nn.Parameter(torch.zeros(NKV * HD, H))
        self.ctx_knorm = nn.Parameter(torch.zeros(HD))
        self.layers = nn.ModuleList(Layer(mlp) for _ in range(layers))
        self.out_norm = nn.Parameter(torch.zeros(H))
        # --feat mtp: read all 4 hyper-connection streams the way the MTP layer does (HyperDFlash: plain DFlash on the
        # collapsed residual of a hyper-connection model kept only 2.14) = fc_hidden per stream, then the MTP's own
        # attn_hc mixer; initialised from the MTP layer and trained
        self.fh_norm = nn.Parameter(torch.zeros(HC * H))
        self.fh = nn.Parameter(torch.zeros(H, H))
        self.hmix = GatedResidual(combine=False)

    def feat(self, hc):
        """target hc [N, 10240] -> drafter features [N, 2560] through the 4-stream path (MTP fuse without the token)."""
        h = F.linear(gemma_rms(hc, self.fh_norm).unflatten(-1, (HC, H)), self.fh).flatten(-2)
        return self.hmix.mix(h)[0]

    def init_from_mtp(self, d):
        """Attention shapes and norms from the served MTP layer (DFlash plan: 'attention and norms initialised from
        today's MTP layer'); the token path from its fc_embedding."""
        with torch.no_grad():
            self.emb_norm.copy_(d.pre_fc_norm_embedding)
            self.emb_proj.copy_(d.fc_embedding)
            self.ctx_k.copy_(d.k_proj)
            self.ctx_v.copy_(d.v_proj)
            self.ctx_knorm.copy_(d.k_norm)
            self.fh_norm.copy_(d.pre_fc_norm_hidden)
            self.fh.copy_(d.fc_hidden)
            for n in ("hc_norm", "down", "up"):
                getattr(self.hmix, n).copy_(getattr(d.attn_hc, n))
            for L in self.layers:
                for n in ("q_proj", "k_proj", "v_proj", "q_norm", "k_norm", "o_proj"):
                    getattr(L, n).copy_(getattr(d, n))

    def forward(self, f, pos, anchors, emb0, window_mask=True):
        """f [N, H] features of positions pos [N] (ascending), anchors [R] indices into f (the p rows), emb0 [R, H]
        token p+1 embeddings -> hidden [R, B, H] (lm_head inputs)."""
        N, R, B = f.shape[0], anchors.shape[0], self.B
        cn = gemma_rms(f, self.ctx_norm)
        ck = rope(gemma_rms(F.linear(cn, self.ctx_k).view(N, NKV, HD), self.ctx_knorm), pos)
        cv = F.linear(cn, self.ctx_v).view(N, NKV, HD)
        ck, cv = fp8_round(ck), fp8_round(cv)  # served: an fp8 draft KV cache
        pp = pos[anchors]                                                         # [R]
        base = F.linear(gemma_rms(f[anchors], self.feat_norm), self.feat_proj)    # [R, H]
        e0 = F.linear(gemma_rms(emb0.to(base.dtype), self.emb_norm), self.emb_proj)
        fill = torch.cat((e0[:, None, :], self.mask.to(base.dtype).expand(R, B - 1, H)), 1)
        x = (base[:, None, :] + self.slot[None, :B, :].to(base.dtype) + fill).reshape(R * B, H)
        qpos = (pp[:, None] + 1 + torch.arange(B, device=f.device)[None, :]).reshape(-1)
        ctx_ok = pos[None, :] <= pp[:, None]
        if window_mask:
            ctx_ok = ctx_ok & (pos[None, :] > pp[:, None] - self.W)
        same = torch.eye(R, dtype=torch.bool, device=f.device)
        mask = torch.cat((ctx_ok.repeat_interleave(B, 0), same.repeat_interleave(B, 0).repeat_interleave(B, 1)), 1)
        rep = NQ // NKV
        for L in self.layers:
            h = gemma_rms(x, L.attn_norm)
            qg = F.linear(h, L.q_proj).view(R * B, NQ, 2 * HD)
            q, gate = qg[..., :HD], qg[..., HD:]
            q = rope(gemma_rms(q, L.q_norm), qpos)
            bk = rope(gemma_rms(F.linear(h, L.k_proj).view(R * B, NKV, HD), L.k_norm), qpos)
            bv = F.linear(h, L.v_proj).view(R * B, NKV, HD)
            K = torch.cat((ck.to(bk.dtype), bk)).transpose(0, 1).repeat_interleave(rep, 0)[None]
            V = torch.cat((cv.to(bv.dtype), bv)).transpose(0, 1).repeat_interleave(rep, 0)[None]
            o = F.scaled_dot_product_attention(q.transpose(0, 1)[None], K, V, attn_mask=mask[None, None])
            o = (o[0].transpose(0, 1) * torch.sigmoid(gate)).reshape(R * B, NQ * HD)
            x = x + F.linear(o, L.o_proj)
            h2 = gemma_rms(x, L.mlp_norm)
            x = x + F.linear(F.silu(F.linear(h2, L.gate)) * F.linear(h2, L.up), L.down)
        return gemma_rms(x, self.out_norm).view(R, B, H)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", action="append", required=True)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--mask", required=True)
    ap.add_argument("--hot", required=True)
    ap.add_argument("--tuned", help="chain baseline: the tuned MTP draft_ft.pt (scored on the same rows)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--block", type=int, default=8)
    ap.add_argument("--layers", type=int, default=3)
    ap.add_argument("--mlp", type=int, default=6144)
    ap.add_argument("--window", type=int, default=256)
    ap.add_argument("--steps", type=int, default=3000)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--rows", type=int, default=160, help="anchors per step (one contiguous run of one request)")
    ap.add_argument("--temp", type=float, default=0.6, help="served temperature: loss and eval")
    ap.add_argument("--top-k", type=int, default=20)
    ap.add_argument("--top-p", type=float, default=0.95)
    ap.add_argument("--gamma", type=float, default=7.0, help="slot weight exp(-i / gamma)")
    ap.add_argument("--kl12", type=float, default=0.5, help="extra KL weight on slots 0-1")
    ap.add_argument("--holdout", type=float, default=0.2)
    ap.add_argument("--eval-every", type=int, default=500)
    ap.add_argument("--eval-rows", type=int, default=6000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--chain-only", action="store_true", help="score only the chain baseline, no block training")
    ap.add_argument("--disk", action="store_true", help="read hc rows from the capture files on demand (DiskStore) "
                                                         "instead of loading every capture into host RAM")
    ap.add_argument("--feat", choices=["mtp", "mixer"], default="mtp",
                    help="drafter input: mtp = all 4 hc streams via the MTP's fc_hidden + attn_hc mixer (trained); "
                         "mixer = the target's final mixer (frozen; bd1, 4-Oct: 2.03 kept at W6 vs chain 3.76)")
    a = ap.parse_args()
    B = a.block
    TD.MSTEPS = B  # query rows: hc to p+B, tokens to p+B+1 (both drafters scored on the same rows, B steps deep)
    random.seed(a.seed)
    torch.manual_seed(a.seed)
    a.out.mkdir(parents=True, exist_ok=True)
    log = open(a.out / "log.jsonl", "a")

    def emit(**kw):
        kw["t"] = round(time.time(), 1)
        print(json.dumps(kw), flush=True)
        log.write(json.dumps(kw) + "\n")
        log.flush()

    # ---- data: train_draft's game split, rebuilt from its helpers (same recipe, same seed) ----
    reqs, loaded = [], []
    for cap in a.cap:
        rq = load_capture(cap)
        stitch(rq)
        loaded.append(rq)
        reqs += [r for r in rq.values() if r.segments and TD.query_rows(r)]
    for rq in loaded:
        capture_io.MROPE_SHAPES.update(capture_io.learn_mrope_shapes(rq))
    groups = TD.chains(reqs)
    size = lambda g: sum(len(TD.query_rows(r)) for r in g)  # noqa: E731
    big = sorted((g for g in groups if size(g) >= 5000), key=size, reverse=True)
    random.shuffle(big)
    system = TD.system_prefix(reqs)
    keys = list(dict.fromkeys(TD.game_key(g, system) for g in big))
    n_hold = max(2, int(round(len(keys) * a.holdout)))
    held = set(keys[:n_hold])
    hold = [r for g in big if TD.game_key(g, system) in held for r in g]
    train = [r for g in groups if TD.game_key(g, system) not in held for r in g]
    store = DiskStore(reqs) if a.disk else TD.HcStore(reqs)
    emit(event="data", config={k: str(v) for k, v in vars(a).items() if k != "cap"}, caps=a.cap, games=len(keys),
         held_games=n_hold, requests=len(reqs), train_rows=sum(len(TD.query_rows(r)) for r in train),
         holdout_rows=sum(len(TD.query_rows(r)) for r in hold),
         ram_gb=0 if a.disk else round(sum(t.numel() * 2 for t in store.files.values()) / 2 ** 30, 1))

    dev = torch.device("cuda")
    hot = torch.load(a.hot) if a.hot.endswith(".pt") else json.load(open(a.hot))
    chain = load_draft(a.ckpt, a.mask, hot, dtype=torch.float32, device=dev)
    for attr in TD.EXPERT_PARAMS.values():
        w = getattr(chain, attr)
        del chain._buffers[attr]
        setattr(chain, attr, nn.Parameter(w.float(), requires_grad=False))
    if a.tuned:
        init = torch.load(a.tuned)
        own = dict(chain.named_parameters())
        with torch.no_grad():
            for ck_, v in init.items():
                own[DT.MAP.get(ck_) or TD.EXPERT_PARAMS[ck_]].copy_(v.to(torch.float32))
        emit(event="tuned", path=a.tuned, tensors=len(init))
    chain.requires_grad_(False)
    tm = GatedResidual(combine=False).to(dev)
    got = read_tensors(a.ckpt, list(TARGET_MIX.values()))
    for attr, n in TARGET_MIX.items():
        getattr(tm, attr).data = got[n].float().to(dev)
    tm.requires_grad_(False)
    W_hot = chain.lm_head[chain.hot]  # [65536, 2560] bf16
    embed = chain.embed
    hot_index = torch.full((chain.lm_head.shape[0],), -1, dtype=torch.long, device=dev)
    hot_index[chain.hot] = torch.arange(chain.hot.numel(), device=dev)

    def feats(hc):
        with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16):
            return tm.mix(hc)[0]

    def served(lp):
        """log-probs -> the served sampling distribution: temperature, top-k, then top-p (train_draft.served_logp)."""
        lp = F.log_softmax(lp.float() / a.temp, -1)
        if a.top_k > 0:
            kth = lp.topk(a.top_k, -1).values[..., -1:]
            lp = F.log_softmax(lp.masked_fill(lp < kth, float("-inf")), -1)
        if a.top_p < 1.0:
            srt, idx = lp.exp().sort(-1, descending=True)
            drop = (srt.cumsum(-1) - srt) >= a.top_p
            lp = F.log_softmax(lp.masked_fill(torch.zeros_like(drop).scatter(-1, idx, drop), float("-inf")), -1)
        return lp

    def ladder(acc):
        """acc [n, D] per-slot acceptance -> expected tokens kept per verify step for widths 2..D+1."""
        chain_p = torch.cumprod(acc, 1)
        return {f"w{w}": float((1 + chain_p[:, : w - 1].sum(1)).mean()) for w in range(2, acc.shape[1] + 2)}

    def eval_rows_iter():
        rng = random.Random(1234)
        n = 0
        for r in sorted(hold, key=lambda r: r.rid):
            rows = TD.query_rows(r)
            if len(rows) > 384:
                i = rng.randrange(0, len(rows) - 384)
                rows = rows[i:i + 384]
            yield r, rows
            n += len(rows)
            if n >= a.eval_rows:
                break

    def eval_chain():
        """The tuned chain over the same rows, B teacher-forced steps (train_draft.evaluate's served RS metric)."""
        DT.FAKE_FP8_KV = True  # served: fp8 draft KV
        accs = []
        for r, rows in eval_rows_iter():
            end = rows[-1] + B + 1
            hc = store.context(r, end).to(dev, non_blocking=True)
            toks = torch.as_tensor(r.tokens[: end + 1], device=dev)
            rows_t = torch.as_tensor(rows, device=dev)
            tok, vecs = emb_plan(r, end)
            t = torch.as_tensor(tok, device=dev)
            t = torch.where(t >= embed.shape[0], torch.full_like(t, IMAGE_PAD_ID), t).clamp_min(0)
            e_in = embed[t]
            for s0, n, path, head, row in vecs:
                e_in[s0:s0 + n] = store.vec(path, head, row, n).to(dev, e_in.dtype)
            rpos = rope_positions(r, end).to(dev)
            with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16):
                n_ctx = int(rows_t[-1]) + 1
                mixed = chain.forward_steps(hc[:n_ctx], e_in[:n_ctx], rows_t, toks, B, rpos=rpos)
                cols = []
                for s_, m in enumerate(mixed):
                    lp = F.log_softmax(chain.logits(m).float(), -1)
                    tl = F.log_softmax(F.linear(feats(hc[rows_t + s_ + 1]), W_hot).float(), -1)
                    cols.append(torch.minimum(served(tl).exp(), served(lp).exp()).sum(-1))
                accs.append(torch.stack(cols, 1))
            del hc
        DT.FAKE_FP8_KV = False
        acc = torch.cat(accs)
        return acc

    def block_batch(r, anchors):
        lo, hi = max(0, anchors[0] - a.window + 1), anchors[-1] + B + 1
        hc = hc_slice(store, r, lo, hi).to(dev, non_blocking=True)
        f = feats(hc)  # target-mixer features: the targets, and the drafter input under --feat mixer
        pos = torch.arange(lo, hi, device=dev)
        anc = torch.as_tensor(anchors, device=dev) - lo
        toks = torch.as_tensor(r.tokens[: hi + 1], device=dev)
        p_abs = anc + lo
        emb0 = embed[toks[p_abs + 1]]
        tgt_idx = anc[:, None] + 1 + torch.arange(B, device=dev)[None, :]          # f rows of hc[p+1+i]
        with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16):
            tl = F.log_softmax(F.linear(f[tgt_idx.reshape(-1)], W_hot).float(), -1).view(len(anchors), B, -1)
        true = hot_index[toks[p_abs[:, None] + 2 + torch.arange(B, device=dev)[None, :]]]  # [R, B], -1 off-map
        return (hc, f), pos, anc, emb0, tl, true

    def drafter_in(model, hf):
        hc, f = hf
        return model.feat(hc) if a.feat == "mtp" else f

    def eval_block(model):
        model.eval()
        accs = []
        for r, rows in eval_rows_iter():
            for c in range(0, len(rows), 128):
                hf, pos, anc, emb0, tl, _ = block_batch(r, rows[c:c + 128])
                with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16):
                    z = F.linear(model(drafter_in(model, hf), pos, anc, emb0), W_hot.to(torch.bfloat16)).float()
                accs.append(torch.minimum(served(tl).exp(), served(z).exp()).sum(-1))
        model.train()
        return torch.cat(accs)

    t0 = time.time()
    acc_c = eval_chain()
    emit(event="chain_eval", rows=acc_c.shape[0], per_slot=[round(float(x), 4) for x in acc_c.mean(0)],
         kept=ladder(acc_c), seconds=round(time.time() - t0, 1))
    if a.chain_only:
        return

    model = BlockDraft(a.layers, a.mlp, B, a.window).to(dev)
    model.init_from_mtp(chain)
    del chain.gate_up, chain.down  # the chain's experts are only needed for its eval
    torch.cuda.empty_cache()
    n_params = sum(p.numel() for p in model.parameters())
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, betas=(0.9, 0.95), weight_decay=0.0)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, (s + 1) / 200) * max(0.1, 0.5 * (1 + math.cos(math.pi * min(1.0, s / max(1, a.steps))))))
    wslot = torch.exp(-torch.arange(B, device=dev, dtype=torch.float32) / a.gamma)
    weights = [len(TD.query_rows(r)) for r in train]
    emit(event="block_init", params_m=round(n_params / 1e6, 1), train_requests=len(train))

    def evaluate(step):
        t1 = time.time()
        acc_b = eval_block(model)
        emit(event="eval", step=step, rows=acc_b.shape[0], per_slot=[round(float(x), 4) for x in acc_b.mean(0)],
             kept=ladder(acc_b), chain_kept=ladder(acc_c), seconds=round(time.time() - t1, 1))

    evaluate(0)
    for step in range(1, a.steps + 1):
        r = random.choices(train, weights=weights)[0]
        rows = TD.query_rows(r)
        i0 = random.randrange(0, max(1, len(rows) - a.rows))
        anchors = rows[i0:i0 + a.rows]
        hf, pos, anc, emb0, tl, true = block_batch(r, anchors)
        with torch.autocast("cuda", dtype=torch.bfloat16):
            z = F.linear(model(drafter_in(model, hf), pos, anc, emb0), W_hot.to(torch.bfloat16)).float()
        pT = F.log_softmax(tl / a.temp, -1)
        qT = F.log_softmax(z / a.temp, -1)
        tv = 0.5 * (pT.exp() - qT.exp()).abs().sum(-1)                              # [R, B]
        ce = -qT.gather(-1, true.clamp_min(0)[..., None]).squeeze(-1) * (true >= 0)
        kl = (pT.exp() * (pT - qT)).sum(-1)
        per_slot = 0.9 * tv + 0.1 * ce
        loss = (per_slot * wslot).sum(1).mean() / wslot.sum() + a.kl12 * kl[:, :2].mean()
        opt.zero_grad(set_to_none=True)
        loss.backward()
        gn = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        if step % 25 == 0:
            emit(event="train", step=step, loss=round(loss.item(), 4), tv=[round(float(x), 3) for x in tv.mean(0)],
                 grad_norm=round(float(gn), 3), lr=round(sched.get_last_lr()[0], 7))
        if step % a.eval_every == 0 or step == a.steps:
            evaluate(step)
    torch.save({k: v.detach().cpu() for k, v in model.state_dict().items()}, a.out / "block.pt")

    # serving-cost probe: one forward for 13 games (bf16, eval), median of 20, context = the window
    model.eval()
    r = max(hold, key=lambda r: len(TD.query_rows(r)))
    rows = TD.query_rows(r)[-13:]
    hf, pos, anc, emb0, _, _ = block_batch(r, rows)
    times = []
    with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16):
        for _ in range(25):
            torch.cuda.synchronize()
            t1 = time.time()
            model(drafter_in(model, hf), pos, anc, emb0)
            torch.cuda.synchronize()
            times.append(time.time() - t1)
    emit(event="cost_probe", anchors=len(rows), block=B, median_ms=round(1000 * sorted(times[5:])[10], 2),
         note="eager PyTorch, masks rebuilt each call; an upper bound on a fused served kernel")
    emit(event="done", saved=str(a.out / "block.pt"))


if __name__ == "__main__":
    main()
