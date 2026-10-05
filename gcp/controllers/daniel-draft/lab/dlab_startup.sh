#!/bin/bash
# daniel-draft lab (2-Oct-2026): train an MTP draft for Daniel Franzen's serving stack on his OWN target's capture
# (Son: retrain the recipe on his AutoRound target, reuse nothing trained on ours). Startup script of a G4 Spot lab VM
# (golden image: docker arc3-sglang:built). Metadata: dlab-run (the capture run id), dlab-steps (default 3500).
#   capture  gs://.../daniel-base/runs/<run>/working/{serve.log,mtp-capture/}  (copied to daniel-draft/captures/<run>/)
#   code     gs://.../daniel-draft/code/  (build_daniel_ckpt.py, package_daniel_draft.py + lobotomy/mtp trainer files)
#   results  gs://.../daniel-draft/results/<run>/  (phases.txt, build.json, verify.json, train.log.jsonl, draft_ft.pt,
#            drafter-tuned/ = his drafter dir with the trained dense tensors)
# Steps: his drafter + target mixer -> checkpoint dir (INT4 experts dequantized, checked against his BF16 copies);
# wait for the capture's stop line, pull it; verify our PyTorch copy reproduces his served draft proposals; train the
# settled recipe (plain KL, lr 2e-5, 512 rows, experts frozen, whole games held out); package.
set -uo pipefail
exec > >(tee -a /var/log/dlab.log) 2>&1
B=gs://cellens-ai-artifacts/arc3-duck
DD=$B/daniel-draft
KI=$B/daniel-base/kaggle-input
md() { curl -sf -H Metadata-Flavor:Google "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
RUN=$(md dlab-run); STEPS=$(md dlab-steps || echo 3500)
R=$DD/results/$RUN
CAP=$B/daniel-base/runs/$RUN/working
L=/opt/arc3/dlab; M=$L/mtp
mkdir -p $M $L/drafter $L/target $L/ckpt
log() { echo "$(date -u +%FT%TZ) $*" | tee -a $L/phases.txt; gcloud storage cp -q $L/phases.txt $R/phases.txt >/dev/null 2>&1 || true; }
DK() { docker run --rm --gpus all --ipc=host -v /opt/arc3:/opt/arc3 arc3-sglang:built bash -lc "source /opt/sglvenv/bin/activate && cd $M && $1"; }
systemctl enable --now docker
echo never > /sys/kernel/mm/transparent_hugepage/enabled || true
log "boot run=$RUN steps=$STEPS"
[ -n "$RUN" ] || { log no_run; exit 1; }
gcloud storage cp -q "$DD/code/*" $M/ || { log code_failed; exit 1; }
gcloud storage cp -q "$KI/models/dfranzen/albucino-qwen3-8-flash-next-drafter/transformers/default/1/*" $L/drafter/ \
  || { log drafter_failed; exit 1; }
for f in model-00017-of-00017.safetensors model_extra_tensors.safetensors model.safetensors.index.json; do
  gcloud storage cp -q "$KI/models/dfranzen/intel-qwen3.8-flash-next-w4a16-autoround/transformers/default/1/$f" $L/target/ \
    || { log "target_failed $f"; exit 1; }
done
gcloud storage cp -q $KI/datasets/dfranzen/pennyroyal-v253/hot_tokens_64k.pt $L/hot_tokens_64k.pt || { log hot_failed; exit 1; }
DK "python build_daniel_ckpt.py --drafter $L/drafter --target $L/target --out $L/ckpt" > $L/build.log 2>&1
rc=$?
gcloud storage cp -q $L/build.log $R/build.log >/dev/null 2>&1
[ -f $L/ckpt/build.json ] && gcloud storage cp -q $L/ckpt/build.json $R/build.json >/dev/null 2>&1
[ $rc = 0 ] || { log "build_failed rc=$rc"; exit 1; }
log "ckpt_ready $(du -shL $L/ckpt | cut -f1)"

# The capture: wait for its stop line, then one full runner sync (every 300 s) so every finished file is in GCS.
# grep reads the whole log (no -q): under pipefail, -q exits at a mid-log match, gcloud dies of SIGPIPE and the loop
# never ends (3-Oct kv4cap: the stop line was line 3,560 of 4,799; the lab sat 30 min).
until gcloud storage cat $CAP/serve.log 2>/dev/null | grep -E "ARC3_MTP_CAPTURE (stopped|disabled)" >/dev/null; do sleep 60; done
gcloud storage cat $CAP/serve.log 2>/dev/null | grep -E "ARC3_MTP_CAPTURE" > $L/capture_lines.txt
log "capture_end: $(tail -1 $L/capture_lines.txt | cut -c1-240)"
sleep 420
# A durable copy first: the runner mirrors /kaggle/working with delete, so a notebook cleanup would remove it there.
gcloud storage cp -q -r "$CAP/mtp-capture/*.mtpc" $DD/captures/$RUN/ >/dev/null 2>&1 || log capture_copy_failed
mkdir -p $M/cap
gcloud storage cp -q "$DD/captures/$RUN/*.mtpc" $M/cap/ || gcloud storage cp -q "$CAP/mtp-capture/*.mtpc" $M/cap/ \
  || { log capture_download_failed; exit 1; }
log "capture_ready $(ls $M/cap | wc -l) files $(du -sh $M/cap | cut -f1)"

DK "python verify_draft.py --cap $M/cap --ckpt $L/ckpt --mask $L/ckpt/mask.pt --hot $L/hot_tokens_64k.pt --requests 24 --out $M/verify.json" \
  > $M/verify.log 2>&1
log "verify rc=$?"
gcloud storage cp -q $M/verify.log $M/verify.json $R/ >/dev/null 2>&1

( while sleep 120; do gcloud storage cp -q $M/train/log.jsonl $R/train.log.jsonl >/dev/null 2>&1; done ) &
SYNC=$!
DK "python train_draft.py --cap $M/cap --ckpt $L/ckpt --mask $L/ckpt/mask.pt --hot $L/hot_tokens_64k.pt --out $M/train \
--steps $STEPS --lr 2e-5 --rows 512 --split game --loss kl --eval-every 500 --eval-rows 12000 \
--eval-temp 0.7 --eval-top-k 20 --eval-top-p 0.95" > $M/train.log 2>&1
rc=$?
kill $SYNC 2>/dev/null
gcloud storage cp -q $M/train/log.jsonl $R/train.log.jsonl >/dev/null 2>&1
gcloud storage cp -q $M/train.log $R/train.log >/dev/null 2>&1
[ -f $M/train/draft_ft.pt ] || { log "train_failed rc=$rc"; exit 1; }
gcloud storage cp -q $M/train/draft_ft.pt $R/draft_ft.pt
log "train_done rc=$rc"

DK "python package_daniel_draft.py --drafter $L/drafter --ft $M/train/draft_ft.pt --out $L/drafter-tuned" > $L/package.log 2>&1 \
  || { log package_failed; gcloud storage cp -q $L/package.log $R/; exit 1; }
gcloud storage cp -q -r $L/drafter-tuned $R/ && gcloud storage cp -q $L/package.log $R/
log "packaged -> $R/drafter-tuned/"
