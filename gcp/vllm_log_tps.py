#!/usr/bin/env python3
"""Throughput summary from a vLLM server log (no extra load on the box).

vLLM logs a metrics line every ~10 s while requests are running:
  Avg prompt throughput: 1234.5 tokens/s, Avg generation throughput: 67.8 tokens/s,
  Running: 7 reqs, Waiting: 0 reqs, GPU KV cache usage: 1.2%, Prefix cache hit rate: 45.0%
plus, at startup, the real KV pool ("GPU KV cache size: N tokens") and the max concurrency
line. This turns a run's vllm.log into: the KV pool, and per-lane-count distributions of
prompt and generation throughput, so a harness run doubles as a tok/s measurement.

Usage:
  vllm_log_tps.py vllm.log [--json out.json]
  gcloud storage cat gs://.../RUN/vllm.log | vllm_log_tps.py -
"""
import argparse, json, re, statistics, sys
from collections import defaultdict

METRIC = re.compile(
    r"Avg prompt throughput: ([\d.]+) tokens/s, Avg generation throughput: ([\d.]+) tokens/s, "
    r"Running: (\d+) reqs, Waiting: (\d+) reqs, GPU KV cache usage: ([\d.]+)%"
    r"(?:, Prefix cache hit rate: ([\d.]+)%)?")
KV_POOL = re.compile(r"GPU KV cache size: ([\d,]+) tokens")
MAX_CONC = re.compile(r"Maximum concurrency for ([\d,]+) tokens per request: ([\d.]+)x")
MODEL_LOAD = re.compile(r"Model loading took ([\d.]+) GiB (?:memory )?and ([\d.]+) seconds")


def q(xs, p):
    xs = sorted(xs); i = max(0, min(len(xs) - 1, round(p * (len(xs) - 1)))); return xs[i]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log"); ap.add_argument("--json")
    a = ap.parse_args()
    text = sys.stdin.read() if a.log == "-" else open(a.log, encoding="utf-8", errors="replace").read()

    out = {"kv_pool_tokens": None, "max_concurrency": None, "model_load": None, "by_running": {}, "samples": 0}
    m = KV_POOL.search(text)
    if m: out["kv_pool_tokens"] = int(m.group(1).replace(",", ""))
    m = MAX_CONC.search(text)
    if m: out["max_concurrency"] = {"tokens_per_request": int(m.group(1).replace(",", "")), "x": float(m.group(2))}
    m = MODEL_LOAD.search(text)
    if m: out["model_load"] = {"gib": float(m.group(1)), "seconds": float(m.group(2))}

    by = defaultdict(lambda: {"prompt_tps": [], "gen_tps": [], "kv_pct": [], "prefix_hit": [], "waiting": []})
    for mm in METRIC.finditer(text):
        p, g, run, wait, kv, hit = mm.groups()
        run = int(run)
        if run == 0 and float(p) == 0 and float(g) == 0: continue   # idle ticks
        b = by[run]; b["prompt_tps"].append(float(p)); b["gen_tps"].append(float(g)); b["kv_pct"].append(float(kv)); b["waiting"].append(int(wait))
        if hit is not None: b["prefix_hit"].append(float(hit))
        out["samples"] += 1

    for run in sorted(by):
        b = by[run]; g = b["gen_tps"]; p = b["prompt_tps"]
        gen_active = [x for x in g if x > 0]; pr_active = [x for x in p if x > 0]
        out["by_running"][run] = {
            "ticks": len(g),
            "gen_tps_aggregate_median": round(statistics.median(gen_active), 1) if gen_active else None,
            "gen_tps_aggregate_p90": round(q(gen_active, 0.9), 1) if gen_active else None,
            "gen_tps_per_lane_median": round(statistics.median(gen_active) / run, 1) if gen_active and run else None,
            "prompt_tps_median_when_prefilling": round(statistics.median(pr_active), 1) if pr_active else None,
            "prompt_tps_p90": round(q(pr_active, 0.9), 1) if pr_active else None,
            "kv_usage_pct_max": round(max(b["kv_pct"]), 2),
            "prefix_hit_pct_median": round(statistics.median(b["prefix_hit"]), 1) if b["prefix_hit"] else None,
            "waiting_max": max(b["waiting"]),
        }

    if a.json:
        with open(a.json, "w") as f: json.dump(out, f, indent=1)
    kv = out["kv_pool_tokens"]
    print(f"KV pool: {kv:,} tokens" if kv else "KV pool: (not found)", end="")
    if out["max_concurrency"]: print(f"  | max concurrency {out['max_concurrency']['x']}x at {out['max_concurrency']['tokens_per_request']:,} tok/req", end="")
    if out["model_load"]: print(f"  | model load {out['model_load']['gib']} GiB in {out['model_load']['seconds']} s", end="")
    print(f"\n{out['samples']} metric ticks\n")
    print(f"{'lanes':>5} {'ticks':>5} {'gen tok/s agg med':>17} {'p90':>7} {'per-lane':>9} {'prefill tok/s med':>17} {'p90':>8} {'KV% max':>8} {'prefix hit%':>11} {'wait max':>8}")
    for run, r in out["by_running"].items():
        print(f"{run:>5} {r['ticks']:>5} {str(r['gen_tps_aggregate_median']):>17} {str(r['gen_tps_aggregate_p90']):>7} {str(r['gen_tps_per_lane_median']):>9} "
              f"{str(r['prompt_tps_median_when_prefilling']):>17} {str(r['prompt_tps_p90']):>8} {r['kv_usage_pct_max']:>8} {str(r['prefix_hit_pct_median']):>11} {r['waiting_max']:>8}")


if __name__ == "__main__":
    main()
