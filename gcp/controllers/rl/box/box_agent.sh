#!/bin/bash
# RL box dispatcher (4-Oct-2026, plan C; rl/box/README.md). Keeps one persistent rollout server per play card
# (box_pslot.sh, systemd unit rl-pslot-<card>) and hands each a session when one is asked for:
#   gs://cellens-ai-artifacts/arc3-rl/box/<box>/requests/<label>.env   written by ops/run_c.sh, one per server and model
#     lines KEY=VALUE, keys RUN_ID CAMPAIGN LABEL MERGE (anything else, or an odd character, is rejected)
#   gs://cellens-ai-artifacts/arc3-rl/box/<box>/slots.json             each card's state and session, every ~20 s
# A request goes to the lowest play card whose server has no session queued or running (state ready or starting).
#   systemd-run --unit box-agent /bin/bash /opt/box/box_agent.sh <box name> [<box code dir>]
# Env: SLOTS (play cards, "0 1 2"), NB_OBJ (the hot-swap notebook), IN (cold-start inputs).
set -uo pipefail
BOX=${1:?box name}
BOXCODE=${2:-gs://cellens-ai-artifacts/arc3-rl/box/code}
BOXQ=gs://cellens-ai-artifacts/arc3-rl/box/$BOX
SLOTS=${SLOTS:-"0 1 2"}
NB_OBJ=${NB_OBJ:?the hot-swap notebook}
IN=${IN:-gs://cellens-ai-artifacts/arc3-duck/daniel-draft/kaggle-input}
mkdir -p /run/box /var/log/box
log() { echo "$(date -u +%FT%TZ) $*" >> /var/log/box/agent.log; }
log "agent start: play cards $SLOTS, notebook $NB_OBJ, cold inputs $IN"
ensure_slot() {   # the persistent server unit of card $1
  systemctl is-active --quiet "rl-pslot-$1" && return 0
  timeout 120 gcloud storage cp "$BOXCODE/box_pslot.sh" /opt/box/box_pslot.sh.new > /dev/null 2>&1 \
    && mv /opt/box/box_pslot.sh.new /opt/box/box_pslot.sh
  systemctl reset-failed "rl-pslot-$1" > /dev/null 2>&1
  mkdir -p "/run/box/pslot$1"
  systemd-run --unit "rl-pslot-$1" --setenv=SLOT="$1" --setenv=GPU="$1" --setenv=NB_OBJ="$NB_OBJ" --setenv=IN="$IN" \
    --property=KillMode=mixed --property=TimeoutStopSec=120 /bin/bash /opt/box/box_pslot.sh > /dev/null 2>&1 \
    && log "card $1: persistent server unit started"
}
while true; do
  for s in $SLOTS; do ensure_slot "$s"; done
  reqs=$(timeout 60 gcloud storage ls "$BOXQ/requests/*.env" 2>/dev/null | tr -d '\r' | sort)
  for r in $reqs; do
    free=""
    for s in $SLOTS; do
      st=$(cat "/run/box/pslot$s/state" 2>/dev/null)
      [ ! -f "/run/box/pslot$s/session.env" ] && [ ! -f "/run/box/pslot$s/session.cur" ] \
        && { [ "$st" = ready ] || [ "$st" = starting ]; } && { free=$s; break; }
    done
    [ -z "$free" ] && break
    f=/run/box/pslot$free/session.env
    timeout 60 gcloud storage cat "$r" 2>/dev/null | tr -d '\r' > "$f.raw" || continue
    if grep -v -E '^(RUN_ID|CAMPAIGN|LABEL|MERGE)=[A-Za-z0-9._:/@=-]*$' "$f.raw" | grep -q . || ! grep -q '^LABEL=.' "$f.raw" \
       || ! grep -q '^CAMPAIGN=.' "$f.raw" || ! grep -q '^RUN_ID=.' "$f.raw"; then
      log "rejected $r: $(head -c 300 "$f.raw" | tr '\n' ' ')"
      timeout 60 gcloud storage mv "$r" "$BOXQ/rejected/" > /dev/null 2>&1
      rm -f "$f.raw"
      continue
    fi
    timeout 60 gcloud storage rm "$r" > /dev/null 2>&1 || { log "could not claim $r"; rm -f "$f.raw"; continue; }
    mv "$f.raw" "$f"
    log "card $free <- $(grep '^LABEL=' "$f" | cut -d= -f2) ($(grep '^CAMPAIGN=' "$f" | cut -d= -f2), model $(grep '^MERGE=' "$f" | cut -d= -f2))"
  done
  {
    printf '{"at": "%s", "slots": {' "$(date -u +%FT%TZ)"
    sep=""
    for s in $SLOTS; do
      st=$(cat "/run/box/pslot$s/state" 2>/dev/null); lb=$(grep -h '^LABEL=' "/run/box/pslot$s/session.cur" "/run/box/pslot$s/session.env" 2>/dev/null | head -1 | cut -d= -f2)
      printf '%s"%s": {"state": "%s", "session": "%s"}' "$sep" "$s" "${st:-none}" "$lb"; sep=", "
    done
    printf '}, "panel": "%s", "training": %s}\n' "$(systemctl is-active rl-panel 2>/dev/null)" \
      "$(pgrep -f 'lora_train.py' > /dev/null && echo true || echo false)"
  } > /run/box/slots.json
  timeout 60 gcloud storage cp /run/box/slots.json "$BOXQ/slots.json" > /dev/null 2>&1
  sleep 20
done
