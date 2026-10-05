#!/bin/bash
# Create the RL box (4-Oct-2026, Son: "just take 8 GPU and redo everything"; rl/box/README.md): a g4-standard-384
# (8x RTX PRO 6000, Spot, STOP on preemption) booted from a snapshot of the RL trainer's disk, running
# rl/box/box_startup.sh (rollout servers + the trainer service on one machine). move_trainer.sh's recipe: grab the
# 8-card host first with a throwaway probe VM on a small public image (about a minute), restore the disk in that zone
# while the probe holds the host, then swap the probe for the box. us-central1 = the bucket's region (no cross-region
# pulls); Son gave this thread the region's whole RTX PRO 6000 quota (8).
#   CODE=gs://.../arc3-rl/code/<sha> bash ops/box_create.sh <snapshot> <box name> [zones, preferred first...]
# prints the zone on its last line. The old trainer VM must be TERMINATED: one machine per job queue.
set -uo pipefail
export CLOUDSDK_PYTHON='C:\python312\python.exe'
OPS=$(cd "$(dirname "$0")" && pwd)
SNAP=$1 NEW=$2; shift 2
OLD=${OLD:-arc3-rl-train4e-20261003} OLD_ZONE=${OLD_ZONE:-us-west3-a}
CODE=${CODE:?set CODE to the code snapshot the trainer runs (gs://cellens-ai-artifacts/arc3-rl/code/<sha>)}
SERVICE=${SERVICE:-train4-1002}
BOXCODE=${BOXCODE:-gs://cellens-ai-artifacts/arc3-rl/box/code}
SIZE=${SIZE:-3000}
ZONES=${*:-us-central1-b us-central1-c us-central1-f}
say() { echo "$(date -u +%H:%M) $*" >&2; }
why() { grep -o -E "STOCKOUT|QUOTA[A-Z_]*|Quota '[A-Z0-9_]*' exceeded|ZONE_RESOURCE_POOL_EXHAUSTED|does not exist|not supported|not available|Invalid value[^.]*" | head -n 1; }

st=$(timeout 120 gcloud compute instances describe "$OLD" --zone "$OLD_ZONE" --format='value(status)' 2>/dev/null | tr -d '\r')
[ "$st" = TERMINATED ] || { say "old trainer $OLD is ${st:-gone}, not TERMINATED: refusing (two machines would run one queue)"; exit 1; }
snap=$(timeout 120 gcloud compute snapshots describe "$SNAP" --format='value(status)' 2>/dev/null | tr -d '\r')
[ "$snap" = READY ] || { say "snapshot $SNAP is ${snap:-missing}"; exit 1; }
timeout 120 gcloud storage ls "$BOXCODE/box_slot.sh" > /dev/null 2>&1 || { say "no box code at $BOXCODE"; exit 1; }

TMP=$(mktemp -d)
probe() {   # <zone>: a throwaway 8-card VM (deletes itself after 45 min whatever happens here); $TMP/<zone> on success
  local out
  out=$(timeout 600 gcloud compute instances create "rlboxprobe-$1" --zone "$1" --machine-type g4-standard-384 \
        --image-family debian-12 --image-project debian-cloud --boot-disk-size 20GB --boot-disk-type hyperdisk-balanced \
        --provisioning-model SPOT --instance-termination-action DELETE --max-run-duration 45m \
        --maintenance-policy TERMINATE --labels purpose=arc3-rl,role=probe < /dev/null 2>&1)
  if [ $? -eq 0 ]; then touch "$TMP/$1"; say "$1: got an 8-card host"
  else say "$1: $(echo "$out" | why)"; fi
}
drop_probe() { timeout 600 gcloud compute instances delete "rlboxprobe-$1" --zone "$1" --quiet < /dev/null > /dev/null 2>&1; }
for Z in $ZONES; do probe "$Z" & done; wait
PICK=""; for Z in $ZONES; do [ -f "$TMP/$Z" ] && { PICK=$Z; break; }; done
for Z in $ZONES; do [ -f "$TMP/$Z" ] && [ "$Z" != "$PICK" ] && drop_probe "$Z" & done
[ -n "$PICK" ] || { wait; say "no zone had a free 8-card host"; exit 1; }

say "$PICK: restoring the disk from $SNAP ($SIZE GB) while the probe holds the host"
if ! out=$(timeout 2400 gcloud compute disks create "$NEW" --zone "$PICK" --source-snapshot "$SNAP" --size "$SIZE" \
           --type hyperdisk-balanced --provisioned-iops 16000 --provisioned-throughput 2400 \
           --labels purpose=arc3-rl,role=box < /dev/null 2>&1); then
  say "$PICK: disk restore failed: $(echo "$out" | tail -n 1 | cut -c1-200)"; drop_probe "$PICK"; wait; exit 1
fi
say "$PICK: disk restored; swapping the probe for the box"
drop_probe "$PICK"; wait
for try in 1 2 3 4 5 6 7 8 9 10; do
  out=$(timeout 600 gcloud compute instances create "$NEW" --zone "$PICK" --machine-type g4-standard-384 \
    --disk "name=$NEW,boot=yes,auto-delete=no" \
    --provisioning-model SPOT --instance-termination-action STOP --maintenance-policy TERMINATE \
    --shielded-vtpm --shielded-integrity-monitoring --scopes cloud-platform --labels purpose=arc3-rl,role=box \
    --metadata "rl-code=$CODE,rl-service=$SERVICE,box-code=$BOXCODE" \
    --metadata-from-file "startup-script=$OPS/../box/box_startup.sh" < /dev/null 2>&1)
  if [ $? -eq 0 ]; then say "created $NEW in $PICK"; echo "$PICK"; exit 0; fi
  say "$PICK: box create try $try: $(echo "$out" | why)"; sleep 30
done
say "$PICK: the host went to someone else; the restored disk $NEW stays there (retry: gcloud compute instances create ... --disk name=$NEW,boot=yes)"
exit 1
