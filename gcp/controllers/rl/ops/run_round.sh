#!/bin/bash
# One more RL round (Son 3-Oct: "do 2 more rounds just to see what is going on"), the round-1 recipe unchanged:
#   0. wait until the previous round's train and hard panel runs have finished (their plays are this round's data);
#   1. queue three trainer jobs: records from those plays (g0_data.py: efficient wins + frontier wins; the held-out
#      panel is never trained), training on at most 32 of them from the previous round's adapter (checkpoint every
#      4 records), merge into Daniel's checkpoint;
#   2. start the trainer VM, restart it whenever Spot stops it, wait for the merge, stop the VM;
#   3. stage the LoRA input copy, launch the three panels through quota limits (launch_panels.sh: retries every
#      10 min across all US zones, lists them on the RL page and in Trace review, watches them), and relaunch any
#      panel that ends unfinished (Spot), once.
#   SHA=<code snapshot> bash ops/run_round.sh <round number>        e.g. 2 (needs round 1's runs on the RL page)
# Every gcloud poll runs under `timeout 120`: an expired login makes gcloud hang.
set -uo pipefail
export CLOUDSDK_PYTHON='C:\python312\python.exe'
OPS=$(cd "$(dirname "$0")" && pwd)
SITE=$(cd "$OPS/../site" && pwd)
VM=arc3-rl-train4-20261002 ZONE=us-south1-b
B=gs://cellens-ai-artifacts/arc3-rl/trainer/train4-1002
RUNS=gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs
WORK=/d/codex-work/rl-20261001
SHA=${SHA:?set SHA to a code snapshot (ops/push_code.sh)}
N=${1:?round number, e.g. 2}
ROUND=r$N PREV=r$((N - 1))
J=$((30 + 3 * (N - 1)))                                  # round 1: jobs 030-032, round 2: 033-035, round 3: 036-038
T=${JOBTAG:-}            # a rerun needs new job ids (the trainer runs each id once): JOBTAG=b gives 033b-r2-records ...
JR=$(printf '%03d%s-%s-records' $J "$T" $ROUND) JT=$(printf '%03d%s-%s-train' $((J + 1)) "$T" $ROUND)
JM=$(printf '%03d%s-%s-merge' $((J + 2)) "$T" $ROUND)
# the records folder on the VM goes to Python as a bare name: Git Bash rewrites a /opt/... argument to Windows Python
# into C:/Program Files/Git/opt/... (3-Oct: that broke round 2's first try)
RECN=$(printf '%03d%s' $((J + 1)) "$T")
say() { echo "$(date -u +%H:%M) $*"; }
g() { timeout 120 gcloud "$@"; }

# ---------------------------------------------------------------- 0. the previous round's plays
# the RL page still names the previous round's training job, which may have been a rerun (034b-r2-train)
read -r TR HR PT < <(C:/Python312/python.exe - "$SITE/site_config.json" "$PREV" <<'PY' | tr -d '\r'
import json, sys
cfg = json.load(open(sys.argv[1], encoding="utf-8"))
runs = {p["key"]: (p["runs"].get(sys.argv[2]) or [""])[-1] for p in cfg["panels"]}
tj = cfg.get("train_job") or ""
print(runs.get("train", ""), runs.get("hard", ""), tj if tj.endswith(f"-{sys.argv[2]}-train") else "")
PY
)
PREV_TRAIN=${PREV_TRAIN:-${PT:-$(printf '%03d-%s-train' $((J - 2)) $PREV)}}
[ -n "$TR" ] && [ -n "$HR" ] || { say "no $PREV train/hard runs on the RL page"; exit 1; }
say "$ROUND: records from $TR and $HR (adapter from $PREV_TRAIN); jobs $JR $JT $JM"
for r in $TR $HR; do
  until g storage cat "$RUNS/$r/phases.tsv" 2>/dev/null | tail -n 1 | grep -q "finish"; do sleep 120; done
  say "$r: $(g storage cat "$RUNS/$r/phases.tsv" | tail -n 1 | cut -f3)"
done

# ---------------------------------------------------------------- 1. the jobs
C:/Python312/python.exe - "$WORK" "$SHA" "$TR" "$HR" "$JR" "$JT" "$JM" "$PREV_TRAIN" "$RECN" "$ROUND" "$PREV" <<'PY' || { echo "job files not written"; exit 1; }
import json, sys
work, sha, tr, hr, jr, jt, jm, prev_train, recn, rnd, prev = sys.argv[1:]
rec = f"/opt/m/work/records/{recn}"
records = (f"set -e; cd /opt/rl && gcloud storage cp 'gs://cellens-ai-artifacts/arc3-rl/code/{sha}/*' /opt/rl/ && "
           f"rm -rf {rec} /opt/m/work/g0{rnd} && mkdir -p {rec} /opt/m/work/g0{rnd} && "
           f"for r in {tr} {hr}; do /opt/rl/venv/bin/python g0_data.py --run $r "
           "--root gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs --frontier frontier.json --hf /opt/m/bf16 "
           f"--campaign rl-1003-{rnd} --harness daniel-nb-v1 --policy {prev} --out /opt/m/work/g0{rnd}/$r && "
           f"for f in /opt/m/work/g0{rnd}/$r/records/*.jsonl.gz; do cp $f {rec}/$r-$(basename $f); done; done && "
           f"ls {rec} && gcloud storage cp -r /opt/m/work/g0{rnd} gs://cellens-ai-artifacts/arc3-rl/rl-1003-{rnd}/")
train = (f"set -e; cd /opt/rl && ls {rec}/*.jsonl.gz > /dev/null && test -f /opt/m/work/out/{prev_train}/ADAPTER.json && "
         f"mkdir -p /opt/m/work/out/{jt} && ARC3_OFFLOAD_MIN_ELEMS=1239040000 /opt/rl/venv/bin/python lora_train.py train "
         "--model /opt/m/bf16 --hf /opt/m/bf16 --gpus 4 --gpu-gib 86 --nvfp4 /opt/m/daniel "
         f"--records '{rec}/*.jsonl.gz' --out /opt/m/work/out/{jt} "
         f"--init-adapter /opt/m/work/out/{prev_train} --epochs 1 --accum 4 --lr 1e-4 --warmup 2 --rank 32 --alpha 64 "
         "--max-tokens 121000 --limit 32 --ckpt-every 1")
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
C:/Python312/python.exe - "$SITE/site_config.json" "$N" "$JT" "$JM" <<'PY'
import json, sys, time
path, n, jt, jm = sys.argv[1:]
cfg = json.load(open(path, encoding="utf-8"))
cfg.update(round=f"Round {n}", train_job=jt, merge_job=jm, records_total=32,
           train_started=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
if not any(m["key"] == f"r{n}" for m in cfg["models"]):
    cfg["models"].append({"key": f"r{n}", "label": f"After round {n}", "short": f"R{n}",
                          "note": f"round {int(n) - 1}'s LoRA, trained on more on the wins of round {int(n) - 1}'s own test plays"})
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
      else   # 3-Oct: QUOTA_EXCEEDED (other sessions' G4s in us-south1) was logged as "started"
        say "trainer start refused ($(echo "$out" | grep -oiE 'QUOTA_EXCEEDED|STOCKOUT|ZONE_RESOURCE_POOL_EXHAUSTED|not enough resources|timed out' | head -n 1)); retrying"
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

# ---------------------------------------------------------------- 3. the test panels
bash "$OPS/make_eval_mirror.sh" $ROUND "$B/out/$JM/merged" || { say "LoRA input copy failed"; exit 1; }
say "LoRA input copy staged for $ROUND"
bash "$OPS/launch_panels.sh" $ROUND a
# a panel that ended unfinished (Spot took its VM) is relaunched once, as letter b
LOST=""
for pb in "held:p5held:noborder-panel-held5x5-v1" "train:p5train:noborder-panel-train5x5-v1" "hard:p4hard:noborder-panel-hard4x6-v1"; do
  key=${pb%%:*} rest=${pb#*:}
  run=$(C:/Python312/python.exe -c "import json,sys; c=json.load(open(sys.argv[1],encoding='utf-8')); print(([p for p in c['panels'] if p['key']==sys.argv[2]][0]['runs'].get(sys.argv[3]) or [''])[-1])" "$SITE/site_config.json" "$key" "$ROUND" | tr -d '\r')
  last=$(g storage cat "$RUNS/$run/phases.tsv" 2>/dev/null | tail -n 1 | cut -f3 | tr -d '\r')
  [[ "$last" == *finish*notebook_rc_0* ]] || { say "$run ended unfinished (${last:-no phases}): relaunching"; LOST="$LOST $rest"; }
done
[ -n "$LOST" ] && PANELS="${LOST# }" bash "$OPS/launch_panels.sh" $ROUND b
say "$ROUND done"
