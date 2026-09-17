"""
Author: Claude Opus 5 (Bubba subagent, arc3-a424-lora-step)
Date: 16-September-2026
PURPOSE: Adapt emitted SFT records (distill/extract_sft.py) onto the field names Qwen3.5's chat
template actually reads, and decode inline base64 image parts into PIL images. Without this,
`processor.apply_chat_template` on our corpus SILENTLY DROPS every chain of thought: the
extractor emits `reasoning` on assistant messages, `chat_template.jinja` reads
`message.reasoning_content`, and the jinja macro renders '' for a missing field rather than
raising. 56 of the 113 baseline assistant turns carry NO `content` at all (reasoning plus a tool
call and no prose), so those turns render as an empty assistant message and the model is trained
to say nothing. The template also raises outright if `tool_call.arguments` is a JSON string
instead of a mapping.
Verified on gx10-a424 against the real Qwen3VLProcessor for Qwen3.8-27B: a 6-assistant-turn
record renders 6 <think> blocks, the reasoning text is present in the rendered string, and the 5
image parts expand to 320 image tokens (64/frame, matching (256/16)^2/4 for 256x256 frames at
patch_size 16 with spatial merge 2).
SRP/DRY check: Pass — extract_sft.py owns record *emission* and is untouched; this owns the
record -> chat-template seam, which previously lived nowhere and was being re-derived (wrongly)
by each consumer.
"""

from __future__ import annotations

import base64
import io
import json
from typing import Any

__all__ = ["adapt_messages"]


def _fix_tool_calls(message: dict[str, Any]) -> list[dict[str, Any]]:
    """Coerce tool_call.arguments to a mapping.

    The Qwen3.5 template raises 'Tool call arguments ... were passed as a JSON string. Parse them
    into an object before calling apply_chat_template.' rather than coping, so this must happen
    before rendering.
    """
    fixed = []
    for call in message.get("tool_calls") or []:
        call = json.loads(json.dumps(call))  # deep copy; never mutate the caller's record
        fn = call.get("function", call)
        args = fn.get("arguments")
        if isinstance(args, str):
            try:
                fn["arguments"] = json.loads(args) if args.strip() else {}
            except json.JSONDecodeError:
                # Keep the payload rather than dropping the turn; a malformed tool call is worth
                # seeing in the rendered text, not worth an exception mid-corpus.
                fn["arguments"] = {"_unparsed_arguments": args}
        fixed.append(call)
    return fixed


def adapt_messages(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[Any]]:
    """Return (messages_for_apply_chat_template, images_in_template_order).

    Images are returned separately because the template emits a
    '<|vision_start|><|image_pad|><|vision_end|>' placeholder and the processor expands it from
    the images passed alongside `text=`. Order matters: the Nth decoded image must correspond to
    the Nth placeholder, so parts are walked in message order.

    Importing PIL is deferred so text-only callers (token counting, corpus stats) do not need it.
    """
    from PIL import Image

    adapted: list[dict[str, Any]] = []
    images: list[Any] = []

    for message in messages:
        message = dict(message)

        if message["role"] == "assistant":
            # THE bug this module exists for: `reasoning` -> `reasoning_content`.
            if "reasoning" in message:
                message["reasoning_content"] = message.pop("reasoning")
            # `content` is legitimately absent when the turn was reasoning + tool call only;
            # the template concatenates it, so None would render as the string "None".
            if message.get("content") is None:
                message["content"] = ""
            calls = _fix_tool_calls(message)
            if calls:
                message["tool_calls"] = calls

        content = message.get("content")
        if isinstance(content, list):
            parts = []
            for part in content:
                if part.get("type") == "image_url":
                    url = part["image_url"]["url"]
                    payload = url.split(",", 1)[1]
                    images.append(Image.open(io.BytesIO(base64.b64decode(payload))).convert("RGB"))
                    parts.append({"type": "image"})
                else:
                    parts.append(part)
            message["content"] = parts

        adapted.append(message)

    return adapted, images
