#!/bin/bash
# RL restart after R0 (Son 4-Oct: "restart training from R1"; "if a trace is better than average then it is positive",
# and worse is negative). Round n<N> of the second recipe; the first recipe's R1-R3 are archived (copy-paste looping,
# docs in D:\codex-work\rl-20261001\sc25audit\FINDINGS.md). What changed:
#   records: g0_data.py reads EVERY pass of the previous round's train and hard panel runs (it read only pass 0), and
#            weights each played level by its advantage = reward - the game's mean over the passes (negative allowed);
#            select_records.py keeps --budget records, half positive, half negative, largest |advantage| first;
#   train:   continues the previous round's adapter AND optimizer (R1 of the first recipe restarted Adam: the looping
#            began there; R0 saved no optimizer, so n1 starts a fresh one), clipped update (--clip) with a KL penalty
#            to the round's start (--kl), lr 5e-5;
#   then merge, stage, the three panels (a Spot-lost panel is relaunched once), and the looping check
#   (loop_check.py: share of the thinking that repeats lines of the same reply; base 0.0%, first-recipe R2 7.2%).
#   SHA=<code snapshot> bash ops/run_round_v2.sh <N>
#   N=0 (Son 4-Oct: "redo Round 0 as well"): data = every base-model panel run (the train panel ran twice: 10
#   attempts per game), a fresh adapter from the original model; N>=1: the previous round's panels, adapter, optimizer.
# Env: BUDGET (24), LR (5e-5), CLIP (0.2), KL (0.05), DP (1; 2 = two copies, needs the half-size chunks),
#      TRAINER_VM / TRAINER_ZONE, JOBTAG (a rerun needs new job ids), DRYRUN=1 (print the jobs only).
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
ROUND=n$N
PREV=$([ "$N" -eq 0 ] && echo base || echo "n$((N - 1))")
BUDGET=${BUDGET:-24} LR=${LR:-5e-5} CLIP=${CLIP:-0.2} KL=${KL:-0.05} DP=${DP:-1}
J=$((103 + 3 * N))                                       # n0: jobs 103-105, n1: 106-108, ...
T=${JOBTAG:-}
JR=$(printf '%03d%s-%s-records' $J "$T" $ROUND) JT=$(printf '%03d%s-%s-train' $((J + 1)) "$T" $ROUND)
JM=$(printf '%03d%s-%s-merge' $((J + 2)) "$T" $ROUND)
RECN=$(printf '%03d%s' $((J + 1)) "$T")                  # bare name: Git Bash rewrites /opt/... args to Windows Python
say() { echo "$(date -u +%H:%M) $*"; }
g() { timeout 120 gcloud "$@"; }

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
[ -n "$TR" ] && [ -n "$HR" ] || { say "no $PREV train/hard runs on the RL page"; exit 1; }
say "$ROUND: records from every pass of $TR $HR (one group per game); adapter ${PREV_TRAIN:-fresh}${PREV_OPTIM:+ + optimizer}; jobs $JR $JT $JM"
for r in $TR $HR; do
  until g storage cat "$RUNS/$r/phases.tsv" 2>/dev/null | tail -n 1 | grep -q "finish"; do sleep 120; done
  say "$r: $(g storage cat "$RUNS/$r/phases.tsv" | tail -n 1 | cut -f3)"
done

# ---------------------------------------------------------------- 1. the jobs
C:/Python312/python.exe - "$WORK" "$SHA" "$TR" "$HR" "$JR" "$JT" "$JM" "$PREV_TRAIN" "$PREV_OPTIM" "$RECN" "$ROUND" \
    "$PREV" "$BUDGET" "$LR" "$CLIP" "$KL" "$DP" <<'PY' || { echo "job files not written"; exit 1; }
import json, sys
(work, sha, tr, hr, jr, jt, jm, prev_train, prev_optim, recn, rnd, prev, budget, lr, clip, kl, dp) = sys.argv[1:]
rec, g0 = f"/opt/m/work/records/{recn}", f"/opt/m/work/g0{rnd}"
run_args = " ".join(f"--run {r}" for r in (tr.split() + hr.split()))
records = (f"set -e; cd /opt/rl && gcloud storage cp 'gs://cellens-ai-artifacts/arc3-rl/code/{sha}/*' /opt/rl/ && "
           f"rm -rf {rec} {g0} && mkdir -p {rec} {g0} && "
           f"/opt/rl/venv/bin/python g0_data.py {run_args} "
           "--root gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs --frontier frontier.json --hf /opt/m/bf16 "
           f"--campaign rl-1004-{rnd} --harness daniel-nb-v1 --policy {prev} --passes all --credit advantage "
           f"--out {g0}/all && "
           f"/opt/rl/venv/bin/python select_records.py --in '{g0}/all/records/*.jsonl.gz' --out {rec} --budget {budget} && "
           f"ls {rec} && gcloud storage rsync -r -x '.*/cache/.*' {g0} gs://cellens-ai-artifacts/arc3-rl/rl-1004-{rnd}/g0{rnd}")
env = "ARC3_OFFLOAD_MIN_ELEMS=1239040000" + (" ARC3_MOE_TOKEN_CHUNK=8192 ARC3_NVFP4_CHUNK=16" if dp != "1" else "")
train = (f"set -e; cd /opt/rl && ls {rec}/*.jsonl.gz > /dev/null && "
         + (f"test -f /opt/m/work/out/{prev_train}/ADAPTER.json && " if prev_train else "")
         + (f"test -f {prev_optim} && " if prev_optim else "")
         + f"mkdir -p /opt/m/work/out/{jt} && {env} /opt/rl/venv/bin/python lora_train.py train "
         f"--model /opt/m/bf16 --hf /opt/m/bf16 --gpus 4 --dp {dp} --gpu-gib 86 --nvfp4 /opt/m/daniel "
         f"--records '{rec}/*.jsonl.gz' --out /opt/m/work/out/{jt} "
         + (f"--init-adapter /opt/m/work/out/{prev_train} " if prev_train else "")
         + (f"--init-optim {prev_optim} " if prev_optim else "")
         + f"--clip {clip} --kl {kl} --epochs 1 --accum 4 --lr {lr} --warmup 2 --rank 32 --alpha 64 "
         "--max-tokens 121000 --ckpt-every 1")
merge = (f"set -e; test -f /opt/m/work/out/{jt}/ADAPTER.json && cd /opt/rl && mkdir -p /opt/m/work/out/{jm} && "
         f"/opt/rl/venv/bin/python merge_lora.py --adapter /opt/m/work/out/{jt} --checkpoint /opt/m/daniel "
         f"--out /opt/m/work/out/{jm}/merged --only-changed && ls -la /opt/m/work/out/{jm}/merged | head -50")
for name, cmd in ((jr, records), (jt, train), (jm, merge)):
    assert "/opt/m/work/" in cmd and "Program Files" not in cmd and "Files/Git" not in cmd, f"{name}: a Windows path got into the command"
    open(f"{work}/job-{name}.json", "w", newline="\n").write(json.dumps({"cmd": "shell", "args": {"command": cmd}}))
print("job files written")
PY
if [ -n "${DRYRUN:-}" ]; then for j in $JR $JT $JM; do echo "== $j"; cat "$WORK/job-$j.json"; echo; done; exit 0; fi
for j in $JR $JT $JM; do
  gcloud storage cp "$WORK/job-$j.json" "$B/jobs/$j.json" > /dev/null 2>&1 || { say "could not queue $j"; exit 1; }
done
say "queued $JR, $JT, $JM (code $SHA)"
C:/Python312/python.exe - "$SITE/site_config.json" "$N" "$ROUND" "$JT" "$JM" "$BUDGET" <<'PY'
import json, sys, time
path, n, rnd, jt, jm, budget = sys.argv[1:]
cfg = json.load(open(path, encoding="utf-8"))
cfg.update(round=f"Round {n} (restart)", train_job=jt, merge_job=jm, records_total=int(budget),
           train_started=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
if not any(m["key"] == rnd for m in cfg["models"]):
    cfg["models"].append({"key": rnd, "label": f"Restart round {n}", "short": f"N{n}",
                          "note": "every attempt, scored against the game's average attempt (better = pulled up, worse = "
                                  "pushed down), clipped update with a pull back to the round's start"})
cfg["next_model"] = None
open(path, "w", encoding="utf-8", newline="\n").write(json.dumps(cfg, indent=1, ensure_ascii=False) + "\n")
print("RL page follows", jt, jm)
PY

# ---------------------------------------------------------------- 2. the trainer, until the merge is done and uploaded
while true; do
  for j in $JR $JT; do      # the first failure is the one worth reading: later jobs fail on its missing outputs
    code=$(g storage cat "$B/out/$j/EXIT" 2>/dev/null | tr -d '\r\n ')
    if [ -n "$code" ] && [ "$code" != 0 ]; then
      say "$j failed (exit $code); last log lines:"; g storage cat "$B/out/$j/job.log" | tail -n 25
      g compute instances stop $VM --zone $ZONE > /dev/null 2>&1 && say "trainer VM stopped"; exit 1
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
  g compute instances stop $VM --zone $ZONE > /dev/null 2>&1; exit 1
fi
say "$ROUND trained on $(g storage cat "$B/out/$JT/ADAPTER.json" | tr -d '\r\n' | grep -o '"records": [0-9]*') and merged"
g compute instances stop $VM --zone $ZONE > /dev/null 2>&1 && say "trainer VM stopped (no jobs left)"

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
