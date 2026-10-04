#!/bin/bash
# RL v1 round N from rollout-server tries (4-Oct-2026, Son: "you don't just play the games better from the beginning,
# you also try to play the game better from everywhere"). Instead of full-game panels, the previous round's merged
# model plays K stock sibling tries from saved game moments of the 14 training games, on rollout-server VMs (the
# 4-Oct fast build: forks per free lane, 16 lanes); every finished try is scored against its siblings (try_records.py:
# reward = level score, advantage = reward - sibling mean) and the round trains on those, with run_round_v3.sh's
# recipe (clip + KL to the round start, adapter and optimizer carried over, 4 copies).
#   SHA=<code snapshot with try_records.py> NB=<gs://.../notebook.ipynb from build_rl_notebook.py --upload> \
#       bash ops/run_round_tries.sh <N>
# Steps (each logged with its UTC time):
#   0. wait for round N-1's merge (the RL page's merge_job, or PREV_MERGE)
#   1. MIRROR_BASE=daniel-draft make_eval_mirror.sh: Daniel's inputs with the tuned drafter + the merged shards
#   2. rl_loop.py init --campaign CAMPAIGN --modes stock --games <train 14>; VMS rollout VMs on that input copy
#   3. rl_loop.py run (refills only: --min-steps so high it never trains a coach policy) until every VM finished;
#      a VM lost before its finish line is relaunched once (its finished tries are already in rl/<C>/tries/)
#   4. trainer job <J>T-nN-records: try_records.py + select_records.py -> /opt/m/work/records/<J><T>
#   5. RECORDS=<J><T> run_round_v3.sh N: train from round N-1's adapter, merge, test panels, loop check
# Env: VMS (2), K (8 = the most siblings a node gets), STAGE_K (4 first), FRONTIER (0.9), LIMIT (40 nodes per
#      refill), BUDGET (48 records), TAG (t), CAMPAIGN (v1r<N>-<MMDD>),
#      TRAINER_VM / TRAINER_ZONE (passed on), DRYRUN=1 (prints the plan and the records job, launches nothing).
set -uo pipefail
export CLOUDSDK_PYTHON='C:\python312\python.exe'
OPS=$(cd "$(dirname "$0")" && pwd)
RLDIR=$(cd "$OPS/.." && pwd)
GT=$(cd "$OPS/../../gtree-rollout" && pwd)
SITE=$(cd "$OPS/../site" && pwd)
B=gs://cellens-ai-artifacts/arc3-rl/trainer/train4-1002
STORE=gs://cellens-ai-artifacts/arc3-gtree/v1
WORK=/d/codex-work/rl-20261001
SHA=${SHA:?set SHA to a code snapshot with try_records.py (ops/push_code.sh)}
NB=${NB:?set NB to the rollout notebook (build_rl_notebook.py --upload)}
N=${1:?round number, at least 1}
[ "$N" -ge 1 ] || { echo "round 0 has no previous model to play: use run_round_v3.sh 0"; exit 1; }
PREV=n$((N - 1))
VMS=${VMS:-2} K=${K:-8} LIMIT=${LIMIT:-40} BUDGET=${BUDGET:-48} T=${TAG:-t}
STAGE_K=${STAGE_K:-4} FRONTIER=${FRONTIER:-0.9}   # 4-Oct picker: 4 tries first, a top-up to K where they split;
                                                  # no restarts on levels the seed plays clear >= 90% of the time
CAMPAIGN=${CAMPAIGN:-v1r$N-$(date -u +%m%d)}
GAMES=bp35,cn04,g50t,ka59,ls20,m0r0,r11l,s5i5,sc25,sk48,sp80,tu93,vc33,wa30     # site_config.json split.train
ZONES="us-east5-a us-east5-b us-east5-c us-central1-a us-central1-b us-central1-c us-central1-f us-east4-a us-east4-b
       us-east4-c us-south1-a us-south1-b us-west4-a us-west4-b us-west4-c us-west1-a us-west1-b us-west1-c us-east1-b
       us-east1-d us-west3-a"
J=$((103 + 3 * N))
JR=$(printf '%03d%s-n%d-records' $J "$T" $N) REC=$(printf '%03d%s' $J "$T")
say() { echo "$(date -u +%H:%M) $*"; }
g() { timeout 120 gcloud "$@"; }
LBL=$(echo "$CAMPAIGN" | tr -cd 'a-z0-9')                                  # VM labels: arc3-rl-<LBL><a|b|...>

# ---------------------------------------------------------------- 0. round N-1's merged model
PJM=${PREV_MERGE:-$(C:/Python312/python.exe -c "import json,sys; c=json.load(open(sys.argv[1],encoding='utf-8')); m=c.get('merge_job') or ''; print(m if m.endswith('-'+sys.argv[2]+'-merge') else '')" "$SITE/site_config.json" "$PREV" | tr -d '\r')}
[ -n "$PJM" ] || { say "no $PREV merge job on the RL page (set PREV_MERGE)"; exit 1; }
say "round n$N from tries: campaign $CAMPAIGN, $VMS VMs x 16 lanes, K=$K stock siblings, games $GAMES; plays $PJM; records job $JR (budget $BUDGET)"

# the records job (written now so a dry run shows it)
C:/Python312/python.exe - "$WORK" "$SHA" "$JR" "$REC" "$CAMPAIGN" "$BUDGET" "n$N" <<'PY' || { echo "records job not written"; exit 1; }
import json, sys
work, sha, jr, rec, campaign, budget, rnd = sys.argv[1:]
tries, out = f"/opt/m/work/tries/{campaign}", f"/opt/m/work/records/{rec}"
cmd = (f"set -e; cd /opt/rl && gcloud storage cp 'gs://cellens-ai-artifacts/arc3-rl/code/{sha}/*' /opt/rl/ && "
       f"rm -rf {tries} {out} && mkdir -p {tries} {out} && "
       f"gcloud storage rsync -r gs://cellens-ai-artifacts/arc3-gtree/v1/rl/{campaign}/tries {tries}/tries && "
       f"/opt/rl/venv/bin/python try_records.py --tries {tries}/tries --out {tries}/candidates.jsonl.gz --modes stock "
       f"--campaign {campaign} --report {tries}/report.json && "
       f"/opt/rl/venv/bin/python select_records.py --in {tries}/candidates.jsonl.gz --out {out} --budget {budget} "
       f"> {tries}/selected.json && cat {tries}/selected.json && ls {out}/*.jsonl.gz > /dev/null && "
       f"gcloud storage cp {tries}/report.json {tries}/selected.json gs://cellens-ai-artifacts/arc3-rl/rl-1004-{rnd}/tries/")
assert "/opt/m/work/" in cmd and "Program Files" not in cmd and "Files/Git" not in cmd, "a Windows path got into the command"
open(f"{work}/job-{jr}.json", "w", newline="\n").write(json.dumps({"cmd": "shell", "args": {"command": cmd}}))
print("records job written")
PY
if [ -n "${DRYRUN:-}" ]; then cat "$WORK/job-$JR.json"; echo; exit 0; fi

until code=$(g storage cat "$B/out/$PJM/EXIT" 2>/dev/null | tr -d '\r\n ') && [ -n "$code" ]; do sleep 120; done
[ "$code" = 0 ] || { say "$PJM ended with exit $code: no model to play"; exit 1; }
say "$PJM merged"

# ---------------------------------------------------------------- 1. the model the tries play
IN=$(MIRROR_BASE=daniel-draft bash "$OPS/make_eval_mirror.sh" "$PREV-rollout" "$B/out/$PJM/merged" | tail -n 1 | tr -d '\r')
case "$IN" in gs://*kaggle-input-*) ;; *) say "rollout input copy failed ($IN)"; exit 1;; esac
say "rollout input $IN"

# ---------------------------------------------------------------- 2. campaign + VMs
cd "$GT" || exit 1
PICK="--modes stock --K $K --N $K --limit $LIMIT --stage-k $STAGE_K --frontier $FRONTIER"
C:/Python312/python.exe rl_loop.py init --campaign "$CAMPAIGN" $PICK --games "$GAMES" --lanes 16 | tail -n 1 \
    || { say "campaign init failed"; exit 1; }
g storage cp runner/rl_host_sync.py ../gtree-ingest/gtree_store.py ../gtree-ingest/gtree_ctx.py \
    gs://cellens-ai-artifacts/arc3-gtree/rollout-code/ > /dev/null 2>&1 || { say "host code upload failed"; exit 1; }
launch() {   # <label>: first zone with capacity (the zone list again after a full pass, for up to 30 min)
  local t0=$SECONDS
  while [ $((SECONDS - t0)) -lt 1800 ]; do
    INPUT_PREFIX=$IN bash runner/launch_rl_vm.sh "$1" "$CAMPAIGN" "$NB" $ZONES | tail -n 1 | grep -q "^launched" && {
      say "launched arc3-rl-$1"; return 0; }
    sleep 60
  done
  say "arc3-rl-$1: no capacity in 30 min"; return 1
}
LABELS=""
for i in $(seq 1 "$VMS"); do LABELS="$LABELS $LBL$(printf "\\x$(printf %x $((96 + i)))")"; done
for l in $LABELS; do launch "$l" & done; wait

# ---------------------------------------------------------------- 3. refills until every VM has finished
# the refills pick with the same rule as init (4-Oct: run had no --modes/--K/--N, so every refill fell back to
# coached modes, K 5, N 4, and try_records --modes stock would then drop those tries)
C:/Python312/python.exe rl_loop.py run --campaign "$CAMPAIGN" --every 10 --no-publish --min-steps 99999999 --lanes 16 \
    $PICK > "$WORK/learner-$CAMPAIGN.log" 2>&1 &
LPID=$!
declare -A RELAUNCHED=()
while true; do
  left=0
  for l in $LABELS; do
    last=$(g storage cat "$STORE/rl/$CAMPAIGN/runs/rl-$CAMPAIGN-$l/phases.tsv" 2>/dev/null | tail -n 1 | cut -f2 | tr -d '\r')
    case "$last" in finish*) continue;; esac
    if [ -z "$(g compute instances list --filter="name=arc3-rl-$l" --format='value(name)' 2>/dev/null | tr -d '\r')" ]; then
      if [ -z "${RELAUNCHED[$l]:-}" ]; then
        say "arc3-rl-$l is gone before its finish (${last:-no phases}): relaunching as arc3-rl-${l}2"
        RELAUNCHED[$l]=1; launch "${l}2" && LABELS="$LABELS ${l}2"
      else
        say "arc3-rl-$l is gone before its finish (${last:-no phases}); not relaunched again"
      fi
      continue
    fi
    left=$((left + 1))
  done
  [ "$left" -eq 0 ] && break
  sleep 300
done
kill $LPID 2>/dev/null
say "tries done: $(g storage ls "$STORE/rl/$CAMPAIGN/tries/**/result.json" 2>/dev/null | wc -l) finished tries uploaded"

# ---------------------------------------------------------------- 3b. gate: the model that played must not loop
# (Son 4-Oct: never stack a round on a model that copy-pastes its reasoning, as the first recipe's R1-R3 did.) Round N
# trains from round N-1's adapter, so wait for N-1's train and hard panels (re-read from the RL page each time: a panel
# lost to Spot is relaunched as letter b) and run loop_check.py on them; LOOPING (> 1% of the thinking repeated) stops
# the round before its records. NO_LOOP_GATE=1 skips the check; LOOP_WAIT_H (8) bounds the wait.
RUNS=${RUNS:-gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs}
if [ -z "${NO_LOOP_GATE:-}" ]; then
  t0=$SECONDS
  while true; do
    read -r PTR PHR < <(C:/Python312/python.exe - "$SITE/site_config.json" "$PREV" <<'PY' | tr -d '\r'
import json, sys
cfg = json.load(open(sys.argv[1], encoding="utf-8"))
runs = {p["key"]: (p["runs"].get(sys.argv[2]) or ["-"])[-1] for p in cfg["panels"]}
print(runs.get("train", "-") or "-", runs.get("hard", "-") or "-")
PY
)
    done_n=0
    for r in $PTR $PHR; do
      [ "$r" != "-" ] && g storage cat "$RUNS/$r/phases.tsv" 2>/dev/null | tail -n 1 | grep -q "finish" && done_n=$((done_n + 1))
    done
    [ "$done_n" -eq 2 ] && break
    [ $((SECONDS - t0)) -gt $(( ${LOOP_WAIT_H:-8} * 3600 )) ] && { say "$PREV panels not finished after ${LOOP_WAIT_H:-8} h: round $N not trained"; exit 1; }
    sleep 120
  done
  lc=$(C:/Python312/python.exe "$OPS/loop_check.py" $PTR $PHR | tr -d '\r')
  echo "$lc" | sed "s/^/$(date -u +%H:%M) loop check $PREV: /"
  echo "$lc" | tail -n 1 | grep -q "^LOOPING" && { say "$PREV loops: round $N not trained (NO_LOOP_GATE=1 overrides)"; exit 1; }
  say "$PREV passed the loop check: round $N trains"
fi

# ---------------------------------------------------------------- 4. records on the trainer, 5. train + merge + panels
g storage cp "$WORK/job-$JR.json" "$B/jobs/$JR.json" > /dev/null 2>&1 || { say "could not queue $JR"; exit 1; }
say "queued $JR"
RECORDS=$REC JOBTAG=$T SHA=$SHA BUDGET=$BUDGET bash "$OPS/run_round_v3.sh" "$N"
