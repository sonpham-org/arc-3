"""Add the mtp3 serving variant to derive_arm.py (run once)."""
from pathlib import Path

p = Path(__file__).with_name("derive_arm.py")
s = p.read_text(encoding="utf-8")
assert '"mtp3"' not in s, "already added"
BSL = "\\\\"  # a literal backslash-backslash in the generated source == one backslash in the startup text

s = s.replace('''    "xxhigh": dict(env=("ARC3_SERVING_REASONING_EFFORT", "xxhigh"),''', '''    "mtp3": dict(env=("ARC3_SERVING_SPECULATIVE", "mtp3-kvfixed"),
                 note="MTP speculative decoding (3 draft tokens) with the KV pool set explicitly (--kv-cache-memory-bytes) instead of the profiler's "
                      "reservation, and --max-num-batched-tokens 2048, after the public single-Blackwell recipe (Son 25-Sep: 'claims >300 tok/s using MTP'). "
                      "Every earlier MTP attempt (13/14/23-Sep) failed the 7x103k capacity gate because the profiler left 8.6 GiB (4.1-4.5x) instead of 13.76 GiB (9.55x). "
                      "Ladder: k=3/13.5GiB -> k=3/13.0GiB -> k=2/13.0GiB, each must pass the capacity gate; FAILED otherwise (never a stock-decoding score)."),
    "xxhigh": dict(env=("ARC3_SERVING_REASONING_EFFORT", "xxhigh"),''')

block = '''elif ARGS.variant == "mtp3":
    NL = chr(10)
    BSL = chr(92)
    s = swap("    --max-model-len 102985 --max-num-seqs 7 --max-num-batched-tokens 6144 " + BSL + NL,
             "    --max-model-len 102985 --max-num-seqs 7 --max-num-batched-tokens $MTP_BATCH " + BSL + NL, s)
    s = swap("    --cudagraph-capture-sizes 1 2 4 8 12 14 15 16 17 18 19 20 21 22 24 32 40" + NL,
             "    --cudagraph-capture-sizes 1 2 4 8 12 14 15 16 17 18 19 20 21 22 24 32 40 --kv-cache-memory-bytes $MTP_KV --speculative-config $MTP_SPEC" + NL, s)
    gate_cmd = NL.join([
        'run_capacity_gate() {',
        "  gcloud storage cp 'gs://cellens-ai-artifacts/arc3-duck/code/astra-execution/context-matrix-r1/0dbd08c9aeec9c5681c232fec2f42fd8e5aa6d9bd3b2a97bdb4bfa0ccef3c186/context-matrix-capacity-r1.tgz' /tmp/astra-native-context-capacity.tgz",
        "  echo '0dbd08c9aeec9c5681c232fec2f42fd8e5aa6d9bd3b2a97bdb4bfa0ccef3c186  /tmp/astra-native-context-capacity.tgz' | sha256sum -c -",
        '  tar xzf /tmp/astra-native-context-capacity.tgz -C /opt/arc3',
        '  timeout --kill-after=10 1230 /opt/arc3/pysrv/bin/python -B /opt/arc3/context-matrix-capacity-r1/capacity_gate.py ' + BSL,
        '    --base-url http://127.0.0.1:1234/v1 --model "$SERVED_MODEL_NAME" ' + BSL,
        '    --context 102985 --concurrency 7 --append-rounds 2 ' + BSL,
        '    --total-seconds 1200 --request-timeout 300 --run-key c102985-w7-matrix-r1 ' + BSL,
        '    --output /opt/arc3/native-context-capacity-gate.json --ack-idle-pregame-server ' + BSL,
        '    2>&1 | tee /opt/arc3/native-context-capacity-gate.log',
        '  python3 -c "import json,sys; r=json.load(open(\\'/opt/arc3/native-context-capacity-gate.json\\')); g=r.get(\\'gates\\',{}); sys.exit(0 if r.get(\\'status\\')==\\'passed\\' and g.get(\\'zero_preemptions_verified\\') and g.get(\\'native_capacity_and_reuse_pass\\') else 1)"',
        '}',
    ]) + NL
    old_serve = NL.join([
        'KV_DTYPE_USED=fp8_e4m3',
        'start_server "$KV_DTYPE_USED"',
        'if ! wait_server; then',
        '  cp /opt/arc3/vllm.log /opt/arc3/vllm-start-attempt1.log',
        '  sleep 10',
        '  container_gpu_ready',
        '  start_server "$KV_DTYPE_USED"',
        'fi',
        'if ! wait_server; then',
        '  echo "Experimental vLLM failed for requested KV" | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"',
        '  sync_all',
        '  exit 1',
        'fi',
    ]) + NL
    new_serve = gate_cmd + NL.join([
        'KV_DTYPE_USED=fp8_e4m3',
        '# MTP ladder (arm=lacr_mtp3): each rung must serve AND pass the native 7x102985 capacity gate with zero preemptions.',
        '# No plain fallback: a score can never silently come from stock decoding.',
        'MTP_RUNG=""',
        'for rung in "3 14495514624 2048 k3-kv13.5g-b2048" "3 13958643712 2048 k3-kv13.0g-b2048" "2 13958643712 2048 k2-kv13.0g-b2048"; do',
        '  read -r MTP_K MTP_KV MTP_BATCH tag <<< "$rung"',
        """  MTP_SPEC='{"method":"mtp","num_speculative_tokens":'"$MTP_K"'}'""",
        '  container_gpu_ready || { sleep 10; container_gpu_ready; }',
        '  start_server "$KV_DTYPE_USED"',
        '  if wait_server && run_capacity_gate; then MTP_RUNG="$tag"; break; fi',
        '  cp /opt/arc3/vllm.log "/opt/arc3/vllm-start-$tag.log"',
        '  timeout 15 gcloud storage cp "/opt/arc3/vllm-start-$tag.log" "$BUCKET/$RUN_ID/vllm-start-$tag.log" || true',
        '  [ -f /opt/arc3/native-context-capacity-gate.json ] && timeout 15 gcloud storage cp /opt/arc3/native-context-capacity-gate.json "$BUCKET/$RUN_ID/capacity-gate-$tag.json" || true',
        '  echo "MTP rung $tag failed; trying next"; sleep 10',
        'done',
        'if [ -z "$MTP_RUNG" ]; then',
        '  echo "vLLM MTP ladder failed (no rung served and passed the 7x103k capacity gate)" | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"',
        '  sync_all',
        '  exit 1',
        'fi',
        'touch /opt/arc3/mtp-gate-passed',
        'echo "mtp-$MTP_RUNG" | tee /opt/arc3/server-mode.txt | gcloud storage cp - "$BUCKET/$RUN_ID/server-mode"',
    ]) + NL
    s = swap(old_serve, new_serve, s)
    # the original gate invocation is skipped when the ladder already passed it on the serving rung
    s = swap("timeout --kill-after=10 1230 /opt/arc3/pysrv/bin/python -B /opt/arc3/context-matrix-capacity-r1/capacity_gate.py " + BSL + NL
             + '  --base-url http://127.0.0.1:1234/v1 --model "$SERVED_MODEL_NAME" ' + BSL + NL,
             "[ -f /opt/arc3/mtp-gate-passed ] || timeout --kill-after=10 1230 /opt/arc3/pysrv/bin/python -B /opt/arc3/context-matrix-capacity-r1/capacity_gate.py " + BSL + NL
             + '  --base-url http://127.0.0.1:1234/v1 --model "$SERVED_MODEL_NAME" ' + BSL + NL, s)
elif ARGS.variant == "xxhigh":
    # Serve a copy of the model's own chat template'''
s = s.replace('''elif ARGS.variant == "xxhigh":
    # Serve a copy of the model's own chat template''', block, 1)
compile(s, "derive_arm.py", "exec")
p.write_text(s, encoding="utf-8", newline="\n")
print("mtp3 variant added")
