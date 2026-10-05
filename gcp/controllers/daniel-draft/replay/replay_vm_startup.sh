#!/bin/bash
# Replay runner (4-Oct-2026, daniel-draft/replay; Slice and dice): daniel-run-vm-startup.sh + the saved request logs of
# arc3-replay-runs mounted read-only at /kaggle/replay, a host dir mounted at /kaggle/capture (the capture hook's output)
# that is synced to arc3-capture-prefix while the replay runs, and outputs under daniel-draft/replay/runs/ (not
# daniel-base/runs/: these are not scored runs). Everything below the next line is the original runner's comment.
# Daniel-base runner (1-Oct-2026, Son: "Daniel notebook is the base"): play dfranzen/arc-agi-3-milestone-2-solution
# on our own G4 (RTX PRO 6000) the way Kaggle runs it: Kaggle's notebook image, --network none, his exact inputs
# mounted at /kaggle/input (staged by stage-daniel-inputs-vm-startup.sh), the notebook executed top to bottom by
# nbconvert. The only notebook edit is one override cell after his "Customization hook" (build_daniel_notebook.py).
# Metadata: arc3-run-id, arc3-notebook-object (gs:// path of the .ipynb). Outputs: $OUT/working (live), $OUT/vm.log.
# Optional (2-Oct, giant336g 9-hour rehearsal): arc3-input-prefix (gs:// mirror of /kaggle/input; default Daniel's),
# arc3-working-gb (cap /kaggle/working at this size with a loop-mounted ext4, like Kaggle's ~20.9 GB), arc3-shm-size
# (docker --shm-size; default 64g, Kaggle's /dev/shm is ~93 GB). A host monitor writes RAM, disk and the top
# processes' memory / open files / threads every minute to $OUT/host-monitor.tsv.
# Powers off at the end; the operator deletes the stopped VM (the default service account cannot).
set -uo pipefail
exec > /var/log/daniel-run.log 2>&1
meta() { curl -s -H 'Metadata-Flavor: Google' "http://metadata.google.internal/computeMetadata/v1/instance/$1"; }
RUN_ID=$(meta attributes/arc3-run-id)
NB_OBJ=$(meta attributes/arc3-notebook-object)
IN=$(meta attributes/arc3-input-prefix); case "$IN" in gs://*) ;; *) IN=gs://cellens-ai-artifacts/arc3-duck/daniel-base/kaggle-input;; esac
WORKING_GB=$(meta attributes/arc3-working-gb); case "$WORKING_GB" in ''|*[!0-9.]*) WORKING_GB="";; esac
SHM=$(meta attributes/arc3-shm-size); case "$SHM" in [0-9]*g) ;; *) SHM=64g;; esac
OUT=gs://cellens-ai-artifacts/arc3-duck/daniel-draft/replay/runs/$RUN_ID
REPLAY_RUNS=$(meta attributes/arc3-replay-runs)
CAP=$(meta attributes/arc3-capture-prefix); case "$CAP" in gs://*) ;; *) CAP=gs://cellens-ai-artifacts/arc3-duck/daniel-draft/replay/captures/$RUN_ID;; esac
IMAGE_BYOD=gcr.io/kaggle-private-byod/python@sha256:57e612b484cf3df5026ee4dcc3cb176974b22b2bc0937fb1e16132a8be4cb13c
IMAGE_GPU=gcr.io/kaggle-gpu-images/python@sha256:37c64f7dd9c54116ecd1bcc88817c5469b88387388fade02bfa8bf3fc647d461
R=/kaggle-root
phase() { printf '%s\t%s\t%s\n' "$(date -u +%FT%TZ)" "$(cut -d' ' -f1 /proc/uptime)" "$1" | tee -a /var/log/daniel-phases.tsv; timeout 30 gcloud storage cp /var/log/daniel-phases.tsv "$OUT/phases.tsv" >/dev/null 2>&1 || true; }
sync_out() {
  timeout 300 gcloud storage rsync -r --delete-unmatched-destination-objects "$R/working" "$OUT/working" >/dev/null 2>&1 || true
  timeout 30 gcloud storage cp /var/log/daniel-run.log "$OUT/vm.log" >/dev/null 2>&1 || true
  [ -f /var/log/host-monitor.tsv ] && timeout 30 gcloud storage cp /var/log/host-monitor.tsv "$OUT/host-monitor.tsv" >/dev/null 2>&1 || true
}
sync_cap() {  # capture files are written once (tmp + rename): copy new ones, never delete
  timeout 7200 gcloud storage rsync -r -x '.*\.tmp$' "$R/capture" "$CAP" >/dev/null 2>&1 || true
}
finish() {
  phase "finish ($1)"
  sync_out
  sync_cap; sync_cap
  echo "$(ls $R/capture | grep -c mtpc) files $(du -sb $R/capture | cut -f1) bytes" > /var/log/capture-done.txt
  timeout 60 gcloud storage cp /var/log/capture-done.txt "$CAP/_DONE" >/dev/null 2>&1 || true
  phase "capture_synced $(cat /var/log/capture-done.txt)"
  shutdown -h now
  exit 0
}
phase "start $RUN_ID $(meta zone | awk -F/ '{print $NF}')"
( while true; do sleep 300; sync_out; done ) &
{ nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader; nproc; free -g; df -h /; \
  systemctl list-units --type=service --type=timer --no-pager | grep -i -E 'arc3|idle|watchdog' ; } > /var/log/vm-facts.txt 2>&1
timeout 30 gcloud storage cp /var/log/vm-facts.txt "$OUT/vm-facts.txt" >/dev/null 2>&1 || true
mkdir -p "$R/input" "$R/working" "$R/nb" "$R/replay" "$R/capture"
( while true; do sleep 180; sync_cap; done ) &
for RUNX in $(echo "$REPLAY_RUNS" | tr ',+' '  '); do
  mkdir -p "$R/replay/$RUNX"
  gcloud storage cp -q "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs/$RUNX/working/*_p0_requests.jsonl" "$R/replay/$RUNX/"     || finish "replay_logs_failed_$RUNX"
done
phase "replay_logs $(ls $R/replay/*/ | grep -c requests.jsonl) files $(du -sh $R/replay | cut -f1)"
if [ -n "$WORKING_GB" ]; then
  fallocate -l "${WORKING_GB}G" /kaggle-working.img && mkfs.ext4 -q -F /kaggle-working.img \
    && mount -o loop /kaggle-working.img "$R/working" && rmdir "$R/working/lost+found" 2>/dev/null
  df -h "$R/working" | tail -1 | tee -a /var/log/vm-facts.txt || finish working_cap_failed
fi
( while true; do
    {
      printf '%s\t' "$(date -u +%FT%TZ)"
      free -m | awk '/Mem:/{printf "ram_used_mb=%s\tram_avail_mb=%s\t", $3, $7} /Swap:/{printf "swap_used_mb=%s\t", $3}'
      df -BM --output=used,avail "$R/working" | tail -1 | awk '{printf "working_used=%s\tworking_avail=%s\t", $1, $2}'
      df -BM --output=used,avail /dev/shm | tail -1 | awk '{printf "host_shm_used=%s\t", $1}'
      ps -eo pid,rss,nlwp,comm --sort=-rss --no-headers | head -4 | while read -r pid rss thr comm; do
        printf 'p=%s:%s:rss_gb=%.1f:thr=%s:fds=%s\t' "$pid" "$comm" "$(awk -v r="$rss" 'BEGIN{print r/1048576}')" "$thr" "$(ls /proc/$pid/fd 2>/dev/null | wc -l)"
      done
      printf 'fds_total=%s\n' "$(ls /proc/[0-9]*/fd 2>/dev/null | wc -l)"
    } >> /var/log/host-monitor.tsv 2>/dev/null
    sleep 60
  done ) &
( while true; do sleep 300; timeout 30 gcloud storage cp /var/log/host-monitor.tsv "$OUT/host-monitor.tsv" >/dev/null 2>&1; done ) &
gcloud storage cp "$NB_OBJ" "$R/nb/notebook.ipynb" || finish notebook_download_failed
# The image pull starts first, beside the wait for the staged inputs and the input copy. Kaggle pins this notebook
# to its BYOD image; fall back to the Kaggle GPU image digest our own Kaggle rehearsals used (Ubuntu 22.04,
# Python 3.12) if the BYOD registry refuses the pull.
( timeout 2400 docker pull "$IMAGE_BYOD" && echo "$IMAGE_BYOD" > /var/log/image-used.txt \
  || { timeout 2400 docker pull "$IMAGE_GPU" && echo "$IMAGE_GPU" > /var/log/image-used.txt; } ) > /var/log/image-pull.log 2>&1 &
P1=$!
for i in $(seq 1 90); do gcloud storage cat "$IN/_STAGED_OK" >/dev/null 2>&1 && break; sleep 60; done
gcloud storage cat "$IN/_STAGED_OK" >/dev/null 2>&1 || finish inputs_not_staged_after_90min
phase inputs_staged
gcloud storage rsync -r "$IN" "$R/input" > /var/log/input-rsync.log 2>&1 || finish input_copy_failed
phase inputs_copied
/usr/bin/python3 - "$R/input" > /var/log/input-check.txt 2>&1 <<'PY' || finish input_check_failed
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
man = json.loads((root / "DANIEL_BASE_MANIFEST.json").read_text())["files"]
bad = [k for k, v in man.items() if not (root / k).is_file() or (root / k).stat().st_size != v["size"]]
print("manifest files", len(man), "missing or wrong size", len(bad), bad[:10])
sys.exit(1 if bad else 0)
PY
wait "$P1" || finish image_pull_failed
IMAGE=$(cat /var/log/image-used.txt)
docker image inspect "$IMAGE" --format '{{.Id}} {{json .RepoDigests}}' > /var/log/image-id.txt
phase "image_ready $IMAGE"
timeout 30 gcloud storage cp /var/log/image-pull.log /var/log/image-id.txt /var/log/input-check.txt "$OUT/" >/dev/null 2>&1 || true
# Pre-flight inside the image: GPU visible, Python 3.12, jupyter present, network really off.
docker run --rm --gpus all --network none --entrypoint bash "$IMAGE" -c \
  'nvidia-smi -L && python3 --version && python3 -c "import sys; assert sys.version_info[:2]==(3,12)" && jupyter nbconvert --version && head -2 /etc/os-release && (getent hosts pypi.org && echo NETWORK_ON || echo network_off)' \
  > /var/log/preflight.txt 2>&1 || finish preflight_failed
grep -q network_off /var/log/preflight.txt || finish network_not_off
timeout 30 gcloud storage cp /var/log/preflight.txt "$OUT/" >/dev/null 2>&1 || true
phase preflight_ok
# Kaggle mounts read-only inputs under a writable /kaggle; the notebook writes /kaggle/harness-changes.patch and
# /kaggle/taaf-kaggle-source-share, and Kaggle executes it with nbconvert from /kaggle/working.
# Startup flake (1-Oct, daniel-noborder-a): his SGLang launcher sets TORCHINDUCTOR_COMPILE_THREADS=8, and in Kaggle's
# image an inductor compile worker can fail with "Could not find an active GPU backend" during CUDA-graph capture
# (our 27-Sep Kaggle packaging hit the same). His notebook then plays on with a dead server. So the server's startup
# is watched: if it dies before "ready to roll", the container is removed, that attempt's working dir is kept as
# failed-attempt<N> (also in GCS), and the notebook starts again from scratch on the same inputs, once.
ATTEMPT=1
while :; do
  docker run -d --name daniel-nb --gpus all --network none --shm-size="$SHM" --ulimit memlock=-1 \
    -v "$R/input:/kaggle/input:ro" -v "$R/working:/kaggle/working" -v "$R/nb:/kaggle/nb:ro"     -v "$R/replay:/kaggle/replay:ro" -v "$R/capture:/kaggle/capture" \
    -w /kaggle/working --entrypoint bash "$IMAGE" -c \
    'jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=-1 --ExecutePreprocessor.kernel_name=python3 /kaggle/nb/notebook.ipynb --output-dir /kaggle/working --output __notebook__.ipynb' \
    > /dev/null || finish docker_run_failed
  OUTCOME=timeout
  DEAD=0
  for i in $(seq 1 180); do
    sleep 20
    if grep -q "ready to roll" "$R/working/serve.log" 2>/dev/null; then OUTCOME=ready; break; fi
    if grep -q -E "Scheduler hit an exception|Capture cuda graph failed|Received sigquit from a child" "$R/working/serve.log" 2>/dev/null; then OUTCOME=server_failed; break; fi
    [ -n "$(docker ps -q -f name=daniel-nb)" ] || { OUTCOME=exited; break; }
    # Any other startup death (3-Oct: an arg-check AssertionError for --kv-cache-dtype nvfp4 matched none of the lines
    # above, and the notebook played 2 h on a dead server): once serve.log exists, the SGLang process must be alive.
    # `docker top` needs a PID column in its ps output (3-Oct: `-eo args` returned nothing, so this counted a healthy,
    # loading server as dead after 3 checks and killed every run ~60 s into weight loading); keep pid in the list.
    if [ -s "$R/working/serve.log" ] && ! docker top daniel-nb -eo pid,args 2>/dev/null | grep -q -i sglang; then
      DEAD=$((DEAD + 1)); [ "$DEAD" -ge 3 ] && { OUTCOME=server_failed; break; }
    else
      DEAD=0
    fi
  done
  phase "server_${OUTCOME} attempt_$ATTEMPT"
  if [ "$OUTCOME" = server_failed ] && [ "$ATTEMPT" -ge 2 ]; then
    # second failed start: stop instead of letting the notebook play on a dead server
    docker logs daniel-nb > "$R/working/nbconvert.log" 2>&1; docker rm -f daniel-nb >/dev/null 2>&1
    finish "server_failed_twice"
  fi
  if [ "$OUTCOME" = server_failed ] && [ "$ATTEMPT" -lt 2 ]; then
    docker logs daniel-nb > "$R/working/nbconvert.log" 2>&1; docker rm -f daniel-nb >/dev/null 2>&1
    # copy + clear rather than mv: /kaggle/working may be a mount point (arc3-working-gb)
    mkdir -p "$R/failed-attempt$ATTEMPT" && cp -a "$R/working/." "$R/failed-attempt$ATTEMPT/" && find "$R/working" -mindepth 1 -delete
    timeout 300 gcloud storage rsync -r "$R/failed-attempt$ATTEMPT" "$OUT/failed-attempt$ATTEMPT" >/dev/null 2>&1 || true
    ATTEMPT=$((ATTEMPT + 1))
    continue
  fi
  break
done
RC=$(docker wait daniel-nb)
docker logs daniel-nb > "$R/working/nbconvert.log" 2>&1
phase "notebook_rc_$RC"
docker rm daniel-nb >/dev/null 2>&1 || true
finish "notebook_rc_$RC"
