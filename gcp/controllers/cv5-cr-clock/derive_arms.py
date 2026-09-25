"""Five intensive-harness arms on the hard seven, one wave, one full 132-minute clock per game.

Son, 24-Sep: (1) the ablation paper's full stack, (2) a simpler version, (3) a simpler executable world
model, (4) a solver-only harness, (5) prediction-checked actions where the model writes a substantial check.
"Measure on the 7 hard games only. Give 7 games all of 132 mins. Scale per-game limit accordingly."

All five derive from the 19-Sep compaction_v5_clean_return_a arm. 7 lanes x 7 games = one wave, so
game_seconds = 132*60 = 7920 (3.8x the 25-game 2061), suite 132, VM 14400. Everything not named below
is byte-identical to that arm.

  arm         feature flags (contract)          prompt ablations   candidate code
  execution   memory + execution (E2 lease)     SEARCH             unchanged   <- (1) verification: predeclared
                                                                                   expected_next checked vs frame,
                                                                                   mismatch leaves the lease
  memory      memory                            SEARCH             unchanged   <- (2) simpler: semantic memory only
  symbolic    memory + symbolic (v2)            SEARCH             unchanged   <- (3) simpler executable WM: declarative
                                                                                   scalar-state model, CPU search,
                                                                                   validated on observed transitions
  solver      none                              SEARCH+LOOP+PRIORS+TRANSITION+COORDS  unchanged
                                                                               <- (4) act toward the goal; the
                                                                                   observe-plan-act loop, world-model
                                                                                   keeping, priors, transition
                                                                                   inspection and coordinate framing
                                                                                   all deleted from the prompt
  selfcheck   none                              SEARCH             patch_selfcheck.py <- (5) expect(check) before
                                                                                   every action; host runs it on the
                                                                                   real transition AND a no-op
                                                                                   counterfactual; trivial/failed
                                                                                   checks halt the batch

Six pinned places move per arm (runner, runtime_probe, CONFIG_FLAGS/config_id, selftest bundle constants
+ manifest env, ADAPTER effective-runner hash, startup pins) plus, per arm: feature flags in env / CONFIG /
probe / startup asserts / selftest `--arm`; prompt_probe's single-ablation count for `solver`;
EXPECTED_PROMPTS re-rendered locally (the renderer reproduces the shipped attestation byte-for-byte);
and for `selfcheck` the candidate bundle itself (three constant-only edits) with the full manifest and
source_sha256 cascade in both candidate.tgz and the selftest bundle's candidate/ copy.

Usage:  python derive_arms.py execution|memory|symbolic|solver|selfcheck [--suite 132]
"""
import argparse, ast, hashlib, io, json, os, re, shutil, subprocess, sys, tarfile, uuid
from watchdog import add_watchdog
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(r"D:\codex-work\compaction-v5-clean-return132-20260919\arms\compaction_v5_clean_return_a")
BUCKET_CODE = "gs://cellens-ai-artifacts/arc3-duck/code/cap-compact132"
RUNNER_DIR = "gs://cellens-ai-artifacts/arc3-duck/code/astra-execution/feature-ablation-132-v1"
BASE_RUNNER_SHA = "b3604c7731dde84089cfc20bbf1366378eb0791c5deb88c9e24271ac5b9f53bb"
HARD7 = ["bp35", "g50t", "lf52", "ls20", "sk48", "tn36", "wa30"]
SUBSET = ",".join(HARD7)
NL = chr(10)
FEATURE_ENV = {"memory": "ARC3_PERSISTENT_GAME_MODEL", "execution": "ARC3_EXECUTION_MODE",
               "symbolic": "ARC3_SYMBOLIC_SEARCH", "workspace": "ARC3_PROGRAMMATIC_WORKSPACE"}
ABLATION_ENV = {a: "ARC3_PROMPT_ABLATE_" + a.upper() for a in ("view", "loop", "search", "coords", "priors", "transition")}

ARMS = {
    "execution": dict(features={"memory", "execution"}, execution_version="memory_lease_e2", symbolic_version="none",
                      ablations={"search"}, patch_candidate=False, feature_arm="execution"),
    "memory":    dict(features={"memory"}, execution_version="none", symbolic_version="none",
                      ablations={"search"}, patch_candidate=False, feature_arm="memory"),
    "symbolic":  dict(features={"memory", "symbolic"}, execution_version="none", symbolic_version="v2",
                      ablations={"search"}, patch_candidate=False, feature_arm="symbolic"),
    "solver":    dict(features=set(), execution_version="none", symbolic_version="none",
                      ablations={"search", "loop", "priors", "transition", "coords"}, patch_candidate=False, feature_arm="baseline"),
    "selfcheck": dict(features=set(), execution_version="none", symbolic_version="none",
                      ablations={"search"}, patch_candidate=True, feature_arm="baseline"),
    # control (25-Sep): the base harness itself on the hard-seven one-wave schedule, so the schedule effect
    # and the arm effect can be separated. NOTE: the 19-Sep base has ARC3_PROMPT_ABLATE_SEARCH=1 already
    # (search/scorer removal is part of clean-return), so "no ablation beyond the base" is ablations={"search"}.
    "baseline":  dict(features=set(), execution_version="none", symbolic_version="none",
                      ablations={"search"}, patch_candidate=False, feature_arm="baseline"),
    # v2 (24-Sep, "reuse the flag but have your own take"): same flags as the arm above each, plus patch_v2.py's
    # per-game code store and one executable, history-replayed verification primitive (see patch_v2.py docstring).
    "execution_v2": dict(features={"memory", "execution"}, execution_version="memory_lease_e2", symbolic_version="none",
                         ablations={"search"}, patch_candidate="execution_v2", feature_arm="execution"),
    "memory_v2":    dict(features={"memory"}, execution_version="none", symbolic_version="none",
                         ablations={"search"}, patch_candidate="memory_v2", feature_arm="memory"),
    "symbolic_v2":  dict(features={"memory", "symbolic"}, execution_version="none", symbolic_version="v2",
                         ablations={"search"}, patch_candidate="symbolic_v2", feature_arm="symbolic"),
}

def sha_b(b: bytes) -> str: return hashlib.sha256(b).hexdigest()
def sub1(pat, repl, text, flags=0):
    new, n = re.subn(pat, repl, text, count=1, flags=flags)
    assert n == 1, f"expected exactly one match for: {pat[:90]}"
    return new
def enc(x) -> bytes: return (json.dumps(x, sort_keys=True, indent=2) + NL).encode()
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

def render_prompts(candidate_src: Path, env: dict) -> dict:
    """Render the five attested surfaces exactly as prompt_probe.attest_prompt does, in a clean subprocess."""
    code = r'''
import sys, os, json, ast
sys.path.insert(0, sys.argv[1])
from inference.agent import tool_agent as ta, prompt_ablation as pa
a = ta.ToolAgent()
out = {'system': a._system_prompt,
       'tool': ta._python_tool_description(),
       'first_user': a._build_user_prompt(0, valid_actions=['MOUSE','RIGHT']),
       'user': a._build_user_prompt(1, valid_actions=['MOUSE','RIGHT'])}
tree = ast.parse(open(ta.__file__, encoding='utf-8').read())
exprs = [n.value for n in ast.walk(tree) if isinstance(n, ast.Assign)
         and any(isinstance(t, ast.Name) and t.id == 'followup_prompt' for t in n.targets) and isinstance(n.value, ast.JoinedStr)]
assert len(exprs) == 1
scope = dict(vars(ta), followup_prefix='You have not acted yet. Investigate first. ')
out['retry'] = pa.transform(eval(compile(ast.Expression(exprs[0]), 'r', 'eval'), scope), 'retry')
print("@@PROMPTS@@" + json.dumps(out))
'''
    full_env = dict(os.environ); full_env.update(env)
    p = subprocess.run([sys.executable, "-c", code, str(candidate_src)], capture_output=True, text=True, env=full_env, timeout=300)
    lines = [l for l in p.stdout.splitlines() if l.startswith("@@PROMPTS@@")]
    assert lines, "prompt render failed:" + NL + p.stderr[-1500:]
    return json.loads(lines[-1][len("@@PROMPTS@@"):])

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("arm", choices=sorted(ARMS)); ap.add_argument("--suite", type=int, default=132)
    ap.add_argument("--all25", action="store_true", help="all 25 games on the normal 4-wave schedule instead of the hard seven in one wave")
    ap.add_argument("--effort", default=None, choices=["low", "medium", "high", "xhigh"], help="Qwen3.8 chat-template reasoning_effort (template default xhigh)")
    args = ap.parse_args()
    spec = ARMS[args.arm]; SUITE_MIN = args.suite; assert SUITE_MIN % 132 == 0
    MULT = SUITE_MIN // 132; VM_LIFE = {1: 14400, 2: 21600, 3: 28800}[MULT]; SAMPLER_MAX = min(VM_LIFE, 18000)
    ALL25 = bool(args.all25)
    GAME_S = 2061 * MULT if ALL25 else SUITE_MIN * 60          # 4 waves of ~34 min x MULT, or one wave with the whole clock
    GAMES = 25 if ALL25 else len(HARD7); SUBSET_ = "" if ALL25 else SUBSET; SCOPE = "all25" if ALL25 else "hard7"
    EFFORT = args.effort
    ARM_NAME = f"cv5cr_{SCOPE}_{args.arm}_{SUITE_MIN}" + (f"_effort_{EFFORT}" if EFFORT else "")
    ARM = HERE / "arms" / ARM_NAME; ARM.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(SRC)); import contract  # noqa

    # -------------------------------------------------- source files (fresh copies every derive)
    for f in ("contract.py", "prompt_probe.py", "time_guidance_probe.py", "instance-body.json"):
        shutil.copy(SRC / f, ARM / f)
    if not (ARM / "runner.py").exists() or sha_b((ARM / "runner.py").read_bytes()) != BASE_RUNNER_SHA:
        subprocess.run(["gcloud", "storage", "cp", f"{RUNNER_DIR}/{BASE_RUNNER_SHA}/runner.py", str(ARM / "runner.py")],
                       check=True, capture_output=True, shell=(os.name == "nt"),
                       env=dict(os.environ, CLOUDSDK_PYTHON=os.environ.get("CLOUDSDK_PYTHON", r"C:\python312\python.exe")))
    assert sha_b((ARM / "runner.py").read_bytes()) == BASE_RUNNER_SHA

    # -------------------------------------------------- candidate bundle (patched only for selfcheck)
    work = HERE / f"_work_{ARM_NAME}"
    if work.exists(): shutil.rmtree(work)
    cand_dir = work / "candidate"; cand_dir.mkdir(parents=True)
    with tarfile.open(SRC / "candidate.tgz") as t:
        cand_names = t.getnames(); t.extractall(cand_dir)
    if spec["patch_candidate"] is True:
        sys.path.insert(0, str(HERE)); import patch_selfcheck
        patch_selfcheck.apply(cand_dir / "src" / "ARC3-Inference")
        candidate_bytes = repack(cand_dir, cand_names)
    elif spec["patch_candidate"]:
        sys.path.insert(0, str(HERE)); import patch_v2
        patch_v2.apply(cand_dir / "src" / "ARC3-Inference", spec["patch_candidate"])
        candidate_bytes = repack(cand_dir, cand_names)
    else:
        candidate_bytes = (SRC / "candidate.tgz").read_bytes()
    (ARM / "candidate.tgz").write_bytes(candidate_bytes); candidate_sha = sha_b(candidate_bytes)
    old_candidate_sha = sha_b((SRC / "candidate.tgz").read_bytes())
    candidate_src = cand_dir / "src" / "ARC3-Inference"

    # -------------------------------------------------- selftest bundle
    st_dir = work / "selftest"; st_dir.mkdir()
    with tarfile.open(SRC / "selftest.tgz") as t:
        st_names = t.getnames(); t.extractall(st_dir)
    fc = st_dir / "feature_contract.py"; x = fc.read_text(encoding="utf-8")
    x = sub1(r"^GAME_SECONDS = 2061$", f"GAME_SECONDS = {GAME_S}", x, re.M)
    x = sub1(r"^SUITE_MINUTES = 132$", f"SUITE_MINUTES = {SUITE_MIN}", x, re.M)
    fc.write_text(x, encoding="utf-8", newline=NL)
    man = json.loads((st_dir / "release-manifest.json").read_text(encoding="utf-8"))
    man["environment"]["ARC3_MAX_RUNTIME_S_PER_GAME"] = str(GAME_S)
    man["environment"]["ARC3_MAX_RUN_RUNTIME_MINUTES"] = str(SUITE_MIN)
    for feat, envk in FEATURE_ENV.items():   # single-switch: only the selected arm's own flag is 1 (feature_contract.environment)
        man["environment"][envk] = "1" if feat == spec["feature_arm"] else "0"
    if spec["patch_candidate"]:
        # mirror the patched sources into the selftest's candidate/ copy and re-hash the manifest
        for name in man["candidate_files"]:
            src_f = cand_dir / name; dst_f = st_dir / "candidate" / name
            if src_f.read_bytes() != dst_f.read_bytes():
                dst_f.write_bytes(src_f.read_bytes())
            man["candidate_files"][name] = sha_b(src_f.read_bytes())
        for name in list(man["implementation"]["candidate_source_sha256"]):
            man["implementation"]["candidate_source_sha256"][name] = sha_b((cand_dir / name).read_bytes())
        man["candidate_bundle_sha256"] = candidate_sha
        man["source_tree_sha256"] = sha_b(enc(man["candidate_files"]))
    source_sha256 = sha_b(enc(man["candidate_files"]))   # == runtime_probe's sha(enc(actual))
    manifest_bytes = enc(man)
    (st_dir / "release-manifest.json").write_bytes(manifest_bytes); (ARM / "release.json").write_bytes(manifest_bytes)
    release_sha = sha_b(manifest_bytes); old_release_sha = sha_b((SRC / "release.json").read_bytes())
    selftest_bytes = repack(st_dir, st_names); (ARM / "selftest.tgz").write_bytes(selftest_bytes)
    selftest_sha = sha_b(selftest_bytes); old_selftest_sha = sha_b((SRC / "selftest.tgz").read_bytes())

    # -------------------------------------------------- runner.py
    r = (ARM / "runner.py").read_text(encoding="utf-8")
    r = sub1(r"assert bm\.solver\.max_runtime_s_per_game == 2061\.0", f"assert bm.solver.max_runtime_s_per_game == {GAME_S}.0", r)
    r = sub1(r'"Experimental runtime lock: 7 workers, 2061 seconds/game, "', f'"Experimental runtime lock: 7 workers, {GAME_S} seconds/game, {SCOPE} {args.arm} arm, "', r)
    if not ALL25:
        r = sub1(r'assert len\(game_ids\) == 25, f"experiment requires 25 games, got \{len\(game_ids\)\}"',
                 f'assert len(game_ids) == {len(HARD7)}, f"hard-seven experiment requires {len(HARD7)} games, got {{len(game_ids)}}"', r)
    r = sub1(r"# 4 waves at 2061 seconds/game fit the 132-minute suite.*",
             f"# 4 waves at {GAME_S} seconds/game fit the {SUITE_MIN}-minute suite." if ALL25 else f"# One wave: 7 lanes x 7 hard games, {GAME_S} s each = the whole {SUITE_MIN}-minute suite per game.", r)
    (ARM / "runner.py").write_text(r, encoding="utf-8", newline=NL); runner_sha = sha_b((ARM / "runner.py").read_bytes())

    # -------------------------------------------------- runtime_probe.py
    p = (SRC / "runtime_probe.py").read_text(encoding="utf-8")
    p = sub1(r"'vm_lifetime_seconds':14400", f"'vm_lifetime_seconds':{VM_LIFE}", p)
    p = sub1(r"original 14400-second", f"original {VM_LIFE}-second", p)
    p = sub1(r"anchor='soft_end = datetime\.now\(\) \+ timedelta\(minutes=132\)'", f"anchor='soft_end = datetime.now() + timedelta(minutes={SUITE_MIN})'", p)
    p = sub1(r"attest\(bm,target,132\)", f"attest(bm,target,{SUITE_MIN})", p)
    if "memory" in spec["features"]:
        p = sub1(r"assert not probe\['memory_write'\]", "assert probe['memory_write']", p)   # remember() is accepted when memory is on
    (ARM / "runtime_probe.py").write_text(p, encoding="utf-8", newline=NL)
    probe_sha = sha_b((ARM / "runtime_probe.py").read_bytes()); old_probe_sha = sha_b((SRC / "runtime_probe.py").read_bytes())

    # -------------------------------------------------- prompt_probe.py (single-ablation count)
    pp = (ARM / "prompt_probe.py").read_text(encoding="utf-8")
    pp = sub1(r"sum\(flags\.values\(\)\) == 1", f"sum(flags.values()) == {len(spec['ablations'])}", pp)
    (ARM / "prompt_probe.py").write_text(pp, encoding="utf-8", newline=NL)
    pprobe_sha = sha_b((ARM / "prompt_probe.py").read_bytes()); old_pprobe_sha = sha_b((SRC / "prompt_probe.py").read_bytes())

    # -------------------------------------------------- CONFIG_FLAGS.json
    cfg = json.loads((SRC / "CONFIG_FLAGS.json").read_text(encoding="utf-8-sig")); rec = cfg["recipe"]
    rec["limits"].update({"game_seconds": GAME_S, "suite_gameplay_minutes": SUITE_MIN, "vm_lifetime_seconds": VM_LIFE, "games": GAMES})
    rec["extra_environment"].update({"ARC3_MAX_RUNTIME_S_PER_GAME": str(GAME_S), "ARC3_MAX_RUN_RUNTIME_MINUTES": str(SUITE_MIN), "ARC3_GAME_SUBSET": SUBSET_})
    for feat, envk in FEATURE_ENV.items():
        # contract.validate: an env override present in extra_environment must equal str(int(flags[feat])).
        # The single-switch env sets only the arm's own flag, so a feature that is IMPLIED (memory under
        # execution/symbolic: flag True, env 0) must be omitted from extra_environment rather than contradict it.
        implied = feat in spec["features"] and feat != spec["feature_arm"]
        if implied: rec["extra_environment"].pop(envk, None)
        else: rec["extra_environment"][envk] = "1" if feat == spec["feature_arm"] else "0"
    for abl, envk in ABLATION_ENV.items():
        rec["extra_environment"][envk] = "1" if abl in spec["ablations"] else "0"
    if spec["patch_candidate"] is True:
        rec["extra_environment"]["ARC3_PREDICTION_CHECK"] = "1"   # exported after the selftest matrix (see startup)
    elif spec["patch_candidate"]:
        rec["extra_environment"]["ARC3_V2_BATCH_GATE"] = "1"      # v2 arms: same placement, gates multi-action batches
    if EFFORT: rec["extra_environment"]["ARC3_SERVING_REASONING_EFFORT"] = EFFORT   # recorded so config_id changes; applied via chat-template kwargs
    mem = "memory" in spec["features"]
    flag_updates = {"memory": mem, "execution": "execution" in spec["features"], "symbolic": "symbolic" in spec["features"],
                    "workspace": False, "reasoning_router": mem, "rule_preservation": mem}   # runtime_probe derives these from agent state
    rec["flags"].update(flag_updates); cfg["requested_flags"].update(flag_updates)
    rec["execution_version"] = spec["execution_version"]; rec["symbolic_version"] = spec["symbolic_version"]
    rec["source_sha256"] = source_sha256
    rec["source_family"] = rec["source_family"].replace("clean_return_a_v1", f"clean_return_{SCOPE}_{args.arm}_v1")
    cfg["run_id"] = f"g4run-cv5cr-{SCOPE}-{args.arm}-{SUITE_MIN}" + (f"-effort{EFFORT}" if EFFORT else "") + "-w7-20260925"
    cand_note = ("PATCHED by patch_selfcheck.py (expect(check) before every action; host verifies the check on the real "
                 "transition and a no-op counterfactual)" if spec["patch_candidate"] is True else
                 f"PATCHED by patch_v2.py arm {spec['patch_candidate']} (per-game code store; "
                 + {"execution_v2": "verify(predict) history replay, auto-checked actions, verified-model batch gate",
                    "memory_v2": "rule(id, text, holds) evidence-linked rules replayed each snippet, first counterexample revokes",
                    "symbolic_v2": "encode/step executable model, replay() fidelity, bounded plan() BFS, auto-checked actions"}[spec["patch_candidate"]]
                 + ")" if spec["patch_candidate"] else "byte-identical to the 19-Sep arm")
    cfg["evidence"]["notes"] = [
        (f"September25 user: '{args.arm}' arm on all 25 games, the normal 4-wave schedule, {GAME_S} s per game, {SUITE_MIN}-minute suite. " if ALL25 else
         f"September24 user: five intensive-harness arms measured on the hard seven only, one wave, the whole {SUITE_MIN}-minute "
         f"clock per game ({GAME_S} s). ") + f"This is the '{args.arm}' arm: features={sorted(spec['features']) or ['none']}, prompt "
        f"ablations={sorted(spec['ablations'])}, candidate {cand_note}. "
        "Base: compaction_v5_clean_return_a (most hard-seven-efficient 132-minute arm in the 23-Sep census). Spot. One attempt.",
    ] + cfg["evidence"]["notes"][1:]
    cfg["config_id"] = contract.config_id(rec); contract.validate(cfg, for_launch=True)
    cfg_bytes = (json.dumps(cfg, indent=2) + NL).encode(); (ARM / "CONFIG_FLAGS.json").write_bytes(cfg_bytes)
    cfg_sha = sha_b(cfg_bytes); old_cfg_sha = sha_b((SRC / "CONFIG_FLAGS.json").read_bytes())

    # -------------------------------------------------- EXPECTED_PROMPTS.json (local render, same env the VM exports)
    render_env = dict(rec["extra_environment"])
    render_env.update({"LOCAL_ANALYZER_MODEL_ID": rec["model"]["id"], "INFERENCE_ANALYZER_MODEL": rec["model"]["id"],
                       "LOCAL_ANALYZER_PROVIDER": "vllm", "OPENAI_PROVIDER": "vllm", "LOCAL_ANALYZER_BASE_URL": "http://127.0.0.1:1234/v1",
                       "OPENAI_BASE_URL": "http://127.0.0.1:1234/v1", "ARC3_ROLLING_HALF_CHECKPOINT": "0"})
    prompts = render_prompts(candidate_src, render_env)
    old_prompts = json.loads((SRC / "EXPECTED_PROMPTS.json").read_text(encoding="utf-8-sig"))
    prompts_bytes = (json.dumps(prompts, indent=2) + NL).encode(); (ARM / "EXPECTED_PROMPTS.json").write_bytes(prompts_bytes)
    prompts_sha = sha_b(prompts_bytes); old_prompts_sha = sha_b((SRC / "EXPECTED_PROMPTS.json").read_bytes())
    changed_surfaces = sorted(k for k in prompts if prompts[k] != old_prompts.get(k))

    # -------------------------------------------------- ADAPTER.json
    old_anchor = "soft_end = datetime.now() + timedelta(hours=11, minutes=20)"; new_anchor = f"soft_end = datetime.now() + timedelta(minutes={SUITE_MIN})"
    assert r.count(old_anchor) == 1
    adapter = json.loads((SRC / "ADAPTER.json").read_text(encoding="utf-8-sig"))
    adapter["effective_runner_sha256"] = sha_b(r.replace(old_anchor, new_anchor).encode())
    adapter["experiment_arm"] = ARM_NAME
    adapter_bytes = enc(adapter); (ARM / "ADAPTER.json").write_bytes(adapter_bytes)
    adapter_sha = sha_b(adapter_bytes); old_adapter_sha = sha_b((SRC / "ADAPTER.json").read_bytes())

    # -------------------------------------------------- startup.sh
    s = (SRC / "startup.sh").read_text(encoding="utf-8")
    s = sub1(r"^# Search/scorer removal \+ 50% swap, W7, 132 minutes", f"# compaction v5 clean-return, {'ALL 25, 4 waves' if ALL25 else 'HARD SEVEN, one wave'}, arm={args.arm}, W7, {SUITE_MIN} minutes", s, re.M)
    s = sub1(r"# Hard cost guard: 14400 seconds", f"# Hard cost guard: {VM_LIFE} seconds", s)
    s = sub1(r"^  sleep 14400$", f"  sleep {VM_LIFE}", s, re.M)
    s = sub1(r"--interval-seconds 30 --max-seconds 14400", f"--interval-seconds 30 --max-seconds {SAMPLER_MAX}", s)
    s = sub1(r"echo '" + BASE_RUNNER_SHA + r"  /opt/arc3/v12_run\.py'", f"echo '{runner_sha}  /opt/arc3/v12_run.py'", s)
    s = sub1(r"new = 'soft_end = datetime\.now\(\) \+ timedelta\(minutes=132\)'", f"new = '{new_anchor}'", s)
    s = sub1(r"grep -F 'soft_end = datetime\.now\(\) \+ timedelta\(minutes=132\)'", f"grep -F '{new_anchor}'", s)
    s = sub1(r"echo '" + old_candidate_sha + r"  /tmp/bundle\.tgz'", f"echo '{candidate_sha}  /tmp/bundle.tgz'", s)
    s = sub1(r"export ARC3_MAX_RUNTIME_S_PER_GAME=2061", f"export ARC3_MAX_RUNTIME_S_PER_GAME={GAME_S}", s)
    s = sub1(r"export ARC3_MAX_RUN_RUNTIME_MINUTES=132", f"export ARC3_MAX_RUN_RUNTIME_MINUTES={SUITE_MIN}", s)
    if not ALL25: s = sub1(r'ARC3_GAME_SUBSET=""', f'ARC3_GAME_SUBSET="{SUBSET}"', s)
    for feat, envk in FEATURE_ENV.items():
        v = "1" if feat == spec["feature_arm"] else "0"
        s = sub1(rf"export {envk}=0", f"export {envk}={v}", s)
        s = sub1(rf"assert os\.environ\['{envk}'\] == '0'", f"assert os.environ['{envk}'] == '{v}'", s)
    for abl, envk in ABLATION_ENV.items():
        v = "1" if abl in spec["ablations"] else "0"
        s = sub1(rf"export {envk}=\d", f"export {envk}={v}", s)
    if "memory" in spec["features"]:
        s = sub1(r"assert \(agent\._execution_mode is not None\) == False", "assert (agent._execution_mode is not None) == True", s)
    if "symbolic" in spec["features"]:
        s = sub1(r"assert agent\._symbolic_search_enabled is False", "assert agent._symbolic_search_enabled is True", s)
    s = sub1(r"--live --arm baseline --model", f"--live --arm {spec['feature_arm']} --model", s)
    s = sub1(r"assert_contract\(agent, Path\(tmp\) / \"state\.json\", 'baseline'\)", f"assert_contract(agent, Path(tmp) / \"state.json\", '{spec['feature_arm']}')", s)
    s = sub1(r'print\("verified feature arm baseline; no curator; 132-minute suite"\)', f'print("verified feature arm {spec["feature_arm"]} ({args.arm}); no curator; {SUITE_MIN}-minute suite, hard seven only")', s)
    s = sub1(r"assert os\.environ\['ARC3_MAX_RUNTIME_S_PER_GAME'\] == '2061'", f"assert os.environ['ARC3_MAX_RUNTIME_S_PER_GAME'] == '{GAME_S}'", s)
    s = sub1(r"assert os\.environ\['ARC3_MAX_RUN_RUNTIME_MINUTES'\] == '132'", f"assert os.environ['ARC3_MAX_RUN_RUNTIME_MINUTES'] == '{SUITE_MIN}'", s)
    # metadata gates the startup itself asserts
    s = sub1(r'test "\$\(meta arc3-symbolic-search\)" = 0', f'test "$(meta arc3-symbolic-search)" = {int("symbolic" in spec["features"])}', s)
    s = sub1(r'test "\$\(meta arc3-execution-mode\)" = 0', f'test "$(meta arc3-execution-mode)" = {int("execution" in spec["features"])}', s)
    for old, new, fn in ((old_probe_sha, probe_sha, "runtime_probe.py"), (old_cfg_sha, cfg_sha, "CONFIG_FLAGS.json"),
                         (old_adapter_sha, adapter_sha, "ADAPTER.json"), (old_pprobe_sha, pprobe_sha, "prompt_probe.py"),
                         (old_prompts_sha, prompts_sha, "EXPECTED_PROMPTS.json")):
        s = sub1(re.escape(f"{BUCKET_CODE}/{old}/{fn}"), f"{BUCKET_CODE}/{new}/{fn}", s)
        s = sub1(re.escape(f"echo '{old}  /opt/arc3/config-audit/{fn}'"), f"echo '{new}  /opt/arc3/config-audit/{fn}'", s)
    s = sub1(re.escape(f"echo '{old_selftest_sha}  /tmp/execution-selftest.tgz'"), f"echo '{selftest_sha}  /tmp/execution-selftest.tgz'", s)
    s = sub1(re.escape(f"echo '{old_release_sha}  /opt/arc3/execution-release-manifest.json'"), f"echo '{release_sha}  /opt/arc3/execution-release-manifest.json'", s)
    if spec["patch_candidate"] is True:
        # after EVERY bundled selftest (test_action_cap_modes.py also drives action() bare), right before gameplay
        s = sub1(r"^capture_gameplay_metrics start$", "export ARC3_PREDICTION_CHECK=1" + NL + "capture_gameplay_metrics start", s, re.M)
    elif spec["patch_candidate"]:
        s = sub1(r"^capture_gameplay_metrics start$", "export ARC3_V2_BATCH_GATE=1" + NL + "capture_gameplay_metrics start", s, re.M)
    if EFFORT:
        s = sub1(r'"preserve_thinking": true\}', '"preserve_thinking": true, "reasoning_effort": "' + EFFORT + '"}', s)
    s = add_watchdog(s)
    old_req = re.search(r"requestId=([0-9a-f-]{36})", s).group(1); new_req = str(uuid.uuid4())
    s = s.replace(old_req, new_req); (ARM / "DELETE_REQUEST_ID").write_text(new_req)
    leftovers = ["2061"] + ([] if ALL25 else ['ARC3_GAME_SUBSET=""'])
    if ALL25 and MULT == 1: leftovers = []   # 2061 s per game is exactly the base clock
    if spec["feature_arm"] != "baseline": leftovers += ["--arm baseline", "'baseline')"]
    if SUITE_MIN != 132: leftovers += ["minutes=132", "132-minute"]
    if VM_LIFE != 14400: leftovers += ["sleep 14400", "max-seconds 14400"]
    for leftover in leftovers:
        assert leftover not in s, leftover
    (ARM / "startup.sh").write_text(s, encoding="utf-8", newline=NL)
    shutil.rmtree(work)

    arm_json = {
        "arm": ARM_NAME, "harness_arm": args.arm, "feature_arm": spec["feature_arm"], "features": sorted(spec["features"]),
        "ablations": sorted(spec["ablations"]), "patched_candidate": spec["patch_candidate"], "changed_prompt_surfaces": changed_surfaces,
        "lanes": 7, "games": GAMES, "subset": SUBSET_, "game_seconds": GAME_S, "suite_minutes": SUITE_MIN, "vm_lifetime_seconds": VM_LIFE,
        "provisioning": "SPOT", "source_arm": "compaction_v5_clean_return_a (19-Sep, 132 min)",
        "runner_object": f"{RUNNER_DIR}/{runner_sha}/runner.py", "runner_sha256": runner_sha,
        "probe_object": f"{BUCKET_CODE}/{probe_sha}/runtime_probe.py", "probe_sha256": probe_sha,
        "prompt_probe_object": f"{BUCKET_CODE}/{pprobe_sha}/prompt_probe.py", "prompt_probe_sha256": pprobe_sha,
        "expected_prompts_object": f"{BUCKET_CODE}/{prompts_sha}/EXPECTED_PROMPTS.json", "expected_prompts_sha256": prompts_sha,
        "config_object": f"{BUCKET_CODE}/{cfg_sha}/CONFIG_FLAGS.json", "config_sha256": cfg_sha,
        "selftest_object": f"{BUCKET_CODE}/{selftest_sha}/selftest.tgz", "selftest_sha256": selftest_sha,
        "adapter_object": f"{BUCKET_CODE}/{adapter_sha}/ADAPTER.json", "adapter_sha256": adapter_sha,
        "release_object": f"{BUCKET_CODE}/{release_sha}/release.json", "release_sha256": release_sha,
        "candidate_object": f"{BUCKET_CODE}/{candidate_sha}/candidate.tgz", "candidate_sha256": candidate_sha,
        "candidate_changed": candidate_sha != old_candidate_sha, "source_sha256": source_sha256, "config_id": cfg["config_id"],
        "run_id_prefix": f"g4run-cv5cr-{SCOPE}-{args.arm}-{SUITE_MIN}" + (f"-effort{EFFORT}" if EFFORT else "") + "-w7", "instance_prefix": f"arc3-g4-{'a25' if ALL25 else 'h7'}{args.arm[:4]}{(EFFORT or '')[:3]}-{SUITE_MIN}",
    }
    (ARM / "ARM.json").write_text(json.dumps(arm_json, indent=2) + NL)
    print(f"{ARM_NAME}: features={sorted(spec['features']) or '-'} ablations={sorted(spec['ablations'])} candidate_changed={arm_json['candidate_changed']} "
          f"prompt_surfaces_changed={changed_surfaces} game_s={GAME_S} config_id={cfg['config_id'][:12]}")

if __name__ == "__main__":
    main()
