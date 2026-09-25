"""Games-over-slots benchmark: N harness-like games share a server that admits S decode slots.

Each game runs T turns. A turn = re-send its growing context (+~2k new tokens, so the prefix must come back from the
radix cache or host RAM) and generate G tokens (ignore_eos), then "sandbox" sleep. Reports aggregate generated tok/s
over the whole run, per-turn latency (queue + prefill + decode), cached_tokens per turn (prefix reuse), and TTFT.
The server's --max-running-requests is the slot count; run this with N > S to measure parking/queueing.
usage: python bench_slots.py --base-url ... --model pennyroyal --games 9 --turns 6 --start-tokens 30000 --grow 2000 --gen 1500 --sandbox 3 --out slots.json
"""
from __future__ import annotations

import argparse, json, random, statistics, threading, time, urllib.request

WORDS = ("grid cell row column colour red blue green move left right up down target wall box key door lever switch "
         "pattern repeat count total plan check verify action result frame level score step object shape line "
         "corner edge center mirror rotate shift copy paste fill clear compare before after").split()


def words(seed: int, approx_tokens: int) -> str:
    rnd = random.Random(seed)
    return " ".join(rnd.choice(WORDS) for _ in range(int(approx_tokens * 0.78)))


def request(base, model, prompt, max_tokens, timeout=3600):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens, "temperature": 1.0,
            "top_p": 0.95, "top_k": 20, "stream": True, "stream_options": {"include_usage": True}, "ignore_eos": True,
            "chat_template_kwargs": {"enable_thinking": True}}
    req = urllib.request.Request(f"{base.rstrip('/')}/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time(); first = None; usage = None
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data: ") or line[6:] == "[DONE]":
                continue
            try:
                chunk = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            if chunk.get("usage"):
                usage = chunk["usage"]
            for ch in chunk.get("choices") or []:
                d = ch.get("delta") or {}
                if first is None and (d.get("content") or d.get("reasoning_content") or d.get("reasoning")):
                    first = time.time()
    end = time.time(); usage = usage or {}
    return {"ttft_s": round((first or end) - t0, 3), "total_s": round(end - t0, 3), "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"), "cached_tokens": (usage.get("prompt_tokens_details") or {}).get("cached_tokens")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8001/v1"); ap.add_argument("--model", default="pennyroyal")
    ap.add_argument("--games", type=int, default=9); ap.add_argument("--turns", type=int, default=6)
    ap.add_argument("--start-tokens", type=int, default=30000); ap.add_argument("--grow", type=int, default=2000)
    ap.add_argument("--gen", type=int, default=1500); ap.add_argument("--sandbox", type=float, default=3.0)
    ap.add_argument("--out", required=True); ap.add_argument("--label", default="")
    a = ap.parse_args()
    turns_log = [[] for _ in range(a.games)]

    def game(i):
        ctx = f"Game {i}. " + words(100 + i, a.start_tokens)
        for t in range(a.turns):
            ctx += " " + words(1000 * i + t, a.grow)
            try:
                r = request(a.base_url, a.model, ctx, a.gen)
            except Exception as exc:  # noqa: BLE001
                r = {"error": f"{type(exc).__name__}: {str(exc)[:160]}"}
            r["turn"] = t; r["t_end"] = time.time()
            turns_log[i].append(r)
            time.sleep(a.sandbox)

    t0 = time.time()
    ths = [threading.Thread(target=game, args=(i,)) for i in range(a.games)]
    [t.start() for t in ths]; [t.join() for t in ths]
    wall = time.time() - t0
    ok = [r for g in turns_log for r in g if "error" not in r]
    gen = sum(r["completion_tokens"] or 0 for r in ok)
    res = {"label": a.label, "games": a.games, "turns": a.turns, "start_tokens": a.start_tokens, "grow": a.grow, "gen": a.gen, "sandbox_s": a.sandbox,
           "wall_s": round(wall, 1), "turns_ok": len(ok), "turns_total": a.games * a.turns, "generated_tokens": gen,
           "aggregate_gen_tok_s": round(gen / wall, 1), "turn_latency_s_median": round(statistics.median([r["total_s"] for r in ok]), 2) if ok else None,
           "turn_latency_s_p90": round(sorted(r["total_s"] for r in ok)[int(0.9 * len(ok)) - 1], 2) if ok else None,
           "ttft_s_median": round(statistics.median([r["ttft_s"] for r in ok]), 2) if ok else None,
           "cached_fraction_median": round(statistics.median([(r["cached_tokens"] or 0) / r["prompt_tokens"] for r in ok if r.get("prompt_tokens")]), 3) if ok else None,
           "errors": [r["error"] for g in turns_log for r in g if "error" in r][:10], "per_game": turns_log}
    json.dump(res, open(a.out, "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "per_game"}, indent=1))


if __name__ == "__main__":
    main()
