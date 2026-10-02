"""Derive RL try-runner arms (one per VM) from an RL seed arm (a Combo A clone with request logs on).

Same image, serving flags, bundle, selftests and harness environment as the source; the runner becomes the source
runner's own preamble + try_driver.py (in place of `asyncio.run(bm.run(...))`), and the VM fetches the try pack
(rl_reward, rl_tree, lake, branch_parse, the Firestore helpers). The Firestore run-score sidecar is switched off
(a try VM plays forks, not a 25-game suite). Plan: docs/plans/2026-10-01-rl-on-burst-games.md §0b step 2.
Pinned places follow derive_inject.py: runner sha in startup + ADAPTER.effective_runner_sha256 + ARM.runner_object,
CONFIG_FLAGS run_id/notes (recipe and config_id unchanged), startup header / pack fetch / ARC3_TRY_* exports,
DELETE_REQUEST_ID. The pack is uploaded here; launch_396.py uploads the arm's own objects.

  python derive_tries.py --src <seed arm> --campaign <name> --vms N [--lanes 19] [--deadline-min 180] [--no-upload]
Launch each arm with: ARC3_ARM_NAME=<arm> python ../sglang-scored/launch_396.py --zones ...
"""
import argparse
import gzip
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
CTRL = HERE.parent
ARMS = CTRL / "sglang-scored" / "arms"
BUCKET_CODE = "gs://cellens-ai-artifacts/arc3-duck/code/rl-tries-v1"
PACK_FILES = (HERE / "rl_reward.py", HERE / "rl_tree.py", HERE / "lake.py", CTRL / "branch-replay" / "branch_parse.py",
              CTRL.parent / "arc3_firestore_scores.py", CTRL.parent / "arc3_minute_score_observer.py")
NL = chr(10)
TAIL = ('asyncio.run(bm.run(soft_end_time=soft_end, runtime_environment=target, minimal_diagnostics=False))' + NL +
        'print("V12 RUN COMPLETE")' + NL)
SIDECAR = re.compile(r"^nice -n 19 /opt/arc3/pysrv/bin/python /opt/arc3/arc3_firestore_scores\.py vm .*&$", re.M)

ap = argparse.ArgumentParser()
ap.add_argument("--src", required=True)
ap.add_argument("--campaign", required=True)
ap.add_argument("--vms", type=int, default=1)
ap.add_argument("--first-vm", type=int, default=0)
ap.add_argument("--lanes", type=int, default=19)
ap.add_argument("--deadline-min", type=int, default=180)
ap.add_argument("--turn-cap", type=int, default=40)
ap.add_argument("--token-cap-x", type=float, default=1.5)
ap.add_argument("--no-upload", action="store_true")
ap.add_argument("--vm-hours", type=float, default=0, help="VM lifetime in hours (default: the source arm's 4 h); "
                "long-lived workers pull from a standing queue (Son 2-Oct: keep VMs running, grow the tree)")
a = ap.parse_args()
assert re.fullmatch(r"[a-z0-9-]{3,20}", a.campaign), "campaign: 3-20 chars of [a-z0-9-]"

SRC = ARMS / a.src
sys.path.insert(0, str(SRC))
import contract  # noqa: E402

src_arm = json.loads((SRC / "ARM.json").read_text(encoding="utf-8"))
assert src_arm.get("save_request_logs") is True, "source must be an RL seed arm (ARC3_SAVE_REQUEST_LOGS=1)"
assert a.lanes <= src_arm["slots"], f"lanes {a.lanes} > server slots {src_arm['slots']}"
life_s = int(a.vm_hours * 3600) if a.vm_hours else int(src_arm["vm_lifetime_seconds"])
life_min = life_s / 60
assert a.deadline_min + 40 <= life_min, f"deadline {a.deadline_min} min + ~40 min setup exceeds the VM lifetime {life_min:.0f} min"


def sha_b(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sub1(pat, repl, text, flags=0):
    new, n = re.subn(pat, repl, text, count=1, flags=flags)
    assert n == 1, pat
    return new


def gcloud(*args):
    exe = shutil.which("gcloud") or shutil.which("gcloud.cmd") or "gcloud"
    return subprocess.run([exe, *args], check=True, capture_output=True, text=True)


# ---------------------------------------------------------------- try pack (shared by all VMs)
buf = io.BytesIO()
gz = gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=6, mtime=0)
with tarfile.open(fileobj=gz, mode="w") as t:
    for p in PACK_FILES:
        data = p.read_bytes()
        ti = tarfile.TarInfo(p.name)
        ti.size, ti.mtime, ti.mode = len(data), 0, 0o644
        t.addfile(ti, io.BytesIO(data))
gz.close()
pack_bytes = buf.getvalue()
pack_sha = sha_b(pack_bytes)
pack_obj = f"{BUCKET_CODE}/{pack_sha}/trypack.tgz"
(HERE / "_build").mkdir(exist_ok=True)
(HERE / "_build" / "trypack.tgz").write_bytes(pack_bytes)
if not a.no_upload:
    gcloud("storage", "cp", str(HERE / "_build" / "trypack.tgz"), pack_obj)
print(f"pack {len(pack_bytes)} B sha {pack_sha[:12]} -> {pack_obj}{' (not uploaded)' if a.no_upload else ''}")

# ---------------------------------------------------------------- runner + adapter
src_runner = (SRC / "runner.py").read_text(encoding="utf-8")
assert src_runner.endswith(TAIL), "source runner tail drift"
runner = src_runner[:-len(TAIL)] + (HERE / "try_driver.py").read_text(encoding="utf-8")
old_anchor = "soft_end = datetime.now() + timedelta(hours=11, minutes=20)"
new_anchor = f"soft_end = datetime.now() + timedelta(minutes={src_arm['suite_minutes']})"
assert runner.count(old_anchor) == 1
compile(runner, "runner.py", "exec")
runner_sha = sha_b(runner.encode())
effective_runner_sha = sha_b(runner.replace(old_anchor, new_anchor).encode())
old_runner_sha = src_arm["runner_sha256"]
adapter = json.loads((SRC / "ADAPTER.json").read_text(encoding="utf-8-sig"))
adapter["effective_runner_sha256"] = effective_runner_sha
adapter_bytes = (json.dumps(adapter, indent=2, sort_keys=True) + NL).encode()
adapter_sha = sha_b(adapter_bytes)
old_adapter_sha, old_cfg_sha = src_arm["adapter_sha256"], src_arm["config_sha256"]
src_cfg_prefix = src_arm["config_object"].rsplit("/", 2)[0]

for k in range(a.first_vm, a.first_vm + a.vms):
    vm = f"vm{k}"
    arm_name = f"rltry_{a.campaign.replace('-', '')}_{vm}"
    ARM = ARMS / arm_name
    assert not ARM.exists(), f"{ARM} exists; pick a new campaign"
    ARM.mkdir(parents=True)
    for f in ("contract.py", "prompt_probe.py", "time_guidance_probe.py", "EXPECTED_PROMPTS.json", "selftest.tgz",
              "release.json", "runtime_probe.py", "instance-body.json", "candidate.tgz", "META_KEYS.json"):
        if (SRC / f).exists():
            shutil.copy(SRC / f, ARM / f)
    (ARM / "runner.py").write_text(runner, encoding="utf-8", newline=NL)
    (ARM / "ADAPTER.json").write_bytes(adapter_bytes)
    cfg = json.loads((SRC / "CONFIG_FLAGS.json").read_text(encoding="utf-8-sig"))
    cfg["run_id"] = f"g4run-rltry-{a.campaign}-{vm}"
    cfg["evidence"]["notes"] = [
        "Son 1-Oct: RL tries (docs/plans/2026-10-01-rl-on-burst-games.md). Serving, bundle, prompts and harness flags are "
        f"byte-identical to {a.src} (Combo A + request logs); the runner is the source preamble + try_driver.py: up to "
        f"{a.lanes} concurrent tries forked from moments in the job queue (campaign {a.campaign}), each replayed exactly to "
        f"its fork turn then played live until the level clears or {a.turn_cap} turns / {a.token_cap_x}x the reference's "
        "remaining tokens / the source game clock. Not a benchmark score.",
    ] + cfg["evidence"]["notes"][1:]
    assert cfg["config_id"] == contract.config_id(cfg["recipe"])
    contract.validate(cfg, for_launch=True)
    cfg_bytes = (json.dumps(cfg, indent=2) + NL).encode()
    cfg_sha = sha_b(cfg_bytes)
    (ARM / "CONFIG_FLAGS.json").write_bytes(cfg_bytes)
    s = (SRC / "startup.sh").read_text(encoding="utf-8")
    lines = s.split(NL)
    assert lines[1].startswith("# "), lines[1]
    lines[1] = f"# RL TRIES {a.campaign} {vm}: serving + harness byte-identical to {a.src}; runner = preamble + try_driver.py."
    s = NL.join(lines)
    s = sub1(re.escape(f"echo '{old_runner_sha}  /opt/arc3/v12_run.py'"), f"echo '{runner_sha}  /opt/arc3/v12_run.py'", s)
    s = sub1(re.escape('gcloud storage cp "$SCORE_OBSERVER_OBJECT" /opt/arc3/arc3_minute_score_observer.py'),
             'gcloud storage cp "$SCORE_OBSERVER_OBJECT" /opt/arc3/arc3_minute_score_observer.py' + NL +
             f"gcloud storage cp '{pack_obj}' /tmp/trypack.tgz" + NL +
             f"echo '{pack_sha}  /tmp/trypack.tgz' | sha256sum -c -" + NL +
             "rm -rf /opt/arc3/trypack && mkdir -p /opt/arc3/trypack && tar xzf /tmp/trypack.tgz -C /opt/arc3/trypack" + NL +
             "test -f /opt/arc3/trypack/try_driver.py || test -f /opt/arc3/trypack/rl_tree.py", s)
    for old, new, fn in ((old_cfg_sha, cfg_sha, "CONFIG_FLAGS.json"), (old_adapter_sha, adapter_sha, "ADAPTER.json")):
        s = sub1(re.escape(f"{src_cfg_prefix}/{old}/{fn}"), f"{BUCKET_CODE}/{new}/{fn}", s)
        s = sub1(re.escape(f"echo '{old}  /opt/arc3/config-audit/{fn}'"), f"echo '{new}  /opt/arc3/config-audit/{fn}'", s)
    s, n_side = SIDECAR.subn(": # Firestore run-score sidecar off on try VMs (forks, not a 25-game suite)", s)
    assert n_side == 1, n_side
    exports = (f"export ARC3_TRY_PACK=/opt/arc3/trypack ARC3_TRY_CAMPAIGN={a.campaign} ARC3_TRY_VM={vm} "
               f"ARC3_TRY_LANES={a.lanes} ARC3_TRY_TURN_CAP={a.turn_cap} ARC3_TRY_TOKEN_CAP_X={a.token_cap_x} "
               f"ARC3_TRY_DEADLINE_MIN={a.deadline_min}" + NL)
    s = sub1(r"^capture_gameplay_metrics start$", exports + "capture_gameplay_metrics start", s, re.M)
    if life_s != int(src_arm["vm_lifetime_seconds"]):        # the startup's own cost guard, and GCE's max run time
        old_life = int(src_arm["vm_lifetime_seconds"])
        s = sub1(rf"^# Hard cost guard: {old_life} seconds from VM startup", f"# Hard cost guard: {life_s} seconds from VM startup", s, re.M)
        s = sub1(rf"^  sleep {old_life}$", f"  sleep {life_s}", s, re.M)
    old_req = re.search(r"requestId=([0-9a-f-]{36})", s).group(1)
    new_req = str(uuid.uuid4())
    s = s.replace(old_req, new_req)
    (ARM / "DELETE_REQUEST_ID").write_text(new_req)
    assert old_runner_sha not in s and old_cfg_sha not in s and old_adapter_sha not in s
    (ARM / "startup.sh").write_text(s, encoding="utf-8", newline=NL)
    arm = dict(src_arm)
    arm.update({
        "arm": arm_name, "source_arm": f"{a.src} + try_driver.py", "campaign": a.campaign, "vm": vm,
        "try_lanes": a.lanes, "deadline_min": a.deadline_min, "turn_cap": a.turn_cap, "token_cap_x": a.token_cap_x,
        "vm_lifetime_seconds": life_s,
        "runner_object": f"{BUCKET_CODE}/{runner_sha}/runner.py", "runner_sha256": runner_sha,
        "config_object": f"{BUCKET_CODE}/{cfg_sha}/CONFIG_FLAGS.json", "config_sha256": cfg_sha,
        "adapter_object": f"{BUCKET_CODE}/{adapter_sha}/ADAPTER.json", "adapter_sha256": adapter_sha,
        "try_pack_object": pack_obj, "try_pack_sha256": pack_sha, "firestore_scores": False,
        "run_id_prefix": f"g4run-rltry-{a.campaign}-{vm}", "instance_prefix": f"arc3-g4-rltry-{a.campaign}-{vm}"[:50],
        "tag": "rltry",
    })
    (ARM / "ARM.json").write_text(json.dumps(arm, indent=2) + NL, encoding="utf-8")
    print(f"{arm_name}: lanes={a.lanes} deadline={a.deadline_min}min cfg={cfg_sha[:10]} runner={runner_sha[:10]}")
print("runner", runner_sha[:12], "effective", effective_runner_sha[:12], "adapter", adapter_sha[:12])
