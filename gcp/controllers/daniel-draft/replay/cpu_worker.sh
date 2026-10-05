#!/bin/bash
# Replay data prep worker (4-Oct-2026, Slice and dice; drafter data from saved conversations): a CPU VM that runs
# shell jobs from a plan file in GCS, no SSH needed.
#   plan:    gs://cellens-ai-artifacts/arc3-duck/daniel-draft/replay/plans/<vm>.txt, lines "<name> <shell command>"
#            (run once each, in order, from /opt/rp with the code dir synced first); "STOP" powers the VM off once
#            everything before it ran.
#   code:    gs://.../daniel-draft/replay/code/* -> /opt/rp/code/ before every job
#   results: gs://.../daniel-draft/replay/prep/<vm>/<name>.log (+ whatever the job uploads itself)
set -uo pipefail
exec > >(tee -a /var/log/rpworker.log) 2>&1
RP=gs://cellens-ai-artifacts/arc3-duck/daniel-draft/replay
VM=$(curl -sf -H Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/name)
PLAN=$RP/plans/$VM.txt
OUT=$RP/prep/$VM
L=/opt/rp
mkdir -p $L/code $L/done $L/work
log() { echo "$(date -u +%FT%TZ) $*" | tee -a $L/phases.txt; gcloud storage cp -q $L/phases.txt $OUT/phases.txt >/dev/null 2>&1 || true; }
log "boot $VM"
if ! python3 -c "import numpy, tokenizers" 2>/dev/null; then
  apt-get update -qq >/dev/null 2>&1; apt-get install -y -qq python3-pip python3-numpy >/dev/null 2>&1
  pip3 install -q --break-system-packages tokenizers numpy >/dev/null 2>&1 || pip3 install -q tokenizers numpy >/dev/null 2>&1
fi
log "python ready: $(python3 -c 'import numpy, tokenizers; print(numpy.__version__, tokenizers.__version__)' 2>&1)"
while true; do
  gcloud storage cp -q $PLAN $L/plan.txt >/dev/null 2>&1 || { sleep 30; continue; }
  tr -d '\r' < $L/plan.txt > $L/plan.lf
  next=""
  while read -r name cmd; do
    [ -z "$name" ] && continue
    case "$name" in \#*) continue;; esac
    if [ "$name" = STOP ]; then [ -z "$next" ] && { log "stop"; shutdown -h now; exit 0; }; break; fi
    [ -e $L/done/$name ] && continue
    next="$name"; ncmd="$cmd"; break
  done < $L/plan.lf
  if [ -z "$next" ]; then sleep 30; continue; fi
  touch $L/done/$next
  gcloud storage cp -q "$RP/code/*" $L/code/ >/dev/null 2>&1
  log "job $next start: $ncmd"
  ( while sleep 60; do gcloud storage cp -q $L/work/$next.log $OUT/$next.log >/dev/null 2>&1; done ) &
  SYNC=$!
  ( cd $L && bash -c "$ncmd" ) > $L/work/$next.log 2>&1
  rc=$?
  kill $SYNC 2>/dev/null
  gcloud storage cp -q $L/work/$next.log $OUT/$next.log >/dev/null 2>&1
  log "job $next rc=$rc"
done
