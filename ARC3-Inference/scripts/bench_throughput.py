"""Measure decode throughput and prefill cost against the local vLLM server.

Reports tokens/sec so serving-config changes (CUDA graphs, prefix caching,
speculative decoding, NVFP4) can be compared against a fixed baseline.
"""

import argparse
import json
import time
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
parser.add_argument("--model", default="Qwen/Qwen3.6-27B-FP8")
parser.add_argument("--api-key-file", default=".cache/arc3_runtime/server-api-key")
parser.add_argument("--label", default="baseline")
parser.add_argument("--decode-tokens", type=int, default=256)
parser.add_argument("--prefill-tokens", type=int, default=4000)
parser.add_argument("--repeat-prefix", action="store_true", help="Send the long prompt twice to expose prefix-cache reuse.")
args = parser.parse_args()

key = ""
key_path = Path(args.api_key_file)
if key_path.is_file():
    key = key_path.read_text().strip().splitlines()[0]


def chat(messages, max_tokens, temperature=0.0):
    payload = {
        "model": args.model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{args.base_url}/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    start = time.monotonic()
    with urllib.request.urlopen(req, timeout=900) as resp:
        data = json.loads(resp.read())
    elapsed = time.monotonic() - start
    usage = data.get("usage", {})
    return elapsed, usage, data["choices"][0]["message"].get("content", "")


print(f"=== {args.label} ===")

# Warm up so we measure steady state, not first-request overhead.
chat([{"role": "user", "content": "Say OK."}], 8)

# Decode: short prompt, long generation -> isolates tokens/sec.
messages = [{"role": "user", "content": "Count from 1 to 200, one number per line. Output only numbers."}]
elapsed, usage, _ = chat(messages, args.decode_tokens)
out = usage.get("completion_tokens", 0)
decode_tps = out / elapsed if elapsed else 0
print(f"DECODE   : {out:4d} tokens in {elapsed:6.2f}s = {decode_tps:6.2f} tok/s")

# Prefill: long prompt, tiny generation -> isolates prompt-processing cost.
filler = "The quick brown fox jumps over the lazy dog. " * (args.prefill_tokens // 9)
long_messages = [{"role": "user", "content": f"{filler}\n\nReply with exactly one word: done."}]
elapsed_p, usage_p, _ = chat(long_messages, 8)
pin = usage_p.get("prompt_tokens", 0)
prefill_tps = pin / elapsed_p if elapsed_p else 0
print(f"PREFILL  : {pin:5d} prompt tokens in {elapsed_p:6.2f}s = {prefill_tps:8.0f} tok/s")

if args.repeat_prefix:
    elapsed_c, usage_c, _ = chat(long_messages, 8)
    cached = usage_c.get("prompt_tokens_details", {}) or {}
    hit = cached.get("cached_tokens", 0)
    speedup = elapsed_p / elapsed_c if elapsed_c else 0
    print(f"PREFILL#2: {usage_c.get('prompt_tokens', 0):5d} prompt tokens in {elapsed_c:6.2f}s "
          f"= {speedup:.2f}x vs first, cached_tokens={hit}")

print(f"SUMMARY  : label={args.label} decode={decode_tps:.2f} tok/s prefill={prefill_tps:.0f} tok/s")
