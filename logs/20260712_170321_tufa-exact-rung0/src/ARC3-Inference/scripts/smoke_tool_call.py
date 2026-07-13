#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from inference.utils.openai_compat import build_chat_payload, build_headers, normalize_provider


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke test OpenAI-compatible tool calling for the Duck Harness."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--provider", default="vllm")
    parser.add_argument("--model", default="auto")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--api-key-file", default="")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--thinking", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def _api_key(args: argparse.Namespace) -> str:
    if args.api_key.strip():
        return args.api_key.strip()
    for env_name in ("LOCAL_ANALYZER_API_KEY", "OPENAI_API_KEY"):
        value = os.environ.get(env_name, "").strip()
        if value:
            return value
    key_path = Path(str(args.api_key_file or "")).expanduser()
    if key_path.is_file():
        return key_path.read_text(encoding="utf-8").splitlines()[0].strip()
    return ""


def _resolve_model(
    *,
    base_url: str,
    provider: str,
    model: str,
    api_key: str,
    timeout: float,
) -> str:
    requested = str(model or "").strip()
    if requested and requested.lower() != "auto":
        return requested
    response = requests.get(
        f"{base_url.rstrip('/')}/models",
        headers=build_headers(provider=provider, api_key=api_key),
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    models = payload.get("data") or []
    if not models:
        raise RuntimeError("server returned no models")
    return str(models[0]["id"])


def _contains_recoverable_markup(message: dict[str, Any]) -> bool:
    fields = [
        message.get("content", ""),
        message.get("reasoning", ""),
        message.get("reasoning_content", ""),
    ]
    return any("<tool_call" in str(field).lower() for field in fields)


def main() -> int:
    args = _parse_args()
    provider = normalize_provider(args.provider)
    api_key = _api_key(args)
    try:
        model = _resolve_model(
            base_url=args.base_url,
            provider=provider,
            model=args.model,
            api_key=api_key,
            timeout=args.timeout,
        )
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "python",
                    "description": "Run one ephemeral Python snippet.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Python code to execute.",
                            }
                        },
                        "required": ["code"],
                    },
                },
            }
        ]
        payload = build_chat_payload(
            provider=provider,
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are testing tool calling. You must call the python tool exactly once.",
                },
                {
                    "role": "user",
                    "content": "Call python with code that sets result = 2 + 2. Do not answer in prose.",
                },
            ],
            max_tokens=256,
            temperature=0.0,
            top_p=1.0,
            top_k=20,
            thinking=bool(args.thinking),
            tools=tools,
            tool_choice="auto",
        )
        response = requests.post(
            f"{args.base_url.rstrip('/')}/chat/completions",
            headers=build_headers(provider=provider, api_key=api_key),
            json=payload,
            timeout=args.timeout,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        print(f"tool smoke failed before response: {exc}", file=sys.stderr)
        return 1

    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        print("tool smoke failed: malformed chat response", file=sys.stderr)
        print(json.dumps(data, indent=2, ensure_ascii=True))
        return 1

    tool_calls = message.get("tool_calls") or []
    if tool_calls:
        print(f"tool smoke passed: parsed {len(tool_calls)} tool call(s)")
        print(json.dumps(tool_calls, indent=2, ensure_ascii=True)[:2000])
        return 0
    if _contains_recoverable_markup(message):
        print("tool smoke passed: no parsed tool_calls, but recoverable <tool_call> markup was emitted")
        print(json.dumps(message, indent=2, ensure_ascii=True)[:2000])
        return 0

    print("tool smoke failed: no parsed tool call or recoverable markup", file=sys.stderr)
    print(json.dumps(message, indent=2, ensure_ascii=True)[:2000])
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
