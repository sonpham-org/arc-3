#!/bin/bash
# RL rollout server on ONE GPU VM (3-Oct-2026, Son: "take advantage of the high throughput in the 10 lanes to do
# sampled rollouts off policy"). STRUCTURE ONLY: written and read, never launched yet.
# The notebook is the best-combo build with the rollout server bound (build_rl_notebook.py: t06 + coach hooks + host
# tier + state snapshots + ARC3_ROLLOUT=server); it runs exactly like daniel-run-vm-startup.sh runs Daniel's notebook
# (Kaggle's image, --network none, his inputs at /kaggle/input, nbconvert, the same server-start watch) with:
#   /kaggle/rollout (read-only)  jobs/round-NNNN/*.json, src/ (staged logs, snapshots, origin requests),
#                                policy/current.json, STOP -- written by the host loop below while the notebook runs
#   /kaggle/working/gtree-rollout  <job>/{restore,k0..k4}/ (result.json, master.jsonl.gz, state/, gtree-store/, ...)
#   runner/rl_host_sync.py loop  every 2 min: stage new jobs + sources, sync the policy, mirror STOP, upload finished
#                                tries (masters, contexts, snapshots, state index) to gs://.../arc3-gtree/v1
# The server stops at its budget (ARC3_ROLLOUT_BUDGET_S, baked into the build, default 2 h) or at STOP; then a final
# host pass uploads the rest and the VM powers off. Publishing to the site is the operator's (ingest.py republish).
# Metadata: arc3-run-id, arc3-notebook-object (the RL build), arc3-campaign, optional arc3-input-prefix (default the
# daniel-draft mirror: tuned drafter included), arc3-shm-size.
set -uo pipefail
exec > /var/log/rl-run.log 2>&1
meta() { curl -s -H 'Metadata-Flavor: Google' "http://metadata.google.internal/computeMetadata/v1/instance/$1"; }
RUN_ID=$(meta attributes/arc3-run-id)
NB_OBJ=$(meta attributes/arc3-notebook-object)
CAMPAIGN=$(meta attributes/arc3-campaign)
VM=$(meta name)
IN=$(meta attributes/arc3-input-prefix); case "$IN" in gs://*) ;; *) IN=gs://cellens-ai-artifacts/arc3-duck/daniel-draft/kaggle-input;; esac
SHM=$(meta attributes/arc3-shm-size); case "$SHM" in [0-9]*g) ;; *) SHM=64g;; esac
STORE=gs://cellens-ai-artifacts/arc3-gtree/v1
RL=$STORE/rl/$CAMPAIGN
OUT=$RL/runs/$RUN_ID
CODE=gs://cellens-ai-artifacts/arc3-gtree/rollout-code       # rl_host_sync.py, gtree_store.py, gtree_ctx.py
IMAGE_BYOD=gcr.io/kaggle-private-byod/python@sha256:57e612b484cf3df5026ee4dcc3cb176974b22b2bc0937fb1e16132a8be4cb13c
IMAGE_GPU=gcr.io/kaggle-gpu-images/python@sha256:37c64f7dd9c54116ecd1bcc88817c5469b88387388fade02bfa8bf3fc647d461
R=/kaggle-root
phase() { printf '%s\t%s\n' "$(date -u +%FT%TZ)" "$1" | tee -a /var/log/rl-phases.tsv; timeout 30 gcloud storage cp /var/log/rl-phases.tsv "$OUT/phases.tsv" >/dev/null 2>&1 || true; }
host_sync() { timeout 900 /usr/bin/python3 /opt/gtree-rollout/rl_host_sync.py once --campaign "$CAMPAIGN" --store "$STORE" \
                --root "$R/rollout" --results "$R/working/gtree-rollout" --vm "$VM" >> /var/log/rl-host.log 2>&1 || true; }
sync_logs() {
  timeout 60 gcloud storage cp "$R/working/serve.log" "$R/working/nbconvert.log" "$OUT/" >/dev/null 2>&1 || true
  # the server's own counters, every 60 s (the base build's /metrics scraper cell): tokens/s and lane fill per minute
  [ -f "$R/working/metrics.jsonl" ] && timeout 60 gcloud storage cp "$R/working/metrics.jsonl" "$OUT/" >/dev/null 2>&1 || true
  timeout 30 gcloud storage cp /var/log/rl-run.log "$OUT/vm.log" >/dev/null 2>&1 || true
  timeout 30 gcloud storage cp /var/log/rl-host.log "$OUT/host.log" >/dev/null 2>&1 || true
}
finish() {
  phase "finish ($1)"
  host_sync
  # everything else of the tries (request logs, transcripts) for later restarts and audits; no request log is lost
  timeout 1800 gcloud storage rsync -r "$R/working/gtree-rollout" "$OUT/gtree-rollout" >/dev/null 2>&1 || true
  sync_logs
  shutdown -h now
  exit 0
}
case "$CAMPAIGN" in ''|*[!A-Za-z0-9._-]*) finish bad_campaign;; esac
phase "start $RUN_ID $VM campaign $CAMPAIGN"
mkdir -p "$R/input" "$R/working/gtree-rollout" "$R/nb" "$R/rollout/jobs" "$R/rollout/policy" /opt/gtree-rollout
gcloud storage cp "$CODE/rl_host_sync.py" "$CODE/gtree_store.py" "$CODE/gtree_ctx.py" /opt/gtree-rollout/ || finish code_download_failed
gcloud storage cat "$RL/policy/current.json" >/dev/null 2>&1 || finish no_policy_run_rl_loop_init_first
host_sync                                                     # first jobs + policy before the notebook starts
[ -n "$(ls -A "$R/rollout/jobs" 2>/dev/null)" ] || finish no_jobs_staged
phase "jobs_staged $(find "$R/rollout/jobs" -name '*.json' | wc -l)"
( while true; do sleep 120; host_sync; sync_logs; done ) &
gcloud storage cp "$NB_OBJ" "$R/nb/notebook.ipynb" || finish notebook_download_failed
( timeout 2400 docker pull "$IMAGE_BYOD" && echo "$IMAGE_BYOD" > /var/log/image-used.txt \
  || { timeout 2400 docker pull "$IMAGE_GPU" && echo "$IMAGE_GPU" > /var/log/image-used.txt; } ) > /var/log/image-pull.log 2>&1 &
P1=$!
gcloud storage cat "$IN/_STAGED_OK" >/dev/null 2>&1 || finish inputs_not_staged
gcloud storage rsync -r "$IN" "$R/input" > /var/log/input-rsync.log 2>&1 || finish input_copy_failed
phase inputs_copied
wait "$P1" || finish image_pull_failed
IMAGE=$(cat /var/log/image-used.txt)
phase "image_ready $IMAGE"
# GPU visible to a container before the notebook starts (3-Oct rl2: 2 of 10 VMs died "CUDA unavailable" at boot)
GPU_OK=0
for i in $(seq 1 20); do
  if nvidia-smi -L >/dev/null 2>&1 && docker run --rm --gpus all --entrypoint nvidia-smi "$IMAGE" -L >/dev/null 2>&1; then
    GPU_OK=1; break
  fi
  sleep 15
done
[ "$GPU_OK" = 1 ] || finish gpu_unavailable
phase gpu_ready
# Server-start watch: the same as daniel-run-vm-startup.sh (one restart if SGLang dies before "ready to roll").
ATTEMPT=1
while :; do
  docker run -d --name rl-nb --gpus all --network none --shm-size="$SHM" --ulimit memlock=-1 \
    -v "$R/input:/kaggle/input:ro" -v "$R/working:/kaggle/working" -v "$R/nb:/kaggle/nb:ro" \
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
    [ -n "$(docker ps -q -f name=rl-nb)" ] || { OUTCOME=exited; break; }
    if [ -s "$R/working/serve.log" ] && ! docker top rl-nb -eo pid,args 2>/dev/null | grep -q -i sglang; then
      DEAD=$((DEAD + 1)); [ "$DEAD" -ge 3 ] && { OUTCOME=server_failed; break; }
    else
      DEAD=0
    fi
  done
  phase "server_${OUTCOME} attempt_$ATTEMPT"
  # the notebook's CUDA check failed although the host saw the GPU: one more attempt, like a server failure
  if [ "$OUTCOME" = exited ] && docker logs rl-nb 2>&1 | grep -q "CUDA unavailable"; then OUTCOME=server_failed; fi
  if [ "$OUTCOME" = server_failed ]; then
    docker logs rl-nb > "$R/working/nbconvert.log" 2>&1; docker rm -f rl-nb >/dev/null 2>&1
    [ "$ATTEMPT" -ge 2 ] && finish server_failed_twice
    mkdir -p "$R/failed-attempt$ATTEMPT" && cp -a "$R/working/." "$R/failed-attempt$ATTEMPT/" && find "$R/working" -mindepth 1 -delete
    mkdir -p "$R/working/gtree-rollout"
    timeout 300 gcloud storage rsync -r "$R/failed-attempt$ATTEMPT" "$OUT/failed-attempt$ATTEMPT" >/dev/null 2>&1 || true
    ATTEMPT=$((ATTEMPT + 1))
    continue
  fi
  break
done
RC=$(docker wait rl-nb)
docker logs rl-nb > "$R/working/nbconvert.log" 2>&1
docker rm rl-nb >/dev/null 2>&1 || true
finish "notebook_rc_$RC"
