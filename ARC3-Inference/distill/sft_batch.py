#!/usr/bin/env python3
# Author: Claude Opus 5 (Bubba)
# Date: 18-September-2026
# PURPOSE: The single shared record->batch->loss path for ARC-3 LoRA SFT. Holds the three
#   things `distill/train_lora.py` and `distill/eval_lora.py` MUST agree on exactly: the
#   assistant-span label mask, the image-token mask, and the chunked cross-entropy over a
#   detached lm_head. Extracted from train_lora.py on 18-Sep-2026 because round 2's headline
#   deliverable is a base-vs-adapter loss comparison, and a comparison is only meaningful if
#   both arms are scored by identical code -- two hand-kept copies of a label mask that drift
#   by one token produce a loss delta that looks like learning and is arithmetic.
#   Chunked CE is REQUIRED, not an optimisation: naive CE over a 27B vocab OOMs at ~20K tokens
#   on a 121 GiB GB10.
# SRP/DRY check: Pass -- this module only encodes and scores. Record selection and the
#   test-set fence stay in extract_sft.py; the corpus->processor message mapping stays in
#   corpus_adapter.py; the optimisation loop stays in train_lora.py.
"""Shared encode + masked chunked-CE path for the ARC-3 LoRA trainer and evaluator."""
from __future__ import annotations

import torch
import torch.nn.functional as F
from torch.utils.checkpoint import checkpoint

from corpus_adapter import adapt

CE_CHUNK = 2048


def build_encoder(proc, cfg):
    """Return `encode(record) -> (batch, n_tokens, n_supervised, n_images)`.

    Labels supervise ONLY assistant-turn content: the span between `<|im_start|>assistant`
    and the matching `<|im_end|>`, header tokens excluded. Image placeholder tokens are then
    masked back out -- they live inside no assistant turn in this corpus, but masking them is
    what makes that a guarantee rather than a property of the current prompt template.
    """
    tok = proc.tokenizer
    IM_START = tok.convert_tokens_to_ids("<|im_start|>")
    IM_END = tok.convert_tokens_to_ids("<|im_end|>")
    ASSIST = tok.encode("assistant", add_special_tokens=False)[0]
    IMG_TOK = cfg.image_token_id

    def encode(rec):
        msgs, imgs = adapt(rec["messages"])
        text = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)
        enc = proc(text=[text], images=imgs if imgs else None, return_tensors="pt")
        i_ids = enc["input_ids"][0]
        labels = torch.full_like(i_ids, -100)
        n_sup, i = 0, 0
        while i < len(i_ids) - 1:
            if i_ids[i] == IM_START and i_ids[i + 1] == ASSIST:
                j = i + 2
                while j < len(i_ids) and i_ids[j] != IM_END:
                    j += 1
                e = min(j + 1, len(i_ids))
                labels[i + 2:e] = i_ids[i + 2:e]
                n_sup += e - (i + 2)
                i = j + 1
            else:
                i += 1
        labels[i_ids == IMG_TOK] = -100
        enc["labels"] = labels.unsqueeze(0)
        return enc, int(i_ids.shape[0]), n_sup, len(imgs)

    return encode


def loss_chunked(h, labels, head_w, head_b=None, *, use_checkpoint: bool = True):
    """Mean CE per supervised token, plus that token count.

    Returns `(loss, n)` where `loss` is the MEAN over supervised tokens. Callers that need a
    token-weighted corpus aggregate must re-multiply by `n` -- averaging the per-record means
    weights a 40-token record the same as a 4,000-token one.

    `use_checkpoint=False` for inference: `torch.utils.checkpoint` under `no_grad` buys
    nothing and the recompute is pure cost.
    """
    hs, labs = h[:-1], labels[0][1:]
    n = int((labs != -100).sum())
    if n == 0:
        raise ValueError("zero supervised tokens")

    def ce_chunk(hc, lc):
        return F.cross_entropy(F.linear(hc, head_w, head_b).float(), lc, reduction="sum")

    loss = hs.new_zeros((), dtype=torch.float32)
    for i in range(0, hs.shape[0], CE_CHUNK):
        hc, lc = hs[i:i + CE_CHUNK], labs[i:i + CE_CHUNK]
        k = lc != -100
        if bool(k.any()):
            if use_checkpoint:
                loss = loss + checkpoint(ce_chunk, hc[k], lc[k], use_reentrant=False)
            else:
                loss = loss + ce_chunk(hc[k], lc[k])
    return loss / n, n
