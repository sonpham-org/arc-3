#!/bin/bash
# Token-matched scoring extractor VM (3-Oct-2026, daniel-draft). Every 60 s: read the queue, extract each listed run
# once it has finished (phases.tsv "finish"; a queue line "RUN now" skips that check), upload the compact JSON.
# Deletes itself after 3.5 h; --max-run-duration (DELETE) is the backstop.
O=gs://cellens-ai-artifacts/arc3-duck/daniel-draft/tokmatch
B=gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs
W=/opt/tm
mkdir -p $W && cd $W
gcloud storage cp -q $O/extract.py $W/extract.py
END=$(( $(date +%s) + 12600 ))
while [ "$(date +%s)" -lt "$END" ]; do
  gcloud storage cp -q $O/queue.txt $W/queue.txt 2>/dev/null
  while read -r run flag; do
    [ -n "$run" ] || continue
    gcloud storage ls "$O/out/$run.json" >/dev/null 2>&1 && continue
    if [ "$flag" != now ]; then
      gcloud storage cat "$B/$run/phases.tsv" 2>/dev/null | grep -q finish || continue
    fi
    python3 $W/extract.py "$run" > "$W/$run.log" 2>&1 && gcloud storage cp -q "$W/$run.json" "$O/out/$run.json"
    gcloud storage cp -q "$W/$run.log" "$O/logs/$run.log"
    rm -rf "$W/raw_$run"
  done < $W/queue.txt
  sleep 60
done
Z=$(curl -s -H Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/zone | cut -d/ -f4)
gcloud compute instances delete "$(hostname)" --zone="$Z" --quiet
