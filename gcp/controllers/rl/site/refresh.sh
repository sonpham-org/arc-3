#!/bin/bash
# Rebuild data.json and deploy the RL live page (https://arc3-rl-live.web.app) every 5 minutes.
#   bash refresh.sh            (runs until stopped; each pass logs one line)
cd "$(dirname "$0")"
while true; do
  if C:/Python312/python.exe build_site.py > .build.log 2>&1 \
     && firebase.cmd deploy --only hosting:rl --project cellensml -m "data $(date -u +%H:%M)" > .deploy.log 2>&1; then
    echo "$(date -u +%H:%M) $(tail -n 1 .build.log | cut -c1-160)"
  else
    echo "$(date -u +%H:%M) FAILED: $(tail -n 2 .build.log .deploy.log | tr '\n' ' ' | cut -c1-300)"
  fi
  sleep 300
done
