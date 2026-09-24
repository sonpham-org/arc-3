"""Local preflight: reproduce every check the VM performs, before spending a VM on it.

Three attempts were lost to pins discovered one at a time (selftest bundle constants, the metrics
sampler's MAX_SECONDS, ADAPTER.json's effective_runner_sha256). This mirrors the whole chain:

  1. every `echo '<sha>  <path>' | sha256sum -c -` line in startup.sh, against the local file
  2. the effective runner hash -- the runner AFTER the startup's own soft_end patch
  3. the selftest bundle's internal cross-check (manifest env == feature_contract.environment(arm))
  4. that those env values equal what startup.sh actually exports
  5. release.json byte-identical to the bundle's release-manifest.json (the startup `cmp -s`s them)
  6. CONFIG_FLAGS config_id recomputed through the arm's own contract.py
  7. the metrics sampler's own argument bounds

Exit 0 and it is worth launching.
"""
import hashlib, json, os, re, shutil, sys, tarfile, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARM = HERE / "arms" / os.environ.get("ARC3_ARM_NAME", "compaction_v5_clean_return_" + os.environ.get("ARC3_SUITE_MINUTES", "396"))
SRC = Path(r"D:\codex-work\compaction-v5-clean-return132-20260919\arms\compaction_v5_clean_return_a")
startup = (ARM / "startup.sh").read_text(encoding="utf-8")
armcfg = json.loads((ARM / "ARM.json").read_text())
fails, checks = [], 0

def ok(cond, label):
    global checks
    checks += 1
    if not cond:
        fails.append(label)
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")

def sha_f(p: Path): return hashlib.sha256(p.read_bytes()).hexdigest()

# 1 ---------------------------------------------------------------- sha256sum -c pairs
VM_TO_LOCAL = {
    "/tmp/execution-selftest.tgz": "selftest.tgz",
    "/opt/arc3/execution-release-manifest.json": "release.json",
    "/opt/arc3/config-audit/CONFIG_FLAGS.json": "CONFIG_FLAGS.json",
    "/opt/arc3/config-audit/ADAPTER.json": "ADAPTER.json",
    "/opt/arc3/config-audit/contract.py": "contract.py",
    "/opt/arc3/config-audit/runtime_probe.py": "runtime_probe.py",
    "/opt/arc3/config-audit/prompt_probe.py": "prompt_probe.py",
    "/opt/arc3/config-audit/time_guidance_probe.py": "time_guidance_probe.py",
    "/opt/arc3/config-audit/EXPECTED_PROMPTS.json": "EXPECTED_PROMPTS.json",
    "/tmp/bundle.tgz": "candidate.tgz",
    "/opt/arc3/v12_run.py": None,          # handled in step 2: patched on the VM
}
print("1. sha256sum -c pins in startup.sh")
seen_paths = set()
for m in re.finditer(r"echo '([0-9a-f]{64})  ([^']+)' \| sha256sum -c -", startup):
    digest, vmpath = m.group(1), m.group(2)
    seen_paths.add(vmpath)
    if vmpath not in VM_TO_LOCAL:
        continue                            # unchanged GCS artifact, nothing local to compare
    local = VM_TO_LOCAL[vmpath]
    if local is None:
        continue
    f = ARM / local
    ok(f.exists() and sha_f(f) == digest, f"{local} -> {vmpath}")
for vmpath, local in VM_TO_LOCAL.items():
    if local and vmpath not in seen_paths:
        ok(False, f"{local}: startup.sh no longer pins {vmpath}")

# 2 ---------------------------------------------------------------- effective runner
print("2. effective runner (post soft_end patch)")
suite = armcfg["suite_minutes"]
raw = (ARM / "runner.py").read_text(encoding="utf-8")
old_anchor = "soft_end = datetime.now() + timedelta(hours=11, minutes=20)"
new_anchor = f"soft_end = datetime.now() + timedelta(minutes={suite})"
ok(raw.count(old_anchor) == 1, "runner carries exactly one soft_end anchor")
eff = hashlib.sha256(raw.replace(old_anchor, new_anchor).encode()).hexdigest()
adapter = json.loads((ARM / "ADAPTER.json").read_text())
ok(adapter["effective_runner_sha256"] == eff, "ADAPTER.effective_runner_sha256 == patched runner")
ok(f"'{new_anchor}'" in startup, "startup patches soft_end to the arm's suite length")
ok(f"attest(bm,target,{suite})" in (ARM / "runtime_probe.py").read_text(), "probe attests the arm's suite length")
ok(sha_f(ARM / "runner.py") == armcfg["runner_sha256"], "runner.py matches ARM.json")

# 3/4/5 ------------------------------------------------------------- selftest bundle
print("3-5. selftest bundle")
tmp = Path(tempfile.mkdtemp())
try:
    with tarfile.open(ARM / "selftest.tgz") as t:
        t.extractall(tmp)
    sys.path.insert(0, str(tmp))
    for mod in ("feature_contract",):
        sys.modules.pop(mod, None)
    import feature_contract as fc
    man = json.loads((tmp / "release-manifest.json").read_text())
    env = fc.environment(armcfg.get("feature_arm", "baseline"))
    ok(man["environment"] == env, "release-manifest.environment == feature_contract.environment()")
    ok(str(fc.GAME_SECONDS) == str(armcfg["game_seconds"]), f"feature_contract.GAME_SECONDS == {armcfg['game_seconds']}")
    ok(str(fc.SUITE_MINUTES) == str(suite), f"feature_contract.SUITE_MINUTES == {suite}")
    bad = [n for n, d in man["candidate_files"].items()
           if hashlib.sha256((tmp / "candidate" / n).read_bytes()).hexdigest() != d]
    ok(not bad, f"candidate_files intact ({len(man['candidate_files'])} files)")
    ok((ARM / "release.json").read_bytes() == (tmp / "release-manifest.json").read_bytes(),
       "release.json byte-identical to bundle manifest (startup cmp -s)")
    # 4: the env the startup exports must equal the manifest's
    for key, want in env.items():
        exported = re.search(rf"^export {re.escape(key)}=(\S+)", startup, re.M) or \
                   re.search(rf"\b{re.escape(key)}=(\S+)", startup)
        got = exported.group(1).strip('"\'') if exported else None
        ok(got == want, f"startup exports {key}={want}" + ("" if got == want else f" (got {got})"))
finally:
    sys.path.remove(str(tmp)); shutil.rmtree(tmp, ignore_errors=True)

# 6 ---------------------------------------------------------------- config receipt
print("6. config receipt")
sys.path.insert(0, str(SRC))
import contract  # noqa: E402
cfg = json.loads((ARM / "CONFIG_FLAGS.json").read_text(encoding="utf-8-sig"))
ok(contract.config_id(cfg["recipe"]) == cfg["config_id"], "config_id matches recipe")
try:
    contract.validate(cfg, for_launch=True); ok(True, "contract.validate(for_launch=True)")
except Exception as e:
    ok(False, f"contract.validate: {e}")
ok(cfg["recipe"]["limits"]["game_seconds"] == armcfg["game_seconds"], "limits.game_seconds")
ok(cfg["recipe"]["limits"]["suite_gameplay_minutes"] == suite, "limits.suite_gameplay_minutes")
ok(cfg["recipe"]["limits"]["vm_lifetime_seconds"] == armcfg["vm_lifetime_seconds"], "limits.vm_lifetime_seconds")

# 6b --------------------------------------------------------------- game count / subset
print("6b. game count and subset")
games = armcfg.get("games", 25)
ok(cfg["recipe"]["limits"]["games"] == games, f"limits.games == {games}")
ok(f"assert len(game_ids) == {games}" in (ARM / "runner.py").read_text(encoding="utf-8"), f"runner asserts {games} games")
subset = armcfg.get("subset", "")
ok(f'ARC3_GAME_SUBSET="{subset}"' in startup, f"startup exports ARC3_GAME_SUBSET={subset!r}")
ok(cfg["recipe"]["extra_environment"].get("ARC3_GAME_SUBSET", "") == subset, "CONFIG extra_environment subset matches")
if games != 25:
    ok(armcfg["game_seconds"] == armcfg["suite_minutes"] * 60, "one wave: game_seconds == suite_minutes*60")

# 6c --------------------------------------------------------------- harness arm (features, ablations, prompts, candidate)
if "harness_arm" in armcfg:
    print("6c. harness arm:", armcfg["harness_arm"])
    import subprocess, io
    FEATURE_ENV = {"memory": "ARC3_PERSISTENT_GAME_MODEL", "execution": "ARC3_EXECUTION_MODE",
                   "symbolic": "ARC3_SYMBOLIC_SEARCH", "workspace": "ARC3_PROGRAMMATIC_WORKSPACE"}
    ABLATION_ENV = {a: "ARC3_PROMPT_ABLATE_" + a.upper() for a in ("view", "loop", "search", "coords", "priors", "transition")}
    xenv = cfg["recipe"]["extra_environment"]
    for feat, envk in FEATURE_ENV.items():
        want = "1" if feat == armcfg["feature_arm"] else "0"   # single-switch env; memory is implied for execution/symbolic
        implied = feat in armcfg["features"] and feat != armcfg["feature_arm"]
        ok(f"export {envk}={want}" in startup and (envk not in xenv if implied else xenv.get(envk) == want),
           f"{envk}={want} exported" + (" and omitted from CONFIG (implied)" if implied else " and in CONFIG"))
    for abl, envk in ABLATION_ENV.items():
        want = "1" if abl in armcfg["ablations"] else "0"
        ok(xenv.get(envk) == want and f"export {envk}={want}" in startup, f"{envk}={want} in CONFIG and startup")
    fa = armcfg["feature_arm"]
    ok(f"--live --arm {fa} --model" in startup and f"'{fa}')" in startup, f"selftest --arm {fa} and assert_contract('{fa}')")
    ok(f"sum(flags.values()) == {len(armcfg['ablations'])}" in (ARM / "prompt_probe.py").read_text(), f"prompt_probe expects {len(armcfg['ablations'])} ablation flag(s)")
    mem = "memory" in armcfg["features"]
    ok(("assert probe['memory_write']" in (ARM / "runtime_probe.py").read_text()) == mem, "runtime_probe memory_write assertion matches memory flag")
    ok(cfg["recipe"]["flags"]["memory"] == mem and cfg["recipe"]["flags"]["reasoning_router"] == mem and cfg["recipe"]["flags"]["rule_preservation"] == mem, "CONFIG flags memory/reasoning_router/rule_preservation consistent")
    ok(cfg["recipe"]["flags"]["execution"] == ("execution" in armcfg["features"]) and cfg["recipe"]["flags"]["symbolic"] == ("symbolic" in armcfg["features"]), "CONFIG execution/symbolic flags match arm")
    ok(f"test \"$(meta arc3-execution-mode)\" = {int('execution' in armcfg['features'])}" in startup, "startup metadata gate arc3-execution-mode")
    ok(f"test \"$(meta arc3-symbolic-search)\" = {int('symbolic' in armcfg['features'])}" in startup, "startup metadata gate arc3-symbolic-search")
    # candidate bundle vs manifest vs CONFIG.source_sha256
    ok(sha_f(ARM / "candidate.tgz") == armcfg["candidate_sha256"] and f"echo '{armcfg['candidate_sha256']}  /tmp/bundle.tgz'" in startup, "candidate.tgz sha pinned in startup")
    man = json.loads((ARM / "release.json").read_text())
    tmpc = Path(tempfile.mkdtemp())
    try:
        with tarfile.open(ARM / "candidate.tgz") as t: t.extractall(tmpc)
        bad = [n for n, d in man["candidate_files"].items() if hashlib.sha256((tmpc / n).read_bytes()).hexdigest() != d]
        ok(not bad, f"manifest candidate_files match candidate.tgz contents ({len(man['candidate_files'])} files)")
        badi = [n for n, d in man["implementation"]["candidate_source_sha256"].items() if hashlib.sha256((tmpc / n).read_bytes()).hexdigest() != d]
        ok(not badi, "manifest implementation.candidate_source_sha256 match candidate.tgz")
        if armcfg["patched_candidate"]:
            ok(man["candidate_bundle_sha256"] == armcfg["candidate_sha256"], "manifest.candidate_bundle_sha256 == patched candidate.tgz")
            ok("def expect(check)" in (tmpc / "src/ARC3-Inference/inference/agent/python_tool_sandbox.py").read_text(encoding="utf-8"), "patched sandbox carries expect()")
        encj = lambda x: (json.dumps(x, sort_keys=True, indent=2) + chr(10)).encode()
        ok(cfg["recipe"]["source_sha256"] == hashlib.sha256(encj(man["candidate_files"])).hexdigest(), "CONFIG.source_sha256 == sha(enc(manifest.candidate_files)) (runtime_probe formula)")
        # EXPECTED_PROMPTS must equal a fresh render from THIS candidate under THIS env
        code = r"""
import sys, os, json, ast
sys.path.insert(0, sys.argv[1])
from inference.agent import tool_agent as ta, prompt_ablation as pa
a = ta.ToolAgent()
out = {'system': a._system_prompt, 'tool': ta._python_tool_description(),
       'first_user': a._build_user_prompt(0, valid_actions=['MOUSE','RIGHT']), 'user': a._build_user_prompt(1, valid_actions=['MOUSE','RIGHT'])}
tree = ast.parse(open(ta.__file__, encoding='utf-8').read())
exprs = [n.value for n in ast.walk(tree) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'followup_prompt' for t in n.targets) and isinstance(n.value, ast.JoinedStr)]
scope = dict(vars(ta), followup_prefix='You have not acted yet. Investigate first. ')
out['retry'] = pa.transform(eval(compile(ast.Expression(exprs[0]), 'r', 'eval'), scope), 'retry')
print("@@P@@" + json.dumps(out))
"""
        renv = dict(os.environ); renv.update(xenv)
        renv.update({"LOCAL_ANALYZER_MODEL_ID": cfg["recipe"]["model"]["id"], "INFERENCE_ANALYZER_MODEL": cfg["recipe"]["model"]["id"], "LOCAL_ANALYZER_PROVIDER": "vllm",
                     "OPENAI_PROVIDER": "vllm", "LOCAL_ANALYZER_BASE_URL": "http://127.0.0.1:1234/v1", "OPENAI_BASE_URL": "http://127.0.0.1:1234/v1", "ARC3_ROLLING_HALF_CHECKPOINT": "0"})
        pr = subprocess.run([sys.executable, "-c", code, str(tmpc / "src/ARC3-Inference")], capture_output=True, text=True, env=renv, timeout=300)
        lines = [l for l in pr.stdout.splitlines() if l.startswith("@@P@@")]
        fresh = json.loads(lines[-1][5:]) if lines else None
        expected = json.loads((ARM / "EXPECTED_PROMPTS.json").read_text(encoding="utf-8-sig"))
        ok(fresh is not None and fresh == expected, "EXPECTED_PROMPTS.json == fresh local render of this candidate under the arm env")
        if fresh and fresh != expected:
            print("     differing surfaces:", [k for k in expected if fresh.get(k) != expected[k]])
    finally:
        shutil.rmtree(tmpc, ignore_errors=True)
    for key, local in (("prompt_probe_sha256", "prompt_probe.py"), ("expected_prompts_sha256", "EXPECTED_PROMPTS.json")):
        ok(sha_f(ARM / local) == armcfg[key] and armcfg[key] in startup, f"{local} sha matches ARM.json and is pinned in startup")

# 7 ---------------------------------------------------------------- sampler bounds
print("7. metrics sampler bounds (its own MAX_SECONDS = 5*3600, interval in {30,60})")
m = re.search(r"--interval-seconds (\d+) --max-seconds (\d+)", startup)
ok(m is not None, "sampler invocation present")
if m:
    ok(int(m.group(1)) in (30, 60), f"interval {m.group(1)} in (30, 60)")
    ok(1 <= int(m.group(2)) <= 18000, f"max-seconds {m.group(2)} within 1..18000")
# the hard-cost guard's sleep, not any other sleep in the script
mm = re.search(r"# Hard cost guard: (\d+) seconds[\s\S]{0,200}?\n  sleep (\d+)\n", startup)
ok(mm and mm.group(1) == mm.group(2) == str(armcfg["vm_lifetime_seconds"]),
   f"hard-cost-guard sleep == VM lifetime ({armcfg['vm_lifetime_seconds']})"
   + ("" if mm else " -- guard block not found"))

print(f"\n{checks - len(fails)}/{checks} checks passed")
if fails:
    print("FAILED:"); [print("  -", f) for f in fails]; sys.exit(1)
print("preflight OK - safe to launch")
