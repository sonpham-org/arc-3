"""Throughput at the ARC harness's shape, against any OpenAI-compatible server.

Phases (each records per-request usage incl. prompt_tokens_details.cached_tokens when the server reports it):
  warm      C distinct prompts of P tokens, max_tokens 1                -> cold prefill tok/s, TTFT
  cached    the same prompts + 256 new tokens, max_tokens 256          -> cached TTFT, cached_tokens, per-stream decode
  decode    the same prompts, max_tokens N (ignore_eos)                -> sustained aggregate + per-stream decode tok/s
  grow      each prompt + 2,000 new tokens, max_tokens 64              -> multi-turn prefix reuse (TTFT, cached_tokens)
usage: python bench_shape.py --base-url http://127.0.0.1:8001/v1 --model pennyroyal --out results.json \
         --shapes 7x50000,7x100000,4x50000,1x50000 --decode-tokens 2000
"""
from __future__ import annotations

import argparse, json, random, statistics, threading, time, urllib.request

WORDS = ("grid cell row column colour red blue green move left right up down target wall box key door lever switch "
         "pattern repeat count total plan check verify action result frame level score step object shape line "
         "corner edge center mirror rotate shift copy paste fill clear compare before after").split()


def make_prompt(seed: int, approx_tokens: int) -> str:
    rnd = random.Random(seed)
    n_words = int(approx_tokens * 0.78)          # ~1.28 tokens per word on this tokenizer for this vocabulary
    return f"Session {seed}. " + " ".join(rnd.choice(WORDS) for _ in range(n_words))


def request(base, model, prompt, max_tokens, temperature=1.0, ignore_eos=False, timeout=1800):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens,
            "temperature": temperature, "top_p": 0.95, "top_k": 20, "stream": True,
            "stream_options": {"include_usage": True}, "chat_template_kwargs": {"enable_thinking": True}}
    if ignore_eos:
        body["ignore_eos"] = True
    req = urllib.request.Request(f"{base.rstrip('/')}/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time(); first = None; n = 0; usage = None
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if chunk.get("usage"):
                usage = chunk["usage"]
            for ch in chunk.get("choices") or []:
                d = ch.get("delta") or {}
                if d.get("content") or d.get("reasoning_content") or d.get("reasoning"):
                    if first is None:
                        first = time.time()
                    n += 1
    end = time.time()
    usage = usage or {}
    comp = usage.get("completion_tokens") or n
    cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
    return {"ttft_s": round((first or end) - t0, 3), "total_s": round(end - t0, 3), "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": comp, "cached_tokens": cached,
            "decode_tok_s": round((comp - 1) / (end - first), 2) if first and comp > 1 and end > first else None}


def run_phase(base, model, prompts, max_tokens, ignore_eos=False):
    out = [None] * len(prompts)
    def worker(i):
        try:
            out[i] = request(base, model, prompts[i], max_tokens, ignore_eos=ignore_eos)
        except Exception as exc:  # noqa: BLE001
            out[i] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    t0 = time.time()
    ths = [threading.Thread(target=worker, args=(i,)) for i in range(len(prompts))]
    [t.start() for t in ths]; [t.join() for t in ths]
    wall = time.time() - t0
    ok = [r for r in out if r and "error" not in r]
    agg = round(sum(max(0, r["completion_tokens"] - 1) for r in ok) / wall, 2) if ok else 0
    return {"wall_s": round(wall, 2), "n_ok": len(ok), "n": len(prompts), "aggregate_decode_tok_s": agg,
            "ttft_s_median": round(statistics.median([r["ttft_s"] for r in ok]), 3) if ok else None,
            "per_stream_decode_tok_s": [r["decode_tok_s"] for r in ok],
            "prompt_tokens": [r["prompt_tokens"] for r in ok], "cached_tokens": [r["cached_tokens"] for r in ok],
            "completion_tokens": [r["completion_tokens"] for r in ok],
            "prefill_tok_s_est": round(sum((r["prompt_tokens"] or 0) - (r["cached_tokens"] or 0) for r in ok) / wall, 1) if ok else None,
            "errors": [r["error"] for r in out if r and "error" in r]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8001/v1"); ap.add_argument("--model", default="pennyroyal")
    ap.add_argument("--out", required=True); ap.add_argument("--shapes", default="7x50000,7x100000,4x50000,1x50000")
    ap.add_argument("--decode-tokens", type=int, default=2000); ap.add_argument("--label", default="")
    a = ap.parse_args()
    results = {"label": a.label, "base_url": a.base_url, "model": a.model, "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "shapes": {}}
    print("warmup", request(a.base_url, a.model, make_prompt(999, 2000), 64))
    for shape in a.shapes.split(","):
        c, p = (int(x) for x in shape.split("x"))
        prompts = [make_prompt(1000 * (i + 1) + p, p) for i in range(c)]
        rec = {"concurrency": c, "prompt_tokens_target": p}
        rec["warm"] = run_phase(a.base_url, a.model, prompts, 1)
        print(shape, "warm", json.dumps({k: rec["warm"][k] for k in ("wall_s", "n_ok", "ttft_s_median", "prompt_tokens", "cached_tokens", "prefill_tok_s_est")}), flush=True)
        tail = [pr + " " + make_prompt(7 + i, 256)[13:] for i, pr in enumerate(prompts)]
        rec["cached"] = run_phase(a.base_url, a.model, tail, 256, ignore_eos=True)
        print(shape, "cached", json.dumps({k: rec["cached"][k] for k in ("wall_s", "n_ok", "ttft_s_median", "cached_tokens", "aggregate_decode_tok_s", "per_stream_decode_tok_s")}), flush=True)
        rec["decode"] = run_phase(a.base_url, a.model, tail, a.decode_tokens, ignore_eos=True)
        print(shape, "decode", json.dumps({k: rec["decode"][k] for k in ("wall_s", "n_ok", "ttft_s_median", "cached_tokens", "aggregate_decode_tok_s", "per_stream_decode_tok_s", "errors")}), flush=True)
        grown = [t + " " + make_prompt(70 + i, 2000)[13:] for i, t in enumerate(tail)]
        rec["grow"] = run_phase(a.base_url, a.model, grown, 64, ignore_eos=True)
        print(shape, "grow", json.dumps({k: rec["grow"][k] for k in ("wall_s", "n_ok", "ttft_s_median", "cached_tokens", "prompt_tokens")}), flush=True)
        results["shapes"][shape] = rec
        json.dump(results, open(a.out, "w"), indent=1)
    results["ended"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(results, open(a.out, "w"), indent=1)
    print("done", a.out)


if __name__ == "__main__":
    main()
