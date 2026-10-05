#!/bin/bash
# Block-drafter scoping worker (DFlash phase 2, 4-Oct-2026): one G4 Spot VM, a queue of train_block.py jobs.
# Setup is daniel-draft/lab/dlab_worker.sh's: his drafter + target mixer -> checkpoint (build_daniel_ckpt.py), the stored
# capture daniel-draft/captures/<run>/ and its tuned chain drafter results/<run>/draft_ft.pt. Code: the lab trainer files
# (daniel-draft/code/*) + ours (daniel-draft/blockdraft/code/*). Plan: gs://.../daniel-draft/blockdraft/plans/<vm>.txt,
# lines "<name> <train_block.py args>", "STOP" ends the worker. Results: .../blockdraft/results/<vm>/<name>.*
set -uo pipefail
exec > >(tee -a /var/log/bdraft.log) 2>&1
B=gs://cellens-ai-artifacts/arc3-duck
DD=$B/daniel-draft
BD=$DD/blockdraft
KI=$B/daniel-base/kaggle-input
md() { curl -sf -H Metadata-Flavor:Google "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
RUN=$(md dlab-run); VM=$(curl -sf -H Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/name)
R=$BD/results/$VM
PLAN=$BD/plans/$VM.txt
L=/opt/arc3/bdraft; M=$L/mtp
mkdir -p $M $L/drafter $L/target $L/ckpt $M/cap $L/done
log() { echo "$(date -u +%FT%TZ) $*" | tee -a $L/phases.txt; gcloud storage cp -q $L/phases.txt $R/phases.txt >/dev/null 2>&1 || true; }
DK() { docker run --rm --gpus all --ipc=host -v /opt/arc3:/opt/arc3 arc3-sglang:built bash -lc "source /opt/sglvenv/bin/activate && cd $M && $1"; }
pull_code() { gcloud storage cp -q "$DD/code/*" $M/ && gcloud storage cp -q "$BD/code/*" $M/; }
systemctl enable --now docker
echo never > /sys/kernel/mm/transparent_hugepage/enabled || true
log "boot run=$RUN vm=$VM"
pull_code || { log code_failed; exit 1; }
gcloud storage cp -q "$KI/models/dfranzen/albucino-qwen3-8-flash-next-drafter/transformers/default/1/*" $L/drafter/ || { log drafter_failed; exit 1; }
for f in model-00017-of-00017.safetensors model_extra_tensors.safetensors model.safetensors.index.json; do
  gcloud storage cp -q "$KI/models/dfranzen/intel-qwen3.8-flash-next-w4a16-autoround/transformers/default/1/$f" $L/target/ || { log "target_failed $f"; exit 1; }
done
gcloud storage cp -q $KI/datasets/dfranzen/pennyroyal-v253/hot_tokens_64k.pt $L/hot_tokens_64k.pt || { log hot_failed; exit 1; }
gcloud storage cp -q $DD/results/$RUN/draft_ft.pt $L/draft_ft.pt || { log tuned_failed; exit 1; }
DK "python build_daniel_ckpt.py --drafter $L/drafter --target $L/target --out $L/ckpt" > $L/build.log 2>&1 || { log build_failed; gcloud storage cp -q $L/build.log $R/build.log; exit 1; }
gcloud storage cp -q "$DD/captures/$RUN/*.mtpc" $M/cap/ || { log capture_failed; exit 1; }
log "ready: ckpt + capture $(ls $M/cap | wc -l) files $(du -sh $M/cap | cut -f1)"
COMMON="--cap $M/cap --ckpt $L/ckpt --mask $L/ckpt/mask.pt --hot $L/hot_tokens_64k.pt --tuned $L/draft_ft.pt"
# metadata bd-extra-caps: more capture runs (comma-separated) -> extra --cap dirs (jobs should use --disk: RAM fits one)
for X in $(md bd-extra-caps | tr ',' ' '); do
  mkdir -p $M/cap_$X
  gcloud storage cp -q "$DD/captures/$X/*.mtpc" $M/cap_$X/ || { log "extra_capture_failed $X"; exit 1; }
  COMMON="$COMMON --cap $M/cap_$X"
  log "extra capture $X: $(ls $M/cap_$X | wc -l) files $(du -sh $M/cap_$X | cut -f1)"
done
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
  touch $L/done/$next
  pull_code >/dev/null 2>&1   # latest code for every job
  log "job $next start: $nargs"
  ( while sleep 120; do gcloud storage cp -q $M/$next/log.jsonl $R/$next.log.jsonl >/dev/null 2>&1; done ) &
  SYNC=$!
  DK "python train_block.py $COMMON --out $M/$next $nargs" > $M/$next.log 2>&1
  rc=$?
  kill $SYNC 2>/dev/null
  gcloud storage cp -q $M/$next/log.jsonl $R/$next.log.jsonl >/dev/null 2>&1
  gcloud storage cp -q $M/$next.log $R/$next.log >/dev/null 2>&1
  [ -f $M/$next/block.pt ] && gcloud storage cp -q $M/$next/block.pt $R/$next.block.pt >/dev/null 2>&1
  log "job $next rc=$rc"
done
