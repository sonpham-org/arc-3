"""Generate docs/data/runs-index.json: per-run stats, per-game scores, harness facts.

Stats come from each run's benchmark.json. The harness block is curated here --
server/weights/env facts live outside the run artifacts (they belong to the VM
that ran it), and this table is their single source of truth. The `baseline`
entry names the run every other run's knobs are diffed against on the site.
"""

import glob
import json
import os
import re


def extract_prompts(run_dir: str) -> dict:
    """First [SYSTEM PROMPT] and first [USER PROMPT] block from any transcript."""
    for t in sorted(glob.glob(os.path.join(run_dir, "transcripts", "*_p0.txt"))):
        text = open(t, errors="replace").read(200_000)
        blocks = re.split(r"^\[([A-Z ]+)\]$", text, flags=re.M)
        # blocks: [pre, LABEL, content, LABEL, content, ...]
        out = {}
        for label, content in zip(blocks[1::2], blocks[2::2]):
            if label == "SYSTEM PROMPT" and "system" not in out:
                out["system"] = content.strip()
            if label == "USER PROMPT" and "user_example" not in out:
                out["user_example"] = content.strip()
            if len(out) == 2:
                return out
        if out:
            return out
    return {}

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
    "20260713_010244_rung1-spec-vrfai-v025": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "Tufa upstream, pristine",
        "memory": "scientist note (optional prose)",
        "render": "plain 4x (256px)",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.25.0",
        "server_max_len": 65536, "spec_decode": "ngram",
        "weights": "vrfai FP8 (35.9 GB)", "concurrency": 28, "budget_min": 132,
        "note": "rung 1: vrfai quant hits a pathological kernel path on vLLM 0.25; spec decode amplifies it",
    },
    "20260713_033303_rung1b-nospec-vrfai-v025": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "Tufa upstream, pristine",
        "memory": "scientist note (optional prose)",
        "render": "plain 4x (256px)",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.25.0",
        "server_max_len": 65536, "spec_decode": "off",
        "weights": "vrfai FP8 (35.9 GB)", "concurrency": 28, "budget_min": 132,
        "note": "rung 1b: isolates spec decode -- still 3.4x slower than vLLM 0.19 on this quant",
    },
    "20260714_150500_v12-corrected-grafts": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "thtennant v12 (taaf_grafts: shortcircuit + efficiency + retry_guard)",
        "memory": "scientist note (optional prose)",
        "render": "plain 4x (256px)",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.19.0 (Tufa wheelhouse)",
        "server_max_len": 65536, "spec_decode": "off",
        "weights": "vrfai FP8 (35.9 GB)", "concurrency": 28, "budget_min": 132,
        "note": "faithful v12 rerun (Kaggle 1.28 recipe) with engine pinned to competition wheels (arc_agi 0.9.8/arcengine 0.9.3) and teardown parity",
    },
    "20260714_151100_v12-fullframe-peraction": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "thtennant v12 + per-action full-frame animation (last_animation)",
        "memory": "scientist note (optional prose)",
        "render": "plain 4x (256px)",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.19.0 (Tufa wheelhouse)",
        "server_max_len": 65536, "spec_decode": "off",
        "weights": "vrfai FP8 (35.9 GB)", "concurrency": 28, "budget_min": 132,
        "note": "v12-corrected plus last_animation: one entry per INDIVIDUAL action of the latest action(...) call, each with every engine frame that single action produced (16-entry cap)",
    },
    "20260713_042338_rung1c-spec-official-v025": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "Tufa upstream, pristine",
        "memory": "scientist note (optional prose)",
        "render": "plain 4x (256px)",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.25.0",
        "server_max_len": 65536, "spec_decode": "ngram",
        "weights": "official Qwen FP8 (30.9 GB)", "concurrency": 28, "budget_min": 132,
        "note": "rung 1c: modern serving validated -- statistically tied with tufa-exact",
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
        "prompts": extract_prompts(os.path.dirname(bench_path)),
    })

runs.sort(key=lambda r: -r["avg_score"])
payload = {"baseline": BASELINE, "runs": runs}
os.makedirs("docs/data", exist_ok=True)
json.dump(payload, open("docs/data/runs-index.json", "w"), indent=1)
print(f"wrote {len(runs)} runs; baseline={BASELINE}")
