"""Assemble per-run x per-game scores for Flash-Next harness runs (DB + unpublished GCS) into dataset.json."""
import json, subprocess, re, os, sys, collections
import psycopg2
from pathlib import Path

SP = Path(__file__).resolve().parent
ENV = dict(os.environ, CLOUDSDK_PYTHON=r"C:\python312\python.exe")
BUCKET = "gs://cellens-ai-artifacts/arc3-duck"
v = json.loads(subprocess.run(["railway", "variables", "--service", "Postgres", "--environment", "production", "--json"],
                              capture_output=True, text=True, shell=True, cwd="D:/codex-work/arc3-game-evolution-20260918").stdout)
c = psycopg2.connect(v["DATABASE_PUBLIC_URL"], connect_timeout=20)
cur = c.cursor()

runs = {}
# ---- published Flash-Next runs since 8-Sep, 25 games
cur.execute("""select run_id, avg_score, level_count, action_count, generated_tokens, duration_seconds, started_at,
                      catalog_entry->'model'->>'id' from arc3_runs
               where started_at >= '2026-09-08' and game_count = 25""")
for run_id, avg, lv, ac, tok, dur, st, model in cur.fetchall():
    if model and "Flash-Next" not in model:
        continue
    runs[run_id] = dict(run_id=run_id, avg=float(avg or 0), levels=lv, actions=ac, tokens=tok, duration=dur,
                        started=str(st)[:10], model=model, source="db", games={})
cur.execute("select run_id, game_id, score, levels_completed, levels_total, actions from arc3_game_scores where run_id = any(%s)", (list(runs),))
for run_id, g, s, l, lt, a in cur.fetchall():
    runs[run_id]["games"][g[:4]] = dict(score=float(s), levels=l, levels_total=lt, actions=a)

# ---- action-type shares per game from score events (published runs only)
cur.execute("""select game_id, action, count(*) from arc3_score_events
               where kind='action' and run_id = any(%s) group by 1,2""", (list(runs),))
acts = collections.defaultdict(collections.Counter)
for g, a, n in cur.fetchall():
    acts[g[:4]][str(a).split("(")[0].upper()] += n
game_actions = {g: dict(cnt) for g, cnt in acts.items()}

# ---- unpublished GCS runs (DONE) from 20-24 Sep, Flash-Next only, plus the live 264s and hard-7 arms
extra = [l.strip() for l in (SP / "done_runs.txt").read_text().splitlines() if l.strip()]
extra = [r for r in extra if not re.search(r"mimo|qwen|signal|glm|dsv4|deepseek|llamacpp", r)]
extra += ["g4run-cv5cr264-w7-20260923-09c0d3183d", "g4run-lacr264-w7-20260923-8367f8ff09",
          "g4run-cv5cr-hard7-264-w7-20260923-7c19c6eb63",
          "g4run-cv5cr-hard7-memory-132-w7-20260923-d5d8b2be9d", "g4run-cv5cr-hard7-symbolic-132-w7-20260923-5aac84d4fc",
          "g4run-cv5cr-hard7-solver-132-w7-20260923-92b391fd79",
          "g4run-compaction-v5-clean-return-a132-w7-20260919-693e7fd43c", "g4run-compaction-v5-clean-return-b132-w7-20260919-0e59b2567b"]
for r in sorted(set(extra)):
    if r in runs:
        continue
    out = subprocess.run(["gcloud", "storage", "cat", f"{BUCKET}/{r}/runs/summary.txt"], capture_output=True, text=True, env=ENV, shell=True).stdout
    if "mean score" not in out:
        print("no summary:", r, file=sys.stderr); continue
    games = {}
    for m in re.finditer(r"^\s+([a-z0-9]{4})-[0-9a-f]+: score=([\d.]+), levels=([\d.]+)/(\d+), actions=(\d+), tokens=(\d+)", out, re.M):
        games[m.group(1)] = dict(score=float(m.group(2)), levels=int(float(m.group(3))), levels_total=int(m.group(4)), actions=int(m.group(5)), tokens=int(m.group(6)))
    mean = float(re.search(r"mean score:\s+([\d.]+)", out).group(1))
    runs[r] = dict(run_id=r, avg=mean, levels=sum(g["levels"] for g in games.values()), actions=sum(g["actions"] for g in games.values()),
                   tokens=sum(g["tokens"] for g in games.values()), duration=None, started=re.search(r"2026\d{4}", r).group(0), model="Flash-Next", source="gcs", games=games)

json.dump({"runs": runs, "game_actions": game_actions}, open(SP / "dataset.json", "w"), indent=1)
print("runs:", len(runs), "db:", sum(r["source"] == "db" for r in runs.values()), "gcs:", sum(r["source"] == "gcs" for r in runs.values()))
