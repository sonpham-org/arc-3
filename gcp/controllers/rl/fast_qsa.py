"""Long-sequence training path for Flash-Next (qwen4_exp, transformers 5.18): same math, flat memory.

The reference code is written for short prompts. Two parts of it cannot train on our ~100k-token records:
1. the QSA indexer (Qwen4ExpTextQSAIndexer.forward) loops over every query position in Python (1-Oct trainer
   smoke: 41 s for one 12k-token forward), and
2. the text model builds a dense S x S attention mask for the full-attention layers (10 GB per GPU at 100k).
This module swaps in, for a single unpadded causal sequence with no cache (the training case):
- select_tokens: the same selection, vectorized over query chunks. For query q, the complete 4-token blocks among
  tokens 0..q are scored by sum over indexer heads of relu(q . pooled block key) / sqrt(d) (pooled = mean of the
  block's raw keys, k_layernorm, rope at the block start); the best 512 are kept, plus the tokens of q's own
  incomplete block (the tail). Queries below the 2048 budget see every earlier token.
- sparse_attention: attention over only those <= 2051 keys per query, gathered per chunk of queries under
  checkpoint, so memory stays flat with sequence length;
- no dense masks: masks are None and every patched layer assumes causal, unpadded, batch 1 (asserted).
- offload_checkpoint: decoder-layer checkpointing that parks each layer's input (S x 10240 BF16, 2 GB at 100k
  tokens) in pinned host RAM instead of GPU memory, and replays the layer in backward.
Anything with a cache, padding or a batch > 1 falls back to the reference code.
test_fast_qsa.py checks selection and outputs against the reference, on random weights.
"""
from __future__ import annotations

import math
import os
import types

import torch
import torch.nn.functional as F
from torch.utils.checkpoint import checkpoint

SEL_CHUNK = int(os.environ.get("ARC3_QSA_SEL_CHUNK", "1024"))     # queries per indexer-score chunk
ATT_CHUNK = int(os.environ.get("ARC3_QSA_ATT_CHUNK", "256"))      # queries per gathered-attention chunk
# diagnostics (off by default): count ties at the selection cut; or pick with the reference loop (slow, exact ref)
TIE_STATS = {"queries": 0, "tied_cut": 0, "zero_cut": 0} if os.environ.get("ARC3_QSA_TIE_STATS") == "1" else None
REF_SELECT = os.environ.get("ARC3_QSA_REF_SELECT") == "1"
_STATE = {"installed": False, "orig_attn": None, "orig_masks": None}


def _m():
    from transformers.models.qwen4_exp import modeling_qwen4_exp as m
    return m


# ------------------------------------------------------------------------------------------------ selection
@torch.no_grad()
def pooled_block_keys(indexer, raw_keys: torch.Tensor, cos_full: torch.Tensor, sin_full: torch.Tensor) -> torch.Tensor:
    """[n_blocks, d] keys of every complete block of the sequence, exactly as the reference builds them per query."""
    m = _m()
    r = indexer.compress_ratio
    nb = raw_keys.shape[0] // r
    groups = raw_keys[: nb * r].view(nb, r, raw_keys.shape[-1])
    pooled = groups.float().mean(dim=1).to(raw_keys.dtype)
    pooled = indexer.k_layernorm(pooled)
    starts = torch.arange(nb, device=raw_keys.device) * r
    return m.apply_rotary_pos_emb(pooled.unsqueeze(1), cos=cos_full[0].index_select(0, starts),
                                  sin=sin_full[0].index_select(0, starts)).squeeze(1)


@torch.no_grad()
def select_tokens(indexer, hidden_states: torch.Tensor, cos_full: torch.Tensor, sin_full: torch.Tensor,
                  chunk: int = 0) -> torch.Tensor:
    """[S, T] int32 key positions each query attends to (T = 512 blocks * 4 + 3 tail), -1 = empty slot."""
    m = _m()
    b, s, _ = hidden_states.shape
    assert b == 1, "fast QSA: batch 1 only"
    r, d, nh = indexer.compress_ratio, indexer.index_head_dim, indexer.index_n_heads
    qk = indexer.index_qk_proj(hidden_states)
    q, token_k = torch.split(qk, [nh * d, indexer.index_kv_heads * d], dim=-1)
    q = indexer.q_layernorm(q.reshape(b, s, nh, d))
    q = m.apply_rotary_pos_emb(q, cos=cos_full[:, -s:, :], sin=sin_full[:, -s:, :], unsqueeze_dim=2)[0]  # [S, nh, d]
    raw = token_k.reshape(s, d)
    keys = pooled_block_keys(indexer, raw, cos_full, sin_full).float()                                 # [nb, d]
    nb = keys.shape[0]
    k_sel = min(indexer.block_topk, nb)
    dev = hidden_states.device
    out = torch.full((s, k_sel * r + r - 1), -1, dtype=torch.int32, device=dev)
    ar_r = torch.arange(r, device=dev)
    ar_t = torch.arange(r - 1, device=dev)
    chunk = chunk or SEL_CHUNK
    for a in range(0, s, chunk):
        e = min(s, a + chunk)
        qpos = torch.arange(a, e, device=dev)
        n_complete = (qpos + 1) // r                                                    # complete blocks seen
        if k_sel > 0:
            sc = torch.relu((q[a:e].float().reshape(-1, d) @ keys.T).view(e - a, nh, nb)).sum(dim=1) / math.sqrt(d)
            sc = sc.masked_fill(torch.arange(nb, device=dev)[None, :] >= n_complete[:, None], float("-inf"))
            if TIE_STATS is not None and k_sel < nb:
                # a tie at the cut: the last kept block scores the same as the best dropped one (often both 0)
                v2 = sc.topk(k_sel + 1, dim=-1).values
                full = n_complete > k_sel
                TIE_STATS["queries"] += int(full.sum())
                TIE_STATS["tied_cut"] += int(((v2[:, -1] == v2[:, -2]) & full).sum())
                TIE_STATS["zero_cut"] += int(((v2[:, -2] == 0) & full).sum())
            val, blk = sc.topk(k_sel, dim=-1)
            tok = (blk[..., None] * r + ar_r).flatten(1)                                 # [C, k_sel * r]
            tok = torch.where(torch.isfinite(val).repeat_interleave(r, dim=1), tok, -1)
            out[a:e, : k_sel * r] = tok.to(torch.int32)
        tail = n_complete[:, None] * r + ar_t                                            # q's incomplete block
        out[a:e, k_sel * r:] = torch.where(tail <= qpos[:, None], tail, -1).to(torch.int32)
    return out


@torch.no_grad()
def ref_select_tokens(indexer, hidden_states: torch.Tensor, cos_full: torch.Tensor, sin_full: torch.Tensor) -> torch.Tensor:
    """Diagnostic: the reference indexer's own picks (its per-query loop on a dense causal mask), as [S, T] indices."""
    s = hidden_states.shape[1]
    causal = torch.ones(s, s, dtype=torch.bool, device=hidden_states.device).tril()[None, None]
    sel = indexer(hidden_states, (cos_full, sin_full), causal, None)[0, 0]          # [S, S] bool
    t = min(s, indexer.token_budget + indexer.compress_ratio - 1)
    counts = sel.sum(dim=1)
    order = torch.argsort((~sel).to(torch.int8), dim=1, stable=True)[:, :t]        # picked positions first
    return torch.where(torch.arange(t, device=sel.device)[None, :] < counts[:, None], order, -1).to(torch.int32)


# ------------------------------------------------------------------------------------------------ attention
def _attend_chunk(qc: torch.Tensor, ks: torch.Tensor, vs: torch.Tensor, ic: torch.Tensor, scale: float) -> torch.Tensor:
    """qc [C, H, D]; ks/vs [S, KVH, D] float32; ic [C, T] -> [C, H, D]. Scores, softmax and P.V in float32.
    The gather is index_select: its backward is an atomic index_add_ into the float32 ks/vs gradient. Advanced
    indexing (ks[ii]) backs off to a sort-based kernel that took 52% of a 12k-token training step (2-Oct profile)."""
    c, h, dd = qc.shape
    kvh = ks.shape[1]
    t = ic.shape[1]
    valid = ic >= 0
    flat = ic.clamp_min(0).long().reshape(-1)
    kc = ks.index_select(0, flat).view(c, t, kvh, dd)                                     # [C, T, KVH, D]
    vc = vs.index_select(0, flat).view(c, t, kvh, dd)
    qg = qc.view(c, kvh, h // kvh, dd).float()
    sc = torch.einsum("cvgd,ctvd->cvgt", qg, kc) * scale
    sc = sc.masked_fill(~valid[:, None, None, :], float("-inf"))
    p = torch.softmax(sc, dim=-1)
    o = torch.einsum("cvgt,ctvd->cvgd", p, vc)
    return o.reshape(c, h, dd).to(qc.dtype)


def sparse_attention(q: torch.Tensor, k: torch.Tensor, v: torch.Tensor, idx: torch.Tensor, scale: float,
                     chunk: int = 0) -> torch.Tensor:
    """q [1, H, S, D], k/v [1, KVH, S, D] (rope applied), idx [S, T] -> [1, S, H, D]."""
    qs = q[0].transpose(0, 1)
    ks, vs = k[0].transpose(0, 1).float(), v[0].transpose(0, 1).float()      # gradients accumulate in float32
    chunk = chunk or ATT_CHUNK
    grad = torch.is_grad_enabled() and (qs.requires_grad or ks.requires_grad or vs.requires_grad)
    outs = []
    for a in range(0, qs.shape[0], chunk):
        e = min(qs.shape[0], a + chunk)
        if grad:
            outs.append(checkpoint(_attend_chunk, qs[a:e], ks, vs, idx[a:e], scale, use_reentrant=False))
        else:
            outs.append(_attend_chunk(qs[a:e], ks, vs, idx[a:e], scale))
    return torch.cat(outs, dim=0).unsqueeze(0)


def attention_forward(self, hidden_states, position_embeddings, attention_mask=None, past_key_values=None, **kwargs):
    """Qwen4ExpTextAttention.forward with the fast indexer + gathered attention (training case only)."""
    if past_key_values is not None or attention_mask is not None or hidden_states.shape[0] != 1:
        if attention_mask is None:
            raise RuntimeError("fast QSA: reference path needs the dense mask; uninstall() before cached generation")
        return _STATE["orig_attn"](self, hidden_states, position_embeddings, attention_mask, past_key_values, **kwargs)
    m = _m()
    cos_full, sin_full = position_embeddings
    s = hidden_states.shape[1]
    if REF_SELECT:
        idx = ref_select_tokens(self.indexer, hidden_states, cos_full, sin_full)
    else:
        idx = select_tokens(self.indexer, hidden_states, cos_full, sin_full)
    cos, sin = cos_full[:, -s:, :], sin_full[:, -s:, :]
    input_shape = hidden_states.shape[:-1]
    hidden_shape = (*input_shape, -1, self.head_dim)
    query_states, gate = torch.chunk(self.q_proj(hidden_states).view(*input_shape, -1, self.head_dim * 2), 2, dim=-1)
    gate = gate.reshape(*input_shape, -1)
    query_states = self.q_norm(query_states.view(hidden_shape)).transpose(1, 2)
    key_states = self.k_norm(self.k_proj(hidden_states).view(hidden_shape)).transpose(1, 2)
    value_states = self.v_proj(hidden_states).view(hidden_shape).transpose(1, 2)
    query_states, key_states = m.apply_rotary_pos_emb(query_states, key_states, cos, sin)
    attn_output = sparse_attention(query_states, key_states, value_states, idx, self.scaling)
    attn_output = attn_output.reshape(*input_shape, -1).contiguous()
    attn_output = attn_output * torch.sigmoid(gate)
    return self.o_proj(attn_output), None


# ------------------------------------------------------------------------------------------------ offload
class _OffloadedLayer(torch.autograd.Function):
    """Run a decoder layer without keeping anything on the GPU; its input waits in pinned host RAM for backward."""

    @staticmethod
    def forward(ctx, x, fn, buf_key):
        ctx.fn = fn
        ctx.dev = x.device
        ctx.shape = x.shape
        buf = _pinned(buf_key, x)
        buf.copy_(x.reshape(-1), non_blocking=True)
        ctx.buf = buf
        with torch.no_grad():
            return fn(x)

    @staticmethod
    def backward(ctx, gy):
        x = ctx.buf.to(ctx.dev, non_blocking=True).view(ctx.shape).detach().requires_grad_(True)
        ctx.buf = None
        with torch.enable_grad():
            y = ctx.fn(x)
        torch.autograd.backward(y, gy)
        return x.grad, None, None


_PINNED: dict = {}


def _pinned(key, x: torch.Tensor) -> torch.Tensor:
    n = x.numel()
    buf = _PINNED.get(key)
    if buf is None or buf.numel() < n or buf.dtype != x.dtype:
        buf = torch.empty(max(n, int(os.environ.get("ARC3_OFFLOAD_MIN_ELEMS", "0"))), dtype=x.dtype, pin_memory=True)
        _PINNED[key] = buf
    return buf[:n]


def offload_checkpoint_for(layer_idx: int):
    def run(fn, x, *rest):
        if rest:
            raise RuntimeError("offload checkpoint: decoder layer takes the hidden states as its only positional arg")
        if not (torch.is_grad_enabled() and x.requires_grad):
            with torch.no_grad():
                return fn(x)
        return _OffloadedLayer.apply(x, fn, layer_idx)
    return run


# ------------------------------------------------------------------------------------------------ install
def install(model=None, offload: bool = False) -> dict:
    """Patch the qwen4_exp classes (all instances); with offload, decoder layers checkpoint into host RAM."""
    m = _m()
    if not _STATE["installed"]:
        _STATE["orig_attn"] = m.Qwen4ExpTextAttention.forward
        _STATE["orig_masks"] = (m.create_causal_mask, m.create_recurrent_attention_mask)
        m.Qwen4ExpTextAttention.forward = attention_forward

        def no_mask(**kw):
            am = kw.get("attention_mask")
            if am is not None and not bool(torch.as_tensor(am).bool().all()):
                raise RuntimeError("fast QSA: padded batches are not supported")
            if kw.get("past_key_values") is not None:
                raise RuntimeError("fast QSA: no cache in training; uninstall() before cached generation")
            return None

        m.create_causal_mask = no_mask
        m.create_recurrent_attention_mask = no_mask
        _STATE["installed"] = True
    n_off = n_hooked = 0
    if model is not None:
        for name, mod in model.named_modules():
            # a model placed with a device_map has accelerate hooks that call the forward bound at load time
            # (module._old_forward), not the class attribute: patch those instances too (2-Oct ladder hit this)
            if isinstance(mod, m.Qwen4ExpTextAttention) and "_old_forward" in mod.__dict__:
                if "_fast_qsa_orig" not in mod.__dict__:
                    mod._fast_qsa_orig = mod._old_forward
                mod._old_forward = types.MethodType(attention_forward, mod)
                n_hooked += 1
            if offload and isinstance(mod, m.Qwen4ExpTextDecoderLayer):
                mod._gradient_checkpointing_func = offload_checkpoint_for(n_off)
                mod.gradient_checkpointing = True
                n_off += 1
    return {"fast_qsa": True, "hooked_attention_layers": n_hooked, "offloaded_layers": n_off}


def uninstall(model=None) -> None:
    m = _m()
    if model is not None:
        for mod in model.modules():
            if "_fast_qsa_orig" in mod.__dict__:
                mod._old_forward = mod.__dict__.pop("_fast_qsa_orig")
    if _STATE["installed"]:
        m.Qwen4ExpTextAttention.forward = _STATE["orig_attn"]
        m.create_causal_mask, m.create_recurrent_attention_mask = _STATE["orig_masks"]
        _STATE["installed"] = False
