"""Progress of a replay run from its replay_log.jsonl (4-Oct-2026). Usage: python replay_progress.py <run id>
Prints requests done, errors, tokenization mismatches (replayed prompt tokens != original), prefilled tokens and rate,
and the capture size so far."""
import json
import subprocess
import sys

GC = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
RP = "gs://cellens-ai-artifacts/arc3-duck/daniel-draft/replay"
run = sys.argv[1]
txt = subprocess.run(GC + ["storage", "cat", f"{RP}/runs/{run}/working/replay_log.jsonl"], capture_output=True,
                     text=True).stdout
recs = [json.loads(l) for l in txt.splitlines() if l.strip()]
ok = [r for r in recs if "error" not in r]
mis = [r for r in ok if r.get("orig") is not None and r.get("prompt") is not None and r["orig"] != r["prompt"]]
prompt = sum(r.get("prompt") or 0 for r in ok)
cached = sum(r.get("cached") or 0 for r in ok)
sec = sum(r.get("sec") or 0 for r in recs)
games = {}
for r in recs:
    games.setdefault(r["game"], 0)
    games[r["game"]] += 1
du = subprocess.run(GC + ["storage", "du", "-s", f"{RP}/captures/{run}/"], capture_output=True, text=True).stdout.split()
out = {"requests": len(recs), "errors": len(recs) - len(ok), "tok_mismatch": len(mis),
       "mismatch_examples": [(r["game"], r["k"], r["orig"], r["prompt"]) for r in mis[:5]],
       "prompt_tokens_M": round(prompt / 1e6, 2), "cached_M": round(cached / 1e6, 2),
       "prefilled_M": round((prompt - cached) / 1e6, 2), "sum_request_seconds": round(sec),
       "games_started": len(games), "capture_gb": round(int(du[0]) / 2 ** 30, 1) if du else None,
       "errors_sample": [r.get("error") for r in recs if "error" in r][:3]}
print(json.dumps(out, indent=1))
