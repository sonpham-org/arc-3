#!/bin/bash
# Mid-tree rollout runner for ONE GPU VM (3-Oct-2026, Son: "sampling from the middle of the tree and then roll out").
# STRUCTURE ONLY: not launched yet. Follows daniel-base-20261001/runner/daniel-run-vm-startup.sh (Kaggle's image,
# --network none, his inputs at /kaggle/input, nbconvert top to bottom) with three differences:
#   1. the queue: runner/stage_jobs.py copies the jobs and their source logs (request / event / coach logs) from
#      $QUEUE to $R/rollout, mounted read-only at /kaggle/rollout (the container has no network);
#   2. the notebook is a build with our cells (build_port.py -> build_daniel_notebook.py --early early.py
#      --override override.py, env ARC3_ROLLOUT=1 set in the port cell); his run cell then awaits bm.run, which
#      rollout_driver.bind() replaced with the job queue (lanes = his concurrency unless ARC3_ROLLOUT_LANES);
#   3. outputs: /kaggle/working/gtree-rollout/<job>/k<k>/ (result.json, rollout.jsonl, requests.jsonl, artifacts/,
#      transcripts/) synced to $QUEUE/results/$VM/ every 5 minutes and at the end. Publishing the records to the tree
#      is a separate step on the operator side (gtree-ingest put_bundle), never from the VM, and never a fenced game.
# Metadata: arc3-run-id, arc3-notebook-object, arc3-rollout-queue (gs://.../arc3-gtree/rollouts/<campaign>),
#           optional arc3-input-prefix (his inputs mirror; default the daniel-base one).
set -uo pipefail
exec > /var/log/gtree-rollout.log 2>&1
meta() { curl -s -H 'Metadata-Flavor: Google' "http://metadata.google.internal/computeMetadata/v1/instance/$1"; }
RUN_ID=$(meta attributes/arc3-run-id)
NB_OBJ=$(meta attributes/arc3-notebook-object)
QUEUE=$(meta attributes/arc3-rollout-queue)
VM=$(meta name)
IN=$(meta attributes/arc3-input-prefix); case "$IN" in gs://*) ;; *) IN=gs://cellens-ai-artifacts/arc3-duck/daniel-base/kaggle-input;; esac
OUT="$QUEUE/results/$VM"
CODE=gs://cellens-ai-artifacts/arc3-gtree/rollout-code      # stage_jobs.py (pushed by the operator)
IMAGE_BYOD=gcr.io/kaggle-private-byod/python@sha256:57e612b484cf3df5026ee4dcc3cb176974b22b2bc0937fb1e16132a8be4cb13c
IMAGE_GPU=gcr.io/kaggle-gpu-images/python@sha256:37c64f7dd9c54116ecd1bcc88817c5469b88387388fade02bfa8bf3fc647d461
R=/kaggle-root
phase() { printf '%s\t%s\n' "$(date -u +%FT%TZ)" "$1" | tee -a /var/log/rollout-phases.tsv; timeout 30 gcloud storage cp /var/log/rollout-phases.tsv "$OUT/phases.tsv" >/dev/null 2>&1 || true; }
sync_out() {
  timeout 300 gcloud storage rsync -r "$R/working/gtree-rollout" "$OUT/gtree-rollout" >/dev/null 2>&1 || true
  timeout 60 gcloud storage cp "$R/working/serve.log" "$R/working/nbconvert.log" "$OUT/" >/dev/null 2>&1 || true
  timeout 30 gcloud storage cp /var/log/gtree-rollout.log "$OUT/vm.log" >/dev/null 2>&1 || true
}
finish() { phase "finish ($1)"; sync_out; shutdown -h now; exit 0; }
case "$QUEUE" in gs://*) ;; *) finish no_queue;; esac
phase "start $RUN_ID $VM"
( while true; do sleep 300; sync_out; done ) &
mkdir -p "$R/input" "$R/working" "$R/nb" "$R/rollout" /opt/gtree-rollout
gcloud storage cp "$NB_OBJ" "$R/nb/notebook.ipynb" || finish notebook_download_failed
( timeout 2400 docker pull "$IMAGE_BYOD" && echo "$IMAGE_BYOD" > /var/log/image-used.txt \
  || { timeout 2400 docker pull "$IMAGE_GPU" && echo "$IMAGE_GPU" > /var/log/image-used.txt; } ) > /var/log/image-pull.log 2>&1 &
P1=$!
gcloud storage cat "$IN/_STAGED_OK" >/dev/null 2>&1 || finish inputs_not_staged
gcloud storage rsync -r "$IN" "$R/input" > /var/log/input-rsync.log 2>&1 || finish input_copy_failed
phase inputs_copied
gcloud storage cp "$CODE/stage_jobs.py" /opt/gtree-rollout/ || finish code_download_failed
/usr/bin/python3 /opt/gtree-rollout/stage_jobs.py "$QUEUE" "$R/rollout" || finish no_jobs_staged
timeout 30 gcloud storage cp "$R/rollout/stage-report.json" "$OUT/" >/dev/null 2>&1 || true
phase "jobs_staged $(ls "$R/rollout/jobs" | wc -l)"
wait "$P1" || finish image_pull_failed
IMAGE=$(cat /var/log/image-used.txt)
phase "image_ready $IMAGE"
# The same server-start watch as daniel-run-vm-startup.sh (one restart on a failed SGLang start) belongs here; left
# out of this structure-only copy. ARC3_ROLLOUT and the lanes are set in the notebook's port cell (build_port.py --env).
docker run -d --name gtree-nb --gpus all --network none --shm-size=64g --ulimit memlock=-1 \
  -v "$R/input:/kaggle/input:ro" -v "$R/working:/kaggle/working" -v "$R/nb:/kaggle/nb:ro" \
  -v "$R/rollout:/kaggle/rollout:ro" \
  -w /kaggle/working --entrypoint bash "$IMAGE" -c \
  'jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=-1 --ExecutePreprocessor.kernel_name=python3 /kaggle/nb/notebook.ipynb --output-dir /kaggle/working --output __notebook__.ipynb' \
  > /dev/null || finish docker_run_failed
phase notebook_started
RC=$(docker wait gtree-nb)
docker logs gtree-nb > "$R/working/nbconvert.log" 2>&1
docker rm gtree-nb >/dev/null 2>&1 || true
finish "notebook_rc_$RC"
