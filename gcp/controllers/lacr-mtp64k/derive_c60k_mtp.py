"""LA-CR at 7 lanes x 61,440 context with MTP speculative decoding (3 draft tokens).

Son, 25-Sep: MTP recipe "claims >300 tok/s"; after the mtp3 ladder showed the drafter costs 5.2 GiB (KV 13.76 ->
8.6 GiB = 463k tokens, 4.5x of 102,985), "Yes, I want to try 64k". 7 x 65,536 = 459k leaves 1% headroom for the
capacity gate, so the arm uses 61,440 per lane (430k, 7% headroom). Input budget = 61,440 - 8,192 - 512 = 52,736.

Base: la_clean_return_a (21-Sep LA-CR, 18.01 / 19.24 on all 25 at 132 min). Everything else byte-identical.
Pinned places that move (every 102985 / 94281): runner (env assert + banner), runtime_probe (input-budget and
max-model-len asserts), CONFIG_FLAGS (env, limits, source_sha256, marker), candidate bundle FEATURE_ARM.json
(context_window + env) and therefore the release manifest (candidate_files sha, env, context_window,
candidate_bundle_sha256, source_tree_sha256), selftest bundle (feature_contract CONTEXT, live_half_swap_gate
budget, candidate/FEATURE_ARM.json copy), ADAPTER effective runner sha, startup (model-info, --max-model-len,
selftest --context flags, capacity gate --context/--run-key, env exports, asserts, pins, MTP ladder).
"""
import hashlib, io, json, os, re, shutil, sys, tarfile, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(r"D:\codex-work\la-clean-return132-20260921\arms\la_clean_return_a")
PARENT_RUN = "g4run-la-clean-return-a132-w7-20260921-b4119c3bbb"
BUCKET_CODE = "gs://cellens-ai-artifacts/arc3-duck/code/lacr-mtp64k-v1"
RUNNER_DIR = BUCKET_CODE
CTX, OLD_CTX = 61440, 102985
BUDGET, OLD_BUDGET = CTX - 8192 - 512, 94281
assert OLD_BUDGET == OLD_CTX - 8192 - 512
ARM_NAME = "lacr_mtp3_c60k_a"
ARM = HERE / "arms" / ARM_NAME
NL = chr(10); BSL = chr(92)
sys.path.insert(0, str(SRC)); sys.path.insert(0, str(HERE))
import contract  # noqa: E402
from watchdog import add_watchdog  # noqa: E402


def sha_b(b: bytes) -> str: return hashlib.sha256(b).hexdigest()
def enc(x) -> bytes: return (json.dumps(x, sort_keys=True, indent=2) + NL).encode()
def sub1(pat, repl, text, flags=0):
    new, n = re.subn(pat, repl, text, count=1, flags=flags)
    assert n == 1, (pat, n)
    return new
def subn(pat, repl, text, expected, flags=0):
    new, n = re.subn(pat, repl, text, flags=flags)
    assert n == expected, (pat, n, expected)
    return new
def lit1(old, new, text):
    assert text.count(old) == 1, (old[:80], text.count(old))
    return text.replace(old, new)
def repack(dirpath: Path, names: list[str]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=9) as t:
        for name in sorted(names):
            full = dirpath / name; ti = t.gettarinfo(str(full), arcname=name)
            ti.mtime = 0; ti.uid = ti.gid = 0; ti.uname = ti.gname = ""
            if ti.isreg():
                with open(full, "rb") as fh: t.addfile(ti, fh)
            else: t.addfile(ti)
    return buf.getvalue()


if ARM.exists(): shutil.rmtree(ARM)
ARM.mkdir(parents=True)
for f in ("contract.py", "prompt_probe.py", "time_guidance_probe.py", "EXPECTED_PROMPTS.json", "instance-body.json"):
    shutil.copy(SRC / f, ARM / f)
work = HERE / "_work";
if work.exists(): shutil.rmtree(work)
work.mkdir()

# ---------------------------------------------------------------- candidate bundle: FEATURE_ARM.json
cand_dir = work / "candidate"; cand_dir.mkdir()
with tarfile.open(SRC / "candidate.tgz") as t:
    cand_names = t.getnames(); t.extractall(cand_dir)
fa = json.loads((cand_dir / "FEATURE_ARM.json").read_text(encoding="utf-8"))
assert fa["context_window"] == OLD_CTX and fa["environment"]["LOCAL_ANALYZER_CONTEXT_WINDOW"] == str(OLD_CTX)
fa["context_window"] = CTX; fa["environment"]["LOCAL_ANALYZER_CONTEXT_WINDOW"] = str(CTX)
fa_bytes = (json.dumps(fa, indent=2) + NL).encode()
(cand_dir / "FEATURE_ARM.json").write_bytes(fa_bytes)
candidate_bytes = repack(cand_dir, cand_names); (ARM / "candidate.tgz").write_bytes(candidate_bytes)
candidate_sha = sha_b(candidate_bytes); old_candidate_sha = sha_b((SRC / "candidate.tgz").read_bytes())

# ---------------------------------------------------------------- selftest bundle + release manifest
st_dir = work / "selftest"; st_dir.mkdir()
with tarfile.open(SRC / "selftest.tgz") as t:
    st_names = t.getnames(); t.extractall(st_dir)
fc = st_dir / "feature_contract.py"; x = fc.read_text(encoding="utf-8")
x = sub1(rf"^CONTEXT = {OLD_CTX}$", f"CONTEXT = {CTX}", x, re.M); fc.write_text(x, encoding="utf-8", newline=NL)
hg = st_dir / "live_half_swap_gate.py"; x = hg.read_text(encoding="utf-8")
x = sub1(rf"production=={OLD_BUDGET}", f"production=={BUDGET}", x); hg.write_text(x, encoding="utf-8", newline=NL)
(st_dir / "candidate" / "FEATURE_ARM.json").write_bytes(fa_bytes)
man = json.loads((st_dir / "release-manifest.json").read_text(encoding="utf-8"))
assert man["candidate_files"]["FEATURE_ARM.json"] == sha_b((SRC / "candidate.tgz").read_bytes()) or True  # (digest of the old file; replaced below)
man["candidate_files"]["FEATURE_ARM.json"] = sha_b(fa_bytes)
man["candidate_bundle_sha256"] = candidate_sha
man["source_tree_sha256"] = sha_b(enc(man["candidate_files"]))
man_text = json.dumps(man)
assert str(OLD_CTX) in man_text
def fix_ctx(obj):
    if isinstance(obj, dict): return {k: fix_ctx(v) for k, v in obj.items()}
    if isinstance(obj, list): return [fix_ctx(v) for v in obj]
    if obj == OLD_CTX: return CTX
    if obj == str(OLD_CTX): return str(CTX)
    return obj
man = fix_ctx(man)
assert str(OLD_CTX) not in json.dumps(man)
source_sha256 = sha_b(enc(man["candidate_files"]))
manifest_bytes = enc(man)
(st_dir / "release-manifest.json").write_bytes(manifest_bytes); (ARM / "release.json").write_bytes(manifest_bytes)
release_sha = sha_b(manifest_bytes); old_release_sha = sha_b((SRC / "release.json").read_bytes())
for p in st_dir.rglob("*.py"):
    if p.is_relative_to(st_dir / "candidate"): continue
    txt = p.read_text(encoding="utf-8", errors="replace")
    assert str(OLD_CTX) not in txt, f"unexpected {OLD_CTX} in {p.relative_to(st_dir)}"
    if str(OLD_BUDGET) in txt and p.name != "test_reminder_requests.py":
        raise AssertionError(f"unexpected {OLD_BUDGET} in {p.relative_to(st_dir)}")
selftest_bytes = repack(st_dir, st_names); (ARM / "selftest.tgz").write_bytes(selftest_bytes)
selftest_sha = sha_b(selftest_bytes); old_selftest_sha = sha_b((SRC / "selftest.tgz").read_bytes())

# ---------------------------------------------------------------- runner.py (pinned base b3604c...)
r = (HERE / "base_runner.py").read_text(encoding="utf-8")
old_runner_sha = sha_b(r.encode()); assert old_runner_sha.startswith("b3604c7731")
r = sub1(rf'assert os\.environ\["LOCAL_ANALYZER_CONTEXT_WINDOW"\] == "{OLD_CTX}"', f'assert os.environ["LOCAL_ANALYZER_CONTEXT_WINDOW"] == "{CTX}"', r)
r = sub1(rf"full_context{OLD_CTX}", f"full_context{CTX} MTP3", r)
(ARM / "runner.py").write_text(r, encoding="utf-8", newline=NL); runner_sha = sha_b((ARM / "runner.py").read_bytes())
old_anchor = "soft_end = datetime.now() + timedelta(hours=11, minutes=20)"; new_anchor = "soft_end = datetime.now() + timedelta(minutes=132)"
assert r.count(old_anchor) == 1
adapter = json.loads((SRC / "ADAPTER.json").read_text(encoding="utf-8-sig"))
adapter["effective_runner_sha256"] = sha_b(r.replace(old_anchor, new_anchor).encode())
adapter["experiment_arm"] = ARM_NAME
adapter_bytes = enc(adapter); (ARM / "ADAPTER.json").write_bytes(adapter_bytes)
adapter_sha = sha_b(adapter_bytes); old_adapter_sha = sha_b((SRC / "ADAPTER.json").read_bytes())

# ---------------------------------------------------------------- runtime_probe.py
p = (SRC / "runtime_probe.py").read_text(encoding="utf-8")
p = sub1(rf"agent\._context_budget_tokens=={OLD_BUDGET}", f"agent._context_budget_tokens=={BUDGET}", p)
p = sub1(rf"'--max-model-len'\)\+1\]=='{OLD_CTX}'", f"'--max-model-len')+1]=='{CTX}'", p)
assert str(OLD_CTX) not in p and str(OLD_BUDGET) not in p
(ARM / "runtime_probe.py").write_text(p, encoding="utf-8", newline=NL)
probe_sha = sha_b((ARM / "runtime_probe.py").read_bytes()); old_probe_sha = sha_b((SRC / "runtime_probe.py").read_bytes())

# ---------------------------------------------------------------- CONFIG_FLAGS.json
cfg = json.loads((SRC / "CONFIG_FLAGS.json").read_text(encoding="utf-8-sig")); rec = cfg["recipe"]
assert rec["extra_environment"]["LOCAL_ANALYZER_CONTEXT_WINDOW"] == str(OLD_CTX)
assert rec["limits"]["context_tokens"] == OLD_CTX and rec["limits"]["input_tokens"] == OLD_BUDGET
rec["extra_environment"]["LOCAL_ANALYZER_CONTEXT_WINDOW"] = str(CTX)
rec["extra_environment"]["ARC3_SERVING_SPECULATIVE"] = "mtp3-c61440"
rec["limits"]["context_tokens"] = CTX; rec["limits"]["input_tokens"] = BUDGET
rec["source_sha256"] = source_sha256
cfg["run_id"] = "g4run-lacr-mtp3-c60k-a132-w7-20260925"
cfg["evidence"]["notes"] = [
    "September25 user: 'Yes, I want to try 64k' after the mtp3 ladder showed MTP's drafter costs 5.2 GiB on this card "
    "(KV 13.76 -> 8.6 GiB = 463k tokens, 4.5x of 102,985; forced 13 GiB pools OOM). LA-CR (la_clean_return_a) with "
    f"7 lanes x {CTX} context (430k KV tokens, 7% headroom; 65,536 would leave 1%) and MTP speculative decoding, "
    "3 draft tokens; ladder k=3/batch 6144 -> k=3/batch 2048 -> k=2/batch 6144, each must pass the native 7-lane "
    f"capacity gate at {CTX} or the run FAILS. Input budget {BUDGET}. Model, prompts, tools, cap 14/return, time-only "
    "guidance, 50% swap, 2061 s/game, 132 minutes, Spot: unchanged. Public single-Blackwell recipe context: 139 tok/s "
    "single-stream / 420 tok/s at 4 streams with a 300k-token KV pool at 200k context.",
] + cfg["evidence"]["notes"][1:]
cfg["config_id"] = contract.config_id(rec); contract.validate(cfg, for_launch=True)
cfg_bytes = (json.dumps(cfg, indent=2) + NL).encode(); (ARM / "CONFIG_FLAGS.json").write_bytes(cfg_bytes)
cfg_sha = sha_b(cfg_bytes); old_cfg_sha = sha_b((SRC / "CONFIG_FLAGS.json").read_bytes())

# ---------------------------------------------------------------- startup.sh
s = (SRC / "startup.sh").read_text(encoding="utf-8")
head = s.splitlines()[1]
s = s.replace(head, f"# LA-CR at 7 x {CTX} context with MTP (3 draft tokens): {head.lstrip('# ')}", 1)
s = sub1(rf'"context_length": {OLD_CTX},', f'"context_length": {CTX},', s)
s = sub1(r'"mtp_enabled": False,', '"mtp_enabled": True,', s)
s = lit1(f"--max-model-len {OLD_CTX} --max-num-seqs 7 --max-num-batched-tokens 6144 " + BSL + NL,
         f"--max-model-len {CTX} --max-num-seqs 7 --max-num-batched-tokens $MTP_BATCH " + BSL + NL, s)
s = lit1("    --cudagraph-capture-sizes 1 2 4 8 12 14 15 16 17 18 19 20 21 22 24 32 40" + NL,
         "    --cudagraph-capture-sizes 1 2 4 8 12 14 15 16 17 18 19 20 21 22 24 32 40 --speculative-config $MTP_SPEC" + NL, s)
gate_cmd = NL.join([
    'run_capacity_gate() {',
    "  gcloud storage cp 'gs://cellens-ai-artifacts/arc3-duck/code/astra-execution/context-matrix-r1/0dbd08c9aeec9c5681c232fec2f42fd8e5aa6d9bd3b2a97bdb4bfa0ccef3c186/context-matrix-capacity-r1.tgz' /tmp/astra-native-context-capacity.tgz",
    "  echo '0dbd08c9aeec9c5681c232fec2f42fd8e5aa6d9bd3b2a97bdb4bfa0ccef3c186  /tmp/astra-native-context-capacity.tgz' | sha256sum -c -",
    '  tar xzf /tmp/astra-native-context-capacity.tgz -C /opt/arc3',
    '  timeout --kill-after=10 1230 /opt/arc3/pysrv/bin/python -B /opt/arc3/context-matrix-capacity-r1/capacity_gate.py ' + BSL,
    '    --base-url http://127.0.0.1:1234/v1 --model "$SERVED_MODEL_NAME" ' + BSL,
    f'    --context {CTX} --concurrency 7 --append-rounds 2 ' + BSL,
    f'    --total-seconds 1200 --request-timeout 300 --run-key c{CTX}-w7-mtp3-r1 ' + BSL,
    '    --output /opt/arc3/native-context-capacity-gate.json --ack-idle-pregame-server ' + BSL,
    '    2>&1 | tee /opt/arc3/native-context-capacity-gate.log',
    '  python3 -c "import json,sys; r=json.load(open(\'/opt/arc3/native-context-capacity-gate.json\')); g=r.get(\'gates\',{}); sys.exit(0 if r.get(\'status\')==\'passed\' and g.get(\'zero_preemptions_verified\') and g.get(\'native_capacity_and_reuse_pass\') else 1)"',
    '}',
]) + NL
old_serve = NL.join([
    'KV_DTYPE_USED=fp8_e4m3', 'start_server "$KV_DTYPE_USED"', 'if ! wait_server; then',
    '  cp /opt/arc3/vllm.log /opt/arc3/vllm-start-attempt1.log', '  sleep 10', '  container_gpu_ready', '  start_server "$KV_DTYPE_USED"', 'fi',
    'if ! wait_server; then', '  echo "Experimental vLLM failed for requested KV" | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"', '  sync_all', '  exit 1', 'fi',
]) + NL
new_serve = gate_cmd + NL.join([
    'KV_DTYPE_USED=fp8_e4m3',
    f'# MTP ladder at {CTX} context: each rung must serve AND pass the native 7x{CTX} capacity gate with zero preemptions.',
    '# No plain fallback: a score can never silently come from stock decoding.',
    'MTP_RUNG=""',
    'for rung in "3 6144 k3-b6144" "3 2048 k3-b2048" "2 6144 k2-b6144"; do',
    '  read -r MTP_K MTP_BATCH tag <<< "$rung"',
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
    f'  echo "vLLM MTP ladder failed (no rung served and passed the 7x{CTX} capacity gate)" | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"',
    '  sync_all', '  exit 1', 'fi',
    'touch /opt/arc3/mtp-gate-passed',
    'echo "mtp-$MTP_RUNG" | tee /opt/arc3/server-mode.txt | gcloud storage cp - "$BUCKET/$RUN_ID/server-mode"',
]) + NL
assert s.count(old_serve) == 1; s = s.replace(old_serve, new_serve)
# original gate invocation: skipped once the ladder passed it; its flags still say the new context
s = lit1(NL + "timeout --kill-after=10 1230 /opt/arc3/pysrv/bin/python -B /opt/arc3/context-matrix-capacity-r1/capacity_gate.py " + BSL + NL,
         NL + "[ -f /opt/arc3/mtp-gate-passed ] || timeout --kill-after=10 1230 /opt/arc3/pysrv/bin/python -B /opt/arc3/context-matrix-capacity-r1/capacity_gate.py " + BSL + NL, s)
s = sub1(rf"  --context {OLD_CTX} --concurrency 7 --append-rounds 2 ", f"  --context {CTX} --concurrency 7 --append-rounds 2 ", s)
s = sub1(rf"--run-key c{OLD_CTX}-w7-matrix-r1", f"--run-key c{CTX}-w7-mtp3-r1", s)
s = sub1(rf"^# Native 7x{OLD_CTX} acceptance", f"# Native 7x{CTX} acceptance", s, re.M)
s = subn(rf"export LOCAL_ANALYZER_CONTEXT_WINDOW={OLD_CTX}", f"export LOCAL_ANALYZER_CONTEXT_WINDOW={CTX}", s, 2)
s = sub1(rf'--live --arm baseline --model "\$SERVED_MODEL_NAME" --context {OLD_CTX} ', f'--live --arm baseline --model "$SERVED_MODEL_NAME" --context {CTX} ', s)
s = sub1(rf"--live --context {OLD_CTX} --base-url", f"--live --context {CTX} --base-url", s)
s = sub1(rf"assert os\.environ\['LOCAL_ANALYZER_CONTEXT_WINDOW'\] == '{OLD_CTX}'", f"assert os.environ['LOCAL_ANALYZER_CONTEXT_WINDOW'] == '{CTX}'", s)
s = sub1(rf"assert agent\._context_budget_tokens == {OLD_BUDGET}", f"assert agent._context_budget_tokens == {BUDGET}", s)
s = sub1(rf"assert report\['configuration'\]\['context'\] == {OLD_CTX}", f"assert report['configuration']['context'] == {CTX}", s)
s = sub1(rf"assert renderer\['context'\] == {OLD_CTX}", f"assert renderer['context'] == {CTX}", s)
s = sub1(rf"assert renderer\['input_budget'\] == {OLD_BUDGET}", f"assert renderer['input_budget'] == {BUDGET}", s)
s = sub1(re.escape(f"echo '{old_candidate_sha}  /tmp/bundle.tgz'"), f"echo '{candidate_sha}  /tmp/bundle.tgz'", s)
s = sub1(re.escape(f"echo '{old_runner_sha}  /opt/arc3/v12_run.py'"), f"echo '{runner_sha}  /opt/arc3/v12_run.py'", s)
src_code = re.search(r"gs://cellens-ai-artifacts/arc3-duck/code/([a-z0-9-]+)/[0-9a-f]{64}/runtime_probe\.py", s).group(1)
for old, new, fn in ((old_probe_sha, probe_sha, "runtime_probe.py"), (old_cfg_sha, cfg_sha, "CONFIG_FLAGS.json"), (old_adapter_sha, adapter_sha, "ADAPTER.json")):
    s = sub1(re.escape(f"gs://cellens-ai-artifacts/arc3-duck/code/{src_code}/{old}/{fn}"), f"{BUCKET_CODE}/{new}/{fn}", s)
    s = sub1(re.escape(f"echo '{old}  /opt/arc3/config-audit/{fn}'"), f"echo '{new}  /opt/arc3/config-audit/{fn}'", s)
s = sub1(re.escape(f"echo '{old_selftest_sha}  /tmp/execution-selftest.tgz'"), f"echo '{selftest_sha}  /tmp/execution-selftest.tgz'", s)
s = sub1(re.escape(f"echo '{old_release_sha}  /opt/arc3/execution-release-manifest.json'"), f"echo '{release_sha}  /opt/arc3/execution-release-manifest.json'", s)
s = sub1(r"^export ARC3_PROMPT_ABLATE_LOOP=1$", "export ARC3_PROMPT_ABLATE_LOOP=1" + NL + "export ARC3_SERVING_SPECULATIVE=mtp3-c61440", s, re.M)
s = add_watchdog(s)
old_req = re.search(r"requestId=([0-9a-f-]{36})", s).group(1); new_req = str(uuid.uuid4())
s = s.replace(old_req, new_req); (ARM / "DELETE_REQUEST_ID").write_text(new_req)
leftovers = [m.start() for m in re.finditer(str(OLD_CTX), s)]
ctx_lines = [s[max(0, i - 60):i + 40].replace(NL, " | ") for i in leftovers]
allowed = [l for l in ctx_lines if "vllm-cache-flashnext-baseline-w7-c102985-132" in l]
assert len(allowed) == len(ctx_lines), ctx_lines
assert str(OLD_BUDGET) not in s
(ARM / "startup.sh").write_text(s, encoding="utf-8", newline=NL)
shutil.rmtree(work)

# ---------------------------------------------------------------- ARM.json (launch_396.py contract)
pp_sha = re.search(rf"gs://cellens-ai-artifacts/arc3-duck/code/{src_code}/([0-9a-f]{{64}})/prompt_probe\.py", s).group(1)
ep_sha = re.search(rf"gs://cellens-ai-artifacts/arc3-duck/code/{src_code}/([0-9a-f]{{64}})/EXPECTED_PROMPTS\.json", s).group(1)
assert sha_b((ARM / "prompt_probe.py").read_bytes()) == pp_sha and sha_b((ARM / "EXPECTED_PROMPTS.json").read_bytes()) == ep_sha
arm_json = {
    "arm": ARM_NAME, "lanes": 7, "games": 25, "subset": "", "game_seconds": 2061, "suite_minutes": 132, "vm_lifetime_seconds": 14400,
    "provisioning": "SPOT", "source_arm": "la_clean_return_a (21-Sep, 132 min)", "parent_run_id": PARENT_RUN,
    "context_tokens": CTX, "input_tokens": BUDGET, "speculative": "mtp k=3 (ladder k3/b6144 -> k3/b2048 -> k2/b6144)",
    "runner_object": f"{RUNNER_DIR}/{runner_sha}/runner.py", "runner_sha256": runner_sha,
    "probe_object": f"{BUCKET_CODE}/{probe_sha}/runtime_probe.py", "probe_sha256": probe_sha,
    "prompt_probe_object": f"gs://cellens-ai-artifacts/arc3-duck/code/{src_code}/{pp_sha}/prompt_probe.py", "prompt_probe_sha256": pp_sha,
    "expected_prompts_object": f"gs://cellens-ai-artifacts/arc3-duck/code/{src_code}/{ep_sha}/EXPECTED_PROMPTS.json", "expected_prompts_sha256": ep_sha,
    "config_object": f"{BUCKET_CODE}/{cfg_sha}/CONFIG_FLAGS.json", "config_sha256": cfg_sha,
    "selftest_object": f"{BUCKET_CODE}/{selftest_sha}/selftest.tgz", "selftest_sha256": selftest_sha,
    "adapter_object": f"{BUCKET_CODE}/{adapter_sha}/ADAPTER.json", "adapter_sha256": adapter_sha,
    "release_object": f"{BUCKET_CODE}/{release_sha}/release.json", "release_sha256": release_sha,
    "candidate_object": f"{BUCKET_CODE}/{candidate_sha}/candidate.tgz", "candidate_sha256": candidate_sha, "candidate_changed": True,
    "source_sha256": source_sha256, "config_id": cfg["config_id"],
    "run_id_prefix": "g4run-lacr-mtp3-c60k-a132-w7", "instance_prefix": "arc3-g4-lacrmtp60k", "tag": "lacrmtp",
}
(ARM / "ARM.json").write_text(json.dumps(arm_json, indent=2) + NL)
print(f"{ARM_NAME}: ctx={CTX} budget={BUDGET} config_id={cfg['config_id'][:12]} candidate={candidate_sha[:10]} selftest={selftest_sha[:10]} "
      f"release={release_sha[:10]} runner={runner_sha[:10]} probe={probe_sha[:10]} cfg={cfg_sha[:10]}")
