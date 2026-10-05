"""Per-run token totals for every saved Daniel-stack run (4-Oct-2026, replay data prep; runs on the prep VM).

  python3 run_stats.py OUT.json

For each gs://.../daniel-base/runs/<run>/: summary.txt (duration, generated tokens, games), the last metrics.jsonl
row (server prompt / cached / generated token totals, requests), and the request-log count/size. Uncached prompt
tokens = what a replay would have to prefill (roughly), generated tokens = the training rows it could yield.
"""
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

B = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs"


def sh(args):
    return subprocess.run(args, capture_output=True, text=True).stdout


runs = [l.rstrip("/").rsplit("/", 1)[-1] for l in sh(["gcloud", "storage", "ls", B + "/"]).split() if l.strip()]


def one(run):
    out = {"run": run}
    s = sh(["gcloud", "storage", "cat", f"{B}/{run}/working/summary.txt"])
    m = re.search(r"duration:\s+(\d+)h (\d+)m", s)
    out["minutes"] = int(m.group(1)) * 60 + int(m.group(2)) if m else None
    m = re.search(r"total tokens:\s+(\d+)", s)
    out["gen_tokens_summary"] = int(m.group(1)) if m else None
    m = re.search(r"mean score:\s+([\d.]+)", s)
    out["score"] = float(m.group(1)) if m else None
    out["games"] = re.findall(r"^\s+([a-z0-9]{4}-[0-9a-f]{8}): score", s, re.M)
    lines = [l for l in sh(["gcloud", "storage", "cat", f"{B}/{run}/working/metrics.jsonl"]).splitlines() if l.strip()]
    for l in reversed(lines):
        try:
            d = json.loads(l)
        except ValueError:
            continue
        if "error" in d:
            continue
        tot = lambda key: sum(v for k, v in d.items() if k.startswith(key))  # noqa: E731
        out.update(prompt=tot("sglang:prompt_tokens_total"), cached=tot("sglang:cached_tokens_total"),
                   generated=tot("sglang:generation_tokens_total"), requests=tot("sglang:num_requests_total"))
        break
    ls = sh(["gcloud", "storage", "ls", "-l", f"{B}/{run}/working/*_p0_requests.jsonl"])
    sizes = [int(l.split()[0]) for l in ls.splitlines() if l.strip().endswith("_p0_requests.jsonl")]
    out["req_logs"], out["req_log_gb"] = len(sizes), round(sum(sizes) / 2 ** 30, 2)
    return out


with ThreadPoolExecutor(24) as ex:
    res = list(ex.map(one, runs))
json.dump(res, open(sys.argv[1], "w"), indent=0)
print(len(res), "runs")
