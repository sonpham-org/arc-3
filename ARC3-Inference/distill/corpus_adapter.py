#!/usr/bin/env python3
# Author: Claude Opus 5 (Bubba)
# Date: 17-September-2026
# PURPOSE: The corpus->processor seam for Qwen3.8-27B (transformers class qwen3_5). Maps the
#   field names `extract_sft.py` emits onto what the Qwen3.5 chat template actually reads, and
#   decodes the inline base64 PNGs into PIL images in template order. Consumed by
#   `distill/train_lora.py` and by the a424 measurement/gradient-census probes. Extracted here
#   because three separate scripts had grown their own copy of this mapping, and the two
#   mismatches it handles are SILENT when unhandled -- they do not raise, they train on
#   truncated data.
# SRP/DRY check: Pass -- this module only adapts records to processor inputs. Image rendering
#   stays in vision_context, message reconstruction stays in traces.py, record selection stays
#   in extract_sft.py. Lifted verbatim from the proven a424 probe (`prep_probe.py`, 16-Sep-2026)
#   rather than rewritten, so the behaviour that produced the 208/208 gradient census is
#   preserved exactly.
"""Adapt extractor SFT records into Qwen3.5 processor inputs."""
from __future__ import annotations

import base64
import io
import json
from typing import Any

from PIL import Image


def adapt(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[Image.Image]]:
    """Map extractor field names onto what the Qwen3.5 chat template actually reads.

    Two mismatches, both silent if unhandled:
      * the extractor emits `reasoning`; the template reads `reasoning_content` and would
        otherwise drop every chain of thought. Many assistant turns have NO `content` at all
        and would render empty.
      * the template raises if tool_call.arguments is a JSON string; it demands a mapping.

    Returns (messages_for_template, PIL images in template order).
    """
    out: list[dict[str, Any]] = []
    imgs: list[Image.Image] = []
    for m in messages:
        m = dict(m)
        if m["role"] == "assistant":
            if "reasoning" in m:
                m["reasoning_content"] = m.pop("reasoning")
            m.setdefault("content", "")
            if m.get("content") is None:
                m["content"] = ""
            tcs = []
            for tc in (m.get("tool_calls") or []):
                tc = json.loads(json.dumps(tc))
                fn = tc.get("function", tc)
                a = fn.get("arguments")
                if isinstance(a, str):
                    try:
                        fn["arguments"] = json.loads(a) if a.strip() else {}
                    except json.JSONDecodeError:
                        fn["arguments"] = {"_raw": a}
                tcs.append(tc)
            if tcs:
                m["tool_calls"] = tcs
        c = m.get("content")
        if isinstance(c, list):
            parts = []
            for p in c:
                if p.get("type") == "image_url":
                    url = p["image_url"]["url"]
                    b64 = url.split(",", 1)[1]
                    imgs.append(Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB"))
                    parts.append({"type": "image"})
                else:
                    parts.append(p)
            m["content"] = parts
        out.append(m)
    return out, imgs
