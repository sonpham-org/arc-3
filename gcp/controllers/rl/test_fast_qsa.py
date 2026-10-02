"""fast_qsa.py against the transformers 5.18 reference, on random weights (GPU box; the fla kernels need CUDA).

1. selection: the fast indexer picks the same keys per query as the reference loop (tiny model past its budget,
   and one real-size attention layer at 4,096 tokens, past the real 2,048 budget);
2. attention layer: same output and same gradients (input and LoRA-style weight) as the reference;
3. whole tiny model: same log-probs with the patch installed;
4. offloaded checkpointing: same LoRA gradients as plain checkpointing, and the input really leaves the GPU;
5. mutation: a selection that drops one picked key changes the layer output (the check can fail).

Run: python test_fast_qsa.py --hf /opt/rl/hf
"""
from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fast_qsa as fq  # noqa: E402
import test_trainer_tiny as tt  # noqa: E402

FAILS = []
DEV = torch.device("cuda")


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""), flush=True)
    if not ok:
        FAILS.append(name)


def causal(s: int) -> torch.Tensor:
    return torch.ones(s, s, dtype=torch.bool, device=DEV).tril()[None, None]


def ref_selection(indexer, h, cos, sin) -> torch.Tensor:
    """[S, S] bool: the reference indexer's picks (loop over queries)."""
    return indexer(h, (cos, sin), causal(h.shape[1]), None)[0, 0]


def fast_selection(indexer, h, cos, sin) -> torch.Tensor:
    idx = fq.select_tokens(indexer, h, cos, sin, chunk=97).long()          # odd chunk: exercise the chunk edges
    s = h.shape[1]
    mask = torch.zeros(s, s + 1, dtype=torch.bool, device=DEV)
    mask.scatter_(1, torch.where(idx >= 0, idx, s), True)
    return mask[:, :s]


def rope(model_or_text, h, s):
    text = model_or_text
    pos = torch.arange(s, device=DEV).view(1, 1, -1).expand(3, 1, -1)
    return text.rotary_emb(h, pos)


def selection_report(name, indexer, h, cos, sin, min_rows=0.995):
    a = ref_selection(indexer, h, cos, sin)
    b = fast_selection(indexer, h, cos, sin)
    rows_same = (a == b).all(dim=1).float().mean().item()
    keys_same = 1 - ((a != b).sum().item() / max(1, a.sum().item()))
    check(f"selection {name}: same keys per query", rows_same >= min_rows and keys_same >= 0.9995,
          f"rows identical {rows_same:.4f}, keys identical {keys_same:.5f}, S={h.shape[1]}")
    return a, b


def attn_compare(name, attn, h, cos, sin, tol=2e-2):
    """Reference forward (sdpa + dense masks) vs fast forward: outputs, d/dh, d/dq_proj."""
    g = torch.randn_like(h[..., : attn.o_proj.out_features])
    outs = {}
    for kind in ("ref", "fast"):
        hh = h.detach().clone().requires_grad_(True)
        attn.zero_grad(set_to_none=True)
        if kind == "ref":
            fq.uninstall()
            o, _ = attn(hh, (cos, sin), causal(h.shape[1]), None)
        else:
            fq.install()
            o, _ = attn(hh, (cos, sin), None, None)
        (o.float() * g.float()).sum().backward()
        outs[kind] = (o.detach().float(), hh.grad.detach().float(), attn.q_proj.weight.grad.detach().float())
    fq.uninstall()
    for i, what in enumerate(("output", "grad wrt input", "grad wrt q_proj")):
        r, f = outs["ref"][i], outs["fast"][i]
        rel = ((r - f).norm() / r.norm().clamp_min(1e-12)).item()
        check(f"attention {name}: same {what}", rel < tol, f"relative diff {rel:.2e}")
    return outs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hf", required=True)
    args = ap.parse_args()
    from transformers import AutoModelForImageTextToText
    from transformers.models.qwen4_exp import modeling_qwen4_exp as m
    torch.manual_seed(0)

    # ---------------- tiny model, budget 64 (16 blocks of 4): selection is active from 64 tokens on
    cfg = tt.tiny_config(args.hf)
    t = cfg.text_config
    # PLE sits on layer index 1, which must be linear attention (as in the real model)
    t.layer_types = ["linear_attention", "linear_attention", "full_attention", "full_attention"]
    t.indexer_budget = 64
    model = AutoModelForImageTextToText.from_config(cfg).to(torch.bfloat16).to(DEV).eval()
    for p in model.parameters():
        p.requires_grad_(False)
    text = model.model.language_model
    attn = text.layers[2].self_attn
    for s in (37, 300, 1001):
        h = torch.randn(1, s, t.hidden_size, device=DEV, dtype=torch.bfloat16)
        cos, sin = rope(text, h, s)
        selection_report(f"tiny S={s}", attn.indexer, h, cos, sin)
    s = 300
    h = torch.randn(1, s, t.hidden_size, device=DEV, dtype=torch.bfloat16)
    cos, sin = rope(text, h, s)
    attn.q_proj.weight.requires_grad_(True)
    attn_compare("tiny S=300", attn, h, cos, sin)
    attn.q_proj.weight.requires_grad_(False)

    # mutation: drop one picked key for one late query -> output must move
    fq.install()
    idx = fq.select_tokens(attn.indexer, h, cos, sin)
    q = torch.randn(1, attn.config.num_attention_heads, s, attn.head_dim, device=DEV, dtype=torch.bfloat16)
    k = torch.randn(1, attn.config.num_key_value_heads, s, attn.head_dim, device=DEV, dtype=torch.bfloat16)
    v = torch.randn_like(k)
    o1 = fq.sparse_attention(q, k, v, idx, attn.scaling)
    bad = idx.clone()
    bad[s - 1, 0] = -1
    o2 = fq.sparse_attention(q, k, v, bad, attn.scaling)
    check("mutation: dropping one picked key changes that query's output",
          (o1[0, s - 1] - o2[0, s - 1]).abs().max().item() > 1e-3 and torch.equal(o1[0, : s - 1], o2[0, : s - 1]))
    fq.uninstall()

    # ---------------- whole tiny model: same log-probs with the patch
    ids = torch.randint(0, t.vocab_size, (1, 700), device=DEV)
    with torch.no_grad():
        ref = torch.log_softmax(model(input_ids=ids, use_cache=False).logits.float(), -1)
        fq.install()
        fast = torch.log_softmax(model(input_ids=ids, use_cache=False).logits.float(), -1)
        fq.uninstall()
    d = (ref - fast).abs().max().item()
    p_ref = ref.exp()
    kl = (p_ref * (ref - fast)).sum(-1).mean().item()
    check("whole tiny model: same log-probs", kl < 1e-3, f"max |dlogp| {d:.3e}, mean KL {kl:.2e}")

    # ---------------- a device_map model: accelerate hooks call the forward bound at load time
    from accelerate.hooks import ModelHook, add_hook_to_module
    hooked = copy.deepcopy(model)
    for mod in hooked.modules():
        if isinstance(mod, m.Qwen4ExpTextAttention):
            add_hook_to_module(mod, ModelHook())
    info = fq.install(hooked)
    with torch.no_grad():
        out_h = torch.log_softmax(hooked(input_ids=ids, use_cache=False).logits.float(), -1)
    n_attn = sum(isinstance(x, m.Qwen4ExpTextAttention) for x in hooked.modules())
    check("hooked model: every attention layer runs the fast path",
          info["hooked_layers"] == n_attn and (out_h - fast).abs().max().item() < 1e-3,
          f"{info['hooked_layers']}/{n_attn} layers, max |dlogp| vs fast {(out_h - fast).abs().max().item():.2e}")
    fq.uninstall(hooked)
    del hooked

    # ---------------- offloaded checkpointing == plain checkpointing (LoRA grads)
    from peft import LoraConfig, get_peft_model
    import lora_train as lt
    base = AutoModelForImageTextToText.from_config(cfg).to(torch.bfloat16).to(DEV)
    for p in base.parameters():
        p.requires_grad_(False)
    pm = get_peft_model(base, LoraConfig(r=4, lora_alpha=8, lora_dropout=0.0, target_modules=lt.TARGET_REGEX))
    for n, p in pm.named_parameters():
        if "lora_B" in n:
            torch.nn.init.normal_(p, std=1e-2)
    pm.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    pm.enable_input_require_grads()
    pm.train()
    ids = torch.randint(0, t.vocab_size, (1, 400), device=DEV)
    grads = {}
    for kind in ("plain", "offload"):
        fq.install(pm, offload=(kind == "offload"))
        if kind == "plain":
            for mod in pm.modules():
                if isinstance(mod, m.Qwen4ExpTextDecoderLayer):
                    mod._gradient_checkpointing_func = _plain_ckpt
        pm.zero_grad(set_to_none=True)
        torch.cuda.reset_peak_memory_stats()
        loss = -torch.log_softmax(pm(input_ids=ids, use_cache=False).logits.float(), -1)[0, :-1].gather(
            -1, ids[0, 1:, None]).mean()
        loss.backward()
        grads[kind] = {n: p.grad.detach().float().clone() for n, p in pm.named_parameters() if p.requires_grad and p.grad is not None}
        fq.uninstall()
    names = sorted(grads["plain"])
    worst = max(((grads["plain"][n] - grads["offload"][n]).norm() / grads["plain"][n].norm().clamp_min(1e-12)).item()
                for n in names)
    check("offload checkpoint: same LoRA gradients as plain checkpointing",
          len(names) > 0 and set(names) == set(grads["offload"]) and worst < 1e-2,
          f"{len(names)} tensors, worst relative diff {worst:.2e}")
    check("offload checkpoint: pinned host buffers in use", len(fq._PINNED) > 0, f"{len(fq._PINNED)} layer buffers")

    # ---------------- per-token work in token chunks (long records): same log-probs and LoRA gradients
    def loss_and_grads(chunk):
        fq.LAYER_CHUNK = chunk
        fq.install(pm, offload=True)
        pm.zero_grad(set_to_none=True)
        lp = torch.log_softmax(pm(input_ids=ids, use_cache=False).logits.float(), -1)[0, :-1].gather(-1, ids[0, 1:, None])
        (-lp.mean()).backward()
        g = {n: p.grad.detach().float().clone() for n, p in pm.named_parameters() if p.requires_grad and p.grad is not None}
        fq.uninstall()
        return lp.detach().squeeze(-1), g
    saved_chunk = fq.LAYER_CHUNK
    lp_full, g_full = loss_and_grads(10 ** 9)
    lp_chunk, g_chunk = loss_and_grads(37)
    fq.LAYER_CHUNK = saved_chunk
    dlp = (lp_full - lp_chunk).abs().max().item()
    worst = max(((g_full[n] - g_chunk[n]).norm() / g_full[n].norm().clamp_min(1e-12)).item() for n in g_full)
    check("chunked layers (37-token chunks) == whole layers: log-probs and LoRA gradients",
          dlp < 2e-2 and worst < 2e-2 and set(g_full) == set(g_chunk),
          f"max |dlogp| {dlp:.2e}, worst grad rel diff {worst:.2e}")

    # ---------------- one real-size attention layer at 4,096 tokens (budget 2,048: selection is active)
    from transformers import AutoConfig
    real = AutoConfig.from_pretrained(args.hf).text_config
    real._attn_implementation = "sdpa"
    big = m.Qwen4ExpTextAttention(real, layer_idx=3).to(torch.bfloat16).to(DEV)
    with torch.no_grad():
        for p in big.parameters():
            if p.ndim == 2:
                torch.nn.init.normal_(p, std=p.shape[1] ** -0.5)
    rot = m.Qwen4ExpTextRotaryEmbedding(config=real).to(DEV)
    s = 4096
    h = torch.randn(1, s, real.hidden_size, device=DEV, dtype=torch.bfloat16)
    pos = torch.arange(s, device=DEV).view(1, 1, -1).expand(3, 1, -1)
    cos, sin = rot(h, pos)
    a, b = selection_report("real dims S=4096", big.indexer, h, cos, sin)
    # query 4095 closes a block: 512 blocks, no tail; query 4094: 512 blocks + its 3-token tail
    check("selection real dims: late queries keep the budget", int(b[-1].sum()) == 2048 and int(b[-2].sum()) == 2051,
          f"last two queries see {int(b[-1].sum())} and {int(b[-2].sum())} keys")
    for p in big.parameters():
        p.requires_grad_(False)
    big.q_proj.weight.requires_grad_(True)
    attn_compare("real dims S=4096", big, h, cos, sin)
    print("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}", flush=True)
    return 1 if FAILS else 0


def _plain_ckpt(fn, *args):
    from torch.utils.checkpoint import checkpoint
    return checkpoint(fn, *args, use_reentrant=False)


if __name__ == "__main__":
    raise SystemExit(main())
