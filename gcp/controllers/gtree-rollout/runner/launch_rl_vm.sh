#!/bin/bash
# Launch ONE RL rollout-server VM (3-Oct-2026). STRUCTURE ONLY: not run yet.
#   launch_rl_vm.sh <label> <campaign> <gs://.../notebook.ipynb (build_rl_notebook.py --upload)> <zone> [<zone> ...]
# VM arc3-rl-<label>, run id rl-<campaign>-<label>; G4 Spot like launch_hicache_run.sh (same image, disk, 5 h cap:
# the notebook's own budget is ARC3_ROLLOUT_BUDGET_S, 2 h by default, plus ~30 min of setup and the final upload).
# Tries the zones in order until one has capacity. The code the host loop needs must be in rollout-code first:
#   gcloud.cmd storage cp runner/rl_host_sync.py ../gtree-ingest/gtree_store.py ../gtree-ingest/gtree_ctx.py \
#       gs://cellens-ai-artifacts/arc3-gtree/rollout-code/
# INPUT_PREFIX=gs://.../kaggle-input-<tag> (4-Oct): the model the tries play (rl-vm-startup.sh's default is the
# daniel-draft mirror = the base model); RL v1 round N plays round N-1's merged model, copied by
# MIRROR_BASE=daniel-draft rl/ops/make_eval_mirror.sh.
set -uo pipefail
LABEL=$1 CAMPAIGN=$2 NB=$3; shift 3
HERE=$(cd "$(dirname "$0")" && pwd)
export CLOUDSDK_PYTHON='C:\python312\python.exe'
for ZONE in "$@"; do
  if gcloud.cmd compute instances create "arc3-rl-$LABEL" --zone "$ZONE" --machine-type g4-standard-48 \
      --image arc3-sglang-sm120-recovery-20260926 --image-project cellensml \
      --boot-disk-size 1000GB --boot-disk-type hyperdisk-balanced \
      --boot-disk-provisioned-iops 16000 --boot-disk-provisioned-throughput 1200 \
      --provisioning-model SPOT --instance-termination-action DELETE --max-run-duration 5h \
      --maintenance-policy TERMINATE --scopes cloud-platform --labels purpose=arc3-rl-rollout \
      --metadata "arc3-run-id=rl-$CAMPAIGN-$LABEL,arc3-notebook-object=$NB,arc3-campaign=$CAMPAIGN${INPUT_PREFIX:+,arc3-input-prefix=$INPUT_PREFIX}" \
      --metadata-from-file "startup-script=$HERE/rl-vm-startup.sh" < /dev/null > "/tmp/launch-rl-$LABEL.log" 2>&1; then
    echo "launched arc3-rl-$LABEL in $ZONE (run rl-$CAMPAIGN-$LABEL)"; exit 0
  fi
  echo "$ZONE: $(grep -o -m1 'STOCKOUT\|QUOTA[A-Z_]*\|already exists\|ZONE_RESOURCE_POOL_EXHAUSTED\|does not have enough resources' "/tmp/launch-rl-$LABEL.log")"
done
exit 1
