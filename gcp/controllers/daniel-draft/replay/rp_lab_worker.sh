#!/bin/bash
# Replay-data lab worker (4-Oct-2026, daniel-draft/replay): one G4 Spot VM, a queue of drafter jobs on replay captures.
# Setup as daniel-draft/lab/dlab_worker.sh: his drafter + target mixer -> checkpoint (build_daniel_ckpt.py), his hot map,
# the tuned drafter (results/daniel-draftcap-a-1002/draft_ft.pt). Captures: metadata rp-caps = "name=gs://prefix+..."
# -> /opt/arc3/rp/caps/<name>/ (only *.mtpc). Code: gs://.../daniel-draft/replay/code/* (pulled before every job).
# Plan: gs://.../daniel-draft/replay/plans/<vm>.txt, lines "<name> <train_draft.py args>" ($CAPS = the caps dir,
# $TUNED = the tuned draft_ft.pt; every job gets --ckpt/--mask/--hot/--out), or "<name> RAW <command>" (run in the
# container from the code dir); "STOP" powers off once everything before it ran.
# Results: gs://.../daniel-draft/replay/results/<vm>/<name>.{log,log.jsonl,draft_ft.pt}.
set -uo pipefail
exec > >(tee -a /var/log/rplab.log) 2>&1
B=gs://cellens-ai-artifacts/arc3-duck
DD=$B/daniel-draft
RP=$DD/replay
KI=$B/daniel-base/kaggle-input
md() { curl -sf -H Metadata-Flavor:Google "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
VM=$(curl -sf -H Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/name)
R=$RP/results/$VM
PLAN=$RP/plans/$VM.txt
L=/opt/arc3/rp; M=$L/mtp; CAPS=$L/caps
mkdir -p $M $L/drafter $L/target $L/ckpt $CAPS $L/done
log() { echo "$(date -u +%FT%TZ) $*" | tee -a $L/phases.txt; gcloud storage cp -q $L/phases.txt $R/phases.txt >/dev/null 2>&1 || true; }
DK() { docker run --rm --gpus all --ipc=host -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True -v /opt/arc3:/opt/arc3 arc3-sglang:built bash -lc "source /opt/sglvenv/bin/activate && cd $M && $1"; }
pull_code() { gcloud storage cp -q "$RP/code/*" $M/; }
systemctl enable --now docker
echo never > /sys/kernel/mm/transparent_hugepage/enabled || true
log "boot vm=$VM"
# multi-GPU (Son 5-Oct): metadata rp-gpus = N > 1 -> every training job runs data-parallel under torchrun
NGPU=$(md rp-gpus || echo 1); [ -z "$NGPU" ] && NGPU=1
PYRUN=python; [ "$NGPU" -gt 1 ] && PYRUN="python -m torch.distributed.run --standalone --nproc_per_node=$NGPU"
log "gpus=$NGPU run=$PYRUN"
pull_code || { log code_failed; exit 1; }
( # captures download beside the checkpoint build
  for kv in $(md rp-caps | tr '+' ' '); do
    n=${kv%%=*}; src=${kv#*=}
    case "$src" in */replay/captures/*)  # a replay capture is complete once its runner wrote _DONE
      until gcloud storage ls "$src/_DONE" >/dev/null 2>&1; do sleep 60; done;;
    esac
    mkdir -p $CAPS/$n
    gcloud storage cp -q "$src/*.mtpc" $CAPS/$n/ > $L/cap_$n.log 2>&1 && echo "$n $(ls $CAPS/$n | wc -l) files $(du -sh $CAPS/$n | cut -f1)" >> $L/caps_ready.txt \
      && touch $L/ready_$n || echo "$n FAILED" >> $L/caps_ready.txt
    log "cap $n: $(tail -1 $L/caps_ready.txt)"
  done
  touch $L/caps_done
) &
gcloud storage cp -q "$KI/models/dfranzen/albucino-qwen3-8-flash-next-drafter/transformers/default/1/*" $L/drafter/ || { log drafter_failed; exit 1; }
for f in model-00017-of-00017.safetensors model_extra_tensors.safetensors model.safetensors.index.json; do
  gcloud storage cp -q "$KI/models/dfranzen/intel-qwen3.8-flash-next-w4a16-autoround/transformers/default/1/$f" $L/target/ || { log "target_failed $f"; exit 1; }
done
gcloud storage cp -q $KI/datasets/dfranzen/pennyroyal-v253/hot_tokens_64k.pt $L/hot_tokens_64k.pt || { log hot_failed; exit 1; }
gcloud storage cp -q $DD/results/daniel-draftcap-a-1002/draft_ft.pt $L/draft_ft.pt || { log tuned_failed; exit 1; }
# optional starting checkpoint for continued training (metadata rp-init = gs://.../<job>.draft_ft.pt; plan args $INIT)
INIT_SRC=$(md rp-init || true)
if [ -n "$INIT_SRC" ]; then gcloud storage cp -q "$INIT_SRC" $L/init.pt || { log init_failed; exit 1; }; log "init $INIT_SRC"; fi
DK "python build_daniel_ckpt.py --drafter $L/drafter --target $L/target --out $L/ckpt" > $L/build.log 2>&1 || { log build_failed; gcloud storage cp -q $L/build.log $R/build.log; exit 1; }
log "ckpt ready"
# a job starts as soon as every capture its args name ($CAPS/<name>) is downloaded, not all of them
COMMON="--ckpt $L/ckpt --mask $L/ckpt/mask.pt --hot $L/hot_tokens_64k.pt"
while true; do
  gcloud storage cp -q $PLAN $L/plan.txt >/dev/null 2>&1 || { sleep 60; continue; }
  tr -d '\r' < $L/plan.txt > $L/plan.lf
  next=""
  while read -r name args; do
    [ -z "$name" ] && continue
    case "$name" in \#*) continue;; esac
    if [ "$name" = STOP ]; then [ -z "$next" ] && { log "stop"; shutdown -h now; exit 0; }; break; fi
    [ -e $L/done/$name ] && continue
    next="$name"; nargs="$args"; break
  done < $L/plan.lf
  if [ -z "$next" ]; then sleep 60; continue; fi
  for n in $(echo "$nargs" | grep -o '[$]CAPS/[A-Za-z0-9_]*' | cut -d/ -f2 | sort -u); do
    until [ -e $L/ready_$n ]; do [ -e $L/caps_done ] && { log "job $next: capture $n missing"; break; }; sleep 30; done
  done
  touch $L/done/$next
  pull_code >/dev/null 2>&1
  a=${nargs//\$TUNED/$L/draft_ft.pt}
  a=${a//\$CAPS/$CAPS}
  a=${a//\$CKPT/$L/ckpt}
  a=${a//\$INIT/$L/init.pt}
  a=${a//\$HOT/$L/hot_tokens_64k.pt}
  log "job $next start: $a"
  mkdir -p $M/$next
  ( while sleep 120; do gcloud storage cp -q $M/$next/log.jsonl $R/$next.log.jsonl >/dev/null 2>&1; [ $M/$next/train_state.pt -nt $L/state_up_$next ] 2>/dev/null && gcloud storage cp -q $M/$next/train_state.pt $R/$next.train_state.pt >/dev/null 2>&1 && touch $L/state_up_$next; gcloud storage cp -q $M/$next.log $R/$next.log >/dev/null 2>&1; done ) &
  SYNC=$!
  case "$a" in
    RAW\ *) DK "${a#RAW }" > $M/$next.log 2>&1 ;;
    *) DK "$PYRUN train_draft.py $COMMON --out $M/$next $a" > $M/$next.log 2>&1 ;;
  esac
  rc=$?
  kill $SYNC 2>/dev/null
  gcloud storage cp -q $M/$next/log.jsonl $R/$next.log.jsonl >/dev/null 2>&1
  gcloud storage cp -q $M/$next.log $R/$next.log >/dev/null 2>&1
  for f in $M/$next/*.json; do [ -f "$f" ] && gcloud storage cp -q "$f" $R/$next.$(basename "$f") >/dev/null 2>&1; done
  case "$a" in *"--steps 0"*|RAW\ *) ;; *) [ -f $M/$next/draft_ft.pt ] && gcloud storage cp -q $M/$next/draft_ft.pt $R/$next.draft_ft.pt >/dev/null 2>&1; [ -f $M/$next/train_state.pt ] && gcloud storage cp -q $M/$next/train_state.pt $R/$next.train_state.pt >/dev/null 2>&1;; esac
  log "job $next rc=$rc"
done
