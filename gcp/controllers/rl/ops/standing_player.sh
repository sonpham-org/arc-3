#!/bin/bash
# Standing player (Son 2-Oct: "always have a GPU that plays the latest trained model"). One eval VM at a time, always
# on the newest model whose input copy is staged (base = Daniel's own inputs; r0, r1, ... once make_eval_mirror.sh has
# written kaggle-input-<model>/_STAGED_OK). Each run takes the panel with the fewest runs of that model (train, hard,
# held on ties), joins the RL page's panel list and Trace review's run list (train and hard panels; the publisher
# refuses held-out games anyway) at launch, and leaves the page's list again if it ends without finishing (a Spot
# preemption deletes the VM). A finished run's powered-off VM is deleted. A running base play is never cut short:
# a new model starts at the next launch.
#   bash ops/standing_player.sh            stop: touch /d/codex-work/rl-20261001/standing.STOP (ends after this run)
# Every gcloud call here runs under `timeout 120`: with an expired login gcloud can hang instead of failing
# (3-Oct 02:57 UTC froze this loop for hours); a timeout reads as a failed check and the loop goes on.
set -uo pipefail
export CLOUDSDK_PYTHON='C:\python312\python.exe'
OPS=$(cd "$(dirname "$0")" && pwd)
SITE=$(cd "$OPS/../site" && pwd)
WORK=/d/codex-work/rl-20261001
NBDIR=/d/codex-work/daniel-base-20261001/build
INPUTS=gs://cellens-ai-artifacts/arc3-duck/daniel-base
RUNS=$INPUTS/runs
STOP_FILE=$WORK/standing.STOP
SEQ_FILE=$WORK/standing.seq
MAX_RUNS=${MAX_RUNS:-40}
say() { echo "$(date -u +%H:%M) $*"; }

latest() {   # the newest staged model, in round order
  local best=base m
  for m in r0 r1 r2 r3 r4 r5 r6 r7 r8 r9; do
    timeout 120 gcloud storage ls "$INPUTS/kaggle-input-$m/_STAGED_OK" > /dev/null 2>&1 || break
    best=$m
  done
  echo "$best"
}

config() {   # config <add|drop|pick> <model> [panel] [run id]: edit or read the RL page's panel lists
  C:/Python312/python.exe - "$SITE/site_config.json" "$@" <<'PY' | tr -d '\r'
import json, sys
path, op, model, *rest = sys.argv[1:]
cfg = json.load(open(path, encoding="utf-8"))
if op == "pick":
    order = {"train": 0, "hard": 1, "held": 2}
    print(min(cfg["panels"], key=lambda p: (len(p["runs"].get(model, [])), order[p["key"]]))["key"])
    raise SystemExit
panel, run = rest
for p in cfg["panels"]:
    if p["key"] == panel:
        runs = p["runs"].setdefault(model, [])
        if op == "add" and run not in runs:
            runs.append(run)
        if op == "drop" and run in runs:
            runs.remove(run)
open(path, "w", encoding="utf-8", newline="\n").write(json.dumps(cfg, indent=1, ensure_ascii=False) + "\n")
print(op, panel, model, run)
PY
}

launch() {   # <label> <notebook build> <input prefix or "">: first zone with capacity, prints the zone
  local label=$1 nbobj Z
  nbobj=$(tr -d '\r' < "$NBDIR/$2.gcs.txt")
  for Z in us-east5-a us-east5-b us-east5-c us-central1-a us-central1-b us-central1-c us-east4-a us-east4-b us-east4-c; do
    if bash "$OPS/launch_daniel_eval.sh" "$label" "$Z" "$nbobj" "$3" > "$WORK/standing_launch.log" 2>&1; then
      echo "$Z"; return 0
    fi
  done
  return 1
}

login_ok() {   # an expired gcloud login makes VMs look gone and launches fail: wait for a working one
  local warned=0
  until timeout 120 gcloud auth print-access-token > /dev/null 2>&1; do
    [ $((warned % 15)) -eq 0 ] && say "gcloud login expired: run gcloud.cmd auth login (waiting)"
    warned=$((warned + 1)); sleep 120
  done
}

finish_run() {   # <label> <zone> <model> <panel>: watch a run to its end, keep or drop it, delete its powered-off VM
  local label=$1 zone=$2 model=$3 panel=$4 run="daniel-$1" last st i
  bash "$OPS/watch_daniel_runs.sh" "$label:$zone"
  login_ok
  last=$(timeout 120 gcloud storage cat "$RUNS/$run/phases.tsv" 2>/dev/null | tail -n 1 | cut -f3 | tr -d '\r')
  if [[ "$last" != *finish*notebook_rc_0* ]]; then
    say "$label ended without finishing (last phase: ${last:-none}): off the page's lists"
    config drop "$model" "$panel" "$run"
  fi
  # the VM powers itself off at the end: delete it once it is off (never while it runs)
  for i in $(seq 1 15); do
    st=$(timeout 120 gcloud compute instances describe "arc3-daniel-$label" --zone "$zone" --format='value(status)' 2>/dev/null | tr -d '\r')
    [ -z "$st" ] && break
    if [ "$st" = TERMINATED ] || [ "$st" = STOPPED ]; then
      timeout 120 gcloud compute instances delete "arc3-daniel-$label" --zone "$zone" --quiet > /dev/null 2>&1 && say "deleted VM arc3-daniel-$label"
      break
    fi
    sleep 60
  done
}

# RESUME=<label>:<zone>:<model>:<panel>: a run launched before this player was restarted; see it through first
if [ -n "${RESUME:-}" ]; then
  IFS=: read -r r_label r_zone r_model r_panel <<< "$RESUME"
  say "resuming the watch on $r_label in $r_zone ($r_model, $r_panel panel)"
  login_ok
  finish_run "$r_label" "$r_zone" "$r_model" "$r_panel"
fi

n=0
while [ ! -f "$STOP_FILE" ] && [ "$n" -lt "$MAX_RUNS" ]; do
  login_ok
  model=$(latest)
  panel=$(config pick "$model")
  case $panel in
    train) prefix=p5train nb=noborder-panel-train5x5-v1 ;;
    hard)  prefix=p4hard  nb=noborder-panel-hard4x6-v1 ;;
    held)  prefix=p5held  nb=noborder-panel-held5x5-v1 ;;
    *) say "no panel picked ($panel)"; sleep 600; continue ;;
  esac
  seq=$(( $(cat "$SEQ_FILE" 2>/dev/null || echo 0) + 1 )); [ -z "${DRY:-}" ] && echo "$seq" > "$SEQ_FILE"
  label="$prefix-$model-s$seq-$(date -u +%m%d)"
  input=""; [ "$model" != base ] && input="$INPUTS/kaggle-input-$model"
  if [ -n "${DRY:-}" ]; then say "dry run: would launch $label ($nb, input ${input:-his own})"; exit 0; fi
  if ! zone=$(launch "$label" "$nb" "$input"); then
    say "$label: no zone had capacity ($(grep -o -E 'STOCKOUT|QUOTA[A-Z_]*|exhausted' "$WORK/standing_launch.log" | head -1)); retry in 10 min"
    sleep 600; continue
  fi
  n=$((n + 1))
  run="daniel-$label"
  say "launched $label in $zone (model $model, $panel panel)"
  config add "$model" "$panel" "$run"
  [ "$panel" != held ] && echo "$run $model" >> "$WORK/review-runs.txt"
  finish_run "$label" "$zone" "$model" "$panel"
done
say "standing player stops ($([ -f "$STOP_FILE" ] && echo "stop file" || echo "$n runs"))"
