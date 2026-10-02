#!/bin/bash
# G0 data VM (plan: docs/plans/2026-10-01-rl-on-burst-games.md §9). CPU only, Debian 12.
# Metadata: rl-code (gs:// dir with the rl/*.py files, frontier.json, the two gcp/*.py helpers),
#           rl-campaign, rl-runs (comma list), rl-root (gs:// folder holding <run>/working/), rl-harness.
# Output: gs://cellens-ai-artifacts/arc3-rl/<campaign>/g0/<run>/ (moments, records, summary) + DONE marker.
# Powers off at the end; delete the VM by hand.
set -uo pipefail
exec > >(tee -a /var/log/rl-g0.log) 2>&1
md() { curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
CODE=$(md rl-code); CAMPAIGN=$(md rl-campaign); RUNS=$(md rl-runs); ROOT=$(md rl-root); HARNESS=$(md rl-harness)
OUT=gs://cellens-ai-artifacts/arc3-rl/$CAMPAIGN/g0
echo "start $(date -u +%FT%TZ) code=$CODE campaign=$CAMPAIGN runs=$RUNS"
mkdir -p /opt/rl/hf /opt/rl/out && cd /opt/rl
gcloud storage cp "$CODE/*" /opt/rl/ || { echo "code copy failed"; exit 1; }
apt-get update -y -q && apt-get install -y -q python3-venv python3-pip curl >/dev/null
python3 -m venv venv && . venv/bin/activate
pip install -q --no-cache-dir --no-deps torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -q --no-cache-dir filelock sympy networkx jinja2 fsspec typing_extensions numpy pillow     "transformers==5.18.0" "peft==0.21.2" accelerate safetensors huggingface_hub
python -c "import transformers, torch, torchvision, peft; print('transformers', transformers.__version__, 'torch', torch.__version__, 'peft', peft.__version__)"
for f in chat_template.jinja config.json generation_config.json preprocessor_config.json tokenizer_config.json \
         video_preprocessor_config.json tokenizer.json vocab.json merges.txt; do
  curl -s -L -m 300 -o hf/$f https://huggingface.co/Qwen/Qwen3.8-Flash-Next/resolve/main/$f
done
ls -la hf
python test_rl_core.py 2>&1 | tail -3
python test_trainer_tiny.py --hf /opt/rl/hf > /opt/rl/out/tiny.log 2>&1; echo "tiny test exit $?"
gcloud storage cp /opt/rl/out/tiny.log "$OUT/tiny.log"
IFS=',' read -ra R <<< "${RUNS//+/,}"
for run in "${R[@]}"; do
  ( python g0_data.py --run "$run" --root "$ROOT" --frontier frontier.json --hf /opt/rl/hf --campaign "$CAMPAIGN" \
      --harness "$HARNESS" --out "/opt/rl/out/$run" --write-firestore > "/opt/rl/out/$run.log" 2>&1
    gcloud storage cp -r "/opt/rl/out/$run.log" "/opt/rl/out/$run/summary.json" "/opt/rl/out/$run/moments.jsonl" "$OUT/$run/"
    gcloud storage cp -r "/opt/rl/out/$run/records" "$OUT/$run/" ) &
done
wait
gcloud storage cp /var/log/rl-g0.log "$OUT/vm.log"
echo "done $(date -u +%FT%TZ)" | gcloud storage cp - "$OUT/DONE"
poweroff
