"""
Author: Claude Opus 5 (Bubba)
Date: 16-September-2026
PURPOSE: Pre-flight gradient assertion for the Qwen3.8-27B LoRA training rounds, plus the
one-line repair for the defect it was written to catch. On 16-Sep-2026 a LoRA run on the
NVFP4 checkpoint reached backward without error and trained only 64 of its 208 adapters:
that checkpoint's compressed-tensors config fake-quantizes INPUT ACTIVATIONS on exactly the
seven projections we target plus lm_head, compressed-tensors implements that by replacing the
module's forward with one that passes the input through `fake_quantize`, and `fake_quantize`
is decorated `@torch.no_grad()`. The input is therefore detached and no gradient can cross a
targeted module. peft hides it: the added `lora_B(lora_A(x))` branch keeps requires_grad alive,
and since lora_B is zero-initialised that branch carries exactly zero backwards. Loss falls,
nothing raises, and three quarters of the adapter is mathematically frozen. Loading with
`dequantize=True` does not help -- it decompresses the weights and leaves the patched forward.
`disable_compressed_tensors_fake_quant()` turns the fake-quant off (the patched forward honours
a `quantization_enabled` flag and falls through to nn.Linear.forward); `check_lora_gradients()`
proves on one real backward that every lora_B now receives a gradient, and is meant to be called
as a gate before any training round starts.
Only lora_B is checked. peft zero-initialises lora_B, so dL/dA is proportional to B and every
lora_A gradient is identically zero on the first backward -- an all-zero lora_A column is
expected and says nothing.
Root cause write-up: docs/trace-findings/2026-09-17-lora-gradient-rootcause.md
SRP/DRY check: Pass -- no existing gradient or trainer pre-flight in this repo (`ls tools/
scripts/`, `grep -ril get_peft_model` and `grep -ril quantization_enabled` over the tree excluding
vendor/ returns nothing). There is no trainer in this repo to change; the training scripts live
on the DGX boxes, which is why this ships as a standalone callable rather than a config edit.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict

import torch
import torch.nn.functional as F


def disable_compressed_tensors_fake_quant(model: torch.nn.Module) -> int:
    """Turn off compressed-tensors' on-the-fly quantize/dequantize on every module that carries a
    quantization scheme, so that the module's forward falls through to the ordinary differentiable
    one. Call this after `from_pretrained(..., quantization_config=CompressedTensorsConfig(
    dequantize=True))` and BEFORE `get_peft_model`. Returns how many modules were changed; zero
    means the checkpoint was never quantized (a plain BF16 load), which is the preferred case and
    not an error.
    """
    n = 0
    for module in model.modules():
        if getattr(module, "quantization_scheme", None) is not None:
            module.quantization_enabled = False
            n += 1
    return n


def lora_b_gradient_table(model: torch.nn.Module, name_filter: str = "") -> dict[str, dict]:
    """Bucket every trainable lora_B parameter by the leaf module it adapts and summarise its
    gradient. `grad_is_none` (the parameter never entered the backward graph) and `zero` (it did,
    and the gradient was exactly zero) have different causes and are counted separately."""
    table: dict[str, dict] = defaultdict(
        lambda: {"n": 0, "grad_is_none": 0, "zero": 0, "nonzero": 0, "abs_sum": 0.0}
    )
    for name, param in model.named_parameters():
        if ".lora_B." not in name or not param.requires_grad:
            continue
        if name_filter and name_filter not in name:
            continue
        entry = table[name.split(".lora_B")[0].rsplit(".", 1)[-1]]
        entry["n"] += 1
        if param.grad is None:
            entry["grad_is_none"] += 1
            continue
        total = float(param.grad.abs().sum())
        entry["abs_sum"] += total
        entry["nonzero" if total > 0 else "zero"] += 1
    return dict(table)


def format_table(table: dict[str, dict]) -> str:
    lines = [f"{'module':16s} {'n':>4s} {'none':>5s} {'zero':>5s} {'nonzero':>8s}   sum|grad|"]
    for leaf in sorted(table, key=lambda k: -table[k]["n"]):
        e = table[leaf]
        lines.append(
            f"{leaf:16s} {e['n']:4d} {e['grad_is_none']:5d} {e['zero']:5d} "
            f"{e['nonzero']:8d}   {e['abs_sum']:.6g}"
        )
    return "\n".join(lines)


def check_lora_gradients(model: torch.nn.Module, name_filter: str = "", strict: bool = True) -> dict:
    """Inspect the gradients already present on `model` (call this straight after `loss.backward()`
    and before `optimizer.step()`), and raise unless every trainable lora_B got a nonzero one."""
    table = lora_b_gradient_table(model, name_filter)
    if not table:
        raise RuntimeError("no trainable lora_B parameters found - is LoRA actually attached?")
    dead = {k: e for k, e in table.items() if e["nonzero"] != e["n"]}
    report = {"table": table, "dead_buckets": sorted(dead), "ok": not dead}
    if dead and strict:
        raise RuntimeError(
            "LoRA gradient pre-flight FAILED: "
            f"{sum(e['n'] - e['nonzero'] for e in dead.values())} of "
            f"{sum(e['n'] for e in table.values())} lora_B parameters received no gradient.\n"
            + format_table(table)
            + "\n\nIf the dead buckets are the input projections (q/k/v_proj, in_proj_qkv, "
            "in_proj_z) while the output projections (o_proj, out_proj) are healthy, this is the "
            "compressed-tensors activation fake-quant detaching the input: call "
            "disable_compressed_tensors_fake_quant(model) before get_peft_model, or train from "
            "the plain BF16 checkpoint."
        )
    return report


def preflight(model, forward_and_loss, name_filter: str = "", strict: bool = True) -> dict:
    """Run one backward through `forward_and_loss(model)` from a cleared gradient state and check
    the result. Grads are cleared to None first and restored to None afterwards, so this leaves no
    residue in an optimizer's view of the model."""
    for p in model.parameters():
        p.grad = None
    model.train()
    loss = forward_and_loss(model)
    if not loss.requires_grad:
        raise RuntimeError(
            "loss has no grad_fn before backward - the graph is severed above the loss. "
            "Check lm_head (it is quantized in the NVFP4 checkpoint) and check that the batch "
            "contains at least one supervised token."
        )
    loss.backward()
    try:
        return check_lora_gradients(model, name_filter=name_filter, strict=strict)
    finally:
        for p in model.parameters():
            p.grad = None


# --------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------

TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "in_proj_qkv", "in_proj_z", "out_proj"]


def _tiny_config(real_config: dict, layers: int, dtype: str):
    """Shrink the real Qwen3.8-27B config to something that fits on a CPU while keeping every
    architectural flag: model_type, full_attention_interval, attn_output_gate, output_gate_type,
    head_dim (mrope_section is derived from it), the gated-delta head ratio and kernel width."""
    from transformers import AutoConfig

    text = dict(real_config["text_config"])
    text.update(
        hidden_size=256,
        intermediate_size=512,
        num_attention_heads=2,
        num_key_value_heads=1,
        num_hidden_layers=layers,
        vocab_size=1000,
        linear_num_key_heads=2,
        linear_num_value_heads=6,
        layer_types=(["linear_attention"] * 3 + ["full_attention"]) * (layers // 4),
        dtype=dtype,
        use_cache=False,
    )
    vision = dict(real_config["vision_config"])
    vision.update(depth=1, hidden_size=64, intermediate_size=128, num_heads=2, out_hidden_size=256)
    top = {k: v for k, v in real_config.items() if k not in ("text_config", "vision_config")}
    top.update(text_config=text, vision_config=vision, dtype=dtype)
    top.pop("transformers_version", None)
    top.pop("model_type", None)
    top.pop("quantization_config", None)
    return AutoConfig.for_model("qwen3_5", **top)


def _self_test(args) -> int:
    """Build a tiny random model of the real architecture on CPU, attach the real LoRA target set,
    and prove both halves of this module: that the check passes on a healthy model, and that it
    catches the failure when the base layers' inputs are detached the way compressed-tensors
    detaches them."""
    import json
    import types
    import warnings

    from peft import LoraConfig, get_peft_model
    from transformers.models.qwen3_5 import modeling_qwen3_5 as qwen

    if torch.cuda.is_available():
        print("refusing to self-test with a GPU visible; run with CUDA_VISIBLE_DEVICES=''")
        return 2

    real = json.load(open(args.config))
    cfg = _tiny_config(real, args.layers, args.dtype)
    cfg._attn_implementation = args.attn
    # fla's Triton kernel is bound unconditionally when fla is importable and has no CPU path.
    qwen.torch_chunk_gated_delta_rule = qwen.torch_chunk_gated_delta_rule.__wrapped__
    qwen.torch_recurrent_gated_delta_rule = qwen.torch_recurrent_gated_delta_rule.__wrapped__

    torch.manual_seed(0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        base = qwen.Qwen3_5ForConditionalGeneration._from_config(cfg, attn_implementation=args.attn)
    base = base.to(getattr(torch, args.dtype))
    for p in base.parameters():
        p.requires_grad_(False)
    model = get_peft_model(
        base,
        LoraConfig(r=16, lora_alpha=32, lora_dropout=0.0, bias="none",
                   task_type="CAUSAL_LM", target_modules=TARGETS),
    )
    inner = model.base_model.model
    head_w = inner.lm_head.weight

    gen = torch.Generator().manual_seed(1)
    ids = torch.randint(0, 900, (1, 96), generator=gen)
    labels = torch.full_like(ids, -100)
    labels[0, 48:] = ids[0, 48:]

    def forward_and_loss(m):
        hidden = m.base_model.model.model(input_ids=ids, use_cache=False).last_hidden_state[0]
        keep = labels[0][1:] != -100
        return F.cross_entropy(
            F.linear(hidden[:-1][keep], head_w).float(), labels[0][1:][keep]
        )

    print(f"resolved attn_implementation: {model.base_model.model.config._attn_implementation!r}")

    healthy = preflight(model, forward_and_loss, name_filter=".language_model.", strict=False)
    print("\n-- healthy model --")
    print(format_table(healthy["table"]))
    if not healthy["ok"]:
        print("SELF-TEST FAILED: a clean model should have gradient everywhere")
        return 1

    for _, module in inner.named_modules():
        layer = getattr(module, "base_layer", None)
        if isinstance(layer, torch.nn.Linear):
            def fwd(self, x):
                with torch.no_grad():          # stands in for compressed-tensors' fake_quantize
                    xq = x.clone()
                return F.linear(xq, self.weight, self.bias)
            layer.forward = types.MethodType(fwd, layer)

    broken = preflight(model, forward_and_loss, name_filter=".language_model.", strict=False)
    print("\n-- base-layer input detached (the NVFP4 failure) --")
    print(format_table(broken["table"]))
    survivors = {k for k, e in broken["table"].items() if e["nonzero"] == e["n"]}
    if broken["ok"] or survivors != {"o_proj", "out_proj"}:
        print(f"SELF-TEST FAILED: expected only o_proj/out_proj to survive, got {sorted(survivors)}")
        return 1
    print("\nSELF-TEST PASSED: the check is green on a healthy model and red on the known defect,")
    print("and the survivors are exactly the two projections that sit on the residual stream.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true",
                    help="CPU-only proof that this check catches the NVFP4 defect")
    ap.add_argument("--config", default="/home/son/models/Qwen3.8-27B-BF16/config.json",
                    help="real config.json to shrink for --self-test")
    ap.add_argument("--layers", type=int, default=8, help="tiny-model layer count (multiple of 4)")
    ap.add_argument("--attn", default="sdpa")
    ap.add_argument("--dtype", default="float32")
    args = ap.parse_args(argv)
    if args.self_test:
        return _self_test(args)
    ap.error("nothing to do: pass --self-test, or import preflight()/check_lora_gradients() "
             "from your trainer and call it after loss.backward()")


if __name__ == "__main__":
    sys.exit(main())
