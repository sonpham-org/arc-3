#!/usr/bin/env bash
# Author: Claude Opus 5 (Bubba sub-agent, label arc3-oracle-driver-and-launch)
# Date: 18-September-2026
# PURPOSE: Sequential multi-pass B/O driver for the oracle test on gx10-a108
# (docs/plans/2026-09-18-oracle-test-plan.md step 4). Runs one-pass seven-game runs back to
# back, alternating arm B (control) and arm O (rulebook injected), at the operating point the
# compact-reasoning multipass used: 7 lanes, 90 min/game, n_passes 1, qwen38-27b-nvfp4 against
# the already-serving vLLM. Per pass it ledgers the vLLM PID/health before and after, the
# treatment marker in the prompt logs (in flight AND at the end), and run_config parity against
# the first pass. Arms alternate so neither monopolises a time of day; passes never overlap,
# because lane contention correlates with the treatment if they do.
#
# Resumable. Every finished pass drops a file in $WORK/banked/, and a re-run skips it. Appending
# a second B/O/B/O cycle is `PASS_PLAN="$DEFAULT_PLAN P5:B:...-b-p3 ..."` with no banked pass
# repeated. Boss's 18-Sep instruction was FOUR passes total (two per arm), not plan section 3's
# eight; the deviation is recorded in docs/trace-findings/2026-09-18-oracle-test-launch.md.
#
# Every run name contains the literal `oracle`, arm B included: the two arms share this
# experiment's run tree and arm-B transcripts here sit beside the answer key, so
# distill/extract_sft.py's `*-oracle-*` refusal must cover both (distill/README.md section 1).
# SRP/DRY check: Pass - adapted from scripts/run_style_multipass.sh, which drives a different
# experiment's arms (ARC3_REASONING_STYLE) over 25 games with the duck-public-harness game
# selector. That selector is mutually exclusive with `--game`, so a seven-game run cannot reuse
# it and this is a separate driver rather than a flag on that one. The marker guard is
# scripts/check_oracle_marker.sh and is called, not restated.
set -u

WORK=${WORK:-$HOME/arc3-oracle-20260918}
INF=${INF:-$HOME/GitHub/arc-3/ARC3-Inference}
RULES_DIR=${RULES_DIR:-$HOME/GitHub/arc-3/datasets/explainer-games/rulebooks}
GAMES=${GAMES:-dc22,g50t,m0r0,sc25,sk48,tn36,tr87}
NGAMES=${NGAMES:-7}
VPID=${VPID:-765547}
CONFIG=${CONFIG:-configs/a108.qwen38.baseline.json}
LANES=${LANES:-7}
CAP_MIN=${CAP_MIN:-90}          # 5,400 s per game, the multipass's cap
MARKER_WAIT_MIN=${MARKER_WAIT_MIN:-30}

DEFAULT_PLAN="P1:B:qwen38-27b-oracle-b-p1 P2:O:qwen38-27b-oracle-o-p1 P3:B:qwen38-27b-oracle-b-p2 P4:O:qwen38-27b-oracle-o-p2"
PASS_PLAN=${PASS_PLAN:-$DEFAULT_PLAN}

mkdir -p "$WORK/logs" "$WORK/guards" "$WORK/banked"
LEDGER=$WORK/guards/ledger.txt
REF=$WORK/guards/reference_run_config.json

stamp(){ date -Iseconds; }
say(){ echo "$(stamp) $*" >> "$LEDGER"; }

guard_vllm(){ # $1 = when-label, $2 = pass-label ; returns 1 if the server is gone
  local et
  et=$(ps -o etime= -p "$VPID" 2>/dev/null | tr -d ' ')
  if [ -z "$et" ]; then
    say "$2 vllm_$1 PID_${VPID}_DEAD"
    return 1
  fi
  say "$2 vllm_$1 pid=$VPID etime=$et health=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:1234/health)"
  return 0
}

run_dir_for(){ ls -1d "$INF"/runs/*_"$1" 2>/dev/null | tail -1; }

# Parity of a pass's run_config against the first pass's. `.games` is compared as a sorted set
# because the harness does not promise lane order, and the three run-identity fields below
# differ by construction. Anything else differing means the arms were not matched, which is the
# whole experiment.
parity(){ # $1 = pass label, $2 = this pass's run_config.json
  python3 - "$REF" "$2" "$1" >> "$LEDGER" 2>&1 <<'PY'
import json,sys
ref,new,lbl=sys.argv[1],sys.argv[2],sys.argv[3]
def flat(d,p=""):
    o={}
    if isinstance(d,dict):
        for k,v in d.items(): o.update(flat(v,p+"."+k))
    elif isinstance(d,list): o[p]=json.dumps(sorted(map(str,d)))
    else: o[p]=d
    return o
fa,fb=flat(json.load(open(ref))),flat(json.load(open(new)))
IGN={".generated_at",".deployment.kaggle.kernel_slug",".deployment.kaggle.kernel_title"}
d=[k for k in set(fa)|set(fb) if fa.get(k)!=fb.get(k) and k not in IGN]
print(f"{lbl} config_parity_vs_P1 unexpected_diffs={sorted(d)}")
PY
}

# `make` is not a process-group leader here (no job control in a script) and it spawns
# `uv run` -> python, so killing make alone leaves the harness running. Walk the tree.
kill_tree(){
  local p=$1 c
  for c in $(pgrep -P "$p" 2>/dev/null); do kill_tree "$c"; done
  kill -TERM "$p" 2>/dev/null
}

# In-flight treatment check. The failure this exists for is a missing (or stale) export on one
# of four launches: arm O running untreated, or arm B running treated, either of which is a
# confidently wrong number. Waiting for the pass to end to find out wastes 90 minutes, so the
# guard fires as soon as all seven prompt logs exist and aborts the driver if it is wrong.
# It must not run before then: with zero logs the arm-B expectation (0) passes vacuously.
marker_watch(){ # $1 = pass label, $2 = run name, $3 = expected count, $4 = pid to kill
  local lbl=$1 name=$2 expect=$3 victim=$4 dir logs waited=0
  while [ "$waited" -lt $(( MARKER_WAIT_MIN * 60 )) ]; do
    kill -0 "$victim" 2>/dev/null || return 0        # pass ended on its own; final check covers it
    dir=$(run_dir_for "$name")
    if [ -n "$dir" ] && [ -d "$dir/prompts" ]; then
      logs=$(ls -1 "$dir"/prompts/* 2>/dev/null | wc -l | tr -d ' ')
      if [ "$logs" -ge "$NGAMES" ]; then
        if "$INF"/scripts/check_oracle_marker.sh "$dir" "$expect" >> "$LEDGER" 2>&1; then
          say "$lbl marker_inflight PASS after ${waited}s"
        else
          say "$lbl marker_inflight FAIL after ${waited}s -- killing pass and aborting driver"
          kill_tree "$victim"
          touch "$WORK/ABORTED"
        fi
        return 0
      fi
    fi
    sleep 20; waited=$(( waited + 20 ))
  done
  say "$lbl marker_inflight NOT_RUN -- fewer than $NGAMES prompt logs after ${MARKER_WAIT_MIN}m"
}

run_pass(){ # $1 = pass label, $2 = arm (B|O), $3 = run name
  local LBL=$1 ARM=$2 NAME=$3 RC DIR
  if [ -f "$WORK/banked/$LBL" ]; then
    say "$LBL SKIP already banked dir=$(cat "$WORK/banked/$LBL")"
    return 0
  fi
  say "$LBL START arm=$ARM name=$NAME"
  guard_vllm before "$LBL" || { say "$LBL ABORT vllm gone before launch"; touch "$WORK/ABORTED"; return 1; }

  cd "$INF" || return 1
  # Arm B is the untouched sparse-deletion prompt: the variable unset, which oracle_rules.py
  # reads as arm B and renders as the empty string. Neither arm sets ARC3_REASONING_STYLE --
  # that is the other experiment's toggle and compact is not this run's control.
  if [ "$ARM" = "O" ]; then export ARC3_ORACLE_RULES_DIR="$RULES_DIR"; else unset ARC3_ORACLE_RULES_DIR; fi
  unset ARC3_REASONING_STYLE
  local EXPECT=0; [ "$ARM" = "O" ] && EXPECT=$NGAMES
  say "$LBL env ARC3_ORACLE_RULES_DIR='${ARC3_ORACLE_RULES_DIR:-<unset>}' expect_marker_games=$EXPECT"

  make interactive CONFIG_PATH="$CONFIG" \
    AGENT=duck-harness \
    GAME="$GAMES" GAME_TAGS= EXCLUDE_GAME_TAGS= \
    N_PASSES=1 CONCURRENT_JOBS=$LANES MAX_RUNTIME_MINUTES=$CAP_MIN \
    RUN_NAME="$NAME" \
    > "$WORK/logs/$LBL.log" 2>&1 &
  local PID=$!
  say "$LBL launched make_pid=$PID log=$WORK/logs/$LBL.log"
  marker_watch "$LBL" "$NAME" "$EXPECT" "$PID" &
  local WATCHER=$!
  wait "$PID"; RC=$?
  kill "$WATCHER" 2>/dev/null
  unset ARC3_ORACLE_RULES_DIR

  guard_vllm after "$LBL"
  DIR=$(run_dir_for "$NAME")
  say "$LBL END rc=$RC dir=$DIR"
  [ -z "$DIR" ] && { say "$LBL ABORT no run dir produced"; touch "$WORK/ABORTED"; return 1; }

  if "$INF"/scripts/check_oracle_marker.sh "$DIR" "$EXPECT" >> "$LEDGER" 2>&1; then
    say "$LBL marker_final PASS"
  else
    say "$LBL marker_final FAIL -- this pass is NOT a valid $ARM pass"
  fi
  [ -f "$REF" ] || { cp "$DIR/run_config.json" "$REF" 2>/dev/null && say "$LBL run_config banked as the parity reference"; }
  parity "$LBL" "$DIR/run_config.json"
  echo "$DIR" > "$WORK/banked/$LBL"
  say "$LBL BANKED"
}

say "DRIVER START pid=$$ plan='$PASS_PLAN' games=$GAMES lanes=$LANES cap_min=$CAP_MIN rules_dir=$RULES_DIR"
rm -f "$WORK/ABORTED"
for SPEC in $PASS_PLAN; do
  IFS=: read -r L A N <<< "$SPEC"
  run_pass "$L" "$A" "$N" || break
  [ -f "$WORK/ABORTED" ] && { say "DRIVER ABORT after $L"; break; }
done
say "DRIVER DONE aborted=$([ -f "$WORK/ABORTED" ] && echo yes || echo no)"
