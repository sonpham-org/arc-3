#!/bin/bash
# Low-overhead resource sampler for GCP harness runs.
# Samples GPU (util / mem / power), CPU%, and RAM every ~20s into a CSV, and syncs
# it to GCS. Runs entirely out-of-band -- nvidia-smi queries the driver (not the
# vLLM compute path), /proc + free are near-instant, and 3 samples/min is nothing,
# so it does not affect harness or inference performance.
#
# Usage (from a startup script, backgrounded): bash resource_sampler.sh "$BUCKET" "$RUN_ID" &
BUCKET=$1
RUN_ID=$2
LOG=/opt/arc3/resource.log
mkdir -p /opt/arc3

echo "ts_utc,gpu_util_pct,gpu_mem_used_mib,gpu_mem_total_mib,gpu_power_w,cpu_util_pct,mem_used_mib,mem_total_mib" > "$LOG"

# CPU% is computed from the delta of /proc/stat between samples (avg over the interval).
prev=$(awk '/^cpu /{print ($2+$3+$4+$5+$6+$7+$8), ($5+$6)}' /proc/stat)

( while true; do
    ts=$(date -u +%FT%TZ)
    gpu=$(nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,power.draw \
            --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')
    [ -z "$gpu" ] && gpu=",,,"
    cur=$(awk '/^cpu /{print ($2+$3+$4+$5+$6+$7+$8), ($5+$6)}' /proc/stat)
    cpu=$(awk -v p="$prev" -v c="$cur" 'BEGIN{split(p,P," ");split(c,C," ");
          dt=C[1]-P[1]; di=C[2]-P[2]; printf "%.1f", (dt>0)?100*(dt-di)/dt:0}')
    prev=$cur
    mem=$(free -m | awk '/^Mem:/{print $3","$2}')
    echo "$ts,$gpu,$cpu,$mem" >> "$LOG"
    sleep 20
  done ) &
SAMPLER_PID=$!

# Sync to GCS every 60s while the sampler is alive.
( while kill -0 "$SAMPLER_PID" 2>/dev/null; do
    gcloud storage cp "$LOG" "$BUCKET/$RUN_ID/resource.log" >/dev/null 2>&1
    sleep 60
  done ) &
echo "resource_sampler: started (pid $SAMPLER_PID) -> $BUCKET/$RUN_ID/resource.log"
