"""Throughput-scaling bench report (3-Oct-2026, daniel-draft): Daniel-base runs, one row each.

From serve.log (decode / prefill lines over the whole gameplay window): busy slots, decode tok/s, per-slot decode tok/s
(decode tok/s / running requests, per log line), generated tokens per minute (tok/s x interval, so prefill stalls count),
accept len, prompt-cache hit, Mamba usage (mean / max), KV pool usage (mean / max). The window starts at the
first decode with >= 5 requests running (the pre-game checks are excluded).
From working/metrics.jsonl (the bench's /metrics scraper; first-to-last deltas): cached tokens by source (device / host)
and their share of prompt tokens.
  python bench_report.py RUN [RUN ...]
"""
import json
import re
import subprocess
import sys
from datetime import datetime

G = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
B = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs"
TS = re.compile(r"^\[(\S+ \S+)\] (Decode|Prefill) batch")
DEC = re.compile(r"#running-req: (\d+), #full token: \d+, full token usage: ([\d.]+), mamba num: \d+, mamba usage: ([\d.]+), "
                 r"accept len: ([\d.]+).*?gen throughput \(token/s\): ([\d.]+)")
PRE = re.compile(r"#new-token: (\d+), #cached-token: (\d+)")


def cat(url):
    r = subprocess.run(G + ["storage", "cat", url], capture_output=True)
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else ""


def metric_sum(row, *subs):
    return sum(v for k, v in row.items() if all(s in k for s in subs))


def report(run, minutes=None):
    ev = [(datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"), m.group(2), l)
          for l in cat(f"{B}/{run}/working/serve.log").splitlines() for m in [TS.match(l)] if m]
    starts = [t for t, kind, l in ev if kind == "Decode" and (m := DEC.search(l)) and int(m.group(1)) >= 5]
    if not starts:
        return {"run": run, "note": "games never reached 5 running"}
    ev = [e for e in ev if e[0] >= starts[0]]   # gameplay window: pre-game checks (single requests) excluded
    if minutes:
        ev = [e for e in ev if (e[0] - starts[0]).total_seconds() <= minutes * 60]
    dec, gen, prev, new, cached = [], 0.0, None, 0, 0
    for t, kind, l in ev:
        if kind == "Decode":
            m = DEC.search(l)
            if not m:
                continue
            run_, kvu, mu, acc, tps = int(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)), float(m.group(5))
            dec.append((run_, kvu, mu, acc, tps))
            if prev is not None and 0 < (t - prev).total_seconds() <= 10:
                gen += tps * (t - prev).total_seconds()
            prev = t
        else:
            m = PRE.search(l)
            new += int(m.group(1)); cached += int(m.group(2))
    if not dec:
        return {"run": run, "note": "no decode logs"}
    span = (ev[-1][0] - ev[0][0]).total_seconds() / 60
    n = len(dec)
    out = {"run": run, "min": round(span), "busy": sum(d[0] for d in dec) / n,
           "tok_s": sum(d[4] for d in dec) / n, "per_slot": sum(d[4] / max(d[0], 1) for d in dec) / n,
           "gen_per_min": gen / max(span, 1e-9), "accept": sum(d[3] for d in dec) / n,
           "hit": cached / max(1, new + cached), "mamba_mean": sum(d[2] for d in dec) / n, "mamba_max": max(d[2] for d in dec),
           "kv_mean": sum(d[1] for d in dec) / n, "kv_max": max(d[1] for d in dec)}
    rows = [json.loads(l) for l in cat(f"{B}/{run}/working/metrics.jsonl").splitlines() if l.startswith("{")]
    rows = [r for r in rows if "error" not in r]
    if len(rows) >= 2:
        a, b = rows[0], rows[-1]
        dev = metric_sum(b, "cached_tokens_total", 'cache_source="device"') - metric_sum(a, "cached_tokens_total", 'cache_source="device"')
        host = metric_sum(b, "cached_tokens_total", 'cache_source="host"') - metric_sum(a, "cached_tokens_total", 'cache_source="host"')
        prompt = metric_sum(b, "prompt_tokens_total") - metric_sum(a, "prompt_tokens_total")
        out.update(dev_hit=dev / max(prompt, 1), host_hit=host / max(prompt, 1), host_share=host / max(dev + host, 1))
    return out


def main():
    args = sys.argv[1:]
    minutes = None
    if args and args[0].startswith('--minutes='):
        minutes = float(args.pop(0).split('=')[1])
        print(f'matched window: first {minutes:.0f} min of play')
    res = [report(r, minutes) for r in args]
    print(f"{'run':30s} {'min':>4s} {'busy':>5s} {'tok/s':>6s} {'/slot':>6s} {'gen/min':>8s} {'accept':>6s} {'hit':>6s} "
          f"{'gpu':>6s} {'host':>6s} {'mamba':>11s} {'kv pool':>11s}")
    for r in res:
        if "note" in r:
            print(f"{r['run']:30s} {r['note']}"); continue
        print(f"{r['run']:30s} {r['min']:4d} {r['busy']:5.2f} {r['tok_s']:6.0f} {r['per_slot']:6.1f} {r['gen_per_min'] / 1e3:7.1f}k "
              f"{r['accept']:6.3f} {r['hit']:6.1%} {r.get('dev_hit', float('nan')):6.1%} {r.get('host_hit', float('nan')):6.1%} "
              f"{r['mamba_mean']:5.2f}/{r['mamba_max']:4.2f} {r['kv_mean']:5.2f}/{r['kv_max']:4.2f}")


if __name__ == "__main__":
    main()
