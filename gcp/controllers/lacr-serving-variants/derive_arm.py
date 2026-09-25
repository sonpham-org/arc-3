"""Serving-only variants of the live LA-CR arm (la_clean_return_a): harness byte-identical, one vLLM flag changed.

  --variant effort_medium   --default-chat-template-kwargs gains "reasoning_effort": "medium" (Qwen3.8 template default is
                            xhigh; the harness only sends enable_thinking, and request kwargs win per key so nothing else moves).
                            Son 23-Sep: "LA-CR + medium then, try it." MiMo-Flash showed tokens-per-action is the lever on this
                            clock (same tok/s, 2x tokens/action -> -27%); Flash-Next spends ~694 tokens/action at xhigh.
  --variant batched16k      --max-num-batched-tokens 6144 -> 16384 (the nightly arms ran 16384 all day without incident;
                            prefill-bound long-context turns should gain). Son 23-Sep: "Sure".

Everything else -- golden runtime image, PLE/qsa/scheduler/retention overlays, bundle, selftests, probes, prompts,
every ARC3_* value, 7 lanes, 102,985 context, 2061 s/game, 132 minutes -- is the LA-CR arm verbatim. The variant is
recorded as an ARC3_SERVING_* entry in recipe.extra_environment (exported on the VM), so the config_id is distinct
and the receipt says what was served.
"""
import argparse, hashlib, json, re, sys, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(r"D:\codex-work\la-clean-return132-20260921\arms\la_clean_return_a")
PARENT_RUN = "g4run-la-clean-return-a132-w7-20260921-b4119c3bbb"
VARIANTS = {
    "effort_medium": dict(env=("ARC3_SERVING_REASONING_EFFORT", "medium"),
                          note="reasoning_effort=medium via vLLM --default-chat-template-kwargs (template default xhigh)"),
    "effort_high": dict(env=("ARC3_SERVING_REASONING_EFFORT", "high"),
                        note="served chat template whose xhigh sentence is replaced by a milder high sentence (the template has no high level). Son 25-Sep: 'LA-CR with High'"),
    "batched16k": dict(env=("ARC3_SERVING_MAX_NUM_BATCHED_TOKENS", "16384"),
                       note="--max-num-batched-tokens 16384 instead of 6144"),
    "spec": dict(env=("ARC3_SERVING_SPECULATIVE", "mtp-or-ngram"),
                 note="speculative decoding: ladder MTP (the NVFP4 checkpoint ships the 4B mtp.* head every run so far left off) -> qwen3_next_mtp -> n-gram drafting; FAILED if none serves. Son 23-Sep: 'Go ahead'"),
    "spec_ngram": dict(env=("ARC3_SERVING_SPECULATIVE", "ngram"),
                       note="speculative decoding by n-gram prompt lookup only (4 draft tokens). MTP (run ...-28d5b5cfe4) served but its drafter KV halved the pool (13.76 -> 8.6 GiB; 9.55x -> 4.5x at 103k), so 7 lanes preempted and the capacity gate failed; n-gram has no draft model and no extra KV"),
    "nopreserve": dict(env=("ARC3_SERVING_PRESERVE_THINKING", "0"),
                       note="--default-chat-template-kwargs preserve_thinking=false: prior turns' reasoning is no longer re-rendered into every prompt (less prefill, slower context growth, fewer 50% swaps; the model loses its own earlier chain of thought). Son 23-Sep: 'Go ahead'"),
    "mtp3": dict(env=("ARC3_SERVING_SPECULATIVE", "mtp3-kvfixed"),
                 note="MTP speculative decoding (3 draft tokens) with the KV pool set explicitly (--kv-cache-memory-bytes) instead of the profiler's "
                      "reservation, and --max-num-batched-tokens 2048, after the public single-Blackwell recipe (Son 25-Sep: 'claims >300 tok/s using MTP'). "
                      "Every earlier MTP attempt (13/14/23-Sep) failed the 7x103k capacity gate because the profiler left 8.6 GiB (4.1-4.5x) instead of 13.76 GiB (9.55x). "
                      "Ladder: k=3/13.5GiB -> k=3/13.0GiB -> k=2/13.0GiB, each must pass the capacity gate; FAILED otherwise (never a stock-decoding score)."),
    "xxhigh": dict(env=("ARC3_SERVING_REASONING_EFFORT", "xxhigh"),
                   note="served chat template with the xhigh instruction extended by an agentic reflect-before-acting sentence (Son 23-Sep: push it to be even more aggressively careful); harness untouched"),
}
HIGH_PREP = ['  cp /opt/arc3/flashnext-model/chat_template.jinja /opt/arc3/high-chat-template.jinja', "  python3 - <<'PYHIGH'", 'from pathlib import Path', "p = Path('/opt/arc3/high-chat-template.jinja'); t = p.read_text(encoding='utf-8')", "old = 'Reasoning effort is set to xhigh. Please think carefully through the task, validate key assumptions, consider plausible alternatives, and prioritize correctness, consistency, and clarity in the final answer.'", "new = 'Reasoning effort is set to high. Think through the task and check the key assumptions behind your next action, but keep the reasoning proportionate to the decision at hand and move to the answer once it is justified.'", 'assert t.count(old) == 1, t.count(old)', "p.write_text(t.replace(old, new), encoding='utf-8'); print('high chat template written')", 'PYHIGH']
XHIGH_SENTENCE = 'Reasoning effort is set to xhigh. Please think carefully through the task, validate key assumptions, consider plausible alternatives, and prioritize correctness, consistency, and clarity in the final answer.'
XXHIGH_SENTENCE = 'Reasoning effort is set to xhigh. Please think carefully through the task, validate key assumptions, consider plausible alternatives, and prioritize correctness, consistency, and clarity in the final answer. After every tool result, reflect carefully on what actually changed before deciding the next step: state the hypothesis you are testing, check it against the observation, and revise it when they disagree. Do not repeat an action whose last outcome you cannot explain; prefer one well-chosen, informative action over several guesses.'
ap = argparse.ArgumentParser()
ap.add_argument("--variant", required=True, choices=sorted(VARIANTS))
ap.add_argument("--arm-suffix", default="a")
ARGS = ap.parse_args()
V = VARIANTS[ARGS.variant]
ARM = HERE / "arms" / f"lacr_{ARGS.variant}_{ARGS.arm_suffix}"
ARM.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(SRC))
import contract  # noqa: E402

for name in ("candidate.tgz", "selftest.tgz", "release.json", "contract.py", "expected-runner.py", "runtime_probe.py",
             "prompt_probe.py", "time_guidance_probe.py", "EXPECTED_PROMPTS.json", "ADAPTER.json", "LOOP_ARM.json",
             "LOCAL_ACTUAL_PROMPTS.json", "LOCAL_PROMPT_ATTEST.json", "LOCAL_PROMPT_RUNTIME_RECEIPT.json"):
    (ARM / name).write_bytes((SRC / name).read_bytes())

# ---------------------------------------------------------------- CONFIG_FLAGS.json
cfg = json.loads((SRC / "CONFIG_FLAGS.json").read_text(encoding="utf-8-sig"))
assert cfg["recipe"]["extra_environment"]["ARC3_PROMPT_ABLATE_LOOP"] == "1"
assert cfg["recipe"]["model"]["id"] == "RadixArk/Qwen3.8-Flash-Next-NVFP4"
env_key, env_val = V["env"]
cfg["recipe"]["extra_environment"][env_key] = env_val
cfg["run_id"] = f"g4run-lacr-{ARGS.variant.replace('_', '-')}-{ARGS.arm_suffix}132-w7-20260923"
cfg["evidence"]["notes"] = [
    f"September23 serving-only variant of la_clean_return_a: {V['note']}. Harness, bundle, prompts, probes, every ARC3_* "
    f"gameplay value and the golden Flash-Next runtime image are byte-identical to the LA-CR arm (18.01 / 19.24 on two "
    f"rolls); the variant is recorded as {env_key}={env_val} and exported on the VM. Comparison target: LA-CR on the same clock.",
] + cfg["evidence"]["notes"]
cfg["config_id"] = contract.config_id(cfg["recipe"])
contract.validate(cfg, for_launch=True)
cfg_bytes = (json.dumps(cfg, indent=2, sort_keys=False) + "\n").encode()
cfg_sha = hashlib.sha256(cfg_bytes).hexdigest()
(ARM / "CONFIG_FLAGS.json").write_bytes(cfg_bytes)
old_cfg_sha = hashlib.sha256((SRC / "CONFIG_FLAGS.json").read_bytes()).hexdigest()
print("config_id", cfg["config_id"]); print("CONFIG_FLAGS sha", cfg_sha, "(was", old_cfg_sha + ")")

# ---------------------------------------------------------------- startup.sh
s = (SRC / "startup.sh").read_text(encoding="utf-8")


def swap(before, after, text, expected=1):
    assert text.count(before) == expected, (before[:90], text.count(before))
    return text.replace(before, after)


if ARGS.variant == "effort_medium":
    s = swap("""    --default-chat-template-kwargs '{"preserve_thinking": true}' \\""",
             """    --default-chat-template-kwargs '{"preserve_thinking": true, "reasoning_effort": "medium"}' \\""", s)
elif ARGS.variant == "effort_high":
    # the template has no 'high' (xhigh = careful sentence, medium = no sentence, low = brief): serve a copy with a
    # milder sentence in place of xhigh's, exactly like the xxhigh variant below
    NL = chr(10)
    BSL = chr(92) + NL
    prep = NL.join(HIGH_PREP) + NL
    s = swap("  # Gloo needs a null-terminated hostname.", prep + "  # Gloo needs a null-terminated hostname.", s)
    s = swap('    -v "$MODEL_DIR:/model:ro" ' + BSL,
             '    -v "$MODEL_DIR:/model:ro" ' + BSL + '    -v /opt/arc3/high-chat-template.jinja:/opt/arc3/high-chat-template.jinja:ro ' + BSL, s)
    s = swap("""    --default-chat-template-kwargs '{"preserve_thinking": true}' """ + BSL,
             """    --default-chat-template-kwargs '{"preserve_thinking": true}' """ + BSL + "    --chat-template /opt/arc3/high-chat-template.jinja " + BSL, s)
elif ARGS.variant == "batched16k":
    s = swap("--max-model-len 102985 --max-num-seqs 7 --max-num-batched-tokens 6144", "--max-model-len 102985 --max-num-seqs 7 --max-num-batched-tokens 16384", s)
    assert "6144" not in s, "another 6144 survived"
elif ARGS.variant == "nopreserve":
    # Attempt 1 flipped the default kwarg; the capacity gate's own completion passes preserve_thinking=true explicitly
    # while the harness counter sends only enable_thinking -> 4-token server_prompt_count_mismatch (run ...-3cf2a5c5d6).
    # Serve a template copy whose history-assistant branch ignores preserve_thinking, so every render path agrees.
    NL = chr(10)
    BSL = chr(92) + NL
    TPL_OLD = "        {%- if preserve_thinking is undefined or preserve_thinking is true or loop.index0 > ns.last_query_index %}"
    TPL_NEW = "        {%- if loop.index0 > ns.last_query_index %}"
    prep = NL.join([
        "  cp /opt/arc3/flashnext-model/chat_template.jinja /opt/arc3/nopreserve-chat-template.jinja",
        "  python3 - <<'PYNOPRESERVE'",
        "from pathlib import Path",
        "p = Path('/opt/arc3/nopreserve-chat-template.jinja'); t = p.read_text(encoding='utf-8')",
        f"old = {TPL_OLD!r}",
        f"new = {TPL_NEW!r}",
        "assert t.count(old) == 1, t.count(old)",
        "p.write_text(t.replace(old, new), encoding='utf-8'); print('nopreserve chat template written')",
        "PYNOPRESERVE",
    ]) + NL
    s = swap("  # Gloo needs a null-terminated hostname.", prep + "  # Gloo needs a null-terminated hostname.", s)
    s = swap('    -v "$MODEL_DIR:/model:ro" ' + BSL,
             '    -v "$MODEL_DIR:/model:ro" ' + BSL + '    -v /opt/arc3/nopreserve-chat-template.jinja:/opt/arc3/nopreserve-chat-template.jinja:ro ' + BSL, s)
    s = swap("""    --default-chat-template-kwargs '{"preserve_thinking": true}' """ + BSL,
             """    --default-chat-template-kwargs '{"preserve_thinking": true}' """ + BSL + "    --chat-template /opt/arc3/nopreserve-chat-template.jinja " + BSL, s)
elif ARGS.variant in ("spec", "spec_ngram"):
    NL = chr(10)
    SPEC_MODES = "mtp qwen3_next_mtp ngram" if ARGS.variant == "spec" else "ngram"
    # the speculative flags are the last docker argument; $SPEC_ARGS is set per rung (JSON without spaces, so an
    # unquoted expansion yields exactly two words)
    s = swap("    --cudagraph-capture-sizes 1 2 4 8 12 14 15 16 17 18 19 20 21 22 24 32 40" + NL,
             "    --cudagraph-capture-sizes 1 2 4 8 12 14 15 16 17 18 19 20 21 22 24 32 40 $SPEC_ARGS" + NL, s)
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
    new_serve = NL.join([
        'KV_DTYPE_USED=fp8_e4m3',
        '# Speculative-decoding ladder (arm=lacr_spec). No plain fallback: a rung must serve or the run FAILS, so a',
        '# score can never silently come from stock decoding.',
        'SPEC_MODE=""',
        f'for mode in {SPEC_MODES}; do',
        '  case "$mode" in',
        """    mtp)            SPEC_ARGS='--speculative-config {"method":"mtp","num_speculative_tokens":1}' ;;""",
        """    qwen3_next_mtp) SPEC_ARGS='--speculative-config {"method":"qwen3_next_mtp","num_speculative_tokens":1}' ;;""",
        """    ngram)          SPEC_ARGS='--speculative-config {"method":"ngram","num_speculative_tokens":4,"prompt_lookup_max":4,"prompt_lookup_min":2}' ;;""",
        '  esac',
        '  container_gpu_ready || { sleep 10; container_gpu_ready; }',
        '  start_server "$KV_DTYPE_USED"',
        '  if wait_server; then SPEC_MODE="$mode"; break; fi',
        '  cp /opt/arc3/vllm.log "/opt/arc3/vllm-start-$mode.log"',
        '  timeout 15 gcloud storage cp "/opt/arc3/vllm-start-$mode.log" "$BUCKET/$RUN_ID/vllm-start-$mode.log" || true',
        '  echo "speculative mode \'$mode\' failed; trying next"; sleep 10',
        'done',
        'if [ -z "$SPEC_MODE" ]; then',
        '  echo "vLLM failed to serve with speculative decoding (mtp, qwen3_next_mtp, ngram)" | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"',
        '  sync_all',
        '  exit 1',
        'fi',
        'echo "spec-$SPEC_MODE" | tee /opt/arc3/server-mode.txt | gcloud storage cp - "$BUCKET/$RUN_ID/server-mode"',
    ]) + NL
    s = swap(old_serve, new_serve, s)
elif ARGS.variant == "mtp3":
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
        '  python3 -c "import json,sys; r=json.load(open(\'/opt/arc3/native-context-capacity-gate.json\')); g=r.get(\'gates\',{}); sys.exit(0 if r.get(\'status\')==\'passed\' and g.get(\'zero_preemptions_verified\') and g.get(\'native_capacity_and_reuse_pass\') else 1)"',
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
    # Serve a copy of the model's own chat template with the xhigh sentence extended. Both /tokenize and completions
    # render through the served template, so the harness's exact-count contract still holds.
    NL = chr(10)
    BSL = chr(92) + NL   # backslash-newline: bash line continuation
    prep = NL.join([
        "  cp /opt/arc3/flashnext-model/chat_template.jinja /opt/arc3/xxhigh-chat-template.jinja",
        "  python3 - <<'PYXXHIGH'",
        "from pathlib import Path",
        "p = Path('/opt/arc3/xxhigh-chat-template.jinja'); t = p.read_text(encoding='utf-8')",
        f"old = {XHIGH_SENTENCE!r}",
        f"new = {XXHIGH_SENTENCE!r}",
        "assert t.count(old) == 1, t.count(old)",
        "p.write_text(t.replace(old, new), encoding='utf-8'); print('xxhigh chat template written')",
        "PYXXHIGH",
    ]) + NL
    s = swap("  # Gloo needs a null-terminated hostname.", prep + "  # Gloo needs a null-terminated hostname.", s)
    s = swap('    -v "$MODEL_DIR:/model:ro" ' + BSL,
             '    -v "$MODEL_DIR:/model:ro" ' + BSL + '    -v /opt/arc3/xxhigh-chat-template.jinja:/opt/arc3/xxhigh-chat-template.jinja:ro ' + BSL, s)
    s = swap("""    --default-chat-template-kwargs '{"preserve_thinking": true}' """ + BSL,
             """    --default-chat-template-kwargs '{"preserve_thinking": true}' """ + BSL + "    --chat-template /opt/arc3/xxhigh-chat-template.jinja " + BSL, s)
# export the variant marker beside the gameplay flags so the receipt's extra_environment is observable on the VM
s = swap("export ARC3_PROMPT_ABLATE_LOOP=1\n", f"export ARC3_PROMPT_ABLATE_LOOP=1\nexport {env_key}={env_val}\n", s)
# re-pin CONFIG_FLAGS
s = swap(f"cap-compact132/{old_cfg_sha}/CONFIG_FLAGS.json", f"cap-compact132/{cfg_sha}/CONFIG_FLAGS.json", s)
s = swap(f"echo '{old_cfg_sha}  /opt/arc3/config-audit/CONFIG_FLAGS.json'", f"echo '{cfg_sha}  /opt/arc3/config-audit/CONFIG_FLAGS.json'", s)
# fresh guest self-delete request id
old_req = re.search(r"instances/\$OWNED_VM_NAME\?requestId=([0-9a-f-]{36})", s).group(1)
new_req = str(uuid.uuid4())
s = s.replace(old_req, new_req)
(ARM / "DELETE_REQUEST_ID").write_text(new_req + "\n")
for must in ("ARC3_PROMPT_ABLATE_LOOP=1", "ARC3_ACTION_CAP_MODE=return", "--tool-call-parser qwen3_xml", "--reasoning-parser qwen3",
             "VLLM_PLE_CPU_OFFLOAD=1", f"export {env_key}={env_val}"):
    assert must in s, must
assert "ARC3_CONTEXT_COMPACTION=1" not in s
(ARM / "startup.sh").write_text(s, encoding="utf-8", newline="\n")
(ARM / "META_KEYS.json").write_text(json.dumps(sorted(set(re.findall(r"meta ([a-z0-9-]+)", s))), indent=1))
print("startup.sh", len(s.splitlines()), "lines; sha", hashlib.sha256(s.encode()).hexdigest())
print("uploads needed:", f"code/cap-compact132/{cfg_sha}/CONFIG_FLAGS.json")
