#!/bin/bash
# Round 1, the last one (Son 3-Oct: "just do 2 rounds and down", 32 records). Run once round 0's test panels ended:
#   1. queue three trainer jobs: 030 builds round-1 records from round 0's train and hard panel plays (g0_data.py:
#      efficient wins + frontier wins; the held-out panel is never trained), 031 trains on at most 32 of them from
#      round 0's adapter (checkpoint every 4 records), 032 merges into Daniel's checkpoint;
#   2. start the trainer VM (stopped after round 0's merge to save cost), restarting it whenever Spot stops it, until
#      032 ends;
#   3. stage the LoRA input copy (kaggle-input-r1), launch the three test panels on it, list them on the RL page
#      (model R1, no next round) and in Trace review;
#   4. stop the trainer VM (no jobs left) and watch the panels to their end.
#   SHA=<code snapshot from push_code.sh> bash ops/run_round1.sh <r0 train-panel run> <r0 hard-panel run>
# Every gcloud poll runs under `timeout 120`: an expired login makes gcloud hang (3-Oct 02:57 UTC).
set -uo pipefail
export CLOUDSDK_PYTHON='C:\python312\python.exe'
OPS=$(cd "$(dirname "$0")" && pwd)
SITE=$(cd "$OPS/../site" && pwd)
VM=arc3-rl-train4-20261002 ZONE=us-south1-b
B=gs://cellens-ai-artifacts/arc3-rl/trainer/train4-1002
RUNS=gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs
NBDIR=/d/codex-work/daniel-base-20261001/build
IN=gs://cellens-ai-artifacts/arc3-duck/daniel-base/kaggle-input-r1
WORK=/d/codex-work/rl-20261001
SHA=${SHA:?set SHA to a code snapshot (ops/push_code.sh)}
TR=${1:?round 0 train-panel run id} HR=${2:?round 0 hard-panel run id}
TAG=$(date -u +%m%d)
say() { echo "$(date -u +%H:%M) $*"; }
g() { timeout 120 gcloud "$@"; }

# ---------------------------------------------------------------- 1. the jobs
C:/Python312/python.exe - "$WORK" "$SHA" "$TR" "$HR" <<'PY' || { echo "job files not written"; exit 1; }
import json, sys
work, sha, tr, hr = sys.argv[1:]
records = (f"set -e; cd /opt/rl && gcloud storage cp 'gs://cellens-ai-artifacts/arc3-rl/code/{sha}/*' /opt/rl/ && "
           "rm -rf /opt/m/work/records/031 /opt/m/work/g0r1 && mkdir -p /opt/m/work/records/031 /opt/m/work/g0r1 && "
           f"for r in {tr} {hr}; do /opt/rl/venv/bin/python g0_data.py --run $r "
           "--root gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs --frontier frontier.json --hf /opt/m/bf16 "
           "--campaign rl-1003a --harness daniel-nb-v1 --policy r0 --out /opt/m/work/g0r1/$r && "
           "for f in /opt/m/work/g0r1/$r/records/*.jsonl.gz; do cp $f /opt/m/work/records/031/$r-$(basename $f); done; done && "
           "ls /opt/m/work/records/031 && gcloud storage cp -r /opt/m/work/g0r1 gs://cellens-ai-artifacts/arc3-rl/rl-1003a/")
train = ("set -e; cd /opt/rl && ls /opt/m/work/records/031/*.jsonl.gz > /dev/null && test -f /opt/m/work/out/028-r0-train/ADAPTER.json && "
         "mkdir -p /opt/m/work/out/031-r1-train && ARC3_OFFLOAD_MIN_ELEMS=1239040000 /opt/rl/venv/bin/python lora_train.py train "
         "--model /opt/m/bf16 --hf /opt/m/bf16 --gpus 4 --gpu-gib 86 --nvfp4 /opt/m/daniel "
         "--records '/opt/m/work/records/031/*.jsonl.gz' --out /opt/m/work/out/031-r1-train "
         "--init-adapter /opt/m/work/out/028-r0-train --epochs 1 --accum 4 --lr 1e-4 --warmup 2 --rank 32 --alpha 64 "
         "--max-tokens 121000 --limit 32 --ckpt-every 1")
merge = ("set -e; test -f /opt/m/work/out/031-r1-train/ADAPTER.json && cd /opt/rl && mkdir -p /opt/m/work/out/032-r1-merge && "
         "/opt/rl/venv/bin/python merge_lora.py --adapter /opt/m/work/out/031-r1-train --checkpoint /opt/m/daniel "
         "--out /opt/m/work/out/032-r1-merge/merged --only-changed && ls -la /opt/m/work/out/032-r1-merge/merged | head -50")
for name, cmd in (("030-r1-records", records), ("031-r1-train", train), ("032-r1-merge", merge)):
    open(f"{work}/job{name[:3]}.json", "w", newline="\n").write(json.dumps({"cmd": "shell", "args": {"command": cmd}}))
print("job files written")
PY
for j in 030-r1-records 031-r1-train 032-r1-merge; do
  gcloud storage cp "$WORK/job${j:0:3}.json" "$B/jobs/$j.json" > /dev/null 2>&1 || { say "could not queue $j"; exit 1; }
done
say "queued 030-r1-records, 031-r1-train, 032-r1-merge (code $SHA; records from $TR and $HR)"
C:/Python312/python.exe - "$SITE/site_config.json" <<'PY'
import json, sys, time
path = sys.argv[1]
cfg = json.load(open(path, encoding="utf-8"))
cfg.update(round="Round 1", train_job="031-r1-train", merge_job="032-r1-merge", records_total=32,
           train_started=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
open(path, "w", encoding="utf-8", newline="\n").write(json.dumps(cfg, indent=1, ensure_ascii=False) + "\n")
print("RL page follows round 1's jobs")
PY

# ---------------------------------------------------------------- 2. the trainer, until the merge ends
while true; do
  if g storage ls "$B/out/032-r1-merge/EXIT" > /dev/null 2>&1; then break; fi
  for j in 030-r1-records 031-r1-train; do      # an earlier job that failed leaves nothing for the next
    code=$(g storage cat "$B/out/$j/EXIT" 2>/dev/null | tr -d '\r\n ')
    if [ -n "$code" ] && [ "$code" != 0 ]; then
      say "$j failed (exit $code); last log lines:"; g storage cat "$B/out/$j/job.log" | tail -n 25
      g compute instances stop $VM --zone $ZONE > /dev/null 2>&1 && say "trainer VM stopped"; exit 1
    fi
  done
  st=$(g compute instances describe $VM --zone $ZONE --format='value(status)' 2>/dev/null | tr -d '\r')
  case "$st" in
    TERMINATED|STOPPED|SUSPENDED)
      out=$(g compute instances start $VM --zone $ZONE 2>&1 | tr '\n' ' ')
      if echo "$out" | grep -qiE "STOCKOUT|exhausted|not enough resources|unavailable"; then say "trainer start: no capacity, retrying"
      else say "trainer VM was $st; started (jobs resume from their checkpoints)"; fi ;;
    "") say "could not read the trainer's status (gcloud login?)" ;;
  esac
  sleep 180
done
while hb=$(g storage cat "$B/status.json" 2>/dev/null); [ -z "$hb" ] || \
      { echo "$hb" | grep -q '"state": "running"' && echo "$hb" | grep -q '"job": "032-r1-merge"'; }; do sleep 60; done
code=$(g storage cat "$B/out/032-r1-merge/EXIT" | tr -d '\r\n ')
if [ "$code" != 0 ]; then
  say "merge failed (exit $code)"; g storage cat "$B/out/032-r1-merge/job.log" | tail -n 25
  g compute instances stop $VM --zone $ZONE > /dev/null 2>&1; exit 1
fi
say "round 1 trained on $(g storage cat "$B/out/031-r1-train/ADAPTER.json" | tr -d '\r\n' | grep -o '"records": [0-9]*') and merged"
g compute instances stop $VM --zone $ZONE > /dev/null 2>&1 && say "trainer VM stopped (no jobs left)"

# ---------------------------------------------------------------- 3. the test panels
launch() {   # <label> <notebook build name>: first zone with capacity
  local label=$1 nbobj Z
  nbobj=$(tr -d '\r' < "$NBDIR/$2.gcs.txt")
  for Z in us-east5-a us-east5-b us-east5-c us-central1-a us-central1-b us-central1-c us-east4-a us-east4-b us-east4-c; do
    if bash "$OPS/launch_daniel_eval.sh" "$label" "$Z" "$nbobj" "$IN" > "/tmp/round1_$label.log" 2>&1; then
      echo "$label:$Z"; return 0
    fi
  done
  say "$label: no zone had capacity" >&2; return 1
}
H=$(launch "p5held-r1-a-$TAG" noborder-panel-held5x5-v1)
T=$(launch "p5train-r1-a-$TAG" noborder-panel-train5x5-v1)
K=$(launch "p4hard-r1-a-$TAG" noborder-panel-hard4x6-v1)
say "launched: $H $T $K"
bash "$OPS/make_eval_mirror.sh" r1 "$B/out/032-r1-merge/merged" || { say "LoRA input copy failed"; exit 1; }
say "LoRA input copy staged: $IN"
C:/Python312/python.exe - "$SITE/site_config.json" "$H" "$T" "$K" <<'PY'
import json, sys
path, *runs = sys.argv[1:]
cfg = json.load(open(path, encoding="utf-8"))
if not any(m["key"] == "r1" for m in cfg["models"]):
    cfg["models"].append({"key": "r1", "label": "After round 1", "short": "R1",
                          "note": "round 0's LoRA, trained on more on the wins of round 0's own test plays"})
cfg["next_model"] = None        # Son 3-Oct: two rounds, then down
ids = {r.split(":")[0].split("-")[0]: "daniel-" + r.split(":")[0] for r in runs if r}
for p in cfg["panels"]:
    key = {"held": "p5held", "train": "p5train", "hard": "p4hard"}[p["key"]]
    if key in ids:
        p["runs"]["r1"] = [ids[key]]
open(path, "w", encoding="utf-8", newline="\n").write(json.dumps(cfg, indent=1, ensure_ascii=False) + "\n")
print("RL page config:", {p["key"]: p["runs"].get("r1") for p in cfg["panels"]})
PY
for r in "$T" "$K"; do [ -n "$r" ] && echo "daniel-${r%%:*} r1" >> "$WORK/review-runs.txt"; done
bash "$OPS/watch_daniel_runs.sh" $H $T $K
say "round 1 panels ended"
