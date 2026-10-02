"""nvfp4_experts.py against the BF16 checkpoint and transformers' own expert code (GPU box).

Works on either served checkpoint (format detected from the tensor names): RadixArk NVFP4 (Combo A) or Daniel's
Intel W4A16 AutoRound (GPTQ int4, group 128). For GPTQ it also checks that the non-expert tensors are byte-identical
to the official BF16 model (the trainer loads those from there).

1. unpacking: the served experts, unpacked, match the official BF16 experts (cosine and relative error, at three
   layers and three experts each); the opposite nibble order (NVFP4) or zero-point convention (GPTQ) must be clearly
   worse (the check can fail);
2. module: NVFP4Experts gives the same output and input gradient as transformers' eager expert loop holding the
   same (unpacked) weights, on random tokens and random routing;
3. size: packed bytes per layer.

Run: python test_nvfp4.py --bf16 /opt/m/bf16 --nvfp4 /opt/m/nvfp4
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nvfp4_experts as nx  # noqa: E402

FAILS = []
DEV = torch.device("cuda")


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""), flush=True)
    if not ok:
        FAILS.append(name)


def bf16_experts(bf16_dir: str, layer: int) -> tuple[torch.Tensor, torch.Tensor]:
    from safetensors import safe_open
    d = Path(bf16_dir)
    wm = json.loads((d / "model.safetensors.index.json").read_text())["weight_map"]
    out = []
    for k in ("gate_up_proj", "down_proj"):
        name = f"model.language_model.layers.{layer}.mlp.experts.{k}"
        with safe_open(str(d / wm[name]), framework="pt") as sf:
            out.append(sf.get_tensor(name))
    return out[0], out[1]


def compare(a: torch.Tensor, b: torch.Tensor) -> tuple[float, float]:
    a, b = a.float().flatten(), b.float().flatten()
    cos = torch.nn.functional.cosine_similarity(a, b, dim=0).item()
    rel = ((a - b).norm() / b.norm()).item()
    return cos, rel


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bf16", required=True)
    ap.add_argument("--nvfp4", required=True)
    ap.add_argument("--layers", default="0,23,47")
    a = ap.parse_args()
    from transformers import AutoConfig
    cfg = AutoConfig.from_pretrained(a.bf16).text_config
    e_n = cfg.num_experts
    wm = json.loads((Path(a.nvfp4) / "model.safetensors.index.json").read_text())["weight_map"]
    fmt = nx.checkpoint_format(wm)
    print("checkpoint format:", fmt, flush=True)
    # the trainer loads every non-expert tensor from the official BF16 model: they must be the served bytes
    from safetensors import safe_open
    wm_bf = json.loads((Path(a.bf16) / "model.safetensors.index.json").read_text())["weight_map"]
    shared = [k for k in ("model.language_model.layers.3.self_attn.q_proj.weight",
                          "model.language_model.layers.0.linear_attn.in_proj_qkv.weight",
                          "model.language_model.layers.0.linear_attn.out_proj.weight",
                          "model.language_model.layers.20.mlp.shared_expert.gate_proj.weight",
                          "model.language_model.layers.20.mlp.gate.weight",
                          "model.language_model.layers.47.attn_hyper_connection.input_mix_weight_up.weight")
              if k in wm and k in wm_bf]
    same = []
    for k in shared:
        with safe_open(str(Path(a.nvfp4) / wm[k]), framework="pt") as f1, \
                safe_open(str(Path(a.bf16) / wm_bf[k]), framework="pt") as f2:
            same.append(torch.equal(f1.get_tensor(k), f2.get_tensor(k)))
    check("non-expert tensors are byte-identical to the official BF16 model", bool(shared) and all(same),
          f"{sum(same)}/{len(shared)} identical")
    for layer in [int(x) for x in a.layers.split(",")]:
        ref_gu, ref_dn = (t.to(DEV) for t in bf16_experts(a.bf16, layer))
        if fmt == "gptq":
            packed = {k: v.to(DEV) for k, v in nx.read_layer_gptq(a.nvfp4, layer, e_n, wm).items()}

            def unpack(zo, n=None):
                sl = slice(0, n)
                gate = nx.dequant_gptq(packed["g_qw"][sl], packed["g_qz"][sl], packed["g_s"][sl], zero_offset=zo)
                up = nx.dequant_gptq(packed["u_qw"][sl], packed["u_qz"][sl], packed["u_s"][sl], zero_offset=zo)
                down = nx.dequant_gptq(packed["d_qw"][sl], packed["d_qz"][sl], packed["d_s"][sl], zero_offset=zo)
                return torch.cat([gate, up], dim=1), down

            # which zero-point convention: auto_gptq v1 stores zero - 1 (offset 1), v2 stores it as is (offset 0)
            errs = {zo: compare(unpack(zo, 4)[0][0], ref_gu[0])[1] for zo in (0, 1)}
            best = min(errs, key=errs.get)
            nx.GPTQ_ZERO_OFFSET = best
            check(f"layer {layer}: the zero-point convention is clear (the other one is much worse)",
                  errs[1 - best] > 3 * errs[best], f"offset {best}: rel {errs[best]:.3f}; offset {1 - best}: "
                  f"rel {errs[1 - best]:.3f}")
            gu, dn = unpack(best)
        else:
            packed = {k: v.to(DEV) for k, v in nx.read_layer(a.nvfp4, layer, e_n).items()}
            gu = nx.dequant(packed["gu_q"], packed["gu_s"], packed["gu_s2"])
            dn = nx.dequant(packed["dn_q"], packed["dn_s"], packed["dn_s2"])
            gu_swap = nx.dequant(packed["gu_q"][:4], packed["gu_s"][:4], packed["gu_s2"][:4], low_first=False)
            cs, rs = compare(gu_swap[0], ref_gu[0])
            c0, r0 = compare(gu[0], ref_gu[0])
            check(f"layer {layer}: the other nibble order is clearly worse (mutation)", rs > 3 * r0,
                  f"swapped rel {rs:.3f} vs {r0:.3f}")
        gib = sum(v.numel() * v.element_size() for v in packed.values()) / 2**30
        check(f"layer {layer}: shapes match the BF16 experts", gu.shape == ref_gu.shape and dn.shape == ref_dn.shape,
              f"{tuple(gu.shape)} {tuple(dn.shape)}; packed {gib:.2f} GiB vs BF16 "
              f"{(ref_gu.numel() + ref_dn.numel()) * 2 / 2**30:.2f} GiB")
        for e in (0, e_n // 2, e_n - 1):
            c1, r1 = compare(gu[e], ref_gu[e])
            c2, r2 = compare(dn[e], ref_dn[e])
            check(f"layer {layer} expert {e}: unpacked {fmt} ~ BF16", c1 > 0.98 and c2 > 0.98 and r1 < 0.2 and r2 < 0.2,
                  f"gate_up cos {c1:.4f} rel {r1:.3f}; down cos {c2:.4f} rel {r2:.3f}")
        del ref_gu, ref_dn

        # module vs transformers' eager experts with the same unpacked weights
        from transformers.models.qwen4_exp import modeling_qwen4_exp as m
        ref = m.Qwen4ExpTextExperts(cfg).to(DEV).to(torch.bfloat16)
        ref.config._experts_implementation = "eager"
        with torch.no_grad():
            ref.gate_up_proj.copy_(gu)
            ref.down_proj.copy_(dn)
        for p in ref.parameters():
            p.requires_grad_(False)
        mod = nx.NVFP4Experts(cfg).to(DEV)
        for k, v in packed.items():
            setattr(mod, k, v)
        mod.fmt = "gptq" if fmt == "gptq" else None
        t = 3000
        torch.manual_seed(layer)
        h = (torch.randn(t, cfg.hidden_size, device=DEV) * 0.5).to(torch.bfloat16)
        logits = torch.randn(t, e_n, device=DEV)
        w, idx = torch.softmax(logits, -1).topk(cfg.num_experts_per_tok, dim=-1)
        w = (w / w.sum(-1, keepdim=True)).to(torch.bfloat16)
        g = torch.randn(t, cfg.hidden_size, device=DEV, dtype=torch.bfloat16)
        outs = []
        for module in (ref, mod):
            hh = h.clone().requires_grad_(True)
            o = module(hh, idx, w)
            (o.float() * g.float()).sum().backward()
            outs.append((o.detach().float(), hh.grad.float()))
        _, ro = compare(outs[1][0], outs[0][0])
        _, rg = compare(outs[1][1], outs[0][1])
        check(f"layer {layer}: NVFP4Experts == eager experts (output, input grad)", ro < 2e-2 and rg < 2e-2,
              f"relative diff output {ro:.2e}, grad {rg:.2e}")
        # token chunks (what ~100k-token records use): same output and gradient as one pass
        saved, nx.TOKEN_CHUNK = nx.TOKEN_CHUNK, 700
        hh = h.clone().requires_grad_(True)
        o = mod(hh, idx, w)
        (o.float() * g.float()).sum().backward()
        nx.TOKEN_CHUNK = saved
        _, rc = compare(o.detach().float(), outs[1][0])
        _, rcg = compare(hh.grad.float(), outs[1][1])
        # BF16 grouped GEMMs round differently with different group sizes: ~5e-3 is the noise level here (the same
        # as NVFP4Experts vs eager); a misaligned chunk would be O(1), which the rolled-rows mutation shows
        _, rroll = compare(torch.roll(o.detach().float(), 700, dims=0), outs[1][0])
        check(f"layer {layer}: token-chunked experts == one pass", rc < 2e-2 and rcg < 2e-2 and rroll > 0.5,
              f"relative diff output {rc:.2e}, grad {rcg:.2e}; rows shifted by one chunk {rroll:.2f}")
        del gu, dn, packed, ref, mod
        torch.cuda.empty_cache()
    print("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}", flush=True)
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
