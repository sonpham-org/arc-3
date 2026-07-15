"""Summarize a run's turn telemetry (logs/<run>/artifacts/*_turn_stats.jsonl).

Usage: python scripts/analyze_turn_stats.py logs/<run-dir>

Per game and overall: total play time, requests, actions reached, token
totals, tok/s distribution, thinking tokens (or chars) per action.
"""

import glob
import json
import statistics
import sys
from pathlib import Path


def summarize(rows: list[dict]) -> dict:
    ts = [r["ts"] for r in rows if r.get("ts")]
    toks = [r["tok_s"] for r in rows if r.get("tok_s")]
    comp = [r.get("completion_tokens") or 0 for r in rows]
    think_tok = [r["reasoning_tokens"] for r in rows if r.get("reasoning_tokens") is not None]
    think_chr = [r.get("reasoning_chars") or 0 for r in rows]
    actions = max((r.get("action") or 0 for r in rows), default=0)
    return {
        "requests": len(rows),
        "actions_reached": actions,
        "play_time_min": round((max(ts) - min(ts)) / 60, 1) if len(ts) > 1 else 0.0,
        "completion_tokens": sum(comp),
        "tok_s_median": round(statistics.median(toks), 1) if toks else None,
        "tok_s_p10_p90": [round(statistics.quantiles(toks, n=10)[0], 1),
                          round(statistics.quantiles(toks, n=10)[-1], 1)] if len(toks) >= 10 else None,
        "latency_s_median": round(statistics.median([r["latency_s"] for r in rows if r.get("latency_s")]), 1)
                            if any(r.get("latency_s") for r in rows) else None,
        "thinking_tokens_per_action": round(sum(think_tok) / actions, 1) if think_tok and actions else None,
        "thinking_chars_per_action": round(sum(think_chr) / actions) if actions else None,
        "completion_tokens_per_action": round(sum(comp) / actions) if actions else None,
    }


def main(run_dir: str) -> None:
    files = sorted(glob.glob(str(Path(run_dir) / "artifacts" / "*turn_stats.jsonl")))
    if not files:
        sys.exit(f"no *turn_stats.jsonl under {run_dir}/artifacts")
    all_rows = []
    print(f"{'game':<28} {'req':>4} {'act':>4} {'min':>6} {'tok/s':>6} {'think-tok/act':>13}")
    for f in files:
        rows = [json.loads(l) for l in open(f) if l.strip()]
        all_rows += rows
        s = summarize(rows)
        name = Path(f).stem.removesuffix("_turn_stats")[:28]
        print(f"{name:<28} {s['requests']:>4} {s['actions_reached']:>4} {s['play_time_min']:>6} "
              f"{s['tok_s_median'] or '-':>6} {s['thinking_tokens_per_action'] or s['thinking_chars_per_action'] or '-':>13}")
    print("\n=== overall ===")
    print(json.dumps(summarize(all_rows), indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
