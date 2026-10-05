#!/bin/bash
# Upload the tuned MTP drafter for Daniel's stack as a PRIVATE Kaggle dataset (Son 2-Oct-2026: "Kaggle upload go!").
# Run as root on a GCP VM with the Kaggle API token at /root/.kaggle/access_token (copied there by gcloud scp, never
# pasted); the token is removed at the end. Dataset: sonphamorg/flashnext-mtp-drafter-tuned = his albucino drafter dir
# with the 29 dense mtp.* tensors retrained (mtp-dense.safetensors sha256 47b2d372...), everything else byte-identical.
# In a notebook it mounts at /kaggle/input/datasets/sonphamorg/flashnext-mtp-drafter-tuned (DRAFT_MODEL_DIR).
set -uo pipefail
trap 'rm -f /root/.kaggle/access_token; echo token removed' EXIT
D=/opt/arc3/kaggle-up/flashnext-mtp-drafter-tuned
mkdir -p $D
[ -f $D/mtp-dense.safetensors ] || gcloud storage cp -q "gs://cellens-ai-artifacts/arc3-duck/daniel-draft/results/daniel-draftcap-a-1002/drafter-tuned/*" $D/ || { echo download_failed; exit 1; }
echo "files: $(ls $D | wc -l), $(du -sh $D | cut -f1)"
sha256sum $D/mtp-dense.safetensors
cat > $D/dataset-metadata.json <<'EOF'
{
  "title": "Flash-Next MTP drafter tuned (Daniel stack)",
  "id": "sonphamorg/flashnext-mtp-drafter-tuned",
  "subtitle": "albucino drafter, dense layers retrained on ARC play",
  "licenses": [{"name": "other"}]
}
EOF
# The golden image's python3 has no venv module and the image's venv has no pip: uv installs the CLI (throwaway container).
docker run --rm -v /root/.kaggle:/root/.kaggle:ro -v $D:$D arc3-sglang:built bash -lc   "uv pip install -q --python /opt/sglvenv/bin/python kaggle && /opt/sglvenv/bin/kaggle --version && /opt/sglvenv/bin/kaggle datasets create -p $D" 2>&1 | tail -8
echo "create rc=${PIPESTATUS[0]}"
