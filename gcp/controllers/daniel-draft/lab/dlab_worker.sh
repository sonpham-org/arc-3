#!/bin/bash
# daniel-draft lab worker (2-Oct-2026): offline drafter experiments on Daniel's stack, one queue on one G4 Spot VM.
# Setup: his drafter + target mixer -> checkpoint dir (build_daniel_ckpt.py), the stored capture
# (daniel-draft/captures/<run>/), the tuned draft (results/<run>/draft_ft.pt). Then it polls a plan file and runs each
# new line once (in order):
#   gs://.../daniel-draft/plans/<vm name>.txt   lines: "<name> <train_draft.py args>"   ($TUNED = the tuned draft_ft.pt)
#   a line "STOP" ends the worker once everything before it ran.
# Every job gets --cap/--ckpt/--mask/--hot/--out. Results: gs://.../daniel-draft/results/<run>/jobs/<name>.{log.jsonl,log}.
# Metadata: dlab-run (the capture run id).
set -uo pipefail
exec > >(tee -a /var/log/dlab.log) 2>&1
B=gs://cellens-ai-artifacts/arc3-duck
DD=$B/daniel-draft
KI=$B/daniel-base/kaggle-input
md() { curl -sf -H Metadata-Flavor:Google "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
RUN=$(md dlab-run); VM=$(curl -sf -H Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/name)
R=$DD/results/$RUN/jobs
PLAN=$DD/plans/$VM.txt
L=/opt/arc3/dlab; M=$L/mtp
mkdir -p $M $L/drafter $L/target $L/ckpt $M/cap $L/done
log() { echo "$(date -u +%FT%TZ) $*" | tee -a $L/phases.txt; gcloud storage cp -q $L/phases.txt $R/phases-$VM.txt >/dev/null 2>&1 || true; }
DK() { docker run --rm --gpus all --ipc=host -v /opt/arc3:/opt/arc3 arc3-sglang:built bash -lc "source /opt/sglvenv/bin/activate && cd $M && $1"; }
systemctl enable --now docker
echo never > /sys/kernel/mm/transparent_hugepage/enabled || true
log "boot run=$RUN vm=$VM"
gcloud storage cp -q "$DD/code/*" $M/ || { log code_failed; exit 1; }
gcloud storage cp -q "$KI/models/dfranzen/albucino-qwen3-8-flash-next-drafter/transformers/default/1/*" $L/drafter/ || { log drafter_failed; exit 1; }
for f in model-00017-of-00017.safetensors model_extra_tensors.safetensors model.safetensors.index.json; do
  gcloud storage cp -q "$KI/models/dfranzen/intel-qwen3.8-flash-next-w4a16-autoround/transformers/default/1/$f" $L/target/ || { log "target_failed $f"; exit 1; }
done
gcloud storage cp -q $KI/datasets/dfranzen/pennyroyal-v253/hot_tokens_64k.pt $L/hot_tokens_64k.pt || { log hot_failed; exit 1; }
gcloud storage cp -q $DD/results/$RUN/draft_ft.pt $L/draft_ft.pt || { log tuned_failed; exit 1; }
DK "python build_daniel_ckpt.py --drafter $L/drafter --target $L/target --out $L/ckpt" > $L/build.log 2>&1 || { log build_failed; exit 1; }
gcloud storage cp -q "$DD/captures/$RUN/*.mtpc" $M/cap/ || { log capture_failed; exit 1; }
log "ready: ckpt + capture $(ls $M/cap | wc -l) files $(du -sh $M/cap | cut -f1)"
COMMON="--cap $M/cap --ckpt $L/ckpt --mask $L/ckpt/mask.pt --hot $L/hot_tokens_64k.pt"
while true; do
  # no plan file for 20 min -> nothing will ever run here: power off (4-Oct: x3 idled 2 h after its plan upload failed)
  gcloud storage cp -q $PLAN $L/plan.txt >/dev/null 2>&1 || { NOPLAN=$((${NOPLAN:-0} + 1)); [ $NOPLAN -ge 20 ] && { log "no plan file $PLAN after 20 min: shutdown"; shutdown -h now; exit 0; }; sleep 60; continue; }
  NOPLAN=0
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
  gcloud storage cp -q "$DD/code/*" $M/ >/dev/null 2>&1   # latest trainer code for every job
  a=${nargs//\$TUNED/$L/draft_ft.pt}
  log "job $next start: $a"
  ( while sleep 120; do gcloud storage cp -q $M/$next/log.jsonl $R/$next.log.jsonl >/dev/null 2>&1; [ $M/$next/train_state.pt -nt $L/state_up_$next ] 2>/dev/null && gcloud storage cp -q $M/$next/train_state.pt $R/$next.train_state.pt >/dev/null 2>&1 && touch $L/state_up_$next; done ) &
  SYNC=$!
  DK "python train_draft.py $COMMON --out $M/$next $a" > $M/$next.log 2>&1
  rc=$?
  kill $SYNC 2>/dev/null
  gcloud storage cp -q $M/$next/log.jsonl $R/$next.log.jsonl >/dev/null 2>&1
  gcloud storage cp -q $M/$next.log $R/$next.log >/dev/null 2>&1
  case "$a" in *"--steps 0"*) ;; *) [ -f $M/$next/draft_ft.pt ] && gcloud storage cp -q $M/$next/draft_ft.pt $R/$next.draft_ft.pt >/dev/null 2>&1; [ -f $M/$next/train_state.pt ] && gcloud storage cp -q $M/$next/train_state.pt $R/$next.train_state.pt >/dev/null 2>&1;; esac
  log "job $next rc=$rc"
done
