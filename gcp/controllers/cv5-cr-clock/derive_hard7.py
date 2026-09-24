"""Hard-seven, one wave, full clock: compaction-v5-clean-return on bp35/g50t/lf52/ls20/sk48/tn36/wa30 only.

Son, 23-Sep: "Do only 1 wave but give the hard 7 games all the time. I really want to see how a harness
tackles really hard games by giving it all the time it needs."

7 lanes x 7 games = one wave, so every game owns the entire suite clock:
  SUITE_MIN=264 -> game_seconds 15840 (7.7x the 132-class 2061), vm 21600  (Spot-survivable class)
  SUITE_MIN=396 -> game_seconds 23760, vm 28800

Everything else is the 19-Sep compaction_v5_clean_return_a arm byte for byte (model, prompts, bundle,
cap 14/return, compaction v5 + half swap, context 102985/94281, sampling). Six pinned places move:
runner (assert 25 games -> 7, clock), runtime_probe (vm life, suite), CONFIG_FLAGS (limits.games,
clock, ARC3_GAME_SUBSET -> new config_id), selftest bundle (feature_contract + manifest env),
ADAPTER.json (effective runner hash), startup.sh (exports, pins, sampler cap, subset).
"""
import hashlib, io, json, os, re, shutil, sys, tarfile, uuid
from watchdog import add_watchdog
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUITE_MIN = int(os.environ.get("ARC3_SUITE_MINUTES", "264"))
assert SUITE_MIN % 132 == 0
MULT = SUITE_MIN // 132
GAME_S = SUITE_MIN * 60                      # one wave: each game gets the whole suite
VM_LIFE = {1: 14400, 2: 21600, 3: 28800}[MULT]
SAMPLER_MAX = min(VM_LIFE, 18000)            # vllm_metrics_sampler MAX_SECONDS = 5*3600
HARD7 = ["bp35", "g50t", "lf52", "ls20", "sk48", "tn36", "wa30"]
SUBSET = ",".join(HARD7)
# Generalised 25-Sep: ARC3_SRC_ARM = any 132-minute arm of this family, ARC3_ARM_TAG = run/instance prefix.
SRC = Path(os.environ.get("ARC3_SRC_ARM", r"D:\codex-work\compaction-v5-clean-return132-20260919\arms\compaction_v5_clean_return_a"))
TAG = os.environ.get("ARC3_ARM_TAG", "cv5cr")
LABEL = SRC.name[:-2] if SRC.name.endswith("_a") else SRC.name
ARM_NAME = f"{LABEL}_hard7_{SUITE_MIN}"
ARM = HERE / "arms" / ARM_NAME
ARM.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(SRC))
import contract  # noqa: E402

BUCKET_CODE = "gs://cellens-ai-artifacts/arc3-duck/code/" + re.search(r"gs://cellens-ai-artifacts/arc3-duck/code/([a-z0-9-]+)/[0-9a-f]{64}/runtime_probe\.py", (SRC / "startup.sh").read_text(encoding="utf-8")).group(1)
RUNNER_DIR = "gs://cellens-ai-artifacts/arc3-duck/code/astra-execution/feature-ablation-132-v1"
BASE_RUNNER_SHA = "b3604c7731dde84089cfc20bbf1366378eb0791c5deb88c9e24271ac5b9f53bb"
NL = chr(10)

def sha_b(b: bytes): return hashlib.sha256(b).hexdigest()
def sub1(pat, repl, text, flags=0):
    new, n = re.subn(pat, repl, text, count=1, flags=flags)
    assert n == 1, pat
    return new

# ---------------------------------------------------------------- runner.py
r = (ARM / "runner.py").read_text(encoding="utf-8")
assert sha_b(r.encode()) == BASE_RUNNER_SHA, "runner.py is not the pinned 132-minute original"
r = sub1(r"assert bm\.solver\.max_runtime_s_per_game == 2061\.0", f"assert bm.solver.max_runtime_s_per_game == {GAME_S}.0", r)
r = sub1(r'"Experimental runtime lock: 7 workers, 2061 seconds/game, "', f'"Experimental runtime lock: 7 workers, {GAME_S} seconds/game, hard-seven only, "', r)
r = sub1(r'assert len\(game_ids\) == 25, f"experiment requires 25 games, got \{len\(game_ids\)\}"',
         f'assert len(game_ids) == {len(HARD7)}, f"hard-seven experiment requires {len(HARD7)} games, got {{len(game_ids)}}"', r)
r = sub1(r"# 4 waves at 2061 seconds/game fit the 132-minute suite.*",
         f"# One wave: 7 lanes x 7 hard games, {GAME_S} s each = the whole {SUITE_MIN}-minute suite per game.", r)
(ARM / "runner.py").write_text(r, encoding="utf-8", newline=NL)
runner_sha = sha_b((ARM / "runner.py").read_bytes())

# ---------------------------------------------------------------- runtime_probe.py
p = (SRC / "runtime_probe.py").read_text(encoding="utf-8")
p = sub1(r"'vm_lifetime_seconds':14400", f"'vm_lifetime_seconds':{VM_LIFE}", p)
p = sub1(r"original 14400-second", f"original {VM_LIFE}-second", p)
p = sub1(r"anchor='soft_end = datetime\.now\(\) \+ timedelta\(minutes=132\)'",
         f"anchor='soft_end = datetime.now() + timedelta(minutes={SUITE_MIN})'", p)
p = sub1(r"attest\(bm,target,132\)", f"attest(bm,target,{SUITE_MIN})", p)
(ARM / "runtime_probe.py").write_text(p, encoding="utf-8", newline=NL)
probe_sha = sha_b((ARM / "runtime_probe.py").read_bytes()); old_probe_sha = sha_b((SRC / "runtime_probe.py").read_bytes())

# ---------------------------------------------------------------- CONFIG_FLAGS.json
cfg = json.loads((SRC / "CONFIG_FLAGS.json").read_text(encoding="utf-8-sig"))
cfg["recipe"]["limits"].update({"game_seconds": GAME_S, "suite_gameplay_minutes": SUITE_MIN,
                                "vm_lifetime_seconds": VM_LIFE, "games": len(HARD7)})
cfg["recipe"]["extra_environment"].update({"ARC3_MAX_RUNTIME_S_PER_GAME": str(GAME_S),
                                           "ARC3_MAX_RUN_RUNTIME_MINUTES": str(SUITE_MIN),
                                           "ARC3_GAME_SUBSET": SUBSET})
cfg["run_id"] = f"g4run-{TAG}-hard7-{SUITE_MIN}-w7-20260925"
cfg["evidence"]["notes"] = [
    "September23 user: 'Do only 1 wave but give the hard 7 games all the time. I really want to see how a "
    "harness tackles really hard games by giving it all the time it needs.' One wave of the seven hard games "
    f"(bp35 g50t lf52 ls20 sk48 tn36 wa30) on 7 lanes, {GAME_S} s per game = the whole {SUITE_MIN}-minute "
    "suite each. Base: the 19-Sep compaction_v5_clean_return_a arm, byte-identical except the clock, the "
    "game subset and the 7-game count; chosen because the 23-Sep census shows it is the most hard-seven-"
    "efficient 132-minute arm (4.20 score/1k actions, 9.0 levels) despite being worst overall. Not "
    "comparable to any 25-game score; compare per game against the same games' rows in the 132/264 runs. "
    "Spot (on-demand GPU quota is 0). One attempt, no replacement, no Kaggle action.",
] + cfg["evidence"]["notes"][1:]
cfg["config_id"] = contract.config_id(cfg["recipe"])
contract.validate(cfg, for_launch=True)
cfg_bytes = (json.dumps(cfg, indent=2) + NL).encode()
cfg_sha = sha_b(cfg_bytes); old_cfg_sha = sha_b((SRC / "CONFIG_FLAGS.json").read_bytes())
(ARM / "CONFIG_FLAGS.json").write_bytes(cfg_bytes)

# ---------------------------------------------------------------- ADAPTER.json (effective runner = runner after startup's soft_end patch)
old_anchor = "soft_end = datetime.now() + timedelta(hours=11, minutes=20)"
new_anchor = f"soft_end = datetime.now() + timedelta(minutes={SUITE_MIN})"
assert r.count(old_anchor) == 1
effective_runner_sha = sha_b(r.replace(old_anchor, new_anchor).encode())
adapter = json.loads((SRC / "ADAPTER.json").read_text(encoding="utf-8-sig"))
adapter["effective_runner_sha256"] = effective_runner_sha
adapter_bytes = (json.dumps(adapter, indent=2, sort_keys=True) + NL).encode()
(ARM / "ADAPTER.json").write_bytes(adapter_bytes)
adapter_sha = sha_b(adapter_bytes); old_adapter_sha = sha_b((SRC / "ADAPTER.json").read_bytes())

# ---------------------------------------------------------------- selftest bundle (feature_contract + manifest env; candidate/ untouched)
work = HERE / "_selftest_hard7"
if work.exists(): shutil.rmtree(work)
work.mkdir()
with tarfile.open(SRC / "selftest.tgz") as t:
    names = t.getnames(); t.extractall(work)
fc = work / "feature_contract.py"; x = fc.read_text(encoding="utf-8")
x = sub1(r"^GAME_SECONDS = 2061$", f"GAME_SECONDS = {GAME_S}", x, re.M)
x = sub1(r"^SUITE_MINUTES = 132$", f"SUITE_MINUTES = {SUITE_MIN}", x, re.M)
fc.write_text(x, encoding="utf-8", newline=NL)
rm = work / "release-manifest.json"; man = json.loads(rm.read_text(encoding="utf-8"))
man["environment"]["ARC3_MAX_RUNTIME_S_PER_GAME"] = str(GAME_S)
man["environment"]["ARC3_MAX_RUN_RUNTIME_MINUTES"] = str(SUITE_MIN)
manifest_bytes = (json.dumps(man, indent=2, sort_keys=True) + NL).encode()
rm.write_bytes(manifest_bytes); (ARM / "release.json").write_bytes(manifest_bytes)
release_sha = sha_b(manifest_bytes); old_release_sha = sha_b((SRC / "release.json").read_bytes())
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=9) as t:
    for name in sorted(names):
        full = work / name; ti = t.gettarinfo(str(full), arcname=name)
        ti.mtime = 0; ti.uid = ti.gid = 0; ti.uname = ti.gname = ""
        if ti.isreg():
            with open(full, "rb") as fh: t.addfile(ti, fh)
        else: t.addfile(ti)
selftest_bytes = buf.getvalue(); (ARM / "selftest.tgz").write_bytes(selftest_bytes)
selftest_sha = sha_b(selftest_bytes); old_selftest_sha = sha_b((SRC / "selftest.tgz").read_bytes())
shutil.rmtree(work)

# ---------------------------------------------------------------- startup.sh
s = (SRC / "startup.sh").read_text(encoding="utf-8")
s = sub1(r"^# Search/scorer removal \+ 50% swap, W7, 132 minutes",
         f"# {LABEL}, HARD SEVEN ONLY, one wave, W7, {SUITE_MIN} minutes", s, re.M)
s = sub1(r"# Hard cost guard: 14400 seconds", f"# Hard cost guard: {VM_LIFE} seconds", s)
s = sub1(r"^  sleep 14400$", f"  sleep {VM_LIFE}", s, re.M)
s = sub1(r"--interval-seconds 30 --max-seconds 14400", f"--interval-seconds 30 --max-seconds {SAMPLER_MAX}", s)
s = sub1(r"echo '" + BASE_RUNNER_SHA + r"  /opt/arc3/v12_run\.py'", f"echo '{runner_sha}  /opt/arc3/v12_run.py'", s)
s = sub1(r"new = 'soft_end = datetime\.now\(\) \+ timedelta\(minutes=132\)'", f"new = '{new_anchor}'", s)
s = sub1(r"grep -F 'soft_end = datetime\.now\(\) \+ timedelta\(minutes=132\)'", f"grep -F '{new_anchor}'", s)
s = sub1(r"export ARC3_MAX_RUNTIME_S_PER_GAME=2061", f"export ARC3_MAX_RUNTIME_S_PER_GAME={GAME_S}", s)
s = sub1(r"export ARC3_MAX_RUN_RUNTIME_MINUTES=132", f"export ARC3_MAX_RUN_RUNTIME_MINUTES={SUITE_MIN}", s)
s = sub1(r'ARC3_GAME_SUBSET=""', f'ARC3_GAME_SUBSET="{SUBSET}"', s)
s = sub1(r"assert os\.environ\['ARC3_MAX_RUNTIME_S_PER_GAME'\] == '2061'", f"assert os.environ['ARC3_MAX_RUNTIME_S_PER_GAME'] == '{GAME_S}'", s)
s = sub1(r"assert os\.environ\['ARC3_MAX_RUN_RUNTIME_MINUTES'\] == '132'", f"assert os.environ['ARC3_MAX_RUN_RUNTIME_MINUTES'] == '{SUITE_MIN}'", s)
s = sub1(r'print\("verified feature arm baseline; no curator; 132-minute suite"\)',
         f'print("verified feature arm baseline; no curator; {SUITE_MIN}-minute suite, hard seven only")', s)
for old, new, fn in ((old_probe_sha, probe_sha, "runtime_probe.py"), (old_cfg_sha, cfg_sha, "CONFIG_FLAGS.json"),
                     (old_adapter_sha, adapter_sha, "ADAPTER.json")):
    s = sub1(re.escape(f"{BUCKET_CODE}/{old}/{fn}"), f"{BUCKET_CODE}/{new}/{fn}", s)
    s = sub1(re.escape(f"echo '{old}  /opt/arc3/config-audit/{fn}'"), f"echo '{new}  /opt/arc3/config-audit/{fn}'", s)
s = sub1(re.escape(f"echo '{old_selftest_sha}  /tmp/execution-selftest.tgz'"), f"echo '{selftest_sha}  /tmp/execution-selftest.tgz'", s)
s = sub1(re.escape(f"echo '{old_release_sha}  /opt/arc3/execution-release-manifest.json'"),
         f"echo '{release_sha}  /opt/arc3/execution-release-manifest.json'", s)
s = add_watchdog(s)
old_req = re.search(r"requestId=([0-9a-f-]{36})", s).group(1); new_req = str(uuid.uuid4())
s = s.replace(old_req, new_req); (ARM / "DELETE_REQUEST_ID").write_text(new_req)
for leftover in ["2061", 'ARC3_GAME_SUBSET=""'] + (["minutes=132", "sleep 14400", "max-seconds 14400", "132-minute"] if SUITE_MIN != 132 else []):
    assert leftover not in s, leftover
(ARM / "startup.sh").write_text(s, encoding="utf-8", newline=NL)

(ARM / "ARM.json").write_text(json.dumps({
    "arm": ARM_NAME, "lanes": 7, "games": len(HARD7), "subset": SUBSET, "game_seconds": GAME_S,
    "suite_minutes": SUITE_MIN, "vm_lifetime_seconds": VM_LIFE, "provisioning": "SPOT",
    "source_arm": "compaction_v5_clean_return_a (19-Sep, 132 min)",
    "runner_object": f"{RUNNER_DIR}/{runner_sha}/runner.py", "runner_sha256": runner_sha,
    "probe_object": f"{BUCKET_CODE}/{probe_sha}/runtime_probe.py", "probe_sha256": probe_sha,
    "config_object": f"{BUCKET_CODE}/{cfg_sha}/CONFIG_FLAGS.json", "config_sha256": cfg_sha,
    "selftest_object": f"{BUCKET_CODE}/{selftest_sha}/selftest.tgz", "selftest_sha256": selftest_sha,
    "adapter_object": f"{BUCKET_CODE}/{adapter_sha}/ADAPTER.json", "adapter_sha256": adapter_sha,
    "release_object": f"{BUCKET_CODE}/{release_sha}/release.json", "release_sha256": release_sha,
    "config_id": cfg["config_id"],
    "run_id_prefix": f"g4run-{TAG}-hard7-{SUITE_MIN}-w7", "instance_prefix": f"arc3-g4-{TAG[:5]}h7-{SUITE_MIN}", "tag": TAG,
}, indent=2) + NL)
print(f"arm {ARM_NAME}: games={len(HARD7)} game_s={GAME_S} suite={SUITE_MIN} vm={VM_LIFE}")
print("config_id", cfg["config_id"][:16], "runner", runner_sha[:12], "probe", probe_sha[:12],
      "selftest", selftest_sha[:12], "adapter", adapter_sha[:12], "release", release_sha[:12])
