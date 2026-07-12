"""Aggregate throughput vs concurrency.

Decode on a dense model is memory-bandwidth-bound: a batched step reads all the
weights once for the whole batch. So concurrent sequences should be close to
free, and aggregate tok/s should scale nearly linearly until the GPU becomes
compute-bound. This measures where that knee actually is, which sets how many
games a424 can play at once.
"""

import argparse
import json
import threading
import time
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
parser.add_argument("--model", default="Qwen/Qwen3.6-27B-FP8")
parser.add_argument("--api-key-file", default=".cache/arc3_runtime/server-api-key")
parser.add_argument("--levels", default="1,4,8,16,25")
parser.add_argument("--tokens", type=int, default=128)
args = parser.parse_args()

key = ""
p = Path(args.api_key_file)
if p.is_file():
    key = p.read_text().strip().splitlines()[0]


def one_request(idx, results):
    payload = {
        "model": args.model,
        # Vary the prompt per slot so they don't all share a prefix and skew the test.
        "messages": [{"role": "user", "content": f"Slot {idx}. Write a short paragraph about grid puzzles, then count from 1 to 60."}],
        "max_tokens": args.tokens,
        "temperature": 0.7,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(
        f"{args.base_url}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            data = json.loads(resp.read())
        results[idx] = data["usage"]["completion_tokens"]
    except Exception as exc:  # noqa: BLE001
        results[idx] = 0
        print(f"  slot {idx} failed: {exc}")


print(f"{'concurrency':>12} {'wall':>8} {'total tok':>10} {'aggregate':>12} {'per-stream':>12}")
print("-" * 60)
base_per_stream = None
for level in [int(x) for x in args.levels.split(",")]:
    results = {}
    threads = [threading.Thread(target=one_request, args=(i, results)) for i in range(level)]
    start = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.monotonic() - start
    total = sum(results.values())
    aggregate = total / elapsed if elapsed else 0
    per_stream = aggregate / level if level else 0
    if base_per_stream is None:
        base_per_stream = per_stream
    retained = 100 * per_stream / base_per_stream if base_per_stream else 0
    print(f"{level:>12} {elapsed:>7.1f}s {total:>10} {aggregate:>9.1f} t/s {per_stream:>7.1f} t/s  ({retained:.0f}% of solo)")
