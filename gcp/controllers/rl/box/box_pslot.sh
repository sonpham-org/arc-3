#!/bin/bash
# One PERSISTENT rollout server on one card of the RL box (4-Oct-2026, plan C: cards 0-2 play nonstop, card 3 runs
# the held-out full test, cards 4-7 train nonstop; rl/box/README.md). The server starts once (the hot-swap notebook:
# build_rl_notebook.py --hotswap, rollout_driver.serve_sessions) and plays one session per model:
#   box_agent.sh hands this card a session: /run/box/pslot<card>/session.env (RUN_ID, CAMPAIGN, LABEL, MERGE)
#   -> the model's delta (/kaggle-delta/<MERGE>/delta.safetensors, made by the train job's background merge, or made
#      here from /opt/m/work/out/<MERGE>/merged) -> the campaign's jobs staged in sess/<campaign>/ (rl_host_sync.py)
#   -> ctl/next.json {"session", "delta"}: the notebook loads the changed layers (hotswap.py apply) and plays
#   -> the campaign's STOP (mirrored by rl_host_sync) ends the session; _sessions/<campaign>.json is the notebook's
#      receipt; the last tries are uploaded, then "finish (session_done)" in runs/<RUN_ID>/phases.tsv.
# A dead container, or a session whose wake/apply failed (weights possibly half-updated), restarts the server cold.
# Env (systemd unit rl-pslot-<card>, started by box_agent.sh): SLOT, NB_OBJ (hot-swap notebook), IN (cold-start inputs,
# default the daniel-draft base).
set -uo pipefail
: "${SLOT:?}" "${NB_OBJ:?}"
GPU=${GPU:-$SLOT}
IN=${IN:-}; case "$IN" in gs://*) ;; *) IN=gs://cellens-ai-artifacts/arc3-duck/daniel-draft/kaggle-input;; esac
STORE=gs://cellens-ai-artifacts/arc3-gtree/v1
CODE=gs://cellens-ai-artifacts/arc3-gtree/rollout-code
R=/kaggle-root/s$SLOT
L=/var/log/box/s$SLOT
Q=/run/box/pslot$SLOT
NAME=rl-nb-s$SLOT
mkdir -p "$L" "$Q" /kaggle-in /kaggle-delta
exec >> "$L/pslot.log" 2>&1
say() { echo "$(date -u +%FT%TZ) card $GPU: $*"; }
up() { [ -n "$(docker ps -q -f name="^$NAME\$")" ]; }

start_server() {   # cold start of the hot-swap notebook on this card; 0 = "ready to roll"
  local IMAGE TAG IND GPU_DEVS="" d ATTEMPT OUTCOME DEAD i
  docker rm -f "$NAME" > /dev/null 2>&1
  rm -rf "$R" && mkdir -p "$R/working" "$R/nb" "$R/code" "$R/rollout/ctl" "$R/rollout/sess" "$R/rollout/policy"
  echo '{}' > "$R/rollout/policy/current.json"
  gcloud storage cp "$CODE/rl_host_sync.py" "$CODE/gtree_store.py" "$CODE/gtree_ctx.py" "$R/code/" > /dev/null 2>&1 || return 1
  gcloud storage cp "$NB_OBJ" "$R/nb/notebook.ipynb" > /dev/null 2>&1 || return 1
  TAG=$(basename "$IN"); IND=/kaggle-in/$TAG
  ( flock -w 3600 9
    [ -f "$IND/.ok" ] || { rm -rf "$IND" && mkdir -p "$IND" && gcloud storage rsync -r "$IN" "$IND" > "$L/input-rsync.log" 2>&1 \
                           && touch "$IND/.ok"; }
  ) 9> /kaggle-in/.lock
  [ -f "$IND/.ok" ] || { say "inputs $IN not ready"; return 1; }
  IMAGE=$(cat /var/lib/box/image 2>/dev/null)
  for i in $(seq 1 120); do [ -n "$IMAGE" ] && docker image inspect "$IMAGE" > /dev/null 2>&1 && break; sleep 30; IMAGE=$(cat /var/lib/box/image 2>/dev/null); done
  for d in /dev/nvidiactl /dev/nvidia-uvm /dev/nvidia-uvm-tools /dev/nvidia-modeset "/dev/nvidia$GPU"; do
    [ -e "$d" ] && GPU_DEVS="$GPU_DEVS --device $d"
  done
  for ATTEMPT in 1 2; do
    # shellcheck disable=SC2086
    docker run -d --name "$NAME" --gpus "device=$GPU" $GPU_DEVS --cpus 48 --memory 200g --network none --shm-size=64g \
      --ulimit memlock=-1 -v "$IND:/kaggle/input:ro" -v "$R/working:/kaggle/working" -v "$R/nb:/kaggle/nb:ro" \
      -v "$R/rollout:/kaggle/rollout:ro" -v /kaggle-delta:/kaggle/delta:ro -w /kaggle/working --entrypoint bash "$IMAGE" -c \
      'jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=-1 --ExecutePreprocessor.kernel_name=python3 /kaggle/nb/notebook.ipynb --output-dir /kaggle/working --output __notebook__.ipynb' \
      > /dev/null || return 1
    OUTCOME=timeout DEAD=0
    for i in $(seq 1 180); do
      sleep 20
      if grep -q "ready to roll" "$R/working/serve.log" 2>/dev/null; then OUTCOME=ready; break; fi
      if grep -q -E "Scheduler hit an exception|Capture cuda graph failed|Received sigquit from a child|unrecognized arguments" "$R/working/serve.log" 2>/dev/null; then OUTCOME=server_failed; break; fi
      up || { OUTCOME=exited; break; }
      if [ -s "$R/working/serve.log" ] && ! docker top "$NAME" -eo pid,args 2>/dev/null | grep -q -i sglang; then
        DEAD=$((DEAD + 1)); [ "$DEAD" -ge 3 ] && { OUTCOME=server_failed; break; }
      else
        DEAD=0
      fi
    done
    say "server start attempt $ATTEMPT: $OUTCOME"
    [ "$OUTCOME" = ready ] && { echo ready > "$Q/state"; return 0; }
    docker logs "$NAME" > "$L/failed-start-$ATTEMPT.log" 2>&1; docker rm -f "$NAME" > /dev/null 2>&1
    cp "$R/working/serve.log" "$L/failed-serve-$ATTEMPT.log" 2>/dev/null; find "$R/working" -mindepth 1 -delete
  done
  return 1
}

run_session() {   # the session in $Q/session.cur
  local RUN_ID CAMPAIGN LABEL MERGE OUT PH VM DELTA DH N LOOP MARK STARTED=""
  RUN_ID=$(grep '^RUN_ID=' "$Q/session.cur" | cut -d= -f2-); CAMPAIGN=$(grep '^CAMPAIGN=' "$Q/session.cur" | cut -d= -f2-)
  LABEL=$(grep '^LABEL=' "$Q/session.cur" | cut -d= -f2-); MERGE=$(grep '^MERGE=' "$Q/session.cur" | cut -d= -f2-)
  OUT=$STORE/rl/$CAMPAIGN/runs/$RUN_ID; PH=$L/$RUN_ID.phases.tsv; VM=arc3-rl-$LABEL
  phase() { printf '%s\t%s\n' "$(date -u +%FT%TZ)" "$1" | tee -a "$PH"; timeout 30 gcloud storage cp "$PH" "$OUT/phases.tsv" >/dev/null 2>&1 || true; }
  # --mount: staged sources must be named by their path INSIDE the container (5-Oct: without it every job read
  # /kaggle/rollout/src/... while its files sat under sess/<campaign>/src, and all of v1c0's jobs failed at once)
  hsync() { timeout 900 python3 "$R/code/rl_host_sync.py" once --campaign "$CAMPAIGN" --store "$STORE" \
              --root "$R/rollout/sess/$CAMPAIGN" --mount "/kaggle/rollout/sess/$CAMPAIGN" \
              --results "$R/working/gtree-rollout/$CAMPAIGN" --vm "$VM" >> "$L/host.log" 2>&1 || true; }
  logs() {
    timeout 60 gcloud storage cp "$R/working/serve.log" "$OUT/" >/dev/null 2>&1 || true
    [ -f "$R/working/metrics.jsonl" ] && timeout 60 gcloud storage cp "$R/working/metrics.jsonl" "$OUT/" >/dev/null 2>&1 || true
    timeout 30 gcloud storage cp "$L/pslot.log" "$OUT/vm.log" >/dev/null 2>&1 || true
    timeout 30 gcloud storage cp "$L/host.log" "$OUT/host.log" >/dev/null 2>&1 || true
  }
  : > "$PH"
  phase "start $RUN_ID box card $GPU campaign $CAMPAIGN (persistent server, model ${MERGE:-as loaded})"
  # the host code fresh for every session: a fix reaches a live server without restarting it
  gcloud storage cp "$CODE/rl_host_sync.py" "$CODE/gtree_store.py" "$CODE/gtree_ctx.py" "$R/code/" > /dev/null 2>&1
  DELTA=null
  if [ -n "$MERGE" ]; then
    DH=/kaggle-delta/$MERGE/delta.safetensors
    if [ ! -f "$DH" ] && [ -d "/opt/m/work/out/$MERGE/merged" ]; then
      ( flock -w 1800 8; [ -f "$DH" ] || /opt/rl/venv/bin/python /opt/rl/extract_delta.py --merged "/opt/m/work/out/$MERGE/merged" --out "$DH" ) \
        8> /kaggle-delta/.lock >> "$L/delta.log" 2>&1
    fi
    [ -f "$DH" ] || { phase "finish (no_delta $MERGE)"; return; }
    chmod -R a+rX "/kaggle-delta/$MERGE"
    DELTA="\"/kaggle/delta/$MERGE/delta.safetensors\""
  fi
  mkdir -p "$R/rollout/sess/$CAMPAIGN" "$R/working/gtree-rollout"
  gcloud storage cat "$STORE/rl/$CAMPAIGN/policy/current.json" > /dev/null 2>&1 || { phase "finish (no_policy)"; return; }
  hsync
  N=$(find "$R/rollout/sess/$CAMPAIGN/jobs" -name '*.json' 2>/dev/null | wc -l)
  [ "$N" -gt 0 ] || { phase "finish (no_jobs_staged)"; return; }
  [ -f "$R/rollout/sess/$CAMPAIGN/policy/current.json" ] && cp "$R/rollout/sess/$CAMPAIGN/policy/current.json" "$R/rollout/policy/current.json"
  printf '{"session": "%s", "delta": %s}\n' "$CAMPAIGN" "$DELTA" > "$R/rollout/ctl/next.json.tmp" && mv "$R/rollout/ctl/next.json.tmp" "$R/rollout/ctl/next.json"
  phase "jobs_staged $N"
  ( while true; do sleep 120; hsync; logs; done ) &
  LOOP=$!
  MARK=$R/working/gtree-rollout/_sessions/$CAMPAIGN.json
  local SUMM=$R/working/gtree-rollout/$CAMPAIGN/summary.json T0=$SECONDS WARNED=""
  while [ ! -f "$MARK" ]; do
    if [ -z "$STARTED" ] && [ -f "$R/working/gtree-rollout/_sessions/$CAMPAIGN.started.json" ]; then
      STARTED=1; phase "server_ready session $(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); a=d.get('apply') or {}; print('apply', a.get('s'), 's', a.get('tensors'), 'tensors, verified', a.get('verified'))" "$R/working/gtree-rollout/_sessions/$CAMPAIGN.started.json" 2>/dev/null)"
    fi
    # 5-Oct: every job of v1c0 failed in its first second and the cards sat idle for 7 h with nothing said. Ten
    # minutes into a session with failed jobs and no finished try, say so once (the driver's watch picks it up).
    if [ -z "$WARNED" ] && [ $((SECONDS - T0)) -gt 600 ] && [ -f "$SUMM" ]; then
      W=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); e=d.get('errors') or []; print(f\"{len(e)} {d.get('tries', 0)} {(e[0].get('error') if e else '')[:160]}\")" "$SUMM" 2>/dev/null)
      if [ "${W%% *}" -gt 0 ] 2>/dev/null && [ "$(echo "$W" | cut -d' ' -f2)" = 0 ]; then
        WARNED=1; phase "jobs_failing ${W%% *} jobs failed, 0 tries finished: $(echo "$W" | cut -d' ' -f3-)"
        timeout 30 gcloud storage cp "$SUMM" "$OUT/summary.json" >/dev/null 2>&1
      fi
    fi
    up || break
    sleep 15
  done
  kill "$LOOP" 2>/dev/null
  hsync
  timeout 1800 gcloud storage rsync -r "$R/working/gtree-rollout/$CAMPAIGN" "$OUT/gtree-rollout" >/dev/null 2>&1 || true
  logs
  if [ ! -f "$MARK" ]; then
    phase "finish (server_died)"; docker rm -f "$NAME" > /dev/null 2>&1
  elif grep -q '"error"' "$MARK"; then
    timeout 30 gcloud storage cp "$MARK" "$OUT/session.json" >/dev/null 2>&1
    phase "finish (session_error $(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('error'))" "$MARK" 2>/dev/null))"
    docker rm -f "$NAME" > /dev/null 2>&1       # weights may be half updated: restart cold
  else
    timeout 30 gcloud storage cp "$MARK" "$OUT/session.json" >/dev/null 2>&1
    phase "finish (session_done)"
  fi
}

say "persistent slot: notebook $NB_OBJ, cold inputs $IN"
echo starting > "$Q/state"
while [ ! -f "$Q/END" ]; do
  if ! up; then
    echo starting > "$Q/state"
    start_server || { say "server start failed; retry in 2 min"; echo failed > "$Q/state"; sleep 120; continue; }
  fi
  if [ -f "$Q/session.env" ]; then
    mv "$Q/session.env" "$Q/session.cur"
    echo busy > "$Q/state"
    run_session
    rm -f "$Q/session.cur"
    up && echo ready > "$Q/state"
  fi
  sleep 10
done
docker rm -f "$NAME" > /dev/null 2>&1
say "ended"
