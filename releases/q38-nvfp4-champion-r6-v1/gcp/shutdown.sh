#!/bin/bash
# Best-effort preemption sync plus immediate MIG teardown. The startup script has
# the authoritative terminal trap; this catches Spot termination separately.
meta() {
  curl -sf -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"
}
BUCKET=$(meta arc3-bucket)
RUN_ID=$(meta arc3-run-id)
MIG=$(meta arc3-mig)
ZONE=$(curl -sf -H "Metadata-Flavor: Google" \
  "http://metadata.google.internal/computeMetadata/v1/instance/zone" | awk -F/ '{print $NF}')
[ -d /opt/arc3/work ] && timeout 25 gcloud storage rsync -r /opt/arc3/work \
  "$BUCKET/$RUN_ID/runs" >/dev/null 2>&1 || true
[ -f /opt/arc3/v12.log ] && timeout 10 gcloud storage cp /opt/arc3/v12.log \
  "$BUCKET/$RUN_ID/v12-run.log" >/dev/null 2>&1 || true
echo "shutdown/preemption $(date -u +%FT%TZ)" | timeout 5 gcloud storage cp - \
  "$BUCKET/$RUN_ID/PREEMPTED" 2>/dev/null || true
timeout 10 gcloud compute instance-groups managed resize "$MIG" --size=0 \
  --zone="$ZONE" >/dev/null 2>&1 || true
exit 0
