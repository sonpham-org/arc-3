#!/bin/bash
# Hot-swap check, part two (4-Oct-2026): hs_test.sh's reads went through the prompt cache, so two reads of one server
# differed as much as two models. Here every read starts with /flush_cache (a fresh prefill), and each server is read
# twice (its own noise floor). Containers from hs_test.sh: hsbase (base + round-0 delta applied), hsn0 (round 0 cold).
#   sudo bash hs_check.sh  -> RESULT lines in /var/log/box/hstest.log
set -uo pipefail
exec >> /var/log/box/hstest.log 2>&1
echo "--- check $(date -u +%FT%TZ)"
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
print(json.dumps({"in": [x[0] for x in mi["input_token_logprobs"] if x[0] is not None],
                  "out_ids": [x[1] for x in mi["output_token_logprobs"]], "text": m["text"][:80]}))'
read() { docker exec "$1" python3 -c "$LP" 2>&1 | tail -n 1; }
cmp() {
  python3 - "$1" "$2" "$3" <<'PY'
import json, sys
label = sys.argv[1]
try:
    a, b = json.loads(sys.argv[2]), json.loads(sys.argv[3])
except ValueError:
    print(f"RESULT {label}: unreadable: {sys.argv[2][:200]} | {sys.argv[3][:200]}"); sys.exit()
x, y = a["in"], b["in"]
n = min(len(x), len(y))
d = [abs(p - q) for p, q in zip(x[:n], y[:n])]
same = sum(1 for p, q in zip(a["out_ids"], b["out_ids"]) if p == q)
print(f"RESULT {label}: prompt tokens {n}, mean |dlogprob| {sum(d)/max(1,n):.5f}, max {max(d or [0]):.4f}; "
      f"greedy tokens equal {same}/{len(a['out_ids'])}")
PY
}
B1=$(read hsbase); B2=$(read hsbase); N1=$(read hsn0); N2=$(read hsn0)
cmp "floor: hsbase twice" "$B1" "$B2"
cmp "floor: hsn0 twice" "$N1" "$N2"
cmp "swapped (base + round-0 delta) vs round 0 cold" "$B1" "$N1"
# toggle: swap hsbase back to the base values of the same 300 tensors, then to round 0 again
HS=/kaggle/taaf-kaggle-source-share/gtree_rollout/hotswap.py
[ -f /kaggle-delta/base/delta.safetensors ] || /opt/rl/venv/bin/python /opt/rl/extract_delta.py --merged /opt/m/daniel     --names-from /opt/m/work/out/105k-n0-merge/merged/MERGE_REPORT.json --out /kaggle-delta/base/delta.safetensors
chmod -R a+rX /kaggle-delta
echo "apply base: $(docker exec hsbase /tmp/sgl-intel/venv/bin/python $HS apply /kaggle/delta/base/delta.safetensors http://127.0.0.1:8001 | cut -c1-200)"
B3=$(read hsbase)
cmp "swapped back to base vs round 0 cold (must differ beyond the floor)" "$B3" "$N1"
echo "apply round 0: $(docker exec hsbase /tmp/sgl-intel/venv/bin/python $HS apply /kaggle/delta/105k-n0-merge/delta.safetensors http://127.0.0.1:8001 | cut -c1-200)"
B4=$(read hsbase)
cmp "swapped to round 0 again vs round 0 cold (must match)" "$B4" "$N1"
echo "RESULT check done"
