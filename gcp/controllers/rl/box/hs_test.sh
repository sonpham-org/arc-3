#!/bin/bash
# Hot-swap check on the RL box (4-Oct-2026): is base + round-0 delta (applied to a LIVE server) the same model as a
# server started cold on round 0's weights? Card 0: the hot-swap notebook on the BASE inputs; card 1: the same
# notebook on round 0's inputs. Both idle in serve_sessions (no ctl/next.json). Then, on the same 400-token text:
#   1. per-token logprobs from both (they must differ: base vs round 0)
#   2. hotswap.py apply <round-0 delta> on card 0 (timed), logprobs again: must match card 1
#   3. a second read: still matches (no drift after the first requests on the new weights)
# Log: /var/log/box/hstest.log; result lines start with "RESULT".
#   sudo bash hs_test.sh <notebook gs://> [card for base] [card for round 0]
set -uo pipefail
NB_OBJ=${1:?notebook}; CB=${2:-0}; CN=${3:-1}
BASE_IN=gs://cellens-ai-artifacts/arc3-duck/daniel-draft/kaggle-input
N0_IN=gs://cellens-ai-artifacts/arc3-duck/daniel-draft/kaggle-input-n0-rollout
DELTA=/kaggle/delta/105k-n0-merge/delta.safetensors
IMAGE=$(cat /var/lib/box/image)
exec >> /var/log/box/hstest.log 2>&1
say() { echo "$(date -u +%FT%TZ) $*"; }
fetch_in() {   # <gs prefix> -> /kaggle-in/<tag>
  local tag; tag=$(basename "$1")
  ( flock -w 3600 9
    [ -f "/kaggle-in/$tag/.ok" ] || { rm -rf "/kaggle-in/$tag"; mkdir -p "/kaggle-in/$tag"
      gcloud storage rsync -r "$1" "/kaggle-in/$tag" > /dev/null 2>&1 && touch "/kaggle-in/$tag/.ok"; }
  ) 9> /kaggle-in/.lock
  echo "/kaggle-in/$tag"
}
start() {   # <name> <card> <input dir>
  local R=/kaggle-root/$1
  docker rm -f "$1" > /dev/null 2>&1
  rm -rf "$R" && mkdir -p "$R/working" "$R/nb" "$R/rollout/ctl" "$R/rollout/sess" "$R/rollout/policy" "$R/rollout/jobs"
  gcloud storage cp "$NB_OBJ" "$R/nb/notebook.ipynb" > /dev/null 2>&1
  echo '{}' > "$R/rollout/policy/current.json"
  docker run -d --name "$1" --gpus "device=$2" --cpus 48 --memory 200g --network none --shm-size=64g --ulimit memlock=-1 \
    -v "$3:/kaggle/input:ro" -v "$R/working:/kaggle/working" -v "$R/nb:/kaggle/nb:ro" -v "$R/rollout:/kaggle/rollout:ro" \
    -v /kaggle-delta:/kaggle/delta:ro -w /kaggle/working --entrypoint bash "$IMAGE" -c \
    'jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=-1 --ExecutePreprocessor.kernel_name=python3 /kaggle/nb/notebook.ipynb --output-dir /kaggle/working --output __notebook__.ipynb' > /dev/null
  say "started $1 on card $2 with $3"
}
ready() { for i in $(seq 1 120); do grep -q "ready to roll" "/kaggle-root/$1/working/serve.log" 2>/dev/null && return 0; sleep 10; done; return 1; }
# per-token logprobs of a fixed text (prefill only), as JSON on one line
LP='import json, urllib.request
text = ("You are playing a grid game. The board is 8 by 8. A blue block sits at row 3, column 5; a red block at row 6, "
        "column 2. Each move shifts every block one cell. Think about which move brings the blue block next to the red "
        "one without leaving the board, then answer with one of UP, DOWN, LEFT, RIGHT. ") * 6
req = {"text": text, "sampling_params": {"temperature": 0, "max_new_tokens": 1}, "return_logprob": True, "logprob_start_len": 0}
r = urllib.request.Request("http://127.0.0.1:8001/generate", data=json.dumps(req).encode(), headers={"Content-Type": "application/json"})
m = json.loads(urllib.request.urlopen(r, timeout=600).read())["meta_info"]
print(json.dumps([x[0] for x in m["input_token_logprobs"] if x[0] is not None]))'
lp() { docker exec "$1" python3 -c "$LP" 2>/dev/null | tail -n 1; }
cmp() {   # <label> <json a> <json b>
  python3 - "$1" "$2" "$3" <<'PY'
import json, sys
label, a, b = sys.argv[1], json.loads(sys.argv[2] or "[]"), json.loads(sys.argv[3] or "[]")
n = min(len(a), len(b))
d = [abs(x - y) for x, y in zip(a[:n], b[:n])]
print(f"RESULT {label}: tokens {len(a)}/{len(b)}, mean |dlogprob| {sum(d)/max(1,n):.5f}, max {max(d or [0]):.4f}")
PY
}
gpu() { nvidia-smi --query-gpu=memory.used --format=csv,noheader -i "$1"; }

say "hot-swap test: base on card $CB, round 0 on card $CN, notebook $NB_OBJ"
INB=$(fetch_in "$BASE_IN"); INN=$(fetch_in "$N0_IN")
chmod -R a+r /kaggle-delta
start hsbase "$CB" "$INB"; start hsn0 "$CN" "$INN"
ready hsbase && ready hsn0 || { say "RESULT FAIL: a server never got ready"; exit 1; }
say "both ready; card memory: base $(gpu "$CB"), n0 $(gpu "$CN")"
grep -c -i "memory_saver\|memory saver" /kaggle-root/hsbase/working/serve.log | sed 's/^/memory-saver lines in serve.log: /'
HS=$(docker exec hsbase bash -c "find / -name hotswap.py -path \"*gtree_rollout*\" 2>/dev/null | head -1")
say "hotswap.py at $HS"
A=$(lp hsbase); B=$(lp hsn0)
cmp "base vs round0 (must differ)" "$A" "$B"
say "apply: $(docker exec hsbase /tmp/sgl-intel/venv/bin/python "$HS" apply "$DELTA" http://127.0.0.1:8001 2>&1 | tail -n 1)"
A2=$(lp hsbase)
cmp "base+delta vs round0 (must match)" "$A2" "$B"
cmp "base+delta vs base (must differ)" "$A2" "$A"
A3=$(lp hsbase)
cmp "second read after apply vs round0 (must match)" "$A3" "$B"
say "RESULT done"
