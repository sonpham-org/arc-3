#!/bin/bash
# run_round_v3b.sh = run_round_v3x.sh for the RL box (4-Oct-2026, Son: "just take 8 GPU and redo everything"): the
# trainer is the 8-card box that also plays the tries (rl/box/README.md), so
#   - KEEP_TRAINER=1 (set by run_round_box.sh): the box is never stopped here (v3x stops the trainer VM after its jobs);
#   - DP (8): one model copy per card on all 8 cards (play and training take turns, so training gets the whole box);
#     DP=4 gives v3x's 4-card jobs.
# A copy, not an edit: v3x was about to run round 1 when this was written (bash reads a running script as it goes).
#   KEEP_TRAINER=1 TRAINER_VM=<box> TRAINER_ZONE=<zone> PREV_TRAIN=104k-n0-train RECORDS=106b JOBTAG=b SHA=<code> \
#       bash ops/run_round_v3b.sh 1
# What follows is v3x's own description.
# run_round_v3x.sh = run_round_v3.sh + ROUND_NAME (a second model of the same round, e.g. n1v), TRAIN_EXTRA (extra
# lora_train flags) and MODEL_LABEL (its name on the RL page). Son 4-Oct: round 1 trains two models on the SAME
# records, the recipe and the recipe + --loss cispo --clip-high 0.28 --token-norm token, both tested on the panels.
# A copy, because run_round_v3.sh was executing (round 0) and bash reads a running script as it goes. It also fixes
# run_round_v3.sh's optimizer path for rounds >= 1: passed to Windows Python as /opt/..., Git Bash rewrote it and the
# job builder refused it (round 1's training would never have been queued). Use this script for rounds >= 1.
#   ROUND_NAME=n1v MODEL_LABEL='Round 1 variant' TRAIN_EXTRA='--loss cispo ...' PREV_TRAIN=104k-n0-train \
#   RECORDS=106t JOBTAG=u SHA=<code> bash ops/run_round_v3x.sh 1
# RL v1 round on the 4-Oct fast trainer (docs/plans/2026-10-04-rl-recipe-speed.md): run_round_v2.sh (same recipe:
# advantage-weighted records, half better / half worse than the game's average attempt, clipped update + KL to the
# round's start, adapter AND optimizer carried over) with
#   train:   4 model copies, one per GPU (--dp 4), packed experts mapped from /opt/m/daniel-stacked (stacked by the job
#            if missing, ~190 s once per disk), n-gram embeddings precomputed per record (--ple-cache), fused QSA kernel
#            + compiled hyper-connection mix (fast_qsa defaults): ~110 s per ~115k-token record per copy, vs ~7 min;
#            the job copies the code snapshot itself;
#   RECORDS: an existing records dir on the trainer disk, /opt/m/work/records/<name> (104 = n0's 24 records, built from
#            every base-model panel run) skips the records job and the wait for panels (Son 4-Oct: round 0 reuses the
#            seed data).
#   SHA=<code snapshot> [RECORDS=/opt/m/work/records/104] JOBTAG=k bash ops/run_round_v3.sh <N>
# Env as run_round_v2.sh (BUDGET, LR, CLIP, KL, TRAINER_VM / TRAINER_ZONE, JOBTAG, DRYRUN=1) + DP (4), RECORDS.
# Every gcloud poll runs under `timeout 120`: an expired login makes gcloud hang.
set -uo pipefail
export CLOUDSDK_PYTHON='C:\python312\python.exe'
OPS=$(cd "$(dirname "$0")" && pwd)
SITE=$(cd "$OPS/../site" && pwd)
VM=${TRAINER_VM:-arc3-rl-train4e-20261003} ZONE=${TRAINER_ZONE:-us-west3-a}
B=gs://cellens-ai-artifacts/arc3-rl/trainer/train4-1002
RUNS=gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs
WORK=/d/codex-work/rl-20261001
SHA=${SHA:?set SHA to a code snapshot (ops/push_code.sh)}
N=${1:?round number, e.g. 0}
ROUND=${ROUND_NAME:-n$N}
PREV=$([ "$N" -eq 0 ] && echo base || echo "n$((N - 1))")
BUDGET=${BUDGET:-24} LR=${LR:-5e-5} CLIP=${CLIP:-0.2} KL=${KL:-0.05} DP=${DP:-8} RECORDS=${RECORDS:-}
J=$((103 + 3 * N))                                       # n0: jobs 103-105, n1: 106-108, ...
T=${JOBTAG:-}
JR=$(printf '%03d%s-%s-records' $J "$T" $ROUND) JT=$(printf '%03d%s-%s-train' $((J + 1)) "$T" $ROUND)
JM=$(printf '%03d%s-%s-merge' $((J + 2)) "$T" $ROUND)
RECN=$(printf '%03d%s' $((J + 1)) "$T")                  # bare name: Git Bash rewrites /opt/... args to Windows Python
say() { echo "$(date -u +%H:%M) $*"; }
g() { timeout 120 gcloud "$@"; }
stop_trainer() { [ -z "${KEEP_TRAINER:-}" ] && g compute instances stop $VM --zone $ZONE > /dev/null 2>&1; }

# ---------------------------------------------------------------- 0. the previous round's plays and adapter
# base: every listed run of the panel (one policy, several runs = one bigger group); a round: its latest run
read -r TR HR PT < <(C:/Python312/python.exe - "$SITE/site_config.json" "$PREV" <<'PY' | tr -d '\r'
import json, sys
cfg = json.load(open(sys.argv[1], encoding="utf-8"))
key = sys.argv[2]
runs = {p["key"]: [r for r in (p["runs"].get(key) or []) if r] for p in cfg["panels"]}
pick = lambda k: ",".join(runs.get(k, []) if key == "base" else runs.get(k, [])[-1:]) or "-"
tj = cfg.get("train_job") or ""
print(pick("train"), pick("hard"), tj if tj.endswith(f"-{key}-train") else "-")
PY
)
TR=${TR//,/ } HR=${HR//,/ }
[ "$TR" = "-" ] && TR="" ; [ "$HR" = "-" ] && HR="" ; [ "$PT" = "-" ] && PT=""
if [ "$N" -eq 0 ]; then PREV_TRAIN="" PREV_OPTIM=""; else
  PREV_TRAIN=${PREV_TRAIN:-${PT:-$(printf '%03d-%s-train' $((J - 2)) $PREV)}}
  PREV_OPTIM=/opt/m/work/out/$PREV_TRAIN/optim.pt
fi
if [ -n "$RECORDS" ]; then
  say "$ROUND: records reused from $RECORDS (no records job); adapter ${PREV_TRAIN:-fresh}${PREV_OPTIM:+ + optimizer}; jobs $JT $JM"
else
  [ -n "$TR" ] && [ -n "$HR" ] || { say "no $PREV train/hard runs on the RL page"; exit 1; }
  say "$ROUND: records from every pass of $TR $HR (one group per game); adapter ${PREV_TRAIN:-fresh}${PREV_OPTIM:+ + optimizer}; jobs $JR $JT $JM"
  for r in $TR $HR; do
    until g storage cat "$RUNS/$r/phases.tsv" 2>/dev/null | tail -n 1 | grep -q "finish"; do sleep 120; done
    say "$r: $(g storage cat "$RUNS/$r/phases.tsv" | tail -n 1 | cut -f3)"
  done
fi

# ---------------------------------------------------------------- 1. the jobs
RECARG=${RECORDS#/opt/m/work/records/}                  # bare name (Git Bash would rewrite an /opt/... argument)
C:/Python312/python.exe - "$WORK" "$SHA" "$TR" "$HR" "$JR" "$JT" "$JM" "$PREV_TRAIN" "${PREV_OPTIM:+1}" "$RECN" "$ROUND" \
    "$PREV" "$BUDGET" "$LR" "$CLIP" "$KL" "$DP" "${RECARG:--}" <<'PY' || { echo "job files not written"; exit 1; }
import json, sys
import os
(work, sha, tr, hr, jr, jt, jm, prev_train, prev_optim, recn, rnd, prev, budget, lr, clip, kl, dp, reuse) = sys.argv[1:]
extra = os.environ.get("TRAIN_EXTRA", "").strip()
# a flag, not the path: Git Bash rewrites an /opt/... argument to Windows Python (4-Oct: it broke round 1's jobs)
prev_optim = f"/opt/m/work/out/{prev_train}/optim.pt" if prev_optim == "1" and prev_train else ""
rec, g0 = f"/opt/m/work/records/{recn}", f"/opt/m/work/g0{rnd}"
if reuse != "-":
    rec = f"/opt/m/work/records/{reuse}"
run_args = " ".join(f"--run {r}" for r in (tr.split() + hr.split()))
records = (f"set -e; cd /opt/rl && gcloud storage cp 'gs://cellens-ai-artifacts/arc3-rl/code/{sha}/*' /opt/rl/ && "
           f"rm -rf {rec} {g0} && mkdir -p {rec} {g0} && "
           f"/opt/rl/venv/bin/python g0_data.py {run_args} "
           "--root gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs --frontier frontier.json --hf /opt/m/bf16 "
           f"--campaign rl-1004-{rnd} --harness daniel-nb-v1 --policy {prev} --passes all --credit advantage "
           f"--out {g0}/all && "
           f"/opt/rl/venv/bin/python select_records.py --in '{g0}/all/records/*.jsonl.gz' --out {rec} --budget {budget} && "
           f"ls {rec} && gcloud storage rsync -r -x '.*/cache/.*' {g0} gs://cellens-ai-artifacts/arc3-rl/rl-1004-{rnd}/g0{rnd}")
env = "ARC3_OFFLOAD_MIN_ELEMS=1239040000 ARC3_MOE_TOKEN_CHUNK=32768 ARC3_NVFP4_CHUNK=128"
fast = ("--experts-source mmap --experts-stacked /opt/m/daniel-stacked "
        f"--ple-cache /opt/m/work/ple/{jt} ") if int(dp) > 1 else ""
train = (f"set -e; cd /opt/rl && gcloud storage cp 'gs://cellens-ai-artifacts/arc3-rl/code/{sha}/*' /opt/rl/ && "
         f"ls {rec}/*.jsonl.gz > /dev/null && "
         + (f"test -f /opt/m/work/out/{prev_train}/ADAPTER.json && " if prev_train else "")
         + (f"test -f {prev_optim} && " if prev_optim else "")
         + "{ test -f /opt/m/daniel-stacked/index.json || /opt/rl/venv/bin/python nvfp4_experts.py stack "
           "--ckpt /opt/m/daniel --out /opt/m/daniel-stacked; } && "
         + f"mkdir -p /opt/m/work/out/{jt} && {env} /opt/rl/venv/bin/python lora_train.py train "
         f"--model /opt/m/bf16 --hf /opt/m/bf16 --gpus {dp} --dp {dp} --gpu-gib 86 --nvfp4 /opt/m/daniel {fast}"
         f"--records '{rec}/*.jsonl.gz' --out /opt/m/work/out/{jt} "
         + (f"--init-adapter /opt/m/work/out/{prev_train} " if prev_train else "")
         + (f"--init-optim {prev_optim} " if prev_optim else "")
         + f"--clip {clip} --kl {kl} --epochs 1 --accum 4 --lr {lr} --warmup 2 --rank 32 --alpha 64 "
         "--max-tokens 121000 --ckpt-every 1" + (f" {extra}" if extra else ""))
merge = (f"set -e; test -f /opt/m/work/out/{jt}/ADAPTER.json && cd /opt/rl && mkdir -p /opt/m/work/out/{jm} && "
         f"/opt/rl/venv/bin/python merge_lora.py --adapter /opt/m/work/out/{jt} --checkpoint /opt/m/daniel "
         f"--out /opt/m/work/out/{jm}/merged --only-changed && ls -la /opt/m/work/out/{jm}/merged | head -50")
for name, cmd in (((jr, records),) if reuse == "-" else ()) + ((jt, train), (jm, merge)):
    assert "/opt/m/work/" in cmd and "Program Files" not in cmd and "Files/Git" not in cmd, f"{name}: a Windows path got into the command"
    open(f"{work}/job-{name}.json", "w", newline="\n").write(json.dumps({"cmd": "shell", "args": {"command": cmd}}))
print("job files written")
PY
QUEUE="$JR $JT $JM"; [ -n "$RECORDS" ] && QUEUE="$JT $JM"
if [ -n "${DRYRUN:-}" ]; then for j in $QUEUE; do echo "== $j"; cat "$WORK/job-$j.json"; echo; done; exit 0; fi
for j in $QUEUE; do
  gcloud storage cp "$WORK/job-$j.json" "$B/jobs/$j.json" > /dev/null 2>&1 || { say "could not queue $j"; exit 1; }
done
say "queued $QUEUE (code $SHA)"
C:/Python312/python.exe - "$SITE/site_config.json" "$N" "$ROUND" "$JT" "$JM" "$BUDGET" <<'PY'
import json, sys, time
path, n, rnd, jt, jm, budget = sys.argv[1:]
cfg = json.load(open(path, encoding="utf-8"))
cfg.update(round=f"Round {n} (fast trainer)", train_job=jt, merge_job=jm, records_total=int(budget),
           train_started=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
if not any(m["key"] == rnd for m in cfg["models"]):
    import os
    cfg["models"].append({"key": rnd, "label": os.environ.get("MODEL_LABEL") or f"Restart round {n}",
                          "short": os.environ.get("MODEL_SHORT") or f"N{n}",
                          "note": "every attempt, scored against the game's average attempt (better = pulled up, worse = "
                                  "pushed down), clipped update with a pull back to the round's start"})
cfg["next_model"] = None
open(path, "w", encoding="utf-8", newline="\n").write(json.dumps(cfg, indent=1, ensure_ascii=False) + "\n")
print("RL page follows", jt, jm)
PY

# ---------------------------------------------------------------- 2. the trainer, until the merge is done and uploaded
while true; do
  for j in ${QUEUE% *}; do  # the first failure is the one worth reading: later jobs fail on its missing outputs
    code=$(g storage cat "$B/out/$j/EXIT" 2>/dev/null | tr -d '\r\n ')
    if [ -n "$code" ] && [ "$code" != 0 ]; then
      say "$j failed (exit $code); last log lines:"; g storage cat "$B/out/$j/job.log" | tail -n 25
      stop_trainer && say "trainer VM stopped"; exit 1
    fi
  done
  g storage ls "$B/out/$JM/EXIT" > /dev/null 2>&1 && break
  st=$(g compute instances describe $VM --zone $ZONE --format='value(status)' 2>/dev/null | tr -d '\r')
  case "$st" in
    TERMINATED|STOPPED|SUSPENDED)
      if out=$(g compute instances start $VM --zone $ZONE 2>&1); then
        say "trainer VM was $st; started (jobs resume from their checkpoints)"
      else
        say "trainer start refused ($(echo "$out" | grep -oiE "QUOTA_EXCEEDED|Quota '[A-Z0-9_]*' exceeded|STOCKOUT|ZONE_RESOURCE_POOL_EXHAUSTED|not enough resources|timed out" | head -n 1)); retrying"
      fi ;;
    "") say "could not read the trainer's status (gcloud login?)" ;;
  esac
  sleep 180
done
while hb=$(g storage cat "$B/status.json" 2>/dev/null); [ -z "$hb" ] || \
      { echo "$hb" | grep -q '"state": "running"' && echo "$hb" | grep -q "\"job\": \"$JM\""; }; do sleep 60; done
code=$(g storage cat "$B/out/$JM/EXIT" | tr -d '\r\n ')
if [ "$code" != 0 ]; then
  say "merge failed (exit $code)"; g storage cat "$B/out/$JM/job.log" | tail -n 25
  stop_trainer; exit 1
fi
say "$ROUND trained on $(g storage cat "$B/out/$JT/ADAPTER.json" | tr -d '\r\n' | grep -o '"records": [0-9]*') and merged"
stop_trainer && say "trainer VM stopped (no jobs left)"

# ---------------------------------------------------------------- 3. the test panels, then the looping check
bash "$OPS/make_eval_mirror.sh" $ROUND "$B/out/$JM/merged" || { say "LoRA input copy failed"; exit 1; }
say "LoRA input copy staged for $ROUND"
bash "$OPS/launch_panels.sh" $ROUND a
LOST=""
for pb in "held:p5held:noborder-panel-held5x5-v1" "train:p5train:noborder-panel-train5x5-v1" "hard:p4hard:noborder-panel-hard4x6-v1"; do
  key=${pb%%:*} rest=${pb#*:}
  run=$(C:/Python312/python.exe -c "import json,sys; c=json.load(open(sys.argv[1],encoding='utf-8')); print(([p for p in c['panels'] if p['key']==sys.argv[2]][0]['runs'].get(sys.argv[3]) or [''])[-1])" "$SITE/site_config.json" "$key" "$ROUND" | tr -d '\r')
  last=$(g storage cat "$RUNS/$run/phases.tsv" 2>/dev/null | tail -n 1 | cut -f3 | tr -d '\r')
  [[ "$last" == *finish*notebook_rc_0* ]] || { say "$run ended unfinished (${last:-no phases}): relaunching"; LOST="$LOST $rest"; }
done
[ -n "$LOST" ] && PANELS="${LOST# }" bash "$OPS/launch_panels.sh" $ROUND b
read -r NTR NHR < <(C:/Python312/python.exe - "$SITE/site_config.json" "$ROUND" <<'PY' | tr -d '\r'
import json, sys
cfg = json.load(open(sys.argv[1], encoding="utf-8"))
runs = {p["key"]: (p["runs"].get(sys.argv[2]) or [""])[-1] for p in cfg["panels"]}
print(runs.get("train", ""), runs.get("hard", ""))
PY
)
C:/Python312/python.exe "$OPS/loop_check.py" $NTR $NHR | sed "s/^/$(date -u +%H:%M) loop check: /"
say "$ROUND done"
