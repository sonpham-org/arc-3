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

import json
import math
import os
import types

import torch
import torch.nn.functional as F
from torch.utils.checkpoint import checkpoint

SEL_CHUNK = int(os.environ.get("ARC3_QSA_SEL_CHUNK", "1024"))     # queries per indexer-score chunk
ATT_CHUNK = int(os.environ.get("ARC3_QSA_ATT_CHUNK", "256"))      # queries per gathered-attention chunk
# kernel (default, 4-Oct): qsa_kernel.py, fused Triton forward + backward over the same picks; 115k tokens: 0.79 s vs
# 13.5 s fwd+bwd, full-model check on a 108k record: mean |dlogp| 0.039 vs gather, step 2.4x faster.
# gather: the 2-Oct gathered attention (float32, index_select / index_add): one indexed-attention layer at 115k tokens
# took 19.8 s fwd+bwd, 12 of them ~73% of a step. flex: FlexAttention (exact <= 32k only, see attention_forward).
ATTN_IMPL = os.environ.get("ARC3_QSA_ATTN", "kernel")
FLEX_TILE = 128                                                    # BlockMask tile (tokens)
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
                  chunk: int = 0, blocks_out: torch.Tensor | None = None) -> torch.Tensor:
    """[S, T] int32 key positions each query attends to (T = 512 blocks * 4 + 3 tail), -1 = empty slot.
    blocks_out: a [S, ceil(S / r)] bool tensor that also receives each query's picked complete blocks (the flex path
    reads the picks from it; its token list is then not built)."""
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
    want_tokens = blocks_out is None
    out = torch.full((s, k_sel * r + r - 1) if want_tokens else (1, 1), -1, dtype=torch.int32, device=dev)
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
            if not want_tokens:
                ok = torch.isfinite(val)
                blocks_out[a:e].scatter_(1, torch.where(ok, blk, 0), ok)
                # the scatter wrote False for invalid slots into block 0: put block 0 back where it was picked
                hit0 = ((blk == 0) & ok).any(dim=1)
                blocks_out[a:e, 0] |= hit0
                continue
            tok = (blk[..., None] * r + ar_r).flatten(1)                                 # [C, k_sel * r]
            tok = torch.where(torch.isfinite(val).repeat_interleave(r, dim=1), tok, -1)
            out[a:e, : k_sel * r] = tok.to(torch.int32)
        if want_tokens:
            tail = n_complete[:, None] * r + ar_t                                        # q's incomplete block
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


# Selection cache (4-Oct): under the offloaded checkpoint a layer runs twice per step, a no-grad forward and a replay
# with grad in backward, on the same input, so the replay reuses the forward's picks (QSA selection is ~1 s per
# indexed-attention layer at 115k tokens). Kept compact: block ids as int16/int32 [S, k_sel] (~120 MB per layer);
# the tail is a function of the position. ARC3_QSA_SEL_VERIFY=1 recomputes in the replay and requires equality.
_SEL: dict = {"mode": None, "store": {}}
SEL_CACHE = os.environ.get("ARC3_QSA_SEL_CACHE", "1") != "0"
SEL_VERIFY = os.environ.get("ARC3_QSA_SEL_VERIFY") == "1"


def _sel_compact(idx: torch.Tensor, r: int) -> torch.Tensor:
    blocks = idx[:, : idx.shape[1] - (r - 1): r]                 # first token of every picked block (-1 = empty)
    blocks = torch.div(blocks, r, rounding_mode="floor")         # -1 stays -1
    return blocks.to(torch.int16) if int(blocks.max()) < 32767 else blocks


def _sel_expand(blocks: torch.Tensor, s: int, r: int, dev) -> torch.Tensor:
    """The [S, k_sel * r + r - 1] token list select_tokens builds, from the compact block ids."""
    b = blocks.to(torch.int64)
    ar_r, ar_t = torch.arange(r, device=dev), torch.arange(r - 1, device=dev)
    tok = torch.where(b[..., None] >= 0, b[..., None] * r + ar_r, -1).flatten(1)
    qpos = torch.arange(s, device=dev)
    tail = ((qpos + 1) // r)[:, None] * r + ar_t
    tail = torch.where(tail <= qpos[:, None], tail, -1)
    return torch.cat([tok, tail], dim=1).to(torch.int32)


_FLEX: dict = {}


def _flex_fn():
    """torch.compile'd flex_attention (one compiled function, shapes marked dynamic: record lengths vary)."""
    if "fn" not in _FLEX:
        from torch.nn.attention.flex_attention import flex_attention
        _FLEX["fn"] = torch.compile(flex_attention, dynamic=True)
    return _FLEX["fn"]


def flex_block_mask(picks: torch.Tensor, s: int, r: int):
    """BlockMask for the QSA picks: query q sees key k <= q when k's r-token block is one q picked, or k is in q's own
    incomplete block (the tail). picks: [S, >= ceil(S / r)] bool (select_tokens(blocks_out=...)). Tiles of FLEX_TILE
    tokens that no query of a query tile touches are skipped; the others are masked per element by mask_mod."""
    from torch.nn.attention.flex_attention import BlockMask
    t = FLEX_TILE
    bpt = t // r                                                   # blocks per tile
    nt = -(-s // t)
    dev = picks.device
    pad = torch.zeros(nt * t, nt * bpt, dtype=torch.bool, device=dev)
    pad[:s, : picks.shape[1]] = picks[:, : nt * bpt]
    tiles = pad.view(nt, t, nt, bpt).any(dim=3).any(dim=1)        # [query tile, key tile]
    tiles |= torch.eye(nt, dtype=torch.bool, device=dev)          # own tile: the tail (and causal diagonal)
    tiles &= torch.ones(nt, nt, dtype=torch.bool, device=dev).tril()
    num = tiles.sum(dim=1).to(torch.int32)
    idx = torch.argsort((~tiles).to(torch.int8), dim=1, stable=True).to(torch.int32)   # picked tiles first, ascending

    def mask_mod(b, h, q_idx, kv_idx):
        blk = kv_idx // r
        tail = blk >= (q_idx + 1) // r                             # q's incomplete block (with kv <= q below)
        return (kv_idx <= q_idx) & (tail | pad[q_idx, blk])

    return BlockMask.from_kv_blocks(num[None, None], idx[None, None], BLOCK_SIZE=t, mask_mod=mask_mod,
                                    seq_lengths=(s, s)), {"tiles_kept": int(num.sum()), "tiles_causal": nt * (nt + 1) // 2}


def flex_sparse_attention(q: torch.Tensor, k: torch.Tensor, v: torch.Tensor, picks: torch.Tensor, r: int,
                          scale: float) -> torch.Tensor:
    """q [1, H, S, D], k/v [1, KVH, S, D] (rope applied) -> [1, S, H, D]: attention over exactly the QSA picks (same
    keys as sparse_attention), as one fused kernel (BF16 inputs, float32 accumulation, no gathered copies)."""
    s = q.shape[2]
    bm, _info = flex_block_mask(picks, s, r)
    _FLEX["last"] = _info
    opts = json.loads(os.environ["ARC3_FLEX_OPTS"]) if os.environ.get("ARC3_FLEX_OPTS") else None   # kernel tiles
    o = _flex_fn()(q, k, v, block_mask=bm, scale=scale, enable_gqa=k.shape[1] != q.shape[1], kernel_options=opts)
    return o.transpose(1, 2)


def attention_forward(self, hidden_states, position_embeddings, attention_mask=None, past_key_values=None, **kwargs):
    """Qwen4ExpTextAttention.forward with the fast indexer + gathered attention (training case only)."""
    if past_key_values is not None or attention_mask is not None or hidden_states.shape[0] != 1:
        if attention_mask is None:
            raise RuntimeError("fast QSA: reference path needs the dense mask; uninstall() before cached generation")
        return _STATE["orig_attn"](self, hidden_states, position_embeddings, attention_mask, past_key_values, **kwargs)
    m = _m()
    cos_full, sin_full = position_embeddings
    s = hidden_states.shape[1]
    picks = idx = None
    # flex only below 2^31 pick-table entries: its generated kernels index the [S, S/r] table with int32 (4-Oct bench:
    # exact at 8k and 32k, cos 0.98 at 115k), and its dense-equivalent tiles make it barely faster than gather there
    if ATTN_IMPL == "flex" and not REF_SELECT and s * -(-s // self.indexer.compress_ratio) < 2**31:
        r = self.indexer.compress_ratio
        picks = torch.zeros(s, -(-s // r), dtype=torch.bool, device=hidden_states.device)
        select_tokens(self.indexer, hidden_states, cos_full, sin_full, blocks_out=picks)
    elif REF_SELECT:
        idx = ref_select_tokens(self.indexer, hidden_states, cos_full, sin_full)
    elif _SEL["mode"] == "load" and id(self) in _SEL["store"]:
        idx = _sel_expand(_SEL["store"].pop(id(self)), s, self.indexer.compress_ratio, hidden_states.device)
        if SEL_VERIFY:
            again = select_tokens(self.indexer, hidden_states, cos_full, sin_full)
            if not torch.equal(again, idx):
                raise RuntimeError("fast QSA: the replay's picks differ from the forward's (selection cache)")
    else:
        idx = select_tokens(self.indexer, hidden_states, cos_full, sin_full)
        if _SEL["mode"] == "save":
            _SEL["store"][id(self)] = _sel_compact(idx, self.indexer.compress_ratio)
    cos, sin = cos_full[:, -s:, :], sin_full[:, -s:, :]
    input_shape = hidden_states.shape[:-1]
    hidden_shape = (*input_shape, -1, self.head_dim)
    query_states, gate = torch.chunk(self.q_proj(hidden_states).view(*input_shape, -1, self.head_dim * 2), 2, dim=-1)
    gate = gate.reshape(*input_shape, -1)
    query_states = self.q_norm(query_states.view(hidden_shape)).transpose(1, 2)
    key_states = self.k_norm(self.k_proj(hidden_states).view(hidden_shape)).transpose(1, 2)
    value_states = self.v_proj(hidden_states).view(hidden_shape).transpose(1, 2)
    query_states, key_states = m.apply_rotary_pos_emb(query_states, key_states, cos, sin)
    if picks is not None:
        attn_output = flex_sparse_attention(query_states, key_states, value_states, picks,
                                            self.indexer.compress_ratio, self.scaling)
    elif ATTN_IMPL == "kernel":
        import qsa_kernel
        attn_output = qsa_kernel.sparse_attention(query_states, key_states, value_states, idx, self.scaling)
    else:
        attn_output = sparse_attention(query_states, key_states, value_states, idx, self.scaling)
    attn_output = attn_output.reshape(*input_shape, -1).contiguous()
    attn_output = attn_output * torch.sigmoid(gate)
    return self.o_proj(attn_output), None


# ------------------------------------------------------------------------------------------------ chunked layer
LAYER_CHUNK = int(os.environ.get("ARC3_LAYER_TOKEN_CHUNK", "16384"))    # tokens per chunk of the per-token work
# Hyper-connection mix (Qwen4ExpTextGatedResidual) as ONE compiled function shared by every layer (4-Oct: its chain
# of float32 elementwise ops on [S, 10240] is ~0.25 s fwd+bwd per mix at 115k; compiling each module would compile
# 96 times). Same ops and dtypes as the module (outputs within ~0.5%); on by default, ARC3_HC_COMPILE=0 runs the module.
HC_COMPILE = os.environ.get("ARC3_HC_COMPILE", "1") == "1"
_HC: dict = {}


def _hc_mix_eager(x, norm_w, down_w, up_w, inj_w, eps: float, hc: int, hidden: int):
    g = x.float().reshape(*x.shape[:-1], hc, hidden)
    normed = (g * torch.rsqrt(g.pow(2).mean(-1, keepdim=True) + eps)).flatten(-2)
    normed = (normed * (1.0 + norm_w.float())).to(x.dtype)
    w = torch.sigmoid(F.linear(F.silu(F.linear(normed, down_w) / hc), up_w)).unflatten(-1, (hc, hidden))
    mixed = (w * normed.unflatten(-1, (hc, hidden))).mean(dim=-2)
    inj = 2 * torch.sigmoid(F.linear(normed, inj_w) / hc)
    return mixed, inj


def hc_mix(mod, x):
    """(mixed input, injection weights) of a Qwen4ExpTextGatedResidual with block injection, as its forward gives."""
    if "fn" not in _HC:
        _HC["fn"] = torch.compile(_hc_mix_eager, dynamic=True)
    return _HC["fn"](x, mod.hc_norm.weight, mod.input_mix_weight_down.weight, mod.input_mix_weight_up.weight,
                     mod.block_inject_weight.weight, float(mod.hc_norm.eps), int(mod.hc_count), int(mod.hidden_size))


def _tokenwise(fn, *tensors, chunk: int = 0):
    """fn(*tensors) for per-token work, in chunks along the sequence (dim 1), each under checkpoint when a gradient
    is needed: only the chunk's own intermediates are alive at a time. Every tensor must have the sequence on dim 1."""
    s = tensors[0].shape[1]
    chunk = chunk or LAYER_CHUNK
    if s <= chunk:
        return fn(*tensors)
    grad = torch.is_grad_enabled() and any(t.requires_grad for t in tensors)
    outs = []
    for a in range(0, s, chunk):
        part = [t[:, a:a + chunk] for t in tensors]
        outs.append(checkpoint(fn, *part, use_reentrant=False) if grad else fn(*part))
    if isinstance(outs[0], tuple):
        return tuple(torch.cat([o[i] for o in outs], dim=1) for i in range(len(outs[0])))
    return torch.cat(outs, dim=1)


def decoder_forward(self, hidden_states, position_embeddings, attention_mask=None, conv_mask=None,
                    past_key_values=None, ple_input_ids=None, **kwargs):
    """Qwen4ExpTextDecoderLayer.forward with its per-token parts in token chunks (same math, same order).

    At ~110k tokens most of a layer's backward memory is per-token work around the attention core: the two
    hyper-connection mixes ([S, 10240] float32 norms, sigmoid gates), the injections, and the MoE block (2-Oct
    ladder: 109k and 118k ran out of memory). Only the attention / linear-attention core needs the whole sequence
    at once. With a cache (generation), the stock forward runs."""
    if past_key_values is not None or hidden_states.shape[0] != 1:
        return _STATE["orig_layer"](self, hidden_states, position_embeddings, attention_mask=attention_mask,
                                    conv_mask=conv_mask, past_key_values=past_key_values,
                                    ple_input_ids=ple_input_ids, **kwargs)
    if self.ple is not None:
        hidden_states = hidden_states + self.ple(hidden_states, ple_input_ids, past_key_values, conv_mask=conv_mask)

    def attn_mix(x):
        if HC_COMPILE:
            return hc_mix(self.attn_hyper_connection, x)
        mixed, _, weights = self.attn_hyper_connection(x)
        return mixed, weights

    mixed, inj_w = _tokenwise(attn_mix, hidden_states)
    if self.layer_type == "linear_attention":
        core = self.linear_attn(mixed, cache_params=past_key_values, attention_mask=conv_mask, **kwargs)
    else:
        core, _ = self.self_attn(mixed, position_embeddings, attention_mask=attention_mask,
                                 past_key_values=past_key_values, **kwargs)
    del mixed

    def inject(x, c, w):
        return x + (c.unsqueeze(-2) * w.unsqueeze(-1)).flatten(-2)

    hidden_states = _tokenwise(inject, hidden_states, core, inj_w)
    del core, inj_w

    def mlp_mix(x):
        if HC_COMPILE:
            return hc_mix(self.mlp_hyper_connection, x)
        mixed2, _, weights = self.mlp_hyper_connection(x)
        return mixed2, weights

    mixed, inj_w = _tokenwise(mlp_mix, hidden_states)
    # the MoE block runs on the whole sequence: packed experts are unpacked once per call and chunk their own tokens
    # (nvfp4_experts.TOKEN_CHUNK); chunking here would unpack them once per chunk
    out = self.mlp(mixed)
    del mixed
    return _tokenwise(inject, hidden_states, out, inj_w)


# ------------------------------------------------------------------------------------------------ offload
COPY_STREAM = os.environ.get("ARC3_OFFLOAD_STREAM", "1") != "0"
_COPY: dict = {"streams": {}, "ahead": {}}     # side stream per GPU; layer key -> (prefetched input, ready event)


def _copy_stream(dev) -> "torch.cuda.Stream":
    """The side stream of this GPU (a model split over GPUs has layers on several: one stream each)."""
    d = torch.device(dev)
    i = d.index if d.index is not None else torch.cuda.current_device()
    if i not in _COPY["streams"]:
        _COPY["streams"][i] = torch.cuda.Stream(device=i)
    return _COPY["streams"][i]


def _fetch(key):
    """Start copying layer `key`'s parked input back to ITS GPU on that GPU's side stream (backward runs the layers in
    reverse, so the next one's input arrives while this one computes)."""
    buf = _PINNED.get(key)
    if buf is None or key in _COPY["ahead"] or key not in _SHAPES:
        return
    shape, dev = _SHAPES[key]
    st = _copy_stream(dev)
    with torch.cuda.device(dev), torch.cuda.stream(st):
        x = buf[: math.prod(shape)].to(dev, non_blocking=True).view(shape)
        ev = torch.cuda.Event()
        ev.record(st)
    _COPY["ahead"][key] = (x, ev)


_SHAPES: dict = {}                               # layer key -> (input shape, its GPU)


class _OffloadedLayer(torch.autograd.Function):
    """Run a decoder layer without keeping anything on the GPU; its input waits in pinned host RAM for backward.
    4-Oct: the copies run on a side stream (the forward's GPU->host copy overlaps the layer's compute; in backward the
    previous layer's input is fetched while this one runs), and the forward / replay set the QSA selection cache's
    mode (the replay reuses the forward's picks)."""

    @staticmethod
    def forward(ctx, x, fn, buf_key):
        ctx.fn, ctx.dev, ctx.shape, ctx.key = fn, x.device, x.shape, buf_key
        buf = _pinned(buf_key, x)
        _SHAPES[buf_key] = (tuple(x.shape), x.device)
        if COPY_STREAM and x.is_cuda:
            st = _copy_stream(x.device)
            st.wait_stream(torch.cuda.current_stream(x.device))       # x is ready
            with torch.cuda.device(x.device), torch.cuda.stream(st):
                buf.copy_(x.reshape(-1), non_blocking=True)
            x.record_stream(st)                                        # x's memory is not reused before the copy
        else:
            buf.copy_(x.reshape(-1), non_blocking=True)
        ctx.buf = buf
        prev = _SEL["mode"]
        _SEL["mode"] = "save" if SEL_CACHE else None
        try:
            with torch.no_grad():
                return fn(x)
        finally:
            _SEL["mode"] = prev

    @staticmethod
    def backward(ctx, gy):
        got = _COPY["ahead"].pop(ctx.key, None)
        if got is not None:
            torch.cuda.current_stream(ctx.dev).wait_event(got[1])
            x = got[0]
            x.record_stream(torch.cuda.current_stream(ctx.dev))
        else:
            if COPY_STREAM and ctx.dev.type == "cuda":
                torch.cuda.current_stream(ctx.dev).wait_stream(_copy_stream(ctx.dev))   # the forward copy is done
            x = ctx.buf.to(ctx.dev, non_blocking=True).view(ctx.shape)
        x = x.detach().requires_grad_(True)
        ctx.buf = None
        if COPY_STREAM and ctx.dev.type == "cuda" and isinstance(ctx.key, int):
            _fetch(ctx.key - 1)                                        # the layer before this one is next
        prev = _SEL["mode"]
        _SEL["mode"] = "load" if SEL_CACHE else None
        try:
            with torch.enable_grad():
                y = ctx.fn(x)
        finally:
            _SEL["mode"] = prev
        torch.autograd.backward(y, gy)
        return x.grad, None, None


_PINNED: dict = {}


# 4-Oct: pin_memory=True goes through the caching host allocator, which rounds each block up to a power of two: the 48
# offload buffers of a 121k-token record (2.5 GB each) took 4 GB each, ~192 GB per training process (baseline run:
# 308 GB host RAM for one copy). ARC3_PIN_EXACT=1 page-locks ordinary memory of the exact size (cudaHostRegister).
PIN_EXACT = os.environ.get("ARC3_PIN_EXACT", "1") != "0"


def _pin_alloc(n: int, dtype) -> torch.Tensor:
    if PIN_EXACT and torch.cuda.is_available():
        buf = torch.empty(n, dtype=dtype)
        rt = torch.cuda.cudart()
        rc = rt.cudaHostRegister(buf.data_ptr(), buf.numel() * buf.element_size(), 0)
        if int(rc) == 0:
            return buf
    return torch.empty(n, dtype=dtype, pin_memory=True)


def _pinned(key, x: torch.Tensor) -> torch.Tensor:
    n = x.numel()
    buf = _PINNED.get(key)
    if buf is None or buf.numel() < n or buf.dtype != x.dtype:
        if buf is not None and PIN_EXACT:
            try:
                torch.cuda.cudart().cudaHostUnregister(buf.data_ptr())   # a smaller exact buffer being replaced
            except Exception:                                           # noqa: BLE001 - it was a pin_memory block
                pass
        buf = _pin_alloc(max(n, int(os.environ.get("ARC3_OFFLOAD_MIN_ELEMS", "0"))), x.dtype)
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
        _STATE["orig_layer"] = m.Qwen4ExpTextDecoderLayer.forward
        _STATE["orig_masks"] = (m.create_causal_mask, m.create_recurrent_attention_mask)
        m.Qwen4ExpTextAttention.forward = attention_forward
        m.Qwen4ExpTextDecoderLayer.forward = decoder_forward

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
            if isinstance(mod, m.Qwen4ExpTextDecoderLayer) and "_old_forward" in mod.__dict__:
                if "_fast_qsa_orig" not in mod.__dict__:
                    mod._fast_qsa_orig = mod._old_forward
                mod._old_forward = types.MethodType(decoder_forward, mod)
                n_hooked += 1
            if offload and isinstance(mod, m.Qwen4ExpTextDecoderLayer):
                mod._gradient_checkpointing_func = offload_checkpoint_for(n_off)
                mod.gradient_checkpointing = True
                n_off += 1
    return {"fast_qsa": True, "hooked_layers": n_hooked, "offloaded_layers": n_off}


def uninstall(model=None) -> None:
    m = _m()
    if model is not None:
        for mod in model.modules():
            if "_fast_qsa_orig" in mod.__dict__:
                mod._old_forward = mod.__dict__.pop("_fast_qsa_orig")
    if _STATE["installed"]:
        m.Qwen4ExpTextAttention.forward = _STATE["orig_attn"]
        m.Qwen4ExpTextDecoderLayer.forward = _STATE["orig_layer"]
        m.create_causal_mask, m.create_recurrent_attention_mask = _STATE["orig_masks"]
        _STATE["installed"] = False
