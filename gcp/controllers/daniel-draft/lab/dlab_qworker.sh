#!/bin/bash
# daniel-draft drafter-autoresearch QUEUE worker (4-Oct-2026): one persistent trainer per lab VM (the 69 GB capture is
# loaded into RAM once), running trial specs as they appear. Setup as dlab_worker.sh (his drafter + target mixer ->
# checkpoint dir, the stored capture, the tuned draft). Then:
#   specs:   gs://.../daniel-draft/queues/<vm name>/<trial>.json  (train_draft.py args as JSON keys, run in name order by
#            train_draft.py --queue --queue-rebuild: every trial from a fresh drafter, its own architecture options and
#            msteps; {"bench": [...]} = bench_draft_cost.py). String values "@<job>" (that job's draft_ft.pt) and
#            "gs://..." are fetched to the VM first; "$TUNED" = the shipped tuned draft. A file STOP there ends the worker
#            once every queued trial ran.
#   results: gs://.../daniel-draft/results/<run>/jobs/<trial>.log.jsonl and <trial>.draft_ft.pt (not for *-at3 evals),
#            the trainer's stdout as q-<vm>.log, phases-<vm>.txt.
# Locked eval (worker CLI, every trial): 7 draft steps, --split game (seed 0), 12,000 held-out rows, T 0.6 / top-k 20 /
# top-p 0.95, rejection sampling, fp8 draft KV. Idle guards: no spec ever for 20 min, or nothing queued for 45 min ->
# power off. Metadata: dlab-run (the capture run id).
set -uo pipefail
exec > >(tee -a /var/log/dlab.log) 2>&1
B=gs://cellens-ai-artifacts/arc3-duck
DD=$B/daniel-draft
KI=$B/daniel-base/kaggle-input
md() { curl -sf -H Metadata-Flavor:Google "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
RUN=$(md dlab-run); VM=$(curl -sf -H Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/name)
R=$DD/results/$RUN/jobs
QG=$DD/queues/$VM
L=/opt/arc3/dlab; M=$L/mtp
Q=$M/queue; QO=$M/q
mkdir -p $M $L/drafter $L/target $L/ckpt $M/cap $L/fetch $L/qin $Q $QO
log() { echo "$(date -u +%FT%TZ) $*" | tee -a $L/phases.txt; gcloud storage cp -q $L/phases.txt $R/phases-$VM.txt >/dev/null 2>&1 || true; }
systemctl enable --now docker
echo never > /sys/kernel/mm/transparent_hugepage/enabled || true
log "boot run=$RUN vm=$VM (queue worker)"
gcloud storage cp -q "$DD/code/*" $M/ || { log code_failed; shutdown -h now; exit 1; }
gcloud storage cp -q "$KI/models/dfranzen/albucino-qwen3-8-flash-next-drafter/transformers/default/1/*" $L/drafter/ || { log drafter_failed; shutdown -h now; exit 1; }
for f in model-00017-of-00017.safetensors model_extra_tensors.safetensors model.safetensors.index.json; do
  gcloud storage cp -q "$KI/models/dfranzen/intel-qwen3.8-flash-next-w4a16-autoround/transformers/default/1/$f" $L/target/ || { log "target_failed $f"; shutdown -h now; exit 1; }
done
gcloud storage cp -q $KI/datasets/dfranzen/pennyroyal-v253/hot_tokens_64k.pt $L/hot_tokens_64k.pt || { log hot_failed; shutdown -h now; exit 1; }
gcloud storage cp -q $DD/results/$RUN/draft_ft.pt $L/draft_ft.pt || { log tuned_failed; shutdown -h now; exit 1; }
docker run --rm --gpus all --ipc=host -v /opt/arc3:/opt/arc3 arc3-sglang:built bash -lc "source /opt/sglvenv/bin/activate && cd $M && python build_daniel_ckpt.py --drafter $L/drafter --target $L/target --out $L/ckpt" > $L/build.log 2>&1 || { log build_failed; shutdown -h now; exit 1; }
gcloud storage cp -q "$DD/captures/$RUN/*.mtpc" $M/cap/ || { log capture_failed; shutdown -h now; exit 1; }
log "ready: ckpt + capture $(ls $M/cap | wc -l) files $(du -sh $M/cap | cut -f1)"
COMMON="--cap $M/cap --ckpt $L/ckpt --mask $L/ckpt/mask.pt --hot $L/hot_tokens_64k.pt"
FIXED="--msteps 7 --step-weights 1,1,1,1,1,1,1 --split game --eval-every 1000000 --eval-rows 12000 --eval-temp 0.6 --eval-top-k 20 --eval-top-p 0.95 --eval-rs --fp8-kv"
start_trainer() {
  docker rm -f dlabq >/dev/null 2>&1
  docker run -d --name dlabq --gpus all --ipc=host -v /opt/arc3:/opt/arc3 arc3-sglang:built bash -lc \
    "source /opt/sglvenv/bin/activate && cd $M && python train_draft.py $COMMON --out $QO --queue $Q --queue-rebuild $FIXED >> $M/q.log 2>&1" >/dev/null
}
running() { [ -n "$(docker ps -q -f name=dlabq)" ]; }
push() {  # trial logs (running ones every pass), checkpoints once a trial is DONE
  for d in $QO/*/; do
    [ -d "$d" ] || continue
    n=$(basename "$d")
    [ -e "$d/.pushed" ] && continue
    [ -f "$d/log.jsonl" ] && gcloud storage cp -q "$d/log.jsonl" $R/$n.log.jsonl >/dev/null 2>&1
    if [ -f "$d/DONE" ]; then
      case "$n" in *-at3|bench*) ;; *) [ -f "$d/draft_ft.pt" ] && gcloud storage cp -q "$d/draft_ft.pt" $R/$n.draft_ft.pt >/dev/null 2>&1;; esac
      touch "$d/.pushed"; log "trial $n $(cat $d/DONE)"
    fi
  done
  [ -f $M/q.log ] && gcloud storage cp -q $M/q.log $R/q-$VM.log >/dev/null 2>&1
}
start_trainer; log "trainer started"
SEEN=0; IDLE=0; NOSPEC=0; RESTARTS=0
while true; do
  # 1. new specs: GCS -> staging -> (fetch referenced files, rewrite paths) -> local queue
  gcloud storage cp -q "$QG/*" $L/qin/ >/dev/null 2>&1
  for f in $L/qin/*.json; do
    [ -e "$f" ] || continue
    n=$(basename "$f")
    [ -e "$Q/$n" ] && continue
    tr -d '\r' < "$f" > $L/spec.tmp
    sed -i "s#\\\$TUNED#$L/draft_ft.pt#g" $L/spec.tmp
    for w in $(grep -o '"@[^"]*"\|"gs://[^"]*"' $L/spec.tmp | tr -d '"'); do
      case "$w" in @*) src=$R/${w#@}.draft_ft.pt ;; *) src=$w ;; esac
      lf=$L/fetch/$(echo "$src" | sed 's#^gs://##; s#/#_#g')
      [ -s "$lf" ] || gcloud storage cp -q "$src" "$lf" >/dev/null 2>&1 || log "fetch_failed $src"
      sed -i "s#\"$w\"#\"$lf\"#g" $L/spec.tmp
    done
    mv $L/spec.tmp "$Q/$n"; SEEN=1; log "queued ${n%.json}"
  done
  [ -e $L/qin/STOP ] && [ ! -e $Q/STOP ] && { touch $Q/STOP; log "STOP queued"; }
  push
  # 2. the trainer: restart it if it died before STOP (a trial without DONE reruns); stop when it ended on STOP
  if ! running; then
    if [ -e $Q/STOP ]; then push; log "trainer ended on STOP: shutdown"; shutdown -h now; exit 0; fi
    RESTARTS=$((RESTARTS + 1))
    [ $RESTARTS -gt 3 ] && { push; log "trainer died $RESTARTS times: shutdown"; shutdown -h now; exit 1; }
    log "trainer not running: restart $RESTARTS"; start_trainer
  fi
  # 3. idle guards
  pending=0
  for s in $Q/*.json; do [ -e "$s" ] || continue; b=$(basename "$s" .json); [ -e "$QO/$b/DONE" ] || pending=$((pending + 1)); done
  if [ $SEEN = 0 ]; then NOSPEC=$((NOSPEC + 1)); [ $NOSPEC -ge 40 ] && { log "no spec in $QG after 20 min: shutdown"; shutdown -h now; exit 0; }; fi
  if [ $pending = 0 ]; then IDLE=$((IDLE + 1)); [ $IDLE -ge 90 ] && { push; log "nothing queued for 45 min: shutdown"; shutdown -h now; exit 0; }; else IDLE=0; fi
  sleep 30
done
