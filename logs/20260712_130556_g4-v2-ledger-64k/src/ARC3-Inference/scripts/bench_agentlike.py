"""Throughput on an agent-shaped workload.

The duck harness re-emits near-identical Python against a long, mostly-stable
context every turn. n-gram speculative decoding drafts from tokens already in
the context, so a synthetic "count to 200" prompt tells us nothing. This
reproduces the real shape: a long prior turn in-context, and a request to emit
a lightly edited version of the code it already contains.
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
parser.add_argument("--label", default="agentlike")
args = parser.parse_args()

key = ""
p = Path(args.api_key_file)
if p.is_file():
    key = p.read_text().strip().splitlines()[0]

PRIOR_CODE = '''
def analyze_board():
    segs = current_frame.segmentation
    nodes = segs["nodes"]
    by_color = {}
    for node in nodes:
        by_color.setdefault(node["color"], []).append(node)
    movable = [n for n in nodes if n["pixels"] < 32 and n["color"] not in ("B", "W")]
    goal = [n for n in nodes if n["color"] == "Y"]
    print("colors:", sorted(by_color))
    print("movable count:", len(movable))
    print("goal count:", len(goal))
    for node in movable[:6]:
        print("movable", node["id"], node["color"], node["pixels"], node["boundary"])
    for node in goal[:6]:
        print("goal", node["id"], node["color"], node["pixels"], node["boundary"])
    return movable, goal

movable, goal = analyze_board()
'''.strip()

messages = [
    {
        "role": "system",
        "content": "You are a coding agent solving a grid-based puzzle game. Your only tool is `python`.",
    },
    {
        "role": "user",
        "content": (
            "Here is the code you ran on the previous turn:\n\n```python\n"
            + PRIOR_CODE
            + "\n```\n\nIt printed the segmentation summary. Now re-run the SAME analysis, "
            "changing only the pixel threshold from 32 to 24 and the goal color from 'Y' to 'R'. "
            "Output the complete updated function verbatim in a ```python code block, changing nothing else."
        ),
    },
]

payload = {
    "model": args.model,
    "messages": messages,
    "max_tokens": 400,
    "temperature": 0.0,
    "chat_template_kwargs": {"enable_thinking": False},
}
req = urllib.request.Request(
    f"{args.base_url}/chat/completions",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
)

# Warm the prefix cache the way a real turn would be warmed.
urllib.request.urlopen(req, timeout=600).read()

start = time.monotonic()
with urllib.request.urlopen(req, timeout=600) as resp:
    data = json.loads(resp.read())
elapsed = time.monotonic() - start

usage = data["usage"]
out = usage.get("completion_tokens", 0)
content = data["choices"][0]["message"].get("content", "")
tps = out / elapsed if elapsed else 0

print(f"=== {args.label} (agent-shaped: regenerate near-identical code) ===")
print(f"prompt tokens    : {usage.get('prompt_tokens', 0)}")
print(f"generated tokens : {out}")
print(f"elapsed          : {elapsed:.2f}s")
print(f"DECODE           : {tps:.2f} tok/s")
print(f"echoed the edits : {'24' in content and 'R' in content}")
