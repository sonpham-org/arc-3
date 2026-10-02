"""CPU test of the trainer and merge path on a tiny random qwen4_exp model (G1 pre-check, no GPU).

Shrinks the real Flash-Next config (same architecture code in transformers 5.18, same tensor names), saves it
as a BF16 safetensors checkpoint, then checks:
1. the LoRA regex hits exactly the shared BF16 targets (attention, linear attention, shared expert; no MTP);
2. lora_train.token_logprobs (decoder -> chunked head) equals log_softmax of the model's own logits;
3. a few optimizer steps on one record lower its loss (gradients reach the LoRA);
4. merge_lora: a zero adapter leaves every shard byte-identical; the trained adapter merged into the BF16
   checkpoint gives the same log-probs as the LoRA model (within BF16 rounding);
5. render.py on a real-template conversation: one span per assistant message, loss only inside them.

Run: python test_trainer_tiny.py --hf /opt/rl/hf   (the processor files of Qwen/Qwen3.8-Flash-Next)
"""
from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
import tempfile
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lora_train as lt  # noqa: E402
import merge_lora as ml  # noqa: E402
import render  # noqa: E402

FAILS = []
# On a GPU box the fast linear-attention kernels (Triton) refuse CPU tensors, so the tiny model runs on the GPU there.
DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""), flush=True)
    if not ok:
        FAILS.append(name)


def tiny_config(hf: str):
    from transformers import AutoConfig
    cfg = AutoConfig.from_pretrained(hf)
    t = cfg.text_config
    shrink = {"hidden_size": 64, "num_hidden_layers": 4, "num_attention_heads": 2, "num_key_value_heads": 1,
              "head_dim": 32, "linear_num_key_heads": 2, "linear_num_value_heads": 4, "linear_key_head_dim": 16,
              "linear_value_head_dim": 16, "num_experts": 8, "num_experts_per_tok": 2, "moe_intermediate_size": 32,
              "shared_expert_intermediate_size": 32, "hc_lowrank": 16, "indexer_head_dim": 16, "indexer_n_heads": 2,
              "indexer_budget": 64, "ple_embed_dim": 64, "ngram_vocab_size_base": 4096, "split_ngram_parts": 2,
              "make_ngram_vocab_size_divisible_by": 8, "mtp_num_hidden_layers": 1}
    for k, v in shrink.items():
        if hasattr(t, k):
            setattr(t, k, v)
    t.layer_types = ["linear_attention", "linear_attention", "linear_attention", "full_attention"]
    v = cfg.vision_config
    for k, val in {"depth": 1, "hidden_size": 32, "intermediate_size": 64, "num_heads": 2, "out_hidden_size": 64}.items():
        if hasattr(v, k):
            setattr(v, k, val)
    for k in ("deepstack_visual_indexes",):
        if hasattr(v, k):
            setattr(v, k, [])
    return cfg


def conversation():
    sys_m = {"role": "system", "content": "You play a grid game."}
    user = {"role": "user", "content": [{"type": "text", "text": "Frame 1: what do you do?"}]}
    a1 = {"role": "assistant", "reasoning_content": "I should test UP alone first.",
          "tool_calls": [{"id": "c1", "type": "function",
                          "function": {"name": "python", "arguments": json.dumps({"code": "action('UP')"})}}]}
    tool = {"role": "tool", "content": "{\"moved\": true}"}
    a2 = {"role": "assistant", "reasoning_content": "UP moved the piece. Now RIGHT.",
          "tool_calls": [{"id": "c2", "type": "function",
                          "function": {"name": "python", "arguments": json.dumps({"code": "action('RIGHT')"})}}]}
    tools = [{"type": "function", "function": {"name": "python", "description": "run code",
                                               "parameters": {"type": "object", "properties": {"code": {"type": "string"}},
                                                              "required": ["code"]}}}]
    return {"messages": [sys_m, user, a1, tool, a2], "train": [False, False, True, False, True], "tools": tools,
            "chat_template_kwargs": {"preserve_thinking": True}, "meta": {"game": "tiny"}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hf", required=True)
    args = ap.parse_args()
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForImageTextToText, AutoProcessor
    torch.manual_seed(0)
    processor = AutoProcessor.from_pretrained(args.hf)

    # 5. render on the real template
    rec = conversation()
    r = render.render(processor, rec)
    text = processor.tokenizer.decode([t for t, m in zip(r["input_ids"], r["loss_mask"]) if m])
    check("render: one span per assistant message", r["n_assistant_spans"] == 2, str(r["n_assistant_spans"]))
    check("render: loss covers both replies and their tool calls",
          "test UP alone" in text and "action('RIGHT')" in text and "<|im_end|>" in text and "system" not in text,
          repr(text[:160]))
    check("render: tool output not trained", '{"moved": true}' not in text and "tool_response" not in text)
    rp = render.render(processor, rec, add_generation_prompt=True)
    check("render: generation prompt adds the open header", len(rp["input_ids"]) > len(r["input_ids"]))
    wrec = dict(rec, weights=[0.0, 0.0, 0.5, 0.0, 1.0])            # efficiency weights per reply
    rw = render.render(processor, wrec)
    span_w = sorted({w for w, m in zip(rw["loss_weights"], rw["loss_mask"]) if m})
    check("render: per-reply weights reach the tokens", span_w == [0.5, 1.0], str(span_w))
    check("render: no weight outside trained spans",
          all(w == 0.0 for w, m in zip(rw["loss_weights"], rw["loss_mask"]) if not m))

    cfg = tiny_config(args.hf)
    model = AutoModelForImageTextToText.from_config(cfg).to(torch.bfloat16)
    tmp = Path(tempfile.mkdtemp())
    ck = tmp / "ck"
    model.save_pretrained(ck, safe_serialization=True, max_shard_size="20MB")
    if not (ck / "model.safetensors.index.json").exists():      # single shard: write an index like the real one
        from safetensors import safe_open
        with safe_open(str(ck / "model.safetensors"), framework="pt") as sf:
            keys = list(sf.keys())
        (ck / "model.safetensors.index.json").write_text(json.dumps({"weight_map": {k: "model.safetensors" for k in keys}}))
    model = AutoModelForImageTextToText.from_pretrained(ck, dtype=torch.bfloat16).to(DEV)
    for p in model.parameters():
        p.requires_grad_(False)

    # 1. targets
    pm = get_peft_model(copy.deepcopy(model), LoraConfig(r=4, lora_alpha=8, lora_dropout=0.0, target_modules=lt.TARGET_REGEX))
    hit = sorted(n.replace("base_model.model.", "").rsplit(".lora_A", 1)[0] for n, _ in pm.named_modules() if n.endswith("lora_A"))
    kinds = {h.split(".layers.")[1].split(".", 1)[1] for h in hit}
    check("lora targets: attention + linear attention + shared expert, no MTP",
          not any(h.startswith("mtp") for h in hit) and kinds == {
              "self_attn.q_proj", "self_attn.k_proj", "self_attn.v_proj", "self_attn.o_proj",
              "linear_attn.in_proj_qkv", "linear_attn.in_proj_z", "linear_attn.out_proj",
              "mlp.shared_expert.gate_proj", "mlp.shared_expert.up_proj", "mlp.shared_expert.down_proj"},
          f"{len(hit)} modules: {sorted(kinds)}")

    # 2. chunked log-probs == model logits
    b = lt.to_batch(processor, rec, DEV)
    with torch.no_grad():
        lp = lt.token_logprobs(pm, b, chunk=3)
        full = pm(input_ids=b["input_ids"], **b["vision"]).logits[0].float()
        pos = b["loss_mask"][0].nonzero().squeeze(-1)
        pos = pos[pos > 0]
        ref = torch.log_softmax(full[pos - 1], -1).gather(-1, b["input_ids"][0][pos][:, None]).squeeze(-1)
    check("token_logprobs == log_softmax(model logits)", torch.allclose(lp, ref, atol=2e-2),
          f"max diff {(lp - ref).abs().max().item():.4f}")
    bw = lt.to_batch(processor, wrec, DEV)
    check("trained_weights aligned with token_logprobs", lt.trained_weights(bw).numel() == lp.numel(),
          f"{lt.trained_weights(bw).numel()} vs {lp.numel()}")

    # 3. a few steps lower the loss
    for n, p in pm.named_parameters():
        if "lora_B" in n:
            torch.nn.init.normal_(p, std=1e-3)
    opt = torch.optim.AdamW([p for p in pm.parameters() if p.requires_grad], lr=5e-3)
    losses = []
    for _ in range(6):
        loss = -lt.token_logprobs(pm, b, grad=True).mean()
        loss.backward()
        opt.step()
        opt.zero_grad()
        losses.append(loss.item())
    check("training lowers the loss", losses[-1] < losses[0] - 1e-3, f"{losses[0]:.3f} -> {losses[-1]:.3f}")

    # 4. merge
    zero = get_peft_model(copy.deepcopy(model), LoraConfig(r=4, lora_alpha=8, lora_dropout=0.0, target_modules=lt.TARGET_REGEX))
    zero.save_pretrained(tmp / "zero")                     # peft initializes B = 0
    ml.merge(tmp / "zero", ck, tmp / "m0", stochastic=False, mult=1.0, seed=0)
    same = all(ml.sha256(ck / s) == ml.sha256(tmp / "m0" / s) for s in
               {*json.loads((ck / "model.safetensors.index.json").read_text())["weight_map"].values()})
    check("zero adapter merge is byte-identical", same)
    pm.save_pretrained(tmp / "trained")
    rep = ml.merge(tmp / "trained", ck, tmp / "m1", stochastic=False, mult=1.0, seed=0)
    merged = AutoModelForImageTextToText.from_pretrained(tmp / "m1", dtype=torch.bfloat16).to(DEV)
    with torch.no_grad():
        lp_m = lt.token_logprobs(merged, b)
        lp_p = lt.token_logprobs(pm, b)
    check("merged checkpoint == LoRA model (BF16)", torch.allclose(lp_m, lp_p, atol=5e-2),
          f"max diff {(lp_m - lp_p).abs().max().item():.4f}, kept share {rep['kept_share_mean']}")
    # mutation: a sign-flipped merge must NOT match
    ml.merge(tmp / "trained", ck, tmp / "m2", stochastic=False, mult=-1.0, seed=0)
    flipped = AutoModelForImageTextToText.from_pretrained(tmp / "m2", dtype=torch.bfloat16).to(DEV)
    with torch.no_grad():
        lp_f = lt.token_logprobs(flipped, b)
    check("mutation: sign-flipped merge differs", (lp_f - lp_p).abs().max().item() > 5e-2,
          f"max diff {(lp_f - lp_p).abs().max().item():.4f}")
    shutil.rmtree(tmp, ignore_errors=True)
    print("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}", flush=True)
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
