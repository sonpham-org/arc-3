#!/bin/bash
# Hot-swap check, part three (4-Oct-2026): one RL round moves the model less than the server's own run-to-run noise
# (hs_check.sh: 0.11-0.13 mean |dlogprob| reading one server twice; base vs round 0 0.136), and this model has no
# weight read-back. So: swap in ZEROS for the 300 tensors (the output must break: far beyond the noise), then round 0
# again (back within the noise of the cold round-0 server). That proves the swap reaches the live forward pass and
# that a swap fully restores a model; the tensor-to-parameter mapping is the server's own load_weights.
set -uo pipefail
exec >> /var/log/box/hstest.log 2>&1
echo "--- check2 $(date -u +%FT%TZ)"
HS=/kaggle/taaf-kaggle-source-share/gtree_rollout/hotswap.py
PY=/tmp/sgl-intel/venv/bin/python
[ -f /kaggle-delta/zero/delta.safetensors ] || /opt/rl/venv/bin/python - <<'PY'
import torch
from pathlib import Path
from safetensors.torch import load_file, save_file
d = load_file("/kaggle-delta/105k-n0-merge/delta.safetensors")
Path("/kaggle-delta/zero").mkdir(parents=True, exist_ok=True)
save_file({k: torch.zeros_like(v) for k, v in d.items()}, "/kaggle-delta/zero/delta.safetensors")
print("zero delta", len(d))
PY
chmod -R a+rX /kaggle-delta
LP='import json, urllib.request
def post(path, body):
    r = urllib.request.Request("http://127.0.0.1:8001" + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(r, timeout=600).read()
text = ("You are playing a grid game. The board is 8 by 8. A blue block sits at row 3, column 5; a red block at row 6, "
        "column 2. Each move shifts every block one cell. Think about which move brings the blue block next to the red "
        "one without leaving the board, then answer with one of UP, DOWN, LEFT, RIGHT. ")
post("/flush_cache", {})
m = json.loads(post("/generate", {"text": text, "sampling_params": {"temperature": 0, "max_new_tokens": 24},
                                  "return_logprob": True, "logprob_start_len": 0}))
mi = m["meta_info"]
print(json.dumps({"in": [x[0] for x in mi["input_token_logprobs"] if x[0] is not None], "text": m["text"][:60]}))'
read() { docker exec "$1" python3 -c "$LP" 2>&1 | tail -n 1; }
cmp() {
  python3 - "$1" "$2" "$3" <<'PY'
import json, sys
label = sys.argv[1]
try:
    a, b = json.loads(sys.argv[2]), json.loads(sys.argv[3])
except ValueError:
    print(f"RESULT {label}: unreadable: {sys.argv[2][:200]} | {sys.argv[3][:200]}"); sys.exit()
n = min(len(a["in"]), len(b["in"]))
d = [abs(p - q) for p, q in zip(a["in"][:n], b["in"][:n])]
print(f"RESULT {label}: mean |dlogprob| {sum(d)/max(1,n):.4f}, max {max(d or [0]):.3f}; texts {a['text'][:40]!r} | {b['text'][:40]!r}")
PY
}
N1=$(read hsn0)
echo "apply zero: $(docker exec hsbase $PY $HS apply /kaggle/delta/zero/delta.safetensors http://127.0.0.1:8001 2>/dev/null | cut -c1-120)"
Z=$(read hsbase)
cmp "zeros swapped in vs round 0 cold (must be far beyond 0.13)" "$Z" "$N1"
echo "apply round 0: $(docker exec hsbase $PY $HS apply /kaggle/delta/105k-n0-merge/delta.safetensors http://127.0.0.1:8001 2>/dev/null | cut -c1-120)"
B=$(read hsbase)
cmp "round 0 swapped back vs round 0 cold (must be within ~0.13)" "$B" "$N1"
echo "RESULT check2 done"
