#!/usr/bin/env python3
"""Pinned two-stage Flash-Next warmup used before the ARC3 harness starts."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import time
import urllib.request
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--model", default="RadixArk/Qwen3.8-Flash-Next-NVFP4")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    endpoint = args.base_url.rstrip("/") + "/chat/completions"

    def call(messages: list[dict[str, str]], tokens: int) -> dict:
        payload = {
            "model": args.model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": tokens,
            "min_tokens": tokens,
            "chat_template_kwargs": {
                "enable_thinking": False,
                "preserve_thinking": True,
            },
        }
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.monotonic()
        with urllib.request.urlopen(request, timeout=900) as response:
            result = json.loads(response.read().decode("utf-8"))
        message = result["choices"][0].get("message") or {}
        content = str(message.get("content") or message.get("reasoning_content") or "")
        completion_tokens = int((result.get("usage") or {}).get("completion_tokens") or 0)
        if not content or completion_tokens < tokens:
            raise RuntimeError(
                f"warmup returned {completion_tokens}/{tokens} tokens"
            )
        return {
            "seconds": time.monotonic() - started,
            "completion_tokens": completion_tokens,
            "content": content,
        }

    seed = "grid observation action hypothesis " * 256

    def decode_lane(index: int) -> dict:
        return call(
            [
                {"role": "system", "content": "ARC3 decode warmup; continue until the token budget is exhausted."},
                {"role": "user", "content": f"Lane {index}. {seed}"},
            ],
            512,
        )

    stage_one_started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=22) as pool:
        stage_one = list(pool.map(decode_lane, range(22)))
    stage_one_seconds = time.monotonic() - stage_one_started

    def growing_lane(index: int) -> dict:
        prior = stage_one[index % len(stage_one)]["content"]
        return call(
            [
                {"role": "system", "content": "ARC3 growing-turn warmup; continue until the token budget is exhausted."},
                {"role": "user", "content": f"Initial game turn for stream {index}. {seed}"},
                {"role": "assistant", "content": prior},
                {"role": "user", "content": "The state changed. Extend and revise the hypothesis for the next turn."},
            ],
            384,
        )

    def continuous_curator() -> dict:
        return call(
            [
                {"role": "system", "content": "Continuously curate cross-game ARC3 hypotheses until the token budget is exhausted."},
                {"role": "user", "content": seed * 2},
            ],
            384,
        )

    stage_two_started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=26) as pool:
        lane_futures = [pool.submit(growing_lane, index) for index in range(25)]
        curator_future = pool.submit(continuous_curator)
        stage_two = [future.result() for future in lane_futures]
        curator = curator_future.result()
    stage_two_seconds = time.monotonic() - stage_two_started

    summary = {
        "stage_one": {
            "streams": 22,
            "tokens_per_stream": 512,
            "wall_seconds": stage_one_seconds,
            "completion_tokens": sum(item["completion_tokens"] for item in stage_one),
        },
        "stage_two": {
            "streams": 25,
            "tokens_per_stream": 384,
            "growing_turn": True,
            "continuous_curator": True,
            "wall_seconds": stage_two_seconds,
            "completion_tokens": sum(item["completion_tokens"] for item in stage_two),
            "curator_completion_tokens": curator["completion_tokens"],
        },
    }
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
