#!/bin/bash
# One rollout server on ONE card of the RL box (4-Oct-2026, Son: "just take 8 GPU and redo everything"). The box is
# a g4-standard-384 (8x RTX PRO 6000) that runs the whole RL v1 loop: all 8 cards play the round's tries, then all 8
# train (play and training take turns: a round's tries must be played by the newest model). This is
# gtree-rollout/runner/rl-vm-startup.sh for one card of that box instead of a whole 1-card VM:
#   - started by box_agent.sh as systemd unit rl-slot-<SLOT>, settings from the environment instead of VM metadata:
#     SLOT (0-7, also the card), RUN_ID, NB_OBJ, CAMPAIGN, LABEL (the logical VM name arc3-rl-<LABEL>: claims, tries/
#     and results/ in the campaign are keyed by it, as for a VM), optional IN (input prefix), SHM;
#   - the container sees only its card and gets a g4-standard-48's share of the box (48 vCPUs, 176 GB);
#   - the model inputs are downloaded once per input prefix into /kaggle-in/<tag> and shared read-only by every slot;
#   - no power-off at the end: the slot writes "finish (...)" to its phases.tsv AFTER its last upload (the round script
#     queues the records job on finish*, and the trainer on this box starts at once, so the order matters here;
#     rl-vm-startup.sh wrote finish first and relied on the trainer VM's boot time to hide the gap).
set -uo pipefail
: "${SLOT:?}" "${RUN_ID:?}" "${NB_OBJ:?}" "${CAMPAIGN:?}" "${LABEL:?}"
GPU=${GPU:-$SLOT}
IN=${IN:-}; case "$IN" in gs://*) ;; *) IN=gs://cellens-ai-artifacts/arc3-duck/daniel-draft/kaggle-input;; esac
SHM=${SHM:-64g}; case "$SHM" in [0-9]*g) ;; *) SHM=64g;; esac
VM=arc3-rl-$LABEL
STORE=gs://cellens-ai-artifacts/arc3-gtree/v1
RL=$STORE/rl/$CAMPAIGN
OUT=$RL/runs/$RUN_ID
CODE=gs://cellens-ai-artifacts/arc3-gtree/rollout-code       # rl_host_sync.py, gtree_store.py, gtree_ctx.py
IMAGE=$(cat /var/lib/box/image 2>/dev/null)
R=/kaggle-root/s$SLOT
L=/var/log/box/s$SLOT
NAME=rl-nb-s$SLOT
mkdir -p "$L" && : > "$L/phases.tsv"
exec > "$L/run.log" 2>&1
phase() { printf '%s\t%s\n' "$(date -u +%FT%TZ)" "$1" | tee -a "$L/phases.tsv"; timeout 30 gcloud storage cp "$L/phases.tsv" "$OUT/phases.tsv" >/dev/null 2>&1 || true; }
host_sync() { timeout 900 python3 "$R/code/rl_host_sync.py" once --campaign "$CAMPAIGN" --store "$STORE" \
                --root "$R/rollout" --results "$R/working/gtree-rollout" --vm "$VM" >> "$L/host.log" 2>&1 || true; }
sync_logs() {
  timeout 60 gcloud storage cp "$R/working/serve.log" "$R/working/nbconvert.log" "$OUT/" >/dev/null 2>&1 || true
  [ -f "$R/working/metrics.jsonl" ] && timeout 60 gcloud storage cp "$R/working/metrics.jsonl" "$OUT/" >/dev/null 2>&1 || true
  timeout 30 gcloud storage cp "$L/run.log" "$OUT/vm.log" >/dev/null 2>&1 || true
  timeout 30 gcloud storage cp "$L/host.log" "$OUT/host.log" >/dev/null 2>&1 || true
}
LOOP=""
ENDING=""
finish() {
  [ -n "$ENDING" ] && exit 0
  ENDING=1
  phase "ending ($1)"
  [ -n "$LOOP" ] && kill "$LOOP" 2>/dev/null
  docker rm -f "$NAME" >/dev/null 2>&1
  host_sync
  timeout 1800 gcloud storage rsync -r "$R/working/gtree-rollout" "$OUT/gtree-rollout" >/dev/null 2>&1 || true
  sync_logs
  phase "finish ($1)"
  exit 0
}
trap 'finish stopped' TERM INT
case "$CAMPAIGN" in ''|*[!A-Za-z0-9._-]*) finish bad_campaign;; esac
phase "start $RUN_ID box slot $SLOT card $GPU campaign $CAMPAIGN"
docker rm -f "$NAME" >/dev/null 2>&1
rm -rf "$R" && mkdir -p "$R/working/gtree-rollout" "$R/nb" "$R/rollout/jobs" "$R/rollout/policy" "$R/code"
gcloud storage cp "$CODE/rl_host_sync.py" "$CODE/gtree_store.py" "$CODE/gtree_ctx.py" "$R/code/" || finish code_download_failed
gcloud storage cat "$RL/policy/current.json" >/dev/null 2>&1 || finish no_policy_run_rl_loop_init_first
host_sync
[ -n "$(ls -A "$R/rollout/jobs" 2>/dev/null)" ] || finish no_jobs_staged
phase "jobs_staged $(find "$R/rollout/jobs" -name '*.json' | wc -l)"
( while true; do sleep 120; host_sync; sync_logs; done ) &
LOOP=$!
gcloud storage cp "$NB_OBJ" "$R/nb/notebook.ipynb" || finish notebook_download_failed

# the inputs: one download per prefix, shared by every slot (the first slot downloads, the others wait on the lock)
TAG=$(basename "$IN")
IND=/kaggle-in/$TAG
mkdir -p /kaggle-in
(
  flock -w 3600 9 || exit 1
  if [ ! -f "$IND/.ok" ]; then
    gcloud storage cat "$IN/_STAGED_OK" >/dev/null 2>&1 || exit 2
    rm -rf "$IND" && mkdir -p "$IND"
    gcloud storage rsync -r "$IN" "$IND" > "$L/input-rsync.log" 2>&1 || exit 3
    touch "$IND/.ok"
    # keep this input and the one before; slots of older rounds have ended (play and training take turns)
    ls -1dt /kaggle-in/*/ 2>/dev/null | tail -n +3 | xargs -r rm -rf
  fi
) 9> /kaggle-in/.lock
case $? in 0) ;; 2) finish inputs_not_staged;; 3) finish input_copy_failed;; *) finish input_lock_timeout;; esac
phase "inputs_ready $TAG"

for i in $(seq 1 120); do [ -n "$IMAGE" ] && docker image inspect "$IMAGE" >/dev/null 2>&1 && break; sleep 30; IMAGE=$(cat /var/lib/box/image 2>/dev/null); done
docker image inspect "$IMAGE" >/dev/null 2>&1 || finish image_missing
phase "image_ready $IMAGE"
GPU_OK=0
for i in $(seq 1 20); do
  docker run --rm --gpus "device=$GPU" --entrypoint nvidia-smi "$IMAGE" -L >/dev/null 2>&1 && { GPU_OK=1; break; }
  sleep 15
done
[ "$GPU_OK" = 1 ] || finish gpu_unavailable
phase gpu_ready
# Server-start watch: as rl-vm-startup.sh (one restart if SGLang dies before "ready to roll").
ATTEMPT=1
while :; do
  docker run -d --name "$NAME" --gpus "device=$GPU" --cpus 48 --memory 176g --network none --shm-size="$SHM" \
    --ulimit memlock=-1 \
    -v "$IND:/kaggle/input:ro" -v "$R/working:/kaggle/working" -v "$R/nb:/kaggle/nb:ro" \
    -v "$R/rollout:/kaggle/rollout:ro" \
    -w /kaggle/working --entrypoint bash "$IMAGE" -c \
    'jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=-1 --ExecutePreprocessor.kernel_name=python3 /kaggle/nb/notebook.ipynb --output-dir /kaggle/working --output __notebook__.ipynb' \
    > /dev/null || finish docker_run_failed
  OUTCOME=timeout
  DEAD=0
  for i in $(seq 1 180); do
    sleep 20
    if grep -q "ready to roll" "$R/working/serve.log" 2>/dev/null; then OUTCOME=ready; break; fi
    if grep -q -E "Scheduler hit an exception|Capture cuda graph failed|Received sigquit from a child|unrecognized arguments" "$R/working/serve.log" 2>/dev/null; then OUTCOME=server_failed; break; fi
    [ -n "$(docker ps -q -f name="^$NAME\$")" ] || { OUTCOME=exited; break; }
    if [ -s "$R/working/serve.log" ] && ! docker top "$NAME" -eo pid,args 2>/dev/null | grep -q -i sglang; then
      DEAD=$((DEAD + 1)); [ "$DEAD" -ge 3 ] && { OUTCOME=server_failed; break; }
    else
      DEAD=0
    fi
  done
  phase "server_${OUTCOME} attempt_$ATTEMPT"
  if [ "$OUTCOME" = exited ] && docker logs "$NAME" 2>&1 | grep -q "CUDA unavailable"; then OUTCOME=server_failed; fi
  if [ "$OUTCOME" = server_failed ]; then
    docker logs "$NAME" > "$R/working/nbconvert.log" 2>&1; docker rm -f "$NAME" >/dev/null 2>&1
    [ "$ATTEMPT" -ge 2 ] && finish server_failed_twice
    mkdir -p "$R/failed-attempt$ATTEMPT" && cp -a "$R/working/." "$R/failed-attempt$ATTEMPT/" && find "$R/working" -mindepth 1 -delete
    mkdir -p "$R/working/gtree-rollout"
    timeout 300 gcloud storage rsync -r "$R/failed-attempt$ATTEMPT" "$OUT/failed-attempt$ATTEMPT" >/dev/null 2>&1 || true
    ATTEMPT=$((ATTEMPT + 1))
    continue
  fi
  break
done
RC=$(docker wait "$NAME")
docker logs "$NAME" > "$R/working/nbconvert.log" 2>&1
finish "notebook_rc_$RC"
