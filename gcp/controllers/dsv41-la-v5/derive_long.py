"""Long-clock ceiling arm: dsv41_la_v5_long = dsv41_la_v5_clean_return_a with the lane/clock
pins lifted (25 lanes, 5 h per game, 330 min suite, 8 h VM) and the MoE served with expert
parallelism (TP8 intermediate-size split is unsupported by the NVFP4 kernel: run #2's failure).
Harness bundle, prompts, cap, compaction, context (102985/94281) and sampling stay frozen.
Re-pins the runner and runtime probe (both outside the candidate bundle) and re-registers
CONFIG_FLAGS.
"""
import hashlib, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / "arms" / "dsv41_la_v5_clean_return_a"
ARM = HERE / "arms" / "dsv41_la_v5_long"
sys.path.insert(0, str(BASE))
import contract  # noqa: E402

LANES, GAME_S, SUITE_MIN, VM_LIFE = 25, 18000, 330, 28800
PREGAME_UPTIME_MAX = 12000          # pre-game work must finish inside this (was 6360)
BUCKET_CODE = "gs://cellens-ai-artifacts/arc3-duck/code/cap-compact132"
RUNNER_OBJ_DIR = "gs://cellens-ai-artifacts/arc3-duck/code/astra-execution/feature-ablation-132-v1"

def sha_b(b: bytes): return hashlib.sha256(b).hexdigest()
def sub1(pat, repl, text, flags=0, count=1):
    new, n = re.subn(pat, repl, text, count=count, flags=flags)
    assert n >= 1, pat
    return new

# ---------------------------------------------------------------- runner.py (from GCS b3604c…)
r = (ARM / "runner.py").read_text(encoding="utf-8")
assert sha_b(r.encode()) == "b3604c7731dde84089cfc20bbf1366378eb0791c5deb88c9e24271ac5b9f53bb"
r = sub1(r"assert bm\.solver\.max_runtime_s_per_game == 2061\.0", f"assert bm.solver.max_runtime_s_per_game == {GAME_S}.0", r)
r = sub1(r"assert bm\.solver\.concurrency == 7", f"assert bm.solver.concurrency == {LANES}", r)
r = sub1(r'"Experimental runtime lock: 7 workers, 2061 seconds/game, "', f'"Experimental runtime lock: {LANES} workers, {GAME_S} seconds/game, "', r)
r = sub1(r"# 4 waves at 2061 seconds/game fit the 132-minute suite.*", f"# One wave: {LANES} lanes x {GAME_S} s/game inside the {SUITE_MIN}-minute suite (long-clock ceiling run).", r)
(ARM / "runner.py").write_text(r, encoding="utf-8", newline="\n")
runner_sha = sha_b((ARM / "runner.py").read_bytes())

# ---------------------------------------------------------------- runtime_probe.py
p = (BASE / "runtime_probe.py").read_text(encoding="utf-8")
p = sub1(r"assert args\[args\.index\('--kv-cache-dtype'\)\+1\]=='fp8_e4m3'", "assert args[args.index('--kv-cache-dtype')+1]=='fp8'", p)
p = sub1(r"assert args\[args\.index\('--max-num-seqs'\)\+1\]=='7'", f"assert args[args.index('--max-num-seqs')+1]=='{LANES}'", p)
p = sub1(r"'vm_lifetime_seconds':14400", f"'vm_lifetime_seconds':{VM_LIFE}", p)
p = sub1(r"original 14400-second", f"original {VM_LIFE}-second", p)
p = sub1(r"anchor='soft_end = datetime\.now\(\) \+ timedelta\(minutes=132\)'", f"anchor='soft_end = datetime.now() + timedelta(minutes={SUITE_MIN})'", p)
p = sub1(r"attest\(bm,target,132\)", f"attest(bm,target,{SUITE_MIN})", p)
(ARM / "runtime_probe.py").write_text(p, encoding="utf-8", newline="\n")
probe_sha = sha_b((ARM / "runtime_probe.py").read_bytes())
old_probe_sha = sha_b((BASE / "runtime_probe.py").read_bytes())

# ---------------------------------------------------------------- CONFIG_FLAGS.json
cfg = json.loads((BASE / "CONFIG_FLAGS.json").read_text(encoding="utf-8-sig"))
lim = cfg["recipe"]["limits"]
lim.update({"lanes": LANES, "game_seconds": GAME_S, "suite_gameplay_minutes": SUITE_MIN, "vm_lifetime_seconds": VM_LIFE})
env = cfg["recipe"]["extra_environment"]
env.update({"ARC3_BENCHMARK_CONCURRENCY": str(LANES), "ARC3_MAX_RUNTIME_S_PER_GAME": str(GAME_S), "ARC3_MAX_RUN_RUNTIME_MINUTES": str(SUITE_MIN)})
cfg["recipe"]["model"]["weights"] += "; expert parallel across 8 GPUs"
cfg["recipe"]["model"]["kv_dtype"] = "fp8"   # nightly rejects the fp8_e4m3 alias for DeepseekV4 packed KV
cfg["run_id"] = "g4run-dsv41flash-la-v5-long-w8x-20260922"
cfg["evidence"]["notes"] = [
    f"September22 user: 'Let's just run for a long time actually … all 25 lanes … keep the context window cap for each lane.' "
    f"Long-clock ceiling run of the la_v5_clean_return_a candidate with DeepSeek-V4.1-Flash-NVFP4: {LANES} lanes "
    f"(every game concurrent, no waves), {GAME_S} s per game, {SUITE_MIN}-minute suite, {VM_LIFE}-second VM life. "
    "Context 102985 / input 94281, cap 14 return, compaction v5, Loop A, time-only guidance, sampling 1.0/0.95/20 "
    "unchanged. Served TP8 + expert parallel (TP-only failed: NVFP4 intermediate-size padding unsupported). "
    "This is not comparable to the 132-minute LA pair on clock; it measures what the harness+model reach when "
    "time is not the binding constraint. One attempt, Spot, no Kaggle action.",
] + cfg["evidence"]["notes"][1:]
cfg["config_id"] = contract.config_id(cfg["recipe"])
contract.validate(cfg, for_launch=True)
cfg_bytes = (json.dumps(cfg, indent=2) + "\n").encode()
cfg_sha = sha_b(cfg_bytes); old_cfg_sha = sha_b((BASE / "CONFIG_FLAGS.json").read_bytes())
(ARM / "CONFIG_FLAGS.json").write_bytes(cfg_bytes)

# ---------------------------------------------------------------- startup.sh
s = (BASE / "startup.sh").read_text(encoding="utf-8")
s = sub1(r"# arm=dsv41_la_v5_clean_return_a\. Server: vLLM TP8", "# arm=dsv41_la_v5_long (25 lanes, 5 h/game, 330 min suite, 8 h VM). Server: vLLM TP8+EP", s)
# lifetime / uptime guards
s = sub1(r"# Hard cost guard: 14400 seconds", f"# Hard cost guard: {VM_LIFE} seconds", s)
s = sub1(r"^  sleep 14400$", f"  sleep {VM_LIFE}", s, re.M)
s = sub1(r"--interval-seconds 30 --max-seconds 14400", f"--interval-seconds 30 --max-seconds {VM_LIFE}", s)
s = sub1(r'test "\$\(cut -d\. -f1 /proc/uptime\)" -lt 6360', f'test "$(cut -d. -f1 /proc/uptime)" -lt {PREGAME_UPTIME_MAX}', s)
# runner: new object + hash; soft-end patch target
s = sub1(r"echo 'b3604c7731dde84089cfc20bbf1366378eb0791c5deb88c9e24271ac5b9f53bb  /opt/arc3/v12_run\.py'", f"echo '{runner_sha}  /opt/arc3/v12_run.py'", s)
s = sub1(r"new = 'soft_end = datetime\.now\(\) \+ timedelta\(minutes=132\)'", f"new = 'soft_end = datetime.now() + timedelta(minutes={SUITE_MIN})'", s)
s = sub1(r"grep -F 'soft_end = datetime\.now\(\) \+ timedelta\(minutes=132\)'", f"grep -F 'soft_end = datetime.now() + timedelta(minutes={SUITE_MIN})'", s)
# server: EP first, TP8+marlin fallback; lanes
s = sub1(r'''  local kv_dtype="\$1" blackwell="\$2"
  local extra=\(\) envs=\(\)
  if \[ "\$blackwell" = 1 \]; then
    # vLLM recipe's Blackwell \(B200/B300\) sparse-MLA path; sm_120 support is unverified,
    # so attempt 2 runs without these if the server does not come up\.
    extra=\(--indexer-kv-dtype mxfp4 --indexer-sparse-logits true\)
    envs=\(-e FLASHINFER_MLA_SPARSE_DSV41=1\)
  fi''',
'''  local kv_dtype="$1" mode="$2"
  local extra=(--enable-expert-parallel) envs=()
  # Run #2 (TP8, no EP) failed: "Intermediate size padding for w1 and w3 ... NvFp4 backend
  # FLASHINFER_CUTLASS not supported". Expert parallelism keeps whole experts per GPU.
  # Attempt 2 keeps EP and swaps the V4.1 sparse-attention kernel family.
  if [ "$mode" = flashmla ]; then
    extra+=(--attention-backend FLASHMLA_SPARSE_DSV41)
  fi''', s)
# sm_120 indexer overlay, built on the VM from the image's own file so image drift is caught.
# In this build DeepseekV41IndexerBackend picks kernel block 128 for every non-Hopper GPU, but
# DeepGEMM's paged-MQA-logits kernel on sm_120 asserts block_kv in {32, 64} (runs #3 and #5).
# Hopper runs the indexer at 64 under the backend's 128 KV block (block table divided by 2);
# that is the working H200 recipe. Route sm_120 the same way.
OVERLAY = r'''INDEXER_PATH=/usr/local/lib/python3.12/dist-packages/vllm/v1/attention/backends/mla/indexer.py
mkdir -p /opt/arc3/indexer-overlay
docker run --rm --entrypoint cat "$CONTAINER_IMAGE" "$INDEXER_PATH" > /opt/arc3/indexer-overlay/indexer.py
sha256sum /opt/arc3/indexer-overlay/indexer.py | tee /opt/arc3/indexer-base-sha.txt
python3 - <<'PYPATCH'
from pathlib import Path
p = Path('/opt/arc3/indexer-overlay/indexer.py'); s = p.read_text()
old = "return [64 if current_platform.is_device_capability_family(90) else 128]"
new = "return [128 if current_platform.is_device_capability_family(100) else 64]  # arc3 sm_120 overlay"
assert s.count(old) == 1, s.count(old)
p.write_text(s.replace(old, new)); print("indexer overlay applied")
PYPATCH
python3 -c "import ast; ast.parse(open('/opt/arc3/indexer-overlay/indexer.py').read())"
gcloud storage cp /opt/arc3/indexer-overlay/indexer.py "$BUCKET/$RUN_ID/indexer-overlay.py" >/dev/null 2>&1 || true

start_server() {'''
s = sub1(r"^start_server\(\) \{$", OVERLAY, s, re.M)
s = sub1(r'    -v /opt/arc3/vllm-cache:/root/\.cache \\\n',
         '    -v /opt/arc3/vllm-cache:/root/.cache \\\n    -v "/opt/arc3/indexer-overlay/indexer.py:$INDEXER_PATH:ro" \\\n', s)
s = sub1(r"--max-model-len 102985 --max-num-seqs 7 --max-num-batched-tokens 16384", f"--max-model-len 102985 --max-num-seqs {LANES} --max-num-batched-tokens 16384", s)
s = sub1(r'SERVER_MODE=blackwell-flags\nstart_server "\$KV_DTYPE_USED" 1', 'SERVER_MODE=tp8-ep8-flashinfer\nstart_server "$KV_DTYPE_USED" flashinfer', s)
s = sub1(r'  SERVER_MODE=plain\n  start_server "\$KV_DTYPE_USED" 0', '  SERVER_MODE=tp8-ep8-flashmla\n  start_server "$KV_DTYPE_USED" flashmla', s)
s = sub1(r'"requested_server_sequences": 7,', f'"requested_server_sequences": {LANES},', s)
# smoke: lanes
s = sub1(r"ThreadPoolExecutor\(max_workers=7\) as pool:\n    capacity = list\(pool\.map\(capacity_call, range\(7\)\)\)",
         f"ThreadPoolExecutor(max_workers={LANES}) as pool:\n    capacity = list(pool.map(capacity_call, range({LANES})))", s)
s = sub1(r'    "max_num_seqs": 7,', f'    "max_num_seqs": {LANES},', s)
s = sub1(r"# Verify ordinary text, vision \(the harness sends current_grid images\), and 7", f"# Verify ordinary text, vision (the harness sends current_grid images), and {LANES}", s)
# capacity gate: lanes
s = sub1(r"--context 102985 --concurrency 7 --append-rounds 2", f"--context 102985 --concurrency {LANES} --append-rounds 2", s)
s = sub1(r"# Native 7x102985 acceptance", f"# Native {LANES}x102985 acceptance", s)
s = sub1(r"assert report\['configuration'\]\['concurrency'\] == 7", f"assert report['configuration']['concurrency'] == {LANES}", s)
# harness env + champion asserts
s = sub1(r"export ARC3_BENCHMARK_CONCURRENCY=7\nexport ARC3_MAX_RUNTIME_S_PER_GAME=2061\nexport ARC3_MAX_RUN_RUNTIME_MINUTES=132",
         f"export ARC3_BENCHMARK_CONCURRENCY={LANES}\nexport ARC3_MAX_RUNTIME_S_PER_GAME={GAME_S}\nexport ARC3_MAX_RUN_RUNTIME_MINUTES={SUITE_MIN}", s)
s = sub1(r"assert os\.environ\['ARC3_BENCHMARK_CONCURRENCY'\] == '7'", f"assert os.environ['ARC3_BENCHMARK_CONCURRENCY'] == '{LANES}'", s)
s = sub1(r"assert os\.environ\['ARC3_MAX_RUNTIME_S_PER_GAME'\] == '2061'", f"assert os.environ['ARC3_MAX_RUNTIME_S_PER_GAME'] == '{GAME_S}'", s)
s = sub1(r"assert os\.environ\['ARC3_MAX_RUN_RUNTIME_MINUTES'\] == '132'", f"assert os.environ['ARC3_MAX_RUN_RUNTIME_MINUTES'] == '{SUITE_MIN}'", s)
s = sub1(r'print\("verified feature arm baseline; no curator; 132-minute suite"\)', f'print("verified feature arm baseline; no curator; {SUITE_MIN}-minute suite, {LANES} lanes")', s)
# probe + config objects
s = sub1(re.escape(f"gcloud storage cp 'gs://cellens-ai-artifacts/arc3-duck/code/cap-compact132/{old_probe_sha}/runtime_probe.py'"),
         f"gcloud storage cp '{BUCKET_CODE}/{probe_sha}/runtime_probe.py'", s)
s = sub1(re.escape(f"echo '{old_probe_sha}  /opt/arc3/config-audit/runtime_probe.py'"), f"echo '{probe_sha}  /opt/arc3/config-audit/runtime_probe.py'", s)
s = sub1(re.escape(f"gcloud storage cp 'gs://cellens-ai-artifacts/arc3-duck/code/cap-compact132/{old_cfg_sha}/CONFIG_FLAGS.json'"),
         f"gcloud storage cp '{BUCKET_CODE}/{cfg_sha}/CONFIG_FLAGS.json'", s)
s = sub1(re.escape(f"echo '{old_cfg_sha}  /opt/arc3/config-audit/CONFIG_FLAGS.json'"), f"echo '{cfg_sha}  /opt/arc3/config-audit/CONFIG_FLAGS.json'", s)
s = sub1(r"KV_DTYPE_USED=fp8_e4m3", "KV_DTYPE_USED=fp8", s)
# capacity gate: 300 s is enough evidence for a ceiling run (the LA arm's 1200 s is Kaggle-parity proof)
s = sub1(r"--total-seconds 1200 --request-timeout 300", "--total-seconds 300 --request-timeout 300", s)
s = sub1(r"timeout --kill-after=10 1230 /opt/arc3/pysrv/bin/python -B /opt/arc3/context-matrix-capacity-r1/capacity_gate.py", "timeout --kill-after=10 330 /opt/arc3/pysrv/bin/python -B /opt/arc3/context-matrix-capacity-r1/capacity_gate.py", s)
# fresh self-delete request id
import uuid
old_req = (BASE / "DELETE_REQUEST_ID").read_text().strip(); new_req = str(uuid.uuid4())
s = sub1(re.escape(old_req), new_req, s)
(ARM / "DELETE_REQUEST_ID").write_text(new_req)
for leftover in ("2061", "minutes=132", "'7'", "== 7", "concurrency 7", "sleep 14400", "max-num-seqs 7", "--indexer-kv-dtype", "blackwell"):
    assert leftover not in s, leftover
(ARM / "startup.sh").write_text(s, encoding="utf-8", newline="\n")

(ARM / "ARM.json").write_text(json.dumps({
    "arm": "dsv41_la_v5_long", "lanes": LANES, "game_seconds": GAME_S, "suite_minutes": SUITE_MIN, "vm_lifetime_seconds": VM_LIFE,
    "runner_object": f"{RUNNER_OBJ_DIR}/{runner_sha}/runner.py", "runner_sha256": runner_sha,
    "probe_object": f"{BUCKET_CODE}/{probe_sha}/runtime_probe.py", "probe_sha256": probe_sha,
    "config_object": f"{BUCKET_CODE}/{cfg_sha}/CONFIG_FLAGS.json", "config_sha256": cfg_sha, "config_id": cfg["config_id"],
    "run_id_prefix": "g4run-dsv41flash-la-v5-long-w8x", "instance_prefix": "arc3-g4-dsv41flash-la-v5-long",
}, indent=2))
print("config_id", cfg["config_id"]); print("runner", runner_sha); print("probe", probe_sha); print("config", cfg_sha)
print("startup lines", len(s.splitlines()))
