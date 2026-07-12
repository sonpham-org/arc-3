#!/bin/bash
# Runs in the ~30s window GCP grants a spot VM before preemption. An incremental
# rsync of the run tree is small (only files changed since the 120s sync loop
# last fired), so it fits; time-box it anyway so we never die mid-transfer with
# nothing written.
BUCKET=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-bucket")
RUN_ID=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-run-id")
cd /opt/arc3/ARC3-Inference 2>/dev/null || exit 0
echo "preempted $(date -u +%FT%TZ)" >> /var/log/arc3-startup.log
timeout 20 gcloud storage rsync -r runs "$BUCKET/$RUN_ID/runs" 2>/dev/null
timeout 5 gcloud storage cp /var/log/arc3-startup.log "$BUCKET/$RUN_ID/startup-$(hostname).log" 2>/dev/null
exit 0
