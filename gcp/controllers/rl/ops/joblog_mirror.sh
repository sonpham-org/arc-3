#!/bin/bash
# Trainer VM: copy each recent job's job.log and train_log.jsonl to GCS every 60 s, each with a <file>.mtime.json
# sidecar (the file's modification time; train_log.jsonl gains a line when a record finishes, so its mtime dates the
# latest record for the live page). The running trainer service predates its own log mirror.
B=gs://cellens-ai-artifacts/arc3-rl/trainer/train4-1002/out
while true; do
  for f in $(find /opt/m/work/out -mindepth 2 -maxdepth 2 \( -name job.log -o -name train_log.jsonl \) -mmin -30); do
    j=$(basename "$(dirname "$f")") n=$(basename "$f")
    gcloud storage cp "$f" "$B/$j/$n" > /dev/null 2>&1
    printf '{"file": "%s", "mtime": %s, "at": %s}\n' "$n" "$(stat -c %Y "$f")" "$(date +%s)" \
      | gcloud storage cp - "$B/$j/$n.mtime.json" > /dev/null 2>&1
  done
  sleep 60
done
