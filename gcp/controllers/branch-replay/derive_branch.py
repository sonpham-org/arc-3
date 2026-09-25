"""Derive the branch-replay arm(s) from the LA-CR hard-seven arm: same golden image, serving flags, bundle,
selftests and harness environment; the runner becomes branch_runner.py and the VM also fetches the branch
pack (plan + parsed transcripts). One arm per shard: `python derive_branch.py <pack_dir> <n_shards>`.

Pinned places that move: runner (sha in startup + ADAPTER.effective_runner_sha256 + ARM.runner_object),
CONFIG_FLAGS (run_id/notes -> new object sha, recipe and config_id unchanged), startup (pack fetch, high
chat template, ARC3_BRANCH_* exports before gameplay, header), DELETE_REQUEST_ID.
"""
import hashlib, io, json, os, re, shutil, sys, tarfile, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(r"D:\codex-work\cv5-cr-396-20260923\arms\la_clean_return_hard7_132")
PACK_DIR = Path(sys.argv[1]); N_SHARDS = int(sys.argv[2])
DEADLINE_MIN = int(os.environ.get("ARC3_BRANCH_DEADLINE_MIN", "185"))
WAVE = os.environ.get("ARC3_BRANCH_WAVE", "")          # "" = wave 1 names; "w2" = second wave (remaining jobs)
WTAG = f"{WAVE}-" if WAVE else ""
PARENT_RUN = "g4run-lacr-hard7-132-w7-20260924-92964fb0e9"
BUCKET_CODE = "gs://cellens-ai-artifacts/arc3-duck/code/branch-lacr-v1"
NL = chr(10)
sys.path.insert(0, str(SRC))
import contract  # noqa: E402

# Served 'high' template: the Qwen3.8 template knows xhigh (careful sentence, default) / medium (no sentence) / low (brief);
# 'high' = a copy whose xhigh sentence is milder. Same recipe as the effort arms (scratchpad/high_effort.py).
XHIGH = 'Reasoning effort is set to xhigh. Please think carefully through the task, validate key assumptions, consider plausible alternatives, and prioritize correctness, consistency, and clarity in the final answer.'
HIGH = 'Reasoning effort is set to high. Think through the task and check the key assumptions behind your next action, but keep the reasoning proportionate to the decision at hand and move to the answer once it is justified.'
HIGH_PREP = [
    "cp /opt/arc3/flashnext-model/chat_template.jinja /opt/arc3/high-chat-template.jinja",
    "python3 - <<'PYHIGH'",
    "from pathlib import Path",
    "p = Path('/opt/arc3/high-chat-template.jinja'); t = p.read_text(encoding='utf-8')",
    f"old = {XHIGH!r}",
    f"new = {HIGH!r}",
    "assert t.count(old) == 1, t.count(old)",
    "p.write_text(t.replace(old, new), encoding='utf-8'); print('high chat template written')",
    "PYHIGH",
]


def sha_b(b: bytes): return hashlib.sha256(b).hexdigest()
def sub1(pat, repl, text, flags=0):
    new, n = re.subn(pat, repl, text, count=1, flags=flags)
    assert n == 1, pat
    return new


# ---------------------------------------------------------------- branch pack (shared by all shards)
import gzip
buf = io.BytesIO()
gz = gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=6, mtime=0)   # deterministic archive (gzip header time zeroed)
with tarfile.open(fileobj=gz, mode="w") as t:
    for p in sorted(PACK_DIR.rglob("*")):
        if p.is_file():
            ti = t.gettarinfo(str(p), arcname=str(p.relative_to(PACK_DIR)).replace(os.sep, "/"))
            ti.mtime = 0; ti.uid = ti.gid = 0; ti.uname = ti.gname = ""
            with open(p, "rb") as fh: t.addfile(ti, fh)
gz.close()
pack_bytes = buf.getvalue(); pack_sha = sha_b(pack_bytes)
(HERE / "arms").mkdir(exist_ok=True)
(HERE / "arms" / "branchpack.tgz").write_bytes(pack_bytes)
pack_obj = f"{BUCKET_CODE}/{pack_sha}/branchpack.tgz"
plan = json.loads((PACK_DIR / "plan.json").read_text(encoding="utf-8"))
print(f"pack {len(pack_bytes)/1e6:.1f} MB sha {pack_sha[:12]} jobs {len(plan)} groups {len({j['group'] for j in plan})}")

# ---------------------------------------------------------------- runner
runner = (HERE / "branch_runner.py").read_text(encoding="utf-8")
old_anchor = "soft_end = datetime.now() + timedelta(hours=11, minutes=20)"
new_anchor = "soft_end = datetime.now() + timedelta(minutes=132)"
assert runner.count(old_anchor) == 1
compile(runner, "runner.py", "exec")
runner_sha = sha_b(runner.encode()); effective_runner_sha = sha_b(runner.replace(old_anchor, new_anchor).encode())
src_arm = json.loads((SRC / "ARM.json").read_text(encoding="utf-8"))
old_runner_sha = src_arm["runner_sha256"]

adapter = json.loads((SRC / "ADAPTER.json").read_text(encoding="utf-8-sig"))
adapter["effective_runner_sha256"] = effective_runner_sha
adapter_bytes = (json.dumps(adapter, indent=2, sort_keys=True) + NL).encode()
adapter_sha = sha_b(adapter_bytes); old_adapter_sha = src_arm["adapter_sha256"]
old_cfg_sha = src_arm["config_sha256"]
src_cfg_prefix = src_arm["config_object"].rsplit("/", 2)[0]      # .../code/cap-compact132

for k in range(N_SHARDS):
    ARM_NAME = f"branch_lacr_{WAVE + '_' if WAVE else ''}s{k}of{N_SHARDS}"
    ARM = HERE / "arms" / ARM_NAME; ARM.mkdir(parents=True, exist_ok=True)
    for f in ("contract.py", "prompt_probe.py", "time_guidance_probe.py", "EXPECTED_PROMPTS.json", "selftest.tgz",
              "release.json", "runtime_probe.py", "instance-body.json"):
        shutil.copy(SRC / f, ARM / f)
    (ARM / "runner.py").write_text(runner, encoding="utf-8", newline=NL)
    (ARM / "ADAPTER.json").write_bytes(adapter_bytes)
    my_jobs = [j for j in plan if int(j["group_index"]) % N_SHARDS == k]
    # ---- CONFIG_FLAGS: recipe untouched (same config_id); run_id + notes describe the experiment
    cfg = json.loads((SRC / "CONFIG_FLAGS.json").read_text(encoding="utf-8-sig"))
    cfg["run_id"] = f"g4run-branch-lacr-{WTAG}s{k}of{N_SHARDS}-20260925"
    cfg["evidence"]["notes"] = [
        "September25 user: 'reduce its thinking efficiency ... for each level that it solves, for i in 1..N replay until finishing turn i, "
        "generate traces from turn i+1 onward with high, medium and low thinking; measure action efficiency (remaining actions) and token "
        f"efficiency.' Branch-replay experiment on the LA-CR hard-seven recording {PARENT_RUN}: the recorded responses are replayed against "
        "fresh offline games (no model) through the branch turn, then play continues live with a per-request reasoning-effort override "
        "(medium/low via chat_template_kwargs.reasoning_effort; high via a served template copy with a milder sentence; xhigh = control "
        f"re-sample). Caps: level solved / 2x original remaining turns / 2x original remaining actions. Shard {k} of {N_SHARDS}: "
        f"{len(my_jobs)} jobs, {len({j['group'] for j in my_jobs})} checkpoints. Serving, bundle, prompts and harness flags are byte-identical "
        "to the parent arm; the runner is branch_runner.py. Not a benchmark score: per-game 'scores' in runs/ are per-branch artifacts.",
    ] + cfg["evidence"]["notes"][1:]
    assert cfg["config_id"] == contract.config_id(cfg["recipe"])
    contract.validate(cfg, for_launch=True)
    cfg_bytes = (json.dumps(cfg, indent=2) + NL).encode(); cfg_sha = sha_b(cfg_bytes)
    (ARM / "CONFIG_FLAGS.json").write_bytes(cfg_bytes)
    # ---- startup.sh
    s = (SRC / "startup.sh").read_text(encoding="utf-8")
    s = sub1(r"^# la_clean_return, HARD SEVEN ONLY, one wave, W7, 132 minutes, time-only guidance; arm=la_clean_return_a\.",
             f"# BRANCH REPLAY on the LA-CR hard-seven recording ({PARENT_RUN}); shard {k}/{N_SHARDS}; serving + harness byte-identical to la_clean_return_hard7_132.", s, re.M)
    s = sub1(re.escape(f"echo '{old_runner_sha}  /opt/arc3/v12_run.py'"), f"echo '{runner_sha}  /opt/arc3/v12_run.py'", s)
    s = sub1(re.escape('gcloud storage cp "$SCORE_OBSERVER_OBJECT" /opt/arc3/arc3_minute_score_observer.py'),
             'gcloud storage cp "$SCORE_OBSERVER_OBJECT" /opt/arc3/arc3_minute_score_observer.py' + NL +
             f"gcloud storage cp '{pack_obj}' /tmp/branchpack.tgz" + NL +
             f"echo '{pack_sha}  /tmp/branchpack.tgz' | sha256sum -c -" + NL +
             "rm -rf /opt/arc3/branchpack && mkdir -p /opt/arc3/branchpack && tar xzf /tmp/branchpack.tgz -C /opt/arc3/branchpack" + NL +
             "test -f /opt/arc3/branchpack/plan.json", s)
    for old, new, fn in ((old_cfg_sha, cfg_sha, "CONFIG_FLAGS.json"), (old_adapter_sha, adapter_sha, "ADAPTER.json")):
        s = sub1(re.escape(f"{src_cfg_prefix}/{old}/{fn}"), f"{BUCKET_CODE}/{new}/{fn}", s)
        s = sub1(re.escape(f"echo '{old}  /opt/arc3/config-audit/{fn}'"), f"echo '{new}  /opt/arc3/config-audit/{fn}'", s)
    # per-request chat templates (the 'high' effort) need vLLM's explicit opt-in
    s = sub1(re.escape("    --reasoning-parser qwen3 \\") + NL, "    --reasoning-parser qwen3 \\" + NL + "    --trust-request-chat-template \\" + NL, s)
    # high template + branch exports right before gameplay (after every bundled selftest)
    prep = NL.join(l[2:] if l.startswith("  ") else l for l in HIGH_PREP) + NL
    exports = (f"export ARC3_BRANCH_PACK=/opt/arc3/branchpack ARC3_BRANCH_SHARD={k}/{N_SHARDS} ARC3_BRANCH_DEADLINE_MIN={DEADLINE_MIN} "
               f"ARC3_HIGH_CHAT_TEMPLATE=/opt/arc3/high-chat-template.jinja" + NL)
    s = sub1(r"^capture_gameplay_metrics start$", prep + exports + "capture_gameplay_metrics start", s, re.M)
    old_req = re.search(r"requestId=([0-9a-f-]{36})", s).group(1); new_req = str(uuid.uuid4())
    s = s.replace(old_req, new_req); (ARM / "DELETE_REQUEST_ID").write_text(new_req)
    assert old_runner_sha not in s and old_cfg_sha not in s and old_adapter_sha not in s
    (ARM / "startup.sh").write_text(s, encoding="utf-8", newline=NL)
    arm = dict(src_arm)
    arm.update({
        "arm": ARM_NAME, "source_arm": "la_clean_return_hard7_132 (24-Sep) + branch_runner.py", "parent_run_id": PARENT_RUN,
        "runner_object": f"{BUCKET_CODE}/{runner_sha}/runner.py", "runner_sha256": runner_sha,
        "config_object": f"{BUCKET_CODE}/{cfg_sha}/CONFIG_FLAGS.json", "config_sha256": cfg_sha,
        "adapter_object": f"{BUCKET_CODE}/{adapter_sha}/ADAPTER.json", "adapter_sha256": adapter_sha,
        "branch_pack_object": pack_obj, "branch_pack_sha256": pack_sha, "shard": f"{k}/{N_SHARDS}", "jobs": len(my_jobs),
        "checkpoints": len({j['group'] for j in my_jobs}), "sum_orig_remaining_turns": sum(j["orig_remaining_turns"] for j in my_jobs),
        "run_id_prefix": f"g4run-branch-lacr-{WTAG}s{k}of{N_SHARDS}", "instance_prefix": f"arc3-g4-brlacr{WAVE}-s{k}", "tag": "branch",
    })
    (ARM / "ARM.json").write_text(json.dumps(arm, indent=2) + NL, encoding="utf-8")
    print(f"{ARM_NAME}: jobs={len(my_jobs)} checkpoints={arm['checkpoints']} turn-units={arm['sum_orig_remaining_turns']} cfg={cfg_sha[:10]}")
print("runner", runner_sha[:12], "effective", effective_runner_sha[:12], "adapter", adapter_sha[:12], "pack", pack_obj)
