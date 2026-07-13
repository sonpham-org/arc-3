"""Generate docs/data/runs-index.json: per-run stats, per-game scores, harness facts.

Stats come from each run's benchmark.json. The harness block is curated here --
server/weights/env facts live outside the run artifacts (they belong to the VM
that ran it), and this table is their single source of truth. The `baseline`
entry names the run every other run's knobs are diffed against on the site.
"""

import glob
import json
import os

BASELINE = "20260712_170321_tufa-exact-rung0"

HARNESS = {
    "20260712_170321_tufa-exact-rung0": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "Tufa upstream, pristine",
        "memory": "scientist note (optional prose)",
        "render": "plain 4x (256px)",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.19.0 (Tufa wheelhouse)",
        "server_max_len": 65536, "spec_decode": "off",
        "weights": "vrfai FP8 (35.9 GB)", "concurrency": 28, "budget_min": 132,
    },
    "20260712_130533_g4-v1-fullstack-32k": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "modified (ledger + fixes)",
        "memory": "two-tier ledger (required arg)",
        "render": "outline 8x + bevel (512px)",
        "yield_s": 900, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.25.0",
        "server_max_len": "32768 (clips generation)", "spec_decode": "ngram",
        "weights": "official Qwen FP8 (30.9 GB)", "concurrency": 25, "budget_min": 132,
    },
    "20260712_130556_g4-v2-ledger-64k": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "modified (ledger + fixes)",
        "memory": "two-tier ledger (required arg)",
        "render": "outline 8x + bevel (512px)",
        "yield_s": 900, "thinking": "on (uncapped)",
        "agent_ctx": 65536, "server": "vLLM 0.25.0",
        "server_max_len": 65536, "spec_decode": "ngram",
        "weights": "official Qwen FP8 (30.9 GB)", "concurrency": 25, "budget_min": 132,
    },
    "20260711_200118_a424-control-25game": {
        "hardware": "GB10 DGX Spark",
        "agent_code": "modified (tier-A fixes)",
        "memory": "scientist note + required world_model",
        "render": "plain 4x (256px)",
        "yield_s": 900, "thinking": "off",
        "agent_ctx": 32768, "server": "vLLM 0.24.0",
        "server_max_len": 32768, "spec_decode": "ngram",
        "weights": "official Qwen FP8 (30.9 GB)", "concurrency": 25, "budget_min": 132,
    },
    "20260711_231159_a424-think3x-uncapped": {
        "hardware": "GB10 DGX Spark",
        "agent_code": "modified (tier-A fixes)",
        "memory": "scientist note + required world_model",
        "render": "outline 8x + bevel (512px)",
        "yield_s": 3600, "thinking": "on (uncapped -- pathological on GB10)",
        "agent_ctx": 32768, "server": "vLLM 0.24.0",
        "server_max_len": 32768, "spec_decode": "ngram",
        "weights": "official Qwen FP8 (30.9 GB)", "concurrency": 25, "budget_min": 396,
    },
    "20260711_185043_a424-study-ft09": {
        "hardware": "GB10 DGX Spark",
        "agent_code": "modified (tier-A fixes)",
        "memory": "scientist note + required world_model",
        "render": "plain 4x (256px)",
        "yield_s": 900, "thinking": "off",
        "agent_ctx": 32768, "server": "vLLM 0.24.0",
        "server_max_len": 32768, "spec_decode": "ngram",
        "weights": "official Qwen FP8 (30.9 GB)", "concurrency": 1, "budget_min": 90,
        "note": "single-game deep study, interrupted",
    },
}

runs = []
for bench_path in sorted(glob.glob("logs/*/benchmark.json")):
    run = os.path.basename(os.path.dirname(bench_path))
    try:
        bench = json.load(open(bench_path))
    except Exception:
        continue
    games = bench.get("game_runs", [])
    n = len(games) or 1
    per_game = [
        {
            "id": g.get("game_id", "?"),
            "score": round(g.get("final_score") or 0, 3),
            "levels": g.get("levels_completed") or 0,
            "levels_total": g.get("number_of_levels") or 0,
            "actions": sum(g.get("actions_per_level") or []),
        }
        for g in games
    ]
    runs.append({
        "run": run,
        "games": len(games),
        "avg_score": round(sum(g["score"] for g in per_game) / n, 3),
        "levels": sum(g["levels"] for g in per_game),
        "actions": sum(g["actions"] for g in per_game),
        "tokens": sum(
            sum(h.get("generated_tokens") or 0 for h in (g.get("history") or []))
            + (g.get("final_generated_tokens") or 0)
            for g in games
        ),
        "per_game": sorted(per_game, key=lambda g: g["id"]),
        "harness": HARNESS.get(run, {}),
    })

runs.sort(key=lambda r: -r["avg_score"])
payload = {"baseline": BASELINE, "runs": runs}
os.makedirs("docs/data", exist_ok=True)
json.dump(payload, open("docs/data/runs-index.json", "w"), indent=1)
print(f"wrote {len(runs)} runs; baseline={BASELINE}")
