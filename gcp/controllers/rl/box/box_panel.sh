#!/bin/bash
# Held-out full test on ONE card of the RL box, model after model (4-Oct-2026, Son: "the testing games should just run
# full from begin to end"; rl/box/README.md). The same test as the outside held-out panels: Daniel's notebook built
# with variants/panel-held5x5 (the five held-out games dc22 lf52 re86 su15 tn36, 5 plays each, 132-min game budget,
# his priority scheduling), run the way daniel-run-vm-startup.sh runs it (Kaggle's image, --network none, nbconvert,
# the server-start watch, GPU device nodes), so its scores compare with every earlier held-out run. Differences:
#   - the input is built ON the box: Daniel's inputs downloaded once to /kaggle-in/daniel-base-kaggle-input, then per
#     model a hard-linked copy with that model's merged shards (/opt/m/work/out/<merge>/merged) linked over his
#     (merge_lora.py --only-changed keeps every shard's size, so his manifest check still passes);
#   - a loop: the newest merged model not yet tested, played to the end, uploaded to the usual run folder
#     gs://.../daniel-base/runs/daniel-p5held-<model>-box-<MMDD>/, then the next newest. ~2 h 25 min a test, so about
#     every third model gets one.
# Started by box_startup.sh as systemd unit rl-panel. Env: CARD (3), NB_OBJ (the held5x5 notebook), FIRST (a merge job
# to test first, e.g. 105k-n0-merge). Ends at /run/box/panel.stop.
set -uo pipefail
CARD=${CARD:-3}
NB_OBJ=${NB_OBJ:?the held-out panel notebook}
BASE_IN=gs://cellens-ai-artifacts/arc3-duck/daniel-base/kaggle-input
RUNS=gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs
MODEL=models/dfranzen/intel-qwen3.8-flash-next-w4a16-autoround/transformers/default/1
OUTS=/opt/m/work/out
TESTED=/var/lib/box/panel-tested.txt
HOLD=gs://cellens-ai-artifacts/arc3-rl/box/$(curl -s -H 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/instance/name)/panel-hold
L=/var/log/box/panel
R=/kaggle-root/panel
NAME=rl-panel
mkdir -p "$L" /kaggle-in /var/lib/box && touch "$TESTED"
exec >> "$L/loop.log" 2>&1
say() { echo "$(date -u +%FT%TZ) $*"; }
IMAGE=$(cat /var/lib/box/image 2>/dev/null)
for i in $(seq 1 120); do [ -n "$IMAGE" ] && docker image inspect "$IMAGE" > /dev/null 2>&1 && break; sleep 30; IMAGE=$(cat /var/lib/box/image 2>/dev/null); done

base_inputs() {   # Daniel's inputs, once (the slots' lock: one download at a time)
  local d=/kaggle-in/daniel-base-kaggle-input
  ( flock -w 7200 9
    [ -f "$d/.ok" ] || { rm -rf "$d" && mkdir -p "$d" && gcloud storage rsync -r "$BASE_IN" "$d" > "$L/base-rsync.log" 2>&1 \
                         && touch "$d/.ok"; }
  ) 9> /kaggle-in/.lock
  [ -f "$d/.ok" ] && echo "$d"
}
next_model() {    # the newest merge with EXIT 0 and its merged shards, not yet tested (FIRST first)
  if [ -n "${FIRST:-}" ] && ! grep -qx "$FIRST" "$TESTED" && [ -d "$OUTS/$FIRST/merged" ]; then echo "$FIRST"; return; fi
  for e in $(ls -t "$OUTS"/*-merge/EXIT 2>/dev/null); do
    m=$(basename "$(dirname "$e")")
    [ "$(tr -d ' \n' < "$e")" = 0 ] && [ -d "$OUTS/$m/merged" ] && ! grep -qx "$m" "$TESTED" && { echo "$m"; return; }
    break                                 # only the newest: an older untested model is skipped for good
  done
}
model_inputs() {  # <base dir> <merge job> -> /kaggle-in/panel-<merge>: his inputs with that model's shards
  local base=$1 m=$2 d=/kaggle-in/panel-$2
  rm -rf "$d" && cp -al "$base" "$d" || return 1
  for f in "$OUTS/$m/merged"/*.safetensors; do ln -f "$f" "$d/$MODEL/$(basename "$f")" || return 1; done
  cp "$OUTS/$m/merged/MERGE_REPORT.json" "$d/MERGE_REPORT.json"
  python3 - "$d" <<'PY' >&2 || return 1          # its report to the log: stdout is this function's answer
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
man = json.loads((root / "DANIEL_BASE_MANIFEST.json").read_text())["files"]
bad = [k for k, v in man.items() if not (root / k).is_file() or (root / k).stat().st_size != v["size"]]
print("manifest files", len(man), "missing or wrong size", len(bad), bad[:5])
sys.exit(1 if bad else 0)
PY
  echo "$d"
}
run_test() {      # <input dir> <run id>
  local IND=$1 RUN_ID=$2 OUT=$RUNS/$2
  phase() { printf '%s\t%s\t%s\n' "$(date -u +%FT%TZ)" "$(cut -d' ' -f1 /proc/uptime)" "$1" | tee -a "$L/$RUN_ID.phases.tsv"; timeout 30 gcloud storage cp "$L/$RUN_ID.phases.tsv" "$OUT/phases.tsv" >/dev/null 2>&1 || true; }
  sync_out() { timeout 300 gcloud storage rsync -r "$R/working" "$OUT/working" >/dev/null 2>&1 || true; }
  docker rm -f "$NAME" > /dev/null 2>&1
  rm -rf "$R" && mkdir -p "$R/working" "$R/nb"
  phase "start $RUN_ID box card $CARD"
  gcloud storage cp "$NB_OBJ" "$R/nb/notebook.ipynb" > /dev/null 2>&1 || { phase "finish (notebook_download_failed)"; return; }
  phase inputs_copied
  local GPU_DEVS="" d
  for d in /dev/nvidiactl /dev/nvidia-uvm /dev/nvidia-uvm-tools /dev/nvidia-modeset "/dev/nvidia$CARD"; do
    [ -e "$d" ] && GPU_DEVS="$GPU_DEVS --device $d"
  done
  ( while true; do sleep 300; sync_out; done ) &
  local SYNC=$! ATTEMPT=1 OUTCOME DEAD i
  while :; do
    # shellcheck disable=SC2086
    docker run -d --name "$NAME" --gpus "device=$CARD" $GPU_DEVS --cpus 48 --memory 200g --network none --shm-size=64g \
      --ulimit memlock=-1 -v "$IND:/kaggle/input:ro" -v "$R/working:/kaggle/working" -v "$R/nb:/kaggle/nb:ro" \
      -w /kaggle/working --entrypoint bash "$IMAGE" -c \
      'jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=-1 --ExecutePreprocessor.kernel_name=python3 /kaggle/nb/notebook.ipynb --output-dir /kaggle/working --output __notebook__.ipynb' \
      > /dev/null || { phase "finish (docker_run_failed)"; kill $SYNC; return; }
    OUTCOME=timeout DEAD=0
    for i in $(seq 1 180); do
      sleep 20
      if grep -q "ready to roll" "$R/working/serve.log" 2>/dev/null; then OUTCOME=ready; break; fi
      if grep -q -E "Scheduler hit an exception|Capture cuda graph failed|Received sigquit from a child" "$R/working/serve.log" 2>/dev/null; then OUTCOME=server_failed; break; fi
      [ -n "$(docker ps -q -f name="^$NAME\$")" ] || { OUTCOME=exited; break; }
      if [ -s "$R/working/serve.log" ] && ! docker top "$NAME" -eo pid,args 2>/dev/null | grep -q -i sglang; then
        DEAD=$((DEAD + 1)); [ "$DEAD" -ge 3 ] && { OUTCOME=server_failed; break; }
      else
        DEAD=0
      fi
    done
    phase "server_${OUTCOME} attempt_$ATTEMPT"
    if [ "$OUTCOME" = server_failed ]; then
      docker logs "$NAME" > "$R/working/nbconvert.log" 2>&1; docker rm -f "$NAME" > /dev/null 2>&1
      [ "$ATTEMPT" -ge 2 ] && { sync_out; phase "finish (server_failed_twice)"; kill $SYNC; return; }
      find "$R/working" -mindepth 1 -delete
      ATTEMPT=$((ATTEMPT + 1))
      continue
    fi
    break
  done
  local RC
  RC=$(docker wait "$NAME")
  docker logs "$NAME" > "$R/working/nbconvert.log" 2>&1
  docker rm "$NAME" > /dev/null 2>&1
  kill $SYNC 2>/dev/null
  sync_out
  phase "finish (notebook_rc_$RC)"
}

say "panel loop: card $CARD, notebook $NB_OBJ, first ${FIRST:-newest}"
BASE=""
while [ ! -f /run/box/panel.stop ]; do
  [ -n "$BASE" ] || BASE=$(base_inputs) || { say "base inputs not ready"; sleep 120; continue; }
  # run_c.py holds the card after the run's first held-out test (the last model gets its test on a 1-card box)
  timeout 60 gcloud storage ls "$HOLD" > /dev/null 2>&1 && { sleep 120; continue; }
  M=$(next_model)
  [ -n "$M" ] || { sleep 60; continue; }
  TAG=$(echo "$M" | sed 's/-merge$//; s/^[0-9]*[a-z]*-//')            # 105k-n0-merge -> n0, c007-merge -> c007
  [ "$TAG" = "$M" ] && TAG=${M%-merge}
  RUN_ID=daniel-p5held-$TAG-boxnp-$(date -u +%m%d)    # np: no priority gate (Son 4-Oct)
  IND=$(model_inputs "$BASE" "$M") || { say "$M: input build failed"; echo "$M" >> "$TESTED"; continue; }
  say "$M: testing as $RUN_ID"
  echo "$M" >> "$TESTED"
  run_test "$IND" "$RUN_ID"
  say "$M: $(tail -n 1 "$L/$RUN_ID.phases.tsv" | cut -f3)"
  ls -1d /kaggle-in/panel-* 2>/dev/null | grep -v "panel-$M\$" | xargs -r rm -rf
done
say "panel loop stopped"
