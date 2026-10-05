#!/bin/bash
# RL v1 round N on the RL box (4-Oct-2026, Son: "just take 8 GPU and redo everything"; rl/box/README.md): one
# g4-standard-384 (8x RTX PRO 6000) in us-central1 plays the round's tries AND trains, taking turns: all 8 cards run
# rollout servers until STOP, then all 8 train (a round's tries must be played by the newest model, so play and
# training never overlap). run_round_tries.sh with:
#   - servers = slot requests to the box (box_agent.sh starts box_slot.sh on a free card), not VMs;
#   - STOP PLAY_MIN after the first server is ready (not after a fixed boot allowance);
#   - every server's finish line comes after its last upload (box_slot.sh), so the records job never misses tries;
#   - training through run_round_v3b.sh: KEEP_TRAINER=1 (the box is never stopped), DP=8 (one copy per card);
#   - EXTRA_TRIES: campaigns the SAME model played (round 1's stopped first attempt, v1r1-1004) join the records;
#   - no variant model (it would train while the next round plays, on the same cards).
# The test panels stay on 1-card VMs in other regions (ops/launch_panels.sh), off the critical path.
#   BOX=arc3-rl-box1 BOX_ZONE=us-central1-b SHA=<code> NB=<gs://.../notebook.ipynb> PREV_MERGE=105k-n0-merge \
#       EXTRA_TRIES=v1r1-1004 bash ops/run_round_box.sh 1
# Env: SLOTS (8), PLAY_MIN (30), K (8), STAGE_K (4), LIMIT (64 nodes a refill), BUDGET (48 records), TAG (b: jobs
#      106b/107b/108b for round 1), CAMPAIGN (v1r<N><TAG>-<MMDD>), MIX, FRONTIER, FRONTIER_RUNS, HISTORY, DP (8),
#      PREV_MERGE, PREV_TRAIN, EXTRA_TRIES, NO_EXTRA_PANELS, NO_LOOP_GATE, MAX_WAIT_MIN (PLAY_MIN + 60: stop waiting
#      for servers that never finish), DRYRUN=1.
set -uo pipefail
export CLOUDSDK_PYTHON='C:\python312\python.exe'
OPS=$(cd "$(dirname "$0")" && pwd)
GT=$(cd "$OPS/../../gtree-rollout" && pwd)
SITE=$(cd "$OPS/../site" && pwd)
B=gs://cellens-ai-artifacts/arc3-rl/trainer/train4-1002
STORE=gs://cellens-ai-artifacts/arc3-gtree/v1
WORK=/d/codex-work/rl-20261001
BOX=${BOX:?set BOX to the RL box VM} BOX_ZONE=${BOX_ZONE:?set BOX_ZONE}
BOXQ=gs://cellens-ai-artifacts/arc3-rl/box/$BOX
SHA=${SHA:?set SHA to a code snapshot with try_records.py (ops/push_code.sh)}
NB=${NB:?set NB to the rollout notebook (build_rl_notebook.py --upload)}
N=${1:?round number, at least 1}
[ "$N" -ge 1 ] || { echo "round 0 has no previous model to play"; exit 1; }
PREV=n$((N - 1))
SLOTS=${SLOTS:-8} K=${K:-8} LIMIT=${LIMIT:-64} BUDGET=${BUDGET:-48} T=${TAG:-b} PLAY_MIN=${PLAY_MIN:-30}
MAX_WAIT_MIN=${MAX_WAIT_MIN:-$((PLAY_MIN + 60))}
MIX=${MIX:-level_start=0.35,backward=0.25,unresumed=0.15,uncertain=0.25}
STAGE_K=${STAGE_K:-4} FRONTIER=${FRONTIER:-0.8}
CAMPAIGN=${CAMPAIGN:-v1r$N$T-$(date -u +%m%d)}
GAMES=bp35,cn04,g50t,ka59,ls20,m0r0,r11l,s5i5,sc25,sk48,sp80,tu93,vc33,wa30     # site_config.json split.train
J=$((103 + 3 * N))
JR=$(printf '%03d%s-n%d-records' $J "$T" $N) REC=$(printf '%03d%s' $J "$T")
say() { echo "$(date -u +%H:%M) $*"; }
g() { timeout 120 gcloud "$@"; }
LBL=$(echo "$CAMPAIGN" | tr -cd 'a-z0-9')

# ---------------------------------------------------------------- 0. round N-1's merged model
PJM=${PREV_MERGE:-$(C:/Python312/python.exe -c "import json,sys; c=json.load(open(sys.argv[1],encoding='utf-8')); m=c.get('merge_job') or ''; print(m if m.endswith('-'+sys.argv[2]+'-merge') else '')" "$SITE/site_config.json" "$PREV" | tr -d '\r')}
[ -n "$PJM" ] || { say "no $PREV merge job on the RL page (set PREV_MERGE)"; exit 1; }
PJN=${PJM%%[!0-9]*}
PREV_TRAIN=${PREV_TRAIN:-$(printf '%03d' $((10#$PJN - 1)))${PJM#$PJN}}
PREV_TRAIN=${PREV_TRAIN%-merge}; PREV_TRAIN=${PREV_TRAIN%-train}-train
say "round n$N on box $BOX: campaign $CAMPAIGN, $SLOTS cards x 16 lanes, $PLAY_MIN min of play, K=$K; plays $PJM; records job $JR (budget $BUDGET${EXTRA_TRIES:+, + tries of $EXTRA_TRIES})"

C:/Python312/python.exe - "$WORK" "$SHA" "$JR" "$REC" "$CAMPAIGN" "$BUDGET" "n$N" "${EXTRA_TRIES:-}" <<'PY' || { echo "records job not written"; exit 1; }
import json, sys
work, sha, jr, rec, campaign, budget, rnd, extra = sys.argv[1:]
tries, out = f"/opt/m/work/tries/{campaign}", f"/opt/m/work/records/{rec}"
camps = [campaign] + [c for c in extra.replace(",", " ").split() if c]
pull = " && ".join(f"mkdir -p {tries}/{c} && gcloud storage rsync -r gs://cellens-ai-artifacts/arc3-gtree/v1/rl/{c}/tries {tries}/{c}"
                   for c in camps)
cmd = (f"set -e; cd /opt/rl && gcloud storage cp 'gs://cellens-ai-artifacts/arc3-rl/code/{sha}/*' /opt/rl/ && "
       f"rm -rf {tries} {out} && mkdir -p {tries} {out} && {pull} && "
       f"/opt/rl/venv/bin/python try_records.py " + " ".join(f"--tries {tries}/{c}" for c in camps) +
       f" --out {tries}/candidates.jsonl.gz --modes stock --campaign {campaign} --report {tries}/report.json && "
       f"/opt/rl/venv/bin/python select_records.py --in {tries}/candidates.jsonl.gz --out {out} --budget {budget} "
       f"> {tries}/selected.json && cat {tries}/selected.json && ls {out}/*.jsonl.gz > /dev/null && "
       f"gcloud storage cp {tries}/report.json {tries}/selected.json gs://cellens-ai-artifacts/arc3-rl/rl-1004-{rnd}/tries/")
assert "/opt/m/work/" in cmd and "Program Files" not in cmd and "Files/Git" not in cmd, "a Windows path got into the command"
open(f"{work}/job-{jr}.json", "w", newline="\n").write(json.dumps({"cmd": "shell", "args": {"command": cmd}}))
print("records job written")
PY
if [ -n "${DRYRUN:-}" ]; then cat "$WORK/job-$JR.json"; echo; exit 0; fi
g storage ls "$B/jobs/$JR.json" > /dev/null 2>&1 && { say "$JR is already queued: pick another TAG"; exit 1; }

until code=$(g storage cat "$B/out/$PJM/EXIT" 2>/dev/null | tr -d '\r\n ') && [ -n "$code" ]; do sleep 60; done
[ "$code" = 0 ] || { say "$PJM ended with exit $code: no model to play"; exit 1; }
say "$PJM merged"

box_status() { g compute instances describe "$BOX" --zone "$BOX_ZONE" --format='value(status)' 2>/dev/null | tr -d '\r'; }
box_up() {   # the box RUNNING with a live agent (slots.json written in the last 3 min); starts a stopped box
  local t0=$SECONDS st at
  while [ $((SECONDS - t0)) -lt 3600 ]; do
    st=$(box_status)
    case "$st" in
      TERMINATED|STOPPED|SUSPENDED) g compute instances start "$BOX" --zone "$BOX_ZONE" > /dev/null 2>&1 && say "box was $st: started" ;;
      RUNNING)
        at=$(g storage cat "$BOXQ/slots.json" 2>/dev/null | C:/Python312/python.exe -c "import json,sys,time,calendar; d=json.load(sys.stdin); print(int(time.time()-calendar.timegm(time.strptime(d['at'],'%Y-%m-%dT%H:%M:%SZ'))))" 2>/dev/null | tr -d '\r')
        [ -n "$at" ] && [ "$at" -lt 180 ] && return 0 ;;
    esac
    sleep 60
  done
  return 1
}
box_up || { say "box $BOX not up with a live agent after 60 min"; exit 1; }

# ---------------------------------------------------------------- 1. the model the tries play
IN=$(MIRROR_BASE=daniel-draft bash "$OPS/make_eval_mirror.sh" "$PREV-rollout" "$B/out/$PJM/merged" | tail -n 1 | tr -d '\r')
case "$IN" in gs://*kaggle-input-*) ;; *) say "rollout input copy failed ($IN)"; exit 1;; esac
say "rollout input $IN"

# ---------------------------------------------------------------- 2. campaign + slot requests
cd "$GT" || exit 1
if [ -z "${FRONTIER_RUNS:-}" ]; then
  if [ "$N" -eq 1 ]; then
    FRONTIER_RUNS=$(C:/Python312/python.exe -c "import pick_nodes; print(','.join(pick_nodes.BASE_RUNS))" | tr -d '\r')
  else
    FRONTIER_RUNS=$(C:/Python312/python.exe -c "import json,sys; c=json.load(open(sys.argv[1],encoding='utf-8')); print(','.join(r for p in c['panels'] if p['key'] in ('train','hard') for r in (p['runs'].get(sys.argv[2]) or []) if r))" "$SITE/site_config.json" "$PREV" | tr -d '\r')
  fi
fi
say "frontier counted from: $FRONTIER_RUNS"
touch "$WORK/tries-campaigns.txt"
HISTORY=${HISTORY:-$(echo "rl1 rl2 speed1 speed2 $(grep -v "^$CAMPAIGN$" "$WORK/tries-campaigns.txt" | tr '\n' ' ')" | tr -s ' ' ',' | sed 's/^,//; s/,$//')}
grep -qx "$CAMPAIGN" "$WORK/tries-campaigns.txt" || echo "$CAMPAIGN" >> "$WORK/tries-campaigns.txt"
say "picker: mix $MIX; resumes counted from campaigns $HISTORY"
PICK="--modes stock --K $K --N $K --limit $LIMIT --stage-k $STAGE_K --frontier $FRONTIER --frontier-runs $FRONTIER_RUNS --mix $MIX --history-campaigns $HISTORY"
C:/Python312/python.exe rl_loop.py init --campaign "$CAMPAIGN" $PICK --games "$GAMES" --lanes 16 | tail -n 1 \
    || { say "campaign init failed"; exit 1; }
g storage cp runner/rl_host_sync.py ../gtree-ingest/gtree_store.py ../gtree-ingest/gtree_ctx.py \
    gs://cellens-ai-artifacts/arc3-gtree/rollout-code/ > /dev/null 2>&1 || { say "host code upload failed"; exit 1; }
request() {   # <label>: one rollout server on the next free card
  printf 'RUN_ID=rl-%s-%s\nNB_OBJ=%s\nCAMPAIGN=%s\nLABEL=%s\nIN=%s\n' "$CAMPAIGN" "$1" "$NB" "$CAMPAIGN" "$1" "$IN" \
    | g storage cp - "$BOXQ/requests/$1.env" > /dev/null 2>&1 && say "requested $1"
}
LABELS=""
for i in $(seq 1 "$SLOTS"); do LABELS="$LABELS $LBL$(printf "\\x$(printf %x $((96 + i)))")"; done
for l in $LABELS; do request "$l" & done; wait
LAUNCH_T0=$SECONDS PLAY_T0="" STOPPED=""

# ---------------------------------------------------------------- 3. refills until every server has finished
C:/Python312/python.exe rl_loop.py run --campaign "$CAMPAIGN" --every 10 --no-publish --min-steps 99999999 --lanes 16 \
    $PICK > "$WORK/learner-$CAMPAIGN.log" 2>&1 &
LPID=$!
declare -A RELAUNCHED=()
PH=$(mktemp -d)
while true; do
  for l in $LABELS; do
    ( g storage cat "$STORE/rl/$CAMPAIGN/runs/rl-$CAMPAIGN-$l/phases.tsv" 2>/dev/null | tr -d '\r' > "$PH/$l" ) &
  done; wait
  st=$(box_status)
  left=0 ready=0
  for l in $LABELS; do
    last=$(tail -n 1 "$PH/$l" | cut -f2)
    case "$last" in finish*) continue;; esac
    grep -q "server_ready" "$PH/$l" && ready=$((ready + 1))
    if [ -n "$st" ] && [ "$st" != RUNNING ] && [ -n "$last" ]; then     # the box went down (Spot) with this server on it
      if [ -z "${RELAUNCHED[$l]:-}" ]; then
        say "box is $st with $l unfinished (${last}): requesting ${l}2 for when it is back"
        RELAUNCHED[$l]=1; LABELS=$(echo "$LABELS" | sed "s/ $l\b//"); request "${l}2" && LABELS="$LABELS ${l}2"
      fi
      continue
    fi
    left=$((left + 1))
  done
  case "$st" in TERMINATED|STOPPED|SUSPENDED) g compute instances start "$BOX" --zone "$BOX_ZONE" > /dev/null 2>&1 && say "box was $st: started";; esac
  [ "$left" -eq 0 ] && break
  [ -z "$PLAY_T0" ] && [ "$ready" -gt 0 ] && { PLAY_T0=$SECONDS; say "first server ready: $PLAY_MIN min of play from now"; }
  if [ -z "$STOPPED" ] && [ -n "$PLAY_T0" ] && [ $((SECONDS - PLAY_T0)) -ge $((PLAY_MIN * 60)) ]; then
    echo stop | g storage cp - "$STORE/rl/$CAMPAIGN/STOP" > /dev/null 2>&1 && STOPPED=1 && \
      say "STOP after $PLAY_MIN min of play ($ready of $(echo $LABELS | wc -w) servers were ready): the servers finish their running nodes and end"
  fi
  if [ $((SECONDS - LAUNCH_T0)) -ge $((MAX_WAIT_MIN * 60)) ]; then
    [ -z "$STOPPED" ] && echo stop | g storage cp - "$STORE/rl/$CAMPAIGN/STOP" > /dev/null 2>&1 && STOPPED=1
    say "$left servers still unfinished after $MAX_WAIT_MIN min: going on without their last tries"; break
  fi
  sleep 60
done
kill $LPID 2>/dev/null
rm -rf "$PH"
say "tries done: $(g storage ls "$STORE/rl/$CAMPAIGN/tries/**/result.json" 2>/dev/null | wc -l) finished tries uploaded"

# ---------------------------------------------------------------- 3a. gate: the model that played must not loop
if [ -z "${NO_LOOP_GATE:-}" ]; then
  lc=$(C:/Python312/python.exe "$OPS/loop_check_tries.py" "$CAMPAIGN" | tr -d '\r')
  echo "$lc" | sed "s/^/$(date -u +%H:%M) loop check $PREV (tries): /"
  echo "$lc" | tail -n 1 | grep -q "^LOOPING" && { say "$PREV loops: round $N not trained (NO_LOOP_GATE=1 overrides)"; exit 1; }
  echo "$lc" | tail -n 1 | grep -q "^NO DATA" && { say "no replies logged in the tries: looping unchecked, round $N not trained (NO_LOOP_GATE=1 overrides)"; exit 1; }
  say "$PREV passed the loop check on its tries: round $N trains"
fi

# ---------------------------------------------------------------- 4. records on the box, 5. train + merge + panels
g storage cp "$WORK/job-$JR.json" "$B/jobs/$JR.json" > /dev/null 2>&1 || { say "could not queue $JR"; exit 1; }
say "queued $JR"
[ -z "${NO_EXTRA_PANELS:-}" ] && { bash "$OPS/extra_panels.sh" "n$N" >> "$WORK/extra_panels_n$N.log" 2>&1 & }
ROUND_NAME=n$N PREV_TRAIN=$PREV_TRAIN RECORDS=$REC JOBTAG=$T SHA=$SHA BUDGET=$BUDGET DP=${DP:-8} KEEP_TRAINER=1 \
  TRAINER_VM=$BOX TRAINER_ZONE=$BOX_ZONE bash "$OPS/run_round_v3b.sh" "$N"
