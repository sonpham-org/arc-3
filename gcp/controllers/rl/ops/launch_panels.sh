#!/bin/bash
# Launch a round's three test panels on its staged input copy, retrying through capacity stockouts across all zones
# that offer RTX PRO 6000 (3-Oct: round 1's panels found no capacity in the 9 usual zones and were never launched),
# then list them on the RL page and Trace review and watch them to the end.
#   bash ops/launch_panels.sh r1 a            (round, run letter); PANELS="p5train:noborder-panel-train5x5-v1" for some
# Every gcloud poll runs under `timeout 120`: an expired login makes gcloud hang.
set -uo pipefail
export CLOUDSDK_PYTHON='C:\python312\python.exe'
OPS=$(cd "$(dirname "$0")" && pwd)
SITE=$(cd "$OPS/../site" && pwd)
ROUND=${1:?round, e.g. r1} LETTER=${2:-a}
NBDIR=/d/codex-work/daniel-base-20261001/build
IN=gs://cellens-ai-artifacts/arc3-duck/daniel-base/kaggle-input-$ROUND
WORK=/d/codex-work/rl-20261001
TAG=$(date -u +%m%d)
ZONES="us-east5-a us-east5-b us-east5-c us-central1-a us-central1-b us-central1-c us-central1-f us-east4-a us-east4-b
       us-east4-c us-south1-a us-south1-b us-west4-a us-west4-b us-west4-c us-west1-a us-west1-b us-west1-c us-east1-b
       us-east1-d us-west3-a"
say() { echo "$(date -u +%H:%M) $*"; }
timeout 120 gcloud storage ls "$IN/_STAGED_OK" > /dev/null 2>&1 || { say "$IN is not staged"; exit 1; }

try_once() {   # <label> <notebook build>: first zone with capacity, prints label:zone
  local label=$1 nbobj Z
  nbobj=$(tr -d '\r' < "$NBDIR/$2.gcs.txt")
  for Z in $ZONES; do
    if bash "$OPS/launch_daniel_eval.sh" "$label" "$Z" "$nbobj" "$IN" > "/tmp/panels_$label.log" 2>&1; then
      echo "$label:$Z"; return 0
    fi
  done
  return 1
}
declare -A GOT
PANELS=${PANELS:-"p5held:noborder-panel-held5x5-v1 p5train:noborder-panel-train5x5-v1 p4hard:noborder-panel-hard4x6-v1"}
for attempt in $(seq 1 36); do                       # up to ~6 hours of retries
  for pb in $PANELS; do
    p=${pb%%:*} nb=${pb##*:}
    [ -n "${GOT[$p]:-}" ] && continue
    if r=$(try_once "$p-$ROUND-$LETTER-$TAG" "$nb"); then GOT[$p]=$r; say "launched $r"; fi
  done
  [ ${#GOT[@]} -eq $(echo $PANELS | wc -w) ] && break
  say "still waiting for capacity: $(for pb in $PANELS; do p=${pb%%:*}; [ -z "${GOT[$p]:-}" ] && printf '%s ' "$p"; done)(retry in 10 min)"
  sleep 600
done
[ ${#GOT[@]} -gt 0 ] || { say "no panel could be launched"; exit 1; }
H=${GOT[p5held]:-} T=${GOT[p5train]:-} K=${GOT[p4hard]:-}
C:/Python312/python.exe - "$SITE/site_config.json" "$ROUND" "$H" "$T" "$K" <<'PY'
import json, sys
path, rnd, *runs = sys.argv[1:]
cfg = json.load(open(path, encoding="utf-8"))
ids = {r.split(":")[0].split("-")[0]: "daniel-" + r.split(":")[0] for r in runs if r}
for p in cfg["panels"]:
    key = {"held": "p5held", "train": "p5train", "hard": "p4hard"}[p["key"]]
    if key in ids:
        p["runs"][rnd] = [ids[key]]
open(path, "w", encoding="utf-8", newline="\n").write(json.dumps(cfg, indent=1, ensure_ascii=False) + "\n")
print("RL page config:", {p["key"]: p["runs"].get(rnd) for p in cfg["panels"]})
PY
for r in "$T" "$K"; do [ -n "$r" ] && echo "daniel-${r%%:*} $ROUND" >> "$WORK/review-runs.txt"; done
bash "$OPS/watch_daniel_runs.sh" $H $T $K
say "$ROUND panels ended"
