#!/usr/bin/env bash
# Author: Claude Opus 5 (Bubba sub-agent, label arc3-style-multipass)
# Date: 18-September-2026
# PURPOSE: Sequential multi-pass A/B driver for the ARC-3 compact-reasoning experiment on
# gx10-a108. Runs 4 one-pass 25-game runs back to back (compact, baseline, compact, baseline)
# at the pinned operating point (conc 7, 90 min/game, n_passes 1), recording per-pass guards:
# vLLM PID/uptime before and after, treatment-marker presence in prompt logs, and run_config
# parity against the reference pass. Arms alternate so neither arm monopolises a time of day.
# SRP/DRY check: Pass - no existing driver; reuses the repo's own `make interactive` entrypoint
# and the 17-Sep launch line verbatim rather than re-implementing the harness invocation.
set -u
WORK=$HOME/arc3-multipass-20260918
INF=$HOME/GitHub/arc-3/ARC3-Inference
REF=$INF/runs/20260917_081554_qwen38-27b-compact-25g/run_config.json
VPID=765547
LEDGER=$WORK/guards/ledger.txt

stamp(){ date -Iseconds; }

guard_vllm(){  # $1 = when-label, $2 = pass-label
  local et
  et=$(ps -o etime= -p $VPID 2>/dev/null | tr -d ' ')
  if [ -z "$et" ]; then
    echo "$(stamp) $2 vllm_$1 PID_${VPID}_DEAD" >> "$LEDGER"
  else
    echo "$(stamp) $2 vllm_$1 pid=$VPID etime=$et health=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:1234/health)" >> "$LEDGER"
  fi
}

run_pass(){ # $1 = pass label, $2 = arm (compact|baseline), $3 = run name
  local LBL=$1 ARM=$2 NAME=$3
  echo "$(stamp) $LBL START arm=$ARM name=$NAME" >> "$LEDGER"
  guard_vllm before "$LBL"
  cd "$INF" || return 1
  if [ "$ARM" = "compact" ]; then
    export ARC3_REASONING_STYLE=compact
  else
    unset ARC3_REASONING_STYLE
  fi
  echo "$(stamp) $LBL env ARC3_REASONING_STYLE='${ARC3_REASONING_STYLE:-<unset>}'" >> "$LEDGER"
  make interactive CONFIG_PATH=configs/a108.qwen38.baseline.json \
    AGENT=duck-harness KAGGLE_DUCK_PUBLIC_HARNESS=true \
    RUN_NAME="$NAME" GAME= GAME_TAGS= EXCLUDE_GAME_TAGS= \
    > "$WORK/logs/$LBL.log" 2>&1
  local RC=$?
  unset ARC3_REASONING_STYLE
  guard_vllm after "$LBL"
  local DIR
  DIR=$(ls -1d "$INF"/runs/*_"$NAME" 2>/dev/null | tail -1)
  echo "$(stamp) $LBL END rc=$RC dir=$DIR" >> "$LEDGER"
  if [ -n "$DIR" ]; then
    local MARK
    MARK=$(grep -l "Reasoning style (MANDATORY)" "$DIR"/prompts/* 2>/dev/null | wc -l)
    echo "$(stamp) $LBL marker_games_with_treatment=$MARK (expect 25 for compact, 0 for baseline)" >> "$LEDGER"
    python3 - "$REF" "$DIR/run_config.json" "$LBL" >> "$LEDGER" 2>&1 <<'PY'
import json,sys
ref,new,lbl=sys.argv[1],sys.argv[2],sys.argv[3]
a=json.load(open(ref)); b=json.load(open(new))
def flat(d,p=""):
    o={}
    if isinstance(d,dict):
        for k,v in d.items(): o.update(flat(v,p+"."+k))
    elif isinstance(d,list): o[p]=json.dumps(d)
    else: o[p]=d
    return o
fa,fb=flat(a),flat(b)
IGN={".generated_at",".deployment.kaggle.kernel_slug",".deployment.kaggle.kernel_title"}
d=[k for k in set(fa)|set(fb) if fa.get(k)!=fb.get(k) and k not in IGN]
print(f"{lbl} config_parity_vs_ref unexpected_diffs={sorted(d)}")
PY
  fi
}

echo "$(stamp) DRIVER START pid=$$" >> "$LEDGER"
run_pass P1 compact  qwen38-27b-mp-compact-p1
run_pass P2 baseline qwen38-27b-mp-baseline-p1
run_pass P3 compact  qwen38-27b-mp-compact-p2
run_pass P4 baseline qwen38-27b-mp-baseline-p2
echo "$(stamp) DRIVER DONE" >> "$LEDGER"
