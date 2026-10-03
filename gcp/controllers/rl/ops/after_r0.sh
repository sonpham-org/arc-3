#!/bin/bash
# Round 0 after training (plan 9g): wait for the merge (trainer job $MERGE_JOB, default 026-r0-merge), then launch the three test panels
# on the LoRA copy of Daniel's inputs and add those runs to the RL page and Trace review. The panel VMs start right
# away: they wait for the copy's _STAGED_OK (written last by make_eval_mirror.sh) while it is built.
#   bash ops/after_r0.sh           (polls every 2 min; stops with a message if the merge failed)
# Every gcloud call here runs under `timeout 120`: with an expired login gcloud can hang instead of failing
# (3-Oct 02:57 UTC froze this loop for hours); a timeout reads as a failed check and the loop goes on.
set -uo pipefail
export CLOUDSDK_PYTHON='C:\python312\python.exe'
OPS=$(cd "$(dirname "$0")" && pwd)
SITE=$(cd "$OPS/../site" && pwd)
OUT=gs://cellens-ai-artifacts/arc3-rl/trainer/train4-1002/out
MJ=${MERGE_JOB:-026-r0-merge}
NBDIR=/d/codex-work/daniel-base-20261001/build
IN=gs://cellens-ai-artifacts/arc3-duck/daniel-base/kaggle-input-r0
RUNS_TXT=/d/codex-work/rl-20261001/review-runs.txt
TAG=$(date -u +%m%d)
say() { echo "$(date -u +%H:%M) $*"; }

until timeout 120 gcloud storage cat "$OUT/$MJ/EXIT" >/dev/null 2>&1; do sleep 120; done
code=$(timeout 120 gcloud storage cat "$OUT/$MJ/EXIT" | tr -d '\r\n ')
if [ "$code" != "0" ]; then
  say "merge failed (exit $code); last log lines:"; timeout 120 gcloud storage cat "$OUT/$MJ/job.log" | tail -n 30; exit 1
fi
timeout 120 gcloud storage ls "$OUT/$MJ/merged/MERGE_REPORT.json" >/dev/null || { say "merge report missing"; exit 1; }
say "merged shards: $(timeout 120 gcloud storage ls "$OUT/$MJ/merged/*.safetensors" | wc -l)"

launch() {   # <label> <notebook build name>: first zone with capacity
  local label=$1 nbobj
  nbobj=$(tr -d '\r' < "$NBDIR/$2.gcs.txt")
  for Z in us-east5-a us-east5-b us-east5-c us-central1-a us-central1-b us-central1-c us-east4-a us-east4-b us-east4-c; do
    if bash "$OPS/launch_daniel_eval.sh" "$label" "$Z" "$nbobj" "$IN" > "/tmp/after_r0_$label.log" 2>&1; then
      echo "$label:$Z"; return 0
    fi
  done
  say "$label: no zone had capacity ($(grep -o -E 'STOCKOUT|QUOTA[A-Z_]*' "/tmp/after_r0_$label.log" | head -1))" >&2
  return 1
}
H=$(launch "p5held-r0-a-$TAG" noborder-panel-held5x5-v1)
T=$(launch "p5train-r0-a-$TAG" noborder-panel-train5x5-v1)
K=$(launch "p4hard-r0-a-$TAG" noborder-panel-hard4x6-v1)
say "launched: $H $T $K"

bash "$OPS/make_eval_mirror.sh" r0 "$OUT/$MJ/merged" || { say "LoRA input copy failed"; exit 1; }
say "LoRA input copy staged: $IN"

# the RL page's panels and Trace review's run list (held-out games are refused by the publisher anyway)
C:/Python312/python.exe - "$SITE/site_config.json" "$H" "$T" "$K" <<'PY'
import json, sys
path, *runs = sys.argv[1:]
cfg = json.load(open(path, encoding="utf-8"))
ids = {r.split(":")[0].split("-")[0]: "daniel-" + r.split(":")[0] for r in runs if r}
for p in cfg["panels"]:
    key = {"held": "p5held", "train": "p5train", "hard": "p4hard"}[p["key"]]
    if key in ids:
        p["runs"]["r0"] = [ids[key]]
open(path, "w", encoding="utf-8", newline="\n").write(json.dumps(cfg, indent=1, ensure_ascii=False) + "\n")
print("RL page config:", {p["key"]: p["runs"]["r0"] for p in cfg["panels"]})
PY
for r in "$T" "$K"; do [ -n "$r" ] && echo "daniel-${r%%:*} r0" >> "$RUNS_TXT"; done
say "runs list: $(tr '\n' ' ' < "$RUNS_TXT")"
bash "$OPS/watch_daniel_runs.sh" $H $T $K
