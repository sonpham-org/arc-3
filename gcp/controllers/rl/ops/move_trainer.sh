#!/bin/bash
# Move the RL trainer to another zone (Spot stockout, or its region's GPU quota taken by other sessions' runs): a new
# VM booted from a snapshot of the old disk keeps the weights, the venv, the job queue state (/opt/m/work/done.txt)
# and the same service name, so the queue and every watcher go on unchanged. Only one VM may run a service: stop the
# old VM's restart loop first; this script refuses while the old VM is not TERMINATED.
# A free 4-GPU host is scarce, and a create that restores the 2 TB disk spends 6-10 min on the restore before GCE
# checks capacity (3-Oct: three stockouts cost 30 min that way). So: probe every zone at once with a throwaway 4-GPU
# VM on a small public image (about a minute), keep the first that gets a host, restore the disk in that zone while
# the probe holds the host, then swap the probe for the trainer.
#   CODE=gs://.../arc3-rl/code/<sha> bash ops/move_trainer.sh <snapshot> <new vm name> [zones, preferred first...]
#   prints the new zone on its last line; run_round.sh then takes TRAINER_VM=<new vm name> TRAINER_ZONE=<zone>
set -uo pipefail
export CLOUDSDK_PYTHON='C:\python312\python.exe'
OPS=$(cd "$(dirname "$0")" && pwd)
SNAP=$1 NEW=$2; shift 2
OLD=${OLD:-arc3-rl-train4-20261002} OLD_ZONE=${OLD_ZONE:-us-south1-b}
[ "$NEW" != "$OLD" ] || { echo "the new VM needs its own name"; exit 1; }
CODE=${CODE:?set CODE to the code snapshot the trainer runs (gs://cellens-ai-artifacts/arc3-rl/code/<sha>)}
SERVICE=${SERVICE:-train4-1002}
ZONES=${*:-us-east4-a us-east4-b us-east4-c us-west1-a us-west1-b us-west1-c us-east1-b us-east1-d us-west3-a
          us-west4-a us-west4-b us-west4-c us-central1-a us-central1-b us-central1-c us-central1-f us-east5-a us-east5-b
          us-east5-c us-south1-a us-south1-b}
say() { echo "$(date -u +%H:%M) $*" >&2; }
why() { grep -o -E "STOCKOUT|QUOTA[A-Z_]*|Quota '[A-Z0-9_]*' exceeded|ZONE_RESOURCE_POOL_EXHAUSTED|does not exist|not supported|not available|Invalid value[^.]*" | head -n 1; }

st=$(timeout 120 gcloud compute instances describe "$OLD" --zone "$OLD_ZONE" --format='value(status)' 2>/dev/null | tr -d '\r')
[ "$st" = TERMINATED ] || { say "old VM $OLD is ${st:-gone}, not TERMINATED: refusing (two VMs would run one queue)"; exit 1; }
snap=$(timeout 120 gcloud compute snapshots describe "$SNAP" --format='value(status)' 2>/dev/null | tr -d '\r')
[ "$snap" = READY ] || { say "snapshot $SNAP is ${snap:-missing}"; exit 1; }

TMP=$(mktemp -d)
probe() {   # <zone>: a throwaway 4-GPU VM (deletes itself after 45 min whatever happens here); $TMP/<zone> on success
  local out
  out=$(timeout 600 gcloud compute instances create "rlprobe-$1" --zone "$1" --machine-type g4-standard-192 \
        --image-family debian-12 --image-project debian-cloud --boot-disk-size 20GB --boot-disk-type hyperdisk-balanced \
        --provisioning-model SPOT --instance-termination-action DELETE --max-run-duration 45m \
        --maintenance-policy TERMINATE --labels purpose=arc3-rl,role=probe < /dev/null 2>&1)
  if [ $? -eq 0 ]; then touch "$TMP/$1"; say "$1: got a 4-GPU host"
  else say "$1: $(echo "$out" | why)"; fi
}
drop_probe() { timeout 600 gcloud compute instances delete "rlprobe-$1" --zone "$1" --quiet < /dev/null > /dev/null 2>&1; }
for Z in $ZONES; do probe "$Z" & done; wait
PICK=""; for Z in $ZONES; do [ -f "$TMP/$Z" ] && { PICK=$Z; break; }; done
for Z in $ZONES; do [ -f "$TMP/$Z" ] && [ "$Z" != "$PICK" ] && drop_probe "$Z" & done
[ -n "$PICK" ] || { wait; say "no zone had a free 4-GPU host"; exit 1; }

say "$PICK: restoring the disk from $SNAP while the probe holds the host"
if ! out=$(timeout 2400 gcloud compute disks create "$NEW" --zone "$PICK" --source-snapshot "$SNAP" --size 2000 \
           --type hyperdisk-balanced --provisioned-iops 12000 --provisioned-throughput 1200 \
           --labels purpose=arc3-rl,role=trainer < /dev/null 2>&1); then
  say "$PICK: disk restore failed: $(echo "$out" | tail -n 1 | cut -c1-200)"; drop_probe "$PICK"; wait; exit 1
fi
say "$PICK: disk restored; swapping the probe for the trainer"
drop_probe "$PICK"; wait
for try in 1 2 3 4 5 6 7 8 9 10; do
  out=$(timeout 600 gcloud compute instances create "$NEW" --zone "$PICK" --machine-type g4-standard-192 \
    --disk "name=$NEW,boot=yes,auto-delete=yes" \
    --provisioning-model SPOT --instance-termination-action STOP --maintenance-policy TERMINATE \
    --shielded-vtpm --shielded-integrity-monitoring --scopes cloud-platform --labels purpose=arc3-rl,role=trainer \
    --metadata "rl-code=$CODE,rl-service=$SERVICE" --metadata-from-file "startup-script=$OPS/../trainer_vm_startup.sh" \
    < /dev/null 2>&1)
  if [ $? -eq 0 ]; then say "created $NEW in $PICK"; echo "$PICK"; exit 0; fi
  say "$PICK: trainer create try $try: $(echo "$out" | why)"; sleep 30
done
say "$PICK: the host went to someone else; the restored disk $NEW stays there (retry: gcloud compute instances create ... --disk name=$NEW,boot=yes)"
exit 1
