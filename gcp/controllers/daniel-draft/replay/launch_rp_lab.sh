#!/bin/bash
# Launch one replay-data lab VM (4-Oct-2026): launch_rp_lab.sh <vm name arc3-drep-...> "<name=gs://cap+name=gs://cap>" <disk GB> <zone>...
# RP_MACHINE=g4-standard-192 RP_GPUS=4 (optional env): a 4-GPU box, jobs run under torchrun.
# RP_INIT=gs://.../<job>.draft_ft.pt (optional env): starting checkpoint, plan args $INIT.
# Uploads the trainer code (LF) to gs://.../daniel-draft/replay/code/ first. Delete the VM by exact name when done.
set -uo pipefail
NAME=$1 CAPS=$2 DISK=$3; shift 3
HERE=/d/codex-work/daniel-draft/replay
MTP=/d/codex-work/arc3-sglang-parking/gcp/controllers/sglang-scored/lobotomy/mtp
export CLOUDSDK_PYTHON='C:\python312\python.exe'
"$HERE/upload_code.sh" $MTP/train_draft.py $MTP/capture_io.py $MTP/draft_torch.py $MTP/replay_rows.py $MTP/verify_draft.py \
  /d/codex-work/daniel-draft/lab/build_daniel_ckpt.py "$HERE/compare_live_replay.py" "$HERE/check_replay_capture.py" "$HERE/prune_held.py" "$HERE/test_aux.py" > /dev/null || exit 1
tr -d '\r' < "$HERE/rp_lab_worker.sh" > /tmp/rp_lab_worker.lf.sh
for ZONE in "$@"; do
  # us-central1: only after asking Son / the RL thread that it is free (Son 5-Oct); then ALLOW_US_CENTRAL1=1
  case "$ZONE" in us-central1-*) [ "${ALLOW_US_CENTRAL1:-0}" = 1 ] || { echo "$ZONE: skipped (ask first; ALLOW_US_CENTRAL1=1 once free)"; continue; };; esac
  if gcloud compute instances create "$NAME" --zone "$ZONE" --machine-type ${RP_MACHINE:-g4-standard-48} \
      --image arc3-sglang-sm120-recovery-20260926 --image-project cellensml \
      --boot-disk-size ${DISK}GB --boot-disk-type hyperdisk-balanced \
      --boot-disk-provisioned-iops 16000 --boot-disk-provisioned-throughput 1200 \
      --provisioning-model SPOT --instance-termination-action DELETE --max-run-duration 12h \
      --maintenance-policy TERMINATE --scopes cloud-platform --labels purpose=arc3-daniel-draft,owner-task=claude-replay \
      --metadata "rp-caps=$CAPS${RP_INIT:+,rp-init=$RP_INIT}${RP_GPUS:+,rp-gpus=$RP_GPUS}" --metadata-from-file "startup-script=/tmp/rp_lab_worker.lf.sh" < /dev/null > "/tmp/launch-$NAME.log" 2>&1; then
    echo "launched $NAME in $ZONE"; exit 0
  fi
  echo "$ZONE: $(grep -o -m1 'STOCKOUT\|QUOTA[A-Z_]*\|already exists\|ZONE_RESOURCE_POOL_EXHAUSTED\|does not have enough resources' "/tmp/launch-$NAME.log")"
done
exit 1
