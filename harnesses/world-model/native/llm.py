"""Minimal OpenAI-compatible chat client for the world-model harness.

Talks to any `/v1/chat/completions` endpoint via env config -- Ollama for local
dev (`gpt-oss:20b`) or our Qwen3.6-27B on vLLM for the real run. No codex, no
Responses API, so none of the codex<->vLLM dialect incompatibilities apply: this
is plain chat-completions with tool-free text, which every server supports.

    WM_LLM_BASE_URL  default http://localhost:11434/v1   (Ollama)
    WM_LLM_MODEL     default gpt-oss:20b
    WM_LLM_API_KEY   default "x" (ignored by local servers)
"""
from __future__ import annotations

import json
import os
import urllib.request

BASE_URL = os.environ.get("WM_LLM_BASE_URL", "http://localhost:11434/v1")
MODEL = os.environ.get("WM_LLM_MODEL", "gpt-oss:20b")
API_KEY = os.environ.get("WM_LLM_API_KEY", "x")


def chat(messages, temperature: float = 0.2, max_tokens: int = 8192,
         model: str | None = None, timeout: int = 900) -> str:
    body = json.dumps({
        "model": model or MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        BASE_URL.rstrip("/") + "/chat/completions",
        data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {API_KEY}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"]


def extract_code(text: str) -> str:
    """Pull the first ```python ...``` block (the synthesized model), else the
    largest fenced block, else the raw text."""
    import re
    blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    if blocks:
        return max(blocks, key=len).strip()
    return text.strip()
