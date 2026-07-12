#!/bin/bash
# Spot-safe startup for the G4 duck-harness run. Idempotent: a preempted VM is
# recreated by the MIG, re-runs this script, pulls prior state from GCS, and
# plays only the games that never reached a terminal state.
set -uo pipefail
exec > >(tee -a /var/log/arc3-startup.log) 2>&1
echo "=== arc3 startup $(date -u +%FT%TZ) ==="

BUCKET=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-bucket")
RUN_ID=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-run-id")
ZONE=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/zone" | awk -F/ '{print $NF}')
echo "bucket=$BUCKET run_id=$RUN_ID zone=$ZONE"

mkdir -p /opt/arc3
cd /opt/arc3

# ---- crash-loop guard: too many boots without finishing means something is
# systematically broken; stop burning spot dollars and leave the logs. --------
ATTEMPTS=$( (gcloud storage cat "$BUCKET/$RUN_ID/attempts" 2>/dev/null || echo 0) | tr -dc '0-9' )
ATTEMPTS=$(( ${ATTEMPTS:-0} + 1 ))
echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/attempts"
echo "boot attempt #$ATTEMPTS"
if [ "$ATTEMPTS" -gt 6 ]; then
  echo failed | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"
  gcloud compute instance-groups managed resize arc3-g4-duck --size=0 --zone="$ZONE" || true
  exit 1
fi

# ---- code -------------------------------------------------------------------
gcloud storage cp "$BUCKET/code/arc3-code.tgz" /tmp/arc3-code.tgz
tar xzf /tmp/arc3-code.tgz -C /opt/arc3
echo "code unpacked: $(ls /opt/arc3)"

# ---- model: GCS snapshot if present, else HF (then stash for next boot) -----
export HF_HOME=/opt/arc3/hf
MODEL_DIR_MARKER="$BUCKET/model/Qwen3.6-27B-FP8/.complete"
if gcloud storage ls "$MODEL_DIR_MARKER" >/dev/null 2>&1; then
  echo "pulling model snapshot from GCS"
  mkdir -p "$HF_HOME/hub"
  gcloud storage rsync -r "$BUCKET/model/Qwen3.6-27B-FP8/hub" "$HF_HOME/hub"
else
  echo "no GCS snapshot; will download from HF during install, then stash"
  NEED_MODEL_STASH=1
fi

# ---- deps -------------------------------------------------------------------
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
cd /opt/arc3/ARC3-Inference
export CONFIG_PATH=configs/gcp.qwen36.duck.json
# Checkpoint benchmark.json every 2 min instead of 10 so a preemption replays
# at most ~2 min of already-terminal games, not ~12.
export TAAF_PERIODIC_SAVE_INTERVAL_S=120
make install-a108
make download-model
if [ "${NEED_MODEL_STASH:-0}" = "1" ]; then
  echo "stashing model snapshot to GCS for future boots"
  gcloud storage rsync -r "$HF_HOME/hub" "$BUCKET/model/Qwen3.6-27B-FP8/hub" && \
    (echo done | gcloud storage cp - "$MODEL_DIR_MARKER") || echo "stash failed (non-fatal)"
fi

# ---- continuous log sync (survives everything below) ------------------------
mkdir -p runs
( while true; do
    gcloud storage rsync -r runs "$BUCKET/$RUN_ID/runs" >/dev/null 2>&1
    gcloud storage cp /var/log/arc3-startup.log "$BUCKET/$RUN_ID/startup-$(hostname).log" >/dev/null 2>&1
    sleep 120
  done ) &
SYNC_PID=$!
echo "log sync loop pid=$SYNC_PID"

# ---- server -----------------------------------------------------------------
make server SERVER_START_TIMEOUT=1800 SERVER_TAIL_ON_WAIT=false
make check-server

# ---- resume: play only games with no terminal state in any prior shard ------
mkdir -p /tmp/prior
gcloud storage rsync -r -x '^(?!.*benchmark\.json$).*' "$BUCKET/$RUN_ID/runs" /tmp/prior >/dev/null 2>&1 || true
REMAINING=$(./.venv/bin/python /opt/arc3/gcp/remaining_games.py /tmp/prior)
echo "remaining games: $REMAINING"
if [ -z "$REMAINING" ]; then
  echo "nothing left to play"
else
  make interactive GAME="$REMAINING" RUN_NAME="$RUN_ID-$(date -u +%H%M%S)" || echo "run exited $?"
fi

# ---- teardown: final sync, DONE marker, scale the MIG to zero ----------------
gcloud storage rsync -r runs "$BUCKET/$RUN_ID/runs"
gcloud storage rsync -r -x '^(?!.*benchmark\.json$).*' "$BUCKET/$RUN_ID/runs" /tmp/prior >/dev/null 2>&1 || true
FINAL_REMAINING=$(./.venv/bin/python /opt/arc3/gcp/remaining_games.py /tmp/prior)
if [ -z "$FINAL_REMAINING" ]; then
  echo done | gcloud storage cp - "$BUCKET/$RUN_ID/DONE"
  echo "run complete; scaling MIG to zero"
  gcloud compute instance-groups managed resize arc3-g4-duck --size=0 --zone="$ZONE" || true
else
  echo "games still remaining after exit: $FINAL_REMAINING -- leaving MIG up for retry"
fi
