#!/usr/bin/env python3
"""Throughput probe for a vLLM OpenAI endpoint under ARC3-shaped load.

Fires N concurrent "lanes" of chat completions whose prompts look like the harness's:
a system preamble, K ASCII 64x64 frames, a tool schema, and a short instruction. Prompt
sizes are calibrated against the server's own /tokenize so the reported numbers are in
the served model's tokens, not a stand-in tokenizer. Streaming is used so time-to-first-
token (prefill) and decode rate are measured separately, which is what decides how many
moves a game gets inside the wall clock (HARNESS-NOTES §1.7).

Usage:
  arc3_tps_probe.py --model ID [--url http://127.0.0.1:1234] [--lanes 7]
                    [--prompt-tokens 12000,48000,90000] [--rounds 2] [--max-tokens 1500]
                    [--out /opt/arc3/tps]
Writes <out>/requests.csv (one row per request) and <out>/summary.json.
"""
import argparse, asyncio, json, os, random, statistics, time, urllib.request

COLORS = "WwgGcBMPRbSYOrNp"
SYSTEM = (
    "You are an agent playing an ARC-AGI-3 interactive game. Each turn you see the current "
    "64x64 frame as ASCII letters (W=white, w=light gray, g=gray, G=dark gray, c=charcoal, "
    "B=black, M=magenta, P=pink, R=red, b=blue, S=sky blue, Y=yellow, O=orange, r=dark red, "
    "N=light green, p=purple). Maintain a world_model ledger of what each action does, cite "
    "frame evidence for every claim, and choose exactly one action by calling the tool.\n"
)
TOOLS = [{
    "type": "function",
    "function": {
        "name": "take_action",
        "description": "Take one game action.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["ACTION1", "ACTION2", "ACTION3", "ACTION4", "ACTION5", "ACTION6", "RESET"]},
                "x": {"type": "integer"}, "y": {"type": "integer"},
                "expected_observation": {"type": "string"},
                "world_model": {"type": "string"},
            },
            "required": ["action", "expected_observation", "world_model"],
        },
    },
}]


def frame(rng, step):
    # Mostly-uniform background with a few colored blocks; realistic entropy for the tokenizer.
    bg = rng.choice("BwG")
    rows = []
    for r in range(64):
        row = [bg] * 64
        for _ in range(3):
            c0 = rng.randrange(0, 56); w = rng.randrange(2, 9); col = rng.choice(COLORS)
            for c in range(c0, c0 + w):
                row[c] = col
        rows.append("".join(row))
    return f"--- frame {step} (score 0, level 1) ---\n" + "\n".join(rows) + "\n"


def build_messages(rng, n_frames):
    history = [{"role": "system", "content": SYSTEM}]
    for i in range(n_frames):
        history.append({"role": "user", "content": frame(rng, i)})
        if i < n_frames - 1:
            history.append({"role": "assistant", "content":
                f"Ledger: ACTION{(i % 4) + 1} moved the object; evidence rows {rng.randrange(60)}-{rng.randrange(60)}. "
                f"Trying ACTION{(i % 4) + 2 if i % 4 < 3 else 1} next."})
    history.append({"role": "user", "content": "Update the ledger and take exactly one action."})
    return history


def count_tokens(url, model, messages):
    body = json.dumps({"model": model, "messages": messages, "add_generation_prompt": True}).encode()
    req = urllib.request.Request(f"{url}/tokenize", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["count"]


def calibrate(url, model, target):
    """Find the frame count whose prompt is closest to `target` tokens."""
    rng = random.Random(0)
    per_frame = count_tokens(url, model, build_messages(rng, 4)) - count_tokens(url, model, build_messages(rng, 2))
    per_frame = max(per_frame // 2, 1)
    n = max(1, target // per_frame)
    msgs = build_messages(random.Random(1), n)
    return n, count_tokens(url, model, msgs)


async def one_request(session_id, url, model, messages, max_tokens, sampling):
    import aiohttp
    body = {"model": model, "messages": messages, "tools": TOOLS, "tool_choice": "auto",
            "max_tokens": max_tokens, "stream": True, "stream_options": {"include_usage": True}, **sampling}
    t0 = time.perf_counter(); t_first = None; n_chunks = 0; usage = {}; finish = None
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3600)) as s:
        async with s.post(f"{url}/v1/chat/completions", json=body) as resp:
            if resp.status != 200:
                return {"lane": session_id, "error": f"HTTP {resp.status}: {(await resp.text())[:200]}"}
            async for raw in resp.content:
                line = raw.decode().strip()
                if not line.startswith("data:"): continue
                payload = line[5:].strip()
                if payload == "[DONE]": break
                d = json.loads(payload)
                if d.get("usage"): usage = d["usage"]
                for ch in d.get("choices", []):
                    delta = ch.get("delta", {})
                    if delta.get("content") or delta.get("reasoning_content") or delta.get("reasoning") or delta.get("tool_calls"):
                        if t_first is None: t_first = time.perf_counter()
                        n_chunks += 1
                    if ch.get("finish_reason"): finish = ch["finish_reason"]
    t_end = time.perf_counter()
    pt = usage.get("prompt_tokens", 0); ct = usage.get("completion_tokens", 0)
    ttft = (t_first or t_end) - t0; decode_s = t_end - (t_first or t_end)
    return {"lane": session_id, "prompt_tokens": pt, "completion_tokens": ct, "ttft_s": round(ttft, 3),
            "decode_s": round(decode_s, 3), "total_s": round(t_end - t0, 3),
            "prefill_tps": round(pt / ttft, 1) if ttft > 0 else None,
            "decode_tps": round(ct / decode_s, 1) if decode_s > 0 and ct else None,
            "finish_reason": finish, "chunks": n_chunks}


async def run_wave(url, model, lanes, messages_by_lane, max_tokens, sampling):
    return await asyncio.gather(*[one_request(i, url, model, messages_by_lane[i], max_tokens, sampling) for i in range(lanes)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:1234")
    ap.add_argument("--model", required=True)
    ap.add_argument("--lanes", type=int, default=7)
    ap.add_argument("--prompt-tokens", default="12000,48000,90000")
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--max-tokens", type=int, default=1500)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--top-p", type=float, default=0.95)
    ap.add_argument("--out", default="/opt/arc3/tps")
    ap.add_argument("--warm", type=int, default=1, help="also run a warm-prefix wave after each cold one")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    sampling = {"temperature": a.temperature, "top_p": a.top_p}
    targets = [int(x) for x in a.prompt_tokens.split(",")]

    rows = []; summary = {"model": a.model, "lanes": a.lanes, "max_tokens": a.max_tokens, "waves": []}
    for target in targets:
        n_frames, actual = calibrate(a.url, a.model, target)
        print(f"[calibrate] target={target} -> {n_frames} frames = {actual} tokens", flush=True)
        for rnd in range(a.rounds):
            # cold: distinct prompts per lane (no prefix-cache help). warm: same prefix + one new
            # frame, which is what a real mid-game turn costs once the conversation is cached.
            msgs = [build_messages(random.Random(1000 * rnd + i), n_frames) for i in range(a.lanes)]
            for phase in (["cold", "warm"] if a.warm else ["cold"]):
                if phase == "warm":
                    msgs = [m[:-1] + [{"role": "assistant", "content": "Ledger updated. Taking ACTION3."},
                                      {"role": "user", "content": frame(random.Random(77 + i), 999) + m[-1]["content"]}]
                            for i, m in enumerate(msgs)]   # frame + instruction in one user turn: no consecutive same-role messages
                t0 = time.perf_counter()
                res = asyncio.run(run_wave(a.url, a.model, a.lanes, msgs, a.max_tokens, sampling))
                wall = time.perf_counter() - t0
                ok = [r for r in res if "error" not in r]
                for r in res:
                    r.update({"target_prompt_tokens": target, "round": rnd, "phase": phase}); rows.append(r)
                agg_ct = sum(r["completion_tokens"] for r in ok); agg_pt = sum(r["prompt_tokens"] for r in ok)
                dec = [r["decode_tps"] for r in ok if r["decode_tps"]]
                wave = {
                    "target_prompt_tokens": target, "round": rnd, "phase": phase, "ok": len(ok), "errors": len(res) - len(ok),
                    "wall_s": round(wall, 1),
                    "ttft_s_median": round(statistics.median(r["ttft_s"] for r in ok), 2) if ok else None,
                    "ttft_s_max": round(max(r["ttft_s"] for r in ok), 2) if ok else None,
                    "per_lane_decode_tps_median": round(statistics.median(dec), 1) if dec else None,
                    "aggregate_decode_tps": round(agg_ct / max(r["total_s"] for r in ok), 1) if ok else None,
                    "aggregate_prompt_tps": round(agg_pt / wall, 1) if ok else None,
                    "request_s_median": round(statistics.median(r["total_s"] for r in ok), 1) if ok else None,
                    "finish_reasons": sorted({str(r["finish_reason"]) for r in ok}),
                }
                summary["waves"].append(wave)
                print(f"[wave] {json.dumps(wave)}", flush=True)
                for r in res:
                    if "error" in r: print(f"[error] lane {r['lane']}: {r['error']}", flush=True)

    with open(os.path.join(a.out, "requests.csv"), "w") as f:
        keys = ["target_prompt_tokens", "round", "phase", "lane", "prompt_tokens", "completion_tokens", "ttft_s", "decode_s", "total_s", "prefill_tps", "decode_tps", "finish_reason", "chunks", "error"]
        f.write(",".join(keys) + "\n")
        for r in rows: f.write(",".join(str(r.get(k, "")) for k in keys) + "\n")
    with open(os.path.join(a.out, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    print(f"[done] wrote {a.out}/summary.json and requests.csv", flush=True)


if __name__ == "__main__":
    main()
