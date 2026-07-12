#!/bin/bash
# Spot-safe startup for the G4 duck-harness run. Idempotent: a preempted VM is
# recreated by the MIG, re-runs this script, pulls prior state from GCS, and
# plays only the games that never reached a terminal state.
set -uo pipefail
exec > >(tee -a /var/log/arc3-startup.log) 2>&1
echo "=== arc3 startup $(date -u +%FT%TZ) ==="
export HOME="${HOME:-/root}"

BUCKET=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-bucket")
RUN_ID=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-run-id")
CODE_OBJ=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-code-object" || echo code/arc3-code.tgz)
CFG=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-config" || echo configs/gcp.qwen36.duck.json)
MIG=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-mig" || echo arc3-g4-duck)
ZONE=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/zone" | awk -F/ '{print $NF}')
echo "bucket=$BUCKET run_id=$RUN_ID zone=$ZONE code=$CODE_OBJ cfg=$CFG mig=$MIG"

mkdir -p /opt/arc3
cd /opt/arc3

# ---- crash-loop guard: too many boots without finishing means something is
# systematically broken; stop burning spot dollars and leave the logs. --------
ATTEMPTS=$( (gcloud storage cat "$BUCKET/$RUN_ID/attempts" 2>/dev/null || echo 0) | tr -dc '0-9' )
ATTEMPTS=$(( ${ATTEMPTS:-0} + 1 ))
echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/attempts"
echo "boot attempt #$ATTEMPTS"
if [ "$ATTEMPTS" -gt 8 ]; then
  echo failed | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"
  gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE" || true
  exit 1
fi

# ---- early log sync: visibility from minute one, before install/model -------
( while true; do
    gcloud storage cp /var/log/arc3-startup.log "$BUCKET/$RUN_ID/startup-$(hostname).log" >/dev/null 2>&1
    sleep 60
  done ) &
EARLY_SYNC_PID=$!

# ---- code -------------------------------------------------------------------
gcloud storage cp "$BUCKET/$CODE_OBJ" /tmp/arc3-code.tgz
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
  # Policy: VMs never download from HF. Seed the bucket first with
  # gcp/upload_model.sh; a missing snapshot is a non-retryable failure.
  echo "MODEL SNAPSHOT MISSING in GCS ($MODEL_DIR_MARKER) -- refusing to download from HF"
  echo failed | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"
  exit 1
fi
export HF_HUB_OFFLINE=1

# ---- deps -------------------------------------------------------------------
apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq build-essential ffmpeg ninja-build
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
cd /opt/arc3/ARC3-Inference
export CONFIG_PATH="$CFG"
# Checkpoint benchmark.json every 2 min instead of 10 so a preemption replays
# at most ~2 min of already-terminal games, not ~12.
export TAAF_PERIODIC_SAVE_INTERVAL_S=120
make install-a108
# HF_HUB_OFFLINE=1: the snapshot came from GCS; download-model only verifies it.
make download-model || true

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
if ! make check-server; then
  echo "SERVER FAILED TO START -- aborting attempt $ATTEMPTS"
  gcloud storage cp .cache/arc3_runtime/arc3-inference-server.log "$BUCKET/$RUN_ID/serverlog-$(hostname)-$ATTEMPTS.log" 2>/dev/null || true
  echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/serverfail"
  exit 1
fi

# ---- resume: play only games with no terminal state in any prior shard ------
mkdir -p /tmp/prior
gcloud storage rsync -r -x '^(?!.*benchmark\.json$).*' "$BUCKET/$RUN_ID/runs" /tmp/prior >/dev/null 2>&1 || true
REMAINING=$(./.venv/bin/python /opt/arc3/gcp/remaining_games.py /tmp/prior) || REMAINING="ERROR"
[ -z "$REMAINING" ] && REMAINING="ERROR"
echo "remaining games: $REMAINING"
if [ "$REMAINING" = "ERROR" ]; then
  echo "resume check failed -- refusing to guess; marking FAILED and stopping"
  echo failed | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"
  gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE" || true
  exit 1
elif [ "$REMAINING" = "NONE" ]; then
  echo "nothing left to play"
else
  make interactive GAME="$REMAINING" RUN_NAME="$RUN_ID-$(date -u +%H%M%S)" || echo "run exited $?"
fi

# ---- teardown: final sync, DONE marker, scale the MIG to zero ----------------
gcloud storage rsync -r runs "$BUCKET/$RUN_ID/runs"
gcloud storage rsync -r -x '^(?!.*benchmark\.json$).*' "$BUCKET/$RUN_ID/runs" /tmp/prior >/dev/null 2>&1 || true
FINAL_REMAINING=$(./.venv/bin/python /opt/arc3/gcp/remaining_games.py /tmp/prior) || FINAL_REMAINING="ERROR"
[ -z "$FINAL_REMAINING" ] && FINAL_REMAINING="ERROR"
if [ "$FINAL_REMAINING" = "NONE" ]; then
  echo done | gcloud storage cp - "$BUCKET/$RUN_ID/DONE"
  echo "run complete; scaling MIG to zero"
  gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE" || true
else
  echo "games still remaining after exit: $FINAL_REMAINING -- leaving MIG up for retry"
fi
