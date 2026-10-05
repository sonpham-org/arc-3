"""Token-matched scoring, extraction half (3-Oct-2026, daniel-draft; Son: "compare the score at the same amount of
tokens"). Runs on a small GCP VM (tokmatch_startup.sh) because each run's request logs are ~840 MB (every line
carries the whole prompt) and this PC downloads at ~1.3 MB/s.

  python3 extract.py RUN_ID      -> /opt/tm/RUN_ID.json

Per p0 game: "resp" = [analysis_step, action, completion_tokens, prompt_tokens] for every response in file order;
"lvl" = action_num of each level_completed event; "nact" = actions played; "viewer" = the final viewer fields our
scorer reads (levels_completed, actions_per_level, status).
"""
import glob
import json
import os
import subprocess
import sys

B = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs"
run = sys.argv[1]
raw = f"/opt/tm/raw_{run}"
for sub in ("req", "ev", "vw"):
    os.makedirs(f"{raw}/{sub}", exist_ok=True)
subprocess.run(["gcloud", "storage", "cp", "-q", f"{B}/{run}/working/*_p0_requests.jsonl", f"{raw}/req/"])
subprocess.run(["gcloud", "storage", "cp", "-q", f"{B}/{run}/working/artifacts/*_p0_events.jsonl", f"{raw}/ev/"])
subprocess.run(["gcloud", "storage", "cp", "-q", f"{B}/{run}/working/artifacts/*_p0_viewer_data.json", f"{raw}/vw/"])


def as_int(x, default=0):
    try:
        return int(x)
    except (TypeError, ValueError):
        return default


def truthy(x):
    return x is True or str(x).lower() == "true"


out = {}
for p in sorted(glob.glob(f"{raw}/req/*_p0_requests.jsonl")):
    g = os.path.basename(p).split("_p0_")[0]
    resp = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            if '"response"' not in line:
                continue
            d = json.loads(line)
            if d.get("event") != "response":
                continue
            u = d.get("usage") or {}
            resp.append([as_int(d.get("analysis_step")), as_int(d.get("action")),
                         as_int(u.get("completion_tokens")), as_int(u.get("prompt_tokens"))])
    out.setdefault(g, {})["resp"] = resp
for p in sorted(glob.glob(f"{raw}/ev/*_p0_events.jsonl")):
    g = os.path.basename(p).split("_p0_")[0]
    lvl, nact = [], 0
    with open(p, encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            if e.get("type") != "action":
                continue
            a = as_int(e.get("action_num"))
            nact = max(nact, a)
            if truthy(e.get("level_completed")):
                lvl.append(a)
    out.setdefault(g, {}).update(lvl=lvl, nact=nact)
for p in sorted(glob.glob(f"{raw}/vw/*_p0_viewer_data.json")):
    v = json.load(open(p, encoding="utf-8"))
    g = str(v.get("game_id"))
    out.setdefault(g, {})["viewer"] = {k: v.get(k) for k in ("levels_completed", "actions_per_level", "status")}
json.dump({"run": run, "games": out}, open(f"/opt/tm/{run}.json", "w"))
print(run, len(out), "games", sum(len(x.get("resp", [])) for x in out.values()), "responses")
