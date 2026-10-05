"""PyTorch copy of the Flash-Next MTP draft (SGLang Qwen4ExpForCausalLMMTP), for offline checks and fine-tuning.

Written from the served code (qwen4_exp_mtp.py, qwen4_exp.py, qwen3_5.py, layers/hyperconnection.py, qwen2_moe.py,
layers/attention/qsa/* at sglang qwen4-main-squashed + fork), using the reference (non-fused) math of each op:
  fuse     e = fc_embedding(gemma_rms(embed(tok p+1))); h = fc_hidden(gemma_rms_10240(hc_p) viewed [4, 2560]);
           x = h + e (broadcast over the 4 streams) -> [T, 10240]
  layer    attn_hc.mix -> gated attention (q/k Gemma-RMS per head, partial neox RoPE on the first 64 of 256 dims,
           theta 1e7, 24 q / 2 kv heads, out * sigmoid(gate), o_proj) with QSA token selection -> attn_hc.combine
           mlp_hc.mix -> MoE (softmax router over the kept experts, top-10, renormalized; silu(gate) * up; shared
           expert * sigmoid(shared_expert_gate)) -> mlp_hc.combine  => hc_out [T, 10240] (the recursion input)
  head     hyper_connection_mixer.mix(hc_out) -> lm_head, restricted to the FR-Spec hot-token map when given.
QSA (qsa_indexer.py): index q = rope(gemma_rms(W_iq x)) [4 x 128], token keys W_ik x [128]; complete 4-token groups
are averaged, gemma-normed and roped at the group's first position; a query at position p sees (p+1)//4 blocks, scores
them sum_h relu(q_h . k_b) / sqrt(128), keeps the top 512 blocks (all of them while <= 512 are visible, i.e. dense
causal attention up to 2,048 tokens) plus the unfinished tail group (p rounded down to 4 .. p).
Row p = (target hc at p, token p+1) at position p predicts token p+2. Sequences start at position 0 (rows ==
positions). Served K/V are fp8 and experts NVFP4; this copy runs bf16 (expect near-, not bit-, identical argmax).

Weights: the BF16 mtp.* tensors (model-bf16-00010..12) plus embed_tokens and lm_head; experts are pruned with the
same mask row as prune_checkpoint.py --mtp (m["mtp"], True = pruned). Dense parameters are nn.Parameters (trainable);
experts, embed and lm_head are frozen buffers.
"""
import contextlib
import json
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

HC, H, LOWRANK, NQ, NKV, HD, ROT, THETA, EPS, TOPK, E_INTER = 4, 2560, 320, 24, 2, 256, 64, 1e7, 1e-6, 10, 640
IDX_H, IDX_D, IDX_RATIO, IDX_BLOCKS = 4, 128, 4, 512
FORCE_DENSE = False  # verify_draft.py --dense: attend to every earlier token (diagnostic only)
FAKE_FP8_KV = False   # verify_draft.py --fp8-kv: round the cached K/V through fp8 e4m3 like an fp8 draft KV cache
FAKE_FP8_IDX = False  # verify_draft.py --fp8-idx: same for the QSA indexer's compressed keys


def fp8_round(x):
    """x -> fp8 e4m3 (scale 1, saturating at +-448) -> x.dtype: what an unscaled fp8 KV cache hands the kernel.
    Straight-through gradient when x requires grad (training against an fp8 draft KV)."""
    q = x.detach().float().clamp(-448.0, 448.0).to(torch.float8_e4m3fn).to(x.dtype)
    return x + (q - x.detach()) if x.requires_grad else q


def gemma_rms(x, w, group=None):
    xf = x.float()
    if group:
        xf = xf.unflatten(-1, (-1, group))
    xf = xf * torch.rsqrt(xf.pow(2).mean(-1, keepdim=True) + EPS)
    if group:
        xf = xf.flatten(-2)
    return (xf * (1.0 + w.float())).to(x.dtype)


class GatedResidual(nn.Module):
    def __init__(self, combine=True):
        super().__init__()
        self.hc_norm = nn.Parameter(torch.zeros(HC * H))
        self.down = nn.Parameter(torch.zeros(LOWRANK, HC * H))
        self.up = nn.Parameter(torch.zeros(HC * H, LOWRANK))
        self.inject = nn.Parameter(torch.zeros(HC, HC * H)) if combine else None

    def mix(self, x):
        xn = gemma_rms(x, self.hc_norm, group=H)
        w = torch.sigmoid(F.linear(F.silu(F.linear(xn, self.down) / HC), self.up))
        return (w.unflatten(-1, (HC, H)) * xn.unflatten(-1, (HC, H))).mean(-2), (x, xn)

    def combine(self, y, res):
        x, xn = res
        inj = 2 * torch.sigmoid(F.linear(xn, self.inject) / HC)
        return (x.unflatten(-1, (HC, H)) + y.unsqueeze(-2) * inj.unsqueeze(-1)).flatten(-2)


MROPE_SECTION = (11, 11, 10)  # config rope_parameters, mrope_interleaved=True


def mrope_axis_map(half=ROT // 2):
    """Which position axis (t, h, w) each frequency pair reads (qsa_indexer._rope_axis_map, interleaved MRoPE)."""
    s0, s1, s2 = MROPE_SECTION
    pair = torch.arange(half)
    axis = torch.zeros(half, dtype=torch.long)
    axis[((pair % 3) == 1) & (pair < s1 * 3)] = 1
    axis[((pair % 3) == 2) & (pair < s2 * 3)] = 2
    return axis


def rope(x, positions):
    """neox-style rotation of the first ROT dims of each head; x [T, heads, D]. positions [T] (text: all three MRoPE
    axes equal) or [T, 3] (t, h, w multimodal positions; images give rows/columns and shift later tokens)."""
    inv = THETA ** (-torch.arange(0, ROT, 2, dtype=torch.float32, device=x.device) / ROT)
    if positions.dim() == 2:
        pos = positions.float().gather(1, mrope_axis_map().to(x.device)[None, :].expand(positions.shape[0], -1))
        ang = pos * inv[None, :]
    else:
        ang = positions.float()[:, None] * inv[None, :]
    cos, sin = ang.cos()[:, None, :], ang.sin()[:, None, :]
    xf = x.float()
    x1, x2, rest = xf[..., :ROT // 2], xf[..., ROT // 2:ROT], xf[..., ROT:]
    return torch.cat((x1 * cos - x2 * sin, x2 * cos + x1 * sin, rest), -1).to(x.dtype)


_E2M1 = (0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0)


def fake_nvfp4(x, per_row_global=False, block=16):
    """Quantize-dequantize to NVFP4 along the last dim: e2m1 values in blocks of 16, e4m3 block scales, fp32 global
    scale (per tensor, or per row for per-token activation scaling). A diagnostic of what serving does to the draft's
    MoE (experts are quantized to NVFP4 at load, activations per token at run time)."""
    shape = x.shape
    xf = x.float().reshape(*shape[:-1], shape[-1] // block, block)
    amax = xf.abs().amax(dim=(-2, -1), keepdim=True) if per_row_global else xf.abs().amax()
    gs = (amax / (6.0 * 448.0)).clamp_min(1e-12)
    bs = (xf.abs().amax(-1, keepdim=True) / 6.0 / gs).clamp(max=448.0).to(torch.float8_e4m3fn).float() * gs
    bs = torch.where(bs == 0, torch.ones_like(bs), bs)
    grid = torch.tensor(_E2M1, device=x.device)
    q = grid[torch.bucketize((xf / bs).abs(), (grid[1:] + grid[:-1]) / 2)] * torch.sign(xf)
    return (q * bs).reshape(shape).to(x.dtype)


def qsa_mask(iq, kc, qpos, T):
    """Allowed-key mask [n, T] for queries at positions qpos (keys are positions 0..T-1)."""
    n = qpos.shape[0]
    keys = torch.arange(T, device=qpos.device)
    causal = keys[None, :] <= qpos[:, None]
    nvis = torch.div(qpos + 1, IDX_RATIO, rounding_mode="floor")
    if FORCE_DENSE or int(nvis.max()) <= IDX_BLOCKS:  # FORCE_DENSE: diagnostic (does the token picking matter?)
        return causal
    nb = kc.shape[0]
    scores = torch.einsum("nhd,bd->nbh", iq.float(), kc.float()).relu().sum(-1) / IDX_D ** 0.5
    blocks = torch.arange(nb, device=qpos.device)
    scores = scores.masked_fill(blocks[None, :] >= nvis[:, None], float("-inf"))
    top = scores.topk(min(IDX_BLOCKS, nb), dim=-1).indices                       # [n, 512]
    chosen = torch.zeros(n, nb, dtype=torch.bool, device=qpos.device)
    chosen.scatter_(1, top, True)
    chosen &= blocks[None, :] < nvis[:, None]                                     # -inf picks when < 512 visible
    allowed = torch.zeros(n, T, dtype=torch.bool, device=qpos.device)
    allowed[:, : nb * IDX_RATIO] = chosen.repeat_interleave(IDX_RATIO, 1)
    tail = keys[None, :] >= (nvis * IDX_RATIO)[:, None]
    allowed |= tail
    allowed &= causal
    return torch.where((nvis <= IDX_BLOCKS)[:, None], causal, allowed)


class Draft(nn.Module):
    def __init__(self, n_experts):
        super().__init__()
        self.pre_fc_norm_embedding = nn.Parameter(torch.zeros(H))
        self.pre_fc_norm_hidden = nn.Parameter(torch.zeros(HC * H))
        self.fc_embedding = nn.Parameter(torch.zeros(H, H))
        self.fc_hidden = nn.Parameter(torch.zeros(H, H))
        self.attn_hc, self.mlp_hc, self.mixer = GatedResidual(), GatedResidual(), GatedResidual(combine=False)
        self.q_proj = nn.Parameter(torch.zeros(NQ * 2 * HD, H))
        self.k_proj = nn.Parameter(torch.zeros(NKV * HD, H))
        self.v_proj = nn.Parameter(torch.zeros(NKV * HD, H))
        self.o_proj = nn.Parameter(torch.zeros(H, NQ * HD))
        self.q_norm = nn.Parameter(torch.zeros(HD))
        self.k_norm = nn.Parameter(torch.zeros(HD))
        self.index_qk = nn.Parameter(torch.zeros((IDX_H + 1) * IDX_D, H))
        self.idx_q_norm = nn.Parameter(torch.zeros(IDX_D))
        self.idx_k_norm = nn.Parameter(torch.zeros(IDX_D))
        self.router = nn.Parameter(torch.zeros(n_experts, H))
        self.sh_gate = nn.Parameter(torch.zeros(E_INTER, H))
        self.sh_up = nn.Parameter(torch.zeros(E_INTER, H))
        self.sh_down = nn.Parameter(torch.zeros(H, E_INTER))
        self.sh_expert_gate = nn.Parameter(torch.zeros(1, H))
        self.register_buffer("gate_up", torch.zeros(n_experts, 2 * E_INTER, H, dtype=torch.bfloat16), persistent=False)
        self.register_buffer("down", torch.zeros(n_experts, H, E_INTER, dtype=torch.bfloat16), persistent=False)
        self.register_buffer("embed", torch.zeros(1, H, dtype=torch.bfloat16), persistent=False)
        self.register_buffer("lm_head", torch.zeros(1, H, dtype=torch.bfloat16), persistent=False)
        self.register_buffer("hot", torch.zeros(0, dtype=torch.long), persistent=False)

    # ---- per-guess adapter (Son 4-Oct, drafter idea 3; not served yet) ----
    def add_step_adapter(self, steps, rank=64):
        """Guess s >= 2 gets x + B_s(A_s(x)) + b_s on its fused 4-stream input (A_s shared across the 4 streams), so
        the one shared layer can tell a real target state (guess 1) from its own output (later guesses). B and b start
        at zero, so the drafter is unchanged until training moves them. Covers guesses 2..steps; later ones: identity."""
        n, dev = max(0, steps - 1), self.q_proj.device
        self.step_A = nn.Parameter(torch.randn(n, rank, H, device=dev) * H ** -0.5)
        self.step_B = nn.Parameter(torch.zeros(n, H, rank, device=dev))
        self.step_b = nn.Parameter(torch.zeros(n, HC * H, device=dev))
        return self

    def step_adapt(self, x, s):
        i = s - 2
        if not hasattr(self, "step_A") or i < 0 or i >= self.step_A.shape[0]:
            return x
        v = x.unflatten(-1, (HC, H))
        v = v + F.linear(F.linear(v, self.step_A[i].to(v.dtype)), self.step_B[i].to(v.dtype))
        return v.flatten(-2) + self.step_b[i].to(v.dtype)

    # ---- multi-layer target input (Son 4-Oct, drafter idea 2, EAGLE-3 / DFlash style; not served yet) ----
    def add_aux(self, n_aux=3):
        """Rows that carry a real target state (context rows and guess 1) also read the target's stream after n_aux
        earlier layers (aux [T, n_aux * 10240], the capture's column order after the layer-47 block): each aux layer's
        10240-wide state is Gemma-RMS-normed (own weight), each of the 4 streams concatenates its n_aux 2560-slices,
        and aux_fc [2560, n_aux * 2560] maps that onto the stream, added to the fc_hidden term. aux_fc starts at zero,
        so the drafter is unchanged until training moves it. Guesses >= 2 run on the drafter's own output: no aux."""
        dev = self.q_proj.device
        self.aux_norm = nn.Parameter(torch.zeros(n_aux, HC * H, device=dev))
        self.aux_fc = nn.Parameter(torch.zeros(H, n_aux * H, device=dev))
        return self

    def aux_term(self, aux, chunk=8192):
        """[T, n_aux * 10240] aux states -> [T, 4, 2560] addition to the fc_hidden term (row chunks bound memory)."""
        n = self.aux_fc.shape[1] // H
        outs = []
        for i in range(0, aux.shape[0], chunk):
            a = gemma_rms(aux[i:i + chunk].unflatten(-1, (n, HC * H)), self.aux_norm)            # [t, n, 10240]
            a = a.unflatten(-1, (HC, H)).transpose(-3, -2).flatten(-2)                           # [t, 4, n*2560]
            outs.append(F.linear(a, self.aux_fc.to(a.dtype)))
        return torch.cat(outs)

    # ---- untied weights for the drafter's own-output guesses (drafter autoresearch 4-Oct; not served yet) ----
    def add_untie(self, names, groups=1):
        """Guesses >= 2 (which read the drafter's own output, not a target state) run with their own copies of the
        dense parameters `names` (Draft attribute paths, e.g. fc_hidden, attn_hc.down), copied from the shared ones, so
        the drafter is unchanged until training moves them. `groups` copies: guess s uses copy min(groups - 1, s - 2)
        (1 = one copy for every own-output guess). Served as a second MTP layer instance for guesses >= 2 sharing the
        routed experts, embed and lm_head: the copy is read instead of the original, no extra bytes per guess."""
        self.untie_names, self.untie_groups = tuple(names), int(groups)
        self.untie = nn.ParameterDict()
        for g in range(self.untie_groups):
            for n in self.untie_names:
                self.untie[f"c{g}__{n.replace('.', '__')}"] = nn.Parameter(self.get_parameter(n).detach().clone())
        return self

    def untie_sync(self):
        """Copy the shared parameters into every untied copy (after loading a checkpoint that has no copies)."""
        with torch.no_grad():
            for g in range(self.untie_groups):
                for n in self.untie_names:
                    self.untie[f"c{g}__{n.replace('.', '__')}"].copy_(self.get_parameter(n))

    def guess_params(self, s):
        """Context manager: guess s's parameters in place of the shared ones (no-op without add_untie or for s < 2)."""
        if s < 2 or not hasattr(self, "untie"):
            return contextlib.nullcontext()
        from torch.nn.utils.stateless import _reparametrize_module
        g = min(self.untie_groups - 1, s - 2)
        return _reparametrize_module(self, {n: self.untie[f"c{g}__{n.replace('.', '__')}"] for n in self.untie_names})

    # ---- wider shared expert (drafter autoresearch 4-Oct; not served yet) ----
    def add_sh_extra(self, n_extra):
        """n_extra more intermediate columns for the shared expert (served as one shared expert of width 640 + n_extra:
        concatenate shx_gate/shx_up after sh_gate/sh_up and shx_down after sh_down's columns, so no extra kernel).
        gate/up start random at the existing columns' scale, down at zero: the drafter is unchanged until training."""
        dev = self.q_proj.device
        self.shx_gate = nn.Parameter(torch.randn(n_extra, H, device=dev) * float(self.sh_gate.float().std()))
        self.shx_up = nn.Parameter(torch.randn(n_extra, H, device=dev) * float(self.sh_up.float().std()))
        self.shx_down = nn.Parameter(torch.zeros(H, n_extra, device=dev))
        return self

    # ---- blocks ----
    def fuse(self, tok_next, hc, e_in=None, aux=None):
        """e_in: explicit input embeddings [T, H] (image chunks, see capture_io.emb_plan); else embed(tok_next).
        aux: the target's earlier-layer states of these rows (add_aux), only for rows with a real target state."""
        emb = e_in if e_in is not None else self.embed[tok_next]
        e = F.linear(gemma_rms(emb.to(hc.dtype), self.pre_fc_norm_embedding), self.fc_embedding)
        h = F.linear(gemma_rms(hc, self.pre_fc_norm_hidden).unflatten(-1, (HC, H)), self.fc_hidden)
        if aux is not None and hasattr(self, "aux_fc"):
            h = h + self.aux_term(aux).to(h.dtype)
        return (h + e.unsqueeze(-2)).flatten(-2)

    def attention(self, x, rows, chunk=512, rpos=None):
        """x [T, H] attention inputs of ALL rows (logical positions 0..T-1); returns outputs for `rows` (sorted).
        rpos: rotary positions per logical position ([>=T] or [>=T, 3] MRoPE); default the logical positions."""
        T = x.shape[0]
        pos = torch.arange(T, device=x.device) if rpos is None else rpos[:T]
        k = rope(gemma_rms(F.linear(x, self.k_proj).view(T, NKV, HD), self.k_norm), pos)
        v = F.linear(x, self.v_proj).view(T, NKV, HD)
        ik = F.linear(x, self.index_qk[IDX_H * IDX_D:])                            # [T, 128] raw token keys
        nb = T // IDX_RATIO
        kc = ik[: nb * IDX_RATIO].view(nb, IDX_RATIO, IDX_D).float().mean(1).to(ik.dtype)
        kc = rope(gemma_rms(kc, self.idx_k_norm).unsqueeze(1), pos[: nb * IDX_RATIO: IDX_RATIO]).squeeze(1)
        if FAKE_FP8_KV:
            k, v = fp8_round(k), fp8_round(v)
        if FAKE_FP8_IDX:
            kc = fp8_round(kc)
        xq = x[rows]
        n = xq.shape[0]
        qg = F.linear(xq, self.q_proj).view(n, NQ, 2 * HD)
        q, gate = qg[..., :HD], qg[..., HD:]
        qpos = rows if rpos is None else rpos[rows]
        q = rope(gemma_rms(q, self.q_norm), qpos)
        iq = rope(gemma_rms(F.linear(xq, self.index_qk[: IDX_H * IDX_D]).view(n, IDX_H, IDX_D), self.idx_q_norm), qpos)
        kt, vt = k.transpose(0, 1).unsqueeze(0), v.transpose(0, 1).unsqueeze(0)      # [1, NKV, T, HD]
        outs = []
        for c in range(0, n, chunk):
            sl = slice(c, c + chunk)
            kmax = int(rows[sl].max()) + 1                                           # keys beyond the last query unused
            mask = qsa_mask(iq[sl], kc[: kmax // IDX_RATIO], rows[sl], kmax)
            o = F.scaled_dot_product_attention(q[sl].transpose(0, 1).unsqueeze(0), kt[:, :, :kmax], vt[:, :, :kmax],
                                               attn_mask=mask[None, None], scale=HD ** -0.5, enable_gqa=True)
            outs.append(o[0].transpose(0, 1))
        o = torch.cat(outs) * torch.sigmoid(gate)
        return F.linear(o.reshape(n, NQ * HD), self.o_proj)

    # ---- multi-step (served steps 1..3) ----
    def ctx_keys(self, y, rpos=None):
        """K, V and compressed index keys of ALL rows (attention inputs y [T, H], logical positions 0..T-1)."""
        T = y.shape[0]
        pos = torch.arange(T, device=y.device) if rpos is None else rpos[:T]
        k = rope(gemma_rms(F.linear(y, self.k_proj).view(T, NKV, HD), self.k_norm), pos)
        v = F.linear(y, self.v_proj).view(T, NKV, HD)
        ik = F.linear(y, self.index_qk[IDX_H * IDX_D:])
        nb = T // IDX_RATIO
        kc = ik[: nb * IDX_RATIO].view(nb, IDX_RATIO, IDX_D).float().mean(1).to(ik.dtype)
        kc = rope(gemma_rms(kc, self.idx_k_norm).unsqueeze(1), pos[: nb * IDX_RATIO: IDX_RATIO]).squeeze(1)
        if FAKE_FP8_KV:
            k, v = fp8_round(k), fp8_round(v)
        if FAKE_FP8_IDX:
            kc = fp8_round(kc)
        return k, v, kc

    def row_qkv(self, y, pos):
        n = y.shape[0]
        qg = F.linear(y, self.q_proj).view(n, NQ, 2 * HD)
        q = rope(gemma_rms(qg[..., :HD], self.q_norm), pos)
        k = rope(gemma_rms(F.linear(y, self.k_proj).view(n, NKV, HD), self.k_norm), pos)
        v = F.linear(y, self.v_proj).view(n, NKV, HD)
        if FAKE_FP8_KV:  # drafted positions are written to the draft KV cache too
            k, v = fp8_round(k), fp8_round(v)
        return q, qg[..., HD:], k, v

    def attend(self, q, gate, ck, cv, mask, extra_k=(), extra_v=()):
        """q [n, NQ, HD] over context keys ck/cv [T] allowed by mask [n, T], plus per-row extra keys (each [n, NKV, HD],
        row i sees only its own): the served draft decode step (frozen selection + the positions drafted since)."""
        n, T = q.shape[0], ck.shape[0]
        K = torch.cat([ck] + list(extra_k))
        V = torch.cat([cv] + list(extra_v))
        if extra_k:
            own = torch.zeros(n, n * len(extra_k), dtype=torch.bool, device=q.device)
            idx = torch.arange(n, device=q.device)
            for j in range(len(extra_k)):
                own[idx, j * n + idx] = True
            mask = torch.cat([mask, own], 1)
        rep = NQ // NKV  # expanded heads: the memory-efficient kernel (masked) instead of materialized scores
        K, V = K.repeat_interleave(rep, 1), V.repeat_interleave(rep, 1)
        o = F.scaled_dot_product_attention(q.transpose(0, 1).unsqueeze(0), K.transpose(0, 1).unsqueeze(0),
                                           V.transpose(0, 1).unsqueeze(0), attn_mask=mask[None, None],
                                           scale=HD ** -0.5)[0].transpose(0, 1)
        return F.linear((o * torch.sigmoid(gate)).reshape(n, NQ * HD), self.o_proj)

    def block_rest(self, att, res):
        x = self.attn_hc.combine(att, res)
        y2, res2 = self.mlp_hc.mix(x)
        return self.mlp_hc.combine(self.moe(y2), res2)

    def forward_steps(self, hc, e_in, rows, toks, steps=3, ctx=None, rows_grad=False, rpos=None, aux=None):
        """Served steps 1..`steps` at query rows p (sorted positions), teacher-forced on the real tokens.
        Step 1: row p = (target hc_p, e_in[p]) over the QSA selection of p. Step s >= 2: position p+s-1, input =
        (step s-1 output hc, embed(token p+s)), keys = step 1's frozen selection + the rows drafted since (the served
        QSAMTPSharedSparseIndices). Returns [mixed_1..mixed_steps] (lm_head inputs). ctx = precomputed
        (y_all, x0, xn, k, v, kc) of all rows (e.g. without gradient); rows_grad recomputes the query rows' own
        path with gradient. rpos: rotary positions per logical position, covering rows + steps (MRoPE [N, 3]).
        aux: [T, n_aux * 10240] earlier-layer target states (add_aux) for the context rows and guess 1."""
        rp = (lambda idx: idx) if rpos is None else (lambda idx: rpos[idx])  # noqa: E731
        if ctx is None:
            y_all, (x0, xn) = self.attn_hc.mix(self.fuse(None, hc, e_in, aux))
            ck, cv, kc = self.ctx_keys(y_all, rpos)
        else:
            y_all, x0, xn, ck, cv, kc = ctx
        T = hc.shape[0]
        if rows_grad:
            y1, (r0, rn) = self.attn_hc.mix(self.fuse(None, hc[rows], e_in[rows], None if aux is None else aux[rows]))
        else:
            y1, r0, rn = y_all[rows], x0[rows], xn[rows]
        q, gate, _, _ = self.row_qkv(y1, rp(rows))
        iq = rope(gemma_rms(F.linear(y1, self.index_qk[: IDX_H * IDX_D]).view(-1, IDX_H, IDX_D), self.idx_q_norm), rp(rows))
        kmax = int(rows.max()) + 1
        mask = qsa_mask(iq, kc[: kmax // IDX_RATIO], rows, kmax)
        ck, cv = ck[:kmax], cv[:kmax]
        x = self.block_rest(self.attend(q, gate, ck, cv, mask), (r0, rn))
        outs = [x]
        ek, ev = [], []
        for s in range(2, steps + 1):
            with self.guess_params(s):  # add_untie: guess s's own dense weights (no-op otherwise)
                ys, res = self.attn_hc.mix(self.step_adapt(self.fuse(None, x, self.embed[toks[rows + s]]), s))
                q, gate, k, v = self.row_qkv(ys, rp(rows + (s - 1)))
                ek.append(k)
                ev.append(v)
                x = self.block_rest(self.attend(q, gate, ck, cv, mask, ek, ev), res)
            outs.append(x)
        if hasattr(self, "untie"):
            mixed = []
            for i, o in enumerate(outs):
                with self.guess_params(i + 1):
                    mixed.append(self.mixer.mix(o)[0])
            return mixed
        return [self.mixer.mix(o)[0] for o in outs]

    def moe(self, x):
        if getattr(self, "skip_routed", False):  # bench_draft_cost.py: shared expert only (no host sync: capturable)
            out = torch.zeros_like(x)
        else:
            out = self.routed(x)
        sh = F.linear(F.silu(F.linear(x, self.sh_gate)) * F.linear(x, self.sh_up), self.sh_down)
        if hasattr(self, "shx_down"):  # add_sh_extra: the shared expert's extra columns
            sh = sh + F.linear(F.silu(F.linear(x, self.shx_gate)) * F.linear(x, self.shx_up), self.shx_down)
        return out + sh * torch.sigmoid(F.linear(x, self.sh_expert_gate))

    def routed(self, x):
        probs = torch.softmax(F.linear(x, self.router).float(), -1)
        w, idx = probs.topk(TOPK, -1)
        w = (w / w.sum(-1, keepdim=True)).to(x.dtype)
        out = torch.zeros_like(x)
        a4 = getattr(self, "fake_nvfp4_act", False)
        xa = fake_nvfp4(x, per_row_global=True) if a4 else x
        # Trainable experts: unbind once (one stacked gradient), never index the Parameter per expert (each index's
        # backward materializes a full [E, ...] zero gradient: 20 s/step instead of < 1 s).
        gus = self.gate_up.unbind(0) if self.gate_up.requires_grad else self.gate_up
        dns = self.down.unbind(0) if self.down.requires_grad else self.down
        for e in idx.unique().tolist():
            r, slot = (idx == e).nonzero(as_tuple=True)
            gu = F.linear(xa[r], gus[e].to(x.dtype))
            g, u = gu.chunk(2, -1)
            h = F.silu(g) * u
            y = F.linear(fake_nvfp4(h, per_row_global=True) if a4 else h, dns[e].to(x.dtype))
            out = out.index_add(0, r, y * w[r, slot, None])
        return out

    def forward(self, hc, tok_next, rows=None, e_in=None, rpos=None):
        """hc [T, 10240] target hc at positions 0..T-1, tok_next [T] token p+1 (or e_in [T, H] input embeddings)
        -> (hc_out, mixed) for `rows`."""
        T = hc.shape[0]
        rows = torch.arange(T, device=hc.device) if rows is None else rows
        y, (x0, xn) = self.attn_hc.mix(self.fuse(tok_next, hc, e_in))
        att = self.attention(y, rows, rpos=rpos)
        x = self.attn_hc.combine(att, (x0[rows], xn[rows]))
        y2, res2 = self.mlp_hc.mix(x)
        x = self.mlp_hc.combine(self.moe(y2), res2)
        return x, self.mixer.mix(x)[0]

    def logits(self, mixed):
        """Over the hot map when one is loaded (FR-Spec: the draft can only propose those ids)."""
        W = self.lm_head[self.hot] if self.hot.numel() else self.lm_head
        return F.linear(mixed, W.to(mixed.dtype))

    def propose(self, mixed):
        a = self.logits(mixed).argmax(-1)
        return self.hot[a] if self.hot.numel() else a


MAP = {
    "mtp.pre_fc_norm_embedding.weight": "pre_fc_norm_embedding", "mtp.pre_fc_norm_hidden.weight": "pre_fc_norm_hidden",
    "mtp.fc_embedding.weight": "fc_embedding", "mtp.fc_hidden.weight": "fc_hidden",
    "mtp.layers.0.self_attn.q_proj.weight": "q_proj", "mtp.layers.0.self_attn.k_proj.weight": "k_proj",
    "mtp.layers.0.self_attn.v_proj.weight": "v_proj", "mtp.layers.0.self_attn.o_proj.weight": "o_proj",
    "mtp.layers.0.self_attn.q_norm.weight": "q_norm", "mtp.layers.0.self_attn.k_norm.weight": "k_norm",
    "mtp.layers.0.self_attn.indexer.index_qk_proj.weight": "index_qk",
    "mtp.layers.0.self_attn.indexer.q_layernorm.weight": "idx_q_norm",
    "mtp.layers.0.self_attn.indexer.k_layernorm.weight": "idx_k_norm",
    "mtp.layers.0.mlp.gate.weight": "router",
    "mtp.layers.0.mlp.shared_expert.gate_proj.weight": "sh_gate", "mtp.layers.0.mlp.shared_expert.up_proj.weight": "sh_up",
    "mtp.layers.0.mlp.shared_expert.down_proj.weight": "sh_down", "mtp.layers.0.mlp.shared_expert_gate.weight": "sh_expert_gate",
}
for _blk, _name in (("mtp.layers.0.attn_hyper_connection", "attn_hc"), ("mtp.layers.0.mlp_hyper_connection", "mlp_hc"),
                    ("mtp.hyper_connection_mixer", "mixer")):
    MAP[f"{_blk}.hc_norm.weight"] = f"{_name}.hc_norm"
    MAP[f"{_blk}.input_mix_weight_down.weight"] = f"{_name}.down"
    MAP[f"{_blk}.input_mix_weight_up.weight"] = f"{_name}.up"
    if _name != "mixer":
        MAP[f"{_blk}.block_inject_weight.weight"] = f"{_name}.inject"
EXPERTS = ("mtp.layers.0.mlp.experts.gate_up_proj", "mtp.layers.0.mlp.experts.down_proj")
SHARED = ("model.language_model.embed_tokens.weight", "lm_head.weight")


def read_tensors(ckpt_dir, names):
    """Read named tensors from safetensors shards WITHOUT mmap (plain seek + read; Windows commit limits)."""
    import struct
    ckpt_dir = Path(ckpt_dir)
    wmap = json.loads((ckpt_dir / "model.safetensors.index.json").read_text())["weight_map"]
    dt = {"BF16": torch.bfloat16, "F32": torch.float32, "F16": torch.float16, "I64": torch.int64, "I32": torch.int32}
    out = {}
    for shard in sorted({wmap[n] for n in names}):
        with open(ckpt_dir / shard, "rb") as f:
            (hl,) = struct.unpack("<Q", f.read(8))
            head = json.loads(f.read(hl))
            base = 8 + hl
            for n in names:
                if wmap[n] != shard:
                    continue
                info = head[n]
                a, b = info["data_offsets"]
                f.seek(base + a)
                buf = bytearray(f.read(b - a))
                out[n] = torch.frombuffer(buf, dtype=dt[info["dtype"]]).reshape(info["shape"])
    return out


def load_draft(ckpt_dir, mask_path=None, hot_ids=None, dtype=torch.float32, device="cpu", nvfp4=False):
    """ckpt_dir holds model.safetensors.index.json and the shards with mtp.*, embed_tokens and lm_head."""
    keep = None
    if mask_path:
        m = torch.load(mask_path, map_location="cpu")
        keep = torch.tensor([e for e in range(len(m["mtp"])) if not bool(m["mtp"][e])])
    got = read_tensors(ckpt_dir, list(MAP) + list(EXPERTS) + list(SHARED))
    gu, dn = got[EXPERTS[0]], got[EXPERTS[1]]
    router = got["mtp.layers.0.mlp.gate.weight"]
    if keep is not None:
        gu, dn, router = gu[keep].contiguous(), dn[keep].contiguous(), router[keep].contiguous()
        got["mtp.layers.0.mlp.gate.weight"] = router
    d = Draft(router.shape[0])
    params = dict(d.named_parameters())
    for n, p in MAP.items():
        t = got[n]
        assert params[p].shape == t.shape, (n, tuple(t.shape), tuple(params[p].shape))
        params[p].data = t.to(dtype)
    assert gu.shape[1:] == (2 * E_INTER, H) and dn.shape[1:] == (H, E_INTER), (gu.shape, dn.shape)
    d.gate_up, d.down = gu.to(torch.bfloat16), dn.to(torch.bfloat16)
    if nvfp4:  # serving's view of the draft MoE: NVFP4 weights (per expert) and activations (per token)
        d.gate_up = torch.stack([fake_nvfp4(t.to(device)).cpu() for t in d.gate_up])
        d.down = torch.stack([fake_nvfp4(t.to(device)).cpu() for t in d.down])
        d.fake_nvfp4_act = True
    d.embed = got[SHARED[0]].to(torch.bfloat16)
    d.lm_head = got[SHARED[1]].to(torch.bfloat16)
    if hot_ids is not None:
        d.hot = torch.tensor(sorted(hot_ids), dtype=torch.long)
    return d.to(device)
