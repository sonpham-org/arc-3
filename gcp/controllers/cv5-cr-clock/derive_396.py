"""Derive the 396-minute (3x) compaction-v5-clean-return arm from the 19-Sep 132-minute arm.

Only the clock moves. Model (Flash-Next NVFP4, golden runtime image), prompts, candidate bundle,
cap 14/return, compaction v5 + half swap, 7 lanes, context 102985/94281 and sampling are the
19-Sep arm's own values, byte for byte, so the result is comparable to
g4run-compaction-v5-clean-return-{a,b}132 and to the 264-minute clean-return run.

Clock convention follows the existing 264 arm (game_seconds 4122 = 2x2061, vm 21600):
  132 -> 2061 s/game, 14400 s VM      264 -> 4122, 21600      396 -> 6183, 28800

Re-pins the runner and runtime_probe (both outside the candidate bundle) and re-registers
CONFIG_FLAGS through the arm's own contract.py.
"""
import hashlib, json, os, re, sys, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Clock is parameterised: SUITE_MIN=264 (the proven, directly comparable class) or 396 (3x).
# game_seconds scales with the suite exactly as the existing arms do (132:2061, 264:4122, 396:6183)
# and vm_lifetime follows their convention (14400 / 21600 / 28800).
SUITE_MIN = int(os.environ.get("ARC3_SUITE_MINUTES", "396"))
assert SUITE_MIN % 132 == 0, "suite must be a whole multiple of the 132-minute class"
MULT = SUITE_MIN // 132
GAME_S, VM_LIFE = 2061 * MULT, {1: 14400, 2: 21600, 3: 28800}[MULT]
SRC = Path(r"D:\codex-work\compaction-v5-clean-return132-20260919\arms\compaction_v5_clean_return_a")
ARM = HERE / "arms" / f"compaction_v5_clean_return_{SUITE_MIN}"
ARM.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(SRC))
import contract  # noqa: E402

PREGAME_UPTIME_MAX = 6360            # unchanged: the golden image keeps pre-game short
BUCKET_CODE = "gs://cellens-ai-artifacts/arc3-duck/code/cap-compact132"
RUNNER_DIR = "gs://cellens-ai-artifacts/arc3-duck/code/astra-execution/feature-ablation-132-v1"
BASE_RUNNER_SHA = "b3604c7731dde84089cfc20bbf1366378eb0791c5deb88c9e24271ac5b9f53bb"

def sha_b(b: bytes): return hashlib.sha256(b).hexdigest()
def sub1(pat, repl, text, flags=0):
    new, n = re.subn(pat, repl, text, count=1, flags=flags)
    assert n == 1, pat
    return new

# ---------------------------------------------------------------- runner.py
r = (ARM / "runner.py").read_text(encoding="utf-8")
assert sha_b(r.encode()) == BASE_RUNNER_SHA, "runner.py is not the pinned 132-minute original"
r = sub1(r"assert bm\.solver\.max_runtime_s_per_game == 2061\.0", f"assert bm.solver.max_runtime_s_per_game == {GAME_S}.0", r)
r = sub1(r'"Experimental runtime lock: 7 workers, 2061 seconds/game, "', f'"Experimental runtime lock: 7 workers, {GAME_S} seconds/game, "', r)
r = sub1(r"# 4 waves at 2061 seconds/game fit the 132-minute suite.*",
         f"# 4 waves at {GAME_S} seconds/game fit the {SUITE_MIN}-minute suite ({MULT}x ceiling run).", r)
(ARM / "runner.py").write_text(r, encoding="utf-8", newline="\n")
runner_sha = sha_b((ARM / "runner.py").read_bytes())

# ---------------------------------------------------------------- runtime_probe.py
p = (SRC / "runtime_probe.py").read_text(encoding="utf-8")
p = sub1(r"'vm_lifetime_seconds':14400", f"'vm_lifetime_seconds':{VM_LIFE}", p)
p = sub1(r"original 14400-second", f"original {VM_LIFE}-second", p)
p = sub1(r"anchor='soft_end = datetime\.now\(\) \+ timedelta\(minutes=132\)'",
         f"anchor='soft_end = datetime.now() + timedelta(minutes={SUITE_MIN})'", p)
p = sub1(r"attest\(bm,target,132\)", f"attest(bm,target,{SUITE_MIN})", p)
(ARM / "runtime_probe.py").write_text(p, encoding="utf-8", newline="\n")
probe_sha = sha_b((ARM / "runtime_probe.py").read_bytes())
old_probe_sha = sha_b((SRC / "runtime_probe.py").read_bytes())

# ---------------------------------------------------------------- CONFIG_FLAGS.json
cfg = json.loads((SRC / "CONFIG_FLAGS.json").read_text(encoding="utf-8-sig"))
cfg["recipe"]["limits"].update({"game_seconds": GAME_S, "suite_gameplay_minutes": SUITE_MIN,
                                "vm_lifetime_seconds": VM_LIFE})
cfg["recipe"]["extra_environment"].update({"ARC3_MAX_RUNTIME_S_PER_GAME": str(GAME_S),
                                           "ARC3_MAX_RUN_RUNTIME_MINUTES": str(SUITE_MIN)})
cfg["run_id"] = f"g4run-compaction-v5-clean-return-{SUITE_MIN}-w7-20260923"
cfg["evidence"]["notes"] = [
    "September23 user: 'It is possible compaction-v5-CR is better. Can you take a look and rerun the "
    "entire thing in 3x. Maybe its ceiling is actually higher here.' The 23-Sep hard-seven census is the "
    "reason: compaction-v5-CR is the WORST arm on all 25 games (12.66 mean) but the BEST on the hard "
    "seven (4.23 mean, 9.0 levels, 238 actions and 149k generated tokens per hard-seven point), and it "
    "is one of only two measured configurations whose hard-seven efficiency exceeds its all-25 "
    "efficiency (1.09x; the other is the 264-minute clean-return run at 1.11x). The 132->264 clean-return "
    "pair also showed hard-seven score rising 3.3x against 1.75x for the all-25 mean, so the hard games "
    "are where a longer clock pays. This run asks whether compaction v5's ceiling is higher when the "
    "clock stops being the binding constraint. "
    f"Only the clock changes from the 19-Sep arm: {GAME_S} s per game, {SUITE_MIN}-minute suite, "
    f"{VM_LIFE}-second VM. Model, prompts, bundle, cap, compaction, 7 lanes, context and sampling are "
    "byte-identical. ON-DEMAND, not Spot: four of the five 264-minute Spot runs were preempted before "
    "finishing. One scored attempt across 25 games; no automatic replacement. No Kaggle action.",
] + cfg["evidence"]["notes"][1:]
cfg["config_id"] = contract.config_id(cfg["recipe"])
contract.validate(cfg, for_launch=True)
cfg_bytes = (json.dumps(cfg, indent=2) + "\n").encode()
cfg_sha = sha_b(cfg_bytes); old_cfg_sha = sha_b((SRC / "CONFIG_FLAGS.json").read_bytes())
(ARM / "CONFIG_FLAGS.json").write_bytes(cfg_bytes)

# ---------------------------------------------------------------- ADAPTER.json
# A FIFTH pin: runtime_probe.main() hashes /opt/arc3/v12_run.py against ADAPTER.json's
# effective_runner_sha256 -- and that is the runner AFTER the startup's own PYRUNLIMIT patch
# rewrites the soft_end line, not the object we upload. Recompute it the same way (this is what
# killed attempt 3, at the very first line of gameplay).
eff = (ARM / "runner.py").read_text(encoding="utf-8")
old_anchor = "soft_end = datetime.now() + timedelta(hours=11, minutes=20)"
new_anchor = f"soft_end = datetime.now() + timedelta(minutes={SUITE_MIN})"
assert eff.count(old_anchor) == 1, "runner soft-deadline anchor drift"
effective_runner_sha = sha_b(eff.replace(old_anchor, new_anchor).encode())
adapter = json.loads((SRC / "ADAPTER.json").read_text(encoding="utf-8-sig"))
assert adapter["effective_runner_sha256"] != effective_runner_sha
adapter["effective_runner_sha256"] = effective_runner_sha
adapter_bytes = (json.dumps(adapter, indent=2, sort_keys=True) + chr(10)).encode()
(ARM / "ADAPTER.json").write_bytes(adapter_bytes)
adapter_sha = sha_b(adapter_bytes); old_adapter_sha = sha_b((SRC / "ADAPTER.json").read_bytes())
print("adapter ", adapter_sha[:16], "(was", old_adapter_sha[:16] + ")", "effective_runner", effective_runner_sha[:16])

# ---------------------------------------------------------------- selftest bundle
# The clock is pinned in a FOURTH place: inside selftest.tgz, as feature_contract.GAME_SECONDS /
# SUITE_MINUTES and release-manifest.json's "environment" dict. linux_selftest_matrix.py asserts
# manifest["environment"] == environment(arm) AND that every one of those values equals the live
# os.environ, so all three must move together or the pre-game selftest aborts the run (this is what
# killed attempt 1: AssertionError ARC3_MAX_RUNTIME_S_PER_GAME 6183 != 2061).
# PROFILES.json and tests/test_arm_configuration.py also mention 132, but that is a different,
# historical artifact (model-class profiles at 1472/1178 s) and is deliberately left alone.
import shutil, subprocess, tarfile, io, os
work = HERE / "_selftest"
if work.exists(): shutil.rmtree(work)
work.mkdir(parents=True)
with tarfile.open(SRC / "selftest.tgz") as t:
    names = t.getnames()
    t.extractall(work)
fc = work / "feature_contract.py"
x = fc.read_text(encoding="utf-8")
x = sub1(r"^GAME_SECONDS = 2061$", f"GAME_SECONDS = {GAME_S}", x, re.M)
x = sub1(r"^SUITE_MINUTES = 132$", f"SUITE_MINUTES = {SUITE_MIN}", x, re.M)
fc.write_text(x, encoding="utf-8", newline=chr(10))
rm = work / "release-manifest.json"
man = json.loads(rm.read_text(encoding="utf-8"))
assert man["environment"]["ARC3_MAX_RUNTIME_S_PER_GAME"] == "2061"
man["environment"]["ARC3_MAX_RUNTIME_S_PER_GAME"] = str(GAME_S)
man["environment"]["ARC3_MAX_RUN_RUNTIME_MINUTES"] = str(SUITE_MIN)
manifest_bytes = (json.dumps(man, indent=2, sort_keys=True) + chr(10)).encode()
rm.write_bytes(manifest_bytes)
# The startup does `cmp -s` between the bundle's copy and the standalone object: byte-identical.
(ARM / "release.json").write_bytes(manifest_bytes)
release_sha = sha_b(manifest_bytes)
# Repack deterministically (sorted names, fixed mtime/uid//gid) so the sha is reproducible.
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=9) as t:
    for name in sorted(names):
        full = work / name
        ti = t.gettarinfo(str(full), arcname=name)
        ti.mtime = 0; ti.uid = ti.gid = 0; ti.uname = ti.gname = ""
        if ti.isreg():
            with open(full, "rb") as fh: t.addfile(ti, fh)
        else:
            t.addfile(ti)
selftest_bytes = buf.getvalue()
(ARM / "selftest.tgz").write_bytes(selftest_bytes)
selftest_sha = sha_b(selftest_bytes)
old_selftest_sha = sha_b((SRC / "selftest.tgz").read_bytes())
old_release_sha = sha_b((SRC / "release.json").read_bytes())
shutil.rmtree(work)
print("selftest", selftest_sha[:16], "(was", old_selftest_sha[:16] + ")")
print("release ", release_sha[:16], "(was", old_release_sha[:16] + ")")

# ---------------------------------------------------------------- startup.sh
s = (SRC / "startup.sh").read_text(encoding="utf-8")
s = sub1(r"^# Search/scorer removal \+ 50% swap, W7, 132 minutes",
         f"# Search/scorer removal + 50% swap + compaction v5, W7, {SUITE_MIN} minutes ({MULT}x ceiling run)", s, re.M)
s = sub1(r"# Hard cost guard: 14400 seconds", f"# Hard cost guard: {VM_LIFE} seconds", s)
s = sub1(r"^  sleep 14400$", f"  sleep {VM_LIFE}", s, re.M)
# The metrics sampler refuses any duration above its own MAX_SECONDS = 5*3600 and exits before
# writing a line, which trips the startup's 10 s "telemetry did not become ready" check (this is
# what killed attempt 2). Cap it: telemetry then covers the first 5 h of the 6.6 h gameplay, and
# teardown kills the sampler with `|| true`, so an already-exited sampler is harmless.
SAMPLER_MAX = min(VM_LIFE, 18000)
s = sub1(r"--interval-seconds 30 --max-seconds 14400", f"--interval-seconds 30 --max-seconds {SAMPLER_MAX}", s)
s = sub1(r"echo '" + BASE_RUNNER_SHA + r"  /opt/arc3/v12_run\.py'", f"echo '{runner_sha}  /opt/arc3/v12_run.py'", s)
s = sub1(r"new = 'soft_end = datetime\.now\(\) \+ timedelta\(minutes=132\)'",
         f"new = 'soft_end = datetime.now() + timedelta(minutes={SUITE_MIN})'", s)
s = sub1(r"grep -F 'soft_end = datetime\.now\(\) \+ timedelta\(minutes=132\)'",
         f"grep -F 'soft_end = datetime.now() + timedelta(minutes={SUITE_MIN})'", s)
s = sub1(r"export ARC3_MAX_RUNTIME_S_PER_GAME=2061", f"export ARC3_MAX_RUNTIME_S_PER_GAME={GAME_S}", s)
s = sub1(r"export ARC3_MAX_RUN_RUNTIME_MINUTES=132", f"export ARC3_MAX_RUN_RUNTIME_MINUTES={SUITE_MIN}", s)
s = sub1(r"assert os\.environ\['ARC3_MAX_RUNTIME_S_PER_GAME'\] == '2061'",
         f"assert os.environ['ARC3_MAX_RUNTIME_S_PER_GAME'] == '{GAME_S}'", s)
s = sub1(r"assert os\.environ\['ARC3_MAX_RUN_RUNTIME_MINUTES'\] == '132'",
         f"assert os.environ['ARC3_MAX_RUN_RUNTIME_MINUTES'] == '{SUITE_MIN}'", s)
s = sub1(r'print\("verified feature arm baseline; no curator; 132-minute suite"\)',
         f'print("verified feature arm baseline; no curator; {SUITE_MIN}-minute suite")', s)
s = sub1(re.escape(f"{BUCKET_CODE}/{old_probe_sha}/runtime_probe.py"), f"{BUCKET_CODE}/{probe_sha}/runtime_probe.py", s)
s = sub1(re.escape(f"echo '{old_probe_sha}  /opt/arc3/config-audit/runtime_probe.py'"),
         f"echo '{probe_sha}  /opt/arc3/config-audit/runtime_probe.py'", s)
s = sub1(re.escape(f"{BUCKET_CODE}/{old_adapter_sha}/ADAPTER.json"), f"{BUCKET_CODE}/{adapter_sha}/ADAPTER.json", s)
s = sub1(re.escape(f"echo '{old_adapter_sha}  /opt/arc3/config-audit/ADAPTER.json'"),
         f"echo '{adapter_sha}  /opt/arc3/config-audit/ADAPTER.json'", s)
s = sub1(re.escape(f"echo '{old_selftest_sha}  /tmp/execution-selftest.tgz'"),
         f"echo '{selftest_sha}  /tmp/execution-selftest.tgz'", s)
s = sub1(re.escape(f"echo '{old_release_sha}  /opt/arc3/execution-release-manifest.json'"),
         f"echo '{release_sha}  /opt/arc3/execution-release-manifest.json'", s)
s = sub1(re.escape(f"{BUCKET_CODE}/{old_cfg_sha}/CONFIG_FLAGS.json"), f"{BUCKET_CODE}/{cfg_sha}/CONFIG_FLAGS.json", s)
s = sub1(re.escape(f"echo '{old_cfg_sha}  /opt/arc3/config-audit/CONFIG_FLAGS.json'"),
         f"echo '{cfg_sha}  /opt/arc3/config-audit/CONFIG_FLAGS.json'", s)
# The Spot-recreation guard refuses every boot after the first; on-demand cannot be recreated,
# so it stays exactly as written. Fresh self-delete request id for this VM.
old_req = re.search(r"requestId=([0-9a-f-]{36})", s).group(1)
new_req = str(uuid.uuid4())
s = s.replace(old_req, new_req)
(ARM / "DELETE_REQUEST_ID").write_text(new_req)
for leftover in ("2061", "minutes=132", "sleep 14400", "max-seconds 14400", "132-minute"):
    assert leftover not in s, leftover
(ARM / "startup.sh").write_text(s, encoding="utf-8", newline="\n")

(ARM / "ARM.json").write_text(json.dumps({
    "arm": f"compaction_v5_clean_return_{SUITE_MIN}", "lanes": 7, "game_seconds": GAME_S,
    "suite_minutes": SUITE_MIN, "vm_lifetime_seconds": VM_LIFE, "provisioning": "SPOT",
    "source_arm": "compaction_v5_clean_return_a (19-Sep, 132 min)",
    "runner_object": f"{RUNNER_DIR}/{runner_sha}/runner.py", "runner_sha256": runner_sha,
    "probe_object": f"{BUCKET_CODE}/{probe_sha}/runtime_probe.py", "probe_sha256": probe_sha,
    "config_object": f"{BUCKET_CODE}/{cfg_sha}/CONFIG_FLAGS.json", "config_sha256": cfg_sha,
    "selftest_object": f"{BUCKET_CODE}/{selftest_sha}/selftest.tgz", "selftest_sha256": selftest_sha,
    "adapter_object": f"{BUCKET_CODE}/{adapter_sha}/ADAPTER.json", "adapter_sha256": adapter_sha,
    "release_object": f"{BUCKET_CODE}/{release_sha}/release.json", "release_sha256": release_sha,
    "config_id": cfg["config_id"],
    "run_id_prefix": f"g4run-cv5cr{SUITE_MIN}-w7", "instance_prefix": f"arc3-g4-cv5cr{SUITE_MIN}",
}, indent=2) + "\n")
print("config_id", cfg["config_id"]); print("runner", runner_sha[:16]); print("probe", probe_sha[:16])
print("config", cfg_sha[:16]); print("startup lines", len(s.splitlines()))
