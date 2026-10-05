#!/bin/bash
# spectree lab worker (3-Oct-2026, daniel-draft spectree): offline draft-tree / draft-depth simulation on Daniel's
# stack. Startup script of ONE G4 Spot VM (arc3-spectree-*; golden image: docker arc3-sglang:built).
# Setup: the tuned drafter (results/daniel-draftcap-a-1002/drafter-tuned) + target mixer -> checkpoint dir
# (build_daniel_ckpt.py), the ARC hot map, the stored 4-bit-KV capture (daniel-draft/captures/<run>/).
# Then it polls gs://.../daniel-draft/spectree/plan.txt and runs each new line once, in order:
#   "<name> [<script.py>] <args>" (default script spectree_sim.py)  -> results gs://.../daniel-draft/spectree/results/<name>/ (+ <name>.log)
#   a line "STOP" ends the worker (the VM shuts down; its owner deletes it by name).
# Metadata: st-run (the capture run id).
set -uo pipefail
exec > >(tee -a /var/log/spectree.log) 2>&1
B=gs://cellens-ai-artifacts/arc3-duck
DD=$B/daniel-draft
ST=$DD/spectree
KI=$B/daniel-base/kaggle-input
md() { curl -sf -H Metadata-Flavor:Google "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
RUN=$(md st-run)
L=/opt/arc3/st; M=$L/mtp
mkdir -p $M $L/drafter $L/target $L/ckpt $M/cap $L/done
log() { echo "$(date -u +%FT%TZ) $*" | tee -a $L/phases.txt; gcloud storage cp -q $L/phases.txt $ST/results/phases.txt >/dev/null 2>&1 || true; }
DK() { docker run --rm --gpus all --ipc=host -v /opt/arc3:/opt/arc3 arc3-sglang:built bash -lc "source /opt/sglvenv/bin/activate && cd $M && $1"; }
systemctl enable --now docker
echo never > /sys/kernel/mm/transparent_hugepage/enabled || true
log "boot run=$RUN"
gcloud storage cp -q "$ST/code/*" $M/ || { log code_failed; exit 1; }
gcloud storage cp -q "$DD/results/daniel-draftcap-a-1002/drafter-tuned/*" $L/drafter/ || { log drafter_failed; exit 1; }
for f in model-00017-of-00017.safetensors model_extra_tensors.safetensors model.safetensors.index.json; do
  gcloud storage cp -q "$KI/models/dfranzen/intel-qwen3.8-flash-next-w4a16-autoround/transformers/default/1/$f" $L/target/ || { log "target_failed $f"; exit 1; }
done
DK "python build_daniel_ckpt.py --drafter $L/drafter --target $L/target --out $L/ckpt" > $L/build.log 2>&1 || { log build_failed; gcloud storage cp -q $L/build.log $ST/results/build.log; exit 1; }
gcloud storage cp -q $L/build.log $ST/results/build.log >/dev/null 2>&1
log "ckpt_ready"
gcloud storage cp -q "$DD/captures/$RUN/*.mtpc" $M/cap/ || { log capture_failed; exit 1; }
log "ready: capture $(ls $M/cap | wc -l) files $(du -sh $M/cap | cut -f1)"
gcloud storage cp -q $DD/results/daniel-bench-kv4cap-1003/draft_ft.pt $L/kv4_draft_ft.pt >/dev/null 2>&1 || log "no kv4 draft_ft.pt"
COMMON="--cap $M/cap --ckpt $L/ckpt --mask $L/ckpt/mask.pt --hot $M/arc-hot-64k.json"
while true; do
  gcloud storage cp -q $ST/plan.txt $L/plan.txt >/dev/null 2>&1 || { sleep 30; continue; }
  tr -d '\r' < $L/plan.txt > $L/plan.lf
  next=""
  while read -r name args; do
    [ -z "$name" ] && continue
    case "$name" in \#*) continue;; esac
    if [ "$name" = STOP ]; then [ -z "$next" ] && { log "stop"; shutdown -h now; exit 0; }; break; fi
    [ -e $L/done/$name ] && continue
    next="$name"; nargs="$args"; break
  done < $L/plan.lf
  if [ -z "$next" ]; then sleep 30; continue; fi
  touch $L/done/$next
  gcloud storage cp -q "$ST/code/*" $M/ >/dev/null 2>&1   # latest code for every job
  log "job $next start: $nargs"
  ( while sleep 60; do gcloud storage cp -q $M/$next.log $ST/results/$next.log >/dev/null 2>&1; done ) &
  SYNC=$!
  script=spectree_sim.py
  case "$nargs" in *.py\ *) script=${nargs%% *}; nargs=${nargs#* };; esac
  DK "python $script $COMMON --out $M/$next $nargs" > $M/$next.log 2>&1
  rc=$?
  kill $SYNC 2>/dev/null
  gcloud storage cp -q $M/$next.log $ST/results/$next.log >/dev/null 2>&1
  gcloud storage cp -q -r $M/$next $ST/results/ >/dev/null 2>&1
  log "job $next rc=$rc"
done
