"""Render a training record into token ids + a loss mask with the model's own processor (plan §2, B4/B6).

Shared by the G0 exactness check and the trainer. The served chat template (Qwen/Qwen3.8-Flash-Next
chat_template.jinja) renders:
- a user turn as  <|im_start|>user\n ... <|im_end|>\n   (images as <|vision_start|><|image_pad|><|vision_end|>,
  expanded by the processor to one pad per 2x2 patch merge);
- an assistant turn as  <|im_start|>assistant\n<think>\n{reasoning|trim}\n</think>\n\n{content}<tool_call>...
  </tool_call><|im_end|>\n ;
- the generation prompt as  <|im_start|>assistant\n<think>\n .
So the tokens the model GENERATED for an assistant turn are everything after "<|im_start|>assistant\n<think>\n"
up to and including its <|im_end|>. Those get loss when the record marks the message for training.

Conversions the server does before templating, done here too:
- tool_call arguments arrive as a JSON string in the logs; the template iterates `arguments|items`, so they are
  parsed to a dict (key order kept);
- OpenAI image parts {"type": "image_url", "image_url": {"url": data-URL}} become {"type": "image", "url": ...};
- the tool schemas are re-serialized the way the serving engine's request model dumps them (`server_tools`).
  Measured 1-Oct on Daniel's server (SGLang 0.5.19 "pennyroyal"): rendering the logged tools as sent gives
  prompts 11 tokens short of the server's own count on every request; SGLang's Tool.model_dump() adds
  "strict": false inside the function (field order description, name, parameters, strict) and "defer_loading":
  null on the wrapper. With that, rendered == logged prompt_tokens exactly (probe_template_gap.py).
"""
from __future__ import annotations

import copy
import json
from typing import Any

GEN_HEADER = "<|im_start|>assistant\n<think>\n"
END = "<|im_end|>"
SERVER_PROFILES = ("sglang-0.5.19", "as-sent")


def server_tools(tools: list[dict] | None, profile: str = "sglang-0.5.19") -> list[dict] | None:
    """Tool schemas exactly as the serving engine hands them to the chat template."""
    if not tools or profile == "as-sent":
        return tools or None
    if profile != "sglang-0.5.19":
        raise ValueError(f"unknown server profile {profile!r}")
    out = []
    for t in tools:
        f = t.get("function", {})
        fn = {"description": f.get("description"), "name": f.get("name"), "parameters": f.get("parameters"),
              "strict": bool(f.get("strict", False))}
        out.append({"type": t.get("type", "function"), "function": fn, "defer_loading": t.get("defer_loading")})
    return out


def normalize_messages(messages: list[dict]) -> list[dict]:
    out = copy.deepcopy(messages)
    for m in out:
        for tc in m.get("tool_calls") or []:
            fn = tc.get("function") if isinstance(tc, dict) else None
            if fn and isinstance(fn.get("arguments"), str):
                try:
                    fn["arguments"] = json.loads(fn["arguments"]) if fn["arguments"].strip() else {}
                except json.JSONDecodeError:
                    pass                                    # leave as is; the token check will flag it
        if isinstance(m.get("content"), list):
            parts = []
            for p in m["content"]:
                if isinstance(p, dict) and p.get("type") == "image_url":
                    url = p["image_url"]["url"] if isinstance(p.get("image_url"), dict) else p.get("image_url")
                    parts.append({"type": "image", "url": url})
                else:
                    parts.append(p)
            m["content"] = parts
    return out


def assistant_spans(ids: list[int], header_ids: list[int], end_id: int) -> list[tuple[int, int]]:
    """[start, end) of every generated assistant segment: after each header occurrence through its <|im_end|>."""
    spans = []
    n, h = len(ids), len(header_ids)
    i = 0
    while i <= n - h:
        if ids[i:i + h] == header_ids:
            s = i + h
            j = s
            while j < n and ids[j] != end_id:
                j += 1
            spans.append((s, min(j + 1, n)))
            i = j + 1
        else:
            i += 1
    return spans


def render(processor: Any, record: dict, *, add_generation_prompt: bool = False,
           profile: str = "sglang-0.5.19") -> dict:
    """Token ids, loss mask and vision inputs of one record.

    With add_generation_prompt=True the result is the PROMPT of the request that produced the record's last
    message (for the token-count check against the logged usage); with False it is the training sequence."""
    msgs = normalize_messages(record["messages"])
    # return_tensors="pt": every model input (pixel values, grid sizes, the multimodal token-type ids the rope index
    # needs) comes back as a batch-of-1 tensor; a plain list broke qwen4_exp's get_rope_index on 1-Oct.
    enc = processor.apply_chat_template(msgs, tools=server_tools(record.get("tools"), profile), tokenize=True,
                                        return_dict=True, return_tensors="pt",
                                        add_generation_prompt=add_generation_prompt,
                                        **(record.get("chat_template_kwargs") or {}))
    ids = enc["input_ids"]
    ids = ids[0].tolist() if hasattr(ids, "tolist") else (ids[0] if ids and isinstance(ids[0], list) else list(ids))
    tok = processor.tokenizer
    header = tok(GEN_HEADER, add_special_tokens=False)["input_ids"]
    end_id = tok.convert_tokens_to_ids(END)
    spans = assistant_spans(ids, header, end_id)
    roles = [m["role"] for m in msgs]
    n_asst = roles.count("assistant")
    if add_generation_prompt:
        spans = spans[:n_asst]                       # the trailing header is the open generation prompt
    mask = [False] * len(ids)
    weight = [0.0] * len(ids)
    flags = record.get("train") or [False] * len(msgs)
    wts = record.get("weights") or [1.0 if f else 0.0 for f in flags]
    trained = [(t, w) for m, t, w in zip(msgs, flags, wts) if m["role"] == "assistant"]
    for (s, e), (tr, w) in zip(spans, trained):
        if tr:
            for k in range(s, e):
                mask[k] = True
                weight[k] = float(w)
    vision = {k: v for k, v in enc.items() if k not in ("input_ids", "attention_mask")}
    return {"input_ids": ids, "loss_mask": mask, "loss_weights": weight, "vision": vision,
            "n_assistant_messages": n_asst, "n_assistant_spans": len(spans), "n_loss_tokens": sum(mask)}
