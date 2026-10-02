#!/bin/bash
# Move the RL trainer to another zone after a Spot stockout: a new VM booted from a snapshot of the old disk keeps
# the weights, the venv, the job queue state (/opt/m/work/done.txt) and the same service name, so the queue and
# every watcher go on unchanged. Only one VM may run a service: stop the old VM's restart loop first; this script
# refuses while the old VM is not TERMINATED.
#   bash ops/move_trainer.sh <snapshot> <new vm name> [zones...]
#   e.g. bash ops/move_trainer.sh arc3-rl-train4-snap-20261002 arc3-rl-train4b-20261002
set -uo pipefail
export CLOUDSDK_PYTHON='C:\python312\python.exe'
OPS=$(cd "$(dirname "$0")" && pwd)
SNAP=$1 NEW=$2; shift 2
[ "$NEW" != "${OLD:-arc3-rl-train4-20261002}" ] || { echo "the new VM needs its own name"; exit 1; }
OLD=${OLD:-arc3-rl-train4-20261002} OLD_ZONE=${OLD_ZONE:-us-south1-b}
CODE=${CODE:-gs://cellens-ai-artifacts/arc3-rl/code/c19938fbaad8} SERVICE=${SERVICE:-train4-1002}
ZONES=${*:-us-south1-a us-central1-b us-central1-c us-central1-f us-east5-a us-east5-b us-east5-c us-east4-b us-east4-c us-west4-a us-west4-b us-west4-c us-east1-b us-east1-d us-west1-a us-west1-b us-west1-c us-west3-a}
say() { echo "$(date -u +%H:%M) $*"; }

st=$(gcloud compute instances describe "$OLD" --zone "$OLD_ZONE" --format='value(status)' 2>/dev/null | tr -d '\r')
[ "$st" = TERMINATED ] || { say "old VM $OLD is ${st:-gone}, not TERMINATED: refusing (two VMs would run one queue)"; exit 1; }
snap=$(gcloud compute snapshots describe "$SNAP" --format='value(status)' 2>/dev/null | tr -d '\r')
[ "$snap" = READY ] || { say "snapshot $SNAP is ${snap:-missing}"; exit 1; }
for Z in $ZONES; do
  out=$(gcloud compute instances create "$NEW" --zone "$Z" --machine-type g4-standard-192 \
    --create-disk="boot=yes,auto-delete=yes,name=$NEW,source-snapshot=$SNAP,size=2000,type=hyperdisk-balanced,provisioned-iops=12000,provisioned-throughput=1200" \
    --provisioning-model SPOT --instance-termination-action STOP --maintenance-policy TERMINATE \
    --shielded-vtpm --shielded-integrity-monitoring --scopes cloud-platform --labels purpose=arc3-rl,role=trainer \
    --metadata "rl-code=$CODE,rl-service=$SERVICE" --metadata-from-file "startup-script=$OPS/../trainer_vm_startup.sh" 2>&1)
  if [ $? -eq 0 ]; then say "created $NEW in $Z"; echo "$Z"; exit 0; fi
  why=$(echo "$out" | grep -o -E 'STOCKOUT|QUOTA[A-Z_]*|ZONE_RESOURCE_POOL_EXHAUSTED[A-Z_]*|does not exist|not supported|Invalid value[^.]*' | head -1)
  say "$Z: ${why:-$(echo "$out" | tail -n 1 | cut -c1-160)}"
  # a failed create can leave the disk behind; remove it so the next zone's create can reuse the name
  gcloud compute disks delete "$NEW" --zone "$Z" --quiet > /dev/null 2>&1
done
say "no zone had a Spot g4-standard-192"; exit 1
